# -*- coding: utf-8 -*-
"""把「資料時間」蓋成整條管線真正跑完的時間（update.bat 最後一行）。

為什麼要獨立一支（2026-07-31 使用者回報）：時間戳原本由 fetch_data.py 寫，取的是**模組載入當下**
的 datetime.now()，而它只是 update.bat 的第 3 步 → 每天都寫成排程啟動的整點 10:00，
但整條管線（版本改動／技能／道具／生涯聚合／積分逐場…）其實還要再跑一個多小時。

**兩個時間戳都要蓋（2026-08-02 補，之前只蓋了 data.js）**——儀表板有兩處在顯示：
  ①頁首「資料時間」          → data.js 的 updated
  ②總覽近況帶「🕒 資料更新」 → data_{年}.js 的 fetched_at（＝前端的 D.fetched_at，
                              AI 問答的資料範圍與英雄Tier 重產指紋也吃這個）
只蓋 ①的話，總覽那行永遠停在 10:00。

fetch_data.py 那邊已改成 keep_stamp()＝沿用磁碟上的舊值，所以管線跑到一半時儀表板顯示的是
「上一輪完成時間」，不會出現半真半假的整點；管線中途失敗也不會假裝更新過。

年份檔要不要蓋的判準＝**mtime 比上一輪完成時間新**（＝這輪重寫過）。歷史年份沒重抓就不動，
它的 fetched_at 保留當初抓取的日期才有意義（2013 資料就是那天抓的）。

用法：python scripts/stamp_updated.py
"""
import io, os, re, sys
from datetime import datetime, timedelta

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MF = os.path.join(ROOT, "data.js")
DDIR = os.path.join(ROOT, "data")
FMT = "%Y-%m-%d %H:%M"


def restamp(path, field, new):
    """只換掉檔頭那一個時間戳；21MB 的年份檔不做 JSON 來回轉換（會重排格式、也慢）。

    鐵則：錨定檔頭 300 字元＋count=1＋比對成功才寫，絕不對全文做字串取代
    （全文取代把資料檔整份弄壞的前例見 fix_text_data.py 檔頭）。寫入走 .tmp + os.replace，
    中途斷掉不會留下半截檔案。
    → 回傳舊值；沒比對到回 None。
    """
    with io.open(path, encoding="utf-8") as f:
        txt = f.read()
    head, rest = txt[:300], txt[300:]
    pat = r'("%s"\s*:\s*")[^"]*(")' % field
    m = re.search(pat, head)
    if not m:
        print(f"  ⚠ {os.path.basename(path)}：檔頭找不到 {field} 欄位，跳過（格式可能改了）")
        return None
    old = re.search(r'"%s"\s*:\s*"([^"]*)"' % field, head).group(1)
    new_head = re.sub(pat, lambda g: g.group(1) + new + g.group(2), head, count=1)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write(new_head + rest)
    os.replace(tmp, path)
    return old


def main():
    if not os.path.exists(MF):
        print("找不到 data.js（fetch_data.py 還沒跑過？）跳過")
        return
    new = datetime.now().strftime(FMT)

    # ①先讀上一輪完成時間（拿來判斷哪些年份檔是這輪重寫的），再蓋
    with io.open(MF, encoding="utf-8") as f:
        m = re.search(r'"updated"\s*:\s*"([^"]*)"', f.read(300))
    prev_s = m.group(1) if m else ""
    try:
        prev = datetime.strptime(prev_s, FMT)
    except ValueError:
        prev = datetime.now() - timedelta(hours=12)   # 讀不到就退回半天（排程間隔 10:00／22:00）
        print(f"  ⚠ data.js 的 updated 讀不到（{prev_s!r}），年份檔改用「12 小時內重寫過」判斷")

    old = restamp(MF, "updated", new)
    if old is not None:
        print(f"資料更新時間：{old} → {new}（管線實際完成時間）")

    # ②這輪重寫過的年份檔：fetched_at 一起對齊
    done = []
    for fn in sorted(os.listdir(DDIR)):
        if not re.match(r"data_\d{4}\.js$", fn):
            continue
        p = os.path.join(DDIR, fn)
        if datetime.fromtimestamp(os.path.getmtime(p)) <= prev:
            continue                        # 這輪沒重寫（歷史年份）→ 保留原本的抓取日期
        if restamp(p, "fetched_at", new) is not None:
            done.append(fn[5:9])
    print(f"年份檔 fetched_at 對齊：{'、'.join(done) if done else '（這輪沒有年份檔被重寫）'}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:                   # 絕不擋更新鏈（後面還有 check_keys、publish）
        print(f"stamp_updated：執行失敗（{type(e).__name__}: {e}）")
    sys.exit(0)
