# -*- coding: utf-8 -*-
"""英雄分頁「英雄篩選」框的回歸（使用者 2026-09-06 回報的兩個 bug）：
  ① 按 ↺ 回復預設後，英雄篩選要真的清空（V.heroQ 與輸入框都空、表格回到全部）
  ② 打 Va → 表格剩多隻；離開輸入框（blur／Enter）**不可以**被自動改成第一個前綴相符（法洛士），
     要保留 Va 當 contains 篩選；從清單挑一隻（完全相符）才變成那一隻。
     清單的輔助說明要帶英文名，打 Va 瀏覽器才列得出建議。

用法：python scripts/hero_filter_test.py
"""
import io, os, subprocess, sys, time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8775
PASS = FAIL = 0


def ok(name, got, want=True):
    global PASS, FAIL
    if got == want:
        PASS += 1; print("  ✓ " + name)
    else:
        FAIL += 1; print("  ✗ %s：得到 %r，應為 %r" % (name, got, want))


srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"], cwd=ROOT,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.5)
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True)
        pg = br.new_page(viewport={"width": 1920, "height": 1080})
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:150]))
        pg.add_init_script("localStorage.setItem('lang','zh')")
        pg.goto("http://127.0.0.1:%d/index.html?y=2026" % PORT, wait_until="load", timeout=120000)
        pg.wait_for_function("() => typeof GAMES !== 'undefined' && GAMES.length > 0", timeout=90000)
        pg.wait_for_timeout(1500)
        pg.click('nav .tab[data-view="英雄"]', timeout=10000)
        pg.wait_for_timeout(3500)          # 表格首繪後還會沉澱一次（360 → 157 列），基準要等它穩
        rows = lambda: pg.evaluate("() => document.querySelectorAll('#tbl tbody tr').length")
        first_name = lambda: pg.evaluate("() => { const td = document.querySelector('#tbl tbody tr td:nth-child(2)'); return td ? (td.dataset.nm || td.textContent.trim()) : ''; }")
        n_all = rows()
        ok("英雄分頁有表格", n_all > 10, True)

        print("\n② 打 Va：表格縮小、離開框不可以被改成法洛士")
        pg.evaluate("() => { const e = document.getElementById('vCh'); e.focus(); }")
        pg.type("#vCh", "Va", delay=120); pg.wait_for_timeout(500)
        n_va = rows()
        ok("打 Va 後表格剩多隻（2~30）", 2 <= n_va <= 30, True)
        sugg = pg.evaluate("() => [...document.querySelectorAll('#vChdl option')].filter(o => (o.value + ' ' + o.textContent).toLowerCase().includes('va')).map(o => o.value)")
        ok("⭐ 清單有英文輔助說明，打 va 對得到 >= 2 個建議", len(sugg) >= 2, True)
        # 離開輸入框（Tab＝blur → change）
        pg.keyboard.press("Tab"); pg.wait_for_timeout(600)
        ok("⭐ 離開框後 V.heroQ 仍是 Va（不被改成第一個前綴相符）", pg.evaluate("() => V.heroQ"), "Va")
        ok("   輸入框仍顯示 Va", pg.evaluate("() => document.getElementById('vCh').value"), "Va")
        ok("   表格仍是那幾隻（不是只剩 1 隻）", rows(), n_va)
        # 從清單挑第二個建議（完全相符）→ 只剩那一隻
        if len(sugg) >= 2:
            pick = sugg[1]
            pg.evaluate("""(v) => { const e = document.getElementById('vCh'); e.focus(); e.value = v;
                e.dispatchEvent(new Event('input', {bubbles:true})); e.dispatchEvent(new Event('change', {bubbles:true})); }""", pick)
            pg.wait_for_timeout(700)
            ok("⭐ 挑了 %r → V.heroQ 就是它" % pick, pg.evaluate("() => V.heroQ"), pick)
            ok("   表格只剩 1 列", rows(), 1)
            ok("   那一列就是它", first_name(), pick)

        print("\n① 按 ↺ 回復預設")
        pg.click("#fReset"); pg.wait_for_timeout(3500)
        ok("⭐ V.heroQ 清空", pg.evaluate("() => V.heroQ || ''"), "")
        ok("⭐ 輸入框清空", pg.evaluate("() => (document.getElementById('vCh') || {value:'?'}).value"), "")
        ok("   表格回到全部英雄", rows(), n_all)

        print("\n③ 反控制：bindCombo 非 strict 的模糊解析不受影響（其他 combo 還是會把 t 解析成 T1）")
        # 直接在頁面裡用一個臨時 combo 驗：同一支 bindCombo，非 strict 打 t → T1；strict 打 t → 保留 t
        res = pg.evaluate("""() => {
          const mk = (id) => { const w = document.createElement('span');
            w.innerHTML = '<input id="' + id + '"><datalist id="' + id + 'dl"></datalist>'; document.body.appendChild(w); };
          mk('tmpA'); mk('tmpB');
          const opts = [{v:'T1', l:'T1', a:['T1 Esports'], n: 9}, {v:'TES', l:'TES', a:['Top Esports'], n: 5}];
          let hitA = null, hitB = null;
          bindCombo('tmpA', opts, '', h => { hitA = h; }, false, 100);
          bindCombo('tmpB', opts, '', h => { hitB = h; }, false, 100, true);
          const a = document.getElementById('tmpA'); a.value = 't'; a.dispatchEvent(new Event('change'));
          const b = document.getElementById('tmpB'); b.value = 't'; b.dispatchEvent(new Event('change'));
          return { a: a.value, hitA, b: b.value, hitB };
        }""")
        ok("非 strict：打 t → 解析成 T1（原本行為）", res["a"], "T1")
        ok("非 strict：回呼拿到 T1", res["hitA"], "T1")
        ok("strict：打 t → 保留 t（不自動跳第一個）", res["b"], "t")
        ok("strict：回呼拿到原文字 t", res["hitB"], "t")

        print("\n④ 沒有 JS 錯誤")
        ok("pageerror 數量", len(errs), 0)
        br.close()
finally:
    srv.kill()

print("")
if FAIL:
    print("✗ %d 條失敗、%d 條通過" % (FAIL, PASS)); sys.exit(1)
print("✓ 全部 %d 條通過" % PASS)
