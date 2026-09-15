# -*- coding: utf-8 -*-
"""fetch_side_sel 主路徑換 Cargo（2026-09-15 線 3 #118）的沙盒測試。

被測的改動：主路徑從「46 頁 HTML 逐頁解析＋三輪隊名配對」換成 Special:CargoExport 的
`MatchScheduleGame ⋈ MatchSchedule`（8 頁一批、撞上限切半、單頁失敗再試一次、仍失敗走 HTML 備援、
連續失敗達 CARGO_MAX_FAIL 就放棄 Cargo）；`--html` 整支退回、`--year` 歷史回補維持 HTML。

要擋住的失誤（照重要性排）：
 ① 欄位語意翻錯（ss 藍紅、pc 先後選、vod 三欄優先序、mvpm 只掛系列第一局、'N/A' 當空、&amp; 沒還原、MVP 沒剝本名）
 ② 撞上限（回滿 limit）被當成完整結果 ⇒ 靜靜少一半局
 ③ 單頁查不到沒走備援 ⇒ 那一頁整段消失；或站掛了時切半變成幾十個請求
 ④ 這一輪沒產出的頁沒沿用舊檔（既有行為，不可以在換路徑時弄丟）
 ⑤ `--html`／`--year` 仍打 Cargo 的 MatchScheduleGame
 ⑥ 沙盒漏接（正本 side_sel.js／csv_cache/sidesel 被動到、模組層路徑常數指真實 repo）

**沙盒紀律**（CLAUDE.md #52／#93／#117）：出口（`WS`＝CargoExport、`MH`＝api.php）整個換成假模組、
`ROOT`／`CACHE` 指到暫存；跑之前 assert「模組層沒有字串指著真實 repo」並配反例證明掃描不是空的；
探針頁名 `ZZ Probe 9942` 是只有沙盒才有的證據；正控制釘 commit `b0d2477b`（#118 改動前）——舊版對同一份
假 Cargo 回應**不會**發 MatchScheduleGame 查詢、也產不出探針局；HTML 備援用真實快取頁（手寫 HTML parse() 不認得）。
跑完 assert 真實 side_sel.js 的 md5＋mtime、csv_cache/sidesel 的檔數＋mtime 都沒動。

用法：python scripts\\fetch_side_sel_cargo_test.py
"""
import hashlib, importlib.util, io, json, os, re, shutil, subprocess, sys, tempfile, types, urllib.error, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

import fetch_side_sel as M

OLDREV = "b0d2477b"        # #118 改動前的那個 commit（＝引入本輪改動的 commit 的 ^）
REAL_OUT = os.path.join(ROOT, "side_sel.js")
REAL_CACHE = os.path.join(ROOT, "csv_cache", "sidesel")
# 真實快取頁（HTML 備援用）：First Stand 走 INTL 規則、2026 新制有 1st Sel／Side Sel 欄
FS = "2026 First Stand"
FS_FILE = os.path.join(REAL_CACHE, "2026_first_stand.html")
PROBE = "LCK/2026 Season/ZZ Probe 9942"          # 只有沙盒才有的賽事頁（TIER1 規則放行）
PB = "LPL/2026 Season/ZZ Probe 9942 B"
PC = "LEC/2026 Season/ZZ Probe 9942 C"            # Cargo 有列但全沒 Selection ⇒ 沒產出 ⇒ 沿用舊檔
PAD = ["LCS/2026 Season/ZZ Pad %d" % i for i in range(1, 7)]   # 湊到 10 頁（chunk 8 ⇒ 2 個請求）
GONE = "CBLOL/2026 Season/ZZ Gone 9942"           # 這一輪根本不在清單裡的頁（舊檔沿用）
PAGES = [PROBE, PB, PC] + PAD + [FS]               # FS 排最後：失敗切半時不會把前面的頁拖進連續失敗

OK, BAD, SKIP = [], [], []


def chk(name, cond, extra=""):
    (OK if cond else BAD).append(name)
    print(("  ✓ " if cond else "  ✗ ") + name + (("　" + str(extra)) if extra else ""))
    return bool(cond)


def snapshot_real():
    files = sorted(os.listdir(REAL_CACHE)) if os.path.isdir(REAL_CACHE) else []
    mt = {f: os.path.getmtime(os.path.join(REAL_CACHE, f)) for f in files}
    md5 = hashlib.md5(io.open(REAL_OUT, "rb").read()).hexdigest() if os.path.exists(REAL_OUT) else None
    mo = os.path.getmtime(REAL_OUT) if os.path.exists(REAL_OUT) else None
    return len(files), mt, md5, mo


def repo_refs(mod):
    bad = []
    r = ROOT.lower().replace("\\", "/")
    for k, v in vars(mod).items():
        if k.startswith("__") or k == "HERE":
            continue
        if isinstance(v, str) and r in v.lower().replace("\\", "/"):
            bad.append(k)
    return bad


# ─────────────────────────── 假出口 ───────────────────────────
class _Resp(object):
    def __init__(self, body):
        self._b = body.encode("utf-8")

    def read(self):
        return self._b


class Box(object):
    """沙盒狀態：Cargo 列／HTML 頁／賽程、要失敗的頁、請求紀錄。"""

    def __init__(self):
        self.pages = list(PAGES)
        self.cargo = {}          # ov → MatchScheduleGame⋈MatchSchedule 列
        self.html = {}           # ov → api.php parse 的 HTML
        self.sched = {}          # ov → MatchSchedule 列（HTML 備援配對用）
        self.fail = set()        # 這些頁在 IN 清單裡就丟 503
        self.fail_all = False
        self.nonjson = set()     # 這些頁在 IN 清單裡就回 HTML（限流頁）
        self.reqs = []           # (kind, pages)

    def g_reqs(self):
        return [p for k, p in self.reqs if k == "g"]

    def as_ws(self):
        m = types.SimpleNamespace()
        m.UA = {"User-Agent": "sandbox"}
        m.FORM = "https://sandbox.invalid/Special:CargoExport"
        m.opener = lambda: _Op(self, "cargo")
        return m

    def as_mh(self):
        m = types.SimpleNamespace()
        m.UA = {"User-Agent": "sandbox"}
        m.opener = lambda: _Op(self, "page")
        return m


class _Op(object):
    def __init__(self, box, kind):
        self.box, self.kind = box, kind

    def open(self, req, timeout=0):
        b = self.box
        url = req.get_full_url() if hasattr(req, "get_full_url") else str(req)
        assert "sandbox.invalid" in url or "lol.fandom.com/api.php" in url, "沙盒外的網址：" + url
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        if self.kind == "page":
            page = q.get("page", [""])[0]
            b.reqs.append(("page", [page]))
            h = b.html.get(page)
            return _Resp(json.dumps({"parse": {"text": h}} if h else {"error": {"code": "missingtitle"}}))
        tables = q.get("tables", [""])[0]
        where = q.get("where", [""])[0]
        pages = re.findall(r'"([^"]*)"', where)
        lim = int(q.get("limit", ["2000"])[0])
        if tables.startswith("ScoreboardGames"):
            b.reqs.append(("sg", []))
            return _Resp(json.dumps([{"ov": p} for p in b.pages]))
        if tables.startswith("MatchScheduleGame"):
            b.reqs.append(("g", pages))
            if b.fail_all or (set(pages) & b.fail):
                raise urllib.error.HTTPError(url, 503, "Service Unavailable", {}, io.BytesIO(b""))
            if set(pages) & b.nonjson:
                return _Resp("<!DOCTYPE html><html><body>rate limited</body></html>")
            rows = [r for p in pages for r in b.cargo.get(p, [])]
            return _Resp(json.dumps(rows[:lim]))          # 真的 CargoExport 也是最多回 limit 列
        if tables.startswith("MatchSchedule="):
            b.reqs.append(("ms", pages))
            rows = [dict(r, ov=p) for p in pages for r in b.sched.get(p, [])]
            return _Resp(json.dumps(rows[:lim]))
        raise AssertionError("沙盒不認得的查詢：" + tables)


# ─────────────────────────── 素材 ───────────────────────────
def probe_rows():
    """探針頁 A 的 Cargo 列——每一列對一條語意；故意亂序（gid 20 在 10 前）驗 _ID 排序。"""
    A = PROBE
    r = lambda **k: dict({"ov": A, "mid": None, "ng": None, "gid": None, "blue": None, "red": None, "sel": None,
                          "psel": None, "fsel": None, "fp": None, "vod": None, "vodpb": None, "vodst": None,
                          "mvp": None, "dt": None, "t1": None, "t2": None, "mvpm": None}, **k)
    return [
        # M2 G1：Selection==Red ⇒ 'r'；PickSelection 空 ⇒ pc 0；fsel 'N/A' ⇒ ''；只有 Vod ⇒ vodk 'vod'；mvpm 'None' ⇒ ''
        r(mid="M2", ng=1, gid=20, blue="KT Rolster", red="Dplus Kia", sel="Dplus Kia", psel="", fsel="N/A", fp="",
          vod="https://v.example/full", dt="2026-09-02 10:00:00", t1="KT Rolster", t2="Dplus Kia", mvpm="None"),
        # M1 G1：Selection==Blue ⇒ 'b'；FirstPick==PickSelection ⇒ pc 1；VodPB 有 &amp; ⇒ 還原；MVP 剝本名；mvpm 掛第一局
        r(mid="M1", ng=1, gid=10, blue="T1", red="Gen.G", sel="T1", psel="T1", fsel="Gen.G", fp="T1",
          vodpb="https://youtu.be/x?v=1&amp;t=2", vodst="https://youtu.be/s1", vod="https://youtu.be/f1",
          mvp="Doran (Choi Hyeon-joon)", dt="2026-09-01 08:00:00", t1="T1", t2="Gen.G", mvpm="Faker (Lee Sang-hyeok)"),
        # M1 G2：Selection==Red ⇒ 'r'；FirstPick!=PickSelection ⇒ pc 2；沒 PB 退 Start ⇒ 'start'；mvp 'N/A'；同系列 mvpm 不再掛
        r(mid="M1", ng=2, gid=11, blue="Gen.G", red="T1", sel="T1", psel="Gen.G", fsel="Gen.G", fp="T1",
          vodst="https://youtu.be/s2", mvp="N/A", dt="2026-09-01 08:00:00", t1="T1", t2="Gen.G", mvpm="Faker (Lee Sang-hyeok)"),
        # M1 G3：還沒打（Selection 空）⇒ 不收
        r(mid="M1", ng=3, gid=12, blue="T1", red="Gen.G", sel="", dt="2026-09-01 08:00:00", t1="T1", t2="Gen.G"),
        # M3：TBD 列 ⇒ 不收
        r(mid="M3", ng=1, gid=30, blue="TBD", red="TBD", sel=None, dt="2026-09-03 08:00:00", t1="TBD", t2="TBD"),
    ]


def pb_rows():
    """頁 B：有選邊、完全沒 MVP ⇒ mg 0／mm 0；Selection 不等於藍紅任一方（wiki 打錯）⇒ 不收。"""
    B = PB
    return [
        {"ov": B, "mid": "B1", "ng": 1, "gid": 1, "blue": "JD Gaming", "red": "Bilibili Gaming", "sel": "JD Gaming",
         "psel": "Bilibili Gaming", "fsel": "JD Gaming", "fp": "JD Gaming", "vodpb": "https://youtu.be/b1",
         "dt": "2026-09-05 12:00:00", "t1": "JD Gaming", "t2": "Bilibili Gaming"},
        {"ov": B, "mid": "B1", "ng": 2, "gid": 2, "blue": "Bilibili Gaming", "red": "JD Gaming", "sel": "Weibo Gaming",
         "dt": "2026-09-05 12:00:00", "t1": "JD Gaming", "t2": "Bilibili Gaming"},
    ]


def pad_rows(ov, n):
    return [{"ov": ov, "mid": ov + "#%d" % i, "ng": 1, "gid": i, "blue": "X", "red": "Y", "sel": "X", "psel": "X", "fp": "X",
             "dt": "2026-08-%02d 00:00:00" % (i + 1), "t1": "X", "t2": "Y"} for i in range(1, n + 1)]


def seed(box, mod):
    box.cargo = {PROBE: probe_rows(), PB: pb_rows(),
                 PC: [{"ov": PC, "mid": "C1", "ng": 1, "gid": 1, "blue": "TBD", "red": "TBD", "sel": None,
                       "dt": "2026-09-20 00:00:00", "t1": "TBD", "t2": "TBD"}]}
    for i, p in enumerate(PAD):
        box.cargo[p] = pad_rows(p, 3 + i)          # 3～8 列不等
    # 舊檔：A 的舊局（要被換掉）、C 的舊局（這輪沒產出 ⇒ 沿用）、GONE（不在清單 ⇒ 沿用）
    old = [{"d": "2026-01-01", "t1": "T1", "t2": "Gen.G", "gi": 1, "ss": "b", "blue": "T1", "red": "GEN", "pc": 0, "fs": "",
            "ps": "", "ov": PROBE, "mvp": "", "mvpm": "", "mg": 0, "mm": 0, "vod": "ZZ_OLD_A", "vodk": "vod"},
           {"d": "2026-01-02", "t1": "G2 Esports", "t2": "Fnatic", "gi": 1, "ss": "r", "blue": "FNC", "red": "G2", "pc": 0,
            "fs": "", "ps": "", "ov": PC, "mvp": "", "mvpm": "", "mg": 0, "mm": 0, "vod": "ZZ_OLD_C", "vodk": "vod"},
           {"d": "2026-01-03", "t1": "LOUD", "t2": "paiN Gaming", "gi": 1, "ss": "b", "blue": "LLL", "red": "PNG", "pc": 0,
            "fs": "", "ps": "", "ov": GONE, "mvp": "", "mvpm": "", "mg": 0, "mm": 0, "vod": "ZZ_OLD_GONE", "vodk": "vod"}]
    io.open(os.path.join(mod.ROOT, "side_sel.js"), "w", encoding="utf-8").write(
        "window.SIDE_SEL=" + json.dumps(old, ensure_ascii=False, separators=(",", ":")) + ";")
    # HTML 備援素材：真實 First Stand 快取頁＋由 parse() 反推的賽程（隊名照抄 ⇒ 嚴格那一輪就配得上）
    if os.path.exists(FS_FILE) and os.path.getsize(FS_FILE) > 5000:
        h = io.open(FS_FILE, encoding="utf-8").read()
        box.html[FS] = h
        sers = mod.parse(FS, h)
        rows, exp = [], 0
        for i, s in enumerate(sers):
            m = re.match(r"^(\d+)\s*-\s*(\d+)$", s["score"] or "")
            if not m:
                continue
            rows.append({"dt": "2026-03-%02d 00:00:00" % (1 + i % 28), "t1": s["t1"], "t2": s["t2"], "s1": m.group(1), "s2": m.group(2)})
            exp += len(s["games"])
        box.sched[FS] = rows
        box.fs_expect = exp
    else:
        box.fs_expect = None


def bind(mod, box, tmp):
    mod.WS, mod.MH = box.as_ws(), box.as_mh()
    mod.ROOT = tmp
    mod.CACHE = os.path.join(tmp, "sidesel")
    os.makedirs(mod.CACHE, exist_ok=True)
    mod.GAP = 0.0
    mod.RETRY_GAP = 0.0
    mod._LAST_HIT[0] = 0.0
    for k, v in (("CARGO_GAP", 0.0), ("CARGO_BACKOFF", 0.0)):
        if hasattr(mod, k):
            setattr(mod, k, v)
    if hasattr(mod, "CSTAT"):
        mod.CSTAT.update({"req": 0, "sec": 0.0, "fail": 0, "streak": 0, "trunc": 0})
        mod._CLAST[0] = 0.0
    mod.SCHED_PRE.clear()
    mod._PRE.clear()
    mod._FUT.clear()


def run_main(mod, argv=None):
    old = sys.argv
    sys.argv = ["fetch_side_sel.py"] + list(argv or [])
    buf, so = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        mod.main()
    finally:
        sys.stdout = so
        sys.argv = old
    return buf.getvalue()


def load_out(mod, name="side_sel.js"):
    p = os.path.join(mod.ROOT, name)
    if not os.path.exists(p):
        return None
    t = io.open(p, encoding="utf-8").read()
    m = re.search(r"=\s*\[", t)
    return json.loads(t[m.end() - 1:].rstrip().rstrip(";"))


def by_ov(recs):
    d = {}
    for r in recs or []:
        d.setdefault(r["ov"], []).append(r)
    return d


def main():
    before = snapshot_real()
    defaults = {k: getattr(M, k) for k in ("CARGO_LIMIT", "CARGO_CHUNK", "CARGO_GAP", "CARGO_MAX_FAIL", "CARGO_BACKOFF")}
    tmp = tempfile.mkdtemp(prefix="sidesel_cargo_")
    try:
        # ── 0. 沙盒紀律：接管前掃得到、接管後掃不到 ──
        print("── 0. 沙盒接管 ──")
        chk("0a 接管前模組層有字串指著真實 repo（掃描不是空的）", "CACHE" in repo_refs(M), repo_refs(M))
        box = Box()
        bind(M, box, tmp)
        chk("0b 接管後模組層沒有任何字串指著真實 repo", not repo_refs(M), repo_refs(M))
        M.CACHE = REAL_CACHE
        chk("0c 反例：把 CACHE 還原成真的，掃描要抓得到", repo_refs(M) == ["CACHE"], repo_refs(M))
        M.CACHE = os.path.join(tmp, "sidesel")
        chk("0d 正本預設值：CARGO_LIMIT 2000／CHUNK 8／GAP 0.5／MAX_FAIL 6（> 一個壞頁的 5 次）／BACKOFF 5.0",
            (defaults["CARGO_LIMIT"], defaults["CARGO_CHUNK"], defaults["CARGO_GAP"], defaults["CARGO_MAX_FAIL"], defaults["CARGO_BACKOFF"]) == (2000, 8, 0.5, 6, 5.0), defaults)

        # ── 1. 正規化小函式 ──
        print("\n── 1. 正規化 ──")
        chk("1a _cs：'N/A'／'None'／'TBD'／None → ''", all(M._cs(x) == "" for x in ("N/A", "None", "TBD", None, " n/a ")))
        chk("1b _cs：&amp; 還原、去空白", M._cs(" a&amp;b ") == "a&b")
        chk("1c _nopar：剝掉 (本名)", M._nopar("Doran (Choi Hyeon-joon)") == "Doran" and M._nopar("Smash") == "Smash")
        chk("1d _nopar：'N/A (x)' 也是空", M._nopar("N/A (x)") == "")

        # ── 2. 快樂路徑：欄位語意 ──
        print("\n── 2. 快樂路徑 ──")
        seed(box, M)
        out = run_main(M)
        recs = load_out(M)
        chk("2a 有寫出沙盒 side_sel.js", recs is not None)
        d = by_ov(recs)
        A = d.get(PROBE, [])
        chk("2b 探針頁 A 收到 3 局（G3 沒 Selection、M3 TBD 不收）", len(A) == 3, [(r["d"], r["gi"]) for r in A])
        chk("2c 同頁照 _ID 排（M1 G1、M1 G2 在 M2 前面）", [r["gi"] for r in A] == [1, 2, 1] and A[0]["t1"] == "T1" and A[2]["t1"] == "KT Rolster")
        g1 = next((r for r in A if r["t1"] == "T1" and r["gi"] == 1), {})
        g2 = next((r for r in A if r["t1"] == "T1" and r["gi"] == 2), {})
        m2 = next((r for r in A if r["t1"] == "KT Rolster"), {})
        chk("2d ss：Selection==Blue ⇒ 'b'、==Red ⇒ 'r'", g1.get("ss") == "b" and g2.get("ss") == "r" and m2.get("ss") == "r")
        chk("2e pc：FirstPick==PickSelection ⇒ 1、不等 ⇒ 2、PickSelection 空 ⇒ 0", (g1.get("pc"), g2.get("pc"), m2.get("pc")) == (1, 2, 0))
        chk("2f fs/ps：全名原樣、'N/A' ⇒ ''", (g1.get("fs"), g1.get("ps"), g2.get("ps"), m2.get("fs"), m2.get("ps")) == ("Gen.G", "T1", "Gen.G", "", ""))
        chk("2g vod 優先序：PB > Start > Vod，且 &amp; 還原", (g1.get("vod"), g1.get("vodk")) == ("https://youtu.be/x?v=1&t=2", "pb")
            and (g2.get("vod"), g2.get("vodk")) == ("https://youtu.be/s2", "start") and (m2.get("vod"), m2.get("vodk")) == ("https://v.example/full", "vod"))
        chk("2h mvp：剝本名、'N/A' ⇒ ''", (g1.get("mvp"), g2.get("mvp"), m2.get("mvp")) == ("Doran", "", ""))
        chk("2i mvpm：只掛該系列第一個收到的局、'None' ⇒ ''", (g1.get("mvpm"), g2.get("mvpm"), m2.get("mvpm")) == ("Faker", "", ""))
        chk("2j mg/mm：A 頁 1/1、B 頁 0/0", all(r["mg"] == 1 and r["mm"] == 1 for r in A) and all(r["mg"] == 0 and r["mm"] == 0 for r in d.get(PB, [])))
        chk("2k d/t1/t2/blue/red 取自 MS／G", (g1.get("d"), g1.get("t1"), g1.get("t2"), g1.get("blue"), g1.get("red")) == ("2026-09-01", "T1", "Gen.G", "T1", "Gen.G"))
        chk("2l B 頁：Selection 不等於藍紅任一方的列不收", len(d.get(PB, [])) == 1 and d[PB][0]["gi"] == 1)
        chk("2m 每一筆紀錄的鍵集合跟 HTML 路徑一樣", all(set(r) == {"d", "t1", "t2", "gi", "ss", "blue", "red", "pc", "fs", "ps", "ov", "mvp", "mvpm", "mg", "mm", "vod", "vodk"} for r in recs))
        gq = box.g_reqs()
        chk("2n 10 頁只發 2 個 MatchScheduleGame 請求（8＋2），沒有切半", len(gq) == 2 and len(gq[0]) == 8 and len(gq[1]) == 2, [len(x) for x in gq])
        chk("2o 沒有任何 api.php 頁面請求、沒有賽程批次查詢（Cargo 路徑不需要）", not any(k in ("page", "ms") for k, _ in box.reqs), [k for k, _ in box.reqs])
        chk("2p 日誌有「Cargo 選邊：N 頁 M 局、K 個請求」那行", re.search(r"Cargo 選邊：\d+ 頁 \d+ 局、2 個請求", out) is not None)
        chk("2q 舊檔沿用：A 的舊局被換掉、C（這輪沒產出）與 GONE（不在清單）沿用", not any(r["vod"] == "ZZ_OLD_A" for r in recs)
            and any(r["vod"] == "ZZ_OLD_C" for r in recs) and any(r["vod"] == "ZZ_OLD_GONE" for r in recs) and "沿用舊檔" in out)
        chk("2r pad 頁 3～8 局都收齊", all(len(d.get(p, [])) == 3 + i for i, p in enumerate(PAD)), [len(d.get(p, [])) for p in PAD])
        chk("2s 沒有走備援（FS 頁的 Cargo 列是空的 ⇒ 沒產出、不是查不到）", "HTML 備援" not in out and FS not in d)
        full_recs = recs

        # ── 3. 撞上限切半 ──
        print("\n── 3. 撞上限 ──")
        seed(box, M); box.reqs = []
        M.CARGO_LIMIT = 9          # 要 > 最大單頁列數（Pad 6 有 8 列）：單頁本身就回滿 limit 是切不開的，會走備援（真站 2000 vs 最大頁 204）
        M.CSTAT.update({"req": 0, "fail": 0, "streak": 0, "trunc": 0})
        out3 = run_main(M)
        recs3 = load_out(M)
        M.CARGO_LIMIT = defaults["CARGO_LIMIT"]
        gq = box.g_reqs()
        chk("3a 撞上限 ⇒ 切半重問（請求數 > 2、有單頁請求）", len(gq) > 2 and any(len(x) == 1 for x in gq), [len(x) for x in gq])
        chk("3b CSTAT.trunc > 0", M.CSTAT["trunc"] > 0, M.CSTAT)
        chk("3c 切完的結果跟不撞上限時一模一樣（一局不少）", recs3 == full_recs, "%s vs %s" % (len(recs3 or []), len(full_recs)))
        chk("3d 沒有走備援", "HTML 備援" not in out3)

        # ── 4. 單頁失敗 ⇒ 再試一次 ⇒ HTML 備援（真實快取頁） ──
        print("\n── 4. 單頁失敗走 HTML 備援 ──")
        if box.fs_expect is None:
            SKIP.append("4 沒有真實快取頁 %s" % FS_FILE)
            print("  ⊘ 跳過：沒有 " + FS_FILE)
        else:
            seed(box, M); box.reqs = []
            box.fail = {FS}
            M.CSTAT.update({"req": 0, "fail": 0, "streak": 0, "trunc": 0})
            out4 = run_main(M)
            recs4 = load_out(M)
            d4 = by_ov(recs4)
            gq = box.g_reqs()
            chk("4a FS 那一頁單獨再試一次（兩次單頁請求都 503）；FS 排序在最前 ⇒ 8→4→2→1→重試共 5 次連續失敗", sum(1 for x in gq if x == [FS]) == 2 and sum(1 for x in gq if FS in x) == 5, gq)
            chk("4b 日誌指名走備援", ("走 HTML 備援：" + FS) in out4)
            chk("4c 備援真的去抓那一頁（api.php parse 請求）", any(k == "page" and p == [FS] for k, p in box.reqs))
            chk("4d 備援的局數＝真實頁 parse 出來的局數（%s）" % box.fs_expect, len(d4.get(FS, [])) == box.fs_expect and box.fs_expect > 0, len(d4.get(FS, [])))
            chk("4e 其餘頁仍走 Cargo、結果不變", all(d4.get(p) == by_ov(full_recs).get(p) for p in [PROBE, PB] + PAD))
            chk("4f 一個壞頁的 5 次連續失敗沒讓斷路器跳（MAX_FAIL 6），其餘頁成功後 streak 歸零", M.CSTAT["fail"] == 5 and M.CSTAT["streak"] == 0, M.CSTAT)
            chk("4g 備援頁的紀錄是 HTML 版型（blue/red 是短名、fs/ps 是頁面文字）", all("ov" in r and r["ov"] == FS for r in d4[FS]))
            box.fail = set()

        # ── 5. 站掛了：連續失敗達上限就不再打 Cargo，全走備援；沿用舊檔 ──
        print("\n── 5. 斷路器 ──")
        seed(box, M); box.reqs = []
        box.fail_all = True
        M.CSTAT.update({"req": 0, "fail": 0, "streak": 0, "trunc": 0})
        out5 = run_main(M)
        recs5 = load_out(M)
        gq = box.g_reqs()
        chk("5a MatchScheduleGame 請求剛好 CARGO_MAX_FAIL 次（6），不是切半後的幾十次", len(gq) == 6 and len(gq) == defaults["CARGO_MAX_FAIL"], len(gq))
        chk("5b 全部 10 頁都指名走備援", ("走 HTML 備援：" in out5) and all(p in out5 for p in PAGES))
        chk("5c 備援對每一頁都發了 api.php 請求", set(p[0] for k, p in box.reqs if k == "page") == set(PAGES))
        chk("5d 探針頁沒有 HTML ⇒ 沒產出 ⇒ 舊檔沿用（ZZ_OLD_A 還在）", any(r["vod"] == "ZZ_OLD_A" for r in recs5 or []))
        box.fail_all = False
        # 非 JSON（限流頁）也算失敗
        seed(box, M); box.reqs = []
        box.nonjson = {PB}
        M.CSTAT.update({"req": 0, "fail": 0, "streak": 0, "trunc": 0})
        out5b = run_main(M)
        recs5b = load_out(M)
        chk("5e 回應不是 JSON 也當失敗：PB 走備援、其他頁照收", ("走 HTML 備援：" + PB) in out5b and len(by_ov(recs5b).get(PROBE, [])) == 3 and "回應不是 JSON" in out5b)
        box.nonjson = set()

        # ── 6. --html／--year 不打 MatchScheduleGame；--dump 不寫檔 ──
        print("\n── 6. 旗標 ──")
        seed(box, M); box.reqs = []
        M.CSTAT.update({"req": 0, "fail": 0, "streak": 0, "trunc": 0})
        out6 = run_main(M, ["--html"])
        chk("6a --html：0 個 MatchScheduleGame 請求、每頁都走 api.php", not box.g_reqs() and set(p[0] for k, p in box.reqs if k == "page") == set(PAGES))
        chk("6b --html：日誌沒有「Cargo 選邊」那行", "Cargo 選邊" not in out6)
        seed(box, M); box.reqs = []
        M.YEAR, M.HIST = 2026, False
        out6c = run_main(M, ["--year", "2025"])
        chk("6c --year 2025：0 個 MatchScheduleGame 請求（歷史回補維持 HTML）", not box.g_reqs() and any(k == "page" for k, _ in box.reqs))
        M.YEAR, M.HIST = 2026, False
        seed(box, M); box.reqs = []
        h0 = hashlib.md5(io.open(os.path.join(tmp, "side_sel.js"), "rb").read()).hexdigest()
        out6d = run_main(M, ["--dump"])
        h1 = hashlib.md5(io.open(os.path.join(tmp, "side_sel.js"), "rb").read()).hexdigest()
        chk("6d --dump：有查 Cargo、有印局、但沙盒 side_sel.js 沒被改寫", box.g_reqs() and h0 == h1 and "合計" in out6d)
        seed(box, M); box.reqs = []
        out6e = run_main(M, ["--page", PROBE])
        chk("6e --page：只問那一頁（1 個請求、IN 清單就它）", box.g_reqs() == [[PROBE]] and len(by_ov(load_out(M)).get(PROBE, [])) == 3, box.g_reqs())

        # ── 7. 正控制：舊版（釘 commit，不是 HEAD） ──
        print("\n── 7. 正控制：舊版 %s ──" % OLDREV)
        oldsrc = os.path.join(tmp, "old_fetch_side_sel.py")
        try:
            blob = subprocess.check_output(["git", "show", "%s:scripts/fetch_side_sel.py" % OLDREV], cwd=ROOT)
            io.open(oldsrc, "wb").write(blob)
            got_old = True
        except Exception as e:
            got_old = False
            print("  ⚠ 取不到舊版：%s" % e)
        chk("7a 取得舊版原始碼", got_old)
        if got_old:
            spec = importlib.util.spec_from_file_location("fetch_side_sel_old_m118", oldsrc)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            tmp7 = tempfile.mkdtemp(prefix="sidesel_cargo_old_")
            box7 = Box()
            bind(mod, box7, tmp7)
            chk("7b 舊版沒有 run_cargo／cargo_records（釘對了 commit）", not hasattr(mod, "run_cargo") and not hasattr(mod, "cargo_records"))
            chk("7c 舊版接管後模組層也沒有字串指著真實 repo", not repo_refs(mod), repo_refs(mod))
            seed(box7, mod)
            out7 = run_main(mod)
            recs7 = load_out(mod)
            chk("7d 舊版對同一份沙盒不發 MatchScheduleGame 查詢", not box7.g_reqs())
            chk("7e 舊版產不出探針局（只有 Cargo 才有那 3 局）", not any(r.get("t1") == "T1" and r.get("d") == "2026-09-01" for r in recs7 or []))
            chk("7f 舊版對 FS 真實頁的 HTML 路徑局數跟新版備援一樣（備援＝舊主路徑、沒動）",
                box.fs_expect is None or len(by_ov(recs7).get(FS, [])) == box.fs_expect, len(by_ov(recs7).get(FS, [])) if recs7 else None)
            shutil.rmtree(tmp7, ignore_errors=True)

        # ── 8. 正本一個位元都沒動 ──
        print("\n── 8. 正本 ──")
        after = snapshot_real()
        chk("8a 真實 csv_cache/sidesel 檔數沒變", before[0] == after[0], "%d → %d" % (before[0], after[0]))
        chk("8b 真實 csv_cache/sidesel 的 mtime 沒動", before[1] == after[1])
        chk("8c 真實 side_sel.js 的 md5 沒變", before[2] == after[2])
        chk("8d 真實 side_sel.js 的 mtime 沒動", before[3] == after[3])
        chk("8e 產物全部落在 tmp（沙盒 side_sel.js 存在）", os.path.exists(os.path.join(tmp, "side_sel.js")))
        chk("8f 模組的 CACHE／ROOT 到最後仍指著沙盒", M.CACHE.startswith(tmp) and M.ROOT == tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\nfetch_side_sel_cargo_test：%d 過／%d 敗／%d 跳過" % (len(OK), len(BAD), len(SKIP)))
    for b in BAD:
        print("  ✗ " + b)
    for s in SKIP:
        print("  ⊘ " + s)
    sys.exit(1 if (BAD or len(SKIP) > 1) else 0)


if __name__ == "__main__":
    main()
