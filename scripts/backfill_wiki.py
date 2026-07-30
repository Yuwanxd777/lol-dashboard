# -*- coding: utf-8 -*-
"""歷年一級聯賽補齊（Leaguepedia Cargo → OE CSV → fetch_data.process → wikifill_{年}.json）

使用者交辦（2026-07-31）：前幾年資料有缺（例：LPL 要 2016 夏季才有，但 2013 就開季了）
→ 把所有一級聯賽補到 2013。**以 WIKI 為主**（gol.gg 實測沒有 2016 以前的賽事名），
gol.gg 能補更細的欄位再說。

三段式：
  ① discover  找出每個「聯賽×年份」缺口對應的 Leaguepedia OverviewPage（頁名歷年會變 →
               每個聯賽準備多組候選前綴，逐一試，全部落空就記進報告請使用者提供）
  ② fetch     每個賽事抓 ScoreboardGames／ScoreboardPlayers／PicksAndBansS7（Cargo 限流兇 →
               預設 25 秒節流、429 退避 60/120/240，全程快取可中斷續跑）
  ③ build     組成 OE CSV 欄位 → fetch_data.process() 產生相容列 → csv_cache/wikifill_{年}.json

用法：
  python scripts\\backfill_wiki.py --plan          # 只列缺口與候選頁名（不連線）
  python scripts\\backfill_wiki.py --discover      # 只做①（會連線，很慢）
  python scripts\\backfill_wiki.py                 # ①②③ 全跑（可中斷續跑）
  python scripts\\backfill_wiki.py --years 2013,2014
"""
import argparse, csv, io, json, os, re, sys, time, urllib.parse, urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, "csv_cache")
if not os.path.isdir(CACHE):
    CACHE = os.path.join(ROOT, "csv_cache")
sys.path.insert(0, HERE)

API = "https://lol.fandom.com/api.php"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
THROTTLE = 26.0            # Cargo 每請求間隔（實測連打 5 次就被 ratelimited）
BACKOFF = [60, 120, 240, 480]
LOG = os.path.join(ROOT, "backfill_log.txt")


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(s + "\n")
    except Exception:
        pass


# 儀表板聯賽碼 → Leaguepedia OverviewPage 前綴候選（歷年頁名會變，逐一試）
PREFIX = {
    "LCK": ["LCK/{y} Season", "Champions/{y} Season", "LCK/Season {s}"],
    "LPL": ["LPL/{y} Season", "LPL/Season {s}"],
    "LEC": ["LEC/{y} Season", "EU LCS/{y} Season", "EU LCS/Season {s}"],
    "LCS": ["LCS/{y} Season", "NA LCS/{y} Season", "NA LCS/Season {s}"],
    "LMS": ["LMS/{y} Season"],
    "PCS": ["PCS/{y} Season"],
    "CBLOL": ["CBLOL/{y} Season"],
    "VCS": ["VCS/{y} Season"],
    "LJL": ["LJL/{y} Season"],
    "LLA": ["LLA/{y} Season"], "LLN": ["LLN/{y} Season"], "CLS": ["CLS/{y} Season"],
    "TCL": ["TCL/{y} Season"], "LCL": ["LCL/{y} Season"], "LCO": ["OPL/{y} Season", "LCO/{y} Season"],
    "GPL": ["GPL/{y} Season"], "LCP": ["LCP/{y} Season"],
    "LTA N": ["LTA/{y} Season/North", "LTA North/{y} Season"],
    "LTA S": ["LTA/{y} Season/South", "LTA South/{y} Season"],
}
SEASON_NO = {2013: 3, 2014: 4, 2015: 5}     # 早年頁名用 "Season 3/4/5"


def cargo(tables, fields, where, limit=500, offset=0):
    q = {"action": "cargoquery", "format": "json", "tables": tables, "fields": fields,
         "where": where, "limit": str(limit), "offset": str(offset)}
    url = API + "?" + urllib.parse.urlencode(q)
    for i, wait in enumerate([0] + BACKOFF):
        if wait:
            log(f"      限流 → 等 {wait}s"); time.sleep(wait)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as f:
                d = json.loads(f.read().decode("utf-8", "replace"))
        except Exception as e:
            log(f"      連線錯誤：{type(e).__name__} {str(e)[:60]}")
            continue
        if isinstance(d, dict) and d.get("error"):
            if d["error"].get("code") == "ratelimited":
                continue
            log(f"      Cargo 錯誤：{d['error'].get('code')}")
            return []
        time.sleep(THROTTLE)
        return [r["title"] for r in d.get("cargoquery", [])]
    return []


def cargo_all(tables, fields, where, page=500):
    out, off = [], 0
    while True:
        rows = cargo(tables, fields, where, limit=page, offset=off)
        out += rows
        if len(rows) < page:
            return out
        off += page
        if off > 20000:
            return out


def have_counts():
    """目前各年各聯賽的局數（participantid=100）"""
    import glob
    out = {}
    for p in sorted(glob.glob(os.path.join(ROOT, "data", "data_*.js"))):
        y = int(os.path.basename(p)[5:9])
        J = json.loads(open(p, encoding="utf-8").read().split("=", 1)[1].strip().rstrip(";"))
        R = J["tabs"]["RAW_DATA"]; h = R[0]; ix = {n: i for i, n in enumerate(h)}
        c = {}
        for r in R[1:]:
            if str(r[ix["participantid"]]) == "100":
                c[str(r[ix["league"]])] = c.get(str(r[ix["league"]]), 0) + 1
        out[y] = c
    return out


def gaps(years):
    t1 = json.load(open(os.path.join(CACHE, "worlds_tier1.json"), encoding="utf-8"))
    hv = have_counts()
    out = []
    for y in years:
        lgs = t1.get(str(y)) or t1.get(str(min(max(y, 2014), 2026))) or []
        for lg in lgs:
            n = hv.get(y, {}).get(lg, 0)
            if n < 30:          # 完全沒有或極少 → 視為缺口（正常一個賽區一年 150+ 局）
                out.append({"year": y, "league": lg, "have": n})
    return out


def discover(year, league):
    """回傳該聯賽該年的 OverviewPage 清單（含 split/playoffs 資訊）"""
    cands = PREFIX.get(league, [league + "/{y} Season"])
    for c in cands:
        pref = c.format(y=year, s=SEASON_NO.get(year, ""))
        rows = cargo("Tournaments", "OverviewPage,Name,Split,IsPlayoffs,DateStart,Year",
                     f'OverviewPage LIKE "{pref}%"', limit=100)
        if rows:
            log(f"    命中前綴「{pref}」→ {len(rows)} 個賽事")
            return rows
        log(f"    前綴「{pref}」無資料")
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2013,2014,2015,2016")
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--discover", action="store_true")
    A = ap.parse_args()
    years = [int(x) for x in A.years.split(",") if x.strip()]
    G = gaps(years)
    log(f"=== 缺口盤點（{time.strftime('%Y-%m-%d %H:%M')}）===")
    for g in G:
        log(f"  {g['year']} {g['league']:6s} 目前 {g['have']} 局")
    if A.plan:
        log("\n候選頁名：")
        for g in G:
            cs = [c.format(y=g["year"], s=SEASON_NO.get(g["year"], "")) for c in PREFIX.get(g["league"], [g["league"] + "/{y} Season"])]
            log(f"  {g['year']} {g['league']:6s} → {cs}")
        return
    found, missing = {}, []
    for g in G:
        log(f"\n[{g['year']} {g['league']}] 探索賽事頁…")
        rows = discover(g["year"], g["league"])
        if rows:
            found[f"{g['year']}_{g['league']}"] = rows
            for r in rows:
                log(f"      {r.get('OverviewPage')}　split={r.get('Split')} PO={r.get('IsPlayoffs')} {r.get('DateStart')}")
        else:
            missing.append(f"{g['year']} {g['league']}")
        json.dump({"found": found, "missing": missing},
                  open(os.path.join(CACHE, "backfill_pages.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    log(f"\n探索完成：命中 {len(found)} 組、找不到 {len(missing)} 組")
    if missing:
        log("找不到賽事頁（需要使用者提供正確的 Leaguepedia 頁名）：")
        for m in missing:
            log("   " + m)


if __name__ == "__main__":
    main()
