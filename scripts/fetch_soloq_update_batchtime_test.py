# -*- coding: utf-8 -*-
"""⑤d fetch_soloq_update「批次分項」量測（2026-09-16 線 3，精進迴圈 #130）——不打網路、不寫任何正本。

① 沙盒守則：只 import 模組、不跑 main()；load_player_file 換成假的；跑完真實 soloq_matches／帳號檔／索引 mtime 沒動。
② pool_estimate（滑動視窗派工模擬）：已知答案、寬 1＝相加、寬無限＝最大值、負值夾 0；突變：把寬度當成批次（Promise.all）算會變大。
③ batch_breakdown：沒批次回 None、沒 el 只印每批秒數、有 el 印中位／P90／最慢／模擬秒數（數字跟 pool_estimate 一致）；
   措辭不含「牆鐘」「合計」（shift_log_archive 的 RE_WALL／update_health 都在 parse 同一份日誌）。
④ node 真的跑 JS_BATCH：假 fetch 延遲 300ms／0ms／json 炸掉 ⇒ el 分別 ≥280／<150／err 也帶 el；ms／id／bad 欄位照舊；JS_NEW 跟改動前一字不差。
⑤ prefetch_batches 用假 pg：每批（含炸掉那批）都記 secs、帶 el 的結果記進 lat、減半行為不變。
⑥ 正控制（釘 OLDREV＝改動前那個 commit）：舊版 JS_BATCH 沒有 el、沒有 pool_estimate／batch_breakdown、st 沒有 secs ⇒ 印不出分項。
用法：python scripts/fetch_soloq_update_batchtime_test.py
"""
import os, sys, io, re, json, tempfile, subprocess, importlib.util, contextlib

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
NEW = os.path.join(HERE, "fetch_soloq_update.py")
OLDREV = "55612ad3"   # #130 改動之前的 HEAD（別寫 HEAD：commit 之後 HEAD 就是新版，見 DAILY #93）
OK = FAIL = 0
def check(name, cond, info=""):
    global OK, FAIL
    if cond: OK += 1; print(f"  ✓ {name}")
    else: FAIL += 1; print(f"  ✗ {name}  {info}")

if HERE not in sys.path: sys.path.insert(0, HERE)   # soloq_src
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

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

U = load("fsu_bt_new", NEW)

print("[1] 模組形狀")
check("有 pool_estimate／batch_breakdown", callable(getattr(U, "pool_estimate", None)) and callable(getattr(U, "batch_breakdown", None)))
check("JS_BATCH 仍包住 JS_NEW、Promise.all、.catch(，而且多了 el", U.JS_NEW in U.JS_BATCH and "Promise.all" in U.JS_BATCH and ".catch(" in U.JS_BATCH and "el:" in U.JS_BATCH and "r.el=" in U.JS_BATCH)
check("main 在批次預抓那行之後印 batch_breakdown", re.search(r"批次預抓[^\n]*\n[^\n]*\n\s*_bd = batch_breakdown\(_BST\)\n\s*if _bd: print\(_bd\)", open(NEW, encoding="utf-8").read()) is not None)

print("[2] pool_estimate 派工模擬")
pe = U.pool_estimate
check("空 ⇒ 0", pe([], 48) == 0.0)
check("96 個 1s、寬 48 ⇒ 2.0", abs(pe([1.0] * 96, 48) - 2.0) < 1e-9, pe([1.0] * 96, 48))
lat = [4.0] + [1.0] * 47 + [1.0] * 48
check("一個 4s 拖尾＋95 個 1s、寬 48 ⇒ 4.0（批次要 5.0）", abs(pe(lat, 48) - 4.0) < 1e-9, pe(lat, 48))
def batch_mode(xs, w):   # 對照：Promise.all 一批等最慢的
    return sum(max(xs[i:i + w]) for i in range(0, len(xs), w))
check("對照組：同一份延遲用批次算＝5.0（突變：把滑動視窗寫成批次會是這個數）", batch_mode(lat, 48) == 5.0)
check("滑動視窗 ≤ 批次（隨機 20 組）", all(pe(x, 7) <= batch_mode(x, 7) + 1e-9 for x in
      ([((i * 37 + j * 11) % 13) / 3.0 for j in range(50)] for i in range(20))))
check("寬 1 ⇒ 相加", abs(pe([0.5, 1.5, 2.0], 1) - 4.0) < 1e-9)
check("寬 ≥ 個數 ⇒ 最大值", abs(pe([0.5, 1.5, 2.0], 99) - 2.0) < 1e-9)
check("負值夾 0", abs(pe([-3.0, 1.0], 1) - 1.0) < 1e-9)

print("[3] batch_breakdown 輸出")
bd = U.batch_breakdown
check("沒批次 ⇒ None", bd({"secs": [], "lat": []}) is None and bd({}) is None)
s1 = bd({"secs": [2.0, 4.0, 3.0], "lat": []})
check("只有每批秒數（沒 el）", s1 and s1.startswith("   批次分項：3 批每批 最快 2.0s／中位 3.0s／最慢 4.0s、相加 9.0s") and "單帳號" not in s1, s1)
L = [(0.2, 1), (0.4, 0), (3.9, 17), (0.3, 2), (0.5, 0), (0.6, 1), (0.7, 0), (0.8, 0), (0.9, 3), (1.0, 0)]
s2 = bd({"secs": [4.0], "lat": L}, width=4)
check("有 el：個數／中位／P90／最慢與那個帳號的新場次", s2 and "單帳號（瀏覽器端）10 個 中位 0.7s／P90 3.9s／最慢 3.9s（那個帳號新場次 17）" in s2, s2)
est = pe([x[0] for x in L], 4)
check("模擬秒數＝pool_estimate 同一份延遲", s2 and ("改滑動視窗 4 路照同一份延遲模擬 %.1fs" % est) in s2, (s2, est))
check("預設寬度＝BATCH_NEW", ("改滑動視窗 %d 路" % U.BATCH_NEW) in (bd({"secs": [1.0], "lat": L}) or ""))
check("措辭不含「牆鐘」「合計」", all(w not in (s1 + s2) for w in ("牆鐘", "合計")))
check("shift_log_archive 的收尾正則不會吃到這行", not re.search(r"^合計 [\d.]+ 分鐘（牆鐘 ([\d.]+)s）", s2.strip()))

print("[4] node 真的跑 JS_BATCH（延遲帶回來）")
node_src = r"""
const batch = (%s);
function part(g){ return {gameName:g, tagLine:'KR1', win:true, kills:1, deaths:2, assists:3, killParticipation:50,
  championName:'Ahri', lane:'MIDDLE', summoner1Id:4, summoner2Id:14, primaryRuneId:8010, itemActions:[], itemIds:[], startItems:[]}; }
function m(t){ return {gameCreation:t, gameDuration:1500, queueId:420, participants:[part('P')]}; }
const sleep = ms => new Promise(r => setTimeout(r, ms));
global.fetch = async (url) => {
  const PU = url.split('/v1/players/')[1].split('/')[0];
  const page = parseInt(url.split('page=')[1]);
  if (PU === 'slow') { await sleep(300); return {ok:true, status:200, json: async()=>({matches: page===1 ? [m(2000)] : []})}; }
  if (PU === 'fast') return {ok:true, status:200, json: async()=>({matches: []})};
  if (PU === 'jerr') { await sleep(100); return {ok:true, status:200, json: async()=>{ throw new Error('json boom'); }}; }
  if (PU === 'bad') return {ok:false, status:429};
  throw new Error('unknown ' + PU);
};
(async()=>{ const r = await batch([['slow','middle',1000], ['fast','top',0], ['jerr','top',0], ['bad','top',0]]); console.log(JSON.stringify(r)); })();
""" % (U.JS_BATCH,)
jsf = os.path.join(tempfile.gettempdir(), "fsu_batchtime_probe_9942.js")
open(jsf, "w", encoding="utf-8").write(node_src)
try:
    r = subprocess.run(["node", jsf], capture_output=True, text=True, encoding="utf-8", timeout=60)
    res = json.loads(r.stdout.strip().splitlines()[-1])
    check("回 4 個結果", isinstance(res, list) and len(res) == 4, (r.stderr or "")[:300])
    check("slow：el ≥ 280ms、欄位照舊（ms 一場 2000、id、bad 0）", res[0]["el"] >= 280 and [g["t"] for g in res[0]["ms"]] == [2000] and res[0]["id"] == {"g": "P", "t": "KR1"} and res[0]["bad"] == 0, res[0])
    check("fast：el < 150ms", res[1]["el"] < 150, res[1])
    check("json 炸掉走 .catch：{err, el ≥ 80}", "json boom" in res[2].get("err", "") and res[2].get("el", -1) >= 80, res[2])
    check("429：bad 照舊、也帶 el", res[3].get("bad") == 429 and isinstance(res[3].get("el"), int), res[3])
except Exception as e:
    check("node 執行 JS_BATCH", False, repr(e))
finally:
    try: os.remove(jsf)
    except Exception: pass

print("[5] prefetch_batches 用假 pg")
class FakePG:
    def __init__(self, with_el=True, boom_first=False):
        self.calls = []; self.with_el = with_el; self.boom_first = boom_first
    def evaluate(self, js, args=None):
        self.calls.append(len(args))
        if self.boom_first and len(self.calls) == 1: raise RuntimeError("整包炸")
        out = []
        for pu, tok, nt in args:
            d = {"id": None, "ms": [{"t": 1}] * (3 if pu.endswith("7") else 0), "bad": 429 if pu == "pu-bad" else 0}
            if self.with_el: d["el"] = 1234 if pu.endswith("7") else 100
            out.append(d)
        return out
def fake_setup(U2):
    keys = [f"T|P{i}" for i in range(9)]
    idx = {"players": {k: {"f": f"p{i}.js", "role": "MIDDLE"} for i, k in enumerate(keys)}}
    accs = {k: [{"dpmPuuid": ("pu-bad" if i == 4 else f"pu-{i}"), "riotId": f"P{i}#1", "platform": "kr"}] for i, k in enumerate(keys)}
    U2.load_player_file = lambda f: ("x", {"matches": [{"t": 5}]})
    return keys, idx, accs
keys, idx, accs = fake_setup(U)
with contextlib.redirect_stdout(io.StringIO()) as so:
    PRE, st = U.prefetch_batches(FakePG(), keys, idx, accs, set(), bs=4)
check("批次大小 4／4／1（pu-bad 在第二批 ⇒ 減半為 2，只剩 1 個）", st["sizes"] == [4, 4, 1], st["sizes"])
check("secs 每批一筆", len(st["secs"]) == st["batches"] == 3, st)
check("lat 每個帶 el 的結果一筆（含 bad 那個）、秒數與新場次正確", len(st["lat"]) == 9 and (1.234, 3) in st["lat"] and (0.1, 0) in st["lat"], st["lat"])
check("命中 8、退回逐一 1、減半 1（行為不變）", (st["hit"], st["fallback"], st["halved"]) == (8, 1, 1), st)
keys, idx, accs = fake_setup(U)
with contextlib.redirect_stdout(io.StringIO()) as so2:
    PRE2, st2 = U.prefetch_batches(FakePG(with_el=False, boom_first=True), keys, idx, accs, set(), bs=4)
check("整包炸掉那批也記 secs、沒 el 不記 lat", len(st2["secs"]) == st2["batches"] and st2["lat"] == [] and st2["fallback"] >= 4, st2)
check("沒 el ⇒ 分項只有每批秒數", "單帳號" not in (U.batch_breakdown(st2) or "單帳號") and U.batch_breakdown(st2).startswith("   批次分項："))

print("[6] 正控制：釘 %s 的舊版" % OLDREV)
try:
    old_src = subprocess.run(["git", "-C", ROOT, "show", f"{OLDREV}:scripts/fetch_soloq_update.py"], capture_output=True, text=True, encoding="utf-8").stdout
    check("拿得到舊版原始碼", len(old_src) > 1000)
    tmpd = tempfile.mkdtemp(prefix="fsu_bt_old_")
    oldp = os.path.join(tmpd, "fetch_soloq_update.py"); open(oldp, "w", encoding="utf-8").write(old_src)
    O = load("fsu_bt_old", oldp)
    check("舊版 JS_BATCH 沒有 el（不是早就有）", "el:" not in O.JS_BATCH and "r.el=" not in O.JS_BATCH)
    check("舊版沒有 pool_estimate／batch_breakdown", not hasattr(O, "pool_estimate") and not hasattr(O, "batch_breakdown"))
    check("JS_NEW 跟舊版一字不差（逐帳號路徑沒被動到）", O.JS_NEW == U.JS_NEW)
    keys, idx, accs = fake_setup(O)
    with contextlib.redirect_stdout(io.StringIO()):
        _, sto = O.prefetch_batches(FakePG(), keys, idx, accs, set(), bs=4)
    check("舊版同一個假 pg：st 沒有 secs／lat ⇒ 印不出分項", "secs" not in sto and "lat" not in sto, sto)
    check("舊版同一個假 pg：批次行為跟新版一樣（大小／命中／退回／減半）", (sto["sizes"], sto["hit"], sto["fallback"], sto["halved"]) == (st["sizes"], st["hit"], st["fallback"], st["halved"]))
except Exception as e:
    check("正控制跑得起來", False, repr(e))

print("[7] 真實檔案沒動")
check("soloq_matches／帳號檔／索引／acc_lastgame 的 mtime 與大小都沒變", snap() == SNAP0)
check("模組層路徑常數仍是正本（這支只 import 不寫，所以不接管；確認沒有被別的測試改掉）", U.OUTDIR == os.path.join(ROOT, "soloq_matches"))

print(f"\n結果：✓ {OK}／✗ {FAIL}")
sys.exit(1 if FAIL else 0)
