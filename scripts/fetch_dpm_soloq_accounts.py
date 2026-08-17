# -*- coding: utf-8 -*-
"""用 dpm.lol 職業頁 API 重建 soloq 帳號清單（使用者定案 2026-07-20）。
端點 /v1/pros/{選手名} → {"players":[{puuid, gameName, tagLine, displayName, team, lane, platform, ranks, lastMatchTimestamp}...]}
puuid 即 dpm 可用 puuid（=dpmPuuid，免再 resolve）；team 欄用來比對消歧（同名不同隊，如 TL Morgan vs BRION Morgan）。
路由（使用者定案）：LCS/LEC/CBLOL（dpm 職業聯賽）以 dpm 為主＝整個換成 dpm 帳號；其餘（LPL/LCK…）以 OBGG 為主＝保留現有再 union 補 dpm。
名單＝現有 soloq_accounts.json 的 (player, team)（即比賽數據出現過的隊伍/選手）。峡谷之巅 dpm 不收，天然過濾。
安全：預設寫到 soloq_accounts.preview.json 並印 diff，不碰現行檔（--apply 才覆寫、先備份 .bak）。best-effort：過不了 Cloudflare 就中止不動檔。
用法：python scripts\\fetch_dpm_soloq_accounts.py         # 產生 preview + diff
      python scripts\\fetch_dpm_soloq_accounts.py --apply # 確認後正式覆寫
"""
import io, sys, json, os, re, time, urllib.parse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ACCOUNTS = os.path.join(HERE, "soloq_accounts.json")
PREVIEW = os.path.join(HERE, "soloq_accounts.preview.json")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
DPM_LEAGUES = ["lcs", "lec", "cblol"]           # 以 dpm 為主的職業聯賽
PLAT = {"NA1": "na1", "KR": "kr", "KR1": "kr", "EUW1": "euw1", "EUN1": "eun1", "BR1": "br1",
        "LA1": "la1", "LA2": "la2", "OC1": "oc1", "TR1": "tr1", "RU": "ru", "JP1": "jp1"}
TODAY = time.strftime("%Y-%m-%d")   # 寫進每筆的 dpmSeen（dpm 選手檔今天確認過這個 riotId）
# 隊碼正規化（僅列已知差異；相同者不需列）。右邊一律是 **load_abbr() 的真縮寫**，一份表兩個用途：
#   ① dpm／OBGG 的隊碼 → 本清單隊碼（LOUD 在 dpm 叫 LLL、Team Liquid 叫 TLAW）
#   ② 清單裡殘留的舊隊碼 → 同一個真縮寫。不收斂的話 (選手,隊) 分組會把同一人拆成兩組互相
#      看不到，帳號各存一份、逐場各抓一份、積分排行榜出現重複列（實測 Aiming 6 列但只有 3 個帳號）。
# ⚠ 方向別寫反：真縮寫是 GEN／TL／KRX／DNS／LOUD（比賽資料 match_roster 給的就是這些），
#    GENG／TLAW／DRX／DNF 才是外來碼。前端 index.html 的 TEAM_ALIAS 是**顯示用**、方向相反
#    （KRX→DRX 顯示成 DRX），兩者不要混為一談。
TEAM_ALIAS = {"GENG": "GEN", "TLAW": "TL", "DRX": "KRX", "DNF": "DNS", "LLL": "LOUD"}
# 使用者本機(localStorage USER_TABBR)改過、但 STATIC_TABBR 仍是舊值的縮寫覆寫（Python 抓不到 localStorage，這裡補）；key=隊全名小寫
ABBR_OVERRIDE = {"fluxo w7m": "FX"}
# 積分頁不列/不抓的選手（已離隊且不再於一級聯賽出場、遭永久禁賽等）；正規化小寫名。
# ⚠ 只擋積分（排位）那一側，**比賽紀錄一律保留**——他打過的職業比賽是既成事實，
#    英雄/選手/戰隊/比賽BP/陣容職業賽都照常收。要同步改 index.html 的 RANK_BL。
# naiyou：2026-08-06 使用者指示，打假賽遭永久禁賽 → 積分與每日戰況都不列。
BLOCK_PLAYERS = {"castle", "naiyou"}


def norm(s):
    return re.sub(r"\s+", "", str(s or "")).lower()


def canon_team(t):
    return TEAM_ALIAS.get(t, t)


def dpm_rank(a):
    """dpm /v1/pros 每帳號附帶的牌位(ranks[0])→存起來；Riot account-v1 查不到舊 riotId(改名等)時，fetch_soloq.py 拿它當備援。"""
    rk = ((a.get("ranks") or [{}])[0]) or {}
    return {"tier": rk.get("tier"), "rank": rk.get("rank"), "lp": rk.get("leaguePoints")} if rk.get("tier") else None


def match_players():
    """比賽數據(data_2026.js)裡實際出場過的選手名(正規化 set)——只重抓這些人，教練/替補等沒出場的不抓（使用者定案 2026-07-20）。"""
    s = set()
    try:
        d0 = open(os.path.join(ROOT, "data", "data_2026.js"), encoding="utf-8", errors="replace").read()
        J = json.loads(re.sub(r";\s*$", "", re.search(r"window\.LOL_DATA\s*=\s*(\{.*)", d0, re.S).group(1)))
        raw = J["tabs"]["RAW_DATA"]; hdr = raw[0]; C = {h: i for i, h in enumerate(hdr)}
        bi, ri, pi = C.get("blue_playername"), C.get("red_playername"), C.get("participantid")
        for r0 in raw[1:]:
            try:
                if not (1 <= int(r0[pi]) <= 5):
                    continue
            except Exception:
                continue
            for i2 in (bi, ri):
                if i2 is not None and i2 < len(r0) and r0[i2]:
                    s.add(norm(r0[i2]))
    except Exception as e:
        print(f"（比賽數據出場名單載入失敗：{e}）", flush=True)
    return s


def load_abbr():
    """從 index.html 抽 STATIC_TABBR（隊全名→縮寫）＋ ABBR_OVERRIDE，供 Python 端算隊縮寫（localStorage 的 USER_TABBR 抓不到）。"""
    st = {}
    # 用 regex 抽 "全名":"縮寫" 配對，**不要 json.loads**——STATIC_TABBR 內含 JS 註解(// …)，
    # json 會整塊解析失敗而靜默退回「壓縮全名前5字」，產生 TOPES/THUND/ANYON 這種假隊碼，
    # 使得那些帳號在前端永遠查不到（2026-07-29 修；每天的 update_log 其實都印了這行警告）。
    pair = lambda s: re.findall(r'"([^"]+)"\s*:\s*"([^"]*)"', s)
    try:
        html = open(os.path.join(ROOT, "index.html"), encoding="utf-8", errors="replace").read()
        m = re.search(r"const STATIC_TABBR=\{(.*?)\};", html, re.S)
        if m:
            st = {k.strip().lower(): v for k, v in pair(m.group(1)) if v}
    except Exception as e:
        print(f"（STATIC_TABBR 載入失敗：{e}）", flush=True)
    # 前端 abbrOf 是多層鏈（STATIC → PROMO → WIKI → LP），Python 端也要吃齊，否則涵蓋率遠不如前端
    for fn in ("promo_abbr.js", "team_abbr_wiki.js", "leaguepedia.js"):
        p = os.path.join(ROOT, fn)
        if not os.path.exists(p):
            continue
        try:
            body = open(p, encoding="utf-8", errors="replace").read()
            if fn == "leaguepedia.js":                       # 只取 LP_TABBR 那一段
                mm = re.search(r"LP_TABBR\s*=\s*\{(.*?)\};", body, re.S)
                body = mm.group(1) if mm else ""
            for k, v in pair(body):
                if v and len(v) <= 8:
                    st.setdefault(k.strip().lower(), v)
        except Exception as e:
            print(f"（{fn} 縮寫表載入失敗：{e}）", flush=True)
    st.update({k.lower(): v for k, v in ABBR_OVERRIDE.items()})
    print(f"  隊縮寫對照表：{len(st)} 筆", flush=True)
    return st


def fix_legacy_team_codes(acc, abbr, fullnames=None):
    """自癒：把過去因對照表載入失敗而寫進去的「全名前5字」假隊碼改回真縮寫。
    截斷碼是可反推的（同一套算法），唯一對應時才改，避免誤判。
    fullnames＝主資料實際出現過的隊全名；**只用這些來反推**，否則 wiki 表裡的青訓隊會造成歧義
    （Top Esports / Top Esports Challenger 前 5 字都是 TOPES → 不唯一就永遠修不掉）。"""
    valid = {str(v).upper() for v in abbr.values() if v}   # 真正在用的縮寫，一律不動（GEN/TL/KRX/DNS 等都在裡面；GENG/TLAW/DRX/DNF 不在，那些走 TEAM_ALIAS）
    src = {f.lower(): abbr.get(f.lower()) for f in (fullnames or [])} if fullnames else abbr
    trunc = {}
    for full, ab in src.items():
        if not ab:
            continue
        t = re.sub(r"[^A-Za-z0-9]", "", full)[:5].upper()
        if len(t) == 5 and t not in valid and t != ab.upper():   # 只認「長度剛好 5 且不是任何已知縮寫」的截斷碼
            trunc.setdefault(t, set()).add(ab)
    fixed = {}
    for a in acc:
        tm = str(a.get("team") or "")
        cand = trunc.get(tm.upper()) if len(tm) == 5 and tm.upper() not in valid else None
        if len(cand or ()) == 1:
            new = next(iter(cand))
            if new != tm:
                a["team"] = new
                fixed[tm] = new
    if fixed:
        print("  修正假隊碼：" + "、".join(f"{k}→{v}" for k, v in sorted(fixed.items())), flush=True)
    return acc


def match_roster(abbr):
    """比賽數據(data_2026.js)每位出場選手 → 我方隊縮寫。隊縮寫＝隊全名經 STATIC_TABBR 換算；取該選手**最後一次出場（依日期）**的隊。
    ⚠ 2026-08-17 修：以前用「列的先後」當最近，但主資料不是嚴格照日期排（KeSPA 盃 12 月的列在檔尾、gol.gg 補檔在後面），
       Flandre/fengyue/Jiwoo 會被指到早就離開的隊、Seany/Kati/RayFarky 被指到國家隊。改成比日期，
       且**國家隊（(National Team)／KeSPA 國家隊）只在該選手今年沒打任何俱樂部時才算**。回 {選手名: 隊縮寫}。"""
    out = {}
    try:
        d0 = open(os.path.join(ROOT, "data", "data_2026.js"), encoding="utf-8", errors="replace").read()
        J = json.loads(re.sub(r";\s*$", "", re.search(r"window\.LOL_DATA\s*=\s*(\{.*)", d0, re.S).group(1)))
        raw = J["tabs"]["RAW_DATA"]; hdr = raw[0]; Cc = {h: i for i, h in enumerate(hdr)}
        bp, rp, pi = Cc.get("blue_playername"), Cc.get("red_playername"), Cc.get("participantid")
        bt, rt, di = Cc.get("blue_teamname"), Cc.get("red_teamname"), Cc.get("date")
        best = {}   # 選手 → (是否俱樂部, 日期, 隊碼)：俱樂部優先、再比日期
        for r0 in raw[1:]:
            try:
                if not (1 <= int(r0[pi]) <= 5):
                    continue
            except Exception:
                continue
            d = str(r0[di] or "")[:16] if (di is not None and di < len(r0)) else ""
            for pcol, tcol in ((bp, bt), (rp, rt)):
                if pcol is None or tcol is None or pcol >= len(r0) or not r0[pcol]:
                    continue
                full = str(r0[tcol] if (tcol is not None and tcol < len(r0)) else "").strip()
                ab = abbr.get(full.lower(), "") or re.sub(r"[^A-Za-z0-9]", "", full)[:5].upper()
                club = 0 if re.search(r"national team|\(national\)|國家隊", full, re.I) else 1
                k = str(r0[pcol]).strip()
                cand = (club, d, ab)
                if k not in best or cand > best[k]:
                    best[k] = cand
        out = {k: v[2] for k, v in best.items()}
    except Exception as e:
        print(f"（match_roster 失敗：{e}）", flush=True)
    return out


def _rekey_files(mapping):
    """轉隊後把逐場檔（soloq_matches/pN.js）內部宣告的 "舊隊|選手" 鍵改成新隊，否則索引裡變孤兒
    （每日戰況同一人兩列、積分頁點不進去）。索引由檔案內部鍵重建，改鍵後跑 build_soloq_index 即可。"""
    import glob, subprocess
    outdir = os.path.join(ROOT, "soloq_matches")
    n = 0
    for fp in glob.glob(os.path.join(outdir, "p*.js")):
        try:
            with open(fp, encoding="utf-8") as f:
                head = f.read(400)
            m = re.match(r'window\.__sqLoad\((".*?"),', head, re.S)
            if not m:
                continue
            key = json.loads(m.group(1))
            if key not in mapping:
                continue
            body = open(fp, encoding="utf-8").read()
            new_head = "window.__sqLoad(" + json.dumps(mapping[key], ensure_ascii=False) + ","
            body = new_head + body[len(m.group(0)):]
            open(fp, "w", encoding="utf-8").write(body)
            n += 1
            print(f"  逐場檔改鍵：{os.path.basename(fp)} {key} → {mapping[key]}", flush=True)
        except Exception as e:
            print(f"  （逐場檔改鍵失敗 {os.path.basename(fp)}：{e}）", flush=True)
    if n:
        try:
            subprocess.run([sys.executable, os.path.join(HERE, "build_soloq_index.py")], check=False)
        except Exception as e:
            print(f"（索引重建失敗：{e}）", flush=True)


def _launch(p):
    for kw in ({"channel": "chrome"}, {"channel": "msedge"}, {}):
        try:
            return p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"], **kw)
        except Exception:
            continue
    raise RuntimeError("找不到可用瀏覽器")


def _warm(pg):
    for wait in (4, 14, 25, 20):
        time.sleep(wait)
        try:
            st = pg.evaluate("async()=>{const r=await fetch('/v1/esport/soloq/top-teams');return r.status;}")
        except Exception:
            st = 0
        if st == 200:
            return True
        print(f"  Cloudflare 盤查中（{st}），續等…", flush=True)
    return False


def main():
    apply = "--apply" in sys.argv
    acc = json.load(open(ACCOUNTS, encoding="utf-8"))
    ABBR = load_abbr()
    _fulls = set()
    try:      # 主資料出現過的隊全名（反推截斷碼用；避免青訓隊造成前 5 字歧義）
        _d0 = open(os.path.join(ROOT, "data", "data_2026.js"), encoding="utf-8", errors="replace").read()
        _J = json.loads(re.sub(r";\s*$", "", re.search(r"window\.LOL_DATA\s*=\s*(\{.*)", _d0, re.S).group(1)))
        _raw = _J["tabs"]["RAW_DATA"]; _h = _raw[0]
        _bt, _rt = _h.index("blue_teamname"), _h.index("red_teamname")
        for _r in _raw[1:]:
            for _i in (_bt, _rt):
                if _r[_i]:
                    _fulls.add(str(_r[_i]).strip())
    except Exception as _e:
        print(f"（隊全名清單載入失敗：{_e}）", flush=True)
    acc = fix_legacy_team_codes(acc, ABBR, _fulls)   # 先把舊的假隊碼(TOPES/THUND…)改回真縮寫，否則同一選手會被拆成兩隊
    # 舊隊碼收斂（2026-08-07）：同一隊在清單裡有兩個碼(DNF/DNS、KRX/DRX)時，下面的 (選手,隊)
    # 分組會把同一人拆成兩組互相看不到 → 帳號各存一份、逐場各抓一份、積分排行榜出現重複列
    # （實測 DRX Aiming 6 列但其實只有 3 個帳號）。只在目標是 load_abbr() 的真縮寫時才換，
    # 對照表寫錯也只會是 no-op。
    _valid_ab = {str(v).upper() for v in ABBR.values() if v}
    _ren = {}
    for a in acc:
        t0 = str(a.get("team") or "")
        t1 = canon_team(t0)
        if t1 != t0 and t1.upper() in _valid_ab:
            a["team"] = t1
            _ren[t0] = t1
    if _ren:
        print("  舊隊碼收斂：" + "、".join(f"{k}→{v}" for k, v in sorted(_ren.items())), flush=True)
    # ── 轉隊跟著比賽資料走（2026-08-17 全面檢視發現 5 位：Ceos SR→PNG、Kaze/Rabelo RED→LOUD、Kaiwing VKS→GZ、Aria DFM→SHG）──
    #    帳號檔只記「第一次抓到時的隊」，選手季中換隊後名單分組還是 (選手,舊隊)，dpm 也就一直用舊隊碼寫回；
    #    積分頁的隊伍欄／賽區篩選都拿帳號檔的隊碼 → 顯示在舊隊底下＝抓錯隊。
    #    規則：該選手在比賽資料裡「最後出賽的隊」≠帳號檔的隊 → 整批改到新隊；只在**同名選手全站唯一**時做
    #    （同名不同人如 TL Morgan／BRION Morgan 各自有自己的隊，不動）。逐場檔的鍵在寫檔後一併改（見 _rekey_files）。
    _mr0 = match_roster(ABBR)
    _mr_ci = {}
    for _pl, _ab in _mr0.items():
        _mr_ci.setdefault(norm(_pl), set()).add(_ab)
    _acc_teams = {}
    for a in acc:
        _acc_teams.setdefault(norm(a.get("player")), set()).add(str(a.get("team") or ""))
    REKEY = {}   # "舊隊|選手" → "新隊|選手"（逐場檔改鍵用）
    for a in acc:
        n0 = norm(a.get("player")); t0 = str(a.get("team") or "")
        cur = _mr_ci.get(n0)
        if not cur or len(cur) != 1 or len(_acc_teams.get(n0, ())) != 1:
            continue                                   # 今年沒出場／同名多隊／帳號檔同名多隊 → 不猜
        t1 = next(iter(cur))
        if not t1 or canon_team(t1) == canon_team(t0):
            continue
        a["team"] = t1
        REKEY[t0 + "|" + a.get("player")] = t1 + "|" + a.get("player")
    if REKEY:
        print("  轉隊改隊碼：" + "、".join(f"{k}→{v.split('|')[0]}" for k, v in sorted(REKEY.items())), flush=True)
    # 名單＝現有 (player, team)（比賽數據出現過的）；記住既有帳號供 union / 保留
    roster = []
    seen_pt = set()
    exist_by_pt = {}
    for a in acc:
        pl, tm = a.get("player"), a.get("team")
        if not pl or not tm:
            continue
        exist_by_pt.setdefault((pl, tm), []).append(a)
        if (pl, tm) not in seen_pt:
            seen_pt.add((pl, tm)); roster.append((pl, tm))
    print(f"名單：{len(roster)} 位選手（{len(acc)} 個現有帳號）", flush=True)

    KEEP_WL = {"theshy"}  # 特例白名單：復出中/沒出場也保留（使用者判例，與 index.html 積分顯示 _WL 一致）
    # 【2026-07-29 收回】曾用 OBGG 現役名冊(csv_cache/obgg_roster.json)豁免「今年沒出賽」的替補，
    # 但 OBGG 的隊伍名單會留著已離開職業的人（TW BeanJ／Glory 今年 0 場仍掛在隊上），
    # 導致他們被抓進積分資料、出現在每日戰況。使用者定案：**今年沒打職業就不該列**。
    # 替補一旦上場，隔天排程的「探索新增」就會自動補帳號，不需要預先保留。
    mp = match_players()
    if mp:
        def _played(pl):
            n = norm(pl)
            if n in mp or n in KEEP_WL:
                return True
            return norm(re.sub(r"\s*\(.*\)\s*$", "", pl)) in mp   # 去「(VN)」等後綴再比對，免誤丟
        before = len(roster)
        dropped = [pt for pt in roster if not _played(pt[0])]
        roster = [pt for pt in roster if _played(pt[0])]
        print(f"比賽數據出場過濾：{before} → {len(roster)} 位（丟棄 {len(dropped)} 位沒出場："
              f"{[t + '|' + p for p, t in dropped][:20]}{'…' if len(dropped) > 20 else ''}）", flush=True)
    else:
        print("⚠ 比賽數據出場名單空 → 不過濾（保險）", flush=True)

    # ── 探索抓取（根因修正）：以前名單只含既有帳號→沒帳號的隊(Fluxo/LOUD/多數 LCS/LEC/LTA)永遠漏抓。
    #    這裡把「比賽出場但目前完全沒帳號」的選手補進名單，DPM 逐一查 /v1/pros 補帳號 ──
    # ABBR 已於開頭載入
    mr = match_roster(ABBR)  # {選手名: 我方隊縮寫}
    covered = {norm(a.get("player")) for a in acc}
    roster = [pt for pt in roster if norm(pt[0]) not in BLOCK_PLAYERS]   # 封鎖名單(已離隊/退出一級)不抓
    new_players = []
    for pl, ab in mr.items():
        n = norm(pl)
        if n in covered or n in BLOCK_PLAYERS:
            continue
        pt = (pl, ab)
        if pt in seen_pt:
            continue
        seen_pt.add(pt); roster.append(pt); new_players.append(pt)
    print(f"探索新增 {len(new_players)} 位無帳號的出場選手：{[t + '|' + p for p, t in new_players][:30]}{'…' if len(new_players) > 30 else ''}", flush=True)

    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("（未安裝 playwright，略過）"); return

    dpm_by_pt = {}      # (player, team) -> [dpm 帳號 entries]
    dpm_primary = set()  # dpm 為主的隊碼（本清單碼）
    with sync_playwright() as p:
        b = _launch(p); pg = b.new_page(user_agent=UA)
        pg.goto("https://dpm.lol/", wait_until="domcontentloaded")
        if not _warm(pg):
            print("✗ 過不了 Cloudflare，中止（不動檔）"); b.close(); return

        for lg in DPM_LEAGUES:
            try:
                tt = pg.evaluate("async(u)=>{const r=await fetch(u);return r.ok?await r.json():null;}",
                                 f"/v1/esport/soloq/top-teams?league={lg}")
            except Exception:
                tt = None
            for t in (tt or []):
                dpm_primary.add(canon_team(t.get("team")))
        print(f"dpm 為主隊伍（{len(dpm_primary)}）：{sorted(dpm_primary)}", flush=True)

        n_hit = n_miss = 0
        for i, (pl, tm) in enumerate(roster, 1):
            # dpm /v1/pros 區分大小寫：比賽數據常是小寫(ceo/xyno)但 dpm 顯示名是 Ceo/Xyno → 查無時自動試大小寫變體
            plist, _tried = [], []
            for _v in (pl, pl[:1].upper() + pl[1:], pl.title(), pl.upper(), pl.lower()):
                if not _v or _v in _tried:
                    continue
                _tried.append(_v)
                try:
                    j = pg.evaluate("async(u)=>{const r=await fetch(u);return r.ok?await r.json():null;}",
                                    "/v1/pros/" + urllib.parse.quote(_v, safe=""))
                except Exception:
                    j = None
                plist = [a for a in ((j or {}).get("players") or []) if a.get("puuid") and a.get("gameName") and a.get("tagLine")]
                if plist:
                    break
            teams_seen = {canon_team(a.get("team")) for a in plist}
            if tm in teams_seen:
                use_as = [a for a in plist if canon_team(a.get("team")) == tm]   # 精確隊碼相符優先
            elif len(teams_seen) == 1:
                use_as = plist                                                   # 同名只有一位職業選手→直接採用(縮寫跟 DPM 對不上也抓得到)
            else:
                use_as = []                                                      # 同名跨多隊且無一相符→無法安全消歧，跳過(避免抓錯人)
            # dpmSeen＝dpm 選手檔（/v1/pros）今天確認過「這個 riotId 現在就是他的名字」。
            # 用途見 fetch_soloq_update.py / fetch_soloq.py 的改名回寫：那兩支拿到的名字來源
            # 是「某一場比賽的參賽者名」或「用舊 puuid 反查」，都可能是過期快照，不可以蓋掉
            # 今天才由選手檔確認過的名字（Zeus 改名後被蓋回舊名就是這樣來的）。
            ents = [{"player": pl, "team": tm,
                     "platform": PLAT.get(a.get("platform"), str(a.get("platform") or "").lower()),
                     "riotId": f"{a.get('gameName')}#{a.get('tagLine')}", "dpmPuuid": a.get("puuid"),
                     "dpmRank": dpm_rank(a), "dpmSeen": TODAY} for a in use_as]
            # 去重（同 riotId）
            uniq = {}
            for e in ents:
                uniq.setdefault(norm(e["riotId"]), e)
            dpm_by_pt[(pl, tm)] = list(uniq.values())
            if uniq:
                n_hit += 1
            else:
                n_miss += 1
            if i % 25 == 0:
                print(f"  ...{i}/{len(roster)}（命中 {n_hit}）", flush=True)
            time.sleep(0.5)
        b.close()
    print(f"dpm /v1/pros：命中 {n_hit} 位、查無 {n_miss} 位", flush=True)

    # 重建：dpm 為主隊→整換 dpm；其餘→union（保留現有再補 dpm）
    new_acc = []
    replaced = added = kept = 0
    diff_lines = []
    ORPHANS = []   # union 分支裡「dpm 有這位選手的檔、卻不含這隻帳號」的既有帳號 → 用 /v1/players/{puuid} 查 dpm 認為它是誰的
    for (pl, tm) in roster:
        existing = exist_by_pt.get((pl, tm), [])   # 探索新增的選手沒有既有帳號→空清單(union 分支會把 dpm 帳號整批補上)
        dpm_ents = dpm_by_pt.get((pl, tm), [])
        old_rids = {norm(e["riotId"]) for e in existing}
        if tm in dpm_primary and dpm_ents:
            use = dpm_ents
            new_rids = {norm(e["riotId"]) for e in use}
            if old_rids != new_rids:
                replaced += 1
                diff_lines.append(f"  [換] {tm}|{pl}: {sorted(old_rids)} → {[e['riotId'] for e in use]}")
        else:
            dbr = {norm(e["riotId"]): e for e in dpm_ents}
            dbp = {e["dpmPuuid"]: e for e in dpm_ents if e.get("dpmPuuid")}
            use = []
            for e in existing:                     # union：保留舊帳號，但同帳號若 dpm 也有→補上新的 dpmRank/dpmPuuid(舊帳號常缺)
                e = dict(e)
                de = dbr.get(norm(e["riotId"]))
                dp = dbp.get(e.get("dpmPuuid") or "")
                # ⚠ 2026-08-17 全面檢視：帳號檔可能存著「名字對、puuid 卻是另一隻」的錯配（DNS Clozer 的 Maldives#0727 掛著
                #    舊帳號 인천물주먹 的 puuid → 逐場一直抓到 2025-10 就停、--missing 補回 0 場）。以前這裡只在缺 puuid 時才補，
                #    錯配永遠不會被修。改成 **dpm 今天回報的 name↔puuid 為準**：
                #    ① 我方 puuid 在 dpm 名下但名字不同 → 帳號改過名，riotId 回寫成 dpm 現名（舊名若 dpm 也另有一隻，下面會補進來）
                #    ② 我方名字在 dpm 名下但 puuid 不同、且我方 puuid dpm 不認 → puuid 錯配，換成 dpm 的
                #    ③ 名字／puuid dpm 都不認 → 留著（OBGG 才有的小號），但記下來給後面查歸屬（/v1/players/{puuid} 的 displayName）
                if dp and norm(dp["riotId"]) != norm(e["riotId"]):
                    diff_lines.append(f"  [改名] {tm}|{pl}: {e['riotId']} → {dp['riotId']}（同 puuid，dpm 現名）")
                    e["riotId"] = dp["riotId"]; e["platform"] = dp.get("platform") or e.get("platform")
                    de = dp
                elif de and de.get("dpmPuuid") and e.get("dpmPuuid") and de["dpmPuuid"] != e["dpmPuuid"] and not dp:
                    diff_lines.append(f"  [錯配] {tm}|{pl}: {e['riotId']} 的 puuid {e['dpmPuuid'][:10]}… ≠ dpm {de['dpmPuuid'][:10]}… → 換成 dpm 的")
                    e["dpmPuuid"] = de["dpmPuuid"]
                if de:
                    e["dpmSeen"] = de.get("dpmSeen")   # dpm 今天仍回報這個名字 → 蓋新日期（沒有 de 就留舊日期，改名回寫的守門自然失效）
                    if de.get("dpmRank"):
                        e["dpmRank"] = de["dpmRank"]
                    if de.get("dpmPuuid") and not e.get("dpmPuuid"):
                        e["dpmPuuid"] = de["dpmPuuid"]
                    e.pop("dpmOwner", None)
                elif e.get("dpmPuuid") and dpm_ents:      # dpm 有這位選手的檔卻不含這隻帳號 → 之後查歸屬
                    ORPHANS.append(e)
                use.append(e)
            seen = {norm(e["riotId"]) for e in use}
            seen_pu = {e.get("dpmPuuid") for e in use if e.get("dpmPuuid")}
            addl = [e for e in dpm_ents if norm(e["riotId"]) not in seen and e.get("dpmPuuid") not in seen_pu]
            if addl:
                use += addl; added += 1
                diff_lines.append(f"  [補] {tm}|{pl}: +{[e['riotId'] for e in addl]}（保留 {len(existing)} 舊）")
            else:
                kept += 1
        # 同一個 dpmPuuid 只留一筆（2026-08-07 修）：改名後 dpm 回的是**新** riotId，
        # 但既有清單裡還留著舊的，而上面只比對 riotId → 兩筆並存。後果：
        #   ・fetch_soloq.py 會拿舊 ID 去查牌位，查到的是「接手舊名的別人」→ found:false 的雜訊
        #     （HLE Zeus 就是這樣：zeus#glgl 與 Athene#lll 同一個 dpmPuuid，牌位掛在舊的那筆上）
        #   ・fetch_soloq_update.py 會用同一個 puuid 白抓兩次（合併時靠時間戳去重才沒重複計算）
        # 保留規則：優先留「dpm 這次回報的 riotId」＝當前名字。
        if use:
            dpm_rids = {norm(e["riotId"]) for e in dpm_ents}
            byp, nopu, dropped = {}, [], []
            for e in use:
                pu = e.get("dpmPuuid")
                if not pu:
                    nopu.append(e); continue
                if pu not in byp:
                    byp[pu] = e; continue
                a0, b0 = byp[pu], e
                keep = b0 if (norm(b0["riotId"]) in dpm_rids and norm(a0["riotId"]) not in dpm_rids) else a0
                byp[pu] = keep; dropped.append(b0 if keep is a0 else a0)
            if dropped:
                diff_lines.append(f"  [併] {tm}|{pl}: 同 puuid 去重 −{[e['riotId'] for e in dropped]}"
                                  f"（留 {[byp[e['dpmPuuid']]['riotId'] for e in dropped]}）")
            use = list(byp.values()) + nopu
        new_acc.extend(use)

    # ── 帳號歸屬複查（2026-08-17）：dpm 有這位選手的檔、卻不含這隻帳號 → 問 dpm 這個 puuid 是誰的
    #    （/v1/players/{puuid} 回 displayName＝dpm 掛牌的職業選手名）。displayName 是**別的職業選手** → 就是張冠李戴
    #    （OBGG／舊搜尋配錯），直接剔除；displayName 空（一般玩家帳號）或就是本人 → 留著。
    if ORPHANS:
        owner_of = {}
        try:
            with sync_playwright() as p2:
                b2 = _launch(p2); pg2 = b2.new_page(user_agent=UA)
                pg2.goto("https://dpm.lol/", wait_until="domcontentloaded")
                if _warm(pg2):
                    for e in ORPHANS:
                        pu = e.get("dpmPuuid")
                        if not pu or pu in owner_of:
                            continue
                        try:
                            j = pg2.evaluate("async(u)=>{const r=await fetch(u);return r.ok?await r.json():null;}", "/v1/players/" + pu)
                        except Exception:
                            j = None
                        owner_of[pu] = (j or {}).get("displayName") if isinstance(j, dict) else None
                        time.sleep(0.25)
                b2.close()
        except Exception as _e:
            print(f"（歸屬複查略過：{_e}）", flush=True)
        bad_owner = []
        for e in ORPHANS:
            o = owner_of.get(e.get("dpmPuuid"))
            if o and norm(o) != norm(e.get("player")) and norm(re.sub(r"\s*\(.*\)\s*$", "", e.get("player") or "")) != norm(o):
                bad_owner.append((e, o))
        if bad_owner:
            _ids = {id(e) for e, _ in bad_owner}
            new_acc = [e for e in new_acc if id(e) not in _ids]
            for e, o in bad_owner:
                diff_lines.append(f"  [歸屬] {e['team']}|{e['player']}: {e['riotId']} dpm 掛牌是「{o}」的帳號 → 剔除")
        print(f"  歸屬複查：{len(ORPHANS)} 隻帳號 dpm 選手檔沒列 → 查到掛牌 {sum(1 for v in owner_of.values() if v)} 隻、其中別人的 {len(bad_owner)} 隻已剔除", flush=True)

    # ── 跨選手清理（2026-08-07 使用者定案）。上面的去重只在同一個 (選手,隊) 內做，
    #    抓錯人造成的「同一個帳號掛在兩位不同選手名下」它看不到。
    #    ① 同 riotId 跨選手 ＝ 其中一位抓錯人。判準＝dpm 這次把它回報在誰名下，只留那位。
    #       實例：May#KR43 同時掛 GZ|Betty 與 OMG|Starry，dpm 只回報給 Betty →
    #       Starry 積分頁顯示的其實是 Betty 的對局（兩人逐場檔都是 381 場）。
    #       Starry 自己的帳號是 May#0411，是靠名字相近被誤配的。
    #    ② 不同 riotId 卻共用同一個 dpmPuuid ＝ 不同帳號不可能是同一個 dpm 身分，
    #       必有一邊是 resolve_obgg_dpmpuuid.py 的 best-effort 搜尋配錯。判不出是哪邊時
    #       **兩邊都清掉** 讓它下一輪重解——留著錯的會讓兩人的逐場互相混入。
    #       實例：KRX|Willer 김정현#Kjh1 與 KT|Bdd 파피몬#1111 共用一個 puuid，兩個名字 dpm 都已不回報。
    cross_lines = []

    def _dpm_has(e):
        return norm(e["riotId"]) in {norm(x["riotId"]) for x in dpm_by_pt.get((e["player"], e["team"]), [])}

    def _pkey(e):
        return e["team"] + "|" + e["player"]

    by_rid = {}
    for e in new_acc:
        by_rid.setdefault(norm(e["riotId"]), []).append(e)
    drop = []
    for _rid, es in by_rid.items():
        if len({e["player"] for e in es}) < 2:
            continue
        ok = [e for e in es if _dpm_has(e)]
        if len(ok) != 1:
            cross_lines.append(f"  [跨] ⚠ 同 riotId {es[0]['riotId']} 跨選手 {[_pkey(x) for x in es]}"
                               f"：dpm 確認 {len(ok)} 筆 → 判不出歸屬，保留不動")
            continue
        rest = [e for e in es if e is not ok[0]]
        # 安全閥：刪到某人一個帳號都不剩就不刪（寧可留著重複也不要讓他整個消失）
        left = {_pkey(e): 0 for e in rest}
        for e in new_acc:
            if _pkey(e) in left and not any(e is r for r in rest):
                left[_pkey(e)] += 1
        if any(v == 0 for v in left.values()):
            cross_lines.append(f"  [跨] ⚠ 同 riotId {es[0]['riotId']} 跨選手 {[_pkey(x) for x in es]}"
                               f"：刪掉會讓 {[k for k, v in left.items() if v == 0]} 沒有任何帳號 → 保留不動")
            continue
        drop += rest
        cross_lines.append(f"  [跨] 同 riotId {es[0]['riotId']} 跨選手 → 留 {_pkey(ok[0])}（dpm 現行歸屬）、"
                           f"刪 {[_pkey(x) for x in rest]}")
    if drop:
        new_acc = [e for e in new_acc if not any(e is d for d in drop)]

    by_pu = {}
    for e in new_acc:
        if e.get("dpmPuuid"):
            by_pu.setdefault(e["dpmPuuid"], []).append(e)
    for pu, es in by_pu.items():
        if len({e["player"] for e in es}) < 2 or len({norm(e["riotId"]) for e in es}) < 2:
            continue
        ok = [e for e in es if _dpm_has(e)]
        victims = [e for e in es if not any(e is o for o in ok)] if len(ok) == 1 else es
        for e in victims:
            e.pop("dpmPuuid", None)
        cross_lines.append(f"  [跨] 不同 riotId 共用 dpmPuuid {pu[:16]}…："
                           f"{[_pkey(x) + ' ' + x['riotId'] for x in es]} → 清掉 {len(victims)} 筆的 dpmPuuid 待重解")

    out = PREVIEW if not apply else ACCOUNTS
    if apply:
        json.dump(acc, open(ACCOUNTS + ".bak", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(new_acc, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if apply and REKEY:
        _rekey_files(REKEY)
    print(f"\n=== 變更摘要 ===", flush=True)
    print(f"  換帳號（dpm 主）: {replaced} 位｜補帳號（union）: {added} 位｜不變: {kept} 位", flush=True)
    print(f"  帳號總數：{len(acc)} → {len(new_acc)}", flush=True)
    for ln in diff_lines[:80]:
        print(ln, flush=True)
    if len(diff_lines) > 80:
        print(f"  …還有 {len(diff_lines) - 80} 條變更", flush=True)
    for ln in cross_lines:      # 跨選手清理筆數少但每一條都要看到，不隨 diff_lines 被截斷
        print(ln, flush=True)
    print(f"\n{'已覆寫 soloq_accounts.json（備份 .bak）' if apply else '→ 寫到 soloq_accounts.preview.json（現行檔未動）。確認後跑 --apply'}", flush=True)


if __name__ == "__main__":
    main()
