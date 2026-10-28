"""fetch_obgg_accounts 連線斷路器（2026-10-28 主對話迴圈 #2178）的沙盒測試。

情境：www.obgg.net TCP 直接逾時（10-27 起連續 4 班），每班空等 199.7s。
沙盒：http.client.HTTPSConnection 換成假連線（connect() 依情境丟 TimeoutError 或成功）、urlopen 換成會炸的 stub、
time.sleep no-op；只跑 pull()，不碰 main() 的任何寫檔。
  [1] 全部連不上 ⇒ 斷路：握手嘗試 ≤ BREAK_AFTER＋工人數、9 區全記 zone 最終失敗（安全門看到的數字跟原本一樣）
  [2] 對照組（正例會動）：BREAK_AFTER 調成極大 ⇒ 不斷路，握手嘗試＝9 區 × 3 次＝27
  [3] 成功過一次之後的連線失敗不跳斷路（只有 LPL 的 zone 能連、其餘都逾時）
  [4] HTTP 非 200 不算「連不上」（全部回 503 ⇒ 不斷路、照舊 27 次）
  [5] 再跑一次 pull() 斷路狀態會重設（上一趟的 down 不會漏到下一趟）
"""
import io, os, sys, json, threading, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch_obgg_accounts as M   # 模組自己會把 stdout 包成 UTF-8（這裡再包一次會被它關掉）

FAILS = []
def check(name, ok, info=""):
    print(("  ✓ " if ok else "  ✗ ") + name + (f"（{info}）" if info != "" else ""))
    if not ok:
        FAILS.append(name)

def no_urlopen(*a, **k):
    raise AssertionError("測試打到真實網路：urllib.request.urlopen")
M.urllib.request.urlopen = no_urlopen
M.time.sleep = lambda s: None

MODE = {"connect": "timeout", "status": 200, "ok_zone": None}
LOCK = threading.Lock()
CNT = {"connect": 0, "request": 0}

class Resp:
    def __init__(self, status, body): self.status, self.b = status, body
    def read(self): return self.b

class FakeConn:
    def __init__(self, host, timeout=None):
        assert host == "www.obgg.net", host
        self.path = None
    def connect(self):
        with LOCK:
            CNT["connect"] += 1
        z = getattr(M._TL, "zone", None)
        if MODE["connect"] == "timeout" and not (MODE["ok_zone"] and z == MODE["ok_zone"]):
            raise TimeoutError("timed out")
    def request(self, method, path, headers=None):
        with LOCK:
            CNT["request"] += 1
        self.path = path
    def getresponse(self):
        if MODE["status"] != 200:
            return Resp(MODE["status"], b"")
        return Resp(200, json.dumps({"data": []}).encode("utf-8"))
    def close(self): pass

M.http.client.HTTPSConnection = FakeConn
M.KEEPALIVE = True

def reset_stats():
    for d in (M.ERRS,):
        for k in d: d[k] = 0
    M.ERR_URLS.clear()
    CNT.update(connect=0, request=0)

def run():
    reset_stats()
    t0 = time.time()
    out, zone_err = M.pull()
    return out, zone_err, time.time() - t0

# 模組層的路徑常數不可以被這支測試動到（pull() 不寫檔，這裡只確認沒有誤設）
check("沙盒：HTTPSConnection 是假連線、urlopen 是 stub", M.http.client.HTTPSConnection is FakeConn and M.urllib.request.urlopen is no_urlopen)

print("[1] 全部連不上 ⇒ 斷路")
MODE.update(connect="timeout", status=200, ok_zone=None)
out, ze, sec = run()
lim = M.BREAK_AFTER + M.TEAM_JOBS
check(f"握手嘗試 ≤ BREAK_AFTER＋工人數（{lim}）", CNT["connect"] <= lim, CNT["connect"])
check("斷路旗標有立", M.BRK["down"] is True)
check("9 區全記 zone 最終失敗", M.ERRS["zone"] == len(M.ZONES), M.ERRS)
check("zone_err 每區 1", all(ze.get(z) == 1 for z in M.ZONES), ze)
check("out 全空（安全門會擋下）", not any(out.get(z) for z in M.ZONES), out)

print("[2] 對照組：不斷路就照舊逐一試滿")
old = M.BREAK_AFTER
M.BREAK_AFTER = 10 ** 9
out, ze, sec = run()
M.BREAK_AFTER = old
check("握手嘗試＝9 區 × 3 次", CNT["connect"] == len(M.ZONES) * 3, CNT["connect"])
check("斷路旗標沒立", M.BRK["down"] is False)
check("同樣 9 區全記失敗（兩種路徑給安全門的數字一致）", M.ERRS["zone"] == len(M.ZONES), M.ERRS)

print("[3] 成功過之後的連線失敗不斷路")
MODE.update(connect="timeout", ok_zone="LPL")
# LPL 先單獨成功一次，確保「已成功」先發生（並行下順序不定）
M.brk_reset()
M._TL.zone = "LPL"
r = M.get(M.BASE + "zone?name=LPL&isClick=0", kind=None)
M._TL.zone = None
M._drop_conn()
check("LPL 預熱成功", isinstance(r, dict) and "_err" not in r, r)
ok_before = M.BRK["ok"]
# 直接用 get() 打 8 個會逾時的區（不經 pull()，pull() 開頭會 brk_reset）
for z in M.ZONES[1:]:
    M._TL.zone = z
    M.get(M.BASE + "zone?name=" + z, kind=None)
M._TL.zone = None
check("成功過一次 ⇒ 之後再多連線失敗也不斷路", M.BRK["down"] is False and ok_before == 1, M.BRK)
check("連線失敗確實有被數到（正例會動）", M.BRK["cf"] >= M.BREAK_AFTER, M.BRK["cf"])

print("[4] HTTP 503 不算連不上")
MODE.update(connect="ok", status=503, ok_zone=None)
out, ze, sec = run()
check("不斷路", M.BRK["down"] is False, M.BRK)
check("照舊 9 區 × 3 次請求", CNT["request"] == len(M.ZONES) * 3, CNT["request"])

print("[5] pull() 開頭重設斷路狀態")
MODE.update(connect="timeout", status=200)
run()
check("先斷路", M.BRK["down"] is True)
MODE.update(connect="ok", status=200)
out, ze, sec = run()
check("下一趟連得上就不再斷路、0 失敗", M.BRK["down"] is False and M.ERRS["zone"] == 0, (M.BRK, M.ERRS))

print("\n" + ("全部通過" if not FAILS else f"失敗 {len(FAILS)} 項：" + "；".join(FAILS)))
sys.exit(1 if FAILS else 0)
