# -*- coding: utf-8 -*-
"""用 Leaguepedia Match History 的逐局名單，補上資料檔缺的選手名。

適用情境：某些賽段的列是 fetch_wiki_pb.py 從 Picks and Bans 頁產的——只有英雄沒有選手名
（圖鑑→賽事的隊伍小框因此只有隊名、沒有「選手(場數)」）。這些賽事若在
`Special:RunQuery/MatchHistoryGame` 查得到，MH 會直接給 `Blue Roster`／`Red Roster`，
而且**順序跟 Picks 一致**（第 n 個選手＝第 n 手英雄的使用者），連路線都不用推。

比 2013 GPL 那套（scripts/fill_gpl2013_players.py，從 {{ExtendedRoster}} 的 r= 旗標
逐字元推）可靠得多，有 MH 就優先用 MH。

用法：python scripts/fill_players_from_mh.py            （乾跑）
      python scripts/fill_players_from_mh.py --write    （實寫）
      python scripts/fill_players_from_mh.py --job 2015GPL夏季

⚠ 這是「補在成品上」：抓取管線重跑 data_{年}.js 之後要再跑一次。
   長遠解是把這些賽事登記進 fetch_wiki_mh 的工作清單（wikifill_{年}.json）。
"""
import io, os, re, sys, json, argparse, importlib.util, collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("mh", os.path.join(HERE, "fetch_wiki_mh.py"))
MH = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(MH)

# (年, 聯賽, 賽段, 來源)
# 來源有兩種：MatchHistoryGame 的 tournament 名；或 "embed:{頁名}"＝賽事的 /Match History 子頁
#（有些賽事在 MHG[tournament] 查不到，但子頁有表，例如 LJL 的升降賽）
# ⚠ LJL 的升降賽頁名是用「升上去的那個賽段」命名：我們資料裡 2016-08 打的那批，
#   在 wiki 上叫 2017 Season/Spring Promotion（2016 Season/Summer Promotion 是 3~4 月那批）。
# 來源可以給多個（一個賽段的比賽散在主賽事＋季後賽等多個 wiki 賽事裡），會合併成同一個索引
JOBS = [(2015, "GPL", "春季", ["2015 GPL Spring", "2015 GPL Spring Playoffs"]),
        (2015, "GPL", "夏季", ["2015 GPL Summer", "2015 GPL Summer Playoffs"]),
        (2016, "LJL", "升降賽", "embed:LJL/2017 Season/Spring Promotion/Match History")]


def ck(s):
    """英雄／隊名比對鍵：只留英數字（Cho'Gath↔Chogath、Rek'Sai↔RekSai）"""
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def load_data(p):
    s = io.open(p, encoding="utf-8").read()
    return json.loads(s[s.index("=") + 1:].strip().rstrip(";"))


def clean_name(n):
    # 「Moss (Sorawat Boonphrom)」→ Moss；MH 有些格會把本名寫在括號裡
    return re.sub(r"\s*\(.*?\)\s*$", "", str(n or "")).strip()


def mh_index(tours, force=False):
    """→ {(隊名集合, 十隻英雄集合): {隊名鍵: {英雄鍵: 選手}}}"""
    if isinstance(tours, str):
        tours = [tours]
    games = []
    for t in tours:
        html = (MH.fetch_embed(t[6:], force=force) if t.startswith("embed:")
                else MH.fetch(t, force=force))
        if html:
            games += MH.parse(html)[1]
    idx, bad, pos_idx = {}, 0, {}
    for g in games:
        bt, rt = str(g.get("Blue") or ""), str(g.get("Red") or "")
        pk = [x.strip() for x in str(g.get("Picks") or "").split(",") if x.strip()]
        pk2 = [x.strip() for x in str(g.get("Picks2") or "").split(",") if x.strip()]
        ro = [clean_name(x) for x in str(g.get("Blue Roster") or "").split(",") if x.strip()]
        ro2 = [clean_name(x) for x in str(g.get("Red Roster") or "").split(",") if x.strip()]
        # 有些 /Match History 子頁沒有選角欄（LJL 升降賽就是）→ 退而用「日期＋對戰隊伍」對，
        # 名單順序即 TOP/JNG/MID/BOT/SUP，照 participantid 指派。
        # 只在該日該對戰的每一局名單都相同時才用，否則分不出是哪一局。
        if bt and rt and len(ro) == 5 and len(ro2) == 5:
            dk = (str(g.get("Date") or "")[:10], ck(bt), ck(rt))
            cur = (tuple(ro), tuple(ro2))
            pos_idx[dk] = cur if pos_idx.get(dk, cur) == cur else None
        if not (bt and rt) or len(pk) != 5 or len(pk2) != 5 or len(ro) != 5 or len(ro2) != 5:
            bad += 1; continue
        key = (frozenset((ck(bt), ck(rt))), frozenset(ck(c) for c in pk + pk2))
        idx[key] = {ck(bt): {ck(c): ro[i] for i, c in enumerate(pk)},
                    ck(rt): {ck(c): ro2[i] for i, c in enumerate(pk2)}}
    return idx, len(games), bad, {k: v for k, v in pos_idx.items() if v}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--job", default="")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    jobs = [j for j in JOBS if not a.job or a.job in f"{j[0]}{j[1]}{j[2]}"]
    by_year = collections.defaultdict(list)
    for j in jobs:
        by_year[j[0]].append(j)

    for year, js in sorted(by_year.items()):
        p = os.path.join(ROOT, "data", f"data_{year}.js")
        D = load_data(p)
        R = D["tabs"]["RAW_DATA"]
        ix = {n: i for i, n in enumerate(R[0])}
        total_wrote = 0
        for _y, lg, sp, tour in js:
            idx, ngame, bad, pidx = mh_index(tour, a.force)
            print(f"== {year} {lg} {sp}｜MH「{tour if isinstance(tour,str) else '＋'.join(tour)}」{ngame} 局，可用 {len(idx)}"
                  + (f"（{bad} 局欄位不齊，略過）" if bad else ""))
            gm = collections.defaultdict(list)
            for r in R[1:]:
                if str(r[ix["league"]]) != lg or str(r[ix["split"]]) != sp:
                    continue
                gm[(str(r[ix["date"]]), str(r[ix["game"]]),
                    str(r[ix["blue_teamname"]]), str(r[ix["red_teamname"]]))].append(r)
            hit = miss = wrote = conflict = 0
            misses = []
            confs = collections.Counter()
            for key, rows in gm.items():
                team_row = next((r for r in rows if str(r[ix["participantid"]]) == "100"), None)
                chs = [c for c in ([str(r[ix["blue_champion"]]) for r in rows] +
                                   [str(r[ix["red_champion"]]) for r in rows]) if c.strip()]
                if len(chs) != 10:
                    miss += 1; misses.append((key, f"英雄 {len(chs)} 隻")); continue
                k2 = (frozenset((ck(key[2]), ck(key[3]))), frozenset(ck(c) for c in chs))
                got = idx.get(k2)
                by_pos = None
                if not got:
                    by_pos = (pidx.get((key[0][:10], ck(key[2]), ck(key[3])))
                              or (lambda v: (v[1], v[0]) if v else None)(
                                  pidx.get((key[0][:10], ck(key[3]), ck(key[2])))))
                if not got and not by_pos:
                    miss += 1; misses.append((key, "MH 找不到同一局")); continue
                hit += 1
                nm_of = {}
                if got:
                    for side, tn in (("blue", key[2]), ("red", key[3])):
                        for c, pl in (got.get(ck(tn)) or {}).items():
                            nm_of[(side, c)] = pl
                if by_pos:      # 沒有選角可比 → 依 participantid（1-5＝TOP~SUP）指派
                    for r in rows:
                        pid = str(r[ix["participantid"]])
                        if pid in ("1", "2", "3", "4", "5"):
                            k3 = int(pid) - 1
                            for side, five in (("blue", by_pos[0]), ("red", by_pos[1])):
                                nm_of[(side, ck(r[ix[side + "_champion"]]))] = five[k3]
                for r in rows:
                    is_team = str(r[ix["participantid"]]) == "100"
                    for side in ("blue", "red"):
                        col = ix[side + "_Lane"]
                        seg = str(r[col]).split("|")
                        ch = False
                        if is_team and len(seg) >= 11:      # 隊伍列：|英雄×5|選手×5|
                            for k in range(5):
                                nm = nm_of.get((side, ck(seg[1 + k])), "")
                                if nm and not seg[6 + k].strip():
                                    seg[6 + k] = nm; ch = True; wrote += 1
                        elif not is_team and len(seg) >= 4:  # 選手列：英雄A|英雄B|選手A|選手B
                            for k in range(2):
                                nm = nm_of.get((side, ck(seg[k])), "")
                                if nm and not seg[2 + k].strip():
                                    seg[2 + k] = nm; ch = True; wrote += 1
                        if ch:
                            r[col] = "|".join(seg)
                        if not is_team:
                            # 只填空格。既有值一律保留：wiki 顯示的是選手**現用 ID**、
                            # OE 保留當年 ID（2016 LJL 實測 Mei→wiki 寫 Vivy、Zerost→Swizzle），
                            # 覆蓋等於把當年的名字改成後來的，會跟其他年份對不起來。
                            nm = nm_of.get((side, ck(r[ix[side + "_champion"]])), "")
                            old = str(r[ix[side + "_playername"]]).strip()
                            if nm and not old:
                                r[ix[side + "_playername"]] = nm; wrote += 1
                            elif nm and old != nm:
                                conflict += 1; confs[f"{old}→{nm}"] += 1
            print(f"   資料檔 {len(gm)} 場｜對上 {hit}／落空 {miss}｜填入空格 {wrote}")
            if conflict:
                print(f"   ℹ 既有值與 wiki 不同（保留既有）{conflict} 格："
                      + "、".join(f"{k}×{v}" for k, v in confs.most_common(6)))
            for k, why in misses[:8]:
                print(f"   · {k[0][:10]} g{k[1]} {k[2]} vs {k[3]}：{why}")
            if len(misses) > 8:
                print(f"   …另外 {len(misses)-8} 場")
            total_wrote += wrote
        if a.write and total_wrote:
            io.open(p, "w", encoding="utf-8").write(
                "window.LOL_DATA=" + json.dumps(D, ensure_ascii=False) + ";")
            print(f"✓ 已寫入 {p}")
        elif not a.write:
            print("（乾跑，未寫入；加 --write 實寫）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
