# -*- coding: utf-8 -*-
"""精進迴圈 #179：`scripts/shift_log_archive.py` 的沙盒測試（不碰真的 update_log.txt／shift_logs/）。

為什麼要有這一支：
  #179 把這支腳本掛進 `publish.bat`（每一班自己留底），並在摘要 JSON 與**台帳**裡記下
  「這一班有沒有守門過／commit／push」。台帳是 2026-09-17 22:00 那種「班次沒發布、
  隔天想查時日誌／console／警示檔全被下一班覆寫或自動刪掉」唯一會留下來的證據
  ——判定規則寫錯，台帳就會說謊，而且說的是那種再也驗證不了的謊。

沙盒紀律（CLAUDE.md 鐵則 17、#52）：
  被測模組的每一個路徑常數（LOG／OUTDIR／LEDGER）都接管到暫存夾，並在收尾斷言
  **模組層沒有任何常數還指著真實 repo**、真實 `autopilot/shift_logs/` 的 size＋mtime_ns 一格沒動。

用法：python scripts/shift_log_archive_test.py
"""
import glob
import io
import json
import os
import shutil
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import shift_log_archive as A               # noqa: E402

REAL_OUT = A.OUTDIR
REAL_LOG = A.LOG
FAILS = []
N = [0]


def ck(cond, msg):
    N[0] += 1
    print(("  OK  " if cond else "  紅  ") + msg)
    if not cond:
        FAILS.append(msg)


HEAD = "==== run_update 2026-09-21 10:00:01（並行 4）====\n"
STEP = "---- fetch_x（12.3s，exit 0）----\n   （【① 補件】這一階段 12.3s）\n"
TAIL = "合計 1.0 分鐘（牆鐘 60.0s）；步驟時間相加 1.0 分鐘（60.0s）——差額 0.0s 是並行省下來的\n"
GATE_OK = "守門通過\n"
GATE_BAD = "PREFLIGHT FAILED - push skipped. see update_log.txt\n"
COMMIT = "[main e6a29529] data update 週日 2026/09/20 22:07:30.56\n 110 files changed, 1 insertions(+)\n"
PUSH = "To https://github.com/Yuwanxd777/lol-dashboard.git\n   f3e04bba..e6a29529  main -> main\n"
# 健檢自己的輸出會被 `type` 折進 update_log.txt，裡面就有「push：✓」這種字樣。
# 它**不可以**被當成「真的 push 過」——publish.bat 裡健檢排在 git 三行之後，
# 守門擋下那一班照樣會印這行，誤判就會讓台帳把「沒發布」記成「發布了」。
HEALTH_ECHO = "那一班的日誌快照（不是現況）：守門：✓／push：✓／lint 錯誤級：0\n"


def sec(t):
    print("\n── %s ──" % t)


def main():
    sec("① parse()：發布結果三欄（合成素材，正反對照）")
    full = HEAD + STEP + TAIL + GATE_OK + COMMIT + PUSH + HEALTH_ECHO
    i = A.parse(full)
    ck(i is not None and i["shift"] == "2026-09-21 10:00", "班次解析 2026-09-21 10:00")
    ck(i["gate"] == "ok", "守門 ok，實際 %s" % i["gate"])
    ck(i["commit"] == "yes", "commit yes，實際 %s" % i["commit"])
    ck(i["push"] == "yes", "push yes，實際 %s" % i["push"])

    i2 = A.parse(HEAD + STEP + TAIL + GATE_OK + GATE_BAD + HEALTH_ECHO)
    ck(i2["gate"] == "fail", "守門擋下 ⇒ fail，實際 %s" % i2["gate"])
    ck(i2["commit"] == "no", "守門擋下那一班 commit no，實際 %s" % i2["commit"])
    ck(i2["push"] == "no", "**健檢輸出裡的『push：✓』不算數**，實際 %s" % i2["push"])

    i3 = A.parse(HEAD + STEP + TAIL + GATE_OK + "nothing to commit, working tree clean\n")
    ck(i3["commit"] == "empty", "沒東西可 commit ⇒ empty，實際 %s" % i3["commit"])
    i4 = A.parse(HEAD + STEP + TAIL + GATE_OK + COMMIT + "Everything up-to-date\n")
    ck(i4["push"] == "uptodate", "遠端已最新 ⇒ uptodate，實際 %s" % i4["push"])
    i5 = A.parse(HEAD + STEP + TAIL)
    ck(i5["gate"] == "?" and i5["commit"] == "no" and i5["push"] == "no",
       "日誌只到 run_update 收尾（publish 還沒走到）⇒ ?／no／no，實際 %s／%s／%s"
       % (i5["gate"], i5["commit"], i5["push"]))
    ck(A.parse("隨便幾行沒有 run_update 的東西\n") is None, "沒有 run_update 那行 ⇒ None")

    sec("② parse()：真實歸檔日誌（素材＝repo 裡真的跑過的班次）")
    reals = sorted(glob.glob(os.path.join(REAL_OUT, "update_log_*.txt")))
    ck(len(reals) >= 2, "至少有兩份真實歸檔可用（實際 %d 份）" % len(reals))
    okpub = 0
    for p in reals:
        t = io.open(p, encoding="utf-8", errors="replace").read()
        r = A.parse(t)
        if r and (r["gate"], r["commit"], r["push"]) == ("ok", "yes", "yes"):
            okpub += 1
    ck(okpub >= 1, "真實日誌裡至少一班判成「守門✓／commit✓／push✓」（實際 %d 班）" % okpub)
    trunc = [p for p in reals if A.parse(io.open(p, encoding="utf-8", errors="replace").read())["push"] == "no"]
    print("     （真實素材 %d 份：完整發布 %d 班、沒走到 git 三行 %d 班 %s）"
          % (len(reals), okpub, len(trunc), [os.path.basename(x) for x in trunc]))

    sec("③ archive()：沙盒歸檔＋台帳")
    box = tempfile.mkdtemp(prefix="m179_arch_")
    A.LOG = os.path.join(box, "update_log.txt")
    A.OUTDIR = os.path.join(box, "shift_logs")
    A.LEDGER = os.path.join(A.OUTDIR, "ledger.txt")
    ck(ROOT not in A.LOG and ROOT not in A.OUTDIR and ROOT not in A.LEDGER,
       "模組層三個路徑常數都在沙盒，沒有一個還指著真實 repo")
    io.open(A.LOG, "w", encoding="utf-8").write(HEAD + STEP + TAIL + GATE_OK + COMMIT + PUSH)
    rc = A.archive(from_publish=True)
    lp = os.path.join(A.OUTDIR, "update_log_20260921_1000.txt")
    jp = os.path.join(A.OUTDIR, "shift_20260921_1000.json")
    ck(rc == 0, "離開碼 0")
    ck(os.path.exists(lp) and os.path.exists(jp), "日誌與摘要 JSON 都寫出來了")
    j = json.load(io.open(jp, encoding="utf-8"))
    ck((j.get("gate"), j.get("commit"), j.get("push")) == ("ok", "yes", "yes"),
       "JSON 記下發布結果，實際 %s／%s／%s" % (j.get("gate"), j.get("commit"), j.get("push")))
    ck(j["n_steps"] == 1 and j["wall"] == 60.0, "步數與牆鐘照舊解析")
    led = io.open(A.LEDGER, encoding="utf-8").read()
    ck(led.count("\n") == 1 and "2026-09-21 10:00" in led and "班次" in led,
       "台帳追加一行且標成「班次」：%r" % led.strip()[-60:])

    sec("④ 台帳是 append-only：手動再跑一次不會蓋掉班次那一行")
    rc2 = A.archive(from_publish=False)
    led2 = io.open(A.LEDGER, encoding="utf-8").read()
    ck(rc2 == 0, "第二次離開碼 0")
    ck(led2.startswith(led) and led2.count("\n") == 2, "第一行還在、又多一行（append-only）")
    ck("手動" in led2.splitlines()[-1], "第二行標成「手動」（分得出是誰跑的）")

    sec("⑤ 班次沒跑／日誌不是這一班：不歸檔，但台帳照樣留一行")
    io.open(A.LOG, "w", encoding="utf-8").write("這份日誌裡沒有 run_update 那行\n")
    rc3 = A.archive(from_publish=True)
    led3 = io.open(A.LEDGER, encoding="utf-8").read()
    ck(rc3 == 1, "離開碼 1（有問題），實際 %s" % rc3)
    ck(led3.count("\n") == 3, "台帳還是多了一行（**沒跑也要留證據**）")
    ck("沒有 run_update" in led3.splitlines()[-1], "那一行寫明原因：%r" % led3.splitlines()[-1][-50:])
    ck(len(glob.glob(os.path.join(A.OUTDIR, "update_log_*.txt"))) == 1, "沒有多歸檔一份垃圾")

    sec("⑥ 同一班重跑：較短的不覆寫較長的，較長的會覆寫（正控制）")
    io.open(A.LOG, "w", encoding="utf-8").write(HEAD + STEP + TAIL)          # 短版
    A.archive(from_publish=False)
    ck("main -> main" in io.open(lp, encoding="utf-8").read(), "短版沒有把完整那份蓋掉")
    io.open(A.LOG, "w", encoding="utf-8").write(HEAD + STEP + STEP + TAIL + GATE_OK + COMMIT + PUSH + "x" * 500)
    A.archive(from_publish=False)
    j2 = json.load(io.open(jp, encoding="utf-8"))
    ck(j2["n_steps"] == 2, "較長的那份覆寫成功（步數 1 → 2，正控制：規則不是死的）")

    sec("⑦ 正控制：寬鬆比對（只看『-> main』字樣）會把「push 被拒」記成「push 成功」")
    # git push 被拒時的真實輸出：`! [rejected]        main -> main (fetch first)`。
    # 這一班**沒有發布**，但字串裡就是有「main -> main」——只看字樣的寬鬆規則會記成發布成功，
    # 而台帳是事後不可能回頭驗證的，說錯一次就永遠錯。
    rejected = (HEAD + STEP + TAIL + GATE_OK + COMMIT +
                "To https://github.com/Yuwanxd777/lol-dashboard.git\n"
                " ! [rejected]        main -> main (fetch first)\n"
                "error: failed to push some refs to 'https://github.com/Yuwanxd777/lol-dashboard.git'\n")
    ck("main -> main" in rejected, "（前提）被拒的輸出裡確實有『main -> main』字樣")
    ck(A.parse(rejected)["push"] == "no",
       "push 被拒 ⇒ 判 no（寬鬆比對會判 yes），實際 %s" % A.parse(rejected)["push"])
    ck(A.parse(rejected)["commit"] == "yes", "同一班 commit 仍判 yes（分得開 commit 與 push）")
    ck(A.parse(HEAD + STEP + TAIL + HEALTH_ECHO)["push"] == "no",
       "健檢輸出裡的『push：✓』也不算數")

    sec("⑧ load_shifts()：#179 之前存的摘要沒有三個欄位 ⇒ 回頭解析歸檔日誌補上")
    # ⚠ 沙盒的資料夾**一定要跟真的同名**（shift_logs）：第一版用 m179_old_xxxx，
    # 目錄名裡沒有「shift_」⇒ 把「換檔名」寫成「換整條路徑」的 bug 照樣全綠，
    # 真的跑 --list 才發現每一班都印「？」（2026-09-21 #179 當場踩到）。
    box2 = os.path.join(tempfile.mkdtemp(prefix="m179_old_"), "shift_logs")
    os.makedirs(box2)
    A.OUTDIR = box2
    A.LEDGER = os.path.join(box2, "ledger.txt")
    old = {"shift": "2026-09-16 22:00", "stamp": "20260916_2200", "jobs": 4, "parallel": True,
           "wall": 261.5, "steps": [], "stages": [], "n_steps": 43, "n_bad": 0, "sum_steps": 380.1}
    json.dump(old, io.open(os.path.join(box2, "shift_20260916_2200.json"), "w", encoding="utf-8"))
    io.open(os.path.join(box2, "update_log_20260916_2200.txt"), "w", encoding="utf-8").write(
        HEAD + STEP + TAIL + GATE_OK + COMMIT + PUSH)
    # 沒有同名日誌的那一班（已被 KEEP 淘汰）：補不了就維持「？」，不可以瞎猜成 ✓
    json.dump(dict(old, stamp="20250101_1000", shift="2025-01-01 10:00"),
              io.open(os.path.join(box2, "shift_20250101_1000.json"), "w", encoding="utf-8"))
    ss = {s["stamp"]: s for s in A.load_shifts()}
    ck(ss["20260916_2200"].get("gate") == "ok" and ss["20260916_2200"].get("push") == "yes",
       "舊摘要＋還在的日誌 ⇒ 補成 ok／yes，實際 %s／%s"
       % (ss["20260916_2200"].get("gate"), ss["20260916_2200"].get("push")))
    ck(ss["20250101_1000"].get("gate") is None,
       "日誌已被淘汰 ⇒ 維持沒有（印成「？」），不瞎猜")
    ck("守門 ？" in A.verdict_str(ss["20250101_1000"]), "verdict_str 對缺值印「？」")
    shutil.rmtree(box2, ignore_errors=True)

    sec("⑨ 還原與隔離：真實 shift_logs/ 一格沒動")
    before = {p: (os.path.getsize(p), os.stat(p).st_mtime_ns)
              for p in glob.glob(os.path.join(REAL_OUT, "*"))}
    shutil.rmtree(box, ignore_errors=True)
    A.LOG, A.OUTDIR = REAL_LOG, REAL_OUT
    A.LEDGER = os.path.join(REAL_OUT, "ledger.txt")
    after = {p: (os.path.getsize(p), os.stat(p).st_mtime_ns)
             for p in glob.glob(os.path.join(REAL_OUT, "*"))}
    ck(before == after, "真實 autopilot/shift_logs/ 的 size＋mtime_ns 全部沒變（%d 個檔）" % len(after))
    ck(A.OUTDIR == REAL_OUT and A.LOG == REAL_LOG, "模組常數已還原")

    print("\n════ %s（%d 條）════"
          % ("全過" if not FAILS else "紅 %d 條" % len(FAILS), N[0]))
    if FAILS:
        for f in FAILS:
            print("  ✗ " + f)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
