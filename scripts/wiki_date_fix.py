# -*- coding: utf-8 -*-
"""Leaguepedia 自己把開賽日期打錯的局（MatchHistoryGame 文字版與 Cargo 的 ScoreboardPlayers 是同一個錯）。

兩支共用這一份（2026-09-21 精進迴圈 #184）：
  fetch_wiki_mh.to_csv       —— 重建 wikifill 時把那局搬到正確日期
  fetch_wiki_stats.year_rows —— 逐選手數據也搬過去（merge_stats 的配對鍵含日期，只修一邊等於兩邊都配不到）
刻意做成**沒有任何副作用的獨立模組**：fetch_wiki_mh 在 import 時會重包 sys.stdout，
fetch_wiki_stats 若為了這張表去 import 它，把 stdout 換成 StringIO 的測試會當場炸掉。

以「賽事名＋原始時間到分＋兩隊」（fetch_wiki_mh）／「GameId＋原始時間到分」（fetch_wiki_stats）鎖定一局，
都對上才改——上游哪天自己修好了（原始時間不再是 was），這一筆就自動失效，不會把對的改錯。
測試：python scripts/wiki_date_fix_test.py
"""

WIKI_DATE_FIX = [
    # GPL 2014 冬季 ahq eSports Club vs Saigon Jokers：wiki 寫 2013-01-06 12:00，
    # 但 GameId 是 Week 2_2_1，同一週其他局全在 2013-11-06～11-08（Week 2_1＝11-06 11:00）⇒ 月份打錯一位。
    # 不修的話那局 6 列排在 data_2014 全年最前、兩隊選手生涯的「首次出場」變成 2013-01-06，
    # 逐選手數據也因為落在 wikistats_2014 的月份範圍（前一年 10 月起）外而補不到（10 格 kills）。
    # ScoreboardGames 那局的 Patch 本來就是空的，所以版本（games_patch）那條路不必跟著修。
    {"tour": "GPL 2014 Winter", "gid": "2014 GPL Winter_Week 2_2_1",
     "was": "2013-01-06 12:00", "fix": "2013-11-06 12:00",
     "teams": ("ahq eSports Club", "Saigon Jokers")},
]
