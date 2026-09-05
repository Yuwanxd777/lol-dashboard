# -*- coding: utf-8 -*-
"""選邊權／先選權統計（2026 新制）→ side_sel.js

**資料在哪**（2026-08-03 使用者指出）：各賽事總覽頁的「VODs & Match Links」表，
例：https://lol.fandom.com/wiki/LCP/2026_Season/Split_3
表頭有 `Blue | Red | 1st Sel | Side Sel | Pick Sel` 五個逐局欄位——這是 2026 新制才有的
記錄：**選邊權與先選權分開**（誰有第一選擇權、誰拿走選邊、誰拿走選先選、實際藍紅方）。

**為什麼值得抓**：我們現有的 firstPick 是從 gol.gg 的 First Pick 圖示與 Picks and Bans 頁
的 T1 反推的，藍紅方在 PB 補的局甚至是近似值；這張表是官方層級的原始記錄，可以直接用，
也可以拿來驗證既有推論。

**表格結構**（欄數各聯賽不同，LCK 比 LCP 多 Interview/With/HL/Reddit）：
  每個系列賽一組列——第一列是「系列層級欄位＋第 1 局」，之後每多一局多一列，
  只有逐局欄位（前面的系列欄位被 rowspan 併掉）。
  → 所以**欄位一律用表頭位置定位，不能寫死偏移**；逐局列的第 0 格＝表頭的 Blue 欄。

用法：
  python scripts\\fetch_side_sel.py                 # 自動找 2026 有比賽的賽事頁
  python scripts\\fetch_side_sel.py --page "LCP/2026 Season/Split 3"   # 只抓指定頁
  python scripts\\fetch_side_sel.py --dump          # 只印不寫檔
"""
import argparse, html as _html, io, json, os, re, sys, time, urllib.parse, urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
CACHE = os.path.join(ROOT, "csv_cache", "sidesel")
YEAR = 2026
GAP = 6.0
HIST = False   # --year <2026 的歷史回補模式：只收 MVP/VOD（選邊欄位清空），輸出 side_sel_YYYY.js

import fetch_wiki_mh as MH          # 共用 opener（先拿 cookie，否則 302→403）與 UA
import fetch_wiki_stats as WS       # 共用 Special:CargoExport 通道（不吃 Cargo API 限流）

TXT = lambda s: re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()
KEYS = ["Blue", "Red", "1st Sel", "Side Sel", "Pick Sel"]


# 只抓**一級聯賽＋國際賽**（＝主數據真的收的那些）。二級／區域聯賽（LCK CL、VCS、
# Rift Legends、Circuito Desafiante、IDL Kings、NACL、Americas Cup…）的局根本不在主數據裡，
# 抓回來永遠配不到任何一局，只是讓每次更新多花時間（2026-08-03 使用者：只要一級聯賽）。
# 寫成規則不寫死年份：`LCK/2026 Season/...` 這種頁名格式歷年一致，明年不必改。
# ⚠ 分隔線一定要是 `/`：`LCK CL/...`（二級）就是靠這個排除的。
TIER1 = re.compile(r"^(LCK|LPL|LEC|LCS|LCP|CBLOL)/")
# 歷史回補（2026-09-04）：2019 前的一級聯賽頁名不同（NA LCS／EU LCS／LMS／
# Champions＝韓國 OGN 時代、PCS＝LCP 前身、CBLoL 大小寫不同）——只在 HIST 模式放寬。
TIER1H = re.compile(r"^(LCK|LPL|LEC|LCS|LCP|CBLOL|NA LCS|EU LCS|LMS|Champions|PCS|CBLoL)/", re.I)
INTL = re.compile(r"(First Stand|KeSPA Cup|Mid-Season Invitational|World Championship|Esports World Cup)", re.I)
want_ov = lambda ov: bool((TIER1H if HIST else TIER1).match(ov or "") or INTL.search(ov or ""))


def ov_pages():
    """2026 有比賽的賽事總覽頁（用 ScoreboardGames 的 OverviewPage 去重），只留一級聯賽＋國際賽。

    不寫死清單：新賽段開打就自動出現，也不會抓到還沒打的頁。
    """
    # 起點抓到前一年 10 月：跨年賽事（賽季的季前 KeSPA 杯在前一年 12 月開打，頁名掛前一年，
    # 如「2025 LoL KeSPA Cup」）只用當年窗永遠發現不了。⚠ 2025-12 那屆實查頁面**沒有**
    # Side Sel／1st Sel 欄（選邊權欄位是 2026 新制才開始記），所以該屆 56 局仍然無解；
    # 放寬視窗是為了明年起的季前賽事能自動被發現（2026-08-05 使用者回報選邊缺漏後查明）。
    p = {"tables": "ScoreboardGames=SG", "fields": "SG.OverviewPage=ov",
         "where": 'SG.DateTime_UTC >= "%d-10-01" AND SG.DateTime_UTC < "%d-01-01"' % (YEAR - 1, YEAR + 1),
         "group_by": "SG.OverviewPage", "format": "json", "limit": "500"}
    url = WS.FORM + "?" + urllib.parse.urlencode(p)
    raw = WS.opener().open(urllib.request.Request(url, headers=WS.UA), timeout=120).read().decode("utf-8", "replace")
    if raw.lstrip()[:1] not in "[{":
        print("  ⚠ 賽事頁清單抓取失敗：" + raw[:120]); return []
    all_ov = sorted({r.get("ov") for r in json.loads(raw) if r.get("ov")})
    keep = [o for o in all_ov if want_ov(o)]
    print(f"  {YEAR} 有比賽的賽事頁 {len(all_ov)} 個 → 一級聯賽／國際賽 {len(keep)} 個")
    return keep


def live_pages(days):
    """最近 days 天內有比賽的賽事頁＝**還在進行中**，每次更新都要重抓頁面。

    ⚠這條是這支腳本能不能天天長新資料的關鍵：page_html 有磁碟快取，
    一旦某個賽事頁抓過就再也不會重抓 → 該賽段後來打的每一局都不會進 side_sel.js
    （2026-08-03 使用者：「選邊只有 WIKI 有紀錄，需要每次更新時都自動去抓」）。
    打完的賽事（近 days 天沒有比賽）維持吃快取，不然 190 幾頁每次跑要 20 分鐘。
    """
    from datetime import date, timedelta
    since = (date.today() - timedelta(days=days)).isoformat()
    p = {"tables": "ScoreboardGames=SG", "fields": "SG.OverviewPage=ov",
         "where": 'SG.DateTime_UTC >= "%s"' % since,
         "group_by": "SG.OverviewPage", "format": "json", "limit": "500"}
    url = WS.FORM + "?" + urllib.parse.urlencode(p)
    try:
        raw = WS.opener().open(urllib.request.Request(url, headers=WS.UA), timeout=120).read().decode("utf-8", "replace")
        if raw.lstrip()[:1] not in "[{":
            return None                       # 查不到就回 None＝不確定 → 呼叫端全部重抓，寧可慢不要漏
        return {r.get("ov") for r in json.loads(raw) if r.get("ov")}
    except Exception as e:
        print(f"  ⚠ 進行中賽事查詢失敗（{type(e).__name__}）→ 這次全部重抓")
        return None


def page_html(ov, force=False):
    os.makedirs(CACHE, exist_ok=True)
    f = os.path.join(CACHE, re.sub(r"[^A-Za-z0-9]+", "_", ov).strip("_").lower() + ".html")
    if os.path.exists(f) and os.path.getsize(f) > 5000 and not force:
        return open(f, encoding="utf-8").read()
    url = ("https://lol.fandom.com/api.php?action=parse&page=" + urllib.parse.quote(ov)
           + "&prop=text&format=json&formatversion=2")
    for a in range(3):
        try:
            d = json.loads(MH.opener().open(urllib.request.Request(url, headers=MH.UA), timeout=120)
                           .read().decode("utf-8", "replace"))
            if "error" in d:
                return ""
            h = d["parse"]["text"]
            open(f, "w", encoding="utf-8").write(h)
            time.sleep(GAP)
            return h
        except Exception as e:
            print(f"    抓取失敗（{a+1}/3）：{type(e).__name__}"); time.sleep(12 * (a + 1))
    return ""


def parse(ov, htm):
    """→ [{t1,t2,score,gi,blue,red,first_sel,side_sel,pick_sel}]（逐局一筆）"""
    # ⚠這張表是**巢狀**的（外層一張、每週一張內層）→ 不能用非貪婪的 <table>.*?</table>：
    # 那樣只會切到第一個 </table>（實測只拿到 1596 字元、資料列全在外面）。
    # 改成從表頭位置往回找最近的 <table，再用配對計數找出真正的結尾。
    pos = htm.find("Side Sel")
    if pos < 0:
        return []
    s = htm.rfind("<table", 0, pos)
    if s < 0:
        return []
    depth, tbl = 0, htm[s:]
    for m in re.finditer(r"<table\b|</table>", htm[s:]):
        depth += -1 if m.group(0).startswith("</") else 1
        if depth == 0:
            tbl = htm[s:s + m.end()]; break
    out, cur = [], None
    idx = None
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tbl, re.S):
        # attrs 要另外留一份：cells 只擷取 <td> 的**內容**，而先選/後選的顏色 class 在
        # <td> 標籤本身上（standings-mhBlue/mhRed）——只看內容永遠讀不到。
        _cell2 = re.findall(r"<t[dh]([^>]*)>(.*?)</t[dh]>", tr, re.S)
        cells = [c for _, c in _cell2]
        attrs = [a0 for a0, _ in _cell2]
        if not cells:
            continue
        txt = [TXT(c) for c in cells]
        if idx is None:                                   # 表頭：記下五個逐局欄的位置
            # 用**前綴**比對不用精確比對：最後一格是「Pick Sel 1st Pick 2nd Pick」
            # （Pick Sel 底下還有子表頭，純文字化後會黏成一格）。
            if any(t.startswith("Side Sel") for t in txt):
                # **先精確比對再退回前綴**：只用前綴的話 "Red" 會先命中 "Reddit" 欄
                #（LEC/LCK 這類表有 Reddit），整欄取到垃圾、選邊權判不出來（實測 36% 落空）。
                # 需要前綴的只有最後那格「Pick Sel 1st Pick 2nd Pick」。
                idx = {}
                for k in KEYS:
                    j = next((i for i, t in enumerate(txt) if t == k), -1)
                    if j < 0:
                        j = next((i for i, t in enumerate(txt) if t.startswith(k)), -1)
                    if j >= 0:
                        idx[k] = j
                # MVP／VODs（使用者 2026-09-04 要求）：MVP＝**系列**MVP（只出現在系列首列、
                # 無 rowspan、位置在 Blue 前——這正是逐局列 base 位移一直對得上的原因）；
                # VODs＝逐局，新版分 PB • Start • Post 三顆連結、舊版單一「Vod」。兩欄都是選配。
                for k in ("MVP", "VODs"):
                    j = next((i for i, t in enumerate(txt) if t == k), -1)
                    if j < 0:
                        j = next((i for i, t in enumerate(txt) if t.startswith(k)), -1)
                    if j >= 0:
                        idx[k] = j
                miss = set(KEYS) - set(idx)
                # 1st Sel／Pick Sel 是**選配**：VCS／Rift Legends／NACL 的表只有 Side Sel，
                # 硬要五欄齊全會把這些聯賽整個丟掉（實測 7 個賽事、幾百局的選邊資料全沒收）。
                # 少了它們就只出選邊權，前端的「選選序率」自然不計這些局。
                if miss - {"1st Sel", "Pick Sel"}:
                    print(f"    ⚠ {ov}：表頭少了 {miss}，跳過"); return []
                if miss:
                    print(f"    · {ov}：只有選邊欄（沒有 {sorted(miss)}）→ 只收選邊權")
            continue
        # 巢狀表是「每週一張」，每張都自帶表頭 → 後面還會再遇到表頭列，不能當成資料
        #（會產出 blue='Team 1' red='Team 2' 這種垃圾列）。
        if txt[0] in ("Team 1", "Blue") or any(t.startswith(("Side Sel", "1st Sel", "Pick Sel")) for t in txt):
            continue
        base = idx["Blue"]
        is_match = "logo std" in (cells[0] if cells else "")   # 系列層級列＝第一格是隊伍 logo
        if is_match:
            # alt 取出來要 unescape：`Anyone&#39;s Legend` 不還原的話正規化成 anyone39slegend，
            # 跟賽程的 anyoneslegend 對不上，整個 LPL 就會因配對率不足被跳過（實測 20/26）。
            team = lambda i: _html.unescape((re.search(r'alt="([^"]+?)logo std"', cells[i]) or [None, ""])[1]).strip()
            # 系列一律先進 out（即使一局都沒收）：out 的順序要與賽程清單逐項對齊，
            # 少一個未打的系列就會整串錯位。
            cur = {"t1": team(0), "t2": team(1), "score": txt[2] if len(txt) > 2 else "", "n": 0, "games": []}
            out.append(cur)
            g = lambda k: (txt[idx[k]] if (k in idx and len(txt) > idx[k]) else "")
            graw = lambda k: (cells[idx[k]] if (k in idx and len(cells) > idx[k]) else "")
            # MVP 兩種版型：LCK 這類＝**系列** MVP、欄在 Blue 前（前導）；LCS 這類＝**逐局** MVP、
            # 欄在 VODs 後（尾隨）。以表頭位置判別；前導式只把值掛在第 1 局。
            _mvlead = ("MVP" in idx) and idx["MVP"] < idx["Blue"]
            _mv = g("MVP") if _mvlead else ""
            cur["mvp"] = "" if _mv.strip().lower() in ("", "none", "tbd") else _mv.strip()   # wiki 沒頒就寫 None
            cur["mvlead"] = _mvlead
        elif cur and len(cells) >= len(idx) - 1:
            g = lambda k: (txt[idx[k] - base] if (k in idx and len(txt) > idx[k] - base) else "")
            graw = lambda k: (cells[idx[k] - base] if (k in idx and len(cells) > idx[k] - base) else "")
        else:
            continue
        cur["n"] += 1
        bl, rd, ss = g("Blue"), g("Red"), g("Side Sel")
        if not (bl or rd):
            continue
        # **關鍵簡化**：Side Sel 必定是該局藍紅其中一隊 → 這裡就算成「選邊權在哪一邊」，
        # 前端不必再做 wiki 縮寫→資料庫縮寫的對照（逐局欄是純文字縮寫、沒有連結可查全名）。
        side = "b" if ss and ss == bl else ("r" if ss and ss == rd else "")
        # 還沒打的場次（Blue/Red 都寫 TBD、選擇權欄全空）不收——實測 2758 列裡有 829 列是這種。
        # 全庫沒有「算不出選邊權但有先選權資料」的列，所以 side 空＝這局根本還沒有資料。
        # ⚠ 歷史回補（HIST）例外：舊賽季頁的 Side Sel 欄常是空的（2026 新制才記），
        # 但 MVP/VOD 還在——只把 TBD（沒打）的列丟掉，其餘留著收 MVP/VOD。
        if not side:
            if not HIST or bl.strip().upper() in ("", "TBD") or rd.strip().upper() in ("", "TBD"):
                cur["n"] -= 1
                continue
        # 先選/後選記在 Pick Sel 那格的**顏色 class** 上（格子文字只有「握選序權的隊名」）：
        # standings-mhBlue＝這隊選了先選、standings-mhRed＝選了後選（wiki 藍/紅色重複利用成 1st/2nd）。
        # 2026-08-03 使用者抓包：LGD S3 七次握選序全選後選(wiki 全紅)，我們的選先選率卻不是 0%——
        # 之前那欄是拿主資料 blue_firstPick 推的，而它在 2026 有一堆是預設藍方，這格才是正解。
        _pi = idx.get("Pick Sel")
        _pj = None if _pi is None else (_pi if is_match else _pi - base)
        _pattr = attrs[_pj] if (_pj is not None and 0 <= _pj < len(attrs)) else ""
        pc = 1 if "standings-mhBlue" in _pattr else (2 if "standings-mhRed" in _pattr else 0)
        # 逐局 VOD：新版一格三顆（PB • Start • Post）→ 只取 **PB**（BP 時間軸，使用者 2026-09-04）；
        # 舊版單一「Vod」連結＝整局，一顆就拿；多顆但沒有 PB（怪表）寧可不取。
        # VODs 不能用表頭索引：部分表的表頭把「1st Pick／2nd Pick」列成獨立欄、資料列卻沒有
        # 那兩格（實測 2551 局只抓到 83）。穩健法＝**從列尾往前**找「錨點文字是 PB/Start/Post/Vod」
        # 的格（LCS 的 VOD 後面還跟一格逐局 MVP 選手連結；⚠ 不能只看「有外部連結」——系列層的
        # Interview/Reddit 也是外連、錨點文字是 Link，會整排誤收（實測 LPL 被灌 639 個假 VOD））。
        # ⚠ 錨點文字夾著 U+2060（word joiner，&#8288;）不是空白、TXT 清不掉 → 比對前把非英數全剝掉
        _atx = lambda tx: re.sub(r"[^A-Za-z0-9]", "", TXT(tx)).upper()
        _VT = {"PB", "START", "POST", "VOD"}
        _vod, _vk = "", ""
        for _c9 in reversed(cells):
            if 'href="http' not in _c9:
                continue
            _ls = [(h, _atx(tx)) for h, tx in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', _c9, re.S)]
            _q = [(h, tx) for h, tx in _ls if tx in _VT]
            if not _q:
                continue                                   # 外連但不是 VOD 格（Interview/Reddit 的 Link）
            # 優先 PB（BP 時間軸，使用者 2026-09-04）；舊式單一「Vod」＝整片，內含 BP 也收。
            # 2026-09-05 使用者定案追加：**沒有 PB 就退回 Start**——LCS 整個聯賽只放 Start，
            # 照原本的字面規則會整年空白。Start 是開局，看不到 BP 過程，但至少點得到那一局；
            # 標記寫進 `vodk`（"pb"／"start"／"vod"），前端據此改連結文字提示。
            _vod = next((h for h, tx in _q if tx == "PB"), "")
            _vk = "pb" if _vod else ""
            if not _vod:
                _s0 = next((h for h, tx in _q if tx == "START"), "")
                if _s0:
                    _vod, _vk = _s0, "start"
            if not _vod and len(_q) == 1 and _q[0][1] == "VOD":
                _vod, _vk = _q[0][0], "vod"
            break
        # 逐局 MVP（尾隨式）：最後一格是 /wiki/ 選手連結才算（外連格＝VOD、純文字＝其他欄）。
        # ⚠ 不能用 mvlead 排除：LPL/First Stand 是前導系列 POM＋尾隨逐局 POG **同時存在**，
        # 舊版在前導頁直接跳過尾隨格 → LPL 的 POG 全沒收到（2026-09-04 使用者抓包）。
        _gm = ""
        if cells and 'href="/wiki/' in cells[-1] and 'href="http' not in cells[-1]:
            _gm = TXT(cells[-1]).strip()
            if _gm.lower() in ("none", "tbd"):
                _gm = ""
        # mvp＝**逐局** MVP（尾隨格），一律不跟系列 MVP 混：LPL/LCS 季後賽/First Stand 是
        # **兩種同時發**（系列一位 POM＋每局一位 POG），舊版「前導式只掛第 1 局、其餘用逐局」
        # 把 LPL 的逐局 POG 全標成 POM（2026-09-04 使用者抓包搞反）。系列 MVP 由 main() 用
        # cur["mvp"]/mvlead 另掛 mvpm。
        cur["games"].append({"gi": cur["n"], "blue": bl, "red": rd, "ss": side, "pc": pc,
                             "first_sel": g("1st Sel"), "pick_sel": g("Pick Sel"),
                             "vod": _html.unescape(_vod), "vodk": _vk,
                             "mvp": _gm})
    return out


def sched(ov):
    """該賽事的比賽清單（依時間）→ [(日期, Team1全名, Team2全名, 'S1-S2')]。

    賽程表沒有日期欄（只有週次分組）→ 靠 Cargo 的 MatchSchedule 補：實測它的時間順序
    與頁面列出的順序完全一致，且有比分可以逐場驗證對齊有沒有跑掉。
    """
    p = {"tables": "MatchSchedule=MS",
         "fields": "MS.DateTime_UTC=dt,MS.Team1=t1,MS.Team2=t2,MS.Team1Score=s1,MS.Team2Score=s2",
         "where": 'MS.OverviewPage="%s"' % ov.replace('"', ""),
         "order_by": "MS.DateTime_UTC", "format": "json", "limit": "500"}
    url = WS.FORM + "?" + urllib.parse.urlencode(p)
    try:
        raw = WS.opener().open(urllib.request.Request(url, headers=WS.UA), timeout=120).read().decode("utf-8", "replace")
        if raw.lstrip()[:1] not in "[{":
            return []
        return [(str(r.get("dt") or "")[:10], r.get("t1") or "", r.get("t2") or "",
                 "%s - %s" % (r.get("s1"), r.get("s2"))) for r in json.loads(raw)]
    except Exception:
        return []


def main():
    global YEAR, HIST
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", action="append", default=[], help="只抓指定 OverviewPage（可重複）")
    ap.add_argument("--force", action="store_true", help="重抓所有頁面（不吃快取）")
    ap.add_argument("--fresh-days", type=int, default=14,
                    help="最近幾天內有比賽的賽事＝進行中，每次都重抓頁面（預設 14）")
    ap.add_argument("--year", type=int, default=0,
                    help="歷史回補：抓指定年份的 MVP/VOD → side_sel_YYYY.js（選邊欄位一律清空，"
                         "舊制頁的 Side Sel 是模板渲染、不是 2026 新制資料）")
    ap.add_argument("--dump", action="store_true", help="只印不寫檔")
    A = ap.parse_args()
    if A.year and A.year < 2026:
        YEAR, HIST = A.year, True

    pages = A.page or ov_pages()
    # 進行中的賽事一律重抓（快取只服務已經打完的賽事）——不這樣做的話，賽段中途新打的局
    # 永遠不會進 side_sel.js，因為那一頁第一次抓完就一直吃快取。
    # 歷史回補：賽季早就打完，全部吃快取（live=空集合＝一頁都不用強制重抓）。
    live = set() if HIST else (None if (A.force or A.page) else live_pages(A.fresh_days))
    print(f"賽事頁 {len(pages)} 個"
          + ("（全部重抓）" if live is None else f"，其中進行中 {len(live & set(pages))} 個要重抓，其餘吃快取"))
    allrec, hit = [], 0
    for ov in pages:
        h = page_html(ov, force=A.force or live is None or ov in live)
        if not h:
            continue
        sers = parse(ov, h)
        if not sers:
            continue
        sc = sched(ov)
        # **不能用位置對齊**：季後賽頁面按賽制分組（勝部／敗部），頁面順序不等於時間順序
        #（LPL Split 1 Playoffs 實測前 10 場對得上、第 11 場起整個錯位）。
        # 改成「兩隊＋比分」配對：逐一在賽程清單裡找還沒被用過、兩隊與比分都吻合的那場。
        # 隊名比對用**互相包含**：頁面的隊名取自 logo alt（"We"），賽程給的是全名（"Team WE"）。
        # 還沒打完的（頁面 TBD）本來就沒有比分可配，直接跳過不收。
        nkq = lambda s: re.sub(r"[^a-z0-9]", "", str(s or "").lower())

        def same(a, b):
            a, b = nkq(a), nkq(b)
            return bool(a) and bool(b) and (a in b or b in a)

        used, pair = set(), {}
        for i, s in enumerate(sers):
            if not re.match(r"^\d+\s*-\s*\d+$", s["score"] or ""):
                continue
            for j, (d0, a0, b0, sco) in enumerate(sc):
                if j in used or sco != s["score"]:
                    continue
                if (same(s["t1"], a0) and same(s["t2"], b0)) or (same(s["t1"], b0) and same(s["t2"], a0)):
                    used.add(j); pair[i] = j; break
        need = [i for i, s in enumerate(sers) if s["games"]]
        got = [i for i in need if i in pair]
        if need and len(got) < len(need) * 0.9:
            print(f"  ⚠ {ov}：賽程配對失敗（{len(got)}/{len(need)} 場配到日期）→ 跳過")
            continue
        hit += 1
        # MVP 兩軌各自獨立（2026-09-04 使用者定名並抓包搞反後改制）：
        #   mvp ＝逐局 POG（每局一位，尾隨格）；mvpm＝系列 POM（一整場一位，前導格，只掛系列第 1 局）。
        #   LPL/LCS 季後賽/First Stand 兩種**同時發**，不能用單一 mvs 版型旗標。
        #   mg/mm＝**這個賽事頁**有沒有發 POG/POM——評分「率」的分母要用可獲得數，
        #   沒發的賽事不能算機會（例：LCK 2026 只發 POM，選手的 POG 分母不含 LCK 局）。
        hasG = any(g2.get("mvp") for s2 in sers for g2 in s2["games"])
        hasM = any(s2.get("mvlead") and s2.get("mvp") for s2 in sers)
        n = 0
        for i, s in enumerate(sers):
            if i not in pair:
                continue                      # 配不到日期的場次寧可不收，不掛錯日期
            d, t1, t2, _ = sc[pair[i]]
            pm = (s.get("mvp") or "") if s.get("mvlead") else ""
            first = True
            for g in s["games"]:
                mvpm = pm if first else ""
                first = False
                if HIST:
                    # 歷史回補：只收 MVP/VOD。選邊欄位**在輸出層清空**（舊制頁的 Side Sel 是
                    # wiki 模板統一渲染，不是 2026 新制的選邊權資料，流出去會生出假統計）；
                    # 三樣都沒有的局不寫（省檔案大小，前端查不到本來就顯示「–」）。
                    if not (g.get("mvp") or mvpm or g.get("vod")):
                        continue
                    allrec.append({"d": d, "t1": t1, "t2": t2, "gi": g["gi"], "ss": "",
                                   "pc": 0, "fs": "", "ps": "", "ov": ov,
                                   "mvp": g.get("mvp") or "", "mvpm": mvpm,
                                   "mg": 1 if hasG else 0, "mm": 1 if hasM else 0,
                                   "vod": g.get("vod") or "", "vodk": g.get("vodk") or ""})
                    n += 1
                    continue
                allrec.append({"d": d, "t1": t1, "t2": t2, "gi": g["gi"], "ss": g["ss"],
                               "blue": g["blue"], "red": g["red"], "pc": g.get("pc") or 0,
                               "fs": g["first_sel"], "ps": g["pick_sel"], "ov": ov,
                               "mvp": g.get("mvp") or "", "mvpm": mvpm,
                               "mg": 1 if hasG else 0, "mm": 1 if hasM else 0,
                               "vod": g.get("vod") or "", "vodk": g.get("vodk") or ""})
                n += 1
        print(f"  ✓ {ov}：{len(sers)} 場 / {n} 局")
    print(f"有選邊權欄位的賽事 {hit}／{len(pages)}，合計 {len(allrec)} 局")
    if A.dump:
        for r in allrec[:12]:
            print("   ", r)
        return
    if not allrec:
        print("沒有任何資料，不覆蓋既有檔案"); return
    # ── 抓取失敗不可以讓既有資料消失（2026-09-05）──────────────────────────
    # 實例：LPL Grand Finals 打到一半，wiki 已列 8 個系列、MatchSchedule 只排得到 6 個
    # ⇒ 配對率 75% < 90% 的門檻 ⇒ **整個賽事被跳過**，重跑一次就從檔案裡少掉 23 局
    # （那 23 局昨天還在）。門檻本身是對的（配錯日期比沒有更糟），但「這次抓不到」
    # 不等於「這些資料不存在」⇒ 這一輪沒產出任何一局的賽事，沿用舊檔裡的紀錄。
    # 只在**全量**跑時做（--page 是單抓，本來就只該動那一頁）。
    if not A.page:
        _out = os.path.join(ROOT, "side_sel_%d.js" % YEAR) if HIST else os.path.join(ROOT, "side_sel.js")
        try:
            if os.path.exists(_out):
                _t = io.open(_out, encoding="utf-8").read()
                # ⚠ 不能用 index("=")／rindex("=") 切：VOD 網址裡就有 `=`（?v=…&t=…）。
                # 找「= 後面緊接著 [」才是真正的賦值點（兩種輸出格式都適用）。
                _m9 = re.search(r"=\s*\[", _t)
                _prev = json.loads(_t[_m9.end() - 1:].rstrip().rstrip(";")) if _m9 else []
                _have = {r.get("ov") for r in allrec}
                _keep = [r for r in _prev if r.get("ov") and r["ov"] not in _have]
                if _keep:
                    _bys = {}
                    for r in _keep:
                        _bys[r["ov"]] = _bys.get(r["ov"], 0) + 1
                    for ov2, n2 in sorted(_bys.items()):
                        print("  ↩ %s：這次沒抓到（配對失敗／頁面沒了）→ 沿用舊檔的 %d 局" % (ov2, n2))
                    allrec += _keep
                    allrec.sort(key=lambda r: (str(r.get("d") or ""), str(r.get("ov") or ""), r.get("gi") or 0))
        except Exception as e:
            print("  ⚠ 舊檔沿用失敗（%s）：這次就只寫新抓到的" % type(e).__name__)
    if HIST:
        p = os.path.join(ROOT, "side_sel_%d.js" % YEAR)
        with io.open(p, "w", encoding="utf-8") as f:
            f.write("window.SIDE_SEL_HIST=window.SIDE_SEL_HIST||{};window.SIDE_SEL_HIST[%d]="
                    % YEAR + json.dumps(allrec, ensure_ascii=False, separators=(",", ":")) + ";")
        print(f"→ side_sel_{YEAR}.js（{len(allrec)} 局、{os.path.getsize(p)//1024} KB）")
        return
    p = os.path.join(ROOT, "side_sel.js")
    with io.open(p, "w", encoding="utf-8") as f:
        f.write("window.SIDE_SEL=" + json.dumps(allrec, ensure_ascii=False, separators=(",", ":")) + ";")
    print(f"→ side_sel.js（{len(allrec)} 局、{os.path.getsize(p)//1024} KB）")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"fetch_side_sel：執行失敗（{type(e).__name__}: {e}）")
    sys.exit(0)
