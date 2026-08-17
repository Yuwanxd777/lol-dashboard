# -*- coding: utf-8 -*-
"""英雄小頭像本機快取：DDragon 的英雄圖是 128×128 PNG（~28KB），全站卻只顯示 15~53px；
英雄Tier 一頁就從 CDN 拉 3.1MB。這支把現行版本的英雄圖抓下來縮成 96×96 WebP（~4KB，
高 DPI 顯示 53px 也夠銳利）放 img/champ/{id}.webp，並寫 champ_icons.js 當清單：
  window.CHAMP_ICONS={"v":"16.16.1","ids":[...]}
index.html 的 chIcoUrl(ver,id) 只在「同一季（大版號相同）＋清單裡有」時用本機小圖，
其餘（歷史年份的舊美術、清單外）照舊走 CDN；壞圖仍走 champImgFb 退回 CDN。

版本沒變、檔案齊全就跳過（每日排程跑很便宜）。用法：python scripts/fetch_champ_icons.py [--force]
需要 Pillow。
"""
import io, json, os, sys, urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DIR = os.path.join(ROOT, "img", "champ")
MANIFEST = os.path.join(ROOT, "champ_icons.js")
CDN = "https://ddragon.leagueoflegends.com/cdn"
SIZE = 96


def fetch(u, timeout=60):
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=timeout).read()


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
    old = {}
    if os.path.exists(MANIFEST):
        try:
            t = io.open(MANIFEST, encoding="utf-8").read()
            old = json.loads(t[t.index("=") + 1:].rstrip().rstrip(";"))
        except Exception:
            old = {}
    have = {i for i in ids if os.path.exists(os.path.join(OUT_DIR, i + ".webp"))}
    same_ver = old.get("v") == ver
    todo = ids if (force or not same_ver) else [i for i in ids if i not in have]
    if not todo and same_ver and set(old.get("ids") or []) == set(ids):
        print(f"fetch_champ_icons: {ver} 已是最新，{len(ids)} 隻齊全，跳過")
        return
    ok, fail = 0, []
    for cid in todo:
        try:
            raw = fetch(f"{CDN}/{ver}/img/champion/{cid}.png")
            im = Image.open(io.BytesIO(raw)).convert("RGBA").resize((SIZE, SIZE), Image.LANCZOS)
            im.save(os.path.join(OUT_DIR, cid + ".webp"), "WEBP", quality=82, method=6)
            ok += 1
        except Exception as e:
            fail.append((cid, str(e)[:60]))
    done = sorted(i for i in ids if os.path.exists(os.path.join(OUT_DIR, i + ".webp")))
    # 版本換了但有幾隻抓失敗：清單只列真的有檔的，缺的走 CDN，不會出現破圖
    io.open(MANIFEST, "w", encoding="utf-8", newline="\n").write(
        "window.CHAMP_ICONS=" + json.dumps({"v": ver, "ids": done}, ensure_ascii=False, separators=(",", ":")) + ";")
    total = sum(os.path.getsize(os.path.join(OUT_DIR, i + ".webp")) for i in done)
    print(f"fetch_champ_icons: {ver} 新抓 {ok} 隻、清單 {len(done)} 隻、共 {total // 1024} KB" + (f"、失敗 {fail}" if fail else ""))


if __name__ == "__main__":
    main()
