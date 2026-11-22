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
OUT_CAR = os.path.join(ROOT, "transfers_career.js")


# 生涯紀錄（使用者 2026-11-22「Calix Deft 這種2026沒打一級聯賽比賽的人 看生涯紀錄」）：
#   陣容表上今年沒有出賽資料的選手（Deft、Calix）⇒ 評分＝最後一個有出賽的年份的整年評分（主站同一個 calcPlayers、篩選全清），
#   英雄池＝career.js 的生涯總場數前三。結果寫 transfers_career.js（主站讀）＋ TS_DATA.car（轉會網站讀）
NEED_JS = r"""()=>{ const D=window.TRANSFERS||{}, R=window._tbRC||{}, Y=R.yr||{}, have=new Set(Object.values(Y).flatMap(o=>Object.keys(o))), out={};
  (D.board||[]).forEach(t=>Object.entries(t.r||{}).forEach(([r,es])=>{ if(r==="COACH")return; es.forEach(e=>{ const k=String(e.n||"").replace(/\s*\([^()]*\)\s*$/,"").toLowerCase(); if(k&&!have.has(k))out[k]=r; }); }));
  return out; }"""
CALC_JS = r"""(names)=>{ const sv={split:F.split,league:F.league,patch:F.patch,d1:F.d1,d2:F.d2,minG:F.minG}, svH=H2H, out={};
  F.split=""; F.league="ALL"; F.patch=""; F.d1=""; F.d2=""; F.minG=0; H2H=null;
  try{ for(const r of ["TOP","JNG","MID","BOT","SUP"])calcPlayers(r,true).forEach(x=>{ const k=String(x._pn||"").toLowerCase(); if(!names.includes(k)||x.評分==null)return;
      if(!out[k]||out[k].g<x.場數)out[k]={sc:+x.評分.toFixed(1),g:x.場數,r}; }); }
  finally{ H2H=svH; Object.assign(F,sv); }
  return out; }"""


def career_scores(b, need, cur_year):
    """need＝{小寫名: 路線}；回傳 {小寫名: {y, sc, g, r, ch:[英雄id…]}}。每個人從 career.js 的最後出賽年往前找（最多三年）"""
    try:
        t = io.open(os.path.join(ROOT, "career.js"), encoding="utf-8").read()
        CA = json.loads(t[t.index("=") + 1:].strip().rstrip(";"))
    except Exception as e:
        print(f"   生涯：career.js 讀不到（{type(e).__name__}），略過")
        return {}
    P = {k.lower(): v for k, v in (CA.get("p") or {}).items()}
    years = sorted(int(y) for y in CA.get("y") or [])
    todo = {}
    for k in need:
        v = P.get(k)
        if not v or not v.get("l"):
            continue
        ly = min(int(str(v["l"])[:4]), cur_year - 1)
        todo[k] = [y for y in range(ly, ly - 3, -1) if y in years]
    out = {}
    for _ in range(3):
        by_y = {}
        for k, ys in todo.items():
            if k not in out and ys:
                by_y.setdefault(ys.pop(0), []).append(k)
        if not by_y:
            break
        for y, names in sorted(by_y.items()):
            pg = b.new_page(viewport={"width": 1400, "height": 900})
            try:
                pg.goto(f"http://127.0.0.1:{PORT}/index.html?y={y}&view=%E9%81%B8%E6%89%8B", wait_until="load", timeout=300000)
                pg.wait_for_function(f"typeof GAMES!=='undefined'&&GAMES.length>0&&+curYear==={y}", timeout=300000)
                pg.wait_for_timeout(1500)
                res = pg.evaluate(CALC_JS, names)
                for k, v in res.items():
                    c = (P.get(k) or {}).get("c") or {}
                    top = sorted(c.items(), key=lambda kv: (-kv[1][0], kv[0]))[:3]
                    v["ch"] = pg.evaluate("(ns)=>ns.map(n=>champId(n))", [n for n, _ in top])
                    v["y"] = y
                    out[k] = v
            except Exception as e:
                print(f"   生涯：{y} 年失敗（{type(e).__name__} {str(e)[:80]}）")
            finally:
                pg.close()
    print(f"   生涯紀錄：今年沒出賽 {len(need)} 人、找到往年評分 {len(out)} 人")
    return out

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
    # 轉會網站：「一隊一張卡」的手機版面用到內容寬 1000 以下（主站是 760 以下）。內容寬 760～999 的表格每欄只剩 70px 上下，
    #   名字會從中間斷行（JackeyLov／e、ShowMak／er）、自由人那一列高到六百多 px（使用者 2026-11-22「全做」——整體檢視的建議）。
    #   只改轉會網站匯出的這一份 CSS；主站的版面是整頁縮放，切換點不動。外掛裡 html.tsDesk 的門檻也跟著是 1000
    _mq = "@container mainc (max-width:759.98px)"
    if css.count(_mq) < 1:
        raise SystemExit("index.html 的 CSS 找不到手機版面那一段（" + _mq + "）")
    css = css.replace(_mq, "@container mainc (max-width:999.98px)")
    shim = r'''
// ── 轉會網站外掛（scripts/export_transfer_site.py 產生，勿手改）：只提供轉會分頁用到的最小全域 ──
(function(){
const TS=window.TS_DATA||{}; window.TRANSFER_RATE=TS.rate||null; window.TR_CAREER=TS.car||null;
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
  // 五顆小按鈕重新設計（使用者 2026-11-20「五個小按鈕重新設計一下 好看一點」；只改轉會網站，主站的基礎按鈕全站一致不動）：
  //   說明／重設／截圖＝同一套線條圖示（原本是三種長相不同的 emoji），深色圓角方塊；Facebook／Discord＝同尺寸同圓角的品牌色；滑過變亮、按下微縮
  // 2026-11-21 使用者「小按鈕裡面的圖示要置中 然後要圓潤化清晰化 不要看起來很粗糙」：用一般螢幕（100%／125% 縮放）實際截圖放大看，原本的問題是
  //   ①圖示 19px 放在 34px 的按鈕裡，左右各 7.5px＝落在半個像素上，整個圖會糊、看起來也偏一點 ②線寬 1.9 縮到 19px 只剩 1.5px，斜線斷斷續續。
  //   ⇒ 線加粗到 2、圓角接頭與圓角機身，圖示改成偶數尺寸（22px；手機 20px）讓它落在整數像素上，圖案的外框都在 24 格的正中間
  // 2026-11-21 晚再修「小按鈕內的圖示感覺邊緣有點鋸齒」：22px 是把 24 格的圖縮成 0.917 倍，2px 的線變 1.83px、每條線的邊都落在小數像素上，
  //   直線一邊實一邊虛、圓與斜線的階梯特別明顯。⇒ 圖示改用 24px 原尺寸（34px 的按鈕左右各留 5px，仍是整數），線寬剛好 2px，
  //   直線、橫線的中心都放在整數格（x＝12、y＝4、y＝9…），圓的半徑用整數；Discord 22px（左右各 6px）
  const SV=d=>`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" shape-rendering="geometricPrecision" aria-hidden="true">${d}</svg>`;
  const IC={help:SV('<circle cx="12" cy="12" r="9"/><path d="M12 11v6"/><circle cx="12" cy="7.5" r="1.3" fill="currentColor" stroke="none"/>'),
    reset:SV('<path d="M20 12a8 8 0 1 1-2.34-5.66"/><path d="M20 4v5h-5"/>'),
    shot:SV('<path d="M5.2 7.5h2.3l1.2-1.8a1.2 1.2 0 0 1 1-.53h4.6a1.2 1.2 0 0 1 1 .53l1.2 1.8h2.3a1.9 1.9 0 0 1 1.9 1.9v7.5a1.9 1.9 0 0 1-1.9 1.9H5.2a1.9 1.9 0 0 1-1.9-1.9V9.4a1.9 1.9 0 0 1 1.9-1.9z"/><circle cx="12" cy="13" r="3.2"/>'),
    share:SV('<path d="M21 4H3l6.5 6.5L12 20z"/><path d="M21 4 9.5 10.5"/>')};   // 紙飛機（使用者 2026-11-21「分享的按鈕圖 要跟 IG 分享的那圖案一樣」）；主站 index.html 的 #trShare 是同一個形狀
  if(!document.getElementById("tsBtnCss")){ const st=document.createElement("style"); st.id="tsBtnCss";
    st.textContent=`.trBar .sqbtn,.trBar #trDc,.trBar #trFb{width:34px!important;height:34px!important;min-width:34px!important;padding:0!important;border-radius:10px!important;display:inline-flex!important;align-items:center;justify-content:center;box-shadow:none!important;font-size:0!important;line-height:0!important;transition:transform .12s,background .12s,border-color .12s,filter .12s;-webkit-tap-highlight-color:transparent}
.trBar button.sqbtn{background:#1a2234!important;border:1px solid rgba(255,255,255,.14)!important;color:#c9d4ea!important}
.trBar button.sqbtn:hover{background:#243049!important;border-color:rgba(122,184,255,.6)!important;color:#fff!important}
.trBar button.sqbtn:disabled{opacity:.45}
.trBar #trDc,.trBar #trFb{border:1px solid rgba(255,255,255,.18)!important}
.trBar #trDc:hover,.trBar #trFb:hover{filter:brightness(1.14)}
.trBar .sqbtn:active,.trBar #trDc:active,.trBar #trFb:active{transform:scale(.93)}
#tsHelpBox .tsHpHd{position:sticky;top:0;z-index:2;display:flex;align-items:center;min-height:46px;margin-bottom:8px;background:#1b2338;white-space:nowrap;font-size:17px;font-weight:800;color:#e8ecf4;border-bottom:1px solid rgba(255,255,255,.1)}
#tsHelpBox .tsHpHd b{flex:1;font-weight:800}
#tsHelpBox .tbTipX{position:static;flex:0 0 auto;margin-right:-10px}
.trBar .sqbtn svg,.trBar #trDc svg,.trBar #trFb svg{width:24px;height:24px;display:block;flex:0 0 auto}
.trBar #trDc svg{width:22px;height:22px}
.trBar .cwrap .cx::after{content:"";position:absolute;inset:-10px -6px -10px -10px}
@media (max-width:400px){.trBar .sqbtn,.trBar #trDc,.trBar #trFb{width:30px!important;height:30px!important;min-width:30px!important;border-radius:9px!important}.trBar .sqbtn svg,.trBar #trFb svg{width:20px;height:20px}.trBar #trDc svg{width:18px;height:18px}}`;
    document.head.appendChild(st); }
  f.insertAdjacentHTML("beforeend",b("tsHelp",IC.help,LANG==="en"?"About this page":"本頁說明")+b("tsReset",IC.reset,LANG==="en"?"Reset filters":"重設篩選"));
  { const sh=document.getElementById("trShot"); if(sh)sh.innerHTML=IC.shot; const sr=document.getElementById("trShare"); if(sr)sr.innerHTML=IC.share; }
  // 電腦版：頁首、篩選列、欄名列往下捲時都留在上方（使用者 2026-11-21「這列以上包括這列 往下滑時都應該維持在上方」）
  //   三層都 sticky，下面兩層的 top＝上面幾層的高度（量出來寫進 CSS 變數；視窗大小變了重量）；篩選列下方的空隙用同色陰影蓋住，列才不會從縫裡露出來
  //   卡片（陣容表／消息表）在電腦版改成單色 #161c2b（原本是 #161c2b→#121722 的直向漸層）：欄名列黏在上方時底色是固定的一個顏色，
  //   卡片卻越往下越深 ⇒ 捲到下面時欄名列比左右兩側的卡片內距亮 5～8 階，像貼了一塊色塊（使用者 2026-11-21「電腦版的這列 背景色怪怪的」；頂端對了、捲下去還是錯）。
  //   欄名列的底色不要加 !important：截圖複本靠行內 background:none 把它變透明，加了會在截圖上畫出色塊
  // 2026-11-21 晚「整體檢視新網站」查到兩個錯位，一起改：
  //   ①這一組規則原本包在 @media (min-width:760px)，但版面是照 main 的內容寬度切換的（CSS 的 @container mainc，760 以下＝手機版面；
  //     main 左右各有 30px 內距 ⇒ 視窗大約 829px 才換成電腦版面）。兩個切換點對不上：視窗 760～828 是手機版面卻黏著頁首＋四行的篩選列（250px）。
  //     ⇒ 改成 html.tsDesk 這個類別（_tsStick 每次照 main 的內容寬度決定），跟版面切換完全同步
  //   ②窄版面（main 內容寬 ≤820）主站有一條通用規則 .card{overflow-x:auto}。卡片一變成捲動容器，裡面 position:sticky 的列就改成「對卡片」定位：
  //     視窗 829～889（iPad Air／Pro 11 直放、或把瀏覽器拉成半個螢幕）欄名列的 top 被當成離卡片上緣的距離 ⇒ 整列被推到表格中間、蓋住一隊；
  //     手機版的聯賽標題列（.tbLg）與消息的日期列（.trDay）寫了 sticky 也黏不住。陣容表與消息表在窄版面都會自己換行、不需要橫向捲動
  //     ⇒ 這兩張卡固定 overflow:visible（只改轉會網站；主站的版面是整頁縮放，不會進到這幾種寬度）
  // 2026-11-22 使用者「平板那個調整」：卡片版面用到內容寬 1000 以下之後，平板與窄視窗的篩選列是手機那套「一組一整排」，五排共 200px，
  //   平板橫放佔掉三分之一個畫面 ⇒ 內容寬 700～999 改成兩排：第一排＝陣容表／消息＋六個賽區＋排序；第二排＝顯示（或狀態）＋搜尋＋小按鈕（排序放第二排的話，直放 820 寬最後一顆小按鈕會被擠到第三排）
  //   規則跟兩欄卡片寫在同一個 @container 裡
  if(!document.getElementById("tsStickCss")){ const st=document.createElement("style"); st.id="tsStickCss";
    st.textContent=`html.tsDesk #tsHdr{position:sticky;top:0;z-index:40;background:#0b0e14}
html.tsDesk #tsCover{display:block;position:fixed;left:0;right:0;top:0;height:calc(var(--tsH1,0px) + var(--tsG1,0px) + var(--tsH2,0px) + var(--tsG0,0px));background:#0b0e14;z-index:37;pointer-events:none}
html.tsDesk .filters.trBar{position:sticky;top:calc(var(--tsH1,0px) + var(--tsG1,0px));z-index:39}
html.tsDesk .card.tbBoard,html.tsDesk .card.trList{background:#161c2b}
html.tsDesk .tbBoard>.tbHd{top:calc(var(--tsH1,0px) + var(--tsG1,0px) + var(--tsH2,0px) + var(--tsG,0px))!important;z-index:38!important;background:var(--tsCB,#161c2b);box-shadow:0 calc(var(--tsG0,0px) - var(--tsG,0px)) 0 0 var(--tsCB,#161c2b)}
html.tsDesk .trList>.trHead{position:sticky;top:calc(var(--tsH1,0px) + var(--tsG1,0px) + var(--tsH2,0px) + var(--tsG,0px));z-index:38;background:var(--tsCB,#161c2b);box-shadow:0 calc(var(--tsG0,0px) - var(--tsG,0px)) 0 0 var(--tsCB,#161c2b)}
.card.tbBoard,.card.trList{overflow:visible}
@container mainc (min-width:700px) and (max-width:999.98px){.tbBoard{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));column-gap:10px}.tbBoard>.tbRow{grid-column:auto}.tbBoard>.tbLg,.tbBoard>.tbFA,.tbBoard>.sumEmpty{grid-column:1/-1}.trBar>.trFG:nth-child(1){flex:0 0 200px}.trBar>.trFG:nth-child(2){flex:1 1 calc(100% - 210px)}.trBar:has(.fgSort)>.trFG:nth-child(2){flex:1 1 calc(100% - 336px)}.trBar .trFG.fgSort{order:0;flex:0 0 120px}.trBar>.trFG:nth-child(3){order:1;flex:1 1 330px}.trBar .trFG.fgSt{flex:1 1 330px}.trBar:has(.fgSort) .cwrap,.trBar .cwrap{flex:1 1 130px;min-width:100px}}
#tsTop{position:fixed;right:12px;bottom:calc(14px + env(safe-area-inset-bottom,0px));z-index:35;width:42px;height:42px;padding:0;border-radius:12px;border:1px solid rgba(255,255,255,.2);background:rgba(26,34,52,.94);color:#e8ecf4;display:none;align-items:center;justify-content:center;box-shadow:0 4px 14px rgba(0,0,0,.5);cursor:pointer;-webkit-tap-highlight-color:transparent}
#tsTop.on{display:flex}#tsTop svg{width:22px;height:22px;display:block}#tsTop:active{transform:scale(.93)}
#tsCap{position:fixed;height:14px;overflow:hidden;z-index:37;pointer-events:none}#tsCap>i{position:absolute;left:0;right:0;top:0;height:60px;box-sizing:border-box;box-shadow:0 0 0 40px #0b0e14}
html:not(.tsDesk) #tsCover,html:not(.tsDesk) #tsCap{display:none}`;
    document.head.appendChild(st);
    window._tsStick=()=>{ const hd=document.getElementById("tsHdr"), bar=document.querySelector(".filters.trBar"), bd=document.querySelector(".tbBoard,.trList"), R=document.documentElement.style; if(!hd||!bar)return;
      { const mc=getComputedStyle(main); document.documentElement.classList.toggle("tsDesk",main.clientWidth-parseFloat(mc.paddingLeft)-parseFloat(mc.paddingRight)>=1000); }   // 電腦版面才黏（跟 CSS 切換卡片版面的依據同一個：main 的內容寬度 1000；見 build_code 把 759.98 換成 999.98 那段）
      const sy=scrollY; R.setProperty("--tsH1",hd.offsetHeight+"px"); R.setProperty("--tsH2",bar.offsetHeight+"px");
      // 捲動後三層之間的空隙要跟頁面最上面時一模一樣（使用者 2026-11-21「往下滑的時候 上方還是有小部分的縮起」：原本頁首與篩選列之間 14px、篩選列與欄名列之間 7px 會被吃掉）
      //   ⇒ 在最上面時量兩段空隙（頁首→篩選列、篩選列→欄名列），sticky 的 top 把空隙算進去，空隙用同色陰影蓋住
      if(sy<4){ const hh=document.querySelector(".tbBoard>.tbHd,.trList>.trHead")||bd;
        R.setProperty("--tsG1","0px"); R.setProperty("--tsG","0px");   // 先歸零再量：變數一旦比實際空隙大，篩選列／欄名列會被推離原位，量到的空隙就把位移也算進去，之後每量一次多一截
        R.setProperty("--tsG1",Math.max(0,Math.round(bar.getBoundingClientRect().top-hd.getBoundingClientRect().bottom))+"px");
        // 空隙用一塊固定在最上面的底色板蓋住（#tsCover，疊在欄名列之下），不再用篩選列的陰影——陰影會跟著圓角長出一塊方方的黑邊（使用者 2026-11-21「捲動的時候 上面介面的邊緣變得不圓滑」）
        if(!document.getElementById("tsCover")){ const c=document.createElement("div"); c.id="tsCover"; document.body.appendChild(c); const k=document.createElement("div"); k.id="tsCap"; k.innerHTML="<i></i>"; document.body.appendChild(k); }
        // 捲動後那張表的上緣也要是圓角（表本身的上緣已經捲到底色板後面）⇒ 在同一個位置畫一段一模一樣的「卡片上緣」（邊框、圓角、底色都讀自那張表）
        //   （位置與樣式在下面每次都重算，這裡只負責建立元素與量空隙）
        if(bd){ R.setProperty("--tsG0",Math.max(0,Math.round(bd.getBoundingClientRect().top-bar.getBoundingClientRect().bottom))+"px"); const c2=getComputedStyle(bd), cb=(/rgb\([^)]*\)/.exec(c2.backgroundImage)||[c2.backgroundColor])[0]; if(cb&&!/rgba\(0, 0, 0, 0\)|transparent/.test(cb))R.setProperty("--tsCB",cb); }   // 欄名列與它上方那一小條的底色＝卡片上緣的顏色（卡片是漸層，取第一個顏色；跟 #tsCap 同一個來源）——原本讀 backgroundColor 是透明的，結果退回預設色，跟卡片、欄名列各差一階（使用者 2026-11-21「電腦版的這列 背景色怪怪的」）
        if(hh)R.setProperty("--tsG",Math.max(0,Math.round(hh.getBoundingClientRect().top-bar.getBoundingClientRect().bottom))+"px");
        if(bd)window._tsStick.g=[Math.max(0,Math.round(bar.getBoundingClientRect().top-hd.getBoundingClientRect().bottom)),Math.max(0,Math.round(bd.getBoundingClientRect().top-bar.getBoundingClientRect().bottom))]; }
      // 卡片上緣那一段（#tsCap）每次都重算：原本只在頁面最上面時算一次 ⇒ 捲下去之後縮放網頁（Ctrl +／−）或改視窗大小，篩選列換了行數、卡片換了寬度，
      //   它還停在舊的位置與寬度——橫在篩選列中間、右邊凸出一截，卡片上緣也沒有圓角（使用者 2026-11-21「縮放網頁比例後 篩選列會跑掉歪掉」）。
      //   左右照卡片現在的位置；上緣＝卡片在頁面最上面時的位置＝頁首高＋空隙＋篩選列高＋空隙（空隙是固定的版面距離，在最上面時量好存在 _tsStick.g）
      { const k=document.getElementById("tsCap"); if(k&&bd){ const q=k.firstChild, c=getComputedStyle(bd), r=bd.getBoundingClientRect(), g=window._tsStick.g||[0,0];
          k.style.left=r.left+"px"; k.style.width=r.width+"px"; k.style.top=(sy<4?r.top:hd.offsetHeight+g[0]+bar.offsetHeight+g[1])+"px"; k.style.height=c.borderTopLeftRadius;
          q.style.border=c.borderTopWidth+" solid "+c.borderTopColor; q.style.borderRadius=c.borderTopLeftRadius; q.style.background=(/rgb\([^)]*\)/.exec(c.backgroundImage)||[c.backgroundColor])[0]; } } };
    addEventListener("resize",()=>window._tsStick());
    // 一開始就在捲動中的位置（重新整理後瀏覽器還原捲動位置）量不到空隙 ⇒ 第一次回到最上面時補量
    addEventListener("scroll",()=>{ if(scrollY<4&&!window._tsStick.g)window._tsStick(); },{passive:true}); }
  window._tsStick(); setTimeout(window._tsStick,300);
  // 說明＝懸浮顯示（使用者 2026-11-20「手機的說明鈕點擊後也是懸浮顯示」）：手機從底部浮上來（跟格子小框同款）、桌面在右上；點 ✕ 或外面關閉
  document.getElementById("tsHelp").onclick=ev=>{ ev.stopPropagation(); let d=document.getElementById("tsHelpBox"); if(d){ d.remove(); return; }
    const mob=matchMedia("(max-width:760px)").matches;
    d=document.createElement("div"); d.id="tsHelpBox";
    d.style.cssText="position:fixed;z-index:10000;background:#1b2338;border:1px solid rgba(255,255,255,.14);box-shadow:0 8px 30px rgba(0,0,0,.6);color:#e8ecf4;line-height:1.75;font-size:14.5px;white-space:pre-line;overflow:auto;overscroll-behavior:contain;"
      +(mob?"left:8px;right:8px;bottom:8px;max-height:72vh;padding:0 14px 14px;border-radius:14px":"right:16px;top:64px;width:min(560px,92vw);max-height:80vh;padding:0 18px 16px;border-radius:10px");
    // 最上面一條標題列黏在頂端、X 放在它的右端：說明很長要捲動時 X 不會跟著捲走（原本 X 是絕對定位在內容裡，一捲就不見；
    //   使用者 2026-11-21「所有小框的X位置不要跑掉 然後大一點 然後背景不要用圓形底色 直接X就好」）。X 的長相跟格子小框共用 .tbTipX
    d.innerHTML=`<div class="tsHpHd"><b>${LANG==="en"?"About this page":"本頁說明"}</b><button class="tbTipX" aria-label="close">✕</button></div>`+((LANG==="en"?HELP.en:HELP.zh)||"");
    document.body.appendChild(d); d.querySelector(".tbTipX").onclick=()=>d.remove(); };
  if(!window._tsHelpOut){ window._tsHelpOut=1; document.addEventListener("click",e=>{ const d=document.getElementById("tsHelpBox"); if(d&&!e.target.closest("#tsHelpBox")&&!e.target.closest("#tsHelp"))d.remove(); }); }
  document.getElementById("tsReset").onclick=()=>{ Object.assign(V,{trSrc:"",trSt:"",trRg:"",trKd:"",trQ:"",tbF:"",tbSort:""}); saveState(); render(); }; }
function render(){
/*__BLOCK__*/
addBase();
const at=document.getElementById("tsAt"), T0=window.TRANSFERS||{}; if(at&&T0.at)at.textContent=(LANG==="en"?"as of ":"截至 ")+T0.at; }
// 換語言＝整頁重新載入。瀏覽器重新載入時是照「原本畫面上那個元素現在的位置」還原捲動位置；兩種語言的篩選列高度不同（英文多一行）
//   ⇒ 明明在最上面換的語言，載入後頁面卻被捲下去 35px，第一個聯賽標題列被欄名列蓋住。這一次不還原、從最上面開始，之後再交還給瀏覽器
const ls=document.getElementById("tsLang"); if(ls){ ls.value=LANG; ls.onchange=()=>{ try{localStorage.setItem("ts_lang",ls.value);}catch(e){}
  try{ sessionStorage.setItem("ts_top","1"); history.scrollRestoration="manual"; }catch(e){} location.reload(); }; }
try{ if(sessionStorage.getItem("ts_top")){ sessionStorage.removeItem("ts_top"); scrollTo(0,0); setTimeout(()=>{ try{ history.scrollRestoration="auto"; }catch(e){} },1500); } }catch(e){}
render();
// 回到最上面（使用者 2026-11-22「全做」）：卡片版面（手機／平板）篩選列不會跟著捲，陣容表一萬多 px、消息更長，換篩選要一路滑回去。
//   捲超過一個多畫面才出現；電腦版面篩選列本來就黏在上面，不顯示
(()=>{ const b=document.createElement("button"); b.id="tsTop"; b.title=LANG==="en"?"Back to top":"回到最上面"; b.setAttribute("aria-label",b.title);
  b.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19V6"/><path d="M5.5 12.5 12 6l6.5 6.5"/></svg>';
  b.onclick=()=>scrollTo({top:0,behavior:"smooth"}); document.body.appendChild(b);
  const up=()=>b.classList.toggle("on",scrollY>innerHeight*1.2&&!document.documentElement.classList.contains("tsDesk")); addEventListener("scroll",up,{passive:true}); addEventListener("resize",up); up(); })();
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
  return {rate:R?{pl:R.pl,plY:R.plY||{},R:R.R||{},md:R.md,tm:R.tm,wr:R.wr||{},s3:R.s3||{},sw:R.sw||{},swY:R.swY||{},cp:R.cp||{},yr:R.yr||{},ch:R.ch||{}}:null, team, ab, lgc:LGC, pos:POS_IMG,
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
            try:
                need = pg.evaluate(NEED_JS)
                cy = pg.evaluate("+curYear")
                data["car"] = career_scores(b, need, cy) if need else {}
            except Exception as e:
                print(f"   生涯紀錄失敗（略過）：{type(e).__name__} {str(e)[:100]}")
                data["car"] = {}
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
    # 消息按鈕的小圖（img/news_faker.png）一樣內嵌；檔案還沒放就不帶，前端退回 📰
    try:
        _p = os.path.join(ROOT, "img", "news_faker.png")
        if os.path.exists(_p):
            import base64
            _raw = io.open(_p, "rb").read()
            try:   # 原圖 180px、畫面上只顯示 17～20px：內嵌的這一份縮到 72px（3 倍螢幕也夠），省四十幾 KB；img/ 裡的原檔不動
                from PIL import Image
                _im = Image.open(io.BytesIO(_raw)).convert("RGBA"); _im.thumbnail((72, 72), Image.LANCZOS)
                _buf = io.BytesIO(); _im.save(_buf, "PNG", optimize=True)
                if len(_buf.getvalue()) < len(_raw):
                    _raw = _buf.getvalue()
            except Exception:
                pass
            data["nic"] = "data:image/png;base64," + base64.b64encode(_raw).decode()
    except Exception:
        pass
    io.open(OUT_DATA, "w", encoding="utf-8", newline="\n").write("window.TS_DATA=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
    io.open(OUT_CODE, "w", encoding="utf-8", newline="\n").write(code)
    io.open(OUT_CAR, "w", encoding="utf-8", newline="\n").write("window.TR_CAREER=" + json.dumps(data.get("car") or {}, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print(f"轉會網站：隊伍 {len(data['team'])}、評分 {'有' if data.get('rate') else '無'}；"
          f"transfers_site.js {os.path.getsize(OUT_DATA)//1024}KB、transfers_site_code.js {os.path.getsize(OUT_CODE)//1024}KB")


if __name__ == "__main__":
    main()
