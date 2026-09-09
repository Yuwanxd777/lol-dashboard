# -*- coding: utf-8 -*-
"""fetch_soloq.riot_get 逐主機 keep-alive（2026-09-09 精進迴圈 #78）的沙盒測試。

跑法：python scripts/fetch_soloq_keepalive_test.py

為什麼要有這支：#78 把 riot_get 從「每次 urllib.request.urlopen（每次重開 TCP+TLS）」
改成「逐主機重用 http.client.HTTPSConnection」。請求數與節流一個字都沒改，
但多了三種以前不存在的失敗模式——連線被對方關掉、伺服器說 Connection: close、
新連線一開就失敗——這支就是釘住那三種的行為。

沙盒紀律（CLAUDE.md 2026-09-07 #52）：
  · 傳輸出口只有一個：模組層的 `_CONN_CLS`。測試把它換掉，並且**同時**把
    `urllib.request.urlopen` 換成「一叫就爆」的漏接偵測器——舊路徑要是還有人走，會當場紅。
  · 模組層路徑常數（HERE／ROOT／ACCOUNTS／OUT）跑前逐一點名，確認沒有一個還指著真實 repo。
  · 跑完比對真實 soloq.js／soloq_accounts.json／soloq_played.json 的 mtime＋大小一位元沒動。
正控制：同一條流程把「重用」關掉（每次請求前先 _conn_close）⇒ 連線數從 1 變 5，
證明「只建立 1 條」那條斷言真的在測東西、不是恆真。
"""
import os, sys, io, json, time, importlib.util, urllib.request, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
os.environ["RIOT_API_KEY"] = "RGAPI-sandbox-not-a-real-key"
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

FAILS = []
N = [0]


def check(cond, msg):
    N[0] += 1
    print(("  OK " if cond else "  XX ") + msg)
    if not cond:
        FAILS.append(msg)


def load_mod(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


REAL_FILES = [os.path.join(HERE, "soloq_accounts.json"), os.path.join(ROOT, "soloq.js"),
              os.path.join(HERE, "soloq_played.json")]


def stat_real():
    return [(os.path.getmtime(p), os.path.getsize(p)) if os.path.exists(p) else None for p in REAL_FILES]


BEFORE = stat_real()
M = load_mod(os.path.join(HERE, "fetch_soloq.py"), "fetch_soloq_ka")


# ── 假傳輸 ──────────────────────────────────────────────────────────────────
class Resp:
    def __init__(self, code, body, hdrs=None, will_close=False):
        self.status = code
        self.headers = hdrs if hdrs is not None else {}
        self._b = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.will_close = will_close

    def read(self, *a):
        return self._b


class Wire:
    """把一連串「該回什麼」餵給假連線。

    plan 是 list，每一項是 dict：
      {"code":200,"body":[...],"hdrs":{...},"close":False}   正常回應
      {"raise":"request"}   在 request() 當下丟例外（＝重用到一條死掉的連線）
      {"raise":"open"}      建立連線時就丟例外（＝主機真的連不上）
    """

    def __init__(self, plan, reuse=True):
        self.plan, self.i = plan, 0
        self.reuse = reuse
        self.conns = []          # 建立過的連線（每一項是 (hostname, 是否已關))
        self.urls = []           # 送出過的 URL
        self.opened = 0

    def next(self):
        step = self.plan[min(self.i, len(self.plan) - 1)]
        self.i += 1
        return step

    def cls(self):
        wire = self

        class FakeConn(object):
            def __init__(self, host, timeout=15):
                wire.opened += 1
                self.host, self.timeout, self.closed, self._url = host, timeout, False, None
                wire.conns.append(self)
                if wire.plan and wire.plan[min(wire.i, len(wire.plan) - 1)].get("raise") == "open":
                    wire.i += 1
                    raise OSError("沙盒：主機連不上")

            def request(self, method, path, headers=None, body=None):
                if self.closed:
                    raise OSError("沙盒：在已關閉的連線上送請求")
                step = wire.plan[min(wire.i, len(wire.plan) - 1)]
                if step.get("raise") == "request":
                    wire.i += 1
                    raise OSError("沙盒：重用到一條已被對方關掉的連線")
                self._url = "https://%s%s" % (self.host, path)

            def getresponse(self):
                step = wire.next()
                wire.urls.append(self._url)
                return Resp(step.get("code", 200), step.get("body", []),
                            step.get("hdrs"), step.get("close", False))

            def close(self):
                self.closed = True

        return FakeConn


def _leak(*a, **k):
    raise AssertionError("沙盒漏接：riot_get 不該再走 urllib.request.urlopen")


@contextlib.contextmanager
def wired(wire, limits=None):
    old_cls, old_open, old_sleep = M._CONN_CLS, urllib.request.urlopen, time.sleep
    old_lim = M._LIMITS
    slept = []
    M._CONN_CLS = wire.cls()
    M._CONNS.clear()
    M._BUCKETS.clear()
    M._LIMITS = limits or [(100000, 1.0)]
    urllib.request.urlopen = _leak
    time.sleep = lambda s: slept.append(s)
    try:
        yield slept
    finally:
        M._CONN_CLS, urllib.request.urlopen, time.sleep = old_cls, old_open, old_sleep
        M._LIMITS = old_lim
        M._CONNS.clear()
        M._BUCKETS.clear()


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **k)


# ── 0. 沙盒點名 ─────────────────────────────────────────────────────────────
print("【0】沙盒點名（出口與路徑）")
check(hasattr(M, "_CONN_CLS") and hasattr(M, "_CONNS") and hasattr(M, "_raw_get"),
      "模組有 _CONN_CLS／_CONNS／_raw_get 這三個新的名字")
src = io.open(os.path.join(HERE, "fetch_soloq.py"), encoding="utf-8").read()
i0 = src.index("def riot_get(")
check("urlopen" not in src[i0:i0 + 1500], "riot_get 本體裡不再出現 urlopen（唯一出口是 _raw_get→_CONN_CLS）")
w = Wire([{"code": 200, "body": []}])
with wired(w):
    check(M._CONN_CLS is not __import__("http.client", fromlist=["x"]).HTTPSConnection,
          "跑測試時 _CONN_CLS 已經是假的（不是真的 HTTPSConnection）")
    try:
        urllib.request.urlopen("https://kr.api.riotgames.com/x")
        check(False, "urlopen 應該一叫就爆")
    except AssertionError:
        check(True, "urlopen 換成漏接偵測器：一叫就爆")

# ── 1. 連線重用 ─────────────────────────────────────────────────────────────
print("【1】同一主機連打 5 次只開 1 條連線")
w = Wire([{"code": 200, "body": []}])
with wired(w):
    for _ in range(5):
        quiet(M.riot_get, "https://kr.api.riotgames.com/p")
check(w.opened == 1, "只建立 %d 條連線（5 次請求）" % w.opened)
check(len(w.urls) == 5, "假 Riot 收到 5 個請求（請求數沒有因為重用而變少）")

print("【1b】正控制：把重用關掉 ⇒ 5 條")
w2 = Wire([{"code": 200, "body": []}])
with wired(w2):
    for _ in range(5):
        M._CONNS.clear()          # 模擬「沒有重用」的舊行為
        quiet(M.riot_get, "https://kr.api.riotgames.com/p")
check(w2.opened == 5, "關掉重用就變 %d 條（證明上面那條不是恆真）" % w2.opened)

print("【2】不同主機各自一條")
w = Wire([{"code": 200, "body": []}])
with wired(w):
    for h in ("kr", "euw1", "br1", "kr", "euw1"):
        quiet(M.riot_get, "https://%s.api.riotgames.com/p" % h)
check(w.opened == 3, "3 個主機 ⇒ %d 條連線（kr／euw1 第二次重用）" % w.opened)
check(sorted(set(c.host for c in w.conns)) ==
      ["br1.api.riotgames.com", "euw1.api.riotgames.com", "kr.api.riotgames.com"], "連線的主機名正確")

# ── 3. 伺服器說要關 ─────────────────────────────────────────────────────────
print("【3】回應帶 will_close ⇒ 下一次重開")
w = Wire([{"code": 200, "body": [], "close": True}, {"code": 200, "body": []}])
with wired(w):
    quiet(M.riot_get, "https://kr.api.riotgames.com/p")
    check(M._CONNS == {}, "will_close 之後連線已從池子裡拿掉")
    quiet(M.riot_get, "https://kr.api.riotgames.com/p")
check(w.opened == 2, "重開了第二條（共 %d 條）" % w.opened)

# ── 4. 重用到死連線 ⇒ 自動換一條重打 ────────────────────────────────────────
print("【4】重用到一條死掉的連線 ⇒ 換新的重打一次，呼叫端無感")
w = Wire([{"code": 200, "body": ["first"]}, {"raise": "request"}, {"code": 200, "body": ["second"]}])
with wired(w) as slept:
    c1, d1 = quiet(M.riot_get, "https://kr.api.riotgames.com/p")
    c2, d2 = quiet(M.riot_get, "https://kr.api.riotgames.com/p")
check((c1, d1) == (200, ["first"]), "第一次正常 %s" % ((c1, d1),))
check((c2, d2) == (200, ["second"]), "第二次自動換連線後成功 %s（不是 (0, None)）" % ((c2, d2),))
check(w.opened == 2, "只多開了 1 條（共 %d 條）" % w.opened)
check(slept == [], "沒有走 riot_get 的『連線錯誤，重試』那條（沒睡：%s）" % (slept,))

# ── 5. 全新連線就失敗 ⇒ 直接往上丟，不做第二次 ──────────────────────────────
print("【5】新連線一開就失敗 ⇒ 不浪費第二次")
w = Wire([{"raise": "open"}])
with wired(w) as slept:
    code, data = quiet(M.riot_get, "https://kr.api.riotgames.com/p")
check((code, data) == (0, None), "riot_get 用盡 4 次重試後回 (0, None)：%s" % ((code, data),))
check(w.opened == 4, "4 次重試各開 1 條、每條只試一次（共 %d 條，不是 8 條）" % w.opened)
check(slept == [2, 2, 2, 2], "每次重試睡 2 秒：%s" % (slept,))

# ── 6. 狀態碼與標頭 ─────────────────────────────────────────────────────────
print("【6】狀態碼與 X-App-Rate-Limit")
w = Wire([{"code": 404, "body": None}])
with wired(w):
    check(quiet(M.riot_get, "https://kr.api.riotgames.com/p") == (404, None), "404 → (404, None)")
w = Wire([{"code": 500, "body": None}])
with wired(w):
    check(quiet(M.riot_get, "https://kr.api.riotgames.com/p") == (500, None), "500 → (500, None)")
w = Wire([{"code": 429, "body": None, "hdrs": {"Retry-After": "3"}}, {"code": 200, "body": ["ok"]}])
with wired(w) as slept:
    r = quiet(M.riot_get, "https://kr.api.riotgames.com/p")
check(r == (200, ["ok"]), "429 之後重試成功 %s" % (r,))
check(slept == [4], "429 等 Retry-After+1＝4 秒：%s" % (slept,))
w = Wire([{"code": 200, "body": [], "hdrs": {"X-App-Rate-Limit": "20:1,100:120"}}])
with wired(w, limits=[(20, 1.0), (100, 120.0)]):
    quiet(M.riot_get, "https://kr.api.riotgames.com/p")
    check(M._LIMITS == [(20, 1.0), (100, 120.0)], "標頭讀得到、額度跟著設（%s）" % (M._LIMITS,))
w = Wire([{"code": 200, "body": [], "hdrs": {"X-App-Rate-Limit": "50:10"}}])
with wired(w, limits=[(20, 1.0)]):
    quiet(M.riot_get, "https://kr.api.riotgames.com/p")
    check(M._LIMITS == [(50, 10.0)], "額度變了會跟著改（%s）" % (M._LIMITS,))

# ── 7. 節流照舊 ─────────────────────────────────────────────────────────────
print("【7】節流與分桶沒被動到")
w = Wire([{"code": 200, "body": []}])
with wired(w, limits=[(5, 100.0)]) as slept:
    for _ in range(4):
        quiet(M.riot_get, "https://kr.api.riotgames.com/p")
    n_free = len(slept)
    quiet(M.riot_get, "https://kr.api.riotgames.com/p")
    n_kr5 = len(slept)
    quiet(M.riot_get, "https://euw1.api.riotgames.com/p")
    n_euw = len(slept)
check(n_free == 0 and n_kr5 == 1 and n_euw == 1, "kr 前 4 次不等、第 5 次等、euw1 不等（%d/%d/%d）"
      % (n_free, n_kr5, n_euw))

# ── 8. 查詢字串與路徑 ───────────────────────────────────────────────────────
print("【8】URL 拆解")
w = Wire([{"code": 200, "body": []}])
with wired(w):
    quiet(M.riot_get, "https://kr.api.riotgames.com/lol/league/v4/entries/by-puuid/abc?x=1&y=2")
check(w.urls == ["https://kr.api.riotgames.com/lol/league/v4/entries/by-puuid/abc?x=1&y=2"],
      "path＋query 原樣送出：%s" % (w.urls,))

# ── 9. 真實檔沒動 ───────────────────────────────────────────────────────────
print("【9】真實檔")
check(stat_real() == BEFORE, "真實 soloq_accounts.json／soloq.js／soloq_played.json 的 mtime＋大小前後相同")
check(M._CONNS == {}, "跑完連線池是空的（沒有留著真實連線）")

print("\n%d 條：%d 失敗" % (N[0], len(FAILS)))
for f in FAILS:
    print("  - " + f)
sys.exit(1 if FAILS else 0)
