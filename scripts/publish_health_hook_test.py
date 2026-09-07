# -*- coding: utf-8 -*-
"""精進迴圈 #45：publish.bat 健檢區塊的端到端測試（不碰真的資料、不跑真的管線）。

做法：把 publish.bat 裡「push 之後」那一整段**原文抽出來**（不是手打複本，手打的複本
會跟真檔漂移，測了等於沒測），在暫存資料夾裡配一支假的 scripts/update_health.py
（離開碼由環境變數 FAKE_RC 決定），用 cmd 真的跑一遍，檢查：

  RC=1（健檢說有異常）   → update_health_log.txt 有內容、autopilot/HEALTH_ALERT.txt 被建出來且內容一致、
                          結論有 append 進 update_log.txt（原有內容不能被蓋掉）、**整支 .bat 離開碼 0**
  RC=0（健檢正常）       → HEALTH_ALERT.txt 被刪掉、結論一樣 append 進 update_log.txt、離開碼 0
  RC=9009（python 不見） → 當成異常，留下 HEALTH_ALERT.txt

另外做突變對照（防恆綠）：把區塊裡的 del／copy／type 各拿掉一行，測試必須變紅。

用法：python scripts/publish_health_hook_test.py
"""
import io
import os
import shutil
import subprocess
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAT = os.path.join(ROOT, "publish.bat")
TMP = os.path.join(ROOT, "autopilot", "_publish_hook_bt")

START = "rem data health check"
END = "echo publish done."

STUB = (
    "# -*- coding: utf-8 -*-\n"
    "import io, os, sys\n"
    "sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')\n"
    "print('=== 假健檢 ===')\n"
    "print('結論：中文測試字串 shrink 縮水 ok')\n"
    "sys.exit(int(os.environ.get('FAKE_RC', '0')))\n"
)

OLD_LOG = "==== previous run ====\n舊的日誌內容不可以被蓋掉\n"


def extract_block(text):
    i = text.index(START)
    j = text.index(END, i)
    return text[i:j]


def build(block):
    if os.path.isdir(TMP):
        shutil.rmtree(TMP)
    os.makedirs(os.path.join(TMP, "scripts"))
    os.makedirs(os.path.join(TMP, "autopilot"))
    io.open(os.path.join(TMP, "scripts", "update_health.py"), "w",
            encoding="utf-8", newline="\n").write(STUB)
    io.open(os.path.join(TMP, "update_log.txt"), "w",
            encoding="utf-8", newline="\n").write(OLD_LOG)
    bat = ('@echo off\r\ncd /d "%~dp0"\r\n' + block
           + "echo publish done. see update_log.txt for details.\r\nexit /b 0\r\n")
    io.open(os.path.join(TMP, "t.bat"), "wb").write(bat.encode("ascii"))


def run(rc):
    env = dict(os.environ, FAKE_RC=str(rc))
    p = subprocess.run(["cmd", "/c", os.path.join(TMP, "t.bat")],
                       capture_output=True, env=env)
    return p.returncode


def read(rel):
    p = os.path.join(TMP, rel)
    if not os.path.exists(p):
        return None
    return io.open(p, encoding="utf-8", errors="replace").read()


FAILS = []


def ck(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        FAILS.append(msg)


def scenario(block, label, expect_pass=True):
    """跑三種離開碼，回傳有沒有全過。"""
    global FAILS
    FAILS = []
    build(block)

    print("[%s] RC=1（健檢說異常）" % label)
    code = run(1)
    ck(code == 0, "publish.bat 整支離開碼 0（不可以因為健檢紅了就讓排程看起來失敗），實際 %s" % code)
    hl = read("update_health_log.txt")
    ck(hl is not None and "假健檢" in hl, "健檢輸出寫進自己的 update_health_log.txt")
    al = read("autopilot/HEALTH_ALERT.txt")
    ck(al is not None, "異常時建出 autopilot/HEALTH_ALERT.txt")
    ck(al == hl, "警示檔內容與健檢輸出一致")
    lg = read("update_log.txt")
    ck(lg is not None and OLD_LOG.split("\n")[1] in lg, "update_log.txt 原有內容還在（是 append 不是覆寫）")
    ck(lg is not None and "結論：中文測試字串" in lg, "健檢結論有折進 update_log.txt")
    ck(lg is not None and lg.count("=== 假健檢 ===") == 1, "只折進去一次")

    print("[%s] RC=0（健檢正常）→ 警示檔要消失" % label)
    code = run(0)
    ck(code == 0, "離開碼 0，實際 %s" % code)
    ck(read("autopilot/HEALTH_ALERT.txt") is None, "正常時 HEALTH_ALERT.txt 被清掉")
    lg = read("update_log.txt")
    ck(lg is not None and lg.count("=== 假健檢 ===") == 2, "第二次的結論也 append 進去（共 2 次）")

    print("[%s] RC=9009（python 不見／指令失敗）" % label)
    run(9009)
    ck(read("autopilot/HEALTH_ALERT.txt") is not None, "非 1 的非零離開碼一樣算異常，留下警示檔")

    ok = not FAILS
    print("[%s] %s" % (label, "全過" if ok else "紅 %d 條：%s" % (len(FAILS), "；".join(FAILS))))
    if expect_pass and not ok:
        return False
    if not expect_pass and ok:
        print("  ⚠ 突變沒有被抓到（測試是恆綠的）")
        return False
    return True


def main():
    txt = io.open(BAT, "rb").read().decode("ascii")
    block = extract_block(txt)
    print("抽出的區塊 %d 字元、%d 行\n" % (len(block), block.count("\r\n")))
    good = scenario(block, "真實區塊", expect_pass=True)

    # ── 突變對照：每個關鍵行拿掉一行，測試都必須變紅 ──────────────────────
    muts = [("刪掉 del 那行（警示檔永遠不會清）", "  if exist autopilot\\HEALTH_ALERT.txt del autopilot\\HEALTH_ALERT.txt\r\n"),
            ("刪掉 copy 那行（異常時不留警示檔）", "  copy /y update_health_log.txt autopilot\\HEALTH_ALERT.txt >nul\r\n"),
            ("刪掉 type 那行（結論不進日誌）", "type update_health_log.txt >> update_log.txt\r\n")]
    mut_ok = True
    for name, line in muts:
        print("\n── 突變：%s ──" % name)
        assert line in block, "突變目標不在區塊裡：" + name
        if not scenario(block.replace(line, ""), "突變", expect_pass=False):
            mut_ok = False

    # 再加一個「覆寫而非追加」的突變：>> 改成 >
    print("\n── 突變：type 用 >（會蓋掉整份 update_log.txt）──")
    if not scenario(block.replace("type update_health_log.txt >> update_log.txt",
                                  "type update_health_log.txt > update_log.txt"),
                    "突變", expect_pass=False):
        mut_ok = False

    shutil.rmtree(TMP, ignore_errors=True)
    print("\n════ 結果：真實區塊 %s／突變對照 %s ════"
          % ("通過" if good else "失敗", "全被抓到" if mut_ok else "有漏網"))
    return 0 if (good and mut_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
