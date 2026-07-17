# -*- coding: utf-8 -*-
"""scoregg 缺口選手 → dpm 解析完整 Riot ID＋dpmPuuid → 併入 soloq_accounts.json
- 來源：csv_cache/scoregg_accounts.json（fetch_scoregg_accounts.py 產出）
- 只收「我們已追蹤戰隊」（soloq_accounts.json 既有 team 集合）的缺口選手；F/A 與未追蹤隊跳過
- dpm 搜尋端點執行時自動偵測（UI 打字攔截 → 記住樣板重放）
- 新帳號欄位：player/team/platform/riotId/dpmPuuid → 隔天每日更新自動補全年逐場＋牌位
用法：python scripts\merge_scoregg_gaps.py [--dry]（--dry 只列不寫）
      python scripts\merge_scoregg_gaps.py --player "TES|Tian"（既有選手補其 scoregg 帳號；逗號可多位。補完記得跑 fetch_soloq_year.py --only 重建該選手）
"""
import io, sys, json, os, time, re, urllib.parse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "csv_cache", "scoregg_accounts.json")
ACCOUNTS = os.path.join(HERE, "soloq_accounts.json")
DRY = "--dry" in sys.argv
def _arg(n, d=""):
    return sys.argv[sys.argv.index(n)+1] if n in sys.argv and sys.argv.index(n)+1 < len(sys.argv) else d
FORCE = {w.strip() for w in _arg("--player").split(",") if w.strip()}  # 「隊|選手」強制補帳號（略過已有/出賽過濾）
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def _launch_real(p):
    for kw in ({"channel": "chrome"}, {"channel": "msedge"}, {}):
        try:
            return p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"], **kw)
        except Exception:
            continue
    raise RuntimeError("找不到可用瀏覽器")


def _warm(pg):
    """過 Cloudflare 盤查：逐步加長等待，最多三輪；回 True=通"""
    for wait in (4, 14, 25):
        time.sleep(wait)
        try:
            st = pg.evaluate("async()=>{const r=await fetch('/v1/esport/soloq/top-teams');return r.status;}")
        except Exception:
            st = 0
        if st == 200:
            return True
        print(f"  盤查中（{st}），續等…")
    return False


def main():
    sg = json.load(open(SRC, encoding="utf-8"))
    acc = json.load(open(ACCOUNTS, encoding="utf-8"))
    ours_pl = {str(a.get("player", "")).strip().lower() for a in acc}
    ours_tm = {str(a.get("team", "")).strip().upper() for a in acc}
    ours_id = {(str(a.get("riotId", "")).lower(), str(a.get("platform", "")).lower()) for a in acc}
    # 只收「今年主資料真的出賽過」的選手——排除教練/退役掛名（scoregg 把 Dandy 掛在 HLE 之類）
    comp = set()
    try:
        d0 = open(os.path.join(ROOT, "data", "data_2026.js"), encoding="utf-8", errors="replace").read()
        J = json.loads(re.sub(r";\s*$", "", re.search(r"window\.LOL_DATA\s*=\s*(\{.*)", d0, re.S).group(1)))
        raw = J["tabs"]["RAW_DATA"]; hdr = raw[0]; C = {h: i for i, h in enumerate(hdr)}
        bi, ri = C.get("blue_playername"), C.get("red_playername")
        for r0 in raw[1:]:
            for i2 in (bi, ri):
                if i2 is not None and i2 < len(r0) and r0[i2]:
                    comp.add(str(r0[i2]).strip().lower())
    except Exception as e:
        print(f"（主資料選手名載入失敗，略過出賽過濾：{e}）")
    # 缺口：追蹤中的戰隊、我們完全沒有此選手
    todo = []
    for t in sg.values():
        tm = str(t.get("team", "")).strip().upper()
        if tm not in ours_tm:
            continue
        for pl, accs in t["players"].items():
            forced = f"{tm}|{pl}" in FORCE
            if FORCE and not forced:
                continue  # --player 模式：只處理指定選手
            if not forced and str(pl or "").strip().lower() in ours_pl:
                continue
            if not forced and comp and str(pl or "").strip().lower() not in comp:
                continue  # 今年沒出賽（教練/退役/掛名）
            for a in accs:
                if a.get("nickname") and a.get("server"):
                    todo.append({"team": tm, "player": pl, "nickname": a["nickname"], "server": a["server"]})
    if not todo:
        print("沒有可補的缺口。"); return
    print(f"待解析 {len(todo)} 個帳號（追蹤中戰隊的缺口選手）：")
    for x in todo: print(f"  {x['team']} {x['player']}: {x['nickname']}@{x['server']}")
    if DRY:
        return

    added, misses = [], []
    with sync_playwright() as p:
        b = _launch_real(p)
        pg = b.new_context(user_agent=UA, viewport={"width": 1400, "height": 900}, locale="en-US").new_page()
        pg.goto("https://dpm.lol/", wait_until="domcontentloaded", timeout=60000)
        if not _warm(pg):
            print("✗ Cloudflare 盤查未解（此 IP 暫時被掛旗）——稍後再跑本腳本即可。"); b.close(); return
        # ── 來源一：dpm esport（官方帳號紀錄，直接帶完整 Riot ID＋dpmPuuid）──
        JS_TEAM = """async(tc)=>{
          const r=await fetch('/v1/esport/soloq/match-history?team='+encodeURIComponent(tc));
          if(!r.ok) return {err:r.status};
          const j=await r.json(); const seen={}; const out=[];
          for(const m of (j.matches||[])){ const plat=m.platformId||'';
            for(const pp of (m.participants||[])){
              if(pp.role==='PRO' && pp.team===tc && pp.gameName && pp.tagLine){
                const rid=pp.gameName+'#'+pp.tagLine;
                if(!seen[rid]){ seen[rid]=1; out.push({player:pp.displayName||pp.gameName,
                  platform:(pp.platformId||plat||'').toLowerCase(), riotId:rid, puuid:pp.puuid||null}); }
              } } }
          return {players:out}; }"""
        gap_by_team = {}
        for x in todo: gap_by_team.setdefault(x["team"], set()).add(str(x["player"]).strip().lower())
        try:
            tt = pg.evaluate("async()=>{const r=await fetch('/v1/esport/soloq/top-teams');return r.ok?await r.json():[];}")
        except Exception:
            tt = []
        dpm_codes = [t2.get("team") for t2 in (tt or []) if t2.get("team")]
        up = {c.upper(): c for c in dpm_codes}
        ALIAS2 = {"TL": "TLAW"}  # 儀表板縮寫→dpm 代碼手動修正（同 fetch_soloq_accounts）
        resolved_pl = set()
        for tm, plset in sorted(gap_by_team.items()):
            code = ALIAS2.get(tm) if ALIAS2.get(tm) in dpm_codes else up.get(tm)
            if not code:
                cands = sorted([c for c in dpm_codes if c.upper().startswith(tm)], key=lambda c: ("." in c, len(c)))
                code = cands[0] if cands else None
            if not code: continue
            try: data = pg.evaluate(JS_TEAM, code)
            except Exception: continue
            for r2 in (data or {}).get("players", []):
                pl = str(r2.get("player") or "").strip()
                if pl.lower() not in plset: continue
                rid = r2["riotId"]; k2 = (rid.lower(), str(r2.get("platform") or "kr").lower())
                if k2 in ours_id: continue  # 已有（含 bad 墓碑：張冠李戴帳號不會被加回）
                added.append({"player": pl, "team": tm, "platform": r2.get("platform") or "kr",
                              "riotId": rid, "dpmPuuid": r2.get("puuid")})
                ours_id.add(k2); resolved_pl.add((tm, pl.lower()))
                print(f"  ✚[dpm] {tm} {pl}: {rid}")
            time.sleep(0.5)
        todo = [x for x in todo if (x["team"], str(x["player"]).strip().lower()) not in resolved_pl]
        print(f"dpm esport 解析後，剩 {len(todo)} 個帳號走 scoregg 暱稱解析…")
        if not todo:
            b.close()
            if added:
                acc.extend(added)
                json.dump(acc, open(ACCOUNTS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
                print(f"\n✚ 已寫入 {len(added)} 個新帳號 → soloq_accounts.json")
            return
        # ── 來源二：scoregg 暱稱 → dpm 搜尋解析 ──
        # 端點偵測：UI 打字攔截 /v1 搜尋請求 → 記住樣板
        tmpl = {"u": None}
        def on_resp(r):
            u = r.url
            if "/v1/" in u and r.request.resource_type in ("xhr", "fetch") and "__PROBE__" in u:
                tmpl["u"] = u
        pg.on("response", on_resp)
        inp = pg.query_selector("input:not([type=hidden])")
        if inp:
            try:
                inp.click(); inp.fill(""); inp.type("__PROBE__", delay=70); time.sleep(3)
            except Exception:
                pass
        if not tmpl["u"]:
            # 備援：常見候選路徑逐一試
            cand = pg.evaluate("""async()=>{const outs=[];
              for(const u of ['/v1/search?gameName=__PROBE__','/v1/players/search?gameName=__PROBE__',
                              '/v1/search/players?query=__PROBE__','/v1/players/autocomplete?query=__PROBE__']){
                try{const r=await fetch(u); if(r.status!==404){outs.push([u,r.status]);}}catch(e){}}
              return outs;}""")
            ok = [u for u, st in cand if st == 200]
            if ok: tmpl["u"] = "https://dpm.lol" + ok[0]
        if not tmpl["u"]:
            print("✗ 找不到 dpm 搜尋端點（UI 攔截與候選路徑都落空）。"); b.close(); return
        print(f"搜尋端點樣板：{tmpl['u']}")
        JSQ = """async(u)=>{try{const r=await fetch(u); if(!r.ok)return {st:r.status};
          return {st:200, j:await r.json()};}catch(e){return {err:String(e).slice(0,80)}}}"""
        # 端點參數格式不只一種（曾遇 __PROBE__ 過但真名 422）：多格式輪試、記住可用格式
        # 2026-07 實測正解＝/v1/search?gameName=（422 錯誤體自曝「property query should not exist」）→ 固定排最前
        FORMATS = ["/v1/search?gameName=__PROBE__",
                   tmpl["u"].replace("https://dpm.lol", ""),
                   "/v1/players/search?gameName=__PROBE__",
                   "/v1/search/players?query=__PROBE__",
                   "/v1/players?search=__PROBE__"]
        good = {"f": None}
        def query(nick):
            enc = urllib.parse.quote(nick, safe="")
            fmts = [good["f"]] + [f for f in FORMATS if f != good["f"]] if good["f"] else FORMATS
            last = {"st": 0}
            for f in fmts:
                if not f: continue
                last = pg.evaluate(JSQ, f.replace("__PROBE__", enc))
                if last.get("st") == 200:
                    good["f"] = f; return last
            return last
        def pick_arr(j):
            if isinstance(j, list): return j
            for k in ("players", "data", "results", "items"):
                v = j.get(k)
                if isinstance(v, list):
                    return [ (e.get("player") if isinstance(e, dict) and isinstance(e.get("player"), dict) else e) for e in v ]
            return []
        for x in todo:
            r = query(x["nickname"])
            hit = None
            if r.get("st") == 200:
                arr = pick_arr(r["j"])
                for c in arr:
                    gn = str(c.get("gameName", "")).strip().lower()
                    plat = str(c.get("platformId") or c.get("platform") or "").lower()  # None→空（未知伺服器不擋）
                    if gn == x["nickname"].strip().lower() and (not plat or x["server"] in plat):
                        hit = c; break
                if not hit:
                    # 名稱不合（暱稱過期）→ 只收 dpm 標記為「該選手本人」的結果；嚴禁盲收第一筆（張冠李戴判例）
                    pl_lo = str(x["player"]).strip().lower()
                    for c in arr:
                        dn = str(c.get("displayName") or "").strip().lower()
                        en = str(c.get("esportName") or "").split(" (")[0].strip().lower()
                        if pl_lo and (dn == pl_lo or en == pl_lo):
                            hit = c; break
            if hit and hit.get("gameName") and hit.get("tagLine") and hit.get("puuid"):
                rid = f'{hit["gameName"]}#{hit["tagLine"]}'
                k = (rid.lower(), x["server"].lower())
                if k in ours_id:
                    print(f"  ＝ {x['team']} {x['player']} {rid} 已在清單"); continue
                added.append({"player": x["player"], "team": x["team"], "platform": x["server"],
                              "riotId": rid, "dpmPuuid": hit["puuid"]})
                ours_id.add(k)
                print(f"  ✚ {x['team']} {x['player']}: {x['nickname']} → {rid}")
            else:
                misses.append(x)
                print(f"  ？ {x['team']} {x['player']}: {x['nickname']} 解析不到（{r}）")
            time.sleep(0.4)
        # ── 來源三：選手名反查（該選手所有暱稱都過期時）──
        # dpm 搜尋結果帶 displayName＝官方選手掛牌；用選手名查、只收「displayName＝本人且隊伍相符」（同名選手防呆）
        got = {(a["team"], str(a["player"]).strip().lower()) for a in added}
        left = {}
        for x in misses:
            k3 = (x["team"], str(x["player"]).strip().lower())
            if k3 not in got: left.setdefault(k3, x)
        for (tm, pl_lo), x in sorted(left.items()):
            r = query(str(x["player"]).strip())
            if r.get("st") != 200: continue
            code = ALIAS2.get(tm) if ALIAS2.get(tm) in dpm_codes else up.get(tm.upper())
            hits = 0
            for c in pick_arr(r["j"]):
                dn = str(c.get("displayName") or "").strip().lower()
                if dn != pl_lo or not (c.get("gameName") and c.get("tagLine") and c.get("puuid")): continue
                if str(c.get("team") or "").upper() not in {str(code or "").upper(), tm.upper()}: continue
                rid = f'{c["gameName"]}#{c["tagLine"]}'
                plat = str(c.get("platform") or x.get("server") or "kr").lower()
                k = (rid.lower(), plat)
                if (rid.lower(), str(x.get("server", "")).lower()) in ours_id or k in ours_id: continue
                added.append({"player": x["player"], "team": tm, "platform": plat,
                              "riotId": rid, "dpmPuuid": c["puuid"]})
                ours_id.add(k); hits += 1
                print(f"  ✚[名反查] {tm} {x['player']}: {rid}（{c.get('platform')}）")
            if hits: misses = [m for m in misses if (m["team"], str(m["player"]).strip().lower()) != (tm, pl_lo)]
            time.sleep(0.4)
        b.close()
    if added:
        acc.extend(added)
        json.dump(acc, open(ACCOUNTS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\n✚ 已寫入 {len(added)} 個新帳號 → soloq_accounts.json（隔天每日更新自動補全年＋牌位；想立刻要就按「添加API」重抓牌位＋跑 fetch_soloq_year.py --missing）")
    if misses:
        print(f"？ {len(misses)} 個解析不到（改名/非公開），已略過。")


if __name__ == "__main__":
    main()
