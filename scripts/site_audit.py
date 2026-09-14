# -*- coding: utf-8 -*-
"""網站本身的錯誤與英文版介面問題 —— 每一輪都掃，8 小時彙報一次（使用者 2026-09-06）。

掃什麼（每個分頁 × 繁中／英文）：
  ① pageerror（JS 未攔截的例外）與 console.error
  ② 破圖：可見的 <img> 載入失敗（naturalWidth=0）
  ③ 英文模式漏中文：#main 裡可見文字仍含 CJK（英雄名／說明文字沒翻到）
  ④ 分頁空白：切過去之後 #main 幾乎沒有內容
  ⑤ 網路 404（本站自己的資源）

**互動劇本層（2026-09-14 #114，使用者「線 1 的提案開始做」）**：以前只看「切到分頁那一刻」的畫面，
互動之後才會壞的狀態（說明浮層、詳情頁、排序、分段切換、combo 輸入、圖鑑各分區與詳情、歷史年份）
一個都看不到。現在每個分頁切過去之後再照 SCN 的劇本逐一互動，**每做完一個劇本就把上面五類再收一次**，
發現歸屬到「分頁／劇本」（例：`英雄／詳情`、`圖鑑／道具詳情`、`歷史2025／圖鑑`）。
漏中文（cjk）同一種語言只記一次、歸屬給第一個看到它的劇本（第一趟 314 筆裡 22 段文字重複掛在後面的劇本上）；
每個劇本的 COLLECT 最多收 40 段中文（圖鑑那幾頁遠不止 40，報告要寫「至少 40」）。
劇本用的是真的 DOM 點擊／事件（不是直接改 V 再 render），元素找不到就記成「略過」印出來（頁面改版時才看得到）。

**互動層的正控制**（掃描器自己會不會壞）：英文那一輪的最後，在 #fHelp 上掛一個探針監聽器
（點下去丟例外＋console.error＋塞一張 /zz_probe_9942.png 壞圖＋塞一段中文），再在 #fReset 上掛一個把
#main 清空的探針，然後照正常劇本點一次——六種發現（例外／console／404／破圖／漏中文／空白）都要被收到
**而且歸屬到那個劇本**，缺一個就印「掃描器有問題」並 exit 2；探針的發現不寫進資料庫。
`--pc-dry` 不掛探針 ⇒ 正控制必須全 ✗、exit 2（證明正控制不是恆真）。

假綠防呆：分頁數 ≤ 5、語言少於 2 種、每種語言跑到的劇本 < MIN_SCN、正控制沒過 ⇒ exit 2（「掃描器壞了」，不是「沒問題」）。

**只讀**：不動 index.html、不動任何資料檔。發現寫進 autopilot/SITE_FINDINGS.json（指紋去重、
記首見／末見／次數）與 SITE_FINDINGS.md（給人看）。使用者定案：**這一線的改動要他同意才動**。

用法：
    python scripts/site_audit.py            # 掃一輪，印「這輪新增／仍在／消失」
    python scripts/site_audit.py --report   # 不掃，只把目前所有未解的發現整理成 8 小時彙報用的 Markdown
    python scripts/site_audit.py --no-scn   # 只掃分頁、不跑互動劇本（#114 之前的行為，量對照用）
    python scripts/site_audit.py --tabs 英雄,積分   # 只跑這幾個分頁（除錯用；正控制照跑）
    python scripts/site_audit.py --pc-dry   # 不掛探針，驗證正控制真的會紅
"""
import io
import json
import os
import re
import subprocess
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AP = os.path.join(ROOT, "autopilot")
JS = os.path.join(AP, "SITE_FINDINGS.json")
MD = os.path.join(AP, "SITE_FINDINGS.md")
PORT = 8774
LANGS = ("zh", "en")
CJK = re.compile(r"[一-鿿㐀-䶿]")
MIN_SCN = 60          # 每種語言至少要真的跑到這麼多個劇本，否則當掃描器壞了（#114 實測 zh／en 各 98、略過 0）
PC_PREFIX = "正控制／"  # 正控制劇本的歸屬前綴：這些發現只驗掃描器、不進資料庫
HIST_YEAR = "2025"    # 歷史年份劇本切到哪一年


def load():
    try:
        return json.load(io.open(JS, encoding="utf-8"))
    except Exception:
        return {"findings": {}, "runs": []}


def save(db):
    os.makedirs(AP, exist_ok=True)
    io.open(JS, "w", encoding="utf-8").write(json.dumps(db, ensure_ascii=False, indent=1))
    # 給人看的版本：未解的在上，依「還在的次數」排序
    open_ = [(k, v) for k, v in db["findings"].items() if not v.get("gone")]
    gone = [(k, v) for k, v in db["findings"].items() if v.get("gone")]
    last = db["runs"][-1] if db["runs"] else {}
    L = ["# 網站稽核發現（自動產生，只讀掃描）", "",
         "最近一輪：%s　未解 %d 筆／已消失 %d 筆　互動劇本 %s 個（略過 %s）" % (
             last.get("at", "–"), len(open_), len(gone), last.get("scn", "–"), len(last.get("scn_skip", []))), ""]
    if open_:
        L.append("## 未解")
        L.append("")
        L.append("| 分頁／劇本 | 語言 | 類型 | 內容 | 首見 | 末見 | 次數 |")
        L.append("|---|---|---|---|---|---|---|")
        for k, v in sorted(open_, key=lambda kv: (-kv[1]["count"], kv[0])):
            L.append("| %s | %s | %s | %s | %s | %s | %d |" % (
                v["tab"], v["lang"], v["kind"], v["text"].replace("|", "\\|")[:90],
                v["first"][5:16], v["last"][5:16], v["count"]))
    if gone:
        L.append("")
        L.append("## 已消失（之前有、最近一輪沒了）")
        for k, v in gone[:30]:
            L.append("- %s／%s／%s：%s（末見 %s）" % (v["tab"], v["lang"], v["kind"], v["text"][:70], v["last"][5:16]))
    if last.get("scn_skip"):
        L.append("")
        L.append("## 最近一輪略過的劇本（元素找不到；頁面改版時要回頭對 SCN）")
        for s in last["scn_skip"][:40]:
            L.append("- " + s)
    io.open(MD, "w", encoding="utf-8").write("\n".join(L) + "\n")


def report(db):
    """8 小時彙報用：只列未解，按類型分組，附上「這段時間新出現的」標記。"""
    open_ = [(k, v) for k, v in db["findings"].items() if not v.get("gone")]
    last = db["runs"][-1] if db["runs"] else {}
    tail = ""
    if last:
        tail = "\n（最近一輪 %s：分頁 %s × %s 語言、互動劇本 %s 個／略過 %s 個、正控制 %s）" % (
            last.get("at"), last.get("tabs"), last.get("langs", len(LANGS)), last.get("scn", "–"),
            len(last.get("scn_skip", [])), "✓" if last.get("pc") else ("未跑" if last.get("pc") is None else "✗"))
    if not open_:
        return "網站稽核：目前**沒有**未解的發現（分頁 × 繁中／英文 × 互動劇本全掃過）。" + tail
    by = {}
    for k, v in open_:
        by.setdefault(v["kind"], []).append(v)
    L = ["網站稽核彙報（未解 %d 筆）：" % len(open_)]
    names = {"pageerror": "JS 例外", "console": "console.error", "img": "破圖",
             "cjk": "英文模式漏中文", "empty": "分頁空白", "404": "資源 404"}
    for kind, items in sorted(by.items(), key=lambda kv: -len(kv[1])):
        L.append("")
        L.append("**%s（%d）**" % (names.get(kind, kind), len(items)))
        for v in sorted(items, key=lambda v: (-v["count"], v["tab"]))[:12]:
            L.append("- %s／%s：%s　（%d 輪）" % (v["tab"], v["lang"], v["text"][:80], v["count"]))
        if len(items) > 12:
            L.append("- …另 %d 筆見 autopilot/SITE_FINDINGS.md" % (len(items) - 12))
    return "\n".join(L) + tail


COLLECT = r"""() => {
  const out = [];
  const vis = el => { const cs = getComputedStyle(el); if (cs.display === 'none' || cs.visibility === 'hidden') return false;
                      const r = el.getBoundingClientRect(); return r.width > 2 && r.height > 2; };
  // ② 破圖
  document.querySelectorAll('#main img, header img, nav img').forEach(im => {
    if (!vis(im)) return;
    if (im.complete && im.naturalWidth === 0 && im.getAttribute('src'))
      out.push({kind: 'img', text: (im.getAttribute('src') || '').slice(-80)});
  });
  // ③ 英文模式漏中文（呼叫端只在 en 時採用）
  const cjk = /[一-鿿㐀-䶿]/;
  const seen = new Set();
  const walker = document.createTreeWalker(document.querySelector('#main') || document.body, NodeFilter.SHOW_TEXT);
  let n; let cnt = 0;
  while ((n = walker.nextNode()) && cnt < 4000) {
    cnt++;
    const t = (n.textContent || '').trim();
    if (!t || !cjk.test(t)) continue;
    const el = n.parentElement; if (!el || !vis(el)) continue;
    // 資料不是介面：選手的積分帳號名本來就會有中文（碎碎念#思念QAQ），不算漏翻（2026-09-06 第 0 次彙報後排除）
    // 刷野速度的 .jgPlayer（影片作者／帳號名，例：GodK馄饨螳螂、個人的JGフルクリア）同理（2026-09-15 #114 互動層第一趟排除）
    if (el.closest('script,style,noscript,[lang="zh"],.zhOnly,.acctLink,a.acctLink,.jgPlayer')) continue;
    const key = t.slice(0, 40);
    if (seen.has(key)) continue; seen.add(key);
    const tag = el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ')[0] : '');
    out.push({kind: 'cjk', text: key + '  <' + tag + '>'});
    if (seen.size >= 40) break;
  }
  // ④ 分頁空白
  const m = document.querySelector('#main');
  const len = m ? (m.textContent || '').replace(/\s+/g, '').length : 0;
  if (len < 120) out.push({kind: 'empty', text: '#main 只有 ' + len + ' 個字'});
  return out;
}"""

# ---- 互動劇本用的 DOM 動作（全部走真的元素事件；找不到元素回 false → 該劇本記「略過」）----
ACT = {
    "click": """(s) => { const el = document.querySelector(s); if (!el) return false; el.click(); return true; }""",
    "seg": """([id, v]) => { const el = document.getElementById(id); if (!el) return false;
        const b = [...el.querySelectorAll('button')].find(b => b.dataset.v === v || b.textContent.trim() === v);
        if (!b) return false; b.click(); return true; }""",
    "dex": """(s) => { const b = [...document.querySelectorAll('.filters .dexTab')].find(x => x.dataset.s === s);
        if (!b) return false; b.click(); return true; }""",
    # combo：把 datalist 第一個選項填進去、發 change（bindCombo 是 inp.onchange 解析後才呼叫回呼）
    "combo": """(id) => { const inp = document.getElementById(id), dl = document.getElementById(id + 'dl');
        if (!inp || !dl) return false; const o = dl.querySelector('option'); if (!o) return false;
        inp.value = o.value; inp.dispatchEvent(new Event('input', {bubbles: true}));
        inp.dispatchEvent(new Event('change', {bubbles: true})); return true; }""",
    "type": """([s, t]) => { const el = document.querySelector(s); if (!el) return false; el.focus(); el.value = t;
        el.dispatchEvent(new Event('input', {bubbles: true})); el.dispatchEvent(new Event('change', {bubbles: true})); return true; }""",
    "select": """([s, v]) => { const el = document.querySelector(s); if (!el) return false;
        if (![...el.options].some(o => o.value === v)) return false;
        el.value = v; el.dispatchEvent(new Event('change', {bubbles: true})); return true; }""",
}

# 每個分頁的劇本：(標籤, 步驟清單, 做完等幾毫秒再收)。步驟 = (動作, 參數…)；"key" 是鍵盤、"waitfn" 是等某個 JS 條件成立。
# 「*」是每個分頁都跑的（接在專屬劇本後面；回復預設放最後，順便把分頁狀態清乾淨）。
# 元素 id／class 來自 autopilot/_m114_dom_probe.py 的盤點（2026-09-14）；頁面改版讓元素消失時劇本會印成「略過」。
SCN_COMMON = [
    ("說明浮層", [("click", "#fHelp")], 900, [("click", "#fHelp")]),
    ("回復預設", [("click", "#fReset")], 1000, []),
]
# 排序只放在有可排序欄名的分頁（英雄／選手／戰隊／積分；其餘分頁沒有 th[data-rs]，放共通會每輪多 12 個「略過」噪音）
SCN_SORT = ("排序", [("click", "#main th[data-rs], #main th[data-k], #main th[data-rk]")], 1000, [])
SCN = {
    "總覽": [("點選手→英雄角色池", [("click", "#main .plink")], 2200, []),
             ("全域返回", [("click", "#globalBack")], 1500, [])],
    "近況": [("輸入戰隊", [("combo", "vRecent")], 2200, [])],
    "英雄": [("散點圖", [("seg", "heroVizSeg", "scatter")], 1500, []),
             ("表格", [("seg", "heroVizSeg", "table")], 1200, []),
             ("詳情", [("click", "#main table tbody tr td:nth-child(2)")], 2500, []),
             ("詳情切積分", [("seg", "heroModeSeg", "soloq")], 2500, []),
             ("詳情切比賽", [("seg", "heroModeSeg", "pro")], 1500, []),
             ("詳情返回", [("click", ".subBack")], 1500, []), SCN_SORT],
    "選手": [("顯示更多", [("click", "#plMore")], 1500, []),
             ("雷達加軸", [("click", "#axAdd")], 1200, []),
             ("點選手→角色池", [("click", "#main table tbody tr td:nth-child(2)")], 2500, []),
             ("全域返回", [("click", "#globalBack")], 1500, []), SCN_SORT],
    "戰隊": [("對戰戰隊", [("combo", "vVs")], 2200, []),
             ("點戰隊列", [("click", "#main table tbody tr td.plink")], 2200, []),
             ("全域返回", [("click", "#globalBack")], 1500, []), SCN_SORT],
    "陣容": [("輸入戰隊", [("combo", "vRoster")], 2500, []),
             ("模式積分", [("seg", "rosterModeSeg", "soloq")], 2500, []),
             ("模式生涯", [("seg", "rosterModeSeg", "career")], 2500, []),
             ("橫排", [("seg", "rosterLaySeg", "h")], 1500, []),
             ("直排", [("seg", "rosterLaySeg", "v")], 1000, []),
             ("模式比賽", [("seg", "rosterModeSeg", "pro")], 1500, [])],
    "比賽BP": [("該隊模式", [("seg", "bpSideSeg", "team")], 1800, []),
               ("選序模式", [("seg", "bpSideSeg", "draft")], 1800, []),
               ("藍紅模式", [("seg", "bpSideSeg", "br")], 1200, []),
               ("顯示更多", [("click", "#bpMore")], 1800, []),
               ("清欄位篩選", [("click", "#bpColClr")], 1200, [])],
    # 模擬BP 刻意不點 #bsLive（直播同步：會去連 8178，線 2 的範圍）
    "模擬BP": [("匯入比賽", [("click", "#bsHist")], 1500, [("key", "Escape")]),
               ("近期積分", [("click", "#bpSoloqPool")], 1800, []),
               ("自動", [("click", "#bpAutoBtn")], 1200, []),
               ("一般模式", [("seg", "bpModeSeg", "normal")], 1500, []),
               ("全域模式", [("seg", "bpModeSeg", "global")], 1000, []),
               ("清盤", [("click", "#bpResetBoard")], 1200, [])],
    "英雄Tier": [("比賽數據", [("click", "#tierData")], 2000, []),
                 ("自訂", [("click", "#tierCustom")], 1500, []),
                 ("加階", [("click", "#tAdd")], 1000, []),
                 ("積分數據", [("click", "#tierDataSoloq")], 2000, []),
                 ("混合模式", [("seg", "tierModeSeg", "mix")], 1500, []),
                 ("分路模式", [("seg", "tierModeSeg", "lanes")], 1000, []),
                 ("參數面板", [("click", "#tierParam")], 1000, [("click", "#tierParam")]),
                 ("搜尋", [("type", "#tierQ", "a")], 1000, [("type", "#tierQ", "")]),
                 ("清除", [("click", "#tierReset")], 1000, [])],
    "積分": [("每日戰況", [("seg", "rankViewSeg", "daily")], 3200, []),
             ("排行榜", [("seg", "rankViewSeg", "ladder")], 1500, []),
             ("搜尋", [("type", "#rankQ", "t1")], 1000, [("type", "#rankQ", "")]),
             ("選手詳情", [("click", "#main .rankName[data-detail]")], 2800, []),
             ("詳情顯示更多", [("click", "#sqMore")], 1500, []),
             ("詳情返回", [("click", ".subBack")], 1500, []), SCN_SORT],
    "圖鑑": [("版本", [("dex", "版本")], 2000, []),
             ("版本→英雄詳情", [("click", ".chgHeroGo")], 2500, []),
             ("版本→英雄詳情返回", [("click", ".subBack")], 1200, []),
             ("英雄", [("dex", "英雄")], 2000, []),
             ("英雄詳情", [("click", "#dexBox .plink")], 2500, []),
             ("英雄詳情返回", [("click", ".subBack")], 1200, []),
             ("道具", [("dex", "道具")], 2000, []),
             ("道具詳情", [("click", "#dexBox .plink")], 2200, []),
             ("道具詳情返回", [("click", ".subBack")], 1200, []),
             ("符文", [("dex", "符文")], 2000, []),
             ("符文詳情", [("click", "#dexBox .runeNm")], 2200, []),
             ("符文詳情返回", [("click", ".subBack")], 1200, []),
             ("召喚師技能", [("dex", "召喚師技能")], 1800, []),
             ("召技詳情", [("click", "#dexBox .plink")], 2000, []),
             ("召技詳情返回", [("click", ".subBack")], 1200, []),
             ("物件", [("dex", "物件")], 1800, []),
             ("物件詳情", [("click", "#dexBox .plink")], 2000, []),
             ("物件詳情返回", [("click", ".subBack")], 1200, []),
             ("賽事", [("dex", "賽事")], 2500, []),
             ("刷野速度", [("dex", "刷野速度")], 2500, []),
             ("刷野排序", [("click", "#jgSortBtn")], 1500, []),
             ("搜尋", [("type", "#dexQ", "a")], 1500, [("type", "#dexQ", "")])],
}
# 歷史年份：切到 HIST_YEAR（整份年度資料重載、篩選全清、回總覽），再看兩個分頁
HIST_TAB = "歷史" + HIST_YEAR   # 這組劇本的歸屬（例：歷史2025／圖鑑）
SCN_YEAR = [
    ("切換", [("select", "#yearSel", HIST_YEAR),
                             ("waitfn", "() => document.getElementById('yload').style.display === 'none' && typeof curYear !== 'undefined' && String(curYear) === '%s' && typeof GAMES !== 'undefined' && GAMES.length > 0" % HIST_YEAR)], 2000, []),
    ("英雄", [("tab", "英雄")], 2000, []),
    ("圖鑑", [("tab", "圖鑑")], 2000, []),
]

# 正控制的探針（掛在 #fHelp／#fReset 上，點下去才發作 ⇒ 只有互動層抓得到）
PC_ARM = r"""() => {
  const h = document.getElementById('fHelp'), r = document.getElementById('fReset');
  if (!h || !r) return false;
  h.addEventListener('click', () => {
    const m = document.getElementById('main');
    const im = document.createElement('img'); im.src = '/zz_probe_9942.png'; im.style.cssText = 'width:24px;height:24px;display:inline-block'; m.appendChild(im);
    const sp = document.createElement('span'); sp.textContent = '探針漏翻九九四二'; m.appendChild(sp);
    console.error('ZZ_PROBE_9942 console');
    throw new Error('ZZ_PROBE_9942 pageerror');
  });
  r.addEventListener('click', () => { document.getElementById('main').innerHTML = ''; });
  return true;
}"""
PC_MARK = ("ZZ_PROBE_9942", "zz_probe_9942", "九九四二", "#main 只有 0 個字")


def scan(opts):
    from playwright.sync_api import sync_playwright
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"], cwd=ROOT,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    found = []          # (lang, tab, kind, text)
    pcs = []            # 正控制收到的（不進資料庫）
    tabs_seen = []
    langs_done = 0
    scn_done = {}       # lang -> 跑到的劇本數
    scn_skip = []       # "lang／分頁／劇本：哪一步找不到"
    pc_ok = None
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(headless=True)
            for lang in LANGS:
                # 每種語言一個乾淨的 context：localStorage 不帶到下一種語言（劇本會 saveState）
                ctx = br.new_context(viewport={"width": 1920, "height": 1080})
                pg = ctx.new_page()
                cur = {"tab": "(boot)"}
                errs, cons, nets = [], [], []
                pg.on("pageerror", lambda e: errs.append((cur["tab"], str(e)[:160])))
                # 暫時性的網路錯誤不是網站的錯（2026-09-06 第 8 輪誤報 net::ERR_ADDRESS_IN_USE：掃描器自己的
                # 本機埠衝突；8178 直播服務沒開時的 ERR_CONNECTION_REFUSED 也是預期的）
                _TRANSIENT = ("ERR_ADDRESS_IN_USE", "ERR_CONNECTION_REFUSED", "ERR_NETWORK_CHANGED", "ERR_ABORTED")
                pg.on("console", lambda m: cons.append((cur["tab"], m.text[:160]))
                      if m.type == "error" and not any(k in m.text for k in _TRANSIENT) else None)
                pg.on("response", lambda r: nets.append((cur["tab"], r.url[-90:])) if r.status == 404 and "127.0.0.1" in r.url else None)
                pg.add_init_script("localStorage.setItem('lang',%r)" % lang)
                pg.goto("http://127.0.0.1:%d/index.html?y=2026" % PORT, wait_until="load", timeout=120000)
                pg.wait_for_function("() => typeof GAMES !== 'undefined' && GAMES.length > 0", timeout=90000)
                pg.wait_for_timeout(1500)
                try:
                    pg.evaluate("() => scheduleWarmup(1e9)")
                except Exception:
                    pass
                tabs = pg.evaluate("() => [...document.querySelectorAll('nav .tab')].map(e => e.dataset.view || e.textContent.trim())")
                tabs_seen = tabs
                sink = found
                seen_cjk = set()   # 這種語言已收過的漏中文：同一段中文在後面的劇本再出現不重複記（歸屬給第一個看到它的劇本）

                def collect(label):
                    for it in pg.evaluate(COLLECT):
                        if it["kind"] == "cjk":
                            if lang != "en" or it["text"] in seen_cjk:
                                continue
                            seen_cjk.add(it["text"])
                        sink.append((lang, label, it["kind"], it["text"]))

                def click_tab(tb):
                    return pg.evaluate("""(t) => { const el = [...document.querySelectorAll('nav .tab')]
                        .find(e => (e.dataset.view || e.textContent.trim()) === t); if (!el) return false; el.click(); return true; }""", tb)

                def step(st):
                    """跑一個步驟；回 False 代表元素找不到（劇本略過）。"""
                    kind = st[0]
                    if kind == "key":
                        pg.keyboard.press(st[1]); return True
                    if kind == "tab":
                        return click_tab(st[1])
                    if kind == "waitfn":
                        pg.wait_for_function(st[1], timeout=60000); return True
                    arg = st[1] if len(st) == 2 else list(st[1:])
                    return bool(pg.evaluate(ACT[kind], arg))

                def run_scn(tb, scn):
                    """跑一個劇本：設歸屬 → 步驟 → 等 → 收五類 → 收尾步驟。回 True＝真的跑了。"""
                    label, steps, wait_ms, post = scn
                    full = tb + "／" + label
                    cur["tab"] = full
                    for i, st in enumerate(steps):
                        if not step(st):
                            scn_skip.append("%s／%s：第 %d 步 %s 找不到" % (lang, full, i + 1, st[:2] if st[0] != "waitfn" else "waitfn"))
                            return False
                    pg.wait_for_timeout(wait_ms)
                    collect(full)
                    for st in post:
                        step(st)
                    if post:
                        pg.wait_for_timeout(300)
                    return True

                only = opts.get("tabs")
                for tb in tabs:
                    if only and tb not in only:
                        continue
                    cur["tab"] = tb
                    if not click_tab(tb):
                        found.append((lang, tb, "empty", "分頁籤點不到"))
                        continue
                    pg.wait_for_timeout(1400)
                    collect(tb)
                    if opts.get("no_scn"):
                        continue
                    for scn in SCN.get(tb, []) + SCN_COMMON:
                        if run_scn(tb, scn):
                            scn_done[lang] = scn_done.get(lang, 0) + 1
                if not opts.get("no_scn") and not only:
                    for scn in SCN_YEAR:
                        if run_scn(HIST_TAB, scn):
                            scn_done[lang] = scn_done.get(lang, 0) + 1
                # ---- 互動層正控制：只在英文那一輪（漏中文那條只有 en 會收）----
                if lang == "en" and not opts.get("no_scn"):
                    click_tab("總覽")
                    pg.wait_for_timeout(1400)
                    sink = pcs
                    armed = True if opts.get("pc_dry") else bool(pg.evaluate(PC_ARM))
                    if armed:
                        run_scn(PC_PREFIX.rstrip("／"), ("說明浮層", [("click", "#fHelp")], 1200, []))
                        run_scn(PC_PREFIX.rstrip("／"), ("回復預設", [("click", "#fReset")], 800, []))
                    sink = found
                    cur["tab"] = "(pc-done)"
                for tb, e in errs:
                    (pcs if tb.startswith(PC_PREFIX) else found).append((lang, tb, "pageerror", e))
                for tb, e in cons:
                    (pcs if tb.startswith(PC_PREFIX) else found).append((lang, tb, "console", e))
                for tb, u in nets:
                    (pcs if tb.startswith(PC_PREFIX) else found).append((lang, tb, "404", u))
                langs_done += 1
                ctx.close()
            br.close()
    finally:
        srv.kill()
    # 正控制判定：六種都要收到、而且歸屬在正控制的劇本上
    if not opts.get("no_scn"):
        def has(kind, label, mark):
            return any(k == kind and t == PC_PREFIX + label and mark in x for (_l, t, k, x) in pcs)
        checks = [("例外", has("pageerror", "說明浮層", "ZZ_PROBE_9942")),
                  ("console", has("console", "說明浮層", "ZZ_PROBE_9942")),
                  ("404", has("404", "說明浮層", "zz_probe_9942")),
                  ("破圖", has("img", "說明浮層", "zz_probe_9942")),
                  ("漏中文", has("cjk", "說明浮層", "九九四二")),
                  ("空白", has("empty", "回復預設", "#main 只有")),
                  ("不進資料庫", not any(any(m in x for m in PC_MARK) for (_l, _t, _k, x) in found))]
        pc_ok = all(ok for _, ok in checks)
        print("   正控制（互動層）：" + "／".join("%s %s" % (n, "✓" if ok else "✗") for n, ok in checks))
        if not pc_ok:
            print("   ⇒ 掃描器有問題（互動層），下面的結果不可信")
    return found, tabs_seen, langs_done, scn_done, scn_skip, pc_ok


def main():
    db = load()
    if "--report" in sys.argv:
        print(report(db))
        return 0
    opts = {"no_scn": "--no-scn" in sys.argv, "pc_dry": "--pc-dry" in sys.argv}
    if "--tabs" in sys.argv:
        opts["tabs"] = sys.argv[sys.argv.index("--tabs") + 1].split(",")
    t0 = time.time()
    found, tabs, langs_done, scn_done, scn_skip, pc_ok = scan(opts)
    now = time.strftime("%Y-%m-%d %H:%M")
    fps = set()
    new, still = [], []
    for lang, tab, kind, text in found:
        fp = "%s|%s|%s|%s" % (lang, tab, kind, text[:120])
        fps.add(fp)
        v = db["findings"].get(fp)
        if v:
            v["last"] = now; v["count"] += 1; v["gone"] = False; still.append(fp)
        else:
            db["findings"][fp] = {"lang": lang, "tab": tab, "kind": kind, "text": text[:160],
                                  "first": now, "last": now, "count": 1, "gone": False}
            new.append(fp)
    gone = []
    partial = bool(opts.get("tabs")) or opts.get("no_scn")
    for fp, v in db["findings"].items():
        if fp not in fps and not v.get("gone"):
            if partial:
                continue   # 只跑部分分頁／沒跑劇本時不把沒掃到的判成消失
            v["gone"] = True; gone.append(fp)
    scn_total = sum(scn_done.values())
    db["runs"].append({"at": now, "tabs": len(tabs), "langs": langs_done, "found": len(found), "new": len(new),
                       "gone": len(gone), "secs": round(time.time() - t0),
                       "scn": scn_total, "scn_by_lang": scn_done, "scn_skip": scn_skip[:60], "pc": pc_ok})
    db["runs"] = db["runs"][-200:]
    if not opts.get("pc_dry"):
        save(db)
    print("網站稽核 %s：分頁 %d × %d 語言，互動劇本 %s，%.0f 秒" % (
        now, len(tabs), langs_done, "／".join("%s %d" % kv for kv in sorted(scn_done.items())) or "0", time.time() - t0))
    print("  發現 %d 筆：新增 %d／仍在 %d／消失 %d" % (len(found), len(new), len(still), len(gone)))
    for fp in new[:15]:
        v = db["findings"][fp]
        print("   + %s／%s／%s：%s" % (v["tab"], v["lang"], v["kind"], v["text"][:90]))
    if len(new) > 15:
        print("   …另 %d 筆新增" % (len(new) - 15))
    if scn_skip:
        print("  略過的劇本 %d 個（元素找不到）：" % len(scn_skip))
        for s in scn_skip[:20]:
            print("   - " + s)
    # 假綠防呆：分頁太少／語言沒跑齊／劇本跑太少／正控制沒過 ⇒ 掃描器壞了
    bad = []
    if len(tabs) <= 5:
        bad.append("分頁只有 %d 個" % len(tabs))
    if langs_done < len(LANGS):
        bad.append("只跑到 %d 種語言" % langs_done)
    if not opts.get("no_scn") and not opts.get("tabs"):
        for lg in LANGS:
            if scn_done.get(lg, 0) < MIN_SCN:
                bad.append("%s 只跑到 %d 個劇本（< %d）" % (lg, scn_done.get(lg, 0), MIN_SCN))
    if pc_ok is False:
        bad.append("互動層正控制沒過")
    if bad:
        print("  ⚠ 掃描器壞了：" + "；".join(bad))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
