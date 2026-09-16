# -*- coding: utf-8 -*-
"""fetch_data.merge_stats ＋ fetch_wiki_stats 新配對鍵（不含開賽時分）的沙盒測試（2026-09-17 精進迴圈 #175）。

背景：舊鍵含「開賽時間到分鐘」，80fabac2 把 MH 來源局改成合成時間 ⇒ 2013～2016 逐選手數據從 08-01 起整批落空。
新鍵 B 日+局號+選手+英雄 → C 日+選手+英雄 → C1 前後一天；wiki 側唯一才填、歧義不填。

沙盒：兩個模組所有指著真實 repo 的字串常數改指暫存目錄（assert 一個不剩）；socket connect 封死並記帳；
合成的 lpstats／lpgames 月快取與年度表，選手名 Zzprobe* 是真 repo 不可能有的證據。
正控制：釘 754530a3（改動前）的兩支原始碼 ⇒ 同一份「時間被重算過」的表一格都填不到；
換回真時間時舊版填得到、但局號顛倒那局會配錯（證明舊版不是崩潰而是行為差異）。
環境變數 MERGESTATS_SRC＝要測的 scripts 目錄（突變測試 autopilot/_m175_mutate.py 用），預設本目錄。

用法：python scripts/fetch_data_mergestats_test.py（約 2 秒，離開碼＝失敗條數>0）
"""
import collections, contextlib, copy, importlib.util, io, json, os, shutil, socket, subprocess, sys, tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
REAL_ROOT = os.path.dirname(HERE)
SRC = os.environ.get("MERGESTATS_SRC") or HERE
OLDREV = "754530a3"
FAILS, PASSES = [], [0]


def ok(name, cond, extra=""):
    if cond:
        PASSES[0] += 1
        print("  ✓ " + name)
    else:
        FAILS.append(name)
        print("  ✗ " + name + ("  " + str(extra) if extra else ""))


def load(name, path):
    sys.path.insert(0, os.path.dirname(path))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m
    finally:
        sys.path.pop(0)


NET_HITS = []


def _blow(self, *a, **k):
    NET_HITS.append(a)
    raise OSError("沙盒封網")


def real_stat():
    out = {}
    for rel in ["csv_cache/wikistats_%d.json" % y for y in (2013, 2014, 2015, 2016)] + \
               ["data/data_%d.js" % y for y in (2013, 2014, 2015, 2016)]:
        p = os.path.join(REAL_ROOT, rel)
        out[rel] = (os.path.getsize(p), os.stat(p).st_mtime_ns) if os.path.exists(p) else None
    return out


def repoint(mod, box):
    """模組層字串常數裡「真實 repo」與「這份原始碼自己的 repo 根」（突變測試時是暫存目錄）一律換成沙盒。
    只換真實 repo 不夠：突變版放在暫存目錄時 ROOT 會是暫存目錄的上一層，第一版就這樣漏接、跑去 %TEMP%/csv_cache 白睡。"""
    roots = sorted({REAL_ROOT, os.path.dirname(os.path.dirname(os.path.abspath(mod.__file__)))}, key=len, reverse=True)
    inbox = lambda v: v.lower().startswith(box.lower() + os.sep) or v.lower() == box.lower()
    for k, v in list(vars(mod).items()):
        if k in ("__file__", "__cached__") or not isinstance(v, str) or inbox(v):
            continue
        for rt in roots:
            if rt.lower() in v.lower():
                i = v.lower().index(rt.lower())
                v = v[:i] + box + v[i + len(rt):]
                setattr(mod, k, v)
                break
    return [k for k, v in vars(mod).items()
            if k not in ("__file__", "__cached__") and isinstance(v, str) and not inbox(v)
            and any(rt.lower() in v.lower() for rt in roots)]


class NetCall(Exception):
    pass


def wrow(nm, ch, dt, gid, k=None, d=None, a=None, g=None):
    return {"nm": nm, "ch": ch, "k": k, "d": d, "a": a, "g": g, "cs": None, "dmg": None, "vs": None,
            "dt": dt, "tm": "T", "gid": gid}


# ── 合成素材 ──────────────────────────────────────────────
WIKI = [
    wrow("ZzprobeAlpha", "Vi", "2013-03-02 09:00:00", "S1_1", 3, 1, 7, 9000),           # ① 時間被重算
    wrow("ZzprobeBeta", "Olaf", "2013-03-03 09:00:00", "S2_1", 2, 8, 5),               # ② 局號顛倒
    wrow("ZzprobeBeta", "Vi", "2013-03-03 09:40:00", "S2_2", 4, 0, 9),
    wrow("ZzprobeGamma", "Ahri", "2013-03-04 09:00:00", "S3_1", 1, 1, 1),              # ③ 同日兩局同英雄
    wrow("ZzprobeGamma", "Ahri", "2013-03-04 15:00:00", "S4_2", 6, 6, 6),
    wrow("ZzprobeNunu", "Nunu &amp; Willump", "2013-03-04 09:00:00", "S3_1", 0, 3, 11),  # ④ 實體
    wrow("ZzprobeDelta", "Lux", "2013-03-05 23:30:00", "S5_1", 5, 2, 8),               # ⑤ ±1 天
    wrow("ZzprobeEps", "Zed", "2013-03-07 10:00:00", "S6_1", 7, 7, 7),                 # ⑥ ±1 天兩邊都有
    wrow("ZzprobeEps", "Zed", "2013-03-09 10:00:00", "S7_1", 8, 8, 8),
    wrow("ZzprobeEps", "Zed", "2013-03-09 14:00:00", "S7b_1", 8, 1, 8),               # 隔天那邊是「局數 2」（整數）
    wrow("ZzprobeFill", "Ezreal", "2013-03-10 09:00:00", "S8_1", 9, 4, 2),             # ⑦ 只填空欄
    wrow("ZzprobeZeta", "Jinx", "2013-03-11 09:00:00", "S9_1", 2, 2, 2),               # ⑧ 重複列
    wrow("ZzprobeZeta", "Jinx", "2013-03-11 09:00:00", "S9_1", 2, 2, 2),
    wrow("ZzprobeEta", "Leona", "2013-03-12 15:00:00", "SB_2", 1, 5, 12),              # ⑨ 沒數據的列也算一局
    wrow("ZzprobeEta", "Leona", "2013-03-12 09:00:00", "SA_1"),                        #    （有數據那局排前面：「不驗唯一」會拿到它而填錯）
    wrow("ZzprobePatch", "Annie", "2013-03-13 09:00:00", "SC_1", 3, 3, 3),             # ⑪ patch 整列欄
]
PMAP_GAMES = [{"gid": "SC_1", "pt": "3.3", "dt": "2013-03-13 09:00:00"}]

HDR = ["league", "split", "date", "game", "result", "patch", "participantid",
       "blue_playername", "blue_teamname", "blue_champion", "blue_kills", "blue_deaths", "blue_assists", "blue_totalgold",
       "red_playername", "red_teamname", "red_champion", "red_kills", "red_deaths", "red_assists", "red_totalgold"]


def drow(date, game, nm, ch, k="", d="", a="", g="", patch=""):
    r = {h: "" for h in HDR}
    r.update({"league": "ZZ", "split": "S", "date": date, "game": game, "patch": patch,
              "blue_playername": nm, "blue_champion": ch, "blue_kills": k, "blue_deaths": d, "blue_assists": a,
              "blue_totalgold": g})
    return [r[h] for h in HDR]


def table(fake_time=True):
    t = (lambda real, fake: fake if fake_time else real)
    return [HDR[:],
            drow(t("2013-03-02 09:00:00", "2013-03-02 00:11:00"), "1", "ZzprobeAlpha", "Vi"),          # 1
            drow(t("2013-03-03 09:00:00", "2013-03-03 00:11:00"), "1", "ZzprobeBeta", "Vi"),           # 2 局號顛倒
            drow(t("2013-03-03 09:40:00", "2013-03-03 00:21:00"), "2", "ZzprobeBeta", "Olaf"),         # 3
            drow("2013-03-04 00:31:00", "3", "ZzprobeGamma", "Ahri"),                                  # 4 歧義
            drow("2013-03-04 00:11:00", "1", "ZzprobeGamma", "Ahri"),                                  # 5 B 勝過 C 歧義
            drow("2013-03-04 00:11:00", "1", "ZzprobeNunu", "Nunu & Willump"),                         # 6
            drow("2013-03-06 00:11:00", "1", "ZzprobeDelta", "Lux"),                                   # 7 C1
            drow("2013-03-08 00:11:00", "1", "ZzprobeEps", "Zed"),                                     # 8 C1 歧義
            drow("2013-03-10 00:11:00", "1", "ZzprobeFill", "Ezreal", k="99"),                         # 9 只填空
            drow("2013-03-11 00:11:00", "1", "ZzprobeZeta", "Jinx"),                                   # 10 去重
            drow("2013-03-12 00:31:00", "3", "ZzprobeEta", "Leona"),                                   # 11 沒數據列算局
            drow("2013-03-13 00:11:00", "1", "ZzprobePatch", "Annie"),                                 # 12 patch
            drow("2013-03-20 00:11:00", "1", "ZzprobeNobody", "Teemo")]                                # 13 沒有


def kda(tb, i):
    h = {n: j for j, n in enumerate(tb[0])}
    r = tb[i]
    return tuple(r[h["blue_" + c]] for c in ("kills", "deaths", "assists"))


def seed_months(box, rows, games):
    raw, graw = os.path.join(box, "csv_cache", "lpstats"), os.path.join(box, "csv_cache", "lpgames")
    os.makedirs(raw, exist_ok=True)
    os.makedirs(graw, exist_ok=True)
    months = [(2012, m) for m in (10, 11, 12)] + [(2013, m) for m in range(1, 13)]
    for yy, m in months:
        name = "%d-%02d.json" % (yy, m)
        json.dump(rows if (yy, m) == (2013, 3) else [], io.open(os.path.join(raw, name), "w", encoding="utf-8"))
        json.dump(games if (yy, m) == (2013, 3) else [], io.open(os.path.join(graw, name), "w", encoding="utf-8"))


def run_merge(fd, tb):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out = fd.merge_stats(2013, tb)
    return out, buf.getvalue()


def main():
    before = real_stat()
    box = tempfile.mkdtemp(prefix="m175_ms_")
    try:
        fd = load("ms_fetch_data", os.path.join(SRC, "fetch_data.py"))
        W = load("ms_fetch_wiki_stats", os.path.join(SRC, "fetch_wiki_stats.py"))
        socket.socket.connect = _blow
        socket.socket.connect_ex = _blow
        print("[0] 沙盒隔離")
        left = repoint(fd, box) + repoint(W, box)
        ok("0a 兩個模組沒有字串常數還指著真實 repo", not left, left)
        ok("0b fd.CACHE_DIR／W.CACHE／W.RAW／W.GRAW 都在沙盒",
           all(x.startswith(box) for x in (fd.CACHE_DIR, W.CACHE, W.RAW, W.GRAW)), (fd.CACHE_DIR, W.RAW))
        called = []

        def _no_fetch(*a, **k):
            called.append(a)
            raise NetCall("快取沒命中：build 想抓 %r" % (a[:2],))
        W.fetch_range = _no_fetch
        seed_months(box, WIKI, PMAP_GAMES)

        print("[1] fetch_wiki_stats.build 產新格式（0 請求）")
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                W.build(2013)
        except NetCall as e:
            print("  （build 中斷：%s）" % e)
        p = os.path.join(W.CACHE, "wikistats_2013.json")
        S = json.load(io.open(p, encoding="utf-8")) if os.path.exists(p) else {}
        ok("1a 檔頭 _v == 2", S.get("_v") == 2, S.get("_v"))
        ok("1b fetch_range 沒被叫（快取齊 ⇒ 0 請求）", not called, len(called))
        ok("1c 鍵不含開賽時分（D|日|…，沒有 09:00 這種）", all(k == "_v" or (k.startswith("D|") and ":" not in k) for k in S), [k for k in S if ":" in k][:3])
        ok("1d 重複列去重後仍唯一（Zeta C 鍵是 dict）", isinstance(S.get("D|2013-03-11|*|zzprobezeta|jinx"), dict))
        ok("1e 同日兩局同英雄 ⇒ C 鍵是局數 2", S.get("D|2013-03-04|*|zzprobegamma|ahri") == 2, S.get("D|2013-03-04|*|zzprobegamma|ahri"))
        ok("1f 沒數據的列也算局數（Eta C 鍵＝2）", S.get("D|2013-03-12|*|zzprobeeta|leona") == 2, S.get("D|2013-03-12|*|zzprobeeta|leona"))
        ok("1g 英雄名解實體（nunuwillump，不是 nunuampwillump）", "D|2013-03-04|*|zzprobenunu|nunuwillump" in S and not any("nunuamp" in k for k in S))

        print("[2] merge_stats 對「時間被重算過」的表")
        tb, log = run_merge(fd, table(True))
        ok("2a ① 時間重算仍配得到（B）", kda(tb, 1) == ("3", "1", "7"), kda(tb, 1))
        h = {n: j for j, n in enumerate(HDR)}
        ok("2b ① 金錢一起補", tb[1][h["blue_totalgold"]] == "9000", tb[1][h["blue_totalgold"]])
        ok("2c ② 局號顛倒：Vi 那列拿 Vi 那局（4/0/9）", kda(tb, 2) == ("4", "0", "9"), kda(tb, 2))
        ok("2d ② 局號顛倒：Olaf 那列拿 Olaf 那局（2/8/5）", kda(tb, 3) == ("2", "8", "5"), kda(tb, 3))
        ok("2e ③ 同日兩局同英雄、局號也對不上 ⇒ 不填", kda(tb, 4) == ("", "", ""), kda(tb, 4))
        ok("2f ③ 局號對得上 ⇒ B 唯一照填（不被 C 的歧義擋掉）", kda(tb, 5) == ("1", "1", "1"), kda(tb, 5))
        ok("2g ④ Nunu &amp; Willump 配得到", kda(tb, 6) == ("0", "3", "11"), kda(tb, 6))
        ok("2h ⑤ 隔天（UTC 23:30 vs 我們隔天）C1 配得到", kda(tb, 7) == ("5", "2", "8"), kda(tb, 7))
        ok("2i ⑥ 前一天一局＋後一天兩局 ⇒ 歧義不填", kda(tb, 8) == ("", "", ""), kda(tb, 8))
        ok("2j ⑦ 已有值的 kills 不動、空的 deaths／assists 補上", kda(tb, 9) == ("99", "4", "2"), kda(tb, 9))
        ok("2k ⑧ 重複列不算兩局 ⇒ 照填", kda(tb, 10) == ("2", "2", "2"), kda(tb, 10))
        ok("2l ⑨ 沒數據的那局也算 ⇒ 歧義不填", kda(tb, 11) == ("", "", ""), kda(tb, 11))
        ok("2m ⑪ patch 整列欄補上（3.3 ⇒ 13.03）", tb[12][h["patch"]] == "13.03", tb[12][h["patch"]])
        ok("2n ⑬ 沒有的照空", kda(tb, 13) == ("", "", ""))
        ok("2o 列數不變", len(tb) == len(table(True)))
        ok("2p 日誌印出 B／C／C1／歧義／沒有 的計數行", "逐選手數據（不含時分配對）：B 6／C 2／C1 1／歧義不填 3／沒有 1" in log, log.strip()[:200])
        ok("2q 有對上就不印 ⚠", "⚠" not in log, log)

        print("[3] 舊格式檔與「一格都沒對上」都要出聲")
        json.dump({"2013-03-02 09:00|1|zzprobealpha": {"kills": "3"}}, io.open(p, "w", encoding="utf-8"))
        tb3, log3 = run_merge(fd, table(True))
        ok("3a 舊格式 ⇒ 表一格沒動", tb3 == table(True))
        ok("3b 舊格式 ⇒ 印 ⚠ 並指名要重跑 fetch_wiki_stats", "舊格式" in log3 and "fetch_wiki_stats.py --years 2013" in log3, log3)
        json.dump({"_v": 2, "D|1999-01-01|*|x|y": {"kills": "1"}}, io.open(p, "w", encoding="utf-8"))
        tb4, log4 = run_merge(fd, table(True))
        ok("3c kills 空著卻一個都沒對上 ⇒ 印 ⚠", "一個都沒對上" in log4, log4)
        ok("3d 那種情況表也沒動", tb4 == table(True))

        print("[4] 正控制：釘 %s 的舊版" % OLDREV)
        old = os.path.join(box, "old")
        os.makedirs(old)
        for f in ("fetch_data.py", "fetch_wiki_stats.py"):
            src = subprocess.run(["git", "show", "%s:scripts/%s" % (OLDREV, f)], cwd=REAL_ROOT, capture_output=True).stdout
            open(os.path.join(old, f), "wb").write(src)
        ofd = load("ms_old_fetch_data", os.path.join(old, "fetch_data.py"))
        oW = load("ms_old_fetch_wiki_stats", os.path.join(old, "fetch_wiki_stats.py"))
        obox = os.path.join(box, "oldbox")
        os.makedirs(obox)
        ok("4a 舊版兩模組也接管乾淨", not (repoint(ofd, obox) + repoint(oW, obox)))
        oW.fetch_range = _no_fetch
        seed_months(obox, WIKI, PMAP_GAMES)
        with contextlib.redirect_stdout(io.StringIO()):
            oW.build(2013)
        ok("4b 舊版沒有 stats_pick／index_rows（真的是改動前那版）", not hasattr(ofd, "stats_pick") and not hasattr(oW, "index_rows"))
        otb, _ = run_merge(ofd, table(True))
        ok("4c 舊版對時間被重算的表：一格 kills 都填不到（就是這次的病）",
           all(kda(otb, i)[0] in ("", "99") for i in range(1, len(otb))), [kda(otb, i) for i in range(1, 4)])
        rtb, _ = run_merge(ofd, table(False))
        ok("4d 舊版對真時間的表：① 填得到（不是崩潰，是配對鍵的行為差異）", kda(rtb, 1) == ("3", "1", "7"), kda(rtb, 1))
        ok("4e 舊版對真時間的表：② 局號顛倒那列配到別隻英雄那局（2/8/5）", kda(rtb, 2) == ("2", "8", "5"), kda(rtb, 2))
        with contextlib.redirect_stdout(io.StringIO()):
            W.build(2013)
        ntb, _ = run_merge(fd, table(False))
        ok("4f 新版對真時間的表：② 仍是 Vi 那局（4/0/9）", kda(ntb, 2) == ("4", "0", "9"), kda(ntb, 2))

        print("[5] 出口")
        ok("5a 網路 0 次", not NET_HITS, len(NET_HITS))
        n0 = len(NET_HITS)
        try:
            socket.create_connection(("127.0.0.1", 9), timeout=1)
        except OSError:
            pass
        ok("5c 正控制：封網保險絲自己會擋、會記帳", len(NET_HITS) == n0 + 1, len(NET_HITS) - n0)
        del NET_HITS[n0:]
    finally:
        shutil.rmtree(box, ignore_errors=True)
    after = real_stat()
    ok("5b 真實 wikistats_2013～2016.json／data_2013～2016.js 的 size＋mtime_ns 沒動", before == after,
       [k for k in before if before[k] != after.get(k)])
    print("\n%d 過／%d 敗" % (PASSES[0], len(FAILS)))
    for f in FAILS:
        print("  ---- 失敗：" + f)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
