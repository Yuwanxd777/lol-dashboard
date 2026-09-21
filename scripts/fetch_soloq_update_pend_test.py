# -*- coding: utf-8 -*-
"""⑤d fetch_soloq_update 的 data["pend"]（2026-09-22 線 3，精進迴圈 #200）——沙盒：假 playwright、暫存目錄、子程序不起、不打網路。

病灶（#68 起就有）：個別帳號「重試仍失敗／抓錯」⇒ 這輪不採用、下輪再補；但逐場檔的 newestT 是整位共用的，同一位選手別的帳號
當班帶進新場次 ⇒ newestT 往前跳 ⇒ 下一班問那個失敗的帳號只問得到比新 newestT 更新的，夾在中間的場次永遠補不回來。
改動：newestT 要往前跳的那一刻，把沒問到的帳號記進逐場檔 meta data["pend"]={dpmPuuid: 那時的 newestT}；之後問那個帳號
一律從 min(newestT, pend) 問起、問成功才清；批次預抓同一個起點；有 pend 的帳號不被「牌位沒動」跳過。穩態檔案與日誌一字不變。

① 純函式：pend_of 的形狀防呆／since_of／plan_accounts（pend 空＝跟 split_static_accounts 一樣）／with_pend（穩態回原物件、放在 matches 前面）。
② 洞補上了（循序）：第 1 班 a1 沒問到、a2 帶進 1300 ⇒ 記 pend；第 2 班 a1 從 1000 問起 ⇒ 1200 回來、pend 清掉；第 3 班穩態。
③ 批次模式：批次預抓用同一個起點（看批次送出去的參數）、命中就清。
④ 連續兩班沒問到：pend 留最舊的起點，不被後來的 newestT 蓋掉。
⑤ newestT 沒往前跳 ⇒ 不記 pend、檔案一個位元不動、跟舊版逐檔逐行相同。
⑥ 「牌位沒動」的帳號有 pend ⇒ 照問（--changed 真的走 main；沒有 pend 的靜止帳號照樣跳過＝對照）。
⑦ 熔斷整位不採用 ⇒ pend 不動（補問到手的也一起丟了，清掉就真的漏了）；下一班補得回來。
⑧ 補問回來的場次跟檔內重複 ⇒「+N 新」不重複計。
⑨ 檔裡的 pend 形狀壞掉 ⇒ 當沒有、下次寫檔順手清掉。
⑩ clean_soloq_matches.fast_rids（真的那支）讀帶 pend 的檔仍走快路徑、結果跟慢路徑相同；對照：pend 放在 src 後面它就丟例外。
⑪ 正控制（釘 OLDREV＝改動前那個 commit）：舊版同樣兩班 ⇒ 1200 漏掉；乾淨資料新舊版輸出逐檔相同、日誌逐行相同。
⑫ 真實檔沒被動。
用法：python scripts/fetch_soloq_update_pend_test.py
"""
import os, sys, io, re, json, copy, shutil, tempfile, subprocess, importlib.util, contextlib, time as _time

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
OLDREV = "33587174"   # #200 改動之前的 HEAD（別寫 HEAD：commit 之後 HEAD 就是新版，見 DAILY #93）
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

REAL = [os.path.join(ROOT, "soloq_match_index.js"), os.path.join(HERE, "soloq_accounts.json"), os.path.join(HERE, "soloq_played.json"),
        os.path.join(ROOT, "soloq_acc_lastgame.js"), os.path.join(ROOT, "csv_cache", "soloq_year_empty.json")]
def snap():
    d = {p: (os.path.getmtime(p), os.path.getsize(p)) if os.path.exists(p) else None for p in REAL}
    md = os.path.join(ROOT, "soloq_matches")
    d[md] = sorted((f, os.path.getmtime(os.path.join(md, f))) for f in os.listdir(md)) if os.path.isdir(md) else None
    return d
SNAP0 = snap()

# ───────── 假資料（跟 breaker 測試同一批人）─────────
def game(t, rid="X#1"):
    return {"t": t, "d": 1500, "c": "Ahri", "o": None, "w": True, "k": 5, "de": 2, "a": 7, "kp": 60, "sc": 80, "scr": 1,
            "pos": "MIDDLE", "su": [4, 14], "r": 8010, "rp": [8010, 0, 0, 0], "rs": [0, 0, 0], "rst": [0, 0, 0], "sk": [],
            "du": None, "dul": None, "duo": None, "rid": rid, "it": [], "st": [], "ib": [], "cs": 200,
            "gd15": 0, "dpm": 500, "tr": None, "lp": None, "xd15": 0, "fl2": None}
PLAYERS = [("T1|A", "MIDDLE", [game(1000)]), ("T2|B", "TOP", [game(2000)]), ("T3|C", "JUNGLE", []), ("T4|D", "BOTTOM", [game(100)]),
           ("T5|E", "UTILITY", [game(50)]), ("T6|F", "MIDDLE", [game(700)]), ("T7|G", "TOP", [game(10)]), ("T8|H", "JUNGLE", [game(4000)])]
ACCS = [("T1|A", "pu-a1", "A1#KR1"), ("T1|A", "pu-a2", "A2#KR1"), ("T2|B", "pu-b1", "B#KR1"), ("T3|C", "pu-c1", "C#KR1"),
        ("T4|D", "pu-d1", "D#KR1"), ("T5|E", "pu-e1", "E1#KR1"), ("T5|E", "pu-e2", "E2#KR1"), ("T6|F", "pu-f1", "F#KR1"),
        ("T7|G", "pu-g1", "G#KR1"), ("T8|H", "pu-h1", "H1#KR1"), ("T8|H", "pu-h2", "H2#KR1")]
# A：a1 有 1500、1200、900；a2 有 1300。第 1 班只收到 a2 ⇒ newestT＝1300 ⇒ 舊版下一班問 a1 只拿得到 1500，**1200 永遠漏掉**
DPM0 = {"pu-a1": ("A1", [game(1500, "A1#KR1"), game(1200, "A1#KR1"), game(900, "A1#KR1")]), "pu-a2": ("A2", [game(1300, "A2#KR1")]),
        "pu-b1": ("B", []), "pu-c1": ("C", [game(500, "C#KR1")]), "pu-d1": ("D", [game(3000, "D#KR1")]),
        "pu-e1": ("E1", [game(4000, "E1#KR1")]), "pu-e2": ("E2", [game(3900, "E2#KR1")]), "pu-f1": ("F", [game(800, "F#KR1")]),
        "pu-g1": ("G", [game(6000, "G#KR1")]), "pu-h1": ("H1", [game(5000, "H1#KR1")]), "pu-h2": ("H2", [game(4500, "H2#KR1")])}
ALL_PU = [a[1] for a in ACCS]

def write_pf(tmp, f, key, data):
    open(os.path.join(tmp, "soloq_matches", f), "w", encoding="utf-8").write(
        f"window.__sqLoad({json.dumps(key, ensure_ascii=False)},{json.dumps(data, ensure_ascii=False)});\n")
def make_sandbox(tmp, files=None):
    """files：{'p1.js': data dict}＝蓋掉預設的逐場檔內容（種 pend 用）"""
    os.makedirs(os.path.join(tmp, "soloq_matches"))
    idx = {"players": {}}
    for i, (key, role, ms) in enumerate(PLAYERS, 1):
        f = f"p{i}.js"; data = (files or {}).get(f) or {"matches": ms}
        idx["players"][key] = {"f": f, "role": role, "n": len(data.get("matches") or [])}
        write_pf(tmp, f, key, data)
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
    """always_bad：{pu: bad}＝批次、逐一都永遠 bad（帶半截結果）；batch_bad：{pu: bad}＝只在批次裡 bad；raise_on：{pu}＝逐一問丟例外。
    since：每一次請求送出去的起點（這支測試的主角）——[(種類, pu, nt)]，種類 n＝逐一、b＝批次裡的一個。"""
    def __init__(self, U, dpm=None, always_bad=None, batch_bad=None, raise_on=None):
        self.U = U; self.dpm = dpm or DPM0; self.always_bad = always_bad or {}; self.batch_bad = batch_bad or {}
        self.raise_on = set(raise_on or ()); self.since = []
    def goto(self, *a, **k): pass
    def on(self, *a, **k): pass
    def _one(self, args, batch):
        pu, tok, nt = args; self.since.append(("b" if batch else "n", pu, nt))
        name, ms = self.dpm[pu]; new = [g for g in ms if g["t"] > nt]
        if not batch and pu in self.raise_on: raise RuntimeError("Target closed（假的 evaluate 例外）")
        if pu in self.always_bad: return {"id": {"g": name, "t": "KR1"}, "ms": new, "bad": self.always_bad[pu]}
        if batch and (pu in self.batch_bad or pu in self.raise_on): return {"id": None, "ms": [], "bad": self.batch_bad.get(pu, -1)}
        return {"id": {"g": name, "t": "KR1"}, "ms": new, "bad": 0}
    def evaluate(self, js, args=None):
        if "top-teams" in js: return 200
        if js == getattr(self.U, "JS_BATCH", None): return [self._one(a, True) for a in args]
        if js == self.U.JS_NEW: return self._one(args, False)
        raise AssertionError("未知的 evaluate：" + js[:60])
    def asked(self, pu, kind=None): return [nt for k, p, nt in self.since if p == pu and (kind is None or k == kind)]

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
    U.HERE = tmp   # --changed 會讀 HERE/soloq_played.json（⑥）；子程序的路徑也從 HERE 組，但 run_child 已經換成假的
    U.sync_playwright = fake_pw; U._launch_real = lambda p: FakeBrowser(page)
    U.comp_roles = lambda: {}
    U.time = FakeTime(); U.MAXP = 0; U.CHILD = []
    U.load_year_empty = lambda path=None: {}
    U.run_child = lambda label, cmd, argv=None: U.CHILD.append((label, list(cmd)))
    U.USE_BATCH = batch; U.BATCH_NEW = bs

def leaks(U):
    """模組層任何路徑常數還指著真實 repo＝漏接；呼叫端要在 main() 之前中止（#188：抓到漏接一律中止，不要只記紅）"""
    bad = [n for n in PATHS + ["HERE"] if os.path.abspath(getattr(U, n)).lower().startswith(ROOT.lower())]
    for n, v in vars(U).items():
        if n.isupper() and n not in PATHS + ["HERE", "ROOT"] and isinstance(v, str) and os.path.isabs(v) and os.path.abspath(v).lower().startswith(ROOT.lower()):
            bad.append(n)
    if U.run_child.__module__ == U.__name__: bad.append("run_child")
    if U.sync_playwright is not fake_pw: bad.append("sync_playwright")
    return bad

TMPS = []
def run(src_path, batch=False, bs=4, tmp=None, files=None, changed=None, **page_kw):
    if tmp is None:
        tmp = tempfile.mkdtemp(prefix="fsu_pend_"); TMPS.append(tmp); make_sandbox(tmp, files)
    if changed is not None: json.dump(changed, open(os.path.join(tmp, "soloq_played.json"), "w", encoding="utf-8"))
    U = load("fsu_" + os.path.basename(tmp) + "_%d" % len(sys.modules), src_path, argv=[])
    page = FakePage(U, **page_kw)
    bind(U, tmp, page, batch, bs)
    lk = leaks(U)
    if lk:
        print("  ✗ 沙盒漏接 %s ⇒ 中止（不呼叫 main，正本一個位元不碰）" % lk); sys.exit(1)
    argv0 = sys.argv; sys.argv = [src_path, "--no-rebuild"] + (["--batch"] if batch else []) + (["--changed"] if changed is not None else [])
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf): U.main()
    finally: sys.argv = argv0
    out = {f: open(os.path.join(tmp, "soloq_matches", f), encoding="utf-8").read() for f in sorted(os.listdir(os.path.join(tmp, "soloq_matches")))}
    return U, page, buf.getvalue(), out, tmp

def data_of(out, f):
    m = re.match(r'window\.__sqLoad\((.*)\);\s*$', out[f], re.S); return json.loads("[" + m.group(1) + "]")[1]
ts = lambda out, f: [g["t"] for g in data_of(out, f)["matches"]]
def norm(txt):
    return [l for l in re.sub(r"\d+(\.\d+)?s", "Ns", txt).splitlines() if not l.lstrip().startswith("最久的")]

# ───────── ① 純函式 ─────────
print("[1] 純函式")
U0 = load("fsu_pend_default", NEW, argv=[])
for fn in ("pend_of", "since_of", "plan_accounts", "with_pend"):
    if not callable(getattr(U0, fn, None)):
        print("  ✗ 模組沒有 %s ⇒ 這支測試沒有東西可測，中止" % fn); sys.exit(1)
check("pend_of：正常形狀原樣回來", U0.pend_of({"pend": {"pu-x": 123, "pu-y": 4.5}}) == {"pu-x": 123, "pu-y": 4.5})
check("pend_of：沒有鍵／None／list／字串／data 不是 dict ⇒ {}", all(U0.pend_of(d) == {} for d in ({}, {"pend": None}, {"pend": ["pu-x"]}, {"pend": "pu-x"}, None, [1])))
check("pend_of：值不是數字（字串／None／bool／dict）的那幾筆丟掉、其餘留著", U0.pend_of({"pend": {"a": "1000", "b": None, "c": True, "d": {}, "e": 7}}) == {"e": 7})
check("since_of：有欠 ⇒ 取較舊的；欠的比 newestT 新（不該發生）⇒ 仍取較舊的；沒欠 ⇒ newestT",
      (U0.since_of(1300, {"p": 1000}, "p"), U0.since_of(900, {"p": 1000}, "p"), U0.since_of(1300, {"p": 1000}, "q")) == (1000, 900, 1300))
_acc = [{"riotId": "A1#KR1", "platform": "kr", "dpmPuuid": "pu-a1"}, {"riotId": "A2#KR1", "platform": "kr", "dpmPuuid": "pu-a2"}, {"riotId": "A3#KR1", "platform": "kr", "dpmPuuid": "pu-a3"}]
_st = {"a1#kr1@kr", "a3#kr1@kr"}
check("plan_accounts：pend 空 ⇒ 跟 split_static_accounts 一模一樣（穩態）", U0.plan_accounts(_acc, _st, {}) == U0.split_static_accounts(_acc, _st) and U0.plan_accounts(_acc, set(), {}) == U0.split_static_accounts(_acc, set()))
_todo, _skip = U0.plan_accounts(_acc, _st, {"pu-a3": 5})
check("plan_accounts：靜止但有欠的 a3 拉回來問、順序照帳號檔（a2、a3）；沒欠的 a1 照樣跳過", [a["dpmPuuid"] for a in _todo] == ["pu-a2", "pu-a3"] and [a["dpmPuuid"] for a in _skip] == ["pu-a1"], (_todo, _skip))
_todo, _skip = U0.plan_accounts(_acc, _st, {"pu-a1": 5, "pu-zz": 9})
check("plan_accounts：順序不是「先 todo 後補」（a1 排回最前面）；pend 裡不在帳號檔的 puuid 不會憑空多出帳號", [a["dpmPuuid"] for a in _todo] == ["pu-a1", "pu-a2"] and [a["dpmPuuid"] for a in _skip] == ["pu-a3"], (_todo, _skip))
_d = {"role": "MIDDLE", "matches": [1], "src": {"v": 1}}
check("with_pend：沒有 pend、檔裡原本也沒有 ⇒ **同一個物件**回去（穩態一字不變）", U0.with_pend(_d, {}) is _d)
_w = U0.with_pend(_d, {"pu-a1": 1000})
check("with_pend：放在 matches 前面、src 仍是最後一個鍵", list(_w) == ["role", "pend", "matches", "src"] and _w["pend"] == {"pu-a1": 1000} and "pend" not in _d, list(_w))
check("with_pend：舊的 pend 換掉不重複；清空 ⇒ 鍵整個拿掉、其餘鍵序不變", list(U0.with_pend(_w, {"pu-a2": 5})) == ["role", "pend", "matches", "src"] and U0.with_pend(_w, {"pu-a2": 5})["pend"] == {"pu-a2": 5}
      and list(U0.with_pend(_w, {})) == ["role", "matches", "src"])
check("with_pend：沒有 matches 鍵（不該發生）⇒ 也不會把 pend 弄丟", U0.with_pend({"role": "TOP"}, {"p": 1}) == {"role": "TOP", "pend": {"p": 1}})

# ───────── ② 洞補上了（循序）─────────
print("[2] 循序三班：沒問到 → 記 pend → 從當時的起點補 → 清")
U, p, t21, o21, tmp2 = run(NEW, always_bad={"pu-a1": -1})
check("第 1 班：a1 重試仍失敗、A 照 #68 收 a2 的 1300", "A1#KR1 dpm 逾時／連線錯（單頁 15s）（重試仍失敗）→ 這輪不採用、下輪再補" in t21 and ts(o21, "p1.js") == [1300, 1000], (ts(o21, "p1.js"), t21))
check("第 1 班：A 的檔記下 pend＝{pu-a1: 1000}（當時的 newestT，不是跳過之後的 1300）、放在 matches 前面", data_of(o21, "p1.js").get("pend") == {"pu-a1": 1000}
      and list(data_of(o21, "p1.js")).index("pend") < list(data_of(o21, "p1.js")).index("matches"), list(data_of(o21, "p1.js")))
check("第 1 班：其餘 7 位的檔沒有 pend 鍵", all("pend" not in data_of(o21, f) for f in o21 if f != "p1.js"))
check("第 1 班：小結「補問成功 0 個…新記下 1 個」、沒有逐帳號的 ↺ 行", "↺ 沒問到的帳號（逐場檔 pend）：這一班補問成功 0 個、撿回原本會漏掉的舊場次 0 場；新記下 1 個" in t21 and t21.count("↺") == 1, t21)
U, p, t22, o22, _ = run(NEW, tmp=tmp2)
check("第 2 班：a1 從 1000 問起（不是 1300）、a2 照舊從 1300", p.asked("pu-a1") == [1000] and p.asked("pu-a2") == [1300], p.since)
check("第 2 班：**1200 回來了**——A＝[1500, 1300, 1200, 1000]", ts(o22, "p1.js") == [1500, 1300, 1200, 1000], ts(o22, "p1.js"))
check("第 2 班：pend 清掉（鍵整個不在）、src 仍是最後一個鍵", "pend" not in data_of(o22, "p1.js") and list(data_of(o22, "p1.js"))[-1] == "src", list(data_of(o22, "p1.js")))
check("第 2 班：逐帳號 ↺ 行指名 A1#KR1「2 場（其中 1 場…原本會漏掉的）」＋小結「補問成功 1 個、撿回…1 場；新記下 0 個」",
      "   ↺ A1#KR1 之前沒問到、這次從當時的起點問成功：2 場（其中 1 場比檔內最新一場舊＝原本會漏掉的）" in t22
      and "↺ 沒問到的帳號（逐場檔 pend）：這一班補問成功 1 個、撿回原本會漏掉的舊場次 1 場；新記下 0 個" in t22, t22)
check("第 2 班：「+2 新（共 4）」", re.search(r"\[1/8\] T1\|A  \+2 新（共 4）", t22), t22)
U, p, t23, o23, _ = run(NEW, tmp=tmp2)
check("第 3 班（穩態）：沒有任何 ↺、a1 從 1500 問起、8 個檔逐位元不變", "↺" not in t23 and p.asked("pu-a1") == [1500] and o23 == o22, (t23, p.since))

# ───────── ③ 批次模式 ─────────
print("[3] 批次模式：批次預抓用同一個起點、命中就清")
U, p, t31, o31, tmp3 = run(NEW, batch=True, bs=4, always_bad={"pu-a1": -1})
check("第 1 班（批次）：a1 批次 bad → 主迴圈重問仍 bad ⇒ 記 pend＝{pu-a1: 1000}、A＝[1300, 1000]", data_of(o31, "p1.js").get("pend") == {"pu-a1": 1000} and ts(o31, "p1.js") == [1300, 1000], data_of(o31, "p1.js").get("pend"))
U, p, t32, o32, _ = run(NEW, batch=True, bs=4, tmp=tmp3)
check("第 2 班（批次）：批次送出去的 a1 起點＝1000、a2＝1300；a1 沒有逐一請求（批次命中就收）", p.asked("pu-a1", "b") == [1000] and p.asked("pu-a2", "b") == [1300] and p.asked("pu-a1", "n") == [], p.since)
check("第 2 班（批次）：A＝[1500, 1300, 1200, 1000]、pend 清掉", ts(o32, "p1.js") == [1500, 1300, 1200, 1000] and "pend" not in data_of(o32, "p1.js"), ts(o32, "p1.js"))

# ───────── ④ 連續兩班沒問到 ─────────
print("[4] 連續兩班沒問到：pend 留最舊的起點")
DPM4 = copy.deepcopy(DPM0)
U, p, t41, o41, tmp4 = run(NEW, dpm=DPM4, always_bad={"pu-a1": 503})
DPM4["pu-a2"] = ("A2", [game(1400, "A2#KR1"), game(1300, "A2#KR1")])   # a2 又打了一場
U, p, t42, o42, _ = run(NEW, tmp=tmp4, dpm=DPM4, always_bad={"pu-a1": 503})
check("第 2 班：a1 仍失敗（從 1000 問的）、A 又收 a2 的 1400 ⇒ newestT＝1400", p.asked("pu-a1") == [1000, 1000] and ts(o42, "p1.js") == [1400, 1300, 1000], (p.since, ts(o42, "p1.js")))
check("第 2 班：pend 仍是 1000（沒被 1300 蓋掉）、小結「新記下 0 個」（不是每班重複算）", data_of(o42, "p1.js").get("pend") == {"pu-a1": 1000} and "新記下 0 個" not in t42 and "↺" not in t42, (data_of(o42, "p1.js").get("pend"), t42))
U, p, t43, o43, _ = run(NEW, tmp=tmp4, dpm=DPM4)
check("第 3 班（dpm 好了）：a1 從 1000 問 ⇒ A＝[1500, 1400, 1300, 1200, 1000]、pend 清掉", ts(o43, "p1.js") == [1500, 1400, 1300, 1200, 1000] and "pend" not in data_of(o43, "p1.js"), ts(o43, "p1.js"))

# ───────── ⑤ newestT 沒往前跳 ⇒ 不記 ─────────
print("[5] 沒問到、但這位的 newestT 沒往前跳 ⇒ 不記 pend、檔案不動")
U, p, t5, o5, _ = run(NEW, always_bad={"pu-b1": -1}, raise_on={"pu-c1"})
Uc, pc, t5c, o5c, _ = run(NEW)
check("B（單帳號、重試仍失敗）與 C（單帳號、抓錯）的檔逐位元原樣、沒有 pend 鍵", o5["p2.js"] != "" and "pend" not in data_of(o5, "p2.js") and "pend" not in data_of(o5, "p3.js") and ts(o5, "p2.js") == [2000] and ts(o5, "p3.js") == [], (o5["p2.js"][:200], o5["p3.js"][:200]))
check("整份日誌沒有任何 ↺；其餘 6 位的檔跟「dpm 全好」那一趟逐位元相同", "↺" not in t5 and all(o5[f] == o5c[f] for f in o5 if f not in ("p2.js", "p3.js")), t5)

# ───────── ⑥ 牌位沒動的帳號有 pend ⇒ 照問 ─────────
print("[6] --changed：靜止帳號有欠 ⇒ 照問；沒欠的靜止帳號照樣跳過")
PLAYED = {"scope": "full", "played": [k for k, _, _ in PLAYERS], "unknown": [], "acc_static": ["a1#kr1@kr", "e1#kr1@kr"]}
SEED6 = {"p1.js": {"pend": {"pu-a1": 1000}, "matches": [game(1300, "A2#KR1"), game(1000)]}}
U, p, t6, o6, tmp6 = run(NEW, files=SEED6, changed=PLAYED)
check("沙盒的 --changed 名單真的被吃到（日誌有「另有 2 個帳號牌位沒動」）＝不是讀到真的 scripts/soloq_played.json", "另有 2 個帳號牌位沒動（逐帳號跳過）" in t6 and os.path.abspath(U.HERE) == os.path.abspath(tmp6), t6[:400])
check("a1 靜止但有欠 ⇒ 照問、從 1000 問起；e1 靜止沒欠 ⇒ 0 次請求（對照）", p.asked("pu-a1") == [1000] and p.asked("pu-e1") == [], p.since)
check("A＝[1500, 1300, 1200, 1000]、pend 清掉；「⏭ 跳過 1 個牌位沒動的帳號」（只剩 e1）", ts(o6, "p1.js") == [1500, 1300, 1200, 1000] and "pend" not in data_of(o6, "p1.js") and "⏭ 跳過 1 個牌位沒動的帳號（11 → 10 次 dpm 請求）" in t6, (ts(o6, "p1.js"), t6))
U, p, t6b, o6b, _ = run(NEW, batch=True, bs=4, files=SEED6, changed=PLAYED)
check("批次模式同一套：a1 進批次（起點 1000）、e1 不進", p.asked("pu-a1", "b") == [1000] and p.asked("pu-e1") == [] and ts(o6b, "p1.js") == [1500, 1300, 1200, 1000], p.since)

# ───────── ⑦ 熔斷整位不採用 ⇒ pend 不動 ─────────
print("[7] 熔斷整位不採用 ⇒ pend 不動（清掉就真的漏了）")
DPM7 = copy.deepcopy(DPM0); DPM7["pu-h2"] = ("H2", [game(4500, "H2#KR1"), game(3800, "H2#KR1")])   # 3800 比 H 檔內最新的 4000 舊、比 pend 3500 新
SEED7 = {"p8.js": {"pend": {"pu-h2": 3500}, "matches": [game(4000)]}}
U, p, t71, o71, tmp7 = run(NEW, batch=True, bs=4, files=SEED7, dpm=DPM7, always_bad={"pu-e1": -1, "pu-f1": -1, "pu-g1": -1}, batch_bad={"pu-h1": -1})
check("情境成立：e1、f1、g1 連續失敗 ⇒ 熔斷；h2 批次命中（起點 3500）、h1 沒問到 ⇒ H 整位不採用", "⚡ dpm 熔斷：連續 3 個帳號問不到" in t71 and p.asked("pu-h2", "b") == [3500] and p.asked("pu-h1", "n") == []
      and re.search(r"T8\|H  熔斷後 1 個帳號沒問到 ⇒ 已到手的 \+2 場這一班不採用", t71), t71)
check("H 的檔逐位元原樣（pend 還是 {pu-h2: 3500}、matches 還是 [4000]）", data_of(o71, "p8.js") == SEED7["p8.js"], data_of(o71, "p8.js"))
check("H 沒有被算成「補問成功」（到手的整位丟了 ⇒ 日誌不可以說補到了）；小結的「新記下 1 個」是 e1（E 收了 e2 批次命中的 3900）",
      "↺ H2#KR1" not in t71 and "這一班補問成功 0 個、撿回原本會漏掉的舊場次 0 場；新記下 1 個" in t71 and data_of(o71, "p5.js").get("pend") == {"pu-e1": 50},
      ([l for l in t71.splitlines() if "↺" in l], data_of(o71, "p5.js").get("pend")))
U, p, t72, o72, _ = run(NEW, batch=True, bs=4, tmp=tmp7, dpm=DPM7)
check("下一班（dpm 好了）：H＝[5000, 4500, 4000, 3800]——**3800 補得回來**、pend 清掉", ts(o72, "p8.js") == [5000, 4500, 4000, 3800] and "pend" not in data_of(o72, "p8.js"), ts(o72, "p8.js"))

# ───────── ⑧ 「+N 新」不重複計 ─────────
print("[8] 補問回來的場次跟檔內重複 ⇒「+N 新」不重複計")
SEED8 = {"p1.js": {"pend": {"pu-a1": 1000}, "matches": [game(1300, "A2#KR1"), game(1200, "A1#KR1"), game(1000)]}}   # 1200 已經在檔裡
U, p, t8, o8, _ = run(NEW, files=SEED8)
check("a1 從 1000 問回 1500、1200；1200 已在檔內 ⇒「+1 新（共 4）」、檔內 1200 只有一筆", re.search(r"T1\|A  \+1 新（共 4）", t8) and ts(o8, "p1.js") == [1500, 1300, 1200, 1000], (ts(o8, "p1.js"), t8))
Uc8, pc8, t8c, o8c, _ = run(NEW)
_tot = lambda t: int(re.search(r"完成：(\d+) 位有新戰績、共 \+(\d+) 場", t).group(2))
check("完成行的總場數也不重複計（比「dpm 全好、沒種 pend」那一趟：A 少 a2 的 1300 與重複的 1200 ⇒ 少 2）", _tot(t8c) - _tot(t8) == 2, (_tot(t8c), _tot(t8)))

print("[8b] 補問成功但 0 場 ⇒ 只重寫 meta（pend 清掉）、不算「有新戰績」")
SEED8B = {"p2.js": {"pend": {"pu-b1": 1500}, "matches": [game(2000)]}}
U, p, t8b, o8b, _ = run(NEW, files=SEED8B)
_done = lambda t: re.search(r"完成：.*", t).group(0)
check("補問成功但 0 場：b1 從 1500 問、B 的 pend 清掉、matches 原樣 [2000]、沒有「T2|B  +N 新」那行", p.asked("pu-b1") == [1500] and "pend" not in data_of(o8b, "p2.js") and ts(o8b, "p2.js") == [2000] and "T2|B  +" not in t8b,
      (p.asked("pu-b1"), list(data_of(o8b, "p2.js")), t8b))
check("補問成功但 0 場：完成行（幾位有新戰績、共幾場）跟沒種 pend 那一趟一字不差；↺ 行照實寫「0 場」", _done(t8b) == _done(t8c) and "↺ B#KR1 之前沒問到、這次從當時的起點問成功：0 場（其中 0 場" in t8b, (_done(t8b), _done(t8c)))

# ───────── ⑨ pend 形狀壞掉 ─────────
print("[9] 檔裡的 pend 形狀壞掉 ⇒ 當沒有、下次寫檔順手清掉")
SEED9 = {"p1.js": {"pend": ["pu-a1"], "matches": [game(1000)]}, "p2.js": {"pend": {"pu-b1": "2000"}, "matches": [game(2000)]}}
try: U, p, t9, o9, _ = run(NEW, files=SEED9); err9 = None
except Exception as e: err9 = e   # 模組在 main() 裡炸掉要記成紅、不可以讓整支測試跟著崩（#184：崩潰≠紅）
check("不炸、a1 照舊從 newestT（1000）問、A 照收 [1500, 1300, 1200, 1000]、壞掉的 pend 鍵清掉", err9 is None and p.asked("pu-a1") == [1000] and ts(o9, "p1.js") == [1500, 1300, 1200, 1000] and "pend" not in data_of(o9, "p1.js"),
      err9 if err9 is not None else (p.since[:3], list(data_of(o9, "p1.js"))))
check("B 沒有新場次 ⇒ 檔不重寫（壞掉的鍵留著無害）、b1 從 2000 問、日誌沒有 ↺", err9 is None and o9["p2.js"].count('"pend"') == 1 and p.asked("pu-b1") == [2000] and "↺" not in t9,
      err9 if err9 is not None else (o9["p2.js"][:120], t9))

# ───────── ⑩ clean_soloq_matches.fast_rids ─────────
print("[10] clean_soloq_matches.fast_rids（真的那支、只讀沙盒檔）")
C = load("csm_for_pend_test", os.path.join(HERE, "clean_soloq_matches.py"), argv=[])
fp = os.path.join(tmp3, "_probe_pend.js"); d31 = data_of(o31, "p1.js")
check("前提：第 1 班寫出來的 A 檔同時有 pend 與 src、src 是最後一個鍵", "pend" in d31 and list(d31)[-1] == "src", list(d31))
open(fp, "w", encoding="utf-8").write(o31["p1.js"])
try: fk, fc = C.fast_rids(fp); ferr = None
except Exception as e: fk = fc = None; ferr = e
check("帶 pend 的檔仍走快路徑（不丟例外）、key 與 rid 次數跟整檔解析相同", ferr is None and fk == "T1|A" and fc == C.slow_rids(C.read_file(fp)[1]) and sum(fc.values()) == 2, (ferr, fc))
bad_order = {k: v for k, v in d31.items() if k != "pend"}; bad_order["pend"] = d31.get("pend") or {"pu-a1": 1000}   # 對照：pend 放在 src 後面（前提那條紅了也不要讓測試崩）
open(fp, "w", encoding="utf-8").write(f'window.__sqLoad("T1|A",{json.dumps(bad_order, ensure_ascii=False)});\n')
try: C.fast_rids(fp); raised = False
except ValueError: raised = True
check("對照：pend 放在 src 後面 ⇒ fast_rids 丟 ValueError（＝鍵序真的有差，不是怎麼放都過）", raised)
os.remove(fp)

# ───────── ⑪ 正控制：舊版 ─────────
print("[11] 正控制：釘 %s 的舊版" % OLDREV)
old_src = subprocess.run(["git", "-C", ROOT, "show", f"{OLDREV}:scripts/fetch_soloq_update.py"], capture_output=True, text=True, encoding="utf-8").stdout
check("舊版拿得到、而且真的沒有 pend_of／with_pend（不是早就有）", bool(old_src) and "pend_of" not in old_src and "with_pend" not in old_src)
if old_src:
    oldf = os.path.join(tempfile.gettempdir(), "fsu_pend_old.py")
    open(oldf, "w", encoding="utf-8").write(old_src)
    Uo, po, to1, oo1, tmpo = run(oldf, always_bad={"pu-a1": -1})
    Uo, po, to2, oo2, _ = run(oldf, tmp=tmpo)
    check("舊版同樣兩班：第 2 班 a1 從 1300 問 ⇒ A＝[1500, 1300, 1000]，**1200 永遠漏掉**、檔裡沒有 pend", po.asked("pu-a1") == [1300] and ts(oo2, "p1.js") == [1500, 1300, 1000] and "pend" not in data_of(oo1, "p1.js"), (po.since[:2], ts(oo2, "p1.js")))
    for b in (False, True):
        Uoc, poc, toc, ooc, _ = run(oldf, batch=b)
        Unc, pnc, tnc, onc, _ = run(NEW, batch=b)
        check("乾淨資料（%s）：新舊版輸出逐檔相同、日誌逐行相同、送出去的起點逐筆相同（穩態一字不變）" % ("批次" if b else "循序"), ooc == onc and norm(toc) == norm(tnc) and poc.since == pnc.since,
              [k for k in ooc if ooc[k] != onc.get(k)] + [x for x in norm(toc) if x not in norm(tnc)] + [x for x in norm(tnc) if x not in norm(toc)])
    Uo5, po5, to5, oo5, _ = run(oldf, always_bad={"pu-b1": -1}, raise_on={"pu-c1"})
    check("沒問到但沒往前跳（⑤ 的情境）：新舊版輸出逐檔相同、日誌逐行相同", oo5 == o5 and norm(to5) == norm(t5), [k for k in oo5 if oo5[k] != o5.get(k)])

# ───────── ⑫ 真實檔 ─────────
print("[12] 真實檔沒被動")
check("真實 index／accounts／played／acc_lastgame／year_empty／soloq_matches 目錄 mtime 全部不變", snap() == SNAP0, [k for k in SNAP0 if SNAP0[k] != snap().get(k)])
for t in TMPS: shutil.rmtree(t, ignore_errors=True)
print(f"\n{OK} 通過／{FAIL} 失敗")
sys.exit(1 if FAIL else 0)
