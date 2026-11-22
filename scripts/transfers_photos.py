# -*- coding: utf-8 -*-
"""轉會分頁「隊伍小框」與「效力」要的資料（使用者 2026-11-22）。

  s26   {隊名（陣容表的 nm）: {TOP/JNG/MID/BOT/SUP/HC: [顯示 ID, wiki 頁名]}}
        HC＝那一年當主教練（含代理主教練）天數最多的人，直接查 wiki 的 Tenures＋RosterChanges（使用者 2026-11-22「如果不知道2026原教練是誰 就去翻WIKI」）
        ＝那一年替這隊出賽最多場的人（Leaguepedia ScoreboardPlayers，所有賽事；同場數取頁名字母序，結果才固定）
  pimg  {wiki 頁名: 縮圖網址}
        選圖順序（使用者「選手的照片記得抓取的是2026最新一張 如果2026沒有才往前抓」）：
        PlayerImages 裡該年最新一張 → 沒有就該年以前最新的一張 → 個人頁那張（Players.Image）→ 其餘任何一張。只存有圖的人
  pfc   {wiki 頁名: [兩眼中點 x÷圖寬, 兩眼中點 y÷圖高, 臉寬÷圖寬, 圖寬÷圖高, 兩眼連線的角度（度，正＝畫面右邊那隻眼睛比較低）, 1＝去背照]}
        （使用者「圖片的人頭大小與位置幫我調整一致」）OpenCV 的 YuNet 臉部偵測（模型檔 csv_cache/face_detection_yunet_2023mar.onnx，
        使用者同意下載）量出來的；前端照這四個數把每張圖縮放、移動到「臉一樣寬、眼睛在同一個位置」。量不到的人前端退回一般的置中裁切
  效力  tenures()：每隊每個人的歷次效力區間（Tenures 表，含已經結束的），fetch_transfers 掛到格子裡的人身上（欄位 tn）

由 fetch_transfers.py 在陣容表建好之後呼叫。查過的結果存在 csv_cache/transfers_photos.json：
  ・先發是整年的統計，賽季打完就不會變 ⇒ 每支隊伍查到一次就不再查
  ・圖片：選到該年照片的人不再查；選到舊照片的 7 天後重查一次；完全沒圖的隔天重查
  ・效力區間一天查一次
前端只讀 transfers.js，沒有這些欄位就只顯示名字——這支失敗不影響其他資料。
"""
import datetime
import io
import json
import os
import re
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, "csv_cache", "transfers_photos.json")
MODEL = os.path.join(ROOT, "csv_cache", "face_detection_yunet_2023mar.onnx")
API = "https://lol.fandom.com/api.php"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}
ROLE = {"top": "TOP", "jungle": "JNG", "mid": "MID", "bot": "BOT", "support": "SUP"}
PX = 220   # 縮圖寬（畫面上最大 112px，臉放大後 2 倍螢幕也夠用）
VER = 2    # 快取版本：選圖規則改了就加一，舊的圖片紀錄整批重查


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
            cand = (int(x.get("n") or 0), str(x["p"]))
            if k not in best or cand[0] > best[k][0] or (cand[0] == best[k][0] and cand[1] < best[k][1]):
                best[k] = cand
        for (tm, rr), (_n, pg) in best.items():
            out.setdefault(tm, {})[rr] = [_disp(pg), pg]
    return out


def coaches(cargo, year, teams):
    """teams＝wiki 隊名清單 → {wiki 隊名: [顯示 ID, 頁名]}：那一年當主教練（Head Coach／Interim Head Coach；助理主教練不算）天數最多的人。
    wiki 上整年都沒登記主教練的隊（OMG、Saigon Warriors 只有職稱「Coach」的人）⇒ 改取職稱剛好是 Coach、待最久的那位"""
    y0, y1 = f"{int(year)}-01-01", f"{int(year)}-12-31"
    today = datetime.date.today().isoformat()
    days = {}
    for i in range(0, len(teams), 15):
        for x in cargo({"tables": "Tenures=T,RosterChanges=RC", "join_on": "T.RosterChangeIdJoin=RC.RosterChangeId",
                        "fields": "T.Player=p,T.Team=tm,T.DateJoin=dj,T.DateLeave=dl,RC.Role=ro",
                        "where": "T.Team IN " + _in(teams[i:i + 15]) + f' AND RC.Role LIKE "%Coach%" AND (T.DateLeave>="{y0}" OR T.IsCurrent=1) AND T.DateJoin<="{y1}"',
                        "limit": "5000", "format": "json"}):
            ro = str(x.get("ro") or "").strip().lower()
            lv = 0 if "head coach" in ro and "assistant" not in ro else 1 if ro == "coach" else None   # 0＝主教練（含代理）、1＝職稱只寫 Coach
            if lv is None or not x.get("p") or not x.get("tm") or not x.get("dj"):
                continue
            a = max(str(x["dj"])[:10], y0)
            b = min(str(x.get("dl") or today)[:10], y1, today)
            if b <= a:
                continue
            k = (x["tm"], lv, str(x["p"]))
            days[k] = days.get(k, 0) + (datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days
    best = {}
    for (tm, lv, p), d in days.items():
        cand = (lv, -d, p)   # 先比主教練優先、再比天數多
        if tm not in best or cand < best[tm]:
            best[tm] = cand
    return {tm: [_disp(p), p] for tm, (_lv, _d, p) in best.items()}


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


def resolve(cargo, pages, teams=()):
    """我們手上的頁名 → {頁名: (wiki 真正的頁名, 個人頁那張圖的檔名或 "")}；查不到的不在結果裡。
    Cargo 回來的頁名大小寫可能不同（deokdam／Deokdam），純數字的 ID（369、1874）會變成數字 ⇒ 一律轉字串、不分大小寫對回去。
    對不上的先查轉址（Thanatos (Park Seung-kyu) → (Park Seung-gyu)），再用 ID 找（Ming → Ming (Shi Sen-Ming)；同 ID 多人時挑在追蹤隊伍裡、或唯一還沒退役的那位）"""
    key = {str(p).lower(): p for p in pages}
    out = {}

    def players(names, as_map=None):
        m = as_map or {}
        for i in range(0, len(names), 40):
            for x in cargo({"tables": "Players=P", "fields": "P.OverviewPage=p,P.Image=img", "where": "P.OverviewPage IN " + _in(names[i:i + 40]), "limit": "500", "format": "json"}):
                k = m.get(str(x.get("p")).lower()) or key.get(str(x.get("p")).lower())
                if k and k not in out:
                    out[k] = (str(x["p"]), str(x.get("img") or ""))

    players(list(pages))
    miss = [p for p in pages if p not in out]
    if miss:
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
                hit = len(L) == 1 or str(L[0].get("tm") or "").lower() in tset
                if hit or len(act) == 1:
                    ali[str((L[0] if hit else act[0])["p"]).lower()] = k
        if ali:
            players(list(ali), ali)
    return out


def pick_files(cargo, real, year):
    """real＝{頁名: (真正的頁名, 個人頁圖檔)} → {頁名: (圖檔名, 是不是該年的照片)}
    PlayerImages.SortDate 大多是空的 ⇒ 日期依序用：SortDate → 那張圖所屬賽事的開始日（Tournaments.DateStart）→ 檔名／賽事名裡的年份"""
    back = {str(rp).lower(): p for p, (rp, _img) in real.items()}
    rows = {}
    names = [rp for rp, _img in real.values()]
    for i in range(0, len(names), 3):   # 一次 3 人：一個人最多上百張，一次查太多人會被 500 筆上限截掉
        for x in cargo({"tables": "PlayerImages=PI,Tournaments=T", "join_on": "PI.Tournament=T.OverviewPage", "fields": "PI.Link=p,PI.FileName=f,PI.SortDate=d,T.DateStart=ds,PI.Tournament=t",
                        "where": "PI.Link IN " + _in(names[i:i + 3]), "limit": "500", "format": "json"}):
            k = back.get(str(x.get("p")).lower())
            if not k or not x.get("f"):
                continue
            d = str(x.get("d") or x.get("ds") or "")[:10]
            if not d:
                ys = re.findall(r"(?<![0-9])20[0-3][0-9](?![0-9])", str(x.get("t") or "") + " " + str(x["f"]))
                d = (max(ys) + "-00-00") if ys else ""
            rows.setdefault(k, []).append((d, str(x["f"])))
    out = {}
    y0, y1 = f"{int(year)}-00-00", f"{int(year) + 1}-00-00"
    for p, (_rp, prof) in real.items():
        L = rows.get(p) or []
        cur = [r for r in L if y0 <= r[0] < y1]
        old = [r for r in L if r[0] and r[0] < y0]
        if cur:
            out[p] = (max(cur)[1], True)
        elif old:
            out[p] = (max(old)[1], False)
        elif prof:
            out[p] = (prof, False)
        elif L:
            out[p] = (L[0][1], False)
    return out


_DET = {}


def face_of(data):
    """圖片位元組 → [兩眼中點 x÷圖寬, 兩眼中點 y÷圖高, 臉寬÷圖寬, 圖寬÷圖高, 兩眼角度]；沒裝 OpenCV、沒有模型檔、或找不到臉就回 None。
    角度（使用者 2026-11-22「有些歐美選手頭像歪歪的」）：照片裡頭本身是歪的，前端照這個角度把頭轉正。YuNet 的眼睛座標＝畫面左邊那隻、畫面右邊那隻"""
    try:
        import cv2
        import numpy as np
        from PIL import Image
        if not os.path.exists(MODEL):
            return None
        im = Image.open(io.BytesIO(data)).convert("RGBA")
        W, H = im.size
        bg = Image.new("RGBA", im.size, (128, 128, 128, 255))
        bg.alpha_composite(im)   # 去背圖墊一層灰底再偵測
        k = 320 / max(W, H)
        a = cv2.cvtColor(np.asarray(bg.convert("RGB").resize((max(1, round(W * k)), max(1, round(H * k))), Image.LANCZOS)), cv2.COLOR_RGB2BGR)
        det = cv2.FaceDetectorYN.create(MODEL, "", (a.shape[1], a.shape[0]), 0.5, 0.3, 20)
        _, faces = det.detect(a)
        if faces is None or not len(faces):
            return None
        f = max(faces, key=lambda r: r[2] * r[3])
        ex, ey = (f[4] + f[6]) / 2, (f[5] + f[7]) / 2
        import math
        ang = math.degrees(math.atan2(float(f[7] - f[5]), float(f[6] - f[4])))
        al = np.asarray(im)[:, :, 3]
        cut = 1 if (al < 20).mean() > 0.05 else 0   # 去背照（透明的部分超過 5%）：前端只轉正這種，帶背景的轉了角落會露白
        return [round(float(ex / a.shape[1]), 3), round(float(ey / a.shape[0]), 3), round(float(f[2] / a.shape[1]), 3), round(W / H, 3), round(ang, 1), cut]
    except Exception:
        return None


def _fetch(url):
    for k in range(2):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read()
        except Exception:
            time.sleep(2)
    return b""


def images(cargo, pages, year, teams=()):
    """頁名清單 → {頁名: {"u": 縮圖網址或 "", "y": 1＝該年的照片, "f": 臉的位置或 None}}"""
    real = resolve(cargo, pages, teams)
    files = pick_files(cargo, real, year)
    th = _thumbs(sorted({f.replace("_", " ") for f, _cur in files.values()}))
    out = {}
    for p in pages:
        f, cur = files.get(p, ("", False))
        u = th.get(f.replace("_", " "), "") if f else ""
        o = {"u": u, "y": 1 if (u and cur) else 0}
        if u:
            data = _fetch(u)
            o["f"] = face_of(data) if data else None
            time.sleep(0.1)
        out[p] = o
    return out


def predecessors(cargo, teams):
    """{現在的隊名: [自己, 改名前的隊名…]}：沿著 Leaguepedia 的 TeamRenames 往回找（改名 rebrand／rename 與被收購 acquire 都算，含 wiki 上的錯字 reband／acuire；partner 不算；最多往回 8 層）。
    收購也算：Gen.G 的前身是 KSV（2017 收購 Samsung Galaxy），Ruler 從 Samsung 時期就在這支隊伍
    使用者 2026-11-22「如果中間有斷掉也要把前面的算進去」——wiki 把改名前後當成不同的隊（DWG KIA → Dplus Kia、SK Telecom T1 → T1），
    不接起來的話 ShowMaker 在 DK 只算得到 2023 年改名後、Faker 在 T1 只算得到 2019 年改名後"""
    out = {t: [t] for t in teams}
    back = {t: t for t in teams}   # 某個名字 → 它屬於哪一支現在的隊
    front = list(teams)
    for _ in range(8):
        if not front:
            break
        nxt = []
        for i in range(0, len(front), 25):
            for x in cargo({"tables": "TeamRenames", "fields": "OriginalName=o,NewName=n,Verb=v", "where": "NewName IN " + _in(front[i:i + 25]), "limit": "500", "format": "json"}):
                o, n = str(x.get("o") or ""), str(x.get("n") or "")
                if not o or n not in back or o in back or str(x.get("v") or "").lower() not in ("rebrand", "rename", "reband", "acquire", "acuire"):
                    continue
                back[o] = back[n]
                out[back[n]].append(o)
                nxt.append(o)
        front = nxt
    return out


def tenures(cargo, teams, C, today):
    """{現在的隊名: [[選手頁名, 加入日, 離隊日或 ""], …]}：這些隊伍（含改名前的名字）所有人的歷次效力區間（一天查一次）"""
    T = C.get("ten") or {}
    if T.get("t") == today and T.get("v") == 3 and all(tm in (T.get("rows") or {}) for tm in teams):
        return T["rows"]
    pre = predecessors(cargo, teams)
    of = {nm: cur for cur, L in pre.items() for nm in L}
    names = sorted(of)
    rows = {tm: [] for tm in teams}
    for i in range(0, len(names), 12):
        for y in cargo({"tables": "Tenures", "fields": "Tenures.Player=p,Tenures.Team=tm,Tenures.DateJoin=dj,Tenures.DateLeave=dl", "limit": "5000", "format": "json",
                        "order_by": "Tenures.DateJoin", "where": "Tenures.Team IN " + _in(names[i:i + 12])}):
            cur = of.get(y.get("tm"))
            if y.get("p") and y.get("dj") and cur:
                rows[cur].append([str(y["p"]), str(y["dj"])[:10], str(y.get("dl") or "")[:10]])
    C["ten"] = {"t": today, "v": 3, "rows": rows, "pre": {k: v for k, v in pre.items() if len(v) > 1}}
    return rows


def _k(n):
    return re.sub(r"[\s_.'\-]+", "", _disp(n)).lower()


def attach_tenures(board, rows):
    """把歷次效力區間掛到格子裡的人身上（tn＝[[起, 迄或 ""], …]，舊到新）。同一人同一隊中間斷過的每一段都列，前端加總。
    名字比對：先比完整頁名，再比「去掉括號與空白」的 ID（wiki 把 BrokenBlade 記成 Broken Blade）"""
    n = 0
    for t in board:
        if t.get("fa"):
            continue
        L = rows.get(t.get("tm")) or rows.get(t.get("nm")) or []
        if not L:
            continue
        by_page, by_id = {}, {}
        for p, dj, dl in L:
            by_page.setdefault(p.lower(), []).append([dj, dl])
            by_id.setdefault(_k(p), []).append([dj, dl])
        for es in (t.get("r") or {}).values():
            for e in es:
                if e.get("r"):
                    continue   # 傳聞的人還沒來，不寫
                pg = str(e.get("p") or e.get("n") or "")
                seg = by_page.get(pg.replace("_", " ").lower()) or by_id.get(_k(pg)) or by_id.get(_k(e.get("n") or ""))
                if seg:
                    e["tn"] = sorted(seg)
                    n += 1
    return n


def _load():
    try:
        return json.load(io.open(CACHE, encoding="utf-8"))
    except Exception:
        return {}


def build(cargo, year, board, roles=None, alias=None):
    """回傳 (s26, pimg, pfc)，並把效力區間掛進 board（e["tn"]）。board＝transfers_board.build 的結果；
    roles＝{名字: [路線, 頁名, wikiID]}（傳聞人選補頁名用）；alias＝{現在的隊名: 那一年打比賽時的隊名}（OpTic Gaming 2026 年叫 Dignitas）"""
    roles = roles or {}
    alias = alias or {}
    C = _load()
    if C.get("v") != VER:
        C["img"] = {}
        C["v"] = VER
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
    needc = sorted({tm for _nm, tm in teams if tm in S and "HC" not in S[tm]})
    if needc:
        got = coaches(cargo, year, sorted({alias.get(tm, tm) for tm in needc}))
        for tm in needc:
            S[tm]["HC"] = got.get(alias.get(tm, tm)) or []   # 空的＝查過但沒有，下次不再查
        print(f"   隊伍小框：{year} 主教練補查 {len(needc)} 隊，查到 {sum(1 for tm in needc if S[tm]['HC'])} 隊")
    s26 = {nm: {r: v for r, v in S[tm].items() if v} for nm, tm in teams if S.get(tm)}

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
    week = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()

    def stale(p):
        o = I.get(p)
        if not o:
            return True
        if not o.get("u"):
            return o.get("t", "") < today        # 沒圖：隔天重查
        return not o.get("y") and o.get("t", "") < week   # 不是該年的照片：7 天後重查一次

    need = sorted(p for p in pages if stale(p))
    if need:
        got = images(cargo, need, year, [tm for _nm, tm in teams])
        for p in need:
            o = got.get(p) or {"u": "", "y": 0}
            o["t"] = today
            I[p] = o
        print(f"   隊伍小框：圖片補查 {len(need)} 人，有圖 {sum(1 for p in need if I[p].get('u'))} 人（{year} 年的照片 {sum(1 for p in need if I[p].get('y'))} 人、量到臉 {sum(1 for p in need if I[p].get('f'))} 人）")
    # ③ 效力區間
    try:
        nt = attach_tenures(board, tenures(cargo, sorted({tm for _nm, tm in teams}), C, today))
        print(f"   效力區間：掛上 {nt} 人")
    except Exception as e:
        print(f"   效力區間查詢失敗（略過）：{type(e).__name__} {str(e)[:100]}")
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    io.open(CACHE, "w", encoding="utf-8").write(json.dumps(C, ensure_ascii=False, separators=(",", ":")))
    # 同一個人在 wiki 的頁名有大小寫兩種寫法（Deokdam／deokdam、Kyeahoo／kyeahoo；使用者 2026-11-22「deokdam 2027為何沒頭像」）：
    #   先發來自出賽紀錄（小寫那種）、格子來自名單（大寫那種），兩邊各查一次、只有一邊查得到圖 ⇒ 查不到的借用另一種寫法的那張
    low = {}
    for p, o in I.items():
        if o.get("u"):
            low.setdefault(p.lower(), o)
    for p in pages:
        if not I.get(p, {}).get("u") and low.get(p.lower()):
            I[p] = dict(low[p.lower()], t=today)
    # 角度是後來才加的：舊紀錄的臉只有四個數 ⇒ 重新抓圖量一次（只量臉，不重查 wiki）
    old = [p for p in pages if I.get(p, {}).get("u") and len(I[p].get("f") or []) < 6]
    for p in old:
        data = _fetch(I[p]["u"])
        I[p]["f"] = face_of(data) if data else I[p].get("f")
        time.sleep(0.1)
    if old:
        print(f"   隊伍小框：重新量臉 {len(old)} 張（加上角度與是否去背）")
        io.open(CACHE, "w", encoding="utf-8").write(json.dumps(C, ensure_ascii=False, separators=(",", ":")))
    pimg = {p: I[p]["u"] for p in sorted(pages) if I.get(p, {}).get("u")}
    pfc = {p: I[p]["f"] for p in sorted(pages) if I.get(p, {}).get("u") and I[p].get("f")}
    return s26, pimg, pfc
