# -*- coding: utf-8 -*-
"""每個「年 / 聯賽 / 賽段」對應的 Leaguepedia 頁 → wiki_links.js。

用途：圖鑑「賽事」樹點賽段標題可以直接跳到該年該季的 wiki（使用者要求 2026-08-01）。

怎麼對：Cargo 的 ScoreboardGames 每一局都帶 OverviewPage（就是 wiki 頁名），所以不必猜
頁名規則（早年完全不照現代規則：LCK 2013 是 Champions/2013 Season/Summer、LEC 2013 是
EU LCS/Season 3/Summer Season）。做法是把該年的 ScoreboardGames 全抓下來建索引，
再拿本地資料檔的每一局去查，同一賽段取**眾數**——少數局對不上（隊名寫法不同、
OE 收了 wiki 沒有的場次）不影響結果。

用法：python scripts\\fetch_wiki_links.py [--years 2013,2014] [--force]
      不加 --years 就跑 data/ 底下所有年份；--force 忽略 csv_cache 的快取重抓。
"""
import argparse, collections, io, json, os, re, sys, time, urllib.parse, urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, "csv_cache")
sys.path.insert(0, HERE)

FORM = "https://lol.fandom.com/wiki/Special:CargoExport"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
      "Accept-Language": "en-US,en;q=0.9", "Referer": FORM}
PAGE = 2000        # CargoExport 單次上限
# 前端的賽段正名（index.html：Opening＝春季、Closing＝夏季，LLA／CBLOL 用語統一成春夏）
SP_ALIAS = {"Opening": "春季", "Opening PO": "春季 PO", "Closing": "夏季", "Closing PO": "夏季 PO"}
# 世界賽資格賽的聯賽碼＝WQS＋區域中文名（與 index.html 的 LEAGUE_META.region 對齊）
WQS_REGION = {"LPL": "中國", "LCK": "韓國", "LEC": "歐洲", "LCS": "北美", "PCS": "太平洋",
              "VCS": "越南", "CBLOL": "巴西", "LLA": "拉丁美洲", "LJL": "日本"}
GAP = 1.5
_OP = None


def opener():
    """CargoExport 走一般頁面請求（action=cargoquery 對匿名限流極兇）；要先拿 cookie 否則 403"""
    global _OP
    if _OP is None:
        import http.cookiejar
        cj = http.cookiejar.CookieJar()
        _OP = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        try:
            _OP.open(urllib.request.Request(FORM, headers=UA), timeout=60).read()
            time.sleep(2)
        except Exception as e:
            print(f"   ⚠ 取 cookie 失敗（仍試著繼續）：{type(e).__name__}")
    return _OP


def cargo(fields, where, offset=0, limit=PAGE):
    p = {"tables": "ScoreboardGames", "fields": fields, "where": where,
         "limit": str(limit), "offset": str(offset), "order by": "DateTime_UTC",
         "format": "json"}
    url = FORM + "?" + urllib.parse.urlencode(p)
    raw = opener().open(urllib.request.Request(url, headers=UA), timeout=120).read()
    return json.loads(raw.decode("utf-8", "replace"))


def sb_of_year(year, force=False):
    """該年所有比賽的 (日期, 隊名) → OverviewPage；分頁抓完存快取"""
    p = os.path.join(CACHE, f"wiki_pages_{year}.json")
    if os.path.exists(p) and not force:
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # 從前一年 10 月起：跨年賽事的比賽會落在前一年（LCK 2013 冬季從 2012-11 開打、
    # IEM 一屆橫跨兩個年度），只抓當年會整段查不到頁名
    where = (f"DateTime_UTC >= '{year-1}-10-01' AND DateTime_UTC <= '{year}-12-31 23:59:59'")
    idx, off, n = {}, 0, 0
    while True:
        rows = cargo("DateTime_UTC,Team1,Team2,OverviewPage", where, off)
        if not rows:
            break
        for r in rows:
            pg = (r.get("OverviewPage") or "").strip()
            d = str(r.get("DateTime UTC") or "")[:10]
            if not pg or not d:
                continue
            for t in (r.get("Team1"), r.get("Team2")):
                t = (t or "").strip().lower()
                if t:
                    idx.setdefault(f"{d}|{t}", pg)
        n += len(rows)
        off += PAGE
        print(f"   {year}：已抓 {n} 局…", flush=True)
        if len(rows) < PAGE:
            break
        time.sleep(GAP)
    os.makedirs(CACHE, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False)
    return idx


def load_year(year):
    """讀 data/data_{年}.js → [(聯賽, 賽段, 日期, 藍隊, 紅隊)]"""
    p = os.path.join(ROOT, "data", f"data_{year}.js")
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        s = f.read()
    i = s.find("{")
    d = json.loads(s[i:s.rstrip().rstrip(";").rfind("}") + 1])
    t = d["tabs"]["RAW_DATA"]
    h = t[0]
    iL, iS, iD = h.index("league"), h.index("split"), h.index("date")
    iB, iR = h.index("blue_teamname"), h.index("red_teamname")
    out = []
    for r in t[1:]:
        out.append((r[iL], r[iS] or "", str(r[iD])[:10], r[iB] or "", r[iR] or ""))
    return out


def fallback_pages():
    """抓取管線裡登記過的 wiki 頁名，當 ScoreboardGames 查不到時的備援。

    2013 那批小賽區（GPL／CBLOL／LCO／LCL／TCL／LLA）Leaguepedia 只有 Picks and Bans
    頁、沒有逐局 scoreboard，ScoreboardGames 自然查不到；但頁名本來就寫在
    fetch_wiki_pb.JOBS 與 fetch_events_extra.EVENTS 裡，直接拿來用。
    """
    out = {}
    try:
        import fetch_wiki_pb as PB
        for j in PB.JOBS:
            y, lg, sp = j[0], j[1], j[2]
            main = j[5] if len(j) > 5 else ""
            if not main:
                continue
            out.setdefault((y, lg, sp), main)
            opt = j[6] if len(j) > 6 else None
            if isinstance(opt, dict):          # sections＝一頁拆成多個賽段
                for v in (opt.get("sections") or {}).values():
                    out.setdefault((y, lg, v), main)
    except Exception as e:
        print(f"   ⚠ 讀 fetch_wiki_pb.JOBS 失敗：{type(e).__name__} {e}")
    try:
        import fetch_events_extra as EX
        for y, m in (getattr(EX, "EVENTS", {}) or {}).items():
            for lg, cfg in m.items():
                if cfg.get("page"):
                    out.setdefault((y, lg, ""), cfg["page"])
                for s in (cfg.get("splits") or []):
                    if s.get("sp") and s.get("page"):
                        out.setdefault((y, lg, s["sp"]), s["page"])
    except Exception as e:
        print(f"   ⚠ 讀 fetch_events_extra.EVENTS 失敗：{type(e).__name__} {e}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    years = ([int(x) for x in a.years.split(",") if x.strip().isdigit()] or
             sorted(int(m.group(1)) for m in
                    (re.match(r"data_(\d{4})\.js$", f) for f in os.listdir(os.path.join(ROOT, "data")))
                    if m))
    out, miss = {}, []
    FB = fallback_pages()
    print(f"管線登記的頁名 {len(FB)} 筆（ScoreboardGames 查不到時的備援）")
    for y in years:
        rows = load_year(y)
        if not rows:
            continue
        print(f"\n[{y}] 本地 {len(rows)} 列")
        idx = sb_of_year(y, a.force)
        print(f"   wiki 索引 {len(idx)} 筆")
        vote = collections.defaultdict(collections.Counter)
        for lg, sp, d, bt, rt in rows:
            for t in (bt, rt):
                pg = idx.get(f"{d}|{(t or '').strip().lower()}")
                if pg:
                    vote[(lg, sp)][pg] += 1
                    # 同年多屆盃賽（2026 兩屆 KeSPA）各屆有各自的頁，但 split 都是空的 →
                    # 眾數只會留下其中一屆。另外記「@比賽年」鍵，前端分屆標籤用它連各屆的頁。
                    vote[(lg, "@" + d[:4])][pg] += 1
                    # 世界賽／MSI 的入圍賽在資料裡沒有獨立賽段（split 是空的），賽事樹是依
                    # 日期把它分出來的 → 靠 wiki 頁名認出來，另外記一份給「入圍賽」那段用
                    if re.search(r"Play[- ]?In", pg, re.I):
                        vote[(lg, "入圍賽")][pg] += 1
                    # 世界賽卡誤含的各賽區資格賽（2022-2025）：資料檔裡 league 還是 WLDs，
                    # index.html 載入時才依日期改標成 WQS{區}（見 _WQS_CUT）。抓取端看不到
                    # 那個碼，改用 wiki 頁名認：各區資格賽的頁是「{聯賽}/…Regional Finals」。
                    if lg == "WLDs" and re.search(r"Regional Finals", pg, re.I):
                        rgn = WQS_REGION.get(pg.split("/")[0].strip())
                        if rgn:
                            vote[("WQS" + rgn, "")][pg] += 1
                    break
        ymap = {}
        for (lg, sp), c in sorted(vote.items()):
            pg, n = c.most_common(1)[0]
            tot = sum(c.values())
            ymap.setdefault(lg, {})[sp] = pg
            # index.html 載入時會把 LLA／CBLOL 的 Opening／Closing 正名成春季／夏季
            #（見 index.html 的 _SP 對照），前端拿正名後的字來查 → 兩個名字都收
            if sp in SP_ALIAS:
                ymap[lg][SP_ALIAS[sp]] = pg
            flag = "" if n / tot >= .6 else f"   ⚠ 只有 {n}/{tot} 一致"
            print(f"   {lg:<8}{(sp or '(空)'):<14}→ {pg}{flag}")
        # 一局都對不上的（wiki 沒有逐局 scoreboard）→ 退回抓取管線登記的頁名
        seen = {(lg, sp) for lg, sp, *_ in rows}
        for lg, sp in sorted(seen - set(vote)):
            base = str(sp).replace(" PO", "")
            pg = FB.get((y, lg, sp)) or FB.get((y, lg, base))
            if pg:
                ymap.setdefault(lg, {})[sp] = pg
                print(f"   {lg:<8}{(sp or '(空)'):<14}→ {pg}   （管線登記）")
            else:
                miss.append(f"{y} {lg} {sp or '(空)'}")
        # 管線登記過、但今年一局都還沒打的（ENC 2026 十一月才開打）→ 也收進來。
        # 賽事樹會列出這種「尚無比賽資料」的卡片，一樣要點得進 wiki。
        for (fy, flg, fsp), fpg in FB.items():
            if fy == y and fpg:
                ymap.setdefault(flg, {}).setdefault(fsp, fpg)
        if ymap:
            out[str(y)] = ymap
    p = os.path.join(ROOT, "wiki_links.js")
    with open(p, "w", encoding="utf-8") as f:
        f.write("window.WIKI_LINKS=" + json.dumps(out, ensure_ascii=False, sort_keys=True) + ";\n")
    n = sum(len(v) for m in out.values() for v in m.values())
    print(f"\n→ wiki_links.js（{len(out)} 年、{n} 個賽段）")
    if miss:
        print(f"\n對不到 wiki 頁的賽段 {len(miss)} 個（多半是 wiki 沒收錄的補充賽事）：")
        for m in miss[:40]:
            print("   " + m)


if __name__ == "__main__":
    main()
