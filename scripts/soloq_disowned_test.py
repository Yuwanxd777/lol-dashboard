# -*- coding: utf-8 -*-
"""soloq_disowned＋clean_soloq_matches 判定三的單元／整合測試（2026-09-07 #36）。

每一條「不該刪」的反例都配一條同結構「該刪」的正例——只有反例的話，
把判定三整段刪掉測試也會全綠（假綠）。

⚠ 沙盒要接管 **clean_soloq_matches 的每一個外部證據來源**（2026-09-07 #51）。
原本只接管了 OUTDIR／ACCOUNTS／LOGP／剔除名單四個，#37 後來加的判定四卻是拿
**真實 repo 的 git 帳號檔歷史**當證據 ⇒ 沙盒裡那隻 `ice seven zero#0721` 被真實歷史
判給 NIP|Care，反例「別位選手同 rid 的 4 場不動」就長期翻紅（而且測試還會順手寫進
真實的 `csv_cache/soloq_acc_history.json`）。現在 `_sandbox()` 連 `soloq_acc_history`
的 ROOT／CACHE 一起接管，`t_isolate()` 負責在**下一次多一條判定**時先翻紅提醒。

用法：  python scripts/soloq_disowned_test.py
"""
import ast
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
import soloq_acc_history as H  # noqa: E402  判定四的證據來源，沙盒要一起接管
import clean_soloq_matches as C  # noqa: E402

FAIL = []

# clean_soloq_matches 會去讀的外部檔案／目錄常數；沙盒必須把每一個都指進 tmp。
# 多一條判定＝多一個來源時，記得同時更新這裡與 _sandbox()（t_isolate 會擋）。
EVIDENCE = [("C", "OUTDIR"), ("C", "ACCOUNTS"), ("C", "LOGP"),
            ("D", "PATH"), ("H", "ROOT"), ("H", "CACHE")]
# clean_soloq_matches 目前 import 的本地模組（scripts/ 底下的）。soloq_src 只處理
# 傳進去的 dict、不自己開檔，所以它沒有東西要接管。
LOCAL_IMPORTS = ["soloq_acc_history", "soloq_disowned", "soloq_src"]


def ck(name, got, want):
    if got == want:
        print("  ✓ %s" % name)
    else:
        print("  ✗ %s\n     實際 %r\n     預期 %r" % (name, got, want))
        FAIL.append(name)


# ── ① 名單本身 ────────────────────────────────────────────────────────────
def t_list():
    print("① 名單讀寫")
    tmp = tempfile.mkdtemp(prefix="dis_")
    p = os.path.join(tmp, "d.json")
    ck("空檔回空 list", D.load(p), [])
    n = D.add([("ice seven zero#0721", "NIP|Care", "Beichuan", "dpm 掛牌")], p, at="2026-09-07 10:00")
    ck("第一次寫入 1 筆", n, 1)
    ck("同一組 (rid,from) 不重複記", D.add([("ICE SEVEN ZERO#0721", "NIP|Care", "Beichuan", "x")], p), 0)
    ck("同 rid 不同 from 要另記", D.add([("ice seven zero#0721", "XX|Other", "Beichuan", "x")], p), 1)
    ck("rid 空的不記", D.add([("", "NIP|Care", "B", "x")], p), 0)
    ck("from 空的不記", D.add([("aa#1", "", "B", "x")], p), 0)
    idx = D.index(D.load(p))
    hit = D.disowned_from(idx, "icesevenzero#0721", "NIP|Care")   # 逐場檔的 rid 沒有空白
    ck("正例：normalize 後對得上（帳號檔有空白、逐場檔沒有）", bool(hit and hit["owner"] == "Beichuan"), True)
    ck("反例：同 rid 但別位選手的檔不受牽連", D.disowned_from(idx, "icesevenzero#0721", "NIP|Someone"), None)
    ck("反例：沒記過的 rid", D.disowned_from(idx, "nobody#0000", "NIP|Care"), None)
    shutil.rmtree(tmp, ignore_errors=True)


# ── ② 從日誌回填 ──────────────────────────────────────────────────────────
def t_log():
    print("② 從 update_log 解析")
    txt = ("  歸屬複查：26 隻帳號 dpm 選手檔沒列\n"
           "  [歸屬] NIP|Care: ice seven zero#0721 dpm 掛牌是「Beichuan」的帳號 → 剔除\n"
           "  [歸屬] OMG|Starry: May#KR43 dpm 掛牌是「Betty」的帳號 → 剔除\n"
           "  [跨] 同 riotId May#KR43 跨選手 → 留 GZ|Betty（dpm 現行歸屬）、刪 ['OMG|Starry']\n"
           "  [跨] ⚠ 同 riotId aa#1 跨選手 ['A|x', 'B|y']：dpm 確認 0 筆 → 判不出歸屬，保留不動\n")
    got = D.parse_log(txt)
    ck("正例：兩行 [歸屬] ＋一行可判定的 [跨] 都解析到", len(got), 3)
    ck("正例：欄位對", got[0], ("ice seven zero#0721", "NIP|Care", "Beichuan", "dpm 掛牌（日誌回填）"))
    ck("正例：[跨] 取被刪的那一位當 from", (got[2][0], got[2][1], got[2][2]), ("May#KR43", "OMG|Starry", "GZ|Betty"))
    ck("反例：『保留不動』那行不可以被當成剔除",
       [g for g in got if g[1] in ("A|x", "B|y")], [])
    ck("反例：沒有 [歸屬]／[跨] 的日誌解析出 0 筆", D.parse_log("一般日誌\n  soloq 逐場 431 位\n"), [])


# ── ③ 真的接進 clean_soloq_matches（沙盒，不碰真實檔）─────────────────────
def _sandbox(matches_by_file, accounts, disowned, hist=None):
    """建一組沙盒檔案並把 clean 的模組常數指過去，回傳沙盒根目錄。

    `hist`＝判定四的假歷史索引 `{rid: [key…]}`。寫成 soloq_acc_history 的快取格式，
    再把 `H.ROOT` 指到沙盒（不是 git repo ⇒ `snapshots()` 掃不到任何 commit ⇒
    `build()` 只會回這份快取，也不會回頭寫真實的 csv_cache）。
    """
    tmp = tempfile.mkdtemp(prefix="cln_")
    out = os.path.join(tmp, "soloq_matches")
    os.makedirs(out)
    for fn, (key, data) in matches_by_file.items():
        with io.open(os.path.join(out, fn), "w", encoding="utf-8") as f:
            f.write("window.__sqLoad(%s,%s);\n" % (json.dumps(key, ensure_ascii=False),
                                                   json.dumps(data, ensure_ascii=False)))
    accp = os.path.join(tmp, "acc.json")
    io.open(accp, "w", encoding="utf-8").write(json.dumps(accounts, ensure_ascii=False))
    disp = os.path.join(tmp, "dis.json")
    io.open(disp, "w", encoding="utf-8").write(json.dumps(disowned, ensure_ascii=False))
    histp = os.path.join(tmp, "hist.json")
    io.open(histp, "w", encoding="utf-8").write(json.dumps(
        {"commits": ["sandbox"], "rid": hist or {}}, ensure_ascii=False))
    C.OUTDIR = out
    C.ACCOUNTS = accp
    C.LOGP = os.path.join(tmp, "log.json")
    D.PATH = disp
    H.ROOT = tmp
    H.CACHE = histp
    return tmp, out


def _game(rid, t):
    return {"t": t, "rid": rid, "c": "Ahri", "w": True}


def _run(argv):
    old = sys.argv
    sys.argv = ["clean"] + argv
    try:
        C.main()
    finally:
        sys.argv = old


def _left(out, fn):
    fp = os.path.join(out, fn)
    if not os.path.exists(fp):
        return None                      # 檔被刪光
    return len(C.read_file(fp)[1]["matches"])


def t_clean():
    print("③ 判定三真的被 clean 用到（沙盒）")
    # 帳號檔：湊滿門檻用的假帳號 300 隻＋ Care 現有帳號（不含被剔除的那隻）
    acc = [{"team": "T%d" % i, "player": "P%d" % i, "riotId": "filler%d#000" % i} for i in range(320)]
    acc.append({"team": "NIP", "player": "Care", "riotId": "Yondaime#Luo"})
    dis = [{"rid": "ice seven zero#0721", "from": "NIP|Care", "owner": "Beichuan",
            "why": "dpm 掛牌", "at": "2026-09-07 10:00"}]
    files = {
        # A：整檔都是被剔除的那隻帳號 ⇒ 判定三該刪光（＝刪檔）
        "p1.js": ("NIP|Care", {"role": "MIDDLE", "matches": [_game("ice seven zero#0721", 100 + i) for i in range(5)]}),
        # B：同一個 rid 但**別位選手**的檔 ⇒ 名單管不到，一場都不能動
        "p2.js": ("NIP|Someone", {"role": "TOP", "matches": [_game("ice seven zero#0721", 200 + i) for i in range(4)]}),
        # C：Care 自己現有帳號的比賽（同一位選手的第二個檔）⇒ 不能刪，判定一會認出是自己的
        "p3.js": ("NIP|Care", {"role": "MIDDLE", "matches": [_game("Yondaime#Luo", 300 + i) for i in range(3)]}),
        # D：判定四的正例，同時是「沙盒歷史真的有被吃到」的證明——這個 rid 只存在於沙盒的
        #    假歷史裡（真實 repo 的帳號檔歷史沒有它），接錯來源這條就會紅
        "p4.js": ("NIP|Ghost", {"role": "BOTTOM", "matches": [_game("sandboxonly#zzz", 400 + i) for i in range(2)]}),
    }
    hist = {"sandboxonly#zzz": ["NIP|Care"]}     # 判定四：這隻歷史上只掛給過 NIP|Care
    tmp, out = _sandbox(files, acc, dis, hist)
    _run(["--apply"])
    ck("正例：被剔除帳號的 5 場全刪（檔刪掉）", _left(out, "p1.js"), None)
    ck("反例：別位選手同 rid 的 4 場不動", _left(out, "p2.js"), 4)
    ck("反例：本人現有帳號的 3 場不動", _left(out, "p3.js"), 3)
    ck("正例：判定四吃的是沙盒歷史（p4 的 2 場全刪）", _left(out, "p4.js"), None)

    # 對照組：關掉判定三 ⇒ p1 一場都刪不掉（證明上面那條真的是判定三做的，不是別條順手清的）
    tmp2, out2 = _sandbox(files, acc, dis, hist)
    _run(["--apply", "--no-disowned"])
    ck("對照：--no-disowned 時 p1 的 5 場留著", _left(out2, "p1.js"), 5)

    # 帳號檔又把該 rid 登記回 Care 名下 ⇒ 名單自動失效（不可以繼續刪）
    acc2 = list(acc) + [{"team": "NIP", "player": "Care", "riotId": "ice seven zero#0721"}]
    tmp3, out3 = _sandbox(files, acc2, dis, hist)
    _run(["--apply"])
    ck("反例：帳號檔重新登記給本人後，判定三不再刪", _left(out3, "p1.js"), 5)
    for t in (tmp, tmp2, tmp3):
        shutil.rmtree(t, ignore_errors=True)


# ── ④ 沙盒有沒有把「所有外部證據來源」接管（2026-09-07 #51）────────────────
def t_isolate():
    print("④ 沙盒接管了 clean 的每一個外部證據來源")
    # ③ 的反例「別位選手同 rid 的 4 場不動」曾經長期翻紅：不是判定三壞了，而是 #37 加的
    # 判定四拿真實 repo 的 git 歷史當證據，沙盒沒接管 ⇒ 測試結果跟著真實帳號檔每天變。
    # 這一條讓「下一次又多一個證據來源」在沙盒漏接的當下就翻紅。
    src = io.open(os.path.join(HERE, "clean_soloq_matches.py"), encoding="utf-8").read()
    got = sorted({a.name for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Import)
                  for a in n.names if os.path.exists(os.path.join(HERE, a.name + ".py"))})
    ck("clean 用到的本地模組沒有變（多一個就要在 _sandbox 裡接管它）", got, LOCAL_IMPORTS)

    tmp, out = _sandbox({}, [], [], {"marker#zz": ["A|b"]})
    mods = {"C": C, "D": D, "H": H}
    root = os.path.abspath(tmp)
    outside = ["%s.%s" % e for e in EVIDENCE
               if not os.path.abspath(getattr(mods[e[0]], e[1])).startswith(root)]
    ck("六個路徑常數全部指進沙盒", outside, [])
    ck("沙盒目錄不是 git repo ⇒ 掃不到快照（歷史只能來自沙盒快取）", H.snapshots(40, repo=tmp), [])
    ck("讀到的就是沙盒那份假歷史（不是真實 csv_cache）", H.build(repo=tmp), {"marker#zz": ["A|b"]})
    shutil.rmtree(tmp, ignore_errors=True)


def main():
    t_list()
    t_log()
    t_clean()
    t_isolate()
    print("\n%s（失敗 %d 條）" % ("全部通過" if not FAIL else "有失敗：" + "、".join(FAIL), len(FAIL)))
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
