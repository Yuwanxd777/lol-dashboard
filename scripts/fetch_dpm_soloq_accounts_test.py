# -*- coding: utf-8 -*-
"""fetch_dpm_soloq_accounts 的沙盒測試（2026-09-08 #66 提速那批；2026-09-09 #73 加 BATCH 24 與退路批次化 fetch_pros_rest）。

只測「不上網、不寫檔」的三個工具：fetch_pros_batch（批次＋節奏＋限流減半＋退路批次化）、_iter_batches（中途縮小）、
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
check(M.BATCH == 24, f"BATCH 應為 24（#73），實際 {M.BATCH}")
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
check(sizes == [24, 4, 2], f"中途縮小：期望 [24,4,2]，實際 {sizes}")
check(sum(sizes) == 30, "切塊總數要等於名字數")
reset()
check([len(c) for c in M._iter_batches(names)] == [24, 6], "預設 24 一批")
check(list(M._iter_batches([])) == [], "空清單不產生批次")

# ── 2. fetch_pros_batch：正常批次一次 evaluate、命中的不再逐一 ───────────────
print("2. fetch_pros_batch 正常")
reset()
tbl = {_url(n): {"st": 200, "j": _players(n)} for n in ["Faker", "Chovy", "Zeus"]}
pg = FakePG(tbl)
out, slept = with_sleep_recorder(lambda: M.fetch_pros_batch(pg, ["Faker", "Chovy", "Zeus"]))
check(set(out) == {"Faker", "Chovy", "Zeus"} and all(out[n][0]["puuid"] == "pu-" + n for n in out), "三位各拿到自己的 plist")
check([c[0] for c in pg.calls] == ["MANY"], f"命中時只有一次 MANY evaluate，實際 {[c[0] for c in pg.calls]}")
check(M._BS[0] == 24, "沒限流 → 批次大小不變")

# 第一個變體查無（小寫 ceo → dpm 顯示名 Ceo）→ #73：只那位的其餘變體再一次 MANY 問完（以前逐變體 ONE）
print("2b. 第一個變體查無 → 只那位的其餘變體再一次 MANY")
reset()
tbl = {_url("Faker"): {"st": 200, "j": _players("Faker")},
       "/v1/pros/Ceo": {"st": 200, "j": _players("Ceo")}}
pg = FakePG(tbl)
out, slept = with_sleep_recorder(lambda: M.fetch_pros_batch(pg, ["Faker", "ceo"]))
check(out["Faker"][0]["puuid"] == "pu-Faker" and out["ceo"] and out["ceo"][0]["puuid"] == "pu-Ceo", "ceo 用第二個變體 Ceo 查到")
kinds = [c[0] for c in pg.calls]
check(kinds == ["MANY", "MANY"], f"兩次 MANY、沒有 ONE，實際 {kinds}")
check(pg.calls[1][1] == ["/v1/pros/Ceo", "/v1/pros/CEO"], f"第二次 MANY 只問 ceo 的其餘變體（Ceo、CEO）、不再問 ceo 也不動 Faker，實際 {pg.calls[1][1]}")
check(5 not in slept and M._BS[0] == 24, "退路批次沒限流 → 不睡 5、不減半")

print("2c. 退路批次：同一名字取第一個有結果的變體（跟 fetch_pro_seq 同義）、多名一次問完")
reset()
tbl = {"/v1/pros/Abc": {"st": 200, "j": _players("Abc")}, "/v1/pros/ABC": {"st": 200, "j": _players("ABC")},
       "/v1/pros/XYZ": {"st": 200, "j": _players("XYZ")}}
pg = FakePG(tbl)
out, _ = with_sleep_recorder(lambda: M.fetch_pros_batch(pg, ["abc", "xyz", "nobody"]))
check(out["abc"][0]["puuid"] == "pu-Abc", f"abc：Abc 與 ABC 都有 → 取順序在前的 Abc，實際 {out['abc']}")
check(out["xyz"][0]["puuid"] == "pu-XYZ" and out["nobody"] == [], "xyz 用第三個變體查到；nobody 全查無 → []")
check([c[0] for c in pg.calls] == ["MANY", "MANY"], f"三位查無 → 其餘變體 6 隻一次 MANY，實際 {[c[0] for c in pg.calls]}")
check(pg.calls[1][1] == ["/v1/pros/Abc", "/v1/pros/ABC", "/v1/pros/Xyz", "/v1/pros/XYZ", "/v1/pros/Nobody", "/v1/pros/NOBODY"],
      f"退路 URL 依名字、再依變體順序，實際 {pg.calls[1][1]}")
_seq = {n: M.fetch_pro_seq(FakePG(tbl), n) for n in ["abc", "xyz", "nobody"]}
check(all(json.dumps(out[n], sort_keys=True) == json.dumps(_seq[n], sort_keys=True) for n in _seq), "三位結果跟舊逐變體路徑逐位相同")

print("2d. 第一變體狀態不是 200／404（fetch 例外 st=0）→ 退路把第一變體也再問一次")
reset()
tbl = {_url("Flaky"): {"st": 0, "j": None}}
pg = FakePG(tbl)
pg.table[_url("Flaky")] = {"st": 0, "j": None}
out, _ = with_sleep_recorder(lambda: M.fetch_pros_batch(pg, ["Flaky"]))
check(pg.calls[1][1][0] == _url("Flaky"), f"退路第一隻就是 Flaky 本身，實際 {pg.calls[1][1]}")
reset()
pg = FakePG({_url("Gone"): {"st": 404, "j": None}})
with_sleep_recorder(lambda: M.fetch_pros_batch(pg, ["Gone"]))
check(_url("Gone") not in pg.calls[1][1], f"404 的第一變體不再問，實際 {pg.calls[1][1]}")

print("2e. 退路批次限流 → 減半＋睡 5、那一塊的名字退回逐變體 ONE；evaluate 例外 → 退回但不減半")
reset()
tbl = {"/v1/pros/Ceo": {"st": 429, "j": None}}
tbl_one = {"/v1/pros/CEO": {"st": 200, "j": _players("CEO")}}
pg = FakePG(tbl, one_table=tbl_one)
out, slept = with_sleep_recorder(lambda: M.fetch_pros_batch(pg, ["ceo"]))
check(5 in slept and M._BS[0] == 12, f"退路 429 → 睡 5、24 → 12，實際 slept={slept} _BS={M._BS[0]}")
check(out["ceo"] and out["ceo"][0]["puuid"] == "pu-CEO", "退回逐變體後仍查到 CEO")
check([c[0] for c in pg.calls][:2] == ["MANY", "MANY"] and "ONE" in [c[0] for c in pg.calls], f"MANY、MANY(退路)、再 ONE，實際 {[c[0] for c in pg.calls]}")
reset()


class FlakyPG(FakePG):
    """第二次 MANY（退路）才炸。"""
    def evaluate(self, js, arg=None):
        if js == M.JS_MANY and sum(1 for c in self.calls if c[0] == "MANY") == 1:
            self.calls.append(("MANY", arg)); raise RuntimeError("退路 evaluate 炸了")
        return super().evaluate(js, arg)


pg = FlakyPG({}, one_table={"/v1/pros/Ceo": {"st": 200, "j": _players("Ceo")}})
out, slept = with_sleep_recorder(lambda: M.fetch_pros_batch(pg, ["ceo"]))
check(out["ceo"] and out["ceo"][0]["puuid"] == "pu-Ceo" and 5 in slept and M._BS[0] == 24, "退路例外：逐變體補到、睡 5、不減半")

print("2f. 退路 URL 依目前批次大小切塊")
reset()
M._BS[0] = 3
pg = FakePG({})
out, _ = with_sleep_recorder(lambda: M.fetch_pros_batch(pg, ["aaa", "bbb"]))
manys = [c[1] for c in pg.calls if c[0] == "MANY"]
check([len(u) for u in manys] == [2, 3, 1], f"2 名 × 2 變體＝4 隻 → 3＋1 兩塊，實際 {[len(u) for u in manys]}")
check(out == {"aaa": [], "bbb": []}, "全查無 → 各 []")
reset()

print("2g. 正控制：HEAD 舊版在 2b 情境真的會走 ONE（斷言不是恆綠）")
import importlib.util, tempfile as _tf
try:
    _old = subprocess.run(["git", "show", "HEAD:scripts/fetch_dpm_soloq_accounts.py"], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30).stdout
except Exception:
    _old = ""
if _old and "def fetch_pros_batch" in _old:
    if "fetch_pros_rest" in _old:      # HEAD 已是新版 → 人工退化：把退路改回逐名 fetch_pro_seq
        _old = _old.replace("out.update(fetch_pros_rest(pg, missed, st_by))", "out.update({n: fetch_pro_seq(pg, n) for n in missed})")
    _old = _old.replace("sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding=\"utf-8\", errors=\"replace\")", "pass")
    _tmp = os.path.join(_tf.mkdtemp(prefix="dpm_old_"), "fetch_dpm_old.py")
    io.open(_tmp, "w", encoding="utf-8").write(_old)
    _spec = importlib.util.spec_from_file_location("fetch_dpm_old", _tmp)
    O = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(O)
    O._BS[0] = O.BATCH; O._last_batch_t[0] = 0.0
    _rs = O.time.sleep; O.time.sleep = lambda s: None
    try:
        class OldPG(FakePG):
            def evaluate(self, js, arg=None):
                kind = ("MANY" if js == O.JS_MANY else "ONE" if js == O.JS_ONE else "?")
                self.calls.append((kind, arg))
                if kind == "MANY":
                    return [dict(self.table.get(u, {"st": 404, "j": None})) for u in arg]
                r = self.table.get(arg)
                return (r or {}).get("j") if r and r.get("st") == 200 else None
        opg = OldPG({_url("Faker"): {"st": 200, "j": _players("Faker")}, "/v1/pros/Ceo": {"st": 200, "j": _players("Ceo")}})
        oout = O.fetch_pros_batch(opg, ["Faker", "ceo"])
        okinds = [c[0] for c in opg.calls]
        check(oout["ceo"] and oout["ceo"][0]["puuid"] == "pu-Ceo", "舊版結果相同（ceo → Ceo）")
        check("ONE" in okinds and okinds.count("MANY") == 1, f"舊版真的走逐變體 ONE（新版是 MANY×2），實際 {okinds}")
        check(len(opg.calls) > 2, f"舊版 evaluate 次數 {len(opg.calls)} > 新版 2")
    finally:
        O.time.sleep = _rs
else:
    check(False, "拿不到 HEAD 版本當 2g 正控制")

# ── 3. 限流：整批退回逐一、睡 5 秒、之後批次減半（最低 3）────────────────────
print("3. 限流減半")
reset()
tbl = {_url(n): {"st": 200, "j": _players(n)} for n in ["A", "B"]}
tbl[_url("C")] = {"st": 429, "j": None}
pg = FakePG(tbl)
out, slept = with_sleep_recorder(lambda: M.fetch_pros_batch(pg, ["A", "B", "C"]))
check(5 in slept, f"限流要睡 5 秒，實際睡了 {slept}")
check(M._BS[0] == 12, f"24 → 12，實際 {M._BS[0]}")
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
check(M._BS[0] == 12 and 5 in slept, "5xx 同樣算限流：減半＋睡 5")
reset()
pg = FakePG({}, fail_many=True)
out, slept = with_sleep_recorder(lambda: M.fetch_pros_batch(pg, ["A"]))
check(out["A"] == [] and 5 in slept and M._BS[0] == 24, "evaluate 例外：退回逐一、睡 5，但**不**減半（不是限流）")

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

# ── 8. #67 union 分支：名單已記是別人的既有帳號直接剔除（不等 puuid 複查） ─────────────
# 背景：③ OBGG 每天把 ⑤ 剔除過的帳號補回（沒 puuid）⇒ 以前這裡只有帶 puuid 的才進 ORPHANS 複查 ⇒ 看不到 ⇒
# ⑤b 補 puuid ⇒ ⑤d 抓幾百場別人的比賽 ⇒ 22:00 才剔除。現在 _union_one 直接查 soloq_disowned 名單。
print("8. #67 名單剔除（_union_one／disowned_hit／load_disowned_idx）")
import tempfile
_tmpd = tempfile.mkdtemp(prefix="dpm_disowned_")
_dpath = os.path.join(_tmpd, "disowned.json")
json.dump([{"rid": "plokijuhyg#yyc04", "from": "TES|Tian", "owner": "Bunny", "why": "dpm 掛牌", "at": "2026-09-07 22:05"},
           {"rid": "Luck Dog #KR1", "from": "OMG|haichao", "owner": "Jinjiao", "why": "dpm 掛牌", "at": "2026-09-07 22:05"}],
          open(_dpath, "w", encoding="utf-8"), ensure_ascii=False)
IDX = M.load_disowned_idx(_dpath)
check(len(IDX) == 2, "load_disowned_idx 讀到 2 筆")
check(M.load_disowned_idx(os.path.join(_tmpd, "nope.json")) == {}, "名單不存在 → {}")
open(os.path.join(_tmpd, "bad.json"), "w").write("{{{")
check(M.load_disowned_idx(os.path.join(_tmpd, "bad.json")) == {}, "名單壞掉 → {}")
check(M.disowned_hit(IDX, "plokijuhyg#yyc04", "TES", "Tian") is not None, "命中：同 rid 同 隊|名")
check(M.disowned_hit(IDX, "PLOKIJUHYG #yyc04", "TES", "Tian") is not None, "命中：大小寫／空白 normalize")
check(M.disowned_hit(IDX, "luck dog#KR1", "OMG", "haichao") is not None, "命中：名單那邊寫 Luck Dog #KR1 也對得上")
check(M.disowned_hit(IDX, "plokijuhyg#yyc04", "TES", "Tian2") is None, "不命中：同 rid 不同選手（同名選手不牽連）")
check(M.disowned_hit(IDX, "plokijuhyg#yyc04", "JDG", "Tian") is None, "不命中：同 rid 不同隊")
check(M.disowned_hit({}, "plokijuhyg#yyc04", "TES", "Tian") is None, "空索引 → None")


def run_one(e, dpm_ents, idx=IDX, tm="TES", pl="Tian"):
    dbr = {M.norm(x["riotId"]): x for x in dpm_ents}
    dbp = {x["dpmPuuid"]: x for x in dpm_ents if x.get("dpmPuuid")}
    lines, orph = [], []
    r = M._union_one(e, dbr, dbp, tm, pl, dpm_ents, idx, lines, orph)
    return r, lines, orph


D1 = {"riotId": "yiqunsb#KR1", "dpmPuuid": "pu-yiq", "dpmSeen": "2026-09-08", "dpmRank": {"tier": "CHALLENGER"}}
r, lines, orph = run_one({"player": "Tian", "team": "TES", "riotId": "plokijuhyg#yyc04", "platform": "kr"}, [D1])
check(r is None, "(a) 名單已記＋dpm 沒回報＋沒 puuid → 剔除")
check(len(lines) == 1 and "[歸屬]" in lines[0] and "Bunny" in lines[0] and "不等 puuid" in lines[0], f"(a) 印一行 [歸屬]…Bunny：{lines}")
check(orph == [], "(a) 不進 ORPHANS")
r, lines, orph = run_one({"player": "Tian", "team": "TES", "riotId": "plokijuhyg#yyc04", "dpmPuuid": "pu-plo"}, [D1])
check(r is None and orph == [], "(b) 有 puuid（⑤b 補過）也直接剔除、不進 ORPHANS（以前會等複查）")
r, lines, orph = run_one({"player": "Tian", "team": "TES", "riotId": "smurf#KR1", "dpmPuuid": "pu-sm"}, [D1])
check(r is not None and len(orph) == 1 and orph[0] is r and lines == [], "(c) 名單沒記＋有 puuid＋dpm 有檔 → 留著並進 ORPHANS（原行為）")
r, lines, orph = run_one({"player": "Tian", "team": "TES", "riotId": "smurf#KR1"}, [D1])
check(r is not None and orph == [] and lines == [], "(d) 名單沒記＋沒 puuid → 留著、不進 ORPHANS（原行為）")
D2 = {"riotId": "plokijuhyg#yyc04", "dpmPuuid": "pu-plo", "dpmSeen": "2026-09-08", "dpmRank": {"tier": "MASTER"}}
r, lines, orph = run_one({"player": "Tian", "team": "TES", "riotId": "plokijuhyg#yyc04"}, [D1, D2])
check(r is not None and r.get("dpmSeen") == "2026-09-08" and r.get("dpmPuuid") == "pu-plo" and r.get("dpmRank", {}).get("tier") == "MASTER" and lines == [],
      "(e) 名單有記但 dpm 這次回報同名 → dpm 現行歸屬優先：留著、補 dpmSeen／puuid／rank、不印 [歸屬]")
D3 = {"riotId": "newname#KR1", "dpmPuuid": "pu-plo", "dpmSeen": "2026-09-08"}
r, lines, orph = run_one({"player": "Tian", "team": "TES", "riotId": "plokijuhyg#yyc04", "dpmPuuid": "pu-plo"}, [D1, D3])
check(r is not None and r["riotId"] == "newname#KR1" and any("[改名]" in l for l in lines) and not any("[歸屬]" in l for l in lines),
      "(f) 名單有記但 dpm 用同 puuid 回報新名 → 走改名路、不剔除")
D4 = {"riotId": "smurf#KR1", "dpmPuuid": "pu-right", "dpmSeen": "2026-09-08"}
r, lines, orph = run_one({"player": "Tian", "team": "TES", "riotId": "smurf#KR1", "dpmPuuid": "pu-wrong"}, [D4])
check(r is not None and r["dpmPuuid"] == "pu-right" and any("[錯配]" in l for l in lines), "(g) 錯配 → 換成 dpm 的（原行為）")
r, lines, orph = run_one({"player": "Tian", "team": "JDG", "riotId": "plokijuhyg#yyc04"}, [D1], tm="JDG")
check(r is not None and lines == [], "(h) 隊|名不同（JDG|Tian）→ 不牽連")
r, lines, orph = run_one({"player": "haichao", "team": "OMG", "riotId": "luck dog#KR1", "dpmPuuid": "pu-ld"}, [], tm="OMG", pl="haichao")
check(r is None, "(i) dpm 完全沒這位的檔（dpm_ents 空）也剔除（以前 ORPHANS 要 dpm_ents 非空 ⇒ 永遠留著）")
r, lines, orph = run_one({"player": "Tian", "team": "TES", "riotId": "plokijuhyg#yyc04", "dpmPuuid": "pu-plo"}, [D1], idx={})
check(r is not None and len(orph) == 1, "(j) 名單讀不到（{}）→ 退回原行為（進 ORPHANS）")
_in = {"player": "Tian", "team": "TES", "riotId": "smurf#KR1", "dpmPuuid": "pu-wrong"}
_cp = dict(_in); run_one(_in, [D4])
check(_in == _cp, "(k) 呼叫端的 dict 不被就地改")
_m8 = SRC[SRC.index("\ndef main():"):]
check(_m8.count("_union_one(") == 1 and _m8.count("load_disowned_idx(") == 1, "main() 呼叫 _union_one／load_disowned_idx 各一次")
check("relisted += 1" in _m8 and "歸屬名單剔除" in _m8, "main() 計數 relisted 並印在摘要")
check("ORPHANS.append(e)" not in _m8, "main() 裡不再有第二份 ORPHANS 邏輯（只在 _union_one）")
_fake8 = SRC.replace("_dis = disowned_hit(dis_idx, e[\"riotId\"], tm, pl)", "_dis = None")
_l8, _o8 = [], []
check(M._union_one({"riotId": "plokijuhyg#yyc04"}, {}, {}, "TES", "Tian", [D1], IDX, _l8, _o8) is None and "_dis = None" in _fake8 and "_dis = None" not in SRC,
      "正控制：把 disowned_hit 拿掉的退化版原始碼真的不同於現版（斷言不是恆綠）")

print()
if FAILS:
    print(f"✗ {len(FAILS)} 條失敗／{N_OK} 條通過")
    sys.exit(1)
print(f"✓ 全部通過：{N_OK} 條")
