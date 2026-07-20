# -*- coding: utf-8 -*-
"""用 dpm.lol 職業頁 API 重建 soloq 帳號清單（使用者定案 2026-07-20）。
端點 /v1/pros/{選手名} → {"players":[{puuid, gameName, tagLine, displayName, team, lane, platform, ranks, lastMatchTimestamp}...]}
puuid 即 dpm 可用 puuid（=dpmPuuid，免再 resolve）；team 欄用來比對消歧（同名不同隊，如 TL Morgan vs BRION Morgan）。
路由（使用者定案）：LCS/LEC/CBLOL（dpm 職業聯賽）以 dpm 為主＝整個換成 dpm 帳號；其餘（LPL/LCK…）以 OBGG 為主＝保留現有再 union 補 dpm。
名單＝現有 soloq_accounts.json 的 (player, team)（即比賽數據出現過的隊伍/選手）。峡谷之巅 dpm 不收，天然過濾。
安全：預設寫到 soloq_accounts.preview.json 並印 diff，不碰現行檔（--apply 才覆寫、先備份 .bak）。best-effort：過不了 Cloudflare 就中止不動檔。
用法：python scripts\\fetch_dpm_soloq_accounts.py         # 產生 preview + diff
      python scripts\\fetch_dpm_soloq_accounts.py --apply # 確認後正式覆寫
"""
import io, sys, json, os, re, time, urllib.parse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ACCOUNTS = os.path.join(HERE, "soloq_accounts.json")
PREVIEW = os.path.join(HERE, "soloq_accounts.preview.json")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
DPM_LEAGUES = ["lcs", "lec", "cblol"]           # 以 dpm 為主的職業聯賽
PLAT = {"NA1": "na1", "KR": "kr", "KR1": "kr", "EUW1": "euw1", "EUN1": "eun1", "BR1": "br1",
        "LA1": "la1", "LA2": "la2", "OC1": "oc1", "TR1": "tr1", "RU": "ru", "JP1": "jp1"}
# dpm 隊碼 → 本清單隊碼（僅列已知差異；相同者不需列）
TEAM_ALIAS = {"GEN": "GENG", "DNF": "DNS"}  # dpm 隊碼→本清單碼；DN Freecs 比賽改名 DNS


def norm(s):
    return re.sub(r"\s+", "", str(s or "")).lower()


def canon_team(t):
    return TEAM_ALIAS.get(t, t)


def match_players():
    """比賽數據(data_2026.js)裡實際出場過的選手名(正規化 set)——只重抓這些人，教練/替補等沒出場的不抓（使用者定案 2026-07-20）。"""
    s = set()
    try:
        d0 = open(os.path.join(ROOT, "data", "data_2026.js"), encoding="utf-8", errors="replace").read()
        J = json.loads(re.sub(r";\s*$", "", re.search(r"window\.LOL_DATA\s*=\s*(\{.*)", d0, re.S).group(1)))
        raw = J["tabs"]["RAW_DATA"]; hdr = raw[0]; C = {h: i for i, h in enumerate(hdr)}
        bi, ri, pi = C.get("blue_playername"), C.get("red_playername"), C.get("participantid")
        for r0 in raw[1:]:
            try:
                if not (1 <= int(r0[pi]) <= 5):
                    continue
            except Exception:
                continue
            for i2 in (bi, ri):
                if i2 is not None and i2 < len(r0) and r0[i2]:
                    s.add(norm(r0[i2]))
    except Exception as e:
        print(f"（比賽數據出場名單載入失敗：{e}）", flush=True)
    return s


def _launch(p):
    for kw in ({"channel": "chrome"}, {"channel": "msedge"}, {}):
        try:
            return p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"], **kw)
        except Exception:
            continue
    raise RuntimeError("找不到可用瀏覽器")


def _warm(pg):
    for wait in (4, 14, 25, 20):
        time.sleep(wait)
        try:
            st = pg.evaluate("async()=>{const r=await fetch('/v1/esport/soloq/top-teams');return r.status;}")
        except Exception:
            st = 0
        if st == 200:
            return True
        print(f"  Cloudflare 盤查中（{st}），續等…", flush=True)
    return False


def main():
    apply = "--apply" in sys.argv
    acc = json.load(open(ACCOUNTS, encoding="utf-8"))
    # 名單＝現有 (player, team)（比賽數據出現過的）；記住既有帳號供 union / 保留
    roster = []
    seen_pt = set()
    exist_by_pt = {}
    for a in acc:
        pl, tm = a.get("player"), a.get("team")
        if not pl or not tm:
            continue
        exist_by_pt.setdefault((pl, tm), []).append(a)
        if (pl, tm) not in seen_pt:
            seen_pt.add((pl, tm)); roster.append((pl, tm))
    print(f"名單：{len(roster)} 位選手（{len(acc)} 個現有帳號）", flush=True)

    KEEP_WL = {"theshy"}  # 特例白名單：復出中/沒出場也保留（使用者判例，與 index.html 積分顯示 _WL 一致）
    mp = match_players()
    if mp:
        def _played(pl):
            n = norm(pl)
            if n in mp or n in KEEP_WL:
                return True
            return norm(re.sub(r"\s*\(.*\)\s*$", "", pl)) in mp   # 去「(VN)」等後綴再比對，免誤丟
        before = len(roster)
        dropped = [pt for pt in roster if not _played(pt[0])]
        roster = [pt for pt in roster if _played(pt[0])]
        print(f"比賽數據出場過濾：{before} → {len(roster)} 位（丟棄 {len(dropped)} 位沒出場："
              f"{[t + '|' + p for p, t in dropped][:20]}{'…' if len(dropped) > 20 else ''}）", flush=True)
    else:
        print("⚠ 比賽數據出場名單空 → 不過濾（保險）", flush=True)

    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("（未安裝 playwright，略過）"); return

    dpm_by_pt = {}      # (player, team) -> [dpm 帳號 entries]
    dpm_primary = set()  # dpm 為主的隊碼（本清單碼）
    with sync_playwright() as p:
        b = _launch(p); pg = b.new_page(user_agent=UA)
        pg.goto("https://dpm.lol/", wait_until="domcontentloaded")
        if not _warm(pg):
            print("✗ 過不了 Cloudflare，中止（不動檔）"); b.close(); return

        for lg in DPM_LEAGUES:
            try:
                tt = pg.evaluate("async(u)=>{const r=await fetch(u);return r.ok?await r.json():null;}",
                                 f"/v1/esport/soloq/top-teams?league={lg}")
            except Exception:
                tt = None
            for t in (tt or []):
                dpm_primary.add(canon_team(t.get("team")))
        print(f"dpm 為主隊伍（{len(dpm_primary)}）：{sorted(dpm_primary)}", flush=True)

        n_hit = n_miss = 0
        for i, (pl, tm) in enumerate(roster, 1):
            try:
                j = pg.evaluate("async(u)=>{const r=await fetch(u);return r.ok?await r.json():null;}",
                                "/v1/pros/" + urllib.parse.quote(pl, safe=""))
            except Exception:
                j = None
            ents = []
            for a in ((j or {}).get("players") or []):
                if canon_team(a.get("team")) != tm:   # 同名消歧：隊必須相符
                    continue
                pu, gn, tl = a.get("puuid"), a.get("gameName"), a.get("tagLine")
                if not (pu and gn and tl):
                    continue
                ents.append({"player": pl, "team": tm,
                             "platform": PLAT.get(a.get("platform"), str(a.get("platform") or "").lower()),
                             "riotId": f"{gn}#{tl}", "dpmPuuid": pu})
            # 去重（同 riotId）
            uniq = {}
            for e in ents:
                uniq.setdefault(norm(e["riotId"]), e)
            dpm_by_pt[(pl, tm)] = list(uniq.values())
            if uniq:
                n_hit += 1
            else:
                n_miss += 1
            if i % 25 == 0:
                print(f"  ...{i}/{len(roster)}（命中 {n_hit}）", flush=True)
            time.sleep(0.5)
        b.close()
    print(f"dpm /v1/pros：命中 {n_hit} 位、查無 {n_miss} 位", flush=True)

    # 重建：dpm 為主隊→整換 dpm；其餘→union（保留現有再補 dpm）
    new_acc = []
    replaced = added = kept = 0
    diff_lines = []
    for (pl, tm) in roster:
        existing = exist_by_pt[(pl, tm)]
        dpm_ents = dpm_by_pt.get((pl, tm), [])
        old_rids = {norm(e["riotId"]) for e in existing}
        if tm in dpm_primary and dpm_ents:
            use = dpm_ents
            new_rids = {norm(e["riotId"]) for e in use}
            if old_rids != new_rids:
                replaced += 1
                diff_lines.append(f"  [換] {tm}|{pl}: {sorted(old_rids)} → {[e['riotId'] for e in use]}")
        else:
            use = list(existing)
            seen = set(old_rids)
            addl = [e for e in dpm_ents if norm(e["riotId"]) not in seen]
            if addl:
                use += addl; added += 1
                diff_lines.append(f"  [補] {tm}|{pl}: +{[e['riotId'] for e in addl]}（保留 {len(existing)} 舊）")
            else:
                kept += 1
        new_acc.extend(use)

    out = PREVIEW if not apply else ACCOUNTS
    if apply:
        json.dump(acc, open(ACCOUNTS + ".bak", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(new_acc, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n=== 變更摘要 ===", flush=True)
    print(f"  換帳號（dpm 主）: {replaced} 位｜補帳號（union）: {added} 位｜不變: {kept} 位", flush=True)
    print(f"  帳號總數：{len(acc)} → {len(new_acc)}", flush=True)
    for ln in diff_lines[:80]:
        print(ln, flush=True)
    if len(diff_lines) > 80:
        print(f"  …還有 {len(diff_lines) - 80} 條變更", flush=True)
    print(f"\n{'已覆寫 soloq_accounts.json（備份 .bak）' if apply else '→ 寫到 soloq_accounts.preview.json（現行檔未動）。確認後跑 --apply'}", flush=True)


if __name__ == "__main__":
    main()
