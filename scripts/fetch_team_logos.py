# -*- coding: utf-8 -*-
"""隊徽下載：dpm 的 https://dpm.lol/esport/teams/{隊縮寫}.webp → img/teams/{隊縮寫}.webp

隊清單＝scripts/soloq_accounts.json 的 team 欄（就是 dpm /v1/pros 回的字串，縮寫一致）。
已存在就跳過（隊徽幾乎不變；要強制重抓刪掉檔案再跑）。404／403＝dpm 沒這隊的圖，前端
onerror 會退回文字縮寫，不算錯誤。靜態圖檔不吃 Cloudflare 挑戰，urllib 直抓即可。

其他失敗（逾時、連線斷、429、5xx、回的不是圖）印 ⚠ 並列出隊名，下一班會再抓，所以不重試、rc 0；
連 2 隊連線類失敗就不再上網，避免 dpm 不回應時每隊都等 30 秒。隊伍名單讀不到才 exit 1。

用法：  python scripts\\fetch_team_logos.py
"""
import http.client
import io
import json
import os
import sys
import time
import urllib.error
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
MAX_CONN_FAIL = 2     # 連續幾隊連線類失敗就不再上網（下一班會再抓，不必在這班等完）


def main():
    accs = json.load(open(os.path.join(HERE, "soloq_accounts.json"), encoding="utf-8"))
    teams = sorted({str(a.get("team") or "").strip() for a in accs} - {""})
    os.makedirs(OUT, exist_ok=True)
    ok = skip = miss = 0
    failed = []
    conn_fail = 0
    for t in teams:
        fn = os.path.join(OUT, t + ".webp")
        if os.path.exists(fn) and os.path.getsize(fn) > 200:
            skip += 1
            continue
        if conn_fail >= MAX_CONN_FAIL:
            failed.append(t)
            continue
        url = "https://dpm.lol/esport/teams/" + urllib.parse.quote(ALIAS.get(t, t)) + ".webp"
        try:
            d = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read()
            conn_fail = 0
            if len(d) < 200 or not d.startswith(b"RIFF"):
                failed.append(t)
                continue
            tmp = fn + ".tmp"
            with open(tmp, "wb") as f:
                f.write(d)
            os.replace(tmp, fn)
            ok += 1
            time.sleep(0.4)
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                conn_fail = 0
                miss += 1
            else:
                conn_fail += 1
                failed.append(t)
        except OSError:      # URLError、逾時、連線斷（寫檔失敗也落在這，同樣下一班再來）
            conn_fail += 1
            failed.append(t)
        except http.client.HTTPException:      # 讀到一半斷線（IncompleteRead 等）
            conn_fail += 1
            failed.append(t)
    print(f"隊徽：新抓 {ok}／已有 {skip}／dpm 沒有 {miss}（共 {len(teams)} 隊）→ img/teams/")
    if failed:
        print(f"  ⚠ 隊徽抓不到 {len(failed)} 隊，下一班再抓：{', '.join(failed)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"fetch_team_logos：執行失敗（{type(e).__name__}: {e}）")
        sys.exit(1)
