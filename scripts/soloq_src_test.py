# -*- coding: utf-8 -*-
"""soloq_src.py 的回歸測試（不連網、不碰真實檔案）。

用法：  python scripts\soloq_src_test.py
每條「不該報」的反例都配一條「同樣結構但該報」的正例，避免整組測試因為函式根本沒被觸發而全綠
（測試綠了 ≠ 功能對了）。
"""
import os, sys, io

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import soloq_src as S

FAIL = []


def ck(name, got, want):
    if got == want:
        print("  ✓ %s" % name)
    else:
        print("  ✗ %s\n     實際 %r\n     預期 %r" % (name, got, want))
        FAIL.append(name)


def g(rid, t=0):
    return {"rid": rid, "t": t}


def mk(acc, obs, full=False):
    s = S.new_src()
    s["full"] = full
    s["acc"] = [{"pu": pu, "rid": rid} for pu, rid in acc]
    s["obs"] = obs
    return {"src": s}


print("① mismatches：抓錯配、不誤報改名")
# 正例：pu1 登記 Alpha#TW，抓回來的全是別人 → 要報
d = mk([("pu1", "Alpha#TW")], {"pu1": {"Bravo#KR": 12}})
ck("錯配要報", [(x[0], x[1], x[2], x[3], x[4]) for x in S.mismatches(d)],
   [("pu1", "Alpha#TW", "Bravo#KR", 12, 12)])
# 反例（改名）：帳號檔已更新成新名，obs 裡舊名 50 場、新名 2 場 → 不可報
d = mk([("pu1", "New#TW")], {"pu1": {"Old#TW": 50, "New#TW": 2}})
ck("改名不誤報", S.mismatches(d), [])
# 反例：大小寫／空白不同的同一個名字 → 不可報
d = mk([("pu1", "Alpha #TW")], {"pu1": {"alpha#tw": 9}})
ck("大小寫空白視為同名", S.mismatches(d), [])
# 門檻：預設 min_games=3，2 場不報、3 場要報（同一組資料只差一場）
ck("2 場不到門檻", S.mismatches(mk([("pu1", "A#TW")], {"pu1": {"B#TW": 2}})), [])
ck("3 場到門檻要報", len(S.mismatches(mk([("pu1", "A#TW")], {"pu1": {"B#TW": 3}}))), 1)
# 沒登記 riotId 的 puuid 不報（沒有可比對的對象）
ck("puuid 不在 acc 裡不報", S.mismatches(mk([], {"pu9": {"B#TW": 9}})), [])
# 沒有 src／obs 的舊檔不報
ck("舊檔沒有 src 不報", S.mismatches({"role": "MID", "matches": []}), [])

print("② note：累計場次、跳過沒有 rid 的")
s = S.new_src()
S.note(s, "pu1", [g("A#TW"), g("A#TW"), g("B#TW"), {"t": 1}])
ck("obs 累計", s["obs"], {"pu1": {"A#TW": 2, "B#TW": 1}})
S.note(s, "pu1", [g("A#TW")])
ck("第二次呼叫是累加不是覆寫", s["obs"]["pu1"]["A#TW"], 3)
S.note(s, "", [g("A#TW")]); S.note(s, "pu2", [])
ck("沒 puuid／沒場次不建 key", sorted(s["obs"]), ["pu1"])

print("③ drop：跨 puuid 只扣總共 n 場（舊版每個 puuid 各扣一次會扣過頭）")
# 正主 pu1 有 Alpha#TW 20 場；錯配的 pu2 也抓回 Alpha#TW 5 場，clean 刪掉那 5 場
s = mk([("pu1", "Alpha#TW"), ("pu2", "Zulu#KR")],
       {"pu1": {"Alpha#TW": 20}, "pu2": {"Alpha#TW": 5, "Zulu#KR": 7}})["src"]
S.drop(s, {"Alpha#TW": 5})
ck("從持有最多的先扣", s["obs"], {"pu1": {"Alpha#TW": 15}, "pu2": {"Alpha#TW": 5, "Zulu#KR": 7}})
ck("扣完總量守恆", sum(sum(d.values()) for d in s["obs"].values()), 32 - 5)
# 對照組（這條才有鑑別力）：正主 pu1 改過名，obs 同時有舊名 Alpha#TW 4 場與新名 Neo#TW 6 場。
# 每個 puuid 各扣一次的寫法會把 pu1 的舊名扣光（剩 Neo#TW 6 場），下一輪對帳就誤報
# 「pu1 從沒出現過自己登記的 Alpha#TW ⇒ 錯配」——實測舊版正是這樣。
s = mk([("pu1", "Alpha#TW"), ("pu2", "Zulu#KR")],
       {"pu1": {"Alpha#TW": 4, "Neo#TW": 6}, "pu2": {"Alpha#TW": 5, "Zulu#KR": 7}})["src"]
S.drop(s, {"Alpha#TW": 5})
ck("正主的舊名沒被扣光", s["obs"]["pu1"], {"Alpha#TW": 4, "Neo#TW": 6})
ck("正主沒被誤判成錯配", S.mismatches({"src": s}), [])
# 扣到 0 移除 rid；該 puuid 空了移除 puuid
s = mk([("pu1", "A#TW")], {"pu1": {"A#TW": 3}, "pu2": {"B#TW": 4}})["src"]
S.drop(s, {"A#TW": 3})
ck("扣到 0 移除 rid 與空 puuid", s["obs"], {"pu2": {"B#TW": 4}})
# 跨 puuid 一次扣多場：8 場分佈在兩個 puuid，刪 6 場
s = mk([], {"pu1": {"X#TW": 5}, "pu2": {"X#TW": 3}})["src"]
S.drop(s, {"X#TW": 6})
ck("跨 puuid 依序扣滿 6 場", s["obs"], {"pu2": {"X#TW": 2}})
# 刪的比 obs 有的還多（obs 只涵蓋增量時很常見）→ 扣到 0 就停，不可變負數
s = mk([], {"pu1": {"X#TW": 2}})["src"]
S.drop(s, {"X#TW": 99})
ck("扣過頭不留負數", s["obs"], {})
s = mk([], {"pu1": {"X#TW": 2}})["src"]
S.drop(s, {}); S.drop(s, {"Y#TW": 3})
ck("空 rid_counts／不存在的 rid 不動", s["obs"], {"pu1": {"X#TW": 2}})

print("④ get_src：舊檔補建、版本不符重建、同版本沿用同一物件")
d = {"role": "MID", "matches": []}
s = S.get_src(d)
ck("舊檔補建 src", (s["v"], s["obs"], d["src"] is s), (S.SRC_V, {}, True))
d = {"src": {"v": 999, "obs": {"pu1": {"A#TW": 3}}}}
ck("版本不符整個重建", S.get_src(d)["obs"], {})
d = {"src": {"v": S.SRC_V, "acc": [], "obs": {"pu1": {"A#TW": 3}}}}
ck("同版本沿用既有 obs", S.get_src(d)["obs"], {"pu1": {"A#TW": 3}})

print("⑤ set_accounts：只收有 dpmPuuid 的")
s = S.new_src()
S.set_accounts(s, [{"dpmPuuid": "pu1", "riotId": "A#TW"}, {"riotId": "沒puuid#TW"}])
ck("acc 內容", s["acc"], [{"pu": "pu1", "rid": "A#TW"}])

print("⑥ same_name：fetch_soloq_update 用它濾掉「改名當輪」的假警報")
ck("大小寫空白不同視為同名", S.same_name("Alpha #TW", "alpha#tw"), True)
ck("真的不同名要 False", S.same_name("Alpha#TW", "Bravo#TW"), False)
ck("None／空字串一律 False", [S.same_name(None, "A#TW"), S.same_name("", "")], [False, False])

print("⑦ merge：併檔（build_soloq_index 去重時用）")
a = mk([("pu1", "A#TW")], {"pu1": {"A#TW": 10}}, full=True)["src"]; a["at"] = "2026-09-01 10:00"
b = mk([("pu1", "A#TW"), ("pu2", "B#TW")], {"pu1": {"A#TW": 4}, "pu2": {"B#TW": 6}}, full=True)["src"]
b["at"] = "2026-09-07 10:00"
m = S.merge([a, b])
ck("obs 相加", m["obs"], {"pu1": {"A#TW": 14}, "pu2": {"B#TW": 6}})
ck("acc 依 puuid 去重", [x["pu"] for x in m["acc"]], ["pu1", "pu2"])
ck("at 取最大", m["at"], "2026-09-07 10:00")
ck("兩檔都 full → full", m["full"], True)
b2 = dict(b); b2["full"] = False
ck("有一檔不 full → 不可宣稱 full", S.merge([a, b2])["full"], False)
ck("沒有 src 回 None", S.merge([None, {"role": "MID"}]), None)
ck("版本不符略過不硬合", S.merge([{"v": 999, "obs": {"pu1": {"A#TW": 3}}}]), None)

print("⑧ classify／summarize：對帳不符自動分類（2026-09-09 #82）")
_D = 86400000; _T0 = 1780000000000


def gt(rid, day):
    return {"rid": rid, "t": _T0 + day * _D}


def mkc(want, obs_rids, ms):
    return {"src": {"v": S.SRC_V, "acc": [{"pu": "pu1", "rid": want}], "obs": {"pu1": dict(obs_rids)}},
            "matches": ms}


_O, _N = "Alpha#TW", "Bravo#TW"
# 正例：不符名那些場全部晚於登記名最後一場 ⇒ 改名（dpm 名字索引落後，資料不用動）
ck("不符名全部較晚 → rename", S.classify(mkc(_O, {_N: 2}, [gt(_N, 20), gt(_N, 21), gt(_O, 10)]), "pu1", _O)[0], "rename")
# 反例（同素材只把一場往前挪）：時間交錯 ⇒ 疑錯配，維持人工判定線
ck("時間交錯 → suspect", S.classify(mkc(_O, {_N: 2}, [gt(_N, 5), gt(_N, 21), gt(_O, 10)]), "pu1", _O)[0], "suspect")
ck("同一時刻不算晚於（保守）→ suspect",
   S.classify(mkc(_O, {_N: 2}, [gt(_N, 10), gt(_N, 12), gt(_O, 10)]), "pu1", _O)[0], "suspect")
ck("登記名一場都沒有 → suspect", S.classify(mkc(_O, {_N: 2}, [gt(_N, 20), gt(_N, 21)]), "pu1", _O)[0], "suspect")
ck("沒有 matches 可比（全年重建只有 src）→ suspect",
   S.classify({"src": mkc(_O, {_N: 2}, [])["src"]}, "pu1", _O)[0], "suspect")
ck("大小寫空白不影響",
   S.classify(mkc("alpha #tw", {"BRAVO#TW": 2}, [gt("Bravo#TW", 20), gt("Alpha#TW", 10)]), "pu1", "alpha #tw")[0],
   "rename")
_rows = [("K%d" % i, _O, _N, 3, 3, "rename", "n") for i in range(12)]
_rows.insert(9, ("SUS", _O, _N, 5, 5, "suspect", "交錯"))
_out = S.summarize(_rows, limit=10)
ck("summarize 標題分別數兩類", "疑錯配 1 筆／改名 12 筆" in _out[0], True)
ck("疑錯配排最前面（不會被改名擠出 limit）", "[疑錯配] SUS" in _out[1], True)
ck("超過 limit 有交代", _out[-1].strip().startswith("…另外 3 筆"), True)
ck("summarize 不改動傳進去的 list", [r[0] for r in _rows][:2], ["K0", "K1"])

print("")
if FAIL:
    print("✗ %d 條失敗：%s" % (len(FAIL), FAIL))
    sys.exit(1)
print("✓ soloq_src 全部通過")
