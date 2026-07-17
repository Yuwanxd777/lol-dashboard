# -*- coding: utf-8 -*-
"""Git 倉庫瘦身：把整段歷史壓成單一提交（內容不變），強制推送後本地 gc。
背景：soloq_matches ~90MB 每日重寫，歷史會無限膨脹（.git 已 175MB+）；資料倉庫的歷史沒有保留價值。
安全網：執行前先把完整歷史打包成 bundle 放到桌面（LOL儀表板_git_backup_日期.bundle，可隨時還原）。
用法：python scripts\git_slim.py [--yes]（無 --yes 時只顯示將執行的動作）
"""
import io, sys, os, subprocess, datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
GIT = r"C:\Program Files\Git\cmd\git.exe"
YES = "--yes" in sys.argv

def run(*args, ok_fail=False):
    print("  $ git", " ".join(args))
    r = subprocess.run([GIT, "-C", ROOT, *args], capture_output=True, text=True)
    if r.stdout.strip(): print("   ", r.stdout.strip()[:300])
    if r.returncode != 0:
        print("   ✗", (r.stderr or "").strip()[:300])
        if not ok_fail: sys.exit(1)
    return r

# 前置檢查：工作區必須乾淨（先 commit 再瘦身）
st = subprocess.run([GIT, "-C", ROOT, "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
if st:
    print("✗ 工作區有未提交變更，先 commit（或跑 publish.bat）再瘦身。"); sys.exit(1)

day = datetime.date.today().strftime("%Y%m%d")
bundle = os.path.join(os.path.expanduser("~"), "Desktop", f"LOL儀表板_git_backup_{day}.bundle")
print(f"步驟：① 備份完整歷史 → {bundle}\n     ② 孤兒分支壓成單一提交 ③ 強制推送 origin/main ④ 本地 gc 清舊物件")
if not YES:
    print("（試跑模式：加 --yes 才會真的執行）"); sys.exit(0)

run("bundle", "create", bundle, "--all")
run("checkout", "--orphan", "_slim")
run("add", "-A")
run("commit", "-m", f"squashed history {day} (content unchanged; full history in Desktop bundle)")
run("branch", "-M", "_slim", "main")
run("push", "-f", "origin", "main")
run("reflog", "expire", "--expire=now", "--all", ok_fail=True)
run("gc", "--prune=now", "--aggressive", ok_fail=True)
sz = subprocess.run([GIT, "-C", ROOT, "count-objects", "-vH"], capture_output=True, text=True).stdout
print(sz)
print(f"✓ 完成。完整歷史備份在 {bundle}（確認一切正常後可自行刪除）。")
