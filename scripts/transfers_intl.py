# -*- coding: utf-8 -*-
"""選手的國際賽資歷分（轉會評分用；使用者 2026-11-20「如果選手 FST MSI WCS 過往有優異成績 參加或打到後面都要逐漸給分…
我要反應 Deft 這種優異選手復出的評分過低問題」）。

資料＝Leaguepedia：世界賽正賽（不含入圍賽、資格賽）、MSI、First Stand 的名次（TournamentResults）× 參賽名單（TournamentPlayers）。
2026-11-20 改版（使用者「如果三大國際賽只算一次最高成績呢 然後改成加 5 10 20」）：三大賽各只算生涯**最好的一次**成績，
三者相加（最多 20＋10＋5＝35），前端直接加在選手分數上。名次的級距照原本的比例換算：
    世界賽（滿分 20）：冠軍 20、亞軍 16、四強 12、八強 8、正賽 4、入圍賽 2（使用者指定叫「正賽」，不寫 16 強）
      （使用者 2026-11-20「世界賽八強後還要分成 16強跟入圍賽」；入圍賽名單另外從 …World Championship/Play-In 頁抓）
    MSI　（滿分 10）：冠軍 10、亞軍 7.5、四強 5、參加 2.5
    FST　（滿分 5）：冠軍 5、亞軍 3.5、參加 2
原本是每一屆各算一次、生涯加總不封頂（世界賽 5／4／3／2／1、MSI 4／3／2／1、FST 3／2／1）⇒ Faker ＋71，比他的去年評分還高。

  scores(cargo) → {選手 wiki 頁名（小寫）: 分數}。結果快取在 csv_cache/transfers_intl.json，7 天內不重抓。
"""
import io
import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "csv_cache", "transfers_intl.json")
PTS = {"World Championship": [(1, 20), (2, 16), (4, 12), (8, 8)], "Mid-Season Invitational": [(1, 10), (2, 7.5), (4, 5)], "First Stand": [(1, 5), (2, 3.5)]}
PART = {"World Championship": 4, "Mid-Season Invitational": 2.5, "First Stand": 2}   # 只有參加（名次沒進上面的級距）；世界賽＝打進正賽
PLAYIN = 2   # 世界賽只打入圍賽、沒進正賽   # (名次上限, 分數)；沒列到＝參加 1 分
W = PTS
TTL = 7 * 86400
VER = 4   # 給分規則改了就加一，舊快取作廢


def _pts(place, lg):
    try:
        p = int(float(place))
    except (TypeError, ValueError):
        return PART[lg]
    for lim, v in PTS[lg]:
        if p <= lim:
            return v
    return PART[lg]


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
        ev = lg_of[pg]   # 每一種賽事只留生涯最好的一次（不分哪一年）
        for p in ps:
            k = (p.lower(), ev)
            best[k] = max(best.get(k, 0), _pts(place.get((pg.split("/Main Event")[0], tm)), lg_of[pg]))
    # 世界賽入圍賽：只出現在入圍賽名單、沒進正賽的人給 PLAYIN 分（進了正賽的人上面已經有更高的分數，取大的）
    try:
        pis = [x["pg"] for x in cargo({"tables": "Tournaments", "fields": "OverviewPage=pg", "limit": "200", "format": "json",
                                       "where": 'League="World Championship" AND OverviewPage LIKE "%World Championship/Play-In%" AND DateStart IS NOT NULL AND DateStart<NOW()'}) if x.get("pg")]
        for i in range(0, len(pis), 25):
            for x in cargo({"tables": "TournamentPlayers", "fields": "OverviewPage=pg,Link=lk,Role=ro", "where": "OverviewPage IN " + _in(pis[i:i + 25]), "limit": "5000", "format": "json"}):
                if x.get("lk") and (x.get("ro") or "") in ("Top", "Jungle", "Mid", "Bot", "Support"):
                    k = (str(x["lk"]).lower(), "World Championship")
                    best[k] = max(best.get(k, 0), PLAYIN)
    except Exception as e:
        print(f"   世界賽入圍賽名單查詢失敗（略過）：{type(e).__name__} {str(e)[:100]}")
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
