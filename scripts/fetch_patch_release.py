# -*- coding: utf-8 -*-
"""各版本的「改版日期」→ csv_cache/patch_release.json

為什麼需要：2013~2016 的比賽有一半沒有版本號（wiki 的 MatchHistoryGame／
Picks and Bans 都沒這欄）。原本靠「同期其他比賽在打哪一版」回推，但那要求同期
剛好有別的賽事有版本資料——LCL 2013 那三天就完全沒有，整段留空。
改用官方改版日期直接回推：比賽日期落在哪兩個改版之間，就是那一版。

來源：LoL 遊戲 wiki（leagueoflegends.fandom.com）的版本頁 V3.8，
Infobox 寫 `|Release = June 13, 2013`。Leaguepedia（電競 wiki）沒有這張表，
它的 Patch 3.08 頁只有改動內容、沒有日期。
MediaWiki API 一次可查 50 頁，2013~2016 共 84 版只要兩個請求。

輸出格式（儀表板版本碼 → 改版日）：{"13.08": "2013-06-13", ...}
版本碼＝大版本+10（3.x=2013、4.x=2014…），次號補零，與 fetch_data 的
float(patch)+10 一致。

用法：
  python scripts/fetch_patch_release.py              # 預設 3.x~6.x（2013~2016）
  python scripts/fetch_patch_release.py --major 3,4  # 只抓指定大版本
  python scripts/fetch_patch_release.py --force      # 忽略快取重抓
"""
import argparse, io, json, os, re, sys, time, urllib.parse, urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, "csv_cache")
OUT = os.path.join(CACHE, "patch_release.json")
API = "https://leagueoflegends.fandom.com/api.php"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
# 每個大版本的最大次號（多抓幾個沒關係，查無的頁面會被 API 標 missing）
MAXMINOR = {3: 15, 4: 21, 5: 24, 6: 24, 7: 24, 8: 24}
MONTH = {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june",
     "july", "august", "september", "october", "november", "december"])}


def parse_date(s):
    """`June 13, 2013` / `April 3rd, 2014` / `2013-06-13` → `2013-06-13`

    序數後綴（st/nd/rd/th）一定要吃掉：LoL wiki 從 4.x 起就改寫成
    「April 3rd, 2014」，不處理的話 2014 之後幾乎全部解析失敗。
    """
    s = re.sub(r"<[^>]+>|\[\[|\]\]|'''", " ", str(s or "")).strip()
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})", s, re.I)
    if m and m.group(1).lower() in MONTH:
        return f"{int(m.group(3)):04d}-{MONTH[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"
    return ""


def fetch(titles):
    """批次取 wikitext：{頁名: wikitext}"""
    q = {"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
         "titles": "|".join(titles), "format": "json", "formatversion": "2"}
    url = API + "?" + urllib.parse.urlencode(q)
    for a in range(4):
        try:
            d = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read())
        except Exception as e:
            print(f"    ⚠ {type(e).__name__}，退避重試 {a+1}/4"); time.sleep(15 * (a + 1)); continue
        out = {}
        for p in d.get("query", {}).get("pages", []):
            if p.get("missing"):
                continue
            try:
                out[p["title"]] = p["revisions"][0]["slots"]["main"]["content"]
            except Exception:
                pass
        return out
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--major", default="3,4,5,6")
    ap.add_argument("--force", action="store_true")
    A = ap.parse_args()
    majors = [int(x) for x in A.major.split(",") if x.strip()]

    old = {}
    if os.path.exists(OUT) and not A.force:
        try:
            old = json.load(open(OUT, encoding="utf-8"))
        except Exception:
            old = {}

    # 頁名兩種寫法都要試：早期是補零的 V3.02，4.x 起改成 V4.5／V4.10。
    # 只查一種會整段落空（V3.1 根本不存在）。查無的頁 API 會標 missing，不影響。
    titles = []
    for mj in majors:
        for mi in range(1, MAXMINOR.get(mj, 24) + 1):
            for t in (f"V{mj}.{mi}", f"V{mj}.{mi:02d}"):
                if t not in titles:
                    titles.append(t)
    print(f"要查 {len(titles)} 個版本頁（{majors}）")
    got = dict(old)
    n_new = 0
    for i in range(0, len(titles), 50):
        batch = titles[i:i + 50]
        pages = fetch(batch)
        print(f"  第 {i//50+1} 批：{len(batch)} 頁 → 取回 {len(pages)}")
        for t, w in pages.items():
            m = re.match(r"^V(\d+)\.(\d+)$", t)
            if not m:
                continue
            key = f"{int(m.group(1)) + 10}.{int(m.group(2)):02d}"
            rel = re.search(r"\|\s*Release\s*=\s*([^\n|}]+)", w, re.I)
            d = parse_date(rel.group(1)) if rel else ""
            if d:
                if key not in got:
                    n_new += 1
                got[key] = d
        if i + 50 < len(titles):
            time.sleep(3)

    os.makedirs(CACHE, exist_ok=True)
    json.dump(dict(sorted(got.items())), open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n→ {OUT}：{len(got)} 個版本（新增 {n_new}）")
    for k in sorted(got)[:6]:
        print(f"   {k} → {got[k]}")
    if len(got) > 6:
        print(f"   …最後：{sorted(got)[-1]} → {got[sorted(got)[-1]]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
