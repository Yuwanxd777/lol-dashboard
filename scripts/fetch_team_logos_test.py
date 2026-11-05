# -*- coding: utf-8 -*-
"""fetch_team_logos.py 抓不到時的處理（#2610）。不上網、不碰正本。

做法：把被測腳本複製到暫存目錄的 scripts/ 底下，路徑全由 __file__ 推出來，所以 soloq_accounts.json、
img/teams 都落在沙盒。子程序用 runpy 以 __main__ 跑（離開碼是主角），urlopen 由 driver 接管。
舊版對照釘 6ebd8578（#2609，改動前最後一個 commit）。

被測檔可用環境變數 FTL_TARGET 換掉（突變測試用）；FTL_NO_OLD=1 跳過舊版對照。
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TARGET = os.environ.get("FTL_TARGET") or os.path.join(HERE, "fetch_team_logos.py")
OLDREV = "6ebd8578"
GOOD = b"RIFF" + b"\x00" * 400

DRIVER = r'''
import http.client, io, json, os, runpy, socket, sys, time, urllib.error, urllib.request
box, script = sys.argv[1], sys.argv[2]
plan = json.load(open(os.path.join(box, "plan.json"), encoding="utf-8"))
log = []
class R(io.BytesIO):
    pass
def fake(req, timeout=None):
    url = req.full_url if hasattr(req, "full_url") else req
    name = url.rsplit("/", 1)[1].rsplit(".", 1)[0]
    log.append(name)
    b = plan.get(name, "404")
    if b == "ok": return R(b"RIFF" + b"\x00" * 400)
    if b == "small": return R(b"RIFF")
    if b == "html": return R(b"<html>" + b"x" * 500)
    if b == "hang": raise urllib.error.URLError(socket.timeout("timed out"))
    if b == "reset": raise ConnectionResetError("reset")
    if b == "partial":
        class P:
            def read(self): raise http.client.IncompleteRead(b"RIFF")
        return P()
    raise urllib.error.HTTPError(url, int(b), "x", {}, None)
urllib.request.urlopen = fake
time.sleep = lambda s: None
code = 0
try:
    runpy.run_path(script, run_name="__main__")
except SystemExit as e:
    code = e.code or 0
json.dump({"asked": log, "rc": code}, open(os.path.join(box, "result.json"), "w", encoding="utf-8"))
'''


def run(script_text, teams, plan, existing=None, accounts_raw=None):
    box = tempfile.mkdtemp(prefix="ftl_")
    os.makedirs(os.path.join(box, "scripts"))
    os.makedirs(os.path.join(box, "img", "teams"))
    with open(os.path.join(box, "scripts", "fetch_team_logos.py"), "w", encoding="utf-8", newline="") as f:
        f.write(script_text)
    with open(os.path.join(box, "scripts", "soloq_accounts.json"), "w", encoding="utf-8") as f:
        f.write(accounts_raw if accounts_raw is not None else json.dumps([{"team": t} for t in teams]))
    for t, data in (existing or {}).items():
        with open(os.path.join(box, "img", "teams", t + ".webp"), "wb") as f:
            f.write(data)
    json.dump(plan, open(os.path.join(box, "plan.json"), "w", encoding="utf-8"))
    drv = os.path.join(box, "driver.py")
    with open(drv, "w", encoding="utf-8") as f:
        f.write(DRIVER)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, "-I", drv, box, os.path.join(box, "scripts", "fetch_team_logos.py")],
                       capture_output=True, env=env, cwd=box)
    out = p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")
    res = json.load(open(os.path.join(box, "result.json"), encoding="utf-8"))
    files = {}
    for fn in os.listdir(os.path.join(box, "img", "teams")):
        files[fn] = open(os.path.join(box, "img", "teams", fn), "rb").read()
    shutil.rmtree(box, ignore_errors=True)
    return {"out": out, "rc": res["rc"], "asked": res["asked"], "files": files}


oks = bads = 0


def check(name, fn):
    global oks, bads
    try:
        good = bool(fn())
    except Exception as e:
        good = False
        name += f"（例外 {type(e).__name__}: {e}）"
    if good:
        oks += 1
    else:
        bads += 1
    print(("  ✓ " if good else "  ✗ ") + name)


def snapshot():
    h = {}
    p = os.path.join(HERE, "soloq_accounts.json")
    h["acc"] = (hashlib.md5(open(p, "rb").read()).hexdigest(), os.path.getmtime(p))
    d = os.path.join(REPO, "img", "teams")
    h["teams"] = sorted((n, os.path.getmtime(os.path.join(d, n))) for n in os.listdir(d))
    return h


def main():
    before = snapshot()
    new = open(TARGET, encoding="utf-8", newline="").read()

    print("一、正常路徑")
    r = run(new, ["ZZOK9942", "ZZNO9942", "ZZHAVE9942"], {"ZZOK9942": "ok", "ZZNO9942": "404"},
            existing={"ZZHAVE9942": GOOD})
    check("有圖的隊寫進沙盒", lambda: r["files"].get("ZZOK9942.webp", b"").startswith(b"RIFF"))
    check("摘要行格式不變（日誌工具比對前綴）",
          lambda: "隊徽：新抓 1／已有 1／dpm 沒有 1（共 3 隊）→ img/teams/" in r["out"])
    check("全部正常沒有 ⚠", lambda: "⚠" not in r["out"])
    check("rc 0", lambda: r["rc"] == 0)
    check("已有的不再問", lambda: "ZZHAVE9942" not in r["asked"])
    check("沒有留 .tmp", lambda: not [f for f in r["files"] if f.endswith(".tmp")])

    r = run(new, ["GEN"], {"GENG": "ok"})
    check("別名：GEN 去問 GENG、存成 GEN", lambda: r["asked"] == ["GENG"] and "GEN.webp" in r["files"])
    r = run(new, ["ZZTINY"], {"ZZTINY": "ok"}, existing={"ZZTINY": b"RIFF"})
    check("過小的舊檔會重抓", lambda: r["asked"] == ["ZZTINY"] and len(r["files"]["ZZTINY.webp"]) > 200)

    print("二、404／403 是「dpm 沒有」，不是抓不到")
    teams = ["ZZ1", "ZZ2", "ZZ3", "ZZ4", "ZZ5"]
    r = run(new, teams, {"ZZ1": "404", "ZZ2": "403", "ZZ3": "404", "ZZ4": "404", "ZZ5": "ok"})
    check("連續 404 不會停手，第 5 隊照抓", lambda: "ZZ5.webp" in r["files"] and len(r["asked"]) == 5)
    check("算進 dpm 沒有 4", lambda: "dpm 沒有 4（" in r["out"])
    check("沒有 ⚠", lambda: "⚠" not in r["out"])

    print("三、連線類失敗")
    teams = ["ZA", "ZB", "ZC", "ZD", "ZE", "ZF"]
    r = run(new, teams, {t: "hang" for t in teams})
    check("全逾時：問 2 隊就停手", lambda: r["asked"] == ["ZA", "ZB"])
    check("全逾時：不算 dpm 沒有", lambda: "dpm 沒有 0（" in r["out"])
    check("全逾時：⚠ 列出 6 隊隊名", lambda: "隊徽抓不到 6 隊" in r["out"] and "ZF" in r["out"])
    check("全逾時：rc 0、沒有 Traceback", lambda: r["rc"] == 0 and "Traceback" not in r["out"])

    r = run(new, ["ZA", "ZB", "ZC", "ZD"], {"ZA": "hang", "ZB": "ok", "ZC": "reset", "ZD": "ok"})
    check("不連續的失敗不停手", lambda: len(r["asked"]) == 4 and "ZD.webp" in r["files"])
    check("ConnectionResetError 算抓不到", lambda: "隊徽抓不到 2 隊" in r["out"])

    r = run(new, ["ZA", "ZB", "ZC", "ZD"], {"ZA": "hang", "ZB": "404", "ZC": "hang", "ZD": "ok"})
    check("中間的 404 代表連線正常、計數歸零", lambda: len(r["asked"]) == 4 and "ZD.webp" in r["files"])

    r = run(new, ["ZA", "ZB", "ZC"], {"ZA": "429", "ZB": "500", "ZC": "ok"})
    check("429／5xx 算抓不到、連 2 隊就停", lambda: r["asked"] == ["ZA", "ZB"] and "隊徽抓不到 3 隊" in r["out"])

    print("四、回的內容不對")
    r = run(new, ["ZA", "ZB", "ZC", "ZD"], {"ZA": "html", "ZB": "small", "ZC": "html", "ZD": "ok"})
    check("200 但不是圖：不寫檔", lambda: set(r["files"]) == {"ZD.webp"})
    check("200 但不是圖：算抓不到不算 dpm 沒有", lambda: "隊徽抓不到 3 隊" in r["out"] and "dpm 沒有 0（" in r["out"])
    check("200 代表連線正常：不停手", lambda: len(r["asked"]) == 4)
    r = run(new, ["ZA", "ZB"], {"ZA": "partial", "ZB": "ok"})
    check("讀到一半斷線：不留半個檔、不崩潰", lambda: set(r["files"]) == {"ZB.webp"} and r["rc"] == 0 and "Traceback" not in r["out"])

    print("五、隊伍名單壞掉")
    r = run(new, [], {}, accounts_raw="{壞掉")
    check("rc 1", lambda: r["rc"] == 1)
    check("印一行、沒有 Traceback", lambda: "執行失敗" in r["out"] and "Traceback" not in r["out"])

    if not os.environ.get("FTL_NO_OLD"):
        print(f"六、舊版對照（釘 {OLDREV}）")
        p = subprocess.run(["git", "show", f"{OLDREV}:scripts/fetch_team_logos.py"], capture_output=True, cwd=REPO)
        old = p.stdout.decode("utf-8")
        check("拉得到舊版", lambda: "fetch_team_logos" in old and "MAX_CONN_FAIL" not in old)
        teams = ["ZA", "ZB", "ZC", "ZD", "ZE", "ZF"]
        r = run(old, teams, {t: "hang" for t in teams})
        check("舊版全逾時每隊都等", lambda: len(r["asked"]) == 6)
        check("舊版把逾時算成 dpm 沒有", lambda: "dpm 沒有 6（" in r["out"] and "⚠" not in r["out"])
        r = run(old, [], {}, accounts_raw="{壞掉")
        check("舊版名單壞掉 rc 0", lambda: r["rc"] == 0)

    print("七、隔離")
    check("正本 soloq_accounts.json 與 img/teams 的 md5／mtime／檔名沒動", lambda: snapshot() == before)

    print(f"合計 ✓{oks} ✗{bads}")
    return 1 if bads else 0


if __name__ == "__main__":
    sys.exit(main())
