# -*- coding: utf-8 -*-
"""fetch_rune_icons／fetch_champ_icons 抓不到時的行為（2026-11-05 精進迴圈 #2609）。

沙盒接管：輸出路徑（OUT／ROOT／OUT_DIR／RUNE_DIR／MANIFEST）、urlopen（入口）、time.sleep。
綁定後 assert 模組層路徑都在沙盒裡，跑完 assert 正本 rune_icons.js／champ_icons.js 與 img/champ、img/rune 沒動。
只有沙盒才有的證據：ZZ Probe 9942 這個名字、版本 99.42.1，真資料不可能有。
舊版對照釘 e15dbdf1（本輪修改前的版本）。環境變數 RUNE_SRC／CHAMP_SRC 可指定被測原始碼（autopilot/_m2609_mutate.py 用）。
用法：python -u scripts/fetch_rune_icons_test.py
"""
import contextlib, hashlib, importlib.util, io, json, os, shutil, subprocess, sys, tempfile, time
import urllib.request
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RUNE_SRC = os.environ.get("RUNE_SRC") or os.path.join(HERE, "fetch_rune_icons.py")
CHAMP_SRC = os.environ.get("CHAMP_SRC") or os.path.join(HERE, "fetch_champ_icons.py")
OLDREV = "e15dbdf1"
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


class Resp:
    def __init__(self, b): self.b = b
    def read(self): return self.b


def load(src, tag):
    # 模組 import 時可能包 sys.stdout.buffer，給它拋棄式的 stdout，被回收時才不會關到真的
    spec = importlib.util.spec_from_file_location(tag, src)
    m = importlib.util.module_from_spec(spec)
    keep = sys.stdout
    sys.stdout = type("S", (), {"buffer": io.BytesIO(), "write": lambda s, x: 0, "flush": lambda s: None})()
    try:
        spec.loader.exec_module(m)
    finally:
        sys.stdout = keep
    return m


def drive(m, urlopen):
    urllib.request.urlopen, time.sleep = urlopen, (lambda s: None)
    buf, rc = io.StringIO(), 0
    keep = sys.stdout
    sys.stdout = buf
    try:
        try:
            m.main()
        except SystemExit as e:
            rc = e.code or 0
        except Exception as e:      # 被測模組自己炸掉：回報成 rc，斷言照常判
            rc = f"例外 {type(e).__name__}"
    finally:
        sys.stdout = keep
        urllib.request.urlopen, time.sleep = real_urlopen, real_sleep
    return rc, buf.getvalue()


# ───────────── fetch_rune_icons ─────────────
CD = "https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default"
R_PREFIX = "window.RUNE_ICONS="
ZH = ["8.1.1", "8.11.1", "8.24.1", "9.24.2", "10.25.1", "11.24.1", "12.23.1", "13.24.1", "14.24.1", "15.24.1"]
CUR = "99.42.1"
PERKS = [{"id": i, "name": f"Rune{i}", "iconPath": f"/lol-game-data/assets/v1/perks/P{i}.png"} for i in (1, 2, 3)]
STYLES = {"styles": [{"id": 8000, "name": "Precision", "iconPath": "/lol-game-data/assets/v1/styles/S.png"}]}


def img_of(i): return f"{CD}/v1/perks/p{i}.png"


def rr(v):
    """8.1.1 才有舊名 舊名一 與 id 3；其餘版本是現名。"""
    first = v == "8.1.1"
    runes = [{"id": 1, "name": "舊名一" if first else "現名一"}, {"id": 2, "name": "名二"}]
    if first:
        runes.append({"id": 3, "name": "只有舊版才有"})
    return [{"id": 8000, "name": "精密", "slots": [{"runes": runes}]}]


def r_prev():
    by_id = {"1": {"zh": "舊名一", "en": "Rune1", "img": img_of(1)}, "2": {"zh": "名二", "en": "Rune2", "img": img_of(2)},
             "3": {"zh": "只有舊版才有", "en": "Rune3", "img": img_of(3)}, "8000": {"zh": "精密", "en": "Precision", "img": f"{CD}/v1/styles/s.png"}}
    by_name = {"舊名一": img_of(1), "現名一": img_of(1), "名二": img_of(2), "只有舊版才有": img_of(3), "精密": f"{CD}/v1/styles/s.png",
               "ZZ Probe 9942": img_of(1), "Rune1": img_of(1), "Rune2": img_of(2), "Rune3": img_of(3), "Precision": f"{CD}/v1/styles/s.png"}
    return {"byId": by_id, "byName": by_name}


def run_rune(src, fail=lambda u: False, reply=None, prev="good"):
    """reply(url) 回傳 None 就走預設內容。回傳 (rc, 輸出, dict 或 None, calls, timeouts, 留下的檔, 原始內容)。"""
    d = tempfile.mkdtemp(prefix="runeicons_")
    out = os.path.join(d, "rune_icons.js")
    if prev == "good":
        open(out, "w", encoding="utf-8").write(R_PREFIX + json.dumps(r_prev(), ensure_ascii=False) + ";")
    elif prev == "broken":
        open(out, "w", encoding="utf-8").write(R_PREFIX + "{壞掉")
    elif prev == "shape":
        open(out, "w", encoding="utf-8").write(R_PREFIX + "[1,2];")
    elif prev == "shape2":
        open(out, "w", encoding="utf-8").write(R_PREFIX + '{"x":1};')
    m = load(src, "r_" + os.path.basename(d))
    m.OUT = out
    for k, v in vars(m).items():
        if isinstance(v, str) and v.startswith(REPO) and k not in ("ROOT", "__file__", "__cached__"):
            raise SystemExit(f"沙盒漏接 {k}={v}")
    before = open(out, encoding="utf-8").read() if os.path.exists(out) else None
    calls, timeouts = [], []

    def urlopen(req, timeout=None):
        u = req.full_url if hasattr(req, "full_url") else req
        calls.append(u); timeouts.append(timeout)
        if fail(u):
            raise OSError("模擬連線被斷 " + u)
        r = reply(u) if reply else None
        if r is None:
            if u.endswith("perks.json"): r = PERKS
            elif u.endswith("perkstyles.json"): r = STYLES
            elif u.endswith("versions.json"): r = [CUR, "99.41.1"]
            else: r = rr(u.split("/cdn/")[1].split("/")[0])
        return Resp(json.dumps(r, ensure_ascii=False).encode("utf-8"))

    rc, o = drive(m, urlopen)
    data, raw = None, None
    if os.path.exists(out):
        raw = open(out, encoding="utf-8").read()
        try:
            data, _ = json.JSONDecoder().raw_decode(raw, len(R_PREFIX))
        except Exception:
            data = "壞檔"
    left = sorted(os.listdir(d))
    shutil.rmtree(d, ignore_errors=True)
    return dict(rc=rc, o=o, d=data, calls=calls, to=timeouts, left=left, raw=raw, before=before)


def snap_dir(p):
    return sorted((f, os.path.getmtime(os.path.join(p, f))) for f in os.listdir(p))


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


REALS = [os.path.join(REPO, x) for x in ("rune_icons.js", "champ_icons.js")]
real_md5 = {p: (md5(p), os.path.getmtime(p)) for p in REALS}
real_dirs = {p: snap_dir(p) for p in (os.path.join(REPO, "img", "champ"), os.path.join(REPO, "img", "rune"))}

print("══ fetch_rune_icons ══")
print("── 全部抓得到 ──")
r = run_rune(RUNE_SRC)
ck("rc 0", lambda: r["rc"] == 0, lambda: r["rc"])
ck("歷代名字都在", lambda: {"舊名一", "現名一", "名二", "只有舊版才有", "精密"} <= set(r["d"]["byName"]), lambda: r["d"])
ck("zh 主名取最早的", lambda: r["d"]["byId"]["1"]["zh"] == "舊名一", lambda: r["d"]["byId"]["1"])
ck("圖網址小寫", lambda: r["d"]["byId"]["1"]["img"] == img_of(1), lambda: r["d"]["byId"]["1"])
ck("英文名進 byName", lambda: r["d"]["byName"]["Rune2"] == img_of(2), lambda: r["d"]["byName"])
ck("上一版獨有的名字不留（成功路徑不是一直累積）", lambda: "ZZ Probe 9942" not in r["d"]["byName"], lambda: r["d"]["byName"])
ck("沒有警告", lambda: "⚠" not in r["o"] and "✗ " not in r["o"].replace("✗ 查無", ""), lambda: r["o"])
ck("單次逾時 30 秒", lambda: set(r["to"]) == {30}, lambda: r["to"])
ck("請求數＝2＋1＋10＋現行版", lambda: len(r["calls"]) == 14, lambda: r["calls"])
ck("現行版有問", lambda: any(f"/{CUR}/" in u for u in r["calls"]), lambda: r["calls"])
ck("沒留 tmp", lambda: r["left"] == ["rune_icons.js"], lambda: r["left"])
ck("檔案格式不變", lambda: r["raw"].startswith(R_PREFIX) and r["raw"].endswith(";"), lambda: r["raw"][:40])

print("── 一版抓不到 ──")
r = run_rune(RUNE_SRC, fail=lambda u: "/8.1.1/" in u)
ck("rc 0（有上一版可補）", lambda: r["rc"] == 0, lambda: r["rc"])
ck("只有那版才有的舊名補回", lambda: r["d"]["byName"]["舊名一"] == img_of(1), lambda: r["d"]["byName"])
ck("只有那版才有的 id 補回中文名", lambda: r["d"]["byId"]["3"]["zh"] == "只有舊版才有", lambda: r["d"]["byId"]["3"])
ck("有抓到的中文名不被上一版蓋掉", lambda: r["d"]["byId"]["1"]["zh"] == "現名一", lambda: r["d"]["byId"]["1"])
ck("日誌指名版本", lambda: "這班有版本抓不到：8.1.1" in r["o"], lambda: r["o"])
ck("日誌有補回筆數", lambda: "補回名字" in r["o"] and "中文名 1 筆" in r["o"], lambda: r["o"])
ck("失敗的版本試 2 次", lambda: sum("/8.1.1/" in u for u in r["calls"]) == 2, lambda: r["calls"])
ck("一版失敗不擋後面的版本", lambda: any("/15.24.1/" in u for u in r["calls"]), lambda: r["calls"])

print("── 200 但內容不對 ──")
for label, bad in (("空陣列", []), ("不是陣列", {"x": 1}), ("元素不是物件", [1, 2]), ("一個都對不上", [{"id": 77777, "name": "x", "slots": []}])):
    r = run_rune(RUNE_SRC, reply=lambda u, b=bad: b if "/8.1.1/" in u else None)
    ck(f"{label} ⇒ 當作抓不到、舊名補回", lambda: r["rc"] == 0 and "舊名一" in r["d"]["byName"] and "這班有版本抓不到：8.1.1" in r["o"], lambda: (r["rc"], r["o"]))

print("── versions.json 抓不到 ──")
r = run_rune(RUNE_SRC, fail=lambda u: u.endswith("versions.json"))
ck("rc 0", lambda: r["rc"] == 0, lambda: r["rc"])
ck("算一筆失敗、上一版補回", lambda: "這班有版本抓不到：versions.json" in r["o"] and "ZZ Probe 9942" in r["d"]["byName"], lambda: r["o"])
ck("歷年版本照問", lambda: any("/8.1.1/" in u for u in r["calls"]), lambda: r["calls"])

print("── DDragon 全斷 ──")
r = run_rune(RUNE_SRC, fail=lambda u: "ddragon" in u)
ck("rc 0（上一版全補回）", lambda: r["rc"] == 0, lambda: r["rc"])
ck("byName 一筆不少", lambda: set(r_prev()["byName"]) <= set(r["d"]["byName"]), lambda: r["d"]["byName"])
ck("中文名一筆不少", lambda: all(r["d"]["byId"][k]["zh"] == v["zh"] for k, v in r_prev()["byId"].items()), lambda: r["d"]["byId"])
ck("連 2 個網址失敗就不再上網（CDragon 2＋2×2）", lambda: len(r["calls"]) == 6, lambda: r["calls"])

print("── 中間成功會把連續失敗歸零 ──")
r = run_rune(RUNE_SRC, fail=lambda u: "/8.1.1/" in u or "/8.24.1/" in u)
ck("隔一版的失敗不觸發停手，全部版本都問到", lambda: all(any(f"/{v}/" in u for u in r["calls"]) for v in ZH + [CUR]), lambda: r["calls"])

print("── CDragon 抓不到 ──")
for label, kw in (("perks.json 斷線", dict(fail=lambda u: u.endswith("perks.json"))),
                  ("perkstyles.json 斷線", dict(fail=lambda u: u.endswith("perkstyles.json"))),
                  ("perks.json 空陣列", dict(reply=lambda u: [] if u.endswith("perks.json") else None)),
                  ("perks.json 不是陣列", dict(reply=lambda u: {"a": 1} if u.endswith("perks.json") else None)),
                  ("perkstyles.json 空的", dict(reply=lambda u: {"styles": []} if u.endswith("perkstyles.json") else None))):
    r = run_rune(RUNE_SRC, **kw)
    ck(f"{label}：rc 1、檔案不動、沒有崩潰", lambda: r["rc"] == 1 and r["raw"] == r["before"] and "不寫檔" in r["o"], lambda: (r["rc"], r["o"]))
r = run_rune(RUNE_SRC, fail=lambda u: u.endswith("perks.json"))
ck("CDragon 失敗試 2 次", lambda: sum(u.endswith("perks.json") for u in r["calls"]) == 2, lambda: r["calls"])
ck("CDragon 失敗就不去問 DDragon", lambda: not any("ddragon" in u for u in r["calls"]), lambda: r["calls"])
r = run_rune(RUNE_SRC, reply=lambda u: STYLES["styles"] if u.endswith("perkstyles.json") else None)
ck("perkstyles.json 是陣列也吃（舊寫法這裡會崩）", lambda: r["rc"] == 0 and "8000" in r["d"]["byId"], lambda: (r["rc"], r["o"]))

print("── CDragon 少了 id ──")
r = run_rune(RUNE_SRC, reply=lambda u: PERKS[:2] if u.endswith("perks.json") else None)
ck("rc 0", lambda: r["rc"] == 0, lambda: r["rc"])
ck("少掉的 id 沿用", lambda: r["d"]["byId"]["3"]["img"] == img_of(3), lambda: r["d"]["byId"])
ck("它的中文名由 DDragon 補上", lambda: r["d"]["byId"]["3"]["zh"] == "只有舊版才有" and "只有舊版才有" in r["d"]["byName"], lambda: r["d"]["byId"])
ck("日誌指名", lambda: "CDragon 少了 1 個 id" in r["o"] and "：3" in r["o"], lambda: r["o"])

print("── 沒有上一版 ──")
r = run_rune(RUNE_SRC, prev=None)
ck("全部抓得到 ⇒ rc 0", lambda: r["rc"] == 0 and "舊名一" in r["d"]["byName"], lambda: (r["rc"], r["o"]))
r = run_rune(RUNE_SRC, fail=lambda u: "/8.1.1/" in u, prev=None)
ck("缺一版 ⇒ rc 1", lambda: r["rc"] == 1, lambda: r["rc"])
ck("其他照寫", lambda: "現名一" in r["d"]["byName"], lambda: r["d"])
ck("日誌講沒有上一版", lambda: "沒有上一版可補" in r["o"], lambda: r["o"])
r = run_rune(RUNE_SRC, fail=lambda u: "/8.1.1/" in u, prev="broken")
ck("上一版壞檔＋缺一版 ⇒ rc 1", lambda: r["rc"] == 1, lambda: r["rc"])
ck("日誌講讀不到上一版", lambda: "讀不到上一版" in r["o"], lambda: r["o"])
r = run_rune(RUNE_SRC, fail=lambda u: "/8.1.1/" in u, prev="shape")
ck("上一版格式不對＋缺一版 ⇒ rc 1 不崩潰", lambda: r["rc"] == 1 and "格式不對" in r["o"], lambda: (r["rc"], r["o"]))
r = run_rune(RUNE_SRC, fail=lambda u: "/8.1.1/" in u, prev="shape2")
ck("上一版沒有 byId 鍵＋缺一版 ⇒ rc 1 不崩潰", lambda: r["rc"] == 1 and "格式不對" in r["o"], lambda: (r["rc"], r["o"]))
r = run_rune(RUNE_SRC, prev="broken")
ck("上一版壞檔＋抓得到 ⇒ rc 0 且修好", lambda: r["rc"] == 0 and isinstance(r["d"], dict) and "舊名一" in r["d"]["byName"], lambda: (r["rc"], r["d"]))

# ───────────── fetch_champ_icons ─────────────
NEWV, OLDV = "99.42.1", "99.41.1"
CHAMPS = [f"C{i:02d}" for i in range(10)]
OLD_MARK = b"RIFFOLD-ZZ-9942"
RUNE_URL = f"{CD}/v1/perks/rr.png"


def png_bytes():
    b = io.BytesIO()
    Image.new("RGBA", (128, 128), (200, 30, 30, 255)).save(b, "PNG")
    return b.getvalue()


PNG = png_bytes()


def seed(root, have=CHAMPS, v=OLDV, manifest=True, runes_old=("rr",), rune_file=True, rune_js="good"):
    os.makedirs(os.path.join(root, "img", "champ")); os.makedirs(os.path.join(root, "img", "rune"))
    for c in have:
        open(os.path.join(root, "img", "champ", c + ".webp"), "wb").write(OLD_MARK)
    if rune_file:
        for b in runes_old:
            open(os.path.join(root, "img", "rune", b + ".webp"), "wb").write(OLD_MARK)
    if manifest:
        open(os.path.join(root, "champ_icons.js"), "w", encoding="utf-8").write(
            "window.CHAMP_ICONS=" + json.dumps({"v": v, "ids": sorted(have), "runes": list(runes_old)}) + ";")
    if rune_js == "good":
        open(os.path.join(root, "rune_icons.js"), "w", encoding="utf-8").write(
            R_PREFIX + json.dumps({"byId": {"1": {"zh": "z", "en": "e", "img": RUNE_URL}}, "byName": {"z": RUNE_URL}}) + ";")
    elif rune_js == "broken":
        open(os.path.join(root, "rune_icons.js"), "w", encoding="utf-8").write(R_PREFIX + "{壞掉")
    elif rune_js == "empty":
        open(os.path.join(root, "rune_icons.js"), "w", encoding="utf-8").write(R_PREFIX + '{"byId":{},"byName":{}};')


ROOTS = set()


def run_champ(src, fail=lambda u: False, reply=None, keep_dir=None, **seed_kw):
    root = keep_dir or tempfile.mkdtemp(prefix="champicons_")
    ROOTS.add(root)
    if not keep_dir:
        seed(root, **seed_kw)
    m = load(src, "c_" + os.path.basename(root) + str(time.time_ns()))
    m.ROOT, m.OUT_DIR = root, os.path.join(root, "img", "champ")
    m.RUNE_DIR, m.MANIFEST = os.path.join(root, "img", "rune"), os.path.join(root, "champ_icons.js")
    for k, v in vars(m).items():
        if isinstance(v, str) and v.startswith(REPO) and k not in ("HERE", "__file__", "__cached__"):
            raise SystemExit(f"沙盒漏接 {k}={v}")
    calls, timeouts = [], []

    def urlopen(req, timeout=None):
        u = req.full_url if hasattr(req, "full_url") else req
        calls.append(u); timeouts.append(timeout)
        if fail(u):
            raise OSError("模擬連線被斷 " + u)
        r = reply(u) if reply else None
        if isinstance(r, bytes):
            return Resp(r)
        if r is None:
            if u.endswith("versions.json"): r = [NEWV, OLDV]
            elif u.endswith("champion.json"): r = {"data": {c: {} for c in CHAMPS}}
            else: return Resp(PNG)
        return Resp(json.dumps(r).encode("utf-8"))

    rc, o = drive(m, urlopen)
    man = None
    mp = os.path.join(root, "champ_icons.js")
    if os.path.exists(mp):
        t = open(mp, encoding="utf-8").read()
        man = json.loads(t[t.index("=") + 1:].rstrip().rstrip(";"))
    def webp_new(c, sub="champ"):
        p = os.path.join(root, "img", sub, c + ".webp")
        if not os.path.exists(p):
            return None
        b = open(p, "rb").read()
        return b != OLD_MARK and b[:4] == b"RIFF" and b[8:12] == b"WEBP"
    tmps = [f for dp, _, fs in os.walk(root) for f in fs if f.endswith(".tmp")]
    return dict(rc=rc, o=o, m=man, calls=calls, to=timeouts, new=webp_new, tmps=tmps, root=root, mtime=os.path.getmtime(mp) if man else None)


def imgs(calls): return [u for u in calls if "/img/champion/" in u]


print("══ fetch_champ_icons ══")
print("── 換版、全部抓得到 ──")
r = run_champ(CHAMP_SRC)
ck("rc 0", lambda: r["rc"] == 0, lambda: (r["rc"], r["o"]))
ck("清單記新版本", lambda: r["m"]["v"] == NEWV, lambda: r["m"])
ck("全部換成新圖", lambda: all(r["new"](c) for c in CHAMPS), lambda: [r["new"](c) for c in CHAMPS])
ck("縮成 96", lambda: Image.open(os.path.join(r["root"], "img", "champ", "C00.webp")).size == (96, 96))
ck("單次逾時 30 秒", lambda: set(r["to"]) == {30}, lambda: r["to"])
ck("沒留 tmp", lambda: r["tmps"] == [], lambda: r["tmps"])
ck("沒有警告", lambda: "⚠" not in r["o"], lambda: r["o"])

print("── 版本沒變 ──")
r = run_champ(CHAMP_SRC, v=NEWV)
ck("跳過、不抓圖、rc 0", lambda: r["rc"] == 0 and "跳過" in r["o"] and not imgs(r["calls"]), lambda: r["o"])
ck("舊圖沒被動", lambda: r["new"]("C00") is False)
r = run_champ(CHAMP_SRC, v=NEWV, have=CHAMPS[:9])
ck("同版本只補缺的一張", lambda: [u.rsplit("/", 1)[1] for u in imgs(r["calls"])] == ["C09.png"] and r["new"]("C09"), lambda: r["calls"])

print("── 換版時一張失敗 ──")
r = run_champ(CHAMP_SRC, fail=lambda u: u.endswith("/C03.png"))
ck("rc 0", lambda: r["rc"] == 0, lambda: r["rc"])
ck("版本號留舊的", lambda: r["m"]["v"] == OLDV, lambda: r["m"])
ck("清單還是十隻（舊圖還在）", lambda: r["m"]["ids"] == CHAMPS, lambda: r["m"])
ck("失敗那張留舊圖、其餘換新", lambda: r["new"]("C03") is False and r["new"]("C04"), lambda: r["o"])
ck("日誌指名", lambda: "失敗 1 張" in r["o"] and "C03" in r["o"] and OLDV in r["o"], lambda: r["o"])
ck("失敗那張試 2 次", lambda: sum(u.endswith("/C03.png") for u in r["calls"]) == 2, lambda: r["calls"])
r2 = run_champ(CHAMP_SRC, keep_dir=r["root"])
ck("下一班整批重抓，版本號才前進", lambda: r2["m"]["v"] == NEWV and len(imgs(r2["calls"])) == 10 and r2["new"]("C03"), lambda: (r2["m"], len(imgs(r2["calls"]))))

print("── 新英雄抓不到 ──")
r = run_champ(CHAMP_SRC, have=CHAMPS[:9], fail=lambda u: u.endswith("/C09.png"))
ck("不進清單（走 CDN）、其餘照常", lambda: r["rc"] == 0 and r["m"]["ids"] == CHAMPS[:9], lambda: r["m"])

print("── 回的不是圖 ──")
r = run_champ(CHAMP_SRC, reply=lambda u: b"<html>" if u.endswith("/C05.png") else None)
ck("算失敗、舊圖不被蓋、版本留舊", lambda: r["new"]("C05") is False and r["m"]["v"] == OLDV and r["tmps"] == [], lambda: (r["m"], r["tmps"]))

print("── 圖的 CDN 全斷 ──")
r = run_champ(CHAMP_SRC, fail=lambda u: "/img/champion/" in u)
ck("連 3 張失敗就停手（3×2 次，不是每張等逾時）", lambda: len(imgs(r["calls"])) == 6, lambda: len(imgs(r["calls"])))
ck("rc 0、清單留舊版本、十隻都在", lambda: r["rc"] == 0 and r["m"]["v"] == OLDV and r["m"]["ids"] == CHAMPS, lambda: (r["rc"], r["m"]))
ck("舊圖全留著", lambda: not any(r["new"](c) for c in CHAMPS))
r = run_champ(CHAMP_SRC, fail=lambda u: u.endswith(("/C00.png", "/C01.png", "/C03.png", "/C04.png")))
ck("中間成功會歸零，十張都問到", lambda: len({u for u in imgs(r["calls"])}) == 10, lambda: imgs(r["calls"]))

print("── 版本或英雄清單抓不到 ──")
for label, kw in (("versions.json 斷線", dict(fail=lambda u: u.endswith("versions.json"))),
                  ("champion.json 斷線", dict(fail=lambda u: u.endswith("champion.json"))),
                  ("英雄清單空的", dict(reply=lambda u: {"data": {}} if u.endswith("champion.json") else None)),
                  ("沒有 data 鍵", dict(reply=lambda u: {"x": 1} if u.endswith("champion.json") else None))):
    r = run_champ(CHAMP_SRC, **kw)
    ck(f"{label}：rc 1、清單不動、沒有崩潰", lambda: r["rc"] == 1 and r["m"]["v"] == OLDV and r["m"]["ids"] == CHAMPS and "不寫檔" in r["o"], lambda: (r["rc"], r["o"], r["m"]))

print("── 一張圖都沒有 ──")
r = run_champ(CHAMP_SRC, have=[], manifest=False, fail=lambda u: "/img/champion/" in u)
ck("rc 1、不寫清單", lambda: r["rc"] == 1 and r["m"] is None and "不寫檔" in r["o"], lambda: (r["rc"], r["m"], r["o"]))

print("── rune_icons.js 有問題 ──")
for js in ("broken", "empty", None):
    r = run_champ(CHAMP_SRC, v=NEWV, rune_js=js)
    ck(f"rune_icons.js={js}：符文清單沿用", lambda: r["rc"] == 0 and r["m"]["runes"] == ["rr"] and "沿用上一版符文清單 1 張" in r["o"], lambda: (r["m"], r["o"]))
r = run_champ(CHAMP_SRC, v=NEWV, rune_js="broken", rune_file=False)
ck("沿用時只留真的有檔的", lambda: r["m"]["runes"] == [], lambda: r["m"])

print("── 符文圖 ──")
r = run_champ(CHAMP_SRC, v=NEWV, runes_old=(), rune_file=False)
ck("缺的符文圖會補", lambda: r["m"]["runes"] == ["rr"] and r["new"]("rr", "rune"), lambda: (r["m"], r["o"]))
r = run_champ(CHAMP_SRC, v=NEWV, runes_old=(), rune_file=False, fail=lambda u: u == RUNE_URL)
ck("抓不到：rc 0、不進清單、日誌指名", lambda: r["rc"] == 0 and r["m"]["runes"] == [] and "符文圖抓不到 1 張" in r["o"] and "rr" in r["o"], lambda: (r["rc"], r["m"], r["o"]))

print(f"── 舊版對照（釘 {OLDREV}）──")
td = tempfile.mkdtemp(prefix="icons_old_")
blobs = {}
for n in ("fetch_rune_icons", "fetch_champ_icons"):
    blobs[n] = subprocess.run(["git", "show", f"{OLDREV}:scripts/{n}.py"], cwd=REPO, capture_output=True).stdout
    open(os.path.join(td, n + ".py"), "wb").write(blobs[n])
ck("拉得到舊版", lambda: b"load_prev" not in blobs["fetch_rune_icons"] and b"save_webp" not in blobs["fetch_champ_icons"] and len(blobs["fetch_champ_icons"]) > 1000)
old_r, old_c = os.path.join(td, "fetch_rune_icons.py"), os.path.join(td, "fetch_champ_icons.py")
r = run_rune(old_r, fail=lambda u: "/8.1.1/" in u)
ck("舊版 rune：一版抓不到 ⇒ 舊名消失、rc 0", lambda: r["rc"] == 0 and "舊名一" not in r["d"]["byName"] and r["d"]["byId"]["3"]["zh"] == "", lambda: (r["rc"], r["d"]))
r = run_rune(old_r, reply=lambda u: PERKS[:2] if u.endswith("perks.json") else None)
ck("舊版 rune：CDragon 少 id ⇒ 消失", lambda: "3" not in r["d"]["byId"] and "只有舊版才有" not in r["d"]["byName"], lambda: r["d"])
r = run_champ(old_c, fail=lambda u: u.endswith("/C03.png"))
ck("舊版 champ：換版失敗一張 ⇒ 版本號照樣前進", lambda: r["rc"] == 0 and r["m"]["v"] == NEWV and r["new"]("C03") is False, lambda: r["m"])
r = run_champ(old_c, fail=lambda u: "/img/champion/" in u)
ck("舊版 champ：CDN 全斷 ⇒ 每張都等", lambda: len(imgs(r["calls"])) == 10, lambda: len(imgs(r["calls"])))
r = run_champ(old_c, v=NEWV, rune_js="broken")
ck("舊版 champ：rune_icons.js 壞掉 ⇒ 符文清單清空", lambda: r["m"]["runes"] == [], lambda: r["m"])
r = run_champ(old_c, reply=lambda u: {"data": {}} if u.endswith("champion.json") else None)
ck("舊版 champ：英雄清單空的 ⇒ 寫出空清單 rc 0", lambda: r["rc"] == 0 and r["m"]["ids"] == [], lambda: (r["rc"], r["m"]))
shutil.rmtree(td, ignore_errors=True)

print("── 正本沒被動 ──")
for p, (h, mt) in real_md5.items():
    ck(f"{os.path.basename(p)} md5／mtime 不變", lambda: md5(p) == h and os.path.getmtime(p) == mt)
for p, s in real_dirs.items():
    ck(f"{os.path.relpath(p, REPO)} 檔名與 mtime 不變", lambda: snap_dir(p) == s)
ck("沒留 tmp", lambda: not any(os.path.exists(p + ".tmp") for p in REALS))

for p in ROOTS:
    shutil.rmtree(p, ignore_errors=True)

print(f"\n合計 ✓ {res['ok']}　✗ {res['bad']}")
sys.exit(1 if res["bad"] else 0)
