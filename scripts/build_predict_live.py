# -*- coding: utf-8 -*-
"""預測分頁「本屆」欄要的即時數字 → predict_live.js（window.PRED_LIVE）。

使用者 2026-10-17：
  Q13「會有選手單場 450 以上尾兵嗎」本屆欄要寫「有沒有人超過 450」，不是 45 分以上長局數；
  Q14「決賽 MVP 路線」本屆欄要開始列出各場 MVP 的路線數。
年度資料檔沒收補兵（白名單 88 欄），MVP 也不在主資料裡 ⇒ 兩樣都從 Leaguepedia Cargo 拿：
  ScoreboardPlayers（逐局逐人：CS、路線）＋ MatchSchedule（系列 MVP；N/A＝沒發）。
輸出：
  {"year", "at", "games": 局數,
   "cs":  [每局補兵最高的那位 {d, g, nm, tm, ch, cs, rl}]（由高到低），
   "mvp": [{d, stage, tab, t1, t2, mvp, tm, rl}]（有發 MVP 的系列；rl 從同屆 ScoreboardPlayers 對名字），
   "series": [{d, stage, tab, w, l}]（打完的系列，前端算誰淘汰；使用者同日：模型卡淘汰的隊要加刪除線）}
查失敗就不覆寫舊檔（前端照舊顯示上一次的數字）。
跑：python scripts/build_predict_live.py [年份]（預設今年；排程 run_update ⑤h2 每班跑一次，兩個請求）
"""
import datetime, io, json, os, re, sys, urllib.parse, urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "predict_live.js")
sys.path.insert(0, HERE)
import fetch_events_extra as F   # noqa: E402  共用 Cargo 的 cookie 與節流

ROLE = {"top": "TOP", "jungle": "JNG", "mid": "MID", "bot": "BOT", "adc": "BOT", "support": "SUP"}


def _nm(s):
    """名字去掉本名括號（Ayu (Andrey Saraiva) → ayu），比對用小寫"""
    return re.sub(r"\s*\([^)]*\)\s*$", "", str(s or "")).strip().lower()


def cargo(params):
    op = F._cargo_opener()
    F._throttle()
    try:
        raw = op.open(urllib.request.Request(F.CARGO_FORM + "?" + urllib.parse.urlencode(params), headers=F.CARGO_UA),
                      timeout=90).read().decode("utf-8", "replace")
    finally:
        F._mark()
    if raw.lstrip()[:1] not in "[{":
        raise RuntimeError("Cargo 回的不是 JSON")
    return json.loads(raw)


def stage_of(ov):
    ov = str(ov or "")
    return "Play-In" if ov.endswith("/Play-In") else ("Main Event" if ov.endswith("/Main Event") else ov.rsplit("/", 1)[-1])


def build(sp, ms, year):
    """sp＝ScoreboardPlayers 列、ms＝MatchSchedule 列 → PRED_LIVE 內容（純函式，測試直接餵）"""
    best, roles = {}, {}
    for r in sp:
        try:
            cs = int(float(r.get("cs") or 0))
        except ValueError:
            continue
        rl = ROLE.get(str(r.get("rl") or "").strip().lower(), "")
        nm = re.sub(r"\s*\([^)]*\)\s*$", "", str(r.get("nm") or "")).strip()
        if nm and rl:
            roles.setdefault(_nm(nm), {}).setdefault(rl, 0)
            roles[_nm(nm)][rl] += 1
        g = str(r.get("gid") or "")
        if not g:
            continue
        cur = best.get(g)
        if cur is None or cs > cur["cs"]:
            best[g] = {"d": str(r.get("dt") or "")[:10], "g": g, "nm": nm, "tm": r.get("tm") or "",
                       "ch": r.get("ch") or "", "cs": cs, "rl": rl}
    mvp = []
    for r in sorted(ms, key=lambda x: str(x.get("dt") or "")):
        m = str(r.get("mvp") or "").strip()
        if m.upper() in ("", "N/A", "NA", "TBD", "NONE", "MISSING") or len(m) > 30:
            continue
        rc = roles.get(_nm(m)) or {}
        rl = max(rc, key=rc.get) if rc else ""
        tm = next((x.get("tm") for x in sp if _nm(x.get("nm")) == _nm(m)), "")
        mvp.append({"d": str(r.get("dt") or "")[:10], "stage": stage_of(r.get("ov")), "tab": r.get("tab") or "",
                    "t1": r.get("t1") or "", "t2": r.get("t2") or "",
                    "mvp": re.sub(r"\s*\([^)]*\)\s*$", "", m), "tm": tm or "", "rl": rl})
    # 打完的系列（淘汰判定用：入圍賽輸兩個系列、瑞士輪輸三場、淘汰賽輸一場＝出局；前端算）
    ser = []
    for r in sorted(ms, key=lambda x: str(x.get("dt") or "")):
        w = str(r.get("w") or "")
        if w not in ("1", "2") or not r.get("t1") or not r.get("t2"):
            continue
        ser.append({"d": str(r.get("dt") or "")[:10], "stage": stage_of(r.get("ov")), "tab": r.get("tab") or "",
                    "w": r["t1"] if w == "1" else r["t2"], "l": r["t2"] if w == "1" else r["t1"]})
    return {"year": year, "at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "games": len(best),
            "cs": sorted(best.values(), key=lambda x: -x["cs"]), "mvp": mvp, "series": ser}


def main():
    year = int(sys.argv[1]) if len(sys.argv) > 1 else datetime.date.today().year
    pg = f"{year} Season World Championship"
    try:
        sp = cargo({"tables": "ScoreboardPlayers=SP",
                    "fields": "SP.OverviewPage=ov,SP.GameId=gid,SP.Name=nm,SP.Team=tm,SP.Champion=ch,SP.CS=cs,SP.Role=rl,SP.DateTime_UTC=dt",
                    "where": f"SP.OverviewPage LIKE '{pg}%'", "limit": "5000", "format": "json"})
        ms = cargo({"tables": "MatchSchedule=M",
                    "fields": "M.OverviewPage=ov,M.Team1=t1,M.Team2=t2,M.MVP=mvp,M.DateTime_UTC=dt,M.Tab=tab,M.Winner=w",
                    "where": f"M.OverviewPage LIKE '{pg}%' AND M.Winner IS NOT NULL", "limit": "500", "format": "json"})
    except Exception as e:
        print(f"Cargo 失敗，保留舊檔：{type(e).__name__} {str(e)[:100]}")
        return 0
    d = build(sp, ms, year)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("window.PRED_LIVE=" + json.dumps(d, ensure_ascii=False, separators=(",", ":")) + ";")
    top = d["cs"][0] if d["cs"] else None
    print(f"→ predict_live.js：{year} 世界賽 {d['games']} 局"
          + (f"，最高補兵 {top['nm']}（{top['tm']}）{top['cs']}" if top else "")
          + f"，450+ {sum(1 for x in d['cs'] if x['cs'] >= 450)} 局；MVP {len(d['mvp'])} 個："
          + "、".join(f"{m['mvp']}({m['rl'] or '?'})" for m in d["mvp"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
