# -*- coding: utf-8 -*-
"""fetch_items 的「來源暫時掛掉就沿用上一班」回歸測試（2026-10-07 精進迴圈 #943）。

背景：10-07 10:00 班 CDragon 整片 522，fetch_items 在下載 items bin 時 Traceback exit 1。
修法：5xx／429／逾時／連線失敗 ⇒ 保留上一班 items.js 與快取、正常結束；404 等其他錯照樣丟。

沙盒接管每一個證據來源與出口：CACHE_DIR／BIN_F／ST_F／MARK_F／OUT_JS（檔案）＋ get（網路）。
跑之前先 assert 模組層沒有任何路徑常數還指著真實 repo。
"""
import io, json, os, shutil, sys, tempfile, urllib.error
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fetch_items as fi  # noqa: E402

REAL = str(HERE.parent)
ok = bad = 0


def eq(got, want, name):
    global ok, bad
    if got == want:
        ok += 1
    else:
        bad += 1
        print("   ✗ %s：得到 %r，應為 %r" % (name, got, want))


SB = Path(tempfile.mkdtemp(prefix="fi943_"))
fi.CACHE_DIR = SB / "csv_cache"
fi.BIN_F = fi.CACHE_DIR / "items_bin.json"
fi.ST_F = fi.CACHE_DIR / "items_st_zhtw.json"
fi.MARK_F = fi.CACHE_DIR / "items_cache_ver.txt"
fi.OUT_JS = SB / "items.js"
fi.ROOT = SB
for k in ("CACHE_DIR", "BIN_F", "ST_F", "MARK_F", "OUT_JS"):
    assert REAL not in str(getattr(fi, k)), "沙盒漏接：%s 仍指著真實 repo" % k
for k, v in vars(fi).items():
    if not k.startswith("__") and isinstance(v, (str, Path)) and REAL in str(v):
        raise SystemExit("沙盒漏接：模組層 %s 仍指著真實 repo（%s）" % (k, v))

BIN = {"Items/1001": {"mDataValues": []}}
ST = {"entries": {"item_1001_tooltip": "移動速度 +25"}}
DD = {"data": {"1001": {"name": "鞋子", "description": "<stats>移速</stats>"}}}
OLD_JS = 'window.ITEM_DESC={"舊":"x"};window.ITEM_XTRA={};window.ITEM_DESC_VER="16.19.1-09241000";'


def http(code):
    return urllib.error.HTTPError("u", code, "x", {}, None)


def mkget(ver="16.20.1", fail=None):
    """fail：{網址關鍵字: 例外}；命中就丟。calls 記錄打過哪些網址。"""
    calls = []

    def get(url, timeout=180):
        calls.append(url)
        for kw, e in (fail or {}).items():
            if kw in url:
                raise e
        if url.endswith("versions.json"):
            return json.dumps([ver]).encode()
        if "items.cdtb.bin.json" in url:
            return json.dumps(BIN).encode()
        if "stringtable" in url:
            return json.dumps(ST).encode()
        if "item.json" in url:
            return json.dumps(DD, ensure_ascii=False).encode("utf-8")
        raise AssertionError("沙盒沒預期的網址：" + url)
    get.calls = calls
    return get


def reset():
    shutil.rmtree(SB, ignore_errors=True)
    fi.CACHE_DIR.mkdir(parents=True)
    fi.OUT_JS.write_text(OLD_JS, encoding="utf-8")
    fi.BIN_F.write_text('{"舊bin":1}', encoding="utf-8")
    fi.ST_F.write_text('{"entries":{}}', encoding="utf-8")
    fi.MARK_F.write_text("16.19.1")


def run(get):
    fi.get = get
    buf, old = io.StringIO(), sys.stdout
    sys.stdout = buf
    try:
        fi.main()
        exc = None
    except Exception as e:  # noqa: BLE001
        exc = e
    finally:
        sys.stdout = old
    return buf.getvalue(), exc


try:
    # ① 正例：來源正常 ⇒ items.js 換新版、快取跟著換（證明沙盒真的會動）
    reset()
    out, exc = run(mkget())
    eq(exc, None, "①正常跑不丟例外")
    eq('ITEM_DESC_VER="16.20.1-' in fi.OUT_JS.read_text(encoding="utf-8"), True, "①items.js 換到 16.20.1")
    eq(fi.MARK_F.read_text(), "16.20.1", "①版本標記跟著換")
    eq(json.loads(fi.BIN_F.read_text(encoding="utf-8")), BIN, "①bin 快取換新")

    # ② CDragon bin 522 ⇒ 沿用上一班、不丟例外、快取與 items.js 原封不動
    for name, e in (("522", http(522)), ("429", http(429)),
                    ("逾時", TimeoutError("timed out")), ("連線失敗", urllib.error.URLError("refused"))):
        reset()
        out, exc = run(mkget(fail={"items.cdtb": e}))
        eq(exc, None, "②%s：不丟例外" % name)
        eq(fi.OUT_JS.read_text(encoding="utf-8"), OLD_JS, "②%s：items.js 原封不動" % name)
        eq(fi.MARK_F.read_text(), "16.19.1", "②%s：版本標記不往前（健檢才看得出落後）" % name)
        eq("維持上一班的 16.19.1" in out, True, "②%s：印出沿用訊息" % name)

    # ③ bin 成功、字串表 522 ⇒ 不留「新 bin 配舊字串表」的半套
    reset()
    out, exc = run(mkget(fail={"stringtable": http(522)}))
    eq(exc, None, "③字串表 522 不丟例外")
    eq(fi.BIN_F.read_text(encoding="utf-8"), '{"舊bin":1}', "③bin 快取沒被單獨換掉")

    # ④ DDragon item.json 暫時掛掉也沿用
    reset()
    out, exc = run(mkget(fail={"item.json": http(503)}))
    eq(exc, None, "④DDragon item.json 503 不丟例外")
    eq(fi.OUT_JS.read_text(encoding="utf-8"), OLD_JS, "④items.js 原封不動")

    # ⑤ 反例：404（真的沒有這個檔）照樣丟——不能把結構性錯誤吞成沿用
    reset()
    out, exc = run(mkget(fail={"items.cdtb": http(404)}))
    eq(isinstance(exc, urllib.error.HTTPError), True, "⑤404 照樣丟例外")

    # ⑥ 反例：沒有上一班 items.js 可沿用 ⇒ 照樣丟（不能假裝成功）
    reset()
    fi.OUT_JS.unlink()
    out, exc = run(mkget(fail={"items.cdtb": http(522)}))
    eq(isinstance(exc, urllib.error.HTTPError), True, "⑥沒有舊檔可沿用時 522 照樣丟")
finally:
    shutil.rmtree(SB, ignore_errors=True)

print("fetch_items 沿用測試：通過 %d 條，失敗 %d 條" % (ok, bad))
sys.exit(1 if bad else 0)
