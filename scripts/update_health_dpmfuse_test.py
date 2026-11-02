# -*- coding: utf-8 -*-
"""update_health 的「dpm 逐場連續幾班熔斷」回歸測試（2026-11-02 主對話迴圈 #2438）。

背景：11-01 22:00／11-02 10:00 連兩班 ⑤d 熔斷、432 個帳號整班沒問，健檢兩班都印「✓ 沒有異常」，
積分頁預設範圍卻已沒有可點的選手。這支守著新加的那一行判定。

沙盒：班次日誌全放 tempfile 目錄、透過 log_dir 傳入；放 2099 年「只有沙盒才有」的班次當正例，
另外 assert 模組層 SHIFT_LOG_DIR 沒被動。素材裡的熔斷行是 2026-11-02 10:00 班日誌的原文。
用法：python scripts\\update_health_dpmfuse_test.py（exit 0＝全過）
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


OK_LOG = ("---- fetch_soloq_auto（60.0s，exit 0）----\nxx\n"
          "---- fetch_soloq_update（86.5s，exit 0）----\n"
          "⏱ 批次預抓 30s：422 個帳號／9 批（批次大小 48）、命中 422、退回逐一 0、減半 0 次\n"
          "---- fetch_soloq_year（47.9s，exit 0）----\n")
WAIT_LOG = ("---- fetch_soloq_update（286.5s，exit 0）----\n"
            "   ⏳ dpm 整批 429（第 1 個帳號起，共 435 個）→ 等 60s 再問（還可再等 3 次）\n"
            "⏱ 批次預抓 90s：435 個帳號／9 批（批次大小 48）、命中 435、退回逐一 0、減半 0 次、限流等待 1 次共 60s\n"
            "---- fetch_soloq_year（47.9s，exit 0）----\n")
FAIL_LOG = ("---- fetch_soloq_update（86.5s，exit 0）----\n"
            "⚡ dpm 熔斷：連續 3 個帳號問不到（重試仍失敗／抓錯）⇒ 這一班剩下的帳號不再問 dpm（批次已命中的照收）\n"
            "⏱ 批次預抓 14s：435 個帳號／176 批（批次大小 48）、命中 0、退回逐一 435、減半 5 次\n"
            "⚡ dpm 熔斷小結：432 個帳號這一班沒問（223 位選手）；批次已到手的照收\n"
            "---- fetch_soloq_year（47.9s，exit 0）----\n")
# 別一步印了同樣字樣：不能算到 ⑤d 頭上（區塊隔離的正控制）
OTHER_LOG = ("---- fetch_soloq_update（86.5s，exit 0）----\n⏱ 批次預抓 30s：1 個帳號\n"
             "---- some_other（1.0s，exit 0）----\n⚡ dpm 熔斷小結：9 個帳號這一班沒問\n")
NOSTEP_LOG = "---- some_other（1.0s，exit 0）----\n⚡ dpm 熔斷小結：9 個帳號這一班沒問\n"
NOBATCH_LOG = "---- fetch_soloq_update（1.0s，exit 0）----\n沒有要問的帳號\n"

# ① 單班判定
eq(uh.dpm_fuse_state(OK_LOG), "ok", "①正常")
eq(uh.dpm_fuse_state(WAIT_LOG), "ok", "①等過限流後問到＝不算熔斷")
eq(uh.dpm_fuse_state(FAIL_LOG), "fail", "①熔斷")
eq(uh.dpm_fuse_state(OTHER_LOG), "ok", "①別一步的字樣不算")
eq(uh.dpm_fuse_state(NOSTEP_LOG), None, "①沒跑這步（就算別步有字樣）")
eq(uh.dpm_fuse_state(NOBATCH_LOG), None, "①沒走到預抓")
eq(uh.dpm_fuse_state(""), None, "①空日誌")
eq(uh.dpm_fuse_state(None), None, "①None")

# ② 讀沙盒目錄＋當班覆蓋同鍵的歸檔；state_of 不傳仍是 OBGG（舊呼叫不變）
real_dir = uh.SHIFT_LOG_DIR
tmp = tempfile.mkdtemp(prefix="uh_dpmfuse_")
try:
    for k, t in [("20991230_1000", OK_LOG), ("20991230_2200", FAIL_LOG), ("20991231_1000", FAIL_LOG)]:
        with io.open(os.path.join(tmp, "update_log_%s.txt" % k), "w", encoding="utf-8") as f:
            f.write(t)
    st = uh.obgg_shift_states(None, None, log_dir=tmp, state_of=uh.dpm_fuse_state)
    eq(dict(st), {"20991230_1000": "ok", "20991230_2200": "fail", "20991231_1000": "fail"}, "②讀到沙盒正例")
    eq(uh.obgg_streak(st), (2, "20991230_2200"), "②連 2 班")
    st2 = uh.obgg_shift_states(OK_LOG, "2099-12-31 10:00:01", log_dir=tmp, state_of=uh.dpm_fuse_state)
    eq(uh.obgg_streak(st2), (0, None), "②當班恢復蓋掉同鍵歸檔")
    st3 = uh.obgg_shift_states(FAIL_LOG, "2099-12-31 22:00:01", log_dir=tmp, state_of=uh.dpm_fuse_state)
    eq(uh.obgg_streak(st3), (3, "20991230_2200"), "②當班新增一班")
    eq(set(dict(uh.obgg_shift_states(None, None, log_dir=tmp)).values()), {None}, "②不傳 state_of＝仍是 OBGG 判定")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
eq(uh.SHIFT_LOG_DIR, real_dir, "②模組層路徑沒被動")

# ③ 門檻：1 班只印、2 班進結論、恢復就解除
K = lambda *v: [("209901%02d_1000" % i, s) for i, s in enumerate(v)]
l, b = uh.dpm_fuse_problems(K("ok", "fail"))
eq((l.startswith("⚠"), "單班" in l, b), (False, True, []), "③1 班只觀察")
l, b = uh.dpm_fuse_problems(K("ok", "fail", "fail"))
eq((l.startswith("⚠ dpm"), len(b), "連續 2 班" in b[0] if b else None), (True, 1, True), "③2 班進結論（正控制）")
l, b = uh.dpm_fuse_problems(K("fail", "fail", "ok"))
eq(("✓" in l, b), (True, []), "③最新恢復＝✓")
l, b = uh.dpm_fuse_problems(K("fail", None, "fail"))
eq(len(b), 1, "③沒跑這步的班跳過不中斷")
l, b = uh.dpm_fuse_problems([("x", None)])
eq(("找不到" in l, b), (True, []), "③全部沒資料不報異常")
l, _ = uh.dpm_fuse_problems(K("ok"), WAIT_LOG)
eq("等待 1 次共 60s" in l, True, "③附限流等待")
l, _ = uh.dpm_fuse_problems(K("ok"), OK_LOG)
eq("等待" in l, False, "③沒等就不提（正控制）")

# ④ 正控制：同一份連兩班素材，舊判定（OBGG 那條）看不到 ⇒ 這條是新增的鑑別力
eq(uh.obgg_state(FAIL_LOG), None, "④OBGG 判定對熔斷素材無反應")

print("update_health dpm 連續熔斷：%d 過、%d 失敗" % (OK[0], len(NG)))
for x in NG:
    print("  ✗ " + x)
sys.exit(1 if NG else 0)
