# -*- coding: utf-8 -*-
"""補充賽事名單（events_extra.js）

用途：OE 的比賽資料沒收錄、但賽事確實存在的場合，讓圖鑑「賽事」樹一樣看得到，例如
  - EWC 2026 中國區線上資格賽（OE 沒收）
  - ENC 2026 電競國家盃（11 月才打，國家隊形式）
資料源：Leaguepedia（lol.fandom.com）的 action=parse HTML。
  Cargo API 對機器人限流很兇（動輒退避數分鐘），改直接解析頁面 HTML 反而穩。

輸出：events_extra.js
  window.EVENTS_EXTRA = { "2026": { "<賽事碼>": {teams:[全名...], from, to, page, url} } }
賽事碼要用儀表板內部的碼（EWCQ中國／ENC…），前端 eventsTreeHTML 會把它併進賽事樹；
EWCQ* 會再被合併卡吸收成 EWC 卡底下的資格賽分段。

用法：python scripts\fetch_events_extra.py
"""
import io, sys, os, re, json, time, html as _html, urllib.request, urllib.parse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "events_extra.js")
API = "https://lol.fandom.com/api.php"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}

# kind: "team"＝一般戰隊（取 team-template 全名）／"nation"＝國家隊（取 X (National Team)）
# 鍵含「#」＝賽段名單補充（LPL#S3＝S3 開賽前的 wiki 陣容），前端賽事樹不會把它當獨立賽事卡
EVENTS = {
    # 2013-2015 的小賽區：Leaguepedia 有賽事頁與參賽隊，但沒有逐局 scoreboard（fetch_wiki_mh 抓 0 局）
    # → 至少讓圖鑑「賽事」樹看得到這些聯賽存在（使用者要求 2026-07-31）。
    # splits＝一個賽段一個頁；po_page＝該賽段的季後賽（2013 GPL 只有夏季有，就 Championship 那一場）
    2013: {
        # GPL 底下還有一個「台灣區世界賽資格賽」（Season 3 Taiwan Regional Finals），
        # 打完才定出世界賽代表隊 → 當成 GPL 的一個賽段（使用者指定 2026-07-31）
        "GPL":   {"splits": [{"sp": "春季", "page": "2013 GPL Spring"},
                             {"sp": "夏季", "page": "2013 GPL Summer", "po_page": "2013 GPL Championship"},
                             {"sp": "世界賽資格賽", "page": "Season 3 Taiwan Regional Finals"}]},
        "TCL":   {"splits": [{"sp": "冬季", "page": "Riot Games Turkey/2013 Season/Winter Tournament"},
                             {"sp": "春季", "page": "Riot Games Turkey/2013 Season/Spring Tournament"},
                             {"sp": "夏季", "page": "Riot Games Turkey/2013 Season/Summer Tournament"}]},
        "CBLOL": {"page": "Riot Season 3 Brazilian Championship"},
        "LCO":   {"page": "Riot Season 3 Oceanic Championship"},
        "LCL":   {"page": "2013 Season CIS Championship"},
        "LLA":   {"page": "Season 3 Latin America Regional Finals"},
    },
    2015: {
        "GPL":   {"splits": [{"sp": "春季", "page": "2015 GPL Spring", "po_page": "2015 GPL Spring/Playoffs"},
                             {"sp": "夏季", "page": "2015 GPL Summer", "po_page": "2015 GPL Summer/Playoffs"}]},
    },
    2026: {
        "EWCQ中國": {"page": "Esports World Cup 2026/Online Qualifiers/China", "kind": "team"},
        "ENC":      {"page": "Esports Nations Cup 2026",                       "kind": "nation"},
        "LPL#S3":   {"page": "LPL/2026 Season/Split 3",                        "kind": "team"},
    },
}


def parse_page(page):
    p = {"action": "parse", "page": page, "prop": "text", "format": "json"}
    url = API + "?" + urllib.parse.urlencode(p)
    for attempt in range(4):
        try:
            r = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
        except Exception as e:
            print(f"    連線失敗（{attempt+1}/4）：{str(e)[:80]}")
            time.sleep(6 * (attempt + 1)); continue
        if "error" in r:
            raise RuntimeError(r["error"].get("info", "")[:200])
        return r["parse"]["text"]["*"]
    raise RuntimeError("重試多次仍失敗")


def teams_of(html, kind):
    if kind == "nation":
        # 國家隊：連結 title 就是 "China (National Team)"
        names = re.findall(r'title="([^"]+?\((?:National Team)\))"', html, re.I)
    else:
        # ① 新版型：team-template-text 裡的連結 title。這條同一隊會同時列全名與縮寫
        #    （EDward Gaming／EDG）→ 只留全名
        names = [n for n in re.findall(r'class="[^"]*team-template-text[^"]*"[^>]*>\s*<a[^>]*title="([^"]+)"', html)
                 if len(n) > 4 and not n.isupper()]
        # ② 舊版型（2013-2015 的賽事頁）：span.teamname 裡面——有 wiki 頁的是 <a title="X">，
        #    沒建頁的小隊是 <span class="new" title="X (page does not exist)">。這裡的 title 本來就是
        #    完整隊名，**不能**再套「去掉全大寫」那個過濾，不然 FIGJAM 這種老隊會整批被丟掉。
        for m in re.finditer(r'class="teamname"[^>]*>\s*<(?:a|span)[^>]*title="([^"]+)"', html):
            names.append(re.sub(r"\s*\(page does not exist\)\s*$", "", m.group(1)))
    seen, out = set(), []
    for n in names:
        n = _html.unescape(n).strip()   # Anyone&#39;s Legend → Anyone's Legend（要與主資料全名對得上）
        if n and n not in seen:
            seen.add(n); out.append(n)
    return out


ROLE_ZH = {"Top Laner": "TOP", "Jungler": "JNG", "Mid Laner": "MID", "Bot Laner": "BOT",
           "AD Carry": "BOT", "Support": "SUP", "Coach": "COACH"}


def rosters_of(html):
    """每隊名單：Leaguepedia 的 table.tournament-roster，一隊一表；選手 catlink-players，位置在 span title"""
    out = {}
    for t in re.findall(r'<table[^>]*class="[^"]*tournament-roster[^"]*"[^>]*>.*?</table>', html, re.S):
        mt = re.search(r'class="[^"]*catlink-teams[^"]*"[^>]*title="([^"]+)"', t)
        if not mt:
            continue
        team = _html.unescape(mt.group(1)).strip()
        players, seen = [], set()
        # 每個選手格：<span title="Jungler" …> 之後跟著 catlink-players（順序穩定）
        for m in re.finditer(r'<span[^>]*title="([^"]*)"[^>]*class="[^"]*sprite[^"]*"[^>]*>|class="[^"]*catlink-players[^"]*"[^>]*>([^<]+)</a>', t):
            if m.group(2):
                nm = _html.unescape(m.group(2)).strip()
                if nm and nm not in seen:
                    seen.add(nm); players.append({"n": nm, "r": rosters_of._last_role})
            elif m.group(1) in ROLE_ZH:
                rosters_of._last_role = ROLE_ZH[m.group(1)]
        if players:
            out[team] = players
    return out


rosters_of._last_role = ""


def dates_of(html):
    ds = sorted(set(re.findall(r"\b(20\d\d-\d\d-\d\d)\b", html)))
    return (ds[0], ds[-1]) if ds else ("", "")


_TNAME = None


def fix_case(nm):
    """還原隊名的正確大小寫。

    wiki 的 title 屬性走 MediaWiki 頁名規則，首字母一定大寫（paiN Gaming → PaiN Gaming、
    ahq eSports Club → Ahq eSports Club）→ 跟主資料的隊名對不上，賽事樹會當成兩支不同的隊。
    以 data_*.js 既有的隊名為準做 casefold 比對；沒比對到的（純補充賽事、沒有比賽資料）就原樣保留。
    """
    global _TNAME
    if _TNAME is None:
        import glob
        _TNAME = {}
        for p in sorted(glob.glob(os.path.join(ROOT, "data", "data_*.js"))):
            try:
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


def bracket_of(html):
    """季後賽對戰表（div.bracket-team）裡的隊伍＝打進季後賽的隊 → 賽事樹的綠勾。

    2013 那些小賽區是「小組賽＋季後賽同一頁、同一個賽段名（甚至沒有賽段名）」，
    沒辦法像現代聯賽那樣靠 split 帶 PO 判斷 → 直接讀對戰表（使用者要求 2026-07-31）。
    """
    out, seen = [], set()
    for b in re.findall(r'<div class="bracket-team[^"]*"[^>]*>(.*?)(?=<div class="bracket-team|</div>\s*</div>)',
                        html, re.S):
        m = re.search(r'title="([^"]+)"', b)
        if not m:
            continue
        nm = fix_case(_html.unescape(m.group(1)).strip())
        if nm and nm not in seen:
            seen.add(nm); out.append(nm)
    return out


def grab(page, kind):
    html = parse_page(page)
    frm, to = dates_of(html)
    return ([fix_case(t) for t in teams_of(html, kind)], rosters_of(html), frm, to, bracket_of(html))


def main():
    old = {}
    if os.path.exists(OUT):                       # 抓失敗時保留舊資料，不要把檔案清空
        try:
            old = json.loads(re.sub(r"^window\.EVENTS_EXTRA=|;\s*$", "", open(OUT, encoding="utf-8").read().strip()))
        except Exception:
            old = {}
    data = {str(y): dict(old.get(str(y), {})) for y in EVENTS}
    for year, evs in EVENTS.items():
        for code, cfg in evs.items():
            kind = cfg.get("kind", "team")
            # ── 分賽段的賽事（splits）：一個賽段一個 wiki 頁，另可指定 po_page＝該賽段的季後賽
            #    （例：2013 GPL 只有夏季有季後賽，就是 2013 GPL Championship 那一場）
            if cfg.get("splits"):
                print(f"[{year}] {code}（{len(cfg['splits'])} 個賽段）")
                segs, allt, frm0, to0 = [], [], "", ""
                for sp in cfg["splits"]:
                    try:
                        teams, _rs, frm, to, brk = grab(sp["page"], kind)
                    except Exception as e:
                        print(f"   {sp['sp']} 失敗：{str(e)[:100]}"); continue
                    # 對戰表涵蓋全部參賽隊＝整個賽事就是淘汰賽（2013 土耳其／大洋洲／CIS 都是）→
                    # 那就沒有「誰晉級」可言，全部打勾等於沒打勾 → 不標
                    po = list(brk) if 0 < len(brk) < len(teams) else []
                    if sp.get("po_page"):   # 季後賽另有獨立頁 → 該頁的參賽隊全是晉級隊
                        try:
                            po2, _r2, _f2, to2, _b2 = grab(sp["po_page"], kind)
                            po = po2 if (0 < len(po2) < len(teams)) else po
                            if to2 > to:
                                to = to2
                            time.sleep(2)
                        except Exception as e:
                            print(f"   {sp['sp']} 季後賽失敗：{str(e)[:80]}")
                    segs.append({"sp": sp["sp"], "teams": teams, "from": frm, "to": to, "po": po,
                                 "page": sp["page"]})
                    allt += teams
                    if frm and (not frm0 or frm < frm0):
                        frm0 = frm
                    if to > to0:
                        to0 = to
                    print(f"   {sp['sp']}：{len(teams)} 隊 {frm}~{to}" + (f"　季後賽 {len(po)} 隊" if po else ""))
                    time.sleep(2)
                if not segs:
                    print("   全部失敗，保留舊資料"); continue
                seen, uniq = set(), []
                for t in allt:
                    if t not in seen:
                        seen.add(t); uniq.append(t)
                data[str(year)][code] = {"teams": uniq, "rosters": {}, "splits": segs,
                                         "from": frm0, "to": to0, "page": cfg["splits"][0]["page"],
                                         "url": "https://lol.fandom.com/wiki/" + urllib.parse.quote(cfg["splits"][0]["page"].replace(" ", "_"))}
                continue
            print(f"[{year}] {code} ← {cfg['page']}")
            try:
                teams, rosters, frm, to, brk = grab(cfg["page"], kind)
            except Exception as e:
                print("   失敗，保留舊資料：", str(e)[:120]); continue
            data[str(year)][code] = {"teams": teams, "rosters": rosters, "from": frm, "to": to,
                                     "po": (brk if 0 < len(brk) < len(teams) else []), "page": cfg["page"],
                                     "url": "https://lol.fandom.com/wiki/" + urllib.parse.quote(cfg["page"].replace(" ", "_"))}
            print(f"   {len(teams)} 隊　{len(rosters)} 份名單　{frm} ~ {to}" + (f"　季後賽 {len(brk)} 隊" if 0 < len(brk) < len(teams) else ("　（純淘汰賽，不標晉級）" if brk else "")))
            if rosters:
                k = list(rosters)[0]
                print(f"    例：{k} → " + "、".join(f"{p['n']}({p['r'] or '?'})" for p in rosters[k][:6]))
            if teams:
                print("   ", "、".join(teams[:8]) + ("…" if len(teams) > 8 else ""))
            time.sleep(2)
    open(OUT, "w", encoding="utf-8").write("window.EVENTS_EXTRA=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";")
    print("→ events_extra.js")


if __name__ == "__main__":
    main()
