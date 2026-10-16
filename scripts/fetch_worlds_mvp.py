# -*- coding: utf-8 -*-
"""歷屆世界賽「各場 MVP」（Leaguepedia 賽程表上每個系列的 MVP）→ csv_cache/worlds_mvp.json。

給「預測」分頁（水晶球）的「決賽 MVP 會是哪條路線」用（使用者 2026-10-16：只看歷屆 FMVP 才 7 筆、不準，
要連各場 MVP 一起看、兩者都列出）。

輸出 {年: {"series": [系列…], "games": [有逐局 MVP 的局…]}}。
來源＝Cargo `MatchSchedule.MVP`（系列）＋`MatchScheduleGame.MVP`（逐局）。世界賽**沒有逐局 MVP**（`MatchScheduleGame.MVP` 2024 整屆只有 1 局有填），
發的是**系列 MVP**（Player of the Match，一個系列一個）——就是 wiki 賽程表每場旁邊那個名字。
`N/A`＝那個系列沒發（入圍賽常見）。名字可能帶本名括號（`knight (Zhuo Ding)`），路線交給
build_predict_hist.py 用主資料的世界賽出場紀錄對。

歷屆資料不會再變 ⇒ 不掛進每日管線；要多加一屆時手動重跑（Cargo 對匿名限流兇，一屆一次請求、走既有節流）：
  python scripts/fetch_worlds_mvp.py              # 預設 2019～2025
  python scripts/fetch_worlds_mvp.py 2026         # 只補（或重抓）某幾屆，其餘照舊保留
"""
import io, json, os, sys, urllib.parse, urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "csv_cache", "worlds_mvp.json")
sys.path.insert(0, HERE)
import fetch_events_extra as F   # noqa: E402  共用 Cargo 的 cookie 與節流


def fetch_year(y):
    op = F._cargo_opener()
    q = {"tables": "MatchSchedule=M",
         "fields": "M.OverviewPage=ov,M.MatchId=mid,M.Team1=t1,M.Team2=t2,M.Winner=w,M.MVP=mvp,"
                   "M.DateTime_UTC=dt,M.Tab=tab,M.BestOf=bo,M.Team1Score=s1,M.Team2Score=s2",
         "where": f"M.OverviewPage LIKE '{y} Season World Championship%'",
         "order by": "M.DateTime_UTC", "limit": "500", "format": "json"}
    F._throttle()
    raw = op.open(urllib.request.Request(F.CARGO_FORM + "?" + urllib.parse.urlencode(q), headers=F.CARGO_UA),
                  timeout=90).read().decode("utf-8", "replace")
    F._mark()
    out = []
    for r in json.loads(raw):
        m = str(r.get("mvp") or "").strip()
        out.append({"ov": r.get("ov"), "tab": r.get("tab") or "", "dt": (r.get("dt") or "")[:16],
                    "t1": r.get("t1"), "t2": r.get("t2"), "w": r.get("w"), "bo": r.get("bo"),
                    "s": [r.get("s1"), r.get("s2")], "mvp": "" if m.upper() in ("", "N/A", "NA", "TBD") else m})
    return out


def fetch_games(y):
    """逐局 MVP（MatchScheduleGame.MVP）：2021／2022 世界賽發的是這種；其餘屆幾乎全空。"""
    op = F._cargo_opener()
    q = {"tables": "MatchScheduleGame=G,MatchSchedule=M", "join on": "G.MatchId=M.MatchId",
         "fields": "G.OverviewPage=ov,G.N_GameInMatch=n,G.MVP=mvp,M.DateTime_UTC=dt,M.Tab=tab",
         "where": f"G.OverviewPage LIKE '{y} Season World Championship%'",
         "order by": "M.DateTime_UTC", "limit": "500", "format": "json"}
    F._throttle()
    raw = op.open(urllib.request.Request(F.CARGO_FORM + "?" + urllib.parse.urlencode(q), headers=F.CARGO_UA),
                  timeout=90).read().decode("utf-8", "replace")
    F._mark()
    out = []
    for r in json.loads(raw):
        m = str(r.get("mvp") or "").strip()
        if m.upper() in ("", "N/A", "NA", "TBD", "NONE", "MISSING"):
            continue
        out.append({"ov": r.get("ov"), "tab": r.get("tab") or "", "dt": (r.get("dt") or "")[:16], "n": r.get("n"), "mvp": m})
    return out


def main():
    years = [int(a) for a in sys.argv[1:]] or list(range(2019, 2026))
    D = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    for y in years:
        rows = fetch_year(y)
        n = sum(1 for r in rows if r["mvp"])
        if not rows:
            print(f"{y}：Cargo 回 0 個系列（保留舊資料，不覆寫）")
            continue
        games = fetch_games(y)
        D[str(y)] = {"series": rows, "games": games}
        print(f"{y}：{len(rows)} 個系列、{n} 個有系列 MVP；逐局 MVP {len(games)} 局")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(D, f, ensure_ascii=False, indent=0)
    print("→", OUT)


if __name__ == "__main__":
    main()
