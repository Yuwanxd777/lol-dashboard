# -*- coding: utf-8 -*-
"""列出 img/teams/*.webp 與 img/flags/*.png 有哪些檔 → img_manifest.js（window.IMG_HAVE）。

為什麼（2026-09-06 線 1 稽核）：teamLogoHTML 的做法是「先試隊徽、404 再試國旗、再 404 才退文字」，
每個沒有隊徽的隊（SEN／JPN／VIE 這種國家隊或 dpm 沒收的隊）每次畫面重繪都噴 404 到 console。
有了清單，前端先查再決定要不要放 <img>，一個 404 都不會發。

跑在 run_update 的第⑥階段（fetch_team_logos／fetch_flags 之後）；也可以手動跑。只寫 img_manifest.js。
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "img_manifest.js")


def main():
    teams = sorted(os.path.splitext(f)[0] for f in os.listdir(os.path.join(ROOT, "img", "teams")) if f.lower().endswith(".webp"))
    flags = sorted(os.path.splitext(f)[0] for f in os.listdir(os.path.join(ROOT, "img", "flags")) if f.lower().endswith(".png"))
    payload = {"teams": {t: 1 for t in teams}, "flags": {f: 1 for f in flags}}
    # 撞名的隊（同縮寫不同隊，fetch_team_logos_wiki.py 產）：隊名 → 自己的隊徽檔名，"-"＝沒有隊徽（不要借用同縮寫別隊的）
    al = os.path.join(ROOT, "csv_cache", "team_logo_alias.json")
    if os.path.exists(al):
        payload["alias"] = {n: k for n, k in json.load(io.open(al, encoding="utf-8")).items() if k == "-" or k in payload["teams"]}
    io.open(OUT, "w", encoding="utf-8").write("window.IMG_HAVE=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print("img_manifest.js：隊徽 %d 個、國旗 %d 個" % (len(teams), len(flags)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
