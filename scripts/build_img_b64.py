# -*- coding: utf-8 -*-
"""本機圖片 → img_b64.js（window.IMG_B64＝{"img/champ/Aatrox.webp":"data:image/webp;base64,…"}）。

為什麼（使用者 2026-10-18「截圖顧名思義，就是要任何情況打開都是那畫面，甚至可能不連網」）：
  📸 截圖用 html2canvas 把畫面畫到 canvas 再存 PNG。用 file:// 開網頁時，本機圖片一畫上 canvas
  就被瀏覽器判成「污染」，存不出來 ⇒ _shotWarm 以前只能把它們藏起來（近期戰況截圖英雄圖、隊徽整片空白）。
  改走 CDN 又要連網。唯一兩全的做法：把本機圖先轉成 data URI 放進一支 .js——<script> 在 file:// 與離線都載得到，
  data URI 畫上 canvas 不會污染。這支只在按 📸 時才載入（_shotWarm），平常不影響開頁速度。
收：img/champ/*.webp、img/teams/*.webp、img/flags/*.png、img/rune/*（符文）、img/*.png（路線圖等）。
跑：python scripts/build_img_b64.py（排程 run_update ⑥ 收尾，fetch_champ_icons／fetch_team_logos／fetch_flags 之後）
"""
import base64, io, json, os, sys

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "img_b64.js")
MIME = {".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml"}
DIRS = ["img/champ", "img/teams", "img/flags", "img/rune", "img"]
SKIP = {"img/logo.jpg"}   # 站台 logo 很大、截圖用不到


def collect():
    out = {}
    for d in DIRS:
        p = os.path.join(ROOT, *d.split("/"))
        if not os.path.isdir(p):
            continue
        for f in sorted(os.listdir(p)):
            fp = os.path.join(p, f)
            ext = os.path.splitext(f)[1].lower()
            key = d + "/" + f
            if not os.path.isfile(fp) or ext not in MIME or key in SKIP:
                continue
            out[key] = "data:%s;base64,%s" % (MIME[ext], base64.b64encode(open(fp, "rb").read()).decode("ascii"))
    return out


def main():
    m = collect()
    txt = "window.IMG_B64=" + json.dumps(m, ensure_ascii=False, separators=(",", ":")) + ";\n"
    old = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
    if txt != old:
        open(OUT, "w", encoding="utf-8", newline="\n").write(txt)
    print("img_b64.js：%d 張圖、%.1f MB%s" % (len(m), len(txt) / 1048576, "" if txt != old else "（沒變）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
