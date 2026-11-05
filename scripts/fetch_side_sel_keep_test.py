# -*- coding: utf-8 -*-
"""fetch_side_sel 抓不到時的處理（#2612）的沙盒測試。

把被測腳本複製到沙盒的 scripts/，旁邊放假的 fetch_wiki_mh／fetch_wiki_stats，用子程序跑 __main__，
所以路徑全在沙盒、離開碼測得到、沒有任何請求出去。HTML 備援的素材是真實快取頁
（2026 First Stand，手寫 HTML parse() 不認得）。

環境變數 SS_SRC 可指定被測檔（突變測試用）。舊版對照釘 f01dee54。

用法：python -u scripts/fetch_side_sel_keep_test.py
"""
import hashlib, io, json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, HERE)
import fetch_side_sel as REAL

OLDREV = "f01dee54"
SRC = os.environ.get("SS_SRC") or os.path.join(HERE, "fetch_side_sel.py")
REAL_OUT = os.path.join(ROOT, "side_sel.js")
REAL_PAGE = os.path.join(ROOT, "csv_cache", "sidesel", "2026_first_stand.html")
FS = "2026 First Stand"
OK2 = "LCK/2026 Season/ZZ Fine 9942"
EXTRA = ["LPL/2026 Season/ZZ Extra %d" % i for i in range(1, 6)]

FAKE_WS = r'''
import io, json, os, time, urllib.error, urllib.parse
ROOTD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SC = json.load(io.open(os.path.join(ROOTD, "scenario.json"), encoding="utf-8"))
FORM = "https://fake.invalid/cargo"
UA = {}
time.sleep = lambda s: open(os.path.join(ROOTD, "sleep.txt"), "a").write("%s\n" % s)
class R:
    def __init__(self, t): self.t = t
    def read(self): return self.t.encode("utf-8")
class O:
    def open(self, req, timeout=None):
        url = req.full_url
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        tb, wh = q.get("tables", [""])[0], q.get("where", [""])[0]
        open(os.path.join(ROOTD, "reqs.txt"), "a", encoding="utf-8").write(tb + " | " + wh + "\n")
        if tb.startswith("ScoreboardGames") and "OverviewPage" in q.get("fields", [""])[0] and "< " in wh:
            m = SC["ov"]
            if m == "exc": raise OSError("ov down")
            if m == "html": return R("<html>blocked</html>")
            return R(json.dumps([{"ov": o} for o in m]))
        if tb.startswith("ScoreboardGames"):
            return R(json.dumps([{"ov": o} for o in SC.get("live", [])]))
        if tb.startswith("MatchScheduleGame"):
            if any(b in wh for b in SC.get("cargo_bad", [])):
                raise urllib.error.HTTPError(url, 403, "x", {}, None)
            out = []
            for o, rs in SC.get("cargo", {}).items():
                if '"%s"' % o in wh: out += rs
            return R(json.dumps(out))
        if tb.startswith("MatchSchedule"):
            out = []
            for o, rs in SC.get("sched", {}).items():
                if '"%s"' % o in wh: out += rs
            return R(json.dumps(out))
        raise OSError("unexpected " + tb)
def opener(): return O()
'''
FAKE_MH = r'''
import io, json, os, urllib.parse
ROOTD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SC = json.load(io.open(os.path.join(ROOTD, "scenario.json"), encoding="utf-8"))
UA = {}
class R:
    def __init__(self, t): self.t = t
    def read(self): return self.t.encode("utf-8")
class O:
    def open(self, req, timeout=None):
        open(os.path.join(ROOTD, "api.txt"), "a", encoding="utf-8").write(req.full_url + "\n")
        if SC.get("api") == "down": raise OSError("api down")
        p = urllib.parse.parse_qs(urllib.parse.urlparse(req.full_url).query)["page"][0]
        if p in SC.get("api_fail", []): raise OSError("api flaky")
        h = SC.get("api_pages", {}).get(p)
        if h is None: return R(json.dumps({"error": {"code": "missingtitle"}}))
        return R(json.dumps({"parse": {"text": io.open(os.path.join(ROOTD, h), encoding="utf-8").read()}}))
def opener(): return O()
'''

OK, BAD = [], []


def chk(name, f):
    try:
        v = bool(f())
    except Exception as e:
        v = False
        name += "（%s: %s）" % (type(e).__name__, e)
    (OK if v else BAD).append(name)
    print(("  ✓ " if v else "  ✗ ") + name)


def rec(ov, d, t1, t2, gi, **kw):
    r = {"d": d, "t1": t1, "t2": t2, "gi": gi, "ss": "b", "blue": "A", "red": "B", "pc": 1, "fs": "A", "ps": "A",
         "ov": ov, "mvp": "", "mvpm": "", "mg": 0, "mm": 0, "vod": "", "vodk": "", "bo": 5}
    r.update(kw)
    return r


def cargo_row(ov, gid, t1="T One", t2="T Two", ng=1):
    return {"ov": ov, "mid": "%s_%s" % (ov, gid), "ng": ng, "gid": gid, "blue": t1, "red": t2, "sel": t1, "psel": t1,
            "fsel": t1, "fp": t1, "vod": "", "vodpb": "", "vodst": "", "mvp": "", "dt": "2026-05-01 10:00:00",
            "t1": t1, "t2": t2, "mvpm": "", "bo": "3"}


class Box:
    def __init__(self, src, scenario, old):
        self.d = tempfile.mkdtemp(prefix="sidesel_keep_")
        os.makedirs(os.path.join(self.d, "scripts"))
        os.makedirs(os.path.join(self.d, "csv_cache", "sidesel"))
        with io.open(os.path.join(self.d, "scripts", "fetch_side_sel.py"), "w", encoding="utf-8", newline="") as f:
            f.write(src)
        io.open(os.path.join(self.d, "scripts", "fetch_wiki_stats.py"), "w", encoding="utf-8").write(FAKE_WS)
        io.open(os.path.join(self.d, "scripts", "fetch_wiki_mh.py"), "w", encoding="utf-8").write(FAKE_MH)
        json.dump(scenario, io.open(os.path.join(self.d, "scenario.json"), "w", encoding="utf-8"))
        self.out = os.path.join(self.d, "side_sel.js")
        if old is not None:
            io.open(self.out, "w", encoding="utf-8").write("window.SIDE_SEL=" + json.dumps(old, ensure_ascii=False) + ";")

    def cache_page(self, ov, html_path):
        shutil.copy(html_path, REAL.cache_path(ov).replace(REAL.CACHE, os.path.join(self.d, "csv_cache", "sidesel")))

    def run(self, *args):
        p = subprocess.run([sys.executable, "-u", os.path.join(self.d, "scripts", "fetch_side_sel.py")] + list(args),
                           capture_output=True, cwd=self.d, timeout=120)
        self.rc, self.log = p.returncode, p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")
        return self

    def data(self):
        t = io.open(self.out, encoding="utf-8").read()
        return json.loads(t[t.index("=") + 1:].rstrip().rstrip(";"))

    def md5(self):
        return hashlib.md5(open(self.out, "rb").read()).hexdigest()

    def count(self, name):
        p = os.path.join(self.d, name)
        return sum(1 for _ in open(p, encoding="utf-8")) if os.path.exists(p) else 0

    def close(self):
        shutil.rmtree(self.d, ignore_errors=True)


def html_material():
    """真實快取頁解析出來的系列 → 假賽程（隊名、比分都對得上，HTML 路徑才配得到）。"""
    sers = REAL.parse(FS, io.open(REAL_PAGE, encoding="utf-8").read())
    sched, games = [], []
    for i, s in enumerate(x for x in sers if x["games"]):
        a, b = s["score"].split(" - ") if " - " in s["score"] else (s["score"].split("-") + ["0"])[:2]
        d = "2026-03-%02d" % (i % 28 + 1)
        sched.append({"ov": FS, "dt": d + " 10:00:00", "t1": s["t1"], "t2": s["t2"], "s1": a.strip(), "s2": b.strip()})
        for g in s["games"]:
            games.append(rec(FS, d, s["t1"], s["t2"], g["gi"], bo=5, vod="https://old/%d" % len(games), vodk="pb"))
    return sched, games


def fallback_scene(src):
    """FS 被 Cargo 擋、OK2 正常；舊檔有 FS 全部局（少最後 2 局）＋一局快取頁沒有的局。"""
    sched, games = html_material()
    only_old = rec(FS, "2026-01-01", "Old A", "Old B", 1, bo=1, ss="")
    old = games[:-2] + [only_old, rec(OK2, "2026-02-01", "T One", "T Two", 1, bo=3, ss="r")]
    sc = {"ov": [FS, OK2], "live": [], "cargo_bad": [FS], "sched": {FS: sched},
          "cargo": {OK2: [cargo_row(OK2, 1), cargo_row(OK2, 2, ng=2)]}}
    b = Box(src, sc, old)
    b.cache_page(FS, REAL_PAGE)
    return b, games, only_old


def t_fallback(src):
    print("── Cargo 擋一頁，HTML 備援吃舊快取")
    b, games, only_old = fallback_scene(src)
    b.run()
    d = b.data()
    fs = [r for r in d if r["ov"] == FS]
    chk("rc 0（備援有接住）", lambda: b.rc == 0)
    chk("舊檔有、快取沒有的局留著", lambda: any(r["t1"] == "Old A" for r in fs))
    chk("舊檔有的局留舊值（bo=5、VOD 是舊的）", lambda: all(r["bo"] == 5 and r["vod"].startswith("https://old/")
                                                 for r in fs if r["t1"] != "Old A" and r["bo"] != 0))
    chk("舊局一局不少", lambda: sum(1 for r in fs if r["bo"] == 5) == len(games) - 2)
    chk("快取比舊檔多的 2 局有補進來", lambda: sum(1 for r in fs if r["bo"] == 0) == 2)
    chk("同一局沒有重複", lambda: len({(r["d"], r["t1"], r["t2"], r["gi"]) for r in fs}) == len(fs))
    chk("正常的頁照 Cargo 更新（2 局，舊檔那局換掉）",
        lambda: [r["ss"] for r in d if r["ov"] == OK2] == ["b", "b"])
    chk("日誌講清楚留舊檔", lambda: "留舊檔的" in b.log and "HTML 備援新增 2 局" in b.log)
    chk("沒有留 tmp", lambda: not os.path.exists(b.out + ".tmp"))
    b.close()


def t_api_down(src):
    print("── Cargo 與 api.php 都掛")
    pages = [FS] + EXTRA
    old = [rec(o, "2026-01-02", "A", "B", 1) for o in pages]
    b = Box(src, {"ov": pages, "live": pages, "cargo_bad": pages, "api": "down", "sched": {}}, old)
    h0 = b.md5()
    b.run()
    chk("rc 1", lambda: b.rc == 1)
    chk("舊檔一個位元沒動", lambda: b.md5() == h0)
    chk("只打 2 頁（2×3 次）就停", lambda: b.count("api.txt") == 6)
    chk("日誌有 ⚠", lambda: "這班不再上網" in b.log)
    b.close()


def t_api_error_not_trip(src):
    print("── api.php 回 error（站是好的）不算連不上")
    pages = [FS] + EXTRA
    old = [rec(o, "2026-01-02", "A", "B", 1) for o in pages]
    b = Box(src, {"ov": pages, "live": pages, "cargo_bad": pages, "sched": {}}, old)
    b.run()
    chk("每頁都有問到", lambda: b.count("api.txt") == len(pages))
    chk("沒有熔斷", lambda: "這班不再上網" not in b.log)
    chk("沒資料但舊檔沒動、rc 1", lambda: b.rc == 1 and len(b.data()) == len(pages))
    b.close()


def t_refetch_ok(src):
    print("── Cargo 擋、api.php 重抓得到真實頁")
    sched, games = html_material()
    b = Box(src, {"ov": [FS], "live": [FS], "cargo_bad": [FS], "sched": {FS: sched}, "api_pages": {FS: "page.html"}}, [])
    shutil.copy(REAL_PAGE, os.path.join(b.d, "page.html"))
    b.run()
    chk("解析得出來（沒有舊檔時全收）", lambda: len(b.data()) == len(games))
    chk("rc 0", lambda: b.rc == 0)
    b.close()


def t_flaky(src):
    print("── 失敗夾著成功，連續數要歸零")
    pages = ["LPL/2026 Season/ZZ F%d" % i for i in range(1, 7)]
    bad = pages[::2]                 # 第 1、3、5 頁例外，第 2、4、6 頁站有回應
    b = Box(src, {"ov": pages, "live": pages, "cargo_bad": pages, "api_fail": bad, "sched": {}},
            [rec(o, "2026-01-02", "A", "B", 1) for o in pages])
    b.run()
    chk("每頁都問到（失敗 3 頁×3 次＋3 頁×1 次＝12）", lambda: b.count("api.txt") == 12)
    chk("沒有熔斷", lambda: "這班不再上網" not in b.log)
    b.close()


def t_partial_down(src):
    print("── 部分頁 Cargo 正常、其餘 Cargo 與 api.php 都掛")
    bad = [FS] + EXTRA
    old = [rec(o, "2026-01-02", "A", "B", 1) for o in bad] + [rec(OK2, "2026-05-01", "T One", "T Two", 1, ss="r")]
    b = Box(src, {"ov": bad + [OK2], "live": bad, "cargo_bad": bad, "cargo": {OK2: [cargo_row(OK2, 1)]},
                  "api": "down", "sched": {}}, old)
    b.run()
    d = b.data()
    chk("rc 1（有資料寫出去，但這班有頁沒更新）", lambda: b.rc == 1)
    chk("正常的頁有更新", lambda: [r["ss"] for r in d if r["ov"] == OK2] == ["b"])
    chk("掛掉的頁沿用舊檔", lambda: all(any(r["ov"] == o for r in d) for o in bad))
    chk("熔斷訊息只印一次", lambda: b.log.count("這班不再上網") == 1)
    b.close()


def t_ov_fail(src):
    print("── 賽事頁清單抓不到")
    old = [rec(FS, "2026-01-02", "A", "B", 1)]
    for mode, why in (("html", "非 JSON"), ("exc", "例外")):
        b = Box(src, {"ov": mode}, old)
        h0 = b.md5()
        b.run()
        chk(why + "：rc 1", lambda: b.rc == 1)
        chk(why + "：舊檔沒動", lambda: b.md5() == h0)
        chk(why + "：日誌有 ⚠", lambda: "⚠" in b.log)
        b.close()


def t_normal(src):
    print("── 正常路徑不受影響")
    cargo = {FS: [cargo_row(FS, 1, ng=1)], OK2: [cargo_row(OK2, 1)]}
    old = [rec(FS, "2026-05-01", "T One", "T Two", 1, vod="https://old", ss="r"), rec(FS, "2026-05-01", "T One", "T Two", 2),
           rec(OK2, "2026-05-01", "T One", "T Two", 1, ss="r"), rec("Gone/Page", "2026-01-01", "A", "B", 1)]
    b = Box(src, {"ov": [FS, OK2], "cargo": cargo}, old)
    b.run()
    d = b.data()
    fs = [r for r in d if r["ov"] == FS]
    chk("rc 0", lambda: b.rc == 0)
    chk("Cargo 查到的頁以 Cargo 為準（舊值不留）", lambda: len(fs) == 1 and fs[0]["ss"] == "b" and fs[0]["vod"] == "")
    chk("這班沒產出的頁沿用", lambda: any(r["ov"] == "Gone/Page" for r in d))
    chk("沒走 api.php", lambda: b.count("api.txt") == 0)
    b.close()


def t_page(src):
    print("── --page 只動那一頁")
    old = [rec(FS, "2026-05-01", "A", "B", 1, ss="r"), rec(OK2, "2026-05-01", "C", "D", 1)]
    b = Box(src, {"ov": [], "cargo": {FS: [cargo_row(FS, 1)]}}, old)
    b.run("--page", FS)
    d = b.data()
    chk("別頁還在", lambda: any(r["ov"] == OK2 for r in d))
    chk("那一頁有更新", lambda: [r["ss"] for r in d if r["ov"] == FS] == ["b"])
    chk("rc 0", lambda: b.rc == 0)
    b.close()


def t_write_fail(src):
    print("── 寫檔失敗")
    old = [rec(FS, "2026-05-01", "A", "B", 1)]
    b = Box(src, {"ov": [FS], "cargo": {FS: [cargo_row(FS, 1)]}}, old)
    os.makedirs(b.out + ".tmp")     # tmp 開不起來
    h0 = b.md5()
    b.run()
    chk("rc 1", lambda: b.rc == 1)
    chk("舊檔完整", lambda: b.md5() == h0)
    b.close()


def t_lost(src):
    print("── Cargo 擋、HTML 也沒有、舊檔也沒有的新賽事")
    b2 = Box(src, {"ov": [FS, "LCK/2026 Season/ZZ New"], "live": [], "cargo_bad": ["ZZ New"],
                   "cargo": {FS: [cargo_row(FS, 1)]}, "sched": {}}, [rec(OK2, "2026-05-01", "C", "D", 1)])
    b2.run()
    chk("rc 1", lambda: b2.rc == 1)
    chk("日誌點名那一頁", lambda: "ZZ New" in b2.log and "舊檔也沒有" in b2.log)
    chk("其他資料照寫", lambda: any(r["ov"] == FS for r in b2.data()))
    b2.close()


def t_old_control():
    print("── 舊版對照（%s）" % OLDREV)
    src = subprocess.run(["git", "show", OLDREV + ":scripts/fetch_side_sel.py"], capture_output=True, cwd=ROOT).stdout.decode("utf-8")
    b, games, only_old = fallback_scene(src)
    b.run()
    fs = [r for r in b.data() if r["ov"] == FS]
    chk("舊版：快取沒有的局被蓋掉", lambda: not any(r["t1"] == "Old A" for r in fs))
    chk("舊版：bo 全變 0", lambda: all(r["bo"] == 0 for r in fs))
    b.close()
    pages = [FS] + EXTRA
    b = Box(src, {"ov": pages, "live": pages, "cargo_bad": pages, "api": "down", "sched": {}},
            [rec(o, "2026-01-02", "A", "B", 1) for o in pages])
    b.run()
    chk("舊版：api.php 掛掉打滿 %d 次" % (len(pages) * 3), lambda: b.count("api.txt") == len(pages) * 3)
    chk("舊版：rc 0 沒人出聲", lambda: b.rc == 0)
    b.close()
    b = Box(src, {"ov": "exc"}, [rec(FS, "2026-01-02", "A", "B", 1)])
    b.run()
    chk("舊版：清單抓不到 rc 0", lambda: b.rc == 0)
    b.close()
    b = Box(src, {"ov": [], "cargo": {FS: [cargo_row(FS, 1)]}}, [rec(FS, "2026-05-01", "A", "B", 1), rec(OK2, "2026-05-01", "C", "D", 1)])
    b.run("--page", FS)
    chk("舊版：--page 把別頁寫掉", lambda: not any(r["ov"] == OK2 for r in b.data()))
    b.close()


def main():
    before = (hashlib.md5(open(REAL_OUT, "rb").read()).hexdigest(), os.path.getmtime(REAL_OUT))
    src = io.open(SRC, encoding="utf-8", newline="").read()
    for t in (t_fallback, t_api_down, t_api_error_not_trip, t_refetch_ok, t_flaky, t_partial_down, t_ov_fail, t_normal, t_page, t_write_fail, t_lost):
        t(src)
    if not os.environ.get("SS_SRC"):
        t_old_control()
    print("── 隔離")
    chk("正本 side_sel.js 的 md5 與 mtime 沒動",
        lambda: before == (hashlib.md5(open(REAL_OUT, "rb").read()).hexdigest(), os.path.getmtime(REAL_OUT)))
    print("合計 %s：%d 條通過、%d 條失敗" % ("✓" if not BAD else "✗", len(OK), len(BAD)))
    for n in BAD:
        print("  ✗ " + n)
    sys.exit(1 if BAD else 0)


if __name__ == "__main__":
    main()
