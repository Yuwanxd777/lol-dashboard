# -*- coding: utf-8 -*-
"""同名選手偵測（同 ID 但其實是不同人）。

為什麼需要：build_career.py 的生涯聚合用「選手名字串」當唯一 key，
同 ID 的不同人會被無聲合併成一份生涯（場數/勝率/角色池全部混在一起）。
資料每年增長，新賽區（LTA/LCP/EWC）進來後撞名只會更多，所以要有自動守門。

判準（分數越高越可能是不同人）：
  A 同一天同名出現在兩支不同隊伍   → 鐵證（+10）
  B 跨「大區」且出賽區間完全不重疊 → 轉會 or 不同人（每多跨一區 +2）
  C 生涯中間空窗 N 年              → 空窗越久越可疑（+N，上限 8）
  D 主要位置改變                   → +3
單純同大區轉隊、國際賽（Worlds/MSI/EWC/KeSPA 盃）不列入賽區判斷。

已人工審定的名字寫進 scripts/player_disambig.json 就不再報：
  "reviewed" = 確認同一人（誤報，永久靜音）
  "persons"  = 確認不同人（已拆分，見該檔說明）

用法：
  python scripts/check_player_dup.py            # 只報未審定的可疑名單
  python scripts/check_player_dup.py --all      # 連已審定的一起列
  python scripts/check_player_dup.py --json out.json   # 完整明細另存
  python scripts/check_player_dup.py --quiet    # 只印摘要（給 update.bat 用）
永遠 exit 0：這是提醒，不阻擋發布。
"""
import glob, io, json, os, re, sys, collections

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIS = os.path.join(ROOT, "scripts", "player_disambig.json")
POS = {1: "TOP", 2: "JNG", 3: "MID", 4: "BOT", 5: "SUP"}

# 國際賽／盃賽不代表賽區歸屬，納入會讓同一人看起來「跨區」
INTL = {"WLDs", "MSI", "EWC", "KeSPA", "IEM", "Rift", "ASCI", "WCG", "IWCI", "IWCQ", "AS", "Demacia", "IC"}
# 大區歸群：同群內換隊是正常轉會，不算可疑
GROUP = {
    "LCK": "KR", "LCKCL": "KR",
    "LPL": "CN", "LDL": "CN",
    "LEC": "EU", "EM": "EU", "LFL": "EU", "PRM": "EU", "SL": "EU", "UL": "EU",
    "NLC": "EU", "LVP": "EU", "EBL": "EU", "HM": "EU", "TCL": "EU", "LCL": "EU",
    "LCS": "NA", "NACL": "NA", "NA": "NA", "LTA N": "NA", "LTAN": "NA",
    "PCS": "APAC", "LMS": "APAC", "GPL": "APAC", "LCP": "APAC", "VCS": "APAC",
    "LJL": "APAC", "LCO": "APAC", "OPL": "APAC",
    "CBLOL": "LATAM", "LLA": "LATAM", "LLN": "LATAM", "CLS": "LATAM",
    "LTA": "LATAM", "LTA S": "LATAM", "LTAS": "LATAM", "CD": "LATAM",
}
THRESHOLD = 10          # 分數 >= 此值才報（低於此值多為單純轉會）


def _grp(lg):
    return GROUP.get(lg, lg)


def load_disambig():
    if not os.path.exists(DIS):
        return {}, set()
    try:
        d = json.load(open(DIS, encoding="utf-8"))
    except Exception as e:
        print(f"⚠ player_disambig.json 讀取失敗（當成空表）：{e}")
        return {}, set()
    entries = {k: v for k, v in d.items() if not k.startswith("_")}
    silent = {k for k, v in entries.items() if v.get("reviewed") or v.get("persons")}
    return entries, silent


def scan():
    """回傳 name -> {segs:[...], sameday:[...]}"""
    seg = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, "9999", ""]))
    sameday = collections.defaultdict(set)
    for dp in sorted(glob.glob(os.path.join(ROOT, "data", "data_*.js"))):
        ym = re.search(r"data_(\d{4})\.js$", dp)
        if not ym:
            continue
        year = ym.group(1)
        try:
            J = json.loads(open(dp, encoding="utf-8").read().split("=", 1)[1].strip().rstrip(";"))
            R = J["tabs"]["RAW_DATA"]; h = R[0]
        except Exception as e:
            print(f"⚠ {os.path.basename(dp)} 解析失敗，略過：{e}")
            continue
        ix = {n: i for i, n in enumerate(h)}
        if any(n not in ix for n in ("participantid", "blue_teamname", "blue_playername", "date", "blue_champion", "red_champion")):
            print(f"⚠ {os.path.basename(dp)} 欄位不符，略過")
            continue
        RB = ix["red_champion"] - ix["blue_champion"]
        pi, dt, lg = ix["participantid"], ix["date"], ix.get("league")
        bt, bp = ix["blue_teamname"], ix["blue_playername"]
        for r in R[1:]:
            try:
                p = int(r[pi])
            except Exception:
                continue
            if p not in POS:
                continue
            d = str(r[dt])[:10]
            league = str(r[lg]) if lg is not None and r[lg] else "?"
            for side in (0, 1):
                off = RB if side else 0
                team, name = r[bt + off], r[bp + off]
                if not team or not name:
                    continue
                name = str(name).strip()
                # 與 build_career.py 相同的清理：OE 偶發把名字寫成「隊縮寫␣ID」
                cmp_ = re.sub(r"[^A-Za-z0-9]", "", str(team))
                if cmp_ and name.startswith(cmp_ + " ") and len(name) > len(cmp_) + 1:
                    name = name[len(cmp_) + 1:]
                e = seg[name][(year, league, str(team), POS[p])]
                e[0] += 1
                if d and d < e[1]:
                    e[1] = d
                if d > e[2]:
                    e[2] = d
                if d:
                    sameday[(name, d)].add(str(team))
    conflicts = collections.defaultdict(list)
    for (name, d), tms in sameday.items():
        if len(tms) > 1:
            conflicts[name].append({"date": d, "teams": sorted(tms)})
    out = {}
    for name, ks in seg.items():
        segs = [{"y": k[0], "lg": k[1], "tm": k[2], "pos": k[3], "n": v[0], "f": v[1], "l": v[2]}
                for k, v in ks.items()]
        segs.sort(key=lambda s: s["f"])
        out[name] = {"segs": segs, "sameday": sorted(conflicts.get(name, []), key=lambda x: x["date"])}
    return out


def score(name, info):
    """回傳 (分數, 理由列表)"""
    segs, sd = info["segs"], info["sameday"]
    sc, why = 0, []
    if sd:
        sc += 10
        why.append(f"同日出現在不同隊 {len(sd)} 次（最早 {sd[0]['date']}：{' / '.join(sd[0]['teams'])}）")
    dom = [s for s in segs if s["lg"] not in INTL]
    groups = {_grp(s["lg"]) for s in dom}
    if len(groups) > 1:
        # 各大區的出賽區間是否重疊
        rng = collections.defaultdict(lambda: ["9999", ""])
        for s in dom:
            e = rng[_grp(s["lg"])]
            if s["f"] < e[0]:
                e[0] = s["f"]
            if s["l"] > e[1]:
                e[1] = s["l"]
        rl = sorted(([g] + v for g, v in rng.items()), key=lambda x: x[1])
        if not any(rl[i][2] >= rl[i + 1][1] for i in range(len(rl) - 1)):
            sc += 2 * (len(groups) - 1)
            why.append("跨大區且區間不重疊：" + "、".join(f"{g}({a[:4]}~{b[:4]})" for g, a, b in rl))
    years = sorted({int(s["y"]) for s in segs})
    gaps = [(years[i], years[i + 1]) for i in range(len(years) - 1) if years[i + 1] - years[i] >= 3]
    if gaps:
        g = max(b - a for a, b in gaps)
        sc += min(g, 8)
        why.append("空窗 " + "、".join(f"{a}→{b}（斷 {b-a} 年）" for a, b in gaps))
    if len({s["pos"] for s in segs}) > 1:
        main = collections.Counter()
        for s in segs:
            main[s["pos"]] += s["n"]
        if len([p for p, n in main.items() if n >= 5]) > 1:
            sc += 3
            why.append("主要位置改變：" + "／".join(f"{p} {n}場" for p, n in main.most_common()))
    return sc, why


def main():
    argv = sys.argv[1:]
    quiet = "--quiet" in argv
    show_all = "--all" in argv
    jout = None
    if "--json" in argv:
        i = argv.index("--json")
        jout = argv[i + 1] if i + 1 < len(argv) else os.path.join(ROOT, "csv_cache", "player_dup.json")

    entries, silent = load_disambig()
    data = scan()
    rows = []
    for name, info in data.items():
        sc, why = score(name, info)
        if sc < THRESHOLD:
            continue
        if name in silent and not show_all:
            continue
        rows.append({"name": name, "score": sc, "why": why,
                     "reviewed": name in silent, "segs": info["segs"], "sameday": info["sameday"]})
    rows.sort(key=lambda r: -r["score"])

    total = len(data)
    if quiet:
        print(f"[check_player_dup] 選手 ID {total} 個，未審定的可疑同名 {len(rows)} 個"
              + ("（跑 python scripts/check_player_dup.py 看明細）" if rows else ""))
    else:
        print(f"選手 ID 總數：{total}　已審定靜音：{len(silent)}　本次可疑：{len(rows)}（門檻 {THRESHOLD} 分）\n")
        for r in rows:
            tag = "［已審定］" if r["reviewed"] else ""
            print("=" * 72)
            print(f"■ {r['name']}　{r['score']} 分 {tag}")
            for w in r["why"]:
                print(f"   ▪ {w}")
            for s in r["segs"]:
                print(f"     {s['y']} {s['lg']:<9} {s['tm'][:28]:<28} {s['pos']} {s['n']:>4}場  {s['f']}~{s['l']}")
        if rows:
            print("=" * 72)
            print("\n判定後請寫進 scripts/player_disambig.json：")
            print('  同一人（誤報）→ {"名字": {"reviewed": "理由"}}')
            print('  不同人        → {"名字": {"persons": [...]}}，格式見該檔 _readme')
    if jout:
        json.dump({"threshold": THRESHOLD, "total_ids": total, "rows": rows},
                  open(jout, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"\n明細 → {jout}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
