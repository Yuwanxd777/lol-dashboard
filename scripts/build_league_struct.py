# -*- coding: utf-8 -*-
"""
聯賽結構補充表 → league_struct.js（讀 csv_cache/lpedia/ 快取，不打 API）
內容：每年 × 主聯賽 的「升降賽／資格賽」賽事清單＋參賽隊縮寫。
用途：圖鑑「賽事」樹狀圖——資料庫（OE）只有主聯賽場次，升降賽多為獨立賽事抓不到；
      以 Leaguepedia Tournaments(Name 含 Promotion/Relegation 或 IsQualifier) ＋ Standings(rosters) 補標。
輸出：window.LEAGUE_STRUCT = { "2016": { "LPL": { promo:[{n:"LPL 2016 Spring Promotion", t:["ROX",…]}] } } }
用法：python scripts/build_league_struct.py   （fetch_leaguepedia.py 抓完快取後執行；rosters 缺年份 → t 為空陣列）
"""
import json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "csv_cache", "lpedia")
OUT = os.path.join(ROOT, "league_struct.js")

# Leaguepedia League 全名 → 儀表板聯賽代碼（只收主聯賽；次級/國際賽不進升降賽表）
LG_MAP = [
    (re.compile(r"LoL Champions Korea|Champions Korea", re.I), "LCK"),
    (re.compile(r"Tencent LoL Pro League|LoL Pro League", re.I), "LPL"),
    (re.compile(r"EMEA Championship|European Championship|Europe League Championship|EU LCS", re.I), "LEC"),
    (re.compile(r"League of Legends Championship Series|North America League Championship|NA LCS|^LCS$", re.I), "LCS"),
    (re.compile(r"Circuit Brazilian|Campeonato Brasileiro", re.I), "CBLOL"),
    (re.compile(r"Liga Latinoam", re.I), "LLA"),
    (re.compile(r"LoL Japan League", re.I), "LJL"),
    (re.compile(r"Turkish Championship League", re.I), "TCL"),
    (re.compile(r"^Vietnam Championship Series$", re.I), "VCS"),
    (re.compile(r"Pacific Championship Series", re.I), "PCS"),
    (re.compile(r"LoL Master Series", re.I), "LMS"),
    (re.compile(r"Oceanic Pro League|Circuit Oceania", re.I), "LCO"),
    (re.compile(r"LoL Continental League", re.I), "LCL"),
    (re.compile(r"LTA North|Championship of The Americas North", re.I), "LTA N"),
    (re.compile(r"LTA South|Championship of The Americas South", re.I), "LTA S"),
    (re.compile(r"Championship of The Americas", re.I), "LTA"),   # 南北合併賽事（放在 North/South 之後）
    (re.compile(r"Championship Pacific", re.I), "LCP"),
    (re.compile(r"Latin America North", re.I), "LLN"),
    (re.compile(r"Latin America South|Copa Latinoam", re.I), "CLS"),
]


def norm(s):
    return re.sub(r"[​‌‍⁠﻿]", "", str(s or "")).strip().lower()


# ⚠ 不要用 Leaguepedia TournamentLevel 推儀表板「賽區級別」：它的 Primary＝該地區頂級聯賽（LJL/CBLOL 也是 Primary），
#   不等於樹狀圖的「國際一級賽區」。級別維持 index.html 的 LEAGUE_META＋LEAGUE_TIER_OVERRIDE 人工制。


def main():
    T = json.load(open(os.path.join(CACHE, "tournaments.json"), encoding="utf-8"))
    teams = json.load(open(os.path.join(CACHE, "teams.json"), encoding="utf-8"))
    rosters_p = os.path.join(CACHE, "rosters.json")
    R = json.load(open(rosters_p, encoding="utf-8")) if os.path.exists(rosters_p) else {}
    short_of = {}
    for t in teams:
        if t.get("Name"):
            short_of[norm(t["Name"])] = (t.get("Short") or t["Name"]).strip()

    out = {}
    # 一級賽區旗標：該年有世界賽席位（正賽/入圍賽）＝一級（csv_cache/worlds_tier1.json，fetch_worlds_tier1.py 產出）
    try:
        _t1 = json.load(open(os.path.join(CACHE, "..", "worlds_tier1.json"), encoding="utf-8"))
    except Exception:
        _t1 = {}
    for y, codes in _t1.items():
        for c in codes:
            out.setdefault(str(y), {}).setdefault(c, {})["t1"] = 1
    for y, ts in T.items():
        for t in ts:
            lg_full, nm = t.get("League") or "", t.get("Name") or ""
            code = next((c for rx, c in LG_MAP if rx.search(lg_full)), None)
            if not code:
                continue
            is_promo = bool(re.search(r"Promotion|Relegation", nm, re.I)) or t.get("IsQualifier") == "1"
            if not is_promo:
                continue
            op = t.get("OverviewPage") or nm
            # 縮寫對照：全名 → 去掉 Leaguepedia 消歧義後綴「(Korean Team)」再試 → 原名
            ab = lambda x: short_of.get(norm(x)) or short_of.get(norm(re.sub(r"\s*\([^)]*\)$", "", x))) or x
            tm = sorted({ab(x) for x in (R.get(op) or [])})
            out.setdefault(y, {}).setdefault(code, {}).setdefault("promo", []).append(
                {"n": nm, "t": tm})
    open(OUT, "w", encoding="utf-8").write(
        "window.LEAGUE_STRUCT=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";")
    n = sum(len(v.get("promo", [])) for yy in out.values() for v in yy.values())
    print(f"寫出 league_struct.js：{len(out)} 年、{n} 場升降/資格賽")
    # Leaguepedia 全名→縮寫 兜底表（abbrOf 鏈最低優先；補歷史年份次級/升降賽隊的縮寫，2026-07-16）
    lpw = {}
    for t in teams:
        nm, sh = t.get("Name"), (t.get("Short") or "").strip()
        if nm and sh and 1 <= len(sh) <= 6 and norm(nm) not in lpw:
            lpw[norm(nm)] = sh
    open(os.path.join(ROOT, "team_abbr_wiki.js"), "w", encoding="utf-8").write(
        "window.LP_TABBR=" + json.dumps(lpw, ensure_ascii=False, separators=(",", ":")) + ";")
    print(f"寫出 team_abbr_wiki.js：{len(lpw)} 隊 Leaguepedia 縮寫兜底")
    for y in ("2016", "2024"):
        if y in out:
            print(f"  {y}:", {k: len(v.get("promo", [])) for k, v in out[y].items() if v.get("promo")})


if __name__ == "__main__":
    main()
