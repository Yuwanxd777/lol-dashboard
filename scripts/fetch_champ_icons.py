# -*- coding: utf-8 -*-
"""英雄／符文小圖本機快取（2026-08-17 效能體檢）。
- 英雄：DDragon 的英雄圖是 128×128 PNG（~28KB），全站卻只顯示 15~53px；英雄Tier 一頁就從 CDN 拉 3.1MB。
  把現行版本的英雄圖抓下來縮成 96×96 WebP（~2KB，高 DPI 顯示 53px 也夠銳利）放 img/champ/{id}.webp。
- 符文：rune_icons.js 指到 CDragon 原檔（128~512px PNG），圖鑑符文分區一頁 1.7MB → img/rune/{檔名}.webp 96px。
清單寫 champ_icons.js：window.CHAMP_ICONS={"v":"16.16.1","ids":[...],"runes":[...檔名（不含 .png）...]}
index.html 的 chIcoUrl(ver,id) 只在「同一季（大版號相同）＋清單裡有」時用本機小圖，其餘（歷史年份的舊美術、
清單外）照舊走 CDN；壞圖仍走 champImgFb 退回 CDN。runeImgOf 依檔名對照，清單沒有的照舊 CDragon。

版本沒變、檔案齊全就跳過（每日排程跑很便宜）。用法：python scripts/fetch_champ_icons.py [--force]
需要 Pillow。
"""
import io, json, os, sys, urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, "img", "champ")
RUNE_DIR = os.path.join(ROOT, "img", "rune")
MANIFEST = os.path.join(ROOT, "champ_icons.js")
CDN = "https://ddragon.leagueoflegends.com/cdn"
SIZE = 96


def fetch(u, timeout=60):
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=timeout).read()


def read_manifest():
    if not os.path.exists(MANIFEST):
        return {}
    try:
        t = io.open(MANIFEST, encoding="utf-8").read()
        return json.loads(t[t.index("=") + 1:].rstrip().rstrip(";"))
    except Exception:
        return {}


def build_runes(Image):
    """符文圖：rune_icons.js 的每個圖 URL → img/rune/{檔名}.webp（只補缺的）。回傳有檔的檔名清單。"""
    os.makedirs(RUNE_DIR, exist_ok=True)
    try:
        t = io.open(os.path.join(ROOT, "rune_icons.js"), encoding="utf-8").read()
        d = json.loads(t[t.index("=") + 1:].rstrip().rstrip(";"))
    except Exception:
        return []
    urls = set(v.get("img") for v in (d.get("byId") or {}).values() if isinstance(v, dict) and v.get("img"))
    urls |= set(u for u in (d.get("byName") or {}).values() if isinstance(u, str))
    names = {}
    for u in urls:
        base = u.split("/")[-1]
        if base.lower().endswith(".png"):
            names[base[:-4]] = u
    for base, u in sorted(names.items()):
        fp = os.path.join(RUNE_DIR, base + ".webp")
        if os.path.exists(fp):
            continue
        try:
            im = Image.open(io.BytesIO(fetch(u))).convert("RGBA")
            if max(im.size) > SIZE:
                im = im.resize((SIZE, SIZE), Image.LANCZOS)
            im.save(fp, "WEBP", quality=82, method=6)
        except Exception:
            pass
    return sorted(b for b in names if os.path.exists(os.path.join(RUNE_DIR, b + ".webp")))


def main():
    force = "--force" in sys.argv
    try:
        from PIL import Image
    except Exception:
        print("fetch_champ_icons: 沒有 Pillow，略過（pip install pillow）")
        return
    ver = json.loads(fetch("https://ddragon.leagueoflegends.com/api/versions.json"))[0]
    ids = sorted(json.loads(fetch(f"{CDN}/{ver}/data/en_US/champion.json"))["data"].keys())
    os.makedirs(OUT_DIR, exist_ok=True)
    old = read_manifest()
    have = {i for i in ids if os.path.exists(os.path.join(OUT_DIR, i + ".webp"))}
    same_ver = old.get("v") == ver
    todo = ids if (force or not same_ver) else [i for i in ids if i not in have]
    ok, fail = 0, []
    for cid in todo:
        try:
            im = Image.open(io.BytesIO(fetch(f"{CDN}/{ver}/img/champion/{cid}.png"))).convert("RGBA").resize((SIZE, SIZE), Image.LANCZOS)
            im.save(os.path.join(OUT_DIR, cid + ".webp"), "WEBP", quality=82, method=6)
            ok += 1
        except Exception as e:
            fail.append((cid, str(e)[:60]))
    done = sorted(i for i in ids if os.path.exists(os.path.join(OUT_DIR, i + ".webp")))
    runes = build_runes(Image)
    new = {"v": ver, "ids": done, "runes": runes}
    if new == old and not todo:
        print(f"fetch_champ_icons: {ver} 已是最新，英雄 {len(done)}／符文 {len(runes)} 齊全，跳過")
        return
    # 版本換了但有幾隻抓失敗：清單只列真的有檔的，缺的走 CDN，不會出現破圖
    io.open(MANIFEST, "w", encoding="utf-8", newline="\n").write(
        "window.CHAMP_ICONS=" + json.dumps(new, ensure_ascii=False, separators=(",", ":")) + ";")
    total = sum(os.path.getsize(os.path.join(OUT_DIR, i + ".webp")) for i in done)
    rtotal = sum(os.path.getsize(os.path.join(RUNE_DIR, b + ".webp")) for b in runes)
    print(f"fetch_champ_icons: {ver} 英雄新抓 {ok}、清單 {len(done)} 隻 {total // 1024} KB；符文 {len(runes)} 張 {rtotal // 1024} KB"
          + (f"；失敗 {fail}" if fail else ""))


if __name__ == "__main__":
    main()
