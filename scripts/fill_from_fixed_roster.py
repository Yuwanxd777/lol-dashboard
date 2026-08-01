# -*- coding: utf-8 -*-
"""名單頁裡「整個賽段固定五人」的隊伍，直接把名字填進缺的場次。

適用剩下的邊角：某隊的比賽 Match History 沒收錄（只有 Picks and Bans 的列，沒有選手名），
但 `{賽事}/Team Rosters` 顯示這隊整季**每個位置都只有一個人**——沒有輪換就沒有
「這局是誰上」的問題，不需要像 fetch_gpl2013_players 那樣逐局對齊旗標。
有輪換的隊（Full Louis 春季打野掛了 KingOfWar／Calvin／SofM 三個人）一律跳過。

列與位置的對應：PB 產的列 participantid 1-5＝TOP/JNG/MID/BOT/SUP（fetch_wiki_pb 的
_POS_OE[POSL[k2]]），所以 pid 直接對到名單的位置。

用法：python scripts/fill_from_fixed_roster.py            （乾跑）
      python scripts/fill_from_fixed_roster.py --write

⚠ 補在成品上，管線重跑 data_{年}.js 之後要再跑一次。
"""
import io, os, re, sys, json, argparse, importlib.util, collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
_s = importlib.util.spec_from_file_location("gpl", os.path.join(HERE, "fetch_gpl2013_players.py"))
G = importlib.util.module_from_spec(_s); _s.loader.exec_module(G)

POS5 = ["TOP", "JNG", "MID", "BOT", "SUP"]
# (年, 聯賽, 賽段, 名單頁, {名單頁的隊名鍵: 資料檔的隊名})
#  名單頁用縮寫當標題，跟資料檔的全名對不上時在這裡指定
JOBS = [
    (2015, "GPL", "春季", "2015 GPL Spring/Team Rosters", {}),
    (2015, "GPL", "夏季", "2015 GPL Summer/Team Rosters", {"fate": "Asus ImbaFate"}),
]


def ck(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def load_data(p):
    s = io.open(p, encoding="utf-8").read()
    return json.loads(s[s.index("=") + 1:].strip().rstrip(";"))


def fixed_fives(page, namemap):
    """→ {資料檔隊名鍵: {位置: 選手}}，只收「每個位置剛好一人」的隊"""
    ros, _ = G.parse_rosters(page)
    out = {}
    for ab, team in ros.items():
        five = {}
        for pos in POS5:
            pl = list(team.get(pos, {}))
            if len(pl) != 1:
                five = None; break
            five[pos] = pl[0]
        if five:
            out[ck(namemap.get(ab, ab))] = five
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    by_year = collections.defaultdict(list)
    for j in JOBS:
        by_year[j[0]].append(j)
    for year, js in sorted(by_year.items()):
        p = os.path.join(ROOT, "data", f"data_{year}.js")
        D = load_data(p)
        R = D["tabs"]["RAW_DATA"]
        ix = {n: i for i, n in enumerate(R[0])}
        wrote = 0
        for _y, lg, sp, page, nm in js:
            five = fixed_fives(page, nm)
            print(f"== {year} {lg} {sp}｜固定五人的隊 {len(five)}：{'、'.join(sorted(five))}")
            gm = collections.defaultdict(list)
            for r in R[1:]:
                if str(r[ix["league"]]) != lg or str(r[ix["split"]]) != sp:
                    continue
                gm[(str(r[ix["date"]]), str(r[ix["game"]]),
                    str(r[ix["blue_teamname"]]), str(r[ix["red_teamname"]]))].append(r)
            for key, rows in gm.items():
                for side, tn in (("blue", key[2]), ("red", key[3])):
                    lineup = five.get(ck(tn))
                    if not lineup:
                        continue
                    hit = 0
                    for r in rows:
                        pid = str(r[ix["participantid"]])
                        if pid not in ("1", "2", "3", "4", "5"):
                            continue
                        want = lineup[POS5[int(pid) - 1]]
                        if not str(r[ix[side + "_playername"]]).strip():
                            r[ix[side + "_playername"]] = want; wrote += 1; hit += 1
                    if hit:
                        print(f"   填 {key[0][:10]} g{key[1]} {tn}："
                              + "／".join(lineup[q] for q in POS5))
        if a.write and wrote:
            io.open(p, "w", encoding="utf-8").write(
                "window.LOL_DATA=" + json.dumps(D, ensure_ascii=False) + ";")
            print(f"✓ 已寫入 {p}（填 {wrote} 格）")
        else:
            print(f"（{'乾跑' if not a.write else '無可填'}，共可填 {wrote} 格）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
