# -*- coding: utf-8 -*-
"""版本發布日 → patch_dates.js（前端用「日期回推版本」）

來源：csv_cache/patch_dates.json，由 build_soloq_builds.py 的 official_patch_dates()
從 Riot 官方 patch notes 標籤頁抓下來並快取（各版公告發布日）。這裡只做「快取 → js」，
不重新連線，所以隨時可跑、不會有網路副作用。

用途：積分（單雙排）的逐場資料每場只有時間戳、沒有版本欄位，英雄詳情頁的出場紀錄
要顯示「版本」就得用發布日回推。職業賽那邊資料本身就有 patch 欄，不需要這個。

用法：python scripts\\build_patch_dates.py
"""
import io, os, sys, json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "csv_cache", "patch_dates.json")
OUT = os.path.join(ROOT, "patch_dates.js")


def patch_key(p):
    """'26.9' < '26.10'：版本字串轉可排序的數值鍵"""
    try:
        a, b = str(p).split(".")[:2]
        return (int(a), int(b))
    except Exception:
        return (0, 0)


def main():
    if not os.path.exists(SRC):
        print(f"找不到 {SRC}；先跑 build_soloq_builds.py 讓它抓官方版本日並快取")
        return 1
    raw = json.load(open(SRC, encoding="utf-8"))
    # 只留「版本號 → YYYY-MM-DD」格式正確的，順便依版本排序讓輸出檔穩定（diff 才乾淨）
    data = {}
    for k, v in raw.items():
        if not isinstance(v, str) or len(v) != 10 or v[4] != "-" or v[7] != "-":
            continue
        if patch_key(k) == (0, 0):
            continue
        data[k] = v
    if not data:
        print("patch_dates.json 沒有可用的版本日期")
        return 1
    ordered = {k: data[k] for k in sorted(data, key=patch_key)}
    body = json.dumps(ordered, ensure_ascii=False, separators=(",", ":"))
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("window.PATCH_DATES=" + body + ";\n")
    lo, hi = min(ordered, key=patch_key), max(ordered, key=patch_key)
    print(f"寫出 {os.path.basename(OUT)}：{len(ordered)} 個版本（{lo} {ordered[lo]} ~ {hi} {ordered[hi]}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
