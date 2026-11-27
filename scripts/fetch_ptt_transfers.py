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
# 2026-11-20 放寬（使用者「感覺 PTT 的轉會資訊少抓很多篇」「有一篇 Doran 去 DK 的就沒抓」）：原本外絮也要有 MOVE 的字才收，
#   「加盟」「重返」「下一個可能是」「考慮」這些都不在裡面 ⇒ Zeus 有望重返 T1、GenG 打野考慮 Sharvel 和 Kanavi、Lucid 或將加盟 KRX、
#   Doran 下一個可能是 DK、Kanavi 加盟 DK 可能性大 全部漏掉。現在每一則上架前都會先複查（不是轉會消息的會標 hide），所以寧可多抓。
# 2026-11-27 再補（使用者「這篇怎沒抓」）：英文 leaves 不算 ⇒「WBG weibo（Jwei,Moham,Xiaohao leaves）」漏掉；「WBG小明簽字了然後二哈可能轉去別隊」的簽字／轉去也不算。
RUMOR = re.compile(r"乳[摸模]|傳聞|有望|考慮|可能|動向|爆料|韓媒|報導|OBGG|方向已定|即將|將加入|預計|或將|準官宣|青蛙圖|提案|報價|接觸|協商|洽談")   # 媒體報導也算傳聞，只有戰隊官方貼文算官方
MOVE = re.compile(r"加入|加盟|離隊|離開|續約|續留|留隊|簽下|簽約|合約|轉會|自由市場|自由球員|thank ?you|welcome|good ?bye|joins?\b|rejoins?|re-?sign|farewell|official|官宣|回歸|重返|復出|退役|退出|遞補|陣容|名單|解散|維持戰隊|上調|擔任|監督|卸任|head coach|下一個|下家|去向|青蛙圖|提案|報價|簽字|簽了|轉去|轉戰|leav(?:e|es|ing)\b|\bleft\b|departs?\b|parts? ways|released",
                  re.I)
# 閒聊常見的極短標題「隊名 選手」「KRX 的上中下」：前面是戰隊縮寫就收（KRX Duro、KRX的上中下）
TEAMS = (r"T1|GEN|GENG|GenG|HLE|KT|DK|KRX|DRX|NS|BRO|BFX|DNS|BLG|JDG|TES|WBG|IG|AL|LNG|EDG|NIP|WE|TT|OMG|UP|LGD|FNC|G2|KC|MKOI|VIT|SK|TH|GX|NAVI|C9|TL|FLY|SR|LYON|SEN|"
         r"CFO|GAM|TSW|MVK|DCG|GZ|SHG|FUR|LOUD|RED|PNG|VKS|LOS")
SHORT = re.compile(r"^(?:" + TEAMS + r")(?:\s+[A-Za-z0-9]+){1,3}$|^(?:" + TEAMS + r")\s*的?\s*(?:上中下|上中野|上路|打野|中路|下路|輔助|教練)")
SKIP = re.compile(r"網站|造型|經濟|怎|嗎|？|\?|採訪|心路|獎盃|喜帖|團練|籃網|紅牛|預告|直播上說|似乎|詢問|拉扯|擴編|純娛樂|影片|擺爛")
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


YT_RE = re.compile(r"https?://(?:www\.|m\.)?(?:youtube\.com/(?:watch\?v=|shorts/|live/)|youtu\.be/)([\w-]{11})")


def yt_of(h):
    """內文（HTML 或文字）裡第一個 YouTube 影片 → https://youtu.be/影片ID；消息後面的 YT 按鈕（使用者 2026-11-22「傳聞裡面如果有影片 記得附上YT連結」）"""
    m = YT_RE.search(h or "")
    return f"https://youtu.be/{m.group(1)}" if m else ""


def plain(h):
    """內文純文字（只到「※ 發信站」前＝不含推文），陣容表拿來比對 Thank you 文點到的名字"""
    # 作者／看板／標題／時間：只拿掉那幾個 metaline 本身。原本寫成「到下一個 </div></div>」，內文開頭有 YouTube 預覽框（richcontent 兩層 div）時
    #   會把開頭一大段（「來源：影片連結」那幾行）一起吃掉（2026-11-22 Smeb 那篇）
    h = re.sub(r'<div class="article-metaline(?:-right)?">(?:<span[^>]*>[^<]*</span>)*</div>', "", h)
    t = re.sub(r"<[^>]+>", "", h.split(">", 1)[-1])
    t = t.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'").replace("&quot;", '"')
    return re.sub(r"\n\s*\n+", "\n", t).strip()[:4000]


def sus_of(main_html, body):
    """來亂的文（使用者 2026-11-25 貼 M.1795596989.A.36A「這種來亂的文不要收入」：標題寫 T1 X(welcome Zeus)，內文只有一句「宙斯回來了啦」，
    沒有連結也沒有圖，官方根本還沒發）。內文沒有任何連結、扣掉簽名檔只剩不到 30 個字 ⇒ 回傳一句說明，條目加 sus 記號，複查時要先查證。"""
    if re.search(r"https?://", main_html):
        return ""
    ls = [z.strip() for z in (body or "").split("\n")[1:]]
    ls = [z for z in ls if z and not re.match(r"^-+$|^Sent from |^※", z)]
    return "內文沒有連結或圖片，只有一兩句話" if len("".join(ls)) < 30 else ""


def want(title):
    if title.startswith("Re:") or title.startswith("Fw:"):
        return False
    m = re.match(r"\[([^\]]+)\]", title)
    cat = m.group(1).strip() if m else ""
    body_ = re.sub(r"^\[[^\]]+\]\s*", "", title).strip()
    if re.search(r"乳[摸模]", title) or cat == "乳摸":
        return not SKIP.search(title)
    if SKIP.search(title):
        return False
    if cat in ("情報", "外絮", "新聞") and (MOVE.search(title) or RUMOR.search(title)):   # 情報／外絮／新聞：有轉會字眼或傳聞字眼就收
        return True
    if cat == "閒聊" and (MOVE.search(title) or SHORT.search(body_)):
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
    if acc and "--full" not in sys.argv:   # 已累積過 ⇒ 只往回翻到最後一則的前一天（不用每班從起點整個重翻）；--full＝篩選規則改了之後整段重翻
        last = max(int(datetime.datetime.strptime(x["d"], "%Y-%m-%d %H:%M").replace(tzinfo=TZ).timestamp()) for x in acc)
        cut = max(cut, last - 86400)
    for x in acc:   # 舊條目補查一次影片連結（2026-11-22 以前存的內文會漏掉開頭那段，直接從原文 HTML 找）
        if "ytc" not in x and x.get("ptt") and "ptt.cc" in x["ptt"]:
            try:
                y_ = yt_of(get(x["ptt"]).split('<div id="main-content"', 1)[-1].split("※ 發信站", 1)[0])
                if y_ and not x.get("yt"):
                    x["yt"] = y_
                x["ytc"] = 1
                time.sleep(0.3)
            except Exception:
                pass
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
        # 轉貼 Sheep Esports 推文 ⇒ 來源標 Sheep、連結直接給那則推文（使用者 2026-11-20「那應該直接給我 Sheep Esports 的連結」）
        sh = ["https://x.com/Sheep_Esports/status/" + i for i in re.findall(r"Sheep_Esports/status/(\d+)", main_)]
        zh = re.sub(r"^\[[^\]]+\]\s*", "", title).strip()
        x = {"id": pid, "d": datetime.datetime.fromtimestamp(t, TZ).strftime("%Y-%m-%d %H:%M"), "title": title, "zh": zh,
             "src": "韓網" if kr else ("Sheep Esports" if sh else "PTT"), "url": kr[0] if kr else (sh[0] if sh else ptt), "ptt": ptt,
             "st": "rumor" if RUMOR.search(title) else "official", "body": plain(main_), "ytc": 1}
        if yt_of(main_):
            x["yt"] = yt_of(main_)
        if sus_of(main_, x["body"]):
            x["sus"] = sus_of(main_, x["body"])
        acc.append(x); have.add(pid); n += 1
        time.sleep(0.3)
    acc.sort(key=lambda x: x["d"])
    io.open(SRC, "w", encoding="utf-8", newline="\n").write(json.dumps(acc, ensure_ascii=False, indent=1))
    print(f"PTT 轉會：新增 {n} 則，累積 {len(acc)} 則（韓網 {sum(x['src'] == '韓網' for x in acc)}）")


if __name__ == "__main__":
    main()
