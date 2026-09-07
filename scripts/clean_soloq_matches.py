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

## 判定一：正面歸屬（保守，只認「rid 命中帳號檔且是別人的」）

每一局帶 `rid`＝dpm 記的「該帳號當時的 Riot ID」。normalize（去空白、轉小寫）後：
  ・命中這位選手自己現有帳號的 riotId → 乾淨，留著
  ・命中**別位**選手現有帳號的 riotId → 髒，刪
  ・誰都沒命中（帳號檔的名字還沒同步／改名／已停用）→ 交給判定二，判不出來就留著
  ・同一個 rid 掛在兩位選手名下（帳號檔自己有矛盾）→ 不判定、留著
  ・沒有 rid 欄位的舊局 → 不判定、留著

## 判定二：舊名歸屬（2026-09-07 追加，處理「rid 是別人的舊 Riot ID」）

判定一只認得**現名**。實測清完之後還有 7 個檔 2380 場是「自己 0 場正面歸屬」，因為那些 rid 是
別位選手改名前的舊 ID（帳號檔只有現名 ⇒ 誰都沒命中）。例如 `TW|BeanJ` p423 的 597 場全是
`Hizto#KR2`／`asdfghjzxc#KR2`（TSW|Hizto 現名 `hjzt0ahjhj#KR2`）。

把 rid X 從 A 檔刪掉，**六個條件全部成立**才算數：
  1. X 誰都沒命中（命中就是判定一的範圍）
  2. **A 檔一場正面歸屬都沒有**（整個檔零實證 ⇒ 目前顯示的東西全都無法證明是 A 的）
  3. X 也出現在別的檔 B，而 **B 檔有至少一場正面歸屬給 B 自己**（B 有實證）
  4. 這樣的 B **只有一個**（多個就是亂帳，不猜）
  5. X 在 A 檔的場數 **不多於** 在 B 檔（A 比 B 多 ⇒ 反而像 B 撿了 A 的，不判定）
  6. 有**名字旁證**：X 的 tag 與 B 現有帳號的 tag 相同（改名多半只改遊戲名），
     或 X 的遊戲名就是 B 的選手 ID；而且 X 的 tag **不**與 A 自己帳號的 tag 相同（有衝突就不判定）

刻意**不**要求「時間不重疊」：不重疊＝改名、重疊＝同一人的第二個帳號，兩者都指向 B，結論一樣。
（實測 `Hizto#KR2` 與 Hizto 現名的場次時間是重疊的雙帳號，硬要求不重疊會漏掉最大的 578 場。）
「rid 只出現在這一個檔」的（IG|Fury 639／BLG|Ben 460／BLG|Daeny 3）**維持不判定**——
那可能是選手自己的舊名，沒有第二個檔可以對照，正是保守規則要保護的情形。
（原本也在這一串的 NIP|Care 356 場，2026-09-07 由下面的判定三解決。）

## 判定三：歸屬複查剔除名單（2026-09-07 #36 追加，處理「帳號早就被拿走、逐場卻還在」）

判定一二都是**看現在的帳號檔**推論。但最強的證據其實在抓取端就出現過又被丟掉：
`fetch_dpm_soloq_accounts` 的歸屬複查會拿 puuid 去問 dpm「這帳號掛在誰名下」，掛牌是別的職業
選手就把帳號從這位選手剔除——那一行只印進 `update_log.txt`，而日誌每次 run 會被覆寫。
帳號檔從此查不到那個 riotId ⇒ 判定一命不中；若該檔另外還有自己的實證（WBG|Jwei 那種）
連判定二也不處理 ⇒ 那些比賽永遠留著。

現在剔除當下就寫進 `csv_cache/soloq_disowned.json`（見 `scripts/soloq_disowned.py`），對帳直接查證據：
  ・rid 現在**誰的帳號檔都沒命中**（命中就回到判定一二的管轄）
  ・而且名單裡有「這個 rid 曾從**這個檔的 key** 被剔除」→ 刪，理由記 dpm 說的真主。
帳號檔哪天又把它登記回本人名下，名單就自動失效（第一個條件不成立），不會累積誤刪。

2026-09-07 首次上線（名單用 `python scripts/soloq_disowned.py --from-log` 從當天日誌回填 3 筆）清掉：
  NIP|Care 356/356 場（ice seven zero#0721＝Beichuan，整頁都是別人的）、
  WBG|Jwei 147/1265 場（BJYBJY#0111＝lamb，其餘 1118 場是他自己的）。

刪光的檔直接刪檔（留一個 0 場的檔會讓索引多一位「0 場選手」）。
檔號安全：`fetch_soloq_year` 新檔號取 `max(現有 pN)+1`，刪掉的號碼不會被重用成別人。

## 保險絲

- 帳號檔有效 riotId 少於 `--min-accounts`（預設 300）⇒ 直接不做（帳號檔被截斷時不要亂刪）。
- 一輪要動的檔數 > `--max-files`（預設 20）或場數 > `--max-games`（預設 3000）⇒ **只印不寫**，
  印出「疑似系統性故障」要人看。真的要照做加 `--force`。
- 每次寫檔都記進 `csv_cache/soloq_clean_log.json`（時間、檔、key、刪幾場、rid→誰、依哪條判定）。

## 用法

    python scripts/clean_soloq_matches.py            # 乾跑，只印（預設）
    python scripts/clean_soloq_matches.py --apply    # 真的寫
    python scripts/clean_soloq_matches.py --apply --force   # 超過保險絲也照做
    python scripts/clean_soloq_matches.py --no-oldname      # 關掉判定二（出事時退回舊行為）
    python scripts/clean_soloq_matches.py --no-disowned     # 關掉判定三（歸屬剔除名單）

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
sys.path.insert(0, HERE)
import soloq_src  # 逐場檔來源 meta：刪場次時同步扣掉 obs，否則 src 會跟 matches 失同步
import soloq_disowned  # 歸屬複查剔除名單：判定三的證據來源
OUTDIR = os.path.join(ROOT, "soloq_matches")
ACCOUNTS = os.path.join(HERE, "soloq_accounts.json")
LOGP = os.path.join(ROOT, "csv_cache", "soloq_clean_log.json")


def _norm(s):
    return re.sub(r"\s+", "", str(s or "")).lower()


def _tag(rid):
    """Riot ID 的 tagline（# 後面）；沒有就回空字串。"""
    r = _norm(rid)
    return r.split("#", 1)[1] if "#" in r else ""


def _game(rid):
    """Riot ID 的遊戲名（# 前面）。"""
    return _norm(rid).split("#", 1)[0]


def load_owners():
    """回傳 (owner, mine, tags)：
    owner[rid]={"隊|人"}、mine["隊|人"]={rid}、tags["隊|人"]={tagline}；bad 的帳號不算數。"""
    acc = json.load(io.open(ACCOUNTS, encoding="utf-8"))
    owner = collections.defaultdict(set)
    mine = collections.defaultdict(set)
    tags = collections.defaultdict(set)
    for a in acc:
        if a.get("bad"):
            continue
        r = _norm(a.get("riotId"))
        if not r:
            continue
        k = "%s|%s" % (a.get("team"), a.get("player"))
        owner[r].add(k)
        mine[k].add(r)
        if _tag(r):
            tags[k].add(_tag(r))
    return owner, mine, tags


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


def scan_all(owner):
    """讀完所有逐場檔，回傳 (files, owncnt, ridmap, unreadable)。

    files[key]  = (fn, fp, data)
    owncnt[key] = 該檔「rid 正面歸屬給自己」的場數（＝這個檔是不是他本人的實證）
    ridmap[rid][key] = 該 rid 在該檔的場數
    """
    files, unreadable = {}, 0
    owncnt = collections.Counter()
    ridmap = collections.defaultdict(collections.Counter)
    for fn in sorted(os.listdir(OUTDIR)):
        if not re.match(r"p\d+\.js$", fn):
            continue
        fp = os.path.join(OUTDIR, fn)
        try:
            key, data = read_file(fp)
        except Exception as e:
            unreadable += 1
            print("  略過 %s：%s" % (fn, e))
            continue
        files[fn] = (key, fp, data)
        for g in (data.get("matches") or []):
            r = _norm(g.get("rid"))
            if not r:
                continue
            ridmap[r][key] += 1
            w = owner.get(r)
            if w and len(w) == 1 and key in w:
                owncnt[key] += 1
    return files, owncnt, ridmap, unreadable


def oldname_owner(rid, key, owner, mine, tags, owncnt, ridmap):
    """判定二：rid 是不是「別位選手的舊名／另一個帳號」。是就回 (那位選手, 理由)，否則 None。"""
    if owner.get(rid):
        return None                                  # ①命中帳號檔 ⇒ 判定一的範圍
    if owncnt.get(key, 0) > 0:
        return None                                  # ②本檔有自己的實證 ⇒ 不動
    cands = [k for k in ridmap.get(rid, {}) if k != key and owncnt.get(k, 0) > 0]
    if len(cands) != 1:                              # ③④ 唯一一個有實證的別檔
        return None
    b = cands[0]
    if ridmap[rid][key] > ridmap[rid][b]:            # ⑤A 比 B 多 ⇒ 反而像 B 撿了 A 的
        return None
    tg, gn = _tag(rid), _game(rid)
    if tg and tg in tags.get(key, set()):            # ⑥tag 跟 A 自己的帳號也對得上 ⇒ 有衝突，不判定
        return None
    why = []
    if tg and tg in tags.get(b, set()):
        why.append("tag #%s＝%s 現有帳號" % (tg, b))
    if gn and gn == _norm(b.split("|")[-1]):
        why.append("遊戲名＝%s 的選手 ID" % b)
    if not why:                                      # ⑥沒有名字旁證 ⇒ 不判定
        return None
    return b, "／".join(why)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真的寫檔（預設只乾跑印出來）")
    ap.add_argument("--force", action="store_true", help="超過保險絲上限也照做")
    ap.add_argument("--no-oldname", action="store_true", help="關掉判定二（舊名歸屬），只跑判定一")
    ap.add_argument("--no-disowned", action="store_true", help="關掉判定三（歸屬複查剔除名單）")
    ap.add_argument("--max-files", type=int, default=20, help="一輪最多動幾個檔（預設 20）")
    ap.add_argument("--max-games", type=int, default=3000, help="一輪最多刪幾場（預設 3000）")
    ap.add_argument("--min-accounts", type=int, default=300, help="帳號檔少於這麼多筆就不做（預設 300）")
    A = ap.parse_args()

    owner, mine, tags = load_owners()
    print("帳號檔：有效 riotId %d 個、涵蓋 %d 位選手" % (len(owner), len(mine)))
    if len(owner) < A.min_accounts:
        print("⛔ 帳號檔只有 %d 個有效 riotId（< %d）＝多半是被截斷或抓取失敗，這輪不清理"
              % (len(owner), A.min_accounts))
        return 0

    DIS = {} if A.no_disowned else soloq_disowned.index(soloq_disowned.load())
    if DIS:
        print("歸屬剔除名單：%d 個 riotId（判定三的證據，來源 csv_cache/soloq_disowned.json）" % len(DIS))

    files, owncnt, ridmap, unreadable = scan_all(owner)

    plans = []
    for fn in sorted(files, key=lambda x: int(re.sub(r"\D", "", x) or 0)):
        key, fp, data = files[fn]
        ms = data.get("matches") or []
        keep, drop = [], []
        for g in ms:
            r = _norm(g.get("rid"))
            who = owner.get(r)
            # 判定一：rid 命中帳號檔、擁有者唯一、而且不是這位選手
            if r and who and len(who) == 1 and key not in who:
                drop.append((g, next(iter(who)), "現名"))
                continue
            # 判定三：這個 rid 曾被歸屬複查從**這位選手**手上剔除（dpm 掛牌是別人的）。
            # 只在「現在誰的帳號檔都沒命中」時才用——帳號檔若又把它登記給誰，那是判定一二的管轄。
            d3 = None if (A.no_disowned or not r or who) else soloq_disowned.disowned_from(DIS, r, key)
            if d3:
                drop.append((g, d3.get("owner") or "?",
                             "剔除（%s %s）" % (d3.get("why") or "歸屬複查", d3.get("at") or "")))
                continue
            # 判定二：rid 是別位選手的舊名／另一個帳號
            hit = None if (A.no_oldname or not r) else oldname_owner(
                r, key, owner, mine, tags, owncnt, ridmap)
            if hit:
                drop.append((g, hit[0], "舊名（%s）" % hit[1]))
            else:
                keep.append(g)
        if drop:
            byrid = collections.Counter("%s＝%s〔%s〕" % (g.get("rid"), w, why) for g, w, why in drop)
            plans.append({"fn": fn, "fp": fp, "key": key, "data": data, "keep": keep,
                          "drop": len(drop), "total": len(ms), "byrid": byrid,
                          # byrid 的鍵是「rid＝擁有者〔理由〕」給人看的；扣 src.obs 要純 rid，另外算一份
                          "droprid": collections.Counter(g.get("rid") for g, _, _ in drop if g.get("rid")),
                          "rules": collections.Counter(("二" if why.startswith("舊名")
                                                        else "三" if why.startswith("剔除") else "一")
                                                       for _, _, why in drop)})

    ngames = sum(p["drop"] for p in plans)
    n2 = sum(p["rules"].get("二", 0) for p in plans)
    n3 = sum(p["rules"].get("三", 0) for p in plans)
    print("掃 %d 個逐場檔（%d 個讀不動）：%d 個檔混進別人的比賽，共 %d 場"
          "（判定一現名 %d、判定二舊名 %d、判定三剔除名單 %d）"
          % (len(files) + unreadable, unreadable, len(plans), ngames, ngames - n2 - n3, n2, n3))
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
            if isinstance(p["data"].get("src"), dict):
                soloq_src.drop(p["data"]["src"], dict(p["droprid"]))   # 刪掉的 rid 同步從來源 obs 扣掉
            write_file(p["fp"], p["key"], p["data"])
            act = "改寫"
        else:
            os.remove(p["fp"])
            act = "刪檔"
        nfile += 1
        ndel += p["drop"]
        rec["files"].append({"f": p["fn"], "key": p["key"], "act": act, "drop": p["drop"],
                             "left": len(p["keep"]), "rid": dict(p["byrid"]),
                             "rules": dict(p["rules"])})
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
