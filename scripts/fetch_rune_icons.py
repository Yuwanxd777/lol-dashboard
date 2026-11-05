# -*- coding: utf-8 -*-
"""
符文圖示正解表 → rune_icons.js
問題：舊年份 DDragon runesReforged(如 8.1.1 給 2017 用)的 icon 是「舊內部代號路徑」
      (ASSETS/Perks/Styles/Inspiration/TheThirdPath/TheThirdPath.dds＝天界之身)，
      現行 CDN 與 CommunityDragon 都沒有這些舊代號檔 → 破圖且無法 heuristic 轉換。
正解：CommunityDragon 的 perks.json / perkstyles.json 含【全部歷史 perk（含已移除）】的
      id→iconPath，圖檔實測皆在。另用歷年 DDragon runesReforged(zh_TW) 補 id→中文名。
輸出：window.RUNE_ICONS = { byId: {id:{zh,en,img}}, byName: {任一歷代中文名: img} }
用法：python scripts/fetch_rune_icons.py

抓不到（2026-11-05 精進迴圈 #2609）：舊版某個 DDragon 版本失敗就 continue、照寫 exit 0，只有那一版才有的
舊中文名會從 byName 消失（fetch_patches 也拿這份名單判斷符文改動）。現在單次逾時 30 秒、試 2 次，
連 2 個版本抓不到就不再上網。有版本抓不到時，byName 與中文名從上一版補回；沒有上一版可補就照寫並 exit 1。
CDragon 少掉的 id 沿用上一版。CDragon 抓不到或是空的就不寫檔並 exit 1。
"""
import json, os, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "rune_icons.js")
CD = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default"
UA = {"User-Agent": "Mozilla/5.0"}
# 歷年年末版本（涵蓋各時期存在過的符文與其當時中文名）
ZH_VERS = ["8.1.1", "8.11.1", "8.24.1", "9.24.2", "10.25.1", "11.24.1", "12.23.1", "13.24.1", "14.24.1", "15.24.1"]
PREFIX = "window.RUNE_ICONS="

TIMEOUT = 30
TRIES = 2
RETRY_WAIT = 3
OFFLINE_AFTER = 2   # 連續幾個網址試完都失敗就不再上網（來源整個掛掉時不要每版都等逾時）
_fail_streak = 0


def g(u):
    global _fail_streak
    if _fail_streak >= OFFLINE_AFTER:
        raise RuntimeError("連續抓不到，這班不再上網")
    last = None
    for i in range(TRIES):
        try:
            r = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=TIMEOUT).read())
            _fail_streak = 0
            return r
        except Exception as e:
            last = e
            if i + 1 < TRIES:
                time.sleep(RETRY_WAIT)
    _fail_streak += 1
    raise last


def load_prev():
    """讀上一版 rune_icons.js。讀不到回空表。"""
    try:
        s = open(OUT, encoding="utf-8").read()
        d, _ = json.JSONDecoder().raw_decode(s, len(PREFIX))
        if isinstance(d, dict) and isinstance(d.get("byId"), dict) and isinstance(d.get("byName"), dict):
            return d
        print("  （上一版 rune_icons.js 格式不對，當作沒有）")
    except Exception as e:
        print(f"  （讀不到上一版 rune_icons.js：{e}）")
    return {"byId": {}, "byName": {}}


def icon_url(icon_path):
    """perks.json 的 /lol-game-data/assets/v1/... → CDragon raw URL（小寫）"""
    if not icon_path:
        return ""
    rel = icon_path.split("/assets/")[-1].lower()
    return f"{CD}/{rel}"


def fetch_cdragon():
    """perk（具體符文，含已移除）＋ perkstyle（符文系/樹：8000 精密…）。任一類是空的就 raise。"""
    by_id = {}
    perks = g(f"{CD}/v1/perks.json")
    if not (isinstance(perks, list) and perks):
        raise ValueError("perks.json 是空的或格式不對")
    for p in perks:
        pid = str(p.get("id"))
        u = icon_url(p.get("iconPath"))
        if pid and u:
            by_id[pid] = {"zh": "", "en": p.get("name") or "", "img": u}
    ps = g(f"{CD}/v1/perkstyles.json")
    styles = ps if isinstance(ps, list) else ps.get("styles")
    if not styles:
        raise ValueError("perkstyles.json 是空的或格式不對")
    for s in styles:
        sid = str(s.get("id"))
        u = icon_url(s.get("iconPath"))
        if sid and u:
            by_id[sid] = {"zh": "", "en": s.get("name") or "", "img": u}
    return by_id


def add_zh(d, by_id, by_name):
    """一個版本的 runesReforged → 補 zh 與 byName（同 id 各年名字都登記；後年不覆蓋 zh 主名，只加 byName）。
    回傳對到幾個符文。"""
    n = 0
    for t in d:
        ent = by_id.get(str(t.get("id")))
        if ent:
            n += 1
            if not ent["zh"]:
                ent["zh"] = t.get("name") or ""
            if t.get("name") and t["name"] not in by_name:
                by_name[t["name"]] = ent["img"]
        for sl in t.get("slots", []):
            for r in sl.get("runes", []):
                e2 = by_id.get(str(r.get("id")))
                if not e2:
                    continue
                n += 1
                if not e2["zh"]:
                    e2["zh"] = r.get("name") or ""
                if r.get("name") and r["name"] not in by_name:
                    by_name[r["name"]] = e2["img"]
    return n


def main():
    by_name = {}
    prev = load_prev()
    try:
        by_id = fetch_cdragon()
    except Exception as e:
        print(f"✗ CDragon 抓不到：{e}；不寫檔，上一版 rune_icons.js 不動")
        sys.exit(1)
    print(f"CDragon perk+style：{len(by_id)} 個")
    # CDragon 應該含全部歷史，少了就是來源異常：沿用上一版，歷代名字才對得到 id
    gone = [k for k, e in prev["byId"].items() if k not in by_id and isinstance(e, dict) and e.get("img")]
    for k in gone:
        by_id[k] = {"zh": "", "en": prev["byId"][k].get("en") or "", "img": prev["byId"][k]["img"]}
    if gone:
        print(f"⚠ CDragon 少了 {len(gone)} 個 id，沿用上一版 rune_icons.js：{'、'.join(gone[:10])}")
    # 歷年 DDragon zh 名
    failed = []
    try:
        cur = g("https://ddragon.leagueoflegends.com/api/versions.json")[0]
    except Exception as e:
        print(f"  versions.json 失敗：{e}")
        failed.append("versions.json")
        cur = None
    for v in ZH_VERS + ([cur] if cur else []):
        try:
            d = g(f"https://ddragon.leagueoflegends.com/cdn/{v}/data/zh_TW/runesReforged.json")
            if not add_zh(d, by_id, by_name):
                raise ValueError("一個符文都對不上")
        except Exception as e:
            print(f"  {v} 失敗：{e}")
            failed.append(v)
    # 英文名也進 byName（版本焦點的英文行）
    for e in by_id.values():
        if e["en"] and e["en"] not in by_name:
            by_name[e["en"]] = e["img"]
    if failed:
        # 只有抓不到的那幾版才有的名字，從上一版補回
        names, zhs = 0, 0
        for k, img in prev["byName"].items():
            if k not in by_name:
                by_name[k] = img
                names += 1
        for k, e in by_id.items():
            old = prev["byId"].get(k)
            if not e["zh"] and isinstance(old, dict) and old.get("zh"):
                e["zh"] = old["zh"]
                zhs += 1
        print(f"⚠ 這班有版本抓不到：{'、'.join(failed)}；沿用上一版 rune_icons.js 補回名字 {names} 筆、中文名 {zhs} 筆；下一班會再試")
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(PREFIX + json.dumps({"byId": by_id, "byName": by_name}, ensure_ascii=False, separators=(",", ":")) + ";")
    os.replace(tmp, OUT)
    named = sum(1 for e in by_id.values() if e["zh"])
    print(f"寫出 rune_icons.js：byId {len(by_id)}（有中文名 {named}）、byName {len(by_name)}")
    for probe in ("天界之身", "鋼鐵肌膚", "魔鏡之護", "掠食者", "竊盜高手"):
        print(f"  {probe}: {'✓ ' + by_name[probe].rsplit('/', 1)[-1] if probe in by_name else '✗ 查無'}")
    if failed and not prev["byName"]:
        print("✗ 有版本抓不到，也沒有上一版可補：這份可能少了舊名")
        sys.exit(1)


if __name__ == "__main__":
    main()
