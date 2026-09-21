# -*- coding: utf-8 -*-
"""
soloq_orphans（孤兒逐場檔不進聚合，2026-09-22 精進迴圈 #196）的沙盒測試。
  python scripts/soloq_orphans_test.py
隔離：soloq_matches／帳號檔／索引／每日戰況全在暫存目錄；被測模組沒有模組層路徑常數（帳號檔路徑由 OUTDIR 推），
跑完 assert 真實 repo 的帳號檔／索引／每日戰況 md5＋mtime 沒動。只有沙盒才有的證據＝key「ZZ|zz_probe_9942」。
每條判準都配正例會動的對照（同一份沙盒拿掉帳號檔 ⇒ 探針 key 回到每日戰況）。
突變用：環境變數 SOLOQ_ORPHANS_MOD／SOLOQ_BSI_MOD 指到改過的副本（autopilot/_m196_mutate.py）。
"""
import os, sys, io, json, time, shutil, tempfile, hashlib, importlib.util

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
REAL = [os.path.join(HERE, "soloq_accounts.json"), os.path.join(ROOT, "soloq_match_index.js"), os.path.join(ROOT, "soloq_recent.js")]
PROBE = "ZZ|zz_probe_9942"
N = [0, 0]


def check(name, ok, detail=""):
    N[0] += 1
    if not ok: N[1] += 1
    print(("  ✓ " if ok else "  ✗ ") + name + ((" ｜ " + str(detail)) if (detail != "" and not ok) else ""))


def load(name, env, default):
    p = os.environ.get(env) or default
    spec = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def sig(paths):
    out = {}
    for p in paths:
        try: out[p] = (hashlib.md5(open(p, "rb").read()).hexdigest(), os.path.getmtime(p))
        except OSError: out[p] = None
    return out


def put(od, n, key, ts, role="MIDDLE"):
    ms = [{"t": t, "c": "Ahri", "w": 1, "d": 1500, "lp": 20, "k": 1, "de": 1, "a": 1} for t in sorted(ts, reverse=True)]
    with open(os.path.join(od, "p%d.js" % n), "w", encoding="utf-8") as f:
        f.write("window.__sqLoad(%s,%s);\n" % (json.dumps(key, ensure_ascii=False), json.dumps({"role": role, "matches": ms}, ensure_ascii=False)))


def put_accs(sb, keys):
    os.makedirs(os.path.join(sb, "scripts"), exist_ok=True)
    rows = [{"team": k.split("|")[0], "player": k.split("|", 1)[1], "riotId": "x#%d" % i} for i, k in enumerate(keys)]
    json.dump(rows, open(os.path.join(sb, "scripts", "soloq_accounts.json"), "w", encoding="utf-8"), ensure_ascii=False)


def main():
    before = sig(REAL)
    SO = load("soloq_orphans", "SOLOQ_ORPHANS_MOD", os.path.join(HERE, "soloq_orphans.py"))
    sys.modules["soloq_orphans"] = SO          # build_soloq_index 在 _build() 裡 import 的就是這一份（突變副本也走這裡）
    BSI = load("build_soloq_index_ut", "SOLOQ_BSI_MOD", os.path.join(HERE, "build_soloq_index.py"))
    tmp = tempfile.mkdtemp(prefix="sqorph_")
    try:
        sb = os.path.join(tmp, "repo"); od = os.path.join(sb, "soloq_matches"); os.makedirs(od)
        now = int(time.time() * 1000); H = 3600 * 1000
        T = lambda *hs: [now - h * H for h in hs]
        put(od, 0, "AA|Alpha", T(1, 2, 3, 4, 5))
        put(od, 1, PROBE, T(6, 7, 8))                                   # 名字也不在 ⇒ absent
        put(od, 2, "OLD|Bravo", T(10, 11))                              # 換隊碼舊檔，整檔被包含 ⇒ dup
        put(od, 3, "NEW|Bravo", T(9, 10, 11, 12))
        put(od, 4, "AA|Charlie (VN)", T(20, 21))                        # 去括號同名仍在、零重疊 ⇒ 留著
        put(od, 5, "AA|Charlie", T(22, 23))
        put(od, 6, "AA|DELTA", T(30, 31))                               # 只差大小寫、整檔被包含 ⇒ dup
        put(od, 7, "AA|delta", T(30, 31, 32))
        put(od, 8, "AA|Echo", T(40))                                    # 同名在別隊、但那邊沒有逐場檔 ⇒ 留著
        put(od, 9, "AA|Foxtrot", [])                                    # 空檔、同名仍在 ⇒ 留著（空集合不能算「被包含」）
        put(od, 10, "BB|Foxtrot", T(50))
        put(od, 11, "OLD|Golf", T(60, 61, 62))                          # 只有部分重疊 ⇒ 留著
        put(od, 12, "NEW|Golf", T(60, 61))
        open(os.path.join(od, "p13.js"), "w", encoding="utf-8").write("這不是逐場檔")
        open(os.path.join(od, "soloq_match_index.js"), "w", encoding="utf-8").write("window.SOLOQ_MATCH_IDX={};\n")
        open(os.path.join(od, "pX.js"), "w", encoding="utf-8").write('window.__sqLoad("ZZ|junk",{"matches":[]});\n')
        ACC = ["AA|Alpha", "NEW|Bravo", "AA|Charlie", "AA|delta", "BB|Echo", "BB|Foxtrot", "NEW|Golf"]
        put_accs(sb, ACC)

        print("① 路徑晚綁／模組層沒有指著真實 repo 的字串")
        check("帳號檔路徑由 OUTDIR 推到沙盒", os.path.normcase(SO.accounts_path_for(od)) == os.path.normcase(os.path.join(sb, "scripts", "soloq_accounts.json")), SO.accounts_path_for(od))
        realn = os.path.normcase(ROOT)
        leaks = [k for k, v in vars(SO).items() if isinstance(v, str) and k not in ("__file__", "__cached__", "__doc__") and os.path.normcase(v).startswith(realn)]
        check("soloq_orphans 模組層沒有路徑常數指著真實 repo", not leaks, leaks)
        if leaks:
            print("漏接 ⇒ 當場中止（寫檔之前）"); return 1

        print("② 判準")
        logs = []
        sk = SO.skip_keys(od, log=logs.append)
        check("探針 key（名字也不在帳號檔）⇒ absent", sk.get(PROBE) == "absent", sk)
        check("換隊碼舊檔整檔被包含 ⇒ dup", sk.get("OLD|Bravo") == "dup", sk)
        check("只差大小寫、整檔被包含 ⇒ dup", sk.get("AA|DELTA") == "dup", sk)
        check("去掉消歧義括號後同名仍在、零重疊 ⇒ 留著", "AA|Charlie (VN)" not in sk, sk)
        check("同名在別隊但那邊沒有逐場檔 ⇒ 留著", "AA|Echo" not in sk, sk)
        check("空檔不算「被包含」⇒ 留著", "AA|Foxtrot" not in sk, sk)
        check("只有部分重疊 ⇒ 留著", "OLD|Golf" not in sk, sk)
        check("帳號檔裡的人一個都不跳過", not (set(sk) & set(ACC)), sk)
        check("雜檔（pX.js／索引殘檔／壞檔）不進結果", set(sk) == {PROBE, "OLD|Bravo", "AA|DELTA"}, sorted(sk))
        check("日誌一行講清楚三類數量", any("名字不在帳號檔 1 位" in l and "整檔重複（換隊碼／大小寫的舊檔）2 位" in l and "留著 4 位" in l for l in logs), logs)

        print("③ 保險：帳號檔讀不到／壞掉／空的 ⇒ 不過濾")
        accp = os.path.join(sb, "scripts", "soloq_accounts.json"); good = open(accp, encoding="utf-8").read()
        os.remove(accp); logs = []
        check("帳號檔不存在 ⇒ {}", SO.skip_keys(od, log=logs.append) == {} and any("讀不到" in l for l in logs), logs)
        open(accp, "w", encoding="utf-8").write("{壞掉"); logs = []
        check("帳號檔不是 JSON ⇒ {}", SO.skip_keys(od, log=logs.append) == {} and any("讀不到" in l for l in logs), logs)
        open(accp, "w", encoding="utf-8").write("[]"); logs = []
        check("帳號檔是空陣列 ⇒ {}（不是全部當孤兒）", SO.skip_keys(od, log=logs.append) == {} and any("空的" in l for l in logs), logs)
        open(accp, "w", encoding="utf-8").write(good)
        check("（對照）帳號檔放回去 ⇒ 又濾得到探針", SO.skip_keys(od, log=lambda *_: None).get(PROBE) == "absent")

        print("④ 保險：absent 多到不像話 ⇒ 當成帳號檔壞了")
        sb2 = os.path.join(tmp, "repo2"); od2 = os.path.join(sb2, "soloq_matches"); os.makedirs(od2)
        for i in range(25):
            put(od2, i, "T%d|P%d" % (i, i), T(i + 1))
        put_accs(sb2, ["T%d|P%d" % (i, i) for i in range(20)])          # 5/25＝20% > 15%
        logs = []
        check("25 檔裡 5 個 absent（20%）⇒ 不過濾＋印 ⚠", SO.skip_keys(od2, log=logs.append) == {} and any(l.startswith("⚠") for l in logs), logs)
        put_accs(sb2, ["T%d|P%d" % (i, i) for i in range(22)])          # 3/25＝12%
        r = SO.skip_keys(od2, log=lambda *_: None)
        check("（對照）3 個 absent（12%）⇒ 照濾", set(r) == {"T22|P22", "T23|P23", "T24|P24"}, r)
        sb3 = os.path.join(tmp, "repo3"); od3 = os.path.join(sb3, "soloq_matches"); os.makedirs(od3)
        for i in range(3):
            put(od3, i, "S%d|Q%d" % (i, i), T(i + 1))
        put_accs(sb3, ["S0|Q0", "S1|Q1"])                               # 1/3＝33% > 15%，但只有 3 個檔
        r = SO.skip_keys(od3, log=lambda *_: None)
        check("檔數少於 MIN_FILES 不套比例保險（3 檔裡 1 個 absent＝33% 照濾）", r == {"S2|Q2": "absent"}, r)

        print("⑤ 接進 build_soloq_index：每日戰況不收、索引目錄照舊全列")
        BSI.OUTDIR = od; BSI.IDX = os.path.join(sb, "soloq_match_index.js"); BSI.RECENT = os.path.join(sb, "soloq_recent.js")
        leaks = [k for k in ("OUTDIR", "IDX", "RECENT") if os.path.normcase(getattr(BSI, k)).startswith(realn)]
        check("build_soloq_index 的三個出入口都在沙盒", not leaks, leaks)
        if leaks:
            print("漏接 ⇒ 當場中止（寫檔之前）"); return 1
        os.remove(os.path.join(od, "p13.js"))                          # 壞檔會讓主迴圈印「略過」，這裡不測那條
        rd = lambda p, pre: json.loads(open(p, encoding="utf-8").read()[len(pre):-2])
        so, sys.stdout = sys.stdout, io.StringIO()
        try: BSI._build()
        finally: out1 = sys.stdout.getvalue(); sys.stdout = so
        idx = rd(BSI.IDX, "window.SOLOQ_MATCH_IDX=")["players"]; rec = rd(BSI.RECENT, "window.SOLOQ_RECENT=")["players"]
        check("索引照舊全列（含探針與兩個 dup）", {PROBE, "OLD|Bravo", "AA|DELTA", "AA|Alpha"} <= set(idx), sorted(idx))
        check("每日戰況沒有探針", PROBE not in rec, sorted(rec))
        check("每日戰況沒有兩個 dup 舊檔", not ({"OLD|Bravo", "AA|DELTA"} & set(rec)), sorted(rec))
        check("每日戰況保留現役＋留著的孤兒", {"AA|Alpha", "NEW|Bravo", "AA|Charlie (VN)", "OLD|Golf", "AA|Echo"} <= set(rec), sorted(rec))
        check("日誌有印那一行", "孤兒逐場檔不進聚合" in out1, out1[-300:])
        os.remove(accp)
        so, sys.stdout = sys.stdout, io.StringIO()
        try: BSI._build()
        finally: out2 = sys.stdout.getvalue(); sys.stdout = so
        rec2 = rd(BSI.RECENT, "window.SOLOQ_RECENT=")["players"]
        check("（對照）拿掉帳號檔 ⇒ 探針與 dup 回到每日戰況＝照舊全收", {PROBE, "OLD|Bravo", "AA|DELTA"} <= set(rec2), sorted(rec2))
        check("（對照）那一趟日誌講「不過濾」", "不過濾" in out2, out2[-300:])

        print("⑥ 真實 repo 沒被碰")
        check("帳號檔／索引／每日戰況 md5＋mtime 都沒動", sig(REAL) == before)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n%d 條、紅 %d" % (N[0], N[1]))
    return 1 if N[1] else 0


if __name__ == "__main__":
    sys.exit(main())
