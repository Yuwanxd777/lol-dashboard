# -*- coding: utf-8 -*-
"""推送前守門（publish.bat 在 git push 前呼叫；失敗＝exit 1 → 不推送，避免壞資料上線）
① 資料檔語法：index.html 引用的每個 .js（含 _LAZYSRC 延遲載入組）用 node --check 驗證（抓截斷/亂碼/半寫入）。
② headless 開機：載入 index.html?y=2026，收集 pageerror；要求 nav 與主內容渲染、英雄分頁能開。
用法：python scripts\preflight_check.py   （exit 0=通過）
"""
import io, sys, os, re, subprocess, threading, time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
fails = []

# ── ⓪ 總上限（2026-09-22 精進迴圈 #208）──
# publish.bat 裡 run_update 有逐步 1800 秒（#202）、auto_fix 有 WaitForExit(600000)，但守門自己沒有上限：
# `pg.evaluate` 沒有 timeout 參數可下（#203 探針實測：頁面載完後主執行緒 for(;;){} ⇒ goto／wait_for_timeout
# 都回來、evaluate 到 45 秒還在等，早超過 goto 的 30 秒導覽逾時）。守門卡死 ⇒ 走不到 push、也走不到健檢
# ⇒ 不留 HEALTH_ALERT.txt，排程 IgnoreNew＋PT72H ⇒ 後面最多 6 班被跳過。
# 門檻先量才定：真實守門牆鐘 13.4s（#203，跟 site_audit 併跑），取十倍以上＝180 秒。
# 到點：印一行「✗ 守門逾時」⇒ 收掉自己的子孫（Playwright driver node ＋ headless_shell）⇒ os._exit(1)。
# exit 1＝守門沒過＝不 push（沒驗完的資料不上線，跟既有語意一致）；publish.bat 照樣跑健檢、留警示檔。
# 不能只 sys.exit：主執行緒卡在 evaluate 裡，計時器執行緒的例外進不去；os._exit 才收得掉。
# 子孫要用 taskkill /T 收：只 os._exit 自己會留下孤兒 headless_shell（每卡一班多一組）。
# 計時器是 daemon：正常 13 秒跑完時它不會把程序多留 180 秒。
# 測試：python scripts/preflight_tmo_test.py（沙盒複本＋卡死頁面；正控制釘 1a5cd582 舊版到點還活著）。
PREFLIGHT_TMO_S = float(os.environ.get("PREFLIGHT_TMO_S", "180"))   # 環境變數只給測試縮短用
_T0 = time.time()


def _children(pid):
    """直接子程序的 PID（不含自己、不含這次去問的 powershell）。psutil 這台沒裝，走 CIM。"""
    try:
        pr = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter 'ParentProcessId=%d' | Select-Object -ExpandProperty ProcessId" % pid],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        out = pr.communicate(timeout=40)[0]
        return [int(x) for x in out.split() if x.strip().isdigit() and int(x) != pr.pid]
    except Exception:
        return []


def _watchdog():
    print("✗ 守門逾時：跑了 %.0f 秒還沒驗完（上限 %.0f 秒）⇒ 收掉 headless 子孫、視為未通過、不推送"
          % (time.time() - _T0, PREFLIGHT_TMO_S), flush=True)
    kids = _children(os.getpid())
    for k in kids:
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(k)], capture_output=True, timeout=40)
        except Exception:
            pass
    print("  已收掉 %d 個子程序樹：%s" % (len(kids), kids), flush=True)
    sys.stdout.flush()
    os._exit(1)


_WD = threading.Timer(PREFLIGHT_TMO_S, _watchdog)
_WD.daemon = True
_WD.start()

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
        b = pw.chromium.launch(headless=True)
        # 固定 1920x1080：欄距/邊距要有可比性，預設小視窗會走到不同的容器斷點
        pg = b.new_page(viewport={"width": 1920, "height": 1080})
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
        # ── ③ 表格欄距一致性（2026-08-16）─────────────────────────────────
        # 使用者一再回報「欄位間隔忽大忽小」，而每次都是**別的改動順手弄壞的**，寫在記憶裡擋不住。
        # ⚠ 量的是**相鄰兩欄內容之間的空白**（使用者原話：「我要的是空白處的間隔一致」）。
        #   不要改成量「單欄留白」——那會漏掉首欄／名稱欄／末欄，而那三個正是最常出包的位置。
        MEAS = """() => {
          const wrap=document.querySelector('.tblwrap'); if(!wrap)return null;
          const tb=wrap.querySelector('table'); if(!tb)return null;
          const ths=[...tb.querySelectorAll('thead th')]; if(ths.length<4)return null;
          const rows=[...tb.querySelectorAll('tbody tr')]; if(!rows.length)return null;
          const z=window._zoomF||1;
          const box=el=>{const r=document.createRange();r.selectNodeContents(el);
            return r.getBoundingClientRect();};
          const L=[],R=[];
          ths.forEach((_,i)=>{ let l=1e9,r=-1e9;
            rows.forEach(tr=>{const td=tr.children[i]; if(!td)return;
              const b=box(td); if(b.width){l=Math.min(l,b.left/z); r=Math.max(r,b.right/z);} });
            L.push(l); R.push(r); });
          const gaps=[];
          for(let i=0;i<ths.length-1;i++){ if(isFinite(L[i+1])&&isFinite(R[i]))
            gaps.push(Math.round((L[i+1]-R[i])*10)/10); }
          let cut=0;
          tb.querySelectorAll('thead th,tbody td').forEach(c=>{if(c.scrollWidth>c.clientWidth+1)cut++;});
          const wr=wrap.getBoundingClientRect();
          return {gaps, cut, L:Math.round((L[0]-wr.left/z)*10)/10,
                  R:Math.round((wr.right/z-R[ths.length-1])*10)/10};
        }"""
        for view in ("英雄", "選手", "戰隊"):
            try:
                pg.click(f'nav .tab[data-view="{view}"]', timeout=5000); pg.wait_for_timeout(1200)
                m = pg.evaluate(MEAS)
            except Exception as e:
                fails.append(f"{view}分頁欄距檢查失敗：{str(e)[:70]}"); continue
            if not m or not m["gaps"]:
                fails.append(f"{view}分頁量不到欄距"); continue
            if m["cut"]:
                fails.append(f"{view}分頁有 {m['cut']} 格被裁字（不裁字鐵則）")
            gs = sorted(m["gaps"]); mid = gs[len(gs)//2]
            bad = [g for g in m["gaps"] if abs(g - mid) > 3]   # 只允許一個空隙偏離（欄名塞不下被補寬時）
            if len(bad) > 1:
                fails.append(f"{view}分頁欄距不一致：{len(bad)}/{len(m['gaps'])} 個空隙偏離中位 {mid}px（{bad[:5]}）")
            if m["L"] < 19.5 or m["R"] < 19.5:
                fails.append(f"{view}分頁內容離框太近：左 {m['L']}px／右 {m['R']}px（鐵則至少 20px）")
            if abs(m["R"] - m["L"]) > 4:
                fails.append(f"{view}分頁左右邊距不對稱：左 {m['L']}px／右 {m['R']}px")
        print("③ 表格欄距檢查完成" + ("，通過" if not any(("欄距" in f) or ("裁字" in f) or ("邊距" in f) or ("離框" in f) for f in fails) else ""))
        for e in errs: fails.append(f"pageerror：{e}")
        b.close()
    print("② headless 開機檢查完成" + ("，通過" if not any("pageerror" in f or "開機" in f or "英雄分頁" in f for f in fails) else ""))
except Exception as e:
    fails.append(f"headless 檢查無法執行：{str(e)[:100]}")

_WD.cancel()
if fails:
    print("✗ 守門未通過：")
    for f in fails: print("  -", f)
    sys.exit(1)
print("✓ 守門通過，可以推送。")
