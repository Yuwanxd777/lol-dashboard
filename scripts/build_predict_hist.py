# -*- coding: utf-8 -*-
"""「預測」分頁（水晶球）的歷屆世界賽參考數據 → predict_hist.js（window.PRED_HIST）。

只讀 data/data_YYYY.js 的 WLDs 場次，逐年算出水晶球題目會用到的排行與數字。
歷屆資料不會再變，所以不掛進每日管線；要多加一屆（或改題目定義）時手動重跑：
  python scripts/build_predict_hist.py            # 預設 2019～2025（使用者：前三屆不夠清楚就往前推）
  python scripts/build_predict_hist.py 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025

口徑跟 index.html 的「預測」分頁即時計算一致（改一邊要改另一邊）：
  出場率＝選用或禁用的局數 ÷ 總局數；勝率／場均死亡＝該英雄 ≥5 場；
  選手 KDA／場均傷害／參與率＝≥6 場；參與率＝(擊殺＋助攻) ÷ 戰隊擊殺。
  淘汰賽＝最後 7 個比賽日出場的戰隊（八強→決賽）；地區＝該隊當年出賽最多的國內賽事。
"""
import csv, datetime, io, json, os, sys
from collections import Counter, defaultdict

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "predict_hist.js")
INTL = {"WLDs", "MSI", "EWC", "FST", "KeSPA", "DCup", "AG", "ASI", "Rift Rivals"}
REGION = {"LTA N": "LCS", "LCS": "LCS", "NA LCS": "LCS", "LTA S": "CBLOL", "CBLOL": "CBLOL",
          "LTA": "LTA", "LCP": "LCP", "PCS": "PCS", "VCS": "VCS", "LJL": "LJL", "LLA": "LLA",
          "LCK": "LCK", "LPL": "LPL", "LEC": "LEC", "EU LCS": "LEC", "TCL": "TCL", "LCO": "LCO"}
# 賽區強度用（2026-10-11 使用者：以近三年賽區對戰成績判定）：舊賽區併到今年的名字
H2H_REG = {"LCK": "LCK", "LPL": "LPL", "LEC": "LEC", "EU LCS": "LEC", "LCS": "LCS", "NA LCS": "LCS", "LTA N": "LCS",
           "CBLOL": "CBLOL", "LTA S": "CBLOL", "LCP": "LCP", "PCS": "LCP", "VCS": "LCP", "LJL": "LCP", "LCO": "LCP"}
H2H_LG = {"WLDs", "MSI", "EWC", "FST", "DCup"}
# 勝率題的熱門度先驗（使用者 2026-10-11：勝率王都是最近很少選、但不是沒人選的英雄）：
#   賽前 90 天主要賽區＋國際賽的選用次數排名；記下該屆勝率前三（≥5 場）各自排第幾
PRE_LG = {"LCK", "LPL", "LEC", "LCS", "LTA N", "LTA S", "LTA", "CBLOL", "LCP", "PCS", "VCS", "LJL", "MSI", "EWC", "FST"}
# 決賽 MVP（資料庫沒有這個欄位，只放確定的屆數；不確定的不寫）
FINALS_MVP = {2019: ["Tian", "JNG"], 2020: ["Canyon", "JNG"], 2021: ["Scout", "MID"], 2022: ["Deft", "BOT"],
              2024: ["Faker", "MID"], 2025: ["Gumayusi", "BOT"]}  # 2023 不確定，先不放


def load(y):
    t = open(os.path.join(ROOT, "data", f"data_{y}.js"), encoding="utf-8").read()
    J = json.loads(t.split("=", 1)[1].strip().rstrip(";"))
    R = J["tabs"]["RAW_DATA"]
    return R[0], R[1:]


# 夏季（7～9 月）主要賽區：拿來算「區域聯賽 → 世界賽」的 15 殺發生率折扣（世界賽對手強、碾壓局少）
REG15_LG = {"LCK", "LPL", "LEC", "LCS", "LTA N", "LTA S", "LTA", "CBLOL", "LCP", "PCS", "VCS", "LJL"}


def cs_stats(y, w0):
    """單場最高總補兵（total cs）——年度資料檔沒收補兵，只能讀 csv_cache/{y}.csv（OE 原檔）。"""
    f = os.path.join(ROOT, "csv_cache", f"{y}.csv")
    if not os.path.exists(f):
        return None, None
    csv.field_size_limit(10 ** 9)
    G = defaultdict(float)
    with open(f, encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            if r.get("league") != "WLDs" or r.get("position") == "team" or str(r.get("date"))[:10] < w0:   # 正賽開打前的 WLDs＝資格賽（CSV 版本號寫法跟資料檔不同，改用日期）
                continue
            try:
                G[r["gameid"]] = max(G[r["gameid"]], float(r.get("total cs") or 0))
            except ValueError:
                pass
    return sum(v >= 450 for v in G.values()), int(max(G.values())) if G else None


def build(y):
    h, R = load(y)
    ix = {c: i for i, c in enumerate(h)}
    num = lambda r, c: float(r[ix[c]]) if r[ix[c]] not in ("", None) else 0.0
    G = {}
    team_lg = defaultdict(Counter)
    regK = defaultdict(float)                     # 夏季主要賽區：每局單人最高擊殺
    # 上游把各賽區的世界賽資格賽也標成 WLDs（2022 起每年都有，例如 LPL 9 月的資格賽）——
    #   跟 index.html 的 _WLD_MAIN 同一套判法：正賽整屆鎖同一版本且一定有跨賽區對戰，
    #   有跨區對戰的版本＝正賽版本，其餘版本的 WLDs 場次就是資格賽，一律排除。
    home = defaultdict(Counter)
    for r in R:
        if str(r[ix["participantid"]]) == "1" and r[ix["league"]] not in INTL:
            home[r[ix["blue_teamname"]]][r[ix["league"]]] += 1; home[r[ix["red_teamname"]]][r[ix["league"]]] += 1
    hl = lambda t: home[t].most_common(1)[0][0] if home[t] else None
    mains = {str(r[ix["patch"]]) for r in R if r[ix["league"]] == "WLDs" and str(r[ix["participantid"]]) == "1"
             and hl(r[ix["blue_teamname"]]) and hl(r[ix["red_teamname"]]) and hl(r[ix["blue_teamname"]]) != hl(r[ix["red_teamname"]])}
    isW = lambda r: r[ix["league"]] == "WLDs" and str(r[ix["patch"]]) in mains
    w0 = min((str(r[ix["date"]])[:10] for r in R if isW(r)), default=f"{y}-10-01")
    pre_lo = (datetime.date.fromisoformat(w0) - datetime.timedelta(days=90)).isoformat()
    pre = Counter()                               # 賽前 90 天選用次數
    h2hG = {}                                     # 國際賽每局 (藍, 紅, 藍勝?)
    for r in R:
        lg = r[ix["league"]]
        if str(r[ix["participantid"]]) not in ("1", "2", "3", "4", "5"):
            continue
        if lg in PRE_LG and pre_lo <= str(r[ix["date"]])[:10] < w0:
            pre[r[ix["blue_champion"]]] += 1; pre[r[ix["red_champion"]]] += 1
        if lg in H2H_LG:
            h2hG[(lg, str(r[ix["date"]])[:10], r[ix["blue_teamname"]], r[ix["red_teamname"]], str(r[ix["game"]]))] = r[ix["result"]] == 1
        if lg in REG15_LG and "07" <= str(r[ix["date"]])[5:7] <= "09":
            k = (str(r[ix["date"]])[:10], r[ix["blue_teamname"]], r[ix["red_teamname"]], str(r[ix["game"]]))
            regK[k] = max(regK[k], num(r, "blue_kills"), num(r, "red_kills"))
        if lg not in INTL:
            team_lg[r[ix["blue_teamname"]]][lg] += 1
            team_lg[r[ix["red_teamname"]]][lg] += 1
        if not isW(r):
            continue
        k = (str(r[ix["date"]])[:10], r[ix["blue_teamname"]], r[ix["red_teamname"]], str(r[ix["game"]]))
        g = G.setdefault(k, {"res": r[ix["result"]], "len": r[ix["blue_gamelength"]], "pl": [],
                             "bans": set(x for x in (str(r[ix["blue_banlist"]] or "") + "|" + str(r[ix["red_banlist"]] or "")).split("|") if x)})
        for s in ("blue", "red"):
            g["pl"].append(dict(name=r[ix[f"{s}_playername"]], team=r[ix[f"{s}_teamname"]], champ=r[ix[f"{s}_champion"]],
                                k=num(r, f"{s}_kills"), d=num(r, f"{s}_deaths"), a=num(r, f"{s}_assists"),
                                tk=num(r, f"{s}_teamkills"), dmg=num(r, f"{s}_damagetochampions"),
                                win=(r[ix["result"]] == 1) == (s == "blue")))
    n = len(G)
    pres, pk, w, dth = Counter(), Counter(), Counter(), Counter()
    P = defaultdict(lambda: dict(k=0, d=0, a=0, tk=0, dmg=0, n=0, team=""))
    lens, big, k15 = [], [], 0
    for g in G.values():
        champs = {p["champ"] for p in g["pl"] if p["champ"]}
        for c in champs | g["bans"]:
            pres[c] += 1
        if g["len"] not in ("", None):
            lens.append(float(g["len"]) / 60)
        if any(p["k"] >= 15 for p in g["pl"]):
            k15 += 1
        for p in g["pl"]:
            if not p["champ"]:
                continue
            pk[p["champ"]] += 1; w[p["champ"]] += p["win"]; dth[p["champ"]] += p["d"]
            q = P[p["name"]]; q["team"] = p["team"]; q["n"] += 1
            for c in ("k", "d", "a", "tk", "dmg"):
                q[c] += p[c]
            big.append([int(p["k"]), p["name"], p["champ"]])
    top = lambda keys, f, m=5: sorted(keys, key=f)[:m]
    c5 = [c for c in pk if pk[c] >= 5]
    p6 = {nm: q for nm, q in P.items() if q["n"] >= 6}
    kda = lambda q: (q["k"] + q["a"]) / max(1, q["d"])
    kp = lambda q: (q["k"] + q["a"]) / max(1, q["tk"])
    # 淘汰賽＝最後 7 個 BO5 系列（八強 4＋四強 2＋決賽 1）。舊版用「最後 7 個比賽日」，
    # 2019（12 隊）／2022（6 隊）賽程天數不同就抓錯；BO5＝系列裡有一方拿到 3 勝。
    ser = defaultdict(lambda: [Counter(), ""])
    for (d, b_, r_, gn), g in G.items():
        k = tuple(sorted((b_, r_)))
        ser[k + (d[:7],)][0][b_ if g["res"] == 1 else r_] += 1
        ser[k + (d[:7],)][1] = max(ser[k + (d[:7],)][1], d)
    bo5 = sorted((v[1], k[:2]) for k, v in ser.items() if max(v[0].values()) >= 3)
    swin = {k[:2]: v[0].most_common(1)[0][0] for k, v in ser.items() if max(v[0].values()) >= 3}
    fin = {}                                      # 淘汰賽最終名次：1 冠軍／2 亞軍／4 四強／8 八強
    for i, (_, pair) in enumerate(bo5[-7:]):
        lose = pair[0] if swin[pair] == pair[1] else pair[1]
        fin[lose] = 2 if i == 6 else (4 if i >= 4 else 8)
        if i == 6:
            fin[swin[pair]] = 1
    ko = sorted({t for _, pair in bo5[-7:] for t in pair})
    reg = {t: REGION.get(team_lg[t].most_common(1)[0][0], team_lg[t].most_common(1)[0][0]) if team_lg[t] else "?" for t in ko}
    shortest = sorted(([float(g["len"]) / 60, (k[1] if g["res"] == 1 else k[2])] for k, g in G.items() if g["len"] not in ("", None)))[:3]
    big.sort(reverse=True)
    out = {
        "games": n,
        "presence": [[c, round(pres[c] / n, 3)] for c, _ in pres.most_common(5)],
        "winrate": [[c, w[c], pk[c]] for c in top(c5, lambda c: (-w[c] / pk[c], -pk[c]))],
        "deaths": [[c, round(dth[c] / pk[c], 2), pk[c]] for c in top(c5, lambda c: -dth[c] / pk[c])],
        "kda": [[nm, p6[nm]["team"], round(kda(p6[nm]), 2), p6[nm]["n"]] for nm in top(p6, lambda nm: -kda(p6[nm]))],
        "dmg": [[nm, p6[nm]["team"], round(p6[nm]["dmg"] / p6[nm]["n"]), p6[nm]["n"]] for nm in top(p6, lambda nm: -p6[nm]["dmg"] / p6[nm]["n"])],
        "kp": [[nm, p6[nm]["team"], round(kp(p6[nm]), 3), p6[nm]["n"]] for nm in top(p6, lambda nm: -kp(p6[nm]))],
        "uniq": len(pk),
        "len32": [sum(l < 32 for l in lens), sum(l >= 32 for l in lens)],
        "avgLen": round(sum(lens) / len(lens), 2) if lens else None,
        "long45": sum(l >= 45 for l in lens),
        "maxLen": round(max(lens), 1) if lens else None,
        "maxKills": big[:3],
        "teemo": pk.get("Teemo", 0),
        "k15": k15,
        "kills": {nm: [int(P[nm]["k"]), P[nm]["n"]] for nm in ("Faker", "Peyz", "Gumayusi") if nm in P},
        "ko": [[t, reg[t]] for t in ko],
        "fin": fin,
        "koRegions": len(set(reg.values())),
        "koLCS": [t for t in ko if reg[t] == "LCS"],
        "shortest": [[round(l, 1), t] for l, t in shortest],
        "mvp": FINALS_MVP.get(y),
        "reg15": [len(regK), sum(v >= 15 for v in regK.values())],
        "h2h": {},
    }
    prank = {c: i + 1 for i, (c, _) in enumerate(pre.most_common())}
    out["wrPre"] = {"n": len(prank), "ranks": [prank.get(c[0], len(prank) + 1) for c in out["winrate"][:3]]}
    # 跨賽區交手（國際賽、不同賽區的兩隊）：{"LCK|LPL": [LCK 勝, LPL 勝]}，鍵照字母序
    hreg = {t: H2H_REG.get(c.most_common(1)[0][0]) for t, c in team_lg.items() if c}
    for (lg, d, b, rr, gn), bw in h2hG.items():
        A, B = hreg.get(b), hreg.get(rr)
        if not A or not B or A == B:
            continue
        k = "|".join(sorted((A, B))); x = out["h2h"].setdefault(k, [0, 0])
        x[0 if (A < B) == bw else 1] += 1
    out["cs450"], out["maxCS"] = cs_stats(y, w0)
    return out


def main():
    years = [int(a) for a in sys.argv[1:]] or list(range(2019, 2026))
    H = {}
    for y in years:
        H[str(y)] = build(y)
        d = H[str(y)]
        print(f"{y}：{d['games']} 局、不同英雄 {d['uniq']}、淘汰賽 {d['koRegions']} 個地區 {d['ko']}、≥450 補兵 {d['cs450']} 局（最高 {d['maxCS']}）、15 殺 {d['k15']}｜區域 {d['reg15']}")
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("window.PRED_HIST=" + json.dumps(H, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print("→", OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()
