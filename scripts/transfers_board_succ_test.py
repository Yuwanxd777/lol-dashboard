# -*- coding: utf-8 -*-
"""transfers_board.succ_rekey 的回歸測試（純函式，不讀寫任何檔、不連網）。

背景（2026-11-25 23:47 每小時複查留的「⚠ 待人工」）：接手席位的新隊（OpTic Gaming 接 Dignitas）在 build() 裡是用
舊隊名那一列去算、最後才改掛新隊名；傳聞標的新隊是「OpTic Gaming」⇒ rumor.get((tkey("Dignitas"), rr)) 永遠對不上，
第一則「去 OPT」的傳聞（Zven）在陣容表上整個消失（進不了那一格 ⇒ 也進不了自由人區）。

用法：python scripts/transfers_board_succ_test.py   （全過離開碼 0）
"""
import copy
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import transfers_board as TB   # noqa: E402

SUCC = {"OpTic Gaming": "Dignitas"}
fails = []


def check(name, cond, detail=""):
    print(("✓ " if cond else "✗ ") + name + (("｜" + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def item(n, lane, to, fr, d, st="rumor"):
    """fetch_transfers 把 PTT 條目的 mv 轉成的 Sheep 同格式（synth）"""
    return {"d": d, "st": st, "kind": "join", "src": "Sheep Esports", "zh": "%s 將加入 %s。" % (n, to), "en": "",
            "who": [n, n, lane], "tags": ([["", fr, "out"]] if fr else []) + [["", to, "in"]]}


# 真實條目的形狀：transfers_ptt_src.json M.1795620363.A.BF8 的 mv＝[Zven, BOT, OpTic Gaming, Cloud9]
ZVEN = item("Zven", "BOT", "OpTic Gaming", "Cloud9", "2026-11-25 23:26")
OLD_DIG = item("Tomo", "BOT", "Dignitas", "", "2026-11-20 10:00")          # 標在舊隊名底下的另一則（合併用）
OTHER = item("Lucid", "JNG", "KT Rolster", "Dplus KIA", "2026-11-19 15:00")   # 不相干的隊

# ① 修之前的病徵真的存在（正控制）：parse_sheep 把它放在新隊名的鍵，舊隊名的鍵查不到
r0 = TB.parse_sheep([copy.deepcopy(ZVEN), copy.deepcopy(OTHER)])
check("①前提：傳聞掛在新隊名的鍵", [v["n"] for v in r0.get(("optic gaming", "BOT"), [])] == ["Zven"], str(sorted(r0)))
check("①前提：用舊隊名查不到（＝原本的病徵）", r0.get((TB.tkey("Dignitas"), "BOT"), []) == [])

# ② 搬鍵之後：build() 用舊隊名查得到，條目自己的 tm 仍是新隊名，新隊名的鍵不留
r1 = TB.succ_rekey(TB.parse_sheep([copy.deepcopy(ZVEN), copy.deepcopy(OTHER)]), SUCC)
L = r1.get((TB.tkey("Dignitas"), "BOT"), [])
check("②用舊隊名查得到 Zven", [v["n"] for v in L] == ["Zven"], str(sorted(r1)))
check("②條目的 tm 仍是 OpTic Gaming（顯示用，不可改成 Dignitas）", bool(L) and L[0]["tm"] == "OpTic Gaming")
check("②來自（from）仍是 Cloud9", bool(L) and L[0].get("from") == "Cloud9")
check("②新隊名的鍵不留", not any(k[0] == "optic gaming" for k in r1))
check("②不相干的隊原封不動", [v["n"] for v in r1.get(("kt rolster", "JNG"), [])] == ["Lucid"])

# ③ 對照：沒有 succ（None／空）就什麼都不動
for nm, s in (("None", None), ("空字典", {}), ("不相干的對應", {"Team X": "Team Y"})):
    r2 = TB.succ_rekey(TB.parse_sheep([copy.deepcopy(ZVEN), copy.deepcopy(OTHER)]), s)
    check("③succ＝%s 時不動" % nm, sorted(r2) == sorted(r0) and [v["n"] for v in r2[("optic gaming", "BOT")]] == ["Zven"])

# ④ 舊隊名底下本來就有傳聞 ⇒ 合併、新的在前，不互蓋
r3 = TB.succ_rekey(TB.parse_sheep([copy.deepcopy(OLD_DIG), copy.deepcopy(ZVEN)]), SUCC)
check("④兩則合併、新的在前", [v["n"] for v in r3.get(("dignitas", "BOT"), [])] == ["Zven", "Tomo"], str(r3.get(("dignitas", "BOT"))))

# ⑤ 不同路線各搬各的
r4 = TB.succ_rekey(TB.parse_sheep([copy.deepcopy(ZVEN), item("Abc", "TOP", "OpTic Gaming", "", "2026-11-24 09:00")]), SUCC)
check("⑤TOP／BOT 各自搬到舊隊名的鍵", sorted(k for k in r4 if k[0] == "dignitas") == [("dignitas", "BOT"), ("dignitas", "TOP")], str(sorted(r4)))

# ⑥ 新舊同名（對應寫成自己接自己）不可把條目弄丟
r5 = TB.succ_rekey(TB.parse_sheep([copy.deepcopy(ZVEN)]), {"OpTic Gaming": "OpTic Gaming"})
check("⑥新舊同鍵時不動、不丟", [v["n"] for v in r5.get(("optic gaming", "BOT"), [])] == ["Zven"])

# ⑦ 接線：build() 真的有呼叫 succ_rekey，而且「去接手隊」不算離隊傳聞那一行還在（有人順手改掉就會紅）
src = io.open(os.path.join(HERE, "transfers_board.py"), encoding="utf-8").read()
check("⑦build() 有把 parse_sheep 的結果交給 succ_rekey", "rumor = succ_rekey(parse_sheep(sheep), succ)" in src)
check("⑦離隊傳聞的比對有把接手隊視為同一列", 'succ_old.get(tkey(ro["tm"]), tkey(ro["tm"])) != tkey(tm)' in src and "succ_old = {tkey(n_): tkey(o_)" in src)

print("")
print("結果：%s（%d 項沒過）" % ("全過" if not fails else "有沒過的", len(fails)))
sys.exit(1 if fails else 0)
