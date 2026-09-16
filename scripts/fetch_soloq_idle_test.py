# -*- coding: utf-8 -*-
"""閒置帳號延後（2026-09-14 線 3，精進迴圈 #110）——純離線，不打 API、不用金鑰。

為什麼有這支：09-14 10:00 那班 ⑤c 主迴圈 150s 裡節流暫停 95s——kr 直接問 entries/by-puuid 185 次，
Riot 每區 100 次／120 秒，第 101 次起整整白等一個視窗。`autopilot/_m110_measure_idle.py` 用歸檔的三班
日誌比 W+L：那 185 個裡 166 個五天一場都沒打。所以「輪著問」：閒置（W+L ≥ IDLE_DAYS 天沒動）的帳號
每平台每班只問 DIRECT_BUDGET 扣掉非閒置之後剩下的額度、越久沒問越先，其餘延後、沿用上一版牌位；
距上次問過 ≥ IDLE_MAX_H 小時的不准再延。

要證明的事（每一件都配「會動的對照」）：
  ① 額度用完 ⇒ 閒置帳號**不發 entries/by-puuid**、沿用上一版牌位＋戳記、標 deferred；越久沒問的先問
  ② 非閒置（活躍／過硬上限／上一版沒戳記）一律照問，不佔閒置的位子
  ③ 聯盟名單命中永遠免費、不被延後；名單命中也記戳記
  ④ 戳記語意：W+L 沒變 ⇒ wlAt 沿用（上一版沒有就用 fetched_at）；變了 ⇒ wlAt＝現在；askedAt 只在真的問到時更新
  ⑤ 逐場對接：延後的帳號進 soloq_played.json 的 acc_static（W+L 沒變 ⇒ 逐場那支照樣跳過）
  ⑥ 第二班輪替：上一班延後的（askedAt 較舊）這班先問；上一班問過的換它延後
  ⑦ `--no-idle-defer`／`--full-id` 關掉延後
  ⑧ 負控制：額度設成無限大 ⇒ ① 一定要紅（證明這支測得到差別）
  ⑨ 正控制（釘 OLDREV）：改動之前那版對同一份沙盒全問、沒有戳記、沒有延後那一行
  ⑩ IDLE_DAYS 門檻的兩個邊界（2026-09-16 #149 補）：`wlAt` 差 5 分鐘**沒到**門檻 ⇒ 判非閒置、每班照問；
     差 5 分鐘**過了**門檻 ⇒ 判閒置、額度 0 時被延後。另開一份沙盒（加帳號到 SPEC 會把 ① 的分配行數字全改掉），
     門檻天數與硬上限都從模組讀（不重抄常數），並用「把門檻挪 ∓0.01 天（14 分）」兩個突變當對照：
     挪早 ⇒ EdgeNew 改判閒置被延後、挪晚 ⇒ EdgeOld 改判非閒置照問，兩條斷言各自會紅
  ⑪ 隔離：真實 soloq.js／soloq_played.json／soloq_accounts.json 的 md5 與 mtime 前後不變；沙盒 puuid 用
     真 repo 不可能有的 ZZPROBE9942_*（只有沙盒才有的證據）
"""
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
OLDREV = "bf3ba764"   # 這輪改動之前最後一個動過 scripts/fetch_soloq.py 的 commit（#93：釘 commit、不釘 HEAD）
PASS = FAIL = 0


def ok(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ✓ " + name)
    else:
        FAIL += 1
        print("  ✗ %s %s" % (name, str(extra)[:600]))


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None


REAL = [os.path.join(ROOT, "soloq.js"), os.path.join(HERE, "soloq_played.json"),
        os.path.join(HERE, "soloq_accounts.json")]
REAL_BEFORE = [(md5(p), os.path.getmtime(p) if os.path.exists(p) else None) for p in REAL]

NOW = datetime.datetime.now()
H = datetime.timedelta(hours=1)
D = datetime.timedelta(days=1)


def st(dt):
    return dt.strftime("%Y-%m-%d %H:%M")


def near_now(s, tol_min=5):
    try:
        t = datetime.datetime.strptime(str(s), "%Y-%m-%d %H:%M")
    except Exception:
        return False
    return abs((t - NOW).total_seconds()) <= tol_min * 60


PREV_AT = st(NOW - 12 * H)     # 上一版＝上一班（12 小時前）
P = "ZZPROBE9942_"             # 只有沙盒才有的 puuid 前綴
# name -> (puuid, prev tier/div/lp/W/L, wlAt, askedAt, Riot 這次回的 W/L)
SPEC = {
    "Active": (P + "act", ("DIAMOND", "I", 50, 100, 90), st(NOW - 1 * D), PREV_AT, (100, 90)),
    "Idle1":  (P + "i1", ("DIAMOND", "II", 40, 50, 50), st(NOW - 5 * D), st(NOW - 36 * H), (50, 50)),
    "Idle2":  (P + "i2", ("DIAMOND", "II", 41, 51, 50), st(NOW - 5 * D), st(NOW - 30 * H), (51, 50)),
    "Idle3":  (P + "i3", ("DIAMOND", "II", 42, 52, 50), st(NOW - 5 * D), st(NOW - 24 * H), (52, 50)),
    "Idle4":  (P + "i4", ("DIAMOND", "II", 43, 53, 50), st(NOW - 5 * D), st(NOW - 12 * H), (53, 50)),
    "Idle5":  (P + "i5", ("DIAMOND", "II", 44, 54, 50), st(NOW - 5 * D), st(NOW - 12 * H), (54, 50)),
    "NewWL":  (P + "nw", ("EMERALD", "I", 10, 20, 20), st(NOW - 5 * D), st(NOW - 40 * H), (21, 20)),
    "Stale":  (P + "stl", ("DIAMOND", "IV", 5, 30, 30), st(NOW - 10 * D), st(NOW - 50 * H), (30, 30)),
    "Ladder": (P + "lad", ("MASTER", "I", 200, 300, 250), st(NOW - 5 * D), st(NOW - 12 * H), (300, 250)),
    "Boot":   (P + "bt", ("DIAMOND", "III", 1, 10, 10), None, None, (10, 10)),
    "Boot2":  (P + "bt2", ("DIAMOND", "III", 2, 10, 10), None, None, (11, 10)),
}
LADDER_ENTRY = {"puuid": P + "lad", "tier": "MASTER", "rank": "I", "leaguePoints": 210,
                "wins": 300, "losses": 250, "queueType": "RANKED_SOLO_5x5"}

TD = tempfile.mkdtemp(prefix="sqidle_")
os.makedirs(os.path.join(TD, "scripts"), exist_ok=True)
accounts = [{"team": "T1", "player": n, "platform": "KR", "riotId": "%s#KR1" % n} for n in SPEC]
with io.open(os.path.join(TD, "scripts", "soloq_accounts.json"), "w", encoding="utf-8") as f:
    json.dump(accounts, f, ensure_ascii=False)


def prev_players(spec=None):
    out = []
    for n, (pu, (t, dv, lp, w, l), wl_at, asked, _riot) in (spec or SPEC).items():
        r = {"player": n, "team": "T1", "platform": "kr", "riotId": "%s#KR1" % n, "puuid": pu,
             "curId": "%s#KR1" % n, "tier": t, "division": dv, "lp": lp, "wins": w, "losses": l, "found": True}
        if wl_at:
            r["wlAt"] = wl_at
        if asked:
            r["askedAt"] = asked
        out.append(r)
    return out


def write_prev(td=None, spec=None):
    with io.open(os.path.join(td or TD, "soloq.js"), "w", encoding="utf-8") as f:
        f.write("window.SOLOQ_DATA=" + json.dumps({"fetched_at": PREV_AT, "players": prev_players(spec)},
                                                  ensure_ascii=False) + ";\n")


HARNESS = '''
import io, json, os, re, sys, time
sys.argv = ["fetch_soloq.py", "--no-ladder"] + %(extra)r
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
# 模組層不可以還有字串指著真實 repo（#96／#98 的規矩）
REAL_ROOT = %(realroot)r
for _k in dir(FS):
    _v = getattr(FS, _k)
    if isinstance(_v, str) and _v.startswith(REAL_ROOT) and _k not in ("__file__", "__cached__"):
        raise SystemExit("模組層還指著真實 repo：%%s=%%s" %% (_k, _v))
time.sleep = lambda s: None
PU = %(pu)r
RANK = %(rank)r
URLS = []
def fake_riot_get(url, timeout=15):
    URLS.append(url)
    for g, pu in PU.items():
        if "/accounts/by-riot-id/" + g + "/" in url:
            return 200, {"puuid": pu, "gameName": g, "tagLine": "KR1"}
    m = re.search(r"/entries/by-puuid/([^/?]+)", url)
    if m and m.group(1) in RANK:
        t, r, lp, w, l = RANK[m.group(1)]
        return 200, [{"queueType": "RANKED_SOLO_5x5", "tier": t, "rank": r, "leaguePoints": lp,
                      "wins": w, "losses": l}]
    return 0, None
FS.riot_get = fake_riot_get
FS.LADDER[("kr", %(ladpu)r)] = %(ladentry)r
_B0 = getattr(FS, "DIRECT_BUDGET", None)      # 正本的預設值（覆寫成沙盒額度之前先記下來，⑩ 要驗它）
if hasattr(FS, "DIRECT_BUDGET"):
    FS.DIRECT_BUDGET = %(budget)r
FS.main()
io.open(os.path.join(TD_, "urls_%(tag)s.txt"), "w", encoding="utf-8").write("\\n".join(URLS))
io.open(os.path.join(TD_, "attrs_%(tag)s.json"), "w", encoding="utf-8").write(json.dumps({
    "has_budget": hasattr(FS, "DIRECT_BUDGET"), "budget": _B0,
    "idle_days": getattr(FS, "IDLE_DAYS", None), "idle_max_h": getattr(FS, "IDLE_MAX_H", None),
    "out": FS.OUT, "acc": FS.ACCOUNTS}))
'''

PU = {n: v[0] for n, v in SPEC.items()}
RANK = {v[0]: (v[1][0], v[1][1], v[1][2] + 1, v[4][0], v[4][1]) for v in SPEC.values()}   # LP +1：證明真的問到 Riot


def run(tag, budget=6, extra=None, moddir=HERE, fresh_prev=True, td=None, spec=None, pu=None, rank=None):
    # td／spec／pu／rank 是 ⑩ 的邊界沙盒用的（另一組帳號、另一個 tmp）；上面那些呼叫維持原本的預設值
    td, pu, rank = td or TD, pu or PU, rank or RANK
    if fresh_prev:
        write_prev(td, spec)
    hp = os.path.join(td, "harness_%s.py" % tag)
    io.open(hp, "w", encoding="utf-8").write(HARNESS % {
        "moddir": moddir, "td": td, "tag": tag, "extra": extra or [], "pu": pu, "rank": rank,
        "ladpu": P + "lad", "ladentry": LADDER_ENTRY, "budget": budget, "realroot": ROOT})
    r = subprocess.run([sys.executable, hp], capture_output=True, text=True, encoding="utf-8", timeout=180)
    out = (r.stdout or "") + (r.stderr or "")
    up = os.path.join(td, "urls_%s.txt" % tag)
    urls = [u for u in io.open(up, encoding="utf-8").read().splitlines() if u] if os.path.exists(up) else []
    js = io.open(os.path.join(td, "soloq.js"), encoding="utf-8").read()
    ap = os.path.join(td, "attrs_%s.json" % tag)
    attrs = json.loads(io.open(ap, encoding="utf-8").read()) if os.path.exists(ap) else {}
    return out, urls, js, attrs


def players(js):
    d = json.loads(re.search(r"=\s*(\{.*\});?\s*$", js, re.S).group(1))
    return {p["player"]: p for p in d["players"]}


def asked(urls, name):
    return any("/entries/by-puuid/" + PU[name] in u for u in urls)


def played_json():
    p = os.path.join(TD, "scripts", "soloq_played.json")
    return json.loads(io.open(p, encoding="utf-8").read()) if os.path.exists(p) else {}


# ── 第一班：額度 6、非閒置 4（Active／Stale／Boot／Boot2）⇒ 閒置只剩 2 個位子 ────────────
out, urls, js, attrs = run("main", budget=6)
print("   （harness 輸出尾端）")
for _l in out.splitlines()[-8:]:
    print("     " + _l)
ok("harness 跑完（沒有 Traceback）", "Traceback" not in out and attrs.get("has_budget") is True, out[-800:])
ok("沙盒出口都在 tmp（OUT／ACCOUNTS）", attrs.get("out", "").startswith(TD) and attrs.get("acc", "").startswith(TD), attrs)
ok("走 puuid 捷徑：完全沒發 account-v1", not any("/accounts/by-riot-id/" in u for u in urls), str(urls)[:400])
PL = players(js)

print("\n① 額度用完 ⇒ 閒置帳號不問、沿用上一版、越久沒問的先問")
ok("印出分配行：kr 直接問 10 → 這班 6（其中閒置 2）、延後 4",
   "kr 直接問 10 → 這班 6（其中閒置 2）、延後 4" in out, [l for l in out.splitlines() if "閒置延後" in l])
ok("延後裡最久 30.0h 沒問（Idle2）", "延後裡最久 30.0h 沒問" in out, [l for l in out.splitlines() if "閒置延後" in l])
ok("NewWL（40h）與 Idle1（36h）這兩個最久沒問的有被問", asked(urls, "NewWL") and asked(urls, "Idle1"), str(urls))
for n in ("Idle2", "Idle3", "Idle4", "Idle5"):
    ok("%s 沒發 entries/by-puuid" % n, not asked(urls, n), str(urls))
    r = PL.get(n, {})
    sp = SPEC[n]
    ok("%s 沿用上一版牌位（tier／lp／W／L 一字不差）" % n,
       (r.get("tier"), r.get("division"), r.get("lp"), r.get("wins"), r.get("losses")) == sp[1] and r.get("found") is True, r)
    ok("%s 戳記沿用（wlAt／askedAt 不續命）＋ 標 deferred" % n,
       r.get("wlAt") == sp[2] and r.get("askedAt") == sp[3] and near_now(r.get("deferred")), r)
ok("日誌印「⏭ 閒置 5.0 天（W+L 沒動）、上次問 30.0h 前 → 這班延後」",
   any("⏭ 閒置 5.0 天（W+L 沒動）、上次問 30.0h 前 → 這班延後" in l for l in out.splitlines()), out[-1500:])
ok("結尾印「4 個閒置帳號這班延後」", "（4 個閒置帳號這班延後" in out, out[-600:])
ok("延後的紀錄 LP 還是上一版（沒有 +1 ⇒ 真的沒問到 Riot）", PL["Idle2"].get("lp") == 41, PL["Idle2"])

print("\n② 非閒置照問，不佔閒置的位子")
ok("Active（1 天前有動）有問、LP 變成 Riot 的值", asked(urls, "Active") and PL["Active"].get("lp") == 51, PL["Active"])
ok("Stale（閒置 10 天但 50h 沒問 ≥ 硬上限）有問", asked(urls, "Stale") and PL["Stale"].get("lp") == 6, PL["Stale"])
ok("Boot／Boot2（上一版沒戳記）有問", asked(urls, "Boot") and asked(urls, "Boot2"), str(urls))
ok("Active／Stale／Boot 都沒有 deferred", all("deferred" not in PL[n] for n in ("Active", "Stale", "Boot", "Boot2")), PL["Stale"])

print("\n③ 聯盟名單命中免費、不延後、也記戳記")
ok("Ladder 沒發 entries/by-puuid", not asked(urls, "Ladder"), str(urls))
ok("Ladder 拿到名單的 MASTER 210LP", PL["Ladder"].get("tier") == "MASTER" and PL["Ladder"].get("lp") == 210, PL["Ladder"])
ok("Ladder askedAt＝現在、wlAt 沿用（W+L 沒變）、沒有 deferred",
   near_now(PL["Ladder"].get("askedAt")) and PL["Ladder"].get("wlAt") == SPEC["Ladder"][2] and "deferred" not in PL["Ladder"], PL["Ladder"])

print("\n④ 戳記語意")
ok("Idle1 問過：askedAt＝現在、wlAt 沿用 5 天前", near_now(PL["Idle1"].get("askedAt")) and PL["Idle1"].get("wlAt") == SPEC["Idle1"][2], PL["Idle1"])
ok("NewWL W+L 變了：wlAt＝現在", near_now(PL["NewWL"].get("wlAt")) and near_now(PL["NewWL"].get("askedAt")), PL["NewWL"])
ok("Boot（沒戳記、W+L 沒變）：wlAt＝上一版 fetched_at", PL["Boot"].get("wlAt") == PREV_AT, PL["Boot"])
ok("Boot2（沒戳記、W+L 變了）：wlAt＝現在", near_now(PL["Boot2"].get("wlAt")), PL["Boot2"])
ok("Stale 問過：askedAt＝現在、wlAt 仍是 10 天前", near_now(PL["Stale"].get("askedAt")) and PL["Stale"].get("wlAt") == SPEC["Stale"][2], PL["Stale"])

print("\n⑤ 逐場對接：延後的帳號＝W+L 沒變 ⇒ acc_static")
pj = played_json()
acc_static = set(pj.get("acc_static") or [])
ok("soloq_played.json 有寫、scope=full", pj.get("scope") == "full", pj)
for n in ("Idle2", "Idle5", "Idle1", "Active"):
    ok("%s 在 acc_static" % n, ("%s#kr1@kr" % n.lower()) in acc_static, sorted(acc_static))
ok("NewWL／Boot2（W+L 變了）不在 acc_static、在 played",
   "newwl#kr1@kr" not in acc_static and "boot2#kr1@kr" not in acc_static
   and "T1|NewWL" in (pj.get("played") or []) and "T1|Boot2" in (pj.get("played") or []), pj)

print("\n⑥ 第二班輪替（上一班的輸出當上一版）")
out2, urls2, js2, _ = run("shift2", budget=6, fresh_prev=False)
PL2 = players(js2)
ok("Idle2／Idle3（上一班延後、askedAt 最舊）這班有問", asked(urls2, "Idle2") and asked(urls2, "Idle3"), str(urls2))
ok("Idle1（上一班剛問過）這班換它延後", not asked(urls2, "Idle1") and "deferred" in PL2["Idle1"], PL2["Idle1"])
ok("Idle2 問過之後沒有 deferred、LP 變成 Riot 的值", "deferred" not in PL2["Idle2"] and PL2["Idle2"].get("lp") == 42, PL2["Idle2"])
ok("NewWL（上一班 W+L 變了 ⇒ 不閒置）這班照問", asked(urls2, "NewWL"), str(urls2))
ok("Active 兩班都問", asked(urls2, "Active"), str(urls2))
ok("分配行：kr 直接問 10 → 這班 6（其中閒置 2）、延後 4", "kr 直接問 10 → 這班 6（其中閒置 2）、延後 4" in out2,
   [l for l in out2.splitlines() if "閒置延後" in l])

print("\n⑦ 關掉延後的旗標")
out7, urls7, js7, _ = run("noidle", budget=6, extra=["--no-idle-defer"])
ok("--no-idle-defer：Idle2～5 全問、沒有分配行", all(asked(urls7, n) for n in ("Idle2", "Idle3", "Idle4", "Idle5")) and "閒置延後" not in out7, str(urls7))
ok("--no-idle-defer：仍記戳記（Idle2 askedAt＝現在）", near_now(players(js7)["Idle2"].get("askedAt")), players(js7)["Idle2"])
out7b, urls7b, js7b, _ = run("fullid", budget=6, extra=["--full-id"])
ok("--full-id：Idle2～5 全問（走 account-v1 完整路徑）", all(asked(urls7b, n) for n in ("Idle2", "Idle5"))
   and any("/accounts/by-riot-id/" in u for u in urls7b), str(urls7b)[:400])

print("\n⑧ 負控制：額度無限大 ⇒ ① 一定要紅")
out8, urls8, js8, _ = run("neg", budget=10 ** 6)
ok("負控制下 Idle2～5 全被問（證明 ① 測得到差別）", all(asked(urls8, n) for n in ("Idle2", "Idle3", "Idle4", "Idle5")), str(urls8))
ok("負控制下沒有「這班延後」", "這班延後" not in out8, out8[-500:])
ok("負控制的分配行寫「延後 0」", "延後 0" in out8, [l for l in out8.splitlines() if "閒置延後" in l])

print("\n⑨ 正控制（釘 %s）：改動之前那版對同一份沙盒全問、沒戳記、沒延後" % OLDREV)
OLD_DIR = os.path.join(TD, "old")
os.makedirs(OLD_DIR, exist_ok=True)
gs = subprocess.run(["git", "show", "%s:scripts/fetch_soloq.py" % OLDREV], cwd=ROOT, capture_output=True)
ok("git show 拉得到舊版", gs.returncode == 0 and len(gs.stdout) > 10000, gs.stderr[:300])
io.open(os.path.join(OLD_DIR, "fetch_soloq.py"), "wb").write(gs.stdout)
ok("舊版真的沒有 DIRECT_BUDGET（釘對 commit）", b"DIRECT_BUDGET" not in gs.stdout and b"IDLE_DAYS" not in gs.stdout)
out9, urls9, js9, attrs9 = run("old", budget=6, moddir=OLD_DIR)
ok("舊版 harness 跑完、模組沒有 DIRECT_BUDGET 屬性", "Traceback" not in out9 and attrs9.get("has_budget") is False, out9[-600:])
ok("舊版：Idle2～5 全問", all(asked(urls9, n) for n in ("Idle2", "Idle3", "Idle4", "Idle5")), str(urls9))
ok("舊版：沒有分配行、沒有「這班延後」", "閒置延後" not in out9 and "這班延後" not in out9, out9[-500:])
PL9 = players(js9)
ok("舊版：輸出沒有 wlAt／askedAt／deferred 戳記",
   all(k not in PL9["Idle2"] for k in ("wlAt", "askedAt", "deferred")), PL9["Idle2"])

print("\n⑩ IDLE_DAYS 門檻的兩個邊界（#149 補：原本 SPEC 的 wlAt 只有 1／5／10 天，離門檻很遠 ⇒ 懸崖沒人守）")
# 為什麼另開一份沙盒：上面那組的人數寫死在 ① 的分配行斷言裡（「直接問 10 → 這班 6…」），
# 往 SPEC 加帳號會把那些數字全部改掉。邊界只要兩個帳號＋額度 1，獨立一份最乾淨。
# 門檻天數／硬上限一律從模組讀（attrs 是主跑那班抓回來的），日後調參數這段不會誤報。
M = datetime.timedelta(minutes=1)
IDLE_D = float(attrs.get("idle_days") or 0)
MAX_H = float(attrs.get("idle_max_h") or 0)
ok("拿得到模組的 IDLE_DAYS／IDLE_MAX_H（邊界樣本照它算，不重抄常數）", IDLE_D >= 1 and MAX_H >= 24, attrs)
E_NOW = datetime.datetime.now()          # 用「現在」算，不用檔頭的 NOW：前面九節跑掉的時間會吃掉 5 分鐘的餘裕
E_TH = datetime.timedelta(days=IDLE_D)
# EdgeNew 差 5 分鐘沒到門檻（必須判非閒置）、EdgeOld 差 5 分鐘過了門檻（必須判閒置）。
# askedAt 刻意錯開：EdgeNew 1 小時前問過、EdgeOld 0.8×IDLE_MAX_H 前問過（還沒到硬上限，不會被強制問）
# ⇒ 突變把 EdgeNew 也判成閒置時，額度 1 會先給「比較久沒問」的 EdgeOld，EdgeNew 就換成被延後（斷言才會翻）。
EDGE = {
    "EdgeNew": (P + "en", ("DIAMOND", "II", 60, 70, 70), st(E_NOW - E_TH + 5 * M), st(E_NOW - 1 * H), (70, 70)),
    "EdgeOld": (P + "eo", ("DIAMOND", "II", 80, 71, 70), st(E_NOW - E_TH - 5 * M), st(E_NOW - 0.8 * MAX_H * H), (71, 70)),
}
TD2 = tempfile.mkdtemp(prefix="sqedge_")
os.makedirs(os.path.join(TD2, "scripts"), exist_ok=True)
with io.open(os.path.join(TD2, "scripts", "soloq_accounts.json"), "w", encoding="utf-8") as f:
    json.dump([{"team": "T1", "player": n, "platform": "KR", "riotId": "%s#KR1" % n} for n in EDGE],
              f, ensure_ascii=False)
EPU = {n: v[0] for n, v in EDGE.items()}
ERANK = {v[0]: (v[1][0], v[1][1], v[1][2] + 1, v[4][0], v[4][1]) for v in EDGE.values()}


def easked(urls, name):
    return any("/entries/by-puuid/" + EPU[name] in u for u in urls)


def run_edge(tag, moddir=HERE):
    return run(tag, budget=1, moddir=moddir, td=TD2, spec=EDGE, pu=EPU, rank=ERANK)


oute, urlse, jse, attrse = run_edge("edge")
ok("邊界沙盒跑完（沒有 Traceback）、出口都在自己的 tmp",
   "Traceback" not in oute and attrse.get("out", "").startswith(TD2) and attrse.get("acc", "").startswith(TD2),
   (oute[-600:], attrse))
PLE = players(jse)
ok("差 5 分鐘沒到門檻（EdgeNew）⇒ 判非閒置、照問、LP 更新成 Riot 的值、沒有 deferred",
   easked(urlse, "EdgeNew") and PLE["EdgeNew"].get("lp") == 61 and "deferred" not in PLE["EdgeNew"], PLE.get("EdgeNew"))
ok("差 5 分鐘過了門檻（EdgeOld）⇒ 判閒置、額度 0 ⇒ 延後、沿用上一版 LP、標 deferred",
   (not easked(urlse, "EdgeOld")) and PLE["EdgeOld"].get("lp") == 80 and near_now(PLE["EdgeOld"].get("deferred")),
   PLE.get("EdgeOld"))
ok("分配行：kr 直接問 2 → 這班 1（其中閒置 0）、延後 1",
   "kr 直接問 2 → 這班 1（其中閒置 0）、延後 1" in oute, [l for l in oute.splitlines() if "閒置延後" in l])

# 突變對照：把門檻挪 ∓0.01 天（14.4 分）——比 5 分鐘的邊界大、比其他樣本（1 天／5 天）小 ⇒ 只會翻邊界那兩條
NEEDLE = "if st is None or st[0] < IDLE_DAYS or st[1] >= IDLE_MAX_H:"
SRC = io.open(os.path.join(HERE, "fetch_soloq.py"), encoding="utf-8").read()
ok("找得到門檻那一行、而且全檔只有一處（突變才有鑑別力）", SRC.count(NEEDLE) == 1, SRC.count(NEEDLE))
for _i, (_lab, _expr, _who, _why) in enumerate([
        ("門檻挪早 0.01 天", "IDLE_DAYS - 0.01", "EdgeNew", "本來照問的 EdgeNew 改判閒置、換它被延後"),
        ("門檻挪晚 0.01 天", "IDLE_DAYS + 0.01", "EdgeOld", "本來被延後的 EdgeOld 改判非閒置、照問")]):
    _md = os.path.join(TD2, "mut%d" % _i)
    os.makedirs(_md, exist_ok=True)
    _mut = SRC.replace(NEEDLE, NEEDLE.replace("IDLE_DAYS", _expr, 1), 1)
    ok("%s：突變真的套進去了" % _lab, _mut != SRC and _expr in _mut)
    io.open(os.path.join(_md, "fetch_soloq.py"), "w", encoding="utf-8").write(_mut)
    _o, _u, _j, _ = run_edge("mut%d" % _i, moddir=_md)
    _p = players(_j)
    if _who == "EdgeNew":
        ok("%s ⇒ %s（證明 EdgeNew 那條有鑑別力）" % (_lab, _why),
           (not easked(_u, "EdgeNew")) and "deferred" in _p["EdgeNew"] and easked(_u, "EdgeOld"), (_p["EdgeNew"], _u))
    else:
        ok("%s ⇒ %s（證明 EdgeOld 那條有鑑別力）" % (_lab, _why),
           easked(_u, "EdgeOld") and "deferred" not in _p["EdgeOld"] and "這班延後" not in _o, (_p["EdgeOld"], _u))

print("\n⑪ 常數的理由與隔離")
ok("3（名單預抓）＋ DIRECT_BUDGET ≤ 100（Riot 每區 100/120s，重抓還有餘裕）",
   attrs.get("budget") is not None and 3 + int(attrs["budget"]) <= 100 and int(attrs["budget"]) >= 80, attrs)
ok("IDLE_DAYS ≥ 1、IDLE_MAX_H 在 24～72 之間", 1 <= int(attrs.get("idle_days") or 0) and 24 <= int(attrs.get("idle_max_h") or 0) <= 72, attrs)
ok("沙盒輸出含只有沙盒才有的 puuid（ZZPROBE9942_）", "ZZPROBE9942_" in js)
real_js = io.open(REAL[0], encoding="utf-8", errors="replace").read() if os.path.exists(REAL[0]) else ""
ok("真實 soloq.js 沒有沙盒 puuid", "ZZPROBE9942_" not in real_js)
after = [(md5(p), os.path.getmtime(p) if os.path.exists(p) else None) for p in REAL]
ok("真實 soloq.js／soloq_played.json／soloq_accounts.json 的 md5 與 mtime 前後不變", after == REAL_BEFORE, (REAL_BEFORE, after))

print("\n結果：%d 過／%d 敗" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
