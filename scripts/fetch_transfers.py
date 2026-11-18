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
import datetime, email.utils, html, io, json, os, re, sys, urllib.request

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
    (r"leaves? for (?:the )?main roster", "上調一軍"), (r"leaves? for (?:the )?academy roster", "下放二軍"), (r"leaves?", "離隊"),
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
    s = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"§\s+", "§", re.sub(r"\s+", " ", s)).strip()
    return s


def _staff(m):
    inner = m.group(1)
    if inner in STAFF:
        return "（" + STAFF[inner] + "）"
    parts = re.split(r"(\s+to\s+|/|,\s*)", inner)
    out = [(" → " if p.strip() == "to" else "／") if re.fullmatch(r"\s+to\s+|/|,\s*", p) else STAFF.get(p.strip(), p.strip()) for p in parts]
    return "（" + "".join(out) + "）"


def _one(sen):
    """一句英文 → 中文；對不上句型回傳原句"""
    body = sen.rstrip(".").strip()
    for a, b in WHOLE:
        if re.fullmatch(a, body):
            return re.sub(a, b, body).replace("Hong Kong", "香港") + "。"
    for pat, rep in VERB:
        m = re.fullmatch(r"(.+?)\s*(" + pat + r")", body)
        if not m:
            continue
        names = re.sub(r"\s*\(([^()]*)\)", _staff, m.group(1))
        names = re.sub(r",?\s+and\s+|,\s*", "、", names).strip()
        verb = re.sub(pat, rep, m.group(2))
        return re.sub(r"^Organization$", "戰隊", names) + " " + verb + "。"
    return sen


def to_zh(s):
    sens = re.split(r"(?<=\.)\s+(?=§|\w)", s)
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


def fetch_sheep(start):
    """內嵌時間軸（免登入）→ 轉會推文；只取 start 之後、帶 [OFFICIAL]/[SOURCES] 標籤或含轉會字眼的"""
    req = urllib.request.Request("https://syndication.twitter.com/srv/timeline-profile/screen-name/Sheep_Esports",
                                 headers={"User-Agent": "Mozilla/5.0"})
    s = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
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
    sheep = [{k: x[k] for k in ("id", "d", "en", "zh", "url") if x.get(k)} for x in acc if x["d"][:10] >= start]
    wiki.sort(key=lambda x: (x["d"], x["n"]), reverse=True)
    data = {"at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "from": start, "wiki": wiki, "sheep": sheep}
    io.open(OUT, "w", encoding="utf-8").write("window.TRANSFERS=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print(f"transfers.js：wiki {len(wiki)}、sheep {len(sheep)}")


if __name__ == "__main__":
    main()
