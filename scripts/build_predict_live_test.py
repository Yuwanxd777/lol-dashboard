# -*- coding: utf-8 -*-
"""build_predict_live.build 守門（純函式，不連網）：預測分頁本屆補兵／MVP／系列結果（使用者 2026-10-17）。
驗：①逐局逐人（同一局兩人都過 450 要都算，使用者 2026-10-26）、由高到低 ②MVP 去本名括號、N/A 不算、路線從 ScoreboardPlayers 對名字
③系列勝負方 ④反例：MVP 名字對不到任何出場紀錄 ⇒ 路線空白（不亂猜）。
跑：python build_predict_live_test.py
"""
import io, os, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_predict_live as B  # noqa: E402

PASS = FAIL = 0


def ok(name, got, want=True):
    global PASS, FAIL
    if got == want:
        PASS += 1; print("  ✓ " + name)
    else:
        FAIL += 1; print("  ✗ %s：得到 %r，應為 %r" % (name, got, want))


PI = "2026 Season World Championship/Play-In"
SP = [{"ov": PI, "gid": "g1", "nm": "Caliste", "tm": "Karmine Corp", "ch": "Xayah", "cs": "436", "rl": "Bot", "dt": "2026-10-15 21:14:00"},
      {"ov": PI, "gid": "g1", "nm": "Canna", "tm": "Karmine Corp", "ch": "Jax", "cs": "300", "rl": "Top", "dt": "2026-10-15 21:14:00"},
      {"ov": PI, "gid": "g2", "nm": "Ayu", "tm": "FURIA", "ch": "Ezreal", "cs": "455", "rl": "Bot", "dt": "2026-10-16 20:00:00"},
      {"ov": PI, "gid": "g2", "nm": "Tactical", "tm": "MVK Esports", "ch": "Lucian", "cs": "451", "rl": "Bot", "dt": "2026-10-16 20:00:00"},
      {"ov": PI, "gid": "g2", "nm": "Gury", "tm": "MVK Esports", "ch": "Vi", "cs": "200", "rl": "Jungle", "dt": "2026-10-16 20:00:00"}]
MS = [{"ov": PI, "t1": "Cloud9", "t2": "Karmine Corp", "mvp": "N/A", "dt": "2026-10-15 18:00:00", "tab": "Round 1", "w": "2"},
      {"ov": PI, "t1": "FURIA", "t2": "Cloud9", "mvp": "Ayu (Andrey Saraiva)", "dt": "2026-10-16 23:00:00", "tab": "Round 1", "w": "1"},
      {"ov": PI, "t1": "FURIA", "t2": "MVK Esports", "mvp": "Gury", "dt": "2026-10-15 23:00:00", "tab": "Round 1", "w": "2"},
      {"ov": PI, "t1": "A", "t2": "B", "mvp": "Nobody", "dt": "2026-10-17 10:00:00", "tab": "Round 2", "w": ""}]
d = B.build(SP, MS, 2026)

print("① 補兵")
ok("局數", d["games"], 2)
ok("逐人、由高到低", [(x["nm"], x["cs"]) for x in d["cs"][:3]], [("Ayu", 455), ("Tactical", 451), ("Caliste", 436)])
ok("同一局兩人過 450 都算", sum(1 for x in d["cs"] if x["cs"] >= 450), 2)
ok("450 以下照樣收（前端列前五）", len(d["cs"]), 5)
print("② MVP")
ok("N/A 不算、照時間排", [m["mvp"] for m in d["mvp"]], ["Gury", "Ayu", "Nobody"])
ok("路線對名字（去本名括號）", [m["rl"] for m in d["mvp"][:2]], ["JNG", "BOT"])
ok("隊伍", d["mvp"][1]["tm"], "FURIA")
ok("階段", d["mvp"][0]["stage"], "Play-In")
print("③ 系列")
ok("勝負方（沒打完的不收）", [(x["w"], x["l"]) for x in d["series"]],
   [("Karmine Corp", "Cloud9"), ("MVK Esports", "FURIA"), ("FURIA", "Cloud9")])
print("④ 反例")
ok("對不到出場紀錄 ⇒ 路線空白", d["mvp"][2]["rl"], "")

print("通過 %d／失敗 %d" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
