# -*- coding: utf-8 -*-
"""把當班的 update_log.txt 歸檔到 autopilot/shift_logs/，並抽出耗時摘要 → 可跨班比較。

為什麼要有這支（2026-09-09 精進迴圈 #90）：
  `update.bat` 第一行就覆寫 `update_log.txt` ⇒ **每一班的日誌只活到下一班**。
  #56 已經把階段牆鐘（「這一階段 X 秒」）寫進 log，解決了「時間資料只落在會被重寫的 console 檔」，
  但 log 自己一樣每班被覆寫 ⇒ 隔天想回頭比「③ 這一階段幾秒」還是沒得比。
  #89 量 ⑤c 的逐帳號拆帳，就是趁 10:00 那班還沒被 22:00 覆寫才抄到的——**下一班一到就永遠沒了**。
  今天（09-09）五個 commit 動了 14 支管線腳本，22:00 那班要驗收十三件提速，
  對照組正是 10:00 那班的日誌。這支就是把對照組先存下來，並讓以後每一班都自動留底。

界線（刻意）：
  - **只讀 `update_log.txt`，只寫 `autopilot/shift_logs/`**。不碰管線任何檔、不改 update.bat／run_update.py，
    所以不受「管線在跑時不改 scripts/*.py」限制，管線跑到一半也可以安全執行（見 --dry 的說明）。
  - 由對話端迴圈每輪跑一次即可；不掛進 update.bat（.bat 的 >> 陷阱見 CLAUDE.md 鐵則 13）。

用法：
  python scripts/shift_log_archive.py           # 歸檔目前的 update_log.txt（同一班且內容沒變就跳過）
  python scripts/shift_log_archive.py --list    # 列出已歸檔的班次（含牆鐘、步數）
  python scripts/shift_log_archive.py --diff    # 比較最近兩班（步驟／階段逐項差）
  python scripts/shift_log_archive.py --diff 20260909_1000 20260909_2200
  python scripts/shift_log_archive.py --dry     # 只印解析結果不寫檔
"""
import argparse, glob, io, json, os, re, sys

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOG = os.path.join(ROOT, "update_log.txt")
OUTDIR = os.path.join(ROOT, "autopilot", "shift_logs")
KEEP = 60          # 只留最近 N 班（一天兩班 ⇒ 一個月）

# 日誌行格式（run_update.py 寫的，全形括號）：
#   ==== run_update 2026-09-09 10:00:01（並行 4）====
#   ---- fetch_fill（23.4s，exit 0）----
#      （【① 補件】這一階段 23.4s）
#   合計 7.5 分鐘（牆鐘 452.8s）；步驟時間相加 10.4 分鐘（626.0s）——差額 173.3s 是並行省下來的
RE_RUN = re.compile(r"^==== run_update (\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):\d{2}（(?:並行 (\d+)|(循序))）", re.M)
RE_STEP = re.compile(r"^---- (.+?)（([\d.]+)s，exit (-?\d+)）----")
RE_STAGE = re.compile(r"^\s*（【(.+?)】這一階段 ([\d.]+)s）")
RE_WALL = re.compile(r"牆鐘 ([\d.]+)s")


def parse(txt):
    """把一份 update_log.txt 解析成摘要 dict；解析不到 run_update 那行就回 None。"""
    m = RE_RUN.search(txt)
    if not m:
        return None
    y, mo, d, hh, mm, jobs, seq = m.groups()
    out = {"shift": f"{y}-{mo}-{d} {hh}:{mm}", "stamp": f"{y}{mo}{d}_{hh}{mm}",
           "jobs": 0 if seq else int(jobs or 0), "parallel": not seq,
           "wall": None, "steps": [], "stages": []}
    for ln in txt.splitlines():
        s = RE_STEP.match(ln)
        if s:
            out["steps"].append({"name": s.group(1), "sec": float(s.group(2)), "rc": int(s.group(3))})
            continue
        g = RE_STAGE.match(ln)
        if g:
            out["stages"].append({"name": g.group(1), "sec": float(g.group(2))})
            continue
        if out["wall"] is None and "牆鐘" in ln:
            w = RE_WALL.search(ln)
            if w:
                out["wall"] = float(w.group(1))
    out["n_steps"] = len(out["steps"])
    out["n_bad"] = sum(1 for x in out["steps"] if x["rc"] != 0)
    out["sum_steps"] = round(sum(x["sec"] for x in out["steps"]), 1)
    return out


def archive(dry=False):
    if not os.path.exists(LOG):
        print("✗ 找不到 update_log.txt"); return 1
    with open(LOG, encoding="utf-8", errors="replace") as f:
        txt = f.read()
    info = parse(txt)
    if not info:
        # 管線正在跑、日誌才寫了幾行時會走到這（run_update 那行一定在最前面，所以多半是別的問題）
        print("✗ 日誌裡沒有 ==== run_update ==== 那行，不歸檔（管線剛起步或日誌被別的東西蓋掉）")
        return 1
    if not info["steps"]:
        print(f"… {info['shift']} 這班還沒有任何步驟完成（管線剛起跑？），不歸檔")
        return 0
    print(f"班次 {info['shift']}｜{'並行 %d' % info['jobs'] if info['parallel'] else '循序'}"
          f"｜步驟 {info['n_steps']}（非零 {info['n_bad']}）｜"
          f"牆鐘 {info['wall'] if info['wall'] is not None else '（未收尾）'}s｜相加 {info['sum_steps']}s")
    if dry:
        for x in sorted(info["steps"], key=lambda x: -x["sec"])[:8]:
            print(f"   {x['name']:30s} {x['sec']:7.1f}s")
        return 0
    os.makedirs(OUTDIR, exist_ok=True)
    lp = os.path.join(OUTDIR, f"update_log_{info['stamp']}.txt")
    jp = os.path.join(OUTDIR, f"shift_{info['stamp']}.json")
    # 同一班重跑（手動補跑）會有較完整的日誌 ⇒ 只在「新的比較長」時覆寫，不會把完整的換成半截的
    if os.path.exists(lp) and os.path.getsize(lp) >= len(txt.encode("utf-8")):
        print(f"   已歸檔且不比舊的長，跳過：{os.path.basename(lp)}")
    else:
        with open(lp, "w", encoding="utf-8") as f:
            f.write(txt)
        with open(jp, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=1)
        print(f"   → autopilot/shift_logs/{os.path.basename(lp)}（{len(txt) // 1024} KB）＋ 同名 .json")
    olds = sorted(glob.glob(os.path.join(OUTDIR, "update_log_*.txt")))
    for p in olds[:-KEEP]:
        os.remove(p)
        j = p.replace("update_log_", "shift_").replace(".txt", ".json")
        if os.path.exists(j):
            os.remove(j)
        print(f"   （超過保留上限 {KEEP} 班，刪除 {os.path.basename(p)}）")
    return 0


def load_shifts():
    out = []
    for p in sorted(glob.glob(os.path.join(OUTDIR, "shift_*.json"))):
        with open(p, encoding="utf-8") as f:
            out.append(json.load(f))
    return out


def cmd_list():
    ss = load_shifts()
    if not ss:
        print("（還沒有歸檔的班次）"); return 0
    print(f"已歸檔 {len(ss)} 班（autopilot/shift_logs/）：")
    for s in ss:
        print(f"  {s['stamp']}  {s['shift']}  {'並行%d' % s['jobs'] if s['parallel'] else '循序  '}"
              f"  牆鐘 {s['wall'] if s['wall'] is not None else '?':>7}s  步驟 {s['n_steps']:2d}"
              f"（非零 {s['n_bad']}）  相加 {s['sum_steps']}s")
    return 0


def _pick(ss, stamp):
    for s in ss:
        if s["stamp"] == stamp:
            return s
    return None


def cmd_diff(a=None, b=None):
    ss = load_shifts()
    if len(ss) < 2 and not (a and b):
        print(f"✗ 只有 {len(ss)} 班，沒得比（至少要兩班）"); return 1
    A = _pick(ss, a) if a else ss[-2]
    B = _pick(ss, b) if b else ss[-1]
    if not A or not B:
        print(f"✗ 找不到指定的班次（有的是：{'、'.join(s['stamp'] for s in ss)}）"); return 1
    print(f"═══ {A['shift']} → {B['shift']} ═══")
    wa, wb = A.get("wall"), B.get("wall")
    if wa and wb:
        print(f"牆鐘 {wa:.1f}s → {wb:.1f}s（{wb - wa:+.1f}s，{(wb - wa) / wa * 100:+.1f}%）")
    print(f"步驟 {A['n_steps']} → {B['n_steps']}；非零離開碼 {A['n_bad']} → {B['n_bad']}"
          f"；{'並行%d' % A['jobs'] if A['parallel'] else '循序'} → "
          f"{'並行%d' % B['jobs'] if B['parallel'] else '循序'}")
    da = {x["name"]: x["sec"] for x in A["steps"]}
    db = {x["name"]: x["sec"] for x in B["steps"]}
    rows = []
    for k in sorted(set(da) | set(db)):
        va, vb = da.get(k), db.get(k)
        rows.append((k, va, vb, (vb - va) if (va is not None and vb is not None) else None))
    rows.sort(key=lambda r: (r[3] is None, r[3] if r[3] is not None else 0))
    print("\n步驟（差最多的在兩頭，只列變化 ≥0.5s 或單邊缺席）：")
    for k, va, vb, d in rows:
        if d is None:
            print(f"  {k:30s} {('%.1fs' % va) if va is not None else '—':>9} → "
                  f"{('%.1fs' % vb) if vb is not None else '—':>9}   ⚠ 單邊沒有這一步")
        elif abs(d) >= 0.5:
            print(f"  {k:30s} {va:8.1f}s → {vb:8.1f}s  {d:+8.1f}s  {d / va * 100:+6.1f}%" if va else
                  f"  {k:30s} {va:8.1f}s → {vb:8.1f}s  {d:+8.1f}s")
    ga = {x["name"]: x["sec"] for x in A["stages"]}
    gb = {x["name"]: x["sec"] for x in B["stages"]}
    if ga and gb:
        print("\n階段：")
        for k in [x["name"] for x in B["stages"]]:
            va, vb = ga.get(k), gb.get(k)
            if va is None:
                print(f"  {k:34s} {'—':>9} → {vb:8.1f}s   ⚠ 舊那班沒有這一階段")
            elif abs(vb - va) >= 0.5:
                print(f"  {k:34s} {va:8.1f}s → {vb:8.1f}s  {vb - va:+8.1f}s")
        for k in [x["name"] for x in A["stages"] if x["name"] not in gb]:
            print(f"  {k:34s} {ga[k]:8.1f}s → {'—':>9}   ⚠ 新那班沒有這一階段")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="列出已歸檔的班次")
    ap.add_argument("--diff", nargs="*", metavar="STAMP", help="比較兩班（不給參數＝最近兩班）")
    ap.add_argument("--dry", action="store_true", help="只解析不寫檔")
    A = ap.parse_args()
    if A.list:
        return cmd_list()
    if A.diff is not None:
        return cmd_diff(*(A.diff[:2] if A.diff else ()))
    return archive(dry=A.dry)


if __name__ == "__main__":
    sys.exit(main())
