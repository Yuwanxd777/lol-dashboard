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
        ‧ **根目錄 50 幾個資料檔的 bytes**（2026-09-10 #100）——上面那 18 個指標之外的
          career／wiki_patches／leaguepedia／soloq_builds／side_sel_20xx／skills／assets…
          一個都沒被量過；順帶補上「基準有、這次連鍵都不見了」＝**檔案整個消失**
        ‧ soloq.js 選手數／有排名數、side_sel.js 局數、lint_text 錯誤級
        ‧ **積分逐場有沒有往前走**（2026-09-16 #143）——上面那三個 soloq 指標全是數量的高水位，
          dpm.lol／Riot 那頭壞掉時（API 改版、帳號錯配、逐場抓到 0 筆又不報錯）一個都不會動：
          檔案還是 425 個、選手還是 1096 位，只是每個檔的最後一局永遠停在壞掉那天。
          拿逐場檔自己的 "t"（Riot 帶進來的開打時間＝獨立證人）看全庫最新一局幾小時前
          （>SQF_STALE_H）與「距那一局 24 小時內也有新局」的檔數（<SQF_THIN_MIN；窗口釘在最新一局
          而不是現在，否則漏一整班就誤報）；只讀每檔開頭 8192 位元組
          （0.02s），判定落後時自動整檔重掃再下結論
        ‧ **可疑同名走現況重算**（2026-09-07 #49），不是讀日誌快照——審定是人在班與班之間補的
        ‧ preflight 有沒有過、有沒有 push

        ‧ **逐聯賽有沒有落後**（2026-09-16 #140）——上面全是全站指標，單一聯賽整段沒收
          （LPL 停三天）會被別的聯賽蓋過去：列數照樣天天變多、「最新一場」照樣是今天，
          18 個指標一個都不會叫。拿 Leaguepedia Cargo 當真相，比對六個一級聯賽
          「wiki 有、我們沒有」的比賽日；這是整份健檢**唯一**會連外的一項（~3 秒），
          wiki 掛掉只降級成「略過」，不影響其餘結論

用法：python scripts/update_health.py           # 報告＋更新基準
      python scripts/update_health.py --no-save # 只報告
      python scripts/update_health.py --accept  # 認可縮水（資料真的變少時才用），把現值寫成新基準
      python scripts/update_health.py --from-publish   # publish.bat 用：日誌不新鮮＝異常
      python scripts/update_health.py --no-live        # 跳過可疑同名的現況重算（省 ~3 秒）
      python scripts/update_health.py --no-soloqfresh  # 跳過積分逐場新鮮度（便宜路徑 0.02s，平常不必跳）
      python scripts/update_health.py --no-lag         # 跳過逐聯賽落後（唯一連外的那項，省 ~3 秒）
"""
import collections
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


# ── run_update 的步驟清單（2026-09-10 #101；純函式，scripts/update_health_test.py 在測）────
# 為什麼要有這段：#100 補的是「產物不見了／變小了」，這一條補的是**上游**——產出它的那一步
# 從此不再跑。`run_update.PLAN` 是一份靜態的 43 步清單，它被改壞（#96 才剛把 fetch_promo
# 換過階段、#72 動過 ③ 的順序）、某支腳本 import 失敗被執行器略過、或 `--only` 驗收把正式日誌
# 覆寫掉時，那一步就此從日誌上消失，而現有的每一條哨兵都看不到：
#   ‧ 產物檔還在、bytes 也不變（#100 量的是體積，沒重寫就沒有變化）
#   ‧ 列數等於基準（高水位，只擋得住變少）
#   ‧ #98 的比賽日期只看 data_*.js、#99 的版本只看 patches／DDragon
#     ⇒ soloq／career／side_sel／圖鑑那一整批的產出步驟消失，沒有任何人出聲
#   ⇒ 報告一路印「✓ 沒有異常」，資料其實從那天起就凍住了（跟 #47 讀到上一班日誌、#49 印舊快照、
#     #98 來源停更同一種病：**沒變化被讀成沒問題**）。
# 諷刺的是健檢本來就 parse 出了步驟名，卻只拿來印「步驟 43 個」，從不跟基準比；
# 存檔時還特地把 steps 丟掉（`{k: v for k, v in lg.items() if k != "steps"}`）。
# 缺席採高水位：不寫回基準，一直報到 `--accept`（跟 counts／sizes／latest／versions 同一個處置）。


def step_names(lg):
    """日誌裡跑過的步驟名：去重、保留首次出現的順序。

    去重是必要的——階段並行炸掉會退回循序把同一批步驟再跑一次（parse_log 的 stage_fallback），
    那時同一個名字在日誌裡出現兩次，不去重的話基準會被「跑幾次」污染。
    """
    seen, out = set(), []
    for n, _, _ in ((lg or {}).get("steps") or []):
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def step_problems(prev, cur):
    """回 (要印的那一行, [異常…])。prev＝基準裡的步驟名（高水位聯集）、cur＝這一班跑過的。"""
    if not cur:
        # 「一個步驟都沒跑完」run_problems 已經報過了，這裡不重複；也不能拿空清單去比基準
        return ("步驟清單：這一班沒有跑完任何步驟（上面已報）", [])
    if not prev:
        return ("步驟清單：%d 個步驟（首次建立基準）" % len(cur), [])
    cs, ps = set(cur), set(prev)
    miss = [n for n in prev if n not in cs]
    new = [n for n in cur if n not in ps]
    bad = []
    if miss:
        bad.append("步驟不見了：%s（基準有、這一班沒跑到；PLAN 被改動或那一步被略過）"
                   % "、".join(miss))
    line = "步驟清單：%d 個步驟%s%s" % (
        len(cur),
        ("，⚠ 少了 %d 個：%s" % (len(miss), "、".join(miss))) if miss
        else ("，基準 %d 個都在" % len(ps)),
        ("；新增 %s" % "、".join(new)) if new else "")
    return (line, bad)


def merge_steps(prev, cur, accept=False):
    """步驟名也採高水位聯集：消失不寫回（不然第二輪就被吃掉，跟 merge_baseline 同一個洞）。

    cur 是空的（沒日誌／一步都沒跑完）時原封不動回舊基準——**不可以把基準清空**，
    否則「這一班整個沒跑」會順手把下一輪的比對對象也毀掉，變成永遠比不出缺席。
    """
    if not cur:
        return list(prev)
    if accept:
        return list(cur)
    return list(prev) + [n for n in cur if n not in set(prev)]


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
    # 基準有、這次連鍵都算不出來＝**檔案整個不見了**（2026-09-10 #100）。舊版只迭代 cur，
    # data_2019.js 被刪掉時這裡靜靜少一行、結論照印「✓ 沒有異常」；preflight ① 也擋不住
    # （它是先用「檔案存在」過濾候選才 node --check，檔案一消失就從清單裡消失）。
    for k in sorted(prev):
        if k not in cur and isinstance(prev[k], int):
            rows.append((k, None, prev[k], "missing"))
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
        if st == "missing":
            if accept:
                out.pop(k, None)          # 認可＝那個檔真的不該存在了
            continue                      # 否則保住基準值，下一輪繼續報
        out[k] = v
    return out


# ── 資料檔體積哨兵（2026-09-10 #100；純函式，scripts/update_health_test.py 在測）────────
# 為什麼要有這段：上面的「資料量」只有 18 個指標（14 年列數＋soloq 兩項＋side_sel＋逐場檔數），
# 而 index.html 真正載入的**根目錄資料檔有 50 幾個**——career.js（12.8MB 選手生涯）、
# wiki_patches.js（3.1MB）、leaguepedia.js（3.4MB）、soloq_builds.js、soloq_champ_games.js、
# side_sel_2018~2025.js（歷年，跟當年那支是不同檔）、skills／assets／items／jungle／masteries…
# **一個都沒被量**。它們寫壞（來源掛了寫出半個檔、過濾把整批丟掉）時：
#   ‧ preflight ① 只跑 node --check——內容剩一半照樣是合法 JS，過
#   ‧ 健檢的資料量看不到它們 ⇒ 報告照印「✓ 沒有異常」
# 用 bytes 而不是「解析後的元素數」的三個理由（2026-09-10 實測 57 個根目錄 .js）：
#   ① 零成本（getsize；要解析是 35MB／0.32 秒，而且每班都白讀一次）
#   ② patches.js／jungle.js／masteries.js／skill_keys.js／patch_line_fix.js／patch_dir_fix.js／
#      skill_alias.js 這 7 個是多 statement 或非 JSON 字面值，js_obj 根本解不開（JSONDecodeError），
#      「頂層容器大小」會把它們整批漏掉
#   ③ 頂層鍵數對包一層的檔沒有意義（career.js 只有 8 個頂層鍵、soloq.js 2 個）
# 門檻怎麼定的（照 #98 的規矩：先量才定）：跑 45 天 734 個 commit 的 git ls-tree，統計每個檔
# 「單次縮水最大幅度」——根目錄資料檔最大 26.25%（events_extra.js 26956→19881，格式重算）、
# 其次 22.83%（side_sel.js）、21.74%（skill_keys.js）。30% ＝比史上最大的正常縮水再留 4 個百分點。
# data/data_20*.js 刻意不放進來：它們已經有列數（更準），而且 2026-08 那次 88 欄白名單重寫讓
# bytes 一次掉 56%，放進來只會逼人每次 --accept。
SHRINK_TOL = 0.30       # 一般檔：縮到基準的 70% 以下才算異常
SMALL_BYTES = 4096      # 這麼小的檔一筆資料就佔好幾個百分點（lck_groups.js 223B、data.js 164B）
SMALL_TOL = 0.50
# 不是資料檔，別放進來：第三方庫、線 2 autopilot 專管的 UI 程式碼、每班重寫的時間戳
SIZE_SKIP = ("chart.umd.min.js", "bp_live_ui.js", "push_time.js")


def file_sizes():
    """根目錄每個資料檔的 bytes（讀不到＝None）。刻意在函式裡才用 ROOT 組路徑（#99）。"""
    out = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "*.js"))):
        b = os.path.basename(f)
        if b in SIZE_SKIP:
            continue
        try:
            out[b] = os.path.getsize(f)
        except Exception:
            out[b] = None
    return out


def size_tol(base):
    """小檔用寬門檻：4KB 的檔少一筆資料就是好幾個百分點，用 30% 會每次改判例都吵。"""
    return SMALL_TOL if base < SMALL_BYTES else SHRINK_TOL


def size_problems(prev, cur, tol=None):
    """回 (要印的那一行, [異常…])。prev＝基準裡的高水位 bytes；tol 給值就蓋掉分段門檻（測試用）。

    三種異常：①**基準有、現在沒有**（檔案不見了）②讀不到 ③縮到基準的 (1-tol) 以下。
    正常時只印一行摘要（50 幾個檔逐行印會把報告淹掉，人就不看了）。
    """
    bad, worst = [], None
    for k in sorted(prev):
        if isinstance(prev[k], int) and k not in cur:
            bad.append("%s 不見了（基準 %d bytes）" % (k, prev[k]))
    for k in sorted(cur):
        v, pv = cur[k], prev.get(k)
        if v is None:
            bad.append("%s 讀不到" % k)
            continue
        if not isinstance(pv, int) or pv <= 0:
            continue                       # 新項目：先收基準，不報
        t = size_tol(pv) if tol is None else tol
        drop = (pv - v) / float(pv)
        if drop > t:
            bad.append("%s 體積縮水 %.0f%%（基準 %d → 現在 %d bytes）" % (k, drop * 100, pv, v))
        elif worst is None or drop > worst[1]:
            worst = (k, drop)
    if worst is None:
        tail = ""
    elif worst[1] > 0:
        tail = "；離門檻最近：%s -%.1f%%" % (worst[0], worst[1] * 100)
    else:
        tail = "；沒有一個比基準小"      # 全部持平或變大（每班的常態，不要印「-0.0%」讓人以為在掉）
    line = "資料檔體積：%d 個檔%s%s" % (
        len(cur), "" if not bad else "，⚠ %d 項有問題" % len(bad), tail)
    return (line, bad)


def merge_sizes(prev, cur, accept=False):
    """bytes 也採高水位：縮水與消失都不寫回基準（不然第二輪就被吃掉，跟 merge_baseline 同一個洞）。"""
    out = dict(prev)
    for k, v in cur.items():
        if v is None:
            continue                       # 讀不到就別把舊值蓋掉
        pv = prev.get(k)
        if isinstance(pv, int) and v < pv and not accept:
            continue
        out[k] = v
    if accept:
        for k in list(out):
            if k not in cur:
                del out[k]                 # 認可＝那個檔真的不該存在了
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


# ══ 逐聯賽落後哨兵（#136～#140）═══════════════════════════════════════════
# 為什麼要有這條：上面那些列數／體積／最新一場全是**全站**指標，單一聯賽整段沒收會被別的聯賽蓋過去
# ——LPL 停收三天，data_2026.js 的列數照樣天天變多、「最新一場比賽」也照樣是今天，18 個指標一個都不會叫。
# 真相來源＝Leaguepedia Cargo（ScoreboardGames），比對「wiki 有、我們沒有」的**比賽日**（不是局數：
# 局數對不上的原因太多——BO 還沒打完、重賽、頁面分割——比賽日才是「整天沒收」的可靠訊號）。
#   ‧ 白名單 LAG_TIER1：只問我們本來就在收的六個一級聯賽。不能用「wiki 有的我們都要有」當真相，
#     wiki 還有一堆我們沒收的頁（#137 探測：PCS/2026 Season/Summer Season 38 局），六個 prefix 已逐一證過對得上。
#   ‧ 寬限 LAG_GRACE_H：開賽後 6 小時內的局不算我們落後（#137：3h 拿 126 班歷史重放誤報 2 次，
#     6h 誤報 0 而且偵測力沒掉）。
#   ‧ 門檻 LAG_THRESHOLD：落後 >= 2 個比賽日才算異常（#136：127 班歷史誤報 0）。
#   ‧ wiki 掛掉／回空陣列 ⇒ 'skip'。既不可以炸掉整份健檢，也不可以當成「沒落後」——
#     空陣列當 ok 的話，Cargo 一改欄名這條哨兵就永遠安靜。
# 這是 update_health.py **唯一**的對外連線（其餘都讀本機檔），出口只有 wiki_rows 一支，
# 測試就是接管它（update_health_test.py 第 ㉖ 組：網路六個出口全封死 + 13 種突變）。
LAG_TIER1 = ("LCK", "LPL", "LEC", "LCS", "CBLOL", "LCP")
LAG_GRACE_H = 6
LAG_WINDOW_D = 14
LAG_THRESHOLD = 2
LAG_FORM = "https://lol.fandom.com/wiki/Special:CargoExport"


def wiki_rows(since, timeout=90):
    """打 Leaguepedia Cargo，回 [{"ov":…, "dt":…}, …]。**唯一的對外出口**（測試接管這一支）。

    urllib 相關的 import 放在函式裡：健檢平常跑得很勤，模組層少載三個套件；
    測試把 urllib/socket 換掉時，函式內 import 拿到的仍是同一個（已被接管的）模組物件。"""
    import http.cookiejar
    import urllib.parse
    import urllib.request
    ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
          "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
          "Accept-Language": "en-US,en;q=0.9", "Referer": LAG_FORM}
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    try:                       # 先拿一次 cookie：直接打 CargoExport 偶爾被擋掉（#137）
        op.open(urllib.request.Request(LAG_FORM, headers=ua), timeout=30).read()
    except Exception:
        pass
    time.sleep(2)
    p = {"tables": "ScoreboardGames=SG",
         "fields": "SG.OverviewPage=ov,SG.DateTime_UTC=dt",
         "where": 'SG.DateTime_UTC >= "%s"' % since,
         "order_by": "SG.DateTime_UTC", "format": "json", "limit": "2000"}
    raw = op.open(urllib.request.Request(LAG_FORM + "?" + urllib.parse.urlencode(p),
                                         headers=ua), timeout=timeout).read()
    return json.loads(raw.decode("utf-8", "replace"))


def wiki_days(since, fetch=None, tier1=None):
    """回 (ok, {league: [開賽時間字串]}, why)。任何例外或空回應 → ok=False（呼叫端降級成略過）。"""
    tier1 = tier1 or LAG_TIER1
    try:
        rows = (fetch or wiki_rows)(since)
        if not isinstance(rows, list) or not rows:
            return False, {}, "回應不是非空陣列"
        out = collections.defaultdict(list)
        for r in rows:
            pref = (r.get("ov") or "").split("/")[0]
            if pref in tier1:
                out[pref].append(str(r.get("dt") or ""))
        return True, out, ""
    except Exception as e:
        return False, {}, "%s: %s" % (type(e).__name__, e)


def our_days(path, since, tier1=None):
    """回 (fetched_at, {league: {比賽日字串}})——我們手上那幾天。

    只收「比賽日」不收局數：#137 的試跑版還帶著一組 (時間,藍,紅,局號) 去重，但判定從頭到尾
    只看「有哪些比賽日」⇒ 每日局數沒人讀 ⇒ 那是測不到的死分支（#139 突變測試：拿掉去重全套照樣全過）。
    欄位一律 hdr.index 查（年度資料是白名單制 88 欄，欄序會變，硬編偏移遲早讀到別欄）。"""
    tier1 = tier1 or LAG_TIER1
    txt = io.open(path, encoding="utf-8").read()
    D = json.loads(txt.split("=", 1)[1].strip().rstrip(";"))
    R = D["tabs"]["RAW_DATA"]
    ix = {n: i for i, n in enumerate(R[0])}
    out = collections.defaultdict(set)
    for r in R[1:]:
        d = str(r[ix["date"]] or "")
        if d[:10] < since:
            continue
        if r[ix["league"]] in tier1:
            out[r[ix["league"]]].add(d[:10])
    return D.get("fetched_at"), out


def lag_problems(now, data_path, fetch=None, tier1=None,
                 grace_h=None, window_d=None, threshold=None):
    """回 (狀態, 訊息列表)；狀態 = "skip"（查不到）／"ok"／"bad"。

    參數全部可注入是為了測試能把每個門檻單獨當變數推——正控制才有意義
    （「寬限改 0 就翻紅」證明的是寬限真的在作用，不是這組資料本來就會過）。"""
    tier1 = tier1 or LAG_TIER1
    grace_h = LAG_GRACE_H if grace_h is None else grace_h
    window_d = window_d or LAG_WINDOW_D
    threshold = LAG_THRESHOLD if threshold is None else threshold
    since = (now - datetime.timedelta(days=window_d)).strftime("%Y-%m-%d")
    cut = (now - datetime.timedelta(hours=grace_h)).strftime("%Y-%m-%d %H:%M")
    ok, wk, why = wiki_days(since, fetch=fetch, tier1=tier1)
    if not ok:
        return "skip", ["查不到 Leaguepedia（%s）⇒ 略過逐聯賽落後檢查" % why]
    _, od = our_days(data_path, since, tier1=tier1)
    msgs, bad = [], []
    for lg in tier1:
        # since 這一刀不能只靠查詢的 where：伺服器若回了視窗外的舊局，我們這側 our_days 有濾、
        # wiki 側沒濾 ⇒ odays 空、wdays 一堆 ⇒ 停賽已久的聯賽天天被誤報（#139 沙箱第 ⑧ 組）。
        wdays = {t[:10] for t in wk.get(lg, []) if since <= t[:10] and t[:16] <= cut}
        odays = set(od.get(lg, {}))
        if not wdays and not odays:
            continue                       # 休賽中：連一行都不要佔（報告要短才有人看）
        # 用 > 不是 >=：我們「已經有」的那一天不可以再算進落後，否則真落後 1 天會被灌成 2 天
        behind = sorted(d for d in wdays if not odays or d > max(odays))
        line = "  %-6s 我們最後比賽日 %s｜wiki 之後還有 %d 個比賽日%s" % (
            lg, (max(odays) if odays else "(無)"), len(behind),
            ("：" + "、".join(behind)) if behind else "")
        if len(behind) >= threshold:
            bad.append("%s 落後 %d 個比賽日（%s）" % (lg, len(behind), "、".join(behind)))
            line += "  << 異常"
        msgs.append(line)
    return ("bad" if bad else "ok"), msgs + (["異常：" + "；".join(bad)] if bad else [])



# ══ 積分逐場「新鮮度」（#143；探針原型 autopilot/_m142_soloq_fresh_probe.py）═══════════
# 為什麼要有這一項：上面積分那三個指標（soloq.players／soloq.found／soloq_matches.files）
# 全是**數量**的高水位。dpm.lol／Riot 那頭一旦壞掉（API 改版、帳號檔錯配、逐場抓到 0 筆又不報錯），
# 這三個數字**一個都不會動**——檔案還是 425 個、選手還是 1096 位、有牌位還是 811 位，
# 只是每一個檔裡的最後一局永遠停在壞掉那一天 ⇒ 健檢一路印「✓ 沒有異常」。
# 跟 #47（讀到上一班日誌）／#49（印舊快照）／#98（列數不再變多）／#99（版本不再往前）
# 同一種病（**沒變化被讀成沒問題**）換到積分這個入口，而 ⑤c＋⑤d 每班 198 秒是整條管線最貴也最脆的一段。
# 真相來源＝逐場檔自己的 "t"（epoch ms，Riot 的對局資料帶進來的開打時間，不是我們算的）＝獨立證人。
SQF_HEAD_BYTES = 8192    # 便宜路徑每個檔只讀開頭這麼多（一局約 900 位元組，夠拿到第一局）
SQF_STALE_H = 30         # 全庫最新一局這麼久沒往前＝落後（30h＝連續兩班都沒抓到任何新局）
SQF_THIN_MIN = 20        # 「有在動」的檔少於這麼多＝總量還在、只剩零星幾個檔在動
SQF_THIN_H = 24          # 「有在動」的窗口——距**最新一局**這麼多小時內有新局就算在動
# ⚠ 稀疏那一項的窗口要釘在「最新一局」而不是「現在」（#143 寫邊界斷言時抓到的真缺陷）：
#   釘在現在的話，漏一整班（26 小時沒抓）時 24 小時內一個檔都沒有 ⇒ 稀疏當場誤報，
#   而 SQF_STALE_H=30（刻意容許「兩班之間 12h ＋ 一整班沒跑 12h ＋ 深夜空窗」）就變成一句空話：
#   真正把關的其實是 24 小時。釘在最新一局＝問「這條線上一次動的時候，有多少個帳號跟著動」，
#   兩種壞法才各自獨立：全部停了看 SQF_STALE_H，只剩零星在動看這裡。
SQF_T_RE = re.compile(r'"t":\s*(\d{10,16})')


def sqf_ts(ms):
    return "-" if not ms else datetime.datetime.fromtimestamp(ms / 1000.0).strftime("%Y-%m-%d %H:%M")


def sqf_scan(files, head_only, head_bytes=None):
    """回 {檔名: 該檔最大的 t}；head_only=True 只讀開頭 head_bytes 個字元（讀不到的檔算 0，不要炸）。"""
    hb = SQF_HEAD_BYTES if head_bytes is None else head_bytes
    out = {}
    for f in files:
        try:
            with io.open(f, encoding="utf-8", errors="replace") as fh:
                s = fh.read(hb) if head_only else fh.read()
        except Exception:
            out[os.path.basename(f)] = 0
            continue
        v = SQF_T_RE.findall(s)
        out[os.path.basename(f)] = max(int(x) for x in v) if v else 0
    return out


def sqf_buckets(vals, now_ms):
    """每個檔「最後一局距現在多久」的分佈（順序就是印出來的順序）。"""
    b = {"<24h": 0, "<72h": 0, "<7d": 0, "<30d": 0, ">=30d": 0, "沒有對局": 0}
    for m in vals:
        if not m:
            b["沒有對局"] += 1
            continue
        h = (now_ms - m) / 3600000.0
        if h < 24:
            b["<24h"] += 1
        elif h < 72:
            b["<72h"] += 1
        elif h < 168:
            b["<7d"] += 1
        elif h < 720:
            b["<30d"] += 1
        else:
            b[">=30d"] += 1
    return b


def soloq_fresh(now_ms=None, mdir=None, files=None,
                stale_h=None, thin_min=None, thin_h=None, head_bytes=None):
    """回 (state, 要印的那一行, [異常…])；state＝"ok"／"bad"。

    **便宜路徑與它的保險**（#142）：實測 425 個逐場檔都是新到舊排序（第一局就是最大的 t），
    所以只讀每個檔開頭 SQF_HEAD_BYTES 就夠（0.02s，整檔掃是冷 3.9s／熱 0.6s）。
    但「新到舊」是對產出端的**假設**——所以便宜路徑一旦判定落後，**先整檔重掃再下結論**：
    假設哪天壞掉只會讓這一項變慢，不會誤報。（要逐檔比對兩條路徑就跑那支探針的 --full。）

    「一個 .js 都沒有」算**異常**而不是「資料很新」：這一項存在的理由就是「沒變化被讀成沒問題」。
    """
    now_ms = time.time() * 1000 if now_ms is None else now_ms
    mdir = os.path.join(ROOT, "soloq_matches") if mdir is None else mdir
    stale_h = SQF_STALE_H if stale_h is None else stale_h
    thin_min = SQF_THIN_MIN if thin_min is None else thin_min
    thin_h = SQF_THIN_H if thin_h is None else thin_h
    files = sorted(glob.glob(os.path.join(mdir, "*.js"))) if files is None else files
    if not files:
        return ("bad", "積分逐場新鮮度：⚠ %s 一個 .js 都沒有（不是「資料很新」）" % mdir,
                ["積分逐場目錄一個 .js 都沒有（%s；不是資料很新）" % mdir])
    head = sqf_scan(files, True, head_bytes)
    mx = max(head.values())
    up = ""
    if mx and (now_ms - mx) / 3600000.0 >= stale_h:
        head = sqf_scan(files, False, head_bytes)
        mx = max(head.values())
        up = "（便宜路徑判定落後 ⇒ 已整檔重掃）"
    if not mx:
        return ("bad", "積分逐場新鮮度：⚠ %d 個檔一個 t 都沒有（格式變了？）" % len(files),
                ["積分逐場 %d 個檔一個 t 都沒有（逐場檔格式變了？）" % len(files)])
    age_h = (now_ms - mx) / 3600000.0
    bk = sqf_buckets(head.values(), now_ms)
    moved = sum(1 for m in head.values() if m and (mx - m) / 3600000.0 < thin_h)
    bad = []
    if age_h >= stale_h:
        bad.append("積分逐場最新一局已經 %.1f 小時沒往前（>%dh）——dpm.lol／Riot 那頭可能壞了，"
                   "檔數與選手數不會動" % (age_h, stale_h))
    if moved < thin_min:
        bad.append("積分逐場距最新一局 %d 小時內有新局的檔只有 %d 個（<%d）——總量還在、只剩零星檔在動"
                   % (thin_h, moved, thin_min))
    # 分桶是互斥區間、六桶全印（相加＝檔數）。#163 之前印「24h 171／72h 74／>=30d 50」：
    # 讀起來像累計（72h 比 24h 還少？），而且漏掉 3~7 天／7~30 天兩桶，加起來對不上檔數。
    line = ("積分逐場新鮮度：%s 最新一局 %s（%.1f 小時前）；%d 個檔裡跟著動 %d（距最新一局 %dh 內）"
            "；各檔最後一局距現在：<24h %d／24~72h %d／3~7天 %d／7~30天 %d／≥30天 %d／沒有對局 %d%s"
            % ("⚠" if bad else "✓", sqf_ts(mx), age_h, len(files), moved, thin_h,
               bk["<24h"], bk["<72h"], bk["<7d"], bk["<30d"], bk[">=30d"], bk["沒有對局"], up))
    return ("bad" if bad else "ok"), line, bad


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
        # 步驟清單（#101）：上面那行只印「幾個」，不跟基準比就看不出某一步從此不再跑
        _stl, _stb = step_problems(prev.get("steps") or [], step_names(lg))
        print(_stl)
        bad += _stb
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
                "shrink": "  ⚠ 縮水（基準 %s → 現在 %s）" % (pv, v),
                "missing": "  ⚠ 不見了（基準 %s）" % pv}[st]
        if st == "unreadable":
            bad.append("%s 讀不到" % k)
        elif st == "shrink":
            bad.append("%s 縮水 %d → %d" % (k, pv, v))
        elif st == "missing":
            bad.append("%s 不見了（基準 %d，檔案被刪或路徑改了）" % (k, pv))
        print("   %-22s %s%s" % (k, "－" if v is None else v, flag))
    # 資料檔體積（#100）：上面 18 個指標之外，根目錄那 50 幾個資料檔一個都沒被量過
    fs = file_sizes()
    sline, sbad = size_problems(prev.get("sizes") or {}, fs)
    print("   " + sline)
    bad += sbad
    # 最新一場比賽（#98）：列數擋「變少」，這行擋「不再變多」
    lline, lbad = latest_problems(prev.get("latest") or {}, lt, time.time())
    print("   " + lline)
    bad += lbad
    # 積分逐場新鮮度（#143）：上面 soloq 那三個指標全是**數量**，抓壞了一個都不會動（#142）
    if "--no-soloqfresh" in sys.argv:
        print("   積分逐場新鮮度：（--no-soloqfresh 跳過）")
    else:
        _sqst, _sqline, _sqbad = soloq_fresh()
        print("   " + _sqline)
        bad += _sqbad
    # 遊戲版本（#99）：比賽資料以外，patch notes／DDragon 也會靜靜地停在舊版
    gv = game_versions()
    vline, vbad, vsince = version_problems(prev.get("versions") or {}, gv,
                                           prev.get("version_mismatch_since"), time.time())
    print("   " + vline)
    bad += vbad
    # 逐聯賽落後（#140）：上面全是全站指標，單一聯賽整段沒收會被別的聯賽蓋過去。
    # 這是整份健檢唯一會連外的一項（~3 秒）；wiki 掛掉只降級成「略過」，不影響其餘結論。
    if "--no-lag" in sys.argv:
        print("   逐聯賽落後：（--no-lag 跳過）")
    else:
        _lst, _lmsgs = lag_problems(datetime.datetime.utcnow(),
                                    os.path.join(ROOT, "data", "data_2026.js"))
        print("   逐聯賽落後（近 %d 天／寬限 %dh／門檻 %d 個比賽日）：%s" % (
            LAG_WINDOW_D, LAG_GRACE_H, LAG_THRESHOLD,
            {"skip": "略過（查不到 Leaguepedia）", "ok": "✓ 六個一級聯賽都跟上", "bad": "⚠ 有落後"}[_lst]))
        for _m in _lmsgs:
            print("   " + _m)
        if _lst == "bad":
            bad += [_m[3:] for _m in _lmsgs if _m.startswith("異常：")]
    print("")
    print("結論：" + ("✓ 沒有異常" if not bad else "⚠ " + "；".join(bad)))
    if any(("縮水" in b or "不見了" in b) for b in bad):
        print("（縮水／不見了的項目**不會**寫回基準，會一直報到你確認為止；"
              "確認資料真的變少就跑 python scripts\\update_health.py --accept）")
    if "--no-save" not in sys.argv:
        os.makedirs(os.path.dirname(BASE), exist_ok=True)
        json.dump({"at": time.strftime("%Y-%m-%d %H:%M"),
                   "counts": merge_baseline(pc, dc, accept),
                   "latest": merge_latest(prev.get("latest") or {}, lt, accept),
                   "sizes": merge_sizes(prev.get("sizes") or {}, fs, accept),
                   "steps": merge_steps(prev.get("steps") or [], step_names(lg), accept),
                   "last_steps": step_names(lg),
                   "last_sizes": fs,
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
