# -*- coding: utf-8 -*-
"""check_player_dup 的「同隊別名」判定回歸測試（純函式，秒級，不碰網路也不讀 data/）。

為什麼有這支：2026-09-07 發現 check_player_dup 報的 10 個可疑同名裡有 5 個
（Tarzan／BeeOne／Tear／ImbaMiBeo／Lucas）全來自同一個假訊號——2015-03-25 GPL 那天，
同一批五人的四局比賽被 OE 記成兩個隊名（"An Phat Ultimate" 兩局、"Ultimate" 兩局），
偵測器把它當成「同一天出現在兩支不同隊」的鐵證（+10 分）。

修法是 _alias_groups：同一天兩個隊名的出賽陣容重疊 >= ALIAS_MIN(3) 人就併成同一隊。
全庫掃過，同日不同隊的隊名配對，陣容交集只有 1 人與 5 人兩種、沒有中間值。

每條測試都有「正例會動」的對照：別名要被併（下面 t_alias_*），真的同日兩隊要照報
（t_real_*），否則這支測試綠了也只是證明判定函式永遠回傳同一個答案。

用法：python scripts/check_player_dup_test.py
"""
import io, os, sys

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_player_dup import _alias_groups, ALIAS_MIN   # noqa: E402

D = "2015-03-25"
FAILED = []


def check(label, got, want):
    ok = got == want
    print(("  ✓ " if ok else "  ✗ ") + label + ("" if ok else f"\n      得到 {got}\n      預期 {want}"))
    if not ok:
        FAILED.append(label)


def groups(roster):
    """roster: {隊名: [選手,...]} → 排序好的群組，方便比對"""
    r = {(D, t): set(ns) for t, ns in roster.items()}
    return sorted(sorted(g) for g in _alias_groups(D, set(roster), r))


FIVE = ["Tarzan", "BeeOne", "Tear", "ImbaMiBeo", "Lucas"]

print("── 同隊別名要被併成一群 ──")
check("t_alias_真實案例：An Phat Ultimate／Ultimate 同一批五人",
      groups({"An Phat Ultimate": FIVE, "Ultimate": FIVE}),
      [["An Phat Ultimate", "Ultimate"]])
check("t_alias_剛好 3 人重疊（門檻邊界，要併）",
      groups({"Long Name": ["a", "b", "c", "d", "e"], "Short": ["a", "b", "c", "x", "y"]}),
      [["Long Name", "Short"]])
check("t_alias_三個寫法連鎖併成一群",
      groups({"A Team": FIVE, "A": FIVE, "Team A": FIVE}),
      [["A", "A Team", "Team A"]])

print("── 真的同日兩隊出賽要照報 ──")
check("t_real_只有那個人自己重疊（Cool：Oh My God／Salvage Javelin）",
      groups({"Oh My God": ["Cool", "Gogoing", "Loveling", "San", "Cloud"],
              "Salvage Javelin": ["Cool", "Ceros", "Yutorimoyashi", "Paz", "Dara"]}),
      [["Oh My God"], ["Salvage Javelin"]])
check("t_real_2 人重疊（門檻邊界，不併）",
      groups({"Team X": ["a", "b", "c", "d", "e"], "Team Y": ["a", "b", "v", "w", "z"]}),
      [["Team X"], ["Team Y"]])
check("t_real_完全沒重疊",
      groups({"Team X": ["a", "b"], "Team Y": ["c", "d"]}),
      [["Team X"], ["Team Y"]])

print("── 混合：別名併掉之後仍剩兩支真的不同隊 ──")
check("t_mix_別名一群＋真對手一群",
      groups({"An Phat Ultimate": FIVE, "Ultimate": FIVE,
              "Saigon Jokers": ["Tarzan", "QTV", "Junie", "Archie", "Optimus"]}),
      [["An Phat Ultimate", "Ultimate"], ["Saigon Jokers"]])

print("── 邊界 ──")
check("t_edge_只有一支隊", groups({"Solo Team": FIVE}), [["Solo Team"]])
check("t_edge_查不到陣容（roster 沒這天）",
      sorted(sorted(g) for g in _alias_groups(D, {"A", "B"}, {})),
      [["A"], ["B"]])

print(f"\nALIAS_MIN = {ALIAS_MIN}")
if FAILED:
    print(f"✗ {len(FAILED)} 條失敗：" + "、".join(FAILED))
    sys.exit(1)
print("✓ 全部通過")
