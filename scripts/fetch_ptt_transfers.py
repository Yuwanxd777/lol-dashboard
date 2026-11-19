# -*- coding: utf-8 -*-
"""PTT LoL 板轉會消息（使用者 2026-11-19「轉會消息新增 PTT／韓網，從 11/15 中午 12 點後的文章開始看，
跟轉會、乳摸相關的才紀錄；點進去是韓網傳過來的消息就寫韓網、並標註韓網的連結」）。

- 從 index.html 往前翻到起點時間為止（置底文不算），標題篩轉會相關（不收 Re:、提問／閒談）。
- 逐篇讀內文找韓網連結（fmkorea／inven／dcinside／naver／theqoo／韓媒…）：有 ⇒ src＝韓網、url＝第一個韓網連結；
  沒有 ⇒ src＝PTT、url＝PTT 文章。另存 ptt＝PTT 文章網址。
- 標題本來就是中文 ⇒ zh＝去掉【分類】的標題，不用翻譯。st：乳摸／傳聞／有望／考慮／可能 ⇒ rumor，其他 official。
- 累積進 transfers_ptt_src.json（跟 Sheep 一樣只增不減；已收過的不重抓內文）。
用法：python scripts/fetch_ptt_transfers.py [起點 YYYY-MM-DDTHH:MM，預設 2026-11-15T12:00]
"""
import datetime
import io
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "transfers_ptt_src.json")
BOARD = "https://www.ptt.cc/bbs/LoL/"
UA = {"User-Agent": "Mozilla/5.0", "Cookie": "over18=1"}
TZ = datetime.timezone(datetime.timedelta(hours=8))
DEFAULT_START = "2026-11-15T12:00"

# 標題篩選：乳摸一律收；情報／外絮／新聞／閒聊 要有轉會字眼；提問、閒談、採訪花絮不收
RUMOR = re.compile(r"乳摸|傳聞|有望|考慮|可能|動向|爆料")
MOVE = re.compile(r"加入|離隊|續約|簽下|簽約|轉會|自由市場|thank ?you|welcome|joins?\b|rejoins?|re-?sign|farewell|官宣|回歸|退出|遞補|陣容|解散|上調|擔任|監督|head coach",
                  re.I)
SKIP = re.compile(r"網站|造型|經濟|怎|嗎|？|\?|採訪|心路|獎盃|喜帖|團練|籃網|紅牛|預告|直播上說|似乎|詢問|拉扯|擴編|純娛樂")
KOREAN = re.compile(r"https?://(?:[\w-]+\.)*(?:fmkorea\.com|inven\.co\.kr|dcinside\.com|naver\.com|naver\.me|theqoo\.net|instiz\.net|ruliweb\.com|"
                    r"daum\.net|dailyesports\.com|fomos\.kr|sportsseoul\.com|xportsnews\.com|osen\.co\.kr|mydaily\.co\.kr|"
                    r"spotvnews\.co\.kr|sports\.khan\.co\.kr|starnewskorea\.com|newsis\.com|yna\.co\.kr|[\w-]+\.kr)(?:/[^\s\"'<>]*)?", re.I)


def get(u):
    for i in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=20).read().decode("utf-8", "replace")
        except Exception:
            if i == 2:
                raise
            time.sleep(2)


def plain(h):
    """內文純文字（只到「※ 發信站」前＝不含推文），陣容表拿來比對 Thank you 文點到的名字"""
    h = re.sub(r'<div class="article-metaline[^"]*">[\s\S]*?</div>\s*</div>', "", h)   # 作者／看板／標題／時間
    t = re.sub(r"<[^>]+>", "", h.split(">", 1)[-1])
    t = t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'").replace("&quot;", '"')
    return re.sub(r"\n\s*\n+", "\n", t).strip()[:4000]


def want(title):
    if title.startswith("Re:") or title.startswith("Fw:"):
        return False
    m = re.match(r"\[([^\]]+)\]", title)
    cat = m.group(1).strip() if m else ""
    if "乳摸" in title or cat == "乳摸":
        return not SKIP.search(title)
    if cat in ("情報", "外絮", "新聞", "閒聊") and MOVE.search(title) and not SKIP.search(title):
        return True
    return False


def list_posts(cut):
    u, out = BOARD + "index.html", {}
    for _ in range(300):
        h = get(u)
        body = h.split('<div class="r-list-sep"></div>')[0]   # 置底文不算
        ts = []
        for href, title in re.findall(r'<div class="title">\s*<a href="(/bbs/LoL/M\.\d+\.A\.[0-9A-F]+\.html)">([^<]*)</a>', body):
            t = int(re.search(r"M\.(\d+)\.", href).group(1))
            ts.append(t)
            out[href] = (t, title.strip().replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", "”"))
        prev = re.search(r'href="(/bbs/LoL/index\d+\.html)">&lsaquo; 上頁', h)
        if (ts and max(ts) < cut) or not prev:
            break
        u = "https://www.ptt.cc" + prev.group(1)
        time.sleep(0.3)
    return sorted((t, ti, href) for href, (t, ti) in out.items() if t >= cut)


def main(start=None):
    start = start or (sys.argv[1] if len(sys.argv) > 1 else DEFAULT_START)
    cut = int(datetime.datetime.fromisoformat(start).replace(tzinfo=TZ).timestamp())
    acc = json.load(io.open(SRC, encoding="utf-8")) if os.path.exists(SRC) else []
    have = {x["id"] for x in acc}
    if acc:   # 已累積過 ⇒ 只往回翻到最後一則的前一天（不用每班從起點整個重翻）
        last = max(int(datetime.datetime.strptime(x["d"], "%Y-%m-%d %H:%M").replace(tzinfo=TZ).timestamp()) for x in acc)
        cut = max(cut, last - 86400)
    for x in acc:   # 舊條目沒存內文的補抓
        if "body" not in x and x.get("ptt"):
            try:
                x["body"] = plain(get(x["ptt"]).split('<div id="main-content"', 1)[-1].split("※ 發信站", 1)[0])
                time.sleep(0.3)
            except Exception:
                pass
    posts = list_posts(cut)
    n = 0
    for t, title, href in posts:
        pid = href.split("/")[-1][:-5]
        if pid in have or not want(title):
            continue
        ptt = "https://www.ptt.cc" + href
        try:
            h = get(ptt)
        except Exception as e:
            print(f"   PTT 內文讀取失敗 {pid}：{type(e).__name__}")
            continue
        main_ = h.split('<div id="main-content"', 1)[-1].split("※ 發信站", 1)[0]   # 只看內文，不看推文（使用者 2026-11-19；推文在「※ 發信站」之後）
        kr = [m.group(0).replace("&amp;", "&") for m in KOREAN.finditer(main_)]
        zh = re.sub(r"^\[[^\]]+\]\s*", "", title).strip()
        x = {"id": pid, "d": datetime.datetime.fromtimestamp(t, TZ).strftime("%Y-%m-%d %H:%M"), "title": title, "zh": zh,
             "src": "韓網" if kr else "PTT", "url": kr[0] if kr else ptt, "ptt": ptt,
             "st": "rumor" if RUMOR.search(title) else "official", "body": plain(main_)}
        acc.append(x); have.add(pid); n += 1
        time.sleep(0.3)
    acc.sort(key=lambda x: x["d"])
    io.open(SRC, "w", encoding="utf-8", newline="\n").write(json.dumps(acc, ensure_ascii=False, indent=1))
    print(f"PTT 轉會：新增 {n} 則，累積 {len(acc)} 則（韓網 {sum(x['src'] == '韓網' for x in acc)}）")


if __name__ == "__main__":
    main()
