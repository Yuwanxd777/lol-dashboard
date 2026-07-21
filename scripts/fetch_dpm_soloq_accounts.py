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
TEAM_ALIAS = {"GEN": "GENG", "DNF": "DNS", "LLL": "LOUD"}  # dpm 隊碼→本清單碼；DNF→DNS(改名)、LOUD 在 dpm 用 LLL
# 使用者本機(localStorage USER_TABBR)改過、但 STATIC_TABBR 仍是舊值的縮寫覆寫（Python 抓不到 localStorage，這裡補）；key=隊全名小寫
ABBR_OVERRIDE = {"fluxo w7m": "FX"}
# 積分頁不列/不抓的選手（已離隊且不再於一級聯賽出場等）；正規化小寫名
BLOCK_PLAYERS = {"castle"}


def norm(s):
    return re.sub(r"\s+", "", str(s or "")).lower()


def canon_team(t):
    return TEAM_ALIAS.get(t, t)


def dpm_rank(a):
    """dpm /v1/pros 每帳號附帶的牌位(ranks[0])→存起來；Riot account-v1 查不到舊 riotId(改名等)時，fetch_soloq.py 拿它當備援。"""
    rk = ((a.get("ranks") or [{}])[0]) or {}
    return {"tier": rk.get("tier"), "rank": rk.get("rank"), "lp": rk.get("leaguePoints")} if rk.get("tier") else None


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


def load_abbr():
    """從 index.html 抽 STATIC_TABBR（隊全名→縮寫）＋ ABBR_OVERRIDE，供 Python 端算隊縮寫（localStorage 的 USER_TABBR 抓不到）。"""
    st = {}
    try:
        html = open(os.path.join(ROOT, "index.html"), encoding="utf-8", errors="replace").read()
        m = re.search(r"const STATIC_TABBR=\{(.*?)\};", html, re.S)
        if m:
            st = {str(k).strip().lower(): v for k, v in json.loads("{" + m.group(1) + "}").items()}
    except Exception as e:
        print(f"（STATIC_TABBR 載入失敗，改用壓縮全名：{e}）", flush=True)
    st.update({k.lower(): v for k, v in ABBR_OVERRIDE.items()})
    return st


def match_roster(abbr):
    """比賽數據(data_2026.js)每位出場選手 → 我方隊縮寫。隊縮寫＝隊全名經 STATIC_TABBR 換算；取該選手最後一次出場的隊。回 {選手名: 隊縮寫}。"""
    out = {}
    try:
        d0 = open(os.path.join(ROOT, "data", "data_2026.js"), encoding="utf-8", errors="replace").read()
        J = json.loads(re.sub(r";\s*$", "", re.search(r"window\.LOL_DATA\s*=\s*(\{.*)", d0, re.S).group(1)))
        raw = J["tabs"]["RAW_DATA"]; hdr = raw[0]; Cc = {h: i for i, h in enumerate(hdr)}
        bp, rp, pi = Cc.get("blue_playername"), Cc.get("red_playername"), Cc.get("participantid")
        bt, rt = Cc.get("blue_teamname"), Cc.get("red_teamname")
        for r0 in raw[1:]:
            try:
                if not (1 <= int(r0[pi]) <= 5):
                    continue
            except Exception:
                continue
            for pcol, tcol in ((bp, bt), (rp, rt)):
                if pcol is None or tcol is None or pcol >= len(r0) or not r0[pcol]:
                    continue
                full = r0[tcol] if (tcol is not None and tcol < len(r0)) else ""
                ab = abbr.get(str(full).strip().lower(), "") or re.sub(r"[^A-Za-z0-9]", "", str(full))[:5].upper()
                out[str(r0[pcol]).strip()] = ab   # 後出現覆蓋前面→自然取最近一隊
    except Exception as e:
        print(f"（match_roster 失敗：{e}）", flush=True)
    return out


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

    # ── 探索抓取（根因修正）：以前名單只含既有帳號→沒帳號的隊(Fluxo/LOUD/多數 LCS/LEC/LTA)永遠漏抓。
    #    這裡把「比賽出場但目前完全沒帳號」的選手補進名單，DPM 逐一查 /v1/pros 補帳號 ──
    ABBR = load_abbr()
    mr = match_roster(ABBR)  # {選手名: 我方隊縮寫}
    covered = {norm(a.get("player")) for a in acc}
    roster = [pt for pt in roster if norm(pt[0]) not in BLOCK_PLAYERS]   # 封鎖名單(已離隊/退出一級)不抓
    new_players = []
    for pl, ab in mr.items():
        n = norm(pl)
        if n in covered or n in BLOCK_PLAYERS:
            continue
        pt = (pl, ab)
        if pt in seen_pt:
            continue
        seen_pt.add(pt); roster.append(pt); new_players.append(pt)
    print(f"探索新增 {len(new_players)} 位無帳號的出場選手：{[t + '|' + p for p, t in new_players][:30]}{'…' if len(new_players) > 30 else ''}", flush=True)

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
            # dpm /v1/pros 區分大小寫：比賽數據常是小寫(ceo/xyno)但 dpm 顯示名是 Ceo/Xyno → 查無時自動試大小寫變體
            plist, _tried = [], []
            for _v in (pl, pl[:1].upper() + pl[1:], pl.title(), pl.upper(), pl.lower()):
                if not _v or _v in _tried:
                    continue
                _tried.append(_v)
                try:
                    j = pg.evaluate("async(u)=>{const r=await fetch(u);return r.ok?await r.json():null;}",
                                    "/v1/pros/" + urllib.parse.quote(_v, safe=""))
                except Exception:
                    j = None
                plist = [a for a in ((j or {}).get("players") or []) if a.get("puuid") and a.get("gameName") and a.get("tagLine")]
                if plist:
                    break
            teams_seen = {canon_team(a.get("team")) for a in plist}
            if tm in teams_seen:
                use_as = [a for a in plist if canon_team(a.get("team")) == tm]   # 精確隊碼相符優先
            elif len(teams_seen) == 1:
                use_as = plist                                                   # 同名只有一位職業選手→直接採用(縮寫跟 DPM 對不上也抓得到)
            else:
                use_as = []                                                      # 同名跨多隊且無一相符→無法安全消歧，跳過(避免抓錯人)
            ents = [{"player": pl, "team": tm,
                     "platform": PLAT.get(a.get("platform"), str(a.get("platform") or "").lower()),
                     "riotId": f"{a.get('gameName')}#{a.get('tagLine')}", "dpmPuuid": a.get("puuid"),
                     "dpmRank": dpm_rank(a)} for a in use_as]
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
        existing = exist_by_pt.get((pl, tm), [])   # 探索新增的選手沒有既有帳號→空清單(union 分支會把 dpm 帳號整批補上)
        dpm_ents = dpm_by_pt.get((pl, tm), [])
        old_rids = {norm(e["riotId"]) for e in existing}
        if tm in dpm_primary and dpm_ents:
            use = dpm_ents
            new_rids = {norm(e["riotId"]) for e in use}
            if old_rids != new_rids:
                replaced += 1
                diff_lines.append(f"  [換] {tm}|{pl}: {sorted(old_rids)} → {[e['riotId'] for e in use]}")
        else:
            dbr = {norm(e["riotId"]): e for e in dpm_ents}
            use = []
            for e in existing:                     # union：保留舊帳號，但同帳號若 dpm 也有→補上新的 dpmRank/dpmPuuid(舊帳號常缺)
                de = dbr.get(norm(e["riotId"]))
                if de:
                    e = dict(e)
                    if de.get("dpmRank"):
                        e["dpmRank"] = de["dpmRank"]
                    if de.get("dpmPuuid") and not e.get("dpmPuuid"):
                        e["dpmPuuid"] = de["dpmPuuid"]
                use.append(e)
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
