# -*- coding: utf-8 -*-
"""fetch_obgg_accounts 的「同一個人換隊 ⇒ 隊碼留舊的，交給比賽資料決定」沙盒測試（2026-11-22 精進迴圈 #3539，不打網路）。

為什麼：轉會期 OBGG 名冊先換隊（Zeus → T1），⑤ fetch_dpm_soloq_accounts 的「轉隊改隊碼」卻照比賽資料改回 HLE；
兩支各拉各的 ⇒ 隔班輪流出現「同一人兩個鍵＋新鍵沒有逐場檔 ⇒ 補全年」（11-21 22:00 班 7 位 5159 場 341 秒）。
細節見 fetch_obgg_accounts.py 檔頭 MATCH_DATA_REL 那段。

沙盒：pull() 換成假資料、urlopen／HTTPSConnection 換成會炸的 stub；ACCOUNTS／OUT／ROSTER_OUT／DISOWNED 全指到暫存目錄，
比賽資料路徑由 ACCOUNTS 推（<暫存>/data/data_2026.js）⇒ 一起被接管；leaks() 抓模組層還指著真實 repo 的路徑。
[3] 的「⑤ 那一步」是**模型**（真的那支要瀏覽器與 dpm）：只照抄它的兩條規則——轉隊改隊碼（比賽資料唯一一隊、帳號檔同名只有一隊才改）
與 union（dpm 依選手名回同一批帳號，名單上每個鍵各補滿）。正控制＝功能關掉時模型要重現日誌裡那個兩班一輪的翻面。
用法：python scripts/fetch_obgg_keepteam_test.py
"""
import io, os, re, sys, json, datetime, tempfile, contextlib, importlib.util

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

# ── 斷網 ─────────────────────────────────────────────────────────────────────
class NoNet:
    def __init__(self, *a, **k):
        raise AssertionError("測試打到真實網路：http.client.HTTPSConnection(%s)" % (a[0] if a else "?"))
def no_urlopen(*a, **k):
    raise AssertionError("測試打到真實網路：urllib.request.urlopen")
M.urllib.request.urlopen = no_urlopen
M.http.client.HTTPSConnection = NoNet

# ── 沙盒路徑 ─────────────────────────────────────────────────────────────────
TMP = tempfile.mkdtemp(prefix="obgg_keepteam_")
os.makedirs(os.path.join(TMP, "scripts")); os.makedirs(os.path.join(TMP, "data")); os.makedirs(os.path.join(TMP, "csv_cache"))
REAL_ACC = os.path.join(M.HERE, "soloq_accounts.json")
REAL_DATA = os.path.join(M.ROOT, "data", "data_2026.js")
REAL_FILES = [p for p in (REAL_ACC, REAL_ACC + ".bak", REAL_DATA,
                          os.path.join(M.ROOT, "csv_cache", "soloq_disowned.json"),
                          os.path.join(M.ROOT, "csv_cache", "obgg_roster.json"),
                          os.path.join(M.ROOT, "csv_cache", "obgg_progamer_cache.json")) if os.path.exists(p)]
REAL_MT = {p: os.stat(p).st_mtime for p in REAL_FILES}
check_real_default = os.path.normcase(M.match_data_path()) == os.path.normcase(REAL_DATA)   # 接管前：預設要指到 ⑤ 讀的同一個檔
M.ACCOUNTS = M.OUT = os.path.join(TMP, "scripts", "acc.json")
M.ROSTER_OUT = os.path.join(TMP, "csv_cache", "roster.json")
M.DISOWNED = os.path.join(TMP, "csv_cache", "disowned.json")
M.PG_CACHE_ON = False
DATA = os.path.join(TMP, "data", "data_2026.js")

def leaks():
    return {k: v for k, v in vars(M).items()
            if isinstance(v, str) and v.endswith((".json", ".txt", ".csv", ".js"))
            and os.path.isabs(v) and not v.startswith(TMP)}

def write_data(rows, path=DATA):
    """rows＝[(participantid, 藍方選手, 紅方選手)]"""
    hdr = ["participantid", "blue_playername", "red_playername"]
    open(path, "w", encoding="utf-8").write(
        "window.LOL_DATA=" + json.dumps({"tabs": {"RAW_DATA": [hdr] + [list(r) for r in rows]}}, ensure_ascii=False) + ";\n")

print("[0] 沙盒守則")
check("接管前 match_data_path() 指到真實 data/data_2026.js（跟 ⑤ 同一個檔）", check_real_default)
check("接管後 match_data_path() 在暫存目錄（跟著 ACCOUNTS 走，不必另外接管）",
      M.match_data_path().startswith(TMP) and os.path.normcase(M.match_data_path()) == os.path.normcase(DATA), M.match_data_path())
check("模組層沒有指向真實 repo 的路徑", not leaks(), leaks())
_sv = M.DISOWNED; M.DISOWNED = os.path.join(M.ROOT, "csv_cache", "soloq_disowned.json")
check("正控制：把 DISOWNED 指回真實名單，leaks() 抓得到", "DISOWNED" in leaks())
M.DISOWNED = _sv
dpm_src = open(os.path.join(HERE, "fetch_dpm_soloq_accounts.py"), encoding="utf-8").read()
check("⑤ 讀的也是 data/" + M.MATCH_DATA_REL[-1] + "（年份兩支要一起改）",
      M.MATCH_DATA_REL == ("data", "data_2026.js") and dpm_src.count('"data", "data_2026.js"') >= 2)

print("[1] match_names：誰算今年有出場")
check("沒有比賽資料檔 → None（＝功能關掉）", M.match_names() is None)
write_data([(1, "Zeus", "Doran"), (5, "Keria", "Kael (VN)"), (100, "TeamRowBlue", "TeamRowRed"), ("x", "Bad", "Row"), (3, "", "Canyon")])
MN = M.match_names()
check("participantid 1~5 的藍紅選手都收、名字 norm（小寫去空白）", MN == {"zeus", "doran", "keria", "kael(vn)", "canyon"}, MN)
check("隊伍列（participantid 100）與壞列不收", "teamrowblue" not in MN and "bad" not in MN)
open(DATA, "w", encoding="utf-8").write("window.LOL_DATA={{{ not json")
check("檔壞掉 → None（不炸）", M.match_names() is None)
write_data([])
check("沒有任何選手列 → None", M.match_names() is None)

print("[2] keep_known_team 單元")
def E(team, player, rid, **k):
    d = {"player": player, "team": team, "platform": "kr", "riotId": rid}; d.update(k); return d
PLAYED = {"zeus", "doran", "morgan", "erha", "kael"}
acc = [E("HLE", "Zeus", "Athene#lll", dpmPuuid="pu1"), E("HLE", "Zeus", "Austin#lll"), E("HLE", "Zeus", "Zimmer#god")]
new = [E("T1", "Zeus", "athene #LLL"), E("T1", "Zeus", "Austin#lll"), E("T1", "Zeus", "Brand New#KR1"), E("T1", "Faker", "Hide#KR1")]
mv = M.keep_known_team(new, acc, PLAYED)
check("換隊：回 {'T1|Zeus': 'HLE'}", mv == {"T1|Zeus": "HLE"}, mv)
check("Zeus 三隻（含帳號檔沒有的新帳號）都改成 HLE；riotId 大小寫／空白不影響",
      [e["team"] for e in new if e["player"] == "Zeus"] == ["HLE"] * 3, [e["team"] for e in new])
check("同隊別人（Faker）不動", [e["team"] for e in new if e["player"] == "Faker"] == ["T1"])
new = [E("T1", "Zeus", "Athene#lll")]
check("played=None → 不做、回 {}", M.keep_known_team(new, acc, None) == {} and new[0]["team"] == "T1")
check("played=空集合 → 不做", M.keep_known_team(new, acc, set()) == {} and new[0]["team"] == "T1")
check("今年沒出場（TheShy 那種）→ 照 OBGG", M.keep_known_team(new, acc, {"doran"}) == {} and new[0]["team"] == "T1")
new = [E("T1", "Zeus", "Only New#KR1")]
check("沒有任何舊列（名冊新人／全新帳號）→ 照 OBGG", M.keep_known_team(new, acc, PLAYED) == {} and new[0]["team"] == "T1")
acc2 = acc + [E("T1", "Zeus", "Athene#lll")]
new = [E("T1", "Zeus", "Athene#lll"), E("T1", "Zeus", "Austin#lll")]
check("舊列分在兩隊（重複狀態）→ 不猜，照 OBGG", M.keep_known_team(new, acc2, PLAYED) == {} and {e["team"] for e in new} == {"T1"})
new = [E("T1", "Doran", "Athene#lll")]
check("同一隻帳號但舊列是別的選手名（OBGG 把帳號改掛別人）→ 不是同一人，照 OBGG",
      M.keep_known_team(new, acc, PLAYED) == {} and new[0]["team"] == "T1")
accm = [E("TL", "Morgan", "tl morgan#NA1")]
new = [E("BRO", "Morgan", "bro morgan#KR1")]
check("同名不同人（帳號不重疊）→ 不動", M.keep_known_team(new, accm, PLAYED) == {} and new[0]["team"] == "BRO")
new = [E("HLE", "Zeus", "Athene#lll")]
check("本來就同隊 → 不列進回傳", M.keep_known_team(new, acc, PLAYED) == {} and new[0]["team"] == "HLE")
acck = [E("GAM", "Kael (VN)", "kael#VN2")]
new = [E("TSW", "Kael (VN)", "kael#VN2")]
check("名字帶消歧義括號：去括號後有出場也算", M.keep_known_team(new, acck, PLAYED) == {"TSW|Kael (VN)": "GAM"} and new[0]["team"] == "GAM")

# ── 假 OBGG ─────────────────────────────────────────────────────────────────
def zone(teams):
    return {tm: {pl: [{"platform": "kr", "riotId": r} for r in rids] for pl, rids in ps.items()} for tm, ps in teams.items()}
TODAY = datetime.date.today().isoformat()
ZEUS = ["Athene#lll", "Austin#lll", "Zimmer#god"]          # dpm 選手檔的三隻；OBGG 只列前兩隻（11-21 實況）
def obgg_now(extra_t1=None):
    t1 = {"Zeus": ZEUS[:2]}; t1.update({f"k{i}": [f"kfill{i}#KR1"] for i in range(20)})
    if extra_t1: t1.update(extra_t1)
    return {"LPL": zone({"FIL": {f"f{i}": [f"fill{i}#KR1"] for i in range(20)}}),
            "LCK": zone({"T1": t1, "HLE": {"Kanavi": ["kanavi#KR1"]}})}

def run(acc, obgg, dis=None):
    assert not leaks(), f"沙盒沒接管到：{leaks()}"
    json.dump(acc, open(M.ACCOUNTS, "w", encoding="utf-8"), ensure_ascii=False)
    if os.path.exists(M.DISOWNED): os.remove(M.DISOWNED)
    if dis is not None: json.dump(dis, open(M.DISOWNED, "w", encoding="utf-8"), ensure_ascii=False)
    M.pull = lambda: (obgg, {})
    M.ROSTER_PLAYERS.clear()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        M.main()
    return json.load(open(M.OUT, encoding="utf-8")), buf.getvalue()

def step5_model(acc, match_team, dpm_accounts):
    """⑤ fetch_dpm_soloq_accounts 的模型：①轉隊改隊碼 ②union。回 (新帳號檔, 改鍵 {舊鍵:新鍵})。"""
    acc = [dict(a) for a in acc]
    teams = {}
    for a in acc: teams.setdefault(M.norm(a["player"]), set()).add(a["team"])
    rekey = {}
    for a in acc:
        n = M.norm(a["player"]); mt = match_team.get(n)
        if not mt or len(teams[n]) != 1 or a["team"] == mt:
            continue
        rekey[a["team"] + "|" + a["player"]] = mt + "|" + a["player"]; a["team"] = mt
    out = []; seen = set()
    for a in acc:                                # union：名單上每個 (選手,隊) 各補滿 dpm 回的那批帳號
        key = (a["player"], a["team"])
        if key in seen: continue
        seen.add(key)
        mine = [x for x in acc if (x["player"], x["team"]) == key]
        have = {M.norm(x["riotId"]) for x in mine}
        out += mine
        for rid in dpm_accounts.get(M.norm(a["player"]), []):
            if M.norm(rid) not in have:
                out.append({"player": a["player"], "team": a["team"], "platform": "kr", "riotId": rid, "dpmPuuid": "pu-" + M.norm(rid)})
        for x in out:
            if (x["player"], x["team"]) == key and M.norm(x["riotId"]) in {M.norm(r) for r in dpm_accounts.get(M.norm(a["player"]), [])}:
                x["dpmSeen"] = TODAY
    return out, rekey

def keys_of(acc, player): return sorted({a["team"] + "|" + a["player"] for a in acc if a["player"] == player})

def simulate(n_shifts, acc0):
    """跑 n 班「③ OBGG（真的 main()）→ ⑤ 模型」；回每班 (③ 之後的鍵, ⑤ 之後的鍵, ⑤ 的改鍵, 補全年的新鍵, ③ 的日誌)。"""
    acc = acc0; files = {"HLE|Zeus"}; hist = []
    for _ in range(n_shifts):
        a3, log = run(acc, obgg_now())
        a5, rekey = step5_model(a3, {"zeus": "HLE", "kanavi": "HLE"}, {"zeus": ZEUS, "kanavi": ["kanavi#KR1"]})
        files = {rekey.get(k, k) for k in files}
        fresh = sorted(k for k in keys_of(a5, "Zeus") if k not in files)     # 沒有逐場檔的鍵 ⇒ ⑤d 當新選手補全年
        files |= set(fresh)
        hist.append((keys_of(a3, "Zeus"), keys_of(a5, "Zeus"), rekey, fresh, log))
        acc = a5
    return hist

ACC_STABLE = [E("HLE", "Zeus", r, dpmPuuid="pu-" + M.norm(r), dpmSeen=TODAY) for r in ZEUS] \
           + [E("HLE", "Kanavi", "kanavi#KR1", dpmPuuid="pu-k", dpmSeen=TODAY)]

print("[3] 正控制：功能關掉（沒有比賽資料檔）⇒ 模型重現日誌裡兩班一輪的翻面")
if os.path.exists(DATA): os.remove(DATA)
H = simulate(4, ACC_STABLE)
check("第 1 班 ③ 之後同名兩隊（HLE 留 1 隻、T1 2 隻）", H[0][0] == ["HLE|Zeus", "T1|Zeus"], H[0][0])
check("第 1 班 ⑤「同名多隊不猜」⇒ 兩個鍵都留著、T1|Zeus 要補全年", H[0][1] == ["HLE|Zeus", "T1|Zeus"] and H[0][3] == ["T1|Zeus"], H[0][1:4])
check("第 2 班 ③ 去重後只剩 T1 ⇒ ⑤ 改回 HLE（改鍵 T1|Zeus→HLE|Zeus）、這班不補全年",
      H[1][0] == ["T1|Zeus"] and H[1][2].get("T1|Zeus") == "HLE|Zeus" and H[1][1] == ["HLE|Zeus"] and H[1][3] == [], H[1][:4])
check("第 3 班又回到第 1 班的狀態（T1|Zeus 再補一次全年）＝兩班一輪", H[2][:2] == H[0][:2] and H[2][3] == ["T1|Zeus"], H[2][:4])
check("四班裡補全年 2 次", sum(len(h[3]) for h in H) == 2, [h[3] for h in H])
check("功能關掉時日誌沒有「換隊不跟 OBGG」", all("換隊不跟 OBGG" not in h[4] for h in H))

print("[4] 功能開著（比賽資料：Zeus／Kanavi 今年有出場）⇒ 穩定在 HLE|Zeus、一次全年都不補")
write_data([(1, "Zeus", "Kanavi"), (2, "k0", "f0")])
H = simulate(4, ACC_STABLE)
check("每一班 ③ 之後都只有 HLE|Zeus", all(h[0] == ["HLE|Zeus"] for h in H), [h[0] for h in H])
check("每一班 ⑤ 之後都只有 HLE|Zeus、沒有改鍵、沒有補全年", all(h[1] == ["HLE|Zeus"] and not h[2] and not h[3] for h in H), [h[1:4] for h in H])
check("③ 的日誌點名 T1|Zeus→HLE", all("換隊不跟 OBGG" in h[4] and "T1|Zeus→HLE" in h[4] for h in H), H[0][4][-300:])
out, log = run(ACC_STABLE, obgg_now())
Z = [a for a in out if a["player"] == "Zeus"]
check("Zeus 三隻帳號都在、dpmPuuid 沿用", len(Z) == 3 and all(a.get("dpmPuuid") for a in Z), Z)
check("沒換隊的人不動（HLE|Kanavi、T1|k0）", keys_of(out, "Kanavi") == ["HLE|Kanavi"] and keys_of(out, "k0") == ["T1|k0"])
check("帳號總數不變（24+20 填充＋Zeus 3＋Kanavi 1）", len(out) == 44, len(out))

print("[5] 從現況的重複狀態（兩個鍵各 3 隻）出發 ⇒ 一班收斂、之後穩定")
ACC_DUP = [E("T1", "Zeus", r, dpmPuuid="pu-" + M.norm(r), dpmSeen=TODAY) for r in ZEUS] + ACC_STABLE
H = simulate(3, ACC_DUP)
check("第 1 班：③ 不猜（照 OBGG 去重成 T1）→ ⑤ 改回 HLE", H[0][0] == ["T1|Zeus"] and H[0][1] == ["HLE|Zeus"], H[0][:3])
check("第 2、3 班穩定在 HLE|Zeus", all(h[0] == ["HLE|Zeus"] and h[1] == ["HLE|Zeus"] and not h[3] for h in H[1:]), [h[:4] for h in H[1:]])
check("三班都不補全年", sum(len(h[3]) for h in H) == 0)

print("[6] 改完隊碼再問一次歸屬名單（名單只認 隊|名，OBGG 的新隊問不到舊鍵底下記過的）")
DIS = [{"rid": "Stolen#KR1", "from": "HLE|Zeus", "owner": "Somebody", "why": "dpm 掛牌", "at": "2026-11-20 22:05"}]
ob = obgg_now(); ob["LCK"]["T1"]["Zeus"].append({"platform": "kr", "riotId": "Stolen#KR1"})
out, log = run(ACC_STABLE, ob, DIS)
check("Stolen#KR1 沒被補回、其餘三隻都在 HLE|Zeus", "stolen#kr1" not in {M.norm(a["riotId"]) for a in out} and keys_of(out, "Zeus") == ["HLE|Zeus"])
check("日誌有 [歸屬] HLE|Zeus … 不從 OBGG 補回、摘要略過 1 隻", "[歸屬] HLE|Zeus: Stolen#KR1" in log and "歸屬名單略過 1 隻" in log, log[-400:])
os.remove(DATA)
out, log = run(ACC_STABLE, ob, DIS)
check("正控制：功能關掉 ⇒ Stolen#KR1 被掛到 T1|Zeus 補回（舊行為）",
      any(M.norm(a["riotId"]) == "stolen#kr1" and a["team"] == "T1" for a in out) and "[歸屬]" not in log)

print("[7] 真實檔一個都沒動、原始碼位置")
for p in REAL_FILES:
    check(f"{os.path.relpath(p, ROOT)} mtime 不變", os.stat(p).st_mtime == REAL_MT[p])
src = open(SRC, encoding="utf-8").read()
m = src[src.index("\ndef main():"):]
check("main() 呼叫 keep_known_team(new, acc, match_names()) 一次", m.count("keep_known_team(new, acc, match_names())") == 1)
check("呼叫點在 prune_old 之前（new_rids 要用改完、剔完的 new）", m.index("keep_known_team(") < m.index("new_rids = ") < m.index("prune_old(acc, new"))
check("比賽資料路徑沒有做成模組層絕對路徑常數", not re.search(r'^[A-Z_]+ = os\.path\.join\(ROOT, "data"', src, re.M))

print(f"\n結果：✓ {OK}　✗ {FAIL}")
sys.exit(1 if FAIL else 0)
