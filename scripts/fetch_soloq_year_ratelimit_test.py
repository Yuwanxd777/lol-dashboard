# -*- coding: utf-8 -*-
"""fetch_soloq_year 的「限流不等於 0 場」沙盒測試（2026-11-02 主迴圈 #2441）——不連網、不開瀏覽器、不碰真實 repo。

舊版 JS_YEAR 非 200 只 break、照樣回到目前為止的場次：
  - 第 1 頁就 429 ⇒ 空陣列 ⇒ 被記成「確認 0 場、3 天不重抓」
  - 第 3 頁才 429 ⇒ 前兩頁被當全年寫檔；--only 還會蓋掉原本完整的檔
蓋三層：
  A) 真的用 node 跑 JS_YEAR 配假 fetch：bad 的值、已抓到的場次、跨年界線正常停手時 bad=0
  B) is_transient／year_fetch 的分類
  C) main() 走完整流程（假 playwright、沙盒路徑）：延後／不記空／不蓋檔／真 0 場仍記空／全量模式照寫
正控制：把 JS_YEAR 換回舊的 break 寫法（OLD_BAD），同一個情境必須真的中舊病。

用法：python scripts/fetch_soloq_year_ratelimit_test.py
"""
import contextlib, importlib.util, io, json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OK, BAD = [], []


def chk(name, cond, extra=""):
    (OK if cond else BAD).append(name)
    if not cond:
        print("   FAIL %s %s" % (name, extra))


def load():
    spec = importlib.util.spec_from_file_location("fsy_rl", os.path.join(HERE, "fetch_soloq_year.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def take_over_empty(m, path):
    """load_year_empty／save_year_empty 的 path 預設值在 def 當下就綁死真實檔，只改 m.EMPTY_PATH 接管不到
    （本測試第一版就這樣把假選手寫進真正的 csv_cache/soloq_year_empty.json）。"""
    m.load_year_empty.__defaults__ = (path,)
    d = m.save_year_empty.__defaults__
    m.save_year_empty.__defaults__ = (path,) + d[1:]
    for f in (m.load_year_empty, m.save_year_empty):
        assert f.__defaults__[0] == path, f.__name__


REAL_EMPTY = os.path.join(ROOT, "csv_cache", "soloq_year_empty.json")
REAL_BEFORE = io.open(REAL_EMPTY, "rb").read() if os.path.exists(REAL_EMPTY) else None


M = load()
CUT = 1000


# ───────── A) 真的跑 JS ─────────
def run_js(pages, js=None):
    """pages：每頁一個元素，int＝該頁回這個狀態碼、"throw"＝fetch 丟例外、list＝該頁 200 的 gameCreation 清單。"""
    code = """
const pages=%s; let calls=0;
globalThis.fetch=async(u)=>{ calls++; const p=pages[calls-1]; if(p==='throw') throw new Error('net');
  if(typeof p==='number') return {ok:false,status:p};
  const ms=(p||[]).map(t=>({gameCreation:t,queueId:420,gameDuration:1800,participants:[{championName:'A',win:true}]}));
  return {ok:true,status:200,json:async()=>({matches:ms})}; };
const f=%s;
f(['PU','top',%d]).then(r=>console.log(JSON.stringify({r,calls})));
""" % (json.dumps(pages), js or M.JS_YEAR, CUT)
    d = tempfile.mkdtemp(prefix="rl_js_")
    try:
        fp = os.path.join(d, "t.js")
        io.open(fp, "w", encoding="utf-8").write(code)
        out = subprocess.run(["node", fp], capture_output=True, encoding="utf-8", timeout=30)
        if out.returncode != 0:
            raise RuntimeError(out.stderr[:400])
        return json.loads(out.stdout)
    finally:
        shutil.rmtree(d, ignore_errors=True)


x = run_js([429])
chk("JS 第 1 頁 429 ⇒ bad=429、0 場", x["r"]["bad"] == 429 and x["r"]["g"] == [] and x["calls"] == 1, x)
x = run_js([[5000, 4000], [3000], 429])
chk("JS 第 3 頁 429 ⇒ bad=429、留前兩頁 3 場", x["r"]["bad"] == 429 and len(x["r"]["g"]) == 3 and x["calls"] == 3, x)
x = run_js(["throw"])
chk("JS 連線失敗 ⇒ bad=-1", x["r"]["bad"] == -1, x)
x = run_js([[5000], [4000, 500]])
chk("JS 跨年界線正常停手 ⇒ bad=0、不含界線前的局", x["r"]["bad"] == 0 and len(x["r"]["g"]) == 2 and x["calls"] == 2, x)
x = run_js([[]])
chk("JS 第 1 頁 200 空 ⇒ bad=0（真的 0 場）", x["r"]["bad"] == 0 and x["r"]["g"] == [], x)
x = run_js([404])
chk("JS 404 ⇒ bad=404", x["r"]["bad"] == 404, x)

# ───────── B) 分類 ─────────
for v in (-1, 403, 408, 425, 429, 500, 502, 503, 520):
    chk("暫時性 %s" % v, M.is_transient(v))
for v in (0, 400, 401, 404, 410):
    chk("不是暫時性 %s" % v, not M.is_transient(v))


class EvalPg:
    def __init__(self, ret=None, exc=None):
        self.ret, self.exc = ret, exc

    def evaluate(self, js, a):
        if self.exc:
            raise self.exc
        return self.ret


chk("year_fetch 正常", M.year_fetch(EvalPg({"g": [{"t": 1}], "bad": 0}), "p", "top", 0) == ([{"t": 1}], None))
chk("year_fetch 429 帶已抓場次", M.year_fetch(EvalPg({"g": [{"t": 1}], "bad": 429}), "p", "top", 0) == ([{"t": 1}], "HTTP 429"))
chk("year_fetch 404 當沒問題", M.year_fetch(EvalPg({"g": [], "bad": 404}), "p", "top", 0) == ([], None))
chk("year_fetch 例外算暫時性", M.year_fetch(EvalPg(exc=RuntimeError("x")), "p", "top", 0)[1].startswith("抓錯"))
chk("year_fetch 舊格式（陣列）算暫時性、不崩", M.year_fetch(EvalPg([{"t": 1}]), "p", "top", 0)[1] is not None)


# ───────── C) main 全流程 ─────────
class FakePg:
    """依 puuid 回 JS_YEAR 的結果；role_counts／盤查探針都回得過去。"""

    def __init__(self, script, js_year):
        self.script, self.js_year, self.asked = script, js_year, []

    def goto(self, *a, **k):
        pass

    def evaluate(self, js, a=None):
        if js == self.js_year:
            self.asked.append(a[0])
            r = self.script[a[0]]
            if isinstance(r, Exception):
                raise r
            return r
        if isinstance(a, str):
            return {"top": 5, "jungle": 0, "middle": 0, "bottom": 0, "utility": 0}
        return 200


class FakeBrowser:
    def __init__(self, pg):
        self.pg = pg

    def new_context(self, **k):
        return self

    def new_page(self):
        return self.pg

    def close(self):
        pass


class FakePW:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def sandbox(script, *, missing=True, only="", js_year=None, seed_empty=None, seed_file=None, staging=False):
    """main() 跑一趟：所有路徑常數都接管到暫存目錄；回傳 (輸出, 空名單, 目錄內容, 索引, 問過的 puuid)。"""
    m = load()
    d = tempfile.mkdtemp(prefix="rl_main_")
    try:
        accs = [{"team": "T", "player": k, "riotId": k + "#1", "dpmPuuid": k} for k in script]
        acc_path = os.path.join(d, "acc.json")
        json.dump(accs, io.open(acc_path, "w", encoding="utf-8"))
        out = os.path.join(d, "out")
        os.makedirs(out)
        idx_path = os.path.join(d, "idx.js")
        idx_players = {}
        if seed_file:
            key, body = seed_file
            io.open(os.path.join(out, "p0.js"), "w", encoding="utf-8").write(
                "window.__sqLoad(%s,%s);\n" % (json.dumps(key), json.dumps(body)))
            idx_players[key] = {"f": "p0.js", "role": "TOP", "n": len(body["matches"])}
        io.open(idx_path, "w", encoding="utf-8").write("window.SOLOQ_MATCH_IDX=" + json.dumps({"players": idx_players}) + ";\n")
        empty = os.path.join(d, "empty.json")
        if seed_empty:
            json.dump(seed_empty, io.open(empty, "w", encoding="utf-8"))
        m.ACCOUNTS, m.OUTDIR, m.IDX, m.EMPTY_PATH, m.ACC_LG_PATH = acc_path, out, idx_path, empty, os.path.join(d, "lg.js")
        take_over_empty(m, empty)
        m._OUT = "sandbox"
        m.STAGING, m.MISSING, m.ONLY, m.MAXP, m.RETRY_EMPTY = staging, missing, only, 0, False
        m.CUT = CUT
        m.comp_roles = lambda: {}
        if js_year:
            m.JS_YEAR = js_year
        pg = FakePg(script, m.JS_YEAR)
        m.sync_playwright = lambda: FakePW()
        m._launch_real = lambda p: FakeBrowser(pg)
        m.time.sleep = lambda s: None
        # 漏接就在寫壞正本之前擋下
        for n in ("ACCOUNTS", "OUTDIR", "IDX", "EMPTY_PATH", "ACC_LG_PATH"):
            assert getattr(m, n).startswith(d), n
        argv, sys.argv = sys.argv, ["x", "--no-rebuild"]
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                m.main()
        finally:
            sys.argv = argv
        em = json.load(io.open(empty, encoding="utf-8")) if os.path.exists(empty) else {}
        files = {fn: io.open(os.path.join(out, fn), encoding="utf-8").read() for fn in os.listdir(out)}
        idx = json.loads(io.open(idx_path, encoding="utf-8").read().split("=", 1)[1].rstrip(";\n"))["players"]
        return buf.getvalue(), em, files, idx, pg.asked
    finally:
        shutil.rmtree(d, ignore_errors=True)


G = lambda *ts: [{"t": t} for t in ts]
OK_R = lambda *ts: {"g": G(*ts), "bad": 0}
LIM_R = lambda *ts: {"g": G(*ts), "bad": 429}

# --missing：一位第 1 頁就限流、一位中途限流、一位真 0 場、一位正常、一位頁面掛了、一位 404
txt, em, files, idx, asked = sandbox({
    "a": LIM_R(), "b": LIM_R(5000, 4000), "c": OK_R(), "d": OK_R(5000, 4000, 3000),
    "e": RuntimeError("page crashed"), "f": {"g": [], "bad": 404},
})
chk("限流 0 場不進空名單", "T|a" not in em, em)
chk("中途限流不進空名單", "T|b" not in em, em)
chk("頁面崩潰不進空名單", "T|e" not in em, em)
chk("真 0 場仍進空名單", em.get("T|c", {}).get("tries") == 1, em)
chk("404 維持舊行為進空名單", "T|f" in em, em)
chk("正常的不進空名單", "T|d" not in em, em)
chk("中途限流不寫檔", "T|b" not in idx, idx)
chk("正常的有寫檔且 3 場", idx.get("T|d", {}).get("n") == 3, idx)
chk("只寫了正常那一個檔", len(files) == 1, list(files))
chk("限流之後的選手照常問", asked == ["a", "b", "c", "d", "e", "f"], asked)
chk("日誌講清楚延後 3 位", "⏳ 3 位" in txt and "T|a" in txt.split("⏳ 3 位")[1], txt[-300:])
chk("日誌帶狀態碼", "HTTP 429" in txt)

# 已在空名單、到期重試又被限流 ⇒ 記錄不動（tries 不累加、日期不刷新，下一班還會試）
txt, em, *_ = sandbox({"a": LIM_R()}, seed_empty={"T|a": {"at": "2020-01-01", "tries": 7}})
chk("到期重試被限流：空名單原封不動", em.get("T|a") == {"at": "2020-01-01", "tries": 7}, em)

# 全部限流也不崩、離開路徑走完
txt, em, files, idx, _ = sandbox({"a": LIM_R(), "b": LIM_R()})
chk("全部限流：沒有檔、沒有空名單", not files and not em, (files, em))
chk("全部限流：main 走到收尾", "完成：" in txt, txt[-200:])

# --only：既有完整檔不被截斷的結果蓋掉；沒限流才覆寫
full = {"role": "TOP", "matches": G(9, 8, 7, 6, 5, 4)}
txt, em, files, idx, _ = sandbox({"a": LIM_R(5000)}, missing=False, only="T|a", seed_file=("T|a", full))
chk("--only 被限流：原檔 6 場留著", json.dumps(full) in files.get("p0.js", ""), files)
chk("--only 被限流：索引 n 不變", idx.get("T|a", {}).get("n") == 6, idx)
txt, em, files, idx, _ = sandbox({"a": OK_R(5000)}, missing=False, only="T|a", seed_file=("T|a", full))
chk("--only 沒限流：照舊覆寫（正例會動）", idx.get("T|a", {}).get("n") == 1, idx)

# 全量模式（part=False）：沒有舊檔可留，略過等於把人拿掉 ⇒ 照寫＋警告
txt, em, files, idx, _ = sandbox({"a": LIM_R(5000)}, missing=False, staging=True)
chk("全量模式被限流：照寫", "p0.js" in files and '"t": 5000' in files["p0.js"], list(files))
chk("全量模式被限流：有警告", "沒問完" in txt, txt[-200:])

# 多帳號：一個帳號限流就整位延後（不可只留半邊帳號的場次）
m2 = load()
d = tempfile.mkdtemp(prefix="rl_two_")
try:
    m2.ACCOUNTS = os.path.join(d, "acc.json")
    json.dump([{"team": "T", "player": "a", "riotId": "x#1", "dpmPuuid": "x"},
               {"team": "T", "player": "a", "riotId": "y#1", "dpmPuuid": "y"}], io.open(m2.ACCOUNTS, "w", encoding="utf-8"))
    m2.OUTDIR = os.path.join(d, "out")
    os.makedirs(m2.OUTDIR)
    m2.IDX = os.path.join(d, "idx.js")
    io.open(m2.IDX, "w", encoding="utf-8").write('window.SOLOQ_MATCH_IDX={"players":{}};\n')
    m2.EMPTY_PATH, m2.ACC_LG_PATH = os.path.join(d, "e.json"), os.path.join(d, "lg.js")
    take_over_empty(m2, m2.EMPTY_PATH)
    m2.STAGING, m2.MISSING, m2.ONLY, m2.MAXP, m2.RETRY_EMPTY = False, True, "", 0, False
    m2.comp_roles = lambda: {}
    pg2 = FakePg({"x": OK_R(5000), "y": LIM_R()}, m2.JS_YEAR)
    m2.sync_playwright = lambda: FakePW()
    m2._launch_real = lambda p: FakeBrowser(pg2)
    m2.time.sleep = lambda s: None
    argv, sys.argv = sys.argv, ["x", "--no-rebuild"]
    with contextlib.redirect_stdout(io.StringIO()):
        m2.main()
    sys.argv = argv
    chk("雙帳號一個限流：不寫檔", not [f for f in os.listdir(m2.OUTDIR) if f.endswith(".js") and f.startswith("p")])
    chk("雙帳號一個限流：有抓到的那個也不算 0 場", not os.path.exists(m2.EMPTY_PATH) or "T|a" not in json.load(io.open(m2.EMPTY_PATH, encoding="utf-8")))
finally:
    shutil.rmtree(d, ignore_errors=True)

# ───────── 正控制：舊寫法同一情境要真的中舊病 ─────────
OLD_JS = M.JS_YEAR.replace("{bad=-1;break;}", "{break;}").replace("{bad=r.status;break;}", "break;")
chk("正控制前提：舊 JS 真的跟新版不同", OLD_JS != M.JS_YEAR and "bad=r.status" not in OLD_JS)
x = run_js([[5000, 4000], 429], OLD_JS)
chk("正控制：舊 JS 第 2 頁 429 ⇒ bad 是 0（看不出沒問完）", x["r"]["bad"] == 0 and len(x["r"]["g"]) == 2, x)
# 舊病的端到端：把 is_transient 關掉（等於舊版不分辨）⇒ 限流被記 0 場、截斷被寫檔
_orig_load = load


def load_old():
    m = _orig_load()
    m.is_transient = lambda bad: False
    return m


load = load_old
txt, em, files, idx, _ = sandbox({"a": LIM_R(), "b": LIM_R(5000)})
load = _orig_load
chk("正控制：不分辨限流 ⇒ 限流被記成 0 場", "T|a" in em, em)
chk("正控制：不分辨限流 ⇒ 截斷的 1 場被寫檔", idx.get("T|b", {}).get("n") == 1, idx)

REAL_AFTER = io.open(REAL_EMPTY, "rb").read() if os.path.exists(REAL_EMPTY) else None
chk("真實 soloq_year_empty.json 一個位元沒動", REAL_BEFORE == REAL_AFTER)
print("通過 %d／失敗 %d" % (len(OK), len(BAD)))
sys.exit(1 if BAD else 0)
