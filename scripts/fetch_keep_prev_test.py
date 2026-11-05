# -*- coding: utf-8 -*-
"""fetch_masteries／fetch_jungle 抓不到時不可以讓資料從線上消失（2026-11-05 精進迴圈 #2606）。

沙盒接管：OUT（兩支的輸出路徑）、urlopen（入口）、time.sleep、fetch_jungle 的 api／csv 入口。
只有沙盒才有的證據：假天賦 ZZ Probe 9942、假賽季卡 ZZ9942，真資料不可能有。
舊版對照釘 85206188（本輪修改前的版本）。
環境變數 MAST_SRC／JUNGLE_SRC 可指定被測原始碼（autopilot/_m2606_mutate.py 用來跑突變）。
用法：python -u scripts/fetch_keep_prev_test.py
"""
import contextlib, hashlib, importlib.util, io, json, os, shutil, subprocess, sys, tempfile, time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
MAST = os.environ.get("MAST_SRC") or os.path.join(HERE, "fetch_masteries.py")
JUNG = os.environ.get("JUNGLE_SRC") or os.path.join(HERE, "fetch_jungle.py")
OLDREV = "85206188"
REAL = [os.path.join(REPO, "masteries.js"), os.path.join(REPO, "jungle.js")]
real_urlopen, real_sleep = urllib.request.urlopen, time.sleep
res = {"ok": 0, "bad": 0}


def ck(name, cond, extra=""):
    res["ok" if cond else "bad"] += 1
    print(("  ✓ " if cond else "  ✗ ") + name + ("" if cond else f"  → {extra}"))


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


class Resp:
    def __init__(self, b): self.b = b
    def read(self): return self.b


def load(src, tag):
    # fetch_jungle 在 import 時包 sys.stdout.buffer，給它拋棄式的 stdout，被回收時才不會關到真的
    spec = importlib.util.spec_from_file_location(tag, src)
    m = importlib.util.module_from_spec(spec)
    keep = sys.stdout
    sys.stdout = type("S", (), {"buffer": io.BytesIO(), "write": lambda s, x: 0, "flush": lambda s: None})()
    try:
        spec.loader.exec_module(m)
    finally:
        sys.stdout = keep
    return m


# ───────────── masteries ─────────────
def mast_item(name, zh):
    return {"name": name, "image": {"full": name.replace(" ", "") + ".png"}}, {"name": zh}


def mastery_json(v, lang):
    """每個版本兩個天賦：共用 Shared（中文名隨版本不同）＋版本專屬。"""
    d = {"1": {"name": "Shared" if lang == "en" else f"共用{v}", "image": {"full": "1.png"}, "ranks": 1, "description": ["d"]},
         "2": {"name": f"Only {v}" if lang == "en" else f"專屬{v}", "image": {"full": "2.png"}, "ranks": 1, "description": ["d"]}}
    return {"data": d, "tree": {"Ferocity": [[{"masteryId": "1", "prereq": "0"}], [{"masteryId": "2", "prereq": "1"}]]}}


def mast_router(fail=lambda u: False):
    calls, timeouts = [], []

    def urlopen(req, timeout=None):
        u = req.full_url if hasattr(req, "full_url") else req
        calls.append(u); timeouts.append(timeout)
        if fail(u):
            raise OSError("模擬連線被斷 " + u)
        if u.endswith("versions.json"):
            return Resp(json.dumps(["16.22.1"]).encode())
        lang = "en" if "en_US" in u else "zh"
        v = u.split("/cdn/")[1].split("/")[0]
        if u.endswith("mastery.json"):
            return Resp(json.dumps(mastery_json(v, lang)).encode())
        if u.endswith("summoner.json"):
            nm = "Flash" if lang == "en" else ("閃現" if v == "16.22.1" else f"閃現{v}")
            return Resp(json.dumps({"data": {"SummonerFlash": {"id": "SummonerFlash", "name": nm, "image": {"full": "F.png"}}}}).encode())
        raise OSError("沒種的網址 " + u)
    return urlopen, calls, timeouts


def run_mast(out_path, urlopen, src=MAST):
    m = load(src, "m_" + hashlib.md5(os.urandom(4)).hexdigest())
    m.OUT = out_path
    m.translate_line = lambda s: s
    m.urllib.request.urlopen = urlopen
    m.time = type("T", (), {"sleep": staticmethod(lambda s: None)}) if hasattr(m, "time") else None
    buf, rc = io.StringIO(), 0
    try:
        with contextlib.redirect_stdout(buf):
            m.main()
    except SystemExit as e:
        rc = e.code or 0
    finally:
        urllib.request.urlopen = real_urlopen
    return rc, buf.getvalue()


def parse_mast(p):
    s = open(p, encoding="utf-8").read()
    d = json.JSONDecoder()
    a, i = d.raw_decode(s, len("window.LOL_MASTERIES="))
    b, _ = d.raw_decode(s, i + len(";window.LOL_MASTERY_TREES="))
    return a, b


def test_masteries():
    print("── masteries ──")
    d = tempfile.mkdtemp(prefix="mast_")
    out = os.path.join(d, "masteries.js")
    try:
        # 基準：全部抓到
        u, calls, tos = mast_router()
        rc, log = run_mast(out, u)
        ck("全部抓到 exit 0", rc == 0, log[-200:])
        a, t = parse_mast(out)
        ck("全部抓到：五年天賦樹", sorted(t) == ["2013", "2014", "2015", "2016", "2017"], list(t))
        ck("全部抓到：沒有印沿用", "沿用上一版" not in log, log[-200:])
        ck("逾時 30 秒", set(tos) == {30}, set(tos))
        base = open(out, "rb").read()
        ck("全部抓到：召喚師技能與舊譯別名都在", a["Flash"]["zh"] == "閃現" and a["Flash"].get("aliases"), a.get("Flash"))

        # 放一個上一版才有的天賦當證據
        a["ZZ Probe 9942"] = {"zh": "探針", "img": "x", "y": [2017]}
        open(out, "w", encoding="utf-8").write("window.LOL_MASTERIES=" + json.dumps(a, ensure_ascii=False, separators=(",", ":"))
                                                + ";window.LOL_MASTERY_TREES=" + json.dumps(t, ensure_ascii=False, separators=(",", ":")) + ";")
        seeded = open(out, "rb").read()

        # 10-08 那一班的情境：7.16.1 連線被斷
        u, calls, _ = mast_router(lambda x: "/7.16.1/" in x)
        rc, log = run_mast(out, u)
        a2, t2 = parse_mast(out)
        ck("7.16.1 斷線：exit 0", rc == 0, rc)
        ck("7.16.1 斷線：2017 天賦樹還在", "2017" in t2, list(t2))
        ck("7.16.1 斷線：2017 樹就是上一版那棵", t2.get("2017") == t["2017"])
        ck("7.16.1 斷線：只有上一版才有的天賦還在", "ZZ Probe 9942" in a2)
        ck("7.16.1 斷線：專屬天賦 Only 7.16.1 還在", "Only 7.16.1" in a2)
        ck("7.16.1 斷線：印出沿用", "沿用上一版" in log, log[-300:])
        ck("7.16.1 斷線：重試過（同網址 ≥2 次）", calls.count(f"https://ddragon.leagueoflegends.com/cdn/7.16.1/data/en_US/mastery.json") >= 2, len(calls))
        ck("7.16.1 斷線：其他年份的樹照新資料", t2["2013"] == t["2013"])

        # 整個 CDN 掛掉：檔案逐位元不變、exit 0、不會每個網址都等逾時
        open(out, "wb").write(seeded)
        u, calls, _ = mast_router(lambda x: True)
        rc, log = run_mast(out, u)
        ck("全斷：exit 0（有上一版）", rc == 0, rc)
        a3, t3 = parse_mast(out)
        ck("全斷：天賦數不變", len(a3) == len(a), (len(a3), len(a)))
        ck("全斷：五年樹都在", len(t3) == 5, list(t3))
        ck("全斷：召喚師技能還在", "Flash" in a3)
        ck("全斷：內容與上一版相同", a3 == a and t3 == t)
        ck("全斷：連 2 個網址失敗就停（最多 4 次請求）", len(calls) <= 4, len(calls))

        # 只有召喚師舊譯少一版：別名不可以變少
        open(out, "wb").write(seeded)
        before = list(a["Flash"].get("aliases") or [])
        u, calls, _ = mast_router(lambda x: "/4.21.5/data/zh_TW/summoner" in x)
        rc, log = run_mast(out, u)
        a4, _t = parse_mast(out)
        ck("舊譯少一版：別名沒變少", set(before) <= set(a4["Flash"].get("aliases") or []), (before, a4["Flash"]))
        ck("舊譯少一版：別名裡有 4.21.5 那條", "閃現4.21.5" in (a4["Flash"].get("aliases") or []), a4["Flash"])
        ck("舊譯少一版：印出沿用", "召喚師舊譯" in log, log[-200:])

        # 只有召喚師整段抓不到
        open(out, "wb").write(seeded)
        u, calls, _ = mast_router(lambda x: "/16.22.1/" in x)
        rc, log = run_mast(out, u)
        a5, _t = parse_mast(out)
        ck("召喚師抓不到：Flash 沿用", a5.get("Flash", {}).get("zh") == "閃現", a5.get("Flash"))
        ck("召喚師抓不到：天賦照新資料（不混入上一版的探針）", "ZZ Probe 9942" not in a5, list(a5)[:3])

        # 不連續的失敗不可以累積成「整班不上網」
        open(out, "wb").write(seeded)
        u, calls, _ = mast_router(lambda x: "/3.15.5/" in x or "/4.21.5/" in x)
        rc, log = run_mast(out, u)
        ck("不連續失敗：後面的版本照常上網", any("/7.21.1/" in c for c in calls), len(calls))
        ck("不連續失敗：沒有進入不上網", "不再上網" not in log, log[-200:])

        # 天賦部分沿用時，召喚師技能仍要拿新資料（上一版的召喚師不可以擋住這班的新譯名）
        stale = json.loads(json.dumps(a))
        stale["Flash"]["zh"] = "舊閃現9942"
        open(out, "w", encoding="utf-8").write("window.LOL_MASTERIES=" + json.dumps(stale, ensure_ascii=False, separators=(",", ":"))
                                                + ";window.LOL_MASTERY_TREES=" + json.dumps(t, ensure_ascii=False, separators=(",", ":")) + ";")
        rc, log = run_mast(out, mast_router(lambda x: "/7.16.1/" in x)[0])
        a7, _t = parse_mast(out)
        ck("天賦沿用時：召喚師仍是新譯名", a7["Flash"]["zh"] == "閃現", a7["Flash"])

        # 一個版本 200 卻空：跟抓不到同樣處理
        open(out, "wb").write(seeded)
        def empty(req, timeout=None, _u=mast_router()[0]):
            uu = req.full_url
            if "/7.16.1/" in uu and uu.endswith("mastery.json"):
                return Resp(json.dumps({"data": {}, "tree": {}}).encode())
            return _u(req, timeout)
        rc, log = run_mast(out, empty)
        a6, t6 = parse_mast(out)
        ck("200 但空的：2017 樹還在", t6.get("2017") == t["2017"], list(t6))
        ck("200 但空的：探針還在（當成失敗）", "ZZ Probe 9942" in a6)

        # 沒有上一版又全斷：不寫檔、exit 1
        os.remove(out)
        u, calls, _ = mast_router(lambda x: True)
        rc, log = run_mast(out, u)
        ck("沒有上一版又全斷：exit 1", rc == 1, rc)
        ck("沒有上一版又全斷：不寫檔", not os.path.exists(out))
        ck("沒有上一版又全斷：沒留 tmp", not os.path.exists(out + ".tmp"))

        # 上一版壞掉又全斷：原檔不被蓋掉
        open(out, "w", encoding="utf-8").write("window.LOL_MASTERIES={壞掉")
        rc, log = run_mast(out, mast_router(lambda x: True)[0])
        ck("上一版壞掉又全斷：exit 1", rc == 1, rc)
        ck("上一版壞掉又全斷：原檔沒被蓋", open(out, encoding="utf-8").read() == "window.LOL_MASTERIES={壞掉")

        # 復原：下一班抓到就回到新資料，探針消失（沿用不是永久）
        open(out, "wb").write(seeded)
        rc, log = run_mast(out, mast_router()[0])
        ck("下一班全部抓到：逐位元回到基準", open(out, "rb").read() == base)

        # 舊版對照：同一情境 2017 樹消失、exit 0
        old = os.path.join(d, "old_masteries.py")
        open(old, "wb").write(subprocess.run(["git", "show", f"{OLDREV}:scripts/fetch_masteries.py"], cwd=REPO, capture_output=True).stdout)
        open(out, "wb").write(seeded)
        rc, log = run_mast(out, mast_router(lambda x: "/7.16.1/" in x)[0], src=old)
        _a, oldt = parse_mast(out)
        ck("對照：舊版同情境 2017 樹消失", "2017" not in oldt, list(oldt))
        ck("對照：舊版 exit 0、沒有任何警告字樣", rc == 0 and "沿用" not in log)
        open(out, "wb").write(seeded)
        rc, log = run_mast(out, mast_router(lambda x: True)[0], src=old)
        olds = open(out, encoding="utf-8").read()
        ck("對照：舊版全斷把檔案寫成空表", olds.startswith("window.LOL_MASTERIES={};"), olds[:40])
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ───────────── jungle ─────────────
def run_jung(out_path, behavior, src=JUNG):
    m = load(src, "j_" + hashlib.md5(os.urandom(4)).hexdigest())
    m.OUT = out_path
    m.KEY = ""
    m.fetch_csv = lambda tab, gid: (behavior((tab, gid)), None)
    m.parse_season = lambda rows, links: rows
    buf = io.StringIO()
    rc = 0
    keep = sys.stdout
    try:
        with contextlib.redirect_stdout(buf):
            m.main()
    except SystemExit as e:
        rc = e.code or 0
    except Exception as e:     # 被測模組崩潰要變成紅燈，不是中斷測試（突變要跑到合計）
        rc, _ = "崩潰", buf.write(f"崩潰：{e!r}")
    finally:
        sys.stdout = keep
    return rc, buf.getvalue()


def parse_jung(p):
    if not os.path.exists(p):
        return {}
    try:
        return json.JSONDecoder().raw_decode(open(p, encoding="utf-8").read(), len("window.JUNGLE_CLEARS="))[0]
    except ValueError:
        return {}


def card(name):
    return {"name": name, "clears": [{"time": "3:00", "noteLinks": []}]}


def test_jungle():
    print("── jungle ──")
    d = tempfile.mkdtemp(prefix="jung_")
    out = os.path.join(d, "jungle.js")
    try:
        good = lambda key: [card(f"new{key[1]}")]
        rc, log = run_jung(out, good)
        base = parse_jung(out)
        ck("全部抓到：三季都有", sorted(base) == ["2024", "2025", "2026"], list(base))
        ck("全部抓到：沒印沿用", "沿用上一版" not in log, log[-200:])
        order = list(base)

        # 種上一版的探針
        prev = {y: [card("ZZ9942" + y)] for y in ("2026", "2025", "2024")}
        js = "window.JUNGLE_CLEARS=" + json.dumps(prev, ensure_ascii=False, separators=(",", ":")) + ";\nwindow.JUNGLE_META={};"
        open(out, "w", encoding="utf-8").write(js)

        def fail_2025(key):
            if key[1] == "0":
                raise OSError("模擬逾時")
            return [card(f"new{key[1]}")]
        rc, log = run_jung(out, fail_2025)
        r = parse_jung(out)
        ck("2025 抓不到：exit 0", rc == 0, (rc, log[-200:]))
        ck("2025 抓不到：2025 沿用上一版", r.get("2025") == prev["2025"], r.get("2025"))
        ck("2025 抓不到：其他兩季是新資料", r.get("2024", [{}])[0].get("name") == "new112351531" and r.get("2026", [{}])[0].get("name", "").startswith("new"), r)
        ck("2025 抓不到：印出沿用", "2025: 沿用上一版" in log, log[-300:])
        ck("2025 抓不到：賽季順序不變", list(r) == order, list(r))

        # 解析 0 筆也算
        open(out, "w", encoding="utf-8").write(js)
        rc, log = run_jung(out, lambda key: [] if key[1] == "0" else [card("n")])
        r = parse_jung(out)
        ck("解析 0 筆：沿用上一版", r.get("2025") == prev["2025"], r.get("2025"))

        # 全斷：檔案逐位元不動
        open(out, "w", encoding="utf-8").write(js)
        before = open(out, "rb").read()
        def all_fail(key): raise OSError("全斷")
        rc, log = run_jung(out, all_fail)
        ck("全斷：檔案逐位元不動", open(out, "rb").read() == before)
        ck("全斷：印保留舊檔", "保留舊" in log, log[-200:])

        # 上一版沒有那一季：退回舊行為（不捏造）
        open(out, "w", encoding="utf-8").write("window.JUNGLE_CLEARS=" + json.dumps({"2026": prev["2026"]}) + ";\nwindow.JUNGLE_META={};")
        rc, log = run_jung(out, fail_2025)
        r = parse_jung(out)
        ck("上一版沒有那一季：不捏造", "2025" not in r, list(r))

        # 上一版壞掉：不崩潰
        open(out, "w", encoding="utf-8").write("壞掉")
        rc, log = run_jung(out, fail_2025)
        r = parse_jung(out)
        ck("上一版壞掉：不崩潰、其餘照寫", sorted(r) == ["2024", "2026"], list(r))

        # 舊版對照
        old = os.path.join(d, "old_jungle.py")
        open(old, "wb").write(subprocess.run(["git", "show", f"{OLDREV}:scripts/fetch_jungle.py"], cwd=REPO, capture_output=True).stdout)
        open(out, "w", encoding="utf-8").write(js)
        rc, log = run_jung(out, fail_2025, src=old)
        r = parse_jung(out)
        ck("對照：舊版同情境 2025 消失", "2025" not in r, list(r))
    finally:
        shutil.rmtree(d, ignore_errors=True)


before = {p: (md5(p), os.path.getmtime(p)) for p in REAL}
test_masteries()
test_jungle()
print("── 隔離 ──")
for p in REAL:
    ck(f"正本沒動：{os.path.basename(p)}", before[p] == (md5(p), os.path.getmtime(p)))
print(f"\n合計 ✓ {res['ok']}　✗ {res['bad']}")
sys.exit(1 if res["bad"] else 0)
