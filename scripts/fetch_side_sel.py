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

import fetch_wiki_mh as MH          # 共用 opener（先拿 cookie，否則 302→403）與 UA
import fetch_wiki_stats as WS       # 共用 Special:CargoExport 通道（不吃 Cargo API 限流）

TXT = lambda s: re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()
KEYS = ["Blue", "Red", "1st Sel", "Side Sel", "Pick Sel"]


def ov_pages():
    """2026 有比賽的賽事總覽頁（用 ScoreboardGames 的 OverviewPage 去重）。

    不寫死清單：新賽段開打就自動出現，也不會抓到還沒打的頁。
    """
    p = {"tables": "ScoreboardGames=SG", "fields": "SG.OverviewPage=ov",
         "where": 'SG.DateTime_UTC >= "%d-01-01" AND SG.DateTime_UTC < "%d-01-01"' % (YEAR, YEAR + 1),
         "group_by": "SG.OverviewPage", "format": "json", "limit": "500"}
    url = WS.FORM + "?" + urllib.parse.urlencode(p)
    raw = WS.opener().open(urllib.request.Request(url, headers=WS.UA), timeout=120).read().decode("utf-8", "replace")
    if raw.lstrip()[:1] not in "[{":
        print("  ⚠ 賽事頁清單抓取失敗：" + raw[:120]); return []
    return sorted({r.get("ov") for r in json.loads(raw) if r.get("ov")})


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
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)
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
                if len(idx) < len(KEYS):
                    print(f"    ⚠ {ov}：表頭少了 {set(KEYS)-set(idx)}，跳過"); return []
            continue
        # 巢狀表是「每週一張」，每張都自帶表頭 → 後面還會再遇到表頭列，不能當成資料
        #（會產出 blue='Team 1' red='Team 2' 這種垃圾列）。
        if txt[0] in ("Team 1", "Blue") or any(t.startswith(("Side Sel", "1st Sel", "Pick Sel")) for t in txt):
            continue
        base = idx["Blue"]
        is_match = "logo std" in (cells[0] if cells else "")   # 系列層級列＝第一格是隊伍 logo
        if is_match:
            team = lambda i: (re.search(r'alt="([^"]+?)logo std"', cells[i]) or [None, ""])[1].strip()
            # 系列一律先進 out（即使一局都沒收）：out 的順序要與賽程清單逐項對齊，
            # 少一個未打的系列就會整串錯位。
            cur = {"t1": team(0), "t2": team(1), "score": txt[2] if len(txt) > 2 else "", "n": 0, "games": []}
            out.append(cur)
            g = lambda k: txt[idx[k]] if len(txt) > idx[k] else ""
        elif cur and len(cells) >= len(KEYS) - 1:
            g = lambda k: txt[idx[k] - base] if len(txt) > idx[k] - base else ""
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
        if not side:
            cur["n"] -= 1
            continue
        cur["games"].append({"gi": cur["n"], "blue": bl, "red": rd, "ss": side,
                             "first_sel": g("1st Sel"), "pick_sel": g("Pick Sel")})
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", action="append", default=[], help="只抓指定 OverviewPage（可重複）")
    ap.add_argument("--force", action="store_true", help="重抓頁面（不吃快取）")
    ap.add_argument("--dump", action="store_true", help="只印不寫檔")
    A = ap.parse_args()

    pages = A.page or ov_pages()
    print(f"賽事頁 {len(pages)} 個")
    allrec, hit = [], 0
    for ov in pages:
        h = page_html(ov, force=A.force)
        if not h:
            continue
        sers = parse(ov, h)
        if not sers:
            continue
        sc = sched(ov)
        # 逐場對齊＋用比分驗證：對不上就整個賽事不採用（寧可沒有，也不要掛錯日期）
        # 只拿**已打完**的場次驗證：還沒打的頁面寫 TBD、賽程寫 None - None，本來就對不上，
        # 把它們算進去會讓對齊率永遠不及格（LCP 實測 25 場裡 14 場未打）。
        done = [i for i, s in enumerate(sers) if re.match(r"^\d+\s*-\s*\d+$", s["score"] or "")]
        ok = sum(1 for i in done if i < len(sc) and sers[i]["score"] == sc[i][3])
        if len(sc) < len(sers) or (done and ok < len(done) * 0.9):
            print(f"  ⚠ {ov}：賽程對齊失敗（{ok}/{len(done)} 場比分吻合、清單 {len(sc)} 場）→ 跳過")
            continue
        hit += 1
        n = 0
        for i, s in enumerate(sers):
            d, t1, t2, _ = sc[i]
            for g in s["games"]:
                allrec.append({"d": d, "t1": t1, "t2": t2, "gi": g["gi"], "ss": g["ss"],
                               "blue": g["blue"], "red": g["red"],
                               "fs": g["first_sel"], "ps": g["pick_sel"], "ov": ov})
                n += 1
        print(f"  ✓ {ov}：{len(sers)} 場 / {n} 局")
    print(f"有選邊權欄位的賽事 {hit}／{len(pages)}，合計 {len(allrec)} 局")
    if A.dump:
        for r in allrec[:12]:
            print("   ", r)
        return
    if not allrec:
        print("沒有任何資料，不覆蓋既有檔案"); return
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
