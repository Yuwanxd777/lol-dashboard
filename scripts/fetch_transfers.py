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
import datetime, email.utils, html, io, json, os, re, sys, time, urllib.parse, urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "transfers.js")
SHEEP = os.path.join(ROOT, "transfers_sheep_src.json")
SHEEP_FAIL = os.path.join(ROOT, "csv_cache", "sheep_fail.txt")   # 上一班 Sheep 抓取失敗的記號（transfers_hourly.py site 會看）
FROM = "2026-11-01"
sys.path.insert(0, HERE)

ROLE = {"Top Laner": "TOP", "Jungler": "JNG", "Mid Laner": "MID", "Bot Laner": "BOT", "Support": "SUP"}
STAFF = {"Head Coach": "主教練", "Assistant Coach": "教練", "Coach": "教練", "Strategic Coach": "戰術教練",
         "Positional Coach": "位置教練", "Team Manager": "領隊", "General Manager": "總經理", "Manager": "經理",
         "Data Analyst": "數據分析師", "Analyst": "分析師", "Esports Director": "電競總監", "Owner": "老闆",
         "Chief Executive Officer": "執行長", "Substitute": "替補", "Performance Coach": "體能教練",
         "Psychologist": "心理師", "Content Creator": "內容創作者", "Streamer": "實況主", "Translator": "翻譯",
         "Sporting Director": "運動總監", "Team Coordinator": "隊務", "Director": "總監", "President": "總裁",
         "Trainee": "練習生", "Two-Way": "雙向合約"}
STAFF.update({"Interim Head Coach": "代理主教練", "JV Manager": "二隊經理", "Academy Program Manager": "青訓計畫經理",
              "Assistant Manager": "助理經理", "Player Performance Coach": "選手表現教練", "Head of LoL": "LoL 部門主管",
              "Director of Esports": "電競總監", "Sub": "替補", "Academy Coach": "青訓教練", "Top": "上路", "Jungle": "打野",
              "Mid": "中路", "Bot": "下路", "Support": "輔助", "Owner/Chief Executive Officer": "老闆／執行長"})
_DT = r"(\d{1,2}) (January|February|March|April|May|June|July|August|September|October|November|December) (\d{4})"
_MON = {m: i + 1 for i, m in enumerate("January February March April May June July August September October November December".split())}
VERB = [   # 一句＝「名單 + 動詞片語.」；只有整句對得上才翻，對不上就保留英文原句（不硬翻）
    (r"joins? as (?:a )?substitutes?", "以替補身分加入"), (r"joins? from (?:the )?academy roster", "從二隊上調"),
    (r"joins? from sister team (.+)", r"從姊妹隊 \1 加入"), (r"joins? on loan", "租借加入"), (r"joins?", "加入"),
    (r"leaves? for sister team (.+)", r"轉往姊妹隊 \1"), (r"leaves? for (?:the )?main roster", "上調一隊"), (r"leaves? for (?:the )?academy roster", "下放二隊"), (r"leaves?", "離隊"),
    (r"will remain with the team for (\d{4})", r"\1 年留隊"), (r"will remain with the team", "留隊"),
    (r"changes? positions?", "轉換職位"), (r"moves? to (?:the )?starting roster", "升上先發"),
    (r"moves? to (?:the )?substitutes?", "轉為替補"), (r"retires?", "退役"),
    (r"(?:is|are) allowed to look for opportunities with other teams", "開放轉會（可洽談其他隊伍）"),
    (r"(?:'s?) contracts? (?:is|are) extended through (\d{4})", r"的合約延長到 \1 年"),
    (r"(?:'s?) contracts? (?:is|are) extended", "的合約延長"),
    (r"(?:'s?) contracts? (?:is|are) updated in the GCD, expiring on " + _DT, lambda m: "的合約在 GCD 更新，到期日 %s/%02d/%02d" % (m.group(3), _MON[m.group(2)], int(m.group(1)))),
    (r"(?:is|are) removed from the GCD", "的合約從 GCD 移除"),   # 2026-11-24 使用者「上路Thanatos is removed from the GCD. 沒翻譯到」（GCD＝Riot 全球合約資料庫）
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


def tweet_ts(url, day=""):
    """來源是 X 貼文 ⇒ 貼文 ID（snowflake）換回發文時間（台灣時間 YYYY-MM-DD HH:MM）。Leaguepedia 的消息只記日期，
    陣容表「近 3 天」要算 72 小時（使用者 2026-11-23）。跟 wiki 記的日期差超過一天就不採用（轉貼舊文）"""
    m = re.search(r"(?:x|twitter)\.com/[^/]+/status/(\d{15,})", url or "")
    if not m:
        return ""
    t = datetime.datetime.utcfromtimestamp(((int(m.group(1)) >> 22) + 1288834974657) / 1000) + datetime.timedelta(hours=8)
    if day:
        try:
            if abs((t.date() - datetime.date.fromisoformat(day)).days) > 1:
                return ""
        except ValueError:
            pass
    return t.strftime("%Y-%m-%d %H:%M")


TWEET_CACHE = os.path.join(ROOT, "csv_cache", "tweet_text.json")
_TW = None


def _tweet_text(url):
    """X 貼文內文（含圖片替代文字）：用公開的 fxtwitter 讀取接口（不用登入）。貼文內容不會變 ⇒ 永久快取在 csv_cache/tweet_text.json；讀不到存空字串、7 天後重試"""
    global _TW
    m = re.search(r"(?:x|twitter)\.com/([^/?#]+)/status/(\d+)", url or "")
    if not m:
        return ""
    if _TW is None:
        try:
            _TW = json.load(io.open(TWEET_CACHE, encoding="utf-8"))
        except Exception:
            _TW = {}
    k = m.group(2)
    o = _TW.get(k)
    if o and (o.get("t") or time.time() - o.get("at", 0) < 7 * 86400):
        return o.get("t") or ""
    txt = ""
    try:
        req = urllib.request.Request(f"https://api.fxtwitter.com/{m.group(1)}/status/{k}", headers={"User-Agent": "Mozilla/5.0"})
        d = json.load(urllib.request.urlopen(req, timeout=15)).get("tweet") or {}
        txt = (d.get("text") or "") + " " + " ".join((q.get("altText") or "") for q in ((d.get("media") or {}).get("all") or []))
        time.sleep(0.3)
    except Exception:
        pass
    _TW[k] = {"t": txt.strip(), "at": time.time()}
    try:
        io.open(TWEET_CACHE, "w", encoding="utf-8").write(json.dumps(_TW, ensure_ascii=False))
    except Exception:
        pass
    return txt.strip()


def _src_map(en, srcs):
    """wiki 一則消息掛好幾則公告（使用者 2026-11-24「每一個來源都確定有連正確」）：讀每則 X 公告的內文，人名只出現在其中一則 ⇒ {人名小寫: 那則的序號}。
    對不到的人不放（前端那一列改成把全部來源都列出來）"""
    names = [re.sub(r"\s*\([^()]*\)\s*$", "", d).strip() for _p, d in re.findall(r"‹([^|›]+)\|([^›]+)›", en or "")]
    txts = [_tweet_text(u).lower() for u, _n in srcs]
    out = {}
    for n in dict.fromkeys(names):
        hit = [i for i, t in enumerate(txts) if t and re.search(r"(?<![a-z0-9])" + re.escape(n.lower()) + r"(?![a-z0-9])", t)]
        if len(hit) > 1:   # 名字同時是常用字／隊名的一部分（Life ↔ Hanwha Life，每則 HLE 公告都有）：看哪一則用引號點名（‘LIFE’、'Life'、"Life"）
            q = [i for i in hit if re.search(r"[‘'\"“「]\s*" + re.escape(n.lower()) + r"\s*[’'\"”」]", txts[i])]
            if len(q) == 1:
                hit = q
        if len(hit) == 1:
            out[n.lower()] = hit[0]
    return out


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
        # 全部來源（使用者 2026-11-24「Easyhoon 的合約延長的來源是Roach的」：wiki 一則消息掛好幾則公告，照人名順序一人一則；前端人數對得上就照來源分列）
        srcs_ = [[f_[0], f_[1] if len(f_) > 1 else ""] for f_ in (z_.split(";;;") for z_ in str(x.get("src") or "").split(":::")) if f_ and f_[0].startswith("http")]
        sm_ = _src_map(en, srcs_) if len(srcs_) > 1 else {}
        out.append({**({"srcs": srcs_} if len(srcs_) > 1 else {}), **({"smap": sm_} if sm_ else {}),"d": str(x.get("ds") or "")[:10], **({"t": tweet_ts(url, str(x.get("ds") or "")[:10])} if tweet_ts(url, str(x.get("ds") or "")[:10]) else {}),
                    "n": int(x.get("n") or 0), "team": x.get("sub") or "",
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


YT_RE = re.compile(r"https?://(?:www\.|m\.)?(?:youtube\.com/(?:watch\?v=|shorts/|live/)|youtu\.be/)([\w-]{11})")


def yt_of(t):
    """文字裡第一個 YouTube 影片連結 → 統一成 https://youtu.be/影片ID（沒有回空字串）"""
    m = YT_RE.search(t or "")
    return f"https://youtu.be/{m.group(1)}" if m else ""


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


NAT_EN = ("Korean|Chinese|Danish|Greek|Spanish|French|German|Turkish|Polish|Swedish|Canadian|American|Vietnamese|Taiwanese|"
          "Brazilian|Lithuanian|Ukrainian|British|English|Czech|Slovenian|Belgian|Dutch|Japanese|Mexican|Argentine|Argentinian|"
          "Peruvian|Chilean|Croatian|Serbian|Bulgarian|Romanian|Hungarian|Austrian|Swiss|Slovak|Estonian|Latvian|Russian|"
          "Israeli|Portuguese|Italian|Norwegian|Finnish|Australian|Filipino|Thai|Malaysian|Indonesian")


def strip_nat(sheep):
    """英文原文拿掉國籍形容詞（The Korean midlaner → The midlaner；all-Canadian botlane → botlane）；使用者 2026-11-19「國名不需要列出」"""
    rx = re.compile(r"\b(?:all-)?(?:" + NAT_EN + r")\s+(?=[a-zA-Z§‹])")
    for x in sheep:
        if x.get("en"):
            x["en"] = rx.sub("", x["en"])


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
    cz = re.compile(r"((?:主|總|助理|戰術|位置|青訓)?教練)\s*" + _NAME)
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
T1_EXTRA = {"OpTic Gaming": "LCS", "Trace Esports": "LPL", "Xi Lai Gaming": "LPL"}   # 2027 才進一級的（2026 名單沒有）：隊名 → 聯賽
# 傳聞的新戰隊（使用者 2026-11-22「LPL新增 TE 跟 XLG 這兩隻戰隊只是傳聞會有的新戰隊 本身有特戰英豪戰隊 可能是因為RIOT政策而組建LOL戰隊」）：
#   隊名 → 縮寫；陣容表標「傳聞新隊」。Trace Esports 在 Leaguepedia 還沒有 LoL 隊伍頁，沒有頁也照列
NEW_RUMOR = {"Trace Esports": "TE", "Xi Lai Gaming": "XLG"}
KEEP_BLUE = [("LGD Gaming", "Crisp")]   # 手動改藍字（合約到期未宣布）：(隊名, 選手)；見 main 裡套用的那段
T1_EXCLUDE = {"Karmine Corp Blue"}   # 二隊：只因特殊賽制打了 LEC 第一賽段（使用者 2026-11-19）
# 消息裡完全不顯示的隊（使用者 2026-11-20「SLY 跟 KCB 是一樣性質 都不用顯示」）：wiki 該隊的條目不列、Sheep 的隊伍標籤拿掉
HIDE_TEAMS = T1_EXCLUDE | {"Solary"}
# 次級聯賽本身的消息不列（使用者 2026-11-26「有些次級聯賽的消息 記得幫我移除」）：Sheep 的推文 id
SEC_HIDE_SHEEP = {"2122808976257761567",   # Shopify Rebellion 成立 NACL 青訓隊
                  "2118737946429780085"}   # Team Heretics 退出 LES、解散青訓隊
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
    try:   # 下一季升降級賽晉級的隊也算一級（降級的仍保留：從一級離開的消息照樣要列）
        import transfers_board
        s |= {t["tm"] for t in transfers_board.promotion(B.cargo, year) if t["ql"]}
    except Exception as e:
        print(f"升降級賽查詢失敗：{type(e).__name__} {str(e)[:80]}")
    return sorted((s | set(T1_EXTRA)) - T1_EXCLUDE)


_STAFF_OK = re.compile(r"\b(?:head coach|coach|assistant coach|strategic coach|positional coach|analyst)\b", re.I)
_STAFF_NO = re.compile(r"performance|physical|strength|fitness|conditioning|psycholog|nutrition|manager|director|owner|ceo|content|creator|streamer|translator|coordinator|head of", re.I)


def staff_only_noise(x):
    """這則只講教練欄不列的職稱（體能教練、經理、總監…）⇒ 不列（使用者 2026-11-20「體能教練這條應該刪除」）。
    有選手路線（§TOP§…）、沒標職稱的人、或任一職稱是主教練／教練／戰略／路線教練／分析師（含「A to Head Coach」）就留"""
    en = x.get("en") or ""
    if re.search(r"§(?:TOP|JNG|MID|BOT|SUP)§", en):
        return False
    roles = re.findall(r"\(([^()]*)\)", re.sub(r"‹[^|›]+\|", "", en).replace("›", ""))
    roles = [r for r in roles if re.search(r"coach|analyst|manager|director|owner|coordinator|head of|ceo|creator|streamer", r, re.I)]
    if not roles:
        return False
    named = len(re.findall(r"‹[^|›]+\|[^›]+›(?!\s*\()", en))   # 沒標職稱的人（選手）
    if named:
        return False
    return all(not _STAFF_OK.search(re.sub(r"(?:performance|physical|strength|fitness|conditioning|mental) coach", "", r, flags=re.I)) for r in roles)


def player_roles(cargo, items, skip):
    """消息內文裡出現、但陣容表沒有的人（二隊選手、退役選手、教練…）的位置：向 Leaguepedia Players 查 ID → 路線／教練
    （使用者 2026-11-20「沒標後面兩位選手的路線」「Nuguri 是上路」「Roach 是教練」「這種類似問題都幫我解決」）。
    items＝[(內文, {賽區…})]；skip＝隊名／縮寫等不是人名的字。回傳 {名字: [路線代碼, wiki 頁名, wiki 的 ID 寫法]}。
    同名多人（Valiant 有韓國的也有挪威的）⇒ 用提到他的消息的賽區對 Residency 挑；挑不出唯一就不標（寧可不標也不要連錯人）"""
    RES = {"韓國": {"Korea"}, "中國": {"China"}, "歐洲": {"EMEA", "Europe"}, "北美": {"North America"}, "巴西": {"Brazil"},
           "亞太": {"PCS", "Vietnam", "Japan", "Oceania", "SEA", "LAS", "LCP"}, "越南": {"Vietnam"}, "日本": {"Japan"}}
    cand = {}
    for t, rgs in items:
        t = re.sub(r"https?://\S+", " ", t or "")
        for m in re.finditer(r"‹[^|›]+\|([^›]+)›|(?<![A-Za-z0-9])([A-Za-z][A-Za-z0-9]{1,15})(?![A-Za-z0-9])", t):
            n = (m.group(1) or m.group(2) or "").strip()
            if not n or n.lower() in skip or (n.isupper() and len(n) <= 3):
                continue
            cand.setdefault(n, set()).update(rgs or ())
    names = sorted(cand)
    LMAP = {"Top": "TOP", "Jungle": "JNG", "Mid": "MID", "Bot": "BOT", "Support": "SUP", "Coach": "COACH", "Analyst": "COACH"}
    rows = []
    for i in range(0, len(names), 40):
        part = names[i:i + 40]
        rows += cargo({"tables": "Players", "fields": "Players.ID=id,Players.OverviewPage=pg,Players.Role=ro,Players.Team=tm,Players.IsRetired=ret,Players.Residency=res",
                       "where": "Players.ID IN (" + ",".join('"%s"' % n.replace('"', "") for n in part) + ")", "limit": "500", "format": "json"})
    by = {}
    for r in rows:
        ro = LMAP.get((r.get("ro") or "").split(",")[0].strip())
        if ro:
            by.setdefault(str(r["id"]).lower(), []).append({"ro": ro, "pg": r["pg"], "tm": bool(r.get("tm")), "res": r.get("res") or "", "id": str(r["id"])})
    out = {}
    for n in names:
        c = by.get(n.lower()) or []
        if len(c) > 1:
            want = set().union(*[RES.get(g, set()) for g in cand[n]]) if cand[n] else set()
            c2 = [x for x in c if x["res"] in want] if want else []
            c = c2 if len(c2) == 1 else ([x for x in c if x["tm"]] if len([x for x in c if x["tm"]]) == 1 and not want else [])
        if len(c) == 1:
            out[n] = [c[0]["ro"], c[0]["pg"], c[0]["id"]]   # 第三格＝wiki 上的 ID 寫法（前端把消息內文裡的名字統一成這個大小寫；使用者 2026-11-21）
    return out


def is_t1(x, keys):
    """這則有牽涉到六大聯賽一級隊（加入、離開到次級都算；使用者 2026-11-19）"""
    if "tags" in x:
        return any((_t1key(t[1]) in keys) if t[1] else (t[0] in T1_RG) for t in x["tags"])
    return _t1key(x.get("team")) in keys


# ── Leaguepedia 查詢快取（使用者 2026-11-23「能不能加速整個流程」）────────────────────────────
#   實測一班 255 秒裡 216 秒是對 fandom 的禮貌節流（每次查詢間隔 2 秒 × 107 次；fandom 限流很兇，不能並行）⇒ 少查：
#   ①歷史賽事（名次、賽段、出賽、升降賽、改名、賽事名單）6 小時重查一次；
#   ②會隨宣布而變的（新聞、轉會、合約、效力、選手資料）只存 5 分鐘：原本 45 分鐘，結果 :40 那班沿用了 :07 的新聞查詢、
#     漏掉剛宣布的消息（使用者 2026-11-23「哪有更新 我看HLE宣布了教練 DK也宣布了輔助」）⇒ 只擋同一班內幾分鐘的重複查詢
#   查詢失敗不存；設環境變數 TR_NOCACHE=1 整個略過。檔案＝csv_cache/cargo_tr_cache.json
CC_PATH = os.path.join(ROOT, "csv_cache", "cargo_tr_cache.json")
CC_LIVE = ("NewsItems", "RosterChanges", "Contracts", "Tenures", "Players", "PlayerRedirects")


def _cargo_cached(B):
    raw_cargo = B.cargo
    try:
        cache = json.load(io.open(CC_PATH, encoding="utf-8")) if os.environ.get("TR_NOCACHE") != "1" else {}
    except Exception:
        cache = {}
    now = time.time(); stat = {"hit": 0, "miss": 0}
    cache = {k: v for k, v in cache.items() if now - v[0] < 6 * 3600}   # 過期的整個丟掉，檔案不會一直長

    def ttl(params):
        tb = str(params.get("tables") or "")
        return 5 * 60 if any(t in tb for t in CC_LIVE) else 6 * 3600

    def cargo(params):
        k = json.dumps(params, sort_keys=True, ensure_ascii=False)
        v = cache.get(k)
        if v and time.time() - v[0] < ttl(params) and os.environ.get("TR_NOCACHE") != "1":
            stat["hit"] += 1
            return json.loads(json.dumps(v[1]))   # 深拷貝：呼叫端會改回傳的列
        r = raw_cargo(params)
        stat["miss"] += 1
        cache[k] = [time.time(), r]
        return r

    def save():
        try:
            os.makedirs(os.path.dirname(CC_PATH), exist_ok=True)
            tmp = CC_PATH + ".tmp"
            io.open(tmp, "w", encoding="utf-8").write(json.dumps(cache, ensure_ascii=False))
            os.replace(tmp, CC_PATH)
        except Exception as e:
            print(f"Cargo 快取寫入失敗（略過）：{type(e).__name__}")
        print(f"Cargo 快取：命中 {stat['hit']}、實際查詢 {stat['miss']}")
    B.cargo = cargo
    return save


def main():
    import build_predict_live as B_
    _cc_save = _cargo_cached(B_)
    try:
        _main()
    finally:
        _cc_save()


def _main():
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
        if os.path.exists(SHEEP_FAIL):
            os.remove(SHEEP_FAIL)
    except Exception as e:
        print(f"Sheep Esports 抓取失敗，只用累積檔：{type(e).__name__} {str(e)[:100]}")
        # 記下這班沒抓到 ⇒ :40 那班（transfers_hourly.py site）看到這個檔會整套重跑一次，不用等下一個整點（使用者 2026-11-22 選的精進第 5 項）
        try:
            io.open(SHEEP_FAIL, "w", encoding="utf-8").write(f"{datetime.datetime.now():%Y-%m-%d %H:%M} {type(e).__name__} {str(e)[:100]}")
        except Exception:
            pass
    acc.sort(key=lambda x: x["d"], reverse=True)
    io.open(SHEEP, "w", encoding="utf-8").write(json.dumps(acc, ensure_ascii=False, indent=1))
    sheep = [{k: x[k] for k in ("id", "d", "en", "zh", "url", "kind", "tags", "st", "yt", "parts") if x.get(k)} for x in acc if x["d"][:10] >= start]
    for x in sheep:   # 推文裡的 YouTube 連結也附成 YT 按鈕
        if not x.get("yt") and yt_of(x.get("en")):
            x["yt"] = yt_of(x.get("en"))
    strip_nat(sheep)
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
        wiki = [x for x in wiki if not staff_only_noise(x)]
        # 「X's contract expires.」＝合約資料庫到期的自動紀錄，沒有公告連結、句子也沒中文化；到期本來就在陣容表用藍字表示 ⇒ 消息區不列（2026-11-20 每小時複查標出來的）
        wiki = [x for x in wiki if not (re.search(r"contract expires", x.get("en") or "") and not x.get("src"))]
        wiki = [x for x in wiki if x.get("team") not in HIDE_TEAMS]
        # 升降賽沒打贏、今年也不是一級隊的戰隊（CBLOL 的 Golden Lions）：它們的公告不列（使用者 2026-11-21「升降賽沒打贏的戰隊 資訊不要列入 例如CBLOL的GLE」）。
        #   原本因為「從一級隊離開的人加入次級隊也列」被帶進來。今年是一級、打輸被降級的隊（DFM）不在此限——那是從一級離開的消息
        try:
            import transfers_board as _tb, build_predict_live as _B
            lost = {_t1key(t["tm"]) for t in _tb.promotion(_B.cargo, int(start[:4]) if start[5:7] > "06" else int(start[:4]) - 1) if not t["ql"]} - keys
            if lost:
                n_ = len(wiki)
                wiki = [x for x in wiki if _t1key(x.get("team")) not in lost]
                for x in sheep:
                    if x.get("tags"):
                        x["tags"] = [t for t in x["tags"] if not (t[1] and _t1key(t[1]) in lost)]
                print(f"升降賽落敗的非一級隊 {len(lost)} 隊：wiki 消息拿掉 {n_ - len(wiki)} 則")
        except Exception as e:
            print(f"升降賽落敗隊過濾失敗（略過）：{type(e).__name__} {str(e)[:80]}")
        for x in sheep:
            if x.get("tags"):
                x["tags"] = [t for t in x["tags"] if t[1] not in HIDE_TEAMS]
        wiki = [x for x in wiki if is_t1(x, keys) or (x["kind"] in ("join", "both") and any(p in gone for p, _ in PL_RE.findall(x["en"])))]
        # 次級隊的那則只留「從一級隊離開的人」加入那幾個名字（使用者 2026-11-26「有些次級聯賽的消息 記得幫我移除」：
        #   BNK FEARX Youth「Lancer、Ivory、Paduck、Berr 加入」只留 Paduck；次級隊自己的離隊句拿掉）；拆不開的整則不列
        _TK = re.compile(r"(?:§[A-Z]+§)?‹[^›]+›(?:\s*\([^)]*\)|（[^）]*）)?")

        def _sec_trim(x_):
            if is_t1(x_, keys):
                return x_
            en_ = [c.strip() for c in re.split(r"(?<=\.)\s+(?=(?:§[A-Z]+§)?‹)", (x_.get("en") or "").strip()) if c.strip()]
            zh_ = [c.strip() for c in re.split(r"(?<=。)\s*", (x_.get("zh") or "").strip()) if c.strip()]
            if not en_ or len(en_) != len(zh_):
                return None
            ke, kz = [], []
            for e_, z_ in zip(en_, zh_):
                if re.search(r"\bleaves?\.?$", e_):
                    continue
                g_ = lambda t_: any(p_ in gone for p_, _ in PL_RE.findall(t_))
                ke += [t_ for t_ in _TK.findall(e_) if g_(t_)]
                kz += [t_ for t_ in _TK.findall(z_) if g_(t_)]
            if not ke or len(ke) != len(kz):
                return None
            y_ = dict(x_, kind="join")
            y_["en"] = (ke[0] + " joins.") if len(ke) == 1 else (", ".join(ke[:-1]) + " and " + ke[-1] + " join.")
            y_["zh"] = "、".join(kz) + " 加入。"
            return y_

        wiki = [y_ for y_ in (_sec_trim(x_) for x_ in wiki) if y_]
        sheep = [x for x in sheep if is_t1(x, keys) and str(x.get("id")) not in SEC_HIDE_SHEEP]
        print(f"六大聯賽一級：wiki {n0}→{len(wiki)}、sheep {n1}→{len(sheep)}（一級隊 {len(t1)}）")
    # 臨時名單（transfers_board.TRIALS：LPL 新生訓練場 11/06 登錄的人）：消息照列，句尾註明不是正式轉會（使用者 2026-11-21）
    try:
        import transfers_board as _tb2
        RG_ = {"LPL": "中國", "LCK": "韓國", "LEC": "歐洲", "LCS": "北美", "CBLOL": "巴西", "LCP": "亞太"}
        for x in wiki:
            for t_ in _tb2.TRIALS:
                if x.get("rg") == RG_.get(t_["lg"]) and x.get("kind") in ("join", "both") and t_["from"] <= x["d"][:10] <= t_["to"] and "臨時名單" not in (x.get("zh") or ""):
                    x["zh"] = (x.get("zh") or "").rstrip() + f"（{t_['name']}的臨時名單，{int(t_['end'][5:7])}/{int(t_['end'][8:10])} 到期，不算正式轉會）"
                    x["en"] = (x.get("en") or "").rstrip() + f" (temporary roster for the LPL rookie tournament, expires {t_['end'][5:].replace('-', '/')}; not a formal transfer)"
    except Exception as e:
        print(f"臨時名單註記失敗（略過）：{type(e).__name__} {str(e)[:80]}")
    wiki.sort(key=lambda x: (x["d"], x["n"]), reverse=True)
    # PTT／韓網（使用者 2026-11-19「轉會消息新增 PTT／韓網」，scripts/fetch_ptt_transfers.py 累積進 transfers_ptt_src.json）
    #   ＋使用者貼的官方消息（transfers_official_src.json，手動維護；BRO／KT 10 月續約）。extra＝[{id,d,zh,src(PTT|韓網|官方),url,st,kind,tags}]
    try:
        import fetch_ptt_transfers
        fetch_ptt_transfers.main("2026-11-15T12:00")
    except Exception as e:
        print(f"PTT 抓取失敗，只用累積檔：{type(e).__name__} {str(e)[:100]}")
    extra, ptt_raw = [], []
    sheep_ids = {x["id"] for x in acc}
    for fn in ("transfers_ptt_src.json", "transfers_official_src.json"):
        p = os.path.join(ROOT, fn)
        if os.path.exists(p):
            raw = json.load(io.open(p, encoding="utf-8"))
            if fn.startswith("transfers_ptt"):
                # 還沒複查過的（沒有 zh_fix、也沒標 hide）先不上架（使用者 2026-11-20「每一個小時更新消息 終端機要幫我重新確認資訊正確性與排版」）：
                #   標題照登常常沒標點、方向寫反、不是轉會消息 ⇒ 等 transfers_hourly.py 的 review 步驟整理過才發布
                hold = [x for x in raw if not x.get("hide") and not x.get("zh_fix")]
                if hold:
                    print(f"PTT 待複查 {len(hold)} 則（先不上架）：" + "、".join(x.get("title", "")[:24] for x in hold[:5]))
                raw = [x for x in raw if x.get("hide") or x.get("zh_fix")]
                ptt_raw = raw
                # 轉貼 Sheep Esports、而那則已收進 Sheep 來源 ⇒ 消息不重複列（使用者 2026-11-20「PTT 的文章消息是 Sheep Esports 也不要重複」）
                raw = [x for x in raw if not (set(re.findall(r"Sheep_Esports/status/(\d+)", x.get("body") or "")) & sheep_ids)]
            for x in raw:   # 內文附的 YouTube 影片（使用者 2026-11-22「傳聞裡面如果有影片 記得附上YT連結」）：手動寫了 yt 就用手動的
                if not x.get("yt"):
                    y_ = yt_of((x.get("body") or "").split("※ 發信站")[0])
                    if y_:
                        x["yt"] = y_
            extra += [{k: x[k] for k in ("id", "d", "zh", "en", "src", "url", "ptt", "st", "kind", "tags", "mv", "fake", "conf", "open", "nosplit", "yt", "parts") if x.get(k)} for x in raw if not x.get("hide")]   # parts＝一則拆成好幾列（使用者 2026-11-23「讓消息單一化」）
    extra.sort(key=lambda x: x["d"], reverse=True)
    off = [x for x in extra if x.get("src") == "官方"]   # 陣容表的續約判定吃得到（粉字）
    # PTT 傳聞進陣容表（使用者 2026-11-20「你不是有抓到 Scout 可能會去 KRX 的消息嗎 怎沒填入陣容表」）：
    #   ptt 條目的 mv／stay 由我人工判讀（標題＋內文）⇒ 轉成 Sheep 同格式交給 transfers_board.parse_sheep，
    #   跟 Sheep 一起依日期「同一人只留最新動向」（使用者「任何傳聞都以最新的動向為主」）；stay＝續約／留隊，蓋掉之前的傳聞
    pgmap = {}
    for x in (wiki or []) + (sheep or []):
        for pg_, nm_ in re.findall(r"‹([^|›]+)\|([^›]+)›", (x.get("en") or "") + (x.get("zh") or "")):
            pgmap.setdefault(nm_.lower(), urllib.parse.unquote(pg_).replace("_", " "))
    for t in old.get("board") or []:
        for L_ in list(t.get("r", {}).values()) + list(t.get("prev", {}).values()):
            for e_ in L_:
                if isinstance(e_, dict) and e_.get("p") and e_.get("n") and "§" not in e_["p"] and "‹" not in e_["p"]:
                    pgmap.setdefault(str(e_["n"]).lower(), e_["p"])
    # PTT 句子裡我手寫的 ‹頁|名›（同名選手指定頁，如 Cloud (Moon Hyeon-ho)）優先於其他來源
    for x in ptt_raw:
        for pg_, nm_ in re.findall(r"‹([^|›]+)\|([^›]+)›", x.get("zh") or ""):
            pgmap[nm_.lower()] = urllib.parse.unquote(pg_).replace("_", " ")
    synth = []
    leave_rum = []   # 只傳出要離隊、沒寫去哪的報導（PTT 條目的 out），交給 transfers_board.LEAVE_RUMORS

    def _en_for(x, nm_):
        """英文版小框的引用句：整則的英文稿裡挑有提到這個人的分句（; 分），沒有就整句"""
        en0 = re.sub(r"‹[^|›]+\|([^›]+)›", r"\1", re.sub(r"§[A-Z]+§", "", x.get("en") or "")).strip()
        cl = [c.strip() for c in re.split(r";", en0.rstrip(".")) if c.strip()]
        hit = [c for c in cl if re.search(r"(?<![A-Za-z0-9])" + re.escape(nm_) + r"(?![A-Za-z0-9])", c)]
        return ("; ".join(hit) + ".") if hit and len(hit) < len(cl) else en0

    for x in ptt_raw:
        for nm_, lane_, to_, fr_, *tp_ in x.get("mv") or []:
            pg_ = pgmap.get(nm_.lower(), nm_)
            # 小框的說明：mv 第五格有寫就用那句（一篇講很多人的消息，每個人只放跟他有關的那一句——使用者 2026-11-20 手機檢視「2 處理」）；
            #   沒寫就從重寫過的句子裡挑有提到他的分句（用「；」分），都沒有才放整句
            zh0_ = x.get("zh") or f"{nm_} 加入 {to_}。"
            cl_ = [c_.strip() for c_ in re.split(r"[；;]", re.sub(r"‹[^|›]+\|([^›]+)›", r"\1", re.sub(r"§[A-Z]+§", "", zh0_)).rstrip("。")) if c_.strip()]
            hit_ = [c_ for c_ in cl_ if re.search(r"(?<![A-Za-z0-9])" + re.escape(nm_) + r"(?![A-Za-z0-9])", c_)]
            zh_ = tp_[0] if tp_ and tp_[0] else ("；".join(hit_) + "。" if hit_ and len(hit_) < len(cl_) else zh0_)
            synth.append({"d": x["d"], "st": x.get("st") or "rumor", "kind": "join", "src": x.get("src") or "PTT",   # 來源名照原樣（含手動加的 X 帳號如 Rostermania，使用者 2026-11-23）
                          # ↓ url 自己一行：2026-11-23（eec23cd7）加上面那句行內註解時把這個鍵一起吃進註解，之後 PTT 來源檔的傳聞進陣容表都沒有來源網址
                          #   ⇒ 小框的來源名點不開原文（使用者 2026-11-20「Sheep 的來源就寫 SE 然後超連結」）。行內註解只能放在一行的最後一個鍵後面
                          "url": x.get("url") or x.get("ptt") or "",
                          "zh": zh_, "en": _en_for(x, nm_), "who": [nm_, pg_, lane_],
                          "tags": ([["", fr_, "out"]] if fr_ else []) + [["", to_, "in"]]})
            if lane_ == "COACH" and nm_ in (x.get("hc") or []):
                synth[-1]["sr"] = "HC"   # 傳聞的是主教練（條目的 hc＝[名字]，例：Sephis 去 FX 當主教練）⇒ 陣容表放主教練欄；沒標的教練傳聞在後勤欄
        if x.get("stay"):
            synth.append({"d": x["d"], "st": x.get("st") or "rumor", "kind": "other", "zh": "", "stay": [s_[0] for s_ in x["stay"]]})
        # out＝[[名字, 原隊全名, 一句話]]：只傳出要離隊、沒寫去哪（使用者 2026-11-25「有離隊傳聞 但還沒宣布的也綠色」）⇒ 陣容表那個人畫綠字。官方消息不走這條
        if not x.get("hide") and (x.get("st") or "rumor") == "rumor":
            for nm_, tm_, *tp_ in x.get("out") or []:
                zh0_ = re.sub(r"‹[^|›]+\|([^›]+)›", r"\1", re.sub(r"§[A-Z]+§", "", x.get("zh") or "")).strip()
                leave_rum.append({"n": nm_, "p": pgmap.get(nm_.lower(), nm_), "tm": tm_, "d": x["d"], "tip": (tp_[0] if tp_ and tp_[0] else zh0_),
                                  "src": x.get("src") or "PTT", "u": x.get("url") or x.get("ptt") or "", "en": (tp_[1] if len(tp_) > 1 and tp_[1] else _en_for(x, nm_))})
    farewell = []   # 戰隊官方 Thank you／Farewell 文（PTT 轉貼，含內文）⇒ 陣容表當宣布離隊
    p = os.path.join(ROOT, "transfers_ptt_src.json")
    if os.path.exists(p):
        farewell = [x for x in json.load(io.open(p, encoding="utf-8")) if x.get("st") == "official"
                    and re.search(r"thank ?you|farewell|離隊|期滿|結束合作", x.get("title") or "", re.I)]   # 陣容表的續約判定吃得到（粉字）
    # 陣容表（使用者 2026-11-19：六大聯賽各隊 × 上野中下輔＋教練，傳聞加 *；scripts/transfers_board.py）
    try:
        import build_predict_live as B, transfers_board
        yr = int(start[:4]) if start[5:7] > "06" else int(start[:4]) - 1
        transfers_board.LEAVE_RUMORS = leave_rum
        for v_ in leave_rum:
            if v_.get("tip") and v_.get("en"):
                transfers_board.TIP_EN[v_["tip"]] = v_["en"]   # 英文版小框的引用句
        board = transfers_board.build(B.cargo, yr, start, sheep + off + synth, dict(T1_EXTRA), wiki, T1_EXCLUDE, farewell, {"OpTic Gaming": "Dignitas"}, NEW_RUMOR)
        print(f"陣容表：{len(board)} 隊")
        # 手動改成藍字（合約到期、未宣布離隊）的人：wiki 記他已離隊，但爆料說會回原隊（使用者 2026-11-22「Crisp那個就用藍字」：微博 LPL 陣容表把 Crisp 列在 LGD 輔助）
        #   ⇒ 該隊格子與自由人列都拿掉「已宣布離隊」，合約到期日記成離隊那天，前端就畫藍字（合約到期未宣布）
        for tm_, nm_ in KEEP_BLUE:
            for x in board:
                for e in x["r"].get("SUP", []) + x["r"].get("TOP", []) + x["r"].get("JNG", []) + x["r"].get("MID", []) + x["r"].get("BOT", []) + x["r"].get("COACH", []):
                    if e["n"].lower() == nm_.lower() and (x.get("nm") == tm_ or (x.get("fa") and e.get("from") == tm_)):
                        gd_ = e.pop("gd", None) or max((z[1] for z in e.get("tn") or [] if z and z[1]), default="")
                        e.pop("gone", None)
                        if gd_ and (not e.get("c") or e["c"] >= datetime.date.today().isoformat()):
                            e["c"] = gd_   # 原本的合約日還沒到的也改成離隊日，不然 gone 拿掉後會變白字「續留」
        # 「傳出要續約／留隊」的報導（PTT 條目的 stay、狀態是傳聞）：陣容表的顏色不動（官方公布才算續約），但小框要看得到那則報導
        #   ——2026-11-21 使用者貼「T1 與教練李知勳續約」說「這個是 T1 教練 Easyhoon」：原本只進消息，Easyhoon 的小框完全看不出來。
        #   做法：掛到那個人在該隊（或自由人列、來自該隊）的格子上，欄位 tips＝[{d, src, u, tip, tipE}]（跟手動自由人的相關消息同一格式，前端共用）
        try:
            n_tip = 0
            for x in ptt_raw:
                if not x.get("stay") or (x.get("st") or "rumor") != "rumor":
                    continue
                plain_ = re.sub(r"‹[^|›]+\|([^›]+)›", r"\1", re.sub(r"§[A-Z]+§", "", x.get("zh") or "")).strip()
                cl_ = [c_.strip() for c_ in re.split(r"[；;]", plain_.rstrip("。")) if c_.strip()]
                for s_ in x["stay"]:
                    nm_, tm_ = s_[0], (s_[1] if len(s_) > 1 else "")
                    hit_ = [c_ for c_ in cl_ if re.search(r"(?<![A-Za-z0-9])" + re.escape(nm_) + r"(?![A-Za-z0-9])", c_)]
                    tip_ = ("；".join(hit_) + "。") if hit_ and len(hit_) < len(cl_) else plain_
                    if not tip_ or not tm_:
                        continue
                    o_ = {"d": x["d"][:10], "src": x.get("src") or "PTT",
                          "u": x.get("url") or x.get("ptt") or "", "tip": tip_, "tipE": _en_for(x, nm_)}
                    for t_ in board:
                        same_tm = transfers_board.tkey(t_.get("nm") or "") == transfers_board.tkey(tm_) or transfers_board.tkey(t_.get("tm") or "") == transfers_board.tkey(tm_)
                        for L_ in t_.get("r", {}).values():
                            for e_ in L_:
                                if e_.get("r") or transfers_board.key(e_.get("n")) != transfers_board.key(nm_):
                                    continue
                                if same_tm or (t_.get("fa") and transfers_board.tkey(e_.get("from") or "") == transfers_board.tkey(tm_)):
                                    L2_ = [v_ for v_ in (e_.get("tips") or []) if v_.get("u") != o_["u"] or v_.get("tip") != o_["tip"]] + [o_]
                                    e_["tips"] = sorted(L2_, key=lambda v_: v_.get("d") or "", reverse=True)[:3]
                                    n_tip += 1
            if n_tip:
                print(f"續約／留隊的報導掛進小框：{n_tip} 格")
        except Exception as e:
            print(f"續約報導掛小框失敗（略過）：{type(e).__name__} {str(e)[:120]}")
    except Exception as e:
        board = old.get("board") or []
        print(f"陣容表失敗，沿用舊檔 {len(board)} 隊：{type(e).__name__} {str(e)[:150]}")
    try:
        import build_predict_live as B2
        skipw = {w.lower() for t in (t1 or []) for w in re.findall(r"[A-Za-z0-9]+", t)} | {"lck", "lpl", "lec", "lcs", "lcp", "cblol", "ptt", "obgg", "gcd", "inven", "riot", "msi", "emea", "masters", "the", "play", "carry", "ad"}
        lg2rg = {"LCK": "韓國", "LPL": "中國", "LEC": "歐洲", "LCS": "北美", "CBLOL": "巴西", "LCP": "亞太"}
        tm_rg = {t["nm"]: lg2rg.get(t["lg"], "") for t in board} | {t["tm"]: lg2rg.get(t["lg"], "") for t in board}
        def _rgs(x):   # 這則消息的賽區：wiki 的 rg、標籤的賽區、標籤／去向的隊伍所屬聯賽
            g = {x.get("rg")} | {t[0] for t in x.get("tags") or []} | {tm_rg.get(t[1], "") for t in x.get("tags") or []}
            g |= {tm_rg.get(m[2], "") for m in x.get("mv") or []} | {tm_rg.get(m[3], "") for m in x.get("mv") or []}
            return {v for v in g if v}
        roles = player_roles(B2.cargo, [((x.get("zh") or ""), _rgs(x)) for x in sheep + extra + wiki], skipw)
        print(f"消息人名位置：查到 {len(roles)} 人")
    except Exception as e:
        roles = old.get("roles") or {}
        print(f"消息人名位置查詢失敗，沿用舊檔 {len(roles)} 人：{type(e).__name__} {str(e)[:100]}")
    # 退役消息（使用者 2026-11-20「幫我找出 Evi 退役的消息放入消息區 有退役的都改成這樣」）：陣容表查到退役的選手 → Leaguepedia 新聞裡他的 retires 那句（附本人貼文連結）
    try:
        ret_ = getattr(transfers_board, "RETIRED", {}) or {}
        if ret_:
            LGRG = {"LCK": "韓國", "LPL": "中國", "LEC": "歐洲", "LCS": "北美", "CBLOL": "巴西", "LCP": "亞太"}
            rows_ = B.cargo({"tables": "NewsItems", "fields": "Date_Sort=d,Sentence=s,Source=src", "where": f'Sentence LIKE "%retire%" AND Date_Sort>="{yr}-06-01"',
                             "order_by": "Date_Sort DESC", "limit": "500", "format": "json"})
            seen_ = {x_.get("id") for x_ in extra}
            for y_ in rows_:
                sent_ = html.unescape(y_.get("s") or "")
                if "out of retirement" in sent_ or "intent to retire" in sent_:
                    continue
                for pg_, _nm in re.findall(r"\[\[([^|\]]+)\|([^\]]+)\]\]", sent_):
                    k_ = transfers_board.key(pg_)
                    if k_ in ret_ and "ret-" + k_ not in seen_:
                        pg0, id0, rr0, tm0, lg0 = ret_[k_]
                        # 在哪一隊退役：陣容表 FA 列記的原隊（from）優先（使用者 2026-11-24「hena是在png退役的」：季中換隊的人兩隊上一位都有他，RETIRED 會先碰到排前面的 UP）
                        fa_ = next((e_ for t_ in board if t_.get("fa") for L_ in (t_.get("r") or {}).values() for e_ in L_
                                    if e_.get("ret") and e_.get("from") and transfers_board.key(e_.get("p") or e_.get("n") or "") == k_), None)
                        if fa_:
                            tm0 = fa_["from"]
                            lg0 = next((t_.get("lg") for t_ in board if not t_.get("fa") and tm0 in (t_.get("nm"), t_.get("tm"))), lg0)
                        extra.append({"id": "ret-" + k_, "d": (y_.get("d") or "")[:10] + " 00:00", "zh": (f"§{rr0}§" if rr0 and rr0 != "COACH" else "") + f"‹{pg0}|{id0}› 宣布退役。",
                                      "en": (f"§{rr0}§" if rr0 and rr0 != "COACH" else "") + f"‹{pg0}|{id0}› announces retirement.",
                                      "src": "官方", "st": "official", "kind": "leave", "tags": [[LGRG.get(lg0, ""), tm0, "out"]], "url": (y_.get("src") or "").split(";;;")[0]})
                        seen_.add("ret-" + k_)
            extra.sort(key=lambda x_: x_["d"], reverse=True)
    except Exception as e_:
        print(f"   退役消息查詢失敗：{type(e_).__name__} {str(e_)[:100]}")
    # 國際賽資歷分（轉會評分的 10%）：陣容表上出現的人（格子＋上一位）→ {名字小寫: 分數}；沒打過國際賽的不列
    intl = (old.get("intl") or {})
    try:
        import transfers_intl
        sc_ = transfers_intl.scores(B.cargo)
        strip_ = lambda n_: re.sub(r"\s*\([^()]*\)\s*$", "", str(n_ or ""))
        it_ = {}
        for t_ in board:
            ppl_ = [(e_.get("p") or e_.get("n"), e_.get("n")) for L_ in t_.get("r", {}).values() for e_ in L_]
            ppl_ += [((e_.get("n") if isinstance(e_, dict) else e_), strip_(e_.get("n") if isinstance(e_, dict) else e_)) for L_ in t_.get("prev", {}).values() for e_ in L_]
            for pg_, nm_ in ppl_:
                v_ = sc_.get(str(pg_ or "").lower())
                if v_:
                    it_[strip_(nm_).lower()] = max(v_, it_.get(strip_(nm_).lower(), 0))
        intl = it_
        print(f"國際賽資歷分：{len(intl)} 人")
    except Exception as e_:
        print(f"   國際賽資歷分失敗（沿用舊的 {len(intl)} 人）：{type(e_).__name__} {str(e_)[:100]}")
    # 同一天在 A 隊離隊、在 B 隊加入的人 ⇒ 消息只留 B 隊「加入」那列（原隊欄本來就會標 A），時間就是加入那則的時間
    #   （RED「Morttheus 離隊」＋VKS「Morttheus 加入」；使用者 2026-11-23「像是 delight 這種加入離隊同一天的要合併 時間算加入的那瞬間」：
    #    HLE「Life、Sonstar 加入。Delight 離隊。」＋DK「Delight 加入。Career 離隊。」⇒ HLE 那則拿掉 Delight 離隊那句）
    #   一則裡有加入也有離隊（kind both）時只拿掉離隊句裡那幾個人；整句拿光就刪句，整則只剩加入就改成 join，什麼都不剩就整則不列。陣容表在這之前已建好，不受影響
    _TOK = re.compile(r"(?:§[A-Z]+§)?‹[^›]+›(?:\s*\([^)]*\)|（[^）]*）)?")

    def _clauses(x_):
        """[(英文句, 中文句, 是不是離隊句)]：英文以「. 」切、中文以「。」切，兩邊句數對得上才拆（對不上回 None，不動那則）"""
        en_ = [c.strip() for c in re.split(r"(?<=\.)\s+(?=(?:§[A-Z]+§)?‹)", (x_.get("en") or "").strip()) if c.strip()]
        zh_ = [c.strip() for c in re.split(r"(?<=。)\s*", (x_.get("zh") or "").strip()) if c.strip()]
        if not en_ or len(en_) != len(zh_):
            return None
        return [(e_, z_, bool(re.search(r"\bleaves?\.?$", e_))) for e_, z_ in zip(en_, zh_)]

    _joined = set()
    for x_ in wiki:
        if x_.get("kind") in ("join", "both"):
            for e_, z_, lv_ in (_clauses(x_) or [(x_.get("en") or "", "", False)]):
                if not lv_:
                    _joined |= {(p_, (x_.get("d") or "")[:10], x_.get("team")) for p_, _ in PL_RE.findall(e_)}
    _jd = {(p_, d_) for p_, d_, _ in _joined}
    _jt = {(p_, d_): t_ for p_, d_, t_ in _joined}

    def _drop_left(x_):
        if x_.get("kind") not in ("leave", "both"):
            return x_
        d_ = (x_.get("d") or "")[:10]
        cl_ = _clauses(x_)
        if cl_ is None:   # 句子拆不開：整則都是離隊、而且每個人都在別隊加入才拿掉（舊規則）
            ps_ = PL_RE.findall(x_.get("en") or "")
            return None if x_.get("kind") == "leave" and ps_ and all((p_, d_) in _jd and _jt[(p_, d_)] != x_.get("team") for p_, _ in ps_) else x_
        out_e, out_z, changed = [], [], False
        for e_, z_, lv_ in cl_:
            if not lv_:
                out_e.append(e_); out_z.append(z_); continue
            te_ = [t_ for t_ in _TOK.findall(e_)]
            tz_ = [t_ for t_ in _TOK.findall(z_)]
            keep = lambda t_: not any((p_, d_) in _jd and _jt[(p_, d_)] != x_.get("team") for p_, _ in PL_RE.findall(t_))
            ke, kz = [t_ for t_ in te_ if keep(t_)], [t_ for t_ in tz_ if keep(t_)]
            if len(ke) == len(te_) and len(kz) == len(tz_):
                out_e.append(e_); out_z.append(z_); continue
            changed = True
            if ke and kz:
                out_e.append((ke[0] if len(ke) == 1 else ", ".join(ke[:-1]) + " and " + ke[-1]) + (" leaves." if len(ke) == 1 else " leave."))
                out_z.append("、".join(kz) + " 離隊。")
        if not changed:
            return x_
        if not out_e:
            return None
        y_ = dict(x_, en=" ".join(out_e), zh=" ".join(out_z))
        if not any(re.search(r"\bleaves?\.?$", e_) for e_ in out_e):
            y_["kind"] = "join"
        return y_
    wiki = [y_ for y_ in (_drop_left(x_) for x_ in wiki) if y_]
    # WIKI 的日期是美國太平洋時間的「日期」（沒有時分），亞洲隊伍早上發的公告會被記成前一天（KRX 11/17 08:00 台灣時間的離隊公告，wiki 記 11/16）
    #   ⇒ 換成台灣時間（使用者 2026-11-20「wiki 的消息時間好像不是標記台灣時間 要幫我轉換」）：
    #   ①來源是 X 貼文：貼文編號本身帶發文時間（snowflake）⇒ 直接換算，精確到分；
    #   ②其他來源（FB、微博、沒附連結）：找 PTT 上同一批人的官方公告轉貼（wiki 日期當天到後兩天內），用那篇的發文時間；
    #   ③都沒有 ⇒ 維持 wiki 的日期（不亂猜）。陣容表用的是轉換前的日期，這裡只改消息顯示用的那一份
    TW_ = datetime.timezone(datetime.timedelta(hours=8))

    def _tw(x_):
        m_ = re.search(r"(?:x|twitter)\.com/[^/]+/status/(\d+)", str(x_.get("src") or "") + " " + str(x_.get("url") or ""))
        if m_:
            return datetime.datetime.fromtimestamp(((int(m_.group(1)) >> 22) + 1288834974657) / 1000, TW_).strftime("%Y-%m-%d %H:%M")
        names_ = [n_ for _, n_ in PL_RE.findall(x_.get("en") or x_.get("zh") or "")]
        d0_ = str(x_.get("d") or "")[:10]
        if names_ and d0_:
            lim_ = (datetime.date.fromisoformat(d0_) + datetime.timedelta(days=2)).isoformat() + " 23:59"
            c_ = [p_["d"] for p_ in ptt_all_ if p_.get("st") == "official" and d0_ <= p_["d"] <= lim_
                  and sum(1 for n_ in names_ if re.search(r"(?<![A-Za-z0-9])" + re.escape(n_) + r"(?![A-Za-z0-9])", (p_.get("title") or "") + " " + (p_.get("body") or ""), re.I)) >= max(1, (len(names_) + 1) // 2)]
            if c_:
                return min(c_)
        return x_.get("d")
    try:
        ptt_all_ = json.load(io.open(os.path.join(ROOT, "transfers_ptt_src.json"), encoding="utf-8"))
    except Exception:
        ptt_all_ = []
    wiki = [dict(x_, d=_tw(x_)) for x_ in wiki]
    extra = [dict(x_, d=_tw(x_)) if str(x_.get("id", "")).startswith("ret-") else x_ for x_ in extra]
    wiki.sort(key=lambda x_: x_["d"], reverse=True); extra.sort(key=lambda x_: x_["d"], reverse=True)
    # 隊伍小框（使用者 2026-11-22「左半邊點擊後要顯示 2026 先發五人(場次最多的)以及教練的WIKI圖片…下方是2027的」）：
    #   s26＝各隊那一年五路出賽最多場的人、pimg＝選手／主教練在 Leaguepedia 的圖片網址（該年最新一張優先）、pfc＝每張圖裡臉的位置（前端把人頭對齊用）
    #   （scripts/transfers_photos.py；查過的存 csv_cache，每小時只補新的人）。同一支也把每個人在這一隊的歷次效力區間掛到 board 的格子上（tn，小框的「效力」用）
    try:
        import transfers_photos
        s26, pimg, pfc, pph, pbio = transfers_photos.build(B.cargo, yr, board, roles, {"OpTic Gaming": "Dignitas"})
        print(f"隊伍小框：先發 {len(s26)} 隊、圖片 {len(pimg)} 張（量到臉 {len(pfc)} 張、裁好頭像 {len(pph)} 張）")
    except Exception as e:
        s26, pimg, pfc, pph, pbio = old.get("s26") or {}, old.get("pimg") or {}, old.get("pfc") or {}, old.get("pph") or {}, old.get("pbio") or {}
        print(f"隊伍小框資料失敗，沿用舊檔（先發 {len(s26)} 隊、圖片 {len(pimg)} 張）：{type(e).__name__} {str(e)[:100]}")
    data = {"at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "from": start, "t1": t1, "wiki": wiki, "sheep": sheep, "extra": extra, "roles": roles, "board": board, "intl": intl,
            "s26": s26, "pimg": pimg, "pfc": pfc, "pph": pph, "pbio": pbio}   # pbio＝{頁名: [生日, 出道日]}（陣容對比 2027 那排的年齡／年資）
    try:
        used = {o.get("tip") for t in board for L in (t.get("r") or {}).values() for e in L for o in ([e] + (e.get("ros") or []) + ([e["ro"]] if e.get("ro") else []) + (e.get("tips") or []))}
        data["tipEn"] = {k: v for k, v in _tb.TIP_EN.items() if k in used} or (old.get("tipEn") or {})
    except Exception as e:
        print(f"   tipEn 對照表沒寫成：{type(e).__name__} {str(e)[:80]}")
        data["tipEn"] = old.get("tipEn") or {}
    # 合約年限（使用者 2026-11-25「例如Zeus這種簽約三年的 小框要寫」）：官方公告講到簽幾年／到哪一年，Leaguepedia 的到期日往往晚幾天才登記
    #   ⇒ transfers_ptt_src.json 的條目用 con＝[[選手 ID, 新隊全名, 年數或 null, 到期年份或 ""], …] 記下來（要 st=official；被 hide 的重複公告也算，帶 sus 記號的不算），
    #   掛到陣容表那一格：cy＝年數、cu＝到期年份。只給小框顯示用，不動 c（到期日）——到期、打勾、評分那些判斷照舊只看 Leaguepedia
    try:
        con_ = {}
        for x_ in ptt_all_:
            if (x_.get("st") or "") != "official" or x_.get("sus"):
                continue
            for nm_, tm_, yrs_, until_ in x_.get("con") or []:
                con_[(str(nm_).lower(), tm_)] = (yrs_, until_)
        n_con = 0
        for t_ in board:
            for L_ in (t_.get("r") or {}).values():
                for e_ in L_:
                    v_ = con_.get((str(e_.get("n") or "").lower(), t_.get("nm")))
                    if v_ and not e_.get("gone") and not e_.get("r"):
                        if v_[0]:
                            e_["cy"] = int(v_[0])
                        if v_[1]:
                            e_["cu"] = str(v_[1])
                        n_con += 1
        if con_:
            print(f"   合約年限：登記 {len(con_)} 筆、掛上 {n_con} 筆")
    except Exception as e:
        print(f"   合約年限沒掛上：{type(e).__name__} {str(e)[:80]}")
    # 粉絲投票（使用者 2026-11-25「把兩邊數據合在一起 點擊綠色勾勾的時候會顯示」）：使用者自己在 Threads／YouTube 發的「2027 T1 新陣容可以走多遠？」投票，
    #   scripts/fetch_fan_polls.py 抓好累積在 transfers_polls_src.json，這裡只把合併後的結果放進來（鍵＝隊伍縮寫大寫；陣容表有打勾的隊才點得到）
    try:
        import fetch_fan_polls
        data["polls"] = fetch_fan_polls.build()
    except Exception as e:
        data["polls"] = old.get("polls") or {}
        print(f"   粉絲投票沒寫成，沿用舊的 {len(data['polls'])} 隊：{type(e).__name__} {str(e)[:80]}")
    # 魚丸影片評價（使用者 2026-11-26「幫我在最後面加上一個眼睛的EMOJI 點擊進去可以看到投票 以及我的影片提到的評價」）：
    #   transfers_takes_src.json＝對話端讀使用者影片的頻道字幕、逐隊整理的重點（手寫，不是抓的；格式見那個檔開頭的說明），這裡原樣帶進 transfers.js 的 takes。
    #   陣容表每列最後面的 👁 點了開「投票＋影片評價」小框（有投票或有評價的隊才有 👁）。檔案讀不到／壞掉 ⇒ 沿用上一版，不讓 👁 整批消失
    try:
        tk = json.load(io.open(os.path.join(ROOT, "transfers_takes_src.json"), encoding="utf-8"))
        data["takes"] = {"v": tk.get("v") or {}, "t": {str(k).upper(): v for k, v in (tk.get("t") or {}).items() if v}}
    except Exception as e:
        data["takes"] = old.get("takes") or {}
        print(f"   影片評價沒寫成，沿用舊的 {len((data['takes'] or {}).get('t') or {})} 隊：{type(e).__name__} {str(e)[:80]}")
    io.open(OUT, "w", encoding="utf-8").write("window.TRANSFERS=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print(f"transfers.js：wiki {len(wiki)}、sheep {len(sheep)}、PTT／韓網／官方 {len(extra)}、粉絲投票 {len(data['polls'])} 隊、影片評價 {len((data.get('takes') or {}).get('t') or {})} 隊")


if __name__ == "__main__":
    main()
