# -*- coding: utf-8 -*-
"""把 data.js 的 updated 蓋成「整條管線真正跑完的時間」。

為什麼要獨立一支（2026-07-31 使用者回報）：`updated` 原本由 fetch_data.py 寫，而它取的是
**模組載入當下**的 datetime.now()，又只是 update.bat 的第 3 步 → 每天都寫成排程啟動的 10:00，
但整條管線（版本改動／技能／道具／生涯聚合／積分逐場…）其實還要跑很久。
儀表板顯示的「資料更新時間」與快取戳記（?v=updated）因此都不準。

→ 本檔排在 update.bat 最後一行執行，只改 updated 一個欄位（years/default 不動）。
用法：python scripts/stamp_updated.py
"""
import io, json, os, sys
from datetime import datetime

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "data.js")

if not os.path.exists(P):
    print("找不到 data.js（fetch_data.py 還沒跑過？）跳過"); raise SystemExit(0)
txt = open(P, encoding="utf-8").read()
head, _, body = txt.partition("=")
if not body.strip():
    print("data.js 格式不符，跳過"); raise SystemExit(0)
m = json.loads(body.strip().rstrip(";"))
old = m.get("updated", "")
m["updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")
with open(P, "w", encoding="utf-8") as f:
    f.write("window.LOL_MANIFEST=" + json.dumps(m) + ";")
print(f"資料更新時間：{old} → {m['updated']}（管線實際完成時間）")
