# -*- coding: utf-8 -*-
"""
孤兒逐場檔：soloq_matches/pN.js 的 key（隊|選手）已經不在 soloq_accounts.json 裡的那些檔。
build_soloq_index／build_soloq_builds 是**掃資料夾**重建、不跟帳號檔對帳 ⇒ 帳號檔早就丟掉的人照樣進聚合。

2026-09-22 精進迴圈 #196 的實況（探針 autopilot/_m196_orphan_probe.py）：448 個檔裡 23 個孤兒／7407 場——
  ① 18 位「名字也不在帳號檔」（5127 場）：09-21 10:51 手動補查把 OBGG 名冊上的教練／分析師／沒出場的人
     （BLG Daeny、DK Khan・Bible・Gorilla・PoohManDu、T1 Tom…）帶進帳號檔，22:00 班的「比賽數據出場過濾」
     照設計把他們丟掉，逐場檔卻留著 ⇒ 英雄頁積分「出場紀錄」有 202 列是他們的對局。
  ② 4 位「換隊碼／大小寫之後的舊檔」（DK|Sharvel ↔ DNS|Sharvel、NS|Taeyoon ↔ BFX|Taeyoon、
     GL|Harpoon ↔ GL|HARPOON、SHFT|Nuc ↔ SHFT|nuc；1464 場）：舊檔的每一場都在現役檔裡 ⇒ 出裝聚合**同一場算兩次**。
  ③ 1 位同名仍在、但對局一場都不重疊（GAM|Taki (VN) 816 場 ↔ GAM|Taki 263 場）：不是重複，是同一位現役選手
     的另一批對局 ⇒ **留著**（寧可多收不要誤丟）。

判準（只回報「聚合時要跳過誰」，**不刪檔、不改檔**——可逆；人回到帳號檔下一班就自動回來）：
  absent＝key 不在帳號檔，而且選手名（不分大小寫、去掉 Leaguepedia 的消歧義括號再比一次）也不在帳號檔任何一隊
          ＝沿用使用者已定案的 rankShow「今年沒出場過就不列」。
  dup   ＝key 不在帳號檔、同名還在，而且這個檔的每一場（t）都已經在同名現役檔裡。
保險：帳號檔讀不到／是空的 ⇒ 不過濾；absent 多到超過 MAX_FRAC（＝多半是帳號檔壞了，09-06 那種大搬風）⇒ 不過濾、印 ⚠。
      寧可摻幾位教練，也不要讓聚合跟著一份壞掉的名單整批消失。

帳號檔路徑刻意**不做模組層常數**、由呼叫端的 OUTDIR 推（<OUTDIR 的上一層>/scripts/soloq_accounts.json）：
沙盒接管 OUTDIR 就連證據來源一起接管，不會從沙盒裡讀到真實 repo 的名單（DAILY #99：晚綁）。
改了跑 `python scripts/soloq_orphans_test.py`。
"""
import os, re, json, glob

MAX_FRAC = 0.15      # absent 佔逐場檔的比例超過這個 ⇒ 當成帳號檔壞了、不過濾（2026-09-22 實況 18/448＝4%）
MIN_FILES = 20       # 逐場檔少於這個數（沙盒／剛開始抓）不套比例保險，避免 1/3 就觸發
_HEAD = re.compile(r'window\.__sqLoad\(\s*("(?:[^"\\]|\\.)*")\s*,')
_FULL = re.compile(r'window\.__sqLoad\((.*)\);\s*$', re.S)
_PAREN = re.compile(r'\s*\([^()]*\)\s*$')


def accounts_path_for(outdir):
    return os.path.join(os.path.dirname(os.path.abspath(outdir)), "scripts", "soloq_accounts.json")


def _name(s):
    return str(s or "").strip().lower()


def _file_keys(outdir):
    """{key: [fp, …]}：只讀每個檔的開頭拿 key（448 檔 260MB 不必整個解析）。"""
    out = {}
    for fp in sorted(glob.glob(os.path.join(outdir, "p*.js"))):
        if not re.match(r'p\d+\.js$', os.path.basename(fp)):
            continue
        try:
            with open(fp, encoding="utf-8") as f:
                m = _HEAD.match(f.read(400))
            if not m:
                continue
            out.setdefault(json.loads(m.group(1)), []).append(fp)
        except Exception:
            continue   # 壞檔留給各支自己的主迴圈去印「略過」
    return out


def _tset(fps):
    ts = set()
    for fp in fps:
        try:
            m = _FULL.match(open(fp, encoding="utf-8").read())
            _, data = json.loads('[' + m.group(1) + ']')
            ts.update(g.get("t") for g in data.get("matches", []) if g.get("t") is not None)
        except Exception:
            pass
    return ts


def skip_keys(outdir, acc_path=None, log=print):
    """回傳 {key: "absent"|"dup"}＝聚合時要跳過的逐場檔 key。任何讀不懂的情況都回 {}（＝照舊全收）。"""
    acc_path = accounts_path_for(outdir) if acc_path is None else acc_path
    try:
        accs = json.load(open(acc_path, encoding="utf-8"))
        acc_keys = set(); acc_names = {}
        for a in accs:
            k = "%s|%s" % (a.get("team", ""), a.get("player", ""))
            acc_keys.add(k)
            acc_names.setdefault(_name(a.get("player")), set()).add(k)
    except Exception as e:
        log("孤兒逐場檔：帳號檔讀不到（%s）⇒ 不過濾" % type(e).__name__)
        return {}
    if not acc_keys:
        log("孤兒逐場檔：帳號檔是空的 ⇒ 不過濾")
        return {}
    files = _file_keys(outdir)
    skip = {}; kept = []
    for key in files:
        if key in acc_keys:
            continue
        nm = _name(key.split("|", 1)[-1])
        same = acc_names.get(nm) or acc_names.get(_PAREN.sub("", nm)) or set()
        if not same:
            skip[key] = "absent"
            continue
        live = [fp for k in same for fp in files.get(k, [])]
        mine = _tset(files[key])
        if mine and live and mine <= _tset(live):
            skip[key] = "dup"
        else:
            kept.append(key)
    n_abs = sum(1 for v in skip.values() if v == "absent")
    if len(files) >= MIN_FILES and n_abs > len(files) * MAX_FRAC:
        log("⚠ 孤兒逐場檔：名字不在帳號檔的有 %d／%d 個檔（超過 %d%%）⇒ 多半是帳號檔壞了，這一趟不過濾"
            % (n_abs, len(files), round(MAX_FRAC * 100)))
        return {}
    if skip or kept:
        log("孤兒逐場檔不進聚合：名字不在帳號檔 %d 位、整檔重複（換隊碼／大小寫的舊檔）%d 位；同名仍在而留著 %d 位%s"
            % (n_abs, len(skip) - n_abs, len(kept), ("（" + "、".join(sorted(kept)) + "）") if kept else ""))
    return skip
