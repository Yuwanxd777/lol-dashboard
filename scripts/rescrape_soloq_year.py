# -*- coding: utf-8 -*-
"""積分逐場「全年重抓」一鍵驅動（在你平常跑排程的原生環境執行；沙箱環境會被 dpm.lol Cloudflare 擋）：
  1) 以暫存模式跑 fetch_soloq_year.py --out soloq_matches_new（不動 live）
  2) 驗收：檔數 / 總場數需達安全門檻，否則保留 live、不 swap
  3) swap：舊資料備份到 soloq_matches_old（上一份 old 會被刪）→ 暫存轉正
  4) 重建 build_soloq_index.py ＋ build_soloq_builds.py
  5) 回報 Laning@15 新欄位（xd15 / fl2）覆蓋率與 fl2 命中的欄位名候選
用法：  python scripts\\rescrape_soloq_year.py     （或直接雙擊 重抓積分全年.bat）
"""
import io, sys, os, re, json, glob, shutil, subprocess

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
NEW = os.path.join(ROOT, "soloq_matches_new")
LIVE = os.path.join(ROOT, "soloq_matches")
OLD = os.path.join(ROOT, "soloq_matches_old")
MIN_FILES, MIN_GAMES = 100, 50000   # 驗收門檻（現況約 245 檔 / 11.7 萬場）

def scan(dirp):
    files = glob.glob(os.path.join(dirp, "p*.js"))
    tot = xd = fl2v = 0; fl2_vals = {}
    for fp in files:
        t = open(fp, encoding="utf-8").read()
        m = re.match(r"window\.__sqLoad\((.*)\);\s*$", t, re.S)
        if not m: continue
        _, d = json.loads("[" + m.group(1) + "]")
        for g in d.get("matches", []):
            tot += 1
            if g.get("xd15") is not None: xd += 1
            v = g.get("fl2")
            if v is not None:
                fl2v += 1; fl2_vals[str(v)] = fl2_vals.get(str(v), 0) + 1
    return len(files), tot, xd, fl2v, fl2_vals

def main():
    print("① 全年重抓（暫存模式，約 1–1.5 小時）…", flush=True)
    r = subprocess.run([sys.executable, os.path.join(HERE, "fetch_soloq_year.py"), "--out", "soloq_matches_new"])
    if r.returncode != 0:
        print("✗ 抓取程序非正常結束，live 未變動"); sys.exit(1)
    nf, tot, xd, fl2v, fl2_vals = scan(NEW)
    print(f"② 驗收：{nf} 檔 / {tot} 場｜xd15 有值 {xd}｜fl2 有值 {fl2v} {fl2_vals}")
    if nf < MIN_FILES or tot < MIN_GAMES:
        print(f"✗ 未達門檻（≥{MIN_FILES} 檔且 ≥{MIN_GAMES} 場）——可能被 Cloudflare 擋或帳號清單問題。live 未變動。")
        sys.exit(1)
    idx_new = os.path.join(NEW, "..", "soloq_matches_new")  # 索引檔由 fetch_soloq_year 寫在 OUTDIR
    print("③ swap：live → soloq_matches_old、暫存 → live", flush=True)
    if os.path.isdir(OLD): shutil.rmtree(OLD)
    os.rename(LIVE, OLD)
    os.rename(NEW, LIVE)
    _stg_idx = os.path.join(LIVE, "soloq_match_index.js")  # 暫存索引跟著資料夾轉正會殘留 → 清掉（真索引在根目錄，稍後重建）
    if os.path.exists(_stg_idx):
        os.remove(_stg_idx)
    print("④ 重建索引與出裝聚合…", flush=True)
    subprocess.run([sys.executable, os.path.join(HERE, "build_soloq_index.py")], cwd=ROOT)
    subprocess.run([sys.executable, os.path.join(HERE, "build_soloq_builds.py")], cwd=ROOT)
    if xd == 0: print("⚠ xd15 全空：dpm 的 xpDiffAt15 欄位名可能不同，要回報處理")
    if fl2v == 0: print("⚠ fl2 全空：四個候選欄位名都沒中，要把 dpm 逐場 JSON 的等級欄位名找出來")
    else: print(f"✓ fl2 命中，值分布 {fl2_vals}（欄位名候選正確）")
    print("完成 ✅ 舊資料保留在 soloq_matches_old（確認新資料沒問題後可刪）")

if __name__ == "__main__":
    main()
