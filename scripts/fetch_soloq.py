# -*- coding: utf-8 -*-
"""
抓取「各隊選手 solo queue 積分」→ 產生 soloq.js（window.SOLOQ_DATA）供儀表板「積分」分頁使用。

用法（PowerShell）：
    $env:RIOT_API_KEY="RGAPI-你的金鑰"; python scripts\fetch_soloq.py

帳號清單放在 scripts\soloq_accounts.json（見該檔範例）：
    [{"player":"Faker","team":"T1","platform":"kr","riotId":"gameName#tagLine"}, ...]
    platform: kr / na1 / euw1 / eun1 / br1 / jp1 / la1 / la2 / oc1 / tr1 / ru / sg2 / ph2 / th2 / tw2 / vn2
    （帳號來源：https://dpm.lol/esport/soloq 各隊選手積分帳號）

Riot API（免費 dev key，20 req/s、100 req/2min，會照速率限制自動 sleep）。
金鑰只從環境變數 RIOT_API_KEY 讀，不寫進任何檔案。
"""
import io, os, sys, json, time, re, urllib.parse, urllib.request, urllib.error, datetime, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ACCOUNTS = os.path.join(HERE, "soloq_accounts.json")
OUT = os.path.join(ROOT, "soloq.js")
TODAY = time.strftime("%Y-%m-%d")   # 對照帳號的 dpmSeen＝dpm 選手檔今天確認過該 riotId（改名回寫的守門用）

KEY = os.environ.get("RIOT_API_KEY", "").strip()
if not KEY:
    print("錯誤：沒有 RIOT_API_KEY 環境變數。\n請先在 PowerShell 執行： $env:RIOT_API_KEY=\"RGAPI-...\"  再跑本腳本。")
    sys.exit(1)
# Riot 走 Cloudflare，urllib 預設 UA 會被擋(403 error 1010) → 一定要帶瀏覽器 User-Agent
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# platform(遊戲伺服器) → account-v1 的區域叢集(regional cluster)
CLUSTER = {
    "na1":"americas","br1":"americas","la1":"americas","la2":"americas","oc1":"americas",
    "euw1":"europe","eun1":"europe","tr1":"europe","ru":"europe",
    "kr":"asia","jp1":"asia","sg2":"asia","ph2":"asia","th2":"asia","tw2":"asia","vn2":"asia",
}
# 友善名稱 → platform（方便手填）
ALIAS = {"KR":"kr","NA":"na1","EUW":"euw1","EUNE":"eun1","BR":"br1","JP":"jp1",
         "LAN":"la1","LAS":"la2","OCE":"oc1","TR":"tr1","RU":"ru","VN":"vn2","TW":"tw2","SG":"sg2"}

_req_times = collections.deque()   # 送出時間戳
# ── 速率上限：**照 Riot 每次回應的 X-App-Rate-Limit 標頭自動調整**（2026-09-05）──
# 原本這裡寫死 dev 金鑰的 20/s + 100/2min。使用者其實早就換成長期金鑰
# （riot_key.local.json 的 permanent:true），額度高得多，卻還是照 dev 的節奏在等——
# 上一次每日更新因此「速率窗口暫停」**39 次**，光等就吃掉大半時間。
# 標頭格式：`X-App-Rate-Limit: 20:1,100:120`（次數:秒數，逗號分隔多組）。
# 抓不到標頭就退回 dev 值＝跟改動前完全一樣的行為（fail-safe）。
_LIMITS = [(20, 1.0), (100, 120.0)]      # [(次數, 視窗秒數)]；第一次回應後會被真實額度取代
_LIM_SRC = "預設（dev 金鑰值，還沒讀到標頭）"


def _set_limits(hdr):
    """把 `X-App-Rate-Limit` 解析成 [(次數, 秒)]。解析失敗就不動（保持保守值）。"""
    global _LIMITS, _LIM_SRC
    if not hdr:
        return
    try:
        got = []
        for part in str(hdr).split(","):
            c, _, s = part.strip().partition(":")
            c, s = int(c), float(s)
            if c > 0 and s > 0:
                got.append((c, s))
        if got and got != _LIMITS:
            old = _LIMITS
            _LIMITS = got
            _LIM_SRC = "Riot 標頭 " + str(hdr)
            print("    ⚡ 依 Riot 回傳的額度調整節流：%s → %s"
                  % (",".join("%d/%gs" % x for x in old), ",".join("%d/%gs" % x for x in got)), flush=True)
    except Exception:
        pass


def _throttle():
    """每一組 (次數, 視窗) 都要滿足；只留最長視窗內的時間戳。"""
    if not _LIMITS:
        return
    span = max(s for _, s in _LIMITS)
    now = time.time()
    while _req_times and now - _req_times[0] > span:
        _req_times.popleft()
    for cnt, sec in _LIMITS:
        recent = [t for t in _req_times if now - t < sec]
        # 餘裕只留 2%（至少 1 個名額）：本來寫 10%，但實測金鑰額度就是 100:120，
        # 留 10 個名額等於**白白慢 10%**（而且改動前的舊碼從沒撞過 429，日誌 429 次數＝0）。
        if len(recent) >= max(1, cnt - max(1, int(cnt * 0.02))):
            wait = sec - (now - recent[0]) + 0.1
            if wait > 3:
                print("    ⏸ 速率窗口暫停 %.0fs（額度 %d 次/%gs，來源：%s）"
                      % (wait, cnt, sec, _LIM_SRC), flush=True)
            if wait > 0:
                time.sleep(wait)
                now = time.time()

def riot_get(url):
    for attempt in range(4):
        _throttle()
        req = urllib.request.Request(url, headers={"X-Riot-Token": KEY, "User-Agent": UA})
        _req_times.append(time.time())
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                _set_limits(r.headers.get("X-App-Rate-Limit"))   # 每次都看，額度變了就跟著改
                return r.getcode(), json.load(r)
        except urllib.error.HTTPError as e:
            _set_limits(e.headers.get("X-App-Rate-Limit") if e.headers else None)
            if e.code == 429:                       # 被限速 → 等 Retry-After 再試
                ra = int(e.headers.get("Retry-After", "5"))
                print(f"    429 限速，等 {ra}s…"); time.sleep(ra + 1); continue
            if e.code == 404: return 404, None
            return e.code, None
        except Exception as ex:
            print(f"    連線錯誤：{ex}，重試…"); time.sleep(2); continue
    return 0, None

def get_account(cluster, game_name, tag_line):
    # account-v1：回傳含 puuid(永久不變的 UID)＋當前 gameName/tagLine
    url = (f"https://{cluster}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/"
           f"{urllib.parse.quote(game_name)}/{urllib.parse.quote(tag_line)}")
    code, data = riot_get(url)
    return data if code == 200 and data else None

def get_region_by_puuid(cluster, puuid):
    # account-v1 region/by-game：帳號清單缺 platform（dpm 回 null）時，問 Riot 這個 puuid 的 LoL 伺服器（回 "br1"/"kr"…）
    code, data = riot_get(f"https://{cluster}.api.riotgames.com/riot/account/v1/region/by-game/lol/by-puuid/{puuid}")
    return (data or {}).get("region", "").lower() if code == 200 and data else None

def get_account_by_puuid(cluster, puuid):
    # 改名自動修復：舊 Riot ID 查不到時，用上次存的 puuid 反查目前 ID（puuid 永不變）
    code, data = riot_get(f"https://{cluster}.api.riotgames.com/riot/account/v1/accounts/by-puuid/{puuid}")
    return data if code == 200 and data else None

def load_prev_puuids():
    # 上一次 soloq.js 的 puuid 快取：{(riotId,platform):puuid} ＋ {(team,player,platform):puuid}
    by_id, by_tp = {}, {}
    try:
        h = open(OUT, encoding="utf-8", errors="replace").read()
        d = json.loads(re.search(r"=\s*(\{.*\});?\s*$", h, re.S).group(1))
        for p in d.get("players", []):
            if p.get("puuid"):
                by_id[(p.get("riotId"), p.get("platform"))] = p["puuid"]
                by_tp[(p.get("team"), p.get("player"), p.get("platform"))] = p["puuid"]
    except Exception:
        pass
    return by_id, by_tp

def get_soloq(platform, puuid):
    """回傳 (單雙排紀錄或 None, 確定嗎)。

    第二個值是 2026-09-05 加的：**分辨「問到了，他就是沒有排名」與「這次沒問成」**。
    以前兩者都回 None，呼叫端一律排進重抓 ⇒ 每天為「未定位／沒打排位」的帳號白跑一輪
    （上一次 1092 個帳號裡有 277 個進重抓，絕大多數是這種永遠不會變的）。
    確定＝True 時呼叫端不再重抓。
    """
    # 先試 by-puuid；不支援(404)再退回 summoner-v4 → by-summoner
    code, data = riot_get(f"https://{platform}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}")
    if code == 404:
        c2, s = riot_get(f"https://{platform}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}")
        if c2 == 200 and s and s.get("id"):
            code, data = riot_get(f"https://{platform}.api.riotgames.com/lol/league/v4/entries/by-summoner/{s['id']}")
        elif c2 == 404:
            return None, True          # 這個 puuid 在這個區沒有召喚師資料＝確定，不用重抓
    if code == 200 and isinstance(data, list):
        for e in data:
            if e.get("queueType") == "RANKED_SOLO_5x5":
                return e, True
        return None, True              # 200 且是清單、只是沒有單雙排那一項＝**確定沒排名**
    return None, False                 # 非 200（連線失敗／5xx／限速用完重試次數）＝這次沒問成

def main():
    if not os.path.exists(ACCOUNTS):
        print(f"錯誤：找不到帳號清單 {ACCOUNTS}\n請建立該檔（格式見腳本說明）。")
        sys.exit(1)
    with open(ACCOUNTS, "r", encoding="utf-8") as f:
        accounts = json.load(f)
    accounts = [a for a in accounts if a.get("riotId") and "#" in a.get("riotId","") and not a.get("bad")]  # bad＝張冠李戴帳號，牌位也不抓
    seen_a = set(); accounts = [a for a in accounts
        if (k := (a.get("team"), a.get("player"), a.get("platform"), a.get("riotId"))) not in seen_a and not seen_a.add(k)]  # 改名同步後可能出現重複帳號 → 去重
    PREV_ALL = []
    # ── --active：只更新「最近有打排位」的選手（2026-09-05，使用者要加速每日爬蟲）──
    # 牌位只有打過的人會變。逐場資料（soloq_recent.js）在 update.bat 裡**跑在這一支之前**，
    # 所以拿它挑人是新鮮的。挑不到的（沒有逐場檔的新選手／逐場落後）一律當成要更新，
    # 寧可多抓也不要漏。完整掃描由 fetch_soloq_auto.py 每週排一次（見那支的 --active 判斷）。
    if "--active" in sys.argv:
        _days = 3
        for _i, _a9 in enumerate(sys.argv):
            if _a9 == "--active-days" and _i + 1 < len(sys.argv):
                try:
                    _days = max(1, int(sys.argv[_i + 1]))
                except ValueError:
                    pass
        try:
            _rt = open(os.path.join(ROOT, "soloq_recent.js"), encoding="utf-8", errors="replace").read()
            _rm = re.search(r"=\s*\{", _rt)
            _rec = json.loads(_rt[_rm.end() - 1:].rstrip().rstrip(";"))
            _gen = str(_rec.get("genDay") or "")
            _keep = set()
            import datetime as _dt
            _base = _dt.date.fromisoformat(_gen) if _gen else _dt.date.today()
            _win = {(_base - _dt.timedelta(days=i)).isoformat() for i in range(0, _days + 1)}
            for _k, _v in (_rec.get("players") or {}).items():
                if any(d in _win and (_v.get("d") or {}).get(d) for d in _win):
                    _t9, _, _p9 = _k.partition("|")
                    _keep.add((_t9, _p9))
            _known = {(_t9, _p9) for _t9, _p9 in
                      ((str(k).partition("|")[0], str(k).partition("|")[2]) for k in (_rec.get("players") or {}))}
            _before = len(accounts)
            # 有逐場檔但這幾天沒打 ⇒ 跳過；**沒有逐場檔的一律保留**（不知道＝要抓）
            accounts = [a for a in accounts
                        if (a.get("team"), a.get("player")) in _keep
                        or (a.get("team"), a.get("player")) not in _known]
            print("--active：近 %d 天有打排位的選手 %d 位 → 帳號 %d → %d 筆（跳過 %d 筆；"
                  "沒有逐場檔的一律保留）" % (_days, len(_keep), _before, len(accounts), _before - len(accounts)))
            if not accounts:
                print("--active：沒有需要更新的帳號，維持現有 soloq.js。"); return
            prevh = open(OUT, encoding="utf-8", errors="replace").read()
            PREV_ALL = json.loads(re.search(r"=\s*(\{.*\});?\s*$", prevh, re.S).group(1)).get("players", [])
        except Exception as _e9:
            print("--active：挑選失敗（%s）→ 退回全量抓取" % type(_e9).__name__)
            PREV_ALL = []
    if "--failed" in sys.argv:  # 只重抓上次 found=false 的選手（該選手全部帳號），結果併回 soloq.js
        try:
            prevh = open(OUT, encoding="utf-8", errors="replace").read()
            PREV_ALL = json.loads(re.search(r"=\s*(\{.*\});?\s*$", prevh, re.S).group(1)).get("players", [])
        except Exception:
            PREV_ALL = []
        bad = {(p.get("team"), p.get("player")) for p in PREV_ALL if not p.get("found")}
        accounts = [a for a in accounts if (a.get("team"), a.get("player")) in bad]
        if not accounts:
            print("--failed：上次沒有失敗帳號，跳過。"); return
        print(f"--failed：只重抓上次失敗的 {len(accounts)} 個帳號（{sorted({a.get('player','') for a in accounts})}）")
    print(f"帳號清單 {len(accounts)} 筆，開始抓取…（依速率限制，約 {len(accounts)*2.5/60:.1f} 分鐘）")

    global PREV_ID, PREV_TP, RENAMES, PLATFIX, FAST_ID
    PREV_ID, PREV_TP = load_prev_puuids(); RENAMES = {}; PLATFIX = {}   # PLATFIX：缺 platform 的帳號用 Riot 查到的伺服器，最後寫回清單
    # 有存 puuid 就跳過 account-v1 那一次查詢（見 fetch_one 的註解）。
    # `--full-id`＝關掉捷徑、走完整路徑把改名補回來（每週全掃那一次用）。
    FAST_ID = "--full-id" not in sys.argv
    if FAST_ID:
        _hit = sum(1 for a in accounts if PREV_ID.get((a["riotId"],
                   ALIAS.get(str(a.get("platform","")).upper(), str(a.get("platform","")).lower()))))
        print("puuid 捷徑：%d/%d 個帳號可跳過 account-v1 查詢（請求數約省 %.0f%%）"
              % (_hit, len(accounts), 100.0 * _hit / max(1, 2 * len(accounts))))
    def fetch_one(a, tag_lbl):
        plat = ALIAS.get(str(a.get("platform","")).upper(), str(a.get("platform","")).lower())
        cluster = CLUSTER.get(plat, "asia")
        game, tagl = a["riotId"].rsplit("#", 1)
        print(f"[{tag_lbl}] {a.get('player','?')} ({a.get('team','?')}) {a['riotId']} @{plat}")
        # ── 捷徑：上一版已經存過這個帳號的 Riot puuid 就直接用（2026-09-05）──────
        # puuid 是**永久不變**的（改名也不變），所以省掉 account-v1 那一次查詢完全安全。
        # 這是牌位這一步最大的一刀：1092 個帳號裡 964 個（88%）有存 puuid ⇒
        # 請求數從 ~2184 降到 ~1220（-44%），而 dev 金鑰的 100 次/2 分鐘正是整條管線的瓶頸。
        # 代價：**改名不會當天被發現**（用舊 puuid 照樣查得到牌位，只是顯示的 Riot ID 是舊的）
        # ⇒ `--full-id`（每週全掃那次會帶）仍走完整路徑，把改名補回來。
        acc = None
        if FAST_ID:
            _pu0 = PREV_ID.get((a["riotId"], plat))
            if _pu0:
                acc = {"puuid": _pu0, "gameName": game.strip(), "tagLine": tagl.strip(), "_cached": True}
        if acc is None:
            acc = get_account(cluster, game.strip(), tagl.strip())  # dpm 的 puuid 非 Riot puuid，用 account-v1 解析真 puuid
        via_prev = False
        if not acc:  # 舊 ID 查不到（改名/暫時性失敗）→ 用上次 puuid 反查目前 ID（改名自動修復）
            # PREV_ID 以 (riotId,platform) 為鍵＝同一個帳號，安全；
            # PREV_TP 以 (team,player,platform) 為鍵＝**該選手在該區的任一帳號**，可能根本不是這筆的
            # puuid。若 dpm 選手檔今天才確認過這個名字，就不准用這條鬆散反查——否則會拿到別人的
            # 帳號、把牌位查成空的，還會把正確的新名字回寫成舊名。
            # （HLE Zeus：Athene#lll 查不到 → PREV_TP 給了舊 puuid → 反查回 zeus#glgl＝接手舊名的別人）
            pu2 = PREV_ID.get((a["riotId"], plat))
            if not pu2 and a.get("dpmSeen") != TODAY:
                pu2 = PREV_TP.get((a.get("team"), a.get("player"), plat))
            if pu2:
                acc = get_account_by_puuid(cluster, pu2); via_prev = True
                if acc: print(f"    ♻ 以 puuid 反查成功：目前 ID = {acc.get('gameName')}#{acc.get('tagLine')}")
        puuid = acc.get("puuid") if acc else None
        curId = (acc.get("gameName","")+"#"+acc.get("tagLine","")) if acc else None  # Riot 目前的 Riot ID(可能已改名)
        # ⚠ 走 puuid 捷徑時 curId 是我們自己填的舊名，不是 Riot 現在的名字 ⇒ 不可以拿去判改名
        if curId and curId != a["riotId"] and not (acc or {}).get("_cached"):
            RENAMES[(a.get("team",""), a.get("player",""), a["riotId"])] = (curId, via_prev)
        rec = {"player": a.get("player",""), "team": a.get("team",""), "platform": plat,
               "riotId": a["riotId"], "puuid": puuid, "curId": curId,
               "tier": None, "division": None, "lp": None,
               "wins": None, "losses": None, "found": False}
        if puuid and not plat:  # 清單缺 platform（dpm 偶爾回 null，如 LOS Feisty#LOS）→ 問 Riot 這個 puuid 在哪個伺服器，並記下來寫回清單
            plat = get_region_by_puuid(cluster, puuid) or ""
            if plat:
                PLATFIX[(a.get("team",""), a.get("player",""), a["riotId"])] = plat
                rec["platform"] = plat
                print(f"    ♻ 清單缺 platform → Riot 區域端點：{plat}")
            else:
                print("    清單缺 platform，Riot 也查不到區域 → 跳過牌位查詢"); return rec
        if not puuid:
            dr = a.get("dpmRank")
            if dr and dr.get("tier"):  # Riot 查不到此舊 riotId(改名等) → 用抓帳號時 dpm 附帶的牌位當備援(如 KT FenRir)
                _lp = dr.get("lp")
                if _lp == 75:
                    _lp = None  # DPM 對非頂端帳號常回佔位 LP=75 → 當未知，只顯示牌位(頂端如 FenRir 1894 才是真值)
                rec.update(tier=dr.get("tier"), division=dr.get("rank"), lp=_lp, found=True, dpmRank=True)
                print(f"    ♻ Riot 查無此 ID → DPM 牌位備援：{dr.get('tier')} {dr.get('rank')} {_lp}LP")
                return rec
            print("    找不到帳號（Riot ID 或區域錯？）"); return rec
        sq, sure = get_soloq(plat, puuid)
        if sq:
            rec.update(tier=sq.get("tier"), division=sq.get("rank"), lp=sq.get("leaguePoints"),
                       wins=sq.get("wins"), losses=sq.get("losses"), found=True)
            print(f"    {sq.get('tier')} {sq.get('rank')} {sq.get('leaguePoints')}LP  {sq.get('wins')}W-{sq.get('losses')}L")
        else:
            # settled＝問到了、答案就是「沒有排名」⇒ 重抓那一輪不要再排它（見 get_soloq）
            rec["settled"] = bool(sure)
            print("    無 solo queue 排名（未定位或無資料）" + ("" if sure else "　※這次沒問成，稍後重抓"))
        return rec

    out = []; retry = []; settled = 0
    for i, a in enumerate(accounts, 1):
        rec = fetch_one(a, f"{i}/{len(accounts)}")
        # 暫時性失敗先跳過，記下位置，全部跑完最後重抓一輪（使用者判例 2026-07-16）。
        # ⚠ 2026-09-05：**「問到了、確定沒排名」不再排進重抓**——那種帳號（未定位／很久沒打）
        # 重抓一百次也是同一個答案，卻要照速率限制排隊。上一次 1092 個帳號有 277 個進重抓，
        # 這一刀砍掉的就是其中永遠不會變的那批。真正的暫時性失敗（連線錯誤／5xx）照舊重抓。
        if not rec["found"]:
            if rec.pop("settled", False):
                settled += 1
            else:
                retry.append((len(out), a))
        out.append(rec)
    if settled:
        print(f"（{settled} 個帳號確定沒有單雙排名次 → 不排進重抓，省下同樣次數的請求）")
    if retry:
        print(f"\n🔁 {len(retry)} 個帳號本輪失敗 → 最後重抓一輪（補救暫時性失敗）…")
        time.sleep(3)
        for pos, a in retry:
            rec2 = fetch_one(a, "重抓")
            if rec2["found"] or (rec2.get("puuid") and not out[pos].get("puuid")):
                out[pos] = rec2

    # 併回（--failed 與 --active 共用同一條路）：這次抓過的選手整組以新結果取代，其餘原樣保留
    if ("--failed" in sys.argv or "--active" in sys.argv) and PREV_ALL:
        newby = {}
        for r in out: newby.setdefault((r["team"], r["player"]), []).append(r)
        merged = []; used = set()
        for p in PREV_ALL:
            k = (p.get("team"), p.get("player"))
            if k in newby:
                if k not in used: merged.extend(newby[k]); used.add(k)
            else:
                merged.append(p)
        # ⚠ 這一輪抓到、但上一版檔案裡沒有的人要補進去（2026-09-05 測試抓到的資料遺失）：
        # 舊迴圈只走 PREV_ALL，所以**新選手會整個消失**。`--failed` 時剛好碰不到
        # （失敗的人本來就在檔裡），但 `--active` 會抓「沒有逐場檔的新人」⇒ 一定踩到。
        for k, rs in newby.items():
            if k not in used:
                merged.extend(rs)
        out = merged
    # ── 誰真的打過排位：勝＋敗有沒有變（2026-09-05 使用者定案的順序）────────────
    # 牌位回應本來就帶 wins／losses，跟上一版比就是**權威**答案——不用猜、也不會落後。
    # 逐場那一支（Playwright 開真 Chrome 過 Cloudflare）每位選手要 ~1.4 秒、431 位要 10 分鐘，
    # 而且**沒人打過也要花這 10 分鐘**（實測 --max 3 走完 431 位、結果 0 場）。
    # ⇒ 便宜的先跑、拿它的結果決定貴的要不要跑。名單寫到 scripts/soloq_played.json，
    #   由 fetch_soloq_update.py --changed 讀。
    try:
        prev_wl = {}
        if os.path.exists(OUT):
            _pt = open(OUT, encoding="utf-8", errors="replace").read()
            for p in json.loads(re.search(r"=\s*(\{.*\});?\s*$", _pt, re.S).group(1)).get("players", []):
                k = (p.get("team"), p.get("player"))
                w, l = p.get("wins"), p.get("losses")
                if w is not None or l is not None:
                    prev_wl[k] = prev_wl.get(k, 0) + (w or 0) + (l or 0)
        now_wl, seen_now = {}, set()
        for p in out:
            k = (p.get("team"), p.get("player"))
            w, l = p.get("wins"), p.get("losses")
            if w is not None or l is not None:
                now_wl[k] = now_wl.get(k, 0) + (w or 0) + (l or 0)
                seen_now.add(k)
        played, unknown = [], []
        for k in seen_now:
            if k not in prev_wl:
                unknown.append(k)                 # 上一版沒有這個人的場數 ⇒ 不知道，當成要抓
            elif now_wl[k] != prev_wl[k]:
                played.append(k)
        # 這一輪完全沒查到場數的人（未定位／查不到帳號）也放進 unknown：他們的排位狀態無從判斷
        for p in out:
            k = (p.get("team"), p.get("player"))
            if k not in seen_now and k not in unknown:
                unknown.append(k)
        io.open(os.path.join(HERE, "soloq_played.json"), "w", encoding="utf-8").write(
            json.dumps({"at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "scope": "active" if "--active" in sys.argv else "full",
                        "played": ["%s|%s" % k for k in sorted(played)],
                        "unknown": ["%s|%s" % k for k in sorted(set(unknown))]},
                       ensure_ascii=False))
        print("勝敗場數比對：**%d 位真的打過**、%d 位無從判斷（未定位/查無帳號）→ scripts/soloq_played.json"
              % (len(played), len(set(unknown))))
    except Exception as e:
        print("勝敗場數比對失敗（%s）→ 不寫 soloq_played.json（逐場那支會退回全掃）" % type(e).__name__)

    payload = {"fetched_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "players": out}
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.SOLOQ_DATA=" + json.dumps(payload, ensure_ascii=False) + ";\n")
    ok = sum(1 for r in out if r["found"])
    print(f"\n完成：{ok}/{len(out)} 有排名 → 已寫入 {OUT}")
    if PLATFIX:  # 缺 platform 的帳號補上 Riot 查到的伺服器（否則每天都要多問一次）
        raw = json.load(open(ACCOUNTS, encoding="utf-8")); n = 0
        for a in raw:
            k = (a.get("team",""), a.get("player",""), a.get("riotId",""))
            if k in PLATFIX and not a.get("platform"):
                a["platform"] = PLATFIX[k]; n += 1
        if n:
            json.dump(raw, open(ACCOUNTS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"♻ 補上 {n} 個帳號的 platform → soloq_accounts.json：")
            for (tm, pl, rid), pf in PLATFIX.items(): print(f"   {tm} {pl}: {rid} @{pf}")
    if RENAMES:  # 改名自動同步回帳號清單：下次起直接用新 ID 查
        raw = json.load(open(ACCOUNTS, encoding="utf-8")); n = 0; skipped = []
        for a in raw:
            k = (a.get("team",""), a.get("player",""), a.get("riotId",""))
            if k not in RENAMES: continue
            new, via_prev = RENAMES[k]
            # 反查來的名字不可信（用的 puuid 未必是這筆帳號的），不准蓋掉 dpm 選手檔今天確認過的名字
            if via_prev and a.get("dpmSeen") == TODAY:
                skipped.append((k[0], k[1], a.get("riotId",""), new)); continue
            a["riotId"] = new; n += 1
        if n:
            json.dump(raw, open(ACCOUNTS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"♻ 改名自動更新 {n} 個帳號 → soloq_accounts.json：")
            for (tm, pl, old), (new, _v) in RENAMES.items(): print(f"   {tm} {pl}: {old} → {new}")
        if skipped:
            print(f"⏭ 略過 {len(skipped)} 個反查來的改名（dpm 選手檔今天確認過現有名字）：")
            for tm, pl, old, new in skipped: print(f"   {tm} {pl}: 保留 {old}（未採用反查到的 {new}）")

if __name__ == "__main__":
    main()
