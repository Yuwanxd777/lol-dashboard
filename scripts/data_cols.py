# -*- coding: utf-8 -*-
"""data_{年}.js 的欄位白名單（2026-08-22 效能改善）。

為什麼要砍欄位：Oracle's Elixir 的原始表有 **294 欄**，但整個專案（index.html＋46 支根目錄 JS
＋80 支 scripts/*.py）真正提到的只有 **57 個欄名**。剩下 237 欄從來沒人讀，卻佔掉年度資料
六成的體積——那是全站最大的單一資產（2026 年 27.2MB，gzip 6.0MB），首載要下載它、JSON.parse 它、
還要一直放在 heap 裡。砍到 88 欄之後：原始 27.2MB→11.7MB、**gzip 6.03MB→2.39MB（省 60%）**。

白名單怎麼來的（要重算就照這三步，別憑印象加減）：
  ① index.html 裡所有 `C.<欄名>` 的靜態引用（54 欄）——欄位一律經 `C={}; HDR.forEach((h,i)=>C[h]=i)` 取索引。
  ② 唯一的動態存取 `objWin(bcol)`（首殺/首塔/首龍/首先鋒/首巴）的五個欄名＋紅方對應（10 欄）。
  ③ **藍紅成對補齊**：只要 blue_x 被用到就一定留 red_x（反之亦然）。多留的 31 欄是保險——
     很多統計是「藍方欄位算完再換算紅方」，少一邊會出現只有一半資料的怪 bug。
驗證方式：把 294 個欄名逐一當單字去掃全專案 134 個檔案，確認「出現過的 57 欄」100% 落在白名單內。

要加回某一欄時：把它加進 KEEP（成對的話兩邊都加）→ `python scripts/fetch_data.py <年> ` 重抓那一年
（或對既有檔跑 `python scripts/trim_data_cols.py`，但那只會砍不會加，欄位得重抓才回得來）。
"""

# 順序＝原始表頭的順序（保持原順序，讀取端只靠欄名查索引，但順序一致比較好 diff）
KEEP = [
    "league", "split", "date", "game", "result", "patch", "participantid",
    "blue_playername", "blue_teamname", "blue_firstPick", "blue_champion", "blue_gamelength",
    "blue_kills", "blue_deaths", "blue_assists", "blue_teamkills", "blue_teamdeaths",
    "blue_firstblood", "blue_firstbloodvictim", "blue_firstdragon", "blue_dragons",
    "blue_firstherald", "blue_heralds", "blue_void_grubs", "blue_firstbaron",
    "blue_firsttower", "blue_firstmidtower", "blue_damagetochampions", "blue_dpm",
    "blue_damageshare", "blue_damagetakenperminute", "blue_damagemitigatedperminute",
    "blue_vspm", "blue_totalgold", "blue_goldat10", "blue_golddiffat10", "blue_xpdiffat10",
    "blue_csdiffat10", "blue_killsat10", "blue_assistsat10", "blue_deathsat10",
    "blue_golddiffat15", "blue_goldat25",
    "red_playername", "red_teamname", "red_firstPick", "red_champion", "red_gamelength",
    "red_kills", "red_deaths", "red_assists", "red_teamkills", "red_teamdeaths",
    "red_firstblood", "red_firstbloodvictim", "red_firstdragon", "red_dragons",
    "red_firstherald", "red_heralds", "red_void_grubs", "red_firstbaron",
    "red_firsttower", "red_firstmidtower", "red_damagetochampions", "red_dpm",
    "red_damageshare", "red_damagetakenperminute", "red_damagemitigatedperminute",
    "red_vspm", "red_totalgold", "red_goldat10", "red_golddiffat10", "red_xpdiffat10",
    "red_csdiffat10", "red_killsat10", "red_assistsat10", "red_deathsat10",
    "red_golddiffat15", "red_goldat25",
    "blue_Lane", "red_Lane", "blue_po", "red_po",
    "banlist", "picklist", "blue_banlist", "red_banlist", "decider_winner",
]
KEEP_SET = set(KEEP)


def trim(table):
    """[表頭, 列…] → 只留白名單欄位。已經砍過的再跑一次是 no-op（冪等）。

    表頭裡沒有的白名單欄位直接略過（不同年份的表頭略有差異，例如舊年份沒有 void_grubs）。
    """
    if not table or not table[0]:
        return table
    hdr = table[0]
    idx = [i for i, h in enumerate(hdr) if h in KEEP_SET]
    if len(idx) == len(hdr):
        return table                       # 已經是精簡版
    return [[row[i] if i < len(row) else "" for i in idx] for row in table]
