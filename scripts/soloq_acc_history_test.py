# -*- coding: utf-8 -*-
"""soloq_acc_history＋clean_soloq_matches 判定四的單元／整合測試（2026-09-07 #37）。

素材用**真的 git repo**（tempdir 裡 `git init`、真的 commit 兩份帳號檔），不是手刻假索引——
判定四的證據全部來自 `git log`／`git show`，把 git 這一段抽掉測，等於沒測到會出事的那半。

每一條「不該刪」的反例都配一條同結構「該刪」的正例，另有一條 `--no-history` 對照組
（關掉判定四，同一份素材一場都不該少）。

用法：  python scripts/soloq_acc_history_test.py
"""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import soloq_acc_history as H  # noqa: E402
import clean_soloq_matches as C  # noqa: E402

FAIL = []
TRACKED = "scripts/soloq_accounts.json"


def ck(name, got, want):
    if got == want:
        print("  ✓ %s" % name)
    else:
        print("  ✗ %s\n     實際 %r\n     預期 %r" % (name, got, want))
        FAIL.append(name)


def _sh(repo, *args):
    p = subprocess.run(["git", "-C", repo] + list(args),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError("git %s 失敗：%s" % (" ".join(args), p.stderr.decode("utf-8", "replace")))
    return p.stdout


def _repo(snapshots):
    """建一個 tmp git repo，把每一份帳號檔 commit 成一個快照（先給的先 commit ＝比較舊）。"""
    tmp = tempfile.mkdtemp(prefix="acch_")
    _sh(tmp, "init", "-q")
    _sh(tmp, "config", "user.email", "t@t")
    _sh(tmp, "config", "user.name", "t")
    os.makedirs(os.path.join(tmp, "scripts"))
    for i, acc in enumerate(snapshots):
        _commit(tmp, acc, "snap%d" % i)
    return tmp


def _commit(repo, acc, msg):
    with io.open(os.path.join(repo, TRACKED), "w", encoding="utf-8") as f:
        f.write(json.dumps(acc, ensure_ascii=False))
    _sh(repo, "add", TRACKED)
    _sh(repo, "commit", "-q", "-m", msg)


def a(team, player, rid, **kw):
    d = {"team": team, "player": player, "riotId": rid}
    d.update(kw)
    return d


# 那次 912 筆異常名單的縮影：三個帳號分別掛在三位「賽事資料沒出場過」的人身上
OLD = [a("IG", "Helper", "Helper#0324"), a("IG", "Fury", "Fury#01111"),
       a("IG", "Fury", "Fury#3794"), a("BLG", "Ben", "똥 팡#1314"),
       a("BLG", "Daeny", "양대인#KR1"), a("T1", "Faker", "hide on bush#KR1")]
# 之後恢復正常：那四位整個人不見了
NEW = [a("T1", "Faker", "hide on bush#KR1"), a("GEN", "Chovy", "chovy#KR1")]


# ── ① 掃 git 歷史 ─────────────────────────────────────────────────────────
def t_scan():
    print("① 掃 git 歷史快照")
    repo = _repo([OLD, NEW])
    cache = os.path.join(repo, "cache.json")
    ck("兩個快照都找得到", len(H.snapshots(40, repo=repo)), 2)
    rid = H.build(repo=repo, path=cache)
    ck("正例：舊快照的帳號留在索引裡（現在的帳號檔已經沒有了）",
       rid.get("helper#0324"), ["IG|Helper"])
    ck("正例：兩個快照都有的人也在", rid.get("hideonbush#KR1".lower()), ["T1|Faker"])
    ck("正例：normalize 掉空白（帳號檔『똥 팡#1314』對得上逐場檔『똥팡#1314』）",
       rid.get("똥팡#1314"), ["BLG|Ben"])
    ck("快取寫出來了", os.path.exists(cache), True)

    # 增量：再 build 一次不該重掃；多 commit 一個快照只掃那一個
    n0 = len(H.load_cache(cache)["commits"])
    H.build(repo=repo, path=cache)
    ck("增量：沒有新 commit 時快照數不變", len(H.load_cache(cache)["commits"]), n0)
    _commit(repo, NEW + [a("HLE", "Zeka", "zeka#KR1")], "snap2")
    rid = H.build(repo=repo, path=cache)
    ck("增量：新 commit 掃進來了", len(H.load_cache(cache)["commits"]), n0 + 1)
    ck("增量：舊快照的帳號沒有被沖掉", rid.get("helper#0324"), ["IG|Helper"])

    # 同一個 rid 在不同快照掛給不同人 ⇒ 索引留兩個 key（判定四就不會動它）
    repo2 = _repo([[a("A", "x", "same#1")], [a("B", "y", "same#1")]])
    rid2 = H.build(repo=repo2, path=os.path.join(repo2, "c.json"))
    ck("正例：換過主人的 rid 兩個 key 都記著", sorted(rid2.get("same#1") or []), ["A|x", "B|y"])

    # bad 的帳號不算數（跟 clean 的 load_owners 一致）
    repo3 = _repo([[a("A", "x", "bad#1", bad=True), a("A", "x", "ok#1")]])
    rid3 = H.build(repo=repo3, path=os.path.join(repo3, "c.json"))
    ck("反例：bad:true 的帳號不進索引", rid3.get("bad#1"), None)
    ck("正例：同一位選手沒 bad 的帳號有進", rid3.get("ok#1"), ["A|x"])

    # 沒有 git／不是 repo ⇒ 空索引，不可以丟例外
    notrepo = tempfile.mkdtemp(prefix="norepo_")
    ck("反例：不是 git repo 時回空快照", H.snapshots(40, repo=notrepo), [])
    ck("反例：不是 git repo 時 build 回空（不丟例外）",
       H.build(repo=notrepo, path=os.path.join(notrepo, "c.json"), rebuild=True), {})
    for t in (repo, repo2, repo3, notrepo):
        shutil.rmtree(t, ignore_errors=True)


# ── ② 判定規則本身 ────────────────────────────────────────────────────────
def t_rule():
    print("② history_owner 的四個條件")
    idx = H.index({"helper#0324": ["IG|Helper"], "same#1": ["A|x", "B|y"],
                   "fury#01111": ["IG|Fury"]})
    got = H.history_owner(idx, "Helper#0324", "IG|Fury")
    ck("正例：歷史只掛給 IG|Helper、本檔是 IG|Fury ⇒ 判給 IG|Helper",
       got and got[0], "IG|Helper")
    ck("反例②：歷史掛給過兩個人 ⇒ 不判定", H.history_owner(idx, "same#1", "C|z"), None)
    ck("反例③：歷史說就是這個檔的人 ⇒ 不判定",
       H.history_owner(idx, "Helper#0324", "IG|Helper"), None)
    ck("反例④：同一個選手 ID 換隊（IG|Fury→WE|Fury）⇒ 不判定",
       H.history_owner(idx, "Fury#01111", "WE|Fury"), None)
    ck("反例：rid 不在歷史索引 ⇒ 不判定", H.history_owner(idx, "nobody#1", "IG|Fury"), None)
    ck("反例：rid 空的 ⇒ 不判定", H.history_owner(idx, "", "IG|Fury"), None)


# ── ③ 真的接進 clean_soloq_matches（沙盒＋真 git repo）────────────────────
def _game(rid, t):
    return {"t": t, "rid": rid, "c": "Ahri", "w": True}


FILES = {
    # 孤兒檔：key 在現在的帳號檔完全不存在，rid 歷史上是 IG|Helper 的 ⇒ 該刪（刪光＝刪檔）
    "p1.js": ("IG|Fury", {"role": "TOP", "matches": [_game("Helper#0324", 1) for _ in range(5)]}),
    # 同一個 rid、但這是本人的檔 ⇒ 不動
    "p2.js": ("IG|Helper", {"role": "TOP", "matches": [_game("Helper#0324", 2) for _ in range(4)]}),
    # 同一位選手換隊（歷史是 IG|Fury，檔是 WE|Fury）⇒ 不動
    "p3.js": ("WE|Fury", {"role": "TOP", "matches": [_game("Fury#01111", 3) for _ in range(3)]}),
    # 現在的帳號檔就有這個 rid（判定一二的管轄）⇒ 判定四不插手
    "p4.js": ("T1|Faker", {"role": "MID", "matches": [_game("hide on bush#KR1", 4) for _ in range(6)]}),
}


def _sandbox(accounts, repo, cache):
    tmp = tempfile.mkdtemp(prefix="cln4_")
    out = os.path.join(tmp, "soloq_matches")
    os.makedirs(out)
    for fn, (key, data) in FILES.items():
        with io.open(os.path.join(out, fn), "w", encoding="utf-8") as f:
            f.write("window.__sqLoad(%s,%s);\n" % (json.dumps(key, ensure_ascii=False),
                                                   json.dumps(json.loads(json.dumps(data)),
                                                              ensure_ascii=False)))
    accp = os.path.join(tmp, "acc.json")
    io.open(accp, "w", encoding="utf-8").write(json.dumps(accounts, ensure_ascii=False))
    C.OUTDIR = out
    C.ACCOUNTS = accp
    C.LOGP = os.path.join(tmp, "log.json")
    H.ROOT = repo          # 歷史索引改看沙盒 repo
    H.CACHE = cache
    return tmp, out


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
    print("③ 接進 clean_soloq_matches")
    repo = _repo([OLD, NEW])
    # 現在的帳號檔＝NEW（四位孤兒都不在）＋ 320 筆填充（要過 --min-accounts 300 的保險絲）
    acc = list(NEW) + [a("T%d" % i, "P%d" % i, "filler%d#000" % i) for i in range(320)]
    tmp, out = _sandbox(acc, repo, os.path.join(repo, "c1.json"))
    _run(["--apply"])
    ck("正例：孤兒檔 IG|Fury 的 5 場（其實是 IG|Helper 的）全刪、檔刪掉", _left(out, "p1.js"), None)
    ck("反例：本人 IG|Helper 的 4 場不動", _left(out, "p2.js"), 4)
    ck("反例：同選手換隊 WE|Fury 的 3 場不動", _left(out, "p3.js"), 3)
    ck("反例：現在帳號檔命中的 T1|Faker 6 場不動", _left(out, "p4.js"), 6)

    # 對照組：關掉判定四 ⇒ p1 一場都不該少（證明上面那條真的是判定四做的）
    tmp2, out2 = _sandbox(acc, repo, os.path.join(repo, "c2.json"))
    _run(["--apply", "--no-history"])
    ck("對照：--no-history 時 p1 的 5 場留著", _left(out2, "p1.js"), 5)

    # 帳號檔哪天把這個 rid 登記回 IG|Fury 名下 ⇒ 回到判定一的管轄，判定四不再刪
    acc2 = list(acc) + [a("IG", "Fury", "Helper#0324")]
    tmp3, out3 = _sandbox(acc2, repo, os.path.join(repo, "c3.json"))
    _run(["--apply"])
    ck("反例：帳號檔重新登記給本檔的人後，判定四不再刪", _left(out3, "p1.js"), 5)

    for t in (tmp, tmp2, tmp3, repo):
        shutil.rmtree(t, ignore_errors=True)


def main():
    t_scan()
    t_rule()
    t_clean()
    print("\n%s（失敗 %d 條）" % ("全部通過" if not FAIL else "有失敗：" + "、".join(FAIL), len(FAIL)))
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
