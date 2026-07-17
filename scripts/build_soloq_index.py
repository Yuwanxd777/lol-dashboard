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
import os, re, json, glob, time

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
OUTDIR = os.path.join(ROOT, "soloq_matches")
IDX = os.path.join(ROOT, "soloq_match_index.js")

def aggregates(matches):
    # matches 已是最新在前
    last10 = [g.get("c") for g in matches[:10] if g.get("c")]
    cut = (time.time() - 7*86400) * 1000
    wk = [g for g in matches if (g.get("t") or 0) >= cut]
    wr7 = sc7 = n7 = kda7 = None
    if wk:
        n7 = len(wk); wins = sum(1 for g in wk if g.get("w"))
        wr7 = round(wins / n7 * 100)
        scs = [g["sc"] for g in wk if g.get("sc") is not None]
        sc7 = round(sum(scs) / len(scs), 1) if scs else None
        sk = sum(g.get("k", 0) for g in wk); sd = sum(g.get("de", 0) for g in wk); sa = sum(g.get("a", 0) for g in wk)
        kda7 = round((sk + sa) / max(1, sd), 1)  # 一週 KDA＝(總K+總A)/總D
    return last10, wr7, sc7, n7, kda7

def build():
    players = {}; newest = 0
    for fp in sorted(glob.glob(os.path.join(OUTDIR, "*.js"))):
        try:
            txt = open(fp, encoding="utf-8").read()
            m = re.match(r'window\.__sqLoad\((.*)\);\s*$', txt, re.S)
            key, data = json.loads('[' + m.group(1) + ']')
        except Exception as e:
            print(f"  略過 {os.path.basename(fp)}：{e}"); continue
        matches = data.get("matches", []); role = data.get("role")
        clean = [g for g in matches if (g.get("d") or 0) >= 600]  # 刪 <10 分鐘局(remake/秒投)
        if len(clean) != len(matches):
            data["matches"] = clean; matches = clean
            with open(fp, "w", encoding="utf-8") as wf:
                wf.write(f"window.__sqLoad({json.dumps(key,ensure_ascii=False)},{json.dumps(data,ensure_ascii=False)});\n")
        if matches: newest = max(newest, matches[0].get("t", 0))
        l10, wr7, sc7, n7, kda7 = aggregates(matches)
        lt = max((g.get("t") or 0) for g in matches) if matches else None  # 最近一場時間戳(ms)：積分表「最近積分」欄
        players[key] = {"f": os.path.basename(fp), "role": role, "n": len(matches),
                        "last10": l10, "wr7": wr7, "sc7": sc7, "n7": n7, "kda7": kda7, "lt": lt}
    year = time.gmtime(newest/1000).tm_year if newest else time.gmtime().tm_year
    payload = {"fetched_at": time.strftime("%Y-%m-%d %H:%M"), "year": year, "players": players}
    with open(IDX, "w", encoding="utf-8") as f:
        f.write("window.SOLOQ_MATCH_IDX=" + json.dumps(payload, ensure_ascii=False) + ";\n")
    wk = sum(1 for v in players.values() if v["n7"])
    print(f"索引重建：{len(players)} 位（{wk} 位近 7 天有出賽）→ {IDX}")

if __name__ == "__main__":
    build()
