# -*- coding: utf-8 -*-
"""快取 puuid 錯配防呆（2026-09-16 線 3，精進迴圈 #125）——純離線，不打 API、不用金鑰。

為什麼有這支：09-15 22:00 班 OBGG 把 DK Career 的舊 ID 帶回清單 → account-v1 404 → 鬆散反查（PREV_TP＝
該選手在該區的任一帳號）拿到兄弟帳號的 puuid → 改名回寫 ⇒ soloq_accounts.json 同一個 ID 兩筆。
同一種病早就在：soloq.js 58 組「不同 Riot ID 共用同一個 puuid」，Riot 實查每組只有一個 ID 活著，
死名靠 puuid 捷徑（_cached，不驗名）一班一班沿用兄弟的牌位。

要證明的事（每一件都配「會動的對照」）：
  ① 門①：上一版同一個 puuid 掛在清單裡同區 3 個 ID 上 ⇒ 三個都不走捷徑、問 account-v1；活的拿回 puuid，
     死的反查到活的名字 ⇒ 門② 拒收 ⇒ puuid None、noAcc＝今天；輸出沒有任何兩筆共用 puuid
  ② 門②：OBGG 帶回的舊 ID（沒有上一版紀錄）走 PREV_TP 反查到兄弟帳號 ⇒ 拒收、不改名、帳號檔沒有重複
  ③ 對照：真的改名（反查到的名字不在清單裡）照樣「♻ 反查成功」並回寫新名字
  ④ 對照：沒有共用的 puuid 照樣走捷徑（不發 account-v1）
  ⑤ 回寫防呆：account-v1 回來的名字已是清單裡另一筆 ⇒ 略過改名（抓取端擋不到的路徑）
  ⑥ 第二班：上一班的輸出當上一版 ⇒ 沒有共用、防呆行不出現；活的回到捷徑；死的吃 404 捷徑一個請求都不發
  ⑦ 純函式：norm_rid 去空白＋不分大小寫；不同區不算共用；自己的名字不算「另一筆」
  ⑧ 正控制（釘 OLDREV）：改動之前那版對同一份沙盒 ⇒ 死名沿用兄弟 puuid、舊 ID 被改名成兄弟 ⇒ 帳號檔重複
  ⑨ 隔離：真實 soloq.js／soloq_played.json／soloq_accounts.json 的 md5 與 mtime 前後不變；沙盒 puuid 用 ZZPROBE9942_
"""
import collections
import datetime
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OLDREV = "fdbf6371"   # 這輪改動之前最後一個動過 scripts/fetch_soloq.py 的 commit（#93：釘 commit、不釘 HEAD）
PASS = FAIL = 0


def ok(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ✓ " + name)
    else:
        FAIL += 1
        print("  ✗ %s %s" % (name, str(extra)[:700]))


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


REAL = [os.path.join(ROOT, "soloq.js"), os.path.join(HERE, "soloq_played.json"),
        os.path.join(HERE, "soloq_accounts.json")]
REAL_BEFORE = [(md5(p), os.path.getmtime(p) if os.path.exists(p) else None) for p in REAL]
TODAY = datetime.date.today().isoformat()
PREV_AT = (datetime.datetime.now() - datetime.timedelta(hours=12)).strftime("%Y-%m-%d %H:%M")
P = "ZZPROBE9942_"

# 帳號檔（清單順序＝PREV_TP 以最後一筆為準，CaB 排在 CaA 後面）
ACCOUNTS = [
    {"team": "T1", "player": "Zv", "platform": "kr", "riotId": "ZvLive#KR1"},
    {"team": "T1", "player": "Zv", "platform": "kr", "riotId": "ZvDead1#KR1"},
    {"team": "T1", "player": "Zv", "platform": "kr", "riotId": "ZvDead2#KR1"},
    {"team": "T1", "player": "Ca", "platform": "kr", "riotId": "CaA#KR1"},
    {"team": "T1", "player": "Ca", "platform": "kr", "riotId": "CaB#KR1"},
    {"team": "T1", "player": "Ca", "platform": "kr", "riotId": "CaOld#KR1"},        # OBGG 帶回的舊 ID
    {"team": "T1", "player": "Rn", "platform": "kr", "riotId": "RnOld#KR1"},        # 真的改名
    {"team": "T1", "player": "Nm", "platform": "kr", "riotId": "Nm#KR1"},
    {"team": "T1", "player": "Wb", "platform": "kr", "riotId": "WbOld#KR1"},        # 回寫防呆
    {"team": "T1", "player": "Wb", "platform": "kr", "riotId": "WbTaken#KR1"},
]
# 上一版 soloq.js
PREV = [
    ("Zv", "ZvLive#KR1", P + "zv"), ("Zv", "ZvDead1#KR1", P + "zv"), ("Zv", "ZvDead2#KR1", P + "zv"),
    ("Ca", "CaA#KR1", P + "caA"), ("Ca", "CaB#KR1", P + "caB"),
    ("Rn", "RnOlder#KR1", P + "rn"),        # PREV_ID 沒有 RnOld ⇒ 只能走 PREV_TP
    ("Nm", "Nm#KR1", P + "nm"),
]
# Riot：by-riot-id 活著的名字 → (puuid, 回傳的 gameName)
ALIVE = {"ZvLive": (P + "zv", "ZvLive"), "CaA": (P + "caA", "CaA"), "CaB": (P + "caB", "CaB"),
         "Nm": (P + "nm", "Nm"), "WbOld": (P + "wbx", "WbTaken"), "WbTaken": (P + "wbt", "WbTaken")}
BY_PUUID = {P + "zv": "ZvLive", P + "caA": "CaA", P + "caB": "CaB", P + "rn": "RnNew", P + "nm": "Nm",
            P + "wbx": "WbTaken", P + "wbt": "WbTaken"}
RANK = {P + "zv": ("MASTER", "I", 300, 200, 150), P + "caA": ("MASTER", "I", 100, 50, 40),
        P + "caB": ("CHALLENGER", "I", 900, 400, 300), P + "rn": ("DIAMOND", "I", 70, 30, 20),
        P + "nm": ("DIAMOND", "II", 40, 20, 20), P + "wbx": ("EMERALD", "I", 1, 5, 5),
        P + "wbt": ("EMERALD", "II", 2, 6, 6)}

TD = tempfile.mkdtemp(prefix="sqpuguard_")
os.makedirs(os.path.join(TD, "scripts"), exist_ok=True)


def seed():
    with io.open(os.path.join(TD, "scripts", "soloq_accounts.json"), "w", encoding="utf-8") as f:
        json.dump(ACCOUNTS, f, ensure_ascii=False)
    pl = []
    for n, rid, pu in PREV:
        t, dv, lp, w, l = RANK[pu]
        pl.append({"player": n, "team": "T1", "platform": "kr", "riotId": rid, "puuid": pu, "curId": rid,
                   "tier": t, "division": dv, "lp": lp, "wins": w, "losses": l, "found": True})
    with io.open(os.path.join(TD, "soloq.js"), "w", encoding="utf-8") as f:
        f.write("window.SOLOQ_DATA=" + json.dumps({"fetched_at": PREV_AT, "players": pl}, ensure_ascii=False) + ";\n")


HARNESS = '''
import io, json, os, re, sys, time, urllib.parse
sys.argv = ["fetch_soloq.py", "--no-ladder", "--no-idle-defer"]
os.environ["RIOT_API_KEY"] = "TEST"
MOD_DIR = %(moddir)r
TD_ = %(td)r
sys.path.insert(0, MOD_DIR)
import fetch_soloq as FS
assert os.path.dirname(os.path.abspath(FS.__file__)) == MOD_DIR, FS.__file__
FS.ROOT = TD_
FS.HERE = os.path.join(TD_, "scripts")
FS.OUT = os.path.join(TD_, "soloq.js")
FS.ACCOUNTS = os.path.join(TD_, "scripts", "soloq_accounts.json")
REAL_ROOT = %(realroot)r
for _k in dir(FS):
    _v = getattr(FS, _k)
    if isinstance(_v, str) and _v.startswith(REAL_ROOT) and _k not in ("__file__", "__cached__"):
        raise SystemExit("模組層還指著真實 repo：%%s=%%s" %% (_k, _v))
time.sleep = lambda s: None
ALIVE = %(alive)r
BY_PUUID = %(bypu)r
RANK = %(rank)r
URLS = []
def fake_riot_get(url, timeout=15):
    URLS.append(url)
    m = re.search(r"/accounts/by-riot-id/([^/]+)/([^/?]+)", url)
    if m:
        g = urllib.parse.unquote(m.group(1))
        if g in ALIVE:
            return 200, {"puuid": ALIVE[g][0], "gameName": ALIVE[g][1], "tagLine": "KR1"}
        return 404, None
    m = re.search(r"/accounts/by-puuid/([^/?]+)", url)
    if m:
        pu = m.group(1)
        return (200, {"puuid": pu, "gameName": BY_PUUID[pu], "tagLine": "KR1"}) if pu in BY_PUUID else (404, None)
    m = re.search(r"/entries/by-puuid/([^/?]+)", url)
    if m and m.group(1) in RANK:
        t, r, lp, w, l = RANK[m.group(1)]
        return 200, [{"queueType": "RANKED_SOLO_5x5", "tier": t, "rank": r, "leaguePoints": lp, "wins": w, "losses": l}]
    return 0, None
FS.riot_get = fake_riot_get
FS.main()
io.open(os.path.join(TD_, "urls_%(tag)s.txt"), "w", encoding="utf-8").write("\\n".join(URLS))
'''


def run(tag, moddir=HERE, reseed=True):
    if reseed:
        seed()
    hp = os.path.join(TD, "harness_%s.py" % tag)
    io.open(hp, "w", encoding="utf-8").write(HARNESS % {
        "moddir": moddir, "td": TD, "tag": tag, "alive": ALIVE, "bypu": BY_PUUID, "rank": RANK, "realroot": ROOT})
    r = subprocess.run([sys.executable, hp], capture_output=True, text=True, encoding="utf-8", timeout=180)
    out = (r.stdout or "") + (r.stderr or "")
    up = os.path.join(TD, "urls_%s.txt" % tag)
    urls = [u for u in io.open(up, encoding="utf-8").read().splitlines() if u] if os.path.exists(up) else []
    js = io.open(os.path.join(TD, "soloq.js"), encoding="utf-8").read()
    acc = json.loads(io.open(os.path.join(TD, "scripts", "soloq_accounts.json"), encoding="utf-8").read())
    return out, urls, js, acc


def recs(js):
    d = json.loads(re.search(r"=\s*(\{.*\});?\s*$", js, re.S).group(1))
    return {p["riotId"]: p for p in d["players"]}


def byid(urls, g):
    return sum(1 for u in urls if "/accounts/by-riot-id/%s/" % g in u)


def bypu(urls, pu):
    return sum(1 for u in urls if "/accounts/by-puuid/" + pu in u)


def shared_groups(js):
    c = collections.Counter(p.get("puuid") for p in recs(js).values() if p.get("puuid"))
    return {k: v for k, v in c.items() if v > 1}


def dup_ids(acc):
    c = collections.Counter((re.sub(r"\s+", "", a["riotId"]).casefold(), a.get("platform")) for a in acc)
    return [k for k, v in c.items() if v > 1]


# ── 第一班 ────────────────────────────────────────────────────────────────
out, urls, js, acc = run("new")
R = recs(js)
print("   （harness 輸出尾端）")
for _l in out.splitlines()[-10:]:
    print("     " + _l)
ok("harness 跑完（沒有 Traceback）", "Traceback" not in out and "模組層還指著真實 repo" not in out, out[-900:])
_prev_js = "window.SOLOQ_DATA=" + json.dumps({"players": [{"riotId": r, "puuid": pu} for _n, r, pu in PREV]}) + ";"
ok("前提：上一版有一組 3 個 ID 共用 puuid（其餘不共用）", shared_groups(_prev_js) == {P + "zv": 3}, shared_groups(_prev_js))

print("\n① 門①：共用 puuid 的三個 ID 不走捷徑、老實驗名")
ok("印出「上一版 1 個 puuid 同時掛在清單裡同區 3 個 ID 上」", "上一版 1 個 puuid 同時掛在清單裡同區 3 個 ID 上" in out,
   [l for l in out.splitlines() if "錯配防呆" in l])
for g in ("ZvLive", "ZvDead1", "ZvDead2"):
    ok("%s 發了 account-v1 by-riot-id（沒走捷徑）" % g, byid(urls, g) == 1, [u for u in urls if "Zv" in u])
ok("ZvLive 拿回自己的 puuid、牌位照 Riot", R["ZvLive#KR1"].get("puuid") == P + "zv" and R["ZvLive#KR1"].get("lp") == 300
   and R["ZvLive#KR1"].get("found") is True, R["ZvLive#KR1"])
for g in ("ZvDead1", "ZvDead2"):
    r = R.get(g + "#KR1", {})
    ok("%s 反查到 ZvLive ⇒ 拒收：puuid None、found False、noAcc＝今天" % g,
       r.get("puuid") is None and r.get("found") is False and r.get("noAcc") == TODAY and r.get("tier") is None, r)
    ok("%s 日誌印「✗ puuid 反查到 ZvLive#KR1，但那已經是清單裡另一筆帳號」" % g,
       "✗ puuid 反查到 ZvLive#KR1，但那已經是清單裡另一筆帳號" in out)
ok("輸出沒有任何兩筆共用 puuid", shared_groups(js) == {}, shared_groups(js))
ok("P+zv 的 entries/by-puuid 只問一次（死名沒再問兄弟的牌位）",
   sum(1 for u in urls if "/entries/by-puuid/" + P + "zv" in u) == 1, [u for u in urls if "entries" in u])

print("\n② 門②：OBGG 帶回的舊 ID 走 PREV_TP 反查到兄弟 ⇒ 拒收")
ok("CaOld 發了 by-riot-id（404）與 by-puuid（CaB 的 puuid）", byid(urls, "CaOld") == 1 and bypu(urls, P + "caB") == 1,
   [u for u in urls if "Ca" in u or "caB" in u])
ok("CaOld 拒收：puuid None、noAcc＝今天", R["CaOld#KR1"].get("puuid") is None and R["CaOld#KR1"].get("noAcc") == TODAY, R["CaOld#KR1"])
ok("帳號檔沒有被改出重複（CaOld 還是 CaOld）", dup_ids(acc) == [] and any(a["riotId"] == "CaOld#KR1" for a in acc), acc)
ok("帳號檔 CaB 只有一筆", sum(1 for a in acc if a["riotId"] == "CaB#KR1") == 1, acc)
ok("收尾印「反查拒收 3 個」與「捷徑擋下 3 個」", "捷徑擋下 3 個" in out and "反查拒收 3 個" in out,
   [l for l in out.splitlines() if "錯配防呆" in l])

print("\n③ 對照：真的改名照樣反查成功並回寫")
ok("RnOld 日誌「♻ 以 puuid 反查成功：目前 ID = RnNew#KR1」", "♻ 以 puuid 反查成功：目前 ID = RnNew#KR1" in out, out[-1500:])
ok("RnOld 拿到 P+rn 的牌位", R["RnOld#KR1"].get("puuid") == P + "rn" and R["RnOld#KR1"].get("lp") == 70, R["RnOld#KR1"])
ok("帳號檔 RnOld → RnNew", any(a["riotId"] == "RnNew#KR1" and a["player"] == "Rn" for a in acc)
   and not any(a["riotId"] == "RnOld#KR1" for a in acc), acc)

print("\n④ 對照：沒有共用的 puuid 照樣走捷徑")
ok("Nm 沒發 account-v1、牌位照問", byid(urls, "Nm") == 0 and R["Nm#KR1"].get("puuid") == P + "nm" and R["Nm#KR1"].get("found"), R["Nm#KR1"])
ok("CaA／CaB 也沒發 account-v1", byid(urls, "CaA") == 0 and byid(urls, "CaB") == 0, [u for u in urls if "by-riot-id" in u])

print("\n⑤ 回寫防呆：account-v1 回來的名字已是清單裡另一筆 ⇒ 略過改名")
ok("日誌「⏭ 略過 1 個改名（新名字已經是清單裡另一筆帳號」", "⏭ 略過 1 個改名（新名字已經是清單裡另一筆帳號" in out,
   [l for l in out.splitlines() if "略過" in l])
_ren = out.split("♻ 改名自動更新", 1)[-1] if "♻ 改名自動更新" in out else ""
ok("「♻ 改名自動更新 1 個帳號」底下只列 Rn、不列被略過的 Wb", "♻ 改名自動更新 1 個帳號" in out
   and "RnOld#KR1 → RnNew#KR1" in _ren and "WbOld#KR1 → WbTaken#KR1" not in _ren, _ren[:300])
ok("帳號檔 WbOld 保留、WbTaken 只有一筆",any(a["riotId"] == "WbOld#KR1" for a in acc)
   and sum(1 for a in acc if a["riotId"] == "WbTaken#KR1") == 1, acc)

print("\n⑥ 第二班（上一班的輸出當上一版）")
out2, urls2, js2, acc2 = run("shift2", reseed=False)
R2 = recs(js2)
ok("第二班沒有 Traceback", "Traceback" not in out2, out2[-800:])
ok("第二班沒有「上一版 N 個 puuid 同時掛在」那行", "同時掛在清單裡同區" not in out2, [l for l in out2.splitlines() if "錯配" in l])
ok("ZvLive 回到捷徑（不發 account-v1）", byid(urls2, "ZvLive") == 0 and R2["ZvLive#KR1"].get("found"), [u for u in urls2 if "Zv" in u])
ok("ZvDead1／2 吃 404 捷徑：一個請求都不發", byid(urls2, "ZvDead1") == 0 and byid(urls2, "ZvDead2") == 0
   and bypu(urls2, P + "zv") == 0, [u for u in urls2 if "Zv" in u or "zv" in u])
ok("第二班輸出仍沒有共用 puuid、帳號檔沒有重複", shared_groups(js2) == {} and dup_ids(acc2) == [], (shared_groups(js2), dup_ids(acc2)))

print("\n⑦ 純函式")
sys.path.insert(0, HERE)
os.environ.setdefault("RIOT_API_KEY", "TEST")
_argv = sys.argv
sys.argv = ["x"]
import fetch_soloq as FS  # noqa: E402
sys.argv = _argv
ok("norm_rid 去空白＋不分大小寫", FS.norm_rid(" Ca B #kr1 ") == FS.norm_rid("CaB#KR1") == "cab#kr1")
L = {(FS.norm_rid("A#1"), "kr"), (FS.norm_rid("B#1"), "kr"), (FS.norm_rid("C#1"), "euw1")}
ok("shared_puuids：同區兩個 ID 共用才算", FS.shared_puuids({("A#1", "kr"): "p", ("B#1", "kr"): "p"}, L) == {"p"})
ok("shared_puuids：不同區不算", FS.shared_puuids({("A#1", "kr"): "p", ("C#1", "euw1"): "p"}, L) == set())
ok("shared_puuids：不在清單裡的 ID 不算", FS.shared_puuids({("A#1", "kr"): "p", ("Z#1", "kr"): "p"}, L) == set())
ok("reverse_taken：自己的名字（大小寫不同）不算另一筆", FS.reverse_taken("a#1", "A#1", "kr", L) is False)
ok("reverse_taken：清單裡另一筆 ⇒ True；不在清單 ⇒ False；別區 ⇒ False",
   FS.reverse_taken("B#1", "A#1", "kr", L) is True and FS.reverse_taken("New#1", "A#1", "kr", L) is False
   and FS.reverse_taken("C#1", "A#1", "kr", L) is False)

print("\n⑧ 正控制（釘 %s）：改動之前那版對同一份沙盒" % OLDREV)
OLD_DIR = os.path.join(TD, "old")
os.makedirs(OLD_DIR, exist_ok=True)
gs = subprocess.run(["git", "show", "%s:scripts/fetch_soloq.py" % OLDREV], cwd=ROOT, capture_output=True)
ok("git show 拉得到舊版", gs.returncode == 0 and len(gs.stdout) > 10000, gs.stderr[:300])
io.open(os.path.join(OLD_DIR, "fetch_soloq.py"), "wb").write(gs.stdout)
ok("舊版真的沒有 SHARED_PU／reverse_taken（釘對 commit）", b"SHARED_PU" not in gs.stdout and b"reverse_taken" not in gs.stdout)
out9, urls9, js9, acc9 = run("old", moddir=OLD_DIR)
R9 = recs(js9)
ok("舊版 harness 跑完", "Traceback" not in out9, out9[-800:])
ok("舊版：死名沿用兄弟 puuid（輸出有共用組）", shared_groups(js9).get(P + "zv") == 3, shared_groups(js9))
ok("舊版：ZvDead1 沒發 account-v1（捷徑不驗名）", byid(urls9, "ZvDead1") == 0, [u for u in urls9 if "Zv" in u])
ok("舊版：CaOld 被改名成 CaB ⇒ 帳號檔重複", (FS.norm_rid("CaB#KR1"), "kr") in dup_ids(acc9), acc9)
ok("舊版：CaOld 拿到 CaB 的牌位", R9["CaOld#KR1"].get("puuid") == P + "caB", R9["CaOld#KR1"])

print("\n⑨ 隔離")
ok("沙盒輸出含只有沙盒才有的 puuid（ZZPROBE9942_）", "ZZPROBE9942_" in js)
real_js = io.open(REAL[0], encoding="utf-8", errors="replace").read() if os.path.exists(REAL[0]) else ""
ok("真實 soloq.js 沒有沙盒 puuid", "ZZPROBE9942_" not in real_js)
after = [(md5(p), os.path.getmtime(p) if os.path.exists(p) else None) for p in REAL]
ok("真實 soloq.js／soloq_played.json／soloq_accounts.json 的 md5 與 mtime 前後不變", after == REAL_BEFORE, (REAL_BEFORE, after))

print("\n結果：%d 過／%d 敗" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
