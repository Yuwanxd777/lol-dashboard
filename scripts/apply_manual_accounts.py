# -*- coding: utf-8 -*-
"""人工釘住的積分帳號 → 併進 soloq_accounts.json（每班跑，冪等）

為什麼要有：dpm 與 OBGG 都是外部名冊，選手換了新號之後它們常常好幾週不更新
（稽核報告裡那一票「帳號疑似停用」就是這件事）。使用者自己看到新號時，
寫進 scripts/soloq_accounts_manual.json 就能立刻補進來，不必等上游。

規則
  ‧ **只加不刪**：同一位選手原本的帳號一個都不動（他可能還在用舊號）。
  ‧ 以 (選手, riotId) 去重；已經有的只補上缺的欄位（team/platform），不覆蓋 dpmPuuid 這種抓回來的值。
  ‧ 每一筆都打 "manual": true，之後看 soloq_accounts.json 就知道哪些是人工加的。
  ‧ 跑的時機：**帳號那兩步（fetch_dpm_soloq_accounts／fetch_obgg_accounts）之後**——
    那兩步會整份重寫帳號檔，先加會被洗掉。run_update 裡排在 ⑤a。

檔案格式（scripts/soloq_accounts_manual.json）：
  [ {"player":"JunJia","team":"JDG","platform":"kr","riotId":"나의본색#KR1","note":"2026-09-21 使用者提供"} ]
  platform 省略時預設 kr。

用法：python scripts\\apply_manual_accounts.py          # 併入
      python scripts\\apply_manual_accounts.py --dry    # 只印不寫
"""
import io, json, os, sys

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ACC = os.path.join(HERE, "soloq_accounts.json")
MAN = os.path.join(HERE, "soloq_accounts_manual.json")
KEEP = ("player", "team", "platform", "riotId", "note", "manual")


def norm_id(s):
    """Riot ID 正規化：使用者常用 `-` 代替 `#`（나의본색-KR1）；大小寫與空白不當識別依據。"""
    s = str(s or "").strip()
    if "#" not in s and "-" in s:
        i = s.rfind("-")
        s = s[:i] + "#" + s[i + 1:]
    return s


def key(e):
    return (str(e.get("player") or "").strip().lower(),
            norm_id(e.get("riotId")).replace(" ", "").lower())


def main():
    dry = "--dry" in sys.argv
    if not os.path.exists(MAN):
        print("（沒有 soloq_accounts_manual.json，略過）")
        return 0
    try:
        man = json.load(open(MAN, encoding="utf-8"))
    except Exception as e:
        print(f"⚠ 人工帳號檔讀不動（略過，不動正本）：{e}")
        return 0
    if not isinstance(man, list):
        print("⚠ 人工帳號檔不是陣列（略過）")
        return 0
    acc = json.load(open(ACC, encoding="utf-8"))
    idx = {key(e): e for e in acc}
    add = upd = 0
    for m in man:
        if not isinstance(m, dict) or not m.get("player") or not m.get("riotId"):
            continue
        e = {k: m[k] for k in KEEP if k in m}
        e["riotId"] = norm_id(e.get("riotId"))
        e.setdefault("platform", "kr")
        e["manual"] = True
        cur = idx.get(key(e))
        if cur is None:
            acc.append(e); idx[key(e)] = e; add += 1
            print(f"  ＋ {e['player']}｜{e['riotId']}（{e.get('team','?')}／{e['platform']}）")
        else:
            miss = [k for k in ("team", "platform") if not cur.get(k) and e.get(k)]
            for k in miss:
                cur[k] = e[k]
            if not cur.get("manual"):
                cur["manual"] = True; miss.append("manual")
            if miss:
                upd += 1
                print(f"  ～ {e['player']}｜{e['riotId']} 補欄位 {miss}")
    if dry:
        print(f"（--dry）新增 {add}、補欄位 {upd}；帳號總數維持 {len(acc) - add}")
        return 0
    if add or upd:
        with open(ACC, "w", encoding="utf-8") as f:
            json.dump(acc, f, ensure_ascii=False, indent=1)
    print(f"人工帳號：新增 {add}、補欄位 {upd}；帳號總數 {len(acc)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
