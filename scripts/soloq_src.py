# -*- coding: utf-8 -*-
"""逐場檔的「來源」meta（`data["src"]`）——把「這個檔的比賽是哪個 dpmPuuid 抓來的」記進檔裡。

為什麼要有：`soloq_matches/pN.js` 的每一場只有 `rid`（抓到當下的 Riot ID 字串），
沒有來源 puuid。一旦帳號檔的 riotId↔dpmPuuid 錯配（dpm 把別人的 puuid 掛在這位選手名下），
逐場檔就會混進別人的比賽，而事後只能靠字串旁證去猜是誰的（見 clean_soloq_matches.py 的判定一／二，
2026-09-07 已為此刪掉 1698 場）。有了來源 puuid，對帳變成「這個 puuid 抓回來的 rid
是不是它自己登記的 riotId」，不必猜。

格式（放在 `__sqLoad(key, data)` 的 data 頂層，key 名 `src`；前端 `__SQCACHE[k]=d` 整份收下，
多這個 key 不影響任何既有讀取）：

    "src": {
      "v": 1,                                  # 格式版本
      "at": "2026-09-07 11:40",                # 最後一次更新 src 的時間
      "full": true,                            # obs 是否涵蓋檔內全部場次（全年重建＝true；只做過增量＝false）
      "acc": [{"pu": "<dpmPuuid>", "rid": "Name#TAG"}],   # 寫檔當下這位選手的帳號清單
      "obs": {"<dpmPuuid>": {"Name#TAG": 場數}}           # 各 puuid 實際抓回來的場次 rid 分布
    }

`full=false` 時 obs 只涵蓋「上線後才抓到的新場次」，可以用來抓錯配，但不能拿它的場數
當「這個檔應該有幾場」。
"""
import time

SRC_V = 1


def new_src():
    return {"v": SRC_V, "at": time.strftime("%Y-%m-%d %H:%M"), "full": False, "acc": [], "obs": {}}


def get_src(data):
    """取出（必要時建立）data 裡的 src；回傳的是 data 內的同一個物件，改它就等於改 data。"""
    s = data.get("src")
    if not isinstance(s, dict) or s.get("v") != SRC_V:
        s = new_src()
        data["src"] = s
    s.setdefault("acc", [])
    s.setdefault("obs", {})
    return s


def set_accounts(src, accs):
    """記下寫檔當下這位選手的帳號清單（accs＝soloq_accounts.json 的項目）。"""
    src["acc"] = [{"pu": a.get("dpmPuuid"), "rid": a.get("riotId")}
                  for a in accs if a.get("dpmPuuid")]
    src["at"] = time.strftime("%Y-%m-%d %H:%M")


def note(src, puuid, games):
    """把某個 puuid 這次抓回來的場次記進 obs（games＝逐場 dict 的 list）。"""
    if not puuid or not games:
        return
    d = src["obs"].setdefault(puuid, {})
    for g in games:
        r = g.get("rid")
        if r:
            d[r] = d.get(r, 0) + 1
    src["at"] = time.strftime("%Y-%m-%d %H:%M")


def drop(src, rid_counts):
    """場次被刪掉時同步扣 obs（rid_counts＝{rid: 刪掉幾場}）。扣到 0 就移除該 rid。

    ⚠ 同一個 rid 常同時掛在好幾個 puuid 底下（錯配時正是這樣：別人的 puuid 抓回來一批
    「別人的 rid」，而那個 rid 也可能是另一支帳號的正常名字）。所以**跨 puuid 只能扣掉總共 n 場**，
    不能每個 puuid 各扣 n——各扣一次會把正主自己的場次也歸零，之後 mismatches() 就會誤報
    「這個 puuid 沒出現過自己的 riotId」。從持有最多的那個 puuid 開始扣（刪掉的多半就是它的）。
    """
    if not rid_counts:
        return
    for rid, n in rid_counts.items():
        left = int(n or 0)
        if left <= 0:
            continue
        for pu, d in sorted(src["obs"].items(), key=lambda kv: -kv[1].get(rid, 0)):
            if left <= 0:
                break
            have = d.get(rid, 0)
            if have <= 0:
                break            # 已排序，後面的只會更少（都是 0）
            take = min(have, left)
            d[rid] = have - take
            left -= take
            if d[rid] <= 0:
                del d[rid]
    for pu in [pu for pu, d in src["obs"].items() if not d]:
        del src["obs"][pu]
    src["at"] = time.strftime("%Y-%m-%d %H:%M")


def merge(srcs):
    """合併同一位選手多個逐場檔的 src（build_soloq_index 去重併檔時用）。回傳 None＝沒有可用的 src。

    obs 逐 puuid 逐 rid 相加；acc 依 puuid 去重（先出現的優先）；
    **full 要全部都 True 才是 True**（只要有一檔是增量寫的，合出來的 obs 就不涵蓋全部場次）；
    at 取最大（格式固定 YYYY-MM-DD HH:MM，字串比大小即可）。版本不同的一律略過，不硬合。
    """
    srcs = [s for s in srcs if isinstance(s, dict) and s.get("v") == SRC_V]
    if not srcs:
        return None
    out = {"v": SRC_V, "at": max((s.get("at") or "") for s in srcs),
           "full": all(bool(s.get("full")) for s in srcs), "acc": [], "obs": {}}
    seen = set()
    for s in srcs:
        for a in s.get("acc") or []:
            if a.get("pu") and a["pu"] not in seen:
                seen.add(a["pu"])
                out["acc"].append(a)
        for pu, d in (s.get("obs") or {}).items():
            tgt = out["obs"].setdefault(pu, {})
            for rid, n in (d or {}).items():
                tgt[rid] = tgt.get(rid, 0) + n
    return out


def _norm(s):
    return str(s or "").strip().lower().replace(" ", "")


def same_name(a, b):
    """兩個 Riot ID 字串是不是同一個（忽略大小寫與空白；任一邊是空的一律 False）。"""
    na, nb = _norm(a), _norm(b)
    return bool(na) and na == nb


def mismatches(data, min_games=3):
    """用 src 對帳：回傳 [(puuid, 帳號登記的 rid, 實際抓到最多的 rid, 那個 rid 幾場, 該 puuid 總場數)]。

    判準是「**這個 puuid 抓回來的場次裡，從頭到尾沒出現過它自己登記的 riotId**」
    ⇒ 那個 puuid 根本不是這個帳號的（帳號檔 riotId↔dpmPuuid 錯配）。

    ⚠ 不能用「最多的那個 rid ≠ 登記的 riotId」當判準：帳號改名後 obs 裡會同時有
    舊名（歷史一大堆）與新名（改名後的少數幾場），而帳號檔已被改名偵測更新成新名 ⇒
    「最多的」永遠是舊名，每天都誤報一次。改名的情況下新名一定出現過，用「有沒有出現過」就不會誤報。
    """
    src = data.get("src")
    if not isinstance(src, dict) or not src.get("obs"):
        return []
    acc = {a.get("pu"): a.get("rid") for a in src.get("acc") or []}
    out = []
    for pu, d in src["obs"].items():
        if not d:
            continue
        tot = sum(d.values())
        if tot < min_games:
            continue
        want = acc.get(pu)
        if not want or any(_norm(r) == _norm(want) for r in d):
            continue
        top, n = max(d.items(), key=lambda kv: kv[1])
        out.append((pu, want, top, n, tot))
    return out


# ── 對帳不符的自動分類（2026-09-09 #82）────────────────────────────────────────
# 起因：⑤d 每次印「N 筆來源對帳不符…可能是改名或錯配」，每一筆都要人工追一輪
#      （#81 追 DNS|DDoiV 那筆就花了半輪）。手上的資料其實就夠判，不必每次重來。
KIND_LABEL = {"rename": "改名", "suspect": "疑錯配"}


def _tday(t):
    """毫秒 epoch → MM-DD（只給人看，判斷一律用原始數值）。"""
    try:
        return time.strftime("%m-%d", time.localtime(int(t) / 1000.0))
    except Exception:
        return "?"


def classify(data, pu, want, got_rids=None):
    """把一筆對帳不符分成「改名」還是「疑錯配」。回傳 `(kind, note)`。

    `kind` ∈ `"rename"`（不用處理，等 dpm 名字索引跟上就自己消失）／
            `"suspect"`（維持原本的人工判定線：clean_soloq_matches 的四條判定）。

    判準（DNS|DDoiV 2026-09-09 這筆真實案例定的）：逐場的 `rid` 是**比賽當下**的名字，
    puuid 不隨改名變。所以選手改名、而 dpm 的名字索引還沒跟上時，同一顆 puuid 抓回來的
    新場次掛的是新名，帳號檔登記的還是舊名 ⇒ **掛新名的那些場一定全部晚於掛登記名的最後一場**
    （中間那個空檔就是改名的時點）。反過來，真的錯配（dpm 把別人的 puuid 掛在這位選手名下）
    抓回來的是別人一整段歷史，時間會跟登記名的場次**交錯**、甚至更早。

        不符 rid 的最早一場 > 登記 rid 的最晚一場              ⇒ rename
        交錯／更早／登記名一場都沒有／沒有逐場可比             ⇒ suspect

    ⚠ **分不出來的一律回 suspect**：誤標成 rename 會讓真的錯配靜悄悄過去（逐場檔混進別人的
    比賽、積分頁算錯），誤標成 suspect 只是多看一眼。方向不對稱，寧可多報。

    `got_rids` 不給就從 `src["obs"][pu]` 取（mismatches() 的定義保證裡面沒有 want）。
    """
    src = data.get("src") if isinstance(data, dict) else None
    obs = (src or {}).get("obs") or {}
    if got_rids is None:
        got_rids = list((obs.get(pu) or {}).keys())
    gset = set(_norm(r) for r in got_rids if r)
    wn = _norm(want)
    gset.discard(wn)
    ms = (data.get("matches") if isinstance(data, dict) else None) or []
    if not ms:
        return "suspect", "沒有逐場資料可比時間（全年重建時只有本次抓回的場次）"
    if not gset:
        return "suspect", "obs 裡沒有可比對的不符 rid"
    tg = [g.get("t") or 0 for g in ms if _norm(g.get("rid")) in gset]
    tw = [g.get("t") or 0 for g in ms if _norm(g.get("rid")) == wn]
    if not tw:
        return "suspect", "登記名 %s 在逐場檔一場都沒有（%d 場全是 %s）" % (want, len(tg), "／".join(sorted(gset))[:40])
    if not tg:
        return "suspect", "不符的那些場已不在逐場檔（被 clean_soloq_matches 清掉？）"
    g0, w1 = min(tg), max(tw)
    if g0 > w1:
        return "rename", ("改名：不符名 %d 場（%s 起）全部晚於登記名最後一場（%s，共 %d 場）"
                          " → 比賽當時的新名，dpm 名字索引沒跟上；資料不用動"
                          % (len(tg), _tday(g0), _tday(w1), len(tw)))
    ovl = sum(1 for t in tw if t > g0)
    return "suspect", ("時間交錯：不符名最早 %s，登記名還有 %d／%d 場在那之後（最後 %s）"
                       " → 不是單純改名，要查 riotId↔dpmPuuid 是不是錯配"
                       % (_tday(g0), ovl, len(tw), _tday(w1)))


def summarize(rows, limit=10):
    """把一批對帳不符整理成要印的行。`rows`＝[(標籤, want, got, n, tot, kind, note)]。

    **疑錯配排前面**（那才是要動手的），改名排後面；`limit` 只截尾巴，
    不會因為改名太多把疑錯配擠掉（那正是分類要解決的事）。回傳 list[str]。
    """
    rows = list(rows)
    nsus = sum(1 for r in rows if r[5] == "suspect")
    head = ("⚠ %d 筆來源對帳不符（帳號 riotId 與該 puuid 實際抓回的 rid 不同）：疑錯配 %d 筆／改名 %d 筆"
            % (len(rows), nsus, len(rows) - nsus))
    rows.sort(key=lambda r: (r[5] != "suspect",))    # 穩定排序：suspect 在前，其餘保持原順序
    out = [head]
    for tag, want, got, n, tot, kind, note in rows[:limit]:
        out.append("   [%s] %s  帳號 %s 的 puuid → 實際 %s×%d／%d 場" % (KIND_LABEL.get(kind, kind), tag, want, got, n, tot))
        out.append("        %s" % note)
    if len(rows) > limit:
        out.append("   …另外 %d 筆同類的省略" % (len(rows) - limit))
    return out
