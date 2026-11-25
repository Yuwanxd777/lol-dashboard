# -*- coding: utf-8 -*-
"""transfers_hourly.py publish() 的回歸：git push 失敗要就地重試一次（2026-11-26 #3737）。

  python scripts/transfers_hourly_push_test.py              測 scripts/transfers_hourly.py
  python scripts/transfers_hourly_push_test.py <某個.py>    測指定的檔（拿修之前的版本當正控制：[2][3][6] 要翻紅）

背景：每小時轉會班 commit 完只 push 一次。GitHub 端偶爾回暫時性的錯誤——2026-11-23 18:15／18:44 兩次「cannot lock ref」、
11-26 00:17 一次「remote rejected (Internal Server Error)」——修之前日誌只有一行「git.exe push → 1」就往下走，
commit 留在本機，主站（GitHub Pages）的轉會分頁要等 30 分鐘後下一班才補推。

沙盒：不起任何子程序、不 commit、不 push、不起 wrangler、不寫 transfers_hourly_log.txt 正本。
  接管的出口／入口：run（起子程序＋寫日誌）、模組裡的 subprocess（publish 直接叫 git diff／git rev-list 的那兩處；
  其他指令一律當場報「沙盒漏接」）、模組裡的 time（sleep）、LOG／ROOT／SITE 與所有指著 repo 的路徑常數、sys.argv。
  開跑前 assert 模組層沒有任何路徑常數還指著真實 repo（GIT／NPX 是執行檔路徑，run 已接管，不算）。
  [1] push 第一次就成功 ⇒ 只推 1 次、沒有警告、不睡、回傳 True
  [2] 第一次 1、第二次 0 ⇒ 推 2 次（指令一模一樣）、有「重試」那行、沒有「仍失敗」、回傳 True
  [3] 兩次都 1 ⇒ 剛好 2 次就停（不無限重試）、有「仍失敗」那行、回傳 True（轉會網站照樣要部署）
  [4] 守門失敗 ⇒ 一次都不推（重試不可以繞過守門）
  [5] 沒有要推的 commit ⇒ 不跑守門、不推
  [6] 整班 do_main：push 兩次都失敗，後面的 wrangler 部署照樣有跑（失敗分支不可以把後面的步驟一起帶走）
  [7] 正本日誌的大小與時間沒變
"""
import importlib.util
import io
import os
import sys
import tempfile
import types

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


def kind(cmd):
    s = [os.path.basename(str(c)) for c in cmd]
    for name, k in (("export_transfer_site.py", "export"), ("preflight_check.py", "preflight"), ("fetch_transfers.py", "fetch"),
                    ("fetch_fan_polls.py", "polls"), ("fetch_team_logos_wiki.py", "logos"), ("wrangler", "wrangler")):
        if name in s:
            return k
    if s[0].lower().startswith("git") and len(s) > 1:
        return "git " + s[1]
    raise AssertionError("沙盒漏接：run 收到不認得的指令 " + " ".join(s[:4]))


class R(object):
    def __init__(self, rc, out=""):
        self.returncode, self.stdout, self.stderr = rc, out, ""


def sandbox(m, tmp, rcs, changed=True, ahead="3"):
    """回傳 (calls, sleeps, 讀日誌的函式)。rcs＝{指令種類: 依序回的離開碼清單}，沒列的回 0；清單用完還被叫就報錯。"""
    root = os.path.join(tmp, "repo")
    site = os.path.join(tmp, "site")
    os.makedirs(root, exist_ok=True)
    os.makedirs(site, exist_ok=True)
    for f in m.FILES:
        with io.open(os.path.join(root, f), "w", encoding="utf-8") as fh:
            fh.write("// sandbox " + f + "\n")
    base = m.ROOT
    nbase = os.path.normcase(base)
    for k, v in list(vars(m).items()):
        if k.startswith("__") or k == "HERE" or not isinstance(v, str):
            continue
        if os.path.normcase(v).startswith(nbase):
            setattr(m, k, os.path.join(root, os.path.relpath(v, base)) if os.path.normcase(v) != nbase else root)
    m.SITE = site
    outer = os.path.normcase(os.path.dirname(REAL_ROOT))
    for k, v in vars(m).items():
        if k.startswith("__") or k == "HERE":
            continue
        if isinstance(v, str) and os.path.normcase(v).startswith(outer):
            raise SystemExit("沙盒漏接：%s 還指著真實路徑（%s）" % (k, v))
    if not os.path.normcase(m.LOG).startswith(os.path.normcase(tmp)):
        raise SystemExit("沙盒漏接：LOG 不在沙盒裡（%s）" % m.LOG)
    calls, sleeps = [], []
    left = {k: list(v) for k, v in rcs.items()}

    def fake_run(cmd, cwd=None, timeout=None):
        k = kind(cmd)
        calls.append((k, list(cmd), cwd, timeout))
        if k in left:
            if not left[k]:
                raise AssertionError("%s 被多叫了一次" % k)
            rc = left[k].pop(0)
        else:
            rc = 0
        m.log("  (假) %s → %d" % (k, rc))
        return rc

    def fake_sp_run(cmd, **kw):
        s = [str(c) for c in cmd]
        if "diff" in s and "--cached" in s:
            return R(1 if changed else 0)
        if "rev-list" in s and "--count" in s:
            return R(0, ahead + "\n")
        raise AssertionError("沙盒漏接：模組直接起了沒接管的子程序 " + " ".join(os.path.basename(x) for x in s[:4]))

    m.run = fake_run
    m.subprocess = types.SimpleNamespace(run=fake_sp_run)
    m.time = types.SimpleNamespace(sleep=lambda s: sleeps.append(s))

    def read_log():
        return io.open(m.LOG, encoding="utf-8").read() if os.path.exists(m.LOG) else ""

    return calls, sleeps, read_log


def n(calls, k):
    return [c for c in calls if c[0] == k]


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "transfers_hourly.py")
    print("被測檔：" + target)
    before = (os.path.getsize(REAL_LOG), os.path.getmtime(REAL_LOG)) if os.path.exists(REAL_LOG) else None
    argv0 = list(sys.argv)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            sys.argv = ["transfers_hourly.py", "main"]
            print("[1] push 第一次就成功")
            m = load(target)
            calls, sleeps, read_log = sandbox(m, os.path.join(tmp, "a"), {"git push": [0]})
            rv = m.publish("測試")
            ck(len(n(calls, "git push")) == 1, "只推 1 次（實際 %d）" % len(n(calls, "git push")))
            ck("⚠" not in read_log(), "日誌沒有警告")
            ck(sleeps == [], "沒有睡")
            ck(rv is True, "回傳 True（實際 %r）" % (rv,))
            ks = [c[0] for c in calls]
            ck(ks == ["export", "git add", "git commit", "preflight", "git push"], "順序＝匯出→add→commit→守門→push（實際 %s）" % ks)

            print("[2] 第一次 1、第二次 0")
            m = load(target)
            calls, sleeps, read_log = sandbox(m, os.path.join(tmp, "b"), {"git push": [1, 0]})
            rv = m.publish("測試")
            p = n(calls, "git push")
            ck(len(p) == 2, "推 2 次（實際 %d）" % len(p))
            ck(len(p) == 2 and p[0] == p[1], "兩次的指令、cwd、timeout 一模一樣")
            ck("重試" in read_log(), "日誌有「重試」那行")
            ck("仍失敗" not in read_log(), "日誌沒有「仍失敗」")
            ck(len(sleeps) == 1 and 0 < sleeps[0] <= 60, "重試前等一下（實際 %s）" % sleeps)
            ck(rv is True, "回傳 True（實際 %r）" % (rv,))
            ck(len(n(calls, "preflight")) == 1, "守門只跑 1 次（重試不重跑守門）")

            print("[3] 兩次都 1")
            m = load(target)
            calls, sleeps, read_log = sandbox(m, os.path.join(tmp, "c"), {"git push": [1, 1]})
            try:
                rv = m.publish("測試")
                over = False
            except AssertionError:
                rv, over = None, True
            p = n(calls, "git push")
            ck(not over and len(p) == 2, "剛好 2 次就停（實際 %d%s）" % (len(p), "，還想推第 3 次" if over else ""))
            ck("仍失敗" in read_log(), "日誌有「仍失敗」那行")
            ck(rv is True, "回傳 True——轉會網站照樣要部署（實際 %r）" % (rv,))

            print("[4] 守門失敗")
            m = load(target)
            calls, sleeps, read_log = sandbox(m, os.path.join(tmp, "d"), {"preflight": [1], "git push": []})
            try:
                rv = m.publish("測試")
                over = False
            except AssertionError:
                rv, over = None, True
            ck(not over and len(n(calls, "git push")) == 0, "一次都不推")
            ck("preflight 失敗" in read_log(), "日誌有「preflight 失敗」")
            ck(sleeps == [], "沒有睡")

            print("[5] 沒有要推的 commit")
            m = load(target)
            calls, sleeps, read_log = sandbox(m, os.path.join(tmp, "e"), {"preflight": [], "git push": []}, changed=False, ahead="0")
            try:
                rv = m.publish("測試")
                over = False
            except AssertionError:
                rv, over = None, True
            ck(not over and not n(calls, "preflight") and not n(calls, "git push"), "不跑守門、不推")
            ck(rv is False, "回傳 False（實際 %r）" % (rv,))

            print("[6] 整班 do_main：push 兩次都失敗，後面的部署照樣跑")
            sys.argv = ["transfers_hourly.py", "main", "--no-review"]
            m = load(target)
            calls, sleeps, read_log = sandbox(m, os.path.join(tmp, "f"), {"git push": [1, 1], "wrangler": [0]})
            err = ""
            try:
                m.do_main()
            except Exception as e:   # 失敗分支寫錯（少 import、打錯名字）會在這裡現形
                err = "%s %s" % (type(e).__name__, str(e)[:120])
            ks = [c[0] for c in calls]
            ck(not err, "do_main 沒有丟例外%s" % ("（" + err + "）" if err else ""))
            ck(len(n(calls, "git push")) == 2, "推 2 次（實際 %d）" % len(n(calls, "git push")))
            ck(len(n(calls, "wrangler")) == 1 and ks and ks[-1] == "wrangler", "最後一步是 wrangler 部署（實際 %s）" % ks)
            ck(n(calls, "wrangler") and n(calls, "wrangler")[0][2] == m.SITE, "部署在沙盒的 SITE 資料夾")
            ck("仍失敗" in read_log(), "日誌有「仍失敗」那行")
    finally:
        sys.argv = argv0
    print("[7] 正本")
    after = (os.path.getsize(REAL_LOG), os.path.getmtime(REAL_LOG)) if os.path.exists(REAL_LOG) else None
    ck(before == after, "transfers_hourly_log.txt 正本沒被碰（大小與時間不變；剛好撞到那一班在寫會誤報，重跑即可）")
    print("\n結果：✓ %d／✗ %d" % (OK[0], NG[0]))
    sys.exit(1 if NG[0] else 0)


if __name__ == "__main__":
    main()
