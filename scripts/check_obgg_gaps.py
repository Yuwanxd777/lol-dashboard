# -*- coding: utf-8 -*-
"""OBGG 帳號覆蓋全面檢視（常駐工具）：逐隊逐選手比對 OBGG 與本地 soloq_accounts.json。

抓三種缺口：
  ①沒帳號     ：該選手本地一個帳號都沒有（OBGG 有）
  ②漏主帳號   ：本地只有小號——OBGG 的「主帳號」(段位最高／年場次最多) 不在本地
  ③疑似失效   ：本地有、OBGG 完全查不到（改名或已棄用）
判定「主帳號」＝段位分數優先、同段位比今年場次；未定級/純數字名/峡谷之巅(BGP2) 一律不算。

用法：
  python scripts\check_obgg_gaps.py                 # LPL+LCK（預設）
  python scripts\check_obgg_gaps.py --zone LPL LCK LCS LEC
  python scripts\check_obgg_gaps.py --all           # 列出每位選手的完整帳號比對（很長）
  python scripts\check_obgg_gaps.py --json out.json # 另存機器可讀結果（給補抓腳本吃）
只讀 OBGG 公開 API，不改任何檔案。
"""
import argparse, io, json, os, re, sys, time, urllib.parse, urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS = os.path.join(HERE, "soloq_accounts.json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
BASE = "https://www.obgg.net/obggmini/"
ALIAS = {"GEN": "GENG"}          # OBGG 隊碼 → 本地隊碼（與 fetch_obgg_accounts.py 一致）

# 段位分數（OBGG tier 形如「王者 - 1971」「宗师 - 1446」「钻1 - 75」「未定级」）
TIER = [("王者", 10), ("宗师", 9), ("大师", 8), ("钻", 7), ("翡", 6), ("铂", 5),
        ("黄金", 4), ("白银", 3), ("青铜", 2), ("黑铁", 1)]
SKIP_REGION = {"BGP2"}           # 峡谷之巅（韓服菁英練習服）：Riot API/dpm 都抓不到


def get(url, retry=2):
    for i in range(retry + 1):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=25)
            return json.loads(r.read().decode("utf-8-sig", "replace"))
        except Exception as e:
            if i == retry:
                return {"_err": str(e)[:120]}
            time.sleep(1.5)


norm = lambda s: re.sub(r"\s+", "", str(s or "")).lower()
num_name = lambda rid: bool(re.fullmatch(r"\d{6,}", str(rid).split("#")[0].strip()))


def tier_score(t):
    t = str(t or "")
    for k, v in TIER:
        if t.startswith(k):
            return v
    return 0


def usable(a):
    """可用帳號＝非峡谷之巅、非純數字死號、有段位或今年有打"""
    if str(a.get("region", "")).upper() in SKIP_REGION or a.get("regionName") == "峡谷之巅":
        return False
    if num_name(a.get("summonerName")):
        return False
    return tier_score(a.get("tier")) > 0 or int(a.get("yearPlay") or 0) > 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zone", nargs="*", default=["LPL", "LCK"])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--json", default="")
    A = ap.parse_args()

    acc = json.load(open(ACCOUNTS, encoding="utf-8"))
    local_rid = {norm(a["riotId"]) for a in acc}
    local_by_player = {}
    for a in acc:
        local_by_player.setdefault((a.get("team", ""), a.get("player", "")), []).append(a)

    report = {"no_account": [], "missing_main": [], "stale": [], "ok": 0}
    for z in A.zone:
        zd = get(BASE + "zone?name=" + urllib.parse.quote(z) + "&isClick=0")
        teams = zd.get("data") if isinstance(zd, dict) else None
        if not teams:
            print(f"✗ {z}: 取不到戰隊清單（{str(zd)[:80]}）"); continue
        print(f"\n{'='*74}\n=== {z}　{len(teams)} 隊 ===")
        for t in teams:
            tm = t["team_name"]
            tc = ALIAS.get(tm, tm)
            rd = get(BASE + "team?name=" + urllib.parse.quote(tm)); time.sleep(0.15)
            roster = rd.get("data") if isinstance(rd, dict) else None
            if not roster:
                print(f"  {tm}: 取不到名單"); continue
            lines = []
            for p in roster:
                gid = p["game_id"]
                pos = str(p.get("pos") or "")
                if re.search(r"教练|经理|分析师|领队|老板|总监", pos):
                    continue                      # 只看選手
                pg = get(BASE + f"progamer?team={urllib.parse.quote(tm)}&game_id={urllib.parse.quote(gid)}")
                time.sleep(0.15)
                d = pg.get("data") if isinstance(pg, dict) else None
                accs = [a for a in ((d or {}).get("accountList") or []) if usable(a)]
                if not accs:
                    continue
                accs.sort(key=lambda a: (tier_score(a.get("tier")), int(a.get("yearPlay") or 0)), reverse=True)
                main_a = accs[0]
                mine = local_by_player.get((tc, gid), [])
                have_main = norm(main_a["summonerName"]) in local_rid
                have_any = bool(mine)
                rest = " 休" if "休息" in pos else ""
                tag = ""
                if not have_any:
                    tag = "✗ 沒帳號"
                    report["no_account"].append({"zone": z, "team": tc, "player": gid,
                                                 "main": main_a["summonerName"], "tier": main_a.get("tier"),
                                                 "yearPlay": main_a.get("yearPlay"),
                                                 "platform": main_a.get("region"),
                                                 "all": [a["summonerName"] for a in accs]})
                elif not have_main:
                    tag = "⚠ 缺主帳號"
                    report["missing_main"].append({"zone": z, "team": tc, "player": gid,
                                                   "main": main_a["summonerName"], "tier": main_a.get("tier"),
                                                   "yearPlay": main_a.get("yearPlay"),
                                                   "platform": main_a.get("region"),
                                                   "local": [x["riotId"] for x in mine]})
                else:
                    report["ok"] += 1
                # OBGG 查不到的本地帳號
                ob_rids = {norm(a["summonerName"]) for a in ((d or {}).get("accountList") or [])}
                gone = [x["riotId"] for x in mine if norm(x["riotId"]) not in ob_rids]
                if gone:
                    report["stale"].append({"zone": z, "team": tc, "player": gid, "local_only": gone})
                if tag or A.all:
                    lines.append(f"    {gid:14s}{rest:2s} {tag or '✓':10s} 主={main_a['summonerName']}"
                                 f" [{main_a.get('tier')}／年{main_a.get('yearPlay')}場]"
                                 + (f"　本地={[x['riotId'] for x in mine]}" if (tag == "⚠ 缺主帳號" or A.all) else "")
                                 + (f"　OBGG另有{len(accs)-1}個小號" if A.all and len(accs) > 1 else ""))
            if lines:
                print(f"  【{tc}】")
                print("\n".join(lines))

    print(f"\n{'='*74}")
    print(f"總結：完全沒帳號 {len(report['no_account'])} 位／只有小號缺主帳號 {len(report['missing_main'])} 位／"
          f"本地有但 OBGG 查無 {len(report['stale'])} 筆／正常 {report['ok']} 位")
    if A.json:
        with open(A.json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print("→ 已寫出", A.json)


if __name__ == "__main__":
    main()
