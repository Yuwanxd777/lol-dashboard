# -*- coding: utf-8 -*-
"""精進迴圈 #46：publish.bat 的「守門 → push → 健檢 → 離開碼」整條控制流測試。

為什麼要有這一支（#45 的 publish_health_hook_test.py 補不到的洞）：
  #45 那支只抽「rem data health check … 」那一段來測，等於**預設健檢一定跑得到**。
  但當時的 publish.bat 在 preflight 失敗時是 `exit /b 1` 當場離開，健檢整段被跳過
  ⇒ 最嚴重的一班（資料壞掉、根本沒 push）反而是唯一**不會**留下 autopilot\\HEALTH_ALERT.txt 的一班，
  而 DAILY.md 的固定檢查點把「沒有警示檔」讀成「上一班沒問題」。這支測的就是那條路徑。

做法跟 #45 同一套：把 publish.bat 從 `rem gate:` 到**檔尾**的整段**原文抽出來**
（手打複本會跟真檔漂移，測了等於沒測），在暫存夾配三支替身，用 cmd 真的跑：
  scripts\\preflight_check.py  假的，離開碼 = 環境變數 FAKE_PRE_RC
  scripts\\update_health.py    假的，離開碼 = 環境變數 FAKE_RC
  fakegit.py                   假的 git，只把自己的參數印進 update_log.txt（驗 push 有沒有真的跑）

四種組合：
  守門 0 ／健檢 0 → git 三行都跑、無警示檔、離開碼 0
  守門 0 ／健檢 1 → git 三行都跑、留警示檔、離開碼**仍是 0**（健檢只告知不擋發布）
  守門 1 ／健檢 1 → **git 一行都不跑**、**健檢照樣跑**、留警示檔、離開碼 1
  守門 1 ／健檢 0 → git 不跑、健檢照樣跑、舊警示檔被清掉、離開碼 1
2026-09-21 #179 起同一段還多了「每班自己留底」（publish.bat 最末段叫 shift_log_archive.py），
所以四種組合也一起驗：留底每一班都跑到、輸出在自己的檔、帶 --from-publish、
而且排在最後（抄到的那份含得到健檢結論與 PREFLIGHT FAILED）。

再加七個突變對照（防恆綠），其中「set PUBRC=1 改回 exit /b 1」就是修好之前的原樣。
最後一節是跨檔契約：真的 update_health.py 讀到 PREFLIGHT FAILED 必須 return 1
（.bat 只負責把它叫起來，判斷是誰壞了要看得出來）。

用法：python scripts/publish_gate_flow_test.py
"""
import io
import os
import shutil
import subprocess
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAT = os.path.join(ROOT, "publish.bat")
TMP = os.path.join(ROOT, "autopilot", "_publish_gate_bt")
BS = chr(92)

START = "rem gate: data-file syntax"
GIT_LINE = 'set GIT="C:' + BS + 'Program Files' + BS + 'Git' + BS + 'cmd' + BS + 'git.exe"'

PRE_STUB = (
    "# -*- coding: utf-8 -*-\n"
    "import io, os, sys\n"
    "sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')\n"
    "rc = int(os.environ.get('FAKE_PRE_RC', '0'))\n"
    "print('守門通過' if rc == 0 else '守門擋下：假的資料檔壞了')\n"
    "sys.exit(rc)\n"
)
HEALTH_STUB = (
    "# -*- coding: utf-8 -*-\n"
    "import io, os, sys\n"
    "sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')\n"
    "print('=== 假健檢 ===')\n"
    "print('結論：假健檢的結論字串')\n"
    "sys.exit(int(os.environ.get('FAKE_RC', '0')))\n"
)
# 假 git 一定要是 python 腳本、不能是 .bat：cmd 裡不加 call 直接叫另一支 .bat 會
# **轉移控制權且不再回來**，區塊之後的健檢就永遠不會跑——那是替身造成的假象
# （真檔叫的是 git.exe，exe 不會轉移控制權）。2026-09-07 #46 第一版就踩到，
# 讓「守門通過」那兩個情境紅了 3 條假紅，差點被當成 publish.bat 有問題。
FAKE_GIT = (
    "# -*- coding: utf-8 -*-\n"
    "import os, sys\n"
    "print('FAKEGIT ' + ' '.join(sys.argv[1:]))\n"
    # #208：publish.bat 要在 git 之前 set 四個「不等人」環境變數；假 git 把看到的印出來給下面斷言
    "print('FAKEGIT-ENV ' + '|'.join(k + '=' + os.environ.get(k, '<unset>') for k in "
    "('GIT_TERMINAL_PROMPT', 'GCM_INTERACTIVE', 'GIT_HTTP_LOW_SPEED_LIMIT', 'GIT_HTTP_LOW_SPEED_TIME')))\n"
)
# 2026-09-21 #179：publish.bat 最末段多了「每班自己留底」。假的歸檔器只做兩件事——
# 把當下的 update_log.txt 原封不動抄一份出來、印一行證明自己跑過——這樣就測得出
# ①它每一班都跑（**尤其是守門擋下、沒發布的那一班**，那正是最需要證據的一班）
# ②它排在整支的最後（抄到的那一份要含得到健檢結論）。
ARCHIVE_STUB = (
    "# -*- coding: utf-8 -*-\n"
    "import io, os, sys\n"
    "sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')\n"
    "root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n"
    "txt = io.open(os.path.join(root, 'update_log.txt'), encoding='utf-8',\n"
    "              errors='replace').read()\n"
    "d = os.path.join(root, 'autopilot', 'shift_logs')\n"
    "os.makedirs(d, exist_ok=True)\n"
    "io.open(os.path.join(d, 'archived.txt'), 'w', encoding='utf-8').write(txt)\n"
    "print('FAKEARCHIVE ' + ' '.join(sys.argv[1:]))\n"
)
OLD_LOG = "==== previous run ====\r\n舊的日誌內容不可以被蓋掉\r\n"

FAILS = []


def ck(cond, msg):
    print(("  OK  " if cond else "  紅  ") + msg)
    if not cond:
        FAILS.append(msg)


def extract_block(text):
    return text[text.index(START):]          # 一路抽到檔尾（含 exit /b %PUBRC%）


def build(block):
    if os.path.isdir(TMP):
        shutil.rmtree(TMP)
    os.makedirs(os.path.join(TMP, "scripts"))
    os.makedirs(os.path.join(TMP, "autopilot"))
    io.open(os.path.join(TMP, "scripts", "preflight_check.py"), "w",
            encoding="utf-8", newline="\n").write(PRE_STUB)
    io.open(os.path.join(TMP, "scripts", "update_health.py"), "w",
            encoding="utf-8", newline="\n").write(HEALTH_STUB)
    io.open(os.path.join(TMP, "scripts", "shift_log_archive.py"), "w",
            encoding="utf-8", newline="\n").write(ARCHIVE_STUB)
    io.open(os.path.join(TMP, "fakegit.py"), "w",
            encoding="utf-8", newline="\n").write(FAKE_GIT)
    io.open(os.path.join(TMP, "update_log.txt"), "w",
            encoding="utf-8", newline="").write(OLD_LOG)
    body = block.replace(GIT_LINE, 'set GIT=python "%~dp0fakegit.py"')
    bat = '@echo off\r\ncd /d "%~dp0"\r\n' + body
    io.open(os.path.join(TMP, "t.bat"), "wb").write(bat.encode("ascii"))


def run(pre_rc, health_rc):
    env = dict(os.environ, FAKE_PRE_RC=str(pre_rc), FAKE_RC=str(health_rc))
    env.pop("PUBRC", None)
    for k in ('GIT_TERMINAL_PROMPT', 'GCM_INTERACTIVE', 'GIT_HTTP_LOW_SPEED_LIMIT', 'GIT_HTTP_LOW_SPEED_TIME'):
        env.pop(k, None)             # #208：四個防呆變數只能來自 publish.bat 自己 set 的
    p = subprocess.run(["cmd", "/c", os.path.join(TMP, "t.bat")],
                       capture_output=True, env=env)
    return p.returncode


def read(rel):
    p = os.path.join(TMP, rel)
    return io.open(p, encoding="utf-8", errors="replace").read() if os.path.exists(p) else None


def scenario(block, label, expect_pass=True):
    global FAILS
    FAILS = []

    print("[%s] 守門 0 ／健檢 0（正常的一班）" % label)
    build(block)
    code = run(0, 0)
    lg = read("update_log.txt") or ""
    ck(code == 0, "離開碼 0，實際 %s" % code)
    ck("FAKEGIT add" in lg and "FAKEGIT commit" in lg and "FAKEGIT push" in lg,
       "git add／commit／push 三行都跑到")
    ck("FAKEGIT-ENV GIT_TERMINAL_PROMPT=0|GCM_INTERACTIVE=never|GIT_HTTP_LOW_SPEED_LIMIT=1000|GIT_HTTP_LOW_SPEED_TIME=60" in lg,
       "git 看得到四個不等人的環境變數（#208：認證視窗不彈、終端不問、停滯 60 秒就斷）")
    ck(read("update_health_log.txt") is not None, "健檢有跑（有自己的 log）")
    ck(read("autopilot/HEALTH_ALERT.txt") is None, "沒有警示檔")
    ck("結論：假健檢的結論字串" in lg, "健檢結論折進 update_log.txt")
    ck("舊的日誌內容不可以被蓋掉" in lg, "原有日誌內容還在")
    ar = read("shift_archive_log.txt") or ""
    ck("FAKEARCHIVE" in ar, "留底有跑（有自己的 log，沒有導回 update_log.txt）")
    ck("--from-publish" in ar, "留底帶 --from-publish（台帳分得出是班次還是手動）")
    ck("FAKEARCHIVE" not in lg, "留底的輸出沒有混進 update_log.txt")
    ck("結論：假健檢的結論字串" in (read("autopilot/shift_logs/archived.txt") or ""),
       "留底排在最後：歸檔的那一份含得到健檢結論")

    print("[%s] 守門 0 ／健檢 1（資料有異常但守門過了）" % label)
    build(block)
    code = run(0, 1)
    lg = read("update_log.txt") or ""
    ck(code == 0, "離開碼仍是 0（健檢只告知不擋發布），實際 %s" % code)
    ck("FAKEGIT push" in lg, "push 照跑")
    ck(read("autopilot/HEALTH_ALERT.txt") is not None, "留下 HEALTH_ALERT.txt")

    print("[%s] 守門 1 ／健檢 1（最嚴重的一班：資料壞了、沒 push）" % label)
    build(block)
    code = run(1, 1)
    lg = read("update_log.txt") or ""
    hl = read("update_health_log.txt")
    al = read("autopilot/HEALTH_ALERT.txt")
    ck(code == 1, "離開碼 1（讓排程看得出這一班沒發布），實際 %s" % code)
    ck("FAKEGIT" not in lg, "git 一行都沒跑（絕不發布壞資料）")
    ck("PREFLIGHT FAILED" in lg, "日誌寫下 PREFLIGHT FAILED")
    ck(hl is not None and "假健檢" in hl, "**健檢照樣跑**（這就是 #46 修的洞）")
    ck(al is not None, "**留下 autopilot/HEALTH_ALERT.txt**（迴圈靠它知道上一班有問題）")
    ck(al == hl, "警示檔內容與健檢輸出一致")
    ck("結論：假健檢的結論字串" in lg, "健檢結論一樣折進 update_log.txt")
    ck("FAKEARCHIVE" in (read("shift_archive_log.txt") or ""),
       "**留底照樣跑**（沒發布的這一班最需要留證據：09-17 22:00 就是這樣查不到的）")
    ck("PREFLIGHT FAILED" in (read("autopilot/shift_logs/archived.txt") or ""),
       "歸檔的那一份寫著 PREFLIGHT FAILED（事後查得出這一班為什麼沒發布）")

    print("[%s] 守門 1 ／健檢 0（守門失敗但健檢說乾淨）" % label)
    build(block)
    io.open(os.path.join(TMP, "autopilot", "HEALTH_ALERT.txt"), "w",
            encoding="utf-8").write("上一班留下的舊警示")
    code = run(1, 0)
    lg = read("update_log.txt") or ""
    ck(code == 1, "離開碼 1，實際 %s" % code)
    ck("FAKEGIT" not in lg, "git 沒跑")
    ck(read("update_health_log.txt") is not None, "健檢照樣跑")
    ck(read("autopilot/HEALTH_ALERT.txt") is None,
       "健檢說乾淨就清掉舊警示（else 分支在守門失敗這條路上也走得到）")

    ok = not FAILS
    print("[%s] %s\n" % (label, "全過" if ok else "紅 %d 條：%s" % (len(FAILS), "；".join(FAILS))))
    if expect_pass:
        return ok
    if ok:
        print("  ⚠ 突變沒有被抓到（測試是恆綠的）\n")
        return False
    return True


def _seed_repo(box):
    """給契約段一個**乾淨的假 repo**：健檢除了日誌以外沒有別的話要說。

    2026-09-10 #99：原本這裡是 `u.data_counts = lambda: {}`（只為了不要讀 194MB），
    #98 把簽名改成 `data_counts(latest_out=None)`、main 改成 `data_counts(lt)` 之後，
    那個 0 參數 lambda 一叫就 TypeError ⇒ main 當場炸掉 ⇒ **離開碼照樣是 1**（契約的第一條
    因此變成假綠），第二條「結論裡指名 preflight 失敗」則因為根本沒印出結論而紅。
    改成種一份假 repo、只接管 ROOT／LOG／BASE：不再對被測模組的內部簽名有任何假設。
    """
    import datetime
    import json
    import time
    today = datetime.date.fromtimestamp(time.time())
    hdr = ["league", "split", "date", "game", "patch"]
    body = [hdr] + [["LPL", "S3", str(today - datetime.timedelta(days=i)), str(i), "16.17"]
                    for i in range(3)]
    os.makedirs(os.path.join(box, "data"), exist_ok=True)
    os.makedirs(os.path.join(box, "csv_cache"), exist_ok=True)
    os.makedirs(os.path.join(box, "soloq_matches"), exist_ok=True)
    io.open(os.path.join(box, "data", "data_2026.js"), "w", encoding="utf-8").write(
        "window.LOL_DATA=" + json.dumps({"tabs": {"RAW_DATA": body}}) + ";")
    io.open(os.path.join(box, "soloq.js"), "w", encoding="utf-8").write(
        "window.SOLOQ=" + json.dumps({"players": [{"found": True}]}) + ";")
    io.open(os.path.join(box, "side_sel.js"), "w", encoding="utf-8").write("window.SIDE=[1,2,3];")
    # #164：#144 起健檢會讀逐場檔的 "t"（積分逐場新鮮度：最新一局 <30h、>=20 個檔跟著動），
    # 只寫 "x" ⇒ 判「一個 t 都沒有」⇒ 所有「乾淨＝沒有異常」的斷言恆紅。
    for _i in range(25):
        io.open(os.path.join(box, "soloq_matches", "p%02d.js" % _i), "w", encoding="utf-8").write(
            'window.SQM=[{"t":%d}];' % int((time.time() - 3600) * 1000))
    io.open(os.path.join(box, "patches.js"), "w", encoding="utf-8").write(
        'window.LOL_PATCHES={"26.17":{"A":["x"]}};')
    io.open(os.path.join(box, "patches_en.js"), "w", encoding="utf-8").write(
        'window.LOL_PATCHES_EN={"26.17":{"A":["x"]}};')
    io.open(os.path.join(box, "skills.js"), "w", encoding="utf-8").write(
        "window.SKILLS=" + json.dumps({"v": "16.17.1", "d": {}}) + ";")
    io.open(os.path.join(box, "assets.js"), "w", encoding="utf-8").write(
        "window.ASSETS=" + json.dumps({"years": {"2026": "16.17.1"}}) + ";")
    json.dump({"26.17": str(today - datetime.timedelta(days=16))},
              io.open(os.path.join(box, "csv_cache", "patch_dates.json"), "w", encoding="utf-8"))


def contract():
    """跨檔契約：真的 update_health.py 讀到 PREFLIGHT FAILED 必須 return 1、乾淨日誌必須 return 0。"""
    print("── 契約：真的 update_health.py vs PREFLIGHT FAILED ──")
    os.makedirs(TMP, exist_ok=True)
    box = os.path.join(TMP, "c_repo")
    shutil.rmtree(box, ignore_errors=True)
    os.makedirs(box)
    _seed_repo(box)
    # 時間戳要用「現在」：寫死日期會讓 #48 的班次點名報「沒有這一班的日誌」，
    # 正控制那條（乾淨日誌 ⇒ 離開碼 0）就永遠成立不了
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log = os.path.join(TMP, "c_log.txt")
    base = os.path.join(TMP, "c_base.json")
    io.open(log, "w", encoding="utf-8").write(
        "==== run_update " + stamp + "（並行 4）====\n"
        "---- fetch_x（12.3s，exit 0）----\n"
        "PREFLIGHT FAILED - push skipped. see update_log.txt\n")
    code = ("import sys; sys.path.insert(0, r'%s');"
            "import update_health as u;"
            "u.ROOT = r'%s'; u.LOG = r'%s'; u.CONSOLE = r'%s'; u.BASE = r'%s';"
            # #164：接管 wiki 出口（#144 起 main 會連 Leaguepedia）＋封網保險絲：撞到就在 stderr 留 NETHIT（ssl 要先載入，否則換掉 socket.socket 後 import ssl 會 TypeError、靜默走略過）
            "u.wiki_rows = lambda since, timeout=90: [{'ov': 'PCS/sandbox', 'dt': since + ' 00:00'}];"
            "import ssl, http.client, urllib.request, socket as _s; _s.socket = _s.create_connection = "
            "lambda *a, **k: (sys.stderr.write('NETHIT '), (_ for _ in ()).throw(OSError('blocked')));"
            "sys.argv = ['x', '--no-save', '--no-live']; sys.exit(u.main())"
            % (os.path.join(ROOT, "scripts"), box, log, log + ".none", base))
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, cwd=ROOT)
    out = p.stdout.decode("utf-8", "replace")
    ok1 = p.returncode == 1
    ok2 = "preflight 失敗、沒有 push" in out
    ck(ok1, "離開碼 1，實際 %s" % p.returncode)
    ck(ok2, "結論裡指名「preflight 失敗、沒有 push」")
    # 正控制：同一份日誌拿掉那一行就不該再報這一條，而且整份健檢要是綠的
    # （假 repo 除了日誌以外沒別的毛病 ⇒ 離開碼 0；舊版這裡因為 main 直接炸掉，
    #   兩邊都是 1，第一條等於沒有鑑別力）
    io.open(log, "w", encoding="utf-8").write(
        "==== run_update " + stamp + "（並行 4）====\n"
        "---- fetch_x（12.3s，exit 0）----\n守門通過\n   1111111..2222222  main -> main\n")
    p2 = subprocess.run([sys.executable, "-c", code], capture_output=True, cwd=ROOT)
    out2 = p2.stdout.decode("utf-8", "replace")
    ok3 = "preflight 失敗、沒有 push" not in out2
    ok4 = p2.returncode == 0
    ck(ok3, "正控制：日誌乾淨時不報這一條（測試不是死的）")
    ck(ok4, "正控制：乾淨的假 repo ⇒ 離開碼 0，實際 %s" % p2.returncode)
    # #208：守門通過、但 push 被拒／被切斷 ⇒ 必須列異常（不然 publish.bat 的「git 不等人」只是把
    # 「卡死」換成「靜靜沒推」）。字樣取 GIT_HTTP_LOW_SPEED 真的斷線時 curl 印的那句（#208 探針實測）。
    io.open(log, "w", encoding="utf-8").write(
        "==== run_update " + stamp + "（並行 4）====\n"
        "---- fetch_x（12.3s，exit 0）----\n守門通過\n"
        "error: RPC failed; curl 28 Operation too slow. Less than 1000 bytes/sec transferred "
        "the last 60 seconds\nfatal: the remote end hung up unexpectedly\n")
    p3 = subprocess.run([sys.executable, "-c", code], capture_output=True, cwd=ROOT)
    out3 = p3.stdout.decode("utf-8", "replace")
    ok5 = p3.returncode == 1 and "沒有 push 成功" in out3
    ck(ok5, "#208：守門通過但 push 失敗 ⇒ 離開碼 1、結論指名「沒有 push 成功」（實際 rc %s）" % p3.returncode)
    # 守門通過、日誌裡連一行 push 都沒有（git 根本沒跑到）⇒ 同樣列異常（靜靜沒推也要出聲）
    io.open(log, "w", encoding="utf-8").write(
        "==== run_update " + stamp + "（並行 4）====\n"
        "---- fetch_x（12.3s，exit 0）----\n守門通過\n")
    p4 = subprocess.run([sys.executable, "-c", code], capture_output=True, cwd=ROOT)
    out4 = p4.stdout.decode("utf-8", "replace")
    ok6 = p4.returncode == 1 and "沒有 push 成功" in out4
    ck(ok6, "#208：守門通過但日誌沒有 push 行 ⇒ 離開碼 1（實際 rc %s）" % p4.returncode)
    # #164：子程序都不可以撞到封網保險絲（被 except 吞掉的也算）
    nethit = any(b"NETHIT" in x.stderr for x in (p, p2, p3, p4))
    ck(not nethit, "沙盒子程序沒有任何一次撞到封網保險絲（出口都接管了）")
    shutil.rmtree(box, ignore_errors=True)
    return ok1 and ok2 and ok3 and ok4 and ok5 and ok6 and not nethit


def main():
    global FAILS
    txt = io.open(BAT, "rb").read().decode("ascii")
    block = extract_block(txt)
    print("抽出的區塊 %d 字元、%d 行（%s → 檔尾）\n" % (len(block), block.count("\r\n"), START))
    assert GIT_LINE in block, "區塊裡找不到 set GIT 那行，抽取邊界可能已經漂移"

    good = scenario(block, "真實區塊", expect_pass=True)

    muts = [
        ("守門失敗改回 exit /b 1（#46 修之前的原樣：健檢整段被跳過）",
         "  set PUBRC=1\r\n", "  exit /b 1\r\n"),
        ("尾端離開碼寫死 0（守門擋下也回報成功）",
         "exit /b %PUBRC%", "exit /b 0"),
        ("push 的守衛條件寫錯（永遠不 push）",
         'if "%PUBRC%"=="0" (\r\n  %GIT% add', 'if "%PUBRC%"=="9" (\r\n  %GIT% add'),
        ("拿掉 set PUBRC=0（旗標沒有初始化）",
         "set PUBRC=0\r\n", ""),
        ("#208：拿掉 set GIT_TERMINAL_PROMPT=0（token 一壞 git 又會等人按認證視窗）",
         "set GIT_TERMINAL_PROMPT=0\r\n", ""),
        ("#179：拿掉留底那一行（班次又會只活到下一班）",
         "python scripts\\shift_log_archive.py --from-publish > shift_archive_log.txt 2>&1\r\n", ""),
        ("#179：留底只在守門通過時才跑（最需要證據的那一班反而沒有）",
         "python scripts\\shift_log_archive.py --from-publish > shift_archive_log.txt 2>&1\r\n",
         'if "%PUBRC%"=="0" (\r\n'
         "  python scripts\\shift_log_archive.py --from-publish > shift_archive_log.txt 2>&1\r\n"
         ")\r\n"),
        ("#179：留底的輸出導回 update_log.txt（鐵則 13；歸檔到的那份也會少掉健檢結論）",
         "python scripts\\shift_log_archive.py --from-publish > shift_archive_log.txt 2>&1\r\n",
         "python scripts\\shift_log_archive.py --from-publish >> update_log.txt 2>&1\r\n"),
    ]
    mut_ok = True
    for name, old, new in muts:
        print("── 突變：%s ──" % name)
        assert old in block, "突變目標不在區塊裡：" + name
        if not scenario(block.replace(old, new, 1), "突變", expect_pass=False):
            mut_ok = False

    FAILS = []
    con = contract()

    shutil.rmtree(TMP, ignore_errors=True)
    print("\n════ 結果：真實區塊 %s／突變對照 %s／跨檔契約 %s ════"
          % ("通過" if good else "失敗",
             "全被抓到" if mut_ok else "有漏網",
             "通過" if con else "失敗"))
    return 0 if (good and mut_ok and con) else 1


if __name__ == "__main__":
    sys.exit(main())
