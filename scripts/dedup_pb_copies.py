# -*- coding: utf-8 -*-
"""移除「同一局被 Match History 與 Picks and Bans 各收一次」的 PB 副本，並統一隊名別名。

怎麼發生的：兩個來源都寫進 csv_cache/wikifill_{年}.json，fetch_data.merge_wiki() 的
去重鍵含**日期＋隊名**，而 PB 頁沒有逐場日期（依賽事期間推算）、隊名又常用自己的縮寫
（我們資料裡同一支隊同時有 Wargods／WGD／Wazabi Gaming 三種寫法）→ 兩層判定都對不上，
同一場就收了兩份。實測 2015 GPL：春季 240 場裡 92 場、夏季 122 場裡 42 場是重複。

判「同一局」不用隊名，用**選角本身**：
    同聯賽＋同賽段＋勝方五隻英雄＋敗方五隻英雄  完全相同
（只比十隻的集合會誤判——2015 春季有兩場十隻相同但分邊不同，其中一場是
 Jakarta Juggernauts vs Saigon Jokers、另一場是 Full Louis vs Jakarta Juggernauts，
 顯然不是同一局。加上「哪五隻贏」就分得開。）

隊名不同時的把關（兩趟）：
  ① 先只採信「其中一邊隊名完全相同」的配對 → 學到別名（WGD＝Wargods、MSK＝Mineski…）
  ② 再用學到的別名去收兩邊都是別名的配對（GFL/IMP e-Sports ＝ Full Louis/Impunity Legends）
  ③ 兩邊都對不上、或跟已學到的別名衝突 → 不動，列出來給人看
     （WGD vs Asus ImbaFate ↔ Diamond Team vs Hanoi Fate 就是靠這條擋掉的：
      WGD 已經學到是 Wargods，不可能又是 Diamond Team）

刪哪一份：沒有 gamelength 的那份＝PB 副本（正本來自 MH，帶真實時間、時長、完整名單）。
PB 副本的選手名多半是「整個賽事套同一組五人」的靜態名單推的，常常是錯的
（2015-06-25 那局 MH 是 Sena／Sunny，PB 副本寫成 Jinkey／FYF）。

用法：python scripts/dedup_pb_copies.py --year 2015              （乾跑）
      python scripts/dedup_pb_copies.py --year 2015 --write
      python scripts/dedup_pb_copies.py --all                     （全年份，只報告）

⚠ 根治要改 fetch_data.merge_wiki() 的去重鍵（改用選角當「同一局」的判準，不要靠日期與隊名），
   那是抓取管線的檔；在那之前，管線重跑 data_{年}.js 之後要再跑一次本檔。
"""
import io, os, re, sys, json, glob, argparse, collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ck(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def load(p):
    s = io.open(p, encoding="utf-8").read()
    return json.loads(s[s.index("=") + 1:].strip().rstrip(";"))


def scan(path, verbose=True):
    D = load(path)
    R = D["tabs"]["RAW_DATA"]
    ix = {n: i for i, n in enumerate(R[0])}
    need = ("league", "split", "date", "game", "participantid", "blue_teamname",
            "red_teamname", "blue_champion", "red_champion", "result", "blue_gamelength")
    if any(k not in ix for k in need):
        return D, set(), collections.Counter(), {}, []

    games = collections.defaultdict(list)
    for r in R[1:]:
        games[(str(r[ix["league"]]), str(r[ix["split"]]), str(r[ix["date"]]), str(r[ix["game"]]),
               str(r[ix["blue_teamname"]]), str(r[ix["red_teamname"]]))].append(r)

    sig = collections.defaultdict(list)
    for k, rows in games.items():
        b = frozenset(ck(r[ix["blue_champion"]]) for r in rows if str(r[ix["blue_champion"]]).strip())
        rd = frozenset(ck(r[ix["red_champion"]]) for r in rows if str(r[ix["red_champion"]]).strip())
        if len(b) != 5 or len(rd) != 5 or b & rd:
            continue
        blue_win = str(rows[0][ix["result"]]) == "1"
        win, lose = (b, rd) if blue_win else (rd, b)
        gl = any(str(r[ix["blue_gamelength"]]).strip() for r in rows)
        # 勝方隊名／敗方隊名（藍紅顛倒也一致）
        wt, lt = (k[4], k[5]) if blue_win else (k[5], k[4])
        sig[(k[0], k[1], win, lose)].append({"k": k, "rows": rows, "gl": gl, "wt": wt, "lt": lt})

    pairs = [v for v in sig.values() if len(v) > 1]

    # ── 兩趟學別名 ──
    alias = {}          # 別名鍵 → 正式名
    def canon(n):
        return alias.get(ck(n), n)

    def learn(a, b):
        """a、b 是同一組的兩筆；回傳 True＝可判定同一局"""
        same_w, same_l = ck(a["wt"]) == ck(b["wt"]), ck(a["lt"]) == ck(b["lt"])
        if same_w and same_l:
            return True
        if same_w or same_l:                      # 一邊相同 → 另一邊學成別名
            x, y = (a["lt"], b["lt"]) if same_w else (a["wt"], b["wt"])
            keep, drop = (x, y) if a["gl"] else (y, x)      # 有時長那份的隊名當正式名
            if ck(drop) in alias and ck(alias[ck(drop)]) != ck(keep):
                return False                      # 跟已學到的衝突
            alias[ck(drop)] = keep
            return True
        return False

    for _ in range(2):                            # 跑兩趟：第二趟才收「兩邊都是別名」的
        for v in pairs:
            for i in range(1, len(v)):
                if ck(canon(v[0]["wt"])) == ck(canon(v[i]["wt"])) and \
                   ck(canon(v[0]["lt"])) == ck(canon(v[i]["lt"])):
                    continue
                learn(v[0], v[i])

    drop, rep, rejected = set(), collections.Counter(), []
    for v in pairs:
        ok = all(ck(canon(v[0]["wt"])) == ck(canon(x["wt"])) and
                 ck(canon(v[0]["lt"])) == ck(canon(x["lt"])) for x in v[1:])
        if not ok:
            rejected.append([(x["k"][2][:10], x["wt"], x["lt"]) for x in v]); continue
        keep = [x for x in v if x["gl"]]
        toss = [x for x in v if not x["gl"]]
        if not keep or not toss:
            rep[(v[0]["k"][0], "無法判斷（時長都有或都無）")] += len(v) - 1; continue
        if len(keep) > 1:
            rep[(v[0]["k"][0], "正本多於一份")] += len(keep) - 1
        for x in toss:
            for r in x["rows"]:
                drop.add(id(r))
            rep[(x["k"][0], x["k"][1])] += 1
            if verbose and rep[(x["k"][0], x["k"][1])] <= 2:
                print(f"     刪 {x['k'][0]} {x['k'][1]} {x['k'][2][:10]} g{x['k'][3]} "
                      f"{x['k'][4]} vs {x['k'][5]}（正本 {keep[0]['k'][2][:10]} "
                      f"{keep[0]['k'][4]} vs {keep[0]['k'][5]}）")
    return D, drop, rep, alias, rejected


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    paths = (sorted(glob.glob(os.path.join(ROOT, "data", "data_*.js"))) if a.all
             else [os.path.join(ROOT, "data", f"data_{a.year}.js")])
    for p in paths:
        y = os.path.basename(p)[5:9]
        D, drop, rep, alias, rejected = scan(p, verbose=not a.all)
        if not rep and not rejected:
            if not a.all:
                print(f"== {y}：沒有找到 PB 副本")
            continue
        print(f"== {y}：要刪 {len(drop)} 列")
        for k, n in sorted(rep.items()):
            print(f"   {k[0]} {k[1]}：{n} 場")
        if alias:
            print("   學到的隊名別名：" + "、".join(f"{k}→{v}" for k, v in sorted(alias.items())))
        for v in rejected:
            print("   ⚠ 隊名對不上，未處理：" + "　".join(f"{d} {w} 勝 {l}" for d, w, l in v))
        if a.write and drop and not a.all:
            R = D["tabs"]["RAW_DATA"]
            D["tabs"]["RAW_DATA"] = [R[0]] + [r for r in R[1:] if id(r) not in drop]
            # 剩下的 PB-only 列也把隊名統一（不然戰隊分頁會出現 WGD 與 Wargods 兩支）
            R2 = D["tabs"]["RAW_DATA"]
            fixed = 0
            for r in R2[1:]:
                for c in ("blue_teamname", "red_teamname"):
                    v = str(r[ix_get(R2, c)]).strip()
                    if ck(v) in alias and alias[ck(v)] != v:
                        r[ix_get(R2, c)] = alias[ck(v)]; fixed += 1
            if fixed:
                print(f"   隊名統一：{fixed} 格")
            io.open(p, "w", encoding="utf-8").write(
                "window.LOL_DATA=" + json.dumps(D, ensure_ascii=False) + ";")
            print(f"✓ 已寫入 {p}（{len(R)-1} → {len(R2)-1} 列）")
    if not a.write:
        print("（乾跑，未寫入；加 --write 實寫）")
    return 0


_IXC = {}
def ix_get(R, name):
    if id(R) not in _IXC:
        _IXC[id(R)] = {n: i for i, n in enumerate(R[0])}
    return _IXC[id(R)][name]


if __name__ == "__main__":
    sys.exit(main())
