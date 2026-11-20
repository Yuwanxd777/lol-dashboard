# -*- coding: utf-8 -*-
"""轉會網站（https://lol-transfer.pages.dev）的兩個檔（使用者 2026-11-20「這個轉會網站只部署轉會的這分頁，其他的不用上來」）。

轉會網站本身只有一支載入頁（Desktop\\CLAUDE專案\\轉會網站\\www\\index.html），執行時從主站讀：
  transfers.js            轉會資料（⑤h3 fetch_transfers）
  transfers_site.js       ← 本程式：評分（主站選手／戰隊評分算好的結果）、每支隊伍的縮寫與隊徽、說明文字
  transfers_site_code.js  ← 本程式：轉會分頁的程式（index.html 裡 <<TRANSFERS_SITE … TRANSFERS_SITE>> 那一段）＋它要的最小外掛＋只跟轉會有關的 CSS
⇒ 其他分頁的程式與資料都不會出現在轉會網站；主站改轉會分頁，下一班排程就自動同步（載入頁不用重新部署）。

做法：無頭開本機 index.html?view=轉會（跟 fetch_team_logos_wiki 一樣自己起 http.server），等陣容表畫完，
直接在頁面裡呼叫 tAb／teamLogoHTML／window._tbRC 拿結果——跟主站完全同一套邏輯，不另外重寫。
用法：python scripts/export_transfer_site.py
"""
import io
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_DATA = os.path.join(ROOT, "transfers_site.js")
OUT_CODE = os.path.join(ROOT, "transfers_site_code.js")
PORT = 8773

# 只留跟轉會頁有關的 CSS：選擇器含這些就留（版面變數、篩選列、按鈕、卡片、陣容表 tb*、提示 tp*、評分 rt*、消息 tr*）
KEEP = re.compile(r"(^|[\s,>+~(])(:root|html|body|\*|main|#main|header|h1|#siteTitle|\.filters|\.sqLaneBtn|\.sqbtn|\.helpBtn|\.card|\.meta|"
                  r"\.cwrap|\.cx|\.tb|\.tp|\.rt|\.tr|#tbTip|\.sumEmpty|mark|input|button|select|label|a(?=[\s:,.{\[]|$)|\.lg\b|#help|\.hiNum|::?-webkit-scrollbar)")


# 類別名出現在選擇器任何位置都算（img.trRole、b.tbY 這種前面黏著標籤名的）
KEEP2 = re.compile(r"\.(?:tb|tp|rt|tr)[A-Za-z]|#tbTip|\.sqLaneBtn|\.sqbtn|\.filters|\.cwrap|\.cx\b|\.card\b|\.meta\b|\.sumEmpty|\.lg\b")


def css_blocks(css):
    """頂層切塊：回傳 [(前綴, 內容)]；@media／@container 等 at-rule 內容遞迴過濾"""
    out, i, n = [], 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j < 0:
            break
        sel = css[i:j].strip()
        depth, k = 1, j + 1
        while k < n and depth:
            if css[k] == "{":
                depth += 1
            elif css[k] == "}":
                depth -= 1
            k += 1
        out.append((sel, css[j + 1:k - 1]))
        i = k
    return out


def filter_css(css):
    css = re.sub(r"/\*[\s\S]*?\*/", "", css)
    res = []
    for sel, body in css_blocks(css):
        if sel.startswith("@font-face") or sel.startswith("@keyframes"):
            res.append(f"{sel}{{{body}}}")
        elif sel.startswith("@"):
            inner = filter_css(body)
            if inner.strip():
                res.append(f"{sel}{{{inner}}}")
        elif KEEP.search(sel) or KEEP2.search(sel):
            res.append(f"{sel}{{{body}}}")
    return "\n".join(res)


def build_code(html):
    blk = re.search(r"// <<TRANSFERS_SITE[^\n]*\n([\s\S]*?)\n\s*// TRANSFERS_SITE>>", html)
    if not blk:
        raise SystemExit("index.html 找不到 <<TRANSFERS_SITE … TRANSFERS_SITE>> 記號")
    styles = "\n".join(re.findall(r"<style[^>]*>([\s\S]*?)</style>", html))
    css = filter_css(styles)
    shim = r'''
// ── 轉會網站外掛（scripts/export_transfer_site.py 產生，勿手改）：只提供轉會分頁用到的最小全域 ──
(function(){
const TS=window.TS_DATA||{}; window.TRANSFER_RATE=TS.rate||null;
let LANG=(()=>{try{return localStorage.getItem("ts_lang")||"zh";}catch(e){return "zh";}})(); if(LANG!=="en")LANG="zh";
const V=(()=>{try{return JSON.parse(localStorage.getItem("ts_state")||"{}")}catch(e){return{}}})();
const saveState=()=>{ try{localStorage.setItem("ts_state",JSON.stringify(V));}catch(e){} };
const esc=s=>String(s).replace(/"/g,"&quot;");
const LGC=TS.lgc||{}, POS_IMG=TS.pos||{};
const TEAM=TS.team||{}, TAB_=TS.ab||{};
const teamFix=t=>t;
const tAb=n=>{ const o=TEAM[n]; return o?o.ab:n; };
const teamLogoHTML=(ab,size,noText,nm)=>{ const o=(nm&&TEAM[nm])||TAB_[ab]; const src=o&&o.logo; if(!src)return noText?"":esc(ab||"");
  return `<img src="${src}" alt="${esc(ab||"")}" title="${esc(ab||"")}" style="width:${size||18}px;height:${size||18}px;object-fit:contain;vertical-align:middle;flex:0 0 auto;filter:drop-shadow(0 0 1px rgba(255,255,255,.55))" onerror="this.remove()">`; };
const curView="轉會", curYear=+String((window.TRANSFERS||{}).from||"").slice(0,4)||0, GAMES=[];
const lazyLoad=()=>Promise.resolve();
const main=document.getElementById("main");
const HELP=(TS.help||{});
function addBase(){ const f=main.querySelector(".filters"); if(!f)return;
  const b=(id,tx,ti)=>`<button id="${id}" class="sqbtn" title="${ti}">${tx}</button>`;
  f.insertAdjacentHTML("beforeend",b("tsHelp","ℹ️",LANG==="en"?"About this page":"本頁說明")+b("tsReset","↺",LANG==="en"?"Reset filters":"重設篩選"));
  // 說明＝懸浮顯示（使用者 2026-11-20「手機的說明鈕點擊後也是懸浮顯示」）：手機從底部浮上來（跟格子小框同款）、桌面在右上；點 ✕ 或外面關閉
  document.getElementById("tsHelp").onclick=ev=>{ ev.stopPropagation(); let d=document.getElementById("tsHelpBox"); if(d){ d.remove(); return; }
    const mob=matchMedia("(max-width:760px)").matches;
    d=document.createElement("div"); d.id="tsHelpBox";
    d.style.cssText="position:fixed;z-index:10000;background:#1b2338;border:1px solid rgba(255,255,255,.14);box-shadow:0 8px 30px rgba(0,0,0,.6);color:#e8ecf4;line-height:1.75;font-size:14.5px;white-space:pre-line;overflow:auto;"
      +(mob?"left:8px;right:8px;bottom:8px;max-height:72vh;padding:16px 14px 14px;border-radius:14px":"right:16px;top:64px;width:min(560px,92vw);max-height:80vh;padding:16px 18px;border-radius:10px");
    d.innerHTML=`<button class="tbTipX" aria-label="close">✕</button><span style="float:right;width:38px;height:28px"></span>`+((LANG==="en"?HELP.en:HELP.zh)||"");   // ✕ 固定在右上角，旁邊留一塊空位讓第一行的字繞開
    document.body.appendChild(d); d.querySelector(".tbTipX").onclick=()=>d.remove(); };
  if(!window._tsHelpOut){ window._tsHelpOut=1; document.addEventListener("click",e=>{ const d=document.getElementById("tsHelpBox"); if(d&&!e.target.closest("#tsHelpBox")&&!e.target.closest("#tsHelp"))d.remove(); }); }
  document.getElementById("tsReset").onclick=()=>{ Object.assign(V,{trSrc:"",trSt:"",trRg:"",trKd:"",trQ:"",tbF:"",tbSort:""}); saveState(); render(); }; }
function render(){
/*__BLOCK__*/
addBase();
const at=document.getElementById("tsAt"), T0=window.TRANSFERS||{}; if(at&&T0.at)at.textContent=(LANG==="en"?"as of ":"截至 ")+T0.at; }
const ls=document.getElementById("tsLang"); if(ls){ ls.value=LANG; ls.onchange=()=>{ try{localStorage.setItem("ts_lang",ls.value);}catch(e){} location.reload(); }; }
render();
})();
'''
    code = shim.replace("/*__BLOCK__*/", blk.group(1))
    return ('(function(){var st=document.createElement("style");st.textContent=' + json.dumps(css, ensure_ascii=False)
            + ';document.head.appendChild(st);})();\n' + code)


EXPORT_JS = r"""()=>{
  const D=window.TRANSFERS||{}, names=new Set();
  const add=n=>{ if(n&&typeof n==="string")names.add(n); };
  (D.board||[]).forEach(t=>{ add(t.nm); add(t.tm); Object.values(t.r||{}).flat().forEach(e=>{ add(e.from); if(e.ro)add(e.ro.to); (e.ros||[]).forEach(o=>add(o.to)); }); });
  (D.wiki||[]).forEach(x=>add(x.team));
  [...(D.sheep||[]),...(D.extra||[])].forEach(x=>{ (x.tags||[]).forEach(t=>add(t[1])); (x.mv||[]).forEach(m=>{ add(m[2]); add(m[3]); }); });
  const team={}, ab={};
  names.forEach(n=>{ const a=teamFix(String(tAb(n)||"")); const h=teamLogoHTML(tAb(n),22,true,n)||""; const m=/src="([^"]+)"/.exec(h);
    team[n]={ab:a||n, logo:m?m[1]:""}; if(a&&m&&!ab[a])ab[a]={ab:a,logo:m[1]}; });
  const R=window._tbRC||null;
  return {rate:R?{pl:R.pl,plY:R.plY||{},R:R.R||{},md:R.md,tm:R.tm,wr:R.wr||{}}:null, team, ab, lgc:LGC, pos:POS_IMG,
          help:{zh:TAB_HELP["轉會"]||"", en:(window.TAB_HELP_EN||(typeof TAB_HELP_EN!=="undefined"?TAB_HELP_EN:{}))["轉會"]||""}};
}"""


def main():
    html = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
    if "--head" in sys.argv:   # 每小時排程：轉會頁程式從已 commit 的 index.html 抽（不帶到還在改、沒 commit 的半成品）
        try:
            html = subprocess.run(["git", "show", "HEAD:index.html"], cwd=ROOT, capture_output=True, check=True).stdout.decode("utf-8")
        except Exception as e:
            print(f"   git show HEAD:index.html 失敗，改用工作區：{type(e).__name__}")
    code = build_code(html)
    from playwright.sync_api import sync_playwright
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"], cwd=ROOT,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(1.5)
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1600, "height": 900})
            pg.add_init_script("try{localStorage.setItem('lang','zh')}catch(e){}")
            pg.goto(f"http://127.0.0.1:{PORT}/index.html?view=%E8%BD%89%E6%9C%83", wait_until="load", timeout=300000)
            pg.wait_for_function("document.querySelectorAll('.tbRow').length>5", timeout=300000)
            pg.wait_for_timeout(1500)
            data = pg.evaluate(EXPORT_JS)
            b.close()
    finally:
        srv.kill()
    if not data.get("rate"):
        print("   ⚠ 評分沒算出來（年份不是轉會賽季？），轉會網站的評分欄會是 –")
    # 自由人那一列的聯賽標誌（img/lg_*.png，96px）內嵌成 data URI：圖檔在主站，主站整點才推上去，中間這段新網站會破圖
    try:
        import base64
        data["lgi"] = {lg: "data:image/png;base64," + base64.b64encode(io.open(os.path.join(ROOT, "img", f"lg_{lg}.png"), "rb").read()).decode()
                       for lg in ("LCK", "LPL", "LEC", "LCS", "CBLOL", "LCP") if os.path.exists(os.path.join(ROOT, "img", f"lg_{lg}.png"))}
    except Exception:
        pass
    io.open(OUT_DATA, "w", encoding="utf-8", newline="\n").write("window.TS_DATA=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
    io.open(OUT_CODE, "w", encoding="utf-8", newline="\n").write(code)
    print(f"轉會網站：隊伍 {len(data['team'])}、評分 {'有' if data.get('rate') else '無'}；"
          f"transfers_site.js {os.path.getsize(OUT_DATA)//1024}KB、transfers_site_code.js {os.path.getsize(OUT_CODE)//1024}KB")


if __name__ == "__main__":
    main()
