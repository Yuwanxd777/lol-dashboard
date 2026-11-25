# -*- coding: utf-8 -*-
"""fetch_release.py 的「連不上 wiki 就地重試一次」回歸測試（2026-11-25 主對話迴圈 #3732）。

不開瀏覽器、不碰網路、不寫真的 champ_release.js：
  ‧ playwright 換成假模組（照劇本丟例外或回內容）
  ‧ jget（DDragon）換成假資料；urllib.request.urlopen 換成「一被呼叫就中止」（漏接會在打網路之前擋下）
  ‧ OUT 搬到暫存資料夾；跑之前確認模組層沒有任何字串常數還指著真實 repo
  ‧ time.sleep 換成只記錄不等待
用法：
  python scripts/fetch_release_retry_test.py              # 測 scripts/fetch_release.py
  python scripts/fetch_release_retry_test.py 某個檔.py     # 測別的版本（例：git show 舊版 > 暫存檔 ⇒ 應該紅）
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import time
import types
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TARGET = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "scripts", "fetch_release.py")
REAL_OUT = os.path.join(ROOT, "champ_release.js")

CHAMPS = {"Aatrox": "Aatrox", "Ahri": "Ahri", "MonkeyKing": "Wukong", "Belveth": "Bel'Veth", "Chogath": "Cho'Gath",
          "DrMundo": "Dr. Mundo", "Fiddlesticks": "Fiddlesticks", "Garen": "Garen", "Jinx": "Jinx", "Zed": "Zed"}
DDRAGON_DATA = {cid: {"name": nm} for cid, nm in CHAMPS.items()}
DDRAGON_DATA["Jade_Ahri"] = {"name": "Ahri"}       # 經典服：不可以進輸出
LUA = "return {\n" + "".join(
    '  ["%s"] = {\n    ["apiname"] = "%s",\n    ["date"] = "20%02d-01-%02d",\n  },\n' % (nm, cid, 10 + i, 1 + i)
    for i, (cid, nm) in enumerate(sorted(CHAMPS.items()))) + "}\n"
EXPECT = {cid: "20%02d-01-%02d" % (10 + i, 1 + i) for i, (cid, nm) in enumerate(sorted(CHAMPS.items()))}
OLD_TEXT = "window.CHAMP_RELEASE=" + json.dumps({k: "1999-09-09" for k in CHAMPS}, sort_keys=True) + ";\n"
TIMEOUT_MSG = "Page.goto: net::ERR_TIMED_OUT at https://wiki.example/raw\nCall log:\n  - navigating"

STATE = {"script": [], "goto": 0, "launch": 0, "close": 0, "sleeps": []}


class _Resp(object):
    def __init__(self, status):
        self.status = status


class _Page(object):
    _body = ""

    def goto(self, url, wait_until=None, timeout=None):
        STATE["goto"] += 1
        act = STATE["script"].pop(0)
        if isinstance(act, Exception):
            raise act
        self._body = act[1]
        return _Resp(act[0])

    def inner_text(self, sel):
        return self._body


class _Browser(object):
    def new_page(self):
        return _Page()

    def close(self):
        STATE["close"] += 1


class _Chromium(object):
    def launch(self, *a, **k):
        STATE["launch"] += 1
        return _Browser()


class _P(object):
    chromium = _Chromium()


class _Ctx(object):
    def __enter__(self):
        return _P()

    def __exit__(self, *a):
        return False


def _install_fakes():
    pw = types.ModuleType("playwright")
    api = types.ModuleType("playwright.sync_api")
    api.sync_playwright = lambda: _Ctx()
    pw.sync_api = api
    sys.modules["playwright"] = pw
    sys.modules["playwright.sync_api"] = api

    def _no_net(*a, **k):
        raise AssertionError("沙盒漏接：有人真的去打網路 %r" % (a[:1],))
    urllib.request.urlopen = _no_net
    time.sleep = lambda s: STATE["sleeps"].append(s)


def _fake_jget(url, timeout=30):
    if url.endswith("versions.json"):
        return ["99.1.1"]
    if url.endswith("champion.json"):
        return {"data": DDRAGON_DATA}
    raise AssertionError("沙盒漏接：jget 沒料到的網址 " + url)


def _load(sandbox):
    spec = importlib.util.spec_from_file_location("fetch_release_under_test", TARGET)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.OUT = os.path.join(sandbox, "champ_release.js")
    mod.jget = _fake_jget
    # 出口點名：模組層不可以還有字串常數指著真實 repo（以後多一個輸出檔，這裡會先擋下）
    real = os.path.normcase(os.path.abspath(ROOT))
    for k, v in vars(mod).items():
        if k.startswith("__") or not isinstance(v, str) or "://" in v:
            continue
        if os.path.normcase(os.path.abspath(v)).startswith(real) and (os.sep in v or "/" in v):
            raise AssertionError("沙盒漏接：模組常數 %s 還指著真實 repo：%s" % (k, v))
    return mod


def _run(mod, script, seed_old=True):
    """跑一次 main()。回傳 dict：rc／raised／out／檔案內容。"""
    STATE.update(script=list(script), goto=0, launch=0, close=0, sleeps=[])
    if seed_old:
        with io.open(mod.OUT, "w", encoding="utf-8", newline="") as f:
            f.write(OLD_TEXT)
    elif os.path.exists(mod.OUT):
        os.remove(mod.OUT)
    buf = io.StringIO()
    rc, raised = 0, None
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            mod.main()
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
        except Exception as e:      # 沒被接住的例外＝實際跑起來會是 traceback＋離開碼 1
            rc, raised = 1, e
    text = io.open(mod.OUT, encoding="utf-8", newline="").read() if os.path.exists(mod.OUT) else None
    return {"rc": rc, "raised": raised, "out": buf.getvalue(), "text": text,
            "goto": STATE["goto"], "launch": STATE["launch"], "close": STATE["close"], "sleeps": list(STATE["sleeps"])}


def _parsed(text):
    return json.loads(text.strip()[len("window.CHAMP_RELEASE="):].rstrip(";\n "))


def main():
    out = sys.stdout.buffer
    res = []

    def check(name, ok, detail=""):
        res.append(bool(ok))
        out.write(("  %s %s%s\n" % ("✓" if ok else "✗", name, ("｜" + detail) if detail and not ok else "")).encode("utf-8"))

    real_md5 = hashlib.md5(open(REAL_OUT, "rb").read()).hexdigest() if os.path.exists(REAL_OUT) else None
    sandbox = tempfile.mkdtemp(prefix="fetch_release_test_")
    try:
        _install_fakes()
        mod = _load(sandbox)
        out.write(("受測檔：%s\n" % TARGET).encode("utf-8"))
        check("沙盒：OUT 在暫存資料夾裡", os.path.normcase(os.path.abspath(mod.OUT)).startswith(os.path.normcase(sandbox)))

        out.write("A 第一次逾時、第二次成功 ⇒ 重試後照常寫檔\n".encode("utf-8"))
        r = _run(mod, [Exception(TIMEOUT_MSG), (200, LUA)])
        check("A1 離開碼 0、沒有漏出例外", r["rc"] == 0 and r["raised"] is None, "rc=%r raised=%r" % (r["rc"], r["raised"]))
        check("A2 goto 叫了 2 次", r["goto"] == 2, "goto=%d" % r["goto"])
        check("A3 中間等了一次（秒數 > 0）", len(r["sleeps"]) == 1 and r["sleeps"][0] > 0, "sleeps=%r" % r["sleeps"])
        check("A4 寫出的內容＝這次抓到的 10 隻", r["text"] is not None and r["text"] != OLD_TEXT and _parsed(r["text"]) == EXPECT,
              "text=%r" % (r["text"] or "")[:80])
        check("A5 日誌有「重試一次」、沒有「仍失敗」", "重試一次" in r["out"] and "仍失敗" not in r["out"], r["out"][:200])
        check("A6 兩次開的瀏覽器都有關", r["launch"] == 2 and r["close"] == 2, "launch=%d close=%d" % (r["launch"], r["close"]))

        out.write("B 兩次都逾時 ⇒ 保留舊檔、離開碼 1、不噴 traceback\n".encode("utf-8"))
        r = _run(mod, [Exception(TIMEOUT_MSG), Exception(TIMEOUT_MSG)])
        check("B1 離開碼 1（走 sys.exit，不是漏出例外）", r["rc"] == 1 and r["raised"] is None, "rc=%r raised=%r" % (r["rc"], r["raised"]))
        check("B2 goto 叫了 2 次（只重試一次，不無限試）", r["goto"] == 2, "goto=%d" % r["goto"])
        check("B3 舊檔逐位元組不變", r["text"] == OLD_TEXT)
        check("B4 日誌有「重試仍失敗」與「保留舊的」", "重試仍失敗" in r["out"] and "保留舊的" in r["out"], r["out"][:200])
        check("B5 日誌只帶錯誤第一行（不含 Call log）", "ERR_TIMED_OUT" in r["out"] and "Call log" not in r["out"], r["out"][:300])

        out.write("C 第一次就成功 ⇒ 不重試、不等待（對照組）\n".encode("utf-8"))
        r = _run(mod, [(200, LUA)], seed_old=False)
        check("C1 離開碼 0", r["rc"] == 0 and r["raised"] is None, "rc=%r raised=%r" % (r["rc"], r["raised"]))
        check("C2 goto 只叫 1 次、沒有等待", r["goto"] == 1 and r["sleeps"] == [], "goto=%d sleeps=%r" % (r["goto"], r["sleeps"]))
        check("C3 內容正確、經典服 Jade_Ahri 沒進來", r["text"] is not None and _parsed(r["text"]) == EXPECT)
        check("C4 日誌沒有「重試」", "重試" not in r["out"], r["out"][:200])

        out.write("D HTTP 502 維護公告 ⇒ 舊守門照舊：保留舊檔、離開碼 0、不重試\n".encode("utf-8"))
        r = _run(mod, [(502, "Wiki is under maintenance")])
        check("D1 離開碼 0", r["rc"] == 0 and r["raised"] is None, "rc=%r raised=%r" % (r["rc"], r["raised"]))
        check("D2 舊檔逐位元組不變", r["text"] == OLD_TEXT)
        check("D3 goto 只叫 1 次", r["goto"] == 1, "goto=%d" % r["goto"])
        check("D4 日誌有「來源異常」", "來源異常" in r["out"], r["out"][:200])

        out.write("E 200 但內容解析不到九成 ⇒ 舊守門照舊：保留舊檔\n".encode("utf-8"))
        r = _run(mod, [(200, "return {}")])
        check("E1 離開碼 0、舊檔不變", r["rc"] == 0 and r["text"] == OLD_TEXT, "rc=%r" % r["rc"])
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)
    now_md5 = hashlib.md5(open(REAL_OUT, "rb").read()).hexdigest() if os.path.exists(REAL_OUT) else None
    check("F 真的 champ_release.js 沒被動到（md5 前後相同）", real_md5 == now_md5, "%s -> %s" % (real_md5, now_md5))
    bad = res.count(False)
    out.write(("結果：%d ✓／%d ✗\n" % (res.count(True), bad)).encode("utf-8"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
