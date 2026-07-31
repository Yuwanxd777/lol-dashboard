# -*- coding: utf-8 -*-
"""補早年比賽的逐選手數據（KDA／CS／金錢）——比賽本身有，但欄位是空的。

為什麼需要：2013~2016 的老賽季是靠 fetch_wiki_mh.py 從 Leaguepedia 的
MatchHistoryGame **文字版**補進來的，那個來源只有選手與英雄，沒有逐選手
K/D/A、金錢、CS → 儀表板上這些欄位全空。實測空值率：
    2013 100%／2014 55%／2015 40%／2016 7%（2017 之後 OE 自己有，0%）

Leaguepedia 的 Cargo 表 ScoreboardPlayers 有這些欄位，本腳本把它抓回來。
**能補到什麼程度**（實測，別期待更多）：
    Kills/Deaths/Assists  2013 起就有
    CS                    2013 起就有
    Gold                  2016 起才有（2013~2015 wiki 也是空的）
    傷害／視野分數         wiki 早年沒有 → 補不了

走 Special:CargoExport（一般頁面請求）而非 action=cargoquery——後者對匿名
存取第一發就限流。同 fetch_wiki_mh.py 的繞法：先造訪頁面拿 cookie。

配對鍵（實測 2013-04 全月，歧義 0%、覆蓋 100%）：
    主鍵　開賽時間 + 系列賽第幾場 + 選手名
    備援　開賽時間 + 選手名 + 英雄
  需要備援是因為兩邊的 game 序號偶爾顛倒（我們記第 2 場、wiki 記第 1 場，
  同一個時間戳成對出現）。

用法：
  python scripts/fetch_wiki_stats.py                 # 預設 2013~2016
  python scripts/fetch_wiki_stats.py --years 2013
  python scripts/fetch_wiki_stats.py --force         # 忽略快取重抓
產出：csv_cache/wikistats_{年}.json，由 fetch_data.py 的 merge_stats() 併入。
"""
import argparse, collections, io, json, os, re, sys, time
import urllib.parse, urllib.request, http.cookiejar

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, "csv_cache")
RAW = os.path.join(CACHE, "lpstats")
FORM = "https://lol.fandom.com/wiki/Special:CargoExport"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
      "Accept-Language": "en-US,en;q=0.9", "Referer": FORM}
GAP = 7.0          # 請求間隔（禮貌節流）
PAGE = 2000        # 實測 CargoExport 吃得下 2000（API 版只有 500）
_OP = None

# Leaguepedia 欄位 → OE 欄位（不含 blue_/red_ 前綴）
COLMAP = {"k": "kills", "d": "deaths", "a": "assists", "cs": "total cs",
          "g": "totalgold", "dmg": "damagetochampions", "vs": "visionscore"}

norm = lambda s: re.sub(r"[^a-z0-9]", "", str(s or "").lower())
gnum = lambda gid: (str(gid or "").rsplit("_", 1)[-1] or "").strip()


def opener():
    global _OP
    if _OP is None:
        cj = http.cookiejar.CookieJar()
        _OP = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        try:
            _OP.open(urllib.request.Request(FORM, headers=UA), timeout=60).read()
            time.sleep(2)
        except Exception as e:
            print(f"  ⚠ 取 cookie 失敗（仍試著繼續）：{type(e).__name__}")
    return _OP


def fetch_range(f, t):
    """抓 [f, t) 期間的 ScoreboardPlayers，自動分頁"""
    out, off = [], 0
    while True:
        p = {"tables": "ScoreboardPlayers=SP",
             "fields": "SP.Name=nm,SP.Champion=ch,SP.Kills=k,SP.Deaths=d,SP.Assists=a,"
                       "SP.Gold=g,SP.CS=cs,SP.DamageToChampions=dmg,SP.VisionScore=vs,"
                       "SP.DateTime_UTC=dt,SP.Team=tm,SP.GameId=gid",
             "where": f'SP.DateTime_UTC >= "{f}" AND SP.DateTime_UTC < "{t}"',
             "order_by": "SP.GameId", "format": "json",
             "limit": str(PAGE), "offset": str(off)}
        url = FORM + "?" + urllib.parse.urlencode(p)
        rows = None
        for att in range(4):
            try:
                raw = opener().open(urllib.request.Request(url, headers=UA), timeout=120).read().decode("utf-8", "replace")
            except Exception as e:
                print(f"      ⚠ {type(e).__name__}，退避重試 {att+1}/4"); time.sleep(20 * (att + 1)); continue
            if raw.lstrip()[:1] not in "[{":
                print(f"      ⚠ 非 JSON，退避重試 {att+1}/4"); time.sleep(20 * (att + 1)); continue
            try:
                rows = json.loads(raw); break
            except Exception:
                time.sleep(20 * (att + 1))
        if rows is None:
            print(f"      ✗ {f}~{t} offset={off} 放棄"); break
        out += rows
        if len(rows) < PAGE:
            break
        off += PAGE
        time.sleep(GAP)
    return out


def year_rows(year, force=False):
    """某年 data 檔涵蓋的 LP 逐選手資料（分月抓，逐月快取）。

    **要含前一年 10~12 月**：冬季賽季跨年打（Champions 2013 Winter 是
    2012-12-08 開打），而 fetch_data.py 會把「世界賽後的比賽歸入隔年」，
    所以 data_{年}.js 裡有 {年-1} 年底的場次。只抓當年 1 月起會整段對不上
    ——實測 2013 的 LCK 冬季 415 列、2014 的 GPL/LCK 冬季 707 列全數落空。
    快取以「年-月」為單位，跨年的月份兩年共用，不會重複下載。"""
    os.makedirs(RAW, exist_ok=True)
    all_rows = []
    months = [(year - 1, m) for m in (10, 11, 12)] + [(year, m) for m in range(1, 13)]
    for yy, m in months:
        f = f"{yy}-{m:02d}-01"
        t = f"{yy+1}-01-01" if m == 12 else f"{yy}-{m+1:02d}-01"
        cp = os.path.join(RAW, f"{yy}-{m:02d}.json")
        if os.path.exists(cp) and not force:
            try:
                all_rows += json.load(open(cp, encoding="utf-8")); continue
            except Exception:
                pass
        rows = fetch_range(f, t)
        json.dump(rows, open(cp, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"    {yy}-{m:02d}：{len(rows)} 列")
        all_rows += rows
        time.sleep(GAP)
    return all_rows


def build(year, force=False):
    print(f"\n[{year}] 抓 Leaguepedia 逐選手數據…", flush=True)
    rows = year_rows(year, force)
    print(f"  合計 {len(rows)} 列")
    out = {}
    stat = collections.Counter()
    for x in rows:
        vals = {}
        for lpk, oek in COLMAP.items():
            v = x.get(lpk)
            if v is None or str(v).strip() == "":
                continue
            vals[oek] = str(v).strip()
            stat[oek] += 1
        if not vals:
            continue
        dt = str(x.get("dt") or "")[:16]
        nm = norm(x.get("nm"))
        if not dt or not nm:
            continue
        out["|".join((dt, gnum(x.get("gid")), nm))] = vals          # 主鍵
        out.setdefault("|".join((dt, "*", nm, norm(x.get("ch")))), vals)  # 備援鍵
    p = os.path.join(CACHE, f"wikistats_{year}.json")
    json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"  → {os.path.basename(p)}：{len(out)} 個鍵")
    print("  可補欄位：" + "、".join(f"{k} {v}" for k, v in stat.most_common()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2013,2014,2015,2016")
    ap.add_argument("--force", action="store_true")
    A = ap.parse_args()
    for y in [int(x) for x in A.years.split(",") if x.strip()]:
        build(y, A.force)
    print("\n下一步：python scripts/fetch_data.py（會由 merge_stats 併入）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
