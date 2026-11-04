# -*- coding: utf-8 -*-
"""最新兩版每班重抓官方頁（精進迴圈 #2550）：期中更新要進快取，頁面壞掉不可以洗掉快取。
素材是真實頁面 csv_cache/patch_html/{en,zh}/26.21.html（en 那份含 October 22 Updates 的 Varus）。
沙盒接管 HERE／CACHE／_TR_CACHE_PATH／fetch／urlopen，跑完核對正本一個位元沒動。
正控制：REFRESH_LATEST=0 與釘住的舊版（OLDREV）都要收不到更新。"""
import glob, hashlib, importlib.util, io, json, os, shutil, subprocess, sys, tempfile

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import urllib.request  # noqa: E402
import fetch_patches as fp  # noqa: E402
import fetch_patches_en as fe  # noqa: E402

OLDREV = "30b34bbb"  # #2550 的前一個 commit
REAL_CACHE = os.path.join(ROOT, "csv_cache")
EN_URL = "https://www.leagueoflegends.com/en-us/news/game-updates/league-of-legends-patch-26-{}-notes/"
ZH_URL = "https://www.leagueoflegends.com/zh-tw/news/game-updates/league-of-legends-patch-26-{}-notes/"
fails = 0


def check(name, cond, info=""):
    global fails
    fails += not cond
    print(("✓" if cond else "✗"), name, "" if cond else f"\n   {info}")


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


def rd(p):
    return io.open(p, encoding="utf-8").read()


WATCH = [os.path.join(ROOT, "patches.js"), os.path.join(ROOT, "patches_en.js"), os.path.join(REAL_CACHE, "patch_26.21.json"),
         os.path.join(REAL_CACHE, "patch_en_26.21.json"), os.path.join(REAL_CACHE, "patch_html", "en", "26.21.html"),
         os.path.join(REAL_CACHE, "patch_html", "zh", "26.21.html"), os.path.join(REAL_CACHE, "patch_tr_cache.json")]
BEFORE = {p: md5(p) for p in WATCH}
REAL_FETCH, REAL_OPEN = fp.fetch, urllib.request.urlopen
PAGES, CALLS, ESCAPED = {}, [], []


def fake_fetch(u):
    CALLS.append(u)
    if u not in PAGES:
        raise OSError("404 " + u)
    v = PAGES[u]
    if isinstance(v, Exception):
        raise v
    return v


def fake_open(req, *a, **k):
    ESCAPED.append(getattr(req, "full_url", req))
    raise OSError("沙盒不連網")


urllib.request.urlopen = fake_open


def bind(mod, sb):
    mod.HERE = sb
    mod.CACHE = os.path.join(sb, "csv_cache")
    if hasattr(mod, "_TR_CACHE_PATH"):
        mod._TR_CACHE_PATH = os.path.join(mod.CACHE, "patch_tr_cache.json")
        mod._TR_MEMO = None
        mod._TR_DIRTY[0] = False
    if hasattr(mod, "_LIKELY_IDX"):
        mod._LIKELY_IDX.clear()
    for g in ("_ITEM_NAMES", "_RUNE_NAMES", "_MANUAL_TR"):
        if hasattr(mod, g):
            setattr(mod, g, None)
    for v in (mod.HERE, mod.CACHE, getattr(mod, "_TR_CACHE_PATH", sb)):
        assert not os.path.abspath(v).startswith(os.path.abspath(ROOT) + os.sep), f"路徑還指著真實 repo：{v}"
    mod.fetch = fake_fetch
    mod.target_patches = lambda: [(2026, 20), (2026, 21), (2026, 22)]
    mod.discover_urls = lambda force=False: {}
    mod.item_debuts = lambda: {}
    mod.item_removals = lambda: ({}, {}, {})


def sandbox():
    sb = tempfile.mkdtemp(prefix="m2550_")
    os.makedirs(os.path.join(sb, "csv_cache"))
    os.makedirs(os.path.join(sb, "scripts"))
    for fn in ("assets.js", "rune_icons.js", "items.js"):
        if os.path.exists(os.path.join(ROOT, fn)):
            shutil.copy2(os.path.join(ROOT, fn), sb)
    for fn in ("manual_tr.json", "item_name_fix.json", "tr_fix.json"):
        if os.path.exists(os.path.join(HERE, fn)):
            shutil.copy2(os.path.join(HERE, fn), os.path.join(sb, "scripts"))
    # parse() 的道具區靠這些名單判斷，少了解析結果會跟素材不同（⑥⑧ 會變假綠、③ 會假紅）
    for pat in ("item_*.json", "champ_slugs.json", "items_st_zhtw.json"):
        for f in glob.glob(os.path.join(REAL_CACHE, pat)):
            shutil.copy2(f, os.path.join(sb, "csv_cache"))
    bind(fp, sb)
    CALLS.clear()
    PAGES.clear()
    return sb


def wr(sb, name, d):
    p = os.path.join(sb, "csv_cache", name)
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    return p


def quiet(f, *a):
    buf, so = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        return f(*a), buf.getvalue()
    finally:
        sys.stdout = so


EN_HTML = rd(os.path.join(REAL_CACHE, "patch_html", "en", "26.21.html"))
ZH_HTML = rd(os.path.join(REAL_CACHE, "patch_html", "zh", "26.21.html"))
sandbox()  # 素材也在沙盒解析：parse() 的道具區看名單，要跟後面每一趟同一份環境
EN_FULL = json.loads(json.dumps(fp.parse(EN_HTML), ensure_ascii=False))
ZH_FULL = json.loads(json.dumps(fp.parse(ZH_HTML), ensure_ascii=False))
check("素材：真實英文頁解析得到 Varus 的期中更新（被動與 Q）",
      sum("Varus" in k for k in EN_FULL) == 1 and len(EN_FULL.get("Varus", [])) >= 2, list(EN_FULL.get("Varus", [])))
check("素材：真實繁中頁解析 ≥ 5 隻英雄", sum(not k.startswith("_") for k in ZH_FULL) >= 5)

STALE = dict(EN_FULL)
STALE["Varus"] = EN_FULL["Varus"][:-2]  # 模擬快取在期中更新之前寫下
if not STALE["Varus"]:
    del STALE["Varus"]
ZH_CHAMP = next(k for k, v in ZH_FULL.items() if not k.startswith("_") and isinstance(v, list) and len(v) >= 2)
ZH_STALE = dict(ZH_FULL)
ZH_STALE[ZH_CHAMP] = ZH_FULL[ZH_CHAMP][:-1]

# ── latest_cached ──
sb = sandbox()
for n in ("patch_26.09", "patch_26.10", "patch_26.22", "patch_26.21", "patch_tr_cache", "patch_en_26.23", "patch_dates", "patch_19.01"):
    wr(sb, n + ".json", {})
check("① 取版本最新的 2 個，不算 patch_en_／非版本檔", fp.latest_cached("patch_") == {"26.21", "26.22"}, fp.latest_cached("patch_"))
check("① prefix＝patch_en_ 只看英文", fp.latest_cached("patch_en_") == {"26.23"})
check("① n=0 ⇒ 空集合", fp.latest_cached("patch_", 0) == set())
wr(sb, "patch_27.01.json", {})
check("① 跨年 27.01 排最新", fp.latest_cached("patch_") == {"26.22", "27.01"}, fp.latest_cached("patch_"))

# ── refresh_cached 單元 ──
sb = sandbox()
c = dict(STALE, _url=EN_URL.format(21))
cf = wr(sb, "patch_en_26.21.json", c)
PAGES[c["_url"]] = EN_HTML
got, log = quiet(fp.refresh_cached, "26.21", c, cf, "en")
disk = json.load(open(cf, encoding="utf-8"))
check("② 期中更新 ⇒ Varus 補回", got.get("Varus") == EN_FULL["Varus"] and disk.get("Varus") == EN_FULL["Varus"], got.get("Varus"))
check("② 期中更新 ⇒ _url 留著", disk.get("_url") == c["_url"])
check("② 期中更新 ⇒ 頁面快取同步（reparse 才不會改回去）", rd(os.path.join(sb, "csv_cache", "patch_html", "en", "26.21.html")) == EN_HTML)
check("② 日誌有說換了", "官方頁有更新" in log, log)
check("② 只發一次請求", CALLS == [c["_url"]], CALLS)

sb = sandbox()
c = dict(ZH_FULL, _url=ZH_URL.format(21), _lang="zh-tw")
cf = wr(sb, "patch_26.21.json", c)
os.utime(cf, (1000000000, 1000000000))
PAGES[c["_url"]] = ZH_HTML
got, log = quiet(fp.refresh_cached, "26.21", c, cf, "zh")
check("③ 內容相同 ⇒ 不寫檔、不寫頁面、不出聲", os.path.getmtime(cf) == 1000000000 and got is c and not log
      and not os.path.exists(os.path.join(sb, "csv_cache", "patch_html")), log)

sb = sandbox()
c = dict(ZH_STALE, _url=ZH_URL.format(21), _lang="zh-tw")
cf = wr(sb, "patch_26.21.json", c)
PAGES[c["_url"]] = ZH_HTML
got, log = quiet(fp.refresh_cached, "26.21", c, cf, "zh")
check("③ 繁中有新行 ⇒ _lang 留著", json.load(open(cf, encoding="utf-8")).get("_lang") == "zh-tw" and got[ZH_CHAMP] == ZH_FULL[ZH_CHAMP])

for label, page, cached_extra, warn in (
    ("④ 抓不到（連線失敗）", OSError("boom"), {}, "失敗"),
    ("⑤ 版型變了解析 0 隻", "<html><body>nothing</body></html>", {}, "解析 0"),
    ("⑥ 少一隻英雄（快取有 ZzProbe）", EN_HTML, {"ZzProbe": ["x ⇒ y"]}, "比快取少"),
    ("⑦ 同一隻行數變少", EN_HTML, {"Varus": EN_FULL["Varus"] + ["多一行 1 ⇒ 2"]}, "比快取少"),
    ("⑧ 區塊整段不見", EN_HTML, {"_extra": dict(EN_FULL.get("_extra") or {}, 探針區=["a ⇒ b"])}, "比快取少"),
):
    sb = sandbox()
    c = dict(EN_FULL, _url=EN_URL.format(21), **cached_extra)
    cf = wr(sb, "patch_en_26.21.json", c)
    before = rd(cf)
    PAGES[c["_url"]] = page
    got, log = quiet(fp.refresh_cached, "26.21", c, cf, "en")
    check(label + " ⇒ 快取一個字不動", rd(cf) == before and got is c, log)
    check(label + " ⇒ 有印原因", warn in log, log)
    check(label + " ⇒ 不寫頁面快取", not os.path.exists(os.path.join(sb, "csv_cache", "patch_html")))

sb = sandbox()
c = {"Varus": ["x"]}
cf = wr(sb, "patch_en_26.21.json", c)
got, log = quiet(fp.refresh_cached, "26.21", c, cf, "en")
check("⑨ 沒有 _url ⇒ 不發請求", not CALLS and got is c)

# ── fetch_patches_en.main 整合 ──
def run_en(refresh):
    sb = sandbox()
    fp.REFRESH_LATEST = refresh
    wr(sb, "patch_en_26.20.json", {"Ahri": ["舊版 1 ⇒ 2"], "_url": EN_URL.format(20)})
    wr(sb, "patch_en_26.21.json", dict(STALE, _url=EN_URL.format(21)))
    wr(sb, "patch_en_26.22.json", dict(EN_FULL, _url=EN_URL.format(22)))
    PAGES[EN_URL.format(21)] = EN_HTML
    PAGES[EN_URL.format(22)] = EN_HTML
    old_argv, sys.argv = sys.argv, ["fetch_patches_en.py"]
    try:
        _, log = quiet(fe.main)
    finally:
        sys.argv = old_argv
    js = rd(os.path.join(sb, "patches_en.js"))
    return json.loads(js[js.index("=") + 1:].rstrip().rstrip(";")), list(CALLS), log


out, calls, log = run_en(2)
check("⑩ 英文 main：只重抓最新兩版，26.20 沒發請求", sorted(calls) == sorted([EN_URL.format(21), EN_URL.format(22)]), calls)
check("⑩ 英文 main：patches_en.js 有 Varus 期中更新", out["26.21"].get("Varus") == EN_FULL["Varus"], out["26.21"].get("Varus"))
check("⑩ 英文 main：26.20 原樣輸出", out["26.20"].get("Ahri") == ["舊版 1 ⇒ 2"])
out, calls, log = run_en(0)
check("⑩ 正控制 REFRESH_LATEST=0：0 次請求、Varus 還是舊的", not calls and out["26.21"].get("Varus") != EN_FULL["Varus"], calls)
fp.REFRESH_LATEST = 2


# ── fetch_patches.main 整合 ──
def run_zh(mod, refresh=2):
    sb = sandbox()
    bind(mod, sb)
    mod.REFRESH_LATEST = refresh
    wr(sb, "patch_26.20.json", {"Ahri": ["舊 1 ⇒ 2"], "_url": ZH_URL.format(20), "_lang": "zh-tw"})
    wr(sb, "patch_26.21.json", dict(ZH_STALE, _url=ZH_URL.format(21), _lang="zh-tw"))
    wr(sb, "patch_26.22.json", dict(EN_FULL, _url=EN_URL.format(22), _lang="en-us"))  # 英文暫代的最新版
    PAGES[ZH_URL.format(21)] = ZH_HTML
    PAGES[EN_URL.format(22)] = EN_HTML
    old_argv, sys.argv = sys.argv, ["fetch_patches.py", "--skip-discover"]
    try:
        _, log = quiet(mod.main)
    finally:
        sys.argv = old_argv
    return sb, json.load(open(os.path.join(sb, "csv_cache", "patch_26.21.json"), encoding="utf-8")), list(CALLS), log


sb, disk, calls, log = run_zh(fp)
check("⑪ 繁中 main：最新版之一 26.21 收到新行", disk.get(ZH_CHAMP) == ZH_FULL[ZH_CHAMP], disk.get(ZH_CHAMP))
check("⑪ 繁中 main：沒有對 26.20 發請求", ZH_URL.format(20) not in calls, calls)
check("⑪ 繁中 main：英文暫代的 26.22 不走重抓（沒抓它自己的 en-us 網址當更新）",
      "官方頁有更新 → 快取已換（zh）" in log and log.count("官方頁有更新") == 1, log)
check("⑪ 繁中 main：英文暫代 26.22 照舊重試繁中", "26.22: 快取為英文公告" in log, log)
_pj = rd(os.path.join(sb, "patches.js"))
_new_line = ZH_FULL[ZH_CHAMP][-1]
check("⑪ 繁中 main：patches.js 有這隻英雄補回的那一行", _new_line[-12:] in _pj, _new_line)

sb, disk, calls, log = run_zh(fp, 0)
check("⑫ 正控制 REFRESH_LATEST=0：26.21 沒發請求、還是舊的", ZH_URL.format(21) not in calls and disk.get(ZH_CHAMP) != ZH_FULL[ZH_CHAMP], calls)
fp.REFRESH_LATEST = 2

# 跨年：26.22 變去年的版本，但快取裡仍是最新兩版之一；它的英雄行是翻過的，不能拿英文原文蓋
_ny = fp.NOW_YEAR
fp.NOW_YEAR = 2027
sb, disk, calls, log = run_zh(fp)
fp.NOW_YEAR = _ny
_d22 = json.load(open(os.path.join(sb, "csv_cache", "patch_26.22.json"), encoding="utf-8"))
check("⑫b 跨年：去年的英文暫代版不重抓、不重試", EN_URL.format(22) not in calls and "26.22: 快取為英文公告" not in log, calls)
check("⑫b 跨年：去年的英文暫代版快取還是 en-us", _d22.get("_lang") == "en-us")
check("⑫b 對照：同一趟 26.21（繁中）照樣重抓", ZH_URL.format(21) in calls, calls)

src = subprocess.run(["git", "show", OLDREV + ":scripts/fetch_patches.py"], cwd=ROOT, capture_output=True).stdout
check("⑬ 釘住的舊版拿得到", b"def main" in src and b"refresh_cached" not in src)
tp = os.path.join(tempfile.mkdtemp(prefix="m2550_old_"), "old_fetch_patches.py")
open(tp, "wb").write(src)
spec = importlib.util.spec_from_file_location("old_fetch_patches", tp)
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
sb, disk, calls, log = run_zh(old)
check(f"⑬ 正控制 舊版（{OLDREV}）：同一份素材收不到新行", disk.get(ZH_CHAMP) != ZH_FULL[ZH_CHAMP] and ZH_URL.format(21) not in calls, calls)

urllib.request.urlopen = REAL_OPEN
for p in WATCH:
    check("⑭ 正本沒動：" + os.path.basename(p), md5(p) == BEFORE[p])
print(f"失敗 {fails}")
sys.exit(1 if fails else 0)
