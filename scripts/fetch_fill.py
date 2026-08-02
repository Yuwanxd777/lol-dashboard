# -*- coding: utf-8 -*-
"""OE 未收錄賽段的應急補資料（gol.gg → OE CSV 格式 → fetch_data.process() → RAW_DATA 相容列）

背景（2026-07-28）：OE(Oracle's Elixir) 對某些賽段收錄很慢——LPL 2026 Split 3 已打完第一週 33 局，
OE 一場都沒有（主資料最後停在 S2 PO 6/14）。本腳本從 gol.gg 抓同一批比賽補上。

**使用者定案：OE 有更新後就不再抓 gol.gg／wiki。** 兩道閘門：
  ①抓取層：OE 該賽段收錄局數 ≥ 本地已知局數 → 完全不抓（連 HTTP 都不發）
  ②併入層：fetch_data.py 併入時以 OE 為準，同一局（日期+兩隊+局號）OE 有就丟掉補充版

為什麼是 gol.gg 而不是 Leaguepedia Cargo：
  Cargo 限流兇到不可用（實測 6s 節流仍被擋、退避 60/120/240 秒仍 429），且沒有 GD@15。
  gol.gg 無限流、逐選手數據更完整。Cargo 版備援留在 fetch_wiki_fill.py。

能填的：選手/英雄/路線/KDA/金錢/CS/傷害(含 DPM、傷害佔比)/視野(含 wards)/隊伍物件(龍/男爵/塔/水晶/先鋒/幼蟲)/
        首殺·首塔/BP 全順序/patch/時長/勝負/**GD@15**（OE 的 LPL 資料反而沒有這欄）
填不了的（留空，與 OE 的 LPL 現況一致）：@10/@20/@25 全系列、turretplates、earnedgold/gspd、傷害減免

用法：
  python scripts\fetch_fill.py            # 有 HTML 快取就不重抓；OE 追上就自動停用
  python scripts\fetch_fill.py --force    # 強制重抓（賽段進行中，要拿新一週的比賽用這個）
  python scripts\fetch_fill.py --dump     # 只印解析結果不寫檔（檢查用）
  python scripts\fetch_fill.py --status   # 只看 OE/補充 各收錄幾局
"""
import argparse, csv, io, json, os, re, sys, time, urllib.parse, urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")  # 防重複包裝：被 import 時再包一層會關掉呼叫端的 buffer
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, "csv_cache")
if not os.path.isdir(CACHE) and os.path.isdir(os.path.join(ROOT, "csv_cache")):
    CACHE = os.path.join(ROOT, "csv_cache")
HCACHE = os.path.join(CACHE, "golgg")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
      "Accept-Language": "en-US,en;q=0.9"}
GAP = 2.0     # 每次請求間隔（禮貌節流；gol.gg 無硬限流）

# ── 要補的賽段（OE 收錄後自動停用，不必手動刪） ──
# wiki＝Leaguepedia 的賽事名（給 build_wiki 用）。**兩邊都抓再合併**（2026-08-02 使用者定案）：
# gol.gg 逐選手數據齊全但**局數會漏**，Leaguepedia 幾乎不漏比賽但沒有逐選手數據——
# 實測 LPL 2026 Split 3：gol.gg 33 局、Leaguepedia 56 局（差 23 局）。
FILL = [
    {"key": "LPL_2026_S3", "tournament": "LPL 2026 Split 3", "wiki": "LPL 2026 Split 3",
     "league": "LPL", "split": "Split 3", "year": 2026, "playoffs": 0},
    # LCK 也開始缺（2026-07-31 使用者回報）：主資料停在 S2 PO 6/14，Rounds 3-4（＝儀表板 S3）一局都沒有。
    # gol.gg 的賽事名是「LCK 2026 Rounds 3-4」（實測 10 個系列賽、已完成 4，最新 7/30）；
    # split 直接寫 S3——`sn` 只會把「Split N」轉成「SN」，本來就是 S3 的照用。
    {"key": "LCK_2026_S3", "tournament": "LCK 2026 Rounds 3-4", "wiki": "LCK 2026 Rounds 3-4",
     "league": "LCK", "split": "S3", "year": 2026, "playoffs": 0},
]

POS5 = ["top", "jng", "mid", "bot", "sup"]
ROLE2POS = {"TOP": "top", "JUNGLE": "jng", "JUNGLER": "jng", "MID": "mid", "MIDDLE": "mid",
            "ADC": "bot", "BOT": "bot", "BOTTOM": "bot", "SUPPORT": "sup", "SUP": "sup"}
PID = {"top": 1, "jng": 2, "mid": 3, "bot": 4, "sup": 5}


# ────────────────────────── 工具 ──────────────────────────
def strip_tags(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def num(s, d=""):
    """'1 234'/'12.5%'/'67.4k' → 數字字串；空/佔位回 d"""
    if s is None:
        return d
    t = str(s).replace(",", "").replace(" ", " ").strip()
    if t in ("", "-", "–", "—", "&nbsp;"):
        return d
    t = t.replace("%", "")
    m = re.match(r"^-?\d+(\.\d+)?$", t)
    return t if m else d


def get(url, cache_name, force=False):
    os.makedirs(HCACHE, exist_ok=True)
    p = os.path.join(HCACHE, cache_name)
    if os.path.exists(p) and not force:
        with open(p, encoding="utf-8") as f:
            return f.read()
    for a in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as f:
                body = f.read().decode("utf-8", "replace")
            with open(p, "w", encoding="utf-8") as f:
                f.write(body)
            time.sleep(GAP)
            return body
        except Exception as e:
            print(f"      {type(e).__name__}: {str(e)[:80]} → 重試 {a+1}", flush=True)
            time.sleep(5 * (a + 1))
    raise RuntimeError("下載失敗：" + url)


def gkey_of(h, r):
    """一局的識別鍵：日期+局號+兩隊（**隊伍不能省**——同一天不同系列的局號會重複，
    只用 (日期,局號) 去重會把 33 局數成 14 局，閘門就會誤判 OE 已經追上）"""
    iD, iG = h.index("date"), h.index("game")
    iBT, iRT = h.index("blue_teamname"), h.index("red_teamname")
    return "|".join([str(r[iD])[:10], str(r[iG])] + sorted([r[iBT] or "", r[iRT] or ""]))


def oe_games(year, league, split_norm, exclude=None):
    """OE 目前收錄該賽段幾局。
    exclude＝本腳本自己補進去的局鍵；data_{年}.js 已經含補充資料，不扣掉就會把自己的補充當成「OE 已收錄」。"""
    p = os.path.join(ROOT, "data", f"data_{year}.js")
    if not os.path.exists(p):
        return 0
    with open(p, encoding="utf-8") as f:
        D = json.loads(f.read().split("=", 1)[1].strip().rstrip(";"))
    R = D["tabs"]["RAW_DATA"]; h = R[0]
    iL, iS, iP = h.index("league"), h.index("split"), h.index("participantid")
    ex = set(exclude or ())
    seen = set()
    for r in R[1:]:
        if r[iL] == league and str(r[iS]).split(" PO")[0] == split_norm and str(r[iP]) == "100":
            k = gkey_of(h, r)
            if k not in ex:
                seen.add(k)
    return len(seen)


def oe_names(year, league):
    """OE 既有的隊名／選手名／英雄名（對齊 gol.gg 的寫法，避免同一實體被拆成兩個名字）"""
    p = os.path.join(ROOT, "data", f"data_{year}.js")
    teams, players, champs = {}, {}, {}
    if not os.path.exists(p):
        return teams, players, champs
    with open(p, encoding="utf-8") as f:
        D = json.loads(f.read().split("=", 1)[1].strip().rstrip(";"))
    R = D["tabs"]["RAW_DATA"]; h = R[0]
    iL = h.index("league")
    bp, bt = h.index("blue_playername"), h.index("blue_teamname")
    rp, rt = h.index("red_playername"), h.index("red_teamname")
    bc, rc = h.index("blue_champion"), h.index("red_champion")
    ibl = h.index("banlist")
    key = lambda s: re.sub(r"[^0-9a-z]", "", str(s or "").lower())
    for r in R[1:]:
        # 英雄名不分聯賽全收（gol.gg 的圖檔名沒有標點：Kaisa→Kai'Sa、Belveth→Bel'Veth）
        for c in (r[bc], r[rc]):
            if c:
                champs.setdefault(key(c), c)
        for c in str(r[ibl] or "").split("|"):
            if c:
                champs.setdefault(key(c), c)
        if r[iL] != league:
            continue
        for a, b in ((bt, bp), (rt, rp)):
            if r[a]:
                teams.setdefault(key(r[a]), r[a])
            if r[b]:
                players.setdefault(key(r[b]), r[b])
    return teams, players, champs


# ────────────────────────── gol.gg 解析 ──────────────────────────
def parse_matchlist(html):
    """→ [{'gid':第一局id,'date':'2026-07-22','patch':'16.13','week':'WEEK1','done':True}]"""
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        m = re.search(r"/game/stats/(\d+)/", tr)
        if not m:
            continue
        tds = [strip_tags(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        tds = [t for t in tds if t]
        date = next((t for t in tds if re.match(r"^\d{4}-\d{2}-\d{2}$", t)), "")
        patch = next((t for t in tds if re.match(r"^\d{1,2}\.\d{1,2}$", t)), "")
        week = next((t for t in tds if re.match(r"^WEEK\s*\d+$", t, re.I)), "")
        score = next((t for t in tds if re.match(r"^\d+\s*-\s*\d+$", t)), "")
        out.append({"gid": int(m.group(1)), "date": date, "patch": patch,
                    "week": week, "done": bool(score and patch)})
    return out


def parse_game(html):
    """page-game → 隊伍層級資料 + BP + 同 match 的所有 gameid"""
    b = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    d = {}
    d["ids"] = sorted({int(x) for x in re.findall(r"/game/stats/(\d+)/", b)})
    m = re.search(r"Game Time.*?<h1>\s*(\d+):(\d+)\s*</h1>", b, re.S)
    d["gamelength"] = str(int(m.group(1)) * 60 + int(m.group(2))) if m else ""
    m = re.search(r"col-3 text-right[^>]*>\s*v?(\d+\.\d+)", b)
    d["patch"] = m.group(1) if m else ""
    m = re.search(r"(\d{4}-\d{2}-\d{2})\s*\((WEEK[^)]*)\)", b)
    d["date"], d["week"] = (m.group(1), m.group(2)) if m else ("", "")

    # 版面順序固定：BLUE 區塊(隊名/統計/首塔或首殺圖示/Bans/Picks) → RED 區塊 → 下方選手表(會再出現一次 blue-line-header)
    # → 依「第一個 blue-line-header / red-line-header / 第二個 blue-line-header」切三刀，各側只認自己段內的東西
    bh = [m.start() for m in re.finditer(r"blue-line-header", b)]
    rh = [m.start() for m in re.finditer(r"red-line-header", b)]
    if not bh or not rh:
        d["sides"] = {}; d["bp"] = []
        return d
    b0, r0 = bh[0], rh[0]
    end = next((x for x in bh if x > r0), len(b))          # 紅段結束＝下一個 blue-line-header（選手表表頭）
    segs = {"blue": b[b0:r0], "red": b[r0:end]}

    sides = {}
    for side, seg in segs.items():
        nm = re.search(r"title='([^']+) stats'", seg)
        hdr = strip_tags(seg[:400]).upper()
        stats = {}
        for m in re.finditer(r"score-box \w+_line\"><img[^>]+alt=['\"]([^'\"]+)['\"]\s*/?>\s*([\d.]+k?)", seg):
            stats[m.group(1).strip()] = m.group(2)
        sides[side] = {
            "team": (nm.group(1).strip() if nm else ""),
            "win": " WIN" in hdr,                          # 「- WIN」/「- LOSS」；LOSS 不含 " WIN"
            "stats": stats,
            "firsttower": "1" if "firsttower" in seg else "0",
            "firstblood": "1" if "firstblood" in seg else "0",
            "firstpick": "1" if re.search(r"_img/first\.png", seg) else "0",  # First Pick 圖示＝該側先選（LPL 不一定是藍方）
        }
    d["sides"] = sides

    # BP：各側段內的 Bans / Picks（紅方是「Picks &nbsp;<img First Pick>」，標籤後不一定緊接 <img）
    bp = {}
    for side, seg in segs.items():
        cur = {}
        marks = [(m.start(), m.group(1)) for m in re.finditer(r">\s*(Bans|Picks)", seg)]
        for i, (pos, kind) in enumerate(marks):
            stop = marks[i + 1][0] if i + 1 < len(marks) else len(seg)
            # 用圖檔名而非 alt：gol.gg 的 alt='Kai'Sa' 單引號沒跳脫，正則會截成「Kai」
            cur[kind.lower()] = re.findall(r"champions_icon/([A-Za-z0-9_.\-]+)\.png'[^>]*class='champion_icon_medium",
                                           seg[pos:stop])[:5] or \
                                re.findall(r"champion_icon_medium[^>]*champions_icon/([A-Za-z0-9_.\-]+)\.png",
                                           seg[pos:stop])[:5]
        bp[side] = cur
    d["bp"] = bp
    return d


def parse_fullstats(html):
    """page-fullstats → {'champs':[10隻], 'rows':{指標: [10 值]}}"""
    b = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    trs = re.findall(r"<tr[^>]*>(.*?)</tr>", b, re.S)
    # 取圖檔名（Kaisa/LeeSin）而非 alt——alt='Kai'Sa' 的單引號沒跳脫；檔名之後用 champs_map 還原成 OE 寫法
    champs = re.findall(r"champions_icon/([A-Za-z0-9_.\-]+)\.png", trs[0]) if trs else []
    rows = {}
    for tr in trs:
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)
        if len(cells) < 2:
            continue
        k = strip_tags(cells[0])
        vals = [strip_tags(c) for c in cells[1:]]
        if k and k not in rows:
            rows[k] = vals
    return {"champs": champs, "rows": rows}


# ────────────────────────── 抓取驅動 ──────────────────────────
def collect(cfg, force=False):
    """→ [每局 dict]（meta / sides / bp / fullstats）"""
    tour = urllib.parse.quote(cfg["tournament"])
    # matchlist 一律重抓（賽段進行中每天有新比賽）；個別局頁面走快取（已完成的比賽資料不會再變）
    ml = get(f"https://gol.gg/tournament/tournament-matchlist/{tour}/",
             f"matchlist_{cfg['key']}.html", force=True)
    matches = [m for m in parse_matchlist(ml) if m["done"]]
    print(f"    matchlist：{len(matches)} 個已完成系列賽")

    day_seq, games, seen = {}, [], set()
    for mi, mt in enumerate(sorted(matches, key=lambda x: (x["date"], x["gid"]))):
        first = get(f"https://gol.gg/game/stats/{mt['gid']}/page-game/",
                    f"g{mt['gid']}_game.html", force=force)
        gd0 = parse_game(first)
        ids = sorted(i for i in gd0["ids"] if i >= mt["gid"]) or [mt["gid"]]
        k = day_seq.get(mt["date"], 0); day_seq[mt["date"]] = k + 1
        for gi, gid in enumerate(ids):
            if gid in seen:
                continue
            seen.add(gid)
            gd = gd0 if gid == mt["gid"] else parse_game(
                get(f"https://gol.gg/game/stats/{gid}/page-game/", f"g{gid}_game.html", force=force))
            if not gd.get("sides"):
                print(f"      ⚠ {gid} 無隊伍區塊，跳過"); continue
            fs = parse_fullstats(get(f"https://gol.gg/game/stats/{gid}/page-fullstats/",
                                     f"g{gid}_full.html", force=force))
            if len(fs.get("champs") or []) < 10 or len(fs["rows"].get("Player") or []) < 10:
                print(f"      ⚠ {gid} 逐選手資料不全，跳過"); continue
            hh = min(9 + k * 3 + gi, 23)   # 同日多系列/多局的假時鐘：只為了 date 排序穩定
            games.append({"gid": gid, "game": gi + 1, "date": gd["date"] or mt["date"],
                          "time": "%02d:%02d:00" % (hh, (gi * 7) % 60),
                          "patch": gd["patch"] or mt["patch"], "week": gd.get("week") or mt["week"],
                          "gamelength": gd["gamelength"], "sides": gd["sides"], "bp": gd["bp"], "fs": fs})
        print(f"      [{mi+1}/{len(matches)}] {mt['date']} match {mt['gid']} → {len(ids)} 局", flush=True)
    return games


# ────────────────────────── 組 OE CSV ──────────────────────────
def oe_header():
    """OE CSV 欄位模板：順序必須與 OE 一致，否則 process() 衍生的 blue_*/red_* 順序對不上主資料"""
    for y in range(2025, 2013, -1):
        p = os.path.join(CACHE, f"{y}.csv")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return next(csv.reader(f))
    raise RuntimeError("找不到 OE CSV 快取（csv_cache/20xx.csv）")


def to_csv_rows(games, cfg):
    hdr = oe_header()
    ix = {h: i for i, h in enumerate(hdr)}
    teams_map, players_map, champs_map = oe_names(cfg["year"], cfg["league"])
    nk = lambda s: re.sub(r"[^0-9a-z]", "", str(s or "").lower())
    align = lambda s, m: m.get(nk(s), s)   # 對齊 OE 既有寫法（gol.gg「Anyone s Legend」→「Anyone's Legend」）
    unknown = set()

    def champ(fname):
        """gol.gg 圖檔名 → OE 英雄名（Kaisa→Kai'Sa、LeeSin→Lee Sin、MonkeyKing→Wukong 等）"""
        if not fname or fname.lower() == "void":
            return ""            # void.png ＝ alt='No ban'，該手 ban 沒使用（OE 用空字串表示）
        v = champs_map.get(nk(fname))
        if v:
            return v
        unknown.add(fname)
        return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", fname)   # 退回：駝峰拆字（新英雄當年還沒人選過時）

    out = []
    for g in games:
        fs, R = g["fs"], g["fs"]["rows"]
        mins = (float(g["gamelength"]) / 60) if num(g["gamelength"]) else 0

        def val(k, i, d=""):
            a = R.get(k) or []
            return num(a[i], d) if i < len(a) else d

        def pct(k, i):
            x = val(k, i)
            return str(round(float(x) / 100, 6)) if x else ""

        kills_of = {s: num(g["sides"][s]["stats"].get("Kills"), "0") for s in ("blue", "red")}
        agg = {}
        for s in ("blue", "red"):
            rng = range(0, 5) if s == "blue" else range(5, 10)
            f = lambda k: sum(float(val(k, i, "0") or 0) for i in rng)
            agg[s] = {"gold": f("Golds"), "dmg": f("Total damage to Champion"), "vs": f("Vision Score"),
                      "cs": f("CS"), "a": f("Assists"), "wp": f("Wards placed"),
                      "wk": f("Wards destroyed"), "cw": f("Control Wards Purchased")}

        def base_row(s, pos, pid):
            r = [""] * len(hdr)
            def put(k, v):
                if k in ix:
                    r[ix[k]] = "" if v is None else str(v)
            put("gameid", f"golgg{g['gid']}"); put("datacompleteness", "partial")
            put("url", f"https://gol.gg/game/stats/{g['gid']}/page-game/")
            put("league", cfg["league"]); put("year", cfg["year"]); put("split", cfg["split"])
            put("playoffs", cfg.get("playoffs", 0)); put("date", f"{g['date']} {g['time']}")
            put("game", g["game"]); put("patch", g["patch"]); put("participantid", pid)
            put("side", s.capitalize()); put("position", pos)
            put("teamname", align(g["sides"][s]["team"], teams_map))
            put("firstPick", g["sides"][s].get("firstpick", "0"))
            for bi, ch in enumerate((g["bp"].get(s, {}).get("bans") or [])[:5]):
                put(f"ban{bi+1}", champ(ch))
            for pi2, ch in enumerate((g["bp"].get(s, {}).get("picks") or [])[:5]):
                put(f"pick{pi2+1}", champ(ch))
            put("gamelength", g["gamelength"]); put("result", "1" if g["sides"][s]["win"] else "0")
            put("teamkills", kills_of[s]); put("teamdeaths", kills_of[s == "blue" and "red" or "blue"])
            return r, put

        for i in range(10):
            s = "blue" if i < 5 else "red"
            role = ((R.get("Role") or [""] * 10)[i] if i < len(R.get("Role") or []) else "").strip().upper()
            pos = ROLE2POS.get(role, POS5[i % 5])
            r, put = base_row(s, pos, PID[pos])
            put("playername", align((R.get("Player") or [""] * 10)[i], players_map))
            put("champion", champ(fs["champs"][i]) if i < len(fs["champs"]) else "")
            put("kills", val("Kills", i)); put("deaths", val("Deaths", i)); put("assists", val("Assists", i))
            for k, c in (("doublekills", "Double kills"), ("triplekills", "Triple kills"),
                         ("quadrakills", "Quadra kills"), ("pentakills", "Penta kills")):
                put(k, val(c, i))
            put("damagetochampions", val("Total damage to Champion", i)); put("dpm", val("DPM", i))
            put("damageshare", pct("DMG%", i))
            if mins:
                put("damagetakenperminute", round(float(val("Total damage taken", i, "0") or 0) / mins, 4))
            put("wardsplaced", val("Wards placed", i)); put("wpm", val("WPM", i))
            put("wardskilled", val("Wards destroyed", i)); put("wcpm", val("WCPM", i))
            put("controlwardsbought", val("Control Wards Purchased", i))
            put("visionscore", val("Vision Score", i)); put("vspm", val("VSPM", i))
            put("totalgold", val("Golds", i)); put("earnedgoldshare", pct("GOLD%", i))
            cs = val("CS", i, "0"); jg = val("CS in Team's Jungle", i, "0"); ej = val("CS in Enemy Jungle", i, "0")
            put("total cs", cs); put("cspm", val("CSM", i))
            put("monsterkills", int(float(jg or 0) + float(ej or 0)))
            put("minionkills", int(float(cs or 0) - float(jg or 0) - float(ej or 0)))
            put("monsterkillsownjungle", jg); put("monsterkillsenemyjungle", ej)
            put("golddiffat15", val("GD@15", i))   # gol.gg 獨有（OE 的 LPL 連這欄都沒有）
            out.append(r)

        for s in ("blue", "red"):
            opp = "red" if s == "blue" else "blue"
            st, ost = g["sides"][s]["stats"], g["sides"][opp]["stats"]
            r, put = base_row(s, "team", 100)
            put("kills", kills_of[s]); put("deaths", kills_of[opp]); put("assists", int(agg[s]["a"]))
            put("firstblood", g["sides"][s]["firstblood"]); put("firsttower", g["sides"][s]["firsttower"])
            put("dragons", num(st.get("Dragons"))); put("opp_dragons", num(ost.get("Dragons")))
            put("barons", num(st.get("Nashor"))); put("opp_barons", num(ost.get("Nashor")))
            put("towers", num(st.get("Towers"))); put("opp_towers", num(ost.get("Towers")))
            put("totalgold", int(agg[s]["gold"])); put("damagetochampions", int(agg[s]["dmg"]))
            put("visionscore", int(agg[s]["vs"])); put("total cs", int(agg[s]["cs"]))
            put("wardsplaced", int(agg[s]["wp"])); put("wardskilled", int(agg[s]["wk"]))
            put("controlwardsbought", int(agg[s]["cw"]))
            if mins:
                put("team kpm", round(float(kills_of[s] or 0) / mins, 4))
                put("ckpm", round((float(kills_of["blue"] or 0) + float(kills_of["red"] or 0)) / mins, 4))
                put("dpm", round(agg[s]["dmg"] / mins, 4))
            out.append(r)
    if unknown:
        print("    ⚠ 這些英雄圖檔名對不到 OE 既有英雄名（用駝峰拆字退回）：" + "、".join(sorted(unknown)))
    return hdr, out


# ────────────────────────── 主流程 ──────────────────────────
def gate(cfg):
    """OE 追上了沒 → (還需要補嗎, OE 局數, prev, fill_path)。gol.gg 與 wiki 兩條補充共用同一道閘門。

    「自己補進去的局」一定要用 fill JSON 存的 gkeys 從 OE 局數扣掉：data_{年}.js 本身已含
    補充資料，不扣就會把自己補的當成「OE 已追上」而把補充資料刪掉（2026-07-28 實際踩過）。
    """
    sn = cfg["split"].replace("Split ", "S")
    fill_path = os.path.join(CACHE, f"fill_{cfg['year']}.json")
    prev = {}
    if os.path.exists(fill_path):
        with open(fill_path, encoding="utf-8") as f:
            prev = json.load(f)
    _pv = prev.get(cfg["key"], {})
    mine = _pv.get("gkeys") or []      # 上次自己補進去的局 → 不能算成「OE 已收錄」
    if not mine and _pv.get("rows"):
        # 舊格式（沒存 gkeys）就地補算
        mine = sorted({gkey_of(_pv["header"], r) for r in _pv["rows"]})
        _pv["gkeys"] = mine
    n_oe = oe_games(cfg["year"], cfg["league"], sn, exclude=mine)
    n_prev = len(_pv.get("games") or [])
    return (not (n_oe and n_oe >= max(n_prev, 1))), n_oe, prev, fill_path


def build(cfg, force=False, dump=False):
    sn = cfg["split"].replace("Split ", "S")
    need, n_oe, prev, fill_path = gate(cfg)
    if not need:
        n_prev = len(prev.get(cfg["key"], {}).get("games") or [])
        print(f"  {cfg['key']}：OE 已收錄 {n_oe} 局（補充版 {n_prev} 局）→ 停用補充資料")
        if cfg["key"] in prev:
            prev.pop(cfg["key"])
            with open(fill_path, "w", encoding="utf-8") as f:
                json.dump(prev, f, ensure_ascii=False)
            print("    已移除舊的補充資料")
        return None
    print(f"  {cfg['key']}：OE {n_oe} 局 → 需要補充")

    games = collect(cfg, force=force)
    if not games:
        print("    沒抓到任何局"); return None
    hdr, rows = to_csv_rows(games, cfg)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(hdr); w.writerows(rows)

    sys.path.insert(0, HERE)
    import fetch_data
    table = fetch_data.process(buf.getvalue(), cfg["year"])   # 衍生欄位(po/Lane/banlist/decider_winner)全部沿用 OE 那套
    if dump:
        print(f"    process() → {len(table)-1} 列，{len(table[0])} 欄")
        h = table[0]
        for r in table[1:7]:
            print("      ", r[h.index("date")], r[h.index("split")], "pid" + str(r[h.index("participantid")]),
                  r[h.index("blue_teamname")], r[h.index("blue_playername")], r[h.index("blue_champion")],
                  "vs", r[h.index("red_playername")], r[h.index("red_champion")])
        return table

    _h = table[0]
    _gk = sorted({gkey_of(_h, r) for r in table[1:]})
    prev[cfg["key"]] = {"header": table[0], "rows": table[1:], "games": [g["gid"] for g in games],
                        "gkeys": _gk,
                        "src": "gol.gg", "tournament": cfg["tournament"],
                        "league": cfg["league"], "split": sn, "year": cfg["year"]}
    with open(fill_path, "w", encoding="utf-8") as f:
        json.dump(prev, f, ensure_ascii=False)
    print(f"    → csv_cache/fill_{cfg['year']}.json（{len(games)} 局 / {len(table)-1} 列）")
    return table


def build_wiki(cfg):
    """同一賽段再從 Leaguepedia 文字版 MH 抓一份 → wikifill_{年}.json（2026-08-02 使用者定案）。

    **為什麼兩邊都要抓**：gol.gg 逐選手數據齊全（KDA／金錢／CS／傷害／GD@15）但**局數會漏**；
    Leaguepedia 幾乎不漏比賽，但沒有逐選手數據。實測 LPL 2026 Split 3：gol.gg 33 局、wiki 56 局。
    合併順序已經是對的（fetch_data：merge_fill 先、merge_wiki 後，同一局已存在就丟掉 wiki 版）
    → 有 gol.gg 的局用 gol.gg 的完整數據，gol.gg 漏掉的局至少有隊伍／勝負／BP／英雄。
    逐選手 KDA／CS／金錢之後可再靠 fetch_wiki_stats.py（Cargo ScoreboardPlayers）補空欄位。

    HTML 一律重抓（不吃快取）：賽段進行中，用快取就拿不到這週的新比賽。
    """
    if not cfg.get("wiki"):
        return None
    need, n_oe, _, _ = gate(cfg)
    wp = os.path.join(CACHE, f"wikifill_{cfg['year']}.json")
    if not need:
        # OE 追上時要跟 gol.gg 版一起停用，否則會留下一批沒有逐選手數據的 wiki 列
        if os.path.exists(wp):
            with open(wp, encoding="utf-8") as f:
                W = json.load(f)
            if W.pop(cfg["key"], None) is not None:
                with open(wp, "w", encoding="utf-8") as f:
                    json.dump(W, f, ensure_ascii=False)
                print(f"    已移除 wiki 補充資料（{cfg['key']}）")
        return None
    sys.path.insert(0, HERE)
    import fetch_wiki_mh
    print(f"  {cfg['key']}：Leaguepedia「{cfg['wiki']}」…")
    try:
        return fetch_wiki_mh.build({"tour": cfg["wiki"], "league": cfg["league"],
                                    "split": cfg["split"], "year": cfg["year"],
                                    "playoffs": cfg.get("playoffs", 0), "key": cfg["key"],
                                    "pb_force": True},   # 賽段進行中：Picks and Bans 頁也要重抓
                                   force=True)
    except Exception as e:      # wiki 掛掉不能連帶讓 gol.gg 那份也沒寫成
        print(f"    ⚠ wiki 補充失敗（略過，gol.gg 版照用）：{type(e).__name__}: {e}")
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="重抓 HTML（賽段進行中要拿新比賽用這個）")
    ap.add_argument("--dump", action="store_true", help="只解析不寫檔")
    ap.add_argument("--status", action="store_true", help="只看 OE / 補充 各幾局")
    ap.add_argument("--no-wiki", action="store_true", help="只抓 gol.gg，不抓 Leaguepedia")
    A = ap.parse_args()
    for cfg in FILL:
        sn = cfg["split"].replace("Split ", "S")
        if A.status:
            p = os.path.join(CACHE, f"fill_{cfg['year']}.json")
            n, mine = 0, []
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    d = json.load(f).get(cfg["key"], {})
                n = len(d.get("games") or []); mine = d.get("gkeys") or []
            wn = 0
            wp = os.path.join(CACHE, f"wikifill_{cfg['year']}.json")
            if os.path.exists(wp):
                with open(wp, encoding="utf-8") as f:
                    wn = json.load(f).get(cfg["key"], {}).get("games") or 0
            print(f"  {cfg['key']:14s} OE={oe_games(cfg['year'], cfg['league'], sn, exclude=mine):3d} 局"
                  f"   gol.gg={n:3d} 局   wiki={wn:3d} 局")
            continue
        build(cfg, force=A.force, dump=A.dump)
        if not (A.dump or A.no_wiki):
            build_wiki(cfg)
    if not A.status:
        print("完成。（fetch_data.py 寫檔時會併入：OE > gol.gg > wiki，同一局以先者為準）")


if __name__ == "__main__":
    main()
