# -*- coding: utf-8 -*-
"""歷年一級聯賽補齊（批次跑 fetch_wiki_mh）。

賽事名＝Leaguepedia 的 Tournaments.Name（就是 MatchHistoryGame 表單的 tournament 欄），
抓不到的會列在最後供人工補名。可重複執行：HTML 與 wikifill_{年}.json 都有快取。

用法：python scripts\\backfill_run.py [--years 2013,2014] [--force]
"""
import argparse, io, json, os, re, sys, time

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch_wiki_mh as MH

# (年, 聯賽碼, 賽段, 季後賽, [賽事名候選])
JOBS = [
    # ── 2013 ──
    (2013, "LCK", "Winter", 0, ["Champions 2013 Winter"]),
    (2013, "LCK", "Spring", 0, ["Champions 2013 Spring"]),
    (2013, "LCK", "Summer", 0, ["Champions 2013 Summer"]),
    (2013, "LPL", "Spring", 0, ["LPL 2013 Spring"]),
    (2013, "LPL", "Summer", 0, ["LPL 2013 Summer"]),
    (2013, "LEC", "Spring", 0, ["EU LCS 2013 Spring", "EU LCS Season 3 Spring"]),
    (2013, "LEC", "Summer", 0, ["EU LCS 2013 Summer", "EU LCS Season 3 Summer"]),
    (2013, "LCS", "Spring", 0, ["NA LCS 2013 Spring", "NA LCS Season 3 Spring"]),
    (2013, "LCS", "Summer", 0, ["NA LCS 2013 Summer", "NA LCS Season 3 Summer"]),
    (2013, "GPL", "Spring", 0, ["GPL 2013 Spring"]),
    (2013, "GPL", "Summer", 0, ["GPL 2013 Summer"]),
    (2013, "TCL", "Summer", 0, ["TCL 2013 Summer", "TCL 2013 Winter"]),
    # ── 2014 ──
    (2014, "LCK", "Winter", 0, ["Champions 2014 Winter"]),
    (2014, "LCK", "Spring", 0, ["Champions 2014 Spring"]),
    (2014, "LCK", "Summer", 0, ["Champions 2014 Summer"]),
    (2014, "LPL", "Spring", 0, ["LPL 2014 Spring"]),
    (2014, "LPL", "Summer", 0, ["LPL 2014 Summer"]),
    (2014, "LMS", "Summer", 0, ["LMS 2014 Summer", "GPL 2014 Summer"]),
    (2014, "GPL", "Spring", 0, ["GPL 2014 Spring"]),
    (2014, "CBLOL", "Spring", 0, ["CBLOL 2014 Split 1", "CBLOL 2014 Spring"]),
    (2014, "CBLOL", "Summer", 0, ["CBLOL 2014 Split 2", "CBLOL 2014 Summer"]),
    (2014, "TCL", "Summer", 0, ["TCL 2014 Summer", "TCL 2014 Winter"]),
    # ── 2015 ──
    (2015, "LPL", "Spring", 0, ["LPL 2015 Spring"]),
    (2015, "LPL", "Summer", 0, ["LPL 2015 Summer"]),
    (2015, "CBLOL", "Spring", 0, ["CBLOL 2015 Split 1", "CBLOL 2015 Spring"]),
    (2015, "CBLOL", "Summer", 0, ["CBLOL 2015 Split 2", "CBLOL 2015 Summer"]),
    (2015, "GPL", "Spring", 0, ["GPL 2015 Spring"]),
    (2015, "GPL", "Summer", 0, ["GPL 2015 Summer"]),
    # ── 2016（LPL 只有夏季，補春季）──
    (2016, "LPL", "Spring", 0, ["LPL 2016 Spring"]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="")
    ap.add_argument("--force", action="store_true")
    A = ap.parse_args()
    yrs = {int(x) for x in A.years.split(",") if x.strip()} if A.years else None
    ok, miss = [], []
    for (year, lg, split, po, names) in JOBS:
        if yrs and year not in yrs:
            continue
        key = f"{lg}_{year}_{re.sub(r'[^A-Za-z0-9]+','',split)}"
        print(f"\n[{year} {lg} {split}]", flush=True)
        done = False
        for nm in names:
            cfg = {"tour": nm, "league": lg, "split": split, "year": year, "playoffs": po, "key": key}
            try:
                t = MH.build(cfg, force=A.force)
            except Exception as e:
                print(f"    例外：{type(e).__name__} {str(e)[:80]}"); t = None
            if t and len(t) > 1:
                ok.append((year, lg, split, nm, len(t) - 1)); done = True; break
        if not done:
            miss.append(f"{year} {lg} {split}（試過：{names}）")
    print("\n" + "=" * 60)
    print(f"完成 {len(ok)} 個賽段：")
    for y, lg, sp, nm, n in ok:
        print(f"   {y} {lg:6s} {sp:8s} ← {nm}（{n} 列）")
    if miss:
        print(f"\n抓不到 {len(miss)} 個（需要正確的 Leaguepedia 賽事名）：")
        for m in miss:
            print("   " + m)


if __name__ == "__main__":
    main()
