# -*- coding: utf-8 -*-
"""fetch_soloq.py 逐主機分桶節流＋帳號依平台交錯（2026-09-08 精進迴圈 #70）的沙盒測試。

跑法：python scripts/fetch_soloq_region_bucket_test.py
全部在暫存目錄與假 Riot 上進行：urllib.request.urlopen 換成假的（記下每一個請求的主機與順序）、
time.sleep 換成只記錄不睡、HERE／ROOT／ACCOUNTS／OUT 全指到暫存目錄，真實 soloq.js／
soloq_accounts.json／soloq_played.json 的 mtime 前後比對不可變。
正控制：`git show HEAD:scripts/fetch_soloq.py` 拉舊版（全域一個桶）跑同一個情境，證明它真的會睡。
"""
import os, sys, io, json, time, shutil, tempfile, subprocess, importlib.util, urllib.request, urllib.error, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
os.environ["RIOT_API_KEY"] = "RGAPI-sandbox-not-a-real-key"
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

FAILS = []
N = [0]


def check(cond, msg):
    N[0] += 1
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        FAILS.append(msg)


def load_mod(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ── 假 Riot ─────────────────────────────────────────────────────────────────
class FakeResp:
    def __init__(self, code, body):
        self.code, self.body = code, json.dumps(body).encode("utf-8")
        self.headers = {}
    def getcode(self): return self.code
    def read(self, *a): return self.body
    def __enter__(self): return self
    def __exit__(self, *a): return False


class FakeRiot:
    """router(url) → (code, body)。calls 記每個請求的 URL（順序就是送出順序）、conns 記建立過幾條連線。"""
    def __init__(self, router):
        self.router, self.calls, self.conns = router, [], []
    def __call__(self, req, timeout=15):
        url = req.full_url
        self.calls.append(url)
        code, body = self.router(url)
        if code != 200:
            raise urllib.error.HTTPError(url, code, "fake", {}, io.BytesIO(b""))
        return FakeResp(code, body)


# 2026-09-09 #78：新版 riot_get 改走 keep-alive（http.client.HTTPSConnection，見 fetch_soloq._raw_get）
# ⇒ **只換掉 urllib.request.urlopen 已經攔不到它了**（CLAUDE.md 2026-09-07 #52 的同一種漏接：
# 模組後來多的出口沒被點名，沙盒會靜默去打真的 Riot）。所以 patched() 改成：
#   有 _CONN_CLS 的模組（新版）→ 換掉 _CONN_CLS 並清空 _CONNS，同時把 urlopen 換成「一叫就爆」的漏接偵測器；
#   沒有的（git HEAD 舊版，正控制）→ 照舊換 urlopen。
class FakeHTTPResp:
    def __init__(self, code, body, hdrs=None, will_close=False):
        self.status = code
        self.headers = hdrs if hdrs is not None else {}
        self._b = json.dumps(body).encode("utf-8") if body is not None else b""
        self.will_close = will_close
    def read(self, *a):
        return self._b


def conn_cls_for(fake):
    """產生假的 HTTPSConnection 類別：所有請求轉給 fake.router，建立過的連線記進 fake.conns。"""
    class FakeConn(object):
        def __init__(self, host, timeout=15):
            self.host, self.timeout, self.closed, self._url = host, timeout, False, None
            fake.conns.append(self)
        def request(self, method, path, headers=None, body=None):
            if self.closed:
                raise OSError("沙盒：連線已關閉")
            self._url = "https://%s%s" % (self.host, path)
        def getresponse(self):
            fake.calls.append(self._url)
            code, body = fake.router(self._url)
            return FakeHTTPResp(code, body)
        def close(self):
            self.closed = True
    return FakeConn


def _leak(*a, **k):
    raise AssertionError("沙盒漏接：新版 riot_get 不該再走 urllib.request.urlopen")


class SleepLog(list):
    def __call__(self, s):
        self.append(s)


@contextlib.contextmanager
def patched(fake, sleeps, mod=None):
    old_open, old_sleep = urllib.request.urlopen, time.sleep
    keep = mod is not None and hasattr(mod, "_CONN_CLS")
    old_cls = getattr(mod, "_CONN_CLS", None) if keep else None
    urllib.request.urlopen = _leak if keep else fake
    time.sleep = sleeps
    if keep:
        mod._CONN_CLS = conn_cls_for(fake)
        mod._CONNS.clear()
    try:
        yield
    finally:
        urllib.request.urlopen, time.sleep = old_open, old_sleep
        if keep:
            mod._CONN_CLS = old_cls
            mod._CONNS.clear()


def host_of(url):
    return url.split("//", 1)[1].split(".", 1)[0]


REAL_FILES = [os.path.join(HERE, "soloq_accounts.json"), os.path.join(ROOT, "soloq.js"),
              os.path.join(HERE, "soloq_played.json")]
mt_before = [os.path.getmtime(p) if os.path.exists(p) else None for p in REAL_FILES]

NEW = load_mod(os.path.join(HERE, "fetch_soloq.py"), "fetch_soloq_new")

# ── 1. _host_of ─────────────────────────────────────────────────────────────
print("【1】_host_of")
check(NEW._host_of("https://kr.api.riotgames.com/lol/league/v4/entries/by-puuid/abc") == "kr", "kr 主機")
check(NEW._host_of("https://euw1.api.riotgames.com/x") == "euw1", "euw1 主機")
check(NEW._host_of("https://asia.api.riotgames.com/riot/account/v1/accounts/by-riot-id/a/b") == "asia", "asia 叢集（account-v1）自成一桶")
check(NEW._host_of("garbage") == "_", "解析不到 → 全丟同一桶")


# ── 2. 分桶節流：額度 (5,100) ⇒ 每桶 4 次免等（2% 餘裕至少留 1 個名額），第 5 次才等 ──
def quiet_router(url):
    return 200, []


def run_bucket_scenario(mod, label):
    mod._LIMITS = [(5, 100.0)]
    if hasattr(mod, "_BUCKETS"):
        mod._BUCKETS.clear()
    if hasattr(mod, "_req_times"):
        mod._req_times.clear()
    fake, sleeps = FakeRiot(quiet_router), SleepLog()
    with patched(fake, sleeps, mod):
        with contextlib.redirect_stdout(io.StringIO()):
            for host in ("kr", "euw1", "br1", "asia"):
                for _ in range(4):
                    mod.riot_get(f"https://{host}.api.riotgames.com/p")
            n_free = len(sleeps)
            mod.riot_get("https://kr.api.riotgames.com/p")          # kr 第 5 次
            n_after_kr5 = len(sleeps)
            mod.riot_get("https://na1.api.riotgames.com/p")         # 沒用過的桶
            n_after_na = len(sleeps)
    return n_free, n_after_kr5, n_after_na, sleeps, fake.calls


print("【2】分桶節流（新版）")
n_free, n_kr5, n_na, sleeps, calls = run_bucket_scenario(NEW, "新版")
check(n_free == 0, "4 主機各 4 次（共 16 次）一次都不等（舊版全域桶在第 5 次就等）")
check(n_kr5 == 1 and 99 < sleeps[0] <= 101, "kr 第 5 次才等，等的是 kr 自己的視窗（%s）" % (sleeps[:1],))
check(n_na == 1, "換到沒用過的 na1 不等")
check(len(calls) == 18, "假 Riot 收到 18 個請求")
check(sorted(NEW._BUCKETS) == ["asia", "br1", "euw1", "kr", "na1"], "桶按主機分開：%s" % sorted(NEW._BUCKETS))

# ── 3. 正控制：HEAD 那版（全域一個桶）跑同一情境，第 5 個請求就得等 ──
print("【3】正控制：git HEAD 舊版（全域桶）")
# 2026-09-09 #78：原本寫死 `HEAD:`——但分桶早就 commit 進 HEAD 了（9dd4aed8），
# 這條正控制從那之後就一直是紅的（比對的是自己）。改成釘住「引入分桶那個 commit 的前一版」，
# 這樣不管 HEAD 走多遠，控制組永遠是真正的舊碼。
BUCKET_COMMIT = "9dd4aed8"      # 「節流改逐主機分桶＋帳號依平台交錯」
old_src = subprocess.run(["git", "show", BUCKET_COMMIT + "~1:scripts/fetch_soloq.py"], cwd=ROOT,
                         capture_output=True).stdout
TMP = tempfile.mkdtemp(prefix="soloq_bucket_")
old_path = os.path.join(TMP, "fetch_soloq_old.py")
open(old_path, "wb").write(old_src)
OLD = load_mod(old_path, "fetch_soloq_old")
check(len(old_src) > 1000, "拉得到 %s~1 的 fetch_soloq.py（%d 位元組）" % (BUCKET_COMMIT, len(old_src)))
check(not hasattr(OLD, "_BUCKETS") and hasattr(OLD, "_req_times"), "分桶前那一版確實是全域 _req_times（不是分桶）")
o_free, o_kr5, o_na, o_sleeps, o_calls = run_bucket_scenario(OLD, "舊版")
check(o_free >= 1, "舊版 16 次裡就等了 %d 次（第 5 個請求起全域桶就滿）" % o_free)
check(o_free > n_free, "舊版等的次數 > 新版（%d > %d）" % (o_free, n_free))

# ── 4. interleave_order ─────────────────────────────────────────────────────
print("【4】interleave_order")
dist = [("kr", 512), ("euw1", 269), ("br1", 159), ("na1", 142), ("jp1", 5), ("vn2", 2), ("tw2", 1)]
accs = []
for plat, n in dist:
    for k in range(n):
        accs.append({"platform": plat if k % 7 else plat.upper() if plat in ("kr",) else plat,
                     "riotId": f"{plat}{k}#T"})
# 上面：kr 的每 7 個帳號有一個寫成大寫 "KR"（ALIAS 會歸成 kr），測別名一起分組
order = NEW.interleave_order(accs)
check(sorted(order) == list(range(len(accs))), "回傳 %d 個索引、恰好是 0..N-1 的排列" % len(order))
plats = [NEW._plat_of(accs[i]) for i in order]
runs, cur, best = [], None, 0
for p in plats:
    if p == cur:
        best += 1
    else:
        runs.append((cur, best)); cur, best = p, 1
runs.append((cur, best))
max_kr = max(b for p, b in runs if p == "kr")
check(max_kr <= 2, "kr 連續最多 %d 個（不會 512 個擠在一起）" % max_kr)
check(len(set(plats[:10])) >= 3, "前 10 個就出現 %d 種平台" % len(set(plats[:10])))
for plat, _ in dist:
    idx = [i for i in order if NEW._plat_of(accs[i]) == plat]
    check(idx == sorted(idx), "%s 內部保持原順序" % plat)
    if plat == "kr":
        break
check(NEW.interleave_order([]) == [], "空清單 → 空排列")
check(NEW.interleave_order([{"platform": "kr", "riotId": "a#b"}]) == [0], "單一帳號 → [0]")


# ── 5. main() 沙盒：交錯 vs 循序，寫出來的三個檔內容相同（順序不影響結果）──
print("【5】main() 沙盒：--no-interleave vs 預設交錯")
PUUID = {("Faker#KR1", "asia"): "pu-faker", ("Caps#EUW", "europe"): "pu-caps", ("Robo#BR", "americas"): "pu-robo",
         ("Bwipo#NA1", "americas"): "pu-bwipo", ("Zeus#KR", "asia"): "pu-zeus", ("Peanut#KR", "asia"): "pu-peanut",
         ("Yike#EUW", "europe"): "pu-yike", ("Tinowns#BR", "americas"): "pu-tinowns", ("New#KR", "asia"): "pu-new"}
ENTRIES = {"pu-faker": ("CHALLENGER", "I", 1500, 300, 250), "pu-caps": ("GRANDMASTER", "I", 900, 200, 180),
           "pu-robo": ("MASTER", "I", 300, 100, 90), "pu-bwipo": ("DIAMOND", "I", 50, 40, 30),
           "pu-zeus": ("CHALLENGER", "I", 1400, 280, 240), "pu-yike": ("MASTER", "I", 200, 150, 140),
           "pu-tinowns": ("DIAMOND", "II", 10, 20, 25), "pu-new": ("EMERALD", "I", 75, 16, 12)}


def router(url):
    h = host_of(url)
    if "/riot/account/v1/accounts/by-riot-id/" in url:
        parts = url.rsplit("/", 2)
        rid = urllib.request.unquote(parts[-2]) + "#" + urllib.request.unquote(parts[-1])
        pu = PUUID.get((rid, h))
        if not pu:
            return 404, None
        g, t = rid.split("#")
        return 200, {"puuid": pu, "gameName": g, "tagLine": t}
    if "/lol/league/v4/entries/by-puuid/" in url:
        pu = url.rsplit("/", 1)[-1]
        e = ENTRIES.get(pu)
        if not e:
            return 200, []          # 問到了、確定沒排名
        tier, rank, lp, w, l = e
        return 200, [{"queueType": "RANKED_SOLO_5x5", "tier": tier, "rank": rank, "leaguePoints": lp,
                      "wins": w, "losses": l, "puuid": pu}]
    if "leagues/by-queue/" in url:
        tier = url.rsplit("/", 2)[-2].replace("leagues", "").upper()
        ents = []
        if h == "kr" and tier == "CHALLENGER":
            ents = [{"puuid": "pu-zeus", "rank": "I", "leaguePoints": 1400, "wins": 280, "losses": 240}]
        return 200, {"tier": tier, "entries": ents}
    if "/summoner/v4/summoners/by-puuid/" in url:
        return 404, None
    return 500, None


ACCS = [
    {"player": "Faker", "team": "T1", "platform": "kr", "riotId": "Faker#KR1"},
    {"player": "Zeus", "team": "HLE", "platform": "kr", "riotId": "Zeus#KR"},
    {"player": "Peanut", "team": "HLE", "platform": "kr", "riotId": "Peanut#KR"},   # 200 空清單＝確定沒排名
    {"player": "Gone", "team": "T1", "platform": "kr", "riotId": "Gone#404"},       # account-v1 404
    {"player": "New", "team": "T1", "platform": "KR", "riotId": "New#KR"},          # 別名大寫、上一版沒有 ⇒ 走 account-v1
    {"player": "Caps", "team": "G2", "platform": "euw1", "riotId": "Caps#EUW"},
    {"player": "Yike", "team": "G2", "platform": "euw1", "riotId": "Yike#EUW"},
    {"player": "Robo", "team": "PNG", "platform": "br1", "riotId": "Robo#BR"},
    {"player": "Tinowns", "team": "PNG", "platform": "br1", "riotId": "Tinowns#BR"},
    {"player": "Bwipo", "team": "FLY", "platform": "na1", "riotId": "Bwipo#NA1"},
]
# 上一版 soloq.js：有 puuid（走捷徑）、Faker 場數比這次少（⇒ played）、Caps 相同（⇒ 沒動）
PREV = {"fetched_at": "2026-09-07 22:00", "players": [
    {"player": "Faker", "team": "T1", "platform": "kr", "riotId": "Faker#KR1", "puuid": "pu-faker", "curId": "Faker#KR1",
     "tier": "CHALLENGER", "division": "I", "lp": 1480, "wins": 299, "losses": 250, "found": True},
    {"player": "Zeus", "team": "HLE", "platform": "kr", "riotId": "Zeus#KR", "puuid": "pu-zeus", "curId": "Zeus#KR",
     "tier": "CHALLENGER", "division": "I", "lp": 1400, "wins": 280, "losses": 240, "found": True},
    {"player": "Peanut", "team": "HLE", "platform": "kr", "riotId": "Peanut#KR", "puuid": "pu-peanut", "curId": "Peanut#KR",
     "tier": None, "division": None, "lp": None, "wins": None, "losses": None, "found": False},
    {"player": "Caps", "team": "G2", "platform": "euw1", "riotId": "Caps#EUW", "puuid": "pu-caps", "curId": "Caps#EUW",
     "tier": "GRANDMASTER", "division": "I", "lp": 880, "wins": 200, "losses": 180, "found": True},
    {"player": "Yike", "team": "G2", "platform": "euw1", "riotId": "Yike#EUW", "puuid": "pu-yike", "curId": "Yike#EUW",
     "tier": "MASTER", "division": "I", "lp": 150, "wins": 149, "losses": 140, "found": True},
    {"player": "Robo", "team": "PNG", "platform": "br1", "riotId": "Robo#BR", "puuid": "pu-robo", "curId": "Robo#BR",
     "tier": "MASTER", "division": "I", "lp": 300, "wins": 100, "losses": 90, "found": True},
    {"player": "Tinowns", "team": "PNG", "platform": "br1", "riotId": "Tinowns#BR", "puuid": "pu-tinowns", "curId": "Tinowns#BR",
     "tier": "DIAMOND", "division": "II", "lp": 10, "wins": 20, "losses": 25, "found": True},
    {"player": "Bwipo", "team": "FLY", "platform": "na1", "riotId": "Bwipo#NA1", "puuid": "pu-bwipo", "curId": "Bwipo#NA1",
     "tier": "DIAMOND", "division": "I", "lp": 40, "wins": 39, "losses": 30, "found": True},
]}


def sandbox_main(argv_extra):
    d = tempfile.mkdtemp(prefix="soloq_main_")
    sd = os.path.join(d, "scripts"); os.makedirs(sd)
    json.dump(ACCS, open(os.path.join(sd, "soloq_accounts.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(d, "soloq.js"), "w", encoding="utf-8").write("window.SOLOQ_DATA=" + json.dumps(PREV, ensure_ascii=False) + ";\n")
    m = load_mod(os.path.join(HERE, "fetch_soloq.py"), "fetch_soloq_sb")
    m.HERE, m.ROOT = sd, d
    m.ACCOUNTS, m.OUT = os.path.join(sd, "soloq_accounts.json"), os.path.join(d, "soloq.js")
    m.LADDER_MIN = 3                    # kr 有 5 個帳號 ⇒ 會抓 kr 的聯盟名單（Zeus 命中）
    m._LIMITS = [(100000, 1.0)]
    for name in ("HERE", "ROOT", "ACCOUNTS", "OUT"):
        assert ROOT not in getattr(m, name), "模組層路徑 %s 還指著真實 repo" % name
    fake, sleeps = FakeRiot(router), SleepLog()
    old_argv = sys.argv
    sys.argv = ["fetch_soloq.py"] + argv_extra
    buf = io.StringIO()
    try:
        with patched(fake, sleeps, m), contextlib.redirect_stdout(buf):
            m.main()
    finally:
        sys.argv = old_argv
    out = json.loads(open(os.path.join(d, "soloq.js"), encoding="utf-8").read().split("=", 1)[1].rstrip().rstrip(";"))
    played = json.load(open(os.path.join(sd, "soloq_played.json"), encoding="utf-8"))
    accs_after = json.load(open(os.path.join(sd, "soloq_accounts.json"), encoding="utf-8"))
    out.pop("fetched_at", None); played.pop("at", None)
    shutil.rmtree(d, ignore_errors=True)
    return out, played, accs_after, fake.calls, buf.getvalue(), sleeps


seq = sandbox_main(["--no-interleave"])
inter = sandbox_main([])
check(seq[0] == inter[0], "soloq.js 內容相同（去掉時間戳）")
check(seq[1] == inter[1], "soloq_played.json 相同：played=%s unknown=%s static=%d" % (inter[1]["played"], inter[1]["unknown"], len(inter[1]["acc_static"])))
check(seq[2] == inter[2], "soloq_accounts.json 相同")
check([p["riotId"] for p in inter[0]["players"]] == [a["riotId"] for a in ACCS], "交錯處理後 soloq.js 的列序＝帳號清單順序（結果照原位放回）")
check(seq[3] != inter[3] and sorted(seq[3]) == sorted(inter[3]), "兩種模式送出的請求集合相同、順序不同（%d 個請求）" % len(inter[3]))
hosts_seq = [host_of(u) for u in seq[3] if "leagues/by-queue" not in u]
hosts_int = [host_of(u) for u in inter[3] if "leagues/by-queue" not in u]
check(hosts_seq[:3] == ["kr", "kr", "kr"] or hosts_seq[:2] == ["kr", "kr"], "循序模式：逐帳號請求開頭連續 kr（%s）" % hosts_seq[:4])
check(len(set(hosts_int[:4])) >= 3, "交錯模式：前 4 個逐帳號請求就跨 %d 個主機（%s）" % (len(set(hosts_int[:4])), hosts_int[:4]))
check("處理順序依平台交錯" in inter[4] and "處理順序依平台交錯" not in seq[4], "只有交錯模式印出順序說明")
check(len(seq[5]) == 0 and len(inter[5]) == 0, "兩種模式都沒睡（額度夠）")
by_id = {p["riotId"]: p for p in inter[0]["players"]}
check(by_id["Faker#KR1"]["wins"] == 300 and by_id["Faker#KR1"]["found"], "Faker 走 puuid 捷徑、抓到新場數 300W")
check(by_id["Zeus#KR"]["found"] and by_id["Zeus#KR"]["tier"] == "CHALLENGER", "Zeus 由聯盟名單命中")
check(by_id["Gone#404"]["found"] is False and by_id["Gone#404"].get("noAcc"), "Gone 404 ⇒ noAcc 記日期")
check(by_id["Peanut#KR"]["found"] is False and by_id["Peanut#KR"].get("noRank"), "Peanut 200 空清單 ⇒ noRank 記日期")
check(by_id["New#KR"]["puuid"] == "pu-new" and by_id["New#KR"]["platform"] == "kr", "New 走 account-v1 拿到 puuid、別名 KR→kr")
check("T1|Faker" in inter[1]["played"] and "G2|Caps" not in inter[1]["played"], "勝敗比對：Faker 打過、Caps 沒動")
check(not any(u for u in inter[3] if "by-riot-id" in u and "Faker" in u), "Faker 沒走 account-v1（puuid 捷徑）")

# ── 6. 真實檔一個位元沒動 ──
print("【6】真實檔")
mt_after = [os.path.getmtime(p) if os.path.exists(p) else None for p in REAL_FILES]
check(mt_before == mt_after, "真實 soloq_accounts.json／soloq.js／soloq_played.json 的 mtime 前後相同")
shutil.rmtree(TMP, ignore_errors=True)

print("\n%d 條：%d 失敗" % (N[0], len(FAILS)))
for f in FAILS:
    print("  ✗", f)
sys.exit(1 if FAILS else 0)
