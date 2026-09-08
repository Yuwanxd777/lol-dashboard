# -*- coding: utf-8 -*-
"""fetch_dpm_soloq_accounts 的沙盒測試（2026-09-08 #66 提速那批）。

只測「不上網、不寫檔」的三個工具：fetch_pros_batch（批次＋節奏＋限流減半）、_iter_batches（中途縮小）、
_owners_of（歸屬複查一次 Promise.all＋逐一補問）。pg 是假物件、time.sleep 被接管記錄，
主流程 main() 不跑（它會讀 26MB 年度資料並寫 preview 檔）——所以這裡另外用**原始碼層**斷言主流程的結構：
只 launch 一個瀏覽器、沒有第二個 sync_playwright、批次迴圈後沒有固定 sleep(0.5)；並拿 git HEAD 那版當正控制，
證明這幾條斷言在舊版真的會紅（不是永遠綠的檢查）。

用法：python scripts/fetch_dpm_soloq_accounts_test.py
"""
import io, os, sys, re, time, json, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fetch_dpm_soloq_accounts as M

FAILS = []
N_OK = 0


def check(cond, msg):
    global N_OK
    if cond:
        N_OK += 1
    else:
        FAILS.append(msg)
        print("  ✗", msg)


class FakePG:
    """假 page：依 URL 決定回什麼。calls 記每次 evaluate 的 (js 種類, 參數)。"""
    def __init__(self, table, delay=0.0, fail_many=False, one_table=None):
        self.table = table          # url -> {"st":..., "j":...} 或 {"st":..., "dn":...}
        self.one_table = one_table  # JS_ONE 專用的表（歸屬補問時同一個 URL 的回法跟 OWNERS 不同）
        self.delay = delay
        self.fail_many = fail_many
        self.calls = []

    def evaluate(self, js, arg=None):
        kind = ("MANY" if js == M.JS_MANY else "OWNERS" if js == M.JS_OWNERS else "ONE" if js == M.JS_ONE else "?")
        self.calls.append((kind, arg))
        if self.delay:
            time.sleep(self.delay)
        if kind == "MANY":
            if self.fail_many:
                raise RuntimeError("evaluate 炸了")
            return [dict(self.table.get(u, {"st": 404, "j": None})) for u in arg]
        if kind == "OWNERS":
            return [dict(self.table.get(u, {"st": 404, "dn": None})) for u in arg]
        if kind == "ONE":
            r = (self.one_table or {}).get(arg) or self.table.get(arg)
            return (r or {}).get("j") if r and r.get("st") == 200 else None
        raise AssertionError("未知的 js")


def _players(name):
    return {"players": [{"puuid": "pu-" + name, "gameName": name, "tagLine": "T1", "team": "X"}]}


def _url(name):
    import urllib.parse
    return "/v1/pros/" + urllib.parse.quote(M._VARIANTS(name)[0], safe="")


def with_sleep_recorder(fn):
    """接管 time.sleep：只記錄不真睡；回 (fn 的結果, 睡的清單)。_pace 也會呼叫 time.sleep，所以會一併記到。"""
    slept = []
    real = M.time.sleep
    M.time.sleep = lambda s: slept.append(round(s, 3))
    try:
        return fn(), slept
    finally:
        M.time.sleep = real


def reset():
    M._BS[0] = M.BATCH
    M._last_batch_t[0] = 0.0


# ── 0. 常數本身 ────────────────────────────────────────────────────────────────
print("0. 常數")
check(M.BATCH == 12, f"BATCH 應為 12，實際 {M.BATCH}")
check(abs(M.MIN_GAP - 0.5) < 1e-9, f"MIN_GAP 應為 0.5，實際 {M.MIN_GAP}")
check(M.OWNER_BATCH >= 24, f"OWNER_BATCH 應 ≥ 24，實際 {M.OWNER_BATCH}")

# ── 1. _iter_batches：依目前批次大小切、中途縮小跟著變 ───────────────────────
print("1. _iter_batches")
reset()
names = [f"n{i}" for i in range(30)]
sizes = []
for ch in M._iter_batches(names):
    sizes.append(len(ch))
    if len(sizes) == 1:
        M._BS[0] = 4          # 模擬第一批之後被限流減半…再減
check(sizes == [12, 4, 4, 4, 4, 2], f"中途縮小：期望 [12,4,4,4,4,2]，實際 {sizes}")
check(sum(sizes) == 30, "切塊總數要等於名字數")
reset()
check([len(c) for c in M._iter_batches(names)] == [12, 12, 6], "預設 12 一批")
check(list(M._iter_batches([])) == [], "空清單不產生批次")

# ── 2. fetch_pros_batch：正常批次一次 evaluate、命中的不再逐一 ───────────────
print("2. fetch_pros_batch 正常")
reset()
tbl = {_url(n): {"st": 200, "j": _players(n)} for n in ["Faker", "Chovy", "Zeus"]}
pg = FakePG(tbl)
out, slept = with_sleep_recorder(lambda: M.fetch_pros_batch(pg, ["Faker", "Chovy", "Zeus"]))
check(set(out) == {"Faker", "Chovy", "Zeus"} and all(out[n][0]["puuid"] == "pu-" + n for n in out), "三位各拿到自己的 plist")
check([c[0] for c in pg.calls] == ["MANY"], f"命中時只有一次 MANY evaluate，實際 {[c[0] for c in pg.calls]}")
check(M._BS[0] == 12, "沒限流 → 批次大小不變")

# 第一個變體查無（小寫 ceo → dpm 顯示名 Ceo）→ 只有那一位走逐變體路徑
print("2b. 第一個變體查無 → 只那位退回逐變體")
reset()
tbl = {_url("Faker"): {"st": 200, "j": _players("Faker")},
       "/v1/pros/Ceo": {"st": 200, "j": _players("Ceo")}}
pg = FakePG(tbl)
out, _ = with_sleep_recorder(lambda: M.fetch_pros_batch(pg, ["Faker", "ceo"]))
check(out["Faker"][0]["puuid"] == "pu-Faker" and out["ceo"] and out["ceo"][0]["puuid"] == "pu-Ceo", "ceo 用第二個變體 Ceo 查到")
ones = [c[1] for c in pg.calls if c[0] == "ONE"]
check(ones and all("eo" in u for u in ones) and not any("Faker" in u for u in ones),
      f"逐變體只問 ceo 的變體、不動 Faker，實際 {ones}")

# ── 3. 限流：整批退回逐一、睡 5 秒、之後批次減半（最低 3）────────────────────
print("3. 限流減半")
reset()
tbl = {_url(n): {"st": 200, "j": _players(n)} for n in ["A", "B"]}
tbl[_url("C")] = {"st": 429, "j": None}
pg = FakePG(tbl)
out, slept = with_sleep_recorder(lambda: M.fetch_pros_batch(pg, ["A", "B", "C"]))
check(5 in slept, f"限流要睡 5 秒，實際睡了 {slept}")
check(M._BS[0] == 6, f"12 → 6，實際 {M._BS[0]}")
check(out["A"] and out["B"] and out["C"] == [], "退回逐一後 A、B 仍查到、C 查無")
kinds = [c[0] for c in pg.calls]
check(kinds[0] == "MANY" and kinds.count("ONE") >= 3, f"MANY 之後每位至少一次 ONE，實際 {kinds}")
for _ in range(5):
    with_sleep_recorder(lambda: M.fetch_pros_batch(pg, ["A", "B", "C"]))
check(M._BS[0] == 3, f"連續限流也不會低於 3，實際 {M._BS[0]}")
reset()
tbl503 = {_url("A"): {"st": 503, "j": None}}
pg = FakePG(tbl503)
out, slept = with_sleep_recorder(lambda: M.fetch_pros_batch(pg, ["A"]))
check(M._BS[0] == 6 and 5 in slept, "5xx 同樣算限流：減半＋睡 5")
reset()
pg = FakePG({}, fail_many=True)
out, slept = with_sleep_recorder(lambda: M.fetch_pros_batch(pg, ["A"]))
check(out["A"] == [] and 5 in slept and M._BS[0] == 12, "evaluate 例外：退回逐一、睡 5，但**不**減半（不是限流）")

# ── 4. 節奏：兩批開始時間至少隔 MIN_GAP；批次本身夠慢就不補睡 ─────────────────
print("4. _pace")
reset()
tbl = {_url("A"): {"st": 200, "j": _players("A")}}
pg = FakePG(tbl)                      # 瞬間回
t0 = time.time()
M.fetch_pros_batch(pg, ["A"]); M.fetch_pros_batch(pg, ["A"]); M.fetch_pros_batch(pg, ["A"])
dt = time.time() - t0
check(0.95 <= dt <= 1.6, f"三批瞬間回 → 兩段間隔各補到 0.5s，合計約 1.0s，實際 {dt:.2f}s")
reset()
pg = FakePG(tbl, delay=0.6)           # 批次本身 0.6s > MIN_GAP
t0 = time.time()
M.fetch_pros_batch(pg, ["A"]); M.fetch_pros_batch(pg, ["A"])
dt = time.time() - t0
check(1.15 <= dt <= 1.5, f"批次本身 0.6s → 不補睡，兩批約 1.2s（舊寫法會是 2.2s），實際 {dt:.2f}s")
reset()
_, slept = with_sleep_recorder(lambda: M.fetch_pros_batch(FakePG(tbl), ["A"]))
check(slept == [] or all(s <= 0.5 for s in slept), f"沒限流時不會出現 5 秒睡，實際 {slept}")

# ── 5. _owners_of：一次 Promise.all、404→None、限流那隻才逐一補問 ──────────────
print("5. _owners_of")
reset()
tbl = {"/v1/players/p1": {"st": 200, "dn": "Beichuan"},
       "/v1/players/p2": {"st": 404, "dn": None},
       "/v1/players/p3": {"st": 429, "dn": None},
       "/v1/players/p4": {"st": 200, "dn": None}}      # 掛牌空＝一般玩家
tbl_one = {"/v1/players/p3": {"st": 200, "j": {"displayName": "lamb"}}}
pg = FakePG(tbl, one_table=tbl_one)
out, slept = with_sleep_recorder(lambda: M._owners_of(pg, ["p1", "p2", "p3", "p4", "p1", None, ""]))
check(out == {"p1": "Beichuan", "p2": None, "p3": "lamb", "p4": None}, f"歸屬結果 {out}")
kinds = [c[0] for c in pg.calls]
check(kinds.count("OWNERS") == 1, f"四隻（去重後）一次 OWNERS，實際 {kinds}")
ones = [c[1] for c in pg.calls if c[0] == "ONE"]
check(ones == ["/v1/players/p3"], f"只有 429 那隻逐一補問，實際 {ones}")
check(5 in slept, "補問前睡 5 秒")
reset()
pg = FakePG({"/v1/players/p1": {"st": 200, "dn": "X"}})
out, slept = with_sleep_recorder(lambda: M._owners_of(pg, ["p1"]))
check(out == {"p1": "X"} and 5 not in slept and [c[0] for c in pg.calls] == ["OWNERS"], "全 200 → 不睡 5、不逐一")
check(M._owners_of(FakePG({}), []) == {}, "空清單 → 空 dict、不呼叫")
reset()
big = {f"/v1/players/q{i}": {"st": 200, "dn": f"N{i}"} for i in range(50)}
pg = FakePG(big)
out, _ = with_sleep_recorder(lambda: M._owners_of(pg, [f"q{i}" for i in range(50)]))
check(len(out) == 50 and [c[0] for c in pg.calls].count("OWNERS") == 3, "50 隻切成 24/24/2 三批")

# ── 6. 原始碼層：主流程只開一個瀏覽器、沒有第二個 sync_playwright、批次後沒有固定睡 ─
print("6. 原始碼結構（含 HEAD 舊版正控制）")
SRC = io.open(M.__file__, encoding="utf-8").read()
main_src = SRC[SRC.index("\ndef main():"):]


def structure_bad(src):
    m = src[src.index("\ndef main():"):]
    bad = []
    if m.count("_launch(") != 1:
        bad.append(f"main 裡 _launch 次數 {m.count('_launch(')}")
    if "sync_playwright() as p2" in m or "pg2" in m or "b2 = " in m:
        bad.append("還有第二個瀏覽器（p2/pg2/b2）")
    if re.search(r"fetch_pros_batch\([^\n]*\n[^\n]*time\.sleep\(0\.5\)", m) or "time.sleep(0.5)" in m:
        bad.append("批次迴圈後還有固定 sleep(0.5)")
    if "_owners_of(pg" not in m:
        bad.append("歸屬複查沒沿用第一個 page")
    if "_shutdown()" not in m:
        bad.append("沒有 _shutdown")
    return bad


check(structure_bad(SRC) == [], f"現版結構：{structure_bad(SRC)}")
try:
    old = subprocess.run(["git", "show", "HEAD:scripts/fetch_dpm_soloq_accounts.py"], cwd=ROOT,
                         capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30).stdout
except Exception as e:
    old = ""
if old and "\ndef main():" in old:
    bad_old = structure_bad(old)
    if "_owners_of(" in old:      # HEAD 已經是新版（commit 之後跑）→ 正控制改用「把新版退化」的假原始碼
        fake_old = SRC.replace("_owners_of(pg,", "_x(pg2,").replace("_shutdown()", "b.close()") + "\n# b2 = _launch(p2)\n"
        bad_old = structure_bad(fake_old)
        check(len(bad_old) >= 2, f"正控制（人工退化版）要紅，實際 {bad_old}")
    else:
        check(len(bad_old) >= 3, f"正控制：HEAD 舊版要紅在 ≥3 點，實際 {bad_old}")
else:
    check(False, "拿不到 HEAD 版本當正控制")

# ── 7. 模組層沒有路徑常數指到別處；本測試不寫檔 ────────────────────────────────
print("7. 沙盒守則")
check(os.path.basename(M.ACCOUNTS) == "soloq_accounts.json" and os.path.basename(M.PREVIEW) == "soloq_accounts.preview.json", "常數名沒被改")
_pw_mods = [k for k in sys.modules if k.startswith("playwright")]
check(not _pw_mods or True, "（資訊）playwright 有沒有被匯入不影響：本測試沒開瀏覽器")

print()
if FAILS:
    print(f"✗ {len(FAILS)} 條失敗／{N_OK} 條通過")
    sys.exit(1)
print(f"✓ 全部通過：{N_OK} 條")
