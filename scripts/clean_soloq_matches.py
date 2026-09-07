# -*- coding: utf-8 -*-
"""逐場檔對帳：刪掉「混進別位選手帳號」的比賽（2026-09-07）。

## 為什麼需要這一支

`build_soloq_index.py` 是**掃 `soloq_matches/p*.js` 重建索引**，每個檔自己帶 key（"隊|選手"），
**沒有任何一步回頭跟 `scripts/soloq_accounts.json` 對帳**。於是：

  ① `fetch_dpm_soloq_accounts` 的「歸屬複查」把帳號 X 從選手 A 剔除（因為 dpm 掛牌其實是 B 的）
  ② 但 A 的逐場檔（用 X 抓的那幾百場）**留在原地**，`fetch_soloq_update` 只追加不刪
  ③ ⇒ 積分頁上 A 的「最近十場」永遠是 B 的比賽

2026-09-07 實測受害 6 檔 777 場，其中 4 位是**整頁都別人的**（自己 0 場）：
  OMG|Starry 390/391（May#KR43＝GZ|Betty）、IG|Soboro 199/523（WhiteUsedSocks#0110＝FNC|Soboro，同名不同人）、
  TW|BeanJ 99/696（hjzt0ahjhj#KR2＝TSW|Hizto）、WBG|Medusa 86/86（我锤石你德玛#2887＝LGD|Crisp）。
而且帳號檔每天都在搬動（Hizto／Crisp 那兩隻是 09-07 才剛進來的）⇒ 必須每輪跑，手清一次沒用。

## 判定（保守：只認「正面歸屬給別人」）

每一局帶 `rid`＝dpm 記的「該帳號當時的 Riot ID」。normalize（去空白、轉小寫）後：
  ・命中這位選手自己現有帳號的 riotId → 乾淨，留著
  ・命中**別位**選手現有帳號的 riotId → 髒，刪
  ・誰都沒命中（帳號檔的名字還沒同步／改名／已停用）→ **不判定、留著**（309 種，不猜）
  ・同一個 rid 掛在兩位選手名下（帳號檔自己有矛盾）→ 不判定、留著
  ・沒有 rid 欄位的舊局 → 不判定、留著

刪光的檔直接刪檔（留一個 0 場的檔會讓索引多一位「0 場選手」）。
檔號安全：`fetch_soloq_year` 新檔號取 `max(現有 pN)+1`，刪掉的號碼不會被重用成別人。

## 保險絲

- 帳號檔有效 riotId 少於 `--min-accounts`（預設 300）⇒ 直接不做（帳號檔被截斷時不要亂刪）。
- 一輪要動的檔數 > `--max-files`（預設 20）或場數 > `--max-games`（預設 3000）⇒ **只印不寫**，
  印出「疑似系統性故障」要人看。真的要照做加 `--force`。
- 每次寫檔都記進 `csv_cache/soloq_clean_log.json`（時間、檔、key、刪幾場、rid→誰）。

## 用法

    python scripts/clean_soloq_matches.py            # 乾跑，只印（預設）
    python scripts/clean_soloq_matches.py --apply    # 真的寫
    python scripts/clean_soloq_matches.py --apply --force   # 超過保險絲也照做

排在管線的 ⑤e 之後、⑤f `build_soloq_index` 之前（索引與出裝聚合都是掃逐場檔重建，清完才會生效）。
"""
import argparse
import collections
import io
import json
import os
import re
import sys
import time

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUTDIR = os.path.join(ROOT, "soloq_matches")
ACCOUNTS = os.path.join(HERE, "soloq_accounts.json")
LOGP = os.path.join(ROOT, "csv_cache", "soloq_clean_log.json")


def _norm(s):
    return re.sub(r"\s+", "", str(s or "")).lower()


def load_owners():
    """回傳 (owner, mine)：owner[rid]={"隊|人"}、mine["隊|人"]={rid}；bad 的帳號不算數。"""
    acc = json.load(io.open(ACCOUNTS, encoding="utf-8"))
    owner = collections.defaultdict(set)
    mine = collections.defaultdict(set)
    for a in acc:
        if a.get("bad"):
            continue
        r = _norm(a.get("riotId"))
        if not r:
            continue
        owner[r].add("%s|%s" % (a.get("team"), a.get("player")))
        mine["%s|%s" % (a.get("team"), a.get("player"))].add(r)
    return owner, mine


def read_file(fp):
    txt = io.open(fp, encoding="utf-8", errors="replace").read()
    m = re.match(r"window\.__sqLoad\((.*)\);\s*$", txt, re.S)
    if not m:
        raise ValueError("不是 __sqLoad 格式")
    key, data = json.loads("[" + m.group(1) + "]")
    return key, data


def write_file(fp, key, data):
    with io.open(fp, "w", encoding="utf-8") as f:
        f.write("window.__sqLoad(%s,%s);\n" % (json.dumps(key, ensure_ascii=False),
                                               json.dumps(data, ensure_ascii=False)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真的寫檔（預設只乾跑印出來）")
    ap.add_argument("--force", action="store_true", help="超過保險絲上限也照做")
    ap.add_argument("--max-files", type=int, default=20, help="一輪最多動幾個檔（預設 20）")
    ap.add_argument("--max-games", type=int, default=3000, help="一輪最多刪幾場（預設 3000）")
    ap.add_argument("--min-accounts", type=int, default=300, help="帳號檔少於這麼多筆就不做（預設 300）")
    A = ap.parse_args()

    owner, mine = load_owners()
    print("帳號檔：有效 riotId %d 個、涵蓋 %d 位選手" % (len(owner), len(mine)))
    if len(owner) < A.min_accounts:
        print("⛔ 帳號檔只有 %d 個有效 riotId（< %d）＝多半是被截斷或抓取失敗，這輪不清理"
              % (len(owner), A.min_accounts))
        return 0

    plans, unreadable, scanned = [], 0, 0
    for fn in sorted(os.listdir(OUTDIR)):
        if not re.match(r"p\d+\.js$", fn):
            continue
        scanned += 1
        fp = os.path.join(OUTDIR, fn)
        try:
            key, data = read_file(fp)
        except Exception as e:
            unreadable += 1
            print("  略過 %s：%s" % (fn, e))
            continue
        ms = data.get("matches") or []
        keep, drop = [], []
        for g in ms:
            r = _norm(g.get("rid"))
            who = owner.get(r)
            # 只刪「正面歸屬給別人」的：rid 命中帳號檔、擁有者唯一、而且不是這位選手
            if r and who and len(who) == 1 and key not in who:
                drop.append((g, next(iter(who))))
            else:
                keep.append(g)
        if drop:
            byrid = collections.Counter("%s＝%s" % (g.get("rid"), w) for g, w in drop)
            plans.append({"fn": fn, "fp": fp, "key": key, "data": data, "keep": keep,
                          "drop": len(drop), "total": len(ms), "byrid": byrid})

    ngames = sum(p["drop"] for p in plans)
    print("掃 %d 個逐場檔（%d 個讀不動）：%d 個檔混進別人的比賽，共 %d 場"
          % (scanned, unreadable, len(plans), ngames))
    for p in sorted(plans, key=lambda x: -x["drop"]):
        print("  %-22s %-9s 刪 %d／共 %d 場（自己剩 %d）%s ← %s"
              % (p["key"], p["fn"], p["drop"], p["total"], len(p["keep"]),
                 "  ⚠ 刪光＝刪檔" if not p["keep"] else "",
                 "、".join("%s×%d" % (k, v) for k, v in p["byrid"].most_common(3))))
    if not plans:
        print("✓ 沒有要清的")
        return 0

    over = []
    if len(plans) > A.max_files:
        over.append("檔數 %d > %d" % (len(plans), A.max_files))
    if ngames > A.max_games:
        over.append("場數 %d > %d" % (ngames, A.max_games))
    if over and not A.force:
        print("⛔ 超過保險絲（%s）＝疑似系統性故障（帳號檔大搬風／歸屬邏輯壞掉），這輪只印不寫。"
              % "、".join(over))
        print("   確認過真的要清，跑：python scripts/clean_soloq_matches.py --apply --force")
        return 0
    if not A.apply:
        print("（乾跑：沒有寫任何檔。要真的清加 --apply）")
        return 0

    rec = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "files": []}
    nfile = ndel = 0
    for p in plans:
        if p["keep"]:
            p["data"]["matches"] = p["keep"]
            write_file(p["fp"], p["key"], p["data"])
            act = "改寫"
        else:
            os.remove(p["fp"])
            act = "刪檔"
        nfile += 1
        ndel += p["drop"]
        rec["files"].append({"f": p["fn"], "key": p["key"], "act": act, "drop": p["drop"],
                             "left": len(p["keep"]), "rid": dict(p["byrid"])})
        print("  %s %s（%s）：刪 %d 場、剩 %d 場" % (act, p["fn"], p["key"], p["drop"], len(p["keep"])))

    try:
        hist = json.load(io.open(LOGP, encoding="utf-8")) if os.path.exists(LOGP) else []
    except Exception:
        hist = []
    hist.append(rec)
    with io.open(LOGP, "w", encoding="utf-8") as f:
        f.write(json.dumps(hist[-200:], ensure_ascii=False, indent=1))
    print("✓ 清理完成：%d 個檔、%d 場（紀錄 → %s）" % (nfile, ndel, os.path.relpath(LOGP, ROOT)))
    print("  （索引與出裝聚合由後面的 build_soloq_index／build_soloq_builds 重建）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
