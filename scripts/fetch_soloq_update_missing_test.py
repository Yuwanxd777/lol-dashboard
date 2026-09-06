# -*- coding: utf-8 -*-
"""fetch_soloq_update 的「另有 N 位無檔」對齊 fetch_soloq_year 的 3 天內不重抓（離線：不打網路、不開瀏覽器）。
用法：python scripts/fetch_soloq_update_missing_test.py
"""
import os, sys, datetime, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
U = load("fsu", "fetch_soloq_update.py")
Y = load("fsy", "fetch_soloq_year.py")

OK = FAIL = 0
def check(name, cond, info=""):
    global OK, FAIL
    if cond: OK += 1; print(f"  ✓ {name}")
    else: FAIL += 1; print(f"  ✗ {name}  {info}")

D = datetime.date(2026, 9, 6)
def at(days_ago): return (D - datetime.timedelta(days=days_ago)).isoformat()
empty = {"A|a": {"at": at(0), "tries": 1}, "B|b": {"at": at(2), "tries": 2}, "C|c": {"at": at(3), "tries": 1},
         "D|d": {"at": "garbage", "tries": 1}, "E|e": {"tries": 1}, "F|f": {"at": at(-1), "tries": 1}}
keys = ["A|a", "B|b", "C|c", "D|d", "E|e", "F|f", "G|g"]

print("[1] split_missing_recent_empty：誰略過、誰照抓")
go, skip = U.split_missing_recent_empty(keys, empty, today=D)
check("今天 0 場 → 略過", ("A|a", at(0)) in skip, skip)
check("2 天前 0 場 → 略過（< 3 天）", ("B|b", at(2)) in skip, skip)
check("3 天前 0 場 → 照抓（到期）", "C|c" in go, go)
check("日期壞掉／沒有 at／未來／沒紀錄 → 照抓", all(k in go for k in ["D|d", "E|e", "F|f", "G|g"]), go)
check("順序保留、不重複", go == ["C|c", "D|d", "E|e", "F|f", "G|g"] and [k for k, _ in skip] == ["A|a", "B|b"], (go, skip))
check("負控制：空表 → 全部照抓、略過 0", U.split_missing_recent_empty(keys, {}, today=D) == (keys, []))
check("負控制：days=0 → 全部照抓", U.split_missing_recent_empty(keys, empty, today=D, days=0)[0] == keys)

print("[2] 與 fetch_soloq_year.split_recent_empty 逐案一致（兩邊常數也一致）")
check("EMPTY_DAYS 兩邊相同", U.EMPTY_DAYS == Y.EMPTY_DAYS, (U.EMPTY_DAYS, Y.EMPTY_DAYS))
check("EMPTY_PATH 兩邊指同一檔", os.path.normcase(U.EMPTY_PATH) == os.path.normcase(Y.EMPTY_PATH), (U.EMPTY_PATH, Y.EMPTY_PATH))
same = True
for dd in range(-2, 6):
    for days in (0, 1, 3, 7):
        e2 = {"K|k": {"at": at(dd)}}
        if U.split_missing_recent_empty(["K|k"], e2, today=D, days=days) != Y.split_recent_empty(["K|k"], e2, today=D, days=days):
            same = False; print("   不一致：", dd, days)
check("-2～5 天 × days 0/1/3/7 共 32 案結果全相同", same)
check("load_year_empty：檔不存在 → {}", U.load_year_empty(os.path.join(HERE, "no_such_file.json")) == {})

print("[3] 原始碼位置：main() 真的走 split_missing_recent_empty、略過的另外印、沒人要抓就不起子程序")
src = open(os.path.join(HERE, "fetch_soloq_update.py"), encoding="utf-8").read()
check("missing 由 split_missing_recent_empty 產生", "missing, missing_skip = split_missing_recent_empty(" in src)
check("印出「⏭ N 位上次補全年 0 場」", "位上次補全年 0 場、{EMPTY_DAYS} 天內不重抓" in src)
check("子程序仍在 if missing: 之下（略過的人不會觸發）", "    if missing:  # 新選手自動補全年" in src)
import re
check("沒有多餘的 import fetch_soloq_year（程式碼行，註解不算）",
      not re.search(r"^\s*(import\s+fetch_soloq_year|from\s+fetch_soloq_year\s+import)", src, re.M))

print(f"\n結果：✓ {OK}　✗ {FAIL}")
sys.exit(1 if FAIL else 0)
