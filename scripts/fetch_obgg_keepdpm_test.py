# -*- coding: utf-8 -*-
"""fetch_obgg_accounts 的「OBGG 主導賽區舊帳號，dpm 近 KEEP_DPM_DAYS 天確認過的暫留」離線測試（不打網路）。
用法：python scripts/fetch_obgg_keepdpm_test.py
"""
import os, sys, json, datetime, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SRC = os.path.join(HERE, "fetch_obgg_accounts.py")
spec = importlib.util.spec_from_file_location("foa", SRC)
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)   # 模組層會包 sys.stdout，這裡不再包

OK = FAIL = 0
def check(name, cond, info=""):
    global OK, FAIL
    if cond: OK += 1; print(f"  ✓ {name}")
    else: FAIL += 1; print(f"  ✗ {name}  {info}")

D = datetime.date(2026, 9, 6)
def at(days_ago): return (D - datetime.timedelta(days=days_ago)).isoformat()

print("[1] dpm_recent：誰算「dpm 近 3 天確認過」")
check("常數 KEEP_DPM_DAYS == 3", M.KEEP_DPM_DAYS == 3, M.KEEP_DPM_DAYS)
check("今天 → 留", M.dpm_recent({"dpmSeen": at(0)}, today=D))
check("3 天前 → 留（含第 3 天）", M.dpm_recent({"dpmSeen": at(3)}, today=D))
check("4 天前 → 刪", not M.dpm_recent({"dpmSeen": at(4)}, today=D))
check("沒有 dpmSeen → 刪", not M.dpm_recent({}, today=D))
check("dpmSeen=None → 刪", not M.dpm_recent({"dpmSeen": None}, today=D))
check("壞字串 → 刪", not M.dpm_recent({"dpmSeen": "garbage"}, today=D))
check("未來日期（時鐘倒退）→ 刪", not M.dpm_recent({"dpmSeen": at(-1)}, today=D))
check("days=0 只留今天", M.dpm_recent({"dpmSeen": at(0)}, today=D, days=0) and not M.dpm_recent({"dpmSeen": at(1)}, today=D, days=0))
check("帶時間的 ISO 字串也吃（取前 10 碼）", M.dpm_recent({"dpmSeen": at(1) + "T10:00:00"}, today=D))

print("[2] prune_old：合成資料")
zone = {"T1": "LCK", "BLG": "LPL", "G2": "LEC", "FLY": "LCS", "XYZ": None}
def zone_of(t): return zone.get(t)
acc = [
 {"team": "T1",  "riotId": "in list#KR1",  "dpmSeen": None},        # OBGG 清單有 → 上面已重建，不重複
 {"team": "T1",  "riotId": "dpm keep#KR1", "dpmSeen": at(1), "dpmPuuid": "p1", "bad": 1},   # 不在清單、dpm 昨天確認 → 暫留
 {"team": "BLG", "riotId": "stale#KR1",    "dpmSeen": at(9)},       # 不在清單、dpm 9 天沒確認 → 刪
 {"team": "BLG", "riotId": "nodpm#KR1"},                            # 不在清單、沒 dpmSeen → 刪
 {"team": "G2",  "riotId": "lec old#EUW",  "dpmSeen": None},        # dpm 主導賽區 → 照舊保留
 {"team": "FLY", "riotId": "lcs in#NA1",   "dpmSeen": None},        # 非 OBGG 區但在清單 → 不重複
 {"team": "XYZ", "riotId": "unknown#KR1"},                          # 無法分類 → 保留
]
new = [{"team": "T1", "riotId": "in list#KR1"}, {"team": "FLY", "riotId": "lcs in#NA1"}]
new_rids = {M.norm(e["riotId"]) for e in new}
removed, kept = M.prune_old(acc, new, new_rids, zone_of, today=D)
rids = [e["riotId"] for e in new]
check("刪 2（stale、nodpm）", removed == 2, removed)
check("暫留 1（dpm keep）", kept == 1, kept)
check("dpm keep 併回", "dpm keep#KR1" in rids, rids)
check("stale／nodpm 沒併回", "stale#KR1" not in rids and "nodpm#KR1" not in rids, rids)
check("LEC 舊帳號照舊保留", "lec old#EUW" in rids, rids)
check("無法分類照舊保留", "unknown#KR1" in rids, rids)
check("清單內的不重複", rids.count("in list#KR1") == 1 and rids.count("lcs in#NA1") == 1, rids)
check("併回的是原 dict（dpmPuuid／bad 欄位都還在）", any(e is acc[1] for e in new))
check("負控制：days=0 且 dpmSeen=昨天 → 刪", M.prune_old([acc[1]], [], set(), zone_of, today=D, days=0) == (1, 0))
check("負控制：OBGG 清單為空、沒人有 dpmSeen → LPL/LCK 全刪", M.prune_old([acc[0], acc[3]], [], set(), zone_of, today=D) == (2, 0))

print("[3] 真實帳號檔離線 e2e：假裝 OBGG 只列出前 800 隻、全部當 LPL")
acc_real = json.load(open(os.path.join(HERE, "soloq_accounts.json"), encoding="utf-8"))
seen = sorted({str(a.get("dpmSeen"))[:10] for a in acc_real if a.get("dpmSeen")})
T = datetime.date.fromisoformat(seen[-1]) if seen else D   # 以檔內最新 dpmSeen 當「今天」，測試不隨日期漂移
with_seen = [a for a in acc_real if a.get("dpmSeen")]
listed = with_seen[:800]                                   # OBGG「有列」的 800 隻全挑有 dpmSeen 的
rest = [a for a in acc_real if not any(a is x for x in listed)]   # 其餘（含所有沒 dpmSeen 的）→ 走「不在清單」的路徑
new_r = [dict(e) for e in listed]; rids_r = {M.norm(e["riotId"]) for e in new_r}
print(f"   （檔內 {len(acc_real)} 隻、有 dpmSeen {len(with_seen)} 隻、沒有 {len(acc_real) - len(with_seen)} 隻；不在清單的 {len(rest)} 隻）")
removed_r, kept_r = M.prune_old(acc_real, new_r, rids_r, lambda t: "LPL", today=T)
exp_keep = sum(1 for a in rest if M.dpm_recent(a, today=T)); exp_rm = len(rest) - exp_keep
check(f"{len(acc_real)} 隻：暫留 {kept_r} == dpmSeen 近 3 天的 {exp_keep}", kept_r == exp_keep, (kept_r, exp_keep))
check(f"刪 {removed_r} == 其餘 {exp_rm}", removed_r == exp_rm, (removed_r, exp_rm))
check("總數 = 800 + 暫留", len(new_r) == 800 + kept_r, len(new_r))
check("正例會動：至少有一隻靠 dpmSeen 留下來", kept_r > 0, kept_r)
check("負控制：today 推到 10 天後 → 一隻都留不住", M.prune_old(acc_real, [dict(e) for e in listed], rids_r, lambda t: "LPL", today=T + datetime.timedelta(days=10))[1] == 0)
players_kept = {(a.get("team"), a.get("player")) for a in new_r}
lost = sorted({(a.get("team"), a.get("player")) for a in rest if M.dpm_recent(a, today=T)} - players_kept)
check("dpm 有確認的選手，帳號全不在清單也不會整個人消失", not lost, lost[:5])

print("[4] 原始碼位置：main() 真的走 prune_old、摘要印出暫留數")
src = open(SRC, encoding="utf-8").read()
check("main() 呼叫 prune_old(acc, new, new_rids, zone_of)", "removed, kept_dpm = prune_old(acc, new, new_rids, zone_of)" in src)
check("舊的 removed += 1 迴圈已不在 main()（只剩 prune_old 裡一處）", src.count("removed += 1") == 1, src.count("removed += 1"))
check("摘要印出「dpm 近 N 天確認過暫留」", "天確認過暫留 {kept_dpm}" in src)
check("import datetime", "import io, sys, json, os, re, time, datetime," in src)

print(f"\n結果：✓ {OK}　✗ {FAIL}")
sys.exit(1 if FAIL else 0)
