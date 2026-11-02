# -*- coding: utf-8 -*-
"""update_health 的「國際賽落後／少局」回歸測試（2026-11-02 主對話迴圈 #2445）。

背景：逐聯賽落後與同一天少局只看六個一級聯賽，世界賽期間那六個全部休賽 ⇒ 兩條哨兵等於沒有在看任何比賽。
回放 2026 的 data_2026.js：EWC 07-15～19 缺局缺到 07-26 以後，當時沒有任何人叫（autopilot/_m2445_replay.txt）。

沙盒：年度檔、日誌、基準全在 tempfile；隊名用 ZZ_PROBE_9942（只有沙盒才有的證據）；網路出口接管 wiki_rows，
wiki_rows 自己的接線測試則接管 urllib.request.build_opener。main() 跑完 assert 真實基準與日誌的 mtime 沒動。
用法：python scripts\\update_health_intl_test.py（exit 0＝全過）
"""
import contextlib
import datetime
import io
import json
import os
import shutil
import sys
import tempfile
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import update_health as uh          # noqa: E402

OK = [0]
NG = []


def eq(got, want, label):
    if got == want:
        OK[0] += 1
    else:
        NG.append("%s：得到 %r，應為 %r" % (label, got, want))


HDR = ["league", "date", "game", "blue_teamname", "red_teamname"]
A, B = "ZZ_PROBE_9942 Alpha", "ZZ_PROBE_9942 Beta"
NOW = datetime.datetime.utcnow().replace(second=0, microsecond=0)


def day(n, hour=12):
    d = NOW - datetime.timedelta(days=n)
    return d.strftime("%Y-%m-%d ") + "%02d:00:00" % hour


def write_data(root, games):
    os.makedirs(os.path.join(root, "data"), exist_ok=True)
    rows = [HDR]
    for lg, dt, g in games:
        rows += [[lg, dt, g, A, B]] * 6      # 真實年度檔一局 6 列
    obj = {"fetched_at": "x", "year": NOW.year, "tabs": {"RAW_DATA": rows}}
    for y in {NOW.year, (NOW - datetime.timedelta(days=30)).year}:
        with io.open(os.path.join(root, "data", "data_%d.js" % y), "w", encoding="utf-8") as f:
            f.write("window.LOL_DATA=" + json.dumps(obj, ensure_ascii=False) + ";")


def wrow(ov, dt, g):
    return {"ov": ov, "dt": dt, "t1": A, "t2": B, "g": g}


WC = "%d Season World Championship/Main Event" % NOW.year

# ① intl_relabel：四個標籤、頁名保留、其他頁不動
r = uh.intl_relabel([{"ov": WC}, {"ov": "2026 Season World Championship/Play-In"},
                     {"ov": "2026 Mid-Season Invitational"}, {"ov": "2026 First Stand"},
                     {"ov": "Esports World Cup 2026"},
                     {"ov": "Esports World Cup 2026/Online Qualifiers/Korea"},
                     {"ov": "LCK/2026 Season/Rounds 1-2"}, {"ov": "PCS/2026 Season/Summer Season"},
                     {"ov": "World Championship Qualifier"}, {"ov": None}, "不是 dict"])
eq([(x.get("ov") if isinstance(x, dict) else x) for x in r],
   ["WLDs/" + WC, "WLDs/2026 Season World Championship/Play-In",
    "MSI/2026 Mid-Season Invitational", "FST/2026 First Stand", "EWC/Esports World Cup 2026",
    "Esports World Cup 2026/Online Qualifiers/Korea", "LCK/2026 Season/Rounds 1-2",
    "PCS/2026 Season/Summer Season", "World Championship Qualifier", None, "不是 dict"], "①改寫")
eq(uh.intl_relabel({"error": "x"}), {"error": "x"}, "①不是陣列原樣回傳")
src = [{"ov": WC}]
uh.intl_relabel(src)
eq(src[0]["ov"], WC, "①不改呼叫端的列")

# ② wiki_rows 接線：查詢含一級聯賽＋國際賽；回傳已改寫。出口接管 build_opener
SEEN = []


class FakeResp:
    def __init__(self, b):
        self.b = b

    def read(self):
        return self.b


class FakeOp:
    def open(self, req, timeout=None):
        SEEN.append(req.full_url)
        return FakeResp(json.dumps([{"ov": WC, "dt": day(1)}, {"ov": "LCK/x", "dt": day(1)}]).encode("utf-8"))


_real_bo, _real_sleep = urllib.request.build_opener, uh.time.sleep
urllib.request.build_opener = lambda *a: FakeOp()
uh.time.sleep = lambda s: None
try:
    got = uh.wiki_rows("2099-01-01", timeout=1)
finally:
    urllib.request.build_opener, uh.time.sleep = _real_bo, _real_sleep
eq([x["ov"] for x in got], ["WLDs/" + WC, "LCK/x"], "②wiki_rows 回傳前改寫")
qs = urllib.parse.parse_qs(urllib.parse.urlparse(SEEN[-1]).query) if SEEN else {}
where = (qs.get("where") or [""])[0]
for pat in list(uh.INTL_LIKE) + [lg + "/%" for lg in uh.LAG_TIER1]:
    eq(('LIKE "%s"' % pat) in where, True, "②查詢含 " + pat)
eq(where.startswith('SG.DateTime_UTC >= "2099-01-01" AND ('), True, "②OR 有包在括號裡")

# ③ 判定（lag／daycount 帶 tier1=INTL_LEAGUES）＋一級聯賽那條不受影響
tmp = tempfile.mkdtemp(prefix="uh_intl_")
try:
    r0 = os.path.join(tmp, "r0")
    write_data(r0, [("WLDs", day(9), 1), ("WLDs", day(5), 1), ("WLDs", day(5, 13), 2)])
    p = os.path.join(r0, "data", "data_%d.js" % NOW.year)
    ALLW = [wrow("WLDs/" + WC, day(9), 1), wrow("WLDs/" + WC, day(5), 1), wrow("WLDs/" + WC, day(5, 13), 2)]
    IL = uh.INTL_LEAGUES

    eq(uh.lag_problems(NOW, p, fetch=lambda s: ALLW, tier1=IL)[0], "ok", "③對得上⇒落後 ok")
    eq(uh.daycount_problems(NOW, p, fetch=lambda s: ALLW, tier1=IL)[0], "ok", "③對得上⇒少局 ok")
    two = ALLW + [wrow("WLDs/" + WC, day(3), 1), wrow("WLDs/" + WC, day(1), 1)]
    st, ms = uh.lag_problems(NOW, p, fetch=lambda s: two, tier1=IL)
    eq((st, any("WLDs 落後 2 個比賽日" in m for m in ms)), ("bad", True), "③晚 2 個比賽日⇒落後")
    one = ALLW + [wrow("WLDs/" + WC, day(1), 1)]
    eq(uh.lag_problems(NOW, p, fetch=lambda s: one, tier1=IL)[0], "ok", "③對照：只晚 1 個比賽日不叫落後")
    miss = ALLW + [wrow("WLDs/" + WC, day(5, 14), 3)]
    st, ms = uh.daycount_problems(NOW, p, fetch=lambda s: miss, tier1=IL)
    eq((st, any("少 1 局" in m and "WLDs" in m for m in ms)), ("bad", True), "③同一天少 1 局⇒少局")
    # 四個標籤各自都要叫（少一個進白名單就看不見那個賽事）
    eq(uh.INTL_LEAGUES, ("WLDs", "MSI", "FST", "EWC"), "③白名單")
    for lab, page in (("WLDs", WC), ("MSI", "2026 Mid-Season Invitational"),
                      ("FST", "2026 First Stand"), ("EWC", "Esports World Cup 2026")):
        rx = os.path.join(tmp, "r_" + lab)
        write_data(rx, [(lab, day(9), 1)])
        px = os.path.join(rx, "data", "data_%d.js" % NOW.year)
        w = uh.intl_relabel([wrow(page, day(9), 1), wrow(page, day(3), 1), wrow(page, day(1), 1)])
        st, ms = uh.lag_problems(NOW, px, fetch=lambda s, w=w: w, tier1=IL)
        eq((st, any((lab + " 落後 2 個比賽日") in m for m in ms)), ("bad", True), "③%s 會叫" % lab)
    # 舊呼叫（不帶 tier1）對同一份素材不看國際賽＝一級聯賽的判定沒變；這條同時是正控制：
    # 沒有 tier1 就看不見，所以舊版健檢對這份素材一定是 ok
    eq(uh.lag_problems(NOW, p, fetch=lambda s: two)[0], "ok", "③不帶 tier1 看不見國際賽（正控制）")
    eq(uh.daycount_problems(NOW, p, fetch=lambda s: miss)[0], "ok", "③不帶 tier1 看不見少局（正控制）")
    # EWC 線上資格賽沒被改寫 ⇒ 不會被算成 EWC 的局
    q = uh.intl_relabel([{"ov": "Esports World Cup 2026/Online Qualifiers/Korea", "dt": day(1), "t1": A, "t2": B, "g": 1},
                         {"ov": "Esports World Cup 2026/Online Qualifiers/EMEA", "dt": day(3), "t1": A, "t2": B, "g": 1}])
    eq(uh.lag_problems(NOW, p, fetch=lambda s: q, tier1=IL)[0], "ok", "③EWC 資格賽不算主賽")

    # ④ main() 端到端
    real = {k: getattr(uh, k) for k in ("ROOT", "wiki_rows", "LOG", "CONSOLE", "BASE", "SHIFT_LOG_DIR", "live_dup")}
    argv0 = list(sys.argv)
    watch = [real["BASE"], real["LOG"]]
    before = [os.path.getmtime(x) if os.path.exists(x) else None for x in watch]
    log = os.path.join(tmp, "log.txt")
    with io.open(log, "w", encoding="utf-8") as f:
        f.write("==== run_update %s（並行 4）====\n---- fetch_x（1.0s，exit 0）----\n守門通過\n"
                "   1111111..2222222  main -> main\n" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def run_main(fetch, extra=()):
        calls = []

        def spy(since, timeout=90):
            calls.append(since)
            return fetch(since)
        uh.ROOT, uh.wiki_rows, uh.LOG = r0, spy, log
        uh.CONSOLE, uh.BASE = os.path.join(tmp, "console.txt"), os.path.join(tmp, "base.json")
        uh.SHIFT_LOG_DIR = os.path.join(tmp, "shift")
        uh.live_dup = lambda timeout=None: (0, "")
        # 模組層路徑常數全都要指沙盒，漏接就在 main 動手之前停下
        for k in ("ROOT", "LOG", "CONSOLE", "BASE", "SHIFT_LOG_DIR"):
            assert getattr(uh, k).startswith(tmp) or getattr(uh, k) == r0, k
        sys.argv = ["update_health.py", "--no-save", "--no-live", "--no-soloqfresh"] + list(extra)
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                rc = uh.main()
        except Exception as e:
            rc = "RAISED %s: %s" % (type(e).__name__, e)
        finally:
            for k, v in real.items():
                setattr(uh, k, v)
            sys.argv = list(argv0)
        out = buf.getvalue()
        concl = [ln for ln in out.splitlines() if ln.startswith("結論：")]
        return rc, out, (concl[0] if concl else ""), calls

    rc, out, concl, calls = run_main(lambda s: two)
    eq("國際賽 WLDs 落後 2 個比賽日" in concl, True, "④落後進結論（%s）" % concl[:120])
    eq(rc != 0 and isinstance(rc, int), True, "④落後 ⇒ 非 0（得到 %r）" % (rc,))
    eq(len(calls), 1, "④一輪只打一次 wiki（共用請求）")
    eq("⚠ 有落後或少局" in out, True, "④報告行標 ⚠")
    rc, out, concl, _ = run_main(lambda s: miss)
    eq("國際賽 WLDs" in concl and "少 1 局" in concl, True, "④少局進結論（%s）" % concl[:120])
    rc, out, concl, _ = run_main(lambda s: ALLW)
    eq("國際賽" in concl, False, "④對得上不進結論（%s）" % concl[:120])
    eq("✓ 比賽日與局數都對得上" in out, True, "④對得上印 ✓")
    eq("WLDs   我們最後比賽日" in out, True, "④進行中的賽事印一行")

    def boom(s):
        raise OSError("zz down")
    rc, out, concl, calls = run_main(boom)
    eq(isinstance(rc, int), True, "④wiki 掛掉 main 不炸（%r）" % (rc,))
    eq("國際賽（" in out and "略過（原因見下一行）" in out and "國際賽" not in concl, True, "④wiki 掛掉走略過、不報異常")
    eq(len(calls), 1, "④wiki 掛掉也不重打")
    rc, out, concl, calls = run_main(lambda s: two, extra=["--no-lag"])
    eq(("國際賽：（--no-lag 跳過）" in out, len(calls), "國際賽" in concl), (True, 0, False), "④--no-lag 跳過")

    after = [os.path.getmtime(x) if os.path.exists(x) else None for x in watch]
    eq(after, before, "⑤真實基準與日誌沒被動")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("update_health_intl_test：通過 %d 條，失敗 %d 條" % (OK[0], len(NG)))
for x in NG:
    print("  ✗ " + x)
sys.exit(1 if NG else 0)
