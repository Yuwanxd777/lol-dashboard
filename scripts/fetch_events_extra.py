# -*- coding: utf-8 -*-
"""補充賽事名單（events_extra.js）

用途：OE 的比賽資料沒收錄、但賽事確實存在的場合，讓圖鑑「賽事」樹一樣看得到，例如
  - EWC 2026 中國區線上資格賽（OE 沒收）
  - ENC 2026 電競國家盃（11 月才打，國家隊形式）
資料源：Leaguepedia（lol.fandom.com）的 action=parse HTML。
  Cargo API 對機器人限流很兇（動輒退避數分鐘），改直接解析頁面 HTML 反而穩。

輸出：events_extra.js
  window.EVENTS_EXTRA = { "2026": { "<賽事碼>": {teams:[全名...], from, to, page, url} } }
賽事碼要用儀表板內部的碼（EWCQ中國／ENC…），前端 eventsTreeHTML 會把它併進賽事樹；
EWCQ* 會再被合併卡吸收成 EWC 卡底下的資格賽分段。

用法：python scripts\fetch_events_extra.py [--force]

速度（2026-09-08 精進迴圈 #60）：每班 51.4s 裡 28s 是 14 次「請求後固定睡 2s」、12/14 個請求在抓
2013 那六個早就定案的賽事（連續 10 天輸出逐位元相同）。所以：
  - 歷史年份（< 今年）的賽事：上一次抓的**設定相同**（EVENTS 那筆的雜湊）、距今 ≤ REFRESH_DAYS 天、
    舊檔裡還有 ⇒ 沿用舊檔那筆不重抓；抓過的時間與雜湊記在 csv_cache/events_extra_meta.json
    （資料本身仍只有 events_extra.js 一份）。今年的賽事每班照抓（名單真的會變，09-08 就多了一位教練）。
    `--force` 全部重抓。改了 EVENTS 的設定不用管快取，雜湊不同就自動重抓。
  - 節流改成「兩次請求的最小間隔」（跟 fetch_fill 一樣）：請求前補足距上次請求的差額，
    最後一次請求之後不再白睡。
歷史賽事到期輪抓（2026-09-15 精進迴圈 #121）：六個 2013 賽事的 at 是同一班寫進 meta 的 ⇒ 每 REFRESH_DAYS 天
  會有一班全部同時到期、一起重抓（09-15 10:00 那班「沿用 0／抓 11」，③ 階段 25s → 85s）。現在到期的按
  上一次抓（或上一次試）最老的排前面，每班只放前 HIST_PER_SHIFT 個真抓，其餘沿用舊檔、下一班再抓
  ⇒ 到期日自然錯開，之後每班最多 1 個。不佔額度、也不會被延後的：--force；舊檔裡沒有（沒東西可沿用）；
  設定雜湊變了或 meta 沒成功記過（人改了設定／上一班抓失敗，照舊每班抓）。被選中的那個抓失敗只在 meta
  記 `tried`（at 不動），下一班換別的到期賽事先抓、它輪過一圈再試，不會一直排第一把其他的餓死。
  細節見 hist_plan()。
"""
import io, sys, os, re, json, time, hashlib, datetime, html as _html, urllib.request, urllib.parse

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "events_extra.js")
META = os.path.join(ROOT, "csv_cache", "events_extra_meta.json")   # {"年|賽事碼": {"sig", "at"}}，只記歷史年份
REFRESH_DAYS = 7      # 歷史年份的賽事多久重抓一次（wiki 對 2013 頁的修訂極少，7 天內的舊帳可接受）
HIST_PER_SHIFT = 1    # 歷史年份「到期」的賽事每班最多真抓幾個，其餘沿用舊檔、下一班再抓（#121，見 hist_plan）
GAP = 2.0             # 對 fandom 的禮貌節流：兩次請求的最小間隔（秒）
_last_req = 0.0
API = "https://lol.fandom.com/api.php"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}


def _throttle():
    """請求前補足「距上次請求」不夠 GAP 的差額；解析花掉的時間也算進間隔，尾端不白睡"""
    w = GAP - (time.time() - _last_req)
    if w > 0:
        time.sleep(w)


def _mark():
    global _last_req
    _last_req = time.time()


def _sig(cfg):
    """EVENTS 那一筆設定的雜湊：頁名／賽段／kind 任何一個變了就不沿用舊資料"""
    return hashlib.sha1(json.dumps(cfg, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]


def load_meta():
    try:
        m = json.loads(open(META, encoding="utf-8").read())
        return m if isinstance(m, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"   ⚠ {os.path.basename(META)} 壞了（{type(e).__name__}），全部重抓"); return {}


def save_meta(meta):
    os.makedirs(os.path.dirname(META), exist_ok=True)
    tmp = META + ".tmp"
    open(tmp, "w", encoding="utf-8").write(json.dumps(meta, ensure_ascii=False, indent=1))
    os.replace(tmp, META)


def _age_days(at, now):
    try:
        return (now - datetime.datetime.strptime(at, "%Y-%m-%d %H:%M")).total_seconds() / 86400.0
    except Exception:
        return None


def cached_reason(year, code, cfg, meta, old, now, force):
    """歷史年份的賽事能不能沿用舊檔：回傳一段說明字串（能沿用）或 None（要抓）"""
    if force or int(year) >= now.year:
        return None
    m = meta.get(f"{year}|{code}") or {}
    if not old.get(str(year), {}).get(code):
        return None
    if m.get("sig") != _sig(cfg):
        return None
    age = _age_days(m.get("at", ""), now)
    if age is None or age < 0 or age > REFRESH_DAYS:
        return None
    return f"{m['at'][:10]} 抓過（{age:.1f} 天前，設定未變）→ 沿用舊檔不重抓"


def hist_plan(meta, old, now, force):
    """歷史年份「到期」的賽事，這一班哪幾個真抓（#121）。

    只看「到期」的：舊檔裡有、meta 的 sig 跟設定一樣、但 at 老過 REFRESH_DAYS（cached_reason 回 None 的那些）。
    舊檔裡沒有／sig 不同／meta 沒記過 ⇒ 不在這裡管，main() 照舊每班抓（不佔額度）。--force ⇒ 全不延後。
    排序鍵取 at 與 tried（抓失敗那班寫的）較新者：抓失敗的那個不會一直排第一、把其他到期的餓死。
    同一時刻到期的照 EVENTS 的設定順序。
    回傳 (picked, deferred)：picked＝這班真抓的鍵（list，照順序）；deferred＝{鍵: 說明字串}（沿用舊檔）。
    """
    if force:
        return [], {}
    due = []
    for year, evs in EVENTS.items():
        if int(year) >= now.year:
            continue
        for i, (code, cfg) in enumerate(evs.items()):
            key = f"{year}|{code}"
            m = meta.get(key) or {}
            if not old.get(str(year), {}).get(code) or m.get("sig") != _sig(cfg):
                continue                    # 一定要抓（沒東西可沿用／設定變了／上一班沒成功記過）→ 不佔額度
            if cached_reason(year, code, cfg, meta, old, now, force):
                continue                    # 還新，沿用
            last = max(str(m.get("at") or ""), str(m.get("tried") or ""))
            due.append((last, int(year), i, key, code, str(m.get("at") or "")))
    due.sort()
    picked = [d[3] for d in due[:HIST_PER_SHIFT]]
    first = "、".join(d[4] for d in due[:HIST_PER_SHIFT])
    deferred = {}
    for d in due[HIST_PER_SHIFT:]:
        deferred[d[3]] = (f"{d[5][:10]} 抓過、已到期，但本班歷史賽事額度用完（{len(due)} 個到期，先抓最老的 {first}）"
                          f"→ 沿用舊檔、下一班再抓")
    return picked, deferred

# kind: "team"＝一般戰隊（取 team-template 全名）／"nation"＝國家隊（取 X (National Team)）
# 鍵含「#」＝賽段名單補充（LPL#S3＝S3 開賽前的 wiki 陣容），前端賽事樹不會把它當獨立賽事卡
EVENTS = {
    # 2013-2015 的小賽區：Leaguepedia 有賽事頁與參賽隊，但沒有逐局 scoreboard（fetch_wiki_mh 抓 0 局）
    # → 至少讓圖鑑「賽事」樹看得到這些聯賽存在（使用者要求 2026-07-31）。
    # splits＝一個賽段一個頁；po_page＝該賽段的季後賽（2013 GPL 只有夏季有，就 Championship 那一場）
    2013: {
        # **賽段名一定要跟比賽資料一致**，不然賽事樹會多長出一列重複的區塊（2026-07-31）。
        # 春季／夏季也列進來（2026-08-01 使用者回報 SF5 小框寫「沒有選手資料」）：這兩段
        # 的比賽是 PB 頁抓的、沒有選手名，名單得另外從 `{賽事}/Team Rosters` 子頁借。
        # 隊伍本身不會因此多出來——前端對「主數據已有場次」的賽段只拿 wiki 名單對齊、
        # 不新增沒出賽的隊（見 index.html 的 _abIn／_abG）。
        "GPL":   {"splits": [{"sp": "台港澳錦標賽", "page": "Season 3 Taiwan Regional Finals"},
                             {"sp": "春季", "page": "2013 GPL Spring"},
                             {"sp": "夏季", "page": "2013 GPL Summer"}]},
        # TCL 只留錦標賽（使用者定案 2026-08-01）：冬／春／夏三段 Leaguepedia 沒有任何逐局
        # 資料，賽事樹列出來也只是一排沒有比賽的隊伍。改成直接指向年度總決賽 Championship
        # 頁（8 隊 40 人），錦標賽那段的比賽資料本來就由 PB 頁提供，這裡只補名單。
        "TCL":   {"page": "Riot Games Turkey/2013 Season/Championship"},
        "CBLOL": {"page": "Riot Season 3 Brazilian Championship"},
        "LCO":   {"page": "Riot Season 3 Oceanic Championship"},
        "LCL":   {"page": "2013 Season CIS Championship"},
        "LLA":   {"page": "Season 3 Latin America Regional Finals"},
    },
    # 2015 GPL 已由 PB 頁補到 145 局（春 96／夏 49）→ 不再需要補充名單
    2026: {
        "EWCQ中國": {"page": "Esports World Cup 2026/Online Qualifiers/China", "kind": "team"},
        # ENC 2026 電競國家盃已取消（使用者 2026-09-04 告知）→ 從清單移除；
        # 輸出層的 keep-filter（main() 開頭）會把舊檔裡的 ENC 一併清掉。若日後復辦再加回。
        "LPL#S3":   {"page": "LPL/2026 Season/Split 3",                        "kind": "team"},
        # 使用者 2026-09-14 交辦建檔（都還沒開打，先讓圖鑑賽事看得到名單；開打後 OE 有場次時
        # 前端會自動只拿 wiki 名單對齊、不再新增沒出賽的隊）：
        #   世界賽用 OE 的代碼 WLDs（跟主資料同碼才會併成同一張卡）；亞運是國家隊（kind=nation）；
        #   德瑪西亞杯全球邀請賽 OE 歷年沒收過、沒有既有代碼，用 DCup。
        "WLDs":     {"page": "2026 Season World Championship",                "kind": "team"},
        "亞運":     {"page": "2026 Asian Games",                                "kind": "nation"},
        "DCup":     {"page": "2026 Demacia Cup Global Invitational",            "kind": "team"},
    },
}


def parse_page(page):
    p = {"action": "parse", "page": page, "prop": "text", "format": "json"}
    url = API + "?" + urllib.parse.urlencode(p)
    for attempt in range(4):
        _throttle()
        try:
            r = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
        except Exception as e:
            _mark()
            print(f"    連線失敗（{attempt+1}/4）：{str(e)[:80]}")
            time.sleep(6 * (attempt + 1)); continue
        _mark()
        if "error" in r:
            raise RuntimeError(r["error"].get("info", "")[:200])
        return r["parse"]["text"]["*"]
    raise RuntimeError("重試多次仍失敗")


def teams_of(html, kind):
    if kind == "nation":
        # 國家隊：連結 title 就是 "China (National Team)"
        names = re.findall(r'title="([^"]+?\((?:National Team)\))"', html, re.I)
    else:
        # ① 新版型：team-template-text 裡的連結 title。這條同一隊會同時列全名與縮寫
        #    （EDward Gaming／EDG）→ 只留全名
        names = [n for n in re.findall(r'class="[^"]*team-template-text[^"]*"[^>]*>\s*<a[^>]*title="([^"]+)"', html)
                 if len(n) > 4 and not n.isupper()]
        # ② 舊版型（2013-2015 的賽事頁）：span.teamname 裡面——有 wiki 頁的是 <a title="X">，
        #    沒建頁的小隊是 <span class="new" title="X (page does not exist)">。這裡的 title 本來就是
        #    完整隊名，**不能**再套「去掉全大寫」那個過濾，不然 FIGJAM 這種老隊會整批被丟掉。
        for m in re.finditer(r'class="teamname"[^>]*>\s*<(?:a|span)[^>]*title="([^"]+)"', html):
            names.append(re.sub(r"\s*\(page does not exist\)\s*$", "", m.group(1)))
    seen, out = set(), []
    for n in names:
        n = _html.unescape(n).strip()   # Anyone&#39;s Legend → Anyone's Legend（要與主資料全名對得上）
        if n and n not in seen:
            seen.add(n); out.append(n)
    return out


ROLE_ZH = {"Top Laner": "TOP", "Jungler": "JNG", "Mid Laner": "MID", "Bot Laner": "BOT",
           "AD Carry": "BOT", "Support": "SUP", "Coach": "COACH"}


def rosters_of(html):
    """每隊名單：Leaguepedia 的 table.tournament-roster，一隊一表；選手 catlink-players，位置在 span title"""
    out = {}
    for t in re.findall(r'<table[^>]*class="[^"]*tournament-roster[^"]*"[^>]*>.*?</table>', html, re.S):
        mt = re.search(r'class="[^"]*catlink-teams[^"]*"[^>]*title="([^"]+)"', t)
        if mt:
            team = _html.unescape(mt.group(1)).strip()
        else:
            # 沒建隊伍頁的隊，隊名是純文字（CBLOL 的 Keyd Team）→ 標籤換成分隔號後取第一段文字。
            # 注意 &#160;（不斷行空格）與 &#8288;（零寬）unescape 後是  /⁠，要一起當分隔
            _txt = _html.unescape(re.sub(r"<[^>]+>", "|", t))
            _parts = [x.strip() for x in re.split(r"[| ⁠\s]+", _txt) if x.strip()]
            # 隊名後面緊接著就是選手名，切不出邊界 → 拿主資料的隊名清單比對，取**最長**能對上的組合
            fix_case("")            # 先觸發 _TNAME 初始化
            team = ""
            for _n in range(4, 0, -1):
                _cand = " ".join(_parts[:_n]).strip()
                if _cand and _cand.casefold() in (_TNAME or {}):
                    team = _TNAME[_cand.casefold()]
                    break
            if not team:
                team = " ".join(_parts[:2]).strip()
            if len(team) < 2:
                continue
        team = re.sub(r"\s*\(page does not exist\)\s*$", "", team).strip()
        players, seen = [], set()
        # 每個選手格：<span title="Jungler" …> 之後跟著 catlink-players（順序穩定）
        for m in re.finditer(r'<span[^>]*title="([^"]*)"[^>]*class="[^"]*sprite[^"]*"[^>]*>|class="[^"]*catlink-players[^"]*"[^>]*>([^<]+)</a>', t):
            if m.group(2):
                nm = _html.unescape(m.group(2)).strip()
                if nm and nm not in seen:
                    seen.add(nm); players.append({"n": nm, "r": rosters_of._last_role})
            elif m.group(1) in ROLE_ZH:
                rosters_of._last_role = ROLE_ZH[m.group(1)]
        if players:
            out[team] = players
    return out


rosters_of._last_role = ""

ROLE_EN = {"Top": "TOP", "Jungle": "JNG", "Mid": "MID", "AD": "BOT", "ADC": "BOT",
           "Bot": "BOT", "Support": "SUP", "Coach": "COACH"}


def rosters_alt(html):
    """舊版型的名單頁（2013 的 `{賽事}/Team Rosters` 子頁，使用者提供 2026-07-31）：
    一隊一個 table.sortable.wikitable，欄位是 ID／Name／Role，隊名在表格前最近的 catlink-teams。
    """
    out = {}
    for m in re.finditer(r'<table[^>]*class="[^"]*sortable wikitable[^"]*"[^>]*>.*?</table>', html, re.S):
        tb, before = m.group(0), html[:m.start()]
        mt = None
        for mm in re.finditer(r'class="[^"]*catlink-teams[^"]*"[^>]*title="([^"]+)"', before):
            mt = mm                                   # 取最後一個＝離這張表最近的隊名
        if not mt:
            continue
        team = re.sub(r"\s*\(page does not exist\)\s*$", "", _html.unescape(mt.group(1))).strip()
        players, seen = [], set()
        for tr in re.findall(r"<tr.*?</tr>", tb, re.S):
            cells = [re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", "", c))).strip()
                     for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", tr, re.S)]
            if len(cells) < 4 or not cells[1] or cells[1] == "ID":
                continue
            if cells[1] in seen:
                continue
            seen.add(cells[1])
            players.append({"n": cells[1], "r": ROLE_EN.get(cells[3], "")})
        if players:
            out.setdefault(fix_case(team), players)
    return out


def dates_of(html):
    ds = sorted(set(re.findall(r"\b(20\d\d-\d\d-\d\d)\b", html)))
    return (ds[0], ds[-1]) if ds else ("", "")


_TNAME = None


def fix_case(nm):
    """還原隊名的正確大小寫。

    wiki 的 title 屬性走 MediaWiki 頁名規則，首字母一定大寫（paiN Gaming → PaiN Gaming、
    ahq eSports Club → Ahq eSports Club）→ 跟主資料的隊名對不上，賽事樹會當成兩支不同的隊。
    以 data_*.js 既有的隊名為準做 casefold 比對；沒比對到的（純補充賽事、沒有比賽資料）就原樣保留。
    """
    global _TNAME
    if _TNAME is None:
        import glob
        _TNAME = {}
        for p in sorted(glob.glob(os.path.join(ROOT, "data", "data_*.js"))):
            try:
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


def bracket_of(html):
    """季後賽對戰表（div.bracket-team）裡的隊伍＝打進季後賽的隊 → 賽事樹的綠勾。

    2013 那些小賽區是「小組賽＋季後賽同一頁、同一個賽段名（甚至沒有賽段名）」，
    沒辦法像現代聯賽那樣靠 split 帶 PO 判斷 → 直接讀對戰表（使用者要求 2026-07-31）。
    """
    out, seen = [], set()
    for b in re.findall(r'<div class="bracket-team[^"]*"[^>]*>(.*?)(?=<div class="bracket-team|</div>\s*</div>)',
                        html, re.S):
        m = re.search(r'title="([^"]+)"', b)
        if not m:
            continue
        nm = fix_case(_html.unescape(m.group(1)).strip())
        if nm and nm not in seen:
            seen.add(nm); out.append(nm)
    return out


CARGO_FORM = "https://lol.fandom.com/wiki/Special:CargoExport"
CARGO_UA = {"User-Agent": UA["User-Agent"],
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
            "Accept-Language": "en-US,en;q=0.9", "Referer": CARGO_FORM}
_COP = None


def _cargo_opener():
    """CargoExport 走一般頁面請求（action=cargoquery 對匿名存取限流極兇）；要先拿 cookie 否則 403"""
    global _COP
    if _COP is None:
        import http.cookiejar
        cj = http.cookiejar.CookieJar()
        _COP = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        _throttle()
        try:
            _COP.open(urllib.request.Request(CARGO_FORM, headers=CARGO_UA), timeout=60).read()
        except Exception as e:
            print(f"   ⚠ Cargo 取 cookie 失敗（仍試著繼續）：{type(e).__name__}")
        _mark()
    return _COP


def cargo_rosters(page, subpages=False, only=None):
    """用 Cargo 表 TournamentPlayers 取參賽名單 → {隊名:[{n,r}]}。

    為什麼要這層：HTML 版型有好幾代，`table.tournament-roster` 與 `/Team Rosters`
    子頁都解析不到時整個賽事就是 0 隊名單（實測 2013 TCL 17 隊、GPL 12 隊全空，
    前端戰隊小框只能顯示「無選手資料」）。Cargo 表不吃版型，穩定得多。

    subpages=True（2026-09-16 精進迴圈 #132，grab() 用）：連 `{page}/…` 子頁的列一起查。
    世界賽的總覽頁「2026 Season World Championship」本身沒有名單，TournamentPlayers 的列全掛在
    `/Main Event`（71 列）與 `/Play-In`（8 列）底下 ⇒ 舊寫法只比總覽頁名、一列都拿不到，
    events_extra.js 的 WLDs 一直是「11 隊 0 份名單」（使用者 09-14 建檔時要的就是先列名單）。
    總覽頁本身的列跟舊行為逐筆相同；子頁的列只補「總覽頁沒有列」而且在 only（總覽頁的隊伍清單，
    casefold 比）裡的隊，同一隊掛在好幾個子頁（Play-In 打上 Main Event）照選手名去重。
    一個請求（OR），不多打；頁名裡的 `_` 在 LIKE 是單字元萬用字，wiki 頁名用空白、不影響。
    真站 13 頁新舊比對（autopilot/_m132_realgrab.txt）：只有「會叫 Cargo 的頁」才有差，沒有 only 時
    CBLOL／LLA 2013、LPL#S3、亞運會多出資格賽／全明星隊的鍵 ⇒ grab() 一律帶 only。
    """
    pg = str(page).replace('"', '\\"')
    where = 'TP.OverviewPage="%s"' % pg
    fields = "TP.Team=tm,TP.Player=pl,TP.Role=rl"
    if subpages:
        where = '(%s OR TP.OverviewPage LIKE "%s/%%")' % (where, pg)
        fields += ",TP.OverviewPage=ov"
    q = {"tables": "TournamentPlayers=TP",
         "fields": fields,
         "where": where,
         "format": "json", "limit": "500"}
    url = CARGO_FORM + "?" + urllib.parse.urlencode(q)
    op = _cargo_opener()
    _throttle()
    try:
        raw = op.open(urllib.request.Request(url, headers=CARGO_UA), timeout=90).read().decode("utf-8", "replace")
    except Exception as e:
        _mark()
        print(f"   Cargo 名單失敗：{type(e).__name__}"); return {}
    _mark()
    if raw.lstrip()[:1] not in "[{":
        return {}
    try:
        rows = json.loads(raw)
    except Exception:
        return {}
    out = {}
    if subpages:
        own = {fix_case(str(r.get("tm") or "").strip()) for r in rows if str(r.get("ov") or "") == str(page)}
        only_cf = None if only is None else {str(t).casefold() for t in only}
        seen = set()
    for r in rows:
        tm = fix_case(str(r.get("tm") or "").strip())
        # 選手名帶消歧後綴（crueL (Ceyhun Ünlü)、Icarus (Turkish Player)）→ 顯示用去掉
        nm = re.sub(r"\s*\([^)]*\)\s*$", "", str(r.get("pl") or "")).strip()
        if not tm or not nm:
            continue
        if subpages and str(r.get("ov") or "") != str(page):
            # 子頁的列：總覽頁本身有這隊 ⇒ 不採用（總覽頁那份照舊）；不在 only（總覽頁的隊伍清單）⇒ 不採用
            # （亞運資格賽被刷掉的隊、LPL 的 Team Demacia／Ionia 全明星隊，真站實測會多出 10／2 個沒人讀的鍵）
            if tm == "TBD" or tm in own or (only_cf is not None and tm.casefold() not in only_cf):
                continue
            if (tm, nm) in seen:
                continue
            seen.add((tm, nm))
        role = ROLE_EN.get(str(r.get("rl") or "").strip().title(), "")
        out.setdefault(tm, []).append({"n": nm, "r": role})
    ORD = {"TOP": 1, "JNG": 2, "MID": 3, "BOT": 4, "SUP": 5, "COACH": 6}
    for tm in out:
        out[tm].sort(key=lambda p: ORD.get(p["r"], 9))
    return out


def grab(page, kind, roster_page=None):
    html = parse_page(page)
    frm, to = dates_of(html)
    rs = rosters_of(html)
    if not rs and roster_page:      # 舊賽事的名單在 `/Team Rosters` 子頁
        try:
            rs = rosters_alt(parse_page(roster_page))
        except Exception as e:
            print(f"   名單子頁失敗：{str(e)[:70]}")
    teams = [fix_case(t) for t in teams_of(html, kind)]
    # 兩種 HTML 解析都不足 → 用 Cargo 補（只補缺的隊，已解析到的不覆蓋）；
    # 連 `{page}/…` 子頁一起查（世界賽的名單在 /Main Event、/Play-In，#132）
    if len(rs) < len(teams):
        cr = cargo_rosters(page, subpages=True, only=teams)
        if cr:
            add = [t for t in cr if t not in rs]
            rs = {**cr, **rs}
            if add:
                print(f"   Cargo 名單：+{len(add)} 隊（{page}）")
    return (teams, rs, frm, to, bracket_of(html))


def align_keys(teams, rosters):
    """名單的隊名對齊 teams 的寫法：HTML 與 Cargo 的大小寫常不同（paiN Gaming／
    PaiN Gaming），前端是用隊名精確查 rosters，對不上就顯示「無選手資料」。"""
    if not rosters:
        return {}
    idx = {str(t).lower(): t for t in teams}
    out = {}
    for tm, pl in rosters.items():
        out[idx.get(str(tm).lower(), tm)] = pl
    return out


def main():
    old = {}
    if os.path.exists(OUT):                       # 抓失敗時保留舊資料，不要把檔案清空
        try:
            old = json.loads(re.sub(r"^window\.EVENTS_EXTRA=|;\s*$", "", open(OUT, encoding="utf-8").read().strip()))
        except Exception:
            old = {}
    # 只保留「EVENTS 裡還登記著的賽事碼」：從設定移除的（例：2013 GPL 已有完整比賽資料）
    # 若沿用舊檔就會一直留著，賽事樹會多長出賽段名不同步的重複區塊（2026-07-31）
    data = {str(y): {k: v for k, v in old.get(str(y), {}).items() if k in evs} for y, evs in EVENTS.items()}
    force = "--force" in sys.argv[1:]
    meta = load_meta()
    now = datetime.datetime.now()
    n_reuse = n_fetch = n_hist = 0
    picked, deferred = hist_plan(meta, old, now, force)
    n_due = len(picked) + len(deferred)
    if deferred:
        print(f"歷史賽事到期 {n_due} 個，本班只重抓最老的 {len(picked)} 個（"
              + "、".join(k.split("|", 1)[1] for k in picked) + f"；每班最多 {HIST_PER_SHIFT} 個），"
              f"其餘 {len(deferred)} 個沿用舊檔、下一班再抓")

    def _tried(key):
        """被選中的歷史賽事這班抓失敗：只記「試過」、at 不動 ⇒ 下一班輪到別的到期賽事先抓（見 hist_plan）"""
        if key in picked and isinstance(meta.get(key), dict):
            meta[key]["tried"] = now.strftime("%Y-%m-%d %H:%M")
    for year, evs in EVENTS.items():
        for code, cfg in evs.items():
            kind = cfg.get("kind", "team")
            why = cached_reason(year, code, cfg, meta, old, now, force)
            if why:
                print(f"[{year}] {code}：{why}"); n_reuse += 1
                continue
            key = f"{year}|{code}"
            if key in deferred:                 # 到期了，但本班歷史賽事額度用完 → 沿用舊檔（#121）
                print(f"[{year}] {code}：{deferred[key]}"); n_reuse += 1
                continue
            n_fetch += 1
            if key in picked:
                n_hist += 1
            # ── 分賽段的賽事（splits）：一個賽段一個 wiki 頁，另可指定 po_page＝該賽段的季後賽
            #    （例：2013 GPL 只有夏季有季後賽，就是 2013 GPL Championship 那一場）
            if cfg.get("splits"):
                print(f"[{year}] {code}（{len(cfg['splits'])} 個賽段）")
                segs, allt, frm0, to0 = [], [], "", ""
                complete = True         # 任一賽段／季後賽頁失敗就不記進 meta，下一班會再抓
                for sp in cfg["splits"]:
                    try:
                        teams, _rs, frm, to, brk = grab(sp["page"], kind, sp.get("page","")+"/Team Rosters")
                    except Exception as e:
                        print(f"   {sp['sp']} 失敗：{str(e)[:100]}"); complete = False; continue
                    # 對戰表涵蓋全部參賽隊＝整個賽事就是淘汰賽（2013 土耳其／大洋洲／CIS 都是）→
                    # 那就沒有「誰晉級」可言，全部打勾等於沒打勾 → 不標
                    po = list(brk) if 0 < len(brk) < len(teams) else []
                    if sp.get("po_page"):   # 季後賽另有獨立頁 → 該頁的參賽隊全是晉級隊
                        try:
                            po2, _r2, _f2, to2, _b2 = grab(sp["po_page"], kind)
                            po = po2 if (0 < len(po2) < len(teams)) else po
                            if to2 > to:
                                to = to2
                        except Exception as e:
                            print(f"   {sp['sp']} 季後賽失敗：{str(e)[:80]}"); complete = False
                    segs.append({"sp": sp["sp"], "teams": teams, "from": frm, "to": to, "po": po,
                                 "rosters": _rs or {}, "page": sp["page"]})
                    allt += teams
                    if frm and (not frm0 or frm < frm0):
                        frm0 = frm
                    if to > to0:
                        to0 = to
                    print(f"   {sp['sp']}：{len(teams)} 隊 {frm}~{to}" + (f"　季後賽 {len(po)} 隊" if po else ""))
                if not segs:
                    print("   全部失敗，保留舊資料"); _tried(key); continue
                seen, uniq = set(), []
                for t in allt:
                    if t not in seen:
                        seen.add(t); uniq.append(t)
                # 各賽段的名單要併到頂層：前端戰隊小框讀的是頂層 rosters，
                # 只留在 segs[].rosters 裡的話整個賽事都會顯示「無選手資料」
                merged = {}
                for s in segs:
                    for tm, pl in (s.get("rosters") or {}).items():
                        if len(pl) > len(merged.get(tm, ())):
                            merged[tm] = pl
                for rp in (cfg.get("roster_pages") or ()):   # 只借名單、不當賽段的頁
                    for tm, pl in (cargo_rosters(rp) or {}).items():
                        if len(pl) > len(merged.get(tm, ())):
                            merged[tm] = pl
                merged = align_keys(uniq, merged)
                if merged:
                    print(f"   併賽段名單：{len(merged)} 隊")
                data[str(year)][code] = {"teams": uniq, "rosters": merged, "splits": segs,
                                         "from": frm0, "to": to0, "page": cfg["splits"][0]["page"],
                                         "url": "https://lol.fandom.com/wiki/" + urllib.parse.quote(cfg["splits"][0]["page"].replace(" ", "_"))}
                if complete and int(year) < now.year:
                    meta[key] = {"sig": _sig(cfg), "at": now.strftime("%Y-%m-%d %H:%M")}
                elif not complete:
                    _tried(key)
                continue
            print(f"[{year}] {code} ← {cfg['page']}")
            try:
                teams, rosters, frm, to, brk = grab(cfg["page"], kind, cfg["page"]+"/Team Rosters")
            except Exception as e:
                print("   失敗，保留舊資料：", str(e)[:120]); _tried(key); continue
            rosters = align_keys(teams, rosters)
            data[str(year)][code] = {"teams": teams, "rosters": rosters, "from": frm, "to": to,
                                     "po": (brk if 0 < len(brk) < len(teams) else []), "page": cfg["page"],
                                     "url": "https://lol.fandom.com/wiki/" + urllib.parse.quote(cfg["page"].replace(" ", "_"))}
            print(f"   {len(teams)} 隊　{len(rosters)} 份名單　{frm} ~ {to}" + (f"　季後賽 {len(brk)} 隊" if 0 < len(brk) < len(teams) else ("　（純淘汰賽，不標晉級）" if brk else "")))
            if rosters:
                k = list(rosters)[0]
                print(f"    例：{k} → " + "、".join(f"{p['n']}({p['r'] or '?'})" for p in rosters[k][:6]))
            if teams:
                print("   ", "、".join(teams[:8]) + ("…" if len(teams) > 8 else ""))
            if int(year) < now.year:
                meta[key] = {"sig": _sig(cfg), "at": now.strftime("%Y-%m-%d %H:%M")}
    open(OUT, "w", encoding="utf-8").write("window.EVENTS_EXTRA=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";")
    # 只留 EVENTS 還登記著的鍵（從設定移除的賽事，meta 也跟著清）
    keep = {f"{y}|{c}" for y, evs in EVENTS.items() for c in evs}
    meta = {k: v for k, v in meta.items() if k in keep}
    save_meta(meta)
    print(f"→ events_extra.js（沿用舊檔 {n_reuse} 個賽事／實際抓取 {n_fetch} 個，歷史年份每 {REFRESH_DAYS} 天重抓一次、"
          f"本班到期 {n_due} 個重抓 {n_hist} 個（每班最多 {HIST_PER_SHIFT} 個）；--force 全部重抓）")


if __name__ == "__main__":
    main()
