# -*- coding: utf-8 -*-
"""S17（2027 賽季）名單＝轉會分頁陣容表裡「確定＋留隊」的五路選手（使用者 2026-11-23 定案）。

判準跟 index.html 的 s17Roster() 同一條（改一邊另一邊要跟著改）：
  不是傳聞(r)、不是已宣布離隊(gone)，而且（新加入 new／有消息且非傳聞 tip／續約 rs／升職 pm
  ／合約還在 c>=今天）。合約還在但傳出要走（ro，例 Ruler→JDG）照算留隊，傳聞成真才移走
  ——這點跟轉會分頁 setE() 不同。FA 那幾列不算。
前端積分頁 S17 模式（s17Roster()）與管線（fetch_dpm_soloq_accounts 補帳號）都吃這份判準。

用法：python scripts/s17_roster.py   # 印名單與每隊人數
"""
import io, os, re, sys, json, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TRANSFERS = os.path.join(ROOT, "transfers.js")
ROLES = ("TOP", "JNG", "MID", "BOT", "SUP")


def pn(s):
    """去掉名字後面的「(本名)」消歧義：Doran (Choi Hyeon-jun) → Doran。"""
    return re.sub(r"\s*\([^()]*\)\s*$", "", str(s or "")).strip()


def confirmed(e, today):
    if e.get("fa") or e.get("r") or e.get("gone"):
        return False
    return bool(e.get("new") or e.get("tip") or e.get("rs") or e.get("pm")
                or (e.get("c") and e["c"] >= today))


def load_board(path=None):
    try:
        t = open(path or TRANSFERS, encoding="utf-8").read()
        d = json.loads(re.search(r"=\s*(\{.*\})\s*;?\s*$", t, re.S).group(1))
        return d.get("board") or []
    except Exception as ex:
        print(f"（S17 名單：transfers.js 讀不到 → 空名單：{ex}）", flush=True)
        return []


def roster(path=None, today=None):
    """[{player, team(全名), lg, pos, from}]；讀不到 transfers.js 回 []（＝不影響舊行為）。"""
    today = today or datetime.date.today().isoformat()
    out = []
    for b in load_board(path):
        if b.get("fa") or not b.get("nm") or b.get("nm") == "FA":
            continue
        for pos in ROLES:
            for e in (b.get("r") or {}).get(pos) or []:
                if confirmed(e, today) and pn(e.get("n")):
                    out.append({"player": pn(e.get("n")), "team": b["nm"], "lg": b.get("lg") or "",
                                "pos": pos, "from": e.get("from") or ""})
    return out


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    R = roster()
    by = {}
    for r in R:
        by.setdefault((r["lg"], r["team"]), []).append(f'{r["pos"]}:{r["player"]}')
    for k in sorted(by):
        print(k[0], k[1], len(by[k]), " ".join(by[k]))
    print(f"共 {len(R)} 位")
