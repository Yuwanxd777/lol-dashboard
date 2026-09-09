# -*- coding: utf-8 -*-
"""OBGG 職業帳號每日更新 → 合併進 soloq_accounts.json（併入 update.bat）。
來源＝OBGG 微信小程序公開 API www.obgg.net/obggmini（免登入，帶 User-Agent 即可）。
  zone?name=LPL → 該賽區戰隊；team?name=IG → 該隊選手(game_id)；
  progamer?team=IG&game_id=TheShy → 該選手 accountList（summonerName=完整RiotID、regionName、lastGameTime…）
路由（使用者定案）：LPL/LCK 以 OBGG 為主（近兩月有打的加入、沒打的刪）、LCS/LEC/CBLOL 以 dpm 為主（保留現有）、其餘 union。
過濾鐵則：峡谷之巅（韓服菁英練習服，Riot API/dpm 抓不到）、近 60 天沒打、純數字死號。
dpmPuuid：本腳本只維護帳號清單；新帳號的 dpmPuuid 由 resolve_obgg_dpmpuuid.py 之後補（才能進逐場）。
安全門：OBGG 抓取失敗或 LPL/LCK 帳號數異常過少 → 不動 soloq_accounts.json（避免 OBGG 掛掉時誤刪整批）。
用法：python scripts\\fetch_obgg_accounts.py
      --jobs=N／--team-jobs=N 併發；--no-keepalive 回到「每請求重新握手」的舊行為（對照組）；
      --out=PATH 把結果寫到別的檔（驗證用，不動 soloq_accounts.json 正本、也不寫 .bak）。
"""
import io, sys, json, os, re, time, datetime, threading, http.client, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ACCOUNTS = os.path.join(HERE, "soloq_accounts.json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
BASE = "https://www.obgg.net/obggmini/"
ZONES = ["LPL", "LCK", "LCS", "LEC", "LCP", "VCS", "LJL", "LTA S", "CBLOL"]
OBGG_ZONES = {"LPL", "LCK"}          # 以 OBGG 為主（重建）
DPM_ZONES = {"LCS", "LEC", "CBLOL"}  # 以 dpm 為主（保留現有，不加 OBGG）
PLAT = {"韩服": "kr", "美服": "na1", "欧服": "euw1", "巴西": "br1"}
ALIAS = {"GEN": "GENG"}              # OBGG 隊碼 → 清單隊碼
CUT_MS = 60 * 24 * 3600 * 1000       # 近兩個月
ROSTER_PLAYERS = set()               # OBGG 標為五路的現役選手（診斷用；不再當作帳號保留的豁免依據）
ROSTER_OUT = os.path.join(ROOT, "csv_cache", "obgg_roster.json")   # csv_cache 在專案根目錄，不是 scripts/ 下
# 2026-09-06 線 3（迴圈 #21）：LPL/LCK「不在 OBGG 清單就刪」每輪刪 219～232 隻、之後 ⑤ fetch_dpm_soloq_accounts 再原封補回
# （11:30／22:00 日誌：1091 → 912 → 1090）。最終輸出沒差，但 dpm 那一輪「過不了 Cloudflare，中止」時就會停在 912 去掃牌位
# ⇒ 56 位 OBGG 沒收錄的選手（KT Pollu／DNS Quantum／GEN Loid／LNG Croco…）整個人從積分頁消失。
# 改法：dpm 選手檔近 KEEP_DPM_DAYS 天確認過的（dpmSeen）暫留，其餘照舊刪；OBGG 有列的照舊重建。純幂等性修正，最終輸出不變。
KEEP_DPM_DAYS = 3
# 2026-09-08 線 3（迴圈 #67）：⑤ fetch_dpm_soloq_accounts 的歸屬複查把「dpm 掛牌是別人的」帳號剔除、記進
# csv_cache/soloq_disowned.json；但 OBGG 仍把那隻掛在原選手名下 ⇒ 這裡隔天原封補回（沒有 dpmPuuid）→ ⑤b 反查到 puuid
# → ⑤d 當「新選手」用它補全年 ⇒ 抓回幾百場別人的比賽 → 22:00 ⑤ 再剔除、⑤e2 再刪 → 每天循環
# （09-07 22:05 剔除 TES|Tian plokijuhyg／WE|Erha 25hdp／OMG|haichao luck dog，09-08 10:00 補回並重抓 798 場）。
# 改法：補帳號前查名單——同一位選手（隊|名）名下被記過的 riotId 不再從 OBGG 補回；只認 from == 隊|名（同名選手不牽連）。
# dpm 若哪天又把帳號還給原主，⑤ 的 union 會用 dpm 選手檔補回（dpmSeen 今天）、prune_old 也會留住；名單不會永久封殺。
DISOWNED = os.path.join(ROOT, "csv_cache", "soloq_disowned.json")


def load_disowned(path=None):
    """讀歸屬剔除名單 → normalize 過的 rid 索引；讀不到／壞掉回空 dict（輔助證據，壞了只是退回舊行為）。"""
    try:
        if HERE not in sys.path:
            sys.path.insert(0, HERE)
        import soloq_disowned
        return soloq_disowned.index(soloq_disowned.load(path or DISOWNED))
    except Exception as e:
        print(f"（歸屬剔除名單讀不到，OBGG 帳號不過濾：{e}）", flush=True)
        return {}


def disowned_of(idx, team, player, rid):
    """OBGG 還把 rid 掛在 team|player 名下、但歸屬複查已認定是別人的 → 回那筆紀錄（要略過）；否則 None。"""
    if not idx:
        return None
    import soloq_disowned
    return soloq_disowned.disowned_from(idx, rid, f"{team}|{player}")


def dpm_recent(a, today=None, days=KEEP_DPM_DAYS):
    """dpm 選手檔近 days 天內確認過這隻帳號（dpmSeen，含第 days 天）→ True；缺／壞日期／未來日期 → False（照舊刪）。"""
    s = a.get("dpmSeen")
    if not s:
        return False
    try:
        d = datetime.date.fromisoformat(str(s)[:10])
    except ValueError:
        return False
    t = today or datetime.date.today()
    return 0 <= (t - d).days <= days


def prune_old(acc, new, new_rids, zone_of, today=None, days=KEEP_DPM_DAYS):
    """OBGG 重建後決定舊帳號 acc 哪些併回 new（就地追加）→ (removed, kept_dpm)。
    OBGG 主導賽區（LPL/LCK）：在 OBGG 清單的上面已重建、不重複；不在清單的只有 dpm 近 days 天確認過才暫留，否則刪。
    其餘賽區：在清單的已由 union 納入；不在的（dpm 主導／無法分類）一律保留。"""
    removed = kept_dpm = 0
    for a in acc:
        z = zone_of(a.get("team"))
        if z in OBGG_ZONES:
            if norm(a["riotId"]) in new_rids:
                continue
            if dpm_recent(a, today, days):
                new.append(a); kept_dpm += 1
            else:
                removed += 1
            continue
        if norm(a["riotId"]) in new_rids:
            continue
        new.append(a)
    return removed, kept_dpm


# ── keep-alive（2026-09-07 線 3 迴圈 #38）─────────────────────────────────────
# 這一步 159.4s 的大頭不是 obgg 慢，是**每一個請求都重新握手**：urllib 不重用連線，
# 而 www.obgg.net 在台灣連過去 TCP+TLS 握手就 1.85 秒。實測（autopilot/_r38_probe2.py，
# 同樣 9 個 zone 請求）：每次新連線 23.8s（2.4s/請求）vs 重用同一條連線 6.5s（0.53s/請求）＝ 4.5 倍。
# 做法：每條執行緒握自己的 http.client.HTTPSConnection（thread-local），跨隊、跨賽區重用。
# 伺服器端的併發連線數沒有變多（一樣是 執行緒數 條），只是不再握手風暴 ⇒ 對 obgg 更輕，不是更重。
# keep-alive 連線會被伺服器關掉（idle 逾時），所以第一次失敗一律「丟掉連線、立刻重連再試一次」
# （不睡 1.5 秒——那是給真的伺服器錯誤用的），之後才照舊退避。--no-keepalive 回到舊行為當對照組。
KEEPALIVE = True

# ── 分項計時（2026-09-10 線 3 迴圈 #107）──────────────────────────────────────
# 這一步 44.1s，但日誌只有逐賽區小計（LCK 20.1s／LPL 10.9s／其餘七區合計 13.1s），
# 拆不出「等 obgg 回應」「TCP/TLS 握手」「重試退避」「每請求後的禮貌睡 0.15」各佔多少
# ⇒ 不知道該再併發、該少睡、還是該把賽區之間的序列化拆掉。這裡逐請求記，收尾印一行。
# 全部只是計數，不改任何請求的數量、順序與間隔。
STAT_LOCK = threading.Lock()
REQ_N = {"zone": 0, "team": 0, "progamer": 0, "other": 0}      # 送出去的請求數（含重試那幾次）
REQ_S = {"zone": 0.0, "team": 0.0, "progamer": 0.0, "other": 0.0}  # 等回應的秒數**相加**（跨執行緒，會大於牆鐘）
RETRY_N = [0]           # 重試次數（第一次失敗之後的每一次嘗試）
RETRY_SLEEP = [0.0]     # 重試退避睡掉的秒數
POLITE_SLEEP = [0.0]    # 禮貌睡（每個 team／progamer 請求後的 0.15）
HS_S = [0.0]            # TCP/TLS 握手秒數相加
ZONE_TEAM_MAX = {}      # zone → (最慢一隊的秒數, 隊名)：判斷「這一區慢」是全區慢還是被一隊拖住
_TL = threading.local()
_CONNS = []                       # 收工時一起關（只是禮貌，執行緒死掉時 GC 也會關）
_CONN_LOCK = threading.Lock()
CONN_NEW = [0]                    # 握手次數（診斷用：理想是「執行緒數」而不是「請求數」）


def _conn(host):
    c = getattr(_TL, "conn", None)
    if c is None:
        c = http.client.HTTPSConnection(host, timeout=25)
        # #107：明著 connect() 只為了把握手秒數量出來（http.client 本來也會在第一個 request 時
        # 自己 connect，時間原本混在那個請求裡）。連不上就丟掉、讓 get() 照舊重試。
        t0 = time.time()
        try:
            c.connect()
        except Exception:
            try:
                c.close()
            except Exception:
                pass
            with STAT_LOCK:
                HS_S[0] += time.time() - t0
            raise
        with _CONN_LOCK:
            _CONNS.append(c); CONN_NEW[0] += 1
        with STAT_LOCK:
            HS_S[0] += time.time() - t0
        _TL.conn = c
    return c


def _drop_conn():
    c = getattr(_TL, "conn", None)
    _TL.conn = None
    _TL.used = False
    if c is not None:
        try:
            c.close()
        except Exception:
            pass


def close_conns():
    with _CONN_LOCK:
        for c in _CONNS:
            try:
                c.close()
            except Exception:
                pass
        _CONNS.clear()


def _fetch_once(url):
    """回傳解析好的 JSON；非 200 或連線壞掉就丟例外（由 get() 的重試處理）。"""
    h = {"User-Agent": UA}  # OBGG API 為公開端點，只需 UA（不帶小程序 appid Referer，避免被誤判為密鑰）
    u = urllib.parse.urlsplit(url)
    if not KEEPALIVE or u.scheme != "https" or not u.netloc:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=25)
        return json.loads(r.read().decode("utf-8-sig", "replace"))
    c = _conn(u.netloc)
    h["Connection"] = "keep-alive"
    c.request("GET", u.path + (("?" + u.query) if u.query else ""), headers=h)
    r = c.getresponse()
    body = r.read()                       # 一定要讀完，不然這條連線不能重用
    if r.status != 200:
        _drop_conn()
        raise OSError(f"HTTP {r.status}")
    _TL.used = True                       # 這條連線收過一次完整回應 ⇒ 之後它壞掉多半是 idle 被關
    return json.loads(body.decode("utf-8-sig", "replace"))


def polite(sec=0.15):
    """每個 team／progamer 請求後的禮貌間隔（抽出來只為了記時數，秒數與位置都沒變）。"""
    time.sleep(sec)
    with STAT_LOCK:
        POLITE_SLEEP[0] += sec


def get(url, retry=2, kind=None):
    k = kind or "other"
    for i in range(retry + 1):
        t0 = time.time()
        try:
            r = _fetch_once(url)
            with STAT_LOCK:
                REQ_N[k] = REQ_N.get(k, 0) + 1
                REQ_S[k] = REQ_S.get(k, 0.0) + (time.time() - t0)
                if i:
                    RETRY_N[0] += 1
            return r
        except Exception as e:
            with STAT_LOCK:
                REQ_N[k] = REQ_N.get(k, 0) + 1
                REQ_S[k] = REQ_S.get(k, 0.0) + (time.time() - t0)
                if i:
                    RETRY_N[0] += 1
            stale = getattr(_TL, "used", False)   # 用過的連線壞掉＝idle 逾時，立刻重連就好
            _drop_conn()
            if i == retry:
                if kind:                      # 只算重試用盡的最終失敗（中途重試成功的不算）
                    with ERR_LOCK:
                        ERRS[kind] = ERRS.get(kind, 0) + 1
                        ERR_URLS.append(url)
                return {"_err": str(e)[:100]}
            if not (i == 0 and stale):        # 第一次疑似 stale socket 就立刻重連，其餘照舊退避
                time.sleep(1.5)
                with STAT_LOCK:
                    RETRY_SLEEP[0] += 1.5


def num_name(rid):
    return bool(re.fullmatch(r"\d{6,}", str(rid).split("#")[0].strip()))


def norm(s):
    return re.sub(r"\s+", "", str(s or "")).lower()


# 段位分數（OBGG tier 形如「王者 - 1971」「宗师 - 1446」「钻1 - 75」「未定级」）：用來判斷哪個是主帳號
TIER = [("王者", 10), ("宗师", 9), ("大师", 8), ("钻", 7), ("翡", 6), ("铂", 5),
        ("黄金", 4), ("白银", 3), ("青铜", 2), ("黑铁", 1)]


def tier_score(t):
    t = str(t or "")
    for k, v in TIER:
        if t.startswith(k):
            return v
    return 0


JOBS = 3   # 同一隊的選手並行抓 progamer 的執行緒數（--jobs 可改；1＝舊行為）
# 2026-09-07 線 3（迴圈 #24）：22:00 這一步 199s＝57 隊逐隊 team 請求＋每隊等最慢的 progamer（obgg.net 每請求 0.4～0.6s）。
# 同一賽區的戰隊也並行（TEAM_JOBS 條，最多 TEAM_JOBS×JOBS 條連線；#24 當時是 2×3＝6，#87 起是 4×3＝12）估 −90s。_team_pull() 只回傳，out[z] 只在 pull() 主執行緒寫；
# ex.map 保持 teams 順序 ⇒ 帳號檔排序跟逐隊時一模一樣。--team-jobs=1 就是舊行為。03:00 真網路只讀煙霧：108.6s、各區帳號數同 22:00、失敗 0。
TEAM_JOBS = 4
# 2026-09-09 線 3（迴圈 #87）：TEAM_JOBS 2 → 4。這一步是 ③ 階段的長桿（10:00 那班 55.8s），
#   時間幾乎全在等 obgg 回應（CPU 是空的）；賽區之間仍循序，所以每一區的隊只有 2 條工人在跑。
#   同一台、同一時段的真站唯讀探針（走 --out= 旁路，不動 soloq_accounts.json 正本）：
#     --team-jobs=2（原設定）48.4s（LPL 12.0／LCK 22.6）  vs  --team-jobs=4 16.4s（LPL 6.1／LCK 3.5）
#   兩趟寫出的帳號檔**逐字相同**（1128 筆、排序一致，diff 空），OBGG 請求最終失敗兩趟都 0，
#   TCP/TLS 握手 25 → 18 次（連線重用沒變差、不是握手風暴）。併發上限＝4 條隊 ＋ 4×JOBS(3)＝12 條選手。
#   要退回舊行為：--team-jobs=2（管線那行在 run_update.py 的 ③，或直接改回這一行）。
# get() 重試用盡的最終失敗以前完全沒印——失敗的隊／人就靜靜消失，LPL/LCK 的舊帳號隨之被當「近兩月未列」刪掉。
# 現在逐類計數＋留 URL 印進摘要；OBGG 主導賽區失敗 ≥ ERR_ABORT 次就不動帳號檔（docstring 第 9 行的安全門本來就這麼寫）。
ERRS = {"zone": 0, "team": 0, "progamer": 0}
ERR_URLS = []
ERR_LOCK = threading.Lock()
ERR_ABORT = 3


def _player_accounts(tm, gid, now):
    """一位選手的可用帳號清單（原本寫在 pull() 迴圈裡，抽出來才能並行）。"""
    pg = get(BASE + f"progamer?team={urllib.parse.quote(tm)}&game_id={urllib.parse.quote(gid)}", kind="progamer")
    polite()
    d = pg.get("data") if isinstance(pg, dict) else None
    accs = (d or {}).get("accountList", []) if isinstance(d, dict) else []
    # 先濾掉一定不能用的：峡谷之巅(Riot API/dpm 都查不到)、純數字死號、今年完全沒打
    cand = []
    for a in accs:
        if a.get("regionName") == "峡谷之巅" or str(a.get("region", "")).upper() == "BGP2":
            continue
        if num_name(a.get("summonerName")):
            continue
        if tier_score(a.get("tier")) <= 0 and int(a.get("yearPlay") or 0) <= 0:
            continue
        cand.append(a)
    # 主帳號＝段位最高、同段位比今年場次；**主帳號不套 60 天規則**
    # （2026-07-29 修：Tian 5/28、369 4/17 最後一場就被整個砍掉，但他們今年打了 278/133 場，
    #   儀表板要的是「今年」的積分資料。60 天規則的原意是清掉棄用小號，不該連主帳號一起清。）
    cand.sort(key=lambda a: (tier_score(a.get("tier")), int(a.get("yearPlay") or 0)), reverse=True)
    good = []
    for i, a in enumerate(cand):
        if i > 0:                       # 小號：維持近 60 天有打才留
            try:
                if (now - float(a.get("lastGameTime"))) > CUT_MS:
                    continue
            except Exception:
                continue
        good.append({"platform": PLAT.get(a.get("regionName"), a.get("region")),
                     "riotId": a.get("summonerName")})
    return gid, good


def _note_team(z, tm, t0):
    """記下這一區最慢的一隊（#107 分項）：賽區小計高，是全區都慢還是被一隊拖住，看這個就知道。"""
    d = time.time() - t0
    with STAT_LOCK:
        if d > ZONE_TEAM_MAX.get(z, (0.0, ""))[0]:
            ZONE_TEAM_MAX[z] = (d, tm)


def _team_pull(z, t, now):
    """一隊：team 請求（登記名冊）＋（非 dpm 主導賽區）逐人 progamer 並行。回 (tm, roster_ok, {gid: good})。
    **不碰 out**——寫入留給 pull() 的主執行緒，所以多隊可以並行（2026-09-07 迴圈 #24 從 pull() 的迴圈抽出來）。"""
    tm = t["team_name"]
    tt0 = time.time()
    rd = get(BASE + "team?name=" + urllib.parse.quote(tm), kind="team"); polite()
    roster = rd.get("data") if isinstance(rd, dict) else None
    if not roster:
        _note_team(z, tm, tt0)
        return tm, False, {}
    # 現役選手名冊（pos 標成五路之一才算；主播/顧問/監督/教練不算）。pos 來自 team 端點，
    # **不需要 progamer**——所以 dpm 主導賽區也照樣登記得到。set.add 在 GIL 下是原子的，多隊並行安全。
    # 註：曾用來豁免 dpm 的「今年沒出賽」過濾，2026-07-29 已收回——OBGG 名單會留著已離開職業的人
    # （TW BeanJ/Glory 今年 0 場仍掛在隊上）。現在只留作診斷用途（check_obgg_gaps.py 等）。
    for p in roster:
        if re.search(r"-\s*(上|野|中|下|辅)(\s|-|$)", str(p.get("pos") or "")):
            ROSTER_PLAYERS.add(p["game_id"])
    # 2026-09-06（線 3 提速，昨晚這一步 427 秒＝第③階段的 94%）：
    # ① dpm 主導賽區（LCS/LEC/CBLOL）的 OBGG 帳號本來就不採用（main() 的 obgg_entries 排除
    #   DPM_ZONES），逐人 progamer 請求純屬浪費 → 整隊跳過。zone_of() 只靠 out[z] 有沒有這隊，
    #   所以 pull() 會放一個空 dict 讓 team_zone 仍然對得到（保留「dpm 主導 → 保留舊帳號」那條路）。
    # ② 其餘賽區：同一隊的選手並行抓（JOBS 條執行緒，每條仍睡 0.15 秒）。
    if z in DPM_ZONES:
        _note_team(z, tm, tt0)
        return tm, True, {}
    gids = [p["game_id"] for p in roster]
    # 2026-09-07（迴圈 #38）：以前這裡每一隊 `with ThreadPoolExecutor(...)` 開新執行緒，
    # 執行緒一死 keep-alive 連線就跟著沒了 ⇒ 每隊都要重新握手。改用 pull() 建好的共用池
    # （PLAYER_EX，長壽執行緒），map 仍照 gids 順序回傳 ⇒ 輸出與排序不變。
    if PLAYER_EX is not None and len(gids) > 1:
        results = list(PLAYER_EX.map(lambda g: _player_accounts(tm, g, now), gids))
    else:
        results = [_player_accounts(tm, g, now) for g in gids]
    _note_team(z, tm, tt0)
    return tm, True, {gid: good for gid, good in results if good}


PLAYER_EX = None   # pull() 建的共用選手池（長壽執行緒 ⇒ keep-alive 連線跨隊重用）


def pull():
    """→ (out, zone_err)：out[zone][team][gid] = 帳號清單；zone_err[zone] = 抓這一區時 get() 最終失敗的次數。"""
    global PLAYER_EX
    now = time.time() * 1000
    out = {}
    zone_err = {}
    # 兩個池整趟只建一次（以前是每賽區／每隊各建一個，執行緒短命 ⇒ 連線重用不到）。
    # 併發連線上限跟以前一樣是 TEAM_JOBS 條隊 ＋ TEAM_JOBS×JOBS 條選手。
    team_ex = ThreadPoolExecutor(max_workers=TEAM_JOBS, thread_name_prefix="team") if TEAM_JOBS > 1 else None
    PLAYER_EX = ThreadPoolExecutor(max_workers=max(JOBS, TEAM_JOBS * JOBS),
                                   thread_name_prefix="pg") if JOBS > 1 else None
    try:
        return _pull_zones(out, zone_err, now, team_ex)
    finally:
        for ex in (team_ex, PLAYER_EX):
            if ex is not None:
                ex.shutdown(wait=True)
        PLAYER_EX = None
        close_conns()


def _pull_zones(out, zone_err, now, team_ex):
    for z in ZONES:
        t0 = time.time(); e0 = sum(ERRS.values())
        zd = get(BASE + "zone?name=" + urllib.parse.quote(z) + "&isClick=0", kind="zone")
        teams = zd.get("data") if isinstance(zd, dict) else None
        if not teams:
            zone_err[z] = sum(ERRS.values()) - e0
            print(f"  {z}: 無資料（跳過）"); continue
        out[z] = {}
        # 2026-09-07（迴圈 #24）：同一賽區的戰隊並行（TEAM_JOBS 條）。ex.map 保持 teams 的順序 ⇒ out[z] 的插入順序、
        # 最終帳號檔的排序都跟逐隊時一模一樣（--team-jobs=1 可對照）。
        if team_ex is not None and len(teams) > 1:
            results = list(team_ex.map(lambda t: _team_pull(z, t, now), teams))
        else:
            results = [_team_pull(z, t, now) for t in teams]
        for tm, ok, ps in results:          # out[z] 只在這裡（主執行緒）寫
            if not ok:
                continue
            if z in DPM_ZONES:
                out[z].setdefault(tm, {})
                continue
            for gid, good in ps.items():
                out[z].setdefault(tm, {})[gid] = good
        zone_err[z] = sum(ERRS.values()) - e0
        print(f"  {z}: {sum(len(v) for v in out[z].values())} 帳號（{len(teams)} 隊，{time.time() - t0:.1f}s"
              + (f"，請求失敗 {zone_err[z]}" if zone_err[z] else "") + "）", flush=True)
    return out, zone_err


def print_breakdown(wall):
    """#107 分項：牆鐘 44s 拆成「等回應／握手／重試退避／禮貌睡」，並點名各區最慢的一隊。
    前四項都是**跨執行緒相加**（併發跑的會重疊），所以相加會大於牆鐘——這正是要看的東西：
    相加遠大於牆鐘＝併發有在做事；相加接近牆鐘＝其實是序列的，還有併發空間。"""
    kinds = [k for k in ("zone", "team", "progamer", "other") if REQ_N.get(k)]
    resp = "／".join(f"{k} {REQ_S[k]:.1f}s({REQ_N[k]})" for k in kinds)
    tot = sum(REQ_S.values()) + HS_S[0] + RETRY_SLEEP[0] + POLITE_SLEEP[0]
    print(f"  分項（跨執行緒相加 {tot:.1f}s vs 牆鐘 {wall:.1f}s）：等回應 {resp}；"
          f"握手 {HS_S[0]:.1f}s({CONN_NEW[0]})；重試 {RETRY_N[0]} 次(退避 {RETRY_SLEEP[0]:.1f}s)；"
          f"禮貌睡 {POLITE_SLEEP[0]:.1f}s", flush=True)
    slow = [f"{z}|{ZONE_TEAM_MAX[z][1]} {ZONE_TEAM_MAX[z][0]:.1f}s" for z in ZONES if z in ZONE_TEAM_MAX]
    if slow:
        print("  各區最慢一隊：" + "／".join(slow), flush=True)


def main():
    t0 = time.time()
    obgg, zone_err = pull()
    wall = time.time() - t0
    print(f"  抓取 {wall:.1f}s（TCP/TLS 握手 {CONN_NEW[0]} 次"
          + ("" if KEEPALIVE else "，--no-keepalive 對照組") + "）", flush=True)
    print_breakdown(wall)
    # 2026-09-07（迴圈 #24）：請求最終失敗以前完全看不到，先印再過安全門（LPL 只抓到 11 帳號時才看得出是 team 請求掛了 3 次）。
    n_all = sum(ERRS.values())
    if n_all:
        print(f"⚠ OBGG 請求最終失敗 {n_all} 次（zone {ERRS['zone']}／team {ERRS['team']}／progamer {ERRS['progamer']}）："
              + "；".join(urllib.parse.unquote(u.replace(BASE, "")) for u in ERR_URLS[:5]) + ("…" if len(ERR_URLS) > 5 else ""))
    # 安全門：OBGG 主導賽區必須抓到夠多帳號，否則不動（避免 OBGG 異常時誤刪整批）
    for z in OBGG_ZONES:
        n = sum(len(v) for v in obgg.get(z, {}).values())
        if n < 20:
            print(f"✗ {z} 只抓到 {n} 帳號（<20），OBGG 可能異常 → 不更新 soloq_accounts.json"); return
    # 安全門 2（2026-09-07 迴圈 #24）：請求最終失敗的隊／人不在清單，以前會被當「近兩月未列」刪掉（dpm 近 3 天確認過的才暫留）。
    # OBGG 主導賽區失敗 ≥ ERR_ABORT 次 → 不動帳號檔（跟上面那道門同精神，等下一輪再抓）。
    n_err = sum(zone_err.get(z, 0) for z in OBGG_ZONES)
    if n_err >= ERR_ABORT:
        print(f"✗ LPL/LCK 的請求失敗 {n_err} 次（≥{ERR_ABORT}），失敗的隊／人會被誤判成「未列」→ 不更新 soloq_accounts.json"); return

    acc = json.load(open(ACCOUNTS, encoding="utf-8"))
    cur_teams = set(a.get("team") for a in acc)

    def canon(tm):
        a = ALIAS.get(tm)
        return a if a and a in cur_teams else tm

    team_zone = {}
    for z, teams in obgg.items():
        for tm in teams:
            team_zone[canon(tm)] = z

    def zone_of(team):
        return team_zone.get(team)

    cur_by_rid = {norm(a["riotId"]): a for a in acc}
    dis_idx = load_disowned()      # #67：歸屬複查剔除過的 (rid, 隊|名) 不從 OBGG 補回
    dis_skipped = []

    def obgg_entries(pred):
        res = []
        for z, teams in obgg.items():
            if not pred(z):
                continue
            for tm, ps in teams.items():
                tc = canon(tm)
                for gid, accs in ps.items():
                    for a in accs:
                        d = disowned_of(dis_idx, tc, gid, a["riotId"])
                        if d:
                            dis_skipped.append(f"  [歸屬] {tc}|{gid}: {a['riotId']} 名單已記是「{d.get('owner') or '?'}」的帳號"
                                               f"（{str(d.get('at') or '')[:16]}）→ 不從 OBGG 補回")
                            continue
                        e = {"player": gid, "team": tc, "platform": a["platform"], "riotId": a["riotId"]}
                        old = cur_by_rid.get(norm(a["riotId"]))
                        if old:  # 沿用已解析的 dpmPuuid 與張冠李戴標記
                            if old.get("dpmPuuid"):
                                e["dpmPuuid"] = old["dpmPuuid"]
                            if old.get("bad"):
                                e["bad"] = old["bad"]; e["bad_reason"] = old.get("bad_reason")
                        res.append(e)
        return res

    new = obgg_entries(lambda z: z in OBGG_ZONES)
    new += obgg_entries(lambda z: z not in OBGG_ZONES and z not in DPM_ZONES)
    new_rids = {norm(e["riotId"]) for e in new}

    removed, kept_dpm = prune_old(acc, new, new_rids, zone_of)   # OBGG 主導：不在清單的舊帳號，dpm 近 3 天確認過才暫留

    best = {}
    for e in new:
        k = norm(e["riotId"]); ex = best.get(k)
        if not ex or (not ex.get("dpmPuuid") and e.get("dpmPuuid")):
            best[k] = e
    final = list(best.values())

    # #107：`--out=` 是唯讀旁路，但名冊以前照樣覆寫正本 csv_cache/obgg_roster.json
    #（docstring 第 12 行寫「不動正本」，實際上動了一個）⇒ 拿它當計時探針會留下副作用。現在一起關掉。
    if OUT != ACCOUNTS:
        print(f"現役選手名冊：{len(ROSTER_PLAYERS)} 位（--out= 旁路，不覆寫 csv_cache/obgg_roster.json）")
    else:
        try:
            os.makedirs(os.path.dirname(ROSTER_OUT), exist_ok=True)
            json.dump(sorted(ROSTER_PLAYERS), open(ROSTER_OUT, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"現役選手名冊：{len(ROSTER_PLAYERS)} 位 → csv_cache/obgg_roster.json")
        except Exception as e:
            print(f"（名冊寫出失敗：{e}）")
    if OUT == ACCOUNTS:                    # 只有寫回正本才留備份（--out= 是驗證用的旁路，不動正本）
        json.dump(acc, open(ACCOUNTS + ".bak", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(final, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for ln in dis_skipped:
        print(ln, flush=True)
    print(f"OBGG 帳號更新：{len(acc)} → {len(final)}（LPL/LCK 刪 {removed} 個近兩月未列、"
          f"dpm 近 {KEEP_DPM_DAYS} 天確認過暫留 {kept_dpm} 個；歸屬名單略過 {len(dis_skipped)} 隻；"
          f"無 dpmPuuid {sum(1 for e in final if not e.get('dpmPuuid'))} 個待 resolve_obgg_dpmpuuid.py 補）")


OUT = ACCOUNTS          # --out=PATH：把結果寫到別的檔（驗證用，不動 soloq_accounts.json 正本）

if __name__ == "__main__":
    for a in sys.argv[1:]:
        if a.startswith("--jobs="):
            JOBS = max(1, int(a.split("=", 1)[1]))
        if a.startswith("--team-jobs="):
            TEAM_JOBS = max(1, int(a.split("=", 1)[1]))
        if a == "--no-keepalive":          # 對照組：回到「每個請求都重新握手」的舊行為
            KEEPALIVE = False
        if a.startswith("--out="):
            OUT = a.split("=", 1)[1]
    main()
