# -*- coding: utf-8 -*-
"""「預測」分頁用的積分版本趨勢 → predict_sq.js（window.PRED_SQ）。

使用者 2026-10-11：世界賽版本（26.19／26.20）沒有職業比賽數據，要參考選手積分的使用情況。
做法：讀 soloq_matches/*.js（職業選手的逐場積分，只有時間戳）＋ patch_dates.js（官方版本發布日）
  新＝最近兩個版本、舊＝再前兩個版本；每個戰隊縮寫 × 英雄記 [場數, 勝場, 死亡總數]。
頁面那邊只取世界賽隊伍的縮寫加總，算「新版使用率 ÷ 舊版使用率」當英雄的版本趨勢。
掛在 run_update 的積分出裝聚合之後（逐場資料每班都會更新）。
"""
import datetime, glob, io, json, os, re, sys
from collections import defaultdict

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "predict_sq.js")
TZ = datetime.timezone(datetime.timedelta(hours=8))     # 版本日以台灣日期判斷（同 index.html patchOfTs）


def main():
    t = open(os.path.join(ROOT, "patch_dates.js"), encoding="utf-8").read()
    P = json.JSONDecoder().raw_decode(t.split("=", 1)[1].strip())[0]
    vers = sorted(P.items(), key=lambda kv: kv[1])
    today = datetime.datetime.now(TZ).strftime("%Y-%m-%d")
    vers = [v for v in vers if v[1] <= today]
    if len(vers) < 4:
        print("版本日不足 4 個，跳過"); return
    new, old = vers[-2:], vers[-4:-2]
    lo_old, lo_new = old[0][1], new[0][1]
    agg = {"new": defaultdict(lambda: defaultdict(lambda: [0, 0, 0])), "old": defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))}
    n = {"new": 0, "old": 0}
    for f in glob.glob(os.path.join(ROOT, "soloq_matches", "p*.js")):
        s = open(f, encoding="utf-8").read()
        m = re.match(r'window\.__sqLoad\("([^"]+)",(.*)\);?\s*$', s, re.S)
        if not m:
            continue
        team = m.group(1).split("|")[0]
        try:
            D = json.loads(m.group(2))
        except Exception:
            continue
        for g in D.get("matches", []):
            d = datetime.datetime.fromtimestamp(g["t"] / 1000, TZ).strftime("%Y-%m-%d")
            k = "new" if d >= lo_new else "old" if d >= lo_old else None
            if not k or not g.get("c"):
                continue
            x = agg[k][team][g["c"]]; x[0] += 1; x[1] += 1 if g.get("w") else 0; x[2] += int(g.get("de") or 0)
            n[k] += 1
    out = {"generated": datetime.datetime.now(TZ).strftime("%Y-%m-%d %H:%M"),
           "new": [v for v, _ in new], "old": [v for v, _ in old],
           "data": {k: {tm: dict(cs) for tm, cs in agg[k].items()} for k in agg}}
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("window.PRED_SQ=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print(f"新 {out['new']} {n['new']} 場／舊 {out['old']} {n['old']} 場 → {OUT} {os.path.getsize(OUT)} bytes")


if __name__ == "__main__":
    main()
