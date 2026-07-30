# -*- coding: utf-8 -*-
"""BP（禁用／選用）補洞：OE 有這局、但 banlist/picklist 是空的 → 從 gol.gg 補回來。

背景（2026-07-31 使用者回報）：07-28 KeSPA BRO 1-2 DNS 三局的 BP 全空，但同一天別場都有
→ 不是整段缺（那是 fetch_fill.py 的守備範圍），而是**個別局的欄位缺**。

與 fetch_fill.py 的分工：
  fetch_fill.py  → OE **整段沒有** 的比賽（補整局，OE 一有就停用）
  本檔           → OE **有這局但欄位空**（只補空欄位，OE 之後補上就自然不再套用）

輸出 csv_cache/patch_{年}.json：{ 局鍵: {欄位: 值} }；由 fetch_data.py 併入時**只填空欄位**，
OE 已有值的一律不動（同「以 OE 為準」的鐵則）。

用法：
  python scripts\fetch_bp_fill.py            # 掃今年，缺 BP 的局去 gol.gg 補
  python scripts\fetch_bp_fill.py 2025       # 指定年份
  python scripts\fetch_bp_fill.py --status   # 只列出缺 BP 的局，不抓
"""
import importlib.util, io, json, os, re, sys, urllib.parse, urllib.request
from collections import defaultdict

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(HERE, "csv_cache")
if not os.path.isdir(CACHE) and os.path.isdir(os.path.join(ROOT, "csv_cache")):
    CACHE = os.path.join(ROOT, "csv_cache")

# fetch_fill 的 gol.gg 解析器直接沿用（matchlist / 單局頁 / 英雄名對齊）
_spec = importlib.util.spec_from_file_location("_ff", os.path.join(HERE, "fetch_fill.py"))
_ff = importlib.util.module_from_spec(_spec)
_argv = sys.argv[:]
sys.argv = ["fetch_fill.py", "--status"]
try:
    _spec.loader.exec_module(_ff)
except SystemExit:
    pass
sys.argv = _argv

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
_nk = lambda s2: re.sub(r"[^0-9a-z]", "", str(s2 or "").lower())
_CHMAP = {}


def champ_of(fname, year, league):
    """gol.gg 圖檔名 → OE 英雄名（Kaisa→Kai'Sa、JarvanIV→Jarvan IV…）；void＝空 BAN"""
    if not fname or str(fname).lower() == "void":
        return ""
    k = (year, league)
    if k not in _CHMAP:
        _CHMAP[k] = _ff.oe_names(year, league)[2]
    v = _CHMAP[k].get(_nk(fname))
    return v or re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(fname))

# 聯賽 → gol.gg 賽事名候選（%s＝年份）。找不到就逐一試，命中即記住。
TOUR_CANDS = {
    "KeSPA": ["KeSPA Cup %s"],
    "LCK": ["LCK %s Rounds 3-4", "LCK %s Rounds 1-2", "LCK Cup %s", "LCK %s Summer", "LCK %s Spring"],
    "LPL": ["LPL %s Split 3", "LPL %s Split 2", "LPL %s Split 1", "LPL %s Summer", "LPL %s Spring"],
    "LEC": ["LEC %s Summer", "LEC %s Spring", "LEC %s Winter"],
    "LCS": ["LCS %s Summer", "LCS %s Spring"],
    "LTA N": ["LTA North %s Split 3", "LTA North %s Split 2", "LTA North %s Split 1"],
    "LTA S": ["LTA South %s Split 3", "LTA South %s Split 2", "LTA South %s Split 1"],
    "LCP": ["LCP %s Season 3", "LCP %s Season 2", "LCP %s Season 1"],
    "MSI": ["MSI %s"], "WLDs": ["World Championship %s", "Worlds %s"], "EWC": ["EWC %s", "Esports World Cup %s"],
}


def gget(url):
    try:
        return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read().decode("utf-8", "replace")
    except Exception as e:
        print(f"      下載失敗 {type(e).__name__}: {str(e)[:70]}")
        return ""


_ML_CACHE = {}


def matchlist(tour):
    if tour in _ML_CACHE:
        return _ML_CACHE[tour]
    h = gget(f"https://gol.gg/tournament/tournament-matchlist/{urllib.parse.quote(tour)}/")
    ms = _ff.parse_matchlist(h) if h else []
    _ML_CACHE[tour] = ms
    return ms


def load_year(y):
    p = os.path.join(ROOT, "data", f"data_{y}.js")
    with open(p, encoding="utf-8") as f:
        return json.loads(f.read().split("=", 1)[1].strip().rstrip(";"))["tabs"]["RAW_DATA"]


def empty(v):
    return str(v or "").strip(" |") == ""


def main():
    args = sys.argv[1:]
    yrs = [int(a) for a in args if a.isdigit()] or [max(
        int(f[5:9]) for f in os.listdir(os.path.join(ROOT, "data")) if f.startswith("data_") and f[5:9].isdigit())]
    status = "--status" in args
    for year in yrs:
        R = load_year(year); h = R[0]; ix = {n: i for i, n in enumerate(h)}
        need = [r for r in R[1:] if str(r[ix["participantid"]]) == "100"
                and empty(r[ix["banlist"]]) and empty(r[ix["picklist"]])]
        print(f"[{year}] 缺 BP 的局：{len(need)}")
        if not need:
            continue
        by = defaultdict(list)
        for r in need:
            by[(str(r[ix['league']]), str(r[ix['date']])[:10])].append(r)
        for (lg, d), rows in sorted(by.items()):
            tms = {frozenset((str(r[ix['blue_teamname']]), str(r[ix['red_teamname']]))) for r in rows}
            print(f"   {d} {lg}：{len(rows)} 局　{[ ' vs '.join(sorted(t)) for t in tms ]}")
        if status:
            continue
        patch, hit, miss = {}, 0, []
        for (lg, d), rows in sorted(by.items()):
            cands = TOUR_CANDS.get(lg, [lg + " %s"])
            series = None
            for c in cands:
                ms = [m for m in matchlist(c % year) if m.get("date") == d and m.get("done")]
                if ms:
                    series = (c % year, ms); break
            if not series:
                miss.append(f"{d} {lg}（gol.gg 找不到賽事：試過 {[c % year for c in cands]}）"); continue
            tour, ms = series
            # 該日的所有局 → 以「兩隊」對上 OE 的局
            games = {}
            for mt in ms:
                gd0 = _ff.parse_game(gget(f"https://gol.gg/game/stats/{mt['gid']}/page-game/"))
                ids = sorted(i for i in gd0["ids"] if i >= mt["gid"]) or [mt["gid"]]
                for gi, gid in enumerate(ids):
                    gd = gd0 if gid == mt["gid"] else _ff.parse_game(gget(f"https://gol.gg/game/stats/{gid}/page-game/"))
                    if not gd.get("sides"):
                        continue
                    key = frozenset(v["team"] for v in gd["sides"].values())
                    games.setdefault(key, []).append(gd)
            for r in rows:
                bt, rt = str(r[ix["blue_teamname"]]), str(r[ix["red_teamname"]])
                cand = None
                for key, lst in games.items():
                    if len(key & {bt, rt}) >= 1 or _same(key, {bt, rt}):
                        cand = lst; break
                if not cand:
                    miss.append(f"{d} {lg} {bt} vs {rt} 局{r[ix['game']]}（gol.gg 對不到隊名）"); continue
                gi = int(str(r[ix["game"]]) or 1) - 1
                if gi >= len(cand):
                    miss.append(f"{d} {lg} {bt} vs {rt} 局{r[ix['game']]}（gol.gg 局數不足 {len(cand)}）"); continue
                gd = cand[gi]
                # gol.gg 的藍/紅要對回 OE 的藍/紅（隊名比對）
                side_of = {}
                for s, v in gd["sides"].items():
                    side_of["blue" if _eq(v["team"], bt) else "red"] = s
                if len(side_of) < 2:
                    miss.append(f"{d} {lg} {bt} vs {rt} 局{r[ix['game']]}（藍紅對不上）"); continue
                out = {}
                _sb = {}
                for oe_side, g_side in side_of.items():
                    bans = [champ_of(c, year, lg) for c in (gd["bp"].get(g_side, {}).get("bans") or [])[:5]]
                    picks = [champ_of(c, year, lg) for c in (gd["bp"].get(g_side, {}).get("picks") or [])[:5]]
                    while bans and not bans[-1]:
                        bans.pop()                      # 尾端空 BAN 不留（中間的保留＝位置正確）
                    _sb[oe_side] = (bans, picks)
                    out[f"{oe_side}_banlist"] = "|" + "|".join(bans) + "|"
                if _sb:
                    out["banlist"] = "|" + "|".join([c for s3 in ("blue", "red") for c in _sb.get(s3, ([], []))[0] if c]) + "|"
                    out["picklist"] = "|" + "|".join([c for s3 in ("blue", "red") for c in _sb.get(s3, ([], []))[1] if c]) + "|"
                if not out:
                    miss.append(f"{d} {lg} {bt} vs {rt} 局{r[ix['game']]}（gol.gg 也沒有 BP）"); continue
                gk = "|".join([str(r[ix["league"]]), str(r[ix["date"]])[:10], bt, rt, str(r[ix["game"]])])
                patch[gk] = out; hit += 1
                print(f"      ✓ {d} {bt} vs {rt} 局{r[ix['game']]}：ban {len(bans)}／pick {len(picks)}")
        if patch:
            p = os.path.join(CACHE, f"patch_{year}.json")
            old = {}
            if os.path.exists(p):
                try:
                    old = json.load(open(p, encoding="utf-8"))
                except Exception:
                    old = {}
            old.update(patch)
            os.makedirs(CACHE, exist_ok=True)
            json.dump(old, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
            print(f"  → {p}（本次 {hit} 局，累計 {len(old)} 局）")
        if miss:
            print("  ⚠ 補不到：")
            for m in miss:
                print("     ", m)


def _eq(a, b):
    n = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())
    return n(a) == n(b) or (n(a) and n(b) and (n(a) in n(b) or n(b) in n(a)))


def _same(k1, k2):
    return all(any(_eq(a, b) for b in k2) for a in k1)


if __name__ == "__main__":
    main()
