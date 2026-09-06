# -*- coding: utf-8 -*-
"""fetch_soloq_year 的「--missing 補全年 0 場 3 天內不重抓」離線測試（不打網路、不開瀏覽器）。
用法：python scripts\\fetch_soloq_year_empty_test.py
"""
import os, sys, json, datetime, tempfile, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location("fsy", os.path.join(HERE, "fetch_soloq_year.py"))
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)   # 不再包 sys.stdout（模組若包過，再包會把同一個 buffer 關掉）

OK = FAIL = 0
def check(name, cond, info=""):
    global OK, FAIL
    if cond: OK += 1; print(f"  ✓ {name}")
    else: FAIL += 1; print(f"  ✗ {name}  {info}")

D = datetime.date(2026, 9, 6)
def at(days_ago): return (D - datetime.timedelta(days=days_ago)).isoformat()

print("[1] split_recent_empty：誰略過、誰照抓")
empty = {"A|a": {"at": at(0), "tries": 1}, "B|b": {"at": at(2), "tries": 2}, "C|c": {"at": at(3), "tries": 1},
         "D|d": {"at": "garbage", "tries": 1}, "E|e": {"tries": 1}, "F|f": {"at": at(-1), "tries": 1}}
keys = ["A|a", "B|b", "C|c", "D|d", "E|e", "F|f", "G|g"]
go, skip = M.split_recent_empty(keys, empty, today=D)
check("今天 0 場 → 略過", ("A|a", at(0)) in skip, skip)
check("2 天前 0 場 → 略過（< 3 天）", ("B|b", at(2)) in skip, skip)
check("3 天前 0 場 → 照抓（到期）", "C|c" in go, go)
check("日期壞掉 → 照抓", "D|d" in go, go)
check("沒有 at → 照抓", "E|e" in go, go)
check("日期在未來（時鐘倒退）→ 照抓", "F|f" in go, go)
check("沒紀錄 → 照抓", "G|g" in go, go)
check("順序保留、不重複", go == ["C|c", "D|d", "E|e", "F|f", "G|g"] and [k for k, _ in skip] == ["A|a", "B|b"], (go, skip))
check("負控制：空表 → 全部照抓", M.split_recent_empty(keys, {}, today=D) == (keys, []))
check("days=0 → 全部照抓", M.split_recent_empty(keys, empty, today=D, days=0)[0] == keys)

print("[2] save_year_empty：0 場記今天並累加 tries，有場次就移除，檔案可回讀")
with tempfile.TemporaryDirectory() as td:
    p = os.path.join(td, "sub", "soloq_year_empty.json")
    m = M.save_year_empty({"A|a": 0, "B|b": 5}, path=p, today=D)
    check("0 場 → 記今天 tries=1", m.get("A|a") == {"at": at(0), "tries": 1}, m)
    check("有場次 → 不記", "B|b" not in m, m)
    check("子目錄自動建立、檔案寫出", os.path.exists(p))
    check("回讀 == 寫出", M.load_year_empty(p) == m)
    m2 = M.save_year_empty({"A|a": 0, "C|c": 0}, path=p, today=D + datetime.timedelta(days=3))
    check("再 0 場 → tries 累加、at 更新", m2.get("A|a") == {"at": at(-3), "tries": 2}, m2)
    check("新的 0 場加入", m2.get("C|c") == {"at": at(-3), "tries": 1}, m2)
    m3 = M.save_year_empty({"A|a": 12}, path=p, today=D + datetime.timedelta(days=4))
    check("終於抓到 → 從表移除、其他保留", "A|a" not in m3 and "C|c" in m3, m3)
    check("空結果不動表", M.save_year_empty({}, path=p, today=D) == m3)
    # 過期後的下一輪：3 天前記的 → 這輪要抓
    go, skip = M.split_recent_empty(["C|c"], M.load_year_empty(p), today=D + datetime.timedelta(days=6))
    check("記錄 3 天後到期 → 重抓", go == ["C|c"] and skip == [], (go, skip))
check("壞掉的檔 → 當空表", M.load_year_empty(os.path.join(ROOT, "scripts", "fetch_soloq_year.py")) == {})
check("不存在的檔 → 空表", M.load_year_empty(os.path.join(ROOT, "csv_cache", "__nope__.json")) == {})

print("[3] 常數與旗標")
check("EMPTY_DAYS = 3", M.EMPTY_DAYS == 3, M.EMPTY_DAYS)
check("EMPTY_PATH 在 csv_cache", M.EMPTY_PATH.endswith(os.path.join("csv_cache", "soloq_year_empty.json")), M.EMPTY_PATH)
check("--retry-empty 沒給 → False", M.RETRY_EMPTY is False)
src = open(os.path.join(HERE, "fetch_soloq_year.py"), encoding="utf-8").read()
check("--missing 分支在 --max 之前套用 split_recent_empty", src.index("split_recent_empty(keys, load_year_empty())") < src.index("if MAXP: keys = keys[:MAXP]"))
check("save_year_empty 只在 --missing 且非暫存模式呼叫", "if MISSING and not STAGING and EMPTY_RES:" in src)
check("無可信帳號那條也記 0", src.count("EMPTY_RES[key] = 0") == 1)

print(f"\n結果：{OK}/{OK + FAIL}" + ("" if FAIL == 0 else f"（{FAIL} 失敗）"))
sys.exit(0 if FAIL == 0 else 1)
