# -*- coding: utf-8 -*-
"""fetch_obgg_accounts 的「賽區之間並行（ZONE_PAR，2026-09-16 迴圈 #128）」離線測試（不打網路）。
假 OBGG：urllib.request.urlopen 換成本地假伺服器（真的 get() 照跑重試／計數），time.sleep 換成 no-op，
http.client.HTTPSConnection 換成會炸的 stub（keep-alive 那條路）。
驗：①新版（並行）與 --zone-seq、與改動前那版（OLDREV）的 out／插入順序／名冊／請求數／zone_err／帳號檔 byte 全等
    ②正控制：新版真的有「不同賽區的隊同時在飛」；--zone-seq 與舊版恆為 1（這條斷言有鑑別力）
    ③併發上限沒變 ④zone_err 在多區同時失敗時歸屬正確（突變：拿掉賽區標記就紅）⑤不死結 ⑥真實檔案一個沒動
用法：python scripts/fetch_obgg_zonepar_test.py
"""
import os, sys, io, json, time, threading, tempfile, inspect, datetime, contextlib, importlib.util, subprocess, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SRC = os.path.join(HERE, "fetch_obgg_accounts.py")
OLDREV = "415f9f48"      # #128 改動之前那一版（釘 commit，不寫 HEAD——一 commit 之後 HEAD 就是新版，見 DAILY #93）

_KEEP = [sys.stdout]     # 被測模組 import 時會把 sys.stdout 換成新的 TextIOWrapper；舊的被 GC 會連 buffer 一起關（#114）
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    _KEEP.append(sys.stdout)
    return m

OK = FAIL = 0
def check(name, cond, info=""):
    global OK, FAIL
    if cond: OK += 1; print(f"  ✓ {name}", flush=True)
    else: FAIL += 1; print(f"  ✗ {name}  {info}", flush=True)

REAL = [os.path.join(HERE, "soloq_accounts.json"), os.path.join(HERE, "soloq_accounts.json.bak"),
        os.path.join(ROOT, "csv_cache", "obgg_roster.json"), os.path.join(ROOT, "csv_cache", "obgg_progamer_cache.json"),
        os.path.join(ROOT, "csv_cache", "soloq_disowned.json")]
def snap():
    return {p: ((os.stat(p).st_size, os.stat(p).st_mtime_ns) if os.path.exists(p) else None) for p in REAL}
REAL0 = snap()

TMP = tempfile.mkdtemp(prefix="obgg_zonepar_")
M = load(SRC, "foa_zonepar_new")
_old = subprocess.run(["git", "show", f"{OLDREV}:scripts/fetch_obgg_accounts.py"], cwd=ROOT, capture_output=True)
assert _old.returncode == 0 and _old.stdout, f"拉不到 {OLDREV} 那版：{_old.stderr[:200]}"
OLD_DIR = os.path.join(TMP, "old"); os.makedirs(OLD_DIR)
OLD_PATH = os.path.join(OLD_DIR, "fetch_obgg_accounts.py")
open(OLD_PATH, "wb").write(_old.stdout)
O = load(OLD_PATH, "foa_zonepar_old")
BASE_URL = M.BASE
assert O.BASE == BASE_URL

# ───────────── 假 OBGG ─────────────
ZONES_FAKE = {"LPL": ["BLG", "JDG", "TES", "WBG", "LNG"], "LCK": ["T1", "GEN", "HLE", "KT"], "LEC": ["G2", "FNC"], "LCP": ["CFO", "PSG"]}
TEAM_ZONE = {t: z for z, ts in ZONES_FAKE.items() for t in ts}
EMPTY_TEAMS = {"PSG"}
POS = ["上", "野", "中", "下", "辅", "辅"]
NOW_MS = time.time() * 1000
LAT = 0.04
_real_sleep = time.sleep
LOCK = threading.Lock()
ST = {}
FAIL_URLS = set()

def reset_stats():
    ST.clear()
    ST.update(infl={"zone": 0, "team": 0, "progamer": 0}, peak={"zone": 0, "team": 0, "progamer": 0},
              calls={"zone": 0, "team": 0, "progamer": 0}, inz={}, inz_t={}, peakz=0, peakz_t=0, zt_pairs=set())

def qs(q):
    return dict(urllib.parse.parse_qsl(q.split("?", 1)[1]))

def answer(q):
    if q.startswith("zone?"):
        teams = ZONES_FAKE.get(qs(q)["name"])
        return {"data": [{"team_name": t} for t in teams]} if teams else {"data": None}
    if q.startswith("team?"):
        tm = qs(q)["name"]
        if tm in EMPTY_TEAMS:
            return {"data": None}
        roster = [{"game_id": f"{tm}p{i + 1}", "pos": f"{tm}-{POS[i]}"} for i in range(6)]
        roster.append({"game_id": f"{tm}coach", "pos": "教练"})
        return {"data": roster}
    if q.startswith("progamer?"):
        gid = qs(q)["game_id"]
        if gid.endswith("coach") or gid == "WBGp6":
            return {"data": {"accountList": []}}
        return {"data": {"accountList": [{"summonerName": f"{gid}#KR1", "regionName": "韩服", "tier": "王者 - 1000",
                                          "yearPlay": 50, "lastGameTime": NOW_MS}]}}
    raise AssertionError("未知 URL " + q)

class Resp:
    def __init__(self, obj): self.b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    def read(self): return self.b

def fake_urlopen(req, timeout=None):
    q = urllib.parse.unquote(req.full_url.replace(BASE_URL, ""))
    kind = q.split("?", 1)[0]
    p = qs(q)
    z = p.get("name") if kind == "zone" else TEAM_ZONE.get(p.get("name") if kind == "team" else p.get("team"))
    with LOCK:
        ST["calls"][kind] += 1; ST["infl"][kind] += 1
        ST["peak"][kind] = max(ST["peak"][kind], ST["infl"][kind])
        ST["inz"][z] = ST["inz"].get(z, 0) + 1
        ST["peakz"] = max(ST["peakz"], sum(1 for v in ST["inz"].values() if v > 0))
        if kind != "zone":
            ST["inz_t"][z] = ST["inz_t"].get(z, 0) + 1
            live = sorted(k for k, v in ST["inz_t"].items() if v > 0)
            ST["peakz_t"] = max(ST["peakz_t"], len(live))
            if len(live) > 1:
                ST["zt_pairs"].add(tuple(live))
    try:
        _real_sleep(LAT)
        if any(f in q for f in FAIL_URLS):
            raise OSError("boom")
        return Resp(answer(q))
    finally:
        with LOCK:
            ST["infl"][kind] -= 1
            ST["inz"][z] -= 1
            if kind != "zone":
                ST["inz_t"][z] -= 1

NET = {"n": 0}
class NoNet:
    def __init__(self, *a, **k):
        NET["n"] += 1
        raise AssertionError("測試打到真實網路：http.client.HTTPSConnection(%s)" % (a[0] if a else "?"))

# 對外入口：兩個模組共用同一個 urllib.request／http.client／time 模組物件 ⇒ 接管一次、兩版都吃到
M.urllib.request.urlopen = fake_urlopen
M.http.client.HTTPSConnection = NoNet
M.time.sleep = lambda s: None
for mod, tag in ((M, "new"), (O, "old")):
    assert hasattr(mod, "KEEPALIVE") and hasattr(mod, "PG_CACHE_ON"), f"{tag} 版旗標改名了，接管方式要重寫"
    mod.KEEPALIVE = False
    mod.PG_CACHE_ON = False
    mod.ROSTER_OUT = os.path.join(TMP, f"roster_{tag}.json")
    mod.DISOWNED = os.path.join(TMP, f"disowned_{tag}.json")        # 不存在＝空名單
    mod.ACCOUNTS = mod.OUT = os.path.join(TMP, f"acc_{tag}.json")

def leaks(mod):
    """模組層還指著真實 repo 的檔案路徑常數（＝沒接管到的出入口）"""
    return {k: v for k, v in vars(mod).items()
            if isinstance(v, str) and v.endswith((".json", ".txt", ".csv")) and os.path.isabs(v) and not v.startswith(TMP)}

def run_pull(mod, zone_par=True, team_jobs=4, jobs=3, fail=(), timeout=60):
    mod.TEAM_JOBS = team_jobs; mod.JOBS = jobs
    if hasattr(mod, "ZONE_PAR"):
        mod.ZONE_PAR = zone_par
    mod.ROSTER_PLAYERS.clear(); mod.ERR_URLS.clear()
    for k in mod.ERRS: mod.ERRS[k] = 0
    reset_stats(); FAIL_URLS.clear(); FAIL_URLS.update(fail)
    buf = io.StringIO(); box = {}
    def body():
        try:
            with contextlib.redirect_stdout(buf):
                t0 = time.time()
                box["r"] = mod.pull()
                box["wall"] = time.time() - t0
        except BaseException as e:          # noqa
            box["e"] = e
    th = threading.Thread(target=body, daemon=True); th.start(); th.join(timeout)
    if th.is_alive():
        check(f"pull() {timeout}s 內收工（zone_par={zone_par} team_jobs={team_jobs} jobs={jobs}）——卡住＝死結", False)
        print(f"\n{OK} 過／{FAIL + 1} 敗（死結，提前結束）"); os._exit(1)
    if "e" in box:
        raise box["e"]
    out, ze = box["r"]
    return dict(out=out, ze=dict(ze), ros=set(mod.ROSTER_PLAYERS), txt=buf.getvalue(), wall=box["wall"],
                errs=dict(mod.ERRS), **{k: (dict(v) if isinstance(v, dict) else v) for k, v in ST.items()})

def order(out):
    return [(z, list(out[z])) for z in out]

ACC0 = [
    {"player": "BLGp1", "team": "BLG", "platform": "kr", "riotId": "BLGp1#KR1", "dpmPuuid": "puuid-blg1"},
    {"player": "X", "team": "BLG", "platform": "kr", "riotId": "gone#KR1", "dpmSeen": datetime.date.today().isoformat()},
    {"player": "Y", "team": "JDG", "platform": "kr", "riotId": "stale#KR1"},
    {"player": "Caps", "team": "G2", "platform": "euw1", "riotId": "caps#EUW"},
]
def run_main(mod, zone_par=True):
    mod.TEAM_JOBS = 4; mod.JOBS = 3
    if hasattr(mod, "ZONE_PAR"):
        mod.ZONE_PAR = zone_par
    mod.ROSTER_PLAYERS.clear(); mod.ERR_URLS.clear()
    for k in mod.ERRS: mod.ERRS[k] = 0
    reset_stats(); FAIL_URLS.clear()
    mod.ACCOUNTS = mod.OUT = os.path.join(TMP, f"acc_main_{mod.__name__}_{zone_par}.json")
    assert not leaks(mod), f"沙盒沒接管到：{leaks(mod)}"
    open(mod.ACCOUNTS, "w", encoding="utf-8").write(json.dumps(ACC0, ensure_ascii=False, indent=1))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mod.main()
    return open(mod.ACCOUNTS, "rb").read(), buf.getvalue()

# ───────────── [0] 隔離 ─────────────
print("[0] 隔離")
_ent = inspect.getsource(M._fetch_once) + inspect.getsource(M._conn)
check("兩條已知對外入口都還在（urlopen／HTTPSConnection；改名＝接管要重寫）",
      all(k in _ent for k in ("urllib.request.urlopen", "http.client.HTTPSConnection")))
check("沒有第三種對外入口", not [w for w in ("requests.", "httpx.", "aiohttp", "socket.create_connection") if w in _ent])
M._drop_conn(); M.KEEPALIVE = True; _n0 = NET["n"]
_r = M.get(BASE_URL + "zone?name=LPL", retry=0)
M.KEEPALIVE = False; M._drop_conn()
check("正控制：keep-alive 那條路會撞上假連線（守得到）", NET["n"] == _n0 + 1 and "_err" in _r, (NET["n"] - _n0, _r))
check("新版模組層沒有指著真實 repo 的檔案路徑", not leaks(M), leaks(M))
check("舊版模組層沒有指著真實 repo 的檔案路徑", not leaks(O), leaks(O))
_sv = M.ROSTER_OUT; M.ROSTER_OUT = REAL[2]
check("正控制：把 ROSTER_OUT 指回真實名冊，leaks() 抓得到", "ROSTER_OUT" in leaks(M))
M.ROSTER_OUT = _sv
check("舊版真的是改動前那版（沒有 ZONE_PAR／_zone_get）", not hasattr(O, "ZONE_PAR") and not hasattr(O, "_zone_get"))

# ───────────── [1] 常數與旗標 ─────────────
print("[1] 常數與旗標")
src = open(SRC, encoding="utf-8").read()
check("ZONE_PAR 預設 True", M.ZONE_PAR is True, M.ZONE_PAR)
check("argv 吃 --zone-seq、docstring 有寫", '"--zone-seq"' in src and "--zone-seq" in (M.__doc__ or ""))
check("zone 請求仍只有一個呼叫點（kind=\"zone\" 恰 1 次）", src.count('kind="zone"') == 1)
check("TEAM_JOBS／JOBS 預設沒被這輪改動（4／3）", M.TEAM_JOBS == 4 and M.JOBS == 3, (M.TEAM_JOBS, M.JOBS))

# ───────────── [2] 等價：並行 == 逐區 == 舊版 == 逐隊 ─────────────
print("[2] 等價")
P1 = run_pull(M, True); P2 = run_pull(M, True)
S1 = run_pull(M, False); S2 = run_pull(M, False)
OL = run_pull(O)
Q1 = run_pull(M, True, team_jobs=1, jobs=1)
for name, R in (("--zone-seq", S1), ("舊版 " + OLDREV, OL), ("TEAM_JOBS=1/JOBS=1", Q1)):
    check(f"out 與 {name} 相等", P1["out"] == R["out"])
    check(f"賽區與戰隊插入順序與 {name} 相等", order(P1["out"]) == order(R["out"]), (order(P1["out"]), order(R["out"])))
    check(f"名冊與 {name} 相等", P1["ros"] == R["ros"], (len(P1["ros"]), len(R["ros"])))
    check(f"請求次數與 {name} 相等（沒多問也沒少問）", P1["calls"] == R["calls"], (P1["calls"], R["calls"]))
    check(f"zone_err 與 {name} 相等（全 0）", P1["ze"] == R["ze"] and not any(P1["ze"].values()), (P1["ze"], R["ze"]))
check("兩趟並行結果相同（沒有競態）", P1["out"] == P2["out"] and order(P1["out"]) == order(P2["out"]))
check("LPL 五隊順序照 zone 回傳", list(P1["out"]["LPL"]) == ["BLG", "JDG", "TES", "WBG", "LNG"], list(P1["out"]["LPL"]))
check("賽區順序照 ZONES（LPL, LCK, LEC, LCP）", list(P1["out"]) == ["LPL", "LCK", "LEC", "LCP"], list(P1["out"]))
_lines_p = [l for l in P1["txt"].splitlines() if l.startswith("  ") and ": " in l and "帳號（" in l or "無資料" in l]
_lines_s = [l for l in S1["txt"].splitlines() if l.startswith("  ") and ": " in l and "帳號（" in l or "無資料" in l]
check("每區小計行的順序與內容（去掉秒數）兩種模式相同",
      [l.split("隊，")[0] for l in _lines_p] == [l.split("隊，")[0] for l in _lines_s] and len(_lines_p) == 9, (_lines_p, _lines_s))
check("並行才印「賽區之間並行…各區小計相加」、恰一行", P1["txt"].count("賽區之間並行（--zone-seq 退回逐區）：各區小計相加") == 1)
check("--zone-seq 不印那行", "賽區之間並行" not in S1["txt"])
check("TEAM_JOBS=1（team_ex 不存在）走逐區、不印那行", "賽區之間並行" not in Q1["txt"])

# ───────────── [3] 並行真的發生（正控制）＋ 上限 ─────────────
print("[3] 並行真的發生＋上限沒變")
check("正控制：新版有「不同賽區的 team／progamer 同時在飛」（≥2 區）", max(P1["peakz_t"], P2["peakz_t"]) >= 2,
      (P1["peakz_t"], P2["peakz_t"]))
check("正控制：新版的 zone 請求有重疊（≥2 個同時在飛）", max(P1["peak"]["zone"], P2["peak"]["zone"]) >= 2, (P1["peak"], P2["peak"]))
check("負控制：--zone-seq 任何時刻只有 1 區在飛（含 zone 請求）", S1["peakz"] == 1 and S2["peakz"] == 1, (S1["peakz"], S2["peakz"]))
check("鑑別力：改動前那版任何時刻也只有 1 區在飛（＝上面那條正控制在舊版會紅）", OL["peakz"] == 1 and OL["peakz_t"] == 1,
      (OL["peakz"], OL["peakz_t"]))
check("上限：新版 team 同時在飛 ≤ TEAM_JOBS(4)", max(P1["peak"]["team"], P2["peak"]["team"]) <= 4, (P1["peak"], P2["peak"]))
check("上限：新版 progamer 同時在飛 ≤ TEAM_JOBS×JOBS(12)", max(P1["peak"]["progamer"], P2["peak"]["progamer"]) <= 12)
check("上限：新版 zone 請求同時在飛 ≤ TEAM_JOBS(4)（走同一個隊池）", max(P1["peak"]["zone"], P2["peak"]["zone"]) <= 4)
check("負控制：TEAM_JOBS=1/JOBS=1 時 team／progamer 都恰 1 條", Q1["peak"]["team"] == 1 and Q1["peak"]["progamer"] == 1, Q1["peak"])
_wp = min(P1["wall"], P2["wall"]); _ws = min(S1["wall"], S2["wall"])
check("牆鐘（相對值，只當輔助）：並行 < 0.85 × 逐區", _wp < 0.85 * _ws, (round(_wp, 3), round(_ws, 3)))

# ───────────── [4] zone_err 歸屬：多區同時失敗 ─────────────
print("[4] zone_err 歸屬")
FAILS = {"team?name=JDG", "game_id=T1p2", "game_id=CFOp3", "zone?name=LEC"}
PF = run_pull(M, True, fail=FAILS)
SF = run_pull(M, False, fail=FAILS)
OF = run_pull(O, fail=FAILS)
exp = {"LPL": 1, "LCK": 1, "LEC": 1, "LCP": 1}
check("並行：zone_err 各區各 1（LPL team／LCK progamer／LCP progamer／LEC zone）",
      all(PF["ze"].get(z) == n for z, n in exp.items()) and sum(PF["ze"].values()) == 4, PF["ze"])
check("並行與 --zone-seq 的 zone_err 相等", PF["ze"] == SF["ze"], (PF["ze"], SF["ze"]))
check("並行與舊版的 zone_err 相等（舊版用 ERRS 前後差）", PF["ze"] == OF["ze"], (PF["ze"], OF["ze"]))
check("ERRS 分類：zone 1／team 1／progamer 2", PF["errs"] == {"zone": 1, "team": 1, "progamer": 2}, PF["errs"])
check("失敗時 out 也與舊版相等", PF["out"] == OF["out"] and order(PF["out"]) == order(OF["out"]))
check("LPL 那行印「請求失敗 1」、LEC 印「無資料（跳過）」",
      "  LPL: 23 帳號（5 隊，" in PF["txt"] and "，請求失敗 1）" in PF["txt"] and "  LEC: 無資料（跳過）" in PF["txt"], PF["txt"])
check("失敗的請求在失敗時真的跟別區同時在飛（不然歸屬測不到並行）", PF["peakz_t"] >= 2, PF["peakz_t"])
# 突變：選手池的工作不標賽區 ⇒ progamer 的失敗記不到區上 ⇒ 上面那條要紅（證明它靠的是 _TL.zone，不是巧合）
_orig = M._player_in_zone
M._player_in_zone = lambda z, tm, g, now: M._player_accounts(tm, g, now)
MF = run_pull(M, True, fail=FAILS)
M._player_in_zone = _orig
check("突變（不標賽區）：LCK／LCP 的 progamer 失敗記不到 ⇒ zone_err 跟正確值不同",
      MF["ze"].get("LCK", 0) == 0 and MF["ze"].get("LCP", 0) == 0 and MF["errs"]["progamer"] == 2, (MF["ze"], MF["errs"]))
_PF2 = run_pull(M, True, fail=FAILS)
check("突變還原後恢復正確", _PF2["ze"] == PF["ze"], _PF2["ze"])

# ───────────── [5] 不死結（小池子）─────────────
print("[5] 不死結")
for tj, j in ((2, 1), (4, 1), (2, 3)):
    R = run_pull(M, True, team_jobs=tj, jobs=j, timeout=30)
    check(f"TEAM_JOBS={tj}/JOBS={j}：收工且結果與逐隊相等", R["out"] == Q1["out"] and order(R["out"]) == order(Q1["out"]))

# ───────────── [6] main()：帳號檔 byte 全等 ─────────────
print("[6] main() 帳號檔")
wp, tp = run_main(M, True)
ws, ts = run_main(M, False)
wo, to = run_main(O)
check("並行 vs --zone-seq：帳號檔 byte 相同", wp == ws)
check("並行 vs 舊版：帳號檔 byte 相同", wp == wo)
check("三趟都真的寫了（不是三個都沒寫）", all(json.dumps(ACC0, ensure_ascii=False, indent=1).encode("utf-8") != w for w in (wp, ws, wo)))
check("摘要行相同", [l for l in tp.splitlines() if l.startswith("OBGG 帳號更新")] == [l for l in to.splitlines() if l.startswith("OBGG 帳號更新")],
      (tp[-300:], to[-300:]))
check("名冊寫到暫存目錄", os.path.exists(M.ROSTER_OUT) and os.path.exists(O.ROSTER_OUT))

# ───────────── [7] 收尾：真實檔案沒動、沒打網路 ─────────────
print("[7] 真實檔案")
check("整支沒有任何真實 TLS 握手（兩版 CONN_NEW 都 0）", M.CONN_NEW[0] == 0 and O.CONN_NEW[0] == 0, (M.CONN_NEW, O.CONN_NEW))
check("真實帳號檔／.bak／名冊／progamer 快取／歸屬名單的大小與 mtime 都沒動", snap() == REAL0, {p: (REAL0[p], snap()[p]) for p in REAL if REAL0[p] != snap()[p]})
_t = REAL[0]
check("正控制：snap() 對真實檔案的變化看得到（比對的是 mtime_ns，不是恆等）",
      REAL0[_t] is not None and REAL0[_t] != (REAL0[_t][0], REAL0[_t][1] + 1))

time.sleep = _real_sleep
print(f"\n{OK} 過／{FAIL} 敗")
sys.exit(1 if FAIL else 0)
