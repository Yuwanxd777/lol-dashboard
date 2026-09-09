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
        rows = lambda: pg.evaluate("() => document.querySelectorAll('#tbl tbody tr').length")
        first_name = lambda: pg.evaluate("() => { const td = document.querySelector('#tbl tbody tr td:nth-child(2)'); return td ? (td.dataset.nm || td.textContent.trim()) : ''; }")

        # 2026-09-09 #92：原本這裡是 wait_for_timeout(3500)。表格首繪後還會沉澱一次（360 → 157 列），
        # 而沉澱要多久跟機器當下的負載有關——單獨跑 3.5 秒夠，接在別的測試後面跑（回歸套件）就不夠，
        # 於是打字打進一個還在重繪的篩選列、輸入被吃掉 ⇒ 這支變成會隨機紅的測試（比沒有測試更糟：
        # 下次真的壞了會被當成 flaky 忽略）。改成等畫面自己沉澱：連兩次取樣（相隔 400ms）列數相同才往下走。
        def settle(what, expr, timeout=30000, polling=400):
            try:
                pg.wait_for_function(expr, timeout=timeout, polling=polling); return True
            except Exception as ex:
                ok("等不到「%s」（%s）" % (what, type(ex).__name__), False, True); return False

        # minrows：這一刻表格「至少」該有幾列（全表 10、篩選後 1）——不設下限的話，
        # 連續兩次都量到 0 列（還沒繪）也會被當成「沉澱好了」。
        def settled(minrows):
            return ("() => { const e = document.getElementById('vCh');"
                    " const n = document.querySelectorAll('#tbl tbody tr').length;"
                    " if (!e || n < %d || !document.querySelectorAll('#vChdl option').length)"
                    " { window.__prevN = null; return false; }"
                    " const p = window.__prevN; window.__prevN = n; return p === n; }" % minrows)
        settle("英雄分頁表格沉澱", settled(10))
        n_all = rows()
        ok("英雄分頁有表格", n_all > 10, True)

        print("\n② 打 Va：表格縮小、離開框不可以被改成法洛士")

        def type_hero(txt):
            """打字並確認真的進去了。輸入框在防抖 rerender 時可能被換掉／輸入被吃掉——
            那是環境慢造成的，重打即可；但**三次都打不進去就記一條失敗**（不會把真的壞掉洗成綠）。
            回傳嘗試次數，>1 就印出來，讓「UI 有競態」這件事看得見而不是被重試藏起來。"""
            for att in range(1, 4):
                pg.evaluate("() => { const e = document.getElementById('vCh'); if (e) { e.dataset._m = 'M'; e.focus(); } }")
                pg.type("#vCh", txt, delay=120)
                pg.wait_for_timeout(400)
                st = pg.evaluate("() => { const e = document.getElementById('vCh'); return e ? [e.value, e.dataset._m || '換掉了'] : ['<沒有這個框>', '-']; }")
                if st[0] == txt:
                    if att > 1:
                        print("     （打字第 %d 次才進得去；元素印記=%s）" % (att, st[1]))
                    return att
                print("     （第 %d 次打字沒進去：value=%r、元素印記=%s，清空重打）" % (att, st[0], st[1]))
                pg.evaluate("() => { const e = document.getElementById('vCh'); if (e) e.value = ''; }")
                pg.wait_for_timeout(400)
            ok("打 %r 進得了輸入框（試了 3 次）" % txt, False, True)
            return 0

        type_hero("Va")
        settle("打 Va 後表格沉澱", settled(1))
        n_va = rows()
        ok("打 Va 後表格剩多隻（2~30）", 2 <= n_va <= 30, True)
        sugg = pg.evaluate("() => [...document.querySelectorAll('#vChdl option')].filter(o => (o.value + ' ' + o.textContent).toLowerCase().includes('va')).map(o => o.value)")
        ok("⭐ 清單有英文輔助說明，打 va 對得到 >= 2 個建議", len(sugg) >= 2, True)
        # 離開輸入框（Tab＝blur → change）。這一段驗的是「**不可以**變」，所以刻意留固定等待
        # 並且等久一點（1000ms）：等太短反而會把「其實會被改掉、只是還沒改」讀成通過。
        pg.keyboard.press("Tab"); pg.wait_for_timeout(1000)
        ok("⭐ 離開框後 V.heroQ 仍是 Va（不被改成第一個前綴相符）", pg.evaluate("() => V.heroQ"), "Va")
        ok("   輸入框仍顯示 Va", pg.evaluate("() => document.getElementById('vCh').value"), "Va")
        ok("   表格仍是那幾隻（不是只剩 1 隻）", rows(), n_va)
        # 從清單挑第二個建議（完全相符）→ 只剩那一隻
        if len(sugg) >= 2:
            pick = sugg[1]
            pg.evaluate("""(v) => { const e = document.getElementById('vCh'); e.focus(); e.value = v;
                e.dispatchEvent(new Event('input', {bubbles:true})); e.dispatchEvent(new Event('change', {bubbles:true})); }""", pick)
            settle("挑了 %s 之後表格收斂成 1 列" % pick,
                   "() => document.querySelectorAll('#tbl tbody tr').length === 1")
            ok("⭐ 挑了 %r → V.heroQ 就是它" % pick, pg.evaluate("() => V.heroQ"), pick)
            ok("   表格只剩 1 列", rows(), 1)
            ok("   那一列就是它", first_name(), pick)

        print("\n① 按 ↺ 回復預設")
        # 按之前先等畫面沉澱：上一步的 settle 是「列數一變成 1 就往下」，那一刻 rerender 可能還沒收尾，
        # 這時點 ↺ 會被吃掉（舊版靠固定的 700ms 剛好躲過）。互動前一律等穩再點。
        settle("按 ↺ 之前畫面先沉澱", settled(1))
        pg.click("#fReset")
        settle("↺ 之後表格回到 %d 列且輸入框清空" % n_all,
               "() => { const e = document.getElementById('vCh');"
               " return !!e && e.value === '' && document.querySelectorAll('#tbl tbody tr').length === %d; }" % n_all)
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
