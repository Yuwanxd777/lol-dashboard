# -*- coding: utf-8 -*-
"""lolsoloq:// 自訂協定處理器 —— 讓積分頁「🔄 更新積分」按鈕能自己把本機服務帶起來（使用者 2026-10-22）。

    lolsoloq://start   → 背景啟動 soloq_key_server.py（pythonw、無主控台視窗，輸出寫 scripts/soloq_key_server.log）

註冊：雙擊 註冊積分更新協定.bat（只寫 HKCU，不需系統管理員；只要一次）。
跟 bplive:// 分開：bplive 那支由 autopilot 專管。
"""
import json, os, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SRV = os.path.join(HERE, "soloq_key_server.py")
LOG = os.path.join(HERE, "soloq_key_server.log")
API = "http://127.0.0.1:8177"
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008


def alive(timeout=1.0):
    try:
        json.loads(urllib.request.urlopen(API + "/ping", timeout=timeout).read().decode("utf-8"))
        return True
    except Exception:
        return False


def start():
    if alive():
        return 0
    exe = sys.executable
    pw = os.path.join(os.path.dirname(exe), "pythonw.exe")   # 無主控台，不跳黑視窗搶焦點
    if os.path.exists(pw):
        exe = pw
    lf = open(LOG, "a", encoding="utf-8")
    lf.write("\n==== %s 由 lolsoloq://start 啟動 ====\n" % time.strftime("%Y-%m-%d %H:%M:%S")); lf.flush()
    subprocess.Popen([exe, SRV], cwd=ROOT, stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                     creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS, close_fds=True)
    for _ in range(40):                                       # 最多等 20 秒
        if alive(0.5):
            return 0
        time.sleep(0.5)
    return 1


if __name__ == "__main__":
    sys.exit(start())
