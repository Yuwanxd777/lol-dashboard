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
    # 賽區錦標賽（決定世界賽代表）：韓國與中國都有，賽事名不照同一套規則
    #（韓國＝Korea Regional Finals Season 3、中國＝China Regional Finals Season 3）
    (2013, "LCK", "錦標賽", 0, ["Korea Regional Finals Season 3", "Season 3 Korea Regional Finals"]),
    (2013, "LPL", "錦標賽", 0, ["China Regional Finals Season 3", "Season 3 China Regional Finals"]),
    (2013, "LPL", "Spring", 0, ["LPL 2013 Spring"]),
    (2013, "LPL", "Summer", 0, ["LPL 2013 Summer"]),
    (2013, "LEC", "Spring", 0, ["EU LCS 2013 Spring", "EU LCS Season 3 Spring"]),
    (2013, "LEC", "Summer", 0, ["EU LCS 2013 Summer", "EU LCS Season 3 Summer"]),
    (2013, "LCS", "Spring", 0, ["NA LCS 2013 Spring", "NA LCS Season 3 Spring"]),
    (2013, "LCS", "Summer", 0, ["NA LCS 2013 Summer", "NA LCS Season 3 Summer"]),
    (2013, "GPL", "Spring", 0, ["GPL 2013 Spring"]),
    (2013, "GPL", "Summer", 0, ["GPL 2013 Summer"]),
    # ── 2013 外卡／其他賽區（使用者 2026-07-31 追加的 wiki 連結）──
    # 賽事名一律用 Page Forms 的自動完成 API 查出來的 Tournaments.Name（別自己猜）：
    #   api.php?action=pfautocomplete&cargo_table=Tournaments&cargo_field=Name&substr=關鍵字
    # 早年頁名不照現代規則（土耳其＝Riot Turkey Season 3…、CIS＝Regional CIS Championship 2013）
    # 世界賽本體的 split 留空（其他年份的 WLDs 也是空的，篩選列才不會冒出「Main」）；
    # 國際外卡賽（賽前一個月打、勝者進世界賽）＝世界賽的入圍賽，併進 WLDs 用 split 標
    #（使用者定案 2026-07-31），不要拆成獨立聯賽碼
    # 第 6 個元素＝版本覆寫：wiki 的 MatchHistoryGame 對 2013 世界賽沒填 Patch 欄，
    # 但那屆就是 3.11 打完的（使用者提供 2026-07-31）→ 儀表板格式 13.11
    (2013, "WLDs", "", 0, ["Season 3 World Championship"], "3.11"),
    (2013, "WLDs", "入圍賽", 0, ["IWCT 2013"]),
    (2013, "CBLOL", "Season", 0, ["Riot Season 3 Brazilian Championship"]),
    (2013, "LCO", "Season", 0, ["Riot Season 3 Oceanic Championship"]),
    (2013, "TCL", "Winter", 0, ["Riot Turkey Season 3 Winter Tournament"]),
    (2013, "TCL", "Spring", 0, ["Riot Turkey Season 3 Spring Tournament"]),
    (2013, "TCL", "Summer", 0, ["Riot Turkey Season 3 Summer Tournament"]),
    (2013, "LCL", "Season", 0, ["Regional CIS Championship 2013"]),
    # ── 2014 ──
    (2014, "LCK", "Winter", 0, ["Champions 2014 Winter"]),
    (2014, "LCK", "Spring", 0, ["Champions 2014 Spring"]),
    (2014, "LCK", "Summer", 0, ["Champions 2014 Summer"]),
    (2014, "LPL", "Spring", 0, ["LPL 2014 Spring"]),
    (2014, "LPL", "Summer", 0, ["LPL 2014 Summer"]),
    # LMS 2014 不存在（LMS 2015 才開賽，2014 台港澳在 GPL 底下）→ 不要再加回來
    (2014, "GPL", "Winter", 0, ["GPL 2014 Winter"]),
    (2014, "GPL", "Spring", 0, ["GPL 2014 Spring"]),
    (2014, "GPL", "Summer", 0, ["GPL 2014 Summer"]),
    (2014, "CBLOL", "Season", 0, ["Brazilian Champions Series 2014"]),
    (2014, "TCL", "Winter", 0, ["TCL 2014 Winter"]),
    (2014, "TCL", "Spring", 0, ["TCL 2014 Spring"]),
    (2014, "TCL", "Summer", 0, ["TCL 2014 Summer"]),
    # ── 2015 ──
    (2015, "LPL", "Spring", 0, ["LPL 2015 Spring"]),
    (2015, "LPL", "Summer", 0, ["LPL 2015 Summer"]),
    (2015, "CBLOL", "Split 1", 0, ["CBLOL 2015 Split 1"]),
    (2015, "CBLOL", "Split 2", 0, ["CBLOL 2015 Split 2"]),
    (2015, "GPL", "Spring", 0, ["GPL 2015 Spring"]),
    (2015, "GPL", "Summer", 0, ["GPL 2015 Summer"]),
    (2015, "TCL", "Winter", 0, ["TCL 2015 Winter"]),
    (2015, "TCL", "Summer", 0, ["TCL 2015 Summer"]),
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
    for job in JOBS:
        year, lg, split, po, names = job[:5]
        pver = job[5] if len(job) > 5 else ""
        if yrs and year not in yrs:
            continue
        # split 是中文或空字串時（如 WLDs 的「入圍賽」）去符號後會變空 → 同年同聯賽的兩個賽事撞 key
        # → 退而用賽事名當識別（WLDs_2013_IWCT2013）
        key = f"{lg}_{year}_{re.sub(r'[^A-Za-z0-9]+','',split) or re.sub(r'[^A-Za-z0-9]+','',names[0])}"
        print(f"\n[{year} {lg} {split}]", flush=True)
        done = False
        for nm in names:
            cfg = {"tour": nm, "league": lg, "split": split, "year": year, "playoffs": po,
                       "key": key, "patch": pver}
            try:
                t = MH.build(cfg, force=A.force)
            except Exception as e:
                print(f"    例外：{type(e).__name__} {str(e)[:80]}"); t = None
            if t and len(t) > 1:
                ok.append((year, lg, split, nm, len(t) - 1)); done = True; break
        if not done:
            miss.append(f"{year} {lg} {split}（試過：{names}）")
    # 清孤兒 key：JOBS 改過名（CBLOL_2015_Spring → CBLOL_2015_Split1）之後，舊 key 還留在
    # wikifill_{年}.json 裡 → 同一批比賽被併進去兩次，而且帶著補零前的錯版本號（15.90 之類）。
    # 只清「這次有跑到的年份」，且以 JOBS 目前的 key 集合為準。（2026-07-31）
    for y in sorted({j[0] for j in JOBS if not yrs or j[0] in yrs}):
        p = os.path.join(MH.CACHE, f"wikifill_{y}.json")
        if not os.path.exists(p):
            continue
        try:
            D = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        live = {f"{lg}_{yy}_{re.sub(r'[^A-Za-z0-9]+','',sp) or re.sub(r'[^A-Za-z0-9]+','',nms[0])}"
                for (yy, lg, sp, _po, nms, *_x) in JOBS if yy == y}   # key 規則要跟上面那行一致
        # ⚠ 只清「本檔（MatchHistoryGame）產的」key。fetch_wiki_pb.py 的成果存在同一個檔裡，
        #   不排除的話兩支腳本會互相把對方的資料當孤兒刪掉（2026-07-31 實測整批 PB 資料被清光）
        _mine = lambda v: "Picks and Bans" not in str(v.get("src", ""))
        drop = ([k for k, v in D.items() if k not in live and _mine(v)]
                + [k for k, v in D.items() if k in live and not v.get("rows")])
        if drop:
            for k in drop:
                D.pop(k, None)
            json.dump(D, open(p, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"\n[{y}] 清掉 {len(drop)} 個孤兒／空的 key：{drop}")

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
