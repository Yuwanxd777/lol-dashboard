# -*- coding: utf-8 -*-
"""抓「刷野速度」GS（Jungle Clear Compilation）→ 產出 jungle.js（圖鑑・刷野速度分區用）。
依賽季分頁抓：S16/2026、S15/2025、S14/2024，輸出成 {年份:[...]}，網頁依目前年份顯示對應賽季。
來源試算表（公開分享）：
  https://docs.google.com/spreadsheets/d/1jE8bnlnIJnmWv9pnVW9veMKRXJNaaJf5tneQB3xUkbI/edit

備註超連結：原作者常把備註某段字（如「QWW ver」）設成 YT 連結。CSV/gviz 拿不到這種 rich-text 局部連結，
需 Google Sheets API v4（含 textFormatRuns/hyperlink）。若環境變數 GS_API_KEY 有設 → 走 API 版（帶連結）；
否則自動退回公開 CSV（無連結）。抓不到（斷網/權限/改名）→ 保留舊 jungle.js、不中斷每日更新。"""
import io, sys, json, re, csv, os, urllib.request, urllib.parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT    = os.path.join(HERE, "jungle.js")
SHEET  = "1jE8bnlnIJnmWv9pnVW9veMKRXJNaaJf5tneQB3xUkbI"
KEY    = os.environ.get("GS_API_KEY", "").strip()
# 年份 → 該賽季分頁（優先用 tab 名稱，沒有就用 gid）
SEASONS = {
    "2026": {"tab": "Jungle clear S16/2026", "gid": None},
    "2025": {"tab": None, "gid": "0"},
    "2024": {"tab": None, "gid": "112351531"},
}
META = {"src": "Jungle Clear Compilation S14–S16",
        "url": f"https://docs.google.com/spreadsheets/d/{SHEET}/edit",
        "discord": "https://discord.com/invite/c9yzQWtYy2"}

FIX = {"Bel'Veth":"Belveth","Cho'Gath":"Chogath","Kha'Zix":"Khazix","Kog'Maw":"KogMaw","Rek'Sai":"RekSai",
       "Nunu & Willump":"Nunu","Nunu":"Nunu","Wukong":"MonkeyKing","Jarvan IV":"JarvanIV","Lee Sin":"LeeSin",
       "Master Yi":"MasterYi","Xin Zhao":"XinZhao","Renata Glasc":"Renata","Aurelion Sol":"AurelionSol",
       "K'Sante":"KSante","Tahm Kench":"TahmKench","Dr. Mundo":"DrMundo","Miss Fortune":"MissFortune",
       "LeBlanc":"Leblanc","Vel'Koz":"Velkoz"}
def cid(name): return FIX.get(name, name.replace("'", "").replace(" ", "").replace(".", ""))

def _get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=40).read()

# ---- 公開 CSV（無連結）----
def fetch_csv(tab, gid):
    if tab:
        url = f"https://docs.google.com/spreadsheets/d/{SHEET}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(tab)}"
    else:
        url = f"https://docs.google.com/spreadsheets/d/{SHEET}/export?format=csv&gid={gid}"
    rows = list(csv.reader(io.StringIO(_get(url).decode("utf-8", "replace"))))
    return rows, None  # link_rows=None

# ---- Sheets API v4（含備註超連結）----
def api_meta():
    url = (f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET}"
           f"?fields=sheets.properties(sheetId,title)&key={KEY}")
    data = json.loads(_get(url))
    return {str(s["properties"]["sheetId"]): s["properties"]["title"] for s in data.get("sheets", [])}

def _cell_links(cell):
    fv = cell.get("formattedValue", "") or ""
    out = []
    runs = cell.get("textFormatRuns")
    if runs and fv:
        for j, run in enumerate(runs):
            start = run.get("startIndex", 0)
            end = runs[j + 1]["startIndex"] if j + 1 < len(runs) else len(fv)
            uri = ((run.get("format") or {}).get("link") or {}).get("uri")
            if uri:
                txt = fv[start:end].strip().rstrip(" .,")  # 去尾端標點，避免備註清標點後與連結文字對不上
                if txt:
                    out.append({"text": txt, "uri": uri})
    elif cell.get("hyperlink") and fv.strip():
        out.append({"text": fv.strip().rstrip(" .,"), "uri": cell["hyperlink"]})
    return out

def fetch_api(title):
    rng = urllib.parse.quote("'" + title.replace("'", "''") + "'")
    fields = "sheets.data.rowData.values(formattedValue,hyperlink,textFormatRuns(startIndex,format(link(uri))))"
    url = (f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET}"
           f"?includeGridData=true&ranges={rng}&fields={urllib.parse.quote(fields)}&key={KEY}")
    data = json.loads(_get(url))
    row_data = (((data.get("sheets") or [{}])[0].get("data") or [{}])[0].get("rowData")) or []
    text_rows, link_rows = [], []
    for row in row_data:
        cells = row.get("values", []) or []
        trow = [c.get("formattedValue", "") or "" for c in cells]
        lrow = {}
        for ci, c in enumerate(cells):
            lk = _cell_links(c)
            if lk:
                lrow[ci] = lk
        text_rows.append(trow)
        link_rows.append(lrow)
    return text_rows, link_rows

def parse_season(rows, link_rows=None):
    data, order, section = {}, [], None
    for ri, r in enumerate(rows):
        r = [(x or "").strip() for x in r] + [""] * 9
        links_at = (link_rows[ri] if (link_rows and ri < len(link_rows)) else {}) or {}
        c0 = r[0]
        if re.match(r"(Meta|Off-Meta|Non-Meta|Outdated|Helpful|Appendix)", c0, re.I) and not r[4]:
            section = c0.rstrip(":").strip(); continue
        if section and re.match(r"(Outdated|Helpful|Appendix)", section, re.I):
            continue
        if c0 in ("", "Champion") or not re.match(r"\d\d?:\d\d", r[4] or ""):
            continue
        champ, patch, camps, smite, time_, path, link, player, notes = r[:9]
        if not re.match(r"\d", camps or ""): continue
        note_links = links_at.get(8, [])  # 備註欄＝索引 8
        # 技能升級序：Notes 中「獨立的大寫 QWER 2~4 字」token（S16 在開頭、S15/S14 常在結尾）
        m = re.search(r"(?<![A-Za-z])([QWER]{2,4})(?![A-Za-z])", notes)
        sk = m.group(1) if m else ""
        note = notes
        # 只有在 sk 不是某段超連結文字的一部分時才從備註移除（避免把「QWW ver」這種連結字拆掉）
        sk_in_link = any(sk and sk in lk["text"] for lk in note_links)
        if sk and not sk_in_link:
            stripped = re.sub(r"(?<![A-Za-z])" + sk + r"(?![A-Za-z])", "", notes, count=1)
            stripped = re.sub(r"\s*,\s*,\s*", ", ", stripped).strip(" ,.")
            # 移除 sk 後若還保得住所有連結文字才採用；否則保留原文（免得把連結那段字拆掉→連結遺失）
            if all(lk["text"] in stripped for lk in note_links):
                note = stripped
        i = cid(champ)
        if i not in data:
            data[i] = {"c": champ, "id": i, "cat": section or "Meta Junglers", "clears": []}
            order.append(i)
        clear = {"patch": patch, "camps": camps, "smite": smite, "time": time_,
                 "path": path.replace("->", "→").replace(">", "→"),
                 "link": link, "player": player, "sk": sk, "note": note}
        # 只保留備註文字仍找得到的連結（避免 sk 被移除後 text 對不上）
        keep = [{"text": lk["text"], "uri": lk["uri"]} for lk in note_links if lk["text"] in note]
        if keep:
            clear["noteLinks"] = keep
        data[i]["clears"].append(clear)
    def sec(t):
        m = re.match(r"(\d+):(\d+)", t); return int(m.group(1)) * 60 + int(m.group(2)) if m else 999
    for i in data: data[i]["clears"].sort(key=lambda x: sec(x["time"]))
    return [data[i] for i in order]

def main():
    mode = "Sheets API（含備註連結）" if KEY else "公開 CSV（無連結，未設 GS_API_KEY）"
    print(f"  來源模式：{mode}")
    gid2title = {}
    if KEY:
        try:
            gid2title = api_meta()
        except Exception as e:
            print(f"  ⚠ 取分頁清單失敗 {e}，本次退回 CSV")
    out = {}
    for year, cfg in SEASONS.items():
        try:
            if KEY:
                title = cfg["tab"] or gid2title.get(str(cfg["gid"]))
                if not title:
                    raise RuntimeError(f"找不到 gid={cfg['gid']} 的分頁名稱")
                rows, link_rows = fetch_api(title)
            else:
                rows, link_rows = fetch_csv(cfg["tab"], cfg["gid"])
            season = parse_season(rows, link_rows)
            if season:
                out[year] = season
                nlinks = sum(len(cl.get("noteLinks", [])) for x in season for cl in x["clears"])
                print(f"  {year}: {len(season)} 隻英雄、{sum(len(x['clears']) for x in season)} 種清野、備註連結 {nlinks} 條")
            else:
                print(f"  ⚠ {year}: 解析 0 筆（分頁結構可能改了），略過")
        except Exception as e:
            print(f"  ⚠ {year}: 抓取失敗 {e}，略過")
    if not out:
        print("⚠ 所有賽季都抓不到，保留舊 jungle.js"); return
    js = ("window.JUNGLE_CLEARS=" + json.dumps(out, ensure_ascii=False, separators=(",", ":"))
          + ";\nwindow.JUNGLE_META=" + json.dumps(META, ensure_ascii=False) + ";")
    open(OUT, "w", encoding="utf-8").write(js)
    print(f"✅ jungle.js：{', '.join(sorted(out))} 共 {sum(len(v) for v in out.values())} 筆英雄卡")

if __name__ == "__main__":
    main()
