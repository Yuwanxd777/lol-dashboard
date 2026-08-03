# -*- coding: utf-8 -*-
"""把比賽BP 偵測到的缺局，從 Leaguepedia 的 Picks and Bans 頁補回來。

**缺局怎麼來的**：系列賽的比分推得出應有幾局（BO5 打到 2-2 就一定有第 5 局），
但資料庫裡少了那一局。全庫 43051 場中有 57 場這種（0.13%），逐年見 --list。

**補什麼、不補什麼**（沿用 2026-08-02 的定案：不造假選手資料）：
  PB 頁只有隊伍／勝負／版本／完整 BP 順序，**沒有選手、KDA、路線** → 補出來的局
  只有隊伍列，不產生五名選手列，那局不計入任何選手／路線統計。

**做法**：
  1. 缺局清單（--miss 指定 JSON）逐筆取 (年,聯賽,賽段) → wiki_links.js 查 OverviewPage
  2. pb_list() 取該賽事逐局（頁面順序），依相鄰同兩隊併成系列
  3. Cargo 的 MatchSchedule 補日期（PB 頁沒有日期欄），用「兩隊＋比分」配對，配不到就不用
  4. 命中的系列**整串**丟給 fetch_wiki_mh.to_csv 產出隊伍列 → merge_wiki 會把我們已有的局
     依十隻英雄去重，只留真正缺的那些（所以這裡不必自己算是第幾局）
  5. 結果寫進 wikifill_{年}.json，走既有的 merge_wiki 併入路徑，不新增合併來源

⚠**只支援新版 PB 版型**（約 2018 起，一張 pbh-cn 大表）。2017 以前是「每局一張
   wikitable pb 小表」，pb_list 會回 0 局 → 那些賽事會被列為「來源版型不支援」。

用法：
  python scripts\\fill_missing_games.py --miss 缺局清單.json          # 實際補
  python scripts\\fill_missing_games.py --miss 缺局清單.json --dry    # 只看能補幾局
"""
import argparse, io, json, os, re, sys

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
CACHE = os.path.join(ROOT, "csv_cache")

import fetch_wiki_mh as MH
import fetch_side_sel as SS

nk = lambda s: re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def same(a, b):
    """隊名鬆比對：PB 用全名／logo alt（Team WE），我們用縮寫（WE）→ 互相包含即可"""
    a, b = nk(a), nk(b)
    return bool(a) and bool(b) and (a in b or b in a)


def wiki_links():
    p = os.path.join(ROOT, "wiki_links.js")
    return json.loads(io.open(p, encoding="utf-8").read().split("=", 1)[1].rstrip().rstrip(";"))


def series_of(rows):
    """PB 逐局清單 → 依「相鄰同兩隊」併成系列"""
    out = []
    for r in rows:
        if out and out[-1]["t1"] == r["t1"] and out[-1]["t2"] == r["t2"] and out[-1]["score"] != r["score"]:
            out[-1]["games"].append(r)
        else:
            out.append({"t1": r["t1"], "t2": r["t2"], "score": r["score"], "games": [r]})
    # 系列的比分＝該串裡「數字總和最大」的那筆（PB 是新→舊，最後一局才是最終比分）
    for s in out:
        best, bn = s["score"], -1
        for g in s["games"]:
            m = re.match(r"^(\d+)\s*-\s*(\d+)$", g["score"] or "")
            if m and int(m.group(1)) + int(m.group(2)) > bn:
                bn = int(m.group(1)) + int(m.group(2)); best = g["score"]
        s["score"] = best
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--miss", required=True, help="缺局清單 JSON（misslist）")
    ap.add_argument("--dry", action="store_true", help="只評估、不寫檔")
    A = ap.parse_args()

    miss = json.load(io.open(A.miss, encoding="utf-8"))
    W = wiki_links()
    groups = {}
    for r in miss:
        groups.setdefault((r["year"], r["league"], r["split"]), []).append(r)

    stat = {"補到": 0, "來源沒有": 0, "版型不支援": 0, "查無頁名": 0, "日期配不到": 0}
    per_year = {}
    for (y, lg, sp), rows in sorted(groups.items()):
        ov = (W.get(str(y), {}).get(lg, {}) or {}).get(sp)
        need = sum(len(r["miss"]) for r in rows)
        if not ov:
            stat["查無頁名"] += need; print(f"  ✗ {y} {lg} {sp}：wiki_links 查不到頁名"); continue
        pbl = MH.pb_list(ov)
        if not pbl:
            stat["版型不支援"] += need; print(f"  – {y} {lg} {sp}（{ov}）：PB 頁是舊版型或不存在 → 跳過 {need} 場"); continue
        sers = series_of(pbl)
        sc = SS.sched(ov)
        # 系列 ↔ 賽程：兩隊＋比分配對（頁面順序在季後賽不等於時間順序，不能用位置對齊）
        used, pair = set(), {}
        for i, s in enumerate(sers):
            for j, (d0, a0, b0, sco) in enumerate(sc):
                if j in used or sco != s["score"]:
                    continue
                if (same(s["t1"], a0) and same(s["t2"], b0)) or (same(s["t1"], b0) and same(s["t2"], a0)):
                    used.add(j); pair[i] = j; break
        games, hit = [], 0
        for r in rows:                              # 我們缺的每一個系列
            # 兩隊都要對上；日期容許 ±1 天並取最接近的——我們的日期來自 OE、wiki 用 UTC，
            # 跨時區的場次常常差一天（一開始要求完全相同，34 場配不到）。
            def _dd(x):
                try:
                    from datetime import date as _dt
                    a = _dt.fromisoformat(x); b = _dt.fromisoformat(r["date"])
                    return abs((a - b).days)
                except Exception:
                    return 99
            tms = r.get("teamsF") or r["teams"]      # 優先用隊伍全名（縮寫對不上 Leaguepedia 全名）
            cand = [i for i in pair
                    if _dd(sc[pair[i]][0]) <= 1
                    and all(any(same(t, sc[pair[i]][k]) for k in (1, 2)) for t in tms)]
            if not cand:
                stat["日期配不到"] += len(r["miss"]); continue
            cand.sort(key=lambda i: _dd(sc[pair[i]][0]))
            # 日期一律用**我們自己那個系列的日期**，不是賽程的（wiki 是 UTC，常差一天）。
            # 用賽程日期的話補進來的局會落在隔天 → 被切成另一個系列，兩邊都顯得缺局，
            # 反而讓缺局總數變多（實測 57 → 64）。
            s = sers[cand[0]]; d = r["date"]
            hit += len(r["miss"])
            for gi, g in enumerate(reversed(s["games"])):   # PB 是新→舊 → 反轉成時間正序
                games.append({"Date": f"{d} {8+gi:02d}:00:00", "Blue": g["t1"], "Red": g["t2"],
                              "Winner": g["win"], "P": g["patch"],
                              "Picks": ",".join(g["t1p"]), "Picks2": ",".join(g["t2p"]),
                              "Bans": ",".join(g["t1b"]), "Bans2": ",".join(g["t2b"]),
                              "Blue Roster": "", "Red Roster": "", "Len": "", "_pbonly": True})
        stat["補到"] += hit
        per_year[y] = per_year.get(y, 0) + hit
        print(f"  ✓ {y} {lg} {sp}：PB {len(pbl)} 局／{len(sers)} 系列 → 命中 {hit} 場缺局、送出 {len(games)} 局待去重")
        if games and not A.dry:
            # pb_nofill：這裡送進去的就是我們自己從 PB 頁挑好的局，to_csv 不可以再自行補齊
            cfg = {"tour": ov, "league": lg, "split": sp, "year": y, "playoffs": 0, "pb_nofill": True,
                   "key": f"PBFIX_{y}_{lg}_{re.sub(r'[^A-Za-z0-9一-鿿]+','',sp) or 'x'}"}
            hdr, rws = MH.to_csv(games, cfg)
            import csv as _csv
            buf = io.StringIO(); w = _csv.writer(buf, lineterminator="\n")
            w.writerow(hdr); w.writerows(rws)
            import fetch_data
            table = fetch_data.process(buf.getvalue(), y)
            p = os.path.join(CACHE, f"wikifill_{y}.json")
            D = json.load(io.open(p, encoding="utf-8")) if os.path.exists(p) else {}
            D[cfg["key"]] = {"header": table[0], "rows": table[1:], "games": len(games),
                             "src": "leaguepedia Picks and Bans（補缺局）", "tour": ov,
                             "league": lg, "split": sp}
            json.dump(D, io.open(p, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"      → wikifill_{y}.json［{cfg['key']}］{len(table)-1} 列")

    print("\n" + "─" * 56)
    for k, v in stat.items():
        print(f"  {k}：{v} 場")
    print("  逐年補到：", dict(sorted(per_year.items())))
    print("（實際併入以 merge_wiki 去重後為準，跑 fetch_data.py 再重算缺局）")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"fill_missing_games：執行失敗（{type(e).__name__}: {e}）")
    sys.exit(0)
