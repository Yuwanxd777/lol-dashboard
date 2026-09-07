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

import os
import sys

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

print("update_health 回歸測試：通過 %d 條" % OK[0] + ("" if not NG else "，失敗 %d 條" % len(NG)))
for m in NG:
    print("   ✗ " + m)
sys.exit(1 if NG else 0)
