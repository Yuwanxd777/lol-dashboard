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

# ══ 網路封鎖：三個出口一起堵，並證明堵得住 ═══════════════════════════════
class BlockedNetwork(RuntimeError):
    pass


def _blow(*a, **k):
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
        # 讀不到的檔算 0 而不是炸掉
        eq(uh.sqf_scan([_os.path.join(mk([]), "不存在.js")], True), {"不存在.js": 0},
           "㉗讀不到的檔算 0（不要讓整份健檢被一個壞檔打斷）")
        eq(uh.sqf_ts(0), "-", "㉗沒有 t 印「-」")
    finally:
        for d in _dirs:
            _sh.rmtree(d, ignore_errors=True)
SQF_SUITE(uh, eq)

print("update_health 回歸測試：通過 %d 條" % OK[0] + ("" if not NG else "，失敗 %d 條" % len(NG)))
for m in NG:
    print("   ✗ " + m)
sys.exit(1 if NG else 0)
