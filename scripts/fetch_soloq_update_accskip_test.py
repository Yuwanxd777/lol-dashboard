# -*- coding: utf-8 -*-
"""⑤d 逐帳號跳過「牌位沒動」的帳號（2026-09-07 線 3，精進迴圈 #23）——離線：不打網路、不開瀏覽器。
① fetch_soloq.acc_static_keys：誰算靜止、誰不算（含改名 curId、同鍵兩數字、found=False）
② fetch_soloq_update.acc_static_from：名單缺／壞／垃圾 → 空集合＝全查
③ split_static_accounts：只跳靜止、順序保留；負控制：static 空 → 全查
④ 兩支的 acc_key 逐案一致；原始碼位置（main 真的用到、日誌真的會印）
⑤ 真資料：現行 soloq.js vs git 前一版（083c0749）重算，靜止帳號要 0 < n < 全部；每一個都用獨立查法再驗 W+L 相同；
   把其中一個帳號的 wins +1 → 只有它從名單消失（正控制）
用法：python scripts/fetch_soloq_update_accskip_test.py
"""
import os, sys, io, re, json, subprocess, importlib.util

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
def load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
os.environ.setdefault("RIOT_API_KEY", "TEST")   # fetch_soloq.py 模組層沒金鑰就 exit；這裡離線，給假的（跟 fetch_soloq_404_test 同法）
S = load("fsq", "fetch_soloq.py")
U = load("fsu", "fetch_soloq_update.py")

OK = FAIL = 0
def check(name, cond, info=""):
    global OK, FAIL
    if cond: OK += 1; print(f"  ✓ {name}")
    else: FAIL += 1; print(f"  ✗ {name}  {info}")

def row(rid, plat, w, l, cur=None, found=True):
    return {"riotId": rid, "platform": plat, "wins": w, "losses": l, "curId": cur or rid, "found": found}

print("[1] fetch_soloq.acc_static_keys：誰算靜止")
prev = [row("Faker#KR1", "kr", 100, 80), row("Zeus#glgl", "kr", 50, 50, cur="Athene#lll"), row("X#1", "euw1", 10, 10),
        row("Y#2", "na1", 5, 5), row("Z#3", "br1", None, None, found=False), row("Dup#9", "kr", 1, 1), row("Dup#9", "kr", 2, 2)]
now = [row("faker#kr1 ", "KR", 100, 80),                # 大小寫／空白不同 → 同一把鍵
       row("Athene#lll", "kr", 50, 50),                 # 改名同步後帳號檔已是 curId → 靠 prev 的 curId 鍵對上
       row("X#1", "euw1", 11, 10),                      # 勝 +1 → 不靜止
       row("Y#2", "na1", 5, 6),                         # 敗 +1 → 不靜止
       row("Z#3", "br1", None, None, found=False),      # 兩版都查不到牌位 → 不算（第一階段只跳「都有牌位」的）
       row("New#0", "jp1", 3, 3),                       # 上一版沒有 → 不靜止
       row("Dup#9", "kr", 1, 1), row("Dup#9", "kr", 1, 1),   # 同鍵兩列數字相同 → 可靜止（prev 兩列不同 → prev=None → 不靜止）
       row("Gone#7", "kr", 0, 0)]                       # prev 沒有 → 不靜止
st = S.acc_static_keys(prev, now)
check("大小寫／空白不同仍算同一帳號 → 靜止", "faker#kr1@kr" in st, st)
check("改名（prev curId＝now riotId）→ 靜止", "athene#lll@kr" in st, st)
check("prev 的舊名 zeus#glgl 不在 now → 不出現", "zeus#glgl@kr" not in st, st)
check("勝 +1 → 不靜止", "x#1@euw1" not in st, st)
check("敗 +1 → 不靜止", "y#2@na1" not in st, st)
check("兩版都 found=False（wins/losses 皆 None）→ 不靜止", "z#3@br1" not in st, st)
check("上一版沒有 → 不靜止", "new#0@jp1" not in st and "gone#7@kr" not in st, st)
check("prev 同鍵兩個數字 → 不靜止", "dup#9@kr" not in st, st)
check("結果排序且不重複", st == sorted(set(st)), st)
check("只剩兩把鍵", set(st) == {"faker#kr1@kr", "athene#lll@kr"}, st)
check("負控制：prev 空 → []", S.acc_static_keys([], now) == [])
check("負控制：now 空 → []", S.acc_static_keys(prev, []) == [])
check("負控制：now 全部 +1 → []", S.acc_static_keys(prev, [dict(r, wins=(r["wins"] or 0) + 1) for r in prev]) == [])
check("正控制：prev 與 now 同一份 → 每個有牌位、鍵不撞的帳號都靜止",
      set(S.acc_static_keys(prev, prev)) == {"faker#kr1@kr", "zeus#glgl@kr", "athene#lll@kr", "x#1@euw1", "y#2@na1"},
      S.acc_static_keys(prev, prev))

print("[2] fetch_soloq_update.acc_static_from：名單形狀")
check("缺鍵 → 空集合", U.acc_static_from({"played": ["A|a"]}) == set())
check("None → 空集合", U.acc_static_from({"acc_static": None}) == set())
check("不是 list（字串）→ 空集合", U.acc_static_from({"acc_static": "faker#kr1@kr"}) == set())
check("不是 dict → 空集合", U.acc_static_from(None) == set() and U.acc_static_from([1, 2]) == set())
check("list 裡的垃圾（數字／None／沒 @）被丟掉、其餘小寫化",
      U.acc_static_from({"acc_static": [1, None, "NoAt", " Faker#KR1@KR ", "x#1@euw1"]}) == {"faker#kr1@kr", "x#1@euw1"})
check("空 list → 空集合", U.acc_static_from({"acc_static": []}) == set())

print("[3] split_static_accounts：只跳靜止、順序保留")
accs = [{"riotId": "Faker#KR1", "platform": "kr"}, {"riotId": "X#1", "platform": "euw1"}, {"riotId": "Y#2", "platform": "na1"}]
todo, skip = U.split_static_accounts(accs, {"faker#kr1@kr", "y#2@na1"})
check("靜止的兩個進 skip、剩下進 todo", [a["riotId"] for a in todo] == ["X#1"] and [a["riotId"] for a in skip] == ["Faker#KR1", "Y#2"], (todo, skip))
check("負控制：static 空 → 全部 todo、skip 0", U.split_static_accounts(accs, set()) == (accs, []))
check("負控制：static 全對不上 → 全部 todo", U.split_static_accounts(accs, {"nobody@kr"}) == (accs, []))
check("全部靜止 → todo 空（這位選手一次 dpm 都不問）", U.split_static_accounts(accs, {"faker#kr1@kr", "x#1@euw1", "y#2@na1"})[0] == [])
check("空帳號列表 → ([], [])", U.split_static_accounts([], {"faker#kr1@kr"}) == ([], []))

print("[4] 兩支的 acc_key 一致；原始碼位置")
pairs = [("Faker#KR1", "kr"), (" faker#kr1", "KR "), ("Athene#lll", None), (None, "euw1"), ("", ""), ("多字節#中文", "tw2")]
check("acc_key 逐案相同", all(S.acc_key(a, b) == U.acc_key(a, b) for a, b in pairs))
check("acc_key 小寫＋去空白", S.acc_key(" Faker#KR1 ", "KR") == "faker#kr1@kr")
src_u = open(os.path.join(HERE, "fetch_soloq_update.py"), encoding="utf-8").read()
src_s = open(os.path.join(HERE, "fetch_soloq.py"), encoding="utf-8").read()
check("update：ACC_STATIC 只在 --changed 的 else 分支（scope=full）填入", "ACC_STATIC = acc_static_from(d)" in src_u
      and src_u.index("ACC_STATIC = set()") < src_u.index('if "--changed" in sys.argv:') < src_u.index("ACC_STATIC = acc_static_from(d)"))
check("update：逐人迴圈真的走 split_static_accounts → for a in _todo", "split_static_accounts(accs.get(key, []), ACC_STATIC)" in src_u and "for a in _todo:" in src_u)
check("update：印「⏭ 跳過 N 個牌位沒動的帳號」", "⏭ 跳過 %d 個牌位沒動的帳號" in src_u)
check("soloq：寫進 soloq_played.json 的是 acc_static", '"acc_static": acc_static' in src_s)
check("soloq：--active／--failed 不寫靜止名單", 'acc_static = [] if any(f in sys.argv for f in ("--active", "--failed"))' in src_s)
check("soloq：prev_players 給 acc_static_keys 用", "acc_static_keys(prev_players, out)" in src_s)

print("[5] 真資料：現行 soloq.js vs git 083c0749（22:00 那一輪的「上一版」）")
def parse_js(txt):
    return json.loads(re.search(r"=\s*(\{.*\});?\s*$", txt, re.S).group(1)).get("players", [])
try:
    prev_txt = subprocess.run(["git", "show", "083c0749:soloq.js"], cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8", "replace")
    now_txt = open(os.path.join(ROOT, "soloq.js"), encoding="utf-8").read()
    P, N = parse_js(prev_txt), parse_js(now_txt)
    st = S.acc_static_keys(P, N)
    n_now = sum(1 for p in N if p.get("wins") is not None or p.get("losses") is not None)
    print(f"   列數 prev {len(P)}／now {len(N)}；now 有牌位 {n_now}；靜止帳號 {len(st)}")
    check("靜止帳號 0 < n < now 有牌位的列數", 0 < len(st) < n_now, (len(st), n_now))
    # 獨立查法：riotId 與 curId 各當一把鍵直接查兩版 W+L（跟 acc_static_keys 不共用程式碼）
    def wl_map(rows):
        d = {}
        for p in rows:
            if p.get("wins") is None and p.get("losses") is None: continue
            plat = str(p.get("platform") or "").lower(); tot = (p.get("wins") or 0) + (p.get("losses") or 0)
            for rid in {str(p.get("riotId") or "").strip().lower(), str(p.get("curId") or "").strip().lower()} - {""}:
                d.setdefault((rid, plat), []).append(tot)
        return d
    pm, nm = wl_map(P), wl_map(N)
    bad = []
    for k in st:
        rid, plat = k.rsplit("@", 1)
        a, b = pm.get((rid, plat)), nm.get((rid, plat))
        if not a or not b or set(a) != set(b) or len(set(a)) != 1:
            bad.append((k, a, b))
    check("每個靜止帳號用獨立查法再驗：兩版 W+L 相同", not bad, bad[:5])
    # 22:00 真正進逐場的那批人：用同一對快照逐人重算（不讀 soloq_played.json——它會被別的步驟覆寫）
    def per_person(rows):
        d = {}
        for p in rows:
            if p.get("wins") is None and p.get("losses") is None: continue
            k = f'{p.get("team")}|{p.get("player")}'
            d[k] = d.get(k, 0) + (p.get("wins") or 0) + (p.get("losses") or 0)
        return d
    pp, npp = per_person(P), per_person(N)
    played_keys = [k for k in npp if k in pp and npp[k] != pp[k]]
    want = set(played_keys) | {k for k in npp if k not in pp}
    raw = json.load(open(os.path.join(HERE, "soloq_accounts.json"), encoding="utf-8"))
    accs = {}
    for a in raw:
        if a.get("bad") or not a.get("dpmPuuid"): continue
        accs.setdefault(f'{a.get("team","")}|{a.get("player","")}', []).append(a)
    tot = sk = 0
    for k in want:
        t_, s_ = U.split_static_accounts(accs.get(k, []), set(st)); tot += len(t_) + len(s_); sk += len(s_)
    print(f"   逐人 W+L 有變 {len(played_keys)} 位（22:00 日誌印 103）＋上一版沒有 {len(want) - len(played_keys)} 位 → 帳號 {tot} 個，其中牌位沒動可跳 {sk} 個（施工單估 100/315）")
    check("有動的選手裡確實有可跳的帳號（0 < 跳 < 全部）", 0 < sk < tot, (sk, tot))
    no_ask = [k for k in played_keys if accs.get(k) and not U.split_static_accounts(accs[k], set(st))[0]]
    check("W+L 有變的每一位至少留一個帳號要問 dpm（變的那一場才有人去抓）", not no_ask, no_ask[:5])
    # 正控制：把一個靜止帳號的 wins +1 → 只有它消失
    k0 = st[0]; rid0, plat0 = k0.rsplit("@", 1)
    N2 = [dict(p, wins=(p.get("wins") or 0) + 1) if (str(p.get("riotId") or "").strip().lower() == rid0 or str(p.get("curId") or "").strip().lower() == rid0) and str(p.get("platform") or "").lower() == plat0 else p for p in N]
    st2 = S.acc_static_keys(P, N2)
    check("正控制：其中一個帳號 wins +1 → 只有它從名單消失", k0 not in st2 and set(st) - set(st2) == {k0} and len(st2) == len(st) - 1, (len(st), len(st2)))
except subprocess.CalledProcessError as e:
    check("git show 083c0749:soloq.js 讀得到", False, e.stderr.decode("utf-8", "replace")[:200])

print(f"\n結果：✓ {OK}　✗ {FAIL}")
sys.exit(1 if FAIL else 0)
