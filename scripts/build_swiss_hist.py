# -*- coding: utf-8 -*-
"""預測分頁「瑞士輪籤運」歷年版 → swiss_hist.js（window.SWISS_HIST）。

使用者 2026-11-01：籤運表右上角可以切換年份，從 2023（第一屆瑞士輪）開始。
本屆（今年）照舊在前端即時算（index.html 的 DRW）；往年的賽程不會再變 ⇒ 這支離線算一次存檔。
算法跟前端 DRW 一字不差（改一邊要改另一邊）：
  每一場籤運＝「中等隊伍打當輪能抽到的對手（等權）的平均勝率」−「打實際對手的勝率」，正＝籤比隨機抽硬（只看對手，2026-11-01 改）。
  合法抽法：第 1 輪照分級（分級數 4 ⇒ 1 級對 4 級、2 級對 3 級；2025 只有 3 級 ⇒ 1 級對 3 級、2 級組內互打，
  兩種都是「級數相加＝級數−1」），同賽區不相遇；第 2 輪起同戰績組內、不重複對手（2023 允許重複對戰，2024 起才禁止）。
  強度＝前端 mkWorld 的模型（賽區 Bradley-Terry＋戰隊半衰期 120 天、往賽區收斂 LAM 1.5），只用瑞士輪開打前的局；
  同賽區對戰改看當年開打前兩隊交手單局（加 2 局模型勝率平滑）。BO3＝p²(3−2p)。
資料：Leaguepedia（MatchSchedule 逐輪對戰、Main Event 頁的分級）＋ data/data_YYYY.js（強度）＋ predict_hist.js（前兩年跨賽區 h2h）。
Leaguepedia 的原始回應存 csv_cache/swiss_hist_src.json，有就不重抓（--refetch 強制）。
跑：python scripts/build_swiss_hist.py [年份…]（預設 2023 到去年）
"""
import datetime, io, json, math, os, re, sys, urllib.parse, urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "swiss_hist.js")
SRC = os.path.join(ROOT, "csv_cache", "swiss_hist_src.json")
sys.path.insert(0, HERE)

# 跟 build_predict_hist.py 同一套（前端賽區強度吃的 h2h 就是它產的）
H2H_REG = {"LCK": "LCK", "LPL": "LPL", "LEC": "LEC", "EU LCS": "LEC", "LCS": "LCS", "NA LCS": "LCS", "LTA N": "LCS",
           "CBLOL": "CBLOL", "LTA S": "CBLOL", "LCP": "LCP", "PCS": "LCP", "VCS": "LCP", "LJL": "LCP", "LCO": "LCP"}
H2H_LG = {"WLDs", "MSI", "EWC", "FST", "DCup"}
# Main Event 頁 TeamRoster 的 team= 代碼 → MatchSchedule 全名
CODE = {"GEN": "Gen.G", "JDG": "JD Gaming", "G2": "G2 Esports", "NRG": "NRG", "T1": "T1", "BLG": "Bilibili Gaming",
        "FNC": "Fnatic", "C9": "Cloud9", "KT": "KT Rolster", "LNG": "LNG Esports", "MADL LEC": "MAD Lions",
        "TL": "Team Liquid", "Dplus": "Dplus Kia", "WBG": "Weibo Gaming", "GAM": "GAM Esports", "BDS": "Team BDS",
        "HLE": "Hanwha Life Esports", "FLY": "FlyQuest", "TES": "Top Esports", "MAD KOI": "MAD Lions KOI",
        "PAIN": "paiN Gaming", "PSGT": "PSG Talon", "CFO": "CTBC Flying Oyster", "AL CN": "Anyone's Legend",
        "VKS": "Vivo Keyd Stars", "MKOI": "Movistar KOI", "Secret Whales": "Team Secret Whales", "100T": "100 Thieves"}
OE_NAME = {(2023, "MAD Lions"): "MAD Lions KOI"}   # OE 把 2023 的 MAD Lions 記成後來的隊名
# 抽籤用的賽區（官方「同賽區不相遇」的賽區）：wiki 的 region= → 顯示代碼
RULE_REG = {"KR": "LCK", "CN": "LPL", "EMEA": "LEC", "NA": "LCS", "VN": "VCS", "BR": "CBLOL", "AME": "LTA"}


def fetch(year):
    import fetch_events_extra as F
    import build_predict_live as B
    ms = B.cargo({"tables": "MatchSchedule=M",
                  "fields": "M.OverviewPage=ov,M.Team1=t1,M.Team2=t2,M.DateTime_UTC=dt,M.Tab=tab,M.Winner=w,M.BestOf=bo",
                  "where": f"M.OverviewPage='{year} Season World Championship/Main Event'", "limit": "500", "format": "json"})
    return {"ms": ms, "wt": wikitext(f"{year} Season World Championship/Main Event"),
            "wtpi": wikitext(f"{year} Season World Championship/Play-In")}


def wikitext(page):
    import fetch_events_extra as F
    p = {"action": "parse", "page": page, "prop": "wikitext", "format": "json"}
    F._throttle()
    try:
        r = json.loads(urllib.request.urlopen(urllib.request.Request(F.API + "?" + urllib.parse.urlencode(p), headers=F.UA),
                                              timeout=60).read())
    finally:
        F._mark()
    return r["parse"]["wikitext"]["*"]


def seeds_of(src):
    """賽區種子：Main Event 頁 TeamRoster 的 seed=「Korea #1」；入圍賽上來的隊（seed=Play-In）改看 Play-In 頁；
    WQS 晉級（2023 BDS）記 "WQS"。回傳 {全名: 1~4 或 "WQS"}"""
    def raw(wt):
        out = {}
        for blk in re.split(r"(?=\{\{TeamRoster\|)", wt)[1:]:
            tm = re.match(r"\{\{TeamRoster\|team=([^\n|]+)", blk)
            sd = re.search(r"\|seed=([^\n]*)", blk[:600])
            out[tm.group(1).strip()] = sd.group(1) if sd else ""
        return out
    me, pi = raw(src["wt"]), raw(src.get("wtpi", ""))
    PI_ALIAS = {"PSGT": "PSG Talon", "KCORP": "Karmine Corp"}   # Play-In 頁的 team= 有時寫全名
    res = {}
    for code, v in me.items():
        if code not in CODE:
            continue
        if not re.search(r"#\s*\d", v):
            v = pi.get(code) or pi.get(PI_ALIAS.get(code, ""), "") or v
        n = re.search(r"#\s*(\d)", v)
        res[CODE[code]] = int(n.group(1)) if n else ("WQS" if "WQS" in v else None)
    return res


def pools_of(wt, year):
    w = wt[wt.index("== Participants =="):]
    pools, reg = [], {}
    for m in re.finditer(r"\{\{PoolStart\|text=Pool (\d)\}\}|\{\{TeamRoster\|team=([^\n|]+)\n\|region=(\w+)", w):
        if m.group(1):
            pools.append([]); continue
        nm = CODE[m.group(2).strip()]
        pools[-1].append(nm)
        rg = m.group(3)
        reg[nm] = RULE_REG.get(rg) or ("PCS" if year < 2025 else "LCP")   # APAC：2025 起併成 LCP
    return pools, reg


def load_games(year):
    d = open(os.path.join(ROOT, "data", f"data_{year}.js"), encoding="utf-8").read()
    R = json.loads(d[d.index("=") + 1:].rstrip().rstrip(";"))["tabs"]["RAW_DATA"]
    h = R[0]; ix = {k: h.index(k) for k in ("league", "date", "result", "participantid", "blue_teamname", "red_teamname")}
    out = []
    for r in R[1:]:
        if str(r[ix["participantid"]]) != "100":
            continue
        out.append({"lg": r[ix["league"]], "d": str(r[ix["date"]]).strip(), "b": r[ix["blue_teamname"]],
                    "r": r[ix["red_teamname"]], "bw": str(r[ix["result"]]) == "1"})
    return out


def dn(v):
    y, m, d = (int(x) for x in str(v)[:10].split("-"))
    return datetime.date(y, m, d).toordinal()


def model(year, games, cut, H):
    """前端 mkWorld 的 MODEL：回傳 strength(t)、teamReg"""
    G0 = [g for g in games if g["d"] < cut]
    cnt = {}
    for g in games:
        rg = H2H_REG.get(g["lg"])
        if not rg:
            continue
        for t in (g["b"], g["r"]):
            c = cnt.setdefault(t, {}); c[rg] = c.get(rg, 0) + 1
    treg = {t: max(c, key=c.get) for t, c in cnt.items()}
    P = {}
    def add(a, b, wa, wb):
        if not a or not b or a == b:
            return
        k = "|".join(sorted((a, b))); x = P.setdefault(k, [0, 0])
        if a < b: x[0] += wa; x[1] += wb
        else: x[0] += wb; x[1] += wa
    for y in (year - 2, year - 1):
        for k, v in ((H.get(str(y)) or {}).get("h2h") or {}).items():
            a, b = k.split("|"); add(a, b, v[0], v[1])
    for g in G0:
        if g["lg"] not in H2H_LG:
            continue
        a, b = treg.get(g["b"]), treg.get(g["r"])
        if a and b and a != b:
            add(a, b, 1 if g["bw"] else 0, 0 if g["bw"] else 1)
    R = {g: 0.0 for g in set(treg.values()) | {x for k in P for x in k.split("|")}}
    PR = [(*k.split("|"), v[0], v[1]) for k, v in P.items()]
    for _ in range(3000):
        gR = {g: -0.05 * R[g] for g in R}
        for a, b, wa, wb in PR:
            p = 1 / (1 + math.exp(R[b] - R[a])); d = wa - (wa + wb) * p; gR[a] += d; gR[b] -= d
        for g in R:
            R[g] += 0.004 * gR[g]
    tLast = dn(max(g["d"][:10] for g in G0))
    GG = [(g["b"], g["r"], 1 if g["bw"] else 0, 0.5 ** ((tLast - dn(g["d"])) / 120))
          for g in G0 if g["b"] in treg and g["r"] in treg]
    r = {t: R[treg[t]] for t in treg}
    for _ in range(300):
        gr = {t: -1.5 * (r[t] - R[treg[t]]) for t in r}
        for a, b, y, w in GG:
            p = 1 / (1 + math.exp(r[b] - r[a])); d = w * (y - p); gr[a] += d; gr[b] -= d
        for t in r:
            r[t] += 0.02 * gr[t]
    return (lambda t: r[t] if t in r else R.get(treg.get(t), 0)), treg


def legal(mem, ok):
    out = []
    def go(l, cur):
        if not l:
            out.append(cur); return
        a = l[0]
        for i in range(1, len(l)):
            if ok(a, l[i]):
                go([x for j, x in enumerate(l) if j not in (0, i)], cur + [(a, l[i])])
    go(mem, [])
    return out


def build_year(year, src, H):
    ms = src["ms"]; pools, rreg = pools_of(src["wt"], year)
    # 八強也算（使用者 2026-11-01）：輪號 6
    isQ = lambda x: "quarter" in str(x.get("tab") or "").lower()
    sw = [x for x in ms if (str(x.get("tab") or "").startswith("Round ") or isQ(x)) and str(x.get("w")) in ("1", "2")]
    cut = min(str(x["dt"])[:10] for x in sw if not isQ(x))
    on = lambda t: OE_NAME.get((year, t), t)
    games = load_games(year)
    st, treg = model(year, games, cut, H)
    S = lambda t: st(on(t))
    HH = {}
    for g in games:
        if not g["d"].startswith(str(year)) or g["d"] >= cut:
            continue
        a, b = g["b"], g["r"]
        if not treg.get(a) or treg.get(a) != treg.get(b):
            continue
        w = a if g["bw"] else b
        for x, y in ((a, b), (b, a)):
            h = HH.setdefault((x, y), [0, 0]); h[1] += 1; h[0] += (w == x)
    pm = lambda a, b: 1 / (1 + math.exp(S(b) - S(a)))
    def pG(a, b):
        h = HH.get((on(a), on(b))) if treg.get(on(a)) and treg.get(on(a)) == treg.get(on(b)) else None
        return (h[0] + 2 * pm(a, b)) / (h[1] + 2) if h and h[1] else pm(a, b)
    pS = lambda p, bo: p * p * (3 - 2 * p) if bo == 3 else p ** 3 * (1 + 3 * (1 - p) + 6 * (1 - p) ** 2) if bo == 5 else p
    # 只看對手（使用者 2026-11-01）：對手有效強度 seff＝S(u) − logit(pG(u,o))，拿「中等隊伍（16 隊平均強度 MU）打他的勝率」比
    byR = {}
    for x in sorted(sw, key=lambda x: str(x["dt"])):
        w = x["t1"] if str(x["w"]) == "1" else x["t2"]; l = x["t2"] if w == x["t1"] else x["t1"]
        byR.setdefault(6 if isQ(x) else int(re.sub(r"\D", "", x["tab"])), []).append((w, l, int(x["bo"] or 1)))
    teams = sorted({t for ps in byR.values() for p in ps for t in p[:2]})
    assert sorted(sum(pools, [])) == teams, (year, "分級名單跟賽程對不上", set(teams) ^ set(sum(pools, [])))
    pool = {t: i for i, pl in enumerate(pools) for t in pl}
    PS = len(pools) - 1
    MU = sum(S(t) for t in teams) / len(teams)
    qR = lambda u, o, bo: pS(1 / (1 + math.exp(S(u) - math.log(pG(u, o) / (1 - pG(u, o))) - MU)), bo)
    okR1 = lambda a, b: rreg[a] != rreg[b] and pool[a] + pool[b] == PS
    rec = {t: [0, 0] for t in teams}; met = set(); T = {t: {"tot": 0.0, "rs": {}} for t in teams}
    mk = lambda a, b: frozenset((a, b))
    warn = []
    for r in sorted(byR):
        ps = byR[r]; groups = {}
        for a, b, _ in ps:
            for t in (a, b):
                groups.setdefault("r1" if r == 1 else "qf" if r == 6 else tuple(rec[t]), []).append(t)
        # 2023 規則允許瑞士輪重複對戰（DK 打了 KT 兩次），2024 起才禁止（使用者 2026-11-01）
        # 八強籤：3-0 抽 3-2、剩下的 3-2 打 3-1、3-1 互打（敗場數配對 0-2／1-2／1-1）；
        #   2023～2025 八強實際都有瑞士輪重賽（NRG–WBG、TES–T1、G2–TES）⇒ 往年不排除重賽（2026 起不再碰，前端那邊）
        okQF = lambda a, b: tuple(sorted((rec[a][1], rec[b][1]))) in ((0, 2), (1, 2), (1, 1))
        ok = okR1 if r == 1 else okQF if r == 6 else (lambda a, b: year < 2024 or mk(a, b) not in met)
        boOf = lambda t: 5 if r == 6 else 3 if r > 1 and 2 in rec[t] else 1
        po = {}
        for k, mem in groups.items():
            L = [] if len(mem) % 2 else legal(mem, ok)
            if not L:
                warn.append(f"R{r} {k} 沒有合法抽法"); continue
            for m in L:
                for a, b in m:
                    po.setdefault(a, set()).add(b); po.setdefault(b, set()).add(a)
        for a, b, bo_act in ps:
            if boOf(a) != bo_act:
                warn.append(f"R{r} {a}-{b} 賽制 BO{bo_act} 跟戰績推的 BO{boOf(a)} 不同")
            if not ok(a, b):
                warn.append(f"R{r} {a}-{b} 實際對戰不在合法抽法裡")
            for u, v, isW in ((a, b, True), (b, a, False)):
                bo = boOf(u); qv = qR(u, v, bo); os_ = po.get(u, set())
                d = sum(qR(u, o, bo) for o in os_) / len(os_) - qv if os_ else None   # 能抽到的對手等權平均 − 實際對手
                rk = 1 + sum(1 for o in os_ if qR(u, o, bo) < qv - 1e-9) if os_ else None
                ol = sorted(os_, key=lambda o: qR(u, o, bo))   # 能抽到的對手由強到弱（滑上去看排名）
                T[u]["rs"][str(r)] = {"o": v, "bo": bo, "d": None if d is None else round(d, 4), "res": isW, "rk": rk, "m": len(os_), "ol": ol}
                if d is not None:
                    T[u]["tot"] += d
        for a, b, _ in ps:
            rec[a][0] += 1; rec[b][1] += 1; met.add(mk(a, b))
    sd = seeds_of(src)
    out = [{"n": t, "rg": rreg[t], "sd": sd.get(t), "q": 1 if rec[t][0] >= 3 else -1 if rec[t][1] >= 3 else 0,   # 3 勝＝晉級（八強輸了仍是 1）
            "tot": round(T[t]["tot"], 4), "rs": T[t]["rs"]} for t in teams]
    elo = {t: round(1500 + S(t) * 400 / math.log(10)) for t in teams}
    return {"from": cut, "T": out}, warn, elo


def main():
    yrs = [int(a) for a in sys.argv[1:] if a.isdigit()] or list(range(2023, datetime.date.today().year))
    cache = json.load(open(SRC, encoding="utf-8")) if os.path.exists(SRC) else {}
    hs = open(os.path.join(ROOT, "predict_hist.js"), encoding="utf-8").read()
    H = json.loads(hs[hs.index("=") + 1:].rstrip().rstrip(";"))
    res = {}
    for y in yrs:
        if str(y) not in cache or "--refetch" in sys.argv:
            cache[str(y)] = fetch(y)
            json.dump(cache, open(SRC, "w", encoding="utf-8"), ensure_ascii=False)
        elif "wtpi" not in cache[str(y)]:   # 舊快取沒有 Play-In 頁（種子要用）
            cache[str(y)]["wtpi"] = wikitext(f"{y} Season World Championship/Play-In")
            json.dump(cache, open(SRC, "w", encoding="utf-8"), ensure_ascii=False)
        res[str(y)], warn, elo = build_year(y, cache[str(y)], H)
        top = sorted(res[str(y)]["T"], key=lambda x: -x["tot"])
        print(f"{y}（開打 {res[str(y)]['from']}）：最硬 " + "、".join(f"{x['n']} {x['tot']:+.2f}" for x in top[:3])
              + "；最好 " + "、".join(f"{x['n']} {x['tot']:+.2f}" for x in top[-3:]))
        print("   強度 " + " ".join(f"{t}:{e}" for t, e in sorted(elo.items(), key=lambda x: -x[1])))
        for w in warn:
            print("   ⚠", w)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("window.SWISS_HIST=" + json.dumps(res, ensure_ascii=False, separators=(",", ":")) + ";")
    print("→ swiss_hist.js", os.path.getsize(OUT), "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
