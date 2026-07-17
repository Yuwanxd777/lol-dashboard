# -*- coding: utf-8 -*-
"""scoregg（尚牛電競，OBGG 小程式同源資料）職業選手積分帳號紀錄
API：POST https://www.scoregg.com/services/api_url.php（公開、免登入）
     api_path=/services/gamingDatabase/professional_player_account.php（分頁：page/limit，可 search/team_id）
欄位：player_name/positionID/team_short_name/game_nickname(帳號ID)/services_ide(kr/cn…)/area_name/game_rank
輸出：csv_cache/scoregg_accounts.json ＋ 與 scripts/soloq_accounts.json 的缺口比對報告
用法：python scripts\fetch_scoregg_accounts.py [--report-only]
"""
import io, sys, json, os, time, urllib.request, urllib.parse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
OUTJ = os.path.join(ROOT, "csv_cache", "scoregg_accounts.json")
ACCOUNTS = os.path.join(HERE, "soloq_accounts.json")


def api(path, **kw):
    d = {"api_path": path, "method": "post", "platform": "web", "api_version": "9.9.9", "language_id": 1}
    d.update(kw)
    req = urllib.request.Request("https://www.scoregg.com/services/api_url.php",
                                 data=urllib.parse.urlencode(d).encode(),
                                 headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0",
                                          "Referer": "https://www.scoregg.com/data_rank_player"})
    return json.loads(urllib.request.urlopen(req, timeout=25).read())


def fetch_all():
    teams = {}
    page = 1
    while page < 60:
        r = api("/services/gamingDatabase/professional_player_account.php",
                limit=20, team_id="", search="", page=page)
        data = r.get("data") or []
        if not data:
            break
        for t in data:
            key = t.get("short_name") or t.get("teamID")
            e = teams.setdefault(key, {"team": t.get("short_name"), "players": {}})
            for p in (t.get("player") or []):
                pl = e["players"].setdefault(p.get("player_name"), [])
                pl.append({"nickname": p.get("game_nickname"), "server": p.get("services_ide"),
                           "area": p.get("area_name"), "rank": p.get("c_game_rank"),
                           "pos": p.get("positionID")})
        print(f"  page {page}: 累計 {len(teams)} 隊")
        page += 1
        time.sleep(0.6)
    return teams


def main():
    if "--report-only" in sys.argv and os.path.exists(OUTJ):
        teams = json.load(open(OUTJ, encoding="utf-8"))
    else:
        teams = fetch_all()
        os.makedirs(os.path.dirname(OUTJ), exist_ok=True)
        json.dump(teams, open(OUTJ, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        nacc = sum(len(a) for t in teams.values() for a in t["players"].values())
        print(f"寫出 {OUTJ}：{len(teams)} 隊 / {sum(len(t['players']) for t in teams.values())} 選手 / {nacc} 帳號")
    # 缺口比對：scoregg 有記錄、但我們 soloq_accounts.json 沒有任何帳號的選手
    ours = set()
    try:
        for a in json.load(open(ACCOUNTS, encoding="utf-8")):
            ours.add(str(a.get("player", "")).strip().lower())
    except Exception:
        pass
    print("\n── 缺口（scoregg 有帳號紀錄、我們清單完全沒有的選手）──")
    n = 0
    for tk in sorted(teams):
        t = teams[tk]
        for pl, accs in sorted(t["players"].items()):
            if str(pl or "").strip().lower() not in ours:
                ids = "、".join(f"{a['nickname']}@{a['server']}" for a in accs if a.get("nickname"))
                if ids:
                    n += 1
                    print(f"  {t['team']} {pl}: {ids}")
    print(f"共 {n} 位缺口選手。（帳號暱稱無 #tagLine，補進清單前需用 dpm 搜尋確認完整 Riot ID）")


if __name__ == "__main__":
    main()
