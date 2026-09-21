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
import argparse, csv, io, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request

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

# ── gol.gg 暫時性失敗的處置（2026-09-14 精進迴圈 #108）──
# 09-14 10:00 那班 gol.gg 整站連不上（TCP 逾時 WinError 10060）：三次逾時各 ~21s ＋ 退避 5/10/15s
# ＝ 93s 全在 ① 階段的關鍵路徑上白等（第三次失敗後還多睡 15s 才放棄）；Leaguepedia 備援抓到 167 局、
# gol.gg 正本 fill JSON 也還在（build() 沒寫檔＝上次成功那份照併），卻仍 exit 1 ⇒ 每班留一份
# HEALTH_ALERT.txt（跟 #102 的 fetch_promo 同一種「狼來了」）。分兩種失敗：
#   暫時性（Transient）＝連線層（連不上／逾時）或伺服器 5xx；不可重試＝4xx／解析錯誤／其他例外。
#   暫時性 ＋ Leaguepedia 那份抓成 ＋ gol.gg 正本 GOLGG_STALE_HARD_DAYS 內更新過 ⇒ 印警告、exit 0；
#   正本不存在／沒有這賽段／老過硬上限／備援也失敗／沒有備援（--no-wiki）⇒ exit 1。
#   一天兩班 ⇒ 最多 6 班不吵，沈默有上限（不是把警報關掉）。
GOLGG_STALE_HARD_DAYS = 3   # gol.gg 正本（fill_{年}.json）超過這麼多天沒更新，暫時性失敗也要 exit 1
CONN_TRIES = 2              # 連線層失敗（主機沒回應／逾時）只試兩次——主機整個不回應時第三次幾乎不會忽然好
HTTP_TRIES = 3              # 伺服器有回但出錯（5xx）／其他例外照舊三次
RETRY_BACKOFF = 5.0         # 第 n 次失敗後睡 RETRY_BACKOFF×n 秒；最後一次失敗不睡（直接放棄）
_DOWN = False               # 這一班已判定 gol.gg 連不上 ⇒ 後續 get() 不再逐頁重試（省牆鐘）

# ── 賽段打完了就別每班重抓（2026-09-16 精進迴圈 #129）──
# LPL 2026 Split 3 的例行賽最後一局是 08-23（季後賽 OE 自己有），之後三週 fetch_fill 每班照樣
# 暖抓 wiki MH＋gol.gg matchlist＋Leaguepedia 抓頁 ≈ 16s（① 階段、關鍵路徑），產出逐位元不變。
# 閘門關不起來的原因：data_年.js 沒有來源欄，oe_games() 只能把「自己補過的 164 局」整批扣掉，
# 而 OE 收錄的正是同樣那 164 局 ⇒ n_oe 永遠只剩季後賽＋wiki 獨有的局（58 < 164）。
# **閘門刻意不修**：OE 其實收了 166/167 局，閘門一關 wiki 那份也跟著刪，會把 OE 沒有的
# 08-07 WE vs TT 第 3 局從主資料拿掉（列數縮水）。改成「補充資料裡最新一局早於 QUIET_DAYS 天
# ＝賽段沒有新比賽了」⇒ 每 RECHECK_H 小時才重抓一次，其餘班次沿用 fill／wikifill（fetch_data 照併）。
QUIET_DAYS = 10     # 補充資料（gol.gg 與 wiki 兩份都要有）最新一局早於這麼多天 ⇒ 安靜賽段
RECHECK_H = 42.0    # 安靜賽段多久真的重抓一次（兩班一天 ⇒ 每 4 班 1 次）。兩個上限夾著：
                    #   < check_keys.FILL_STALE_H 48h（跳過的班次金鑰檢查不會報「補資料太舊」）
                    #   < GOLGG_STALE_HARD_DAYS 3 天（重抓那班 gol.gg 暫時失敗時仍走 exit 0 那條，下一班再試）
_now = time.time    # 沙盒接管時鐘用


class Transient(RuntimeError):
    """gol.gg 暫時性失敗（連不上／逾時／5xx）——main() 據此決定要不要 exit 1"""


def _is_conn_err(e):
    """連線層失敗？HTTPError 是伺服器有回應、不算；其餘 OSError 家族（URLError／socket.timeout／
    ConnectionError／TimeoutError）都是「根本沒連上」。"""
    if isinstance(e, urllib.error.HTTPError):
        return False
    return isinstance(e, OSError)

# ── 要補的賽段（OE 收錄後自動停用，不必手動刪） ──
# wiki＝Leaguepedia 的賽事名（給 build_wiki 用）。**兩邊都抓再合併**（2026-08-02 使用者定案）：
# gol.gg 逐選手數據齊全但**局數會漏**，Leaguepedia 幾乎不漏比賽但沒有逐選手數據——
# 實測 LPL 2026 Split 3：gol.gg 33 局、Leaguepedia 56 局（差 23 局）。
FILL = [
    {"key": "LPL_2026_S3", "tournament": "LPL 2026 Split 3", "wiki": "LPL 2026 Split 3",
     "league": "LPL", "split": "Split 3", "year": 2026, "playoffs": 0},
    # ⚠ LCK 已停用（2026-08-07 使用者定案：「OE 的 LCK 數據回復了，接下來 LCK 以 OE 為主，
    #   但 LPL 一樣要去 WIKI+GOL 找」）。當時實測 LCK S3 有選手資料的 34 局裡，**30 局是真 OE**
    #   （7/29~8/5，有 @10／earnedgold 這些補檔填不了的欄位），只剩最新的 8/6 還沒上。
    #   而補檔繼續跑會製造幽靈局：wiki 版把 8/6 的 DK vs T1、DRX vs DNS 記成 **8/5 00:31/00:41**
    #   （合成時間），gol.gg 版是正確的 8/6 09:00 → 兩份日期不同，以日期為鍵的去重攔不到，
    #   主資料就同時出現 8/5 與 8/6 兩份同一場（使用者回報「T1 8/5 沒有跟 DK 打」）。
    #   OE 哪天又停更再把這筆打開即可（連同 csv_cache 的 LCK_2026_S3 一起清掉再重抓）。
    # {"key": "LCK_2026_S3", "tournament": "LCK 2026 Rounds 3-4", "wiki": "LCK 2026 Rounds 3-4",
    #  "league": "LCK", "split": "S3", "year": 2026, "playoffs": 0},
    # ── 亞運（國家隊，使用者 2026-09-21 交辦）──────────────────────────────
    # golgg:False＝**只有 Leaguepedia 有**：gol.gg 沒有國家隊友誼賽、OE 也不會收
    #   ⇒ 不打 gol.gg、也不過 OE 閘門（閘門會把自己補的局數當成「OE 已追上」而把補充刪掉，
    #      見 #129 的註解；wiki_only 的賽事沒有 gol.gg 那一份可以互相扣抵）。
    #   萬一 OE 哪天真的收了，fetch_data 的 merge_wiki 以「日期＋十個英雄」去重，不會變兩份。
    # not_before＝賽事開打前不必每班去問（省 ① 階段的關鍵路徑）。
    {"key": "AG2026_PRE", "wiki": "KOREA Pre Evaluation for 2026 Asian Games",
     "league": "亞運", "split": "熱身賽", "year": 2026, "playoffs": 0, "golgg": False},
    {"key": "AG2026", "wiki": "2026 Asian Games",
     "league": "亞運", "split": "", "year": 2026, "playoffs": 0, "golgg": False,
     "not_before": "2026-09-28"},   # 賽期 09-29 ~ 10-02（events_extra.js）
]
# ⚠ csv_cache/wikifill_2026.json 裡另有一筆**人工釘住**的 key「PBFIX_2026_LCK_S3」：
#   8/1 GEN vs DK 官方 0-2 共兩局，但 **OE 與 gol.gg 收到的是同一局**（十隻英雄完全一致、
#   只是一個標 g1 一個標 g2——就是本檔一直在講的「局號不可靠」），真正缺的那局只有
#   Leaguepedia 的 Picks and Bans 有 → 沿用 fill_missing_games.py 的 PBFIX 格式釘住那一列
#   （只有隊伍列＋BP，不造假選手資料）。
#   本腳本只會動自己 FILL 清單裡的 key，不會清掉它；OE 哪天補上那局，merge_wiki 的英雄組合
#   去重會自動讓這筆落空。（2026-08-07 使用者指示「8/1 的補就好，8/6 剛過等 OE 自己補」）

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


_last_req = 0.0   # 上一次真的打 gol.gg 的時刻（節流用）

# ── 階段計時（2026-09-10 線 3 精進迴圈 #104）──
# 為什麼要有：09-09 兩班逐班比對（shift_log_archive --diff）裡，**只有 fetch_fill 從 23.4s 變 51.0s
# （+118%）**，其餘每一步都變快；而日誌除了「暖抓 4.0s」沒有任何分項 ⇒ 無從判斷是 gol.gg 慢、
# Leaguepedia 慢、節流白睡、還是本機解析變重。#56 已經替 run_update 的「階段」加了牆鐘，
# 這一層是那之下的分項。（動手前先量掉的假設：#77 的暖抓讓 gate() 一班跑兩次 ⇒ 兩次讀 12.8MB 的
# data_2026.js；實測 gate 只要 0.11s，不是元兇，所以沒有為它加快取。）
# **只加計時與一行摘要，不改任何抓取行為**：請求數、順序、節流間隔全部照舊。
_PH = {}                                        # 階段名 → 累計秒數（dict 依插入順序）
_NETK = ("gol.gg 下載", "gol.gg 節流")            # 屬於「網路」的階段，扣殘差時要排除


def _ph(name, t0):
    """把 (現在 - t0) 累加到 name 這個階段；回傳這一段的秒數。"""
    d = time.time() - t0
    _PH[name] = _PH.get(name, 0.0) + d
    return d


def _ph_sum(keys=None):
    return sum(v for k, v in _PH.items() if keys is None or k in keys)


def _throttle():
    """GAP 是「兩次請求的最小間隔」，不是「每次請求後固定睡」：
    2026-09-08 線 3 量到每天那班 63.5s 裡有 20s 是四段尾端純睡眠——最後一次請求之後
    沒有下一次了還照睡（gol.gg 這邊整班只打一次 matchlist，就白睡 2s）。
    改成請求前看「距上次請求夠不夠 GAP」，中間解析的時間也算進間隔。"""
    w = GAP - (time.time() - _last_req)
    if w > 0:
        t0 = time.time()
        time.sleep(w)
        _ph("gol.gg 節流", t0)


def get(url, cache_name, force=False):
    global _last_req, _DOWN
    os.makedirs(HCACHE, exist_ok=True)
    p = os.path.join(HCACHE, cache_name)
    if os.path.exists(p) and not force:
        with open(p, encoding="utf-8") as f:
            return f.read()
    if _DOWN:
        raise Transient("gol.gg 這一班已判定連不上，不再重試：" + url)
    last, tries = None, HTTP_TRIES
    for a in range(HTTP_TRIES):
        _t = None
        try:
            _throttle()
            _t = time.time()
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as f:
                body = f.read().decode("utf-8", "replace")
            _ph("gol.gg 下載", _t)
            _last_req = time.time()
            with open(p, "w", encoding="utf-8") as f:
                f.write(body)
            return body
        except Exception as e:
            _last_req = time.time()      # 失敗也算打過一次
            if _t is not None:
                _ph("gol.gg 失敗等待", _t)   # 逾時／錯誤回應等掉的時間（#108 前全歸「其他」）
            last = e
            if _is_conn_err(e):
                tries = CONN_TRIES       # 連線層：縮成兩次
            if a + 1 >= tries:
                print(f"      {type(e).__name__}: {str(e)[:80]} → 第 {a+1} 次失敗，放棄", flush=True)
                break
            back = RETRY_BACKOFF * (a + 1)
            print(f"      {type(e).__name__}: {str(e)[:80]} → 第 {a+1} 次失敗，{back:.0f}s 後重試", flush=True)
            _t0 = time.time()
            time.sleep(back)
            _ph("gol.gg 重試退避", _t0)
    if _is_conn_err(last):
        _DOWN = True                     # 之後的頁面不必再各自等兩次逾時
        raise Transient(f"連不上 gol.gg（試了 {tries} 次）：{url}")
    if isinstance(last, urllib.error.HTTPError) and last.code >= 500:
        raise Transient(f"gol.gg 回 {last.code}：{url}")
    raise RuntimeError("下載失敗：" + url)


# ── 解析結果快取（2026-09-08 線 3）──
# 每天那班 fetch_fill 63.5s 裡 20.8s 是**冷開 329 個 gol.gg 快取 HTML**（每個 ~600KB、共 240MB，
# 冷開一次 15~58ms）再重新正則解析。已完成的局不會再變，解析結果也不會變 → 把每局
# parse_game／parse_fullstats 的結果存成一個 JSON，下一班只開這一個檔。
# 只存「通過完整性檢查」的局；不完整的（無隊伍區塊／逐選手不足 10 人）照舊每次走 HTML 路徑。
# --force 時不讀（全部重抓重解析）但會把新結果寫回，所以 --force 也會刷新這份快取。
PARSED_NAME = "_parsed.json"


def _parsed_path():
    return os.path.join(HCACHE, PARSED_NAME)     # 動態取 HCACHE：測試沙盒改了 HCACHE 也要跟著搬


def load_parsed():
    p = _parsed_path()
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        return d.get("games") or {} if isinstance(d, dict) else {}
    except Exception as e:
        print(f"      ⚠ 解析快取讀取失敗（重建）：{type(e).__name__}: {str(e)[:60]}", flush=True)
        return {}


def save_parsed(games):
    os.makedirs(HCACHE, exist_ok=True)
    tmp = _parsed_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"v": 1, "games": games}, f, ensure_ascii=False)
    os.replace(tmp, _parsed_path())


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
    _t_local, _net0 = time.time(), _ph_sum(_NETK)   # 本機那格＝整段 collect 扣掉網路（#104）
    tour = urllib.parse.quote(cfg["tournament"])
    # matchlist 一律重抓（賽段進行中每天有新比賽）；個別局頁面走快取（已完成的比賽資料不會再變）
    ml = get(f"https://gol.gg/tournament/tournament-matchlist/{tour}/",
             f"matchlist_{cfg['key']}.html", force=True)
    matches = [m for m in parse_matchlist(ml) if m["done"]]
    print(f"    matchlist：{len(matches)} 個已完成系列賽")

    PC = load_parsed()                                   # 整份（可能含別的賽段），寫回時一起保留
    hit = (lambda gid: None) if force else (lambda gid: PC.get(str(gid)))
    n_hit = n_parse = 0
    dirty = False

    def _gd(gid):
        e = hit(gid)
        if e is not None:
            return e["gd"]
        return parse_game(get(f"https://gol.gg/game/stats/{gid}/page-game/", f"g{gid}_game.html", force=force))

    def _fs(gid):
        e = hit(gid)
        if e is not None:
            return e["fs"]
        return parse_fullstats(get(f"https://gol.gg/game/stats/{gid}/page-fullstats/",
                                   f"g{gid}_full.html", force=force))

    day_seq, games, seen = {}, [], set()
    for mi, mt in enumerate(sorted(matches, key=lambda x: (x["date"], x["gid"]))):
        gd0 = _gd(mt["gid"])
        ids = sorted(i for i in gd0["ids"] if i >= mt["gid"]) or [mt["gid"]]
        k = day_seq.get(mt["date"], 0); day_seq[mt["date"]] = k + 1
        for gi, gid in enumerate(ids):
            if gid in seen:
                continue
            seen.add(gid)
            gd = gd0 if gid == mt["gid"] else _gd(gid)
            if not gd.get("sides"):
                print(f"      ⚠ {gid} 無隊伍區塊，跳過"); continue
            fs = _fs(gid)
            if len(fs.get("champs") or []) < 10 or len(fs["rows"].get("Player") or []) < 10:
                print(f"      ⚠ {gid} 逐選手資料不全，跳過"); continue
            if hit(gid) is not None:
                n_hit += 1
            else:
                n_parse += 1
                PC[str(gid)] = {"gd": gd, "fs": fs}; dirty = True
            hh = min(9 + k * 3 + gi, 23)   # 同日多系列/多局的假時鐘：只為了 date 排序穩定
            games.append({"gid": gid, "game": gi + 1, "date": gd["date"] or mt["date"],
                          "time": "%02d:%02d:00" % (hh, (gi * 7) % 60),
                          "patch": gd["patch"] or mt["patch"], "week": gd.get("week") or mt["week"],
                          "gamelength": gd["gamelength"], "sides": gd["sides"], "bp": gd["bp"], "fs": fs})
        print(f"      [{mi+1}/{len(matches)}] {mt['date']} match {mt['gid']} → {len(ids)} 局", flush=True)
    if dirty:
        save_parsed(PC)
    # 這一段的牆鐘扣掉期間的下載與節流 ⇒ 剩下的就是「開快取檔＋正則解析」（#104）
    _local = (time.time() - _t_local) - (_ph_sum(_NETK) - _net0)
    _PH["gol.gg 快取／解析"] = _PH.get("gol.gg 快取／解析", 0.0) + _local
    print(f"    解析快取：命中 {n_hit} 局／新解析 {n_parse} 局（{PARSED_NAME}）", flush=True)
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
def _gate(cfg):
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


def gate(cfg):
    """_gate 的計時外殼（#104）。一班會被呼叫兩次（warm_wiki 一次、build 一次），
    分項要看得到那是 0.1s 級的小錢，不是元兇。"""
    t0 = time.time()
    try:
        return _gate(cfg)
    finally:
        _ph("閘門（讀 data_年.js）", t0)


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
    _t = time.time()
    hdr, rows = to_csv_rows(games, cfg)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(hdr); w.writerows(rows)

    sys.path.insert(0, HERE)
    import fetch_data
    table = fetch_data.process(buf.getvalue(), cfg["year"])   # 衍生欄位(po/Lane/banlist/decider_winner)全部沿用 OE 那套
    _ph("組 CSV＋process", _t)
    if dump:
        print(f"    process() → {len(table)-1} 列，{len(table[0])} 欄")
        h = table[0]
        for r in table[1:7]:
            print("      ", r[h.index("date")], r[h.index("split")], "pid" + str(r[h.index("participantid")]),
                  r[h.index("blue_teamname")], r[h.index("blue_playername")], r[h.index("blue_champion")],
                  "vs", r[h.index("red_playername")], r[h.index("red_champion")])
        return table

    _t = time.time()
    _h = table[0]
    _gk = sorted({gkey_of(_h, r) for r in table[1:]})
    prev[cfg["key"]] = {"header": table[0], "rows": table[1:], "games": [g["gid"] for g in games],
                        "gkeys": _gk,
                        "src": "gol.gg", "tournament": cfg["tournament"],
                        "league": cfg["league"], "split": sn, "year": cfg["year"]}
    with open(fill_path, "w", encoding="utf-8") as f:
        json.dump(prev, f, ensure_ascii=False)
    _ph("寫 fill JSON", _t)
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
    # 只有 Leaguepedia 有的賽事：沒有 gol.gg 那一份可以從 OE 局數扣抵 ⇒ 過閘門等於自己刪自己
    need = True if not cfg.get("golgg", True) else gate(cfg)[0]
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
    _t = time.time()
    try:
        return fetch_wiki_mh.build({"tour": cfg["wiki"], "league": cfg["league"],
                                    "split": cfg["split"], "year": cfg["year"],
                                    "playoffs": cfg.get("playoffs", 0), "key": cfg["key"],
                                    "pb_force": True},   # 賽段進行中：Picks and Bans 頁也要重抓
                                   force=True)
    except Exception as e:      # wiki 掛掉不能連帶讓 gol.gg 那份也沒寫成
        print(f"    ⚠ wiki 補充失敗（略過，gol.gg 版照用）：{type(e).__name__}: {e}")
        return None
    finally:
        _ph("Leaguepedia 抓頁", _t)


def warm_wiki(cfg):
    """開工就先把 Leaguepedia 的 MH 頁抓下來（2026-09-09 #77，純為了省牆鐘）。

    2026-09-09 量到這一步 23.4s 的組成：gol.gg matchlist 下載 ~7.7s、Leaguepedia 13.0s
    （**其中 10.0s 是純 time.sleep**：opener 取 cookie 後固定睡 2s ＋ MH→PB 之間 GAP=8s 的節流）、
    本機解析／讀檔 2.7s。兩個來源是不同主機、節流各自獨立，**卻是一前一後跑的**
    ⇒ gol.gg 那 8 秒完全沒被拿來抵 Leaguepedia 的節流等待。

    改成先打 MH 頁再去做 gol.gg：等 build_wiki 要抓 Picks and Bans 時，距 MH 那一發已經
    過了 8 秒以上，`_throttle()` 一秒都不用等。**請求數不變、間隔只會更長（更禮貌）**，
    純粹是把等待跟別的工作疊起來。抓失敗就當沒發生（build_wiki 自己會照舊重抓）。
    """
    if not gate(cfg)[0]:
        return          # OE 已追上 ⇒ build_wiki 只會去停用舊資料，不會抓頁面，別白打一發
    sys.path.insert(0, HERE)
    import fetch_wiki_mh
    print(f"  {cfg['key']}：暖抓 Leaguepedia MH 頁（讓 gol.gg 那段跟節流重疊）…", flush=True)
    t0 = time.time()
    try:
        n = len(fetch_wiki_mh.fetch(cfg["wiki"], force=True) or "")
    except Exception as e:
        print(f"    ⚠ 暖抓失敗（不影響，build_wiki 會照舊重抓）：{type(e).__name__}: {str(e)[:80]}")
        _ph("暖抓 wiki MH", t0)
        return
    _ph("暖抓 wiki MH", t0)
    print(f"    暖抓 {n} bytes（{time.time() - t0:.1f}s）"
          f"{'' if n else '——空的，build_wiki 會照舊重抓'}", flush=True)


def _phase_report(t_all):
    """把 _PH 印成一行分項（#104）。

    順序就是實際發生的順序（dict 依插入序）；**殘差一律歸「其他」**——分項加起來要對得上牆鐘，
    不然下次比對又要重新猜。Leaguepedia 那一側的純睡眠由 fetch_wiki_mh.SLEPT 提供
    （它散在 _throttle 與 opener 兩處，這裡只借來當註腳，不重複計進總和）。
    """
    if not _PH:
        return
    try:
        sys.path.insert(0, HERE)
        import fetch_wiki_mh
        slept = float(getattr(fetch_wiki_mh, "SLEPT", 0.0) or 0.0)
    except Exception:
        slept = 0.0
    parts = [f"{k} {v:.1f}s" for k, v in _PH.items() if v >= 0.05]
    other = t_all - _ph_sum()
    if other >= 0.05:
        parts.append(f"其他 {other:.1f}s")
    tail = f"；Leaguepedia 純睡眠 {slept:.1f}s（含在暖抓＋抓頁裡）" if slept >= 0.05 else ""
    print(f"   ⏱ 分項：" + "｜".join(parts) + f"　全程 {t_all:.1f}s" + tail, flush=True)


def _transient_verdict(cfg, wiki_ok):
    """gol.gg 暫時性失敗之後要不要 exit 1 → (rc, 說明)。（#108，照 fetch_promo #102 的規矩）

    wiki_ok：Leaguepedia 那份這一班抓成了嗎（None＝根本沒抓，--no-wiki／--dump）。
    正本＝csv_cache/fill_{年}.json（build() 每次成功都會重寫 ⇒ mtime 就是上次成功的時間）。
    """
    if not wiki_ok:
        return 1, ("   ✗ Leaguepedia 那份也沒抓成（或沒抓）⇒ 這一班兩個來源都沒更新 ⇒ exit 1。"
                   if wiki_ok is None else
                   "   ✗ Leaguepedia 備援也沒抓成 ⇒ 這一班兩個來源都沒更新 ⇒ exit 1。")
    fill_path = os.path.join(CACHE, f"fill_{cfg['year']}.json")
    if not os.path.exists(fill_path):
        return 1, f"   ✗ gol.gg 正本 fill_{cfg['year']}.json 不存在 ⇒ exit 1。"
    try:
        with open(fill_path, encoding="utf-8") as f:
            has = cfg["key"] in json.load(f)
    except Exception as e:
        return 1, f"   ✗ gol.gg 正本讀不動（{type(e).__name__}）⇒ exit 1。"
    if not has:
        return 1, f"   ✗ gol.gg 正本裡沒有 {cfg['key']} 的資料（這賽段一局都還沒補到）⇒ exit 1。"
    age_d = (time.time() - os.path.getmtime(fill_path)) / 86400
    if age_d >= GOLGG_STALE_HARD_DAYS:
        return 1, (f"   ✗ gol.gg 正本已經 {age_d:.1f} 天沒更新，超過硬上限 {GOLGG_STALE_HARD_DAYS} 天"
                   f" ⇒ exit 1（該有人看一眼 gol.gg 是不是換了網址／擋了我們）。")
    return 0, (f"   gol.gg 正本還在（{age_d:.1f} 天，硬上限 {GOLGG_STALE_HARD_DAYS} 天）、Leaguepedia 已補"
               f" ⇒ 這次以 exit 0 收，下一班再試。")


def _newest_date(block):
    """fill／wikifill JSON 某個 key 的 {"header","rows"} → 最新一局的 YYYY-MM-DD（沒有就回 ""）。"""
    try:
        i = block["header"].index("date")
    except (KeyError, ValueError, TypeError, AttributeError):
        return ""
    return max((str(r[i])[:10] for r in (block.get("rows") or []) if len(r) > i and r[i]), default="")


def quiet_skip(cfg, wiki):
    """安靜賽段這班要不要跳過重抓 → (跳過嗎, 要印的一行或 None)。（#129）

    兩份補充資料（wiki=False 時只看 gol.gg 那份）**都要**有這個 key、有列、有日期，才可能跳過；
    缺任何一份＝還沒補齊／OE 追上已刪除 ⇒ 照舊抓（閘門該做的事照做）。
    「上次重抓」取兩份檔 mtime 的較舊者：build()／fetch_wiki_mh.build() 成功才會重寫，
    所以哪一邊上次沒抓成，下一班就會到期重試。"""
    paths = [] if not cfg.get("golgg", True) else [os.path.join(CACHE, f"fill_{cfg['year']}.json")]
    if wiki:
        paths.append(os.path.join(CACHE, f"wikifill_{cfg['year']}.json"))
    newest, last = "", None
    for p in paths:
        try:
            with open(p, encoding="utf-8") as f:
                blk = json.load(f).get(cfg["key"])
            mt = os.path.getmtime(p)
        except (OSError, ValueError, AttributeError):
            return False, None
        nd = _newest_date(blk) if isinstance(blk, dict) else ""
        if not nd:
            return False, None
        newest = max(newest, nd)
        last = mt if last is None else min(last, mt)
    try:
        quiet_d = (_now() - time.mktime(time.strptime(newest, "%Y-%m-%d"))) / 86400
    except ValueError:
        return False, None
    if quiet_d < QUIET_DAYS:
        return False, None
    age_h = (_now() - last) / 3600
    if age_h >= RECHECK_H:
        return False, (f"  {cfg['key']}：補充資料最新一局 {newest}（{quiet_d:.0f} 天前，賽段沒有新比賽）、"
                       f"上次重抓 {age_h:.0f} 小時前 ≥ {RECHECK_H:.0f} ⇒ 這班重抓一次")
    return True, (f"  {cfg['key']}：補充資料最新一局 {newest}（{quiet_d:.0f} 天前，≥{QUIET_DAYS} 天沒有新比賽）、"
                  f"上次重抓 {age_h:.0f} 小時前 ⇒ 沿用 fill／wikifill、這班不重抓"
                  f"（每 {RECHECK_H:.0f} 小時重抓一次；--force 或 --no-quiet-skip 強制）")


def main():
    _t_all = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="重抓 HTML（賽段進行中要拿新比賽用這個）")
    ap.add_argument("--dump", action="store_true", help="只解析不寫檔")
    ap.add_argument("--status", action="store_true", help="只看 OE / 補充 各幾局")
    ap.add_argument("--no-wiki", action="store_true", help="只抓 gol.gg，不抓 Leaguepedia")
    ap.add_argument("--no-quiet-skip", action="store_true", help="安靜賽段也照抓（#129 之前的行為）")
    A = ap.parse_args()
    failed, quiet = [], []
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
            if not cfg.get("golgg", True):
                print(f"  {cfg['key']:14s} （只有 Leaguepedia）           wiki={wn:3d} 局")
            else:
                print(f"  {cfg['key']:14s} OE={oe_games(cfg['year'], cfg['league'], sn, exclude=mine):3d} 局"
                      f"   gol.gg={n:3d} 局   wiki={wn:3d} 局")
            continue
        wiki = not (A.dump or A.no_wiki) and bool(cfg.get("wiki"))
        nb = cfg.get("not_before")
        if nb and time.strftime("%Y-%m-%d", time.localtime(_now())) < nb and not A.force:
            print(f"  {cfg['key']}：{nb} 才開打 ⇒ 這班不抓（--force 可強制）", flush=True)
            continue
        if not (A.force or A.dump or A.no_quiet_skip):
            _t = time.time()
            skip, why = quiet_skip(cfg, wiki)
            _ph("安靜賽段判定", _t)
            if why:
                print(why, flush=True)
            if skip:
                continue
        if wiki and cfg.get("golgg", True):
            warm_wiki(cfg)   # wiki_only 沒有 gol.gg 可以重疊，暖抓只會多打一發
        transient = None
        try:
            if not cfg.get("golgg", True):
                print(f"  {cfg['key']}：只有 Leaguepedia 有這個賽事 ⇒ 不打 gol.gg", flush=True)
            else:
                build(cfg, force=A.force, dump=A.dump)
        except Transient as e:
            # 暫時性（連不上／逾時／5xx，#108）：build() 沒寫檔 ⇒ 上次成功的 fill JSON 還在、fetch_data 照併。
            # 要不要 exit 1 等 Leaguepedia 那份抓完、看正本年齡再決定（_transient_verdict）。
            print(f"  ⚠ gol.gg 暫時連不上（略過，續抓 Leaguepedia；上次成功的 fill JSON 照用）：{str(e)[:120]}")
            transient = e
        except Exception as e:
            # gol.gg 掛掉不能連帶讓 wiki 那份也沒抓成（build_wiki 早就有對稱的 try——
            # 2026-09-09 #77 補上這一半：當天 14:5x gol.gg 整個連不上［WinError 10060］，
            # 舊版是 build() 直接往上炸 ⇒ main() 中斷 ⇒ Leaguepedia 那份**整班沒更新**，
            # 而它是唯一不漏局的來源）。仍然記下來、最後 exit 1，警示訊號不吞掉。
            print(f"  ⚠ gol.gg 補充失敗（略過，續抓 Leaguepedia）：{type(e).__name__}: {str(e)[:120]}")
            failed.append(f"{cfg['key']} gol.gg：{type(e).__name__}")
        wtab = None
        if wiki:
            wtab = build_wiki(cfg)
        if transient is not None:
            rc1, why = _transient_verdict(cfg, (wtab is not None) if wiki else None)
            print(why)
            if rc1:
                failed.append(f"{cfg['key']} gol.gg：暫時性失敗但{('備援也沒抓成' if wiki else '沒有備援') if not wtab else '正本太舊／缺席'}")
            else:
                quiet.append(cfg["key"])
    if failed:
        print("⚠ 有來源失敗：" + "、".join(failed))
    elif quiet:
        print("⚠ gol.gg 暫時失敗、備援已補、正本還新 ⇒ 不算失敗（exit 0，下一班再試）：" + "、".join(quiet))
    if not A.status:
        _phase_report(time.time() - _t_all)
        print("完成。（fetch_data.py 寫檔時會併入：OE > gol.gg > wiki，同一局以先者為準）")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
