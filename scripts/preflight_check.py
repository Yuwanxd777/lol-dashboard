# -*- coding: utf-8 -*-
"""推送前守門（publish.bat 在 git push 前呼叫；失敗＝exit 1 → 不推送，避免壞資料上線）
① 資料檔語法：index.html 引用的每個 .js（含 _LAZYSRC 延遲載入組）用 node --check 驗證（抓截斷/亂碼/半寫入）。
② headless 開機：載入 index.html?y=2026，收集 pageerror；要求 nav 與主內容渲染、英雄分頁能開。
用法：python scripts\preflight_check.py   （exit 0=通過）
"""
import io, sys, os, re, subprocess

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
fails = []

# ── ① 資料檔語法 ──
html = open(os.path.join(ROOT, "index.html"), encoding="utf-8", errors="replace").read()
srcs = set(re.findall(r'src="([^"]+\.js)"', html))
srcs |= set(re.findall(r'"([a-z_0-9]+\.js)"', html.split("_LAZYSRC", 1)[1][:400])) if "_LAZYSRC" in html else set()
srcs = sorted(s for s in srcs if "://" not in s)
node = "node"
for s in srcs:
    p = os.path.join(ROOT, s)
    if not os.path.exists(p):
        fails.append(f"缺檔案：{s}"); continue
    if os.path.getsize(p) == 0:
        fails.append(f"空檔案：{s}"); continue
    r = subprocess.run([node, "--check", p], capture_output=True, text=True)
    if r.returncode != 0:
        fails.append(f"語法錯誤：{s} → {(r.stderr or '').strip().splitlines()[-1][:120] if r.stderr else '?'}")
print(f"① 資料檔 {len(srcs)} 個檢查完成" + (f"，{len(fails)} 個問題" if fails else "，全部通過"))

# ── ② headless 開機 ──
try:
    from playwright.sync_api import sync_playwright
    import pathlib
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True); pg = b.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:150]))
        pg.goto(pathlib.Path(os.path.join(ROOT, "index.html")).resolve().as_uri() + "?y=2026")
        pg.wait_for_timeout(2600)
        ok = pg.evaluate("()=>!!document.querySelector('nav') && (document.body.innerHTML.length>5000)")
        if not ok: fails.append("開機渲染異常（nav/主內容缺）")
        try:
            pg.click('nav .tab[data-view="英雄"]', timeout=4000); pg.wait_for_timeout(700)
            rows = pg.evaluate("()=>document.querySelectorAll('#tbl tbody tr').length")
            if not rows: fails.append("英雄分頁 0 列")
        except Exception as e:
            fails.append(f"英雄分頁開啟失敗：{str(e)[:80]}")
        for e in errs: fails.append(f"pageerror：{e}")
        b.close()
    print("② headless 開機檢查完成" + ("，通過" if not any("pageerror" in f or "開機" in f or "英雄分頁" in f for f in fails) else ""))
except Exception as e:
    fails.append(f"headless 檢查無法執行：{str(e)[:100]}")

if fails:
    print("✗ 守門未通過：")
    for f in fails: print("  -", f)
    sys.exit(1)
print("✓ 守門通過，可以推送。")
