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
_STAFF_TOK = {"head coach": "HC", "interim head coach": "HC", "coach": "C", "assistant coach": "C",   # 使用者 2026-11-19「助理教練就是教練」
"strategic coach": "SC", "positional coach": "PC",
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


def _sister(frm, tm):
    """frm 是 tm 同組織的二隊／青訓隊？（HANJIN BRION Challengers → HANJIN BRION、T1 Esports Academy → T1）"""
    a, b = frm.split(), tm.split()
    return bool(a and b and a[0].lower() == b[0].lower() and frm != tm
                and re.search(r"Academy|Challengers|Chall\.|Youth|Rookies|Junior|Blue$|\.A$|Second|Rising|NXT", frm, re.I))


RETIRED = {}   # 最近一次 build 查到的退役選手：{key: (頁名, ID, 路線, 隊顯示名, 聯賽)}（fetch_transfers 拿去補退役消息）


def build(cargo, year, since, sheep, extra=None, wiki=None, exclude=(), farewell=None, succ=None):
    """cargo＝build_predict_live.cargo；since＝本休賽期起點（YYYY-MM-DD）；sheep＝輸出層的 Sheep 條目；extra＝{隊名: 聯賽}（2027 新進）"""
    import datetime as _dt
    today = _dt.date.today().isoformat()
    green_out = set()   # （人, 隊）：合約還在但傳出要走、同一路已有別的人選 ⇒ 格子不顯示、改列自由人（仍是綠字）
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
    prev, prole = {}, {}
    for tm, (_, rl, ro) in last.items():
        d = prev.setdefault(tm, {})
        for p, ro1 in zip(rl.split(";;"), ro.split(";;")):
            rr = ROLE_OF.get(ro1.strip())
            if rr and p.strip():
                d.setdefault(rr, []).append(p.strip())
                prole[(tm, p.strip())] = ro1.strip()
    # 改名前的舊隊名（DRX→Kiwoom DRX）在 Teams 表沒有自己的頁（是轉址）、解散的（Dignitas）IsDisbanded ⇒ 都不列；Name＝顯示名（LYON）
    tt = cargo({"tables": "Teams", "fields": "OverviewPage=pg,Name=n,Short=sh,IsDisbanded=dis", "where": "Teams.OverviewPage IN " + _in(sorted({uc(t) for t in lg_of})),
                "limit": "500", "format": "json"})
    disp = {x["pg"]: (x.get("n") or x["pg"]) for x in tt if str(x.get("dis")) != "1"}
    short = {x["pg"]: x.get("sh") or "" for x in tt}
    disp = {t: disp[uc(t)] for t in lg_of if uc(t) in disp}   # wiki 頁名首字母一律大寫（paiN Gaming → PaiN Gaming）
    # 接手席位的新隊（OPT 接 DIG）：新隊還沒有任何人 ⇒ 先照原本那隊的陣容顯示（使用者 2026-11-20「新戰隊 OPT 的選手應該先依照本來的隊伍去顯示」）。
    #   做法＝原本那隊（已解散、平常不列）照常算一列，最後把那一列改掛新隊的名字，新隊自己那列空的就不要
    succ = {n_: o_ for n_, o_ in (succ or {}).items() if o_ in lg_of}
    for n_, o_ in succ.items():
        disp.setdefault(o_, o_)
    teams = sorted(t for t in disp if t not in set(exclude) and t not in succ)
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
        tstaff, allcur = staff_tenures(cargo, teams)
        for tm in teams:
            cur.setdefault(tm, {})["COACH"] = tstaff.get(tm, [])
            for _, pg, *_ in tstaff.get(tm, []):
                team_of[key(pg)] = tm   # Players.Team 常沒跟上 ⇒ 教練的現任隊以 Tenures 為準（新人判定、原隊都靠它）
    except Exception as e:   # 查不到就退回 Players
        print(f"   教練現任名單（Tenures）查詢失敗，退回 Players：{type(e).__name__} {str(e)[:100]}")
        tstaff, allcur = None, {}
    try:
        played = played_set(cargo, year, teams)
    except Exception as e:
        print(f"   出賽紀錄查詢失敗（不濾沒上場的人）：{type(e).__name__} {str(e)[:100]}")
        played = None
    # ③ 合約
    # 同一人同一隊常有好幾筆（BLG Viper：2026-01 那則記到 2027-11-16、2026-11-12 那則改成 2026-11-17）⇒ 以「最新那則公告」（NewsId 的日期）為準，
    #   不是取到期日最晚的（使用者 2026-11-20 全面核對選手頁：Viper／Tian／climber 表上多算了一年）；NewsId 缺的才退回比到期日
    ct = cargo({"tables": "Contracts", "fields": "Player=p,Team=tm,ContractEnd=ce,IsRemoval=rm,NewsId=nid",
                "where": "Contracts.Team IN " + _in(teams) + f' AND Contracts.ContractEnd>="{since}"', "limit": "5000", "format": "json"})
    con, con_at = {}, {}

    def _nid(x):
        m_ = re.search(r"(\d{4}-\d{2}-\d{2})_(\d+)", str(x.get("nid") or ""))
        return (m_.group(1), int(m_.group(2))) if m_ else ("", 0)
    for x in ct:
        if str(x.get("rm")) == "1" or not x.get("ce"):
            continue
        k = (key(x["p"]), x["tm"])
        at = (_nid(x), x["ce"][:10])
        if k not in con or at > con_at[k]:
            con[k], con_at[k] = x["ce"][:10], at
    # ③b Contracts（GCD）沒有的 ⇒ 用 wiki 戰隊頁名單上那欄合約日（Players.Contract；使用者 2026-11-20「不知道選手合約到何時 就是 WIKI 上該隊的網站看 例如 Quad」）
    try:
        for x in cargo({"tables": "Players", "fields": "Players.OverviewPage=pg,Players.ID=id,Players.Team=tm,Players.Contract=c",
                        "where": "Players.Team IN " + _in(teams) + ' AND Players.Contract IS NOT NULL', "limit": "3000", "format": "json"}):
            c_ = str(x.get("c") or "")[:10]
            if c_ >= since:
                con.setdefault((key(x.get("pg") or x["id"]), x["tm"]), c_)
    except Exception as e:
        print(f"   戰隊頁合約日（Players.Contract）查詢失敗：{type(e).__name__} {str(e)[:100]}")
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
    promo_hc = {}   # 人 → 「Coach to Head Coach」（提示小框要寫怎麼升的，使用者 2026-11-20）
    for x in wiki or []:
        if (x.get("d") or "") >= since:
            for m in re.finditer(r"‹([^|›]+)\|[^›]+›\s*\(([^()]+ to (?:Interim )?Head Coach)\)", x.get("en") or ""):
                promo_hc[key(urllib.parse.unquote(m.group(1)))] = m.group(2)
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
    # ④c 合約到期、還沒宣布離隊（使用者 2026-11-19「教練的合約到期不要預設離隊啊，要是藍字」「GEN 就沒有任何宣布」）：
    #     wiki 在合約到期日自動記一筆 Leave（Kiin／Canyon／Lyn／Nova 都是 11/16），跟真的宣布離隊分不出來 ⇒
    #     離隊日＝合約到期日（±1 天）、之後沒加入別隊、也沒有官方「分道揚鑣／告別」消息的人留在原隊，合約欄顯示已到期（藍字）。
    #     官方公告「合約到期」（Gen.G announce that Kiin's contract has expired）也算宣布離隊（使用者確認 GEN 有發布）
    ann = set()
    for x in sheep or []:
        if (x.get("st") or "") != "official" or x.get("kind") not in ("leave", "both"):
            continue
        txt = (x.get("en") or "") + " " + (x.get("zh") or "")
        if not re.search(r"part(?:s|ed)? ways|farewell|depart|leaves? the|bid(?:s)? goodbye|contract (?:has )?expired|分道揚鑣|告別|道別|離開|離隊|合約到期", txt, re.I):
            continue
        outs = [tkey(t[1]) for t in (x.get("tags") or []) if len(t) > 2 and t[2] == "out" and t[1]]
        for nm_ in re.findall(r"‹[^|›]+\|([^›]+)›", txt):
            for o in outs:
                ann.add((key(nm_), o))
    # wiki 新聞的「X leaves」句（來源＝戰隊官方 X／FB 貼文）也是宣布離隊（使用者 2026-11-19「BRO 教練 Duke 應該是有宣佈離隊的 WIKI 上也有」）
    for x in wiki or []:
        if x.get("kind") not in ("leave", "both") or not x.get("team"):
            continue
        for sen in re.split(r"(?<=\.)\s+", x.get("en") or ""):
            if re.search(r"\bleaves?\b|\bdeparts?\b|parts? ways|contract (?:has )?expired", sen) and not re.search(r"leaves? for|joins", sen):
                for pg_, nm_ in re.findall(r"‹([^|›]+)\|([^›]+)›", sen):
                    ann.add((key(nm_), tkey(x["team"])))
                    ann.add((key(urllib.parse.unquote(pg_).replace("_", " ")), tkey(x["team"])))
    # 戰隊官方 Thank you／Farewell 文（PTT [情報]／[外絮] 轉貼，使用者 2026-11-19「CFO 的選手不是宣布離隊了嗎 那就不應該是藍字」）：
    #   標題認隊（縮寫／隊名），內文有點到名字的人＝官方宣布離隊；標題寫「全員」⇒ 該隊合約到期的人全部算
    fw = {}
    for f in farewell or []:
        ttl = f.get("title") or ""
        for tm in teams:
            al = {disp.get(tm, tm), tm, short.get(uc(tm), "")} | ({"KRX"} if "DRX" in tm else set())
            if any(a and re.search(r"(?<![A-Za-z0-9])" + re.escape(a) + r"(?![A-Za-z0-9])", ttl, re.I) for a in al):
                fw.setdefault(tkey(tm), []).append((ttl + "\n" + (f.get("body") or ""), "全員" in ttl))
    def _fw(pg, tm):
        n = re.sub(r"\s*\([^()]*\)$", "", pg)
        return any(a or re.search(r"(?<![A-Za-z0-9])" + re.escape(n) + r"(?![A-Za-z0-9])", t, re.I) for t, a in fw.get(tkey(tm), []))
    expired, lastev = {}, {}
    for x in rc:   # 新到舊
        k2 = (key(x["p"]), x["tm"])
        if k2 not in lastev:
            lastev[k2] = x
    # annd＝本休賽期宣布離隊、還沒去別隊的人（使用者 2026-11-19「如果宣布離隊 但該隊沒有任何傳聞跟新簽約的消息 就是藍字加上刪除線」）
    #   ⇒ 主迴圈裡那個位置沒有新簽約／傳聞時留在格子（gone＝1，前端藍字刪除線）；有人補上就照舊進「上一位」
    annd = {}
    for (k, tm), x in lastev.items():
        d = (x.get("d") or "")[:10]
        ce = con.get((k, tm))
        if x.get("dir") != "Leave" or d < since:
            continue
        if (team_of.get(k) and team_of[k] != tm) or any(k in v for t2, v in allcur.items() if t2 != tm):
            continue   # 已經去別隊
        dd = (k, tkey(tm)) in ann or _fw(str(x["p"]), tm) or not ce or abs(_days(min(d, ce), max(d, ce))) > 1
        ro = x.get("ro") or ""
        pg = str(x["p"])
        disp_id = re.sub(r"\s*\([^()]*\)$", "", pg)
        if (key(disp_id), tkey(tm)) in ann:
            dd = True
        tgt = annd if dd else expired   # 宣布離隊（或不是合約到期那天走的）／合約到期未宣布
        rr = ROLE_OF.get(ro) if ro in ("Top", "Jungle", "Mid", "Bot", "Support") else None
        if rr:
            tgt.setdefault(tm, {}).setdefault(rr, []).append((disp_id, pg, ro))
        else:
            code = staff_code(ro, "")
            if code:
                tgt.setdefault(tm, {}).setdefault("COACH", []).append((disp_id, pg, ro, code))
    # ⑤ 傳聞
    rumor = parse_sheep(sheep)
    # 傳聞人選沒寫原隊的（陣容整理文、PTT 沒填）⇒ 查 wiki 現在掛在哪一隊補上：小框「來自」、消息的原隊欄用得到，
    #   評分也靠它判斷是不是次級聯賽上來的（使用者 2026-11-20「次級上來且沒有一軍出賽紀錄的選手 應該比中位數低 10 分左右」）
    need = sorted({v["p"] for L in rumor.values() for v in L if v.get("p") and not v.get("from")})
    if need:
        try:
            rows = []
            for i in range(0, len(need), 40):
                rows += cargo({"tables": "Players", "fields": "Players.OverviewPage=pg,Players.Team=tm",
                               "where": "Players.OverviewPage IN " + _in(need[i:i + 40]), "limit": "500", "format": "json"})
            cur_tm = {key(x["pg"]): x["tm"] for x in rows if x.get("tm")}
            for L in rumor.values():
                for v in L:
                    t_ = cur_tm.get(key(v.get("p") or ""))
                    if not v.get("from") and t_ and tkey(t_) != tkey(v["tm"]):
                        v["from"] = t_
        except Exception as e:
            print(f"   傳聞人選原隊查詢失敗：{type(e).__name__} {str(e)[:100]}")
    # 連頁名都沒有的（Sheep 陣容整理文只有 ID）⇒ 用 ID＋路線找：同 ID 同路線、現在有隊的剛好一位才認
    need = sorted({v["n"] for L in rumor.values() for v in L if not v.get("from")})
    if need:
        try:
            rows = []
            for i in range(0, len(need), 40):
                rows += cargo({"tables": "Players", "fields": "Players.ID=id,Players.Team=tm,Players.Role=ro",
                               "where": "Players.ID IN " + _in(need[i:i + 40]) + " AND Players.Team IS NOT NULL", "limit": "500", "format": "json"})
            for L in rumor.values():
                for v in L:
                    if v.get("from"):
                        continue
                    c_ = {x["tm"] for x in rows if key(str(x["id"])) == key(v["n"]) and ROLE_OF.get((x.get("ro") or "").split(",")[0].strip()) == v["rr"] and x.get("tm")}
                    if len(c_) == 1 and tkey(next(iter(c_))) != tkey(v["tm"]):
                        v["from"] = next(iter(c_))
        except Exception as e:
            print(f"   傳聞人選原隊（依 ID）查詢失敗：{type(e).__name__} {str(e)[:100]}")
    # 還是沒有的（已經離隊的自由球員，Players.Team 是空的）⇒ 最後一段效力紀錄（Tenures）的那一隊
    need = sorted({(v.get("p") or v["n"]) for L in rumor.values() for v in L if not v.get("from")})
    if need:
        try:
            rows = []
            for i in range(0, len(need), 40):
                rows += cargo({"tables": "Tenures", "fields": "Tenures.Player=p,Tenures.Team=tm,Tenures.DateJoin=dj",
                               "where": "Tenures.Player IN " + _in(need[i:i + 40]), "order_by": "Tenures.DateJoin", "limit": "5000", "format": "json"})
            last_tm = {}
            for x in rows:
                if x.get("tm") and x.get("dj"):
                    last_tm[key(x["p"])] = x["tm"]   # 依加入日排序，後面的蓋前面的
            for L in rumor.values():
                for v in L:
                    t_ = last_tm.get(key(v.get("p") or v["n"]))
                    if not v.get("from") and t_ and tkey(t_) != tkey(v["tm"]):
                        v["from"] = t_
        except Exception as e:
            print(f"   傳聞人選原隊（依效力紀錄）查詢失敗：{type(e).__name__} {str(e)[:100]}")
    # 傳出要去別隊的人（使用者 2026-11-19「如果合約還在但有傳出可能去別隊 上綠色」）：名字 → 最新一則傳聞（目的地＝傳聞的隊）
    rum_names = {key(v["n"]) for L in rumor.values() for v in L} | {key(v["p"]) for L in rumor.values() for v in L if v.get("p")}
    rum_out = {}
    for v in sorted((v for L in rumor.values() for v in L if v["st"] == "rumor"), key=lambda v: v["d"], reverse=True):   # 新的在前，最多三隊
        for k_ in {key(v["n"])} | ({key(v["p"])} if v.get("p") else set()):
            rum_out.setdefault(k_, []).append(v)
    out = []
    for tm in teams:
        c = cur.get(tm, {})
        prevkeys = {key(p) for v in prev.get(tm, {}).values() for p in v}
        rows, gone = {}, {}
        for rr in LANES + ["COACH"]:
            cell = []
            ppl = c.get(rr, [])
            hk = {key(p[1]) for p in ppl}
            ppl = ppl + [p for p in expired.get(tm, {}).get(rr, []) if key(p[1]) not in hk]   # 合約到期未宣布離隊的也列（藍字）
            srole = {}
            if rr == "COACH":   # 只列主教練／教練／戰略教練／路線教練／分析師（使用者 2026-11-19），依序排
                keep = []
                for p in ppl:
                    s = p[3] if len(p) > 3 else staff_code(news_role.get(key(p[1])) or joined.get((key(p[1]), tm), ("", ""))[1], p[2])   # Tenures 來的已帶職稱代碼
                    if s:
                        srole[p[1]] = s; keep.append(p)
                ppl = sorted(keep, key=lambda p: STAFF_ORDER.index(srole[p[1]]))
                # 主教練已經有現任的（HLE Mowgli 升主教練）⇒ 合約到期的舊主教練（Homme）當作離任，移到上一位
                exk = {key(p[1]) for p in expired.get(tm, {}).get("COACH", [])}
                if any(srole[p[1]] == "HC" and key(p[1]) not in exk for p in ppl):
                    old = [p for p in ppl if srole[p[1]] == "HC" and key(p[1]) in exk]
                    gone.setdefault("COACH", []).extend(p[1] for p in old)
                    ppl = [p for p in ppl if p not in old]
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
                # 升職（使用者 2026-11-20「教練或分析師轉成主教練的標紫色叫做升職，從二隊三隊上到一隊的也是」）：
                #   本休賽期 wiki 記「X to Head Coach」的人；或原隊是同組織的二隊／青訓（隊名第一個字相同＋Academy／Challengers／Youth…）
                if k in promo_hc or (e.get("from") and _sister(e["from"], tm)):
                    e["pm"] = promo_hc.get(k) or 1   # 字串＝職稱異動；1＝從二隊／青訓上調（原隊在 from）
                # 今年沒替這隊上過場的選手不列（使用者 2026-11-19「G2 Sola 是簽來當 co-stream 實況主的…沒上過場的都不應該出現在名單」）；新人不套
                #     本休賽期有官方續約消息的不套（NS Calix 今年沒上場但續約到 2028，是明年的人）
                if rr != "COACH" and "new" not in e and "rs" not in e and played is not None and (k, tkey(tm)) not in played and (key(pid), tkey(tm)) not in played:
                    continue
                ros = []
                for ro in rum_out.get(k) or rum_out.get(key(pid)) or []:
                    if tkey(ro["tm"]) != tkey(tm) and ro["d"][:10] >= since:
                        o = {"to": ro["tm"], "d": ro["d"][:10], "tip": ro["tip"]}
                        if ro.get("src"):
                            o["src"] = ro["src"]
                        if ro.get("u"):
                            o["u"] = ro["u"]
                        ros.append(o)
                if ros:
                    e["ro"] = ros[0]   # 前端：合約還在才上綠色；ro＝最新一則
                    if len(ros) > 1:
                        e["ros"] = ros[:3]   # 最多三支傳聞隊伍（新的在前）
                cell.append(e)
            have = {key(e["p"]) for e in cell} | {key(e["n"]) for e in cell}
            for rmr in rumor.get((tkey(tm), rr), []):
                if key(rmr["n"]) in have:
                    continue
                ot = team_of.get(key(rmr["n"]))
                if ot and ot != tm and joined.get((key(rmr["n"]), ot), ("", ""))[0] >= rmr["d"][:10]:
                    continue   # 傳聞之後他已官宣去別隊
                e = {"n": rmr["n"], "p": rmr.get("p") or "", "tip": rmr["tip"], "d": rmr["d"][:10]}
                if rmr.get("src"):
                    e["src"] = rmr["src"]
                if rmr.get("u"):
                    e["u"] = rmr["u"]   # 來源網址（小框的來源名稱點了開原文；使用者 2026-11-20「Sheep 的來源就寫 SE 然後超連結」）
                if rmr["st"] == "rumor":
                    e["r"] = 1
                if rmr.get("from"):
                    e["from"] = rmr["from"]
                cell.append(e)
            # 使用者 2026-11-19「如果該路線有新加入的選手，舊的就當作離隊」：選手路線有官方新人（wiki 新加入或 Sheep 官方消息）
            # ⇒ 同格原有的人移到「上一位」（傳聞不算新人；教練欄不套）
            moved = []
            if rr != "COACH" and any(("new" in e or ("tip" in e and "r" not in e)) for e in cell):
                # 使用者 2026-11-20「如果有新加入 那麼同路線的傳聞都清掉」「只留下二隊三隊的晉升傳聞以及本來就在陣容的人」：
                #   官方新人已經定了 ⇒ 這一路其他「外面的人要來」的傳聞不再列（DK 上路 Doran 官宣後，其餘人選拿掉）；
                #   留下：同組織二隊／青訓要升上來的傳聞（Jaehyuk）、本來就在陣容且合約還在的人（合約到期／查不到合約的照舊移到上一位）
                def _keep(e):
                    if "new" in e or ("tip" in e and "r" not in e) or "rs" in e or "pm" in e:
                        return True
                    if "r" in e:
                        return bool(e.get("from") and _sister(e["from"], tm))
                    return bool(e.get("c") and e["c"] >= today)
                moved = [e["p"] or e["n"] for e in cell if "tip" not in e and not _keep(e)]
                cell = [e for e in cell if _keep(e)]
            # 同一路有新加入或續約的人 ⇒ 合約到期的人不再顯示，移上一位（使用者 2026-11-20「例如 BFX 的中路」）
            #   2026-11-20 再加：有「傳聞的人要進來」也一樣（使用者「如果該隊路線原選手離隊或合約到期 同時又有傳聞的選手進來 那就不顯示」：
            #   JDG 打野 JunJia／xiaofang 合約到期＋Kanavi／Tarzan 傳聞 ⇒ 格子只留傳聞的兩位，原本的移到上一位）
            if rr != "COACH" and any(("new" in e or "rs" in e or "tip" in e) for e in cell):
                old_ = [e for e in cell if "new" not in e and "rs" not in e and "tip" not in e and (not e.get("c") or e["c"] < today)]   # 合約無紀錄也算到期（使用者 2026-11-20）
                if old_:
                    moved += [e["p"] or e["n"] for e in old_]
                    cell = [e for e in cell if e not in old_]
            # 綠字（合約還在、傳出要去別隊）的人：同一路還有別人的傳聞或新加入 ⇒ 視為離隊，格子不顯示、移到上一位，
            #   並列進該聯賽的自由人（仍是綠字）（使用者 2026-11-20「有綠字時 同路線如果還有別人傳聞或新加入 綠字的就不顯示 默認離隊 但還是綠字 並且這種綠字的人要擺到FA」）
            if rr != "COACH":
                grn = [e for e in cell if e.get("ro") and not any(k_ in e for k_ in ("new", "rs", "pm", "tip", "r", "gone"))]
                if grn and any(("new" in e or "tip" in e) for e in cell if e not in grn):
                    for e in grn:
                        green_out.add((key(e["p"] or e["n"]), tm))
                    moved += [e["p"] or e["n"] for e in grn]
                    cell = [e for e in cell if e not in grn]
            if moved:
                gone.setdefault(rr, []).extend(moved)
            # 宣布離隊、這個位置還沒有新簽約也沒有傳聞 ⇒ 留在格子、標 gone（藍字刪除線）；教練分 主教練／後勤 兩組各自看
            have = {key(e["p"]) for e in cell} | {key(e["n"]) for e in cell}
            grp = (lambda c: "HC" if c == "HC" else "S") if rr == "COACH" else (lambda c: "")
            filled = {grp(e.get("sr", "")) for e in cell if "new" in e or "tip" in e or "rs" in e}   # 有新加入／續約／傳聞就不列（BFX 中路 Daystar）
            if rr == "COACH" and any(e.get("sr") == "HC" for e in cell):
                filled.add("HC")   # 主教練只有一位：已有現任（HLE Mowgli 升任）就不再列刪除線的舊主教練（Homme）
            for p in annd.get(tm, {}).get(rr, []):
                pid, pg = p[0], p[1]
                k = key(pg)
                code = p[3] if len(p) > 3 else ""
                if k in have or grp(code) in filled:
                    continue
                if rr != "COACH" and played is not None and (k, tkey(tm)) not in played and (key(pid), tkey(tm)) not in played:
                    continue
                e = {"n": pid, "p": pg, "gone": 1}
                if code:
                    e["sr"] = code
                if con.get((k, tm)):
                    e["c"] = con[(k, tm)]
                cell.append(e); have.add(k)
            # 選手位置整格空（顯示 –）、原本的人只是離隊、沒有他的傳聞也沒去別隊 ⇒ 一樣留格子藍字刪除線
            #   （使用者 2026-11-20「本來的選手只是離隊 還沒有任何傳聞與加入別隊的消息 那就用藍字+刪除線」；含轉會期前就走的，如 TT 9/30）
            if rr != "COACH" and not cell:
                stay = {key(pg) for v in c.values() for _, pg, *_ in v} | allcur.get(tm, set())
                for pg in prev.get(tm, {}).get(rr, []):
                    k = key(pg)
                    pid = re.sub(r"\s*\([^()]*\)$", "", pg)
                    if k in stay or k in have or key(pid) in rum_names or k in rum_names:
                        continue
                    if (team_of.get(k) and team_of[k] != tm) or any(k in v for t2, v in allcur.items() if t2 != tm) \
                            or any(kk == k and t2 != tm and jd_[0] >= since for (kk, t2), jd_ in joined.items()):
                        continue   # 已經去別隊
                    e = {"n": pid, "p": pg, "gone": 1}
                    if con.get((k, tm)):
                        e["c"] = con[(k, tm)]
                    cell.append(e); have.add(k)
            if rr == "COACH":
                cell.sort(key=lambda e: STAFF_ORDER.index(e["sr"]) if e.get("sr") in STAFF_ORDER else 9)
            if cell:
                rows[rr] = cell
        pv = {}
        for rr in LANES + ["COACH"]:
            # 還在隊上的人不是「上一位」（使用者 2026-11-19「Ratis 沒說離開 GZ，他是教練」：職稱不在五種裡沒顯示，不代表離隊）
            gk = {key(g) for g in gone.get(rr, [])}
            here = {key(e["p"]) for e in rows.get(rr, [])} | {key(pg) for v in c.values() for _, pg, *_ in v if key(pg) not in gk} \
                | (allcur.get(tm, set()) - gk)
            seen, L = set(), []
            for p in gone.get(rr, []) + prev.get(tm, {}).get(rr, []):   # 被新人擠掉的排前面
                if key(p) not in here and key(p) not in seen:
                    seen.add(key(p)); L.append(p)
            pv[rr] = L
        # 上一位教練也帶職稱（使用者 2026-11-19「教練分成兩欄 主教練 跟後勤」⇒ 前端要知道放哪一欄）
        gk = {key(g) for g in gone.get("COACH", [])}
        psr = {p: ("HC" if key(p) in gk else (staff_code(joined.get((key(p), tm), ("", ""))[1], prole.get((tm, p), "")) or "C"))
               for p in pv.get("COACH", [])}
        pv = {rr: v for rr, v in pv.items() if v}
        out.append({"tm": tm, "nm": disp[tm], "lg": lg_of[tm], "r": rows, "prev": pv,
                    "_still": sorted({key(g) for v in gone.values() for g in v} - {key(p_[1]) for v_ in annd.get(tm, {}).values() for p_ in v_}), "_psr": psr,
                    "_pc": {p_: con[(key(p_), tm)] for v_ in pv.values() for p_ in v_ if con.get((key(p_), tm))}})   # 已宣布離隊的不算還在隊上；_pc＝上一位的合約到期日   # 被新人擠掉、其實還在隊上的（add_tenure 用完拿掉）
    # 已退役的人不留在格子裡（使用者 2026-11-20「Evi 已經退役 那格應該改成 -…有退役的都改成這樣」）：
    #   格子裡沒有新身分（新加入／續約／傳聞／升職）的人＋上一位，向 Players.IsRetired 查；退役的從格子拿掉、放進上一位並標 ret
    global RETIRED
    RETIRED = {}
    try:
        cand = sorted({e["p"] for x in out for L in x["r"].values() for e in L if e.get("p") and not any(k_ in e for k_ in ("new", "rs", "tip", "r", "pm"))}
                      | {p for x in out for v in x["prev"].values() for p in v})
        rset = {}
        for i in range(0, len(cand), 40):
            for y in cargo({"tables": "Players", "fields": "Players.OverviewPage=pg,Players.ID=id,Players.Role=ro",
                            "where": "Players.OverviewPage IN " + _in(cand[i:i + 40]) + " AND Players.IsRetired=1", "limit": "500", "format": "json"}):
                rset[key(y["pg"])] = (y["pg"], str(y.get("id") or y["pg"]), ROLE_OF.get((y.get("ro") or "").split(",")[0].strip()) or "")
        for x in out:
            rk_ = set()
            for rr in list(x["r"]):
                keep_ = []
                for e in x["r"][rr]:
                    if key(e.get("p") or "") in rset and not any(k_ in e for k_ in ("new", "rs", "tip", "r", "pm")):
                        if e["p"] not in x["prev"].get(rr, []):
                            x["prev"].setdefault(rr, []).insert(0, e["p"])
                        rk_.add(key(e["p"]))
                    else:
                        keep_.append(e)
                if keep_:
                    x["r"][rr] = keep_
                else:
                    x["r"].pop(rr)
            for rr, v in x["prev"].items():
                for p in v:
                    if key(p) in rset:
                        rk_.add(key(p))
                        if rr != "COACH":
                            RETIRED.setdefault(key(p), rset[key(p)] + (x["nm"], x["lg"]))
            x["_ret"] = sorted(rk_)
            x["_still"] = [k_ for k_ in x.get("_still", []) if k_ not in rk_]
    except Exception as e:
        print(f"   退役查詢失敗：{type(e).__name__} {str(e)[:100]}")
    # ── 每個聯賽一列「FA」（自由球員；使用者 2026-11-20「每個聯賽用一個隊伍格當作 FA 自由人的意思 把去年一級聯賽有參賽過 但目前合約到期或離隊的都列入」）──
    #   來源＝各隊格子裡「已宣布離隊／合約到期（含查不到合約）」的人＋上一位；排除：今年沒替那隊上過場、已退役、已經有新東家
    #   （在別隊是新加入／續約／升職／合約還在，或 wiki 選手頁現在掛在別隊——含次級聯賽）。只列五路選手，教練不列。
    #   每筆帶 from＝原隊、c＝合約到期日、gone＝已宣布離隊、ro／ros＝傳聞去向（跟格子裡的人同一套）
    fa_rows = []
    try:
        settled = set()
        for x in out:
            for L in x["r"].values():
                for e in L:
                    k_ = key(e.get("p") or e["n"])
                    if e.get("gone") or e.get("r"):
                        continue
                    if e.get("new") or e.get("rs") or e.get("pm") or e.get("tip") or (e.get("c") and e["c"] >= today):
                        settled.add(k_); settled.add(key(e["n"]))
        cand, seen_ = [], set()
        left_rc = set()   # 這個休賽期前後 wiki 記了「離隊」的（人, 隊）
        try:
            for i in range(0, len(teams), 20):
                for y in cargo({"tables": "RosterChanges", "fields": "Player=p,Team=tm", "limit": "5000", "format": "json",
                                "where": "RosterChanges.Team IN " + _in(teams[i:i + 20]) + f' AND RosterChanges.Direction="Leave" AND RosterChanges.Date_Sort>="{year}-08-01"'}):
                    left_rc.add((key(y["p"]), y["tm"]))
        except Exception as e:
            print(f"   離隊紀錄查詢失敗（自由人的教練不列上一位）：{type(e).__name__} {str(e)[:100]}")
        for x in out:
            for rr in LANES:
                for e in x["r"].get(rr, []):
                    if e.get("r") or e.get("new") or e.get("rs") or e.get("pm") or e.get("tip"):
                        continue
                    if e.get("gone") or not e.get("c") or e["c"] < today:
                        cand.append((x, rr, e.get("p") or e["n"], e["n"], e.get("c") or "", 1 if e.get("gone") else 0))
                for p in x["prev"].get(rr, []):
                    cand.append((x, rr, p, re.sub(r"\s*\([^()]*\)$", "", p), con.get((key(p), x["tm"]), ""), 0 if (key(p), x["tm"]) in green_out else 1))
            # 教練那格（使用者 2026-11-20「FA 多一個主教練」→「主教練改成 教練與分析師也列入」）：已宣布離隊的主教練、教練、分析師都列
            #   （只列「已宣布離隊」的：教練大多查不到合約紀錄，「無紀錄算到期」會把還在任的也列進來）；教練不看出賽紀錄。第七格＝職稱代碼
            for e in x["r"].get("COACH", []):
                if e.get("r") or e.get("new") or e.get("rs") or e.get("pm") or e.get("tip") or not e.get("gone"):
                    continue
                cand.append((x, "COACH", e.get("p") or e["n"], e["n"], e.get("c") or "", 1, e.get("sr") or "C"))
            for p in x["prev"].get("COACH", []):
                if (key(p), x["tm"]) not in left_rc:
                    continue   # 上一位教練要 wiki 真的記了離隊才算（UP 的 ScreamM 只是不在最新名單上、沒有離隊紀錄，也沒有選手頁）
                cand.append((x, "COACH", p, re.sub(r"\s*\([^()]*\)$", "", p), con.get((key(p), x["tm"]), ""), 1, (x.get("_psr") or {}).get(p) or "C"))
        # 掛名在隊上但休假中（inactive）的主教練也算自由人（使用者 2026-11-20「Homme kkOma 都算」：kkOma 在 T1 是 inactive、合約 2026-11-16 到期，
        #   教練欄本來就不列休假的人，所以要另外查）
        try:
            by_tm_ = {x["tm"]: x for x in out}
            for i in range(0, len(teams), 20):
                for y in cargo({"tables": "Tenures=T,RosterChanges=RC", "join_on": "T.RosterChangeIdJoin=RC.RosterChangeId",
                                "fields": "T.Player=p,T.Team=tm,RC.Role=ro,RC.Status=st",
                                "where": "T.IsCurrent=1 AND T.Team IN " + _in(teams[i:i + 20]) + ' AND RC.Status="inactive" AND RC.Role LIKE "%Head Coach%"',
                                "limit": "500", "format": "json"}):
                    x = by_tm_.get(y.get("tm"))
                    if x and y.get("p"):
                        cand.append((x, "COACH", y["p"], re.sub(r"\s*\([^()]*\)$", "", y["p"]), con.get((key(y["p"]), x["tm"]), ""), 0, "HC"))
        except Exception as e:
            print(f"   休假主教練查詢失敗：{type(e).__name__} {str(e)[:100]}")
        pages_ = sorted({c_[2] for c_ in cand})
        now_tm, retd_ = {}, set()
        for i in range(0, len(pages_), 40):
            for y in cargo({"tables": "Players", "fields": "Players.OverviewPage=pg,Players.Team=tm,Players.IsRetired=ret",
                            "where": "Players.OverviewPage IN " + _in(pages_[i:i + 40]), "limit": "500", "format": "json"}):
                now_tm[key(y["pg"])] = y.get("tm") or ""
                if str(y.get("ret")) == "1":
                    retd_.add(key(y["pg"]))
        by_lg = {}
        for x, rr, pg, nm_, c_, gone_, *sr_ in cand:
            k_ = key(pg)
            if k_ in seen_ or k_ in settled or key(nm_) in settled or k_ in retd_:
                continue
            if rr != "COACH" and played is not None and (k_, tkey(x["tm"])) not in played and (key(nm_), tkey(x["tm"])) not in played:
                continue
            t_now = now_tm.get(k_, "")
            if t_now and tkey(t_now) != tkey(x["tm"]):
                continue   # 選手頁已經掛在別隊（含次級聯賽）
            seen_.add(k_)
            e = {"n": nm_, "p": pg, "fa": 1, "from": x["nm"]}
            if k_ not in now_tm:
                e["nop"] = 1   # wiki 沒有這個人的頁面 ⇒ 前端不做連結
            if rr == "COACH":
                e["sr"] = (sr_[0] if sr_ else "") or "C"
            if c_:
                e["c"] = c_
            if gone_:
                e["gone"] = 1
            ros = []
            for ro in rum_out.get(k_) or rum_out.get(key(nm_)) or []:
                if ro["d"][:10] >= since and tkey(ro["tm"]) != tkey(x["tm"]):   # 傳聞的是「留在原隊」（陣容整理文把他列在原隊）不算去向
                    o = {"to": ro["tm"], "d": ro["d"][:10], "tip": ro["tip"]}
                    if ro.get("src"):
                        o["src"] = ro["src"]
                    if ro.get("u"):
                        o["u"] = ro["u"]
                    ros.append(o)
            if ros:
                e["ro"] = ros[0]
                if len(ros) > 1:
                    e["ros"] = ros[:3]
            by_lg.setdefault(x["lg"], {}).setdefault(rr, []).append(e)
        for lg_, rows_ in by_lg.items():
            for L in rows_.values():
                L.sort(key=lambda e: (e["from"].lower(), e["n"].lower()))
            fa_rows.append({"tm": "FA " + lg_, "nm": "FA", "lg": lg_, "r": rows_, "prev": {}, "fa": 1})
    except Exception as e:
        print(f"   FA 列失敗（不列）：{type(e).__name__} {str(e)[:120]}")
    try:
        add_tenure(cargo, out)
    except Exception as e:   # 查不到效力期間就只列名字
        print(f"   上一位效力期間查詢失敗：{type(e).__name__} {str(e)[:100]}")
        for x in out:
            x.pop("_still", None); psr = x.pop("_psr", {}); x.pop("_pc", None); x.pop("_ret", None)
            if x["prev"].get("COACH"):
                x["prev"]["COACH"] = [{"n": p, "sr": psr.get(p, "C")} for p in x["prev"]["COACH"]]
    try:
        rk = team_rank(cargo, year)
    except Exception as e:   # 名次查不到就退回字母序，不擋整張表
        print(f"   陣容表排序名次失敗（改字母序）：{type(e).__name__} {str(e)[:100]}")
        rk = {}
    for x in out:
        k = rk.get(tkey(x["tm"])) or rk.get(tkey(x["nm"]))
        if k:
            x["rk"] = k[3]
    for n_, o_ in succ.items():
        for x in out:
            if x["tm"] == o_:
                x["was"] = o_; x["tm"] = n_; x["nm"] = disp.get(n_, n_)
    out += fa_rows
    out.sort(key=lambda x: (ORDER.index(x["lg"]) if x["lg"] in ORDER else 9, x.get("fa", 0),
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
    allcur = {}   # 各隊 wiki 現任名單上的所有人（任何職稱／狀態）：「上一位」不可列這些人（GZ Ratis）
    for x in rows:
        if x.get("p") is not None:
            allcur.setdefault(x["tm"], set()).add(key(str(x["p"])))
    return out, allcur


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
        still = set(x.pop("_still", [])); psr = x.pop("_psr", {}); pc = x.pop("_pc", {}); retd = set(x.pop("_ret", []))
        for rr, v in x["prev"].items():
            L = []
            for p in v:
                s, e = stints(sorted(ev.get((key(p), x["tm"]), [])))
                if s and not e:   # 沒記離隊、但之後加入了別隊（Benny 2026-03 進 TT、11-06 進 UP，TT 沒記離隊）⇒ 以加入別隊那天當離隊日
                    later = sorted(d for d, t in joins.get(key(p), []) if t != x["tm"] and d > s)
                    if later:
                        e = later[0]
                d = {"n": p}
                if key(p) in retd:
                    d["ret"] = 1
                if rr == "COACH" and psr.get(p):
                    d["sr"] = psr[p]
                if s:
                    d["s"] = s
                    if e:
                        d["e"] = e
                    elif key(p) not in still:
                        d["e"] = "?"   # 不在隊上、wiki 又沒記離隊 ⇒ 前端顯示「離隊日未記錄」，不寫「今」
                if key(p) in still and not e:   # 有離隊／轉職日期的（BRO Roamer、BFX Edo）不算還在隊上
                    if pc.get(p):
                        d["c"] = pc[p]
                    d["still"] = 1   # 被新人擠到上一位、但其實還沒宣布離隊（WBG Elk）⇒ 前端標「合約到期」不標「離隊」（使用者 2026-11-20）
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
    return (disp or plain or "").strip(), urllib.parse.unquote(pg or "").replace("_", " ")   # 頁名可能是 %28…%29 編碼（Noah 連錯頁，使用者 2026-11-20）


def parse_sheep(sheep):
    """Sheep 推文 → {(隊, 位置): [{n, p, d, tip, from}]}；同一人只留最新一則（照日期由舊到新覆蓋）"""
    # 使用者 2026-11-20「一個選手最多有三個傳聞隊伍 取前三隊」：同一人留最新的三支傳聞隊伍（同一隊只留最新一則）；
    #   官方消息一出就只剩那一則，官方之後又有新傳聞則以新傳聞為主
    best = {}

    def put(n_, it):
        L = best.get(n_) or []
        if it["st"] != "rumor" or any(v["st"] != "rumor" for v in L):
            L = []
        L = [v for v in L if tkey(v["tm"]) != tkey(it["tm"])] + [it]
        best[n_] = L[-3:]

    for x in sorted(sheep, key=lambda x: x["d"]):
        # 只有「官方」續約／留隊才蓋掉之前的轉隊傳聞；續留本身也只是傳聞的不蓋（使用者 2026-11-20「Viper 去 KRX 的消息怎麼不見了」：
        #   BLG 加碼留人是傳聞、去 KRX 也是傳聞，兩邊都要看得到）
        for n_ in (x.get("stay") or []) if (x.get("st") or "rumor") != "rumor" else []:   # 之後的續約／留隊消息蓋掉之前的傳聞（最新動向為主）
            best.pop(n_.lower(), None)
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
                    put(n.lower(), {"tm": tm, "rr": LANES[i], "n": n, "p": pg, "d": x["d"], "tip": tip, "st": st, "src": x.get("src") or "", "u": x.get("url") or ""})
            continue
        if x.get("kind") not in ("join", "both") or len(inn) != 1:
            continue
        # who＝[名字, 頁名, 路線]：PTT 人工判讀的 mv 直接指名（一句話裡有好幾個人時，不能靠「第一個帶路線記號的名字」認人——
        #   使用者 2026-11-20「DK 將從二隊拉上 Jaehyuk 怎麼沒注記到轉會表上」：句子前面先出現帶記號的 Cloud，Jaehyuk 被認成 Cloud）
        if x.get("who"):
            n, pg, lane_ = x["who"]
            put(n.lower(), {"tm": inn[0][1], "rr": lane_, "n": n, "p": pg, "d": x["d"], "tip": tip, "st": st, "src": x.get("src") or "", "u": x.get("url") or "",
                            "from": out[0] if out else ""})
            continue
        m = re.search(r"§(TOP|JNG|MID|BOT|SUP)§" + _NM, zh)
        if not m:
            continue
        n, pg = _name(m, 2)
        put(n.lower(), {"tm": inn[0][1], "rr": m.group(1), "n": n, "p": pg, "d": x["d"], "tip": tip, "st": st, "src": x.get("src") or "", "u": x.get("url") or "",
                        "from": out[0] if out else ""})
    res = {}
    for L in best.values():
        for v in L:
            res.setdefault((tkey(v["tm"]), v["rr"]), []).append(v)
    # 同一隊同一路有好幾則傳聞 ⇒ 只留最新一篇的（使用者 2026-11-20「任何傳聞都以最新的動向為主」：KRX 打野 Kanavi 11/17 → Lucid 11/19）；官方消息不動
    #   2026-11-20 之後改成「一個選手最多三支傳聞隊伍」⇒ 這條停用：不然 Lucid（GEN 11/19 早上、KRX 11/19 下午）在 GEN 那格會被後來的 Sharvel 擠掉，
    #   每個人永遠只剩一隊。同一格會並列好幾位傳聞人選（新的在前）
    for k_, L_ in res.items():
        L_.sort(key=lambda v: v["d"], reverse=True)
    return res
