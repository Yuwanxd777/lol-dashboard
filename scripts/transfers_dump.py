# -*- coding: utf-8 -*-
"""把轉會分頁「實際顯示出來的樣子」倒成文字檔，給每小時複查用（scripts/transfers_hourly.py 的 review 步驟）。

  python scripts/transfers_dump.py            → transfers_review_dump.txt（專案根目錄，不發布）

內容：①消息每一列＝日期｜狀態｜賽區｜原隊｜新隊｜內文（[上路] 這種是路線圖、[教] 是教練圖、{隊名} 是有連結的隊）｜連結；
      ②陣容表每一隊每一格（名字後面的記號：new 新加入、rs 續約、pm 升職、exp 合約到期、gone 已宣布離隊、out 可能轉會、rumor 傳聞、沒記號＝續留）。
無頭瀏覽器開本機 index.html（自己起一個暫時的 http.server），不開使用者的 Chrome。
擷取前一定先 settle()（停掉頁面的背景預熱，見該函式）；改了這支跑 python scripts/transfers_dump_test.py。
"""
import io
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "transfers_review_dump.txt")
PORT = 8866

NEWS = """()=>{ let day=''; const out=[]; [...document.querySelector('.trList').children].forEach(x=>{
  if(x.classList.contains('trDay')){day=x.innerText;return;} if(!x.classList.contains('trRow'))return;
  const g=s=>x.querySelector(s)?x.querySelector(s).innerText.split(String.fromCharCode(10)).join(','):'';
  const tx=x.querySelector('.trTxt').innerHTML.replace(/<img[^>]*class="trRole"[^>]*title="([^"]*)"[^>]*>/g,'[$1]').replace(/<img[^>]*class="trCoach"[^>]*>/g,'[教]')
    .replace(/<a [^>]*class="trAb"[^>]*>([^<]*)<[/]a>/g,'{$1}').replace(/<br>/g,' ⏎ ').replace(/<[^>]+>/g,'');
  out.push([day, x.querySelector('.trSt').innerText, g('.trRgC').replace(/,/g,''), g('.trFrom')||g('.trSpan'), g('.trTo'), tx,
    [...x.querySelectorAll('.trLks a,.trLk1 a')].map(a=>a.innerText.replace(' ↗','')).filter((v,i,a)=>a.indexOf(v)===i).join('+')].join(' | ')); });
  return out; }"""
BOARD = """()=>{ const M={tbNew:'new',tbRs:'rs',tbPm:'pm',tbExp:'exp',tbGone:'gone',tbOut:'out',tbY:'rumor'}; const out=[];
  [...document.querySelectorAll('.tbBoard>.tbLg,.tbBoard>.tbRow')].forEach(e=>{ if(e.classList.contains('tbLg')){ out.push('== '+e.querySelector('b').textContent); return; }
    out.push(e.querySelector('.tbTeam').innerText.split(String.fromCharCode(10)).join('')+' : '+[...e.querySelectorAll('.tbCell[data-r]')].map(c=>c.dataset.r+'='+([...c.querySelectorAll('.tbN')].map(n=>{
      const k=[...n.classList].map(x=>M[x]).filter(Boolean); return n.textContent+(k.length?'('+(k.includes('gone')?'gone':k[0])+')':''); }).join('/')||'–')).join('  ')
      +'  評分='+(e.querySelector('.tbRate')||{}).textContent); });
  return out; }"""


SETTLE_MS = 30000   # 等背景預熱收尾最多幾毫秒（平常 1 秒內；逾時就報錯，不倒半套）


def settle(pg, timeout=None):
    """停掉頁面的背景預熱，等它真的收尾。擷取畫面之前一定要先叫。

    index.html 開站約 1.5 秒後會「預熱」別的分頁（_warmViews）：先在真的 <main id="main"> 後面插一份
    靜態複製品（data-warm-cover）蓋住畫面，再把真的 main 設成 visibility:hidden、輪流 render 別的分頁。
    那幾秒裡 ①同一顆按鈕在頁面上有 2 顆 ⇒ locator.click() 丟 strict mode violation
            ②.tbBoard 有 2 份、藏起來那份的 innerText 全是空字串 ⇒ 陣容表倒出 128 列、前 64 列沒有隊名
    2026-11-21 22:22 之後這支每次都撞上（11-22 01:13 複查記的「跑不完」）。跟按鈕有幾顆無關，是時機。
    做法同 audit_text_overflow.py／audit_mobile.py：scheduleWarmup(1e9) 讓進行中的那一輪作廢，
    再等 _warming 落下、複製品拿掉（finish() 會把目前分頁 render 回來）。"""
    pg.evaluate("() => { if (typeof scheduleWarmup === 'function') scheduleWarmup(1e9); }")
    try:
        pg.wait_for_function("() => !window._warming && !document.querySelector('[data-warm-cover]')",
                             timeout=SETTLE_MS if timeout is None else timeout)
    except Exception as e:
        raise RuntimeError("頁面的背景預熱沒有收尾（_warming 還是 true 或複製品還在），這時擷取會是兩份或空白，不倒：%s"
                           % str(e).splitlines()[0])
    pg.wait_for_timeout(300)


def check_board(board):
    """陣容表每一列都要有隊名。沒有＝擷取時 main 被藏著（innerText 是空字串），整份不可信 ⇒ 報錯不寫檔。"""
    bad = [x for x in board if not x.startswith("==") and not x.split(" : ", 1)[0].strip()]
    if bad:
        raise RuntimeError("陣容表有 %d／%d 列沒有隊名（擷取時畫面被藏著？），不寫檔。第一列：%s"
                           % (len(bad), sum(1 for x in board if not x.startswith("==")), bad[0][:80]))


def dump(pg, timeout=None):
    """已經開在轉會分頁（陣容表模式）的頁面 → (消息每一列, 陣容表每一列)。"""
    settle(pg, timeout)
    board = pg.evaluate(BOARD)
    check_board(board)
    pg.locator('.sqLaneBtn[data-k="trMode"][data-v="news"]').click()
    pg.wait_for_timeout(2000)
    settle(pg, timeout)
    news = pg.evaluate(NEWS)
    return news, board


def open_page(browser, port, errs=None, init=None):
    pg = browser.new_page(viewport={"width": 1700, "height": 900})
    if errs is not None:
        pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.add_init_script("localStorage.setItem('lang','zh')")
    if init:
        pg.add_init_script(init)
    pg.goto(f"http://127.0.0.1:{port}/index.html?view=%E8%BD%89%E6%9C%83", wait_until="load", timeout=240000)
    pg.wait_for_function("document.querySelectorAll('.tbRow').length>5", timeout=240000)
    return pg


def main(out=None, port=None):
    from playwright.sync_api import sync_playwright
    out = OUT if out is None else out
    port = PORT if port is None else port
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"], cwd=ROOT,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            errs = []
            pg = open_page(b, port, errs)
            pg.wait_for_timeout(4000)
            news, board = dump(pg)
            b.close()
        with io.open(out, "w", encoding="utf-8") as f:
            f.write("【消息】日期｜狀態｜賽區｜原隊｜新隊｜內文｜連結\n" + "\n".join(news) + "\n\n【陣容表】\n" + "\n".join(board) + "\n")
        print(f"{os.path.basename(out)}：消息 {len(news)} 列、陣容表 {sum(1 for x in board if not x.startswith('=='))} 隊；JS 錯誤 {errs[:2]}")
    finally:
        srv.kill()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
