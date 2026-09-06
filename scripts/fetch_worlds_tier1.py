# -*- coding: utf-8 -*-
"""一級賽區＝該年有世界賽席位（正賽或入圍賽）的賽區（使用者定義，2026-07-16）。
資料源：lol.fandom「{Y}_Season_World_Championship」頁的 Qualified 資格表 Region 欄。
輸出 csv_cache/worlds_tier1.json = {year:[dashboard 聯賽碼,...]}；歷史年份永久快取，當年每次重抓；
當年資格未定（清單過小）→ 沿用前一年。build_league_struct.py 讀此檔把 t1 旗標寫進 league_struct.js。
用法：python scripts\\fetch_worlds_tier1.py [--force]
"""
import io, sys, json, os, re, time, urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
OUTJ = os.path.join(ROOT, "csv_cache", "worlds_tier1.json")
FORCE = "--force" in sys.argv
YEARS = list(range(2014, 2027))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}
HTML_DIR = os.path.join(ROOT, "csv_cache", "worlds_html")   # 抓到的頁面 HTML（離線測試 fetch_worlds_tier1_test.py 用）

# Worlds 頁 Region 全名 → 儀表板聯賽碼
NAME2LG = [
    ("korea", "LCK"), ("china", "LPL"),
    ("europe", "LEC"), ("emea", "LEC"),
    ("north america", "LCS"),
    ("taiwan/hong kong/macao", "LMS"), ("taiwan", "LMS"), ("lms", "LMS"),
    ("asia-pacific", "LCP"), ("asia pacific", "LCP"), ("lcp", "LCP"),   # 2025 起 LCP（要排在 pacific 前面）
    ("pacific", "PCS"), ("pcs", "PCS"),
    ("southeast asia", "GPL"), ("garena premier league", "GPL"), ("sea", "GPL"),
    ("vietnam", "VCS"),
    ("brazil", "CBLOL"),
    ("cis", "LCL"), ("commonwealth of independent states", "LCL"),
    ("turkey", "TCL"), ("türkiye", "TCL"),
    ("japan", "LJL"),
    ("latin america - north", "LLN"), ("latin america north", "LLN"),
    ("latin america - south", "CLS"), ("latin america south", "CLS"),
    ("latin america", "LLA"),
    ("oceania", "LCO"),
    ("lta north", "LTA N"), ("lta south", "LTA S"), ("americas", "LTA"),
    ("international wildcard", None), ("world championship", None), ("international", None),
]


def lg_of(name):
    n = re.sub(r"\s+", " ", name).strip().lower()
    for k, c in NAME2LG:
        if n.startswith(k):
            return c
    return f"?{name.strip()}"   # 未映射 → 帶問號回報


def fetch_page_html(page, opener=None):
    """先走 api.php?action=parse（2026-09-06 實測：本環境 /wiki/ 直連不管什麼 UA 一律 403，api.php 0.5 秒 200），
    失敗才退回 /wiki/ 直連。抓到的 HTML 存 csv_cache/worlds_html/{page}.html。opener 參數給測試注入。"""
    import urllib.parse
    opener = opener or (lambda url: urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=50).read())
    errs = []
    api = "https://lol.fandom.com/api.php?" + urllib.parse.urlencode(
        {"action": "parse", "page": page, "prop": "text", "format": "json", "formatversion": "2"})
    h = None
    try:
        j = json.loads(opener(api).decode("utf-8", "replace"))
        if "error" in j:
            raise RuntimeError(j["error"].get("info") or str(j["error"]))
        h = j["parse"]["text"]
    except Exception as e:
        errs.append(f"api.php {e}")
        try:
            h = opener(f"https://lol.fandom.com/wiki/{page}").decode("utf-8", "replace")
        except Exception as e2:
            errs.append(f"wiki {e2}")
            raise RuntimeError("；".join(errs))
    try:
        os.makedirs(HTML_DIR, exist_ok=True)
        with open(os.path.join(HTML_DIR, page + ".html"), "w", encoding="utf-8") as f:
            f.write(h)
    except OSError:
        pass
    return h


def fetch_year(y):
    return parse_year(fetch_page_html(f"{y}_Season_World_Championship"))


def parse_year(h):
    """Worlds 頁 HTML → (聯賽碼清單, 未映射賽區清單)。"""
    i = h.find("Qualified for")
    if i < 0:
        i = h.find("region-icon")
    j = h.find('id="Format"', i)
    if j < 0:
        j = i + 200000
    seg = h[i:j]
    out, unk = [], []
    for m in re.finditer(r'region-icon[^>]*>\s*[A-Za-z]{2,6}\s*</div>\s*([^<]{2,40})</td>', seg):
        c = lg_of(m.group(1))
        if c is None:
            continue
        if str(c).startswith("?"):
            if c not in unk: unk.append(c)
            continue
        if c not in out:
            out.append(c)
    return out, unk


# 403/缺頁年份的手動權威表（公開史實逐年核對；/wiki/ 直連全 403，2026-09-06 起改走 api.php 抓得到 → 抓到且全部映射成功才覆蓋）
HAND = {
    2014: ["LCK","LPL","LEC","LCS","LMS","GPL","CBLOL","TCL"],
    2015: ["LCK","LPL","LEC","LCS","LMS","GPL","CBLOL"],
    2016: ["LCK","LPL","LEC","LCS","LMS","CBLOL","LCL"],
    2017: ["LCK","LPL","LEC","LCS","LMS","GPL","CBLOL","LCL","TCL","LJL","LLN","CLS","LCO"],
    2018: ["LCK","LPL","LEC","LCS","LMS","VCS","GPL","CBLOL","LCL","TCL","LJL","LLN","CLS","LCO"],
    2019: ["LCK","LPL","LEC","LCS","LMS","VCS","CBLOL","LCL","TCL","LJL","LLA","LCO"],
    2020: ["LCK","LPL","LEC","LCS","PCS","VCS","CBLOL","LCL","TCL","LJL","LLA","LCO"],
    2021: ["LCK","LPL","LEC","LCS","PCS","VCS","CBLOL","LCL","TCL","LJL","LLA","LCO"],
    2022: ["LCK","LPL","LEC","LCS","PCS","VCS","CBLOL","LJL","LLA","TCL","LCO"],
    2023: ["LCK","LPL","LEC","LCS","PCS","VCS","CBLOL","LJL","LLA"],
    2024: ["LCK","LPL","LEC","LCS","PCS","VCS","CBLOL","LJL","LLA"],
    2025: ["LCK","LPL","LEC","LCP","LTA N","LTA S"],
    2026: ["LCK","LPL","LEC","LCP","LCS","CBLOL"],   # 2026-09-06：LTA 解散，data_2026.js 只有 LCS／CBLOL 列（Worlds 頁 Region＝North America／Brazil）
}

def decide_year(y, lst, unk, prev):
    """抓取結果 → 該年最終清單。回傳 (清單, 說明列)。
    規則：有未映射賽區 ⇒ 整年不採抓取結果（NAME2LG 要補，漏一個一級賽區比沿用手動表更糟）；
    清單 < 5 ⇒ 手動表，沒有手動表 ⇒ 沿用前一年；否則以抓取為準，跟手動表不同時印出來。"""
    notes = []
    lst = list(lst)
    if unk:
        notes.append(f"⚠ 未映射賽區 {unk}（NAME2LG 要補）→ 不採抓取結果 {lst}")
        lst = []
    if len(lst) < 5 and y in HAND:  # 403/缺頁/未映射 → 手動權威表
        notes.append(f"抓不到 → 手動表 {HAND[y]}")
        lst = HAND[y][:]
    elif len(lst) < 5 and prev:     # 當年資格未定 → 沿用前一年
        notes.append(f"資料不足({lst}) → 沿用 {prev}")
        lst = prev[:]
    elif y in HAND and set(lst) != set(HAND[y]):
        notes.append(f"抓取 {lst} ≠ 手動表 {HAND[y]}（以抓取為準；手動表該更新）")
    return lst, notes


def main():
    cache = {}
    if os.path.exists(OUTJ) and not FORCE:
        cache = json.load(open(OUTJ, encoding="utf-8"))
    import datetime
    nowy = datetime.date.today().year
    prev = []
    for y in YEARS:
        ck = str(y)
        if ck in cache and y < nowy and not FORCE:
            prev = cache[ck]; print(f"  {y}: 快取 {cache[ck]}"); continue
        try:
            lst, unk = fetch_year(y)
        except Exception as e:
            print(f"  {y}: 抓取失敗 {e}"); lst, unk = [], []
        lst, notes = decide_year(y, lst, unk, prev)
        for n in notes:
            print(f"  {y}: {n}")
        cache[ck] = lst; prev = lst
        print(f"  {y}: {lst}")
        time.sleep(1.0)
    json.dump(cache, open(OUTJ, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"寫出 {OUTJ}")


if __name__ == "__main__":
    main()
