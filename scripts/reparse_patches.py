# -*- coding: utf-8 -*-
"""版本改動解析器的回歸稽核：拿**同一份官方頁面**用目前的 fetch_patches.parse() 重新解析，
和 csv_cache/patch_*.json（上一次解析結果）逐行比對。改 fetch_patches.py 之後一定要跑。

為什麼要這支（2026-08-17）：解析器改一條規則，往往同時修好幾個版本、又弄壞另外幾個版本
（停止字「錯誤修正」修好 26.16 卻砍掉 23.03 期中更新整段；「商店」修好 25.13 卻砍掉 24.19 防禦塔金錢）。
靠肉眼看幾個版本擋不住，要全庫比對。

用法：
  python scripts/reparse_patches.py            # 全庫重解析 → 印每版差異摘要（新增／消失的英雄與各區行數）
  python scripts/reparse_patches.py --lost     # 只列「舊有、新無」的行（連英雄名前綴去掉都對不到才算消失）→ 逐條判斷是不是模式垃圾
  python scripts/reparse_patches.py --detail 26.11 25.15   # 指定版本印逐行 +/-
  python scripts/reparse_patches.py --apply    # 確認差異都合理後，把新解析寫回 csv_cache（之後跑 fetch_patches.py --skip-discover
                                               #  重建 patches.js，再跑 clean_patch_text.py）
  python scripts/reparse_patches.py --en ...   # 同上但對英文版快取 patch_en_*.json（fetch_patches_en.py 用）

頁面 HTML 快取在 csv_cache/patch_html/{zh|en}/{pk}.html（第一次跑會抓 ~170 頁，之後直接讀快取；--refetch 重抓）。
⚠ 英文快取（_lang=en-us 的 patch_*.json）裡的英雄行是抓取當下翻譯過的，--apply 只換 _extra／新增英雄（翻譯後）／刪消失的英雄，
  不動既有英雄行（沒辦法拿英文比中文）。
"""
import io, json, os, re, sys, glob, time

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fetch_patches as fp  # noqa: E402

CACHE = os.path.join(ROOT, "csv_cache")


def _lines(d):
    """(區/英雄, 行) 平鋪；英雄用 @Key"""
    out = []
    for k, v in d.items():
        if k == "_extra" and isinstance(v, dict):
            for sec, ls in v.items():
                for l in ls or []:
                    out.append((sec, l))
        elif not k.startswith("_") and isinstance(v, list):
            for l in v:
                out.append(("@" + k, l))
    return out


def _suffix(l):
    return l.split("｜", 1)[1] if "｜" in l else l


def main():
    args = sys.argv[1:]
    en = "--en" in args
    apply = "--apply" in args
    lost = "--lost" in args
    refetch = "--refetch" in args
    detail = set()
    if "--detail" in args:
        i = args.index("--detail")
        detail = {a for a in args[i + 1:] if re.match(r"^\d\d\.\d\d$", a)}
    hdir = os.path.join(CACHE, "patch_html", "en" if en else "zh")
    os.makedirs(hdir, exist_ok=True)
    pat = "patch_en_*.json" if en else "patch_*.json"
    rx = re.compile(r"patch_en_(\d\d\.\d\d)\.json$" if en else r"patch_(\d\d\.\d\d)\.json$")
    files = [f for f in sorted(glob.glob(os.path.join(CACHE, pat))) if rx.search(f)]
    tot_lost = 0
    for f in files:
        pk = rx.search(f).group(1)
        old = json.load(open(f, encoding="utf-8"))
        url = old.get("_url")
        if not url:
            continue
        hp = os.path.join(hdir, pk + ".html")
        if os.path.exists(hp) and not refetch:
            html = io.open(hp, encoding="utf-8").read()
        else:
            try:
                html = fp.fetch(url)
            except Exception as e:
                print(f"{pk}: 抓不到 {url}：{e}")
                continue
            io.open(hp, "w", encoding="utf-8").write(html)
            time.sleep(0.2)
        new = fp.parse(html)
        if not new or not [k for k in new if not k.startswith("_")]:
            print(f"{pk}: 重新解析是空的（版型變了？），略過")
            continue
        lang = old.get("_lang", "en-us" if en else "zh-tw")
        translated_champs = (not en) and lang == "en-us"   # 英文頁的英雄行在快取裡是翻過的
        ok = [k for k in old if not k.startswith("_")]
        nk = [k for k in new if not k.startswith("_")]
        oe = old.get("_extra") or {}
        ne = new.get("_extra") or {}
        added = [k for k in nk if k not in ok]
        removed = [k for k in ok if k not in nk]
        chg = {} if translated_champs else {k: (len([x for x in new[k] if x not in old[k]]),
                                                len([x for x in old[k] if x not in new[k]]))
                                            for k in nk if k in ok and old[k] != new[k]}
        exd = {s: (len(oe.get(s, [])), len(ne.get(s, []))) for s in sorted(set(oe) | set(ne)) if oe.get(s) != ne.get(s)}
        if lost:
            if translated_champs:
                continue
            newset = {l for _, l in _lines(new)}
            newsuf = {_suffix(l) for _, l in _lines(new)}
            ls = [(sec, l) for sec, l in _lines(old) if l not in newset and _suffix(l) not in newsuf]
            if ls:
                tot_lost += len(ls)
                print(f"===== {pk} 消失 {len(ls)} 行")
                for sec, l in ls:
                    print(f"    {sec} | {l[:130]}")
            continue
        if added or removed or chg or exd:
            print(f"{pk} [{lang}] 英雄 {len(ok)}→{len(nk)}"
                  + (f" +{added}" if added else "") + (f" -{removed}" if removed else "")
                  + (f" 改{chg}" if chg else "") + (f" 區{exd}" if exd else ""))
        if pk in detail:
            for k in nk:
                if k in ok and old[k] != new[k] and not translated_champs:
                    for x in new[k]:
                        if x not in old[k]:
                            print(f"    @{k} + {x[:140]}")
                    for x in old[k]:
                        if x not in new[k]:
                            print(f"    @{k} - {x[:140]}")
            for sec in sorted(set(oe) | set(ne)):
                a, b = oe.get(sec, []), ne.get(sec, [])
                for x in b:
                    if x not in a:
                        print(f"    {sec} + {x[:140]}")
                for x in a:
                    if x not in b:
                        print(f"    {sec} - {x[:140]}")
        if apply:
            if translated_champs:
                out = dict(old)
                if ne:
                    out["_extra"] = ne
                elif "_extra" in out:
                    del out["_extra"]
                if new.get("_spotlight"):
                    out["_spotlight"] = new["_spotlight"]
                for k in added:
                    out[k] = [fp.translate_line(x) for x in new[k]]
                for k in removed:
                    del out[k]
            else:
                out = dict(new)
                out["_url"] = url
                if not en:
                    out["_lang"] = lang
            json.dump(out, open(f, "w", encoding="utf-8"), ensure_ascii=False)
    if lost:
        print(f"消失合計 {tot_lost} 行")
    if apply:
        print("已寫回快取。接著：python scripts/fetch_patches.py --skip-discover → python scripts/clean_patch_text.py"
              if not en else "已寫回快取。接著：python scripts/fetch_patches_en.py")


if __name__ == "__main__":
    main()
