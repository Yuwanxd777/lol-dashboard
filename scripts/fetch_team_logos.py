# -*- coding: utf-8 -*-
"""隊徽下載：dpm 的 https://dpm.lol/esport/teams/{隊縮寫}.webp → img/teams/{隊縮寫}.webp

隊清單＝scripts/soloq_accounts.json 的 team 欄（就是 dpm /v1/pros 回的字串，縮寫一致）。
已存在就跳過（隊徽幾乎不變；要強制重抓刪掉檔案再跑）。404＝dpm 沒這隊的圖，前端
onerror 會退回文字縮寫，不算錯誤。靜態圖檔不吃 Cloudflare 挑戰，urllib 直抓即可。

用法：  python scripts\\fetch_team_logos.py
"""
import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "img", "teams")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
# dpm 檔名跟我們縮寫不同的（實測 2026-08-04）：GEN 在 dpm 叫 GENG；查無的隊留在這裡補別名
ALIAS = {"GEN": "GENG"}


def main():
    accs = json.load(open(os.path.join(HERE, "soloq_accounts.json"), encoding="utf-8"))
    teams = sorted({str(a.get("team") or "").strip() for a in accs} - {""})
    os.makedirs(OUT, exist_ok=True)
    ok = skip = miss = 0
    for t in teams:
        fn = os.path.join(OUT, t + ".webp")
        if os.path.exists(fn) and os.path.getsize(fn) > 200:
            skip += 1
            continue
        url = "https://dpm.lol/esport/teams/" + urllib.parse.quote(ALIAS.get(t, t)) + ".webp"
        try:
            d = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()
            if len(d) < 200 or not d.startswith(b"RIFF"):
                miss += 1
                continue
            open(fn, "wb").write(d)
            ok += 1
            time.sleep(0.4)
        except Exception:
            miss += 1
    print(f"隊徽：新抓 {ok}／已有 {skip}／dpm 沒有 {miss}（共 {len(teams)} 隊）→ img/teams/")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"fetch_team_logos：執行失敗（{type(e).__name__}: {e}）")
    sys.exit(0)
