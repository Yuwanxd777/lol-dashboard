# -*- coding: utf-8 -*-
"""update_health 的「Sheep 直抓來源過時」回歸測試（2026-11-22 主對話迴圈 #3541）。

背景（#3540）：X 的免登入內嵌時間軸從 11-19 晚上起整份換成凍結的舊精選，fetch_transfers 照樣 exit 0、
「新增 0 則」，44 小時沒有任何指標出聲；同一段時間 Sheep 的新消息其實一直經「PTT 轉貼＋每小時複查」進來。
哨兵拿這兩條獨立進來的同源消息互相對照（推文 ID 解出來的時間），這支守著那一行判定。

沙盒：兩個來源檔（transfers_sheep_src.json／transfers.js）全放 tempfile 目錄、透過 path 參數傳入；
另外 assert 模組層的兩個路徑常數沒被改動、正本 mtime 沒動，並放一條「只有沙盒才有」的證據（2031 年的推文）
確認讀的是沙盒。素材的形狀照真實檔（window.TRANSFERS={…,"extra":[…]}；一篇 PTT 文拆成多列共用同一個推文網址），
ID 用真實的兩則當錨；④ 另外唯讀讀一次正本，檔案形狀哪天變了（讀不出東西）會在這裡翻紅，而不是靜靜印「略過」。
每一組都有會翻面的正控制。用法：python scripts\\update_health_sheep_test.py（exit 0＝全過）
"""
import calendar
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import update_health as uh          # noqa: E402

OK = [0]
NG = []


def eq(got, want, label):
    if got == want:
        OK[0] += 1
    else:
        NG.append("%s：得到 %r，應為 %r" % (label, got, want))


def sf(epoch):
    """時間 → 那一刻的推文 ID（snowflake，序號位元補 0）。"""
    return str((int(round(epoch * 1000)) - uh.TW_EPOCH_MS) << 22)


def fmt(t):
    return time.strftime("%m-%d %H:%M", time.localtime(t))


H = 3600.0
A_REAL = "2123425961056358704"      # 真實：直抓累積檔最新一則，d＝2026-11-19 22:39（台北）
B_REAL = "2123902262271684684"      # 真實：PTT M.1795237153.A.60B 轉貼的 Sheep_Esports 推文
A_UTC = calendar.timegm((2026, 11, 19, 14, 39, 0))
NOW = calendar.timegm((2026, 11, 21, 17, 13, 0))    # 2026-11-22 01:13 台北（寫這支的時候）

REAL_PATHS = (uh.SHEEP_SRC, uh.TRANSFERS_JS, uh.BASE)
MT0 = [os.path.getmtime(p) if os.path.exists(p) else None for p in REAL_PATHS]

# ① 推文 ID → 時間
A = uh.snowflake_ts(A_REAL)
eq(0 <= A - A_UTC < 60, True, "①真實 ID 解出來＝累積檔 d 欄那一分鐘")
eq(abs(uh.snowflake_ts(sf(NOW)) - NOW) < 0.01, True, "①sf() 來回一致")
eq(uh.snowflake_ts(B_REAL) > A, True, "①轉貼那則比直抓最新一則晚")
for bad_id in ("M.1795237153.A.60B", "M.1795237153.A.60B-1", "", None, "12345"):
    eq(uh.snowflake_ts(bad_id), None, "①不是推文 ID：%r" % (bad_id,))

tmp = tempfile.mkdtemp(prefix="uh_sheep_")
P_SRC = os.path.join(tmp, "transfers_sheep_src.json")
P_JS = os.path.join(tmp, "transfers.js")


def tw(handle, tid, host="x.com", src="Sheep Esports", sub=""):
    return {"id": "M.1795237153.A.60B" + sub, "d": "2026-11-21 12:59", "zh": "…", "en": "…", "src": src,
            "url": "https://%s/%s/status/%s" % (host, handle, tid),
            "ptt": "https://www.ptt.cc/bbs/LoL/M.1795237153.A.60B.html", "st": "rumor"}


NOISE = [
    {"id": "M.1795230000.A.111", "d": "2026-11-21 20:00", "zh": "…", "src": "PTT",
     "ptt": "https://www.ptt.cc/bbs/LoL/M.1795230000.A.111.html"},                       # 沒有推文網址
    tw("ratotolol", sf(NOW - 2 * H), src="PTT"),                                         # 別人的推文
    tw("SheepEsportsBR", sf(NOW - 3 * H)), tw("SheepEsportsBR", sf(NOW - 30 * H)),       # 巴西分站＝另一條時間軸
    {"id": "o1", "d": "2026-11-20 10:00", "src": "官方", "url": "https://x.com/Brionesports/status/" + sf(NOW - 5 * H)},
]


def put(direct_ids, extra, raw_js=None):
    acc = [{"id": i, "d": "x", "en": "[SOURCES] …", "url": "https://x.com/Sheep_Esports/status/%s" % i}
           for i in direct_ids]
    io.open(P_SRC, "w", encoding="utf-8").write(json.dumps(acc, ensure_ascii=False, indent=1))
    if raw_js is None:
        raw_js = "window.TRANSFERS=" + json.dumps(
            {"at": "2026-11-22 00:17", "from": "2026-11-01", "wiki": [], "sheep": [], "extra": extra},
            ensure_ascii=False, separators=(",", ":")) + ";"
    io.open(P_JS, "w", encoding="utf-8").write(raw_js)


def run(now=NOW, **kw):
    return uh.sheep_problems(uh.sheep_direct_latest(P_SRC), uh.sheep_relay_tweets(P_JS), now, **kw)


def warned(r):
    return (r[0].startswith("⚠ 提醒：Sheep 直抓來源過時"), r[1])


OLD = [sf(A - 400 * H), sf(A - 30 * H)]
# 2026-11-22 01:13 的真實情況：比直抓新的轉貼 5 則（+12.9h／+13.6h／+14.6h／+29.3h／+31.5h）
CUR = [tw("Sheep_Esports", sf(A + h * H), sub="-%d" % i) for i, h in enumerate((12.9, 13.6, 14.6, 29.3, 31.5))]

try:
    # ② 現況（正例）與「直抓有進新的」（反例）
    put(OLD + [A_REAL], NOISE + CUR)
    r = run()
    eq(warned(r), (True, []), "②現況：提醒、不進結論")
    eq("比它新的有 5 則" in r[0], True, "②現況：比它新的 5 則（雜訊列都沒算進去）")
    eq(fmt(A) in r[0] and fmt(A + 31.5 * H) in r[0], True, "②現況：兩個時間都印出來")
    put(OLD + [A_REAL, sf(NOW - 1 * H)], NOISE + CUR)
    r = run()
    eq((r[0].startswith("Sheep 直抓：✓"), r[1]), (True, []), "②直抓一小時前才進新的 ⇒ ✓（反例）")

    # ③ 差距門檻：最新的轉貼只比直抓新 20 小時 ⇒ 不提醒；拉到 25 小時 ⇒ 提醒
    put([A_REAL], NOISE + [tw("Sheep_Esports", sf(A + 10 * H)), tw("Sheep_Esports", sf(A + 20 * H))])
    r = run()
    eq((warned(r)[0], "未達提醒門檻" in r[0]), (False, True), "③差 20h 不提醒")
    put([A_REAL], NOISE + [tw("Sheep_Esports", sf(A + 10 * H)), tw("Sheep_Esports", sf(A + 25 * H))])
    eq(warned(run()), (True, []), "③差 25h 提醒（正控制）")

    # ④ 則數門檻：只有 1 則比它新（可能是直抓過濾本來就不收的）⇒ 不提醒；同一則推文拆成三列仍算 1 則
    one = sf(A + 30 * H)
    put([A_REAL], NOISE + [tw("Sheep_Esports", one, sub="-%d" % i) for i in range(3)])
    r = run()
    eq((warned(r)[0], "有 1 則比它新" in r[0]), (False, True), "④同一則拆三列＝1 則，不提醒")
    eq(warned(run(min_newer=1)), (True, []), "④門檻降到 1 就提醒（門檻真的有在用）")
    put([A_REAL], NOISE + [tw("Sheep_Esports", one), tw("Sheep_Esports", sf(A + 31 * H))])
    eq(warned(run()), (True, []), "④兩則不同的推文 ⇒ 提醒（正控制）")

    # ⑤ 直抓停多久：47 小時不提醒、49 小時提醒
    put([A_REAL], [tw("Sheep_Esports", sf(A + 30 * H)), tw("Sheep_Esports", sf(A + 40 * H))])
    eq(warned(run(now=A + 47 * H))[0], False, "⑤停 47h 不提醒")
    eq(warned(run(now=A + 49 * H)), (True, []), "⑤停 49h 提醒（正控制）")

    # ⑥ 只認同一個帳號；大小寫／twitter.com 網域照認
    ids = [sf(A + 30 * H), sf(A + 40 * H)]
    put([A_REAL], [tw("SheepEsportsBR", i) for i in ids] + [tw("Sheep_Esports_", ids[0]), tw("xSheep_Esports", ids[1])])
    r = run()
    eq((r[0].startswith("Sheep 直抓：✓"), "推文 0 則" in r[0]), (True, True), "⑥別的帳號不算")
    put([A_REAL], [tw("sheep_esports", ids[0]), tw("Sheep_Esports", ids[1], host="twitter.com")])
    eq(warned(run()), (True, []), "⑥同帳號（小寫／twitter.com）⇒ 提醒（正控制）")
    eq(warned(uh.sheep_problems(uh.sheep_direct_latest(P_SRC),
                                uh.sheep_relay_tweets(P_JS, handle="SheepEsportsBR"), NOW))[0], False,
       "⑥handle 參數真的有在濾")

    # ⑦ 讀不到＝印「讀不到」、不提醒；讀到了但一則都沒有＝✓
    put([A_REAL], CUR)
    os.remove(P_SRC)
    r = run()
    eq(("讀不到 transfers_sheep_src.json" in r[0], r[1]), (True, []), "⑦累積檔不見")
    put([], CUR)
    eq("讀不到 transfers_sheep_src.json" in run()[0], True, "⑦累積檔是空清單")
    put([A_REAL], CUR, raw_js="window.TRANSFERS={壞掉")
    r = run()
    eq(("讀不到 transfers.js 的 extra" in r[0], r[1]), (True, []), "⑦transfers.js 壞掉")
    put([A_REAL], CUR, raw_js='window.TRANSFERS={"at":"x","wiki":[]};')
    eq("讀不到 transfers.js 的 extra" in run()[0], True, "⑦沒有 extra 鍵")
    put([A_REAL], [])
    r = run()
    eq((r[0].startswith("Sheep 直抓：✓"), "推文 0 則" in r[0], r[1]), (True, True, []), "⑦extra 是空的 ⇒ ✓")

    # ⑧ 沙盒才有的證據：2031 年的推文（正本不可能有）
    far = calendar.timegm((2031, 1, 2, 3, 4, 0))
    put([A_REAL], [tw("Sheep_Esports", sf(far)), tw("Sheep_Esports", sf(far - H))])
    r = run(now=far + H)
    eq((warned(r)[0], fmt(far) in r[0]), (True, True), "⑧讀到的是沙盒（2031 年那則）")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ⑨ 模組層路徑沒被動、還指著 repo（沙盒走的是參數，不是改常數）
eq((uh.SHEEP_SRC, uh.TRANSFERS_JS), REAL_PATHS[:2], "⑨模組層路徑沒被動")
eq(os.path.dirname(uh.SHEEP_SRC) == uh.ROOT and os.path.dirname(uh.TRANSFERS_JS) == uh.ROOT, True, "⑨預設讀 repo 根目錄")

# ⑩ 正本唯讀：檔案在就一定要讀得出東西（形狀變了會在這裡紅，不是靜靜「略過」）
if os.path.exists(uh.SHEEP_SRC) and os.path.exists(uh.TRANSFERS_JS):
    d0, r0 = uh.sheep_direct_latest(), uh.sheep_relay_tweets()
    eq(d0 is not None and d0 > A_UTC - 1, True, "⑩正本累積檔讀得到最新一則（不早於 11-19 22:39）")
    eq(isinstance(r0, dict), True, "⑩正本 transfers.js 的 extra 讀得到")
    print("   正本現況：" + uh.sheep_problems(d0, r0, time.time())[0])
    # ⑪ main() 真的有印這一行，而且提醒不進結論
    p = subprocess.run([sys.executable, os.path.join(HERE, "update_health.py"),
                        "--no-save", "--no-live", "--no-lag", "--no-soloqfresh"],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.stdout.decode("utf-8", "replace")
    lines = [x for x in out.splitlines() if "Sheep 直抓" in x]
    eq(len(lines), 1, "⑪main() 印一行 Sheep 直抓")
    concl = [x for x in out.splitlines() if x.startswith("結論：")]
    eq(len(concl) == 1 and "Sheep" not in concl[0], True, "⑪提醒不進結論")
else:
    print("   （正本沒有 transfers_sheep_src.json／transfers.js，⑩⑪ 略過）")

MT1 = [os.path.getmtime(p) if os.path.exists(p) else None for p in REAL_PATHS]
eq(MT1, MT0, "⑫正本三個檔（累積檔／transfers.js／健檢基準）mtime 沒動")

print("update_health Sheep 直抓過時：%d 過、%d 失敗" % (OK[0], len(NG)))
for x in NG:
    print("  ✗ " + x)
sys.exit(1 if NG else 0)
