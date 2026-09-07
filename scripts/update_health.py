# -*- coding: utf-8 -*-
"""每日資料更新（10:00／22:00 publish.bat）的健檢——線 3「準確度與速度」的固定尺（2026-09-06）。

讀最近一次 update_log.txt 與產出的資料檔，印一份短報告，並把數字存進 autopilot/UPDATE_BASELINE.json
供下一次比對。**只讀**（只寫 UPDATE_BASELINE.json）。

看什麼：
  有跑  ‧ **這份日誌是不是這一班寫的**（2026-09-07 #47）——日誌裡有沒有 run_update、有沒有步驟、
          run 的開始時間距現在多久。publish.bat 呼叫時帶 --from-publish 才判新鮮度（手動跑只顯示）
  速度  ‧ run_update 開始時間、有沒有退回循序、各階段並行是否炸掉（traceback）
        ‧ 最久的 8 步、非零離開碼的步驟、管線總時長（run_update 開始 → 「資料更新時間」那行）
  準確  ‧ data_YYYY.js（**全部 14 年**）列數不可比基準少（縮水＝來源掛了或過濾壞了）
        ‧ 基準是「已知良好的高水位」：縮水不會寫回基準，會一直報到 --accept 認可為止
        ‧ soloq.js 選手數／有排名數、side_sel.js 局數、lint_text 錯誤級、check_player_dup 可疑數
        ‧ preflight 有沒有過、有沒有 push

用法：python scripts/update_health.py           # 報告＋更新基準
      python scripts/update_health.py --no-save # 只報告
      python scripts/update_health.py --accept  # 認可縮水（資料真的變少時才用），把現值寫成新基準
      python scripts/update_health.py --from-publish   # publish.bat 用：日誌不新鮮＝異常
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


# ── 「這一班到底有沒有真的跑」（純函式；scripts/update_health_test.py 在測）──────────
# 正常一班：10:00 開始、25~30 分鐘跑完，最壞那次退回循序 94 分鐘；健檢緊接在 push 之後跑。
# 失效那一班：日誌是上一班寫的 ⇒ 至少差 12 小時（兩班間隔）。240 分鐘落在中間，兩邊都有很大餘裕。
FRESH_MIN = 240


def log_age_min(start_at, log_mtime, now_ts):
    """日誌有多舊（分鐘）。優先用日誌裡 run_update 的開始時間，沒有才退回檔案 mtime。

    為什麼優先用內容而不是 mtime：publish.bat 在健檢跑完後會 `type` 健檢結論折進 update_log.txt，
    mtime 因此永遠是「剛剛」；而且日誌裡的時間才是這一班真的開始跑的時間。
    回 None＝兩個都沒有（檔案不存在）。時鐘漂移造成的負值夾成 0。
    """
    ts = None
    if start_at:
        try:
            ts = time.mktime(time.strptime(start_at, "%Y-%m-%d %H:%M:%S"))
        except ValueError:
            ts = None
    if ts is None:
        ts = log_mtime
    if ts is None:
        return None
    return max(0.0, (now_ts - ts) / 60.0)


def run_problems(lg, age_min, fresh_min):
    """這一班的更新到底有沒有跑起來 → bad 訊息 list（fresh_min=None＝手動跑，不判新鮮度）。

    2026-09-07 #47 補的洞：健檢只分析日誌裡「有什麼」，從來不問「這份日誌是不是這一班寫的」。
    `update.bat` 第一件事就是覆寫 update_log.txt，所以只要它沒跑到（publish.bat 被改壞、
    call 被跳過、cd /d 失敗），健檢讀到的是**上一班的完整日誌**：42 步全 exit 0、守門通過、
    資料量也沒變（因為根本沒更新）⇒ 結論「✓ 沒有異常」、不留 HEALTH_ALERT.txt。
    那正是 2026-09-06 10:00「一步都沒跑還照樣 push」的重演，而健檢就是為了抓它才做的。
    publish.bat 的註解本來就寫著「exit 1 = ... / no run at all」，程式碼裡卻沒有這條。
    """
    if lg is None:
        return ["找不到 update_log.txt（這一班沒有寫出任何日誌）"]
    out = []
    if not lg.get("runs"):
        out.append("日誌裡沒有 run_update（這一班的更新根本沒開始跑）")
    elif not lg.get("steps"):
        out.append("run_update 有開始、卻一個步驟都沒跑完")
    if fresh_min is None:
        return out                       # 手動跑（迴圈每輪查）：只問有沒有跑，不判新鮮度
    if age_min is None:
        out.append("日誌沒有時間戳，無法判斷是不是這一班寫的")
    elif age_min > fresh_min:
        out.append("日誌是 %.1f 小時前的（>%d 分鐘）⇒ 這一班沒有寫新日誌" % (age_min / 60.0, fresh_min))
    return out


def data_counts():
    out = {}
    # 2026-09-07：本來是 [-3:]（只看最近三年），2013~2023 共 11 年的縮水永遠測不到。
    # 實測全部 14 年（194MB）解析只要 1.9 秒，沒有理由省。
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "data_20*.js"))):
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


# ── 基準比對（純函式；scripts/update_health_test.py 在測，不讀檔不印字）────────────
# 「硬性」項＝歷史比賽資料，只會增不會減。它變少一定是來源掛了或過濾壞了（DAILY.md 線 3），
# 不是資料真的變少。其餘（soloq 選手數、逐場檔數）本來就會因為換人／清孤兒而合理減少。
def is_hard(key):
    return key.startswith("data_") or key == "side_sel.games"


def diff_counts(prev, cur):
    """比對本次與基準 → [(key, 現值, 基準值, 狀態)]。

    狀態：ok／new（基準沒這項）／unreadable（讀不到）／soft_down（可以合理變少）／shrink（硬性縮水）。
    """
    rows = []
    for k, v in cur.items():
        pv = prev.get(k)
        if v is None:
            st = "unreadable"
        elif not isinstance(pv, int):
            st = "new"
        elif v < pv:
            st = "shrink" if is_hard(k) else "soft_down"
        else:
            st = "ok"
        rows.append((k, v, pv if isinstance(pv, int) else None, st))
    return rows


def merge_baseline(prev, cur, accept=False):
    """算出要寫回的基準。

    2026-09-07 的洞：舊版無條件把本次數字存成基準，於是**縮水第二天就被吃掉**——
    第一輪報一次「data_2024 縮水」，存檔後基準跟著變小，之後每一輪都看起來正常，
    問題還在但再也不會被提醒。改成硬性項採「已知良好的高水位」：縮水不寫回較小值，
    會一直報到有人用 `--accept` 認可（例如 OE 真的撤掉了幾場比賽）為止。
    軟性項與讀不到的項一律沿用舊值／新值，不受影響。
    """
    out = dict(prev)
    for k, v, pv, st in diff_counts(prev, cur):
        if st == "unreadable":
            continue                      # 讀不到就別把 None 蓋掉舊基準
        if st == "shrink" and not accept:
            continue                      # 保住高水位
        out[k] = v
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
    # 先問「這份日誌是不是這一班寫的」，再談日誌裡的內容（#47）
    fresh_min = FRESH_MIN if "--from-publish" in sys.argv else None
    age = log_age_min((lg or {}).get("start_at"),
                      os.path.getmtime(LOG) if os.path.exists(LOG) else None, time.time())
    print("日誌：%s（%s%s）" % (
        (lg or {}).get("start_at") or "沒有 run_update 時間戳",
        "年齡不明" if age is None else "%.1f 小時前" % (age / 60.0),
        "" if fresh_min else "，手動跑不判新鮮度"))
    bad += run_problems(lg, age, fresh_min)
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
        # 失敗優先：日誌萬一同時有兩種字樣（例如手動補跑過），印 ✓ 會跟下面的結論自相矛盾
        print("守門：%s／push：%s／lint 錯誤級：%s／可疑同名：%s" % (
            "✗ FAILED" if lg["preflight_fail"] else ("✓" if lg["preflight_ok"] else "？"),
            "✓" if lg["pushed"] else "？", lg["lint_err"], lg["dup"]))
        if lg["lint_err"]:
            bad.append("lint_text 錯誤級 %d（應為 0）" % lg["lint_err"])
        if lg["preflight_fail"]:
            bad.append("preflight 失敗、沒有 push")
    else:
        print("（找不到 update_log.txt）")
    pc = prev.get("counts", {})
    accept = "--accept" in sys.argv
    print("資料量（基準＝已知良好的高水位，%s）：" % (prev.get("at") or "尚無基準"))
    for k, v, pv, st in diff_counts(pc, dc):
        flag = {"ok": ("  （基準 %s）" % pv) if pv is not None else "",
                "new": "  （新項目）",
                "unreadable": "  ⚠ 讀不到",
                "soft_down": "  比基準少（%s → %s）" % (pv, v),
                "shrink": "  ⚠ 縮水（基準 %s → 現在 %s）" % (pv, v)}[st]
        if st == "unreadable":
            bad.append("%s 讀不到" % k)
        elif st == "shrink":
            bad.append("%s 縮水 %d → %d" % (k, pv, v))
        print("   %-22s %s%s" % (k, v, flag))
    print("")
    print("結論：" + ("✓ 沒有異常" if not bad else "⚠ " + "；".join(bad)))
    if any("縮水" in b for b in bad):
        print("（縮水的項目**不會**寫回基準，會一直報到你確認為止；"
              "確認資料真的變少就跑 python scripts\\update_health.py --accept）")
    if "--no-save" not in sys.argv:
        os.makedirs(os.path.dirname(BASE), exist_ok=True)
        json.dump({"at": time.strftime("%Y-%m-%d %H:%M"),
                   "counts": merge_baseline(pc, dc, accept),
                   "last": dc,
                   "log": {k: v for k, v in (lg or {}).items() if k != "steps"},
                   "bad": bad}, io.open(BASE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("（基準已存 autopilot/UPDATE_BASELINE.json%s）" % ("，--accept：縮水已認可" if accept else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
