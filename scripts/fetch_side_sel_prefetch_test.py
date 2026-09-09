# -*- coding: utf-8 -*-
"""fetch_side_sel 快取頁併發預讀（#88）的沙盒測試。

要擋住的失誤（照重要性排）：
 ①**進行中的賽事被預讀的舊快取餵回去** ⇒ 那一輪新打的局全部不見（這支腳本最嚴重的失效模式，
   2026-08-03 使用者親自點名過「選邊要每次更新都去抓」）。
 ② 預讀的內容跟循序讀不一樣（編碼、換行、截斷）。
 ③ 預讀吃到不合格的快取（< 5000 位元組）而繞過重抓。
 ④ `--read-jobs=1` 退不回循序。
 ⑤ 預讀把 `_PRE` 留著沒清 ⇒ 同一支跑第二輪拿到上一輪的頁面。

**沙盒紀律**（CLAUDE.md 2026-09-07 #52）：模組層每一個「證據來源」都要接管——
`CACHE`（快取目錄）與 `MH.opener`（唯一的對外出口）都換成沙盒版；跑完 assert
模組的 CACHE 還指著沙盒、且真實 `csv_cache/sidesel` 與 `side_sel.js` 一個位元沒動。
每一條都配「正例會動」的對照，避免整組永遠綠。

用法：python scripts\\fetch_side_sel_prefetch_test.py
"""
import hashlib, io, json, os, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import fetch_side_sel as M

OK = [0]
BAD = [0]


def ck(cond, msg):
    if cond:
        OK[0] += 1
    else:
        BAD[0] += 1
        print("  ✗ " + msg)


def md5dir(d):
    h = hashlib.md5()
    for n in sorted(os.listdir(d)):
        p = os.path.join(d, n)
        if os.path.isfile(p):
            h.update(n.encode("utf-8"))
            h.update(open(p, "rb").read())
    return h.hexdigest()


REAL_CACHE = M.CACHE
REAL_OUT = os.path.join(ROOT, "side_sel.js")
real_cache_md5 = md5dir(REAL_CACHE) if os.path.isdir(REAL_CACHE) else "(無)"
real_out_md5 = hashlib.md5(open(REAL_OUT, "rb").read()).hexdigest() if os.path.exists(REAL_OUT) else "(無)"

box = tempfile.mkdtemp(prefix="sidesel_pf_")
M.CACHE = os.path.join(box, "sidesel")
os.makedirs(M.CACHE)

# ── 沙盒素材：假的快取頁（內容可辨識，含非 ASCII 與 CRLF，驗編碼／換行不被動到）─────
PAGES = ["LCK/2026 Season/Rounds 1-2", "LPL/2026 Season/Split 3", "2026 Mid-Season Invitational",
         "LEC/2026 Season/Summer Season", "CBLOL/2026 Season/Split 2"]
BODY = {}


def seed():
    """把沙盒快取重新鋪一次。

    ⚠ 每一節開頭都要鋪：page_html 抓到新頁面時**會覆寫快取檔**，上一節跑完素材就不是原樣了
    （第一版沒鋪 ⇒ 第二節只讀到 4 頁、KeyError 才發現）。
    """
    for ov in PAGES:
        body = ("<html>快取版本 舊 · %s · Ø漢字" % ov) + ("x" * 6000) + "</html>"
        BODY[ov] = body
        io.open(M.cache_path(ov), "w", encoding="utf-8", newline="").write(body)


def disk_read(ov):
    """比對用的**唯一正確答案**＝這支腳本原本讀快取的方式（文字模式）。

    不可以拿「寫進去的原文」當答案：文字模式讀會做換行轉換（CRLF → LF），
    那是預讀前就有的既有行為；預讀只要跟它**逐字相同**就對了。
    """
    return open(M.cache_path(ov), encoding="utf-8").read()


seed()

# 太小的快取（③）：不該被預讀，也不該被 page_html 當成有效快取
SMALL = "LCS/2026 Season/Summer Season"
io.open(M.cache_path(SMALL), "w", encoding="utf-8", newline="").write("<html>tiny</html>")

# ── 接管唯一的對外出口：MH.opener（page_html 走 api.php）──────────────────────
NET = []


class _Resp(object):
    def __init__(self, b):
        self.b = b

    def read(self):
        return self.b


class _Opener(object):
    def open(self, req, timeout=0):
        url = req.get_full_url() if hasattr(req, "get_full_url") else str(req)
        NET.append(url)
        return _Resp(json.dumps({"parse": {"text": "<html>剛抓的 新 · %d</html>" % len(NET)}}).encode("utf-8"))


M.MH.opener = lambda: _Opener()
M.GAP = 0.0            # 測試不要真的睡 3 秒（節流本身另有其他測試覆蓋）
M._LAST_HIT[0] = 0.0

print("=== ① 進行中的頁不可以被預讀餵回舊快取 ===")
M._PRE.clear()
forced = {PAGES[0], PAGES[1]}
M.prefetch_cached(PAGES, forced)
ck(set(M._PRE) == set(PAGES) - forced, "預讀名單應該只有非強制的 3 頁，實際 %s" % sorted(M._PRE))
h0 = M.page_html(PAGES[0], force=True)
ck("剛抓的 新" in h0, "強制頁必須走網路，拿到的是：%s" % h0[:40])
ck(len(NET) == 1, "強制頁應該送出 1 次請求，實際 %d" % len(NET))
h2 = M.page_html(PAGES[2], force=False)
ck(h2 == disk_read(PAGES[2]), "非強制頁應該拿到預讀的快取內容（逐字＝直接讀磁碟）")
ck("快取版本 舊" in h2, "非強制頁拿到的不是快取內容：%s" % h2[:40])
ck(len(NET) == 1, "非強制頁不該送出請求，累計 %d" % len(NET))

print("=== ②預讀內容 == 循序讀（逐字，含非 ASCII）===")
seed()
M._PRE.clear()
M.READ_JOBS = 8
M.prefetch_cached(PAGES, set())
par = dict(M._PRE)
M._PRE.clear()
M.READ_JOBS = 1
M.prefetch_cached(PAGES, set())
seq = dict(M._PRE)
ck(par == seq, "併發與循序讀到的內容不一致")
ck(len(par) == len(PAGES), "併發應該讀滿 %d 頁，實際 %d" % (len(PAGES), len(par)))
ck(all(par[ov] == disk_read(ov) for ov in PAGES), "預讀的內容跟直接讀磁碟不一致（編碼／換行被動到）")
ck(all("Ø漢字" in par[ov] for ov in PAGES), "非 ASCII 被吃掉了（編碼不對）")
# 正控制：故意改一個檔 ⇒ disk_read 變了、預讀的舊值就該對不上，證明這條比對真的會紅
io.open(M.cache_path(PAGES[0]), "a", encoding="utf-8").write("動過了")
ck(par[PAGES[0]] != disk_read(PAGES[0]), "（正控制）改過檔之後這條比對居然還相等")
seed()

print("=== ③ 不合格的快取（<5000B）不預讀，且照樣會去抓 ===")
seed()
M._PRE.clear()
M.READ_JOBS = 8
M.prefetch_cached(PAGES + [SMALL], set())
ck(SMALL not in M._PRE, "太小的快取不該進預讀名單")
n0 = len(NET)
hs = M.page_html(SMALL, force=False)
ck("剛抓的 新" in hs, "太小的快取應該觸發重抓，實際拿到：%s" % hs[:40])
ck(len(NET) == n0 + 1, "太小的快取應該送出 1 次請求")

print("=== ④ --read-jobs=1 退回循序（不開執行緒池）===")
seed()
import concurrent.futures as _cf
made = [0]
_TPE = _cf.ThreadPoolExecutor


class _Spy(_TPE):
    def __init__(self, *a, **k):
        made[0] += 1
        _TPE.__init__(self, *a, **k)


_cf.ThreadPoolExecutor = _Spy
M._PRE.clear()
M.READ_JOBS = 1
M.prefetch_cached(PAGES, set())
ck(made[0] == 0, "READ_JOBS=1 不該建執行緒池，實際建了 %d 個" % made[0])
ck(len(M._PRE) == len(PAGES), "循序模式也要讀滿 %d 頁，實際 %d" % (len(PAGES), len(M._PRE)))
M._PRE.clear()
M.READ_JOBS = 8
M.prefetch_cached(PAGES, set())
ck(made[0] == 1, "（正控制）READ_JOBS=8 應該建 1 個執行緒池，實際 %d" % made[0])
_cf.ThreadPoolExecutor = _TPE

print("=== ⑤ page_html 取用後要把預讀的頁丟掉（不留著給下一輪）===")
seed()
M._PRE.clear()
M.prefetch_cached(PAGES, set())
before = len(M._PRE)
M.page_html(PAGES[3], force=False)
ck(len(M._PRE) == before - 1, "取用後 _PRE 應該少一頁（%d → %d）" % (before, len(M._PRE)))
ck(PAGES[3] not in M._PRE, "取用過的頁還留在 _PRE")
n1 = len(NET)
again = M.page_html(PAGES[3], force=False)
ck(again == disk_read(PAGES[3]), "第二次取用要退回讀磁碟快取（拿到 %s）" % again[:30])
ck(len(NET) == n1, "第二次取用不該送出請求")

print("=== ⑥ 空名單／全部強制 → 什麼都不做（不炸、不留殘留）===")
seed()
M._PRE.clear()
M.prefetch_cached([], set())
ck(M._PRE == {}, "空名單不該留東西")
M.prefetch_cached(PAGES, set(PAGES))
ck(M._PRE == {}, "全部強制時不該預讀任何頁")

print("=== ⑦ 沙盒紀律：正本一個位元沒動 ===")
ck(M.CACHE.startswith(box), "模組的 CACHE 已經不指著沙盒了：%s" % M.CACHE)
ck(os.path.dirname(M.cache_path(PAGES[0])) == M.CACHE, "cache_path 沒有跟著沙盒走")
now_cache = md5dir(REAL_CACHE) if os.path.isdir(REAL_CACHE) else "(無)"
now_out = hashlib.md5(open(REAL_OUT, "rb").read()).hexdigest() if os.path.exists(REAL_OUT) else "(無)"
ck(now_cache == real_cache_md5, "真實 csv_cache/sidesel 被動到了")
ck(now_out == real_out_md5, "真實 side_sel.js 被動到了")
# 只有沙盒才有的證據（把來源清空不算隔離）：沙盒裡真的存在那幾個檔
ck(all(os.path.exists(M.cache_path(ov)) for ov in PAGES), "沙盒素材不見了（那前面讀到的是哪裡的檔？）")

shutil.rmtree(box, ignore_errors=True)
print("")
print("fetch_side_sel_prefetch_test：%d 過／%d 敗" % (OK[0], BAD[0]))
sys.exit(1 if BAD[0] else 0)
