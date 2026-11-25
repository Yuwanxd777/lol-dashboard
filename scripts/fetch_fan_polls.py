"""fetch_fan_polls.py：使用者自己發的「2027 T1 新陣容可以走多遠？」投票（Threads＋YouTube 社群貼文），兩邊票數合在一起給轉會陣容表的 ✔ 用。

使用者 2026-11-25：「去看我的 Threads與YT … 通常每一隊陣容確認後我都會發類似的文章 2027 T1 新陣容可以走多遠？#LCK2027
  Zeus / Oner / Faker / Peyz / Keria / Roach … 幫我每天凌晨12點更新一次 把兩邊數據合在一起 點擊綠色勾勾的時候會顯示 有資料的綠色勾勾變成粗體」

資料怎麼來（都用無頭瀏覽器、不登入、不碰使用者的 Chrome）：
  Threads  個人頁（未登入只給最新 7 篇上下）找貼文 → 單篇貼文頁的內嵌 JSON 有投票每個選項的實際票數（tallies），進行中的也有
  YouTube  社群貼文頁的 ytInitialData 有選項與總票數；**各選項的票數要登入並投過票才看得到**，未登入拿不到 ⇒ 只有總票數
           （登入後 YouTube 會多給 voteRatio 之類的欄位，yt_choice() 認得；目前沒有登入的管道，那一段沒有實測過）
累積在 transfers_polls_src.json（本機檔，不進 git）；fetch_transfers.py 呼叫 build() 把結果放進 transfers.js 的 polls。

用法（transfers_hourly.py 的 main 每班都叫一次，不帶參數）：
  python scripts/fetch_fan_polls.py           找新貼文；今天第一次跑（＝凌晨 00:10 那班）順便把所有貼文的票數重抓一遍
  python scripts/fetch_fan_polls.py --full    不管今天跑過沒有，全部重抓
  python scripts/fetch_fan_polls.py --light   只找新貼文
  python scripts/fetch_fan_polls.py --add-th https://www.threads.com/@yuwanxd/post/XXXX [...]
                                              手動補 Threads 貼文（個人頁未登入只看得到最新幾篇，更早的要給網址）
為什麼每班都找新貼文：Threads 個人頁未登入只露出最新 7 篇左右，轉會期一天發十幾篇，只在半夜看一次會漏掉白天發的那篇。
票數則照使用者說的一天更新一次；Threads 的投票 24 小時截止，截止後抓過一次就不再重抓。
"""
import datetime
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "transfers_polls_src.json")
TH_USER = "yuwanxd"
TH_HOME = "https://www.threads.com/@" + TH_USER
YT_HOME = "https://www.youtube.com/@yuwanxd/posts"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
# 標題：「2027 T1 新陣容可以走多遠？」——年份＋隊伍縮寫＋「新陣容」；後半句不寫死（使用者說「類似這樣」）
RE_T = re.compile(r"^\s*(20\d\d)\s*([A-Za-z0-9][A-Za-z0-9 .\-]{0,23}?)\s*新陣容")


def load():
    try:
        d = json.load(io.open(SRC, encoding="utf-8"))
        if isinstance(d, dict) and isinstance(d.get("posts"), dict):
            return d
    except Exception:
        pass
    return {"full": "", "posts": {}}


def save(d):
    tmp = SRC + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1))
    os.replace(tmp, SRC)


def walk(o, key, acc):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key:
                acc.append(v)
            walk(v, key, acc)
    elif isinstance(o, list):
        for v in o:
            walk(v, key, acc)
    return acc


def norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def head_of(text):
    """貼文內文 → (年, 隊伍, 問句, 陣容那一行)；不是這種貼文回 None。主題標籤（#LCK2027）不算在問句裡。"""
    ls = [norm(re.sub(r"#\S+", "", z)) for z in str(text or "").split("\n")]
    ls = [z for z in ls if z]
    if not ls:
        return None
    m = RE_T.match(ls[0])
    if not m:
        return None
    return int(m.group(1)), norm(m.group(2)).upper(), ls[0], (ls[1] if len(ls) > 1 else "")


def num(s):
    """「4427 票」「1.2 萬票」「4.4K votes」→ 整數（帶單位的是約數）"""
    s = str(s or "").replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(萬|万|億|K|M)?", s, re.I)
    if not m:
        return None
    v = float(m.group(1)) * {"萬": 1e4, "万": 1e4, "億": 1e8, "K": 1e3, "M": 1e6}.get((m.group(2) or "").upper(), 1)
    return int(round(v))


# ───────── YouTube ─────────
def yt_choice(c, total):
    """一個選項 → [文字, 票數或 None]。未登入只有文字；登入並投過票的話 YouTube 會多給比例（這一段沒有實測過，欄位名照公開的格式寫）"""
    txt = norm("".join(r.get("text", "") for r in (c.get("text") or {}).get("runs", [])) or (c.get("text") or {}).get("simpleText"))
    v = None
    if c.get("numVotes") is not None:
        v = num(c.get("numVotes"))
    else:
        r = c.get("voteRatio")
        if r is None:
            r = c.get("voteRatioIfSelected") if c.get("selected") else c.get("voteRatioIfNotSelected")
        if r is not None and total:
            v = int(round(float(r) * total))
    return [txt, v]


def yt_parse(data):
    """ytInitialData → [{id, text, n, o, lk}]（只留有投票的貼文）"""
    out = []
    for p in walk(data, "backstagePostRenderer", []):
        poll = (p.get("backstageAttachment") or {}).get("pollRenderer")
        if not poll or not p.get("postId"):
            continue
        text = "".join(r.get("text", "") for r in (p.get("contentText") or {}).get("runs", []))
        n = num((poll.get("totalVotes") or {}).get("simpleText"))
        out.append({"id": p["postId"], "text": text, "n": n, "o": [yt_choice(c, n) for c in poll.get("choices") or []],
                    "lk": num((p.get("voteCount") or {}).get("simpleText"))})
    return out


def yt_fetch(pg, url):
    pg.goto(url, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_function("()=>!!window.ytInitialData", timeout=30000)
    return yt_parse(json.loads(pg.evaluate("()=>JSON.stringify(window.ytInitialData)")))


# ───────── Threads ─────────
def th_posts(strs):
    """頁面內嵌的 JSON／graphql 回應 → {貼文代碼: post 物件}（只留使用者自己的）。
    個人頁的貼文在 thread_items[].post，單篇貼文頁的主貼文在 data.media ⇒ 不認路徑，凡是「有 code、user 是本人」的物件都收；
    同一篇出現兩次時留有投票票數的那一份。"""
    out = {}

    def rec(o):
        if isinstance(o, dict):
            if isinstance(o.get("code"), str) and isinstance(o.get("user"), dict) and (o["user"].get("username") or "").lower() == TH_USER and "caption" in o:
                if o["code"] not in out or (walk(o, "tallies", []) and not walk(out[o["code"]], "tallies", [])):
                    out[o["code"]] = o
            for v in o.values():
                rec(v)
        elif isinstance(o, list):
            for v in o:
                rec(v)
    for s in strs:
        try:
            rec(json.loads(s))
        except Exception:
            continue
    return out


def th_page(pg, url, scroll=0):
    got = []

    def on_resp(r):
        if "graphql" in r.url:
            try:
                s = r.text()
                if TH_USER in s:
                    got.append(s)
            except Exception:
                pass
    pg.on("response", on_resp)
    try:
        pg.goto(url, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(6000)
        for _ in range(scroll):
            pg.mouse.wheel(0, 4000)
            pg.wait_for_timeout(1300)
        h = pg.content()
    finally:
        pg.remove_listener("response", on_resp)
    return th_posts([m.group(1) for m in re.finditer(r'<script type="application/json"[^>]*>(.*?)</script>', h, re.S) if TH_USER in m.group(1)] + got)


def th_stat(po):
    """post 物件 → 投票與互動數；沒有投票回 None"""
    polls = [x for x in walk(po, "poll", []) if isinstance(x, dict) and x.get("tallies")]
    if not polls:
        return None
    pl = polls[0]
    o = [[norm(t.get("text")), int(t.get("count") or 0)] for t in pl["tallies"]]
    tpa = po.get("text_post_app_info") or {}
    return {"code": po["code"], "t": po.get("taken_at"), "n": sum(v for _, v in o), "o": o, "fin": bool(pl.get("finished")), "end": pl.get("expires_at"),
            "lk": po.get("like_count"), "rp": tpa.get("direct_reply_count")}


def code_of(u):
    m = re.search(r"/post/([A-Za-z0-9_\-]+)", u)
    return m.group(1) if m else u.strip()


def main():
    from playwright.sync_api import sync_playwright
    sys.stdout.reconfigure(encoding="utf-8")
    argv = sys.argv[1:]
    store = load()
    posts = store["posts"]
    now = datetime.datetime.now()
    stamp, today = now.strftime("%Y-%m-%d %H:%M"), now.strftime("%Y-%m-%d")
    full = "--full" in argv or ("--light" not in argv and store.get("full") != today)
    add = [code_of(a) for a in argv[argv.index("--add-th") + 1:]] if "--add-th" in argv else []
    logs, bad = [], []

    def entry(hd):
        y, team, q, ln = hd
        e = posts.setdefault(f"{y}|{team}", {"y": y, "team": team})
        e["q"] = q
        if ln:
            e["ln"] = ln
        return e

    def put(e, side, new):
        """票數不會變少：新抓到的比舊的少一半以上＝頁面沒載完整，留舊的"""
        old = e.get(side) or {}
        if old.get("n") and (new.get("n") or 0) < old["n"] * 0.5:
            bad.append(f"{e['team']} {side} 票數 {old['n']}→{new.get('n')}（不採用）")
            return
        if side == "yt" and old.get("o") and any(v is not None for _, v in old["o"]) and all(v is None for _, v in new.get("o") or []):
            new["o"] = old["o"]   # 這次沒拿到各選項票數（登入失效之類）⇒ 留上次的，不退回空白
        new["at"] = stamp
        e[side] = new

    with sync_playwright() as p:
        b = p.chromium.launch()
        cx = b.new_context(user_agent=UA, locale="zh-TW", viewport={"width": 1300, "height": 2000})
        pg = cx.new_page()
        # ① YouTube 貼文列表（一頁）：新貼文；全部重抓時列表上有的順便更新
        seen_yt = set()
        try:
            for y in yt_fetch(pg, YT_HOME):
                hd = head_of(y["text"])
                if not hd:
                    continue
                e = entry(hd)
                seen_yt.add(y["id"])
                if full or not e.get("yt"):
                    if not e.get("yt"):
                        logs.append(f"YT 新貼文 {e['team']}")
                    put(e, "yt", {k: y[k] for k in ("id", "n", "o", "lk")})
        except Exception as ex:
            bad.append(f"YT 列表失敗：{type(ex).__name__} {str(ex)[:80]}")
        # ② Threads 個人頁：新貼文的代碼
        todo = {}
        try:
            for code, po in th_page(pg, TH_HOME, scroll=6).items():
                hd = head_of((po.get("caption") or {}).get("text"))
                if hd:
                    e = entry(hd)
                    if not e.get("th"):
                        todo[code] = e
        except Exception as ex:
            bad.append(f"Threads 個人頁失敗：{type(ex).__name__} {str(ex)[:80]}")
        for code in add:
            todo.setdefault(code, None)
        if full:   # 截止後抓過一次的（done）不再重抓
            for e in posts.values():
                th = e.get("th") or {}
                if th.get("code") and not th.get("done"):
                    todo.setdefault(th["code"], e)
        # ③ Threads 單篇貼文頁：各選項票數
        for code, e in todo.items():
            try:
                po = th_page(pg, f"{TH_HOME}/post/{code}").get(code)
                if not po:
                    bad.append(f"Threads {code} 讀不到貼文")
                    continue
                hd = head_of((po.get("caption") or {}).get("text"))
                st = th_stat(po)
                if not hd or not st:
                    bad.append(f"Threads {code} 不是陣容投票貼文")
                    continue
                e = entry(hd)
                if not e.get("th"):
                    logs.append(f"Threads 新貼文 {e['team']}")
                if st["fin"]:
                    st["done"] = 1
                put(e, "th", st)
            except Exception as ex:
                bad.append(f"Threads {code} 失敗：{type(ex).__name__} {str(ex)[:80]}")
        # ④ 全部重抓：不在列表第一頁的 YouTube 貼文逐篇開
        if full:
            for e in posts.values():
                yt = e.get("yt") or {}
                if not yt.get("id") or yt["id"] in seen_yt:
                    continue
                try:
                    r = [y for y in yt_fetch(pg, "https://www.youtube.com/post/" + yt["id"]) if y["id"] == yt["id"]]
                    if r:
                        put(e, "yt", {k: r[0][k] for k in ("id", "n", "o", "lk")})
                    else:
                        bad.append(f"YT {e['team']} 單篇頁讀不到")
                except Exception as ex:
                    bad.append(f"YT {e['team']} 失敗：{type(ex).__name__} {str(ex)[:80]}")
        b.close()
    if full and not any("列表失敗" in z or "個人頁失敗" in z for z in bad):
        store["full"] = today   # 兩邊入口都有開成功才算今天更新過；失敗的話下一班再整套重試
        store["at"] = stamp
    save(store)
    for z in logs + bad:
        print(("⚠ " if z in bad else "") + z)
    miss = [e["team"] + ("缺 Threads" if not e.get("th") else "缺 YT") for e in posts.values() if not e.get("th") or not e.get("yt")]
    print(f"{'全部重抓' if full else '只找新貼文'}：{len(posts)} 隊（" + "、".join(
        f"{e['team']} {((e.get('th') or {}).get('n') or 0) + ((e.get('yt') or {}).get('n') or 0)}" for e in posts.values()) + "）"
        + (f"｜{'、'.join(miss)}" if miss else "") + (f"｜⚠ {len(bad)} 項失敗" if bad else ""))


def build():
    """給 fetch_transfers.py：transfers.js 的 polls＝{隊伍縮寫（大寫）: {y, q, ln, o:[[選項, Threads 票數, YouTube 票數]], th:{u,n,fin}, yt:{u,n}, at}}
    票數是 None＝那一邊沒有這個數字（YouTube 未登入看不到各選項）。同一隊有好幾年的貼文 ⇒ 留最新一年。"""
    out = {}
    for e in sorted(load()["posts"].values(), key=lambda z: z.get("y") or 0):
        th, yt = e.get("th") or {}, e.get("yt") or {}
        tv, yv = dict(map(tuple, th.get("o") or [])), dict(map(tuple, yt.get("o") or []))
        names = list(tv) + [n for n in yv if n not in tv]
        if not names or not e.get("team"):
            continue
        out[e["team"].upper()] = {
            "y": e.get("y"), "q": e.get("q") or "", "ln": e.get("ln") or "", "o": [[n, tv.get(n), yv.get(n)] for n in names],
            "th": {"u": f"{TH_HOME}/post/{th['code']}", "n": th.get("n") or 0, "fin": 1 if th.get("fin") else 0} if th.get("code") else None,
            "yt": {"u": "https://www.youtube.com/post/" + yt["id"], "n": yt.get("n") or 0} if yt.get("id") else None,
            "at": max(th.get("at") or "", yt.get("at") or "")}
    return out


if __name__ == "__main__":
    main()
