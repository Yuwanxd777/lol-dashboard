# -*- coding: utf-8 -*-
"""隊徽補洞：dpm 沒有的隊 → Leaguepedia 的「{隊名}logo square.png」→ img/teams/{縮寫}.webp

使用者 2026-11-01：「缺的戰隊隊徽都去 WIKI 找」（籤運表歷年的 BDS／MAD／NRG 都是灰盾牌）。
fetch_team_logos.py 只抓 dpm（現役、有積分帳號的隊），歷年資料裡的隊大多沒有。
做法：
  ① 隊名＝data/data_YYYY.js 全部年份出現過的隊（國家隊除外，它們走國旗）。
  ② 縮寫要跟畫面一致 ⇒ 開無頭頁面直接呼叫前端的 tAb()／teamFix()（縮寫表很多層，不在 Python 重寫一份）。
  ③ 已有 img/teams/{縮寫}.webp 就跳過（dpm 的優先）；同一個縮寫多隊共用時取最近一年出現的那隊。
  ④ Leaguepedia API 一次 50 個檔名查 imageinfo（跟著 redirect），拿 128px 縮圖 → 轉 webp。
     square 沒有再試 std。查不到的記進 csv_cache/team_logo_wiki_miss.json，30 天內不重查。
跑完要再跑 scripts/build_img_manifest.py（前端先查 IMG_HAVE 才放 <img>）。這支結尾會自己呼叫。
用法：python scripts/fetch_team_logos_wiki.py [--dry]
"""
import datetime, io, json, os, subprocess, sys, time, urllib.parse, urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "img", "teams")
MISS = os.path.join(ROOT, "csv_cache", "team_logo_wiki_miss.json")
API = "https://lol.fandom.com/api.php"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}
PX = 128


def all_names():
    last = {}
    for y in range(2013, datetime.date.today().year + 1):
        fn = os.path.join(ROOT, "data", f"data_{y}.js")
        if not os.path.exists(fn):
            continue
        d = open(fn, encoding="utf-8").read()
        R = json.loads(d[d.index("=") + 1:].rstrip().rstrip(";"))["tabs"]["RAW_DATA"]
        h = R[0]; iB, iR, iP = h.index("blue_teamname"), h.index("red_teamname"), h.index("participantid")
        for r in R[1:]:
            if str(r[iP]) == "100":
                for n in (r[iB], r[iR]):
                    if n and "(National Team)" not in n:
                        last[n] = y
    return last


def abbrs(names):
    """前端的 tAb＋teamFix（無頭開頁面，本機 server 開在 8772）"""
    from playwright.sync_api import sync_playwright
    srv = subprocess.Popen([sys.executable, "-m", "http.server", "8772", "--bind", "127.0.0.1"], cwd=ROOT,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(); pg = b.new_page()
            pg.goto("http://127.0.0.1:8772/index.html", wait_until="load")
            pg.wait_for_function("typeof GAMES!=='undefined' && GAMES.length>0", timeout=180000)
            res = pg.evaluate("(ns)=>ns.map(n=>teamFix(String(tAb(n)||'')))", names)
            b.close()
    finally:
        srv.terminate()
    return dict(zip(names, res))


def api(params):
    params = dict(params, format="json")
    for k in range(4):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(API + "?" + urllib.parse.urlencode(params), headers=UA),
                                                     timeout=60).read())
        except Exception as e:
            print(f"   API 失敗（{k + 1}/4）：{str(e)[:80]}"); time.sleep(8 * (k + 1))
    return {}


def thumbs(files):
    """檔名清單 → {檔名: 縮圖網址}（跟著 redirect；一次 50 個）"""
    out = {}
    for i in range(0, len(files), 50):
        chunk = files[i:i + 50]
        r = api({"action": "query", "titles": "|".join("File:" + f for f in chunk), "prop": "imageinfo",
                 "iiprop": "url", "iiurlwidth": PX, "redirects": 1})
        q = r.get("query") or {}
        back = {}
        for x in (q.get("normalized") or []) + (q.get("redirects") or []):
            back[x["to"]] = back.get(x["from"], x["from"])
        for pg in (q.get("pages") or {}).values():
            ii = (pg.get("imageinfo") or [None])[0]
            if not ii:
                continue
            src = pg["title"]
            while src in back:
                src = back[src]
            out[src.replace("File:", "", 1)] = ii.get("thumburl") or ii.get("url")
        time.sleep(1.5)
    return out


def to_webp(data, fn):
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert("RGBA")
    if max(im.size) > PX:
        im.thumbnail((PX, PX), Image.LANCZOS)
    im.save(fn, "WEBP", quality=90, method=6)


def main():
    dry = "--dry" in sys.argv
    last = all_names()
    ab = abbrs(sorted(last))
    have = {f[:-5] for f in os.listdir(OUT) if f.endswith(".webp")}
    miss = json.load(open(MISS, encoding="utf-8")) if os.path.exists(MISS) else {}
    today = datetime.date.today()
    want = {}   # 縮寫 → 隊名（取最近一年出現的）
    for n, a in ab.items():
        # tAb 回全名＝沒有縮寫（跳過）；但 NRG／TSM 這種隊名本身就是縮寫的要照抓
        if not a or (a == n and (" " in n or len(n) > 5)) or a in have or "/" in a or "\\" in a:
            continue
        m = miss.get(n)
        if m and (today - datetime.date.fromisoformat(m)).days < 30:
            continue
        if a not in want or last[n] > last[want[a]]:
            want[a] = n
    print(f"隊名 {len(last)}、缺隊徽要查 {len(want)} 個縮寫")
    if dry:
        for a, n in sorted(want.items()): print("  ", a, n)
        return 0
    got = {}
    for suf in ("logo square.png", "logo std.png"):
        left = [n for n in want.values() if n not in got]
        if not left:
            break
        t = thumbs([n + suf for n in left])
        for n in left:
            if n + suf in t:
                got[n] = t[n + suf]
    # 還沒找到的：隊名本身可能是轉址／同名消歧義（Rogue → Rogue (European Team)）⇒ 先問隊伍頁的正式頁名再查一次
    left = [n for n in want.values() if n not in got]
    canon = {}
    for i in range(0, len(left), 50):
        r = api({"action": "query", "titles": "|".join(left[i:i + 50]), "redirects": 1})
        q = r.get("query") or {}
        mp = {x["from"]: x["to"] for x in (q.get("normalized") or []) + (q.get("redirects") or [])}
        for n in left[i:i + 50]:
            t = n
            while t in mp and mp[t] != t:
                t = mp[t]
            if t != n:
                canon[n] = t
        time.sleep(1.5)
    for alt in (" (European Team)", " (North American Team)", " (Chinese Team)", " (Korean Team)", " (Vietnamese Team)"):
        for n in left:
            canon.setdefault(n + "|" + alt, n + alt)
    if canon:
        for suf in ("logo square.png", "logo std.png"):
            t = thumbs(sorted({c + suf for c in canon.values()}))
            for k, c in canon.items():
                n = k.split("|")[0]
                if n not in got and c + suf in t:
                    got[n] = t[c + suf]
    ok = 0
    for a, n in sorted(want.items()):
        u = got.get(n)
        if not u:
            miss[n] = today.isoformat(); continue
        try:
            to_webp(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read(), os.path.join(OUT, a + ".webp"))
            ok += 1; miss.pop(n, None)
        except Exception as e:
            print(f"   {a} {n} 下載失敗：{str(e)[:80]}"); miss[n] = today.isoformat()
        time.sleep(0.3)
    json.dump(miss, open(MISS, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"隊徽（Leaguepedia）：新增 {ok}／wiki 也沒有 {len(want) - ok} → img/teams/")
    subprocess.run([sys.executable, os.path.join(HERE, "build_img_manifest.py")])
    return 0


if __name__ == "__main__":
    sys.exit(main())
