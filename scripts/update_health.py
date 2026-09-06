# -*- coding: utf-8 -*-
"""每日資料更新（10:00／22:00 publish.bat）的健檢——線 3「準確度與速度」的固定尺（2026-09-06）。

讀最近一次 update_log.txt 與產出的資料檔，印一份短報告，並把數字存進 autopilot/UPDATE_BASELINE.json
供下一次比對。**只讀**（只寫 UPDATE_BASELINE.json）。

看什麼：
  速度  ‧ run_update 開始時間、有沒有退回循序、各階段並行是否炸掉（traceback）
        ‧ 最久的 8 步、非零離開碼的步驟、管線總時長（run_update 開始 → 「資料更新時間」那行）
  準確  ‧ data_YYYY.js 列數不可比上次少（縮水＝來源掛了或過濾壞了）
        ‧ soloq.js 選手數／有排名數、side_sel.js 局數、lint_text 錯誤級、check_player_dup 可疑數
        ‧ preflight 有沒有過、有沒有 push

用法：python scripts/update_health.py           # 報告＋更新基準
      python scripts/update_health.py --no-save # 只報告
"""
import glob
import io
import json
import os
import re
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "update_log.txt")
BASE = os.path.join(ROOT, "autopilot", "UPDATE_BASELINE.json")


def js_obj(path):
    h = io.open(path, encoding="utf-8", errors="replace").read()
    m = re.search(r"=\s*(\{.*\}|\[.*\]);?\s*$", h, re.S)
    return json.loads(m.group(1)) if m else None


CONSOLE = os.path.join(ROOT, "update_console.txt")   # run_update 的 console（摘要＋traceback）；2026-09-06 起與 update_log 分開


def parse_log():
    if not os.path.exists(LOG):
        return None
    t = io.open(LOG, encoding="utf-8", errors="replace").read()
    # 2026-09-06 10:00 的教訓：update.bat 不能把 run_update 的輸出導進它自己會開的 update_log.txt
    # （Windows 檔案鎖 → PermissionError → 整條沒跑）。console 另存一檔，健檢兩個都看。
    if os.path.exists(CONSOLE):
        t += "\n" + io.open(CONSOLE, encoding="utf-8", errors="replace").read()
    r = {"runs": re.findall(r"==== run_update (\S+ \S+)（並行 (\d+)）====", t),
         "fallback_whole": t.count("run_update.py failed - falling back to sequential"),
         "stage_fallback": re.findall(r"⚠ 【(.+?)】並行執行炸掉", t),
         "tracebacks": t.count("Traceback (most recent call last)"),
         "steps": [(n, float(s), int(c)) for n, s, c in re.findall(r"---- (\S+)（([\d.]+)s，exit (-?\d+)）----", t)],
         "preflight_ok": "守門通過" in t, "preflight_fail": "PREFLIGHT FAILED" in t,
         "pushed": bool(re.search(r"\n\s*[0-9a-f]{7,}\.\.[0-9a-f]{7,}\s+\S+ -> \S+", t)) or "-> main" in t,
         "lint_err": None, "dup": None, "done_at": None, "start_at": None}
    m = re.search(r"資料更新時間：.*?→ (\d{4}-\d{2}-\d{2} \d{2}:\d{2})", t)
    if m:
        r["done_at"] = m.group(1)
    m = re.search(r"==== (\d{4}/\d{1,2}/\d{1,2}) .*?(\d{1,2}:\d{2}):\d{2}", t)
    if r["runs"]:
        r["start_at"] = r["runs"][0][0]
    # lint_text 的摘要行長這樣：「文本體檢：掃描 81574 條字串 → 錯誤 0、提醒 7284」
    m = re.search(r"文本體檢：.*?錯誤 (\d+)、提醒 (\d+)", t)
    if m:
        r["lint_err"] = int(m.group(1)); r["lint_warn"] = int(m.group(2))
    m = re.search(r"未審定的可疑同名 (\d+)", t)
    if m:
        r["dup"] = int(m.group(1))
    return r


def data_counts():
    out = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "data_20*.js")))[-3:]:
        try:
            d = js_obj(f)
            out[os.path.basename(f)] = len(d["tabs"]["RAW_DATA"])
        except Exception:
            out[os.path.basename(f)] = None
    try:
        s = js_obj(os.path.join(ROOT, "soloq.js"))
        ps = s.get("players", [])
        out["soloq.players"] = len(ps)
        out["soloq.found"] = sum(1 for p in ps if p.get("found"))
    except Exception:
        out["soloq.players"] = out["soloq.found"] = None
    try:
        out["side_sel.games"] = len(js_obj(os.path.join(ROOT, "side_sel.js")) or [])
    except Exception:
        out["side_sel.games"] = None
    try:
        out["soloq_matches.files"] = len(glob.glob(os.path.join(ROOT, "soloq_matches", "*.js")))
    except Exception:
        out["soloq_matches.files"] = None
    return out


def main():
    lg = parse_log()
    dc = data_counts()
    prev = {}
    try:
        prev = json.load(io.open(BASE, encoding="utf-8"))
    except Exception:
        pass
    print("═══ 資料更新健檢 %s ═══" % time.strftime("%Y-%m-%d %H:%M"))
    bad = []
    if lg:
        print("run_update：%s" % ("、".join("%s（並行 %s）" % x for x in lg["runs"]) or "（日誌裡沒有 run_update）"))
        if lg["fallback_whole"]:
            bad.append("整條退回循序 %d 次" % lg["fallback_whole"])
        if lg["stage_fallback"]:
            bad.append("階段並行炸掉：" + "、".join(lg["stage_fallback"]))
        if lg["tracebacks"]:
            bad.append("日誌裡 %d 個 Traceback" % lg["tracebacks"])
        st = lg["steps"]
        if st:
            tot = sum(s for _, s, _ in st)
            print("步驟 %d 個、相加 %.1f 分鐘；最久的 8 步：" % (len(st), tot / 60))
            for n, s, c in sorted(st, key=lambda x: -x[1])[:8]:
                print("   %-28s %7.1fs%s" % (n, s, "" if c == 0 else "  ⚠ exit %d" % c))
            nz = [(n, c) for n, _, c in st if c != 0]
            if nz:
                bad.append("非零離開碼：" + "、".join("%s(%d)" % x for x in nz))
        print("守門：%s／push：%s／lint 錯誤級：%s／可疑同名：%s" % (
            "✓" if lg["preflight_ok"] else ("✗ FAILED" if lg["preflight_fail"] else "？"),
            "✓" if lg["pushed"] else "？", lg["lint_err"], lg["dup"]))
        if lg["lint_err"]:
            bad.append("lint_text 錯誤級 %d（應為 0）" % lg["lint_err"])
        if lg["preflight_fail"]:
            bad.append("preflight 失敗、沒有 push")
    else:
        print("（找不到 update_log.txt）")
    print("資料量：")
    for k, v in dc.items():
        pv = prev.get("counts", {}).get(k)
        flag = ""
        if v is None:
            flag = "  ⚠ 讀不到"; bad.append("%s 讀不到" % k)
        elif pv is not None and v < pv:
            flag = "  ⚠ 比上次少（%d → %d）" % (pv, v)
            if k.startswith("data_") or k == "side_sel.games":
                bad.append("%s 縮水 %d → %d" % (k, pv, v))
        elif pv is not None:
            flag = "  （上次 %d）" % pv
        print("   %-22s %s%s" % (k, v, flag))
    print("")
    print("結論：" + ("✓ 沒有異常" if not bad else "⚠ " + "；".join(bad)))
    if "--no-save" not in sys.argv:
        os.makedirs(os.path.dirname(BASE), exist_ok=True)
        json.dump({"at": time.strftime("%Y-%m-%d %H:%M"), "counts": dc,
                   "log": {k: v for k, v in (lg or {}).items() if k != "steps"},
                   "bad": bad}, io.open(BASE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("（基準已存 autopilot/UPDATE_BASELINE.json）")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
