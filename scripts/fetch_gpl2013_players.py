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
                # ⚠ 2013 的模板兩邊寫法不一樣：藍方 bluepick1、紅方 red_pick1（多一條底線）
                pk = {}
                for sd in ("blue", "red"):
                    pk[sd] = [(g("%spick%d" % (sd, n)) or g("%s_pick%d" % (sd, n)))
                              for n in range(1, 6)]
                games.append({"round": ri, "i": seen_in_round, "t1": _tk(t1), "t2": _tk(t2),
                              "picks": pk, "page": page})
                seen_in_round += 1
    return games


def lineup_chars(team):
    """一隊的名單 → [{位置: 選手}, ...]（逐局），以及每組（週/輪）的字元數。

    旗標一個字元＝**一局**（使用者定案 2026-08-01：「一場勾勾最多五個，一個 R1(一週)
    有兩場他也都有分開寫」）。字元的意思：
      y＝照自己掛的位置上場／n＝沒上場／其他字母＝**當局改打的路線**（wiki 那格畫路線圖示，
      一樣算有上場，只是換路；使用者補充：「有時候他會給路線圖 那也代表他出賽 只是他換路了」）。
    實測 16 隊 × 28 局：每局都剛好五個位置、0 個位置衝突 → 不會有「同場換人」的歧義。
    """
    allg = [g for players in team.values() for g in players.values()]
    if not allg:
        return [], []
    ngroups = max(len(g) for g in allg)
    sizes = [max((len(g[k]) for g in allg if k < len(g)), default=0) for k in range(ngroups)]
    per = [dict() for _ in range(sum(sizes))]
    off = [sum(sizes[:k]) for k in range(ngroups)]
    for pos, players in team.items():
        for pl, groups in players.items():
            for k, gs in enumerate(groups):
                for c, ch in enumerate(gs):
                    p2 = pos if ch == "y" else LANE_CH.get(ch.lower())
                    if p2 and off[k] + c < len(per):
                        per[off[k] + c][p2] = pl
    return per, sizes


def align_rounds(sizes, counts):
    """名單的每組字元數 vs PB 每輪該隊局數 → {輪次index: 名單組index}。

    夏季有三隊只有 12 組卻有 13 週（bkt/saj/tpa），直接用輪次當索引會整段錯位；
    用大小序列做貪婪對齊（可跳過名單組＝該週沒記，或跳過輪次＝名單漏那週），
    只有大小一致的輪次才配對，其餘留空不寫。
    """
    out, gi = {}, 0
    for ri, n in enumerate(counts):
        if gi < len(sizes) and sizes[gi] == n:
            out[ri] = gi; gi += 1
        elif gi + 1 < len(sizes) and sizes[gi + 1] == n:   # 名單多一組（PB 沒收錄那週）
            gi += 1; out[ri] = gi; gi += 1
        else:                                              # 對不上：這一輪不寫，名單也不前進
            continue
    return out


def resolve(rosters, games):
    """→ {gi: {隊: {位置: 選手}}}；逐局解析，對不齊的輪次直接略過不寫。"""
    per_team = {}
    for gi, gm in enumerate(games):
        for side in ("t1", "t2"):
            per_team.setdefault(gm[side], []).append(gi)
    picks, stat = {}, {"ok": 0, "skip": 0, "norose": 0, "modes": {}}
    for ab, idxs in per_team.items():
        team = rosters.get(ab)
        if not team:
            stat["norose"] += len(idxs); continue
        per, sizes = lineup_chars(team)
        rounds_of = sorted({games[gi]["round"] for gi in idxs})
        counts = [sum(1 for gi in idxs if games[gi]["round"] == r) for r in rounds_of]
        amap = align_rounds(sizes, counts)
        stat["modes"][ab] = f"{len(amap)}/{len(rounds_of)} 輪對齊"
        for ri, r in enumerate(rounds_of):
            gidx = amap.get(ri)
            same = [gi for gi in idxs if games[gi]["round"] == r]
            if gidx is None:
                stat["skip"] += len(same); continue
            base = sum(sizes[:gidx])
            for k, gi in enumerate(same):
                if base + k >= len(per):
                    stat["skip"] += 1; continue
                picks.setdefault(gi, {})[ab] = dict(per[base + k])
                stat["ok"] += 1
    res = [{"gi": gi, "round": gm["round"], "t1": gm["t1"], "t2": gm["t2"],
            "picks": gm.get("picks", {}), "teams": picks.get(gi, {})} for gi, gm in enumerate(games)]
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
        tot = stat["ok"] + stat["skip"]
        print(f"   隊次解析：成功 {stat['ok']}／略過 {stat['skip']}"
              f"（{stat['ok']*100//max(1,tot)}%）｜名單查無 {stat['norose']} 隊次")
        for ab, mm in sorted(stat["modes"].items()):
            if not mm.startswith(mm.split("/")[1].split(" ")[0]):
                print(f"   ⚠ {ab}: {mm}")
        allout[name] = res
    if a.json:
        io.open(a.json, "w", encoding="utf-8").write(json.dumps(allout, ensure_ascii=False, indent=1))
        print("已寫出", a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
