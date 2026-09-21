# -*- coding: utf-8 -*-
"""run_update 的逐步逾時（2026-09-22 精進迴圈 #202）——沙盒測試。

被測的事
--------
以前 run_one 是不帶 timeout 的 subprocess.run：任何一步卡死 ⇒ 整班卡死 ⇒ publish.bat 走不到守門／push／健檢，
而排程工作是 IgnoreNew＋PT72H ⇒ 後面最多 6 班整個被跳過。現在單步超過 `--step-timeout`（預設 1800s）就
**連孫程序一起**收掉、記 exit 124、後面的步驟與階段照跑。

沙盒紀律
--------
- 每一次執行都是**子程序**跑 `drv.py`（離開碼、stdout 編碼、卡不卡住只有子程序量得到），PLAN 換成暫存目錄裡的假步驟，
  `--log` 指到暫存檔；不打網路、不碰任何真實資料檔。跑完 assert 真實 `update_log.txt` 的 size／mtime 沒動。
- 只有沙盒才有的證據：輸出字樣一律帶 9942（`BEFORE-HANG-9942`…），真實日誌不可能有。
- 卡住的假步驟會起一個**繼承 stderr 管線的孫程序**（＝Playwright 的 node driver 的形狀）：只殺子程序不殺孫程序時
  communicate() 等不到 EOF——③ 用「只 p.kill()」當對照，證明孫程序那條斷言是 kill_tree 在撐、不是本來就會死。
- 正控制釘 `fef8b682`（＝改動前一版；#93：不可以寫 HEAD）：舊版對同一份卡住的 PLAN 10 秒後還在跑；
  乾淨的 PLAN 新舊版日誌逐行相同（剝掉秒數與時間戳）。

用法：python scripts/run_update_steptmo_test.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable
OLDREV = "fef8b682"
REAL_LOG = os.path.join(ROOT, "update_log.txt")
RE_STEP = re.compile(r"^---- (.+?)（([\d.]+)s，exit (-?\d+)）----", re.M)

fails, checks = [], [0]


def ck(cond, msg):
    checks[0] += 1
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        fails.append(msg)


def alive(pid):
    if not pid:
        return False
    if os.name == "nt":
        r = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid, "/NH", "/FO", "CSV"],
                           capture_output=True, text=True, errors="replace")
        return ('"%d"' % pid) in (r.stdout or "")
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def kill_pid_tree(pid):
    if pid and os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
    elif pid:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


DRV = r'''
import importlib.util, json, os, sys
mod_path, plan_json = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("ru_under_test", mod_path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
with open(plan_json, encoding="utf-8") as f:
    m.PLAN = [(st, [(n, cmd) for n, cmd in steps]) for st, steps in json.load(f)]
if os.environ.get("ZZ_NOTREE_9942") == "1":      # 對照組：只殺子程序、不殺孫程序
    m.kill_tree = lambda p: p.kill()
    m.KILL_WAIT_S = 2
if os.environ.get("ZZ_DEFTMO_9942"):            # ⑧：不帶 --step-timeout 時吃的是模組層的預設值
    m.STEP_TMO_S = float(os.environ["ZZ_DEFTMO_9942"])
sys.argv = ["run_update.py"] + sys.argv[3:]
sys.exit(m.main())
'''

OK_STEP = "import sys\nprint(sys.argv[1], flush=True)\n"
SLEEP_STEP = "import sys, time\nprint('SLEEP-START-9942', flush=True)\ntime.sleep(float(sys.argv[1]))\nprint('SLEEP-END-9942', flush=True)\n"
HANG_STEP = (
    "import subprocess, sys, time\n"
    "print('BEFORE-HANG-9942', flush=True)\n"
    "g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'], stdout=sys.stdout, stderr=sys.stderr)\n"
    "open(sys.argv[1], 'w').write(str(g.pid))\n"
    "time.sleep(300)\n"
    "print('AFTER-HANG-9942', flush=True)\n")


def main():
    real_before = (os.path.getsize(REAL_LOG), os.path.getmtime(REAL_LOG)) if os.path.exists(REAL_LOG) else None
    tmp = tempfile.mkdtemp(prefix="ru_steptmo_9942_")
    pidfiles = []
    try:
        def w(name, text):
            p = os.path.join(tmp, name)
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
            return p

        drv, okp, slp, hgp = w("drv.py", DRV), w("ok.py", OK_STEP), w("sl.py", SLEEP_STEP), w("hang.py", HANG_STEP)
        newmod = os.path.join(HERE, "run_update.py")
        r = subprocess.run(["git", "show", OLDREV + ":scripts/run_update.py"], cwd=ROOT, capture_output=True)
        oldmod = os.path.join(tmp, "run_update_old.py")
        with open(oldmod, "wb") as f:
            f.write(r.stdout)
        old_src = r.stdout.decode("utf-8", "replace")
        ck(r.returncode == 0 and "def run_one" in old_src and "kill_tree" not in old_src and "step-timeout" not in old_src,
           "正控制底稿：%s 的 run_update.py 拉得出來、而且真的沒有 kill_tree／--step-timeout" % OLDREV)

        def plan_file(tag, plan):
            return w("plan_%s.json" % tag, json.dumps(plan, ensure_ascii=False))

        def hang_plan(tag):
            pf = os.path.join(tmp, "gpid_%s.txt" % tag)
            pidfiles.append(pf)
            return pf, plan_file(tag, [
                ["甲 假並行", [["ok_a", [PY, okp, "A-OUT-9942"]], ["hang_tree", [PY, hgp, pf]],
                               ["ok_b", [PY, okp, "B-OUT-9942"]]]],
                ["乙 假單步", [["ok_c", [PY, okp, "C-OUT-9942"]]]]])

        def run(mod, planf, tag, args, wall, env_extra=None):
            """→ (rc 或 None＝超過 wall 還沒結束, 秒數, stdout, 日誌內容)"""
            logp = os.path.join(tmp, "log_%s.txt" % tag)
            env = dict(os.environ, PYTHONIOENCODING="utf-8", **(env_extra or {}))
            t0 = time.time()
            p = subprocess.Popen([PY, drv, mod, planf, "--log", logp] + args, cwd=tmp, env=env,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
            try:
                so, _ = p.communicate(timeout=wall)
                rc = p.returncode
            except subprocess.TimeoutExpired:
                rc = None
                kill_pid_tree(p.pid)
                try:
                    so, _ = p.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    so = b""
            el = time.time() - t0
            try:
                with open(logp, encoding="utf-8", errors="replace") as f:
                    lg = f.read()
            except OSError:
                lg = ""
            return rc, el, (so or b"").decode("utf-8", "replace"), lg

        def gpid(pf):
            try:
                return int(open(pf).read().strip())
            except (OSError, ValueError):
                return 0

        def steps_of(lg):
            return {n: (float(s), int(c)) for n, s, c in RE_STEP.findall(lg)}

        # ── ①② 新版：並行與循序兩條路都要收得掉、後面照跑 ──
        for tag, jobs in (("par", "4"), ("seq", "1")):
            print("\n【%s 新版 --jobs %s --step-timeout 3】" % ("①" if tag == "par" else "②", jobs))
            pf, planf = hang_plan(tag)
            rc, el, so, lg = run(newmod, planf, tag, ["--jobs", jobs, "--step-timeout", "3"], 30)
            st = steps_of(lg)
            ck(rc == 0, "整支跑得完、離開碼 0（實得 %r，%.1fs）" % (rc, el))
            ck(el < 25, "牆鐘 %.1fs < 25s（3 秒逾時＋收尾；卡住的步驟本來要睡 300 秒）" % el)
            h = st.get("hang_tree", (0.0, None))
            ck(h[1] == 124, "hang_tree 記 exit 124（實得 %r）" % (h[1],))
            ck(3.0 <= h[0] < 20, "hang_tree 的秒數 %.1fs 落在 3～20（＝真的等到逾時才收、收了就回）" % h[0])
            ck(all(st.get(n, (0, None))[1] == 0 for n in ("ok_a", "ok_b", "ok_c")),
               "同階段的 ok_a／ok_b 與下一階段的 ok_c 都 exit 0（%r）" % {n: st.get(n) for n in ("ok_a", "ok_b", "ok_c")})
            ck(all(m in lg for m in ("A-OUT-9942", "B-OUT-9942", "C-OUT-9942")), "三個正常步驟的輸出都在日誌裡")
            ck("BEFORE-HANG-9942" in lg, "卡住之前已經印出來的輸出有留在日誌裡")
            ck("AFTER-HANG-9942" not in lg, "卡住之後那行沒有出現（＝真的是被收掉、不是睡完了）")
            ck("⏱ 逐步逾時：hang_tree" in lg and "exit 124" in lg, "日誌有指名的「⏱ 逐步逾時：hang_tree」")
            ck("⚠ 非零離開碼：hang_tree(124)" in lg and "⚠ 非零離開碼：hang_tree(124)" in so,
               "收尾的「⚠ 非零離開碼：hang_tree(124)」日誌與 stdout 都有")
            ck(lg.find("C-OUT-9942") > lg.find("⏱ 逐步逾時") > 0, "下一階段排在逾時那一步後面（階段順序沒亂）")
            g = gpid(pf)
            ck(g > 0, "孫程序的 PID 有記下來（%d）＝假步驟真的跑到起孫程序那一行" % g)
            ck(not alive(g), "孫程序也被收掉了（PID %d 不在）" % g)

        # ── ③ 對照：只殺子程序、不殺孫程序 ⇒ 孫程序還活著、輸出讀不回來 ──
        print("\n【③ 對照：kill_tree 換成只 p.kill()】")
        pf, planf = hang_plan("notree")
        rc, el, so, lg = run(newmod, planf, "notree", ["--jobs", "4", "--step-timeout", "3"], 30,
                             {"ZZ_NOTREE_9942": "1"})
        g = gpid(pf)
        still = alive(g)
        ck(g > 0 and still, "只 p.kill() ⇒ 孫程序 PID %d 還活著（①② 那條「孫程序不在」是 kill_tree 在撐）" % g)
        ck("讀不回來" in lg and "BEFORE-HANG-9942" not in lg,
           "孫程序握著管線 ⇒ 已印出來的輸出讀不回來（①② 讀得回來也是 kill_tree 在撐）")
        ck(rc == 0 and steps_of(lg).get("hang_tree", (0, None))[1] == 124 and "C-OUT-9942" in lg,
           "就算孫程序收不掉，這一班仍然跑得完（KILL_WAIT_S 封頂、不會換個地方卡死）")
        kill_pid_tree(g)

        # ── ④ --step-timeout 真的有被吃進去；0＝不設上限 ──
        print("\n【④ --step-timeout 1／0 對同一個睡 2.5 秒的步驟】")
        planf = plan_file("sl", [["甲", [["sleepy", [PY, slp, "2.5"]]]]])
        rc1, el1, _, lg1 = run(newmod, planf, "sl1", ["--step-timeout", "1"], 60)
        rc0, el0, _, lg0 = run(newmod, planf, "sl0", ["--step-timeout", "0"], 60)
        ck(steps_of(lg1).get("sleepy", (0, None))[1] == 124 and "SLEEP-END-9942" not in lg1,
           "--step-timeout 1 ⇒ exit 124、沒睡完")
        ck(steps_of(lg0).get("sleepy", (0, None))[1] == 0 and "SLEEP-END-9942" in lg0 and "逐步逾時" not in lg0,
           "--step-timeout 0 ⇒ 不設上限：exit 0、睡完、沒有逾時行")

        # ── ⑤ 正控制：舊版對同一份卡住的 PLAN 10 秒後還在跑 ──
        print("\n【⑤ 正控制：%s 舊版】" % OLDREV)
        pf, planf = hang_plan("old")
        rc, el, so, lg = run(oldmod, planf, "old", ["--jobs", "4"], 10)
        ck(rc is None, "舊版 10 秒後還沒結束（rc=%r）＝它會一路卡到假步驟睡完 300 秒" % (rc,))
        ck("A-OUT-9942" not in lg and "exit 124" not in lg,
           "舊版卡住那一刻日誌連同階段的正常步驟都還沒寫（整階段等那一步）")
        kill_pid_tree(gpid(pf))

        # ── ⑥ 穩態：乾淨的 PLAN 新舊版日誌逐行相同 ──
        print("\n【⑥ 穩態：乾淨 PLAN 新舊版逐行相同】")
        planf = plan_file("clean", [["甲 假並行", [["ok_a", [PY, okp, "A-OUT-9942"]], ["ok_b", [PY, okp, "B-OUT-9942"]]]],
                                    ["乙 假單步", [["ok_c", [PY, okp, "C-OUT-9942"]]]]])
        rn, _, son, lgn = run(newmod, planf, "clean_new", ["--jobs", "4"], 60)
        ro, _, soo, lgo = run(oldmod, planf, "clean_old", ["--jobs", "4"], 60)

        def norm(t):
            t = re.sub(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d", "<TS>", t)
            t = re.sub(r"[\d.]+ ?s", "<S>", t)
            t = re.sub(r"[\d.]+ 分鐘", "<M>", t)
            return [l.rstrip() for l in t.splitlines()]

        ck(rn == 0 and ro == 0, "新舊版離開碼都是 0（%r／%r）" % (rn, ro))
        ck(len(norm(lgn)) > 8 and "C-OUT-9942" in lgn, "新版乾淨日誌不是空的（%d 行）" % len(norm(lgn)))
        # 「最久的 10 步」照牆鐘排序、沙盒裡每步 0.0x 秒 ⇒ 順序每次不同（DAILY #198 的教訓）
        # ⇒ 那一段之前逐行比、整份再比「同一批行」
        def head(ls):
            i = next((k for k, l in enumerate(ls) if "最久的 10 步" in l), len(ls))
            return ls[:i]

        ln, lo, so_n, so_o = norm(lgn), norm(lgo), norm(son), norm(soo)
        ck(head(ln) == head(lo) and len(head(ln)) > 6, "日誌在「最久的 10 步」之前逐行相同（剝掉秒數與時間戳，%d 行）" % len(head(ln)))
        ck(sorted(ln) == sorted(lo), "日誌整份是同一批行（照牆鐘排序的那幾行不比順序）")
        ck(head(so_n) == head(so_o) and sorted(so_n) == sorted(so_o), "stdout 同樣：前段逐行相同、整份同一批行")
        ck("逐步逾時" not in lgn and "exit 124" not in lgn, "穩態沒有任何逾時字樣")

        # ── ⑧ 預設值：不帶 --step-timeout 也有上限 ──
        print("\n【⑧ 不帶 --step-timeout：吃模組層預設值】")
        pf, planf = hang_plan("deftmo")
        rc, el, so, lg = run(newmod, planf, "deftmo", ["--jobs", "4"], 30, {"ZZ_DEFTMO_9942": "2"})
        ck(rc == 0 and steps_of(lg).get("hang_tree", (0, None))[1] == 124,
           "STEP_TMO_S 調成 2 秒、不帶旗標 ⇒ 照樣收掉（rc=%r，%.1fs）＝預設值真的接在 argparse 上" % (rc, el))
        kill_pid_tree(gpid(pf))
        src_new = open(newmod, encoding="utf-8").read()
        mm = re.search(r"^STEP_TMO_S = (\d+)", src_new, re.M)
        dv = int(mm.group(1)) if mm else 0
        ck(300 < dv <= 3600, "正式的預設值 %d 秒落在 300～3600（高過歷來正常最久的 272s、遠短於 12 小時班距）" % dv)

        # ── ⑦ 隔離 ──
        print("\n【⑦ 隔離】")
        real_after = (os.path.getsize(REAL_LOG), os.path.getmtime(REAL_LOG)) if os.path.exists(REAL_LOG) else None
        ck(real_before == real_after, "真實 update_log.txt 的 size／mtime 沒動")
    finally:
        for pf in pidfiles:
            try:
                kill_pid_tree(int(open(pf).read().strip()))
            except (OSError, ValueError):
                pass
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n結果：%d 條、失敗 %d" % (checks[0], len(fails)))
    for m in fails:
        print("   ✗ " + m)
    return 1 if fails else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    sys.exit(main())
