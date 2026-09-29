# -*- coding: utf-8 -*-
"""wiki 逐局名單「本名 → 職業 ID」的守門測試（2026-09-29）。

這一刀最大的風險不是「解不到」，是**解了不該解的**：一般職業 ID 若剛好是重新導向
（選手改名），全域套用會把整個聯賽的舊名默默換掉。所以 _looks_realname 是這條線的
安全閥，正反例都要有。

跑：python scripts/fetch_wiki_mh_realname_test.py        （純離線，不打 wiki）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_wiki_mh as M   # noqa: E402

# 真的出現在 2026 亞運正賽第一天的名單（本名）——這些**必須**被判為本名
REAL = [
    "N AL", "A WAZZAN", "A A (Abdolaziz Almubarak)", "N A", "S W",
    "K K", "J ANG", "E SIA", "Y LIM", "A LIM",
    "D TRAN", "S TRAN", "H LE", "K NGUYEN", "N HOANG", "T DINH",
    "B A", "F A", "M A", "K A (Khalifa Aldhaheri)", "A A (Ahmed Alsuwaidi)",
]

# 一般職業 ID（含亞運熱身賽實際出現過的）——這些**絕對不可以**被動到
IDS = [
    "Faker", "Zeus", "Keria", "Canyon", "Gumayusi", "Zeka", "Perry", "Kiaya",
    "Dire", "Hizto", "Pun", "Eddie", "Taki", "Aojune", "Denathor", "ScaryJerry",
    "Zyko", "BeryL", "Chovy", "Ruler", "Duro", "Kiin", "Doran", "Oner", "Peyz",
    "1Jiang", "Bin", "Wei", "knight", "Elk", "ON", "JackeyLove", "369",
]


def main():
    bad = 0
    for n in REAL:
        if not M._looks_realname(n):
            print("  X 本名沒被認出來：%r" % n)
            bad += 1
    for n in IDS:
        if M._looks_realname(n):
            print("  X 職業 ID 被誤判成本名（會被改掉！）：%r" % n)
            bad += 1

    # 邊界：全大寫的單字 ID（ON／369）只有一段 → 不該中；兩段全大寫才算本名
    edge = {
        "ON": False, "369": False, "T1": False, "GEN": False,
        "V CHEN": True, "GB KIM": True, "W CHOI": True,
        "Mid King": False,          # 有小寫 → 不是本名格式
        "A": False,                 # 只有一段
    }
    for n, want in edge.items():
        got = M._looks_realname(n)
        if got != want:
            print("  X 邊界判斷錯：%r 期望 %s 得到 %s" % (n, want, got))
            bad += 1

    print("本名 %d 個、職業 ID %d 個、邊界 %d 個" % (len(REAL), len(IDS), len(edge)))
    print("結果：" + ("OK 守門正確" if not bad else "NG %d 項" % bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
