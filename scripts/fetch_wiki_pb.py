# -*- coding: utf-8 -*-
"""從 Leaguepedia 的「Picks and Bans」頁抓比賽（2013-2015 小賽區專用）

背景（2026-07-31 使用者提供連結）：2013 的 CBLOL／拉美／台灣區資格賽／大洋洲／CIS／土耳其／GPL
在 MatchHistoryGame（ScoreboardGames）裡是 0 局——那張表只收有完整逐局數據的比賽。
但這些賽事都有人工整理的 `{賽事}/Picks and Bans` 頁，裡面有**隊伍、禁用、選用、勝方、局號**。

能拿到什麼、拿不到什麼（很重要，別誤以為資料是完整的）：
  ✔ 藍紅隊名、3+3 禁用、5+5 選用、勝方、系列賽內局號
  ✘ **選手名與路線**（PB 頁根本沒有）→ 只產生隊伍列（pid 100/200），不產生選手列。
    選手生涯統計因此不會被這批資料影響；對戰BP 的路線欄會是空的，這是誠實的空，不是 bug。
  ✘ 日期（PB 頁沒有）→ 從賽事主頁的比賽列表依「隊伍組合」配對；配不到就退用賽事起始日。

輸出：csv_cache/wikifill_{年}.json（與 fetch_wiki_mh 同一個檔、同一套 key），
由 fetch_data.merge_wiki() 併入，OE 之後若補上這些比賽會自動以 OE 為準。

用法：
  python scripts\fetch_wiki_pb.py                 # 跑 JOBS 全部
  python scripts\fetch_wiki_pb.py --probe "Riot Season 3 Brazilian Championship"
"""
import argparse, csv, html as _html, io, json, os, re, sys, time, urllib.parse, urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, "csv_cache")
HTML_DIR = os.path.join(CACHE, "wikipb")
sys.path.insert(0, HERE)

API = "https://lol.fandom.com/api.php"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
GAP = 3.0

# (年, 聯賽碼, 賽段, 季後賽, PB 頁, 取日期用的主頁)
JOBS = [
    # 季後賽的 PB 頁常常掛在「例行賽頁面底下」的子頁（使用者提示 2026-07-31：
    # 沒寫季後賽的賽事，資料多半藏在 {聯賽}/{年} Season/{賽段} Playoffs/Picks and Bans）
    (2013, "LPL", "夏季", 1, "LPL/2013 Season/Summer Playoffs/Picks and Bans",
     "LPL/2013 Season/Summer Playoffs"),
    (2013, "GPL", "春季", 0, "2013 GPL Spring/Picks and Bans", "2013 GPL Spring"),
    (2013, "GPL", "夏季", 0, "2013 GPL Summer/Picks and Bans", "2013 GPL Summer"),
    # 賽段寫「夏季」就好，PO 後綴由 fetch_data 依 playoffs 欄自己加；
    # 自己先寫 "夏季 PO" 會變成「夏季 PO PO」，前端只去掉一個 PO → 賽事卡多長出一列（2026-07-31）
    # 賽事名叫 Championship／Regional Finals 的，賽段一律標「錦標賽」（使用者定案 2026-07-31）
    # TESL（台灣電子競技聯盟職業挑戰賽）：與 GPL 夏季同期進行的台灣本土聯賽，
    # MatchHistory 沒收（0 局）但 PB 頁有 75 局。使用者指定放在 GPL 底下、夏季之後（2026-07-31）
    (2013, "GPL", "TESL", 0, "Taiwan eSports League/Professional Challenges/Picks and Bans",
     "Taiwan eSports League/Professional Challenges"),
    # GPL 的兩個錦標賽分開標（使用者定案 2026-07-31）：
    #   台港澳＝GPL 年度總決賽（春夏冠軍對決，兩隊都是台灣隊）＋台灣區世界賽代表選拔
    #   東南亞＝Season 3 Southeast Asia Regional Finals（KLH／SGS／SAJ／BKT／Mineski／Xgame 六隊；
    #           Qualifiers 不列，PB 頁本來就只收正賽 11 局）
    (2013, "GPL", "台港澳錦標賽", 0, "2013 GPL Championship/Picks and Bans", "2013 GPL Championship"),
    (2013, "GPL", "台港澳錦標賽", 0, "Season 3 Taiwan Regional Finals/Picks and Bans",
     "Season 3 Taiwan Regional Finals"),
    (2013, "GPL", "東南亞錦標賽", 0, "Season 3 Southeast Asia Regional Finals/Picks and Bans",
     "Season 3 Southeast Asia Regional Finals"),
    (2013, "CBLOL", "錦標賽", 0, "Riot Season 3 Brazilian Championship/Picks and Bans",
     "Riot Season 3 Brazilian Championship"),
    (2013, "LLA", "錦標賽", 0, "Season 3 Latin America Regional Finals/Picks and Bans",
     "Season 3 Latin America Regional Finals"),
    (2013, "LCO", "錦標賽", 0, "Riot Season 3 Oceanic Championship/Picks and Bans",
     "Riot Season 3 Oceanic Championship"),
    (2013, "LCL", "錦標賽", 0, "2013 Season CIS Championship/Picks and Bans", "2013 Season CIS Championship"),
    # 2015 GPL：MatchHistory 是 0 局，但 PB 頁有（春 96／夏 49）
    (2015, "GPL", "春季", 0, "2015 GPL Spring/Picks and Bans", "2015 GPL Spring"),
    (2015, "GPL", "夏季", 0, "2015 GPL Summer/Picks and Bans", "2015 GPL Summer"),
    # 土耳其：冬／春／夏三個 Tournament 沒有 PB 子頁，但年度總決賽 Championship 有（21 局）。
    # 使用者提供 2026-07-31：Gamescom 外卡賽的土耳其席次就是「Season 3 Turkish Championship winner」
    (2013, "TCL", "錦標賽", 0, "Riot Games Turkey/2013 Season/Championship/Picks and Bans",
     "Riot Games Turkey/2013 Season/Championship"),
]


def parse_page(page, force=False):
    """action=parse 的 HTML（存快取，可離線重跑）"""
    os.makedirs(HTML_DIR, exist_ok=True)
    fp = os.path.join(HTML_DIR, re.sub(r"[^A-Za-z0-9]+", "_", page)[:120] + ".html")
    if not force and os.path.exists(fp):
        return open(fp, encoding="utf-8").read()
    url = API + "?" + urllib.parse.urlencode({"action": "parse", "page": page, "prop": "text", "format": "json"})
    for i in range(4):
        try:
            r = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read())
        except Exception as e:
            print(f"      連線失敗（{i+1}/4）{str(e)[:70]}"); time.sleep(5 * (i + 1)); continue
        if "error" in r:
            raise RuntimeError(r["error"].get("info", "")[:150])
        h = r["parse"]["text"]["*"]
        open(fp, "w", encoding="utf-8").write(h)
        time.sleep(GAP)
        return h
    raise RuntimeError("重試多次仍失敗")


def pb_games(html):
    """PB 頁 → [{blue, red, game, win(1藍/2紅), bans{}, picks{}}]

    版型（實測 2013 各賽事一致）：一個 table.wikitable.pb ＝ 一局；
      td.pb-winner 內容就是 1／2；td.pb-ban／td.pb-pick 帶 pb-blue／pb-red，
      class 後面還會多掛 pb-border 之類的修飾 → 比對要寬鬆，不能寫死整串 class。
    """
    out = []
    for _ti, t in enumerate(re.findall(r'<table[^>]*class="[^"]*wikitable pb[^"]*"[^>]*>.*?</table>', html, re.S)):
        cls = re.search(r'class="([^"]*)"', t).group(1)
        mg = re.search(r"pb-game-(\d+)", cls)
        teams = re.findall(r'<a href="/wiki/[^"]+" class="[^"]*\bt[A-Z]{2,}\b[^"]*" title="([^"]+)"', t)
        if len(teams) < 2:
            teams = re.findall(r'class="team-object">.*?title="([^"]+)"', t, re.S)
        # 勝方判定：比分列長這樣 → [藍方比分][show/hide][紅方比分]，**帶 pb-winner class 的那一側就是勝方**。
        # 格子裡的數字是「系列賽比分」不是勝方編號（實測會出現 0／1／3）→ 只看數字一定判錯
        #（2026-07-31 使用者回報：LCO 的 Team Immunity 明明 4W0L 卻寫成 0W4L）
        win = 0
        for tr in re.findall(r"<tr.*?</tr>", t, re.S):
            if "pb-winner" not in tr:
                continue
            tds = re.findall(r"<td([^>]*)>", tr)
            if len(tds) >= 3:
                win = 1 if "pb-winner" in tds[0] else (2 if "pb-winner" in tds[2] else 0)
            break
        bp = {"blue": {"ban": [], "pick": []}, "red": {"ban": [], "pick": []}}
        for m in re.finditer(r'<td class="[^"]*\bpb-(ban|pick)\b[^"]*\bpb-(blue|red)\b[^"]*"[^>]*>(.*?)</td>', t, re.S):
            k, s, body = m.group(1), m.group(2), m.group(3)
            c = re.search(r'title="([^"]+)"', body)
            bp[s][k].append(_html.unescape(c.group(1)).strip() if c else "")
        if len(teams) < 2 or not bp["blue"]["pick"]:
            continue
        # wiki 沒建隊伍頁的小隊，title 會是「FIGJAM (page does not exist)」→ 後綴一定要剝掉，
        # 不然那個字串會變成資料庫裡的隊名，縮寫表永遠查不到、篩選列只好顯示全名
        #（2026-07-31 使用者回報：手動改的縮寫沒套用、還是出現全名）
        _tn = lambda s: re.sub(r"\s*\(page does not exist\)\s*$", "", _html.unescape(s)).strip()
        out.append({"blue": fix_case(_tn(teams[0])), "red": fix_case(_tn(teams[1])), "idx": _ti,
                    "game": int(mg.group(1)) if mg else 1, "win": win, "bp": bp})
    return out


def dates_of(html):
    """主頁 → [(日期, 隊A, 隊B)]；比賽列表每列都帶日期與兩隊"""
    out = []
    for m in re.finditer(r'<div class="matchlist-[^"]*"[^>]*>.*?</div>\s*</div>', html, re.S):
        pass
    # matchlist 的實際結構逐年不同 → 直接掃「日期 ... 兩個隊連結」的鄰近關係
    for m in re.finditer(r'(20\d\d-\d\d-\d\d)(.{0,900}?)(?=20\d\d-\d\d-\d\d|$)', html, re.S):
        d, seg = m.group(1), m.group(2)
        tms = re.findall(r'<a href="/wiki/[^"]+" class="[^"]*\bt[A-Z]{2,}\b[^"]*" title="([^"]+)"', seg)
        tms = [_html.unescape(x).strip() for x in tms]
        uniq = []
        for x in tms:
            if x not in uniq:
                uniq.append(x)
        if len(uniq) >= 2:
            out.append((d, uniq[0], uniq[1]))
    return out


def bracket_pairs(html):
    """主頁季後賽對戰表的配對 {frozenset(隊A,隊B), ...}。

    2013 這些小賽事的小組賽與季後賽寫在同一個 PB 頁，wiki 也沒有獨立的 Playoffs 賽事
    → 用主頁 bracket 的對戰組合來認季後賽（使用者 2026-07-31：CBLOL 也有季後賽，在底下有寫）。
    """
    tms = []
    for m in re.finditer(r'<div class="bracket-team[^"]*"[^>]*>(.*?)(?=<div class="bracket-team|</div>\s*</div>)',
                         html, re.S):
        t = re.search(r'title="([^"]+)"', m.group(1))
        if t:
            tms.append(re.sub(r"\s*\(page does not exist\)\s*$", "", _html.unescape(t.group(1))).strip())
    out = set()
    for i in range(0, len(tms) - 1, 2):      # bracket 內兩兩成對
        a, b = _norm(tms[i]), _norm(tms[i + 1])
        if a and b and a != b:
            out.add(frozenset((a, b)))
    return out


def mark_po(games, pairs):
    """由後往前掃：符合對戰表配對的局標成季後賽。

    小組賽也可能出現同樣的兩隊 → 連續 3 局都對不上就停，不再往前標。
    """
    if not pairs:
        return 0
    n, miss = 0, 0
    for g in reversed(games):
        if frozenset((_norm(g["blue"]), _norm(g["red"]))) in pairs:
            g["po"] = 1; n += 1; miss = 0
        else:
            miss += 1
            if miss >= 3:
                break
    return n


def span_of(html):
    ds = sorted(set(re.findall(r"\b(20\d\d-\d\d-\d\d)\b", html)))
    return (ds[0], ds[-1]) if ds else ("", "")


_norm = lambda s: re.sub(r"[^a-z0-9]", "", str(s or "").lower())
_TNAME = None


def fix_case(nm):
    """對齊主資料的隊名寫法。

    PB 頁的隊名取自連結 title，走 MediaWiki 頁名規則＝首字母一定大寫
    （paiN Gaming → PaiN Gaming）→ 跟世界賽那邊的 paiN Gaming 變成兩支不同的隊，
    「這隊有沒有打進世界賽」就判不出來（2026-07-31 實測 CBLOL 的 paiN 對不上）。
    以 2016 年起的 OE 原生資料為權威寫法（2015 以前混有 wiki 補的，不能當基準）。
    """
    global _TNAME
    if _TNAME is None:
        import glob
        _TNAME = {}
        for p in sorted(glob.glob(os.path.join(ROOT, "data", "data_*.js"))):
            try:
                if int(os.path.basename(p)[5:9]) < 2016:
                    continue
                R = json.loads(open(p, encoding="utf-8").read().split("=", 1)[1].strip().rstrip(";"))["tabs"]["RAW_DATA"]
            except Exception:
                continue
            ix = {n: i for i, n in enumerate(R[0])}
            for k in ("blue_teamname", "red_teamname"):
                if k not in ix:
                    continue
                for r in R[1:]:
                    v = str(r[ix[k]] or "").strip()
                    if v:
                        _TNAME.setdefault(v.casefold(), v)
    return _TNAME.get(str(nm or "").casefold(), nm)


def build(job, force=False):
    year, lg, split, po, pb_page, main_page = job
    key = f"{lg}_{year}_" + (re.sub(r"[^A-Za-z0-9]+", "", split) or re.sub(r"[^A-Za-z0-9]+", "", pb_page)[:24])
    print(f"\n[{year} {lg} {split or '（無賽段）'}] ← {pb_page}")
    try:
        html = parse_page(pb_page, force)
    except Exception as e:
        print(f"    PB 頁失敗：{str(e)[:110]}"); return None
    games = pb_games(html)
    print(f"    解析到 {len(games)} 局")
    if not games:
        return None
    # 日期：主頁的比賽列表 → 以隊伍組合配對；配不到用賽事起始日
    dmap, first, last = {}, "", ""
    try:
        mh = parse_page(main_page, force)
        first, last = span_of(mh)
        _npo = mark_po(games, bracket_pairs(mh))
        if _npo >= len(games):
            # 全部都符合對戰表＝整個賽事本來就是淘汰賽（大洋洲／CIS／土耳其／東南亞錦標賽），
            # 那就沒有「例行賽 vs 季後賽」可言 → 不標（2026-07-31）
            for _g in games:
                _g.pop("po", None)
            _npo = 0
        if _npo:
            print(f"    季後賽（依主頁對戰表）：{_npo} 局")
        for d, a, b in dates_of(mh):
            dmap.setdefault(frozenset((_norm(a), _norm(b))), []).append(d)
    except Exception as e:
        print(f"    主頁日期失敗（改用賽事起始日）：{str(e)[:70]}")
    if not first:
        first = last = f"{year}-01-01"

    import fetch_data
    hdr = fetch_data.oe_header() if hasattr(fetch_data, "oe_header") else None
    if not hdr:
        import fetch_fill
        hdr = fetch_fill.oe_header()
    ix = {n: i for i, n in enumerate(hdr)}
    rows, used = [], {}
    from datetime import date as _date, timedelta as _td
    _d0 = _date(*map(int, first.split("-")))
    _d1 = _date(*map(int, (last or first).split("-")))
    for g in games:
        pair = frozenset((_norm(g["blue"]), _norm(g["red"])))
        ds = dmap.get(pair) or []
        i = used.get(pair, 0)
        if ds:
            date = ds[min(i, len(ds) - 1)]
        else:
            # 主頁只有 Start/End Date、沒有逐場日期（2013 這些都是兩三天的線下賽）→
            # 同一組隊伍的第 N 次遭遇往後挪一天（夾在賽事期間內）。全部塞同一天的話，
            # 小組賽與季後賽的同組對戰會被當成同一個系列，BO 判定就錯了。
            date = min(_d0 + _td(days=i), _d1).isoformat()
        if g["game"] == 1:
            used[pair] = i + 1
        # 隊名要用完整的正規化字串，不能截斷：Saigon Jokers 與 Saigon Fantastic Five 取前 6 字
        # 都是 saigon，gameid 會撞在一起互相覆蓋（實測 GPL 春季 56 局只剩 22 局）
        # 再帶上「第幾次遭遇」：賽事只有三四天時，同一組隊伍多次對戰的推得日期會被夾在同一天，
        # 光靠 日期＋局號 還是會撞（CBLOL 19 局少 1、CIS 7 局少 1）
        # 用「表格在頁面中的序號」當識別，保證唯一：局號會重複（同一頁多個系列都各有第 2 局），
        # 光靠 隊伍＋日期＋局號＋遭遇序 還是會撞（實測 LPL 2013 夏季季後賽 7 局只進 5 局）
        gid = f"wikipb_{key}_{g.get('idx', i)}_{_norm(g['blue'])}_{_norm(g['red'])}_{date}_{g['game']}"
        for side, pid in (("blue", 100), ("red", 200)):
            r = [""] * len(hdr)
            put = lambda k, v: r.__setitem__(ix[k], "" if v is None else str(v)) if k in ix else None
            put("gameid", gid); put("datacompleteness", "partial")
            put("league", lg); put("year", year); put("split", split)
            put("playoffs", 1 if g.get("po") else po)
            put("date", date + " 00:00:00"); put("game", g["game"]); put("participantid", pid)
            put("side", side.capitalize()); put("position", "team")
            put("teamname", g[side])
            put("result", "1" if (g["win"] == (1 if side == "blue" else 2)) else "0")
            for i2, ch in enumerate(g["bp"][side]["ban"][:5]):
                put(f"ban{i2+1}", ch)
            for i2, ch in enumerate(g["bp"][side]["pick"][:5]):
                put(f"pick{i2+1}", ch)
            rows.append(r)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(hdr); w.writerows(rows)
    table = fetch_data.process(buf.getvalue(), year)
    print(f"    process() → {len(table)-1} 列（{len(games)} 局）"
          + (f"　主頁配到日期 {len(dmap)} 組" if dmap else f"　日期＝賽事期間 {first}~{last} 內依遭遇序遞推"))
    if len(table) < 2:
        return None
    p = os.path.join(CACHE, f"wikifill_{year}.json")
    D = {}
    if os.path.exists(p):
        try:
            D = json.load(open(p, encoding="utf-8"))
        except Exception:
            D = {}
    D[key] = {"header": table[0], "rows": table[1:], "games": len(games),
              "src": "leaguepedia Picks and Bans（無選手／路線）", "tour": pb_page,
              "league": lg, "split": split}
    json.dump(D, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"    → {p}（{key}）")
    return table


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe"); ap.add_argument("--force", action="store_true")
    ap.add_argument("--years", default="")
    A = ap.parse_args()
    if A.probe:
        h = parse_page(A.probe + ("" if A.probe.endswith("Picks and Bans") else "/Picks and Bans"), A.force)
        gs = pb_games(h)
        print(f"{A.probe}：{len(gs)} 局")
        for g in gs[:3]:
            print(f"   {g['blue']} vs {g['red']} 局{g['game']} 勝={g['win']}")
            print(f"     藍 ban {g['bp']['blue']['ban']} pick {g['bp']['blue']['pick']}")
        return
    yrs = {int(x) for x in A.years.split(",") if x.strip()} if A.years else None
    ok, miss = [], []
    for job in JOBS:
        if yrs and job[0] not in yrs:
            continue
        t = None
        try:
            t = build(job, A.force)
        except Exception as e:
            print(f"    例外：{type(e).__name__} {str(e)[:100]}")
        (ok if t else miss).append(f"{job[0]} {job[1]} {job[2] or '-'}")
    # 清孤兒：改過賽段名（"夏季 PO" → "夏季"）之後 key 會變，舊 key 還留在 wikifill 裡
    # → 同一批比賽被併進去兩次，而且帶著「夏季 PO PO」這種賽段名（2026-07-31 實測）
    for y in sorted({j[0] for j in JOBS if not yrs or j[0] in yrs}):
        p = os.path.join(CACHE, f"wikifill_{y}.json")
        if not os.path.exists(p):
            continue
        try:
            D = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        live = {f"{lg}_{yy}_" + (re.sub(r"[^A-Za-z0-9]+", "", sp) or re.sub(r"[^A-Za-z0-9]+", "", pg)[:24])
                for (yy, lg, sp, _po, pg, _mp) in JOBS if yy == y}
        drop = [k for k, v in D.items() if "Picks and Bans" in str(v.get("src", "")) and k not in live]
        if drop:
            for k in drop:
                D.pop(k, None)
            json.dump(D, open(p, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"\n[{y}] 清掉 {len(drop)} 個孤兒 key：{drop}")

    print("\n" + "=" * 56)
    print(f"完成 {len(ok)}：" + "、".join(ok))
    if miss:
        print(f"失敗 {len(miss)}：" + "、".join(miss))


if __name__ == "__main__":
    main()
