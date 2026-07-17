# -*- coding: utf-8 -*-
"""
舊天賦(Masteries, Runes Reforged 7.22 前)中英名＋圖示 → masteries.js
用途：2014–2017 版本焦點/歷年改動裡的舊天賦 keystone(Courage of the Colossus / Warlord's Bloodlust /
      Stoneborn Pact …)在 DDragon 的 runesReforged 沒有 → 版本焦點顯示英文無圖。
      本表補「英文名 → 官方中文名＋圖示」，讓前端 assetZh/assetImg 能解析。
資料源：DDragon 各年 mastery.json(en_US + zh_TW)，圖＝/cdn/{ver}/img/mastery/{id}.png。
輸出：window.LOL_MASTERIES = { "英文名": {zh:"中文名", img:"完整圖URL", y:[年份...]}, ... }
用法：python scripts/fetch_masteries.py
"""
import json, urllib.request
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from fetch_patches import translate_line  # wiki_extra 用的同一套翻譯 → 產生「wiki 譯名」別名，讓前端對得到
except Exception:
    translate_line = lambda s: s
OUT = os.path.join(ROOT, "masteries.js")
# 各年「賽季中＋年末」兩個取樣版（名稱對照要涵蓋季中被季前賽移除的天賦，如 Veteran's Scars/Strength of the Ages 在 6.22 被換掉）
VERS = {2014: ["4.16.1", "4.21.5"], 2015: ["5.16.1", "5.24.2"], 2016: ["6.16.2", "6.24.1"], 2017: ["7.16.1", "7.21.1"]}
CDN = "https://ddragon.leagueoflegends.com/cdn"


def g(u):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=40).read())


def main():
    out = {}
    for yr, vlist in VERS.items():
      for v in vlist:
        try:
            en = g(f"{CDN}/{v}/data/en_US/mastery.json")["data"]
            zh = g(f"{CDN}/{v}/data/zh_TW/mastery.json")["data"]
        except Exception as e:
            print(f"  {v} 載入失敗：{e}"); continue
        n = 0
        for iid, e in en.items():
            enm = (e.get("name") or "").strip()
            if not enm:
                continue
            znm = (zh.get(iid, {}).get("name") or enm).strip()
            img = f"{CDN}/{v}/img/mastery/{e.get('image', {}).get('full', iid + '.png')}"
            cur = out.get(enm)
            if cur:
                if yr not in cur["y"]:
                    cur["y"].append(yr)
                # 同一天賦不同版本官方譯名不同（Veteran's Scars：4.x 退役勇士的傷疤 / 6.x 老兵之殤）→ 都收進 aliases
                if znm and znm != cur["zh"] and znm not in (cur.get("aliases") or []):
                    cur.setdefault("aliases", []).append(znm)
            else:
                e = {"zh": znm, "img": img, "y": [yr]}
                alias = translate_line(enm)  # wiki 的翻譯法(可能與官方 zh 不同，如 戰爭領主的嗜血 vs 軍閥血嗜)
                if alias and alias not in (znm, enm):
                    e["alias"] = alias
                out[enm] = e
                n += 1
        print(f"  {yr}({v}): +{n} 天賦（累計 {len(out)}）", flush=True)
    # ── 各年天賦「樹狀結構」（給圖鑑符文分區的舊天賦頁畫成像新符文那樣的樹）──
    # 天賦改版都在賽季末 preseason → 樹用「賽季中」版本才對應當年職業比賽（年末版本其實是次年賽季的樹）
    TREE_VERS = {2014: "4.16.1", 2015: "5.16.1", 2016: "6.16.2", 2017: "7.16.1"}
    trees_out = {}
    for yr, v in TREE_VERS.items():
        try:
            zh = g(f"{CDN}/{v}/data/zh_TW/mastery.json")
            en = g(f"{CDN}/{v}/data/en_US/mastery.json")
        except Exception as e:
            print(f"  tree {v} 載入失敗：{e}"); continue
        zd, ed = zh.get("data", {}), en.get("data", {})
        data = {}
        for mid, z in zd.items():
            e = ed.get(mid, {})
            data[mid] = {"zh": z.get("name") or e.get("name") or mid,
                         "en": e.get("name") or "",
                         "img": f"{CDN}/{v}/img/mastery/{z.get('image', {}).get('full', mid + '.png')}",
                         "r": z.get("ranks") or 1,
                         "d": (z.get("description") or [""])[-1]}   # 滿級描述
        trees = []
        for key, rows in (zh.get("tree") or {}).items():
            trees.append({"key": key,
                          "rows": [[(c.get("masteryId") if c else None) for c in (row or [])] for row in rows]})
            for row in rows:                       # 前置天賦（S4/S5 樹的上下連結線用）：data[id].pre = 需先點滿的天賦 id
                for c in (row or []):
                    if c and str(c.get("prereq") or "0") != "0" and str(c.get("masteryId")) in data:
                        data[str(c["masteryId"])]["pre"] = str(c["prereq"])
        trees_out[yr] = {"ver": v, "trees": trees, "data": data}
        print(f"  tree {yr}({v}): {len(trees)} 樹 {len(data)} 天賦", flush=True)

    # 召喚師技能 en→zh+圖：現行版為主；再掃舊版 zh 收「歷代舊譯」當 alias（幽靈疾步→鬼步、洞悉之石時代譯名等），
    # 版本焦點的舊譯名才對得到現行官方名與圖
    try:
        ver = g("https://ddragon.leagueoflegends.com/api/versions.json")[0]
        sen = g(f"{CDN}/{ver}/data/en_US/summoner.json")["data"]
        szh = g(f"{CDN}/{ver}/data/zh_TW/summoner.json")["data"]
        ns = 0
        ekey = {}
        for sid, e in sen.items():
            enm = (e.get("name") or "").strip()
            if not enm or enm in out:
                continue
            znm = (szh.get(sid, {}).get("name") or enm).strip()
            img = f"{CDN}/{ver}/img/spell/{e.get('image', {}).get('full', sid + '.png')}"
            out[enm] = {"zh": znm, "img": img, "y": []}
            ekey[e.get("id") or sid] = enm
            ns += 1
        alias_n = 0
        for ov in ("4.21.5", "7.24.2", "9.24.2", "12.23.1"):
            try:
                ozh = g(f"{CDN}/{ov}/data/zh_TW/summoner.json")["data"]
            except Exception:
                continue
            for sid, z in ozh.items():
                enm = ekey.get(z.get("id") or sid)
                onm = (z.get("name") or "").strip()
                if not enm or not onm:
                    continue
                ent = out[enm]
                if onm != ent["zh"] and onm not in (ent.get("aliases") or []):
                    ent.setdefault("aliases", []).append(onm); alias_n += 1
        print(f"  召喚師技能: +{ns}（舊譯別名 {alias_n}）", flush=True)
    except Exception as e:
        print(f"  召喚師技能載入失敗：{e}")
    open(OUT, "w", encoding="utf-8").write(
        "window.LOL_MASTERIES=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";"
        + "window.LOL_MASTERY_TREES=" + json.dumps(trees_out, ensure_ascii=False, separators=(",", ":")) + ";")
    print(f"寫出 masteries.js：{len(out)} 筆(天賦＋召喚師技能)＋{len(trees_out)} 年天賦樹")


if __name__ == "__main__":
    main()
