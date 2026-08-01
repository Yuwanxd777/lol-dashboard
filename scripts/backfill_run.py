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

# wikifill 的 key 片段：只留英數與中日韓字。純去英數會讓「S7 卡托維茲」「S7 世界賽」
# 一起塌成 S7 而互相覆蓋（2026-08-01 抓 IEM 時發現）。
_kslug = lambda s: re.sub(r"[^A-Za-z0-9一-鿿぀-ヿ가-힯]+", "", str(s or ""))

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
    # 夏季季後賽的 Tournament 名是「LPL/2013 Season/Summer Playoffs」（不是 LPL 2013 Summer Playoffs）。
    # 之前查不到才改走 /Match History 嵌入表，但那張表的英雄是圖片、純文字化後只剩選手名
    # → 英雄欄全空（2026-07-31 使用者回報）。改回 MatchHistoryGame 純文字版，英雄與選手都齊全。
    (2013, "LPL", "Summer", 1, ["LPL/2013 Season/Summer Playoffs", "LPL 2013 Summer Playoffs"]),
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
    # ── 季後賽（Leaguepedia 各賽區都是獨立賽事；2013 的 LCS/LEC 當年叫 NA LCS／EU LCS）──
    (2013, "LEC", "Spring", 1, ["EU LCS 2013 Spring Playoffs"]),
    (2013, "LEC", "Summer", 1, ["EU LCS 2013 Summer Playoffs"]),
    (2013, "LCS", "Spring", 1, ["NA LCS 2013 Spring Playoffs"]),
    (2013, "LCS", "Summer", 1, ["NA LCS 2013 Summer Playoffs"]),
    (2013, "LPL", "Spring", 1, ["LPL/2013 Season/Spring Playoffs", "LPL 2013 Spring Playoffs"]),
    (2014, "LEC", "Spring", 1, ["EU LCS 2014 Spring Playoffs"]),
    (2014, "LEC", "Summer", 1, ["EU LCS 2014 Summer Playoffs"]),
    (2014, "LCS", "Spring", 1, ["NA LCS 2014 Spring Playoffs"]),
    (2014, "LCS", "Summer", 1, ["NA LCS 2014 Summer Playoffs"]),
    (2014, "LPL", "Spring", 1, ["LPL 2014 Spring Playoffs"]),
    (2014, "LPL", "Summer", 1, ["LPL 2014 Summer Playoffs"]),
    (2015, "LPL", "Spring", 1, ["LPL 2015 Spring Playoffs"]),
    (2015, "LPL", "Summer", 1, ["LPL 2015 Summer Playoffs"]),
    (2015, "CBLOL", "Split 1", 1, ["CBLOL 2015 Split 1 Playoffs"]),
    (2015, "CBLOL", "Split 2", 1, ["CBLOL 2015 Split 2 Playoffs"]),
    (2015, "TCL", "Winter", 1, ["TCL 2015 Winter Playoffs"]),
    (2015, "TCL", "Summer", 1, ["TCL 2015 Summer Playoffs"]),
    # ── 2016（LPL 只有夏季，補春季）──
    (2016, "LPL", "Spring", 0, ["LPL 2016 Spring"]),
    # ── 2026-07-31 逐案查證後補的缺口 ──
    # 判定方式：拿 csv_cache/lpstats（ScoreboardPlayers）的場次比對 data_{年}.js，
    # **隊名要模糊比對**——直接比會被改名/前後綴誤判成缺（Anarchy↔Rebels Anarchy、
    # KOO Tigers↔ROX Tigers、SBENU Sonicboom↔SBENU Korea），初估「缺 500 場」其實
    # 多半是假象。以下是隊名 0% 對得上、確認整段沒有的：
    # ── IEM（使用者定案 2026-08-01）──
    # 從 2013 的 Katowice 站開始一路抓到最後一站（S11 世界賽，2017-02）；Leaguepedia 之後
    # 就沒有 LoL 的 IEM 了。賽段寫「S{屆} {站名}」，站名用台灣慣用譯名；World Championship
    # 不寫地名、只寫「S{屆} 世界賽」。
    # S11 Challenger（2016-10 法國，22 局）不抓：Leaguepedia 標 IsQualifier=1，性質是
    # IEM Oakland 的資格賽，比照使用者先前定案的「Qualifiers 不抓」。
    # 年份＝比賽實際發生的年份（backfill 依此寫進 wikifill_{年}.json，跨年的站要放對）。
    (2013, "IEM", "S7 卡托維茲", 0, ["IEM Season 7 Katowice"]),
    (2013, "IEM", "S7 世界賽",   0, ["IEM Season 7 World Championship"]),
    (2013, "IEM", "S8 上海",     0, ["IEM Season 8 Shanghai"]),
    (2013, "IEM", "S8 科隆業餘", 0, ["IEM Season 8 Cologne Amateur"]),
    (2013, "IEM", "S8 新加坡",   0, ["IEM Season 8 Singapore"]),
    (2014, "IEM", "S8 聖保羅",   0, ["IEM Season 8 Sao Paulo"]),
    (2014, "IEM", "S8 世界賽",   0, ["IEM Season 8 World Championship"]),
    (2014, "IEM", "S9 深圳",     0, ["IEM Season 9 Shenzhen"]),
    (2014, "IEM", "S9 聖荷西",   0, ["IEM Season 9 San Jose"]),
    (2014, "IEM", "S9 科隆",     0, ["IEM Season 9 Cologne"]),
    (2015, "IEM", "S9 台北",     0, ["IEM Season 9 Taipei"]),
    (2015, "IEM", "S9 世界賽",   0, ["IEM Season 9 World Championship"]),
    # ⚠ 下面四站的年份**故意不等於比賽日期的年份**：OE 把 IEM 按「賽季年」歸檔（S10 橫跨
    # 2015-11~2016-03 全放 data_2016、S11 橫跨 2016-10~2017-02 全放 data_2017）。這裡若照
    # 日期年放到 2015／2016，wiki 版與 OE 版就落在不同檔案，merge_wiki 只在同一檔內比對、
    # 去重抓不到，整批變成重複收錄（2026-08-01 實測 data_2015 與 data_2016 各有一份聖荷西）。
    (2016, "IEM", "S10 聖荷西",  0, ["IEM Season 10 San Jose"]),      # 實際 2015-11
    (2016, "IEM", "S10 科隆",    0, ["IEM Season 10 Cologne"]),       # 實際 2015-12
    (2016, "IEM", "S10 世界賽",  0, ["IEM Season 10 World Championship"]),
    (2017, "IEM", "S11 奧克蘭",  0, ["IEM Season 11 Oakland"]),       # 實際 2016-11
    (2017, "IEM", "S11 京畿",    0, ["IEM Season 11 Gyeonggi"]),      # 實際 2016-12
    (2017, "IEM", "S11 世界賽",  0, ["IEM Season 11 World Championship"]),
    (2015, "LCO", "Split 1", 0, ["OPL 2015 Split 1"]),           # LCO 2015 只有夏季
    (2015, "LCO", "Split 2", 0, ["OPL 2015 Split 2"]),           # 夏季有一部分，補齊
    (2015, "LJL", "Spring", 0, ["LJL 2015 Season 1"]),           # LJL 2015 整年沒有
    (2015, "LJL", "Summer", 0, ["LJL 2015 Season 2"]),
    # 國際外卡賽＝世界賽入圍賽，併進 WLDs 用 split 標（使用者定案 2026-07-31）
    (2016, "WLDs", "入圍賽", 0, ["IWCQ 2016"]),
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
        emb = job[6] if len(job) > 6 else ""
        if yrs and year not in yrs:
            continue
        # split 是中文或空字串時（如 WLDs 的「入圍賽」）去符號後會變空 → 同年同聯賽的兩個賽事撞 key
        # → 退而用賽事名當識別（WLDs_2013_IWCT2013）。
        # 中日韓字要保留（2026-08-01 修）：原本只留 [A-Za-z0-9]，IEM 的「S7 卡托維茲」與
        # 「S7 世界賽」雙雙變成 S7，同年五個站被壓成兩個 key、資料互相覆蓋。
        key = (f"{lg}_{year}_{_kslug(split) or _kslug(names[0])}"
               + ("_PO" if po else ""))   # 季後賽是獨立賽事，key 不加後綴會跟同賽段的例行賽撞
        print(f"\n[{year} {lg} {split}]", flush=True)
        done = False
        for nm in names:
            cfg = {"tour": nm, "league": lg, "split": split, "year": year, "playoffs": po,
                       "key": key, "patch": pver, "embed": emb}
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
        live = {f"{lg}_{yy}_{_kslug(sp) or _kslug(nms[0])}"
                + ("_PO" if _po else "")
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
