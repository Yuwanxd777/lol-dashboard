(function(){var st=document.createElement("style");st.textContent=":root{\n    --bg:#0b0e14; --card:#141926; --card2:#1c2333; --line:#2a3345;\n    --tx:#e8ecf4; --tx2:#8b98ad; --acc:#4f8ef7; --acc2:#7c5cff; --gold:#f5b942;\n    --green:#5dd39e; --red:#e05c5c; --gap:14px; \n  }\n*{box-sizing:border-box}\nhtml,body{overflow-x:clip}\nhtml{scrollbar-gutter:stable}\n@font-face{font-family:\"GenSenRounded TW\";font-weight:400;src:url(\"fonts/GenSenRounded2TW-L.woff2\") format(\"woff2\"),url(\"fonts/GenSenRounded2TW-L.otf\") format(\"opentype\");font-display:swap;\n    ascent-override:106.7%;descent-override:26.7%;line-gap-override:0%}\n@font-face{font-family:\"GenSenRounded TW\";font-weight:700;src:url(\"fonts/GenSenRounded2TW-R.woff2\") format(\"woff2\"),url(\"fonts/GenSenRounded2TW-R.otf\") format(\"opentype\");font-display:swap;\n    ascent-override:106.7%;descent-override:26.7%;line-gap-override:0%}\nbody{margin:0;color:var(--tx);font-family:\"jf-openhuninn\",\"Microsoft JhengHei\",\"Segoe UI\",sans-serif;font-size:16.5px;\n    background:var(--bg)}\nbody::before{content:\"\";position:fixed;inset:0;z-index:-1;pointer-events:none;\n    background:radial-gradient(1200px 500px at 15% -10%,#1a2340 0%,transparent 60%),\n               radial-gradient(1000px 500px at 95% 0%,#241a3d 0%,transparent 55%)}\n::-webkit-scrollbar{width:9px;height:9px}\n::-webkit-scrollbar-thumb{background:#2e3a52;border-radius:9px}\n::-webkit-scrollbar-track{background:transparent}\n.filters select,.filters input{height:30px;box-sizing:border-box;padding-top:3px;padding-bottom:3px;line-height:1.2}\n.filters .pgbtn,.filters .pgbtn *{height:30px;box-sizing:border-box}\n.filters .pgbtn{padding-top:3px;padding-bottom:3px;line-height:1.2;display:inline-flex;align-items:center}\nheader{display:flex;align-items:center;gap:14px;padding:12px 30px;position:sticky;top:0;z-index:100;flex-wrap:wrap;\n    background:rgba(15,19,30,.85);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}\nheader h1{font-size:21px;margin:0;display:flex;align-items:center;background:linear-gradient(90deg,#7cb3ff,#b79bff);\n    -webkit-background-clip:text;background-clip:text;color:transparent;letter-spacing:.5px}\n.meta{color:var(--tx2);font-size:13.5px}\nmain{max-width:none;margin:0;padding:14px 30px;container-type:inline-size;container-name:mainc}\n#main img{translate:0 1px}\n.filters .tab{cursor:pointer;border:1px solid var(--line);border-radius:999px;transition:border-color .12s,color .12s}\n.filters .tab:hover:not(.on){border-color:var(--acc);color:var(--acc)}\n.filters .tab.on{color:#fff}\n.filters .posLbl .posic{width:22px;height:22px}\n.filters{display:flex;flex-wrap:wrap;gap:10px 11px;align-items:center;border:1px solid var(--line);\n    border-radius:14px;padding:12px 18px;margin-bottom:var(--gap);background:linear-gradient(180deg,#161c2b,#131826)}\n.filters label{color:var(--tx2);font-size:15px}\n.filters select,.filters input{font-size:15px}\n.bpFRow .fsel.hasV:hover,.bpFRow input.bpColF.on:hover{cursor:pointer;background-image:linear-gradient(#e0574d,#e0574d);background-repeat:no-repeat;background-size:calc(100% - 12px) 2px;background-position:center}\nselect,input,textarea,button{background:var(--card2);color:var(--tx);border:1px solid var(--line);\n    border-radius:9px;padding:8px 12px;font-family:inherit;font-size:15.5px;outline:none}\nselect:focus,input:focus,textarea:focus{border-color:var(--acc)}\nbutton{cursor:pointer;transition:.15s}\nbutton:hover{border-color:var(--acc)}\nbutton.primary{background:linear-gradient(135deg,var(--acc),var(--acc2));border-color:transparent;color:#fff;font-weight:bold}\nbutton.primary:hover{filter:brightness(1.15)}\n.sqbtn{width:30px;height:30px;padding:0;font-size:15px;line-height:1;flex:0 0 auto;\n    display:inline-flex;align-items:center;justify-content:center}\n.grid .card{margin-bottom:0}\n.grid>*{min-width:0}\n@media(max-width:820px){header{padding:8px 10px;gap:8px}\nheader h1{font-size:17px}\nheader h1 img{width:26px!important;height:26px!important}\nmain{padding:10px}}\n@media(max-width:1099.98px){.filters .barBtns{flex-wrap:wrap;justify-content:flex-end;max-width:100%;row-gap:6px}\nheader{position:static;padding:8px 10px 6px}}\n@container mainc (max-width:820px){.filters{padding:8px 10px;gap:8px}\n.tphdr{padding-right:0!important}\n.tpctl{position:static!important;flex-wrap:wrap;margin-bottom:6px}\n.card{overflow-x:auto}\n.card table{table-layout:auto;width:max-content;min-width:100%}}\n.card{background:linear-gradient(180deg,#161c2b,#121722);border:1px solid var(--line);border-radius:14px;\n    padding:16px;margin-bottom:var(--gap);box-shadow:0 4px 24px rgba(0,0,0,.35)}\n.card h2{font-size:19px;margin:0 0 12px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}\n.card h2 .sub{color:var(--tx2);font-weight:normal;font-size:15.5px}\ntable.tblEven td:has(.heroname){padding-left:11px}\n.tblwrap{overflow:visible;border:1px solid var(--line);border-radius:10px;background:#161c2b}\n.tblwrap table{table-layout:auto;width:max-content;min-width:100%}\n#main[data-view=\"英雄\"] .tblwrap table,#main[data-view=\"選手\"] .tblwrap table,#main[data-view=\"戰隊\"] .tblwrap table{min-width:0}\n.tblwrap.hscroll{overflow-x:auto}\n.tblwrap.hscroll th{top:0}\n.tblwrap.pt1 th,.tblwrap.pt1 td{padding-left:4px;padding-right:4px}\n.tblwrap.pt2 th,.tblwrap.pt2 td{padding-left:2px;padding-right:2px}\n#tierPool.tpNarrow .tphdr{padding-right:0!important}\n#tierPool.tpNarrow .tpctl{position:static!important;margin-top:6px;justify-content:flex-start}\n.tLaneIco.tLPn .cx{display:none!important}\n.tLaneIco.tLPn input{padding-right:8px!important;padding-left:8px!important}\n@media(pointer:coarse){select,input,textarea{font-size:16px!important}\n#tierPool .tphdr{padding-right:0!important}\n#tierPool .tpctl{position:static!important;margin-top:6px;justify-content:flex-start}\n.tblwrap{-webkit-overflow-scrolling:touch}}\n@container mainc (max-width:1980px){table.tblEven td:has(.heroname){padding-left:7px}}\ntable.tblEven .thL{padding:0}\ntable.tblEven .sortArr{right:-12px}\n@keyframes sp{to{transform:rotate(360deg)}}\n.cc:has(>img.glow)>.po,#main[data-view=\"比賽BP\"] .cc:hover>.po{z-index:4;transform:translate(1.25px,-1.25px)}\ninput[type=number]::-webkit-outer-spin-button,input[type=number]::-webkit-inner-spin-button{-webkit-appearance:none;margin:0}\ninput[type=number]{-moz-appearance:textfield;appearance:textfield}\n.cwrap{position:relative;display:inline-flex;align-items:center}\n.cwrap .combo{padding-right:26px}\n.cx{position:absolute;right:5px;background:none;border:none;color:var(--tx2);padding:0 3px;font-size:13px;cursor:pointer;line-height:1}\n.cx:hover{color:#ff6b6b}\ninput.combo::-webkit-calendar-picker-indicator,input[list]::-webkit-calendar-picker-indicator{display:none!important;opacity:0;width:0}\n.cwrap .cal{position:absolute;right:24px;background:none;border:none;cursor:pointer;font-size:13px;padding:0 2px;line-height:1}\n.cwrap .cal:hover{filter:brightness(1.4)}\n.rosterGrid .card{margin-bottom:0;padding:20px}\n.rosterGrid .card{overflow-x:auto}\n.laneHd .meta{font-size:25px}\n.chgLanes .card{margin-bottom:0}\n#hoverTip .scGrid>*{padding:3.5px 0}\n#hoverTip .tipTitle .meta{font-size:13.5px}\n#hoverTip .tipRow .meta{color:#7a8aaa;font-size:11.5px;margin-left:6px}\n#hoverTip .tGrid .rt .v{font-size:22px;font-weight:bold;line-height:1.1}\n.skillsBody .tipTitle .meta{font-size:14px;color:#7a8aaa}\n.skillsBody .tipRow .meta{color:#7a8aaa;font-size:12.5px;margin-left:6px}\n.dexIt .meta{font-size:13.5px}\n.jgCtrl select,.jgCtrl #jgSortBtn{height:30px;box-sizing:border-box;padding-top:3px;padding-bottom:3px;line-height:1.2;font-size:15px}\n.jgHd .jgMeta,.jgHd>.meta{font-size:13.5px!important}\n.sqbtn.helpBtn{width:30px;padding:0}\n.filters .barBtns .sqbtn,.sqbtn.helpBtn{font-size:17px;line-height:1}\n#main[data-view=\"英雄Tier\"] .tChip:hover>img,\n  #main[data-view=\"英雄Tier\"] .tChip>img.tglow, \n  #main[data-view=\"比賽BP\"] .cc:hover img{transform:scale(1.05);position:relative;z-index:3;\n    box-shadow:0 0 5px 3px rgba(255,255,255,.3)}\n#main[data-view=\"英雄Tier\"] .tChip:hover .tlic img,\n  #main[data-view=\"英雄Tier\"] .tChip:has(>img.tglow) .tlic img{transform:scale(1.05);filter:drop-shadow(0 0 4px rgba(255,255,255,.95))}\n#main td:has(.cc:hover),#main th:has(.cc:hover){overflow:visible}\n#main td:has(.cc img.glow),#main td:has(.cc img.glowS),#main td:has(.heroname.chi){overflow:visible}\n#main .dexIt:has(.cc:hover),#main .dexIt:has(.cc img.glow),#main .chgHead:has(.cc:hover),#main .chgHead:has(.cc img.glow){overflow:visible;position:relative;z-index:4}\nbody.bpDragging .bpSlot::before{pointer-events:auto}\nbody.carrying{cursor:grabbing}\nbody.carrying .tierRow{outline:2px dashed rgba(245,185,66,.55);outline-offset:-3px}\n@keyframes bpPulse{0%,100%{box-shadow:0 0 5px rgba(245,185,66,.45)}50%{box-shadow:0 0 14px rgba(245,185,66,.9)}}\n.bpSlot .meta{font-size:12px}\n#tmGrid .card{padding:10px 12px;margin-bottom:0}\n#tmGrid .card h2{margin-bottom:8px}\n#tmGrid .card h2 .lg{font-size:20px;padding:3px 15px}\n#tmGrid .card h2 .sub{font-size:19px}\n#tmGrid tbody .lg{font-size:15.5px}\n.heroname .lg{font-size:inherit}\na.spWiki{color:inherit;text-decoration:none;border-bottom:1px dotted rgba(150,165,195,.55)}\na.spWiki:hover{color:var(--acc);border-bottom-color:var(--acc)}\n.tblwrap th:nth-child(1),.tblwrap td:nth-child(1){position:sticky;left:0;background:#161c2b;z-index:2;min-width:34px}\n.tblwrap th:nth-child(2),.tblwrap td:nth-child(2){position:sticky;left:46px;background:#161c2b;z-index:2}\n.tblwrap thead th:nth-child(1),.tblwrap thead th:nth-child(2){z-index:5}\n.tblwrap tbody tr:nth-child(even) td:nth-child(1),\n  .tblwrap tbody tr:nth-child(even) td:nth-child(2){background:#1a202f}\n.tblwrap tbody tr:hover td:nth-child(1),\n  .tblwrap tbody tr:hover td:nth-child(2){background:#1e2740}\n.lg{display:inline-block;padding:1px 9px;border-radius:999px;font-size:12px;font-weight:bold;background:#141b2b;border:1px solid #33405c}\n.dlyHd .lg{font-size:11.5px;opacity:.62}\nhtml[data-lang=en] .dlyStats{gap:11px}\n.dlyStat .meta{font-size:12px;margin-right:3px}\n.dlyStats .meta{font-weight:400}\n#sqMates .meta{font-size:20px}\n.sqLaneBtn{padding:3px 11px;border-radius:14px;border:1px solid #33405c;background:#141b2b;color:var(--tx2);cursor:pointer;font-size:12.5px}\n.sqLaneBtn.on{background:var(--acc);color:#fff;border-color:var(--acc)}\nhtml[data-lang=\"en\"] .ovChgLb{width:124px}\n.sumEmpty{color:var(--tx2)}\n.ntIt .meta{font-size:12px}\n.ntDoc h1{font-size:22px;margin:0 0 10px}\n.ntDoc a{color:#7fb2ff}\n.ntDoc a.ntTs{font-family:Consolas,monospace;font-size:.92em}\n.tbBoard{padding:6px 16px 14px;display:grid;grid-template-columns:max-content repeat(6,minmax(0,1fr)) minmax(0,1.6fr) max-content;column-gap:0}\n.tbN.tbY,b.tbY{color:#ffc850}\n.tbN.tbNew,b.tbNew{color:#ff5a5a}\n.tbN.tbExp,b.tbExp{color:#5aa9ff}\n.tbN.tbRs,b.tbRs{color:#ff8ec6}\n.tbN.tbPm,b.tbPm{color:#b98cff}\n.tbN.tbOut,b.tbOut{color:#4cd07d}\n.tbOk{color:#4cd07d;font-size:14px;margin-left:2px}\n.tbN.tbGone{text-decoration:line-through;text-decoration-thickness:1px}\n.tbN.tbDim{opacity:.2}\n.tbVacN{font-style:normal;font-size:11px;font-weight:700;color:var(--tx2);margin-left:6px;padding:0 6px;border:1px solid rgba(255,255,255,.2);border-radius:999px;white-space:nowrap}\n.tbLegend .sqLaneBtn b{font-weight:700}\n.tbLgB{display:inline-flex;align-items:center;gap:2px}\n.tbLgSep{font-style:normal;color:var(--tx2);margin:0 3px}\n.tbLegend .sqLaneBtn{margin-right:2px}\n.tbLegend .sqLaneBtn.on{background:rgba(255,255,255,.14);border-color:var(--tx);box-shadow:0 0 0 1px var(--tx) inset}\n.tbLgG .sqLaneBtn:not(.on){background:transparent;border-color:transparent}\n.trFG{display:inline-flex;align-items:center;gap:6px;padding-left:12px;border-left:1px solid rgba(255,255,255,.16)}\n.trFG:first-child{border-left:0;padding-left:0}\n.trFG>label{margin-right:2px}\n.tbLegend{display:inline-flex;gap:6px;align-items:center}\n.trSrc-kr{color:#ff9a6b;background:rgba(255,154,107,.12)}\n.trSrc-ptt{color:#c9d1e0;background:rgba(255,255,255,.08)}\n.trSrc-man{color:#ffd166;background:rgba(255,209,102,.12)}\n.tbLegend{display:inline-flex;gap:12px;align-items:center}\n.tbHd,.tbRow{grid-column:1/-1;display:grid;grid-template-columns:subgrid;align-items:center}\n.tbHd{position:sticky;top:0;z-index:2;background:var(--card,#141a2a);padding:8px 0;border-bottom:1px solid var(--line);font-weight:700;color:var(--tx2);font-size:14px}\n.tbHd>span{display:flex;align-items:center;justify-content:center;gap:4px}\n.tbLg{grid-column:1/-1;display:flex;align-items:baseline;gap:10px;margin:26px 0 6px;padding:8px 14px;border-radius:8px;border-left:5px solid var(--lgc);background:linear-gradient(90deg,color-mix(in srgb,var(--lgc) 22%,transparent),transparent 70%)}\n.tbHd+.tbLg{margin-top:12px}\n.tbLg b{font-size:22px;font-weight:900;letter-spacing:.5px;color:var(--lgc)}\n.tbLg span{font-size:14px;font-weight:700;color:var(--tx)}\n.tbLg i{font-style:normal;font-size:13px;color:var(--tx2);margin-left:auto}\n.tbRow{min-height:44px;border-radius:6px}\n.tbRow:nth-of-type(even){background:rgba(255,255,255,.035)}\n.tbRow:hover{background:rgba(255,255,255,.07)}\n.tbTeam{display:flex;align-items:center;gap:8px;padding:6px 18px 6px 10px;font-weight:800;font-size:16px;white-space:nowrap;border-left:3px solid color-mix(in srgb,var(--lgc,transparent) 70%,transparent)}\n.tbCell{text-align:center;padding:6px 6px;font-size:15px;line-height:1.5;cursor:default}\n.tbRate{min-width:72px;padding:6px 14px;font-variant-numeric:tabular-nums}\n.tbRateH{padding:0 14px}\n.tbUp{color:#ff5a5a}\n.tbDn{color:#3fcf7a}\n.tbCell:hover{background:rgba(122,184,255,.10);border-radius:6px}\n.tbN{white-space:nowrap;display:inline-block}\n.tbN a{color:inherit;text-decoration:none}\n.tbN a:hover{color:#7fb2ff;text-decoration:underline}\n.tbSep{color:var(--tx2);margin:0 3px}\n.tbSr{font-size:12px;font-weight:400;color:var(--tx2);margin-left:4px}\n.tbMuted{color:var(--tx2);opacity:.75}\n#tbTip{position:fixed;z-index:9999;display:none;max-width:340px;padding:10px 12px;border-radius:8px;background:#1b2338;border:1px solid rgba(255,255,255,.14);box-shadow:0 8px 24px rgba(0,0,0,.45);font-size:14px;line-height:1.6;color:var(--tx);pointer-events:none}\n#tbTip hr{border:0;border-top:1px solid rgba(255,255,255,.1);margin:6px 0}\n.tbRum{font-size:12px;padding:0 6px;border-radius:4px;background:rgba(255,200,80,.16);color:#ffc850}\n#tbTip:has(.tpBox){max-width:420px;padding:12px 14px}\n.tpBox{min-width:260px}\n.tpBox .rtHd{border-bottom-color:color-mix(in srgb,var(--lgc) 45%,transparent)}\n.tpLane{display:inline-flex;align-items:center;gap:5px;color:var(--tx2);font-size:13px}\n.tpLane img{width:18px;height:18px;object-fit:contain}\n.tpLg{margin-left:auto;padding:1px 8px;border-radius:999px;font-size:13px;font-weight:800;color:var(--lgc);border:1px solid color-mix(in srgb,var(--lgc) 55%,transparent)}\n.tpP{padding:8px 10px;border-radius:8px;background:rgba(255,255,255,.04);margin-top:8px}\n.tpP:first-of-type{margin-top:0}\n.tpName{display:flex;align-items:center;gap:8px;flex-wrap:wrap}\n.tpName>b{font-size:16px}\n.tpSr{font-size:13px;color:var(--tx2)}\n.tpPill{font-size:12px;font-weight:700;padding:1px 7px;border-radius:999px;margin-left:auto}\n.tpR{background:rgba(255,90,90,.16);color:#ff5a5a}\n.tpB{background:rgba(90,169,255,.16);color:#5aa9ff}\n.tpY{background:rgba(255,200,80,.16);color:#ffc850}\n.tpW{background:rgba(255,255,255,.1);color:var(--tx)}\n.tpK{background:rgba(255,142,198,.16);color:#ff8ec6}\n.tpV{background:rgba(185,140,255,.16);color:#b98cff}\n.tpG{background:rgba(76,208,125,.16);color:#4cd07d}\n.tpKv{display:grid;grid-template-columns:auto 1fr;column-gap:12px;row-gap:2px;margin-top:6px;font-size:14px;font-variant-numeric:tabular-nums}\n.tpKv>span:nth-child(odd){color:var(--tx2)}\n.tpKv>span{display:flex;align-items:center;gap:5px;flex-wrap:wrap;min-height:22px}\n.tpTm{display:inline-flex;align-items:center;gap:5px;font-weight:700}\n.tpQ{margin-top:6px;padding:6px 8px;border-left:3px solid rgba(255,200,80,.5);background:rgba(255,200,80,.06);border-radius:4px;font-size:14px;line-height:1.55}\n.tpQg{border-left-color:rgba(76,208,125,.55);background:rgba(76,208,125,.06)}\n.tpQ>span .tpTm{font-size:11px}\n.tpQ>span{display:block;font-size:12px;color:var(--tx2);margin-bottom:2px}\n.tpPvC{margin-top:6px}\n.tpPvC .tpName>b{color:var(--tx2)}\n.tpX{background:rgba(255,255,255,.08);color:var(--tx2)}\n.tpPv{margin-top:10px;padding-top:8px;border-top:1px solid rgba(255,255,255,.1)}\n.tpPvR{display:grid;grid-template-columns:auto 1fr auto;column-gap:10px;align-items:center;margin-top:5px;font-size:13px}\n.tpPer{color:var(--tx2);font-variant-numeric:tabular-nums;white-space:nowrap}\n.tpDu{font-size:12px;font-weight:700;padding:1px 7px;border-radius:999px;background:rgba(255,255,255,.08);white-space:nowrap}\n#tbTip:has(.rtBox){max-width:min(520px,94vw);padding:12px 14px}\n.rtBox{min-width:300px}\n.rtHd{display:flex;align-items:center;gap:8px;padding-bottom:10px;margin-bottom:10px;border-bottom:1px solid rgba(255,255,255,.1);white-space:nowrap}\n.rtHd>b:first-of-type{font-size:16px}\n.rtTt{color:var(--tx2);font-size:13px}\n.rtSum{margin-left:auto;padding-left:20px;font-size:24px;line-height:1;font-weight:800;font-variant-numeric:tabular-nums}\n.rtGrid{display:grid;grid-template-columns:20px auto 18px auto auto;column-gap:12px;row-gap:8px;align-items:center}\n.rtCh{font-size:13px;color:var(--tx2);line-height:1}\n.rtChD{justify-self:end}\n.rtIc img{width:20px;height:20px;display:block;object-fit:contain}\n.rtP{display:flex;flex-direction:column;line-height:1.3;min-width:0}\n.rtN{font-weight:700;white-space:nowrap;display:flex;align-items:center;gap:6px}\n.rtV{font-size:14px;color:var(--tx2);font-variant-numeric:tabular-nums;white-space:nowrap}\n.rtV i{font-style:normal;font-size:11px;opacity:.8;margin-left:0;display:block;white-space:nowrap}\n.rtAr{color:var(--tx2);text-align:center;font-size:13px}\n.rtD{justify-self:end;min-width:58px;text-align:center;padding:3px 8px;border-radius:6px;font-weight:800;font-variant-numeric:tabular-nums;background:rgba(255,255,255,.06)}\n.rtD.tbUp{background:rgba(255,90,90,.15)}\n.rtD.tbDn{background:rgba(63,207,122,.15)}\n.rtXl{grid-column:2/-1;margin-top:-6px;font-size:11px;color:var(--tx2)}\n.rtEmpty{color:var(--tx2)}\n.rtFoot{margin-top:12px;padding-top:8px;border-top:1px solid rgba(255,255,255,.1);font-size:12px;line-height:1.5;color:var(--tx2);white-space:nowrap}\n@container mainc (max-width:999.98px){.tbTeam{padding-right:8px;font-size:13px;gap:5px}\n.tbCell{font-size:13px;padding:6px 3px}\n.tbHd{font-size:12px}\n.tbHd img{display:none}}\n.trList{padding:6px 16px 12px;display:grid;grid-template-columns:max-content max-content max-content max-content max-content minmax(0,1fr);column-gap:14px}\n.trHead{grid-column:1/-1;display:grid;grid-template-columns:subgrid;padding:4px 10px 6px;font-size:13px;color:var(--tx2);font-weight:700;border-bottom:1px solid var(--line)}\n.trFlow{display:contents}\n.trFrom,.trTo,.trSpan{display:flex;flex-direction:column;align-items:flex-start;gap:4px;white-space:nowrap}\n.trRow>.trSt{grid-column:1}\n.trRgC{grid-column:2;display:flex;align-items:center;gap:4px;white-space:nowrap}\n.trRgC .trArr{font-size:12px}\n.trRgC .trLg{margin-left:0}\n.trFrom{grid-column:3}\n.trFlow>.trArr{grid-column:4}\n.trTo{grid-column:5}\n.trSpan{grid-column:3/6}\n.trRow>.trTx{grid-column:6}\n.trArr{color:var(--tx2);font-size:15px}\n.trNone{color:var(--tx2);opacity:.6;padding:0 6px}\n.trLg{font-size:12px;font-weight:800;color:var(--lgc,var(--tx2));margin-left:4px;padding:0 6px;border-radius:999px;border:1px solid color-mix(in srgb,var(--lgc,#888) 55%,transparent)}\n.trLgOnly{font-size:13px;font-weight:700;margin-left:0}\n.trSt{font-size:13px;font-weight:700;padding:1px 9px;border-radius:999px;white-space:nowrap;justify-self:start}\n.trSt-official{color:var(--tx);background:rgba(255,255,255,.1)}\n.trSt-conf{color:#4cd07d;background:rgba(76,208,125,.16)}\n.trSt-fake{color:#ff5a5a;background:rgba(255,90,90,.16)}\nb.trCf{color:#4cd07d}\nb.trFk{color:#ff5a5a}\n.trSt-rumor{color:#ffc850;background:rgba(255,200,80,.16)}\na.trPl{color:inherit;text-decoration:underline dotted rgba(255,255,255,.35);text-underline-offset:3px}\na.trPl:hover{color:#7fb2ff;text-decoration-color:#7fb2ff}\n.trList>.sumEmpty{grid-column:1/-1}\n.trDay{grid-column:1/-1;font-weight:900;color:var(--gold);font-size:18px;margin:18px 0 6px;padding:6px 14px;border-radius:8px;border-left:5px solid var(--gold);background:linear-gradient(90deg,color-mix(in srgb,var(--gold) 18%,transparent),transparent 70%)}\n.trRow{grid-column:1/-1;display:grid;grid-template-columns:subgrid;align-items:center;padding:8px 10px;border-radius:6px;line-height:1.7}\n.trRow:nth-of-type(even){background:rgba(255,255,255,.03)}\n.trRow:hover{background:rgba(255,255,255,.06)}\n.trTeam{display:inline-flex;align-items:center;gap:6px;font-weight:700}\n.trSrcTag{font-size:13px;padding:1px 8px;border-radius:999px;background:rgba(255,255,255,.08);color:var(--tx2)}\n.trSrcTag{color:#7ab8ff;background:rgba(122,184,255,.12);font-size:11px;font-weight:700;padding:1px 7px}\nimg.trRole{width:20px;height:20px;object-fit:contain;padding:0;margin:0 4px 0 2px;background:none;vertical-align:-4px}\nimg.trCoach{width:20px;height:20px;object-fit:contain;margin:0 4px 0 2px;vertical-align:-4px;background:none;padding:0}\n.trCoachTx{white-space:nowrap;margin-left:4px}\n.trRole{display:inline-block;font-size:12.5px;padding:0 6px;margin:0 4px 0 2px;border-radius:5px;background:rgba(255,200,80,.14);color:#ffc850;vertical-align:1px}\n.trTx{min-width:0;word-break:break-word;display:flex;align-items:center;gap:12px}\n.trTxt{flex:1 1 auto;min-width:0}\n.trLks{flex:0 0 auto;margin-left:auto;display:flex;gap:10px;white-space:nowrap}\n.trLks .trLk{margin-left:0}\n.trLk{font-size:13px;color:#7fb2ff;white-space:nowrap;margin-left:6px}\n@container mainc (max-width:999.98px){.trList{grid-template-columns:max-content minmax(0,1fr)}\n.trHead{display:none}\n.trFlow{display:flex;align-items:center;gap:10px;flex-wrap:wrap;grid-column:2;grid-row:1}\n.trFrom,.trTo,.trSpan{flex-direction:row;flex-wrap:wrap;gap:10px}\n.trTx{flex-wrap:wrap}\n.trLks{margin-left:0}\n.trRgC{grid-column:1/-1;grid-row:2}\n.trRow>.trTx{grid-column:1/-1;grid-row:3;margin-top:4px}}\n.ntDoc mark{background:#5a4a12;color:inherit;border-radius:3px}\n.pdDRys .sqLaneBtn{font-size:14px;padding:3px 12px}\n.pdToc .sqLaneBtn{border-left-width:3px;font-size:14px;padding:3px 12px}\n.pdRdR>*{padding:3px 0;font-size:17px;line-height:1.7;white-space:nowrap;font-variant-numeric:tabular-nums}\n.pdRdH>*{font-size:14.5px;color:var(--tx2);border-bottom:1px solid rgba(255,255,255,.08);padding-bottom:5px}\n.pdExt .pdExtSrc a{color:inherit;text-decoration:none}\n.pdExt .pdExtWhy a{color:#8ab4ff;text-decoration:none;white-space:nowrap}\n.pdExt a:hover{text-decoration:underline}\n.sumPool .sumProw>*{display:flex;align-items:center;padding:5px 0;min-width:0}\n.sumPool .sumProw>*:first-child{justify-content:flex-start}\n.sumPool .sumProw>*:last-child{justify-content:flex-end}\n.sumPool .sumPhd>*{padding-bottom:4px;min-width:0}\n.sumPool .sumZeb>*{background:rgba(255,255,255,.04)}\n.sumPool .sumPhd>*{font-size:13px;color:var(--tx2)}\n.segBtn button{border:none;background:transparent;padding:0 12px;cursor:pointer;color:var(--tx2);\n    font:inherit;font-size:15px;border-radius:0;height:100%;white-space:nowrap;box-sizing:border-box;\n    display:inline-flex;align-items:center;justify-content:center;gap:5px}\n.segBtn button+button{border-left:1px solid var(--line)}\n.segBtn button:hover:not(.on){background:rgba(255,255,255,.06)}\n.segBtn button.on{background:rgba(245,185,66,.22);color:var(--gold);font-weight:700}\n.segBtn.sm button{font-size:13.5px;padding:0 10px}\n.card.ovPad30{padding-left:30px;padding-right:30px}\n#axesBox #axAdd,#axesBox #axReset.sqbtn{width:auto;height:26px;padding:0 10px;font-size:14px;line-height:1}\n#axesBox .meta{font-size:16.5px}\n@container mainc (max-width:759.98px){.tbBoard{display:block;padding:4px 6px 10px}\n.tbHd{display:none}\n.tbLg{margin:14px 0 6px;padding:6px 12px}\n.tbLg b{font-size:19px}\n.tbRow{display:flex;flex-wrap:wrap;align-items:center;gap:3px 12px;margin:6px 0;padding:7px 10px 8px;border:1px solid var(--line);border-left:4px solid var(--lgc);border-radius:9px;background:rgba(255,255,255,.02)}\n.tbTeam{order:0;flex:1 1 auto;border-left:0;padding:0;font-size:17px}\n.tbRow::after{content:\"\";order:2;flex:0 0 100%;height:0}\n.tbCell{order:3;display:inline-flex;align-items:center;gap:5px;padding:2px 0;font-size:15px;line-height:1.35;border-radius:4px;text-align:left}\n.tbCell.tbRate{order:1;flex:0 0 auto;font-size:15px;margin-left:auto}\n.tbCell::before{content:\"\";flex:0 0 16px;width:16px;height:16px;background:center/contain no-repeat}\n.tbCell[data-r=\"TOP\"]::before{background-image:url(img/TOP.png)}\n.tbCell[data-r=\"JNG\"]::before{background-image:url(img/JG.png)}\n.tbCell[data-r=\"MID\"]::before{background-image:url(img/MID.png)}\n.tbCell[data-r=\"BOT\"]::before{background-image:url(img/BOT.png)}\n.tbCell[data-r=\"SUP\"]::before{background-image:url(img/SUP.png)}\n.tbCell[data-r=\"HC\"]::before{background-image:url(img/COACH.png)}\n.tbCell[data-r=\"STF\"]::before,.tbCell.tbRate::before{content:attr(data-lb);flex:0 0 auto;width:auto;height:auto;font-size:11px;color:var(--tx2);background:none}\n.tbCell .tbCv{min-width:0}\n.tbCell .tbN{white-space:nowrap}\n.tbCell:hover{background:none}\n.trBar{gap:6px 8px!important;padding:8px 10px!important}\n.trBar .trFG{border-left:0;padding-left:0;flex:1 1 100%;flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none}\n.trBar .trFG::-webkit-scrollbar{display:none}\n.trBar .trFG>span{flex-wrap:nowrap!important}\n.trBar .sqLaneBtn{flex:0 0 auto;white-space:nowrap}\n.trBar .trFG:first-child{flex:0 0 auto}\n.tbLegend{flex-wrap:nowrap}\n.trBar .meta{font-size:12px}\n.trBar>label,.trBar .trFG>label{display:none}\n.trBar .cwrap{flex:1 1 140px}\n.trBar .cwrap input{width:100%!important}}\n#tbTip.sheet{pointer-events:auto!important;left:8px!important;right:8px!important;top:auto!important;bottom:8px!important;max-width:none!important;max-height:72vh;overflow:auto;padding:16px 14px 14px;border-radius:14px;box-shadow:0 -6px 30px rgba(0,0,0,.6)}\n#tbTip.sheet .tpBox,#tbTip.sheet .rtBox{min-width:0}\n#tbTip.sheet .rtHd{padding-right:40px}\n.tbTipX{position:absolute;top:8px;right:8px;width:30px;height:30px;border-radius:50%;border:1px solid var(--line);background:rgba(255,255,255,.06);color:var(--tx);font-size:14px;cursor:pointer}\nhtml.solo #nav,html.solo #lblYear,html.solo #yearSel,html.solo #penBtn,html.solo #meta{display:none!important}";document.head.appendChild(st);})();

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
  document.getElementById("tsHelp").onclick=()=>{ const d=document.getElementById("tsHelpBox"); if(d){d.remove();return;}
    main.insertAdjacentHTML("afterbegin",`<div id="tsHelpBox" class="card" style="margin-bottom:12px;line-height:1.8;font-size:15px">${(LANG==="en"?HELP.en:HELP.zh)||""}</div>`); };
  document.getElementById("tsReset").onclick=()=>{ Object.assign(V,{trSrc:"",trSt:"",trRg:"",trKd:"",trQ:"",tbF:""}); saveState(); render(); }; }
function render(){
    (()=>{
    const en2=LANG==="en";
    if(!window.TRANSFERS){ main.innerHTML=`<div class="card"><span class="sumEmpty">${en2?"Loading…":"載入中"}</span></div>`;
      lazyLoad("tr").then(()=>{ if(!window.TRANSFERS)window.TRANSFERS={wiki:[],sheep:[]}; if(curView==="轉會")render(); }); return; }
    const D=window.TRANSFERS, RL={TOP:en2?"Top":"上路",JNG:en2?"Jungle":"打野",MID:en2?"Mid":"中路",BOT:en2?"Bot":"下路",SUP:en2?"Support":"輔助"};
    const RG_EN={"韓國":"Korea","中國":"China","歐洲":"EMEA","北美":"North America","巴西":"Brazil","亞太":"Asia Pacific","國際":"International","越南":"Vietnam","日本":"Japan"};
    // 賽區一律顯示聯賽名（使用者 2026-11-19「地區改成賽區 韓國就是LCK」）；資料內部仍用 韓國／歐洲… 當鍵
    const RG_LG={"韓國":"LCK","中國":"LPL","歐洲":"LEC","北美":"LCS","巴西":"CBLOL","亞太":"LCP","越南":"LCP","日本":"LCP"};
    const rgNm=r=>RG_LG[r]||(en2?(RG_EN[r]||r):r);
    // Sheep 推文：tags＝[[賽區, 隊名]…]（推文提到的戰隊，人工標）；kind 同 wiki（join／leave／both／other）
    // PTT／韓網／官方（使用者 2026-11-19「轉會消息新增 PTT／韓網」＋使用者貼的官方續約）：D.extra（scripts/fetch_ptt_transfers.py＋transfers_official_src.json）
    //   s＝ptt／kr／man；沒標隊的照標題認隊（陣容表的隊名／縮寫），kind 照標題字眼判
    const LG2RG={LCK:"韓國",LPL:"中國",LEC:"歐洲",LCS:"北美",CBLOL:"巴西",LCP:"亞太"};
    const ab0=n=>/^Kiwoom DRX$/i.test(String(n||""))?"KRX":(teamFix(String(tAb(n)||""))||n);
    const BTM=(D.board||[]).map(t=>({nm:t.nm,rg:LG2RG[t.lg]||"",al:[...new Set([t.nm,ab0(t.nm),t.tm].filter(Boolean))]}));
    const autoTags=s=>BTM.filter(b=>b.al.some(a=>new RegExp("(?<![A-Za-z0-9])"+a.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")+"(?![A-Za-z0-9])","i").test(s))).map(b=>[b.rg,b.nm]);
    const autoKind=s=>{ const j=/加入|joins?\b|rejoin|welcome|簽下|加盟|回歸|上調|擔任/i.test(s), l=/離隊|thank ?you|farewell|解散|自由市場|退出/i.test(s); return j&&l?"both":j?"join":l?"leave":"other"; };
    const SRCN={sheep:"Sheep Esports",ptt:"PTT",kr:en2?"Korean sites":"韓網",man:en2?"Official":"官方"};
    // 傳聞後續（使用者 2026-11-20「如果傳聞被推翻就變成謠言，用紅色」「如果被證實就是證實，綠色」）：
    //   陣容表的官方狀態（wiki 新加入／Sheep 官方消息／官方續約）對照傳聞的「誰 → 哪隊」——
    //   官方加入的正是那隊（或傳聞是續約、官方也續約了）＝證實；官方去了別隊或跟別隊續約＝謠言；還沒定＝傳聞。另有人工標的闢謠（fake）
    const nk=n=>String(n||"").replace(/\s*\([^()]*\)\s*$/,"").toLowerCase(), sameTm=(a,b)=>a===b||ab0(a)===ab0(b);
    const OFF=new Map(); (D.board||[]).forEach(t=>Object.values(t.r||{}).flat().forEach(e=>{ const j=!!(e.new||e.pm||(e.tip&&!e.r)), r=!!e.rs; if(!j&&!r)return;
      const k=nk(e.n); if(!OFF.has(k))OFF.set(k,[]); OFF.get(k).push({tm:t.nm,j,r}); }));
    const verdict=(mv,stay)=>{ const vs=[...(mv||[]).map(([n,to])=>{ const o=OFF.get(nk(n))||[]; return o.some(x=>sameTm(x.tm,to))?"conf":o.some(x=>!sameTm(x.tm,to))?"fake":""; }),   // 在那隊官方加入或續約都算對得上
        ...(stay||[]).map(([n,tm])=>{ const o=OFF.get(nk(n))||[]; return o.some(x=>sameTm(x.tm,tm))?"conf":o.some(x=>!sameTm(x.tm,tm))?"fake":""; })];
      return vs.length&&vs.every(v=>v==="conf")?"conf":vs.some(v=>v==="fake")&&!vs.some(v=>v==="conf")?"fake":""; };
    const sheepMv=x=>{ const ins=(x.tags||[]).filter(t=>t[2]==="in").map(t=>t[1]); if(ins.length!==1)return [];
      return [...String(x.zh||x.en||"").matchAll(/‹[^|›]+\|([^›]+)›/g)].map(m=>[m[1],ins[0]]); };
    // 離隊／續約傳聞的對照：wiki 官方離隊（誰＋哪隊）、Sheep 傳聞是續約（寫續約／留隊、只標一隊）
    const namesOf=x=>[...new Set([...String((x.zh||"")+" "+(x.en||"")).matchAll(/‹[^|›]+\|([^›]+)›/g)].map(m=>nk(m[1])))];
    const LEFT=new Set(); (D.wiki||[]).forEach(x=>{ if(/leave|both/.test(x.kind||""))String(x.zh||"").split(/(?<=。)\s*/).filter(z=>/離隊|分道揚鑣/.test(z)).forEach(z=>namesOf({zh:z}).forEach(n=>LEFT.add(n+">"+x.team))); });
    const sheepV=x=>{ const tg=x.tags||[], ns=namesOf(x), zh=String(x.zh||"");
      if(/續約|留在|留隊/.test(zh)&&tg.length===1&&ns.length)return verdict([],ns.map(n=>[n,tg[0][1]]));
      const outs=tg.filter(t=>t[2]==="out").map(t=>t[1]), ins=tg.filter(t=>t[2]==="in");
      if(x.kind==="leave"&&outs.length===1&&!ins.length&&ns.length)return ns.every(n=>LEFT.has(n+">"+outs[0]))?"conf":"";
      return verdict(sheepMv(x)); };
    const all0=[...(D.wiki||[]).map(x=>({...x,s:"wiki"})),...(D.sheep||[]).map(x=>({...x,s:"sheep",tags:x.tags||[],rg:"",kind:x.kind||"other",team:(x.tags||[]).map(t=>t[1]).join(" "),
        _v:x.st==="rumor"?sheepV(x):""})),
      ...(()=>{ const rgOf=n=>(BTM.find(b=>b.nm===n)||{}).rg||"", er=n=>String(n).replace(/[.*+?^${}()|[\]\\]/g,"\\$&"),
          has=(n,s)=>new RegExp("(?<![A-Za-z0-9])"+er(n)+"(?![A-Za-z0-9])","i").test(s||"");
        // 去重（使用者 2026-11-20「這跟官方重複了」）：PTT／韓網跟 Sheep／wiki 三天內同一件事就不列——
        //   同一人＋同一個新隊；或隊伍組合相同、且標題裡的英文字（選手名）在對方內文也有（沒有英文字就只看隊伍）
        const SW=[...(D.wiki||[]).map(x=>({d:x.d,t:(x.en||"")+" "+(x.zh||""),tm:[x.team],st:"official"})),...(D.sheep||[]).map(x=>({d:x.d,t:(x.en||"")+" "+(x.zh||""),tm:(x.tags||[]).map(t=>t[1]),st:x.st||"rumor"}))];   // 只跟同狀態的比（傳聞後來官方公布＝證實，不是重複）
        const dd=(a,b)=>Math.abs((new Date(String(a).slice(0,10))-new Date(String(b).slice(0,10)))/864e5);
        const dupMv=(d,n,to,st)=>SW.some(y=>y.st===st&&dd(d,y.d)<=3&&y.tm.includes(to)&&has(n,y.t));
        const dupTm=(d,tags,zh,manual,st)=>{ const ts=[...new Set(tags.map(t=>t[1]).filter(Boolean))]; if(!ts.length)return false;
          const ab=new Set(ts.map(n=>ab0(n).toLowerCase())), ws=[...new Set((zh.match(/[A-Za-z][A-Za-z0-9]{2,}/g)||[]))].filter(w=>!ab.has(w.toLowerCase())&&!/^(thank|you|welcome|joins?|official|fb|yt|lck|lpl|lec|lcs|cblol|lcp)$/i.test(w));
          if(!ws.length&&!manual)return false;   // 沒人名又不是我手標隊伍的（KRX 跟選手會面很多次）只看隊伍會誤刪
          return SW.some(y=>y.st===st&&dd(d,y.d)<=3&&(ws.length?true:y.tm.length===ts.length)&&ts.every(t=>y.tm.includes(t))&&(!ws.length||ws.some(w=>has(w,y.t)))); };
        const out=[];
        (D.extra||[]).forEach(x0=>{ // 標題開頭的「乳摸：」「韓網乳摸：」不寫（使用者 2026-11-20：第一欄已標傳聞）
          const x={...x0,zh:String(x0.zh||"").replace(/^\s*(?:韓網)?乳摸\s*[:：]?\s*/,"").replace(/\s*[(（]含乳摸[)）]/,"")};
          const base={...x,s:x.src==="韓網"?"kr":x.src==="官方"?"man":x.src==="Sheep Esports"?"sheep":"ptt",rg:""};   // PTT 轉貼 Sheep 的：來源＝Sheep、連結給推文
          // 原隊／新隊只放標題有點名的人（KRX 五人那篇內文另提 Sharvel→GEN，不該多出 DNS／GEN）；都沒點名才全放
          const mvIn=x.mv?x.mv.filter(m=>has(m[0],x.zh)):[], mvU=mvIn.length?mvIn:(x.mv||[]);
          // 內文雜亂（好幾個人、原隊或新隊不同）⇒ 拆成一人一列（使用者 2026-11-20「記得把內文拆開來判斷」）
          const messy=!x.nosplit&&mvU.length>1&&(new Set(mvU.map(m=>m[2])).size>1||new Set(mvU.map(m=>m[3])).size>1);   // nosplit：人工標「這則是候選名單，不拆」（JDG 五選二）
          if(messy){ mvU.forEach(([n,l,to,fr],k)=>{ if(base.s!=="man"&&dupMv(x.d,n,to,x.st||"rumor"))return;
              const tags=[...(fr?[[rgOf(fr),fr,"out"]]:[]),[rgOf(to),to,"in"]];
              out.push({...base,id:x.id+"#"+k,tags,kind:fr?"both":"join",team:tags.map(t=>t[1]).join(" "),_sig:[nk(n)+">"+to],_v:x.fake?"fake":x.conf?"conf":x.st==="rumor"?verdict([[n,to]]):"",
                zh:`§${l}§${n} ${en2?"joins":"加入"} ${to}${en2?".":"。"}`}); }); return; }   // 狀態欄已標傳聞；不再重複整串標題
          const mvT=x.mv?[...new Map(mvU.flatMap(([n,l,to,fr])=>[...(fr?[[rgOf(fr),fr,"out"]]:[]),[rgOf(to),to,"in"]]).map(t=>[t[1]+t[2],t])).values()]:null;
          // 標題自動認出的隊：照標題字眼放原隊／新隊（加入／Welcome＝新隊、離隊／Thank you＝原隊）
          const kd=x.kind||autoKind(x.zh||""), at=autoTags(x.zh||"").map(t=>kd==="join"?[...t,"in"]:kd==="leave"?[...t,"out"]:t);
          const tags=x.tags||mvT||at;
          if(base.s!=="man"&&(mvU.length===1?dupMv(x.d,mvU[0][0],mvU[0][2],x.st||"rumor"):dupTm(x.d,tags,x.zh||"",!!x.tags,x.st||"rumor")))return;
          out.push({...base,tags,kind:kd,team:tags.map(t=>t[1]).join(" "),_sig:mvU.map(m=>nk(m[0])+">"+m[2]),_v:x.fake?"fake":x.conf?"conf":x.st==="rumor"?verdict(mvU.map(m=>[m[0],m[2]]),x.stay):""}); });
        return out; })()];
    // 消息頁全面清理（使用者 2026-11-20「把重複的消息或不正確顯示的消息都處理」）：
    //   ① wiki 的「合約在 GCD 更新」是資料庫同步、不是消息 ⇒ 那幾句拿掉，整則只剩它就不列
    //   ② wiki 與 Sheep 官方講同一件事（同隊、方向不衝突、三天內、人名重疊 ≥ 75%）⇒ 留人名較多的那則，一樣多留 Sheep（有前因後果）
    const all=(()=>{ const dd2=(a,b)=>Math.abs((new Date(String(a).slice(0,10))-new Date(String(b).slice(0,10)))/864e5);
      const L=all0.map(x=>{ if(x.s!=="wiki")return x; const cut=(t,re)=>String(t||"").split(/(?<=[。.])\s+/).filter(z=>!re.test(z)).join(" ");
        return {...x,zh:cut(x.zh,/合約在 GCD 更新/),en:cut(x.en,/updated in the/i)}; }).filter(x=>x.s!=="wiki"||String(x.zh||x.en||"").trim());
      const W=L.filter(x=>x.s==="wiki"), S=L.filter(x=>x.s==="sheep"&&(x.st||"rumor")==="official"), drop=new Set();
      W.forEach(w=>{ const wn=namesOf(w); if(!wn.length)return;
        S.forEach(sh=>{ if(drop.has(sh)||drop.has(w)||dd2(w.d,sh.d)>3)return; const tg=sh.tags.find(t=>t[1]===w.team); if(!tg)return;
          if(tg[2]&&((w.kind==="join"&&tg[2]!=="in")||(w.kind==="leave"&&tg[2]!=="out")))return;
          const sn=namesOf(sh); if(!sn.length)return; const ov=wn.filter(n=>sn.includes(n)).length;
          if(ov/Math.min(wn.length,sn.length)<0.75)return; drop.add(wn.length>sn.length?sh:w); }); });
      return L.filter(x=>!drop.has(x)); })();
    const RGS=[...new Set(all.flatMap(x=>x.s!=="wiki"?x.tags.map(t=>t[0]):[x.rg]).filter(Boolean))].sort((a,b)=>Object.keys(RG_LG).indexOf(a)-Object.keys(RG_LG).indexOf(b));
    const KD={join:en2?"Join":"加入",leave:en2?"Leave":"離隊",other:en2?"Other":"其他"};
    const q=(V.trQ||"").trim().toLowerCase();
    // 戰隊一律顯示縮寫（使用者 2026-11-19「戰隊全部改成縮寫」）：左欄＋內文都換，滑過看全名；沒有縮寫的（tAb 回全名）照舊
    const abOf=n=>{ if(/^Kiwoom DRX$/i.test(String(n||"")))return "KRX";   // 使用者 2026-11-19「DRX 前陣子就改成 KRX 了」：只改這頁的顯示（全站 teamFix 把 KRX 收斂成 DRX 當比對鍵，不能動）
      const a=teamFix(String(tAb(n)||"")); return a||n; };
    const TN=new Map([...new Set(all.flatMap(x=>x.s!=="wiki"?x.tags.map(t=>t[1]):[x.team]).filter(Boolean))].map(n=>[n,abOf(n)]).filter(([n,a])=>a!==n));
    const TNRE=TN.size?new RegExp("(?<![A-Za-z0-9])("+[...TN.keys()].sort((a,b)=>b.length-a.length).map(n=>esc(n).replace(/[.*+?^${}()|[\]\\]/g,"\\$&")).join("|")+")(?![A-Za-z0-9])","g"):null;
    const TNE=new Map([...TN].map(([n,a])=>[esc(n),a]));
    const ST={official:en2?"Official":"官方",rumor:en2?"Rumor":"傳聞",conf:en2?"Confirmed":"證實",fake:en2?"Debunked":"謠言"};
    const stOf=x=>x.s==="wiki"?"official":x._v==="fake"?"fake":x._v==="conf"?"conf":(x.st||"rumor");
    const shown=all.filter(x=>(!V.trSrc||x.s===V.trSrc)&&(!V.trSt||stOf(x)===V.trSt)&&(!V.trRg||(x.s!=="wiki"?x.tags.some(t=>t[0]===V.trRg):x.rg===V.trRg))
      &&(!V.trKd||(V.trKd==="join"?/join|both/.test(x.kind):V.trKd==="leave"?/leave|both/.test(x.kind):x.kind==="other"))
      &&(!q||[x.team,x.en,x.zh].join(" ").replace(/‹[^|›]+\|([^›]+)›/g,"$1").toLowerCase().includes(q))).sort((a,b)=>a.d<b.d?1:a.d>b.d?-1:(b.n||0)-(a.n||0));
    // 狀態欄（使用者 2026-11-19「新增一欄在第二欄 說明是Rumor還是官方消息」）：wiki＝官方；Sheep 依 st（抓取端標），內文開頭的【官方】／[SOURCES] 前綴拿掉
    // 教練圖示放在 ID 前面（跟路線圖一樣；使用者 2026-11-19「為何教練的圖是在教練ID後面」）：
    //   「名字（總教練）」→ ⟦C:職稱⟧名字⟦R:職稱⟧；純「教練」只留圖示，其他職稱文字留在名字後面
    const CO=/(‹[^|›]+\|[^›]+›|[A-Za-z0-9][A-Za-z0-9_.'\-]*)\s*(?:（([^（）]*教練[^（）]*)）|\(([^()]*Coach[^()]*)\))/g;
    // 推文原文清理（2026-11-19 分頁審視）：國旗 emoji 在 Windows 會畫成 KR／MX 字母方塊 ⇒ 拿掉；#LCK 的 # 拿掉；連空行壓成一行；網址改成「文章」連結
    const clean=s=>s.replace(/[ \t]?[\u{1F1E6}-\u{1F1FF}]{2}/gu,"").replace(/^[ \t]+/gm,"").replace(/(^|\s)#(\w)/g,"$1$2").replace(/[ \t]*\n\s*\n\s*/g,"\n").trim();
    // 選手名冊（陣容表格子＋上一位＋wiki／Sheep 的 ‹頁|名›）⇒ 名字 → {頁, 路線}；內文沒標的名字自動補路線圖示與 wiki 連結
    //   （使用者 2026-11-20「消息頁面很多選手沒有標註路線圖」「很多選手沒有標記超連結」）。比對分大小寫、前後不能接英數字
    const pn0=s=>String(s||"").replace(/\s*\([^()]*\)\s*$/,"");   // 同陣容表的 pn（那個定義在後面，這裡先用不到它）
    const PLM=new Map(), addPl=(n,p,l)=>{ n=String(n||"").trim(); if(n.length<2)return; try{ p=decodeURIComponent(String(p||"")); }catch(_){} const o=PLM.get(n)||{}; PLM.set(n,{p:o.p||p||"",l:o.l||l||""}); };
    (D.board||[]).forEach(t=>{ Object.entries(t.r||{}).forEach(([r,L])=>L.forEach(e=>addPl(pn0(e.n),e.p,r)));
      Object.entries(t.prev||{}).forEach(([r,L])=>L.forEach(p=>{ const o=typeof p==="string"?{n:p}:p; addPl(pn0(o.n),o.n,r); })); });
    [...(D.wiki||[]),...(D.sheep||[])].forEach(x=>((x.en||"")+" "+(x.zh||"")).replace(/(?:§(TOP|JNG|MID|BOT|SUP|COACH)§)?‹([^|›]+)\|([^›]+)›/g,(m,l,p,d)=>{ let pg=p; try{pg=decodeURIComponent(p);}catch(e){} addPl(d,pg.replace(/_/g," "),l||""); return m; }));
    // 陣容表沒有的人（二隊、退役、教練）：排程向 Leaguepedia 查好的位置（transfers.js 的 roles；使用者 2026-11-20 Cracker／Nuguri／Roach）
    // 跟隊伍縮寫／隊名同字的不算人名（NAVI 被當成中路選手，使用者 2026-11-20 檢視時發現）
    const TMW=new Set([...BTM.flatMap(b=>b.al),...TN.keys(),...TN.values()].map(z=>String(z).toLowerCase()));
    Object.entries(D.roles||{}).forEach(([n,v])=>{ if(!TMW.has(n.toLowerCase()))addPl(n,v[1],v[0]); });
    const PLRE=PLM.size?new RegExp("(§[A-Z]+§)?(?<![A-Za-z0-9|‹])("+[...PLM.keys()].sort((a,b)=>b.length-a.length).map(n=>n.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")).join("|")+")(?![A-Za-z0-9›|])","g"):null;
    // 多字隊名整段保護（使用者 2026-11-20「錯誤的把 LIFE 標註了」：Hanwha Life Esports 裡的 Life 被當成輔助 Life）；
    //   去掉 Esports／Gaming 的短名（Hanwha Life）也算
    const TMN=[...new Set([...(D.board||[]).flatMap(t=>[t.nm,t.tm]),...(D.wiki||[]).map(x=>x.team),...[...(D.sheep||[]),...(D.extra||[])].flatMap(x=>(x.tags||[]).map(t=>t[1])),
      ...(D.extra||[]).flatMap(x=>(x.mv||[]).flatMap(m=>[m[2],m[3]]))].filter(n=>n&&/\s/.test(n)).flatMap(n=>[n,n.replace(/\s+(Esports|Gaming|e-?Sports)$/i,"")]))].filter(n=>/\s/.test(n)).sort((a,b)=>b.length-a.length);
    const TMSRC=TMN.length?"|"+TMN.map(n=>n.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")).join("|"):"";
    const SPLITRE=new RegExp("(§[A-Z]+§‹[^›]*›|‹[^›]*›|https?:\\/\\/\\S+"+TMSRC+")");
    const autoPl=s=>{ if(!PLRE)return s;
      // 已標的 ‹頁|名› 沒有路線就補；純文字的名字包成 ‹頁|名›（網址、既有連結、整段隊名不動）
      return s.split(SPLITRE).map((seg,i)=>{
        if(i%2){ const m=/^‹([^|›]+)\|([^›]+)›$/.exec(seg); if(!m)return seg; const o=PLM.get(m[2]); return o&&o.l&&o.l!=="COACH"?`§${o.l}§${seg}`:seg; }
        // 前面已經有路線記號（§TOP§Naak Nako）⇒ 整個名字一起認、只補連結，不再把後半（Nako）當成另一個人（使用者 2026-11-20）
        return seg.replace(PLRE,(m,pre,n)=>{ const o=PLM.get(n); if(!o)return m; const lk=o.p?`‹${encodeURIComponent(o.p.replace(/ /g,"_"))}|${n}›`:n;
          return (pre||(o.l&&o.l!=="COACH"?`§${o.l}§`:o.l==="COACH"?"§COACH§":""))+lk; }); }).join(""); };
    const txt=x=>{ let t=esc(clean(autoPl(((en2?x.en:(x.zh||x.en))||"").replace(/^\s*(【[^】]{1,4}】|\[[A-Z]+\])\s*/,""))).replace(CO,(m,n,a,b)=>`⟦C:${a||b}⟧${n}⟦R:${a||b}⟧`))
        .replace(/https?:\/\/[^\s<]+/g,u=>`<a class="trPl" href="${u}" target="_blank" rel="noopener">${en2?"Article":"文章"}</a>`)
        .replace(/§COACH§/g,()=>`<img class="trCoach" src="img/COACH.png" alt="${en2?"Coach":"教練"}" title="${en2?"Coach":"教練"}">`).replace(/‹([^|›]+)\|([^›]+)›/g,(m,p,d)=>`<a class="trPl" href="https://lol.fandom.com/wiki/${p}" target="_blank" rel="noopener">${d}</a>`).replace(/§(TOP|JNG|MID|BOT|SUP)§/g,(m,r)=>POS_IMG[r]?`<img class="trRole" src="${POS_IMG[r]}" alt="${RL[r]}" title="${RL[r]}">`:`<span class="trRole">${RL[r]}</span>`)
        .replace(/⟦C:([^⟧]*)⟧/g,(m,r)=>`<img class="trCoach" src="img/COACH.png" alt="${r}" title="${r}">`)
        .replace(/⟦R:([^⟧]*)⟧/g,(m,r)=>/→|->| to /.test(r)?`<span class="trCoachTx">${r}</span>`:"").replace(/(?:主教練|助理教練|代理主教練|教練)\s*(?=(?:<[^>]+>)*<img class="trCoach")/g,"").replace(/\n/g,"<br>");   // 職稱不寫（滑過哨子圖看得到；使用者 2026-11-20「戰術教練 Sephis 戰術教練 離隊，寫離隊就好」），只留職稱異動
      if(TNRE)t=t.replace(/(^|>)([^<]+)/g,(m,a,b)=>a+b.replace(TNRE,n=>`<span class="trAb" title="${n}">${esc(TNE.get(n)||n)}</span>`));
      // 中英混排補半形空格（使用者 2026-11-20「消息的文字要尊重像改版資訊的排版，英文後面如果是中文要空格」）：
      //   中文字 ↔ 英文／數字之間補一格，中間隔著標籤（連結、圖示、隊名縮寫）也算；緊鄰標點不補
      // 括號、斜線同改版資訊（使用者 2026-11-20「括號跟斜線也要遵守」）：有中文的那則 ⇒ 半形 ( ) / 換全形（）／、前後不留空格；數字之間的 / 不動
      if(!en2&&/[㐀-鿿]/.test(t.replace(/<[^>]+>/g,"")))
        t=t.replace(/(^|>)([^<]+)/g,(m,a,b)=>a+b.replace(/\s*\(\s*/g,"（").replace(/\s*\)\s*/g,"）").replace(/\s*（\s*/g,"（").replace(/\s*）\s*/g,"）").replace(/(?<!\d)\s*\/\s*(?!\d)/g,"／").replace(/\s*／\s*/g,"／"));
      { const CJ="[㐀-䶿一-鿿]", TG="((?:<[^>]+>)*)";
        t=t.replace(new RegExp("("+CJ+")"+TG+"([A-Za-z0-9])","g"),"$1 $2$3").replace(new RegExp("([A-Za-z0-9%])"+TG+"("+CJ+")","g"),"$1$2 $3"); }
      if(q){ const re=new RegExp("("+q.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")+")","gi"); t=t.replace(/(^|>)([^<]+)/g,(m,a,b)=>a+b.replace(re,"<mark>$1</mark>")); } return t; };
    const btns=(key,opts)=>`<span style="display:inline-flex;gap:6px;flex-wrap:wrap">${opts.map(([v,l])=>`<button class="sqLaneBtn${(V[key]||"")===v?" on":""}" data-k="${key}" data-v="${esc(v)}">${l}</button>`).join("")}</span>`;
    // ── 版面（使用者 2026-11-19「重新調整這邊的UI 感覺不直觀」）：每列固定「狀態｜原隊 → 新隊｜消息」＋欄標題。
    //   方向用位置表達：加入＝隊在「新隊」、離隊＝隊在「原隊」、另一邊 –；A→B 兩邊都有；續約／動態這類沒有方向的橫跨兩欄、不畫箭頭。
    //   賽區改成隊名旁的小灰字（不再一列塞一排膠囊）；來源連結接在內文尾。
    // 賽區獨立一欄（使用者 2026-11-20「新增一欄在第二欄叫做賽區，後面隊伍就不用每個都標註賽區，跨賽區就標註兩個」）
    const team=(rg,tm)=>tm?`<span class="trTeam" title="${esc(tm)}">${teamLogoHTML(tAb(tm),22,true,tm)||""}${esc(abOf(tm))}</span>`:"";
    const lgPill=rg=>`<span class="trLg" style="--lgc:${LGC[rgNm(rg)]||"var(--tx2)"}">${esc(rgNm(rg))}</span>`;
    const rgCol=x=>{ let a;
      if(x.s==="wiki")a=[x.rg];
      else{ const o=x.tags.filter(t=>t[2]==="out").map(t=>t[0]), i=x.tags.filter(t=>t[2]==="in").map(t=>t[0]);
        a=o.length&&i.length?[...o,...i]:x.tags.map(t=>t[0]); }
      const u=[...new Set(a.filter(Boolean).map(rgNm))];
      return u.map(l=>`<span class="trLg" style="--lgc:${LGC[l]||"var(--tx2)"}">${esc(l)}</span>`).join(`<span class="trArr">➜</span>`); };
    const NONE=`<span class="trNone">–</span>`;
    // 只知道新隊的加入消息：陣容表有記這個人從哪來就補原隊（使用者 2026-11-20「Bluffing 本來是 HLE 二隊的，怎麼沒寫成 HLEC → DNS」「SeTab 也是」）
    const ORG=new Map(); (D.board||[]).forEach(t=>Object.values(t.r||{}).flat().forEach(e=>{ if(e.from&&!e.r)ORG.set(nk(e.n)+">"+t.nm,e.from); }));
    const orgOf=(x,to)=>{ const fs=[...new Set(namesOf(x).map(n=>ORG.get(n+">"+to)).filter(Boolean))]; return fs.length?fs.map(f=>team("",f)).join(""):""; };
    const flowOf=x=>{
      if(x.s==="wiki"){ const t=team(x.rg,x.team);
        return x.kind==="join"?{from:orgOf(x,x.team)||NONE,to:t}:x.kind==="leave"?{from:t,to:NONE}:{span:t}; }
      const out=x.tags.filter(t=>t[2]==="out"), inn=x.tags.filter(t=>t[2]==="in"), col=a=>a.map(t=>team(t[0],t[1])).join("");
      if(out.length||inn.length)return {from:out.length?col(out):((inn.length===1&&orgOf(x,inn[0][1]))||NONE),to:inn.length?col(inn):NONE};
      return {span:x.tags.length?col(x.tags):(x.s==="sheep"?`<span class="trSrcTag">${SRCN[x.s]}</span>`:NONE)};
    };
    // 同隊同時期合併（使用者 2026-11-20「相同戰隊的同一時期（兩小時內）的轉會資訊都合併」）：
    //   同來源、同狀態、同一組隊伍，時間差 ≤ 2 小時（wiki 只有日期 ⇒ 同一天）⇒ 併成一列，內文分行、連結全列、原隊／新隊取聯集
    const tkOf=x=>[...new Set((x.s==="wiki"?[x.team]:x.tags.map(t=>t[1])).filter(Boolean))].sort().join("|");
    const tsOf=x=>{ const t=Date.parse(String(x.d).replace(" ","T")); return isNaN(t)?0:t; };
    const groups=[];
    shown.forEach(x=>{ const k=tkOf(x);
      const fam=y=>y.s==="kr"?"ptt":y.s;   // PTT 與韓網（都是 PTT 文）算同一家
      const g=k&&groups.find(g=>fam(g)===fam(x)&&stOf(g)===stOf(x)&&g._k===k&&(x.s==="wiki"?g.d.slice(0,10)===x.d.slice(0,10):Math.abs(tsOf(g._last)-tsOf(x))<=2*3600e3));
      // 同一則合併裡，同一個人去同一隊的只留一行（使用者 2026-11-20 KRX Lucid 兩篇）
      if(g&&x._sig&&x._sig.length&&g._items.some(i=>i._sig&&x._sig.every(z=>i._sig.includes(z)))){ g._last=x; return; }
      if(g){ g._items.push(x); g._last=x; if(x.tags)g.tags=[...new Map([...(g.tags||[]),...x.tags].map(t=>[t[1]+"|"+(t[2]||""),t])).values()];
        if(g.kind!==x.kind)g.kind=/join|both/.test(g.kind)&&/leave|both/.test(x.kind)||/leave|both/.test(g.kind)&&/join|both/.test(x.kind)?"both":g.kind; return; }
      groups.push({...x,_k:k,_items:[x],_last:x}); });
    const lkA=(u,l,ti)=>` <a class="trLk" href="${esc(u)}" target="_blank" rel="noopener" title="${esc(ti||"")}">${l} ↗</a>`;
    // 韓網：連結標韓網原文（使用者要求），另附 PTT 轉貼
    const lkOf=x=>{ const link=x.s==="wiki"?x.src:x.url;
      return (link?lkA(link,x.s==="sheep"?"X":x.s==="ptt"?"PTT":x.s==="kr"?SRCN.kr:(en2?"Source":"來源"),x.srcNm):"")+(x.s==="kr"&&x.ptt?lkA(x.ptt,"PTT"):""); };
    let lastD="", rows="";
    groups.forEach(x=>{ const d=x.d.slice(0,10);
      if(d!==lastD){ rows+=`<div class="trDay">${+d.slice(5,7)}/${+d.slice(8,10)}</div>`; lastD=d; }
      const f=flowOf(x);
      const flow=f.span!=null?`<div class="trSpan">${f.span}</div>`
        :`<div class="trFrom">${f.from}</div><span class="trArr">➜</span><div class="trTo">${f.to}</div>`;
      const seen=new Set(), lk=x._items.map(lkOf).filter(h=>h&&!seen.has(h)&&seen.add(h)).join("");
      const body=x._items.map(i=>txt(i)).join("<br>");
      rows+=`<div class="trRow"><span class="trSt trSt-${stOf(x)}">${ST[stOf(x)]}</span><span class="trRgC">${rgCol(x)}</span><div class="trFlow">${flow}</div><div class="trTx"><span class="trTxt">${body}</span>${lk?`<span class="trLks">${lk}</span>`:""}</div></div>`; });
    const head=rows?`<div class="trHead"><span>${en2?"Status":"狀態"}</span><span>${en2?"League":"賽區"}</span><span>${en2?"From":"原隊"}</span><span></span><span>${en2?"To":"新隊"}</span><span>${en2?"News":"消息"}</span></div>`:"";
    // ── 陣容表（使用者 2026-11-19：參考巴哈 LCK 陣容圖「左邊是戰隊 六大聯賽一路往下列」「傳聞就在ID前面打一個星號」
    //    「滑鼠移到那格顯示簽約到何時、上一位選手、新加入的選手原先來自哪個戰隊」）。資料＝transfers.js 的 board（scripts/transfers_board.py）
    const MODE=V.trMode||"board";
    const BL=["TOP","JNG","MID","BOT","SUP","COACH"], BLN={TOP:RL.TOP,JNG:RL.JNG,MID:RL.MID,BOT:RL.BOT,SUP:RL.SUP,COACH:en2?"Coach":"教練",HC:en2?"Head Coach":"主教練",STF:en2?"Staff":"後勤"};
    // 教練分兩欄（使用者 2026-11-19「教練分成兩欄 主教練 跟後勤」）：HC＝主教練、STF＝其他教練／分析師；資料仍是 COACH 一格，顯示時依 sr 拆
    const COLS=["TOP","JNG","MID","BOT","SUP","HC","STF"], isHC=e=>(e&&e.sr)==="HC";
    const colE=(t,c)=>c==="HC"?(t.r.COACH||[]).filter(isHC):c==="STF"?(t.r.COACH||[]).filter(e=>!isHC(e)):(t.r[c]||[]);
    const colP=(t,c)=>{ const pv=(t.prev||{})[c==="HC"||c==="STF"?"COACH":c]||[];
      return c==="HC"?pv.filter(isHC):c==="STF"?pv.filter(p=>!isHC(p)):pv; };
    const pn=s=>String(s||"").replace(/\s*\([^()]*\)\s*$/,"");
    // 教練欄只列這五種（使用者 2026-11-19「除了總教練 教練 分析師以外的教練都不要列出」「戰略教練也列出」「路線教練也可以」），名字後面標職稱
    const SRN=en2?{HC:"Head Coach",C:"Coach",SC:"Strategic",PC:"Positional",AN:"Analyst"}:{HC:"主教練",C:"教練",SC:"戰略教練",PC:"路線教練",AN:"分析師"};
    const today=new Date().toISOString().slice(0,10), ymd=s=>s?s.replace(/-/g,"/"):"";
    const LG_OF_RG=r=>RG_LG[r]||"";
    const board=(D.board||[]).filter(t=>!V.trRg||t.lg===LG_OF_RG(V.trRg));
    const bq=q, hitE=e=>bq&&(pn(e.n).toLowerCase().includes(bq)||String(e.p||"").toLowerCase().includes(bq));
    const bRows=board.filter(t=>!bq||[t.tm,t.nm,abOf(t.nm)].join(" ").toLowerCase().includes(bq)||BL.some(r=>(t.r[r]||[]).some(hitE)));
    const TIPS=[];
    // 格子提示（使用者 2026-11-19「除了評分的小框都重新設計」）：同評分小框的版型——標題列＝隊徽＋隊名＋路線；
    //   每個人一張小卡（名字＋狀態標籤、合約／加入／來自 的欄位、傳聞引用框）；上一位獨立一區（期間＋年資）
    // 聯賽識別色＝全站 LGC（使用者 2026-11-19「要跟積分分頁的聯賽顏色一樣」），不另外定義
    const laneIc=r=>(r==="COACH"||r==="HC"||r==="STF")?`<img src="img/COACH.png" alt="">`:(POS_IMG[r]?`<img src="${POS_IMG[r]}" alt="">`:"");
    const pill=(c,tx)=>`<span class="tpPill ${c}">${tx}</span>`;
    // 綠＝合約還在、但傳出可能去別隊（使用者 2026-11-19「如果合約還在但有傳出可能去別隊 上綠色」）；合約已到期的維持藍字、提示照樣看得到傳聞
    const roOn=e=>!!(e&&e.ro&&!(e.c&&e.c<today&&!e.rs));   // 合約沒確定到期就算（GCD 沒紀錄的 FLY Quad 也上綠；使用者 2026-11-20）
    const stPill=e=>e.gone?pill("tpB",en2?"Departure announced":"已宣布離隊"):e.r?pill("tpY",en2?"Rumor":"傳聞"):e.pm?pill("tpV",en2?"Promoted":"升職"):e.new?pill("tpR",en2?"New":"新加入"):roOn(e)?pill("tpG",en2?"Possible move":"可能轉會")
      :(e.c&&e.c<today&&!e.rs)?pill("tpB",en2?"Contract expired":"合約到期"):e.rs?pill("tpK",en2?"Re-signed":"續約"):"";
    const tmChip=n=>`<span class="tpTm">${teamLogoHTML(tAb(n),16,true,n)||""}${esc(abOf(n))}</span>`;
    const tenureP=o=>{ if(!o.s)return null; const unk=o.e==="?", e=(!o.e||unk)?today:o.e;
      const mo=(+e.slice(0,4)-+o.s.slice(0,4))*12+(+e.slice(5,7)-+o.s.slice(5,7)), y=Math.floor(mo/12), m=Math.max(mo%12,0);
      return {per:`${ymd(o.s).slice(0,7)} – ${unk?(en2?"leave date not recorded":"離隊日未記錄"):o.e?ymd(o.e).slice(0,7):(en2?"now":"今")}`,
        du:unk?"":(en2?(y?`${y}y${m?` ${m}m`:""}`:`${m}m`):(y?`${y} 年${m?` ${m} 個月`:""}`:`${m} 個月`))}; };
    const cellTip=(t,r)=>{ const es=colE(t,r), pv=colP(t,r);
      let h=`<div class="tpBox" style="--lgc:${LGC[t.lg]||"var(--gold)"}"><div class="rtHd">${teamLogoHTML(tAb(t.nm),22,true,t.nm)||""}<b>${esc(abOf(t.nm))}</b>`
        +`<span class="tpLane">${laneIc(r)}${BLN[r]}</span><span class="tpLg">${esc(t.lg)}</span></div>`;
      if(!es.length)h+=`<div class="rtEmpty">${en2?"Vacant":"空缺"}</div>`;
      es.forEach(e=>{ const kv=[];
        if(e.rs&&(!e.c||e.c<today))kv.push([en2?"Contract":"合約",e.rs!=="1"?`${en2?"re-signed through":"續約到"} ${e.rs}`:(en2?"re-signed":"已續約")]);
        else if(e.c)kv.push([en2?"Contract":"合約",e.c<today?`<span class="tbExp">${en2?"expired":"已到期"} ${ymd(e.c)}</span>`:`${en2?"until":"到"} ${ymd(e.c)}`]);
        else if(!e.r)kv.push([en2?"Contract":"合約",`<span class="tbMuted">${en2?"not on record":"GCD 無紀錄"}</span>`]);
        // 升職怎麼升的（使用者 2026-11-20「升職怎麼樣的升法 小框要寫」）：職稱異動「教練 → 主教練」；或「從 二隊 上調」
        if(e.pm){ const RZ={"Head Coach":"主教練","Interim Head Coach":"代理主教練","Assistant Coach":"教練","Strategic Coach":"戰略教練","Positional Coach":"路線教練","Coach":"教練","Analyst":"分析師","Head Analyst":"分析師"};
          kv.push([en2?"Promoted":"升職",typeof e.pm==="string"?e.pm.split(" to ").map(z=>en2?z:(RZ[z.trim()]||z)).join(" → "):(e.from?(en2?`called up from ${tmChip(e.from)}`:`從 ${tmChip(e.from)} 上調`):(en2?"promoted":"升職"))]); }
        if(e.new)kv.push([en2?"Joined":"加入",ymd(e.new)]);
        if(e.from&&!(e.pm&&typeof e.pm!=="string"))kv.push([en2?"From":"來自",tmChip(e.from)]);   // 上調的已經寫「從 X 上調」，不重複寫來自（使用者 2026-11-20）
        h+=`<div class="tpP"><div class="tpName"><b class="${tbCls(e)}">${esc(pn(e.n))}</b>${e.sr?`<span class="tpSr">${SRN[e.sr]}</span>`:""}${stPill(e)}</div>`
          +(kv.length?`<div class="tpKv">${kv.map(([k,v])=>`<span>${k}</span><span>${v}</span>`).join("")}</div>`:"")
          +(e.r&&e.tip?`<div class="tpQ"><span>${ymd(e.d).slice(5)}・${esc(e.src||"Sheep Esports")}</span>${esc(e.tip)}</div>`:"")
          +(e.ro?`<div class="tpQ tpQg"><span>${ymd(e.ro.d).slice(5)}・${esc(e.ro.src||"Sheep Esports")}・${en2?"rumored to":"傳聞去"} ${tmChip(e.ro.to)}</span>${esc(e.ro.tip)}</div>`:"")+`</div>`; });
      if(pv.length){ h+=`<div class="tpPv">`   /* 不寫「上一位」標題，靠分隔線隔開（使用者 2026-11-19） */
        +pv.map(p=>{ const o=typeof p==="string"?{n:p}:p, T=tenureP(o);
          // 上一位改成跟上面同一種小卡（使用者 2026-11-19「上一位跟上面合約有續約的UI相近一點」）：名字＋職稱＋標籤，下面 效力／年資 欄位
          // 還沒宣布離隊、只是被新人擠到這裡的（WBG Elk）：寫合約到期日，不寫效力期間（使用者 2026-11-20）
          const kv=o.still?(o.c?[[en2?"Contract":"合約",`<span class="tbExp">${en2?"expired":"已到期"} ${ymd(o.c)}</span>`]]:[])
            :T?[[en2?"Tenure":"效力",T.per],...(T.du?[[en2?"Length":"年資",T.du]]:[])]:[];
          return `<div class="tpP tpPvC"><div class="tpName"><b>${esc(pn(o.n))}</b>${(r==="STF"||r==="HC")&&o.sr&&SRN[o.sr]?`<span class="tpSr">${SRN[o.sr]}</span>`:""}${o.still?pill("tpB",en2?"Contract expired":"合約到期"):pill("tpX",en2?"Left":"離隊")}</div>`
            +(kv.length?`<div class="tpKv">${kv.map(([k,v])=>`<span>${k}</span><span>${v}</span>`).join("")}</div>`:"")+`</div>`; }).join("")+`</div>`; }
      TIPS.push(h+`</div>`); return TIPS.length-1; };
    // 轉會評分（使用者 2026-11-19「教練右邊新增一欄 轉會評分 依照原先選手的成績去與新選手的成績對比 判斷是加分還是扣分 然後教練只看主教練」）：
    //   選手＝選手分頁同一套「評分」（calcPlayers 同路百分位，withRef(0) 借整年全部賽事、不吃上方篩選），每條路 新人 − 上一位；
    //   教練只看總教練：教練沒有個人數據 ⇒ 新總教練原隊的戰隊評分 − 本隊的戰隊評分（calcTeams）。
    //   只算官方確認的新人（傳聞不算）；新人或上一位沒有該年比賽資料的那條路不計。年份要切到該休賽期的賽季才算得出來
    const SEASON=+String(D.from||"").slice(0,4)||0;
    const RATE=(()=>{ if(window.TRANSFER_RATE)return window.TRANSFER_RATE;   // 轉會網站：主站排程先算好匯出（transfers_site.js）
      if(curYear!==SEASON||typeof calcPlayers!=="function")return null;
      const k=curYear+"|"+(GAMES||[]).length+"|s3w2"; if(window._tbRC&&window._tbRC.k===k)return window._tbRC;
      const res={k,pl:{},tm:{}};
      // 只看第三賽段（使用者 2026-11-20「轉會評分只看第三賽段數據以及最終成績」）：各聯賽最後一個賽段（S3；CBLOL 只有兩段＝S2）例行賽＋季後賽，
      //   用場次白名單（H2H）圈範圍，其他篩選全部清空；最終成績（世界賽／季後賽名次）在主教練戰績分那邊加
      const S3RUN=fn=>{ const last={}; (GAMES||[]).forEach(o=>{ const m=/^S(\d)/.exec(String(o.split||"")); if(m)last[o.league]=Math.max(last[o.league]||0,+m[1]); });
        const keep=new Set((GAMES||[]).filter(o=>{ const m=/^S(\d)( PO)?$/.exec(String(o.split||"")); return m&&+m[1]===last[o.league]; }).map(gkey));
        const sv={split:F.split,league:F.league,patch:F.patch,d1:F.d1,d2:F.d2,minG:F.minG}, svH=H2H;
        F.split=""; F.league="ALL"; F.patch=""; F.d1=""; F.d2=""; F.minG=0; H2H=keep;
        try{ return fn(); } finally{ H2H=svH; Object.assign(F,sv); } };
      S3RUN(()=>{ for(const r of ["TOP","JNG","MID","BOT","SUP"]){ const m=res.pl[r]={};
          calcPlayers(r,true).forEach(x=>{ const nk=String(x._pn||"").toLowerCase(); if(x.評分!=null&&(!m[nk]||m[nk].g<x.場數))m[nk]={v:x.評分,g:x.場數,lg:x._lg||"",tm:x._team||""}; });
          const vs=Object.values(m).map(x=>x.v).sort((a,b)=>a-b), h=vs.length>>1;   // 該路全部選手評分的中位數（今年沒比賽資料的人用它當基準）
          res.md=res.md||{}; res.md[r]=vs.length?(vs.length%2?vs[h]:(vs[h-1]+vs[h])/2):null; }
        calcTeams("").forEach(x=>{ if(x.評分!=null)res.tm[teamFix(String(x.戰隊||""))]=x.評分; if(x.勝率!=null&&x.場數>=5)(res.wr=res.wr||{})[teamFix(String(x.戰隊||""))]=x.勝率; }); });
      // 沒打第三賽段的人（Noah 全年在 LEC 58 場、但第三賽段沒上）⇒ 退回全年評分，不要直接當沒資料用中位數（使用者 2026-11-20）
      res.plY={}; withRef(0,()=>{ for(const r of ["TOP","JNG","MID","BOT","SUP"]){ const m=res.plY[r]={};
          calcPlayers(r,true).forEach(x=>{ const nk=String(x._pn||"").toLowerCase(); if(x.評分!=null&&(!m[nk]||m[nk].g<x.場數))m[nk]={v:x.評分,g:x.場數,lg:x._lg||"",tm:x._team||""}; }); } });
      // 聯賽強度（使用者 2026-11-20「應該以預測模型的聯賽強弱去給權重」）：跟預測分頁 MODEL 的賽區強度同一套——
      //   近三年國際賽「不同賽區」交手的 Bradley-Terry（前兩年 predict_hist.js 的 h2h＋今年 GAMES 的國際賽），ridge 0.05
      res.R=(()=>{ const REG={LCK:"LCK",LPL:"LPL",LEC:"LEC",LCS:"LCS","LTA N":"LCS",LCP:"LCP",CBLOL:"CBLOL","LTA S":"CBLOL"}, INTL=new Set(["WLDs","MSI","EWC","FST","DCup","AC"]);
        const bT=o=>o.raw[C.blue_teamname], rT=o=>o.raw[C.red_teamname], cnt={}, tr={};
        (GAMES||[]).forEach(o=>{ const rg=REG[o.league]; if(!rg)return; [bT(o),rT(o)].forEach(t=>{ const c=cnt[t]=cnt[t]||{}; c[rg]=(c[rg]||0)+1; }); });
        for(const t in cnt)tr[t]=Object.keys(cnt[t]).sort((a,b)=>cnt[t][b]-cnt[t][a])[0];
        const PP={}, add=(a,b,wa,wb)=>{ if(!a||!b||a===b)return; const k=[a,b].sort().join("|"), x=PP[k]=PP[k]||[0,0]; if(a<b){x[0]+=wa;x[1]+=wb;}else{x[0]+=wb;x[1]+=wa;} };
        const H=window.PRED_HIST||{}; [curYear-2,curYear-1].forEach(y=>{ const h=(H[String(y)]||{}).h2h||{}; for(const k in h){ const [a,b]=k.split("|"); add(a,b,h[k][0],h[k][1]); } });
        (GAMES||[]).forEach(o=>{ if(!INTL.has(o.league))return; const a=tr[bT(o)], b=tr[rT(o)]; if(a&&b&&a!==b)add(a,b,o.result===1?1:0,o.result===1?0:1); });
        const Rg={}; ["LCK","LPL","LEC","LCS","LCP","CBLOL"].forEach(g=>Rg[g]=0); const PR=Object.entries(PP).map(([k,v])=>[...k.split("|"),v[0],v[1]]).filter(x=>x[0] in Rg&&x[1] in Rg);
        for(let it=0;it<3000;it++){ const g={}; for(const k in Rg)g[k]=-0.05*Rg[k];
          for(const [a,b,wa,wb] of PR){ const p=1/(1+Math.exp(Rg[b]-Rg[a])), d=wa-(wa+wb)*p; g[a]+=d; g[b]-=d; }
          for(const k in Rg)Rg[k]+=0.004*g[k]; }
        return Rg; })();
      return window._tbRC=res; })();
    // 二隊／青訓／盃賽併回所屬一級聯賽（使用者 2026-11-20「KeSPA → LCK 不是跨聯賽」）
    const lgN=l=>{ const s=String(l||""); return /kespa|lck ?cl|lckc|lck ?(academy|as)|lck challengers/i.test(s)?"LCK":/ldl|lpl/i.test(s)?"LPL":/nacl|lcs/i.test(s)?"LCS":/cblol/i.test(s)?"CBLOL":/lcp|pcs|vcs|ljl/i.test(s)?"LCP":/lec/i.test(s)?"LEC":s; };
    const tmR=n=>RATE&&n?RATE.tm[teamFix(String(tAb(n)||n))]:undefined;
    // 主教練戰績分（使用者 2026-11-19「教練的評分就看該隊勝率以及最終成績 能否到世界賽 能否到季後賽 已經到了後的名次」）：
    //   勝率 × 50 ＋ 成績分（滿分 50）；成績＝陣容表的 rk（W世界賽名次／P最後賽段季後賽名次／I季後賽入圍賽／R例行賽）
    const RK={}; (D.board||[]).forEach(t=>{ if(t.rk)[t.nm,t.tm].forEach(n=>RK[teamFix(String(tAb(n)||n))]=t.rk); });
    const ACH=rk=>{ if(!rk)return null; const m=/^([WPIR])(\d+)/.exec(rk); if(!m)return null; const n=+m[2];
      return m[1]==="W"?(n===1?50:n===2?45:n<=4?40:n<=8?35:n<=11?30:n<=16?28:24):m[1]==="P"?Math.max(22-2*n,8):m[1]==="I"?6:0; };
    const RKN=rk=>{ if(!rk)return en2?"no result":"無成績"; const m=/^([WPIR])(.+)$/.exec(rk); const n=m[2];
      return en2?({W:"Worlds ",P:"Playoffs #",I:"Play-in ",R:"Regular #"}[m[1]]+n):({W:`世界賽 ${n==="1"?"冠軍":n==="2"?"亞軍":n}`,P:`季後賽第 ${n} 名`,I:"季後賽入圍賽",R:`例行賽第 ${n} 名`}[m[1]]); };
    const coachS=n=>{ if(!RATE||!n)return null; const k=teamFix(String(tAb(n)||n)), wr=(RATE.wr||{})[k]; if(wr==null)return null;
      const rk=RK[k], a=ACH(rk)||0; return {v:wr*50+a, wr, rk, note:`${RKN(rk)}・${en2?"WR":"勝率"} ${Math.round(wr*100)}%`}; };
    const rateOf=t=>{ if(!RATE)return null; const items=[];
      // 聯賽權重：別的聯賽來的分數 × exp(LGK × (原聯賽強度 − 本隊聯賽強度))；同聯賽＝1、強度缺＝1
      const blend=a=>{ const ts=a.tm?coachS(a.tm):null; return ts?(a.v+ts.v)/2:a.v; };
      // 中位數也用同一把尺（個人＋戰績各半之後的分數）重算，不然空缺的基準會比真人高一截
      const MDB=window._tbMDB&&window._tbMDB.k===RATE.k?window._tbMDB:(window._tbMDB={k:RATE.k});
      const mdOf=r=>{ if(r in MDB)return MDB[r]; const vs=Object.values(RATE.pl[r]||{}).map(blend).sort((x,y)=>x-y), h=vs.length>>1; return MDB[r]=vs.length?(vs.length%2?vs[h]:(vs[h-1]+vs[h])/2):null; };
      const LGK=0.3, lgW=lg=>{ const a=lgN(lg), b=t.lg, Rg=RATE.R||{}; return (!a||a===b||Rg[a]==null||Rg[b]==null)?1:Math.exp(LGK*(Rg[a]-Rg[b])); };
      for(const r of ["TOP","JNG","MID","BOT","SUP"]){ const P=RATE.pl[r], PY=(RATE.plY||{})[r]||{},
          get=n=>{ const k=String(pn(n)).toLowerCase(), a=P[k]||(PY[k]?{...PY[k],yr:1}:undefined); if(!a)return a;
            // 個人評分只看個人數據（弱隊核心會很高：Scout 在 NS 91.4、Faker 39.6）⇒ 跟所屬戰隊的戰績分（第三賽段勝率＋最終成績）各半
            //   （使用者 2026-11-20「Scout 為何能有 91.4 分 評分是不是怪怪的」；原話「只看第三賽段數據以及最終成績」）；戰隊沒有戰績資料就只用個人
            const v0=blend(a), w=lgW(a.lg); return {...a,raw:v0,v:v0*w,w}; };
        // 今年沒有比賽資料的人（使用者 2026-11-19「用全部該路線的分數中位數當做基準」）：s 補成中位數、標 md；兩邊都沒資料就不算
        const md=mdOf(r), fill=x=>x.s?x:(md==null?x:{...x,s:{v:md,g:0,lg:""},md:1}), byG=(a,b)=>(b.s?b.s.g:-1)-(a.s?a.s.g:-1);
        let nw=(t.r[r]||[]).filter(e=>e.new||e.tip).map(e=>({n:pn(e.n),s:get(e.n),rm:!!e.r})).sort((a,b)=>a.rm-b.rm||byG(a,b))[0];   // 官方優先；Sheep 消息（傳聞／官方未進 wiki）也算
        // 有人離隊、還沒補人（格子沒有官方的人、也沒傳聞）⇒ 空缺當中位數（使用者 2026-11-19「有選手離隊但還沒補新人也是這樣做」）
        if(!nw&&!(t.r[r]||[]).some(e=>!e.gone))nw={n:en2?"Vacant":"空缺",s:null,rm:false,vac:1};
        const od=[...((t.prev||{})[r]||[]),...(t.r[r]||[]).filter(e=>e.gone)].map(p=>{ const n=typeof p==="string"?p:p.n; return {n:pn(n),s:get(n)}; }).sort(byG)[0];
        if(nw&&od&&(nw.s||od.s)){ const A=fill(nw), B=fill(od);
          const tg=x=>[x.s.yr?(en2?"full year":"全年"):"",x.s.w&&Math.abs(x.s.w-1)>0.005?lgN(x.s.lg):""].filter(Boolean).join(" ");   // 只寫「全年 LEC」，不寫權重數字（使用者 2026-11-20）
          if(A.s&&B.s)items.push({r,nw:A.n,od:B.n,a:A.s.v,b:B.s.v,d:A.s.v-B.s.v,rm:A.rm,ma:A.md&&(A.vac?2:1),mb:B.md,ta:A.md?"":tg(A),tb:B.md?"":tg(B)}); } }
      const hc=(t.r.COACH||[]).find(e=>e.sr==="HC"&&(e.new||e.tip)&&e.from), A=hc&&coachS(hc.from), B=coachS(t.nm)||coachS(t.tm);
      if(hc&&A&&B)items.push({r:"COACH",nw:`${pn(hc.n)}（${abOf(hc.from)}・${A.note}）`,od:`${abOf(t.nm)}（${B.note}）`,a:A.v,b:B.v,d:A.v-B.v,rm:!!hc.r});
      return {items,sum:items.reduce((s,x)=>s+x.d,0),rm:items.some(x=>x.rm),vac:items.filter(x=>x.ma===2).length}; };
    // 評分小框（使用者 2026-11-19「評分的小框重新設計」）：標題列＝隊徽＋隊名＋總分；每條路一列＝路線圖示｜離隊（名字／分數）→ 加入｜增減色塊
    const rateTip=t=>{ const rt=rateOf(t), sg=v=>(v>0?"+":"")+v.toFixed(1), cls=v=>v>0?"tbUp":v<0?"tbDn":"";
      const has=rt&&rt.items.length;
      let h=`<div class="rtBox"><div class="rtHd">${teamLogoHTML(tAb(t.nm),22,true,t.nm)||""}<b>${esc(abOf(t.nm))}</b><span class="rtTt">${en2?"Transfer rating":"轉會評分"}</span>`
        +(has?`<b class="rtSum ${cls(rt.sum)}">${rt.rm?"(":""}${sg(rt.sum)}${rt.rm?")":""}</b>`:"")+`</div>`;
      if(!RATE)h+=`<div class="rtEmpty">${en2?`Switch the year to ${SEASON} to compute`:`年份切到 ${SEASON} 才會計算`}</div>`;
      else if(!has)h+=`<div class="rtEmpty">${en2?"No lineup change to compare yet":"這隊還沒有可比較的異動"}</div>`;
      else{ const pc=(n,v,md,rm,tg)=>`<span class="rtP"><span class="rtN">${esc(n)}${rm?`<span class="tbRum">${en2?"Rumor":"傳聞"}</span>`:""}</span>`
          +`<span class="rtV">${v.toFixed(1)}</span></span>`;   // 分數下面不寫「全年／中位數」註記（使用者 2026-11-20），算法在 ℹ️ 說明
        h+=`<div class="rtGrid"><span></span><span class="rtCh">${en2?"Out":"離隊"}</span><span></span><span class="rtCh">${en2?"In":"加入"}</span><span class="rtCh rtChD">${en2?"Diff":"增減"}</span>`;
        rt.items.forEach(x=>{ const ic=x.r==="COACH"?`<img src="img/COACH.png" alt="">`:(POS_IMG[x.r]?`<img src="${POS_IMG[x.r]}" alt="">`:"");
          h+=`<span class="rtIc" title="${BLN[x.r]}">${ic}</span>${pc(x.od,x.b,x.mb?1:0,false,x.tb)}<span class="rtAr">➜</span>${pc(x.nw,x.a,x.ma,x.rm,x.ta)}<b class="rtD ${cls(x.d)}">${sg(x.d)}</b>`; });
        h+=`</div>`; }   // 計算說明不放小框，寫在 ℹ️ 說明（使用者 2026-11-20）
      TIPS.push(h+`</div>`); return TIPS.length-1; };
    const rateCell=t=>{ const rt=rateOf(t), v=rt&&rt.items.length?rt.sum:null;
      return `<div class="tbCell tbRate" data-r="RATE" data-lb="${en2?"Rating":"評分"}" data-tb="${rateTip(t)}"><span class="tbCv">${v==null?`<span class="tbMuted">–</span>`:`<b class="${v>0?"tbUp":v<0?"tbDn":""}">${rt.rm?"(":""}${(v>0?"+":"")+v.toFixed(1)}${rt.rm?")":""}</b>`}</span></div>`; };
    // 顏色（使用者 2026-11-19，取代星號）：黃＝傳聞未確定、紅＝新加入、藍＝合約已到期但還沒宣布離隊（Doran）、粉＝本轉會期續約（使用者 2026-11-19「粉色 跟紅色相近」）、白＝留隊
    // 藍字刪除線＝已宣布離隊、這個位置還沒有新簽約也沒有傳聞（使用者 2026-11-19）
    const tbCls=e=>e.gone?"tbExp tbGone":e.r?"tbY":e.pm?"tbPm":e.new?"tbNew":roOn(e)?"tbOut":e.rs?"tbRs":(e.c&&e.c<today?(e.ro?"tbExp tbGone":"tbExp"):"");   // 合約到期沒宣布、但傳出去別隊（LØS Zest）也畫刪除線（使用者 2026-11-20）   // rs＝本轉會期有官方續約消息（GCD 還沒更新也算）⇒ 粉字
    // 圖例篩選＝三組，一框一顆按鈕、兩種一起篩（使用者 2026-11-20「一個框的意思是點擊也會一起點，不用分開點」）
    const TBG={add:["tbNew","tbRs","tbPm"],out:["tbExp","tbGone"],rum:["tbOut","tbY"]};
    if(V.tbF&&!TBG[V.tbF])V.tbF="";   // 舊存檔的單一類別值
    const tbMf=e=>{ const c=tbCls(e).split(" "); return (TBG[V.tbF]||[]).some(k=>c.includes(k)); };
    const vRows=bRows.filter(t=>(!V.tbF||Object.values(t.r).flat().some(tbMf)));
    const wkPg=p=>{ let s=String(p||""); try{ s=decodeURIComponent(s); }catch(_){} return s.replace(/ /g,"_"); };   // wiki 頁名：已編碼的先解開（Noah 連錯頁，使用者 2026-11-20）
    const nameH=e=>{ const n=esc(pn(e.n)), inner=bq&&hitE(e)?`<mark>${n}</mark>`:n;
      return `<span class="tbN ${tbCls(e)}${V.tbF&&!tbMf(e)?" tbDim":""}">${e.p?`<a href="https://lol.fandom.com/wiki/${encodeURIComponent(wkPg(e.p))}" target="_blank" rel="noopener">${inner}</a>`:inner}</span>`; };   // 格子不標教練職稱，只在小框顯示（使用者 2026-11-20）
    // 陣容到位打勾（使用者 2026-11-20「五路選手以及主教練都有新加入或續約了，一路有兩人有一個也可以，就在隊伍縮寫後面打個勾」）：
    //   每一格至少一人是官方新加入／官方續約；合約本來就還在（沒到期、沒傳出要走）的人也算確定
    const setE=e=>!e.r&&!e.gone&&!!(e.new||e.tip||e.rs||e.pm||(e.c&&e.c>=today&&!e.ro));
    const tbDone=t=>["TOP","JNG","MID","BOT","SUP","HC"].every(c=>colE(t,c).some(setE));
    let bHTML="", lastLg="";
    vRows.forEach(t=>{ if(t.lg!==lastLg){ const n=vRows.filter(x=>x.lg===t.lg).length;
        bHTML+=`<div class="tbLg" style="--lgc:${LGC[t.lg]||"var(--gold)"}"><b>${esc(t.lg)}</b><span>${esc((en2?{LCK:"Korea",LPL:"China",LEC:"EMEA",LCS:"North America",CBLOL:"Brazil",LCP:"Asia-Pacific"}:{LCK:"韓國",LPL:"中國",LEC:"歐洲",LCS:"北美",CBLOL:"巴西",LCP:"亞太"})[t.lg]||"")}</span><i>${n}${en2?" teams":" 隊"}</i></div>`; lastLg=t.lg; }
      bHTML+=`<div class="tbRow" style="--lgc:${LGC[t.lg]||"var(--gold)"}"><div class="tbTeam" title="${esc(t.nm)}">${teamLogoHTML(tAb(t.nm),26,true,t.nm)||teamLogoHTML(tAb(t.tm),26,true,t.tm)||""}<span>${esc(abOf(t.nm))}</span>${tbDone(t)?`<span class="tbOk" title="${en2?"All five lanes and the head coach are set":"五路與主教練都確定了"}">✔</span>`:""}</div>`
        +COLS.map(r=>{ const es=colE(t,r); return `<div class="tbCell" data-r="${r}" data-lb="${BLN[r]}" data-tb="${cellTip(t,r)}"><span class="tbCv">${es.length?es.map(nameH).join(`<span class="tbSep">/</span>`):`<span class="tbMuted">–</span>`}</span></div>`; }).join("")+rateCell(t)+`</div>`; });
    const bHead=`<div class="tbHd"><span></span>${COLS.map(r=>`<span>${(r==="HC"||r==="STF")?`<img class="trCoach" src="img/COACH.png" alt="">`:(POS_IMG[r]?`<img class="trRole" src="${POS_IMG[r]}" alt="">`:"")}${BLN[r]}</span>`).join("")}<span class="tbRateH">${en2?"Rating":"轉會評分"}</span></div>`;
    // 篩選列（使用者 2026-11-20「消息跟轉會表的篩選列也統一一下 並且直觀一點」）：兩種模式同一個順序——
    //   模式（圖示＋文字）｜賽區（聯賽色）｜該模式自己的篩選（分組、組間直線）｜……｜更新時間＋搜尋（最右）
    const FG=(lb,inner)=>`<span class="trFG">${lb?`<label>${lb}</label>`:""}${inner}</span>`;
    const lgTx=r=>{ const l=rgNm(r); return `<span style="color:${LGC[l]||"inherit"};font-weight:800">${esc(l)}</span>`; };
    const modeBtns=FG("",btns("trMode",[["",`📋 ${en2?"Rosters":"陣容表"}`],["news",`📰 ${en2?"News":"消息"}`]]));
    const rgBtns=FG(en2?"League":"賽區",btns("trRg",[["",en2?"All":"全部"],...RGS.map(r=>[r,lgTx(r)])]));
    const newsBtns=FG(en2?"Status":"狀態",btns("trSt",[["",en2?"All":"全部"],["official",ST.official],["rumor",`<b class="tbY">${ST.rumor}</b>`],["conf",`<b class="trCf">${ST.conf}</b>`],["fake",`<b class="trFk">${ST.fake}</b>`]]))
      +FG(en2?"Type":"類型",btns("trKd",[["",en2?"All":"全部"],["join",KD.join],["leave",KD.leave],["other",KD.other]]))
      +FG(en2?"Source":"來源",btns("trSrc",[["",en2?"All":"全部"],["wiki","Leaguepedia"],["sheep","Sheep Esports"],["ptt","PTT"],["kr",SRCN.kr],["man",SRCN.man]]));
    const boardBtns=FG(en2?"Show":"顯示",`<span class="tbLegend">${[["add",[["tbNew",en2?"New signing":"新加入"],["tbRs",en2?"Re-signed":"續約"],["tbPm",en2?"Promoted":"升職"]]],["out",[["tbExp",en2?"Contract expired":"合約到期未宣布"],["tbGone",en2?"Departure announced":"已宣布離隊"]]],["rum",[["tbOut",en2?"Possible move":"可能轉會"],["tbY",en2?"Rumor":"傳聞"]]]]
        .map(([g,L])=>`<button class="sqLaneBtn tbLgB${V.tbF===g?" on":""}" data-k="tbF" data-v="${V.tbF===g?"":g}" title="${en2?"Show only these (click again to clear)":"只看這兩種（再點一次取消）"}">${L.map(([c,l])=>`<b class="tbN ${c==="tbGone"?"tbExp tbGone":c}">${l}</b>`).join(`<i class="tbLgSep">／</i>`)}</button>`).join("")}`
      +`</span>`);   // 「只看有異動」已刪（使用者 2026-11-20；休賽期幾乎每隊都有異動，沒作用）
    const metaTx=MODE==="news"?`${shown.length} / ${all.length}${D.at?`・${en2?"updated":"更新"} ${esc(D.at)}`:""}`:(D.at?`${en2?"as of":"截至"} ${esc(D.at)}`:"");
    main.innerHTML=`<div class="filters trBar">`+modeBtns+rgBtns+(MODE==="news"?newsBtns:boardBtns)
      // 搜尋放最右邊（使用者 2026-11-20「篩選列重新調整一下 搜尋應該在最右邊」）
      +`<span style="flex:1"></span><span class="meta">${metaTx}</span>`
      +`<label>${en2?"Search":"搜尋"}</label><span class="cwrap"><input type="text" id="trQ" value="${esc(V.trQ||"")}" placeholder="${en2?"Player or team":"選手或隊名"}" style="width:190px;padding-right:26px"><button class="cx" tabindex="-1" data-x="trQ" title="一鍵清除">✕</button></span>`+`</div>`
      +(MODE==="news"?`<div class="card trList">${head}${rows||`<span class="sumEmpty">${V.trSrc==="sheep"?(en2?"No Sheep Esports posts collected yet.":"還沒有收錄到 Sheep Esports 的貼文。"):(en2?"No match":"沒有符合的消息")}</span>`}</div>`
        :`<div class="card tbBoard">${vRows.length?bHead+bHTML:`<span class="sumEmpty">${en2?"No match":"沒有符合的隊伍或選手"}</span>`}</div>`);
    // 隊徽視覺大小統一（使用者 2026-11-20「全面檢視隊徽 視覺上統一大小」）：圖檔都是正方形畫布，但圖案本身有扁（T1／DK／SHG）有窄（MKOI／DNS）
    //   ⇒ 用小畫布量圖案的外框，把「圖案面積」調成一樣（扁的放寬、方的略縮），寬最多 1.5 倍、高不超過原本的框；
    //   每個隊徽佔固定寬 1.5 倍的位子、置中 ⇒ 後面的縮寫對齊。量不到（跨網域沒開 CORS、file://）就維持原樣
    const LGF=window._tbLGF||(window._tbLGF=new Map()), LGP=window._tbLGP||(window._tbLGP=new Map());
    // 量外框用另外一張帶 crossOrigin 的圖（轉會網站的隊徽在主站網域；直接在顯示的圖上設 crossorigin，CORS 一失敗圖就整張不見）
    const lgGet=(src,cb)=>{ if(LGF.has(src)){ cb(LGF.get(src)); return; } if(LGP.has(src)){ LGP.get(src).push(cb); return; } LGP.set(src,[cb]);
      const done=m=>{ LGF.set(src,m); (LGP.get(src)||[]).forEach(f=>f(m)); LGP.delete(src); };
      const p=new Image(); p.crossOrigin="anonymous";
      p.onload=()=>{ let m=null; try{ const N=48, c=document.createElement("canvas"); c.width=c.height=N; const g=c.getContext("2d",{willReadFrequently:true}); g.drawImage(p,0,0,N,N);
          const d=g.getImageData(0,0,N,N).data; let x0=N,y0=N,x1=-1,y1=-1;
          for(let y=0;y<N;y++)for(let x=0;x<N;x++)if(d[(y*N+x)*4+3]>24){ if(x<x0)x0=x; if(x>x1)x1=x; if(y<y0)y0=y; if(y>y1)y1=y; }
          if(x1>=x0&&y1>=y0)m={fw:(x1-x0+1)/N,fh:(y1-y0+1)/N}; }catch(_){ m=null; } done(m); };
      p.onerror=()=>done(null); p.src=src; };
    const lgFit=img=>{ if(img.dataset.fit)return; const S=parseFloat(img.style.height)||img.height||0; if(!S)return; img.dataset.fit="0";
      lgGet(img.currentSrc||img.src,m=>{ if(!m||!img.isConnected)return; img.dataset.fit="1";
        const r=m.fw/m.fh, A=0.6*S*S, W=1.5*S; let w=Math.sqrt(A*r), h=Math.sqrt(A/r); const k=Math.min(1,W/w,S/h); w*=k; h*=k;
        const E=w/m.fw;   // 整張正方形圖要畫多大，圖案才是 w×h
        img.style.width=img.style.height=E+"px"; img.style.margin=`${(S-E)/2}px ${(W-E)/2}px`; img.style.maxWidth="none"; }); };
    const lgFitAll=root=>root.querySelectorAll(".tbTeam img,.trTeam img,.tpTm img,.rtHd img").forEach(lgFit);
    lgFitAll(main);
    if(MODE!=="news"){ // 格子提示（自建浮層：多行＋排版，原生 title 做不到）
      let tip=document.getElementById("tbTip"); if(!tip){ tip=document.createElement("div"); tip.id="tbTip"; document.body.appendChild(tip);
        addEventListener("scroll",()=>{ if(!tip.classList.contains("sheet"))tip.style.display="none"; },{passive:true});
        // 手機：點格子以外的地方收起底部小框
        document.addEventListener("click",e=>{ if(tip.classList.contains("sheet")&&!e.target.closest(".tbCell")&&!e.target.closest("#tbTip"))tip.style.display="none"; }); }
      const bd=main.querySelector(".tbBoard");
      // 手機／觸控（使用者 2026-11-20「幫我設計手機點擊時的 UI」）：沒有滑鼠懸停 ⇒ 點格子從畫面底部滑出小框（再點同一格或點別處收起）；格子裡的 wiki 連結在手機不直接跳走
      const touch=()=>matchMedia("(hover:none)").matches||innerWidth<760;
      const show=(c,sheet)=>{ tip.innerHTML=TIPS[+c.dataset.tb]+(sheet?`<button class="tbTipX" aria-label="close">✕</button>`:""); tip.classList.toggle("sheet",!!sheet); tip.style.display="block"; lgFitAll(tip);
        if(sheet){ tip.style.left=tip.style.top=""; tip.dataset.cur=c.dataset.tb; const x=tip.querySelector(".tbTipX"); if(x)x.onclick=()=>{ tip.style.display="none"; }; return; }
        const r=c.getBoundingClientRect(), w=tip.offsetWidth, h=tip.offsetHeight;
        let x=r.left+r.width/2-w/2, y=r.bottom+6; x=Math.max(8,Math.min(innerWidth-w-8,x)); if(y+h>innerHeight-8)y=r.top-h-6;
        tip.style.left=x+"px"; tip.style.top=y+"px"; };
      bd.onmouseover=e=>{ if(touch())return; const c=e.target.closest(".tbCell"); if(!c){ tip.style.display="none"; return; } show(c,false); };
      bd.onmouseleave=()=>{ if(!touch())tip.style.display="none"; };
      bd.onclick=e=>{ if(!touch())return; const c=e.target.closest(".tbCell"); if(!c)return; if(e.target.closest("a"))e.preventDefault();
        if(tip.style.display==="block"&&tip.classList.contains("sheet")&&tip.dataset.cur===c.dataset.tb){ tip.style.display="none"; return; } show(c,true); };
    } else { const tip=document.getElementById("tbTip"); if(tip)tip.style.display="none"; }
    main.querySelectorAll(".filters .sqLaneBtn[data-k]").forEach(b=>b.onclick=()=>{ V[b.dataset.k]=b.dataset.v; saveState(); render(); });
    const qi=document.getElementById("trQ");
    qi.oninput=()=>{ clearTimeout(window._trQT); window._trQT=setTimeout(()=>{ V.trQ=qi.value; saveState(); const pos=qi.selectionStart; render(); const q2=document.getElementById("trQ"); q2.focus(); q2.setSelectionRange(pos,pos); },300); };
    main.querySelector('.cx[data-x="trQ"]').onclick=()=>{ V.trQ=""; saveState(); render(); };
    })();
addBase(); }
const ls=document.getElementById("tsLang"); if(ls){ ls.value=LANG; ls.onchange=()=>{ try{localStorage.setItem("ts_lang",ls.value);}catch(e){} location.reload(); }; }
render();
})();
