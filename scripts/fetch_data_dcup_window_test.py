# -*- coding: utf-8 -*-
"""league_ok 的國際賽年份窗守門測試（2026-10-04）。

守的是一個**使用者的決定**，不是一條程式規則：德瑪西亞杯「只要 2026 這屆」。
OE 其實 2016~2025 都有（7932 列、約 1300 局），10-04 為了讓今年這屆過 league_ok 把 DCUP
加進 INTL_LEAGUES；沒有年份窗的話，下一次 `fetch_data.py --force` 會把那九屆默默灌進
歷史年份的資料檔，而且不會有任何訊息 —— 這支測試就是為了讓那件事在 CI／手跑時當場紅。

反向也要守：年份窗不可以誤傷其他國際賽（MSI／世界賽／亞運…都是不分年份一律收）。

跑：python scripts/fetch_data_dcup_window_test.py        （純離線，不下載 OE）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_data as F   # noqa: E402

CASES = [
    # 德瑪西亞杯：2026 起才收（使用者 2026-10-04 定案）
    ("DCup", 2026, True,  "今年這屆（10-03 開打）"),
    ("DCup", 2027, True,  "之後的屆數照收"),
    ("DCup", 2025, False, "2025 那屆：OE 有 936 列，使用者選不要"),
    ("DCup", 2018, False, "2018 那屆：OE 有 1164 列，使用者選不要"),
    ("DCup", 2016, False, "最早那屆"),
    # 其他國際賽／盃賽：不分年份一律收，不可被年份窗誤傷
    ("WLDs", 2013, True,  "世界賽"),
    ("MSI",  2015, True,  "MSI"),
    ("亞運", 2026, True,  "亞運（國家隊）"),
    ("KeSPA", 2019, True, "KeSPA 盃"),
    ("IWCT", 2014, True,  "國際外卡賽"),
    # 一級聯賽：走 TIER1_YEARS，不受這次改動影響
    ("LCK", 2013, True,  "LCK 一直都是一級"),
    ("LCS", 2025, False, "2025 併入 LTA N ⇒ 那年不收"),
    ("LCS", 2026, True,  "2026 回歸"),
    ("PCS", 2025, False, "2025 併入 LCP"),
    ("某個不存在的聯賽", 2026, False, "不在任何表裡"),
]


def main():
    bad = 0
    for lg, yr, want, why in CASES:
        got = F.league_ok(lg, yr)
        if got != want:
            print("  X %-8s %d 期望 %-5s 得到 %-5s （%s）" % (lg, yr, want, got, why))
            bad += 1

    # 正控制：把年份窗拿掉，DCup 2018 就必須變成 True
    #（證明這支測試真的在量年份窗，不是在量「DCup 本來就被擋」）
    _save = F.INTL_YEARS
    try:
        F.INTL_YEARS = {}
        if F.league_ok("DCup", 2018) is not True:
            print("  X 正控制失敗：年份窗拿掉之後 DCup 2018 應該要通過")
            bad += 1
    finally:
        F.INTL_YEARS = _save

    print("案例 %d 個＋正控制 1 個；目前的窗：%s" % (len(CASES), F.INTL_YEARS))
    print("結果：" + ("OK 守門正確" if not bad else "NG %d 項" % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
