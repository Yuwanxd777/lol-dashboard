# -*- coding: utf-8 -*-
"""⑤d fetch_soloq_update 整批 429 等待後重問（2026-11-02 線 3，精進迴圈 #2437）——不打網路、不寫任何正本、不真的睡。

① 沙盒守則：只 import 模組、不跑 main()；load_player_file／time.sleep 換成假的；跑完真實逐場檔／帳號檔／索引 mtime 沒動。
② 預設關：沒帶 --rl-waits ⇒ RL_WAITS 空、整批 429 不等、照舊減半（正控制：舊行為就是本次事故的樣子）。
③ 限流過了：前 N 次整批 429、之後 200 ⇒ 全部命中、退回逐一 0、減半 0、等待照順序。
④ 等完還是 429：等待用完就退回舊路徑（減半＋留給主迴圈），不會無窮迴圈。
⑤ 只有「整批全 429」才等：一批裡部分 429／503／逾時都不等；已命中的帳號不會被重問。
⑥ 中途才限流：前面的批次已命中，後面整批 429 ⇒ 只重問沒命中的，每個帳號恰好命中一次。
⑦ run_update 的 ⑤d 真的帶旗標；參數解析對得上。
⑧ 限流起訖的牆鐘：⏳ 帶時間、解除只印一次，等完還是 429 不可以印解除（#2521）。
用法：python scripts/fetch_soloq_update_rlwait_test.py
"""
import os, sys, io, re, importlib.util, contextlib

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SRC = os.path.join(HERE, "fetch_soloq_update.py")
OK = FAIL = 0
def check(name, cond, info=""):
    global OK, FAIL
    if cond: OK += 1; print(f"  ✓ {name}")
    else: FAIL += 1; print(f"  ✗ {name}  {info}")

if HERE not in sys.path: sys.path.insert(0, HERE)
def load(flags):
    argv0 = sys.argv; sys.argv = [SRC] + flags
    try:
        spec = importlib.util.spec_from_file_location("fsu_rl", SRC)
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
    finally: sys.argv = argv0

REAL = [os.path.join(ROOT, "soloq_match_index.js"), os.path.join(HERE, "soloq_accounts.json"),
        os.path.join(ROOT, "soloq_acc_lastgame.js"), os.path.join(ROOT, "soloq_matches")]
def snap():
    d = {}
    for p in REAL:
        if os.path.isdir(p): d[p] = sorted((f, os.stat(os.path.join(p, f)).st_mtime_ns) for f in os.listdir(p))
        elif os.path.exists(p): d[p] = (os.stat(p).st_mtime_ns, os.path.getsize(p))
        else: d[p] = None
    return d
SNAP0 = snap()

class FakePG:
    """rule(第幾次呼叫 從 1 起, puuid) → bad 值；0＝正常"""
    def __init__(self, rule): self.rule = rule; self.n = 0; self.asked = []; self.good = []
    def evaluate(self, js, args=None):
        self.n += 1; out = []
        for pu, tok, nt in args:
            self.asked.append(pu); b = self.rule(self.n, pu)
            if not b: self.good.append(pu)
            out.append({"id": None, "ms": [], "bad": b, "el": 100})
        return out

def setup(U, n=9):
    keys = [f"T|P{i}" for i in range(n)]
    idx = {"players": {k: {"f": f"p{i}.js", "role": "MIDDLE"} for i, k in enumerate(keys)}}
    accs = {k: [{"dpmPuuid": f"pu-{i}", "riotId": f"P{i}#1", "platform": "kr"}] for i, k in enumerate(keys)}
    U.load_player_file = lambda f: ("x", {"matches": [{"t": 5}]})
    return keys, idx, accs

def run(flags, rule, n=9, bs=4):
    U = load(flags); slept = []
    U.time.sleep, sl0 = (lambda s: slept.append(s)), U.time.sleep
    try:
        keys, idx, accs = setup(U, n); pg = FakePG(rule)
        with contextlib.redirect_stdout(io.StringIO()) as so:
            PRE, st = U.prefetch_batches(pg, keys, idx, accs, set(), bs=bs)
    finally: U.time.sleep = sl0
    return U, PRE, st, pg, slept, so.getvalue()

W = ["--rl-waits", "60,120,180"]

print("[②] 預設關（正控制：舊行為）")
U, PRE, st, pg, slept, out = run([], lambda c, pu: 429)
check("RL_WAITS 空", U.RL_WAITS == [])
check("全 429 ⇒ 不等、全部退回逐一、有減半（＝事故的樣子）", slept == [] and st["hit"] == 0 and st["fallback"] == 9 and st["halved"] >= 1, st)
check("沒帶旗標不印等待行", "⏳" not in out)

print("[③] 限流過了")
U, PRE, st, pg, slept, out = run(W, lambda c, pu: 429 if c <= 2 else 0)
check("解析成 [60,120,180]", U.RL_WAITS == [60, 120, 180], U.RL_WAITS)
check("等了 60、120", slept == [60, 120], slept)
check("全部命中 9、退回逐一 0、減半 0", (st["hit"], st["fallback"], st["halved"]) == (9, 0, 0), st)
check("被等掉的批次不計入 batches／sizes／secs", st["batches"] == 3 and st["sizes"] == [4, 4, 1] and len(st["secs"]) == 3, st)
check("統計有等待次數與秒數", st.get("rlwaits") == 2 and st.get("rlwait") == 180, st)
check("每個帳號都進 PRE", len(PRE) == 9)
check("日誌有 ⏳ 兩行", out.count("⏳") == 2, out)

print("[④] 等完還是 429")
U, PRE, st, pg, slept, out = run(W, lambda c, pu: 429)
check("等滿三次就不再等", slept == [60, 120, 180], slept)
check("退回舊路徑：命中 0、退回逐一 9、有減半", st["hit"] == 0 and st["fallback"] == 9 and st["halved"] >= 1, st)
check("迴圈有結束且呼叫次數有限", pg.n < 20, pg.n)

print("[⑤] 不是整批 429 就不等")
U, PRE, st, pg, slept, out = run(W, lambda c, pu: 429 if pu == "pu-4" else 0)
check("部分 429 ⇒ 不等、照舊減半", slept == [] and st["halved"] == 1 and st["hit"] == 8, st)
check("命中的沒被重問", len(pg.asked) == len(set(pg.asked)) == 9, pg.asked)
U, PRE, st, pg, slept, out = run(W, lambda c, pu: 503)
check("整批 503 ⇒ 不等（只等限流）", slept == [], slept)
U, PRE, st, pg, slept, out = run(W, lambda c, pu: -1)
check("整批逾時 ⇒ 不等、不減半", slept == [] and st["halved"] == 0 and st.get("net") == 9, st)

print("[⑥] 中途才限流")
U, PRE, st, pg, slept, out = run(W, lambda c, pu: 429 if c == 2 else 0)
check("等一次", slept == [60], slept)
check("每個帳號恰好命中一次", sorted(pg.good) == sorted(f"pu-{i}" for i in range(9)), pg.good)
check("第一批沒被重問（pu-0 只問一次）", pg.asked.count("pu-0") == 1, pg.asked)
check("第二批問兩次（pu-4 問兩次）", pg.asked.count("pu-4") == 2, pg.asked)

print("[⑧] 限流起訖的牆鐘（#2521）")
_ts = r"\[\d\d:\d\d:\d\d\]"
U, PRE, st, pg, slept, out = run(W, lambda c, pu: 429 if c <= 2 else 0)
_lines = [l for l in out.splitlines() if "⏳" in l]
check("每一行 ⏳ 都帶時間", len(_lines) == 2 and all(re.search(_ts + "$", l) for l in _lines), _lines)
check("解除恰好印一行、帶第一次 429 的時間", out.count("限流解除") == 1 and re.search(r"限流解除：\d\d:\d\d:\d\d .*第一次整批 429 在 \d\d:\d\d:\d\d", out), out)
check("統計記下起訖", re.fullmatch(r"\d\d:\d\d:\d\d", st.get("rl_first", "")) and re.fullmatch(r"\d\d:\d\d:\d\d", st.get("rl_clear", "")), st)
U, PRE, st, pg, slept, out = run(W, lambda c, pu: 429)
check("等完還是 429 ⇒ 不可以印解除", "限流解除" not in out and "rl_clear" not in st and st.get("rl_first"), out)
U, PRE, st, pg, slept, out = run(W, lambda c, pu: 0)
check("沒被限流 ⇒ 不印解除、不記時間", "限流解除" not in out and "rl_first" not in st, out)
U, PRE, st, pg, slept, out = run([], lambda c, pu: 429 if c <= 2 else 0)
check("沒帶旗標（不等待）⇒ 不印解除", "限流解除" not in out and "rl_first" not in st, out)
_d = io.open(os.path.join(HERE, "fetch_dpm_soloq_accounts.py"), encoding="utf-8").read()
_r = io.open(os.path.join(HERE, "resolve_obgg_dpmpuuid.py"), encoding="utf-8").read()
check("⑤ 的盤查與歸屬複查行有時間", "續等…[{time.strftime" in _d and "逐一重查 [{time.strftime" in _d)
check("⑤b 的盤查行有時間", "續等…[{time.strftime" in _r)
check("fetch_dpm 有 import time", re.search(r"^import .*\btime\b", _d, re.M))
check("resolve 有 import time", re.search(r"^import .*\btime\b", _r, re.M))

print("[⑦] 接線")
s = io.open(os.path.join(HERE, "run_update.py"), encoding="utf-8").read()
m = re.search(r'S\("fetch_soloq_update"[^)]*\)', s)
check("run_update ⑤d 帶 --rl-waits", m and '"--rl-waits", "60,120,180,240,300"' in m.group(0), m and m.group(0))
src = io.open(SRC, encoding="utf-8").read()
check("批次預抓那行會印等待（否則事後查不到）", "限流等待" in src)

print("[①] 正本沒動")
check("真實逐場檔／帳號檔／索引 mtime 沒變", snap() == SNAP0)

print(f"\n通過 {OK}／失敗 {FAIL}")
if FAIL: sys.exit(1)
print("全部通過 ✓")
