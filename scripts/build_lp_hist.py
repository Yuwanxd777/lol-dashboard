# -*- coding: utf-8 -*-
"""每天 10:00 的牌位分數快照 → soloq_lp_hist.js（近期戰況「牌位(+N)」的準確增減用）。

為什麼（使用者 2026-10-18「你不是每天都會查 API 嗎，那不是一定知道分數的加減」）：
  逐場資料的 lp 一半是增減、一半是會落後的總分快照，推算出來只有 ~86% 可信。
  但排程每天 10:00 都會用 Riot API 查每個帳號的牌位（soloq.js，askedAt≈10:01），而 soloq.js 每班都被 commit
  ⇒ git 歷史裡就有「每天 10:00 的分數」。範圍增減＝結束那天 10:00 的分數 − 開始那天 10:00 的分數，跟近期戰況
  「10:00 往前 N×24 小時」的分界完全一致。
分數用連續值：大師以下＝段位×400＋分段×100＋LP；大師以上＝2800＋LP（大師／宗師／菁英共用 LP 軸）⇒ 升降段也能直接相減。
來源：今天＝工作區的 soloq.js（排程此時剛查完）；之前＝git 裡每天第一個 10:00～12:59 的 soloq.js commit。只留近 DAYS 天。
輸出：window.SOLOQ_LP_HIST={"dates":[…由舊到新],"acc":{"小寫去空白的riotId":[分數或 null,…]}}
跑：python scripts/build_lp_hist.py（排程 run_update ⑥ 收尾）
"""
import datetime, io, json, os, re, subprocess, sys

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "soloq.js")
OUT = os.path.join(ROOT, "soloq_lp_hist.js")
DAYS = 16
TIER = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND"]
DIV = {"IV": 0, "III": 1, "II": 2, "I": 3}
APEX = {"MASTER", "GRANDMASTER", "CHALLENGER"}


def score(p):
    """牌位 → 連續分數；查不到／沒定位＝None"""
    t = str(p.get("tier") or "").upper(); lp = p.get("lp")
    if not p.get("found", True) or not t or not isinstance(lp, (int, float)):
        return None
    if t in APEX:
        return 2800 + lp
    if t in TIER and str(p.get("division") or "").upper() in DIV:
        return TIER.index(t) * 400 + DIV[str(p["division"]).upper()] * 100 + lp
    return None


def key(rid):
    return re.sub(r"\s+", "", str(rid or "")).lower()


def parse(txt):
    i = txt.find("=")
    return json.loads(txt[i + 1:].strip().rstrip(";")) if i >= 0 else {}


def snap(d):
    """soloq.js 內容 → {riotId鍵: 分數}"""
    out = {}
    for p in (d.get("players") or []):
        s = score(p)
        if s is not None and p.get("riotId"):
            out[key(p["riotId"])] = s
    return out


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


def bucket_day(dt):
    """10:00 分界的「這一天」：10:00 前算前一天（同 build_soloq_index 的桶）"""
    return (dt - datetime.timedelta(hours=10)).date().isoformat()


def main():
    snaps = {}
    # 今天：工作區（排程這一步之前剛跑完 fetch_soloq_auto）；fetched_at 在 10:00～12:59 才算「今天 10:00 那份」
    try:
        cur = parse(open(SRC, encoding="utf-8").read())
        fa = datetime.datetime.strptime(str(cur.get("fetched_at"))[:16], "%Y-%m-%d %H:%M")
        if 10 <= fa.hour < 13:
            snaps[fa.date().isoformat()] = snap(cur)
    except Exception as e:
        print(f"（工作區 soloq.js 讀取失敗：{type(e).__name__}）")
    since = (datetime.date.today() - datetime.timedelta(days=DAYS + 1)).isoformat()
    for line in git("log", f"--since={since}", "--format=%H %ci", "--", "soloq.js").splitlines():
        h, d, t = line.split()[:3]
        hh = int(t[:2])
        if not (10 <= hh < 13) or d in snaps:      # 只要早上那班；git log 由新到舊，同一天保留最早被看到的…
            continue
        try:
            snaps[d] = snap(parse(git("show", f"{h}:soloq.js")))
        except Exception:
            continue
    dates = sorted(snaps)[-DAYS:]
    accs = sorted({k for d in dates for k in snaps[d]})
    out = {"dates": dates, "acc": {k: [snaps[d].get(k) for d in dates] for k in accs}}
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("window.SOLOQ_LP_HIST=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print(f"soloq_lp_hist.js：{len(dates)} 天（{dates[0] if dates else '-'}～{dates[-1] if dates else '-'}）、{len(accs)} 個帳號")
    return 0


if __name__ == "__main__":
    sys.exit(main())
