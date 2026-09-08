# -*- coding: utf-8 -*-
"""⑤d fetch_soloq_update 逐人批次化（2026-09-08 線 3，精進迴圈 #68）——沙盒：假 playwright、暫存目錄、子程序不起、不打網路。

① 沙盒守則：IDXP／OUTDIR／ACCOUNTS／ACC_LG_PATH／EMPTY_PATH 全在暫存目錄、run_child 是假的；
   正控制：把 ACCOUNTS 指回真實檔 → leaks() 抓得到。跑完真實檔 mtime 一個都沒變。
② JS 本體（node 真的跑 JS_BATCH）：Promise.all 包 JS_NEW；429 回 bad、json() 炸掉走 .catch → {err}、正常帳號只收 > newestT 的 420 場。
③ 假 dpm 的六位選手／七個帳號：循序模式 vs 批次模式（bs=3）輸出**逐檔相同**（pN.js／soloq_acc_lastgame.js／soloq_accounts.json 改名），
   而且批次模式 JS_BATCH 3 次（3／3／1：d1 回 429 → 減半為 2）、JS_NEW 只剩退回逐一的 4 次；循序模式 JS_NEW 9 次、JS_BATCH 0 次。
④ 退路：整批 evaluate 炸掉 → 那一批全部退回逐一，輸出仍與循序相同。
⑤ 限流：逐一問到 bad → 睡 1.5s 再問；仍 bad → 丟掉半截結果、印「這輪不採用」、檔案不動（newestT 不往前跳）。
⑥ 舊版（git HEAD）正控制：沒有 JS_BATCH／prefetch_batches；乾淨資料（沒有 bad／err）下舊版與新版循序輸出相同。
用法：python scripts/fetch_soloq_update_batch_test.py
"""
import os, sys, io, re, json, shutil, tempfile, subprocess, importlib.util, contextlib, time as _time

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
OK = FAIL = 0
def check(name, cond, info=""):
    global OK, FAIL
    if cond: OK += 1; print(f"  ✓ {name}")
    else: FAIL += 1; print(f"  ✗ {name}  {info}")

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

REAL = [os.path.join(ROOT, "soloq_match_index.js"), os.path.join(HERE, "soloq_accounts.json"),
        os.path.join(ROOT, "soloq_acc_lastgame.js"), os.path.join(ROOT, "csv_cache", "soloq_year_empty.json")]
def snap():
    d = {p: (os.path.getmtime(p), os.path.getsize(p)) if os.path.exists(p) else None for p in REAL}
    md = os.path.join(ROOT, "soloq_matches")
    d[md] = sorted((f, os.path.getmtime(os.path.join(md, f))) for f in os.listdir(md)) if os.path.isdir(md) else None
    return d
SNAP0 = snap()

# ───────── 假資料 ─────────
def game(t, rid="X#1"):
    return {"t": t, "d": 1500, "c": "Ahri", "o": None, "w": True, "k": 5, "de": 2, "a": 7, "kp": 60, "sc": 80, "scr": 1,
            "pos": "MIDDLE", "su": [4, 14], "r": 8010, "rp": [8010, 0, 0, 0], "rs": [0, 0, 0], "rst": [0, 0, 0], "sk": [],
            "du": None, "dul": None, "duo": None, "rid": rid, "it": [], "st": [], "ib": [], "cs": 200,
            "gd15": 0, "dpm": 500, "tr": None, "lp": None, "xd15": 0, "fl2": None}
PLAYERS = [("T1|A", "MIDDLE", [game(1000)]), ("T2|B", "TOP", [game(2000)]), ("T3|C", "JUNGLE", []),
           ("T4|D", "BOTTOM", [game(100)]), ("T5|E", "UTILITY", [game(50)]), ("T6|F", "MIDDLE", [game(700)])]
ACCS = [("T1|A", "pu-a1", "A1#KR1"), ("T1|A", "pu-a2", "A2#KR1"), ("T2|B", "pu-b1", "B#KR1"), ("T3|C", "pu-c1", "C#KR1"),
        ("T4|D", "pu-d1", "D#KR1"), ("T5|E", "pu-e1", "E#KR1"), ("T6|F", "pu-f1", "OldF#KR1"), ("T7|G", "pu-g1", "G#KR1")]
DPM = {"pu-a1": ("A1", [game(1500, "A1#KR1"), game(1200, "A1#KR1"), game(900, "A1#KR1")]),   # 900 ≤ newestT 1000 → 不收
       "pu-a2": ("A2", [game(1300, "A2#KR1")]), "pu-b1": ("B", []), "pu-c1": ("C", [game(500, "C#KR1")]),
       "pu-d1": ("D", [game(3000, "D#KR1")]), "pu-e1": ("E", [game(4000, "E#KR1")]), "pu-f1": ("NewF", [game(800, "NewF#KR1")])}

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
    json.dump(accs, open(os.path.join(tmp, "soloq_accounts.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(tmp, "soloq_acc_lastgame.js"), "w", encoding="utf-8").write("window.SOLOQ_ACC_LG={};\n")
    return md

class FakeTime:
    def __init__(self): self.slept = 0.0; self.sleeps = []
    def time(self): return _time.time()
    def strftime(self, *a): return _time.strftime(*a)
    def sleep(self, s): self.slept += s; self.sleeps.append(s)

class FakePage:
    """evaluate(JS_NEW, [pu,tok,nt]) 或 evaluate(JS_BATCH, [[pu,tok,nt],…])；d1 批次回 429、逐一第一次 429 第二次好；
    e1 批次走 .catch → {err}、逐一永遠 503；其餘正常。clean=True 全部正常。throw_first：第一次 JS_BATCH 整包炸。"""
    def __init__(self, U, clean=False, throw_first=False):
        self.U = U; self.clean = clean; self.throw_first = throw_first; self.calls = []; self.seq = {}
    def goto(self, *a, **k): pass
    def on(self, *a, **k): pass
    def _one(self, args, batch):
        pu, tok, nt = args; self.calls.append(("n" if not batch else "b1", pu, tok))
        name, ms = DPM[pu]
        if not self.clean:
            if pu == "pu-d1":
                if batch: return {"id": {"g": name, "t": "KR1"}, "ms": [], "bad": 429}
                self.seq[pu] = self.seq.get(pu, 0) + 1
                if self.seq[pu] == 1: return {"id": {"g": name, "t": "KR1"}, "ms": [], "bad": 429}
            if pu == "pu-e1":
                if batch: return {"err": "TypeError: boom"}
                return {"id": {"g": name, "t": "KR1"}, "ms": [g for g in ms if g["t"] > nt][:0], "bad": 503}
        return {"id": {"g": name, "t": "KR1"}, "ms": [g for g in ms if g["t"] > nt], "bad": 0}
    def evaluate(self, js, args=None):
        if "top-teams" in js: return 200
        if js == getattr(self.U, "JS_BATCH", None):
            self.calls.append(("B", [a[0] for a in args]))
            if self.throw_first and not any(c[0] == "Bthrown" for c in self.calls):
                self.calls.append(("Bthrown", None)); raise RuntimeError("Execution context was destroyed")
            return [self._one(a, True) for a in args]
        if js == self.U.JS_NEW: return self._one(args, False)
        raise AssertionError("未知的 evaluate：" + js[:60])
    def n_calls(self, kind): return sum(1 for c in self.calls if c[0] == kind)

class FakeBrowser:
    def __init__(self, page): self.page = page
    def new_context(self, **k): return self
    def new_page(self): return self.page
    def close(self): pass
@contextlib.contextmanager
def fake_pw(): yield None

def bind(U, tmp, page, batch, bs=3):
    U.IDXP = os.path.join(tmp, "soloq_match_index.js"); U.OUTDIR = os.path.join(tmp, "soloq_matches")
    U.ACCOUNTS = os.path.join(tmp, "soloq_accounts.json"); U.ACC_LG_PATH = os.path.join(tmp, "soloq_acc_lastgame.js")
    U.EMPTY_PATH = os.path.join(tmp, "soloq_year_empty.json")
    U.sync_playwright = fake_pw; U._launch_real = lambda p: FakeBrowser(page); U.comp_roles = lambda: {}
    U.time = FakeTime(); U.MAXP = 0; U.CHILD = []
    U.load_year_empty = lambda path=None: {}   # 預設參數在 def 時就綁死真實 csv_cache 路徑，直接換掉函式
    U.run_child = lambda label, cmd, argv=None: U.CHILD.append((label, list(cmd)))
    if hasattr(U, "USE_BATCH"): U.USE_BATCH = batch; U.BATCH_NEW = bs

def leaks(U):
    names = ["IDXP", "OUTDIR", "ACCOUNTS", "ACC_LG_PATH", "EMPTY_PATH"]
    bad = [n for n in names if hasattr(U, n) and os.path.abspath(getattr(U, n)).lower().startswith(ROOT.lower())]
    if getattr(U, "run_child", None) and U.run_child.__module__ == U.__name__: bad.append("run_child")
    if getattr(U, "sync_playwright", None) is not fake_pw: bad.append("sync_playwright")
    return bad

def run(src_path, batch, clean=False, throw_first=False, bs=3):
    tmp = tempfile.mkdtemp(prefix="fsu_batch_")
    make_sandbox(tmp)
    U = load("fsu_" + os.path.basename(tmp), src_path)
    page = FakePage(U, clean=clean, throw_first=throw_first)
    bind(U, tmp, page, batch, bs)
    assert not leaks(U), leaks(U)
    argv0 = sys.argv; sys.argv = [src_path, "--no-rebuild"] + (["--batch"] if batch else [])
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf): U.main()
    finally: sys.argv = argv0
    out = {}
    for f in sorted(os.listdir(os.path.join(tmp, "soloq_matches"))):
        out[f] = open(os.path.join(tmp, "soloq_matches", f), encoding="utf-8").read()
    out["acc_lg"] = open(U.ACC_LG_PATH, encoding="utf-8").read()
    out["accounts"] = open(U.ACCOUNTS, encoding="utf-8").read()
    return U, page, buf.getvalue(), out, tmp

def matches_of(txt):
    m = re.match(r'window\.__sqLoad\((.*)\);\s*$', txt, re.S); return json.loads("[" + m.group(1) + "]")[1]["matches"]

NEW = os.path.join(HERE, "fetch_soloq_update.py")

print("[1] 沙盒守則")
U0 = load("fsu_guard", NEW); pg0 = FakePage(U0)
tmp0 = tempfile.mkdtemp(prefix="fsu_guard_"); make_sandbox(tmp0); bind(U0, tmp0, pg0, True)
check("五個路徑常數＋run_child＋sync_playwright 全部離開真實 repo", not leaks(U0), leaks(U0))
U0.ACCOUNTS = os.path.join(HERE, "soloq_accounts.json")
check("正控制：ACCOUNTS 指回真實檔 → leaks() 抓到", leaks(U0) == ["ACCOUNTS"], leaks(U0))
U0.ACCOUNTS = os.path.join(tmp0, "soloq_accounts.json")
check("模組層有 JS_BATCH／prefetch_batches／USE_BATCH／BATCH_NEW", all(hasattr(U0, n) for n in ("JS_BATCH", "prefetch_batches", "USE_BATCH", "BATCH_NEW")))
check("JS_BATCH 真的包住 JS_NEW（一字不差）", U0.JS_NEW in U0.JS_BATCH and "Promise.all" in U0.JS_BATCH and ".catch(" in U0.JS_BATCH)
check("預設不開批次（管線沒帶 --batch 行為不變；重新載入看 import 時的值）", "--batch" not in sys.argv and load("fsu_default", NEW).USE_BATCH is False and load("fsu_default2", NEW).BATCH_NEW == 8)
shutil.rmtree(tmp0, ignore_errors=True)

print("[2] node 真的跑 JS_BATCH")
def js_lit(s): return json.dumps(s)
node_src = r"""
const one = (%s);
const batch = (%s);
function part(g, extra){ return Object.assign({gameName:g, tagLine:'KR1', win:true, kills:1, deaths:2, assists:3, killParticipation:50,
  championName:'Ahri', lane:'MIDDLE', summoner1Id:4, summoner2Id:14, primaryRuneId:8010, itemActions:[], itemIds:[], startItems:[]}, extra||{}); }
function m(t, q){ return {gameCreation:t, gameDuration:1500, queueId:(q===undefined?420:q), participants:[part('P')]}; }
global.fetch = async (url) => {
  const PU = url.split('/v1/players/')[1].split('/')[0];
  const page = parseInt(url.split('page=')[1]);
  if (PU === 'bad') return {ok:false, status:429};
  if (PU === 'jerr') return {ok:true, status:200, json: async()=>{ throw new Error('json boom'); }};
  if (PU === 'nf') return {ok:false, status:404};
  if (PU === 'ok') return {ok:true, status:200, json: async()=>({matches: page===1 ? [m(2000), m(1800, 440), m(1500), m(1000), m(900)] : []})};
  if (PU === 'two') return {ok:true, status:200, json: async()=>({matches: page===1 ? [m(5000)] : page===2 ? [m(4000)] : []})};
  throw new Error('unknown ' + PU);
};
(async()=>{
  const r = await batch([['ok','middle',1000], ['bad','top',0], ['jerr','top',0], ['nf','top',0], ['two','jungle',0]]);
  console.log(JSON.stringify(r));
})();
""" % (U0.JS_NEW, U0.JS_BATCH)
jsf = os.path.join(tempfile.gettempdir(), "fsu_batch_probe.js")
open(jsf, "w", encoding="utf-8").write(node_src)
try:
    r = subprocess.run(["node", jsf], capture_output=True, text=True, encoding="utf-8", timeout=60)
    res = json.loads(r.stdout.strip().splitlines()[-1])
    check("node 跑得起來、回 5 個結果", isinstance(res, list) and len(res) == 5, (r.stderr or "")[:300])
    check("正常帳號：只收 > newestT 且 queue 420 的（2000、1500），bad=0、id 帶出", res[0]["bad"] == 0 and [g["t"] for g in res[0]["ms"]] == [2000, 1500] and res[0]["id"] == {"g": "P", "t": "KR1"}, res[0])
    check("429 → bad=429、ms 空", res[1].get("bad") == 429 and res[1]["ms"] == [], res[1])
    check("json() 炸掉 → 走 .catch → {err}", "err" in res[2] and "json boom" in res[2]["err"], res[2])
    check("404 → 不算 bad（bad=0、ms 空）", res[3].get("bad") == 0 and res[3]["ms"] == [], res[3])
    check("翻頁：第 2 頁也收（5000、4000）", [g["t"] for g in res[4]["ms"]] == [5000, 4000], res[4])
except Exception as e:
    check("node 執行 JS_BATCH", False, repr(e))

print("[3] 循序 vs 批次（bs=3）：輸出逐檔相同、呼叫次數對")
Us, ps, outs_txt, outs, tmps = run(NEW, batch=False)
Ub, pb, outb_txt, outb, tmpb = run(NEW, batch=True)
check("六個逐場檔＋acc_lastgame＋accounts 全部相同", outs == outb, [k for k in outs if outs[k] != outb.get(k)])
check("循序：JS_NEW 9 次（7 帳號＋d1、e1 各重試 1 次）、JS_BATCH 0 次", ps.n_calls("n") == 9 and ps.n_calls("B") == 0, (ps.n_calls("n"), ps.n_calls("B")))
check("批次：JS_BATCH 3 次、大小 3／3／1（d1 回 429 → 減半為 2）", [len(c[1]) for c in pb.calls if c[0] == "B"] == [3, 3, 1], [c for c in pb.calls if c[0] == "B"])
check("批次：JS_NEW 只剩 4 次（d1 兩次、e1 兩次）", pb.n_calls("n") == 4 and sorted(c[1] for c in pb.calls if c[0] == "n") == ["pu-d1", "pu-d1", "pu-e1", "pu-e1"], [c for c in pb.calls if c[0] == "n"])
check("批次：命中 5、退回逐一 2、減半 1 次（日誌行）", re.search(r"批次預抓 \d+s：7 個帳號／3 批（批次大小 3）、命中 5、退回逐一 2、減半 1 次", outb_txt), outb_txt)
check("循序模式沒有批次日誌行", "批次預抓" not in outs_txt)
check("路線 token 逐選手正確（A middle／B top／C jungle／D bottom／E utility）",
      {c[1]: c[2] for c in pb.calls if c[0] == "b1"} .items() >= {"pu-a1": "middle", "pu-b1": "top", "pu-c1": "jungle", "pu-e1": "utility"}.items()
      and [c[2] for c in pb.calls if c[0] == "n" and c[1] == "pu-d1"] == ["bottom", "bottom"], pb.calls)
mA = matches_of(outb["p1.js"]); check("A：兩個帳號各自的新場合併（1500、1300、1200、1000），900 沒收", [g["t"] for g in mA] == [1500, 1300, 1200, 1000], [g["t"] for g in mA])
check("B：沒新場 → 檔案原樣", matches_of(outb["p2.js"]) == [game(2000)])
check("C：newestT 0 → 500 收進來", [g["t"] for g in matches_of(outb["p3.js"])] == [500])
check("D：批次 429 → 退回逐一 → 第一次 429 睡 1.5s → 第二次成功 3000", [g["t"] for g in matches_of(outb["p4.js"])] == [3000, 100] and 1.5 in pb.U.time.sleeps)
check("E：逐一兩次都 503 → 丟掉、檔案不動、印出「這輪不採用」", matches_of(outb["p5.js"]) == [game(50)] and "E#KR1 dpm 回 503（重試仍失敗）→ 這輪不採用" in outb_txt, outb_txt)
check("F：改名 OldF#KR1 → NewF#KR1 同步進 accounts（兩種模式都一樣）", '"riotId": "NewF#KR1"' in outb["accounts"] and outb["accounts"] == outs["accounts"])
lg = json.loads(re.search(r"=\s*(\{.*\})\s*;", outb["acc_lg"], re.S).group(1))
check("acc_lastgame：a1 1500／a2 1300／c 500／d 3000／f 800，e 沒有", lg.get("a1#kr1") == 1500 and lg.get("a2#kr1") == 1300 and lg.get("c#kr1") == 500 and lg.get("d#kr1") == 3000 and lg.get("f#kr1") is None and lg.get("oldf#kr1") == 800 and "e#kr1" not in lg, lg)
order_s = re.findall(r"^\[\d+/6\] (\S+)", outs_txt, re.M); order_b = re.findall(r"^\[\d+/6\] (\S+)", outb_txt, re.M)
check("寫檔／列印順序＝keys 順序（兩種模式一樣）", order_s == order_b == ["T1|A", "T3|C", "T4|D", "T6|F"], (order_s, order_b))
check("批次少睡：批次 %.1fs < 循序 %.1fs（少掉 5 個 0.1s）" % (pb.U.time.slept, ps.U.time.slept), abs((ps.U.time.slept - pb.U.time.slept) - 0.5) < 1e-6)
check("新選手 T7|G → 子程序（假的）被叫、帶 --no-rebuild", len(Ub.CHILD) == 1 and Ub.CHILD[0][0] == "新選手補全年" and "--missing" in Ub.CHILD[0][1] and "--no-rebuild" in Ub.child_cmd(Ub.CHILD[0][1], ["x", "--no-rebuild"]), Ub.CHILD)

print("[4] 整批 evaluate 炸掉 → 那批退回逐一，輸出仍相同")
Ut, pt, outt_txt, outt, tmpt = run(NEW, batch=True, throw_first=True)
check("輸出與循序相同", outt == outs, [k for k in outs if outs[k] != outt.get(k)])
check("日誌有「批次抓錯 … 這 3 個帳號改逐一問」、退回逐一 5", "這 3 個帳號改逐一問" in outt_txt and "退回逐一 5" in outt_txt, outt_txt)
check("JS_NEW 3＋4＝7 次", pt.n_calls("n") == 7, pt.n_calls("n"))

print("[5] 舊版（git HEAD）正控制")
old_src = subprocess.run(["git", "show", "HEAD:scripts/fetch_soloq_update.py"], capture_output=True, text=True, encoding="utf-8", cwd=ROOT).stdout
check("舊版沒有 JS_BATCH／prefetch_batches／bad 回報（不是早就有）", old_src and "JS_BATCH" not in old_src and "prefetch_batches" not in old_src and "bad=r.status" not in old_src)
oldf = os.path.join(tempfile.gettempdir(), "fsu_old_head.py")
open(oldf, "w", encoding="utf-8").write(old_src)
Uo, po, outo_txt, outo, tmpo = run(oldf, batch=False, clean=True)
Un, pn, outn_txt, outn, tmpn = run(NEW, batch=False, clean=True)
Unb, pnb, outnb_txt, outnb, tmpnb = run(NEW, batch=True, clean=True)
check("乾淨資料：舊版循序 ＝ 新版循序 ＝ 新版批次（逐檔）", outo == outn == outnb, [k for k in outo if not (outo[k] == outn.get(k) == outnb.get(k))])
check("乾淨資料：批次 JS_BATCH 3 次、JS_NEW 0 次、沒減半", pnb.n_calls("B") == 3 and pnb.n_calls("n") == 0 and "減半 0 次" in outnb_txt, (pnb.n_calls("B"), pnb.n_calls("n")))

print("[6] 真實檔沒被動")
check("真實 index／accounts／acc_lastgame／year_empty／soloq_matches 目錄 mtime 全部不變", snap() == SNAP0, [k for k in SNAP0 if SNAP0[k] != snap().get(k)])
for t in (tmps, tmpb, tmpt, tmpo, tmpn, tmpnb): shutil.rmtree(t, ignore_errors=True)
print(f"\n{OK} 通過／{FAIL} 失敗")
sys.exit(1 if FAIL else 0)
