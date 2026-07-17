# -*- coding: utf-8 -*-
"""
從逐場檔聚合「每個英雄的核心裝＋主要出裝流派(>=5%)」→ soloq_builds.js（給圖鑑英雄詳情用）。
- core：該英雄所有場最終裝(it)中出現率前 5 的「大裝」(排除鞋/飾品/小裝)，含出裝%。
- paths：從購買順序(ib)抓每場「前 3 件大裝的順序」（該場打輔助＝前 2 件），列出現率 >=5% 的所有序列，各含 場數 n＋勝場 w(→勝率)。
- paths2p：同 paths 但只算「近兩版」場次（版本視窗＝職業賽各版最早比賽日，p2patches 存兩個版本號）。
需要 item.json 分類大裝(gold/into/tags)。免重抓逐場(只讀本機檔)。
fetch_soloq_year.py / update.py 末端可連帶呼叫（跟 build_soloq_index 一樣每日更新）。
用法：  python scripts\build_soloq_builds.py
"""
import os, re, json, glob, urllib.request, datetime, bisect
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
OUTDIR = os.path.join(ROOT, "soloq_matches")
OUT = os.path.join(ROOT, "soloq_builds.js")
MIN_GAMES = 15  # 少於這場數不輸出(樣本不足)
CHAMP_FIX = {"FiddleSticks": "Fiddlesticks"}  # dpm名→DDragon id(其餘已一致)
TRINK = {1104, 3330, 3340, 3348, 3349, 3363, 3364, 3513, 6702}  # 飾品(眼)：起手裝排除
SUP_LINE = {3865, 3866, 3867, 3869, 3870, 3871, 3876, 3877}  # 世界地圖支援線(dpm startItems/itemActions 抓不到，只在 itemIds)
SUP_START = 3865  # 世界地圖(起手支援裝)
SUP_LEG = {3869, 3870, 3871, 3876, 3877}  # 完成的支援傳奇裝(輔助道具裝)：輔助的「起手裝」欄改顯示他完成哪件
CORE_EXCLUDE = {3041}  # 靈魂竊取者(梅賈滾雪球裝)：不計入核心裝與出裝流派
COREP_MINWIN = 10  # 版本趨勢用「前三版核心裝」：視窗場數少於此不判定(樣本不足)

def round_pcts(pairs):
    """互斥選項（起手裝：一場只買一件）的百分比取整——用最大餘數法，讓顯示整數加總＝四捨五入後總和。
    避免各自 round() 後加總 >100%（Skarner 三寵物 64.6+22.7+12.7 各自進位變 65+23+13=101%）。"""
    if not pairs:
        return []
    tgt = round(sum(p for _, p in pairs))            # 目標總和（真實總和 ≤100 → tgt ≤100）
    fl = [[i, int(p), p - int(p)] for i, p in pairs]  # [id, 無條件捨去, 小數餘數]
    need = tgt - sum(x[1] for x in fl)                # 還差幾個 +1 才到 tgt
    for k in sorted(range(len(fl)), key=lambda k: -fl[k][2])[:max(0, need)]:
        fl[k][1] += 1                                 # 餘數最大的先 +1
    return [{"id": i, "pct": p} for i, p, _ in fl]

def patch_key(pstr):  # 版本字串→可排序鍵，"26.10">"26.9"("26.9"其實不會出現，patch 一律兩位小數)
    try:
        a, b = str(pstr).split(".")[:2]; return (int(a), int(b))
    except Exception:
        return (0, 0)

def _date_of(t_ms):  # 積分逐場只有 epoch 毫秒時間戳→UTC 日期(YYYY-MM-DD)；版本視窗以「日」為界，時區級誤差不影響 10% 核心判定
    if not t_ms: return None
    try:
        return datetime.datetime.utcfromtimestamp(t_ms / 1000).strftime("%Y-%m-%d")
    except Exception:
        return None

def load_patch_bounds():
    """從職業賽資料(data/data_*.js)推導每個版本「最早出現的比賽日期」。
    用真實比賽日當版本分界，避開硬猜各伺服器改版時差(使用者叮囑：以伺服器公告時間為主)。
    回傳 {版本字串: 最早日期YYYY-MM-DD}。"""
    start = {}
    ddir = os.path.join(ROOT, "data")
    for fp in glob.glob(os.path.join(ddir, "data_*.js")):
        try:
            txt = open(fp, encoding="utf-8").read()
            txt = txt[txt.index("=") + 1:].rstrip()
            if txt.endswith(";"): txt = txt[:-1]
            tbl = json.loads(txt)["tabs"]["RAW_DATA"]
        except Exception:
            continue
        hdr = tbl[0]
        if "date" not in hdr or "patch" not in hdr: continue
        di = hdr.index("date"); pi = hdr.index("patch")
        for r in tbl[1:]:
            d = str(r[di])[:10]; pv = str(r[pi]).strip()
            if not d or "." not in pv: continue
            if pv not in start or d < start[pv]: start[pv] = d
    return start

PDATE_CACHE = os.path.join(ROOT, "csv_cache", "patch_dates.json")

def official_patch_dates(pks):
    """官方 patch-notes 標籤頁 __NEXT_DATA__ → {pk:'YYYY-MM-DD'}（各版公告「發布日」，一次抓全部、快取只補缺）。
    「近兩版」視窗要用真實發布日：職業賽首戰日會漏掉職業圈跳過的版本（如 26.12），積分玩家則是改版當天就上新版。"""
    got = json.load(open(PDATE_CACHE, encoding="utf-8")) if os.path.exists(PDATE_CACHE) else {}
    if all(p in got for p in pks):
        return got
    SLUG = re.compile(r"patch-(\d+)-(\d+)-notes$")   # s1 分季格式(patch-25-s1-2)不會匹配→略過，這裡只需常規版
    def slug_in(o):                                  # 物件子樹裡找 patch slug（url 欄位名稱各層不一，通掃字串）
        if isinstance(o, str):
            mm = re.search(r"patch-[a-z0-9-]+-notes", o); return mm.group(0) if mm else None
        for v in (o.values() if isinstance(o, dict) else (o if isinstance(o, list) else ())):
            r = slug_in(v)
            if r: return r
        return None
    def walk(o):                                     # 有 publishedAt 的物件＝一篇文章卡片 → 配對其子樹裡的 slug
        if isinstance(o, dict):
            pub = o.get("publishedAt") or o.get("firstPublishedAt")
            if isinstance(pub, str) and len(pub) >= 10:
                s = slug_in(o); mm = SLUG.search(s) if s else None
                if mm:
                    maj, mi = int(mm.group(1)), int(mm.group(2))
                    yy = maj + 10 if maj <= 14 else maj      # 舊序號版→年份%100，對齊 patch key
                    got.setdefault(f"{yy}.{mi:02d}", pub[:10])
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    try:
        req = urllib.request.Request("https://www.leagueoflegends.com/zh-tw/news/tags/patch-notes/",
                                     headers={"User-Agent": "Mozilla/5.0"})
        h = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
        m = re.search(r'id="__NEXT_DATA__"[^>]*>(\{.*?\})</script>', h, re.S)
        walk(json.loads(m.group(1)))
        json.dump(got, open(PDATE_CACHE, "w", encoding="utf-8"))
    except Exception as e:
        print(f"⚠ 官方發布日抓取失敗（{e}），近兩版視窗退回職業賽首戰日")
    return got

def season_patches():
    """patches.js(官方公告) 的版本鍵 → 當季(最新 major)的版本序列。職業賽跳過的版本(26.12)也在內。"""
    try:
        txt = open(os.path.join(ROOT, "patches.js"), encoding="utf-8").read()
        pks = sorted({k for k in re.findall(r'"(\d{2}\.\d{2})":\{', txt)}, key=patch_key)
        if not pks: return []
        maj = pks[-1].split(".")[0]
        return [p for p in pks if p.split(".")[0] == maj]
    except Exception:
        return []

def load_items():
    ver = json.load(urllib.request.urlopen("https://ddragon.leagueoflegends.com/api/versions.json"))[0]
    data = json.load(urllib.request.urlopen(f"https://ddragon.leagueoflegends.com/cdn/{ver}/data/en_US/item.json"))["data"]
    leg = set(); excl = set(); boots = set(); gold = {}  # leg=大裝, excl=起手排除(飾品+消耗), boots=鞋, gold=各裝總價(選單一起手裝用)
    for i, v in data.items():
        g = v.get("gold", {}); tg = v.get("tags", [])
        gold[int(i)] = g.get("total", 0)
        if "Trinket" in tg or "Consumable" in tg: excl.add(int(i))
        if "Boots" in tg and g.get("purchasable"): boots.add(int(i))
        if g.get("purchasable") and not v.get("into") and g.get("total", 0) >= 1100 and "Boots" not in tg and "Trinket" not in tg:
            leg.add(int(i))
    # 鞋子升級版→基礎鞋 對照(合併計算、以基礎鞋當圖)：① 升級鞋(from 內含 T2 鞋) ② 同名不同ID(早期500g版)
    t2 = {i for i in boots if 1001 in [int(x) for x in data.get(str(i), {}).get("from", [])]}  # T2鞋(由 1001 升上來)
    boot_base = {}
    for i in boots:
        b = [x for x in [int(x) for x in data.get(str(i), {}).get("from", [])] if x in t2]
        if b: boot_base[i] = b[0]  # 升級鞋(如 不朽之道/快速行軍)→T2 基礎鞋
    by_name = defaultdict(list)
    for i in boots: by_name[data[str(i)]["name"]].append(i)
    for _nm, ids in by_name.items():  # 同名不同ID(如 223006↔3006)→標準版(3000~3299)
        std = [x for x in ids if 3000 <= x < 3300]; canon = min(std) if std else min(ids)
        for x in ids:
            if x != canon and x not in boot_base: boot_base[x] = canon
    def _resolve(x):  # 攤平多層鏈
        seen = set()
        while x in boot_base and x not in seen: seen.add(x); x = boot_base[x]
        return x
    boot_base = {k: _resolve(k) for k in boot_base}
    return leg, excl, boots, boot_base, gold

def main():
    leg, EXCL, BOOTS, BOOT_BASE, GOLD = load_items(); leg -= CORE_EXCLUDE  # 排除滾雪球裝(靈魂竊取者)不當核心裝/流派
    pstart = load_patch_bounds(); uni = sorted(pstart.keys(), key=patch_key)  # 版本→最早比賽日、版本序(供「前三版核心裝」coreP)
    sp = season_patches()                            # 近兩版＝官方公告當季最新兩版(職業賽跳過的版本也算，如 26.12)
    p2v = sp[-2:] if len(sp) >= 2 else (sp or uni[-2:])
    pdates = official_patch_dates(p2v) if p2v else {}
    # 視窗起日：次新版本的「官方公告發布日」(含)之後全算近兩版；抓不到才退回職業賽首戰日
    p2lo = (pdates.get(p2v[0]) or pstart.get(p2v[0]) or (pstart[uni[-2]] if len(uni) >= 2 else None)) if p2v else None
    print(f"大裝 {len(leg)} / 鞋 {len(BOOTS)} / 起手排除 {len(EXCL)}｜版本界 {len(uni)} 版（{uni[0] if uni else '—'}～{uni[-1] if uni else '—'}）｜近兩版視窗 {p2v}（{p2lo}～）")
    games = Counter(); core = defaultdict(Counter); paths = defaultdict(Counter); pathW = defaultdict(Counter)
    runeCount = defaultdict(Counter)  # 符文keystone -> 英雄 -> 場數
    runePage = defaultdict(Counter); runePageW = defaultdict(Counter)  # 英雄 -> 符文排列(主4+副3) -> 場數/勝場：圖鑑英雄詳情「符文排列」前三
    bootCount = defaultdict(Counter)  # 鞋子
    startLane = defaultdict(lambda: defaultdict(Counter)); laneGames = defaultdict(Counter)  # 起手裝依路線分
    supLeg = defaultdict(Counter)  # 英雄 -> 完成的支援傳奇裝(輔助道具裝) -> 場數
    # 英雄分頁「積分數據版」彙總：英雄 -> 路線 -> [n,w,k,d,a,cs,dur秒,kp和,kp樣本, gd樣本,gd和, xd樣本,xd和, fl2樣本,fl2先到]
    heroAgg = defaultdict(lambda: defaultdict(lambda: [0] * 15))
    # 每版本彙總（積分模式的版本篩選；積分改版當天就上新版，界線用官方公告發布日，抓不到才退職業賽首戰日）
    heroAggP = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0] * 15)))  # 英雄 -> 版本 -> 路線 -> 同上15欄
    _pdAll = official_patch_dates(sp) if sp else {}
    _bounds = sorted([((_pdAll.get(p) or pstart.get(p)), p) for p in sp if (_pdAll.get(p) or pstart.get(p))])
    _bd = [d for d, _ in _bounds]; _bp = [p for _, p in _bounds]
    def patch_of(t_ms):
        d = _date_of(t_ms)
        if not d or not _bd: return None
        i = bisect.bisect_right(_bd, d) - 1
        return _bp[i] if i >= 0 else _bp[0]
    muCnt = defaultdict(lambda: defaultdict(lambda: [0, 0]))  # 積分對位：英雄 -> 對位英雄 -> [場,勝]（g.o＝dpm 的對位欄）
    suCnt = defaultdict(Counter)                              # 召喚師技能組合：英雄 -> (id小,id大) -> 場數
    ksOpp = defaultdict(lambda: defaultdict(Counter))         # 符文盒「常對到」：英雄 -> keystone -> 對位英雄 -> 場數
    recentCore = defaultdict(list)  # 英雄 -> [(t, (大裝tuple))]：算近100場核心裝
    recentPath = defaultdict(list)  # 英雄 -> [(t, (序列tuple), win)]：算「近兩版」出裝流派(依版本視窗過濾)
    # ── 每路線平行聚合（byLane：多路線英雄的圖鑑出裝卡逐路線分開；單路線英雄不輸出、沿用整體）──
    coreL = defaultdict(lambda: defaultdict(Counter))         # 英雄 -> 路線 -> 大裝 -> 場數
    bootL = defaultdict(lambda: defaultdict(Counter))         # 英雄 -> 路線 -> 基礎鞋 -> 場數
    recentCoreL = defaultdict(lambda: defaultdict(list))      # 英雄 -> 路線 -> [(t, legs)]
    pathsL = defaultdict(lambda: defaultdict(Counter)); pathWL = defaultdict(lambda: defaultdict(Counter))
    recentPathL = defaultdict(lambda: defaultdict(list))
    runePageL = defaultdict(lambda: defaultdict(Counter)); runePageWL = defaultdict(lambda: defaultdict(Counter))
    ksOppL = defaultdict(lambda: defaultdict(lambda: defaultdict(Counter)))  # 英雄 -> 路線 -> keystone -> 對位
    suCntL = defaultdict(lambda: defaultdict(Counter))        # 英雄 -> 路線 -> 召技組合
    corePGames = defaultdict(list)  # 英雄 -> [(t, (該場常用道具tuple))]：算 coreP(版本趨勢用；含大裝＋鞋＋起手裝，如多蘭之盔)
    scanned = 0
    for fp in glob.glob(os.path.join(OUTDIR, "*.js")):
        txt = open(fp, encoding="utf-8").read()
        m = re.match(r'window\.__sqLoad\((.*)\);\s*$', txt, re.S)
        if not m: continue
        _, data = json.loads('[' + m.group(1) + ']')
        for g in data.get("matches", []):
            c = CHAMP_FIX.get(g.get("c"), g.get("c"))
            if not c: continue
            scanned += 1; games[c] += 1; win = 1 if g.get("w") else 0
            _hl = g.get("pos") if g.get("pos") in ("TOP", "MIDDLE", "BOTTOM", "JUNGLE", "UTILITY") else "?"
            _pkm = patch_of(g.get("t") or 0)
            _targets = [heroAgg[c][_hl]] + ([heroAggP[c][_pkm][_hl]] if _pkm else [])
            for _ha in _targets:
                _ha[0] += 1; _ha[1] += win; _ha[2] += g.get("k") or 0; _ha[3] += g.get("de") or 0; _ha[4] += g.get("a") or 0
                _ha[5] += g.get("cs") or 0; _ha[6] += g.get("d") or 0
                if g.get("kp") is not None: _ha[7] += g["kp"]; _ha[8] += 1
                if g.get("gd15") is not None: _ha[9] += 1; _ha[10] += g["gd15"]
                if g.get("xd15") is not None: _ha[11] += 1; _ha[12] += g["xd15"]
                if g.get("fl2") is not None: _ha[13] += 1; _ha[14] += 1 if g["fl2"] else 0
            lk = None if _hl == "?" else _hl  # 每路線聚合的路線鍵（未知路線不入 byLane，仍計整體）
            _opp = CHAMP_FIX.get(g.get("o"), g.get("o"))
            if _opp: _m = muCnt[c][_opp]; _m[0] += 1; _m[1] += win
            _su = [x for x in (g.get("su") or []) if x]
            if len(_su) == 2:
                _sp2 = tuple(sorted(_su)); suCnt[c][_sp2] += 1
                if lk: suCntL[c][lk][_sp2] += 1
            it0 = g.get("it") or []
            legs0 = [i for i in it0 if i in leg]
            for iid in set(legs0):
                core[c][iid] += 1
                if lk: coreL[c][lk][iid] += 1
            recentCore[c].append((g.get("t") or 0, tuple(legs0)))  # 近100場核心裝用
            if lk: recentCoreL[c][lk].append((g.get("t") or 0, tuple(legs0)))
            for iid in set(BOOT_BASE.get(i, i) for i in it0 if i in BOOTS):
                bootCount[c][iid] += 1  # 鞋子(升級版合併到基礎鞋)
                if lk: bootL[c][lk][iid] += 1
            _cpset = set(legs0)  # coreP 用：這場的「常用道具」＝大裝＋鞋(併基礎鞋)＋起手裝(含多蘭之盔等；排除飾品/消耗品)
            _cpset |= {BOOT_BASE.get(i, i) for i in it0 if i in BOOTS}
            _cpset |= {i for i in (g.get("st") or []) if i and i not in EXCL}
            corePGames[c].append((g.get("t") or 0, tuple(_cpset)))
            _runes = set()  # 全符文(關鍵符文＋主/副系＋碎片)：算「最常帶它的英雄」
            if g.get("r"): _runes.add(g["r"])
            for _arr in (g.get("rp"), g.get("rs"), g.get("rst")):
                for _x in (_arr or []):
                    if _x: _runes.add(_x)
            for _rid in _runes: runeCount[_rid][c] += 1
            _rp4 = [x for x in (g.get("rp") or []) if x][:4]; _rs3 = [x for x in (g.get("rs") or []) if x][:3]
            if len(_rp4) >= 4 and len(_rs3) >= 2:  # 完整符文頁才計（主系4＋副系至少2）
                _sig = (tuple(_rp4), tuple(_rs3))
                runePage[c][_sig] += 1; runePageW[c][_sig] += win
                if _opp: ksOpp[c][_rp4[0]][_opp] += 1  # 該 keystone(rp4[0]) 對到的英雄（符文盒頭像列）
                if lk:
                    runePageL[c][lk][_sig] += 1; runePageWL[c][lk][_sig] += win
                    if _opp: ksOppL[c][lk][_rp4[0]][_opp] += 1
            pos = g.get("pos") or "?"  # 起手裝依實際路線各自一組(上/中/下/野/輔)
            if pos in ("TOP", "MIDDLE", "BOTTOM", "JUNGLE", "UTILITY"):
                laneGames[c][pos] += 1
                if pos == "UTILITY":  # 輔助：「起手裝」欄改記錄他完成哪件支援傳奇裝(輔助道具裝)
                    for i in set(x for x in it0 if x in SUP_LEG): supLeg[c][i] += 1
                else:
                    # 起手裝「只買一個」：用「開場 60 秒內買的」判定，每場只計一件。
                    # 為何不用 st 快照：st 會把「升級後」的也算進去（野怪寵物 1101→1102 evolve，st=[1101,1102] 兩隻都在 → 總和 >100%）；
                    # 開場一分鐘內買不起第二件起手裝，所以 ib 前 60 秒的購買才是真正的起手裝（使用者指出的更準做法）。
                    first_min = [iid for (t, iid) in (g.get("ib") or []) if t < 60 and iid not in EXCL and iid in GOLD]
                    if not first_min:  # 舊資料無 ib 時間戳 → 退回 st 快照取總價最高一件
                        first_min = [i for i in (g.get("st") or []) if i not in EXCL and i in GOLD]
                    if first_min:
                        main_st = max(first_min, key=lambda i: (GOLD.get(i, 0), -i))  # 通常只有一件；萬一多件取總價最高（同價 id 較小）
                        startLane[c][pos][main_st] += 1
            need = 2 if pos == "UTILITY" else 3  # 輔助經濟少、常整場只完成兩件大裝 → 流派看前2件；其他路線前3件
            seq = []; seen = set()
            for _t, iid in (g.get("ib") or []):
                if iid in leg and iid not in seen:
                    seen.add(iid); seq.append(iid)
                    if len(seq) >= need: break
            if len(seq) >= need:
                k = tuple(seq); paths[c][k] += 1; pathW[c][k] += win
                recentPath[c].append((g.get("t") or 0, k, win))  # 近100場流派用
                if lk:
                    pathsL[c][lk][k] += 1; pathWL[c][lk][k] += win
                    recentPathL[c][lk].append((g.get("t") or 0, k, win))
    # ── 出裝/符文聚合 helper（整體與 byLane 共用同一套邏輯與門檻，避免兩份漂移）──
    def _core_pack(cnt, nn):  # 核心裝(>=10%) + 剩餘適合裝備(>1% 非核心, 上限15)
        top = [{"id": i, "pct": round(k / nn * 100)} for i, k in cnt.most_common() if k / nn * 100 >= 10]
        ids = {ci["id"] for ci in top}
        rest = [{"id": i, "pct": round(k / nn * 100)} for i, k in cnt.most_common() if k / nn * 100 > 1 and i not in ids][:15]
        return top, rest
    def _boots_pack(cnt, nn):  # 鞋子 >10%(升級版已併入基礎鞋)
        return [{"id": i, "pct": round(k / nn * 100)} for i, k in cnt.most_common() if k / nn * 100 > 10]
    def _recent_core(lst):  # 近兩版核心裝（無版本界資料時退回近100場）
        rc = [x for x in lst if p2lo and (_date_of(x[0]) or "") >= p2lo] if p2lo else sorted(lst, key=lambda x: -x[0])[:100]
        nrc = len(rc); cc = Counter()
        for _t, legs in rc:
            for i in set(legs): cc[i] += 1
        return [{"id": i, "pct": round(k / nrc * 100)} for i, k in cc.most_common() if k / nrc * 100 >= 10] if nrc else []
    def _path_pack(pcnt, pw):  # 主要出裝流派＝出現率>=5%(全列)；無任何達標則至少列最多的一種
        tot = sum(pcnt.values())
        return [{"seq": list(k), "n": cnt, "w": pw[k]} for k, cnt in pcnt.most_common() if tot and cnt / tot * 100 >= 5] \
               or [{"seq": list(k), "n": cnt, "w": pw[k]} for k, cnt in pcnt.most_common(1)]
    def _path_recent(lst):  # 近兩版出裝流派：只算最新兩版視窗內的場；該窗沒場 → 空(前端顯示 —)
        rp = [(t, k, w) for t, k, w in lst if p2lo and (_date_of(t) or "") >= p2lo] if p2lo \
             else sorted(lst, key=lambda x: -x[0])[:100]
        pc = Counter(); pw = Counter()
        for _t, k, w in rp:
            pc[k] += 1; pw[k] += w
        return _path_pack(pc, pw)
    def _runes_ks(pageCnt, pageW, oppMap):  # 前三 keystone(第2/3需≥10場)×各前二配置(第2種≥3場)＋常對到(≥2場,前8)
        ks_games = Counter(); ks_pages = defaultdict(list)
        for _sig, _cnt in pageCnt.items():
            _ks = _sig[0][0]
            ks_games[_ks] += _cnt
            ks_pages[_ks].append((_sig, _cnt, pageW[_sig]))
        out = []
        for _ki, (_ks, _kn) in enumerate(ks_games.most_common(3)):
            if _ki >= 1 and _kn < 10: break
            _vs_all = sorted(ks_pages[_ks], key=lambda x: -x[1])
            _vs = [v for _vi, v in enumerate(_vs_all) if _vi == 0 or v[1] >= 3][:2]
            _kw = sum(_w for _, _, _w in ks_pages[_ks])
            _opps = [o for o, _on in oppMap[_ks].most_common(8) if _on >= 2]
            out.append({"ks": _ks, "n": _kn, "w": _kw, "opp": _opps,
                        "v": [{"rp": list(_s[0]), "rs": list(_s[1]), "n": _c2, "w": _w2} for _s, _c2, _w2 in _vs]})
        return out
    champs = {}
    for c, n in games.items():
        if n < MIN_GAMES: continue
        coreTop, restTop = _core_pack(core[c], n)
        core100 = _recent_core(recentCore[c])
        pathTop = _path_pack(paths[c], pathW[c])
        pathTop2p = _path_recent(recentPath[c])
        startByPos = {}  # 起手裝依實際路線各一組：{pos:{n:場數, items:[{id,pct}]}}；上/中/下/野＝起手裝、輔助＝完成的支援傳奇裝
        for pos in ("TOP", "MIDDLE", "BOTTOM", "JUNGLE", "UTILITY"):
            ln = laneGames[c].get(pos, 0)
            if ln < MIN_GAMES: continue
            src = supLeg[c] if pos == "UTILITY" else startLane[c][pos]
            # 起手裝互斥（一場一件）→ 用最大餘數法取整，加總不會 >100%
            its = round_pcts([(i, cnt / ln * 100) for i, cnt in src.most_common() if cnt / ln * 100 > 10])
            if its: startByPos[pos] = {"n": ln, "items": its}
        bootsTop = _boots_pack(bootCount[c], n)
        # coreP：每個版本各自的「前三版核心裝」——版本趨勢(#4)判定某版道具被增/削時，只有該英雄在此版前三版內把它當核心裝(≥10%)才標記。
        # 例：26.13 砍無盡→往前看 26.10/11/12 積分數據算核心裝。視窗以「該版前三個職業賽版本的起日～該版起日」的比賽日期界定(交集不受內部版本邊界精度影響)。
        coreP = {}
        allg = corePGames[c]  # [(t, 常用道具tuple), ...] 全場(含大裝＋鞋＋起手裝)
        for P in uni:
            priors = [p for p in uni if patch_key(p) < patch_key(P)]
            if not priors: continue
            win = priors[-3:]; lo = pstart[win[0]]; hi = pstart[P]  # 視窗起日(前三版首)～迄日(該版起日，不含該版本自身)
            cnt = Counter(); tot = 0
            for t_ms, legs in allg:
                d = _date_of(t_ms)
                if d is None or not (lo <= d < hi): continue
                tot += 1
                for iid in set(legs): cnt[iid] += 1
            if tot < COREP_MINWIN: continue
            ids = [iid for iid, k in cnt.items() if k / tot * 100 >= 10]
            if ids: coreP[P] = ids
        # 符文排列：依「最大顆符文(keystone＝主系第一顆)」分組 → 前三 keystone×各前二配置（邏輯在 _runes_ks）
        runesKS = _runes_ks(runePage[c], runePageW[c], ksOpp[c])
        champs[c] = {"n": n, "start": startByPos, "boots": bootsTop, "core": coreTop, "rest": restTop, "core100": core100, "paths": pathTop, "paths2p": pathTop2p, "coreP": coreP, "runesKS": runesKS}
        # ── byLane：多路線英雄逐路線分開（路線需 ≥max(30, 5%總場)；只有 1 條達標＝單路線英雄 → 不輸出，前端沿用整體）──
        _majors = [(p3, laneGames[c].get(p3, 0)) for p3 in ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY")]
        _majors = [(p3, ln3) for p3, ln3 in _majors if ln3 >= max(30, 0.05 * n)]
        if len(_majors) >= 2:
            byLane = {}
            for p3, ln3 in _majors:
                _ct, _rt = _core_pack(coreL[c][p3], ln3)
                byLane[p3] = {"n": ln3, "boots": _boots_pack(bootL[c][p3], ln3), "core": _ct, "rest": _rt,
                              "core100": _recent_core(recentCoreL[c][p3]),
                              "paths": _path_pack(pathsL[c][p3], pathWL[c][p3]),
                              "paths2p": _path_recent(recentPathL[c][p3]),
                              "runesKS": _runes_ks(runePageL[c][p3], runePageWL[c][p3], ksOppL[c][p3])}
            champs[c]["byLane"] = byLane  # 起手裝不重複存：前端直接讀 champs[c].start[路線]
    # 反向：道具→把它當核心裝的英雄(依該英雄此裝出裝%排序、上限15)
    itemChamps = defaultdict(list)
    for c, d in champs.items():
        for ci in d["core"]: itemChamps[ci["id"]].append((c, ci["pct"]))
    items = {str(iid): [c for c, _ in sorted(lst, key=lambda x: -x[1])][:15] for iid, lst in itemChamps.items()}
    # 反向：符文→最常用它的英雄(依場數，取前8；英雄樣本需夠)
    runes = {}  # 符文→最常帶它的英雄：使用率(該英雄帶此符文場數÷該英雄總場)>20% 才列，依使用率排序
    for rid, cnt in runeCount.items():
        lst = [(c, n / games[c]) for c, n in cnt.items() if games[c] >= MIN_GAMES and n / games[c] > 0.2]
        lst.sort(key=lambda x: -x[1])
        if lst: runes[str(rid)] = [c for c, _ in lst][:12]
    # 英雄分頁積分版：全季彙總(不分版本；路線分桶)。樣本 < MIN_GAMES 的英雄不列。
    hero = {c: {ln: arr for ln, arr in lanes.items()} for c, lanes in heroAgg.items() if games[c] >= MIN_GAMES}
    # 每版本彙總（版本篩選用）＋積分實際有場次的版本清單（前端下拉補進職業賽沒有的最新版，如 26.14）
    heroP = {c: {pk: {ln: arr for ln, arr in lanes.items()} for pk, lanes in pks.items()}
             for c, pks in heroAggP.items() if games[c] >= MIN_GAMES}
    sq_patches = sorted({pk for pks in heroP.values() for pk in pks}, key=patch_key)
    # 積分對位（給英雄詳情對位表）：pair 場數 >=3 才列，控檔案大小
    mu = {}
    for c, opps in muCnt.items():
        if games[c] < MIN_GAMES: continue
        d2 = {o: v for o, v in opps.items() if v[0] >= 3}
        if d2: mu[c] = d2
    # 召喚師技能組合（zh 名稱＝現行 DDragon summoner.json；前端用名稱查 EXTRA_IMG 拿圖）
    try:
        _ver = json.load(urllib.request.urlopen("https://ddragon.leagueoflegends.com/api/versions.json"))[0]
        _sm = json.load(urllib.request.urlopen(f"https://ddragon.leagueoflegends.com/cdn/{_ver}/data/zh_TW/summoner.json"))["data"]
        SUM_NAME = {int(v["key"]): v["name"] for v in _sm.values()}
    except Exception:
        SUM_NAME = {}
    sp = {}
    for c, cnt in suCnt.items():
        if games[c] < MIN_GAMES: continue
        tot = sum(cnt.values())
        top = [{"s": [SUM_NAME.get(a, str(a)), SUM_NAME.get(b, str(b))], "pct": round(n2 / tot * 100)}
               for (a, b), n2 in cnt.most_common(3) if n2 / tot * 100 >= 5]
        if top: sp[c] = top
    # byLane 每路線召技組合（同門檻：前三、≥5%）
    for c, cc in champs.items():
        for p3, blob in (cc.get("byLane") or {}).items():
            cnt = suCntL[c][p3]; tot = sum(cnt.values())
            if not tot: continue
            top = [{"s": [SUM_NAME.get(a, str(a)), SUM_NAME.get(b, str(b))], "pct": round(n2 / tot * 100)}
                   for (a, b), n2 in cnt.most_common(3) if n2 / tot * 100 >= 5]
            if top: blob["sp"] = top
    payload = {"champs": champs, "items": items, "runes": runes, "p2patches": p2v, "hero": hero, "heroP": heroP, "patches": sq_patches, "mu": mu, "sp": sp}  # p2patches＝「近兩版流派」的兩個版本號(前端標題顯示)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.SOLOQ_BUILDS=" + json.dumps(payload, ensure_ascii=False) + ";\n")
    print(f"完成：{len(champs)} 英雄 / {len(items)} 道具 / {len(runes)} 符文（掃 {scanned} 場）→ {OUT}（{os.path.getsize(OUT)/1024:.0f} KB）")

if __name__ == "__main__":
    main()
