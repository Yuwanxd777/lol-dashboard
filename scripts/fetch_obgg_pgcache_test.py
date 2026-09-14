# -*- coding: utf-8 -*-
"""fetch_obgg_accounts 的「progamer 逐人結果快取、到期日錯開、每班只重抓 1/PG_CYCLE」離線測試（不打網路）。
（2026-09-14 線 3 精進迴圈 #111）
沙盒：urlopen 換成假 OBGG、KEEPALIVE 關掉、HTTPSConnection 換成會炸的 stub、time.sleep no-op、
**time.time 換成假時鐘**（快取到期看的是「現在 − at」，要逼出「下一班／再下一班」不能等日曆——DAILY #109 的通則）。
ACCOUNTS／OUT／ROSTER_OUT／DISOWNED 全指到暫存目錄；快取路徑跟著 ROSTER_OUT 的目錄走 ⇒ 自動落在暫存目錄
（leaks() 掃模組層絕對路徑，另配「把 ROSTER_OUT 指回真實檔 ⇒ 快取路徑也回到真實 csv_cache」的正控制證明推導是真的）。
「只有沙盒才有的證據」：快取裡種 riotId ZZPROBE9942#KR1（真 OBGG 不可能回這個）——沿用時它要出現在帳號檔、重抓時要消失。
正控制釘 commit fdbf6371（#111 之前的最後一版）：同一個沙盒連跑兩趟，舊版兩趟都全問、也沒有 pg_cache_path。
用法：python scripts/fetch_obgg_pgcache_test.py
"""
import os, sys, io, json, time, threading, tempfile, hashlib, contextlib, subprocess, importlib.util, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SRC = os.path.join(HERE, "fetch_obgg_accounts.py")
OLDREV = "fdbf6371"     # #111 之前的收工 commit（#93：正控制釘 commit，不寫 HEAD）


_SO = sys.stdout
_STDOUT_KEEP = []


def load(src_path, name):
    spec = importlib.util.spec_from_file_location(name, src_path)
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m; spec.loader.exec_module(m)
    _STDOUT_KEEP.append(sys.stdout)   # 模組層會把 sys.stdout 換成新 wrapper；抓住它（被 GC 會關掉共用的 buffer），再把原本的換回來
    sys.stdout = _SO
    return m


M = load(SRC, "foa_pg")

OK = FAIL = 0
def check(name, cond, info=""):
    global OK, FAIL
    if cond: OK += 1; print(f"  ✓ {name}")
    else: FAIL += 1; print(f"  ✗ {name}  {info}")


# ───────────── 假 OBGG ─────────────
ZONES_FAKE = {"LPL": ["BLG", "JDG", "TES", "WBG", "LNG"], "LCK": ["T1", "GEN", "HLE", "KT"], "LEC": ["G2", "FNC"], "LCP": ["CFO", "PSG"]}
EMPTY_TEAMS = {"PSG"}
POS = ["上", "野", "中", "下", "辅", "辅"]
_real_time = time.time
_real_sleep = time.sleep
NOW0 = _real_time()                  # 假時鐘的起點（秒）
CLOCK = [NOW0]
H = 3600.0
LOCK = threading.Lock()
ASKED = []                           # 這一趟 progamer 問過的 game_id（含重試）
CALLS = {"zone": 0, "team": 0, "progamer": 0}
FAIL_URLS = set()                    # 解碼後查詢字串含這些子字串 → 丟例外（每次都丟，讓重試用盡）
EMPTY_GIDS = set()                   # 這些選手 progamer 回空 accountList（測第三道門）
PROBE = "ZZPROBE9942#KR1"

def qs(q):
    return dict(urllib.parse.parse_qsl(q.split("?", 1)[1]))

def answer(q):
    now_ms = CLOCK[0] * 1000
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
        if gid in EMPTY_GIDS or gid.endswith("coach") or gid == "WBGp6":
            return {"data": {"accountList": []}}
        if gid == "TESp3":
            return {"data": {"accountList": [{"summonerName": "x#KR1", "regionName": "峡谷之巅", "tier": "王者 - 1", "yearPlay": 9, "lastGameTime": now_ms}]}}
        return {"data": {"accountList": [{"summonerName": f"{gid}#KR1", "regionName": "韩服", "tier": "王者 - 1000", "yearPlay": 50, "lastGameTime": now_ms}]}}
    raise AssertionError("未知 URL " + q)

class Resp:
    def __init__(self, obj): self.b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    def read(self): return self.b

def fake_urlopen(req, timeout=None):
    q = urllib.parse.unquote(req.full_url.replace(M.BASE, ""))
    kind = q.split("?", 1)[0]
    with LOCK:
        CALLS[kind] += 1
        if kind == "progamer":
            ASKED.append(qs(q)["game_id"])
    _real_sleep(0.005)
    if any(f in q for f in FAIL_URLS):
        raise OSError("boom")
    return Resp(answer(q))

class NoNet:
    def __init__(self, *a, **k):
        raise AssertionError("測試打到真實網路：http.client.HTTPSConnection(%s)" % (a[0] if a else "?"))


def sandbox(m, tmp):
    assert hasattr(m, "KEEPALIVE"), "沒有 KEEPALIVE 旗標了：對外入口改過，接管方式要重寫"
    m.KEEPALIVE = False
    m.urllib.request.urlopen = fake_urlopen
    m.http.client.HTTPSConnection = NoNet
    m.time.sleep = lambda s: None
    m.time.time = lambda: CLOCK[0]
    m.ACCOUNTS = m.OUT = os.path.join(tmp, "acc.json")
    m.ROSTER_OUT = os.path.join(tmp, "csv_cache", "obgg_roster.json")
    m.DISOWNED = os.path.join(tmp, "csv_cache", "soloq_disowned.json")
    os.makedirs(os.path.join(tmp, "csv_cache"), exist_ok=True)
    return m


TMP = tempfile.mkdtemp(prefix="obgg_pgcache_")
sandbox(M, TMP)
CACHE = M.pg_cache_path()

def leaks(m):
    return {k: v for k, v in vars(m).items()
            if isinstance(v, str) and v.endswith((".json", ".txt", ".csv")) and os.path.isabs(v) and not v.startswith(TMP)}

ACC0 = [
    {"player": "BLGp1", "team": "BLG", "platform": "kr", "riotId": "BLGp1#KR1", "dpmPuuid": "puuid-blg1"},
    {"player": "Caps", "team": "G2", "platform": "euw1", "riotId": "caps#EUW"},
]
REAL = {p: (hashlib.md5(open(p, "rb").read()).hexdigest(), os.stat(p).st_mtime) for p in
        [os.path.join(HERE, "soloq_accounts.json"), os.path.join(ROOT, "csv_cache", "obgg_roster.json"),
         os.path.join(ROOT, "csv_cache", "obgg_progamer_cache.json"), os.path.join(HERE, "soloq_accounts.json.bak")]
        if os.path.exists(p)}


def reset(fail=(), empty=()):
    M.ROSTER_PLAYERS.clear(); M.ERR_URLS.clear()
    for k in M.ERRS: M.ERRS[k] = 0
    for k in CALLS: CALLS[k] = 0
    ASKED.clear(); FAIL_URLS.clear(); FAIL_URLS.update(fail); EMPTY_GIDS.clear(); EMPTY_GIDS.update(empty)

def run_main(fail=(), empty=(), acc=None):
    """跑 main()；回 (帳號檔 bytes 或 None, stdout)。"""
    reset(fail, empty)
    assert not leaks(M), f"沙盒沒接管到：{leaks(M)}"
    open(M.ACCOUNTS, "wb").write(json.dumps(acc if acc is not None else ACC0, ensure_ascii=False, indent=1).encode("utf-8"))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        M.main()
    out = open(M.OUT, "rb").read() if os.path.exists(M.OUT) else None
    return out, buf.getvalue()

def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest() if os.path.exists(p) else ""

def cache():
    return json.load(open(CACHE, encoding="utf-8"))

def rids(b):
    return {a["riotId"] for a in json.loads(b.decode("utf-8"))} if b else set()

ALL_KEYS = [f"{tm}|{tm}p{i + 1}" for z in ("LPL", "LCK", "LCP") for tm in ZONES_FAKE[z] if tm not in EMPTY_TEAMS for i in range(6)] + \
           [f"{tm}|{tm}coach" for z in ("LPL", "LCK", "LCP") for tm in ZONES_FAKE[z] if tm not in EMPTY_TEAMS]
N = len(ALL_KEYS)
SLOT = {s: {k for k in ALL_KEYS if M.pg_slot(k) == s} for s in range(M.PG_CYCLE)}
gid_of = lambda k: k.split("|", 1)[1]


print("[1] 隔離")
check("模組層沒有指向真實 repo 的路徑（ACCOUNTS／OUT／ROSTER_OUT／DISOWNED 都在暫存目錄）", not leaks(M), leaks(M))
check("快取路徑跟著 ROSTER_OUT 的目錄走 ⇒ 在暫存目錄", CACHE.startswith(TMP) and CACHE.endswith("obgg_progamer_cache.json"), CACHE)
_sv = M.ROSTER_OUT; M.ROSTER_OUT = os.path.join(ROOT, "csv_cache", "obgg_roster.json")
check("正控制：ROSTER_OUT 指回真實檔 ⇒ 快取路徑也回到真實 csv_cache（推導不是恆綠）",
      M.pg_cache_path() == os.path.join(ROOT, "csv_cache", "obgg_progamer_cache.json") and "ROSTER_OUT" in leaks(M))
M.ROSTER_OUT = _sv
check("KEEPALIVE 關、HTTPSConnection 是 stub、time.time 是假時鐘", M.KEEPALIVE is False and M.http.client.HTTPSConnection is NoNet and M.time.time() == CLOCK[0])
check(f"預設 PG_CYCLE=3、TTL=30h、PG_CACHE_ON 開", M.PG_CYCLE == 3 and abs(M.pg_ttl_s() - 30 * H) < 1 and M.PG_CACHE_ON is True)
check(f"沙盒 {N} 位選手分成 {M.PG_CYCLE} 個槽、每槽都有人", N == 70 and all(SLOT[s] for s in SLOT), {s: len(SLOT[s]) for s in SLOT})

print("[2] 冷跑：沒有快取 ⇒ 全問、寫出快取、時間戳錯開")
CLOCK[0] = NOW0
b_cold, txt = run_main()
check(f"progamer 問了 {N} 位（每人一次）", sorted(ASKED) == sorted(gid_of(k) for k in ALL_KEYS), (len(ASKED), CALLS))
check("日誌印「冷跑：沒有快取，全問」與「新選手 70」", "冷跑" in txt and f"新選手 {N}" in txt, txt)
check("快取檔寫出、版本 v==PG_VER、70 筆", os.path.exists(CACHE) and cache()["v"] == M.PG_VER and len(cache()["players"]) == N)
ats = {k: cache()["players"][k]["at"] for k in ALL_KEYS}
check("時間戳＝現在 − slot×12h（三種值各有人）",
      all(abs(ats[k] - (NOW0 - M.pg_slot(k) * 12 * H)) < 1 for k in ALL_KEYS) and len({round(v) for v in ats.values()}) == 3)
check("帳號檔含 BLGp1#KR1、不含 coach／WBGp6／峡谷之巅", "BLGp1#KR1" in rids(b_cold) and not any(r.startswith(("BLGcoach", "WBGp6", "x#")) for r in rids(b_cold)))
check("日誌「下一班預計重抓」＝槽 2 的人數", f"下一班預計重抓 {len(SLOT[2])}" in txt, txt)
check("寫出的筆數印出來", f"progamer 快取寫出 {N} 筆" in txt)

print("[3] 同一班再跑一次：全部沿用、零 progamer 請求、帳號檔逐位元相同")
b_warm, txt = run_main()
check("progamer 0 次", CALLS["progamer"] == 0, CALLS)
check(f"日誌「沿用 {N}／重抓 0／新選手 0」＋「讀進 {N} 筆」", f"沿用 {N}／重抓 0／新選手 0" in txt and f"讀進 {N} 筆" in txt, txt)
check("帳號檔跟冷跑逐位元相同", b_warm == b_cold)
check("zone／team 請求照舊每班發（9 區都問、13 隊）", CALLS["zone"] == len(M.ZONES) and CALLS["team"] == 13, CALLS)

print("[4]~[6] 三班輪替：每班只重抓一個槽、三班合起來每人恰好一次")
asked_by_shift = {}
for shift, s in ((1, 2), (2, 1), (3, 0)):
    CLOCK[0] = NOW0 + shift * 12 * H
    b, txt = run_main()
    asked_by_shift[shift] = set(ASKED)
    check(f"第 {shift} 班（+{shift * 12}h）重抓的＝槽 {s}（{len(SLOT[s])} 位）", set(ASKED) == {gid_of(k) for k in SLOT[s]} and len(ASKED) == len(SLOT[s]),
          (len(ASKED), len(SLOT[s])))
    check(f"第 {shift} 班日誌：沿用 {N - len(SLOT[s])}／重抓 {len(SLOT[s])}", f"沿用 {N - len(SLOT[s])}／重抓 {len(SLOT[s])}／新選手 0" in txt, txt)
    c = cache()["players"]
    check(f"第 {shift} 班重抓的人時間戳＝這一班、其餘沒動",
          all(abs(c[k]["at"] - CLOCK[0]) < 1 for k in SLOT[s]) and all(abs(c[k]["at"] - ats[k]) < 1 for k in ALL_KEYS if M.pg_slot(k) < s))
    check(f"第 {shift} 班帳號檔跟冷跑相同（內容沒因為快取而變）", b == b_cold)
check("三班合起來每人恰好重抓一次", sum(len(v) for v in asked_by_shift.values()) == N and set().union(*asked_by_shift.values()) == {gid_of(k) for k in ALL_KEYS})
CLOCK[0] = NOW0 + 4 * 12 * H
b, txt = run_main()
check("第 4 班又輪回槽 2（週期 3 班）", set(ASKED) == {gid_of(k) for k in SLOT[2]}, len(ASKED))

print("[7] 只有沙盒才有的證據：快取裡種探針帳號")
def seed(key, at, good=None):
    d = cache(); d["players"][key] = {"at": at, "good": good if good is not None else [{"platform": "kr", "riotId": PROBE}]}
    json.dump(d, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
seed("BLG|BLGp1", CLOCK[0])
b, txt = run_main()
check("沿用（沒到期）：BLGp1 沒被問、探針帳號出現在帳號檔、真帳號 BLGp1#KR1 不在", "BLGp1" not in ASKED and PROBE in rids(b) and "BLGp1#KR1" not in rids(b), sorted(rids(b))[:5])
seed("BLG|BLGp1", CLOCK[0] - 40 * H)
b, txt = run_main()
check("反例（到期）：BLGp1 被重抓、探針消失、真帳號回來", ASKED.count("BLGp1") == 1 and PROBE not in rids(b) and "BLGp1#KR1" in rids(b))
check("重抓後探針在快取裡也被蓋掉", cache()["players"]["BLG|BLGp1"]["good"][0]["riotId"] == "BLGp1#KR1")

print("[8] 請求最終失敗：有舊快取 ⇒ 沿用舊值、時間戳不動；沒快取 ⇒ 照舊回空")
seed("BLG|BLGp2", CLOCK[0] - 40 * H)
at_before = cache()["players"]["BLG|BLGp2"]["at"]
b, txt = run_main(fail=("game_id=BLGp2",))
check("BLGp2 問了 3 次（重試用盡）", ASKED.count("BLGp2") == 3, ASKED.count("BLGp2"))
check("帳號檔用的是舊快取的探針帳號", PROBE in rids(b) and "BLGp2#KR1" not in rids(b))
check("日誌「請求失敗沿用舊值 1」、ERRS progamer 1（未達安全門 2 的 3 次）", "請求失敗沿用舊值 1" in txt and M.ERRS["progamer"] == 1, txt)
check("時間戳沒被更新（下一班還會再試）", abs(cache()["players"]["BLG|BLGp2"]["at"] - at_before) < 1)
d = cache(); del d["players"]["BLG|BLGp2"]; json.dump(d, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
b, txt = run_main(fail=("game_id=BLGp2",))
check("沒快取＋失敗：BLGp2 不在帳號檔、快取也不建它的紀錄（不把失敗當結果存）", "BLGp2#KR1" not in rids(b) and "BLG|BLGp2" not in cache()["players"])
b, txt = run_main()
check("正控制：失敗解除後下一班補回（BLGp2 被問、帳號回來、快取建了紀錄）", ASKED.count("BLGp2") == 1 and "BLGp2#KR1" in rids(b) and "BLG|BLGp2" in cache()["players"])

print("[9] --out= 旁路：讀快取但不寫")
seed("BLG|BLGp3", CLOCK[0] - 40 * H)          # 只有這一位到期 ⇒ 旁路應該恰好問 1 次
m0 = md5(CACHE); M.OUT = os.path.join(TMP, "probe_out.json")
b, txt = run_main()
check("旁路有沿用（progamer 只問到期的那 1 位）", CALLS["progamer"] == 1 and ASKED == ["BLGp3"], (CALLS, ASKED))
check("快取檔 md5 沒變（重抓的結果沒被寫回）、日誌沒有「快取寫出」", md5(CACHE) == m0 and "快取寫出" not in txt)
M.OUT = M.ACCOUNTS

print("[10] --no-pg-cache：不讀不寫＝每班全問")
M.PG_CACHE_ON = False; m0 = md5(CACHE)
b, txt = run_main()
check(f"全問 {N} 次、快取 md5 沒變、日誌沒有 progamer 快取那行", CALLS["progamer"] == N and md5(CACHE) == m0 and "progamer 快取" not in txt, CALLS)
M.PG_CACHE_ON = True

print("[11] 安全門 1（LPL 抓不到）⇒ 不存快取")
m0 = md5(CACHE); CLOCK[0] += 12 * H
b, txt = run_main(fail=("name=LPL&",))
check("✗ 只抓到 0 帳號 ⇒ 帳號檔沒改、快取 md5 沒變", "只抓到 0 帳號" in txt and md5(CACHE) == m0 and json.loads(b.decode("utf-8")) == ACC0)

print("[12] 安全門 3：重抓的人裡「上一版有帳號、這次回空」過半 ⇒ 不動")
CLOCK[0] += 12 * H
ten = [f"{tm}|{tm}p{i + 1}" for tm in ("T1", "BLG") for i in range(5)]   # LCK 5＋LPL 5：兩區各自仍 ≥20 帳號，第一道門不會先擋
d = cache()
for k in ALL_KEYS:
    d["players"][k] = {"at": CLOCK[0] - (40 * H if k in ten else 0), "good": [{"platform": "kr", "riotId": f"{gid_of(k)}#OLD"}]}
json.dump(d, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
m0 = md5(CACHE)
b, txt = run_main(empty={gid_of(k) for k in ten})
check("10 位重抓、10 位回空 ⇒ ✗ OBGG 可能異常、帳號檔沒改、快取沒存", "10 位回來是空的" in txt and "不存 progamer 快取" in txt
      and json.loads(b.decode("utf-8")) == ACC0 and md5(CACHE) == m0, txt)
b, txt = run_main(empty={gid_of(k) for k in ten[:4]})
check("正控制：只有 4/10 回空（<50%）⇒ 照常更新、快取寫出、那 4 位的舊帳號被空值取代", "OBGG 可能異常" not in txt and md5(CACHE) != m0
      and "T1p1#OLD" not in rids(b) and "T1p5#KR1" in rids(b) and cache()["players"]["T1|T1p1"]["good"] == [], txt)

print("[13] 剪枝與版本")
seed("GONE|gone1", CLOCK[0] - 31 * 86400); seed("GONE|gone2", CLOCK[0] - 20 * 86400)
b, txt = run_main()
check("31 天沒重抓的剪掉、20 天的留著", "GONE|gone1" not in cache()["players"] and "GONE|gone2" in cache()["players"])
d = cache(); d["v"] = 0; json.dump(d, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
b, txt = run_main()
check("版本不合 ⇒ 當冷跑（全問）、寫回新版本", CALLS["progamer"] == N and "冷跑" in txt and cache()["v"] == M.PG_VER, CALLS)
b, txt = run_main()
check("接著又是熱跑", CALLS["progamer"] == 0)

print("[14] 舊版正控制（%s）：同一個沙盒兩趟都全問、沒有快取函式" % OLDREV)
old_src = subprocess.run(["git", "show", f"{OLDREV}:scripts/fetch_obgg_accounts.py"], cwd=ROOT, capture_output=True).stdout
if not old_src:
    check("git show 拿得到舊版", False, "git show 失敗")
else:
    op = os.path.join(TMP, "old_foa.py"); open(op, "wb").write(old_src)
    O = sandbox(load(op, "foa_old"), os.path.join(TMP, "old"))
    check("舊版沒有 pg_cache_path／PG_CACHE_ON", not hasattr(O, "pg_cache_path") and not hasattr(O, "PG_CACHE_ON"))
    for i in (1, 2):
        reset()
        open(O.ACCOUNTS, "wb").write(json.dumps(ACC0, ensure_ascii=False).encode("utf-8"))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            O.main()
        check(f"舊版第 {i} 趟 progamer 全問 {N} 次", CALLS["progamer"] == N, CALLS)
    check("舊版沒寫出快取檔", not os.path.exists(os.path.join(TMP, "old", "csv_cache", "obgg_progamer_cache.json")))

print("[15] 真實檔案沒動")
for p, (h, mt) in REAL.items():
    check(f"{os.path.relpath(p, ROOT)} md5 與 mtime 不變", md5(p) == h and os.stat(p).st_mtime == mt)
check("真實 csv_cache 沒被這支測試建出快取檔（沙盒前後一致）",
      (os.path.join(ROOT, "csv_cache", "obgg_progamer_cache.json") in REAL) == os.path.exists(os.path.join(ROOT, "csv_cache", "obgg_progamer_cache.json")))

M.time.time = _real_time; M.time.sleep = _real_sleep
print(f"\n{OK} 過 / {FAIL} 失敗")
sys.exit(1 if FAIL else 0)
