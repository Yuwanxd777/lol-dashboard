# -*- coding: utf-8 -*-
"""把既有的 data_{年}.js 砍成白名單欄位（見 scripts/data_cols.py）。

為什麼要獨立一支：`fetch_data.py` 寫檔時已經會過濾，但歷史年份的檔案是以前產的（2013~2025 共 13 個檔、
合計 400MB），重抓一次要下載幾百 MB 的 CSV，沒必要——直接就地砍即可。冪等，重跑無害。
補檔腳本（fill_*.py／dedup_pb_copies.py）是「讀既有檔→改→寫回」，砍過之後它們自然維持精簡版。

用法：
  python scripts/trim_data_cols.py            # 只看會省多少，不寫入
  python scripts/trim_data_cols.py --apply    # 真的寫回
  python scripts/trim_data_cols.py --apply 2026
"""
import glob, io, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from data_cols import trim, KEEP_SET

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

apply_ = "--apply" in sys.argv
years = [a for a in sys.argv[1:] if a.isdigit()]
files = sorted(glob.glob(os.path.join(ROOT, "data", "data_*.js")))
if years:
    files = [f for f in files if any(y in os.path.basename(f) for y in years)]

tot_before = tot_after = 0
for f in files:
    s = io.open(f, encoding="utf-8").read()
    i = s.index("=")
    d = json.loads(s[i + 1:].strip().rstrip(";"))
    tb = d["tabs"]["RAW_DATA"]
    n0 = len(tb[0])
    tb2 = trim(tb)
    n1 = len(tb2[0])
    if n1 == n0:
        print(f"  {os.path.basename(f):<18} {n0} 欄（已是精簡版）")
        tot_before += len(s); tot_after += len(s)
        continue
    d["tabs"]["RAW_DATA"] = tb2
    out = "window.LOL_DATA=" + json.dumps(d, ensure_ascii=False, separators=(",", ":")) + ";"
    tot_before += len(s); tot_after += len(out)
    print(f"  {os.path.basename(f):<18} {n0} → {n1} 欄　{len(s)/1e6:6.1f}MB → {len(out)/1e6:5.1f}MB")
    if apply_:
        io.open(f, "w", encoding="utf-8", newline="\n").write(out)
print(f"\n合計 {tot_before/1e6:.0f}MB → {tot_after/1e6:.0f}MB"
      + ("（已寫回）" if apply_ else "（dry-run，加 --apply 才寫入）"))
