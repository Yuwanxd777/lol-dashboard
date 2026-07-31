# -*- coding: utf-8 -*-
"""Leaguepedia 文字版 Match History → OE CSV → fetch_data.process() → wikifill_{年}.json

**為什麼用這條路**（2026-07-31 使用者提供關鍵網址）：
  Cargo API（api.php?action=cargoquery）對匿名存取限流極兇——連打幾次就 ratelimited，
  退避到 480 秒仍被擋，等於不可用。但 `Special:RunQuery/MatchHistoryGame` 的
  **textonly** 版是一般頁面請求，一次就能拿整個賽事（limit 999），完全不吃 Cargo 限流。
  注意：要先造訪表單頁拿 cookie，否則第二次請求開始會 302→403。

文字表欄位（實測 Champions 2013 Winter 113 局）：
  Date, P(atch), Blue, Red, Winner, Bans藍, Bans紅, Picks藍, Picks紅, 藍名單, 紅名單, Len,
  BG/BK/BT/BD/BB/BRH/BVG（藍方 金錢/擊殺/塔/龍/男爵/先鋒/幼蟲）, RG/RK/…（紅方）, SB, VOD
  **Picks 與名單同為路線序**（實測 NaJin Sword：MakNooN=Renekton…）→ 可直接配對成逐選手列。
  wiki 沒有的（逐選手 K/D/A、金錢、CS、傷害）一律留空，與 OE 對某些賽區的現況一致。

用法：
  python scripts\\fetch_wiki_mh.py --tour "Champions 2013 Winter" --league LCK --split "Winter" --year 2013
  python scripts\\fetch_wiki_mh.py --probe "LPL 2013 Spring"      # 只看抓到幾局
"""
import argparse, csv, html, io, json, os, re, sys, time, urllib.parse, urllib.request, http.cookiejar

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# 快取目錄要跟 fetch_fill 判定一致——**別在 scripts/ 下建 csv_cache**：
# fetch_fill 看到 scripts/csv_cache 存在就會用它，年份 CSV（在根目錄）就找不到，oe_header() 會炸
CACHE = os.path.join(ROOT, "csv_cache")
if not os.path.isdir(CACHE) and os.path.isdir(os.path.join(HERE, "csv_cache")):
    CACHE = os.path.join(HERE, "csv_cache")
HTML_DIR = os.path.join(CACHE, "wikitxt")
sys.path.insert(0, HERE)

BASE = "https://lol.fandom.com/wiki/Special:RunQuery/MatchHistoryGame"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      "Accept-Language": "en-US,en;q=0.9", "Referer": BASE, "Upgrade-Insecure-Requests": "1"}
GAP = 8.0            # 頁面請求間隔（一般頁面，不吃 Cargo 限流；仍禮貌節流）
_OP = None


def opener():
    """先造訪表單頁拿 cookie——不帶 cookie 的話第二次請求開始會 302→403"""
    global _OP
    if _OP is None:
        cj = http.cookiejar.CookieJar()
        _OP = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        try:
            _OP.open(urllib.request.Request(BASE, headers=UA), timeout=60).read()
            time.sleep(2)
        except Exception as e:
            print(f"  ⚠ 表單頁取 cookie 失敗（仍試著繼續）：{type(e).__name__}")
    return _OP


def fetch(tour, force=False):
    os.makedirs(HTML_DIR, exist_ok=True)
    fn = re.sub(r"[^A-Za-z0-9]+", "_", tour).strip("_").lower() + ".html"
    p = os.path.join(HTML_DIR, fn)
    if os.path.exists(p) and os.path.getsize(p) > 5000 and not force:
        return open(p, encoding="utf-8").read()
    q = {"MHG[preload]": "Tournament", "MHG[tournament]": tour, "MHG[limit]": "999",
         "MHG[textonly][is_checkbox]": "true", "MHG[textonly][value]": "", "_run": "",
         "pfRunQueryFormName": "MatchHistoryGame", "wpRunQuery": "", "pf_free_text": ""}
    url = BASE + "?" + urllib.parse.urlencode(q, safe="[]")
    for a in range(3):
        try:
            b = opener().open(urllib.request.Request(url, headers=UA), timeout=150).read().decode("utf-8", "replace")
            open(p, "w", encoding="utf-8").write(b)
            time.sleep(GAP)
            return b
        except Exception as e:
            print(f"    抓取失敗（{a+1}/3）：{type(e).__name__} {str(e)[:60]}")
            time.sleep(20 * (a + 1))
    return ""


def cells_html(row):
    """把每格轉成文字，但**隊伍欄用 title 屬性補**。

    賽事頁的 `/Match History` 子頁（嵌入版）隊名是圖片，純文字化後只剩零寬字元 →
    Blue/Red/Winner 三欄會變空（2026-07-31 使用者提供 LPL 2013 夏季季後賽的正確來源）。
    """
    out = []
    for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S):
        txt = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c))).strip()
        txt = txt.replace("⁠", "").strip()
        if not txt:
            m = re.search(r'<a[^>]+title="([^"]+)"', c)
            if m:
                txt = html.unescape(m.group(1)).strip()
        out.append(txt)
    return out


def fetch_embed(page, force=False):
    """賽事頁的 `/Match History` 子頁（action=parse），回傳 HTML"""
    os.makedirs(HTML_DIR, exist_ok=True)
    fp = os.path.join(HTML_DIR, "embed_" + re.sub(r"[^A-Za-z0-9]+", "_", page)[:110] + ".html")
    if os.path.exists(fp) and os.path.getsize(fp) > 3000 and not force:
        return open(fp, encoding="utf-8").read()
    u = "https://lol.fandom.com/api.php?" + urllib.parse.urlencode(
        {"action": "parse", "page": page, "prop": "text", "format": "json"})
    for a in range(3):
        try:
            r = json.loads(opener().open(urllib.request.Request(u, headers=UA), timeout=120).read())
            if "error" in r:
                print(f"    {page}：{r['error'].get('info','')[:70]}"); return ""
            b = r["parse"]["text"]["*"]
            open(fp, "w", encoding="utf-8").write(b)
            time.sleep(GAP)
            return b
        except Exception as e:
            print(f"    嵌入頁失敗（{a+1}/3）{type(e).__name__}"); time.sleep(10 * (a + 1))
    return ""


def cells(row):
    return [html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c))).strip()
            for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S)]


def parse(hml):
    """→ (欄名, [每局 dict])"""
    tabs = re.findall(r"<table[^>]*>.*?</table>", hml, re.S)
    if not tabs:
        return [], []
    # ⚠ 別用「tr 最多的表」：局數少的賽事（季後賽常常只有 4-5 局）會被頁尾那張表蓋過去，
    #   結果整個賽事變 0 局（2026-07-31 使用者回報 LPL 2013 夏季季後賽）。
    #   RunQuery 的結果表一定帶 class="…mhgame…"，先用它挑，挑不到才退回 tr 最多。
    mh = [t for t in tabs if "mhgame" in (re.match(r"<table[^>]*>", t) or [""])[0]]
    big = max(mh or tabs, key=lambda t: len(re.findall(r"<tr", t)))
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", big, re.S)
    hdr = None
    out = []
    for r in rows:
        c = cells_html(r)
        if not c or all(not x for x in c):
            continue
        if hdr is None:
            if c[0].strip().lower() == "date":
                hdr = c
            continue
        if len(c) < len(hdr) - 4:
            continue
        d = {}
        for i, k in enumerate(hdr):
            k2 = k.strip()
            if k2 in d:                       # Bans/Picks 各出現兩次（藍、紅）
                k2 += "2"
            d[k2] = c[i] if i < len(c) else ""
        if d.get("Date"):
            out.append(d)
    return hdr or [], out


SPL = lambda s: [x.strip() for x in str(s or "").split(",") if x.strip()]


_PNAME = None


def pname(nm):
    """wiki 的選手 ID 是「當年寫法」，OE 用的是統一寫法（2013 是 bengi、2015 之後 OE 寫 Bengi）。

    不對齊的話同一個人會被拆成兩份生涯統計（2026-07-31 使用者提醒：抓 Match History 要抓選手名稱，
    不然選手生涯統計會漏）。以 2016 年起的 OE 原生資料為權威寫法，用 casefold 比對換過來；
    對不上的（早年就退役、OE 沒收）保留 wiki 原寫法，反正那些人只出現在補進來的年份、彼此一致。
    """
    global _PNAME
    if _PNAME is None:
        import glob
        _PNAME = {}
        for p in sorted(glob.glob(os.path.join(ROOT, "data", "data_*.js"))):
            try:
                y = int(os.path.basename(p)[5:9])
            except ValueError:
                continue
            if y < 2016:                      # 2015 以前混有 wiki 補的資料，不能當權威
                continue
            try:
                R = json.loads(open(p, encoding="utf-8").read().split("=", 1)[1].strip().rstrip(";"))["tabs"]["RAW_DATA"]
            except Exception:
                continue
            ix = {n: i for i, n in enumerate(R[0])}
            for k in ("blue_playername", "red_playername"):
                if k not in ix:
                    continue
                for r in R[1:]:
                    v = str(r[ix[k]] or "").strip()
                    if v:
                        _PNAME.setdefault(v.casefold(), v)
    return _PNAME.get(str(nm or "").casefold(), nm)


def _patch(v):
    """wiki 的版本欄補零成 OE 格式（"3.9"→"3.09"）。

    OE 自己就是補零的（CSV 實測全是 5.09/5.11），fetch_data 之後統一 +10 換成 13.xx／15.xx。
    不補零的話 float("3.9")+10 會被格式化成 "13.90"，看起來像第 90 個版本，
    而且同一個版本會裂成 15.90／15.09 兩種值（2026-07-31 使用者回報）。
    """
    m = re.match(r"^\s*(\d+)\.(\d+)\s*$", str(v or ""))
    return f"{m.group(1)}.{int(m.group(2)):02d}" if m else str(v or "")


def to_csv(games, cfg):
    import fetch_fill as _ff
    hdr = _ff.oe_header()
    ix = {h: i for i, h in enumerate(hdr)}
    teams_map, players_map, champs_map = _ff.oe_names(cfg["year"], cfg["league"])
    nk = lambda s: re.sub(r"[^0-9a-z]", "", str(s or "").lower())
    align = lambda s, m: m.get(nk(s), s)
    POS5 = ["top", "jng", "mid", "bot", "sup"]
    rows = []
    day = {}
    # 系列賽內的局號：wiki 的表格已照時間排 → 同一天、同兩隊（藍紅可能互換，所以用 frozenset）
    # 依序 1、2、3…。原本寫死 game=1，同一場 BO5 的三局全變第 1 局，對戰BP 的比分與
    # 「BO3／BO5」判定就全錯（2026-07-31 使用者回報：10-05 WCS RYL vs SKT 三局同一天卻顯示 0-1）
    # 系列賽鍵**不能含日期**：BO5 常跨午夜或跨天（NA LCS 2013 春季決賽 TSM vs GGU
    # 第 1 局在 04-28、其餘四局在 04-29），用 (日期,兩隊) 當鍵會拆成兩個系列、
    # 各自從 1 重編 → 局號變成 [1,1,2,3,4]，前端按 (日期,局號) 去重就少三局
    #（2026-07-31 使用者回報「漏了三場」）。
    # 改成同兩隊且與上一局相隔 <=1 天就算同一系列；隔更久（例行賽下一輪再戰）才重新編。
    def _dd(a, b):
        try:
            from datetime import date as _dt
            x = _dt(*map(int, a.split("-"))); y = _dt(*map(int, b.split("-")))
            return abs((y - x).days)
        except Exception:
            return 99
    # wiki 的 MatchHistoryGame 結果表是**新→舊倒序**，不反轉的話系列賽會從最後一局
    # 開始編號、日期也會取到最後一天（實測 NA LCS 2013 春季決賽第一局在 04-28，
    # 卻被編成 g5、整個系列掛在 04-29）。只在確定倒序時反轉，正序的賽事不動。
    if len(games) > 1:
        _d0 = (games[0].get("Date") or "")[:10]
        _dN = (games[-1].get("Date") or "")[:10]
        if _d0 and _dN and _d0 > _dN:
            games = list(reversed(games))
    ser = {}
    for g in games:
        dt = g.get("Date", "")[:19]
        d10 = dt[:10]
        n = day.get(d10, 0) + 1
        day[d10] = n
        _pair = frozenset((nk(g.get("Blue")), nk(g.get("Red"))))
        _prev = ser.get(_pair)
        if _prev and _dd(_prev[0], d10) <= 1:
            gno, _start = _prev[1] + 1, _prev[2]
        else:
            gno, _start = 1, d10
        # 比對用「上一局的原始日期」，這樣連續跨天（04-28→29→30）也接得上；
        # 寫進資料的日期則統一成系列賽第一局那天（使用者定案 2026-07-31），
        # 免得同一個 BO5 在前端被日期切成兩段。時間保留原值，同系列仍能依時序排。
        ser[_pair] = (d10, gno, _start)
        if _start != d10:
            dt = _start + dt[10:]
        gid = f"wiki_{cfg['key']}_{d10}_{n}"     # gid 用原始日期，保證唯一
        bt, rt = align(g.get("Blue"), teams_map), align(g.get("Red"), teams_map)
        win = g.get("Winner", "")
        bwin = nk(win) == nk(g.get("Blue"))
        ln = g.get("Len", "")
        secs = ""
        m = re.match(r"^(\d+):(\d+)$", ln.strip())
        if m:
            secs = str(int(m.group(1)) * 60 + int(m.group(2)))
        bans = {"blue": SPL(g.get("Bans")), "red": SPL(g.get("Bans2"))}
        # wiki 的 Bans 欄整格只寫一個 "None" ＝ 那一隊**整輪都沒禁**，不是「只有一手沒禁」→
        # 展開成該局應有的禁用數（對手有幾手就幾手，兩邊都 None 就用該年制度：2014 以前 3 禁、2015 起 5 禁），
        # 否則畫面上只會出現一個空 BAN 圖（2026-07-31 使用者回報：None 應該是三個禁用圖）。
        _allnone = lambda a: (not a) or all(str(x).strip().lower() == "none" for x in a)
        for _s in ("blue", "red"):
            if _allnone(bans[_s]):
                _o = "red" if _s == "blue" else "blue"
                bans[_s] = [""] * (len(bans[_o]) if not _allnone(bans[_o])
                                   else (3 if int(cfg["year"]) <= 2014 else 5))
        picks = {"blue": SPL(g.get("Picks")), "red": SPL(g.get("Picks2"))}
        roster = {"blue": SPL(g.get("Blue Roster")), "red": SPL(g.get("Red Roster"))}
        num = lambda k: re.sub(r"[^0-9.]", "", str(g.get(k, "") or ""))
        obj = {"blue": {"g": num("BG"), "k": num("BK"), "t": num("BT"), "d": num("BD"),
                        "b": num("BB"), "h": num("BRH"), "v": num("BVG")},
               "red": {"g": num("RG"), "k": num("RK"), "t": num("RT"), "d": num("RD"),
                       "b": num("RB"), "h": num("RRH"), "v": num("RVG")}}

        def base(side, pos, pid):
            r = [""] * len(hdr)
            put = lambda k, v: r.__setitem__(ix[k], "" if v is None else str(v)) if k in ix else None
            put("gameid", gid); put("datacompleteness", "partial")
            put("league", cfg["league"]); put("year", cfg["year"]); put("split", cfg["split"])
            put("playoffs", cfg.get("playoffs", 0)); put("date", dt)
            put("game", gno); put("patch", _patch(g.get("P", "") or cfg.get("patch", ""))); put("participantid", pid)
            put("side", side.capitalize()); put("position", pos)
            put("teamname", bt if side == "blue" else rt)
            put("result", "1" if (bwin if side == "blue" else not bwin) else "0")
            put("gamelength", secs)
            put("teamkills", obj[side]["k"]); put("teamdeaths", obj["red" if side == "blue" else "blue"]["k"])
            return r, put

        for side in ("blue", "red"):
            for i in range(5):
                pid = i + 1 if side == "blue" else i + 6
                r, put = base(side, POS5[i], pid)
                nm = roster[side][i] if i < len(roster[side]) else ""
                nm = re.sub(r"\s*\(.*?\)$", "", nm).strip()      # 「Woong (Jang Gun-woong)」→ Woong
                put("playername", pname(align(nm, players_map)))   # 對齊 OE 的統一寫法（bengi→Bengi）
                put("champion", align(picks[side][i] if i < len(picks[side]) else "", champs_map))
                rows.append(r)
            r, put = base(side, "team", 100 if side == "blue" else 200)
            # wiki 用字串 "None" 表示「那一手真的沒禁」→ 存成空字串（位置照留，前端才畫得出空 BAN 圖）。
            # 直接丟給 align() 會變成一隻叫 None 的英雄（2026-07-31 使用者回報對戰BP 出現 None）。
            for i2, ch in enumerate(bans[side][:5]):
                put(f"ban{i2+1}", "" if str(ch).strip().lower() in ("none", "") else align(ch, champs_map))
            for i2, ch in enumerate(picks[side][:5]):
                put(f"pick{i2+1}", align(ch, champs_map))
            o = obj[side]
            put("totalgold", o["g"].replace(".", "") if o["g"] else "")
            put("towers", o["t"]); put("dragons", o["d"]); put("barons", o["b"])
            put("heralds", o["h"]); put("void_grubs", o["v"])
            rows.append(r)
    return hdr, rows


def build(cfg, force=False):
    # cfg["embed"]＝賽事頁的 `/Match History` 子頁；有些賽事在 MHG[tournament] 查不到
    # （LPL 2013 夏季季後賽），但賽事頁自己嵌了同一張表（2026-07-31 使用者提供）
    hml = fetch_embed(cfg["embed"], force=force) if cfg.get("embed") else fetch(cfg["tour"], force=force)
    if not hml:
        return None
    hdr0, games = parse(hml)
    print(f"  {cfg['tour']}：解析到 {len(games)} 局")
    if not games:
        return None
    hdr, rows = to_csv(games, cfg)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(hdr); w.writerows(rows)
    import fetch_data
    table = fetch_data.process(buf.getvalue(), cfg["year"])
    print(f"    process() → {len(table)-1} 列")
    p = os.path.join(CACHE, f"wikifill_{cfg['year']}.json")
    D = {}
    if os.path.exists(p):
        try:
            D = json.load(open(p, encoding="utf-8"))
        except Exception:
            D = {}
    D[cfg["key"]] = {"header": table[0], "rows": table[1:], "games": len(games),
                     "src": "leaguepedia MatchHistoryGame(textonly)", "tour": cfg["tour"],
                     "league": cfg["league"], "split": cfg["split"]}
    json.dump(D, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"    → {p}（{cfg['key']}：{len(games)} 局 / {len(table)-1} 列）")
    return table


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tour"); ap.add_argument("--league"); ap.add_argument("--split")
    ap.add_argument("--year", type=int); ap.add_argument("--playoffs", type=int, default=0)
    ap.add_argument("--key"); ap.add_argument("--probe"); ap.add_argument("--force", action="store_true")
    A = ap.parse_args()
    if A.probe:
        h = fetch(A.probe, force=A.force)
        _, gs = parse(h)
        print(f"{A.probe}：{len(gs)} 局")
        for g in gs[:3]:
            print("   ", g.get("Date"), g.get("Blue"), "vs", g.get("Red"), "｜", g.get("Picks", "")[:50])
        return
    cfg = {"tour": A.tour, "league": A.league, "split": A.split, "year": A.year,
           "playoffs": A.playoffs, "key": A.key or re.sub(r"[^A-Za-z0-9]+", "_", A.tour)}
    build(cfg, force=A.force)


if __name__ == "__main__":
    main()
