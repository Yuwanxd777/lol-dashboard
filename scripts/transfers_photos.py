# -*- coding: utf-8 -*-
"""轉會分頁「隊伍小框」要的兩份資料（使用者 2026-11-22「左半邊點擊後要顯示 2026 先發五人(場次最多的)以及教練的WIKI圖片 這個放在上方 下方是2027的」）。

  s26   {隊名（陣容表的 nm）: {TOP/JNG/MID/BOT/SUP: [顯示 ID, wiki 頁名]}}
        ＝那一年替這隊出賽最多場的人（Leaguepedia ScoreboardPlayers，所有賽事；同場數取頁名字母序，結果才固定）
  pimg  {wiki 頁名: 縮圖網址}  ＝ Players.Image（個人頁那張圖）；沒有就退回 PlayerImages 最新一張。只存有圖的人

由 fetch_transfers.py 在陣容表建好之後呼叫 build()。查過的結果存在 csv_cache/transfers_photos.json：
  ・先發是整年的統計，賽季打完就不會變 ⇒ 每支隊伍查到一次就不再查（隊名換了才補查）
  ・圖片每個人查一次；查不到的隔一天再試（新簽的人頁面常常晚幾天才有圖）
前端只讀 transfers.js 的 s26／pimg，沒有就只顯示名字——這支失敗不影響其他資料。
"""
import datetime
import io
import json
import os
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, "csv_cache", "transfers_photos.json")
API = "https://lol.fandom.com/api.php"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}
ROLE = {"top": "TOP", "jungle": "JNG", "mid": "MID", "bot": "BOT", "support": "SUP"}
PX = 220   # 縮圖寬（畫面上最大 112px，2 倍螢幕夠用）


def _in(names):
    return "(" + ",".join('"' + str(n).replace("\\", "\\\\").replace('"', '\\"') + '"' for n in names) + ")"


def _disp(page):
    """頁名 → 顯示 ID（去掉尾巴的消歧義括號：Doran (Choi Hyeon-jun) → Doran）"""
    s = str(page or "")
    i = s.rfind(" (")
    return s[:i] if i > 0 and s.endswith(")") else s


def starters(cargo, year, teams):
    """teams＝wiki 隊名清單 → {wiki 隊名: {路線: [顯示 ID, 頁名]}}"""
    out = {}
    for i in range(0, len(teams), 10):
        rows = cargo({"tables": "ScoreboardPlayers=SP", "fields": "SP.Team=tm,SP.Link=p,SP.Role=r,COUNT(*)=n", "group_by": "SP.Team,SP.Link,SP.Role",
                      "where": "SP.Team IN " + _in(teams[i:i + 10]) + f' AND SP.DateTime_UTC>="{year}-01-01" AND SP.DateTime_UTC<"{int(year) + 1}-01-01"',
                      "limit": "5000", "format": "json"})
        best = {}
        for x in rows:
            rr = ROLE.get(str(x.get("r") or "").strip().lower())
            if not rr or not x.get("p") or not x.get("tm"):
                continue
            k = (x["tm"], rr)
            cand = (int(x.get("n") or 0), x["p"])
            if k not in best or cand[0] > best[k][0] or (cand[0] == best[k][0] and cand[1] < best[k][1]):
                best[k] = cand
        for (tm, rr), (_n, pg) in best.items():
            out.setdefault(tm, {})[rr] = [_disp(pg), pg]
    return out


def _api(params):
    params = dict(params, format="json")
    for k in range(3):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(API + "?" + urllib.parse.urlencode(params), headers=UA), timeout=60).read())
        except Exception as e:
            print(f"   圖片 API 失敗（{k + 1}/3）：{str(e)[:80]}")
            time.sleep(6 * (k + 1))
    return {}


def _thumbs(files):
    """檔名清單 → {檔名: 縮圖網址}（一次 50 個）"""
    out = {}
    for i in range(0, len(files), 50):
        chunk = files[i:i + 50]
        r = _api({"action": "query", "titles": "|".join("File:" + f for f in chunk), "prop": "imageinfo", "iiprop": "url", "iiurlwidth": PX, "redirects": 1})
        q = r.get("query") or {}
        back = {}
        for x in (q.get("normalized") or []) + (q.get("redirects") or []):
            back[x["to"]] = back.get(x["from"], x["from"])
        for pg in (q.get("pages") or {}).values():
            ii = (pg.get("imageinfo") or [None])[0]
            if not ii:
                continue
            src = pg["title"]
            while src in back:
                src = back[src]
            out[src.replace("File:", "", 1).replace("_", " ")] = ii.get("thumburl") or ii.get("url") or ""
        time.sleep(1.2)
    return out


def images(cargo, pages, teams=()):
    """頁名清單 → {頁名: 縮圖網址（沒有圖＝空字串）}。teams＝目前追蹤的隊名（同 ID 好幾個人時用來挑對的那位）
    Cargo 回來的頁名大小寫可能跟我們手上的不同（deokdam／Deokdam），純數字的 ID（369、1874）還會變成數字 ⇒ 一律轉字串、不分大小寫對回去"""
    key = {str(p).lower(): p for p in pages}
    files = {}

    def put(p, f, as_=None):
        k = as_ or key.get(str(p).lower())
        if k and f and k not in files:
            files[k] = str(f)

    def by_pages(names, as_map=None):   # Players.Image → 沒有就 PlayerImages 最新一張；as_map＝{查詢用的頁名（小寫）: 我們手上的頁名}
        m = as_map or {}
        for i in range(0, len(names), 40):
            for x in cargo({"tables": "Players=P", "fields": "P.OverviewPage=p,P.Image=img", "where": "P.OverviewPage IN " + _in(names[i:i + 40]), "limit": "500", "format": "json"}):
                put(x.get("p"), x.get("img"), m.get(str(x.get("p")).lower()))
        rest = [n for n in names if (m.get(str(n).lower()) or key.get(str(n).lower())) not in files]
        for i in range(0, len(rest), 10):
            for x in cargo({"tables": "PlayerImages=PI", "fields": "PI.Link=p,PI.FileName=f,PI.SortDate=d", "where": "PI.Link IN " + _in(rest[i:i + 10]),
                            "order_by": "PI.SortDate DESC", "limit": "500", "format": "json"}):
                put(x.get("p"), x.get("f"), m.get(str(x.get("p")).lower()))

    by_pages(list(pages))
    miss = [p for p in pages if p not in files]
    if miss:   # 頁名對不上的：先查轉址（Thanatos (Park Seung-kyu) → (Park Seung-gyu)），再用 ID 找（Ming → Ming (Shi Sen-Ming)；同 ID 多人時挑在追蹤隊伍裡的那位）
        ali = {}
        for i in range(0, len(miss), 40):
            for x in cargo({"tables": "PlayerRedirects=R", "fields": "R.AllName=a,R.OverviewPage=p", "where": "R.AllName IN " + _in(miss[i:i + 40]), "limit": "500", "format": "json"}):
                k = key.get(str(x.get("a")).lower())
                if k and x.get("p") and str(x["p"]).lower() != str(k).lower():
                    ali[str(x["p"]).lower()] = k
        ids = [p for p in miss if p not in ali.values() and "(" not in p]
        tset = {str(t).lower() for t in teams}
        for i in range(0, len(ids), 40):
            cand = {}
            for x in cargo({"tables": "Players=P", "fields": "P.OverviewPage=p,P.ID=id,P.Team=tm,P.IsRetired=ret", "where": "P.ID IN " + _in(ids[i:i + 40]), "limit": "500", "format": "json"}):
                k = key.get(str(x.get("id")).lower())
                if k and x.get("p") and str(x["p"]).lower() != str(k).lower():
                    cand.setdefault(k, []).append(x)
            for k, L in cand.items():
                L.sort(key=lambda x: (str(x.get("tm") or "").lower() not in tset, str(x.get("ret") or "") in ("1", "Yes", "true")))
                act = [x for x in L if str(x.get("ret") or "") not in ("1", "Yes", "true")]
                if len(L) == 1 or str(L[0].get("tm") or "").lower() in tset or len(act) == 1:
                    ali[str((L[0] if (len(L) == 1 or str(L[0].get("tm") or "").lower() in tset) else act[0])["p"]).lower()] = k
        if ali:
            real = {}
            for i in range(0, len(ali), 40):   # 用查到的真正頁名再查一次圖（轉址／同 ID 查到的頁名大小寫以 Players 為準）
                for x in cargo({"tables": "Players=P", "fields": "P.OverviewPage=p", "where": "P.OverviewPage IN " + _in(list(ali)[i:i + 40]), "limit": "500", "format": "json"}):
                    real[str(x.get("p")).lower()] = str(x.get("p"))
            by_pages([real.get(a, a) for a in ali], ali)
    th = _thumbs(sorted({f.replace("_", " ") for f in files.values()}))
    return {p: th.get(str(files.get(p, "")).replace("_", " "), "") for p in pages}


def _load():
    try:
        return json.load(io.open(CACHE, encoding="utf-8"))
    except Exception:
        return {}


def build(cargo, year, board, roles=None, alias=None):
    """回傳 (s26, pimg)。board＝transfers_board.build 的結果；roles＝{名字: [路線, 頁名, wikiID]}（傳聞人選補頁名用）；
    alias＝{現在的隊名: 那一年打比賽時的隊名}（OpTic Gaming 2026 年叫 Dignitas）"""
    roles = roles or {}
    alias = alias or {}
    C = _load()
    today = datetime.date.today().isoformat()
    teams = [(t.get("nm") or t.get("tm"), t.get("tm") or t.get("nm")) for t in board if not t.get("fa") and (t.get("tm") or t.get("nm"))]
    # ① 先發
    S = C.setdefault("s26", {}).setdefault(str(year), {})
    need = sorted({tm for _nm, tm in teams if tm not in S})
    if need:
        got = starters(cargo, year, sorted({alias.get(tm, tm) for tm in need}))
        for tm in need:
            if got.get(alias.get(tm, tm)):
                S[tm] = got[alias.get(tm, tm)]
        print(f"   隊伍小框：{year} 先發補查 {len(need)} 隊，查到 {sum(1 for tm in need if tm in S)} 隊")
    s26 = {nm: S[tm] for nm, tm in teams if S.get(tm)}
    # ② 圖片：先發五人＋每隊格子裡的五路選手與主教練＋上一任主教練
    def page_of(e):
        n = e.get("n") or ""
        return str(e.get("p") or (roles.get(n) or [None, None])[1] or n).replace("_", " ")

    pages = {v[1] for d in s26.values() for v in d.values()}
    for t in board:
        if t.get("fa"):
            continue
        for rr, L in (t.get("r") or {}).items():
            for e in L:
                if rr != "COACH" or e.get("sr") == "HC":
                    pages.add(page_of(e))
        for e in ((t.get("prev") or {}).get("COACH") or []):
            if e.get("sr") == "HC":
                pages.add(page_of(e))
    pages.discard("")
    I = C.setdefault("img", {})
    need = sorted(p for p in pages if p not in I or (not I[p].get("u") and I[p].get("t", "") < today))
    if need:
        got = images(cargo, need, [tm for _nm, tm in teams])
        for p in need:
            I[p] = {"u": got.get(p, ""), "t": today}
        print(f"   隊伍小框：圖片補查 {len(need)} 人，有圖 {sum(1 for p in need if got.get(p))} 人")
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    io.open(CACHE, "w", encoding="utf-8").write(json.dumps(C, ensure_ascii=False, separators=(",", ":")))
    pimg = {p: I[p]["u"] for p in sorted(pages) if I.get(p, {}).get("u")}
    return s26, pimg
