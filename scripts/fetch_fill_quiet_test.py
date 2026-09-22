# -*- coding: utf-8 -*-
"""fetch_fill「安靜賽段每 RECHECK_H 小時才重抓」沙盒測試（2026-09-16 精進迴圈 #129）。

驗的是：
  ① 補充資料最新一局早於 QUIET_DAYS 天、上次重抓未滿 RECHECK_H ⇒ main() 不叫 warm_wiki／build／build_wiki、exit 0、檔案一個位元沒動
  ② 到期／賽段還在打／任一份缺 key、缺列、缺日期／--force／--no-quiet-skip／--dump ⇒ 照舊抓
  ③ 假時鐘走 8 班（每班 12h、重抓時把檔 mtime 蓋成當下）⇒ 重抓 2 次（每 4 班 1 次）；突變 RECHECK_H=1e9 ⇒ 只剩 0 次（鑑別力）
  ④ 上限契約：RECHECK_H < check_keys.FILL_STALE_H、< GOLGG_STALE_HARD_DAYS×24；重抓那班 gol.gg 暫時失敗仍 exit 0
  ⑤ 正控制釘 OLDREV（本輪改動前）：舊版對同一份安靜沙盒照樣三步全叫
  ⑥（2026-09-22 #211）「上次重抓」看 block 自記的 fetched_at、不看共用檔 mtime：別的 key 重寫共用檔不會讓安靜 key 看起來「剛抓過」
     （共用檔每班被重寫的 8 班仍複查 2 次；舊版 0 次）；沒記／記垃圾退回 mtime；build()／fetch_wiki_mh.build() 真的會蓋章
     （網路與 fetch_data.process 換假的、寫檔走真程式）；正控制釘 OLDREV2 證明舊版不蓋章、也看不出 50h 沒抓
隔離：CACHE／HCACHE 指暫存目錄並當場點名；warm_wiki／build／build_wiki 換記錄器；urlopen 與 fetch_wiki_mh.opener 一叫就炸；
跑完 assert 真實 csv_cache/fill_2026.json、wikifill_2026.json 的 size＋mtime_ns 沒動。
用法：python scripts/fetch_fill_quiet_test.py
"""
import io, os, re, sys, json, time, tempfile, shutil, subprocess, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OLDREV = "3663e923"   # #129 改動前的 HEAD；#93：釘 commit，不寫 HEAD
if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
_STDOUT = sys.stdout
_KEEP = []
sys.path.insert(0, HERE)

FAIL, OKN = [], [0]


def ck(cond, msg):
    OKN[0] += 1
    if cond:
        print("  ✓ " + msg)
    else:
        FAIL.append(msg)
        print("  ✗ " + msg)


REAL = [os.path.join(ROOT, "csv_cache", "fill_2026.json"), os.path.join(ROOT, "csv_cache", "wikifill_2026.json")]


def stat_real():
    out = {}
    for p in REAL:
        if os.path.exists(p):
            st = os.stat(p)
            out[p] = (st.st_size, st.st_mtime_ns)
    return out


REAL0 = stat_real()
SB = tempfile.mkdtemp(prefix="m129_fillquiet_")
YEAR = 2099
KEY = "ZZ_PROBE_9942"
CFG = {"key": KEY, "tournament": "ZZ Probe 9942", "wiki": "ZZ Probe 9942", "league": "ZZ",
       "split": "Split 9", "year": YEAR, "playoffs": 0}
HDR = ["league", "split", "date", "game", "participantid", "blue_teamname", "red_teamname"]
T0 = 4102444800.0 - 400 * 86400       # 固定的假「現在」（2098 年底），跟真實日曆無關
CALLS = []


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    _KEEP.append(m)
    return m


def boom(*a, **k):
    raise AssertionError("測試不該打真的網路")


def bind(m):
    m.CACHE = os.path.join(SB, "csv_cache")
    m.HCACHE = os.path.join(m.CACHE, "golgg")
    os.makedirs(m.HCACHE, exist_ok=True)
    m.FILL = [dict(CFG)]
    m.urllib.request.urlopen = boom
    m.warm_wiki = lambda cfg: CALLS.append("warm")

    def _build(cfg, force=False, dump=False):
        CALLS.append("build" + ("(dump)" if dump else ""))
        return None
    m.build = _build
    m.build_wiki = lambda cfg: CALLS.append("wiki")
    m._PH.clear()
    if hasattr(m, "_now"):
        m._now = lambda: CLOCK[0]
    # 點名：模組層路徑常數不可還指著真實 repo
    leaks = [k for k in ("CACHE", "HCACHE") if os.path.abspath(getattr(m, k)).startswith(os.path.join(ROOT, "csv_cache"))]
    return leaks


CLOCK = [T0]


def day(n):
    return time.strftime("%Y-%m-%d", time.localtime(T0 - n * 86400))


def seed(newest_days_ago=30, fill_age_h=12.0, wiki_age_h=12.0, fill=True, wiki=True, fill_rows=True, wiki_rows=True,
         wiki_key=True, date_col=True):
    cdir = os.path.join(SB, "csv_cache")
    os.makedirs(cdir, exist_ok=True)
    hdr = HDR if date_col else [c for c in HDR if c != "date"]
    def rows(n_days):
        base = [["ZZ", "S9", day(n_days + 5) + " 09:00:00", "1", "100", "A", "B"],
                ["ZZ", "S9", day(n_days) + " 11:00:00", "2", "100", "A", "B"]]
        return base if date_col else [[c for i, c in enumerate(r) if i != 2] for r in base]
    for nm, on, age, has_rows, has_key in (("fill", fill, fill_age_h, fill_rows, True),
                                           ("wikifill", wiki, wiki_age_h, wiki_rows, wiki_key)):
        p = os.path.join(cdir, f"{nm}_{YEAR}.json")
        if os.path.exists(p):
            os.remove(p)
        if not on:
            continue
        d = {"OTHER_9942": {"header": HDR, "rows": [["ZZ", "S9", day(1) + " 00:00:00", "1", "100", "C", "D"]]}}
        if has_key:
            # 真實格式：fill 的 games 是 gol.gg gid 清單、wikifill 的 games 是局數（--status 各自這樣讀）
            d[KEY] = {"header": hdr, "rows": rows(newest_days_ago) if has_rows else [],
                      "games": [1, 2] if nm == "fill" else 2}
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        t = CLOCK[0] - age * 3600
        os.utime(p, (t, t))


def fsnap():
    cdir = os.path.join(SB, "csv_cache")
    out = {}
    for n in sorted(os.listdir(cdir)):
        p = os.path.join(cdir, n)
        if os.path.isfile(p):
            st = os.stat(p)
            out[n] = (st.st_size, st.st_mtime_ns, open(p, "rb").read())
    return out


def run(m, argv=()):
    CALLS.clear()
    m._PH.clear()
    sys.argv = ["fetch_fill.py"] + list(argv)
    buf = io.StringIO()
    sys.stdout = buf
    try:
        rc = m.main()
    except SystemExit as e:
        rc = e.code
    finally:
        sys.stdout = _STDOUT
    return rc, buf.getvalue(), list(CALLS)


ff = load("fetch_fill_m129new", os.path.join(HERE, "fetch_fill.py"))
import fetch_wiki_mh as _fw
_fw.opener = boom

print("【0】隔離與契約")
leaks = bind(ff)
ck(not leaks, f"新版模組層路徑都改指沙盒（漏：{leaks}）")
ck(hasattr(ff, "quiet_skip") and hasattr(ff, "QUIET_DAYS") and hasattr(ff, "RECHECK_H"), "新版有 quiet_skip／QUIET_DAYS／RECHECK_H")
ck_src = open(os.path.join(HERE, "check_keys.py"), encoding="utf-8").read()
mm = re.search(r"^FILL_STALE_H\s*=\s*([\d.]+)", ck_src, re.M)
ck(mm is not None, "check_keys.py 讀得到 FILL_STALE_H")
if mm:
    ck(ff.RECHECK_H < float(mm.group(1)), f"RECHECK_H {ff.RECHECK_H} < check_keys.FILL_STALE_H {mm.group(1)}（跳過的班次金鑰檢查不報舊）")
ck(ff.RECHECK_H < ff.GOLGG_STALE_HARD_DAYS * 24, f"RECHECK_H {ff.RECHECK_H} < GOLGG_STALE_HARD_DAYS×24（重抓那班暫時失敗仍 exit 0）")
ck(ff.RECHECK_H > 36, "RECHECK_H > 36（第 3 班 36h 不會到期 ⇒ 真的有省）")

print("\n【1】安靜＋未到期 ⇒ 跳過")
seed(newest_days_ago=30, fill_age_h=12, wiki_age_h=12)
before = fsnap()
rc, out, calls = run(ff)
ck(rc == 0, f"exit 0（實際 {rc}）")
ck(calls == [], f"warm_wiki／build／build_wiki 一個都沒叫（實際 {calls}）")
ck("這班不重抓" in out and KEY in out, "日誌印「沿用 fill／wikifill、這班不重抓」並指名 key")
ck("30 天前" in out and "12 小時前" in out, "日誌帶最新一局幾天前與上次重抓幾小時前")
ck(fsnap() == before, "沙盒兩份補充資料 size／mtime／內容一個位元沒動")
ck("完成。" in out, "收尾行照印（run_update 日誌格式不變）")

print("\n【2】到期 ⇒ 重抓（邊界）")
seed(newest_days_ago=30, fill_age_h=ff.RECHECK_H - 0.1, wiki_age_h=ff.RECHECK_H - 0.1)
rc, out, calls = run(ff)
ck(calls == [], f"差 0.1h 未到期 ⇒ 仍跳過（實際 {calls}）")
seed(newest_days_ago=30, fill_age_h=ff.RECHECK_H + 0.01, wiki_age_h=ff.RECHECK_H + 0.01)
rc, out, calls = run(ff)
ck(calls == ["warm", "build", "wiki"], f"到期 ⇒ 暖抓→gol.gg→wiki 照舊順序（實際 {calls}）")
ck("這班重抓一次" in out, "日誌印「這班重抓一次」")
ck(rc == 0, "exit 0")

print("\n【3】賽段還在打 ⇒ 每班照抓（QUIET_DAYS 邊界）")
seed(newest_days_ago=ff.QUIET_DAYS - 1, fill_age_h=1, wiki_age_h=1)
rc, out, calls = run(ff)
ck(calls == ["warm", "build", "wiki"], f"最新一局 {ff.QUIET_DAYS - 1} 天前、1 小時前才抓過 ⇒ 仍照抓（實際 {calls}）")
ck("不重抓" not in out and "重抓一次" not in out, "進行中的賽段不印安靜賽段那行")
seed(newest_days_ago=ff.QUIET_DAYS + 1, fill_age_h=1, wiki_age_h=1)
rc, out, calls = run(ff)
ck(calls == [], f"最新一局 {ff.QUIET_DAYS + 1} 天前 ⇒ 跳過（實際 {calls}）")

print("\n【4】證據不齊 ⇒ 照抓（閘門該做的事照做）")
for label, kw in (("wikifill 檔不存在", dict(wiki=False)),
                  ("fill 檔不存在", dict(fill=False)),
                  ("wikifill 沒這個 key", dict(wiki_key=False)),
                  ("fill 的列是空的（_m108 那種種子）", dict(fill_rows=False)),
                  ("沒有 date 欄", dict(date_col=False)),
                  ("fill 剛抓、wikifill 上次沒抓成（50h）", dict(fill_age_h=1, wiki_age_h=50))):
    base = dict(newest_days_ago=30, fill_age_h=12, wiki_age_h=12)
    base.update(kw)
    seed(**base)
    rc, out, calls = run(ff)
    ck("build" in calls and "wiki" in calls, f"{label} ⇒ 照抓（實際 {calls}）")
cdir = os.path.join(SB, "csv_cache")
seed(newest_days_ago=30)
with open(os.path.join(cdir, f"fill_{YEAR}.json"), "w", encoding="utf-8") as f:
    f.write("{壞掉的 json")
rc, out, calls = run(ff)
ck("build" in calls, f"fill JSON 壞掉 ⇒ 不炸、照抓（實際 {calls}，rc {rc}）")

print("\n【5】旗標")
seed(newest_days_ago=30, fill_age_h=12, wiki_age_h=12)
for argv, want in ((["--force"], ["warm", "build", "wiki"]),
                   (["--no-quiet-skip"], ["warm", "build", "wiki"]),
                   (["--dump"], ["build(dump)"]),
                   (["--no-wiki"], [])):
    rc, out, calls = run(ff, argv)
    ck(calls == want, f"{argv} ⇒ {want}（實際 {calls}）")
seed(newest_days_ago=30, fill_age_h=12, wiki=False)
rc, out, calls = run(ff, ["--no-wiki"])
ck(calls == [], f"--no-wiki 只看 gol.gg 那份：wikifill 不存在也可以跳過（實際 {calls}）")
seed(newest_days_ago=30, fill_age_h=12, wiki_age_h=12)
rc, out, calls = run(ff, ["--status"])
ck(calls == [] and "gol.gg=" in out and "這班不重抓" not in out, "--status 照舊只印狀態、不走安靜判定")

print("\n【6】假時鐘走 8 班（每班 12h；重抓就把兩份檔 mtime 蓋成當下）")


def timeline(m, shifts=8):
    CLOCK[0] = T0
    seed(newest_days_ago=30, fill_age_h=0, wiki_age_h=0)
    n = 0
    for i in range(1, shifts + 1):
        CLOCK[0] = T0 + i * 12 * 3600 + (37 if i % 2 else -41)     # 班次起跑時間有秒級抖動
        rc, out, calls = run(m)
        if "build" in calls:
            n += 1
            for nm in ("fill", "wikifill"):
                p = os.path.join(cdir, f"{nm}_{YEAR}.json")
                os.utime(p, (CLOCK[0], CLOCK[0]))
    CLOCK[0] = T0
    return n


n_new = timeline(ff)
ck(n_new == 2, f"8 班重抓 2 次（每 4 班 1 次；實際 {n_new}）")
_rh = ff.RECHECK_H
ff.RECHECK_H = 1e9
n_mut = timeline(ff)
ff.RECHECK_H = _rh
ck(n_mut == 0, f"突變 RECHECK_H=1e9 ⇒ 8 班 0 次（證明【6】量得到重抓週期；實際 {n_mut}）")
_qd = ff.QUIET_DAYS
ff.QUIET_DAYS = 10 ** 6
n_mut2 = timeline(ff)
ff.QUIET_DAYS = _qd
ck(n_mut2 == 8, f"突變 QUIET_DAYS=10^6（永不安靜）⇒ 8 班 8 次＝舊行為（實際 {n_mut2}）")

print("\n【7】重抓那班 gol.gg 暫時失敗 ⇒ 仍 exit 0（跟 #108 的上限咬合）")
seed(newest_days_ago=30, fill_age_h=ff.RECHECK_H + 6, wiki_age_h=ff.RECHECK_H + 6)
_real_age = time.time() - (ff.RECHECK_H + 6) * 3600     # _transient_verdict 用真時鐘看 mtime
os.utime(os.path.join(cdir, f"fill_{YEAR}.json"), (_real_age, _real_age))
rc1, why = ff._transient_verdict(dict(CFG), True)
ck(rc1 == 0, f"上次重抓 {ff.RECHECK_H + 6:.0f}h 前 ⇒ _transient_verdict 回 0（{why.strip()[:40]}…）")

print(f"\n【8】正控制（{OLDREV}）")
old_src = subprocess.run(["git", "-C", ROOT, "show", f"{OLDREV}:scripts/fetch_fill.py"], capture_output=True).stdout
ck(len(old_src) > 1000 and b"quiet_skip" not in old_src, "OLDREV 那版拉得出來、而且真的沒有 quiet_skip")
od = tempfile.mkdtemp(prefix="m129_old_")
op = os.path.join(od, "fetch_fill_m129old.py")
open(op, "wb").write(old_src)
sys.path.insert(0, HERE)
fo = load("fetch_fill_m129old", op)
leaks_o = bind(fo)
ck(not leaks_o, f"舊版模組層路徑也改指沙盒（漏：{leaks_o}）")
seed(newest_days_ago=30, fill_age_h=12, wiki_age_h=12)
rc, out, calls = run(fo)
ck(calls == ["warm", "build", "wiki"], f"舊版對同一份安靜沙盒三步全叫（實際 {calls}）")
n_old = timeline(fo)
ck(n_old == 8, f"舊版 8 班重抓 8 次（實際 {n_old}）")

print("\n【10】block 自記 fetched_at 優先於共用檔 mtime（2026-09-22 精進迴圈 #211）")
OLDREV2 = "c20c617a"   # #211 改動前的 HEAD（#93：釘 commit，不寫 HEAD）


_NA = object()


def stamp(nm, h, raw=_NA):
    """把沙盒 {nm}_{YEAR}.json 裡 KEY 的 block 蓋上 fetched_at＝CLOCK − h 小時（raw 給定就照放，含 None），檔案 mtime 不動
    （模擬「這個 key 上次真的抓成是 h 小時前，但檔案後來被別的 key 重寫過」）。"""
    p = os.path.join(cdir, f"{nm}_{YEAR}.json")
    st = os.stat(p)
    d = json.load(open(p, encoding="utf-8"))
    d[KEY]["fetched_at"] = raw if raw is not _NA else CLOCK[0] - h * 3600
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.utime(p, (st.st_atime, st.st_mtime))


ck(hasattr(ff, "_last_fetch"), "新版有 _last_fetch")
seed(newest_days_ago=30, fill_age_h=1, wiki_age_h=1)
stamp("fill", 50); stamp("wikifill", 50)
rc, out, calls = run(ff)
ck(calls == ["warm", "build", "wiki"], f"共用檔 1h 前被別的 key 重寫、自己的 block 記 50h ⇒ 到期重抓（實際 {calls}）")
ck("50 小時前" in out and "這班重抓一次" in out, "日誌印的是 block 的 50 小時、不是檔案的 1 小時")
seed(newest_days_ago=30, fill_age_h=50, wiki_age_h=50)
stamp("fill", 12); stamp("wikifill", 12)
rc, out, calls = run(ff)
ck(calls == [] and "12 小時前" in out, f"反向：檔案 mtime 50h、block 12h ⇒ block 贏 ⇒ 跳過（實際 {calls}）")
seed(newest_days_ago=30, fill_age_h=1, wiki_age_h=1)
stamp("wikifill", 50)
rc, out, calls = run(ff)
ck(calls == ["warm", "build", "wiki"], f"只有 wiki 那份記了 50h、fill 沒記（mtime 1h）⇒ 取較舊者 ⇒ 重抓（實際 {calls}）")
seed(newest_days_ago=30, fill_age_h=12, wiki_age_h=12)
rc, out, calls = run(ff)
ck(calls == [] and "12 小時前" in out, "舊格式（兩份都沒有 fetched_at）⇒ 退回檔案 mtime 12h ⇒ 跳過（#129 行為不變）")
for raw in ("abc", 0, -5, True, None):
    seed(newest_days_ago=30, fill_age_h=12, wiki_age_h=12)
    stamp("fill", 0, raw=raw); stamp("wikifill", 0, raw=raw)
    rc, out, calls = run(ff)
    ck(rc == 0 and calls == [] and "12 小時前" in out, f"fetched_at={raw!r} ⇒ 當沒記、退回 mtime 12h、不炸、跳過（實際 rc {rc}／{calls}）")
CFG_W = {"key": KEY, "wiki": "ZZ Probe 9942", "league": "ZZ", "split": "", "year": YEAR, "playoffs": 0, "golgg": False}
ff.FILL = [dict(CFG_W)]
seed(newest_days_ago=30, fill=False, wiki_age_h=1)
stamp("wikifill", 43)
rc, out, calls = run(ff)
ck(calls == ["wiki"], f"wiki_only（AG2026_PRE 那型）：共用 wikifill 1h 前被別的 key 重寫、自己的 block 43h ⇒ 到期重抓（實際 {calls}）")
seed(newest_days_ago=30, fill=False, wiki_age_h=1)
stamp("wikifill", 41)
rc, out, calls = run(ff)
ck(calls == [], f"wiki_only：block 41h ⇒ 未到期 ⇒ 跳過（實際 {calls}）")
ff.FILL = [dict(CFG)]


def timeline_shared(m, shifts=8):
    """#211 要修的情境：每班都有別的 key 重寫共用檔（mtime＝當下）；只有真的重抓那班才蓋 block 的 fetched_at。"""
    CLOCK[0] = T0
    seed(newest_days_ago=30, fill_age_h=0, wiki_age_h=0)
    stamp("fill", 0); stamp("wikifill", 0)
    n = 0
    for i in range(1, shifts + 1):
        CLOCK[0] = T0 + i * 12 * 3600 + (37 if i % 2 else -41)
        for nm in ("fill", "wikifill"):        # 別的 key 這班重寫了共用檔
            p = os.path.join(cdir, f"{nm}_{YEAR}.json")
            os.utime(p, (CLOCK[0], CLOCK[0]))
        rc, out, calls = run(m)
        if "build" in calls:
            n += 1
            stamp("fill", 0); stamp("wikifill", 0)
    CLOCK[0] = T0
    return n


n_sh = timeline_shared(ff)
ck(n_sh == 2, f"共用檔每班被別的 key 重寫：新版 8 班仍重抓 2 次（每 4 班 1 次；實際 {n_sh}）")

print("\n【11】build()／fetch_wiki_mh.build() 真的把 fetched_at 寫進 block（網路與 process 換成假的、寫檔走真程式）")
import types
FAKE_ROW = ["ZZ", "S9", day(30) + " 11:00:00", "1", "100", "A", "B"]
fake_fd = types.SimpleNamespace(process=lambda csv_text, year: [HDR, FAKE_ROW])
_saved_fd = sys.modules.get("fetch_data")
sys.modules["fetch_data"] = fake_fd
fill_p = os.path.join(cdir, f"fill_{YEAR}.json")
wp = os.path.join(cdir, f"wikifill_{YEAR}.json")


def bind_write(m):
    m.CACHE = os.path.join(SB, "csv_cache")
    m.HCACHE = os.path.join(m.CACHE, "golgg")
    m.urllib.request.urlopen = boom
    if hasattr(m, "_now"):
        m._now = lambda: CLOCK[0]
    m.gate = lambda cfg: (True, 0, {}, fill_p)
    m.collect = lambda cfg, force=False: [{"gid": 7}]
    m.to_csv_rows = lambda games, cfg: (HDR, [FAKE_ROW])
    m._PH.clear()


def bind_wiki_write(m):
    m.CACHE = os.path.join(SB, "csv_cache")
    m.HTML_DIR = os.path.join(m.CACHE, "wikitxt")
    m.PB_DIR = os.path.join(m.CACHE, "wikipb")
    m.opener = boom
    m.urllib.request.urlopen = boom
    m.fetch = lambda tour, force=False: "<html>probe</html>"
    m.parse = lambda hml: (HDR, [{"g": 1}, {"g": 2}])
    m.to_csv = lambda games, cfg: (HDR, [FAKE_ROW])
    leaks = [k for k in ("CACHE", "HTML_DIR", "PB_DIR") if os.path.abspath(getattr(m, k)).startswith(os.path.join(ROOT, "csv_cache"))]
    return leaks


WCFG = {"tour": CFG["wiki"], "league": "ZZ", "split": "S9", "year": YEAR, "playoffs": 0, "key": KEY}


def run_writes(mf, mw):
    for p in (fill_p, wp):
        if os.path.exists(p):
            os.remove(p)
    buf = io.StringIO()
    sys.stdout = buf
    try:
        t = mf.build(dict(CFG))
        t_real = time.time()
        tw = mw.build(dict(WCFG), force=True)
    finally:
        sys.stdout = _STDOUT
    blk = json.load(open(fill_p, encoding="utf-8")).get(KEY, {}) if os.path.exists(fill_p) else {}
    wb = json.load(open(wp, encoding="utf-8")).get(KEY, {}) if os.path.exists(wp) else {}
    return t, tw, blk, wb, t_real


ffw = load("fetch_fill_m211w", os.path.join(HERE, "fetch_fill.py"))
bind_write(ffw)
fww = load("fetch_wiki_mh_m211w", os.path.join(HERE, "fetch_wiki_mh.py"))
leaks_w = bind_wiki_write(fww)
ck(not leaks_w, f"fetch_wiki_mh 模組層路徑改指沙盒（漏：{leaks_w}）")
t, tw, blk, wb, t_real = run_writes(ffw, fww)
ck(t is not None and blk.get("fetched_at") == CLOCK[0], f"fetch_fill.build() 寫進沙盒 fill JSON 的 block 帶 fetched_at＝假時鐘（實際 {blk.get('fetched_at')}）")
ck(blk.get("src") == "gol.gg" and blk.get("rows") == [FAKE_ROW] and blk.get("gkeys") and blk.get("games") == [7], "fill block 其餘欄位照舊（src／rows／gkeys／games）")
ck(tw is not None and isinstance(wb.get("fetched_at"), float) and abs(wb["fetched_at"] - t_real) < 60,
   f"fetch_wiki_mh.build() 寫進沙盒 wikifill JSON 的 block 帶 fetched_at＝真時鐘（實際 {wb.get('fetched_at')}）")
ck(wb.get("games") == 2 and str(wb.get("src", "")).startswith("leaguepedia") and wb.get("rows") == [FAKE_ROW], "wiki block 其餘欄位照舊（games／src／rows）")
ck(ffw._last_fetch(blk, 0.0) == CLOCK[0] and ffw._last_fetch({"fetched_at": "x"}, 5.0) == 5.0 and ffw._last_fetch(None, 7.0) == 7.0,
   "_last_fetch：蓋過章的 block 回 fetched_at；垃圾／None 回 mtime")
# 蓋章後的 block 拿給 quiet_skip：剛抓完 ⇒ 0 小時 ⇒ 跳過；把時鐘撥 43h（檔案 mtime 也蓋成當下）⇒ 到期
d = json.load(open(fill_p, encoding="utf-8")); d[KEY]["rows"] = [[c for c in FAKE_ROW]]; json.dump(d, open(fill_p, "w", encoding="utf-8"), ensure_ascii=False)
os.utime(fill_p, (CLOCK[0], CLOCK[0])); os.utime(wp, (CLOCK[0], CLOCK[0]))
wb_all = json.load(open(wp, encoding="utf-8")); wb_all[KEY]["fetched_at"] = CLOCK[0]; json.dump(wb_all, open(wp, "w", encoding="utf-8"), ensure_ascii=False)
os.utime(wp, (CLOCK[0], CLOCK[0]))
rc, out, calls = run(ff)
ck(calls == [] and "0 小時前" in out, f"真程式蓋的章拿給 quiet_skip：剛抓完 ⇒ 跳過（實際 {calls}）")
CLOCK[0] = T0 + 43 * 3600
os.utime(fill_p, (CLOCK[0], CLOCK[0])); os.utime(wp, (CLOCK[0], CLOCK[0]))
rc, out, calls = run(ff)
ck(calls == ["warm", "build", "wiki"] and "43 小時前" in out, f"時鐘撥 43h、檔案又被重寫成當下 ⇒ 仍照 block 到期重抓（實際 {calls}）")
CLOCK[0] = T0

print(f"\n【12】正控制（{OLDREV2}，#211 改動前）")
old2 = subprocess.run(["git", "-C", ROOT, "show", f"{OLDREV2}:scripts/fetch_fill.py"], capture_output=True).stdout
old2w = subprocess.run(["git", "-C", ROOT, "show", f"{OLDREV2}:scripts/fetch_wiki_mh.py"], capture_output=True).stdout
ck(len(old2) > 1000 and b"quiet_skip" in old2 and b"fetched_at" not in old2, "OLDREV2 的 fetch_fill 拉得出來：有 quiet_skip、沒有 fetched_at")
ck(len(old2w) > 1000 and b"fetched_at" not in old2w, "OLDREV2 的 fetch_wiki_mh 拉得出來：沒有 fetched_at")
od2 = tempfile.mkdtemp(prefix="m211_old_")
op2 = os.path.join(od2, "fetch_fill_m211old.py")
open(op2, "wb").write(old2)
op2w = os.path.join(od2, "fetch_wiki_mh_m211old.py")
open(op2w, "wb").write(old2w)
fo2 = load("fetch_fill_m211old", op2)
leaks2 = bind(fo2)
ck(not leaks2, f"舊版模組層路徑也改指沙盒（漏：{leaks2}）")
seed(newest_days_ago=30, fill_age_h=1, wiki_age_h=1)
stamp("fill", 50); stamp("wikifill", 50)
rc, out, calls = run(fo2)
ck(calls == [], f"舊版只看共用檔 mtime 1h ⇒ 明明 50h 沒抓也跳過（實際 {calls}）")
n_old_sh = timeline_shared(fo2)
ck(n_old_sh == 0, f"舊版在「共用檔每班被別的 key 重寫」的 8 班裡 0 次複查（實際 {n_old_sh}）＝#211 要修的洞")
fo2w = load("fetch_fill_m211oldw", op2)
bind_write(fo2w)
fo2ww = load("fetch_wiki_mh_m211oldw", op2w)
bind_wiki_write(fo2ww)
t, tw, blk, wb, t_real = run_writes(fo2w, fo2ww)
ck(t is not None and "fetched_at" not in blk and blk.get("src") == "gol.gg", "舊版 fetch_fill.build() 寫的 block 沒有 fetched_at（其餘照寫）")
ck(tw is not None and "fetched_at" not in wb and wb.get("games") == 2, "舊版 fetch_wiki_mh.build() 寫的 block 沒有 fetched_at（其餘照寫）")
if _saved_fd is None:
    sys.modules.pop("fetch_data", None)
else:
    sys.modules["fetch_data"] = _saved_fd
shutil.rmtree(od2, ignore_errors=True)

print("\n【9】真實檔案沒動")
ck(stat_real() == REAL0, "真實 csv_cache/fill_2026.json、wikifill_2026.json size＋mtime_ns 沒動")
shutil.rmtree(SB, ignore_errors=True)
shutil.rmtree(od, ignore_errors=True)

print(f"\n合計 {OKN[0]} 條：✓ {OKN[0] - len(FAIL)}／✗ {len(FAIL)}")
for f in FAIL:
    print("  ✗ " + f)
sys.exit(1 if FAIL else 0)
