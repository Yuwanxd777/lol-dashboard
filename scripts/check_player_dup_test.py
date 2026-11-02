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
from check_player_dup import _alias_groups, ALIAS_MIN, INTL, GROUP, score, unknown_leagues   # noqa: E402

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
# ── #2453：國際賽碼不算大區、新碼要出聲 ───────────────────────────────
def _seg(lg, y, pos="BOT", n=20):
    return {"y": str(y), "lg": lg, "pos": pos, "n": n, "f": f"{y}-03-01", "l": f"{y}-04-01", "tm": "T"}

def _sc(segs):
    return score("x", {"segs": segs, "sameday": []})[0]

_home = [_seg("LCS", 2020), _seg("LCS", 2022)]
for _lg in ("AC", "DCup", "FST", "ENC", "亞運"):
    check(f"t_intl_{_lg}_不多出跨區分", _sc(_home + [_seg(_lg, 2023)]), _sc(_home))
check("t_intl_正控制_沒登記的碼會多 2 分", _sc(_home + [_seg("ZZ_PROBE", 2023)]), _sc(_home) + 2)
check("t_intl_正控制_真跨區照報", _sc(_home + [_seg("LCK", 2023)]), _sc(_home) + 2)
# JoJo 型：真跨區被 AC 自成一區的重疊遮掉
_jojo = [_seg("LPL", 2013), _seg("CBLOL", 2019), _seg("CBLOL", 2026), _seg("AC", 2026)]
_INTL_NOAC = set(INTL)
INTL.discard("AC")
_masked = _sc(_jojo)
INTL.add("AC")
check("t_intl_JoJo型_AC 拿掉才會多出跨區分", (_sc(_jojo) - _masked) > 0, True)
check("t_intl_INTL 還原", INTL == _INTL_NOAC, True)
check("t_ewcq_歸該區", [GROUP[k] for k in ("EWCQ歐洲", "EWCQ韓國", "EWCQ中國", "EWCQ太平洋", "EWCQ巴西", "EWCQ北美")],
      ["EU", "KR", "CN", "APAC", "LATAM", "NA"])
check("t_unk_回報新碼", unknown_leagues({"a": {"segs": [_seg("LCS", 2020), _seg("ZZ_PROBE", 2023), _seg("ZZ_PROBE", 2024), _seg("AC", 2026)]}}),
      [("ZZ_PROBE", 2)])
check("t_unk_都登記過回空", unknown_leagues({"a": {"segs": [_seg("LCS", 2020), _seg("WLDs", 2023)]}}), [])

if FAILED:
    print(f"✗ {len(FAILED)} 條失敗：" + "、".join(FAILED))
    sys.exit(1)
print("✓ 全部通過")
