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
UA = {"User-Agent": "Mozilla/5.0 (dashboard research)"}

# Worlds 頁 Region 全名 → 儀表板聯賽碼
NAME2LG = [
    ("korea", "LCK"), ("china", "LPL"),
    ("europe", "LEC"), ("emea", "LEC"),
    ("north america", "LCS"),
    ("taiwan/hong kong/macao", "LMS"), ("taiwan", "LMS"), ("lms", "LMS"),
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


def fetch_year(y):
    url = f"https://lol.fandom.com/wiki/{y}_Season_World_Championship"
    h = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=50).read().decode("utf-8", "replace")
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


# 403/缺頁年份的手動權威表（公開史實逐年核對；本環境 fandom 全 403 → 全年份以此為準，能抓到才覆蓋）
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
    2026: ["LCK","LPL","LEC","LCP","LTA N","LTA S","CBLOL"],
}

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
        if len(lst) < 5 and y in HAND:  # 403/缺頁 → 手動權威表
            print(f"  {y}: 抓不到 → 手動表 {HAND[y]}")
            lst = HAND[y][:]
        elif len(lst) < 5 and prev:     # 當年資格未定 → 沿用前一年
            print(f"  {y}: 資料不足({lst}) → 沿用 {prev}")
            lst = prev[:]
        cache[ck] = lst; prev = lst
        print(f"  {y}: {lst}" + (f"｜未映射:{unk}" if unk else ""))
        time.sleep(1.0)
    json.dump(cache, open(OUTJ, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"寫出 {OUTJ}")


if __name__ == "__main__":
    main()
