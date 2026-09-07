# -*- coding: utf-8 -*-
"""帳號檔的**歷史歸屬**：某個 riotId 在過去的 `scripts/soloq_accounts.json` 裡登記給誰。
（2026-09-07 #37）

## 為什麼要這一支

`clean_soloq_matches` 的三條判定都是「拿**現在**的帳號檔（或抓取端當下留下的名單）推論」：

  判定一 rid 命中現在的帳號檔、判定二 現在的帳號檔有名字旁證、判定三 抓取端剔除時寫下的名單。

但 2026-09-06 01:1x 出現了第四種漏法：那次手動跑的帳號檔是一份**只有 912 筆的異常名單**
（平常 1082～1092 筆），裡面多出 `IG|Helper`／`IG|Fury`／`BLG|Ben`／`BLG|Daeny` 這些
**賽事資料裡根本沒出場過**的人，而且名字與帳號對錯位了。用那份名單抓完，逐場檔留下三個檔：

    p431 IG|Fury    639 場，rid 全是 Helper#0324  ←（那份名單裡）是 IG|Helper 的帳號
    p432 BLG|Daeny    3 場，rid 全是 Fury#01111   ←（那份名單裡）是 IG|Fury 的帳號
    p433 BLG|Ben    460 場，rid 全是 똥 팡#1314    ←（那份名單裡）就是 BLG|Ben 自己的

下一次跑，帳號檔回到正常名單、**這三位整個人都不見了** ⇒ 逐場檔變成「孤兒」：
沒有帳號 ⇒ `fetch_soloq_update` 不再更新它、判定一二三全部碰不到（rid 誰都沒命中、
本檔零實證但沒有第二個檔可對照、抓取端沒剔除過），可是 `build_soloq_index` 是**掃資料夾**重建索引，
它們照樣進積分頁與每日戰況。⇒ 積分頁上「IG|Fury 的最近十場」其實是 IG|Helper 的比賽。

證據其實還在：`scripts/soloq_accounts.json` 每天 commit 兩次，**git 歷史裡就有那份名單**。
這支把歷史快照掃成 `rid → 曾經登記給誰`，給 `clean_soloq_matches` 的判定四用。

## 判定四怎麼用（保守規則）

只有**全部成立**才算「這個 rid 是別人的」：

  1. rid **現在誰的帳號檔都沒命中**（命中就是判定一二三的管轄，這支不插手）
  2. 掃過的所有快照裡，這個 rid 命中的 key **恰好只有一個**
     （曾經掛給兩個人以上＝歷史本身就是亂帳，不猜）
  3. 那個 key **不是**這個逐場檔的 key
  4. 兩邊的**選手 ID 不同**（`IG|Fury` vs `WE|Fury` ＝同一人換隊，不是別人的比賽）

「歷史本身就是誤配」的防線是第 2、4 條：誤配通常會讓同一個 rid 在不同快照掛給不同的人（第 2 條擋掉），
而換隊改 key 的正常情形由第 4 條擋掉。真的整段歷史都只掛給某一個人、名字也不同，那就是最強的證據了。

## 快取

掃一次 40 個快照要 `git show` 40 份 ~1MB JSON（約 15 秒），所以結果存
`csv_cache/soloq_acc_history.json`，記「掃過哪些 commit」＋`rid → [key…]`。
之後每天只掃新增的那 1～2 個 commit，union 進去（union ＝只會讓判定更保守）。

沒有 git／不是 repo／`git show` 失敗都**回空索引**（判定四整條不生效），不讓管線掛掉。

## 用法

    python scripts/soloq_acc_history.py                 # 更新快取並印摘要
    python scripts/soloq_acc_history.py --rebuild       # 重掃（丟掉舊快取）
    python scripts/soloq_acc_history.py --who "Fury#01111"   # 查某個 rid 的歷史歸屬
"""
import argparse
import io
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, "csv_cache", "soloq_acc_history.json")
TRACKED = "scripts/soloq_accounts.json"      # git 裡的路徑（一律正斜線）
LIMIT = 40                                   # 最多往回掃幾個快照（約 20 天，每天兩次 commit）


def _norm(s):
    return re.sub(r"\s+", "", str(s or "")).lower()


def _player(key):
    """'IG|Fury' → 'fury'（換隊時 key 會變，但選手 ID 不變）。"""
    return _norm(str(key).split("|")[-1])


def _git(args, repo=None):
    """跑 git，回傳 stdout（bytes）；失敗回 None（不丟例外，管線不能因為沒有 git 就掛掉）。"""
    try:
        p = subprocess.run(["git", "-C", repo or ROOT] + list(args),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception:
        return None
    if p.returncode != 0:
        return None
    return p.stdout


def snapshots(limit=LIMIT, repo=None, tracked=TRACKED):
    """回傳最近 limit 個動過帳號檔的 commit hash（新→舊）。"""
    out = _git(["log", "--format=%H", "-%d" % int(limit), "--", tracked], repo=repo)
    if not out:
        return []
    return [h for h in out.decode("utf-8", "replace").split() if h]


def owners_in(commit, repo=None, tracked=TRACKED):
    """某個快照裡的 {rid(normalized): {key…}}；讀不到回 None（跟「讀到空的」要分得出來）。"""
    out = _git(["show", "%s:%s" % (commit, tracked)], repo=repo)
    if out is None:
        return None
    try:
        acc = json.loads(out.decode("utf-8", "replace"))
    except Exception:
        return None
    got = {}
    for a in acc:
        if not isinstance(a, dict) or a.get("bad"):
            continue
        r = _norm(a.get("riotId"))
        if not r:
            continue
        got.setdefault(r, set()).add("%s|%s" % (a.get("team"), a.get("player")))
    return got


def load_cache(path=None):
    p = path or CACHE
    try:
        d = json.load(io.open(p, encoding="utf-8"))
    except Exception:
        d = {}
    if not isinstance(d, dict):
        d = {}
    d.setdefault("commits", [])
    d.setdefault("rid", {})
    return d


def save_cache(d, path=None):
    p = path or CACHE
    dr = os.path.dirname(p)
    if dr and not os.path.isdir(dr):
        os.makedirs(dr)
    with io.open(p, "w", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True))


def build(limit=LIMIT, repo=None, tracked=TRACKED, path=None, rebuild=False, verbose=False):
    """更新快取並回傳 {rid: [key…]}（只掃還沒掃過的 commit；union 進去）。"""
    d = {"commits": [], "rid": {}} if rebuild else load_cache(path)
    done = set(d["commits"])
    todo = [c for c in snapshots(limit, repo=repo, tracked=tracked) if c not in done]
    for c in todo:
        got = owners_in(c, repo=repo, tracked=tracked)
        if got is None:
            continue                                  # 那個快照讀不到就跳過，不要記成「掃過了」
        for rid, keys in got.items():
            cur = set(d["rid"].get(rid) or [])
            cur.update(keys)
            d["rid"][rid] = sorted(cur)
        d["commits"].append(c)
    d["at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    d["commits"] = d["commits"][-400:]
    if todo:
        save_cache(d, path)
    if verbose:
        print("帳號檔歷史：快照 %d 個（本次新掃 %d 個）、riotId %d 個"
              % (len(d["commits"]), len(todo), len(d["rid"])))
    return d["rid"]


def index(rid_map):
    """把 build() 的結果轉成查詢用（值變成 set）。"""
    return {r: set(v) for r, v in (rid_map or {}).items()}


def history_owner(idx, rid, key):
    """判定四：這個 rid 在歷史帳號檔裡是不是**只**掛給過別的某一位選手。

    是就回 (那位選手的 key, 理由字串)，否則 None。呼叫端要先確定
    「rid 現在誰的帳號檔都沒命中」（判定一二三優先）。
    """
    r = _norm(rid)
    if not r:
        return None
    keys = idx.get(r)
    if not keys or len(keys) != 1:                    # ②歷史上掛給兩個人以上＝亂帳，不猜
        return None
    b = next(iter(keys))
    if b == key:                                      # ③歷史說就是這位選手的
        return None
    if _player(b) == _player(key):                    # ④同一個選手 ID 換隊，不是別人
        return None
    return b, "歷史帳號檔登記給 %s" % b


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="丟掉舊快取重掃")
    ap.add_argument("--limit", type=int, default=LIMIT, help="往回掃幾個快照（預設 %d）" % LIMIT)
    ap.add_argument("--who", help="查某個 riotId 的歷史歸屬")
    A = ap.parse_args(argv)

    if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    rid = build(limit=A.limit, rebuild=A.rebuild, verbose=True)
    if not rid:
        print("⚠ 沒有拿到任何歷史快照（沒有 git／不是 repo／帳號檔沒進版控）＝判定四不生效")
        return 0
    if A.who:
        idx = index(rid)
        keys = idx.get(_norm(A.who))
        print("%s → %s" % (A.who, "、".join(sorted(keys)) if keys else "（歷史快照裡沒有）"))
    else:
        multi = [r for r, v in rid.items() if len(v) > 1]
        print("其中 %d 個 riotId 在歷史上掛給過兩位以上的選手（判定四不碰這些）" % len(multi))
    return 0


if __name__ == "__main__":
    sys.exit(main())
