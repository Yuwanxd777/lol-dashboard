# -*- coding: utf-8 -*-
"""查某個賽段的「季後賽從哪一天開始」——OE 有時整段不標 playoffs 欄，
儀表板就會把季後賽當成例行賽（2026-08-26 使用者回報 LCP 8/20 已開打卻還是 S3）。

作法：Leaguepedia 的 action=parse（**不要用 Cargo**，匿名限流極兇，實測第二次就 ratelimited）
拿整頁 HTML → ① 讀 Playoffs 段的對戰表（誰對誰、幾比幾）② 讀完整賽程表（data-date）
→ 對照兩者，就知道括號賽的第一場是哪一天。

用法：python wiki_po_start.py "LCP/2026 Season/Split 3" [--from 2026-08-01]
"""
import argparse, html, io, json, os, re, sys, time, urllib.parse, urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
CACHE = os.path.join(HERE, "..", "csv_cache", "wiki_po")

ap = argparse.ArgumentParser()
ap.add_argument("page", nargs="+")
ap.add_argument("--from", dest="t0", default="2026-08-01")
ap.add_argument("--refresh", action="store_true", help="不用快取，重抓")
A = ap.parse_args()


def page_html(page):
    os.makedirs(CACHE, exist_ok=True)
    fp = os.path.join(CACHE, re.sub(r"[^A-Za-z0-9]+", "_", page) + ".html")
    if os.path.exists(fp) and not A.refresh:
        return io.open(fp, encoding="utf-8").read()
    u = "https://lol.fandom.com/api.php?" + urllib.parse.urlencode(
        {"action": "parse", "page": page, "prop": "text", "format": "json"})
    d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read())
    if "error" in d:
        raise SystemExit("Wiki 回錯：%s" % d["error"].get("code"))
    h = d["parse"]["text"]["*"]
    io.open(fp, "w", encoding="utf-8").write(h)
    time.sleep(3)
    return h


def strip(x):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x))).replace("⁠", "").strip()


for page in A.page:
    print("══════ %s ══════" % page)
    try:
        h = page_html(page)
    except Exception as e:
        print("  抓不到：%s" % e); continue
    for sec in ("Playoffs", "Play-In", "Knockout_Stage", "Bracket_Stage"):
        i = h.find('id="%s"' % sec)
        if i < 0:
            continue
        print("  【%s】%s" % (sec, strip(h[i:i + 9000])[:420]))
    rows = re.findall(r'<tr class="[^"]*ml-row[^"]*"[^>]*data-date="([^"]+)"[^>]*>(.*?)</tr>', h, flags=re.S)
    print("  ── 賽程（%s 起）──" % A.t0)
    for d, body in rows:
        if d < A.t0:
            continue
        tds = [strip(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", body, flags=re.S)]
        tds = [t for t in tds if t]
        # 只留「隊名 比分 比分 隊名」那幾格，時間欄很長丟掉
        tds = [t for t in tds if not re.match(r"^\d{1,2} \w+ 20\d\d", t)]
        print("     %s  %s" % (d, " ".join(tds)[:60]))
