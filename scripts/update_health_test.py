# -*- coding: utf-8 -*-
"""update_health.py 的回歸測試（2026-09-07 精進迴圈 #44）。

守著兩件事：
  ① `data_counts()` 要涵蓋**全部年份**——舊版 `[-3:]` 讓 2013~2023 共 11 年的縮水永遠測不到。
  ② 基準是「已知良好的高水位」——舊版無條件把本次數字存成基準，於是**縮水隔天就被吃掉**：
     第一輪報一次，存檔後基準跟著變小，之後每輪都看起來正常，問題還在卻再也不會被提醒。

每一組都配「正控制」（把條件改掉，斷言真的會翻面），否則綠燈沒有意義。
用法：python scripts\\update_health_test.py    （exit 0＝全過）
"""
import contextlib
import glob
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import update_health as uh          # noqa: E402

# ⚠ 這裡**不要**自己再包一層 stdout：update_health 匯入時已經做過
#   `sys.stdout = TextIOWrapper(sys.stdout.buffer, "utf-8")`；再包一次會讓前一層失去參照被回收，
#   TextIOWrapper 的解構順手把底層 buffer 關掉 ⇒ 之後每個 print 都 ValueError: I/O operation on closed file。

OK = [0]
NG = []


def eq(got, want, label):
    if got == want:
        OK[0] += 1
    else:
        NG.append("%s：得到 %r，應為 %r" % (label, got, want))


def state_of(rows, key):
    return {k: st for k, _, _, st in rows}.get(key)


# ── ⓪ 整份測試封網＋接管唯一的對外出口（2026-09-17 #164）──────────────────────
# #144 把逐聯賽落後接進 main() 之後，⑫⑮ 那幾次 uh.main() 都沒帶 --no-lag、也沒人接管 wiki_rows
# ⇒ 每跑一次這份測試就真的去打四次 Leaguepedia（每次含 sleep 2 秒）；_r48／_r49 每個突變都整份重跑
# ⇒ 單跑從 ~110s 拖到 ~210s、超過 suite 的 150s 逾時（#163 整批跑才發現，py-spy 停在 wiki_rows）。
# 兩層：①uh.wiki_rows 換成假出口（丟例外 ⇒ lag_problems 走 skip，main 照樣出結論）
#       ②六個網路出口全封死當保險絲。**被擋下的呼叫會被 wiki_days 的 except 吞掉、測試照樣綠**
#         ⇒ 光封網看不出漏接，所以每一次被擋都記進 NET_HITS，檔尾 assert 它是空的。
class BlockedNetwork(RuntimeError):
    pass


NET_HITS = []


def _blow(*a, **k):
    NET_HITS.append(repr(a)[:80])
    raise BlockedNetwork("測試沙箱禁止連外（有人漏接了一個網路出口）")


def block_network():
    """回傳 restore()。socket 層是保險絲：就算被測模組換用別的 http 函式庫也會在這裡炸。"""
    import socket
    import http.client
    import urllib.request
    saved = [(socket, "socket", socket.socket),
             (socket, "create_connection", socket.create_connection),
             (http.client, "HTTPSConnection", http.client.HTTPSConnection),
             (http.client, "HTTPConnection", http.client.HTTPConnection),
             (urllib.request, "urlopen", urllib.request.urlopen),
             (urllib.request, "build_opener", urllib.request.build_opener)]
    for mod, name, _ in saved:
        setattr(mod, name, _blow)

    def restore():
        for mod, name, orig in saved:
            setattr(mod, name, orig)
    return restore


WIKI_CALLS = []


def _wiki_takeover(since, timeout=90):
    WIKI_CALLS.append(since)
    raise IOError("測試接管：不連 Leaguepedia")


_restore_net_all = block_network()
_real_wiki_rows = uh.wiki_rows
uh.wiki_rows = _wiki_takeover
# 正控制：封鎖器真的會擋、而且真的會記帳（否則檔尾「NET_HITS 是空的」可能只是記帳壞了）
try:
    import urllib.request as _ur0
    _ur0.urlopen("https://lol.fandom.com/")
    NG.append("⓪封鎖器沒作用：urlopen 居然通了")
except BlockedNetwork:
    eq(len(NET_HITS), 1, "⓪正控制：被擋下的呼叫有記進 NET_HITS")
del NET_HITS[:]
# 正控制：真出口 wiki_rows 在封網下一定會撞到封鎖器（證明「不接管就會被記帳」，不是它根本不連網）
try:
    _real_wiki_rows("2026-09-01", timeout=1)
    NG.append("⓪真的 wiki_rows 在封網下居然回傳了")
except BlockedNetwork:
    eq(len(NET_HITS) >= 1, True, "⓪正控制：真出口 wiki_rows 會撞封鎖器、被記帳")
except Exception as _e0:
    NG.append("⓪真的 wiki_rows 撞到的不是封鎖器：%s" % _e0)
del NET_HITS[:]


# ── ① is_hard：哪些項目「只會增不會減」──────────────────────────────────
for k in ("data_2013.js", "data_2026.js", "side_sel.games"):
    eq(uh.is_hard(k), True, "is_hard 硬性 %s" % k)
for k in ("soloq.players", "soloq.found", "soloq_matches.files"):
    eq(uh.is_hard(k), False, "is_hard 軟性 %s" % k)

# ── ② 硬性縮水：狀態＝shrink，且不寫回基準（高水位）─────────────────────
prev = {"data_2024.js": 19447, "side_sel.games": 2628, "soloq.players": 1091}
cur = {"data_2024.js": 19000, "side_sel.games": 2628, "soloq.players": 1091}
rows = uh.diff_counts(prev, cur)
eq(state_of(rows, "data_2024.js"), "shrink", "②縮水狀態")
eq(uh.merge_baseline(prev, cur)["data_2024.js"], 19447, "②縮水不寫回（保住高水位）")
# 正控制：--accept 才把較小值寫成新基準
eq(uh.merge_baseline(prev, cur, accept=True)["data_2024.js"], 19000, "②正控制：accept 寫回小值")

# ── ③ 本輪的核心回歸：縮水不可以「隔天被吃掉」───────────────────────────
# 模擬兩輪：22:00 的 run 讓 data_2024 掉了 447 列 → 第一輪報一次、存基準 →
# 第二輪再跑（資料還是壞的、數字沒變）→ **必須還是 shrink**。舊版會變成 ok。
base1 = uh.merge_baseline(prev, cur)                 # 第一輪存下的基準
rows2 = uh.diff_counts(base1, cur)                   # 第二輪再比一次
eq(state_of(rows2, "data_2024.js"), "shrink", "③第二輪仍然報縮水（不被吃掉）")
# 正控制：如果第一輪像舊版那樣無條件寫回，第二輪就變成 ok（＝問題被吃掉了）
old_style = dict(prev); old_style.update(cur)
eq(state_of(uh.diff_counts(old_style, cur), "data_2024.js"), "ok", "③正控制：舊寫法第二輪就變 ok")
# 資料恢復之後要自己回到 ok，不需要人工介入
eq(state_of(uh.diff_counts(base1, {"data_2024.js": 19447}), "data_2024.js"), "ok", "③恢復後自動回 ok")

# ── ④ 軟性減少：選手離隊／清孤兒逐場檔，合理，照常更新基準 ───────────────
prev4 = {"soloq.players": 1091, "soloq_matches.files": 428}
cur4 = {"soloq.players": 1080, "soloq_matches.files": 425}
rows4 = uh.diff_counts(prev4, cur4)
eq(state_of(rows4, "soloq.players"), "soft_down", "④軟性減少狀態")
eq(uh.merge_baseline(prev4, cur4), cur4, "④軟性減少照常寫回基準")

# ── ⑤ 讀不到（None）：不可以拿 None 蓋掉舊基準 ─────────────────────────
prev5 = {"data_2025.js": 16357}
cur5 = {"data_2025.js": None}
eq(state_of(uh.diff_counts(prev5, cur5), "data_2025.js"), "unreadable", "⑤讀不到狀態")
eq(uh.merge_baseline(prev5, cur5)["data_2025.js"], 16357, "⑤讀不到不覆蓋基準")
eq(uh.merge_baseline(prev5, cur5, accept=True)["data_2025.js"], 16357, "⑤accept 也不覆蓋")

# ── ⑥ 新項目與成長 ──────────────────────────────────────────────────
rows6 = uh.diff_counts({}, {"data_2027.js": 12})
eq(state_of(rows6, "data_2027.js"), "new", "⑥沒有基準＝新項目")
eq(uh.merge_baseline({}, {"data_2027.js": 12}), {"data_2027.js": 12}, "⑥新項目寫進基準")
eq(state_of(uh.diff_counts({"data_2026.js": 16370}, {"data_2026.js": 16400}), "data_2026.js"),
   "ok", "⑥成長＝ok")
eq(uh.merge_baseline({"data_2026.js": 16370}, {"data_2026.js": 16400})["data_2026.js"],
   16400, "⑥成長更新基準")
# 基準裡有、這次沒量到的項目要留著（不要因為少量一項就把歷史高水位丟掉）
eq(uh.merge_baseline({"側": 5}, {"data_2026.js": 1}), {"側": 5, "data_2026.js": 1}, "⑥舊項目保留")

# ── ⑦ 真實資料端到端：data_counts 要涵蓋 data/ 下**每一個**年份檔 ────────
years = sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "data", "data_20*.js")))
dc = uh.data_counts()
eq([k for k in dc if k.startswith("data_")], years, "⑦涵蓋全部年份（不是只有最近 3 年）")
eq(len(years) >= 14, True, "⑦年份檔至少 14 個")
eq(all(isinstance(dc[y], int) and dc[y] > 0 for y in years), True, "⑦每年都讀得到列數")
eq("data_2013.js" in dc, True, "⑦最早那年也在（舊版 [-3:] 會漏）")

# ── ⑧ 真實資料：現況對現況比對不可以出現任何 shrink ─────────────────────
eq([k for k, _, _, st in uh.diff_counts(dc, dc) if st == "shrink"], [], "⑧自己比自己沒有縮水")

# ── ⑨ log_age_min：這份日誌有多舊（#47）────────────────────────────────
NOW = time.mktime(time.strptime("2026-09-07 22:30:00", "%Y-%m-%d %H:%M:%S"))
eq(round(uh.log_age_min("2026-09-07 22:00:00", None, NOW)), 30, "⑨用日誌裡 run_update 的開始時間")
# 關鍵：publish.bat 在健檢之後會 type 結論進 update_log.txt，mtime 因此永遠是「剛剛」。
# 只看 mtime 的話，一份 12 小時前的舊日誌會被當成新鮮的。
eq(round(uh.log_age_min("2026-09-07 10:00:00", NOW, NOW)), 750, "⑨內容優先於 mtime（mtime 剛被 type 更新過也騙不到）")
eq(round(uh.log_age_min(None, NOW - 3600, NOW)), 60, "⑨沒有時間戳才退回 mtime")
eq(uh.log_age_min(None, None, NOW), None, "⑨兩個都沒有＝年齡不明")
eq(uh.log_age_min("壞掉的時間戳", None, NOW), None, "⑨時間戳解析失敗又沒 mtime")
eq(uh.log_age_min("2026-09-08 00:00:00", None, NOW), 0.0, "⑨時鐘漂移的負值夾成 0")

# ── ⑩ run_problems：這一班到底有沒有真的跑（#47 的核心）──────────────────
FULL = {"runs": [("2026-09-07 22:00:01", "4")], "steps": [("a", 1.0, 0)]}
EMPTY = {"runs": [], "steps": []}
STARTED = {"runs": [("2026-09-07 22:00:01", "4")], "steps": []}
eq(uh.run_problems(FULL, 30, uh.FRESH_MIN), [], "⑩正常一班：沒問題")


def why(lg, age, fresh=uh.FRESH_MIN):
    """把訊息接成一條字串再比對——只斷言「有幾條」抓不到「報錯了原因」：
    2026-09-07 的突變對照就漏抓過一個（把「沒有 run_update」那條拿掉之後，
    空日誌照樣因為「0 個步驟」而報 1 條，數量沒變、原因全錯）。"""
    return "／".join(uh.run_problems(lg, age, fresh))


eq(why(EMPTY, 0), "日誌裡沒有 run_update（這一班的更新根本沒開始跑）", "⑩日誌裡沒有 run_update ⇒ 異常（且說得出是這個原因）")
eq(why(STARTED, 30), "run_update 有開始、卻一個步驟都沒跑完", "⑩有開始卻 0 個步驟 ⇒ 異常（且說得出是這個原因）")
eq(uh.run_problems(None, None, uh.FRESH_MIN), ["找不到 update_log.txt（這一班沒有寫出任何日誌）"],
   "⑩連日誌都沒有 ⇒ 異常")
# 這條就是 2026-09-06 10:00 的形狀：日誌整份是上一班的，內容完美無缺
eq("沒有寫新日誌" in why(FULL, 12 * 60), True, "⑩12 小時前的舊日誌 ⇒ 異常（不新鮮）")
eq(why(FULL, uh.FRESH_MIN - 1), "", "⑩剛好在門檻內：不報")
eq("沒有寫新日誌" in why(FULL, uh.FRESH_MIN + 1), True, "⑩剛好超過門檻：報")
eq("無法判斷" in why(FULL, None), True, "⑩年齡不明也算異常（publish 模式）")
# 手動跑（迴圈每輪查，常常落在兩班之間）不判新鮮度，但「有沒有跑」照樣要問
eq(why(FULL, 12 * 60, None), "", "⑩手動模式：舊日誌不報")
eq(why(FULL, None, None), "", "⑩手動模式：年齡不明不報")
eq("沒有 run_update" in why(EMPTY, 12 * 60, None), True, "⑩手動模式：沒有 run_update 還是要報")
eq(uh.FRESH_MIN > 94 + 30, True, "⑩門檻要大於最久那次（94 分退回循序）加緩衝")
eq(uh.FRESH_MIN < 12 * 60, True, "⑩門檻要小於兩班間隔 12 小時，否則舊日誌照樣過關")

# ── ⑫ 排程班次點名：publish.bat 整個沒被叫起來，也要有人出聲（#48）──────────
def T(s):
    return time.mktime(time.strptime(s, "%Y-%m-%d %H:%M:%S"))


def shift_at(now, boundary):
    eq(uh.last_shift_ts(T(now)), T(boundary), "⑫%s 的上一班＝%s" % (now[11:16], boundary[5:16]))


shift_at("2026-09-07 17:47:00", "2026-09-07 10:00:00")
shift_at("2026-09-07 09:59:00", "2026-09-06 22:00:00")     # 跨午夜要取到昨天 22:00
shift_at("2026-09-07 22:00:00", "2026-09-07 22:00:00")     # 剛好在班次時刻
shift_at("2026-09-08 00:30:00", "2026-09-07 22:00:00")


def swhy(start_at, now):
    """同⑩：把訊息接成字串再比對，只數「幾條」抓不到「報錯了原因」。"""
    return "／".join(uh.shift_problems(start_at, T(now))[0])


def snote(start_at, now):
    return uh.shift_problems(start_at, T(now))[1]


eq(swhy("2026-09-07 10:00:05", "2026-09-07 17:47:00"), "", "⑫這一班有跑：不報")
eq("✓ 已跑" in snote("2026-09-07 10:00:05", "2026-09-07 17:47:00"), True, "⑫說明行講得出已跑")
# 這條就是 #48 要補的洞：排程沒被叫起來 ⇒ 沒有新日誌、沒有 HEALTH_ALERT.txt、
# 手動健檢又不判年齡 ⇒ 從頭到尾沒有任何檢查出聲。
eq("上一班 09-07 10:00 沒跑" in swhy("2026-09-06 22:00:01", "2026-09-07 17:47:00"), True,
   "⑫排程沒跑（日誌還是上一班的）⇒ 異常，且指得出是哪一班")
eq("publish.bat 這一班沒被叫起來" in swhy("2026-09-06 22:00:01", "2026-09-07 17:47:00"), True,
   "⑫訊息要說出根因（不是只說日誌舊）")
# 寬限：剛過班次時間、或排程被 Windows「錯過就盡快補跑」延後，都不可以誤報
eq(swhy("2026-09-06 22:00:01", "2026-09-07 10:30:00"), "", "⑫班次後 30 分鐘（寬限內）：不報")
eq(swhy("2026-09-06 22:00:01", "2026-09-07 12:59:00"), "", "⑫剛好在寬限內：不報")
eq("沒跑" in swhy("2026-09-06 22:00:01", "2026-09-07 13:01:00"), True, "⑫剛好超過寬限：報")
eq(swhy("2026-09-07 09:57:00", "2026-09-07 17:47:00"), "", "⑫日誌早 3 分鐘（排程抖動）仍算這一班")
eq("沒有 run_update 時間戳" in swhy(None, "2026-09-07 17:47:00"), True, "⑫連時間戳都沒有＝沒跑")
eq(swhy(None, "2026-09-07 10:30:00"), "", "⑫沒有時間戳但還在寬限內：不報")
# 為什麼不能用 ⑩ 的固定年齡代替：迴圈每輪手動跑常落在兩班之間，
# 同一份「今天 10:00 跑過」的日誌，固定年齡會誤報、班次點名不會（正反對照）。
eq("沒有寫新日誌" in why(FULL, 11.9 * 60), True, "⑫對照：固定年齡對 11.9 小時前的日誌會報")
eq(swhy("2026-09-07 10:00:05", "2026-09-07 21:55:00"), "", "⑫同一份日誌用班次點名不報（手動跑不誤報）")
eq(uh.SHIFT_GRACE_MIN < 12 * 60, True, "⑫寬限要小於兩班間隔，否則永遠來不及在下一班前發現")
eq(uh.SHIFT_GRACE_MIN > 94, True, "⑫寬限要大於最久那次（94 分退回循序）")
eq(uh.start_ts("2026-09-07 10:00:05"), T("2026-09-07 10:00:05"), "⑫start_ts 正常解析")
eq(uh.start_ts("壞掉"), None, "⑫start_ts 壞格式回 None")
eq(uh.start_ts(None), None, "⑫start_ts 沒有值回 None")

# ── ⑪ 自我污染：健檢結論被 type 折進日誌後，下次 parse 不可以讀出新的 run／步驟 ──
_real_log, _real_console = uh.LOG, uh.CONSOLE
try:
    tmp = tempfile.mkdtemp(prefix="uh_test_")
    src = io.open(os.path.join(ROOT, "update_log.txt"), encoding="utf-8", errors="replace").read()
    uh.CONSOLE = os.path.join(tmp, "no_console.txt")
    uh.LOG = os.path.join(tmp, "log.txt")
    io.open(uh.LOG, "w", encoding="utf-8").write(src)
    before = uh.parse_log()
    verdict = ("═══ 資料更新健檢 2026-09-07 22:31 ═══\n"
               "日誌：2026-09-07 22:00:01（0.5 小時前）\n"
               "班次 09-07 22:00：✓ 已跑（日誌 2026-09-07 22:00:01）\n"
               "run_update：2026-09-07 22:00:01（並行 4）\n"
               "步驟 42 個、相加 28.2 分鐘；最久的 8 步：\n"
               "   fetch_soloq_matches            639.5s  ⚠ exit 3\n"
               "那一班的日誌快照（不是現況）：守門：✓／push：✓／lint 錯誤級：0\n"
               "可疑同名：0（現況重算；那一班日誌是 10，已經是舊帳）\n"
               "結論：⚠ 日誌是 7.5 小時前的（>240 分鐘）⇒ 這一班沒有寫新日誌\n")
    io.open(uh.LOG, "a", encoding="utf-8").write(verdict * 3)
    after = uh.parse_log()
    for k in ("runs", "steps", "start_at", "preflight_fail", "lint_err", "dup", "tracebacks"):
        eq(after[k], before[k], "⑪折進日誌三次後 %s 不變" % k)
    # 正控制：真的多一個步驟行就一定要被讀到，否則這組測試是死的
    io.open(uh.LOG, "a", encoding="utf-8").write("---- 假步驟（12.3s，exit 7）----\n")
    eq(len(uh.parse_log()["steps"]), len(before["steps"]) + 1, "⑪正控制：真的步驟行讀得到")
finally:
    uh.LOG, uh.CONSOLE = _real_log, _real_console
    shutil.rmtree(tmp, ignore_errors=True)

# ── ⑫⑮ 共用：一份種齊的乾淨假 repo（2026-09-17 #165）─────────────────────────────
# ⑫⑮ 以前讓 main() 讀**真的** repo（14 個年度檔 194MB＋真基準）：逐段量（autopilot/_m165_uht_sections.py）
# 這兩段佔整份 13.9 秒裡的 8.9 秒，而 _r48／_r49 每個突變都整份重跑 ⇒ _r48 117 秒、離 suite 的 150 秒只剩 22%。
# 這兩段測的是「接線」（班次點名／可疑同名有沒有進結論），真實資料端到端另有 ⑦⑧⑰⑲㉔ 負責。
# 照 #99「種一份乾淨的假 repo、只接管 ROOT／LOG／BASE」：不對 main 的內部簽名做任何假設；
# 基準也不手寫 JSON，由 main() 自己在沙盒存一次（格式跟著 main 走）。
# 只有沙盒才有的證據：data_2026.js 計數 4（表頭＋3 局）、步驟 3 步（真 repo 一萬多列、43 步）⇒ 斷言輸出裡是這兩個數，
# 證明 main 讀的是沙盒；真基準的 size＋mtime_ns 前後比對，證明沒被寫到。
SEED_STEPS = ["fetch_data", "fetch_soloq_auto", "zz_uht_probe_step_9942"]
_REAL_BASE_PATH = uh.BASE


def _stat_of(p):
    try:
        st = os.stat(p)
        return (st.st_size, st.st_mtime_ns)
    except OSError:
        return None


def _days_ago(n):
    return time.strftime("%Y-%m-%d", time.localtime(time.time() - n * 86400))


def seed_clean_repo(box):
    """健檢的每一個證據來源都種齊（照 autopilot/_m101_steps_test.seed_repo）；缺一個結論就恆紅。"""
    def w(rel, text):
        p = os.path.join(box, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        io.open(p, "w", encoding="utf-8").write(text)
    body = [["league", "split", "date", "game", "patch"]] + [
        ["LPL", "S3", _days_ago(i), str(i), "16.17"] for i in range(3)]
    w("data/data_2026.js", "window.LOL_DATA=" + json.dumps({"tabs": {"RAW_DATA": body}}) + ";")
    w("soloq.js", "window.SOLOQ=" + json.dumps({"players": [{"found": True}]}) + ";")
    w("side_sel.js", "window.SIDE=[1,2,3];")
    for i in range(25):      # 積分逐場新鮮度：最新一局 <30h、>=20 個檔跟著動
        w("soloq_matches/p%02d.js" % i, 'window.SQM=[{"t":%d}];' % int((time.time() - 3600) * 1000))
    w("patches.js", 'window.LOL_PATCHES={"26.17":{"某英雄":["x"]}};')
    w("patches_en.js", 'window.LOL_PATCHES_EN={"26.17":{"Champ":["x"]}};')
    w("skills.js", "window.SKILLS=" + json.dumps({"v": "16.17.1", "d": {}}) + ";")
    w("assets.js", "window.ASSETS=" + json.dumps({"years": {"2026": "16.17.1"}}) + ";")
    w("csv_cache/patch_dates.json", json.dumps({"26.17": _days_ago(16)}))
    os.makedirs(os.path.join(box, "autopilot"), exist_ok=True)


def point_clean(box):
    uh.ROOT = box
    uh.BASE = os.path.join(box, "autopilot", "UPDATE_BASELINE.json")


_REAL_BASE_STAT = _stat_of(_REAL_BASE_PATH)
UHT_BOX = tempfile.mkdtemp(prefix="uh_clean_repo_")
seed_clean_repo(UHT_BOX)
_real_seed = (uh.ROOT, uh.BASE, uh.LOG, uh.CONSOLE, sys.argv)
try:
    point_clean(UHT_BOX)
    uh.LOG = os.path.join(UHT_BOX, "update_log.txt")
    uh.CONSOLE = os.path.join(UHT_BOX, "update_console.txt")
    io.open(uh.LOG, "w", encoding="utf-8").write(
        "==== run_update %s（並行 4）====\n" % time.strftime("%Y-%m-%d %H:%M:%S")
        + "".join("---- %s（1.0s，exit 0）----\n" % n for n in SEED_STEPS)
        + "文本體檢：掃描 1 條字串 → 錯誤 0、提醒 0\n未審定的可疑同名 0\n守門通過\n")
    sys.argv = ["update_health.py", "--no-live"]          # 存檔模式：讓 main 自己在沙盒建基準
    _sbuf = io.StringIO()
    with contextlib.redirect_stdout(_sbuf):
        _seed_rc = uh.main()
    _seed_out = _sbuf.getvalue()
finally:
    uh.ROOT, uh.BASE, uh.LOG, uh.CONSOLE, sys.argv = _real_seed
eq(_seed_rc, 0, "⑫⑮前提：假 repo 種齊 ⇒ main 第一次跑就沒有異常（否則後面的「乾淨」斷言是空測）%s"
   % ("" if _seed_rc == 0 else "\n" + _seed_out))
eq(os.path.exists(os.path.join(UHT_BOX, "autopilot", "UPDATE_BASELINE.json")), True,
   "⑫⑮前提：基準存進了沙盒")
eq(uh.BASE, _REAL_BASE_PATH, "⑫⑮前提：種完之後 BASE 已還原")

# ── ⑬ 端到端：main() 真的把班次點名接進結論（純函式對了、接線斷了一樣沒人知道）──
# 不寫死時鐘：拿「上一班再往前一小時」當日誌時間（⇒ 一定不是這一班寫的），
# 然後斷言 main() 的結論**與 shift_problems 的判斷一致**——寬限期內就不該報，過了寬限就一定要報。
_real_log, _real_console, _real_argv, _real_grace = uh.LOG, uh.CONSOLE, sys.argv, uh.SHIFT_GRACE_MIN
_real_root12, _real_base12 = uh.ROOT, uh.BASE
try:
    tmp = tempfile.mkdtemp(prefix="uh_e2e_")
    uh.SHIFT_GRACE_MIN = 0        # 寬限歸零＝不管這一輪幾點跑，舊日誌一定要被判定成「沒跑」
    uh.CONSOLE = os.path.join(tmp, "no_console.txt")
    uh.LOG = os.path.join(tmp, "log.txt")
    point_clean(UHT_BOX)          # #165：讀種齊的假 repo（基準也是沙盒那份），不再讀 194MB 真資料
    sys.argv = ["update_health.py", "--no-save", "--no-live"]   # 這組測班次，不必真的去掃 26MB 算同名

    # 假日誌的步驟要**跟基準一致**（2026-09-10 #103）：原本只寫一步 fetch_x，
    # #101 的步驟哨兵上線並存進基準之後，這份日誌每次都被判「少了 43 步」⇒ 結論永遠帶著一大串噪音。
    # 這一段測的是班次點名，不該被別條哨兵的訊息干擾（＝#99「種一份乾淨的假 repo」同一個道理）。
    try:
        _base_steps = (json.load(io.open(uh.BASE, encoding="utf-8")).get("steps") or [])
    except Exception:
        _base_steps = []
    _steps = _base_steps or ["fetch_x"]

    def main_out(when_ts):
        s = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(when_ts))
        io.open(uh.LOG, "w", encoding="utf-8").write(
            "==== run_update %s（並行 4）====\n" % s
            + "".join("---- %s（1.0s，exit 0）----\n" % n for n in _steps)
            + "文本體檢：掃描 1 條字串 → 錯誤 0、提醒 0\n未審定的可疑同名 0\n守門通過\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            uh.main()
        return s, buf.getvalue()

    b = uh.last_shift_ts(time.time())
    stale, out = main_out(b - 3600)                       # 上一班之前的舊日誌
    want_bad = bool(uh.shift_problems(stale, time.time())[0])
    eq(want_bad, True, "⑬前提：寬限 0 時舊日誌一定判沒跑（否則下一條是空測）")
    # ⑬b（2026-09-09 #96）：上面那條「寬限歸零」只有在**班次後 180 分鐘內**才分得出旗標有沒有生效
    # ——其餘時段 elapsed 早就超過 180，即使 monkeypatch 沒作用也會回 bad ⇒ 白天綠、晚上紅。
    # 這兩條不看時鐘：把寬限調到大到不可能過 ⇒ 一定「還不判」；調回 0 ⇒ 一定要報。
    # 舊寫法 `grace_min=SHIFT_GRACE_MIN` 是 import 當下綁死的預設值，這裡會直接紅。
    uh.SHIFT_GRACE_MIN = 10 ** 6
    eq(uh.shift_problems(stale, time.time())[0], [],
       "⑬b 寬限調到 10^6 分 ⇒ 不判（證明旗標是呼叫時才取，不是 import 綁死）")
    eq("還不判" in uh.shift_problems(stale, time.time())[1], True, "⑬b 說明行說「還不判」")
    uh.SHIFT_GRACE_MIN = 0
    eq(bool(uh.shift_problems(stale, time.time())[0]), True,
       "⑬b 正控制：寬限歸零又要報（證明上一條不是恆回空）")
    concl = [l for l in out.splitlines() if l.startswith("結論：")][0]
    eq(any(l.startswith("班次 ") for l in out.splitlines()), True, "⑬main() 有印出班次那一行")
    # 關鍵字用班次訊息自己的開頭「上一班 」，不用「沒跑」（2026-09-10 #103）：
    # #101 的步驟哨兵訊息尾巴就是「基準有、這一班**沒跑**到」⇒ 舊寫法在舊日誌那邊變成假綠
    # （綠的原因是步驟不見了，不是班次點名），在正控制那邊直接紅。DAILY.md #101 的 ⚠ 已預告這個撞名。
    eq("上一班 " in concl, want_bad, "⑬main() 的結論與班次點名一致（舊日誌）")
    # 正控制：日誌換成這一班寫的、步驟也齊 ⇒ 結論不可以再點班次，而且整份要乾淨
    fresh, out2 = main_out(b + 300)
    concl2 = [l for l in out2.splitlines() if l.startswith("結論：")][0]
    eq("上一班 " in concl2, False, "⑬正控制：這一班的日誌 ⇒ 結論不點班次")
    eq("✓ 已跑" in out2, True, "⑬正控制：說明行說已跑")
    eq("步驟不見了" in concl2, False, "⑬正控制：假日誌步驟已對齊基準 ⇒ 結論不該有步驟噪音")
    eq(bool(_base_steps), True, "⑬前提：基準裡真的有 steps（否則上一條是空測）")
    # #165：假 repo 種齊 ⇒ 這一班的日誌那次整份要乾淨（以前讀真 repo 只能斷言「不點班次」）
    eq(concl2, "結論：✓ 沒有異常", "⑬正控制：乾淨假 repo＋這一班的日誌 ⇒ 結論整份乾淨")
    eq(bool(re.search(r"data_2026\.js\s+4\s", out2)) and "data_2013.js" not in out2, True,
       "⑬沙盒證據：main 讀的是假 repo（data_2026.js 計數 4、沒有 2013 檔）")
    eq("基準 %d 個都在" % len(SEED_STEPS) in out2, True, "⑬沙盒證據：步驟基準是沙盒那 3 步（真基準是 43 步）")
finally:
    uh.LOG, uh.CONSOLE, sys.argv = _real_log, _real_console, _real_argv
    uh.ROOT, uh.BASE = _real_root12, _real_base12
    uh.SHIFT_GRACE_MIN = _real_grace
    shutil.rmtree(tmp, ignore_errors=True)

# ── ⑭ 可疑同名：日誌快照 vs 現況（#49 的純函式）─────────────────────────────
eq(uh.parse_dup_quiet("[check_player_dup] 選手 ID 4087 個，未審定的可疑同名 10 個（跑 … 看明細）"),
   10, "⑭parse：抓得到 10")
eq(uh.parse_dup_quiet("[check_player_dup] 選手 ID 4087 個，未審定的可疑同名 0 個"),
   0, "⑭parse：0 是數字不是 None（0 和「算不出來」不可以混為一談）")
eq(uh.parse_dup_quiet("Traceback (most recent call last)"), None, "⑭parse：認不得回 None")
eq(uh.parse_dup_quiet(None), None, "⑭parse：None 不炸")

eq(uh.dup_line(10, 0, ""), "可疑同名：0（現況重算；那一班日誌是 10，已經是舊帳）",
   "⑭line：今天真的發生過的那種（班後才審定）")
eq(uh.dup_line(0, 0, ""), "可疑同名：0（現況重算）", "⑭line：一樣就不囉嗦")
eq(uh.dup_line(0, 5, ""), "可疑同名：5（現況重算；那一班日誌是 0，已經是舊帳）",
   "⑭line：反向（快照 0、現況 5）＝假綠，一定要講")
eq(uh.dup_line(None, 3, ""), "可疑同名：3（現況重算）", "⑭line：沒有快照也照樣報現況")
eq(uh.dup_line(10, None, "重算逾時（>180s）"), "可疑同名：10（那一班日誌的舊數字；重算逾時（>180s））",
   "⑭line：算不出來要明講印的是舊數字")
eq(uh.dup_line(None, None, ""), "可疑同名：？（那一班日誌的舊數字；現況算不出來）", "⑭line：兩邊都沒有")

_real_root = uh.ROOT
try:
    uh.ROOT = tempfile.mkdtemp(prefix="uh_noroot_")     # 腳本不在 ⇒ 只能回 None，不可以丟例外
    _n, _e = uh.live_dup()
    eq((_n, bool(_e)), (None, True), "⑭live_dup：找不到 check_player_dup.py 回 None＋說明")
finally:
    shutil.rmtree(uh.ROOT, ignore_errors=True)
    uh.ROOT = _real_root

# ── ⑮ 端到端：main() 的可疑同名要走現況，不是印日誌快照（專打接線，#48 的教訓）──
_real_log, _real_console, _real_argv, _real_live = uh.LOG, uh.CONSOLE, sys.argv, uh.live_dup
_real_root15, _real_base15 = uh.ROOT, uh.BASE
_dup_outs = []
try:
    tmp = tempfile.mkdtemp(prefix="uh_dup_e2e_")
    uh.CONSOLE = os.path.join(tmp, "no_console.txt")
    uh.LOG = os.path.join(tmp, "log.txt")
    point_clean(UHT_BOX)          # #165：同 ⑫，讀種齊的假 repo
    io.open(uh.LOG, "w", encoding="utf-8").write(
        "==== run_update %s（並行 4）====\n---- fetch_x（1.0s，exit 0）----\n"
        "[check_player_dup] 選手 ID 4087 個，未審定的可疑同名 10 個\n守門通過\n"
        % time.strftime("%Y-%m-%d %H:%M:%S"))
    uh.live_dup = lambda timeout=None: (0, "")          # 假現況：那一班之後已經審定完

    def dup_lines(argv):
        sys.argv = argv
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            uh.main()
        _dup_outs.append(buf.getvalue())
        return [l for l in buf.getvalue().splitlines() if l.startswith("可疑同名：")]

    eq(dup_lines(["update_health.py", "--no-save"]),
       ["可疑同名：0（現況重算；那一班日誌是 10，已經是舊帳）"], "⑮main() 印的是現況不是快照")
    # 正控制：--no-live 就該退回快照那個舊數字，否則上面那條可能是恆真的
    eq(dup_lines(["update_health.py", "--no-save", "--no-live"]),
       ["可疑同名：10（那一班日誌的舊數字；--no-live 跳過重算）"], "⑮正控制：--no-live 退回快照 10")
    eq([bool(re.search(r"data_2026\.js\s+4\s", o)) and "data_2013.js" not in o for o in _dup_outs],
       [True, True], "⑮沙盒證據：兩次 main 都讀假 repo（data_2026.js 計數 4、沒有 2013 檔）")
finally:
    uh.LOG, uh.CONSOLE, sys.argv, uh.live_dup = _real_log, _real_console, _real_argv, _real_live
    uh.ROOT, uh.BASE = _real_root15, _real_base15
    shutil.rmtree(tmp, ignore_errors=True)

# ── ⑫⑮ 收尾：真基準一個位元沒動、路徑常數都還原、沙盒刪掉 ─────────────────────────
eq(_stat_of(_REAL_BASE_PATH), _REAL_BASE_STAT, "⑫⑮真的 UPDATE_BASELINE.json 沒被寫到（size＋mtime_ns 前後一致）")
eq((uh.ROOT, uh.BASE), (ROOT, _REAL_BASE_PATH), "⑫⑮ ROOT／BASE 已還原成真 repo")
# 沒還原就強制拉回來：後面 ⑰⑲㉔ 讀真資料，指著已刪的沙盒會直接 KeyError 崩掉、
# 上面那條 NG 連印都印不出來（#165 突變實測）。
uh.ROOT, uh.BASE = ROOT, _REAL_BASE_PATH
shutil.rmtree(UHT_BOX, ignore_errors=True)

# ── ⑯ 最新一場比賽（#98）：列數擋「變少」，這一組擋「不再變多」──────────────
HDR = ["league", "date", "patch"]
eq(uh.max_date([HDR, ["LPL", "2026-09-08", "16.17"], ["LCK", "2026-09-01", "16.17"]]),
   "2026-09-08", "⑯取最大的日期不是最後一列")
eq(uh.max_date([HDR, ["LPL", "2026-09-08 12:00:00", "16.17"]]), "2026-09-08", "⑯帶時間也切得出日期")
eq(uh.max_date([HDR, ["LPL", "", "16.17"], ["LCK", None, "16.17"]]), None, "⑯全是空值＝None")
eq(uh.max_date([HDR, ["LPL", "不是日期", "16.17"]]), None, "⑯認不得的格式不當日期")
eq(uh.max_date([["league", "patch"], ["LPL", "16.17"]]), None, "⑯沒有 date 欄就 None（不是丟例外）")
# 欄位一律 hdr.index 查：把 date 換到別的位置，答案要一樣（正控制＝硬編偏移會在這裡翻面）
eq(uh.max_date([["patch", "league", "date"], ["16.17", "LPL", "2026-09-08"]]),
   "2026-09-08", "⑯正控制：date 換欄位照樣讀得到")

eq(uh.newest({"data_2025.js": "2025-11-09", "data_2026.js": "2026-09-08"}),
   ("data_2026.js", "2026-09-08"), "⑯newest 取全庫最新")
eq(uh.newest({"data_2026.js": None}), (None, None), "⑯newest 全空＝(None, None)")
NOW98 = time.mktime(time.strptime("2026-09-10 00:50:00", "%Y-%m-%d %H:%M:%S"))
eq(uh.days_since("2026-09-08", NOW98), 2, "⑯days_since")


def lp(prev, cur, now=NOW98, stale=uh.STALE_DAYS):
    line, bad = uh.latest_problems(prev, cur, now, stale)
    return (line, "／".join(bad))


FRESH = {"data_2026.js": "2026-09-08"}
eq(lp({"data_2026.js": "2026-09-08"}, FRESH)[1], "", "⑯沒往前不算異常（賽季空窗最長 69 天）")
eq(lp({"data_2026.js": "2026-09-08"}, FRESH)[0],
   "最新一場比賽：2026-09-08（data_2026.js，2 天前）；基準同一天（沒往前）", "⑯沒往前那一行照樣印出來")
eq(lp({"data_2026.js": "2026-09-07"}, FRESH)[0].endswith("基準 2026-09-07（+1 天）"), True, "⑯往前一天")
eq(lp({}, FRESH)[0].endswith("基準沒這項（新項目）"), True, "⑯第一次跑＝新項目")
# ① 倒退＝硬性異常（比賽被刪或 date 欄解析壞了），而且要指名是哪一年
eq(lp({"data_2026.js": "2026-09-08"}, {"data_2026.js": "2026-08-01"})[1],
   "data_2026.js 最新比賽日期倒退（基準 2026-09-08 → 現在 2026-08-01）", "⑯倒退＝異常")
# 別的年份倒退、最新那年沒事 ⇒ 照樣要抓到（不能只看 newest 那一個檔）
eq(lp({"data_2025.js": "2025-11-09", "data_2026.js": "2026-09-08"},
      {"data_2025.js": "2025-06-01", "data_2026.js": "2026-09-08"})[1],
   "data_2025.js 最新比賽日期倒退（基準 2025-11-09 → 現在 2025-06-01）", "⑯舊年份倒退也抓（正控制）")
# ② 超過 STALE_DAYS 才算停更：69 天（史上最長空窗）不報、76 天才報
eq(lp({}, {"data_2026.js": "2026-07-03"})[1], "", "⑯69 天不報（2022-11-06→2023-01-14 那種空窗）")
eq("來源可能停更" in lp({}, {"data_2026.js": "2026-06-26"})[1], True, "⑯76 天＝來源可能停更")
eq("date 欄解析壞了" in lp({}, {"data_2026.js": "2026-09-30"})[1], True, "⑯未來日期＝解析壞了")
eq(lp({}, {"data_2026.js": None})[1], "讀不到任何一場比賽的日期", "⑯讀不到日期＝異常")
# 正控制：門檻真的在作用（同一份資料，門檻調到 1 天就必須翻面）
eq("來源可能停更" in lp({}, FRESH, stale=1)[1], True, "⑯正控制：門檻 1 天時同一份資料會報")

# merge_latest 也是高水位：倒退不寫回，否則第二輪就被吃掉（跟 merge_baseline 同一個洞）
eq(uh.merge_latest({"data_2026.js": "2026-09-08"}, {"data_2026.js": "2026-08-01"}),
   {"data_2026.js": "2026-09-08"}, "⑯倒退不寫回基準")
eq(uh.merge_latest({"data_2026.js": "2026-09-08"}, {"data_2026.js": "2026-08-01"}, accept=True),
   {"data_2026.js": "2026-08-01"}, "⑯--accept 才認可倒退")
eq(uh.merge_latest({"data_2026.js": "2026-09-08"}, {"data_2026.js": "2026-09-09"}),
   {"data_2026.js": "2026-09-09"}, "⑯往前照常更新")
eq(uh.merge_latest({"data_2026.js": "2026-09-08"}, {"data_2026.js": None}),
   {"data_2026.js": "2026-09-08"}, "⑯讀不到就別把舊值蓋掉")

# ── ⑰ 真實資料端到端：data_counts 的出參要填滿每一年，而且日期都在合理範圍 ──
lt = {}
dc2 = uh.data_counts(lt)
eq(sorted(lt), years, "⑰latest_out 涵蓋全部年份")
eq(dc2, dc, "⑰帶出參不影響列數（跟 ⑦ 那次結果一樣）")
eq(all(isinstance(lt[y], str) and len(lt[y]) == 10 for y in years), True, "⑰每年都讀得到日期")
eq(all(lt[y][:4] in (y[5:9], str(int(y[5:9]) - 1)) for y in years), True,
   "⑰日期年份＝檔名那年或前一年（跨年賽前賽）")
eq(uh.latest_problems(lt, lt, time.time())[1], [], "⑰現況對現況沒有異常")

# ── ⑱ 遊戲版本（#99）：列數擋「變少」、日期擋「比賽不再變多」，這一組擋「版本不再往前」──
# 病灶：run_update 跑 `fetch_patches --skip-discover`，新版本靠猜 URL slug 抓；官方換過格式
# （26.04 起 league-of-legends-patch-26-N-notes），再換一次就靜靜抓不到 ⇒ patches.js 停在舊版，
# 而列數一列不少、比賽日期照樣往前 ⇒ 舊版報告印「✓ 沒有異常」。
eq(uh.ver_key("26.09") < uh.ver_key("26.10"), True, "⑱ver_key 數字比大小")
eq(uh.ver_key("16.17.1") > uh.ver_key("16.17"), True, "⑱ver_key 位數不同也比得動")
eq(uh.ver_key("亂碼"), (0,), "⑱ver_key 認不得＝(0,)（不是丟例外）")
eq(uh.ver_key(None), (0,), "⑱ver_key None＝(0,)")

eq(uh.dd_to_pk("16.17.1"), "26.17", "⑱DDragon 16.17.1＝版本改動 26.17")
eq(uh.dd_to_pk("15.1.1"), "25.01", "⑱minor 補零：15.1.1＝25.01")
eq(uh.dd_to_pk("14.24.1"), "24.24", "⑱2024 年（序號版 14）也對得上")
eq(uh.dd_to_pk("26.3.1"), "26.03", "⑱萬一 DDragon 改年份版（major>20）就不再 +10")
eq(uh.dd_to_pk("abc"), None, "⑱認不得的版號＝None")
eq(uh.dd_to_pk("16"), None, "⑱只有 major 沒 minor＝None")

_sb = tempfile.mkdtemp(prefix="uh99_")
_pj = os.path.join(_sb, "p.js")
io.open(_pj, "w", encoding="utf-8").write(
    'window.LOL_PATCHES={"25.24":{"A":["x"]},"26.09":{"B":["y"]},"26.10":{"C":["z"]}};'
    'window.ITEM_REMOVED={"某道具":"14.20"};')
eq(uh.newest_pk(_pj), "26.10", "⑱newest_pk 取最新版本鍵")
io.open(_pj, "w", encoding="utf-8").write('window.LOL_PATCHES={};')
eq(uh.newest_pk(_pj), None, "⑱一個版本都沒有＝None")
eq(uh.newest_pk(os.path.join(_sb, "沒這個檔.js")), None, "⑱檔案不存在＝None（不是丟例外）")
shutil.rmtree(_sb, ignore_errors=True)

NOW99 = time.mktime(time.strptime("2026-09-10 01:30:00", "%Y-%m-%d %H:%M:%S"))
GOOD = {"patches": "26.17", "patches_en": "26.17", "ddragon": "16.17.1",
        "assets": "16.17.1", "patch_date": "2026-08-25"}


def vp(prev, cur, since=None, now=NOW99, grace=uh.VER_GRACE_H, stale=uh.PATCH_STALE_DAYS):
    line, bad, out = uh.version_problems(prev, cur, since, now, grace, stale)
    return (line, "／".join(bad), out)


eq(vp(GOOD, GOOD)[1], "", "⑱四個來源一致＝沒有異常")
eq(vp(GOOD, GOOD)[0].endswith("— 一致"), True, "⑱一致那一行照樣印出來")
eq("26.17（2026-08-25 發布，16 天前）" in vp(GOOD, GOOD)[0], True, "⑱印出版本與發布日")
eq(vp(GOOD, GOOD)[2], None, "⑱一致就把 since 清掉（不會卡住）")

# ★ 這一輪要抓的病：DDragon 已經 16.18（＝26.18），版本改動還停在 26.17
LAG = dict(GOOD, ddragon="16.18.1", assets="16.18.1")
eq(vp(GOOD, LAG)[1], "", "⑱剛發生的不一致不當異常（改版當天兩邊上線有時差）")
eq("⚠ 不一致" in vp(GOOD, LAG)[0], True, "⑱剛發生也要印在報告上")
eq("滿 24 小時才算異常" in vp(GOOD, LAG)[0], True, "⑱講清楚還在寬限內")
eq(vp(GOOD, LAG)[2], NOW99, "⑱第一次看到不一致＝記下時間")
eq(vp(GOOD, LAG, since=NOW99 - 3600)[2], NOW99 - 3600, "⑱已經在計時就沿用舊時間")
eq("版本不一致已 25.0 小時" in vp(GOOD, LAG, since=NOW99 - 25 * 3600)[1], True,
   "⑱撐過 24 小時＝異常")
eq("DDragon 16.18.1（＝26.18）≠ 版本改動 26.17" in vp(GOOD, LAG, since=NOW99 - 25 * 3600)[1], True,
   "⑱異常訊息要指名是哪兩邊對不上")
eq(vp(GOOD, LAG, grace=0)[1] != "", True, "⑱正控制：寬限 0 小時時同一份資料就翻紅")
eq(vp(GOOD, GOOD, since=NOW99 - 99 * 3600)[1], "", "⑱恢復一致就不再報（舊 since 不會賴著）")

# 英文版／圖鑑素材各自落後也算不一致（它們是不同支抓取，會單獨掛掉）
eq("英文 26.16 ≠ 繁中 26.17" in vp(GOOD, dict(GOOD, patches_en="26.16"), since=NOW99 - 25 * 3600)[1],
   True, "⑱英文版落後")
eq("圖鑑素材 16.16.1 ≠ 技能 16.17.1" in vp(GOOD, dict(GOOD, assets="16.16.1"),
                                       since=NOW99 - 25 * 3600)[1], True, "⑱圖鑑素材落後")

# ① 倒退＝硬性異常，四個來源都要抓，而且要指名
eq("patches.js 版本倒退（基準 26.17 → 現在 26.16）" in vp(GOOD, dict(GOOD, patches="26.16"))[1], True,
   "⑱版本改動倒退")
eq("skills.js（DDragon） 版本倒退（基準 16.17.1 → 現在 16.16.1）"
   in vp(GOOD, dict(GOOD, ddragon="16.16.1", assets="16.16.1"))[1], True, "⑱DDragon 倒退")
eq("patches_en.js 版本倒退" in vp(GOOD, dict(GOOD, patches_en="26.16"))[1], True, "⑱英文版倒退")
eq("assets.js（DDragon） 版本倒退" in vp(GOOD, dict(GOOD, assets="16.16.1"))[1], True, "⑱圖鑑素材倒退")
eq(vp({}, GOOD)[1], "", "⑱第一次跑（沒有基準）不算倒退")

# ② 讀不到＝異常（檔案被清空／格式改掉，舊版會安靜地什麼都不說）
eq("讀不到版本：patches.js" in vp(GOOD, dict(GOOD, patches=None))[1], True, "⑱讀不到 patches.js")
eq("讀不到版本：skills.js、assets.js" in vp(GOOD, dict(GOOD, ddragon=None, assets=None))[1], True,
   "⑱讀不到 DDragon 兩支")

# ③ 停更：門檻 80 天＝比史上最長間隔（71 天，24.24→25.04）再寬一點
eq(vp(GOOD, dict(GOOD, patch_date="2026-07-01"))[1], "", "⑱71 天不報（史上最長間隔）")
eq("版本改動停在 26.17 已經 101 天" in vp(GOOD, dict(GOOD, patch_date="2026-06-01"))[1], True,
   "⑱101 天＝可能停更")
eq(vp(GOOD, GOOD, stale=1)[1] != "", True, "⑱正控制：門檻 1 天時同一份新鮮資料會翻紅")
eq("發布日不明" in vp(GOOD, dict(GOOD, patch_date=None))[0], True, "⑱沒有發布日就明講不明")

# merge_versions 也是高水位（跟 merge_baseline／merge_latest 同一個洞）
eq(uh.merge_versions(GOOD, dict(GOOD, patches="26.16"))["patches"], "26.17", "⑱倒退不寫回基準")
eq(uh.merge_versions(GOOD, dict(GOOD, patches="26.16"), accept=True)["patches"], "26.16",
   "⑱--accept 才認可倒退")
eq(uh.merge_versions(GOOD, dict(GOOD, patches="26.18"))["patches"], "26.18", "⑱往前照常更新")
eq(uh.merge_versions(GOOD, dict(GOOD, ddragon=None))["ddragon"], "16.17.1", "⑱讀不到就別把舊值蓋掉")
eq(uh.merge_versions(GOOD, dict(GOOD, patch_date="2026-08-11"))["patch_date"], "2026-08-11",
   "⑱發布日跟著版本走、不做高水位（版本倒退已經有人擋）")

# ── ⑲ 真實資料端到端：現況必須讀得到、而且自己跟自己不會有異常 ──
gv = uh.game_versions()
eq(sorted(gv), ["assets", "ddragon", "patch_date", "patches", "patches_en"], "⑲game_versions 五個鍵")
eq(bool(gv["patches"]) and bool(gv["patches_en"]), True, "⑲兩份版本改動都讀得到")
eq(bool(gv["ddragon"]) and bool(gv["assets"]), True, "⑲DDragon 兩個見證都讀得到")
# 不寫死「現在是 26.17」（正本會往前走，寫死＝下個版本就永久紅）：改用獨立方法算一次最大鍵
_txt = io.open(os.path.join(ROOT, "patches.js"), encoding="utf-8", errors="replace").read()
_pk2 = max(set(re.findall(r'"(\d{2}\.\d{2})":', _txt)), key=uh.ver_key)
eq(gv["patches"], _pk2, "⑲newest_pk 跟獨立算法算出同一個最新版")
eq(uh.version_problems({}, gv, None, time.time())[1], [], "⑲現況沒有異常（第一次跑）")
eq(uh.version_problems(gv, gv, None, time.time())[1], [], "⑲現況對自己的基準沒有異常")
eq(uh.version_problems(gv, gv, None, time.time())[2], None, "⑲現況四個來源一致")


# ── ⑳ 資料檔體積哨兵：分段門檻（2026-09-10 #100）─────────────────────
eq(uh.size_tol(1000000), 0.30, "⑳大檔用 30%")
eq(uh.size_tol(4096), 0.30, "⑳邊界 4096＝大檔")
eq(uh.size_tol(4095), 0.50, "⑳小檔用 50%")
eq(uh.size_tol(223), 0.50, "⑳lck_groups 那種 223B 也是小檔")

# ── ㉑ size_problems：三種異常各一組，每組都配「正控制會翻面」──────────
BIG = 1000000
sp = uh.size_problems
eq(sp({"a.js": BIG}, {"a.js": BIG})[1], [], "㉑沒變＝沒異常")
eq(sp({"a.js": BIG}, {"a.js": int(BIG * 1.4)})[1], [], "㉑變大＝沒異常")
# ① 縮水
eq(len(sp({"a.js": BIG}, {"a.js": int(BIG * 0.65)})[1]), 1, "㉑大檔縮 35%＝異常")
eq("a.js 體積縮水 35%" in sp({"a.js": BIG}, {"a.js": int(BIG * 0.65)})[1][0], True, "㉑異常訊息指名檔案與幅度")
eq(sp({"a.js": BIG}, {"a.js": int(BIG * 0.75)})[1], [], "㉑正控制：縮 25% 在門檻內＝不報")
eq(sp({"a.js": 1000}, {"a.js": 650})[1], [], "㉑正控制：同樣縮 35%，小檔不報（門檻 50%）")
eq(len(sp({"a.js": 1000}, {"a.js": 350})[1]), 1, "㉑小檔縮 65%＝異常")
eq(sp({"a.js": BIG}, {"a.js": int(BIG * 0.75)}, tol=0.1)[1] != [], True, "㉑tol 參數蓋得掉分段門檻")
# ② 檔案不見了（基準有、這次沒有）
eq(sp({"a.js": BIG, "b.js": 500}, {"a.js": BIG})[1], ["b.js 不見了（基準 500 bytes）"], "㉑檔案消失＝異常")
eq(sp({"a.js": BIG}, {"a.js": BIG, "b.js": 500})[1], [], "㉑正控制：反過來（新檔）不報")
eq(sp({"a.js": None}, {})[1], [], "㉑基準值不是數字就不算消失")
# ③ 讀不到
eq(sp({"a.js": BIG}, {"a.js": None})[1], ["a.js 讀不到"], "㉑讀不到＝異常")
eq(sp({}, {"a.js": None})[1], ["a.js 讀不到"], "㉑沒基準也照報讀不到")
# 新項目與怪基準不報
eq(sp({}, {"a.js": 10})[1], [], "㉑新項目先收基準不報")
eq(sp({"a.js": 0}, {"a.js": 10})[1], [], "㉑基準 0 不做除法")
# 摘要行
eq("資料檔體積：2 個檔" in sp({"a.js": BIG}, {"a.js": BIG, "b.js": 5})[0], True, "㉑摘要行有檔數")
eq("離門檻最近：a.js -10.0%" in sp({"a.js": BIG}, {"a.js": int(BIG * 0.9)})[0], True, "㉑摘要行報最接近的餘裕")
eq("沒有一個比基準小" in sp({"a.js": BIG}, {"a.js": BIG})[0], True, "㉑全部持平＝不印「-0.0%」")
eq("沒有一個比基準小" in sp({"a.js": BIG}, {"a.js": BIG * 2})[0], True, "㉑全部變大也是同一句")
eq("離門檻最近" in sp({}, {"a.js": BIG})[0], False, "㉑全新項目沒得比就不印那一段")
eq("⚠ 1 項有問題" in sp({"a.js": BIG}, {"a.js": 1})[0], True, "㉑有異常時摘要行也看得出來")

# ── ㉒ merge_sizes：高水位（跟 merge_baseline／merge_latest 同一個洞）────
ms = uh.merge_sizes
eq(ms({"a.js": 100}, {"a.js": 120}), {"a.js": 120}, "㉒變大寫回")
eq(ms({"a.js": 100}, {"a.js": 50}), {"a.js": 100}, "㉒縮水不寫回（保住高水位）")
eq(ms({"a.js": 100}, {"a.js": 50}, accept=True), {"a.js": 50}, "㉒正控制：accept 才寫回小值")
eq(ms({"a.js": 100}, {"a.js": None}), {"a.js": 100}, "㉒讀不到不覆蓋")
eq(ms({"a.js": 100, "b.js": 9}, {"a.js": 100}), {"a.js": 100, "b.js": 9}, "㉒消失的鍵留著（下一輪繼續報）")
eq(ms({"a.js": 100, "b.js": 9}, {"a.js": 100}, accept=True), {"a.js": 100}, "㉒正控制：accept 才把消失的鍵刪掉")
eq(ms({}, {"a.js": 7}), {"a.js": 7}, "㉒新檔寫進基準")
# 第二輪還會報（高水位真的有守住）
_b1 = ms({"a.js": BIG}, {"a.js": int(BIG * 0.5)})
eq(len(sp(_b1, {"a.js": int(BIG * 0.5)})[1]), 1, "㉒縮水第二輪仍然報")

# ── ㉓ 資料量：基準有、這次連鍵都不見了＝檔案整個消失 ───────────────────
_prevm = {"data_2019.js": 21673, "data_2026.js": 16406}
_curm = {"data_2026.js": 16406}
eq(state_of(uh.diff_counts(_prevm, _curm), "data_2019.js"), "missing", "㉓消失＝missing 狀態")
eq(uh.merge_baseline(_prevm, _curm)["data_2019.js"], 21673, "㉓消失不寫回基準（下一輪繼續報）")
eq("data_2019.js" in uh.merge_baseline(_prevm, _curm, accept=True), False, "㉓正控制：accept 才把鍵刪掉")
eq(state_of(uh.diff_counts({"data_2019.js": None}, _curm), "data_2019.js"), None,
   "㉓上次就讀不到（基準是 None）不算消失")
# 正控制：舊寫法（只迭代 cur）對同一份資料完全看不到這件事
_old_rows = [(k, v, _prevm.get(k), "ok") for k, v in _curm.items()]
eq(state_of(_old_rows, "data_2019.js"), None, "㉓正控制：舊寫法（只迭代 cur）看不到消失")

# ── ㉔ 真實資料端到端：現況自己跟自己不可以有異常 ───────────────────────
_fs = uh.file_sizes()
eq(len(_fs) >= 40, True, "㉔根目錄至少 40 個資料檔")
eq([k for k in uh.SIZE_SKIP if k in _fs], [], "㉔SIZE_SKIP 的三個檔真的沒被收進來")
eq([k for k, v in _fs.items() if not isinstance(v, int) or v <= 0], [], "㉔每個檔都讀得到 bytes")
eq([k for k in _fs if k.startswith("data_20")], [], "㉔年度檔不在體積哨兵裡（它們有列數）")
eq(sp(_fs, _fs)[1], [], "㉔現況對自己的基準沒有異常")
_hurt = dict(_fs)
_victim = sorted(_hurt, key=lambda k: -_hurt[k])[0]
_hurt[_victim] = _hurt[_victim] // 3
eq(len(sp(_fs, _hurt)[1]), 1, "㉔正控制：把最大的檔砍成三分之一就會被抓到")

# ── ㉕ 步驟清單哨兵（2026-09-10 #101）：#100 擋「產物變小／不見」，這一組擋「產出它的那一步不再跑」──
# 舊版唯一的訊號是「步驟 43 個」這個**沒有基準可比的數字**，所以 PLAN 少一步時報告一路綠。
def spn(prev, cur):
    return uh.step_problems(prev, cur)

_full = ["fetch_fill", "fetch_promo", "fetch_data", "fetch_side_sel", "build_soloq_builds"]
_less = [n for n in _full if n != "fetch_side_sel"]
_more = _full + ["fetch_newthing"]
eq(spn(_full, _full)[1], [], "㉕全到齊沒有異常")
eq("基準 5 個都在" in spn(_full, _full)[0], True, "㉕正常那行要講基準都在")
eq(len(spn(_full, _less)[1]), 1, "㉕少一步＝一條異常")
eq("fetch_side_sel" in spn(_full, _less)[1][0], True, "㉕異常訊息要指名是哪一步")
eq("不見了" in spn(_full, _less)[1][0], True, "㉕措辭含「不見了」才會觸發 main 的高水位提示句")
eq("少了 1 個" in spn(_full, _less)[0], True, "㉕摘要行要講少了幾個")
eq(len(spn(_full, [_full[0]])[1]), 1, "㉕少四步仍是一條（訊息裡列出全部）")
eq(spn(_full, [_full[0]])[1][0].count("、") >= 3, True, "㉕四個缺席的名字都要列出來")
eq(spn(_full, _more)[1], [], "㉕新增步驟不算異常（PLAN 加東西是常態）")
eq("新增 fetch_newthing" in spn(_full, _more)[0], True, "㉕新增要印出來給人看")
eq(spn(_full, [])[1], [], "㉕這一班沒跑完任何步驟時不重複報（run_problems 已報過）")
eq("上面已報" in spn(_full, [])[0], True, "㉕空清單那行講清楚為什麼不報")
eq(spn([], _full)[1], [], "㉕沒有基準時不報")
eq("首次建立基準" in spn([], _full)[0], True, "㉕首次那行講清楚")
# step_names：去重（階段並行炸掉會退回循序把同一批再跑一次）＋保序＋能吃 None
eq(uh.step_names({"steps": [("a", 1.0, 0), ("b", 2.0, 0), ("a", 3.0, 0)]}), ["a", "b"],
   "㉕step_names 去重且保留首次出現順序")
eq(uh.step_names(None), [], "㉕沒有日誌回空清單")
eq(uh.step_names({}), [], "㉕日誌沒有 steps 回空清單")
eq(uh.step_names({"steps": []}), [], "㉕steps 是空的回空清單")
# merge_steps：高水位（跟 merge_baseline／merge_sizes 同一個洞）
eq(uh.merge_steps(_full, _less), _full, "㉕缺席不寫回基準（下一輪繼續報）")
eq(uh.merge_steps(_full, _less, accept=True), _less, "㉕正控制：accept 才認可縮小後的清單")
eq(uh.merge_steps(_full, _more), _more, "㉕新增併進基準")
eq(uh.merge_steps(_full, []), _full, "㉕這一班沒步驟時不可以把基準清空")
eq(uh.merge_steps([], _full), _full, "㉕空基準吃下這一班")
eq(uh.merge_steps(_full, _less)[3], "fetch_side_sel", "㉕高水位保留原順序")
# 正控制：舊版存檔時特地把 steps 丟掉 ⇒ 連基準都沒有，缺席根本比不出來
_oldsave = {k: v for k, v in {"runs": [], "steps": [("a", 1.0, 0)]}.items() if k != "steps"}
eq("steps" in _oldsave, False, "㉕正控制：舊版基準裡根本沒有 steps 可比")
# 真實日誌端到端：現況自己跟自己零異常，拿掉一步一定要被抓到
_rl = uh.parse_log()
if _rl:
    _rn = uh.step_names(_rl)
    eq(len(_rn) >= 20, True, "㉕真實日誌至少 20 個步驟（少於這個數＝parse 壞了）")
    eq(spn(_rn, _rn)[1], [], "㉕真實日誌自己跟自己沒有異常")
    eq(len(spn(_rn, _rn[1:])[1]), 1, "㉕正控制：真實日誌拿掉一步就會被抓到")
    eq(len(set(_rn)), len(_rn), "㉕真實步驟名沒有重複（去重生效）")

# ── ㉖ 逐聯賽落後哨兵（2026-09-16 #140）：整組從 autopilot/_m139_lag_sentinel_test_draft.py 搬來 ──
# 上面那些哨兵都是全站指標，單一聯賽整段沒收會被蓋過去。這組把 Leaguepedia 出口接管掉，
# 六個網路出口全封死並附「封鎖器自己會擋」的正控制（#52：把來源清空不算隔離）。
import datetime as dt          # noqa: E402


def yes(cond, label):
    eq(bool(cond), True, label)

# 網路封鎖（BlockedNetwork／_blow／block_network）定義在檔頭 ⓪，整份測試全程封網；
# 這裡再包一層是 #140 原樣（巢狀呼叫無害：存下的「原版」本來就是已封死的那個）。

# ══ 合成資料入口：長得像 data_2026.js，但只有測試要的那幾欄有意義 ═════════
COLS = ["date", "league", "blue_teamname", "red_teamname", "game", "patch"]


_TMP = []


def make_data_js(rows, fetched_at="2026-09-16 08:00"):
    """rows = [(date_str, league, 第幾局), ...] → 寫出一個沙箱 data_2026.js，回傳路徑。

    路徑登記在 _TMP，收尾一律刪掉——每跑一次留十幾個 .js 在 %TEMP% 是慢性汙染。"""
    raw = [list(COLS)]
    for i, (d, lg, g) in enumerate(rows):
        # ⚠ 一定要**按欄名**擺，不可以按固定位置：⑨ 把 COLS 打亂就是要證明被測端用 hdr.index 查。
        #   若這裡也照位置填，打亂後表頭與值同步錯位，被測端硬編偏移也會「剛好」過關（假綠）。
        cell = {"date": d, "league": lg, "blue_teamname": "B%d" % i,
                "red_teamname": "R%d" % i, "game": g, "patch": "26.18"}
        raw.append([cell[c] for c in COLS])
    obj = {"fetched_at": fetched_at, "tabs": {"RAW_DATA": raw}}
    fd, path = tempfile.mkstemp(prefix="m139_data_", suffix=".js")
    os.close(fd)
    io.open(path, "w", encoding="utf-8").write(
        "window.LOL_DATA=" + json.dumps(obj, ensure_ascii=False) + ";")
    _TMP.append(path)
    return path


def wiki_stub(rows, filter_since=True):
    """rows = [(OverviewPage, DateTime_UTC), ...] → 一個 fetch(since, timeout) 假出口。

    filter_since=False 模擬「Cargo 沒照 where 過濾、回了視窗外的舊局」——
    判定端不可以因此誤報（見 SUITE 第 ⑧ 組）。"""
    def fetch(since, timeout=90):
        return [{"ov": ov, "dt": t} for ov, t in rows if (not filter_since) or t[:10] >= since]
    return fetch


def fetch_boom(since, timeout=90):
    raise IOError("HTTP Error 503: Service Unavailable")


# ══ 測試本體：同一組斷言可以套在參考實作或 update_health 上 ═══════════════
NOW140 = dt.datetime(2026, 9, 16, 8, 0)      # 固定「現在」，不吃系統時鐘


def SUITE(M, tag):
    """M 要提供 lag_problems / wiki_days / our_days / LAG_* 四個常數。"""
    def LP(**kw):
        return M.lag_problems(NOW140, kw.pop("data"), **kw)

    # ── ① 正例：wiki 有的我們都有 ⇒ ok ────────────────────────────────
    d_ok = make_data_js([("2026-09-14 10:00", "LPL", 1), ("2026-09-15 10:00", "LPL", 1),
                         ("2026-09-15 10:00", "LCK", 1)])
    w_ok = wiki_stub([("LPL/2026 Season/Split 3", "2026-09-14 10:00"),
                      ("LPL/2026 Season/Split 3", "2026-09-15 10:00"),
                      ("LCK/2026 Season/Split 3", "2026-09-15 10:00")])
    st, msgs = LP(data=d_ok, fetch=w_ok)
    eq(st, "ok", "%s ①正例：跟上 ⇒ ok" % tag)

    # ── ② 反例：LPL 三天沒收 ⇒ bad，而且訊息要點名是誰、差哪幾天 ──────
    w_lag = wiki_stub([("LPL/2026 Season/Split 3", "2026-09-13 10:00"),
                       ("LPL/2026 Season/Split 3", "2026-09-14 10:00"),
                       ("LPL/2026 Season/Split 3", "2026-09-15 10:00"),
                       ("LCK/2026 Season/Split 3", "2026-09-15 10:00")])
    d_lag = make_data_js([("2026-09-12 10:00", "LPL", 1), ("2026-09-15 10:00", "LCK", 1)])
    st, msgs = LP(data=d_lag, fetch=w_lag)
    eq(st, "bad", "%s ②反例：LPL 落後 3 天 ⇒ bad" % tag)
    yes(any("LPL 落後 3 個比賽日" in m for m in msgs), "%s ②訊息點名 LPL 與天數" % tag)
    yes(any("2026-09-13" in m and "2026-09-15" in m for m in msgs), "%s ②訊息列出缺的比賽日" % tag)
    yes(not any("LCK" in m and "異常" in m for m in msgs), "%s ②跟上的 LCK 不被連坐" % tag)

    # ── ③ 門檻真的在作用：落後 1 天不報；門檻改 1 同一份資料就翻紅 ─────
    w_one = wiki_stub([("LPL/2026 Season/Split 3", "2026-09-15 10:00")])
    d_one = make_data_js([("2026-09-14 10:00", "LPL", 1)])
    eq(LP(data=d_one, fetch=w_one)[0], "ok", "%s ③落後 1 天＜門檻 ⇒ ok" % tag)
    eq(LP(data=d_one, fetch=w_one, threshold=1)[0], "bad",
       "%s ③正控制：門檻 1 時同一份資料翻紅" % tag)
    # 邊界：我們「已經有」的那一天不可以被算進落後（比較要用 > 不是 >=，
    # 寫成 >= 的話下面這組真實落後 1 天會被灌成 2 天而誤報）
    w_edge = wiki_stub([("LPL/2026 Season/Split 3", "2026-09-14 10:00"),
                        ("LPL/2026 Season/Split 3", "2026-09-15 10:00")])
    d_edge = make_data_js([("2026-09-14 10:00", "LPL", 1)])
    eq(LP(data=d_edge, fetch=w_edge)[0], "ok", "%s ③邊界：我們已有的那天不算落後" % tag)
    eq(LP(data=d_edge, fetch=w_edge, threshold=1)[0], "bad",
       "%s ③正控制：門檻 1 時這組（真的落後 1 天）會叫" % tag)

    # ── ④ 寬限 6 小時：剛開賽的局不算「我們落後」（兩邊都釘 threshold=1，唯一變數是寬限）
    #    NOW140=09-16 08:00 ⇒ 寬限線 02:00；兩局 04:00／06:00 都還在寬限內
    w_fresh = wiki_stub([("LCK/2026 Season/Split 3", "2026-09-16 04:00"),
                         ("LCK/2026 Season/Split 3", "2026-09-16 06:00")])
    d_fresh = make_data_js([("2026-09-15 10:00", "LCK", 1)])
    eq(LP(data=d_fresh, fetch=w_fresh, threshold=1)[0], "ok",
       "%s ④寬限內剛開賽 ⇒ 不算落後" % tag)
    eq(LP(data=d_fresh, fetch=w_fresh, threshold=1, grace_h=0)[0], "bad",
       "%s ④正控制：只把寬限改成 0，同一份資料就翻紅" % tag)

    # ── ⑤ 白名單：PCS 落後五天也不該叫（我們本來就沒收那個賽段）──────────
    #    #137 wiki 探測：PCS/2026 Season/Summer Season 38 局是我們完全沒有的頁
    w_pcs = wiki_stub([("PCS/2026 Season/Summer Season", "2026-09-%02d 10:00" % d)
                       for d in (10, 11, 12, 13, 14)])
    d_pcs = make_data_js([("2026-09-15 10:00", "LCK", 1)])
    eq(LP(data=d_pcs, fetch=w_pcs)[0], "ok", "%s ⑤PCS 不在白名單 ⇒ 不叫" % tag)
    eq(LP(data=d_pcs, fetch=w_pcs, tier1=("LCK", "PCS"))[0], "bad",
       "%s ⑤正控制：把 PCS 加進白名單就會叫（證明資料真的餵進去了）" % tag)

    # ── ⑥ 降級：wiki 掛了 ⇒ skip，不是 bad、也不可以炸掉整個健檢 ─────────
    st, msgs = LP(data=d_lag, fetch=fetch_boom)
    eq(st, "skip", "%s ⑥wiki 失敗 ⇒ skip（不算異常）" % tag)
    yes(any("略過" in m for m in msgs), "%s ⑥訊息說明是略過" % tag)
    eq(LP(data=d_lag, fetch=w_lag)[0], "bad",
       "%s ⑥正控制：同一份資料在 fetch 正常時是 bad（skip 不是恆真）" % tag)
    # 空回應（Cargo 偶爾回 []）也要當查不到，不能當成「wiki 沒比賽 ⇒ 我們沒落後」
    eq(LP(data=d_lag, fetch=lambda s, timeout=90: [])[0], "skip",
       "%s ⑥空回應 ⇒ skip 而不是 ok" % tag)

    # ── ⑦ 兩邊都沒比賽（休賽期）⇒ 不叫，而且連一行都不要印 ──────────────
    #    只斷言狀態擋不住「把跳過拿掉」那種改動（沒比賽的聯賽 behind 本來就 0、狀態不會變），
    #    所以這裡順便釘訊息行數：六個聯賽只有 LCK 有比賽 ⇒ 只能有一行。
    d_idle = make_data_js([("2026-09-15 10:00", "LCK", 1)])
    st, msgs = LP(data=d_idle, fetch=wiki_stub([("LCK/2026 Season/Split 3", "2026-09-15 10:00")]))
    eq(st, "ok", "%s ⑦其餘聯賽兩邊都沒比賽 ⇒ 不叫" % tag)
    eq(len(msgs), 1, "%s ⑦休賽中的聯賽不佔訊息行（只剩 LCK 一行）" % tag)
    yes("LCK" in msgs[0], "%s ⑦那一行是 LCK" % tag)

    # ── ⑧ 視窗外的舊局不可以造成假警報 ────────────────────────────────
    #    我們這側 our_days 依 since 過濾，wiki 側如果不過濾就會「odays 空、wdays 一堆」
    #    ⇒ 整個停賽已久的聯賽天天被叫。這裡用「不照 where 過濾」的假出口逼出那個不對稱。
    w_old = wiki_stub([("LEC/2026 Season/Split 2", "2026-08-01 10:00"),
                       ("LEC/2026 Season/Split 2", "2026-08-02 10:00")], filter_since=False)
    eq(LP(data=make_data_js([("2026-09-15 10:00", "LCK", 1)]), fetch=w_old)[0], "ok",
       "%s ⑧伺服器回了視窗外的舊局也不誤報" % tag)
    eq(LP(data=make_data_js([("2026-09-15 10:00", "LCK", 1)]), fetch=w_old, window_d=60)[0],
       "bad", "%s ⑧正控制：視窗拉到 60 天（那兩天就進窗了）同一份資料會叫" % tag)

    # ── ⑨ 欄位一律 hdr.index 查（把欄序打亂，答案要一樣）──────────────
    #    欄序刻意讓偏移 0（game=整數 1）與偏移 1（patch="26.18"）兩個常見硬編都是錯的。
    #    斷言挑「ok」那一側：讀錯欄 ⇒ 全部列被視窗濾掉或聯賽對不上
    #    ⇒ odays 空 ⇒ wiki 那兩天全算落後 ⇒ 翻成 bad（測試就會紅）。
    global COLS
    _save = COLS
    COLS = ["game", "patch", "date", "league", "blue_teamname", "red_teamname"]
    try:
        d_mix = make_data_js([("2026-09-14 10:00", "LPL", 1), ("2026-09-15 10:00", "LPL", 1),
                              ("2026-09-15 10:00", "LCK", 1)])
    finally:
        COLS = _save
    eq(LP(data=d_mix, fetch=w_ok)[0], "ok", "%s ⑨欄序打亂照樣讀得到（沒有硬編偏移）" % tag)

    # ── ⑩ 常數要跟 #136／#137 定案一致（有人手滑改門檻就會紅）────────────
    eq(tuple(M.LAG_TIER1), ("LCK", "LPL", "LEC", "LCS", "CBLOL", "LCP"), "%s ⑩白名單六隊" % tag)
    eq(M.LAG_GRACE_H, 6, "%s ⑩寬限 6 小時" % tag)
    eq(M.LAG_THRESHOLD, 2, "%s ⑩門檻 2 個比賽日" % tag)
    eq(M.LAG_WINDOW_D, 14, "%s ⑩視窗 14 天" % tag)

    # ── ⑪ 出口點名：不給 fetch 時，走的一定是模組層的 wiki_rows ──────────
    called = []

    def spy(since, timeout=90):
        called.append(since)
        return [{"ov": "LPL/2026 Season/Split 3", "dt": "2026-09-15 10:00"}]
    _orig = M.wiki_rows
    M.wiki_rows = spy
    try:
        st, _ = LP(data=make_data_js([("2026-09-12 10:00", "LPL", 1)]))
        eq(len(called), 1, "%s ⑪預設出口＝模組層 wiki_rows（接管得到）" % tag)
        eq(called[0], "2026-09-02", "%s ⑪since 是 now−14 天" % tag)
    finally:
        M.wiki_rows = _orig


# 跑第 ㉖ 組（全程封網；先證明封鎖器真的會擋，否則「沒連到外面」可能只是根本沒呼叫）
_restore = block_network()
_hits_before26 = len(NET_HITS)     # 只清下面兩發故意撞的；前面 ⑫⑮ 真的漏接留著給檔尾抓
try:
    try:
        import urllib.request as _ur
        _ur.urlopen("https://lol.fandom.com/")
        NG.append("㉖⓪封鎖器沒作用：urlopen 居然通了")
    except BlockedNetwork:
        OK[0] += 1
    try:
        import socket as _sk
        _sk.socket()
        NG.append("㉖⓪封鎖器沒作用：socket 居然建得起來")
    except BlockedNetwork:
        OK[0] += 1
    # 上面兩發是故意撞的，不算漏接（檔尾會 assert NET_HITS 是空的）。
    # ⚠ 不可以 del NET_HITS[:] 整本清掉——那會把前面 ⑫⑮ 的真漏接一起抹掉（#164 突變 B 抓到的假綠）
    del NET_HITS[_hits_before26:]
    for _n in dir(uh):
        _v = getattr(uh, _n, None)
        if isinstance(_v, str) and _v.endswith("data_2026.js") and os.path.isabs(_v):
            NG.append("㉖模組層常數 %s 指著真實 data_2026.js（沙箱漏接）" % _n)
    SUITE(uh, "㉖")
finally:
    _restore()
    for _f in _TMP:
        try:
            os.remove(_f)
        except OSError:
            pass

# ══ ㉘ 逐聯賽落後：年度檔依時鐘選、讀不懂降級（2026-09-17 #164）══════════════════════
# #163 查到兩個真缺陷：main 寫死 data/data_2026.js（2027 賽季一開打就每班誤報六聯賽落後）、
# our_days 讀檔失敗直接把整份健檢炸掉（沒有結論、不存基準）。
import types as _types      # noqa: E402

_YR_DIRS = []


def _year_root(spec):
    """spec＝{年: [(date, league, game), …] 或 "BROKEN"} → 假 repo 根目錄（只有 data/）。"""
    r = tempfile.mkdtemp(prefix="uh_yr_")
    _YR_DIRS.append(r)
    os.makedirs(os.path.join(r, "data"))
    for y, rows in spec.items():
        p = os.path.join(r, "data", "data_%d.js" % y)
        if rows == "BROKEN":                       # 寫到一半的檔
            io.open(p, "w", encoding="utf-8").write('window.LOL_DATA={"tabs":{"RAW_DATA":[["date"')
            continue
        src = make_data_js(rows)                   # 借 ㉖ 的產生器（按欄名擺）
        io.open(p, "w", encoding="utf-8").write(io.open(src, encoding="utf-8").read())
        os.remove(src)
    return r


def _bn(paths):
    return [os.path.basename(p) for p in paths]


def _clock_shim(fake_utc):
    """換掉 uh.datetime 用的替身：只有 datetime.datetime.utcnow() 回假時鐘，其餘照真的。"""
    class _DT(dt.datetime):
        @classmethod
        def utcnow(cls):
            return fake_utc
    shim = _types.ModuleType("datetime_shim")
    for k in dir(dt):
        if not k.startswith("__"):
            setattr(shim, k, getattr(dt, k))
    shim.datetime = _DT
    return shim


N27 = dt.datetime(2027, 1, 20, 8, 0)
_real_root28, _real_dt28 = uh.ROOT, uh.datetime
_real_log28, _real_console28, _real_base28, _real_live28, _real_argv28 = (
    uh.LOG, uh.CONSOLE, uh.BASE, uh.live_dup, list(sys.argv))
try:
    R0 = _year_root({})
    eq(_bn(uh.lag_data_paths(N27, root=R0)), ["data_2027.js"], "㉘1/20 視窗 14 天只碰 2027")
    eq(_bn(uh.lag_data_paths(dt.datetime(2027, 1, 5, 8, 0), root=R0)), ["data_2026.js", "data_2027.js"],
       "㉘1/5 視窗跨年 ⇒ 兩年都讀（12 月底的局在前一年的檔）")
    eq(_bn(uh.lag_data_paths(NOW140, root=R0)), ["data_2026.js"], "㉘賽季中只讀當年")
    uh.ROOT = R0
    eq(os.path.dirname(os.path.dirname(uh.lag_data_paths(N27)[0])), R0,
       "㉘root 晚綁：沙盒換 ROOT 之後路徑跟著換（不是 import 當下焊死）")
    uh.ROOT = _real_root28

    # A. 定時炸彈本身：2027-01-20，2027 的局都在 data_2027.js ⇒ 不可以報落後
    w27 = wiki_stub([("LCK/2027 Season/Cup", "2027-01-15 08:00"), ("LCK/2027 Season/Cup", "2027-01-17 08:00"),
                     ("LCK/2027 Season/Cup", "2027-01-18 08:00"), ("LPL/2027 Season/Split 1", "2027-01-17 10:00")])
    RA = _year_root({2026: [("2026-11-02 08:00", "LCK", 1), ("2026-11-03 08:00", "LPL", 1)],
                     2027: [("2027-01-15 08:00", "LCK", 1), ("2027-01-17 08:00", "LCK", 1),
                            ("2027-01-18 08:00", "LCK", 1), ("2027-01-17 10:00", "LPL", 1)]})
    stA, msA = uh.lag_problems(N27, uh.lag_data_paths(N27, root=RA), fetch=w27)
    eq(stA, "ok", "㉘A 2027-01-20 依時鐘讀 data_2027.js ⇒ 跟上")
    eq(any("不存在" in m for m in msA), False, "㉘A 檔都在 ⇒ 不印「不存在」")
    eq(uh.lag_problems(N27, os.path.join(RA, "data", "data_2026.js"), fetch=w27)[0], "bad",
       "㉘A 正控制：照 #164 之前寫死讀 data_2026.js ⇒ 同一份資料誤報落後")

    # B. 真落後不可以被靜音：data_2027.js 還沒長出來、wiki 已有 3 個比賽日 ⇒ 照報，並講明哪個檔不存在
    RB = _year_root({2026: [("2026-11-02 08:00", "LCK", 1)]})
    stB, msB = uh.lag_problems(N27, uh.lag_data_paths(N27, root=RB), fetch=w27)
    eq(stB, "bad", "㉘B 新賽季的檔不存在、wiki 有 3 個比賽日 ⇒ 照報落後（不是略過）")
    eq(any("data_2027.js 不存在" in m for m in msB), True, "㉘B 訊息講明 data_2027.js 不存在")
    eq(any(m.startswith("異常：") and "LCK 落後 3 個比賽日" in m for m in msB), True, "㉘B 異常行點名 LCK 3 天")
    stB2, msB2 = uh.lag_problems(N27, uh.lag_data_paths(N27, root=RB),
                                 fetch=wiki_stub([("PCS/2027 Season/Spring", "2027-01-17 08:00")]))
    eq((stB2, msB2), ("ok", []), "㉘B 對照：wiki 也還沒開打 ⇒ ok、一行都不印（檔不存在不是噪音來源）")

    # C. 跨年視窗：1/5，12 月底的局在 data_2026.js、data_2027.js 還沒有 ⇒ 靠前一年的檔跟上
    N0105 = dt.datetime(2027, 1, 5, 8, 0)
    wC = wiki_stub([("LPL/2026 Season/Split 3", "2026-12-28 10:00"), ("LPL/2026 Season/Split 3", "2026-12-29 10:00")])
    RC = _year_root({2026: [("2026-12-28 10:00", "LPL", 1), ("2026-12-29 10:00", "LPL", 1)]})
    stC, msC = uh.lag_problems(N0105, uh.lag_data_paths(N0105, root=RC), fetch=wC)
    eq(stC, "ok", "㉘C 跨年視窗讀到前一年的檔 ⇒ 跟上")
    eq(any("不存在" in m for m in msC), False, "㉘C 沒落後時 data_2027.js 不存在不印（噪音）")
    eq(uh.lag_problems(N0105, [os.path.join(RC, "data", "data_2027.js")], fetch=wC)[0], "bad",
       "㉘C 正控制：只讀當年（2027 不存在）⇒ 同一份資料報落後 2 天（證明前一年的檔真的有被讀）")

    # D. 讀不懂的檔 ⇒ 略過並講原因，不可以丟例外
    RD = _year_root({2027: "BROKEN"})
    try:
        stD, msD = uh.lag_problems(N27, uh.lag_data_paths(N27, root=RD), fetch=w27)
    except Exception as e:
        stD, msD = "RAISED", ["%s: %s" % (type(e).__name__, e)]
    eq(stD, "skip", "㉘D 年度檔寫到一半 ⇒ skip（不是例外、也不是 bad）")
    eq(any("讀不懂" in m and "data_2027.js" in m for m in msD), True, "㉘D 訊息點名是哪個檔讀不懂")
    eq(uh.lag_problems(N27, uh.lag_data_paths(N27, root=RA), fetch=w27)[0], "ok",
       "㉘D 對照：同一份 wiki、檔案完好 ⇒ ok（skip 不是恆真）")

    # E. main() 端到端：假時鐘 2027-01-20＋假 repo（2026／2027 兩個檔）⇒ 逐聯賽落後那行要是 ✓
    #    NET：wiki 出口換成 w27；其餘證據來源（LOG／CONSOLE／BASE／live_dup）一併接管、--no-save 不寫基準。
    tmpE = tempfile.mkdtemp(prefix="uh_e28_")
    _YR_DIRS.append(tmpE)
    uh.LOG = os.path.join(tmpE, "log.txt")
    uh.CONSOLE = os.path.join(tmpE, "console.txt")
    uh.BASE = os.path.join(tmpE, "base.json")
    uh.live_dup = lambda timeout=None: (0, "")
    io.open(uh.LOG, "w", encoding="utf-8").write(
        "==== run_update %s（並行 4）====\n---- fetch_x（1.0s，exit 0）----\n守門通過\n"
        % time.strftime("%Y-%m-%d %H:%M:%S"))
    sys.argv = ["update_health.py", "--no-save", "--no-live", "--no-soloqfresh"]

    def _main28(root, wiki, clock):
        uh.ROOT, uh.wiki_rows, uh.datetime = root, wiki, _clock_shim(clock)
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                rc = uh.main()
        except Exception as e:
            rc = "RAISED %s: %s" % (type(e).__name__, e)
        finally:
            uh.ROOT, uh.wiki_rows, uh.datetime = _real_root28, _wiki_takeover, _real_dt28
        out = buf.getvalue()
        lag = [l.strip() for l in out.splitlines() if l.strip().startswith("逐聯賽落後（近")]
        return rc, out, (lag[0] if lag else None)

    rcE, outE, lagE = _main28(RA, w27, N27)
    eq(isinstance(rcE, int), True, "㉘E main() 在假時鐘 2027-01-20 跑完（沒有例外）")
    eq((lagE or "").endswith("✓ 六個一級聯賽都跟上"), True, "㉘E main() 依時鐘讀 data_2027.js ⇒ 逐聯賽落後 ✓")
    eq("LCK 落後" in outE, False, "㉘E 結論沒有 LCK 落後")
    # 正控制：同一個 main、同一個假 repo，時鐘撥回 2026-09-16 ⇒ 讀 data_2026.js ⇒ wiki 那幾天全算落後
    #（證明假時鐘真的有接進 main 的年份選擇，不是 main 恰好沒去讀）。2027 檔照樣放著：
    # main 若無視時鐘去讀 2027，LCK 最後比賽日是 2027-01-18 ⇒ 不算落後 ⇒ 這條會紅。
    RE2 = _year_root({2026: [("2026-09-01 08:00", "LCK", 1)],
                      2027: [("2027-01-18 08:00", "LCK", 1)]})
    rcE2, outE2, lagE2 = _main28(RE2, wiki_stub([("LCK/2026 Season/Split 3", "2026-09-13 08:00"),
                                                ("LCK/2026 Season/Split 3", "2026-09-14 08:00"),
                                                ("LCK/2026 Season/Split 3", "2026-09-15 08:00")]),
                                 NOW140)
    eq((lagE2 or "").endswith("⚠ 有落後"), True, "㉘E 正控制：時鐘換成 2026 ⇒ 讀 2026 檔 ⇒ 真的落後會叫")

    # F. main() 在年度檔讀不懂時照樣出結論（#163：our_days 沒有 try ⇒ 整份健檢崩潰）
    rcF, outF, lagF = _main28(RD, w27, N27)
    eq(isinstance(rcF, int), True, "㉘F 年度檔壞掉 ⇒ main() 不崩潰（得到 %r）" % (rcF,))
    eq("結論：" in outF, True, "㉘F 照樣印出結論")
    eq((lagF or "").endswith("略過（原因見下一行）"), True, "㉘F 逐聯賽落後那行是略過")
    eq("讀不懂我們的年度檔 data_2027.js" in outF, True, "㉘F 下一行講明是哪個檔讀不懂")
finally:
    uh.ROOT, uh.datetime, uh.wiki_rows = _real_root28, _real_dt28, _wiki_takeover
    uh.LOG, uh.CONSOLE, uh.BASE, uh.live_dup = _real_log28, _real_console28, _real_base28, _real_live28
    sys.argv = _real_argv28
    for _d in _YR_DIRS:
        shutil.rmtree(_d, ignore_errors=True)

# ══ ㉗ 積分逐場新鮮度（#143；逐字抽自 autopilot/_m143_soloq_fresh_port.py）═══════════
def SQF_SUITE(uh, eq):
    """合成逐場目錄，直接問 uh.soloq_fresh()。NOW143 是固定的「現在」⇒ 跑在哪一天結果都一樣。"""
    import io as _io
    import os as _os
    import shutil as _sh
    import tempfile as _tf
    NOW143 = 1789000000000.0          # 固定的 epoch ms（2026-09-09 前後），素材全相對它算
    H = 3600000.0
    _dirs = []

    def mk(specs, pad=0):
        """specs＝[(檔名, [該檔的 t 們])]；pad>0 就在第一局塞這麼多位元組的填充，
        把後面的局推到便宜路徑（開頭 8192 位元組）讀不到的地方——用來測「新到舊」假設壞掉。"""
        d = _tf.mkdtemp(prefix="sqf_")
        _dirs.append(d)
        for name, ts in specs:
            recs = []
            for i, t in enumerate(ts):
                recs.append('{"t":%d,"pad":"%s"}' % (int(t), ("x" * pad) if (pad and i == 0) else ""))
            _io.open(_os.path.join(d, name), "w", encoding="utf-8").write(
                "window.SQM=[" + ",".join(recs) + "];")
        return d

    def sf(d, **kw):
        kw.setdefault("now_ms", NOW143)
        return uh.soloq_fresh(mdir=d, **kw)

    try:
        eq((uh.SQF_HEAD_BYTES, uh.SQF_STALE_H, uh.SQF_THIN_MIN, uh.SQF_THIN_H),
           (8192, 30, 20, 24), "㉗門檻常數＝探針實測那組（8192／30h／20 檔／24h 窗口）")
        # 新鮮：30 個檔，最後一局都在 1 小時前
        fresh = mk([("p%d.js" % i, [NOW143 - 1 * H, NOW143 - 50 * H]) for i in range(30)])
        st, line, bad = sf(fresh)
        eq((st, bad), ("ok", []), "㉗新鮮：30 個檔都在 1 小時前 ⇒ ok")
        eq("✓" in line and "跟著動 30" in line, True, "㉗新鮮那一行印 ✓ 與「跟著動」的檔數")
        # 停更：全部檔最後一局都在 40 小時前（>30h）
        stale = mk([("p%d.js" % i, [NOW143 - 40 * H]) for i in range(30)])
        st, line, bad = sf(stale)
        eq(st, "bad", "㉗停更：全庫最新一局 40 小時前 ⇒ bad")
        eq(any("沒往前" in b for b in bad), True, "㉗停更的異常訊息講「沒往前」")
        eq("⚠" in line, True, "㉗停更那一行印 ⚠")
        # 稀疏：最新一局很新，但只有 5 個檔在動
        thin = mk([("p%d.js" % i, [NOW143 - 1 * H]) for i in range(5)]
                  + [("q%d.js" % i, [NOW143 - 240 * H]) for i in range(25)])
        st, line, bad = sf(thin)
        eq(st, "bad", "㉗稀疏：只有 5 個檔跟著最新一局在動 ⇒ bad（最新一局再新也不算過）")
        eq(any("只有 5 個" in b for b in bad), True, "㉗稀疏的異常訊息點出 5 個檔")
        eq(any("沒往前" in b for b in bad), False, "㉗稀疏不該同時報「沒往前」")
        # 漏一整班（26 小時沒抓到新局）：STALE_H=30 刻意容許 ⇒ 不可以有任何異常。
        # 舊寫法把稀疏的窗口釘在「現在」，這一格 24h 內一個檔都沒有 ⇒ 當場誤報，
        # 30 小時的寬限形同不存在（真正把關的是 24 小時）。這一條就是那個缺陷的哨兵。
        miss = mk([("p%d.js" % i, [NOW143 - 26 * H]) for i in range(30)])
        st, line, bad = sf(miss)
        eq((st, bad), ("ok", []), "㉗漏一整班（26h）＝還在寬限內，稀疏不可以跟著誤報")
        # 空目錄：異常，不是「資料很新」
        st, line, bad = sf(mk([]))
        eq(st, "bad", "㉗空目錄＝異常（不是資料很新）")
        eq(any("一個 .js 都沒有" in b for b in bad), True, "㉗空目錄的訊息講「一個 .js 都沒有」")
        # 檔案在、但一個 t 都沒有（格式變了）
        not_j = mk([("p1.js", []), ("p2.js", [])])
        st, line, bad = sf(not_j)
        eq(st, "bad", "㉗一個 t 都沒有＝異常")
        eq(any("格式變了" in b for b in bad), True, "㉗沒有 t 的訊息講「格式變了」")
        # 「新到舊」假設壞掉：第一局最舊、新局被推到 8192 位元組之後
        # 便宜路徑會算出 40 小時前 ⇒ 必須自動整檔重掃 ⇒ 結論 ok（不誤報）
        scr = mk([("p%d.js" % i, [NOW143 - 40 * H, NOW143 - 1 * H]) for i in range(30)], pad=12000)
        st, line, bad = sf(scr)
        eq((st, bad), ("ok", []), "㉗排序假設壞掉：便宜路徑判落後 ⇒ 自動整檔重掃 ⇒ 仍是 ok")
        eq("整檔重掃" in line, True, "㉗升級整檔重掃要寫在那一行上（不然沒人知道它慢了）")
        eq(max(uh.sqf_scan(sorted(_os.path.join(scr, f) for f in _os.listdir(scr)),
                           True).values()) < NOW143 - 30 * H, True,
           "㉗對照：便宜路徑真的只讀開頭（掃到的最大 t 還是那個舊的）")
        # 正例會動的對照：同樣走升級路徑，但整檔掃之後**真的**還是舊的 ⇒ 仍要 bad
        scr2 = mk([("p%d.js" % i, [NOW143 - 40 * H, NOW143 - 900 * H]) for i in range(30)], pad=12000)
        st, line, bad = sf(scr2)
        eq(st, "bad", "㉗對照：升級整檔掃之後還是舊的 ⇒ 照樣 bad（升級不是無條件放過）")
        # 門檻邊界：剛好等於門檻算落後（寫成 > 的話真落後那一刻會漏掉一整班）
        eq(sf(mk([("p%d.js" % i, [NOW143 - 30 * H]) for i in range(30)]))[0], "bad",
           "㉗邊界：age 剛好 30h＝落後（>= 不是 >）")
        eq(sf(mk([("p%d.js" % i, [NOW143 - 29.5 * H]) for i in range(30)]))[0], "ok",
           "㉗邊界：29.5h 還不算落後")
        eq(sf(mk([("p%d.js" % i, [NOW143 - 1 * H]) for i in range(20)]))[0], "ok",
           "㉗邊界：跟著動的檔剛好 20 個＝過")
        eq(sf(mk([("p%d.js" % i, [NOW143 - 1 * H]) for i in range(19)]))[0], "bad",
           "㉗邊界：跟著動的檔 19 個＝不過")
        # 窗口是「距最新一局」多久，所以素材要相對 mx（這裡 mx＝1 小時前）算，不是相對現在
        eq(sf(mk([("p0.js", [NOW143 - 1 * H])]
                 + [("q%d.js" % i, [NOW143 - (1 + 24.1) * H]) for i in range(29)]))[0], "bad",
           "㉗窗口邊界：距最新一局 24.1 小時的檔不算在動（29 個也救不了）")
        eq(sf(mk([("p0.js", [NOW143 - 1 * H])]
                 + [("q%d.js" % i, [NOW143 - (1 + 23.9) * H]) for i in range(29)]))[0], "ok",
           "㉗窗口邊界：距最新一局 23.9 小時的檔算在動")
        # 分桶邊界
        bk = uh.sqf_buckets([NOW143 - 23.9 * H, NOW143 - 24.1 * H, NOW143 - 71.9 * H,
                             NOW143 - 72.1 * H, NOW143 - 167.9 * H, NOW143 - 168.1 * H,
                             NOW143 - 719.9 * H, NOW143 - 720.1 * H, 0], NOW143)
        eq((bk["<24h"], bk["<72h"], bk["<7d"], bk["<30d"], bk[">=30d"], bk["沒有對局"]),
           (1, 2, 2, 2, 1, 1), "㉗分桶邊界 24／72／168／720 小時各自落在對的桶")
        # 那一行印的分桶（#163）：互斥區間、六桶全印、相加＝檔數。
        # 舊格式「24h N／72h M／>=30d K」讀起來像累計、又漏印 3~7 天／7~30 天兩桶 ⇒ 下面三條舊版都紅。
        import re as _re
        mixed = mk([("a%d.js" % i, [NOW143 - 1 * H]) for i in range(20)]
                   + [("b%d.js" % i, [NOW143 - 30 * H]) for i in range(2)]
                   + [("c%d.js" % i, [NOW143 - 100 * H]) for i in range(3)]
                   + [("d%d.js" % i, [NOW143 - 300 * H]) for i in range(4)]
                   + [("e%d.js" % i, [NOW143 - 1000 * H]) for i in range(5)]
                   + [("f0.js", [])])
        st, line, bad = sf(mixed)
        got = _re.findall(r"(<24h|24~72h|3~7天|7~30天|≥30天|沒有對局) (\d+)", line.split("距現在：")[-1])
        eq([k for k, _ in got], ["<24h", "24~72h", "3~7天", "7~30天", "≥30天", "沒有對局"],
           "㉗那一行六個分桶照順序全印（不再漏 3~7 天／7~30 天）")
        eq([int(v) for _, v in got], [20, 2, 3, 4, 5, 1], "㉗那一行每一桶的數字＝互斥區間的檔數")
        eq(sum(int(v) for _, v in got), 35, "㉗那一行分桶相加＝檔數 35（不是累計、沒有漏桶）")
        eq(("跟著動 20" in line, st), (True, "ok"), "㉗對照：同一份素材「跟著動」仍是距最新一局 24h 內的 20 個")
        # 讀不到的檔算 0 而不是炸掉
        eq(uh.sqf_scan([_os.path.join(mk([]), "不存在.js")], True), {"不存在.js": 0},
           "㉗讀不到的檔算 0（不要讓整份健檢被一個壞檔打斷）")
        eq(uh.sqf_ts(0), "-", "㉗沒有 t 印「-」")
    finally:
        for d in _dirs:
            _sh.rmtree(d, ignore_errors=True)
SQF_SUITE(uh, eq)

# ══ ㉙ 同一天少局（2026-09-17 #168；突變驗收 autopilot/_m168_ctrl.py 會把 DC_SUITE 整段抽出去打改壞的模組）══
# 逐聯賽落後只比「有哪些比賽日」，某一天少幾局看不到（#167 回放：CBLOL 08-15 缺兩局 16.5 天、LEC／LCS 09-12 缺四局 3.5 天）。
# 這次局數有人讀 ⇒ 兩側的去重、±1 天合併、48h 寬限、我們側多收 3h、留給逐聯賽落後叫的那幾天，每一條都配「拿掉就翻面」的對照。


def DC_SUITE(M, eq):
    import contextlib as _cl
    import datetime as _dt
    import io as _io
    import json as _json
    import os as _os
    import shutil as _sh
    import sys as _sys
    import tempfile as _tf
    import types as _ty

    NOW = _dt.datetime(2026, 9, 16, 8, 0)          # UTC；since 09-02、48h 那一刀 09-14 08:00、落後寬限 09-16 02:00
    dirs = []
    # 欄序刻意打亂、值按欄名擺（#139：按位置填會讓硬編偏移「剛好」過關）
    cols = ["patch", "game", "red_teamname", "participantid", "league", "date", "blue_teamname"]

    def mk(games, broken=False):
        """games＝[(date, league, 藍, 紅, 局號)] → 假 repo 根目錄；年度檔一局 6 列（跟真的一樣）。"""
        r = _tf.mkdtemp(prefix="uh_dc_")
        dirs.append(r)
        _os.makedirs(_os.path.join(r, "data"))
        p = _os.path.join(r, "data", "data_2026.js")
        if broken:
            _io.open(p, "w", encoding="utf-8").write('window.LOL_DATA={"tabs":{"RAW_DATA":[["date"')
            return r
        raw = [list(cols)]
        for d, lg, b, rd, g in games:
            for pid in (1, 2, 3, 4, 5, 100):
                cell = {"date": d, "league": lg, "blue_teamname": b, "red_teamname": rd,
                        "game": g, "participantid": pid, "patch": "26.18"}
                raw.append([cell[c] for c in cols])
        _io.open(p, "w", encoding="utf-8").write(
            "window.LOL_DATA=" + _json.dumps({"fetched_at": "2026-09-16 07:00", "tabs": {"RAW_DATA": raw}},
                                             ensure_ascii=False) + ";")
        return r

    def dp(r):
        return [_os.path.join(r, "data", "data_2026.js")]

    def wk(rows, filter_since=True):
        """rows＝[(OverviewPage, 開賽, 隊1, 隊2, 局號)]；局號給 None ⇒ 模擬舊出口只有 ov／dt。"""
        def fetch(since, timeout=90):
            out = []
            for ov, t, a, b, g in rows:
                if filter_since and t[:10] < since:
                    continue
                out.append({"ov": ov, "dt": t} if g is None else {"ov": ov, "dt": t, "t1": a, "t2": b, "g": g})
            return out
        return fetch

    def DC(r, fetch, **kw):
        try:
            return M.daycount_problems(NOW, dp(r) if isinstance(r, str) else r, fetch=fetch, **kw)
        except Exception as e:
            return "RAISED", ["%s: %s" % (type(e).__name__, e)]

    LCS = "LCS/2026 Season/Championship"
    try:
        # ① 基本正例：09-12 SR vs C9 三局我們一局都沒有（09-13 有）⇒ 報、指名、異常行
        W1 = wk([(LCS, "2026-09-12 20:00:00", "SR", "C9", "1"), (LCS, "2026-09-12 20:50:00", "SR", "C9", "2"),
                 (LCS, "2026-09-12 21:40:00", "SR", "C9", "3"), (LCS, "2026-09-13 20:00:00", "TL", "FLY", "1")])
        r1 = mk([("2026-09-13 20:01:10", "LCS", "TL", "FLY", 1)])
        st, ms = DC(r1, W1)
        eq(st, "bad", "㉙① 某一天少三局 ⇒ bad")
        eq(any("LCS 2026-09-12 少 3 局（wiki 3、我們 0；最早一局開賽 84 小時前）" in m for m in ms), True,
           "㉙① 訊息指名聯賽／日期／少幾局／wiki 與我們各幾局／最早一局幾小時前（得到 %r）" % (ms,))
        eq(sum(1 for m in ms if m.startswith("異常：")), 1, "㉙① 恰好一行「異常：」（main 靠它收進結論）")
        eq(sum(1 for m in ms if m.endswith("<< 異常")), 1, "㉙① 只指名少局的那一天（相鄰 09-13 局數對得上，不可以被合併牽連）")
        # ② 對照：三局都在 ⇒ ok、一行都不印
        r2 = mk([("2026-09-12 20:01:00", "LCS", "SR", "C9", 1), ("2026-09-12 20:51:00", "LCS", "SR", "C9", 2),
                 ("2026-09-12 21:41:00", "LCS", "SR", "C9", 3), ("2026-09-13 20:01:10", "LCS", "TL", "FLY", 1)])
        eq(DC(r2, W1), ("ok", []), "㉙② 對照：局數都對得上 ⇒ ok、不佔版面")
        # ③ 我們側去重：一局 6 列。wiki 5 局、我們 3 局（18 列）⇒ 仍要報（不去重會變成 18 > 5 而靜音）
        W3 = wk([(LCS, "2026-09-10 20:0%d:00" % i, "A", "B", str(i + 1)) for i in range(5)])
        r3 = mk([("2026-09-10 20:0%d:30" % i, "LCS", "A", "B", i + 1) for i in range(3)])
        eq(DC(r3, W3)[0], "bad", "㉙③ 我們側以局去重（一局 6 列）：wiki 5／我們 3 ⇒ 報")
        # ④ 我們比 wiki 多不報（PBFIX 人工補局）
        r4 = mk([("2026-09-10 20:0%d:30" % i, "LCS", "A", "B", i + 1) for i in range(5)] +
                [("2026-09-10 00:21:00", "LCS", "GEN", "DK", 1)])
        eq(DC(r4, W3), ("ok", []), "㉙④ 我們比 wiki 多（人工釘住的補局）⇒ 不報")
        # ⑤ wiki 側去重：同一局登錄兩次（LCP 08-13）⇒ 不報；同一分鐘但隊伍不同＝兩局 ⇒ 要報
        LCP = "LCP/2026 Season/Split 3"
        W5 = wk([(LCP, "2026-09-10 09:19:00", "DCG", "GAM", "1"), (LCP, "2026-09-10 09:19:00", "DCG", "GAM", "1"),
                 (LCP, "2026-09-10 10:26:00", "DCG", "GAM", "2"), (LCP, "2026-09-10 10:26:00", "DCG", "GAM", "2")])
        r5 = mk([("2026-09-10 09:20:00", "LCP", "DCG", "GAM", 1), ("2026-09-10 10:27:00", "LCP", "DCG", "GAM", 2)])
        eq(DC(r5, W5), ("ok", []), "㉙⑤ wiki 把同一局登錄兩次 ⇒ 去重後對得上、不報")
        W5b = wk([(LCP, "2026-09-10 09:00:00", "DCG", "GAM", "1"), (LCP, "2026-09-10 09:00:00", "CFO", "TSW", "1")])
        r5b = mk([("2026-09-10 09:01:00", "LCP", "DCG", "GAM", 1)])
        eq(DC(r5b, W5b)[0], "bad", "㉙⑤ 同一分鐘兩個不同系列＝兩局（去重鍵要含隊伍）⇒ 少一局要報")
        # ⑥ 舊出口只有 ov／dt（缺 t1／t2／g）⇒ 不丟例外，退成用開賽分鐘去重
        W6 = wk([(LCS, "2026-09-10 20:00:00", None, None, None), (LCS, "2026-09-10 20:00:00", None, None, None),
                 (LCS, "2026-09-10 21:00:00", None, None, None)])
        eq(DC(r3, W6)[0] in ("ok", "bad"), True, "㉙⑥ 缺欄的回應不丟例外")
        eq(DC(mk([("2026-09-10 20:00:30", "LCS", "A", "B", 1)]), W6)[1][:1],
           ["  LCS 2026-09-10 少 1 局（wiki 2、我們 1；最早一局開賽 132 小時前）  << 異常"],
           "㉙⑥ 缺欄時用開賽分鐘去重：同一分鐘兩筆算一局")
        # ⑦ 48h 寬限：開賽 46 小時前少一局 ⇒ 還不報；寬限改 0 ⇒ 報（證明寬限真的在作用）
        W7 = wk([(LCS, "2026-09-14 10:00:00", "A", "B", "1"), (LCS, "2026-09-14 11:00:00", "A", "B", "2"),
                 (LCS, "2026-09-15 10:00:00", "C", "D", "1")])
        r7 = mk([("2026-09-14 10:00:30", "LCS", "A", "B", 1), ("2026-09-15 10:00:30", "LCS", "C", "D", 1)])
        eq(DC(r7, W7), ("ok", []), "㉙⑦ 開賽未滿 48 小時的少局不報（OE 當天延遲是常態）")
        eq(DC(r7, W7, grace_h=0)[0], "bad", "㉙⑦ 正控制：寬限改 0 ⇒ 同一份資料報")
        # ⑧ 我們側多收 3 小時：同一局 wiki 07:58（剛好在那一刀前）、我們 08:03（刀後）⇒ 不報；多收改 0 ⇒ 誤報
        W8 = wk([(LCS, "2026-09-14 07:58:00", "A", "B", "1")])
        r8 = mk([("2026-09-14 08:03:00", "LCS", "A", "B", 1)])
        eq(DC(r8, W8), ("ok", []), "㉙⑧ 兩邊開賽時間跨在 48h 那一刀上 ⇒ 我們側多收 3h 吸掉、不誤報")
        eq(DC(r8, W8, slack_h=0)[0], "bad", "㉙⑧ 正控制：多收改 0 ⇒ 同一份資料誤報（證明 slack 在作用）")
        # ⑨ ±1 天合併：wiki 09-10 23:50、我們 09-11 00:05（跨午夜）⇒ 不報
        W9 = wk([(LCS, "2026-09-10 23:50:00", "A", "B", "1")])
        r9 = mk([("2026-09-11 00:05:00", "LCS", "A", "B", 1)])
        eq(DC(r9, W9), ("ok", []), "㉙⑨ 開賽時間跨午夜掉到隔天 ⇒ 相鄰天合併後對得上、不報")
        # ⑩ 視窗：伺服器回了 since 之前的局（08-15，視窗 30 天 ⇒ since 08-17）⇒ 不算；六聯賽以外（PCS）⇒ 不算
        W10 = wk([(LCS, "2026-08-15 20:00:00", "A", "B", "1"), ("PCS/2026 Season/Summer", "2026-09-10 10:00:00", "X", "Y", "1")],
                 filter_since=False)
        eq(DC(mk([]), W10), ("ok", []), "㉙⑩ 視窗外的舊局、非一級聯賽都不算（不誤報）")
        eq(DC(mk([]), W10, window_d=40)[0], "bad", "㉙⑩ 正控制：視窗拉到 40 天 ⇒ 同一局報（證明擋掉它的是 since）")
        # ⑪ 留給逐聯賽落後叫：我們最後 LPL 09-05、wiki 之後還有 3 天 ⇒ 這裡不叫（逐聯賽落後會叫）
        LPL = "LPL/2026 Season/Split 3"
        W11 = wk([(LPL, "2026-09-05 09:00:00", "A", "B", "1"), (LPL, "2026-09-08 09:00:00", "A", "B", "1"),
                  (LPL, "2026-09-09 09:00:00", "C", "D", "1"), (LPL, "2026-09-10 09:00:00", "E", "F", "1")])
        r11 = mk([("2026-09-05 09:00:30", "LPL", "A", "B", 1)])
        eq(DC(r11, W11), ("ok", []), "㉙⑪ 落後 3 個比賽日的那幾天留給逐聯賽落後、這裡不重複叫")
        eq(M.lag_problems(NOW, dp(r11), fetch=W11)[0], "bad", "㉙⑪ 前提：同一份資料逐聯賽落後確實會叫")
        # ⑫ 只落後 1 個比賽日、但已經超過 48h（逐聯賽落後門檻 2 不會叫）⇒ 歸這裡叫
        W12 = wk([(LPL, "2026-09-05 09:00:00", "A", "B", "1"), (LPL, "2026-09-10 09:00:00", "E", "F", "1"),
                  (LPL, "2026-09-16 03:00:00", "G", "H", "1")])     # 5 小時前那局在落後寬限 6h 內，不算落後
        st12, ms12 = DC(r11, W12)
        eq(st12, "bad", "㉙⑫ 只落後 1 天但已 >48h ⇒ 這裡叫")
        eq(any("LPL 2026-09-10 少 1 局" in m for m in ms12), True, "㉙⑫ 指名 LPL 09-10")
        eq(M.lag_problems(NOW, dp(r11), fetch=W12)[0], "ok", "㉙⑫ 前提：同一份資料逐聯賽落後不會叫（兩條不是都啞）")
        # ⑯ 視窗 30 天（#169）：CBLOL 08-15 缺了 16.5 天，14 天視窗會在它還缺著時滑出去、之後照印 ✓
        eq(M.DAYCOUNT_WINDOW_D, 30, "㉙⑯ 同一天少局的視窗 30 天（不借逐聯賽落後的 14 天）")
        W16 = wk([(LCS, "2026-08-28 20:00:00", "A", "B", "1"), (LCS, "2026-08-28 20:50:00", "A", "B", "2"),
                  (LCS, "2026-09-13 20:00:00", "C", "D", "1")])
        r16 = mk([("2026-08-28 20:00:30", "LCS", "A", "B", 1), ("2026-09-13 20:00:30", "LCS", "C", "D", 1)])
        st16, ms16 = DC(r16, W16)
        eq((st16, any("LCS 2026-08-28 少 1 局" in m for m in ms16)), ("bad", True),
           "㉙⑯ 19 天前少一局 ⇒ 預設視窗照報（得到 %r）" % (ms16,))
        eq(DC(r16, W16, window_d=14), ("ok", []), "㉙⑯ 正控制：同一份資料視窗 14 天 ⇒ 滑出去、不報")
        # ⑰ 兩個視窗不同時「留給逐聯賽落後」要照它自己的 14 天算：我們最後 LCS 08-27（20 天前），
        #    wiki 08-29 兩局（18 天前）＋09-13 一局 ⇒ 30 天內落後 2 天，但逐聯賽落後只看得到 09-13 那 1 天（不叫）
        W17 = wk([(LCS, "2026-08-27 20:00:00", "A", "B", "1"), (LCS, "2026-08-29 20:00:00", "C", "D", "1"),
                  (LCS, "2026-08-29 20:50:00", "C", "D", "2"), (LCS, "2026-09-13 20:00:00", "E", "F", "1")])
        r17 = mk([("2026-08-27 20:00:30", "LCS", "A", "B", 1)])
        eq(M.lag_problems(NOW, dp(r17), fetch=W17)[0], "ok", "㉙⑰ 前提：逐聯賽落後（14 天）只看到 1 天、不叫")
        st17, ms17 = DC(r17, W17)
        eq((st17, any("LCS 2026-08-29 少 2 局" in m for m in ms17), any("LCS 2026-09-13 少 1 局" in m for m in ms17)),
           ("bad", True, True), "㉙⑰ 兩條不可以都啞：逐聯賽落後不叫 ⇒ 這裡把 08-29／09-13 都叫出來（得到 %r）" % (ms17,))
        # ⑱ 停擺：逐聯賽落後會叫（14 天內落後 3 天）⇒ 我們最後比賽日之後**整段**讓給它，連 14 天以前的 08-29 也不重複叫
        W18 = wk([(LPL, "2026-08-27 09:00:00", "A", "B", "1"), (LPL, "2026-08-29 09:00:00", "C", "D", "1"),
                  (LPL, "2026-09-05 09:00:00", "E", "F", "1"), (LPL, "2026-09-08 09:00:00", "G", "H", "1"),
                  (LPL, "2026-09-10 09:00:00", "I", "J", "1")])
        r18 = mk([("2026-08-27 09:00:30", "LPL", "A", "B", 1)])
        eq(M.lag_problems(NOW, dp(r18), fetch=W18)[0], "bad", "㉙⑱ 前提：逐聯賽落後會叫")
        eq(DC(r18, W18), ("ok", []), "㉙⑱ 停擺整段讓給逐聯賽落後：14 天以前的 08-29 也不重複叫")
        # ⑳ ±1 天合併時相鄰天兩側同一刀（#170）。48h 那一刀 09-14 08:00、我們那一刀 09-14 11:00。
        #    重現 08-19 00:25 那班：當天真的少 2 局，隔天 3 局剛滿 45h（我們收了、wiki 48h 還沒收）⇒ #168 寫法 5+1 ≤ 3+4 抵掉
        W20 = wk([(LCS, "2026-09-13 10:00:00", "A", "B", "1"), (LCS, "2026-09-13 11:00:00", "A", "B", "2"),
                  (LCS, "2026-09-13 12:00:00", "A", "B", "3"), (LCS, "2026-09-13 13:00:00", "C", "D", "1"),
                  (LCS, "2026-09-13 14:00:00", "C", "D", "2"), (LCS, "2026-09-14 07:00:00", "E", "F", "1"),
                  (LCS, "2026-09-14 08:30:00", "G", "H", "1"), (LCS, "2026-09-14 09:30:00", "G", "H", "2"),
                  (LCS, "2026-09-14 10:30:00", "G", "H", "3")])
        next4 = [("2026-09-14 07:00:30", "LCS", "E", "F", 1), ("2026-09-14 08:30:30", "LCS", "G", "H", 1),
                 ("2026-09-14 09:30:30", "LCS", "G", "H", 2), ("2026-09-14 10:30:30", "LCS", "G", "H", 3)]
        r20 = mk([("2026-09-13 1%d:00:30" % i, "LCS", "A", "B", i + 1) for i in range(3)] + next4)
        st20, ms20 = DC(r20, W20)
        eq((st20, any("LCS 2026-09-13 少 2 局（wiki 5、我們 3；最早一局開賽 70 小時前）" in m for m in ms20),
            sum(1 for m in ms20 if m.endswith("<< 異常"))), ("bad", True, 1),
           "㉙⑳ 相鄰天 slack 收進來的局不可以抵掉當天真的少局（得到 %r）" % (ms20,))
        r20b = mk([("2026-09-13 1%d:00:30" % i, "LCS", "A", "B", i + 1) for i in range(3)] +
                  [("2026-09-13 13:00:30", "LCS", "C", "D", 1), ("2026-09-13 14:00:30", "LCS", "C", "D", 2)] + next4)
        eq(DC(r20b, W20), ("ok", []), "㉙⑳ 對照：當天 5 局都在 ⇒ ok（上一條紅的只是那 2 局）")
        #    當天的少局仍照 48h 寬限算：wiki 09-14 00:05 那局我們掛到前一天 23:55（跨午夜）、09:00 那局開賽 47h 我們還沒有
        #    ⇒ 不報（09:00 那局在寬限內，不可以因為合併改用 45h 那一刀就被算成少局）
        W20c = wk([(LCS, "2026-09-14 00:05:00", "A", "B", "1"), (LCS, "2026-09-14 09:00:00", "C", "D", "1")])
        eq(DC(mk([("2026-09-13 23:55:30", "LCS", "A", "B", 1)]), W20c), ("ok", []),
           "㉙⑳ 跨午夜＋當天還在寬限內的一局 ⇒ 合併後不報")
        st20c, ms20c = DC(mk([]), W20c)
        eq((st20c, any("LCS 2026-09-14 少 1 局（wiki 1、我們 0；" in m for m in ms20c)), ("bad", True),
           "㉙⑳ 正控制：前一天沒有那局可抵 ⇒ 報少 1 局（寬限內那局不算，得到 %r）" % (ms20c,))
        # ⑬ 降級：wiki 查不到／回空／撞上限、年度檔讀不懂 ⇒ skip；檔不存在 ⇒ 當 0 局照報
        def boom(since, timeout=90):
            raise IOError("HTTP Error 503")
        s, m = DC(r1, boom)
        eq((s, any("查不到 Leaguepedia" in x for x in m)), ("skip", True), "㉙⑬ wiki 丟例外 ⇒ skip 並講原因")
        eq(DC(r1, lambda since, timeout=90: [])[0], "skip", "㉙⑬ wiki 回空陣列 ⇒ skip（不可當成沒少局）")
        full = [{"ov": "PCS/2026 Season/Summer", "dt": "2026-09-10 10:00:00"}] * M.LAG_LIMIT
        s, m = DC(r1, lambda since, timeout=90: full)
        eq((s, any("撞到上限" in x for x in m)), ("skip", True), "㉙⑬ 回滿 LAG_LIMIT 列 ⇒ skip（最新的局可能被截掉）")
        eq(DC(r1, lambda since, timeout=90: full[1:])[0], "ok", "㉙⑬ 對照：少一列就不算撞上限")
        eq(M.wiki_days("2026-09-02", fetch=lambda since: full)[0], False,
           "㉙⑬ 逐聯賽落後的 wiki_days 也把撞上限當查不到（不然被截掉的最新局會被讀成落後）")
        eq(M.wiki_days("2026-09-02", fetch=lambda since: full[1:])[0], True, "㉙⑬ 對照：wiki_days 少一列照常")
        s, m = DC(mk([], broken=True), W1)
        eq((s, any("讀不懂我們的年度檔 data_2026.js" in x for x in m)), ("skip", True),
           "㉙⑬ 年度檔寫到一半 ⇒ skip、點名檔案（不丟例外）")
        ghost = _os.path.join(mk([]), "data", "data_2099.js")
        eq(DC([ghost], W3)[0], "bad", "㉙⑬ 年度檔不存在＝我們 0 局 ⇒ 照報（不是略過；W3 只有一個比賽日，不會整段留給逐聯賽落後）")
        eq(DC([ghost], W1), ("ok", []), "㉙⑬ 年度檔不存在、wiki 有 2 個比賽日 ⇒ 整段留給逐聯賽落後叫（這裡不重複）")
        eq(DC([dp(r2)[0], ghost], W1), ("ok", []), "㉙⑬ 一串路徑：讀得到的那個有局 ⇒ 合併後對得上")

        # ⑭ main() 端到端：假 repo＋假時鐘＋假出口（記次數）
        real = (M.ROOT, M.wiki_rows, M.datetime, M.LOG, M.CONSOLE, M.BASE, M.live_dup, list(_sys.argv))
        CLOCK = [NOW]

        class _T(_dt.datetime):
            @classmethod
            def utcnow(cls):
                return CLOCK[0]
        shim = _ty.ModuleType("datetime_shim_dc")
        for k in dir(_dt):
            if not k.startswith("__"):
                setattr(shim, k, getattr(_dt, k))
        shim.datetime = _T
        tmp = _tf.mkdtemp(prefix="uh_dc_main_")
        dirs.append(tmp)
        _io.open(_os.path.join(tmp, "log.txt"), "w", encoding="utf-8").write(
            "==== run_update %s（並行 4）====\n---- fetch_x（1.0s，exit 0）----\n守門通過\n"
            % _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        def run_main(root, fetch, extra=()):
            calls = []

            def spy(since, timeout=90):
                calls.append(since)
                return fetch(since)
            M.ROOT, M.wiki_rows, M.datetime = root, spy, shim
            M.LOG, M.CONSOLE, M.BASE = (_os.path.join(tmp, "log.txt"), _os.path.join(tmp, "console.txt"),
                                        _os.path.join(tmp, "base.json"))
            M.live_dup = lambda timeout=None: (0, "")
            _sys.argv = ["update_health.py", "--no-save", "--no-live", "--no-soloqfresh"] + list(extra)
            buf = _io.StringIO()
            try:
                with _cl.redirect_stdout(buf):
                    rc = M.main()
            except Exception as e:
                rc = "RAISED %s: %s" % (type(e).__name__, e)
            finally:
                (M.ROOT, M.wiki_rows, M.datetime, M.LOG, M.CONSOLE, M.BASE, M.live_dup) = real[:7]
                _sys.argv = list(real[7])
            out = buf.getvalue()
            line = [l.strip() for l in out.splitlines() if l.strip().startswith("同一天少局")]
            concl = [l for l in out.splitlines() if l.startswith("結論：")]
            return rc, out, (line[0] if line else None), (concl[0] if concl else ""), calls

        rc, out, line, concl, calls = run_main(r1, W1)
        eq(isinstance(rc, int), True, "㉙⑭ main() 跑完沒有例外（得到 %r）" % (rc,))
        eq(line, "同一天少局（近 30 天／開賽滿 48h／wiki 比我們多才算）：⚠ 有少局", "㉙⑭ main 印出同一天少局那行（⚠）")
        eq("LCS 2026-09-12 少 3 局" in concl, True, "㉙⑭ 少局收進結論（得到 %r）" % concl)
        # ⚠ 不斷言「離開碼 1」：這個假 repo 只有 data/，其他項一律「讀不到」⇒ 離開碼恆為 1、沒有鑑別力
        #   （#168 突變 N1「少局沒收進結論」時那條照樣綠＝假綠）。收進結論由上一條的結論字串證明。
        eq(len(calls), 1, "㉙⑭ 逐聯賽落後與同一天少局共用一個 wiki 請求（得到 %d 次）" % len(calls))
        eq(calls[:1], ["2026-08-17"], "㉙⑭ 共用的那個請求用兩個視窗裡較早的 since（30 天前；14 天會讓少局那項缺資料）")
        rc, out, line, concl, calls = run_main(r2, W1)
        eq((line or "").endswith("✓ 逐日局數都對得上"), True, "㉙⑭ 對照：局數都在 ⇒ ✓")
        eq("少 " in concl, False, "㉙⑭ 對照：結論沒有少局")
        rc, out, line, concl, calls = run_main(r1, W1, ["--no-lag"])
        eq(line, "同一天少局：（--no-lag 跳過）", "㉙⑭ --no-lag 一起跳過同一天少局")
        eq((len(calls), "少 " in concl), (0, False), "㉙⑭ --no-lag ⇒ 一個請求都不發、結論沒有少局")
        rc, out, line, concl, calls = run_main(r1, boom)
        eq((isinstance(rc, int), (line or "").endswith("略過（原因見下一行）"), len(calls)), (True, True, 1),
           "㉙⑭ wiki 掛掉 ⇒ main 照樣出結論、兩項都略過、失敗也只打一次（得到 rc=%r line=%r calls=%d）"
           % (rc, line, len(calls)))
        # ⑲ 跨年（#169）：2027-01-20 時逐聯賽落後的 14 天只碰 2027，同一天少局的 30 天要連 2026 的檔一起讀
        #    ——拿錯那串，12-28 那局在 data_2026.js 裡、卻會被讀成「我們 0 局」天天誤報到 1 月底。
        ry = _tf.mkdtemp(prefix="uh_dc_year_")
        dirs.append(ry)
        _os.makedirs(_os.path.join(ry, "data"))
        for yr, games in ((2026, [("2026-12-28 10:00:30", "LCK", "A", "B", 1)]),
                          (2027, [("2027-01-15 10:00:30", "LCK", "C", "D", 1)])):
            raw = [list(cols)]
            for d, lg, b, rd, g in games:
                for pid in (1, 2, 3, 4, 5, 100):
                    cell = {"date": d, "league": lg, "blue_teamname": b, "red_teamname": rd,
                            "game": g, "participantid": pid, "patch": "26.18"}
                    raw.append([cell[c] for c in cols])
            _io.open(_os.path.join(ry, "data", "data_%d.js" % yr), "w", encoding="utf-8").write(
                "window.LOL_DATA=" + _json.dumps({"fetched_at": "x", "tabs": {"RAW_DATA": raw}}) + ";")
        LCK = "LCK/2027 Season/Cup"
        W19 = wk([(LCK, "2026-12-28 10:00:00", "A", "B", "1"), (LCK, "2027-01-15 10:00:00", "C", "D", "1")])
        CLOCK[0] = _dt.datetime(2027, 1, 20, 8, 0)
        try:
            rc, out, line, concl, calls = run_main(ry, W19)
        finally:
            CLOCK[0] = NOW
        eq((line or "").endswith("✓ 逐日局數都對得上"), True,
           "㉙⑲ 跨年：少局那項讀到 data_2026.js 的 12-28 ⇒ ✓（得到 %r；%r）" % (line, concl))
        eq(calls[:1], ["2026-12-21"], "㉙⑲ 跨年時請求的 since 也是 30 天前（得到 %r）" % (calls,))
        eq(M.daycount_problems(_dt.datetime(2027, 1, 20, 8, 0), [_os.path.join(ry, "data", "data_2027.js")],
                               fetch=W19)[0], "bad",
           "㉙⑲ 正控制：同一份資料只給 data_2027.js ⇒ 12-28 那局被讀成我們 0 局（證明上一條靠的是讀對檔）")
    finally:
        for d in dirs:
            _sh.rmtree(d, ignore_errors=True)
# ══ ㉙ 結束（_m168_ctrl.py 抽取到這一行為止）══


DC_SUITE(uh, eq)

# ── ⓪ 收尾：整份測試沒有任何一次撞到封鎖器（被 wiki_days 的 except 吞掉的也算），
#    而且假出口真的有被 main() 走到（⑫⑮ 都沒帶 --no-lag）——否則上一條可能只是 main 根本沒接逐聯賽落後。
eq(NET_HITS, [], "⓪整份測試沒有任何一次真的去連外（有人漏接了出口）")
eq(len(WIKI_CALLS) >= 4, True, "⓪⑫⑮ 那四次 main() 都走到接管的 wiki 出口（得到 %d 次）" % len(WIKI_CALLS))
uh.wiki_rows = _real_wiki_rows
_restore_net_all()

print("update_health 回歸測試：通過 %d 條" % OK[0] + ("" if not NG else "，失敗 %d 條" % len(NG)))
for m in NG:
    print("   ✗ " + m)
sys.exit(1 if NG else 0)
