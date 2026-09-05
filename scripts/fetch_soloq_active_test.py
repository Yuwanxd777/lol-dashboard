# -*- coding: utf-8 -*-
"""`--active`（只更新近期有打的選手）與重抓瘦身的離線驗收（2026-09-05）。

不打 API、不用金鑰：把 `fetch_one` 換成假的，只驗**挑人與合併**的邏輯。
要證明的四件事：
  ① 近 N 天有打的會抓、沒打的跳過
  ② **沒有逐場檔的選手一律保留**（不知道＝要抓，寧可多抓不要漏）
  ③ 合併之後，沒抓的那些人**原樣保留**上一版的牌位（不可以變成空的）
  ④ 「確定沒排名」不排進重抓，「這次沒問成」才重抓
"""
import datetime
import io
import json
import os
import subprocess
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PASS = FAIL = 0


def ok(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ✓ " + name)
    else:
        FAIL += 1
        print("  ✗ %s %s" % (name, extra))


# ── 用暫存目錄搭一組假資料，完全不碰真檔 ──────────────────────────────
TD = tempfile.mkdtemp(prefix="sqact_")
TODAY = datetime.date.today()
D0 = TODAY.isoformat()
D9 = (TODAY - datetime.timedelta(days=30)).isoformat()

recent = {"genDay": D0, "players": {
    "T1|Faker": {"r": "MID", "d": {D0: [[1, 1]]}},          # 今天有打 ⇒ 要抓
    "T1|Zeus": {"r": "TOP", "d": {D9: [[1, 0]]}},           # 30 天前打的 ⇒ 跳過
    "GEN|Chovy": {"r": "MID", "d": {}},                      # 有檔但沒打 ⇒ 跳過
}}
accounts = [
    {"team": "T1", "player": "Faker", "platform": "KR", "riotId": "Faker#KR1"},
    {"team": "T1", "player": "Zeus", "platform": "KR", "riotId": "Zeus#KR1"},
    {"team": "GEN", "player": "Chovy", "platform": "KR", "riotId": "Chovy#KR1"},
    {"team": "HLE", "player": "NewGuy", "platform": "KR", "riotId": "New#KR1"},   # 沒有逐場檔 ⇒ 一定要抓
]
prev = {"fetched_at": "2026-09-04 10:00", "players": [
    {"team": "T1", "player": "Faker", "riotId": "Faker#KR1", "tier": "CHALLENGER", "lp": 1000, "found": True},
    {"team": "T1", "player": "Zeus", "riotId": "Zeus#KR1", "tier": "MASTER", "lp": 300, "found": True},
    {"team": "GEN", "player": "Chovy", "riotId": "Chovy#KR1", "tier": "GRANDMASTER", "lp": 700, "found": True},
]}

os.makedirs(os.path.join(TD, "scripts"), exist_ok=True)
with io.open(os.path.join(TD, "soloq_recent.js"), "w", encoding="utf-8") as f:
    f.write("window.SOLOQ_RECENT=" + json.dumps(recent, ensure_ascii=False) + ";")
with io.open(os.path.join(TD, "soloq.js"), "w", encoding="utf-8") as f:
    f.write("window.SOLOQ_DATA=" + json.dumps(prev, ensure_ascii=False) + ";")
with io.open(os.path.join(TD, "scripts", "soloq_accounts.json"), "w", encoding="utf-8") as f:
    json.dump(accounts, f, ensure_ascii=False)

# 假的 fetch_one：不連網，回一個「有排名」的紀錄並記下被抓過誰
HARNESS = r'''
import io, json, os, sys
sys.argv = ["fetch_soloq.py", "--active", "--active-days", "3"]
os.environ["RIOT_API_KEY"] = "TEST"
sys.path.insert(0, r"{HERE}")
import fetch_soloq as FS
FS.ROOT = r"{TD}"
FS.OUT = os.path.join(r"{TD}", "soloq.js")
FS.ACCOUNTS = os.path.join(r"{TD}", "scripts", "soloq_accounts.json")
called = []
def fake_fetch_one(a, tag):
    called.append((a["team"], a["player"]))
    return {"player": a["player"], "team": a["team"], "platform": "kr", "riotId": a["riotId"],
            "puuid": "p", "curId": a["riotId"], "tier": "DIAMOND", "division": "I", "lp": 11,
            "wins": 1, "losses": 1, "found": True}
_orig_main = FS.main
src = _orig_main.__code__
# 直接呼叫 main，但把 fetch_one 換掉：main 內部是區域函式，改用猴補的方式攔在 get_soloq 之前不可行
# ⇒ 改成攔 riot_get，讓整條鏈都不連網，並記錄被查過的 riotId
def fake_riot_get(url):
    return 0, None
FS.riot_get = fake_riot_get
FS.get_account = lambda c, g, t: (called.append((g, t)) or {"puuid": "p", "gameName": g, "tagLine": t})
FS.get_soloq = lambda p, u: ({"queueType": "RANKED_SOLO_5x5", "tier": "DIAMOND", "rank": "I",
                               "leaguePoints": 11, "wins": 1, "losses": 1}, True)
FS.load_prev_puuids = lambda: ({}, {})
FS.main()
json.dump([list(c) for c in called], io.open(os.path.join(r"{TD}", "called.json"), "w", encoding="utf-8"))
'''.replace("{HERE}", HERE).replace("{TD}", TD)

hp = os.path.join(TD, "harness.py")
io.open(hp, "w", encoding="utf-8").write(HARNESS)
r = subprocess.run([sys.executable, hp], capture_output=True, text=True, encoding="utf-8", timeout=180)
out = (r.stdout or "") + (r.stderr or "")
print("   （harness 輸出）")
for _l in out.splitlines()[-14:]:
    print("     " + _l)

called = []
try:
    called = json.load(io.open(os.path.join(TD, "called.json"), encoding="utf-8"))
except Exception:
    pass
names = {c[0] for c in called}

print("① 挑人")
ok("今天有打的 Faker 有抓", any("Faker" in str(c) for c in called), str(called)[:90])
ok("30 天前才打的 Zeus 沒抓", not any("Zeus" in str(c) for c in called), str(called)[:90])
ok("有檔但沒打的 Chovy 沒抓", not any("Chovy" in str(c) for c in called), str(called)[:90])
print("\n② 不知道的一律保留")
ok("沒有逐場檔的 NewGuy 有抓", any("New" in str(c) for c in called), str(called)[:90])

print("\n③ 合併：沒抓的人要原樣保留上一版牌位")
try:
    t = io.open(os.path.join(TD, "soloq.js"), encoding="utf-8").read()
    got = json.loads(t[t.index("=") + 1:].rstrip().rstrip(";"))["players"]
except Exception as e:
    got = []
    print("   讀新檔失敗:", e)
by = {(p.get("team"), p.get("player")): p for p in got}
ok("Zeus 的舊牌位還在（MASTER 300LP）",
   by.get(("T1", "Zeus"), {}).get("tier") == "MASTER" and by.get(("T1", "Zeus"), {}).get("lp") == 300,
   str(by.get(("T1", "Zeus"))))
ok("Chovy 的舊牌位還在（GRANDMASTER）", by.get(("GEN", "Chovy"), {}).get("tier") == "GRANDMASTER",
   str(by.get(("GEN", "Chovy"))))
ok("Faker 換成這次抓到的新值（DIAMOND）", by.get(("T1", "Faker"), {}).get("tier") == "DIAMOND",
   str(by.get(("T1", "Faker"))))
ok("NewGuy 有被寫進去", ("HLE", "NewGuy") in by, str(list(by)))

print("\n④ 重抓瘦身：確定沒排名 vs 這次沒問成")
sys.path.insert(0, HERE)
os.environ.setdefault("RIOT_API_KEY", "TEST")
import fetch_soloq as FS2   # noqa: E402
FS2.riot_get = lambda url: (200, [{"queueType": "RANKED_FLEX_SR"}])       # 200 但沒有單雙排
ok("200＋沒有單雙排 ⇒ 確定（不重抓）", FS2.get_soloq("kr", "p") == (None, True), str(FS2.get_soloq("kr", "p")))
FS2.riot_get = lambda url: (0, None)                                      # 連線失敗
ok("連線失敗 ⇒ 不確定（要重抓）", FS2.get_soloq("kr", "p") == (None, False), str(FS2.get_soloq("kr", "p")))
FS2.riot_get = lambda url: (200, [{"queueType": "RANKED_SOLO_5x5", "tier": "GOLD"}])
_g, _s = FS2.get_soloq("kr", "p")
ok("有單雙排 ⇒ 回紀錄且確定", _g and _g.get("tier") == "GOLD" and _s is True)

import shutil
shutil.rmtree(TD, ignore_errors=True)
print(("\n✓ 全部 %d 條通過" % PASS) if not FAIL else ("\n✗ %d 條失敗、%d 條通過" % (FAIL, PASS)))
sys.exit(0 if not FAIL else 1)
