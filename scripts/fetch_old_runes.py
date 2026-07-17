# -*- coding: utf-8 -*-
"""舊符文系統（Runes Reforged 之前，2014–2017）→ old_runes.js
資料源：DDragon 各年賽季中版本 rune.json（zh_TW；符文以道具形式存在，rune.tier 1~3、type red/yellow/blue/black）。
圖鑑「符文」分區 ≤2017 年的「符文頁」用：只列 tier 3（頂級，玩家實際用的等級），依 印記紅/護符黃/雕紋藍/精華紫 分組。
用法：python scripts\\fetch_old_runes.py
"""
import io, sys, json, os, urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "old_runes.js")
CDN = "https://ddragon.leagueoflegends.com/cdn"
# 賽季中版本（與天賦樹同原則：年末版本已是次年賽季）
VERS = {2014: "4.16.1", 2015: "5.16.1", 2016: "6.16.2", 2017: "7.16.1"}


def g(u):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=40).read())


def main():
    out = {}
    for yr, v in VERS.items():
        try:
            d = g(f"{CDN}/{v}/data/zh_TW/rune.json")["data"]
        except Exception as e:
            print(f"  {yr}({v}) 失敗：{e}"); continue
        grp = {"red": [], "yellow": [], "blue": [], "black": []}
        for rid, r in d.items():
            ru = r.get("rune") or {}
            if str(ru.get("tier")) != "3":
                continue                       # 只列頂級（1/2 級是升級素材，遊戲後期沒人用）
            ty = ru.get("type")
            if ty not in grp:
                continue
            grp[ty].append({"n": r.get("name") or rid, "d": r.get("description") or "",
                            "img": f"{CDN}/{v}/img/rune/{(r.get('image') or {}).get('full', rid + '.png')}"})
        for ty in grp:
            grp[ty].sort(key=lambda x: x["n"])
        out[yr] = {"ver": v, **{k: v2 for k, v2 in grp.items()}}
        print(f"  {yr}({v}): 紅{len(grp['red'])} 黃{len(grp['yellow'])} 藍{len(grp['blue'])} 紫{len(grp['black'])}")
    open(OUT, "w", encoding="utf-8").write("window.OLD_RUNES=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";")
    print(f"寫出 old_runes.js（{os.path.getsize(OUT)//1024} KB）")


if __name__ == "__main__":
    main()
