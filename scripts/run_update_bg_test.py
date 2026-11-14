# -*- coding: utf-8 -*-
"""run_update 背景階段（#3145）的沙盒測試：假步驟、暫存目錄、不碰真實日誌與資料。

PLAN 換成：
    A（0.3s）→ BG（背景，2.0s，結束時寫 bg_done，until=C）→ B（0.5s，記下「當時 bg_done 在不在」）→ C（記下 bg_done 在不在）
正例（並行 4）：B 看到 bg_done **不在**（真的在背景跑）、C 看到**在**（until 前有收）、牆鐘 < 循序的總和。
對照一（--jobs 1）：照舊就地循序 ⇒ B 看到 bg_done 在。
對照二（拿掉 bg 選項）：B 看到在——證明正例的「不在」是 bg 造成，不是測試本身寫錯。
另驗：until 寫不存在的階段名 ⇒ 跑到最後才收（C 看到不在、但日誌仍有 BG 的區塊、exit 0）。
沙盒守則：模組層 ROOT／預設 --log 都不准被用到——一律帶 --log 指到暫存目錄，並 assert 日誌寫在那裡。
"""
import io
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_update as ru  # noqa: E402

PY = sys.executable
fails = []


def check(name, ok, info=""):
    print(("  ✓ " if ok else "  ✗ ") + name + ("" if ok else "  " + str(info)))
    if not ok:
        fails.append(name)


def step(name, code):
    return (name, [PY, "-c", code])


def build(tmp, bg=True, until="C 階段"):
    done = os.path.join(tmp, "bg_done").replace("\\", "/")
    rec = lambda tag: os.path.join(tmp, tag).replace("\\", "/")
    mark = ("import os,time;time.sleep(%s);open('%s','w').write('1' if os.path.exists('%s') else '0')")
    opt = {"bg": True, "until": until} if bg else {}
    plan = [
        ("A 階段", [step("sA", "import time;time.sleep(0.3)")]),
        ("BG 階段", [step("sBG", "import time;time.sleep(2.0);open('%s','w').write('x');print('bg out')" % done)], opt),
        ("B 階段", [step("sB", mark % (0.5, rec("b_saw"), done))]),
        ("C 階段", [step("sC", mark % (0, rec("c_saw"), done))]),
    ]
    if not bg:
        plan[1] = plan[1][:2]
    return plan


def run(tmp, plan, jobs):
    ru.PLAN = plan
    logp = os.path.join(tmp, "log.txt")
    argv = sys.argv
    sys.argv = ["run_update.py", "--jobs", str(jobs), "--log", logp]
    t0 = time.time()
    try:
        rc = ru.main()
    finally:
        sys.argv = argv
    wall = time.time() - t0
    rd = lambda t: io.open(os.path.join(tmp, t)).read() if os.path.exists(os.path.join(tmp, t)) else "?"
    return rc, wall, rd("b_saw"), rd("c_saw"), io.open(logp, encoding="utf-8").read()


real_log = os.path.join(ru.ROOT, "update_log.txt")
real_mtime = os.path.getmtime(real_log) if os.path.exists(real_log) else None

print("【正例：並行 4，BG 背景跑到 C 前收】")
with tempfile.TemporaryDirectory() as tmp:
    rc, wall, b, c, log = run(tmp, build(tmp), 4)
    check("exit 0", rc == 0, rc)
    check("B 開跑時 BG 還沒結束（真的在背景）", b == "0", b)
    check("C 開跑前 BG 已收（until 生效）", c == "1", c)
    check("牆鐘 < 循序總和 2.8s（實際 %.2fs）" % wall, wall < 2.6, wall)
    check("日誌有 BG 的步驟區塊與輸出", "---- sBG（" in log and "bg out" in log, log[-400:])
    check("BG 階段行註明背景", "【BG 階段】這一階段" in log and "背景；收的時候多等了" in log)
    check("BG 區塊寫在 C 之前", log.index("---- sBG（") < log.index("---- sC（"))
    check("四步都記進「最久的 10 步」", all(("   " + n) in log.split("最久的 10 步")[1] for n in ("sA", "sBG", "sB", "sC")))

print("【對照一：--jobs 1 ⇒ 就地循序】")
with tempfile.TemporaryDirectory() as tmp:
    rc, wall, b, c, log = run(tmp, build(tmp), 1)
    check("exit 0", rc == 0, rc)
    check("B 開跑時 BG 已結束", b == "1", b)
    check("沒有「背景」註記", "背景；收的時候" not in log)

print("【對照二：拿掉 bg 選項 ⇒ 舊行為】")
with tempfile.TemporaryDirectory() as tmp:
    rc, wall, b, c, log = run(tmp, build(tmp, bg=False), 4)
    check("B 開跑時 BG 已結束", b == "1", b)
    check("牆鐘 ≥ 2.7s（循序，實際 %.2fs）" % wall, wall >= 2.7, wall)

print("【until 找不到 ⇒ 跑到最後才收】")
with tempfile.TemporaryDirectory() as tmp:
    rc, wall, b, c, log = run(tmp, build(tmp, until="不存在的階段"), 4)
    check("exit 0", rc == 0, rc)
    check("C 開跑時 BG 還沒結束", c == "0", c)
    check("日誌仍有 BG 區塊（最後收）", "---- sBG（" in log)

print("【沙盒沒碰真實日誌】")
check("update_log.txt 的 mtime 沒變",
      real_mtime is None or os.path.getmtime(real_log) == real_mtime)

print("【真正的 PLAN：label_pending 是背景、⑥ 前收】")
import importlib  # noqa: E402
ru2 = importlib.reload(ru)
ent = [e for e in ru2.PLAN if any(s and s[0] == "label_pending" for s in e[1])]
if ent:
    e = ent[0]
    check("label_pending 單獨一個背景階段", len(e[1]) == 1 and len(e) > 2 and e[2].get("bg"), e)
    names = [x[0] for x in ru2.PLAN]
    check("until 指向存在的 ⑥ 收尾", e[2].get("until") in names and e[2]["until"].startswith("⑥"), e[2])
    check("⑥ 收尾裡有 trim_data_cols（所以要在它之前收）",
          any(s and s[0] == "trim_data_cols" for s in ru2.PLAN[names.index(e[2]["until"])][1]))
else:
    print("  （scripts/bplive/label_pending.py 不存在 ⇒ SB 回 None，略過）")

print("\n%s（%d 條失敗）" % ("全部通過" if not fails else "有失敗", len(fails)))
sys.exit(1 if fails else 0)
