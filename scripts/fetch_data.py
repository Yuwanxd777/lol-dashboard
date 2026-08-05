# -*- coding: utf-8 -*-
"""
LOL 儀表板資料抓取 v2 — 直接從 Oracle's Elixir 官方 S3 下載並在本機處理
（處理邏輯 1:1 移植自 GS Apps Script v9，不再依賴 Google Sheets）

用法：
  python fetch_data.py            # 更新今年；歷史年份缺哪年補哪年
  python fetch_data.py 2025      # 強制重抓指定年份
  python fetch_data.py --force   # 全部年份強制重抓

輸出：data_{年}.js（各年 RAW_DATA）＋ data.js（年份清單 manifest）
"""
import collections, csv, io, json, os, re, sys, urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 專案根目錄（本腳本在 scripts\ 內）
# Oracle's Elixir 官方公開 Google Drive 資料夾（免認證）
OE_FOLDER = "1gLSw0RLjBbtaNy0dgnGQDAZOHIgCe-HH"
FIRST_YEAR = 2013   # 2013 起（使用者定案 2026-07-31：一級聯賽補到 2013；OE 沒有 2013→走 wiki）
NOW = datetime.now()
DEFAULT_YEAR = NOW.year


def keep_stamp(path, field):
    """沿用磁碟上既有的時間戳；檔案還不存在（第一次建）才寫當下時間。

    「資料時間」的語意＝**整條管線最後一次完整跑完**的時間（使用者 2026-07-31 定案），
    推進它是 stamp_updated.py（update.bat 最後一行）的職責，不是這裡。
    本檔只是管線第 3 步：在這裡寫 datetime.now() 會有兩個症狀——
      ①每天固定寫成排程啟動的整點（10:00），但整條管線還要再跑一個多小時
      ②管線中途失敗時，時間戳照樣往前跳，等於假裝更新過
    所以這裡一律原封不動，讓跑到一半的儀表板顯示「上一輪完成時間」而不是半真半假的時間。
    """
    try:
        with io.open(path, encoding="utf-8") as f:
            m = re.search(r'"%s"\s*:\s*"([^"]*)"' % field, f.read(300))
        if m and m.group(1):
            return m.group(1)
    except OSError:
        pass
    return NOW.strftime("%Y-%m-%d %H:%M")
YEARS = list(range(FIRST_YEAR, DEFAULT_YEAR + 1))

# 保留聯賽（None = 全部）。含 MSI / RR(洲際賽) 等國際賽。
# ── 一級聯賽分級表（依 Leaguepedia 各年賽制）：聯賽 → (一級起年, 迄年) ──
# 次級/學院/CS 一律不收；改制合併後舊聯賽自動失效（如 TCL 2023 併入 EMEA 後不再是一級）
TIER1_YEARS = {
    "LCS": [(2013, 2024), (2026, 2099)],   # 2025 併入 LTA N，2026 LTA 解散後回歸
    "LEC": (2013, 2099), "LCK": (2013, 2099), "LPL": (2013, 2099),
    "LMS": (2015, 2019), "GPL": (2013, 2015),
    "PCS": (2020, 2024), "VCS": (2018, 2024), "LJL": (2014, 2024),
    # 起始年往前推到 2013（使用者要求把一級聯賽補到 2013）：這些賽區 2013 就有自己的賽事，
    # 只是當年叫別的名字（巴西＝Riot Season 3 Brazilian Championship、大洋洲＝Riot Season 3
    # Oceanic Championship、CIS＝Regional CIS Championship、土耳其＝Riot Turkey Season 3…）。
    # 不放進來的話 league_ok 會把整批補進來的比賽丟掉（實測 process() 回 0 列）。
    "CBLOL": [(2013, 2024), (2026, 2099)], # 2025 併入 LTA S，2026 回歸
    "LLA": (2013, 2024), "LLN": (2017, 2018), "CLS": (2017, 2018),
    "TCL": (2013, 2022), "LCO": (2013, 2024), "LCL": (2013, 2022),  # LCO=OPL 改名(2021)，2025 併入 LCP
    "LCP": (2025, 2099), "LTA": (2025, 2025), "LTA N": (2025, 2025), "LTA S": (2025, 2025),
}
# 國際賽/盃賽不分級。IWCT＝2013-2015 的國際外卡賽（外卡賽區爭世界賽／MSI 名額），
# 不在 TIER1_YEARS 裡 → 不列進來的話整個賽事會被 league_ok 丟掉（wiki 抓到 17 局卻 0 列）
INTL_LEAGUES = {"WLDS", "MSI", "EWC", "FST", "ENC", "KESPA", "IEM", "IWCT"}

def league_ok(lg, year):
    if lg.upper() in INTL_LEAGUES:
        return True
    rng = TIER1_YEARS.get(lg)
    if not rng:
        return False
    ranges = rng if isinstance(rng, list) else [rng]
    return any(s <= year <= e for s, e in ranges)

FILTER_LEAGUES = ["LPL","LCK","CBLOL","LCP","LEC","LCS","LTA S","LTA N","LTA",
                  "FST","MSI","EWC","ENC","WLDs","KeSPA","LMS","EU LCS","NA LCS",
                  "OGN","IEM","OPL","TCL",   # （保留給舊碼參考；實際過濾改用 TIER1_YEARS）
                  "RR","IEM","MSC"]

# 選手 ID 大小寫變體 → 統一寫法（casefold 當 key，值取場次多的那個寫法）。
# 只收「同一支隊伍、時間相鄰」的組合＝確定是同一人，來源寫法不一致而已；
# 不同隊不同時期的同名異寫（ARK/Ark、bless/Bless、FATE/fate、Mountain/MounTain…）多半是**不同人**，
# 一律不併。不併的話生涯統計會被拆成兩份（2026-07-31 使用者提醒：選手生涯統計會漏）。
PLAYER_ALIAS = {
    "bigpomelo": "bigpomelo",       # Oh My God 2013
    "fzzf": "Fzzf",                 # EDward Gaming 2013-2014
    "imaqtpie": "Imaqtpie",         # Dignitas 2013-2014
    "miso": "MiSo",                 # Jin Air Falcons 2013-2014
    "noname": "NONAME",             # LMQ 2013-2014
    "puszu": "puszu",               # Fnatic 2013
    "san": "san",                   # Oh My God 2013-2015
    "watch": "Watch",               # NaJin 2013-2015
    "weiwei": "Weiwei",             # LNG/BLG 2019-2026
    "wuxx": "Wuxx",                 # Royal Never Give Up 2015-2017
    "xiaoweixiao": "xiaoweixiao",   # LMQ／Team Impulse 2013-2015
}

SHARED_COLS = ["league","split","date","game","result","patch","participantid"]
# 效能已非問題 → 全部留存。只刪「識別碼」與「已被 banlist/picklist/pid 取代」的冗欄。
# 其餘統計欄（含 @15、@20、@25、golddiff、opp_*、視野、補刀、野怪、小龍細分…）全部保留。
DELETE_COLS = {
  "gameid","datacompleteness","url","playerid","teamid","year","position","side","playoffs",
  "ban1","ban2","ban3","ban4","ban5","pick1","pick2","pick3","pick4","pick5",
}
SPLIT_MAP = {
  "Cup":"Split 1","Versus":"Split 1","Lock-In":"Split 1","Winter":"Split 1",
  "Rounds 1-2":"Split 2","Spring":"Split 2","Split 2 Placements":"Split 2","Split 2 Placement":"Split 2",
  "Rounds 3-4":"Split 3","Rounds 3-5":"Split 3","Summer":"Split 3",
}
CBLOL_SPLIT_MAP = {"Split 1":"Split 2","Split 2":"Split 3"}
# 2025 前的賽制統一為春季/夏季（Winter/Fall/Split 1-2 只是各地區稱法不同）
# Winter 是真的多打的一季（LCK 2013/2014 的 Champions、TCL 2013-2016、GPL 2014），
# 併進「春季」等於把兩個賽段的隊伍與戰績混在一起，圖鑑賽事也看不到冬季賽
#（2026-07-31 使用者回報 LCK 冬季賽沒出現）→ 獨立成「冬季」
OLD_SPLIT_MAP = {"Spring":"春季","Winter":"冬季","Split 1":"春季",
                 "Summer":"夏季","Fall":"夏季","Split 2":"夏季","Split 3":"夏季",
                 "Summer Placements":"夏季","Finals":"夏季","Championship":"夏季",
                 "Lock-In":"春季","Kickoff":"春季"}
# 季後賽起始日人工表（(年, OE聯賽碼, OE原始split) → 起始日；該日含以後的場次一律標成該賽段的季後賽）
# 用途：OE 對某些賽事整段不標 playoffs 欄位（開季盃賽最常見），導致「S1 季後賽」在儀表板查不到。
# 使用者定案：季後賽從 Play-In（含性質相同的 Last Chance）起算。日期＝比對 Leaguepedia 賽制頁與 OE 每日場次結構得出。
#   LCK 2026 Cup      小組賽 1/14–1/25（2 組各 5 隊、跨組 BO3，每天 2 系列）→ Play-In 1/28–2/01 → Playoffs 2/06–3/01
#                     https://lol.fandom.com/wiki/LCK/2026_Season/Cup
#   CBLOL 2026 Cup    單循環 BO1 1/17–2/01（8 隊 28 場）→ Play-In 2/02–2/03 → Playoffs 2/07–3/01
#                     https://lol.fandom.com/wiki/CBLOL/2026_Season/Cup
#   LCS 2026 Lock-In  瑞士制三輪 1/24–2/01 → Last Chance 2/02（第 6 種子加賽，等同 Play-In）→ Playoffs 2/07–3/02
#                     https://lol.fandom.com/wiki/LCS/2026_Season/Lock-In
PO_START = {
    # 2013-2014 的 Champions／GPL：wiki 的 MatchHistoryGame 沒有 playoffs 欄。
    # 分界是看得出來的——小組賽每天 4 隊（兩場 BO），季後賽每天只有 2 隊（單一系列賽）
    #（2026-07-31 使用者要求把 LCK 各季的季後賽標出來）
    (2013, "LCK",   "Winter"):  "2012-12-26",
    (2013, "LCK",   "Spring"):  "2013-05-08",
    (2013, "LCK",   "Summer"):  "2013-08-07",
    (2014, "LCK",   "Winter"):  "2013-12-25",
    (2014, "LCK",   "Spring"):  "2014-04-16",
    (2014, "LCK",   "Summer"):  "2014-07-16",
    (2014, "GPL",   "Winter"):  "2013-12-04",
    (2014, "GPL",   "Summer"):  "2014-07-16",
    (2026, "LCK",   "Cup"):     "2026-01-28",
    (2026, "CBLOL", "Cup"):     "2026-02-02",
    (2026, "LCS",   "Lock-In"): "2026-02-02",
}
LEAGUE_ORDER = {"LCK":0,"LPL":1,"LCP":2,"LEC":3,"LCS":4,"CBLOL":5}
PO_MAP = {1:1,2:2,3:2,4:3,5:3,6:4,7:5,8:6,9:6,10:7}
PO_TABLES = {("b",1):[1,4,5,8,9],("b",0):[2,3,6,7,10],("r",1):[2,3,6,7,10],("r",0):[1,4,5,8,9]}
POS5 = ["top","jng","mid","bot","sup"]


_folder_cache = None
def list_folder():
    """列出 OE 公開資料夾 → {年份: file_id}"""
    global _folder_cache
    if _folder_cache is not None:
        return _folder_cache
    import re
    url = f"https://drive.google.com/embeddedfolderview?id={OE_FOLDER}#list"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace")
    out = {}
    for fid, name in re.findall(r'id="entry-([\w-]+)".*?flip-entry-title">([^<]+)<', html, re.S):
        m = re.match(r"(\d{4})_LoL_esports_match_data", name)
        if m:
            out[int(m.group(1))] = fid
    _folder_cache = out
    return out


JSON_KEY = os.path.join(HERE, "..", "字幕", "app", "mslol-500204-37d9f63f8b81.json")
_session = None
def drive_session():
    """service account 的 Drive API session（匿名下載常被額度擋，走 API 才穩）"""
    global _session
    if _session is None:
        from google.oauth2.service_account import Credentials
        from google.auth.transport.requests import AuthorizedSession
        creds = Credentials.from_service_account_file(
            JSON_KEY, scopes=["https://www.googleapis.com/auth/drive.readonly"])
        _session = AuthorizedSession(creds)
    return _session


CACHE_DIR = os.path.join(HERE, "csv_cache")
def download(year):
    # 歷史年份 CSV 快取在本機，改規則重算時不用重新下載
    cache = os.path.join(CACHE_DIR, f"{year}.csv")
    if year < DEFAULT_YEAR and os.path.exists(cache):
        print(f"  使用快取 {os.path.getsize(cache)//1048576} MB")
        with open(cache, encoding="utf-8") as f:
            return f.read()
    fid = list_folder().get(year)
    if fid is None:
        raise urllib.error.HTTPError("", 404, "no file for year", None, None)
    r = drive_session().get(
        f"https://www.googleapis.com/drive/v3/files/{fid}",
        params={"alt": "media"}, timeout=900)
    if r.status_code != 200:
        raise RuntimeError(f"Drive API {r.status_code}：{r.text[:200]}")
    data = r.content
    print(f"  下載 {len(data)//1048576} MB")
    text = data.decode("utf-8", errors="replace")
    if year < DEFAULT_YEAR:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(cache, "w", encoding="utf-8") as f:
            f.write(text)
    return text


def calc_po(champ, picks, is_blue, first, ):
    try: slot = picks.index(champ)
    except ValueError: return 0
    po = PO_TABLES[("b" if is_blue else "r", first)][slot]
    return PO_MAP.get(po, 0)


def process(text, year=DEFAULT_YEAR):
    rows = list(csv.reader(io.StringIO(text)))
    hdr = rows[0]
    width = len(hdr)
    idx = {h:i for i,h in enumerate(hdr)}
    gi = lambda n: idx.get(n, -1)
    iLeague=gi("league"); iSide=gi("side"); iGameid=gi("gameid"); iGame=gi("game")
    iPos=gi("position"); iChamp=gi("champion"); iPlayer=gi("playername")
    iBan1=gi("ban1"); iPick1=gi("pick1"); iSplit=gi("split"); iPlayoffs=gi("playoffs")
    iFBK=gi("firstbloodkill"); iFBA=gi("firstbloodassist"); iFB=gi("firstblood"); iPid=gi("participantid")

    # 官方 CSV 沒有 firstPick 時：藍方視為先選（標準 draft 藍方 B1）
    iFP = gi("firstPick")
    if iFP < 0:
        hdr = hdr + ["firstPick"]; idx["firstPick"] = width; iFP = width; width += 1
        print("  ⚠ 來源無 firstPick 欄，以藍方=先選補上")

    # 補齊短列 + 篩聯賽
    allowed = set(l.upper() for l in FILTER_LEAGUES) if FILTER_LEAGUES else None
    filtered = []
    for r in rows[1:]:
        if len(r) < width: r = r + [""]*(width-len(r))
        lg = (r[iLeague] or "").strip()
        if not lg: continue
        # 聯賽更名統一：NA LCS→LCS、EU LCS→LEC、OGN(韓國前身)→LCK
        # 「KeSPA Cup」＝OE 2026 七月那屆的寫法（2025-12 那屆寫 KeSPA）；不正名的話 league_ok 比對不到 KESPA → 整屆被丟掉
        RENAME = {"NA LCS": "LCS", "EU LCS": "LEC", "OGN": "LCK", "OPL": "LCO",
                  "KeSPA Cup": "KeSPA"}
        if lg in RENAME:
            lg = RENAME[lg]; r[iLeague] = lg
        if not league_ok(lg, year): continue  # 只收該年度的一級聯賽與國際賽
        if iPlayer >= 0:                      # 選手 ID 大小寫統一（見 PLAYER_ALIAS）
            _pn = (r[iPlayer] or "").strip()
            if _pn and _pn.casefold() in PLAYER_ALIAS: r[iPlayer] = PLAYER_ALIAS[_pn.casefold()]
        # firstPick 空值一律補「藍方＝先選」（標準 draft 藍方 B1）。
        # **不可只在「本欄是新補的」時才填**（原本的 gi==width-1 條件，2026-08-02 修）：
        # 來源本身帶了這一欄但沒填值時就漏掉了，而空字串在 calc_po 是 int("") 例外 → first=0
        # → 藍方整批被當成後選方、順位左右對調。中招的是所有 wiki 來源的局（2013 全年 1490 局、
        # 2016 全年 3177 局），症狀是比賽BP 的金色順位數字全反，且不會報錯。
        if iFP >= 0 and len(r) > iFP and r[iFP] == "":
            r[iFP] = "1" if (r[iSide] or "").lower() == "blue" else "0"
        filtered.append(r)
    del rows

    # 2026+ EWC：同區對戰＝區域資格賽（EWCQ○○），跨區對戰＝正賽（維持 EWC）
    if year >= 2026:
        gi_g, gi_t = gi("gameid"), gi("teamname")
        dom = {}   # 隊伍 → 所屬國內一級聯賽
        for r in filtered:
            if r[iLeague] in ("LCK", "LPL", "LEC", "LCS", "CBLOL", "LCP"):
                dom[r[gi_t]] = r[iLeague]
        MAPQ = {"LEC": "EWCQ歐洲", "LCK": "EWCQ韓國", "LPL": "EWCQ中國",
                "LCP": "EWCQ太平洋", "CBLOL": "EWCQ巴西", "LCS": "EWCQ北美"}
        by_game = {}
        for r in filtered:
            if r[iLeague] == "EWC":
                by_game.setdefault(r[gi_g], set()).add(dom.get(r[gi_t]))
        glabel = {}
        for g, regs in by_game.items():
            regs = {x for x in regs if x}
            glabel[g] = MAPQ[next(iter(regs))] if len(regs) == 1 else "EWC"
        for r in filtered:
            if r[iLeague] == "EWC":
                r[iLeague] = glabel.get(r[gi_g], "EWC")

    # split 正規化 + 季後賽 PO 後綴（S1/S2/S3 制度 2025 才開始；之前用季名）
    _gi_date = gi("date")
    for r in filtered:
        lg = (r[iLeague] or "").strip().upper()
        orig = (r[iSplit] or "").strip()
        try: is_po = int(r[iPlayoffs] or 0) == 1
        except ValueError: is_po = False
        # OE 有些賽事整段沒標 playoffs（LCK 2026 Cup 全部 playoffs=0）→ 用人工「季後賽起始日」補
        _ps = PO_START.get((year, (r[iLeague] or "").strip(), orig))
        if _ps and (r[_gi_date] or "")[:10] >= _ps:
            is_po = True
        if year >= 2025:
            norm = CBLOL_SPLIT_MAP.get(orig, SPLIT_MAP.get(orig, orig)) if lg=="CBLOL" else SPLIT_MAP.get(orig, orig)
            final = (norm + " PO") if (is_po and norm) else norm
            r[iSplit] = final.replace("Split ", "S")
        else:
            norm = OLD_SPLIT_MAP.get(orig, orig)
            # 「錦標賽」是短期盃賽（Championship／Regional Finals，兩三天打完），
            # 整個賽事本來就是淘汰賽，沒有「例行賽 vs 季後賽」可分
            #（使用者定案 2026-07-31）→ 不加 PO 後綴
            r[iSplit] = (norm + " PO") if (is_po and norm and norm != "錦標賽") else norm

    # 升降賽標記：以 Leaguepedia 逐場資料為準（fetch_promo.py → promo_games.json）
    # 比對條件：兩隊配對（正規化名）＋日期±1天＋聯賽相符
    _pg_path = os.path.join(CACHE_DIR, "promo_games.json")
    if os.path.exists(_pg_path):
        import datetime as _dt
        _norm = lambda s: re.sub(r"[^0-9a-z一-鿿]", "", (s or "").lower())
        _pi = {}
        for g in json.load(open(_pg_path, encoding="utf-8")).get("games", []):
            _pi.setdefault(frozenset((_norm(g["t1"]), _norm(g["t2"]))), []).append(
                (g["lg"], g.get("d") or "", str(g.get("y") or "")))
        _gi_g, _gi_t, _gi_d = gi("gameid"), gi("teamname"), gi("date")
        _gteams, _gmeta = {}, {}
        for r in filtered:
            tn = _norm(r[_gi_t])
            if not tn: continue
            gid = r[_gi_g]
            _gteams.setdefault(gid, set()).add(tn)
            _gmeta[gid] = ((r[iLeague] or ""), (r[_gi_d] or "")[:10], (r[iSplit] or ""))
        def _near(d1, d2):
            try:
                return abs((_dt.date.fromisoformat(d1) - _dt.date.fromisoformat(d2)).days) <= 1
            except Exception:
                return False
        _hit = set()
        for gid, ts in _gteams.items():
            if len(ts) != 2: continue
            ent = _pi.get(frozenset(ts))
            if not ent: continue
            lg0, d0, _sp0 = _gmeta[gid]
            # 有日期→日期±1天；wiki 無日期→退用賽季年份比對（升降賽可能掛前一年檔，年份±1容忍）
            if any(lg == lg0 and (_near(d0, d) if d else abs(int(y or 0) - year) <= 1)
                   for lg, d, y in ent):
                _hit.add(gid)
        # 時間窗層：wiki/OE 隊名不同步（改名）時配對會漏 → 用該聯賽升降賽的日期範圍（±1天）
        # 補標窗內含「非正規隊」的場次（升降賽時間與聯賽賽程差很開，窗內不會有例行賽）
        _winmap = {}
        for g in json.load(open(_pg_path, encoding="utf-8")).get("games", []):
            if g.get("d"): _winmap.setdefault((g["lg"], str(g.get("y") or "")), []).append(g["d"])
        # 同一 (聯賽, 賽季年) 可能含春/夏兩次升降賽（相隔數月）——直接 min~max 會做出
        # 跨大半年的假窗把例行賽蓋進去 → 按日期聚類切窗（相鄰 ≤14 天視為同一窗）
        _windows = []
        for (lg2, _y2), ds in _winmap.items():
            ds = sorted(set(ds))
            a = b = ds[0]
            for x in ds[1:]:
                try:
                    gap = (_dt.date.fromisoformat(x) - _dt.date.fromisoformat(b)).days
                except Exception:
                    gap = 999
                if gap <= 14:
                    b = x
                else:
                    _windows.append((lg2, a, b)); a = b = x
            _windows.append((lg2, a, b))
        def _inwin(lg0, d0):
            for lg2, a, b in _windows:
                if lg2 != lg0: continue
                try:
                    da = _dt.date.fromisoformat(a) - _dt.timedelta(days=1)
                    db = _dt.date.fromisoformat(b) + _dt.timedelta(days=1)
                    if da <= _dt.date.fromisoformat(d0) <= db: return True
                except Exception:
                    pass
            return False
        _mainN = {}   # 聯賽 → 正規賽段隊伍（正規化名）
        _lgspan = {}  # 聯賽 → 例行賽日期範圍
        _seg, _segd = {}, {}
        for r in filtered:
            sp2 = r[iSplit] or ""
            if sp2 == "升降賽" or sp2.endswith("PO"): continue
            tn = _norm(r[_gi_t])
            if not tn: continue
            key2 = ((r[iLeague] or ""), sp2)
            _seg.setdefault(key2, {}).setdefault(tn, set()).add(r[_gi_g])
            d2 = (r[_gi_d] or "")[:10]
            if d2: _segd.setdefault(key2, []).append(d2)
        _mainSegs = set()  # 正規賽段 (聯賽, split)
        for (lg2, sp2), tm in _seg.items():
            cnts = sorted((len(g2) for g2 in tm.values()), reverse=True)
            if len(cnts) >= 6 and cnts[len(cnts)//3] >= 8:
                ds2 = _segd.get((lg2, sp2)) or []
                # 整段日期都落在該聯賽升降賽窗口內 → 是升降賽段，不是例行賽
                # （VCS 2024 升降＝6隊循環各9場，會誤過例行賽門檻）
                if ds2 and _inwin(lg2, min(ds2)) and _inwin(lg2, max(ds2)):
                    continue
                _mainN.setdefault(lg2, set()).update(tm.keys())
                _mainSegs.add((lg2, sp2))
                if ds2:
                    a0, b0 = _lgspan.get(lg2, ("9999", "0000"))
                    _lgspan[lg2] = (min(a0, min(ds2)), max(b0, max(ds2)))
        _cand = {}  # 窗內散段候選：(聯賽, split) → gid 集合
        for gid, ts in _gteams.items():
            if gid in _hit or len(ts) != 2: continue
            lg0, d0, sp0 = _gmeta[gid]
            if not d0 or not _inwin(lg0, d0): continue
            if sp0 == "升降賽" or sp0.endswith("PO"): continue      # 季後賽/已標者絕不動
            if (lg0, sp0) in _mainSegs: continue                    # 例行賽段不動
            _cand.setdefault((lg0, sp0), set()).add(gid)
        # 段級判定：窗內散段須含足量「非正規隊」才標升降（升降賽必有次級/改名隊；
        # 全是正規隊的散段是區域資格賽 gauntlet，日期恰與升降賽重疊也不能標）
        for (lg0, _sp0), gids in _cand.items():
            tset = set()
            for g2 in gids: tset |= _gteams.get(g2) or set()
            known = _mainN.get(lg0) or set()
            strangers = sum(1 for t in tset if t not in known)
            if strangers * 3 >= len(tset):
                _hit |= gids
        if _hit:
            for r in filtered:
                if r[_gi_g] in _hit:
                    r[iSplit] = "升降賽"
            print(f"  升降賽(wiki 比對)：{len(_hit)} 場")
        # 補漏層：wiki 場次不全時（如 LCP 升降賽前段輪次），小型賽段若 ≥60% 隊伍
        # 不屬於該聯賽正規隊 → 整段標升降賽（只影響 wiki 沒標到的場次）
        # 閘門：加盟制聯賽（LTA 等）沒有升降賽，不跑補漏（避免小賽段誤標）
        PROMO_OK = {
            "LCS": (2013, 2017), "LEC": (2013, 2018), "LCK": (2013, 2020), "LPL": (2013, 2017),
            "CBLOL": (2014, 2020), "LJL": (2014, 2019), "LMS": (2015, 2019),
            "TCL": (2015, 2022), "LCL": (2016, 2022), "LCO": (2015, 2020),
            "VCS": (2018, 2024), "PCS": (2020, 2024), "LCP": (2025, 2099),
            "LLN": (2017, 2018), "CLS": (2017, 2018), "GPL": (2013, 2014),
        }
        _grp2 = {}
        for r in filtered:
            lg2 = (r[iLeague] or "")
            rng2 = PROMO_OK.get(lg2)
            if not (rng2 and rng2[0] <= year <= rng2[1]): continue
            sp2 = r[iSplit] or ""
            if sp2 == "升降賽" or sp2.endswith("PO"): continue
            tn = (r[_gi_t] or "").strip()
            if not tn: continue
            _grp2.setdefault((lg2, sp2), {}).setdefault(tn, set()).add(r[_gi_g])
        _mainT = {}
        for (lg2, sp2), tm in _grp2.items():
            cnts = sorted((len(g) for g in tm.values()), reverse=True)
            if len(cnts) >= 6 and cnts[len(cnts)//3] >= 8:
                _mainT.setdefault(lg2, set()).update(tm.keys())
        _hit2 = set()
        for (lg2, sp2), tm in _grp2.items():
            cnts = sorted((len(g) for g in tm.values()), reverse=True)
            if len(cnts) >= 6 and cnts[len(cnts)//3] >= 8: continue
            mt = _mainT.get(lg2)
            if not mt: continue
            unk = sum(1 for t2 in tm if t2 not in mt)
            if unk >= max(2, len(tm)*0.6):
                for g in tm.values(): _hit2 |= g
        if _hit2:
            for r in filtered:
                if r[_gi_g] in _hit2:
                    r[iSplit] = "升降賽"
            print(f"  升降賽(補漏層)：{len(_hit2)} 場")

    # PID 1-5 合併 firstbloodkill+assist → firstblood
    if iFBK>=0 and iFBA>=0 and iFB>=0:
        for r in filtered:
            try: pid = int(r[iPid] or 0)
            except ValueError: pid = 0
            if 1 <= pid <= 5:
                fbk = int(float(r[iFBK] or 0)); fba = int(float(r[iFBA] or 0))
                r[iFB] = "1" if (fbk or fba) else "0"

    # 第一輪：team rows 建 picks / banlist / picklist（banlist 另存分邊版，供「對手 ban」統計）
    pick_map, ban_acc, pick_acc, ban_side = {}, {}, {}, {}
    for r in filtered:
        if (r[iPos] or "").lower() != "team": continue
        mk = (r[iGameid], r[iGame])
        side = (r[iSide] or "").lower()
        sk = mk + (side,)
        picks = [r[iPick1+k] if iPick1>=0 else "" for k in range(5)]
        pick_map[sk] = picks
        # **空 BAN 要保留位置**（2026-07-31 使用者回報 JDG 1-2 WE 第三局）：少見但確實會發生
        # （忘記按或戰術性空 BAN）。以前把空的濾掉 → 該手之後的 BAN 全部往前擠，順位就錯了；
        # 合併版 banlist 少一格更會讓前端「對半切」把少的那手記到對面隊上。
        # 分邊版保留空格（尾端的空 BAN 不留，免得平白多出空位）；合併版仍只收有值的（統計用）。
        bans_raw = [(r[iBan1+k] if iBan1 >= 0 else "") or "" for k in range(5)]
        while bans_raw and not bans_raw[-1]:
            bans_raw.pop()
        bans = [b for b in bans_raw if b]
        ban_acc.setdefault(mk, []).extend(bans)
        ban_side.setdefault(mk, {})[side] = bans_raw
        pick_acc.setdefault(mk, []).extend(p for p in picks if p)
    ban_str  = {k: "|"+"|".join(v)+"|" for k,v in ban_acc.items()}
    banb_str = {k: "|"+"|".join(d.get("blue") or [])+"|" for k,d in ban_side.items()}
    banr_str = {k: "|"+"|".join(d.get("red") or [])+"|" for k,d in ban_side.items()}
    pick_str = {k: "|"+"|".join(v)+"|" for k,v in pick_acc.items()}

    # 複製 picks 到個人列 + 建 blue/red map
    blue_map, red_map = {}, {}
    for r in filtered:
        if (r[iPos] or "").lower() != "team" and iPick1 >= 0:
            sk = (r[iGameid], r[iGame], (r[iSide] or "").lower())
            picks = pick_map.get(sk)
            if picks:
                for k in range(5): r[iPick1+k] = picks[k]
        key = (r[iGameid], r[iGame], r[iPos])
        if (r[iSide] or "").lower() == "blue": blue_map[key] = r
        else: red_map[key] = r

    # 組合 Map（各路英雄+選手）
    combo = {}
    for key, blue in blue_map.items():
        pos = (key[2] or "").lower()
        if pos not in POS5: continue
        mk = (key[0], key[1])
        e = combo.setdefault(mk, {p:["",""] for p in POS5} | {p+"_r":["",""] for p in POS5})
        e[pos] = [blue[iChamp] or "", blue[iPlayer] or ""]
        red = red_map.get(key)
        if red: e[pos+"_r"] = [red[iChamp] or "", red[iPlayer] or ""]

    shared_idx = [idx[c] for c in SHARED_COLS if c in idx]
    extra_idx  = [i for i,c in enumerate(hdr) if c not in set(SHARED_COLS) and c not in DELETE_COLS]
    merged_headers = ([c for c in SHARED_COLS if c in idx]
        + ["blue_"+hdr[i] for i in extra_idx] + ["red_"+hdr[i] for i in extra_idx]
        + ["blue_Lane","red_Lane","blue_po","red_po","banlist","picklist","blue_banlist","red_banlist"])
    p_patch = SHARED_COLS.index("patch"); p_res = SHARED_COLS.index("result"); p_pid = SHARED_COLS.index("participantid")

    merged = []
    for key, blue in blue_map.items():
        red = red_map.get(key)
        if red is None: continue
        row = [blue[i] for i in shared_idx] + [blue[i] for i in extra_idx] + [red[i] for i in extra_idx]
        try: row[p_patch] = f"{float(row[p_patch])+10:.2f}"
        except (ValueError, TypeError): pass
        try: row[p_res] = 1 if int(row[p_res]) == 1 else 2
        except (ValueError, TypeError): row[p_res] = 2
        mk = (blue[iGameid], blue[iGame])
        c = combo.get(mk, {p:["",""] for p in POS5} | {p+"_r":["",""] for p in POS5})
        try: pid = int(row[p_pid] or 0)
        except ValueError: pid = 0

        if pid in (4,5):
            bfp = "|".join([c["bot"][0], c["sup"][0], c["bot"][1], c["sup"][1]])
            rfp = "|".join([c["bot_r"][0], c["sup_r"][0], c["bot_r"][1], c["sup_r"][1]])
        elif pid in (2,3):
            bfp = "|".join([c["mid"][0], c["jng"][0], c["mid"][1], c["jng"][1]])
            rfp = "|".join([c["mid_r"][0], c["jng_r"][0], c["mid_r"][1], c["jng_r"][1]])
        elif pid == 100:
            bfp = "|" + "|".join([c[p][0] for p in POS5] + [c[p][1] for p in POS5]) + "|"
            rfp = "|" + "|".join([c[p+"_r"][0] for p in POS5] + [c[p+"_r"][1] for p in POS5]) + "|"
        else:
            bfp = rfp = ""
        row.append(bfp); row.append(rfp)

        try: first = 1 if int(blue[iFP]) == 1 else 0
        except (ValueError, TypeError): first = 0
        bpicks = [blue[iPick1+k] if iPick1>=0 else "" for k in range(5)]
        rpicks = [red[iPick1+k] if iPick1>=0 else "" for k in range(5)]
        if pid == 100:
            row.append("|".join(str(calc_po(c[p][0], bpicks, True, first)) for p in POS5))
            row.append("|".join(str(calc_po(c[p+"_r"][0], rpicks, False, first)) for p in POS5))
        else:
            row.append(calc_po(blue[iChamp] or "", bpicks, True, first))
            row.append(calc_po(red[iChamp] or "", rpicks, False, first))
        row.append(ban_str.get(mk, "||")); row.append(pick_str.get(mk, "||"))
        row.append(banb_str.get(mk, "||")); row.append(banr_str.get(mk, "||"))
        merged.append(row)

    # 排序
    d_lg = merged_headers.index("league"); d_dt = merged_headers.index("date")
    d_gm = merged_headers.index("game"); d_pid = merged_headers.index("participantid")
    def fnum(v):
        try: return float(v)
        except (ValueError, TypeError): return 0
    merged.sort(key=lambda r:(LEAGUE_ORDER.get(r[d_lg],99), str(r[d_dt]), fnum(r[d_gm]), fnum(r[d_pid])))

    # decider_winner
    d_bt = merged_headers.index("blue_teamname"); d_rt = merged_headers.index("red_teamname")
    series_max = {}
    for r in merged:
        k = (str(r[d_dt])[:10], *sorted([r[d_bt] or "", r[d_rt] or ""]))
        g = fnum(r[d_gm])
        if g > series_max.get(k, 0): series_max[k] = g
    merged_headers.append("decider_winner")
    for r in merged:
        k = (str(r[d_dt])[:10], *sorted([r[d_bt] or "", r[d_rt] or ""]))
        r.append(r[p_res] if fnum(r[d_gm]) == series_max.get(k) else 0)

    return [merged_headers] + merged


# ── 世界賽(WLDs)後的比賽（KeSPA盃等）歸入隔年：世界賽後大多換人 ──
def split_spill(table):
    hdr = table[0]; rows = table[1:]
    iL = hdr.index("league"); iD = hdr.index("date")
    wd = [str(r[iD]) for r in rows if r[iL] == "WLDs"]
    if not wd:
        return table, [hdr]
    cutoff = max(wd)
    keep  = [r for r in rows if str(r[iD]) <= cutoff]
    spill = [r for r in rows if str(r[iD]) >  cutoff]
    return [hdr] + keep, [hdr] + spill


def spill_path(year):
    return os.path.join(HERE, "csv_cache", f"spill_{year}.json")


def save_spill(year, table):
    os.makedirs(os.path.join(HERE, "csv_cache"), exist_ok=True)
    with open(spill_path(year), "w", encoding="utf-8") as f:
        json.dump(table, f, ensure_ascii=False)
    if len(table) > 1:
        print(f"  世界賽後 {len(table)-1} 列 → 移入 {year} 年")


def load_spill(year):
    p = spill_path(year)
    if not os.path.exists(p): return None
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except Exception: return None


def remap_rows(src_table, target_hdr):
    """跨年併入時，把去年的欄位順序對映到今年的表頭（缺欄補空）"""
    sh = src_table[0]; idx = {h: i for i, h in enumerate(sh)}
    out = []
    for r in src_table[1:]:
        out.append([r[idx[h]] if h in idx and idx[h] < len(r) else "" for h in target_hdr])
    return out


def write_year(year, table):
    path = os.path.join(HERE, "data", f"data_{year}.js")
    data = {"fetched_at": keep_stamp(path, "fetched_at"), "year": year,
            "sheet_title": f"Oracle's Elixir {year}", "tabs": {"RAW_DATA": table}}
    js = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    with open(path, "w", encoding="utf-8") as f:
        f.write("window.LOL_DATA=" + js + ";")
    print(f"  → data_{year}.js（{len(table)-1} 列，{os.path.getsize(path)//1024} KB）")


def write_manifest():
    years = sorted(int(f[5:9]) for f in os.listdir(os.path.join(HERE, "data"))
                   if f.startswith("data_") and f.endswith(".js") and f[5:9].isdigit())
    mf = os.path.join(HERE, "data.js")
    m = {"years": years, "default": DEFAULT_YEAR if DEFAULT_YEAR in years else (years[-1] if years else DEFAULT_YEAR),
         "updated": keep_stamp(mf, "updated")}
    with open(os.path.join(HERE, "data.js"), "w", encoding="utf-8") as f:
        f.write("window.LOL_MANIFEST=" + json.dumps(m) + ";")
    print(f"manifest：{years}")


def merge_wiki(year, table):
    """併入 csv_cache/wikifill_{年}.json（scripts/fetch_wiki_mh.py 由 Leaguepedia 文字版 Match History 產生）。
    用途＝**OE 根本沒收錄的老賽季**（如 LPL 2016 春季以前、2013 全年）。
    與 fill_/patch_ 相同鐵則：同一局（聯賽+賽段+日期+兩隊+局號）OE 有就丟掉補充版。"""
    p = os.path.join(CACHE_DIR, f"wikifill_{year}.json")
    if not os.path.exists(p):
        return table
    try:
        with open(p, encoding="utf-8") as f:
            D = json.load(f)
    except Exception as e:
        print(f"  ⚠ wiki 補充資料讀取失敗（略過）：{e}"); return table
    if not D:
        return table
    hdr = table[0]
    iL, iS, iD = hdr.index("league"), hdr.index("split"), hdr.index("date")
    iG, iP = hdr.index("game"), hdr.index("participantid")
    iBT, iRT = hdr.index("blue_teamname"), hdr.index("red_teamname")
    # 去重鍵**不含 split**（2026-08-01 修）：OE 對盃賽的賽段欄是空的，wiki 版帶站名
    #（IEM 的「S9 世界賽」），把 split 算進鍵會判成兩場不同的比賽 → 2015~2017 的 IEM
    # 整批重複收錄（使用者要求分站後才發現）。兩隊用 frozenset 比，藍紅顛倒也算同一局。
    iBC, iRC = hdr.index("blue_champion"), hdr.index("red_champion")
    gkey = lambda r: (r[iL], str(r[iD])[:10],
                      frozenset((r[iBT] or "", r[iRT] or "")), str(r[iG]), str(r[iP]))
    # 第二層「同一局」判定：日期＋該局十個英雄。同一支隊兩邊寫法可能不同（wiki 的
    # GE Tigers ＝ OE 的 ROX Tigers），只靠隊名鍵會對不上而把同一局收兩份；而十個英雄
    # 的組合對一局來說是固定的，跟隊名、局號怎麼標都無關。**不能只用英雄不看局**——
    # 早年英雄池小，逐列比對（pid＋兩個英雄）會把同日不同場誤判成同一局（實測 2013 掉了
    # 1474 列）。所以先分組成局，再比整局的英雄集合。（2026-08-01）
    def _by_game(rows):
        g = {}
        for r in rows:
            g.setdefault((r[iL], str(r[iD])[:10], str(r[iG]),
                          frozenset((r[iBT] or "", r[iRT] or ""))), []).append(r)
        return g

    iPLc = hdr.index("picklist")

    def _cset(rs):
        s = {str(x) for r in rs for x in (r[iBC], r[iRC]) if x}
        # PB 補的局**只有隊伍列、沒有逐選手英雄** → 這裡會是空集合，去重就退回位置式比對
        # （聯賽+日期+兩隊+局號），而 gol.gg 只抓到系列中一局時局號本來就不可靠
        # → 曾把「真正缺的那局」當成重複砍掉、留下重複的那局（2026-08-03 實例：
        #   LCK 08-01 DK vs GEN，gol.gg 標成 G1 的其實是第 2 局）。
        # 隊伍列本身有 picklist（十隻英雄），拿它補算集合就對得起來了。
        if len(s) < 8:
            for r in rs:
                s |= {x.strip() for x in str(r[iPLc]).split("|") if x.strip()}
        return frozenset(s)

    have = {gkey(r) for r in table[1:]}
    oe_c = {}
    for k, rs in _by_game(table[1:]).items():
        cs = _cset(rs)
        if len(cs) >= 8:                       # 十個英雄齊全才拿來當識別（有缺就不夠獨特）
            oe_c.setdefault((k[0], k[1], cs), []).extend(rs)
    for key, v in D.items():
        rows = remap_rows([v["header"]] + v["rows"], hdr)
        keep, filled, dup = [], 0, 0
        for k, rs in _by_game(rows).items():
            cs = _cset(rs)
            old = oe_c.get((k[0], k[1], cs)) if len(cs) >= 8 else None
            # 位置式比對（聯賽+日期+兩隊+局號+pid）只在**英雄集合不可用**時才算數。
            # 十隻英雄齊全卻對不到任何既有局＝真的是另一局，不能因為局號撞到就丟掉：
            # 來源只抓到系列中一局時局號本來就不可靠（2026-08-03 實例：LCK 08-01 DK vs GEN，
            # gol.gg 標成 G1 的其實是第 2 局，真正缺的第 1 局因局號同為 1 被誤判成重複）。
            _gk_dup = all(gkey(r) in have for r in rs) and not (len(cs) >= 8 and not old)
            if old or _gk_dup:
                dup += len(rs)
                sp = next((str(r[iS]) for r in rs if str(r[iS]).strip()), "")
                if sp and old:                 # OE 沒填賽段（盃賽常見）→ 用 wiki 的站名補上
                    for o in old:
                        if not str(o[iS]).strip():
                            o[iS] = sp; filled += 1
                continue
            keep += rs
            for r in rs:
                have.add(gkey(r))
            if len(cs) >= 8:
                oe_c.setdefault((k[0], k[1], cs), []).extend(rs)
        if keep:
            table = table + keep
        if not keep:
            print(f"  wiki {key}：OE 已全數收錄 → 不併入"
                  + (f"（補上賽段 {filled} 列）" if filled else "")); continue
        print(f"  wiki {key}：+{len(keep)} 列（{v.get('src','?')}；OE 已有的 {dup} 列略過"
              + (f"，其中補上賽段 {filled} 列" if filled else "") + "）")
    return table


# 人工判定的幽靈局（來源殘留的假局）：刪除該局所有列，並把同系列剩餘局依時間重編 1..n。
# ⚠ 判定用**完整時間戳前綴**不用局號——這裡跑在 fix_game_no 之前，撞號還沒重編，
# 用局號會連真局一起殺（實測 game=1 會同時吃掉 gol.gg 殘局與 PB 真局 6 列）。
# 2026-08-01 LCK DK vs GEN：真實只有兩局（wiki 記 gi1,2），資料裡卻多一個只有 1 列、
# 00:21 的殘局（gol.gg 補檔殘留），把真局擠成 2、3 → BP 顯示多一局、選邊也對不上
#（2026-08-05 使用者回報）。來源修好後可移除該條。
BAD_GAMES = [("LCK", "2026-08-01 00:21", "Dplus Kia", "Gen.G")]


def fix_bad_games(table):
    hdr = table[0]
    try:
        iL, iD, iG = hdr.index("league"), hdr.index("date"), hdr.index("game")
        iBT, iRT = hdr.index("blue_teamname"), hdr.index("red_teamname")
    except ValueError:
        return table
    out = [hdr]
    dropped = 0
    touched = set()
    for r in table[1:]:
        hit = next((b for b in BAD_GAMES
                    if r[iL] == b[0] and str(r[iD]).startswith(b[1])
                    and {str(r[iBT]), str(r[iRT])} == {b[2], b[3]}), None)
        if hit:
            dropped += 1
            touched.add((r[iL], str(r[iD])[:10], frozenset((str(r[iBT]), str(r[iRT])))))
            continue
        out.append(r)
    if not dropped:
        return table
    # 同系列（同日同兩隊）剩餘局依 (完整時間, 原局號) 重編 1..n，
    # 不然殘局剔除後局號從 2 起跳，選邊比對用的 gi 會全部落空。
    for grp in touched:
        rows = [r for r in out[1:] if (r[iL], str(r[iD])[:10], frozenset((str(r[iBT]), str(r[iRT])))) == grp]
        seq = sorted({(str(r[iD]), str(r[iG])) for r in rows})
        num = {k: i + 1 for i, k in enumerate(seq)}
        for r in rows:
            r[iG] = num[(str(r[iD]), str(r[iG]))]
    print(f"  幽靈局剔除 {dropped} 列（{len(touched)} 個系列重編局號）")
    return out


def fix_game_no(table):
    """同一天、同兩隊出現**重複局號**時，依實際時間先後重編。

    為什麼會撞號（2026-08-03 實例）：來源只收錄系列中的一局時，它的局號本來就不可靠——
    gol.gg 對 LCK 08-01 DK vs GEN 只有第 2 局，卻標成 G1；PB 補進真正的第 1 局後兩局都叫 G1。
    前端以 (日期,局號) 分辨小局，撞號會少算一局（等於白補）。
    只動「真的撞號」的組，其他一律不碰。
    """
    hdr = table[0]
    try:
        iL, iD, iG = hdr.index("league"), hdr.index("date"), hdr.index("game")
        iBT, iRT = hdr.index("blue_teamname"), hdr.index("red_teamname")
    except ValueError:
        return table
    grp = {}
    for r in table[1:]:
        k = (r[iL], str(r[iD])[:10], frozenset((str(r[iBT]), str(r[iRT]))))
        grp.setdefault(k, {}).setdefault((str(r[iD]), str(r[iG])), []).append(r)
    n = 0
    for k, games in grp.items():
        nums = [g for _, g in games]
        if len(set(nums)) == len(nums):
            continue                                   # 沒撞號
        for i, dtg in enumerate(sorted(games, key=lambda x: x[0]), 1):
            if str(games[dtg][0][iG]) != str(i):
                n += 1
            for r in games[dtg]:
                r[iG] = i
    if n:
        print(f"  局號重編 {n} 局（同日同兩隊撞號 → 依時間先後）")
    return table


def fix_firstpick(table):
    """收尾：補上仍為空的 firstPick，並依它把 po 重算一遍。

    為什麼還會有空的（2026-08-02）：補充來源（wikifill_／fill_ JSON）存的是**已經 process 過
    的列**，改了推導邏輯不會自動生效，要重跑該來源才會。但有些賽段的 Leaguepedia 賽事名
    已不可考（孤兒 key，2013 GPL 春夏／TESL、各區錦標賽等 427 局），根本無從重生 → 在這裡收尾。

    空字串在 calc_po 是 int("") 例外 → first=0 → **藍方整批被當成後選方，順位左右對調**，
    而且完全不會報錯。**2025 以前藍方固定先選**（使用者定案 2026-08-02），所以補藍方是正解；
    2026 起先選與藍紅脫鉤，真值只能來自來源，補不了的只好沿用藍方。
    po 必須跟著重算，否則 firstPick 補對了、po 還是照 first=0 算出來的（兩者互相矛盾）。
    """
    hdr = table[0]
    try:
        iFP, iRFP = hdr.index("blue_firstPick"), hdr.index("red_firstPick")
        iPid, iPL = hdr.index("participantid"), hdr.index("picklist")
        iBP, iRP = hdr.index("blue_po"), hdr.index("red_po")
        iBC, iRC = hdr.index("blue_champion"), hdr.index("red_champion")
        iBL, iRL = hdr.index("blue_Lane"), hdr.index("red_Lane")
    except ValueError:
        return table
    # 隊伍列(pid=100)的 po 是「|」串起來的**路線序**五個值 → 要用 blue_Lane 的路線序英雄去算，
    # 不能拿 picklist（選角序）當來源，順序會整組錯位。
    lane5 = lambda v: (str(v).split("|") + [""] * 7)[1:6]
    n = 0
    for r in table[1:]:
        if str(r[iFP]).strip():
            continue
        r[iFP], r[iRFP] = "1", "0"          # 藍方先選
        n += 1
        pl = [x for x in str(r[iPL]).split("|")]      # "|藍5|紅5|" → 去頭尾空元素
        pl = pl[1:11] if len(pl) >= 12 else [x for x in pl if x.strip()]
        if len(pl) < 10:
            continue
        bp, rp = pl[:5], pl[5:10]
        if str(r[iPid]) == "100":
            r[iBP] = "|".join(str(calc_po(c, bp, True, 1)) for c in lane5(r[iBL]))
            r[iRP] = "|".join(str(calc_po(c, rp, False, 1)) for c in lane5(r[iRL]))
        else:
            r[iBP] = calc_po(r[iBC] or "", bp, True, 1)
            r[iRP] = calc_po(r[iRC] or "", rp, False, 1)
    if n:
        print(f"  firstPick 收尾補值 {n} 列（藍方先選＋重算 po）")
    return table


def fix_firstpick_wiki(table, year):
    """2026 起：以 wiki「VODs & Match Links」的 Pick Sel 顏色（side_sel.js 的 pc）校正
    blue_firstPick／red_firstPick，並把 po 重算。

    為什麼需要（2026-08-03 使用者抓包 LGD）：OE 沒給 firstPick 的局，fix_firstpick 一律
    補「藍方先選」，但 2026 新制先選與藍紅脫鉤——實測 35 局與 wiki 官方紀錄相反
    （LPL 20／EWC 6／LCK 2…），而 po 就是照錯的先選方算的。前端已在顯示層以 wiki 覆寫
    先選/後選標籤，這裡把資料本體連 po 一起修，兩邊才不會互相矛盾（選擇欄寫後選、
    金字順位卻是先選那組）。

    對齊鍵與前端 ssRec 同一套：日期(前10碼)＋兩隊全名正規化(去括號註記/去非英數/去 CN 尾綴)
    排序＋局號。握選序權的隊＝選邊權(ss)的對面；pc=1 它先選、pc=2 它後選。
    """
    if int(year) < 2026:
        return table
    sp = os.path.join(HERE, "side_sel.js")
    if not os.path.exists(sp):
        return table
    try:
        recs = json.loads(open(sp, encoding="utf-8").read().split("=", 1)[1].strip().rstrip(";"))
    except Exception as e:
        print(f"  ⚠ side_sel.js 讀取失敗（{type(e).__name__}）→ 跳過 firstPick 校正")
        return table
    norm = lambda s: re.sub(r"cn$", "", re.sub(r"[^a-z0-9]", "", re.sub(r"\([^)]*\)", "", str(s or "")).lower()))
    truth = {}
    for r in recs:
        if r.get("ss") not in ("b", "r") or r.get("pc") not in (1, 2):
            continue
        pk_blue = r["ss"] == "r"                       # 選邊權在紅 → 選序權在藍
        first_blue = pk_blue == (r["pc"] == 1)         # 選序那隊 pc=1 先選／pc=2 後選
        key = (str(r.get("d"))[:10], "|".join(sorted([norm(r.get("t1")), norm(r.get("t2"))])), str(r.get("gi") or ""))
        truth[key] = "1" if first_blue else "0"
    if not truth:
        return table
    hdr = table[0]
    try:
        iFP, iRFP = hdr.index("blue_firstPick"), hdr.index("red_firstPick")
        iPid, iPL = hdr.index("participantid"), hdr.index("picklist")
        iBP, iRP = hdr.index("blue_po"), hdr.index("red_po")
        iBC, iRC = hdr.index("blue_champion"), hdr.index("red_champion")
        iBL, iRL = hdr.index("blue_Lane"), hdr.index("red_Lane")
        iBT, iRT = hdr.index("blue_teamname"), hdr.index("red_teamname")
        iD, iG = hdr.index("date"), hdr.index("game")
    except ValueError:
        return table
    lane5 = lambda v: (str(v).split("|") + [""] * 7)[1:6]
    n = 0
    for r in table[1:]:
        key = (str(r[iD])[:10], "|".join(sorted([norm(r[iBT]), norm(r[iRT])])), str(r[iG]).strip())
        fb = truth.get(key)
        if fb is None:
            continue
        cur = "1" if str(r[iFP]).strip() in ("1", "1.0") else "0"
        if cur == fb:
            continue
        r[iFP], r[iRFP] = fb, ("0" if fb == "1" else "1")
        first = 1 if fb == "1" else 0
        pl = [x for x in str(r[iPL]).split("|")]
        pl = pl[1:11] if len(pl) >= 12 else [x for x in pl if x.strip()]
        n += 1
        if len(pl) < 10:
            continue
        bp, rp = pl[:5], pl[5:10]
        if str(r[iPid]) == "100":
            r[iBP] = "|".join(str(calc_po(c, bp, True, first)) for c in lane5(r[iBL]))
            r[iRP] = "|".join(str(calc_po(c, rp, False, first)) for c in lane5(r[iRL]))
        else:
            r[iBP] = calc_po(r[iBC] or "", bp, True, first)
            r[iRP] = calc_po(r[iRC] or "", rp, False, first)
    if n:
        print(f"  firstPick 依 wiki 校正 {n} 列（含 po 重算）")
    return table


def unify_players(table):
    """選手 ID 大小寫統一（PLAYER_ALIAS）。

    必須排在 merge_fill／merge_wiki／merge_patch **之後**：那些補充來源存的是「process() 之後的列」，
    直接併進 table，不會經過 process() 裡那次正規化 → 只改 process() 的話，wiki 補回來的
    watch/San 之類仍會跟 OE 的 Watch/san 拆成兩份生涯（2026-07-31 實測）。
    """
    if not table or not PLAYER_ALIAS:
        return table
    ix = {n: i for i, n in enumerate(table[0])}
    cols = [ix[c] for c in ("blue_playername", "red_playername") if c in ix]
    if not cols:
        return table
    n = 0
    for r in table[1:]:
        for c in cols:
            v = str(r[c] or "").strip()
            t = PLAYER_ALIAS.get(v.casefold())
            if t and t != v:
                r[c] = t; n += 1
    if n:
        print(f"  選手 ID 大小寫統一：{n} 處")
    return table


def merge_patch(year, table):
    """併入 csv_cache/patch_{年}.json：OE 有這局、但某些欄位是空的（如 07-28 KeSPA BRO vs DNS 的 BP）
    → 由 scripts/fetch_bp_fill.py 從 gol.gg 補。**只填空欄位**，OE 已有值的一律不動（以 OE 為準）。
    OE 之後自己補上 → 該欄不再是空的，修補自然失效。"""
    p = os.path.join(CACHE_DIR, f"patch_{year}.json")
    if not os.path.exists(p):
        return table
    try:
        with open(p, encoding="utf-8") as f:
            P = json.load(f)
    except Exception as e:
        print(f"  ⚠ 修補資料讀取失敗（略過）：{e}")
        return table
    if not P:
        return table
    hdr = table[0]
    iL, iD = hdr.index("league"), hdr.index("date")
    iG = hdr.index("game")
    iBT, iRT = hdr.index("blue_teamname"), hdr.index("red_teamname")
    key = lambda r: "|".join([str(r[iL]), str(r[iD])[:10], str(r[iBT]), str(r[iRT]), str(r[iG])])
    used, filled = set(), 0
    for r in table[1:]:
        pv = P.get(key(r))
        if not pv:
            continue
        for col, val in pv.items():
            if col not in hdr or not val:
                continue
            j = hdr.index(col)
            if str(r[j] or "").strip(" |") == "":     # 只填空的
                r[j] = val; filled += 1
        used.add(key(r))
    if filled:
        print(f"  修補 {len(used)} 局／{filled} 欄（gol.gg；只填 OE 空著的欄位）")
    return table


def merge_stats(year, table):
    """併入 csv_cache/wikistats_{年}.json（scripts/fetch_wiki_stats.py 由 Leaguepedia
    Cargo 表 ScoreboardPlayers 產生）：**這局 OE／wiki 都有，但逐選手數據是空的**。

    為什麼需要：2013~2016 老賽季靠 merge_wiki 從 MatchHistoryGame 文字版補進來，
    那個來源只有選手與英雄，沒有 K/D/A、CS、金錢 → 這些欄位全空
    （實測空值率 2013 100%／2014 55%／2015 40%／2016 7%）。

    與 merge_patch 相同鐵則：**只填空欄位**，已有值的一律不動。
    配對鍵：開賽時間+系列賽第幾場+選手；兩邊 game 序號偶爾顛倒，退而用
    開賽時間+選手+英雄（實測 2013-04 全月覆蓋 100%、歧義 0%）。"""
    p = os.path.join(CACHE_DIR, f"wikistats_{year}.json")
    if not os.path.exists(p):
        return table
    try:
        with open(p, encoding="utf-8") as f:
            S = json.load(f)
    except Exception as e:
        print(f"  ⚠ 逐選手數據讀取失敗（略過）：{e}")
        return table
    if not S:
        return table
    hdr = table[0]
    ix = {n: i for i, n in enumerate(hdr)}
    iD, iG = ix.get("date"), ix.get("game")
    if iD is None or iG is None:
        return table
    _n = lambda s: re.sub(r"[^a-z0-9]", "", str(s or "").lower())
    filled = collections.Counter()
    hit = miss = 0
    for r in table[1:]:
        dt, gm = str(r[iD])[:16], str(r[iG] or "").strip()
        for pre in ("blue", "red"):
            ip, ic = ix.get(pre + "_playername"), ix.get(pre + "_champion")
            if ip is None:
                continue
            nm = _n(r[ip])
            if not nm:
                continue
            v = S.get("|".join((dt, gm, nm)))
            if v is None and ic is not None:
                v = S.get("|".join((dt, "*", nm, _n(r[ic]))))
            if v is None:
                miss += 1
                continue
            hit += 1
            for col, val in v.items():
                if not val:
                    continue
                # patch 是整列共用欄（非 blue_/red_）：wiki 早年賽事常沒填版本
                j = ix.get("patch") if col == "patch" else ix.get(f"{pre}_{col}")
                if j is None:
                    continue
                if str(r[j] or "").strip() == "":        # 只填空的
                    r[j] = val
                    filled[col] += 1
    if filled:
        tot = sum(filled.values())
        print(f"  逐選手數據 {hit} 人次對上（{miss} 落空）／補 {tot} 欄："
              + "、".join(f"{k} {v}" for k, v in filled.most_common()))
    return table


def fill_cup_split(year, table):
    """分站盃賽（IEM）OE 沒填賽段 → 用同一份資料裡已標好賽段的比賽日期範圍回填。

    merge_wiki 會逐局比對補一輪，但兩邊隊名寫法不同的對不上（wiki 寫 GE Tigers、
    OE 寫 ROX Tigers），那些列的賽段還是空的。各站的舉辦日期本來就不重疊，
    用日期落點判斷是安全的。（使用者要求 2026-08-01：IEM 每站站名都要標清楚）
    """
    hdr = table[0]
    iL, iS, iD = hdr.index("league"), hdr.index("split"), hdr.index("date")
    rng = {}
    for r in table[1:]:
        sp = str(r[iS] or "").strip()
        if r[iL] != "IEM" or not sp:
            continue
        d = str(r[iD])[:10]
        a = rng.get(sp)
        rng[sp] = (min(a[0], d), max(a[1], d)) if a else (d, d)
    if not rng:
        return table

    def _shift(d, k):                          # 日期前後挪一天（不引 datetime，字串夠用）
        import datetime as _dt
        try:
            return (_dt.date(*map(int, d.split("-"))) + _dt.timedelta(days=k)).isoformat()
        except Exception:
            return d

    # 範圍前後各放寬一天：OE 用 UTC、Leaguepedia 用當地日期，跨日的決賽會差一天
    #（IEM Oakland 2016 決賽 wiki 記 11-20、OE 記 11-21）
    rng = {sp: (_shift(a, -1), _shift(b, 1)) for sp, (a, b) in rng.items()}
    n = 0
    for r in table[1:]:
        if r[iL] != "IEM" or str(r[iS] or "").strip():
            continue
        d = str(r[iD])[:10]
        for sp, (a, b) in rng.items():
            if a <= d <= b:
                r[iS] = sp
                n += 1
                break
    if n:
        print(f"  IEM 賽段依日期回填 {n} 列")
    return table


def merge_patch_release(year, table):
    """用官方改版日期補空的 patch 欄（csv_cache/patch_release.json，
    由 scripts/fetch_patch_release.py 從 LoL wiki 的版本頁抓）。

    為什麼需要：早年 wiki 來源（MatchHistoryGame／Picks and Bans）都沒有版本欄，
    OE 對 2013~2015 本身也大量空缺（實測 2013 有 89%、2014 58%、2015 35% 的場次
    沒有版本號）。使用者定案 2026-07-31：**用改版日期回推**——比賽日期落在哪兩個
    改版之間，就算哪一版。

    只填空的，OE／wiki 已有的值一律不動。註：職業賽常鎖舊版，回推值與實際開打
    版本可能差一版（2013-07-19 那批回推是 3.9，同期 LPL 實際還在打 3.8），
    這是使用者選定的取捨。"""
    p = os.path.join(CACHE_DIR, "patch_release.json")
    if not os.path.exists(p):
        return table
    try:
        REL = json.load(open(p, encoding="utf-8"))
    except Exception as e:
        print(f"  ⚠ 改版日期表讀取失敗（版本欄留空）：{e}")
        return table
    if not REL:
        return table
    rel = sorted(((d, k) for k, d in REL.items() if d), reverse=True)   # 新→舊
    hdr = table[0]
    ix = {n: i for i, n in enumerate(hdr)}
    ip, idt = ix.get("patch"), ix.get("date")
    if ip is None or idt is None:
        return table
    n = 0
    for r in table[1:]:
        if str(r[ip] or "").strip():
            continue
        d = str(r[idt])[:10]
        for rd, k in rel:
            if rd <= d:
                r[ip] = k
                n += 1
                break
    if n:
        print(f"  版本補值 {n} 列（依官方改版日期）")
    return table


def merge_fill(year, table):
    """併入 csv_cache/fill_{年}.json：OE 尚未收錄的賽段補充資料（scripts/fetch_fill.py 由 gol.gg 產生）。

    使用者定案：**OE 有更新後就不再用補充資料**。這裡是第二道閘門——逐局比對，
    同一局（聯賽+賽段+日期+兩隊+局號）只要 OE 有，補充版一律丟掉；整段被 OE 追上時補充資料自然全數落空。
    （第一道在 fetch_fill.py：OE 局數追上就連抓都不抓。）
    """
    p = os.path.join(CACHE_DIR, f"fill_{year}.json")
    if not os.path.exists(p):
        return table
    try:
        with open(p, encoding="utf-8") as f:
            D = json.load(f)
    except Exception as e:
        print(f"  ⚠ 補充資料讀取失敗（略過）：{e}")
        return table
    if not D:
        return table
    hdr = table[0]
    iL, iS, iD = hdr.index("league"), hdr.index("split"), hdr.index("date")
    iG, iP = hdr.index("game"), hdr.index("participantid")
    iBT, iRT = hdr.index("blue_teamname"), hdr.index("red_teamname")
    gkey = lambda r: (r[iL], str(r[iS]).split(" PO")[0], str(r[iD])[:10],
                      frozenset((r[iBT] or "", r[iRT] or "")), str(r[iG]), str(r[iP]))
    have = {gkey(r) for r in table[1:]}
    added = 0
    for key, v in D.items():
        rows = remap_rows([v["header"]] + v["rows"], hdr)
        keep = [r for r in rows if gkey(r) not in have]
        if not keep:
            print(f"  補充 {key}：OE 已全數收錄 → 不併入")
            continue
        table = table + keep
        added += len(keep)
        print(f"  補充 {key}：+{len(keep)} 列（{v.get('src','?')}；OE 已有的 {len(rows)-len(keep)} 列略過）")
    if added:
        d_lg, d_dt = hdr.index("league"), hdr.index("date")
        d_gm, d_pid = hdr.index("game"), hdr.index("participantid")
        fnum = lambda v: float(v) if str(v).replace(".", "", 1).replace("-", "", 1).isdigit() else 0
        table = [hdr] + sorted(table[1:], key=lambda r: (LEAGUE_ORDER.get(r[d_lg], 99), str(r[d_dt]),
                                                        fnum(r[d_gm]), fnum(r[d_pid])))
    return table


def main():
    args = [a for a in sys.argv[1:]]
    force_all = "--force" in args
    pick_years = [int(a) for a in args if a.isdigit()]
    targets = pick_years or YEARS
    for y in targets:
        out = os.path.join(HERE, "data", f"data_{y}.js")
        # 今年每天重抓；歷史年份有檔就跳過（除非 --force 或指定年份）
        if not force_all and not pick_years and y != DEFAULT_YEAR and os.path.exists(out):
            continue
        print(f"[{y}]")
        try:
            table = process(download(y), y)
        except urllib.error.HTTPError as e:
            # OE 沒有該年份（2013 及更早）→ 若有 wiki 補充資料就用它自己建表
            wp = os.path.join(CACHE_DIR, f"wikifill_{y}.json")
            if os.path.exists(wp):
                try:
                    with open(wp, encoding="utf-8") as f:
                        WD = json.load(f)
                    ks = list(WD.keys())
                    if ks:
                        table = [WD[ks[0]]["header"]]
                        print(f"  OE 無此年份（{e.code}）→ 改用 wiki 補充資料建表")
                    else:
                        raise ValueError("wiki 檔是空的")
                except Exception as e2:
                    print(f"  跳過（{e.code}；wiki 亦不可用：{e2}）"); continue
            else:
                print(f"  跳過（{e.code}，該年份可能無資料）"); continue
        except Exception as e:
            print(f"  失敗：{e}"); continue
        # 世界賽後的比賽切出去 → 存給隔年；並把去年切來的併進今年
        table, spill = split_spill(table)
        save_spill(y + 1, spill)
        prev = load_spill(y)
        if prev and len(prev) > 1:
            table = [table[0]] + remap_rows(prev, table[0]) + table[1:]
            print(f"  併入去年世界賽後 {len(prev)-1} 列")
        table = merge_fill(y, table)
        table = merge_wiki(y, table)
        table = merge_patch(y, table)      # OE 未收錄賽段的補充資料（OE 有的一律以 OE 為準）
        table = merge_stats(y, table)      # 老賽季逐選手 KDA/CS/金錢（wiki 文字版沒有 → 只填空欄位）
        table = merge_patch_release(y, table)   # 空的版本欄依官方改版日期回推
        table = fill_cup_split(y, table)   # 盃賽分站：OE 沒填的賽段依日期回填（見函式說明）
        table = fix_bad_games(table)       # 人工判定的幽靈局剔除＋該系列局號重編（要在 fix_game_no 前）
        table = fix_game_no(table)         # 同日同兩隊撞局號 → 依時間重編（要排在所有 merge 之後）
        table = fix_firstpick(table)       # 補充來源留下的空 firstPick 收尾（要排在所有 merge 之後）
        table = fix_firstpick_wiki(table, y)  # 2026+：wiki Pick Sel 顏色校正先選方＋po（要在 fix_firstpick 之後）
        table = unify_players(table)       # 選手 ID 大小寫統一（要排在所有 merge 之後，見下）
        write_year(y, table)
    write_manifest()
    print("完成")


if __name__ == "__main__":
    main()
