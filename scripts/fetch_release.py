# -*- coding: utf-8 -*-
"""抓各英雄「加入英雄聯盟的日期」→ champ_release.js（window.CHAMP_RELEASE={id:"YYYY-MM-DD"}）。
資料來源：wiki.leagueoflegends.com 的 Module:ChampionData/data（含每隻英雄 date_int / date）。
該 wiki 對純 urllib 會回 403，故用 Playwright（真瀏覽器）載入 raw 模組再解析。
DDragon 提供 id 對照（apiname/英文名 → DDragon id）。抓不到就略過。
"""
import json, os, re, urllib.request

DDRAGON = "https://ddragon.leagueoflegends.com"
RAW = "https://wiki.leagueoflegends.com/en-us/Module:ChampionData/data?action=raw"
OUT = os.path.join(os.path.dirname(__file__), "..", "champ_release.js")

def jget(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def main():
    ver = jget(f"{DDRAGON}/api/versions.json")[0]
    champs = jget(f"{DDRAGON}/cdn/{ver}/data/en_US/champion.json")["data"]
    # DDragon: name(英文) -> id ；用來把 wiki 的英雄名對回 DDragon id
    name2id = {c["name"]: cid for cid, c in champs.items()}
    ids = set(champs.keys())

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto(RAW, wait_until="domcontentloaded", timeout=60000)
        lua = pg.inner_text("body")
        b.close()
    print("raw module chars:", len(lua))

    # 解析：每個區塊 ["Name"] = { ... ["date"] = "YYYY-MM-DD" ... }
    rel = {}
    # 逐一找 ["<name>"] = { 開頭，往後在該英雄區塊內找 date
    for m in re.finditer(r'\["([^"]+)"\]\s*=\s*\{', lua):
        nm = m.group(1)
        start = m.end()
        seg = lua[start:start + 4000]
        dm = re.search(r'\["date"\]\s*=\s*"([0-9]{4}-[0-9]{2}-[0-9]{2})"', seg)
        if not dm:
            continue
        date = dm.group(1)
        # 對回 DDragon id：優先 name2id；其次 apiname；再者名字去符號比對
        cid = None
        if nm in ids:
            cid = nm
        elif nm in name2id:
            cid = name2id[nm]
        else:
            am = re.search(r'\["apiname"\]\s*=\s*"([^"]+)"', seg)
            if am and am.group(1) in ids:
                cid = am.group(1)
        if cid:
            rel[cid] = date

    payload = json.dumps(rel, ensure_ascii=False, sort_keys=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.CHAMP_RELEASE=" + payload + ";\n")
    print(f"champ_release.js: {len(rel)}/{len(ids)} champions, {os.path.getsize(OUT)} bytes")
    miss = sorted(ids - set(rel.keys()))
    if miss:
        print("missing:", ", ".join(miss))

if __name__ == "__main__":
    main()
