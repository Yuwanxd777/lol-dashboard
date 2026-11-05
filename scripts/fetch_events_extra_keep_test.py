# -*- coding: utf-8 -*-
"""fetch_events_extra.py 抓不到時不可蓋掉舊資料（#2611）。不上網、不碰正本。

素材：redirect 那段是 2026-11-05 真站 action=parse「Esports Nations Cup 2026」的回應原文。
做法：把被測腳本複製到暫存目錄的 scripts/，路徑全由 __file__ 推出來，所以 events_extra.js、
csv_cache、data/ 都落在沙盒。子程序用 runpy 以 __main__ 跑（離開碼要測），urlopen／build_opener 由 driver 接管。
舊版對照釘 d8661150（#2610，改動前最後一個 commit）。

被測檔可用環境變數 FEE_TARGET 換掉（突變測試用）；FEE_NO_OLD=1 跳過舊版對照。
"""
import datetime
import hashlib
import io
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TARGET = os.environ.get("FEE_TARGET") or os.path.join(HERE, "fetch_events_extra.py")
OLDREV = "d8661150"

REDIRECT = ('<div class="mw-content-ltr mw-parser-output" lang="en" dir="ltr"><div class="redirectMsg"><p>Redirect to:</p>'
            '<ul class="redirectText"><li><a href="/wiki/Esports_Nations_Cup_2027" title="Esports Nations Cup 2027">'
            'Esports Nations Cup 2027</a></li></ul></div>')


def page_html(teams, rosters=(), day="2026-11-01"):
    h = [f"<p>{day}</p>"]
    for t in teams:
        h.append(f'<span class="team-template-text"><a title="{t}">x</a></span>')
    for t in rosters:
        h.append(f'<table class="tournament-roster"><a class="catlink-teams" title="{t}">x</a>'
                 f'<span title="Top Laner" class="sprite"></span><a class="catlink-players" href="x">P_{t.replace(" ", "")}</a></table>')
    return "".join(h)


DRIVER = r'''
import io, json, os, runpy, sys, time, urllib.parse, urllib.request, urllib.error
box, script = sys.argv[1], sys.argv[2]
plan = json.load(open(os.path.join(box, "plan.json"), encoding="utf-8"))
asked = []
class R(io.BytesIO):
    pass
def fake(req, timeout=None):
    url = req.full_url if hasattr(req, "full_url") else req
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    if q.get("action") == ["query"]:
        return R(json.dumps({"query": {}}).encode())
    page = q["page"][0]
    asked.append(page)
    b = plan["pages"].get(page, plan["nation"] if page == plan["nation_page"] else plan["default"])
    if b == "fail":
        raise urllib.error.URLError("reset")
    return R(json.dumps({"parse": {"text": {"*": b}}}).encode())
class Op:
    def open(self, req, timeout=None):
        url = req.full_url
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        asked.append("cargo")
        if plan.get("cargo") == "fail" and "tables" in q:
            raise urllib.error.URLError("cargo down")
        return R(b"[]")
urllib.request.urlopen = fake
urllib.request.build_opener = lambda *a, **k: Op()
time.sleep = lambda s: None
code = 0
try:
    runpy.run_path(script, run_name="__main__")
except SystemExit as e:
    code = e.code or 0
json.dump({"asked": asked, "rc": code}, open(os.path.join(box, "result.json"), "w", encoding="utf-8"))
'''

NATION_PAGE = "2026 Asian Games"
OK = page_html(["Zz New Alpha", "Zz New Bravo"], ["Zz New Alpha", "Zz New Bravo"])


def seed_entry(tag, page="p"):
    t = [f"Zz Old {tag} A", f"Zz Old {tag} B", f"Zz Old {tag} C"]
    return {"teams": t, "rosters": {x: [{"n": "Old_" + x.replace(" ", ""), "r": "TOP"}] for x in t},
            "from": "2026-01-01", "to": "2026-01-09", "po": [], "page": page, "url": "u"}


def seed():
    """舊檔＋meta：2013 全部還新（沿用），2026 全部有舊資料"""
    g = runpy.run_path(TARGET, run_name="not_main")
    ev, sig = g["EVENTS"], g["_sig"]
    now = datetime.datetime.now()
    fresh = now.strftime("%Y-%m-%d %H:%M")
    old, meta = {}, {}
    for y, evs in ev.items():
        old[str(y)] = {}
        for c, cfg in evs.items():
            e = seed_entry(c)
            if cfg.get("splits"):
                e["splits"] = [{**seed_entry(c + s["sp"]), "sp": s["sp"], "from": "2013-0%d-01" % (i + 1), "to": "2013-0%d-09" % (i + 1)}
                               for i, s in enumerate(cfg["splits"])]
            old[str(y)][c] = e
            if int(y) < now.year:
                meta[f"{y}|{c}"] = {"sig": sig(cfg), "at": fresh}
    return old, meta, ev


def run(script_text, plan, old, meta):
    box = tempfile.mkdtemp(prefix="fee_")
    os.makedirs(os.path.join(box, "scripts"))
    os.makedirs(os.path.join(box, "csv_cache"))
    os.makedirs(os.path.join(box, "data"))
    spath = os.path.join(box, "scripts", "fetch_events_extra.py")
    with open(spath, "w", encoding="utf-8", newline="") as f:
        f.write(script_text)
    with open(os.path.join(box, "events_extra.js"), "w", encoding="utf-8") as f:
        f.write("window.EVENTS_EXTRA=" + json.dumps(old, ensure_ascii=False) + ";")
    json.dump(meta, open(os.path.join(box, "csv_cache", "events_extra_meta.json"), "w", encoding="utf-8"), ensure_ascii=False)
    # 亞運是國家隊型（teams_of 只認 X (National Team)），要給它自己的頁，否則快樂路徑也是 0 隊
    plan = {**plan, "nation": '<a title="Zz Land (National Team)">x</a>', "nation_page": NATION_PAGE}
    json.dump(plan, open(os.path.join(box, "plan.json"), "w", encoding="utf-8"), ensure_ascii=False)
    drv = os.path.join(box, "driver.py")
    with open(drv, "w", encoding="utf-8") as f:
        f.write(DRIVER)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, "-I", drv, box, spath], capture_output=True, env=env, cwd=box)
    out = p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")
    res = json.load(open(os.path.join(box, "result.json"), encoding="utf-8"))
    raw = open(os.path.join(box, "events_extra.js"), encoding="utf-8").read()
    data = json.loads(re.sub(r"^window\.EVENTS_EXTRA=|;\s*$", "", raw.strip()))
    m = json.load(open(os.path.join(box, "csv_cache", "events_extra_meta.json"), encoding="utf-8"))
    left = sorted(os.listdir(box))
    shutil.rmtree(box, ignore_errors=True)
    return {"out": out, "rc": res["rc"], "asked": res["asked"], "data": data, "meta": m, "files": left}


oks = bads = 0


def check(name, fn):
    global oks, bads
    try:
        good = bool(fn())
    except Exception as e:
        good = False
        name += f"（例外 {type(e).__name__}: {e}）"
    oks, bads = (oks + 1, bads) if good else (oks, bads + 1)
    print(("  ✓ " if good else "  ✗ ") + name)


def snapshot():
    h = {}
    for rel in ("events_extra.js", os.path.join("csv_cache", "events_extra_meta.json"), os.path.join("csv_cache", "wiki_realname_id.json")):
        p = os.path.join(REPO, rel)
        h[rel] = (hashlib.md5(open(p, "rb").read()).hexdigest(), os.path.getmtime(p)) if os.path.exists(p) else None
    return h


def main():
    before = snapshot()
    src = open(TARGET, encoding="utf-8", newline="").read()
    old, meta, ev = seed()
    deep = lambda x: json.loads(json.dumps(x, ensure_ascii=False))
    PAGE_AC = ev[2026]["AC"]["page"]
    GPL = ev[2013]["GPL"]["splits"]
    stale = "2026-01-01 00:00"
    # 2013 GPL 到期 ⇒ 這班會抓它
    meta_gpl = deep(meta)
    meta_gpl["2013|GPL"]["at"] = stale
    meta_lco = deep(meta)
    meta_lco["2013|LCO"]["at"] = stale
    PAGE_LCO = ev[2013]["LCO"]["page"]

    print("〔快樂路徑：正例要真的會更新〕")
    r = run(src, {"default": OK, "pages": {}}, old, meta)
    check("rc 0", lambda: r["rc"] == 0)
    check("今年賽事換成新資料", lambda: r["data"]["2026"]["AC"]["teams"] == ["Zz New Alpha", "Zz New Bravo"])
    check("隊數變少（3→2）是真的變少，照收", lambda: len(r["data"]["2026"]["DCup"]["teams"]) == 2)
    check("沒參賽的隊不留舊名單", lambda: "Zz Old AC A" not in r["data"]["2026"]["AC"]["rosters"])
    check("沒有警告", lambda: "⚠" not in r["out"])
    check("2013 還新的照舊沿用", lambda: r["data"]["2013"]["TCL"]["teams"] == old["2013"]["TCL"]["teams"])
    check("沒留 .tmp", lambda: not any(f.endswith(".tmp") for f in r["files"]))

    print("〔頁面搬走（真站轉址素材）〕")
    r = run(src, {"default": OK, "pages": {PAGE_AC: REDIRECT}}, old, meta)
    check("整筆沿用舊檔", lambda: r["data"]["2026"]["AC"] == old["2026"]["AC"])
    check("rc 1", lambda: r["rc"] == 1)
    check("指名搬去哪裡", lambda: "Esports Nations Cup 2027" in r["out"] and "頁面已搬走" in r["out"])
    check("收尾指名是哪個賽事", lambda: "2026|AC" in r["out"].split("個賽事解析到 0 隊")[1])
    check("其他賽事照常更新", lambda: r["data"]["2026"]["DCup"]["teams"] == ["Zz New Alpha", "Zz New Bravo"])

    print("〔不是轉址、版型變了：一樣 0 隊〕")
    r = run(src, {"default": OK, "pages": {PAGE_AC: "<p>nothing</p>"}}, old, meta)
    check("沿用舊檔、rc 1", lambda: r["data"]["2026"]["AC"] == old["2026"]["AC"] and r["rc"] == 1)
    check("不謊稱搬走", lambda: "頁面已搬走" not in r["out"])

    print("〔舊檔本來就沒有：新賽事還沒名單〕")
    o2 = deep(old)
    del o2["2026"]["AC"]
    r = run(src, {"default": OK, "pages": {PAGE_AC: "<p>nothing</p>"}}, o2, meta)
    check("照舊寫空的那筆", lambda: r["data"]["2026"]["AC"]["teams"] == [])
    check("rc 0（沒有東西被蓋掉）", lambda: r["rc"] == 0)

    print("〔歷史年份 0 隊：不可以記成抓過〕")
    r = run(src, {"default": OK, "pages": {PAGE_LCO: REDIRECT}}, old, meta_lco)
    check("確實抓了這頁", lambda: PAGE_LCO in r["asked"])
    check("沿用舊檔", lambda: r["data"]["2013"]["LCO"] == old["2013"]["LCO"])
    check("at 沒動、記 tried", lambda: r["meta"]["2013|LCO"]["at"] == stale and "tried" in r["meta"]["2013|LCO"])

    print("〔歷史年份正常抓到：at 要前進（對照）〕")
    r = run(src, {"default": OK, "pages": {}}, old, meta_lco)
    check("at 前進", lambda: r["meta"]["2013|LCO"]["at"] != stale and "tried" not in r["meta"]["2013|LCO"])

    print("〔Cargo 掛掉：名單不可以消失〕")
    only_teams = page_html(["Zz Old AC A", "Zz Old AC B", "Zz Brand New"], ["Zz Old AC B"])
    r = run(src, {"default": OK, "pages": {PAGE_AC: only_teams}, "cargo": "fail"}, old, meta)
    e = r["data"]["2026"]["AC"]
    check("這班沒名單的隊沿用舊名單", lambda: e["rosters"]["Zz Old AC A"] == old["2026"]["AC"]["rosters"]["Zz Old AC A"])
    check("這班有名單的隊用新的", lambda: e["rosters"]["Zz Old AC B"][0]["n"] == "P_ZzOldACB")
    check("舊檔也沒有的隊不生出來", lambda: "Zz Brand New" not in e["rosters"])
    check("已不參賽的隊不留", lambda: "Zz Old AC C" not in e["rosters"])
    check("印警告、rc 0（下一班再試）", lambda: "1 隊這班沒有名單" in r["out"] and r["rc"] == 0)

    print("〔分賽段：一段連線失敗〕")
    sp0, sp1, sp2 = GPL[0], GPL[1], GPL[2]
    r = run(src, {"default": OK, "pages": {sp1["page"]: "fail"}}, old, meta_gpl)
    e, oe = r["data"]["2013"]["GPL"], old["2013"]["GPL"]
    check("還是三段", lambda: [s["sp"] for s in e["splits"]] == [s["sp"] for s in GPL])
    check("失敗那段是舊資料", lambda: e["splits"][1]["teams"] == oe["splits"][1]["teams"])
    check("別段是新資料", lambda: e["splits"][0]["teams"] == ["Zz New Alpha", "Zz New Bravo"])
    check("頂層隊伍含舊段", lambda: oe["splits"][1]["teams"][0] in e["teams"] and "Zz New Alpha" in e["teams"])
    check("頂層名單含舊段", lambda: oe["splits"][1]["teams"][0] in e["rosters"])
    check("頂層日期含舊段", lambda: e["from"] <= oe["splits"][1]["from"] and e["to"] >= oe["splits"][1]["to"])
    check("at 沒動、rc 0（暫時性）", lambda: r["meta"]["2013|GPL"]["at"] == stale and r["rc"] == 0)

    print("〔分賽段：一段搬走〕")
    r = run(src, {"default": OK, "pages": {sp2["page"]: REDIRECT}}, old, meta_gpl)
    e = r["data"]["2013"]["GPL"]
    check("0 隊那段是舊資料", lambda: e["splits"][2]["teams"] == oe["splits"][2]["teams"])
    check("別段是新資料", lambda: e["splits"][1]["teams"] == ["Zz New Alpha", "Zz New Bravo"])
    check("rc 1、指名賽段", lambda: r["rc"] == 1 and f"2013|GPL|{sp2['sp']}" in r["out"])
    check("at 沒動", lambda: r["meta"]["2013|GPL"]["at"] == stale)

    print("〔分賽段：Cargo 掛掉，賽段名單不可以消失〕")
    t0 = oe["splits"][0]["teams"][0]
    r = run(src, {"default": OK, "pages": {sp0["page"]: page_html([t0])}, "cargo": "fail"}, old, meta_gpl)
    e = r["data"]["2013"]["GPL"]
    check("賽段沿用舊名單", lambda: e["splits"][0]["rosters"][t0] == oe["splits"][0]["rosters"][t0])
    check("頂層也有", lambda: t0 in e["rosters"])

    print("〔分賽段：全部失敗〕")
    pages = {s["page"]: "fail" for s in GPL}
    r = run(src, {"default": OK, "pages": pages}, old, meta_gpl)
    check("三段都是舊資料", lambda: [s["teams"] for s in r["data"]["2013"]["GPL"]["splits"]] == [s["teams"] for s in oe["splits"]])

    print("〔分賽段：全部正常（對照）〕")
    r = run(src, {"default": OK, "pages": {}}, old, meta_gpl)
    check("三段都換新、at 前進", lambda: all(s["teams"] == ["Zz New Alpha", "Zz New Bravo"] for s in r["data"]["2013"]["GPL"]["splits"]) and r["meta"]["2013|GPL"]["at"] != stale)
    check("舊段的隊不殘留", lambda: oe["splits"][0]["teams"][0] not in r["data"]["2013"]["GPL"]["teams"])

    print("〔單頁連線失敗（原本就對）〕")
    r = run(src, {"default": OK, "pages": {PAGE_AC: "fail"}}, old, meta)
    check("沿用舊檔、rc 0", lambda: r["data"]["2026"]["AC"] == old["2026"]["AC"] and r["rc"] == 0)

    if not os.environ.get("FEE_NO_OLD"):
        print(f"〔舊版對照（{OLDREV}）：同一份素材要重現真實事故〕")
        o = subprocess.run(["git", "show", f"{OLDREV}:scripts/fetch_events_extra.py"], capture_output=True, cwd=REPO).stdout.decode("utf-8")
        r = run(o, {"default": OK, "pages": {PAGE_AC: REDIRECT}}, old, meta)
        check("舊版：搬走的頁把舊資料蓋成 0 隊", lambda: r["data"]["2026"]["AC"]["teams"] == [])
        check("舊版：rc 0、沒人出聲", lambda: r["rc"] == 0 and "⚠" not in r["out"])
        r = run(o, {"default": OK, "pages": {sp1["page"]: "fail"}}, old, meta_gpl)
        check("舊版：失敗的賽段從輸出消失", lambda: len(r["data"]["2013"]["GPL"]["splits"]) == 2)

    print("〔正本沒動〕")
    check("events_extra.js／meta／本名表的 md5 與 mtime 都沒變", lambda: snapshot() == before)
    print(f"合計 ✓{oks} ✗{bads}")
    sys.exit(1 if bads else 0)


if __name__ == "__main__":
    main()
