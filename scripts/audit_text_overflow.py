# -*- coding: utf-8 -*-
"""文字溢出稽核（使用者 2026-09-05 回報「英文介面有些文字長度超出框」後建立）。

用法：python scripts/audit_text_overflow.py [en|zh|cn]（預設 en）
全站逐分頁＋說明浮層＋詳情頁＋圖鑑各分區，兩種視窗寬度各掃一遍。加語言就能比對
「改英文有沒有把中文弄壞」。

用 **Range 量真正畫出來的文字邊界**，不是只看 scrollWidth——
英文長字多半是 overflow:visible 的「疊出去」，不會被裁，scrollWidth 看不到。

三種判準：
  ① 文字比框寬：文字 Range 右緣超出元素的內容盒（overflow 不論可見與否）
  ② 被裁：scrollWidth > clientWidth 且該元素會裁切
  ③ 超出視窗：文字右緣超過視窗

⚠ 兩個踩過的坑（都寫在腳本裡防重犯）：
  ‧ 掃之前一定要 `scheduleWarmup(1e9)` 停掉背景預熱——預熱時 #main 是 visibility:hidden，
    掃描器會把整頁當隱藏跳過，掃出 0 筆假綠。
  ‧ 一定要放正控制（clip 版＋visible 版各一），掃不到就代表掃描器壞了。
"""
import io, os, subprocess, sys, time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANG = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in ("en", "zh", "cn") else "en"
PORT = 8773
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"], cwd=ROOT,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.5)

SCAN = """() => {
  const out = [], seen = new Set();
  const textRect = el => {                 // 只量這個元素**自己的**文字（不含子元素）
    let best = null;
    for (const n of el.childNodes) {
      if (n.nodeType !== 3 || !n.textContent.trim()) continue;
      const rg = document.createRange(); rg.selectNodeContents(n);
      const r = rg.getBoundingClientRect();
      if (r.width < 1) continue;
      best = best ? { left: Math.min(best.left, r.left), right: Math.max(best.right, r.right),
                      top: Math.min(best.top, r.top), bottom: Math.max(best.bottom, r.bottom) } : r;
    }
    return best;
  };
  document.querySelectorAll('#main *, header *, nav *').forEach(el => {
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (!own) return;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) return;
    const box = el.getBoundingClientRect();
    if (box.width < 3 || box.height < 3) return;
    const tr = textRect(el);
    if (!tr) return;
    const txt = (el.textContent || '').trim().slice(0, 60);
    // ⚠ 單位：getComputedStyle 給的是**版面 px**，getBoundingClientRect 是**視覺 px**
    // （本站有 _zoomF 縮放，實測 1920 寬時 0.75）。不換算的話每個有 padding 的元素
    // 都會被誤判成溢出（2026-09-05 踩過：所有分頁籤固定報 11.1px）。
    const Z = window._zoomF || 1;
    const padR = (parseFloat(cs.paddingRight) || 0) * Z, padL = (parseFloat(cs.paddingLeft) || 0) * Z;
    const bwR = (parseFloat(cs.borderRightWidth) || 0) * Z, bwL = (parseFloat(cs.borderLeftWidth) || 0) * Z;
    const contentRight = box.right - bwR - padR;
    const contentLeft = box.left + bwL + padL;
    let kind = null, over = 0;
    if (tr.right - contentRight > 1.5) { kind = '字比框寬'; over = tr.right - contentRight; }
    else if (contentLeft - tr.left > 1.5) { kind = '字往左溢'; over = contentLeft - tr.left; }
    else if (el.scrollWidth > el.clientWidth + 1 && cs.overflowX !== 'visible') {
      kind = '被裁'; over = el.scrollWidth - el.clientWidth;
    } else if (tr.right > document.documentElement.clientWidth + 1) {
      kind = '超出視窗'; over = tr.right - document.documentElement.clientWidth;
    }
    if (!kind || over < 2) return;
    const key = kind + '|' + el.tagName + '|' + (el.className || '') + '|' + txt.slice(0, 30);
    if (seen.has(key)) return;
    seen.add(key);
    out.push({ kind, over: +over.toFixed(1), tag: el.tagName,
               cls: String(el.className || '').slice(0, 34), txt });
  });
  return out.sort((a, b) => b.over - a.over);
}"""

PC = """() => {
  const m = document.getElementById('main');
  const a = document.createElement('div'); a.id = '__pc1';
  a.style.cssText = 'width:60px;overflow:hidden;white-space:nowrap;text-overflow:clip';
  a.textContent = 'PCLIP overflowing text that must be detected';
  const b = document.createElement('div'); b.id = '__pc2';
  b.style.cssText = 'width:60px;overflow:visible;white-space:nowrap';
  b.textContent = 'PVIS overflowing text that must be detected';
  m.appendChild(a); m.appendChild(b);
}"""

TABS = ["總覽", "英雄", "選手", "戰隊", "近況", "比賽BP", "模擬BP", "英雄Tier", "積分", "圖鑑"]
code = 1
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        total = 0
        for W, H in ((1920, 1080), (1366, 768)):
            pg = br.new_page(viewport={"width": W, "height": H})
            pg.add_init_script("localStorage.setItem('lang',%r)" % LANG)
            pg.goto("http://127.0.0.1:%d/index.html?y=2026" % PORT, wait_until="load", timeout=120000)
            pg.wait_for_function("() => typeof GAMES !== 'undefined' && GAMES.length > 0", timeout=60000)
            pg.wait_for_timeout(2000)
            pg.evaluate("() => scheduleWarmup(1e9)")     # 見檔頭：不停預熱會掃出 0 筆假綠
            pg.wait_for_timeout(300)
            tab1 = pg.evaluate("() => ((document.querySelector('nav .tab')||{}).textContent||'').trim()")
            print("\n═════ %dx%d（首個分頁籤=%r）═════" % (W, H, tab1))
            pg.evaluate(PC)
            pc = pg.evaluate(SCAN)
            g1 = any("PCLIP" in x["txt"] for x in pc)
            g2 = any("PVIS" in x["txt"] for x in pc)
            print("   正控制：裁切版 %s／可見溢出版 %s" % ("✓" if g1 else "✗", "✓" if g2 else "✗"))
            if not (g1 and g2):
                print("   ⇒ 掃描器有問題，下面的結果不可信")
            pg.evaluate("() => ['__pc1','__pc2'].forEach(i => { const e = document.getElementById(i); if (e) e.remove(); })")
            def scan(label):
                rs = pg.evaluate(SCAN)
                if rs:
                    print("\n【%s】%d 筆" % (label, len(rs)))
                    for x in rs[:8]:
                        print("   %-6s 超出%6.1fpx  <%s class=%s>  %r"
                              % (x["kind"], x["over"], x["tag"].lower(), x["cls"], x["txt"]))
                return len(rs)

            for tb in TABS:
                ok = pg.evaluate("""(t) => { const el = [...document.querySelectorAll('nav .tab')]
                    .find(e => e.dataset.view === t); if (!el) return false; el.click(); return true; }""", tb)
                if not ok:
                    continue
                pg.wait_for_timeout(2200)
                total += scan(tb)
                # 每頁再開「說明」浮層掃一次（英文說明最長）
                if pg.evaluate("() => { const b = document.getElementById('fHelp'); if (!b) return false; b.click(); return true; }"):
                    pg.wait_for_timeout(800)
                    total += scan(tb + "／說明浮層")
                    pg.evaluate("() => { const b = document.getElementById('fHelp'); if (b) b.click(); }")
                    pg.wait_for_timeout(300)
                # 子頁面：詳情頁、每日戰況、圖鑑各分區（英文最容易爆的地方）
                if tb == "英雄":
                    if pg.evaluate("() => { const a = document.querySelector('#main table tbody tr td:nth-child(2)');"
                                   " if (!a) return false; a.click(); return true; }"):
                        pg.wait_for_timeout(2800)
                        total += scan("英雄詳情")
                if tb == "選手":
                    if pg.evaluate("() => { const a = document.querySelector('#main table tbody tr td:nth-child(2)');"
                                   " if (!a) return false; a.click(); return true; }"):
                        pg.wait_for_timeout(2800)
                        total += scan("選手詳情")
                if tb == "積分":
                    pg.evaluate("() => { V.rankView = 'daily'; render(); }")
                    pg.wait_for_timeout(3200)
                    total += scan("積分／每日戰況")
                    pg.evaluate("() => { V.rankView = 'ladder'; render(); }")
                    pg.wait_for_timeout(1500)
                if tb == "圖鑑":
                    for sec in ("英雄", "道具", "符文", "物件", "賽事", "刷野速度", "版本"):
                        pg.evaluate("(s) => { V.dexSec = s; V.dexDetail = null; render(); }", sec)
                        pg.wait_for_timeout(2400)
                        total += scan("圖鑑／" + sec)
            pg.close()
        br.close()
        print("\n合計 %d 筆" % total)
        code = 0
finally:
    srv.kill()
sys.exit(code)
