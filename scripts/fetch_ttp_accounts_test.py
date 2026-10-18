# -*- coding: utf-8 -*-
"""fetch_ttp_accounts 純函式守門（不連網）：parse_page＋decide。
素材＝真實 TTP 頁面的版型（2026-10-18 抓的 Grell／Contractz 頁摘出來的片段）。
驗：①解析帳號、地區、停用旗標、隊伍、位置 ②查無此人（導回 /players）⇒ None
③身分核對：隊伍相符收、隊伍不符不收、沒寫隊伍時看位置 ④停用帳號不收、未知地區不收。
跑：python fetch_ttp_accounts_test.py
"""
import io, os, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_ttp_accounts as M  # noqa: E402

PASS = FAIL = 0


def ok(name, got, want=True):
    global PASS, FAIL
    if got == want:
        PASS += 1; print("  ✓ " + name)
    else:
        FAIL += 1; print("  ✗ %s：得到 %r，應為 %r" % (name, got, want))


GRELL = ("<html><head><title>Grell</title></head><body><section class='content'><h3>Grell</h3>"
         "<div class='player-info-inner'><h4>Player Info</h4><table><tr><td>Rank</td><td>Grandmaster 1,553LP</td></tr>"
         "<tr><td>Role</td><td>Jungle</td></tr><tr><td>Name</td><td>Jesús Alberto Loya Trujillo</td></tr>"
         "<tr><td>Residency</td><td>Liga Latinoamérica</td></tr></table></div>"
         "<div class='player-info-inner'> <h4>Accounts</h4> <table style='width:100%;' class='table'><tbody>"
         "<tr ><td><b>[NA]</b> Grell#3010</td><td class='dt-right'>GM 1,553LP</td></tr>"
         "<tr class='inactive_account'><td><b>[NA]</b> old grell#NA1</td><td class='dt-right'>Unranked</td></tr>"
         "<tr ><td><b>[XX]</b> weird#1</td><td class='dt-right'>Unranked</td></tr>"
         "</tbody></table></div></section></body></html>")
CTZ = ("<html><head><title>Contractz</title></head><body><section class='content'><h4>Player Info</h4>"
       "<table><tr><td>Role</td><td>Jungle</td></tr><tr><td>Team</td><td>Shopify Rebellion</td></tr>"
       "<tr><td>Birthday</td><td>August 25, 1999</td></tr></table>"
       "<h4>Accounts</h4> <table class='table'><tbody>"
       "<tr ><td><b>[NA]</b> ctz main#NA1</td><td class='dt-right'>Master 100LP</td></tr>"
       "</tbody></table></section></body></html>")
NOPE = "<html><head><title>Players</title></head><body>list</body></html>"

print("① 解析")
g = M.parse_page(GRELL)
ok("名字", g["name"], "Grell")
ok("沒寫隊伍", g["team"], "")
ok("位置 Jungle→JUNGLE", g["role"], "JUNGLE")
ok("帳號三列", [(a["region"], a["riotId"], a["active"]) for a in g["accounts"]],
   [("NA", "Grell#3010", True), ("NA", "old grell#NA1", False), ("XX", "weird#1", True)])
c = M.parse_page(CTZ)
ok("隊伍欄", c["team"], "Shopify Rebellion")
print("② 查無此人")
ok("導回 /players ⇒ None", M.parse_page(NOPE), None)

team_ab = {"shopify rebellion": "SR"}.get
tab = lambda full: team_ab(str(full).lower(), "")
print("③ 身分核對")
add, why = M.decide({"player": "Grell", "team": "FUE", "pos": "JUNGLE"}, g, tab)
ok("沒寫隊伍＋位置相符 ⇒ 收使用中的那隻（停用、未知地區不收）", [(e["riotId"], e["platform"], e["ttp"]) for e in add], [("Grell#3010", "na1", True)])
add, why = M.decide({"player": "Grell", "team": "FUE", "pos": "MIDDLE"}, g, tab)
ok("反例：沒寫隊伍＋位置不符 ⇒ 不收", (add, bool(why)), ([], True))
add, why = M.decide({"player": "Contractz", "team": "SR", "pos": "JUNGLE"}, c, tab)
ok("隊伍相符 ⇒ 收", [e["riotId"] for e in add], ["ctz main#NA1"])
add, why = M.decide({"player": "Contractz", "team": "DIG", "pos": "JUNGLE"}, c, tab)
ok("反例：隊伍不符（同名不同人／TTP 隊伍過期）⇒ 不收", (add, "隊伍不符" in why), ([], True))
add, why = M.decide({"player": "Grellx", "team": "FUE", "pos": "JUNGLE"}, g, tab)
ok("反例：頁名跟選手名不同 ⇒ 不收", (add, "頁名不符" in why), ([], True))
add, why = M.decide({"player": "Nobody", "team": "FUE", "pos": "TOP"}, None, tab)
ok("反例：查無此人 ⇒ 不收", (add, why), ([], "TTP 查無此人"))

print("通過 %d／失敗 %d" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
