# -*- coding: utf-8 -*-
"""⑤d fetch_soloq_update 主迴圈熔斷（2026-09-22 線 3，精進迴圈 #199）——沙盒：假 playwright、暫存目錄、子程序不起、不打網路。

病灶：#198 讓單頁最多等 15s，但 dpm 整站掛住時每個帳號仍是 15＋1.5＋15＝31.5s × 兩百多個帳號，全在關鍵路徑上。
改動：**連續** DOWN_AFTER（預設 3）個帳號「真的打出去、重試仍失敗／evaluate 丟例外」⇒ 這一班剩下的帳號不再問 dpm；
熔斷後沒問到的帳號走 #200 的 pend（2026-09-22 #201 起；#199 原本是「整位不採用」）：批次已到手的帳號當班就收，
newestT 因此往前跳的那一刻把沒問到的帳號記進 data["pend"]；打 dpm 的兩支子程序也不起。穩態日誌一字不變。

① 模組層／純函式：DOWN_AFTER 預設 3、--down-after 吃得到、breaker_step 的歸零與門檻。
② dpm 全掛（循序）：只問前 3 個帳號（各 2 次）就停、其餘 8 個帳號 0 次請求、檔案全部原樣、兩行 ⚡、子程序不起。
③ 不連續不熔斷：失敗 4 個但中間都隔著成功 ⇒ 全部問完、沒有 ⚡、輸出與日誌跟舊版逐行相同。
④ 重試成功會歸零（2 敗＋重試成功＋2 敗 ⇒ 不熔斷；再多 1 敗 ⇒ 熔斷在第 3 個，同一位選手的下一個帳號也不問）。
⑤ 批次模式：批次命中**不歸零也不加**（夾在失敗中間照樣熔斷）；全命中的選手照收；「一個命中＋一個沒問到」的選手
   當班就收命中的那一半、沒問到的帳號記 pend（#201；釘 c87b736b 的舊版＝整位不採用、晚一班）；
   下一班（dpm 好了）從 pend 的起點補——包含比另一個帳號最新場還舊的那一場（不記 pend 就會永遠漏掉的那一場）；第三班逐位元不變。
⑥ evaluate 丟例外也算失敗（3 個連續 ⇒ 熔斷）。
⑦ --down-after 5 ⇒ 問 5 個才停。
⑧ 正控制（釘 OLDREV＝改動前那個 commit）：舊版對同一個全掛的假 dpm 把 11 個帳號全部問兩次、沒有 ⚡；乾淨資料新舊版輸出與日誌逐行相同。
⑨ 真實檔沒被動。
用法：python scripts/fetch_soloq_update_breaker_test.py
"""
import os, sys, io, re, json, shutil, tempfile, subprocess, importlib.util, contextlib, time as _time

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
OLDREV = "978c51f0"   # #199 改動之前的 HEAD（別寫 HEAD：commit 之後 HEAD 就是新版，見 DAILY #93）
OLDREV201 = "c87b736b"   # #201 改動之前的 HEAD（#200：熔斷後有帳號沒問到的選手「整位不採用」）
NEW = os.path.join(HERE, "fetch_soloq_update.py")
OK = FAIL = 0
def check(name, cond, info=""):
    global OK, FAIL
    if cond: OK += 1; print(f"  ✓ {name}")
    else: FAIL += 1; print(f"  ✗ {name}  {str(info)[:700]}")

def load(name, path, argv=None):
    a0 = sys.argv
    if argv is not None: sys.argv = [path] + list(argv)
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
    finally: sys.argv = a0

REAL = [os.path.join(ROOT, "soloq_match_index.js"), os.path.join(HERE, "soloq_accounts.json"),
        os.path.join(ROOT, "soloq_acc_lastgame.js"), os.path.join(ROOT, "csv_cache", "soloq_year_empty.json")]
def snap():
    d = {p: (os.path.getmtime(p), os.path.getsize(p)) if os.path.exists(p) else None for p in REAL}
    md = os.path.join(ROOT, "soloq_matches")
    d[md] = sorted((f, os.path.getmtime(os.path.join(md, f))) for f in os.listdir(md)) if os.path.isdir(md) else None
    return d
SNAP0 = snap()

# ───────── 假資料：8 位選手／11 個帳號＋1 位沒有逐場檔的新選手（T9|Z，用來看「新選手補全年」子程序起不起）─────────
def game(t, rid="X#1"):
    return {"t": t, "d": 1500, "c": "Ahri", "o": None, "w": True, "k": 5, "de": 2, "a": 7, "kp": 60, "sc": 80, "scr": 1,
            "pos": "MIDDLE", "su": [4, 14], "r": 8010, "rp": [8010, 0, 0, 0], "rs": [0, 0, 0], "rst": [0, 0, 0], "sk": [],
            "du": None, "dul": None, "duo": None, "rid": rid, "it": [], "st": [], "ib": [], "cs": 200,
            "gd15": 0, "dpm": 500, "tr": None, "lp": None, "xd15": 0, "fl2": None}
PLAYERS = [("T1|A", "MIDDLE", [game(1000)]), ("T2|B", "TOP", [game(2000)]), ("T3|C", "JUNGLE", []), ("T4|D", "BOTTOM", [game(100)]),
           ("T5|E", "UTILITY", [game(50)]), ("T6|F", "MIDDLE", [game(700)]), ("T7|G", "TOP", [game(10)]), ("T8|H", "JUNGLE", [game(4000)])]
ACCS = [("T1|A", "pu-a1", "A1#KR1"), ("T1|A", "pu-a2", "A2#KR1"), ("T2|B", "pu-b1", "B#KR1"), ("T3|C", "pu-c1", "C#KR1"),
        ("T4|D", "pu-d1", "D#KR1"), ("T5|E", "pu-e1", "E1#KR1"), ("T5|E", "pu-e2", "E2#KR1"), ("T6|F", "pu-f1", "F#KR1"),
        ("T7|G", "pu-g1", "G#KR1"), ("T8|H", "pu-h1", "H1#KR1"), ("T8|H", "pu-h2", "H2#KR1"), ("T9|Z", "pu-z1", "Z#KR1")]
IN_IDX = [a for a in ACCS if a[0] != "T9|Z"]   # 11 個
# H：h1 的新場 5000、h2 的新場 4500（比 5000 舊）——熔斷那一班只收 h1 的話 newestT 跳到 5000，h2 的 4500 下一班就永遠問不到了
DPM = {"pu-a1": ("A1", [game(1500, "A1#KR1"), game(1200, "A1#KR1"), game(900, "A1#KR1")]), "pu-a2": ("A2", [game(1300, "A2#KR1")]),
       "pu-b1": ("B", []), "pu-c1": ("C", [game(500, "C#KR1")]), "pu-d1": ("D", [game(3000, "D#KR1")]),
       "pu-e1": ("E1", [game(4000, "E1#KR1")]), "pu-e2": ("E2", [game(3900, "E2#KR1")]), "pu-f1": ("F", [game(800, "F#KR1")]),
       "pu-g1": ("G", [game(6000, "G#KR1")]), "pu-h1": ("H1", [game(5000, "H1#KR1")]), "pu-h2": ("H2", [game(4500, "H2#KR1")])}
ALL_PU = [a[1] for a in IN_IDX]

def make_sandbox(tmp):
    md = os.path.join(tmp, "soloq_matches"); os.makedirs(md)
    idx = {"players": {}}
    for i, (key, role, ms) in enumerate(PLAYERS, 1):
        f = f"p{i}.js"; idx["players"][key] = {"f": f, "role": role, "n": len(ms)}
        open(os.path.join(md, f), "w", encoding="utf-8").write(
            f"window.__sqLoad({json.dumps(key, ensure_ascii=False)},{json.dumps({'matches': ms}, ensure_ascii=False)});\n")
    open(os.path.join(tmp, "soloq_match_index.js"), "w", encoding="utf-8").write("window.SOLOQ_MATCH_IDX=" + json.dumps(idx) + ";\n")
    accs = [{"team": k.split("|")[0], "player": k.split("|")[1], "riotId": rid, "platform": "kr", "dpmPuuid": pu, "dpmSeen": "2000-01-01"}
            for k, pu, rid in ACCS]
    json.dump(accs, open(os.path.join(tmp, "soloq_accounts.json"), "w", encoding="utf-8"), ensure_ascii=False)

class FakeTime:
    def __init__(self): self.slept = 0.0; self.sleeps = []
    def time(self): return _time.time()
    def strftime(self, *a): return _time.strftime(*a)
    def sleep(self, s): self.slept += s; self.sleeps.append(s)

class FakePage:
    """always_bad：{pu: bad}＝批次、逐一都永遠 bad（帶半截結果）；batch_bad：{pu: bad}＝只在批次裡 bad、逐一問正常；
    once_bad：{pu: bad}＝逐一問的第一次 bad、重試就好；raise_on：{pu}＝逐一問直接丟例外。"""
    def __init__(self, U, always_bad=None, batch_bad=None, once_bad=None, raise_on=None):
        self.U = U; self.always_bad = always_bad or {}; self.batch_bad = batch_bad or {}
        self.once_bad = dict(once_bad or {}); self.raise_on = set(raise_on or ()); self.calls = []; self.since = []
    def goto(self, *a, **k): pass
    def on(self, *a, **k): pass
    def asked(self, pu): return [nt for p, nt in self.since if p == pu]   # #201：送給 dpm 的起點（批次＋逐一）
    def _one(self, args, batch):
        pu, tok, nt = args; self.calls.append(("b1" if batch else "n", pu)); self.since.append((pu, nt))
        name, ms = DPM[pu]; new = [g for g in ms if g["t"] > nt]
        if not batch and pu in self.raise_on: raise RuntimeError("Target closed（假的 evaluate 例外）")
        if pu in self.always_bad: return {"id": {"g": name, "t": "KR1"}, "ms": new, "bad": self.always_bad[pu]}
        if batch and (pu in self.batch_bad or pu in self.raise_on): return {"id": None, "ms": [], "bad": self.batch_bad.get(pu, -1)}
        if not batch and pu in self.once_bad: return {"id": None, "ms": [], "bad": self.once_bad.pop(pu)}
        return {"id": {"g": name, "t": "KR1"}, "ms": new, "bad": 0}
    def evaluate(self, js, args=None):
        if "top-teams" in js: return 200
        if js == getattr(self.U, "JS_BATCH", None):
            self.calls.append(("B", [a[0] for a in args])); return [self._one(a, True) for a in args]
        if js == self.U.JS_NEW: return self._one(args, False)
        raise AssertionError("未知的 evaluate：" + js[:60])
    def n_calls(self, kind, pu=None): return sum(1 for c in self.calls if c[0] == kind and (pu is None or c[1] == pu))
    def live(self): return [c[1] for c in self.calls if c[0] == "n"]

class FakeBrowser:
    def __init__(self, page): self.page = page
    def new_context(self, **k): return self
    def new_page(self): return self.page
    def close(self): pass
@contextlib.contextmanager
def fake_pw(): yield None

PATHS = ["IDXP", "OUTDIR", "ACCOUNTS", "ACC_LG_PATH", "EMPTY_PATH"]
def bind(U, tmp, page, batch, bs):
    U.IDXP = os.path.join(tmp, "soloq_match_index.js"); U.OUTDIR = os.path.join(tmp, "soloq_matches")
    U.ACCOUNTS = os.path.join(tmp, "soloq_accounts.json"); U.ACC_LG_PATH = os.path.join(tmp, "soloq_acc_lastgame.js")
    U.EMPTY_PATH = os.path.join(tmp, "soloq_year_empty.json")
    U.sync_playwright = fake_pw; U._launch_real = lambda p: FakeBrowser(page)
    U.comp_roles = lambda: {"d": "top"}   # T4|D 的資料庫位置（top）≠ 積分檔路線（bottom）⇒ 正常班次會起「重建錯路線選手」
    U.time = FakeTime(); U.MAXP = 0; U.CHILD = []
    U.load_year_empty = lambda path=None: {}
    U.run_child = lambda label, cmd, argv=None: U.CHILD.append((label, list(cmd)))
    U.USE_BATCH = batch; U.BATCH_NEW = bs

def leaks(U):
    """模組層任何路徑常數還指著真實 repo＝漏接；呼叫端要在 main() 之前中止（#188：抓到漏接一律中止，不要只記紅）"""
    bad = [n for n in PATHS if os.path.abspath(getattr(U, n)).lower().startswith(ROOT.lower())]
    for n, v in vars(U).items():   # 以後誰加了新的路徑常數（#179 LEDGER／#188 RNID 那種）也要在這裡被抓到
        if n.isupper() and n not in PATHS + ["HERE", "ROOT"] and isinstance(v, str) and os.path.isabs(v) and os.path.abspath(v).lower().startswith(ROOT.lower()):
            bad.append(n)
    if U.run_child.__module__ == U.__name__: bad.append("run_child")
    if U.sync_playwright is not fake_pw: bad.append("sync_playwright")
    return bad

TMPS = []
def run(src_path, batch=False, bs=4, tmp=None, load_argv=(), **page_kw):
    if tmp is None:
        tmp = tempfile.mkdtemp(prefix="fsu_brk_"); TMPS.append(tmp); make_sandbox(tmp)
    U = load("fsu_" + os.path.basename(tmp) + "_%d" % len(sys.modules), src_path, argv=list(load_argv))
    page = FakePage(U, **page_kw)
    bind(U, tmp, page, batch, bs)
    lk = leaks(U)
    if lk:
        print("  ✗ 沙盒漏接 %s ⇒ 中止（不呼叫 main，正本一個位元不碰）" % lk); sys.exit(1)
    argv0 = sys.argv; sys.argv = [src_path, "--no-rebuild"] + (["--batch"] if batch else [])
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf): U.main()
    finally: sys.argv = argv0
    out = {f: open(os.path.join(tmp, "soloq_matches", f), encoding="utf-8").read() for f in sorted(os.listdir(os.path.join(tmp, "soloq_matches")))}
    return U, page, buf.getvalue(), out, tmp

def ts(out, f):
    m = re.match(r'window\.__sqLoad\((.*)\);\s*$', out[f], re.S); return [g["t"] for g in json.loads("[" + m.group(1) + "]")[1]["matches"]]
def pend(out, f):
    """逐場檔 meta 的 pend（沒有＝{}）；#201：熔斷後沒問到的帳號記在這裡"""
    m = re.match(r'window\.__sqLoad\((.*)\);\s*$', out[f], re.S); return json.loads("[" + m.group(1) + "]")[1].get("pend") or {}
def norm(txt):
    """照牆鐘排序的「最久的 N 位」那行不比（#198：沙盒裡每位 0.00x 秒，列到誰、順序都看牆鐘）；秒數抹平。
    #200 刻意多印的「↺」行（個別帳號沒問到時記 pend）剝掉再比——那是 pend 測試的事，這裡守的是「熔斷沒動到別的」"""
    return [l for l in re.sub(r"\d+(\.\d+)?s", "Ns", txt).splitlines() if not l.lstrip().startswith(("最久的", "↺"))]
def no_pend(out):
    """#200 刻意多寫的 data["pend"] 剝掉再跟舊版逐檔比（其餘位元組要一樣：同一套 json.dumps 重新序列化）"""
    res = {}
    for f, txt in out.items():
        m = re.match(r'window\.__sqLoad\((.*)\);\s*$', txt, re.S); key, data = json.loads("[" + m.group(1) + "]")
        if "pend" not in data: res[f] = txt; continue
        data.pop("pend")
        res[f] = f"window.__sqLoad({json.dumps(key, ensure_ascii=False)},{json.dumps(data, ensure_ascii=False)});\n"
    return res
labels = lambda U: [c[0] for c in U.CHILD]
ORIG = {f"p{i}.js": [g["t"] for g in ms] for i, (_, _, ms) in enumerate(PLAYERS, 1)}
ORIG_TXT = {f"p{i}.js": f"window.__sqLoad({json.dumps(key, ensure_ascii=False)},{json.dumps({'matches': ms}, ensure_ascii=False)});\n"
            for i, (key, _, ms) in enumerate(PLAYERS, 1)}   # make_sandbox 種下去的原文（#201：沒被越過的檔要逐位元原樣）
ALL_BAD = {pu: -1 for pu in ALL_PU}

# ───────── ① 模組層／純函式 ─────────
print("[1] 模組層／純函式")
U0 = load("fsu_brk_default", NEW, argv=[])
check("DOWN_AFTER 預設 3、有 breaker_step", getattr(U0, "DOWN_AFTER", None) == 3 and callable(getattr(U0, "breaker_step", None)))
U5 = load("fsu_brk_5", NEW, argv=["--down-after", "5"])
check("--down-after 5 吃得到", U5.DOWN_AFTER == 5)
bs_ = U0.breaker_step
check("breaker_step：失敗 ＋1、第 3 個到門檻（0→1→2→3）", [bs_(0, False), bs_(1, False), bs_(2, False)] == [(1, False), (2, False), (3, True)])
check("breaker_step：成功歸零（2→0、不到門檻）", bs_(2, True) == (0, False))
check("breaker_step：after 參數蓋過預設（after=1 ⇒ 第 1 個就到）", bs_(0, False, after=1) == (1, True) and bs_(3, False, after=5) == (4, False))

# ───────── ② dpm 全掛（循序）─────────
print("[2] dpm 全掛（循序、每個帳號永遠 -1）")
U, p, txt, out, _ = run(NEW, always_bad=ALL_BAD)
check("只問前 3 個帳號、各 2 次（a1、a2、b1）", p.live() == ["pu-a1", "pu-a1", "pu-a2", "pu-a2", "pu-b1", "pu-b1"], p.live())
check("其餘 8 個帳號 0 次請求", all(p.n_calls("n", pu) == 0 for pu in ALL_PU[3:]), {pu: p.n_calls("n", pu) for pu in ALL_PU[3:]})
check("只睡了 3 次 1.5s（不是 11 次）", U.time.sleeps.count(1.5) == 3, U.time.sleeps)
check("8 個逐場檔全部原樣（半截結果沒被採用）", {f: ts(out, f) for f in out} == ORIG, {f: ts(out, f) for f in out})
check("日誌：⚡ 熔斷那行指名「連續 3 個帳號」", "⚡ dpm 熔斷：連續 3 個帳號問不到" in txt and txt.count("⚡ dpm 熔斷：連續") == 1, txt)
check("日誌：小結「8 個帳號這一班沒問（6 位選手）」＋「不丟資料」", "⚡ dpm 熔斷小結：8 個帳號這一班沒問（6 位選手）；" in txt and "其餘下一班從原 newestT 再抓、不丟資料" in txt, txt)
check("#201 全掛＝沒有任何帳號帶進新場 ⇒ 沒有檔多出 pend 鍵、8 個檔逐位元原樣、沒有 ↺（沒被越過就不記）", out == ORIG_TXT and '"pend"' not in "".join(out.values()) and "↺" not in txt,
      [f for f in out if out[f] != ORIG_TXT.get(f)])
check("打 dpm 的兩支子程序都不起、日誌指名（重建錯路線 1 位／新選手 1 位）", labels(U) == [] and "這一班不起「重建錯路線選手」（1 位）／「新選手補全年」（1 位）" in txt, (labels(U), txt[-500:]))
check("完成行照印（0 位有新戰績、共 +0 場）", "完成：0 位有新戰績、共 +0 場。" in txt, txt[-400:])

# ───────── ③ 不連續不熔斷 ─────────
print("[3] 不連續：4 個帳號永遠 -1，但中間都隔著成功 ⇒ 不熔斷")
SCAT = {"pu-a1": -1, "pu-c1": -1, "pu-e1": -1, "pu-g1": -1}
U, p, txt3, out3, _ = run(NEW, always_bad=SCAT)
check("11 個帳號全部問到（失敗的 4 個各 2 次）", all(p.n_calls("n", pu) == (2 if pu in SCAT else 1) for pu in ALL_PU), {pu: p.n_calls("n", pu) for pu in ALL_PU})
check("沒有任何 ⚡", "⚡" not in txt3, txt3)
check("子程序照起（重建錯路線＋新選手補全年）", labels(U) == ["重建錯路線選手", "新選手補全年"], labels(U))
check("沒失敗的帳號照收（A 收 a2 的 1300、E 收 e2 的 3900、H 兩個都收）", ts(out3, "p1.js") == [1300, 1000] and ts(out3, "p5.js") == [3900, 50] and ts(out3, "p8.js") == [5000, 4500, 4000],
      (ts(out3, "p1.js"), ts(out3, "p5.js"), ts(out3, "p8.js")))

# ───────── ④ 重試成功歸零 ─────────
print("[4] 重試成功會歸零")
U, p, txt4, out4, _ = run(NEW, always_bad={"pu-a1": -1, "pu-a2": 503, "pu-c1": -1, "pu-d1": 429}, once_bad={"pu-b1": -1})
check("2 敗＋b1 重試成功＋2 敗 ⇒ 不熔斷、11 個都問到", "⚡" not in txt4 and all(p.n_calls("n", pu) >= 1 for pu in ALL_PU), (txt4[-300:], p.live()))
check("b1 真的是第一次 bad、重試才好（問了 2 次）", p.n_calls("n", "pu-b1") == 2)
U, p, txt4b, out4b, _ = run(NEW, always_bad={"pu-a1": -1, "pu-a2": 503, "pu-c1": -1, "pu-d1": 429, "pu-e1": 500}, once_bad={"pu-b1": -1})
check("再多 1 敗（c1、d1、e1 連續）⇒ 熔斷在 e1；HTTP 狀態的 bad（429／500）一樣算", "⚡ dpm 熔斷：連續 3 個帳號問不到" in txt4b and p.n_calls("n", "pu-e1") == 2, txt4b)
check("同一位選手的下一個帳號（e2）也不問、之後 f1 g1 h1 h2 都不問", all(p.n_calls("n", pu) == 0 for pu in ["pu-e2", "pu-f1", "pu-g1", "pu-h1", "pu-h2"]), p.live())
check("小結：5 個帳號沒問（4 位選手＝E、F、G、H）；循序模式沒有已到手的 ⇒ 沒有檔多出 pend", "⚡ dpm 熔斷小結：5 個帳號這一班沒問（4 位選手）" in txt4b and '"pend"' not in "".join(out4b.values()), txt4b)

# ───────── ⑤ 批次模式 ─────────
print("[5] 批次模式：命中不歸零／全命中照收／一半沒問到 ⇒ 命中的當班收、沒問到的記 pend（#201）／下一班補得回來")
U, p, txt5, out5, tmp5 = run(NEW, batch=True, bs=4, always_bad={"pu-a1": -1, "pu-b1": -1, "pu-c1": -1}, batch_bad={"pu-h2": -1})
check("a1 失敗 → a2 批次命中（不歸零）→ b1、c1 失敗 ⇒ 熔斷", "⚡ dpm 熔斷：連續 3 個帳號問不到" in txt5 and p.live() == ["pu-a1", "pu-a1", "pu-b1", "pu-b1", "pu-c1", "pu-c1"], (p.live(), txt5))
check("熔斷前：A 照 #68 收 a2 命中的 1300", ts(out5, "p1.js") == [1300, 1000], ts(out5, "p1.js"))
check("熔斷後：全命中的選手照收（D 3000、E 4000＋3900、F 800、G 6000）", ts(out5, "p4.js") == [3000, 100] and ts(out5, "p5.js") == [4000, 3900, 50] and ts(out5, "p6.js") == [800, 700] and ts(out5, "p7.js") == [6000, 10],
      {f: ts(out5, f) for f in out5})
check("熔斷後：h2 沒問（逐一 0 次）", p.n_calls("n", "pu-h2") == 0)
check("#201 H 當班就收 h1 命中的 5000（#199／#200 是整位不採用、檔案原樣 [4000]）", ts(out5, "p8.js") == [5000, 4000], ts(out5, "p8.js"))
check("#201 H 的逐場檔記下 pend＝{pu-h2: 4000}（h2 沒問到、newestT 要從 4000 跳到 5000 的那一刻）", pend(out5, "p8.js") == {"pu-h2": 4000}, pend(out5, "p8.js"))
check("日誌：H 照常印「+1 新（共 2）」、不再有「這一班不採用」", re.search(r"\[8/8\] T8\|H  \+1 新（共 2）", txt5) and "這一班不採用" not in txt5, txt5)
check("小結：1 個帳號沒問（1 位選手）＋↺ 小結「新記下 2 個」（a1 重試仍失敗、h2 熔斷後沒問）", "⚡ dpm 熔斷小結：1 個帳號這一班沒問（1 位選手）" in txt5 and "這一班補問成功 0 個、撿回原本會漏掉的舊場次 0 場；新記下 2 個" in txt5,
      [l for l in txt5.splitlines() if "⚡" in l or "↺" in l])
check("沒被越過的不記：B、C 的帳號也沒問到、但沒有別的帳號帶新場 ⇒ 檔案逐位元原樣；只有 A、H 兩個檔有 pend", out5["p2.js"] == ORIG_TXT["p2.js"] and out5["p3.js"] == ORIG_TXT["p3.js"]
      and sorted(f for f in out5 if pend(out5, f)) == ["p1.js", "p8.js"], sorted(f for f in out5 if pend(out5, f)))
U2, p2, txt5b, out5b, _ = run(NEW, batch=True, bs=4, tmp=tmp5)   # 下一班：同一個沙盒、dpm 好了
check("下一班：h2 從 pend 的起點 4000 問（不是 newestT 5000）", p2.asked("pu-h2") == [4000] and p2.asked("pu-h1") == [5000], (p2.asked("pu-h2"), p2.asked("pu-h1")))
check("下一班：H 兩個帳號都補回來，**包含 4500**（不記 pend 的話 h2 從 5000 問、4500 永遠漏掉）", ts(out5b, "p8.js") == [5000, 4500, 4000], ts(out5b, "p8.js"))
check("下一班：H 的 pend 清掉、↺ 行指名 H2「1 場（其中 1 場比檔內最新一場舊」", pend(out5b, "p8.js") == {} and '"pend"' not in out5b["p8.js"]
      and re.search(r"↺ H2#KR1 之前沒問到、這次從當時的起點問成功：1 場（其中 1 場比檔內最新一場舊", txt5b), [l for l in txt5b.splitlines() if "↺" in l])
check("下一班：C 補回 500、沒有 ⚡、子程序照起", ts(out5b, "p3.js") == [500] and "⚡" not in txt5b and labels(U2) == ["重建錯路線選手", "新選手補全年"], (ts(out5b, "p3.js"), labels(U2)))
check("#200 補上的洞：A 在熔斷前收了 a2 的 1300（newestT 跳到 1300），下一班 a1 從當時的起點補 ⇒ **1200 也回來**（#199 當時實測 [1500, 1300, 1000]）",
      ts(out5b, "p1.js") == [1500, 1300, 1200, 1000], ts(out5b, "p1.js"))
U3, p3, txt5c, out5c, _ = run(NEW, batch=True, bs=4, tmp=tmp5)   # 第三班：穩態
check("第三班（穩態）：8 個檔逐位元不變、沒有任何檔還留著 pend、日誌沒有 ⚡／↺", out5c == out5b and '"pend"' not in "".join(out5c.values()) and "⚡" not in txt5c and "↺" not in txt5c,
      [f for f in out5c if out5c[f] != out5b.get(f)])

# ───────── ⑥ evaluate 丟例外 ─────────
print("[6] evaluate 丟例外也算失敗")
U, p, txt6, out6, _ = run(NEW, raise_on={"pu-a1", "pu-a2", "pu-b1"})
check("3 個連續丟例外 ⇒ 熔斷、各只問 1 次（例外不重試，照舊）、其餘不問", "⚡ dpm 熔斷：連續 3 個帳號問不到" in txt6 and p.live() == ["pu-a1", "pu-a2", "pu-b1"], (p.live(), txt6))
check("「抓錯」照印 3 行", txt6.count(" 抓錯 ") == 3, txt6)
U, p, txt6b, out6b, _ = run(NEW, raise_on={"pu-a1", "pu-c1", "pu-e1"})
check("不連續的例外 ⇒ 不熔斷、其餘照收", "⚡" not in txt6b and ts(out6b, "p4.js") == [3000, 100] and ts(out6b, "p8.js") == [5000, 4500, 4000], txt6b)

# ───────── ⑦ --down-after ─────────
print("[7] --down-after 5")
U, p, txt7, out7, _ = run(NEW, load_argv=["--down-after", "5"], always_bad=ALL_BAD)
check("問 5 個帳號（各 2 次）才停、日誌寫「連續 5 個」", p.live() == [pu for pu in ALL_PU[:5] for _ in (0, 1)] and "連續 5 個帳號問不到" in txt7, (p.live(), txt7))

# ───────── ⑧ 正控制：舊版 ─────────
print("[8] 正控制：釘 %s 的舊版" % OLDREV)
old_src = subprocess.run(["git", "-C", ROOT, "show", f"{OLDREV}:scripts/fetch_soloq_update.py"], capture_output=True, text=True, encoding="utf-8").stdout
check("舊版拿得到、而且真的沒有 DOWN_AFTER／breaker_step（不是早就有）", bool(old_src) and "DOWN_AFTER" not in old_src and "breaker_step" not in old_src)
if old_src:
    oldf = os.path.join(tempfile.gettempdir(), "fsu_brk_old.py")
    open(oldf, "w", encoding="utf-8").write(old_src)
    Uo, po, txt_o, out_o, _ = run(oldf, always_bad=ALL_BAD)
    check("舊版對同一個全掛的假 dpm：11 個帳號全部問 2 次（22 次請求、睡 11 次 1.5s）、沒有 ⚡",
          all(po.n_calls("n", pu) == 2 for pu in ALL_PU) and Uo.time.sleeps.count(1.5) == 11 and "⚡" not in txt_o, (po.live(), Uo.time.sleeps))
    check("舊版全掛時仍起兩支打 dpm 的子程序", labels(Uo) == ["重建錯路線選手", "新選手補全年"], labels(Uo))
    Uo3, po3, txt_o3, out_o3, _ = run(oldf, always_bad=SCAT)
    check("不連續失敗：新舊版輸出逐檔相同、日誌逐行相同（沒熔斷＝行為一字不變；#200 的 pend 鍵與 ↺ 行剝掉再比）", out_o3 == no_pend(out3) and norm(txt_o3) == norm(txt3),
          [k for k in out3 if no_pend(out3)[k] != out_o3.get(k)] + [x for x in norm(txt_o3) if x not in norm(txt3)] + [x for x in norm(txt3) if x not in norm(txt_o3)])
    check("剝掉的東西真的存在、而且只在有帳號沒問到又往前跳的那兩位（A、E）——不是整批都多了鍵", sorted(f for f in out3 if no_pend(out3)[f] != out3[f]) == ["p1.js", "p5.js"] and txt3.count("↺") == 1,
          (sorted(f for f in out3 if no_pend(out3)[f] != out3[f]), txt3.count("↺")))
    for b in (False, True):
        Uoc, poc, txt_oc, out_oc, _ = run(oldf, batch=b)
        Unc, pnc, txt_nc, out_nc, _ = run(NEW, batch=b)
        check("乾淨資料（%s）：新舊版輸出逐檔相同、日誌逐行相同（穩態一字不變）" % ("批次" if b else "循序"), out_oc == out_nc and norm(txt_oc) == norm(txt_nc),
              [k for k in out_oc if out_oc[k] != out_nc.get(k)] + [x for x in norm(txt_oc) if x not in norm(txt_nc)] + [x for x in norm(txt_nc) if x not in norm(txt_oc)])
    Uo5, po5, txt_o5, out_o5, tmp_o5 = run(oldf, batch=True, bs=4, always_bad={"pu-a1": -1, "pu-b1": -1, "pu-c1": -1}, batch_bad={"pu-h2": -1})
    check("舊版同一個批次情境：h2 照問（沒有熔斷可言）⇒ H 當班就 [5000, 4500, 4000]", po5.n_calls("n", "pu-h2") == 1 and ts(out_o5, "p8.js") == [5000, 4500, 4000], ts(out_o5, "p8.js"))

# ───────── ⑧b 正控制：#201 之前（整位不採用）─────────
print("[8b] 正控制：釘 %s（#200：熔斷後有帳號沒問到的選手整位不採用）" % OLDREV201)
old201 = subprocess.run(["git", "-C", ROOT, "show", f"{OLDREV201}:scripts/fetch_soloq_update.py"], capture_output=True, text=True, encoding="utf-8").stdout
check("#200 那版拿得到、而且真的是「整位不採用」那一版（有那句日誌、熔斷那行沒有 _pfail.append）", bool(old201) and "這一班不採用" in old201 and "_NDOWN += 1; continue" in old201)
if old201:
    oldf201 = os.path.join(tempfile.gettempdir(), "fsu_brk_old201.py")
    open(oldf201, "w", encoding="utf-8").write(old201)
    Uq, pq, txt_q, out_q, tmp_q = run(oldf201, batch=True, bs=4, always_bad={"pu-a1": -1, "pu-b1": -1, "pu-c1": -1}, batch_bad={"pu-h2": -1})
    check("#200 那版同一個情境：H 當班檔案原樣 [4000]、沒有 pend、日誌說「這一班不採用」（＝新版的 [5000, 4000] 是 #201 帶來的）",
          ts(out_q, "p8.js") == [4000] and pend(out_q, "p8.js") == {} and "已到手的 +1 場這一班不採用" in txt_q, (ts(out_q, "p8.js"), txt_q[-400:]))
    check("除了 H，其餘 7 個檔新舊版當班逐位元相同（#201 只動到「熔斷後有帳號沒問到」的那一位）", all(out_q[f] == out5[f] for f in out5 if f != "p8.js"), [f for f in out5 if f != "p8.js" and out_q[f] != out5[f]])
    Uq2, pq2, txt_q2, out_q2, _ = run(oldf201, batch=True, bs=4, tmp=tmp_q)
    check("下一班殊途同歸：新舊版 8 位選手的場次清單完全相同（新版只是早一班收到 5000、沒有多收也沒有少收）", {f: ts(out_q2, f) for f in out_q2} == {f: ts(out5b, f) for f in out5b},
          {f: (ts(out_q2, f), ts(out5b, f)) for f in out5b if ts(out_q2, f) != ts(out5b, f)})
    Uqc, pqc, txt_qc, out_qc, _ = run(oldf201, batch=True, bs=4)
    Unc2, pnc2, txt_nc2, out_nc2, _ = run(NEW, batch=True, bs=4)
    check("乾淨資料（批次）：#200 那版與新版輸出逐檔相同、日誌逐行相同（穩態一字不變）", out_qc == out_nc2 and norm(txt_qc) == norm(txt_nc2),
          [k for k in out_qc if out_qc[k] != out_nc2.get(k)] + [x for x in norm(txt_qc) if x not in norm(txt_nc2)] + [x for x in norm(txt_nc2) if x not in norm(txt_qc)])

# ───────── ⑨ 真實檔 ─────────
print("[9] 真實檔沒被動")
check("真實 index／accounts／acc_lastgame／year_empty／soloq_matches 目錄 mtime 全部不變", snap() == SNAP0, [k for k in SNAP0 if SNAP0[k] != snap().get(k)])
for t in TMPS: shutil.rmtree(t, ignore_errors=True)
print(f"\n{OK} 通過／{FAIL} 失敗")
sys.exit(1 if FAIL else 0)
