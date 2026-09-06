# -*- coding: utf-8 -*-
"""fetch_worlds_tier1 離線測試（不打網路）。
用法：python scripts\\fetch_worlds_tier1_test.py
素材：csv_cache/worlds_html/2026_Season_World_Championship.html（fetch_worlds_tier1.py 抓到時自己存的真實頁面）。
"""
import io, os, sys, json, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("fwt", os.path.join(HERE, "fetch_worlds_tier1.py"))
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)   # 模組自己會把 sys.stdout 包成 utf-8（這裡不能再包一次，會把同一個 buffer 關掉）

OK = FAIL = 0
def check(name, cond, info=""):
    global OK, FAIL
    if cond: OK += 1; print(f"  ✓ {name}")
    else: FAIL += 1; print(f"  ✗ {name}  {info}")

print("[1] 賽區全名 → 聯賽碼映射")
check("Asia-Pacific → LCP", M.lg_of("Asia-Pacific") == "LCP", M.lg_of("Asia-Pacific"))
check("Pacific → PCS（沒被 LCP 吃掉）", M.lg_of("Pacific") == "PCS", M.lg_of("Pacific"))
check("North America → LCS", M.lg_of("North America") == "LCS")
check("EMEA → LEC", M.lg_of("EMEA") == "LEC")
check("LTA North → LTA N", M.lg_of("LTA North") == "LTA N")
check("Brazil → CBLOL", M.lg_of("Brazil") == "CBLOL")
check("World Championship → None（略過）", M.lg_of("World Championship") is None)
check("未知賽區 → ?開頭", str(M.lg_of("Atlantis")).startswith("?"), M.lg_of("Atlantis"))

print("[2] 真實 2026 頁面解析（api.php 抓回的 HTML）")
fx = os.path.join(ROOT, "csv_cache", "worlds_html", "2026_Season_World_Championship.html")
if os.path.exists(fx):
    h = open(fx, encoding="utf-8").read()
    lst, unk = M.parse_year(h)
    check("2026 六個一級賽區", set(lst) == {"LCK", "LPL", "LEC", "LCP", "LCS", "CBLOL"}, lst)
    check("2026 沒有未映射", unk == [], unk)
    check("2026 不含 LTA N/S（LTA 已解散）", not any(c.startswith("LTA") for c in lst), lst)
    # 負控制：把 Asia-Pacific 改成沒見過的名字 → 一定要冒出未映射
    h2 = h.replace("Asia-Pacific", "Atlantis")
    lst2, unk2 = M.parse_year(h2)
    check("負控制：改名後出現未映射 ?Atlantis", unk2 == ["?Atlantis"], unk2)
    check("負控制：LCP 從清單消失", "LCP" not in lst2, lst2)
else:
    check("素材存在 " + fx, False, "先跑一次 python scripts/fetch_worlds_tier1.py 讓它存頁面")

print("[3] decide_year 決策")
prev = ["LCK", "LPL", "LEC", "LCP", "LCS", "CBLOL"]
l, n = M.decide_year(2026, ["LCK", "LPL", "LEC", "LCP", "LCS", "CBLOL"], [], prev)
check("抓到 ≥5 且全映射 → 以抓取為準", l == ["LCK", "LPL", "LEC", "LCP", "LCS", "CBLOL"] and n == [], (l, n))
l, n = M.decide_year(2026, ["LCK", "LPL", "LEC", "LCS", "CBLOL"], ["?Atlantis"], prev)
check("有未映射 → 整年退回手動表", l == M.HAND[2026] and any("未映射" in x for x in n), (l, n))
l, n = M.decide_year(2026, [], [], prev)
check("抓取失敗（空）→ 手動表", l == M.HAND[2026], (l, n))
l, n = M.decide_year(2027, ["LCK", "LPL"], [], prev)
check("沒手動表且清單 <5 → 沿用前一年", l == prev and any("沿用" in x for x in n), (l, n))
l, n = M.decide_year(2027, ["LCK", "LPL", "LEC", "LCP", "LCS", "CBLOL", "VCS"], [], prev)
check("沒手動表、抓到 7 個 → 以抓取為準", "VCS" in l and n == [], (l, n))
l, n = M.decide_year(2026, ["LCK", "LPL", "LEC", "LCP", "LTA N", "LTA S"], [], prev)
check("抓到 ≠ 手動表 → 以抓取為準並提示", l == ["LCK", "LPL", "LEC", "LCP", "LTA N", "LTA S"] and any("手動表" in x for x in n), (l, n))

print("[4] 手動表 2026 對得上 data_2026.js 的聯賽碼")
check("HAND[2026] 含 LCS", "LCS" in M.HAND[2026], M.HAND[2026])
check("HAND[2026] 不含 LTA N/S", not any(c.startswith("LTA") for c in M.HAND[2026]), M.HAND[2026])
dp = os.path.join(ROOT, "data", "data_2026.js")
if os.path.exists(dp):
    s = open(dp, encoding="utf-8").read()
    d = json.loads(s[s.index("=") + 1:].rstrip().rstrip(";"))
    rows = d["tabs"]["RAW_DATA"]; li = rows[0].index("league")
    codes = {r[li] for r in rows[1:]}
    miss = [c for c in M.HAND[2026] if c not in codes]
    check("HAND[2026] 每個聯賽碼在 data_2026.js 都有比賽列", miss == [], miss)

print("[5] fetch_page_html：api.php 優先、失敗退回 /wiki/、都失敗才丟例外")
calls = []
def op_api_ok(url):
    calls.append(url)
    if "api.php" in url:
        return json.dumps({"parse": {"title": "x", "text": "<p>FROM-API</p>"}}).encode("utf-8")
    raise AssertionError("不該打 wiki")
M.HTML_DIR = os.path.join(ROOT, "autopilot", "_r19", "_worlds_html_test")
h = M.fetch_page_html("Test_Page", opener=op_api_ok)
check("api 200 → 用 api 內容", h == "<p>FROM-API</p>", h)
check("api 成功就不打 wiki", len(calls) == 1 and "api.php" in calls[0], calls)
check("HTML 存進 HTML_DIR", open(os.path.join(M.HTML_DIR, "Test_Page.html"), encoding="utf-8").read() == "<p>FROM-API</p>")
calls.clear()
def op_api_fail(url):
    calls.append(url)
    if "api.php" in url:
        raise RuntimeError("HTTP Error 500")
    return b"<p>FROM-WIKI</p>"
h = M.fetch_page_html("Test_Page", opener=op_api_fail)
check("api 失敗 → 退回 wiki 內容", h == "<p>FROM-WIKI</p>", h)
check("順序：先 api 再 wiki", len(calls) == 2 and "api.php" in calls[0] and "/wiki/" in calls[1], calls)
def op_api_err(url):
    if "api.php" in url:
        return json.dumps({"error": {"code": "missingtitle", "info": "The page you specified doesn't exist."}}).encode("utf-8")
    raise RuntimeError("HTTP Error 403: Forbidden")
try:
    M.fetch_page_html("Nope", opener=op_api_err); check("都失敗要丟例外", False)
except RuntimeError as e:
    check("都失敗 → 例外含兩邊原因", "api.php" in str(e) and "403" in str(e), str(e))

print(f"\n結果：{OK}/{OK + FAIL}" + ("" if FAIL == 0 else f"（{FAIL} 失敗）"))
sys.exit(0 if FAIL == 0 else 1)
