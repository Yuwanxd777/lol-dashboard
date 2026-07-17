# -*- coding: utf-8 -*-
"""
從 dpm.lol 自動抓「各隊選手 solo queue 帳號」→ scripts/soloq_accounts.json（給 fetch_soloq.py）。
dpm.lol 有 Cloudflare，用 Playwright 真瀏覽器的 session 直接打 dpm 內部 API 繞過。

資料來源：
  /v1/esport/soloq/top-teams                 各隊(依 soloq LP 排序)
  /v1/esport/soloq/match-history?team=XXX     該隊比賽；participant 中 role=PRO 且 team=XXX ＝該隊選手帳號

用法：  python scripts\fetch_soloq_accounts.py            (預設抓 soloq LP 前 40 隊)
        python scripts\fetch_soloq_accounts.py --max 80
        python scripts\fetch_soloq_accounts.py --teams T1,GENG,BLG,HLE,KT   (只抓指定隊，用 dpm 隊代碼)
不需要 Riot 金鑰（這支只抓帳號；抓積分是 fetch_soloq.py）。
"""
import os, json, sys, re
from playwright.sync_api import sync_playwright

def _launch_real(p):
    """dpm Cloudflare 對策：真 Chrome/Edge 通道才過 API 挑戰（2026-07 起內建 chromium 一律 403）"""
    for kw in ({"channel": "chrome"}, {"channel": "msedge"}, {}):
        try:
            return p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"], **kw)
        except Exception:
            continue
    raise RuntimeError("找不到可用瀏覽器")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "soloq_accounts.json")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

def arg(name, d=None):
    return sys.argv[sys.argv.index(name)+1] if name in sys.argv and sys.argv.index(name)+1 < len(sys.argv) else d

WANT = [s.strip() for s in (arg("--teams") or "").split(",") if s.strip()]
MAXT = int(arg("--max") or 40)
# 儀表板縮寫 → dpm 代碼的手動修正（自動對應(開頭相符)會抓錯的隊，在這裡指定正解）
ALIAS = {"TL": "TLAW"}

def main():
    accounts, seen, per_player = [], set(), {}
    with sync_playwright() as p:
        b = _launch_real(p)
        ctx = b.new_context(user_agent=UA, viewport={"width":1500,"height":950}, locale="en-US")
        pg = ctx.new_page()
        print("開啟 dpm.lol …")
        pg.goto("https://dpm.lol/esport/soloq", wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(4000)

        tt = pg.evaluate("async()=>{const r=await fetch('/v1/esport/soloq/top-teams');return await r.json();}")
        dpm_codes = [t.get("team") for t in (tt or []) if t.get("team")]
        if WANT:
            # 把要抓的隊代碼(可能是儀表板縮寫)對應到 dpm 代碼：完全相同優先，否則取開頭相符(偏好無點、較短，如 GEN→GENG)
            up = {c.upper(): c for c in dpm_codes}
            teams, unmatched = [], []
            for w in WANT:
                wu = w.upper()
                if wu in ALIAS and ALIAS[wu] in dpm_codes:
                    teams.append(ALIAS[wu]); print(f"  對應(手動)：{w} → {ALIAS[wu]}"); continue
                if wu in up:
                    teams.append(up[wu]); continue
                cands = sorted([c for c in dpm_codes if c.upper().startswith(wu)], key=lambda c: ("." in c, len(c)))
                if cands:
                    teams.append(cands[0]); print(f"  對應：{w} → {cands[0]}")
                else:
                    unmatched.append(w)
            teams = list(dict.fromkeys(teams))  # 去重
            if unmatched: print(f"  ⚠ dpm 找不到、跳過：{', '.join(unmatched)}")
        else:
            teams = dpm_codes[:MAXT]
        print(f"要抓 {len(teams)} 隊…（各隊打一次 dpm API，約 {len(teams)*1.5/60:.1f} 分）")

        for i, tc in enumerate(teams, 1):
            try:
                data = pg.evaluate("""async(tc)=>{
                  const r=await fetch('/v1/esport/soloq/match-history?team='+encodeURIComponent(tc));
                  if(!r.ok) return {err:r.status};
                  const j=await r.json(); const seen={}; const out=[];
                  for(const m of (j.matches||[])){ const plat=m.platformId||'';
                    for(const pp of (m.participants||[])){
                      if(pp.role==='PRO' && pp.team===tc && pp.gameName && pp.tagLine){
                        const rid=pp.gameName+'#'+pp.tagLine;
                        if(!seen[rid]){ seen[rid]=1; out.push({player:pp.displayName||pp.gameName, team:pp.team,
                          platform:(pp.platformId||plat||'').toLowerCase(), riotId:rid, puuid:pp.puuid||null,
                          tier:pp.tier||null, lp:(pp.lp!=null?pp.lp:pp.leaguePoints)}); }
                      }
                    } }
                  return {players:out};
                }""", tc)
            except Exception as e:
                print(f"[{i}/{len(teams)}] {tc}  錯誤：{e}"); continue
            if not data or data.get("err"):
                print(f"[{i}/{len(teams)}] {tc}  API {data.get('err') if data else '?'}"); continue
            add = 0
            for r in data.get("players", []):
                k = r["riotId"].lower()
                if k in seen: continue
                pk = (r["team"], r["player"])
                if per_player.get(pk, 0) >= 3: continue      # 每位選手最多 3 個帳號
                seen.add(k); per_player[pk] = per_player.get(pk, 0) + 1
                accounts.append({"player": r["player"], "team": r["team"],
                                 "platform": r["platform"] or "kr", "riotId": r["riotId"],
                                 "dpmPuuid": r.get("puuid")})  # dpm 內部 puuid：給 best-champs / rank-history 用
                add += 1
            print(f"[{i}/{len(teams)}] {tc}  +{add}（累計 {len(accounts)}）"
                  + (f"  例:{data['players'][0]['player']} {data['players'][0].get('tier') or ''}" if data.get("players") else ""))
        b.close()

    # 合併保留：不整檔覆寫——保住 bad 墓碑、手動加的帳號與其他隊；同 riotId 以既有為準
    old = []
    if os.path.exists(OUT):
        try: old = json.load(open(OUT, encoding="utf-8"))
        except Exception: old = []
    have = {(str(a.get("riotId","")).lower(), str(a.get("platform","")).lower()) for a in old}
    newn = 0
    for r in accounts:
        k = (str(r.get("riotId","")).lower(), str(r.get("platform","")).lower())
        if k in have: continue
        old.append(r); have.add(k); newn += 1
    old.sort(key=lambda r: (r.get("team") or "", r.get("player") or ""))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(old, f, ensure_ascii=False, indent=1)
    print(f"\n完成：新增 {newn} 個帳號（合併保留既有 {len(old)-newn} 筆）→ {OUT}")
    print('下一步（抓積分）：  $env:RIOT_API_KEY="RGAPI-..."; python scripts\\fetch_soloq.py')

if __name__ == "__main__":
    main()
