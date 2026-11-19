# -*- coding: utf-8 -*-
"""「轉會」分頁資料 → transfers.js（window.TRANSFERS）。使用者 2026-11-18：S16 即將結束，記錄 11/1 起的轉會消息。

兩個來源：
  ① Leaguepedia News（https://lol.fandom.com/wiki/Leaguepedia:News/2026/November 那頁的資料本體＝Cargo 表 NewsItems）
     每條＝一句名單異動（加入／離隊／留隊／換職位／合約更新…），附來源連結。句子是固定句型 ⇒ 這裡直接轉成中文。
  ② Sheep Esports 的 X（@Sheep_Esports，[OFFICIAL]／[SOURCES]／[RUMOR] 轉會消息）。
     X 要登入才能看時間軸；能免登入拿到的只有內嵌時間軸（syndication），它給的是「熱門＋近期」混在一起的約 100 則、
     不保證連續 ⇒ 每班抓一次、把新的轉會推文累積進 transfers_sheep_src.json（不進白名單）。
     那個檔也可以手動補（使用者貼推文網址／內容，由 Claude 翻譯後寫進去）：每筆 {id, d, en, zh?, url, manual?}。
輸出：{"at", "from", "wiki":[{d, n, team, st, rg, kind, en, zh, src, srcNm}], "sheep":[{d, id, en, zh, url}]}
Cargo 失敗就沿用舊檔的 wiki；X 失敗就只用累積檔。
跑：python scripts/fetch_transfers.py [起始日 YYYY-MM-DD]（預設 FROM；排程 run_update ⑤h3 每班跑一次）
"""
import datetime, email.utils, html, io, json, os, re, sys, urllib.parse, urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "transfers.js")
SHEEP = os.path.join(ROOT, "transfers_sheep_src.json")
FROM = "2026-11-01"
sys.path.insert(0, HERE)

ROLE = {"Top Laner": "TOP", "Jungler": "JNG", "Mid Laner": "MID", "Bot Laner": "BOT", "Support": "SUP"}
STAFF = {"Head Coach": "總教練", "Assistant Coach": "助理教練", "Coach": "教練", "Strategic Coach": "戰術教練",
         "Positional Coach": "位置教練", "Team Manager": "領隊", "General Manager": "總經理", "Manager": "經理",
         "Data Analyst": "數據分析師", "Analyst": "分析師", "Esports Director": "電競總監", "Owner": "老闆",
         "Chief Executive Officer": "執行長", "Substitute": "替補", "Performance Coach": "體能教練",
         "Psychologist": "心理師", "Content Creator": "內容創作者", "Streamer": "實況主", "Translator": "翻譯",
         "Sporting Director": "運動總監", "Team Coordinator": "隊務", "Director": "總監", "President": "總裁",
         "Trainee": "練習生", "Two-Way": "雙向合約"}
STAFF.update({"Interim Head Coach": "代理總教練", "JV Manager": "二軍經理", "Academy Program Manager": "青訓計畫經理",
              "Assistant Manager": "助理經理", "Player Performance Coach": "選手表現教練", "Head of LoL": "LoL 部門主管",
              "Director of Esports": "電競總監", "Sub": "替補", "Academy Coach": "青訓教練", "Top": "上路", "Jungle": "打野",
              "Mid": "中路", "Bot": "下路", "Support": "輔助", "Owner/Chief Executive Officer": "老闆／執行長"})
_DT = r"(\d{1,2}) (January|February|March|April|May|June|July|August|September|October|November|December) (\d{4})"
_MON = {m: i + 1 for i, m in enumerate("January February March April May June July August September October November December".split())}
VERB = [   # 一句＝「名單 + 動詞片語.」；只有整句對得上才翻，對不上就保留英文原句（不硬翻）
    (r"joins? as (?:a )?substitutes?", "以替補身分加入"), (r"joins? from (?:the )?academy roster", "從二軍上調"),
    (r"joins? from sister team (.+)", r"從姊妹隊 \1 加入"), (r"joins? on loan", "租借加入"), (r"joins?", "加入"),
    (r"leaves? for sister team (.+)", r"轉往姊妹隊 \1"), (r"leaves? for (?:the )?main roster", "上調一軍"), (r"leaves? for (?:the )?academy roster", "下放二軍"), (r"leaves?", "離隊"),
    (r"will remain with the team for (\d{4})", r"\1 年留隊"), (r"will remain with the team", "留隊"),
    (r"changes? positions?", "轉換職位"), (r"moves? to (?:the )?starting roster", "升上先發"),
    (r"moves? to (?:the )?substitutes?", "轉為替補"), (r"retires?", "退役"),
    (r"(?:is|are) allowed to look for opportunities with other teams", "開放轉會（可洽談其他隊伍）"),
    (r"(?:'s?) contracts? (?:is|are) extended through (\d{4})", r"的合約延長到 \1 年"),
    (r"(?:'s?) contracts? (?:is|are) extended", "的合約延長"),
    (r"(?:'s?) contracts? (?:is|are) updated in the GCD, expiring on " + _DT, lambda m: "的合約在 GCD 更新，到期日 %s/%02d/%02d" % (m.group(3), _MON[m.group(2)], int(m.group(1)))),
    (r"(?:is|are) now inactive", "轉為非活躍"), (r"(?:is|are) benched", "下放板凳"),
    (r"will no longer compete in the (.+)", r"不再參加 \1"),
]
WHOLE = [   # 一次性的整句（Leaguepedia 的非固定句型），對得上就整句換
    (r"Organization withdraws from League of Legends", "戰隊退出英雄聯盟"),
    (r"Organization steps away from the (\w+) in (\d{4}), with (.+?) taking over its spot through a partnership", r"戰隊 \2 年退出 \1，席位透過合作由 \3 接手"),
    (r"Organization announces its return to the (\w+) in (\d{4}) through a partnership with (.+?) and (.+)", r"戰隊宣布 \2 年透過與 \3、\4 合作重返 \1"),
    (r"(.+?) receives a provisional suspension from all Riot-affiliated tournaments for potential breaches of the Riot Games Esports Global Code of Conduct while the investigation is ongoing",
     r"\1 疑似違反 Riot 電競全球行為準則，調查期間暫停參加所有 Riot 相關賽事"),
    (r"(.+?) is released from prison on parole and deported to (.+)", r"\1 假釋出獄，被遣返\2"),
]
STAFF["General Manager for League of Legends"] = "LoL 總經理"
STAFF.update({"Strategy Analyst": "戰略分析師", "Director of Culture": "文化總監", "Competitive Development": "競技發展",
              "Head of League of Legends": "LoL 部門主管", "Performance Coordinator": "表現協調員",
              "Head of Coaching Development": "教練發展主管", "Director of Culture and Competitive Development": "文化與競技發展總監"})   # 2026-11-19 分頁審視：殘留英文的職稱
REGION = {"Korea": "韓國", "China": "中國", "EMEA": "歐洲", "North America": "北美", "Brazil": "巴西",
          "Asia Pacific": "亞太", "International": "國際", "Vietnam": "越南", "Latin America": "拉丁美洲",
          "Japan": "日本", "Oceania": "大洋洲", "Turkey": "土耳其", "CIS": "獨國協"}


def clean(s):
    """Leaguepedia 句子 HTML → 純文字；路線圖示換成 §TOP§ 這種記號（前端換成路線標籤）"""
    s = html.unescape(html.unescape(s or ""))
    s = re.sub("⁠[^⁠]*⁠", "", s).replace("'''", "").replace("''", "")   # 隊徽模板 ⁠48px|link=…⁠顯示名 → 顯示名；粗斜體
    s = re.sub(r'<span title="([^"]+)" class="sprite role-sprite"[^>]*>.*?</span>',
               lambda m: "§%s§" % ROLE.get(m.group(1), "") if ROLE.get(m.group(1)) else "", s, flags=re.S)
    s = re.sub(r"<[^>]+>", "", s)
    # wiki 連結 → ‹頁名(URL 編碼)|顯示名›，前端換成可點的 Leaguepedia 連結（使用者 2026-11-19「選手的ID點擊要可以跳轉到他的WIKI」）
    s = re.sub(r"\[\[([^|\]]*)\|?([^\]]*)\]\]", lambda m: "‹%s|%s›" % (urllib.parse.quote(m.group(1).strip().replace(" ", "_"), safe="_"), (m.group(2) or m.group(1)).strip()), s)
    s = re.sub(r"§\s+", "§", re.sub(r"\s+", " ", s)).strip()
    return s


def _staff(m):
    inner = m.group(1)
    if inner in STAFF:
        return "（" + STAFF[inner] + "）"
    parts = re.split(r"(\s+to\s+|/|,\s*)", inner)
    out = [(" → " if p.strip() == "to" else "／") if re.fullmatch(r"\s+to\s+|/|,\s*", p) else STAFF.get(p.strip(), p.strip()) for p in parts]
    return "（" + "".join(out) + "）"


def _prefix(body, n):
    """body 去掉 ‹頁|名› 記號後的前 n 個字，對回帶記號的原文（名單段保留連結）"""
    out, k = "", 0
    for i, s in enumerate(re.split(r"(‹[^|›]+\|[^›]+›)", body)):
        plain = re.sub(r"‹[^|›]+\|([^›]+)›", r"\1", s)
        if k + len(plain) <= n:
            out += s; k += len(plain)
        else:
            out += plain[:n - k]; break
    return out


def _one(sen):
    """一句英文 → 中文；對不上句型回傳原句。句型比對用去掉連結記號的純文字（動詞段的 GCD／姊妹隊連結不擋翻譯），
    名單段再對回帶記號的原文（選手名可點）"""
    body0 = sen.rstrip(".").strip()
    body = re.sub(r"‹[^|›]+\|([^›]+)›", r"\1", body0)
    for a, b in WHOLE:
        if re.fullmatch(a, body):
            return re.sub(a, b, body).replace("Hong Kong", "香港") + "。"
    for pat, rep in VERB:
        m = re.fullmatch(r"(.+?)\s*(" + pat + r")", body)
        if not m:
            continue
        names = re.sub(r"\s*\(([^()]*)\)", _staff, _prefix(body0, m.end(1)))
        names = re.sub(r",?\s+and\s+|,\s*", "、", names).strip()
        verb = re.sub(pat, rep, m.group(2))
        return re.sub(r"^Organization$", "戰隊", names) + " " + verb.rstrip(".") + "。"
    return sen


def to_zh(s):
    sens = re.split(r"(?<=\.)\s+(?=§|‹|\w)", s)
    return " ".join(_one(x) for x in sens)


def kind_of(raw, en):
    j = "rosterchange-join" in raw or re.search(r"\bjoins?\b", en)
    l = "rosterchange-leave" in raw or re.search(r"\bleaves?\b|\bretires?\b", en)
    return "both" if j and l else "join" if j else "leave" if l else "other"


def src_of(src):
    f = (src or "").split(":::")[0].split(";;;")
    return (f[0] if f and f[0].startswith("http") else ""), (f[1] if len(f) > 1 else "")


def fetch_wiki(start):
    import build_predict_live as B   # 共用 Cargo 的 cookie 與節流
    r = B.cargo({"tables": "NewsItems",
                 "fields": "NewsItems.Sentence=s,NewsItems.Source=src,NewsItems.Region=rg,NewsItems.N_LineInDate=n,"
                           "NewsItems.Date_Sort=ds,NewsItems.Subject=sub,NewsItems.SubjectType=st",
                 "where": f'NewsItems.Date_Sort>="{start}"', "order_by": "NewsItems.Date_Sort,NewsItems.N_LineInDate",
                 "limit": "5000", "format": "json"})
    out = []
    for x in r:
        if x.get("st") == "Tournament":   # 版本上線、賽事公告不是轉會
            continue
        en = clean(x.get("s"))
        if not en:
            continue
        url, nm = src_of(x.get("src"))
        out.append({"d": str(x.get("ds") or "")[:10], "n": int(x.get("n") or 0), "team": x.get("sub") or "",
                    "rg": REGION.get(x.get("rg"), x.get("rg") or ""), "kind": kind_of(html.unescape(x.get("s") or ""), en),
                    "en": en, "zh": to_zh(en), "src": url, "srcNm": nm})
    return out


TAG = re.compile(r"\[(OFFICIAL|SOURCES|RUMOU?R|BREAKING|REPORT)\]", re.I)
MOVE = re.compile(r"\b(join|sign|re-sign|leave|part(?:s|ed)? ways|contract|roster|free agent|extend|transfer|bench|retire|verbal agreement|set to)\w*", re.I)


SHEEP_WAIT_MAX = 180  # 429 時最多等幾秒（端點是 15 分鐘滾動窗、額度 30 次，跟別人共用；重置點隨機落在窗裡）


def _sheep_get(req, sleep=None):
    """內嵌時間軸常回 429（x-rate-limit-remaining 0），但它是滾動窗不是封鎖：重置一過就 200
    （2026-11-19 10:20 實測：10:18 429、重置 10:20:04、10:20:08 再問 200 且剩 11 次）。
    重置點離現在 ≤ SHEEP_WAIT_MAX 秒就等過去再問一次；更遠就照舊拋錯、退回累積檔（不拖慢整條管線）。"""
    import time, urllib.error
    sleep = sleep or time.sleep
    try:
        return urllib.request.urlopen(req, timeout=60).read()
    except urllib.error.HTTPError as e:
        if e.code != 429:
            raise
        try:
            wait = int(e.headers.get("x-rate-limit-reset", "0")) - time.time() + 3
        except ValueError:
            raise e
        if not 0 < wait <= SHEEP_WAIT_MAX:
            print(f"Sheep Esports 429，額度重置要等 {wait:.0f}s（> {SHEEP_WAIT_MAX}s）不等")
            raise
        print(f"Sheep Esports 429，等 {wait:.0f}s 到額度重置再問一次")
        sleep(wait)
        return urllib.request.urlopen(req, timeout=60).read()


def fetch_sheep(start):
    """內嵌時間軸（免登入）→ 轉會推文；只取 start 之後、帶 [OFFICIAL]/[SOURCES] 標籤或含轉會字眼的"""
    req = urllib.request.Request("https://syndication.twitter.com/srv/timeline-profile/screen-name/Sheep_Esports",
                                 headers={"User-Agent": "Mozilla/5.0"})
    s = _sheep_get(req).decode("utf-8", "replace")
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', s, re.S)
    ents = json.loads(m.group(1))["props"]["pageProps"]["timeline"]["entries"]
    out = []
    for e in ents:
        t = (e.get("content") or {}).get("tweet") or {}
        if not t.get("id_str"):
            continue
        dt = email.utils.parsedate_to_datetime(t["created_at"]).astimezone(datetime.timezone(datetime.timedelta(hours=8)))
        txt = t.get("full_text") or t.get("text") or ""
        for u in (t.get("entities") or {}).get("urls") or []:
            txt = txt.replace(u.get("url", ""), u.get("expanded_url", ""))
        txt = re.sub(r"\s*https://t\.co/\w+\s*$", "", txt).strip()
        if dt.strftime("%Y-%m-%d") < start or not MOVE.search(txt):  # 只看轉會字眼；光有 [OFFICIAL] 標籤會收進 MVP／賽程新聞
            continue
        out.append({"id": t["id_str"], "d": dt.strftime("%Y-%m-%d %H:%M"), "en": txt,
                    "url": f"https://x.com/Sheep_Esports/status/{t['id_str']}"})
    return out


PL_STOP = {"will", "set", "join", "hope", "rich", "free", "star", "back", "more", "team", "head", "coach", "season",
           "world", "worlds", "official", "sources", "breaking", "the", "and", "for", "with", "from", "new", "top", "mid", "bot"}
PL_RE = re.compile(r"‹([^|›]+)\|([^›]+)›")


def link_sheep(wiki, sheep):
    """輸出層：Sheep 推文裡出現 wiki 句子連過的名字（選手／教練）→ 套同一個 ‹頁名|顯示名› 記號。
    只認 wiki 連過的名字（不猜），大小寫一致＋前後不是英數字；網址裡的不動；常見英文字跳過。"""
    pg = {}
    for x in wiki:   # 只收「人」：前面有路線記號 §XX§，或後面接職稱括號
        for m in re.finditer(r"(§[A-Z]+§)?‹([^|›]+)\|([^›]+)›(\s*\()?", x.get("en") or ""):
            p, d = m.group(2), m.group(3)
            if (m.group(1) or m.group(4)) and len(d) >= 3 and d.lower() not in PL_STOP and not re.search(r"[‹›|]", d):
                pg.setdefault(d, {}).setdefault(p, set()).add(x.get("rg") or "")
    if not pg:
        return

    def page(d, rgs):   # 同名多頁（Zeus 有兩個）⇒ 用這則推文標的賽區挑；挑不出唯一就不連
        c = pg[d]
        if len(c) == 1:
            return next(iter(c))
        c = [p for p, r in c.items() if r & rgs]
        return c[0] if len(c) == 1 else None
    teams = {x.get("team") for x in wiki} | {t[1] for x in sheep for t in x.get("tags") or []}
    teams = sorted((t for t in teams if t and " " in t), key=len, reverse=True)   # 多字隊名整段保護（Hanwha Life Esports 的 Life）
    prot = re.compile(r"(https?://\S+" + "".join("|" + re.escape(t) for t in teams) + ")")
    rx = re.compile(r"(?<![A-Za-z0-9_/.@#'-])(" + "|".join(sorted(map(re.escape, pg), key=len, reverse=True)) + r")(?![A-Za-z0-9_'-])")
    for x in sheep:
        rgs = {t[0] for t in x.get("tags") or []}

        def rep(m):
            p = page(m.group(1), rgs)
            return "‹%s|%s›" % (p, m.group(1)) if p else m.group(1)
        for k in ("en", "zh"):
            if x.get(k):
                parts = prot.split(x[k])
                x[k] = "".join(s if i % 2 else rx.sub(rep, s) for i, s in enumerate(parts))
    lane_sheep(sheep, prot)


LANE_ZH = {"上路": "TOP", "打野": "JNG", "中路": "MID", "下路": "BOT", "AD Carry": "BOT", "ADC": "BOT", "輔助": "SUP"}
LANE_EN = {"toplaner": "TOP", "top laner": "TOP", "jungler": "JNG", "midlaner": "MID", "mid laner": "MID",
           "botlaner": "BOT", "bot laner": "BOT", "ad carry": "BOT", "adc": "BOT", "support": "SUP"}
_NAME = r"(‹[^|›]+\|[^›]+›|[A-Z0-9][A-Za-z0-9_.'-]*|[a-z][a-z0-9]*[A-Z0-9][A-Za-z0-9_.'-]*)"
_NAMEN = _NAME.replace("(", "(?:", 1)
_EN_STOP = {"For", "The", "In", "As", "At", "And", "To", "Of", "On", "With", "From", "Is", "Was", "Will", "LCK", "LPL", "LEC", "LCS", "CBLOL", "LCP",
            "Former", "Current", "New", "Previous", "This", "That", "He", "She", "They", "His", "Her", "Their", "Both", "All"}


def lane_sheep(sheep, prot=None, year=None):
    """Sheep 推文的「輔助 Cryogen」「support Cryogen」→ §SUP§Cryogen（跟 wiki 句子一樣顯示路線圖示；使用者 2026-11-19）。
    只在路線字後面緊接選手名時換（「以先發打野加入」「AD Carry 未定」不動）；名字＝連結記號或大寫開頭的英數字，排除介系詞與聯賽名"""
    rz = re.compile(r"(?<![A-Za-z])(" + "|".join(map(re.escape, sorted(LANE_ZH, key=len, reverse=True))) + r")\s*" + _NAME)
    re_ = re.compile(r"(?<![A-Za-z])((?i:" + "|".join(map(re.escape, sorted(LANE_EN, key=len, reverse=True))) + r"))\s+" + _NAME)   # 只有路線字不分大小寫，名字要大寫開頭

    def fz(m):
        return m.group(0) if m.group(2) in _EN_STOP or m.group(2).isdigit() else "§%s§%s" % (LANE_ZH[m.group(1)], m.group(2))

    def fe(m):
        return m.group(0) if m.group(2) in _EN_STOP or m.group(2).isdigit() else "§%s§%s" % (LANE_EN[m.group(1).lower()], m.group(2))
    td = datetime.date.today()
    pos = player_pos(year or (td.year if td.month > 6 else td.year - 1))
    RG_LG = {"韓國": "LCK", "中國": "LPL", "歐洲": "LEC", "北美": "LCS", "巴西": "CBLOL", "亞太": "LCP", "越南": "LCP", "日本": "LCP"}

    def lane_of(name, lgs):   # 同名多人 ⇒ 用這則推文標的賽區挑；挑不出唯一就不標
        c = pos.get(name.lower())
        if not c:
            return None
        if len({p for p in c.values()}) == 1:
            return next(iter(c.values()))
        c2 = {p for lg, p in c.items() if lg in lgs}
        return next(iter(c2)) if len(c2) == 1 else None
    # 教練：「總教練 Daeny」「Head Coach Daeny」→ 名字前補 §COACH§（職稱字留著）；wiki 標過教練、又不是當季選手的名字也補
    cz = re.compile(r"((?:總|助理|戰術|位置|青訓)?教練)\s*" + _NAME)
    ce = re.compile(r"((?:(?:Head|Assistant|Strategic|Positional|Academy)\s+)?Coach)\s+" + _NAME)
    spaced = sorted((n for n in pos if " " in n), key=len, reverse=True)
    for x in sheep:
        lgs = {RG_LG.get(t[0]) for t in x.get("tags") or []}
        for k, rx, f in (("zh", rz, fz), ("en", re_, fe)):
            if x.get(k):
                parts = re.split(r"(https?://\S+)", x[k])
                x[k] = "".join(s if i % 2 else rx.sub(f, s) for i, s in enumerate(parts))
                cr = cz if k == "zh" else ce
                x[k] = cr.sub(lambda m: m.group(0) if m.group(2) in _EN_STOP or m.group(2).isdigit() else "%s §COACH§%s" % (m.group(1), m.group(2)), x[k])
                x[k] = re.sub(r"\s+§COACH§", " §COACH§", x[k])
                for nm in spaced:   # 名字有空格的（Naak Nako）
                    m = re.search(r"(?<![A-Za-z0-9_§|])(" + re.escape(nm) + r")(?![A-Za-z0-9_])", x[k], re.I)
                    if m and not x[k][:m.start()].endswith("§"):
                        ln = lane_of(nm, lgs)
                        if ln:
                            x[k] = x[k][:m.start()] + "§%s§" % ln + x[k][m.start():]
                # 角色寫在名字後面（「DuDu 與 DNS 續約…這位上路」）或沒寫 ⇒ 查當季比賽資料的位置，第一次出現的名字前面補圖示
                plain = lambda nm: re.sub(r"^‹[^|›]+\|([^›]+)›$", r"\1", nm)
                seen = {plain(n) for n in re.findall(r"§[A-Z]+§" + _NAME, x[k])}

                def fd(m):
                    nm = m.group(1); key = plain(nm)
                    if key in seen or key in _EN_STOP:
                        return nm
                    ln = lane_of(key, lgs)
                    if ln:
                        seen.add(key)
                    return "§%s§%s" % (ln, nm) if ln else nm
                parts = (prot or re.compile(r"(https?://\S+)")).split(x[k])
                parts = [s for i, s in enumerate(parts)] if prot else parts
                out = []
                for i, s in enumerate(parts):
                    if i % 2:   # 網址／隊名（Hanwha Life Esports 的 Life）不動
                        out.append(s); continue
                    for j, u in enumerate(re.split(r"(§[A-Z]+§" + _NAMEN + ")", s)):
                        out.append(u if j % 2 else re.sub(r"(?<![A-Za-z0-9_§])" + _NAME + r"(?![A-Za-z0-9_])", fd, u))
                x[k] = "".join(out)


_POS = {}


def player_pos(year):
    """當季年度資料：選手名（小寫）→ {聯賽: 位置}（participantid 1～5＝上野中下輔；同一聯賽取出場最多的位置）"""
    if year in _POS:
        return _POS[year]
    import collections
    cnt = collections.defaultdict(collections.Counter)
    fn = os.path.join(ROOT, "data", f"data_{year}.js")
    if os.path.exists(fn):
        d = io.open(fn, encoding="utf-8").read()
        R = json.loads(d[d.index("=") + 1:].rstrip().rstrip(";"))["tabs"]["RAW_DATA"]
        h = R[0]; iL, iP, iB, iR = h.index("league"), h.index("participantid"), h.index("blue_playername"), h.index("red_playername")
        for r in R[1:]:
            p = str(r[iP])
            if p in ("1", "2", "3", "4", "5"):
                for n in (r[iB], r[iR]):
                    if n:
                        cnt[(n.lower(), r[iL])][("TOP", "JNG", "MID", "BOT", "SUP")[int(p) - 1]] += 1
    out = {}
    for (n, lg), c in cnt.items():
        out.setdefault(n, {})[lg] = c.most_common(1)[0][0]
    _POS[year] = out
    return out


T1_LEAGUES = ("LoL Champions Korea", "Tencent LoL Pro League", "LoL EMEA Championship",
              "League of Legends Championship Series", "Circuit Brazilian League of Legends", "League of Legends Championship Pacific")
T1_EXTRA = {"OpTic Gaming"}   # 2027 才進一級的（2026 名單沒有）
T1_RG = {"韓國", "中國", "歐洲", "北美", "巴西", "亞太", "越南", "日本"}   # 只標賽區沒標隊（自由球員名單）＝六大聯賽的消息
_t1key = lambda n: re.sub(r"\s*\([^()]*\)\s*$", "", n or "").strip().lower()


def tier1_teams(year):
    """六大聯賽一級例行賽（Primary、非資格賽）當年的參賽隊＋本機年度資料的 LPL（Cargo 的 LPL 名冊缺 WBG／UP）"""
    import build_predict_live as B
    r = B.cargo({"tables": "Tournaments=T,TournamentRosters=TR", "join_on": "T.OverviewPage=TR.OverviewPage",
                 "fields": "T.League=lg,TR.Team=tm", "group_by": "T.League,TR.Team", "limit": "2000", "format": "json",
                 "where": f'T.Year={year} AND T.TournamentLevel="Primary" AND T.IsQualifier=0 AND T.League IN ("' + '","'.join(T1_LEAGUES) + '")'})
    s = {x["tm"] for x in r if x.get("tm")}
    if len(s) < 40:
        raise ValueError(f"一級隊只有 {len(s)} 隊，名冊不完整")
    fn = os.path.join(ROOT, "data", f"data_{year}.js")
    if os.path.exists(fn):
        d = io.open(fn, encoding="utf-8").read()
        R = json.loads(d[d.index("=") + 1:].rstrip().rstrip(";"))["tabs"]["RAW_DATA"]
        h = R[0]; iL, iB, iR = h.index("league"), h.index("blue_teamname"), h.index("red_teamname")
        s |= {n for row in R[1:] if row[iL] == "LPL" for n in (row[iB], row[iR]) if n}
    return sorted(s | T1_EXTRA)


def is_t1(x, keys):
    """這則有牽涉到六大聯賽一級隊（加入、離開到次級都算；使用者 2026-11-19）"""
    if "tags" in x:
        return any((_t1key(t[1]) in keys) if t[1] else (t[0] in T1_RG) for t in x["tags"])
    return _t1key(x.get("team")) in keys


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else FROM
    old = {}
    if os.path.exists(OUT):
        try:
            t = io.open(OUT, encoding="utf-8").read()
            old = json.loads(t[t.index("=") + 1:].rstrip().rstrip(";"))
        except Exception:
            old = {}
    try:
        wiki = fetch_wiki(start)
        print(f"Leaguepedia News：{len(wiki)} 條（{start} 起）")
    except Exception as e:
        wiki = old.get("wiki") or []
        print(f"Leaguepedia 失敗，沿用舊檔 {len(wiki)} 條：{type(e).__name__} {str(e)[:100]}")
    acc = []
    if os.path.exists(SHEEP):
        acc = json.load(io.open(SHEEP, encoding="utf-8"))
    have = {x["id"] for x in acc}
    try:
        new = [x for x in fetch_sheep(start) if x["id"] not in have]
        acc += new
        print(f"Sheep Esports 內嵌時間軸：新增 {len(new)} 則")
    except Exception as e:
        print(f"Sheep Esports 抓取失敗，只用累積檔：{type(e).__name__} {str(e)[:100]}")
    acc.sort(key=lambda x: x["d"], reverse=True)
    io.open(SHEEP, "w", encoding="utf-8").write(json.dumps(acc, ensure_ascii=False, indent=1))
    sheep = [{k: x[k] for k in ("id", "d", "en", "zh", "url", "kind", "tags", "st") if x.get(k)} for x in acc if x["d"][:10] >= start]
    link_sheep(wiki, sheep)   # 連結用全部 wiki 句子當名字來源（過濾前）
    # 只留六大聯賽一級隊相關的（使用者 2026-11-19「不是加入六大聯賽的一級賽事的資訊都不要列出」「從六大聯賽離開到次級也列出」）
    try:
        t1 = tier1_teams(int(start[:4]) if start[5:7] > "06" else int(start[:4]) - 1)
    except Exception as e:
        t1 = old.get("t1") or []
        print(f"一級隊名單失敗，沿用舊檔 {len(t1)} 隊：{type(e).__name__} {str(e)[:100]}")
    if t1:
        keys = {_t1key(n) for n in t1}
        n0, n1 = len(wiki), len(sheep)
        # wiki 一隊一句：一級隊離隊的人，之後「加入次級隊」那句也留（從六大聯賽離開到次級也列出）
        gone = {p for x in wiki if is_t1(x, keys) and x["kind"] in ("leave", "both") for p, _ in PL_RE.findall(x["en"])}
        wiki = [x for x in wiki if is_t1(x, keys) or (x["kind"] in ("join", "both") and any(p in gone for p, _ in PL_RE.findall(x["en"])))]
        sheep = [x for x in sheep if is_t1(x, keys)]
        print(f"六大聯賽一級：wiki {n0}→{len(wiki)}、sheep {n1}→{len(sheep)}（一級隊 {len(t1)}）")
    wiki.sort(key=lambda x: (x["d"], x["n"]), reverse=True)
    data = {"at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "from": start, "t1": t1, "wiki": wiki, "sheep": sheep}
    io.open(OUT, "w", encoding="utf-8").write("window.TRANSFERS=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print(f"transfers.js：wiki {len(wiki)}、sheep {len(sheep)}")


if __name__ == "__main__":
    main()
