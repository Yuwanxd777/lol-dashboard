# -*- coding: utf-8 -*-
"""fetch_assets 抓不到時不可以把殘缺結果寫進永久快取（2026-11-05 精進迴圈 #2607）。

沙盒接管：CACHE、OUT（兩個出口）、urlopen（入口）、time.sleep、Image（解圖）。
只有沙盒才有的證據：假道具 ZZ Probe 9942，真資料不可能有。
舊版對照釘 406af44e（本輪修改前的版本）。
環境變數 ASSETS_SRC 可指定被測原始碼（autopilot/_m2607_mutate.py 用來跑突變）。
用法：python -u scripts/fetch_assets_test.py
"""
import contextlib, hashlib, importlib.util, io, json, os, shutil, subprocess, sys, tempfile, time
import urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC = os.environ.get("ASSETS_SRC") or os.path.join(HERE, "fetch_assets.py")
OLDREV = "406af44e"
REAL = [os.path.join(REPO, "assets.js"), os.path.join(REPO, "csv_cache", "assets_cache.json")]
real_urlopen, real_sleep = urllib.request.urlopen, time.sleep
res = {"ok": 0, "bad": 0}
PROBE = "ZZ Probe 9942"
CUR = "16.22.1"
VERS = ["16.22.1", "7.24.2"]   # 2026 一版、2017 一版（沒有 zh_TW 符文）


def ck(name, cond, extra=""):
    res["ok" if cond else "bad"] += 1
    print(("  ✓ " if cond else "  ✗ ") + name + ("" if cond else f"  → {extra}"))


def stat(p):
    return (hashlib.md5(open(p, "rb").read()).hexdigest(), os.path.getmtime(p))


class Resp:
    def __init__(self, b): self.b = b
    def read(self): return self.b
    def __enter__(self): return self
    def __exit__(self, *a): return False


def gone(u, code=403):
    return urllib.error.HTTPError(u, code, "gone", {}, None)


def router(fail=lambda u: None, versions=None, img=None):
    """fail(u) 回例外就丟；img(u) 回圖片 bytes。"""
    calls = []
    vs = versions or VERS

    def urlopen(req, timeout=None):
        u = req.full_url if hasattr(req, "full_url") else req
        calls.append(u)
        e = fail(u)
        if e:
            raise e
        if u.endswith("versions.json"):
            return Resp(json.dumps(vs).encode())
        if "/data/" in u:
            v = u.split("/cdn/")[1].split("/")[0]
            major = int(v.split(".")[0])
            if u.endswith("runesReforged.json"):
                if major < 8:
                    raise gone(u)
                r = {"id": 8001, "name": "Rune", "icon": "r.png"}
                return Resp(json.dumps([{"id": 8000, "name": "Style", "icon": "s.png",
                                         "slots": [{"runes": [r]}]}]).encode())
            if u.endswith("item.json"):
                return Resp(json.dumps({"data": {"9942": {"name": PROBE, "image": {"full": "9942.png"}}}}).encode())
            if u.endswith("champion.json"):
                return Resp(json.dumps({"data": {"Ahri": {"name": "Ahri", "tags": ["Mage"], "info": {"attack": 3, "defense": 4, "magic": 8},
                                                          "image": {"full": "Ahri.png"}}}}).encode())
            raise OSError("沒種的網址 " + u)
        return Resp((img or (lambda u: b"IMG"))(u))
    return urlopen, calls


class FakeIm:
    def __init__(self, data): self.data = data
    def convert(self, m): return self
    def resize(self, s): return self
    def getdata(self):
        v = self.data[0] if self.data else 0
        return [v] * 4
    def tobytes(self):
        return bytes(self.getdata())


class FakeImage:
    @staticmethod
    def open(b):
        return FakeIm(b.read())


def load(src=SRC):
    spec = importlib.util.spec_from_file_location("fa_sb", src)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run(sb, src=SRC, r=None, cache=None, prev=None, argv=None, year=2026):
    """回 (rc, 輸出, 快取, assets, 請求清單)。"""
    urlopen, calls = r or router()
    cpath, opath = os.path.join(sb, "c.json"), os.path.join(sb, "a.js")
    for p in (cpath, opath, cpath + ".tmp", opath + ".tmp"):
        if os.path.exists(p):
            os.remove(p)
    if cache is not None:
        open(cpath, "w", encoding="utf-8").write(cache if isinstance(cache, str) else json.dumps(cache))
    if prev is not None:
        open(opath, "w", encoding="utf-8").write(prev)
    keep_argv = sys.argv
    sys.argv = ["fetch_assets.py"] + (argv or [])
    urllib.request.urlopen = urlopen
    time.sleep = lambda s: None
    buf, rc = io.StringIO(), 0
    try:
        m = load(src)
        m.CACHE, m.OUT = cpath, opath
        m.Image, m._HAS_PIL = FakeImage, True
        import io as _i
        m._io = _i
        with contextlib.redirect_stdout(buf):
            try:
                m.main()
            except SystemExit as e:
                rc = e.code or 0
            except Exception as e:
                rc = "崩潰:" + repr(e)
    finally:
        urllib.request.urlopen, time.sleep = real_urlopen, real_sleep
        sys.argv = keep_argv
    c = None
    if os.path.exists(cpath):
        try:
            c = json.load(open(cpath, encoding="utf-8"))
        except ValueError:
            c = None      # 壞快取情境：全斷時它還是壞的
    a = None
    if os.path.exists(opath):
        raw = open(opath, encoding="utf-8").read()
        if not raw.startswith("window.LOL_ASSETS="):
            ck("輸出有 window.LOL_ASSETS 外殼", False, raw[:40])
            print(f"合計 ✓ {res['ok']}／✗ {res['bad']}")
            sys.exit(1)
        a = json.loads(raw[len("window.LOL_ASSETS="):].rstrip().rstrip(";"))
    return rc, buf.getvalue(), c, a, calls


def ent(v, item=True, rune=True, champ=True):
    return {"v": v,
            "item": {"9942": {"zh": PROBE, "en": PROBE, "img": "9942.png"}} if item else {},
            "rune": {"8001": {"zh": "R", "en": "R", "img": "r.png"}} if rune else {},
            "champ": {"Ahri": {"zh": "Ahri", "en": "Ahri", "img": "Ahri.png"}} if champ else {}}


PREV = 'window.LOL_ASSETS={"ctag":{"Ahri":{"t":["Mage"],"i":[3,4,8]},"ZZ9942":{"t":[],"i":[0,0,0]}},"item":{},"rune":{},"champ":{}};\n'
SIG_A = "11" * 4
SIG_B = "99" * 4


def main():
    before = {p: stat(p) for p in REAL}
    sb = tempfile.mkdtemp(prefix="fa_test_")
    old_src = os.path.join(sb, "old_fetch_assets.py")
    open(old_src, "wb").write(subprocess.check_output(["git", "-C", REPO, "show", f"{OLDREV}:scripts/fetch_assets.py"]))
    try:
        print("① 快樂路徑")
        rc, o, c, a, calls = run(sb)
        ck("rc 0", rc == 0, rc)
        ck("兩版都進快取", set(c["kinds"]) == {"2026|16.22.1", "2017|7.24.2"}, list(c["kinds"]))
        ck("2017 符文 403 是本來就沒有：有存、符文 0", c["kinds"]["2017|7.24.2"]["rune"] == {})
        ck("2017 不被當失敗", "失敗" not in o, o)
        ck("2026 符文有存", "8001" in c["kinds"]["2026|16.22.1"]["rune"])
        ck("沙盒證據進輸出", a["item"]["9942"]["zh"] == PROBE)
        ck("分類標籤有", a["ctag"]["Ahri"]["t"] == ["Mage"])
        ck("輸出是可解析的完整外殼", a is not None)
        ck("沒留 tmp", not os.path.exists(os.path.join(sb, "a.js.tmp")) and not os.path.exists(os.path.join(sb, "c.json.tmp")))
        n = len(calls)
        rc, o, c2, a2, calls2 = run(sb, cache=c)
        ck("熱跑不再抓版本資料（只剩 versions 與分類標籤）",
           sum("/data/" in u for u in calls2) == 1, calls2)
        ck("冷跑請求比熱跑多（正控制）", n > len(calls2))

        print("② 當年版本符文暫時抓不到（連線斷）")
        f = lambda u: OSError("斷線") if "16.22.1" in u and "runesReforged" in u else None
        cache = {"cur": "16.21.1", "kinds": {"2026|16.21.1": ent("16.21.1")}, "sig": {}}
        rc, o, c, a, calls = run(sb, r=router(f), cache=cache)
        ck("rc 0", rc == 0, rc)
        ck("殘缺的版本不進快取", "2026|16.22.1" not in c["kinds"], list(c["kinds"]))
        ck("舊版本還在", "2026|16.21.1" in c["kinds"])
        ck("日誌講這版下一班重抓", "這版不進快取" in o and "rune" in o, o)
        ck("輸出仍有上一版的符文", "8001" in a["rune"], a["rune"])
        ck("連線失敗有重試（zh 符文請求 2 次）",
           sum(u.endswith("16.22.1/data/zh_TW/runesReforged.json") for u in calls) == 2, calls)
        rc, o, c3, a3, _ = run(sb, cache=c)
        ck("下一班網路好了就補回", "2026|16.22.1" in c3["kinds"] and "8001" in c3["kinds"]["2026|16.22.1"]["rune"], list(c3["kinds"]))

        print("③ 8.x 以後的 403 不可以當本來就沒有（DDragon 尚未上線的版本連 item 都 403）")
        f = lambda u: gone(u) if "16.22.1" in u and "runesReforged" in u else None
        rc, o, c, a, calls = run(sb, r=router(f), cache=cache)
        ck("當年符文 403 不進快取", "2026|16.22.1" not in c["kinds"], list(c["kinds"]))
        ck("403 不重試（zh 符文請求 1 次）",
           sum(u.endswith("16.22.1/data/zh_TW/runesReforged.json") for u in calls) == 1, calls)

        print("④ 7.x 的非 403 失敗不可以當本來就沒有")
        f = lambda u: OSError("斷線") if "7.24.2" in u and "runesReforged" in u else None
        rc, o, c, a, _ = run(sb, r=router(f))
        ck("不進快取", "2017|7.24.2" not in c["kinds"], list(c["kinds"]))

        print("⑤ item／champ 失敗、200 但空的")
        for kind, name in (("item.json", "item"), ("champion.json", "champ")):
            f = lambda u, k=kind: OSError("斷線") if "16.22.1" in u and u.endswith(k) and "/cdn/16" in u else None
            cc = {"cur": CUR, "kinds": {"2026|16.21.1": ent("16.21.1")}, "sig": {}}
            rc, o, c, a, _ = run(sb, r=router(f), cache=cc)
            ck(f"{name} 失敗不進快取", "2026|16.22.1" not in c["kinds"], list(c["kinds"]))
        base_open, _ = router()

        def empty_item(req, timeout=None):
            u = req.full_url
            if "16.22.1" in u and u.endswith("zh_TW/item.json"):
                return Resp(b'{"data":{}}')
            return base_open(req, timeout)
        rc, o, c, a, _ = run(sb, r=(empty_item, []), cache=cc)
        ck("item 200 但 0 筆不進快取", "2026|16.22.1" not in c["kinds"], list(c["kinds"]))

        def empty_champ(req, timeout=None):
            u = req.full_url
            if "16.22.1" in u and u.endswith("zh_TW/champion.json"):
                return Resp(b'{"data":{}}')
            return base_open(req, timeout)
        rc, o, c, a, _ = run(sb, r=(empty_champ, []), cache=cc)
        ck("champ 200 但 0 筆不進快取", "2026|16.22.1" not in c["kinds"], list(c["kinds"]))

        print("⑥ 全斷：不洗掉線上那份")
        def all_fail(u):
            return None if u.endswith("versions.json") else OSError("全斷")
        many = ["16.22.1", "16.21.1", "16.20.1", "16.19.1"] + ["15.24.1", "15.17.1", "15.9.1", "15.1.1"]
        rc, o, c, a, calls = run(sb, r=router(all_fail, versions=many), prev=PREV)
        ck("exit 1", rc == 1, rc)
        ck("assets.js 原封不動（沙盒 ZZ9942 還在）", a is not None and "ZZ9942" in a["ctag"], a)
        ck("日誌說不寫", "不寫 assets.js" in o, o)
        vers_hit = {u.split("/cdn/")[1].split("/")[0] for u in calls if "/data/" in u}
        ck("連 2 版抓不到就不再上網", vers_hit.issubset({"15.1.1", "15.9.1", CUR}) and len(vers_hit) <= 3, vers_hit)
        ck("日誌說其餘不上網", "這班不再上網" in o, o)

        print("⑦ 分類標籤抓不到沿用上一版")
        hit = []

        def f_ctag(u):
            if u.endswith(f"{CUR}/data/en_US/champion.json"):
                hit.append(u)
                if len(hit) > 0:
                    return OSError("斷線")
            return None
        cc = {"cur": CUR, "kinds": {"2026|16.22.1": ent(CUR), "2017|7.24.2": ent("7.24.2", rune=False)}, "sig": {}}
        rc, o, c, a, _ = run(sb, r=router(f_ctag), cache=cc, prev=PREV)
        ck("沿用上一版（沙盒 ZZ9942 還在）", "ZZ9942" in a["ctag"], a["ctag"])
        ck("rc 0", rc == 0, rc)
        ck("日誌有 沿用上一版", "沿用上一版" in o, o)
        rc, o, c, a, _ = run(sb, r=router(f_ctag), cache=cc)
        ck("沒有上一版時是空表、不崩", a["ctag"] == {} and rc == 0, (rc, a["ctag"]))
        rc, o, c, a, _ = run(sb, r=router(f_ctag), cache=cc, prev="garbage")
        ck("上一版壞掉時是空表、不崩", a["ctag"] == {} and rc == 0, (rc, a["ctag"]))

        print("⑧ 圖片簽章抓不到不記 None")
        img_url = f"https://ddragon.leagueoflegends.com/cdn/{CUR}/img/item/9942.png"
        f = lambda u: OSError("斷線") if u == img_url else None
        rc, o, c, a, _ = run(sb, r=router(f), cache=cc)
        ck("抓不到的沒進 sig", img_url not in c["sig"], c["sig"].get(img_url))
        ck("日誌說下一班重試", "下一班重試" in o, o)
        rc, o, c2, a2, calls = run(sb, cache=c)
        ck("下一班重試成功", (c2["sig"].get(img_url) or "") != "", c2["sig"].get(img_url))
        cn = json.loads(json.dumps(c2))
        cn["sig"][img_url] = None
        rc, o, c3, _, calls = run(sb, cache=cn)
        ck("舊快取記的 None 會重試並解毒", c3["sig"].get(img_url) and img_url in calls, c3["sig"].get(img_url))
        rc, o, c4, _, calls = run(sb, cache=c3)
        ck("有簽章的不重抓（正控制）", img_url not in calls)
        f403 = lambda u: gone(u) if u == img_url else None
        rc, o, c5, _, calls = run(sb, r=router(f403), cache=cc)
        ck("403 的圖也不記、不算連線失敗", img_url not in c5["sig"] and "中途停手" not in o, o)
        ck("403 的圖不印警告（每班都有，印了會稀釋）", "⚠" not in o and "沒有簽章" in o, o)

        print("⑨ 圖片連續連線失敗就停手")
        def f_imgs(u):
            return OSError("斷線") if "/img/" in u else None
        ks = {f"2026|16.{i}.1": ent(f"16.{i}.1") for i in range(1, 2)}
        big = dict(ent(CUR))
        big["item"] = {str(i): {"zh": "x", "en": "x", "img": f"{i}.png"} for i in range(200)}
        cc2 = {"cur": CUR, "kinds": {"2026|16.22.1": big, "2017|7.24.2": ent("7.24.2", rune=False)}, "sig": {}}
        rc, o, c, a, calls = run(sb, r=router(f_imgs), cache=cc2)
        n_img = sum("/img/" in u for u in calls)
        ck("沒有全部打一遍（200 多張最多打幾十次）", n_img < 60, n_img)
        ck("日誌說中途停手", "中途停手" in o, o)
        ck("輸出照寫", a is not None and "0" in a["item"])

        f403s = lambda x: gone(x) if "/img/" in x else None
        rc, o, c, a, calls = run(sb, r=router(f403s), cache=cc2)
        ck("整批 403 不觸發停手，每張都問過", sum("/img/" in x for x in calls) > 200 and "中途停手" not in o, sum("/img/" in x for x in calls))

        print("⑩ 簽章不明不算換圖")
        m = load()
        ck("同檔名、一邊不明 ⇒ 併", m.same_seg(None, "a.png", SIG_A, "a.png") and m.same_seg(SIG_A, "a.png", None, "a.png"))
        ck("不同檔名、一邊不明 ⇒ 不併", not m.same_seg(None, "a.png", SIG_A, "b.png"))
        ck("兩邊都有、圖相同 ⇒ 併", m.same_seg(SIG_A, "a.png", SIG_A, "b.png"))
        ck("兩邊都有、圖不同 ⇒ 不併（真換圖，檔名相同也要切）", not m.same_seg(SIG_A, "a.png", SIG_B, "a.png"))
        u = lambda v: f"https://ddragon.leagueoflegends.com/cdn/{v}/img/item/9942.png"
        c6 = {"cur": CUR, "kinds": {"2024|14.1.1": ent("14.1.1"), "2025|15.1.1": ent("15.1.1"), "2026|16.22.1": ent(CUR),
                                    "2017|7.24.2": ent("7.24.2", rune=False)},
              "sig": {u("7.24.2"): SIG_A, u("14.1.1"): SIG_A, u(CUR): SIG_A}}
        f = lambda x: gone(x) if x == u("15.1.1") else None
        rc, o, c, a, _ = run(sb, r=router(f), cache=c6)
        ck("中間一年不明不切段（3637.png 那種）", len(a["item"]["9942"]["g"]) == 1, a["item"]["9942"]["g"])
        c7 = json.loads(json.dumps(c6))
        c7["sig"][u("15.1.1")] = SIG_B
        c7["sig"][u(CUR)] = SIG_B
        rc, o, c, a, _ = run(sb, cache=c7)
        ck("真換圖仍切段（正控制）", len(a["item"]["9942"]["g"]) == 2, a["item"]["9942"]["g"])

        c8 = {"cur": CUR, "kinds": c6["kinds"], "sig": {u("14.1.1"): SIG_A, u(CUR): SIG_B}}
        f = lambda x: gone(x) if x in (u("7.24.2"), u("15.1.1")) else None
        rc, o, c, a, _ = run(sb, r=router(f), cache=c8)
        ck("第一年不明、後面真換圖仍切段（不明段要接手簽章）", len(a["item"]["9942"]["g"]) == 2, a["item"]["9942"]["g"])

        print("⑪ 寫檔不留半截")
        rc, o, c, a, _ = run(sb, cache="{壞掉的 json", prev=PREV)
        ck("快取壞掉＋網路好：重抓成功", rc == 0 and "2026|16.22.1" in c["kinds"], rc)
        rc, o, c, a, _ = run(sb, r=router(all_fail), cache="{壞掉的 json", prev=PREV)
        ck("快取壞掉＋全斷：不洗掉 assets.js", rc == 1 and a is not None and "ZZ9942" in a["ctag"], (rc, a))

        print("⑫ 舊版對照（釘 %s，同樣情境舊版真的會壞）" % OLDREV)
        f = lambda x: OSError("斷線") if "16.22.1" in x and "runesReforged" in x else None
        rc, o, c, a, _ = run(sb, src=old_src, r=router(f), cache=cache)
        ck("舊版把殘缺版本存進快取", "2026|16.22.1" in c["kinds"] and c["kinds"]["2026|16.22.1"]["rune"] == {}, list(c["kinds"]))
        rc, o, c, a, calls = run(sb, src=old_src, cache=c)
        ck("舊版下一班不會重抓，毒留著", c["kinds"]["2026|16.22.1"]["rune"] == {} and not any("16.22.1/data/zh_TW/runesReforged" in x for x in calls))
        rc, o, c, a, _ = run(sb, src=old_src, r=router(all_fail), prev=PREV)
        ck("舊版全斷時把 assets.js 寫成空的且 exit 0", rc == 0 and a["item"] == {} and a["ctag"] == {}, (rc, a))
        f = lambda x: OSError("斷線") if x == img_url else None
        rc, o, c, a, _ = run(sb, src=old_src, r=router(f), cache=cc)
        ck("舊版把圖片失敗記成 None", img_url in c["sig"] and c["sig"][img_url] is None, c["sig"].get(img_url))

        print("⑬ 模組層與隔離")
        src_txt = open(SRC, encoding="utf-8").read()
        mm = load()
        src_root = os.path.dirname(os.path.dirname(os.path.abspath(SRC))).lower()
        ck("模組層路徑只有 ROOT／CACHE／OUT 三個（都已接管或衍生）",
           [k for k, v in vars(mm).items() if isinstance(v, str) and src_root in v.lower() and not k.startswith("__")] == ["ROOT", "CACHE", "OUT"])
        ck("沒有裸的 open(OUT, \"w\")", 'open(OUT, "w"' not in src_txt)
        for p in REAL:
            ck("真實檔沒動：" + os.path.basename(p), stat(p) == before[p])
    finally:
        shutil.rmtree(sb, ignore_errors=True)
    print(f"合計 ✓ {res['ok']}／✗ {res['bad']}")
    sys.exit(1 if res["bad"] else 0)


if __name__ == "__main__":
    main()
