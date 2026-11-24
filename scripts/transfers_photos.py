# -*- coding: utf-8 -*-
"""轉會分頁「隊伍小框」與「效力」要的資料（使用者 2026-11-22）。

  s26   {隊名（陣容表的 nm）: {TOP/JNG/MID/BOT/SUP/HC: [顯示 ID, wiki 頁名]}}
        HC＝戰隊 wiki 頁 Tournaments 區最近一場賽事名單上的第一位教練（使用者 2026-11-22 定的規則；細節見 coaches()）
        ＝那一年第三賽段替這隊出賽最多場的人（Leaguepedia ScoreboardPlayers；細節見 starters()）
  pimg  {wiki 頁名: 縮圖網址}
        選圖順序（使用者「選手的照片記得抓取的是2026最新一張 如果2026沒有才往前抓」）：
        PlayerImages 裡該年最新一張 → 沒有就該年以前最新的一張 → 個人頁那張（Players.Image）→ 其餘任何一張。只存有圖的人
  pfc   {wiki 頁名: [兩眼中點 x÷圖寬, 兩眼中點 y÷圖高, 臉寬÷圖寬, 圖寬÷圖高, 兩眼連線的角度（度，正＝畫面右邊那隻眼睛比較低）, 1＝去背照]}
        （使用者「圖片的人頭大小與位置幫我調整一致」）OpenCV 的 YuNet 臉部偵測（模型檔 csv_cache/face_detection_yunet_2023mar.onnx，
        使用者同意下載）量出來的；前端照這四個數把每張圖縮放、移動到「臉一樣寬、眼睛在同一個位置」。量不到的人前端退回一般的置中裁切
  pph   {wiki 頁名: 檔名}：程式端先裁好的頭像（192×192 webp，臉一樣寬、兩眼在同一點、頭轉正、身體下緣漸隱），
        放在轉會網站的 www/ph/（部署時一起上傳），前端直接顯示、不再用 CSS 縮放（使用者 2026-11-22「頭像感覺還是沒這麼整齊」「點頭像讀取的速度幫我加速」）。
        原圖抓過的存在 csv_cache/ph_src/，之後重裁不用再下載
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

import hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, "csv_cache", "transfers_photos.json")
MODEL = os.path.join(ROOT, "csv_cache", "face_detection_yunet_2023mar.onnx")
API = "https://lol.fandom.com/api.php"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}
ROLE = {"top": "TOP", "jungle": "JNG", "mid": "MID", "bot": "BOT", "support": "SUP"}
PX = 220   # 縮圖寬（畫面上最大 112px，臉放大後 2 倍螢幕也夠用）
VER = 2    # 快取版本：選圖規則改了就加一，舊的圖片紀錄整批重查
SRCDIR = os.path.join(ROOT, "csv_cache", "ph_src")
PHDIR = os.path.join(os.path.dirname(ROOT), "轉會網站", "www", "ph")   # 轉會網站的部署資料夾（transfers_hourly.py site 整個 www 一起部署）
RVER = "5"  # 裁切規則版本：改了 FW／EY／漸隱就加一，檔名跟著換（瀏覽器快取才會更新）
PS, PFW, PEY = 192, 0.36, 0.44   # 頭像邊長、臉寬佔邊長、兩眼高度佔邊長
PSH = 192   # 頭像高（2026-11-22 試過直式 4:5：只拍到胸口的照片下面空一截，跟 Viper 的空隙同一種問題 ⇒ 維持正方形）
PFADE = 48   # 頭像下緣淡出的長度（px，邊長 192；使用者 2026-11-22 嫌 26 不夠多不夠深）


def _in(names):
    return "(" + ",".join('"' + str(n).replace("\\", "\\\\").replace('"', '\\"') + '"' for n in names) + ")"


def _disp(page):
    """頁名 → 顯示 ID（去掉尾巴的消歧義括號：Doran (Choi Hyeon-jun) → Doran）"""
    s = str(page or "")
    i = s.rfind(" (")
    return s[:i] if i > 0 and s.endswith(")") else s


_POST = re.compile(r"playoff|final|road to|qualif|promotion|regional|play-in|tiebreak", re.I)
_PO = re.compile(r"playoff|final|regional", re.I)   # 季後賽（含聯賽決賽、地區資格賽）


def starters(cargo, year, teams):
    """teams＝wiki 隊名清單 → {wiki 隊名: {路線: [顯示 ID, 頁名]}}：那一年「第三賽段」各路出賽最多場的人。
    使用者 2026-11-22「陣容2026的圖 看的先發五人 要看第三賽段的先發五人 例如VKS輔助Kaiwing第三賽段就離隊了」（原本是整年出賽最多）。
    第三賽段＝這支隊伍那一年最後一個國內常規賽事（頁名有「/<年> Season/」、不是季後賽／決賽／資格賽那類）開打之後的國內比賽
    （含它的季後賽）：LCK＝Rounds 3-4＋Season Playoffs、LPL＝Split 3＋Grand Finals、LEC／LCS＝Summer、CBLOL＝Split 2（一年只有兩個 Split）、
    LPL 第二賽段就淘汰的隊＝Split 2。國際賽（MSI、世界賽、EWC、KeSPA 杯…）不算。同場數取頁名字母序，結果才固定"""
    out = {}
    tag = f"/{int(year)} Season/"
    for i in range(0, len(teams), 6):
        rows = cargo({"tables": "ScoreboardPlayers=SP", "fields": "SP.Team=tm,SP.Link=p,SP.Role=r,SP.OverviewPage=ov,COUNT(*)=n,MIN(SP.DateTime_UTC)=d0",
                      "group_by": "SP.Team,SP.Link,SP.Role,SP.OverviewPage",
                      "where": "SP.Team IN " + _in(teams[i:i + 6]) + f' AND SP.DateTime_UTC>="{year}-01-01" AND SP.DateTime_UTC<"{int(year) + 1}-01-01"',
                      "limit": "5000", "format": "json"})
        start = {}   # (隊, 賽事) → 這支隊伍在這個賽事的第一場
        for x in rows:
            k = (x.get("tm"), str(x.get("ov") or ""))
            d = str(x.get("d0") or "")[:10]
            if k[0] and tag in k[1] and d and (k not in start or d < start[k]):
                start[k] = d
        cut = {}     # 隊 → 第三賽段從哪天開始＝最後一個國內常規賽事的第一場
        for (tm, ov), d in start.items():
            if not _POST.search(ov.split(tag, 1)[1]) and d > cut.get(tm, ""):
                cut[tm] = d
        # 有進季後賽就只看季後賽（使用者 2026-11-22「第三賽段先發要優先看季後賽 如果有進季後賽就先看季後賽 如果沒進才看例行賽 BLG先發上路應該就是Bin」）
        def _po(ov):
            return bool(_PO.search(ov.split(tag, 1)[1])) if tag in ov else False
        inwin = [x for x in rows if x.get("tm") in cut and tag in str(x.get("ov") or "") and start.get((x.get("tm"), str(x.get("ov") or "")), "") >= cut[x.get("tm")]]
        haspo = {x.get("tm") for x in inwin if _po(str(x.get("ov") or "")) and ROLE.get(str(x.get("r") or "").strip().lower())}
        cnt = {}
        for x in inwin:
            tm, ov = x.get("tm"), str(x.get("ov") or "")
            rr = ROLE.get(str(x.get("r") or "").strip().lower())
            if not rr or not x.get("p") or (tm in haspo and not _po(ov)):
                continue
            k = (tm, rr, str(x["p"]))
            cnt[k] = cnt.get(k, 0) + int(x.get("n") or 0)
        best = {}
        for (tm, rr, p), n in cnt.items():
            if (tm, rr) not in best or n > best[(tm, rr)][0] or (n == best[(tm, rr)][0] and p < best[(tm, rr)][1]):
                best[(tm, rr)] = (n, p)
        for (tm, rr), (_n, pg) in best.items():
            out.setdefault(tm, {})[rr] = [_disp(pg), pg]
    return out


def coaches(cargo, year, teams):
    """teams＝wiki 隊名清單 → {wiki 隊名: [顯示 ID, 頁名]}：那一年的主教練。
    規則（使用者 2026-11-22「主教練就是看戰隊WIKI下方 Tournaments 的部分 最近一個比賽的第一個哨子圖後面的ID」）：
      戰隊頁下方 Tournaments 那一區＝wiki 的 TournamentPlayers（每場賽事的登錄名單）⇒ 取那一年、已經開打的賽事裡最近的一場，
      名單上職稱是教練（哨子圖）的第一位（N_PlayerInTeam 最小）。青訓／學院賽（LPL Youth Academy 之類）不算：那是二隊的名單。
      查不到賽事名單的隊，退回 Tenures：那一年當主教練（含代理）天數最多的人；再沒有就取職稱只寫 Coach、待最久的"""
    y0, y1 = f"{int(year)}-01-01", f"{int(year) + 1}-01-01"
    today = datetime.date.today().isoformat()
    out, best = {}, {}
    for i in range(0, len(teams), 10):
        for x in cargo({"tables": "TournamentPlayers=TP,Tournaments=T", "join_on": "TP.OverviewPage=T.OverviewPage",
                        "fields": "TP.Team=tm,TP.Link=p,TP.Role=ro,TP.N_PlayerInTeam=n,TP.OverviewPage=ov,T.DateStart=ds",
                        "where": "TP.Team IN " + _in(teams[i:i + 10]) + f' AND TP.Role LIKE "%Coach%" AND T.DateStart>="{y0}" AND T.DateStart<"{y1}" AND T.DateStart<="{today}"',
                        "limit": "5000", "format": "json"}):
            ov = str(x.get("ov") or "")
            if not x.get("p") or not x.get("tm") or re.search(r"youth|academy|rookie", ov, re.I):
                continue
            # 升降賽／資格賽、下一季的賽事不算（使用者 2026-11-22 GZ：抓到 11 月「LCP/2027 Season/Promotion」名單上的 Ratis，2026 實際是 Skywalk）
            sy = re.search(r"(20\d\d) Season", ov)
            if re.search(r"promotion|relegation|qualif", ov, re.I) or (sy and int(sy.group(1)) != int(year)):
                continue
            try:
                n = int(x.get("n") or 99)
            except ValueError:
                n = 99
            k = (str(x.get("ds") or "")[:10], ov)      # 最近的賽事：開打日最晚的那場（同一天開打取名稱排序後面的，結果才固定）
            cand = (k, -n, str(x["p"]))
            if x["tm"] not in best or cand[0] > best[x["tm"]][0] or (cand[0] == best[x["tm"]][0] and cand[1] > best[x["tm"]][1]):
                best[x["tm"]] = cand
    # 顯示 ID：賽事名單給的是頁名（wiki 頁名第一個字一定大寫：CvMax、Maizijian）⇒ 查 Players.ID 拿選手自己的寫法（cvMax）
    idof = {}
    pgs = sorted({str(p) for _k, _n, p in best.values()})
    for i in range(0, len(pgs), 40):
        for y in cargo({"tables": "PlayerRedirects=PR,Players=P", "join_on": "PR.OverviewPage=P.OverviewPage", "fields": "PR.AllName=an,P.ID=id,P.OverviewPage=pg",
                        "where": "PR.AllName IN " + _in(pgs[i:i + 40]), "limit": "500", "format": "json"}):
            if y.get("id") is not None and y.get("an") is not None:
                idof[str(y["an"]).lower()] = (str(y["id"]), str(y.get("pg") or y["an"]))
    for tm, (_k, _n, p) in best.items():
        disp, pg = idof.get(str(p).lower(), (_disp(p), p))
        out[tm] = [disp, pg]
    rest = [t for t in teams if t not in out]
    if rest:   # 退回 Tenures
        days = {}
        for i in range(0, len(rest), 15):
            for x in cargo({"tables": "Tenures=T,RosterChanges=RC", "join_on": "T.RosterChangeIdJoin=RC.RosterChangeId",
                            "fields": "T.Player=p,T.Team=tm,T.DateJoin=dj,T.DateLeave=dl,RC.Role=ro",
                            "where": "T.Team IN " + _in(rest[i:i + 15]) + f' AND RC.Role LIKE "%Coach%" AND (T.DateLeave>="{y0}" OR T.IsCurrent=1) AND T.DateJoin<"{y1}"',
                            "limit": "5000", "format": "json"}):
                ro = str(x.get("ro") or "").strip().lower()
                lv = 0 if "head coach" in ro and "assistant" not in ro else 1 if ro == "coach" else None
                if lv is None or not x.get("p") or not x.get("tm") or not x.get("dj"):
                    continue
                a = max(str(x["dj"])[:10], y0)
                b = min(str(x.get("dl") or today)[:10], f"{int(year)}-12-31", today)
                if b <= a:
                    continue
                kk = (x["tm"], lv, str(x["p"]))
                days[kk] = days.get(kk, 0) + (datetime.date.fromisoformat(b) - datetime.date.fromisoformat(a)).days
        fb = {}
        for (tm, lv, p), d in days.items():
            c = (lv, -d, p)
            if tm not in fb or c < fb[tm]:
                fb[tm] = c
        for tm, (_lv, _d, p) in fb.items():
            out[tm] = [_disp(p), p]
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
HR = 1.33   # 頭寬÷臉寬（去背照的中位數）：用頭寬推回臉寬，平均大小跟原本一樣


def _head_geom(al, F):
    """去背照的輪廓（al＝不透明的布林陣列、F＝臉框與眼睛，原圖座標）→ (頭中心 x, 頭寬, 傾斜度數) 或 None。
    每一列只取「包含臉中心的那一段連續不透明」（排除舉在頭旁邊的手），範圍＝輪廓頂 → 臉框底；
    只用寬度達最寬 75% 的列（去掉頭頂尖端與脖子）。傾斜＝這些列中點的斜率（正＝越往下越偏右）"""
    import math
    import numpy as np
    H, W = al.shape
    bx, by, bw, bh = F[:4]
    seed = bx + bw / 2
    top = None
    for y in range(0, int(min(H, by + bh))):
        if al[y, max(0, int(seed - bw / 2)):max(1, int(seed + bw / 2))].any():
            top = y
            break
    if top is None:
        return None
    ys, L, R = [], [], []
    for y in range(top, int(min(H, by + bh))):
        row = al[y]
        x0 = int(min(W - 1, max(0, seed)))
        if not row[x0]:
            xs = np.where(row)[0]
            if not len(xs):
                continue
            x0 = int(xs[np.argmin(abs(xs - seed))])
            if abs(x0 - seed) > bw * 0.6:
                continue
        l = x0
        while l > 0 and row[l - 1]:
            l -= 1
        r = x0
        while r < W - 1 and row[r + 1]:
            r += 1
        ys.append(y); L.append(l); R.append(r)
    if len(ys) < 8:
        return None
    ys, L, R = np.array(ys, float), np.array(L, float), np.array(R, float)
    w, mid = R - L, (L + R) / 2
    m = w >= 0.75 * np.percentile(w, 90)
    lean = math.degrees(math.atan(np.polyfit(ys[m], mid[m], 1)[0])) if m.sum() >= 8 else 0.0
    return float(np.median(mid[m])), float(np.percentile(w[m], 75)), lean


def face_of(data):
    """圖片位元組 → [頭的中心 x÷圖寬, 兩眼中點 y÷圖高, 臉寬÷圖寬, 圖寬÷圖高, 轉正角度, 是否去背, 1]；沒裝 OpenCV、沒有模型檔、或找不到臉就回 None。
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
        s = W / a.shape[1]
        F = [float(v) * s for v in f[:8]]   # 換回原圖座標
        ey = (F[5] + F[7]) / 2
        import math
        eang = math.degrees(math.atan2(F[7] - F[5], F[6] - F[4]))
        al = np.asarray(im)[:, :, 3]
        cut = 1 if (al < 20).mean() > 0.05 else 0   # 去背照（透明的部分超過 5%）：前端只轉正這種，帶背景的轉了角落會露白
        # 左右置中看頭型，不看眼睛（使用者 2026-11-22「不要用眼睛去判斷 依照頭型來置中 否則像Quad這種側臉就會看起來很怪」）：
        #   去背照用輪廓量頭的中心、頭寬（臉寬改用 頭寬÷HR，側臉的臉框偏窄會被放太大）、頭的傾斜；帶背景的照片退回臉框中心
        cx, fw, ang = F[0] + F[2] / 2, F[2], eang
        if cut:
            g = _head_geom(al > 60, F)
            if g:
                hx, hw, lean = g
                # 頭寬只拿來微調大小：推回的臉寬夾在臉框的 0.92～1.12 倍（使用者 2026-11-22「Reapered 頭像太小 他只是頭髮比較澎」「Carzzy也是」：
                #   頭髮蓬的人頭寬是臉寬的 1.75～1.9 倍，直接除 HR 會把頭縮太小；側臉 Quad 約 1.1 倍，不受影響）
                cx, fw = hx, min(max(hw / HR, F[2] * 0.92), F[2] * 1.12)
                # 很歪的頭略為轉正（使用者「頭如果很歪 你也可以略為轉正」）：眼睛角度與輪廓傾斜方向一致時取平均，不一致只信眼睛
                ang = (eang - lean) / 2 if eang * lean < 0 else eang
        return [round(cx / W, 3), round(ey / H, 3), round(fw / W, 3), round(W / H, 3), round(ang, 1), cut, 2]
    except Exception:
        return None


def _fetch(url):
    """原圖：先看 csv_cache/ph_src 有沒有，沒有才下載並存起來"""
    fn = os.path.join(SRCDIR, hashlib.md5(url.encode()).hexdigest() + ".img")
    if os.path.exists(fn):
        return io.open(fn, "rb").read()
    for k in range(2):
        try:
            data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read()
            os.makedirs(SRCDIR, exist_ok=True)
            io.open(fn, "wb").write(data)
            return data
        except Exception:
            time.sleep(2)
    return b""


def render_head(data, f):
    """原圖＋臉的位置 → 192×192 的頭像（RGBA；寬 PS、高 PSH）：臉寬＝邊長的 36%、兩眼中點在 (50%, 44%)、去背照把頭轉正（2～20 度）、
    身體下緣落在格子裡的（照片拍得比較近）最後 26px 漸隱；帶背景的照片放大到蓋滿整格"""
    from PIL import Image
    im = Image.open(io.BytesIO(data)).convert("RGBA")
    W, H = im.size
    ex, ey, fw, _ar, ang = f[:5]
    cut = f[5] if len(f) > 5 else 1
    S, SH = PS, PSH
    k = PFW * S / (fw * W)
    if not cut:
        k = max(k, (S / 2) / max(1e-6, ex * W), (S / 2) / max(1e-6, (1 - ex) * W), (PEY * S) / max(1e-6, ey * H), (SH - PEY * S) / max(1e-6, (1 - ey) * H))
    rw, rh = max(1, round(W * k)), max(1, round(H * k))
    r = im.resize((rw, rh), Image.LANCZOS)
    cx, cy = ex * rw, ey * rh
    if cut and 2 <= abs(ang) <= 20:
        r = r.rotate(ang, center=(cx, cy), resample=Image.BICUBIC)
    cv = Image.new("RGBA", (S, SH), (0, 0, 0, 0))
    ox, oy = round(S / 2 - cx), round(PEY * S - cy)
    cv.alpha_composite(r, (max(0, ox), max(0, oy)), (max(0, -ox), max(0, -oy)))
    # 每一張頭像下緣都漸隱（使用者 2026-11-22「所有陣容對比框的頭像 底下都用漸層」）：身體下緣落在格子裡就從那裡淡出，否則淡出格子最下面 26px
    # 2026-11-22 再改（使用者「漸層不夠多不夠深 導致 Viper 這種底部有空隙的 還是很明顯」）：轉正後身體下緣是斜的，水平一條漸層蓋不到 ⇒
    #   每一直行各自從「那一行的身體下緣」往上淡出 PFADE px，曲線 ((下緣−y)/L)^1.6（越靠下越透明）；只處理下緣在格子下半部的行（頭髮、耳朵的邊不動）
    # 2026-11-22 三改（使用者「頭像底部的空隙還是比較清楚」）：原圖只拍到胸口的（身體在框底上方就被切平），淡出蓋不掉下面那段空白 ⇒
    #   身體下緣在格子下半部、又沒到框底的直行：取下緣上面那幾列的衣服顏色往下延伸到框底（橫向 9px 平滑，避免直條紋），
    #   之後淡出改從框底往上 PFADE px；其他直行照舊從自己的身體下緣淡出
    import numpy as np
    a = np.asarray(cv).astype(np.float32)
    A = a[:, :, 3]
    op = A > 200
    last = np.where(op.any(axis=0), SH - 1 - np.argmax(op[::-1, :], axis=0), -1)
    ext = (last >= SH * 0.55) & (last < SH - 1)
    fill = np.zeros((S, 4), np.float32)
    for x in np.where(ext)[0]:
        seg = a[max(0, last[x] - 8):max(1, last[x] - 1), x]
        seg = seg[seg[:, 3] > 200]
        if len(seg):
            fill[x] = seg.mean(axis=0)
        else:
            ext[x] = False
    ker = np.ones(9) / 9
    w = ext.astype(np.float32)
    ws = np.convolve(w, ker, "same")
    sm = np.stack([np.convolve(fill[:, c] * w, ker, "same") for c in range(4)], 1) / np.maximum(ws[:, None], 1e-6)
    for x in np.where(ext)[0]:
        a[last[x] - 1:, x, :3] = sm[x, :3]
        a[last[x] - 1:, x, 3] = 255
    A = a[:, :, 3]
    op = A > 8
    last2 = np.where(op.any(axis=0), SH - 1 - np.argmax(op[::-1, :], axis=0), -1)
    yy = np.arange(SH, dtype=np.float32)[:, None]
    m = np.clip(((last2 + 1).astype(np.float32)[None, :] - yy) / PFADE, 0, 1) ** 1.6
    a[:, :, 3] = np.where((last2 >= SH * 0.55)[None, :], A * m, A)
    cv = Image.fromarray(a.clip(0, 255).astype(np.uint8), "RGBA")
    return cv


def heads(I, pages):
    """裁好頭像存到 PHDIR，回傳 {頁名: 檔名}；轉會網站的資料夾不在（別台電腦）就跳過。沒用到的舊檔刪掉"""
    if not os.path.isdir(os.path.dirname(PHDIR)):
        return {}
    os.makedirs(PHDIR, exist_ok=True)
    out, made = {}, 0
    for p in pages:
        o = I.get(p) or {}
        if not o.get("u") or not o.get("f"):
            continue
        fn = hashlib.md5((o["u"] + "|" + json.dumps(o["f"]) + "|" + RVER).encode()).hexdigest()[:14] + ".webp"
        dst = os.path.join(PHDIR, fn)
        if not os.path.exists(dst):
            try:
                data = _fetch(o["u"])
                if not data:
                    continue
                render_head(data, o["f"]).save(dst, "WEBP", quality=80, method=6)
                made += 1
            except Exception as e:
                print(f"   頭像裁切失敗 {p}：{type(e).__name__} {str(e)[:60]}")
                continue
        out[p] = fn
    keep = set(out.values())
    gone = [x for x in os.listdir(PHDIR) if x.endswith(".webp") and x not in keep]
    for x in gone:
        try:
            os.remove(os.path.join(PHDIR, x))
        except Exception:
            pass
    if made or gone:
        print(f"   隊伍小框：頭像新裁 {made} 張、刪掉沒用到的 {len(gone)} 張（共 {len(out)} 張）")
    return out


# Leaguepedia 沒有照片、從 Liquipedia 補的人（使用者 2026-11-22 選的精進第 6 項；跟 TE／XLG 隊徽同一種做法）
#   {Leaguepedia 頁名: (Liquipedia 圖片網址, 1＝該年的照片)}。Leaguepedia 之後有圖就用 Leaguepedia 的（這裡只補「沒圖」的人）
#   2026-11-22 查過：JinJin（Liquipedia 也沒照片）、Van1／Leigg／Dalike（Liquipedia 沒有頁面）找不到
LIQ_IMG = {
    "Guchi": ("https://liquipedia.net/commons/images/thumb/4/4e/FX_Guchi_at_CBLOL_Cup_2026_Week_3.jpeg/600px-FX_Guchi_at_CBLOL_Cup_2026_Week_3.jpeg", 1),
    # 第三格＝手動指定臉的位置（照片裡不只一個人、自動偵測抓錯人時用；格式同 face_of 的回傳）：KryRa 那張三個人，他在中間
    "KryRa": ("https://liquipedia.net/commons/images/thumb/0/05/DSG_KryRa_at_LCS_2026_Lock-In.jpg/600px-DSG_KryRa_at_LCS_2026_Lock-In.jpg", 1, [0.39, 0.37, 0.12, 1.496, 0.0, 0, 2]),
}


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


# 一級聯賽（年資用）：現在的六大聯賽＋前身（OGN Champions、EU／NA LCS）＋後來併進 LCP／LTA 的各區頂級聯賽＋國際賽
T1_HIST = {"LoL Champions Korea", "LoL The Champions", "Tencent LoL Pro League", "LoL EMEA Championship", "Europe League Championship Series",
           "League of Legends Championship Series", "North America League Championship Series", "Circuit Brazilian League of Legends",
           "League of Legends Championship Pacific", "Pacific Championship Series", "LoL Master Series", "Vietnam Championship Series",
           "LoL Japan League", "Garena Premier League", "Liga Latinoamerica", "League of Legends Championship of The Americas",
           "League of Legends Championship of The Americas North", "League of Legends Championship of The Americas South",
           "World Championship", "Mid-Season Invitational", "First Stand", "Mid-Season Cup 2020", "Esports World Cup"}


# 國籍 → 國旗檔名（IOC 三碼，img/flags/{碼}.png）；跟 index.html 的 NAT_ABBR 同一份（陣容對比頭像右上的國旗，使用者 2026-11-23）
NAT_IOC = {'Taiwan': 'TPE', 'Armenia': 'ARM', 'Iraq': 'IRQ', 'Venezuela': 'VEN', 'China': 'CHN', 'South Korea': 'KOR', 'Korea': 'KOR', 'Japan': 'JPN', 'Vietnam': 'VIE', 'Chinese Taipei': 'TPE', 'Hong Kong': 'HKG', 'Mongolia': 'MGL', 'Philippines': 'PHI', 'Thailand': 'THA', 'Singapore': 'SGP', 'Malaysia': 'MAS', 'Indonesia': 'INA', 'India': 'IND', 'Australia': 'AUS', 'New Zealand': 'NZL', 'United States': 'USA', 'Canada': 'CAN', 'Mexico': 'MEX', 'Guatemala': 'GUA', 'Brazil': 'BRA', 'Argentina': 'ARG', 'Chile': 'CHI', 'Peru': 'PER', 'Colombia': 'COL', 'France': 'FRA', 'Germany': 'GER', 'Spain': 'ESP', 'Portugal': 'POR', 'Italy': 'ITA', 'Greece': 'GRE', 'Poland': 'POL', 'Denmark': 'DEN', 'Sweden': 'SWE', 'Norway': 'NOR', 'Finland': 'FIN', 'Belgium': 'BEL', 'Netherlands': 'NED', 'Czech Republic': 'CZE', 'Slovakia': 'SVK', 'Hungary': 'HUN', 'Austria': 'AUT', 'Switzerland': 'SUI', 'Romania': 'ROU', 'Bulgaria': 'BUL', 'Croatia': 'CRO', 'Serbia': 'SRB', 'Slovenia': 'SLO', 'Lithuania': 'LTU', 'Latvia': 'LAT', 'Estonia': 'EST', 'Ireland': 'IRL', 'Iceland': 'ISL', 'United Kingdom': 'GBR', 'Ukraine': 'UKR', 'Russia': 'RUS', 'Türkiye': 'TUR', 'Turkey': 'TUR', 'Saudi Arabia': 'KSA', 'United Arab Emirates': 'UAE', 'Qatar': 'QAT', 'Kuwait': 'KUW', 'Israel': 'ISR', 'Algeria': 'ALG', 'Tunisia': 'TUN', 'Morocco': 'MAR', 'Egypt': 'EGY', 'South Africa': 'RSA'}


def bios(cargo, pages):
    """頁名清單 → {頁名小寫: {"b": 生日 YYYY-MM-DD, "j": 第一次加入職業隊的日子}}。
    生日＝Players.Birthdate（重新導向的舊頁名也查得到：走 PlayerRedirects）；出道＝Tenures 最早的 DateJoin（任何隊、任何職稱）"""
    out = {}
    for i in range(0, len(pages), 40):
        for y in cargo({"tables": "PlayerRedirects=PR,Players=P", "join_on": "PR.OverviewPage=P.OverviewPage",
                        "fields": "PR.AllName=an,P.OverviewPage=pg,P.Birthdate=b,P.Country=n", "where": "PR.AllName IN " + _in(pages[i:i + 40]),
                        "limit": "500", "format": "json"}):
            an = str(y.get("an") or "").lower()
            if an:
                o = out.setdefault(an, {"pg": str(y.get("pg") or "")})
                b = str(y.get("b") or "")[:10]
                if re.match(r"\d{4}-\d\d-\d\d$", b) and not b.startswith("0000"):
                    o["b"] = b
                n_ = NAT_IOC.get(str(y.get("n") or "").strip())
                if n_:
                    o["n"] = n_   # 國籍（IOC 三碼）
    pgs = sorted({o["pg"] for o in out.values() if o.get("pg")} | set(pages))
    # 年資只算一級聯賽（使用者 2026-11-22「年資全部改看一級聯賽的 教練也是」）：TournamentPlayers（賽事名單，選手與教練都在上面）×
    #   一級聯賽（現在六大＋它們的前身與併進來的聯賽、國際賽）、正賽（TournamentLevel=Primary、非資格賽）⇒ 最早那個賽事的開打日
    #   選手＝以五個位置上名單；教練＝職稱含 Coach／Analyst（分析師也算教練年資）
    lgs = _in(sorted(T1_HIST))
    first, firstc = {}, {}
    for i in range(0, len(pgs), 40):
        for y in cargo({"tables": "TournamentPlayers=TP,Tournaments=T", "join_on": "TP.OverviewPage=T.OverviewPage",
                        "fields": "TP.Player=p,TP.Role=ro,MIN(T.DateStart)=d",
                        "where": "TP.Player IN " + _in(pgs[i:i + 40]) + " AND T.League IN " + lgs + ' AND T.TournamentLevel="Primary" AND T.IsQualifier=0',
                        "group_by": "TP.Player,TP.Role", "limit": "2000", "format": "json"}):
            d = str(y.get("d") or "")[:10]
            if not re.match(r"\d{4}-\d\d-\d\d$", d):
                continue
            ro, k = str(y.get("ro") or ""), str(y.get("p") or "").lower()
            tgt = first if ro in ("Top", "Jungle", "Mid", "Bot", "Support") else (firstc if re.search(r"Coach|Analyst", ro) else None)
            if tgt is not None and (k not in tgt or d < tgt[k]):
                tgt[k] = d
    for p in pages:
        o = out.setdefault(p.lower(), {})
        j = first.get(str(o.get("pg") or "").lower()) or first.get(p.lower())
        if j:
            o["j"] = j
        c = firstc.get(str(o.get("pg") or "").lower()) or firstc.get(p.lower())
        if c:
            o["c"] = c
    return {k: {x: v for x, v in o.items() if x in ("b", "j", "c", "n")} for k, o in out.items()}


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
    """回傳 (s26, pimg, pfc, pph)，並把效力區間掛進 board（e["tn"]）。board＝transfers_board.build 的結果；
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
    # 規則改版 ⇒ 整批重查（版本號逐步升，每一版只做一次）：
    #   v2 先發改成第三賽段；v3 主教練排除升降賽／資格賽；v4 第三賽段有季後賽只看季後賽（都是 2026-11-22）
    sv = C.get("s26v") or 0

    def _drop_lanes():
        for tm in list(S):
            S[tm] = {k: v for k, v in S[tm].items() if k == "HC"}
            if not S[tm]:
                del S[tm]
    if sv < 3:
        for tm in S:
            S[tm].pop("HC", None)
    if sv < 4:
        _drop_lanes()
    C["s26v"] = 4
    need = sorted({tm for _nm, tm in teams if not any(r in (S.get(tm) or {}) for r in ROLE.values())})
    if need:
        got = starters(cargo, year, sorted({alias.get(tm, tm) for tm in need}))
        for tm in need:
            if got.get(alias.get(tm, tm)):
                S[tm] = dict(got[alias.get(tm, tm)], **({"HC": S[tm]["HC"]} if "HC" in (S.get(tm) or {}) else {}))
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
    # 後勤（主教練以外的教練／分析師）：只查生日／出道日（陣容表後勤欄照年資排；使用者 2026-11-24「後勤的排序依照年資」），不抓照片
    spages = {page_of(e) for t in board if not t.get("fa") for e in ((t.get("r") or {}).get("COACH") or []) if e.get("sr") != "HC"} - {""}
    I = C.setdefault("img", {})
    week = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()

    def stale(p):
        o = I.get(p)
        if not o:
            return True
        if not o.get("u") or o.get("liq"):
            return o.get("t", "") < today        # 沒圖（或暫用 Liquipedia 的）：隔天重查
        return not o.get("y") and o.get("t", "") < week   # 不是該年的照片：7 天後重查一次

    need = sorted(p for p in pages if stale(p))
    if need:
        got = images(cargo, need, year, [tm for _nm, tm in teams])
        for p in need:
            o = got.get(p) or {"u": "", "y": 0}
            o["t"] = today
            I[p] = o
        print(f"   隊伍小框：圖片補查 {len(need)} 人，有圖 {sum(1 for p in need if I[p].get('u'))} 人（{year} 年的照片 {sum(1 for p in need if I[p].get('y'))} 人、量到臉 {sum(1 for p in need if I[p].get('f'))} 人）")
    for p in sorted(pages & set(LIQ_IMG)):   # Leaguepedia 沒圖的人改用 Liquipedia 的
        o = I.get(p) or {}
        if o.get("u") and o.get("liq") is None:
            continue
        u, cur, *ff = LIQ_IMG[p]
        if o.get("u") != u or (ff and o.get("f") != ff[0]):
            data = _fetch(u)
            if data:
                I[p] = {"u": u, "y": cur, "f": ff[0] if ff else face_of(data), "t": today, "liq": 1}
                print(f"   隊伍小框：{p} 用 Liquipedia 的照片（量到臉 {'是' if I[p]['f'] else '否'}）")
    # ③ 效力區間
    try:
        nt = attach_tenures(board, tenures(cargo, sorted({tm for _nm, tm in teams}), C, today))
        print(f"   效力區間：掛上 {nt} 人")
    except Exception as e:
        print(f"   效力區間查詢失敗（略過）：{type(e).__name__} {str(e)[:100]}")
    # ④ 生日與出道日（陣容對比 2027 那排的年齡、年資；使用者 2026-11-22「2027 底下列出 年齡 年資(職業時長)」）：每 7 天重查一次
    BI = C.setdefault("bio", {})
    needb = sorted(p for p in pages | spages if (BI.get(p) or {}).get("t", "") < week or (BI.get(p) or {}).get("v") != 7)
    if needb:
        try:
            got = bios(cargo, needb)
            for p in needb:
                BI[p] = dict(got.get(p.lower()) or {}, t=today, v=7)   # v3＝教練年資含分析師；v4＝年資只算一級聯賽；v6＝多抓國籍
            print(f"   隊伍小框：生日／出道日補查 {len(needb)} 人，有生日 {sum(1 for p in needb if BI[p].get('b'))} 人、有出道日 {sum(1 for p in needb if BI[p].get('j'))} 人")
        except Exception as e:
            print(f"   生日／出道日查詢失敗（略過）：{type(e).__name__} {str(e)[:100]}")
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
    # 量法改過就重新量（只量臉，不重查 wiki；原圖有快取）：6 格＝舊的眼睛置中，7 格（最後一格 1）＝頭型置中
    old = [p for p in pages if I.get(p, {}).get("u") and ((I[p].get("f") or [0] * 7) + [0])[6] < 2]   # 7 格最後一格＝量法版本：1 頭型置中、2 臉寬夾在臉框 0.92～1.12 倍
    for p in old:
        data = _fetch(I[p]["u"])
        I[p]["f"] = face_of(data) if data else I[p].get("f")
        time.sleep(0.1)
    if old:
        print(f"   隊伍小框：重新量臉 {len(old)} 張（加上角度與是否去背）")
        io.open(CACHE, "w", encoding="utf-8").write(json.dumps(C, ensure_ascii=False, separators=(",", ":")))
    pimg = {p: I[p]["u"] for p in sorted(pages) if I.get(p, {}).get("u")}
    pfc = {p: I[p]["f"] for p in sorted(pages) if I.get(p, {}).get("u") and I[p].get("f")}
    pph = heads(I, sorted(pages))
    pbio = {p: [BI[p].get("b", ""), BI[p].get("j", ""), BI[p].get("c", ""), BI[p].get("n", "")] for p in sorted(pages | spages) if any((BI.get(p) or {}).get(x) for x in ("b", "j", "c", "n"))}   # 第 4 格＝國籍 IOC 碼   # [生日, 出道日, 第一次當教練]
    return s26, pimg, pfc, pph, pbio
