# -*- coding: utf-8 -*-
"""fetch_soloq_year 的沙盒測試（2026-09-09 主迴圈 #85 加）——不連網、不開瀏覽器、不碰真實 repo。

蓋三件事：
  A) `_key_of_file` / `_keys_on_disk`：只讀檔頭解出選手 key，不要為了開頭那個字串解析整個 250MB。
     「只有沙盒才有的證據」正例＝**把檔案後半段寫成壞掉的 JSON**：快路徑照樣拿得到 key，
     代表它真的沒有解析整個檔（舊版一定會炸）。
  B) `role_counts`：5 條路線併發問，出現 -1（非 200）或丟例外就退回循序版重問一次。
  C) 四支 soloq 抓取共用的 Cloudflare 等待區塊「先問再等」：直接把原始碼裡那一段抽出來 exec，
     用假 pg／假 time 檢查「第一次就 200 ⇒ 一秒都不睡」與「沒放行時 3.5/14/25 階梯不變」。
     正控制＝改動前那 4 行寫死在本檔（`OLD_CF_BLOCK`），跑同一套必須紅在「第一次就 200 也先睡 3.5」。
     **不要改成對著 `git show HEAD:`**——改動一 commit 進去 HEAD 就是新版，正控制會當場翻紅
     （fetch_soloq_ladder_test.py 就這樣在 #84 commit 之後變成「37 通過／4 失敗」）。

用法：python scripts/fetch_soloq_year_test.py
"""
import io, json, os, subprocess, sys, tempfile, textwrap, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

OK = []
BAD = []


def chk(name, cond, extra=""):
    (OK if cond else BAD).append(name)
    if not cond:
        print("   FAIL %s %s" % (name, extra))


# ───────────────────────── A) 檔頭解 key ─────────────────────────
def write_sq(path, key, matches, tail_ok=True):
    """造一個逐場檔；tail_ok=False 時把後半段寫成壞掉的 JSON（只有沙盒會有）。"""
    body = json.dumps({"role": "MIDDLE", "matches": matches}, ensure_ascii=False)
    if not tail_ok:
        body = body[:-1] + ", THIS IS NOT JSON }}}"
    with io.open(path, "w", encoding="utf-8") as f:
        f.write("window.__sqLoad(%s,%s);\n" % (json.dumps(key, ensure_ascii=False), body))


def test_key_of_file(fy):
    d = tempfile.mkdtemp(prefix="r85sq_")
    try:
        big = [{"t": 1700000000000 + i, "c": "Ahri", "k": i} for i in range(4000)]
        write_sq(os.path.join(d, "p0.js"), "T1|Faker", big)
        write_sq(os.path.join(d, "p1.js"), "HLE|제우스", big[:5])            # 非 ASCII key
        write_sq(os.path.join(d, "p2.js"), 'GEN|Chovy "(quote)"', big[:5])   # key 裡有引號與括號
        write_sq(os.path.join(d, "p3.js"), "DK|Broken", big[:5], tail_ok=False)  # 後半段是壞 JSON
        with io.open(os.path.join(d, "p4.js"), "w", encoding="utf-8") as f:
            f.write("window.__NOTsqLoad(oops);\n")                            # 前綴不對 → 退回整檔解析 → 丟例外
        io.open(os.path.join(d, "notes.txt"), "w", encoding="utf-8").write("x")  # 不是 pN.js，要被略過

        chk("A1 大檔拿得到 key", fy._key_of_file(os.path.join(d, "p0.js")) == "T1|Faker")
        chk("A2 非 ASCII key", fy._key_of_file(os.path.join(d, "p1.js")) == "HLE|제우스")
        chk("A3 key 內含引號", fy._key_of_file(os.path.join(d, "p2.js")) == 'GEN|Chovy "(quote)"')
        # 只有沙盒才有的證據：後半段是壞 JSON，能回 key 就證明沒解析整個檔
        chk("A4 壞掉的尾巴不影響（＝真的沒解析整檔）", fy._key_of_file(os.path.join(d, "p3.js")) == "DK|Broken")
        # head 小到切斷 key 時要退回整檔解析（保底路徑本身也要對）
        chk("A5 檔頭切太短仍退回整檔解析", fy._key_of_file(os.path.join(d, "p0.js"), head=4) == "T1|Faker")
        try:
            fy._key_of_file(os.path.join(d, "p4.js"))
            chk("A6 前綴不對要丟例外", False, "沒丟")
        except Exception:
            chk("A6 前綴不對要丟例外", True)

        got = fy._keys_on_disk(d)
        chk("A7 _keys_on_disk 只認 pN.js、壞檔跳過",
            got == {"T1|Faker", "HLE|제우스", 'GEN|Chovy "(quote)"', "DK|Broken"}, sorted(got))
        chk("A8 目錄不存在回空集合", fy._keys_on_disk(os.path.join(d, "nope")) == set())
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ───────────────────────── B) role_counts ─────────────────────────
class FakePage(object):
    """假 pg：依「JS 裡有沒有 Promise.all」分辨併發版／循序版，各自給預設好的回應。"""

    def __init__(self, par, seq):
        self.par, self.seq = par, seq
        self.calls = []

    def evaluate(self, js, arg=None):
        mode = "par" if "Promise.all" in js else "seq"
        self.calls.append(mode)
        r = self.par if mode == "par" else self.seq
        if isinstance(r, Exception):
            raise r
        return r


FULL = {"top": 1, "jungle": 2, "middle": 30, "bottom": 4, "utility": 5}
WITH_NEG = {"top": 1, "jungle": -1, "middle": 30, "bottom": 4, "utility": 5}


def test_role_counts(fy):
    p = FakePage(FULL, {"middle": 999})
    chk("B1 併發乾淨就用併發結果", fy.role_counts(p, "PU") == FULL)
    chk("B2 併發乾淨時不重問循序", p.calls == ["par"], p.calls)

    p = FakePage(WITH_NEG, FULL)
    chk("B3 併發有 -1 退回循序", fy.role_counts(p, "PU") == FULL)
    chk("B4 退回循序時的呼叫順序", p.calls == ["par", "seq"], p.calls)

    p = FakePage(RuntimeError("boom"), FULL)
    chk("B5 併發丟例外退回循序", fy.role_counts(p, "PU") == FULL)
    chk("B6 例外時也真的問了循序", p.calls == ["par", "seq"], p.calls)

    p = FakePage(RuntimeError("boom"), RuntimeError("boom2"))
    chk("B7 兩邊都掛回空字典（不炸）", fy.role_counts(p, "PU") == {})

    p = FakePage(WITH_NEG, WITH_NEG)
    chk("B8 循序也有 -1 就回循序結果（舊行為）", fy.role_counts(p, "PU") == WITH_NEG)

    p = FakePage(None, FULL)
    chk("B9 併發回非字典退回循序", fy.role_counts(p, "PU") == FULL)

    p = FakePage({}, {})
    chk("B10 兩邊都空回空", fy.role_counts(p, "PU") == {})

    chk("B11 併發版 JS 用 Promise.all", "Promise.all" in fy.JS_ROLE)
    chk("B12 循序版 JS 沒有 Promise.all", "Promise.all" not in fy.JS_ROLE_SEQ)
    # 兩版打的是同一個端點、同樣的 -1 規則（逐字比對片段）
    for frag in ("/v1/players/${PU}/match-history?size=15&page=1&lane=${t}",
                 "r.ok ? ((await r.json()).totalCount||0) : -1",
                 "['top','jungle','middle','bottom','utility']"):
        chk("B13 兩版共用片段：%s" % frag[:34], frag in fy.JS_ROLE and frag in fy.JS_ROLE_SEQ)


# ───────────────────── C) Cloudflare 等待區塊 ─────────────────────
CF_FILES = ("fetch_soloq_champs.py", "fetch_soloq_matches_raw.py",
            "fetch_soloq_update.py", "fetch_soloq_year.py")

# 2026-09-09 #85 改動前那 4 行，原封不動寫死在這裡當正控制（對著 HEAD 的正控制一 commit 就會腐爛）。
OLD_CF_BLOCK = "\n".join([
    "for _w in (3.5, 14, 25):  # Cloudflare 盤查自動重試（偶發互動式 Turnstile：多等幾輪通常自動放行）",
    "    time.sleep(_w)",
    "    try:",
    "        if pg.evaluate(\"async()=>{const r=await fetch('/v1/esport/soloq/top-teams');return r.status;}\") == 200: break",
    "    except Exception: pass",
])


def grab_block(src):
    """把 `for _w in (...)` 那 4~5 行連同它前面的判斷抽出來（到 `except Exception: pass` 為止）。"""
    lines = src.splitlines()
    i = [n for n, l in enumerate(lines) if l.strip().startswith("for _w in (")]
    if len(i) != 1:
        return None
    a = i[0]
    b = a
    while b < len(lines) and "except Exception: pass" not in lines[b]:
        b += 1
    return textwrap.dedent("\n".join(lines[a:b + 1]))


class FakeTime(object):
    def __init__(self):
        self.slept = []

    def sleep(self, s):
        self.slept.append(s)


class PingPage(object):
    """回應序列；'raise' 代表這一次 evaluate 丟例外。"""

    def __init__(self, seq):
        self.seq = list(seq)
        self.asked = 0

    def evaluate(self, js, arg=None):
        self.asked += 1
        v = self.seq.pop(0) if self.seq else 200
        if v == "raise":
            raise RuntimeError("cf")
        return v


def run_block(block, seq):
    t, pg = FakeTime(), PingPage(seq)
    exec(compile(block, "<cf-block>", "exec"), {"time": t, "pg": pg})
    return t.slept, pg.asked


def test_cf_block():
    cur = {}
    for fn in CF_FILES:
        src = io.open(os.path.join(HERE, fn), encoding="utf-8").read()
        b = grab_block(src)
        chk("C0 %s 抽得到等待區塊" % fn, b is not None)
        cur[fn] = b
    uniq = set(v for v in cur.values() if v)
    chk("C1 四支的等待區塊逐字相同（不會只修好三支）", len(uniq) == 1,
        "有 %d 種寫法" % len(uniq))

    block = cur["fetch_soloq_year.py"]
    slept, asked = run_block(block, [200])
    chk("C2 第一次就 200 ⇒ 一秒都不睡", slept == [], slept)
    chk("C3 第一次就 200 ⇒ 只問一次", asked == 1, asked)

    slept, asked = run_block(block, [403, 200])
    chk("C4 第一次沒過 ⇒ 睡 3.5 再問", slept == [3.5] and asked == 2, (slept, asked))

    slept, asked = run_block(block, [403, 403, 200])
    chk("C5 第二次沒過 ⇒ 階梯 3.5→14", slept == [3.5, 14] and asked == 3, (slept, asked))

    slept, asked = run_block(block, [403, 403, 403, 403])
    chk("C6 一路沒過 ⇒ 3.5/14/25 全走完就放棄", slept == [3.5, 14, 25] and asked == 4, (slept, asked))

    slept, asked = run_block(block, ["raise", 200])
    chk("C7 evaluate 丟例外不會炸、會繼續等", slept == [3.5] and asked == 2, (slept, asked))

    # 正控制：HEAD 那版跑同一套，必須紅在 C2（證明這條測試量得到差別）
    # 正控制**不要對著 HEAD**：改動一 commit 進去 HEAD 就是新版，這條會當場翻紅
    # （fetch_soloq_ladder_test.py 就是這樣在 #84 commit 之後變成「37 通過／4 失敗」的）。
    # 所以把改動前那 4 行原封不動寫死在這裡，永遠不會腐爛。
    oslept, oasked = run_block(OLD_CF_BLOCK, [200])
    chk("C8 正控制：舊寫法第一次就 200 也先睡 3.5", oslept == [3.5] and oasked == 1, (oslept, oasked))
    chk("C9 正控制：舊寫法與現行不是同一段", OLD_CF_BLOCK != block)
    oslept, oasked = run_block(OLD_CF_BLOCK, [403, 403, 403, 403])
    chk("C10 正控制：舊寫法的階梯也是 3.5/14/25（只差在第一次要不要先睡）",
        oslept == [3.5, 14, 25] and oasked == 3, (oslept, oasked))


def main():
    print("fetch_soloq_year 沙盒測試（不連網、不開瀏覽器）")
    import fetch_soloq_year as fy
    # 沙盒紀律：這支測試不准碰真實輸出。模組層的 OUTDIR／IDX 指著真 repo 是 import 的副作用（沒辦法避開），
    # 所以改成「跑完比對正本一個位元都沒動」，而測試全程只用自己 mkdtemp 出來的目錄、也不呼叫 main()。
    def snap():
        s = []
        for p in (fy.OUTDIR, os.path.dirname(fy.IDX)):
            for fn in sorted(os.listdir(p)) if os.path.isdir(p) else []:
                fp = os.path.join(p, fn)
                if os.path.isfile(fp):
                    s.append((fp, os.path.getsize(fp), os.path.getmtime(fp)))
        return s
    before = snap()
    test_key_of_file(fy)
    test_role_counts(fy)
    test_cf_block()
    chk("Z1 正本（soloq_matches／根目錄）一個位元都沒動", snap() == before)
    print("通過 %d／失敗 %d" % (len(OK), len(BAD)))
    if BAD:
        print("失敗：" + "、".join(BAD))
    return 1 if BAD else 0


if __name__ == "__main__":
    sys.exit(main())
