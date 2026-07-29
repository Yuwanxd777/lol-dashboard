# -*- coding: utf-8 -*-
"""LPL 常規賽分組 → lpl_groups.js
成員：由主資料 data/data_{年}.js 常規賽(split=S1/S2/S3，排除 PO 季後賽)的「同組互打」連通分量還原（可靠、不需 Wiki）。
組名：從 Leaguepedia wikitext(action=parse，非 Cargo/非 index.php raw，較不被 Cloudflare 擋)的 AutoStandings 模板抓
      display=Group X + finalorder=<縮寫>，再以隊伍重疊比對到各分群；抓不到名字的分群退回「Group 1/2…」。
輸出 window.LPL_GROUPS={年:{split:{組名:[隊縮寫...]}}}（隊縮寫＝儀表板 tAb 慣例，season split 大小排序）。
用法：python scripts/fetch_lpl_groups.py
"""
import os, re, json, time, urllib.request, urllib.parse
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "lpl_groups.js")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
YEARS = [2025, 2026]
SPLITS = ["S1", "S2", "S3"]

# 隊全名 → 儀表板縮寫（與 index.html tAb/teamFix 一致；LPL 用得到的隊）
AB = {"Anyone's Legend": "AL", "Bilibili Gaming": "BLG", "Invictus Gaming": "IG", "JD Gaming": "JDG",
      "Top Esports": "TES", "Weibo Gaming": "WBG", "LGD Gaming": "LGD", "LNG Esports": "LNG",
      "Oh My God": "OMG", "Ultra Prime": "UP", "EDward Gaming": "EDG", "Ninjas in Pyjamas": "NIP",
      "Team WE": "WE", "ThunderTalk Gaming": "TT", "FunPlus Phoenix": "FPX", "Royal Never Give Up": "RNG",
      "Ninjas in Pyjamas.CN": "NIP"}   # wiki 對 NIP 的中國隊寫法
def ab(t): return AB.get(t, t)


def load(year):
    p = os.path.join(ROOT, "data", f"data_{year}.js")
    if not os.path.exists(p): return None
    d = json.loads(re.match(r'window\.LOL_DATA=(.*?);?\s*$', open(p, encoding="utf-8", errors="replace").read(), re.S).group(1))
    raw = d["tabs"]["RAW_DATA"]; h = raw[0]
    return raw, h.index("league"), h.index("split"), h.index("blue_teamname"), h.index("red_teamname")


def clusters(raw, li, si, bt, rt, split):
    """常規賽同組互打的連通分量＝各組成員"""
    edges = defaultdict(set); teams = set()
    for r in raw[1:]:
        if r[li] != "LPL" or str(r[si]) != split: continue
        a, b = r[bt], r[rt]
        if not a or not b or a == b: continue
        teams |= {a, b}; edges[a].add(b); edges[b].add(a)
    comp = {}
    for t in teams:
        if t in comp: continue
        stack = [t]
        while stack:
            x = stack.pop()
            if x in comp: continue
            comp[x] = t
            for y in edges[x]:
                if y not in comp: stack.append(y)
    g = defaultdict(list)
    for t, c in comp.items(): g[c].append(t)
    gl = [sorted((ab(t) for t in ts)) for ts in g.values()]
    gl.sort(key=lambda ts: (-len(ts), ts[0]))
    return gl


def wiki_groups(overview):
    """從 wikitext 的 AutoStandings 抓 [(組名, [隊縮寫...])]（finalorder 可能缺）"""
    url = "https://lol.fandom.com/api.php?" + urllib.parse.urlencode(
        {"action": "parse", "page": overview, "prop": "wikitext", "format": "json", "formatversion": "2"})
    wt = None
    for a in range(6):
        try:
            r = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45).read())
            if "error" in r: return []
            wt = r["parse"]["wikitext"]; break
        except Exception as e:
            print(f"    {overview} 重試 {a+1}：{e}", flush=True); time.sleep(15 * (a + 1))
    if not wt: return []
    out = []
    for blk in re.findall(r'\{\{AutoStandings[^}]*\}\}', wt, re.S):
        dn = re.search(r'display=\s*([^|\n}]+)', blk)
        og = re.search(r'onlygroup=\s*([^|\n}]+)', blk)
        name = (dn.group(1) if dn else (og.group(1) if og else "")).strip()
        fo = re.search(r'finalorder=\s*([^|\n}]+)', blk)
        teams = []
        if fo:
            for tok in fo.group(1).split(","):
                s = tok.strip().split(" ")[0].strip()  # "AL CN" → "AL"
                if s: teams.append(s)
        if name: out.append((name, teams))
    return out


def html_groups(overview):
    """賽段還沒開賽（主資料無場次）時的 fallback：抓渲染後 HTML 的 Participants，
    每個「Group X」headline 底下的 tournament-roster 表＝該組成員（2026 S3 開賽前更新分組用）"""
    import html as _html
    url = "https://lol.fandom.com/api.php?" + urllib.parse.urlencode(
        {"action": "parse", "page": overview, "prop": "text", "format": "json"})
    h = None
    for a in range(4):
        try:
            r = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
            if "error" in r: return []
            h = r["parse"]["text"]["*"]; break
        except Exception as e:
            print(f"    {overview} HTML 重試 {a+1}：{e}", flush=True); time.sleep(12 * (a + 1))
    if not h: return []
    out = []
    for m in re.finditer(r'<span class="mw-headline" id="(Group_[^"]+)"', h):
        gname = m.group(1).replace("Group_", "").replace("_", " ")
        seg = h[m.end():]
        nxt = re.search(r'<span class="mw-headline"', seg)   # 下一個任何 headline（含下一個 Group_）就停，否則 Ascend 會吃到 Nirvana 的表
        if nxt: seg = seg[:nxt.start()]
        teams = []
        for t in re.findall(r'<table[^>]*class="[^"]*tournament-roster[^"]*"[^>]*>.*?</table>', seg, re.S):
            mt = re.search(r'class="[^"]*catlink-teams[^"]*"[^>]*title="([^"]+)"', t)
            if mt: teams.append(ab(_html.unescape(mt.group(1)).strip()))
        if teams: out.append((gname, sorted(set(teams))))
    return out


def match(cl, wg):
    """把 wiki 組名配到各分群（依 finalorder 隊伍重疊）；配不到的分群給 Group N"""
    names = [None] * len(cl)
    used = set()
    # 先用 finalorder 有隊的組去精確配
    for gname, gteams in wg:
        if not gteams: continue
        best, bi = -1, -1
        for i, c in enumerate(cl):
            if i in used: continue
            ov = len(set(gteams) & set(c))
            if ov > best: best, bi = ov, i
        if bi >= 0 and best > 0:
            names[bi] = gname.replace("Group ", "").strip(); used.add(bi)
    # 剩下沒配到的分群，用還沒用到的 wiki 組名（依 wiki 順序）補
    leftover = [n.replace("Group ", "").strip() for n, _ in wg if n.replace("Group ", "").strip() not in [x for x in names if x]]
    li = 0
    for i in range(len(cl)):
        if names[i] is None:
            names[i] = leftover[li] if li < len(leftover) else f"Group {i+1}"; li += 1
    return names


def main():
    data = {}
    for y in YEARS:
        L = load(y)
        if not L: continue
        raw, li, si, bt, rt = L
        for sp in SPLITS:
            cl = clusters(raw, li, si, bt, rt, sp)
            n = int(sp[1:])
            overview = f"LPL/{y} Season/Split {n}"
            if len(cl) <= 1:
                # 主資料還沒有這個賽段的場次（開賽前）→ 直接用 wiki Participants 的分組（2026-07-28 使用者需求）
                hg = html_groups(overview)
                if len(hg) >= 2:
                    data.setdefault(str(y), {})[sp] = {gn: ts for gn, ts in hg}
                    print(f"{y} {sp}: 開賽前，分組取自 wiki → " + ", ".join(f"{gn}({len(ts)})" for gn, ts in hg), flush=True)
                    time.sleep(8)
                continue  # 單一循環或 wiki 也沒有＝無分組
            print(f"{y} {sp}: {len(cl)} 組，抓組名 {overview} …", flush=True)
            wg = wiki_groups(overview)
            # 賽段剛開賽（組內還沒互打滿）時連通分量會把同一組拆成好幾塊 → 官方組數為準，改用 Participants 名單。
            # 2026-07-28 真實案例：補進 LPL S3 第一週資料後，Nirvana 4 隊只打過 IG-WBG、LNG-NIP
            # → 連通分量得出 3 組（多一個假的「Group 3」）。場次補齊後組數會相等，自動回到連通分量。
            if wg and len(cl) > len(wg):
                hg = html_groups(overview)
                if len(hg) >= 2:
                    data.setdefault(str(y), {})[sp] = {gn: ts for gn, ts in hg}
                    print(f"   場次不足（連通分量 {len(cl)} 組 > 官方 {len(wg)} 組）→ 改用 wiki Participants："
                          + ", ".join(f"{gn}({len(ts)})" for gn, ts in hg), flush=True)
                    time.sleep(8)
                    continue
            names = match(cl, wg)
            data.setdefault(str(y), {})[sp] = {names[i]: cl[i] for i in range(len(cl))}
            print(f"   → {', '.join(f'{names[i]}({len(cl[i])})' for i in range(len(cl)))}", flush=True)
            time.sleep(10)  # 溫和間隔避免 Cloudflare
    open(OUT, "w", encoding="utf-8").write("window.LPL_GROUPS=" + json.dumps(data, ensure_ascii=False) + ";\n")
    print("寫出", OUT, flush=True)


if __name__ == "__main__":
    main()
