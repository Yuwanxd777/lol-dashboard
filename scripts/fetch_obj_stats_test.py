# -*- coding: utf-8 -*-
"""fetch_obj_stats 抓不到時不可以讓物件從 obj_stats.js 消失（2026-11-05 精進迴圈 #2605）。

沙盒接管：CACHE／OUT／ROOT／HERE 路徑、urlopen（入口）、time.sleep。
只有沙盒才有的證據：假數值 hp=99421 之類真資料不可能有的值。
舊版對照釘 beeb56ab（紅 Buff 消失那一班的版本）。
環境變數 OBJ_SRC 可指定被測原始碼（autopilot/_m2605_mutate.py 用來跑突變）。
用法：python -u scripts/fetch_obj_stats_test.py
"""
import contextlib, hashlib, importlib.util, io, json, os, shutil, subprocess, sys, tempfile, time
import urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC = os.environ.get("OBJ_SRC") or os.path.join(HERE, "fetch_obj_stats.py")
OLDREV = "beeb56ab"
REAL_OUT = os.path.join(REPO, "obj_stats.js")
real_urlopen, real_sleep = urllib.request.urlopen, time.sleep
_real_stdout = sys.stdout
res = {"ok": 0, "bad": 0}


def ck(name, cond, extra=""):
    res["ok" if cond else "bad"] += 1
    print(("  ✓ " if cond else "  ✗ ") + name + ("" if cond else f"  → {extra}"))


def bin_of(unit_hp, turret=False):
    key = "Characters/Turret/CharacterRecords/Root" if turret else "Characters/X/CharacterRecords/Root"
    return json.dumps({key: {"baseHP": unit_hp, "baseMoveSpeed": 300}})


class D(dict):
    """缺鍵回空表：項目不見時走到斷言變紅，不會在半路 KeyError 中斷（突變測試要跑到結尾）。"""
    def __missing__(self, k): return D()


class Resp:
    def __init__(self, b): self.b = b
    def read(self): return self.b


class Sandbox:
    """behavior(unit_or_turret, 第幾次) 回傳字串內容或 raise。"""

    def __init__(self, src=SRC):
        self.d = tempfile.mkdtemp(prefix="objstats_")
        self.cache = os.path.join(self.d, "csv_cache")
        os.makedirs(self.cache)
        self.out = os.path.join(self.d, "obj_stats.js")
        self.src = src
        self.calls = []
        self.timeouts = []
        self.sleeps = []

    def seed_prev(self, obj):
        open(self.out, "w", encoding="utf-8").write("window.OBJ_STATS=" + json.dumps(obj, ensure_ascii=False) + ";")

    def seed_cache(self, name, text, age_h=48):
        p = os.path.join(self.cache, name)
        open(p, "w", encoding="utf-8").write(text)
        t = time.time() - age_h * 3600
        os.utime(p, (t, t))
        return p

    def prev(self):
        if not os.path.exists(self.out):
            return None
        t = open(self.out, encoding="utf-8").read()
        try:
            return D(json.loads(t[t.index("{"):t.rindex("}") + 1]))
        except ValueError:
            return D()

    def run(self, behavior):
        spec = importlib.util.spec_from_file_location("objstats_under_test", self.src)
        m = importlib.util.module_from_spec(spec)
        real_out = sys.stdout
        # 模組 import 時會包一層 sys.stdout.buffer，被回收時會把底層關掉；給它一個拋棄式的。
        sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        try:
            spec.loader.exec_module(m)
        finally:
            sys.stdout = real_out
        m.HERE, m.ROOT, m.CACHE, m.OUT = self.d, self.d, self.cache, self.out
        m.FORCE = False
        leaks = [k for k, v in vars(m).items()
                 if isinstance(v, str) and os.path.normcase(REPO) in os.path.normcase(v) and k not in ("__file__", "__cached__")]
        assert not leaks, f"模組層還有路徑指著真實 repo：{leaks}"

        counts = {}

        def fake(req, timeout=None):
            url = req.full_url if hasattr(req, "full_url") else req
            who = url.rsplit("/", 1)[1].replace(".bin.json", "")
            counts[who] = counts.get(who, 0) + 1
            self.calls.append(who)
            self.timeouts.append(timeout)
            return Resp(behavior(who, counts[who]).encode("utf-8"))

        urllib.request.urlopen = fake
        time.sleep = lambda s: self.sleeps.append(s)
        buf = io.StringIO()
        rc = 0
        try:
            with contextlib.redirect_stdout(buf):
                try:
                    m.main()
                except SystemExit as e:
                    rc = e.code or 0
                except Exception as e:
                    rc = f"崩潰：{e!r}"
        finally:
            urllib.request.urlopen, time.sleep = real_urlopen, real_sleep
        return rc, buf.getvalue()

    def close(self):
        shutil.rmtree(self.d, ignore_errors=True)


def ok_all(who, n):
    return bin_of(99421, turret=who == "turret")


def fail_red(who, n):
    if who == "sru_red":
        raise OSError("The handshake operation timed out")
    return ok_all(who, n)


def http404(who):
    return urllib.error.HTTPError("u", 404, "nf", None, None)


real_md5 = hashlib.md5(open(REAL_OUT, "rb").read()).hexdigest() if os.path.exists(REAL_OUT) else None

print("① 全部正常（正例）")
s = Sandbox(); rc, out = s.run(ok_all)
p = s.prev()
ck("離開碼 0", rc == 0, rc)
ck("19 項都寫出", len(p) == 19, len(p))
ck("數值來自假資料", p["紅 Buff"]["hp"] == 99421 and p["外塔（一塔）"]["hp"] == 99421, p.get("紅 Buff"))
ck("塔不留 ms", "ms" not in p["外塔（一塔）"], p["外塔（一塔）"])
ck("沒有警告", "⚠" not in out and "沿用" not in out, out)
ck("逾時不超過 30 秒", max(s.timeouts) <= 30, max(s.timeouts))
s.close()

print("② 11-05 那一班：紅 Buff 交握逾時、沒快取、上一版有（主案例）")
s = Sandbox(); s.seed_prev({"紅 Buff": {"hp": 88123}, "藍 Buff": {"hp": 1}})
rc, out = s.run(fail_red); p = s.prev()
ck("紅 Buff 沒消失，值是上一版", p.get("紅 Buff") == {"hp": 88123}, p.get("紅 Buff"))
ck("其他項照常更新", p["藍 Buff"]["hp"] == 99421, p["藍 Buff"])
ck("仍是 19 項", len(p) == 19, len(p))
ck("重試了第 2 次", s.calls.count("sru_red") == 2, s.calls.count("sru_red"))
ck("日誌有寫沿用", "紅 Buff" in out and "沿用上一版" in out, out)
ck("收尾行有數量", "其中 1 個沿用上一版" in out, out)
ck("離開碼 0（暫時性，下一班再試）", rc == 0, rc)
ck("失敗的不留快取（下一班才會再抓）", not os.path.exists(os.path.join(s.cache, "objbin_sru_red.json")))
s.close()

print("③ 第一次失敗、重試成功")
s = Sandbox()


def flaky(who, n):
    if who == "sru_red" and n == 1:
        raise OSError("timeout")
    return ok_all(who, n)


rc, out = s.run(flaky); p = s.prev()
ck("拿到新值", p["紅 Buff"]["hp"] == 99421, p["紅 Buff"])
ck("沒有沿用字樣", "沿用" not in out, out)
ck("重試前有等", 3 in s.sleeps, s.sleeps)
s.close()

print("④ 有過期快取時優先用快取")
s = Sandbox(); s.seed_prev({"紅 Buff": {"hp": 88123}})
c = s.seed_cache("objbin_sru_red.json", bin_of(77654))
mt = os.path.getmtime(c)
rc, out = s.run(fail_red); p = s.prev()
ck("值來自快取", p["紅 Buff"]["hp"] == 77654, p["紅 Buff"])
ck("有警告", "過期快取" in out, out)
ck("沒碰快取 mtime", os.path.getmtime(c) == mt)
s.close()

print("⑤ 新鮮快取不上網（正控制：快取路徑還在）")
s = Sandbox(); s.seed_cache("objbin_sru_red.json", bin_of(66555), age_h=1)
rc, out = s.run(ok_all); p = s.prev()
ck("用新鮮快取", p["紅 Buff"]["hp"] == 66555, p["紅 Buff"])
ck("沒對它發請求", "sru_red" not in s.calls, s.calls)
s.close()

print("⑥ 過期快取＋網路正常 ⇒ 換成新值（復原路徑）")
s = Sandbox(); s.seed_prev({"紅 Buff": {"hp": 88123}}); s.seed_cache("objbin_sru_red.json", bin_of(77654))
rc, out = s.run(ok_all); p = s.prev()
ck("新值蓋掉舊值", p["紅 Buff"]["hp"] == 99421, p["紅 Buff"])
s.close()

print("⑦ 404：不重試、沿用")
s = Sandbox(); s.seed_prev({"紅 Buff": {"hp": 88123}})


def nf(who, n):
    if who == "sru_red":
        raise http404(who)
    return ok_all(who, n)


rc, out = s.run(nf); p = s.prev()
ck("只問一次", s.calls.count("sru_red") == 1, s.calls.count("sru_red"))
ck("沿用上一版", p["紅 Buff"] == {"hp": 88123}, p["紅 Buff"])
ck("404 後面的項目還繼續抓", p["河蟹"]["hp"] == 99421, p["河蟹"])
s.close()

print("⑧ 連續多個 404 不算來源掛了")
s = Sandbox()


def many404(who, n):
    if who != "turret":
        raise http404(who)
    return ok_all(who, n)


rc, out = s.run(many404)
ck("15 個單位都有問到", len(set(s.calls)) == 16, len(set(s.calls)))
s.close()

print("⑨ 無 Root 紀錄／抓到空內容 ⇒ 沿用")
s = Sandbox(); s.seed_prev({"紅 Buff": {"hp": 88123}, "外塔（一塔）": {"hp": 5}})


def noroot(who, n):
    if who in ("sru_red", "turret"):
        return "{}"
    return ok_all(who, n)


rc, out = s.run(noroot); p = s.prev()
ck("野怪沿用", p["紅 Buff"] == {"hp": 88123}, p["紅 Buff"])
ck("塔沿用", p["外塔（一塔）"] == {"hp": 5}, p.get("外塔（一塔）"))
ck("上一版沒有的塔不亂補", "內塔（二塔）" not in p, p.get("內塔（二塔）"))
s.close()

print("⑩ 來源全掛：請求數有上限、上一版完整保留")
s = Sandbox()
old = {"紅 Buff": {"hp": 88123}, "藍 Buff": {"hp": 2}, "外塔（一塔）": {"hp": 5}}
s.seed_prev(old)


def down(who, n):
    raise OSError("down")


rc, out = s.run(down); p = s.prev()
ck("只發 4 次就停（連 2 個檔 × 試 2 次）", len(s.calls) == 4, len(s.calls))
ck("上一版全部保留", p == old, p)
ck("離開碼 0", rc == 0, rc)
s.close()

print("⑩b 不連續的失敗不算來源掛了（成功會歸零）")
s = Sandbox()


def spaced(who, n):
    if who in ("sru_baron", "sru_red", "sru_gromp"):
        raise OSError("timeout")
    return ok_all(who, n)


rc, out = s.run(spaced); p = s.prev()
ck("最後一個單位照樣抓到", p["超級士兵（Super Minion）"]["hp"] == 99421, p["超級士兵（Super Minion）"])
ck("3 個失敗各試滿 2 次", all(s.calls.count(u) == 2 for u in ("sru_baron", "sru_red", "sru_gromp")), s.calls)
s.close()

print("⑪ 來源全掛又沒有上一版：不寫檔、離開碼 1")
s = Sandbox()
rc, out = s.run(down)
ck("離開碼 1", rc == 1, rc)
ck("沒有產出空檔", not os.path.exists(s.out))
s.close()

print("⑫ 上一版壞掉不會讓整支崩潰")
s = Sandbox(); open(s.out, "w", encoding="utf-8").write("window.OBJ_STATS={壞掉")
rc, out = s.run(fail_red); p = s.prev()
ck("其餘照常寫出", len(p) == 18, len(p))
ck("抓不到又沒上一版會印 ？", "？紅 Buff" in out, out)
s.close()

if not os.environ.get("OBJ_SRC"):
    print("⑬ 正控制：釘 beeb56ab 的舊版，同一情境紅 Buff 真的消失")
    txt = subprocess.run(["git", "-C", REPO, "show", f"{OLDREV}:scripts/fetch_obj_stats.py"], capture_output=True)
    ck("拉得出舊版", txt.returncode == 0, txt.stderr)
    tmp = tempfile.mkdtemp(prefix="objold_")
    oldsrc = os.path.join(tmp, "old.py")
    open(oldsrc, "wb").write(txt.stdout)
    s = Sandbox(src=oldsrc); s.seed_prev({"紅 Buff": {"hp": 88123}})
    rc, out = s.run(fail_red); p = s.prev()
    ck("舊版紅 Buff 不見", "紅 Buff" not in p, p.get("紅 Buff"))
    ck("舊版離開碼照樣 0", rc == 0, rc)
    ck("舊版不重試", s.calls.count("sru_red") == 1, s.calls.count("sru_red"))
    ck("舊版逾時 120 秒", max(s.timeouts) == 120, max(s.timeouts))
    s.close()
    shutil.rmtree(tmp, ignore_errors=True)

print("⑭ 隔離：真實 obj_stats.js 一個位元沒動")
now = hashlib.md5(open(REAL_OUT, "rb").read()).hexdigest() if os.path.exists(REAL_OUT) else None
ck("md5 相同", now == real_md5, (real_md5, now))

print(f"\n合計 ✓{res['ok']} ✗{res['bad']}")
sys.exit(1 if res["bad"] else 0)
