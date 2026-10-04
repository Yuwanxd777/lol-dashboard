# -*- coding: utf-8 -*-
"""process() 的兩道聯賽關卡守門測試：league_ok（年份）＋intl_from_ok（盃賽起始日）。

守的是一個**使用者的決定**，不是一條程式規則：德瑪西亞杯只要 2026-10-03 這屆
（2026-10-04 兩段定案：先「只要今年這屆」，再「1 月那三局刪了」）。

為什麼需要這支測試：
  ①OE 其實 2016~2025 都有德瑪西亞杯（7932 列、約 1300 局），以前一直被 league_ok 擋著。
    10-04 為了讓今年這屆過關把 DCUP 加進 INTL_LEAGUES（那張表不分年份一律收）⇒ 沒有這道
    起始日關卡的話，下一次 `fetch_data.py --force` 會把那九屆默默灌進歷史年份的資料檔，
    而且不會有任何訊息。
  ②第一版寫成「年份窗 (2026, 2099)」，當天就被打破：2025 那屆的尾巴（01-01~01-03 共 3 局）
    年份就是 2026。所以關卡必須看**日期**，不是年份——這支測試裡那三局是獨立案例。

跑：python scripts/fetch_data_dcup_window_test.py        （純離線，不下載 OE）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_data as F   # noqa: E402


def accept(lg, date):
    """複製 process() 真正的兩道關卡順序（year＝那個資料檔的年份，就是日期的年）。"""
    return F.league_ok(lg, int(str(date)[:4])) and F.intl_from_ok(lg, date)


CASES = [
    # ── 德瑪西亞杯：只收 2026-10-03 起 ──
    ("DCup", "2026-10-03", True,  "今年這屆開打日"),
    ("DCup", "2026-10-17", True,  "這屆最後一天（events_extra 的 to）"),
    ("DCup", "2027-01-05", True,  "往後的屆數照收"),
    ("DCup", "2026-10-02", False, "開打前一天"),
    ("DCup", "2026-01-01", False, "★2025 那屆的尾巴——年份窗擋不掉的那三局"),
    ("DCup", "2026-01-03", False, "★同上"),
    ("DCup", "2025-12-29", False, "2025 那屆本體（OE 2025 檔 936 列）"),
    ("DCup", "2018-12-23", False, "2018 那屆（OE 1164 列）"),
    ("DCup", "2016-06-29", False, "最早那屆"),
    # ── 其他國際賽／盃賽：不分年份一律收，不可被起始日關卡誤傷 ──
    ("WLDs",  "2013-10-04", True, "世界賽"),
    ("MSI",   "2015-05-10", True, "MSI"),
    ("亞運",  "2026-10-01", True, "亞運（國家隊）"),
    ("KeSPA", "2019-12-25", True, "KeSPA 盃"),
    ("IWCT",  "2014-05-10", True, "國際外卡賽"),
    # ── 一級聯賽：走 TIER1_YEARS，不受這次改動影響 ──
    ("LCK", "2013-03-01", True,  "LCK 一直都是一級"),
    ("LCS", "2025-03-01", False, "2025 併入 LTA N ⇒ 那年不收"),
    ("LCS", "2026-03-01", True,  "2026 回歸"),
    ("PCS", "2025-03-01", False, "2025 併入 LCP"),
    ("某個不存在的聯賽", "2026-03-01", False, "不在任何表裡"),
]


def main():
    bad = 0
    for lg, date, want, why in CASES:
        got = accept(lg, date)
        if got != want:
            print("  X %-8s %s 期望 %-5s 得到 %-5s （%s）" % (lg, date, want, got, why))
            bad += 1

    # 正控制一：把起始日表清空，DCup 的 1 月那局與 2018 那局都必須變成通過
    #（證明測的是這道關卡，不是「DCup 本來就被擋」）
    _save = F.INTL_FROM
    try:
        F.INTL_FROM = {}
        for d in ("2026-01-01", "2018-12-23"):
            if accept("DCup", d) is not True:
                print("  X 正控制一失敗：起始日表清空後 DCup %s 應該要通過" % d)
                bad += 1
    finally:
        F.INTL_FROM = _save

    # 正控制二：起始日表有列、但日期欄是空的 ⇒ 不可以當成通過
    #（process() 真的遇到空日期時寧可丟掉，不要讓舊屆數從空值溜進來）
    if F.intl_from_ok("DCup", "") is not False:
        print("  X 正控制二失敗：日期空白時 DCup 不該通過")
        bad += 1

    print("案例 %d 個＋正控制 3 個；目前的起始日：%s" % (len(CASES), F.INTL_FROM))
    print("結果：" + ("OK 守門正確" if not bad else "NG %d 項" % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
