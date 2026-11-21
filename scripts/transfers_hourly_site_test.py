# -*- coding: utf-8 -*-
"""transfers_hourly.py do_site() 的回歸：wrangler 部署失敗要重試一次（2026-11-22 #3546）。

  python scripts/transfers_hourly_site_test.py              測 scripts/transfers_hourly.py
  python scripts/transfers_hourly_site_test.py <某個.py>    測指定的檔（拿修之前的版本當正控制：[2][3] 要翻紅）

背景：wrangler 的登入權杖約一小時到期。到期點剛好落在一次部署的兩個 API 請求之間時，第二個請求回 401
「Authentication error [code: 10000]」，wrangler 不重試、離開碼 1，但離開前會把權杖換新——所以馬上再跑一次就會過。
2026-11-20 13:10／11-21 00:40／11-22 04:40 三次都是這個長相（277 次部署裡 3 次）；修之前日誌只有一行「→ 1」，
發生在 [main] 那趟的話轉會網站要等 30 分鐘後的 [site] 才補上。

沙盒：不起 wrangler、不碰真的 轉會網站 資料夾、不寫 transfers_hourly_log.txt 正本。
  接管的出口／入口：run（唯一會起子程序的地方）、LOG、ROOT、SITE、time.sleep；
  開跑前 assert 模組層沒有任何路徑常數還指著真實 repo（GIT／NPX 是執行檔路徑，run 已接管，不算）。
  [1] 第一次就成功 ⇒ 只部署 1 次、沒有警告、不睡
  [2] 第一次 1、第二次 0 ⇒ 部署 2 次（指令與 cwd 一模一樣）、有「重試」那行、回傳 0
  [3] 兩次都 1 ⇒ 剛好 2 次就停（不無限重試）、有「仍失敗」那行、回傳非 0
  [4] 三個檔真的複製進沙盒的 www/fallback；正本日誌的大小與時間沒變
"""
import importlib.util
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REAL_ROOT = os.path.dirname(HERE)
REAL_LOG = os.path.join(REAL_ROOT, "transfers_hourly_log.txt")
OK = [0]
NG = [0]


def ck(cond, msg):
    if cond:
        OK[0] += 1
        print("  ✓ " + msg)
    else:
        NG[0] += 1
        print("  ✗ " + msg)


def load(path):
    spec = importlib.util.spec_from_file_location("transfers_hourly_under_test", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def sandbox(m, tmp, rcs):
    """回傳 (calls, sleeps, 讀日誌的函式)。rcs＝假 run 依序回的離開碼，用完就報錯（多跑一次會被抓到）。"""
    root = os.path.join(tmp, "repo")
    site = os.path.join(tmp, "site")
    os.makedirs(root, exist_ok=True)
    os.makedirs(site, exist_ok=True)
    for f in m.FILES:
        with io.open(os.path.join(root, f), "w", encoding="utf-8") as fh:
            fh.write("// sandbox " + f + "\n")
    # 模組層所有指著真實 repo 的路徑常數（ROOT／LOG／REVIEW_STATE／REVIEW_LOG…）一律搬到沙盒的同名相對路徑；
    # SITE 在 repo 外面（隔壁的 轉會網站），另外指定。
    # 以被測檔自己算出來的 ROOT 為準（拿別處的舊版檔當正控制時，它的 ROOT 不是 repo 根目錄）。
    base = m.ROOT
    nbase = os.path.normcase(base)
    for k, v in list(vars(m).items()):
        if k.startswith("__") or k == "HERE" or not isinstance(v, str):
            continue
        if os.path.normcase(v).startswith(nbase):
            setattr(m, k, os.path.join(root, os.path.relpath(v, base)) if os.path.normcase(v) != nbase else root)
    m.SITE = site
    # 搬完再查一次：不可以還有字串常數指著真實的專案資料夾或它隔壁的 轉會網站（之後有人加新出口，這裡先擋，不會寫壞正本）
    outer = os.path.normcase(os.path.dirname(REAL_ROOT))
    for k, v in vars(m).items():
        if k.startswith("__") or k == "HERE":
            continue
        if isinstance(v, str) and os.path.normcase(v).startswith(outer):
            raise SystemExit(f"沙盒漏接：{k} 還指著真實路徑（{v}）")
    if not os.path.normcase(m.LOG).startswith(os.path.normcase(tmp)):
        raise SystemExit(f"沙盒漏接：LOG 不在沙盒裡（{m.LOG}）")
    calls, sleeps, left = [], [], list(rcs)

    def fake_run(cmd, cwd=None, timeout=None):
        calls.append((list(cmd), cwd, timeout))
        if not left:
            raise AssertionError("run 被多叫了一次")
        rc = left.pop(0)
        m.log(f"  (假) wrangler → {rc}")
        return rc

    m.run = fake_run
    if hasattr(m, "time"):
        m.time.sleep = lambda s: sleeps.append(s)

    def read_log():
        return io.open(m.LOG, encoding="utf-8").read() if os.path.exists(m.LOG) else ""

    return calls, sleeps, read_log


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "transfers_hourly.py")
    print("被測檔：" + target)
    before = (os.path.getsize(REAL_LOG), os.path.getmtime(REAL_LOG)) if os.path.exists(REAL_LOG) else None
    import time as _time
    real_sleep = _time.sleep
    try:
        with tempfile.TemporaryDirectory() as tmp:
            print("[1] 第一次就成功")
            m = load(target)
            calls, sleeps, read_log = sandbox(m, os.path.join(tmp, "a"), [0])
            rc = m.do_site()
            ck(len(calls) == 1, f"只部署 1 次（實際 {len(calls)}）")
            ck("⚠" not in read_log(), "日誌沒有警告")
            ck(sleeps == [], "沒有睡")
            ck(rc in (0, None), f"回傳 0／None（實際 {rc!r}）")
            ck(calls[0][1] == m.SITE and "wrangler" in calls[0][0] and "lol-transfer" in calls[0][0],
               "在沙盒的 SITE 資料夾跑 wrangler pages deploy（專案 lol-transfer）")

            print("[2] 第一次 1、第二次 0")
            m = load(target)
            calls, sleeps, read_log = sandbox(m, os.path.join(tmp, "b"), [1, 0])
            rc = m.do_site()
            ck(len(calls) == 2, f"部署 2 次（實際 {len(calls)}）")
            ck(len(calls) == 2 and calls[0] == calls[1], "兩次的指令、cwd、timeout 一模一樣")
            ck("重試" in read_log(), "日誌有「重試」那行")
            ck("仍失敗" not in read_log(), "日誌沒有「仍失敗」")
            ck(len(sleeps) == 1 and 0 < sleeps[0] <= 60, f"重試前等一下（實際 {sleeps}）")
            ck(rc == 0, f"回傳 0（實際 {rc!r}）")

            print("[3] 兩次都 1")
            m = load(target)
            calls, sleeps, read_log = sandbox(m, os.path.join(tmp, "c"), [1, 1])
            try:
                rc = m.do_site()
                over = False
            except AssertionError:
                rc, over = None, True
            ck(not over and len(calls) == 2, f"剛好 2 次就停（實際 {len(calls)}{'，還想跑第 3 次' if over else ''}）")
            ck("仍失敗" in read_log(), "日誌有「仍失敗」那行")
            ck(rc not in (0, None), f"回傳非 0（實際 {rc!r}）")

            print("[4] 複製與正本")
            dst = os.path.join(m.SITE, "www", "fallback")
            ck(all(os.path.exists(os.path.join(dst, f)) for f in m.FILES), "三個檔複製進沙盒的 www/fallback")
            ck(io.open(os.path.join(dst, m.FILES[0]), encoding="utf-8").read().startswith("// sandbox"), "複製的是沙盒的檔，不是正本")
    finally:
        _time.sleep = real_sleep
    after = (os.path.getsize(REAL_LOG), os.path.getmtime(REAL_LOG)) if os.path.exists(REAL_LOG) else None
    ck(before == after, "transfers_hourly_log.txt 正本沒被碰（大小與時間不變；剛好撞到整點那趟在寫會誤報，重跑即可）")
    print(f"\n結果：✓ {OK[0]}／✗ {NG[0]}")
    sys.exit(1 if NG[0] else 0)


if __name__ == "__main__":
    main()
