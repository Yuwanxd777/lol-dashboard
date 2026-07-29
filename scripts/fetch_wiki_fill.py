# -*- coding: utf-8 -*-
"""OE 未收錄賽事的應急補資料：Leaguepedia Cargo → OE CSV 格式 → fetch_data.process() → RAW_DATA 相容列

背景：OE(Oracle's Elixir) 對某些賽段收錄很慢（2026-07-28：LPL Split 3 已打完第一週 33 局，OE 一場都沒有）。
本腳本從 Leaguepedia 的 Cargo 表抓同一批比賽，組成「OE CSV 格式」的原始列，再交給 fetch_data.process()
產生完全相容的 RAW_DATA 列（po/Lane/banlist/picklist/decider_winner 等衍生欄位全部沿用同一套邏輯，不另寫）。

輸出 csv_cache/wikifill_{年}.json；fetch_data.py 寫檔前會併入（同一局以 OE 為準，OE 收錄後自動退場）。

限制（wiki 沒有的欄位一律留空，與 OE 的 LPL 資料現況一致）：
  - @10/@15/@20/@25 全系列（LPL 本來就沒有：OE 的 LPL 現有資料同樣是空的）
  - firstblood/firsttower/firstdragon 等「首殺旗標」、turretplates、earnedgold、gspd
  - wardsplaced/wardskilled/controlwardsbought（Cargo 只有 VisionScore）
  有的：K/D/A、金錢、CS、傷害、視野分、隊伍物件(龍/男爵/塔/水晶/先鋒/虛空幼蟲/納塔坎)、BP 全順序、patch、路線

用法：
  python scripts\fetch_wiki_fill.py                # 抓設定表中所有賽事（有快取就不重抓）
  python scripts\fetch_wiki_fill.py --force        # 強制重抓 Cargo
  python scripts\fetch_wiki_fill.py --list         # 只列出設定與現況
Cargo 限流很兇（6 秒節流仍會被擋）→ 預設每次請求間隔 25 秒、遇限流退避 60/120/240 秒。
"""
import argparse, csv, io, json, os, re, sys, time, urllib.parse, urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, "csv_cache")
if not os.path.isdir(CACHE):
    CACHE = os.path.join(ROOT, "csv_cache")

API = "https://lol.fandom.com/api.php"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
THROTTLE = 25          # 每次 Cargo 請求後的固定間隔（秒）
BACKOFF = [60, 120, 240]

# ── 要補的賽事（OE 收錄後可整條刪掉，或留著——併入時 OE 優先，不會重複） ──
FILL = [
    {"key": "LPL_2026_S3", "overview": "LPL/2026 Season/Split 3",
     "league": "LPL", "split": "Split 3", "year": 2026, "playoffs": 0},
]

ROLE2POS = {"top": "top", "jungle": "jng", "mid": "mid", "middle": "mid",
            "bot": "bot", "adc": "bot", "support": "sup", "sup": "sup"}
POS_PID = {"top": 1, "jng": 2, "mid": 3, "bot": 4, "sup": 5}


def cargo(tables, fields, where, limit=500, offset=0):
    p = {"action": "cargoquery", "format": "json", "tables": tables, "fields": fields,
         "where": where, "limit": str(limit), "offset": str(offset)}
    url = API + "?" + urllib.parse.urlencode(p)
    for a in range(len(BACKOFF) + 1):
        try:
            raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read()
            r = json.loads(raw)
            if "error" in r:
                info = r["error"].get("info", "")
                if "rate limit" in info.lower() and a < len(BACKOFF):
                    w = BACKOFF[a]; print(f"      限流 → 等 {w}s", flush=True); time.sleep(w); continue
                raise RuntimeError("Cargo error: " + info[:200])
            time.sleep(THROTTLE)
            return [x["title"] for x in r.get("cargoquery", [])]
        except Exception as e:
            if a >= len(BACKOFF):
                raise
            w = BACKOFF[a]
            print(f"      {type(e).__name__}: {str(e)[:90]} → 等 {w}s 重試", flush=True)
            time.sleep(w)
    return []


def cargo_all(tables, fields, where, page=500):
    """自動翻頁"""
    out, off = [], 0
    while True:
        got = cargo(tables, fields, where, limit=page, offset=off)
        out.extend(got)
        if len(got) < page:
            break
        off += page
        print(f"      …已取 {len(out)} 列", flush=True)
    return out


def oe_games(year, league, split_norm):
    """OE 目前收錄了幾局（data_{年}.js 的 RAW_DATA，以 pid=100 戰隊列計數）。
    split_norm＝正規化後的 split（"Split 3"→"S3"，含季後賽則另有 "S3 PO"）"""
    p = os.path.join(ROOT, "data", f"data_{year}.js")
    if not os.path.exists(p):
        return 0
    with open(p, encoding="utf-8") as f:
        D = json.loads(f.read().split("=", 1)[1].strip().rstrip(";"))
    R = D["tabs"]["RAW_DATA"]; h = R[0]
    iL, iS, iP = h.index("league"), h.index("split"), h.index("participantid")
    iD, iG = h.index("date"), h.index("game")
    seen = set()
    for r in R[1:]:
        if r[iL] == league and str(r[iS]).split(" PO")[0] == split_norm and str(r[iP]) == "100":
            seen.add((str(r[iD])[:10], str(r[iG])))
    return len(seen)


def fetch_one(cfg, force=False):
    """抓一個賽事的三張表；回傳 dict(games, players, pb)。
    OE 已追上（收錄局數 ≥ 上次 wiki 抓到的局數）就完全不抓——使用者定案：OE 有更新後就不再抓 wiki/gol.gg。"""
    path = os.path.join(CACHE, f"wikifill_raw_{cfg['key']}.json")
    sn = cfg["split"].replace("Split ", "S")
    n_oe = oe_games(cfg["year"], cfg["league"], sn)
    n_wiki = 0
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                n_wiki = len(json.load(f).get("games") or [])
        except Exception:
            pass
    if n_oe and (not n_wiki or n_oe >= n_wiki):
        print(f"  {cfg['key']}：OE 已收錄 {n_oe} 局（wiki 快取 {n_wiki} 局）→ 停止補抓，改用 OE")
        return None
    if os.path.exists(path) and not force:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        print(f"  {cfg['key']}：用快取（{len(d.get('games',[]))} 局 / {len(d.get('players',[]))} 選手列）")
        return d
    ovw = cfg["overview"].replace('"', '')
    W = lambda t: f'{t}.OverviewPage="{ovw}"'
    print(f"  {cfg['key']}：抓 Cargo（每請求間隔 {THROTTLE}s）…", flush=True)

    print("    ScoreboardGames…", flush=True)
    games = cargo_all("ScoreboardGames",
        "GameId,MatchId,N_GameInMatch,DateTime_UTC,Patch,Gamelength_Number,Team1,Team2,WinTeam,"
        "Team1Kills,Team2Kills,Team1Gold,Team2Gold,Team1Dragons,Team2Dragons,Team1Barons,Team2Barons,"
        "Team1Towers,Team2Towers,Team1Inhibitors,Team2Inhibitors,Team1RiftHeralds,Team2RiftHeralds,"
        "Team1VoidGrubs,Team2VoidGrubs,Team1Atakhans,Team2Atakhans,"
        "Team1Infernals,Team1Mountains,Team1Clouds,Team1Oceans,Team1Chemtechs,Team1Hextechs,Team1Elders,"
        "Team2Infernals,Team2Mountains,Team2Clouds,Team2Oceans,Team2Chemtechs,Team2Hextechs,Team2Elders,"
        "Team1Bans,Team2Bans,Team1Picks,Team2Picks", W("ScoreboardGames"))
    print(f"      {len(games)} 局", flush=True)

    print("    ScoreboardPlayers…", flush=True)
    players = cargo_all("ScoreboardPlayers",
        "GameId,Name,Link,Team,Champion,Role,Role_Number,Side,Kills,Deaths,Assists,Gold,CS,"
        "DamageToChampions,VisionScore,TeamKills,TeamGold,PlayerWin,Pentakills", W("ScoreboardPlayers"))
    print(f"      {len(players)} 列", flush=True)

    print("    PicksAndBansS7…", flush=True)
    pb = cargo_all("PicksAndBansS7",
        "GameId,Team1,Team2,Winner,"
        "Team1Ban1,Team1Ban2,Team1Ban3,Team1Ban4,Team1Ban5,Team2Ban1,Team2Ban2,Team2Ban3,Team2Ban4,Team2Ban5,"
        "Team1Pick1,Team1Pick2,Team1Pick3,Team1Pick4,Team1Pick5,Team2Pick1,Team2Pick2,Team2Pick3,Team2Pick4,Team2Pick5,"
        "Team1Role1,Team1Role2,Team1Role3,Team1Role4,Team1Role5,Team2Role1,Team2Role2,Team2Role3,Team2Role4,Team2Role5",
        W("PicksAndBansS7"))
    print(f"      {len(pb)} 局", flush=True)

    d = {"games": games, "players": players, "pb": pb, "cfg": cfg}
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--list", action="store_true")
    A = ap.parse_args()
    if A.list:
        for c in FILL:
            p = os.path.join(CACHE, f"wikifill_raw_{c['key']}.json")
            print(f"  {c['key']:14s} {c['overview']:32s} 快取={'有' if os.path.exists(p) else '無'}")
        return
    for cfg in FILL:
        fetch_one(cfg, force=A.force)
    print("完成。")


if __name__ == "__main__":
    main()
