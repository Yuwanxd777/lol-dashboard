# -*- coding: utf-8 -*-
"""fetch_items 的 CDragon build 第二把鍵＋fetch_item_nostore 的空表守門（2026-11-05 精進迴圈 #2613）。

背景：items.js 的快取鍵只有 DDragon 版本。DDragon 換版那班建的那份會卡到下次改版，
16.22 上線兩天狂霸血甲還是 12%，DDragon 與 CDragon 都已是 10%。

做法：把腳本複製到沙盒的 scripts/ 用子程序 runpy 跑 __main__，路徑全由 __file__ 推出來，離開碼也測得到；
只接管 urlopen。素材是真實快取 csv_cache/items_bin.json 與 items_st_zhtw.json 的條目。
舊版對照釘 OLDREV（引入這輪改動之前的 commit）。
"""
import hashlib, io, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SRC = Path(os.environ.get("M_SRC") or HERE)   # 突變測試用：被測腳本從這裡拿
OLDREV = "b0703311"
ok = bad = 0


def check(name, fn):
    global ok, bad
    try:
        r = fn()
    except Exception as e:
        r = False
        name += f"（{type(e).__name__}: {e}）"
    if r:
        ok += 1
    else:
        bad += 1
        print("   ✗", name)


RUNNER = r'''
import io, json, os, runpy, sys, urllib.error, urllib.request
sc = json.load(open(sys.argv[1], encoding="utf-8"))
script = sys.argv[2]
calls = []
class R(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False
def urlopen(req, timeout=None):
    u = getattr(req, "full_url", req)
    calls.append(u)
    json.dump(calls, open(sc["calls"], "w"))
    for kw, v in sc["routes"]:
        if kw in u:
            if isinstance(v, int):
                raise urllib.error.HTTPError(u, v, "x", {}, None)
            if v is None:
                raise urllib.error.URLError("down")
            return R(v.encode("utf-8"))
    raise urllib.error.HTTPError(u, 404, "x", {}, None)
urllib.request.urlopen = urlopen
sys.path.insert(0, os.path.dirname(script))
sys.argv = [script] + sys.argv[3:]
json.dump(calls, open(sc["calls"], "w"))
runpy.run_path(script, run_name="__main__")
'''

# ── 真實素材 ─────────────────────────────────────────
REAL_BIN = json.loads((REPO / "csv_cache" / "items_bin.json").read_text(encoding="utf-8"))
REAL_ST = json.loads((REPO / "csv_cache" / "items_st_zhtw.json").read_text(encoding="utf-8"))["entries"]
BLOOD = "2501"
assert f"Items/{BLOOD}" in REAL_BIN and f"item_{BLOOD}_tooltip" in REAL_ST, "素材不見了"


def bin_with(val):
    e = json.loads(json.dumps(REAL_BIN[f"Items/{BLOOD}"]))
    hit = 0
    for d in e["mDataValues"]:
        if d["mName"] == "MissingHealthAD":
            d["mValue"] = val
            hit += 1
    assert hit == 1
    return e


def routes(bin_, st=None, dd=None, ddv="16.22.1", cdver="B2"):
    st = st if st is not None else {"entries": {f"item_{BLOOD}_tooltip": REAL_ST[f"item_{BLOOD}_tooltip"]}}
    dd = dd if dd is not None else {"data": {BLOOD: {"name": "狂霸血甲", "description": "<stats>40 物理攻擊</stats>"}}}
    return [
        ["api/versions.json", json.dumps([ddv])],
        ["content-metadata.json", cdver if isinstance(cdver, int) or cdver is None else json.dumps({"version": cdver})],
        ["items.cdtb.bin.json", bin_ if isinstance(bin_, int) or bin_ is None else json.dumps(bin_)],
        ["lol.stringtable.json", json.dumps(st)],
        ["/data/zh_TW/item.json", json.dumps(dd)],
    ]


class Box:
    def __init__(self, src=None):
        self.d = Path(tempfile.mkdtemp(prefix="m2613_"))
        (self.d / "scripts").mkdir()
        (self.d / "csv_cache").mkdir()
        for n in ("fetch_items.py", "fetch_skills.py"):
            shutil.copy(SRC / n, self.d / "scripts" / n)
        if src:
            (self.d / "scripts" / "fetch_items.py").write_bytes(src)
        (self.d / "runner.py").write_text(RUNNER, encoding="utf-8")
        self.js = self.d / "items.js"
        self.mark = self.d / "csv_cache" / "items_cache_ver.txt"
        self.cdm = self.d / "csv_cache" / "items_cache_cdver.txt"

    def run(self, rts, script="fetch_items.py", args=()):
        sc = self.d / "sc.json"
        cf = self.d / "calls.json"
        sc.write_text(json.dumps({"routes": rts, "calls": str(cf)}), encoding="utf-8")
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        r = subprocess.run([sys.executable, str(self.d / "runner.py"), str(sc), str(self.d / "scripts" / script), *args],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(self.d))
        self.rc, self.out = r.returncode, r.stdout + r.stderr
        self.calls = json.loads(cf.read_text()) if cf.exists() else []
        return self

    def dl(self):
        return [c for c in self.calls if "items.cdtb.bin" in c or "stringtable" in c]

    def text(self):
        return self.js.read_text(encoding="utf-8")

    def tmp_left(self):
        return [p.name for p in self.d.rglob("*.tmp")]


def desc(box):
    js = box.text()
    return json.loads(js[js.index("=") + 1:js.index(";window.ITEM_XTRA=")])


def seed(box, val=0.12, cdver="B1"):
    """先建一份上一班的成品"""
    box.run(routes(bin_with_map(val), cdver=cdver))
    assert box.rc == 0 and box.js.exists(), box.out[-400:]


def bin_with_map(val):
    return {f"Items/{BLOOD}": bin_with(val)}


snap_files = [REPO / "items.js", REPO / "item_nostore.js", REPO / "csv_cache" / "items_cache_ver.txt",
              REPO / "csv_cache" / "items_bin.json", REPO / "csv_cache" / "items_st_zhtw.json"]


def snap():
    return {str(p): (hashlib.md5(p.read_bytes()).hexdigest(), p.stat().st_mtime) for p in snap_files if p.exists()}


cdm_real = REPO / "csv_cache" / "items_cache_cdver.txt"
before = snap()
cdm_before = cdm_real.exists()

# ① 真實素材算得出數字（正控制：後面的 12→10 才有意義）
b = Box()
seed(b)
check("①真實模板填得出 12%", lambda: "最多12%" in desc(b)["狂霸血甲"].replace(" ", ""))
check("①cdver 記下來", lambda: b.cdm.read_text() == "B1")
check("①mark 記下來", lambda: b.mark.read_text() == "16.22.1")
check("①沒留 tmp", lambda: b.tmp_left() == [])

# ② 兩把鍵都沒變 ⇒ 跳過、不下載、一個位元不動
raw = b.text()
b.run(routes(bin_with_map(0.10), cdver="B1"))
check("②同 build 跳過 rc 0", lambda: b.rc == 0 and "跳過" in b.out)
check("②不下載 bin", lambda: b.dl() == [])
check("②檔案沒動", lambda: b.text() == raw)

# ③ 主角：同一版 DDragon、CDragon build 變、值變 ⇒ 換成 10%
b.run(routes(bin_with_map(0.10), cdver="B2"))
check("③rc 0", lambda: b.rc == 0)
check("③有重新下載", lambda: len(b.dl()) == 2)
check("③變成 10%", lambda: "最多10%" in desc(b)["狂霸血甲"].replace(" ", ""))
check("③cdver 前進", lambda: b.cdm.read_text() == "B2")
check("③版本戳仍是這版 DDragon", lambda: 'ITEM_DESC_VER="16.22.1-' in b.text())
check("③日誌指名變動的道具", lambda: "1 件內容變了：狂霸血甲" in b.out)

# ④ build 變、內容沒變 ⇒ 不換版本戳（前端快取不白白失效），但記住 build
raw = b.text()
b.run(routes(bin_with_map(0.10), cdver="B3"))
check("④內容沒變不重寫", lambda: b.rc == 0 and b.text() == raw and "內容沒變" in b.out)
check("④cdver 前進，下一班不再下載", lambda: b.cdm.read_text() == "B3")
b.run(routes(bin_with_map(0.10), cdver="B3"))
check("④下一班跳過", lambda: b.dl() == [] and "跳過" in b.out)

# ⑤ 查 build 失敗 ⇒ 這班只看 DDragon，不下載、不報錯、mark 不變
b.run(routes(bin_with_map(0.22), cdver=503))
check("⑤查不到 build 跳過 rc 0", lambda: b.rc == 0 and b.dl() == [] and "CDragon 版本查詢失敗" in b.out)
check("⑤cdver 沒被清掉", lambda: b.cdm.read_text() == "B3")

# ⑥ build 變但 bin 抓不到 ⇒ 留舊檔、cdver 不前進（下一班還會試）、rc 0
raw = b.text()
b.run(routes(503, cdver="B4"))
check("⑥暫時掛 rc 0", lambda: b.rc == 0 and "來源暫時抓不到" in b.out)
check("⑥舊檔沒動", lambda: b.text() == raw)
check("⑥cdver 沒前進", lambda: b.cdm.read_text() == "B3")
b.run(routes(bin_with_map(0.15), cdver="B4"))
check("⑥下一班補上", lambda: b.rc == 0 and "最多15%" in desc(b)["狂霸血甲"].replace(" ", "") and b.cdm.read_text() == "B4")

# ⑦ 改版當天 CDragon 還沒跟上：DDragon 先換版、build 沒變 ⇒ 仍要建；之後 build 變再建一次（舊版就卡在這）
b2 = Box()
seed(b2, 0.12, "B1")
b2.run(routes(bin_with_map(0.12), ddv="16.23.1", cdver="B1"))
check("⑦DDragon 換版照建", lambda: b2.rc == 0 and 'ITEM_DESC_VER="16.23.1-' in b2.text())
b2.run(routes(bin_with_map(0.20), ddv="16.23.1", cdver="B9"))
check("⑦CDragon 跟上後再建", lambda: "最多20%" in desc(b2)["狂霸血甲"].replace(" ", ""))

# ⑧ 第一次跑新版（沒有 cdver 檔）⇒ 重建一次，這就是 22:00 班把線上 12% 修掉的路徑
b3 = Box()
seed(b3, 0.12, "B1")
b3.cdm.unlink(missing_ok=True)
b3.run(routes(bin_with_map(0.10), cdver="B1"))
check("⑧沒 cdver 檔會重建", lambda: "最多10%" in desc(b3)["狂霸血甲"].replace(" ", ""))

# ⑨ 值查不到：這件留上一版數字、其他道具照更新。素材是真實的傲慢模板（16.21 最終 bin 真的出過這種句子）
IID = "6697"
assert "@ADPerStatue@" in REAL_ST[f"item_{IID}_tooltip"], "素材變了"
ST2 = {"entries": {f"item_{BLOOD}_tooltip": REAL_ST[f"item_{BLOOD}_tooltip"], f"item_{IID}_tooltip": REAL_ST[f"item_{IID}_tooltip"]}}
DD2 = {"data": {BLOOD: {"name": "狂霸血甲", "description": ""}, IID: {"name": "測試道具", "description": ""}}}
e_good = json.loads(json.dumps(REAL_BIN[f"Items/{IID}"]))
e_good["mDataValues"] += [{"mName": "BaseADBonus", "mValue": 12.0}, {"mName": "ADPerStatue", "mValue": 3.0}]
good = {f"Items/{BLOOD}": bin_with(0.12), f"Items/{IID}": e_good}
b4 = Box()
b4.run(routes(good, st=ST2, dd=DD2, cdver="B1"))
first = desc(b4)["測試道具"]
gone = {f"Items/{BLOOD}": bin_with(0.10), f"Items/{IID}": REAL_BIN[f"Items/{IID}"]}  # 真實 bin 就是查不到這兩個值
b4.run(routes(gone, st=ST2, dd=DD2, cdver="B2"))
check("⑨值查不到留上一版", lambda: desc(b4)["測試道具"] == first and "沿用上一版文字：測試道具" in b4.out)
check("⑨其他道具照更新", lambda: "最多10%" in desc(b4)["狂霸血甲"].replace(" ", ""))
check("⑨正控制：上一版有 12", lambda: "12物理攻擊" in re.sub(r"<[^>]+>", "", first))

# ⑨b 沒有查不到的值、只是文案變短 ⇒ 照收，不可以被當成缺值
b7 = Box()
st7a = {"entries": {f"item_{BLOOD}_tooltip": "效果 10 與 20"}}
st7b = {"entries": {f"item_{BLOOD}_tooltip": "效果 10"}}
b7.run(routes(bin_with_map(0.1), st=st7a, cdver="B1"))
b7.run(routes(bin_with_map(0.1), st=st7b, cdver="B2"))
check("⑨b文案變短照收", lambda: "與" not in desc(b7)["狂霸血甲"] and "沿用上一版" not in b7.out)

# ⑩ 解析結果砍太多 ⇒ 不寫、mark 不前進、rc 1
b5 = Box()
many = {str(1000 + i): {"name": f"道{i}", "description": ""} for i in range(20)}
st20 = {"entries": {f"item_{i}_tooltip": f"效果 {i}" for i in many}}
bin20 = {f"Items/{i}": {"mDataValues": []} for i in many}
b5.run(routes(bin20, st=st20, dd={"data": many}, cdver="B1"))
raw = b5.text()
check("⑩正控制：先建出 20 件", lambda: len(desc(b5)) == 20)
b5.run(routes({"Items/1000": {"mDataValues": []}}, st=st20, dd={"data": many}, cdver="B2"))
check("⑩砍到 1 件 rc 1", lambda: b5.rc == 1 and "保留舊的 items.js" in b5.out)
check("⑩舊檔沒動", lambda: b5.text() == raw)
check("⑩cdver 沒前進", lambda: b5.cdm.read_text() == "B1")
b5.run(routes(bin20, st={"entries": {}}, dd={"data": many}, cdver="B2"))
check("⑩0 件 rc 1", lambda: b5.rc == 1 and b5.text() == raw)
b8 = Box()
b8.run(routes(bin20, st={"entries": {}}, dd={"data": many}, cdver="B1"))
check("⑩沒舊檔又 0 件 rc 1、不寫檔", lambda: b8.rc == 1 and not b8.js.exists() and not b8.mark.exists())
keep19 = dict(list(bin20.items())[:19])
b5.run(routes(keep19, st=st20, dd={"data": many}, cdver="B3"))
check("⑩少 1 件（95%）照收", lambda: b5.rc == 0 and len(desc(b5)) == 19)

# ⑪ 舊版對照：同一份情境，舊版跳過、留 12%（這輪要修的就是這個）
oldsrc = subprocess.run(["git", "show", f"{OLDREV}:scripts/fetch_items.py"], cwd=REPO, capture_output=True).stdout
assert oldsrc and b"URL_CDVER" not in oldsrc, "OLDREV 釘錯了"
b6 = Box(oldsrc)
b6.run(routes(bin_with_map(0.12), cdver="B1"))
b6.run(routes(bin_with_map(0.10), cdver="B2"))
check("⑪舊版真的卡 12%", lambda: "最多12%" in desc(b6)["狂霸血甲"].replace(" ", "") and b6.dl() == [])
b6.run(routes(bin_with_map(0.10), st={"entries": {}}, ddv="16.23.1", cdver="B2"))
check("⑪舊版 0 件照寫", lambda: b6.rc == 0 and desc(b6) == {})

# ── fetch_item_nostore ───────────────────────────────
NS_OLD = subprocess.run(["git", "show", f"{OLDREV}:scripts/fetch_item_nostore.py"], cwd=REPO, capture_output=True).stdout
assert NS_OLD and b"MIN_KEEP" not in NS_OLD


def ns_box(src=None):
    x = Box()
    p = x.d / "scripts" / "fetch_item_nostore.py"
    if src:
        p.write_bytes(src)
    else:
        shutil.copy(SRC / "fetch_item_nostore.py", p)
    return x


def ns_routes(off, total=10):
    dd = {"data": {str(1000 + i): {"name": f"道{i}"} for i in range(total)}}
    cd = [{"id": 1000 + i, "inStore": False if i < off else True} for i in range(total)]
    return [["api/versions.json", json.dumps(["16.22.1"])], ["item.json", json.dumps(dd)], ["items.json", json.dumps(cd)]]


def ns_read(x):
    s = (x.d / "item_nostore.js").read_text(encoding="utf-8")
    return json.loads(s[s.index("=") + 1:].strip().rstrip(";"))


n = ns_box()
n.run(ns_routes(8), "fetch_item_nostore.py")
check("⑫正常寫出 8 個", lambda: n.rc == 0 and len(ns_read(n)) == 8)
n.run(ns_routes(0), "fetch_item_nostore.py")
check("⑫來源 0 個 rc 1 留舊檔", lambda: n.rc == 1 and len(ns_read(n)) == 8 and "保留舊的" in n.out)
n.run(ns_routes(3), "fetch_item_nostore.py")
check("⑫掉到一半以下 rc 1", lambda: n.rc == 1 and len(ns_read(n)) == 8)
n.run(ns_routes(4), "fetch_item_nostore.py")
check("⑫剛好一半照收", lambda: n.rc == 0 and len(ns_read(n)) == 4)
n.run(ns_routes(9), "fetch_item_nostore.py")
check("⑫變多照收", lambda: n.rc == 0 and len(ns_read(n)) == 9 and n.tmp_left() == [])
n0 = ns_box()
n0.run(ns_routes(0), "fetch_item_nostore.py")
check("⑫沒舊檔又 0 個 rc 1、不寫空表", lambda: n0.rc == 1 and not (n0.d / "item_nostore.js").exists())
n1 = ns_box(NS_OLD)
n1.run(ns_routes(8), "fetch_item_nostore.py")
n1.run(ns_routes(0), "fetch_item_nostore.py")
check("⑫舊版對照：0 個照寫成空表、rc 0", lambda: n1.rc == 0 and ns_read(n1) == {})

check("⑬正本一個位元沒動", lambda: snap() == before)
check("⑬正本沒多 cdver 檔", lambda: cdm_real.exists() == cdm_before)
print(f"合計 ✓ {ok} ✗ {bad}")
sys.exit(1 if bad else 0)
