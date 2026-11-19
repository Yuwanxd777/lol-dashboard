# -*- coding: utf-8 -*-
"""轉會每小時更新（使用者 2026-11-20「新網頁每一個小時更新一次」「轉會分頁也每小時更新一次 轉會分頁先更新 10 分鐘後再更新新網頁」）。

  python scripts/transfers_hourly.py main   整點：抓轉會（fetch_transfers）→ 匯出轉會網站檔（export_transfer_site）
                                            → 只 commit 這三個檔 → preflight 通過才 push（主站轉會分頁更新）
  python scripts/transfers_hourly.py site   10 分：三個檔複製到 轉會網站\\www\\fallback → wrangler 部署 lol-transfer.pages.dev

排程：工作排程器 LOL_Transfers_Main（每小時 :00）、LOL_Transfers_Site（每小時 :10），由 transfers_hourly.vbs 隱藏執行。
跳過條件：10／22 點（publish.bat 那班本來就會更新＋推）、LOL_Dashboard_Update 正在跑、autopilot\\STREAM 存在（直播中不跑吃 CPU 的無頭頁）。
⚠ push 會把本機所有還沒推的 commit 一起推上去（GitHub Pages 只有一條分支）⇒ 推之前一定跑 preflight，失敗就不推。
紀錄寫自己的 transfers_hourly_log.txt（不要寫進 update_log.txt：那是 publish 的）。
"""
import datetime
import io
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SITE = os.path.join(os.path.dirname(ROOT), "轉會網站")
LOG = os.path.join(ROOT, "transfers_hourly_log.txt")
FILES = ["transfers.js", "transfers_site.js", "transfers_site_code.js"]
GIT = r"C:\Program Files\Git\cmd\git.exe"
NPX = r"C:\Program Files\nodejs\npx.cmd"
ENV = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never", GIT_HTTP_LOW_SPEED_LIMIT="1000", GIT_HTTP_LOW_SPEED_TIME="60",
           PYTHONIOENCODING="utf-8")


def log(msg):
    line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line)
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(cmd, cwd=ROOT, timeout=1200):
    r = subprocess.run(cmd, cwd=cwd, env=ENV, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    tail = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-3:]
    log(f"  {' '.join(os.path.basename(str(c)) for c in cmd[:3])} → {r.returncode}｜{' / '.join(tail)[:300]}")
    return r.returncode


def publish_running():
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-ScheduledTask -TaskName LOL_Dashboard_Update).State"],
                           capture_output=True, text=True, timeout=30)
        return "Running" in (r.stdout or "")
    except Exception:
        return False


def skip_reason():
    h = datetime.datetime.now().hour
    if h in (10, 22):
        return "10／22 點由 publish.bat 那班更新"
    if publish_running():
        return "LOL_Dashboard_Update 正在跑"
    if os.path.exists(os.path.join(ROOT, "autopilot", "STREAM")):
        return "直播中（autopilot\\STREAM）"
    return ""


def do_main():
    py = sys.executable
    if run([py, "scripts/fetch_transfers.py"]) != 0:
        log("  fetch_transfers 失敗，沿用舊資料繼續")
    if run([py, "scripts/export_transfer_site.py", "--head"]) != 0:
        log("  export_transfer_site 失敗，不推")
        return
    if "--dry" in sys.argv:
        log("  --dry：不 commit／不推")
        return
    run([GIT, "add", "--"] + FILES)
    if subprocess.run([GIT, "diff", "--cached", "--quiet", "--"] + FILES, cwd=ROOT, env=ENV).returncode == 0:
        log("  轉會資料沒變")
    else:
        run([GIT, "commit", "-m", f"轉會每小時更新 {datetime.datetime.now():%Y-%m-%d %H:%M}", "--"] + FILES)
    ahead = subprocess.run([GIT, "rev-list", "--count", "@{u}..HEAD"], cwd=ROOT, env=ENV, capture_output=True, text=True).stdout.strip()
    if ahead in ("", "0"):
        log("  沒有要推的 commit")
        return
    if run([py, "scripts/preflight_check.py"], timeout=1800) != 0:
        log("  ⚠ preflight 失敗，不推（下一班 publish 會再試）")
        return
    run([GIT, "push"], timeout=600)


def do_site():
    dst = os.path.join(SITE, "www", "fallback")
    os.makedirs(dst, exist_ok=True)
    for f in FILES:
        shutil.copy2(os.path.join(ROOT, f), os.path.join(dst, f))
    # 一定要在 轉會網站 資料夾跑（在 C:\fit 跑會把訓練計畫的 functions 一起傳上去）
    run([NPX, "--yes", "wrangler", "pages", "deploy", "www", "--project-name", "lol-transfer", "--branch", "main", "--commit-dirty=true"],
        cwd=SITE, timeout=600)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode not in ("main", "site"):
        raise SystemExit("用法：transfers_hourly.py main|site")
    why = skip_reason() if mode == "main" else ""
    if why:
        log(f"[{mode}] 跳過：{why}")
        return
    log(f"[{mode}] 開始")
    (do_main if mode == "main" else do_site)()
    log(f"[{mode}] 結束")


if __name__ == "__main__":
    main()
