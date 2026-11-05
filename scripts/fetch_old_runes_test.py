# -*- coding: utf-8 -*-
"""fetch_old_runes 抓不到時不可以讓某一年從線上消失（2026-11-05 精進迴圈 #2608）。

沙盒接管：OUT（輸出路徑）、urlopen（入口）、time.sleep。跑完 assert 正本 old_runes.js 的 md5／mtime 沒動。
只有沙盒才有的證據：假符文 ZZ Probe 9942，真資料不可能有。
舊版對照釘 94bc747a（本輪修改前的版本）。環境變數 RUNES_SRC 可指定被測原始碼（autopilot/_m2608_mutate.py 用）。
用法：python -u scripts/fetch_old_runes_test.py
"""
import contextlib, hashlib, importlib.util, io, json, os, shutil, subprocess, sys, tempfile, time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC = os.environ.get("RUNES_SRC") or os.path.join(HERE, "fetch_old_runes.py")
OLDREV = "94bc747a"
REAL = os.path.join(REPO, "old_runes.js")
real_urlopen, real_sleep = urllib.request.urlopen, time.sleep
res = {"ok": 0, "bad": 0}
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def ck(name, cond, extra=None):
    """cond／extra 都是 lambda：資料長得不對時算這一條 ✗，不是整支崩潰（突變測試才分得出「擋下」和「崩潰」）。"""
    try:
        good = bool(cond())
    except Exception as e:
        good = False
        print(f"    （斷言例外 {type(e).__name__}: {e}）")
    res["ok" if good else "bad"] += 1
    x = ""
    if not good and extra:
        try:
            x = f"  → {extra()}"
        except Exception:
            x = "  → （extra 取不到）"
    print(("  ✓ " if good else "  ✗ ") + name + x)


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


class Resp:
    def __init__(self, b): self.b = b
    def read(self): return self.b


def load(src, tag):
    # 模組 import 時包 sys.stdout.buffer，給它拋棄式的 stdout，被回收時才不會關到真的
    spec = importlib.util.spec_from_file_location(tag, src)
    m = importlib.util.module_from_spec(spec)
    keep = sys.stdout
    sys.stdout = type("S", (), {"buffer": io.BytesIO(), "write": lambda s, x: 0, "flush": lambda s: None})()
    try:
        spec.loader.exec_module(m)
    finally:
        sys.stdout = keep
    return m


def rune_json(v, drop=()):
    d = {}
    for i, ty in enumerate(("red", "yellow", "blue", "black")):
        if ty in drop:
            continue
        d[f"{i}3"] = {"name": f"新{ty}{v}", "description": "d", "rune": {"tier": 3, "type": ty}, "image": {"full": f"{i}.png"}}
        d[f"{i}1"] = {"name": f"低階{ty}", "description": "d", "rune": {"tier": 1, "type": ty}, "image": {"full": "x.png"}}
    d["99"] = {"name": "怪色", "description": "d", "rune": {"tier": 3, "type": "green"}, "image": {"full": "y.png"}}
    return {"data": d}


def prev_data():
    return {str(y): {"ver": "舊", "red": [{"n": f"ZZ Probe 9942 {y}", "d": "", "img": ""}], "yellow": [], "blue": [], "black": []}
            for y in (2013, 2014, 2015, 2016, 2017)}


def run(src, fail=lambda u: False, reply=None, prev="good"):
    """回傳 (rc, 輸出, 寫出的 dict 或 None, calls, timeouts, 模組)。"""
    d = tempfile.mkdtemp(prefix="oldrunes_")
    out = os.path.join(d, "old_runes.js")
    if prev == "good":
        open(out, "w", encoding="utf-8").write("window.OLD_RUNES=" + json.dumps(prev_data(), ensure_ascii=False) + ";")
    elif prev == "broken":
        open(out, "w", encoding="utf-8").write("window.OLD_RUNES={壞掉")
    m = load(src, "t_" + os.path.basename(d))
    m.OUT = out   # 模組只有 OUT 這一個輸出路徑；正本有沒有被動由檔尾的 md5／mtime 把關
    calls, timeouts = [], []

    def urlopen(req, timeout=None):
        u = req.full_url if hasattr(req, "full_url") else req
        calls.append(u); timeouts.append(timeout)
        if fail(u):
            raise OSError("模擬連線被斷 " + u)
        v = u.split("/cdn/")[1].split("/")[0]
        r = reply(v) if reply else rune_json(v)
        return Resp(json.dumps(r, ensure_ascii=False).encode("utf-8"))

    urllib.request.urlopen, time.sleep = urlopen, (lambda s: None)
    buf, rc = io.StringIO(), 0
    try:
        with contextlib.redirect_stdout(buf):
            try:
                m.main()
            except SystemExit as e:
                rc = e.code or 0
            except Exception as e:      # 被測模組自己炸掉：回報成 rc，斷言照常判
                rc = f"例外 {type(e).__name__}"
    finally:
        urllib.request.urlopen, time.sleep = real_urlopen, real_sleep
    data = None
    if os.path.exists(out):
        try:
            data, _ = json.JSONDecoder().raw_decode(open(out, encoding="utf-8").read(), len("window.OLD_RUNES="))
        except Exception:
            data = "壞檔"
    left = sorted(os.listdir(d))
    shutil.rmtree(d, ignore_errors=True)
    return rc, buf.getvalue(), data, calls, timeouts, left


YEARS = {"2013", "2014", "2015", "2016", "2017"}
real_md5, real_mtime = md5(REAL), os.path.getmtime(REAL)

print("── 全部抓得到 ──")
rc, o, d, calls, to, left = run(SRC)
ck("rc 0", lambda: rc == 0, lambda: rc)
ck("五年都在、都是新資料", lambda: set(d) == YEARS and all(d[y]["red"][0]["n"].startswith("新red") for y in d), lambda: d)
ck("ver 是當年版本", lambda: d["2014"]["ver"] == "4.16.1", lambda: d["2014"])
ck("只留 tier 3", lambda: all(len(d["2015"][k]) == 1 for k in ("red", "yellow", "blue", "black")), lambda: d["2015"])
ck("上一版的探針被蓋掉（成功路徑真的有寫）", lambda: "ZZ Probe 9942" not in json.dumps(d, ensure_ascii=False))
ck("沒印沿用", lambda: "沿用" not in o, lambda: o)
ck("單次逾時 30 秒", lambda: set(to) == {30}, lambda: to)
ck("每年一次請求", lambda: len(calls) == 5, lambda: calls)
ck("沒留 tmp", lambda: left == ["old_runes.js"], lambda: left)

print("── 一年抓不到 ──")
rc, o, d, calls, to, left = run(SRC, fail=lambda u: "/5.16.1/" in u)
ck("rc 0（有上一版可沿用）", lambda: rc == 0, lambda: rc)
ck("2015 沿用上一版", lambda: d["2015"]["red"][0]["n"] == "ZZ Probe 9942 2015", lambda: d["2015"])
ck("其他年是新的", lambda: d["2014"]["ver"] == "4.16.1" and d["2016"]["ver"] == "6.16.2", lambda: d)
ck("五年都在", lambda: set(d) == YEARS, lambda: list(d))
ck("年份順序不變", lambda: list(d) == sorted(YEARS), lambda: list(d))
ck("日誌指名沿用 2015", lambda: "沿用上一版 old_runes.js：2015" in o, lambda: o)
ck("失敗的版本試 2 次", lambda: sum("/5.16.1/" in u for u in calls) == 2, lambda: calls)
ck("一次失敗不會擋後面的年份", lambda: any("/7.16.1/" in u for u in calls), lambda: calls)

print("── 200 但內容不對 ──")
rc, o, d, *_ = run(SRC, reply=lambda v: rune_json(v, drop=("black",)) if v == "6.16.2" else rune_json(v))
ck("缺一色的年份沿用上一版", lambda: d["2016"]["red"][0]["n"] == "ZZ Probe 9942 2016", lambda: d["2016"])
ck("日誌指名哪一色", lambda: "black 0 筆" in o, lambda: o)
ck("其他年不受影響", lambda: d["2017"]["ver"] == "7.16.1", lambda: d["2017"])
rc, o, d, *_ = run(SRC, reply=lambda v: {"data": {}} if v == "3.15.5" else rune_json(v))
ck("data 空表沿用上一版", lambda: d["2013"]["red"][0]["n"] == "ZZ Probe 9942 2013", lambda: d["2013"])
rc, o, d, *_ = run(SRC, reply=lambda v: {"type": "rune"} if v == "3.15.5" else rune_json(v))
ck("沒有 data 鍵沿用上一版", lambda: d["2013"]["red"][0]["n"] == "ZZ Probe 9942 2013", lambda: d["2013"])

print("── 全斷 ──")
rc, o, d, calls, *_ = run(SRC, fail=lambda u: True)
ck("rc 0（五年都沿用）", lambda: rc == 0, lambda: rc)
ck("檔案內容就是上一版", lambda: d == prev_data(), lambda: d)
ck("連 2 個版本失敗就不再上網（2 年 × 2 次）", lambda: len(calls) == 4, lambda: calls)
ck("日誌列出五年", lambda: "2013、2014、2015、2016、2017" in o, lambda: o)

print("── 中間成功會把連續失敗歸零 ──")
rc, o, d, calls, *_ = run(SRC, fail=lambda u: "/3.15.5/" in u or "/5.16.1/" in u)
ck("隔一年的失敗不觸發停手，五個版本都問到", lambda: all(any(f"/{v}/" in u for u in calls) for v in ("3.15.5", "4.16.1", "5.16.1", "6.16.2", "7.16.1")), lambda: calls)
ck("新舊混合", lambda: d["2014"]["ver"] == "4.16.1" and d["2013"]["ver"] == "舊", lambda: d)

print("── 沒有上一版 ──")
rc, o, d, *_ = run(SRC, fail=lambda u: True, prev=None)
ck("全斷 rc 1", lambda: rc == 1, lambda: rc)
ck("不寫檔", lambda: d is None, lambda: d)
ck("日誌講不寫檔", lambda: "不寫檔" in o, lambda: o)
rc, o, d, *_ = run(SRC, fail=lambda u: "/4.16.1/" in u, prev=None)
ck("缺一年 rc 1", lambda: rc == 1, lambda: rc)
ck("其他年照寫", lambda: set(d) == YEARS - {"2014"}, lambda: d and list(d))
ck("日誌指名 2014", lambda: "沒有上一版可沿用：2014" in o, lambda: o)
rc, o, d, *_ = run(SRC, fail=lambda u: True, prev="broken")
ck("上一版壞檔＋全斷 rc 1", lambda: rc == 1, lambda: rc)
ck("壞檔不被覆寫成空表", lambda: d == "壞檔", lambda: d)
ck("日誌講讀不到上一版", lambda: "讀不到上一版" in o, lambda: o)
rc, o, d, *_ = run(SRC, prev="broken")
ck("上一版壞檔＋抓得到 ⇒ rc 0 且修好", lambda: rc == 0 and set(d) == YEARS, lambda: (rc, d))

print("── 舊版對照（釘 " + OLDREV + "）──")
td = tempfile.mkdtemp(prefix="oldrunes_old_")
oldsrc = os.path.join(td, "fetch_old_runes.py")
blob = subprocess.run(["git", "show", f"{OLDREV}:scripts/fetch_old_runes.py"], cwd=REPO, capture_output=True).stdout
ck("拉得到舊版", lambda: b"OLD_RUNES" in blob and b"load_prev" not in blob, lambda: blob[:80])
open(oldsrc, "wb").write(blob)
rc, o, d, *_ = run(oldsrc, fail=lambda u: "/5.16.1/" in u)
ck("舊版：一年抓不到 ⇒ 那一年消失、rc 0", lambda: rc == 0 and "2015" not in d, lambda: (rc, d and list(d)))
rc, o, d, *_ = run(oldsrc, fail=lambda u: True)
ck("舊版：全斷 ⇒ 寫成空表、rc 0", lambda: rc == 0 and d == {}, lambda: (rc, d))
shutil.rmtree(td, ignore_errors=True)

print("── 正本沒被動 ──")
ck("old_runes.js md5 不變", lambda: md5(REAL) == real_md5)
ck("old_runes.js mtime 不變", lambda: os.path.getmtime(REAL) == real_mtime)
ck("沒留 tmp", lambda: not os.path.exists(REAL + ".tmp"))

print(f"\n合計 ✓ {res['ok']}　✗ {res['bad']}")
sys.exit(1 if res["bad"] else 0)
