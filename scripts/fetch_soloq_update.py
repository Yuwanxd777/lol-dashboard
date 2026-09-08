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
sys.path.insert(0, HERE)
import soloq_src  # 逐場檔來源 meta（哪個 dpmPuuid 抓回哪些 rid）
IDXP = os.path.join(ROOT, "soloq_match_index.js")
OUTDIR = os.path.join(ROOT, "soloq_matches")
ACCOUNTS = os.path.join(HERE, "soloq_accounts.json")
# 2026-09-06 線 3（迴圈 #21）：fetch_soloq_year --missing 對「近 EMPTY_DAYS 天補全年抓到 0 場」的人不重抓（csv_cache/soloq_year_empty.json），
# 這裡的「另有 N 位無檔」要跟它對齊：略過的分開印、一位都不用抓就不起子程序（日誌才對得上，也省一次子程序啟動）。
EMPTY_PATH = os.path.join(ROOT, "csv_cache", "soloq_year_empty.json")   # {"隊|選手": {"at": "YYYY-MM-DD", "tries": n}}
EMPTY_DAYS = 3   # 要跟 fetch_soloq_year.EMPTY_DAYS 一致（fetch_soloq_update_missing_test.py 會比對兩邊）


def load_year_empty(path=EMPTY_PATH):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return {}


def split_missing_recent_empty(keys, empty, today=None, days=EMPTY_DAYS):
    """語意與 fetch_soloq_year.split_recent_empty 相同：0～days-1 天內 0 場的略過 [(key, at)]；沒紀錄／壞日期／過期／未來照抓。
    不 import fetch_soloq_year（它模組層讀 sys.argv 的 --out／--since／--max）。"""
    import datetime as _dt
    today = today or _dt.date.today()
    go, skip = [], []
    for k in keys:
        at = (empty.get(k) or {}).get("at")
        try:
            d = _dt.date.fromisoformat(at) if at else None
        except (TypeError, ValueError):
            d = None
        if d is not None and 0 <= (today - d).days < days:
            skip.append((k, at))
        else:
            go.append(k)
    return go, skip
# 每帳號最後一場 soloq 時間(ms)：積分頁挑「最近7天有打 soloq 的帳號」用（獨立小檔，合併既有）
# ── 逐帳號跳過「牌位沒動」的帳號（2026-09-07 線 3，精進迴圈 #23）────────────────────
# 名單來源：fetch_soloq.py 牌位那一步比對兩版 soloq.js，逐帳號 W+L 相同的寫進 soloq_played.json 的 acc_static
# （鍵＝riotId 小寫@platform 小寫，跟這裡的 acc_key 同一條；fetch_soloq_update_accskip_test.py 會比對兩邊）。
# 22:00 實測 111 位 315 個帳號裡 100 個沒動、每帳號 1.7 秒 ⇒ 省約 170 秒。
# 名單缺／壞／不是 list → 空集合＝全查；只在 --changed 且 scope=full 時啟用。
def acc_key(riot_id, platform):
    return "%s@%s" % (str(riot_id or "").strip().lower(), str(platform or "").strip().lower())

def acc_static_from(d):
    """soloq_played.json 的 dict → 靜止帳號鍵集合；任何形狀不對都回空集合（＝全查）。"""
    v = d.get("acc_static") if isinstance(d, dict) else None
    if not isinstance(v, list):
        return set()
    return {s.strip().lower() for s in v if isinstance(s, str) and "@" in s}

def split_static_accounts(acc_list, static):
    """→ (要問 dpm 的帳號, 跳過的帳號)，順序保留；static 空就全部要問（負控制）。"""
    if not static:
        return list(acc_list), []
    todo, skip = [], []
    for a in acc_list:
        (skip if acc_key(a.get("riotId"), a.get("platform")) in static else todo).append(a)
    return todo, skip

ACC_LG = {}
ACC_LG_PATH = os.path.join(ROOT, "soloq_acc_lastgame.js")
def _accnorm(s):
    return re.sub(r"\s+", "", str(s or "")).lower()
def write_acc_lastgame(new_map):
    old = {}
    try:
        m = re.search(r"=\s*(\{.*\})\s*;?\s*$", open(ACC_LG_PATH, encoding="utf-8").read(), re.S)
        if m: old = json.loads(m.group(1))
    except Exception:
        pass
    old.update(new_map)
    open(ACC_LG_PATH, "w", encoding="utf-8").write("window.SOLOQ_ACC_LG=" + json.dumps(old, ensure_ascii=False) + ";\n")
    return len(old)
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

JS_NEW = """async(args)=>{ const [PU,tok,newestT]=args; const out=[]; let ID=null, bad=0;
  for(let pg=1; pg<=20; pg++){
    let r; try{ r=await fetch(`/v1/players/${PU}/match-history?size=15&page=${pg}&lane=${tok}`);}catch(e){break;}
    if(!r.ok){ if(r.status===429||r.status===403||r.status>=500) bad=r.status; break; }   // 限流／擋下要回報（以前靜默截斷）
    const j=await r.json(); const ms=j.matches||[]; if(!ms.length) break; let stop=false;
    if(pg===1&&ms[0]&&ms[0].participants&&ms[0].participants[0]){const q0=ms[0].participants[0]; ID={g:q0.gameName||null,t:q0.tagLine||null};} // 最近一場的當前 Riot ID：改名偵測
    for(const m of ms){ if((m.gameCreation||0) <= newestT){ stop=true; break; }   // 追到已存在的最新一場就停
      if(m.queueId!==420) continue; if((m.gameDuration||0)<600) continue; const p=(m.participants||[])[0]; if(!p) continue;
      const buy=(p.itemActions||[]).filter(a=>a.action==='purchase').map(a=>[Math.round((a.timestamp||0)/1000),a.id]);
      out.push({ t:m.gameCreation,d:m.gameDuration,c:p.championName,o:p.opponentChampionName||p.duoOpponentChampionName||null,
        w:!!p.win,k:p.kills,de:p.deaths,a:p.assists,kp:Math.round(p.killParticipation||0),sc:p.dpmScore,scr:p.dpmScoreRank,
        pos:p.lane||null, su:[p.summoner1Id,p.summoner2Id], r:p.primaryRuneId,
        rp:[p.primaryRuneId,p.primaryRuneId2,p.primaryRuneId3,p.primaryRuneId4], rs:[p.secondaryRuneId,p.secondaryRuneId2,p.secondaryRuneId3], rst:[p.perksStat1,p.perksStat2,p.perksStat3],
        sk:p.skillLevelUps||[],
        // 搭檔／對手（dpm 的 duo 就是使用者要的配對：上→野、野→中、中→野、下→輔、輔→下）
        du:p.duoChampionName||null, dul:p.duoLane||null, duo:p.duoOpponentChampionName||null,
        // 該局當下的 Riot ID：帳號改名史就是靠逐場這一欄還原（dpm 沒有歷史 ID 端點）
        rid:((p.gameName||'')+(p.tagLine?'#'+p.tagLine:''))||null,
        it:(p.itemIds||[]).filter(id=>[1104,3330,3340,3348,3349,3363,3364,3513,6702].indexOf(id)<0), st:p.startItems||[], ib:buy, cs:(p.totalMinionsKilled||0)+(p.neutralMinionsKilled||0),
        gd15:p.goldDiffAt15, dpm:p.damagePerMinute, tr:p.tier||null, lp:(p.lp!=null?p.lp:p.leaguePoints),
        // Laning Phase(at 15) 追加（與 fetch_soloq_year.py 同步）：xp diff＋first to level 2；cs diff 不抓（使用者指定）
        xd15:p.xpDiffAt15,
        fl2:(p.isFirstToHitLevel2!=null?(p.isFirstToHitLevel2?1:0):null) });
    }
    if(stop) break;
  }
  return {id:ID, ms:out, bad:bad}; }"""

# 2026-09-08 線 3（精進迴圈 #68）：逐人 267s 的批次化。10:00 那班 133 位／238 個帳號逐一 pg.evaluate(JS_NEW)
# 一次約 1.1s ＋ sleep 0.1 ⇒ 267s。這裡一次 evaluate 用 Promise.all 同時問 BATCH_NEW 個帳號（帳號那一支
# fetch_dpm_soloq_accounts 早就這樣做、dpm 沒限流），結果按 (選手, puuid) 收進 PRE，主迴圈逐帳號 pop；
# 沒命中（批次整包炸掉／dpm 回 429、403、5xx）就退回原本的逐一 evaluate ⇒ RENAME／ACC_LG／_perpu 的
# 逐帳號歸屬與寫檔順序一個字沒變。預設關（--batch 才開），管線由 run_update 的 ⑤d 帶旗標。
# 改這段要跑 scripts/fetch_soloq_update_batch_test.py（沙盒：假 playwright、暫存目錄、子程序不起）。
# 2026-09-09 線 3（精進迴圈 #71）：批次 8 → 24。22:00 那班「批次預抓 88s：314 個帳號／40 批」＝每批 2.2s，
# 唯讀探針（autopilot/_r71_batch_probe2.txt，六組**不重疊的冷帳號**交錯跑 8／24／16）證明每批耗時跟批次大小
# 幾乎無關（1.4～1.9s，由最慢那一支請求決定）⇒ 每帳號 bs=8 0.216s／bs=16 0.131s／bs=24 0.078s，
# 三種大小全命中、0 退回、0 減半；314 個帳號換算 68s → 24s。帳號那支 fetch_dpm_soloq_accounts 早就 24 並發
# （OWNER_BATCH）沒被 dpm 擋；真被限流時下面 prefetch_batches 會自動減半（24→12→6→3→2）。
JS_BATCH = "async(items)=>{ const one=(" + JS_NEW + "); return Promise.all(items.map(it=>one(it).catch(e=>({err:String(e)})))); }"
USE_BATCH = "--batch" in sys.argv
BATCH_NEW = int(arg("--batch-size") or 24)

def _res_ok(r):
    """批次結果可用嗎：dict、沒有 err、dpm 沒回限流／擋下（bad）——不可用的留給主迴圈逐一問"""
    return isinstance(r, dict) and not r.get("err") and not r.get("bad")

def prefetch_batches(pg, keys, idx, accs, static, bs=None):
    """把所有待問的 (選手, 帳號) 攤平、每 bs 個一批問 dpm；回 (PRE, 統計)。
    一批裡有人被限流就把批次減半（最小 2），那幾個帳號留給主迴圈逐一問（那邊會睡一下再試）。"""
    bs = bs or BATCH_NEW
    items = []
    for key in keys:
        meta = idx["players"][key]; tok = LANE2TOK.get(meta.get("role"), "middle")
        try: _, data = load_player_file(meta["f"])
        except Exception: continue   # 讀檔錯的留給主迴圈印
        ex = data.get("matches", []); nt = ex[0]["t"] if ex else 0
        todo, _ = split_static_accounts(accs.get(key, []), static)
        for a in todo: items.append((key, a["dpmPuuid"], [a["dpmPuuid"], tok, nt]))
    PRE = {}; st = {"items": len(items), "batches": 0, "hit": 0, "fallback": 0, "halved": 0, "sizes": []}
    i = 0
    while i < len(items):
        chunk = items[i:i + bs]; i += len(chunk); st["batches"] += 1; st["sizes"].append(len(chunk))
        try:
            rs = pg.evaluate(JS_BATCH, [it[2] for it in chunk])
            if not isinstance(rs, list) or len(rs) != len(chunk): raise ValueError("批次回傳形狀不對")
        except Exception as e:
            print(f"   批次抓錯 {e} → 這 {len(chunk)} 個帳號改逐一問"); st["fallback"] += len(chunk); continue
        bad = 0
        for (k, pu, _), r in zip(chunk, rs):
            if _res_ok(r): PRE[(k, pu)] = r; st["hit"] += 1
            else:
                st["fallback"] += 1
                if isinstance(r, dict) and r.get("bad"): bad = r["bad"]
        if bad and bs > 2:
            bs = max(2, bs // 2); st["halved"] += 1
            print(f"   dpm 回 {bad} → 批次減半為 {bs}")
    return PRE, st

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

def child_cmd(cmd, argv=None):
    """子程序（fetch_soloq_year --only／--missing）的完整命令列：父程序帶 --no-rebuild 時子程序也要帶。

    2026-09-07 #58：管線的 ⑤d 是 `fetch_soloq_update --changed --no-rebuild`，但它起的
    `fetch_soloq_year --missing` 子程序沒帶 ⇒ 子程序尾端照樣跑 build_soloq_index＋build_soloq_builds，
    而 run_update 的 ⑤f／⑤g 之後又做一遍。09-07 22:00 那班「⏱ 新選手補全年：137s」裡約 92s
    （⑤f 19.6s＋⑤g 72.6s）就是這段白做的，真正抓 356 場只要 45s 上下。
    """
    argv = sys.argv if argv is None else argv
    return list(cmd) + (["--no-rebuild"] if "--no-rebuild" in argv else [])

def run_child(label, cmd, argv=None):
    """起子程序並計時（印「⏱ label：Ns」）。

    起之前先 flush：管線裡 stdout 是 pipe（block-buffered），子程序 -u 直接寫同一條 pipe，
    父程序累積的輸出要等結束才落地 ⇒ update_log.txt 裡「補全年」整段出現在「--changed」之前，
    看起來像先補全年再增量（09-07 22:00 那班就是這樣，實際順序相反）。
    """
    import subprocess
    sys.stdout.flush()
    _t = time.time()
    subprocess.run(child_cmd(cmd, argv))
    print(f"⏱ {label}：{time.time() - _t:.0f}s")

def main():
    if not os.path.exists(IDXP):
        print("找不到 soloq_match_index.js，請先跑 fetch_soloq_year.py。"); return
    idx = read_js_obj(IDXP, "SOLOQ_MATCH_IDX")
    accs = _load_accs()
    keys = list(idx["players"].keys())
    # ── --changed：只抓「牌位那一步確認勝敗場數有變」的選手（2026-09-05 使用者定案）──
    # 為什麼這樣排：這一支每位選手 ~1.4 秒（Playwright 開真 Chrome 過 Cloudflare），
    # 431 位＝10 分鐘，而且**沒人打過也要花滿 10 分鐘**（實測 --max 3 走完 431 位、0 場）。
    # 牌位那一支是普通 HTTP、又本來就帶 wins/losses ⇒ 讓便宜的先跑、拿它的結果決定這一支抓誰。
    # 讀不到名單（牌位沒跑／格式壞了）就**退回全掃**，寧可慢不要漏。
    ACC_STATIC = set()   # 逐帳號靜止名單（只在 --changed 且 scope=full 時填入）
    if "--changed" in sys.argv:
        pf = os.path.join(HERE, "soloq_played.json")
        try:
            d = json.load(open(pf, encoding="utf-8"))
            want = set(d.get("played") or []) | set(d.get("unknown") or [])
            if d.get("scope") != "full":
                print("--changed：soloq_played.json 是 --active 那一輪寫的（涵蓋範圍不完整）→ 退回全掃")
            elif not want:
                print("--changed：牌位比對顯示**沒有人打過排位** → 這一輪不用抓逐場（省下約 10 分鐘）")
                keys = []
            else:
                before = len(keys)
                keys = [k for k in keys if k in want]
                ACC_STATIC = acc_static_from(d)   # 逐帳號：牌位沒動的帳號連 dpm 都不問（名單壞→空集合＝全查）
                print("--changed：牌位比對出 %d 位有動（含無從判斷的）→ 逐場 %d → %d 位；另有 %d 個帳號牌位沒動（逐帳號跳過）"
                      % (len(want), before, len(keys), len(ACC_STATIC)))
        except Exception as e:
            print("--changed：讀不到名單（%s）→ 退回全掃" % type(e).__name__)
    keys = keys[:MAXP] if MAXP else keys
    print(f"增量更新 {len(keys)} 位選手（只抓比現有最新更新的 Solo/Duo）…")
    CROLE = comp_roles()  # 判例：資料庫位置＝權威；index 路線不符 → 蒐集、最後自動用 --only 重建
    MISMATCH = []
    _MISSRC = []   # 來源對帳：某 puuid 抓回來的 rid ≠ 帳號檔登記的 riotId（riotId↔dpmPuuid 疑似錯配）
    added_tot = 0; upd = 0; RENAME = {}
    # 2026-09-06 線 3：這一步昨晚 1926 秒（130 位＝每位 15 秒，說明寫的是 1.4 秒）。
    # 錢花在哪沒有紀錄 ⇒ 印各階段耗時，下一次 10:00 的 update_log 就看得出來。
    _T0 = time.time(); _TCF = _TPU = 0.0; _TPL = []; _NACC = _NSKIP = 0
    with sync_playwright() as p:
        b = _launch_real(p)
        pg = b.new_context(user_agent=UA, viewport={"width":1400,"height":900}, locale="en-US").new_page()
        pg.goto("https://dpm.lol/", wait_until="domcontentloaded", timeout=60000)
        for _w in (3.5, 14, 25):  # Cloudflare 盤查自動重試（偶發互動式 Turnstile：多等幾輪通常自動放行）
            time.sleep(_w)
            try:
                if pg.evaluate("async()=>{const r=await fetch('/v1/esport/soloq/top-teams');return r.status;}") == 200: break
            except Exception: pass
        _TCF = time.time() - _T0
        _t1 = time.time()
        if fill_missing_puuids(pg):
            accs = _load_accs()  # 補完 puuid 立即生效：新帳號本輪就進增量/補全年
        _TPU = time.time() - _t1
        PRE = {}; _BST = None; _TB = 0.0
        if USE_BATCH:   # #68：先一批批問完，主迴圈只 pop 結果；沒命中的照舊逐一問
            _tb = time.time()
            PRE, _BST = prefetch_batches(pg, keys, idx, accs, ACC_STATIC)
            _TB = time.time() - _tb
        for i, key in enumerate(keys, 1):
            _tp = time.time()
            meta = idx["players"][key]; role = meta.get("role")
            tok = LANE2TOK.get(role, "middle")
            _comp = CROLE.get(str(key.split("|", 1)[-1]).strip().lower())
            if _comp and _comp != tok:
                MISMATCH.append(key)  # 資料庫位置≠積分檔路線：帳號找錯或缺主帳，最後統一重建
            try: _, data = load_player_file(meta["f"])
            except Exception as e: print(f"[{i}/{len(keys)}] {key} 讀檔錯 {e}"); continue
            existing = data.get("matches", []); newestT = existing[0]["t"] if existing else 0
            newg = []
            _todo, _skip = split_static_accounts(accs.get(key, []), ACC_STATIC)
            _NACC += len(_todo) + len(_skip); _NSKIP += len(_skip)
            _perpu = {}   # 這輪每個 dpmPuuid 抓回來的新場次 → 寫進逐場檔的 src（來源對帳用）
            for a in _todo:
                _hit = (key, a["dpmPuuid"]) in PRE
                try:
                    res = PRE.pop((key, a["dpmPuuid"])) if _hit else pg.evaluate(JS_NEW, [a["dpmPuuid"], tok, newestT])
                    if isinstance(res, dict) and res.get("bad"):
                        # dpm 限流／擋下：睡一下再問一次；還是不行就**丟掉半截結果**（留著會讓 newestT 往前跳、
                        # 中間那段永遠補不回來——以前是靜默截斷，2026-09-08 #68 改成回報＋丟棄，下輪從原 newestT 再抓）
                        time.sleep(1.5)
                        res = pg.evaluate(JS_NEW, [a["dpmPuuid"], tok, newestT])
                        if isinstance(res, dict) and res.get("bad"):
                            print(f"   {a.get('riotId')} dpm 回 {res['bad']}（重試仍失敗）→ 這輪不採用、下輪再補")
                            res = dict(res, ms=[])
                    _ms = (res.get("ms") if isinstance(res, dict) else res) or []
                    if _ms: _perpu.setdefault(a["dpmPuuid"], []).extend(_ms)
                    if _ms:  # 記該帳號自己最後一場 soloq 時間
                        _lg = max((g.get("t") or 0) for g in _ms)
                        if _lg: ACC_LG[_accnorm(a.get("riotId"))] = _lg
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
                if not _hit: time.sleep(0.1)   # 批次命中的沒真的打 dpm，不用睡
            if newg:
                seen=set(); merged=[]
                for g in sorted(newg+existing, key=lambda x: x.get("t",0), reverse=True):
                    if g["t"] in seen: continue
                    seen.add(g["t"]); merged.append(g)
                data["matches"] = merged
                _s = soloq_src.get_src(data)   # 來源 meta：這次的新場次是哪個 puuid 抓來的（見 scripts/soloq_src.py）
                soloq_src.set_accounts(_s, accs.get(key, []))
                for _pu, _msl in _perpu.items():
                    soloq_src.note(_s, _pu, _msl)
                for _pu, _want, _got, _n, _tot in soloq_src.mismatches(data):
                    # 改名當輪不是錯配：obs 只有這輪抓回的新名，帳號檔還是舊名（RENAME 要等下面才同步），
                    # 下一輪 acc 就會是新名而不再報。不濾掉的話每次有人改名就假警報一次。
                    if soloq_src.same_name(RENAME.get((key, _want)), _got):
                        continue
                    _MISSRC.append((key, _want, _got, _n, _tot))
                with open(os.path.join(OUTDIR, meta["f"]), "w", encoding="utf-8") as fp:
                    fp.write(f"window.__sqLoad({json.dumps(key,ensure_ascii=False)},{json.dumps(data,ensure_ascii=False)});\n")
                meta["n"] = len(merged); added_tot += len(newg); upd += 1
                print(f"[{i}/{len(keys)}] {key}  +{len(newg)} 新（共 {len(merged)}）")
            _TPL.append((time.time() - _tp, key, len(_todo)))
        b.close()
    if _BST:
        print("⏱ 批次預抓 %.0fs：%d 個帳號／%d 批（批次大小 %d）、命中 %d、退回逐一 %d、減半 %d 次"
              % (_TB, _BST["items"], _BST["batches"], BATCH_NEW, _BST["hit"], _BST["fallback"], _BST["halved"]))
    if _TPL:
        if _NSKIP:
            print("⏭ 跳過 %d 個牌位沒動的帳號（%d → %d 次 dpm 請求）" % (_NSKIP, _NACC, _NACC - _NSKIP))
        _TPL.sort(reverse=True)
        _tot = sum(t for t, _, _ in _TPL)
        print("⏱ 逐場階段計時：開瀏覽器＋Cloudflare %.0fs／補 puuid %.0fs／逐人合計 %.0fs（%d 位，平均 %.1fs）"
              % (_TCF, _TPU, _tot, len(_TPL), _tot / len(_TPL)))
        print("   最久的 5 位：" + "、".join("%s %.0fs（%d 帳號）" % (k, t, n) for t, k, n in _TPL[:5]))
    if RENAME:  # 改名自動同步：更新 soloq_accounts.json 的 riotId（fetch_soloq 牌位查詢下輪直接用新 ID）
        # ⚠ 這裡的「新名字」來源是 dpm 最近一場比賽的參賽者名，那是**該局當下**的 ID（見 JS_NEW 的
        #   rid 註解），選手改名後若還沒再打一場，讀到的就是舊名。所以不可以蓋掉今天才由 dpm
        #   選手檔(/v1/pros)確認過的名字（dpmSeen==今天）——否則會把正確的新名改回舊名，而且
        #   下一支 fetch_soloq.py 又會改回來，兩支每天來回震盪。
        #   實例：HLE Zeus 改名 Athene#lll，這裡讀到舊名 Zeus#glgl 蓋回去 → 牌位永遠查不到。
        _today = time.strftime("%Y-%m-%d")
        raw = json.load(open(ACCOUNTS, encoding="utf-8")); n = 0; skipped = []
        for e in raw:
            k = (f'{e.get("team","")}|{e.get("player","")}', e.get("riotId",""))
            if k not in RENAME: continue
            if e.get("dpmSeen") == _today:
                skipped.append((k[0], e.get("riotId",""), RENAME[k])); continue
            e["riotId"] = RENAME[k]; n += 1
        if n:
            json.dump(raw, open(ACCOUNTS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"♻ 改名自動更新 {n} 個帳號 → soloq_accounts.json：")
            for (key2, old), new in RENAME.items(): print(f"   {key2}: {old} → {new}")
        if skipped:
            print(f"⏭ 略過 {len(skipped)} 個改名（dpm 選手檔今天確認過現有名字，比賽紀錄裡的是舊快照）：")
            for key2, old, new in skipped: print(f"   {key2}: 保留 {old}（未採用比賽紀錄的 {new}）")
    if ACC_LG:  # 每帳號最後 soloq 時間（合併既有）→ 積分頁挑帳號用
        tot = write_acc_lastgame(ACC_LG)
        print(f"每帳號最後 soloq 時間：本次更新 {len(ACC_LG)} 個 → soloq_acc_lastgame.js（累計 {tot}）")
    missing, missing_skip = split_missing_recent_empty([k for k in accs if k not in idx["players"]], load_year_empty())
    print(f"\n完成：{upd} 位有新戰績、共 +{added_tot} 場。"
          + (f" 另有 {len(missing)} 位無檔(新選手)→ 自動補抓整年。" if missing else "")
          + (f" ⏭ {len(missing_skip)} 位上次補全年 0 場、{EMPTY_DAYS} 天內不重抓（不起子程序）。" if missing_skip else ""))
    # 2026-09-06 線 3：這一步的 1926 秒有一大半在下面這四支子程序（補全年、重建索引、掃 30 萬場
    # 聚合出裝），逐段計時，update_log 才看得出哪一段該減。
    # 2026-09-07 #58：抽成模組層 run_child／child_cmd（子程序要跟著帶 --no-rebuild、起之前先 flush）。
    _timed = run_child
    if _MISSRC:  # 逐場檔 src 對帳（2026-09-07 #34）：只印不動，累積幾天再決定要不要自動處置
        print(f"⚠ {len(_MISSRC)} 筆來源對帳不符（帳號 riotId 與該 puuid 實際抓回的 rid 不同，可能是改名或錯配）：")
        for _k, _want, _got, _n, _tot in _MISSRC[:10]:
            print(f"   {_k}  帳號 {_want} 的 puuid → 實際 {_got}×{_n}／{_tot} 場")
    if MISMATCH:  # 判例自動修復：以資料庫位置重建這些選手（單次上限 5 位；帳號真的缺主帳的會場數偏少→提醒補帳號）
        print(f"⚠ {len(MISMATCH)} 位「資料庫位置≠積分路線」→ 自動以資料庫位置重建：{MISMATCH[:5]}")
        _timed("重建錯路線選手", [sys.executable, "-u", os.path.join(HERE, "fetch_soloq_year.py"), "--only", ",".join(MISMATCH[:5])])
    if missing:  # 新選手自動補全年（單次上限 10 位，防守每日排程時長；沒補完的明天續）
        _timed("新選手補全年", [sys.executable, "-u", os.path.join(HERE, "fetch_soloq_year.py"), "--missing", "--max", "10"])
    # 重建索引(彙總，7天滑動窗口每天重算)＋英雄核心裝/流派聚合
    # 2026-09-06：這兩支重建器 fetch_soloq_year --missing 的尾端也會跑 ⇒ 每次管線掃兩遍 30 萬場。
    # run_update.py 現在把重建放成獨立的第⑤f 階段、兩支抓取器都帶 --no-rebuild；單獨手跑時照舊會重建。
    if "--no-rebuild" in sys.argv:
        print("（--no-rebuild：索引與出裝聚合交給 run_update 的第⑤f 階段一次做）")
    else:
        _timed("重建索引 build_soloq_index", [sys.executable, os.path.join(HERE, "build_soloq_index.py")])
        _timed("出裝聚合 build_soloq_builds", [sys.executable, os.path.join(HERE, "build_soloq_builds.py")])

if __name__ == "__main__":
    main()
