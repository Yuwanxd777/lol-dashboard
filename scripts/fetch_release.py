# -*- coding: utf-8 -*-
"""抓各英雄「加入英雄聯盟的日期」→ champ_release.js（window.CHAMP_RELEASE={id:"YYYY-MM-DD"}）。
資料來源：wiki.leagueoflegends.com 的 Module:ChampionData/data（含每隻英雄 date_int / date）。
該 wiki 對純 urllib 會回 403，故用 Playwright（真瀏覽器）載入 raw 模組再解析。
DDragon 提供 id 對照（apiname/英文名 → DDragon id）。抓不到就略過。

連不上 wiki（逾時／連線重設，2026-11-25 22:00 班第一次遇到：121 班裡的第 1 次，平常 1~2 秒）
⇒ 等 RETRY_WAIT 秒就地重試一次；兩次都失敗才印一行說明、保留舊檔、離開碼 1（不噴 traceback）。
日誌裡單獨一行「重試一次」後面接著正常輸出不用理；「重試仍失敗」連續好幾班才是真的壞了。
改了這段跑 `python scripts/fetch_release_retry_test.py`（不開瀏覽器、不碰網路、不寫真的 champ_release.js）。
"""
import json, os, re, sys, time, urllib.request
# 經典服（LoL Classic，DDragon 內部代號 Jade_*）不是我們要的資料（2026-07-31 使用者回報：
# 英雄Tier 出現經典服頭像）——它的 zh/en 名稱與現行英雄**完全相同**，混進來會造成同名重複與圖片誤植。
# 日後若 Riot 再開別的分支服，一樣在這裡擋掉。
CLASSIC_RE = re.compile(r"^(Jade|Classic|Legacy)_", re.I)   # 分支服前綴：不進資料

DDRAGON = "https://ddragon.leagueoflegends.com"
RAW = "https://wiki.leagueoflegends.com/en-us/Module:ChampionData/data?action=raw"
OUT = os.path.join(os.path.dirname(__file__), "..", "champ_release.js")
RETRY_WAIT = 8          # 秒：第一次連不上之後等多久再試
GOTO_TIMEOUT = 45000    # 毫秒：單次載入上限（平常 1~2 秒；Chromium 自己的連線逾時約 30 秒）


class SourceDown(Exception):
    """wiki 連兩次都連不上。"""


def jget(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def fetch_raw():
    """回傳 (lua 原文, HTTP 狀態碼)。連線層失敗就地重試一次；兩次都失敗丟 SourceDown。
    HTTP 狀態碼不在這裡判（502 維護公告交給 main() 的守門：保留舊檔不覆寫）。"""
    from playwright.sync_api import sync_playwright   # 沒裝 playwright 是真的壞了，讓它照常噴錯
    for attempt in (1, 2):
        try:
            with sync_playwright() as p:
                b = p.chromium.launch()
                try:
                    pg = b.new_page()
                    resp = pg.goto(RAW, wait_until="domcontentloaded", timeout=GOTO_TIMEOUT)
                    status = resp.status if resp else 0
                    lua = pg.inner_text("body")
                finally:
                    b.close()
            return lua, status
        except Exception as e:
            txt = str(e).strip()
            msg = txt.splitlines()[0][:200] if txt else repr(e)
            if attempt == 1:
                print(f"⚠ 連不上 wiki（{msg}）⇒ {RETRY_WAIT} 秒後重試一次")
                time.sleep(RETRY_WAIT)
            else:
                raise SourceDown(msg)


def main():
    ver = jget(f"{DDRAGON}/api/versions.json")[0]
    champs = {k: v for k, v in jget(f"{DDRAGON}/cdn/{ver}/data/en_US/champion.json")["data"].items()
              if not CLASSIC_RE.match(k)}   # 濾掉經典服（見檔頭 CLASSIC_RE）
    # DDragon: name(英文) -> id ；用來把 wiki 的英雄名對回 DDragon id
    name2id = {c["name"]: cid for cid, c in champs.items()}
    ids = set(champs.keys())

    try:
        lua, status = fetch_raw()
    except SourceDown as e:
        print(f"⚠ 重試仍失敗（{e}）⇒ 保留舊的 champ_release.js 不覆寫，離開碼 1"
              "（單獨一班不用理；連續好幾班都這樣才是真的壞了）")
        sys.exit(1)
    print("raw module chars:", len(lua), "HTTP", status)

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

    # 守門（2026-10-21 主對話迴圈 #1747）：wiki 維護時回 502＋一段 207 字的公告，解析出 0 隻，
    # 舊版照樣把 {} 寫進 champ_release.js 並被推上線。來源異常或覆蓋率掉太多 ⇒ 保留舊檔不寫。
    old = {}
    try:
        with open(OUT, encoding="utf-8") as f:
            old = json.loads(f.read().strip()[len("window.CHAMP_RELEASE="):].rstrip(";\n "))
    except Exception:
        pass
    if status != 200 or len(rel) < 0.9 * len(ids) or len(rel) < 0.9 * len(old):
        print(f"⚠ 來源異常（HTTP {status}、解析 {len(rel)}/{len(ids)}、舊檔 {len(old)} 筆）⇒ 保留舊的 champ_release.js 不覆寫")
        print("  頁首：", lua[:160].replace("\n", " "))
        return
    payload = json.dumps(rel, ensure_ascii=False, sort_keys=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.CHAMP_RELEASE=" + payload + ";\n")
    print(f"champ_release.js: {len(rel)}/{len(ids)} champions, {os.path.getsize(OUT)} bytes")
    miss = sorted(ids - set(rel.keys()))
    if miss:
        print("missing:", ", ".join(miss))

if __name__ == "__main__":
    main()
