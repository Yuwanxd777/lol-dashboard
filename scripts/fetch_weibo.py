"""fetch_weibo.py：定期看三個微博爆料帳號（使用者 2026-11-27「這個人說的也定期去看」），新貼文放進 transfers_ptt_src.json 等每小時複查員整理。

帳號（index.html 的 WB_NM 也要同步）：尧阿尧 2600241232（LPL 經紀人）、恋恋红茶_244 2266865584、丶涵艺 1992350413。

讀法：微博不登入看不到內容 ⇒ 用 weibo_login.bat 建的專用 Chrome 設定檔（WB_PROFILE，不是使用者平常那個），
  使用者在跳出來的視窗登入一次、關掉；這支用同一個設定檔以無頭模式開 weibo.com/u/<uid>，在頁面裡呼叫網站自己的
  /ajax/statuses/mymblog（跟捲動頁面時網頁自己做的一樣），長文再打 /ajax/statuses/longtext。
  沒有這個資料夾、或登入失效 ⇒ 印一行提醒就結束（不影響其他步驟）。

寫進去的條目：id＝wb-<mblogid>、src「微博」、url＝原文、body＝原文（簡體；轉發的另附被轉的內文）、沒有 zh_fix
  ⇒ fetch_transfers 先不上架，transfers_hourly 的複查員照 REVIEW_BRIEF 重寫成繁中（閒聊就 hide）。
  只收 START 之後、含轉會關鍵字的貼文；看過的 mblogid 記在 transfers_weibo_state.json（本機檔），不重複收。
用法：python scripts/fetch_weibo.py          （transfers_hourly.py main 每班都叫）
      python scripts/fetch_weibo.py --check  只看登入狀態與每個帳號最新一則，不寫檔
"""
import datetime
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "transfers_ptt_src.json")
STATE = os.path.join(ROOT, "transfers_weibo_state.json")
WB_PROFILE = os.path.join(os.environ.get("LOCALAPPDATA") or ROOT, "lol_dashboard_wb_profile")
ACCOUNTS = {"2600241232": "尧阿尧", "2266865584": "恋恋红茶", "1992350413": "涵艺"}
START = "2026-11-27 12:00"   # 這之前的貼文 11-27 已在對話端整理過
KEY = re.compile(r"转会|轉會|签约|簽約|签字|签了|落笔|合同|合约|续约|离队|加盟|加入|报价|解约|官宣|二选一|试训|首发|替补|教练|阵容|经纪|意向|接触|沟通|谈|🍉|瓜|退役|复出|韩援|AD|打野|中单|上单|辅助")

JS = r"""async (uid) => {
  const out = [];
  const r = await fetch('/ajax/statuses/mymblog?uid=' + uid + '&page=1&feature=0', {credentials: 'include'});
  let j; try { j = await r.json(); } catch (e) { return {err: 'not json ' + r.status}; }
  if (!j || j.ok !== 1) return {err: 'ok=' + (j && j.ok)};
  for (const m of ((j.data || {}).list || [])) {
    let x = m.text_raw || '';
    if (m.isLongText) { try { const lt = await (await fetch('/ajax/statuses/longtext?id=' + m.mblogid, {credentials: 'include'})).json(); x = (lt.data && lt.data.longTextContent) || x; } catch (e) {} }
    out.push({id: m.mblogid, t: m.created_at, x: x, top: m.isTop ? 1 : 0,
              rt: m.retweeted_status ? ((m.retweeted_status.user || {}).screen_name || '') + '：' + (m.retweeted_status.text_raw || '') : ''});
  }
  return {list: out};
}"""


def tw_time(s):
    """微博的 created_at（Thu Nov 27 11:33:00 +0800 2026）→ 台灣時間字串"""
    d = datetime.datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y")
    return d.astimezone(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    check = "--check" in sys.argv
    if not os.path.isdir(WB_PROFILE):
        print("微博：還沒登入過（跑專案根目錄的 weibo_login.bat 登入一次），略過")
        return
    from playwright.sync_api import sync_playwright
    state = json.load(io.open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {"seen": []}
    seen = set(state.get("seen") or [])
    got, bad = [], []
    with sync_playwright() as p:
        kw = dict(channel="chrome", headless=True, locale="zh-CN", viewport={"width": 1300, "height": 1600})
        try:
            cx = p.chromium.launch_persistent_context(WB_PROFILE, **kw)
        except Exception as e:   # 登入視窗還開著 ⇒ 設定檔被鎖住
            print(f"微博：專用 Chrome 設定檔開不起來（weibo_login.bat 的視窗還開著？），這班略過｜{type(e).__name__}")
            return
        pg = cx.pages[0] if cx.pages else cx.new_page()
        ua = pg.evaluate("()=>navigator.userAgent")
        if "HeadlessChrome" in ua:   # 無頭模式自報 HeadlessChrome ⇒ 報成跟登入時同一個 Chrome
            cx.close()
            cx = p.chromium.launch_persistent_context(WB_PROFILE, user_agent=ua.replace("HeadlessChrome", "Chrome"), **kw)
            pg = cx.pages[0] if cx.pages else cx.new_page()
        for uid, nm in ACCOUNTS.items():
            try:
                pg.goto("https://weibo.com/u/" + uid, timeout=60000)
                pg.wait_for_timeout(2500)
                if "passport.weibo.com" in pg.url or "login" in pg.url:
                    bad.append(f"{nm}：登入失效（重跑 weibo_login.bat）")
                    break
                r = pg.evaluate(JS, uid)
                if r.get("err"):
                    bad.append(f"{nm}：讀不到（{r['err']}）")
                    continue
                L = r.get("list") or []
                if check:
                    print(f"{nm}：{len(L)} 則，最新 {tw_time(L[0]['t']) if L else '-'}｜{(L[0]['x'] if L else '')[:60]}")
                    continue
                for m in L:
                    d = tw_time(m["t"])
                    if m["id"] in seen or d < START:
                        continue
                    seen.add(m["id"])
                    if not KEY.search(m["x"] + " " + m["rt"]):
                        continue
                    got.append({"id": "wb-" + m["id"], "d": d, "title": f"[微博] {nm}",
                                "body": m["x"] + (("\n\n（轉發）" + m["rt"]) if m["rt"] else ""),
                                "src": "微博", "url": f"https://weibo.com/{uid}/{m['id']}", "st": "rumor"})
            except Exception as e:
                bad.append(f"{nm}：{type(e).__name__} {str(e)[:80]}")
        cx.close()
    if check:
        for z in bad:
            print("⚠ " + z)
        return
    if got:
        data = json.load(io.open(SRC, encoding="utf-8"))
        have = {x["id"] for x in data}
        new = [x for x in got if x["id"] not in have]
        data += new
        tmp = SRC + ".tmp"
        io.open(tmp, "w", encoding="utf-8", newline="\n").write(json.dumps(data, ensure_ascii=False, indent=1))
        os.replace(tmp, SRC)
        got = new
    state["seen"] = sorted(seen)[-3000:]
    state["at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    io.open(STATE, "w", encoding="utf-8").write(json.dumps(state, ensure_ascii=False))
    print(f"微博：新收 {len(got)} 則待複查" + ("（" + "、".join(x["title"][5:] + " " + x["d"][5:] for x in got[:6]) + "）" if got else "")
          + ("｜⚠ " + "；".join(bad) if bad else ""))


if __name__ == "__main__":
    main()
