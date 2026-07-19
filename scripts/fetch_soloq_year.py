# -*- coding: utf-8 -*-
"""
抓「全職業選手 2026 整年、職業出場路線的單雙排(Solo/Duo)逐場」→ 每位選手一個檔(懶載)。
- 職業路線：每帳號查 5 條路的 totalCount 取最大＝該帳號主導路線；同一選手(同隊同名)取「主帳(場數最多)」的主導路線當職業路線，套用到該選手所有帳號。
- 只抓 queueId==420、gameCreation >= 2026-01-01。
- 精簡欄位：技能只留前 3 點(sk)、符文只留主符文第一個 keystone(r)。
- 輸出：soloq_matches/p{n}.js（每檔 `window.__sqLoad("隊|選手",{role,matches:[...]})`，前端點到才載）
         soloq_match_index.js（`window.SOLOQ_MATCH_IDX`，小檔，開頁載，知道誰可點/檔名/場數）

用法：  python scripts\fetch_soloq_year.py                (全部 275 帳號，約 1-1.5 小時)
        python scripts\fetch_soloq_year.py --max 3        (只跑前 3 位選手，測試用)
        python scripts\fetch_soloq_year.py --since 2025    (改年份界線)
        python scripts\fetch_soloq_year.py --missing       (只補「還沒有逐場檔」的新選手；每日排程自動呼叫)
        python scripts\fetch_soloq_year.py --only "T1|Faker,GEN|Chovy"  (指定選手整年重抓；既有選手加新帳號後用)
不需 Riot 金鑰。
"""
import os, json, sys, time, calendar
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
_OUT = sys.argv[sys.argv.index("--out")+1] if "--out" in sys.argv else "soloq_matches"  # --out 暫存夾(不碰 live、跑完手動 swap)
STAGING = _OUT != "soloq_matches"
OUTDIR = os.path.join(ROOT, _OUT)
IDX = os.path.join(ROOT, "soloq_match_index.js")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

def arg(name, d=None):
    return sys.argv[sys.argv.index(name)+1] if name in sys.argv and sys.argv.index(name)+1 < len(sys.argv) else d
YEAR = int(arg("--since") or 2026)
CUT  = calendar.timegm((YEAR,1,1,0,0,0)) * 1000          # 該年 1/1 00:00 UTC (ms)
MAXP = int(arg("--max") or 0)                            # >0＝只跑前 N 位選手(測試；--missing 時＝單次補抓上限)
ONLY = (arg("--only") or "").strip()                     # 指定選手鍵「隊|選手」逗號分隔：整年重抓這幾位、覆寫原檔
MISSING = "--missing" in sys.argv                        # 只抓「index 沒有的新選手」，附加進現有索引
TOK2LANE = {"top":"TOP","jungle":"JUNGLE","middle":"MIDDLE","bottom":"BOTTOM","utility":"UTILITY"}

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


# Phase1：查 5 條路 totalCount → 該帳號主導路線 token + 場數
JS_ROLE = """async(PU)=>{ const TOKS=['top','jungle','middle','bottom','utility']; const out={};
  for(const t of TOKS){ try{ const r=await fetch(`/v1/players/${PU}/match-history?size=15&page=1&lane=${t}`);
    out[t]= r.ok ? ((await r.json()).totalCount||0) : -1; }catch(e){ out[t]=-1; } } return out; }"""

# Phase2：只抓 lane=token 的 2026 q420，回精簡逐場(技能前3、符文keystone)
JS_YEAR = """async(args)=>{ const [PU, tok, CUT]=args; const out=[];
  for(let pg=1; pg<=400; pg++){
    let r; try{ r=await fetch(`/v1/players/${PU}/match-history?size=15&page=${pg}&lane=${tok}`);}catch(e){break;}
    if(!r.ok) break; const j=await r.json(); const ms=j.matches||[]; if(!ms.length) break; let stop=false;
    for(const m of ms){ if((m.gameCreation||0) < CUT){ stop=true; break; }
      if(m.queueId!==420) continue; if((m.gameDuration||0)<600) continue; const p=(m.participants||[])[0]; if(!p) continue;
      const buy=(p.itemActions||[]).filter(a=>a.action==='purchase').map(a=>[Math.round((a.timestamp||0)/1000),a.id]);
      out.push({ t:m.gameCreation,d:m.gameDuration,c:p.championName,o:p.opponentChampionName||p.duoOpponentChampionName||null,
        w:!!p.win,k:p.kills,de:p.deaths,a:p.assists,kp:Math.round(p.killParticipation||0),sc:p.dpmScore,scr:p.dpmScoreRank,
        pos:p.lane||null, su:[p.summoner1Id,p.summoner2Id], r:p.primaryRuneId,
        rp:[p.primaryRuneId,p.primaryRuneId2,p.primaryRuneId3,p.primaryRuneId4], rs:[p.secondaryRuneId,p.secondaryRuneId2,p.secondaryRuneId3], rst:[p.perksStat1,p.perksStat2,p.perksStat3],
        sk:(p.skillLevelUps||[]).slice(0,5),
        it:(p.itemIds||[]).filter(id=>[1104,3330,3340,3348,3349,3363,3364,3513,6702].indexOf(id)<0), st:p.startItems||[], ib:buy, cs:(p.totalMinionsKilled||0)+(p.neutralMinionsKilled||0),
        gd15:p.goldDiffAt15, xd15:p.xpDiffAt15, dpm:p.damagePerMinute, tr:p.tier||null, lp:(p.lp!=null?p.lp:p.leaguePoints),
        // Laning Phase(at 15) 追加：xp diff(xd15)＋first to level 2(fl2)；gold diff 已是 gd15。cs diff 不抓。
        // fl2 正解欄位＝isFirstToHitLevel2（2026-07-17 實測 dpm payload）
        fl2:(p.isFirstToHitLevel2!=null?(p.isFirstToHitLevel2?1:0):null) });
    }
    if(stop) break;
  }
  return out; }"""

# 每帳號最後一場 soloq 時間(ms)：積分頁挑「最近7天有打 soloq 的帳號」用（獨立小檔，合併既有不覆蓋未更新者）
ACC_LG = {}
ACC_LG_PATH = os.path.join(ROOT, "soloq_acc_lastgame.js")
def _accnorm(s):
    import re as _r
    return _r.sub(r"\s+", "", str(s or "")).lower()
def write_acc_lastgame(new_map):
    old = {}
    try:
        import re as _r
        t = open(ACC_LG_PATH, encoding="utf-8").read()
        m = _r.search(r"=\s*(\{.*\})\s*;?\s*$", t, _r.S)
        if m: old = json.loads(m.group(1))
    except Exception:
        pass
    old.update(new_map)
    open(ACC_LG_PATH, "w", encoding="utf-8").write("window.SOLOQ_ACC_LG=" + json.dumps(old, ensure_ascii=False) + ";\n")
    return len(old)


def main():
    with open(ACCOUNTS, "r", encoding="utf-8") as f:
        accounts = [a for a in json.load(f) if a.get("dpmPuuid") and a.get("riotId") and not a.get("bad")]  # bad＝已判定張冠李戴的帳號，永久跳過
    # 依 (隊,選手) 分組
    players = {}
    for a in accounts:
        key = f'{a.get("team","")}|{a.get("player","")}'
        players.setdefault(key, []).append(a)
    keys = list(players.keys())
    # 部分模式（--missing／--only）：載入現有索引，只抓目標選手、保留其他人
    live_idx = {}
    if MISSING or ONLY:
        try:
            live_idx = json.loads(open(IDX, encoding="utf-8").read().split("=", 1)[1].rstrip(";\n")).get("players", {})
        except Exception:
            live_idx = {}
    if MISSING:
        keys = [k for k in keys if k not in live_idx]
        if not keys:
            print("--missing：沒有缺檔的新選手，跳過。"); return
        print(f"--missing：{len(keys)} 位新選手待補全年 → {keys}")
    if ONLY:
        want = {w.strip() for w in ONLY.split(",") if w.strip()}
        keys = [k for k in keys if k in want]
        miss = want - set(keys)
        if miss: print(f"--only：帳號清單裡找不到 {sorted(miss)}")
        if not keys: print("--only：無符合選手。"); return
    if MAXP: keys = keys[:MAXP]
    print(f"{len(keys)} 位選手 / {sum(len(players[k]) for k in keys)} 帳號；界線 {YEAR}-01-01。約 1-1.5 小時（--max 可先測）")
    CROLE = comp_roles()  # 資料庫比賽位置＝權威路線
    BADACC = []  # 本輪判定「來源網站張冠李戴」的帳號 → 跑完標 bad 排除（判例 2026-07-16）
    with open(ACCOUNTS, "r", encoding="utf-8") as f0:
        _rawAll = json.load(f0)
    BAD_BY_KEY = {}  # 已標 bad 的帳號：該選手重建時複驗，網站資料變正確（主路=資料庫位置）就解除
    for a in _rawAll:
        if a.get("bad") and a.get("dpmPuuid") and a.get("riotId"):
            BAD_BY_KEY.setdefault(f'{a.get("team","")}|{a.get("player","")}', []).append(a)
    UNBAD = []
    os.makedirs(OUTDIR, exist_ok=True)
    part = (MISSING or ONLY) and not STAGING
    idx = dict(live_idx) if part else {}
    done = 0; totG = 0; written = 0
    if part:  # 檔名接在現有 pN 之後，不覆蓋別人；--only 既有選手沿用原檔名覆寫
        import re as _re
        used = [int(m.group(1)) for fn in os.listdir(OUTDIR) for m in [_re.match(r"p(\d+)\.js$", fn)] if m]
        done = (max(used) + 1) if used else 0
    with sync_playwright() as p:
        b = _launch_real(p)
        pg = b.new_context(user_agent=UA, viewport={"width":1400,"height":900}, locale="en-US").new_page()
        pg.goto("https://dpm.lol/", wait_until="domcontentloaded", timeout=60000)
        for _w in (3.5, 14, 25):  # Cloudflare 盤查自動重試（偶發互動式 Turnstile：多等幾輪通常自動放行）
            time.sleep(_w)
            try:
                if pg.evaluate("async()=>{const r=await fetch('/v1/esport/soloq/top-teams');return r.status;}") == 200: break
            except Exception: pass
        for i, key in enumerate(keys, 1):
            accs = players[key]
            # Phase1：每帳號主導路線；選手職業路線＝主帳(主導場數最多)的主導路線
            best_tok, best_cnt = "middle", -1
            for a in accs:
                try: tc = pg.evaluate(JS_ROLE, a["dpmPuuid"])
                except Exception: tc = {}
                if tc:
                    dom = max(tc, key=lambda t: tc[t]); a["_dom"]=dom; a["_domN"]=tc.get(dom,0)
                    if tc.get(dom,0) > best_cnt: best_cnt = tc.get(dom,0); best_tok = dom
                time.sleep(0.1)
            comp = CROLE.get(str(key.split("|", 1)[-1]).strip().lower())
            use = accs
            if comp:  # 判例：資料庫位置＝權威；帳號主路(≥8場)與資料庫不符＝該帳號被來源網站張冠李戴 → 標錯永久跳過
                if best_cnt > 0 and comp != best_tok:
                    print(f"   ⚠ 積分主路 {best_tok}({best_cnt}場) ≠ 資料庫 {comp} → 以資料庫為準")
                badn = [a for a in accs if a.get("_domN", 0) >= 8 and a.get("_dom") and a["_dom"] != comp]
                for a in badn:
                    BADACC.append((a.get("riotId"), a.get("dpmPuuid")))
                    print(f"   ⛔ 帳號標示錯誤：{a.get('riotId')}（主路 {a.get('_dom')}≠{comp}），以後不再抓")
                use = [a for a in accs if a not in badn]
                for a in BAD_BY_KEY.get(key, []):  # 複驗已標錯帳號：主路已符合資料庫 → 解除標記、恢復抓取
                    try: tc2 = pg.evaluate(JS_ROLE, a["dpmPuuid"])
                    except Exception: tc2 = {}
                    if tc2:
                        dom2 = max(tc2, key=lambda t2: tc2[t2])
                        if dom2 == comp and tc2.get(dom2, 0) >= 8:
                            UNBAD.append((a.get("riotId"), a.get("dpmPuuid")))
                            use = use + [a]
                            print(f"   ♻ 解除錯誤標記：{a.get('riotId')} 主路 {dom2}＝資料庫位置，恢復抓取")
                    time.sleep(0.1)
                best_tok = comp
            role = TOK2LANE.get(best_tok, "MIDDLE")
            if not use:  # 全部帳號都判錯 → 移出積分（積分頁會顯示「缺積分帳號」＝真實狀態），待補真帳號
                if part and key in idx:
                    try: os.remove(os.path.join(OUTDIR, idx[key]["f"]))
                    except Exception: pass
                    idx.pop(key, None)
                print(f"[{i}/{len(keys)}] {key}  ⛔ 無可信帳號 → 移出積分，待補真帳號（merge_scoregg_gaps.py --player 可補）")
                continue
            # Phase2：該選手可信帳號都抓職業路線
            merged = []
            for a in use:
                try: arr = pg.evaluate(JS_YEAR, [a["dpmPuuid"], best_tok, CUT])
                except Exception as e: print(f"   {a['riotId']} 抓錯 {e}"); arr = []
                merged.extend(arr)
                if arr:  # 記該帳號自己最後一場 soloq 的時間
                    _lg = max((g.get("t") or 0) for g in arr)
                    if _lg: ACC_LG[_accnorm(a.get("riotId"))] = _lg
                time.sleep(0.1)
            merged.sort(key=lambda g: g.get("t",0), reverse=True)
            if merged:
                if part and key in idx:
                    fid = idx[key]["f"].replace(".js", "")   # --only 既有選手：覆寫原檔
                else:
                    fid = f"p{done}"; done += 1
                written += 1; totG += len(merged)
                with open(os.path.join(OUTDIR, fid+".js"), "w", encoding="utf-8") as f:
                    f.write(f"window.__sqLoad({json.dumps(key,ensure_ascii=False)},"
                            f"{json.dumps({'role':role,'matches':merged},ensure_ascii=False)});\n")
                idx[key] = {"f": fid+".js", "role": role, "n": len(merged)}
            print(f"[{i}/{len(keys)}] {key}  {role}  {len(merged)} 場（累計 {totG}）")
        b.close()
    _idx_path = os.path.join(OUTDIR, "soloq_match_index.js") if STAGING else IDX  # 暫存模式：索引也寫進暫存夾，絕不碰 live（swap 後由 build_soloq_index 重建）
    with open(_idx_path, "w", encoding="utf-8") as f:
        f.write("window.SOLOQ_MATCH_IDX=" + json.dumps({"fetched_at": time.strftime("%Y-%m-%d %H:%M"),
                "year": YEAR, "players": idx}, ensure_ascii=False) + ";\n")
    if ACC_LG:  # 每帳號最後一場 soloq 時間（合併既有）→ 積分頁挑帳號用
        tot = write_acc_lastgame(ACC_LG)
        print(f"每帳號最後 soloq 時間：本次更新 {len(ACC_LG)} 個 → soloq_acc_lastgame.js（累計 {tot}）")
    if BADACC or UNBAD:  # 壞帳號標記/解除 持久化（墓碑留檔：防自動抓帳號把它加回來；網站更正後自動解除）
        rawA = json.load(open(ACCOUNTS, encoding="utf-8")); nb = 0; nu = 0
        ks = set(BADACC); us = set(UNBAD)
        for a in rawA:
            ka = (a.get("riotId"), a.get("dpmPuuid"))
            if ka in ks and not a.get("bad"):
                a["bad"] = True; a["bad_reason"] = "role-mismatch"; nb += 1
            elif ka in us and a.get("bad"):
                a.pop("bad", None); a.pop("bad_reason", None); nu += 1
        if nb or nu:
            json.dump(rawA, open(ACCOUNTS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"⛔ 標示 {nb} 個錯誤帳號｜♻ 解除 {nu} 個 → soloq_accounts.json")
    tot_mb = sum(os.path.getsize(os.path.join(OUTDIR,v["f"])) for v in idx.values() if os.path.exists(os.path.join(OUTDIR,v["f"])))/1024/1024
    print(f"\n完成：{written or done} 位有戰績 / {totG} 場 → soloq_matches/（{tot_mb:.0f} MB，共 {len(idx)} 檔）")
    if STAGING:
        print(f"※ 暫存模式：資料在 {OUTDIR}，未動 live。確認後 swap 再重建索引/出裝：\n"
              f"  Remove-Item soloq_matches -Recurse -Force; Rename-Item {_OUT} soloq_matches; python scripts\\build_soloq_index.py; python scripts\\build_soloq_builds.py")
    else:
        import subprocess  # 重建索引(彙總)＋英雄核心裝/流派聚合
        subprocess.run([sys.executable, os.path.join(HERE, "build_soloq_index.py")])
        subprocess.run([sys.executable, os.path.join(HERE, "build_soloq_builds.py")])

if __name__ == "__main__":
    main()
