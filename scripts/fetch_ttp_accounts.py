# -*- coding: utf-8 -*-
"""trackingthepros.com（TTP）選手頁的帳號 → 補進 soloq_accounts.json（每班跑，冪等、只加不刪）

為什麼要有（使用者 2026-10-18「積分帳號感覺少的有點多，這網站也納入參考」）：
  dpm／OBGG 對 LCS 升降級新隊、CBLOL 新隊、拉美選手收得很慢（稽核報告 501 位出場選手裡 42 位沒帳號），
  TTP 的選手頁（/player/{名字}）有人工整理的帳號清單，北美／歐洲／巴西／拉美最齊，例：FUE Grell → Grell#3010（GM）。
  世界賽集訓頁（/bootcamp，本屆在北美）那 71 隻我們本來就有 59 隻，缺的是教練／主播，所以不靠它。

只查「有問題的人」：跑 audit_soloq_coverage.py --json，取 ①沒帳號 ②無牌位 ⑤疑停用 ⑥看來已棄用 的選手
  （約 70 位，第一次 ~2 分鐘；頁面快取 csv_cache/ttp/ 三天，之後幾乎不打網路）。
身分核對（同名不同人是最大風險）：
  ‧ 頁面標題要等於選手名（查無此人 TTP 會導回 /players 列表）；
  ‧ TTP 有寫隊伍 ⇒ 隊縮寫要跟我們的一樣；沒寫隊伍 ⇒ 位置（Role）要跟比賽位置一樣；兩者都對不上就不收。
  ‧ 只收沒標 inactive_account 的帳號（TTP 自己把停用的號藏起來）。
寫法照 apply_manual_accounts：以 (選手, riotId) 去重、只加不刪、打 "ttp": true；
  排在 run_update ⑤a 之後、⑤b 解 puuid 之前（帳號兩步會整份重寫帳號檔，先加會被洗掉）。

用法：python scripts\\fetch_ttp_accounts.py          # 併入
      python scripts\\fetch_ttp_accounts.py --dry    # 只印不寫
"""
import html as _html, io, json, os, re, subprocess, sys, time, urllib.parse, urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ACC = os.path.join(HERE, "soloq_accounts.json")
CACHE = os.path.join(ROOT, "csv_cache", "ttp")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"}
TTL = 3 * 86400
GAP = 1.5
WANT = ("①", "②", "⑤", "⑥")
PLAT = {"NA": "na1", "EUW": "euw1", "EUNE": "eun1", "KR": "kr", "BR": "br1", "LAN": "la1", "LAS": "la2",
        "OCE": "oc1", "JP": "jp1", "TR": "tr1", "VN": "vn2", "TW": "tw2", "ME": "me1", "SG": "sg2",
        "PH": "ph2", "TH": "th2", "RU": "ru"}
ROLE = {"top": "TOP", "jungle": "JUNGLE", "mid": "MIDDLE", "adc": "BOTTOM", "bot": "BOTTOM", "support": "UTILITY"}


def parse_page(h):
    """選手頁 HTML → {name, team, role, accounts:[{region, riotId, rank, active}]}；查無此人回 None"""
    t = re.search(r"<title>(.*?)</title>", h, re.S)
    name = _html.unescape(t.group(1)).strip() if t else ""
    if not name or name == "Players" or "<h4>Accounts</h4>" not in h and "Player Info" not in h:
        return None
    info = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h[h.find("Player Info"):h.find("<h4>Accounts</h4>") if "<h4>Accounts</h4>" in h else None]))
    tm = re.search(r" Team (.+?) (?:Birthday|Contract|Follow|$)", info)
    rl = re.search(r" Role (\w+)", info)
    accs = []
    i = h.find("<h4>Accounts</h4>")
    if i >= 0:
        seg = h[i:h.find("</table>", i)]
        for cls, reg, rid, rank in re.findall(r"<tr ?(class='[^']*')?\s*><td><b>\[([A-Z]+)\]</b>\s*(.*?)</td><td class='dt-right'>(.*?)</td></tr>", seg):
            accs.append({"region": reg, "riotId": _html.unescape(rid).strip(), "rank": _html.unescape(rank).strip(),
                         "active": "inactive_account" not in cls})
    return {"name": name, "team": _html.unescape(tm.group(1)).strip() if tm else "",
            "role": ROLE.get((rl.group(1) if rl else "").lower(), ""), "accounts": accs}


def norm_rid(s):
    return re.sub(r"\s+", "", str(s or "")).lower()


def decide(row, page, team_ab):
    """稽核的一列＋TTP 頁 → (要加的帳號清單, 理由)。team_ab：TTP 隊全名 → 我方縮寫（對不到回 ""）。純函式。"""
    if not page:
        return [], "TTP 查無此人"
    if page["name"].lower() != str(row["player"]).lower():
        return [], f"頁名不符（{page['name']}）"
    if page["team"]:
        ab = team_ab(page["team"])
        if not ab or ab.upper() != str(row["team"]).upper():
            return [], f"隊伍不符（TTP {page['team']}→{ab or '?'}，我方 {row['team']}）"
    elif not page["role"] or page["role"] != row.get("pos"):
        return [], f"TTP 沒寫隊伍、位置也對不上（{page['role'] or '?'} vs {row.get('pos')}）"
    out = []
    for a in page["accounts"]:
        if not a["active"] or a["region"] not in PLAT or "#" not in a["riotId"]:
            continue
        out.append({"player": row["player"], "team": row["team"], "platform": PLAT[a["region"]],
                    "riotId": a["riotId"], "ttp": True, "note": f"TTP {a['rank']}"})
    return out, "" if out else "沒有使用中的帳號"


def fetch_page(name):
    os.makedirs(CACHE, exist_ok=True)
    f = os.path.join(CACHE, re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower() + ".html")
    if os.path.exists(f) and time.time() - os.path.getmtime(f) < TTL:
        return open(f, encoding="utf-8").read(), False
    url = "https://www.trackingthepros.com/player/" + urllib.parse.quote(name.replace(" ", "_"))
    h = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read().decode("utf-8", "replace")
    open(f, "w", encoding="utf-8").write(h)
    return h, True


def main():
    dry = "--dry" in sys.argv
    aud = os.path.join(CACHE, "_audit.json")
    os.makedirs(CACHE, exist_ok=True)
    r = subprocess.run([sys.executable, os.path.join(HERE, "audit_soloq_coverage.py"), "--json", aud],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not os.path.exists(aud):
        print(f"⚠ 稽核失敗（略過，不動帳號檔）：{(r.stderr or '')[-200:]}")
        return 0
    rows = [x for x in json.load(open(aud, encoding="utf-8"))["rows"]
            if any(str(i).startswith(WANT) for i in x.get("issues") or [])]
    sys.path.insert(0, HERE)
    import fetch_dpm_soloq_accounts as D   # 隊全名 → 縮寫（同一張對照表，帳號檔的隊碼就是這樣來的）
    abbr = D.load_abbr()
    team_ab = lambda full: D.norm_ab(abbr.get(str(full).lower(), "")) or ""
    acc = json.load(open(ACC, encoding="utf-8"))
    have = {(str(e.get("player") or "").lower(), norm_rid(e.get("riotId"))) for e in acc}
    add, net, miss = [], 0, {}
    for row in rows:
        try:
            h, fresh = fetch_page(row["player"])
        except Exception as e:
            miss[row["player"]] = f"抓取失敗 {type(e).__name__}"
            continue
        if fresh:
            net += 1
            time.sleep(GAP)
        new, why = decide(row, parse_page(h), team_ab)
        if why:
            miss[f"{row['team']} {row['player']}"] = why
        for e in new:
            k = (e["player"].lower(), norm_rid(e["riotId"]))
            if k in have:
                continue
            have.add(k); add.append(e)
            print(f"  ＋ {e['team']} {e['player']}｜{e['riotId']}（{e['platform']}，{e['note']}）")
    print(f"TTP：查 {len(rows)} 位有問題的選手（連網 {net} 頁），新增 {len(add)} 隻帳號；沒補到 {len(miss)} 位")
    for k, v in list(miss.items())[:80]:
        print(f"    · {k}：{v}")
    if dry or not add:
        return 0
    acc.extend(add)
    with open(ACC, "w", encoding="utf-8") as f:
        json.dump(acc, f, ensure_ascii=False, indent=1)
    print(f"→ soloq_accounts.json 帳號總數 {len(acc)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
