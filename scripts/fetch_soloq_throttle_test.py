# -*- coding: utf-8 -*-
"""節流器依 Riot 回傳額度自動調整（2026-09-05）——純離線，不打 API、不用金鑰。

為什麼有這支：原本節流寫死 dev 金鑰的 100 次/2 分鐘，而使用者早就換成長期金鑰，
上一次每日更新「速率窗口暫停」**39 次**，光等就吃掉大半時間。改成讀
`X-App-Rate-Limit` 標頭之後，這支負責證明：
  ① 標頭解析對（含多組限制、空白、格式亂掉）
  ② 解析失敗／沒有標頭 → **保持原本的保守值**（fail-safe，不能變成無限快）
  ③ 真的會依額度放行：dev 額度下第 100 次要等，production 額度下不用等
  ④ 負控制：把新邏輯換成舊的寫死值，③ 一定要紅（證明這支測得到差別）
"""
import io
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("RIOT_API_KEY", "TEST-not-a-real-key")   # 匯入時別因為缺金鑰就退出

import fetch_soloq as FS   # noqa: E402

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PASS = FAIL = 0


def ok(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ✓ " + name)
    else:
        FAIL += 1
        print("  ✗ %s %s" % (name, extra))


def reset(limits=None):
    FS._req_times.clear()
    FS._LIMITS = list(limits) if limits else [(20, 1.0), (100, 120.0)]
    FS._LIM_SRC = "測試"


print("① 標頭解析")
reset()
FS._set_limits("20:1,100:120")
ok("dev 格式", FS._LIMITS == [(20, 1.0), (100, 120.0)], str(FS._LIMITS))
FS._set_limits("500:10,30000:600")
ok("production 格式", FS._LIMITS == [(500, 10.0), (30000, 600.0)], str(FS._LIMITS))
FS._set_limits(" 100 : 60 , 2000 : 600 ")
ok("有空白也吃得下", FS._LIMITS == [(100, 60.0), (2000, 600.0)], str(FS._LIMITS))

print("\n② 壞掉的標頭不可以放寬限制（fail-safe）")
for bad in (None, "", "亂碼", "abc:def", "0:0", "100"):
    reset([(7, 3.0)])
    FS._set_limits(bad)
    ok("壞標頭 %r → 保持原值" % (bad,), FS._LIMITS == [(7, 3.0)], str(FS._LIMITS))

print("\n③ 真的會依額度放行（用假的時間戳，不真的 sleep）")


def would_wait(limits, n_sent, gap=0.001):
    """塞 n_sent 個剛剛送出的時間戳，看下一次 _throttle 會不會等。"""
    reset(limits)
    now = time.time()
    for i in range(n_sent):
        FS._req_times.append(now - i * gap)
    t0 = time.time()
    FS._throttle()
    return time.time() - t0


# ⚠ 用**縮小版視窗**（1 秒而不是 120 秒）：比例關係一模一樣，但測試秒級跑完。
# 「窄額度會等、寬額度不等」才是要驗的性質，視窗長度不是。
w_dev = would_wait([(20, 1.0), (100, 1.0)], 95)        # 窄額度：95 次已達 90% 門檻 ⇒ 要等
ok("窄額度下、送了 95 次 → 會等（>0.3s）", w_dev > 0.3, "實際等了 %.2fs" % w_dev)
w_prod = would_wait([(500, 1.0), (30000, 60.0)], 95)   # 寬額度：95 次遠不到門檻 ⇒ 不等
ok("寬額度下、同樣 95 次 → 不等（<0.2s）", w_prod < 0.2, "實際等了 %.2fs" % w_prod)
print("   ⇒ 同樣的請求量，窄額度要等 %.2fs、寬額度等 %.2fs" % (w_dev, w_prod))

print("\n④ 負控制：換回舊的寫死邏輯，③ 的第二條必須紅")
_orig = FS._throttle


def _old_throttle():
    """改動前的版本（寫死 dev 值）。"""
    now = time.time()
    while FS._req_times and now - FS._req_times[0] > 120:
        FS._req_times.popleft()
    if len(FS._req_times) >= 100:
        wait = 120 - (now - FS._req_times[0]) + 0.1
        if wait > 0:
            time.sleep(min(wait, 1.0))      # 測試裡不真的睡滿
    recent = [t for t in FS._req_times if time.time() - t < 1]
    if len(recent) >= 18:
        time.sleep(1.0)


FS._throttle = _old_throttle
w_old = would_wait([(500, 1.0), (30000, 60.0)], 95)
FS._throttle = _orig
ok("舊邏輯在寬額度下**照樣會等** ⇒ 這支測得到差別", w_old > 0.3,
   "舊邏輯等了 %.2fs（<0.5 代表這支測試沒有鑑別力）" % w_old)

print(("\n✓ 全部 %d 條通過" % PASS) if not FAIL else ("\n✗ %d 條失敗、%d 條通過" % (FAIL, PASS)))
sys.exit(0 if not FAIL else 1)
