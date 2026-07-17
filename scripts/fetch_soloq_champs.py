# -*- coding: utf-8 -*-
"""
抓各選手的「常用英雄池」（dpm best-champs）→ soloq_champs.js（給積分分頁顯示英雄池）。
一次呼叫/人：/v1/players/{dpmPuuid}/widgets/best-champs（回整段追蹤期每隻英雄的場數/勝場/KDA）。
用 Playwright 真瀏覽器 session 繞 dpm Cloudflare；不需要 Riot 金鑰。

用法：  python scripts\fetch_soloq_champs.py
需要 scripts\soloq_accounts.json 先由 fetch_soloq_accounts.py 產出（含 dpmPuuid）。
"""
import os, json, time
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
OUT = os.path.join(ROOT, "soloq_champs.js")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
TOPN = 12  # 每人最多留幾隻（依場數）

def main():
    with open(ACCOUNTS, "r", encoding="utf-8") as f:
        accounts = [a for a in json.load(f) if a.get("dpmPuuid") and a.get("riotId")]
    print(f"要抓 {len(accounts)} 位選手的英雄池…（一次呼叫/人，約 {len(accounts)*0.8/60:.1f} 分）")
    champs = {}
    with sync_playwright() as p:
        b = _launch_real(p)
        ctx = b.new_context(user_agent=UA, viewport={"width":1400,"height":900}, locale="en-US")
        pg = ctx.new_page()
        pg.goto("https://dpm.lol/", wait_until="domcontentloaded", timeout=60000)
        for _w in (3.5, 14, 25):  # Cloudflare 盤查自動重試（偶發互動式 Turnstile：多等幾輪通常自動放行）
            time.sleep(_w)
            try:
                if pg.evaluate("async()=>{const r=await fetch('/v1/esport/soloq/top-teams');return r.status;}") == 200: break
            except Exception: pass
        pg.wait_for_timeout(3500)
        ok = 0
        for i, a in enumerate(accounts, 1):
            try:
                arr = pg.evaluate("""async(pu)=>{
                  const r=await fetch('/v1/players/'+pu+'/widgets/best-champs');
                  if(!r.ok) return {err:r.status};
                  const j=await r.json(); const a=Array.isArray(j)?j:[];
                  return a.map(c=>({c:c.championName,g:c.gamesPlayed,w:c.win,
                    k:Math.round((c.kills||0)*10)/10,d:Math.round((c.deaths||0)*10)/10,as:Math.round((c.assists||0)*10)/10}))
                    .sort((x,y)=>y.g-x.g);
                }""", a["dpmPuuid"])
            except Exception as e:
                print(f"[{i}/{len(accounts)}] {a.get('player','?')}  錯誤 {e}"); continue
            if isinstance(arr, dict) and arr.get("err"):
                print(f"[{i}/{len(accounts)}] {a.get('player','?')}  API {arr['err']}"); continue
            top = (arr or [])[:TOPN]
            champs[a["riotId"]] = top
            ok += 1
            if i % 25 == 0 or i == len(accounts):
                print(f"[{i}/{len(accounts)}] 已抓 {ok}  例:{a.get('player','?')} {top[0]['c'] if top else '-'}")
            time.sleep(0.15)
        b.close()
    payload = {"fetched_at": time.strftime("%Y-%m-%d %H:%M"), "champs": champs}
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.SOLOQ_CHAMPS=" + json.dumps(payload, ensure_ascii=False) + ";\n")
    print(f"\n完成：{ok} 位有英雄池 → {OUT}")

if __name__ == "__main__":
    main()
