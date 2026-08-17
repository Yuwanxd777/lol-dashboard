# -*- coding: utf-8 -*-
"""積分（solo queue）覆蓋全面檢視：比賽數據裡今年出場過的每一位選手，逐一核對本地積分資料有沒有抓到、抓得對不對。

只讀檔、不打任何 API、不改任何檔案。輸出分五類：
  ①沒帳號       ：soloq_accounts.json 一個帳號都沒有（積分頁會顯「缺積分帳號」）
  ②有帳號無牌位 ：帳號都查不到排名（改名／未定位／假 ID）→ 積分頁只剩「未定位」
  ③有帳號無逐場 ：soloq_match_index.js 沒這個人（沒 dpmPuuid 或 fetch_soloq_year 漏抓）→ 點不進去、無最近十場
  ④路線不符     ：逐場主路 ≠ 比賽數據位置（≥8 場）→ 很可能是張冠李戴的帳號
  ⑤帳號疑似停用 ：逐場最後一場 > N 天前、但選手最近仍在打職業（帳號改名／換號沒跟上）
另列「帳號檔有、今年比賽卻沒出場」的人（教練／退役／二隊，前端本來就不列，只供參考）。

用法：
  python scripts\\audit_soloq_coverage.py                # 全部（依最近出賽日排序，只列有問題的）
  python scripts\\audit_soloq_coverage.py --days 60      # 「最近仍在打」的門檻（預設 45 天）
  python scripts\\audit_soloq_coverage.py --league LCK LPL   # 只看這些賽事
  python scripts\\audit_soloq_coverage.py --json out.json    # 機器可讀（給補抓腳本吃）
"""
import argparse, io, json, os, re, sys, datetime
from collections import Counter, defaultdict

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from fetch_dpm_soloq_accounts import load_abbr, norm, TEAM_ALIAS, BLOCK_PLAYERS  # noqa: E402

POS = {1: "TOP", 2: "JUNGLE", 3: "MIDDLE", 4: "BOTTOM", 5: "UTILITY"}
ROLE_ALIAS = {"TOP": "TOP", "JUNGLE": "JUNGLE", "JG": "JUNGLE", "MID": "MIDDLE", "MIDDLE": "MIDDLE",
              "BOT": "BOTTOM", "BOTTOM": "BOTTOM", "ADC": "BOTTOM", "SUP": "UTILITY", "SUPPORT": "UTILITY", "UTILITY": "UTILITY"}


def load_js_json(path, var):
    s = open(path, encoding="utf-8", errors="replace").read()
    m = re.search(re.escape(var) + r"\s*=\s*(\{.*)", s, re.S)
    return json.loads(re.sub(r";\s*$", "", m.group(1)))


def roster(abbr):
    """比賽數據每位出場選手：隊縮寫(最後一隊)、位置(眾數)、場數、最後出賽日、賽事集合。"""
    J = load_js_json(os.path.join(ROOT, "data", "data_2026.js"), "window.LOL_DATA")
    raw = J["tabs"]["RAW_DATA"]; hdr = raw[0]; C = {h: i for i, h in enumerate(hdr)}
    bp, rp, pi = C["blue_playername"], C["red_playername"], C["participantid"]
    bt, rt, di, li = C["blue_teamname"], C["red_teamname"], C["date"], C["league"]
    out = {}
    for r in raw[1:]:
        try:
            pid = int(r[pi])
        except Exception:
            continue
        if not 1 <= pid <= 5:
            continue
        for pcol, tcol in ((bp, bt), (rp, rt)):
            nm = str(r[pcol] or "").strip() if pcol < len(r) else ""
            if not nm:
                continue
            full = str(r[tcol] or "").strip()
            ab = abbr.get(full.lower(), "") or re.sub(r"[^A-Za-z0-9]", "", full)[:5].upper()
            e = out.setdefault(nm, {"player": nm, "n": 0, "pos": Counter(), "last": "", "teams": Counter(), "leagues": Counter(), "team": ab})
            e["n"] += 1; e["pos"][POS[pid]] += 1; e["teams"][ab] += 1; e["leagues"][str(r[li])] += 1
            d = str(r[di])[:10]
            if d > e["last"]:
                e["last"] = d; e["team"] = ab
    for e in out.values():
        e["pos"] = e["pos"].most_common(1)[0][0]
        e["leagues"] = sorted(e["leagues"], key=lambda k: -e["leagues"][k])
        e["teams"] = sorted(e["teams"], key=lambda k: -e["teams"][k])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=45, help="「最近仍在打職業」門檻（天）")
    ap.add_argument("--stale", type=int, default=45, help="逐場最後一場超過幾天算疑似停用")
    ap.add_argument("--league", nargs="*", default=None)
    ap.add_argument("--json", default=None)
    ap.add_argument("--all", action="store_true", help="連沒問題的也列")
    a = ap.parse_args()

    abbr = load_abbr()
    R = roster(abbr)
    acc = json.load(open(os.path.join(HERE, "soloq_accounts.json"), encoding="utf-8"))
    SQ = load_js_json(os.path.join(ROOT, "soloq.js"), "window.SOLOQ_DATA")
    IDX = load_js_json(os.path.join(ROOT, "soloq_match_index.js"), "window.SOLOQ_MATCH_IDX")["players"]
    today = datetime.date.today()
    last_match_day = max(e["last"] for e in R.values())

    # 帳號 by 選手名（不分隊，隊碼兩邊可能差 GEN/GENG）
    acc_by = defaultdict(list)
    for e in acc:
        acc_by[norm(e.get("player"))].append(e)
    rank_by = defaultdict(list)
    for e in SQ.get("players", []):
        rank_by[norm(e.get("player"))].append(e)
    idx_by = defaultdict(list)
    for k, v in IDX.items():
        tm, _, pl = k.partition("|")
        idx_by[norm(pl)].append((tm, v))

    def team_eq(t1, t2):
        c = lambda t: TEAM_ALIAS.get(str(t or "").upper(), str(t or "").upper())
        return c(t1) == c(t2)

    rows = []
    for nm, e in R.items():
        if a.league and not any(l in a.league for l in e["leagues"]):
            continue
        k = norm(nm)
        if k in BLOCK_PLAYERS:
            continue
        accs = acc_by.get(k, [])
        accs_team = [x for x in accs if team_eq(x.get("team"), e["team"])] or accs
        ranks = [x for x in rank_by.get(k, []) if x.get("found") and x.get("tier")]
        idx = idx_by.get(k, [])
        idx_team = [v for tm, v in idx if team_eq(tm, e["team"])] or [v for tm, v in idx]
        recent = (today - datetime.date.fromisoformat(e["last"])).days <= a.days if e["last"] else False
        issues = []
        if not accs:
            issues.append("①沒帳號")
        else:
            if not accs_team or not any(team_eq(x.get("team"), e["team"]) for x in accs):
                issues.append(f"隊碼不符(帳號在 {sorted({x.get('team') for x in accs})})")
            if not ranks:
                issues.append("②有帳號無牌位")
            if not idx_team:
                issues.append("③有帳號無逐場")
            else:
                v = idx_team[0]
                role = ROLE_ALIAS.get(str(v.get("role") or "").upper(), v.get("role"))
                if role and v.get("n", 0) >= 8 and role != e["pos"]:
                    issues.append(f"④路線不符(逐場 {role} {v.get('n')}場 vs 比賽 {e['pos']})")
                lt = v.get("lt")
                if lt and recent:
                    dlast = datetime.date.fromtimestamp(lt / 1000)
                    if (today - dlast).days > a.stale:
                        issues.append(f"⑤帳號疑停用(逐場最後 {dlast.isoformat()})")
        row = {"player": nm, "team": e["team"], "pos": e["pos"], "n": e["n"], "last": e["last"], "leagues": e["leagues"][:3],
               "recent": recent, "accounts": len(accs), "ranked": len(ranks), "idx": bool(idx_team), "issues": issues,
               "riotIds": [x.get("riotId") for x in accs][:4]}
        rows.append(row)

    rows.sort(key=lambda r: (not r["recent"], r["last"]), reverse=False)
    rows.sort(key=lambda r: r["last"], reverse=True)
    prob = [r for r in rows if r["issues"]]
    print(f"比賽數據 2026 出場選手 {len(rows)} 位（最後比賽日 {last_match_day}）；有問題 {len(prob)} 位；"
          f"最近 {a.days} 天內仍出賽者 {sum(1 for r in rows if r['recent'])} 位、其中有問題 {sum(1 for r in prob if r['recent'])} 位")
    cnt = Counter()
    for r in prob:
        for i in r["issues"]:
            cnt[i[:1] if i[0] in "①②③④⑤" else "隊碼"] += 1
    print("  分類：" + "、".join(f"{k} {v}" for k, v in sorted(cnt.items())))
    print()
    print("── 最近仍在打職業、有問題的（優先處理）──")
    for r in prob:
        if not r["recent"]:
            continue
        print(f"  {r['last']}  {r['team']:<5} {r['player']:<14} {r['pos']:<8} {r['n']:>3}場  {'/'.join(r['leagues'])}  → {'；'.join(r['issues'])}"
              + (f"  [{'、'.join(str(x) for x in r['riotIds'])}]" if r['riotIds'] and any(i.startswith(('②','③','④','⑤')) for i in r['issues']) else ""))
    print()
    print(f"── 最近 {a.days} 天沒出賽、有問題的（多半是二隊／已離隊／短期替補）──")
    for r in prob:
        if r["recent"]:
            continue
        print(f"  {r['last']}  {r['team']:<5} {r['player']:<14} {r['pos']:<8} {r['n']:>3}場  {'/'.join(r['leagues'])}  → {'；'.join(r['issues'])}")
    if a.all:
        print()
        print("── 沒問題的 ──")
        for r in rows:
            if not r["issues"]:
                print(f"  {r['last']}  {r['team']:<5} {r['player']:<14} {r['pos']:<8} {r['n']:>3}場  帳號{r['accounts']} 牌位{r['ranked']} 逐場{'有' if r['idx'] else '無'}")
    # 帳號檔有、今年沒出場
    rk = {norm(n) for n in R}
    extra = sorted({(e.get("team"), e.get("player")) for e in acc if norm(e.get("player")) not in rk})
    print()
    print(f"── 帳號檔有、今年比賽沒出場（前端不列；{len(extra)} 位）── " + "、".join(f"{t}|{p}" for t, p in extra))
    if a.json:
        json.dump({"generated": today.isoformat(), "rows": rows}, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"→ {a.json}")


if __name__ == "__main__":
    main()
