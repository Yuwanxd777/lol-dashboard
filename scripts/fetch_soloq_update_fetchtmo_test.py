# -*- coding: utf-8 -*-
"""⑤d fetch_soloq_update 單頁請求逾時（2026-09-22 線 3，精進迴圈 #198）——沙盒：假 playwright、暫存目錄、子程序不起、不打網路。

病灶：09-21 22:00 那班「批次預抓 80s：8 批每批 最快 1.3s／中位 2.8s／最慢 58.4s」——一個帳號的 fetch 掛 58.4s 才等到 dpm 回 500，
Promise.all 一批等最慢那一個 ⇒ ⑤d 33s → 87s。JS_NEW 的 fetch 沒有逾時；而且 fetch 丟例外時靜默 break、半截結果照收（bad=0）。

① 模組層：FETCH_TMO_MS 預設 15000、--fetch-timeout-ms 吃得到、JS 裡沒有殘留的佔位字、JS_BATCH 仍包住 JS_NEW。
② node 真的跑 JS_BATCH（逾時設 300ms；假 fetch 認 signal）：掛住的請求 ~300ms 就回 bad=-1（不是等 3 秒後的 500）、
   第 2 頁掛住 ⇒ bad=-1（半截結果要被標成不可用）、fetch 直接丟例外 ⇒ bad=-1（以前 bad=0）、json() 掛住 ⇒ 走 .catch → {err}、
   慢但在時限內的照常收、**計時器有清掉**（完成之後再等一輪逾時，signal 仍未 abort）、整批不被掛住的那個拖到 3 秒。
③ Python 端（假 pg）：批次裡 bad=-1 ⇒ 退回逐一、**不減半**、日誌指名、輸出跟循序逐檔相同；對照：同一個位置回 429 ⇒ 照舊減半。
   逐一問兩次都 -1 ⇒ 半截結果丟掉、檔案不動、訊息不印「dpm 回 -1」。
④ 正控制（釘 OLDREV＝改動前那個 commit）：舊版 JS 對同一個假 fetch 要等滿 3 秒拿到 500；舊版 Python 對 bad=-1 會減半。
⑤ 真實檔沒被動。
用法：python scripts/fetch_soloq_update_fetchtmo_test.py
"""
import os, sys, io, re, json, shutil, tempfile, subprocess, importlib.util, contextlib, time as _time

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
OLDREV = "d6782569"   # #198 改動之前的 HEAD（別寫 HEAD：commit 之後 HEAD 就是新版，見 DAILY #93）
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

# ───────── 假資料（跟 fetch_soloq_update_batch_test 同一組形狀）─────────
def game(t, rid="X#1"):
    return {"t": t, "d": 1500, "c": "Ahri", "o": None, "w": True, "k": 5, "de": 2, "a": 7, "kp": 60, "sc": 80, "scr": 1,
            "pos": "MIDDLE", "su": [4, 14], "r": 8010, "rp": [8010, 0, 0, 0], "rs": [0, 0, 0], "rst": [0, 0, 0], "sk": [],
            "du": None, "dul": None, "duo": None, "rid": rid, "it": [], "st": [], "ib": [], "cs": 200,
            "gd15": 0, "dpm": 500, "tr": None, "lp": None, "xd15": 0, "fl2": None}
PLAYERS = [("T1|A", "MIDDLE", [game(1000)]), ("T2|B", "TOP", [game(2000)]), ("T3|C", "JUNGLE", []),
           ("T4|D", "BOTTOM", [game(100)]), ("T5|E", "UTILITY", [game(50)]), ("T6|F", "MIDDLE", [game(700)])]
ACCS = [("T1|A", "pu-a1", "A1#KR1"), ("T1|A", "pu-a2", "A2#KR1"), ("T2|B", "pu-b1", "B#KR1"), ("T3|C", "pu-c1", "C#KR1"),
        ("T4|D", "pu-d1", "D#KR1"), ("T5|E", "pu-e1", "E#KR1"), ("T6|F", "pu-f1", "F#KR1")]
DPM = {"pu-a1": ("A1", [game(1500, "A1#KR1"), game(1200, "A1#KR1"), game(900, "A1#KR1")]),
       "pu-a2": ("A2", [game(1300, "A2#KR1")]), "pu-b1": ("B", []), "pu-c1": ("C", [game(500, "C#KR1")]),
       "pu-d1": ("D", [game(3000, "D#KR1")]), "pu-e1": ("E", [game(4000, "E#KR1")]), "pu-f1": ("F", [game(800, "F#KR1")])}

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
    """batch_bad：{pu: bad 值}＝那個帳號在**批次裡**回 bad（逐一問正常）；always_bad：{pu: bad 值}＝逐一問也永遠 bad，而且帶半截結果。"""
    def __init__(self, U, batch_bad=None, always_bad=None):
        self.U = U; self.batch_bad = batch_bad or {}; self.always_bad = always_bad or {}; self.calls = []
    def goto(self, *a, **k): pass
    def on(self, *a, **k): pass
    def _one(self, args, batch):
        pu, tok, nt = args; self.calls.append(("b1" if batch else "n", pu))
        name, ms = DPM[pu]; new = [g for g in ms if g["t"] > nt]
        if pu in self.always_bad: return {"id": {"g": name, "t": "KR1"}, "ms": new, "bad": self.always_bad[pu]}   # 半截結果也帶著
        if batch and pu in self.batch_bad: return {"id": None, "ms": [], "bad": self.batch_bad[pu]}
        return {"id": {"g": name, "t": "KR1"}, "ms": new, "bad": 0}
    def evaluate(self, js, args=None):
        if "top-teams" in js: return 200
        if js == getattr(self.U, "JS_BATCH", None):
            self.calls.append(("B", [a[0] for a in args])); return [self._one(a, True) for a in args]
        if js == self.U.JS_NEW: return self._one(args, False)
        raise AssertionError("未知的 evaluate：" + js[:60])
    def n_calls(self, kind, pu=None): return sum(1 for c in self.calls if c[0] == kind and (pu is None or c[1] == pu))

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
    U.sync_playwright = fake_pw; U._launch_real = lambda p: FakeBrowser(page); U.comp_roles = lambda: {}
    U.time = FakeTime(); U.MAXP = 0; U.CHILD = []
    U.load_year_empty = lambda path=None: {}
    U.run_child = lambda label, cmd, argv=None: U.CHILD.append((label, list(cmd)))
    U.USE_BATCH = batch; U.BATCH_NEW = bs

def leaks(U):
    """模組層任何字串常數還指著真實 repo（除了模組自己的位置）＝漏接；呼叫端要在 main() 之前中止（#188：抓到漏接一律中止）"""
    bad = [n for n in PATHS if os.path.abspath(getattr(U, n)).lower().startswith(ROOT.lower())]
    if U.run_child.__module__ == U.__name__: bad.append("run_child")
    if U.sync_playwright is not fake_pw: bad.append("sync_playwright")
    return bad

TMPS = []
def run(src_path, batch, bs=4, batch_bad=None, always_bad=None):
    tmp = tempfile.mkdtemp(prefix="fsu_tmo_"); TMPS.append(tmp)
    make_sandbox(tmp)
    U = load("fsu_" + os.path.basename(tmp), src_path, argv=[])
    page = FakePage(U, batch_bad=batch_bad, always_bad=always_bad)
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
    out["acc_lg"] = open(U.ACC_LG_PATH, encoding="utf-8").read()
    return U, page, buf.getvalue(), out

def matches_of(txt):
    m = re.match(r'window\.__sqLoad\((.*)\);\s*$', txt, re.S); return json.loads("[" + m.group(1) + "]")[1]["matches"]

# ───────── ① 模組層 ─────────
print("[1] 模組層")
U0 = load("fsu_tmo_default", NEW, argv=[])
check("FETCH_TMO_MS 預設 15000、BAD_NET＝-1", getattr(U0, "FETCH_TMO_MS", None) == 15000 and getattr(U0, "BAD_NET", None) == -1)
check("JS_NEW 有 AbortController、signal、clearTimeout、逾時值 15000，沒有殘留佔位字",
      all(s in U0.JS_NEW for s in ("AbortController", "signal:ac.signal", "clearTimeout(tm)", "ac.abort(), 15000)")) and "__TMO__" not in U0.JS_NEW)
check("JS_BATCH 仍包住 JS_NEW（一字不差）", U0.JS_NEW in U0.JS_BATCH and "Promise.all" in U0.JS_BATCH)
U3 = load("fsu_tmo_300", NEW, argv=["--fetch-timeout-ms", "300"])
check("--fetch-timeout-ms 300 吃得到（JS 裡是 300、不是 15000）", U3.FETCH_TMO_MS == 300 and "ac.abort(), 300)" in U3.JS_NEW and "15000" not in U3.JS_NEW)
check("bad_name：-1 不印成「回 -1」、HTTP 狀態照舊", "逾時" in U0.bad_name(-1) and "-1" not in U0.bad_name(-1) and "15s" in U0.bad_name(-1) and U0.bad_name(503) == "回 503")

# ───────── ② node 真的跑 ─────────
NODE_TMPL = r"""
const batch = (%s);
function part(g){ return {gameName:g, tagLine:'KR1', win:true, kills:1, deaths:2, assists:3, killParticipation:50,
  championName:'Ahri', lane:'MIDDLE', summoner1Id:4, summoner2Id:14, primaryRuneId:8010, itemActions:[], itemIds:[], startItems:[]}; }
function m(t){ return {gameCreation:t, gameDuration:1500, queueId:420, participants:[part('P')]}; }
const SIG = {};
function hang(opts, ms, val){   // 掛 ms 毫秒才回 val；認 signal（被 abort 就 reject，跟瀏覽器一樣）
  return new Promise((res, rej)=>{ const t=setTimeout(()=>res(val), ms);
    if(opts && opts.signal) opts.signal.addEventListener('abort', ()=>{ clearTimeout(t); rej(new Error('AbortError')); }); });
}
global.fetch = async (url, opts) => {
  const PU = url.split('/v1/players/')[1].split('/')[0];
  const page = parseInt(url.split('page=')[1]);
  SIG[PU + ':' + page] = opts && opts.signal;
  const okj = (ms)=>({ok:true, status:200, json: async()=>({matches: ms})});
  if (PU === 'ok') return okj(page===1 ? [m(2000), m(1500), m(1000)] : []);
  if (PU === 'hang') return hang(opts, 3000, {ok:false, status:500});          // 真實形狀：掛很久最後回 500
  if (PU === 'hang2') return page===1 ? okj([m(9000), m(8000)]) : hang(opts, 3000, {ok:false, status:500});
  if (PU === 'neterr') throw new TypeError('Failed to fetch');
  if (PU === 'jhang') return {ok:true, status:200, json: ()=>hang(opts, 3000, {matches: []})};
  if (PU === 'slowok') return hang(opts, 120, okj(page===1 ? [m(7000)] : []));
  throw new Error('unknown ' + PU);
};
(async()=>{
  const t0 = Date.now();
  const r = await batch([['ok','middle',1000], ['hang','top',0], ['hang2','top',0], ['neterr','top',0], ['jhang','top',0], ['slowok','top',0]]);
  const wall = Date.now() - t0;
  await new Promise(res=>setTimeout(res, %d));   // 再等一輪逾時：計時器沒清掉的話 slowok 的 signal 會在這段變成 aborted
  console.log(JSON.stringify({r: r, wall: wall, slowok_aborted: !!(SIG['slowok:1'] && SIG['slowok:1'].aborted),
                              has_signal: !!SIG['ok:1']}));
  process.exit(0);
})();
"""
def node_run(js_batch, settle_ms, tag):
    jsf = os.path.join(tempfile.gettempdir(), "fsu_tmo_probe_%s.js" % tag)
    open(jsf, "w", encoding="utf-8").write(NODE_TMPL % (js_batch, settle_ms))
    r = subprocess.run(["node", jsf], capture_output=True, text=True, encoding="utf-8", timeout=60)
    return json.loads(r.stdout.strip().splitlines()[-1]), r.stderr

print("[2] node 真的跑 JS_BATCH（逾時 300ms）")
try:
    o, err = node_run(U3.JS_BATCH, 450, "new")
    res = o["r"]
    check("node 跑得起來、回 6 個結果、fetch 真的收到 signal", len(res) == 6 and o["has_signal"], err[:300])
    check("正常帳號照舊：2000、1500（1000 ≤ newestT 不收）、bad 0、id 帶出", [g["t"] for g in res[0]["ms"]] == [2000, 1500] and res[0]["bad"] == 0 and res[0]["id"] == {"g": "P", "t": "KR1"}, res[0])
    check("掛住的請求：~300ms 就回 bad=-1（不是等 3 秒後的 500）、ms 空", res[1].get("bad") == -1 and res[1]["ms"] == [] and 250 <= res[1]["el"] < 1500, res[1])
    check("第 2 頁掛住：bad=-1（半截結果 9000、8000 帶著但被標成不可用）", res[2].get("bad") == -1 and [g["t"] for g in res[2]["ms"]] == [9000, 8000] and 250 <= res[2]["el"] < 1500, res[2])
    check("fetch 直接丟例外：bad=-1（以前靜默 bad=0）、馬上回", res[3].get("bad") == -1 and res[3]["el"] < 200, res[3])
    check("json() 掛住：逾時後走 .catch → {err}（照舊的 err 路徑）、~300ms", "err" in res[4] and 250 <= res[4].get("el", -1) < 1500, res[4])
    check("慢但在時限內（120ms）：照常收 7000、bad 0", [g["t"] for g in res[5]["ms"]] == [7000] and res[5]["bad"] == 0, res[5])
    check("計時器有清掉：完成後再等 450ms，slowok 的 signal 仍未 abort", o["slowok_aborted"] is False, o)
    check("整批不被掛住的那個拖到 3 秒（牆鐘 %dms < 1500）" % o["wall"], o["wall"] < 1500, o["wall"])
except Exception as e:
    check("node 執行新版 JS_BATCH", False, repr(e))

# ───────── ③ Python 端 ─────────
print("[3] Python 端：批次裡 bad=-1 ⇒ 退回逐一、不減半；429 對照 ⇒ 減半")
Us, ps, txt_s, out_s = run(NEW, batch=False)
Un, pn, txt_n, out_n = run(NEW, batch=True, bs=4, batch_bad={"pu-a1": -1})
U4, p4, txt_4, out_4 = run(NEW, batch=True, bs=4, batch_bad={"pu-a1": 429})
sizes = lambda p: [len(c[1]) for c in p.calls if c[0] == "B"]
check("bad=-1：批次大小 4／3（沒減半）", sizes(pn) == [4, 3], sizes(pn))
check("對照 bad=429：批次大小 4／2／1（照舊減半）", sizes(p4) == [4, 2, 1], sizes(p4))
check("bad=-1：日誌指名「逾時／連線錯（單頁 15s） 1 個 → 留給主迴圈逐一重問（不減半）」、沒有「批次減半」", "dpm 逾時／連線錯（單頁 15s） 1 個 → 留給主迴圈逐一重問（不減半）" in txt_n and "批次減半" not in txt_n, txt_n)
check("bad=-1：收尾行「退回逐一 1、減半 0 次、逾時／連線錯 1 個」", re.search(r"批次預抓 \d+s：7 個帳號／2 批（批次大小 4）、命中 6、退回逐一 1、減半 0 次、逾時／連線錯 1 個\n", txt_n), txt_n)
check("對照 429：收尾行「減半 1 次」結尾、沒有逾時尾巴（穩態那行一字不變）", re.search(r"、退回逐一 1、減半 1 次\n", txt_4) and "逾時" not in txt_4, txt_4)
check("bad=-1：那個帳號逐一重問 1 次、其餘帳號沒有逐一問", pn.n_calls("n", "pu-a1") == 1 and pn.n_calls("n") == 1, [c for c in pn.calls if c[0] == "n"])
check("bad=-1：輸出跟循序逐檔相同（A 拿到 1500、1200）", out_n == out_s and [g["t"] for g in matches_of(out_n["p1.js"])] == [1500, 1300, 1200, 1000], [k for k in out_s if out_s[k] != out_n.get(k)])
check("循序模式沒有批次日誌行", "批次預抓" not in txt_s)

print("[3b] 逐一問兩次都 -1 ⇒ 半截結果丟掉、檔案不動")
Ue, pe, txt_e, out_e = run(NEW, batch=False, always_bad={"pu-e1": -1})
check("E：逐一 2 次、中間睡 1.5s", pe.n_calls("n", "pu-e1") == 2 and 1.5 in Ue.time.sleeps, (pe.n_calls("n", "pu-e1"), Ue.time.sleeps))
check("E：半截結果（4000）沒被採用、檔案原樣", matches_of(out_e["p5.js"]) == [game(50)], out_e["p5.js"][:200])
check("E：訊息「E#KR1 dpm 逾時／連線錯（單頁 15s）（重試仍失敗）→ 這輪不採用」、不印「回 -1」", "E#KR1 dpm 逾時／連線錯（單頁 15s）（重試仍失敗）→ 這輪不採用" in txt_e and "回 -1" not in txt_e, txt_e)
check("E：其他選手照常（D 拿到 3000）", [g["t"] for g in matches_of(out_e["p4.js"])] == [3000, 100])
Ub, pb, txt_b, out_b = run(NEW, batch=True, bs=4, always_bad={"pu-e1": -1})
check("E（批次模式）：批次 1 次＋逐一 2 次、輸出跟循序那次相同", pb.n_calls("b1", "pu-e1") == 1 and pb.n_calls("n", "pu-e1") == 2 and out_b == out_e, [k for k in out_e if out_e[k] != out_b.get(k)])

# ───────── ④ 正控制：舊版 ─────────
print("[4] 正控制：釘 %s 的舊版" % OLDREV)
old_src = subprocess.run(["git", "-C", ROOT, "show", f"{OLDREV}:scripts/fetch_soloq_update.py"], capture_output=True, text=True, encoding="utf-8").stdout
check("舊版拿得到、而且真的沒有 AbortController／FETCH_TMO_MS（不是早就有）", bool(old_src) and "AbortController" not in old_src and "FETCH_TMO_MS" not in old_src)
if old_src:
    oldf = os.path.join(tempfile.gettempdir(), "fsu_tmo_old.py")
    open(oldf, "w", encoding="utf-8").write(old_src)
    UO = load("fsu_tmo_oldmod", oldf, argv=[])
    try:
        oo, err = node_run(UO.JS_BATCH, 50, "old")
        ro = oo["r"]
        check("舊版 JS：掛住的請求等滿 3 秒才拿到 500（el ≥ 2900）", ro[1].get("bad") == 500 and ro[1]["el"] >= 2900, ro[1])
        check("舊版 JS：整批被拖到 3 秒（牆鐘 %dms ≥ 2900）" % oo["wall"], oo["wall"] >= 2900, oo["wall"])
        check("舊版 JS：fetch 丟例外 ⇒ 靜默 bad=0（＝半截結果會被當成完整）", ro[3].get("bad") == 0, ro[3])
        check("舊版 JS：fetch 沒收到 signal", oo["has_signal"] is False, oo)
    except Exception as e:
        check("node 執行舊版 JS_BATCH", False, repr(e))
    Uo, po, txt_o, out_o = run(oldf, batch=True, bs=4, batch_bad={"pu-a1": -1})
    check("舊版 Python：bad=-1 會減半（4／2／1）、印「dpm 回 -1」", sizes(po) == [4, 2, 1] and "dpm 回 -1 → 批次減半為 2" in txt_o, (sizes(po), txt_o[-400:]))
    Uoc, poc, txt_oc, out_oc = run(oldf, batch=True, bs=4)
    Unc, pnc, txt_nc, out_nc = run(NEW, batch=True, bs=4)
    # 「最久的 N 位」那行照**真實牆鐘**排序，沙盒裡每位都是 0.00x 秒 ⇒ 順序每次跑都不一樣（第一次跑就紅在這，兩版輸出其實逐檔相同）
    # ⇒ 那一行只比「兩版都有、各列 5 位沙盒裡的選手」，其餘逐行比。6 位取前 5 ⇒ **連列到誰都看牆鐘**
    # （三連跑第 2 次紅在「同一批人」：舊版漏 T1|A、新版漏 T2|B），所以人名集合也不能比。
    def _norm(txt):
        ls = re.sub(r"\d+(\.\d+)?s", "Ns", txt).splitlines()
        slow = [l for l in ls if l.lstrip().startswith("最久的")]
        return [l for l in ls if l not in slow], [sorted(re.findall(r"T\d\|\w", l)) for l in slow]
    (lo, so), (ln, sn) = _norm(txt_oc), _norm(txt_nc)
    check("乾淨資料：舊版與新版輸出逐檔相同、日誌逐行相同（穩態一字不變）", out_oc == out_nc and lo == ln,
          [k for k in out_oc if out_oc[k] != out_nc.get(k)] + [x for x in lo if x not in ln] + [x for x in ln if x not in lo])
    _names = {p[0] for p in PLAYERS}
    check("乾淨資料：「最久的 N 位」那行兩版都各有 1 行、各列 5 位沙盒選手（列到誰、順序都看牆鐘 ⇒ 不比）",
          all(len(s) == 1 and len(s[0]) == 5 and len(set(s[0])) == 5 and set(s[0]) <= _names for s in (so, sn)), (so, sn))

# ───────── ⑤ 真實檔 ─────────
print("[5] 真實檔沒被動")
check("真實 index／accounts／acc_lastgame／year_empty／soloq_matches 目錄 mtime 全部不變", snap() == SNAP0, [k for k in SNAP0 if SNAP0[k] != snap().get(k)])
for t in TMPS: shutil.rmtree(t, ignore_errors=True)
print(f"\n{OK} 通過／{FAIL} 失敗")
sys.exit(1 if FAIL else 0)
