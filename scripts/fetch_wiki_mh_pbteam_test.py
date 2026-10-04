# -*- coding: utf-8 -*-
"""PB 補局「短名 → 全名」的守門測試（2026-10-04）。

這一刀有兩種錯法，兩邊都要擋：
  ① 解錯／不解 → 主資料多出幽靈隊（BNK FEARX 與 FearX 並存，戰績切兩半）——10-03 德瑪西亞杯踩到的。
  ② 解太兇 → 把短名硬塞給一支不相干的隊，或在該解不出來的時候亂猜。
所以正例（該解出來）、反例（該回 None）、以及「對到兩支就不准猜」的衝突例都要有。

跑：python scripts/fetch_wiki_mh_pbteam_test.py        （純離線，不打 wiki）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_wiki_mh as M   # noqa: E402

# 2026 德瑪西亞杯全球邀請賽 10-03 那天 MH 實際出現的隊名（全名）
DCUP = ["RED Canids", "Natus Vincere", "FlyQuest", "LGD Gaming", "KT Rolster",
        "Shopify Rebellion", "BNK FEARX", "Team Vitality", "Team WE", "GAM Esports",
        "JD Gaming", "HANJIN BRION"]

# 短名 → 期望解出來的全名（None＝必須解不出來）
CASES = [
    # ── 正例：PB 頁 logo alt 的短名 ──
    ("FearX",      DCUP, "BNK FEARX"),      # 真正踩到的那兩個
    ("Lgd",        DCUP, "LGD Gaming"),
    ("JDG",        DCUP, "JD Gaming"),      # 跳字的短名：jdgaming 含 jdg，第③層接到
    ("JD Gaming",  DCUP, "JD Gaming"),      # 全名照樣要過
    ("jdgaming",   DCUP, "JD Gaming"),      # 大小寫／空白不計
    ("GAM",        DCUP, "GAM Esports"),    # 第②層：字是 gam；LGD/JD Gaming 只是含 gam，不算
    ("Vitality",   DCUP, "Team Vitality"),
    ("HanJin",     DCUP, "HANJIN BRION"),    # hanjin 是 hanjinbrion 的前置子串 ⇒ 該解出來
    # ── 反例：不在這個賽事裡的隊，絕對不可以硬塞 ──
    ("T1",         DCUP, None),
    ("Gen.G",      DCUP, None),
    ("",           DCUP, None),
    (None,         DCUP, None),
    # ── 衝突例：對到兩支以上 ⇒ 不准猜 ──
    ("Team",       DCUP, None),             # Team Vitality／Team WE 都含 → None
    ("RED",        ["RED Canids", "Redemption"], "RED Canids"),  # 第②層正好排除 Redemption
    ("RED",        ["RED Canids", "RED Bulls"], None),           # 兩边都有 red 這個字 ⇒ 不准猜
    ("RED",        ["RED Canids"], "RED Canids"),
    # ── MH 一局都沒有（pool 空）⇒ 一律 None，整批不補 ──
    ("FearX",      [], None),
]


def main():
    bad = 0
    for nm, pool, want in CASES:
        got = M._pb_team(nm, pool)
        if nm == "HanJin":                  # hanjin 是 hanjinbrion 的前綴 ⇒ 本來就該解出來
            want = "HANJIN BRION"
        if got != want:
            print("  X %r（%d 支隊）期望 %r 得到 %r" % (nm, len(pool), want, got))
            bad += 1

    # 正控制：把 pool 的 BNK FEARX 拿掉，FearX 就必須解不出來（證明它真的在查 pool，不是寫死）
    if M._pb_team("FearX", [t for t in DCUP if t != "BNK FEARX"]) is not None:
        print("  X 正控制失敗：pool 拿掉 BNK FEARX 之後 FearX 還是解出了東西")
        bad += 1

    print("案例 %d 個＋正控制 1 個" % len(CASES))
    print("結果：" + ("OK 守門正確" if not bad else "NG %d 項" % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
