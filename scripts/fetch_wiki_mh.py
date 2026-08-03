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
PB_DIR = os.path.join(CACHE, "wikipb")      # {OverviewPage}/Picks and Bans 頁（真實選角順序）
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


# ──────────────── Picks and Bans 頁：真實選角順序 ────────────────
# MatchHistoryGame 文字版的 Picks 欄是**路線序**（當初就是靠這點直接配對成逐選手列），
# 拿它當 pick1~5 會讓 fetch_data 的 calc_po 把路線序當選角序 → 順位整個是假的
#（2026-08-02 使用者回報：LPL/LCK 補進來的局，順位都是預設的 1,3,3,6,6／2,2,4,5,7）。
# 真實順序只在 {OverviewPage}/Picks and Bans 頁上（Cargo 的 PicksAndBansS7 對 2026 整批是 null、
# ScoreboardGames 的 Team1Picks 也是路線序，兩張表都拿不到）。
# 25 欄固定順序（實測 LPL/2026 Season/Split 3）：
#   0 Phase 1 Team1 2 Team2 3 Score 4 Winner 5 Patch
#   6 T1B1 7 T2B1 8 T1B2 9 T2B2 10 T1B3 11 T2B3
#   12 T1P1 13 T2P1-2 14 T1P2-3 15 T2P3
#   16 T2B4 17 T1B4 18 T2B5 19 T1B5
#   20 T2P4 21 T1P4-5 22 T2P5      23 SB 24 VOD
# ⚠**T1／T2 是「賽程上的隊伍一二」，不是藍／紅方**（同一系列每局換邊）→ 哪一組屬於藍方
#   一律用「該組五隻英雄＝藍方五隻」判定，不可用隊名或欄位順序。
#   （已用 gol.gg 已知順序的 33 局交叉驗證：PICK 31/33、BAN 32/33 一致，
#     兩筆不一致都是 gol.gg 那邊的解析缺口，其中一局只解析到 9 隻英雄。）
PB_T1P, PB_T2P = (12, 14, 21), (13, 15, 20, 22)
PB_T1B, PB_T2B = (6, 8, 10, 17, 19), (7, 9, 11, 16, 18)
pbn = lambda s: re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def ov_of(tour):
    """賽事名 → Leaguepedia OverviewPage：「LPL 2026 Split 3」→「LPL/2026 Season/Split 3」"""
    m = re.match(r"^(\S+)\s+(\d{4})\s+(.+)$", str(tour or "").strip())
    return f"{m.group(1)}/{m.group(2)} Season/{m.group(3)}" if m else str(tour or "")


def pb_page(tour, force=False):
    os.makedirs(PB_DIR, exist_ok=True)
    p = os.path.join(PB_DIR, re.sub(r"[^A-Za-z0-9]+", "_", tour).strip("_").lower() + ".html")
    if os.path.exists(p) and os.path.getsize(p) > 5000 and not force:
        return open(p, encoding="utf-8").read()
    url = ("https://lol.fandom.com/api.php?action=parse&page="
           + urllib.parse.quote(ov_of(tour) + "/Picks and Bans")
           + "&prop=text&format=json&formatversion=2")
    for a in range(3):
        try:
            raw = opener().open(urllib.request.Request(url, headers=UA), timeout=120).read().decode("utf-8", "replace")
            d = json.loads(raw)
            if "error" in d:
                print(f"    ⚠ Picks and Bans 頁不存在（{ov_of(tour)}）：{d['error'].get('info','')[:60]}")
                return ""
            h = d["parse"]["text"]
            open(p, "w", encoding="utf-8").write(h)
            time.sleep(GAP)
            return h
        except Exception as e:
            print(f"    Picks and Bans 抓取失敗（{a+1}/3）：{type(e).__name__} {str(e)[:60]}")
            time.sleep(15 * (a + 1))
    return ""


def pb_orders(tour, force=False):
    """→ {十隻英雄的 frozenset: {"p":(隊1五手, 隊2五手), "b":(隊1五禁, 隊2五禁)}}

    用整局十隻英雄當鍵：同一局的英雄組合是固定的，跟隊名寫法、局號怎麼標都無關
    （merge_wiki 判定同一局也是用這招）。抓不到頁面就回 {}，呼叫端自行退回。
    """
    html = pb_page(tour, force=force)
    if not html:
        return {}
    tbl = [t for t in re.findall(r"<table[^>]*>.*?</table>", html, re.S) if "pbh-cn" in t]
    if not tbl:
        print("    ⚠ Picks and Bans 頁沒有 pbh-cn 表格（版型可能改了）")
        return {}
    out = {}
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tbl[0], re.S):
        cs = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)
        if len(cs) < 23 or "pbh-cn" not in tr:
            continue
        ch = lambda i: re.findall(r'data-champion="([^"]+)"', cs[i])
        t1p = ch(12) + ch(14) + ch(21)
        t2p = ch(13) + ch(15) + ch(20) + ch(22)
        if len(t1p) != 5 or len(t2p) != 5:
            continue
        key = frozenset(pbn(c) for c in t1p + t2p)
        if len(key) < 10 or key in out:        # 十隻不齊或兩局英雄完全相同 → 不夠獨特，寧可不用
            out.pop(key, None)
            continue
        team = lambda i: (re.search(r'alt="([^"]+?)logo std"', cs[i]) or [None, ""])[1].strip()
        out[key] = {"p": (t1p, t2p),
                    "b": ([(ch(i) or [""])[0] for i in PB_T1B],
                          [(ch(i) or [""])[0] for i in PB_T2B]),
                    # 補局用的中繼資料（PB 頁只有這些，沒有選手／KDA／路線／時間）
                    "t1": team(1), "t2": team(2), "win": team(4),
                    "patch": re.sub(r"<[^>]+>", "", cs[5]).strip()}
    return out


def pb_of(pb, blue_champs, red_champs):
    """查某一局的真實順序 → (藍方五手, 紅方五手, 藍方五禁, 紅方五禁, 藍方是否先選)；查不到回 None。

    T1／T2 不是藍紅方 → 用「哪一組的五隻等於藍方五隻」對齊。
    **T1 ＝先選方**：拿 gol.gg 有 firstPick 真值的 33 局對照，
    「gol.gg 說藍方先選」與「T1 是藍方」完全一致（14 局藍先、19 局紅先，33/33）。
    先選方不是固定藍方（LPL 2026 實測紅方先選佔多數），所以一定要判，不能預設藍方。
    """
    if not pb:
        return None
    b = {pbn(c) for c in blue_champs if c}
    m = pb.get(frozenset(b | {pbn(c) for c in red_champs if c}))
    if not m:
        return None
    p1, p2 = m["p"]
    b1, b2 = m["b"]
    if {pbn(c) for c in p1} == b:
        return p1, p2, b1, b2, True            # 藍方＝T1 ＝先選方
    if {pbn(c) for c in p2} == b:
        return p2, p1, b2, b1, False           # 藍方＝T2 ＝後選方
    return None                                # 兩組都對不上藍方 → 寧可不用，不要猜


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


def _patch(v, year=0):
    """wiki 的版本欄補零成 OE 格式（"3.9"→"3.09"），並把新制年份編號換回 OE 舊制。

    ①補零：OE 自己就是補零的（CSV 實測全是 5.09/5.11），fetch_data 之後統一 +10 換成
      13.xx／15.xx。不補零的話 float("3.9")+10 會被格式化成 "13.90"，看起來像第 90 個版本，
      而且同一個版本會裂成 15.90／15.09 兩種值（2026-07-31 使用者回報）。

    ②主版號換算（2026-08-02 修）：Riot 2025 起改用**年份編號**（26.14），但 OE 的 CSV 仍是
      舊制賽季編號（16.14），`process()` 對所有來源一律 +10 → wiki 版直接變成 **36.14**。
      判準＝主版號正好等於年份末兩碼（26 之於 2026）就先減 10，讓 +10 之後回到正確值。
      舊年份不會誤判：2013 的 wiki 版本是 3.x、2016 是 6.x，都不等於 13／16。
      （gol.gg 那條沒事，它抓到的本來就是 OE 舊制的 16.14。）
    """
    m = re.match(r"^\s*(\d+)\.(\d+)\s*$", str(v or ""))
    if not m:
        return str(v or "")
    maj, mnr = int(m.group(1)), int(m.group(2))
    if year and maj == int(year) % 100:
        maj -= 10
    return f"{maj}.{mnr:02d}"


def to_csv(games, cfg):
    import fetch_fill as _ff
    hdr = _ff.oe_header()
    ix = {h: i for i, h in enumerate(hdr)}
    teams_map, players_map, champs_map = _ff.oe_names(cfg["year"], cfg["league"])
    nk = lambda s: re.sub(r"[^0-9a-z]", "", str(s or "").lower())
    align = lambda s, m: m.get(nk(s), s)
    POS5 = ["top", "jng", "mid", "bot", "sup"]
    # 真實選角順序。歷史賽事的 PB 頁不會再變 → 走快取；進行中的賽段由 fetch_fill 傳 pb_force=True
    PB = pb_orders(cfg["tour"], force=cfg.get("pb_force", False))
    pb_hit = pb_miss = pb_bad = 0
    # 先選方規則（使用者定案 2026-08-02）：**2026 起是新制**，先選／後選與藍／紅方脫鉤，
    # 由雙方自己選（LPL 2026 實測紅方先選佔多數）；**2025 以前藍方固定先選**。
    # 老年份因此多一道驗證：PB 判出「紅方先選」＝我們的藍紅對齊出錯，不是真的 → 整局不採用。
    _yr = int(cfg.get("year") or 0)
    rows = []
    day = {}
    sday = {}          # 每天已出現幾個系列賽（給同日多系列排序用）
    # 系列賽內的局號：wiki 的表格已照時間排 → 同一天、同兩隊（藍紅可能互換，所以用 frozenset）
    # 依序 1、2、3…。原本寫死 game=1，同一場 BO5 的三局全變第 1 局，比賽BP 的比分與
    # 「BO3／BO5」判定就全錯（2026-07-31 使用者回報：10-05 WCS RYL vs SKT 三局同一天卻顯示 0-1）
    # 系列賽鍵**不能含日期**：BO5 常跨午夜或跨天（NA LCS 2013 春季決賽 TSM vs GGU
    # 第 1 局在 04-28、其餘四局在 04-29），用 (日期,兩隊) 當鍵會拆成兩個系列、
    # 各自從 1 重編 → 局號變成 [1,1,2,3,4]，前端按 (日期,局號) 去重就少三局
    #（2026-07-31 使用者回報「漏了三場」）。
    # 改成同兩隊且與上一局間隔夠短就算同一系列；隔更久（例行賽下一輪再戰）才重新編。
    # 用**原始時間差**而不是日期差（2026-08-01 修）：日期差 <=1 天會把「連兩天各打一場
    # 單局」也併成系列——2013 EU LCS 夏季 NiP vs Fnatic 在 08-16 19:00 打例行賽最後一輪、
    # 08-17 19:00 打 Tiebreaker，兩場都是獨立的 BO1，卻被併成 1-1 的系列，前端據此判定
    # 「BO3 缺第 3 局」（使用者回報）。真正跨天的 BO5 各局只隔 1 小時（NA LCS 2013 春季
    # 決賽 TSM vs GGU：04-28 23:00 → 04-29 00:00/01:00/02:00/03:00），8 小時的門檻兩者
    # 都判得對。Date 欄本來就帶時分秒，不必另外抓資料。
    SERIES_GAP_H = 8
    def _hh(a, b):
        try:
            from datetime import datetime as _dtm
            f = "%Y-%m-%d %H:%M:%S"
            return abs((_dtm.strptime(b[:19], f) - _dtm.strptime(a[:19], f)).total_seconds()) / 3600.0
        except Exception:
            return 999.0
    # wiki 的 MatchHistoryGame 結果表是**新→舊倒序**，不反轉的話系列賽會從最後一局
    # 開始編號、日期也會取到最後一天（實測 NA LCS 2013 春季決賽第一局在 04-28，
    # 卻被編成 g5、整個系列掛在 04-29）。只在確定倒序時反轉，正序的賽事不動。
    if len(games) > 1:
        _d0 = (games[0].get("Date") or "")[:10]
        _dN = (games[-1].get("Date") or "")[:10]
        if _d0 and _dN and _d0 > _dN:
            games = list(reversed(games))

    # ── PB 補局（2026-08-03 使用者回報）──────────────────────────────────────
    # Picks and Bans 頁是「哪些局打過」最完整的來源：實測 LCK 2026 Rounds 3-4 →
    # PB 25 局、MH 文字版 23 局、gol.gg 24 局（08-01 DK vs GEN 第 2 局只有 PB 有，
    # 連 Cargo 的 ScoreboardGames 都還沒填）。MH 沒有的局就用 PB 補一筆。
    # **不造假選手資料**（使用者定案）：PB 只有隊伍／勝負／版本／BP，沒有選手、KDA、路線
    # → 補出來的局**只有隊伍列**，不產生五名選手列，那局就不計入任何選手／路線統計。
    # 兩個已知的近似（PB 頁給不了，且無從查證）：
    #   ①**藍紅方**：PB 的 Team1／Team2 是賽程隊伍一二、不是藍紅（實測 33 局裡 20 局 T1 是紅方），
    #     2026 新制先選方又與藍紅脫鉤 → 這裡取 Team1 當藍方（同時也是先選方，自洽）。
    #   ②**時間**：PB 沒有日期 → 取前後最近「有對到 MH」的那一局的日期，時間往後推。
    # 兩者在 gol.gg／OE 補上該局後都會被取代（merge_ 系列一律以先者為準）。
    if PB:
        _mhkeys = {frozenset(pbn(c) for c in (SPL(g.get("Picks")) + SPL(g.get("Picks2")))) for g in games}
        _pbchrono = list(PB.items())[::-1]        # PB 頁是新→舊 → 反轉成時間正序
        _dates = [next((g.get("Date", "")[:19] for g in games
                        if frozenset(pbn(c) for c in (SPL(g.get("Picks")) + SPL(g.get("Picks2")))) == k), "")
                  for k, _ in _pbchrono]
        _add, _seq = [], 0
        for i, (k, m) in enumerate(_pbchrono):
            if k in _mhkeys:
                _seq = 0
                continue
            base_dt = next((d for d in _dates[i::-1] if d), "") or next((d for d in _dates[i:] if d), "")
            if not base_dt:
                continue                          # 整頁都對不到 → 無從推日期，寧可不補
            _seq += 1
            hh = min(23, int(base_dt[11:13] or 0) + _seq)
            _add.append({"Date": f"{base_dt[:10]} {hh:02d}:{base_dt[14:16] or '00'}:00",
                         "Blue": m["t1"], "Red": m["t2"], "Winner": m["win"], "P": m["patch"],
                         "Picks": ",".join(m["p"][0]), "Picks2": ",".join(m["p"][1]),
                         "Bans": ",".join(m["b"][0]), "Bans2": ",".join(m["b"][1]),
                         "Blue Roster": "", "Red Roster": "", "Len": "", "_pbonly": True})
        if _add:
            games = sorted(games + _add, key=lambda g: g.get("Date", "")[:19])
            print(f"    PB 補局：MH 沒有但 PB 有的 {len(_add)} 局（只補隊伍列，不含選手資料）")
    ser = {}
    for g in games:
        dt = g.get("Date", "")[:19]
        d10 = dt[:10]
        n = day.get(d10, 0) + 1
        day[d10] = n
        _pair = frozenset((nk(g.get("Blue")), nk(g.get("Red"))))
        _prev = ser.get(_pair)
        if _prev and _hh(_prev[0], dt) <= SERIES_GAP_H:
            gno, _start, _sn = _prev[1] + 1, _prev[2], _prev[3]
        else:
            gno, _start = 1, d10
            _sn = sday.get(d10, 0) + 1          # 這天的第幾個系列賽（表格已是時間正序）
            sday[d10] = _sn
        # 比對用「上一局的原始時間」，這樣連續跨天（04-28 23:00→04-29 00:00）也接得上；
        # 寫進資料的日期則統一成系列賽第一局那天（使用者定案 2026-07-31），
        # 免得同一個 BO5 在前端被日期切成兩段。
        ser[_pair] = (dt, gno, _start, _sn)
        # 時間整段重算成「當天第幾個系列 × 10 ＋ 局號」，不沿用 wiki 的原始時鐘。
        # 原因：日期已被統一成系列第一局那天，但原始時間還是各局自己的——跨午夜的
        # BO5 會變成 g1=23:00、g2=00:00，時序整個顛倒（實測 NA LCS 2013 春季決賽）。
        # 而且同一天的季軍賽與決賽若時間相同，fetch_data 依 (日期,局號) 排序就分不出
        # 先後（使用者回報決賽被排到季軍賽下面）。
        # 表格已反轉成時間正序，所以「第幾個系列」本身就是正確的先後。
        _mm = _sn * 10 + gno
        dt = f"{_start} {_mm // 60:02d}:{_mm % 60:02d}:00"
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
        # 真實選角順序（Picks and Bans 頁）；查不到就回 None，下面退回路線序
        od = pb_of(PB, picks["blue"], picks["red"])
        if od and _yr < 2026 and not od[4]:
            pb_bad += 1; od = None        # 舊制藍方必先選 → 判成紅方先選＝對齊錯了，寧可不用
        if PB:
            pb_hit += bool(od); pb_miss += not od
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
            put("game", gno)
            put("patch", _patch(g.get("P", "") or cfg.get("patch", ""), cfg.get("year", 0)))
            put("participantid", pid)
            # firstPick 一定要填（2026-08-02 修）：OE 表頭本來就有這欄，所以 fetch_data 的
            # 「沒有這欄就補藍方＝先選」那段**不會觸發**，留空的話 int("") 例外 → first=0
            # → 整批 wiki 局的藍方都被當成後選方，順位全反。
            # 有 PB 就用真值（T1＝先選方）；沒有的話 2025 以前藍方必先選（正解），
            # 2026 起是新制、藍方先選只是猜（下面會印出筆數）。
            put("firstPick", "1" if (side == "blue") == (od[4] if od else True) else "0")
            put("side", side.capitalize()); put("position", pos)
            put("teamname", bt if side == "blue" else rt)
            put("result", "1" if (bwin if side == "blue" else not bwin) else "0")
            put("gamelength", secs)
            put("teamkills", obj[side]["k"]); put("teamdeaths", obj["red" if side == "blue" else "blue"]["k"])
            return r, put

        for side in ("blue", "red"):
            for i in range(5) if not g.get("_pbonly") else ():   # PB 補的局沒有選手資料 → 只出隊伍列
                pid = i + 1 if side == "blue" else i + 6
                r, put = base(side, POS5[i], pid)
                nm = roster[side][i] if i < len(roster[side]) else ""
                nm = re.sub(r"\s*\(.*?\)$", "", nm).strip()      # 「Woong (Jang Gun-woong)」→ Woong
                put("playername", pname(align(nm, players_map)))   # 對齊 OE 的統一寫法（bengi→Bengi）
                put("champion", align(picks[side][i] if i < len(picks[side]) else "", champs_map))
                rows.append(r)
            r, put = base(side, "team", 100 if side == "blue" else 200)
            # ban1~5／pick1~5 要的是**選角順序**，不是路線序——fetch_data 的 calc_po 直接拿
            # 這裡的索引去查順位表。文字版 MH 的 Picks 是路線序，所以優先用 Picks and Bans 頁
            # 的真實順序；那頁對不到才退回（退回時順位會是假的，所以最後會印出筆數警告）。
            _p = (od[0] if side == "blue" else od[1]) if od else picks[side]
            _b = (od[2] if side == "blue" else od[3]) if od else bans[side]
            # wiki 用字串 "None" 表示「那一手真的沒禁」→ 存成空字串（位置照留，前端才畫得出空 BAN 圖）。
            # 直接丟給 align() 會變成一隻叫 None 的英雄（2026-07-31 使用者回報比賽BP 出現 None）。
            for i2, ch in enumerate(_b[:5]):
                put(f"ban{i2+1}", "" if str(ch).strip().lower() in ("none", "") else align(ch, champs_map))
            for i2, ch in enumerate(_p[:5]):
                put(f"pick{i2+1}", align(ch, champs_map))
            o = obj[side]
            put("totalgold", o["g"].replace(".", "") if o["g"] else "")
            put("towers", o["t"]); put("dragons", o["d"]); put("barons", o["b"])
            put("heralds", o["h"]); put("void_grubs", o["v"])
            rows.append(r)
    if PB:
        msg = f"    選角順序：Picks and Bans 頁對到 {pb_hit} 局"
        if pb_bad:
            msg += f"、剔除 {pb_bad} 局（判成紅方先選，但 {_yr} 年藍方必先選＝對齊錯了）"
        if pb_miss:
            msg += f"、對不到 {pb_miss} 局（順位退回路線序＝假的"
            msg += "，先選方用藍方＝正解）" if _yr < 2026 else "，先選方只能猜藍方＝新制未必對）"
        print(msg)
    else:
        print(f"    ⚠ 沒有 Picks and Bans 頁 → 順位退回路線序（假的）"
              + ("；先選方藍方＝舊制正解" if _yr < 2026 else "；先選方新制無從得知，暫用藍方"))
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
