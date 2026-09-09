# -*- coding: utf-8 -*-
"""fetch_fill 的「暖抓 Leaguepedia MH 頁」與「gol.gg 掛了不連坐」沙盒測試（2026-09-09 #77）。

驗的是三件事：
  ① main() 的順序是 暖抓 → build(gol.gg) → build_wiki，而**整班只打一次 MH 頁**
     （build_wiki 帶著 force=True 進來時要被 fetch_wiki_mh._FRESH 擋掉，否則變成打兩次、比沒改還慢）。
  ② build() 炸掉不會連帶讓 build_wiki 沒跑；離開碼仍是 1（警示訊號不能被吞）。
  ③ --no-wiki／--status／OE 已追上／暖抓自己失敗 這四種情況各自的行為。

隔離（漏接要在寫壞正本之前擋下）：
  - fetch_wiki_mh 的 CACHE／HTML_DIR／PB_DIR 全部改指沙盒，開跑前 assert 沒有任何一個還指著真實 repo。
  - opener() 換成假的（回固定 bytes、計數），一發真的網路都不打；time.sleep 換成記錄器（不真睡）。
  - 跑完 assert 真實 csv_cache/wikitxt 的 mtime+size 一個位元沒動。
每一條「不該發生」的斷言都配一條「拿掉機制就會發生」的正控制（案例 2）。
"""
import io
import os
import sys
import time
import tempfile
import importlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

TMP = tempfile.mkdtemp(prefix="r77warm_")
FAIL = []
OK = [0]


def chk(cond, msg):
    OK[0] += 1
    if not cond:
        FAIL.append(msg)
        print("  ✗ " + msg)
    else:
        print("  ✓ " + msg)


def snap_real():
    d = {}
    for sub in ("wikitxt", "wikipb"):
        p = os.path.join(ROOT, "csv_cache", sub)
        if not os.path.isdir(p):
            continue
        for fn in os.listdir(p):
            st = os.stat(os.path.join(p, fn))
            d[sub + "/" + fn] = (st.st_mtime_ns, st.st_size)
    return d


before = snap_real()

ff = importlib.import_module("fetch_fill")
wm = importlib.import_module("fetch_wiki_mh")

# ── 沙盒：路徑常數全部搬走，並當場點名 ──
wm.CACHE = os.path.join(TMP, "csv_cache")
wm.HTML_DIR = os.path.join(wm.CACHE, "wikitxt")
wm.PB_DIR = os.path.join(wm.CACHE, "wikipb")
os.makedirs(wm.HTML_DIR)
os.makedirs(wm.PB_DIR)
for nm in ("CACHE", "HTML_DIR", "PB_DIR"):
    v = getattr(wm, nm)
    chk(str(v).startswith(TMP), "沙盒點名：fetch_wiki_mh.%s 指向沙盒（%s）" % (nm, v))

NET = [0]
BODY = ("<html>" + "x" * 9000 + "</html>").encode("utf-8")


class _Resp:
    def read(self):
        NET[0] += 1
        return BODY


class _Op:
    def open(self, *a, **k):
        return _Resp()


wm.opener = lambda: _Op()
SLEPT = [0.0]
_rs = time.sleep
time.sleep = lambda s: SLEPT.__setitem__(0, SLEPT[0] + s)

CFG = {"key": "TEST_S9", "tournament": "T 2099 Split 9", "wiki": "T 2099 Split 9",
       "league": "T", "split": "Split 9", "year": 2099, "playoffs": 0}
ff.FILL = [CFG]

ORDER = []
NEED = [True]
ff.gate = lambda cfg: (NEED[0], 0, {}, os.path.join(TMP, "fill.json"))
BUILD_RAISES = [False]


def fake_build(cfg, force=False, dump=False):
    ORDER.append("build")
    if BUILD_RAISES[0]:
        raise RuntimeError("下載失敗：gol.gg（模擬 WinError 10060）")
    return None


def fake_wiki_build(cfg, force=False):
    """模仿真的 fetch_wiki_mh.build 第一行：帶 force=True 去要 MH 頁。"""
    ORDER.append("wiki.build")
    wm.fetch(cfg["tour"], force=True)
    return None


ff.build = fake_build
wm.build = fake_wiki_build
_real_warm = ff.warm_wiki


def warm(cfg):
    ORDER.append("warm")
    return _real_warm(cfg)


ff.warm_wiki = warm


def run(argv, label):
    ORDER.clear()
    NET[0] = 0
    wm._FRESH.clear()
    sys.argv = ["fetch_fill.py"] + argv
    print("\n[%s]  argv=%s" % (label, argv))
    buf, old = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        rc = ff.main()
    finally:
        sys.stdout = old
    return rc, list(ORDER), NET[0]


# ── ① 正常流程：順序對、MH 頁只打一次 ──
rc, order, net = run([], "正常")
chk(order == ["warm", "build", "wiki.build"], "順序是 暖抓 → build → build_wiki（實際 %s）" % order)
chk(net == 1, "整班只打 1 次 MH 頁（實際 %d 次）" % net)
chk(rc == 0, "離開碼 0（實際 %s）" % rc)

# ── ② 正控制：拿掉 _FRESH 機制就會打兩次（證明上一條真的在測東西）──
def warm_then_forget(cfg):
    ORDER.append("warm")
    _real_warm(cfg)
    wm._FRESH.clear()          # 模擬「沒有 #77 那段 force 抑制」


ff.warm_wiki = warm_then_forget
rc, order, net = run([], "正控制：沒有 _FRESH")
chk(net == 2, "正控制：拿掉 _FRESH 就變成打 2 次（實際 %d 次）" % net)
ff.warm_wiki = warm

# ── ③ gol.gg 炸掉不連坐 ──
BUILD_RAISES[0] = True
rc, order, net = run([], "gol.gg 掛了")
chk(order == ["warm", "build", "wiki.build"], "build 炸掉後 build_wiki 仍然跑到（實際 %s）" % order)
chk(net == 1, "而且 MH 頁仍然只打 1 次（實際 %d 次）" % net)
chk(rc == 1, "離開碼 1，警示訊號沒被吞掉（實際 %s）" % rc)
BUILD_RAISES[0] = False

# ── ④ --no-wiki：不暖抓、不打網路 ──
rc, order, net = run(["--no-wiki"], "--no-wiki")
chk(order == ["build"], "--no-wiki 只有 build（實際 %s）" % order)
chk(net == 0, "--no-wiki 一發網路都沒打（實際 %d 次）" % net)

# ── ⑤ --dump：不暖抓 ──
rc, order, net = run(["--dump"], "--dump")
chk("warm" not in order and "wiki.build" not in order, "--dump 不碰 Leaguepedia（實際 %s）" % order)

# ── ⑥ OE 已追上（gate 說不用補）：不白打一發暖抓 ──
NEED[0] = False
rc, order, net = run([], "OE 已追上")
chk(order == ["warm", "build"], "OE 追上時 build_wiki 走「停用舊資料」那條、不呼叫 wm.build（實際 %s）" % order)
chk(net == 0, "暖抓被 gate 擋掉、build_wiki 也不抓頁面 ⇒ 0 發網路（實際 %d 次）" % net)
NEED[0] = True

# ── ⑦ 暖抓自己失敗：不影響，build_wiki 照舊重抓 ──
_of = wm.fetch
CALLS = [0]


def flaky_fetch(tour, force=False):
    CALLS[0] += 1
    if CALLS[0] == 1:
        raise OSError("模擬暖抓時 Leaguepedia 不通")
    return _of(tour, force=force)


wm.fetch = flaky_fetch
CALLS[0] = 0
rc, order, net = run([], "暖抓失敗")
chk(order == ["warm", "build", "wiki.build"], "暖抓失敗不中斷流程（實際 %s）" % order)
chk(net == 1, "build_wiki 照舊自己重抓（實際 %d 次）" % net)
chk(rc == 0, "暖抓失敗不算 fetch_fill 失敗（實際 %s）" % rc)
wm.fetch = _of

time.sleep = _rs

# ── 正本一個位元沒動 ──
after = snap_real()
chk(before == after, "真實 csv_cache/wikitxt＋wikipb 一個位元沒動（%d 個檔）" % len(before))

print("\n%d 條，%d 條失敗" % (OK[0], len(FAIL)))
for f in FAIL:
    print("  ✗ " + f)
sys.exit(1 if FAIL else 0)
