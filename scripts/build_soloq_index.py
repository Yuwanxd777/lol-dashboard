# -*- coding: utf-8 -*-
"""
從現有的 soloq_matches/pN.js 重建 soloq_match_index.js，並算進「排行榜要用的彙總」：
  last10 = 最近 10 場使用英雄(重複不去除、最新在前)
  wr7    = 最近 7 天勝率(%)
  sc7    = 最近 7 天平均 dpm 評分
  n7     = 最近 7 天場數
不需重抓（只讀本機檔）。fetch_soloq_year.py / fetch_soloq_update.py 末端都會呼叫它，
每日排程也會透過 update.py 連帶更新（7 天滑動窗口要每天重算）。
用法：  python scripts\build_soloq_index.py
"""
import os, re, json, glob, time, sys, gc

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import soloq_src  # 逐場檔來源 meta（哪個 dpmPuuid 抓回哪些 rid）；併檔時要一起合併
OUTDIR = os.path.join(ROOT, "soloq_matches")
IDX = os.path.join(ROOT, "soloq_match_index.js")
RECENT = os.path.join(ROOT, "soloq_recent.js")   # 每日戰況(各隊每人近幾天逐場)：積分頁「每日戰況」視圖用
TZ_H = 9           # 分日時區：KST(UTC+9)＝選手所在伺服器的自然日；「昨天」以此界定
RECENT_DAYS = 8    # 每日戰況保留最近 8 天(今天＋近 7 天)

def aggregates(matches):
    # matches 已是最新在前
    last10 = [g.get("c") for g in matches[:10] if g.get("c")]
    cut = (time.time() - 7*86400) * 1000
    wk = [g for g in matches if (g.get("t") or 0) >= cut]
    wr7 = sc7 = n7 = kda7 = w7 = None
    if wk:
        n7 = len(wk); wins = sum(1 for g in wk if g.get("w"))
        w7 = wins
        wr7 = round(wins / n7 * 100)
        scs = [g["sc"] for g in wk if g.get("sc") is not None]
        sc7 = round(sum(scs) / len(scs), 1) if scs else None
        sk = sum(g.get("k", 0) for g in wk); sd = sum(g.get("de", 0) for g in wk); sa = sum(g.get("a", 0) for g in wk)
        kda7 = round((sk + sa) / max(1, sd), 1)  # 一週 KDA＝(總K+總A)/總D
    return last10, wr7, sc7, n7, kda7, w7

def _pnum(b):
    return int(re.match(r'p(\d+)\.js$', b).group(1))

def _dedup_files():
    """自癒：同一 key 出現多個 pN.js(通常是索引漂移時 --missing 誤重建)＝資料異常。
    union 合併(依 t 去重、低號檔記錄優先)進最低號檔、刪其餘、印警告。每次重建索引前跑，杜絕儀表板漏場。
    回傳 {fp: (key, data)}＝這一趟已解析、而且沒被改寫／刪掉的檔，build() 直接用、不再把 423 檔 260MB 讀第二次
    （2026-09-09 精進迴圈 #75：兩趟各解析一次、關掉 GC 之後仍佔 ~5s（唯讀包裝實測 8.1s → 3.3s））。被合併改寫的 canonical 檔會從快取拿掉，
    讓 build() 重讀磁碟上的新內容。"""
    from collections import defaultdict
    groups = defaultdict(list)  # key -> [(pnum, fp, data)]
    parsed = {}                 # fp -> (key, data)：給 build() 的解析快取
    for fp in sorted(glob.glob(os.path.join(OUTDIR, "p*.js"))):
        b = os.path.basename(fp)
        if not re.match(r'p\d+\.js$', b):  # 只認選手逐場檔 pN.js；跳過殘留暫存索引等雜檔(曾把 soloq_match_index.js 掃進來報 group 錯)
            continue
        try:
            m = re.match(r'window\.__sqLoad\((.*)\);\s*$', open(fp, encoding="utf-8").read(), re.S)
            key, data = json.loads('[' + m.group(1) + ']')
        except Exception:
            continue  # 壞檔留給主迴圈印「略過」
        groups[key].append((_pnum(b), fp, data))
        parsed[fp] = (key, data)
    for key, lst in groups.items():
        if len(lst) < 2:
            continue
        lst.sort(key=lambda x: x[0])  # 低號優先＝canonical
        by_t = {}; extra = []
        for _, fp, data in lst:  # 低號先 → 同 t 保低號記錄
            for g in data.get("matches", []):
                t = g.get("t")
                if t is None: extra.append(g)
                elif t not in by_t: by_t[t] = g
        merged = sorted(by_t.values(), key=lambda g: g.get("t", 0), reverse=True) + extra
        canon = lst[0][1]; role = lst[0][2].get("role")
        _out = {'role': role, 'matches': merged}
        _m = soloq_src.merge([d.get("src") for _, _, d in lst])  # 併檔時保住來源 meta（obs 相加、full 取 and）
        if _m: _out["src"] = _m
        with open(canon, "w", encoding="utf-8") as wf:
            wf.write(f"window.__sqLoad({json.dumps(key,ensure_ascii=False)},{json.dumps(_out,ensure_ascii=False)});\n")
        parsed.pop(canon, None)  # 內容剛改寫 ⇒ 快取作廢，build() 重讀
        dropped = []
        for _, fp, _ in lst[1:]:
            parsed.pop(fp, None)  # 刪失敗也照樣作廢：檔還在的話 build() 會重讀，跟以前一樣
            try: os.remove(fp); dropped.append(os.path.basename(fp))
            except Exception: pass
        print(f"  ⚠ 重複 key {key}：合併 {[os.path.basename(x[1]) for x in lst]} → {os.path.basename(canon)}（union {len(merged)} 場），已刪 {dropped}")
    return parsed

def build():
    """重建索引。整段關掉循環 GC：資料全是 json.loads 出來的樹狀物件（dict／list／str），沒有參考循環，
    refcount 就能回收；但 423 檔逐一解析會不斷觸發 gen2 全堆掃描（_dedup_files 把 423 檔都抓在手上時最痛），
    22:00 那班 17.4s 裡有 ~9s 是在做這個（2026-09-09 精進迴圈 #75 唯讀包裝實測 16.9s → 8.1s，產出逐位元相同）。
    用 try/finally 還原，程序內被別支腳本呼叫時不會把人家的 GC 一路關著。"""
    was = gc.isenabled(); gc.disable()
    try:
        _build()
    finally:
        if was: gc.enable()

def _build():
    parsed = _dedup_files()  # 先自癒去重(同 key 多檔 union 合併)，主迴圈才不會靜默漏場；順便帶回解析快取
    players = {}; newest = 0
    recent = {}; rec_cut = (time.time() - RECENT_DAYS*86400) * 1000  # 每日戰況：只收近 RECENT_DAYS 天的逐場
    for fp in sorted(glob.glob(os.path.join(OUTDIR, "p*.js"))):
        b = os.path.basename(fp)
        if not re.match(r'p\d+\.js$', b):  # 只認選手逐場檔 pN.js；跳過殘留暫存索引等雜檔(曾把 soloq_match_index.js 掃進來報 group 錯)
            continue
        try:
            if fp in parsed:
                key, data = parsed.pop(fp)  # _dedup_files 剛解析過、檔案沒被改寫 ⇒ 直接用（pop 掉讓記憶體邊走邊還）
            else:
                txt = open(fp, encoding="utf-8").read()
                m = re.match(r'window\.__sqLoad\((.*)\);\s*$', txt, re.S)
                key, data = json.loads('[' + m.group(1) + ']')
        except Exception as e:
            print(f"  略過 {b}：{e}"); continue
        matches = data.get("matches", []); role = data.get("role")
        clean = [g for g in matches if (g.get("d") or 0) >= 600]  # 刪 <10 分鐘局(remake/秒投)
        if len(clean) != len(matches):
            data["matches"] = clean; matches = clean
            with open(fp, "w", encoding="utf-8") as wf:
                wf.write(f"window.__sqLoad({json.dumps(key,ensure_ascii=False)},{json.dumps(data,ensure_ascii=False)});\n")
        if key in players:  # 同一選手兩個檔＝資料異常(應先跑合併去重)：索引取場數多者，別靜默漏另一檔的戰績
            if len(matches) <= players[key]["n"]:
                print(f"  ⚠ 重複 key {key}：{b}({len(matches)}場) 不多於既有 {players[key]['f']}({players[key]['n']}場)，索引沿用既有"); continue
            print(f"  ⚠ 重複 key {key}：{b}({len(matches)}場) 覆蓋 {players[key]['f']}({players[key]['n']}場)，索引取場數多者")
        if matches: newest = max(newest, matches[0].get("t", 0))
        l10, wr7, sc7, n7, kda7, w7 = aggregates(matches)
        lt = max((g.get("t") or 0) for g in matches) if matches else None  # 最近一場時間戳(ms)：積分表「最近積分」欄
        players[key] = {"f": b, "role": role, "n": len(matches),
                        "last10": l10, "wr7": wr7, "sc7": sc7, "n7": n7, "kda7": kda7, "w7": w7, "lt": lt}
        # 每日戰況：以 KST 分日，每場記 [英雄, 勝(1)/敗(0), LP 變化]；最新在前
        byday = {}
        for g in matches:
            t = g.get("t")
            if not t or t < rec_cut:
                continue
            day = time.strftime("%Y-%m-%d", time.gmtime(t/1000 + TZ_H*3600))
            lp = g.get("lp"); lp = lp if isinstance(lp, (int, float)) else 0
            byday.setdefault(day, []).append([g.get("c"), 1 if g.get("w") else 0, lp])
        if byday:
            recent[key] = {"r": role, "d": byday}
    year = time.gmtime(newest/1000).tm_year if newest else time.gmtime().tm_year
    payload = {"fetched_at": time.strftime("%Y-%m-%d %H:%M"), "year": year, "players": players}
    with open(IDX, "w", encoding="utf-8") as f:
        f.write("window.SOLOQ_MATCH_IDX=" + json.dumps(payload, ensure_ascii=False) + ";\n")
    wk = sum(1 for v in players.values() if v["n7"])
    print(f"索引重建：{len(players)} 位（{wk} 位近 7 天有出賽）→ {IDX}")
    # 每日戰況小檔(積分頁「每日戰況」視圖懶載用)
    gen_day = time.strftime("%Y-%m-%d", time.gmtime(time.time() + TZ_H*3600))
    rec_payload = {"generated": time.strftime("%Y-%m-%d %H:%M"), "genDay": gen_day, "tzHours": TZ_H, "players": recent}
    with open(RECENT, "w", encoding="utf-8") as f:
        f.write("window.SOLOQ_RECENT=" + json.dumps(rec_payload, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print(f"每日戰況：{len(recent)} 位近 {RECENT_DAYS} 天有出賽 → {RECENT}")

if __name__ == "__main__":
    build()
