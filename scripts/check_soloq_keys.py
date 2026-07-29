# -*- coding: utf-8 -*-
"""積分資料覆蓋＋鍵落差健檢（常駐工具，比照 lint_text.py：改積分管線或發現「某隊沒有積分資料」時跑一次）

檢查三件事：
 ① 鍵落差：比賽端的「隊縮寫|選手名」與積分端（soloq_accounts / soloq_match_index / soloq_recent）的鍵不一致
    → 前端已用 index.html 的 sqKey() 吸收（teamFix + 小寫），但落差變多代表上游標籤又漂移了，值得看一眼。
    2026-07-28 首次跑出 16 筆：GEN↔GENG、TL↔TLAW、DRX↔KRX（整隊 11 位）＋ Vulcan/huhi/nuc/Pout/HARPOON 大小寫。
 ② 覆蓋缺口：今年有出賽卻完全沒有積分帳號的選手（排除 KeSPA 二軍那種 1-3 場的臨時名單）。
 ③ 殭屍：帳號檔有、今年完全沒出賽的選手（無害，僅供清理參考）。

用法：python scripts\check_soloq_keys.py [--year 2026] [--min 5] [--all]
      --min N  ②只列出賽 ≥N 場的（預設 5，濾掉盃賽二軍）；--all 全列
純本機讀檔，不呼叫任何外部 API。
"""
import argparse, io, json, os, re, sys
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)

ap = argparse.ArgumentParser()
ap.add_argument("--year", type=int, default=0, help="預設＝data.js 的最新年份")
ap.add_argument("--min", type=int, default=5, help="②的出場數門檻（預設 5）")
ap.add_argument("--all", action="store_true", help="②不套門檻，全部列出")
A = ap.parse_args()

# index.html 的 TEAM_ALIAS 要與這裡一致（縮寫統一）
TEAM_ALIAS = {"GENG": "GEN", "TLAW": "TL", "AGAL": "AL", "DNF": "DNS", "KRX": "DRX"}
teamFix = lambda t: TEAM_ALIAS.get(t, t)


def load_js(path):
    """window.X = {...};  →  dict"""
    s = open(path, encoding="utf-8").read()
    return json.loads(s.split("=", 1)[1].strip().rstrip(";"))


year = A.year
if not year:
    dj = load_js(os.path.join(ROOT, "data.js"))
    ys = dj.get("years") or dj.get("list") or []
    year = max(int(y) for y in ys) if ys else 2026

D = load_js(os.path.join(ROOT, "data", f"data_{year}.js"))
RAW = D["tabs"]["RAW_DATA"]; hdr, rows = RAW[0], RAW[1:]
BI = hdr.index("blue_playername"); RI = hdr.index("red_playername")
TB = hdr.index("blue_teamname");   TR = hdr.index("red_teamname")
PI = hdr.index("participantid")

games = defaultdict(int); team_of = defaultdict(lambda: defaultdict(int))
for r in rows:
    pid = int(r[PI]) if str(r[PI]).isdigit() else 0
    if pid not in (1, 2, 3, 4, 5):
        continue
    for nmi, tmi in ((BI, TB), (RI, TR)):
        nm, tm = r[nmi], r[tmi]
        if nm and tm:
            games[nm] += 1; team_of[nm][tm] += 1
main_team = lambda p: max(team_of[p].items(), key=lambda x: x[1])[0]

ACC = json.load(open(os.path.join(HERE, "soloq_accounts.json"), encoding="utf-8"))
acc_by_player = defaultdict(list)
for a in ACC:
    if a.get("player"):
        acc_by_player[a["player"]].append(a)

# 積分端各表的鍵（隊縮寫|選手名）
srcs = {}
for fn, var in (("soloq_match_index.js", "IDX"), ("soloq_recent.js", "REC")):
    p = os.path.join(ROOT, fn)
    if os.path.exists(p):
        srcs[var] = set((load_js(p).get("players") or {}).keys())
# 帳號檔沒有隊縮寫→選手名的鍵，改用 (team, player)
srcs["ACC"] = set(f'{a.get("team","")}|{a.get("player","")}' for a in ACC if a.get("player"))

norm = lambda k: (teamFix(k.split("|", 1)[0]) + "|" + k.split("|", 1)[1]) if "|" in k else k
maps = {v: {norm(k).lower(): k for k in sorted(ks)} for v, ks in srcs.items()}
exact = {v: set(ks) for v, ks in srcs.items()}

# 比賽端隊縮寫：用帳號端的縮寫反推（本腳本沒有 abbrOf，改以「同名選手在積分端的隊縮寫」對照）
print(f"=== 積分鍵健檢　年份 {year}　（比賽 {len(games)} 位選手 / 帳號 {len(acc_by_player)} 位 / "
      f"IDX {len(srcs.get('IDX',()))} / REC {len(srcs.get('REC',()))}）===\n")

# ── ① 鍵落差：帳號端名字與比賽端名字只差大小寫 ──
oe_lower = {}
for p in games:
    oe_lower.setdefault(p.lower(), p)
case_diff = []
for p in acc_by_player:
    if p not in games and p.lower() in oe_lower:
        case_diff.append((oe_lower[p.lower()], p, games[oe_lower[p.lower()]]))
print("① 選手名大小寫落差（比賽端 vs 積分端）：%d 筆" % len(case_diff))
for oe, ac, g in sorted(case_diff, key=lambda x: -x[2]):
    print(f"    {g:4d} 場  比賽「{oe}」  積分「{ac}」")
ab_diff = sorted({(t, teamFix(t)) for a in ACC for t in [a.get("team", "")] if t and teamFix(t) != t})
print("   隊縮寫落差（TEAM_ALIAS 吸收中）：", ", ".join(f"{a}→{b}" for a, b in ab_diff) or "無")
print("   ※ 前端由 index.html 的 sqKey() 統一吸收；此處只是提醒上游標籤變動\n")

# ── ② 覆蓋缺口 ──
acc_lower = set(p.lower() for p in acc_by_player)
miss = sorted(((g, p, main_team(p)) for p, g in games.items() if p.lower() not in acc_lower), reverse=True)
lim = 0 if A.all else A.min
shown = [m for m in miss if m[0] >= lim]
print(f"② 今年有出賽但沒有積分帳號：{len(miss)} 位（其中 ≥{lim} 場的 {len(shown)} 位）")
for g, p, t in shown:
    print(f"    {g:4d} 場  {p:18s} {t}")
if not shown:
    print("    （無）")

# ── ③ 殭屍 ──
gl = set(p.lower() for p in games)
zomb = sorted(p for p in acc_by_player if p.lower() not in gl)
print(f"\n③ 帳號檔有、今年完全沒出賽：{len(zomb)} 位")
print("    " + ("、".join(zomb) if zomb else "（無）"))
