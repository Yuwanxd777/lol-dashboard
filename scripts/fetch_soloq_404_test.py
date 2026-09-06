# -*- coding: utf-8 -*-
"""account-v1 回 404 的帳號不排進重抓（2026-09-06 線 3）——純離線，不打 API、不用金鑰。

為什麼有這支：11:30 那輪 1091 個帳號裡 84 個「找不到帳號」（Riot ID 已不存在／區域錯）**全部進了重抓**、
84 次照樣 404，白白排 84 次速率限制隊（100 次/2 分鐘 ⇒ 約 100 秒／輪）。
要證明的三件事：
  ① account-v1 回 **404** ⇒ 標成「確定」，不重抓
  ② account-v1 **連線失敗（code 0）** ⇒ 仍然重抓（真正的暫時性失敗不能被這一刀砍掉）
  ③ 負控制：把 get_account 換回「不回報狀態碼」的舊行為，① 一定要紅（證明這支測得到差別）
"""
import io
import json
import os
import subprocess
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
PASS = FAIL = 0


def ok(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ✓ " + name)
    else:
        FAIL += 1
        print("  ✗ %s %s" % (name, extra))


TD = tempfile.mkdtemp(prefix="sq404_")
os.makedirs(os.path.join(TD, "scripts"), exist_ok=True)
accounts = [
    {"team": "T1", "player": "Gone", "platform": "KR", "riotId": "Gone#KR1"},      # 404：ID 不存在
    {"team": "T1", "player": "Flaky", "platform": "KR", "riotId": "Flaky#KR1"},    # 連線失敗：要重抓
    {"team": "T1", "player": "Fine", "platform": "KR", "riotId": "Fine#KR1"},      # 正常：有排名
]
with io.open(os.path.join(TD, "scripts", "soloq_accounts.json"), "w", encoding="utf-8") as f:
    json.dump(accounts, f, ensure_ascii=False)

HARNESS = '''
import io, json, os, sys, time
sys.argv = ["fetch_soloq.py", "--no-ladder"]
os.environ["RIOT_API_KEY"] = "TEST"
HERE_ = %(here)r
TD_ = %(td)r
sys.path.insert(0, HERE_)
import fetch_soloq as FS
FS.ROOT = TD_
FS.HERE = os.path.join(TD_, "scripts")          # soloq_played.json 也寫進暫存目錄，不碰真檔
FS.OUT = os.path.join(TD_, "soloq.js")
FS.ACCOUNTS = os.path.join(TD_, "scripts", "soloq_accounts.json")
FS.load_prev_puuids = lambda: ({}, {})
time.sleep = lambda s: None                     # 重抓前的 3 秒等待跳過
def fake_riot_get(url, timeout=15):
    if "/accounts/by-riot-id/Gone/" in url:
        return 404, None
    if "/accounts/by-riot-id/Flaky/" in url:
        return 0, None
    if "/accounts/by-riot-id/Fine/" in url:
        return 200, {"puuid": "pf", "gameName": "Fine", "tagLine": "KR1"}
    if "/entries/by-puuid/pf" in url:
        return 200, [{"queueType": "RANKED_SOLO_5x5", "tier": "GOLD", "rank": "I",
                      "leaguePoints": 1, "wins": 2, "losses": 3}]
    return 0, None
FS.riot_get = fake_riot_get
if %(negctl)r:
    # 負控制：舊行為＝get_account 不回報狀態碼（ACC_LAST_CODE 永遠是 0）
    def old_get_account(cluster, g, t):
        code, data = FS.riot_get("x/accounts/by-riot-id/%%s/%%s" %% (g, t))
        return data if code == 200 and data else None
    FS.get_account = old_get_account
FS.main()
'''


def run(negctl):
    # 兩趟共用同一個暫存目錄：第一趟寫出的 soloq.js 會帶 noAcc（#18 的 404 七天捷徑），
    # 第二趟（負控制）若讀到它就會直接跳過 Gone、根本不問 Riot ⇒ 負控制誤紅。每趟都從沒有上一版開始。
    _prev = os.path.join(TD, "soloq.js")
    if os.path.exists(_prev):
        os.remove(_prev)
    hp = os.path.join(TD, "harness_%d.py" % int(negctl))
    io.open(hp, "w", encoding="utf-8").write(HARNESS % {"here": HERE, "td": TD, "negctl": negctl})
    r = subprocess.run([sys.executable, hp], capture_output=True, text=True, encoding="utf-8", timeout=120)
    return (r.stdout or "") + (r.stderr or "")


out = run(False)
lines = out.splitlines()
retry = [l for l in lines if l.startswith("[重抓]")]
print("   （harness 輸出尾端）")
for _l in lines[-8:]:
    print("     " + _l)

print("① 404 ⇒ 確定，不重抓")
ok("Gone 印「找不到帳號」且沒有「沒問成」",
   any("Gone#KR1" in l for l in lines) and
   any(l.strip() == "找不到帳號（Riot ID 或區域錯？）" for l in lines), out[-600:])
ok("Gone 不在重抓名單", not any("Gone" in l for l in retry), str(retry))
print("\n② 連線失敗 ⇒ 仍重抓")
ok("Flaky 印「※這次沒問成，稍後重抓」", any("找不到帳號" in l and "沒問成" in l for l in lines), out[-600:])
ok("重抓名單恰好 1 個＝Flaky", len(retry) == 1 and "Flaky" in retry[0], str(retry))
ok("Fine 有排名（GOLD）", any("GOLD I 1LP" in l for l in lines))
ok("寫出 1/3 有排名", "完成：1/3 有排名" in out)

print("\n③ 負控制：舊行為下 Gone 一定被重抓")
out2 = run(True)
retry2 = [l for l in out2.splitlines() if l.startswith("[重抓]")]
ok("舊行為重抓名單 2 個（含 Gone）", len(retry2) == 2 and any("Gone" in l for l in retry2), str(retry2))

print("\n結果：%d 過／%d 敗" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
