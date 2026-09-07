# -*- coding: utf-8 -*-
"""「歸屬複查剔除」名單：哪個 riotId 曾經從哪位選手身上被拿掉、dpm 說它其實是誰的。
（2026-09-07 #36）

## 為什麼要這一支

`fetch_dpm_soloq_accounts.py` 的歸屬複查會拿 puuid 去問 dpm「這個帳號掛在誰名下」，
掛牌是**別的職業選手**就把帳號從這位選手的帳號檔剔除。問題是：

  ① 剔除只寫進 `update_log.txt` 的一行 `[歸屬] …→ 剔除`，**日誌每次 run 會被覆寫**，證據就沒了；
  ② 用那隻帳號抓回來的幾百場**留在逐場檔裡**（`fetch_soloq_update` 只追加不刪）；
  ③ 帳號檔已經沒有那個 riotId 了 ⇒ `clean_soloq_matches` 的判定一（rid 命中別人）**永遠命不中**，
     只能靠判定二的字串旁證去猜，猜不出來就留著＝積分頁那位選手的「最近十場」繼續是別人的比賽。

實例（2026-09-07 10:00 的日誌）：
    [歸屬] NIP|Care: ice seven zero#0721 dpm 掛牌是「Beichuan」的帳號 → 剔除
`soloq_matches/p54.js`（NIP|Care）356 場全是 `icesevenzero#0721`，也就是全部都是 Beichuan 的，
但帳號檔已經沒有這個 riotId ⇒ 三條判定都碰不到它。

這支把那個知識寫成持久名單（`csv_cache/soloq_disowned.json`），逐場對帳就從「猜字串」變成
**查 dpm 給過的歸屬證據**（clean_soloq_matches 的判定三）。

## 名單長什麼樣

    [{"rid": "ice seven zero#0721", "from": "NIP|Care", "owner": "Beichuan",
      "why": "dpm 掛牌", "at": "2026-09-07 13:05"}, …]

`from` 是**被剔除的那一位**（＝逐場檔的 key），`owner` 是 dpm 說的真正主人。
判定時只認 `from == 該檔 key`：A 被剔除的帳號不會拿去刪 B 的檔。

## 會不會誤刪（如果 dpm 那天判錯、之後又把帳號還給原主）

不會累積傷害：`clean_soloq_matches` 只在「這個 rid 現在**誰的帳號檔都沒命中**」時才走判定三。
帳號檔重新把它登記給某人之後，就回到判定一／二的管轄，這份名單自動失效。
"""
import io
import json
import os
import re
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PATH = os.path.join(ROOT, "csv_cache", "soloq_disowned.json")
KEEP = 2000          # 只留最近這麼多筆（跟 soloq_clean_log 同樣的做法，不要無限長）


def _norm(s):
    """與 clean_soloq_matches._norm 同一套：去掉全部空白、轉小寫。
    帳號檔寫「ice seven zero#0721」、逐場檔的 rid 是「icesevenzero#0721」，不 normalize 就對不上。"""
    return re.sub(r"\s+", "", str(s or "")).lower()


def load(path=None):
    """讀名單；檔不存在／壞掉都回空 list（這份是輔助證據，壞了只要退回原本的判定一二）。"""
    p = path or PATH
    try:
        rows = json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return []
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def index(rows):
    """normalize 過的 rid → 該 rid 的所有紀錄。"""
    d = {}
    for r in rows:
        k = _norm(r.get("rid"))
        if k:
            d.setdefault(k, []).append(r)
    return d


def add(items, path=None, at=None):
    """追加紀錄，回傳實際新增幾筆。

    items：`(rid, from_key, owner, why)` 的序列。同一組 (rid, from) 只記第一次
    （每天的歸屬複查都會重報同一筆，不去重的話名單會被同一件事灌爆）。
    """
    p = path or PATH
    rows = load(p)
    seen = {(_norm(r.get("rid")), r.get("from")) for r in rows}
    now = at or time.strftime("%Y-%m-%d %H:%M")
    n = 0
    for rid, frm, owner, why in items:
        k = (_norm(rid), frm)
        if not k[0] or not frm or k in seen:
            continue
        rows.append({"rid": rid, "from": frm, "owner": owner or "", "why": why or "", "at": now})
        seen.add(k)
        n += 1
    if n:
        d = os.path.dirname(p)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(p, "w", encoding="utf-8") as f:
            f.write(json.dumps(rows[-KEEP:], ensure_ascii=False, indent=1))
    return n


def disowned_from(idx, rid, key):
    """這個 rid 是不是「曾經從 key 手上被剔除」？是就回那筆紀錄，不是回 None。

    刻意**不**做模糊比對：`from` 必須完全等於逐場檔的 key（「隊縮寫|選手名」），
    否則同名選手（IG|Soboro vs FNC|Soboro 那種）會互相牽連。
    """
    for r in idx.get(_norm(rid), []):
        if r.get("from") == key:
            return r
    return None


# ── 從 update_log.txt 補抓（第二來源）───────────────────────────────────────
# 抓取端寫名單是主要路徑，但 `update_log.txt` **每次 run 會被覆寫**，所以只要那一輪
# 因為任何原因沒寫成（例如這支還沒上線的那些天），證據就永久消失了。
# 這條路徑讓「日誌還在的那一輪」可以補回來，也是 2026-09-07 第一次回填的方法。
RE_OWN = re.compile(r"\[歸屬\]\s*(\S+?)\s*:\s*(.+?)\s+dpm 掛牌是「(.+?)」的帳號\s*→\s*剔除")
RE_CROSS = re.compile(r"\[跨\]\s*同 riotId\s+(.+?)\s+跨選手\s*→\s*留\s*(.+?)（dpm 現行歸屬）、刪\s*\[(.*?)\]")


def parse_log(text):
    """從 run_update 日誌文字解析出 add() 吃的 (rid, from, owner, why) 清單。"""
    out = []
    for m in RE_OWN.finditer(text):
        out.append((m.group(2), m.group(1), m.group(3), "dpm 掛牌（日誌回填）"))
    for m in RE_CROSS.finditer(text):
        rid, keep = m.group(1), m.group(2)
        for frm in re.findall(r"'([^']+)'", m.group(3)):
            out.append((rid, frm, keep, "跨選手：dpm 現行歸屬（日誌回填）"))
    return out


def main(argv=None):
    import sys as _sys
    argv = list(argv if argv is not None else _sys.argv[1:])
    rows = load()
    if "--from-log" in argv:
        i = argv.index("--from-log")
        lp = argv[i + 1] if len(argv) > i + 1 and not argv[i + 1].startswith("--") \
            else os.path.join(ROOT, "update_log.txt")
        txt = io.open(lp, encoding="utf-8", errors="replace").read()
        items = parse_log(txt)
        n = add(items)
        print("從 %s 解析到 %d 筆歸屬剔除，新增 %d 筆（其餘已在名單裡）"
              % (os.path.basename(lp), len(items), n))
        rows = load()
    print("名單共 %d 筆：" % len(rows))
    for r in rows[-40:]:
        print("  %-28s 從 %-22s → 其實是 %-14s（%s %s）"
              % (r.get("rid"), r.get("from"), r.get("owner"), r.get("why"), r.get("at")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
