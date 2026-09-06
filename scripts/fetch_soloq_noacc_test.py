# -*- coding: utf-8 -*-
"""404 帳號 7 天內不再問 Riot（2026-09-06 線 3，精進迴圈 #18）——純離線，不打 API、不用金鑰。

為什麼有這支：11:30 那輪 132 個帳號（84 找不到＋48 DPM 備援）**每天**都走 account-v1、每天都 404，
它們永遠拿不到 puuid ⇒ 永遠進不了 puuid 捷徑 ⇒ 每輪固定白排 132 次速率限制隊（約 160 秒）。
要證明的事：
  ① 上一版 noAcc 還新鮮（昨天）⇒ **不打 account-v1**、紀錄沿用 noAcc、不進重抓
  ② 同上但帳號帶 dpmRank ⇒ 不打 Riot、直接 DPM 備援（found=True、dpmRank=True、noAcc 沿用）
  ③ noAcc 過期（8 天前）⇒ 照問；再 404 ⇒ noAcc 改成今天
  ④ 親自問到 404 的新帳號 ⇒ 寫出 noAcc＝今天（第一次建立紀錄）
  ⑤ 連線失敗（code 0）⇒ **不寫 noAcc**、照舊重抓（暫時性失敗不能被這一刀砍掉）
  ⑥ `--full-id` ⇒ 捷徑關掉，①的帳號照問
  ⑦ 負控制：上一版 soloq.js 沒有 noAcc 欄 ⇒ ①的帳號照問（證明是那個欄位在驅動）
  ⑧ 有 puuid 的正常帳號完全不受影響
"""
import datetime
import io
import json
import os
import re
import subprocess
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
PASS = FAIL = 0
TODAY = datetime.date.today()
D = lambda n: (TODAY - datetime.timedelta(days=n)).isoformat()


def ok(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ✓ " + name)
    else:
        FAIL += 1
        print("  ✗ %s %s" % (name, extra))


accounts = [
    {"team": "T1", "player": "Gone", "platform": "KR", "riotId": "Gone#KR1"},                       # ① 昨天 404
    {"team": "T1", "player": "Dpm", "platform": "KR", "riotId": "Dpm#KR1",
     "dpmRank": {"tier": "EMERALD", "rank": "II", "lp": 75}},                                       # ② 前天 404＋dpm 牌位
    {"team": "T1", "player": "Old", "platform": "KR", "riotId": "Old#KR1"},                          # ③ 8 天前 404
    {"team": "T1", "player": "New", "platform": "KR", "riotId": "New#KR1"},                          # ④ 上一版沒紀錄、今天 404
    {"team": "T1", "player": "Flaky", "platform": "KR", "riotId": "Flaky#KR1"},                      # ⑤ 連線失敗
    {"team": "T1", "player": "Fine", "platform": "KR", "riotId": "Fine#KR1"},                        # ⑧ 有 puuid
]


def base(a, **kw):
    r = {"player": a["player"], "team": a["team"], "platform": "kr", "riotId": a["riotId"],
         "puuid": None, "curId": None, "tier": None, "division": None, "lp": None,
         "wins": None, "losses": None, "found": False}
    r.update(kw)
    return r


def prev_players(with_noacc):
    ps = [base(accounts[0]), base(accounts[1], tier="EMERALD", division="II", found=True, dpmRank=True),
          base(accounts[2]), base(accounts[5], puuid="pf", curId="Fine#KR1", tier="GOLD", division="I",
                                  lp=1, wins=2, losses=3, found=True)]
    if with_noacc:
        ps[0]["noAcc"] = D(1)
        ps[1]["noAcc"] = D(2)
        ps[2]["noAcc"] = D(8)
    return ps


HARNESS = '''
import io, json, os, sys, time
sys.argv = ["fetch_soloq.py", "--no-ladder"] + %(extra)r
os.environ["RIOT_API_KEY"] = "TEST"
HERE_ = %(here)r
TD_ = %(td)r
sys.path.insert(0, HERE_)
import fetch_soloq as FS
FS.ROOT = TD_
FS.HERE = os.path.join(TD_, "scripts")          # soloq_played.json 也寫進暫存目錄，不碰真檔
FS.OUT = os.path.join(TD_, "soloq.js")
FS.ACCOUNTS = os.path.join(TD_, "scripts", "soloq_accounts.json")
time.sleep = lambda s: None                     # 重抓前的 3 秒等待跳過
CALLS = []
def fake_riot_get(url, timeout=15):
    CALLS.append(url)
    if "/accounts/by-riot-id/Flaky/" in url:
        return 0, None
    if "/accounts/by-riot-id/Fine/" in url:
        return 200, {"puuid": "pf", "gameName": "Fine", "tagLine": "KR1"}
    if "/accounts/by-riot-id/" in url:
        return 404, None
    if "/entries/by-puuid/pf" in url:
        return 200, [{"queueType": "RANKED_SOLO_5x5", "tier": "GOLD", "rank": "I",
                      "leaguePoints": 1, "wins": 2, "losses": 3}]
    return 0, None
FS.riot_get = fake_riot_get
FS.main()
io.open(os.path.join(TD_, "calls.json"), "w", encoding="utf-8").write(json.dumps(CALLS))
'''


def run(tag, with_noacc, extra=()):
    td = tempfile.mkdtemp(prefix="sqnoacc_%s_" % tag)
    os.makedirs(os.path.join(td, "scripts"), exist_ok=True)
    with io.open(os.path.join(td, "scripts", "soloq_accounts.json"), "w", encoding="utf-8") as f:
        json.dump(accounts, f, ensure_ascii=False)
    with io.open(os.path.join(td, "soloq.js"), "w", encoding="utf-8") as f:
        f.write("window.SOLOQ_DATA=" + json.dumps({"fetched_at": D(1) + " 22:00",
                                                    "players": prev_players(with_noacc)}, ensure_ascii=False) + ";\n")
    hp = os.path.join(td, "harness.py")
    io.open(hp, "w", encoding="utf-8").write(HARNESS % {"here": HERE, "td": td, "extra": list(extra)})
    r = subprocess.run([sys.executable, hp], capture_output=True, text=True, encoding="utf-8", timeout=120)
    out = (r.stdout or "") + (r.stderr or "")
    calls = json.loads(io.open(os.path.join(td, "calls.json"), encoding="utf-8").read()) \
        if os.path.exists(os.path.join(td, "calls.json")) else None
    t = io.open(os.path.join(td, "soloq.js"), encoding="utf-8").read()
    players = json.loads(re.search(r"=\s*(\{.*\});?\s*$", t, re.S).group(1)).get("players", [])
    byid = {p["riotId"]: p for p in players}
    return out, calls, byid


def acc_calls(calls, name):
    return [u for u in (calls or []) if "/accounts/by-riot-id/%s/" % name in u]


out, calls, byid = run("main", True)
lines = out.splitlines()
retry = [l for l in lines if l.startswith("[重抓]")]
print("   （harness 輸出尾端）")
for _l in lines[-10:]:
    print("     " + _l)
ok("harness 有跑完（calls.json 存在）", calls is not None, out[-800:])

print("① noAcc 昨天 ⇒ 不問 Riot、沿用 noAcc、不重抓")
ok("Gone 沒打 account-v1", not acc_calls(calls, "Gone"), str(acc_calls(calls, "Gone")))
ok("Gone 印「⏭ … 不再問 Riot」", any("Gone#KR1" in l for l in lines) and
   any("⏭ 上一版 %s 已確定 Riot ID 不存在（404）" % D(1) in l for l in lines), out[-800:])
ok("Gone 紀錄 noAcc＝昨天、found=False", byid.get("Gone#KR1", {}).get("noAcc") == D(1)
   and byid.get("Gone#KR1", {}).get("found") is False, str(byid.get("Gone#KR1")))
ok("Gone 不在重抓名單", not any("Gone" in l for l in retry), str(retry))

print("\n② noAcc 前天＋dpmRank ⇒ 不問 Riot、DPM 備援")
ok("Dpm 沒打 account-v1", not acc_calls(calls, "Dpm"), str(acc_calls(calls, "Dpm")))
p = byid.get("Dpm#KR1", {})
ok("Dpm found=True、dpmRank=True、EMERALD II、LP 75 當未知", p.get("found") is True and p.get("dpmRank") is True
   and p.get("tier") == "EMERALD" and p.get("division") == "II" and p.get("lp") is None, str(p))
ok("Dpm noAcc 沿用前天", p.get("noAcc") == D(2), str(p.get("noAcc")))

print("\n③ noAcc 8 天前 ⇒ 過期照問；再 404 ⇒ noAcc 改今天")
ok("Old 打了 account-v1 恰好 1 次（重抓不算它）", len(acc_calls(calls, "Old")) == 1, str(acc_calls(calls, "Old")))
ok("Old noAcc＝今天", byid.get("Old#KR1", {}).get("noAcc") == TODAY.isoformat(), str(byid.get("Old#KR1")))

print("\n④ 上一版沒紀錄、今天 404 ⇒ 建立 noAcc＝今天")
ok("New 打了 account-v1 恰好 1 次", len(acc_calls(calls, "New")) == 1, str(acc_calls(calls, "New")))
ok("New noAcc＝今天、found=False", byid.get("New#KR1", {}).get("noAcc") == TODAY.isoformat()
   and byid.get("New#KR1", {}).get("found") is False, str(byid.get("New#KR1")))

print("\n⑤ 連線失敗 ⇒ 不寫 noAcc、照舊重抓")
ok("Flaky 沒有 noAcc", "noAcc" not in byid.get("Flaky#KR1", {}), str(byid.get("Flaky#KR1")))
ok("重抓名單恰好 1 個＝Flaky", len(retry) == 1 and "Flaky" in retry[0], str(retry))
ok("Flaky account-v1 打了 2 次（本輪＋重抓）", len(acc_calls(calls, "Flaky")) == 2, str(acc_calls(calls, "Flaky")))

print("\n⑧ 有 puuid 的正常帳號不受影響")
ok("Fine 走 puuid 捷徑、GOLD I", not acc_calls(calls, "Fine") and byid.get("Fine#KR1", {}).get("tier") == "GOLD",
   str(byid.get("Fine#KR1")))
ok("摘要行：2 個帳號沒問 account-v1", any("2 個帳號上一版已確定 Riot ID 不存在" in l for l in lines), out[-800:])
ok("寫出 2/6 有排名（Dpm 備援＋Fine）", "完成：2/6 有排名" in out, out[-300:])

print("\n⑥ --full-id ⇒ 捷徑關掉，Gone 照問")
out6, calls6, byid6 = run("fullid", True, ["--full-id"])
ok("Gone 打了 account-v1", len(acc_calls(calls6, "Gone")) >= 1, str(calls6)[:300])
ok("沒有任何「⏭」行", not any("⏭ 上一版" in l for l in out6.splitlines()))
ok("Gone noAcc 改成今天（親自問到 404）", byid6.get("Gone#KR1", {}).get("noAcc") == TODAY.isoformat(), str(byid6.get("Gone#KR1")))

print("\n⑦ 負控制：上一版沒有 noAcc 欄 ⇒ Gone 照問")
out7, calls7, byid7 = run("negctl", False)
ok("Gone 打了 account-v1", len(acc_calls(calls7, "Gone")) >= 1, str(calls7)[:300])
ok("沒有任何「⏭」行", not any("⏭ 上一版" in l for l in out7.splitlines()))

print("\n結果：%d 過／%d 敗" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
