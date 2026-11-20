# -*- coding: utf-8 -*-
"""選手的國際賽資歷分（轉會評分用；使用者 2026-11-20「如果選手 FST MSI WCS 過往有優異成績 參加或打到後面都要逐漸給分…
我要反應 Deft 這種優異選手復出的評分過低問題」）。

資料＝Leaguepedia：世界賽正賽（不含入圍賽、資格賽）、MSI、First Stand 的名次（TournamentResults）× 參賽名單（TournamentPlayers）。
給分是使用者逐條定的（2026-11-20），每一屆各算一次、生涯直接加總，**不封頂**（「分數破百沒差」），前端直接加在選手分數上：
    世界賽：冠軍 5、亞軍 4、四強 3、八強 2、參加 1
    MSI　：冠軍 4、亞軍 3、四強 2、參加 1
    FST　：冠軍 3、亞軍 2、參加 1

  scores(cargo) → {選手 wiki 頁名（小寫）: 分數}。結果快取在 csv_cache/transfers_intl.json，7 天內不重抓。
"""
import io
import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "csv_cache", "transfers_intl.json")
PTS = {"World Championship": [(1, 5), (2, 4), (4, 3), (8, 2)], "Mid-Season Invitational": [(1, 4), (2, 3), (4, 2)], "First Stand": [(1, 3), (2, 2)]}   # (名次上限, 分數)；沒列到＝參加 1 分
W = PTS
TTL = 7 * 86400
VER = 2   # 給分規則改了就加一，舊快取作廢


def _pts(place, lg):
    try:
        p = int(float(place))
    except (TypeError, ValueError):
        return 1
    for lim, v in PTS[lg]:
        if p <= lim:
            return v
    return 1


def _in(xs):
    return "(" + ",".join('"' + str(x).replace('"', '\\"') + '"' for x in xs) + ")"


def scores(cargo, force=False):
    if not force and os.path.exists(CACHE) and time.time() - os.path.getmtime(CACHE) < TTL:
        try:
            c_ = json.load(io.open(CACHE, encoding="utf-8"))
            if c_.get("_ver") == VER:
                c_.pop("_ver"); return c_
        except Exception:
            pass
    ts = cargo({"tables": "Tournaments", "fields": "OverviewPage=pg,League=lg,DateStart=ds",
                "where": "League IN " + _in(W) + ' AND IsQualifier=0 AND TournamentLevel="Primary" AND DateStart IS NOT NULL AND DateStart<NOW()',
                "limit": "500", "format": "json"})
    lg_of = {x["pg"]: x["lg"] for x in ts if x.get("pg") and "Regional Finals" not in x["pg"] and "Qualifier" not in x["pg"]}   # 區域資格賽被歸在同一個 League 底下，不算
    pages = sorted(lg_of)
    place, roster = {}, {}
    for i in range(0, len(pages), 25):
        part = pages[i:i + 25]
        # 名次記在賽事主頁（…World Championship），名單記在正賽頁（…/Main Event）⇒ 兩種頁名都查，一律收斂成主頁
        par = sorted({p.split("/Main Event")[0] for p in part} | set(part))
        for x in cargo({"tables": "TournamentResults", "fields": "OverviewPage=pg,Team=tm,Place_Number=pl", "where": "OverviewPage IN " + _in(par), "limit": "5000", "format": "json"}):
            if x.get("tm"):
                k = (x["pg"].split("/Main Event")[0], x["tm"])
                try:
                    v = int(float(x.get("pl")))
                except (TypeError, ValueError):
                    continue
                place[k] = min(place.get(k, 999), v)
        for x in cargo({"tables": "TournamentPlayers", "fields": "OverviewPage=pg,Team=tm,Link=lk,Role=ro", "where": "OverviewPage IN " + _in(part), "limit": "5000", "format": "json"}):
            if x.get("lk") and x.get("tm") and (x.get("ro") or "") in ("Top", "Jungle", "Mid", "Bot", "Support"):
                roster.setdefault((x["pg"], x["tm"]), set()).add(str(x["lk"]))
    # 同一屆拆成好幾頁的（小組賽頁＋淘汰賽頁）：同一年同一賽事只取最好的那個名次
    best = {}
    for (pg, tm), ps in roster.items():
        ev = (lg_of[pg], pg.split("/")[0][:4])
        for p in ps:
            k = (p.lower(), ev)
            best[k] = max(best.get(k, 0), _pts(place.get((pg.split("/Main Event")[0], tm)), lg_of[pg]))
    out = {}
    for (p, _), v in best.items():
        out[p] = out.get(p, 0) + v
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with io.open(CACHE, "w", encoding="utf-8") as f:
        json.dump(dict(out, _ver=VER), f, ensure_ascii=False)
    return out


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    sys.stdout.reconfigure(encoding="utf-8")
    import build_predict_live as B
    s = scores(B.cargo, force="--force" in sys.argv)
    print(len(s), "人")
    for n in ("faker", "deft", "zeus", "kiin", "canyon", "viper (park do-hyeon)", "chovy", "ruler", "bluffing", "caps", "doggo", "scout (lee ye-chan)", "pyosik", "kingen"):
        print(" ", n, s.get(n))
