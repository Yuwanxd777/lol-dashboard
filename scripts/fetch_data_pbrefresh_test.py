# -*- coding: utf-8 -*-
"""fetch_data.fix_draft_wiki 的「PB 頁快取比那局還舊 ⇒ 重抓一次」沙盒測試（2026-09-16 精進迴圈 #131）。

背景：LCS 2026-08-16 G2 每一班都印「在 PB 頁對不到十隻 → 不動」。PB 頁快取寫於 08-09（24 局），
現況頁 64 局、那局在上面——pb_page() 快取一存在就永遠不重抓，所以快取寫入之後才打的殘缺局永遠修不到。

沙盒接管的證據來源／出口：
  fetch_wiki_mh ：PB_DIR（與模組層其餘指著真實 repo 的字串）、_OP（唯一網路出口：opener() 看到 _OP 就不打表單頁）、
                  GAP（節流）、time（只換 sleep，記錄退避）
  fetch_data    ：HERE（wiki_links.js 從這裡讀）與模組層其餘指著真實 repo 的字串
素材：真實 csv_cache/wikipb 裡第一份解析得出 ≥5 局的 PB 頁（真實版型），探針局用它的一列當模板、
      英雄名換成 Zzprobe*（真 repo 不可能有的值）；「舊快取」＝原頁、「現況頁」＝原頁＋探針列。
正控制：釘 OLDREV（引入本改動之前的 commit），舊版對同一個沙盒 0 個請求、照樣印「對不到十隻」、表格不動。
"""
import contextlib, hashlib, importlib.util, io, json, os, re, shutil, subprocess, sys, tempfile, time, types
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
REAL = os.path.dirname(HERE)
sys.path.insert(0, HERE)
OLDREV = "761507ab"

import fetch_wiki_mh as MH
import fetch_data as FD

OK = FAIL = 0


def check(name, cond, extra=""):
    global OK, FAIL
    if cond:
        OK += 1; print(f"  ✓ {name}")
    else:
        FAIL += 1; print(f"  ✗ {name}  {extra}")


REAL_PB = MH.PB_DIR
stat_dir = lambda d: sorted((f, os.stat(os.path.join(d, f)).st_size, os.stat(os.path.join(d, f)).st_mtime_ns) for f in os.listdir(d))
REAL_FILES = [os.path.join(REAL, "wiki_links.js"), os.path.join(REAL, "data", "data_2026.js")]
stat_f = lambda: [(p, os.stat(p).st_size, os.stat(p).st_mtime_ns) for p in REAL_FILES if os.path.exists(p)]
BEFORE_DIR, BEFORE_F = stat_dir(REAL_PB), stat_f()

# ── 素材：真實 PB 頁 ─────────────────────────────────────────────
SRC = None
for f in sorted(os.listdir(REAL_PB)):
    p = os.path.join(REAL_PB, f)
    if os.path.getsize(p) < 5000:
        continue
    h = io.open(p, encoding="utf-8").read()
    if "pbh-cn" not in h:
        continue
    orig = MH.pb_page
    MH.pb_page = lambda tour, force=False, tries=3, _h=h: _h
    try:
        n = len(MH.pb_orders("x"))
    finally:
        MH.pb_page = orig
    if n >= 5:
        SRC, SRC_HTML = f, h
        break
assert SRC, "真實 csv_cache/wikipb 裡找不到可解析的 PB 頁（素材前提不成立）"
print(f"素材：csv_cache/wikipb/{SRC}")

T1P = [f"Zzprobe A{i}" for i in range(1, 6)]
T2P = [f"Zzprobe B{i}" for i in range(1, 6)]
T1B = [f"Zzban C{i}" for i in range(1, 6)]
T2B = [f"Zzban D{i}" for i in range(1, 5)] + [""]          # 紅方第 5 禁是真的空禁


def make_row(tr, t1p, t2p, t1b, t2b):
    """用真實 <tr> 當模板，只換 data-champion 的值（各格保留原本的隻數與版型）。"""
    spans = [(m.start(1), m.end(1)) for m in re.finditer(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
    # 先數每格原本幾隻，依序切清單
    body = lambda i: tr[spans[i][0]:spans[i][1]]
    nch = lambda i: len(re.findall(r'data-champion="[^"]+"', body(i)))
    seq1, seq2 = list(t1p), list(t2p)
    alloc = {}
    for i in (12, 14, 21):
        alloc[i] = [seq1.pop(0) for _ in range(nch(i))]
    for i in (13, 15, 20, 22):
        alloc[i] = [seq2.pop(0) for _ in range(nch(i))]
    assert not seq1 and not seq2, "模板列的選角格隻數不是 5+5"
    for k, i in enumerate(MH.PB_T1B):
        alloc[i] = [t1b[k]]
    for k, i in enumerate(MH.PB_T2B):
        alloc[i] = [t2b[k]]
    out, last = [], 0
    for i, (a, b) in enumerate(spans):
        out.append(tr[last:a])
        cell = tr[a:b]
        if i in alloc:
            it = iter(alloc[i])
            def sub(m):
                v = next(it, None)
                return f'data-champion="{v}"' if v else 'data-zz-none="1"'
            cell = re.sub(r'data-champion="[^"]+"', sub, cell)
            if alloc[i] and alloc[i][0] and 'data-champion' not in cell:       # 原本是空禁格 → 補一個
                cell = f'<span data-champion="{alloc[i][0]}"></span>' + cell
        out.append(cell)
        last = b
    out.append(tr[last:])
    return "".join(out)


tbl0 = [t for t in re.findall(r"<table[^>]*>.*?</table>", SRC_HTML, re.S) if "pbh-cn" in t][0]
TPL = next(tr for tr in re.findall(r"<tr[^>]*>.*?</tr>", tbl0, re.S)
           if "pbh-cn" in tr and len(re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)) >= 23
           and len(re.findall(r'data-champion="[^"]+"', "".join(re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)[i] for i in (12, 13, 14, 15, 20, 21, 22)))) == 10)
PROBE_TR = make_row(TPL, T1P, T2P, T1B, T2B)
FRESH_HTML = SRC_HTML.replace(tbl0, tbl0[:tbl0.rindex("</table>")] + PROBE_TR + "</table>", 1)
STALE_HTML = SRC_HTML
assert "Zzprobe" not in STALE_HTML


def parse_count(h):
    orig = MH.pb_page
    MH.pb_page = lambda tour, force=False, tries=3: h
    try:
        return MH.pb_orders("x")
    finally:
        MH.pb_page = orig


N_STALE, pb_fresh = len(parse_count(STALE_HTML)), parse_count(FRESH_HTML)
N_FRESH = len(pb_fresh)
print(f"素材局數：舊快取 {N_STALE}、現況頁 {N_FRESH}")
check("[0] 探針列用真實版型解析得出來（現況頁多 1 局）", N_FRESH == N_STALE + 1)
od = MH.pb_of(pb_fresh, T1P, T2P)
check("[0] 探針局 pb_of 對得上、紅禁第 5 格是空", bool(od) and od[3][4] == "" and od[2] == T1B, str(od))

# ── 沙盒 ─────────────────────────────────────────────────────────
TMP = tempfile.mkdtemp(prefix="pbrefresh_")
OV = "ZZ Probe 9942/Season"
LG, SP = "ZZP", "S9"


class FakeResp:
    def __init__(self, b): self.b = b
    def read(self): return self.b


class FakeOp:
    def __init__(self): self.urls, self.mode = [], "fresh"
    def open(self, req, timeout=None):
        url = getattr(req, "full_url", str(req))
        self.urls.append(url)
        if self.mode == "fail":
            raise OSError("zz probe connection reset")
        if self.mode == "error":
            return FakeResp(json.dumps({"error": {"info": "The page you specified doesn't exist."}}).encode())
        h = {"fresh": FRESH_HTML, "stale": STALE_HTML, "nohdr": "<div>" + "x" * 6000 + "</div>"}[self.mode]
        return FakeResp(json.dumps({"parse": {"text": h}}).encode())


SLEEPS = []
tshim = types.SimpleNamespace(**{k: getattr(time, k) for k in dir(time) if not k.startswith("__")})
tshim.sleep = lambda s: SLEEPS.append(s)


def redirect(mod):
    for k, v in list(vars(mod).items()):
        if isinstance(v, str) and REAL in v:
            setattr(mod, k, v.replace(REAL, TMP))


def bind(fd, mh):
    redirect(fd); redirect(mh)
    fd.HERE = TMP
    mh.PB_DIR = os.path.join(TMP, "wikipb")
    mh.GAP = 0.0
    mh._OP = OP
    mh.time = tshim


OP = FakeOp()
os.makedirs(os.path.join(TMP, "wikipb"), exist_ok=True)
io.open(os.path.join(TMP, "wiki_links.js"), "w", encoding="utf-8").write(
    "window.WIKI_LINKS = " + json.dumps({"2026": {LG: {SP: OV}}}) + ";\n")
bind(FD, MH)
left = [(m.__name__, k) for m in (FD, MH) for k, v in vars(m).items() if isinstance(v, str) and REAL in v]
check("[0] 模組層沒有任何字串還指著真實 repo", not left, str(left))
check("[0] PB 快取路徑落在沙盒", MH.pb_cache_path(OV).startswith(TMP))

COLS = ["league", "split", "date", "game", "blue_teamname", "red_teamname", "participantid", "picklist",
        "blue_po", "red_po", "banlist", "blue_banlist", "red_banlist", "blue_champion", "red_champion",
        "blue_Lane", "red_Lane", "blue_firstPick", "red_firstPick"]


def game_rows(date, gno, blue5, red5, broken=True, had=True):
    pk = "|" + "|".join(blue5 + red5[:4]) + "|" if broken else "|" + "|".join(blue5 + red5) + "|"
    bb = "|" + "|".join(T1B) + "|" if had else "||"
    rb = "|" + "|".join(T2B[:4]) + "|" if had else "||"
    if not had:
        pk = "||"
    rows = []
    for pid in ("1", "2", "3", "4", "5"):
        i = int(pid) - 1
        rows.append([LG, SP, date, gno, "Zz Blue", "Zz Red", pid, pk, 0, 0, "|", bb, rb, blue5[i], red5[i], "", "", "1", "0"])
    rows.append([LG, SP, date, gno, "Zz Blue", "Zz Red", "100", pk, "0|0|0|0|0", "0|0|0|0|0", "|", bb, rb, "", "",
                 "|" + "|".join(blue5) + "|", "|" + "|".join(red5) + "|", "1", "0"])
    return rows


def table(*games):
    t = [list(COLS)]
    for g in games:
        t += g
    return t


def team_row(t, date, gno):
    return next(r for r in t[1:] if r[2] == date and r[3] == gno and r[6] == "100")


def seed_cache(html, mtime):
    p = MH.pb_cache_path(OV)
    io.open(p, "w", encoding="utf-8").write(html)
    os.utime(p, (mtime, mtime))
    return p


def run(fd, t, mode="fresh"):
    OP.urls.clear(); OP.mode = mode; SLEEPS.clear()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fd.fix_draft_wiki(t, 2026)
    return buf.getvalue()


def ts(date, days=0.0):
    return datetime.strptime(date[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() + days * 86400


D = "2026-08-16 22:05:12"
GRACE = FD.PB_REFRESH_GRACE_D
check("[0] 寬限天數是 3", GRACE == 3)

# [1] 快取早於那局 ⇒ 重抓一次、修好、快取換成現況頁
print("[1] 快取寫於那局之前 7 天")
p = seed_cache(STALE_HTML, ts(D, -7))
t = table(game_rows(D, "2", T1P, T2P))
out = run(FD, t)
tr = team_row(t, D, "2")
check("[1] 發 1 個請求、是 Picks and Bans 頁", len(OP.urls) == 1 and "Picks%20and%20Bans" in OP.urls[0], str(OP.urls))
check("[1] 印「重抓一次：N → N+1 局」", f"→ 重抓一次：{N_STALE} → {N_FRESH} 局" in out, out)
check("[1] 修好：picklist 十隻、紅禁 5 格含空禁", tr[7] == "|" + "|".join(T1P + T2P) + "|" and tr[12] == "|" + "|".join(T2B) + "|", str(tr))
check("[1] 印「← wiki PB（ban 5+4、先選=藍方）」", "← wiki PB（ban 5+4、先選=藍方）" in out, out)
check("[1] 沒有「對不到十隻」", "對不到十隻" not in out, out)
check("[1] 快取被現況頁取代（含探針）", "Zzprobe" in io.open(p, encoding="utf-8").read())
check("[1] 沒有退避睡眠", not [s for s in SLEEPS if s >= 1], str(SLEEPS))

# [2] 同一份資料再跑一趟 ⇒ 局已修好、不打網路
out2 = run(FD, t)
check("[2] 修好之後再跑：0 個請求、沒有輸出", len(OP.urls) == 0 and out2.strip() == "", out2 + str(OP.urls))

# [3] 快取已晚於「那局＋3 天」⇒ 不重抓、照舊警告（真的修不到的局不會每班打網路）
print("[3] 寬限邊界")
for label, days, expect_req in (("+3 天前 60 秒", GRACE - 60 / 86400, 1), ("+3 天後 60 秒", GRACE + 60 / 86400, 0), ("+20 天", 20, 0)):
    seed_cache(STALE_HTML, ts(D, days))
    t = table(game_rows(D, "2", T1P, T2P))
    out = run(FD, t)
    check(f"[3] 快取寫於那局{label} ⇒ 請求 {expect_req}", len(OP.urls) == expect_req, f"{OP.urls} {out}")
    if not expect_req:
        check(f"[3] {label}：照舊印「對不到十隻」、表格不動", "對不到十隻" in out and team_row(t, D, "2")[12] == "|" + "|".join(T2B[:4]) + "|", out)

# [3b] 那局才剛打完、上一班才重抓過（快取 mtime＝12 小時前）⇒ 這一班仍重抓 1 次：
#      寬限期內是「每班每頁一次」，不是「整局只一次」（docstring 寫的就是這個代價：3 天 ≈ 6 班）
tday = datetime.now(timezone.utc).strftime("%Y-%m-%d") + " 01:00:00"
seed_cache(STALE_HTML, time.time() - 12 * 3600)
t = table(game_rows(tday, "2", T1P, T2P))
out = run(FD, t, mode="stale")
check("[3b] 寬限期內上一班才重抓過：這一班仍發 1 個請求、印「重抓一次」＋「對不到十隻」",
      len(OP.urls) == 1 and f"重抓一次：{N_STALE} → {N_STALE} 局" in out and "對不到十隻" in out, f"{OP.urls} {out}")

# [4] 重抓失敗 ⇒ 只試一次、不退避、沿用快取、快取位元不動
print("[4] 重抓失敗")
p = seed_cache(STALE_HTML, ts(D, -7))
md5 = hashlib.md5(open(p, "rb").read()).hexdigest(); mt = os.stat(p).st_mtime_ns
t = table(game_rows(D, "2", T1P, T2P))
out = run(FD, t, mode="fail")
check("[4] 只發 1 個請求（tries=1）", len(OP.urls) == 1, str(OP.urls))
check("[4] 沒有 15s 以上的退避", not [s for s in SLEEPS if s >= 1], str(SLEEPS))
check("[4] 印「沒抓成，沿用快取」＋「對不到十隻」", "沒抓成，沿用快取" in out and "對不到十隻" in out, out)
check("[4] 快取位元與 mtime 不動", hashlib.md5(open(p, "rb").read()).hexdigest() == md5 and os.stat(p).st_mtime_ns == mt)

# [4b] 同一個沙盒、快取裡有另一局可修 ⇒ 重抓失敗也不影響那一局（沿用快取那份，不是變成空的）
tpl_od = next(iter(parse_count(STALE_HTML).values()))
b5, r5 = tpl_od["p"]
alt = table(game_rows(D, "2", T1P, T2P), game_rows("2026-08-15 10:00:00", "1", b5, r5))
out = run(FD, alt, mode="fail")
check("[4b] 快取裡本來就有的那局照樣修好（pbs 沒被空結果蓋掉）", "2026-08-15 G1 ← wiki PB" in out, out)

# [5] 重抓回來沒有 pbh-cn 表 ⇒ 快取不被蓋掉
print("[5] 重抓回來版型壞掉")
p = seed_cache(STALE_HTML, ts(D, -7))
md5 = hashlib.md5(open(p, "rb").read()).hexdigest()
t = table(game_rows(D, "2", T1P, T2P))
out = run(FD, t, mode="nohdr")
check("[5] 印「沒有 pbh-cn 表 → 保留快取」", "保留快取" in out, out)
check("[5] 快取位元不動", hashlib.md5(open(p, "rb").read()).hexdigest() == md5)

# [6] 頁面不存在（error）⇒ 快取不動
p = seed_cache(STALE_HTML, ts(D, -7))
md5 = hashlib.md5(open(p, "rb").read()).hexdigest()
out = run(FD, table(game_rows(D, "2", T1P, T2P)), mode="error")
check("[6] error 回應：1 個請求、快取位元不動、沿用快取", len(OP.urls) == 1 and hashlib.md5(open(p, "rb").read()).hexdigest() == md5 and "沿用快取" in out, out)

# [7] 同一頁兩局都對不上 ⇒ 只重抓一次
print("[7] 同一頁多局")
seed_cache(STALE_HTML, ts(D, -7))
g2 = [f"Zzother E{i}" for i in range(1, 6)]; g3 = [f"Zzother F{i}" for i in range(1, 6)]
t = table(game_rows(D, "2", T1P, T2P), game_rows(D, "3", g2, g3))
out = run(FD, t, mode="stale")
check("[7] 兩局對不上、同一頁只發 1 個請求", len(OP.urls) == 1 and out.count("重抓一次") == 1, f"{OP.urls} {out}")

# [8] 沒有快取、這一趟才抓 ⇒ 即使那局是今天（在寬限內）也不再強制重抓
print("[8] 沒有快取")
os.remove(MH.pb_cache_path(OV))
today = datetime.now(timezone.utc).strftime("%Y-%m-%d") + " 01:00:00"
t = table(game_rows(today, "1", g2, g3))
out = run(FD, t, mode="stale")
check("[8] 沒快取：只發 pb_orders 那 1 個請求、不再重抓", len(OP.urls) == 1 and "重抓一次" not in out, f"{OP.urls} {out}")

# [9] 快取就對得上 ⇒ 0 個請求
seed_cache(FRESH_HTML, ts(D, -7))
t = table(game_rows(D, "2", T1P, T2P))
out = run(FD, t)
check("[9] 快取本來就有那局：0 個請求、修好", len(OP.urls) == 0 and "← wiki PB" in out, f"{OP.urls} {out}")

# [10] 整局沒 BP（_had=False）也適用重抓（這類本來安靜失敗、註解說「下次更新會再試」其實讀同一份舊快取）
seed_cache(STALE_HTML, ts(D, -7))
t = table(game_rows(D, "2", T1P, T2P, had=False))
out = run(FD, t)
check("[10] 整局沒 BP：重抓一次並修好", len(OP.urls) == 1 and "← wiki PB" in out, out)

# [11] pb_page 預設 tries=3 失敗時：最後一次之後不睡（15+30，不是 15+30+45）
os.remove(MH.pb_cache_path(OV))
OP.urls.clear(); OP.mode = "fail"; SLEEPS.clear()
with contextlib.redirect_stdout(io.StringIO()):
    h = MH.pb_page(OV)
check("[11] 預設 3 次、睡 [15, 30]、回空", h == "" and len(OP.urls) == 3 and SLEEPS == [15, 30], f"{OP.urls} {SLEEPS}")

# [12] 突變：寬限改成 0 天 ⇒ 快取寫於那局之後 1 天（原本會重抓的 [3] 前一條）就不重抓
FD.PB_REFRESH_GRACE_D = 0
seed_cache(STALE_HTML, ts(D, 1))
out = run(FD, table(game_rows(D, "2", T1P, T2P)))
check("[12] 突變 GRACE=0：快取晚於那局 1 天 ⇒ 0 個請求（證明寬限真的有在判）", len(OP.urls) == 0, out)
FD.PB_REFRESH_GRACE_D = GRACE

# ── 正控制：舊版 ─────────────────────────────────────────────────
print(f"[13] 正控制：舊版（{OLDREV}）")
OLD = os.path.join(TMP, "oldsrc", "scripts")
os.makedirs(OLD, exist_ok=True)
for f in ("fetch_data.py", "fetch_wiki_mh.py"):
    src = subprocess.run(["git", "-C", REAL, "show", f"{OLDREV}:scripts/{f}"], capture_output=True).stdout
    open(os.path.join(OLD, f), "wb").write(src)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


old_mh = load("fetch_wiki_mh_old131", os.path.join(OLD, "fetch_wiki_mh.py"))
old_fd = load("fetch_data_old131", os.path.join(OLD, "fetch_data.py"))
check("[13] 舊版真的沒有 pb_cache_mtime／PB_REFRESH_GRACE_D", not hasattr(old_mh, "pb_cache_mtime") and not hasattr(old_fd, "PB_REFRESH_GRACE_D"))
redirect(old_fd); redirect(old_mh)
old_fd.HERE = TMP
old_mh.PB_DIR = os.path.join(TMP, "wikipb"); old_mh.GAP = 0.0; old_mh._OP = OP; old_mh.time = tshim
left = [(m.__name__, k) for m in (old_fd, old_mh) for k, v in vars(m).items() if isinstance(v, str) and REAL in v]
check("[13] 舊版模組層也沒有字串指著真實 repo", not left, str(left))
seed_cache(STALE_HTML, ts(D, -7))
t = table(game_rows(D, "2", T1P, T2P))
saved = sys.modules["fetch_wiki_mh"]
sys.modules["fetch_wiki_mh"] = old_mh                      # 舊 fix_draft_wiki 函式內 import fetch_wiki_mh
try:
    out = run(old_fd, t)
finally:
    sys.modules["fetch_wiki_mh"] = saved
check("[13] 舊版：0 個請求、印「對不到十隻」、表格不動", len(OP.urls) == 0 and "對不到十隻" in out
      and team_row(t, D, "2")[12] == "|" + "|".join(T2B[:4]) + "|", f"{OP.urls} {out}")

# ── 真實檔案沒動 ─────────────────────────────────────────────────
shutil.rmtree(TMP, ignore_errors=True)
check("[14] 真實 csv_cache/wikipb 檔名＋大小＋mtime_ns 沒動", stat_dir(REAL_PB) == BEFORE_DIR)
check("[14] 真實 wiki_links.js／data_2026.js 大小＋mtime_ns 沒動", stat_f() == BEFORE_F)

print(f"\n{OK} 過 / {FAIL} 失敗")
sys.exit(1 if FAIL else 0)
