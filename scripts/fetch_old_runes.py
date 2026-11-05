# -*- coding: utf-8 -*-
"""舊符文系統（Runes Reforged 之前，2013–2017）→ old_runes.js
資料源：DDragon 各年賽季中版本 rune.json（zh_TW；符文以道具形式存在，rune.tier 1~3、type red/yellow/blue/black）。
圖鑑「符文」分區 ≤2017 年的「符文頁」用：只列 tier 3（頂級，玩家實際用的等級），依 印記紅/護符黃/雕紋藍/精華紫 分組。
用法：python scripts\\fetch_old_runes.py

抓不到（2026-11-05 精進迴圈 #2608）：舊版某年失敗就印一行、照寫 exit 0，那一年的符文頁從線上消失到下一班；
全斷時寫成空表。現在單次逾時 30 秒、試 2 次，連 2 個版本抓不到就不再上網。抓不到、或任一色 0 筆的那一年
沿用上一版 old_runes.js；連上一版都沒有的年份 exit 1；一年都沒有才不寫檔。
"""
import io, sys, json, os, time, urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "old_runes.js")
CDN = "https://ddragon.leagueoflegends.com/cdn"
# 賽季中版本（與天賦樹同原則：年末版本已是次年賽季）
# 2013＝3.15.5（S3 最後一版，rune.json 拿得到）→ 符文頁才有資料版可畫（2026-07-31）
VERS = {2013: "3.15.5", 2014: "4.16.1", 2015: "5.16.1", 2016: "6.16.2", 2017: "7.16.1"}
PREFIX = "window.OLD_RUNES="

TIMEOUT = 30
TRIES = 2
RETRY_WAIT = 3
OFFLINE_AFTER = 2   # 連續幾個版本試完都失敗就不再上網（CDN 整個掛掉時不要每年都等逾時）
_fail_streak = 0


def g(u):
    global _fail_streak
    if _fail_streak >= OFFLINE_AFTER:
        raise RuntimeError("連續抓不到，這班不再上網")
    last = None
    for i in range(TRIES):
        try:
            r = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=TIMEOUT).read())
            _fail_streak = 0
            return r
        except Exception as e:
            last = e
            if i + 1 < TRIES:
                time.sleep(RETRY_WAIT)
    _fail_streak += 1
    raise last


def load_prev():
    """讀上一版 old_runes.js。讀不到回空表。"""
    try:
        s = open(OUT, encoding="utf-8").read()
        d, _ = json.JSONDecoder().raw_decode(s, len(PREFIX))
        return d if isinstance(d, dict) else {}
    except Exception as e:
        print(f"  （讀不到上一版 old_runes.js：{e}）")
        return {}


def main():
    prev = load_prev()
    out, kept, missing = {}, [], []
    for yr, v in VERS.items():
        try:
            d = g(f"{CDN}/{v}/data/zh_TW/rune.json")["data"]
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
            empty = [k for k, x in grp.items() if not x]
            if empty:
                raise ValueError(f"{'、'.join(empty)} 0 筆")
        except Exception as e:
            print(f"  {yr}({v}) 失敗：{e}")
            if prev.get(str(yr)):
                out[yr] = prev[str(yr)]
                kept.append(str(yr))
            else:
                missing.append(str(yr))
            continue
        for ty in grp:
            grp[ty].sort(key=lambda x: x["n"])
        out[yr] = {"ver": v, **grp}
        print(f"  {yr}({v}): 紅{len(grp['red'])} 黃{len(grp['yellow'])} 藍{len(grp['blue'])} 紫{len(grp['black'])}")
    if kept:
        print(f"⚠ 這班沿用上一版 old_runes.js：{'、'.join(kept)}；下一班會再試")
    if not out:
        print("✗ 一年都拿不到，也沒有上一版可沿用：不寫檔")
        sys.exit(1)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(PREFIX + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";")
    os.replace(tmp, OUT)
    print(f"寫出 old_runes.js（{os.path.getsize(OUT)//1024} KB）")
    if missing:
        print(f"✗ 這幾年沒有符文頁資料，也沒有上一版可沿用：{'、'.join(missing)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
