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
import os
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

# ── ⑬ 端到端：main() 真的把班次點名接進結論（純函式對了、接線斷了一樣沒人知道）──
# 不寫死時鐘：拿「上一班再往前一小時」當日誌時間（⇒ 一定不是這一班寫的），
# 然後斷言 main() 的結論**與 shift_problems 的判斷一致**——寬限期內就不該報，過了寬限就一定要報。
_real_log, _real_console, _real_argv, _real_grace = uh.LOG, uh.CONSOLE, sys.argv, uh.SHIFT_GRACE_MIN
try:
    tmp = tempfile.mkdtemp(prefix="uh_e2e_")
    uh.SHIFT_GRACE_MIN = 0        # 寬限歸零＝不管這一輪幾點跑，舊日誌一定要被判定成「沒跑」
    uh.CONSOLE = os.path.join(tmp, "no_console.txt")
    uh.LOG = os.path.join(tmp, "log.txt")
    sys.argv = ["update_health.py", "--no-save", "--no-live"]   # 這組測班次，不必真的去掃 26MB 算同名

    def main_out(when_ts):
        s = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(when_ts))
        io.open(uh.LOG, "w", encoding="utf-8").write(
            "==== run_update %s（並行 4）====\n---- fetch_x（1.0s，exit 0）----\n"
            "文本體檢：掃描 1 條字串 → 錯誤 0、提醒 0\n未審定的可疑同名 0\n守門通過\n" % s)
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
    eq("沒跑" in concl, want_bad, "⑬main() 的結論與班次點名一致（舊日誌）")
    # 正控制：日誌換成這一班寫的，結論就不可以再說「沒跑」——否則上面那條是恆真的
    fresh, out2 = main_out(b + 300)
    concl2 = [l for l in out2.splitlines() if l.startswith("結論：")][0]
    eq("沒跑" in concl2, False, "⑬正控制：這一班的日誌 ⇒ 結論不報沒跑")
    eq("✓ 已跑" in out2, True, "⑬正控制：說明行說已跑")
finally:
    uh.LOG, uh.CONSOLE, sys.argv = _real_log, _real_console, _real_argv
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
try:
    tmp = tempfile.mkdtemp(prefix="uh_dup_e2e_")
    uh.CONSOLE = os.path.join(tmp, "no_console.txt")
    uh.LOG = os.path.join(tmp, "log.txt")
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
        return [l for l in buf.getvalue().splitlines() if l.startswith("可疑同名：")]

    eq(dup_lines(["update_health.py", "--no-save"]),
       ["可疑同名：0（現況重算；那一班日誌是 10，已經是舊帳）"], "⑮main() 印的是現況不是快照")
    # 正控制：--no-live 就該退回快照那個舊數字，否則上面那條可能是恆真的
    eq(dup_lines(["update_health.py", "--no-save", "--no-live"]),
       ["可疑同名：10（那一班日誌的舊數字；--no-live 跳過重算）"], "⑮正控制：--no-live 退回快照 10")
finally:
    uh.LOG, uh.CONSOLE, sys.argv, uh.live_dup = _real_log, _real_console, _real_argv, _real_live
    shutil.rmtree(tmp, ignore_errors=True)

print("update_health 回歸測試：通過 %d 條" % OK[0] + ("" if not NG else "，失敗 %d 條" % len(NG)))
for m in NG:
    print("   ✗ " + m)
sys.exit(1 if NG else 0)
