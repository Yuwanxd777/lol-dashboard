# -*- coding: utf-8 -*-
"""fetch_skills 第二把鍵（CDragon build）的沙盒測試（2026-11-05 精進迴圈 #2614）。

案發：改版當天 CDragon 還沒跟上，建出上一版的數值；舊版 build 變了只重建缺值的英雄，
沒缺值但數值舊的卡到下次改版。26.22 上線兩天，瑟雷西 R 還是 250/400/550（實際 200/350/500），量到 11 位。

接管每一個入口與出口：CACHE／OUT_JS／ST_F 在暫存資料夾、get_json／urlopen／build_champ 換成假的；
真實 repo 的 skills.js 與快取跑完比 md5 與 mtime。斷言寫成 lambda，例外算這一條 ✗。
舊版對照釘 OLDREV（引入這輪改動之前的 commit）：同一份情境舊版要真的卡在舊值。
"""
import hashlib, importlib.util, io, json, os, subprocess, sys, tempfile, urllib.error
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
REPO = Path(__file__).resolve().parent.parent
OLDREV = "50b2e885"
sys.stdout = io.TextIOWrapper(open(sys.stdout.fileno(), "wb", closefd=False), encoding="utf-8", errors="replace", line_buffering=True)


def load(src_path, name):
    spec = importlib.util.spec_from_file_location(name, src_path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def entry(tag, gaps=0):
    return {"n": tag, "t": "", "p": {"n": "", "d": ""},
            "s": [{"k": "Q", "d": tag}] + [{"k": "W", "d": "x", "fb": 1}] * gaps}


class Sandbox:
    """cache：快取初值；build：cid → 條目或例外；mark：items_cache_cdver.txt 內容；cdver：None＝查詢失敗"""
    def __init__(self, fs, tmp, cache, build, cdver="C2", mark="C2", st_file='{"entries":{"a":"b"}}', st_net=None):
        self.fs, self.tmp = fs, tmp
        self.calls, self.net = [], []
        fs.CACHE, fs.OUT_JS, fs.ST_F = tmp / "cache.json", tmp / "skills.js", tmp / "st.json"
        for name in ("CACHE", "OUT_JS", "ST_F"):
            assert REPO not in getattr(fs, name).resolve().parents, f"{name} 還指著真實 repo"
        if st_file is not None:
            fs.ST_F.write_text(st_file, encoding="utf-8")
        if mark is not None:
            (tmp / "items_cache_cdver.txt").write_text(mark, encoding="utf-8")
        fs.CACHE.write_text(json.dumps(cache), encoding="utf-8")

        def fake_get_json(url, timeout=30):
            if url.endswith("versions.json"):
                return ["V"]
            if url.endswith("champion.json"):
                return {"data": {k: {} for k in build}}
            if url.endswith("content-metadata.json"):
                if cdver is None:
                    raise urllib.error.URLError("down")
                return {"version": cdver}
            raise AssertionError(f"沙盒漏接的網址：{url}")

        self.st_seen = []

        def fake_build(cid, ddv, st=None):
            self.calls.append(cid)
            self.st_seen.append(st)
            r = build[cid]
            if isinstance(r, Exception):
                raise r
            return r

        class Resp:
            def __init__(s, b): s.b = b
            def read(s): return s.b
            def __enter__(s): return s
            def __exit__(s, *a): return False

        def fake_urlopen(req, timeout=None):
            self.net.append(getattr(req, "full_url", str(req)))
            if st_net is None:
                raise urllib.error.URLError("st down")
            return Resp(st_net.encode("utf-8"))

        fs.get_json, fs.build_champ = fake_get_json, fake_build
        fs.urllib.request.urlopen = fake_urlopen
        fs.time.sleep = lambda *_: None
        fs.FORCE, fs.SINGLE = False, None
        fs.SKILL_WORKERS = 1   # 測試要固定順序（熔斷的連續次數）

    def run(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.fs.main()
        js = self.fs.OUT_JS.read_text(encoding="utf-8")
        self.out = json.loads(js[js.index("=") + 1:].rstrip(";"))
        self.cache = json.loads(self.fs.CACHE.read_text(encoding="utf-8"))
        self.log = buf.getvalue()
        return self


bad = passed = 0


def check(fn, msg):
    global bad, passed
    try:
        ok = fn()
    except Exception as e:
        ok, msg = False, f"{msg}（例外 {type(e).__name__}: {e}）"
    print(("✓ " if ok else "✗ ") + msg)
    passed += bool(ok)
    bad += not ok


def fp(p):
    return (hashlib.md5(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns) if p.exists() else None


REAL = [REPO / "skills.js", REPO / "csv_cache/skills_cache.json", REPO / "csv_cache/items_st_zhtw.json", REPO / "csv_cache/items_cache_cdver.txt"]
before = [fp(p) for p in REAL]
real_urlopen = None


def fresh():
    return load(REPO / "scripts/fetch_skills.py", "fs_new")


def base_cache(**kw):
    c = {"ver": "V", "cdver": "C1", "champs": {"A": entry("A-舊"), "B": entry("B-舊")},
         "cdv_of": {"A": "C1", "B": "C1"}}
    c.update(kw)
    return c


# 1. 核心：build 變了，沒缺值的英雄也要換成新值（案發情境）
with tempfile.TemporaryDirectory() as td:
    s = Sandbox(fresh(), Path(td), base_cache(), {"A": entry("A-新"), "B": entry("B-新")}).run()
    check(lambda: s.out["d"]["A"]["s"][0]["d"] == "A-新", "build 變 ⇒ 沒缺值的 A 也換成新值")
    check(lambda: s.out["d"]["B"]["s"][0]["d"] == "B-新", "build 變 ⇒ B 也換成新值")
    check(lambda: s.cache["cdv_of"] == {"A": "C2", "B": "C2"}, "cdv_of 記到新 build")
    check(lambda: s.cache["cdver"] == "C2", "cdver 前進")
    check(lambda: s.out["v"] == "V", "v 不變")
    check(lambda: "重建 2 位" in s.log, "日誌印重建位數")

# 2. 舊快取沒有 cdv_of（上線第一班）⇒ 全部重建
with tempfile.TemporaryDirectory() as td:
    c = base_cache(cdver="C2")
    del c["cdv_of"]
    s = Sandbox(fresh(), Path(td), c, {"A": entry("A-新"), "B": entry("B-新")}).run()
    check(lambda: sorted(s.calls) == ["A", "B"], "沒有 cdv_of 的舊快取 ⇒ 全部重建一次")

# 3. build 沒變 ⇒ 不重建（一般班次不上網）
with tempfile.TemporaryDirectory() as td:
    s = Sandbox(fresh(), Path(td), base_cache(cdver="C2", cdv_of={"A": "C2", "B": "C2"}),
                {"A": entry("A-新"), "B": entry("B-新")}).run()
    check(lambda: s.calls == [], "build 沒變 ⇒ 0 位重建（正例：上一條同情境會重建）")
    check(lambda: s.out["d"]["A"]["s"][0]["d"] == "A-舊", "build 沒變 ⇒ 內容不動")
    check(lambda: s.net == [], "build 沒變 ⇒ 字串表不上網")
    check(lambda: "重建" not in s.log, "build 沒變 ⇒ 日誌不印重建")

with tempfile.TemporaryDirectory() as td:   # mark 落後時 load_st 會上網：沒人要重建就不該叫到它
    s = Sandbox(fresh(), Path(td), base_cache(cdver="C2", cdv_of={"A": "C2", "B": "C2"}),
                {"A": entry("A-新"), "B": entry("B-新")}, mark="C1", st_net='{"entries":{"new":"x"}}').run()
    check(lambda: s.net == [], "沒人要重建 ⇒ 字串表不載入（mark 落後也不上網）")

# 4. 查不到 build ⇒ 不重建已有條目，缺的照建
with tempfile.TemporaryDirectory() as td:
    c = base_cache()
    del c["champs"]["B"]
    s = Sandbox(fresh(), Path(td), c, {"A": entry("A-新"), "B": entry("B-新")}, cdver=None).run()
    check(lambda: s.calls == ["B"], "build 查不到 ⇒ 只建缺的 B")
    check(lambda: s.out["d"]["A"]["s"][0]["d"] == "A-舊", "build 查不到 ⇒ A 不動")
    check(lambda: "B" not in s.cache["cdv_of"] or s.cache["cdv_of"]["B"] != "", "build 查不到 ⇒ 不記空字串 build")
    check(lambda: s.cache["cdver"] == "C1", "build 查不到 ⇒ cdver 不前進")

# 5. 中途失敗：失敗的留同版舊條目（不是上一版）、不記 build，下一班只補它
with tempfile.TemporaryDirectory() as td:
    c = base_cache(prev={"ver": "OLD", "champs": {"B": entry("B-上一版")}})
    fs = fresh()
    s = Sandbox(fs, Path(td), c, {"A": entry("A-新"), "B": fs.Transient("522")}).run()
    check(lambda: s.out["d"]["B"]["s"][0]["d"] == "B-舊", "暫時失敗 ⇒ B 留這版舊條目")
    check(lambda: s.out["v"] == "V", "暫時失敗 ⇒ v 不退回上一版")
    check(lambda: s.cache["cdv_of"]["A"] == "C2" and s.cache["cdv_of"]["B"] == "C1", "只有成功的前進 build")
    check(lambda: "沿用這版舊條目" in s.log and "重建沒完成" in s.log, "日誌講清楚沒完成")
    check(lambda: "B" in s.cache["champs"], "快取保留 B")
    # 下一班：只補 B
    s2 = Sandbox(fresh(), Path(td), s.cache, {"A": entry("A-再新"), "B": entry("B-新")}, st_file=None, mark=None)
    s2.fs.ST_F.write_text('{"entries":{"a":"b"}}', encoding="utf-8")
    (Path(td) / "items_cache_cdver.txt").write_text("C2", encoding="utf-8")
    s2.run()
    check(lambda: s2.calls == ["B"], "下一班只補沒建成的 B（A 不重抓）")
    check(lambda: s2.out["d"]["B"]["s"][0]["d"] == "B-新", "下一班 B 換新")

# 6. 這版沒建過的英雄失敗 ⇒ 既有「沿用上一版」路徑不變
with tempfile.TemporaryDirectory() as td:
    c = {"ver": "V", "cdver": "C2", "cdv_of": {}, "champs": {}, "prev": {"ver": "OLD", "champs": {"B": entry("B-上一版")}}}
    fs = fresh()
    s = Sandbox(fs, Path(td), c, {"B": fs.Transient("522")}).run()
    check(lambda: s.out["d"]["B"]["s"][0]["d"] == "B-上一版" and s.out["v"] == "OLD", "這版沒有 ⇒ 沿用上一版、v 留上一版")

# 7. 缺值變多 ⇒ 留舊、不記 build；一樣多 ⇒ 換；變少 ⇒ 換
with tempfile.TemporaryDirectory() as td:
    c = base_cache()
    c["champs"]["B"] = entry("B-舊缺", gaps=1)
    s = Sandbox(fresh(), Path(td), c, {"A": entry("A-壞", gaps=2), "B": entry("B-新")}).run()
    check(lambda: s.out["d"]["A"]["s"][0]["d"] == "A-舊", "缺值變多（bin 404）⇒ 留舊")
    check(lambda: s.cache["cdv_of"]["A"] == "C1", "缺值變多 ⇒ 不記 build，下一班再試")
    check(lambda: s.out["d"]["B"]["s"][0]["d"] == "B-新", "缺值變少 ⇒ 換新（缺值補回的 #2614 前行為保留）")
    check(lambda: "留舊條目" in s.log, "日誌印留舊條目")
with tempfile.TemporaryDirectory() as td:
    c = base_cache()
    c["champs"]["A"] = entry("A-舊缺", gaps=1)
    s = Sandbox(fresh(), Path(td), c, {"A": entry("A-新缺", gaps=1), "B": entry("B-新")}).run()
    check(lambda: s.out["d"]["A"]["s"][0]["d"] == "A-新缺", "缺值一樣多 ⇒ 換新")

# 8. --force 不受缺值保護
with tempfile.TemporaryDirectory() as td:
    fs = fresh()
    sb = Sandbox(fs, Path(td), base_cache(), {"A": entry("A-壞", gaps=2), "B": entry("B-新")})
    fs.FORCE = True
    sb.run()
    check(lambda: sb.out["d"]["A"]["s"][0]["d"] == "A-壞", "--force 照換")

# 9. 熔斷：連續暫時失敗到門檻就不再上網；成功會歸零
ids = [f"C{i:03d}" for i in range(60)]
with tempfile.TemporaryDirectory() as td:
    fs = fresh()
    c = {"ver": "V", "cdver": "C1", "champs": {k: entry(k + "-舊") for k in ids}, "cdv_of": {k: "C1" for k in ids}}
    s = Sandbox(fs, Path(td), c, {k: fs.Transient("522") for k in ids}).run()
    check(lambda: len(s.calls) == fs.BREAK_AFTER, f"全掛 ⇒ 只打 {fs.BREAK_AFTER} 位（實際 {len(s.calls)}）")
    check(lambda: "不再上網" in s.log and f"{60 - fs.BREAK_AFTER} 位這班沒試" in s.log, "日誌印熔斷與沒試的位數")
    check(lambda: all(s.out["d"][k]["s"][0]["d"] == k + "-舊" for k in ids), "熔斷 ⇒ 60 位都留舊條目")
    check(lambda: all(v == "C1" for v in s.cache["cdv_of"].values()), "熔斷 ⇒ 沒有人前進 build")
    check(lambda: s.log.count("✗") == fs.BREAK_AFTER, "沒試的不逐行印 ✗")
with tempfile.TemporaryDirectory() as td:
    fs = fresh()
    c = {"ver": "V", "cdver": "C1", "champs": {k: entry(k + "-舊") for k in ids}, "cdv_of": {k: "C1" for k in ids}}
    bd = {k: (entry(k + "-新") if i % 10 == 9 else fs.Transient("522")) for i, k in enumerate(ids)}
    s = Sandbox(fs, Path(td), c, bd).run()
    check(lambda: len(s.calls) == 60, "中間有成功 ⇒ 連續數歸零、不熔斷（正控制）")
with tempfile.TemporaryDirectory() as td:
    fs = fresh()
    c = {"ver": "V", "cdver": "C1", "champs": {k: entry(k + "-舊") for k in ids}, "cdv_of": {k: "C1" for k in ids}}
    s = Sandbox(fs, Path(td), c, {k: ValueError("壞 JSON") for k in ids}).run()
    check(lambda: len(s.calls) == 60, "非暫時性失敗不熔斷（內容壞不是連線問題）")
    check(lambda: "2" not in [] and all(s.out["d"][k]["s"][0]["d"] == k + "-舊" for k in ids), "非暫時性失敗也留舊條目")

# 10. 字串表：快取和 build 對得上就不上網；比 build 舊就抓新的、不寫檔；抓不到退回快取
with tempfile.TemporaryDirectory() as td:
    s = Sandbox(fresh(), Path(td), base_cache(), {"A": entry("A-新"), "B": entry("B-新")}, mark="C2").run()
    check(lambda: s.net == [] and s.st_seen[0] == {"a": "b"}, "mark＝build ⇒ 用快取檔、不上網")
with tempfile.TemporaryDirectory() as td:
    s = Sandbox(fresh(), Path(td), base_cache(), {"A": entry("A-新"), "B": entry("B-新")}, mark="C1",
                st_net='{"entries":{"new":"zzprobe9942"}}').run()
    check(lambda: len(s.net) == 1 and s.st_seen[0] == {"new": "zzprobe9942"}, "mark 比 build 舊 ⇒ 抓新字串表來用")
    check(lambda: json.loads(s.fs.ST_F.read_text(encoding="utf-8"))["entries"] == {"a": "b"}, "快取檔歸 fetch_items，這邊不寫")
    check(lambda: (Path(td) / "items_cache_cdver.txt").read_text(encoding="utf-8") == "C1", "mark 不動")
with tempfile.TemporaryDirectory() as td:
    s = Sandbox(fresh(), Path(td), base_cache(), {"A": entry("A-新"), "B": entry("B-新")}, mark="C1").run()
    check(lambda: s.st_seen[0] == {"a": "b"} and "字串表抓不到" in s.log, "字串表抓不到 ⇒ 退回快取檔並印出來")
with tempfile.TemporaryDirectory() as td:
    c = base_cache()
    del c["champs"]["B"]
    s = Sandbox(fresh(), Path(td), c, {"A": entry("A-新"), "B": entry("B-新")}, mark=None, st_file=None).run()
    check(lambda: s.calls == ["B"], "完全沒有字串表 ⇒ 不重建已有的，只建缺的")
    check(lambda: s.cache["cdv_of"]["A"] == "C1", "沒有字串表 ⇒ A 不前進 build")
    check(lambda: not s.fs.ST_F.exists(), "抓不到就不留空的字串表檔")
with tempfile.TemporaryDirectory() as td:
    s = Sandbox(fresh(), Path(td), base_cache(), {"A": entry("A-新"), "B": entry("B-新")}, mark=None, st_file=None,
                st_net='{"entries":{"new":"zzprobe9942"}}').run()
    check(lambda: s.fs.ST_F.exists(), "字串表檔不存在時抓到要留一份")
    check(lambda: not list(Path(td).glob("*.tmp*")), "沒留下暫存檔")

# 11. 換版（ddv 變）：cdv_of 清空、整份重建、上一版進 prev
with tempfile.TemporaryDirectory() as td:
    c = {"ver": "OLD", "cdver": "C2", "champs": {"A": entry("A-上一版")}, "cdv_of": {"A": "C2"}}
    s = Sandbox(fresh(), Path(td), c, {"A": entry("A-新")}).run()
    check(lambda: s.calls == ["A"] and s.out["v"] == "V", "換版 ⇒ 重建")
    check(lambda: s.cache["cdv_of"] == {"A": "C2"} and s.cache["prev"]["ver"] == "OLD", "換版 ⇒ prev 收上一版")

# 12. 寫檔中途壞掉不留半個檔
with tempfile.TemporaryDirectory() as td:
    fs = fresh()
    sb = Sandbox(fs, Path(td), base_cache(cdver="C2", cdv_of={"A": "C2", "B": "C2"}), {"A": entry("A"), "B": entry("B")})
    fs.OUT_JS.write_text("原本的內容", encoding="utf-8")
    real_replace = fs.os.replace

    def boom(a, b):
        raise OSError("disk")
    fs.os.replace = boom
    try:
        try:
            sb.run()
        except OSError:
            pass
    finally:
        fs.os.replace = real_replace
    check(lambda: fs.OUT_JS.read_text(encoding="utf-8") == "原本的內容", "換名失敗 ⇒ 舊 skills.js 完好")

# 舊版對照：拉 OLDREV 的 fetch_skills.py，跑同一個情境，要真的卡在舊值
src = subprocess.run(["git", "show", f"{OLDREV}:scripts/fetch_skills.py"], cwd=REPO, capture_output=True).stdout
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "old_fs.py"
    p.write_bytes(src)
    (Path(td) / "w").mkdir()
    old = load(p, "fs_old")
    s = Sandbox(old, Path(td) / "w", base_cache(), {"A": entry("A-新"), "B": entry("B-新")}).run()
    check(lambda: s.out["d"]["A"]["s"][0]["d"] == "A-舊", f"舊版對照（{OLDREV}）：build 變了 A 還是舊值")
    check(lambda: s.calls == [], "舊版對照：沒缺值的一位都不重建")

after = [fp(p) for p in REAL]
check(lambda: after == before, "正本 skills.js／快取／字串表／mark 的 md5 與 mtime 沒動")
print(f"合計 ✓ {passed} ✗ {bad}")
sys.exit(1 if bad else 0)
