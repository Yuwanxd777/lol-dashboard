# -*- coding: utf-8 -*-
"""每日更新的執行器：**互不相干的步驟並行跑**，並逐步計時（2026-09-05）。

為什麼要它（使用者 2026-09-05：「需要加速每日 10 點跟 22 點的爬蟲」）：
`update.bat` 是嚴格循序跑 38 步，但那些步驟打的是**不同來源**（OE／wiki／DDragon／
CDragon／dpm／Riot），彼此不相依，而且幾乎全是**網路等待**——循序跑等於把等待時間相加。
並行不吃 CPU（都在等 socket），純賺牆鐘時間。

**設計上刻意保守**：只有「明確互不相干」的那一批並行，其餘維持原順序。
依賴關係逐條抄自 `update.bat` 的註解（fill 要在 data 前、career 要在 data 後、
clean_patch_text 要在兩支 patches 後、soloq 那串嚴格循序…）。看不出來的一律排循序。

另外一個附加價值：**以前完全不知道時間花在哪**（日誌沒有逐步計時）。
跑完會印一張「哪一步最久」的表，之後要再優化就有依據。

用法：
    python scripts/run_update.py                 # 照計畫跑（預設並行 4）
    python scripts/run_update.py --jobs 1        # 完全循序（跟舊 update.bat 一樣）
    python scripts/run_update.py --dry-run       # 只印計畫，不執行
    python scripts/run_update.py --only fetch_items,fetch_flags   # 只跑指定幾步（驗收用）
"""
import argparse
import io
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

# line_buffering：stdout 被 update.bat 導進 update_console.txt（區塊緩衝）⇒ 班次跑到一半時
# 那個檔幾乎是空的，從外面完全看不出「現在跑到哪一階段」（2026-09-07 #56 在 22:2x 撞到）。
# 逐行 flush 之後，管線進行中就能 tail 得到進度。
if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace",
                                  line_buffering=True)
else:
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable


def S(name, *args):
    """一個步驟：腳本名（不含 .py）＋參數。"""
    return (name, [PY, os.path.join(HERE, name + ".py")] + list(args))


def SB(name, *args):
    """scripts/bplive/ 底下的步驟（本機工具，可能不存在 ⇒ 自動跳過）。"""
    p = os.path.join(HERE, "bplive", name + ".py")
    return (name, [PY, p] + list(args)) if os.path.exists(p) else None


# ── 階段計畫：階段之間循序、階段之內並行 ────────────────────────────────
# 每一階段的註解寫的是「為什麼這幾步可以同時跑」與「為什麼要等上一階段」。
PLAN = [
    # 補件資料要先寫好，fetch_data 寫 data_{year}.js 時會把它併進去（update.bat 原註解）
    ("① 補件", [S("fetch_promo"), S("fetch_fill")]),
    # 主資料：後面一堆東西都讀它，自己一階段
    ("② 主資料", [S("fetch_data")]),
    # 這一批全部打不同來源、彼此不讀對方的產物 ⇒ 可以一起跑
    ("③ 各來源抓取（互不相干）", [
        S("build_career"),           # 讀 data/data_*.js（上一階段已寫完）
        S("fetch_patches"), S("fetch_patches_en"),
        S("fetch_skills"), S("fetch_items"),
        S("fetch_jungle"), S("fetch_release"), S("fetch_assets"),
        S("fetch_wiki_objectives"), S("fetch_obj_stats"),
        S("fetch_masteries"), S("fetch_old_runes"), S("fetch_rune_icons"),
        S("fetch_champ_icons"), S("fetch_team_logos"), S("fetch_flags"),
        S("fetch_worlds_tier1"), S("fetch_events_extra"),
        S("fetch_side_sel"),
        S("fetch_obgg_accounts"),    # soloq 那串的第一步，先跑完才能進 ⑤
    ]),
    # 這三步各自依賴上面某一步的產物
    ("④ 後處理", [
        S("clean_patch_text"),       # 要 patches + patches_en 都寫完
        S("fetch_item_nostore"),     # 要 items
        S("build_league_struct"),    # 讀 Leaguepedia 快取
    ]),
    # ── soloq 這一串**嚴格循序**，而且順序在 2026-09-05 依使用者的判斷倒過來了 ──
    # 舊順序：帳號 → 逐場（貴）→ 補新人 → 牌位（便宜）
    # 新順序：帳號 → **牌位（便宜，全掃）** → 逐場（貴，只抓勝敗有變的）→ 補新人
    # 理由（實測）：逐場每位 ~1.4 秒（Playwright 開真 Chrome 過 Cloudflare），431 位＝10 分鐘，
    # **而且沒人打過也要花滿 10 分鐘**；牌位是普通 HTTP、回應本來就帶 wins/losses
    # ⇒ 讓便宜的先跑、用「勝敗場數有沒有變」這個權威訊號決定貴的要抓誰。
    ("⑤ 積分：帳號（循序）", [S("fetch_dpm_soloq_accounts", "--apply")]),
    ("⑤b 解 puuid", [S("resolve_obgg_dpmpuuid")]),
    ("⑤c 牌位（便宜，全掃）", [S("fetch_soloq_auto")]),
    # --batch（2026-09-08 #68）：逐帳號改一次問 8 個（Promise.all），10:00 那班逐人 267s 預估 → 60~70s；
    # 沒命中的帳號自動退回逐一問，拿掉旗標＝回到舊行為。沙盒 scripts/fetch_soloq_update_batch_test.py。
    ("⑤d 逐場（貴，只抓有動的）", [S("fetch_soloq_update", "--changed", "--no-rebuild", "--batch")]),
    ("⑤e 補新人", [S("fetch_soloq_year", "--missing", "--no-rebuild")]),
    # 2026-09-07：帳號歸屬複查把帳號從 A 剔除後，A 的舊逐場檔沒人回收（索引是掃檔重建、檔自己帶 key）
    # ⇒ 積分頁上 A 顯示的是別人的比賽（實測 6 檔 777 場，4 位是整頁別人的）。
    # 排在這裡：⑤ 的帳號檔已定案、⑤d/⑤e 也寫完了，而 ⑤f/⑤g 都是掃逐場檔重建 ⇒ 清完才會生效。
    ("⑤e2 逐場對帳（刪掉別人的比賽）", [S("clean_soloq_matches", "--apply")]),
    # 2026-09-06：索引與出裝聚合（掃 30 萬場）原本 ⑤d 與 ⑤e 的尾端各跑一次＝每次管線兩遍；
    # 而 ⑤e 沒有新選手時會提早 return、連一次都不跑。改成獨立階段：**永遠恰好一次**。
    ("⑤f 積分索引（一次）", [S("build_soloq_index")]),
    ("⑤g 出裝聚合（一次）", [S("build_soloq_builds")]),
    # 收尾：彼此不相干，但都要等前面資料齊
    ("⑥ 收尾（互不相干）", [
        SB("label_pending", "--apply"),
        S("build_patch_dates"),
        S("build_img_manifest"),       # 隊徽／國旗清單（fetch_team_logos／fetch_flags 之後）
        S("trim_data_cols", "--apply"),
        S("build_font_subset"),
        S("lint_text", "--quiet"),
        S("check_player_dup", "--quiet"),
    ]),
    # 時間戳要蓋在所有寫資料的步驟之後
    ("⑦ 時間戳與健檢", [S("stamp_updated")]),
    ("⑧", [S("check_keys")]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=4, help="階段內同時跑幾步（預設 4；1＝完全循序）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default="", help="逗號分隔的步驟名，只跑這幾步（驗收用）")
    ap.add_argument("--log", default=os.path.join(ROOT, "update_log.txt"))
    A = ap.parse_args()
    only = {x.strip() for x in A.only.split(",") if x.strip()}

    plan = []
    for stage, steps in PLAN:
        keep = [s for s in steps if s and (not only or s[0] in only)]
        if keep:
            plan.append((stage, keep))
    if A.dry_run:
        for stage, steps in plan:
            print("%s（%d 步，%s）" % (stage, len(steps),
                                      "並行" if len(steps) > 1 and A.jobs > 1 else "循序"))
            for n, cmd in steps:
                print("    " + n + (" " + " ".join(cmd[2:]) if len(cmd) > 2 else ""))
        return 0

    log = io.open(A.log, "a", encoding="utf-8", errors="replace")
    log.write("\n==== run_update %s（並行 %d）====\n"
              % (time.strftime("%Y-%m-%d %H:%M:%S"), A.jobs))
    times = []
    t_all = time.time()

    def emit(s):
        """同時印到 stdout 與寫進 update_log.txt。

        2026-09-07 #56：階段牆鐘與收尾摘要以前**只** print 到 stdout ⇒ 只落在
        update_console.txt，而那個檔每一班被 update.bat 重寫 ⇒ 隔天想回頭比
        「③ 這一階段幾秒」根本沒得比（#55 量關鍵路徑時是趁當班還沒被覆寫才抄到的）。
        update_log.txt 每班留一份完整的，時間資料要放在那裡才追得了趨勢。
        """
        print(s)
        log.write(s + "\n")

    def run_one(step):
        name, cmd = step
        t0 = time.time()
        try:
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
            out, rc = (r.stdout or "") + (r.stderr or ""), r.returncode
        except Exception as e:
            out, rc = "執行失敗：%s: %s" % (type(e).__name__, e), -1
        return name, time.time() - t0, rc, out

    for stage, steps in plan:
        print("\n【%s】%d 步%s" % (stage, len(steps), "（並行）" if len(steps) > 1 and A.jobs > 1 else ""))
        t0 = time.time()
        # 2026-09-06：昨晚 22:00 並行在第②階段之後整支炸掉 → update.bat 退回**整條**循序（94 分鐘）。
        # 改成「哪一階段並行出事，就只把那一階段改循序重跑」，traceback 寫進日誌，其餘階段照常並行。
        # RUN_UPDATE_FAULT=1 是給測試用的故障注入（並行路徑故意炸），正式跑不會設。
        try:
            if A.jobs > 1 and len(steps) > 1:
                if os.environ.get("RUN_UPDATE_FAULT") == "1":
                    raise RuntimeError("故障注入：模擬並行階段崩潰")
                with ThreadPoolExecutor(max_workers=min(A.jobs, len(steps))) as ex:
                    res = list(ex.map(run_one, steps))
            else:
                res = [run_one(s) for s in steps]
        except Exception:
            import traceback
            tb = traceback.format_exc()
            log.write("\n" + "⚠ 【%s】並行執行炸掉，改循序重跑這一階段：" % stage + "\n" + tb + "\n")
            log.flush()
            print("   ⚠ 這一階段並行炸掉（%s）→ 改循序重跑這一階段（traceback 在日誌）"
                  % tb.strip().splitlines()[-1][:80])
            res = [run_one(s) for s in steps]
        # 寫日誌時照計畫順序，不照完成順序（日誌要能跟舊版對照著看）
        for name, el, rc, out in res:
            times.append((el, name, rc))
            log.write("\n---- %s（%.1fs，exit %d）----\n" % (name, el, rc))
            log.write(out if out.endswith("\n") else out + "\n")
            print("   %-26s %6.1fs  exit %d" % (name, el, rc))
        emit("   （【%s】這一階段 %.1fs）" % (stage, time.time() - t0))
        log.flush()

    # 2026-09-07 #56：這裡原本是
    #     print("合計 %.1f 分鐘（步驟時間相加 %.1f 分鐘——差額就是並行省下來的）"
    #           % (sum(...)/60.0, sum(...)/60.0))
    # **兩個參數是同一個算式** ⇒ 兩個數字永遠相等、「差額」永遠 0，
    # 看起來像「並行一秒都沒省到」（22:00 那班印的是「合計 28.8（相加 28.8）」，
    # 實際牆鐘 24.9 分、省了 3.9 分）。合計要用牆鐘＝總經過時間。
    wall = time.time() - t_all
    add = sum(t for t, _, _ in times)
    emit("\n═══ 最久的 10 步 ═══")
    for el, name, rc in sorted(times, reverse=True)[:10]:
        emit("   %-26s %6.1fs%s" % (name, el, "" if rc == 0 else "   ⚠ exit %d" % rc))
    emit("合計 %.1f 分鐘（牆鐘 %.1fs）；步驟時間相加 %.1f 分鐘（%.1fs）"
         "——差額 %.1fs 是並行省下來的" % (wall / 60.0, wall, add / 60.0, add, add - wall))
    bad = [(n, rc) for _, n, rc in times if rc != 0]
    if bad:
        emit("⚠ 非零離開碼：" + "、".join("%s(%d)" % x for x in bad))
    log.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
