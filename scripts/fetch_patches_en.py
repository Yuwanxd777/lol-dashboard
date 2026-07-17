# -*- coding: utf-8 -*-
"""抓 Riot 官方 patch notes（英文原文，不翻譯）→ patches_en.js
給儀表板「英文模式」的版本改動顯示官方英文原文。復用 fetch_patches.py 的解析器（語言無關）與 URL 目錄。
用法：
  python fetch_patches_en.py                 # 補缺（沿用 patch_urls.json 的 zh-tw URL，改抓 en-us）
  python fetch_patches_en.py --force         # 全部重抓
排程：與 fetch_patches.py 同邏輯（當年版本每次試抓、舊年 404 永久跳過、未來版本跳過）。
"""
import os, sys, json
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_patches as fp  # 復用 fetch/parse/discover_urls/patch_est_date/riot_major/target_patches/CACHE/HERE

TODAY = date.today()

def to_en(url):
    return url.replace("/zh-tw/", "/en-us/").replace("/zh-hant/", "/en-us/") if url else None

def get_html_en(pk, url_map):
    """只抓 en-us 頁：先用目錄的 URL 轉英文，再退回 slug 猜測。"""
    tries = []
    disc = url_map.get(pk)
    if disc:
        tries.append(to_en(disc))
    parts = pk.split("."); yy, mm = int(parts[0]), int(parts[1])
    year = yy + (2010 if yy <= 14 else 2000); major = fp.riot_major(year)
    m2 = f"{mm:02d}"
    for fmt in (f"patch-{major}-{mm}-notes", f"patch-{major}-{m2}-notes",
                f"patch-{major}-s1-{mm}-notes", f"patch-{year}-s1-{mm}-notes",
                f"league-of-legends-patch-{major}-{mm}-notes",
                f"league-of-legends-patch-{major}-{m2}-notes"):
        tries.append(f"https://www.leagueoflegends.com/en-us/news/game-updates/{fmt}/")
    for u in tries:
        if not u:
            continue
        try:
            return fp.fetch(u), u
        except Exception:
            continue
    return None, None

def main():
    force = "--force" in sys.argv
    os.makedirs(fp.CACHE, exist_ok=True)
    url_map = fp.discover_urls(force=False)  # 沿用既有 zh-tw URL 目錄（不重跑 Playwright）
    targets = set(url_map.keys()) | {f"{y%100}.{m:02d}" for y, m in fp.target_patches()}

    miss_path = os.path.join(fp.CACHE, "patch_en_missing.json")
    missing = set()
    if os.path.exists(miss_path) and not force:
        try: missing = set(json.load(open(miss_path, encoding="utf-8")))
        except Exception: pass

    all_en, got = {}, 0
    for pk in sorted(targets):
        cf = os.path.join(fp.CACHE, f"patch_en_{pk}.json")
        if os.path.exists(cf) and not force:
            all_en[pk] = json.load(open(cf, encoding="utf-8")); continue
        parts = pk.split("."); yy, mm = int(parts[0]), int(parts[1])
        year = yy + (2010 if yy <= 14 else 2000)
        if fp.patch_est_date(year, mm) > TODAY and not force:
            continue  # 未發布
        if pk in missing and not force:
            if year < fp.NOW_YEAR:
                continue  # 舊年份確認無 → 永久跳過
            missing.discard(pk)
        html_text, url = get_html_en(pk, url_map)
        if not html_text:
            missing.add(pk); continue
        champs = fp.parse(html_text)  # 語言無關解析：英文頁 → 英文改動行
        if not champs or not any(k != "_url" and k != "_extra" for k in champs):
            print(f"  {pk}: parsed 0"); missing.add(pk); continue
        champs["_url"] = url
        all_en[pk] = champs
        json.dump(champs, open(cf, "w", encoding="utf-8"), ensure_ascii=False)
        got += 1
        print(f"  {pk}: {len([k for k in champs if k not in ('_url','_extra')])} champs (en)")

    json.dump(sorted(missing), open(miss_path, "w", encoding="utf-8"), ensure_ascii=False)
    js = json.dumps(all_en, ensure_ascii=False, separators=(",", ":"))
    out = os.path.join(fp.HERE, "patches_en.js")
    open(out, "w", encoding="utf-8").write("window.LOL_PATCHES_EN=" + js + ";")
    print(f"✅ patches_en.js：{len(all_en)} 個版本、本次新抓 {got} → {os.path.getsize(out)//1024} KB")

if __name__ == "__main__":
    main()
