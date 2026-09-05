# -*- coding: utf-8 -*-
"""`fetch_side_sel.parse()` 必須咬到**真正的比賽表**，不可以被同名的東西騙走。

2026-09-05 抓到的 bug：`parse()` 用 `htm.find("Side Sel")` 當入口，而 LPL 2025 的
Split 1／Split 2 頁面上有一個「**1v1 Side Selection**」活動的連結與 tooltip，位置在比賽表
**前面** ⇒ 從它往回找表格會咬到只有 5 列的導覽表 ⇒ 整頁回空，那一段的 MVP／VOD／選邊
全部沒收。受害的是 LPL 2025 的 5 個賽事頁，該年只剩 296 局進得來（修好之後 815 局）。

**離線**：只讀 `csv_cache/sidesel/` 已經抓好的頁面，不連 Leaguepedia。
⚠ 用真實頁面而不是手寫 HTML：第一版手寫的 HTML 根本不被當成比賽表，
   於是「有導覽表」與「沒導覽表」都回 0、兩邊相等——測試全綠但什麼都沒測到。
用法：python scripts/sidesel_table_test.py
"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import fetch_side_sel as F      # noqa: E402

CACHE = os.path.join(ROOT, "csv_cache", "sidesel")
PASS = FAIL = SKIP = 0


def ok(name, got, want=True):
    global PASS, FAIL
    if got == want:
        PASS += 1; print("  ✓ " + name)
    else:
        FAIL += 1; print("  ✗ %s：得到 %r，應為 %r" % (name, got, want))


def html_of(slug):
    p = os.path.join(CACHE, slug + ".html")
    return io.open(p, encoding="utf-8").read() if os.path.exists(p) else None


def games_of(slug, ov):
    h = html_of(slug)
    if h is None:
        return None
    sers = F.parse(ov, h)
    return (sum(len(s["games"]) for s in sers),
            sum(1 for s in sers for g in s["games"] if g.get("mvp")),
            sum(1 for s in sers if s.get("mvlead") and s.get("mvp")))


# ── ① 有「1v1 Side Selection」導覽表的那幾頁 ─────────────────────────────
print("① 受害頁：頁面上有『1v1 Side Selection』排在比賽表前面")
CASES = [("lpl_2025_season_split_1", "LPL/2025 Season/Split 1", 80),
         ("lpl_2025_season_split_2", "LPL/2025 Season/Split 2", 240),
         ("lpl_2025_season_split_2_playoffs", "LPL/2025 Season/Split 2 Playoffs", 60)]
for slug, ov, floor in CASES:
    r = games_of(slug, ov)
    if r is None:
        print("  · 快取沒有 %s，跳過" % slug); SKIP += 1; continue
    n, pog, pom = r
    # 先確認這一頁真的有那個誘餌，不然這條測試等於沒在測東西
    has_decoy = "1v1 Side Selection" in html_of(slug)
    ok("%s 頁面確實有那個誘餌" % ov.split("/")[-1], has_decoy, True)
    ok("⭐ %s 解析得到 >= %d 局（bug 時是 0）" % (ov.split("/")[-1], floor), n >= floor, True)
    ok("   而且逐局 MVP 幾乎都有（>= 局數的 95%）", pog >= n * 0.95, True)

# ── ② 反控制：沒有誘餌的頁面本來就正常，不可以被這次改動弄壞 ──────────────
print("\n② 反控制：沒有誘餌的頁面，數字不可以變")
for slug, ov, exp in [("lpl_2025_season_split_3", "LPL/2025 Season/Split 3", 212),
                      ("lpl_2025_season_grand_finals", "LPL/2025 Season/Grand Finals", 73)]:
    r = games_of(slug, ov)
    if r is None:
        print("  · 快取沒有 %s，跳過" % slug); SKIP += 1; continue
    ok("%s 沒有誘餌" % ov.split("/")[-1], "1v1 Side Selection" in html_of(slug), False)
    ok("   局數維持 %d" % exp, r[0], exp)

# ── ③ 系列 MVP：2025 一筆都沒有、2026 有（使用者 2026-09-05 問的那件事）──────
print("\n③ 系列賽 MVP（POM）只有 2026 才有")
r25 = games_of("lpl_2025_season_split_2_playoffs", "LPL/2025 Season/Split 2 Playoffs")
r26 = games_of("lpl_2026_season_split_1_playoffs", "LPL/2026 Season/Split 1 Playoffs")
if r25:
    ok("LPL 2025 季後賽：系列 MVP 0 筆（頁面上就沒有那一欄）", r25[2], 0)
if r26:
    ok("LPL 2026 季後賽：系列 MVP 有值", r26[2] > 0, True)
    ok("   同一頁逐局 MVP 也在（兩種同時發）", r26[1] > 0, True)
else:
    print("  · 快取沒有 2026 季後賽頁，跳過"); SKIP += 1

# ── ④ 賽程配對：Leaguepedia 的消歧義後綴不可以害整頁被跳過 ─────────────
# 2026-09-05：LCP 2025 的比賽表寫「Vikings Esports (2023 Vietnamese Team)」，
# 賽程表寫「MGN Vikings Esports」⇒ 互相都不是對方的子字串 ⇒ 7 場配不到日期 ⇒
# 只配到 21/28、整頁被 90% 門檻跳過（Mid Season／Season Finals／Season Kickoff 共 190 局）。
# 受測程式碼從 fetch_side_sel.py 抽出來，不另抄一份。
print("\n④ 賽程配對：括號裡的消歧義後綴")
src = io.open(os.path.join(ROOT, "scripts", "fetch_side_sel.py"), encoding="utf-8").read()
ns = {"re": re, "unicodedata": __import__("unicodedata")}
for pat in (r'        _FOLD = \{.*\n',
            r'        def _fold\(x\):\n(?:.*\n)*?            return "".join\(c for c.*\n',
            r'        nkq = lambda s: .*\n',
            r'        def same\(a, b\):\n(?:.*\n)*?            return bool\(a\).*\n',
            r'        nopar = lambda s2: .*\n',
            r'        def same_loose\(a, b\):\n(?:.*\n)*?            return bool\(a\).*\n',
            r'        def _initials\(x\):\n(?:.*\n)*?            return "".join.*\n',
            r'        def same_abbr\(a, b\):\n(?:.*\n)*?            return \(len\(na\).*\n',
            r'        same_any = lambda a, b: .*\n'):
    m = re.search(pat, src)
    if not m:
        print("  ✗ 抽不到 %r（原始碼結構變了）" % pat[:28]); FAIL += 1; continue
    exec("\n".join(l[8:] for l in m.group(0).rstrip("\n").split("\n")), ns)

if "same" in ns and "same_loose" in ns:
    PAGE, SCHED = "Vikings Esports (2023 Vietnamese Team)", "MGN Vikings Esports"
    ok("⭐ 去掉括號之後配得上（這一條就是那 190 局的解）", ns["same_loose"](PAGE, SCHED), True)
    ok("   嚴格比對本來配不上（證明修的是這個點，不是本來就會過）",
       ns["same"](PAGE, SCHED), False)
    # 反控制：不同隊還是不可以配在一起
    ok("不同隊不會被誤配", ns["same_loose"]("GAM Esports", "Team Secret Whales"), False)
    ok("同名不同地區的兩支隊，去括號後仍視為同名（所以嚴格那輪一定要先跑）",
       ns["same_loose"]("MVP (Korean Team)", "MVP (Chinese Team)"), True)
    # 原本就對得上的不可以被弄壞
    ok("原本就對得上的照樣對得上", ns["same_loose"]("CTBC Flying Oyster", "CTBC Flying Oyster"), True)

# ── ⑤ 賽程配對：頁面寫縮寫、賽程表寫全名 ────────────────────────────────
# 2026-09-05：LCS 2023 的比賽表寫「Eg」，賽程表寫「Evil Geniuses.NA」⇒ "eg" 不是
# "evilgeniusesna" 的子字串 ⇒ 4 個 LCS 賽事頁＋2022 世界賽 Play-In 全被 90% 門檻跳過
# （合計 387 局）。第三輪改用「去掉賽區後綴後取首字母」比對。
print("\n⑤ 賽程配對：縮寫 ↔ 全名首字母")
if "same_abbr" in ns and "same_any" in ns:
    ok("⭐ Eg ↔ Evil Geniuses.NA 配得上（那 387 局的解）",
       ns["same_abbr"]("Eg", "Evil Geniuses.NA"), True)
    ok("   前兩輪本來都配不上（證明修的是這個點）",
       ns["same"]("Eg", "Evil Geniuses.NA") or ns["same_loose"]("Eg", "Evil Geniuses.NA"), False)
    ok("   .NA／.EU 這種賽區後綴要先去掉（不然首字母會多一個 n）",
       ns["_initials"]("Evil Geniuses.NA"), "eg")
    # 第一版就是敗在這裡：一場比賽通常只有一隊寫縮寫，另一隊是全名對全名
    ok("⭐ 同一場的另一隊是全名對全名 → same_abbr 本身回 False",
       ns["same_abbr"]("Counter Logic Gaming", "Counter Logic Gaming"), False)
    ok("   所以第三輪要用『寬鬆 or 縮寫』，那一隊才過得了",
       ns["same_any"]("Counter Logic Gaming", "Counter Logic Gaming"), True)
    # 反控制：不可以亂配
    ok("縮寫對不上的隊不會被誤配", ns["same_abbr"]("Eg", "Golden Guardians"), False)
    ok("兩個長名不會走縮寫規則（避免首字母亂中）",
       ns["same_abbr"]("Team Liquid Honda", "Team Legends Holding"), False)
else:
    print("  ✗ 抽不到 same_abbr／same_any"); FAIL += 1

# ── ⑥ 隊名正規化：非 ASCII 字母要摺疊，不可以被丟掉 ──────────────────────
# 2026-09-05：CBLOL 2023 頁面寫「LØS」、賽程表寫「Los Grandes」。
# 舊的 nkq 只留 [a-z0-9] ⇒ Ø 整個被丟掉 ⇒ "ls"（不是 "los"）⇒ 三場配不上、整頁被跳過。
print("\n⑥ 隊名正規化：Ø／重音字母")
if "nkq" in ns and "same" in ns:
    ok("⭐ LØS → los（Ø 摺疊成 o，不是被丟掉）", ns["nkq"]("LØS"), "los")
    ok("⭐ LØS ↔ Los Grandes 配得上（CBLOL 那 30 局的解）",
       ns["same"]("LØS", "Los Grandes"), True)
    ok("   重音字母也要摺疊（é→e）", ns["nkq"]("Café"), "cafe")
    ok("   ß → ss", ns["nkq"]("Straße"), "strasse")
    # 反控制：摺疊不可以把不同隊變成同一隊
    ok("摺疊之後仍分得出不同隊", ns["same"]("LØS", "FURIA"), False)
    ok("原本就正常的隊名不受影響", ns["nkq"]("paiN Gaming"), "paingaming")
else:
    print("  ✗ 抽不到 nkq"); FAIL += 1

print("")
if SKIP:
    print("（跳過 %d 項：快取沒有那些頁面）" % SKIP)
if FAIL:
    print("✗ %d 條失敗、%d 條通過" % (FAIL, PASS)); sys.exit(1)
print("✓ 全部 %d 條通過" % PASS)
