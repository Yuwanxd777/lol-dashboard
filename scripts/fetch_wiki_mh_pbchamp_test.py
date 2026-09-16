# -*- coding: utf-8 -*-
"""fetch_wiki_mh.pb_orders／pb_list 的英雄名（data-champion）要解 HTML 實體的沙盒測試（2026-09-17 精進迴圈 #173）。

背景：Leaguepedia Picks and Bans 頁的 data-champion 都是小寫英數（kaisa／jarvaniv），只有 Nunu 寫成
「nunu&amp;willump」（真實快取頁 lpl_2017～2020／lms_2018／lcs_2019／opl_2017 共 24 處）。沒解碼 ⇒
pbn 變 nunuampwillump，而 MH 文字版寫「Nunu &amp; Willump」、cells() 解碼後 pbn 是 nunuwillump ⇒ 有 Nunu 的局：
  ① pb_of 對不到 ⇒ 選序退回路線序（假的），2026 起先選方只能猜藍方；fetch_data.fix_draft_wiki 也修不到那局
  ② to_csv 的 PB 補局把「MH 已經有的那局」當成 MH 沒有、再補一次 ⇒ 幽靈重複局，選禁欄寫著 nunu&amp;willump
2026 至今沒人選／禁過 Nunu（data_2026.js 0 次），所以現況 0 局，這是擋下一次。

沙盒接管的證據來源／出口：
  fetch_wiki_mh（新版與舊版各一份）：pb_page（唯一的 PB 頁來源 ⇒ 回傳沙盒素材）、_OP（網路出口 ⇒ 一叫就記帳並炸）、
                 _PNAME（選手名對照 ⇒ 空的，不去讀 data/data_*.js）、
                 模組層所有指著真實 repo 的字串（HERE／ROOT／CACHE／HTML_DIR／PB_DIR…）全改指暫存目錄，並 assert 一個不剩
  fetch_fill   ：to_csv 內部 import 的模組 ⇒ sys.modules 換成假模組（最小表頭；英雄對照由沙盒 MH 局的英雄名生成）
  MH 頁        ：不經 fetch()，直接把沙盒字串丟給 parse()
素材：真實 csv_cache/wikipb/lpl_2026_split_3.html（PB）＋ csv_cache/wikitxt/lpl_2026_split_3.html（MH），167 局兩邊全對得上。
只有沙盒才有的證據：挑一局、把其中一隻英雄在 PB 那一列換成「nunu&amp;willump」、在 MH 那一格換成「Nunu &amp; Willump」
      ——真實 2026 兩份頁面一個 nunu 都沒有，新版解得出 nunu&willump＝它真的讀了沙盒那份。
正控制：OLDREV＝引入本改動之前的 commit；舊版對同一份沙盒必須對不到那局、PB 補局多補 1 局、寫出 nunu&amp;willump
      （這支測試抓得到那個病）；而在**沒注入的真實素材**上新舊兩版逐局完全相同（現況資料不受影響）。
"""
import copy, html, importlib.util, io, os, re, shutil, subprocess, sys, tempfile, types

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
REAL = os.path.dirname(HERE)
sys.path.insert(0, HERE)
OLDREV = "7f9f8a3b"        # 引入本改動之前的 commit（#93：不可以寫 HEAD）

import fetch_wiki_mh as MH

OK = FAIL = 0
RAW_NUNU, DEC_NUNU, MH_NUNU = "nunu&amp;willump", "nunu&willump", "Nunu & Willump"


def check(name, cond, extra=""):
    global OK, FAIL
    if cond:
        OK += 1; print(f"  ✓ {name}")
    else:
        FAIL += 1; print(f"  ✗ {name}  {extra}")


REAL_PB, REAL_TXT = MH.PB_DIR, MH.HTML_DIR
stat_dir = lambda d: sorted((f, os.stat(os.path.join(d, f)).st_size, os.stat(os.path.join(d, f)).st_mtime_ns)
                            for f in os.listdir(d))
BEFORE_PB, BEFORE_TXT = stat_dir(REAL_PB), stat_dir(REAL_TXT)
rd = lambda p: io.open(p, encoding="utf-8").read()
pbn = lambda s: re.sub(r"[^a-z0-9]", "", str(s or "").lower())
SPL = lambda s: [x.strip() for x in str(s or "").split(",") if x.strip()]
PB_T1P, PB_T2P = (12, 14, 21), (13, 15, 20, 22)

# ── [1] 素材 ───────────────────────────────────────────────────────
print("[1] 素材")
PB_SRC, MH_SRC = os.path.join(REAL_PB, "lpl_2026_split_3.html"), os.path.join(REAL_TXT, "lpl_2026_split_3.html")
check("1a 真實 PB 頁與 MH 頁都在", os.path.exists(PB_SRC) and os.path.exists(MH_SRC))
if not (os.path.exists(PB_SRC) and os.path.exists(MH_SRC)):
    sys.exit(1)
REAL_PBH, REAL_MHH = rd(PB_SRC), rd(MH_SRC)
check("1b 真實 2026 兩份頁面沒有任何 nunu（注入後的 nunu 只可能來自沙盒）",
      "nunu" not in REAL_PBH.lower() and "nunu" not in REAL_MHH.lower())
HIST = sorted(f for f in os.listdir(REAL_PB) if f'data-champion="{RAW_NUNU}"' in rd(os.path.join(REAL_PB, f)))
check("1c 真實歷史 PB 快取頁確實把 Nunu 寫成 data-champion=“nunu&amp;willump”（≥1 份）", len(HIST) >= 1, HIST)
odd = sorted({v for f in os.listdir(REAL_PB) for v in re.findall(r'data-champion="([^"]+)"', rd(os.path.join(REAL_PB, f)))
              if re.search(r"[^a-z0-9]", v)})
print(f"    （資訊）全部真實 PB 頁裡不是純小寫英數的 data-champion：{odd}")
TXT_NUNU = next((f for f in sorted(os.listdir(REAL_TXT)) if "Nunu &amp; Willump" in rd(os.path.join(REAL_TXT, f))), None)
_, _hg = MH.parse(rd(os.path.join(REAL_TXT, TXT_NUNU))) if TXT_NUNU else ([], [])
check("1d 真實 MH 頁寫「Nunu &amp; Willump」、parse 解碼成「Nunu & Willump」（MH 側 pbn＝nunuwillump）",
      any(MH_NUNU in SPL(g.get("Picks")) + SPL(g.get("Picks2")) + SPL(g.get("Bans")) + SPL(g.get("Bans2")) for g in _hg),
      TXT_NUNU)


def pb_rows(page):
    """跟 pb_orders 同一套切法 → [(tr 原文, 十隻英雄原始值)]"""
    tbl = [t for t in re.findall(r"<table[^>]*>.*?</table>", page, re.S) if "pbh-cn" in t]
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tbl[0], re.S):
        cs = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)
        if len(cs) < 23 or "pbh-cn" not in tr:
            continue
        ch = lambda i: re.findall(r'data-champion="([^"]+)"', cs[i])
        p = [c for i in PB_T1P + PB_T2P for c in ch(i)]
        if len(p) == 10:
            out.append((tr, p))
    return out


# 挑探針局：MH 那一格原文唯一、PB 那一列裡那隻英雄只出現一次
_, REAL_GAMES = MH.parse(REAL_MHH)
PBR = pb_rows(REAL_PBH)
PROBE = None
for g in REAL_GAMES:
    for side in ("Picks", "Picks2"):
        cell = g.get(side, "")
        for x in SPL(cell):
            key = frozenset(pbn(c) for c in SPL(g.get("Picks")) + SPL(g.get("Picks2")))
            trs = [tr for tr, p in PBR if frozenset(p) == key]
            if len(trs) != 1 or REAL_PBH.count(trs[0]) != 1:
                continue
            if trs[0].count(f'data-champion="{pbn(x)}"') != 1 or REAL_MHH.count(cell) != 1:
                continue
            PROBE = (g, side, x, trs[0], cell)
            break
        if PROBE:
            break
    if PROBE:
        break
check("1e 找得到探針局（MH 格原文唯一、PB 列裡那隻英雄恰好一次）", PROBE is not None)
if PROBE is None:
    sys.exit(1)
PG, PSIDE, PX, PTR, PCELL = PROBE
SAND_PB = REAL_PBH.replace(PTR, PTR.replace(f'data-champion="{pbn(PX)}"', f'data-champion="{RAW_NUNU}"'), 1)
NEW_CELL = ",".join("Nunu &amp; Willump" if c == PX else c for c in SPL(PCELL))
SAND_MH = REAL_MHH.replace(PCELL, NEW_CELL, 1)
check("1f 注入後兩份沙盒各恰好一處 nunu", SAND_PB.count(RAW_NUNU) == 1 and SAND_MH.count("Nunu &amp; Willump") == 1,
      (PX, SAND_PB.count(RAW_NUNU), SAND_MH.count("Nunu &amp; Willump")))
print(f"    探針局：{PG.get('Date')} {PG.get('Blue')} vs {PG.get('Red')}，{PSIDE} 的 {PX} → Nunu & Willump")

TMP = tempfile.mkdtemp(prefix="m173_pbchamp_")
CALLS = []


class BoomOpener:
    def open(self, *a, **k):
        CALLS.append(a)
        raise RuntimeError("沙盒：不准打網路")


PAGE = {"html": SAND_PB}


def sandbox(mod):
    """把模組層每一個指著真實 repo 的字串改指暫存目錄，換掉頁面來源與網路出口。"""
    for k, v in list(vars(mod).items()):
        if isinstance(v, str) and os.path.normcase(REAL) in os.path.normcase(v):
            setattr(mod, k, os.path.join(TMP, "redir_" + k))
    mod.pb_page = lambda tour, force=False, tries=3: PAGE["html"]
    mod._OP = BoomOpener()
    mod._PNAME = {}
    return [k for k, v in vars(mod).items() if isinstance(v, str) and os.path.normcase(REAL) in os.path.normcase(v)]


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
check("2c 舊版真的是舊的（pb_orders 的 ch 沒有 unescape、隊名已有 #172 的 unescape）",
      b"ch = lambda i: re.findall(r'data-champion=\"([^\"]+)\"', cs[i])" in old_src
      and b"html.unescape(c) for c in re.findall" not in old_src and b"Anyone&#39;s Legend" in old_src)

try:
    # ── [3] 沒注入的真實素材：新舊逐局相同（現況資料不受影響）──────────────
    PAGE["html"] = REAL_PBH
    R_NEW, R_OLD = MH.pb_orders("sandbox"), OLD.pb_orders("sandbox")
    RL_NEW, RL_OLD = MH.pb_list("sandbox"), OLD.pb_list("sandbox")
    print("[3] 真實 2026 素材（沒注入）")
    check("3a 解得出 167 局上下（≥100）", len(R_NEW) >= 100, len(R_NEW))
    check("3b pb_orders 新舊逐局完全相同", R_NEW == R_OLD)
    check("3c pb_list 新舊逐局完全相同", RL_NEW == RL_OLD and len(RL_NEW) >= 100)

    # ── [4] 沙盒素材：pb_orders／pb_of ─────────────────────────────────
    PAGE["html"] = SAND_PB
    NEW_PB, OLD_PB = MH.pb_orders("sandbox"), OLD.pb_orders("sandbox")
    _, SG = MH.parse(SAND_MH)
    probe = next((g for g in SG if MH_NUNU in SPL(g.get("Picks")) + SPL(g.get("Picks2"))), None)
    print("[4] pb_orders／pb_of（沙盒）")
    check("4a 沙盒 MH 解得出探針局（Nunu & Willump 在選角欄）", probe is not None)
    blue5, red5 = SPL(probe.get("Picks")), SPL(probe.get("Picks2"))
    vals = lambda PB: [c for m in PB.values() for side in ("p", "b") for grp in m[side] for c in grp]
    check("4b 新版選禁值裡有 nunu&willump（讀的是沙盒）、沒有任何 &amp;／&#",
          DEC_NUNU in vals(NEW_PB) and not any("&amp;" in c or "&#" in c for c in vals(NEW_PB)))
    check("4c 新版局鍵含 nunuwillump、不含 nunuampwillump",
          any("nunuwillump" in k for k in NEW_PB) and not any("nunuampwillump" in k for k in NEW_PB))
    od_new, od_old = MH.pb_of(NEW_PB, blue5, red5), OLD.pb_of(OLD_PB, blue5, red5)
    check("4d 新版 pb_of 對得到探針局、選角裡有 nunu&willump", bool(od_new) and DEC_NUNU in od_new[0] + od_new[1], od_new)
    check("4e 正控制：舊版 pb_of 對不到探針局（這支測試抓得到那個病）", od_old is None, od_old)
    check("4f 正控制：舊版局鍵是 nunuampwillump", any("nunuampwillump" in k for k in OLD_PB))
    others_new = {k: v for k, v in NEW_PB.items() if "nunuwillump" not in k}
    others_old = {k: v for k, v in OLD_PB.items() if "nunuampwillump" not in k}
    check("4g 探針局以外新舊逐局相同、局數相同", others_new == others_old and len(NEW_PB) == len(OLD_PB),
          (len(NEW_PB), len(OLD_PB)))
    check("4h fix_draft_wiki 的正名反查對得上（pbn(nunu&willump)＝pbn(Nunu & Willump)），舊值對不上",
          pbn(DEC_NUNU) == pbn(MH_NUNU) != pbn(RAW_NUNU))

    # ── [5] pb_list（fill_missing_games 用）─────────────────────────────
    L_NEW, L_OLD = MH.pb_list("sandbox"), OLD.pb_list("sandbox")
    lv = lambda L: [c for r in L for f in ("t1p", "t2p", "t1b", "t2b") for c in r[f]]
    print("[5] pb_list（沙盒）")
    check("5a 新版有 nunu&willump、沒有任何實體", DEC_NUNU in lv(L_NEW) and not any("&amp;" in c or "&#" in c for c in lv(L_NEW)))
    check("5b 正控制：舊版吐出 nunu&amp;willump", RAW_NUNU in lv(L_OLD))
    check("5c 新＝unescape(舊)，逐局逐格、局數相同", len(L_NEW) == len(L_OLD) and all(
        a[f] == [html.unescape(c) for c in b[f]] for a, b in zip(L_NEW, L_OLD) for f in ("t1p", "t2p", "t1b", "t2b")))

    # ── [6] to_csv 端到端：PB 補局與選序 ─────────────────────────────────
    HDR = (["gameid", "datacompleteness", "league", "year", "split", "playoffs", "date", "game", "patch",
            "participantid", "firstPick", "side", "position", "playername", "teamname", "champion", "result",
            "gamelength", "teamkills", "teamdeaths"] + [f"ban{i}" for i in range(1, 6)]
           + [f"pick{i}" for i in range(1, 6)] + ["totalgold", "towers", "dragons", "barons", "heralds", "void_grubs"])
    nk = lambda s: re.sub(r"[^0-9a-z]", "", str(s or "").lower())

    def fake_ff(games):
        FF = types.ModuleType("fetch_fill")
        FF.oe_header = lambda: list(HDR)
        champs = {nk(c): c for g in games for f in ("Picks", "Picks2", "Bans", "Bans2") for c in SPL(g.get(f))}
        FF.oe_names = lambda year, league: ({}, {}, dict(champs))      # 英雄對照＝OE 寫法（Nunu & Willump）
        return FF

    def run_csv(mod, mh_html, pb_html):
        PAGE["html"] = pb_html
        _, games = mod.parse(mh_html)
        saved = sys.modules.get("fetch_fill")
        sys.modules["fetch_fill"] = fake_ff(games)
        cfg = {"tour": "sandbox", "league": "LPL", "split": "Split 3", "year": 2026, "key": "SANDBOX", "playoffs": 0}
        buf = io.StringIO()
        _o, sys.stdout = sys.stdout, buf
        try:
            hdr, rows = mod.to_csv(copy.deepcopy(games), cfg)
        finally:
            sys.stdout = _o
            if saved is None:
                sys.modules.pop("fetch_fill", None)
            else:
                sys.modules["fetch_fill"] = saved
        return hdr, rows, buf.getvalue()

    hB, rB, oB = run_csv(MH, REAL_MHH, REAL_PBH)        # 基線：真實素材、新版
    hN, rN, oN = run_csv(MH, SAND_MH, SAND_PB)
    hO, rO, oO = run_csv(OLD, SAND_MH, SAND_PB)
    ix = {h: i for i, h in enumerate(HDR)}
    gids = lambda rows: {r[ix["gameid"]] for r in rows}
    hits = lambda out: int((re.search(r"Picks and Bans 頁對到 (\d+) 局", out) or [0, -1])[1])
    added = lambda out: int((re.search(r"PB 補局：MH 沒有但 PB 有的 (\d+) 局", out) or [0, 0])[1])
    has_ent = lambda rows: any("&amp;" in str(v) or "&#" in str(v) for r in rows for v in r)

    def probe_team(rows):
        g = next((r[ix["gameid"]] for r in rows if r[ix["champion"]] == MH_NUNU), None)
        t = [r for r in rows if r[ix["gameid"]] == g and r[ix["participantid"]] in ("100", "200")]
        return g, {r[ix["participantid"]]: [r[ix[f"pick{i}"]] for i in range(1, 6)] for r in t}

    print("[6] to_csv 端到端")
    check("6a 基線（真實素材）：PB 補局 0、對到 ≥100 局", added(oB) == 0 and hits(oB) >= 100, (added(oB), hits(oB)))
    check("6b 新版沙盒：沒有 PB 補局（不產生幽靈重複局）", added(oN) == 0, oN[-300:])
    check("6c 新版沙盒：對到局數＝基線", hits(oN) == hits(oB), (hits(oN), hits(oB)))
    check("6d 新版沙盒：列數與局數＝基線", len(rN) == len(rB) and len(gids(rN)) == len(gids(rB)),
          (len(rN), len(rB), len(gids(rN)), len(gids(rB))))
    check("6e 新版沙盒：沒有任何欄位帶 HTML 實體", not has_ent(rN))
    gN, tN = probe_team(rN)
    CH = fake_ff(SG).oe_names(0, 0)[2]
    exp = {"100": [CH.get(nk(x), x) for x in od_new[0]], "200": [CH.get(nk(x), x) for x in od_new[1]]} if od_new else {}
    check("6f 新版沙盒：探針局兩方 pick1~5＝PB 真實順序（對齊成 OE 寫法、含 Nunu & Willump）",
          bool(gN) and tN == exp and MH_NUNU in tN.get("100", []) + tN.get("200", []), (tN, exp))
    check("6g 正控制：舊版沙盒 PB 補局多補 1 局", added(oO) == 1, oO[-300:])
    miss = lambda out: int((re.search(r"對不到 (\d+) 局", out) or [0, 0])[1])
    # 舊版「對到」數字不變：真的那局對不到（−1），幽靈局的選角本來就是 PB 值、一定對得到（+1）
    check("6h 正控制：舊版沙盒「對不到 1 局」（真的那局）、新版與基線沒有對不到", miss(oO) == 1 and miss(oN) == 0 == miss(oB),
          (miss(oO), miss(oN), miss(oB)))
    check("6i 正控制：舊版沙盒多出 1 局（2 個隊伍列）", len(gids(rO)) == len(gids(rB)) + 1 and len(rO) == len(rB) + 2,
          (len(gids(rO)), len(rO)))
    check("6j 正控制：舊版沙盒寫出 nunu&amp;willump", any(RAW_NUNU in str(v) for r in rO for v in r))
    gO, tO = probe_team(rO)
    check("6k 正控制：舊版探針局順位退回路線序（MH 的 Picks 原樣）",
          bool(gO) and (tO.get("100") == SPL(probe.get("Picks")) and tO.get("200") == SPL(probe.get("Picks2"))), tO)
    check("6l 探針局的 PB 真實順序跟路線序不同（否則 6f／6k 分不出新舊）", tN != tO, (tN, tO))

    # ── [7] 真實歷史頁（唯讀）：lcs_2019 春季等頁的 Nunu 局 ────────────────────
    print("[7] 真實歷史 PB 頁（唯讀）")
    n_new = n_old = n_new_bad = 0
    for f in HIST:
        PAGE["html"] = rd(os.path.join(REAL_PB, f))
        a, b = MH.pb_orders("sandbox"), OLD.pb_orders("sandbox")
        n_new += sum("nunuwillump" in k for k in a); n_new_bad += sum("nunuampwillump" in k for k in a)
        n_old += sum("nunuampwillump" in k for k in b)
    print(f"    新版 nunuwillump 局鍵 {n_new}、舊版 nunuampwillump 局鍵 {n_old}（{len(HIST)} 份頁面）")
    check("7a 新版局鍵全部是 nunuwillump、數量＝舊版的 nunuampwillump", n_new_bad == 0 and n_new == n_old and n_new > 0,
          (n_new, n_new_bad, n_old))
finally:
    print("[8] 出口")
    check("8a 網路出口一次都沒被叫", CALLS == [], len(CALLS))
    check("8b 真實 csv_cache/wikipb 檔名／大小／mtime 一個沒動", stat_dir(REAL_PB) == BEFORE_PB)
    check("8c 真實 csv_cache/wikitxt 檔名／大小／mtime 一個沒動", stat_dir(REAL_TXT) == BEFORE_TXT)
    shutil.rmtree(TMP, ignore_errors=True)

print(f"\n合計 {OK} 過／{FAIL} 失敗")
sys.exit(1 if FAIL else 0)
