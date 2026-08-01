# -*- coding: utf-8 -*-
"""移除「同一局被 Match History 與 Picks and Bans 各收一次」的 PB 副本。

怎麼發生的：兩個來源都寫進 csv_cache/wikifill_{年}.json，fetch_data.merge_wiki() 的
去重鍵含**日期**（`str(r[iD])[:10]`），而 PB 頁沒有逐場日期、日期是依賽事期間**推算**的
（fetch_wiki_pb 用階段順序內插），跟 MH 的真實日期對不上 → 第二層「同一局＝十隻英雄」
的判定被日期擋在門外，同一場就收了兩份。
實測 2015 GPL：春季 240 場裡 83 場、夏季 122 場裡 23 場是重複。

PB 副本的特徵（三個一起看才動手）：
  ・同聯賽、同兩隊、同十隻英雄、同一方獲勝
  ・自己**沒有 gamelength**，正本有 → 正本來自 MH（帶時長、時間戳、完整名單）
  ・選手名多半是「整個賽事套同一組五人」的靜態名單推的，常常是錯的
    （2015-06-25 那局 MH 是 Sena／Sunny，PB 副本寫成 Jinkey／FYF）

用法：python scripts/dedup_pb_copies.py --year 2015              （乾跑）
      python scripts/dedup_pb_copies.py --year 2015 --write
      python scripts/dedup_pb_copies.py --all                     （全年份掃描，只報告）

⚠ 根治要改 fetch_data.merge_wiki() 的去重鍵（同聯賽＋同十隻英雄＋日期相近就算同一局），
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
    """→ (D, 要刪的列集合 id, 報告)"""
    D = load(path)
    R = D["tabs"]["RAW_DATA"]
    ix = {n: i for i, n in enumerate(R[0])}
    need = ("league", "split", "date", "game", "participantid", "blue_teamname",
            "red_teamname", "blue_champion", "red_champion", "result", "blue_gamelength")
    if any(k not in ix for k in need):
        return D, set(), collections.Counter()
    games = collections.defaultdict(list)
    for r in R[1:]:
        games[(str(r[ix["league"]]), str(r[ix["split"]]), str(r[ix["date"]]), str(r[ix["game"]]),
               str(r[ix["blue_teamname"]]), str(r[ix["red_teamname"]]))].append(r)

    def info(rows):
        chs = sorted(ck(c) for r in rows for c in (r[ix["blue_champion"]], r[ix["red_champion"]])
                     if str(c).strip())
        gl = any(str(r[ix["blue_gamelength"]]).strip() for r in rows)
        nm = sum(1 for r in rows for s2 in ("blue", "red")
                 if str(r[ix[s2 + "_playername"]]).strip())
        return chs, gl, nm

    sig = collections.defaultdict(list)
    for k, rows in games.items():
        chs, gl, nm = info(rows)
        if len(chs) != 10:
            continue
        # 勝方用隊名而不是藍/紅：兩份的藍紅可能顛倒
        win = k[4] if str(rows[0][ix["result"]]) == "1" else k[5]
        sig[(k[0], frozenset((ck(k[4]), ck(k[5]))), tuple(chs), ck(win))].append((k, rows, gl, nm))

    drop, rep = set(), collections.Counter()
    for key, lst in sig.items():
        if len(lst) < 2:
            continue
        keep = [x for x in lst if x[2]]          # 有時長＝MH 正本
        toss = [x for x in lst if not x[2]]      # 沒時長＝PB 副本
        if not keep or not toss:
            rep[(key[0], "無法判斷（時長都有或都無）")] += len(lst) - 1
            continue
        if len(keep) > 1:                        # 正本不只一份 → 不動，留給人看
            rep[(key[0], "正本多於一份")] += len(keep) - 1
        for k, rows, _gl, _nm in toss:
            for r in rows:
                drop.add(id(r))
            rep[(key[0], k[1])] += 1
            if verbose and rep[(key[0], k[1])] <= 2:
                print(f"     刪 {k[0]} {k[1]} {k[2][:10]} g{k[3]} {k[4]} vs {k[5]}"
                      f"（正本 {keep[0][0][2][:10]}）")
    return D, drop, rep


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
        D, drop, rep = scan(p, verbose=not a.all)
        if not rep:
            if not a.all:
                print(f"== {y}：沒有找到 PB 副本")
            continue
        print(f"== {y}：要刪 {len(drop)} 列")
        for k, n in sorted(rep.items()):
            print(f"   {k[0]} {k[1]}：{n} 場")
        if a.write and drop and not a.all:
            R = D["tabs"]["RAW_DATA"]
            D["tabs"]["RAW_DATA"] = [R[0]] + [r for r in R[1:] if id(r) not in drop]
            io.open(p, "w", encoding="utf-8").write(
                "window.LOL_DATA=" + json.dumps(D, ensure_ascii=False) + ";")
            print(f"✓ 已寫入 {p}（{len(R)-1} → {len(D['tabs']['RAW_DATA'])-1} 列）")
    if not a.write:
        print("（乾跑，未寫入；加 --write 實寫）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
