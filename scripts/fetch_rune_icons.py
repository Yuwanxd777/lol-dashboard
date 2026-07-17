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
"""
import json, os, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "rune_icons.js")
CD = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default"
UA = {"User-Agent": "Mozilla/5.0"}
# 歷年年末版本（涵蓋各時期存在過的符文與其當時中文名）
ZH_VERS = ["8.1.1", "8.11.1", "8.24.1", "9.24.2", "10.25.1", "11.24.1", "12.23.1", "13.24.1", "14.24.1", "15.24.1"]


def g(u):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read())


def icon_url(icon_path):
    """perks.json 的 /lol-game-data/assets/v1/... → CDragon raw URL（小寫）"""
    if not icon_path:
        return ""
    rel = icon_path.split("/assets/")[-1].lower()
    return f"{CD}/{rel}"


def main():
    by_id, by_name = {}, {}
    # 1) perk（具體符文，含已移除）
    for p in g(f"{CD}/v1/perks.json"):
        pid = str(p.get("id"))
        u = icon_url(p.get("iconPath"))
        if pid and u:
            by_id[pid] = {"zh": "", "en": p.get("name") or "", "img": u}
    # 2) perkstyle（符文系/樹：8000 精密…）
    ps = g(f"{CD}/v1/perkstyles.json")
    for s in (ps.get("styles") or ps if isinstance(ps, list) else ps.get("styles", [])):
        sid = str(s.get("id"))
        u = icon_url(s.get("iconPath"))
        if sid and u:
            by_id[sid] = {"zh": "", "en": s.get("name") or "", "img": u}
    print(f"CDragon perk+style：{len(by_id)} 個")
    # 3) 歷年 DDragon zh 名 → 補 zh 與 byName（同 id 各年名字都登記；後年不覆蓋 zh 主名，只加 byName）
    try:
        cur = g("https://ddragon.leagueoflegends.com/api/versions.json")[0]
    except Exception:
        cur = None
    for v in ZH_VERS + ([cur] if cur else []):
        try:
            d = g(f"https://ddragon.leagueoflegends.com/cdn/{v}/data/zh_TW/runesReforged.json")
        except Exception:
            continue
        for t in d:
            ent = by_id.get(str(t.get("id")))
            if ent:
                if not ent["zh"]:
                    ent["zh"] = t.get("name") or ""
                if t.get("name") and t["name"] not in by_name:
                    by_name[t["name"]] = ent["img"]
            for sl in t.get("slots", []):
                for r in sl.get("runes", []):
                    e2 = by_id.get(str(r.get("id")))
                    if not e2:
                        continue
                    if not e2["zh"]:
                        e2["zh"] = r.get("name") or ""
                    if r.get("name") and r["name"] not in by_name:
                        by_name[r["name"]] = e2["img"]
    # 英文名也進 byName（版本焦點的英文行）
    for e in by_id.values():
        if e["en"] and e["en"] not in by_name:
            by_name[e["en"]] = e["img"]
    open(OUT, "w", encoding="utf-8").write(
        "window.RUNE_ICONS=" + json.dumps({"byId": by_id, "byName": by_name}, ensure_ascii=False, separators=(",", ":")) + ";")
    named = sum(1 for e in by_id.values() if e["zh"])
    print(f"寫出 rune_icons.js：byId {len(by_id)}（有中文名 {named}）、byName {len(by_name)}")
    for probe in ("天界之身", "鋼鐵肌膚", "魔鏡之護", "掠食者", "竊盜高手"):
        print(f"  {probe}: {'✓ ' + by_name[probe].rsplit('/', 1)[-1] if probe in by_name else '✗ 查無'}")


if __name__ == "__main__":
    main()
