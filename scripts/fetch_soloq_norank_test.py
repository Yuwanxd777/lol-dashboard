# -*- coding: utf-8 -*-
"""無排名帳號 N 天不再問 entries/by-puuid（2026-09-07 線 3，精進迴圈 #50）——純離線，不打 API、不用金鑰。

為什麼有這支：`fetch_soloq_auto` 639.5 秒幾乎全是速率限制排隊（545 次 by-puuid ÷ 100 次/2 分鐘 = 654 秒），
其中 200 次問完得到「確定沒有單雙排排名」。`autopilot/_r50_norank_churn.py` 用 git 裡 15 個 soloq.js
快照量過：無排名→有排名 14 班只有 2 次，一直無排名平均每班 174 個。

要證明的六件事（每一件都配一個「會動的對照」）：
  ① 上一版 noRank 還新鮮 ⇒ **完全不發 entries/by-puuid**，且沿用舊日期（期限不續命）
  ② 上一版 noRank 過期 ⇒ 照樣問
  ③ **聯盟名單命中蓋過捷徑**（無排名躍升到 Master 以上仍然當天看到）——這是這一刀的安全閥
  ④ 親自問到「確定沒排名」才寫 noRank=今天；「這次沒問成」不寫、且照舊重抓
  ⑤ `--no-norank-skip` 關掉捷徑
  ⑥ 負控制：把 SKIP_NORANK 硬設成 False，① 一定要紅（證明這支測得到差別）
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import datetime

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


TODAY = datetime.date.today()
D_FRESH = TODAY.isoformat()                                    # 今天問過 ⇒ 新鮮
D_OLD = (TODAY - datetime.timedelta(days=10)).isoformat()      # 10 天前 ⇒ 過期

TD = tempfile.mkdtemp(prefix="sqnr_")
os.makedirs(os.path.join(TD, "scripts"), exist_ok=True)
accounts = [
    {"team": "T1", "player": "Stale", "platform": "KR", "riotId": "Stale#KR1"},    # noRank 新鮮 ⇒ 跳過
    {"team": "T1", "player": "Old", "platform": "KR", "riotId": "Old#KR1"},        # noRank 過期 ⇒ 要問
    {"team": "T1", "player": "Risen", "platform": "KR", "riotId": "Risen#KR1"},    # noRank 新鮮但上了名單 ⇒ 名單蓋過
    {"team": "T1", "player": "Fresh", "platform": "KR", "riotId": "Fresh#KR1"},    # 沒紀錄，問到確定沒排名
    {"team": "T1", "player": "Flaky", "platform": "KR", "riotId": "Flaky#KR1"},    # entries 非 200 ⇒ 沒問成
]
with io.open(os.path.join(TD, "scripts", "soloq_accounts.json"), "w", encoding="utf-8") as f:
    json.dump(accounts, f, ensure_ascii=False)

# 上一版 soloq.js（load_prev_norank 讀這個）
PREV = {"fetched_at": "2026-09-06 22:31", "players": [
    {"player": "Stale", "team": "T1", "platform": "kr", "riotId": "Stale#KR1", "puuid": "ps",
     "found": False, "noRank": D_FRESH},
    {"player": "Old", "team": "T1", "platform": "kr", "riotId": "Old#KR1", "puuid": "po",
     "found": False, "noRank": D_OLD},
    {"player": "Risen", "team": "T1", "platform": "kr", "riotId": "Risen#KR1", "puuid": "pr",
     "found": False, "noRank": D_FRESH},
]}


def write_prev():
    with io.open(os.path.join(TD, "soloq.js"), "w", encoding="utf-8") as f:
        f.write("window.SOLOQ_DATA=" + json.dumps(PREV, ensure_ascii=False) + ";\n")


HARNESS = '''
import io, json, os, sys, time
sys.argv = ["fetch_soloq.py", "--no-ladder"] + %(extra)r
os.environ["RIOT_API_KEY"] = "TEST"
HERE_ = %(here)r
TD_ = %(td)r
sys.path.insert(0, HERE_)
import fetch_soloq as FS
FS.ROOT = TD_
FS.HERE = os.path.join(TD_, "scripts")
FS.OUT = os.path.join(TD_, "soloq.js")
FS.ACCOUNTS = os.path.join(TD_, "scripts", "soloq_accounts.json")
FS.load_prev_puuids = lambda: ({}, {})
time.sleep = lambda s: None
PU = {"Stale": "ps", "Old": "po", "Risen": "pr", "Fresh": "pn", "Flaky": "px"}
URLS = []
def fake_riot_get(url, timeout=15):
    URLS.append(url)
    for g, pu in PU.items():
        if "/accounts/by-riot-id/" + g + "/" in url:
            return 200, {"puuid": pu, "gameName": g, "tagLine": "KR1"}
    if "/entries/by-puuid/px" in url:
        return 0, None                      # 連線失敗＝這次沒問成
    if "/entries/by-puuid/" in url:
        return 200, []                      # 200 且是清單、沒有單雙排 ⇒ 確定沒排名
    return 0, None
FS.riot_get = fake_riot_get
# Risen 這一版上了大師名單（--no-ladder 之下手動注入，等同 prefetch_ladders 的結果）
FS.LADDER[("kr", "pr")] = {"puuid": "pr", "tier": "MASTER", "rank": "I", "leaguePoints": 120,
                           "wins": 30, "losses": 20, "queueType": "RANKED_SOLO_5x5"}
_real_main = FS.main
def main2():
    _real_main()
    io.open(os.path.join(TD_, "urls_%(tag)s.txt"), "w", encoding="utf-8").write("\\n".join(URLS))
if %(negctl)r:
    # 負控制：捷徑整個關掉（等同改動之前的行為）
    _om = FS.main
    def main3():
        import builtins
        _orig_load = FS.load_prev_norank
        FS.load_prev_norank = lambda: {}
        _om()
        FS.load_prev_norank = _orig_load
        io.open(os.path.join(TD_, "urls_%(tag)s.txt"), "w", encoding="utf-8").write("\\n".join(URLS))
    main3()
else:
    main2()
'''


def run(tag, negctl=False, extra=None):
    write_prev()
    hp = os.path.join(TD, "harness_%s.py" % tag)
    io.open(hp, "w", encoding="utf-8").write(
        HARNESS % {"here": HERE, "td": TD, "negctl": negctl, "tag": tag, "extra": extra or []})
    r = subprocess.run([sys.executable, hp], capture_output=True, text=True, encoding="utf-8", timeout=120)
    urls = []
    up = os.path.join(TD, "urls_%s.txt" % tag)
    if os.path.exists(up):
        urls = [u for u in io.open(up, encoding="utf-8").read().splitlines() if u]
    out_js = ""
    op = os.path.join(TD, "soloq.js")
    if os.path.exists(op):
        out_js = io.open(op, encoding="utf-8").read()
    return (r.stdout or "") + (r.stderr or ""), urls, out_js


def players(out_js):
    import re
    d = json.loads(re.search(r"=\s*(\{.*\});?\s*$", out_js, re.S).group(1))
    return {p["player"]: p for p in d["players"]}


out, urls, js = run("main")
print("   （harness 輸出尾端）")
for _l in out.splitlines()[-10:]:
    print("     " + _l)
P = players(js) if js else {}
ent = [u for u in urls if "/entries/by-puuid/" in u]

print("\n① noRank 新鮮 ⇒ 不發 entries/by-puuid、沿用舊日期")
ok("Stale 印「⏭ …已確定沒有單雙排排名」", "已確定沒有單雙排排名" in out, out[-400:])
ok("完全沒發 entries/by-puuid/ps", not any("/by-puuid/ps" in u for u in ent), str(ent))
ok("Stale 的 noRank 沿用舊日期（不續命）", P.get("Stale", {}).get("noRank") == D_FRESH,
   str(P.get("Stale")))
ok("Stale 仍是 found=False", P.get("Stale", {}).get("found") is False, str(P.get("Stale")))
ok("Stale 保留 puuid（下一版還能走捷徑）", P.get("Stale", {}).get("puuid") == "ps", str(P.get("Stale")))
ok("開頭印出捷徑統計行", "無排名捷徑：" in out and "個帳號上一版已確定沒有單雙排排名" in out, out[:900])
ok("結尾印出省下的請求數", "沒問 entries/by-puuid，省下同樣次數的請求" in out, out[-500:])

print("\n② noRank 過期 ⇒ 照樣問")
ok("有發 entries/by-puuid/po", any("/by-puuid/po" in u for u in ent), str(ent))
ok("Old 的 noRank 更新成今天", P.get("Old", {}).get("noRank") == D_FRESH, str(P.get("Old")))

print("\n③ 聯盟名單命中蓋過捷徑（躍升 Master 當天看到）")
ok("Risen 抓到 MASTER 而不是被跳過", P.get("Risen", {}).get("tier") == "MASTER", str(P.get("Risen")))
ok("Risen 的 found=True", P.get("Risen", {}).get("found") is True, str(P.get("Risen")))
ok("Risen 沒留下 noRank（有排名就該清掉）", "noRank" not in P.get("Risen", {}), str(P.get("Risen")))
ok("Risen 也沒發 entries/by-puuid（名單免費）", not any("/by-puuid/pr" in u for u in ent), str(ent))

print("\n④ 親自問到才記日期；沒問成不記")
ok("Fresh（確定沒排名）noRank=今天", P.get("Fresh", {}).get("noRank") == D_FRESH, str(P.get("Fresh")))
ok("Flaky（沒問成）沒有 noRank", "noRank" not in P.get("Flaky", {}), str(P.get("Flaky")))
ok("Flaky 進了重抓", any(l.startswith("[重抓]") and "Flaky" in l for l in out.splitlines()),
   str([l for l in out.splitlines() if l.startswith("[重抓]")]))

print("\n⑤ --no-norank-skip 關掉捷徑")
out5, urls5, js5 = run("noskip", extra=["--no-norank-skip"])
ent5 = [u for u in urls5 if "/entries/by-puuid/" in u]
ok("Stale 這次有被問", any("/by-puuid/ps" in u for u in ent5), str(ent5))
ok("沒有印捷徑統計行", "無排名捷徑：" not in out5, out5[:600])

print("\n⑥ 負控制：捷徑關掉時 ① 一定要紅")
out6, urls6, js6 = run("neg", negctl=True)
ent6 = [u for u in urls6 if "/entries/by-puuid/" in u]
ok("負控制下 Stale 有被問（證明 ① 測得到差別）", any("/by-puuid/ps" in u for u in ent6), str(ent6))
ok("負控制下沒有「⏭ …已確定沒有單雙排排名」", "已確定沒有單雙排排名" not in out6, out6[-400:])

print("\n結果：%d 過／%d 敗" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
