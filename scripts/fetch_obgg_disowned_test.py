# -*- coding: utf-8 -*-
"""fetch_obgg_accounts 的「歸屬剔除名單：dpm 認定是別人的帳號，OBGG 不再補回」沙盒測試（2026-09-08 #67，不打網路）。

為什麼：⑤ fetch_dpm_soloq_accounts 的歸屬複查把 TES|Tian plokijuhyg／WE|Erha 25hdp／OMG|haichao luck dog 剔除（dpm 掛牌是
Bunny／Yagao／Jinjiao 的）並記進 csv_cache/soloq_disowned.json；隔天 10:00 ③ OBGG 仍把它們掛在原選手名下 ⇒ 原封補回（沒 puuid）
⇒ ⑤b 反查 puuid ⇒ ⑤d 當新選手補全年 798 場別人的比賽 ⇒ 22:00 再剔除 ⇒ 每天循環。

沙盒：pull() 整個換成假資料、urlopen／HTTPSConnection 換成會炸的 stub（多一條路就翻紅，不是靜默上網）；
ACCOUNTS／OUT／ROSTER_OUT／DISOWNED 四個路徑常數全指到暫存目錄，leaks() 抓「模組層還指著真實 repo 的路徑」，
並保留一條正控制（把 DISOWNED 指回真實檔 ⇒ leaks() 要抓得到）。跑完比對真實 soloq_accounts.json／.bak／soloq_disowned.json／
obgg_roster.json 的 mtime 一個都沒動。
用法：python scripts/fetch_obgg_disowned_test.py
"""
import io, os, sys, json, datetime, tempfile, contextlib, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SRC = os.path.join(HERE, "fetch_obgg_accounts.py")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location("foa", SRC)
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)   # 模組層會包 sys.stdout，這裡不再包

OK = FAIL = 0
def check(name, cond, info=""):
    global OK, FAIL
    if cond: OK += 1; print(f"  ✓ {name}")
    else: FAIL += 1; print(f"  ✗ {name}  {info}")

# ── 斷網（每一個對外入口都點名） ─────────────────────────────────────────────
class NoNet:
    def __init__(self, *a, **k):
        raise AssertionError("測試打到真實網路：http.client.HTTPSConnection(%s)" % (a[0] if a else "?"))
def no_urlopen(*a, **k):
    raise AssertionError("測試打到真實網路：urllib.request.urlopen")
M.urllib.request.urlopen = no_urlopen
M.http.client.HTTPSConnection = NoNet

# ── 沙盒路徑（每一個出口／證據來源都接管） ────────────────────────────────────
TMP = tempfile.mkdtemp(prefix="obgg_disowned_")
REAL_ACC = os.path.join(M.HERE, "soloq_accounts.json")
REAL_DIS = os.path.join(M.ROOT, "csv_cache", "soloq_disowned.json")
REAL_ROSTER = os.path.join(M.ROOT, "csv_cache", "obgg_roster.json")
REAL_FILES = [p for p in (REAL_ACC, REAL_ACC + ".bak", REAL_DIS, REAL_ROSTER) if os.path.exists(p)]
REAL_MT = {p: os.stat(p).st_mtime for p in REAL_FILES}
M.ACCOUNTS = M.OUT = os.path.join(TMP, "acc.json")
M.ROSTER_OUT = os.path.join(TMP, "roster.json")
M.DISOWNED = os.path.join(TMP, "disowned.json")

def leaks():
    """模組層還指著真實 repo 的檔案路徑常數（＝沒接管到的出入口）"""
    return {k: v for k, v in vars(M).items()
            if isinstance(v, str) and v.endswith((".json", ".txt", ".csv"))
            and os.path.isabs(v) and not v.startswith(TMP)}

print("[0] 沙盒守則")
check("模組層沒有指向真實 repo 的路徑（ACCOUNTS／OUT／ROSTER_OUT／DISOWNED 都在暫存目錄）", not leaks(), leaks())
_sv = M.DISOWNED; M.DISOWNED = REAL_DIS
check("正控制：把 DISOWNED 指回真實名單，leaks() 抓得到（不是恆綠）", "DISOWNED" in leaks())
M.DISOWNED = _sv
check("模組有 DISOWNED／load_disowned／disowned_of", hasattr(M, "DISOWNED") and callable(M.load_disowned) and callable(M.disowned_of))

# ── 假 OBGG：LPL／LCK 各 ≥20 帳號過安全門 ───────────────────────────────────
def zone(teams):
    return {tm: {pl: [{"platform": "kr", "riotId": r} for r in rids] for pl, rids in ps.items()} for tm, ps in teams.items()}
OBGG = {
    "LPL": zone({
        "TES": {"Tian": ["plokijuhyg#yyc04", "yiqunsb#KR1", "other#KR1"]},   # plokijuhyg 名單記是 Bunny 的；other 名單記的是 BLG|Bin 名下 → 不牽連
        "WE":  {"Erha": ["25hdp#JDG", "qwerfdlp#23967"]},                     # 25hdp 名單記是 Yagao 的，但帳號檔裡 dpm 今天確認過 → prune_old 留住
        "OMG": {"haichao": ["luck dog#KR1", "hc main#KR1"]},                  # 名單那邊寫「Luck Dog #KR1」→ normalize 要對得上
        "FIL": {f"f{i}": [f"fill{i}#KR1"] for i in range(20)},
    }),
    "LCK": zone({"T1": {f"k{i}": [f"kfill{i}#KR1"] for i in range(20)}}),
}
TODAY = datetime.date.today().isoformat()
ACC0 = [
    {"player": "Tian", "team": "TES", "platform": "kr", "riotId": "plokijuhyg#yyc04", "dpmPuuid": "pu-plo"},          # 10:00 那班的狀態：補回＋⑤b 反查到 puuid、沒 dpmSeen
    {"player": "Tian", "team": "TES", "platform": "kr", "riotId": "yiqunsb#KR1", "dpmPuuid": "pu-yiq", "dpmSeen": TODAY},
    {"player": "Erha", "team": "WE", "platform": "kr", "riotId": "25hdp#JDG", "dpmPuuid": "pu-25", "dpmSeen": TODAY},   # dpm 又把它還給 Erha（今天確認）
    {"player": "haichao", "team": "OMG", "platform": "kr", "riotId": "luck dog#KR1", "dpmPuuid": "pu-ld"},
]
DIS = [
    {"rid": "plokijuhyg#yyc04", "from": "TES|Tian", "owner": "Bunny", "why": "dpm 掛牌", "at": "2026-09-07 22:05"},
    {"rid": "25hdp#JDG", "from": "WE|Erha", "owner": "Yagao", "why": "dpm 掛牌", "at": "2026-09-07 22:05"},
    {"rid": "Luck Dog #KR1", "from": "OMG|haichao", "owner": "Jinjiao", "why": "dpm 掛牌", "at": "2026-09-07 22:05"},
    {"rid": "other#KR1", "from": "BLG|Bin", "owner": "Nobody", "why": "dpm 掛牌", "at": "2026-09-07 22:05"},
]

def run(dis, acc=ACC0, obgg=OBGG):
    """寫沙盒帳號檔＋名單（dis=None → 不建名單檔；dis=str → 原樣寫壞檔），跑 main()；回 (輸出帳號 list, stdout)。"""
    assert not leaks(), f"沙盒沒接管到：{leaks()}"
    json.dump(acc, open(M.ACCOUNTS, "w", encoding="utf-8"), ensure_ascii=False)
    if os.path.exists(M.DISOWNED):
        os.remove(M.DISOWNED)
    if isinstance(dis, str):
        open(M.DISOWNED, "w", encoding="utf-8").write(dis)
    elif dis is not None:
        json.dump(dis, open(M.DISOWNED, "w", encoding="utf-8"), ensure_ascii=False)
    M.pull = lambda: (obgg, {})
    M.ROSTER_PLAYERS.clear()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        M.main()
    out = json.load(open(M.OUT, encoding="utf-8"))
    return out, buf.getvalue()

def rids(out): return {M.norm(e["riotId"]) for e in out}
def by_rid(out): return {M.norm(e["riotId"]): e for e in out}

print("[1] disowned_of／load_disowned 單元")
json.dump(DIS, open(M.DISOWNED, "w", encoding="utf-8"), ensure_ascii=False)
IDX = M.load_disowned()
check("讀到 4 筆索引", len(IDX) == 4, len(IDX))
check("命中：同 rid 同 隊|名", M.disowned_of(IDX, "TES", "Tian", "plokijuhyg#yyc04") is not None)
check("命中：大小寫／空白 normalize（帳號檔 luck dog#KR1 vs 名單 Luck Dog #KR1）", M.disowned_of(IDX, "OMG", "haichao", "luck dog#KR1") is not None)
check("不命中：同 rid 不同選手（同名選手不牽連）", M.disowned_of(IDX, "TES", "Tian2", "plokijuhyg#yyc04") is None)
check("不命中：同 rid 不同隊", M.disowned_of(IDX, "JDG", "Tian", "plokijuhyg#yyc04") is None)
check("空索引 → None", M.disowned_of({}, "TES", "Tian", "plokijuhyg#yyc04") is None)
check("回的是那筆紀錄（owner／at 可印）", (M.disowned_of(IDX, "TES", "Tian", "plokijuhyg#yyc04") or {}).get("owner") == "Bunny")
os.remove(M.DISOWNED)
check("名單檔不存在 → 空索引", M.load_disowned() == {})
open(M.DISOWNED, "w", encoding="utf-8").write("{{{ not json")
check("名單檔壞掉 → 空索引（不炸）", M.load_disowned() == {})

print("[2] main() e2e：名單有記的不從 OBGG 補回")
out, log = run(DIS)
R = rids(out); B = by_rid(out)
check("plokijuhyg#yyc04 不在輸出（OBGG 略過＋舊檔沒 dpmSeen 被 prune_old 刪）", "plokijuhyg#yyc04" not in R)
check("luck dog#KR1 不在輸出（名單寫法不同也對得上）", "luckdog#kr1" not in R)
check("25hdp#JDG 還在（OBGG 略過，但 dpm 今天確認過 → prune_old 留住＝dpm 現行歸屬優先）",
      "25hdp#jdg" in R and B["25hdp#jdg"].get("dpmSeen") == TODAY and B["25hdp#jdg"].get("player") == "Erha")
check("同選手其他帳號照常（yiqunsb／qwerfdlp／hc main）", {"yiqunsb#kr1", "qwerfdlp#23967", "hcmain#kr1"} <= R)
check("other#KR1 在（名單記的是 BLG|Bin 名下，TES|Tian 不牽連）", "other#kr1" in R and B["other#kr1"]["player"] == "Tian")
check("填充 40 隻都在（安全門過、正常重建）", sum(1 for r in R if r.startswith(("fill", "kfill"))) == 40)
check("三行 [歸屬]…不從 OBGG 補回", log.count("[歸屬]") == 3 and log.count("不從 OBGG 補回") == 3, log.count("[歸屬]"))
check("那三行點名 Bunny／Yagao／Jinjiao", all(o in log for o in ("Bunny", "Yagao", "Jinjiao")))
check("摘要「歸屬名單略過 3 隻」", "歸屬名單略過 3 隻" in log, [l for l in log.splitlines() if "OBGG 帳號更新" in l])
check("舊格式的暫留字樣還在（keepdpm 測試靠它）", "天確認過暫留 " in log)

print("[3] 正控制：名單為空／不存在／壞掉 → 三隻照舊補回（證明是名單在擋）")
for label, dis in (("空名單", []), ("沒有名單檔", None), ("名單檔壞掉", "{{{")):
    out, log = run(dis)
    R = rids(out)
    check(f"{label}：plokijuhyg／luck dog 都被補回", {"plokijuhyg#yyc04", "luckdog#kr1"} <= R, sorted(R)[:6])
    check(f"{label}：沒有 [歸屬] 行、摘要略過 0 隻", "[歸屬]" not in log and "歸屬名單略過 0 隻" in log)

print("[4] OBGG 把同一隻掛在別的選手名下 → 那是 from 不同，照常補（名單不封殺 rid 本身）")
OBGG2 = json.loads(json.dumps(OBGG)); OBGG2["LPL"]["TES"]["Bunny"] = [{"platform": "kr", "riotId": "plokijuhyg#yyc04"}]
del OBGG2["LPL"]["TES"]["Tian"][0]
out, log = run(DIS, obgg=OBGG2)
B = by_rid(out)
check("plokijuhyg#yyc04 進了 TES|Bunny", "plokijuhyg#yyc04" in B and B["plokijuhyg#yyc04"]["player"] == "Bunny", B.get("plokijuhyg#yyc04"))
check("只剩 2 行 [歸屬]（25hdp／luck dog）", log.count("[歸屬]") == 2, log.count("[歸屬]"))

print("[5] 真實檔一個都沒動")
for p in REAL_FILES:
    check(f"{os.path.relpath(p, ROOT)} mtime 不變", os.stat(p).st_mtime == REAL_MT[p])
check("沙盒帳號檔的 .bak 寫在暫存目錄（OUT == ACCOUNTS 才留備份）", os.path.exists(M.ACCOUNTS + ".bak"))

print("[6] 原始碼位置：main() 真的走 load_disowned／disowned_of、摘要印略過數")
src = open(SRC, encoding="utf-8").read()
m = src[src.index("\ndef main():"):]
check("main() 載入名單一次", m.count("load_disowned()") == 1, m.count("load_disowned()"))
check("obgg_entries 逐帳號問 disowned_of(dis_idx, tc, gid, …)", "disowned_of(dis_idx, tc, gid, a[\"riotId\"])" in m)
check("摘要印「歸屬名單略過」", "歸屬名單略過 {len(dis_skipped)} 隻" in m)
check("DISOWNED 指向 csv_cache/soloq_disowned.json", 'DISOWNED = os.path.join(ROOT, "csv_cache", "soloq_disowned.json")' in src)

print(f"\n結果：✓ {OK}　✗ {FAIL}")
sys.exit(1 if FAIL else 0)
