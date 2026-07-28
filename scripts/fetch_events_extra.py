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
import io, sys, os, re, json, time, urllib.request, urllib.parse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "events_extra.js")
API = "https://lol.fandom.com/api.php"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}

# kind: "team"＝一般戰隊（取 team-template 全名）／"nation"＝國家隊（取 X (National Team)）
EVENTS = {
    2026: {
        "EWCQ中國": {"page": "Esports World Cup 2026/Online Qualifiers/China", "kind": "team"},
        "ENC":      {"page": "Esports Nations Cup 2026",                       "kind": "nation"},
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
        # 兩種模板都要試（頁面新舊版型不同）：team-template-text ／ span.teamname
        names = re.findall(r'class="[^"]*team-template-text[^"]*"[^>]*>\s*<a[^>]*title="([^"]+)"', html)
        names += re.findall(r'<span class="teamname"[^>]*>\s*<a[^>]*>([^<]+)</a>', html)
        # 同一隊會同時列全名與縮寫（EDward Gaming／EDG）→ 只留全名
        names = [n for n in names if len(n) > 4 and not n.isupper()]
    seen, out = set(), []
    for n in names:
        n = n.strip()
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
        team = mt.group(1).strip()
        players, seen = [], set()
        # 每個選手格：<span title="Jungler" …> 之後跟著 catlink-players（順序穩定）
        for m in re.finditer(r'<span[^>]*title="([^"]*)"[^>]*class="[^"]*sprite[^"]*"[^>]*>|class="[^"]*catlink-players[^"]*"[^>]*>([^<]+)</a>', t):
            if m.group(2):
                nm = m.group(2).strip()
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
            print(f"[{year}] {code} ← {cfg['page']}")
            try:
                html = parse_page(cfg["page"])
            except Exception as e:
                print("   失敗，保留舊資料：", str(e)[:120]); continue
            teams = teams_of(html, cfg["kind"])
            rosters = rosters_of(html)
            frm, to = dates_of(html)
            data[str(year)][code] = {"teams": teams, "rosters": rosters, "from": frm, "to": to,
                                     "page": cfg["page"],
                                     "url": "https://lol.fandom.com/wiki/" + urllib.parse.quote(cfg["page"].replace(" ", "_"))}
            print(f"   {len(teams)} 隊　{len(rosters)} 份名單　{frm} ~ {to}")
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
