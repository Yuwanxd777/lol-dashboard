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
import csv, io, json, os, re, sys, urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 專案根目錄（本腳本在 scripts\ 內）
# Oracle's Elixir 官方公開 Google Drive 資料夾（免認證）
OE_FOLDER = "1gLSw0RLjBbtaNy0dgnGQDAZOHIgCe-HH"
FIRST_YEAR = 2014
NOW = datetime.now()
DEFAULT_YEAR = NOW.year
YEARS = list(range(FIRST_YEAR, DEFAULT_YEAR + 1))

# 保留聯賽（None = 全部）。含 MSI / RR(洲際賽) 等國際賽。
# ── 一級聯賽分級表（依 Leaguepedia 各年賽制）：聯賽 → (一級起年, 迄年) ──
# 次級/學院/CS 一律不收；改制合併後舊聯賽自動失效（如 TCL 2023 併入 EMEA 後不再是一級）
TIER1_YEARS = {
    "LCS": [(2013, 2024), (2026, 2099)],   # 2025 併入 LTA N，2026 LTA 解散後回歸
    "LEC": (2013, 2099), "LCK": (2013, 2099), "LPL": (2013, 2099),
    "LMS": (2015, 2019), "GPL": (2013, 2014),
    "PCS": (2020, 2024), "VCS": (2018, 2024), "LJL": (2014, 2024),
    "CBLOL": [(2014, 2024), (2026, 2099)], # 2025 併入 LTA S，2026 回歸
    "LLA": (2019, 2024), "LLN": (2017, 2018), "CLS": (2017, 2018),
    "TCL": (2015, 2022), "LCO": (2015, 2024), "LCL": (2016, 2022),  # LCO=OPL 改名(2021)，2025 併入 LCP
    "LCP": (2025, 2099), "LTA": (2025, 2025), "LTA N": (2025, 2025), "LTA S": (2025, 2025),
}
INTL_LEAGUES = {"WLDS", "MSI", "EWC", "FST", "ENC", "KESPA", "IEM"}  # 國際賽/盃賽不分級

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
OLD_SPLIT_MAP = {"Spring":"春季","Winter":"春季","Split 1":"春季",
                 "Summer":"夏季","Fall":"夏季","Split 2":"夏季","Split 3":"夏季",
                 "Summer Placements":"夏季","Finals":"夏季","Championship":"夏季",
                 "Lock-In":"春季","Kickoff":"春季"}
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
        RENAME = {"NA LCS": "LCS", "EU LCS": "LEC", "OGN": "LCK", "OPL": "LCO"}
        if lg in RENAME:
            lg = RENAME[lg]; r[iLeague] = lg
        if not league_ok(lg, year): continue  # 只收該年度的一級聯賽與國際賽
        if gi("firstPick") == width-1 and len(r) == width and r[iFP] == "":
            r[iFP] = "1" if (r[iSide] or "").lower()=="blue" else "0"
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
    for r in filtered:
        lg = (r[iLeague] or "").strip().upper()
        orig = (r[iSplit] or "").strip()
        try: is_po = int(r[iPlayoffs] or 0) == 1
        except ValueError: is_po = False
        if year >= 2025:
            norm = CBLOL_SPLIT_MAP.get(orig, SPLIT_MAP.get(orig, orig)) if lg=="CBLOL" else SPLIT_MAP.get(orig, orig)
            final = (norm + " PO") if (is_po and norm) else norm
            r[iSplit] = final.replace("Split ", "S")
        else:
            norm = OLD_SPLIT_MAP.get(orig, orig)
            r[iSplit] = (norm + " PO") if (is_po and norm) else norm

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
        bans = [b for b in (r[iBan1+k] if iBan1>=0 else "" for k in range(5)) if b]
        ban_acc.setdefault(mk, []).extend(bans)
        ban_side.setdefault(mk, {})[side] = bans
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
    data = {"fetched_at": NOW.strftime("%Y-%m-%d %H:%M"), "year": year,
            "sheet_title": f"Oracle's Elixir {year}", "tabs": {"RAW_DATA": table}}
    js = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    path = os.path.join(HERE, "data", f"data_{year}.js")
    with open(path, "w", encoding="utf-8") as f:
        f.write("window.LOL_DATA=" + js + ";")
    print(f"  → data_{year}.js（{len(table)-1} 列，{os.path.getsize(path)//1024} KB）")


def write_manifest():
    years = sorted(int(f[5:9]) for f in os.listdir(os.path.join(HERE, "data"))
                   if f.startswith("data_") and f.endswith(".js") and f[5:9].isdigit())
    m = {"years": years, "default": DEFAULT_YEAR if DEFAULT_YEAR in years else (years[-1] if years else DEFAULT_YEAR),
         "updated": NOW.strftime("%Y-%m-%d %H:%M")}
    with open(os.path.join(HERE, "data.js"), "w", encoding="utf-8") as f:
        f.write("window.LOL_MANIFEST=" + json.dumps(m) + ";")
    print(f"manifest：{years}")


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
        write_year(y, table)
    write_manifest()
    print("完成")


if __name__ == "__main__":
    main()
