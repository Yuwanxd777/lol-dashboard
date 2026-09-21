# -*- coding: utf-8 -*-
"""WIKI_DATE_FIX（Leaguepedia 自己把開賽日期打錯的局）的測試——2026-09-21 精進迴圈 #184。

那一局：GPL 2014 冬季 ahq eSports Club vs Saigon Jokers，wiki 寫 2013-01-06 12:00、GameId 是 Week 2_2_1，
同一週其他局全在 2013-11-06～11-08 ⇒ 月份打錯一位。兩支共用一張表：
  fetch_wiki_mh.to_csv   —— 重建 wikifill 時把那局搬到 2013-11-06（其他局一局都不能動）
  fetch_wiki_stats.year_rows —— 逐選手數據也要搬過去，配對鍵才對得起來（它含日期）

用法：python scripts/wiki_date_fix_test.py        （約 10～30 秒，只讀；全程封網）

素材用**真實快取頁**（csv_cache/wikitxt/gpl_2014_winter.html、csv_cache/lpstats/*.json），
正控制把 OLDREV（修之前）那版拉出來跑同一套，證明舊版真的把那局留在 2013-01-06、真的配不到。
沙盒段（T3）用 Zzprobe9942 這種真 repo 不可能有的選手名當「只有沙盒才有的證據」。
跑完 assert 真實快取／年度檔的 size＋mtime_ns 一個都沒動。
"""
import collections, io, json, os, subprocess, sys, tempfile, types

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")    # 先換好，被測模組就不會再包一層（#182 踩過）
except Exception:
    pass
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
OLDREV = "3646104d"          # 修之前的版本（WIKI_DATE_FIX 還不存在）；別寫 HEAD（#93）
TOUR, GID = "GPL 2014 Winter", "2014 GPL Winter_Week 2_2_1"
HTML = os.path.join(ROOT, "csv_cache", "wikitxt", "gpl_2014_winter.html")
REAL = [os.path.join(ROOT, *p) for p in (
    ("csv_cache", "wikifill_2014.json"), ("csv_cache", "wikistats_2014.json"), ("csv_cache", "wikistats_2013.json"),
    ("data", "data_2014.js"), ("csv_cache", "lpstats", "2013-01.json"), ("csv_cache", "lpstats", "2013-11.json"),
    ("csv_cache", "wikitxt", "gpl_2014_winter.html"))]

ok = bad = 0


def check(cond, msg):
    global ok, bad
    if cond:
        ok += 1
        print("  ✓ " + msg)
    else:
        bad += 1
        print("  ✗ " + msg)


def stamp():
    return {p: (os.path.getsize(p), os.stat(p).st_mtime_ns) if os.path.exists(p) else None for p in REAL}


def boom(*a, **k):
    raise RuntimeError("測試封網：不准打 Leaguepedia")


def old_module(name):
    """OLDREV 那版原始碼，__file__ 設成真實路徑（HERE／ROOT 才會指到真 repo 的快取）。"""
    src = subprocess.run(["git", "show", f"{OLDREV}:scripts/{name}.py"], cwd=ROOT,
                         capture_output=True).stdout.decode("utf-8")
    assert "def " in src, f"拿不到 {OLDREV}:scripts/{name}.py"
    m = types.ModuleType(name + "_old")
    m.__file__ = os.path.join(HERE, name + ".py")
    exec(compile(src, m.__file__, "exec"), m.__dict__)
    return m


def fuse_mh(m):
    m.fetch = boom
    m.opener = boom
    m.fetch_embed = boom
    m.pb_page = lambda tour, force=False, tries=3: ""   # 那個賽事沒有 PB 頁快取（真的跑也是「頁不存在」）
    m.pname = lambda nm: nm                              # 選手名對齊跟日期無關，省掉讀 11 個年度檔


before = stamp()
import fetch_wiki_mh as MH
import fetch_wiki_stats as FWS
MHo = old_module("fetch_wiki_mh")
FWSo = old_module("fetch_wiki_stats")
for m in (MH, MHo):
    fuse_mh(m)
for m in (FWS, FWSo):
    m.fetch_range = boom

html = open(HTML, encoding="utf-8").read()
_, raw_games = MH.parse(html)
chrono = list(reversed(raw_games))           # 那頁是新→舊（to_csv 也是這樣判的）
nk = lambda s: "".join(c for c in str(s or "").lower() if c.isalnum())
# 兩隊那一季打了 6 局（11-22、01-08 ×3、01-09…），要連時間一起鎖才是「那一局」
is_pair = lambda g: frozenset((nk(g.get("Blue")), nk(g.get("Red")))) == frozenset(("ahqesportsclub", "saigonjokers"))
is_it = lambda g: is_pair(g) and str(g.get("Date"))[:16] in ("2013-01-06 12:00", "2013-11-06 12:00")

print("T0 素材：真實頁面裡那一局還是打錯的日期（上游修好了這支測試就該改）")
tgt = [g for g in raw_games if is_it(g)]
check(len(raw_games) == 94, f"GPL 2014 冬季解析到 {len(raw_games)} 局（期望 94）")
check(len(tgt) == 1 and tgt[0]["Date"].startswith("2013-01-06 12:00"), f"ahq vs SJ 那局：{[g['Date'] for g in tgt]}")
check(sum(map(is_pair, raw_games)) == 6 and min(g["Date"] for g in raw_games if is_pair(g)).startswith("2013-01-06"),
      "兩隊同季 6 局，打錯的那局是全季最早（修之前排在最前面）")
check(hasattr(MH, "WIKI_DATE_FIX") and not hasattr(MHo, "WIKI_DATE_FIX"), "新版有 WIKI_DATE_FIX、舊版沒有（OLDREV 釘對了）")

print("T1 fix_dates（純函式，真實素材）")
snap_in = json.dumps(chrono, ensure_ascii=False)
new, n = MH.fix_dates(chrono, TOUR)
check(n == 1, f"改了 {n} 局（期望 1）")
check(json.dumps(chrono, ensure_ascii=False) == snap_in, "呼叫端的 list 與 dict 一個字沒動")
moved = [i for i, g in enumerate(new) if is_it(g)]
check(len(moved) == 1 and new[moved[0]]["Date"] == "2013-11-06 12:00:00", f"新日期：{new[moved[0]]['Date'] if moved else None}")
i = moved[0] if moved else 0
d_prev = new[i - 1]["Date"][:19] if i > 0 else ""
d_next = new[i + 1]["Date"][:19] if i + 1 < len(new) else "（沒有，排在最後）"
check("2013-11-06" <= d_prev <= "2013-11-06 12:00:00" and d_next[:10] == "2013-11-07",
      f"搬到正確位置：前一局 {d_prev}、後一局 {d_next}")
check([g for g in new if not is_it(g)] == [g for g in chrono if not is_it(g)], "其他 93 局的先後與內容完全不變")
same, n2 = MH.fix_dates(chrono, "GPL 2014 Spring")
check(n2 == 0 and same == chrono, "別的賽事名 ⇒ 不動")
fixed_up = [dict(g, Date="2013-11-06 12:00:00") if is_it(g) else g for g in chrono]
_, n3 = MH.fix_dates(fixed_up, TOUR)
check(n3 == 0, "上游自己修好了（原始時間不再是 was）⇒ 不動")
twice = chrono + [g for g in chrono if is_it(g)]
_, n4 = MH.fix_dates(twice, TOUR)
check(n4 == 0, "同一時刻兩隊出現兩局（不夠確定）⇒ 不動")
decoy = [dict(g, Date="2013-01-06 12:00:00") if g["Blue"] == "Mineski" and g["Date"].startswith("2013-11-06") else g
         for g in chrono if not is_it(g)]
check(sum(g["Date"].startswith("2013-01-06") for g in decoy) == 1, "（素材：別的兩隊放在打錯的那個時刻、目標局拿掉）")
dnew, n6 = MH.fix_dates(decoy, TOUR)
check(n6 == 0 and dnew == decoy, "同一時刻但不是那兩隊 ⇒ 不動（鎖定要連兩隊一起比）")
swapped = [dict(g, Blue=g["Red"], Red=g["Blue"]) if is_it(g) else g for g in chrono]
_, n5 = MH.fix_dates(swapped, TOUR)
check(n5 == 1, "藍紅方互換照樣對得上（兩隊當集合比）")

print("T2 to_csv 端到端（真實頁面，新版 vs 舊版）")
cfg = {"tour": TOUR, "league": "GPL", "split": "Winter", "year": 2014, "playoffs": 0,
       "key": "GPL_2014_Winter", "patch": "", "embed": None}
hdr, rows = MH.to_csv(raw_games, dict(cfg))
hdro, rowso = MHo.to_csv(raw_games, dict(cfg))
di, ti = hdr.index("date"), hdr.index("teamname")
gi = hdr.index("gameid")
pair_rows = lambda rs: [r for r in rs if r[ti] in ("ahq eSports Club", "Saigon Jokers")
                        and r[di][:10] in ("2013-01-06", "2013-11-06")]
nr, orr = pair_rows(rows), pair_rows(rowso)
check(hdr == hdro, "表頭相同")
check(len(nr) == 12 and {r[di] for r in nr} == {"2013-11-06 00:51:00"},
      f"新版那局 12 列全是 2013-11-06 00:51:00（當天第 5 個系列）：{sorted({r[di] for r in nr})}")
check(len(orr) == 12 and {r[di] for r in orr} == {"2013-01-06 00:11:00"},
      f"正控制：舊版那局 12 列是 2013-01-06 00:11:00：{sorted({r[di] for r in orr})}")
strip = lambda r: tuple(v for j, v in enumerate(r) if j not in (di, gi))
check(sorted(map(strip, nr)) == sorted(map(strip, orr)), "那局除了日期（與內部 gameid）以外 12 列逐欄相同")
rest_n = [r for r in rows if r not in nr]
rest_o = [r for r in rowso if r not in orr]
check(rest_n == rest_o, f"其他 {len(rest_n)} 列逐列、逐欄、連順序都相同")
day = collections.Counter(r[di] for r in rows if r[di][:10] == "2013-11-06" and r[hdr.index("position")] == "team")
check(all(v == 2 for v in day.values()), f"2013-11-06 每個合成時間剛好一局（兩隊各一列）：{dict(sorted(day.items()))}")
import csv as _csv
import fetch_data
buf_n, buf_o = io.StringIO(), io.StringIO()      # process() 吃的是 build() 的 csv.writer 輸出，照同一條路組
_csv.writer(buf_n, lineterminator="\n").writerows([hdr] + rows)
_csv.writer(buf_o, lineterminator="\n").writerows([hdro] + rowso)
tn, to = fetch_data.process(buf_n.getvalue(), 2014), fetch_data.process(buf_o.getvalue(), 2014)
pdi = tn[0].index("date")
chg_n = [r for r in tn[1:] if r not in to[1:]]
chg_o = [r for r in to[1:] if r not in tn[1:]]
check(len(tn) == len(to) and len(chg_n) == 6 and len(chg_o) == 6,
      f"process() 之後：列數 {len(tn)-1}＝{len(to)-1}，只有 6 列不同（新 {len(chg_n)}／舊 {len(chg_o)}）")
check({r[pdi] for r in chg_n} == {"2013-11-06 00:51:00"} and {r[pdi] for r in chg_o} == {"2013-01-06 00:11:00"},
      "而且只差在日期那一欄")

print("T3 fetch_wiki_stats.fix_dates（沙盒：Zzprobe9942 只存在這裡）")
real_raw = FWS.RAW
with tempfile.TemporaryDirectory() as td:
    FWS.RAW = td
    mine = [{"gid": GID, "dt": "2013-01-06 12:00:00", "nm": f"Zzprobe9942_{k}", "ch": "Singed", "k": str(k)} for k in range(10)]
    other = {"gid": "2013 GPL Spring_Week 1_1_1", "dt": "2013-01-06 11:00:00", "nm": "Zzprobe9942_other", "ch": "Annie", "k": "1"}
    json.dump(mine + [other], open(os.path.join(td, "2013-01.json"), "w", encoding="utf-8"))
    span14 = {f"2013-{m:02d}" for m in (10, 11, 12)} | {f"2014-{m:02d}" for m in range(1, 13)}
    span13 = {f"2012-{m:02d}" for m in (10, 11, 12)} | {f"2013-{m:02d}" for m in range(1, 13)}
    r14 = FWS.fix_dates([], span14)
    check(len(r14) == 10 and {x["dt"] for x in r14} == {"2013-11-06 12:00:00"} and all(x["nm"].startswith("Zzprobe9942_") for x in r14),
          f"2014：從原始月份（沙盒）撈進 10 列、日期改成 2013-11-06（{len(r14)} 列）")
    check(not any(x["nm"] == "Zzprobe9942_other" for x in r14), "2014：同月份的其他局不會被撈進來")
    src13 = mine + [other]
    r13 = FWS.fix_dates(src13, span13)
    check(len(r13) == 11 and sum(x["dt"].startswith("2013-11-06") for x in r13) == 10 and src13[0]["dt"] == "2013-01-06 12:00:00",
          "2013（兩個月份都在範圍內）：就地改日期、不重複撈、不改呼叫端的 dict")
    r_only01 = FWS.fix_dates(src13, {"2013-01"})
    check(len(r_only01) == 1 and r_only01[0]["nm"] == "Zzprobe9942_other", "正確日期不在這一年的範圍 ⇒ 那局拿掉，其他留著")
    up = [dict(x, dt="2013-11-06 12:00:00") for x in mine]
    os.remove(os.path.join(td, "2013-01.json"))
    r_nocache = FWS.fix_dates([], span14)
    check(r_nocache == [], "原始月份沒有快取 ⇒ 不撈、不打網路（封網沒炸）")
    r_up = FWS.fix_dates(up, span14)
    check(r_up == up, "上游自己修好了（dt 已經是 2013-11-06）⇒ 原樣")
FWS.RAW = real_raw

print("T4 真實快取：逐選手數據配得到了（舊版配不到＝正控制）")
rows14 = FWS.year_rows(2014)
rows14o = FWSo.year_rows(2014)
mine14 = [x for x in rows14 if x.get("gid") == GID]
check(len(mine14) == 10 and {str(x["dt"])[:16] for x in mine14} == {"2013-11-06 12:00"}, f"新版 2014：那局 {len(mine14)} 列、日期 2013-11-06")
check(not any(x.get("gid") == GID for x in rows14o), "正控制：舊版 2014 根本沒有那局")
check(len(rows14) == len(rows14o) + 10, f"新版只多那 10 列（{len(rows14)} vs {len(rows14o)}）")
idx, _ = FWS.index_rows(rows14, {})
idxo, _ = FWSo.index_rows(rows14o, {})
k = "|".join(("D", "2013-11-06", "*", FWS.norm("Prydz"), FWS.norm("Singed")))
check(isinstance(idx.get(k), dict) and idx[k].get("kills") == "2", f"新版鍵 {k} → kills {idx.get(k, {}).get('kills') if isinstance(idx.get(k), dict) else idx.get(k)}")
check(k not in idxo, "正控制：舊版沒有這個鍵")
extra = set(idx) - set(idxo)
check(len(extra) == 20 and not (set(idxo) - set(idx)) and all(idx[x] == idxo[x] for x in idxo),
      f"新版只多 20 個鍵（10 人 × B／C 兩種）、舊鍵一個不少且值全同（多 {len(extra)}）")

after = stamp()
check(after == before, "真實 wikifill／wikistats／data_2014／lpstats／wikitxt 的 size＋mtime_ns 都沒動")
print(f"\n{ok} 通過 / {bad} 失敗")
sys.exit(1 if bad else 0)
