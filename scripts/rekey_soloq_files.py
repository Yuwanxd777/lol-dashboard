# -*- coding: utf-8 -*-
"""逐場檔重新掛鍵：把 soloq_matches/pN.js 內部宣告的 "隊|選手" 鍵，依 fetch_dpm_soloq_accounts
的 TEAM_ALIAS 收斂到主資料的真縮寫（KRX|Willer → DRX|Willer、DNF|Peter → DNS|Peter）。

為什麼要有這支：帳號清單那邊收斂隊碼之後，逐場檔還留著舊鍵，會變成索引裡的孤兒
（積分排行榜/每日戰況出現同一人兩列）。索引完全由檔案內部的鍵重建，所以改鍵就夠；
改完跑 build_soloq_index.py，它的 _dedup_files() 會自動把同鍵的多個檔 union 合併掉，
不需要在這裡判斷誰是重複、也不會掉場次。

用法：  python scripts\rekey_soloq_files.py            # 預演，只印不動
        python scripts\rekey_soloq_files.py --apply    # 實際改寫，之後跑 build_soloq_index.py
"""
import os, re, sys, json, glob

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUTDIR = os.path.join(ROOT, "soloq_matches")

sys.path.insert(0, HERE)
# 注意：這支 import 進來的模組自己會把 sys.stdout 包成 utf-8 TextIOWrapper，
# 所以**這裡不可以再包一次**——兩個 wrapper 疊在同一個 buffer 上，先被回收的那個
# 會把底層 buffer 關掉，之後任何 print 都會炸 "I/O operation on closed file"。
from fetch_dpm_soloq_accounts import TEAM_ALIAS, canon_team, load_abbr   # 同一份對照表，不另抄一份


def main():
    apply = "--apply" in sys.argv
    valid = {str(v).upper() for v in load_abbr().values() if v}
    files = sorted(f for f in glob.glob(os.path.join(OUTDIR, "p*.js"))
                   if re.match(r"p\d+\.js$", os.path.basename(f)))
    print(f"掃描 {len(files)} 個逐場檔｜隊碼對照 {TEAM_ALIAS}")

    keys = {}          # 現有鍵 -> [檔名]
    plan = []          # (檔路徑, 舊鍵, 新鍵)
    for fp in files:
        try:
            with open(fp, encoding="utf-8") as f:
                head = f.read(400)
            m = re.match(r'window\.__sqLoad\((".*?"),', head, re.S)
            key = json.loads(m.group(1))
        except Exception as e:
            print(f"  略過 {os.path.basename(fp)}：{e}")
            continue
        keys.setdefault(key, []).append(os.path.basename(fp))
        if "|" not in key:
            continue
        tm, pl = key.split("|", 1)
        t1 = canon_team(tm)
        if t1 != tm and t1.upper() in valid:
            plan.append((fp, key, t1 + "|" + pl))

    if not plan:
        print("沒有需要改鍵的檔案。")
        return
    print(f"\n需要改鍵：{len(plan)} 個")
    for fp, old, new in plan:
        dup = "（新鍵已有檔 " + "、".join(keys.get(new, [])) + "，build_soloq_index 會合併）" if new in keys else ""
        print(f"  {os.path.basename(fp):<10} {old} → {new} {dup}")

    if not apply:
        print("\n預演模式，未改動。確認後跑 --apply")
        return

    for fp, old, new in plan:
        with open(fp, encoding="utf-8") as f:
            txt = f.read()
        pre = "window.__sqLoad(" + json.dumps(old, ensure_ascii=False) + ","
        if not txt.startswith(pre):
            print(f"  ⚠ {os.path.basename(fp)} 開頭與預期不符，跳過")
            continue
        txt = "window.__sqLoad(" + json.dumps(new, ensure_ascii=False) + "," + txt[len(pre):]
        with open(fp, "w", encoding="utf-8") as f:
            f.write(txt)
    print(f"\n已改寫 {len(plan)} 個檔。接著跑：python scripts\\build_soloq_index.py")


if __name__ == "__main__":
    main()
