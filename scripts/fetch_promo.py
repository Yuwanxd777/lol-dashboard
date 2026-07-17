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

API = "https://lol.fandom.com/api.php"

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
            if "error" in r:  # 限流等 API 錯誤：重退避重試（匿名限額嚴格）
                if i == retries - 1:
                    raise RuntimeError(r["error"].get("info", "cargo error"))
                time.sleep(60 * (i + 1)); continue
            time.sleep(6)  # 全域節流
            return [x["title"] for x in r.get("cargoquery", [])]
        except RuntimeError:
            raise
        except Exception:
            if i == retries - 1: raise
            time.sleep(10)

def lg_of(page):
    for p, lg in PREFIX_LG:
        if page.startswith(p):
            return lg
    return None

def main():
    if OUT_J.exists() and "--force" not in sys.argv and time.time() - OUT_J.stat().st_mtime < 30*86400:
        print("promo_games.json 未滿 30 天，跳過（--force 強制重抓）")
        return
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
    print(f"✅ {OUT_J.name} / {OUT_JS.name}")

if __name__ == "__main__":
    main()
