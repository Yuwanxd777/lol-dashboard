# -*- coding: utf-8 -*-
"""從 Leaguepedia 的「Picks and Bans」頁抓比賽（2013-2015 小賽區專用）

背景（2026-07-31 使用者提供連結）：2013 的 CBLOL／拉美／台灣區資格賽／大洋洲／CIS／土耳其／GPL
在 MatchHistoryGame（ScoreboardGames）裡是 0 局——那張表只收有完整逐局數據的比賽。
但這些賽事都有人工整理的 `{賽事}/Picks and Bans` 頁，裡面有**隊伍、禁用、選用、勝方、局號**。

能拿到什麼、拿不到什麼（很重要，別誤以為資料是完整的）：
  ✔ 藍紅隊名、3+3 禁用、5+5 選用、勝方、系列賽內局號
  ✔ **路線＝推定值**：PB 頁的 5 個 pick 是「選擇順序」（第幾手），不是路線順序。
    用該年「英雄→路線」分布（取自同年有選手名的比賽）做 5×5 最佳指派排回五路，
    產生 participantid 1-5／6-10 的選手列（使用者指定 2026-07-31）。
    實測 Keyd vs RMA g1 紅方 pick 序 TF→Caitlyn→Nasus→Renekton→Lulu，
    正確排成 Renekton(TOP)／Nasus(JNG)／TF(MID)／Caitlyn(BOT)／Lulu(SUP)
    ——Nasus 2013 有 81% 在打野，照 pick 序硬排就會錯。
  ✔ **選手名＝賽事登錄名單**：PB 頁沒有，但賽事主頁的參賽名單有，而且是照
    TOP→JNG→MID→BOT→SUP 排的（使用者提供 2026-07-31：CBLOL 2013 Keyd Team＝
    Mylon／Revolta／Snowlz／Haelz／Loop）。位置既然已經推定，就能把名字填回去。
    **是「該賽事的登錄名單」不是逐局先發**——有替補或位置輪換就會掛錯人，
    所以只在該隊五個位置齊全時才填。這批資料會進選手生涯統計。
  ✘ 日期（PB 頁沒有）→ 從賽事主頁的比賽列表依「隊伍組合」配對；配不到就退用賽事起始日。

輸出：csv_cache/wikifill_{年}.json（與 fetch_wiki_mh 同一個檔、同一套 key），
由 fetch_data.merge_wiki() 併入，OE 之後若補上這些比賽會自動以 OE 為準。

用法：
  python scripts\fetch_wiki_pb.py                 # 跑 JOBS 全部
  python scripts\fetch_wiki_pb.py --probe "Riot Season 3 Brazilian Championship"
"""
import argparse, collections, csv, glob, html as _html, io, itertools, json, os, re, sys, time, urllib.parse, urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, "csv_cache")
HTML_DIR = os.path.join(CACHE, "wikipb")
sys.path.insert(0, HERE)

API = "https://lol.fandom.com/api.php"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
GAP = 3.0

# (年, 聯賽碼, 賽段, 季後賽, PB 頁, 取日期用的主頁)
JOBS = [
    # LPL 2013 夏季季後賽改由 backfill_run 走 /Match History 嵌入表（有選手名單，比 PB 頁完整）
    (2013, "GPL", "春季", 0, "2013 GPL Spring/Picks and Bans", "2013 GPL Spring"),
    (2013, "GPL", "夏季", 0, "2013 GPL Summer/Picks and Bans", "2013 GPL Summer"),
    # 賽段寫「夏季」就好，PO 後綴由 fetch_data 依 playoffs 欄自己加；
    # 自己先寫 "夏季 PO" 會變成「夏季 PO PO」，前端只去掉一個 PO → 賽事卡多長出一列（2026-07-31）
    # 賽事名叫 Championship／Regional Finals 的，賽段一律標「錦標賽」（使用者定案 2026-07-31）
    # TESL（台灣電子競技聯盟職業挑戰賽）：與 GPL 夏季同期進行的台灣本土聯賽，
    # MatchHistory 沒收（0 局）但 PB 頁有 75 局。使用者指定放在 GPL 底下、夏季之後（2026-07-31）
    (2013, "GPL", "TESL", 0, "Taiwan eSports League/Professional Challenges/Picks and Bans",
     "Taiwan eSports League/Professional Challenges"),
    # GPL 的兩個錦標賽分開標（使用者定案 2026-07-31）：
    #   台港澳＝GPL 年度總決賽（春夏冠軍對決，兩隊都是台灣隊）＋台灣區世界賽代表選拔
    #   東南亞＝Season 3 Southeast Asia Regional Finals（KLH／SGS／SAJ／BKT／Mineski／Xgame 六隊；
    #           Qualifiers 不列，PB 頁本來就只收正賽 11 局）
    (2013, "GPL", "台港澳錦標賽", 0, "2013 GPL Championship/Picks and Bans", "2013 GPL Championship"),
    (2013, "GPL", "台港澳錦標賽", 0, "Season 3 Taiwan Regional Finals/Picks and Bans",
     "Season 3 Taiwan Regional Finals"),
    (2013, "GPL", "東南亞錦標賽", 0, "Season 3 Southeast Asia Regional Finals/Picks and Bans",
     "Season 3 Southeast Asia Regional Finals"),
    (2013, "CBLOL", "錦標賽", 0, "Riot Season 3 Brazilian Championship/Picks and Bans",
     "Riot Season 3 Brazilian Championship"),
    # LLA 2013 是三段獨立賽事寫在同一頁（使用者提供 2026-07-31）：南區、北區各自打完，
    # 冠軍再打 Grand Finals。sections＝用 h2 章節把賽段拆開；roster_pages＝南北區的
    # 參賽名單在各自的 Qualifiers 子頁，主頁只有進總決賽的兩隊。
    (2013, "LLA", "錦標賽", 0, "Season 3 Latin America Regional Finals/Picks and Bans",
     "Season 3 Latin America Regional Finals",
     {"sections": {"Latin America South": "南區", "Latin America North": "北區",
                   "Latin America Grand Finals": "錦標賽"},
      "roster_pages": ["Season 3 Latin America Regional Finals/Qualifiers/Southern Qualifier",
                       "Season 3 Latin America Regional Finals/Qualifiers/Northern Qualifier"]}),
    (2013, "LCO", "錦標賽", 0, "Riot Season 3 Oceanic Championship/Picks and Bans",
     "Riot Season 3 Oceanic Championship"),
    (2013, "LCL", "錦標賽", 0, "2013 Season CIS Championship/Picks and Bans", "2013 Season CIS Championship"),
    # 2015 GPL：MatchHistory 是 0 局，但 PB 頁有（春 96／夏 49）
    (2015, "GPL", "春季", 0, "2015 GPL Spring/Picks and Bans", "2015 GPL Spring"),
    (2015, "GPL", "夏季", 0, "2015 GPL Summer/Picks and Bans", "2015 GPL Summer"),
    # 土耳其：冬／春／夏三個 Tournament 沒有 PB 子頁，但年度總決賽 Championship 有（21 局）。
    # 使用者提供 2026-07-31：Gamescom 外卡賽的土耳其席次就是「Season 3 Turkish Championship winner」
    (2013, "TCL", "錦標賽", 0, "Riot Games Turkey/2013 Season/Championship/Picks and Bans",
     "Riot Games Turkey/2013 Season/Championship"),
]


def parse_page(page, force=False):
    """action=parse 的 HTML（存快取，可離線重跑）"""
    os.makedirs(HTML_DIR, exist_ok=True)
    fp = os.path.join(HTML_DIR, re.sub(r"[^A-Za-z0-9]+", "_", page)[:120] + ".html")
    if not force and os.path.exists(fp):
        return open(fp, encoding="utf-8").read()
    url = API + "?" + urllib.parse.urlencode({"action": "parse", "page": page, "prop": "text", "format": "json"})
    for i in range(4):
        try:
            r = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read())
        except Exception as e:
            print(f"      連線失敗（{i+1}/4）{str(e)[:70]}"); time.sleep(5 * (i + 1)); continue
        if "error" in r:
            raise RuntimeError(r["error"].get("info", "")[:150])
        h = r["parse"]["text"]["*"]
        open(fp, "w", encoding="utf-8").write(h)
        time.sleep(GAP)
        return h
    raise RuntimeError("重試多次仍失敗")


def pb_games(html):
    """PB 頁 → [{blue, red, game, win(1藍/2紅), bans{}, picks{}}]

    版型（實測 2013 各賽事一致）：一個 table.wikitable.pb ＝ 一局；
      td.pb-winner 內容就是 1／2；td.pb-ban／td.pb-pick 帶 pb-blue／pb-red，
      class 後面還會多掛 pb-border 之類的修飾 → 比對要寬鬆，不能寫死整串 class。
    """
    out = []
    # 章節標題（Group A／Group B／Semifinals／Finals）→ 每局屬於哪個階段。
    # 用途是推日期：PB 頁沒有逐場日期，但賽事的階段順序就是時間順序（使用者定案
    # 2026-07-31：CBLOL 2013 小組賽 7/19、四強 7/20、決賽 7/21）。
    # 兩層都要留：h2 常是「賽區／大區塊」（LLA 2013 分 Latin America South／North／
    # Grand Finals），h3 才是輪次（Semifinals／Finals）。只取最近的一個標題會把
    # 南北區丟掉，整個賽事被壓成同一個賽段（2026-07-31 使用者回報）。
    _hd = [(m.start(), int(m.group(1)),
            re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(2))).replace("[]", "").strip())
           for m in re.finditer(r"<h([2-4])[^>]*>(.*?)</h\1>", html, re.S)]
    for _ti, _mt in enumerate(re.finditer(r'<table[^>]*class="[^"]*wikitable pb[^"]*"[^>]*>.*?</table>', html, re.S)):
        t = _mt.group(0)
        sec2 = sec3 = ""
        for _hp, _lv, _ht in _hd:
            if _hp >= _mt.start() or not _ht or _ht.lower() == "contents":
                continue
            if _lv == 2:
                sec2, sec3 = _ht, ""
            else:
                sec3 = _ht
        stage = sec3 or sec2
        cls = re.search(r'class="([^"]*)"', t).group(1)
        mg = re.search(r"pb-game-(\d+)", cls)
        teams = re.findall(r'<a href="/wiki/[^"]+" class="[^"]*\bt[A-Z]{2,}\b[^"]*" title="([^"]+)"', t)
        if len(teams) < 2:
            teams = re.findall(r'class="team-object">.*?title="([^"]+)"', t, re.S)
        # 勝方判定：比分列長這樣 → [藍方比分][show/hide][紅方比分]，**帶 pb-winner class 的那一側就是勝方**。
        # 格子裡的數字是「系列賽比分」不是勝方編號（實測會出現 0／1／3）→ 只看數字一定判錯
        #（2026-07-31 使用者回報：LCO 的 Team Immunity 明明 4W0L 卻寫成 0W4L）
        win, sb, sr = 0, None, None
        for tr in re.findall(r"<tr.*?</tr>", t, re.S):
            if "pb-winner" not in tr:
                continue
            cells = re.findall(r"<td([^>]*)>(.*?)</td>", tr, re.S)
            if len(cells) >= 3:
                win = 1 if "pb-winner" in cells[0][0] else (2 if "pb-winner" in cells[2][0] else 0)

                def _num(x):
                    m2 = re.search(r"\d+", re.sub(r"<[^>]+>", "", x))
                    return int(m2.group(0)) if m2 else None
                sb, sr = _num(cells[0][1]), _num(cells[2][1])
            break
        # 局號＝比分列兩數相加。那兩個數是「系列賽累計比分」，所以第 N 局結束時總和就是 N
        #（實測 CBLOL 決賽 CNB vs paiN：1-0→g1、1-1→g2、1-2→g3、3-1→g4）。
        # **不能用 class 的 pb-game-N**：20 局裡只有 5 局帶這個 class，其餘全被當成第 1 局
        # → BO5 被當成 4 次不同遭遇，日期推算把它們拆到 3 個不同天（2026-07-31 使用者回報）
        gno = (sb + sr) if (sb is not None and sr is not None and 1 <= sb + sr <= 7) \
            else (int(mg.group(1)) if mg else 1)
        bp = {"blue": {"ban": [], "pick": []}, "red": {"ban": [], "pick": []}}
        for m in re.finditer(r'<td class="[^"]*\bpb-(ban|pick)\b[^"]*\bpb-(blue|red)\b[^"]*"[^>]*>(.*?)</td>', t, re.S):
            k, s, body = m.group(1), m.group(2), m.group(3)
            c = re.search(r'title="([^"]+)"', body)
            nm = _html.unescape(c.group(1)).strip() if c else ""
            # wiki 用「Missing Data」標示沒有禁用的空格（2013 GPL 有 96 處）＝空 BAN，
            # 不是英雄名。使用者指定改寫成「?」（2026-07-31），否則會被當成一隻叫
            # Missing Data 的英雄混進 banlist。
            if nm.lower() in ("missing data", "missingdata"):
                nm = "?"
            bp[s][k].append(nm)
        if len(teams) < 2 or not bp["blue"]["pick"]:
            continue
        # wiki 沒建隊伍頁的小隊，title 會是「FIGJAM (page does not exist)」→ 後綴一定要剝掉，
        # 不然那個字串會變成資料庫裡的隊名，縮寫表永遠查不到、篩選列只好顯示全名
        #（2026-07-31 使用者回報：手動改的縮寫沒套用、還是出現全名）
        _tn = lambda s: re.sub(r"\s*\(page does not exist\)\s*$", "", _html.unescape(s)).strip()
        out.append({"blue": fix_case(_tn(teams[0])), "red": fix_case(_tn(teams[1])), "idx": _ti,
                    "game": gno, "win": win, "bp": bp, "stage": stage, "sec2": sec2, "sec3": sec3})
    return out


def dates_of(html):
    """主頁 → [(日期, 隊A, 隊B)]；比賽列表每列都帶日期與兩隊"""
    out = []
    for m in re.finditer(r'<div class="matchlist-[^"]*"[^>]*>.*?</div>\s*</div>', html, re.S):
        pass
    # matchlist 的實際結構逐年不同 → 直接掃「日期 ... 兩個隊連結」的鄰近關係
    for m in re.finditer(r'(20\d\d-\d\d-\d\d)(.{0,900}?)(?=20\d\d-\d\d-\d\d|$)', html, re.S):
        d, seg = m.group(1), m.group(2)
        tms = re.findall(r'<a href="/wiki/[^"]+" class="[^"]*\bt[A-Z]{2,}\b[^"]*" title="([^"]+)"', seg)
        tms = [_html.unescape(x).strip() for x in tms]
        uniq = []
        for x in tms:
            if x not in uniq:
                uniq.append(x)
        if len(uniq) >= 2:
            out.append((d, uniq[0], uniq[1]))
    return out


def bracket_pairs(html):
    """主頁季後賽對戰表的配對 {frozenset(隊A,隊B), ...}。

    2013 這些小賽事的小組賽與季後賽寫在同一個 PB 頁，wiki 也沒有獨立的 Playoffs 賽事
    → 用主頁 bracket 的對戰組合來認季後賽（使用者 2026-07-31：CBLOL 也有季後賽，在底下有寫）。
    """
    tms = []
    for m in re.finditer(r'<div class="bracket-team[^"]*"[^>]*>(.*?)(?=<div class="bracket-team|</div>\s*</div>)',
                         html, re.S):
        t = re.search(r'title="([^"]+)"', m.group(1))
        if t:
            tms.append(re.sub(r"\s*\(page does not exist\)\s*$", "", _html.unescape(t.group(1))).strip())
    out = set()
    for i in range(0, len(tms) - 1, 2):      # bracket 內兩兩成對
        a, b = _norm(tms[i]), _norm(tms[i + 1])
        if a and b and a != b:
            out.add(frozenset((a, b)))
    return out


def mark_po(games, pairs):
    """由後往前掃：符合對戰表配對的局標成季後賽。

    小組賽也可能出現同樣的兩隊 → 連續 3 局都對不上就停，不再往前標。
    """
    if not pairs:
        return 0
    n, miss = 0, 0
    for g in reversed(games):
        if frozenset((_norm(g["blue"]), _norm(g["red"]))) in pairs:
            g["po"] = 1; n += 1; miss = 0
        else:
            miss += 1
            if miss >= 3:
                break
    return n


def span_of(html):
    """賽事期間：優先取 infobox 的 Start Date／End Date。

    全頁掃日期取最早最晚會撈到不相關的——實測 CBLOL 2013 的 infobox 明明寫
    07-19~07-21，但賽程表裡有一列「Mon 2013-07-22」，害期間多出一天、
    階段推算整個往後挪（2026-07-31 使用者提供正確值）。
    """
    def _lbl(name):
        m = re.search(name + r".{0,120}?(20\d\d-\d\d-\d\d)", html, re.S | re.I)
        return m.group(1) if m else ""
    s, e = _lbl("Start Date"), _lbl("End Date")
    if s and e and s <= e:
        return (s, e)
    ds = sorted(set(re.findall(r"\b(20\d\d-\d\d-\d\d)\b", html)))
    return (ds[0], ds[-1]) if ds else ("", "")


_norm = lambda s: re.sub(r"[^a-z0-9]", "", str(s or "").lower())
_TNAME = None


def fix_case(nm):
    """對齊主資料的隊名寫法。

    PB 頁的隊名取自連結 title，走 MediaWiki 頁名規則＝首字母一定大寫
    （paiN Gaming → PaiN Gaming）→ 跟世界賽那邊的 paiN Gaming 變成兩支不同的隊，
    「這隊有沒有打進世界賽」就判不出來（2026-07-31 實測 CBLOL 的 paiN 對不上）。
    以 2016 年起的 OE 原生資料為權威寫法（2015 以前混有 wiki 補的，不能當基準）。
    """
    global _TNAME
    if _TNAME is None:
        import glob
        _TNAME = {}
        for p in sorted(glob.glob(os.path.join(ROOT, "data", "data_*.js"))):
            try:
                if int(os.path.basename(p)[5:9]) < 2016:
                    continue
                R = json.loads(open(p, encoding="utf-8").read().split("=", 1)[1].strip().rstrip(";"))["tabs"]["RAW_DATA"]
            except Exception:
                continue
            ix = {n: i for i, n in enumerate(R[0])}
            for k in ("blue_teamname", "red_teamname"):
                if k not in ix:
                    continue
                for r in R[1:]:
                    v = str(r[ix[k]] or "").strip()
                    if v:
                        _TNAME.setdefault(v.casefold(), v)
    return _TNAME.get(str(nm or "").casefold(), nm)


POSL = ["TOP", "JNG", "MID", "BOT", "SUP"]
_PID2POS = {1: "TOP", 2: "JNG", 3: "MID", 4: "BOT", 5: "SUP"}
# OE 的 position 欄位值（process() 只靠 participantid 判位，這欄是給人看的）
_POS_OE = {"TOP": "top", "JNG": "jng", "MID": "mid", "BOT": "bot", "SUP": "sup"}
_LANE_CACHE = {}


def pb_segments(year):
    """該年由本檔（PB 頁）產生的 (聯賽, 賽段)——這些列的路線是推定值，
    不能拿回來當統計證據。src 標記存在 wikifill_{年}.json 裡。"""
    out = set()
    p = os.path.join(CACHE, f"wikifill_{year}.json")
    if os.path.exists(p):
        try:
            for v in json.load(open(p, encoding="utf-8")).values():
                if "Picks and Bans" in str(v.get("src", "")):
                    out.add((str(v.get("league") or ""), str(v.get("split") or "").split(" PO")[0]))
        except Exception:
            pass
    return out


def lane_stats(year):
    """該年「英雄→各路線出場次數」，取自 data_{年}.js 的**真實**列。

    PB 頁只給英雄與**選擇順序**（第幾手），不是路線順序，所以要靠這張表把 5 個
    pick 排回 TOP/JNG/MID/BOT/SUP。

    **必須排除本檔自己產生的賽段**，否則第二次跑會把上一輪的推定值當成證據自我
    強化。原本靠「沒有選手名」就能濾掉，但自從選手名改成從參賽名單填回去之後，
    PB 的列也有名字了 → 改用 wikifill 的 src 標記逐賽段排除。"""
    if year in _LANE_CACHE:
        return _LANE_CACHE[year]
    st = collections.defaultdict(collections.Counter)
    skip = pb_segments(year)
    p = os.path.join(ROOT, "data", f"data_{year}.js")
    if os.path.exists(p):
        try:
            J = json.loads(open(p, encoding="utf-8").read().split("=", 1)[1].strip().rstrip(";"))
            T = J["tabs"]["RAW_DATA"]
            ix = {n: i for i, n in enumerate(T[0])}
            RB = ix["red_champion"] - ix["blue_champion"]
            for r in T[1:]:
                try:
                    pid = int(r[ix["participantid"]])
                except Exception:
                    continue
                if pid not in _PID2POS:
                    continue
                if (str(r[ix["league"]] or ""), str(r[ix["split"]] or "").split(" PO")[0]) in skip:
                    continue                      # 本檔推定的賽段，不當證據
                for side in (0, 1):
                    o = RB if side else 0
                    nm = str(r[ix["blue_playername"] + o] or "").strip()
                    ch = str(r[ix["blue_champion"] + o] or "").strip()
                    if ch and nm:
                        st[ch][_PID2POS[pid]] += 1
        except Exception as e:
            print(f"    ⚠ 路線統計失敗（改用平均分配）：{str(e)[:70]}")
    _LANE_CACHE[year] = st
    return st


def assign_lanes(champs, st):
    """5 個 pick（依選擇順序）→ 指派到 TOP/JNG/MID/BOT/SUP。

    5×5 完美匹配，5!=120 種直接窮舉取聯合機率最大者（不必上匈牙利演算法）。
    +0.02 平滑：某英雄該年沒打過某路線時機率為 0，整條排列會被歸零，
    導致有解也選不出來。"""
    champs = [str(c or "").strip() for c in champs][:5]
    if len(champs) < 5:
        champs += [""] * (5 - len(champs))

    def pr(ch, pos):
        c = st.get(ch)
        if not c:
            return 0.2                      # 該年沒資料 → 五路均等
        n = sum(c.values()) or 1
        return c.get(pos, 0) / n

    best, bs = tuple(range(5)), -1.0
    for perm in itertools.permutations(range(5)):
        s = 1.0
        for i, j in enumerate(perm):
            s *= pr(champs[i], POSL[j]) + 0.02
        if s > bs:
            bs, best = s, perm
    out = [""] * 5
    for i, j in enumerate(best):
        out[j] = champs[i]
    return out                               # [TOP, JNG, MID, BOT, SUP]


_ROS_CACHE = {}


def tour_rosters(page):
    """賽事主頁的參賽名單 → {正規化隊名: {位置: 選手名}}。

    PB 頁只有英雄，沒有選手名；但賽事主頁有「Team Rosters／Participants」表，
    而且是照 TOP→JNG→MID→BOT→SUP 排的（使用者提供 2026-07-31：CBLOL 2013
    Keyd Team＝Mylon／Revolta／Snowlz／Haelz／Loop）。
    英雄的位置已由 assign_lanes 推定，對上位置就能把名字填回去。

    來源用 Cargo 表 TournamentPlayers（見 fetch_events_extra.cargo_rosters），
    不吃 HTML 版型。**這是「該賽事的登錄名單」不是逐局先發**：有替補或位置輪換
    就會掛錯人，所以只在該隊剛好五個位置各一人時才填。
    """
    if page in _ROS_CACHE:
        return _ROS_CACHE[page]
    out = {}
    try:
        import fetch_events_extra as EE
        for tm, pl in (EE.cargo_rosters(page) or {}).items():
            m = {}
            for p in pl:
                r = p.get("r")
                if r in POSL and r not in m:
                    m[r] = p.get("n") or ""
            if len(m) == 5:            # 五個位置齊全才用，缺角就整隊不填
                out[_norm(tm)] = m
    except Exception as e:
        print(f"    ⚠ 參賽名單取得失敗（選手名留空）：{str(e)[:70]}")
    _ROS_CACHE[page] = out
    return out


def _ros_of(ros, team):
    """查該隊名單，隊名允許互為前綴。PB 頁常用短名、名單頁用全名
    （Renegades of Hell↔Renegades of Hell Inner Fire、Isurus↔Isurus Gaming Chile），
    精確比對會整隊填不到名字。"""
    k = _norm(team)
    if not k:
        return {}
    if k in ros:
        return ros[k]
    for kk, v in ros.items():
        if kk and (kk.startswith(k) or k.startswith(kk)):
            return v
    return {}


_PBD_CACHE = {}


_REL_CACHE = None


def patch_release():
    """改版日期表 {儀表板版本碼: 發布日}，由 scripts/fetch_patch_release.py 從
    LoL wiki 的版本頁（Infobox 的 Release 欄）抓來。"""
    global _REL_CACHE
    if _REL_CACHE is None:
        p = os.path.join(CACHE, "patch_release.json")
        try:
            _REL_CACHE = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
        except Exception:
            _REL_CACHE = {}
    return _REL_CACHE


def patch_by_release(date):
    """比賽日期 → 該日在線的版本（OE 原始格式，process() 會再 +10）。

    使用者定案 2026-07-31：**用改版日期回推，不要用同期比賽在打哪一版**。
    找最後一個「發布日 <= 比賽日」的版本即可。
    """
    rel = patch_release()
    if not rel or not date:
        return ""
    best, bd = "", ""
    for k, d in rel.items():
        if d and d <= date[:10] and d > bd:
            bd, best = d, k
    if not best:
        return ""
    m = re.match(r"^(\d+)\.(\d+)$", best)          # 13.08 → 3.08（存的是儀表板碼）
    return f"{int(m.group(1)) - 10}.{m.group(2)}" if m else ""


def patch_by_date(year):
    """該年的「日期→版本」對照，用來推定 PB 頁比賽的版本。

    PB 頁沒有版本欄，但**同一天的職業賽幾乎都打同一版**，所以拿同年其他有版本號
    的比賽（csv_cache/lpgames，scripts/fetch_wiki_stats.py 抓的 ScoreboardGames）
    建時間軸來回推。實測 2013-07-19~21（CBLOL 決賽那三天）每天都有 3.8 的場次，
    下一版 3.9 要到 8/2 才開打 → 那場就是 3.8。
    版本號的尾隨 0 會被 Cargo 截掉（4.10→4.1），沿用 fetch_wiki_stats 的還原邏輯。
    """
    if year in _PBD_CACHE:
        return _PBD_CACHE[year]
    day = collections.defaultdict(collections.Counter)
    try:
        import fetch_wiki_stats as WS
        raw = []
        for p in glob.glob(os.path.join(CACHE, "lpgames", "*.json")):
            try:
                items = json.load(open(p, encoding="utf-8"))
            except Exception:
                continue
            for x in items:
                m = re.match(r"^\s*(\d{1,2})\.(\d{1,2})\s*$", str(x.get("pt") or ""))
                d = str(x.get("dt") or "")[:10]
                if m and d.startswith(str(year)):
                    raw.append((int(m.group(1)), int(m.group(2)), d))
        fix = WS.fix_trailing_zero(raw)
        for major, minor, d in raw:
            # **填 OE 原始格式（3.08），不是儀表板格式（13.08）**：本檔的列是走 CSV
            # 進 fetch_data.process()，那裡會統一做 float(patch)+10。先轉好會被加兩次
            #（實測變成 23.08）。fetch_wiki_stats 的 merge_stats 是直接填進 process 之後
            # 的表，那邊才要填 13.08。
            day[d][f"{major}.{fix.get((major, minor, d), minor):02d}"] += 1
    except Exception as e:
        print(f"    ⚠ 版本對照建立失敗（版本欄留空）：{str(e)[:70]}")
    out = {d: c.most_common(1)[0][0] for d, c in day.items()}
    _PBD_CACHE[year] = out
    return out


def patch_of(pbd, date, span=7):
    """查該日版本。

    **以改版日期為準**（使用者定案 2026-07-31）：改版日表查得到就用它，
    查不到才退回「同期其他比賽在打哪一版」。
    註：兩者會有落差，職業賽常鎖舊版——2013-07-19 那批，改版日算是 3.9
    （7/9 發布），但同期 LPL 實際還在打 3.8。使用者要的是前者。
    """
    v = patch_by_release(date)
    if v:
        return v
    if not pbd or not date:
        return ""
    if date in pbd:
        return pbd[date]
    from datetime import date as _dt
    try:
        d0 = _dt(*map(int, date[:10].split("-")))
    except Exception:
        return ""
    best, gap = "", 10 ** 9
    for d, v in pbd.items():
        try:
            g = abs((_dt(*map(int, d.split("-"))) - d0).days)
        except Exception:
            continue
        if g < gap:
            gap, best = g, v
    return best if gap <= span else ""


def build(job, force=False):
    year, lg, split, po, pb_page, main_page = job[:6]
    # 第 7 個元素（選用）：{"sections": {h2 章節: 賽段名}, "roster_pages": [額外名單頁]}
    opt = job[6] if len(job) > 6 and isinstance(job[6], dict) else {}
    SECMAP = opt.get("sections") or {}
    key = f"{lg}_{year}_" + (re.sub(r"[^A-Za-z0-9]+", "", split) or re.sub(r"[^A-Za-z0-9]+", "", pb_page)[:24])
    print(f"\n[{year} {lg} {split or '（無賽段）'}] ← {pb_page}")
    try:
        html = parse_page(pb_page, force)
    except Exception as e:
        print(f"    PB 頁失敗：{str(e)[:110]}"); return None
    games = pb_games(html)
    print(f"    解析到 {len(games)} 局")
    if not games:
        return None
    # 日期：主頁的比賽列表 → 以隊伍組合配對；配不到用賽事起始日
    dmap, first, last = {}, "", ""
    try:
        mh = parse_page(main_page, force)
        first, last = span_of(mh)
        _npo = mark_po(games, bracket_pairs(mh))
        if _npo >= len(games):
            # 全部都符合對戰表＝整個賽事本來就是淘汰賽（大洋洲／CIS／土耳其／東南亞錦標賽），
            # 那就沒有「例行賽 vs 季後賽」可言 → 不標（2026-07-31）
            for _g in games:
                _g.pop("po", None)
            _npo = 0
        if _npo:
            print(f"    季後賽（依主頁對戰表）：{_npo} 局")
        for d, a, b in dates_of(mh):
            dmap.setdefault(frozenset((_norm(a), _norm(b))), []).append(d)
    except Exception as e:
        print(f"    主頁日期失敗（改用賽事起始日）：{str(e)[:70]}")
    if not first:
        first = last = f"{year}-01-01"

    import fetch_data
    hdr = fetch_data.oe_header() if hasattr(fetch_data, "oe_header") else None
    if not hdr:
        import fetch_fill
        hdr = fetch_fill.oe_header()
    ix = {n: i for i, n in enumerate(hdr)}
    rows, used, cur = [], {}, {}
    LST = lane_stats(year)
    print(f"    路線統計：{len(LST)} 個英雄（{year} 年有選手名的列）")
    PBD = patch_by_date(year)
    ROS = dict(tour_rosters(main_page))
    for _rp in (opt.get("roster_pages") or ()):     # 額外名單頁（分區資格賽等）
        for _k, _v in (tour_rosters(_rp) or {}).items():
            ROS.setdefault(_k, _v)
        time.sleep(2)
    if ROS:
        print(f"    參賽名單：{len(ROS)} 隊五個位置齊全 → 選手名可填")
    from datetime import date as _date, timedelta as _td
    _d0 = _date(*map(int, first.split("-")))
    _d1 = _date(*map(int, (last or first).split("-")))
    # ── 階段 → 日期：把賽事期間平均分給各階段（小組賽 → 四強 → 決賽）──
    # PB 頁沒有逐場日期，賽事又常只有兩三天。階段順序就是時間順序，比「同一組隊伍
    # 第 N 次遭遇往後挪一天」準得多——後者會把 BO5 的第 1 局跟後面幾局分到不同天。
    # Group A／Group B 併成同一個「小組賽」階段（使用者定案 2026-07-31：
    # CBLOL 2013 小組賽 7/19、四強 7/20、決賽 7/21）。
    def _sk(g):
        """階段鍵＝上層章節＋輪次。分區賽事（LLA 2013 南北區）兩邊都有 Semifinals，
        只用輪次會撞成同一階段；Group A／Group B 則相反，要併成一個小組賽階段。"""
        s2, s3 = str(g.get("sec2") or ""), str(g.get("sec3") or "")
        # 小組賽層級不固定：CBLOL 是 h2=Group Stage／h3=Group A，GPL 台港澳錦標賽
        # 直接把 Group A／Group B 當 h2。兩種都要併成同一個小組賽階段——不併的話
        # 兩個小組會被分到賽事期間的頭尾（實測 Group A=07-03、Group B=08-29）。
        if re.match(r"^\s*group\b", s3 or s2, re.I):
            return "Group Stage"
        return (s2 + "／" + s3) if (s2 and s3) else (s3 or s2)

    _stages = []
    for g in games:
        k = _sk(g)
        if k and k not in _stages:
            _stages.append(k)
    _span = (_d1 - _d0).days
    _sdate = {}
    if len(_stages) > 1 and _span > 0:
        for _k, _st in enumerate(_stages):
            _sdate[_st] = (_d0 + _td(days=round(_k * _span / (len(_stages) - 1)))).isoformat()
        print("    階段→日期：" + "、".join(f"{k}={v[5:]}" for k, v in _sdate.items()))
    for g in games:
        pair = frozenset((_norm(g["blue"]), _norm(g["red"])))
        ds = dmap.get(pair) or []
        # 「第幾次遭遇」要**整個系列賽共用一個**：第 1 局時取新的序號並記住，第 2 局之後
        # 沿用。原本在 g1 就把序號 +1，g2 之後拿到的是加過的值 → BO5 的第 1 局被推到前一天、
        # 跟後面幾局分家（2026-07-31 使用者回報 CBLOL 決賽 CNB vs paiN 被拆到 3 天）。
        if g["game"] == 1 or pair not in cur:
            i = used.get(pair, 0)
            used[pair] = i + 1
            cur[pair] = i
        else:
            i = cur[pair]
        if ds:
            date = ds[min(i, len(ds) - 1)]
        elif _sdate.get(_sk(g)):
            date = _sdate[_sk(g)]                   # 依階段（小組賽／四強／決賽）
        else:
            # 連階段標題都沒有 → 退回「同一組隊伍的第 N 次遭遇往後挪一天」（夾在賽事期間內）。
            # 全部塞同一天的話，小組賽與季後賽的同組對戰會被當成同一個系列，BO 判定就錯了。
            date = min(_d0 + _td(days=i), _d1).isoformat()
        # 隊名要用完整的正規化字串，不能截斷：Saigon Jokers 與 Saigon Fantastic Five 取前 6 字
        # 都是 saigon，gameid 會撞在一起互相覆蓋（實測 GPL 春季 56 局只剩 22 局）
        # 再帶上「第幾次遭遇」：賽事只有三四天時，同一組隊伍多次對戰的推得日期會被夾在同一天，
        # 光靠 日期＋局號 還是會撞（CBLOL 19 局少 1、CIS 7 局少 1）
        # 用「表格在頁面中的序號」當識別，保證唯一：局號會重複（同一頁多個系列都各有第 2 局），
        # 光靠 隊伍＋日期＋局號＋遭遇序 還是會撞（實測 LPL 2013 夏季季後賽 7 局只進 5 局）
        # 版本：PB 頁沒有這欄 → 用同年其他比賽的「日期→版本」時間軸推定
        _pt = patch_of(PBD, date)
        # 賽段：分區賽事用 h2 章節對照（LLA 2013 → 南區／北區／錦標賽），其餘沿用 JOBS 的值
        _sp = SECMAP.get(str(g.get("sec2") or ""), split)
        gid = f"wikipb_{key}_{g.get('idx', i)}_{_norm(g['blue'])}_{_norm(g['red'])}_{date}_{g['game']}"
        for side, pid in (("blue", 100), ("red", 200)):
            r = [""] * len(hdr)
            put = lambda k, v: r.__setitem__(ix[k], "" if v is None else str(v)) if k in ix else None
            put("gameid", gid); put("datacompleteness", "partial")
            put("league", lg); put("year", year); put("split", _sp)
            put("playoffs", 1 if g.get("po") else po)
            put("date", date + " 00:00:00"); put("game", g["game"]); put("participantid", pid)
            put("patch", _pt)
            put("side", side.capitalize()); put("position", "team")
            put("teamname", g[side])
            put("result", "1" if (g["win"] == (1 if side == "blue" else 2)) else "0")
            for i2, ch in enumerate(g["bp"][side]["ban"][:5]):
                put(f"ban{i2+1}", ch)
            for i2, ch in enumerate(g["bp"][side]["pick"][:5]):
                put(f"pick{i2+1}", ch)
            rows.append(r)
        # ── 逐選手列（participantid 1-5 藍／6-10 紅）──
        # PB 頁給的是英雄與**選擇順序**（第幾手），不是路線順序 → 用當年的英雄路線
        # 分布排回五路（使用者指定 2026-07-31）。少了這段，這些比賽只有隊伍列，
        # 英雄完全進不了圖鑑／英雄統計，等於白抓。選手名 wiki 沒有 → 留空。
        for side, base in (("blue", 1), ("red", 6)):
            lanes = assign_lanes(g["bp"][side]["pick"], LST)
            for k2, ch in enumerate(lanes):
                if not ch:
                    continue
                r = [""] * len(hdr)
                put2 = lambda k3, v: r.__setitem__(ix[k3], "" if v is None else str(v)) if k3 in ix else None
                put2("gameid", gid); put2("datacompleteness", "partial")
                put2("league", lg); put2("year", year); put2("split", _sp)
                put2("playoffs", 1 if g.get("po") else po)
                put2("date", date + " 00:00:00"); put2("game", g["game"])
                put2("patch", _pt); put2("participantid", base + k2)
                put2("side", side.capitalize())
                put2("position", _POS_OE[POSL[k2]])
                put2("teamname", g[side]); put2("champion", ch)
                put2("playername", (_ros_of(ROS, g[side]) or {}).get(POSL[k2], ""))
                put2("result", "1" if (g["win"] == (1 if side == "blue" else 2)) else "0")
                rows.append(r)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(hdr); w.writerows(rows)
    table = fetch_data.process(buf.getvalue(), year)
    print(f"    process() → {len(table)-1} 列（{len(games)} 局）"
          + (f"　主頁配到日期 {len(dmap)} 組" if dmap else f"　日期＝賽事期間 {first}~{last} 內依遭遇序遞推"))
    if len(table) < 2:
        return None
    p = os.path.join(CACHE, f"wikifill_{year}.json")
    D = {}
    if os.path.exists(p):
        try:
            D = json.load(open(p, encoding="utf-8"))
        except Exception:
            D = {}
    D[key] = {"header": table[0], "rows": table[1:], "games": len(games),
              "src": "leaguepedia Picks and Bans（無選手名；路線由當年英雄路線分布推定）", "tour": pb_page,
              "league": lg, "split": split}
    json.dump(D, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"    → {p}（{key}）")
    return table


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe"); ap.add_argument("--force", action="store_true")
    ap.add_argument("--years", default="")
    A = ap.parse_args()
    if A.probe:
        h = parse_page(A.probe + ("" if A.probe.endswith("Picks and Bans") else "/Picks and Bans"), A.force)
        gs = pb_games(h)
        print(f"{A.probe}：{len(gs)} 局")
        for g in gs[:3]:
            print(f"   {g['blue']} vs {g['red']} 局{g['game']} 勝={g['win']}")
            print(f"     藍 ban {g['bp']['blue']['ban']} pick {g['bp']['blue']['pick']}")
        return
    yrs = {int(x) for x in A.years.split(",") if x.strip()} if A.years else None
    ok, miss = [], []
    for job in JOBS:
        if yrs and job[0] not in yrs:
            continue
        t = None
        try:
            t = build(job, A.force)
        except Exception as e:
            print(f"    例外：{type(e).__name__} {str(e)[:100]}")
        (ok if t else miss).append(f"{job[0]} {job[1]} {job[2] or '-'}")
    # 清孤兒：改過賽段名（"夏季 PO" → "夏季"）之後 key 會變，舊 key 還留在 wikifill 裡
    # → 同一批比賽被併進去兩次，而且帶著「夏季 PO PO」這種賽段名（2026-07-31 實測）
    for y in sorted({j[0] for j in JOBS if not yrs or j[0] in yrs}):
        p = os.path.join(CACHE, f"wikifill_{y}.json")
        if not os.path.exists(p):
            continue
        try:
            D = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        live = {f"{j[1]}_{j[0]}_" + (re.sub(r"[^A-Za-z0-9]+", "", j[2]) or re.sub(r"[^A-Za-z0-9]+", "", j[4])[:24])
                for j in JOBS if j[0] == y}      # JOBS 可能帶第 7 個元素（分區設定），別寫死解包
        drop = [k for k, v in D.items() if "Picks and Bans" in str(v.get("src", "")) and k not in live]
        if drop:
            for k in drop:
                D.pop(k, None)
            json.dump(D, open(p, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"\n[{y}] 清掉 {len(drop)} 個孤兒 key：{drop}")

    print("\n" + "=" * 56)
    print(f"完成 {len(ok)}：" + "、".join(ok))
    if miss:
        print(f"失敗 {len(miss)}：" + "、".join(miss))


if __name__ == "__main__":
    main()
