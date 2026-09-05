# -*- coding: utf-8 -*-
"""牌位自動更新（每天 10:00 update.bat 呼叫）
讀「添加API」按鈕存下的本機金鑰（scripts/riot_key.local.json，dev 金鑰 24 小時過期），
還新鮮就代跑 fetch_soloq.py 更新 soloq.js（之後 publish.bat 照常推上 git）；
沒金鑰或已過期 → 印訊息跳過，永遠 exit 0 不擋更新鏈。
"""
import io, sys, json, os, time, datetime, subprocess

FULL_EVERY_D = 7        # 幾天至少全掃一次（其餘日子只掃近三天有打的）

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
KEYF = os.path.join(HERE, "riot_key.local.json")
MAX_AGE_H = 23  # dev 金鑰 24h 過期，留 1h 餘裕


def main():
    if not os.path.exists(KEYF):
        print("牌位自動更新：尚未添加金鑰（儀表板積分頁「添加API」按鈕），跳過。")
        return
    try:
        d = json.load(open(KEYF, encoding="utf-8"))
        key, saved = str(d.get("key", "")).strip(), float(d.get("saved", 0))
        perm = bool(d.get("permanent"))  # Personal/Production 長期金鑰：不做 24h 過期檢查
    except Exception as e:
        print(f"牌位自動更新：金鑰檔讀取失敗（{e}），跳過。")
        return
    age_h = (time.time() - saved) / 3600
    if not key.startswith("RGAPI-") or (not perm and age_h > MAX_AGE_H):
        print(f"牌位自動更新：金鑰已過期（{age_h:.1f} 小時前添加，dev 金鑰 24h 失效），跳過。到積分頁按「添加API」換新的。")
        return
    # ── 一律全掃（2026-09-05 下午，使用者定案把順序倒過來之後）──────────────
    # 早上曾經改成「只掃近三天有打的（--active）」，那是在「逐場先跑、牌位後跑」的舊順序下
    # 為了省牌位的請求。**順序倒過來之後這個取捨反了**：牌位是便宜的那一邊（普通 HTTP），
    # 而且它回應裡的 wins/losses 正是決定「逐場要抓誰」的權威訊號——
    # 只掃一部分＝那個訊號有洞，貴的那一邊就得退回全掃，反而更慢。
    # ⇒ 牌位全掃、逐場只抓有動的。`--active` 保留在 fetch_soloq.py 裡當手動選項。
    args = [sys.executable, os.path.join(HERE, "fetch_soloq.py")]
    print("牌位自動更新：使用%s，全掃（結果會寫 scripts/soloq_played.json 給逐場那一步用）"
          % ("長期金鑰" if perm else f"{age_h:.1f} 小時前添加的金鑰"))
    full = True
    env = dict(os.environ); env["RIOT_API_KEY"] = key
    try:
        rc = subprocess.call(args, cwd=ROOT, env=env)
        print(f"牌位自動更新：fetch_soloq.py 結束（exit {rc}）。")
        if full and rc == 0:
            json.dump({"last": datetime.date.today().isoformat()},
                      open(stamp, "w", encoding="utf-8"))
    except Exception as e:
        print(f"牌位自動更新：執行失敗 {e}")


if __name__ == "__main__":
    main()
    sys.exit(0)
