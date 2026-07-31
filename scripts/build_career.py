# -*- coding: utf-8 -*-
"""生涯資料聚合（陣容分頁的「📜 生涯」用）。

為什麼要預先聚合：data/data_2014..2026.js 合計約 400MB（單檔 6-43MB），瀏覽器不可能全部載入。
陣容頁只需要「每位選手每隻英雄的 場數/勝數/被對手禁次數/最後使用日」＋「每隊每路有哪些選手」，
聚合後只剩幾 MB，開啟生涯模式時再懶載。

輸出 career.js：
  window.CAREER={
    v:"建置日", y:[年份...],
    t:{ "<戰隊全名>":{ "TOP":[ ["<選手>", 場數, 最後出賽日], ... ] } },   // 依最後出賽日新→舊
    p:{ "<選手>":{ n:總場, w:勝場, f:首戰日, l:末戰日,
                   c:{ "<英雄資料名>":[場,勝,被對手禁,最後使用日] } } }   // 生涯＝跨隊全部
  }
用法：python scripts/build_career.py
"""
import glob, io, json, os, re, sys

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "career.js")

teams = {}      # team -> pos -> player -> [n, last]
plr = {}        # player -> {n,w,f,l,c:{champ:[n,w,ob,last]}}
POS = {1: "TOP", 2: "JNG", 3: "MID", 4: "BOT", 5: "SUP"}
years = []

# ── 同名選手拆分（同 ID 其實是不同人）────────────────────────────────
# OE 資料只有顯示 ID，沒有唯一識別，同名的不同人（例：LPL 的 Uzi 簡自豪 vs
# 越南的 Uzi Lê Thanh Hà）會被合併成一份生涯。scripts/player_disambig.json
# 由 fetch_player_ids.py 從 Leaguepedia 產生，用「隊伍」把場次分回正確的人。
# 主人格的 key 沿用原名 → 前端還沒改查詢時，行為與過去相同，不會壞。
_DIS = {}
_dp = os.path.join(ROOT, "scripts", "player_disambig.json")
if os.path.exists(_dp):
    try:
        _DIS = {k: v for k, v in json.load(open(_dp, encoding="utf-8")).items()
                if not k.startswith("_") and isinstance(v, dict) and v.get("persons")}
    except Exception as e:
        print(f"⚠ player_disambig.json 讀取失敗，不做拆分：{e}")
dmap = {}       # "隊伍|原名" -> 人格 key（只記與原名不同的，給前端查）


def _nt(t):
    """隊名正規化（同 fetch_player_ids.py）：GiantX/GIANTX、尾括號註記"""
    t = re.sub(r"\s*\([^)]*\)\s*$", "", str(t))
    t = re.sub(r"\b(e-?sports?|gaming|club|team)\b", "", t, flags=re.I)
    return re.sub(r"[^a-z0-9]", "", t.lower())


def resolve(name, team):
    """(名字,隊伍) → 該場次真正屬於誰。對不上的隊一律歸主人格＝維持原本行為。"""
    e = _DIS.get(name)
    if not e:
        return name
    ps = e["persons"]
    a = _nt(team)
    if a:
        for p in ps[1:]:                     # 次人格要明確對到隊才拆出去
            # teams＝Leaguepedia 的隊名；teams_oe_manual＝人工補的 OE 隊名對照
            # （OE 有時把青訓隊記成一隊，例：Amazing 在 OMD 的比賽被記成 Oh My God）
            for t in list(p.get("teams") or ()) + list(p.get("teams_oe_manual") or ()):
                b = _nt(t)
                if b and (a == b or a.startswith(b) or b.startswith(a)):
                    k = p["key"]
                    dmap[team + "|" + name] = k
                    return k
    return ps[0]["key"]

for dp in sorted(glob.glob(os.path.join(ROOT, "data", "data_*.js"))):
    y = re.search(r"data_(\d{4})\.js$", dp)
    if not y:
        continue
    y = y.group(1)
    txt = open(dp, encoding="utf-8").read()
    J = json.loads(txt.split("=", 1)[1].strip().rstrip(";"))
    R = J["tabs"]["RAW_DATA"]; h = R[0]
    ix = {n: i for i, n in enumerate(h)}
    need = ("participantid", "blue_teamname", "blue_playername", "blue_champion", "date", "result")
    if any(n not in ix for n in need):
        print(f"⚠ {os.path.basename(dp)} 欄位不符，略過"); continue
    RB = ix["red_champion"] - ix["blue_champion"]
    pi, dt, rs = ix["participantid"], ix["date"], ix["result"]
    bt, bp, bc = ix["blue_teamname"], ix["blue_playername"], ix["blue_champion"]
    bl = ix.get("blue_banlist"); rl = ix.get("red_banlist"); ban1 = ix.get("banlist")
    n0 = len(plr)
    for r in R[1:]:
        try:
            p = int(r[pi])
        except Exception:
            continue
        if p not in POS:
            continue
        d = str(r[dt])[:10]
        for side in (0, 1):
            off = RB if side else 0
            team, name, ch = r[bt + off], r[bp + off], r[bc + off]
            if not team or not name or not ch:
                continue
            name = str(name).strip()
            # OE 偶發把選手名寫成「隊縮寫␣ID」→ 與該列自隊縮寫相符的前綴剝掉（同 index.html 的清理）
            cmp_ = re.sub(r"[^A-Za-z0-9]", "", str(team))
            if cmp_ and name.startswith(cmp_ + " ") and len(name) > len(cmp_) + 1:
                name = name[len(cmp_) + 1:]
            name = resolve(name, str(team))
            won = (r[rs] == (2 if side else 1)) or (str(r[rs]) == str(2 if side else 1))
            t = teams.setdefault(str(team), {}).setdefault(POS[p], {})
            e = t.setdefault(name, [0, ""])
            e[0] += 1
            if d > e[1]:
                e[1] = d
            a = plr.setdefault(name, {"n": 0, "w": 0, "f": "9999", "l": "", "c": {}})
            a["n"] += 1
            if won:
                a["w"] += 1
            if d and d < a["f"]:
                a["f"] = d
            if d > a["l"]:
                a["l"] = d
            c = a["c"].setdefault(str(ch), [0, 0, 0, ""])
            c[0] += 1
            if won:
                c[1] += 1
            if d > c[3]:
                c[3] = d
            # 被「對手」禁：對手的 banlist（沒有分邊欄位的舊檔退回合併名單）
            col = (bl if side else rl)
            if col is None:
                col = ban1
            if col is not None and r[col]:
                for b in set(str(r[col]).split("|")):
                    if b:
                        bb = a["c"].setdefault(b, [0, 0, 0, ""])
                        bb[2] += 1
    years.append(y)
    print(f"  {y}: 累計選手 {len(plr)}（+{len(plr)-n0}）", flush=True)

# 隊→路→選手（依最後出賽日新→舊）
tout = {}
for tm, ps in teams.items():
    o = {}
    for pos, mp in ps.items():
        lst = sorted(([p] + v for p, v in mp.items()), key=lambda x: (x[2], x[1]), reverse=True)
        o[pos] = [[p, n, d] for p, n, d in lst if n >= 1]
    tout[tm] = o
for a in plr.values():
    if a["f"] == "9999":
        a["f"] = ""
# d：(隊伍|原名) → 人格 key。只列拆出去的次人格；前端查生涯時先查這張表，
# 查不到就沿用原名（＝主人格），所以前端沒改也不會壞。
data = {"v": max(years) if years else "", "y": years, "t": tout, "p": plr, "d": dmap}
js = "window.CAREER=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"
with open(OUT, "w", encoding="utf-8") as f:
    f.write(js)
print(f"\n→ {OUT}　{len(js)/1048576:.1f} MB　戰隊 {len(tout)}　選手 {len(plr)}　年份 {years[0]}~{years[-1]}")
if _DIS:
    print(f"　同名拆分：表內 {len(_DIS)} 個名字，實際拆出 {len(set(dmap.values()))} 個次人格、"
          f"影響 {len(dmap)} 組（隊伍,名字）")
