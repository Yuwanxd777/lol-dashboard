# -*- coding: utf-8 -*-
"""把轉會分頁「實際顯示出來的樣子」倒成文字檔，給每小時複查用（scripts/transfers_hourly.py 的 review 步驟）。

  python scripts/transfers_dump.py            → transfers_review_dump.txt（專案根目錄，不發布）

內容：①消息每一列＝日期｜狀態｜賽區｜原隊｜新隊｜內文（[上路] 這種是路線圖、[教] 是教練圖、{隊名} 是有連結的隊）｜連結；
      ②陣容表每一隊每一格（名字後面的記號：new 新加入、rs 續約、pm 升職、exp 合約到期、gone 已宣布離隊、out 可能轉會、rumor 傳聞、沒記號＝續留）。
無頭瀏覽器開本機 index.html（自己起一個暫時的 http.server），不開使用者的 Chrome。
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


def main():
    from playwright.sync_api import sync_playwright
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"], cwd=ROOT,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            errs = []
            pg = b.new_page(viewport={"width": 1700, "height": 900})
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.add_init_script("localStorage.setItem('lang','zh')")
            pg.goto(f"http://127.0.0.1:{PORT}/index.html?view=%E8%BD%89%E6%9C%83", wait_until="load", timeout=240000)
            pg.wait_for_function("document.querySelectorAll('.tbRow').length>5", timeout=240000)
            pg.wait_for_timeout(4000)
            board = pg.evaluate(BOARD)
            pg.locator('.sqLaneBtn[data-k="trMode"][data-v="news"]').click()
            pg.wait_for_timeout(2000)
            news = pg.evaluate(NEWS)
            b.close()
        with io.open(OUT, "w", encoding="utf-8") as f:
            f.write("【消息】日期｜狀態｜賽區｜原隊｜新隊｜內文｜連結\n" + "\n".join(news) + "\n\n【陣容表】\n" + "\n".join(board) + "\n")
        print(f"transfers_review_dump.txt：消息 {len(news)} 列、陣容表 {sum(1 for x in board if not x.startswith('=='))} 隊；JS 錯誤 {errs[:2]}")
    finally:
        srv.kill()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
