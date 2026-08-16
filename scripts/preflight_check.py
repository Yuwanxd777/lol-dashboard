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
# 掃「index.html 裡出現、且檔案真的存在」的每一個 .js 名稱。
# ⚠ 舊寫法有兩個洞，兩個都會讓最該檢查的大檔溜過去（2026-08-01 全面稽核抓到）：
#   ① 只認 src="xxx.js"：data.js／career.js 改成帶快取破壞參數（src="data.js?t=…"、document.write
#      組出來的）之後就再也掃不到；bp_live_ui.js 同理。
#   ② _LAZYSRC 用 split("_LAZYSRC",1)[1][:400] 取清單，但檔案裡**第一個** _LAZYSRC 出現在一行註解
#      （「見下方 _LAZYSRC.builds + ensureBuilds」），於是取到的 400 字是註解本文，
#      wiki_patches(3.0MB)／career(5.8MB)／leaguepedia(3.3MB)／soloq_builds(1.5MB)…
#      這些延遲載入的大檔一個都沒被檢查。守門的意義就是擋半寫入／截斷的資料檔，漏掉它們等於沒守。
# 新寫法：把所有字串字面值裡的 .js 名稱都撈出來（允許後面接 ?query），再用「檔案存在」過濾。
# 多檢查幾個檔沒有壞處；漏檢才有。
cand = set(re.findall(r'["\'(]\s*([A-Za-z0-9_\-./]+\.js)(?:\?[^"\')]*)?', html))
srcs = sorted(s for s in cand if "://" not in s and os.path.isfile(os.path.join(ROOT, s)))
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
        # ── ③ 表格欄距一致性（2026-08-16 加）───────────────────────────────
        # 使用者一再回報「欄位間隔忽大忽小」，而每次都是**別的改動順手弄壞的**（最近一次：把三個資料欄
        # 包進 .heroname 借用對齊機制，連帶吃到 td:has(.heroname) 給名稱欄用的 1em 左內距）。
        # 規則寫在記憶裡擋不住 → 改成機器檢查：量每個資料欄的「欄寬 − 該欄最寬內容」，
        # 允許**最多一欄**因欄名塞不下被保險機制補寬，其餘必須落在中位數 ±2.5px 內。
        MEAS = """() => {
          const wrap=document.querySelector('.tblwrap'); if(!wrap)return null;
          const tb=wrap.querySelector('table'); if(!tb)return null;
          const ths=[...tb.querySelectorAll('thead th')]; if(ths.length<4)return null;
          const rows=[...tb.querySelectorAll('tbody tr')]; if(!rows.length)return null;
          const z=window._zoomF||1;
          const cw=el=>{const r=document.createRange();r.selectNodeContents(el);
            return r.getBoundingClientRect().width/z;};
          const box=el=>{const r=document.createRange();r.selectNodeContents(el);
            return r.getBoundingClientRect();};
          const pads=[]; let cut=0;
          ths.forEach((th,i)=>{
            const w=th.getBoundingClientRect().width/z;
            let m=0; rows.forEach(tr=>{const td=tr.children[i]; if(td)m=Math.max(m,cw(td));});
            if(i>=2&&i<ths.length-1)pads.push(Math.round((w-m)*10)/10);
          });
          tb.querySelectorAll('thead th,tbody td').forEach(c=>{if(c.scrollWidth>c.clientWidth+1)cut++;});
          const wr=wrap.getBoundingClientRect(), r0=rows[0].children;
          const L=(box(r0[0]).left-wr.left)/z, R=(wr.right-box(r0[r0.length-1]).right)/z;
          return {pads, cut, L:Math.round(L*10)/10, R:Math.round(R*10)/10};
        }"""
        for view in ("英雄", "選手", "戰隊"):
            try:
                pg.click(f'nav .tab[data-view="{view}"]', timeout=5000); pg.wait_for_timeout(1200)
                m = pg.evaluate(MEAS)
            except Exception as e:
                fails.append(f"{view}分頁欄距檢查失敗：{str(e)[:70]}"); continue
            if not m or not m["pads"]:
                fails.append(f"{view}分頁量不到欄距"); continue
            if m["cut"]:
                fails.append(f"{view}分頁有 {m['cut']} 格被裁字（不裁字鐵則）")
            ps = sorted(m["pads"]); mid = ps[len(ps)//2]
            bad = [p for p in m["pads"] if abs(p - mid) > 2.5]   # 正常只有四捨五入誤差(<1px)；門檻放到 6 會擋不住實際 5px 的偏差
            if len(bad) > 1:
                fails.append(f"{view}分頁欄距不一致：{len(bad)}/{len(m['pads'])} 欄偏離中位 {mid}px（{bad[:5]}）")
            if m["R"] < 19.5:
                fails.append(f"{view}分頁末欄離右框只有 {m['R']}px（鐵則至少 20px）")
            if abs(m["R"] - m["L"]) > 8:
                fails.append(f"{view}分頁左右邊距不對稱：左 {m['L']}px / 右 {m['R']}px")
        print("③ 表格欄距檢查完成" + ("，通過" if not any(("欄距" in f) or ("裁字" in f) or ("邊距" in f) or ("右框" in f) for f in fails) else ""))
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
