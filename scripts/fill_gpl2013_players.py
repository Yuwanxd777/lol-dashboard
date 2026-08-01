# -*- coding: utf-8 -*-
"""把 2013 GPL 春季／夏季的**逐局**選手名寫進 data/data_2013.js。

背景：這兩個賽段的列是 fetch_wiki_pb.py 從 Picks and Bans 頁產的，只有英雄沒有選手名
（圖鑑→賽事的隊伍小框因此只有隊名、沒有「選手(場數)」）。Leaguepedia 的
`{賽事}/Team Rosters` 用 {{ExtendedRoster}} 記了**逐局先發**（r=yy,yy,… 一個字元一局），
由 fetch_gpl2013_players.py 解析；本檔負責把它對回資料檔。

對法：
  ① PB 區塊（輪次＋該輪順序）→ 名單的第幾局 → {位置: 選手}
  ② 資料檔一場 6 列（participantid 1-5 是五個位置、100 是隊伍列）。隊伍列的
     blue_Lane/red_Lane 就是**照 TOP/JNG/MID/BOT/SUP 排好的五隻英雄**，
     拿它跟 PB 的選角集合比對即可認出是同一局，再依位置把名字寫到 1-5 列。
用法：python scripts/fill_gpl2013_players.py        （乾跑，只印報告）
      python scripts/fill_gpl2013_players.py --write（實寫）

⚠ 這是「補在成品上」：抓取管線重跑 data_2013.js 之後要再跑一次。
   長遠解是把 lineup_chars() 併進 fetch_wiki_pb.py 的 _ros_of 之前（TODO）。
"""
import io, os, re, sys, json, argparse, importlib.util

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("gpl", os.path.join(HERE, "fetch_gpl2013_players.py"))
G = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(G)

POS5 = ["TOP", "JNG", "MID", "BOT", "SUP"]
SPLITS = [("春季", "2013 GPL Spring/Team Rosters", ["2013 GPL Spring/Picks and Bans"]),
          ("夏季", "2013 GPL Summer/Team Rosters",
           ["2013 GPL Summer/Picks and Bans", "2013 GPL Summer/Picks and Bans/8-14"])]


def ck(s):
    """英雄名比對用的鍵：wiki 與 OE 的寫法差在標點與大小寫（Cho'Gath／Chogath、
    Kha'Zix／KhaZix、Dr. Mundo／DrMundo）→ 只留英數字。"""
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


# wiki 的 PB 頁大量用簡寫，且是 2013 當年的舊名 → 對照到資料檔的正式名。
# 前綴／子字串能唯一命中的（nunu→nunuwillump、xin→xinzhao、mundo→drmundo）由 build_alias()
# 自動解，這裡只列自動解不掉的縮寫。
ALIAS = {"mf": "missfortune", "j4": "jarvaniv", "tf": "twistedfate", "ww": "warwick",
         "gp": "gangplank", "lb": "leblanc", "yi": "masteryi", "asol": "aurelionsol",
         "noc": "nocturne", "eve": "evelynn", "sej": "sejuani", "naut": "nautilus",
         "trynd": "tryndamere", "panth": "pantheon", "morde": "mordekaiser",
         "fiddle": "fiddlesticks", "heca": "hecarim", "malz": "malzahar",
         "kass": "kassadin", "cass": "cassiopeia", "vlad": "vladimir", "ori": "orianna"}


def build_alias(canon):
    """{wiki 寫法鍵: 資料檔正式名鍵}；canon＝資料檔裡真實出現過的英雄名鍵集合。"""
    m = {}
    for a, b in ALIAS.items():
        if b in canon:
            m[a] = b
    return m


def canon_of(k, canon, alias):
    if k in canon:
        return k
    if k in alias:
        return alias[k]
    hit = [c for c in canon if c.startswith(k)] or [c for c in canon if k in c]
    return hit[0] if len(hit) == 1 else k


def load_data(p):
    s = io.open(p, encoding="utf-8").read()
    i = s.index("=")
    return json.loads(s[i + 1:].strip().rstrip(";"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    # ── ① 先讀資料檔（要拿它的英雄名當基準才能解 wiki 的簡寫）──
    p = os.path.join(ROOT, "data", "data_2013.js")
    D = load_data(p)
    R = D["tabs"]["RAW_DATA"]
    H = R[0]
    ix = {n: i for i, n in enumerate(H)}
    canon = set()
    for r in R[1:]:
        for k in ("blue_champion", "red_champion"):
            v = ck(r[ix[k]]) if k in ix else ""
            if v:
                canon.add(v)
    alias = build_alias(canon)

    # ── ② 從 wiki 解出逐局陣容，建索引 {(隊集合, 選角集合): {隊: {位置: 選手}}} ──
    idx = {}
    unres = set()
    for name, rpage, pbpages in SPLITS:
        rosters, _ = G.parse_rosters(rpage)
        games = G.parse_pb(pbpages)
        res, stat = G.resolve(rosters, games)
        n = 0
        for r in res:
            if not r["teams"]:
                continue
            pk = r.get("picks") or {}
            raw = [c for c in (pk.get("blue") or []) + (pk.get("red") or []) if c]
            for c in raw:
                if canon_of(ck(c), canon, alias) not in canon:
                    unres.add(c)
            allpk = frozenset(canon_of(ck(c), canon, alias) for c in raw)
            if len(allpk) < 10:      # 選角沒收齊就不當比對鍵，寧可不寫
                continue
            idx[(frozenset((r["t1"], r["t2"])), allpk)] = r["teams"]
            n += 1
        print(f"== {name}：可用局 {n}／{len(res)}（隊次成功 {stat['ok']}、略過 {stat['skip']}）")

    if unres:
        print("   ⚠ 對不到正式英雄名（該局不寫）：", "、".join(sorted(unres)))

    # ── ②-b 選手名拼法對齊 ──
    # wiki 名單頁與 MatchHistory 的大小寫常常不同（bebe／Bebe、westdoor／Westdoor、
    # WahzleNs／wAhzLeNs）。build_career.py 拿「名字字串」當生涯的唯一 key，拼法不同
    # ＝同一個人被拆成兩份生涯、隊伍小框也會列成兩個人各自算場數。
    # 基準取**春夏以外**的賽段（TESL／台港澳／東南亞是 fetch_wiki_mh 抓的，已經過 pname() 對齊）。
    import collections as _c
    auth_cnt = _c.defaultdict(_c.Counter)
    for r in R[1:]:
        if str(r[ix["split"]]) in ("春季", "夏季"):
            continue
        for k in ("blue_playername", "red_playername"):
            v = str(r[ix[k]]).strip()
            if v:
                auth_cnt[v.casefold()][v] += 1
    AUTH = {k: v.most_common(1)[0][0] for k, v in auth_cnt.items()}

    def pn(nm):
        return AUTH.get(str(nm).strip().casefold(), nm) if nm else nm

    # ── ③ 掃資料檔，逐場比對 ──
    need = ["league", "split", "date", "game", "participantid", "blue_teamname", "red_teamname",
            "blue_champion", "red_champion", "blue_Lane", "red_Lane",
            "blue_playername", "red_playername"]
    for k in need:
        if k not in ix:
            print("✗ 缺欄位：", k); return 1

    gm = {}
    for r in R[1:]:
        if "GPL" not in str(r[ix["league"]]).upper() or str(r[ix["split"]]) not in ("春季", "夏季"):
            continue
        key = (r[ix["split"]], r[ix["date"]], r[ix["game"]],
               r[ix["blue_teamname"]], r[ix["red_teamname"]])
        gm.setdefault(key, []).append(r)

    hit = miss = wrote = fixed = 0
    misses = []
    for key, rows in gm.items():
        team_row = next((r for r in rows if str(r[ix["participantid"]]) == "100"), None)
        if not team_row:
            miss += 1; misses.append((key, "無隊伍列")); continue
        # 隊伍列的 Lane 欄格式是 |英雄×5|選手×5|（有名字的賽段後五格才有值）→ 不能整串 filter，
        # 要照位置切：1..5 是 TOP/JNG/MID/BOT/SUP 的英雄、6..10 是同順序的選手名
        def _seg(v):
            a = str(v).split("|")
            return (a[1:6], a[6:11]) if len(a) >= 11 else ([x for x in a if x], [])
        bl, bnm = _seg(team_row[ix["blue_Lane"]])
        rl, rnm = _seg(team_row[ix["red_Lane"]])
        if len([x for x in bl if x]) != 5 or len([x for x in rl if x]) != 5:
            miss += 1; misses.append((key, f"路線英雄 {len(bl)}/{len(rl)}")); continue
        bt, rt = G._tk(key[3]), G._tk(key[4])
        k2 = (frozenset((bt, rt)), frozenset(ck(c) for c in bl + rl))
        got = idx.get(k2)
        if not got:
            miss += 1; misses.append((key, "wiki 找不到同一局")); continue
        hit += 1
        lane_of = {}
        for i2, c in enumerate(bl):
            lane_of[("blue", ck(c))] = POS5[i2]
        for i2, c in enumerate(rl):
            lane_of[("red", ck(c))] = POS5[i2]
        # 英雄 → 選手（該局該邊）
        name_of = {}
        for side in ("blue", "red"):
            tm = bt if side == "blue" else rt
            for c in (bl if side == "blue" else rl):
                pos = lane_of.get((side, ck(c)))
                nm = pn((got.get(tm) or {}).get(pos or "", ""))
                if nm:
                    name_of[(side, ck(c))] = nm
        for r in rows:
            is_team = str(r[ix["participantid"]]) == "100"
            for side in ("blue", "red"):
                col = ix[side + "_Lane"]
                seg = str(r[col]).split("|")
                if is_team and len(seg) >= 11:
                    # 隊伍列：|英雄×5|選手×5|
                    for k in range(5):
                        nm = name_of.get((side, ck(seg[1 + k])), "")
                        if nm and seg[6 + k].strip() != nm:
                            fixed += 1 if seg[6 + k].strip() else 0
                            seg[6 + k] = nm; wrote += 1
                    r[col] = "|".join(seg)
                elif not is_team and len(seg) >= 4:
                    # 選手列：英雄A|英雄B|選手A|選手B（同路兩人；單人路是空字串）
                    for k in range(2):
                        nm = name_of.get((side, ck(seg[k])), "")
                        if nm and seg[2 + k].strip() != nm:
                            fixed += 1 if seg[2 + k].strip() else 0
                            seg[2 + k] = nm; wrote += 1
                    r[col] = "|".join(seg)
                if not is_team:
                    # 舊值可能是「整個賽事套同一組五人」的靜態名單（會忽略輪換：Manila Eagles
                    # 春季的 Chock 被灌成 14 場、名單其實只有 9 場）→ 逐局資料優先，直接覆蓋。
                    nm = name_of.get((side, ck(r[ix[side + "_champion"]])), "")
                    old = str(r[ix[side + "_playername"]]).strip()
                    if nm and old != nm:
                        fixed += 1 if old else 0
                        r[ix[side + "_playername"]] = nm
                        wrote += 1
    # ── ④ 我補過的名字，在整個 GPL 內統一拼法 ──
    # 隊伍小框是「同一顆 chip 把該隊所有 GPL 賽段加總」，所以 bebe／Bebe 並存會被列成兩個人
    # （TPA 中路出現 Bebe(2)、下路 bebe(24)）。只動我補過的那些名字，其他聯賽的既有不一致不碰。
    # 基準：春夏（剛補的，已對齊過）優先；其餘 GPL 賽段的衝突取最常見的拼法
    # （GuRuCat 4 vs GuruCat 25 落在 TESL／台港澳，跟春夏無關但一樣會被列成兩個人）。
    gpl_cnt = _c.defaultdict(_c.Counter)
    for r in R[1:]:
        if "GPL" not in str(r[ix["league"]]).upper():
            continue
        for k in ("blue_playername", "red_playername"):
            v = str(r[ix[k]]).strip()
            if v:
                gpl_cnt[v.casefold()][v] += 1
    mine = {k: v.most_common(1)[0][0] for k, v in gpl_cnt.items()}
    for rows in gm.values():
        for r in rows:
            for k in ("blue_playername", "red_playername"):
                v = str(r[ix[k]]).strip()
                if v:
                    mine[v.casefold()] = v
    uni = 0
    for r in R[1:]:
        if "GPL" not in str(r[ix["league"]]).upper():
            continue
        for side in ("blue", "red"):
            v = str(r[ix[side + "_playername"]]).strip()
            want = mine.get(v.casefold())
            if v and want and v != want:
                r[ix[side + "_playername"]] = want; uni += 1
            col = ix[side + "_Lane"]
            seg = str(r[col]).split("|")
            ch = False
            for k in range(len(seg)):
                w2 = mine.get(seg[k].strip().casefold())
                if seg[k].strip() and w2 and seg[k] != w2 and not ck(seg[k]) in canon:
                    seg[k] = w2; ch = True; uni += 1
            if ch:
                r[col] = "|".join(seg)
    if uni:
        print(f"   拼法統一（GPL 內）：{uni} 格")
    print(f"\n== 資料檔比對：{len(gm)} 場｜對上 {hit}／落空 {miss}｜可寫入名字 {wrote} 格（其中修正舊值 {fixed} 格）")
    for k, why in misses[:12]:
        print(f"   · {k[0]} {str(k[1])[:10]} g{k[2]} {k[3]} vs {k[4]}：{why}")
    if len(misses) > 12:
        print(f"   …另外 {len(misses)-12} 場")

    if a.write and (wrote or uni):
        io.open(p, "w", encoding="utf-8").write(
            "window.LOL_DATA=" + json.dumps(D, ensure_ascii=False) + ";")
        print(f"✓ 已寫入 {p}")
    elif not a.write:
        print("（乾跑，未寫入；加 --write 實寫）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
