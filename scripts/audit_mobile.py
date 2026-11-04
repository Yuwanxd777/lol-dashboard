# -*- coding: utf-8 -*-
"""手機寬度的只讀掃描（線 1，2026-11-04 精進迴圈 #2573）。

site_audit 只開 1920×1080、audit_text_overflow 只開 1920／1366，視窗寬 < 760 的版面沒有人掃。
這支用 390×844（可帶寬度參數）＋觸控模擬跑 12 分頁 × 繁中／英文，再驗兩個會切換狀態的控件：
  A 每個分頁：JS 例外、console.error、分頁空白、裁字（td/th 的 ellipsis）、
    超出視窗右緣又不在可捲容器裡的元素（html／body 不能橫捲，超出去的東西點不到）
  B 英雄表「精簡｜完整」：手機與 1920 都要切得動、欄數要變多
  C 預測頁目錄：按鈕要出現、點了要真的捲動（1920）

⚠ 開機後一定要 scheduleWarmup(1e9) 關預熱：預熱會自己巡分頁並藏起 #main，不關會量到「0 字」
  和「切換失效」，全是假象（#2573 第一版就這樣）。site_audit 也是這樣關。
⚠ html／body 不能橫捲 ⇒ documentElement.scrollWidth 不會變大，**不要拿它判斷溢出**
  （#2573 第一版的正控制抓到這點），要逐元素看 getBoundingClientRect。

正控制：塞一個超寬元素與一格被裁字的 td，兩個量測都要變大，否則印「掃描器有問題」。
⚠ 視窗寬 ≥ 760 時全站有 zoom＝視窗寬÷2560，超寬探針要比 2560 寬才超得出去（#2575：原本 2000px 在 768 寬只剩 600px，正控制紅）。
離開碼：0＝沒有發現；1＝有發現；2＝掃描器壞了（分頁 ≤ 5、語言不足、正控制沒過），不是「沒問題」。
只讀：不動 index.html 與資料檔，也不寫 SITE_FINDINGS。發現的處理跟線 1 一樣：彙報，使用者同意才改。
"""
import io
import json
import os
import subprocess
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PORT = 8779
LANGS = ("zh", "en")
SLOW = ("圖鑑", "積分", "預測", "模擬BP")
MOBILE_W = int(sys.argv[1]) if len(sys.argv) > 1 else 390   # 可帶寬度：python scripts/audit_mobile.py 360

MEASURE = r"""() => {
  const W = innerWidth;
  const vis = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const inScroller = e => { for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) {
      const o = getComputedStyle(p).overflowX; if (o === 'auto' || o === 'scroll' || o === 'hidden' || o === 'clip') return true; } return false; };
  const off = [];
  for (const e of document.querySelectorAll('body *')) {
    if (!vis(e) || e.closest('script,style')) continue;
    const r = e.getBoundingClientRect();
    if (r.right > W + 1 && !inScroller(e) && getComputedStyle(e).position !== 'fixed') {
      off.push({ t: e.tagName + (e.id ? '#' + e.id : '') + (typeof e.className === 'string' && e.className ? '.' + e.className.split(' ')[0] : ''),
                 right: Math.round(r.right) });
      if (off.length >= 200) break; }
  }
  off.sort((a, b) => b.right - a.right);
  const clip = [];
  for (const e of document.querySelectorAll('#main th,#main td')) {
    if (!vis(e) || !e.textContent.trim()) continue;
    const s = getComputedStyle(e);
    if (s.textOverflow === 'ellipsis' && s.overflow !== 'visible' && e.scrollWidth > e.clientWidth + 1)
      clip.push(e.textContent.trim().slice(0, 24));
  }
  const main = document.getElementById('main');
  return { W, off, clip, txt: main ? main.innerText.trim().length : 0 };
}"""

TH = "() => document.querySelectorAll('#main table th').length"


def click_tab(pg, v):
    return pg.evaluate("""(t) => { const el = [...document.querySelectorAll('nav .tab')].find(e => (e.dataset.view || e.textContent.trim()) === t);
        if (!el) return false; el.click(); return true; }""", v)


def boot(br, lang, w, h, mobile):
    ctx = br.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append("例外 " + str(e)[:160]))
    transient = ("ERR_ADDRESS_IN_USE", "ERR_CONNECTION_REFUSED", "ERR_NETWORK_CHANGED", "ERR_ABORTED")
    pg.on("console", lambda m: errs.append("console " + m.text[:160])
          if m.type == "error" and not any(k in m.text for k in transient) else None)
    pg.add_init_script("localStorage.setItem('lang',%r)" % lang)
    pg.goto("http://127.0.0.1:%d/index.html?y=2026" % PORT, wait_until="load", timeout=120000)
    pg.wait_for_function("() => typeof GAMES !== 'undefined' && GAMES.length > 0", timeout=90000)
    pg.wait_for_timeout(1500)
    pg.evaluate("() => scheduleWarmup(1e9)")
    pg.wait_for_timeout(1500)
    return ctx, pg, errs


def hero_toggle(pg, where, found):
    click_tab(pg, "英雄")
    pg.wait_for_timeout(1200)
    lite = pg.evaluate(TH)
    ok = pg.evaluate("() => { const b = document.querySelector('#heroColSeg button[data-v=full]'); if (!b) return false; b.click(); return true; }")
    pg.wait_for_timeout(1200)
    full = pg.evaluate(TH)
    on = pg.evaluate("() => { const b = document.querySelector('#heroColSeg button.on'); return b ? b.dataset.v : null; }")
    m = pg.evaluate(MEASURE)
    print("   %s 英雄表 精簡 %d 欄 → 完整 %d 欄（on=%s）裁字 %d" % (where, lite, full, on, len(m["clip"])))
    if not ok or on != "full" or full <= lite:
        found.append("%s／英雄表：切完整失敗（按鈕 %s，%d→%d 欄，on=%s）" % (where, ok, lite, full, on))
    if m["clip"]:
        found.append("%s／英雄表完整：裁字 %d 格，例：%s" % (where, len(m["clip"]), m["clip"][:3]))


def sweep(br, lang, found):
    ctx, pg, errs = boot(br, lang, MOBILE_W, 844, True)
    tabs = pg.evaluate("() => [...document.querySelectorAll('nav .tab')].filter(e => e.getBoundingClientRect().width > 0).map(e => e.dataset.view || e.textContent.trim())")
    print("── %s 手機 %d×844：%d 個分頁" % (lang, MOBILE_W, len(tabs)))
    for v in tabs:
        n0 = len(errs)
        click_tab(pg, v)
        pg.wait_for_timeout(1800 if v in SLOW else 900)
        m = pg.evaluate(MEASURE)
        print("   %s 超出 %d 裁字 %d 文字 %d%s" % (v, len(m["off"]), len(m["clip"]), m["txt"], "  例外／console %d" % (len(errs) - n0) if len(errs) > n0 else ""))
        where = "%s／%s" % (lang, v)
        if m["off"]:
            found.append("%s：%d 個元素超出右緣（視窗 %d），最遠 %s right=%d" % (where, len(m["off"]), m["W"], m["off"][0]["t"], m["off"][0]["right"]))
        if m["clip"]:
            found.append("%s：裁字 %d 格，例：%s" % (where, len(m["clip"]), m["clip"][:3]))
        if m["txt"] < 30:
            found.append("%s：分頁幾乎空白（%d 字）" % (where, m["txt"]))
        for e in errs[n0:]:
            found.append("%s：%s" % (where, e))
    base = pg.evaluate(MEASURE)
    pg.evaluate("""() => { const d = document.createElement('div'); d.id = 'zzProbe9942'; d.style.cssText = 'width:6000px;height:5px'; document.body.appendChild(d);
        const t = document.createElement('table'); t.id = 'zzProbeT'; t.style.cssText = 'width:30px;table-layout:fixed';
        t.innerHTML = '<tr><td>' + 'x'.repeat(80) + '</td></tr>'; document.getElementById('main').appendChild(t); }""")
    probe = pg.evaluate(MEASURE)
    pg.evaluate("() => { document.getElementById('zzProbe9942').remove(); document.getElementById('zzProbeT').remove(); }")
    pc = len(probe["off"]) > len(base["off"]) and len(probe["clip"]) > len(base["clip"])
    print("   正控制 %s（超出 %d→%d，裁字 %d→%d）" % ("✓" if pc else "✗", len(base["off"]), len(probe["off"]), len(base["clip"]), len(probe["clip"])))
    hero_toggle(pg, lang + "／手機", found)
    ctx.close()

    ctx, pg, errs = boot(br, lang, 1920, 1080, False)
    hero_toggle(pg, lang + "／桌機", found)
    click_tab(pg, "預測")
    pg.wait_for_timeout(3000)
    n = pg.evaluate("() => document.querySelectorAll('.pdToc button').length")
    moved = 0
    for i in range(n):
        y0 = pg.evaluate("() => scrollY")
        pg.evaluate("(i) => document.querySelectorAll('.pdToc button')[i].click()", i)
        pg.wait_for_timeout(1000)
        moved += abs(pg.evaluate("() => scrollY") - y0) > 5
    print("   %s／桌機 預測目錄 %d 顆，點了有捲動 %d 顆" % (lang, n, moved))
    if not n or moved < n:
        found.append("%s／預測目錄：%d 顆按鈕只有 %d 顆會捲動" % (lang, n, moved))
    for e in errs:
        found.append("%s／桌機控件：%s" % (lang, e))
    ctx.close()
    return len(tabs), pc


def main():
    from playwright.sync_api import sync_playwright
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"], cwd=ROOT,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    found, bad = [], []
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(headless=True)
            for lang in LANGS:
                n, pc = sweep(br, lang, found)
                if n <= 5:
                    bad.append("%s 只有 %d 個分頁" % (lang, n))
                if not pc:
                    bad.append("%s 正控制沒過" % lang)
            br.close()
    finally:
        srv.terminate()
    print("═══ 手機掃描：發現 %d 筆" % len(found))
    for f in found:
        print(" ·", f)
    if bad:
        print("掃描器有問題：" + "；".join(bad))
        return 2
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
