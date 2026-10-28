# -*- coding: utf-8 -*-
"""update_health 的「OBGG 帳號連續幾班沒更新」回歸測試（2026-10-28 主對話迴圈 #2179）。

背景：www.obgg.net 從 10-27 10:00 起連不上，fetch_obgg_accounts 連續 4 班拒絕更新帳號檔，
但 exit 0、帳號檔沿用舊版 ⇒ 健檢 4 班都印「✓ 沒有異常」。這支守著新加的那一行判定。

沙盒：班次日誌全放 tempfile 目錄、透過 log_dir 參數傳入；另外 assert 模組層 SHIFT_LOG_DIR
沒被改動、而且沙盒裡放了「只有沙盒才有」的班次（正例），確認讀的是沙盒不是真的 autopilot/shift_logs/。
每一組都有會翻面的正控制。用法：python scripts\\update_health_obgg_test.py（exit 0＝全過）
"""
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import update_health as uh          # noqa: E402

OK = [0]
NG = []


def eq(got, want, label):
    if got == want:
        OK[0] += 1
    else:
        NG.append("%s：得到 %r，應為 %r" % (label, got, want))


OK_LOG = ("---- fetch_dpm_soloq_accounts（30.1s，exit 0）----\nxx\n"
          "---- fetch_obgg_accounts（13.4s，exit 0）----\n現役選手名冊：325 位\n"
          "OBGG 帳號更新：1244 → 1280（…）\n---- resolve_obgg_dpmpuuid（2.8s，exit 0）----\n")
FAIL_LOG = ("---- fetch_obgg_accounts（199.7s，exit 0）----\n"
            "⚠ OBGG 請求最終失敗 9 次（zone 9／team 0／progamer 0）\n"
            "✗ LCK 只抓到 0 帳號（<20），OBGG 可能異常 → 不更新 soloq_accounts.json\n"
            "---- resolve_obgg_dpmpuuid（2.9s，exit 0）----\n")
# 別一步印了同樣字樣：不能算到 OBGG 頭上（區塊隔離的正控制）
OTHER_LOG = ("---- fetch_obgg_accounts（10.0s，exit 0）----\nOBGG 帳號更新：1 → 2\n"
             "---- some_other（1.0s，exit 0）----\n→ 不更新 soloq_accounts.json\n")

# ① 單班判定
eq(uh.obgg_state(OK_LOG), "ok", "①有寫出帳號檔")
eq(uh.obgg_state(FAIL_LOG), "fail", "①拒絕更新")
eq(uh.obgg_state(OTHER_LOG), "ok", "①別一步的字樣不算")
eq(uh.obgg_state("---- fetch_dpm（1s，exit 0）----\n"), None, "①沒跑這步")
eq(uh.obgg_state(""), None, "①空日誌")

# ② 連續班數：None 跳過不中斷、遇到 ok 就停
st = [("20261026_2200", "ok"), ("20261027_1000", "fail"), ("20261027_2200", None),
      ("20261028_1000", "fail"), ("20261028_2200", "fail")]
eq(uh.obgg_streak(st), (3, "20261027_1000"), "②跳過 None 連 3 班")
eq(uh.obgg_streak(st + [("20261029_1000", "ok")]), (0, None), "②最新一班恢復＝0（正控制）")
eq(uh.obgg_streak([]), (0, None), "②沒資料")

# ③ 班次鍵
eq(uh.shift_key_of("2026-10-28 22:00:05"), "20261028_2200", "③晚班")
eq(uh.shift_key_of("2026-10-29 10:00:03"), "20261029_1000", "③早班")
eq(uh.shift_key_of(None), None, "③沒有時間")

# ④ 讀沙盒目錄＋當班覆蓋同鍵的歸檔
real_dir = uh.SHIFT_LOG_DIR
tmp = tempfile.mkdtemp(prefix="uh_obgg_")
try:
    for k, t in [("20261026_2200", OK_LOG), ("20261027_1000", FAIL_LOG),
                 ("20261027_2200", FAIL_LOG), ("20991231_1000", FAIL_LOG)]:   # 2099 只有沙盒有
        io.open(os.path.join(tmp, "update_log_%s.txt" % k), "w", encoding="utf-8").write(t)
    io.open(os.path.join(tmp, "update_log_bad.txt"), "w", encoding="utf-8").write(FAIL_LOG)  # 檔名不合格式 ⇒ 不收
    got = dict(uh.obgg_shift_states(None, None, log_dir=tmp))
    eq(sorted(got), ["20261026_2200", "20261027_1000", "20261027_2200", "20991231_1000"], "④只收合格檔名、讀到沙盒正例")
    eq(uh.obgg_streak(list(got.items())), (3, "20261027_1000"), "④沙盒連 3 班")
    # 當班日誌（還沒歸檔）恢復 ⇒ 蓋掉沙盒裡同一班的 fail
    got2 = dict(uh.obgg_shift_states(OK_LOG, "2099-12-31 10:00:01", log_dir=tmp))
    eq(got2["20991231_1000"], "ok", "④當班覆蓋同鍵歸檔")
    eq(uh.obgg_streak(list(got2.items())), (0, None), "④當班恢復＝0")
    # 當班是新的一班 ⇒ 加在最前面、連續數 +1
    got3 = uh.obgg_shift_states(FAIL_LOG, "2099-12-31 22:00:01", log_dir=tmp)
    eq(uh.obgg_streak(got3), (4, "20261027_1000"), "④當班新增一班")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
eq(uh.SHIFT_LOG_DIR, real_dir, "④模組層路徑沒被動")

# ⑤ 門檻：<warn 不提醒、≥warn 提醒不進結論、≥bad 進結論
fails = lambda n: [("2026%04d" % i, "fail") for i in range(n)]
l1, b1 = uh.obgg_problems(fails(1), warn=2, bad_n=4)
eq((l1.startswith("⚠"), b1), (False, []), "⑤1 班只觀察")
l2, b2 = uh.obgg_problems(fails(2), warn=2, bad_n=4)
eq((l2.startswith("⚠ 提醒"), b2), (True, []), "⑤2 班提醒、不進結論")
l4, b4 = uh.obgg_problems(fails(4), warn=2, bad_n=4)
eq((l4.startswith("⚠ OBGG"), len(b4)), (True, 1), "⑤滿門檻進結論（正控制）")
l0, b0 = uh.obgg_problems(fails(4) + [("20999999", "ok")], warn=2, bad_n=4)
eq((l0.startswith("OBGG 帳號：✓"), b0), (True, []), "⑤最新恢復＝✓")
ln, bn = uh.obgg_problems([("x", None)])
eq(("找不到" in ln, bn), (True, []), "⑤全部沒跑這步")

print("update_health OBGG 連續失敗：%d 過、%d 失敗" % (OK[0], len(NG)))
for x in NG:
    print("  ✗ " + x)
sys.exit(1 if NG else 0)
