# -*- coding: utf-8 -*-
"""
升降賽基準資料：Leaguepedia Cargo API → promo_games.json + promo_abbr.js

以 wiki 為準的升降賽判定：抓各一級聯賽的 Promotion 賽事逐場對戰（隊伍＋日期），
fetch_data.py 用「隊伍配對＋日期」精準標記 split=升降賽。
同時抓參賽隊的官方縮寫（Teams.Short）供前端戰隊縮寫表預填。

用法：python scripts/fetch_promo.py
"""
import json, re, sys, time, urllib.request, urllib.parse
from pathlib import Path

ROOT   = Path(__file__).resolve().parent.parent
OUT_J  = ROOT / "csv_cache/promo_games.json"
OUT_JS = ROOT / "promo_abbr.js"
# 「這次嘗試過了」的戳記。成功會刪掉、失敗會留著。
# 沒有它的話：失敗 ⇒ 不寫 OUT_J ⇒ OUT_J 的 mtime 永遠不動 ⇒ 下面 30 天那條永遠成立 ⇒ 每一班都重抓一次。
TRY_ST = ROOT / "csv_cache/promo_last_try.txt"

API = "https://lol.fandom.com/api.php"

# 這份資料 30 天才更新一次，晚一天完全沒差，不值得讓排程班次空等。
# 2026-09-09 22:00 那班就是：Leaguepedia 回限流 ⇒ 舊版退避 60/120/…/420 秒共睡 1682.8 秒才放棄，
# 整班牆鐘從 7.5 分鐘變成 33.1 分鐘，而且失敗不留戳記 ⇒ 每一班都會再燒一次。
RETRY_BUDGET_S = 90      # 整支腳本（跨所有查詢）在退避上最多花這麼多秒，超過就放棄
RETRY_AFTER_H  = 20      # 上次嘗試失敗後這麼多小時內不再試（排程一天兩班 ⇒ 每天最多重試一次）
# 可重試的 API 錯誤碼；其餘（查詢寫錯、資料表不存在…）重試幾次都一樣，立刻放棄別空等。
RETRYABLE = ("ratelimited", "maxlag", "readonly", "internal_api_error", "busy")

_SLEPT = 0.0             # 這次執行已經花在退避上的秒數（全域預算，所有查詢共用）


def _backoff(sec, why):
    """退避睡眠。回傳 False＝總預算用完，呼叫端該放棄了。"""
    global _SLEPT
    left = RETRY_BUDGET_S - _SLEPT
    if left <= 0:
        return False
    sec = min(sec, left)
    print("   ⏳ %s，退避 %.0fs（退避已用 %.0f/%.0fs）" % (why, sec, _SLEPT, RETRY_BUDGET_S), flush=True)
    time.sleep(sec)
    _SLEPT += sec
    return True

# Leaguepedia OverviewPage 前綴 → 儀表板聯賽代碼
PREFIX_LG = [
    ("LCK/", "LCK"), ("Champions/", "LCK"),          # Champions = LCK 前身
    ("LPL/", "LPL"),
    ("NA LCS/", "LCS"), ("LCS/", "LCS"),
    ("EU LCS/", "LEC"), ("LEC/", "LEC"),
    ("LMS/", "LMS"), ("CBLOL/", "CBLOL"), ("LJL/", "LJL"),
    ("TCL/", "TCL"), ("LCL/", "LCL"),
    ("OPL/", "LCO"), ("LCO/", "LCO"),
    ("VCS/", "VCS"), ("PCS/", "PCS"), ("LCP/", "LCP"),
    ("LLA/", "LLA"), ("LLN/", "LLN"), ("CLS/", "CLS"), ("GPL/", "GPL"),
]

def cargo(params, retries=8):
    q = urllib.parse.urlencode({"action": "cargoquery", "format": "json", "limit": "500", **params})
    req = urllib.request.Request(API + "?" + q, headers={"User-Agent": "Mozilla/5.0 lol-dashboard"})
    for i in range(retries):
        try:
            r = json.loads(urllib.request.urlopen(req, timeout=60).read())
            if "error" in r:  # 限流等 API 錯誤：退避重試（匿名限額嚴格），但受 RETRY_BUDGET_S 封頂
                code = str(r["error"].get("code", "") or "?")
                info = r["error"].get("info", "cargo error")
                if code not in RETRYABLE:
                    raise RuntimeError("cargo API 錯誤（不可重試的錯誤碼，直接放棄）：%s — %s" % (code, info))
                if i == retries - 1 or not _backoff(20 * (i + 1), "API %s" % code):
                    raise RuntimeError("cargo API 錯誤（退避預算 %ds 用完）：%s — %s" % (RETRY_BUDGET_S, code, info))
                continue
            time.sleep(6)  # 全域節流
            return [x["title"] for x in r.get("cargoquery", [])]
        except RuntimeError:
            raise
        except Exception as e:
            if i == retries - 1 or not _backoff(10, "連線失敗 %s" % type(e).__name__):
                raise

def lg_of(page):
    for p, lg in PREFIX_LG:
        if page.startswith(p):
            return lg
    return None

def main():
    force = "--force" in sys.argv
    if OUT_J.exists() and not force and time.time() - OUT_J.stat().st_mtime < 30*86400:
        print("promo_games.json 未滿 30 天，跳過（--force 強制重抓）")
        return
    if TRY_ST.exists() and not force:
        age_h = (time.time() - TRY_ST.stat().st_mtime) / 3600.0
        if age_h < RETRY_AFTER_H:
            print("上次嘗試在 %.1f 小時前沒成功（未滿 %d 小時），這班跳過（--force 強制重抓）"
                  % (age_h, RETRY_AFTER_H))
            return
    TRY_ST.parent.mkdir(parents=True, exist_ok=True)
    TRY_ST.write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    # 1) 所有 Promotion 賽事（含 offset 翻頁）
    tours, offset = [], 0
    while True:
        rows = cargo({"tables": "Tournaments", "fields": "Tournaments.Name,Tournaments.OverviewPage,Tournaments.Year",
                      "where": "Tournaments.Name LIKE '%Promotion%'", "offset": str(offset)})
        tours += rows
        if len(rows) < 500: break
        offset += 500
    ours = [(t["OverviewPage"], lg_of(t["OverviewPage"]), t["Year"]) for t in tours]
    ours = [(p, lg, y) for p, lg, y in ours if lg]
    print(f"Promotion 賽事共 {len(tours)}，屬於一級聯賽的 {len(ours)}")

    # 2) 逐賽事抓場次（分批 IN 查詢）
    games, teams = [], set()
    pages = [p for p, _, _ in ours]
    lgmap = {p: (lg, y) for p, lg, y in ours}
    for i in range(0, len(pages), 25):
        chunk = pages[i:i+25]
        inlist = ",".join("'" + p.replace("'", "\\'") + "'" for p in chunk)
        rows = cargo({"tables": "ScoreboardGames",
                      "fields": "ScoreboardGames.Team1,ScoreboardGames.Team2,ScoreboardGames.DateTime_UTC,ScoreboardGames.OverviewPage",
                      "where": f"ScoreboardGames.OverviewPage IN ({inlist})"})
        for r in rows:
            lg, y = lgmap.get(r["OverviewPage"], (None, None))
            if not lg or not r.get("Team1") or not r.get("Team2"): continue
            # Cargo 輸出鍵名會把底線轉空格：DateTime_UTC → "DateTime UTC"
            d = (r.get("DateTime UTC") or r.get("DateTime_UTC") or "")[:10]
            games.append({"lg": lg, "y": y, "d": d, "t1": r["Team1"], "t2": r["Team2"]})
            teams.add(r["Team1"]); teams.add(r["Team2"])
        time.sleep(0.4)
    print(f"升降賽場次 {len(games)}，隊伍 {len(teams)}")

    # 3) 隊伍縮寫
    abbr = {}
    tl = sorted(teams)
    for i in range(0, len(tl), 40):
        chunk = tl[i:i+40]
        inlist = ",".join("'" + t.replace("'", "\\'") + "'" for t in chunk)
        rows = cargo({"tables": "Teams", "fields": "Teams.Name,Teams.Short",
                      "where": f"Teams.Name IN ({inlist})"})
        for r in rows:
            if r.get("Short"): abbr[r["Name"]] = r["Short"]
        time.sleep(0.4)
    print(f"縮寫命中 {len(abbr)}/{len(teams)}")

    OUT_J.write_text(json.dumps({"games": games, "abbr": abbr}, ensure_ascii=False), encoding="utf-8")
    OUT_JS.write_text("window.PROMO_ABBR=" + json.dumps(abbr, ensure_ascii=False, separators=(",", ":")) + ";",
                      encoding="utf-8")
    try:
        TRY_ST.unlink()   # 成功了就把戳記收掉（下次到期照常重抓）
    except OSError:
        pass
    print(f"✅ {OUT_J.name} / {OUT_JS.name}")

if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        # 預期內的放棄（限流／API 錯誤）：印清楚的一行、離開碼非 0，不要吐 traceback。
        print("⚠ fetch_promo 放棄：%s" % e)
        print("   已留戳記 %s，%d 小時內不再重試（--force 可強制）。" % (TRY_ST.name, RETRY_AFTER_H))
        sys.exit(1)
