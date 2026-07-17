# -*- coding: utf-8 -*-
"""
逐場「增量」更新（給每日排程用）：不重抓全年，只補新戰績。
對每位已在 soloq_match_index.js 的選手：讀現有 soloq_matches/pN.js → 往回抓 dpm，
抓到「已存在的最新一場(newestT)」就停 → 把新的幾場 prepend 進去、重寫該檔＋index。
角色用 index 已存的(不重測 5 路)。只 queue 420。純 dpm、免 Riot 金鑰。約 3-5 分。
新加入、還沒有檔的選手會略過(需跑 fetch_soloq_year.py 補全)。

用法：  python scripts\fetch_soloq_update.py            (增量更新全部)
        python scripts\fetch_soloq_update.py --max 3    (測試)
"""
import os, json, re, sys, time
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
IDXP = os.path.join(ROOT, "soloq_match_index.js")
OUTDIR = os.path.join(ROOT, "soloq_matches")
ACCOUNTS = os.path.join(HERE, "soloq_accounts.json")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
LANE2TOK = {"TOP":"top","JUNGLE":"jungle","MIDDLE":"middle","BOTTOM":"bottom","UTILITY":"utility"}

def comp_roles():
    """主資料選手→比賽位置 token（判例 2026-07-16：資料庫位置＝權威；積分主路不符＝帳號 100% 找錯）"""
    import re as _re
    P2TOK = {1: "top", 2: "jungle", 3: "middle", 4: "bottom", 5: "utility"}
    m = {}
    try:
        d0 = open(os.path.join(ROOT, "data", "data_2026.js"), encoding="utf-8", errors="replace").read()
        J = json.loads(_re.sub(r";\s*$", "", _re.search(r"window\.LOL_DATA\s*=\s*(\{.*)", d0, _re.S).group(1)))
        raw = J["tabs"]["RAW_DATA"]; hdr = raw[0]; C = {h: i for i, h in enumerate(hdr)}
        bi, ri, pi = C.get("blue_playername"), C.get("red_playername"), C.get("participantid")
        cnt = {}
        for r0 in raw[1:]:
            try: pid = int(r0[pi])
            except Exception: continue
            if not (1 <= pid <= 5): continue
            for i2 in (bi, ri):
                if i2 is not None and i2 < len(r0) and r0[i2]:
                    k = str(r0[i2]).strip().lower()
                    cnt.setdefault(k, {}).setdefault(pid, 0); cnt[k][pid] += 1
        for k, v in cnt.items():
            m[k] = P2TOK[max(v, key=v.get)]
    except Exception as e:
        print(f"（主資料位置載入失敗：{e}——退回積分主路判定）")
    return m

def arg(n,d=None): return sys.argv[sys.argv.index(n)+1] if n in sys.argv and sys.argv.index(n)+1<len(sys.argv) else d
MAXP = int(arg("--max") or 0)

JS_NEW = """async(args)=>{ const [PU,tok,newestT]=args; const out=[]; let ID=null;
  for(let pg=1; pg<=20; pg++){
    let r; try{ r=await fetch(`/v1/players/${PU}/match-history?size=15&page=${pg}&lane=${tok}`);}catch(e){break;}
    if(!r.ok) break; const j=await r.json(); const ms=j.matches||[]; if(!ms.length) break; let stop=false;
    if(pg===1&&ms[0]&&ms[0].participants&&ms[0].participants[0]){const q0=ms[0].participants[0]; ID={g:q0.gameName||null,t:q0.tagLine||null};} // 最近一場的當前 Riot ID：改名偵測
    for(const m of ms){ if((m.gameCreation||0) <= newestT){ stop=true; break; }   // 追到已存在的最新一場就停
      if(m.queueId!==420) continue; if((m.gameDuration||0)<600) continue; const p=(m.participants||[])[0]; if(!p) continue;
      const buy=(p.itemActions||[]).filter(a=>a.action==='purchase').map(a=>[Math.round((a.timestamp||0)/1000),a.id]);
      out.push({ t:m.gameCreation,d:m.gameDuration,c:p.championName,o:p.opponentChampionName||p.duoOpponentChampionName||null,
        w:!!p.win,k:p.kills,de:p.deaths,a:p.assists,kp:Math.round(p.killParticipation||0),sc:p.dpmScore,scr:p.dpmScoreRank,
        pos:p.lane||null, su:[p.summoner1Id,p.summoner2Id], r:p.primaryRuneId,
        rp:[p.primaryRuneId,p.primaryRuneId2,p.primaryRuneId3,p.primaryRuneId4], rs:[p.secondaryRuneId,p.secondaryRuneId2,p.secondaryRuneId3], rst:[p.perksStat1,p.perksStat2,p.perksStat3],
        sk:(p.skillLevelUps||[]).slice(0,5),
        it:(p.itemIds||[]).filter(id=>[1104,3330,3340,3348,3349,3363,3364,3513,6702].indexOf(id)<0), st:p.startItems||[], ib:buy, cs:(p.totalMinionsKilled||0)+(p.neutralMinionsKilled||0),
        gd15:p.goldDiffAt15, dpm:p.damagePerMinute, tr:p.tier||null, lp:(p.lp!=null?p.lp:p.leaguePoints),
        // Laning Phase(at 15) 追加（與 fetch_soloq_year.py 同步）：xp diff＋first to level 2；cs diff 不抓（使用者指定）
        xd15:p.xpDiffAt15,
        fl2:(p.isFirstToHitLevel2!=null?(p.isFirstToHitLevel2?1:0):null) });
    }
    if(stop) break;
  }
  return {id:ID, ms:out}; }"""

def read_js_obj(path, prefix):
    s = open(path, encoding="utf-8").read().strip()
    s = s[s.index("=")+1:].rstrip(); s = s[:-1] if s.endswith(";") else s
    return json.loads(s)

def load_player_file(f):
    txt = open(os.path.join(OUTDIR, f), encoding="utf-8").read()
    m = re.match(r'window\.__sqLoad\((.*)\);\s*$', txt, re.S)
    key, data = json.loads('['+m.group(1)+']'); return key, data

def _load_accs():
    accs = {}
    for a in json.load(open(ACCOUNTS, encoding="utf-8")):
        if a.get("bad"): continue  # 判例：張冠李戴帳號永久跳過
        if a.get("dpmPuuid"): accs.setdefault(f'{a.get("team","")}|{a.get("player","")}', []).append(a)
    return accs

def fill_missing_puuids(pg, cap=10):
    """手動加的帳號只需 riotId：用 dpm 選手頁反查 dpmPuuid 自動補齊（不靠搜尋端點，同一 warmed session 不觸發盤查）"""
    import urllib.parse as _up
    raw = json.load(open(ACCOUNTS, encoding="utf-8"))
    todo = [a for a in raw if not a.get("bad") and not a.get("dpmPuuid")
            and a.get("riotId") and "#" in a.get("riotId", "")][:cap]
    if not todo:
        return 0
    print(f"♻ {len(todo)} 個帳號缺 dpmPuuid（手動新增）→ dpm 選手頁反查…")
    got = {}
    hit = {"u": None}
    pg.on("request", lambda r: hit.__setitem__("u", r.url) if re.search(r"/v1/players/[A-Za-z0-9_-]{20,}", r.url) else None)
    for a in todo:
        g, tl = a["riotId"].rsplit("#", 1)
        hit["u"] = None
        try:
            pg.goto(f"https://dpm.lol/{_up.quote(g)}-{_up.quote(tl)}", wait_until="domcontentloaded", timeout=30000)
            for _ in range(16):
                if hit["u"]: break
                time.sleep(0.5)
        except Exception:
            pass
        m = re.search(r"/v1/players/([A-Za-z0-9_-]{20,})", hit["u"] or "")
        if m:
            got[(a.get("riotId"), a.get("platform"))] = m.group(1)
            print(f"   ♻ {a.get('team')} {a.get('player')} {a['riotId']} → puuid OK")
        else:
            print(f"   ？ {a.get('team')} {a.get('player')} {a['riotId']} 反查不到（ID 打錯或 dpm 沒收錄）")
    if got:
        for a in raw:
            k = (a.get("riotId"), a.get("platform"))
            if k in got and not a.get("dpmPuuid"):
                a["dpmPuuid"] = got[k]
        json.dump(raw, open(ACCOUNTS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"♻ 已補 {len(got)} 個 dpmPuuid → soloq_accounts.json")
    return len(got)

def main():
    if not os.path.exists(IDXP):
        print("找不到 soloq_match_index.js，請先跑 fetch_soloq_year.py。"); return
    idx = read_js_obj(IDXP, "SOLOQ_MATCH_IDX")
    accs = _load_accs()
    keys = list(idx["players"].keys());  keys = keys[:MAXP] if MAXP else keys
    print(f"增量更新 {len(keys)} 位選手（只抓比現有最新更新的 Solo/Duo）…")
    CROLE = comp_roles()  # 判例：資料庫位置＝權威；index 路線不符 → 蒐集、最後自動用 --only 重建
    MISMATCH = []
    added_tot = 0; upd = 0; RENAME = {}
    with sync_playwright() as p:
        b = _launch_real(p)
        pg = b.new_context(user_agent=UA, viewport={"width":1400,"height":900}, locale="en-US").new_page()
        pg.goto("https://dpm.lol/", wait_until="domcontentloaded", timeout=60000)
        for _w in (3.5, 14, 25):  # Cloudflare 盤查自動重試（偶發互動式 Turnstile：多等幾輪通常自動放行）
            time.sleep(_w)
            try:
                if pg.evaluate("async()=>{const r=await fetch('/v1/esport/soloq/top-teams');return r.status;}") == 200: break
            except Exception: pass
        if fill_missing_puuids(pg):
            accs = _load_accs()  # 補完 puuid 立即生效：新帳號本輪就進增量/補全年
        for i, key in enumerate(keys, 1):
            meta = idx["players"][key]; role = meta.get("role")
            tok = LANE2TOK.get(role, "middle")
            _comp = CROLE.get(str(key.split("|", 1)[-1]).strip().lower())
            if _comp and _comp != tok:
                MISMATCH.append(key)  # 資料庫位置≠積分檔路線：帳號找錯或缺主帳，最後統一重建
            try: _, data = load_player_file(meta["f"])
            except Exception as e: print(f"[{i}/{len(keys)}] {key} 讀檔錯 {e}"); continue
            existing = data.get("matches", []); newestT = existing[0]["t"] if existing else 0
            newg = []
            for a in accs.get(key, []):
                try:
                    res = pg.evaluate(JS_NEW, [a["dpmPuuid"], tok, newestT])
                    if isinstance(res, dict):
                        newg.extend(res.get("ms") or [])
                        idn = res.get("id") or {}
                        if idn.get("g") and idn.get("t"):  # dpm 最近一場的當前 ID ≠ 清單 ID → 改名，記下待同步
                            cur = f'{idn["g"]}#{idn["t"]}'
                            if a.get("riotId") and cur != a["riotId"]:
                                RENAME[(key, a["riotId"])] = cur
                    else:
                        newg.extend(res or [])
                except Exception as e: print(f"   {a.get('riotId')} 抓錯 {e}")
                time.sleep(0.1)
            if newg:
                seen=set(); merged=[]
                for g in sorted(newg+existing, key=lambda x: x.get("t",0), reverse=True):
                    if g["t"] in seen: continue
                    seen.add(g["t"]); merged.append(g)
                data["matches"] = merged
                with open(os.path.join(OUTDIR, meta["f"]), "w", encoding="utf-8") as fp:
                    fp.write(f"window.__sqLoad({json.dumps(key,ensure_ascii=False)},{json.dumps(data,ensure_ascii=False)});\n")
                meta["n"] = len(merged); added_tot += len(newg); upd += 1
                print(f"[{i}/{len(keys)}] {key}  +{len(newg)} 新（共 {len(merged)}）")
        b.close()
    if RENAME:  # 改名自動同步：更新 soloq_accounts.json 的 riotId（fetch_soloq 牌位查詢下輪直接用新 ID）
        raw = json.load(open(ACCOUNTS, encoding="utf-8")); n = 0
        for e in raw:
            k = (f'{e.get("team","")}|{e.get("player","")}', e.get("riotId",""))
            if k in RENAME: e["riotId"] = RENAME[k]; n += 1
        if n:
            json.dump(raw, open(ACCOUNTS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"♻ 改名自動更新 {n} 個帳號 → soloq_accounts.json：")
            for (key2, old), new in RENAME.items(): print(f"   {key2}: {old} → {new}")
    missing = [k for k in accs if k not in idx["players"]]
    print(f"\n完成：{upd} 位有新戰績、共 +{added_tot} 場。"
          + (f" 另有 {len(missing)} 位無檔(新選手)→ 自動補抓整年。" if missing else ""))
    import subprocess
    if MISMATCH:  # 判例自動修復：以資料庫位置重建這些選手（單次上限 5 位；帳號真的缺主帳的會場數偏少→提醒補帳號）
        print(f"⚠ {len(MISMATCH)} 位「資料庫位置≠積分路線」→ 自動以資料庫位置重建：{MISMATCH[:5]}")
        subprocess.run([sys.executable, "-u", os.path.join(HERE, "fetch_soloq_year.py"), "--only", ",".join(MISMATCH[:5])])
    if missing:  # 新選手自動補全年（單次上限 10 位，防守每日排程時長；沒補完的明天續）
        subprocess.run([sys.executable, "-u", os.path.join(HERE, "fetch_soloq_year.py"), "--missing", "--max", "10"])
    # 重建索引(彙總，7天滑動窗口每天重算)＋英雄核心裝/流派聚合
    subprocess.run([sys.executable, os.path.join(HERE, "build_soloq_index.py")])
    subprocess.run([sys.executable, os.path.join(HERE, "build_soloq_builds.py")])

if __name__ == "__main__":
    main()
