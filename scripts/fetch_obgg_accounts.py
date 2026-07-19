# -*- coding: utf-8 -*-
"""OBGG 職業帳號每日更新 → 合併進 soloq_accounts.json（併入 update.bat）。
來源＝OBGG 微信小程序公開 API www.obgg.net/obggmini（免登入，帶 User-Agent 即可）。
  zone?name=LPL → 該賽區戰隊；team?name=IG → 該隊選手(game_id)；
  progamer?team=IG&game_id=TheShy → 該選手 accountList（summonerName=完整RiotID、regionName、lastGameTime…）
路由（使用者定案）：LPL/LCK 以 OBGG 為主（近兩月有打的加入、沒打的刪）、LCS/LEC/CBLOL 以 dpm 為主（保留現有）、其餘 union。
過濾鐵則：峡谷之巅（韓服菁英練習服，Riot API/dpm 抓不到）、近 60 天沒打、純數字死號。
dpmPuuid：本腳本只維護帳號清單；新帳號的 dpmPuuid 由 resolve_obgg_dpmpuuid.py 之後補（才能進逐場）。
安全門：OBGG 抓取失敗或 LPL/LCK 帳號數異常過少 → 不動 soloq_accounts.json（避免 OBGG 掛掉時誤刪整批）。
用法：python scripts\\fetch_obgg_accounts.py
"""
import io, sys, json, os, re, time, urllib.parse, urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS = os.path.join(HERE, "soloq_accounts.json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
BASE = "https://www.obgg.net/obggmini/"
ZONES = ["LPL", "LCK", "LCS", "LEC", "LCP", "VCS", "LJL", "LTA S", "CBLOL"]
OBGG_ZONES = {"LPL", "LCK"}          # 以 OBGG 為主（重建）
DPM_ZONES = {"LCS", "LEC", "CBLOL"}  # 以 dpm 為主（保留現有，不加 OBGG）
PLAT = {"韩服": "kr", "美服": "na1", "欧服": "euw1", "巴西": "br1"}
ALIAS = {"GEN": "GENG"}              # OBGG 隊碼 → 清單隊碼
CUT_MS = 60 * 24 * 3600 * 1000       # 近兩個月


def get(url, retry=2):
    h = {"User-Agent": UA, "Referer": "https://servicewechat.com/wxe8e7f9130f2ba69c/"}
    for i in range(retry + 1):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=25)
            return json.loads(r.read().decode("utf-8-sig", "replace"))
        except Exception as e:
            if i == retry:
                return {"_err": str(e)[:100]}
            time.sleep(1.5)


def num_name(rid):
    return bool(re.fullmatch(r"\d{6,}", str(rid).split("#")[0].strip()))


def norm(s):
    return re.sub(r"\s+", "", str(s or "")).lower()


def pull():
    now = time.time() * 1000
    out = {}
    for z in ZONES:
        zd = get(BASE + "zone?name=" + urllib.parse.quote(z) + "&isClick=0")
        teams = zd.get("data") if isinstance(zd, dict) else None
        if not teams:
            print(f"  {z}: 無資料（跳過）"); continue
        out[z] = {}
        for t in teams:
            tm = t["team_name"]
            rd = get(BASE + "team?name=" + urllib.parse.quote(tm)); time.sleep(0.15)
            roster = rd.get("data") if isinstance(rd, dict) else None
            if not roster:
                continue
            for p in roster:
                gid = p["game_id"]
                pg = get(BASE + f"progamer?team={urllib.parse.quote(tm)}&game_id={urllib.parse.quote(gid)}")
                time.sleep(0.15)
                d = pg.get("data") if isinstance(pg, dict) else None
                accs = (d or {}).get("accountList", []) if isinstance(d, dict) else []
                good = []
                for a in accs:
                    if a.get("regionName") == "峡谷之巅":
                        continue
                    if num_name(a.get("summonerName")):
                        continue
                    try:
                        lt = float(a.get("lastGameTime"))
                    except Exception:
                        continue
                    if (now - lt) > CUT_MS:
                        continue
                    good.append({"platform": PLAT.get(a["regionName"], a.get("region")),
                                 "riotId": a.get("summonerName")})
                if good:
                    out[z].setdefault(tm, {})[gid] = good
        print(f"  {z}: {sum(len(v) for v in out[z].values())} 帳號", flush=True)
    return out


def main():
    obgg = pull()
    # 安全門：OBGG 主導賽區必須抓到夠多帳號，否則不動（避免 OBGG 異常時誤刪整批）
    for z in OBGG_ZONES:
        n = sum(len(v) for v in obgg.get(z, {}).values())
        if n < 20:
            print(f"✗ {z} 只抓到 {n} 帳號（<20），OBGG 可能異常 → 不更新 soloq_accounts.json"); return

    acc = json.load(open(ACCOUNTS, encoding="utf-8"))
    cur_teams = set(a.get("team") for a in acc)

    def canon(tm):
        a = ALIAS.get(tm)
        return a if a and a in cur_teams else tm

    team_zone = {}
    for z, teams in obgg.items():
        for tm in teams:
            team_zone[canon(tm)] = z

    def zone_of(team):
        return team_zone.get(team)

    cur_by_rid = {norm(a["riotId"]): a for a in acc}

    def obgg_entries(pred):
        res = []
        for z, teams in obgg.items():
            if not pred(z):
                continue
            for tm, ps in teams.items():
                tc = canon(tm)
                for gid, accs in ps.items():
                    for a in accs:
                        e = {"player": gid, "team": tc, "platform": a["platform"], "riotId": a["riotId"]}
                        old = cur_by_rid.get(norm(a["riotId"]))
                        if old:  # 沿用已解析的 dpmPuuid 與張冠李戴標記
                            if old.get("dpmPuuid"):
                                e["dpmPuuid"] = old["dpmPuuid"]
                            if old.get("bad"):
                                e["bad"] = old["bad"]; e["bad_reason"] = old.get("bad_reason")
                        res.append(e)
        return res

    new = obgg_entries(lambda z: z in OBGG_ZONES)
    new += obgg_entries(lambda z: z not in OBGG_ZONES and z not in DPM_ZONES)
    new_rids = {norm(e["riotId"]) for e in new}

    removed = 0
    for a in acc:
        z = zone_of(a.get("team"))
        if z in OBGG_ZONES:          # OBGG 主導：舊帳號只有還在 OBGG 清單才留（上面已重建），否則刪
            if norm(a["riotId"]) not in new_rids:
                removed += 1
            continue
        if norm(a["riotId"]) in new_rids:  # 其餘賽區已由 union 納入
            continue
        new.append(a)                # dpm 主導/無法分類：保留

    best = {}
    for e in new:
        k = norm(e["riotId"]); ex = best.get(k)
        if not ex or (not ex.get("dpmPuuid") and e.get("dpmPuuid")):
            best[k] = e
    final = list(best.values())

    json.dump(acc, open(ACCOUNTS + ".bak", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(final, open(ACCOUNTS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"OBGG 帳號更新：{len(acc)} → {len(final)}（LPL/LCK 刪 {removed} 個近兩月未列；"
          f"無 dpmPuuid {sum(1 for e in final if not e.get('dpmPuuid'))} 個待 resolve_obgg_dpmpuuid.py 補）")


if __name__ == "__main__":
    main()
