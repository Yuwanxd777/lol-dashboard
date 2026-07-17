# -*- coding: utf-8 -*-
"""
從 Leaguepedia(lol.fandom.com)Cargo API 抓 2014–2026 英雄聯盟賽事結構：
  1) Teams        → 戰隊全名 / 縮寫(Short) / 賽區 / 是否解散  → 修正縮寫碰撞(同縮寫不同隊)
  2) Tournaments  → 各賽事的 聯賽/賽區/年份/分級(TournamentLevel)/是否資格賽
  3) 參賽隊(Standings) → 每個賽事有哪些隊參加(隊名 → 再對回 Teams 拿縮寫)

輸出 leaguepedia.js = window.LOL_LEAGUEPEDIA = { teams:[...], tournaments:{year:[...]}, rosters:{tournament:[team...]} }
Cargo API 有 rate limit → 每次查詢間隔 DELAY 秒、分頁 500 筆、結果快取(csv_cache/lpedia/)可續跑。

用法：
  python scripts/fetch_leaguepedia.py --teams          # 只抓戰隊縮寫表
  python scripts/fetch_leaguepedia.py --tournaments    # 只抓賽事清單
  python scripts/fetch_leaguepedia.py                  # 全部(teams + tournaments + rosters)
  python scripts/fetch_leaguepedia.py --year 2023      # 單一年份(rosters)
"""
import os, sys, json, time, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, "csv_cache", "lpedia"); os.makedirs(CACHE, exist_ok=True)
OUT = os.path.join(ROOT, "leaguepedia.js")
API = "https://lol.fandom.com/api.php"
DELAY = 12            # rate limit：查詢間隔（Leaguepedia Cargo 限制嚴，拉長避免整段被封）
UA = {"User-Agent": "Mozilla/5.0 (dashboard research; contact via github)"}
YEARS = list(range(2014, 2027))


def cargo(tables, fields, where="", order_by="", limit=500, offset=0, join_on="", group_by=""):
    """單次 Cargo 查詢（含 rate-limit 重試）"""
    p = {"action": "cargoquery", "format": "json", "tables": tables, "fields": fields,
         "limit": str(limit), "offset": str(offset)}
    if where: p["where"] = where
    if order_by: p["order_by"] = order_by
    if join_on: p["join_on"] = join_on
    if group_by: p["group_by"] = group_by
    url = API + "?" + urllib.parse.urlencode(p)
    for attempt in range(10):
        try:
            r = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read())
        except Exception as e:
            time.sleep(30 * (attempt + 1)); continue
        if isinstance(r, dict) and r.get("error"):
            info = r["error"].get("info", "")
            if "rate limit" in info.lower():
                time.sleep(45 * (attempt + 1)); continue   # 指數退避，最長約 7.5 分
            raise RuntimeError(info)
        return [x["title"] for x in r.get("cargoquery", [])]
    raise RuntimeError("rate limit：重試多次仍失敗")


def paged(tables, fields, where="", order_by="", **kw):
    """自動分頁抓全部"""
    out, off = [], 0
    while True:
        rows = cargo(tables, fields, where=where, order_by=order_by, offset=off, **kw)
        out += rows
        if len(rows) < 500:
            break
        off += 500; time.sleep(DELAY)
    return out


def fetch_teams():
    cf = os.path.join(CACHE, "teams.json")
    if os.path.exists(cf):
        return json.load(open(cf, encoding="utf-8"))
    print("抓 Teams（全名/縮寫/賽區）…", flush=True)
    rows = paged("Teams", "Name,Short,Region,Location,IsDisbanded", order_by="Name")
    json.dump(rows, open(cf, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"  ✓ {len(rows)} 隊", flush=True)
    return rows


def fetch_tournaments():
    cf = os.path.join(CACHE, "tournaments.json")
    if os.path.exists(cf):
        return json.load(open(cf, encoding="utf-8"))
    out = {}
    for y in YEARS:
        print(f"抓 Tournaments {y}…", end=" ", flush=True)
        rows = paged("Tournaments",
                     "Name,OverviewPage,League,Region,Year,TournamentLevel,IsQualifier,IsPlayoffs,DateStart,Split",
                     where=f'Tournaments.Year="{y}"', order_by="DateStart")
        out[str(y)] = rows
        print(f"{len(rows)} 個", flush=True)
        time.sleep(DELAY)
    json.dump(out, open(cf, "w", encoding="utf-8"), ensure_ascii=False)
    return out


def fetch_rosters(tournaments):
    """每個賽事的參賽隊：Standings 表 join Tournaments，依年份整表分頁抓（每年幾頁，非每賽事一查詢）。
    回傳 {OverviewPage: [Team...]}。已完成的年份快取續跑。"""
    cf = os.path.join(CACHE, "rosters.json")
    got = json.load(open(cf, encoding="utf-8")) if os.path.exists(cf) else {}
    done_years = json.load(open(os.path.join(CACHE, "rosters_years.json"), encoding="utf-8")) \
        if os.path.exists(os.path.join(CACHE, "rosters_years.json")) else []
    for y in YEARS:
        if str(y) in done_years:
            continue
        print(f"抓 Rosters {y}（Standings join）…", end=" ", flush=True)
        rows = paged("Standings=S,Tournaments=T",
                     "S.OverviewPage=OverviewPage,S.Team=Team",
                     where=f'T.Year="{y}"', join_on="S.OverviewPage=T.OverviewPage",
                     order_by="S.OverviewPage")
        cnt = 0
        for r in rows:
            op, tm = r.get("OverviewPage"), r.get("Team")
            if op and tm:
                got.setdefault(op, [])
                if tm not in got[op]:
                    got[op].append(tm); cnt += 1
        done_years.append(str(y))
        json.dump(got, open(cf, "w", encoding="utf-8"), ensure_ascii=False)
        json.dump(done_years, open(os.path.join(CACHE, "rosters_years.json"), "w", encoding="utf-8"))
        print(f"{cnt} 筆名單", flush=True)
        time.sleep(DELAY)
    return got


def fetch_tr_rosters(rosters):
    """補抓參賽隊：TournamentRosters 表（每隊每賽事一列）join Tournaments 依年份分頁。
    Standings 只涵蓋積分賽制；升降賽/資格賽多為淘汰賽制、沒有 Standings 條目 → 用這張表補。
    合併進同一份 rosters.json（build_league_struct.py 直接受益）。進度檔 tr_years.json 可續跑。"""
    cf = os.path.join(CACHE, "rosters.json")
    done_p = os.path.join(CACHE, "tr_years.json")
    done_years = json.load(open(done_p, encoding="utf-8")) if os.path.exists(done_p) else []
    for y in YEARS:
        if str(y) in done_years:
            continue
        print(f"補抓 Rosters {y}（TournamentRosters join）…", end=" ", flush=True)
        rows = paged("TournamentRosters=TR,Tournaments=T",
                     "TR.OverviewPage=OverviewPage,TR.Team=Team",
                     where=f'T.Year="{y}"', join_on="TR.OverviewPage=T.OverviewPage",
                     order_by="TR.OverviewPage")
        cnt = 0
        for r in rows:
            op, tm = r.get("OverviewPage"), r.get("Team")
            if op and tm:
                rosters.setdefault(op, [])
                if tm not in rosters[op]:
                    rosters[op].append(tm); cnt += 1
        done_years.append(str(y))
        json.dump(rosters, open(cf, "w", encoding="utf-8"), ensure_ascii=False)
        json.dump(done_years, open(done_p, "w", encoding="utf-8"))
        print(f"{cnt} 筆新增", flush=True)
        time.sleep(DELAY)
    return rosters


def build(teams, tournaments, rosters):
    data = {"teams": teams, "tournaments": tournaments, "rosters": rosters}
    open(OUT, "w", encoding="utf-8").write("window.LOL_LEAGUEPEDIA=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";")
    print(f"\n寫出 {os.path.basename(OUT)}：{len(teams)} 隊、{sum(len(v) for v in tournaments.values())} 賽事、{len(rosters)} 賽事名單")


def main():
    only_teams = "--teams" in sys.argv
    only_tours = "--tournaments" in sys.argv
    if "--nowait" not in sys.argv:
        print("等待 rate limit 冷卻 90 秒…", flush=True); time.sleep(90)
    teams = fetch_teams()
    if only_teams:
        build(teams, {}, {}); return
    tours = fetch_tournaments()
    if only_tours:
        build(teams, tours, {}); return
    rosters = fetch_rosters(tours)
    rosters = fetch_tr_rosters(rosters)
    build(teams, tours, rosters)


if __name__ == "__main__":
    main()
