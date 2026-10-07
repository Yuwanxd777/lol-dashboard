# -*- coding: utf-8 -*-
"""fetch_skills 的「CDragon 暫時抓不到 ⇒ 沿用上一版」沙盒測試（2026-10-07 #942）。

案發：26.20 當天 CDragon 全面 522，舊版把 522 當「沒有 bin」建成純描述條目，173 位全部沒數值。
修法：5xx／逾時 → Transient（不進快取），skills.js 用快取 prev（上一版）補位、v 留在上一版。

沙盒接管 fetch_skills 的每一個證據來源與出口：CACHE／OUT_JS／ST_F 指到暫存資料夾、get_json 與
build_champ 換成假的；跑之前 assert 模組層沒有路徑常數還指著真實 repo。
正例：B 這一班建得成 ⇒ 用新版、v＝新版。反例：B 522 ⇒ 沿用上一版、v＝上一版、快取不收 B。
"""
import io, json, sys, tempfile, urllib.error
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_skills as fs

REPO = Path(__file__).resolve().parent.parent

def entry(tag, fb=False):
    return {"n": tag, "t": "", "p": {"n": "", "d": ""}, "s": [{"d": tag, **({"fb": 1} if fb else {})}]}

def run(tmp, fail):
    fs.CACHE, fs.OUT_JS, fs.ST_F = tmp / "cache.json", tmp / "skills.js", tmp / "st.json"
    for name in ("CACHE", "OUT_JS", "ST_F"):
        assert REPO not in getattr(fs, name).resolve().parents, f"{name} 還指著真實 repo"
    fs.ST_F.write_text('{"entries":{}}', encoding="utf-8")
    fs.CACHE.write_text(json.dumps({"ver": "OLD", "cdver": "C1",
                                    "champs": {"A": entry("A-old"), "B": entry("B-old")}}), encoding="utf-8")
    def fake_get_json(url, timeout=30):
        if url.endswith("versions.json"):
            return ["NEW"]
        if url.endswith("champion.json"):
            return {"data": {"A": {}, "B": {}, "Jade_X": {}}}
        if url.endswith("content-metadata.json"):
            return {"version": "C1"}
        raise AssertionError(f"沙盒漏接的網址：{url}")
    def fake_build(cid, ddv, st=None):
        assert ddv == "NEW"
        if cid == "B" and fail:
            raise fs.Transient("CDragon bin 暫時抓不到：HTTP Error 522")
        return entry(f"{cid}-new")
    fs.get_json, fs.build_champ = fake_get_json, fake_build
    buf = io.StringIO()
    with redirect_stdout(buf):
        fs.main()
    js = fs.OUT_JS.read_text(encoding="utf-8")
    out = json.loads(js[js.index("=") + 1:].rstrip(";"))
    cache = json.loads(fs.CACHE.read_text(encoding="utf-8"))
    return out, cache, buf.getvalue()

def main():
    fs.FORCE, fs.SINGLE = False, None
    bad = 0
    def check(cond, msg):
        nonlocal bad
        print(("✓ " if cond else "✗ ") + msg)
        bad += not cond
    # _is_transient：522／429／連線失敗算暫時，404 不算
    check(fs._is_transient(urllib.error.HTTPError("u", 522, "x", {}, None)), "522 算暫時性")
    check(fs._is_transient(urllib.error.HTTPError("u", 429, "x", {}, None)), "429 算暫時性")
    check(fs._is_transient(urllib.error.URLError("timed out")), "連線失敗算暫時性")
    check(not fs._is_transient(urllib.error.HTTPError("u", 404, "x", {}, None)), "404 不算（真的沒有 bin）")
    with tempfile.TemporaryDirectory() as td:
        out, cache, log = run(Path(td), fail=False)                     # 正例
        check(out["v"] == "NEW", f"正例：全部建成 ⇒ v＝新版（得到 {out['v']}）")
        check(out["d"]["B"]["s"][0]["d"] == "B-new", "正例：B 用新版條目")
        check("Jade_X" not in out["d"], "分支服不進 skills.js")
    with tempfile.TemporaryDirectory() as td:
        out, cache, log = run(Path(td), fail=True)                      # 反例
        check(out["v"] == "OLD", f"反例：B 522 ⇒ v 留在上一版（得到 {out['v']}）")
        check(out["d"]["B"]["s"][0]["d"] == "B-old", "反例：B 沿用上一版條目（不是純描述）")
        check(out["d"]["A"]["s"][0]["d"] == "A-new", "反例：A 照樣用新版")
        check("B" not in cache["champs"], "反例：B 沒進這一版快取（下一班會再試）")
        check(cache["prev"]["ver"] == "OLD" and "B" in cache["prev"]["champs"], "快取留著 prev＝上一版")
        check("沿用上一版" in log, "日誌有印沿用上一版")
    print("全部通過" if not bad else f"{bad} 項失敗")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
