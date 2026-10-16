# -*- coding: utf-8 -*-
"""fetch_data.label_ewc 守門：EWC 正賽／各區資格賽的切分（2026-10-16）。

舊版只看「兩隊同區＝資格賽、跨區＝正賽」，實查 2026 錯了 12 局：
  ①正賽淘汰賽同區碰頭（07-17 T1 vs HLE、07-18 Gen.G vs DK、07-19 Gen.G vs T1）→ 被標成 EWCQ韓國
  ②OE 在正賽把 TSW 寫成「Team Secret」（國內聯賽叫 Team Secret Whales ⇒ 查不到賽區）
    → 只剩對手的賽區 ⇒ 對 Sentinels 那局標成 EWCQ北美、對 KC 三局標成 EWCQ歐洲
修法＝正賽開打日（最早一局兩隊賽區都認得而且不同）起一律是正賽。

跑：python scripts/fetch_data_ewc_split_test.py   （純離線）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_data as F   # noqa: E402

L, G, T, D = 0, 1, 2, 3


def rows():
    R = []
    # 國內聯賽出賽紀錄（決定隊伍賽區）
    for t, lg in (("T1", "LCK"), ("Gen.G", "LCK"), ("Hanwha Life Esports", "LCK"), ("Dplus Kia", "LCK"),
                  ("Sentinels", "LCS"), ("Karmine Corp", "LEC"), ("Team Secret Whales", "LCP"), ("GAM Esports", "LCP")):
        R.append([lg, "dom-" + t, t, "2026-03-01"])

    def game(gid, d, a, b):
        R.append(["EWC", gid, a, d]); R.append(["EWC", gid, b, d])
    game("q-kr", "2026-05-04", "T1", "Gen.G")                       # 韓國資格賽
    game("q-pac", "2026-05-20", "Team Secret", "GAM Esports")       # 太平洋資格賽（TSW 以 Team Secret 出賽）
    game("m-open", "2026-07-15", "Gen.G", "Karmine Corp")           # 正賽第一局（跨區）
    game("m-ts", "2026-07-15", "Sentinels", "Team Secret")          # ★正賽：Team Secret 查不到賽區
    game("m-kr", "2026-07-19", "Gen.G", "T1")                       # ★正賽淘汰賽同區碰頭
    return R


def label(R):
    F.label_ewc(R, L, G, T, D)
    return {r[G]: r[L] for r in R if r[G][:2] in ("q-", "m-")}


def old_label(R):
    """改動前的規則（不看日期），當反例：要證明這支測試抓得到舊錯"""
    dom = {r[T]: r[L] for r in R if r[L] in F.EWC_MAPQ}
    by = {}
    for r in R:
        if r[L] == "EWC":
            by.setdefault(r[G], set()).add(dom.get(r[T]))
    out = {}
    for g, regs in by.items():
        regs = {x for x in regs if x}
        out[g] = F.EWC_MAPQ[next(iter(regs))] if len(regs) == 1 else "EWC"
    return out


WANT = {"q-kr": "EWCQ韓國", "q-pac": "EWCQ太平洋", "m-open": "EWC", "m-ts": "EWC", "m-kr": "EWC"}


def main():
    bad = 0
    got = label(rows())
    for g, w in WANT.items():
        ok = got.get(g) == w
        bad += not ok
        print("  %s %-7s 期望 %-8s 得到 %s" % ("✓" if ok else "X", g, w, got.get(g)))
    old = old_label(rows())
    caught = old["m-ts"] != "EWC" and old["m-kr"] != "EWC"
    bad += not caught
    print("  %s 反例：舊規則把 m-ts→%s、m-kr→%s（要是資格賽才代表測試抓得到舊錯）"
          % ("✓" if caught else "X", old["m-ts"], old["m-kr"]))
    # 沒有任何跨區局（例如只抓到資格賽）＝開打日未知 ⇒ 同區局維持資格賽
    R = [r for r in rows() if not r[G].startswith("m-")]
    g2 = label(R)
    ok = g2 == {"q-kr": "EWCQ韓國", "q-pac": "EWCQ太平洋"}
    bad += not ok
    print("  %s 只有資格賽時照舊：%s" % ("✓" if ok else "X", g2))
    print("全部通過" if not bad else "%d 條失敗" % bad)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
