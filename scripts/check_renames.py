# -*- coding: utf-8 -*-
"""
用 PUUID(永久不變的 UID) 找出改了 Riot ID 的選手。
讀 soloq.js 各帳號的 puuid → 打 Riot account-v1 by-puuid 查「目前」Riot ID → 跟當初記錄比對，列出改名的。
（PUUID 改不了，所以就算選手把 gameName#tagLine 改掉，也能靠 puuid 找到新名字。）

用法： $env:RIOT_API_KEY="RGAPI-..."; python scripts\check_renames.py
需要 soloq.js 先由 fetch_soloq.py 產出(含 puuid 欄位)。
"""
import os, sys, json, re, time, collections, urllib.parse, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SOLOQ = os.path.join(ROOT, "soloq.js")
KEY = os.environ.get("RIOT_API_KEY", "").strip()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
CLUSTER = {"na1":"americas","br1":"americas","la1":"americas","la2":"americas","oc1":"americas",
           "euw1":"europe","eun1":"europe","tr1":"europe","ru":"europe",
           "kr":"asia","jp1":"asia","sg2":"asia","ph2":"asia","th2":"asia","tw2":"asia","vn2":"asia"}
if not KEY:
    print('需要 RIOT_API_KEY： $env:RIOT_API_KEY="RGAPI-..."; python scripts\\check_renames.py'); sys.exit(1)

_t = collections.deque()
def get(url):
    now = time.time()
    while _t and now - _t[0] > 120: _t.popleft()
    if len(_t) >= 100: time.sleep(120 - (now - _t[0]) + 0.1)
    if len([x for x in _t if time.time()-x < 1]) >= 18: time.sleep(1.0)
    req = urllib.request.Request(url, headers={"X-Riot-Token": KEY, "User-Agent": UA})
    _t.append(time.time())
    try:
        with urllib.request.urlopen(req, timeout=15) as r: return r.getcode(), json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 429: time.sleep(int(e.headers.get("Retry-After","5"))+1); return get(url)
        return e.code, None
    except Exception: return 0, None

def main():
    txt = open(SOLOQ, encoding="utf-8").read()
    m = re.search(r"window\.SOLOQ_DATA\s*=\s*(\{.*\})\s*;?\s*$", txt, re.S)
    if not m: print("讀不到 soloq.js（請先跑 fetch_soloq.py）"); sys.exit(1)
    players = [p for p in json.loads(m.group(1)).get("players", []) if p.get("puuid")]
    print(f"用 PUUID 檢查 {len(players)} 個帳號目前的 Riot ID…")
    renamed, gone = [], []
    for i, p in enumerate(players, 1):
        cluster = CLUSTER.get(p.get("platform"), "asia")
        code, acc = get(f"https://{cluster}.api.riotgames.com/riot/account/v1/accounts/by-puuid/{p['puuid']}")
        if code == 200 and acc:
            cur = f"{acc.get('gameName','')}#{acc.get('tagLine','')}"
            old = p.get("riotId")
            if cur != old:
                renamed.append((p, old, cur)); print(f"  改名：{p['team']} {p['player']}　{old} → {cur}")
        elif code == 404:
            gone.append(p); print(f"  查無：{p['team']} {p['player']}（puuid 失效？）")
    print(f"\n完成：{len(renamed)} 個改名、{len(gone)} 個查無。")
    if renamed:
        print("改名清單：")
        for p, old, cur in renamed: print(f"  {p['team']} {p['player']}: {old} → {cur}")

if __name__ == "__main__":
    main()
