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
import os, sys, json, time, re, urllib.parse, urllib.request, urllib.error, datetime, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ACCOUNTS = os.path.join(HERE, "soloq_accounts.json")
OUT = os.path.join(ROOT, "soloq.js")

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

_req_times = collections.deque()   # 送出時間戳，控 20/s & 100/120s
def _throttle():
    now = time.time()
    while _req_times and now - _req_times[0] > 120: _req_times.popleft()
    # 100 / 2min
    if len(_req_times) >= 100:
        wait = 120 - (now - _req_times[0]) + 0.1
        if wait > 3:
            print(f"    ⏸ 速率窗口暫停 {wait:.0f}s（Riot 限 100 次/2 分鐘，約每 50 位選手停一次——正常，不是卡住）", flush=True)
        if wait > 0: time.sleep(wait)
    # 20 / 1s
    recent = [t for t in _req_times if time.time() - t < 1]
    if len(recent) >= 18:
        time.sleep(1.0)

def riot_get(url):
    for attempt in range(4):
        _throttle()
        req = urllib.request.Request(url, headers={"X-Riot-Token": KEY, "User-Agent": UA})
        _req_times.append(time.time())
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.getcode(), json.load(r)
        except urllib.error.HTTPError as e:
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
    # 先試 by-puuid；不支援(404)再退回 summoner-v4 → by-summoner
    code, data = riot_get(f"https://{platform}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}")
    if code == 404:
        c2, s = riot_get(f"https://{platform}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}")
        if c2 == 200 and s and s.get("id"):
            code, data = riot_get(f"https://{platform}.api.riotgames.com/lol/league/v4/entries/by-summoner/{s['id']}")
    if code == 200 and isinstance(data, list):
        for e in data:
            if e.get("queueType") == "RANKED_SOLO_5x5":
                return e
    return None

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

    global PREV_ID, PREV_TP, RENAMES
    PREV_ID, PREV_TP = load_prev_puuids(); RENAMES = {}
    def fetch_one(a, tag_lbl):
        plat = ALIAS.get(str(a.get("platform","")).upper(), str(a.get("platform","")).lower())
        cluster = CLUSTER.get(plat, "asia")
        game, tagl = a["riotId"].rsplit("#", 1)
        print(f"[{tag_lbl}] {a.get('player','?')} ({a.get('team','?')}) {a['riotId']} @{plat}")
        acc = get_account(cluster, game.strip(), tagl.strip())  # dpm 的 puuid 非 Riot puuid，用 account-v1 解析真 puuid
        if not acc:  # 舊 ID 查不到（改名/暫時性失敗）→ 用上次 puuid 反查目前 ID（改名自動修復）
            pu2 = PREV_ID.get((a["riotId"], plat)) or PREV_TP.get((a.get("team"), a.get("player"), plat))
            if pu2:
                acc = get_account_by_puuid(cluster, pu2)
                if acc: print(f"    ♻ 以 puuid 反查成功：目前 ID = {acc.get('gameName')}#{acc.get('tagLine')}")
        puuid = acc.get("puuid") if acc else None
        curId = (acc.get("gameName","")+"#"+acc.get("tagLine","")) if acc else None  # Riot 目前的 Riot ID(可能已改名)
        if curId and curId != a["riotId"]:
            RENAMES[(a.get("team",""), a.get("player",""), a["riotId"])] = curId
        rec = {"player": a.get("player",""), "team": a.get("team",""), "platform": plat,
               "riotId": a["riotId"], "puuid": puuid, "curId": curId,
               "tier": None, "division": None, "lp": None,
               "wins": None, "losses": None, "found": False}
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
        sq = get_soloq(plat, puuid)
        if sq:
            rec.update(tier=sq.get("tier"), division=sq.get("rank"), lp=sq.get("leaguePoints"),
                       wins=sq.get("wins"), losses=sq.get("losses"), found=True)
            print(f"    {sq.get('tier')} {sq.get('rank')} {sq.get('leaguePoints')}LP  {sq.get('wins')}W-{sq.get('losses')}L")
        else:
            print("    無 solo queue 排名（未定位或無資料）")
        return rec

    out = []; retry = []
    for i, a in enumerate(accounts, 1):
        rec = fetch_one(a, f"{i}/{len(accounts)}")
        if not rec["found"]:  # 暫時性失敗先跳過，記下位置，全部跑完最後重抓一輪（使用者判例 2026-07-16）
            retry.append((len(out), a))
        out.append(rec)
    if retry:
        print(f"\n🔁 {len(retry)} 個帳號本輪失敗/無排名 → 最後重抓一輪（補救暫時性失敗）…")
        time.sleep(3)
        for pos, a in retry:
            rec2 = fetch_one(a, "重抓")
            if rec2["found"] or (rec2.get("puuid") and not out[pos].get("puuid")):
                out[pos] = rec2

    if "--failed" in sys.argv and PREV_ALL:  # 併回：失敗選手整組以新結果取代，其餘紀錄原樣保留
        newby = {}
        for r in out: newby.setdefault((r["team"], r["player"]), []).append(r)
        merged = []; used = set()
        for p in PREV_ALL:
            k = (p.get("team"), p.get("player"))
            if k in newby:
                if k not in used: merged.extend(newby[k]); used.add(k)
            else:
                merged.append(p)
        out = merged
    payload = {"fetched_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "players": out}
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.SOLOQ_DATA=" + json.dumps(payload, ensure_ascii=False) + ";\n")
    ok = sum(1 for r in out if r["found"])
    print(f"\n完成：{ok}/{len(out)} 有排名 → 已寫入 {OUT}")
    if RENAMES:  # 改名自動同步回帳號清單：下次起直接用新 ID 查
        raw = json.load(open(ACCOUNTS, encoding="utf-8")); n = 0
        for a in raw:
            k = (a.get("team",""), a.get("player",""), a.get("riotId",""))
            if k in RENAMES:
                a["riotId"] = RENAMES[k]; n += 1
        if n:
            json.dump(raw, open(ACCOUNTS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"♻ 改名自動更新 {n} 個帳號 → soloq_accounts.json：")
            for (tm, pl, old), new in RENAMES.items(): print(f"   {tm} {pl}: {old} → {new}")

if __name__ == "__main__":
    main()
