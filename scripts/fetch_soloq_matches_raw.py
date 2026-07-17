# -*- coding: utf-8 -*-
"""
抓各選手「未裁的整包逐場 JSON」→ soloq_matches_raw.json（離線分析用，不進儀表板）。
和 fetch_soloq_matches.py 同樣邏輯(偵測主路→只抓那路 Solo/Duo，每人≤cap 場)，
但把 dpm 回傳的「整個 match 物件」原封不動存下來(gameId/gameCreation/gameDuration/queueId/
platformId + participants[該選手全欄位])，不壓短鍵、不丟欄位。
注意：dpm 逐場只含「該選手一人」(participants 長度=1)；真正 10 人整場要走 Riot match-v5(需金鑰)，
      matchId＝platformId+"_"+gameId(如 KR_8294576001)。此檔已存 gameId/platformId，日後要升級 Riot 版可直接用。

用法：  python scripts\fetch_soloq_matches_raw.py            (每人≤30場、≤8頁)
        python scripts\fetch_soloq_matches_raw.py --cap 50 --pages 12
需要 scripts\soloq_accounts.json(含 dpmPuuid)。不需 Riot 金鑰。
"""
import os, json, sys, time
from playwright.sync_api import sync_playwright

def _launch_real(p):
    """dpm Cloudflare 對策：真 Chrome/Edge 通道才過 API 挑戰（2026-07 起內建 chromium 一律 403）"""
    for kw in ({"channel": "chrome"}, {"channel": "msedge"}, {}):
        try:
            return p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"], **kw)
        except Exception:
            continue
    raise RuntimeError("找不到可用瀏覽器")

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
ACCOUNTS = os.path.join(HERE, "soloq_accounts.json")
OUT = os.path.join(ROOT, "soloq_matches_raw.json")   # 大檔(~30-50MB)、不進 .gitignore 白名單、不載入儀表板
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

def arg(name, d=None):
    return sys.argv[sys.argv.index(name)+1] if name in sys.argv and sys.argv.index(name)+1 < len(sys.argv) else d
CAP   = int(arg("--cap")   or 30)
PAGES = int(arg("--pages") or 8)

# 偵測主路(page1 眾數)→ 只抓主路 Solo/Duo，回傳「整個 match 物件」不裁
JS = """async(args)=>{
  const [PU, cap, pages] = args;
  const TOK={TOP:'top',JUNGLE:'jungle',MIDDLE:'middle',BOTTOM:'bottom',UTILITY:'utility'};
  let det; try{ det=await fetch(`/v1/players/${PU}/match-history?size=15&page=1`); }catch(e){ return {main:null,matches:[]}; }
  if(!det.ok) return {main:null,matches:[]};
  const dj=await det.json(); const lc={};
  for(const m of (dj.matches||[])){ if(m.queueId!==420) continue; const p=(m.participants||[])[0]; if(p&&p.lane) lc[p.lane]=(lc[p.lane]||0)+1; }
  let main=null,best=-1; for(const k in lc){ if(lc[k]>best){best=lc[k];main=k;} }
  if(!main){ for(const m of (dj.matches||[])){ const p=(m.participants||[])[0]; if(p&&p.lane) lc[p.lane]=(lc[p.lane]||0)+1; } for(const k in lc){ if(lc[k]>best){best=lc[k];main=k;} } }
  if(!main) return {main:null,matches:[]};
  const tok=TOK[main]||'middle';
  const out=[];
  for(let pg=1; pg<=pages && out.length<cap; pg++){
    let r; try{ r=await fetch(`/v1/players/${PU}/match-history?size=15&page=${pg}&lane=${tok}`); }catch(e){ break; }
    if(!r.ok) break; const j=await r.json(); const ms=j.matches||[]; if(!ms.length) break;
    for(const m of ms){ if(m.queueId!==420) continue; out.push(m); if(out.length>=cap) break; }
  }
  return {main, matches:out};
}"""

def main():
    with open(ACCOUNTS, "r", encoding="utf-8") as f:
        accounts = [a for a in json.load(f) if a.get("dpmPuuid") and a.get("riotId")]
    print(f"要抓 {len(accounts)} 位選手整包逐場（每人≤{CAP}場主路 Solo/Duo、不裁欄位）…約 {len(accounts)*2/60:.0f}-{len(accounts)*4/60:.0f} 分")
    players = {}; tot = 0
    with sync_playwright() as p:
        b = _launch_real(p)
        pg = b.new_context(user_agent=UA, viewport={"width":1400,"height":900}, locale="en-US").new_page()
        pg.goto("https://dpm.lol/", wait_until="domcontentloaded", timeout=60000)
        for _w in (3.5, 14, 25):  # Cloudflare 盤查自動重試（偶發互動式 Turnstile：多等幾輪通常自動放行）
            time.sleep(_w)
            try:
                if pg.evaluate("async()=>{const r=await fetch('/v1/esport/soloq/top-teams');return r.status;}") == 200: break
            except Exception: pass
        time.sleep(3.5)
        ok = 0
        for i, a in enumerate(accounts, 1):
            try:
                res = pg.evaluate(JS, [a["dpmPuuid"], CAP, PAGES])
            except Exception as e:
                print(f"[{i}/{len(accounts)}] {a.get('player','?')}  錯誤 {e}"); continue
            ms = (res or {}).get("matches") or []; main = (res or {}).get("main")
            if ms:
                players[a["riotId"]] = {"player": a.get("player"), "team": a.get("team"),
                                       "platform": a.get("platform"), "main": main, "matches": ms}
                ok += 1; tot += len(ms)
            if i % 20 == 0 or i == len(accounts):
                print(f"[{i}/{len(accounts)}] 有戰績 {ok} 人 / 累計 {tot} 場  例:{a.get('player','?')} {main or '?'} {len(ms)}場")
            time.sleep(0.1)
        b.close()
    payload = {"fetched_at": time.strftime("%Y-%m-%d %H:%M"), "cap": CAP,
               "source": "dpm /v1/players/{dpmPuuid}/match-history (per-player, main lane, queue 420, untrimmed)",
               "note": "participants 只含該選手一人；10 人整場需 Riot match-v5，matchId=platformId+'_'+gameId",
               "players": players}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)   # 緊湊(不 indent)省空間
    sz = os.path.getsize(OUT)/1024/1024
    print(f"\n完成：{ok} 位 / {tot} 場 → {OUT}（{sz:.1f} MB）")

if __name__ == "__main__":
    main()
