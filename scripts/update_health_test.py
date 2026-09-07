# -*- coding: utf-8 -*-
"""update_health.py 的回歸測試（2026-09-07 精進迴圈 #44）。

守著兩件事：
  ① `data_counts()` 要涵蓋**全部年份**——舊版 `[-3:]` 讓 2013~2023 共 11 年的縮水永遠測不到。
  ② 基準是「已知良好的高水位」——舊版無條件把本次數字存成基準，於是**縮水隔天就被吃掉**：
     第一輪報一次，存檔後基準跟著變小，之後每輪都看起來正常，問題還在卻再也不會被提醒。

每一組都配「正控制」（把條件改掉，斷言真的會翻面），否則綠燈沒有意義。
用法：python scripts\\update_health_test.py    （exit 0＝全過）
"""
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
               "run_update：2026-09-07 22:00:01（並行 4）\n"
               "步驟 42 個、相加 28.2 分鐘；最久的 8 步：\n"
               "   fetch_soloq_matches            639.5s  ⚠ exit 3\n"
               "守門：✓／push：✓／lint 錯誤級：0／可疑同名：0\n"
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

print("update_health 回歸測試：通過 %d 條" % OK[0] + ("" if not NG else "，失敗 %d 條" % len(NG)))
for m in NG:
    print("   ✗ " + m)
sys.exit(1 if NG else 0)
