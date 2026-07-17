# -*- coding: utf-8 -*-
"""
從 leaguepedia teams.json 建「戰隊縮寫碰撞」精簡對照 → team_collide.js
準則：同一聯賽的縮寫必唯一 → 同縮寫但跨不同聯賽＝不同隊(如 RoX/CIS vs ROX Tigers/LCK 都 Short=ROX)。
先把 Leaguepedia 的 Region 映射成聯賽碼(Europe/EMEA→LEC 之類，消掉假碰撞)，只留真的跨聯賽同縮寫。
輸出 window.TEAM_COLLIDE = { abbrs:[碰撞縮寫(大寫)...], names:{正規化全名: 聯賽碼} }
前端：某戰隊縮寫在 abbrs 裡、且該全名在 names 裡 → 清單顯示「縮寫(聯賽碼)」。
用法：python scripts/build_team_collide.py
"""
import os, json, re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEAMS = os.path.join(ROOT, "csv_cache", "lpedia", "teams.json")
OUT = os.path.join(ROOT, "team_collide.js")

# Leaguepedia Region → 賽區(聯賽)碼。顯示一律用賽區名稱而非地區名（TSW（LCP）而非 TSW（Asia Pacific））；
# 同聯賽的不同 Region 名要映到同一碼，避免假碰撞。新地區沒映到會在建置時印警告。
REGION2LG = {
    "Korea": "LCK", "China": "LPL",
    "Europe": "LEC", "EMEA": "LEC",
    "North America": "LCS",
    "Brazil": "CBLOL",
    "Latin America": "LLA",
    "Latin America North": "LLN", "LAN": "LLN",   # 拉美北(合併前)
    "Latin America South": "CLS", "LAS": "CLS",   # 拉美南(合併前)
    "Japan": "LJL", "Turkey": "TCL", "Vietnam": "VCS",
    "Oceania": "LCO", "SEA": "PCS", "Pacific": "PCS", "PCS": "PCS", "Taiwan": "PCS", "LMS": "LMS",
    "Asia Pacific": "LCP",                        # 2025 起亞太合併賽區
    "Americas": "LTA",                            # 2025 起美洲合併賽區
    "CIS": "LCL", "Commonwealth of Independent States": "LCL",  # 獨聯體賽區的聯賽＝LCL
    "MENA": "AL",                                 # 中東北非賽區的聯賽＝Arabian League
    "International": "INT",
}


def norm_name(s):
    return re.sub(r"[​‌‍⁠﻿]", "", str(s)).strip().lower()


def main():
    teams = json.load(open(TEAMS, encoding="utf-8"))
    by_short = defaultdict(list)          # 正規化縮寫(大寫) → [(正規化全名, 聯賽碼, 原始Region)]
    unmapped = set()
    for t in teams:
        short = (t.get("Short") or "").strip().upper()
        name = t.get("Name") or ""
        region = (t.get("Region") or "").strip()
        if not short or not name:
            continue
        lg = REGION2LG.get(region)
        if lg is None:
            if region: unmapped.add(region)
            lg = region or "?"
        by_short[short].append((norm_name(name), lg, region))
    if unmapped:
        print(f"⚠ 未映射的 Region（會以地區名原樣顯示，請補進 REGION2LG）：{sorted(unmapped)}")

    collide_abbrs, name2lg = [], {}
    for short, lst in by_short.items():
        lgs = {lg for _, lg, _ in lst}
        if len(lgs) > 1:                  # 真的跨聯賽 → 碰撞
            collide_abbrs.append(short)
            for name, lg, _ in lst:
                name2lg[name] = lg

    data = {"abbrs": sorted(collide_abbrs), "names": name2lg}
    open(OUT, "w", encoding="utf-8").write("window.TEAM_COLLIDE=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";")
    print(f"寫出 team_collide.js：{len(collide_abbrs)} 個碰撞縮寫、{len(name2lg)} 個全名對照")
    # 抽樣
    for a in ["ROX", "TL", "FNC"]:
        if a in collide_abbrs:
            ns = [n for n, lg in name2lg.items() if any(s == a for s in [a])][:0]
            print(f"  {a}: 碰撞", {lg for n, lg in name2lg.items()} if False else "")
    print("  ROX 對照:", {n: lg for n, lg in name2lg.items() if "rox" in n})


if __name__ == "__main__":
    main()
