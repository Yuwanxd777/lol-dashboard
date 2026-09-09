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
        ‧ **最新一場比賽是哪一天**（2026-09-10 #98）——列數只擋得住「變少」，擋不住「不再變多」：
          來源停更（OE 的 Drive CSV 沒再更新／service account 失效）時列數會**剛好等於基準**，
          舊版報告一路印「✓ 沒有異常」。現在多印一行「最新一場比賽 YYYY-MM-DD（N 天前）」，
          並在**日期倒退**（＝比賽被刪或解析壞了，硬性）或**超過 STALE_DAYS**時列為異常
        ‧ **遊戲版本有沒有往前走**（2026-09-10 #99）——同一種病的另一個入口：run_update 跑
          `fetch_patches --skip-discover`，新版本靠猜 URL slug 抓，官方換格式（26.04 換過一次）
          就會靜靜地抓不到，patches.js 停在舊版而列數一列不少。拿**獨立來源** DDragon
          （skills.js 的 v／assets.js 的 years，每班現抓 versions.json）對照版本改動最新版
        ‧ soloq.js 選手數／有排名數、side_sel.js 局數、lint_text 錯誤級
        ‧ **可疑同名走現況重算**（2026-09-07 #49），不是讀日誌快照——審定是人在班與班之間補的
        ‧ preflight 有沒有過、有沒有 push

用法：python scripts/update_health.py           # 報告＋更新基準
      python scripts/update_health.py --no-save # 只報告
      python scripts/update_health.py --accept  # 認可縮水（資料真的變少時才用），把現值寫成新基準
      python scripts/update_health.py --from-publish   # publish.bat 用：日誌不新鮮＝異常
      python scripts/update_health.py --no-live        # 跳過可疑同名的現況重算（省 ~3 秒）
"""
import datetime
import glob
import io
import json
import os
import re
import subprocess
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


# ── 日誌快照 vs 現況（2026-09-07 #49）──────────────────────────────────────────
# 「守門／push／lint 錯誤級／可疑同名」是**那一班日誌寫下來的快照**，下面的資料量卻是**現況**，
# 兩種時間基準用同一種語氣印出來 ⇒ 讀的人分不出哪個數字現在還算數。
# 真的踩到（2026-09-07 18:1x）：10:00 那班報「可疑同名 10」，15:28 審定完早就是 0，
# 健檢每輪照樣印 10，迴圈追了一輪才發現是舊帳。反過來更糟——那班之後資料變髒、
# 快照仍印 0 就是**假綠**（跟 #47 讀到上一班日誌是同一種病）。
# 可疑同名便宜（整份掃 ~3 秒）且**會被人在班與班之間改動**（審定檔 player_disambig.json），
# 所以直接重算現況；lint 錯誤級留快照（掃 8 萬條字串太貴，來源也只有管線會動），但那行明講是快照。
DUP_TIMEOUT = 180


def parse_dup_quiet(text):
    """check_player_dup.py --quiet 的輸出 → 未審定可疑同名數（認不得回 None）。"""
    m = re.search(r"未審定的可疑同名 (\d+)", text or "")
    return int(m.group(1)) if m else None


def live_dup(timeout=DUP_TIMEOUT):
    """現況重算未審定可疑同名。回 (數字或 None, 說明)。

    永遠不丟例外：健檢是每輪都要能跑完的尺，不能被一個附帶指標弄死；算不出來就退回快照。
    子程序的 stdout 強制 utf-8（Windows 預設 cp950 會把中文摘要打亂 ⇒ 認不得輸出）。
    """
    exe = os.path.join(ROOT, "scripts", "check_player_dup.py")
    if not os.path.exists(exe):
        return None, "找不到 check_player_dup.py"
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        p = subprocess.Popen([sys.executable, exe, "--quiet"], cwd=ROOT, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = p.communicate(timeout=timeout)[0]
    except Exception as e:
        try:
            p.kill()
        except Exception:
            pass
        return None, "重算失敗：%s" % (e.__class__.__name__,)
    n = parse_dup_quiet((out or b"").decode("utf-8", "replace"))
    if n is None:
        return None, "重算的輸出認不得（exit %s）" % p.returncode
    return n, ""


def dup_line(snapshot, live, err):
    """可疑同名那一行的字（純函式，好測）。live 是現況、snapshot 是日誌快照。"""
    if live is None:
        return "可疑同名：%s（那一班日誌的舊數字；%s）" % (
            "？" if snapshot is None else snapshot, err or "現況算不出來")
    if snapshot is None or snapshot == live:
        return "可疑同名：%d（現況重算）" % live
    return "可疑同名：%d（現況重算；那一班日誌是 %d，已經是舊帳）" % (live, snapshot)


# ── 「這一班到底有沒有真的跑」（純函式；scripts/update_health_test.py 在測）──────────
# 正常一班：10:00 開始、25~30 分鐘跑完，最壞那次退回循序 94 分鐘；健檢緊接在 push 之後跑。
# 失效那一班：日誌是上一班寫的 ⇒ 至少差 12 小時（兩班間隔）。240 分鐘落在中間，兩邊都有很大餘裕。
FRESH_MIN = 240


def start_ts(start_at):
    """日誌裡 run_update 的開始時間字串 → timestamp（壞格式／None 回 None）。"""
    if not start_at:
        return None
    try:
        return time.mktime(time.strptime(start_at, "%Y-%m-%d %H:%M:%S"))
    except ValueError:
        return None


def log_age_min(start_at, log_mtime, now_ts):
    """日誌有多舊（分鐘）。優先用日誌裡 run_update 的開始時間，沒有才退回檔案 mtime。

    為什麼優先用內容而不是 mtime：publish.bat 在健檢跑完後會 `type` 健檢結論折進 update_log.txt，
    mtime 因此永遠是「剛剛」；而且日誌裡的時間才是這一班真的開始跑的時間。
    回 None＝兩個都沒有（檔案不存在）。時鐘漂移造成的負值夾成 0。
    """
    ts = start_ts(start_at)
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


# ── 排程班次點名（2026-09-07 #48）────────────────────────────────────────────────
# 為什麼還要這一條：#47 的新鮮度只在 **publish.bat 真的跑起來** 時才判（--from-publish）。
# publish.bat 整個沒被叫起來——排程工作被停用／改名、電腦當時在睡、捷徑路徑壞掉——
# 就沒有任何人問「這一班有沒有跑」；而迴圈每輪手動跑刻意不判新鮮度（手動本來就落在兩班之間）。
# 結果：`autopilot/HEALTH_ALERT.txt` 不存在，DAILY.md 的檢查點把它讀成「上一班沒事」，
# 網站默默停在昨天的資料。這是 #47 那個洞往上一層的同一個形狀：**沒有壞消息 ≠ 有跑過**。
# 做法：不用固定年齡，改問「上一個排定的班次（10:00／22:00）有沒有留下它自己的日誌」，
# 所以手動在任何時刻跑都不會誤報。
SHIFTS = (10, 22)          # publish.bat 的排程時刻（工作 LOL_Dashboard_Update）
SHIFT_GRACE_MIN = 180      # 過了班次多久還沒日誌才算沒跑
SHIFT_SLACK_MIN = 5        # 日誌可以比班次早這麼多（排程提早觸發／時鐘漂移）


def last_shift_ts(now_ts, shifts=SHIFTS):
    """now 之前最近一個排定班次的 timestamp（跨午夜會取到昨天 22:00）。"""
    lt = time.localtime(now_ts)
    day0 = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
    cand = [day0 + d * 86400 + h * 3600 for d in (0, -1) for h in shifts]
    return max(c for c in cand if c <= now_ts)


def shift_problems(start_at, now_ts, shifts=None, grace_min=None, slack_min=None):
    """上一個排定班次有沒有留下自己的日誌 → (bad 訊息 list, 給人看的一行說明)。

    三種結果：①日誌的 run 開始時間 ≥ 班次時刻 ⇒ 跑過了 ②還在寬限期內 ⇒ 不判
    （可能正在跑、或排程被 Windows 的「錯過就盡快補跑」延後）③過了寬限還是舊日誌 ⇒ 這一班沒跑。

    2026-09-09 #96：三個參數改成 None ＋ **呼叫時**才取模組常數。原本寫成
    `grace_min=SHIFT_GRACE_MIN` 這種預設值，Python 在 import 當下就把值綁死 ⇒
    測試 monkeypatch `uh.SHIFT_GRACE_MIN = 0`（⑬「寬限歸零」的前提）完全沒有作用。
    後果是時間相依的假紅：班次後 180 分鐘內（22:00~01:00、10:00~13:00，**正好是迴圈在跑的時段**）
    elapsed < 180 ⇒ 舊日誌被判「還不判」⇒ ⑬前提恆假，連帶 _r48_mutate／_r49_mutate
    因為「原版就沒過」整批放棄突變 ⇒ 一次 4 紅。
    """
    if shifts is None:
        shifts = SHIFTS
    if grace_min is None:
        grace_min = SHIFT_GRACE_MIN
    if slack_min is None:
        slack_min = SHIFT_SLACK_MIN
    b = last_shift_ts(now_ts, shifts)
    bl = time.strftime("%m-%d %H:%M", time.localtime(b))
    elapsed = (now_ts - b) / 60.0
    ts = start_ts(start_at)
    if ts is not None and ts >= b - slack_min * 60:
        return [], "班次 %s：✓ 已跑（日誌 %s）" % (bl, start_at)
    if elapsed < grace_min:
        return [], "班次 %s：才過 %.0f 分鐘（寬限 %d 分），還不判" % (bl, elapsed, grace_min)
    if ts is None:
        return (["上一班 %s 沒跑：日誌裡根本沒有 run_update 時間戳" % bl],
                "班次 %s：✗ 日誌沒有時間戳" % bl)
    return (["上一班 %s 沒跑：日誌最後一次 run_update 是 %s（%.1f 小時前）⇒ publish.bat 這一班沒被叫起來"
             % (bl, start_at, (now_ts - ts) / 3600.0)],
            "班次 %s：✗ 沒有這一班的日誌（最後 %s）" % (bl, start_at))


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def max_date(raw):
    """RAW_DATA（含表頭）→ 最新的一場比賽日期 'YYYY-MM-DD'；一筆都認不得就 None。

    欄位一律 hdr.index('date') 查（年度資料是白名單制的 88 欄，硬編偏移會在改白名單那天壞掉）。
    """
    hdr = raw[0]
    try:
        di = hdr.index("date")
    except ValueError:
        return None
    best = None
    for r in raw[1:]:
        v = r[di] if di < len(r) else None
        if not v:
            continue
        s = str(v)[:10]
        if DATE_RE.match(s) and (best is None or s > best):
            best = s
    return best


def data_counts(latest_out=None):
    """列數；`latest_out` 給一個 dict 就順便填「每個年度檔的最新比賽日期」。

    刻意做成選填的出參而不是改回傳值：`scripts/update_health_test.py` 的端到端那段
    直接 `uh.data_counts()` 拿 dict，改簽名會把既有測試打壞。日期在**同一次解析**裡算完，
    不會為了新增一個指標再讀一遍 194MB。
    """
    out = {}
    # 2026-09-07：本來是 [-3:]（只看最近三年），2013~2023 共 11 年的縮水永遠測不到。
    # 實測全部 14 年（194MB）解析只要 1.9 秒，沒有理由省。
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "data_20*.js"))):
        try:
            d = js_obj(f)
            raw = d["tabs"]["RAW_DATA"]
            out[os.path.basename(f)] = len(raw)
            if latest_out is not None:
                latest_out[os.path.basename(f)] = max_date(raw)
        except Exception:
            out[os.path.basename(f)] = None
            if latest_out is not None:
                latest_out[os.path.basename(f)] = None
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


# ── 最新一場比賽（2026-09-10 #98；純函式，scripts/update_health_test.py 在測）──────────
# 為什麼門檻鬆到 75 天：**LOL 的空窗期本來就很長**，2026-09-10 實測全庫 3219 個比賽日，
# 最長的無比賽間隔是 69 天（2022-11-06 → 2023-01-14），其次 55、44、35、31。
# 而且空窗不只出現在冬季——2021-09-05 → 2021-10-05 中間 30 天（各賽區總決賽打完、世界賽還沒開打），
# **今天（2026-09-08 最後一場）正好又落在那個窗口**。所以「N 天沒新比賽」做不成靈敏的警報，
# 硬調嚴只會每年固定誤報好幾次、然後大家學會忽略它。
# 這裡的分工：
#   ‧ 日期**每一輪都印出來**（資訊性）——迴圈看得到「有沒有往前走」，這是舊版完全沒有的訊號
#   ‧ 只有兩種情況算異常：①日期**倒退**（硬性，比賽被刪或 date 欄解析壞了，跟列數縮水同一種病）
#     ②超過 STALE_DAYS＝比史上最長空窗還長 ⇒ 那時「來源停更」已經是唯一合理解釋
STALE_DAYS = 75
FUTURE_DAYS = 7      # 比今天還晚這麼多天＝日期解析壞了（時區差不可能有一週）


def newest(latest):
    """{檔名: 'YYYY-MM-DD'} → (檔名, 日期)，全庫最新的那一場；沒有可讀日期就 (None, None)。"""
    ok = [(v, k) for k, v in latest.items() if v]
    if not ok:
        return (None, None)
    v, k = max(ok)
    return (k, v)


def days_since(datestr, now_ts):
    y, m, d = (int(x) for x in datestr.split("-")[:3])
    return (datetime.date.fromtimestamp(now_ts) - datetime.date(y, m, d)).days


def latest_problems(prev, cur, now_ts, stale_days=STALE_DAYS):
    """回 (要印的那一行, [異常…])。prev＝基準裡的高水位日期，cur＝這次算出來的。"""
    k, v = newest(cur)
    if not v:
        return ("最新一場比賽：讀不到（date 欄壞了？）", ["讀不到任何一場比賽的日期"])
    bad = []
    # ① 倒退：逐檔比，跟列數縮水同一種病（某一年被刪光也照樣抓得到，即使別的年份還在往前走）
    for kk in sorted(cur):
        pv, cv = prev.get(kk), cur.get(kk)
        if cv and isinstance(pv, str) and cv < pv:
            bad.append("%s 最新比賽日期倒退（基準 %s → 現在 %s）" % (kk, pv, cv))
    n = days_since(v, now_ts)
    if n > stale_days:
        bad.append("最新一場比賽 %s 已經 %d 天前（>%d 天）——來源可能停更" % (v, n, stale_days))
    elif n < -FUTURE_DAYS:
        bad.append("最新一場比賽 %s 比今天還晚 %d 天——date 欄解析壞了？" % (v, -n))
    pv = prev.get(k)
    if not isinstance(pv, str):
        move = "基準沒這項（新項目）"
    elif pv == v:
        move = "基準同一天（沒往前）"
    elif v > pv:
        move = "基準 %s（+%d 天）" % (pv, days_since(pv, now_ts) - n)
    else:
        move = "⚠ 基準 %s（倒退）" % pv
    return ("最新一場比賽：%s（%s，%d 天前）；%s" % (v, k, n, move), bad)


def merge_latest(prev, cur, accept=False):
    """日期也採高水位：倒退不寫回基準（不然第二輪就被吃掉，跟 merge_baseline 同一個洞）。"""
    out = dict(prev)
    for k, v in cur.items():
        if not v:
            continue                      # 讀不到就別把舊值蓋掉
        pv = prev.get(k)
        if isinstance(pv, str) and v < pv and not accept:
            continue
        out[k] = v
    return out


# ── 遊戲版本（2026-09-10 #99）───────────────────────────────────────────────
# 為什麼要有這段：patches.js 的版本改動來自官方 patch notes 頁，而 run_update 跑的是
# `fetch_patches --skip-discover`（不開 Playwright 掃 tag 頁），新版本是靠**猜 URL slug** 抓的。
# 官方換過一次格式（26.04 起變成 league-of-legends-patch-26-N-notes），再換一次就會靜靜地抓不到：
# patches.js 停在舊版、每個資料檔一列不少、日期也沒倒退 ⇒ 報告一路印「✓ 沒有異常」。
# 跟 #47（讀到上一班日誌）／#49（印舊快照）／#98（列數不再變多）是同一種病：**沒變化被讀成沒問題**。
# csv_cache/patch_dates.json 幫不上忙——`official_patch_dates()` 是「patches.js 的版本鍵都在快取裡
# 就直接 return」，它永遠看不到 patches.js 還不知道的版本（循環相依，不是獨立證人）。
# 唯一**獨立**的證人是 DDragon：fetch_skills（skills.js 的 v）與 fetch_assets（assets.js 的 years）
# 每一班都去 ddragon 的 versions.json 拿最新版號，跟 patch notes 頁是完全不同的來源。
# 所以這裡比的是「DDragon 說現在打的是哪一版」對「版本改動最新收到哪一版」。
PATCH_STALE_DAYS = 80   # 版本改動停在同一版超過這麼多天＝可能停更（史上最長間隔 71 天：24.24→25.04）
VER_GRACE_H = 24        # 不一致要撐過這麼久才算異常（改版當天兩邊上線本來就有時差，跨兩班才可疑）

PK_RE = re.compile(r'"(\d{2}\.\d{2})":\{')   # 與 build_soloq_builds.season_patches() 同一個慣用法


def ver_key(v):
    """版本字串 → 可比大小的數字元組；'26.9' < '26.10'、'16.17.1' > '16.17'。認不得就 (0,)。"""
    try:
        return tuple(int(x) for x in str(v).split(".") if x != "")
    except Exception:
        return (0,)


def newest_pk(path):
    """patches.js／patches_en.js 的最新版本鍵。只掃字串不 json.loads——那個檔是兩個 statement
    （window.LOL_PATCHES=…;window.ITEM_REMOVED=…），整份解析反而會炸。"""
    try:
        t = io.open(path, encoding="utf-8", errors="replace").read()
    except Exception:
        return None
    ks = set(PK_RE.findall(t))
    return max(ks, key=ver_key) if ks else None


def dd_to_pk(ver):
    """DDragon 版號 → 版本改動鍵：'16.17.1' → '26.17'。
    DDragon 一直用序號版（2026 年＝16.x），patch notes 從 2025 起改年份版（25.x／26.x）⇒ 差 10。
    萬一哪天 DDragon 也改成年份版（major 直接是 25、26…），major > 20 就當它已經是年份版
    ——DDragon 的 major 要漲到 21 是 2031 年，那時年份版早就是 31 了，兩邊不會撞。"""
    p = str(ver).split(".")
    if len(p) < 2:
        return None
    try:
        maj, mi = int(p[0]), int(p[1])
    except ValueError:
        return None
    return "%02d.%02d" % (maj if maj > 20 else maj + 10, mi)


def game_versions():
    """四個來源現在各自停在哪一版（讀不到就 None，不要讓例外把整份健檢打斷）。

    路徑**在函式裡才組**、不做成模組層常數（#96 寬限旗標晚綁的同一個道理）：沙盒測試接管的是
    `ROOT`，模組層常數會在 import 當下就把真實 repo 的路徑焊死，接管不到 ⇒ 測試看起來綠、
    其實讀的是正本（而且會被 `_m98_freshness_test` 的「模組層沒有字串指著真實 repo」那條抓出來）。
    """
    P = lambda *a: os.path.join(ROOT, *a)
    cur = {"patches": newest_pk(P("patches.js")), "patches_en": newest_pk(P("patches_en.js")),
           "ddragon": None, "assets": None, "patch_date": None}
    try:
        cur["ddragon"] = (js_obj(P("skills.js")) or {}).get("v")
    except Exception:
        pass
    try:
        yrs = (js_obj(P("assets.js")) or {}).get("years") or {}
        if yrs:
            cur["assets"] = yrs.get(max(yrs))
    except Exception:
        pass
    try:
        if cur["patches"]:
            cur["patch_date"] = json.load(
                io.open(P("csv_cache", "patch_dates.json"), encoding="utf-8")).get(cur["patches"])
    except Exception:
        pass
    return cur


def version_problems(prev, cur, prev_since, now_ts,
                     grace_h=VER_GRACE_H, stale_days=PATCH_STALE_DAYS):
    """回 (要印的那一行, [異常…], 要存回基準的 since)。

    prev＝基準裡的高水位版本；cur＝這次讀到的；prev_since＝上次看到不一致的時間戳（沒有＝None）。
    三種異常：①版本**倒退**（硬性，跟列數縮水同一種病）②不一致**撐過 grace_h**
    （改版當天 DDragon 與公告有時差，當場報會每兩週固定誤報一次）③版本改動停在同一版超過 stale_days。
    """
    bad = []
    p, pe, dd, ast = cur.get("patches"), cur.get("patches_en"), cur.get("ddragon"), cur.get("assets")
    miss = [n for n, v in (("patches.js", p), ("patches_en.js", pe),
                           ("skills.js", dd), ("assets.js", ast)) if not v]
    if miss:
        bad.append("讀不到版本：" + "、".join(miss))
    # ① 倒退：四個來源逐一比基準（高水位）
    for k, label in (("patches", "patches.js"), ("patches_en", "patches_en.js"),
                     ("ddragon", "skills.js（DDragon）"), ("assets", "assets.js（DDragon）")):
        pv, cv = prev.get(k), cur.get(k)
        if cv and isinstance(pv, str) and ver_key(cv) < ver_key(pv):
            bad.append("%s 版本倒退（基準 %s → 現在 %s）" % (label, pv, cv))
    # ② 不一致：DDragon 是獨立證人，它往前走了而版本改動沒有 ⇒ patch notes 沒抓到
    ddpk = dd_to_pk(dd) if dd else None
    mism = []
    if p and ddpk and p != ddpk:
        mism.append("DDragon %s（＝%s）≠ 版本改動 %s" % (dd, ddpk, p))
    if p and pe and p != pe:
        mism.append("英文 %s ≠ 繁中 %s" % (pe, p))
    if dd and ast and dd != ast:
        mism.append("圖鑑素材 %s ≠ 技能 %s" % (ast, dd))
    since, hrs = prev_since, None
    if mism:
        if not isinstance(since, (int, float)):
            since = now_ts
        hrs = (now_ts - since) / 3600.0
        if hrs >= grace_h:
            bad.append("版本不一致已 %.1f 小時（>%d）：%s" % (hrs, grace_h, "；".join(mism)))
    else:
        since = None
    # ③ 停更：發布日距今太久（門檻 80 天＝比史上最長間隔 71 天再寬一點）
    n = None
    if cur.get("patch_date"):
        n = days_since(cur["patch_date"], now_ts)
        if n > stale_days:
            bad.append("版本改動停在 %s 已經 %d 天（>%d 天）——官方 URL 格式又變了？"
                       % (p, n, stale_days))
    dpart = "發布日不明" if n is None else "%s 發布，%d 天前" % (cur["patch_date"], n)
    line = "遊戲版本：版本改動 %s（%s）／英文 %s／DDragon %s＝%s／圖鑑 %s" % (
        p or "？", dpart, pe or "？", dd or "？", ddpk or "？", ast or "？")
    if mism:
        line += "  ⚠ 不一致（%s）：已 %.1f 小時%s" % (
            "；".join(mism), hrs, "" if hrs >= grace_h else "（滿 %d 小時才算異常）" % grace_h)
    else:
        line += " — 一致"
    return (line, bad, since)


def merge_versions(prev, cur, accept=False):
    """版本也採高水位：倒退不寫回基準（不然第二輪就被吃掉，跟 merge_baseline／merge_latest 同一個洞）。"""
    out = dict(prev)
    for k, v in cur.items():
        if not v:
            continue
        pv = prev.get(k)
        if k != "patch_date" and isinstance(pv, str) and ver_key(v) < ver_key(pv) and not accept:
            continue
        out[k] = v
    return out


def main():
    lg = parse_log()
    lt = {}
    dc = data_counts(lt)
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
    # 排程班次點名（#48）：手動跑不判「年齡」，但一定要判「上一個 10:00／22:00 有沒有留下日誌」，
    # 否則 publish.bat 整個沒被叫起來時，沒有任何檢查會出聲（--from-publish 的新鮮度也跟著沒跑）。
    sp, snote = shift_problems((lg or {}).get("start_at"), time.time())
    print(snote)
    if fresh_min is None:                # publish 模式已有 FRESH_MIN 那條，不重複報同一件事
        bad += sp
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
        print("那一班的日誌快照（不是現況）：守門：%s／push：%s／lint 錯誤級：%s" % (
            "✗ FAILED" if lg["preflight_fail"] else ("✓" if lg["preflight_ok"] else "？"),
            "✓" if lg["pushed"] else "？", lg["lint_err"]))
        if lg["lint_err"]:
            bad.append("lint_text 錯誤級 %d（應為 0）" % lg["lint_err"])
        if lg["preflight_fail"]:
            bad.append("preflight 失敗、沒有 push")
    else:
        print("（找不到 update_log.txt）")
    # 可疑同名走現況重算（#49；--no-live 可跳過，例如管線正在跑、不想再讀一次 26MB 年度資料）
    if "--no-live" in sys.argv:
        print("可疑同名：%s（那一班日誌的舊數字；--no-live 跳過重算）"
              % ("？" if (lg or {}).get("dup") is None else lg["dup"]))
    else:
        _live, _err = live_dup()
        print(dup_line((lg or {}).get("dup"), _live, _err))
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
    # 最新一場比賽（#98）：列數擋「變少」，這行擋「不再變多」
    lline, lbad = latest_problems(prev.get("latest") or {}, lt, time.time())
    print("   " + lline)
    bad += lbad
    # 遊戲版本（#99）：比賽資料以外，patch notes／DDragon 也會靜靜地停在舊版
    gv = game_versions()
    vline, vbad, vsince = version_problems(prev.get("versions") or {}, gv,
                                           prev.get("version_mismatch_since"), time.time())
    print("   " + vline)
    bad += vbad
    print("")
    print("結論：" + ("✓ 沒有異常" if not bad else "⚠ " + "；".join(bad)))
    if any("縮水" in b for b in bad):
        print("（縮水的項目**不會**寫回基準，會一直報到你確認為止；"
              "確認資料真的變少就跑 python scripts\\update_health.py --accept）")
    if "--no-save" not in sys.argv:
        os.makedirs(os.path.dirname(BASE), exist_ok=True)
        json.dump({"at": time.strftime("%Y-%m-%d %H:%M"),
                   "counts": merge_baseline(pc, dc, accept),
                   "latest": merge_latest(prev.get("latest") or {}, lt, accept),
                   "last": dc,
                   "last_latest": lt,
                   "versions": merge_versions(prev.get("versions") or {}, gv, accept),
                   "version_mismatch_since": vsince,
                   "last_versions": gv,
                   "log": {k: v for k, v in (lg or {}).items() if k != "steps"},
                   "bad": bad}, io.open(BASE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("（基準已存 autopilot/UPDATE_BASELINE.json%s）" % ("，--accept：縮水已認可" if accept else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
