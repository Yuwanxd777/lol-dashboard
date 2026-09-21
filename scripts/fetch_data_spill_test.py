# -*- coding: utf-8 -*-
"""fetch_data.split_spill 的世界賽截止點（2026-09-21 精進迴圈 #180）。

病根：OE 把區域資格賽也標成 WLDs（2026 是 LPL Regional Finals 09-17～19）。舊寫法拿「全部 WLDs 列
的最晚日期」當世界賽截止點 ⇒ 真世界賽開打前，截止點落在資格賽最後一天，之後的 LEC／LCS／CBLOL
決賽全被當成「世界賽後」搬去隔年（spill_2027.json），健檢報三個聯賽落後 2 個比賽日。
新寫法：有「藍紅兩隊主場聯賽不同」的 WLDs 局才算世界賽開打了；沒有就不切。

  ⓪ 封網保險絲（本測試不該有任何網路請求）＋保險絲自己會擋的正控制
  ① 合成案例（隊名 Zzprobe* 只有沙盒才有）：沒有 WLDs／只有資格賽／資格賽＋真世界賽＋世界賽後／
     同賽區決賽／入圍賽查不到主場／兩隊都查不到／國際賽列不算主場／回傳值
  ② 正控制：釘 OLDREV 的舊版 split_spill 對「只有資格賽」必須把之後的聯賽局切走（重現病），
     對「真世界賽已開打」必須跟新版一樣（舊版在那時是對的）
  ③ 真實素材：釘 PIN_DATA 那一版 data_2026.js（72 列同賽區 WLDs），注入 LEC／CBLOL 09-20 的局
     （那一版沒有 ⇒ 只有沙盒才有的證據）；再注入一場跨賽區世界賽＋一場世界賽後的 KeSPA 走完整個生命週期
  ④ 真實 OE 原檔（csv_cache/{年}.csv）逐年：新舊 keep／spill 逐列相同；2022～2025 都有「第一場跨賽區
     之前的 WLDs 列」（＝素材裡真的有被標成 WLDs 的資格賽，新規則那一刀有被走到）。--quick 跳過。
  ⑤ 正本 size＋mtime_ns 沒動、網路帳是空的

用法：python scripts/fetch_data_spill_test.py [--quick]
環境變數 M180_FD＝要測的 fetch_data.py 路徑（突變腳本 autopilot/_m180_mutate.py 用；預設就是 scripts/ 那支）。
被測的只有 team_home_leagues／worlds_cutoff／split_spill 三個純函式；④ 產素材的 process() 一律用正本模組。
"""
import ast, contextlib, copy, importlib.util, io, json, os, subprocess, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
QUICK = "--quick" in sys.argv
OLDREV = "2fffcbe5"     # #180 改動前最後一版（split_spill 還是「全部 WLDs 取 max」）
PIN_DATA = "18da6b0f"   # 09-21 10:00 那班的 data_2026.js：LPL 資格賽 72 列標成 WLDs、LEC／CBLOL 只到 09-18
HIST_YEARS = (2014, 2022, 2023, 2024, 2025)

sys.path.insert(0, HERE)
import fetch_data as FD_REAL  # noqa: E402  （④ 用它的 process() 產素材）

TARGET = os.environ.get("M180_FD") or os.path.join(HERE, "fetch_data.py")
_spec = importlib.util.spec_from_file_location("fetch_data_under_test", TARGET)
FD = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(FD)

# ── ⓪ 封網：import 完（ssl／http.client 都已載入）才裝保險絲（DAILY #164 (a)）──
import socket, http.client, urllib.request  # noqa: E402,E401
NET_HITS = []


class _Blocked(RuntimeError):
    pass


def _blow(name):
    def f(*a, **k):
        NET_HITS.append(name)
        raise _Blocked("封網：" + name)
    return f


socket.socket = _blow("socket.socket")
socket.create_connection = _blow("socket.create_connection")
http.client.HTTPConnection = _blow("HTTPConnection")
http.client.HTTPSConnection = _blow("HTTPSConnection")
urllib.request.urlopen = _blow("urlopen")

OK = []
NG = []


def check(name, cond, detail=""):
    (OK if cond else NG).append(name)
    print(("  ✓ " if cond else "  ✗ ") + name + ("" if cond else ("　" + str(detail))))


def stat_of(paths):
    out = {}
    for p in paths:
        try:
            st = os.stat(p)
            out[p] = (st.st_size, st.st_mtime_ns)
        except OSError:
            out[p] = None
    return out


GUARD = [os.path.join(ROOT, "data", "data_2026.js"), os.path.join(ROOT, "csv_cache", "promo_games.json")]
GUARD += [os.path.join(ROOT, "csv_cache", f"spill_{y}.json") for y in range(2014, 2028)]
GUARD += [os.path.join(ROOT, "csv_cache", f"{y}.csv") for y in HIST_YEARS]
BEFORE = stat_of(GUARD)

print("⓪ 封網保險絲")
_n0 = len(NET_HITS)
try:
    urllib.request.urlopen("http://zzprobe9942.invalid/")
    blocked = False
except _Blocked:
    blocked = True
except Exception:
    blocked = False
check("⓪ 保險絲真的會擋（正控制）", blocked and NET_HITS[_n0:] == ["urlopen"], NET_HITS[_n0:])
del NET_HITS[_n0:]   # 只清自己這一發（DAILY #164 (b)）

# ── 合成素材 ──
HDR = ["league", "split", "date", "game", "result", "patch", "participantid",
       "blue_playername", "blue_teamname", "red_playername", "red_teamname"]


def game(lg, date, blue, red, n=6):
    return [[lg, "", date, "1", 1, "26.18", str(i + 1), "p%d" % i, blue, "q%d" % i, red] for i in range(n)]


def season(lg, teams, month="2026-06"):
    rows = []
    for i, a in enumerate(teams):
        for b in teams[i + 1:]:
            rows += game(lg, f"{month}-1{i} 10:00:00", a, b)
    return rows


LPL = ["Zzprobe LPL A", "Zzprobe LPL B", "Zzprobe LPL C"]
LCK = ["Zzprobe LCK A", "Zzprobe LCK B"]
LEC = ["Zzprobe LEC A", "Zzprobe LEC B"]
BASE = season("LPL", LPL) + season("LCK", LCK) + season("LEC", LEC)
REGIONAL = game("WLDs", "2026-09-17 09:00:00", LPL[0], LPL[1]) + game("WLDs", "2026-09-19 12:09:59", LPL[1], LPL[2])
LEC_FINAL = game("LEC", "2026-09-20 15:13:50", LEC[0], LEC[1])
WORLDS = game("WLDs", "2026-10-15 08:00:00", LCK[0], LPL[0]) + game("WLDs", "2026-10-20 08:00:00", LEC[0], LPL[2])
MID = game("LPL", "2026-10-25 08:00:00", LPL[1], LPL[2])        # 世界賽期間排在最後一個世界賽日之前的別的賽事
FINAL_SAME = game("WLDs", "2026-11-08 09:00:00", LCK[0], LCK[1])  # 同賽區決賽（2022 DRX vs T1 那種）
KESPA = game("KeSPA", "2026-12-06 06:00:00", LCK[0], LCK[1])


def run(mod, rows):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        keep, spill = mod.split_spill([list(HDR)] + copy.deepcopy(rows))
    return keep[1:], spill[1:], buf.getvalue()


print("① 合成案例（新版）")
k, s, out = run(FD, BASE + LEC_FINAL)
check("①a 沒有 WLDs ⇒ 全部留下", len(k) == len(BASE + LEC_FINAL) and s == [], (len(k), len(s)))
check("①a 沒有 WLDs ⇒ 不印資格賽那句（不製造噪音）", "同賽區對戰" not in out, out)

k, s, out = run(FD, BASE + REGIONAL + LEC_FINAL)
check("①b 只有資格賽 ⇒ 一列都不切（LEC 09-20 決賽留在今年）", s == [] and LEC_FINAL[0] in k, (len(s),))
check("①b 只有資格賽 ⇒ 印出「WLDs 12 列全是同賽區對戰」（放過要出聲）", "WLDs 12 列全是同賽區對戰" in out, out)

rows = BASE + REGIONAL + LEC_FINAL + WORLDS + MID + FINAL_SAME + KESPA
k, s, out = run(FD, rows)
check("①c 真世界賽開打後 ⇒ 只切世界賽後（KeSPA）", s == KESPA, [r[:3] for r in s][:3])
check("①c 資格賽／LEC 決賽／世界賽期間的別的賽事都留下",
      all(r in k for r in REGIONAL + LEC_FINAL + MID), "")
check("①d 同賽區決賽那天整局留下（截止點＝最晚 WLDs 列，含當天）", all(r in k for r in FINAL_SAME), "")
check("①c 真世界賽開打後不印資格賽那句", "同賽區對戰" not in out, out)

hdr = list(HDR)
cut, n_w, n_i = FD.worlds_cutoff(hdr, rows)
check("①h worlds_cutoff 回 (決賽時間, WLDs 30 列, 跨賽區 12 列)", (cut, n_w, n_i) == ("2026-11-08 09:00:00", 30, 12),
      (cut, n_w, n_i))
check("①h 只有資格賽 ⇒ (None, 12, 0)", FD.worlds_cutoff(hdr, BASE + REGIONAL) == (None, 12, 0),
      FD.worlds_cutoff(hdr, BASE + REGIONAL))
check("①h 沒有 WLDs ⇒ (None, 0, 0)", FD.worlds_cutoff(hdr, BASE) == (None, 0, 0), FD.worlds_cutoff(hdr, BASE))

PLAYIN = game("WLDs", "2026-10-10 08:00:00", "Zzprobe Wildcard", LEC[1])
AFTER = game("LCK", "2026-10-11 08:00:00", LCK[0], LCK[1])
k, s, out = run(FD, BASE + REGIONAL + PLAYIN + AFTER)
check("①e 入圍賽：查不到主場的隊 vs 查得到的 ⇒ 算世界賽開打（之後的局被切）", s == AFTER, len(s))

TWO_WILD = game("WLDs", "2026-10-10 08:00:00", "Zzprobe Wildcard", "Zzprobe Wildcard 2")
k, s, out = run(FD, BASE + REGIONAL + TWO_WILD + AFTER)
check("①f 兩隊都查不到主場 ⇒ 不算跨賽區、不切", s == [] and "WLDs 18 列全是同賽區對戰" in out, (len(s), out))

MSI_HEAVY = []
for i in range(4):
    MSI_HEAVY += game("MSI", f"2026-07-0{i + 1} 08:00:00", LPL[0], LCK[1])
MSI_HEAVY += game("EWC", "2026-07-15 08:00:00", LPL[0], LEC[0]) * 2
k, s, out = run(FD, game("LPL", "2026-06-01 10:00:00", LPL[0], LPL[1]) + BASE[6:] + MSI_HEAVY + REGIONAL + LEC_FINAL)
home = FD.team_home_leagues(hdr, game("LPL", "2026-06-01 10:00:00", LPL[0], LPL[1]) + MSI_HEAVY)
check("①g 國際賽列比聯賽列多的隊，主場仍是聯賽（LPL）", home.get(LPL[0]) == "LPL", home.get(LPL[0]))
check("①g 所以那場資格賽仍是同賽區、LEC 決賽不被切", s == [], len(s))
# 非國際賽的次要聯賽（真實資料裡 Gen.G 有 EWCQ韓國 列）：主場要取出現最多的那個
two = game("LPL", "2026-06-01 10:00:00", LPL[0], LPL[1]) * 2 + game("Zzprobe Qual", "2026-05-01 10:00:00", LPL[0], LCK[0])
home2 = FD.team_home_leagues(hdr, two)
check("①g2 主場＝出現最多的聯賽（LPL 12 列 vs 次要聯賽 6 列）", home2.get(LPL[0]) == "LPL", home2.get(LPL[0]))

print("② 正控制：釘 %s 的舊版 split_spill" % OLDREV)
try:
    old_src = subprocess.run(["git", "show", f"{OLDREV}:scripts/fetch_data.py"], cwd=ROOT,
                             capture_output=True, check=True).stdout.decode("utf-8")
    fn = next(n for n in ast.parse(old_src).body if isinstance(n, ast.FunctionDef) and n.name == "split_spill")
    ns = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "old_split_spill", "exec"), ns)
    OLD = type("OldFD", (), {"split_spill": staticmethod(ns["split_spill"])})
    old_ok = "worlds_cutoff" not in old_src
except Exception as e:
    OLD, old_ok = None, False
    print("   舊版拉不出來：", e)
check("② 舊版拉得出來、而且真的沒有 worlds_cutoff（釘對版本）", OLD is not None and old_ok, OLDREV)
if OLD is not None:
    k, s, out = run(OLD, BASE + REGIONAL + LEC_FINAL)
    check("② 舊版對「只有資格賽」把 LEC 09-20 決賽切走（重現 09-21 的病）", s == LEC_FINAL, len(s))
    k2, s2, _ = run(FD, rows)
    k1, s1, _ = run(OLD, rows)
    check("② 真世界賽已開打時新舊一樣（舊版那時是對的）", (k1, s1) == (k2, s2), (len(s1), len(s2)))

print("③ 真實素材：釘 %s 的 data_2026.js" % PIN_DATA)
real = None
try:
    raw = subprocess.run(["git", "show", f"{PIN_DATA}:data/data_2026.js"], cwd=ROOT,
                         capture_output=True, check=True).stdout.decode("utf-8")
    real = json.loads(raw[raw.index("=") + 1:].rstrip().rstrip(";"))["tabs"]["RAW_DATA"]
except Exception as e:
    print("   素材讀不到：", e)
check("③ 素材讀得到", bool(real) and len(real) > 16000, len(real) if real else 0)
if real:
    rh = real[0]
    iL, iD, iB, iR = (rh.index(c) for c in ("league", "date", "blue_teamname", "red_teamname"))
    body = real[1:]
    wl = [r for r in body if r[iL] == "WLDs"]
    check("③ 前提：那一版有 72 列 WLDs、全在 09-17～09-19", len(wl) == 72 and
          {r[iD][:10] for r in wl} == {"2026-09-17", "2026-09-18", "2026-09-19"}, len(wl))
    home = FD.team_home_leagues(rh, body)
    teams = {r[iB] for r in wl} | {r[iR] for r in wl}
    check("③ 那幾隊的主場全是 LPL（所以是同賽區資格賽）", {home.get(t) for t in teams} == {"LPL"},
          {t: home.get(t) for t in teams})

    def clone(lg, when, n=None):
        src = [r for r in body if r[iL] == lg]
        last = max(r[iD] for r in src)
        g = [copy.deepcopy(r) for r in src if r[iD] == last]
        for r in g:
            r[iD] = when
        return g

    inj = clone("LEC", "2026-09-20 17:13:10") + clone("CBLOL", "2026-09-20 18:46:20")
    check("③ 注入的局那一版沒有（只有沙盒才有的證據）",
          not any(r[iD].startswith("2026-09-20") and r[iL] in ("LEC", "CBLOL") for r in body), "")
    tb = [rh] + body + inj
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        k, s = FD.split_spill(copy.deepcopy(tb))
    check("③ 新版：一列都不切（%d 列全留）" % len(body + inj), len(k) == len(tb) and len(s) == 1, (len(k), len(s)))
    check("③ 新版：印「WLDs 72 列全是同賽區對戰」", "WLDs 72 列全是同賽區對戰" in buf.getvalue(), buf.getvalue())
    if OLD is not None:
        with contextlib.redirect_stdout(io.StringIO()):
            ok_, os_ = OLD.split_spill(copy.deepcopy(tb))
        check("③ 舊版：注入的 LEC／CBLOL 09-20 全被切走（正控制）", all(r in os_[1:] for r in inj), len(os_) - 1)

    # 生命週期：真世界賽開打（Gen.G vs Bilibili Gaming）→ 世界賽後的 KeSPA
    def pick(lg, prefer):
        src = {r[iB] for r in body if r[iL] == lg}
        return next((t for t in prefer if t in src), sorted(src)[0])
    t_lck = pick("LCK", ("Gen.G", "T1"))
    t_lpl = pick("LPL", ("Bilibili Gaming", "Top Esports"))
    wg = [copy.deepcopy(r) for r in wl[:6]]
    for r in wg:
        r[iD] = "2026-10-15 10:00:00"
        r[iB], r[iR] = t_lck, t_lpl
    kp = [copy.deepcopy(r) for r in body if r[iL] == "KeSPA"][:6]
    for r in kp:
        r[iD] = "2026-12-06 06:06:51"
    check("③ 前提：%s 主場 LCK、%s 主場 LPL、有 KeSPA 可複製" % (t_lck, t_lpl),
          home.get(t_lck) == "LCK" and home.get(t_lpl) == "LPL" and len(kp) == 6, (home.get(t_lck), home.get(t_lpl), len(kp)))
    with contextlib.redirect_stdout(io.StringIO()):
        k, s = FD.split_spill(copy.deepcopy([rh] + body + inj + wg + kp))
    check("③ 世界賽開打後：只切 12-06 那場 KeSPA", s[1:] == kp, len(s) - 1)
    check("③ 世界賽開打後：LEC／CBLOL 09-20 仍留在今年", all(r in k for r in inj), "")

if not QUICK:
    print("④ 真實 OE 原檔逐年（process() 用正本模組；新舊 split_spill 逐列比）")
    have = 0
    for y in HIST_YEARS:
        p = os.path.join(ROOT, "csv_cache", f"{y}.csv")
        if not os.path.exists(p):
            print(f"   {y}：沒有原檔快取，略過")
            continue
        have += 1
        with open(p, encoding="utf-8") as f:
            text = f.read()
        with contextlib.redirect_stdout(io.StringIO()):
            table = FD_REAL.process(text, y)
            nk, ns_ = FD.split_spill(copy.deepcopy(table))
            ok_, os_ = OLD.split_spill(copy.deepcopy(table)) if OLD else (None, None)
        check(f"④ {y} 新舊 keep／spill 逐列相同（keep {len(nk) - 1}／spill {len(ns_) - 1}）",
              OLD is not None and (nk, ns_) == (ok_, os_), (len(ok_ or []), len(os_ or [])))
        if y >= 2022:
            h = table[0]
            jL, jD, jB, jR = (h.index(c) for c in ("league", "date", "blue_teamname", "red_teamname"))
            hm = FD.team_home_leagues(h, table[1:])
            w = [r for r in table[1:] if r[jL] == "WLDs"]
            intl = [r[jD] for r in w if (hm.get(r[jB]) or hm.get(r[jR])) and hm.get(r[jB]) != hm.get(r[jR])]
            first = min(intl) if intl else ""
            pre = [r for r in w if r[jD] < first]
            check(f"④ {y} 素材裡真的有「第一場跨賽區之前」的 WLDs 列（{len(pre)} 列＝被標成 WLDs 的資格賽）",
                  len(pre) > 0, len(pre))
    check("④ 至少 4 年有原檔快取（素材不足就不算測過）", have >= 4, have)
else:
    print("④ --quick：跳過真實 OE 原檔逐年比對")

print("⑤ 收尾")
check("⑤ 網路帳是空的（本測試沒有任何請求漏出去）", NET_HITS == [], NET_HITS)
AFTER_ST = stat_of(GUARD)
changed = [p for p in GUARD if BEFORE[p] != AFTER_ST[p]]
check("⑤ 正本 %d 個檔 size＋mtime_ns 沒動" % len(GUARD), not changed, changed)

print(f"\n{len(OK)} 過／{len(NG)} 敗")
if NG:
    print("---- 失敗：")
    for n in NG:
        print("   ", n)
sys.exit(1 if NG else 0)
