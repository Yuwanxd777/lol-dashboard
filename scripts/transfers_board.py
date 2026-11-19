# -*- coding: utf-8 -*-
"""轉會分頁「陣容表」資料（使用者 2026-11-19：參考巴哈那張 LCK 陣容圖——左＝戰隊、六大聯賽一路往下列，
欄＝上野中下輔＋教練；傳聞在 ID 前加 *；滑過格子顯示合約到期日、上一位選手、新加入者原本來自哪隊）。

全部來自 Leaguepedia Cargo（fetch_transfers 已經在用同一套 cookie／節流）：
  ① 一級隊與 2026 名冊：Tournaments × TournamentRosters（當季 Primary 非資格賽；每隊取最後一個賽段的名冊＝「上一位」）
  ② 官方現況：Players.Team（選手官宣加入／離隊後 wiki 直接改所屬隊 ⇒ 這就是「目前確認」的陣容）
  ③ 合約：Contracts（GCD；同隊取最晚的 ContractEnd、排除 IsRemoval）
  ④ 異動：RosterChanges（本休賽期加入的＝新人 ⇒ 找他上一個離開的隊＝原隊；教練用最近一次加入時的 Role 分主教練）
  ⑤ 傳聞：Sheep 推文（fetch_transfers 輸出層已套好 §路線§‹頁|名› 記號）——「X 將加入 Y」取第一個帶路線的名字；
     「Y 2027 陣容：A／B／C／D／E」依序對上野中下輔。官方已經確認的不重複列。
"""
import re
import urllib.parse

ROLE_OF = {"Top": "TOP", "Jungle": "JNG", "Mid": "MID", "Bot": "BOT", "Support": "SUP", "Coach": "COACH", "Analyst": "COACH"}
STAFF_ORDER = ["HC", "C", "SC", "PC", "AN"]   # 主教練／教練／戰略教練／路線教練／分析師（其餘助理教練、體能教練、經理…不列）
_STAFF_TOK = {"head coach": "HC", "interim head coach": "HC", "coach": "C", "strategic coach": "SC", "positional coach": "PC",
              "analyst": "AN", "head analyst": "AN", "data analyst": "AN", "strategy analyst": "AN", "gameplay analyst": "AN"}


def staff_code(rc_role, pl_role):
    """教練欄要不要列、列成什麼：先看最近一次加入這隊時的職稱（RosterChanges，可能是 Assistant Coach/Analyst 這種複合），
    沒有異動紀錄才退回 Players.Role（只有 Coach／Analyst 兩種）。複合職稱取優先序最高的那個"""
    toks = [t.strip().lower() for t in (rc_role or "").split("/") if t.strip()]
    if toks:
        got = [_STAFF_TOK[t] for t in toks if t in _STAFF_TOK]
        return min(got, key=STAFF_ORDER.index) if got else ""
    return _STAFF_TOK.get((pl_role or "").strip().lower(), "")
LG_SHORT = {"LoL Champions Korea": "LCK", "Tencent LoL Pro League": "LPL", "LoL EMEA Championship": "LEC",
            "League of Legends Championship Series": "LCS", "Circuit Brazilian League of Legends": "CBLOL",
            "League of Legends Championship Pacific": "LCP"}
ORDER = ["LCK", "LPL", "LEC", "LCS", "CBLOL", "LCP"]
LANES = ["TOP", "JNG", "MID", "BOT", "SUP"]
RG_LG = {"韓國": "LCK", "中國": "LPL", "歐洲": "LEC", "北美": "LCS", "巴西": "CBLOL", "亞太": "LCP", "越南": "LCP", "日本": "LCP"}


def uc(t):
    return t[:1].upper() + t[1:]


def key(n):
    """選手名正規化：去掉消歧義括號、小寫（Contracts／RosterChanges 的 Player 寫法不一：Zeus／Zeus (Choi Woo-je)／ucal）"""
    return re.sub(r"\s*\([^()]*\)\s*$", "", str(n if n is not None else "").replace("_", " ")).strip().lower()


def _in(vals):
    return "(" + ",".join('"%s"' % str(v).replace('"', '\\"') for v in vals) + ")"


def build(cargo, year, since, sheep, extra=None, wiki=None, exclude=()):
    """cargo＝build_predict_live.cargo；since＝本休賽期起點（YYYY-MM-DD）；sheep＝輸出層的 Sheep 條目；extra＝{隊名: 聯賽}（2027 新進）"""
    # ① 一級隊＋各隊最後一個賽段的名冊
    r = cargo({"tables": "Tournaments=T,TournamentRosters=TR", "join_on": "T.OverviewPage=TR.OverviewPage",
               "fields": "T.League=lg,T.DateStart=ds,TR.Team=tm,TR.RosterLinks=rl,TR.Roles=ro", "limit": "3000", "format": "json",
               "where": f'T.Year={year} AND T.TournamentLevel="Primary" AND T.IsQualifier=0 AND T.League IN ' + _in(LG_SHORT)})
    lg_of, last = {}, {}
    for x in r:
        tm = x.get("tm")
        if not tm:
            continue
        lg_of[tm] = LG_SHORT[x["lg"]]
        if tm not in last or (x.get("ds") or "") >= last[tm][0]:
            last[tm] = (x.get("ds") or "", x.get("rl") or "", x.get("ro") or "")
    for tm, lg in (extra or {}).items():
        lg_of.setdefault(tm, lg)
    # 下一季的升降級賽（使用者 2026-11-19「DFM 升降賽打輸了，應該換成打贏的那隊」）：Qualified=0 的一級隊拿掉、=1 的外來隊加進來
    try:
        for t in promotion(cargo, year):
            if t["ql"] and t["tm"] not in lg_of:
                lg_of[t["tm"]] = t["lg"]
            elif not t["ql"] and t["tm"] in lg_of:
                lg_of.pop(t["tm"])
    except Exception as e:
        print(f"   升降級賽查詢失敗（照 {year} 名單）：{type(e).__name__} {str(e)[:100]}")
    prev = {}
    for tm, (_, rl, ro) in last.items():
        d = prev.setdefault(tm, {})
        for p, ro1 in zip(rl.split(";;"), ro.split(";;")):
            rr = ROLE_OF.get(ro1.strip())
            if rr and p.strip():
                d.setdefault(rr, []).append(p.strip())
    # 改名前的舊隊名（DRX→Kiwoom DRX）在 Teams 表沒有自己的頁（是轉址）、解散的（Dignitas）IsDisbanded ⇒ 都不列；Name＝顯示名（LYON）
    tt = cargo({"tables": "Teams", "fields": "OverviewPage=pg,Name=n,IsDisbanded=dis", "where": "Teams.OverviewPage IN " + _in(sorted({uc(t) for t in lg_of})),
                "limit": "500", "format": "json"})
    disp = {x["pg"]: (x.get("n") or x["pg"]) for x in tt if str(x.get("dis")) != "1"}
    disp = {t: disp[uc(t)] for t in lg_of if uc(t) in disp}   # wiki 頁名首字母一律大寫（paiN Gaming → PaiN Gaming）
    teams = sorted(t for t in disp if t not in set(exclude))
    # ② 官方現況
    pl = cargo({"tables": "Players", "fields": "Players.ID=id,Players.OverviewPage=pg,Players.Team=tm,Players.Role=ro,Players.IsRetired=ret",
                "where": "Players.Team IN " + _in(teams) + ' AND Players.Role IN ("Top","Jungle","Mid","Bot","Support","Coach","Analyst")',
                "limit": "3000", "format": "json"})
    cur = {}   # 隊 → 位置 → [(ID, 頁)]
    team_of = {}
    for x in pl:
        if str(x.get("ret")) == "1":
            continue
        rr = ROLE_OF.get(x.get("ro"))
        cur.setdefault(x["tm"], {}).setdefault(rr, []).append((str(x["id"]), str(x.get("pg") or x["id"]), x.get("ro") or ""))
        team_of[key(x["pg"] or x["id"])] = x["tm"]
    # ②b 教練欄改用 wiki 戰隊頁的「Current Roster」本體（使用者 2026-11-19「每一隊的教練都去 WIKI 重新檢視」）：
    #     Tenures.IsCurrent × 加入那筆 RosterChanges 的職稱／狀態。Players.Role 只有 Coach／Analyst 兩種、Team 欄常沒跟上
    #     （TL Annibal 是 Business Analyst、SR Nulu 根本不在 SR 名單、kkOma 休假 inactive、SR 漏了路線教練 Selfie）
    try:
        tstaff = staff_tenures(cargo, teams)
        for tm in teams:
            cur.setdefault(tm, {})["COACH"] = tstaff.get(tm, [])
            for _, pg, *_ in tstaff.get(tm, []):
                team_of[key(pg)] = tm   # Players.Team 常沒跟上 ⇒ 教練的現任隊以 Tenures 為準（新人判定、原隊都靠它）
    except Exception as e:   # 查不到就退回 Players
        print(f"   教練現任名單（Tenures）查詢失敗，退回 Players：{type(e).__name__} {str(e)[:100]}")
        tstaff = None
    try:
        played = played_set(cargo, year, teams)
    except Exception as e:
        print(f"   出賽紀錄查詢失敗（不濾沒上場的人）：{type(e).__name__} {str(e)[:100]}")
        played = None
    # ③ 合約
    ct = cargo({"tables": "Contracts", "fields": "Player=p,Team=tm,ContractEnd=ce,IsRemoval=rm",
                "where": "Contracts.Team IN " + _in(teams) + f' AND Contracts.ContractEnd>="{since}"', "limit": "5000", "format": "json"})
    con = {}
    for x in ct:
        if str(x.get("rm")) == "1" or not x.get("ce"):
            continue
        k = (key(x["p"]), x["tm"])
        con[k] = max(con.get(k, ""), x["ce"][:10])
    # ④ 異動：這些隊近三年的加入紀錄（教練職稱＋本季新人）
    rc = cargo({"tables": "RosterChanges", "fields": "Date_Sort=d,Player=p,Direction=dir,Team=tm,Role=ro",
                "where": "RosterChanges.Team IN " + _in(teams) + f' AND RosterChanges.Date_Sort>="{int(year) - 3}-01-01"',
                "order_by": "RosterChanges.Date_Sort DESC", "limit": "5000", "format": "json"})   # 新到舊：上限 5000 筆時截掉的是最舊的
    joined = {}   # (player key, 隊) → (日期, 職稱)；只留最近一次加入
    for x in rc:
        if x.get("dir") == "Join":
            joined.setdefault((key(x["p"]), x["tm"]), ((x.get("d") or "")[:10], x.get("ro") or ""))
    # wiki 新聞句子裡最新的職稱（「Rather (Head Coach)'s contract…」「Mowgli (Coach to Head Coach)」）比 RosterChanges 新 ⇒ 優先
    news_role = {}
    for x in sorted(wiki or [], key=lambda x: (x.get("d") or "", x.get("n") or 0)):
        for m in re.finditer(r"‹([^|›]+)\|[^›]+›\s*\(([^()]+)\)", x.get("en") or ""):
            news_role[key(urllib.parse.unquote(m.group(1)))] = m.group(2).split(" to ")[-1]
    new_keys = sorted({k for (k, tm), (d, _) in joined.items() if d >= since and team_of.get(k) == tm})
    origin = {}
    if new_keys:
        names = [pg for t in cur.values() for v in t.values() for _, pg, *_ in v if key(pg) in new_keys]
        lv = cargo({"tables": "RosterChanges", "fields": "Date_Sort=d,Player=p,Direction=dir,Team=tm",
                    "where": "RosterChanges.Player IN " + _in(sorted(set(names) | {re.sub(r"\s*\([^()]*\)$", "", n) for n in names})) +
                             f' AND RosterChanges.Date_Sort>="{int(year) - 1}-06-01"',
                    "order_by": "RosterChanges.Date_Sort", "limit": "3000", "format": "json"})
        # 原隊＝他在別隊的最後一筆異動（離隊或加入都算）：舊隊漏記離隊時（Benny TT→UP，wiki 沒記 TT 離隊）也找得到
        for x in lv:
            k = key(x["p"])
            if team_of.get(k) and x["tm"] != team_of[k]:
                origin[k] = x["tm"]   # 照日期排序 ⇒ 留最後一個
    # ④b 續約（使用者 2026-11-19「續約就用白字」）：wiki「contract(s) extended / will remain」與 Sheep 官方「續約」消息裡的人
    #     ⇒ 不算新加入、不算合約到期（GCD 常晚幾天才更新，Kingen 續約到 2028 但 Contracts 還是 2026/11/16）
    resign = {}
    for x in wiki or []:
        for sen in re.split(r"(?<=\.)\s+", x.get("en") or ""):
            if re.search(r"extended|will remain", sen):
                y = re.search(r"through (\d{4})", sen)
                for pg in re.findall(r"‹([^|›]+)\|", sen):
                    resign[key(urllib.parse.unquote(pg))] = y.group(1) if y else ""
    for x in sheep or []:
        zh = x.get("zh") or ""
        if (x.get("st") or "") == "official" and "續約" in zh:
            y = re.search(r"(?:續約|延長)(?:到|至)?\s*(\d{4})", zh)
            for disp_ in re.findall(r"‹[^|›]+\|([^›]+)›", zh):
                resign.setdefault(key(disp_), y.group(1) if y else "")
    # ⑤ 傳聞
    rumor = parse_sheep(sheep)
    out = []
    for tm in teams:
        c = cur.get(tm, {})
        prevkeys = {key(p) for v in prev.get(tm, {}).values() for p in v}
        rows, gone = {}, {}
        for rr in LANES + ["COACH"]:
            cell = []
            ppl = c.get(rr, [])
            srole = {}
            if rr == "COACH":   # 只列主教練／教練／戰略教練／路線教練／分析師（使用者 2026-11-19），依序排
                keep = []
                for p in ppl:
                    s = p[3] if len(p) > 3 else staff_code(news_role.get(key(p[1])) or joined.get((key(p[1]), tm), ("", ""))[1], p[2])   # Tenures 來的已帶職稱代碼
                    if s:
                        srole[p[1]] = s; keep.append(p)
                ppl = sorted(keep, key=lambda p: STAFF_ORDER.index(srole[p[1]]))
            for pid, pg, *_ in ppl:
                k = key(pg)
                e = {"n": pid, "p": pg}
                if srole.get(pg):
                    e["sr"] = srole[pg]
                if con.get((k, tm)):
                    e["c"] = con[(k, tm)]
                if k in resign or key(pid) in resign:
                    e["rs"] = resign.get(k, resign.get(key(pid), "")) or "1"
                jd = joined.get((k, tm), ("", ""))[0]
                if jd >= since and k not in prevkeys and "rs" not in e:   # 續約／換職位也會記一筆 Join ⇒ 2026 名冊上本來就在的不算新加入
                    e["new"] = jd
                    if origin.get(k):
                        e["from"] = origin[k]
                # 今年沒替這隊上過場的選手不列（使用者 2026-11-19「G2 Sola 是簽來當 co-stream 實況主的…沒上過場的都不應該出現在名單」）；新人不套
                #     本休賽期有官方續約消息的不套（NS Calix 今年沒上場但續約到 2028，是明年的人）
                if rr != "COACH" and "new" not in e and "rs" not in e and played is not None and (k, tkey(tm)) not in played and (key(pid), tkey(tm)) not in played:
                    continue
                cell.append(e)
            have = {key(e["p"]) for e in cell} | {key(e["n"]) for e in cell}
            for rmr in rumor.get((tkey(tm), rr), []):
                if key(rmr["n"]) in have:
                    continue
                ot = team_of.get(key(rmr["n"]))
                if ot and ot != tm and joined.get((key(rmr["n"]), ot), ("", ""))[0] >= rmr["d"][:10]:
                    continue   # 傳聞之後他已官宣去別隊
                e = {"n": rmr["n"], "p": rmr.get("p") or "", "tip": rmr["tip"], "d": rmr["d"][:10]}
                if rmr["st"] == "rumor":
                    e["r"] = 1
                if rmr.get("from"):
                    e["from"] = rmr["from"]
                cell.append(e)
            # 使用者 2026-11-19「如果該路線有新加入的選手，舊的就當作離隊」：選手路線有官方新人（wiki 新加入或 Sheep 官方消息）
            # ⇒ 同格原有的人移到「上一位」（傳聞不算新人；教練欄不套）
            moved = []
            if rr != "COACH" and any(("new" in e or ("tip" in e and "r" not in e)) for e in cell):
                moved = [e["p"] or e["n"] for e in cell if "new" not in e and "tip" not in e]
                cell = [e for e in cell if "new" in e or "tip" in e]
            if moved:
                gone.setdefault(rr, []).extend(moved)
            if cell:
                rows[rr] = cell
        pv = {}
        for rr in LANES + ["COACH"]:
            # 還在隊上的人不是「上一位」（使用者 2026-11-19「Ratis 沒說離開 GZ，他是教練」：職稱不在五種裡沒顯示，不代表離隊）
            here = {key(e["p"]) for e in rows.get(rr, [])} | {key(pg) for v in c.values() for _, pg, *_ in v if key(pg) not in {key(g) for g in gone.get(rr, [])}}
            seen, L = set(), []
            for p in gone.get(rr, []) + prev.get(tm, {}).get(rr, []):   # 被新人擠掉的排前面
                if key(p) not in here and key(p) not in seen:
                    seen.add(key(p)); L.append(p)
            pv[rr] = L
        pv = {rr: v for rr, v in pv.items() if v}
        out.append({"tm": tm, "nm": disp[tm], "lg": lg_of[tm], "r": rows, "prev": pv,
                    "_still": sorted({key(g) for v in gone.values() for g in v})})   # 被新人擠掉、其實還在隊上的（add_tenure 用完拿掉）
    try:
        add_tenure(cargo, out)
    except Exception as e:   # 查不到效力期間就只列名字
        print(f"   上一位效力期間查詢失敗：{type(e).__name__} {str(e)[:100]}")
        for x in out:
            x.pop("_still", None)
    try:
        rk = team_rank(cargo, year)
    except Exception as e:   # 名次查不到就退回字母序，不擋整張表
        print(f"   陣容表排序名次失敗（改字母序）：{type(e).__name__} {str(e)[:100]}")
        rk = {}
    for x in out:
        k = rk.get(tkey(x["tm"])) or rk.get(tkey(x["nm"]))
        if k:
            x["rk"] = k[3]
    out.sort(key=lambda x: (ORDER.index(x["lg"]) if x["lg"] in ORDER else 9,
                            (rk.get(tkey(x["tm"])) or rk.get(tkey(x["nm"])) or (999, 999, 999, ""))[:3], x["tm"].lower()))
    return out


def played_set(cargo, year, teams):
    """{(選手 key, 隊 key)}：該年替這隊打過至少一場（ScoreboardPlayers，所有賽事）"""
    got = set()
    for i in range(0, len(teams), 10):
        r = cargo({"tables": "ScoreboardPlayers=SP", "fields": "SP.Link=p,SP.Team=tm,COUNT(*)=n", "group_by": "SP.Link,SP.Team",
                   "where": "SP.Team IN " + _in(teams[i:i + 10]) + f' AND SP.DateTime_UTC>="{year}-01-01" AND SP.DateTime_UTC<"{int(year) + 1}-01-01"',
                   "limit": "5000", "format": "json"})
        for x in r:
            if x.get("p"):
                got.add((key(x["p"]), tkey(x["tm"])))
    if len(got) < 100:
        raise RuntimeError(f"出賽紀錄只有 {len(got)} 筆，不像完整")
    return got


def staff_tenures(cargo, teams):
    """{隊: [(顯示 ID, 頁名, 職稱, 職稱代碼)]}：各隊目前在職、職稱屬於五種的教練／分析師。
    狀態 inactive（休假、停職）不列；同一人同時掛兩隊（舊隊漏記離隊，如 Benny TT→UP）只算最晚加入的那隊"""
    rows = []
    for i in range(0, len(teams), 20):
        rows += cargo({"tables": "Tenures=T,RosterChanges=RC", "join_on": "T.RosterChangeIdJoin=RC.RosterChangeId",
                       "fields": "T.Player=p,T.Team=tm,T.DateJoin=dj,RC.Role=ro,RC.Status=st",
                       "where": "T.IsCurrent=1 AND T.Team IN " + _in(teams[i:i + 20]), "limit": "5000", "format": "json"})
    best = {}
    for x in rows:
        p = str(x.get("p") or "")
        code = staff_code(x.get("ro") or "", "")
        if not p or not code or str(x.get("st") or "").lower() == "inactive":
            continue
        k = key(p)
        if k not in best or (x.get("dj") or "") > (best[k].get("dj") or ""):
            best[k] = dict(x, code=code)
    # 顯示 ID：頁名可能是舊名或轉址（Deam147 → Deam），查 PlayerRedirects 拿現在的 ID
    pages = sorted({str(x["p"]) for x in best.values()})
    idof = {}
    for i in range(0, len(pages), 60):
        for y in cargo({"tables": "PlayerRedirects=PR,Players=P", "join_on": "PR.OverviewPage=P.OverviewPage",
                        "fields": "PR.AllName=an,P.ID=id,P.OverviewPage=pg", "where": "PR.AllName IN " + _in(pages[i:i + 60]),
                        "limit": "500", "format": "json"}):
            if y.get("id") is not None:
                idof[str(y["an"])] = (str(y["id"]), str(y.get("pg") or y["an"]))
    out = {}
    for x in best.values():
        p = str(x["p"])
        disp_id, pg = idof.get(p, (re.sub(r"\s*\([^()]*\)$", "", p), p))
        out.setdefault(x["tm"], []).append((disp_id, pg, x.get("ro") or "", x["code"]))
    return out


def stints(evs):
    """同一人在同一隊的 RosterChanges（由舊到新 [(日期, Join/Leave)]）→ 最後一段效力 (起, 迄)；迄＝"" 表示還沒離隊。
    Leave 後 45 天內又 Join 同隊（換職位、轉二軍再升回、續約重記）視為同一段"""
    s = e = ""
    for d, dr in evs:
        if dr == "Join":
            if not s or (e and _days(e, d) > 45):
                s = d
            e = ""
        elif dr == "Leave" and s:
            e = d
    return s, e


def _days(a, b):
    import datetime as _dt
    f = lambda x: _dt.date(*map(int, x.split("-")))
    return (f(b) - f(a)).days


def add_tenure(cargo, out):
    """上一位選手在這隊待了多久（使用者 2026-11-19「上一位要寫他待了多久」）：prev 由名字字串改成 {n, s, e}"""
    want = {(key(p), x["tm"]) for x in out for v in x["prev"].values() for p in v}
    names = sorted({p for x in out for v in x["prev"].values() for p in v})
    ev, joins = {}, {}
    for i in range(0, len(names), 40):
        part = names[i:i + 40]
        r = cargo({"tables": "RosterChanges", "fields": "Date_Sort=d,Player=p,Direction=dir,Team=tm",
                   "where": "RosterChanges.Player IN " + _in(sorted(set(part) | {re.sub(r"\s*\([^()]*\)$", "", n) for n in part})),
                   "order_by": "RosterChanges.Date_Sort", "limit": "5000", "format": "json"})
        for y in r:
            if not y.get("d"):
                continue
            k = (key(y["p"]), y["tm"])
            if k in want:
                ev.setdefault(k, []).append((y["d"][:10], y.get("dir")))
            if y.get("dir") == "Join":
                joins.setdefault(key(y["p"]), []).append((y["d"][:10], y["tm"]))
    for x in out:
        still = set(x.pop("_still", []))
        for rr, v in x["prev"].items():
            L = []
            for p in v:
                s, e = stints(sorted(ev.get((key(p), x["tm"]), [])))
                if s and not e:   # 沒記離隊、但之後加入了別隊（Benny 2026-03 進 TT、11-06 進 UP，TT 沒記離隊）⇒ 以加入別隊那天當離隊日
                    later = sorted(d for d, t in joins.get(key(p), []) if t != x["tm"] and d > s)
                    if later:
                        e = later[0]
                d = {"n": p}
                if s:
                    d["s"] = s
                    if e:
                        d["e"] = e
                    elif key(p) not in still:
                        d["e"] = "?"   # 不在隊上、wiki 又沒記離隊 ⇒ 前端顯示「離隊日未記錄」，不寫「今」
                L.append(d)
            x["prev"][rr] = L


def promotion(cargo, year):
    """{year+1} Season/Promotion 的結果 → [{tm, lg, ql}]（六大聯賽有開升降級賽的：LCS／CBLOL／LCP…）"""
    shorts = {v: k for k, v in LG_SHORT.items()}
    pages = [f"{s}/{int(year) + 1} Season/Promotion" for s in shorts]
    r = cargo({"tables": "TournamentResults", "fields": "OverviewPage=pg,Team=tm,Qualified=ql",
               "where": "TournamentResults.OverviewPage IN " + _in(pages), "limit": "200", "format": "json"})
    return [{"tm": x["tm"], "lg": x["pg"].split("/")[0], "ql": str(x.get("ql")) == "1"} for x in r if x.get("tm")]


def team_rank(cargo, year):
    """聯賽內排序（使用者 2026-11-19「依照世界賽排序，沒進世界賽的依照第三賽段季後賽成績，也沒進季後賽就看第三賽段例行賽」）
    → {隊名 key: (世界賽名次, 季後賽名次, 例行賽名次, 說明)}；缺的項目 999。
    第三賽段＝各聯賽當年最後一個 split（CBLOL 只有兩段 ⇒ 取 Split 2）；同一 split 有兩個季後賽頁（LCK 的 Play-In＋Playoffs）
    ⇒ 最晚開始的是正賽、其餘（入圍）名次 +100 排在正賽隊伍後面。名次：TournamentResults，例行賽沒有就退 Standings。"""
    ts = cargo({"tables": "Tournaments=T", "fields": "T.OverviewPage=pg,T.League=lg,T.DateStart=ds,T.Split=sp,T.IsPlayoffs=po",
                "where": f'T.Year={year} AND T.TournamentLevel="Primary" AND T.IsQualifier=0 AND T.League IN ' + _in(LG_SHORT),
                "order_by": "T.DateStart", "limit": "500", "format": "json"})
    by_lg = {}
    for t in ts:
        by_lg.setdefault(t["lg"], []).append(t)
    po_pages, reg_pages = {}, []   # 季後賽頁 → 名次加權
    for lg, L in by_lg.items():
        sp = [t for t in L if str(t.get("po")) != "1"][-1]["sp"]   # 最後一個例行賽的 split
        reg_pages += [t["pg"] for t in L if t["sp"] == sp and str(t.get("po")) != "1"]
        pos = [t for t in L if t["sp"] == sp and str(t.get("po")) == "1"]
        for i, t in enumerate(pos):
            po_pages[t["pg"]] = 0 if i == len(pos) - 1 else 100
    wpage = f"{year} Season World Championship"
    pages = [wpage] + list(po_pages) + reg_pages
    res = cargo({"tables": "TournamentResults", "fields": "OverviewPage=pg,Team=tm,Place_Number=pn,Place=pl",
                 "where": "TournamentResults.OverviewPage IN " + _in(pages), "limit": "2000", "format": "json"})
    have_reg = {x["pg"] for x in res if x["pg"] in reg_pages}
    miss = [p for p in reg_pages if p not in have_reg]
    if miss:
        res += cargo({"tables": "Standings", "fields": "OverviewPage=pg,Team=tm,Place=pn", "where": "Standings.OverviewPage IN " + _in(miss),
                      "limit": "1000", "format": "json"})
    W, P, R = {}, {}, {}
    for x in res:
        try:
            n = int(x.get("pn"))
        except (TypeError, ValueError):
            continue
        k = tkey(x["tm"])
        if x["pg"] == wpage:
            W[k] = (n, str(x.get("pl") or n))
        elif x["pg"] in po_pages:
            v = n + po_pages[x["pg"]]
            P[k] = min(P.get(k, 999), v)
        elif x["pg"] in reg_pages:
            R[k] = min(R.get(k, 999), n)
    out = {}
    for k in set(W) | set(P) | set(R):
        w = W.get(k, (999, ""))
        p, r = P.get(k, 999), R.get(k, 999)
        note = f"W{w[1]}" if w[0] < 999 else (f"P{p}" if p < 100 else (f"I{p - 100}" if p < 999 else (f"R{r}" if r < 999 else "")))
        out[k] = (w[0], p, r, note)
    return out


def rumor_any(rumor, tm):
    return any(t == tkey(tm) for t, _ in rumor)


def tkey(n):
    return re.sub(r"\s*\([^()]*\)\s*$", "", n or "").strip().lower()


_NM = r"(?:‹([^|›]+)\|([^›]+)›|([A-Za-z0-9][A-Za-z0-9_.'-]*(?: [A-Z][A-Za-z0-9_.'-]*)?))"


def _name(m, i):
    pg, disp, plain = m.group(i), m.group(i + 1), m.group(i + 2)
    return (disp or plain or "").strip(), (pg or "").replace("_", " ")


def parse_sheep(sheep):
    """Sheep 推文 → {(隊, 位置): [{n, p, d, tip, from}]}；同一人只留最新一則（照日期由舊到新覆蓋）"""
    best = {}
    for x in sorted(sheep, key=lambda x: x["d"]):
        tags = x.get("tags") or []
        zh = x.get("zh") or ""
        plain = re.sub(r"‹[^|›]+\|([^›]+)›", r"\1", re.sub(r"§[A-Z]+§", "", zh))
        tip = re.sub(r"^【[^】]+】", "", plain).strip()
        st = x.get("st") or "rumor"
        inn = [t for t in tags if len(t) > 2 and t[2] == "in" and t[1]]
        out = [t[1] for t in tags if len(t) > 2 and t[2] == "out" and t[1]]
        if "陣容" in zh and "：" in zh and len([t for t in tags if t[1]]) == 1:
            tm = [t for t in tags if t[1]][0][1]
            body = zh.split("：", 1)[1]
            body = re.split(r"[。；]", body)[0]
            for i, it in enumerate(body.split("／")[:5]):
                it = re.sub(r"§[A-Z]+§", "", it).strip()
                if not it or "未定" in it or "?" in it:
                    continue
                m = re.match(_NM, it)
                if m:
                    n, pg = _name(m, 1)
                    best[n.lower()] = {"tm": tm, "rr": LANES[i], "n": n, "p": pg, "d": x["d"], "tip": tip, "st": st}
            continue
        if x.get("kind") not in ("join", "both") or len(inn) != 1:
            continue
        m = re.search(r"§(TOP|JNG|MID|BOT|SUP)§" + _NM, zh)
        if not m:
            continue
        n, pg = _name(m, 2)
        best[n.lower()] = {"tm": inn[0][1], "rr": m.group(1), "n": n, "p": pg, "d": x["d"], "tip": tip, "st": st,
                           "from": out[0] if out else ""}
    res = {}
    for v in best.values():
        res.setdefault((tkey(v["tm"]), v["rr"]), []).append(v)
    return res
