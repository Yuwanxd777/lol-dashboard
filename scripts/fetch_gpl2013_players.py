# -*- coding: utf-8 -*-
"""GPL 2013 逐場選手回填（Leaguepedia Team Rosters 的 ExtendedRoster 出賽旗標）

背景（2026-08-01 使用者指出）：
  2013 GPL 的比賽資料是從 `Picks and Bans` 頁抓的，那個模板寫著 noroles=yes——只有英雄、
  沒有選手名，所以逐選手場數整批是空的。MatchHistoryGame 表對 2013 GPL 完全沒有資料
  （fetch_wiki_mh.py --probe 是 0 局），所以走不了既有那條路。

  但 `<賽事>/Team Rosters` 頁的 {{ExtendedRoster/Line}} 有 r= 旗標，逐輪逐局記「這局有沒有上場」：
      |player=Prydz |role=Top |r=yy,y,yyy,yy,yy,yy,yy,yy,yyy,yy,yy,yyy,yy
      逗號分組＝輪次（rounds=13），組內每個字元＝該輪的一局；y＝上場、n＝沒上場，
      另有 m/t/b 等狀態（bkt 就有 m）——非 y 一律不當上場。
  自洽性實測：ahq 打野 Lantyr 24 場＋GarnetDevil 4 場＝28，剛好補滿該位置的總場位。

⚠ 對齊問題（本腳本的重點）：
  Team Rosters 記的是**該隊打過的每一局**（春季每隊 28 局），但 PB 頁只收錄了其中一半
  （春季 56 個區塊＝每隊 14 局）。所以不能按索引硬拉，要以「輪次」為單位對齊，
  而且只在**該輪該位置只有一個人上場**時才敢寫入——同一輪換過人就標成 ambiguous 不寫。
  寧可少補，也不要把場次掛到錯的人頭上。

用法：
  python scripts\\fetch_gpl2013_players.py            # 只分析、印覆蓋率，不寫檔
  python scripts\\fetch_gpl2013_players.py --json out.json   # 另存逐場配對結果
"""
import argparse, io, json, os, re, sys, urllib.parse, urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, "csv_cache", "gpl2013")
UA = {"User-Agent": "lol-dashboard/1.0 (local backfill)"}

# PB 頁的隊名欄混用縮寫與全名（同一頁裡 BKT 與 Bangkok Titans 都出現過）→ 正規化成縮寫
TEAM_FIX = {"bangkok titans": "bkt", "kuala lumpur hunters": "klh", "manila eagles": "mle",
            "singapore sentinels": "sgs", "taipei assassins": "tpa", "saigon jokers": "saj",
            "fantastic five": "sf5", "saigon fantastic five": "sf5", "ahq esports club": "ahq",
            "ahq e-sports club": "ahq"}
_tk = lambda s: TEAM_FIX.get(str(s).strip().lower(), str(s).strip().lower())

# 位置：wiki 寫法 → 儀表板寫法
ROLE = {"top": "TOP", "jungle": "JNG", "jg": "JNG", "mid": "MID", "middle": "MID",
        "bot": "BOT", "ad": "BOT", "adc": "BOT", "support": "SUP", "sup": "SUP"}
# r= 旗標的字元：y＝照自己掛的位置上場、n＝沒上場、
# 其餘字母＝**當局改打的路線**（wiki 那格會畫路線圖示，一樣算有上場，只是換路）
#（2026-08-01 使用者指出；ahq 春季第 9 局 Prydz=j／GarnetDevil=t 就是上路與打野互換）
LANE_CH = {"t": "TOP", "j": "JNG", "m": "MID", "b": "BOT", "s": "SUP", "a": "BOT", "u": "SUP"}


def wikitext(page):
    """取頁面原始 wikitext（有快取；wiki 的歷史頁不會變，抓一次就夠）"""
    os.makedirs(CACHE, exist_ok=True)
    fp = os.path.join(CACHE, re.sub(r"[^A-Za-z0-9]+", "_", page) + ".txt")
    if os.path.exists(fp):
        return io.open(fp, encoding="utf-8").read()
    u = "https://lol.fandom.com/api.php?" + urllib.parse.urlencode(
        {"action": "parse", "page": page, "prop": "wikitext", "format": "json"})
    d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60))
    w = d["parse"]["wikitext"]["*"]
    io.open(fp, "w", encoding="utf-8").write(w)
    return w


def parse_rosters(page):
    """→ {隊縮寫小寫: {位置: {選手: [每輪的旗標字串, ...]}}}；同時回傳每隊的輪數"""
    w = wikitext(page)
    out, rounds = {}, {}
    for m in re.finditer(r"===\s*\{\{team\|([^}]+)\}\}\s*===\s*(\{\{ExtendedRoster.*?\n\}\})", w, re.S):
        ab = m.group(1).strip().lower()
        blk = m.group(2)
        rn = re.search(r"rounds=(\d+)", blk)
        rounds[ab] = int(rn.group(1)) if rn else 0
        team = out.setdefault(ab, {})
        for L in re.finditer(r"\{\{ExtendedRoster/Line\|(.*?)\}\}", blk, re.S):
            f = L.group(1)
            g = lambda k: (re.search(r"\|?\s*" + k + r"\s*=\s*([^|\n}]+)", f) or [None, ""])[1].strip()
            player = g("player")
            # 有些 player 欄寫成「ADM (Phongsak Charoenchai)」→ 括號是本名，取前面的 ID
            player = re.sub(r"\s*\(.*\)\s*$", "", player).strip()
            if not player:
                continue
            pairs = []
            if g("roles"):                                  # 多位置：role1/r1、role2/r2…
                for i in range(1, 5):
                    r_ = g("role%d" % i)
                    if not r_:
                        continue
                    s = (re.search(r"\|\s*r%d\s*=\s*([A-Za-z,]+)" % i, f) or [None, ""])[1]
                    if s:
                        pairs.append((r_, s))
            else:
                s = (re.search(r"\|\s*r\s*=\s*([A-Za-z,]+)", f) or [None, ""])[1]
                if s:
                    pairs.append((g("role"), s))
            for r_, s in pairs:
                pos = ROLE.get(r_.strip().lower())
                if not pos:
                    continue
                team.setdefault(pos, {})[player] = s.split(",")
    return out, rounds


def parse_pb(pages):
    """Picks and Bans 頁 → [{round:輪次index, i:該輪第幾局, t1, t2}]（依頁面順序）"""
    games = []
    for page in pages:
        try:
            w = wikitext(page)
        except Exception as e:
            print(f"   （{page} 取不到：{e}）")
            continue
        # ⚠ 輪次要讀標題裡的數字，不能自己累加：夏季分成主頁（Week 1-7）與 /8-14 子頁（Week 8-13），
        #   每頁各自從 0 累加會撞號，13 週被壓成 7 週（2026-08-01 除錯）
        ri = 0
        seen_in_round = 0
        for chunk in re.split(r"\n==\s*", w):
            head = chunk.split("\n", 1)[0]
            mh = re.match(r"(?:Round|Week)\s*(\d+)", head, re.I)
            if mh:
                ri = int(mh.group(1))
                seen_in_round = 0
            for bl in re.finditer(r"\{\{PicksAndBans\|(.*?)\}\}", chunk, re.S):
                f = bl.group(1)
                g = lambda k: (re.search(r"\|?\s*" + k + r"\s*=\s*([^|\n}]+)", f) or [None, ""])[1].strip()
                t1, t2 = g("team1"), g("team2")
                if not t1 or not t2:
                    continue
                games.append({"round": ri, "i": seen_in_round, "t1": _tk(t1), "t2": _tk(t2),
                              "page": page})
                seen_in_round += 1
    return games


def resolve(rosters, games):
    """以「每隊自己的出場序」對齊，再逐位置挑出上場的人。

    ⚠ 不能用 PB 頁的 Round 標題當索引：春季 PB 只有 7 個 Round 標題、名單卻是 14 組。
    兩邊真正的對應是「該隊的第幾場」：
      ・夏季：PB（主頁＋/8-14 子頁）每隊 28 局、名單也是 28 個字元 → 1:1 逐字元對。
      ・春季：PB 每隊 14 局、名單 28 個字元分成 14 組 → 一個 PB 區塊＝一場 BO2，
        對到名單的第 k 組（該組兩個字元＝那場的兩局），只要組內任一局是 y 就算有上場。
    同一場/組裡同位置有兩個人以上標 y ＝ 中途換人，無法判斷這一局是誰 → 標 ambiguous 不寫。
    """
    per_team = {}
    for gi, gm in enumerate(games):
        for side in ("t1", "t2"):
            per_team.setdefault(gm[side], []).append(gi)
    picks = {}                      # gi -> {ab: {pos: player|None}}
    stat = {"ok": 0, "ambiguous": 0, "norose": 0, "unaligned": [], "modes": {}}
    for ab, idxs in per_team.items():
        team = rosters.get(ab)
        if not team:
            stat["norose"] += len(idxs)
            continue
        # ⚠ 要取「全隊最長」的旗標字串：中途加入的選手字串比較短（ahq 春季有人只有 9 字元/5 組），
        #   拿他當基準會誤判成對不齊
        allg = [g for players in team.values() for g in players.values()]
        total = max(sum(len(x) for x in g) for g in allg)
        ngroups = max(len(g) for g in allg)
        rounds_of = sorted({games[gi]["round"] for gi in idxs})   # 該隊出現過的週次/輪次
        mode = None
        if total == len(idxs):
            mode = "char"                                   # 1:1 逐字元
        elif ngroups == len(idxs):
            mode = "group"                                  # 一個 PB 區塊＝名單的一組（春季 BO2）
        elif ngroups == len(rounds_of):
            mode = "week"                                   # 名單一組＝一週；該週的每一局都用同一組
        if not mode:
            stat["unaligned"].append(f"{ab}: PB {len(idxs)} 局 vs 名單 {total} 字元/{ngroups} 組")
            continue
        stat["modes"][ab] = mode
        for k, gi in enumerate(idxs):
            gk = rounds_of.index(games[gi]["round"]) if mode == "week" else k
            for pos, players in team.items():
                cand = []
                for pl, groups in players.items():
                    if mode in ("group", "week"):
                        if gk < len(groups) and "y" in groups[gk]:
                            cand.append(pl)
                    else:
                        flat = "".join(groups)
                        if k < len(flat) and flat[k] == "y":
                            cand.append(pl)
                if len(cand) == 1:
                    picks.setdefault(gi, {}).setdefault(ab, {})[pos] = cand[0]
                    stat["ok"] += 1
                elif len(cand) > 1:
                    picks.setdefault(gi, {}).setdefault(ab, {})[pos] = None
                    stat["ambiguous"] += 1
    res = [{"gi": gi, "round": gm["round"], "t1": gm["t1"], "t2": gm["t2"],
            "teams": picks.get(gi, {})} for gi, gm in enumerate(games)]
    return res, stat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    SPLITS = [
        ("春季", "2013 GPL Spring/Team Rosters", ["2013 GPL Spring/Picks and Bans"]),
        ("夏季", "2013 GPL Summer/Team Rosters",
         ["2013 GPL Summer/Picks and Bans", "2013 GPL Summer/Picks and Bans/8-14"]),
    ]
    allout = {}
    for name, rpage, pbpages in SPLITS:
        print(f"== GPL 2013 {name}")
        rosters, rounds = parse_rosters(rpage)
        games = parse_pb(pbpages)
        print(f"   名單 {len(rosters)} 隊（輪數 {sorted(set(rounds.values()))}）｜PB 局數 {len(games)}"
              f"｜輪次 {len(set(g['round'] for g in games))}")
        res, stat = resolve(rosters, games)
        tot = stat["ok"] + stat["ambiguous"]
        print(f"   位置配對：唯一 {stat['ok']}／同場換人 {stat['ambiguous']}"
              f"（可寫入 {stat['ok']*100//max(1,tot)}%）｜名單查無 {stat['norose']} 隊次")
        print("   對齊方式：", stat["modes"])
        for u in stat["unaligned"]:
            print("   ⚠ 對不齊：", u)
        allout[name] = res
    if a.json:
        io.open(a.json, "w", encoding="utf-8").write(json.dumps(allout, ensure_ascii=False, indent=1))
        print("已寫出", a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
