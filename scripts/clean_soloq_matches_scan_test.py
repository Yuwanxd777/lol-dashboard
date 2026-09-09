# -*- coding: utf-8 -*-
"""clean_soloq_matches 掃描快路徑（fast_rids）的測試（2026-09-09 #86）。

#86 把掃描階段從「423 個檔 252MB 全部 json.loads」改成「bytes 上正則抓 rid＋檔頭解 key」，
真的要動的檔才整檔讀回來。這一支守住三件事：

  1. **src 的 rid 不可以算進場次**（`src.acc[].rid` 是抓取來源，不是比賽）——算進去
     ridmap 就多出假場次，判定二條件⑤（A 檔不多於 B 檔）會判錯。
  2. **邊界對不上一定要退回整檔解析**，不可以硬猜著刪比賽。
  3. **快路徑真的沒有整檔解析**：正例是「matches 裡塞一段不合法 JSON」的檔——
     整檔解析會爆（舊版會印『略過』並整個檔跳過），快路徑照樣掃得到 key 與 rid。
     把快路徑拿掉，這一條當場紅。

沙盒接管 clean_soloq_matches 的每一個外部證據來源（同 soloq_disowned_test 的 EVIDENCE 清單）；
最後 Z1 驗證真實 repo 的 soloq_matches／帳號檔一個位元都沒動。

用法：  python scripts/clean_soloq_matches_scan_test.py
"""
import collections
import io
import json
import os
import shutil
import sys
import tempfile

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import soloq_disowned as D  # noqa: E402
import soloq_acc_history as H  # noqa: E402
import clean_soloq_matches as C  # noqa: E402

FAIL = []
REAL_OUTDIR, REAL_ACC, REAL_LOGP = C.OUTDIR, C.ACCOUNTS, C.LOGP
REAL_DPATH, REAL_HROOT, REAL_HCACHE = D.PATH, H.ROOT, H.CACHE
EVIDENCE = [(C, "OUTDIR"), (C, "ACCOUNTS"), (C, "LOGP"), (D, "PATH"), (H, "ROOT"), (H, "CACHE")]


def ck(name, got, want):
    if got == want:
        print("  ✓ %s" % name)
    else:
        print("  ✗ %s\n     實際 %r\n     預期 %r" % (name, got, want))
        FAIL.append(name)


def raises(name, fn):
    try:
        fn()
    except Exception:
        print("  ✓ %s" % name)
        return
    print("  ✗ %s（沒有丟例外）" % name)
    FAIL.append(name)


def _game(rid, t):
    return {"t": t, "rid": rid, "c": "Ahri", "w": True}


def _write(tmp, fn, text):
    fp = os.path.join(tmp, fn)
    io.open(fp, "w", encoding="utf-8").write(text)
    return fp


def _dump(key, data, sep=None):
    kw = {"ensure_ascii": False}
    if sep:
        kw["separators"] = sep
    return "window.__sqLoad(%s,%s);\n" % (json.dumps(key, **kw), json.dumps(data, **kw))


# ── ① fast_rids 單元 ─────────────────────────────────────────────────────
def t_fast():
    print("① fast_rids：拿 key 與 rid 次數，不解析整檔")
    tmp = tempfile.mkdtemp(prefix="csm86_")
    data = {"role": "MIDDLE",
            "matches": [_game("A#1", 1), _game("A#1", 2), _game("b#2", 3), _game("我鎚石#7", 4)],
            # src.acc 的 rid 跟比賽無關；切錯邊界就會多算 2 場（其中一隻還是別人的）
            "src": {"v": 1, "acc": [{"pu": "x", "rid": "A#1"}, {"pu": "y", "rid": "OTHER#9"}]}}
    fp = _write(tmp, "p1.js", _dump("T|P", data))
    key, cnt = C.fast_rids(fp)
    ck("key 正確", key, "T|P")
    ck("rid 次數正確、且 src 的 rid 沒被算進去",
       dict(cnt), {"a#1": 2, "b#2": 1, "我鎚石#7": 1})
    ck("跟整檔解析算出來的一字不差", dict(cnt), dict(C.slow_rids(C.read_file(fp)[1])))

    # json.dumps 預設分隔符是 ", " ／ ": "，fetch 端有的用 (",", ":")；兩種都要吃得下
    fp2 = _write(tmp, "p2.js", _dump("T|P", data, sep=(",", ":")))
    ck("src 前後沒有空白的寫法也對", dict(C.fast_rids(fp2)[1]), {"a#1": 2, "b#2": 1, "我鎚石#7": 1})

    nosrc = {"role": "TOP", "matches": [_game("z#3", 9)]}
    fp3 = _write(tmp, "p3.js", _dump("T|Q", nosrc))
    ck("沒有 src 的檔（matches 是最後一個鍵）", C.fast_rids(fp3), ("T|Q", collections.Counter({"z#3": 1})))

    esc = {"role": "TOP", "matches": [_game('a"b#t', 1), _game("", 2), _game(None, 3)]}
    fp4 = _write(tmp, "p4.js", _dump("T|R", esc))
    ck("rid 含跳脫引號讀得對、空 rid 與沒有 rid 不計", dict(C.fast_rids(fp4)[1]), {'a"b#t': 1})
    ck("空 rid 的行為跟整檔解析一致", dict(C.fast_rids(fp4)[1]), dict(C.slow_rids(C.read_file(fp4)[1])))

    raises("前綴不是 __sqLoad ⇒ 例外", lambda: C.fast_rids(_write(tmp, "p5.js", '{"a":1}')))
    raises("結尾多接東西（邊界對不上）⇒ 例外",
           lambda: C.fast_rids(_write(tmp, "p6.js", _dump("T|P", data).rstrip() + "\nfoo();\n")))
    raises("matches 不是陣列收尾（鍵序被換過）⇒ 例外",
           lambda: C.fast_rids(_write(tmp, "p7.js",
                                      _dump("T|P", {"matches": [_game("a#1", 1)], "role": "MID"}))))
    raises("檔頭第一個值不是字串 key ⇒ 例外",
           lambda: C.fast_rids(_write(tmp, "p8.js", "window.__sqLoad(123,{\"matches\": []});\n")))
    shutil.rmtree(tmp, ignore_errors=True)


# ── ② 沙盒 e2e：保底路徑與「沒有整檔解析」的證據 ──────────────────────────
def _sandbox(texts, accounts):
    tmp = tempfile.mkdtemp(prefix="csm86e_")
    out = os.path.join(tmp, "soloq_matches")
    os.makedirs(out)
    for fn, txt in texts.items():
        io.open(os.path.join(out, fn), "w", encoding="utf-8").write(txt)
    accp = os.path.join(tmp, "acc.json")
    io.open(accp, "w", encoding="utf-8").write(json.dumps(accounts, ensure_ascii=False))
    disp = os.path.join(tmp, "dis.json")
    io.open(disp, "w", encoding="utf-8").write("[]")
    histp = os.path.join(tmp, "hist.json")
    io.open(histp, "w", encoding="utf-8").write(json.dumps({"commits": ["sandbox"], "rid": {}}))
    C.OUTDIR, C.ACCOUNTS, C.LOGP = out, accp, os.path.join(tmp, "log.json")
    D.PATH, H.ROOT, H.CACHE = disp, tmp, histp
    return tmp, out


def _run(argv):
    old, buf = sys.argv, io.StringIO()
    sys.argv = ["clean"] + argv
    real = sys.stdout
    sys.stdout = buf
    try:
        C.main()
    finally:
        sys.argv, sys.stdout = old, real
    return buf.getvalue()


def _left(out, fn):
    fp = os.path.join(out, fn)
    return None if not os.path.exists(fp) else len(C.read_file(fp)[1]["matches"])


def t_e2e():
    print("② 沙盒 e2e：壞 JSON 的檔照樣掃得動（＝快路徑真的沒整檔解析）")
    acc = [{"team": "T%d" % i, "player": "P%d" % i, "riotId": "filler%d#000" % i} for i in range(320)]
    acc.append({"team": "AA", "player": "Real", "riotId": "mine#kr1"})
    # p1：matches 裡有一段**不合法的 JSON**（01 前導零）⇒ 整檔解析必爆；但它是**乾淨的**
    #     （rid 就是本人的帳號）。舊版（掃描階段整檔解析）會印「略過 p1.js」並算成 1 個讀不動；
    #     新版快路徑只掃 "rid":"…" ⇒ 掃得到、判乾淨、連讀都不用讀 ⇒ 0 個讀不動。
    broken_clean = ('window.__sqLoad("AA|Real",{"role": "TOP", "matches": ['
                    '{"t": 1, "d": 01, "rid": "mine#kr1"}, {"t": 2, "rid": "mine#kr1"}'
                    ']});\n')
    dirty = _dump("BB|Other", {"role": "MID", "matches": [_game("mine#kr1", 5)]})
    tmp, out = _sandbox({"p1.js": broken_clean, "p2.js": dirty}, acc)
    raw_before = io.open(os.path.join(out, "p1.js"), encoding="utf-8").read()
    txt = _run(["--apply"])
    ck("正例：壞 JSON 的乾淨檔照樣掃得動（不是『略過』）", "略過 p1.js" in txt, False)
    ck("正例：結論行 0 個讀不動（舊版會是 1 個）", "掃 2 個逐場檔（0 個讀不動）" in txt, True)
    ck("反例：乾淨檔一個位元沒動",
       io.open(os.path.join(out, "p1.js"), encoding="utf-8").read(), raw_before)
    ck("對照：同一輪的髒檔照樣刪光刪檔", _left(out, "p2.js"), None)
    shutil.rmtree(tmp, ignore_errors=True)

    print("②b 掃到髒 rid 卻整檔讀不回來 ⇒ 只警告、不動那個檔")
    broken_dirty = ('window.__sqLoad("BB|Other",{"role": "TOP", "matches": ['
                    '{"t": 1, "d": 01, "rid": "mine#kr1"}]});\n')
    tmpb, outb = _sandbox({"p1.js": broken_dirty}, acc)
    txtb = _run(["--apply"])
    ck("印出『掃到髒 rid 卻讀不回來』", "掃到髒 rid 卻讀不回來" in txtb, True)
    ck("檔還在（不會拿猜的內容去覆寫）", os.path.exists(os.path.join(outb, "p1.js")), True)
    shutil.rmtree(tmpb, ignore_errors=True)

    print("③ 邊界對不上 ⇒ 退回整檔解析（不是放過它）")
    # 鍵序被換過（matches 不是最後一個鍵、也沒有 src）⇒ fast_rids 一定丟例外；
    # 但 `window.__sqLoad(…);` 的外框是好的 ⇒ 保底的整檔解析讀得到 ⇒ 照樣清掉。
    bad_edge = _dump("BB|Other", {"matches": [_game("mine#kr1", 1)], "role": "TOP"})
    raises("這個檔的快路徑確實失敗", lambda: C.fast_rids(_write(tempfile.mkdtemp(prefix="csm86b_"),
                                                          "x.js", bad_edge)))
    tmp2, out2 = _sandbox({"p1.js": bad_edge}, acc)
    txt2 = _run(["--apply"])
    ck("正例：保底路徑照樣刪掉別人的 1 場", _left(out2, "p1.js"), None)
    ck("而且沒有被當成讀不動", "1 個讀不動" in txt2, False)
    shutil.rmtree(tmp2, ignore_errors=True)

    print("④ 真的讀不動的檔仍然只是略過，不會讓整支爆掉")
    tmp3, out3 = _sandbox({"p1.js": "not a sqLoad file\n"}, acc)
    txt3 = _run(["--apply"])
    ck("讀不動的檔算進『讀不動』", "掃 1 個逐場檔（1 個讀不動）" in txt3, True)
    ck("檔還在（沒被刪）", os.path.exists(os.path.join(out3, "p1.js")), True)
    shutil.rmtree(tmp3, ignore_errors=True)


# ── ⑤ 隔離 ───────────────────────────────────────────────────────────────
def t_isolate():
    print("⑤ 沙盒隔離：模組層沒有任何路徑常數還指著真實 repo")
    tmp, out = _sandbox({}, [])
    root = os.path.dirname(HERE)
    leak = [n for m, n in EVIDENCE if os.path.abspath(getattr(m, n)).startswith(os.path.abspath(root) + os.sep)]
    ck("六個證據來源全部指進 tmp", leak, [])
    shutil.rmtree(tmp, ignore_errors=True)


def t_untouched(snap):
    print("Z1 真實 repo 一個位元都沒動")
    now = _snap()
    ck("soloq_matches 的 mtime／大小全部沒變", now["files"], snap["files"])
    ck("帳號檔沒被動到", now["acc"], snap["acc"])


def _snap():
    fs = {}
    if os.path.isdir(REAL_OUTDIR):
        for fn in sorted(os.listdir(REAL_OUTDIR)):
            fp = os.path.join(REAL_OUTDIR, fn)
            fs[fn] = (os.path.getmtime(fp), os.path.getsize(fp))
    acc = (os.path.getmtime(REAL_ACC), os.path.getsize(REAL_ACC)) if os.path.exists(REAL_ACC) else None
    return {"files": fs, "acc": acc}


def main():
    snap = _snap()
    t_fast()
    t_e2e()
    t_isolate()
    C.OUTDIR, C.ACCOUNTS, C.LOGP = REAL_OUTDIR, REAL_ACC, REAL_LOGP
    D.PATH, H.ROOT, H.CACHE = REAL_DPATH, REAL_HROOT, REAL_HCACHE
    t_untouched(snap)
    print("\n%s（失敗 %d 條）" % ("全部通過" if not FAIL else "有失敗：" + "、".join(FAIL), len(FAIL)))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
