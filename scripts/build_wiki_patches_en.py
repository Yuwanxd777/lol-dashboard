# -*- coding: utf-8 -*-
"""wiki 歷年改動的**英文原文** → wiki_patches_en.js（給英文模式用）

為什麼要有（2026-09-21 迴圈第 1 項）：
  英文模式的「歷年改動」有一大票版本只有中文。官方英文公告（patches_en.js）只到 19.01，
  而且 2019~2024 也有不少版本官方根本沒收該英雄／道具 ⇒ 那些條目只有 wiki 有，
  但我們發布的 wiki_patches.js 是**翻譯後**的成品（fetch_wiki.py 的 clean_lines 會套精譯表），
  英文原文在輸出時就沒了 ⇒ 英文畫面只好顯示中文。

  好消息是**英文原文一直都在** `csv_cache/wiki/<英雄>.json`（fetch_wiki.py 抓下來的原始快取，
  翻譯之前的樣子）。這支就是把那份快取直接攤成跟 wiki_patches.js 同樣形狀的英文版。

輸出：wiki_patches_en.js
  window.WIKI_PATCHES_EN = { "<wiki 版本號>": { "<英雄>": ["Skill｜text", …] } }
  版本號沿用 wiki 的寫法（9.9／14.4），前端的 wikiVerPk() 會換算成我們的 pk（19.09／24.04）。

⚠ 只做結構清理，**不翻譯、不改寫**——這支的全部價值就是「原文」。
⚠ 只有英雄（csv_cache/wiki/ 底下就是逐英雄一個檔）。道具／物件／符文的 wiki 快取不在這裡，
  那幾類的英文缺口要另外處理。

用法：python scripts\\build_wiki_patches_en.py
"""
import io, json, os, re, sys

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, "csv_cache", "wiki")
OUT = os.path.join(ROOT, "wiki_patches_en.js")


def ver_key(v):
    p = str(v).split(".")
    try:
        return (int(p[0]), int(p[1]))
    except Exception:
        return (0, 0)


def clean(ls):
    """結構清理：壓空白、丟只剩標點的殘渣。**不碰字義**。"""
    out = []
    for l in ls or []:
        t = re.sub(r"\s+", " ", str(l or "")).strip()
        if not t or not re.search(r"[0-9A-Za-z]", t):
            continue
        out.append(t)
    return out


def build_obj():
    """物件（塔／龍／巴龍／野區…）的 wiki 英文原文 → wiki_objectives_en.js。
    csv_cache/wiki_obj/<Key>.json 的形狀跟 window.WIKI_OBJECTIVES 一模一樣（{pk:[行]}），
    而且版本號就是我們的 pk ⇒ 直接攤平即可。"""
    cdir = os.path.join(ROOT, "csv_cache", "wiki_obj")
    out2 = os.path.join(ROOT, "wiki_objectives_en.js")
    if not os.path.isdir(cdir):
        print("（沒有 csv_cache/wiki_obj，略過物件英文）")
        return
    obj = {}
    for fn in sorted(os.listdir(cdir)):
        if not fn.endswith(".json"):
            continue
        try:
            d = json.load(open(os.path.join(cdir, fn), encoding="utf-8"))
        except Exception as e:
            print(f"  ⚠ {fn} 讀不動（略過）：{str(e)[:60]}")
            continue
        if not isinstance(d, dict):
            continue
        cur = {}
        for v, ls in d.items():
            c = clean(ls)
            if c:
                cur[str(v)] = c
        if cur:
            obj[fn[:-5]] = cur
    with open(out2, "w", encoding="utf-8") as f:
        f.write("window.WIKI_OBJECTIVES_EN=" + json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + ";\n")
    lines = sum(len(x) for v in obj.values() for x in v.values())
    print(f"物件：{len(obj)} 個 / {lines} 行 → {out2}（{os.path.getsize(out2)/1024:.0f} KB）")


def main():
    build_obj()
    if not os.path.isdir(CACHE):
        print(f"⚠ 找不到 {CACHE}（fetch_wiki.py 還沒跑過？）→ 不寫檔")
        return 0
    by_ver = {}
    n_champ = 0
    for fn in sorted(os.listdir(CACHE)):
        if not fn.endswith(".json"):
            continue
        champ = fn[:-5]
        try:
            d = json.load(open(os.path.join(CACHE, fn), encoding="utf-8"))
        except Exception as e:
            print(f"  ⚠ {fn} 讀不動（略過）：{str(e)[:60]}")
            continue
        if not isinstance(d, dict):
            continue
        n_champ += 1
        for v, ls in d.items():
            c = clean(ls)
            if c:
                by_ver.setdefault(str(v), {})[champ] = c
    obj = {v: by_ver[v] for v in sorted(by_ver, key=ver_key)}
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.WIKI_PATCHES_EN=" + json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + ";\n")
    lines = sum(len(x) for v in obj.values() for x in v.values())
    print(f"完成：{len(obj)} 個版本 / {n_champ} 個英雄 / {lines} 行 → {OUT}"
          f"（{os.path.getsize(OUT)/1024:.0f} KB）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
