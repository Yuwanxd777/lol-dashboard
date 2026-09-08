# -*- coding: utf-8 -*-
"""fetch_obgg_accounts 的「同賽區戰隊並行（TEAM_JOBS）＋請求失敗計數／安全門 2」離線測試（不打網路）。
假 OBGG：把 urllib.request.urlopen 換成本地假伺服器（真的 get() 仍在跑，重試／計數走真碼），time.sleep 換成 no-op。
用法：python scripts/fetch_obgg_teampar_test.py
"""
import os, sys, io, re, json, time, threading, tempfile, inspect, datetime, contextlib, importlib.util, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SRC = os.path.join(HERE, "fetch_obgg_accounts.py")
spec = importlib.util.spec_from_file_location("foa", SRC)
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)   # 模組層會包 sys.stdout，這裡不再包

OK = FAIL = 0
def check(name, cond, info=""):
    global OK, FAIL
    if cond: OK += 1; print(f"  ✓ {name}")
    else: FAIL += 1; print(f"  ✗ {name}  {info}")

# ───────────── 假 OBGG ─────────────
# LPL 5 隊、LCK 4 隊（OBGG 主導，各要 ≥20 帳號過第一道安全門）；LEC 2 隊（dpm 主導，只登記名冊）；LCP 2 隊（union，其中 PSG 名冊空）。
ZONES_FAKE = {"LPL": ["BLG", "JDG", "TES", "WBG", "LNG"], "LCK": ["T1", "GEN", "HLE", "KT"], "LEC": ["G2", "FNC"], "LCP": ["CFO", "PSG"]}
EMPTY_TEAMS = {"PSG"}
POS = ["上", "野", "中", "下", "辅", "辅"]
NOW_MS = time.time() * 1000
_real_sleep = time.sleep
LOCK = threading.Lock()
INFL = {"zone": 0, "team": 0, "progamer": 0}
PEAK = {"zone": 0, "team": 0, "progamer": 0}
CALLS = {"zone": 0, "team": 0, "progamer": 0}
FAIL_URLS = set()     # 解碼後的查詢字串含這些子字串 → urlopen 丟例外（每次都丟，讓重試用盡）

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
        roster.append({"game_id": f"{tm}coach", "pos": "教练"})      # 不算五路，但 progamer 照舊會問（跟真 OBGG 一樣）
        return {"data": roster}
    if q.startswith("progamer?"):
        gid = qs(q)["game_id"]
        if gid.endswith("coach") or gid == "WBGp6":                 # 沒帳號
            return {"data": {"accountList": []}}
        if gid == "TESp3":                                          # 只有峡谷之巅 → 濾掉
            return {"data": {"accountList": [{"summonerName": "x#KR1", "regionName": "峡谷之巅", "tier": "王者 - 1", "yearPlay": 9, "lastGameTime": NOW_MS}]}}
        return {"data": {"accountList": [{"summonerName": f"{gid}#KR1", "regionName": "韩服", "tier": "王者 - 1000", "yearPlay": 50, "lastGameTime": NOW_MS}]}}
    raise AssertionError("未知 URL " + q)

class Resp:
    def __init__(self, obj): self.b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    def read(self): return self.b

def fake_urlopen(req, timeout=None):
    q = urllib.parse.unquote(req.full_url.replace(M.BASE, ""))
    kind = q.split("?", 1)[0]
    with LOCK:
        INFL[kind] += 1; CALLS[kind] += 1; PEAK[kind] = max(PEAK[kind], INFL[kind])
    try:
        _real_sleep(0.02)
        if any(f in q for f in FAIL_URLS):
            raise OSError("boom")
        return Resp(answer(q))
    finally:
        with LOCK:
            INFL[kind] -= 1

M.urllib.request.urlopen = fake_urlopen
# ⚠ 2026-09-07（精進迴圈 #52）：模組後來多了 keep-alive 直連——KEEPALIVE=True 時 _fetch_once 走
#   http.client.HTTPSConnection，**完全繞過 urlopen**。所以這支宣稱「不打網路」的測試從那天起
#   靜默地打起真的 OBGG：卡在 SSL read，300 秒連第一行都印不出來（用 faulthandler 抓堆疊才看見）。
#   隔離要接管「每一個對外入口」，不是只接管當初寫測試時的那一個：
#     ① 把 KEEPALIVE 關掉 ⇒ 請求走假 urlopen 那條
#     ② HTTPSConnection 換成會炸的 stub ⇒ 哪天又多一條路、或旗標改名，測試當場紅而不是連上網
assert hasattr(M, "KEEPALIVE"), "fetch_obgg_accounts 沒有 KEEPALIVE 旗標了：對外入口改過，接管方式要重寫"
M.KEEPALIVE = False
BASE_URL = M.BASE
NET = {"n": 0}


class NoNet:
    def __init__(self, *a, **k):
        NET["n"] += 1
        raise AssertionError("測試打到真實網路：http.client.HTTPSConnection(%s)" % (a[0] if a else "?"))


M.http.client.HTTPSConnection = NoNet
M.time.sleep = lambda s: None          # 0.15／1.5 秒的睡都跳過（假伺服器自己用 _real_sleep 0.02s 製造重疊）

def reset(team_jobs, jobs, fail=()):
    M.TEAM_JOBS = team_jobs; M.JOBS = jobs
    M.ROSTER_PLAYERS.clear(); M.ERR_URLS.clear()
    for k in M.ERRS: M.ERRS[k] = 0
    for k in INFL: INFL[k] = 0; PEAK[k] = 0; CALLS[k] = 0
    FAIL_URLS.clear(); FAIL_URLS.update(fail)

def run_pull(team_jobs, jobs, fail=()):
    reset(team_jobs, jobs, fail)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out, zone_err = M.pull()
    return out, zone_err, set(M.ROSTER_PLAYERS), buf.getvalue()

TODAY = datetime.date.today().isoformat()
ACC0 = [
    {"player": "BLGp1", "team": "BLG", "platform": "kr", "riotId": "BLGp1#KR1", "dpmPuuid": "puuid-blg1"},   # OBGG 有列 → 重建、沿用 dpmPuuid
    {"player": "X", "team": "BLG", "platform": "kr", "riotId": "gone#KR1", "dpmSeen": TODAY},               # 不在清單、dpm 今天確認 → 暫留
    {"player": "Y", "team": "JDG", "platform": "kr", "riotId": "stale#KR1"},                                 # 不在清單、沒 dpmSeen → 刪
    {"player": "Caps", "team": "G2", "platform": "euw1", "riotId": "caps#EUW"},                              # dpm 主導 → 保留
    {"player": "Z", "team": "NOBODY", "platform": "kr", "riotId": "nobody#KR1"},                             # 無法分類 → 保留
]
TMP = tempfile.mkdtemp(prefix="obgg_teampar_")
M.ROSTER_OUT = os.path.join(TMP, "obgg_roster.json")
M.DISOWNED = os.path.join(TMP, "soloq_disowned.json")   # #67 新增的證據來源（歸屬剔除名單）也要接管；不存在＝空名單
# ⚠ 2026-09-07（#52）：模組有兩個路徑常數——ACCOUNTS（讀、判斷要不要留 .bak）與 **OUT（真正寫出的目標，
#   --out= 旁路後來加的）**。這支原本只接管 ACCOUNTS ⇒ main() 把假帳號寫進**真實的
#   scripts/soloq_accounts.json**（12507 行變 162 行，本輪跑測試時真的發生了，靠 git checkout 還原）。
#   接管要涵蓋「每一個出口」，下面的 leaks() 會在每次 main() 前後把這件事變成會翻紅的檢查。
REAL_ACC = os.path.join(M.HERE, "soloq_accounts.json")
REAL_MT = os.stat(REAL_ACC).st_mtime
REAL_BAK = REAL_ACC + ".bak"
REAL_BAK_MT = os.stat(REAL_BAK).st_mtime if os.path.exists(REAL_BAK) else 0
M.ACCOUNTS = M.OUT = os.path.join(TMP, "acc_init.json")


def leaks():
    """模組層還指著真實 repo 的檔案路徑常數（＝沒接管到的出入口）"""
    return {k: v for k, v in vars(M).items()
            if isinstance(v, str) and v.endswith((".json", ".txt", ".csv"))
            and os.path.isabs(v) and not v.startswith(TMP)}

def run_main(team_jobs, jobs, fail=()):
    """用暫存帳號檔跑 main()；回 (寫出的帳號檔 bytes 或 None＝沒寫, stdout)。"""
    reset(team_jobs, jobs, fail)
    M.ACCOUNTS = M.OUT = os.path.join(TMP, f"acc_{team_jobs}_{jobs}_{len(fail)}.json")
    assert not leaks(), f"沙盒沒接管到：{leaks()}"
    before = json.dumps(ACC0, ensure_ascii=False, indent=1).encode("utf-8")
    open(M.ACCOUNTS, "wb").write(before)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        M.main()
    after = open(M.ACCOUNTS, "rb").read()
    return (None if after == before else after), buf.getvalue()

# ───────────── [0] 隔離：對外入口全被接管（這支不准打真實網路）─────────────
print("[0] 隔離：對外入口")
check("KEEPALIVE 已關（開著的話 _fetch_once 會走 http.client 直連、繞過假 urlopen）", M.KEEPALIVE is False)
_ent = inspect.getsource(M._fetch_once) + inspect.getsource(M._conn)
check("兩條已知入口都還在（改名了就代表接管要重寫）",
      all(k in _ent for k in ("urllib.request.urlopen", "http.client.HTTPSConnection")))
_other = [w for w in ("requests.", "httpx.", "aiohttp", "socket.create_connection",
                      "http.client.HTTPConnection(") if w in _ent]
check("沒有第三種對外入口（新增了就要一起接管）", not _other, _other)
# 正控制：把 keep-alive 打開，_fetch_once 就該撞上 NoNet ⇒ 證明 stub 真的守在那條路上，
# 不是「反正沒人走所以恆綠」（把來源清空不算隔離，見 CLAUDE.md 2026-09-07 那條）。
M._drop_conn()
M.KEEPALIVE = True
_n0 = NET["n"]
_r = M.get(BASE_URL + "zone?name=LPL", retry=0)
M.KEEPALIVE = False
M._drop_conn()
check("正控制：keep-alive 那條路確實會撞上假連線（守得到）",
      NET["n"] == _n0 + 1 and isinstance(_r, dict) and "_err" in _r, (NET["n"] - _n0, _r))
check("模組層沒有指向真實 repo 的檔案路徑（ACCOUNTS／OUT／ROSTER_OUT 都在暫存目錄）", not leaks(), leaks())
_sv_out = M.OUT
M.OUT = REAL_ACC
check("正控制：把 OUT 指回真實帳號檔，leaks() 抓得到（不是恆綠）", "OUT" in leaks())
M.OUT = _sv_out

# ───────────── [1] 常數與簽名 ─────────────
print("[1] 常數與簽名")
check("TEAM_JOBS 預設 2", M.TEAM_JOBS == 2, M.TEAM_JOBS)
check("JOBS 仍是 3", M.JOBS == 3, M.JOBS)
check("ERR_ABORT == 3", M.ERR_ABORT == 3, M.ERR_ABORT)
check("ERRS 三類", set(M.ERRS) == {"zone", "team", "progamer"}, M.ERRS)
check("get() 多了 kind 參數（預設 None，舊呼叫法不變）", inspect.signature(M.get).parameters["kind"].default is None)
src = open(SRC, encoding="utf-8").read()
check("_team_pull 的程式碼不碰 out[（註解不算）", not any("out[" in re.sub(r"#.*", "", l) for l in inspect.getsource(M._team_pull).splitlines()))
# #38 把賽區迴圈從 pull() 搬到 _pull_zones()（pull 現在只負責建／收兩個執行緒池），
# 合併仍在主執行緒，只是換了個函式 ⇒ 這條要看兩支的原始碼合起來，不然是在測「函式叫什麼名字」。
_pullsrc = inspect.getsource(M.pull) + inspect.getsource(M._pull_zones)
check("pull()／_pull_zones() 在主執行緒合併結果", "for tm, ok, ps in results:" in _pullsrc)
check("argv 吃 --team-jobs=", '"--team-jobs="' in src)
check("zone／team／progamer 三種請求都標了 kind", src.count('kind="zone"') == 1 and src.count('kind="team"') == 1 and src.count('kind="progamer"') == 1)

# ───────────── [2] 等價：並行 == 逐隊 ─────────────
print("[2] 等價：TEAM_JOBS=2/JOBS=3 的結果要跟 TEAM_JOBS=1/JOBS=1 一模一樣")
out1, ze1, ros1, txt1 = run_pull(1, 1)
peak1 = dict(PEAK); calls1 = dict(CALLS)
out2, ze2, ros2, txt2 = run_pull(2, 3)
peak2 = dict(PEAK); calls2 = dict(CALLS)
check("out 相等（含每個 gid 的帳號清單）", out1 == out2)
check("每一區的戰隊插入順序相等", all(list(out1[z]) == list(out2[z]) for z in out1) and list(out1) == list(out2),
      {z: (list(out1[z]), list(out2[z])) for z in out1})
check("名冊相等", ros1 == ros2, (len(ros1), len(ros2)))
check("兩種模式 zone_err 全 0", not any(ze1.values()) and not any(ze2.values()), (ze1, ze2))
check("請求次數相等（並行沒有多問也沒有少問）", calls1 == calls2, (calls1, calls2))
check("LPL 五隊順序照 zone 回傳", list(out2["LPL"]) == ["BLG", "JDG", "TES", "WBG", "LNG"], list(out2["LPL"]))
check("LPL 28 帳號（TESp3 峡谷之巅、WBGp6 無帳號、教練都不算）", sum(len(v) for v in out2["LPL"].values()) == 28,
      {t: len(v) for t, v in out2["LPL"].items()})
check("LCK 24 帳號", sum(len(v) for v in out2["LCK"].values()) == 24)
check("LEC（dpm 主導）兩隊都是空 dict、沒問 progamer", out2["LEC"] == {"G2": {}, "FNC": {}})
check("LCP：CFO 6 帳號、PSG 名冊空 → 不在 out", list(out2["LCP"]) == ["CFO"] and len(out2["LCP"]["CFO"]) == 6, out2.get("LCP"))
check("沒資料的賽區不在 out", set(out2) == {"LPL", "LCK", "LEC", "LCP"}, set(out2))
check("名冊 12 隊 × 6 位 = 72（含 dpm 主導賽區；PSG 名冊空不算）", len(ros2) == 72, len(ros2))
check("每區印「N 帳號（M 隊，…s）」", re.search(r"  LPL: 28 帳號（5 隊，[\d.]+s）", txt2) is not None, txt2)
check("失敗 0 時不印「請求失敗」", "請求失敗" not in txt2)

# ───────────── [3] 並行真的發生（正控制）＋ 負控制 ─────────────
print("[3] 並行真的發生")
check("正控制：TEAM_JOBS=2 → team 請求同時在飛 ≥2", peak2["team"] >= 2, peak2)
check("正控制：TEAM_JOBS=2/JOBS=3 → progamer 同時在飛 ≥4（跨隊）", peak2["progamer"] >= 4, peak2)
check("負控制：TEAM_JOBS=1 → team 同時在飛 ==1", peak1["team"] == 1, peak1)
check("負控制：TEAM_JOBS=1/JOBS=1 → progamer 同時在飛 ==1", peak1["progamer"] == 1, peak1)
check("上限：progamer 同時在飛 ≤ TEAM_JOBS×JOBS＝6", peak2["progamer"] <= 6, peak2)
_, _, _, _ = run_pull(1, 3)
check("舊行為（TEAM_JOBS=1/JOBS=3）：progamer 同時在飛 ≤3", PEAK["progamer"] <= 3 and PEAK["team"] == 1, dict(PEAK))

# ───────────── [4] 失敗計數 ─────────────
print("[4] 請求失敗計數（只算重試用盡的最終失敗）")
out, ze, _, txt = run_pull(2, 3, fail={"team?name=JDG"})
check("team 失敗 1 次（重試 3 趟只算 1）", M.ERRS == {"zone": 0, "team": 1, "progamer": 0}, M.ERRS)
check("假伺服器真的被問了 3 趟（retry=2）", CALLS["team"] == 13 + 2, CALLS)
check("JDG 從 LPL 消失、其餘照舊", "JDG" not in out["LPL"] and list(out["LPL"]) == ["BLG", "TES", "WBG", "LNG"], list(out["LPL"]))
check("zone_err 記在 LPL", ze["LPL"] == 1 and ze["LCK"] == 0, ze)
check("LPL 那行印「請求失敗 1」", re.search(r"  LPL: 22 帳號（5 隊，[\d.]+s，請求失敗 1）", txt) is not None, txt)
check("ERR_URLS 留了那條 URL", len(M.ERR_URLS) == 1 and "team?name=JDG" in M.ERR_URLS[0], M.ERR_URLS)
out, ze, _, txt = run_pull(2, 3, fail={"game_id=TESp1", "game_id=CFOp2"})
check("progamer 失敗 2 次（LPL 1、LCP 1）", M.ERRS["progamer"] == 2 and ze["LPL"] == 1 and ze["LCP"] == 1, (M.ERRS, ze))
check("失敗的人消失、隊還在", "TESp1" not in out["LPL"]["TES"] and len(out["LPL"]["TES"]) == 4 and len(out["LCP"]["CFO"]) == 5)
out, ze, _, txt = run_pull(2, 3, fail={"zone?name=LCK"})
check("zone 失敗：LCK 無資料（跳過）、zone_err 記 1", "LCK" not in out and ze["LCK"] == 1 and M.ERRS["zone"] == 1, (ze, M.ERRS))

# ───────────── [5] main()：安全門 2 ＋ 兩種模式寫出一模一樣的帳號檔 ─────────────
print("[5] main()：安全門 2 與帳號檔等價")
w1, t1 = run_main(1, 1)
w2, t2 = run_main(2, 3)
check("乾淨跑：兩種模式都寫了帳號檔", w1 is not None and w2 is not None)
check("兩種模式寫出的帳號檔 byte 相同", w1 == w2)
final = json.loads(w2.decode("utf-8")) if w2 else []
rids = [e["riotId"] for e in final]
check("筆數 58 OBGG（LPL 28＋LCK 24＋LCP 6）＋ 暫留 gone ＋ caps ＋ nobody ＝ 61", len(final) == 61, len(final))
check("stale#KR1 被刪、gone#KR1 暫留、caps／nobody 保留", "stale#KR1" not in rids and {"gone#KR1", "caps#EUW", "nobody#KR1"} <= set(rids))
check("BLGp1 沿用 dpmPuuid", any(e["riotId"] == "BLGp1#KR1" and e.get("dpmPuuid") == "puuid-blg1" for e in final))
check("摘要行：5 → 61、刪 1、暫留 1", "OBGG 帳號更新：5 → 61（LPL/LCK 刪 1 個近兩月未列、dpm 近 3 天確認過暫留 1 個" in t2, t2)
check("乾淨跑沒有 ⚠", "⚠" not in t2)
w, t = run_main(2, 3, fail={"game_id=TESp1"})
check("LPL 失敗 1 次（<3）→ 照寫，帳號少 1（60）", w is not None and len(json.loads(w.decode("utf-8"))) == 60, (w is not None, t))
check("印 ⚠ 失敗 1 次＋URL", "⚠ OBGG 請求最終失敗 1 次（zone 0／team 0／progamer 1）：progamer?team=TES&game_id=TESp1" in t, t)
w, t = run_main(2, 3, fail={"game_id=TESp1", "game_id=TESp2", "game_id=BLGp1"})
check("LPL 失敗 3 次（≥3）→ 不動帳號檔", w is None, t)
check("是安全門 2 擋的（不是 <20 那道：LPL 仍有 25 帳號）", "✗ LPL/LCK 的請求失敗 3 次（≥3）" in t and "只抓到" not in t, t)
check("擋下時也沒寫 .bak", not os.path.exists(M.ACCOUNTS + ".bak"))
w, t = run_main(2, 3, fail={"game_id=CFOp1", "game_id=CFOp2", "game_id=CFOp3"})
check("失敗 3 次但全在 LCP（非 OBGG 主導）→ 照寫，只印 ⚠", w is not None and "⚠ OBGG 請求最終失敗 3 次" in t and "✗" not in t, t)
w, t = run_main(2, 3, fail={"team?name=T1", "team?name=GEN", "team?name=HLE"})
check("LCK 三隊 team 請求全失敗 → 只剩 6 帳號，<20 那道門先擋（兩道門都在）", w is None and "✗ LCK 只抓到 6 帳號" in t, t)
w, t = run_main(2, 3, fail={"team?name=BLG", "team?name=JDG", "team?name=TES"})
check("LPL 三隊 team 失敗（剩 11 帳號 <20）→ 第一道門擋、且 ⚠ 印在門前（看得出是 team 掛 3 次）", w is None and "✗ LPL 只抓到 11 帳號" in t and "⚠ OBGG 請求最終失敗 3 次（zone 0／team 3／progamer 0）" in t and t.index("⚠") < t.index("✗ LPL"), t)

# ───────────── [6] 負控制：把新邏輯關掉（--team-jobs=1）請求路徑回到舊行為 ─────────────
print("[6] 負控制")
out, ze, _, txt = run_pull(1, 3)
check("TEAM_JOBS=1 也回 (out, zone_err) 兩件、結果同並行", out == out2 and not any(ze.values()))

check("整支跑完沒有任何真實 TLS 握手（CONN_NEW 仍是 0）", M.CONN_NEW[0] == 0, M.CONN_NEW[0])
check("整支跑完沒有碰真實的 scripts/soloq_accounts.json（mtime 沒變）",
      os.stat(REAL_ACC).st_mtime == REAL_MT)
check("整支跑完也沒動真實的 .bak（main() 寫回正本時才會留備份）",
      (os.stat(REAL_BAK).st_mtime if os.path.exists(REAL_BAK) else 0) == REAL_BAK_MT)

time.sleep = _real_sleep
print(f"\n{OK} 過／{FAIL} 敗")
sys.exit(1 if FAIL else 0)
