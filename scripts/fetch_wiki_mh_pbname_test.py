# -*- coding: utf-8 -*-
"""fetch_wiki_mh.pb_orders 隊名要解 HTML 實體的沙盒測試（2026-09-17 精進迴圈 #172）。

背景：Leaguepedia 的 Picks and Bans 頁把隊伍 logo 的 alt 寫成「Anyone&#39;s Legendlogo std」。
pb_orders 的區域變數叫 html、把模組蓋掉了所以沒有 unescape ⇒ to_csv 的 PB 補局（MH 沒有、PB 有的局）
寫出「Anyone&#39;s Legend」這支隊伍；to_csv 的 align() 用 nk 對 OE 寫法也對不上（anyone39slegend），
08-12～08-15、08-24～08-25 上線的 data_2026.js 裡 AL 被拆成兩隊。同一份頁面的 pb_list 早就有 unescape。

沙盒接管的證據來源／出口：
  fetch_wiki_mh（新版與舊版各一份）：pb_page（唯一的頁面來源，換成回傳沙盒素材）、_OP（網路出口，換成一叫就記帳並炸掉的假 opener）、
                 _PNAME（選手名對照，設成空的 ⇒ 不去讀 data/data_*.js）、
                 模組層所有指著真實 repo 的字串（HERE／ROOT／CACHE／HTML_DIR／PB_DIR…）全改指暫存目錄，並 assert 一個不剩
  fetch_fill   ：to_csv 內部 import 的模組 ⇒ sys.modules 換成假模組（最小表頭、空對照），不讀任何 CSV
素材：真實 csv_cache/wikipb 裡 alt 含「&#39;」的 PB 頁（lpl_2026_split_3.html 優先，真實版型）。
只有沙盒才有的證據：素材裡的「Anyone&#39;s Legend」全換成「Zzsandbox&#39;s Probe」——真 repo 不可能有，
      新版吐得出「Zzsandbox's Probe」＝它真的讀了沙盒那份。
正控制：OLDREV＝引入本改動之前的 commit；舊版對同一份素材必須吐出「Zzsandbox&#39;s Probe」（這支測試抓得到那個病），
      且新舊兩版的局鍵／選禁／版本逐局相同（只改隊名、沒動別的）。
"""
import hashlib, html, importlib.util, io, os, shutil, subprocess, sys, tempfile, types

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
REAL = os.path.dirname(HERE)
sys.path.insert(0, HERE)
OLDREV = "0079138c"        # 引入本改動之前的 commit（#93：不可以寫 HEAD）

import fetch_wiki_mh as MH

OK = FAIL = 0
PROBE_RAW, PROBE = "Zzsandbox&#39;s Probe", "Zzsandbox's Probe"


def check(name, cond, extra=""):
    global OK, FAIL
    if cond:
        OK += 1; print(f"  ✓ {name}")
    else:
        FAIL += 1; print(f"  ✗ {name}  {extra}")


REAL_PB = MH.PB_DIR
stat_dir = lambda d: sorted((f, os.stat(os.path.join(d, f)).st_size, os.stat(os.path.join(d, f)).st_mtime_ns)
                            for f in os.listdir(d))
BEFORE = stat_dir(REAL_PB)

# ── 素材 ───────────────────────────────────────────────────────
cands = ["lpl_2026_split_3.html"] + sorted(os.listdir(REAL_PB))
SRC = next((f for f in cands if os.path.exists(os.path.join(REAL_PB, f))
            and "&#39;" in "".join(__import__("re").findall(r'alt="([^"]+?)logo std"',
                                                            io.open(os.path.join(REAL_PB, f), encoding="utf-8").read()))),
           None)
print("[1] 素材")
check("1a 找得到 alt 含 &#39; 的真實 PB 頁", SRC is not None)
if SRC is None:
    sys.exit(1)
REAL_HTML = io.open(os.path.join(REAL_PB, SRC), encoding="utf-8").read()
N_AL = REAL_HTML.count("Anyone&#39;s Legendlogo std")
check("1b 素材裡有「Anyone&#39;s Legendlogo std」", N_AL > 0, SRC)
SAND_HTML = REAL_HTML.replace("Anyone&#39;s Legend", PROBE_RAW)
check("1c 探針隊名換進去了、原名一個不剩", SAND_HTML.count(PROBE_RAW + "logo std") == N_AL
      and "Anyone&#39;s Legend" not in SAND_HTML)

TMP = tempfile.mkdtemp(prefix="m172_pbname_")
CALLS = []


class BoomOpener:
    def open(self, *a, **k):
        CALLS.append(a)
        raise RuntimeError("沙盒：不准打網路")


def sandbox(mod):
    """把模組層每一個指著真實 repo 的字串改指暫存目錄，換掉頁面來源與網路出口。"""
    for k, v in list(vars(mod).items()):
        if isinstance(v, str) and os.path.normcase(REAL) in os.path.normcase(v):
            setattr(mod, k, os.path.join(TMP, "redir_" + k))
    mod.pb_page = lambda tour, force=False, tries=3: SAND_HTML
    mod._OP = BoomOpener()
    mod._PNAME = {}
    left = [k for k, v in vars(mod).items() if isinstance(v, str) and os.path.normcase(REAL) in os.path.normcase(v)]
    return left


# ── 舊版：釘 OLDREV ─────────────────────────────────────────────
old_src = subprocess.run(["git", "show", f"{OLDREV}:scripts/fetch_wiki_mh.py"], cwd=REAL, capture_output=True).stdout
old_dir = os.path.join(TMP, "old")
os.makedirs(old_dir)
io.open(os.path.join(old_dir, "fetch_wiki_mh_old.py"), "wb").write(old_src)
spec = importlib.util.spec_from_file_location("fetch_wiki_mh_old", os.path.join(old_dir, "fetch_wiki_mh_old.py"))
OLD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(OLD)

print("[2] 沙盒隔離")
check("2a 新版模組層沒有字串還指著真實 repo", sandbox(MH) == [])
check("2b 舊版模組層沒有字串還指著真實 repo", sandbox(OLD) == [])
check("2c 舊版真的是舊的（pb_orders 裡還是 html = pb_page）",
      b"    html = pb_page(tour, force=force, tries=tries)" in old_src and len(old_src) > 10000)

try:
    NEW_PB, OLD_PB = MH.pb_orders("sandbox"), OLD.pb_orders("sandbox")
    names = lambda PB: [m[k] for m in PB.values() for k in ("t1", "t2", "win")]

    print("[3] pb_orders（新版）")
    check("3a 解得出局（≥5）", len(NEW_PB) >= 5, len(NEW_PB))
    check("3b 探針隊名解成「Zzsandbox's Probe」（讀的是沙盒素材）", PROBE in names(NEW_PB))
    bad = sorted({n for n in names(NEW_PB) if "&#" in n or "&amp;" in n or "&quot;" in n})
    check("3c 隊名／勝方沒有任何 HTML 實體殘留", bad == [], bad)

    print("[4] 正控制：舊版（%s）" % OLDREV)
    check("4a 舊版同一份素材吐出「Zzsandbox&#39;s Probe」（這支測試抓得到那個病）", PROBE_RAW in names(OLD_PB))
    check("4b 新舊局鍵一模一樣", set(NEW_PB) == set(OLD_PB), (len(NEW_PB), len(OLD_PB)))
    same = all(NEW_PB[k]["p"] == OLD_PB[k]["p"] and NEW_PB[k]["b"] == OLD_PB[k]["b"]
               and NEW_PB[k]["patch"] == OLD_PB[k]["patch"] for k in NEW_PB if k in OLD_PB)
    check("4c 新舊選／禁／版本逐局相同（只改隊名）", same)
    check("4d 新版隊名＝html.unescape(舊版隊名)，逐局逐欄", all(
        NEW_PB[k][f] == html.unescape(OLD_PB[k][f]) for k in NEW_PB if k in OLD_PB for f in ("t1", "t2", "win")))

    # ── to_csv 端到端：PB 補局那條路（實際寫出 teamname 的地方）──────────────
    HDR = (["gameid", "datacompleteness", "league", "year", "split", "playoffs", "date", "game", "patch",
            "participantid", "firstPick", "side", "position", "playername", "teamname", "champion", "result",
            "gamelength", "teamkills", "teamdeaths"] + [f"ban{i}" for i in range(1, 6)]
           + [f"pick{i}" for i in range(1, 6)] + ["totalgold", "towers", "dragons", "barons", "heralds", "void_grubs"])
    FF = types.ModuleType("fetch_fill")
    FF.oe_header = lambda: list(HDR)
    FF.oe_names = lambda year, league: ({}, {}, {})
    saved_ff = sys.modules.get("fetch_fill")
    sys.modules["fetch_fill"] = FF

    def run_csv(mod, PB):
        chrono = list(PB.items())[::-1]
        # MH 那一局挑時間序最早、而且兩隊都不是探針隊的 ⇒ 探針隊的列只可能來自 PB 補局
        k, m = next(((k, m) for k, m in chrono if PROBE not in html.unescape(m["t1"] + m["t2"])), chrono[0])
        g = {"Date": "2026-08-01 10:00:00", "Blue": html.unescape(m["t1"]), "Red": html.unescape(m["t2"]),
             "Winner": html.unescape(m["win"]), "P": m["patch"], "Picks": ",".join(m["p"][0]),
             "Picks2": ",".join(m["p"][1]), "Bans": ",".join(m["b"][0]), "Bans2": ",".join(m["b"][1]),
             "Blue Roster": "a,b,c,d,e", "Red Roster": "f,g,h,i,j", "Len": "30:00"}
        cfg = {"tour": "sandbox", "league": "LPL", "split": "Split 3", "year": 2026, "key": "SANDBOX", "playoffs": 0}
        buf = io.StringIO()
        _o, sys.stdout = sys.stdout, buf
        try:
            hdr, rows = mod.to_csv([g], cfg)
        finally:
            sys.stdout = _o
        it, ir = hdr.index("teamname"), hdr.index("result")
        return [(r[it], r[ir]) for r in rows], buf.getvalue()

    try:
        new_rows, new_out = run_csv(MH, NEW_PB)
        old_rows, old_out = run_csv(OLD, OLD_PB)
    finally:
        if saved_ff is None:
            sys.modules.pop("fetch_fill", None)
        else:
            sys.modules["fetch_fill"] = saved_ff

    print("[5] to_csv 端到端（PB 補局寫出的 teamname）")
    check("5a 真的走到 PB 補局（印出「PB 補局」且列數 > 12）", "PB 補局" in new_out and len(new_rows) > 12,
          (len(new_rows), new_out[:120]))
    tn_new = {t for t, _ in new_rows}
    tn_old = {t for t, _ in old_rows}
    check("5b 新版 teamname 有「Zzsandbox's Probe」", PROBE in tn_new)
    check("5c 新版 teamname 沒有任何 HTML 實體", not any("&#" in t or "&amp;" in t for t in tn_new),
          sorted(t for t in tn_new if "&" in t))
    check("5d 正控制：舊版 teamname 有「Zzsandbox&#39;s Probe」（拆隊那個病）", PROBE_RAW in tn_old)
    check("5e 新舊列數相同", len(new_rows) == len(old_rows), (len(new_rows), len(old_rows)))
    wins = lambda rows, name: sum(1 for t, r in rows if t == name and r == "1")
    check("5f 探針隊的勝場新舊一樣多（勝負判定沒被改到）", wins(new_rows, PROBE) == wins(old_rows, PROBE_RAW)
          and wins(new_rows, PROBE) > 0, (wins(new_rows, PROBE), wins(old_rows, PROBE_RAW)))
    nk = lambda s: __import__("re").sub(r"[^0-9a-z]", "", str(s or "").lower())
    check("5g 解碼後 nk 對得上 OE 寫法（Anyone's Legend → anyoneslegend）；舊寫法對不上",
          nk(html.unescape("Anyone&#39;s Legend")) == nk("Anyone's Legend") != nk("Anyone&#39;s Legend"))
finally:
    print("[6] 出口")
    check("6a 網路出口一次都沒被叫", CALLS == [], len(CALLS))
    check("6b 真實 csv_cache/wikipb 檔名／大小／mtime 一個沒動", stat_dir(REAL_PB) == BEFORE)
    shutil.rmtree(TMP, ignore_errors=True)

print(f"\n合計 {OK} 過／{FAIL} 失敗")
sys.exit(1 if FAIL else 0)
