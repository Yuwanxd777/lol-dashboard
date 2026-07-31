# -*- coding: utf-8 -*-
"""用 Leaguepedia 權威資料，把「同 ID 其實是不同人」的選手拆開。

背景：OE（Oracle's Elixir）比賽資料只有選手顯示 ID，沒有唯一識別，所以
build_career.py 用名字當 key 時，同 ID 的不同人會被合併成一份生涯。
Leaguepedia 的 ScoreboardPlayers.Link 是唯一選手頁（例：Uzi (Jian Zi-Hao)
vs Uzi (Lê Thanh Hà)），可以用 (顯示名, 隊伍) 對回唯一人。

**為什麼不用 action=cargoquery**：Cargo API 對匿名存取限流極兇，第一發就
被擋。改走 Special:CargoExport（一般頁面請求），先造訪頁面拿 cookie 再查，
實測穩定且不吃 Cargo 限流——同 fetch_wiki_mh.py 的繞法。

用法：
  python scripts/fetch_player_ids.py                 # 查 check_player_dup 報出的可疑名單
  python scripts/fetch_player_ids.py Uzi Knight      # 只查指定名字
  python scripts/fetch_player_ids.py --force         # 忽略快取重查
輸出：scripts/player_disambig.json（人工可再編輯；本腳本只覆寫查得到的條目）
"""
import io, json, os, re, sys, time, urllib.parse, urllib.request, http.cookiejar, collections

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "player_disambig.json")
DUP = os.path.join(ROOT, "csv_cache", "player_dup.json")
CACHE = os.path.join(ROOT, "csv_cache", "lpedia_players")
FORM = "https://lol.fandom.com/wiki/Special:CargoExport"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      "Accept-Language": "en-US,en;q=0.9", "Referer": FORM, "Upgrade-Insecure-Requests": "1"}
GAP = 8.0          # 頁面請求間隔（禮貌節流）
BATCH = 8          # 一次查幾個名字（URL 長度與 500 列上限的折衷）
_OP = None


def norm_link(lk):
    """選手頁正規化：wiki 連結底線＝空格，同一頁會兩種寫法都出現
    （例：Leo (Han Gyeo-re) 與 Leo_(Han_Gyeo-re)），不併會被當成兩個人。"""
    return re.sub(r"\s+", " ", lk.replace("_", " ")).strip()


def norm_team(t):
    """隊名正規化後比對：OE 與 Leaguepedia 的寫法常有差
    （GiantX/GIANTX、CERBERUS Esports/CERBERUS Esports (Vietnamese Team)）。
    只做大小寫與贅字，不做改名對照（Top Esports↔Topsports Gaming 這種要人工）。"""
    t = re.sub(r"\s*\([^)]*\)\s*$", "", str(t))          # 去尾括號註記
    t = re.sub(r"\b(e-?sports?|gaming|club|team)\b", "", t, flags=re.I)
    return re.sub(r"[^a-z0-9]", "", t.lower())


def team_match(oe, lp_teams):
    """OE 隊名能不能對到這個人格的某支隊（正規化後相等或互為前綴）"""
    a = norm_team(oe)
    if not a:
        return False
    for t in lp_teams:
        b = norm_team(t)
        if b and (a == b or a.startswith(b) or b.startswith(a)):
            return True
    return False


def merge_same(per):
    """把其實是同一人的人格併起來：LP 有改名重導，同一人會有兩個頁面
    （例：Raven (Kenneth Goh) 與 Raven (Kenneth Goh Kai Yang)），
    判準＝隊伍集合完全相同，且其中一個 link 是另一個的前綴。"""
    keys = sorted(per, key=lambda k: (-per[k]["n"], k))
    drop = {}
    for i, a in enumerate(keys):
        if a in drop:
            continue
        for b in keys[i + 1:]:
            if b in drop:
                continue
            ta, tb = set(per[a]["teams"]), set(per[b]["teams"])
            if not ta or ta != tb:
                continue
            sa, sb = a.split(" (", 1)[-1].rstrip(")"), b.split(" (", 1)[-1].rstrip(")")
            if sa.startswith(sb) or sb.startswith(sa):
                drop[b] = a
    for b, a in drop.items():
        for t, c in per[b]["teams"].items():
            per[a]["teams"][t] = max(per[a]["teams"].get(t, 0), c)
        per[a]["n"] = max(per[a]["n"], per[b]["n"])
        per[a]["f"] = min(per[a]["f"], per[b]["f"])
        per[a]["l"] = max(per[a]["l"], per[b]["l"])
        del per[b]
    return per, drop


def opener():
    """先造訪頁面拿 cookie——不帶 cookie 會 403"""
    global _OP
    if _OP is None:
        cj = http.cookiejar.CookieJar()
        _OP = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        try:
            _OP.open(urllib.request.Request(FORM, headers=UA), timeout=60).read()
            time.sleep(2)
        except Exception as e:
            print(f"  ⚠ 取 cookie 失敗（仍試著繼續）：{type(e).__name__}")
    return _OP


def export(names):
    """查一批名字 → [{nm,lk,tm,n,f,l}]

    三個條件都要：OE 的顯示 ID 與 Leaguepedia 的不一定一致（例：OE 寫 Amazing，
    LP 那位中國選手的頁面是 Amazing (Liu Shi-Yu) 但比賽顯示名不是 Amazing），
    只靠 Name 會漏掉整個人格，那些場次就會被錯歸給主人格。
    """
    def cond(n):
        e = n.replace('"', '\\"')
        return f'SP.Name="{e}" OR SP.Link="{e}" OR SP.Link LIKE "{e} (%"'
    q = " OR ".join("(%s)" % cond(n) for n in names)
    p = {"tables": "ScoreboardPlayers=SP",
         "fields": "SP.Name=nm,SP.Link=lk,SP.Team=tm,COUNT(*)=n,"
                   "MIN(SP.DateTime_UTC)=f,MAX(SP.DateTime_UTC)=l",
         "where": q, "group_by": "SP.Name,SP.Link,SP.Team",
         "order_by": "SP.Name", "format": "json", "limit": "500"}
    url = FORM + "?" + urllib.parse.urlencode(p)
    op = opener()
    for a in range(4):
        try:
            raw = op.open(urllib.request.Request(url, headers=UA), timeout=60).read().decode("utf-8", "replace")
        except Exception as e:
            print(f"    ⚠ 第 {a+1} 次失敗（{type(e).__name__}），退避重試…")
            time.sleep(15 * (a + 1)); continue
        if raw.lstrip()[:1] not in "[{":
            print(f"    ⚠ 非 JSON 回應，退避重試…")
            time.sleep(15 * (a + 1)); continue
        try:
            return json.loads(raw)
        except Exception:
            time.sleep(15 * (a + 1))
    print("    ✗ 這批查詢放棄")
    return []


def oe_teams(names):
    """從 check_player_dup 的明細取得每個名字在 OE 資料裡的隊伍，用來比對覆蓋率"""
    if not os.path.exists(DUP):
        return {}
    try:
        rows = json.load(open(DUP, encoding="utf-8"))["rows"]
    except Exception:
        return {}
    out = {}
    for r in rows:
        if r["name"] in names:
            t = collections.Counter()
            for s in r["segs"]:
                t[s["tm"]] += s["n"]
            out[r["name"]] = t
    return out


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    if argv:
        names = argv
    else:
        if not os.path.exists(DUP):
            print("找不到 csv_cache/player_dup.json —— 請先跑：")
            print("  python scripts/check_player_dup.py --json csv_cache/player_dup.json")
            return 1
        names = [r["name"] for r in json.load(open(DUP, encoding="utf-8"))["rows"]]
    print(f"要查 {len(names)} 個名字：{'、'.join(names[:12])}{' …' if len(names) > 12 else ''}\n")

    os.makedirs(CACHE, exist_ok=True)
    got = {}
    todo = []
    for n in names:
        cp = os.path.join(CACHE, re.sub(r"[^A-Za-z0-9_-]", "_", n) + ".json")
        if os.path.exists(cp) and not force:
            try:
                got[n] = json.load(open(cp, encoding="utf-8")); continue
            except Exception:
                pass
        todo.append(n)
    if got:
        print(f"（{len(got)} 個用快取）")

    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        print(f"  查詢 {i//BATCH+1}/{(len(todo)+BATCH-1)//BATCH}：{'、'.join(batch)}")
        rows = export(batch)
        for n in batch:
            # 一列屬於名字 n 的條件：顯示名相符，或選手頁就是 n／n (消歧)
            got[n] = [x for x in rows
                      if str(x.get("nm") or "") == n
                      or norm_link(str(x.get("lk") or "")) == n
                      or norm_link(str(x.get("lk") or "")).startswith(n + " (")]
            cp = os.path.join(CACHE, re.sub(r"[^A-Za-z0-9_-]", "_", n) + ".json")
            json.dump(got[n], open(cp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        if i + BATCH < len(todo):
            time.sleep(GAP)

    # 既有表：只覆寫本次查到的條目，人工加的註記保留
    old = {}
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT, encoding="utf-8"))
        except Exception as e:
            print(f"⚠ 舊表讀取失敗，將重建：{e}")
    oet = oe_teams(set(names))

    out = dict(old)
    out.setdefault("_readme", {
        "用途": "同 ID 但不同人的選手拆分表。build_career.py 讀本表，把 (隊伍,名字) 對到正確的人。",
        "persons": "依總場次多→少排序；第一個是主人格，key 沿用原名，前端沒改也不會壞。",
        "teams": "該人格在 OE 資料裡用過的隊名。沒列到的隊伍一律歸主人格（安全預設）。",
        "reviewed": "填了這欄＝人工確認是同一人（誤報），check_player_dup 就不再報。",
        "來源": "scripts/fetch_player_ids.py 由 Leaguepedia ScoreboardPlayers.Link 產生；可人工編輯。",
    })
    nsplit = nsingle = nmiss = 0
    report = []
    for n in names:
        rows = got.get(n) or []
        if not rows:
            nmiss += 1
            report.append((n, "查無", []))
            continue
        # Link → 隊伍集合、場次
        per = collections.defaultdict(lambda: {"n": 0, "teams": {}, "f": "9999", "l": ""})
        for x in rows:
            lk = norm_link(str(x.get("lk") or ""))
            if not lk:
                continue
            e = per[lk]
            c = int(x.get("n") or 0)
            e["n"] += c
            tm = str(x.get("tm") or "").strip()
            if tm:
                e["teams"][tm] = e["teams"].get(tm, 0) + c
            f, l = str(x.get("f") or "")[:10], str(x.get("l") or "")[:10]
            if f and f < e["f"]:
                e["f"] = f
            if l > e["l"]:
                e["l"] = l
        per, merged = merge_same(dict(per))
        if merged:
            print(f"    ↺ {n}：合併重導頁 " + "、".join(f"{b} → {a}" for b, a in merged.items()))
        if len(per) <= 1:
            nsingle += 1
            lk = next(iter(per)) if per else ""
            prev = old.get(n) if isinstance(old.get(n), dict) else {}
            ent = {k: v for k, v in prev.items() if k not in ("persons",)}
            ent["reviewed"] = f"Leaguepedia 只有一位（{lk}）→ 同一人，誤報"
            ent["link"] = lk
            out[n] = ent
            report.append((n, "同一人", [lk]))
            continue
        nsplit += 1
        prev = old.get(n) if isinstance(old.get(n), dict) else {}
        # teams_add＝人工補的隊名對照（OE 與 LP 隊名不同時用；本腳本不覆寫它）
        add = prev.get("teams_add") or {}
        oc = oet.get(n) or {}

        def oe_games(lk, e):
            tl = list(e["teams"]) + list(add.get(lk) or [])
            return sum(c for t, c in oc.items() if team_match(t, tl))

        # 主人格＝在「我們的 OE 資料」裡出賽最多的那位，不是 LP 場次最多的。
        # 主人格的 key 沿用原名，若挑到一位 OE 根本沒出賽的人，career.p[原名]
        # 就會不存在，前端查生涯直接變 0 場——比不拆還糟。
        order = sorted(per.items(), key=lambda kv: (-oe_games(kv[0], kv[1]), -kv[1]["n"], kv[0]))
        persons = []
        for i, (lk, e) in enumerate(order):
            p = {"key": n if i == 0 else lk, "link": lk,
                 "teams": sorted(e["teams"], key=lambda t: -e["teams"][t]),
                 "games_lp": e["n"], "games_oe": oe_games(lk, e),
                 "first": e["f"], "last": e["l"]}
            if add.get(lk):
                p["teams_oe_manual"] = list(add[lk])
            persons.append(p)
        ent = {k: v for k, v in prev.items() if k != "reviewed"}
        ent["persons"] = persons
        ent["source"] = "leaguepedia"
        out[n] = ent
        # OE 有、但 LP 任何人格都沒列到的隊伍 → 會被歸主人格（＝維持現狀，不會更糟），
        # 但若那支隊其實屬於次人格就仍是錯的，所以列出來讓人工確認
        lpteams = [t for p in persons for t in list(p["teams"]) + list(p.get("teams_oe_manual") or [])]
        unknown = [t for t in (oet.get(n) or {}) if not team_match(t, lpteams)]
        if unknown:
            ent["_未對應隊伍"] = {t: (oet.get(n) or {}).get(t, 0) for t in unknown}
        else:
            ent.pop("_未對應隊伍", None)
        report.append((n, f"拆成 {len(persons)} 人", [p["link"] for p in persons]))

    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n{'='*66}")
    for n, st, lks in report:
        print(f"  {n:<12} {st:<10} {'｜'.join(lks)}")
    print(f"{'='*66}")
    print(f"拆分 {nsplit}　同一人（誤報）{nsingle}　查無 {nmiss}")
    print(f"→ {OUT}")
    print("\n下一步：python scripts/build_career.py 重建生涯（會套用本表）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
