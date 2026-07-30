# -*- coding: utf-8 -*-
"""LCK Rounds 分組 → lck_groups.js（使用者 2026-07-29：LCK S3 也有分組，比照 LPL）
LCK 的分組成員在賽前就定案且比賽資料常晚到 → 成員與組名都直接抓 Leaguepedia
（action=parse wikitext 的 Participants 段：===組名 Group=== 下的 |team=全名）。
輸出 window.LCK_GROUPS={年:{split:{組名:[隊縮寫...]}}}，縮寫沿用儀表板 tAb 慣例。
用法：python scripts/fetch_lck_groups.py
"""
import os, json, re, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "lck_groups.js")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

# (年, split, wiki 頁)：LCK 2026 Rounds 3-4 = 儀表板的 S3（之後有 Rounds 5 再加）
PAGES = [(2026, "S1", "LCK/2026 Season/Cup"),   # LCK Cup 分組（僅圖鑑賽事卡用）
         (2026, "S3", "LCK/2026 Season/Rounds 3-4")]

AB = {"Dplus Kia": "DK", "Gen.G": "GEN", "Hanwha Life Esports": "HLE", "KT Rolster": "KT", "T1": "T1",
      "BNK FEARX": "BFX", "DN SOOPers": "DNS", "HANJIN BRION": "BRO", "Kiwoom DRX": "DRX",
      "Nongshim RedForce": "NS"}


def fetch(page):
    u = "https://lol.fandom.com/api.php?" + urllib.parse.urlencode(
        {"action": "parse", "page": page, "prop": "wikitext", "format": "json"})
    req = urllib.request.Request(u, headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=30).read())["parse"]["wikitext"]["*"]


def groups_of(wt):
    """Participants 段：===Xxx Group=== 標題後的 |team=全名 清單"""
    out = {}
    secs = re.split(r"^===\s*([^=\n]+?)\s*===\s*$", wt, flags=re.M)
    for i in range(1, len(secs) - 1, 2):
        name = secs[i].strip()
        if not name.endswith("Group"):
            continue
        gname = name[:-5].strip()          # "Legend Group" → "Legend"
        teams = [AB.get(t.strip(), t.strip())
                 for t in re.findall(r"\{\{TeamRoster\|team=([^|\n}]+)", secs[i + 1])]
        if teams:
            out[gname] = sorted(set(teams))
    return out


def groups_from_html(page):
    """後備：TeamRoster 沒按組分段（如 Cup 頁）→ 抓渲染後 HTML，
    以「LCK Cup 2026 Group X」標題切段，段內出現的隊全名（AB 鍵）依序取 5 隊"""
    u = "https://lol.fandom.com/api.php?" + urllib.parse.urlencode(
        {"action": "parse", "page": page, "prop": "text", "format": "json"})
    req = urllib.request.Request(u, headers=UA)
    html = json.loads(urllib.request.urlopen(req, timeout=30).read())["parse"]["text"]["*"]
    # 組名白名單＝wikitext 的 display=…Group X（避免 Group Stage/Total 等標題污染）
    wt = fetch(page)
    names = re.findall(r"display=[^|\n}]*Group (\w+)", wt)
    marks = [(m.start(), m.group(1)) for m in re.finditer(r"Group (\w+)", html) if m.group(1) in names]
    ALT = {"HANJIN BRION": "BRO", "BRION": "BRO", "Kiwoom DRX": "DRX", "DRX": "DRX",
           "Nongshim": "NS", "SOOPers": "DNS", "FEARX": "BFX", "Dplus": "DK", "Gen.G": "GEN",
           "Hanwha": "HLE", "KT Rolster": "KT", "T1": "T1"}
    out = {}
    for k, (pos, g) in enumerate(marks):
        if g in out: continue
        nxt = next((p2 for p2, g2 in marks[k + 1:] if g2 != g), len(html))
        seg = html[pos:nxt]
        teams = []
        for at, ab2 in sorted((seg.find(tok), ab3) for tok, ab3 in ALT.items() if tok in seg):
            if ab2 not in teams: teams.append(ab2)
        if len(teams) >= 4:
            out[g] = sorted(teams[:5])
    return out


def main():
    data = {}
    for year, split, page in PAGES:
        try:
            gs = groups_of(fetch(page))
        except Exception as e:
            print(f"⚠ {page} 抓取失敗：{e}"); continue
        if not gs:
            try:
                gs = groups_from_html(page)
            except Exception as e:
                print(f"⚠ {page} HTML 後備也失敗：{e}")
        if gs:
            data.setdefault(str(year), {})[split] = gs
            print(f"{year} {split}: " + "、".join(f"{g}={v}" for g, v in gs.items()))
        else:
            print(f"⚠ {page} 沒解析到分組")
    if not data:
        print("沒有任何資料，不覆寫輸出檔"); return
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.LCK_GROUPS=" + json.dumps(data, ensure_ascii=False) + ";\n")
    print("→", OUT)


if __name__ == "__main__":
    main()
