(function(){var st=document.createElement("style");st.textContent=":root{\n    --bg:#0b0e14; --card:#141926; --card2:#1c2333; --line:#2a3345;\n    --tx:#e8ecf4; --tx2:#8b98ad; --acc:#4f8ef7; --acc2:#7c5cff; --gold:#f5b942;\n    --green:#5dd39e; --red:#e05c5c; --gap:14px; \n  }\n*{box-sizing:border-box}\nhtml,body{overflow-x:clip}\nhtml{scrollbar-gutter:stable}\n@font-face{font-family:\"GenSenRounded TW\";font-weight:400;src:url(\"fonts/GenSenRounded2TW-L.woff2\") format(\"woff2\"),url(\"fonts/GenSenRounded2TW-L.otf\") format(\"opentype\");font-display:swap;\n    ascent-override:106.7%;descent-override:26.7%;line-gap-override:0%}\n@font-face{font-family:\"GenSenRounded TW\";font-weight:700;src:url(\"fonts/GenSenRounded2TW-R.woff2\") format(\"woff2\"),url(\"fonts/GenSenRounded2TW-R.otf\") format(\"opentype\");font-display:swap;\n    ascent-override:106.7%;descent-override:26.7%;line-gap-override:0%}\nbody{margin:0;color:var(--tx);font-family:\"jf-openhuninn\",\"Microsoft JhengHei\",\"Segoe UI\",sans-serif;font-size:16.5px;\n    background:var(--bg)}\nbody::before{content:\"\";position:fixed;inset:0;z-index:-1;pointer-events:none;\n    background:radial-gradient(1200px 500px at 15% -10%,#1a2340 0%,transparent 60%),\n               radial-gradient(1000px 500px at 95% 0%,#241a3d 0%,transparent 55%)}\n::-webkit-scrollbar{width:9px;height:9px}\n::-webkit-scrollbar-thumb{background:#2e3a52;border-radius:9px}\n::-webkit-scrollbar-track{background:transparent}\n.filters select,.filters input{height:30px;box-sizing:border-box;padding-top:3px;padding-bottom:3px;line-height:1.2}\n.filters .pgbtn,.filters .pgbtn *{height:30px;box-sizing:border-box}\n.filters .pgbtn{padding-top:3px;padding-bottom:3px;line-height:1.2;display:inline-flex;align-items:center}\nheader{display:flex;align-items:center;gap:14px;padding:12px 30px;position:sticky;top:0;z-index:100;flex-wrap:wrap;\n    background:rgba(15,19,30,.85);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}\nheader h1{font-size:21px;margin:0;display:flex;align-items:center;background:linear-gradient(90deg,#7cb3ff,#b79bff);\n    -webkit-background-clip:text;background-clip:text;color:transparent;letter-spacing:.5px}\n.meta{color:var(--tx2);font-size:13.5px}\nmain{max-width:none;margin:0;padding:14px 30px;container-type:inline-size;container-name:mainc}\n#main img{translate:0 1px}\n.filters .tab{cursor:pointer;border:1px solid var(--line);border-radius:999px;transition:border-color .12s,color .12s}\n.filters .tab:hover:not(.on){border-color:var(--acc);color:var(--acc)}\n.filters .tab.on{color:#fff}\n.filters .posLbl .posic{width:22px;height:22px}\n.filters{display:flex;flex-wrap:wrap;gap:10px 11px;align-items:center;border:1px solid var(--line);\n    border-radius:14px;padding:12px 18px;margin-bottom:var(--gap);background:linear-gradient(180deg,#161c2b,#131826)}\n.filters label{color:var(--tx2);font-size:15px}\n.filters select,.filters input{font-size:15px}\n.bpFRow .fsel.hasV:hover,.bpFRow input.bpColF.on:hover{cursor:pointer;background-image:linear-gradient(#e0574d,#e0574d);background-repeat:no-repeat;background-size:calc(100% - 12px) 2px;background-position:center}\nselect,input,textarea,button{background:var(--card2);color:var(--tx);border:1px solid var(--line);\n    border-radius:9px;padding:8px 12px;font-family:inherit;font-size:15.5px;outline:none}\nselect:focus,input:focus,textarea:focus{border-color:var(--acc)}\nbutton{cursor:pointer;transition:.15s}\nbutton:hover{border-color:var(--acc)}\nbutton.primary{background:linear-gradient(135deg,var(--acc),var(--acc2));border-color:transparent;color:#fff;font-weight:bold}\nbutton.primary:hover{filter:brightness(1.15)}\n.sqbtn{width:30px;height:30px;padding:0;font-size:15px;line-height:1;flex:0 0 auto;\n    display:inline-flex;align-items:center;justify-content:center}\n.grid .card{margin-bottom:0}\n.grid>*{min-width:0}\n@media(max-width:820px){header{padding:8px 10px;gap:8px}\nheader h1{font-size:17px}\nheader h1 img{width:26px!important;height:26px!important}\nmain{padding:10px}}\n@media(max-width:1099.98px){.filters .barBtns{flex-wrap:wrap;justify-content:flex-end;max-width:100%;row-gap:6px}\nheader{position:static;padding:8px 10px 6px}}\n@container mainc (max-width:820px){.filters{padding:8px 10px;gap:8px}\n.tphdr{padding-right:0!important}\n.tpctl{position:static!important;flex-wrap:wrap;margin-bottom:6px}\n.card{overflow-x:auto}\n.card table{table-layout:auto;width:max-content;min-width:100%}}\n.card{background:linear-gradient(180deg,#161c2b,#121722);border:1px solid var(--line);border-radius:14px;\n    padding:16px;margin-bottom:var(--gap);box-shadow:0 4px 24px rgba(0,0,0,.35)}\n.card h2{font-size:19px;margin:0 0 12px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}\n.card h2 .sub{color:var(--tx2);font-weight:normal;font-size:15.5px}\ntable.tblEven td:has(.heroname){padding-left:11px}\n.tblwrap{overflow:visible;border:1px solid var(--line);border-radius:10px;background:#161c2b}\n.tblwrap table{table-layout:auto;width:max-content;min-width:100%}\n#main[data-view=\"英雄\"] .tblwrap table,#main[data-view=\"選手\"] .tblwrap table,#main[data-view=\"戰隊\"] .tblwrap table{min-width:0}\n.tblwrap.hscroll{overflow-x:auto}\n.tblwrap.hscroll th{top:0}\n.tblwrap.pt1 th,.tblwrap.pt1 td{padding-left:4px;padding-right:4px}\n.tblwrap.pt2 th,.tblwrap.pt2 td{padding-left:2px;padding-right:2px}\n#tierPool.tpNarrow .tphdr{padding-right:0!important}\n#tierPool.tpNarrow .tpctl{position:static!important;margin-top:6px;justify-content:flex-start}\n.tLaneIco.tLPn .cx{display:none!important}\n.tLaneIco.tLPn input{padding-right:8px!important;padding-left:8px!important}\n@media(pointer:coarse){select,input,textarea{font-size:16px!important}\n#tierPool .tphdr{padding-right:0!important}\n#tierPool .tpctl{position:static!important;margin-top:6px;justify-content:flex-start}\n.tblwrap{-webkit-overflow-scrolling:touch}}\n@container mainc (max-width:1980px){table.tblEven td:has(.heroname){padding-left:7px}}\ntable.tblEven .thL{padding:0}\ntable.tblEven .sortArr{right:-12px}\n@keyframes sp{to{transform:rotate(360deg)}}\n.cc:has(>img.glow)>.po,#main[data-view=\"比賽BP\"] .cc:hover>.po{z-index:4;transform:translate(1.25px,-1.25px)}\ninput[type=number]::-webkit-outer-spin-button,input[type=number]::-webkit-inner-spin-button{-webkit-appearance:none;margin:0}\ninput[type=number]{-moz-appearance:textfield;appearance:textfield}\n.cwrap{position:relative;display:inline-flex;align-items:center}\n.cwrap .combo{padding-right:26px}\n.cx{position:absolute;right:5px;background:none;border:none;color:var(--tx2);padding:0 3px;font-size:13px;cursor:pointer;line-height:1}\n.cx:hover{color:#ff6b6b}\ninput.combo::-webkit-calendar-picker-indicator,input[list]::-webkit-calendar-picker-indicator{display:none!important;opacity:0;width:0}\n.cwrap .cal{position:absolute;right:24px;background:none;border:none;cursor:pointer;font-size:13px;padding:0 2px;line-height:1}\n.cwrap .cal:hover{filter:brightness(1.4)}\n.rosterGrid .card{margin-bottom:0;padding:20px}\n.rosterGrid .card{overflow-x:auto}\n.laneHd .meta{font-size:25px}\n.chgLanes .card{margin-bottom:0}\n#hoverTip .scGrid>*{padding:3.5px 0}\n#hoverTip .tipTitle .meta{font-size:13.5px}\n#hoverTip .tipRow .meta{color:#7a8aaa;font-size:11.5px;margin-left:6px}\n#hoverTip .tGrid .rt .v{font-size:22px;font-weight:bold;line-height:1.1}\n.skillsBody .tipTitle .meta{font-size:14px;color:#7a8aaa}\n.skillsBody .tipRow .meta{color:#7a8aaa;font-size:12.5px;margin-left:6px}\n.dexIt .meta{font-size:13.5px}\n.jgCtrl select,.jgCtrl #jgSortBtn{height:30px;box-sizing:border-box;padding-top:3px;padding-bottom:3px;line-height:1.2;font-size:15px}\n.jgHd .jgMeta,.jgHd>.meta{font-size:13.5px!important}\n.sqbtn.helpBtn{width:30px;padding:0}\n.filters .barBtns .sqbtn,.sqbtn.helpBtn{font-size:17px;line-height:1}\n#main[data-view=\"英雄Tier\"] .tChip:hover>img,\n  #main[data-view=\"英雄Tier\"] .tChip>img.tglow, \n  #main[data-view=\"比賽BP\"] .cc:hover img{transform:scale(1.05);position:relative;z-index:3;\n    box-shadow:0 0 5px 3px rgba(255,255,255,.3)}\n#main[data-view=\"英雄Tier\"] .tChip:hover .tlic img,\n  #main[data-view=\"英雄Tier\"] .tChip:has(>img.tglow) .tlic img{transform:scale(1.05);filter:drop-shadow(0 0 4px rgba(255,255,255,.95))}\n#main td:has(.cc:hover),#main th:has(.cc:hover){overflow:visible}\n#main td:has(.cc img.glow),#main td:has(.cc img.glowS),#main td:has(.heroname.chi){overflow:visible}\n#main .dexIt:has(.cc:hover),#main .dexIt:has(.cc img.glow),#main .chgHead:has(.cc:hover),#main .chgHead:has(.cc img.glow){overflow:visible;position:relative;z-index:4}\nbody.bpDragging .bpSlot::before{pointer-events:auto}\nbody.carrying{cursor:grabbing}\nbody.carrying .tierRow{outline:2px dashed rgba(245,185,66,.55);outline-offset:-3px}\n@keyframes bpPulse{0%,100%{box-shadow:0 0 5px rgba(245,185,66,.45)}50%{box-shadow:0 0 14px rgba(245,185,66,.9)}}\n.bpSlot .meta{font-size:12px}\n#tmGrid .card{padding:10px 12px;margin-bottom:0}\n#tmGrid .card h2{margin-bottom:8px}\n#tmGrid .card h2 .lg{font-size:20px;padding:3px 15px}\n#tmGrid .card h2 .sub{font-size:19px}\n#tmGrid tbody .lg{font-size:15.5px}\n.heroname .lg{font-size:inherit}\na.spWiki{color:inherit;text-decoration:none;border-bottom:1px dotted rgba(150,165,195,.55)}\na.spWiki:hover{color:var(--acc);border-bottom-color:var(--acc)}\n.tblwrap th:nth-child(1),.tblwrap td:nth-child(1){position:sticky;left:0;background:#161c2b;z-index:2;min-width:34px}\n.tblwrap th:nth-child(2),.tblwrap td:nth-child(2){position:sticky;left:46px;background:#161c2b;z-index:2}\n.tblwrap thead th:nth-child(1),.tblwrap thead th:nth-child(2){z-index:5}\n.tblwrap tbody tr:nth-child(even) td:nth-child(1),\n  .tblwrap tbody tr:nth-child(even) td:nth-child(2){background:#1a202f}\n.tblwrap tbody tr:hover td:nth-child(1),\n  .tblwrap tbody tr:hover td:nth-child(2){background:#1e2740}\n.lg{display:inline-block;padding:1px 9px;border-radius:999px;font-size:12px;font-weight:bold;background:#141b2b;border:1px solid #33405c}\n.dlyHd .lg{font-size:11.5px;opacity:.62}\nhtml[data-lang=en] .dlyStats{gap:11px}\n.dlyStat .meta{font-size:12px;margin-right:3px}\n.dlyStats .meta{font-weight:400}\n#sqMates .meta{font-size:20px}\n.sqLaneBtn{padding:3px 11px;border-radius:14px;border:1px solid #33405c;background:#141b2b;color:var(--tx2);cursor:pointer;font-size:12.5px}\n.sqLaneBtn.on{background:var(--acc);color:#fff;border-color:var(--acc)}\nhtml[data-lang=\"en\"] .ovChgLb{width:124px}\n.sumEmpty{color:var(--tx2)}\n.ntIt .meta{font-size:12px}\n.ntDoc h1{font-size:22px;margin:0 0 10px}\n.ntDoc a{color:#7fb2ff}\n.ntDoc a.ntTs{font-family:Consolas,monospace;font-size:.92em}\n.tbBoard{padding:6px 16px 14px;display:grid;grid-template-columns:max-content repeat(6,minmax(0,1fr)) minmax(0,1.4fr) max-content;column-gap:0}\n.tbN.tbRet,b.tbRet{color:#8b98ad;text-decoration:line-through}\n.tbLegend .sqLaneBtn b.tbRet{text-decoration:none;display:inline-block;background:linear-gradient(currentColor,currentColor) left 54%/100% 1.5px no-repeat}\n.tbN.tbY,b.tbY{color:#ffc850}\n.tbN.tbNew,b.tbNew{color:#ff5a5a}\n.tbN.tbExp,b.tbExp{color:#5aa9ff}\n.tbN.tbRs,b.tbRs{color:#ff8ec6}\n.tbN.tbPm,b.tbPm{color:#ff8ec6}\n.tbN.tbOut,b.tbOut{color:#4cd07d}\n.tbOk{color:#4cd07d;font-size:14px;margin-left:2px}\n.tbN.tbGone{text-decoration:line-through;text-decoration-thickness:1px}\n.rtBox .tbN.tbGone{text-decoration:none}\n.tbN.tbDim{opacity:.2}\n.tbVacN{font-style:normal;font-size:11px;font-weight:700;color:var(--tx2);margin-left:6px;padding:0 6px;border:1px solid rgba(255,255,255,.2);border-radius:999px;white-space:nowrap}\n.tbLegend .sqLaneBtn b{font-weight:700}\n.tbLgB{display:inline-flex;align-items:center;gap:2px}\n.tbLgSep{font-style:normal;color:var(--tx2);margin:0 3px}\n.tbLegend .sqLaneBtn{margin-right:2px}\n.tbLegend .sqLaneBtn.on,.trBar .sqLaneBtn[data-mk].on{background:rgba(255,255,255,.14);border-color:var(--tx);box-shadow:0 0 0 1px var(--tx) inset;color:var(--tx)}\n.tbLgG .sqLaneBtn:not(.on){background:transparent;border-color:transparent}\n.trFG{display:inline-flex;align-items:center;gap:6px;padding-left:12px;border-left:1px solid rgba(255,255,255,.16)}\n.trFG:first-child{border-left:0;padding-left:0}\n.trFG>label{margin-right:2px}\n.tbLegend{display:inline-flex;gap:6px;align-items:center}\n.trSrc-kr{color:#ff9a6b;background:rgba(255,154,107,.12)}\n.trSrc-ptt{color:#c9d1e0;background:rgba(255,255,255,.08)}\n.trSrc-man{color:#ffd166;background:rgba(255,209,102,.12)}\n.tbLegend{display:inline-flex;gap:12px;align-items:center}\n.tbLegend b.tbStay{color:#fff}\n.tbCell.tbFaCo{display:none}\n.tbHd,.tbRow{grid-column:1/-1;display:grid;grid-template-columns:subgrid;align-items:center}\n.tbHd{position:sticky;top:0;z-index:2;background:#161c2b;padding:7px 0 9px;border-bottom:1px solid var(--line);font-weight:700;color:var(--tx);font-size:16px}\n.tbHd>span{display:flex;align-items:center;justify-content:center;gap:4px}\n.tbLgIc{width:20px;height:20px;object-fit:contain;border-radius:5px;background:#e8ecf4;padding:2px;box-sizing:border-box;flex:0 0 auto}\n.tbLg{grid-column:1/-1;display:flex;align-items:center;gap:10px;margin:26px 0 6px;padding:8px 14px 8px 17.5px;border-radius:8px;border-left:5px solid var(--lgc);background:linear-gradient(90deg,color-mix(in srgb,var(--lgc) 22%,transparent),transparent 70%)}\n.tbHd+.tbLg{margin-top:12px}\n.tbLg b{font-size:22px;font-weight:900;letter-spacing:.5px;color:var(--lgc)}\n.tbLg span{font-size:14px;font-weight:700;color:var(--tx2)}\n.tbLg i{font-style:normal;font-size:13px;color:var(--tx2);margin-left:auto}\n.tbRow{min-height:44px;border-radius:6px}\n.tbRow:nth-of-type(even){background:rgba(255,255,255,.035)}\n.tbRow:hover{background:rgba(255,255,255,.07)}\n.tbTeam{display:flex;align-items:center;gap:8px;padding:6px 18px 6px 10px;font-weight:800;font-size:16px;white-space:nowrap;border-left:3px solid color-mix(in srgb,var(--lgc,transparent) 70%,transparent)}\n.tbCell{text-align:center;padding:6px 6px;font-size:15px;line-height:1.5;cursor:default}\n.tbCell.tbSpan2{grid-column:span 2}\n.tbRtSz{display:block;height:0;overflow:hidden;visibility:hidden;white-space:nowrap}\n.tbRow>.tbTeam{align-self:stretch}\n.tbFaIc{object-fit:contain;border-radius:6px;background:#e8ecf4;flex:0 0 auto;margin:0 6.5px;padding:3px;box-sizing:border-box}\n.tbTeam img.tbFaIc{width:20px!important;height:20px!important;margin:0 9.5px!important;padding:2px;border-radius:5px}\n.tbRate{min-width:72px;padding:6px 13px;font-variant-numeric:tabular-nums;text-align:center;white-space:nowrap}\n.tbRateH{padding:0 13px;text-align:center}\n.tbCell.tbRate .rtPc{margin-right:0}\n.tbCell.tbRate b{font-weight:400}\n.rtPc{font-style:normal;display:inline-block;margin-right:-.5em}\n.tbHd .tbRateH{justify-self:center}\n.tbUp{color:#ff5a5a}\n.tbDn{color:#3fcf7a}\n.tbCell:hover{background:rgba(122,184,255,.10);border-radius:6px}\n.tbN{white-space:nowrap;display:inline-block}\n.tbN a{color:inherit;text-decoration:none}\n.tbN a:hover{color:#7fb2ff;text-decoration:underline}\n.tbSep{color:var(--tx2);margin:0 3px}\n.tbNw{white-space:nowrap}\n.tbSr{font-size:12px;font-weight:400;color:var(--tx2);margin-left:4px}\n.tbMuted{color:var(--tx2);opacity:.75}\n#tbTip{position:fixed;z-index:9999;display:none;max-width:340px;padding:10px 12px;border-radius:8px;background:#1b2338;border:1px solid rgba(255,255,255,.14);box-shadow:0 8px 24px rgba(0,0,0,.45);font-size:14px;line-height:1.6;color:var(--tx);pointer-events:none}\n#tbTip hr{border:0;border-top:1px solid rgba(255,255,255,.1);margin:6px 0}\n.tbRum{font-size:12px;padding:0 6px;border-radius:4px;background:rgba(255,200,80,.16);color:#ffc850}\n#tbTip:has(.tpBox){max-width:420px;padding:12px 14px}\n.tpBox{min-width:260px}\n.tpBox .rtHd{border-bottom-color:color-mix(in srgb,var(--lgc) 45%,transparent)}\n.tpLane{display:inline-flex;align-items:center;gap:5px;color:var(--tx);font-size:17px;font-weight:800}\n.tpLane img{width:18px;height:18px;object-fit:contain}\n.tpLg{margin-left:auto;padding:1px 8px;border-radius:999px;font-size:13px;font-weight:800;color:var(--lgc);border:1px solid color-mix(in srgb,var(--lgc) 55%,transparent)}\n.tpP{padding:8px 10px;border-radius:8px;background:rgba(255,255,255,.04);margin-top:8px}\n.tpP:first-of-type{margin-top:0}\n.trShIc{width:22px;height:22px;display:block;margin:auto;color:#eef2fb}\n.trShD{position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;padding:16px;box-sizing:border-box;background:rgba(5,8,14,.74)}\n.trShD .trShBox{width:min(560px,100%);max-height:calc(100vh - 32px);overflow:auto;box-sizing:border-box;padding:0 18px 18px;border-radius:14px;background:#161c2b;border:1px solid #2a3345;box-shadow:0 12px 44px rgba(0,0,0,.55);color:#e8ecf4;font-size:15px;text-align:left}\n.trShHd{display:flex;align-items:center;gap:10px;position:sticky;top:0;z-index:2;margin:0 -18px 10px;padding:6px 18px 4px;background:#161c2b;box-shadow:inset 18px 0 0 #161c2b,inset -18px 0 0 #161c2b,inset 0 -1px 0 rgba(255,255,255,.1)}\n.trShHd b{flex:1;font-size:17px;font-weight:800}\n.trShX{flex:0 0 auto;margin-right:-10px}\n.trShMsg{min-height:20px;margin-bottom:10px;font-size:13.5px;line-height:20px;color:#8b98ad}\n.trShMsg:empty{display:none}\n.trShImgs{display:grid;grid-template-columns:repeat(auto-fill,minmax(92px,1fr));gap:8px;margin-bottom:14px}\n.trShImgs:empty{display:none}\n.trShI{position:relative;aspect-ratio:1;border-radius:9px;overflow:hidden;background:#0b0e14;border:2px solid rgba(255,255,255,.12);cursor:pointer;box-sizing:border-box}\n.trShI img{display:block;width:100%;height:100%;object-fit:cover}\n.trShI{cursor:zoom-in}\n.trShImgs.one .trShI i{display:none}\n.trShI i{position:absolute;right:0;top:0;width:38px;height:38px;cursor:pointer}\n.trShI i::before{content:\"\";position:absolute;right:6px;top:6px;width:22px;height:22px;border-radius:50%;box-sizing:border-box;border:1.5px solid rgba(255,255,255,.85);background:rgba(11,14,20,.6)}\n.trShI b{position:absolute;left:0;right:0;bottom:0;padding:10px 6px 3px;font-size:11.5px;font-weight:700;line-height:1.3;color:#fff;text-align:left;white-space:nowrap;background:linear-gradient(rgba(5,8,14,0),rgba(5,8,14,.9))}\n.trShI.on{border-color:#5aa9ff}\n.trShI.on i::before{border-color:#5aa9ff;background:#5aa9ff}\n.trShI.on i::after{content:\"\";position:absolute;right:14px;top:9.5px;width:5px;height:10px;border:solid #fff;border-width:0 2px 2px 0;transform:rotate(45deg)}\n.trShI:not(.on) img{opacity:.42}\n.trShBtns{display:grid;gap:8px}\n.trShP.trShDl{background:#243049}\n.trShMsg .trShA{margin-left:10px;cursor:pointer}\n.trShZ{position:fixed;inset:0;z-index:5;display:flex;align-items:center;justify-content:center;background:rgba(3,5,9,.95)}\n.trShZI{max-width:100vw;max-height:100vh;overflow:auto;overscroll-behavior:contain}\n.trShZI img{display:block;width:min(96vw,calc(100vh - 76px));height:auto;max-width:none;cursor:zoom-in;border-radius:6px}\n.trShZI.big{width:100vw;height:100vh}\n.trShZI.big img{width:min(2000px,250vw);cursor:zoom-out;border-radius:0}\n.trShZX{position:fixed;top:6px;right:8px;z-index:2;margin:0;filter:drop-shadow(0 0 3px #000) drop-shadow(0 0 3px #000)}\n.trShZN{position:fixed;top:50%;z-index:2;width:44px;height:68px;margin-top:-34px;padding:0;border:0;border-radius:10px;background:rgba(10,14,22,.55);color:#fff;font-size:36px;line-height:60px;cursor:pointer}\n.trShZN[data-d=\"-1\"]{left:6px}\n.trShZN[data-d=\"1\"]{right:6px}\n.trShZT{position:fixed;left:0;right:0;bottom:8px;z-index:2;text-align:center;font-size:14px;color:#dfe6f5;pointer-events:none;text-shadow:0 0 4px #000,0 0 4px #000}\n.trShZT b{display:inline-block;margin-left:.8em;padding:1px 10px;border-radius:999px;background:#2f6fed;color:#fff;font-weight:700;text-shadow:none}\n.trShZT b.no{background:#6b4310;color:#ffd9a8}\n.trShP{display:flex;align-items:center;justify-content:center;gap:8px;min-width:0;height:44px;padding:0 6px;border-radius:10px;border:1px solid rgba(255,255,255,.2);color:#fff;font:inherit;font-size:15px;font-weight:700;cursor:pointer;transition:filter .12s,transform .12s}\n.trShP svg{flex:0 0 auto;width:20px;height:20px;display:block}\n.trShP span{min-width:0;overflow-wrap:anywhere}\n.trShP:hover:not(:disabled){filter:brightness(1.13)}\n.trShP:active:not(:disabled){transform:scale(.97)}\n.trShP:disabled{opacity:.38;cursor:default}\n.trShHint{min-height:22px;margin-top:10px;font-size:13.5px;line-height:1.6;color:#c9d4ea}\n.trShHint:empty{display:none}\n.trShA{display:inline-block;margin-left:6px;color:#7ab8ff;font-weight:700}\n@media (max-width:759.98px){.trShD{align-items:flex-end;padding:0}\n.trShD .trShBox{width:100%;max-height:88vh;border-radius:16px 16px 0 0;border-bottom:0;padding:0 14px calc(16px + env(safe-area-inset-bottom,0px))}\n.trShHd{margin:0 -14px 10px;padding:6px 14px 4px;box-shadow:inset 14px 0 0 #161c2b,inset -14px 0 0 #161c2b,inset 0 -1px 0 rgba(255,255,255,.1)}\n.trShP{font-size:14px;gap:6px}\n.trShZN{top:auto;bottom:0;margin-top:0;width:56px;height:44px;line-height:38px;background:none}}\n@media (max-width:359.98px){.trShP span{font-size:12.5px}}\n.tbTmA{color:inherit;text-decoration:none}\n.tbTmA:hover{text-decoration:underline}\n#tbTip .tpName a{cursor:pointer}\n#tbTip .tpName a::after{content:\"↗\";display:inline-block;text-decoration:none;font-size:.62em;margin-left:3px;opacity:.35;vertical-align:.25em}\n#tbTip .tpName a:hover{text-decoration:underline}\n#tbTip .tpName a:hover::after{opacity:1}\n.tpName{display:flex;align-items:center;gap:8px;flex-wrap:wrap}\n.tpName>b{font-size:16px}\n.tpSr{font-size:13px;color:var(--tx2)}\n.tpPill{font-size:12px;font-weight:700;padding:1px 7px;border-radius:999px;margin-left:auto}\n.tpR{background:rgba(255,90,90,.16);color:#ff5a5a}\n.tpB{background:rgba(90,169,255,.16);color:#5aa9ff}\n.tpY{background:rgba(255,200,80,.16);color:#ffc850}\n.tpW{background:rgba(255,255,255,.1);color:var(--tx)}\n.tpK{background:rgba(255,142,198,.16);color:#ff8ec6}\n.tpV{background:rgba(255,142,198,.16);color:#ff8ec6}\n.tpG{background:rgba(76,208,125,.16);color:#4cd07d}\n.tpKv{display:grid;grid-template-columns:auto 1fr;column-gap:12px;row-gap:2px;margin-top:6px;font-size:14px;font-variant-numeric:tabular-nums}\n.tpKv>span:nth-child(odd){color:var(--tx2)}\n.tpKv>span{display:flex;align-items:center;gap:5px;flex-wrap:wrap;min-height:24px;line-height:20px}\n.tbBoard .tbCell .tbCv{padding:6px 10px;margin:-6px -10px}\n.tpTm{display:inline-flex;align-items:center;gap:5px;font-weight:700}\n.tpSrc{color:#7fb2ff;text-decoration:underline;text-underline-offset:2px}\n.tpA{color:inherit;text-decoration:none}\n#tbTip.sheet .tpA{text-decoration:underline;text-decoration-color:rgba(255,255,255,.35);text-underline-offset:3px}\n#tbTip.sheet .tpGo{cursor:pointer;position:relative;padding-right:22px}\n#tbTip.sheet .tpGo::after{content:\"›\";position:absolute;right:8px;top:50%;transform:translateY(-50%);font-size:18px;color:var(--tx2)}\n.trRow.trFlash{outline:2px solid var(--gold);outline-offset:-2px;background:rgba(255,200,80,.14)!important}\n.tpQ{margin-top:6px;padding:6px 8px;border-left:3px solid rgba(255,200,80,.5);background:rgba(255,200,80,.06);border-radius:4px;font-size:14px;line-height:1.55}\n.tpQg{border-left-color:rgba(76,208,125,.55);background:rgba(76,208,125,.06)}\n.tpQb{border-left-color:rgba(90,169,255,.55);background:rgba(90,169,255,.07)}\n.rtPlG{display:grid;grid-template-columns:22px minmax(0,1fr) max-content max-content;column-gap:14px;row-gap:9px;align-items:center}\n.rtPlG .rtChD{text-align:right}\n.rtPv{text-align:right;font-variant-numeric:tabular-nums;font-size:15px;white-space:nowrap}\n.rtPlG .rtIc img{width:22px;height:22px;display:block}\n.rtRsL{font-style:normal;font-weight:400;font-size:12px;color:var(--tx2);margin-left:2px}\n.tpQ>span .tpTm{font-size:12px;vertical-align:middle;line-height:1}\n.tpQ>span .tpTm img{display:block}\n.tpQ>span{display:flex;align-items:center;flex-wrap:wrap;white-space:pre-wrap;font-size:12px;color:var(--tx2);margin-bottom:2px}\n.tpPvC{margin-top:6px}\n.tpPvC .tpName>b{color:var(--tx2)}\n.tpX{background:rgba(255,255,255,.08);color:var(--tx2)}\n.tpPv{margin-top:10px;padding-top:8px;border-top:1px solid rgba(255,255,255,.1)}\n.tpPvR{display:grid;grid-template-columns:auto 1fr auto;column-gap:10px;align-items:center;margin-top:5px;font-size:13px}\n.tpPer{color:var(--tx2);font-variant-numeric:tabular-nums;white-space:nowrap}\n.tpDu{font-size:12px;font-weight:700;padding:1px 7px;border-radius:999px;background:rgba(255,255,255,.08);white-space:nowrap}\n#tbTip:has(.rtBox){max-width:min(520px,94vw);padding:12px 14px}\n#tbTip:has(.rtBox):not(.sheet){width:400px;max-width:94vw;box-sizing:border-box}\n.rtBox{width:auto;max-width:100%}\n.rtHd{display:flex;align-items:center;gap:8px;padding-bottom:10px;margin-bottom:10px;border-bottom:1px solid rgba(255,255,255,.1);white-space:nowrap}\n.rtHd>b:first-of-type{font-size:17px;font-weight:800}\n.rtTt{color:var(--tx2);font-size:13px}\n.rtSum{margin-left:auto;padding-left:20px;font-size:17px;white-space:nowrap;line-height:1;font-weight:800;font-variant-numeric:tabular-nums}\n.rtGrid{display:grid;grid-template-columns:22px minmax(0,1fr) 30px minmax(0,1fr) 66px;column-gap:10px;row-gap:14px;align-items:center}\n.rtGrid>.rtCh{margin-bottom:-6px}\n.rtGrid>.rtXs{margin-top:-8px}\n.rtCh{font-size:13px;color:var(--tx2);line-height:1}\n.rtChD{justify-self:end}\n.rtIc img{width:20px;height:20px;display:block;object-fit:contain}\n.rtP{display:flex;flex-direction:column;line-height:1.3;min-width:0}\n.rtN{font-weight:700;white-space:nowrap;display:flex;align-items:center;gap:6px}\n.rtN .tbN{font-weight:700}\n.rtV{font-size:14px;color:var(--tx2);font-variant-numeric:tabular-nums;white-space:nowrap}\n.rtTop{align-self:start}\n.rtIc.rtTop,.rtAr.rtTop{height:calc(1.3em * 2);display:flex;align-items:center;justify-content:center}\n.rtAr.rtTop{height:36px}\n.rtIc.rtTop{height:36px}\n.rtMulti{grid-column:4/6;display:grid;grid-template-columns:subgrid;row-gap:8px;align-items:center;min-width:0}\n.rtD{white-space:nowrap}\n.rtD i{font-style:normal;display:block;line-height:.7;font-size:12px;opacity:.75}\n.rtSumR{white-space:nowrap}\n.rtMa{grid-column:1/-1;display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin-top:2px;padding-top:3px;border-top:1px solid rgba(255,255,255,.12);font-size:14px;color:var(--tx2);white-space:nowrap}\n.rtMa b{font-weight:800;color:var(--tx);font-variant-numeric:tabular-nums}\n.rtV i{font-style:normal;font-size:11px;opacity:.8;margin-left:0;display:block;white-space:nowrap}\n.rtAr{color:#aab6cc;text-align:center;font-size:20px;line-height:1}\n.rtD{justify-self:end;min-width:58px;text-align:center;padding:3px 8px;border-radius:6px;font-weight:800;font-variant-numeric:tabular-nums;background:rgba(255,255,255,.06)}\n.rtD.tbUp{background:rgba(255,90,90,.15)}\n.rtD.tbDn{background:rgba(63,207,122,.15)}\n.rtXl{grid-column:2/-1;margin-top:-6px;font-size:11px;color:var(--tx2)}\n.rtEmpty{color:var(--tx2)}\n.rtFoot{margin-top:12px;padding-top:8px;border-top:1px solid rgba(255,255,255,.1);font-size:12px;line-height:1.5;color:var(--tx2);white-space:nowrap}\n@container mainc (max-width:999.98px){.tbTeam{padding-right:8px;font-size:13px;gap:5px}\n.tbCell{font-size:13px;padding:6px 3px}\n.tbHd{font-size:14px}\n.tbCell .tbN{white-space:normal;overflow-wrap:anywhere}\n.tbHd img{display:none}}\n.trList{padding:6px 16px 12px;display:grid;grid-template-columns:max-content max-content max-content max-content max-content minmax(0,1fr);column-gap:14px}\n.trHead{grid-column:1/-1;display:grid;grid-template-columns:subgrid;padding:4px 10px 6px;font-size:13px;color:var(--tx2);font-weight:700;border-bottom:1px solid var(--line)}\n.trFlow{display:contents}\n.trFrom,.trTo,.trSpan{display:flex;flex-direction:column;align-items:flex-start;gap:4px;white-space:nowrap}\n.trRow>.trSt{grid-column:1}\n.trRgC{grid-column:2;display:flex;align-items:center;gap:4px;white-space:nowrap}\n.trRgC .trArr{font-size:12px}\n.trRgC .trLg{margin-left:0}\n.trFrom{grid-column:3}\n.trFlow .trArr{grid-column:4}\n.trTo{grid-column:5}\n.trAT{display:contents}\n.trSpan{grid-column:3/6}\n.trRow>.trTx{grid-column:6}\n.trArr{color:var(--tx2);font-size:15px}\n.trList .trFrom,.trList .trTo,.trList .trSpan{align-items:flex-start}\n.trList .trSpan{grid-column:3}\n.trList .trFlow .trArr{justify-self:center;color:var(--gold);opacity:.85}\n.trList .trNone{padding:0}\n.trNone{color:var(--tx2);opacity:.6;padding:0 6px}\n.trLg{font-size:12px;font-weight:800;color:var(--lgc,var(--tx2));margin-left:4px;padding:0 6px;border-radius:999px;border:1px solid color-mix(in srgb,var(--lgc,#888) 55%,transparent)}\n.trLgOnly{font-size:13px;font-weight:700;margin-left:0}\n.trSt{font-size:13px;font-weight:700;padding:1px 9px;border-radius:999px;white-space:nowrap;justify-self:start}\n.trSt-official{color:var(--tx);background:rgba(255,255,255,.1)}\n.trSt-conf{color:#4cd07d;background:rgba(76,208,125,.16)}\n.trSt-fake{color:#ff5a5a;background:rgba(255,90,90,.16)}\nb.trCf{color:#4cd07d}\nb.trFk{color:#ff5a5a}\n.trSt-rumor{color:#ffc850;background:rgba(255,200,80,.16)}\na.trPl{color:inherit;text-decoration:underline dotted rgba(255,255,255,.35);text-underline-offset:3px}\na.trPl:hover{color:#7fb2ff;text-decoration-color:#7fb2ff}\n.trList>.sumEmpty{grid-column:1/-1}\n.trDay{grid-column:1/-1;font-weight:900;color:var(--gold);font-size:18px;margin:18px 0 6px;padding:6px 14px;border-radius:8px;border-left:5px solid var(--gold);background:linear-gradient(90deg,color-mix(in srgb,var(--gold) 18%,transparent),transparent 70%)}\n.trRow{grid-column:1/-1;display:grid;grid-template-columns:subgrid;align-items:center;padding:8px 10px;border-radius:6px;line-height:1.7}\n.trRow:nth-of-type(even){background:rgba(255,255,255,.03)}\n.trRow:hover{background:rgba(255,255,255,.06)}\n.trTeam{display:inline-flex;align-items:center;gap:6px;font-weight:700}\na.trTeam,a.trAb{color:inherit;text-decoration:none}\na.trTeam:hover,a.trAb:hover{color:#7fb2ff}\n.trSrcTag{font-size:13px;padding:1px 8px;border-radius:999px;background:rgba(255,255,255,.08);color:var(--tx2)}\n.trSrcTag{color:#7ab8ff;background:rgba(122,184,255,.12);font-size:11px;font-weight:700;padding:1px 7px}\nimg.trRole{width:20px;height:20px;object-fit:contain;padding:0;margin:0 4px 0 2px;background:none;vertical-align:-4px}\nimg.trCoach{width:20px;height:20px;object-fit:contain;margin:0 4px 0 2px;vertical-align:-4px;background:none;padding:0}\n.trCoachTx{white-space:nowrap;margin-left:4px}\n.trRole{display:inline-block;font-size:12.5px;padding:0 6px;margin:0 4px 0 2px;border-radius:5px;background:rgba(255,200,80,.14);color:#ffc850;vertical-align:1px}\n.trTx{min-width:0;word-break:break-word;display:flex;align-items:center;gap:12px}\n.trTxt{flex:1 1 auto;min-width:0}\n.trLks{flex:0 0 auto;margin-left:auto;display:flex;gap:10px;white-space:nowrap}\n.trLks .trLk{margin-left:0}\n.trLk{font-size:13px;color:#7fb2ff;white-space:nowrap;margin-left:6px}\n.trNb{white-space:nowrap}\n.trLk1{display:none}\n.trNIc{width:1.35em;height:1.35em;object-fit:cover;border-radius:4px;vertical-align:-.3em;display:inline-block}\n.trSW{display:inline-flex;align-items:center;gap:8px;white-space:nowrap;margin-left:auto}\n@container mainc (max-width:999.98px){.trList{grid-template-columns:max-content minmax(0,1fr)}\n.trHead{display:none}\n.trFlow{display:flex;align-items:center;gap:10px;flex-wrap:wrap;grid-column:2;grid-row:1}\n.trFrom,.trTo,.trSpan{flex-direction:row;flex-wrap:wrap;gap:10px}\n.trTx{flex-wrap:wrap}\n.trLks{margin-left:0}\n.trRgC{grid-column:1/-1;grid-row:2}\n.trRow>.trTx{grid-column:1/-1;grid-row:3;margin-top:4px}}\n.ntDoc mark{background:#5a4a12;color:inherit;border-radius:3px}\n.pdDRys .sqLaneBtn{font-size:14px;padding:3px 12px}\n.pdToc .sqLaneBtn{border-left-width:3px;font-size:14px;padding:3px 12px}\n.pdRdR>*{padding:3px 0;font-size:17px;line-height:1.7;white-space:nowrap;font-variant-numeric:tabular-nums}\n.pdRdH>*{font-size:14.5px;color:var(--tx2);border-bottom:1px solid rgba(255,255,255,.08);padding-bottom:5px}\n.pdExt .pdExtSrc a{color:inherit;text-decoration:none}\n.pdExt .pdExtWhy a{color:#8ab4ff;text-decoration:none;white-space:nowrap}\n.pdExt a:hover{text-decoration:underline}\n.sumPool .sumProw>*{display:flex;align-items:center;padding:5px 0;min-width:0}\n.sumPool .sumProw>*:first-child{justify-content:flex-start}\n.sumPool .sumProw>*:last-child{justify-content:flex-end}\n.sumPool .sumPhd>*{padding-bottom:4px;min-width:0}\n.sumPool .sumZeb>*{background:rgba(255,255,255,.04)}\n.sumPool .sumPhd>*{font-size:13px;color:var(--tx2)}\n.segBtn button{border:none;background:transparent;padding:0 12px;cursor:pointer;color:var(--tx2);\n    font:inherit;font-size:15px;border-radius:0;height:100%;white-space:nowrap;box-sizing:border-box;\n    display:inline-flex;align-items:center;justify-content:center;gap:5px}\n.segBtn button+button{border-left:1px solid var(--line)}\n.segBtn button:hover:not(.on){background:rgba(255,255,255,.06)}\n.segBtn button.on{background:rgba(245,185,66,.22);color:var(--gold);font-weight:700}\n.segBtn.sm button{font-size:13.5px;padding:0 10px}\n.card.ovPad30{padding-left:30px;padding-right:30px}\n#axesBox #axAdd,#axesBox #axReset.sqbtn{width:auto;height:26px;padding:0 10px;font-size:14px;line-height:1}\n#axesBox .meta{font-size:16.5px}\n@container mainc (max-width:759.98px){.tbBoard{display:block;padding:2px 4px 10px}\n.tbHd{display:none}\n.tbLg{position:sticky;top:0;z-index:3;margin:12px 0 6px;padding:6px 12px 6px 6px;   background:linear-gradient(90deg,color-mix(in srgb,var(--lgc) 30%,#141926),#141926 75%)}\n.tbLg b{font-size:18px}\n.tbRow{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));align-items:stretch;gap:0;margin:6px 0;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:rgba(255,255,255,.02)}\n.tbRow .tbTeam img{margin-left:calc(0px - var(--lgpad,0px))!important;margin-right:calc(0px - var(--lgpadR,var(--lgpad,0px)))!important}\n.tbRow .tbTeam>span:not(.tbOk){margin-left:8px}\n.tbTeam .tbOk{margin-left:.35em}\n.tbTeam{grid-column:1;border-left:0;padding:7px 10px;gap:0;font-size:16px;background:color-mix(in srgb,var(--lgc) 14%,transparent)}\n.tbCell{display:flex;align-items:flex-start;gap:5px;padding:7px 8px;font-size:14px;line-height:1.35;text-align:left;border-radius:0;border-top:1px solid rgba(255,255,255,.06);border-left:1px solid rgba(255,255,255,.06);min-width:0}\n.tbCell.tbRate{grid-column:2;grid-row:1;align-items:center;justify-content:flex-end;padding:7px 10px;font-size:15px;background:color-mix(in srgb,var(--lgc) 14%,transparent);border:0}\n.tbCell[data-r=\"TOP\"],.tbCell[data-r=\"MID\"],.tbCell[data-r=\"SUP\"],.tbCell[data-r=\"STF\"]{border-left:0}\n.tbCell[data-r=\"STF\"]{grid-column:1/-1}\n.tbCell::before{content:\"\";flex:0 0 15px;width:15px;height:15px;margin-top:2px;background:center/contain no-repeat}\n.tbCell[data-r=\"TOP\"]::before{background-image:url(img/TOP.png)}\n.tbCell[data-r=\"JNG\"]::before{background-image:url(img/JG.png)}\n.tbCell[data-r=\"MID\"]::before{background-image:url(img/MID.png)}\n.tbCell[data-r=\"BOT\"]::before{background-image:url(img/BOT.png)}\n.tbCell[data-r=\"SUP\"]::before{background-image:url(img/SUP.png)}\n.tbCell[data-r=\"HC\"]::before,.tbCell[data-r=\"STF\"]::before,.tbCell[data-r=\"CO\"]::before{background-image:url(img/COACH.png)}\n.tbFA .tbCell[data-r=\"HC\"],.tbFA .tbCell[data-r=\"STF\"]{display:none}\n.tbFA .tbCell.tbFaCo{display:flex}\n.tbFA .tbCell.tbEmpty{display:none}\n.tbRow .tbTeam img.tbFaIc{margin:0!important}\n.tbFA .tbCell:not(.tbRate){grid-column:1/-1;border-left:0}\n.tbRtSz{display:none}\n.tbCell.tbRate::before{content:none}\n.tbCell.tbRate .rtPc{margin-right:calc(0px - var(--rb,.5em))}\n.tbCell.tbRate .tbCv{position:relative;left:var(--rb,0px)}\n.tbCell.tbRate .tbCv{white-space:nowrap;font-size:min(15px,3.55cqw)}\n.tbCell .tbCv{min-width:0;overflow-wrap:anywhere}\n.tbCell .tbN{white-space:nowrap}\n.tbCell:not(.tbRate):hover{background:none}\n.tbCell:not(.tbRate):active{background:rgba(122,184,255,.12)}\n.tbCell.tbRate:hover,.tbCell.tbRate:active{background:color-mix(in srgb,var(--lgc) 14%,transparent);border-radius:0}\n.trBar{gap:6px 6px!important;padding:8px 8px!important;margin-bottom:8px!important}\n.trBar .trFG{border-left:0;padding-left:0;flex:1 1 100%;min-width:0;overflow:visible}\n.trBar .trFG>span:not(.tbLegend){display:grid!important;grid-auto-flow:column;grid-auto-columns:minmax(0,1fr);gap:5px!important;width:100%}\n.trBar:has(.fgSort) .cwrap{order:2;flex:1 1 100%}\n.trBar .trFG.fgSort{order:3;flex:1 1 0;min-width:0}\n.trBar:has(.fgSort)>.sqbtn{order:4!important}\n.trBar:has(.fgSort)>#trShot,.trBar:has(.fgSort)>#trShare{order:5!important}\n.trBar:has(.fgSort)>#trFb{order:6!important}\n.trBar:has(.fgSort)>#trDc{order:7!important}\n.trBar .trFG.fgSt{flex:1 1 100%}\n.trHideM{display:none}\n.trList{display:block!important;padding:2px 6px 10px!important}\n.trDay{position:sticky;top:0;z-index:3;margin:10px 0 4px;padding:5px 12px;font-size:16px;background:linear-gradient(90deg,color-mix(in srgb,var(--gold) 26%,#141926),#141926 75%)}\n.trRow{display:flex!important;flex-wrap:wrap;align-items:center;gap:4px 8px;padding:9px 6px 10px!important;border-radius:0;border-bottom:1px solid rgba(255,255,255,.07);line-height:1.5}\n.trRow>.trSt{order:0}\n.trRgC{order:1;grid-row:auto}\n.trLk1{order:2;display:inline-flex;margin-left:auto}\n.trLk1 .trLk{margin-left:0;font-size:13px}\n.trLks{display:none!important}\n.trFlow{order:3;display:flex!important;align-items:center;gap:6px;flex:1 1 100%;min-width:0;flex-wrap:wrap;grid-column:auto;grid-row:auto}\n.trFlow:has(>.trSpan:empty),.trSpan:empty{display:none!important}\n.trRow{gap:0 8px!important;padding:8px 6px!important;line-height:28px}\n.trRgC{min-height:28px}\n.trLk1{min-height:28px;align-items:center}\n.trLk1 .trLk{position:relative}\n.trLk1 .trLk::after,.trBar .cx::after{content:\"\";position:absolute;inset:-9px -8px}\n.trRow>.trSt,.trRow .trLg{line-height:1.45}\n.trFlow{min-height:28px;gap:0 6px!important}\n.trFrom,.trTo,.trSpan{gap:0 8px!important;min-height:28px;align-items:center}\n.trTeam{display:inline-flex;align-items:center;height:28px;line-height:28px}\n.trFlow.trMany{padding:0!important;gap:0 8px!important;margin:0;background:none}\n.trRow>.trTx{line-height:28px!important;margin-top:0!important}\n.trTx img.trRole,.trTx img.trCoach{width:18px!important;height:18px!important;vertical-align:-4px}\n.trFrom,.trTo,.trSpan{flex-direction:row;flex-wrap:wrap;gap:8px;white-space:normal}\n.trNone{display:none}\n.trTeam{font-size:15px}\n.trFlow,.trFlow.trMany{display:flex!important;flex-wrap:wrap;align-items:center;gap:0 8px!important}\n.trFlow .trFrom{display:contents}\n.trFlow .trAT{display:inline-flex;flex-wrap:wrap;align-items:center;gap:0 8px;max-width:100%;min-width:0;min-height:28px}\n.trFlow .trAT .trTo{display:contents}\n.trRow>.trTx{order:4;flex:1 1 100%;display:block;margin-top:2px;font-size:15px;line-height:1.65;grid-column:auto;grid-row:auto}\n.trTxt{display:inline}\n.trLks{display:inline-flex;float:right;gap:10px;margin:3px 0 0 10px}\n.trLks .trLk{font-size:12px}\n.trBar .sqLaneBtn{min-width:0;padding:6px 2px;font-size:12.5px;text-align:center;justify-content:center;white-space:nowrap;overflow:hidden}\n.tbLegend{display:grid!important;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;width:100%}\n.tbLegend .sqLaneBtn{margin-right:0;flex-direction:row;gap:0;padding:6px 2px;line-height:1.3;font-size:0}\n.tbLegend .sqLaneBtn b{font-size:0}\n.tbLegend .sqLaneBtn b::after{content:attr(data-s);font-size:min(12.5px,3.25cqw)}\n.tbLgSep{font-size:0;margin:0 2px}\n.tbLgSep::after{content:\"·\";font-size:11px;font-weight:900;color:var(--tx2)}\n.tbLegend{display:flex!important;gap:5px}\n.tbLegend .sqLaneBtn{flex:1 1 auto}\n.tbLegend .sqLaneBtn b.tbGone{text-decoration:none}\n.tbLegend .sqLaneBtn b.tbGone::after{text-decoration:line-through}\n.tbLegend .sqLaneBtn b.tbRet{text-decoration:none;background:none}\n.tbLegend .sqLaneBtn b.tbRet::after{display:inline-block;background:linear-gradient(currentColor,currentColor) left 54%/100% 1.5px no-repeat}\n.trBar>label,.trBar .trSW>label,.trBar .trFG>label,.trBar>span[style*=\"flex:1\"]{display:none}\n.trBar .trSW{display:contents}\n.trBar .meta{order:9;flex:1 1 100%;font-size:11px;text-align:right;opacity:.8}\n.trBar .cwrap{flex:1 1 0;min-width:84px}\n.trBar .cwrap input{width:100%!important}\n.trBar .sqbtn{flex:0 0 auto}\n.tbLegend{flex-wrap:wrap}}\n@container mainc (max-width:330px){.trBar .trFG.fgSort,.trBar:not(:has(.fgSort)) .cwrap{flex:1 1 100%!important}\n.trBar>#tsHelp{margin-left:auto}}\n@container mainc (max-width:310px){.trBar .sqLaneBtn[data-mk=\"trRg\"],.trBar .sqLaneBtn[data-mk=\"trSt\"]{font-size:12px!important;letter-spacing:-.3px;padding-left:1px!important;padding-right:1px!important}}\n#tbTip.sheet{pointer-events:auto!important;left:8px!important;right:8px!important;top:auto!important;bottom:8px!important;max-width:none!important;max-height:72vh;overflow:auto;padding:16px 14px 14px;border-radius:14px;box-shadow:0 -6px 30px rgba(0,0,0,.6)}\n#tbTip.sheet .tpBox,#tbTip.sheet .rtBox{min-width:0}\n#tbTip.sheet .rtBox{width:auto}\n#tbTip.sheet .rtGrid{column-gap:8px;grid-template-columns:20px minmax(0,1fr) 24px minmax(0,1fr) max-content}\n#tbTip.sheet .rtAr{font-size:18px}\n@media (max-width:345px){#tbTip.sheet .rtGrid{column-gap:6px;grid-template-columns:18px minmax(0,1fr) 18px minmax(0,1fr) max-content}\n#tbTip.sheet .rtIc img{width:18px;height:18px}\n#tbTip.sheet .rtN,#tbTip.sheet .rtV{font-size:13px}\n#tbTip.sheet .rtD{min-width:0;font-size:12.5px}\n#tbTip.sheet .rtAr{font-size:16px}}\n#tbTip.sheet .rtD{min-width:44px;padding:3px 4px;font-size:min(15px,4.2vw)}\n#tbTip.sheet .rtMulti .tbRum{padding:0 4px}\n#tbTip.sheet .rtSum{font-size:min(17px,4.5vw);padding-left:8px}\n#tbTip.sheet .rtMulti{column-gap:8px}\n#tbTip.sheet{padding-top:0}\n#tbTip.sheet .rtHd{padding-right:44px;min-height:30px;position:sticky;top:0;z-index:2;background:#1b2338;padding-top:14px}\n#tbTip.sheet .tbTipXW{position:sticky;top:0;height:0;z-index:3}\n.tbTipX,.trShX{width:40px;height:40px;padding:0;border:0;border-radius:0;background:url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23e8ecf4' stroke-width='2.6' stroke-linecap='round'%3E%3Cpath d='M5.5 5.5l13 13M18.5 5.5l-13 13'/%3E%3C/svg%3E\") center/22px 22px no-repeat;font-size:0;line-height:0;color:transparent;cursor:pointer;opacity:.86;-webkit-tap-highlight-color:transparent}\n.tbTipX:hover,.trShX:hover{opacity:1}\n.tbTipX{position:absolute;top:6px;right:6px}\n#tbTip.sheet .tbTipX{top:9px;right:-10px}\nhtml.solo #nav,html.solo #lblYear,html.solo #yearSel,html.solo #penBtn,html.solo #meta{display:none!important}\n[data-tshot] .tbCell::before{content:none!important}\n[data-tshot] .trHead,[data-tshot] .tbHd,[data-tshot] .trDay{position:static!important;top:auto!important}\n[data-tshot] .tbBoard>.tbHd,[data-tshot] .trList>.trHead{background:none!important;box-shadow:none!important}";document.head.appendChild(st);})();

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
@media (max-width:400px){.trBar .sqbtn,.trBar #trDc,.trBar #trFb{width:30px!important;height:30px!important;min-width:30px!important;border-radius:9px!important}.trBar .sqbtn svg,.trBar #trFb svg{width:20px;height:20px}.trBar #trDc svg{width:18px;height:18px}}`;
    document.head.appendChild(st); }
  f.insertAdjacentHTML("beforeend",b("tsHelp",IC.help,LANG==="en"?"About this page":"本頁說明")+b("tsReset",IC.reset,LANG==="en"?"Reset filters":"重設篩選"));
  { const sh=document.getElementById("trShot"); if(sh)sh.innerHTML=IC.shot; const sr=document.getElementById("trShare"); if(sr)sr.innerHTML=IC.share; }
  // 電腦版：頁首、篩選列、欄名列往下捲時都留在上方（使用者 2026-11-21「這列以上包括這列 往下滑時都應該維持在上方」）
  //   三層都 sticky，下面兩層的 top＝上面幾層的高度（量出來寫進 CSS 變數；視窗大小變了重量）；篩選列下方的空隙用同色陰影蓋住，列才不會從縫裡露出來
  //   卡片（陣容表／消息表）在電腦版改成單色 #161c2b（原本是 #161c2b→#121722 的直向漸層）：欄名列黏在上方時底色是固定的一個顏色，
  //   卡片卻越往下越深 ⇒ 捲到下面時欄名列比左右兩側的卡片內距亮 5～8 階，像貼了一塊色塊（使用者 2026-11-21「電腦版的這列 背景色怪怪的」；頂端對了、捲下去還是錯）。
  //   欄名列的底色不要加 !important：截圖複本靠行內 background:none 把它變透明，加了會在截圖上畫出色塊
  if(!document.getElementById("tsStickCss")){ const st=document.createElement("style"); st.id="tsStickCss";
    st.textContent=`@media (min-width:760px){#tsHdr{position:sticky;top:0;z-index:40;background:#0b0e14}
#tsCover{display:block;position:fixed;left:0;right:0;top:0;height:calc(var(--tsH1,0px) + var(--tsG1,0px) + var(--tsH2,0px) + var(--tsG0,0px));background:#0b0e14;z-index:37;pointer-events:none}
.filters.trBar{position:sticky;top:calc(var(--tsH1,0px) + var(--tsG1,0px));z-index:39}
.card.tbBoard,.card.trList{background:#161c2b}
.tbBoard>.tbHd{top:calc(var(--tsH1,0px) + var(--tsG1,0px) + var(--tsH2,0px) + var(--tsG,0px))!important;z-index:38!important;background:var(--tsCB,#161c2b);box-shadow:0 calc(var(--tsG0,0px) - var(--tsG,0px)) 0 0 var(--tsCB,#161c2b)}
.trList>.trHead{position:sticky;top:calc(var(--tsH1,0px) + var(--tsG1,0px) + var(--tsH2,0px) + var(--tsG,0px));z-index:38;background:var(--tsCB,#161c2b);box-shadow:0 calc(var(--tsG0,0px) - var(--tsG,0px)) 0 0 var(--tsCB,#161c2b)}}
#tsCap{position:fixed;height:14px;overflow:hidden;z-index:37;pointer-events:none}#tsCap>i{position:absolute;left:0;right:0;top:0;height:60px;box-sizing:border-box;box-shadow:0 0 0 40px #0b0e14}
@media (max-width:759.98px){#tsCover,#tsCap{display:none}}`;
    document.head.appendChild(st);
    window._tsStick=()=>{ const hd=document.getElementById("tsHdr"), bar=document.querySelector(".filters.trBar"), bd=document.querySelector(".tbBoard,.trList"), R=document.documentElement.style; if(!hd||!bar)return;
      const sy=scrollY; R.setProperty("--tsH1",hd.offsetHeight+"px"); R.setProperty("--tsH2",bar.offsetHeight+"px");
      // 捲動後三層之間的空隙要跟頁面最上面時一模一樣（使用者 2026-11-21「往下滑的時候 上方還是有小部分的縮起」：原本頁首與篩選列之間 14px、篩選列與欄名列之間 7px 會被吃掉）
      //   ⇒ 在最上面時量兩段空隙（頁首→篩選列、篩選列→欄名列），sticky 的 top 把空隙算進去，空隙用同色陰影蓋住
      if(sy<4){ const hh=document.querySelector(".tbBoard>.tbHd,.trList>.trHead")||bd; R.setProperty("--tsG1",Math.max(0,Math.round(bar.getBoundingClientRect().top-hd.getBoundingClientRect().bottom))+"px");
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
    d.style.cssText="position:fixed;z-index:10000;background:#1b2338;border:1px solid rgba(255,255,255,.14);box-shadow:0 8px 30px rgba(0,0,0,.6);color:#e8ecf4;line-height:1.75;font-size:14.5px;white-space:pre-line;overflow:auto;"
      +(mob?"left:8px;right:8px;bottom:8px;max-height:72vh;padding:0 14px 14px;border-radius:14px":"right:16px;top:64px;width:min(560px,92vw);max-height:80vh;padding:0 18px 16px;border-radius:10px");
    // 最上面一條標題列黏在頂端、X 放在它的右端：說明很長要捲動時 X 不會跟著捲走（原本 X 是絕對定位在內容裡，一捲就不見；
    //   使用者 2026-11-21「所有小框的X位置不要跑掉 然後大一點 然後背景不要用圓形底色 直接X就好」）。X 的長相跟格子小框共用 .tbTipX
    d.innerHTML=`<div class="tsHpHd"><b>${LANG==="en"?"About this page":"本頁說明"}</b><button class="tbTipX" aria-label="close">✕</button></div>`+((LANG==="en"?HELP.en:HELP.zh)||"");
    document.body.appendChild(d); d.querySelector(".tbTipX").onclick=()=>d.remove(); };
  if(!window._tsHelpOut){ window._tsHelpOut=1; document.addEventListener("click",e=>{ const d=document.getElementById("tsHelpBox"); if(d&&!e.target.closest("#tsHelpBox")&&!e.target.closest("#tsHelp"))d.remove(); }); }
  document.getElementById("tsReset").onclick=()=>{ Object.assign(V,{trSrc:"",trSt:"",trRg:"",trKd:"",trQ:"",tbF:"",tbSort:""}); saveState(); render(); }; }
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
    const SRCN={sheep:"SE",ptt:"PTT",kr:en2?"Korean media":"韓網",man:en2?"Announcement":"公告"};   // 來源的「官方」跟狀態的「官方」同名會混淆 ⇒ 來源叫官方公告
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
      const noRs=/不[^，。；]{0,45}續約|不續約|不會留|不留/.test(zh);   // 「決定不和 Wunder 續約」是離隊傳聞，不是續約傳聞（原本被當成續約 ⇒ 官方離隊後也對不上，一直停在傳聞）
      if(!noRs&&/續約|留在|留隊/.test(zh)&&tg.length===1&&ns.length)return verdict([],ns.map(n=>[n,tg[0][1]]));
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
      // ③ 退役與離隊併成一則（使用者 2026-11-21「退役選手退役與離隊的消息要合併」）：官方退役消息（id＝ret-…）講到的人——
      //   wiki 的離隊句把他拿掉（那句只有他就整句不列）；Sheep 官方也報了他退役 ⇒ 留 Sheep 那則（有前因後果），官方那則不重複列；
      //   否則官方那則改寫成「離隊並宣布退役」。要排在 ② 前面：先把人從 wiki 的離隊名單拿掉，② 才不會把 Sheep 的退役消息當成那則離隊的重複
      const gone3=new Set();
      { const reE=n=>String(n).replace(/[.*+?^${}()|[\]\\]/g,"\\$&"), plain=t=>String(t||"").replace(/§[A-Z]+§/g,"").replace(/‹[^|›]+\|([^›]+)›/g,"$1");
        L.filter(r=>/^ret-/.test(String(r.id||""))).forEach(r=>{ const mm=/‹[^|›]+\|([^›]+)›/.exec(r.zh||""); if(!mm)return; const nm=mm[1], tm=((r.tags||[]).find(t=>t[2]==="out")||[])[1]||"";
          const hit=new RegExp("(?<![A-Za-z0-9])"+reE(nm)+"(?![A-Za-z0-9])"), one="(?:§[A-Z]+§)?‹[^|›]+\\|"+reE(nm)+"›(?:\\s*[（(][^（）()]*[）)])?", oneRe=new RegExp(one), oneAll=new RegExp("^"+one+"$");
          let merged=false;
          L.forEach(w=>{ if(w.s!=="wiki"||!/leave|both/.test(w.kind||"")||(tm&&!sameTm(w.team,tm))||!hit.test(plain(w.zh)))return;
            // 中文「A、B、C 離隊。」／英文「A, B, and C leave.」「A leaves.」——逐句處理，只動離隊那句
            const zh=String(w.zh||"").split(/(?<=。)\s*/).map(z=>{ const m2=/^(.*?)(\s*離隊。)$/.exec(z); if(!m2||!oneRe.test(z))return z;
                const it=m2[1].split("、").filter(i=>!oneAll.test(i.trim())); merged=true; return it.length?it.join("、")+m2[2]:""; }).filter(Boolean).join(" ");
            const en=String(w.en||"").split(/(?<=\.)\s+/).map(z=>{ const m2=/^(.*?)\s+leaves?\.$/.exec(z); if(!m2||!oneRe.test(z))return z;
                const it=m2[1].split(/,\s*(?:and\s+)?|\s+and\s+/).map(i=>i.trim()).filter(i=>i&&!oneAll.test(i)); if(!it.length)return "";
                return (it.length===1?it[0]+" leaves":it.length===2?it.join(" and ")+" leave":it.slice(0,-1).join(", ")+", and "+it[it.length-1]+" leave")+"."; }).filter(Boolean).join(" ");
            w.zh=zh; w.en=en; if(!String(zh||en).trim())gone3.add(w); });
          const sh=L.find(y=>y.s==="sheep"&&y!==r&&(y.st||"rumor")==="official"&&/退役|retire/i.test((y.zh||"")+(y.en||""))&&hit.test(plain(y.zh)+" "+plain(y.en))&&dd2(y.d,r.d)<=7);
          if(sh){ gone3.add(r); return; }
          if(merged){ const who=((/^§[A-Z]+§/.exec(r.zh||"")||[""])[0])+mm[0]; r.zh=who+" 離隊並宣布退役。"; r.en=who+" leaves and announces retirement."; } }); }
      const L2=L.filter(x=>!gone3.has(x));
      const W=L2.filter(x=>x.s==="wiki"), S=L2.filter(x=>x.s==="sheep"&&(x.st||"rumor")==="official"), drop=new Set();
      W.forEach(w=>{ const wn=namesOf(w); if(!wn.length)return;
        S.forEach(sh=>{ if(drop.has(sh)||drop.has(w)||dd2(w.d,sh.d)>3)return; const tg=sh.tags.find(t=>t[1]===w.team); if(!tg)return;
          if(tg[2]&&((w.kind==="join"&&tg[2]!=="in")||(w.kind==="leave"&&tg[2]!=="out")))return;
          const sn=namesOf(sh); if(!sn.length)return; const ov=wn.filter(n=>sn.includes(n)).length;
          if(ov/Math.min(wn.length,sn.length)<0.75)return; drop.add(wn.length>sn.length?sh:w); }); });
      return L2.filter(x=>!drop.has(x)); })();
    const RGS=[...new Set(all.flatMap(x=>x.s!=="wiki"?x.tags.map(t=>t[0]):[x.rg]).filter(Boolean))].sort((a,b)=>Object.keys(RG_LG).indexOf(a)-Object.keys(RG_LG).indexOf(b));
    const KD={join:en2?"Join":"加入",leave:en2?"Leave":"離隊",other:en2?"Other":"其他"};
    const q=(V.trQ||"").trim().toLowerCase();
    // 戰隊一律顯示縮寫（使用者 2026-11-19「戰隊全部改成縮寫」）：左欄＋內文都換，滑過看全名；沒有縮寫的（tAb 回全名）照舊
    // 自由人那一列的名稱＝地區＋自由人（使用者 2026-11-20「自由人改寫成 地區+自由人 例如亞太自由人」）
    const FARG=en2?{LCK:"Korea",LPL:"China",LEC:"EMEA",LCS:"NA",CBLOL:"Brazil",LCP:"APAC"}:{LCK:"韓國",LPL:"中國",LEC:"歐洲",LCS:"北美",CBLOL:"巴西",LCP:"亞太"};
    const rowNm=t=>t.fa?"FA":abOf(t.nm);   // 中英文統一寫「聯賽 FA」（使用者 2026-11-21「自由人統一改成FA」）
    const abOf=n=>{ if(n==="FA")return "FA";
      if(/^Kiwoom DRX$/i.test(String(n||"")))return "KRX";   // 使用者 2026-11-19「DRX 前陣子就改成 KRX 了」：只改這頁的顯示（全站 teamFix 把 KRX 收斂成 DRX 當比對鍵，不能動）
      const a=teamFix(String(tAb(n)||"")); return a||n; };
    // 內文提到的隊伍一律寫縮寫（使用者 2026-11-21「消息提到的隊伍 都改寫成縮寫」）：除了這批消息標到的隊，陣容表全部隊伍（含改名前的舊名）也算
    const TN=new Map([...new Set([...all.flatMap(x=>x.s!=="wiki"?x.tags.map(t=>t[1]):[x.team]),...(D.board||[]).filter(t=>!t.fa).flatMap(t=>[t.nm,t.tm,t.was]),...(D.board||[]).flatMap(t=>Object.values(t.r||{}).flat().flatMap(e=>[e.from,(e.ro||{}).to,...(e.ros||[]).map(o=>o.to)]))].filter(Boolean))].map(n=>[n,abOf(n)]).filter(([n,a])=>a!==n));
    [["Vitality","Team Vitality"],["Heretics","Team Heretics"],["Shopify","Shopify Rebellion"],["Liquid","Team Liquid"]].forEach(([s,f])=>{ const a=abOf(f); if(a&&a!==f&&!TN.has(s))TN.set(s,a); });   // 內文常見的簡稱；大小寫不同的（Dplus KIA）靠下面的 i 旗標
    const TNL=new Map([...TN].map(([n,a])=>[n.toLowerCase(),a]));
    const TNRE=TN.size?new RegExp("(?<![A-Za-z0-9])("+[...TN.keys()].sort((a,b)=>b.length-a.length).map(n=>esc(n).replace(/[.*+?^${}()|[\]\\]/g,"\\$&")).join("|")+")(?![A-Za-z0-9])","gi"):null;
    const TNE={get:n=>TNL.get(String(n).replace(/&amp;/g,"&").replace(/&#39;/g,"'").toLowerCase())};
    // 戰隊一律連到 WIKI 戰隊頁（使用者 2026-11-20「消息 有些戰隊沒有超連結」）：原隊／新隊的隊徽、內文裡的全名與縮寫（GEN、KRX…）都連
    const tmWk=n=>"https://lol.fandom.com/wiki/"+encodeURIComponent(String(n).replace(/ /g,"_"));
    const ABM=new Map(); [...TN].forEach(([n,a])=>{ if(a&&a.length>=2&&!ABM.has(a))ABM.set(a,n); });
    ((window.TRANSFERS||{}).board||[]).forEach(t=>{ const a=abOf(t.nm); if(a&&a.length>=2&&!ABM.has(a))ABM.set(a,t.nm); });   // 全名就是縮寫的隊（T1、LYON、LOUD）TN 裡沒有
    const ABRE=ABM.size?new RegExp("(?<![A-Za-z0-9])("+[...ABM.keys()].sort((a,b)=>b.length-a.length).map(n=>esc(n).replace(/[.*+?^${}()|[\]\\]/g,"\\$&")).join("|")+")(?![A-Za-z0-9])","g"):null;
    const ST={official:en2?"Official":"官方",rumor:en2?"Rumor":"傳聞",conf:en2?"Confirmed":"證實",fake:en2?"Debunked":"謠言"};
    const stOf=x=>x.s==="wiki"?"official":x._v==="fake"?"fake":x._v==="conf"?"conf":(x.st||"rumor");
    // 篩選可複選（使用者 2026-11-20「篩選列的全部拿掉，然後篩選列要可以複選」）：每個鍵存逗號分隔的字串，沒選＝全部
    const mset=k=>new Set(String(V[k]||"").split(",").filter(Boolean));
    V.trSrc="";   // 來源篩選已刪：舊存檔留下的值不可以再生效
    const F_SRC=mset("trSrc"), F_ST=mset("trSt"), F_RG=mset("trRg"), F_KD=new Set();   /* 類型篩選已刪：舊存檔留下的值不可以再生效 */
    const kdOk=x=>(F_KD.has("join")&&/join|both/.test(x.kind))||(F_KD.has("leave")&&/leave|both/.test(x.kind))||(F_KD.has("other")&&x.kind==="other");
    // 來源的 WIKI 併進「公告」（使用者 2026-11-20「WIKI 跟公告的按鈕合併 改稱 公告 就好 因為 WIKI 一定有附上公告消息」）；舊存檔選過 wiki 的也當成公告
    const shown=all.filter(x=>(!F_SRC.size||F_SRC.has(x.s==="wiki"?"man":x.s))&&(!F_ST.size||F_ST.has(stOf(x)))&&(!F_RG.size||(x.s!=="wiki"?x.tags.some(t=>F_RG.has(t[0])):F_RG.has(x.rg)))
      &&(!F_KD.size||kdOk(x))
      &&(!q||[x.team,x.en,x.zh].join(" ").replace(/‹[^|›]+\|([^›]+)›/g,"$1").toLowerCase().includes(q))).sort((a,b)=>a.d<b.d?1:a.d>b.d?-1:(b.n||0)-(a.n||0));
    // 狀態欄（使用者 2026-11-19「新增一欄在第二欄 說明是Rumor還是官方消息」）：wiki＝官方；Sheep 依 st（抓取端標），內文開頭的【官方】／[SOURCES] 前綴拿掉
    // 教練圖示放在 ID 前面（跟路線圖一樣；使用者 2026-11-19「為何教練的圖是在教練ID後面」）：
    //   「名字（總教練）」→ ⟦C:職稱⟧名字⟦R:職稱⟧；純「教練」只留圖示，其他職稱文字留在名字後面
    const CO=/(‹[^|›]+\|[^›]+›|[A-Za-z0-9][A-Za-z0-9_.'\-]*)\s*(?:（([^（）]*(?:教練|分析師)[^（）]*)）|\(([^()]*(?:[Cc]oach|[Aa]nalyst)[^()]*)\))/g;   // 分析師也算教練團：名字前放同一顆後勤圖示、職稱不另外寫（使用者 2026-11-21）
    // 推文原文清理（2026-11-19 分頁審視）：國旗 emoji 在 Windows 會畫成 KR／MX 字母方塊 ⇒ 拿掉；#LCK 的 # 拿掉；連空行壓成一行；網址改成「文章」連結
    const clean=s=>s.replace(/[ \t]?[\u{1F1E6}-\u{1F1FF}]{2}/gu,"").replace(/^[ \t]+/gm,"").replace(/(^|\s)#(\w)/g,"$1$2").replace(/[ \t]*\n\s*\n\s*/g,"\n").trim().split("\n").map(z=>z.trim()).filter(z=>z&&!/^❓[\s?？]*$/.test(z)).reduce((o,b,i,L)=>{ if(!i)return b;   // 排版照中文版：整則接成一段、名單用 / 隔開，不逐行列（使用者 2026-11-21「排版都要遵照中文版面」）
      const it=z=>{ const p=z.replace(/§\w+§/g,"").replace(/‹[^|›]+\|([^›]+)›/g,"$1"); return p.length<=40&&!/[.!?。:：]$/.test(p)&&!/https?:/.test(p); }, a=L[i-1];
      return o+(it(b)&&it(a)&&i>1?" / ":/[.!?:：。！？]$/.test(a)?" ":it(b)&&!it(a)?": ":". ")+b; },"");
    // 選手名冊（陣容表格子＋上一位＋wiki／Sheep 的 ‹頁|名›）⇒ 名字 → {頁, 路線}；內文沒標的名字自動補路線圖示與 wiki 連結
    //   （使用者 2026-11-20「消息頁面很多選手沒有標註路線圖」「很多選手沒有標記超連結」）。比對分大小寫、前後不能接英數字
    const pn0=s=>String(s||"").replace(/\s*\([^()]*\)\s*$/,"");   // 同陣容表的 pn（那個定義在後面，這裡先用不到它）
    const PLM=new Map(), addPl=(n,p,l)=>{ n=String(n||"").trim(); if(n.length<2)return; try{ p=decodeURIComponent(String(p||"")); }catch(_){} const o=PLM.get(n)||{}; PLM.set(n,{p:o.p||p||"",l:o.l||l||""}); };
    (D.board||[]).forEach(t=>{ Object.entries(t.r||{}).forEach(([r,L])=>L.forEach(e=>{ addPl(pn0(e.n),e.p,r); if(e.a)addPl(pn0(e.a),e.p,r); }));   // a＝報導原本的寫法（資料端已把 n 統一成 wiki 的大小寫），內文裡的舊寫法靠它認人
      Object.entries(t.prev||{}).forEach(([r,L])=>L.forEach(p=>{ const o=typeof p==="string"?{n:p}:p; addPl(pn0(o.n),o.n,r); })); });
    [...(D.wiki||[]),...(D.sheep||[])].forEach(x=>((x.en||"")+" "+(x.zh||"")).replace(/(?:§(TOP|JNG|MID|BOT|SUP|COACH)§)?‹([^|›]+)\|([^›]+)›/g,(m,l,p,d)=>{ let pg=p; try{pg=decodeURIComponent(p);}catch(e){} addPl(d,pg.replace(/_/g," "),l||""); return m; }));
    // 陣容表沒有的人（二隊、退役、教練）：排程向 Leaguepedia 查好的位置（transfers.js 的 roles；使用者 2026-11-20 Cracker／Nuguri／Roach）
    // 跟隊伍縮寫／隊名同字的不算人名（NAVI 被當成中路選手，使用者 2026-11-20 檢視時發現）
    const TMW=new Set([...BTM.flatMap(b=>b.al),...TN.keys(),...TN.values()].map(z=>String(z).toLowerCase()));
    Object.entries(D.roles||{}).forEach(([n,v])=>{ if(!TMW.has(n.toLowerCase()))addPl(n,v[1],v[0]); });
    // 名字的大小寫統一成 wiki 的寫法（使用者 2026-11-21「選手ID的大小寫統一 像是HOYA就有兩種寫法 統一成WIKI的寫法」）：
    //   陣容表的名字資料端已經換好；消息內文是照報導寫的（Hoya／HOYA）⇒ 畫連結文字時用「頁名 → wiki 的 ID」對照表換掉，只在兩者只差大小寫時才換
    //   CID 來源＝陣容表每個人的（頁名, 名字）＋ roles 第三格（排程向 Leaguepedia 查到的 Players.ID）
    const CID=new Map(), pgK=p=>{ let z=String(p||""); try{ z=decodeURIComponent(z); }catch(_){} return z.replace(/_/g," ").trim().toLowerCase(); };
    (D.board||[]).forEach(t=>Object.values(t.r||{}).forEach(L=>L.forEach(e=>{ if(e.p)CID.set(pgK(e.p),pn0(e.n)); })));
    Object.values(D.roles||{}).forEach(v=>{ if(v&&v[1]&&v[2]&&!CID.has(pgK(v[1])))CID.set(pgK(v[1]),v[2]); });
    const cidOf=(p,d)=>{ const c=CID.get(pgK(p)); return c&&c.toLowerCase()===String(d).toLowerCase()?c:d; };
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
    const txt=x=>{ let t=esc(clean(autoPl(((en2?(x.en||x.zh):(x.zh||x.en))||"").replace(/^\s*(【[^】]{1,4}】|\[[A-Z]+\])\s*/,""))).replace(CO,(m,n,a,b)=>`⟦C:${a||b}⟧${n}⟦R:${a||b}⟧`))
        .replace(/https?:\/\/[^\s<]+/g,u=>`<a class="trPl" href="${u}" target="_blank" rel="noopener">${en2?"Article":"文章"}</a>`)
        .replace(/§COACH§/g,()=>`<img class="trCoach" src="img/COACH.png" alt="${en2?"Coach":"教練"}" title="${en2?"Coach":"教練"}">`).replace(/‹([^|›]+)\|([^›]+)›/g,(m,p,d)=>`<a class="trPl" href="https://lol.fandom.com/wiki/${p}" target="_blank" rel="noopener">${cidOf(p,d)}</a>`).replace(/§(TOP|JNG|MID|BOT|SUP)§/g,(m,r)=>POS_IMG[r]?`<img class="trRole" src="${POS_IMG[r]}" alt="${RL[r]}" title="${RL[r]}">`:`<span class="trRole">${RL[r]}</span>`)
        .replace(/⟦C:([^⟧]*)⟧/g,(m,r)=>`<img class="trCoach" src="img/COACH.png" alt="${r}" title="${r}">`)
        .replace(/⟦R:([^⟧]*)⟧/g,(m,r)=>/→|->| to /.test(r)?`<span class="trCoachTx">${r}</span>`:"").replace(/(?:主教練|助理教練|代理主教練|教練)\s*(?=(?:<[^>]+>)*<img class="trCoach")/g,"").replace(/\n/g,"<br>");   // 職稱不寫（滑過哨子圖看得到；使用者 2026-11-20「戰術教練 Sephis 戰術教練 離隊，寫離隊就好」），只留職稱異動
      if(TNRE)t=t.replace(/(^|>)([^<]+)/g,(m,a,b)=>a+b.replace(TNRE,n=>`<a class="trAb" href="${tmWk(n.replace(/&amp;/g,"&"))}" target="_blank" rel="noopener" title="${n}">${esc(TNE.get(n)||n)}</a>`));
      if(ABRE)t=t.split(/(<a [^>]*>[^<]*<\/a>)/).map((seg,i)=>i%2?seg:seg.replace(/(^|>)([^<]+)/g,(m,a,b)=>a+b.replace(ABRE,n=>`<a class="trAb" href="${tmWk(ABM.get(n.replace(/&amp;/g,"&"))||n)}" target="_blank" rel="noopener" title="${esc(ABM.get(n)||n)}">${n}</a>`))).join("");   // 既有連結（選手、已換成縮寫的全名）裡面不再套
      // 中英混排補半形空格（使用者 2026-11-20「消息的文字要尊重像改版資訊的排版，英文後面如果是中文要空格」）：
      //   中文字 ↔ 英文／數字之間補一格，中間隔著標籤（連結、圖示、隊名縮寫）也算；緊鄰標點不補
      // 括號、斜線同改版資訊（使用者 2026-11-20「括號跟斜線也要遵守」）：有中文的那則 ⇒ 半形 ( ) / 換全形（）／、前後不留空格；數字之間的 / 不動
      if(!en2&&/[㐀-鿿]/.test(t.replace(/<[^>]+>/g,"")))
        t=t.replace(/(^|>)([^<]+)/g,(m,a,b)=>a+b.replace(/\s*\(\s*/g,"（").replace(/\s*\)\s*/g,"）").replace(/\s*（\s*/g,"（").replace(/\s*）\s*/g,"）").replace(/(?<!\d)\s*\/\s*(?!\d)/g,"／").replace(/\s*／\s*/g,"／"));
      { const CJ="[㐀-䶿一-鿿]", TG="((?:<[^>]+>)*)";
        t=t.replace(new RegExp("("+CJ+")"+TG+"([A-Za-z0-9])","g"),"$1 $2$3").replace(new RegExp("([A-Za-z0-9%])"+TG+"("+CJ+")","g"),"$1$2 $3"); }
      // 路線／教練圖示跟後面的名字綁在一起，不可在中間換行（手機上圖示留在行尾、名字掉到下一行）
      t=t.replace(/(<img class="tr(?:Role|Coach)"[^>]*>)\s*(<a class="trPl"[^>]*>[^<]*<\/a>)/g,'<span class="trNb">$1$2</span>');
      if(q){ const re=new RegExp("("+q.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")+")","gi"); t=t.replace(/(^|>)([^<]+)/g,(m,a,b)=>a+b.replace(re,"<mark>$1</mark>")); } return t; };
    const btns=(key,opts)=>`<span style="display:inline-flex;gap:6px;flex-wrap:wrap">${opts.map(([v,l])=>`<button class="sqLaneBtn${(V[key]||"")===v?" on":""}" data-k="${key}" data-v="${esc(v)}">${l}</button>`).join("")}</span>`;
    // ── 版面（使用者 2026-11-19「重新調整這邊的UI 感覺不直觀」）：每列固定「狀態｜原隊 → 新隊｜消息」＋欄標題。
    //   方向用位置表達：加入＝隊在「新隊」、離隊＝隊在「原隊」、另一邊 –；A→B 兩邊都有；續約／動態這類沒有方向的橫跨兩欄、不畫箭頭。
    //   賽區改成隊名旁的小灰字（不再一列塞一排膠囊）；來源連結接在內文尾。
    // 賽區獨立一欄（使用者 2026-11-20「新增一欄在第二欄叫做賽區，後面隊伍就不用每個都標註賽區，跨賽區就標註兩個」）
    const team=(rg,tm)=>tm?`<a class="trTeam" href="${tmWk(tm)}" target="_blank" rel="noopener" title="${esc(tm)}">${teamLogoHTML(tAb(tm),22,true,tm)||""}${esc(abOf(tm))}</a>`:"";
    const lgPill=rg=>`<span class="trLg" style="--lgc:${LGC[rgNm(rg)]||"var(--tx2)"}">${esc(rgNm(rg))}</span>`;
    const rgCol=x=>{ const pl=l=>`<span class="trLg" style="--lgc:${LGC[l]||"var(--tx2)"}">${esc(l)}</span>`, uq=a=>[...new Set(a.filter(Boolean).map(rgNm))];
      if(x.s==="wiki")return uq([x.rg]).map(pl).join("");
      const o=uq(x.tags.filter(t=>t[2]==="out").map(t=>t[0])), i=uq(x.tags.filter(t=>t[2]==="in").map(t=>t[0]));
      // 箭頭只在「原隊的賽區」跟「新隊的賽區」完全不同時才畫（LEC ➜ LCS）；有重疊（JDG 五選二：LPL＋LCK 的人去 LPL）就只並列
      if(o.length&&i.length&&!o.some(l=>i.includes(l)))return o.map(pl).join("")+`<span class="trArr">➜</span>`+i.map(pl).join("");
      return uq(x.tags.map(t=>t[0])).map(pl).join(""); };
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
      const g=k&&groups.find(g=>fam(g)===fam(x)&&stOf(g)===stOf(x)&&g._k===k&&(x.s==="wiki"?(g.d.slice(0,10)===x.d.slice(0,10)&&(g.src||"")===(x.src||"")):Math.abs(tsOf(g._last)-tsOf(x))<=2*3600e3));   // 官方公告：同一天也要是同一則公告（同一個來源連結）才併；兩則不同的貼文分兩列（使用者 2026-11-21 NS 的續約與 bon0 加入）
      // 同一則合併裡，同一個人去同一隊的只留一行（使用者 2026-11-20 KRX Lucid 兩篇）
      if(g&&x._sig&&x._sig.length&&g._items.some(i=>i._sig&&x._sig.every(z=>i._sig.includes(z)))){ g._last=x; return; }
      if(g){ g._items.push(x); g._last=x; if(x.tags)g.tags=[...new Map([...(g.tags||[]),...x.tags].map(t=>[t[1]+"|"+(t[2]||""),t])).values()];
        if(g.kind!==x.kind)g.kind=/join|both/.test(g.kind)&&/leave|both/.test(x.kind)||/leave|both/.test(g.kind)&&/join|both/.test(x.kind)?"both":g.kind; return; }
      groups.push({...x,_k:k,_items:[x],_last:x}); });
    const lkA=(u,l,ti)=>` <a class="trLk" href="${esc(u)}" target="_blank" rel="noopener" title="${esc(ti||"")}">${l} ↗</a>`;
    // 韓網：連結標韓網原文（使用者要求），另附 PTT 轉貼
    const lkOf=x=>{ const link=x.s==="wiki"?x.src:x.url;
      // 來源連結照網域寫名字（使用者 2026-11-20「來源 ↗ 如果是 X 要寫 X ↗」）
      const dom=u=>/Sheep_?Esports|sheepesports\.com/i.test(u)?"SE":/(^|\/\/)(www\.)?(x|twitter)\.com\//.test(u)?"X":/facebook\.com|fb\.com/.test(u)?"FB":/instagram\.com/.test(u)?"IG":/weibo\.(com|cn)/.test(u)?(en2?"Weibo":"微博"):/youtube\.com|youtu\.be/.test(u)?"YT":/ptt\.cc/.test(u)?"PTT":(en2?"Source":"來源");
      return (link?lkA(link,x.s==="kr"?SRCN.kr:dom(link),x.srcNm):"")+(x.s==="kr"&&x.ptt?lkA(x.ptt,"PTT"):""); };
    let lastD="", rows="";
    groups.forEach(x=>{ const d=x.d.slice(0,10);
      if(d!==lastD){ rows+=`<div class="trDay">${+d.slice(5,7)}/${+d.slice(8,10)}</div>`; lastD=d; }
      const f=flowOf(x);
      const flow=f.span!=null?`<div class="trSpan">${f.span}</div>`
        :`<div class="trFrom">${f.from}</div><span class="trAT"><span class="trArr">➜</span><div class="trTo">${f.to}</div></span>`;
      const nTm=x.s==="wiki"?1:new Set((x.tags||[]).map(t=>t[1]).filter(Boolean)).size;   // 隊伍很多（≥4）⇒ 手機版原隊一行、➜ 新隊另一行
      const seen=new Set(), lk=x._items.map(lkOf).filter(h=>h&&!seen.has(h)&&seen.add(h)).join("");
      const body=x._items.map(i=>txt(i)).join("<br>");
      rows+=`<div class="trRow" data-d="${d}"><span class="trSt trSt-${stOf(x)}">${ST[stOf(x)]}</span><span class="trRgC">${rgCol(x)}</span><span class="trLk1">${(/<a [^>]*>[^<]*<\/a>/.exec(lk)||[""])[0]}</span><div class="trFlow${nTm>=4?" trMany":""}">${flow}</div><div class="trTx"><span class="trTxt">${body}</span>${lk?`<span class="trLks">${lk}</span>`:""}</div></div>`; });
    const head=rows?`<div class="trHead"><span>${en2?"Status":"狀態"}</span><span>${en2?"League":"賽區"}</span><span>${en2?"From":"原隊"}</span><span></span><span>${en2?"To":"新隊"}</span><span>${en2?"News":"消息"}</span></div>`:"";
    // ── 陣容表（使用者 2026-11-19：參考巴哈 LCK 陣容圖「左邊是戰隊 六大聯賽一路往下列」「傳聞就在ID前面打一個星號」
    //    「滑鼠移到那格顯示簽約到何時、上一位選手、新加入的選手原先來自哪個戰隊」）。資料＝transfers.js 的 board（scripts/transfers_board.py）
    const MODE=V.trMode||"board";
    const BL=["TOP","JNG","MID","BOT","SUP","COACH"], BLN={TOP:RL.TOP,JNG:RL.JNG,MID:RL.MID,BOT:RL.BOT,SUP:RL.SUP,COACH:en2?"Coach":"教練",HC:en2?"Head Coach":"主教練",STF:en2?"Staff":"後勤",CO:en2?"Coaches":"教練"};   // CO＝手機 FA 卡把主教練與後勤併成一格用的假欄位（見 colE）
    // 教練分兩欄（使用者 2026-11-19「教練分成兩欄 主教練 跟後勤」）：HC＝主教練、STF＝其他教練／分析師；資料仍是 COACH 一格，顯示時依 sr 拆
    const COLS=["TOP","JNG","MID","BOT","SUP","HC","STF"], isHC=e=>(e&&e.sr)==="HC";
    // 自由人那一列：教練與分析師全部放在同一格（主教練那欄），後勤那欄留空（使用者 2026-11-20「FA 的主教練改成 教練與分析師也列入」）
    // 後勤排序（使用者 2026-11-21）：新加入 → 續約 → 續留 → 升職 → 合約到期（→ 傳聞）；已宣布離隊的直接離開後勤區（自由人那列不動）
    const stfK=e=>e.r?5:e.pm?3:(e.new||e.tip)?0:e.rs?1:(e.c&&e.c<today)?4:2;
    // CO＝主教練＋後勤全部（主教練排前面）：手機版的 FA 卡把兩格併成一格（使用者 2026-11-21「手機版的FA資訊 主教練跟教練要放一起」；電腦版仍分兩欄）
    const colE=(t,c)=>c==="CO"?[...(t.r.COACH||[]).filter(isHC),...(t.r.COACH||[]).filter(e=>!isHC(e))]:c==="HC"?(t.r.COACH||[]).filter(isHC):c==="STF"?(t.fa?(t.r.COACH||[]).filter(e=>!isHC(e)):(t.r.COACH||[]).filter(e=>!isHC(e)).map((e,i)=>[e,i]).sort((a,b)=>stfK(a[0])-stfK(b[0])||a[1]-b[1]).map(a=>a[0])):(t.r[c]||[]);
    const colP=(t,c)=>{ const pv=(t.prev||{})[c==="HC"||c==="STF"||c==="CO"?"COACH":c]||[];
      return c==="HC"?pv.filter(isHC):c==="STF"?pv.filter(p=>!isHC(p)):pv; };
    const pn=s=>String(s||"").replace(/\s*\([^()]*\)\s*$/,"");
    // 教練欄只列這五種（使用者 2026-11-19「除了總教練 教練 分析師以外的教練都不要列出」「戰略教練也列出」「路線教練也可以」），名字後面標職稱
    const SRN=en2?{HC:"Head Coach",C:"Coach",SC:"Strategic Coach",PC:"Positional Coach",AN:"Analyst"}:{HC:"主教練",C:"教練",SC:"戰略教練",PC:"路線教練",AN:"分析師"};
    const today=new Date().toISOString().slice(0,10), ymd=s=>s?s.replace(/-/g,"/"):"";
    const LG_OF_RG=r=>RG_LG[r]||"";
    const board=(D.board||[]).filter(t=>!F_RG.size||[...F_RG].some(r=>LG_OF_RG(r)===t.lg));
    const bq=q, hitE=e=>bq&&(pn(e.n).toLowerCase().includes(bq)||String(e.p||"").toLowerCase().includes(bq));
    const bRows=board.filter(t=>!bq||[t.tm,t.nm,abOf(t.nm)].join(" ").toLowerCase().includes(bq)||BL.some(r=>(t.r[r]||[]).some(hitE)));
    const TIPS=[];
    // 格子提示（使用者 2026-11-19「除了評分的小框都重新設計」）：同評分小框的版型——標題列＝隊徽＋隊名＋路線；
    //   每個人一張小卡（名字＋狀態標籤、合約／加入／來自 的欄位、傳聞引用框）；上一位獨立一區（期間＋年資）
    // 聯賽識別色＝全站 LGC（使用者 2026-11-19「要跟積分分頁的聯賽顏色一樣」），不另外定義
    const laneIc=r=>(r==="COACH"||r==="HC"||r==="STF"||r==="CO")?`<img src="img/COACH.png" alt="">`:(POS_IMG[r]?`<img src="${POS_IMG[r]}" alt="">`:"");
    const pill=(c,tx)=>`<span class="tpPill ${c}">${tx}</span>`;
    // 綠＝合約還在、但傳出可能去別隊（使用者 2026-11-19「如果合約還在但有傳出可能去別隊 上綠色」）；合約已到期的維持藍字、提示照樣看得到傳聞
    const expd=e=>!e.tip&&(!e.c||e.c<today);   // 合約無紀錄也算合約到期（使用者 2026-11-20「合約無紀錄的 例如 Uniboy 這種 也要算是合約到期」）
    const roOn=e=>!!(e&&e.ro&&!(expd(e)&&!e.rs));
    const stPill=e=>e.ret?pill("tpX",en2?"Retired":"退役"):e.cb?pill("tpB",en2?"Comeback":"復出"):e.gone?pill("tpB",en2?"Departure announced":"已宣布離隊"):e.r?pill("tpY",en2?"Rumor":"傳聞"):e.pm?pill("tpV",en2?"Promoted":"升職"):(e.new||(e.tip&&!e.r))?pill("tpR",en2?"New":"新加入"):roOn(e)?pill("tpG",en2?"Possible move":"可能轉會")
      :(expd(e)&&!e.rs)?pill("tpB",en2?"Contract expired":"合約到期"):e.rs?pill("tpK",en2?"Re-signed":"續約"):"";
    const tmChip=n=>`<span class="tpTm">${teamLogoHTML(tAb(n),16,true,n)||""}${esc(abOf(n))}</span>`;
    const tenureP=o=>{ if(!o.s)return null; const unk=o.e==="?", e=(!o.e||unk)?today:o.e;
      const mo=(+e.slice(0,4)-+o.s.slice(0,4))*12+(+e.slice(5,7)-+o.s.slice(5,7)), y=Math.floor(mo/12), m=Math.max(mo%12,0);
      const sameM=!!o.e&&!unk&&o.e.slice(0,7)===o.s.slice(0,7);   // 同一個月進出的寫到日（不然會是「2026/09 – 2026/09」）
      return {per:sameM?`${ymd(o.s)} – ${ymd(o.e).slice(5)}`:`${ymd(o.s).slice(0,7)} – ${unk?(en2?"departure date not recorded":"離隊日未記錄"):o.e?ymd(o.e).slice(0,7):(en2?"now":"今")}`,
        du:unk?"":(en2?(y?`${y}y${m?` ${m}m`:""}`:`${m}m`):(y?`${y} 年${m?` ${m} 個月`:""}`:`${m} 個月`))}; };
    // 離隊的人去了哪（使用者 2026-11-20「如果選手離開 A 隊去 B 隊 本來 A 隊的那路線小框也要寫那選手離隊後去哪」）：
    //   翻整張陣容表找他現在出現在哪一隊——官方加入的寫「加入 B」，只有傳聞的列出傳聞的隊（最多三隊）並標傳聞
    const WHERE=new Map(); board.forEach(t=>Object.values(t.r||{}).flat().forEach(e=>{ if(e.gone||!(e.new||e.r||e.tip))return; const k=String(pn(e.n)).toLowerCase(); if(!WHERE.has(k))WHERE.set(k,[]); WHERE.get(k).push({tm:t.nm,r:!!e.r}); }));
    const goKv=(name,self)=>{ const L=(WHERE.get(String(pn(name)).toLowerCase())||[]).filter(o=>o.tm!==self); if(!L.length)return []; const off=L.filter(o=>!o.r);
      // 只有傳聞的：這一列的標題直接寫「傳聞」，後面不再另外標（使用者 2026-11-21「如果FA小框的去向 寫的是傳聞…那就把去向改寫成傳聞」）
      return off.length?[[en2?"Joined":"加入",tmChip(off[0].tm)]]:[[en2?"Rumor":"傳聞",L.slice(0,3).map(o=>tmChip(o.tm)).join(" ")]]; };
    // 來源名稱：Sheep Esports 一律寫 SE；有網址就做成超連結（使用者 2026-11-20「Sheep 的來源就寫 SE 然後超連結」）。沒寫來源的是 Sheep 的推文
    const srcA=o=>{ const nm=(!o.src||o.src==="Sheep Esports")?"SE":o.src==="韓網"?SRCN.kr:o.src==="官方"?SRCN.man:o.src, u=o.u||"";   /* 英文版：韓網→Korean media、官方→Announcement（跟消息頁同一套名稱） */ return /^https?:/.test(u)?`<a class="tpSrc" href="${esc(u)}" target="_blank" rel="noopener">${esc(nm)}</a>`:esc(nm); };
    const tipTx=o=>{ const s=en2?(o.tipE||(D.tipEn||{})[o.tip]||o.tip):o.tip; return TNRE?String(s||"").replace(TNRE,n=>TNL.get(n.toLowerCase())||n):s; };   // 小框引用句的隊名也寫縮寫（使用者 2026-11-21「小框的資訊以後也都要同步改」）   // 英文版引用句：資料端的中→英對照（tipEn），手動名單自帶 tipE
    const cellTip=(t,r)=>{ const es=colE(t,r), pv=colP(t,r);
      let h=`<div class="tpBox" style="--lgc:${LGC[t.lg]||"var(--gold)"}"><div class="rtHd">${teamLogoHTML(tAb(t.nm),22,true,t.nm)||""}<b>${esc(rowNm(t))}</b>`
        +`<span class="tpLane">${laneIc(r)}${BLN[r]}</span><span class="tpLg">${esc(t.lg)}</span></div>`;
      if(!es.length)h+=`<div class="rtEmpty">${en2?"Vacant":"空缺"}</div>`;
      es.forEach(e=>{ const kv=[];
        // FA：合約跟來自併成一列「與 NS 已到期 2026/11/16」（使用者 2026-11-21「合約跟來自要合併寫 比較清晰」）
        const faC=e.fa&&e.from?(en2?`with ${tmChip(e.from)} `:`與 ${tmChip(e.from)} `):"";
        // 「到期 2026/11/16」；合約還沒到就宣布離隊的＝提早解約，寫「解約」（使用者 2026-11-21）
        const JD=(e.new||(e.tip&&!e.r&&e.d))?(e.new||e.d):"";
        if(faC)kv.push([en2?"Contract":"合約",faC+(e.c?(e.c<today?`<span class="tbExp">${en2?"expired":"到期"} ${ymd(e.c)}</span>`:(e.gone?`<span class="tbExp">${en2?"terminated":"解約"}${e.gd?" "+ymd(e.gd):""}</span>`:`${en2?"until":"到"} ${ymd(e.c)}`)):`<span class="tbMuted">${en2?"not on record":"無紀錄"}</span>`)]);
        else if(e.rs&&(!e.c||e.c<today))kv.push([en2?"Contract":"合約",e.rs!=="1"?`${en2?"re-signed through":"續約到"} ${e.rs}`:(en2?"re-signed":"已續約")]);
        else if(JD)kv.push([en2?"Contract":"合約",`${en2?"joined":"加入於"} ${ymd(JD)}`+(e.c&&e.c>=today?`${en2?", until":"，到"} ${ymd(e.c)}`:"")]);   // 剛加入通常還不知道年限 ⇒ 合約與加入併成一行（使用者 2026-11-21）
        else if(e.c)kv.push([en2?"Contract":"合約",e.c<today?`<span class="tbExp">${en2?"expired":"已到期"} ${ymd(e.c)}</span>`:`${en2?"until":"到"} ${ymd(e.c)}`]);
        else if(!e.r)kv.push([en2?"Contract":"合約",`<span class="tbMuted">${en2?"not on record":"無紀錄"}</span>`]);
        // 升職怎麼升的（使用者 2026-11-20「升職怎麼樣的升法 小框要寫」）：職稱異動「教練 → 主教練」；或「從 二隊 上調」
        if(e.pm){ const RZ={"Head Coach":"主教練","Interim Head Coach":"代理主教練","Assistant Coach":"教練","Strategic Coach":"戰略教練","Positional Coach":"路線教練","Coach":"教練","Analyst":"分析師","Head Analyst":"分析師"};
          kv.push([en2?"Promoted":"升職",typeof e.pm==="string"?e.pm.split(" to ").map(z=>en2?z:(RZ[z.trim()]||z)).join(" → "):(e.from?(en2?`called up from ${tmChip(e.from)}`:`從 ${tmChip(e.from)} 上調`):(en2?"promoted":"升職"))]); }
        if(JD&&(faC||(e.rs&&(!e.c||e.c<today))))kv.push([en2?"Joined":"加入",ymd(JD)]);
        if(e.gone)kv.push(...goKv(e.n,t.nm));
        if(e.from&&!faC&&!(e.pm&&typeof e.pm!=="string"))kv.push([en2?"From":"來自",tmChip(e.from)]);
        // 退役的人不寫評分，改寫年資＝wiki 效力紀錄的第一天到最後一天（使用者 2026-11-21「小框的評分改寫成 他在WIKI顯示的年資」）；資料端給 ys／ye
        if(e.fa&&e.ret){ const T=e.ys?tenureP({s:e.ys,e:e.ye||"?"}):null; if(T)kv.push([en2?"Career":"年資",T.du?`${T.du}（${T.per}）`:T.per]); }
        else if(e.fa&&e._sc!=null)kv.push([en2?"Score":"評分",e._sc.toFixed(1)+(e._wl?` <span class="tbMuted">${esc(e._wl)}</span>`:"")]);   // 從別的聯賽換算過來的，後面標原聯賽（跟評分小框同一種寫法：只寫聯賽、不寫權重數字）   // 自由人的評分寫在最後一列（使用者 2026-11-20）   // 上調的已經寫「從 X 上調」，不重複寫來自（使用者 2026-11-20）
        h+=`<div class="tpP"><div class="tpName"><b class="${tbCls(e)}"><a class="tpA" href="https://lol.fandom.com/wiki/${encodeURIComponent(wkPg(e.p||((D.roles||{})[e.n]||[])[1]||e.n))}" target="_blank" rel="noopener">${esc(pn(e.n))}</a></b>${e.sr?`<span class="tpSr">${SRN[e.sr]}</span>`:""}${stPill(e)}</div>`
          +(kv.length?`<div class="tpKv">${kv.map(([k,v])=>`<span>${k}</span><span>${v}</span>`).join("")}</div>`:"")
          // 傳聞引用只留最新的一則（使用者 2026-11-21「小框顯示的傳聞新聞 顯示最新一個就好」）；去向那列照舊列出所有傳聞隊伍
          +[...(e.r&&e.tip?[[e.d||"",`<div class="tpQ tpGo" data-go="${esc(pn(e.n))}|${e.d||""}|${esc(abOf(t.nm))}"><span>${ymd(e.d).slice(5)}・${srcA(e)}</span>${esc(tipTx(e))}</div>`]]:[]),
          ...(e.ros||(e.ro?[e.ro]:[])).map(o=>[o.d||"",`<div class="tpQ tpGo" data-go="${esc(pn(e.n))}|${o.d||""}|${esc(abOf(o.to))}"><span>${ymd(o.d).slice(5)}・${srcA(o)}・${en2?"rumored to join":"傳聞去"} ${tmChip(o.to)}</span>${esc(tipTx(o))}</div>`]),...(e.tips||[]).map(o=>[o.d||"",`<div class="tpQ tpGo" data-go="${esc(pn(e.n))}|${o.d||""}|"><span>${ymd(o.d).slice(5)}・${srcA(o)}</span>${esc(tipTx(o))}</div>`])].sort((a,b)=>a[0]<b[0]?1:a[0]>b[0]?-1:0).slice(0,1).map(q=>q[1]).join("")+`</div>`; });
      if(pv.length){ h+=`<div class="tpPv">`   /* 不寫「上一位」標題，靠分隔線隔開（使用者 2026-11-19） */
        +pv.map(p=>{ const o=typeof p==="string"?{n:p}:p, T=tenureP(o);
          // 上一位改成跟上面同一種小卡（使用者 2026-11-19「上一位跟上面合約有續約的UI相近一點」）：名字＋職稱＋標籤，下面 效力／年資 欄位
          // 還沒宣布離隊、只是被新人擠到這裡的（WBG Elk）：寫合約到期日，不寫效力期間（使用者 2026-11-20）
          // 合約其實還沒到期的人（合約還在、傳出要走、同一路已有別的人選 ⇒ 被移到這裡的綠字，RED 的 frosty 合約到 2027/11）不可以寫「已到期」：寫「到 日期」、標「可能轉會」
          const live=!!(o.still&&o.c&&o.c>=today);
          const kv=o.still?(o.c?[[en2?"Contract":"合約",live?`${en2?"until":"到"} ${ymd(o.c)}`:`<span class="tbExp">${en2?"expired":"已到期"} ${ymd(o.c)}</span>`]]:[])
            :T?[[en2?"Tenure":"效力",T.per]]:[];   // 年資不寫（使用者 2026-11-21）
          if(!o.ret)kv.push(...goKv(o.n,t.nm));
          return `<div class="tpP tpPvC"><div class="tpName"><b><a class="tpA" href="https://lol.fandom.com/wiki/${encodeURIComponent(wkPg(o.n))}" target="_blank" rel="noopener">${esc(pn(o.n))}</a></b>${(r==="STF"||r==="HC"||r==="CO")&&o.sr&&SRN[o.sr]?`<span class="tpSr">${SRN[o.sr]}</span>`:""}${o.ret?pill("tpX",en2?"Retired":"退役"):live?pill("tpG",en2?"Possible move":"可能轉會"):o.still?pill("tpB",en2?"Contract expired":"合約到期"):pill("tpX",en2?"Left":"離隊")}</div>`
            +(kv.length?`<div class="tpKv">${kv.map(([k,v])=>`<span>${k}</span><span>${v}</span>`).join("")}</div>`:"")+`</div>`; }).join("")+`</div>`; }
      TIPS.push(h+`</div>`); return TIPS.length-1; };
    // 轉會評分（使用者 2026-11-19「教練右邊新增一欄 轉會評分 依照原先選手的成績去與新選手的成績對比 判斷是加分還是扣分 然後教練只看主教練」）：
    //   選手＝選手分頁同一套「評分」（calcPlayers 同路百分位，withRef(0) 借整年全部賽事、不吃上方篩選），每條路 新人 − 上一位；
    //   教練只看總教練：教練沒有個人數據 ⇒ 新總教練原隊的戰隊評分 − 本隊的戰隊評分（calcTeams）。
    //   只算官方確認的新人（傳聞不算）；新人或上一位沒有該年比賽資料的那條路不計。年份要切到該休賽期的賽季才算得出來
    const SEASON=+String(D.from||"").slice(0,4)||0;
    const RATE=(()=>{ if(window.TRANSFER_RATE)return window.TRANSFER_RATE;   // 轉會網站：主站排程先算好匯出（transfers_site.js）
      if(curYear!==SEASON||typeof calcPlayers!=="function")return null;
      const k=curYear+"|"+(GAMES||[]).length+"|seg8"; if(window._tbRC&&window._tbRC.k===k)return window._tbRC;
      const res={k,pl:{},tm:{}};
      // 分段加權（使用者 2026-11-20「轉會評分改成 第一賽段 10% 第二賽段 30% 第三賽段 50% 世界賽 10% 其餘的不算」「哪個段落沒打就沒分」）：
      //   每段各自算一次選手評分（場次白名單 H2H 圈範圍、其他篩選清空），再照權重相加；沒打的那段＝0 分，不重新分配權重。
      //   賽段＝例行賽＋季後賽（S1／S1 PO…）；世界賽＝WLDs 全部（入圍賽、瑞士輪、淘汰賽）。MSI、盃賽、資格賽、升降賽都不算。
      //   只有兩個賽段的聯賽（CBLOL）：第一段算第二賽段的 30%、第二段算第三賽段的 50%（最後一段＝第三賽段，沿用先前的定義）
      // 2026-11-20 使用者改定案：第三賽段 50% → 40%，多一塊「國際賽資歷」10%（FST／MSI／世界賽過往的參賽與名次，scripts/transfers_intl.py 算成 0～100，D.intl）
      //   ——「我要反應 Deft 這種優異選手復出的評分過低問題」。同日使用者再定給分：世界賽 冠 5／亞 4／四強 3／八強 2／參加 1、MSI 4／3／2／1、FST 3／2／1，
      //   生涯直接加總、「分數破百沒差」⇒ 不混進百分位，而是算完百分位之後直接加在選手分數上（見 rateOf 的 get／fill）
      // 同日最後定案：「分數改成 賽段 1 2 3 ＝ 10 30 50 留 10% 給加分 破百沒差」「今年世界賽成績的參數分要拿掉」⇒ 今年世界賽那 10% 整個拿掉，
      //   三個賽段合計 90%（百分位 × 0.9），剩下 10% 的位置給國際賽資歷加分（直接加、可以超過）
      // 2026-11-21 使用者再改：「第一賽段10% FST5% 第二20% MSI10% 第三40% 世界賽15%」⇒ 六段合計 100%；沒打的那段照舊 0 分、不重新分配
      const SEGW={S1:0.1,F:0.05,S2:0.2,M:0.1,S3:0.4,W:0.15};
      const SEGW_OLD={S1:0.15,S2:0.35,S3:0.5};   // 2026-11-20 使用者「去年評分改成 123賽段 15 35 50」⇒ 三個賽段合計 100%，百分位不再打八折（BASEW_ 1）；成就加分照舊另外加
      //   // 再改：第三賽段 40%（使用者 2026-11-20「第三賽段改成 40%」）⇒ 三個賽段合計 80%，百分位 × 0.8，其餘留給加分
      const lastSp={}; (GAMES||[]).forEach(o=>{ const m=/^S(\d)/.exec(String(o.split||"")); if(m&&o.league!=="WLDs")lastSp[o.league]=Math.max(lastSp[o.league]||0,+m[1]); });
      const segOf=o=>{ if(o.league==="WLDs")return "W"; if(o.league==="FST")return "F"; if(o.league==="MSI")return "M"; const m=/^S(\d)( PO)?$/.exec(String(o.split||"")); if(!m)return ""; const sh=3-(lastSp[o.league]||3); return "S"+(+m[1]+sh); };
      const SEGRUN=(seg,fn)=>{ const ss=[].concat(seg), keep=new Set((GAMES||[]).filter(o=>ss.includes(segOf(o))).map(gkey));
        const sv={split:F.split,league:F.league,patch:F.patch,d1:F.d1,d2:F.d2,minG:F.minG}, svH=H2H;
        F.split=""; F.league="ALL"; F.patch=""; F.d1=""; F.d2=""; F.minG=0; H2H=keep;
        try{ return keep.size?fn():null; } finally{ H2H=svH; Object.assign(F,sv); } };
      for(const r of ["TOP","JNG","MID","BOT","SUP"])res.pl[r]={};
      for(const seg of ["S1","S2","S3","F","M","W"])SEGRUN(seg,()=>{ for(const r of ["TOP","JNG","MID","BOT","SUP"]){ const best={};
          calcPlayers(r,true).forEach(x=>{ const nk=String(x._pn||"").toLowerCase(); if(x.評分!=null&&(!best[nk]||best[nk].場數<x.場數))best[nk]=x; });
          for(const nk in best){ const x=best[nk], a=res.pl[r][nk]||(res.pl[r][nk]={v:0,g:0,lg:"",tm:"",sg:{}});
            a.v+=SEGW[seg]*x.評分; a.g+=x.場數; a.sg[seg]=+x.評分.toFixed(1);
            if(/^S/.test(seg)||!a.lg){ a.lg=x._lg||a.lg; a.tm=x._team||a.tm; } } }   // 所屬聯賽／戰隊取最後一個賽段的（世界賽的 _lg 是 WLDs，不拿來當所屬聯賽）
          // 戰隊：第三賽段的勝率（主教練戰績分用）
          if(seg==="S3")calcTeams("").forEach(x=>{ if(x.評分!=null)res.tm[teamFix(String(x.戰隊||""))]=x.評分; if(x.勝率!=null&&x.場數>=5)(res.wr=res.wr||{})[teamFix(String(x.戰隊||""))]=x.勝率;
            }); });
      // 第三賽段小框的數據＝第三賽段範圍內的所有比賽，含世界賽（使用者 2026-11-21）
      SEGRUN(["S3","W"],()=>calcTeams("").forEach(x=>{ if(x.場數)(res.s3=res.s3||{})[teamFix(String(x.戰隊||""))]={g:x.場數,wr:x.勝率,sc:x.評分}; }));
      res.md={}; for(const r of ["TOP","JNG","MID","BOT","SUP"]){ const vs=Object.values(res.pl[r]).map(x=>x.v).sort((a,b)=>a-b), h=vs.length>>1;
        res.md[r]=vs.length?(vs.length%2?vs[h]:(vs[h-1]+vs[h])/2):null; }
      res.plY={};   // 不再退回全年評分：沒打的賽段就是 0 分
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
    // rk＝「W名次|聯賽內名次」拆開：rk 留主要的（有世界賽就是世界賽），rkL＝聯賽內的名次
    (D.board||[]).forEach(t=>{ if(t.rkL!==undefined)return; const p=String(t.rk||"").split("|"); t.rkL=p[1]||(/^W/.test(p[0])?"":p[0]); if(t.rk)t.rk=p[0]; });
    const RK={}; (D.board||[]).forEach(t=>{ if(t.rk)[t.nm,t.tm].forEach(n=>RK[teamFix(String(tAb(n)||n))]=t.rk); });
    const ACH=rk=>{ if(!rk)return null; const m=/^([WPIR])(\d+)/.exec(rk); if(!m)return null; const n=+m[2];
      return m[1]==="W"?(n===1?50:n===2?45:n<=4?40:n<=8?35:n<=11?30:n<=16?28:24):m[1]==="P"?Math.max(22-2*n,8):m[1]==="I"?6:0; };
    // 第三賽段成績（戰績評分模式的最後一欄；使用者 2026-11-21「今年成績 改寫成第三賽段成績 有晉級世界賽就寫世界賽第幾名」）
    const RK3=(rk,t)=>{ if(!rk&&t&&!t.fa&&t.lg==="LPL")return en2?"Out in Split 2":"第二賽段遭淘汰";   // LPL 第二賽段後淘汰、沒打第三賽段的隊（OMG、UP；使用者 2026-11-21）
      if(/^U/.test(rk||""))return (en2?"Promotion: beat ":"升降賽擊敗 ")+abOf(rk.slice(1)); const m=/^([WPIR])(.+)$/.exec(rk||""); if(!m)return "–"; const n=m[2];
      if(m[1]==="W")return en2?("Worlds "+(n==="1"?"champion":n==="2"?"runner-up":n==="3-4"?"top 4":n==="5-8"?"top 8":n)):("世界賽"+(n==="1"?"冠軍":n==="2"?"亞軍":n==="3-4"?"四強":n==="5-8"?"八強":" "+n));   // 8 強以外直接寫「世界賽 9-11」（使用者 2026-11-21）
      return en2?"#"+n:`第 ${n} 名`; };   // 沒進世界賽的只寫整體名次，不標季後賽／例行賽（使用者 2026-11-21）   // 入圍賽與例行賽的名次都是整個聯賽的整體名次
    // 截圖寫在隊名縮寫下面的成績（使用者 2026-11-21「世界賽冠軍 -> WCS #1 ；LCK第五名 -> LCK #5」）：有進世界賽寫世界賽名次，否則寫聯賽名次；
    //   升降賽上來的隊寫「聯賽 #Q」；LPL 第二賽段就淘汰、沒打第三賽段的兩隊資料裡沒有名次，照使用者指定的寫（2026-11-21「UP 寫 LPL #13 OMG#14」），
    //   截圖排序也照這個名次排在該聯賽最後（S2OUT；網頁的戰績評分那一欄仍寫「第二賽段遭淘汰」，那是使用者同一天稍早定的）
    const S2OUT={"Ultra Prime":13,"Oh My God":14}, s2Of=t=>(t&&!t.fa&&!t.rk&&t.lg==="LPL"&&(S2OUT[t.nm]||S2OUT[t.tm]))||0;
    const rkS=t=>{ if(!t||t.fa)return ""; const rk=String(t.rk||""), m=/^([WPIR])(.+)$/.exec(rk);
      if(/^U/.test(rk))return t.lg+" #Q";   // 升降賽上來的隊：#Q（使用者 2026-11-21「升降賽上來的 截圖的成績寫 LCP #Q」；中英文同一種寫法）
      if(!m)return s2Of(t)?"LPL #"+s2Of(t):(t.lg==="LPL"?(en2?"LPL out in S2":"LPL S2 淘汰"):"");
      return (m[1]==="W"?"WCS":t.lg)+" #"+m[2]; };
    const RKN=rk=>{ if(!rk)return en2?"no result":"無成績"; if(/^U/.test(rk))return RK3(rk); const m=/^([WPIR])(.+)$/.exec(rk); if(!m)return en2?"no result":"無成績"; const n=m[2];
      return en2?({W:"Worlds ",P:"Playoffs #",I:"Play-in ",R:"Regular #"}[m[1]]+n):({W:`世界賽 ${n==="1"?"冠軍":n==="2"?"亞軍":n}`,P:`季後賽第 ${n} 名`,I:"季後賽入圍賽",R:`例行賽第 ${n} 名`}[m[1]]); };
    // noW＝選手評分用：今年世界賽打到第幾名不再算（使用者 2026-11-20「那麼今年世界賽成績的參數分要拿掉」——世界賽名次已經用國際賽資歷分直接加在選手身上，
    //   這裡再算一次就重複了）⇒ 進世界賽的隊一律給「有進世界賽」的基本分 24，不分名次；主教練的戰績分照舊看名次
    const coachS=(n,noW)=>{ if(!RATE||!n)return null; const k=teamFix(String(tAb(n)||n)), wr=(RATE.wr||{})[k]; if(wr==null)return null;
      const rk=RK[k], a=(noW&&/^W/.test(rk||""))?24:(ACH(rk)||0); return {v:wr*50+a, wr, rk, note:`${RKN(rk)}・${en2?"WR":"勝率"} ${Math.round(wr*100)}%`}; };
    const T1SET=new Set(board.flatMap(x=>[x.nm,x.tm])), BASEW_=1;   /* 原本 0.8＝三個賽段合計 80%；賽段權重改成 15／35／50 之後是 100% */
    // 聯賽強度的換算（隊伍評分與自由人共用）：別的聯賽來的分數 × exp(LGK × (原聯賽強度 − 目的聯賽強度))；同聯賽＝1、強度缺＝1
    const LGK=0.3, lgW0=(from,to)=>{ const a=lgN(from), Rg=(RATE&&RATE.R)||{}; return (!a||a===to||Rg[a]==null||Rg[to]==null)?1:Math.exp(LGK*(Rg[a]-Rg[to])); };
    // 自由人那一列照分數高到低排（使用者 2026-11-20「FA 的人依照分數排序」）：選手＝轉會評分同一套分數（同路百分位＋國際賽加分）、
    //   今年沒資料的當 50 分再加國際賽分；主教練＝原隊的戰績分。分數存在 e._sc，小框也拿來顯示。
    //   聯賽強度：列在哪個聯賽的 FA 就換算成那個聯賽的分數（使用者 2026-11-21「Doggo為何…LEC跟LCP都是顯示相同評分」：原本這裡不乘聯賽強度，
    //   後來有傳聞去別的聯賽的人兩邊都列，兩邊就照抄同一個數字）；列在自己原本的聯賽時權重是 1，分數不變。e._wl＝有換算時的原聯賽（小框標出來）
    if(RATE){ const blend0=a=>{ const ts=a.tm?coachS(a.tm,true):null; return ts?(a.v+ts.v)/2:a.v; }, SC0={};
      const srt0=r=>SC0[r]||(SC0[r]=Object.values(RATE.pl[r]||{}).map(blend0).sort((x,y)=>x-y));
      const pct0=(r,v)=>{ const a=srt0(r); if(!a.length)return 50; let lo=0, eq=0; for(const z of a){ if(z<v)lo++; else if(z===v)eq++; } return 100*(lo+eq/2)/a.length; };
      board.filter(t=>t.fa).forEach(t=>{ for(const r in t.r){ t.r[r].forEach(e=>{ const k=String(pn(e.n)).toLowerCase(), it=(D.intl||{})[k]||0;
            if(r==="COACH"){ const c=e.from?coachS(e.from):null; e._sc=c?c.v:null; }
            else{ const a=(RATE.pl[r]||{})[k], w=a?lgW0(a.lg,t.lg):1; e._sc=(a?Math.min(100,(50+(pct0(r,blend0(a))-50)*Math.min(1,(a.g||0)/30))*w):50)*BASEW_+it; e._wl=a&&Math.abs(w-1)>0.005?lgN(a.lg):""; } });
          t.r[r].sort((p,q)=>((p.ret?1:0)-(q.ret?1:0))||(r==="COACH"?((p.sr==="HC"?0:1)-(q.sr==="HC"?0:1)):0)||(q._sc??-1)-(p._sc??-1)||String(p.n).localeCompare(String(q.n))); } }); }   // 退役的一律排最後（使用者 2026-11-21「退役選手在FA 直接把他列在最後一位」）   // 教練那格：主教練排前面   // 三個賽段合計的占比（10＋30＋40），跟 RATE 那邊的 SEGW 要一起改
    const rateOf=t=>{ if(!RATE||t.fa)return null; const items=[], scOf=new Map(), plL=[]; let plSum=0;   // FA 列不是隊伍，不算評分
      // 聯賽權重：別的聯賽來的分數 × exp(LGK × (原聯賽強度 − 本隊聯賽強度))；同聯賽＝1、強度缺＝1
      const blend=a=>{ const ts=a.tm?coachS(a.tm,true):null; return ts?(a.v+ts.v)/2:a.v; };
      // 中位數也用同一把尺（個人＋戰績各半之後的分數）重算，不然空缺的基準會比真人高一截
      const MDB=window._tbMDB&&window._tbMDB.k===RATE.k?window._tbMDB:(window._tbMDB={k:RATE.k});
      // 刻度換成同路百分位（使用者 2026-11-20「Zeus 為何才 68.4 分 我的感覺他起碼應該要 90 分」）：個人＋戰績各半的原始分最高也才 80 出頭，
      //   排名對但數字看起來不像頂尖 ⇒ 換成「贏過同一路百分之幾的選手」（最高接近 100、中段 50）；空缺的基準（中位數）＝50
      const srt=r=>MDB[r]||(MDB[r]=Object.values(RATE.pl[r]||{}).map(blend).sort((x,y)=>x-y));
      const pct=(r,v)=>{ const a=srt(r); if(!a.length)return v; let lo=0; for(const z of a){ if(z<v)lo++; else break; } let eq=0; for(const z of a){ if(z===v)eq++; } return 100*(lo+eq/2)/a.length; };
      const mdOf=r=>srt(r).length?50:null;
      const lgW=lg=>lgW0(lg,t.lg);
      for(const r of ["TOP","JNG","MID","BOT","SUP"]){ const P=RATE.pl[r], PY=(RATE.plY||{})[r]||{},
          get=(n,base=50)=>{ const k=String(pn(n)).toLowerCase(), a=P[k]||(PY[k]?{...PY[k],yr:1}:undefined); if(!a)return a;
            // 個人評分只看個人數據（弱隊核心會很高：Scout 在 NS 91.4、Faker 39.6）⇒ 跟所屬戰隊的戰績分（第三賽段勝率＋最終成績）各半
            //   （使用者 2026-11-20「Scout 為何能有 91.4 分 評分是不是怪怪的」；原話「只看第三賽段數據以及最終成績」）；戰隊沒有戰績資料就只用個人
            // 出賽太少的人往 50 分靠攏（使用者 2026-11-20「為何 Bluffing 的分數這麼高」：他只替 HLE 代打 6 場就拿到 67.7，還吃到 HLE 整年的戰績分，
            //   比打了 62 場的 Peter 還高）⇒ 不到 30 場的照場數比例打折：分數＝50＋（原分數−50）× 場數／30
            const v0=base+(pct(r,blend(a))-base)*Math.min(1,(a.g||0)/30), w=lgW(a.lg), it=(D.intl||{})[k]||0; return {...a,raw:v0,v:Math.min(100,v0*w)*BASEW_+it,w,it}; };   // 國際賽資歷分直接加，可以破百
        // 今年沒有比賽資料的人（使用者 2026-11-19「用全部該路線的分數中位數當做基準」）：s 補成中位數、標 md；兩邊都沒資料就不算
        // 次級聯賽上來、今年完全沒有一級聯賽出賽紀錄的人：比中位數低 10 分（使用者 2026-11-20「次級上來且去年完全沒有一軍出賽紀錄的選手 應該比中位數低 10 分左右」）；
        //   判定＝原隊不在六大聯賽一級隊名單裡，或從同組織二隊／青訓上調（pm===1）。有少量出賽的（Bluffing 6 場）靠攏的目標也一樣是 40
        const isSub=e=>e.pm===1||(!!e.from&&!T1SET.has(e.from));
        // 今年沒有比賽資料的人（復出的 Deft）：基準 50（次級上來 40）再加他的國際賽資歷分
        const itOf=n=>(D.intl||{})[String(pn(n)).toLowerCase()]||0;
        const md=mdOf(r), fill=x=>x.s?x:(md==null?x:{...x,s:{v:(md-(x.sub?10:0))*BASEW_+itOf(x.n),g:0,lg:""},md:1}), byG=(a,b)=>(b.s?b.s.g:-1)-(a.s?a.s.g:-1);
        // 同一格多人：照分數高到低排（使用者 2026-11-20「多選手沒依照分數上到下」）；分數跟評分小框同一把尺，沒資料的用基準分
        const sv=e=>{ const sub=isSub(e), x=fill({n:pn(e.n),s:get(e.n,sub?40:50),sub}); return x.s?x.s.v:-1; }, onTm=e=>!(e.r||e.gone||(expd(e)&&!(e.new||e.rs||e.pm)));
        // 選手評分（使用者 2026-11-20「第三下第四下變成 選手評分升降冪」「一個路線兩個選手的話要取平均」）：這一路的分數＝格子裡所有人的平均（已宣布離隊的不算）；空的用基準分。五路加總
        // 同一路官方已定（續約／新加入／升職）的有兩位以上 ⇒ 兩種評分都以分數最高的那位算（使用者 2026-11-20「如果一路宣布續約 加入 升職兩位以上 算評分時以最高的算」）
        (t.r[r]||[]).forEach(e=>scOf.set(e,sv(e)));   // 每個人的分數留著，小框的續約／續留那幾列要寫
        const conf=(t.r[r]||[]).filter(e=>!e.gone&&(e.new||e.rs||e.pm||(e.tip&&!e.r)));
        // 畫刪除線的人都不算（已宣布離隊，或合約到期又傳出去別隊——LØS 的 Zest；使用者 2026-11-20「為何 Zest 宣布離隊 小框依然有資料 但 CFO 的都沒有」）
        { const es=(conf.length>=2?conf:(t.r[r]||[]).filter(e=>!e.gone&&!(expd(e)&&e.ro&&!e.r&&!e.pm&&!e.new&&!e.rs))).map(e=>({n:pn(e.n),v:sv(e),it:itOf(e.n),e})).filter(x=>x.v>=0), vs=es.map(x=>x.v);
          const lv=vs.length?(conf.length>=2?Math.max(...vs):vs.reduce((a,b)=>a+b,0)/vs.length):(md==null?0:md*BASEW_);
          plSum+=lv; plL.push({r,ps:es.sort((a,b)=>b.v-a.v),v:lv,best:conf.length>=2}); }
        if((t.r[r]||[]).length>1&&!t._srt?.[r]){ (t._srt||(t._srt={}))[r]=1;
          t.r[r].map((e,i)=>({e,i,v:sv(e),g:(e.r||e.gone||(expd(e)&&!(e.new||e.rs||e.pm)))?1:0})).sort((p,q)=>p.g-q.g||q.v-p.v||p.i-q.i)   /* 還在隊上的（續留／新加入／續約／升職／合約還在）排最前面，再來才是合約到期、已離隊、傳聞（使用者 2026-11-20「這種路線上擺第一個 因為他還是在隊伍」）*/.forEach((o,i)=>{ t.r[r][i]=o.e; }); }
        const cands=(t.r[r]||[]).filter(e=>e.new||e.tip).map(e=>{ const sub=isSub(e); return {n:pn(e.n),s:get(e.n,sub?40:50),rm:!!e.r,sub,e}; }).sort((a,b)=>a.rm-b.rm||byG(a,b));
        let nw=cands[0];   // 官方優先；Sheep 消息（傳聞／官方未進 wiki）也算
        if(conf.length>=2){ const best=conf.map(e=>{ const sub=isSub(e); return fill({n:pn(e.n),s:get(e.n,sub?40:50),rm:false,sub,e}); }).filter(x=>x.s).sort((a,b)=>b.s.v-a.s.v)[0]; if(best)nw=best; }
        // 這一路沒有官方新人、傳聞人選有兩位以上 ⇒ 每一位的分數都列出來，這一路用平均（使用者 2026-11-20「如果該路的傳聞選手有兩位以上 就所有分數都要列出 但顯示的是該路要取平均」）
        const multi=cands.length>=2&&cands.every(x=>x.rm)?cands.map(x=>fill(x)).filter(x=>x.s):null;
        // 有人離隊、還沒補人（格子沒有官方的人、也沒傳聞）⇒ 空缺當中位數（使用者 2026-11-19「有選手離隊但還沒補新人也是這樣做」）
        // 2026-11-20 使用者改定案「空的先不算分」：走光還沒補人的隊（LEV +168、DSG +114）會因為「空缺 50 分 − 原本的低分」變成大加分，不合理 ⇒ 空缺那一路整個不計
        if(!nw)continue;
        // 被比較的「原本那位」：上一位＋已宣布離隊的；都沒有（原本的人還在隊上、只是傳出有人要來：DK 的 Siwoo／Lucid／Career）⇒ 拿現在那格的人比，
        //   優先挑傳出要走的（使用者 2026-11-20「DK 為何沒評分」）
        let odSrc=[...((t.prev||{})[r]||[]),...(t.r[r]||[]).filter(e=>e.gone)];
        if(!odSrc.length){ const ex=(t.r[r]||[]).filter(e=>!e.gone&&!e.new&&!e.tip&&!e.r), go=ex.filter(e=>e.ro); odSrc=go.length?go:ex; }
        const od=odSrc.map(p=>{ const n=typeof p==="string"?p:p.n; return {n:pn(n),s:get(n),e:(typeof p!=="string"&&"p" in p)?p:{prevE:typeof p==="string"?{}:p}}; }).sort(byG)[0];   // e＝格子裡的人（照陣容表的顏色）；prevE＝上一位（已離隊）
        if(nw&&od&&(nw.s||od.s)){ const A=fill(nw), B=fill(od);
          const tg=x=>[x.s.yr?(en2?"full year":"全年"):"",x.s.w&&Math.abs(x.s.w-1)>0.005?lgN(x.s.lg):""].filter(Boolean).join(" ");   // 只寫「全年 LEC」，不寫權重數字（使用者 2026-11-20）
          // 多位傳聞人選：不取平均，用「最低～最高」表示（使用者 2026-11-20「評分顯示不要用平均好了 就用 ～ 代表最低最高分」）；d＝中間值，只拿來排序與決定顏色
          const mv=multi&&multi.length>=2?multi.map(x=>x.s.v):null, mlo=mv?Math.min(...mv):null, mhi=mv?Math.max(...mv):null, av=mv?(mlo+mhi)/2:null;
          if(A.s&&B.s&&A.n!==B.n)items.push({r,nw:A.n,od:B.n,a:av??A.s.v,b:B.s.v,d:(av??A.s.v)-B.s.v,dlo:(mlo??A.s.v)-B.s.v,dhi:(mhi??A.s.v)-B.s.v,nws:av!=null?multi.map(x=>({n:x.n,v:x.s.v,e:x.e})).sort((p,q)=>q.v-p.v):null,ne:A.e,oe:B.e,rm:A.rm,ma:A.md&&(A.vac?2:1),mb:B.md,ta:A.md?"":tg(A),tb:B.md?"":tg(B)}); } }
      const hc=(t.r.COACH||[]).find(e=>e.sr==="HC"&&(e.new||e.tip)&&e.from), A=hc&&coachS(hc.from), B=coachS(t.nm)||coachS(t.tm);
      if(hc&&A&&B)items.push({r:"COACH",nw:`${pn(hc.n)}（${abOf(hc.from)}・${A.note}）`,od:`${abOf(t.nm)}（${B.note}）`,a:A.v,b:B.v,d:A.v-B.v,rm:!!hc.r});
      // 續約鼓勵分（使用者 2026-11-20「選手續約給個五分鼓勵 如果兩人續約給兩個6分 以此類推到五人 最後五人續約時 主教練也沒變化 那就是總共+50」）：
      //   N 路有人續約 ⇒ 每人 1.5＋N×0.5 分（1 人 2、2 人各 2.5、…、5 人各 4＝20）；五路都續約且主教練沒換再 ＋5 ⇒ 合計 25
      //   （原本是每人 4＋N、合計 50：BRO 原班續約 ＋50 比 DK 換上 Doran＋Kanavi 還多 ⇒ 使用者 2026-11-20 同意調小）
      //   2026-11-20 再改「主教練續約也算進去獎勵 獎勵的算法變成六人」：主教練跟選手一樣，有續約就算一人 ⇒ 最多六人、每人 1.5＋N×0.5（六人各 4.5＝27）；
      //   原本「五路都續約且主教練沒換再 ＋5」那條拿掉（主教練只是沒換、沒有續約消息的不算）
      //   2026-11-20 三改「續留也要加分」：續留（白字：合約還在、沒有任何動向）跟續約一樣算一人。keep＝續約，或合約還在且沒有傳出要走；新加入／傳聞／升任／已離隊的不算
      { const keep=e=>!e.gone&&!e.r&&!e.new&&!e.tip&&!e.pm&&(e.rs||(!expd(e)&&!e.ro));
        const rsL=["TOP","JNG","MID","BOT","SUP"].filter(r=>(t.r[r]||[]).some(keep)), hcR=null   /* 2026-11-20 五改「主教練不給獎勵分好了」：只算五路選手 */, nR=rsL.length;
        // 2026-11-20 四改「續留給1分 續約給兩分 不漸進好了」：固定分數，不再隨人數加碼（六人全續約最多 12）
        if(nR){ rsL.forEach(r=>{ const e=t.r[r].find(x=>keep(x)&&x.rs)||t.r[r].find(keep); items.push({r,rs:e.rs?1:3,nw:pn(e.n),ne:e,v:scOf.get(e),d:e.rs?2:1}); });
          if(hcR){ const cs=coachS(t.nm)||coachS(t.tm); items.push({r:"COACH",rs:hcR.rs?1:3,nw:pn(hcR.n),ne:hcR,v:cs?cs.v:null,d:hcR.rs?2:1}); }
          // 默契加成（使用者 2026-11-20「固定給就沒把默契加成放大」→ 同意折衷）：留下來的五路選手兩兩一組，每組 0.5（2 人 0.5、3 人 1.5、4 人 3、5 人 5）；主教練不算搭檔
          const k=rsL.length; if(k>=2)items.push({r:"SYN",rs:4,k,d:k*(k-1)/2*1}); } }   // 2026-11-20 使用者「默契加成可以多一倍」：每組 0.5 → 1（2 人 1、3 人 3、4 人 6、5 人 10）
      // 同一路官方已定兩位以上只算最高分 ⇒ 沒算進去的也要列在小框（使用者 2026-11-21「為何 BRO 的轉會評分沒有 SeTab」）：掛在那一路的列底下（xs）；那一路完全沒有列就補一列不計分的
      for(const r of ["TOP","JNG","MID","BOT","SUP"]){ const cf=(t.r[r]||[]).filter(e=>!e.gone&&(e.new||e.rs||e.pm||e.tip||e.r||!expd(e))); if(cf.length<2)continue;   // 還在隊上或有消息的人都要看得到（DK 上路的升職傳聞 Jaehyuk、LYON 上路續留的 Castle）
        const its=items.filter(x=>x.r===r), shown=new Set(its.flatMap(x=>[x.nw,x.od,...(x.nws||[]).map(c=>c.n)]));
        const xs=cf.filter(e=>!shown.has(pn(e.n))).map(e=>({n:pn(e.n),v:scOf.get(e),e})).sort((a,b)=>b.v-a.v); if(!xs.length)continue;
        if(its.length)its[its.length-1].xs=xs; else{ const f=xs.shift(); items.push({r,rs:5,nw:f.n,ne:f.e,v:f.v,d:0,xs}); } }
      items.sort((a,b)=>(a.rs===4)-(b.rs===4));   // 補上去的列排在默契加成前面
      items.forEach(x=>{ if(x.dlo==null){ x.dlo=x.d; x.dhi=x.d; } });   // 主教練那一筆沒有範圍
      // plN＝五路裡「有人可以算分」的有幾路：0＝全隊沒有任何人留下（CFO、LEV：五路都已宣布離隊、也沒有新人或傳聞），五路全用基準分加起來的數字沒有意義
      //   ⇒ 選手評分顯示「–」、排序排最後（使用者 2026-11-21「全隊沒有任何人留下的戰隊 選手評分應該顯示 -」）
      return {pl:plSum,plL,plN:plL.filter(x=>x.ps.length).length,items,sum:items.reduce((s,x)=>s+x.d,0),lo:items.reduce((s,x)=>s+x.dlo,0),hi:items.reduce((s,x)=>s+x.dhi,0),rng:items.some(x=>x.dhi-x.dlo>0.05),rm:items.some(x=>x.rm),vac:items.filter(x=>x.ma===2).length}; };
    // 評分小框（使用者 2026-11-19「評分的小框重新設計」）：標題列＝隊徽＋隊名＋總分；每條路一列＝路線圖示｜離隊（名字／分數）→ 加入｜增減色塊
    // 範圍的寫法與顏色：最低～最高；兩頭都正＝紅、都負＝綠、一正一負看中間值
    // 加減號與括號用全形（使用者 2026-11-20「加減號用全型 括號也是」）；四捨五入後是 0.0 的不帶符號
    const rSg=v=>{ const t=Math.abs(v).toFixed(1); return (t==="0.0"?"":v>0?"＋":"－")+t; }, rtx=(lo,hi)=>hi-lo>0.05?`${rSg(lo)} ～ ${rSg(hi)}`:rSg((lo+hi)/2), rcls=(lo,hi)=>{ const m=lo>0?1:hi<0?-1:(lo+hi)/2; return m>0?"tbUp":m<0?"tbDn":""; };
    // 戰績評分模式的小框＝第三賽段的成績數據（使用者 2026-11-21）：成績、場數、勝敗、勝率
    const s3Tip=t=>{ const k=teamFix(String(tAb(t.nm)||t.nm)), d=RATE&&RATE.s3?(RATE.s3[k]||RATE.s3[teamFix(String(tAb(t.tm)||t.tm))]):null;
      let h=`<div class="rtBox rtS3"><div class="rtHd">${teamLogoHTML(tAb(t.nm),22,true,t.nm)||""}<b>${esc(rowNm(t))}</b></div><div class="tpKv">`
        +`<span>${en2?"Split 3":"第三賽段"}</span><span>${t.rkL?RK3(t.rkL):RK3(/^W/.test(t.rk||"")?"":t.rk,t)}</span>`
        +(/^W/.test(t.rk||"")?`<span>${en2?"Worlds":"世界賽"}</span><span>${RK3(t.rk).replace(/^(世界賽|Worlds) ?/,"")}</span>`:"");
      if(d){ const w=Math.round(d.g*d.wr); h+=`<span>${en2?"Games":"場數"}</span><span>${d.g}</span><span>${en2?"W–L":"勝敗"}</span><span>${w} ${en2?"W":"勝"} ${d.g-w} ${en2?"L":"敗"}</span><span>${en2?"Win rate":"勝率"}</span><span>${(d.wr*100).toFixed(1)}%</span>`; }
      else h+=`<span>${en2?"Games":"場數"}</span><span class="tbMuted">${en2?"no data":"無資料"}</span>`;
      TIPS.push(h+`</div></div>`); return TIPS.length-1; };
    const rateTip=t=>{ const rt=rateOf(t), sg=rSg, cls=v=>v>0?"tbUp":v<0?"tbDn":"";
      // 選手評分模式（排序鈕切到選手評分）：小框列每一路的選手分數與這一路採計的分數，不含續約／續留／默契這些獎勵分
      //   （使用者 2026-11-20「選手評分模式 就不給獎勵分」；獎勵分只屬於轉會評分）
      if(rt&&typeof SPL!=="undefined"&&SPL){
        // 右邊不重複寫這一路的分數，改寫每個人的「去年評分」（同路百分位那一塊）與「成就加分」（國際賽資歷）；名字下面＝兩者相加（使用者 2026-11-20）
        let h=`<div class="rtBox"><div class="rtHd">${teamLogoHTML(tAb(t.nm),22,true,t.nm)||""}<b>${esc(rowNm(t))}</b><b class="rtSum${rt.plN?"":" tbMuted"}">${rt.plN?rt.pl.toFixed(1):"–"}</b></div>`
          +`<div class="rtPlG"><span></span><span class="rtCh">${en2?"Player":"選手"}</span><span class="rtCh rtChD">${en2?"Last season":"去年評分"}</span><span class="rtCh rtChD">${en2?"Honors":"成就加分"}</span>`;
        rt.plL.forEach(x=>{ const ic=`<span class="rtIc" title="${BLN[x.r]}">${POS_IMG[x.r]?`<img src="${POS_IMG[x.r]}" alt="">`:""}</span>`;
          if(!x.ps.length){ h+=ic+`<span class="rtP"><span class="rtN"><b class="tbMuted">${en2?"Vacant":"空缺"}</b></span><span class="rtV">${rt.plN?x.v.toFixed(1):"–"}</span></span><span class="rtPv">–</span><span class="rtPv">–</span>`; return; }
          x.ps.forEach((p,i)=>{ h+=(i?`<span></span>`:ic)+`<span class="rtP"><span class="rtN"><b class="tbN ${tbCls(p.e)}">${esc(p.n)}</b></span><span class="rtV">${p.v.toFixed(1)}</span></span>`   // 名字一律照陣容表的顏色；同路已確認兩人只算最高分 ⇒ 沒算進去的那位把「數字」調淡，不動名字（使用者 2026-11-21「SeTab 不是正常的紅字」）
            +`<span class="rtPv"${x.best&&i?` style="opacity:.45"`:""}>${(p.v-p.it).toFixed(1)}</span><span class="rtPv${p.it>0?" tbUp":""}"${x.best&&i?` style="opacity:.45"`:""}>${p.it>0?"＋"+(+p.it.toFixed(1)):"–"}</span>`; }); });
        TIPS.push(h+`</div></div>`); return TIPS.length-1; }
      const has=rt&&rt.items.length;
      let h=`<div class="rtBox"><div class="rtHd">${teamLogoHTML(tAb(t.nm),22,true,t.nm)||""}<b>${esc(rowNm(t))}</b>`
        +(has?`<b class="rtSum ${rt.rng?"rtSumR ":""}${rcls(rt.lo,rt.hi)}">${rt.rm?"（":""}${rtx(rt.lo,rt.hi)}${rt.rm?`<i class="rtPc">）</i>`:""}</b>`:"")+`</div>`;
      if(!RATE)h+=`<div class="rtEmpty">${en2?`Switch the year to ${SEASON} to compute`:`年份切到 ${SEASON} 才會計算`}</div>`;
      else if(!has)h+=`<div class="rtEmpty">${en2?"No lineup change to compare yet":"這隊還沒有可比較的異動"}</div>`;
      else{ // 不貼「傳聞」標籤，原選手與新選手都照陣容表同一套顏色標示狀態（使用者 2026-11-20「小框不用加上傳聞標籤 就原選手跟新選手的狀態 用顏色標示即可」）：
        //   黃＝傳聞、紅＝新加入、綠＝可能轉會、藍＝合約到期、藍字刪除線＝已離隊；上一位（已經不在格子裡的）＝已離隊
        const stC=o=>!o?"":o.prevE?((o.prevE.still&&!o.prevE.ret)?"tbExp":"tbExp tbGone"):tbCls(o);
        const pc=(n,v,o)=>`<span class="rtP"><span class="rtN"><b class="tbN ${stC(o)}">${esc(n)}</b></span>`
          +`<span class="rtV">${v.toFixed(1)}</span></span>`;   // 分數下面不寫「全年／中位數」註記（使用者 2026-11-20），算法在 ℹ️ 說明
        h+=`<div class="rtGrid"><span></span><span class="rtCh">${en2?"Previous":"原隊"}</span><span></span><span class="rtCh">${en2?"In":"加入"}</span><span class="rtCh rtChD">${en2?"Change":"增減"}</span>`;
        rt.items.forEach(x=>{ const ic=x.r==="COACH"?`<img src="img/COACH.png" alt="">`:(POS_IMG[x.r]?`<img src="${POS_IMG[x.r]}" alt="">`:"");
          if(x.rs===4){ h+=`<span class="rtIc"></span><span class="rtP" style="grid-column:2/5;align-self:start"><span class="rtN"><b>${en2?"Synergy":"默契加成"}</b><i class="rtRsL">${en2?`${x.k} players kept`:`${x.k} 位選手留隊`}</i></span></span><b class="rtD ${cls(x.d)}">${sg(x.d)}</b>`; return; }
          const xsH=col=>(x.xs||[]).map(c=>`<span></span><span class="rtP rtXs" style="grid-column:${col}"><span class="rtN"><b class="tbN ${tbCls(c.e)}">${esc(c.n)}</b></span>${c.v!=null&&c.v>=0?`<span class="rtV" style="opacity:.45">${c.v.toFixed(1)}</span>`:""}</span><span></span>`).join("");   // 沒算進去的：名字照原色、分數調淡
          if(x.rs){ h+=`<span class="rtIc" title="${BLN[x.r]||""}">${ic}</span><span class="rtP" style="grid-column:2/5"><span class="rtN"><b class="tbN ${tbCls(x.ne)}">${esc(x.nw)}</b></span>${x.v!=null&&x.v>=0?`<span class="rtV">${x.v.toFixed(1)}</span>`:""}</span>${x.rs===5?`<b class="rtD">–</b>`:`<b class="rtD ${cls(x.d)}">${sg(x.d)}</b>`}`+xsH("2/5"); return; }
          const tp=x.nws?" rtTop":"";   // 多人：路線圖、原本那位、箭頭都對齊第一位（分數最高的），其他人往下列（使用者 2026-11-20「小框的箭頭都指向第一位分數最高的 接著往下列」）
          h+=`<span class="rtIc${tp}" title="${BLN[x.r]}">${ic}</span>${x.nws?pc(x.od,x.b,x.oe).replace('class="rtP"','class="rtP rtTop"'):pc(x.od,x.b,x.oe)}<span class="rtAr${tp}">➜</span>${x.nws?`<span class="rtMulti">${x.nws.map(c=>pc(c.n,c.v,c.e)+`<b class="rtD ${cls(c.v-x.b)}">${sg(c.v-x.b)}</b>`).join("")}</span>`:pc(x.nw,x.a,x.ne)+`<b class="rtD ${cls(x.d)}">${sg(x.d)}</b>`}`+xsH("4/5").replace(/<span><\/span><span class="rtP rtXs"/g,'<span></span><span></span><span></span><span class="rtP rtXs"'); });   // 多位傳聞人選：每一位各自一個增減（使用者 2026-11-20「小框 多人的增減分分開列」），總分仍是最低 ～ 最高
        h+=`</div>`; }   // 計算說明不放小框，寫在 ℹ️ 說明（使用者 2026-11-20）
      TIPS.push(h+`</div>`); return TIPS.length-1; };
    if(RATE)board.forEach(t=>{ if(!t.fa)rateOf(t); });   // 先跑一遍：格子裡的人要在畫之前就排好
    const rateCell=t=>{ const rt=rateOf(t), v=rt&&rt.items.length?rt.sum:null;
      // 最後一欄的寬度不隨排序模式變（使用者 2026-11-21「最後一欄的寬度都幫我固定 以轉會評分的寬度為主」）：選手評分／戰績評分模式也塞一行看不見的轉會評分字串把欄寬撐成一樣
      const szr=`<span class="tbRtSz" aria-hidden="true">${v==null?"–":`${rt.rm?"（":""}${rtx(rt.lo,rt.hi)}${rt.rm?"）":""}`}</span>`;
      if(SRT0==="o")return `<div class="tbCell tbRate" data-r="RATE" data-lb="${en2?"Split 3":"第三賽段"}" data-tb="${t.fa?rateTip(t):s3Tip(t)}"><span class="tbCv">${t.fa||RK3(t.rk,t)==="–"?`<span class="tbMuted">–</span>`:`<b>${esc(RK3(t.rk,t))}</b>`}</span>${szr}</div>`;   // 戰績評分模式：這欄寫今年成績（使用者 2026-11-21「戰績評分時 改寫今年成績」）
      if(SPL)return `<div class="tbCell tbRate" data-r="RATE" data-lb="${SLB}" data-tb="${rateTip(t)}"><span class="tbCv">${rt&&rt.plN?`<b>${rt.pl.toFixed(1)}</b>`:`<span class="tbMuted">–</span>`}</span>${szr}</div>`;   // 照選手評分排序時，這欄顯示五路選手分數加總
      return `<div class="tbCell tbRate" data-r="RATE" data-lb="${en2?"Rating":"評分"}"${v!=null&&rt.rng?` data-avg="${(()=>{ const m=rt.items.reduce((z,x)=>z+(x.nws?x.nws.reduce((q,c)=>q+c.v,0)/x.nws.length-x.b:x.d),0); return rSg(m)+"|"+(m>0?"tbUp":m<0?"tbDn":""); })()}"`:""} data-tb="${rateTip(t)}"><span class="tbCv">${v==null?`<span class="tbMuted">–</span>`:`<b class="${rcls(rt.lo,rt.hi)}${rt.rng?" rtRngT":""}">${rt.rm?"（":""}${rtx(rt.lo,rt.hi)}${rt.rm?`<i class="rtPc">）</i>`:""}</b>`}</span></div>`; };   // 全形「）」的字框右半邊是空的 ⇒ 用負邊距收掉，看起來才跟沒括號的數字一樣貼齊右邊（使用者 2026-11-20「注意是視覺上空格一致 全型括號右邊的空格會比較大 要修正」）
    // 顏色（使用者 2026-11-19，取代星號）：黃＝傳聞未確定、紅＝新加入、藍＝合約已到期但還沒宣布離隊（Doran）、粉＝本轉會期續約（使用者 2026-11-19「粉色 跟紅色相近」）、白＝留隊
    // 藍字刪除線＝已宣布離隊、這個位置還沒有新簽約也沒有傳聞（使用者 2026-11-19）
    const tbCls=e=>e.fa?(e.ret?"tbRet":e.ro?"tbY":"tbExp"):e.gone?"tbExp tbGone":e.r?"tbY":e.pm?"tbPm":(e.new||(e.tip&&!e.r))?"tbNew":roOn(e)?"tbOut":e.rs?"tbRs":(expd(e)?(e.ro?"tbOut":"tbExp"):"tbStay");   // tbStay＝合約還在、沒有任何動向（白字「續留」，使用者 2026-11-20）   // 合約到期沒宣布、但傳出去別隊（LØS Zest）也畫刪除線（使用者 2026-11-20）   // rs＝本轉會期有官方續約消息（GCD 還沒更新也算）⇒ 粉字
    // 圖例篩選＝三組，一框一顆按鈕、兩種一起篩（使用者 2026-11-20「一個框的意思是點擊也會一起點，不用分開點」）
    const TBG={add:["tbNew","tbRs","tbPm","tbStay"],out:["tbExp","tbGone"],rum:["tbOut","tbY","tbRet"]};
    const F_TB=new Set([...mset("tbF")].filter(g=>TBG[g]));   // 可複選；舊存檔的單一類別值不認
    const tbMf=e=>{ const c=tbCls(e).split(" "); return [...F_TB].some(g=>TBG[g].some(k=>c.includes(k))); };
    let vRows=bRows.filter(t=>(!F_TB.size||Object.values(t.r).flat().some(tbMf)));
    // 轉會評分升降冪（使用者 2026-11-20「轉會評分要可以升降冪」）：賽區順序不動，各賽區內照評分排；沒有評分的隊排最後。點欄名或篩選列的按鈕輪流 降冪 → 升冪 → 原順序
    // 排序按鈕兩種輪流：轉會評分（高到低）↔ 選手評分（高到低）；↺ 才回原順序。不畫箭頭
    const SRT0=({d:"d",a:"d",pd:"pd",pa:"pd",o:"o"})[V.tbSort]||"d",   /* 預設就照轉會評分排（使用者 2026-11-21「排序預設是 轉會評分」）*/   /* 2026-11-20 使用者「只有降的那兩個 然後降冪圖案也刪掉」：只剩 轉會評分降冪 ↔ 選手評分降冪；舊存檔的升冪當成降冪 */ SPL=SRT0[0]==="p", SRT=SRT0==="o"?"":SRT0.slice(-1), SLB=SPL?(en2?"Player rating":"選手評分"):(en2?"Transfer rating":"轉會評分"),
      SBT=SRT0==="o"?(en2?"Team record":"戰績評分"):SLB;   // 第三種「戰績評分」＝最一開始的預設順序（各賽區照去年戰績排；使用者 2026-11-21「排序多一個戰績評分 就是依照我一開始的那種排序」），評分欄照舊顯示轉會評分
    if(SRT){ const lgI={}; vRows.forEach(t=>{ if(!(t.lg in lgI))lgI[t.lg]=Object.keys(lgI).length; }); const rv=t=>{ const rt=rateOf(t); return SPL?(rt&&rt.plN?rt.pl:null):(rt&&rt.items.length?rt.sum:null); };
      vRows=vRows.map((t,i)=>[t,i,rv(t)]).sort((a,b)=>lgI[a[0].lg]-lgI[b[0].lg]||(a[2]==null)-(b[2]==null)||(SRT==="d"?b[2]-a[2]:a[2]-b[2])||a[1]-b[1]).map(x=>x[0]); }
    const srtArr="";   // 不畫箭頭，排序中靠按鈕亮起與欄名變金色表示
    const wkPg=p=>{ let s=String(p||""); try{ s=decodeURIComponent(s); }catch(_){} return s.replace(/ /g,"_"); };   // wiki 頁名：已編碼的先解開（Noah 連錯頁，使用者 2026-11-20）
    const nameH=e=>{ const n=esc(pn(e.n)), inner=bq&&hitE(e)?`<mark>${n}</mark>`:n;
      return `<span class="tbN ${tbCls(e)}${F_TB.size&&!tbMf(e)?" tbDim":""}">${inner}</span>`; };   // 陣容表的名字不做超連結，連結只放在小框裡的名字（使用者 2026-11-21）   // 沒頁名的傳聞人選（BrokenBlade、Zven…）退回 roles 查到的頁、再退回 ID 本身（使用者 2026-11-20 全面檢視）   // 格子不標教練職稱，只在小框顯示（使用者 2026-11-20）
    // 陣容到位打勾（使用者 2026-11-20「五路選手以及主教練都有新加入或續約了，一路有兩人有一個也可以，就在隊伍縮寫後面打個勾」）：
    //   每一格至少一人是官方新加入／官方續約；合約本來就還在（沒到期、沒傳出要走）的人也算確定
    const setE=e=>!e.r&&!e.gone&&!!(e.new||e.tip||e.rs||e.pm||(e.c&&e.c>=today&&!e.ro));
    const tbDone=t=>["TOP","JNG","MID","BOT","SUP","HC"].every(c=>colE(t,c).some(setE));
    // 一列的 HTML（抽成函式：截圖量版面時要替沒顯示在畫面上的聯賽也排一份，見 runShot）；data-o＝在整份資料裡的順序（＝第三賽段成績的順序）
    const rowH=t=>`<div class="tbRow${t.fa?" tbFA":""}" data-o="${s2Of(t)?9000+s2Of(t):(D.board||board).indexOf(t)}"${t.fa?"":` data-rk="${esc(rkS(t))}"`} style="--lgc:${LGC[t.lg]||"var(--gold)"}"><div class="tbTeam" title="${t.fa?"FA":esc(t.nm)}">${t.fa?`<img class="tbFaIc" src="${((window.TS_DATA||{}).lgi||{})[t.lg]||("img/lg_"+t.lg+".png")}" alt="">`:""}${teamLogoHTML(tAb(t.nm),26,true,t.nm)||teamLogoHTML(tAb(t.tm),26,true,t.tm)||""}<span>${t.fa?esc(rowNm(t)):`<a class="tbTmA" href="${tmWk(t.nm)}" target="_blank" rel="noopener">${esc(rowNm(t))}</a>`}</span>${tbDone(t)?`<span class="tbOk" title="${en2?"All five roles and the head coach are confirmed":"五路與主教練都確定了"}">✔</span>`:""}</div>`
        +COLS.map(r=>{ const es=t.fa?colE(t,r):colE(t,r).filter(e=>!e.gone);   /* 已宣布離隊的不留在陣容表格子裡，只列在 FA 那列（使用者 2026-11-21「所有已宣布離隊的都直接離開陣容表 去到FA區」）；小框仍查得到 */   /* FA 的主教練與後勤分兩格（使用者 2026-11-21 先要合併、隨後改回「主教練跟後勤分開」） */
          return `<div class="tbCell${es.length?"":" tbEmpty"}" data-r="${r}" data-lb="${BLN[r]}" data-tb="${cellTip(t,r)}"><span class="tbCv">${es.length?es.map((e,i)=>i<es.length-1?`<span class="tbNw">${nameH(e)}<span class="tbSep">/</span></span><wbr>`:nameH(e)).join(""):`<span class="tbMuted">–</span>`}</span></div>`; }).join("")
        // 手機版的 FA 卡：主教練與後勤併成一格（data-r="CO"，主教練排前面；小框也列全部）。電腦版這格不顯示、手機版改藏主教練與後勤那兩格（見 .tbFaCo 的樣式）
        +(t.fa?(()=>{ const es=colE(t,"CO"); return `<div class="tbCell tbFaCo${es.length?"":" tbEmpty"}" data-r="CO" data-lb="${BLN.CO}" data-tb="${cellTip(t,"CO")}"><span class="tbCv">${es.length?es.map((e,i)=>i<es.length-1?`<span class="tbNw">${nameH(e)}<span class="tbSep">/</span></span><wbr>`:nameH(e)).join(""):`<span class="tbMuted">–</span>`}</span></div>`; })():"")
        +rateCell(t)+`</div>`;
    let bHTML="", lastLg="";
    vRows.forEach(t=>{ if(t.lg!==lastLg){ const n=vRows.filter(x=>x.lg===t.lg&&!x.fa).length;
        bHTML+=`<div class="tbLg" data-rg="${esc((en2?{LCK:"Korea",LPL:"China",LEC:"EMEA",LCS:"North America",CBLOL:"Brazil",LCP:"Asia-Pacific"}:{LCK:"韓國",LPL:"中國",LEC:"歐洲",LCS:"北美",CBLOL:"巴西",LCP:"亞太"})[t.lg]||"")}" style="--lgc:${LGC[t.lg]||"var(--gold)"}"><img class="tbLgIc" src="${((window.TS_DATA||{}).lgi||{})[t.lg]||("img/lg_"+t.lg+".png")}" alt=""><b>${esc(t.lg)}</b><span>${n}${en2?" teams":" 隊"}</span></div>`; lastLg=t.lg; }   // 聯賽徽章＋聯賽名稱＋隊伍數（使用者 2026-11-21）；地區名只留在 data-rg 給截圖標題用
      bHTML+=rowH(t); });
    const bHead=`<div class="tbHd"><span></span>${COLS.map(r=>`<span>${(r==="HC"||r==="STF")?`<img class="trCoach" src="img/COACH.png" alt="">`:(POS_IMG[r]?`<img class="trRole" src="${POS_IMG[r]}" alt="">`:"")}${BLN[r]}</span>`).join("")}<span class="tbRateH tbSortT" style="cursor:pointer;white-space:nowrap" title="${en2?"Click to sort":"點一下照評分排序"}">${SRT0==="o"?(en2?"Split 3":"第三賽段"):SLB}${srtArr}</span></div>`;
    // 篩選列（使用者 2026-11-20「消息跟轉會表的篩選列也統一一下 並且直觀一點」）：兩種模式同一個順序——
    //   模式（圖示＋文字）｜賽區（聯賽色）｜該模式自己的篩選（分組、組間直線）｜……｜更新時間＋搜尋（最右）
    const FG=(lb,inner,cls)=>`<span class="trFG${cls?" "+cls:""}">${lb?`<label>${lb}</label>`:""}${inner}</span>`;
    const lgTx=r=>{ const l=rgNm(r); return `<span style="color:${LGC[l]||"inherit"};font-weight:800">${esc(l)}</span>`; };
    const modeBtns=FG("",btns("trMode",[["",`📋 ${en2?"Rosters":"陣容表"}`],["news",`<span class="trNIcW"><img class="trNIc" src="${(window.TS_DATA||{}).nic||"img/news_faker.png"}" alt="" onerror="this.parentNode.textContent='📰'"></span> ${en2?"News":"消息"}`]]));   // 消息的小圖＝使用者給的 Faker 比噓圖（img/news_faker.png，正方形）；檔案不在就退回 📰
    // 複選按鈕：沒有「全部」，點了亮、再點取消，都沒亮＝全部
    const mbtns=(key,opts)=>{ const S=mset(key); return `<span style="display:inline-flex;gap:6px;flex-wrap:wrap">${opts.map(([v,l])=>`<button class="sqLaneBtn${S.has(v)?" on":""}" data-mk="${key}" data-v="${esc(v)}">${l}</button>`).join("")}</span>`; };
    const rgBtns=FG(en2?"League":"賽區",mbtns("trRg",RGS.map(r=>[r,lgTx(r)])));
    const newsBtns=FG(en2?"Status":"狀態",mbtns("trSt",[["official",ST.official],["rumor",`<b class="tbY">${ST.rumor}</b>`],["conf",`<b class="trCf">${ST.conf}</b>`],["fake",`<b class="trFk">${ST.fake}</b>`]]),"fgSt")
      /* 類型（加入／離開／其他）那組按鈕已刪（使用者 2026-11-20） */
      /* 來源（公告／SE／PTT／韓網）那組篩選已刪（使用者 2026-11-20） */;
    const boardBtns=FG(en2?"Show":"顯示",`<span class="tbLegend">${[["add",[["tbNew",en2?"New signing":"新加入",en2?"New":"加入"],["tbRs",en2?"Re-signed & promoted":"續約升職",en2?"Re-sign & promo":""],["tbStay",en2?"Staying":"續留",en2?"Stay":""]]],["out",[["tbExp",en2?"Contract expired":"合約到期未宣布",en2?"Expired":"合約到期"]]],["rum",[["tbOut",en2?"Possible move":"可能轉會",en2?"Maybe":""],["tbY",en2?"Rumor":"傳聞"],["tbRet",en2?"Retired":"退役"]]]]
        .map(([g,L])=>`<button class="sqLaneBtn tbLgB${F_TB.has(g)?" on":""}" data-mk="tbF" data-v="${g}" title="${en2?"Show these (multi-select, click again to clear)":"只看這幾種（可複選，再點一次取消）"}">${L.map(([c,l,sh])=>`<b class="tbN ${c==="tbGone"?"tbExp tbGone":c}" data-s="${sh||l}">${l}</b>`).join(`<i class="tbLgSep">／</i>`)}</button>`).join("")}`
      +`</span>`)   // 「只看有異動」已刪（使用者 2026-11-20；休賽期幾乎每隊都有異動，沒作用）
      +FG(en2?"Sort":"排序",`<span><button class="sqLaneBtn tbSortT on" title="${en2?"Cycle: transfer rating, player rating, team record":"輪流切換：轉會評分 → 選手評分 → 戰績評分"}">${SBT}</button></span>`,"fgSort");
    // 粉專：電腦（網頁版）用粉專網址，手機用分享連結（會直接開 App）（使用者 2026-11-21「臉書按鈕的網址 網頁版改成 https://www.facebook.com/yuwanxd」）
    const TR_FB=(matchMedia("(hover:none)").matches||innerWidth<760)?"https://www.facebook.com/share/1EwfwfRyCF/":"https://www.facebook.com/yuwanxd";
    const metaTx=MODE==="news"?`${shown.length} / ${all.length}${D.at?`・${en2?"updated":"更新"} ${esc(D.at)}`:""}`:(D.at?`${en2?"as of":"截至"} ${esc(D.at)}`:"");
    main.innerHTML=`<div class="filters trBar">`+modeBtns+rgBtns+(MODE==="news"?newsBtns:boardBtns)
      // 搜尋放最右邊（使用者 2026-11-20「篩選列重新調整一下 搜尋應該在最右邊」）
      +`<span style="flex:1"></span><span class="meta">${metaTx}</span>`
      +`<span class="trSW"><label>${en2?"Search":"搜尋"}</label><span class="cwrap"><input type="text" id="trQ" value="${esc(V.trQ||"")}" placeholder="${en2?"Player / team":"選手或隊名"}" style="width:190px;padding-right:26px"><button class="cx" tabindex="-1" data-x="trQ" title="一鍵清除">✕</button></span></span>`
      // 分享（使用者 2026-11-21）：同一套截圖，開小視窗看圖、下載；點開小圖自動複製（原本的三顆平台按鈕已依使用者要求刪除）
      //   order：主站的 orderBaseBtns 會把行內 order≥1 的照數字搬到基礎按鈕（📸 ℹ️ ↺ ←）左邊 ⇒ 給 2，排在 FB／Discord 之後、緊貼 📸；
      //   轉會網站（有 TS_DATA）沒有那套搬動，照 DOM 順序排 ⇒ 給 1，接在 📸 後面
      +`<button id="trShare" class="sqbtn" style="order:${window.TS_DATA?1:2}" title="${en2?"Screenshots: download or copy":"截圖：下載或複製"}"><svg class="trShIc" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" shape-rendering="geometricPrecision" aria-hidden="true"><path d="M21 4H3l6.5 6.5L12 20z"/><path d="M21 4 9.5 10.5"/></svg></button>`   /* 紙飛機＝社群 App 的「分享」圖示（使用者 2026-11-21「分享的按鈕圖 要跟 IG 分享的那圖案一樣」）；轉會網站會換成自己那套線條圖示的同一個形狀。
           同一天再要求「小按鈕裡面的圖示要置中 然後要圓潤化清晰化 不要看起來很粗糙」：線加粗（2.3）、圓角接頭，圖案的外框正好在 24 格的正中間，尺寸用偶數（22px）才不會落在半個像素上 */
      // Facebook 粉專（使用者 2026-11-20「多一個FB按鈕 連接到我的粉專」）：網址填在 TR_FB，空的時候不畫這顆
      +(TR_FB?`<a id="trFb" class="sqbtn" style="order:1;text-decoration:none;background:#1877F2;border:1px solid #4a95f5;box-shadow:0 1px 0 rgba(0,0,0,.35);box-sizing:border-box;border-radius:9px;cursor:pointer" href="${esc(TR_FB)}" target="_blank" rel="noopener" title="${en2?"My Facebook page":"我的 Facebook 粉專"}"><svg viewBox="0 0 24 24" width="20" height="20" fill="#fff" aria-hidden="true" class="trFbG"><path d="M9.101 23.691v-7.98H6.627v-3.667h2.474v-1.58c0-4.085 1.848-5.978 5.858-5.978.401 0 .955.042 1.468.103a8.68 8.68 0 0 1 1.141.195v3.325a8.623 8.623 0 0 0-.653-.036 26.805 26.805 0 0 0-.733-.009c-.707 0-1.259.096-1.675.309a1.686 1.686 0 0 0-.679.622c-.258.42-.374.995-.374 1.752v1.297h3.919l-.386 2.103-.287 1.564h-3.246v8.245C19.396 23.238 24 18.179 24 12.044c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.628 3.874 10.35 9.101 11.647Z"/></svg></a>`:"")
      // Discord（使用者 2026-11-20「如果有任何新的轉會通知 可以到我的 DC 群告訴我…也新增一個 DC 按鈕在外面」）
      +`<a id="trDc" class="sqbtn" style="order:1;text-decoration:none;background:#5865F2;border:1px solid #7983f5;box-shadow:0 1px 0 rgba(0,0,0,.35);box-sizing:border-box;border-radius:9px;cursor:pointer" href="https://discord.gg/ffJvcswnkC" target="_blank" rel="noopener" title="${en2?"Have transfer news? Tell me on Discord":"有新的轉會消息？到 Discord 群告訴我"}"><svg viewBox="0 0 24 24" width="20" height="20" fill="#fff" aria-hidden="true"><path d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189Z"/></svg></a>`+`</div>`
      +(MODE==="news"?`<div class="card trList">${head}${rows||`<span class="sumEmpty">${en2?"No results":"沒有符合的消息"}</span>`}</div>`
        :`<div class="card tbBoard">${vRows.length?bHead+bHTML:`<span class="sumEmpty">${en2?"No results":"沒有符合的隊伍或選手"}</span>`}</div>`);
    // 篩選列放不下的時候（視窗變窄、瀏覽器放大到 110%～150%）：flex 換行是一顆一顆掉下去的——110% 時只剩 Facebook／Discord 兩顆掉到下一排最左邊，
    //   125% 時搜尋與五顆小按鈕掉下去卻靠左（前面那個 flex:1 的空白留在上一排尾端）；看起來就是「跑掉歪掉」（使用者 2026-11-21「縮放網頁比例後 篩選列會跑掉歪掉」）。
    //   ⇒ 右邊那一組（更新時間、搜尋、小按鈕）被拆開的時候，在它前面強制換行，整組一起到下一排、照舊靠右；沒被拆開就不換。
    //   手機版面（搜尋那組是 display:contents，另有自己的排法）不處理。寬度變了重算（ResizeObserver 只看寬度，避免自己改高度又觸發自己）
    { const bar=main.querySelector(".filters.trBar"), sw=bar&&bar.querySelector(".trSW");
      const fitBar=()=>{ if(!bar||!bar.isConnected||!sw)return; let brk=bar.querySelector(".trBrk");
        if(!brk){ brk=document.createElement("i"); brk.className="trBrk"; brk.style.cssText="flex:0 0 100%;height:0;margin:0;padding:0;border:0;display:none";
          const sp=[...bar.children].find(x=>x.tagName==="SPAN"&&/flex:\s*1/.test(x.getAttribute("style")||"")); bar.insertBefore(brk,sp||sw); }
        const was=brk.style.display; brk.style.display="none"; for(let n=brk.nextElementSibling;n;n=n.nextElementSibling)n.style.marginTop="";
        if(getComputedStyle(sw).display!=="contents"){
          // 只有右邊那一組（更新時間、搜尋、小按鈕）自己被拆成兩排時才強制換行；整組還在同一排（跟被擠下來的「排序」同一排也算）就不動，免得多佔一排
          const grp=[...bar.children].filter(x=>x!==brk&&x.offsetWidth>0&&x.offsetHeight>0&&(x===sw||x.classList.contains("sqbtn")||x.classList.contains("meta"))), cy=x=>x.offsetTop+x.offsetHeight/2, c0=grp.length?cy(grp[0]):0;
          if(grp.some(x=>Math.abs(cy(x)-c0)>12)){ brk.style.display="block";
            // 換行用的那個 0 高度元素自己佔一排，上下各多一段列距 ⇒ 後面那一組往上收一段列距，兩排之間才是正常的一段
            const g=parseFloat(getComputedStyle(bar).rowGap)||0; if(g)for(let n=brk.nextElementSibling;n;n=n.nextElementSibling)n.style.marginTop=(-g)+"px"; } }
        if(brk.style.display!==was&&typeof window._tsStick==="function")window._tsStick(); };   // 獨立站：篩選列的高度變了，黏頂的位移要重量
      fitBar(); if(document.fonts&&document.fonts.ready)document.fonts.ready.then(fitBar);
      try{ if(window._trBarRO)window._trBarRO.disconnect(); if(bar&&window.ResizeObserver){ let w0=-1; window._trBarRO=new ResizeObserver(es=>{ const w=Math.round(es[0].contentRect.width); if(w===w0)return; w0=w; fitBar(); }); window._trBarRO.observe(bar); } }catch(_){} }
    // 📸 截圖（使用者 2026-11-20「新增截圖按鈕」「截圖要跟大家說明文字顏色代表什麼」「截圖大小為 2000x2000」「如果有好幾個賽區 就是一個賽區一張圖」）：
    //   陣容表＝一個賽區一張；每隊一張卡（沿用手機版卡片：每格自己是 @container mainc），欄數挑「縮放後最大」的那個，整張等比縮放置中進 2000×2000。
    //   消息＝照列的邊界分頁，每頁 2000×2000。每張頂端都有標題＋截至時間，陣容表多一行顏色說明。主站與轉會網站共用這一段（不靠 shotEl）
    { const sb=document.getElementById("trShot");
      // runShot(sink)：sink＝null 照舊一張一張下載（📸）；給 sink 就不下載，把每張圖交給 sink.add（📤 分享用）
      const runShot=async sink=>{ if(sb)sb.disabled=true; const SZ=2000, hosts=[]; let rootZ=null;
        const fixC=root=>{ const P=["color","backgroundColor","backgroundImage","borderTopColor","borderRightColor","borderBottomColor","borderLeftColor","outlineColor","textDecorationColor","boxShadow"];   // html2canvas 不認 color-mix 算出來的 color(srgb …)
          const cv=x=>x.replace(/color[(]srgb ([0-9.e-]+) ([0-9.e-]+) ([0-9.e-]+)(?: [/] ([0-9.e-]+))?[)]/g,(m,r,g,b,a)=>`rgba(${Math.round(r*255)},${Math.round(g*255)},${Math.round(b*255)},${a==null?1:a})`);
          [root,...root.querySelectorAll("*")].forEach(el=>{ const cs=getComputedStyle(el); P.forEach(p=>{ const v=cs[p]; if(v&&v.includes("color("))el.style[p]=cv(v); }); }); };
        // 圖片一律先換成 data URI 再畫（使用者 2026-11-20 回報「Tainted canvases may not be exported」）：轉會網站的隊徽、路線圖在主站網域，
        //   瀏覽器快取裡沒帶 CORS 的那份一畫上去畫布就被鎖 ⇒ 自己 fetch 成 data URI（失敗再強制重抓一次；file:// 退回主站的 IMG_B64 包；都不行就藏起來）。
        //   卡片的路線圖原本是 ::before 背景圖（html2canvas 會自己去抓、一樣會鎖）⇒ 截圖複本改放真的 <img>
        const D64=window._tbD64||(window._tbD64=new Map());
        const dataOf=async(u,raw)=>{ if(/^data:/i.test(u))return u; if(D64.has(u))return D64.get(u); let v=null;
          for(const c of ["default","reload"]){ try{ const r=await fetch(u,{mode:"cors",cache:c}); if(r.ok){ const bl=await r.blob(); v=await new Promise(ok=>{ const fr=new FileReader(); fr.onload=()=>ok(fr.result); fr.onerror=()=>ok(null); fr.readAsDataURL(bl); }); if(v)break; } }catch(_){} }
          if(!v&&typeof _loadImgB64==="function"){ try{ await _loadImgB64(); v=(window.IMG_B64||{})[String(raw||"").replace(/^[.][/]/,"").split("?")[0]]||null; }catch(_){} }
          D64.set(u,v); return v; };
        const LIC={TOP:"img/TOP.png",JNG:"img/JG.png",MID:"img/MID.png",BOT:"img/BOT.png",SUP:"img/SUP.png",HC:"img/COACH.png",STF:"img/COACH.png"};
        const warm=async root=>{ if(!root.dataset.noic)root.querySelectorAll(".tbCell[data-r]").forEach(c=>{ const f=LIC[c.dataset.r]; if(f)c.insertAdjacentHTML("afterbegin",`<img class="tbShIc" src="${f}" alt="" style="flex:0 0 15px;width:15px;height:15px;margin-top:2px">`); });
          await Promise.all([...root.querySelectorAll("img")].map(async im=>{ const d=await dataOf(im.src,im.getAttribute("src")); im.removeAttribute("loading"); im.removeAttribute("crossorigin"); im.onerror=null;
            if(d){ im.src=d; try{ await im.decode(); }catch(_){} } else im.style.visibility="hidden"; })); };
        // mid＝標題列中間那一段（陣容表放顏色說明）：標題、賽區、顏色說明、資料時間併成一列，把高度讓給資料
        //   （使用者 2026-11-21「為了讓截圖資料的部分更大一些 上面標籤與日期那塊 可以合併寫成一列嗎」）
        // 複本裡的欄名列一律透明、不要陰影：獨立站為了讓欄名列黏在上方，給它不透明底色與一條往上蓋的陰影（選擇器比行內樣式弱，但只要誰加了 !important 就會蓋過複本的行內 background:none），畫在截圖的資料框上就是一塊顏色不一樣的色塊（2026-11-21 實際發生過）⇒ 這裡用更高的權重一次擋掉
        const mkHost=(w,sub,mid)=>{ const h=document.createElement("div"); h.setAttribute("data-tshot","1"); h.style.cssText=`position:fixed;left:-99999px;top:0;width:${w}px;padding:22px;box-sizing:border-box;background:#0b0e14;color:#e8ecf4`;
          h.innerHTML=`<style>[data-tshot] .tbCell::before{content:none!important}[data-tshot] .trHead,[data-tshot] .tbHd,[data-tshot] .trDay{position:static!important;top:auto!important}[data-tshot] .tbBoard>.tbHd,[data-tshot] .trList>.trHead{background:none!important;box-shadow:none!important}</style><div class="trShHdRow" style="display:flex;align-items:center;gap:12px;margin:0 2px 10px;white-space:nowrap${mid?";line-height:1.2":""}"><b style="font-size:24px;color:#f0e6d2">${en2?"2027 Season Transfers":"S17 轉會整理"}</b>${sub}${mid||""}<span style="margin-left:auto;font-size:14px;color:#8b98ad">${D.at?(en2?"as of ":"截至 ")+esc(D.at):""}</span></div>`;
          document.body.appendChild(h); hosts.push(h); return h; };
        // 「水平」＝每一塊看得見的部分（墨水）中心在同一條線上（使用者 2026-11-21 貼圖「這部分還是沒有水平」「截圖的隊徽與隊名感覺沒有水平」）：
        //   之前先是照文字框置中（中文字的墨水比框中心低、英文大寫比框中心高），後來改對齊基線（大字的中心又比小字高 2～6px），兩種都不是眼睛看到的水平。
        //   inkOf＝這串字實際畫出來的上下緣：基線位置（塞一個 0 大小的行內塊量）＋canvas 量這串字在這個字型下高出、低於基線多少
        const inkOf=el=>{ try{ if(!el)return null; const tx=(el.textContent||"").trim(); if(!tx)return null; const g=getComputedStyle(el), cx=inkOf._c||(inkOf._c=document.createElement("canvas").getContext("2d"));
            const pr=document.createElement("i"); pr.style.cssText="display:inline-block;width:0;height:0;padding:0;margin:0;border:0;vertical-align:baseline"; el.insertBefore(pr,el.firstChild); const by=pr.getBoundingClientRect().bottom; pr.remove();
            cx.font=`${g.fontStyle} ${g.fontWeight} ${g.fontSize} ${g.fontFamily}`; const m=cx.measureText(tx); if(!(m.actualBoundingBoxAscent+m.actualBoundingBoxDescent>0))return null;
            return {top:by-m.actualBoundingBoxAscent,bot:by+m.actualBoundingBoxDescent}; }catch(_){ return null; } };
        const nudge=(el,d)=>{ if(!isFinite(d)||Math.abs(d)<0.05)return; el.style.position="relative"; el.style.top=((parseFloat(el.style.top)||0)+d).toFixed(2)+"px"; };
        // 最上面那一列：標題、賽區名、頁碼、時間各自把墨水中心移到這一列的中線；顏色說明框本身置中，框裡的字用同一個位移（彼此仍在同一條基線上）對到框的中心
        const level=row=>{ if(!row)return; const rc=row.getBoundingClientRect(), C=(rc.top+rc.bottom)/2;
          [...row.children].forEach(el=>{ if(el.classList.contains("trShHdLg")){ const br=el.getBoundingClientRect(), ks=[...el.children].map(inkOf).filter(Boolean); if(!ks.length)return;
                const d=(br.top+br.bottom)/2-(Math.min(...ks.map(k=>k.top))+Math.max(...ks.map(k=>k.bot)))/2; [...el.children].forEach(b=>nudge(b,d)); return; }
              const k=inkOf(el); if(k)nudge(el,C-(k.top+k.bot)/2); }); };
        // 資料框（陣容表）：不管哪個聯賽都畫在同一個位置、同一個大小（使用者 2026-11-21「截圖資料框 在不同聯賽切換看的時候 會感覺框框大小不一致」）
        //   原本框是內容的一部分，跟著內容縮放 ⇒ 各聯賽的下緣差 5～11px、右緣差 2px。現在框由這裡自己畫，內容只畫在框的內側
        //   m＝框離圖片左右下三邊；p＝框內留白（上右下左）。inner(top)＝框內可以放內容的範圍
        const FR={m:40,r:26,p:[10,26,24,26]};
        const inner=top=>({top,x:FR.m+FR.p[3],y:top+FR.p[0],w:SZ-2*FR.m-FR.p[1]-FR.p[3],h:SZ-top-FR.m-FR.p[0]-FR.p[2]});
        const rrect=(g,x,y,w,h,r)=>{ g.beginPath(); g.moveTo(x+r,y); g.lineTo(x+w-r,y); g.arcTo(x+w,y,x+w,y+r,r); g.lineTo(x+w,y+h-r); g.arcTo(x+w,y+h,x+w-r,y+h,r); g.lineTo(x+r,y+h); g.arcTo(x,y+h,x,y+h-r,r); g.lineTo(x,y+r); g.arcTo(x,y,x+r,y,r); g.closePath(); };
        // 文字的上下位置：html2canvas 畫字用的基線是它自己量的（1px 圖與文字的 offsetTop 相減再加 2，全是整數）⇒ 每種字級會比瀏覽器低 1～2px，
        //   字就不在列的正中間、也跟隊徽不在同一條線上（使用者 2026-11-21「資料要是在每一列的置中」）。
        //   做法：每種字級先用 html2canvas 畫一個測試字，量它實際畫在哪、跟瀏覽器差多少（DY），再把截圖複本裡的文字往上補回去（lift）
        const DY=new Map(), PX1="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";
        const capOf=(fam,fs)=>{ try{ const K=8, n=Math.ceil(fs*K*1.6), c=document.createElement("canvas"); c.width=c.height=n; const x=c.getContext("2d",{willReadFrequently:true}); x.font=`400 ${fs*K}px ${fam}`; x.textBaseline="alphabetic"; x.fillStyle="#fff"; const by=Math.round(n*0.8); x.fillText("H",Math.round(n*0.1),by);
            const d=x.getImageData(0,0,n,n).data; for(let y=0;y<n;y++)for(let X=0;X<n;X++)if(d[(y*n+X)*4+3]>128)return (by-y)/K; }catch(_){} return fs*0.7; };
        const calib=async keys=>{ if(!keys.length)return; let t=null;
          try{ const W=90, rows=keys.map(k=>{ const i=k.lastIndexOf("|"), fs=parseFloat(k.slice(i+1)); return {k,fam:k.slice(0,i),fs,h:Math.ceil(fs*3)}; }), H=rows.reduce((a,r)=>a+r.h,0);
            t=document.createElement("div"); t.setAttribute("data-tshot","1"); t.style.cssText=`position:fixed;left:-99999px;top:0;width:${W}px;background:#000;color:#fff;line-height:1.5;font-weight:400`;
            t.innerHTML=rows.map(r=>`<div style="height:${r.h}px;display:flex;align-items:center;justify-content:center;font-size:${r.fs}px;font-family:${r.fam.replace(/"/g,"'")}"><span>H</span></div>`).join("");
            document.body.appendChild(t); const t0=t.getBoundingClientRect().top;
            rows.forEach((r,i)=>{ const sp=t.children[i].firstChild, im=document.createElement("img"); im.src=PX1; im.style.cssText="width:1px;height:1px;margin:0;padding:0;vertical-align:baseline"; sp.appendChild(im); const base=im.getBoundingClientRect().bottom-t0; im.remove(); r.want=base-capOf(r.fam,r.fs)/2; });
            const Z=4, cv=await html2canvas(t,{backgroundColor:"#000",useCORS:true,scale:Z,width:W,height:H,windowWidth:Math.max(document.documentElement.scrollWidth,W)}), g=cv.getContext("2d",{willReadFrequently:true}); let y0=0;
            rows.forEach(r=>{ const hh=Math.round(r.h*Z), w=cv.width, d=g.getImageData(0,Math.round(y0*Z),w,hh).data; let a=-1, b=-1;
              for(let y=0;y<hh;y++){ let hit=false; for(let x=0;x<w;x++)if(d[(y*w+x)*4]>140){ hit=true; break; } if(hit){ if(a<0)a=y; b=y; } }
              DY.set(r.k,a>=0?Math.max(-4,Math.min(4,(y0+(a+b+1)/2/Z)-r.want)):0); y0+=r.h; });
          }catch(_){ keys.forEach(k=>{ if(!DY.has(k))DY.set(k,0); }); }
          if(t)t.remove(); };
        const lift=async root=>{ const todo=[], walk=el=>{ if(el.nodeType!==1||/^(IMG|STYLE|CANVAS|BR|SVG)$/i.test(el.tagName))return;
            const tx=[...el.childNodes].filter(n=>n.nodeType===3&&n.textContent.trim());
            if(tx.length&&!el.querySelector("img")){ todo.push(el); return; }
            tx.forEach(n=>{ const s=document.createElement("span"); s.textContent=n.textContent; el.replaceChild(s,n); });
            [...el.children].forEach(walk); };
          walk(root);
          const info=todo.map(el=>{ const cs=getComputedStyle(el); return {el,key:cs.fontFamily+"|"+(Math.round(parseFloat(cs.fontSize)*100)/100),pos:cs.position,top:parseFloat(cs.top)||0}; });
          await calib([...new Set(info.map(o=>o.key))].filter(k=>!DY.has(k)));
          info.forEach(o=>{ const dy=DY.get(o.key)||0; if(!dy)return; if(o.pos==="static")o.el.style.position="relative"; o.el.style.top=(o.top-dy)+"px"; }); };
        // 刪除線（已宣布離隊）：html2canvas 畫不出這條線（使用者 2026-11-20「截圖的刪除線消失」）⇒ 截圖複本改用 1.5px 的背景橫線自己畫
        const strike=root=>root.querySelectorAll(".tbN.tbGone").forEach(el=>{ const c=getComputedStyle(el).color; el.style.textDecoration="none"; if(!el.children.length){ el.style.position="relative"; el.style.display="inline-block"; el.insertAdjacentHTML("beforeend",`<i style="position:absolute;left:0;right:0;top:54%;height:1.5px;background:${c}"></i>`); return; }   /* 說明列那顆是純文字的 flex 子項，背景線畫不出來 ⇒ 疊一條絕對定位的線 */
          el.style.backgroundImage=`linear-gradient(${c},${c})`; el.style.backgroundRepeat="no-repeat"; el.style.backgroundSize="100% 1.5px"; el.style.backgroundPosition="0 56%"; });
        const out=async(h,name,head,IN)=>{ h.querySelectorAll(".trTx a,.tbN a").forEach(x=>x.style.textDecoration="none"); await warm(h); fixC(h); strike(h); if(head)strike(head);
          await lift(h); if(head)await lift(head);
          // head＝頂端那塊（標題、截至時間、文字顏色）：不管哪個聯賽都固定畫滿 2000 寬（使用者 2026-11-20「截圖上面那塊 無論哪個聯賽都固定滿版」），內容縮放後放在它下面置中
          let hc=null; if(head){ await warm(head); fixC(head); const hw=head.offsetWidth; hc=await html2canvas(head,{backgroundColor:"#0b0e14",useCORS:true,scale:SZ/hw,width:hw,height:head.offsetHeight,windowWidth:Math.max(document.documentElement.scrollWidth,hw)}); head.remove(); }
          // IN＝陣容表的固定資料框（見 FR／inner）：框畫在固定位置，內容（透明底）縮到框內側；沒給 IN（消息）照舊整塊置中
          const top=hc?hc.height:0, w=h.offsetWidth, ht=h.offsetHeight, k=IN?Math.min(IN.w/w,IN.h/ht):Math.min(SZ/w,(SZ-top)/ht);
          const cv=await html2canvas(h,{backgroundColor:IN?null:"#0b0e14",useCORS:true,scale:k,width:w,height:ht,windowWidth:Math.max(document.documentElement.scrollWidth,w)});
          const pc=document.createElement("canvas"); pc.width=pc.height=SZ; const g=pc.getContext("2d"); g.fillStyle="#0b0e14"; g.fillRect(0,0,SZ,SZ);
          if(hc)g.drawImage(hc,0,0);
          if(IN){ g.fillStyle="#141a26"; g.strokeStyle="rgba(255,255,255,.10)"; g.lineWidth=2; rrect(g,FR.m,IN.top,SZ-2*FR.m,SZ-IN.top-FR.m,FR.r); g.fill(); g.stroke();
            g.drawImage(cv,Math.round(IN.x+(IN.w-cv.width)/2),IN.y); }   // 內容一律從框內側的上緣開始畫（消息最後一頁比較短；陣容表本來就鋪滿）：原本陣容表上下置中、吸收不到 1px 的餘數，結果各聯賽的欄名列上下差 1px（2026-11-21 量到 LPL 比 LCK 高 1px）
          else g.drawImage(cv,Math.round((SZ-cv.width)/2),hc?top:Math.round((SZ-cv.height)/2));
          const d=new Date(), pad=x=>String(x).padStart(2,"0"), fn=`${name}_${pad(d.getFullYear()%100)}${pad(d.getMonth()+1)}${pad(d.getDate())}${pad(d.getHours())}.jpg`;
          await new Promise(ok=>pc.toBlob(bl=>{
            if(sink){ const fin=png=>{ sink.add({bl,fn,png,tag:String(name).replace(/^S17_LoL_/,"").replace(/_/g," ")}); ok(); }; if(sink.png)pc.toBlob(fin,"image/png"); else fin(null); return; }   // 分享視窗：不下載；另外要一份 PNG（剪貼簿只收 PNG，點開小圖時複製用）
            const a=document.createElement("a"); a.href=URL.createObjectURL(bl); a.download=fn;
            document.body.appendChild(a); a.click(); a.remove(); setTimeout(()=>URL.revokeObjectURL(a.href),5000); ok(); },"image/jpeg",0.93));
          h.remove(); if(!sink)await new Promise(r=>setTimeout(r,350)); };   // 連續下載間隔
        try{
          if(!window.html2canvas)await new Promise((ok,no)=>{ const sc=document.createElement("script"); sc.src="html2canvas.min.js"; sc.onload=ok; sc.onerror=no; document.head.appendChild(sc); });
          rootZ=document.documentElement.style.zoom; document.documentElement.style.zoom="";   // html2canvas 不懂整頁 zoom
          // ── 整批截圖共用同一套版面（使用者 2026-11-21「截圖的邊框位置 以及每一欄的寬度應該要是一致的」）──
          //   ①上方那一列：寬度、字級、顏色說明框的位置用六大聯賽裡最擠的那個來定（不看現在篩了哪幾個聯賽），消息也用同一個高度
          //     ⇒ 不管哪個聯賽、陣容表或消息，資料框的上緣都在同一個位置（inner 算出來的 IN 整批共用）
          //   ②陣容表：隊名欄與六個資料欄的寬度各取所有聯賽裡最寬的需求，每張圖用同一組欄寬、同一個縮放（字一樣大、欄位在同一個位置）；
          //     原本每個聯賽各自挑「字最大」的寬度，隊伍少的聯賽字比較大、欄位也跟著跑
          //   ③消息：欄寬用整份消息量出來的那一組，每一頁都一樣（原本每頁照自己的內容排，原隊／新隊那幾欄每頁寬度不同）
          const LG=en2?[["tbNew","New signing"],["tbRs","Re-signed & promoted"],["tbStay","Staying"],["tbExp","Contract expired"],["tbOut","Possible move"],["tbY","Rumor"]]
            :[["tbNew","新加入"],["tbRs","續約升職"],["tbStay","續留"],["tbExp","合約到期"],["tbOut","可能轉會"],["tbY","傳聞"]];   // 續約與升職併成一項、都用粉色（使用者 2026-11-21）；小框的標籤仍分開寫
          const legend=`<div class="trShHdLg" style="flex:1 1 auto;min-width:0;display:flex;flex-wrap:nowrap;align-items:center;gap:14px;margin:0 4px;padding:5px 12px;border:1px solid rgba(255,255,255,.12);border-radius:8px;font-size:18px;justify-content:space-evenly">`
            +LG.map(([c,l])=>`<b class="tbN ${c}"${c==="tbStay"?` style="color:#fff"`:""}>${l}</b>`).join("")+`<b class="tbN" style="color:#8b98ad"><span class="tbOk" style="margin:0 4px 0 0;font-size:inherit">✔</span>${en2?"Roster confirmed":"陣容確認"}</b></div>`;
          // 賽區名放大、後面不寫國名（使用者 2026-11-21「截圖的聯賽後面不用寫國名了 然後聯賽字體大一點 並且標籤列的資料要水平」）；
          //   整列的字（大標題、賽區、顏色說明、時間）對在同一條中線上——照墨水中心對，見 level()。對齊基線試過，使用者看了仍說沒有水平
          const mkHead=(sc,w,fs,lx)=>{ const hd=mkHost(w,`<span style="font-size:32px;font-weight:900;color:${sc.c||"#f0e6d2"}">${esc(sc.lg)}</span>`,legend), lg=hd.querySelector(".trShHdLg");
            hd.style.padding="18px 22px 0"; lg.style.fontSize=fs+"px"; if(lx){ const d=lx-lg.offsetLeft; if(d>0)lg.style.marginLeft=(4+d)+"px"; } level(hd.querySelector(".trShHdRow")); return hd; };
          let HW=1000, HF=18, LX=0; const LGS=["LCK","LPL","LEC","LCS","CBLOL","LCP"];
          LGS.forEach(n=>{ const hd=mkHead({lg:n},HW,HF,0); LX=Math.max(LX,hd.querySelector(".trShHdLg").offsetLeft); hd.remove(); });   // 顏色說明那一框的左緣對齊最長的賽區名
          { const hd=mkHead({lg:LGS[0]},HW,HF,LX), row=hd.querySelector(".trShHdRow"), lg=hd.querySelector(".trShHdLg");
            // 塞不塞得下：看最後一項的右緣有沒有吃到框的右留白（scrollWidth 不算右邊的留白，量不出來）；字先縮到 15px，還不夠就把整塊加寬（＝等比例縮小），不換行
            const over=()=>lg.lastElementChild.getBoundingClientRect().right>lg.getBoundingClientRect().right-11||row.scrollWidth>row.clientWidth+1;
            while(over()&&HF>15){ HF--; lg.style.fontSize=HF+"px"; }
            while(over()&&HW<1800){ HW+=50; hd.style.width=HW+"px"; }
            hd.remove(); }
          const hp0=mkHead({lg:LGS[0]},HW,HF,LX), IN=inner(Math.round(hp0.offsetHeight*SZ/hp0.offsetWidth)); hp0.remove();
          if(MODE==="news"){
            // 消息也用固定的資料框（跟陣容表同一套 FR／inner）：每一頁的框都在同一個位置、同一個大小，內容靠上放——
            //   原本整塊照內容高度縮放再置中，每頁的框寬、框高都不一樣（第 1 頁左右留 78px、第 2 頁 54px），最後一頁還會浮在中間。
            //   另外獨立站的欄名列是 sticky（往下捲時留在上方），截圖複本裡會往下滑一段、蓋住第一則消息 ⇒ mkHost 的樣式把它固定回原位
            const src=main.querySelector(".trList"), NW=1400, kids=[...src.children].filter(e=>!e.classList.contains("trHead")), hd=src.querySelector(".trHead");
            const CARD=`class="card trList" style="margin:0;padding:0;background:none;border:0;border-radius:0;box-shadow:none"`;
            // 上方那一列跟陣容表同一個寬度、同一個高度：放一個看不見的顏色說明框佔位（它決定整列的高度與基線）
            const mkNH=(i,n)=>{ const x=mkHost(HW,`<span style="font-size:32px;font-weight:900">${en2?"News":"消息"}</span>${n>1?`<span style="font-size:17px;color:#8b98ad">${i+1} / ${n}</span>`:""}`,legend.replace('class="trShHdLg" style="','class="trShHdLg" style="visibility:hidden;'));
              x.style.padding="18px 22px 0"; x.querySelector(".trShHdLg").style.fontSize=HF+"px"; level(x.querySelector(".trShHdRow")); return x; };
            const INn={...IN,ta:1};
            const probe=mkHost(NW,""); probe.querySelector(".trShHdRow").remove(); probe.style.padding="0"; probe.insertAdjacentHTML("beforeend",`<div ${CARD}></div>`); const pl=probe.lastChild; pl.innerHTML=src.innerHTML;
            const GC=getComputedStyle(pl).gridTemplateColumns, CARD2=/^[0-9. px]+$/.test(GC)?CARD.replace('style="','style="grid-template-columns:'+GC+";"):CARD;   // 整份消息量出來的欄寬（px）：每一頁都用這一組
            // 每一列實際佔的高度＝下一列的頂 − 這一列的頂（列與列之間的間隔也算進去，才不會排到超出框）
            const els=[...pl.children], tops=els.map(e=>e.getBoundingClientRect().top), endY=pl.getBoundingClientRect().bottom, occ=i=>(i+1<els.length?tops[i+1]:endY)-tops[i];
            const hi=els.findIndex(e=>e.classList.contains("trHead")), hdrH=hi<0?0:occ(hi), hs=[]; els.forEach((e,i)=>{ if(i!==hi)hs.push(occ(i)); }); probe.remove();
            const CAP=INn.h*NW/INn.w-hdrH-2;
            const pages=[]; let cur=[], used=0; kids.forEach((e,i)=>{ if(cur.length&&used+hs[i]>CAP){ pages.push(cur); cur=[]; used=0; } cur.push(e); used+=hs[i]; }); if(cur.length)pages.push(cur);
            for(let i=0;i<pages.length-1;i++){ const pg=pages[i]; if(pg.length>1&&pg[pg.length-1].classList.contains("trDay"))pages[i+1].unshift(pg.pop()); }   // 日期標題不留在頁尾
            // 分享視窗先產生最新幾頁（整份消息十幾頁，手機全畫完要半分鐘）；要更多再按「產生其餘」從 skip 接著畫
            const P0=sink&&sink.skip?Math.min(sink.skip,pages.length):0, NP=sink&&sink.max?Math.min(pages.length,P0+sink.max):pages.length; if(sink){ sink.capped=pages.length>NP; sink.total=pages.length; }
            for(let i=P0;i<NP;i++){ if(sink&&sink.stop)break; const pg=pages[i];
              const nh=mkNH(i,pages.length), h=mkHost(NW,""); h.querySelector(".trShHdRow").remove(); h.style.padding="0"; h.style.background="transparent";
              h.insertAdjacentHTML("beforeend",`<div ${CARD2}>${hd?hd.outerHTML:""}${pg.map(e=>e.outerHTML).join("")}</div>`);
              await out(h,"S17_LoL_"+(en2?"News":"消息")+(pages.length>1?"_"+(i+1):""),nh,INn); }
          }else{
            const secs=[]; [...main.querySelectorAll(".tbBoard>.tbLg,.tbBoard>.tbRow")].forEach(e=>{ if(e.classList.contains("tbLg"))secs.push({lg:e.querySelector("b").textContent,sub:e.dataset.rg||"",c:e.style.getPropertyValue("--lgc"),rows:[]}); else if(secs.length)secs[secs.length-1].rows.push(e); });
            // 版面＝一列一隊，跟網頁（桌面版）的表格一樣（使用者 2026-11-20「截圖能不能改成一列一隊這樣 跟網頁顯示的一樣」）
            const bhd=main.querySelector(".tbBoard>.tbHd"), live=secs.filter(sc=>sc.rows.length);
            // prep：把一個聯賽的列排進截圖用的複本（還不決定寬度）
            const prep=sc=>{ const h=mkHost(1200,""); h.querySelector(".trShHdRow").remove(); h.style.padding="0"; h.style.background="transparent"; h.dataset.noic="1";
              h.insertAdjacentHTML("beforeend",`<div><div class="card tbBoard" style="margin:0;padding:0;background:none;border:0;border-radius:0;box-shadow:none">${bhd?bhd.outerHTML:""}${sc.rows.filter(r=>!r.classList.contains("tbFA")).sort((p,q)=>(+p.dataset.o||0)-(+q.dataset.o||0)).map(r=>r.outerHTML).join("")}</div></div>`);   // 截圖一律照第三賽段成績排（＝資料原本的順序），不跟著網頁目前的排序（使用者 2026-11-21「截圖預設以第三賽段成績排序」）
              // 截圖專用（使用者 2026-11-20「截圖的教練只列主教練 自由人也不列 每路每個選手都換行」）：不列自由人那一列；同一格多人時一人一行
              // 2026-11-21 改版「選手評分那欄改成後勤 但不顯示合約到的(藍字) 只顯示其餘的狀況」：最後一欄＝後勤（評分欄整欄拿掉），後勤那格不列合約到期的人
              { const bd=h.querySelector(".tbBoard");
                h.querySelectorAll(".tbCell.tbRate,.tbCell.tbFaCo").forEach(x=>x.remove()); { const rh=h.querySelector(".tbHd .tbRateH"); if(rh)rh.remove(); }
                // 2026-11-21 晚再改「截圖的主教練跟後勤合併 改稱 教練」：主教練那格接上後勤（後勤照舊不列合約到期的藍字），一人一行、主教練排前面；後勤那格與它的欄名拿掉，欄名改寫「教練」
                h.querySelectorAll(".tbRow").forEach(r=>{ const hc=r.querySelector('.tbCell[data-r="HC"]'), st=r.querySelector('.tbCell[data-r="STF"]'); if(!hc)return; const v=hc.querySelector(".tbCv"); if(!v)return;
                  const keep=[...v.querySelectorAll(".tbN"),...(st?[...st.querySelectorAll(".tbCv .tbN")].filter(n=>!n.classList.contains("tbExp")):[])];
                  v.innerHTML=keep.length?keep.map(n=>n.outerHTML).join("<br>"):`<span class="tbMuted">–</span>`; hc.classList.toggle("tbEmpty",!keep.length); hc.dataset.r="CO"; hc.classList.add("tbShCo"); if(st)st.remove(); });
                { const hs=h.querySelector(".tbHd"); if(hs&&hs.children[7])hs.children[7].remove(); const c6=hs&&hs.children[6]; if(c6){ [...c6.childNodes].forEach(n=>{ if(n.nodeType===3)n.remove(); }); c6.appendChild(document.createTextNode(en2?"Coach":"教練")); } }
                h.querySelectorAll(".tbSep").forEach(x=>x.outerHTML="<br>");
                h.querySelectorAll(".tbRtSz").forEach(x=>x.remove());   // 網頁上用來撐住最後一欄寬度的隱形字串（最長的評分範圍）：截圖的欄寬另外算，留著會把七欄都撐成那麼寬、整張表的字跟著變小
                // 表頭：「路線圖＋路線名稱」這一組對在下方資料的正中間（使用者 2026-11-20「截圖的資料 是要在路線圖跟路線名的置中位置 不是路線名稱的置中位置」），
                //   圖和字同一條水平線（html2canvas 畫行內圖會偏高 ⇒ 圖字都放進固定高度的 inline-flex，各自垂直置中）
                h.querySelectorAll(".tbHd>span").forEach(sp=>{ const im=sp.querySelector("img"); if(!im)return; const tx=sp.textContent.trim(), w=im.offsetWidth||20, hh=im.offsetHeight||20;
                  sp.innerHTML=`<span style="display:inline-flex;align-items:center;gap:6px;height:${hh}px;line-height:${hh}px"><span style="display:block;height:${hh}px;line-height:${hh}px">${esc(tx)}</span></span>`;
                  im.style.cssText+=`;display:block;flex:0 0 auto;margin:0;width:${w}px;height:${hh}px;vertical-align:top`; sp.firstChild.insertBefore(im,sp.firstChild.firstChild); });
                // 隊名那格：隊徽放大 1.3 倍，右邊兩行＝縮寫（＋✔）與第三賽段成績；隊徽對在這兩行的正中間（位移在排好版之後由 lvTeam 算）
                //   （使用者 2026-11-21「第三賽段成績改寫在隊名縮寫下方」「隊徽放大一點 然後放在隊名縮寫與成績的高度置中位置」）
                h.querySelectorAll(".tbRow").forEach(r=>{ const tm=r.querySelector(".tbTeam"); if(!tm)return; const im=tm.querySelector("img:not(.tbFaIc)"), K=1.3; let top=im; while(top&&top.parentElement!==tm)top=top.parentElement;
                  if(im){ ["width","height","marginTop","marginRight","marginBottom","marginLeft"].forEach(p=>{ const v=parseFloat(im.style[p]); if(isFinite(v))im.style[p]=(v*K)+"px"; });
                    if(!parseFloat(im.style.width)){ const w0=(+im.getAttribute("width"))||parseFloat(im.style.height)/K||26; im.style.width=im.style.height=(w0*K)+"px"; }
                    // 還沒經過 lgFit 的圖（量版面用的參考複本是從資料直接排的）：佔跟畫面上一樣的固定寬位子（圖寬的 1.5 倍），隊名欄量出來才跟畫面上的一樣寬
                    if(!im.dataset.fit){ const w1=parseFloat(im.style.width)||26*K; im.style.margin=`0 ${w1*0.25}px`; }
                    im.style.flex="0 0 auto"; im.style.maxWidth="none"; }
                  const box=document.createElement("span"), l1=document.createElement("span"); box.className="tbTmB"; box.style.cssText="display:flex;flex-direction:column;align-items:flex-start;justify-content:center;gap:3px;line-height:1.15";
                  l1.style.cssText="display:flex;align-items:center;gap:4px"; [...tm.children].filter(x=>x!==top).forEach(x=>l1.appendChild(x)); box.appendChild(l1);
                  if(r.dataset.rk){ const l2=document.createElement("span"); l2.className="tbTmR"; l2.style.cssText="font-size:12.5px;font-weight:700;color:#8b98ad;white-space:nowrap"; l2.textContent=r.dataset.rk; box.appendChild(l2); }
                  tm.appendChild(box); }); }
              h.querySelectorAll(".tbHd").forEach(x=>{ x.style.position="static"; x.style.background="none"; }); h.querySelectorAll(".tbDim").forEach(x=>x.classList.remove("tbDim"));
              return h; };
            const built=live.map(sc=>({sc,h:prep(sc)}));
            // 量版面用的參考複本＝六大聯賽的完整名單（從資料直接排，不看畫面上篩了哪幾個聯賽、有沒有搜尋或只看某些狀態）：
            //   字級（＝整張的寬度 W）由它們決定，所以不管哪一次截圖、截哪一個聯賽，ID 的大小都一樣
            //   （使用者 2026-11-21「所有ID大小一致的情況下調整大小」；原本只量這一批要輸出的聯賽，只截 LCK 時字會比六個聯賽一起截時大）
            const tip0=TIPS.length;
            const ref=["LCK","LPL","LEC","LCS","CBLOL","LCP"].map(lg=>{ const ts=(D.board||[]).filter(t=>t.lg===lg&&!t.fa); if(!ts.length)return null;
              const tmp=document.createElement("div"); tmp.innerHTML=ts.map(rowH).join(""); return {sc:{lg,rows:[...tmp.children]}}; }).filter(Boolean).map(o=>({...o,h:prep(o.sc)}));
            TIPS.length=tip0;   // 參考複本不會開小框，排它們時多塞進去的小框內容丟掉
            const allH=[...built,...ref];
            // 教練人數不影響字的大小（使用者 2026-11-21「預設教練是三行 然後超過三人就針對該隊教練那格縮小」；前一版教練一人一行、列高照人數長，
            //   實測每隊教練 3 人字會從 32.7px 掉到 23.3px、4 人掉到 18.3px）：決定整張寬度 W（＝字級）與每一列的基本高度時，教練那格只算一行；
            //   之後每一張圖再看這個聯賽放不放得下：放得下就照原字級排（列高照人數長），真的塞滿才縮教練格的字——見下面每一張圖的「列高與教練格」那一段
            allH.forEach(o=>o.h.querySelectorAll(".tbRow .tbShCo").forEach(c=>{ const v=c.querySelector(".tbCv"); if(!v)return;
              v.style.display="block"; v.style.maxHeight=(parseFloat(getComputedStyle(c).lineHeight)||22.5)+"px"; v.style.overflow="hidden"; }));   // 先夾成一行來量；輸出前在「列高與教練格」那一段放開
            // 欄寬：每個聯賽都量一次「隊名欄」與「六個資料欄」各自最少要多寬（放得下最長的那個字），整批取最大
            //   ⇒ 隊名欄固定 teamW、六欄等寬（五路＋教練）。每張圖的欄位位置與字級因此完全一樣
            // 字的大小＝整張的寬度 W 越小、縮放到 2000px 之後字越大。W 取兩個條件裡比較大的：
            //   ①放得下最長的 ID：隊名欄＋六欄 ×（最寬的格子＋PADX 的呼吸空間）②隊伍最多的聯賽（LPL 14 隊）在這個寬度下不會超出資料框（教練格只算一行）
            //   原本 W 至少 1000：六欄每欄 139px，最長的 ID 才 93px，左右空很多、字只有 28px；現在大約 860 ⇒ 字 32.6px（放大 16% 左右）
            let teamW=0, colW=0;
            allH.forEach(o=>{ const bd=o.h.querySelector(".tbBoard"); o.h.style.width="6000px"; bd.style.gridTemplateColumns="max-content repeat(6,max-content)"; bd.style.justifyContent="start";
              const tr=getComputedStyle(bd).gridTemplateColumns.split(/\s+/).map(parseFloat); if(tr[0]>teamW)teamW=tr[0]; tr.slice(1,7).forEach(v=>{ if(v>colW)colW=v; }); bd.style.justifyContent=""; });
            teamW=Math.ceil(teamW)+2; colW=Math.ceil(colW)+2;
            const PADX=8, WMIN=800;   // PADX＝最長的 ID 左右再多留的空間（加上格子本身的內距 12px，相鄰兩欄最長的字之間至少 20px）；WMIN＝字不要大到離譜的下限
            let W=Math.max(WMIN,teamW+6*(colW+PADX));   // 資料欄＝五路＋教練，共六欄
            const lay=w=>allH.forEach(o=>{ o.h.style.width=w+"px"; o.h.querySelector(".tbBoard").style.gridTemplateColumns=teamW+"px repeat(6,minmax(0,1fr))"; });
            lay(W); for(let it=0;it<200&&allH.some(o=>o.h.offsetHeight+2>IN.h*W/IN.w);it++){ W+=4; lay(W); }   // 隊伍最多的聯賽在這個寬度下太高（會超出框）⇒ 整批一起加寬（等於一起縮小）
            ref.forEach(o=>o.h.remove());   // 參考複本量完就丟，只輸出 built
            const lvTeam=h=>h.querySelectorAll(".tbRow .tbTeam").forEach(tm=>{ const box=tm.querySelector(".tbTmB"), im=tm.querySelector("img:not(.tbFaIc)"); if(!box||!im)return;
              const a=inkOf(box.querySelector(".tbTmA")||box.firstChild), b=inkOf(box.querySelector(".tbTmR"))||a; if(!a)return; const ir=im.getBoundingClientRect(); nudge(box,(ir.top+ir.bottom)/2-(a.top+b.bot)/2); });
            for(const o of built){ if(sink&&sink.stop)break; const h=o.h, hd=mkHead(o.sc,HW,HF,LX);
              // 列高與教練格（使用者 2026-11-20「底部不要太多留空」；2026-11-21「預設教練是三行 然後超過三人就針對該隊教練那格縮小」，同一天再定
              //   「如果本來的模式可以塞下一兩支隊伍有四位教練 例如LEC 那就不要縮那一兩隊的教練ID 只有不得已的情況真的塞滿才會縮」⇒ 沒有「最多三行」這個上限了）：
              //   b＝每一列的基本高度（選手那幾格決定；教練格在量版面時夾成一行）、t＝這一隊教練名單照原字級排的文字高度（人數 × 行高）。
              //   分三級，前一級放得下就不往下走：
              //   ①全部照原字級、上下內距照常（pv）：這個聯賽放得下就完全不縮（LCK／LEC 有一兩隊四位教練屬於這一級）
              //   ②字不縮，只把「被教練名單撐高的那幾列」的上下內距一起收小（最少 PMIN）
              //   ③還是放不下才縮字：找一個文字高度的上限 T，名單比 T 高的教練格才縮到 T（人最多的先縮），其他格不動
              //   三級算出來的是每一列最少要多高；還有剩的高度從最矮的列開始墊（墊到同一個高度），內容剛好頂到框的內側。
              //   教練人數完全不影響整張圖的字級（W 在前面就定了）。高度一律用帶小數的實際值（offsetHeight 取整會讓整塊比框高 1～2px、
              //   這一張的縮放被壓小，字就跟別的聯賽不一樣大）
              { const rs=[...h.querySelectorAll(".tbRow")], hh=()=>h.getBoundingClientRect().height, lim=IN.h*W/IN.w;
                if(rs.length){ const cs=rs.map(r=>r.querySelector(".tbShCo")), g0=getComputedStyle(cs.find(Boolean)||rs[0].querySelector(".tbCell")||rs[0]), fs0=parseFloat(g0.fontSize)||15, lh=parseFloat(g0.lineHeight)||fs0*1.5, pv=(parseFloat(g0.paddingTop)+parseFloat(g0.paddingBottom))||12, PMIN=2;
                  const sum=a=>a.reduce((x,y)=>x+y,0), bis=(lo,hi,ok)=>{ for(let i=0;i<40;i++){ const md=(lo+hi)/2; if(ok(md))lo=md; else hi=md; } return lo; };   // bis＝ok 成立的最大值（二分）
                  const b=rs.map(r=>r.getBoundingClientRect().height), room=lim-(hh()-sum(b));
                  const vs=cs.map(c=>c&&c.querySelector(".tbCv")), t=vs.map(v=>v?(v.querySelectorAll(".tbN").length||1)*lh:0), TM=Math.max(0,...t);
                  const fit=(T,q)=>b.map((x,i)=>Math.max(x,t[i]?Math.min(t[i],T)+q:0)), ok=(T,q)=>sum(fit(T,q))<=room;
                  let hs=ok(TM,pv)?fit(TM,pv):ok(TM,PMIN)?fit(TM,bis(PMIN,pv,q=>ok(TM,q))):fit(bis(0,TM,T=>ok(T,PMIN)),PMIN);
                  const Lv=bis(0,Math.max(...hs)+Math.max(0,room-sum(hs)),l=>sum(hs.map(x=>Math.max(x,l)))<=room); hs=hs.map(x=>Math.max(x,Lv));
                  rs.forEach((r,i)=>{ const rowH=hs[i]-0.02; r.style.minHeight=rowH+"px"; const c=cs[i], v=vs[i]; if(!v)return;   // −0.02＝每列留一點點餘裕，免得小數進位後整塊比框高一丁點、又被下面的保險收掉 1px
                    v.style.display=v.style.maxHeight=v.style.overflow="";   // 放開量版面時夾的那一行
                    const can=Math.max(lh*0.5,rowH-PMIN); let lines=t[i];
                    if(lines>can+0.3){ const f=Math.max(4,Math.floor(fs0*can/lines*4)/4); c.style.fontSize=f+"px"; lines=lines*f/fs0; }   // 只縮這一格的字（0.25px 一階）
                    if(lines+pv>rowH){ const p=Math.max(0,(rowH-lines)/2); c.style.paddingTop=c.style.paddingBottom=p+"px"; } }); }
                for(let it=0;it<60&&rs.length&&hh()>lim;it++){ const r=rs[rs.length-1-(it%rs.length)], v=parseFloat(r.style.minHeight)||0; if(v>1)r.style.minHeight=(v-1)+"px"; } }
              lvTeam(h);
              await out(h,"S17_LoL_"+o.sc.lg,hd,IN); }
          }
        }catch(e){ if(sink&&sink.fail)sink.fail(e); else alert((en2?"Screenshot failed: ":"截圖失敗：")+((e&&e.message)||e)); }
        hosts.forEach(h=>h.remove()); if(rootZ!=null)document.documentElement.style.zoom=rootZ; if(sb)sb.disabled=false; };
      if(sb)sb.onclick=()=>runShot(null);
      // 📤 分享（紙飛機）：圖照同一套截圖流程產生、留在記憶體，開一個小視窗看圖、挑圖、下載；點開小圖＝放大並把那一張複製到剪貼簿。
      //   沿革（都是使用者 2026-11-21）：①「新增一個分享按鈕 就是把截圖功能轉換成發文形式 把圖片放到 FB IG THREADS 之一 讓使用者選擇
      //   使用者最終只需要寫內文並按發佈即可發出與分享」⇒ 做了三顆平台按鈕（手機＝系統分享清單；電腦＝圖片進剪貼簿＋開該站）
      //   ②「手機或網頁都是 直接開啟那網頁到發文的地方 點開後把圖片放進去」⇒ 查過三家的官方文件，沒有任何一家提供「帶圖片開發文框」的網址
      //   （Threads 的 intent/post 只收文字與連結；FB 的 sharer 只收連結；IG 完全沒有），瀏覽器也不准一個網站把檔案塞進另一個網站，做不到
      //   ③定案「還是無法做到直接把圖片放到文章內 不行的話這三個社群按鈕就刪除 改成點開小圖時自動複製」
      //   ⇒ 三顆平台按鈕與系統分享清單都拿掉（別再加回來），只留下載；點開小圖就自動複製，到哪裡發文都是貼上
      const shb=document.getElementById("trShare");
      if(shb)shb.onclick=()=>{ if(document.getElementById("trShD"))return;
        const T=(zh,en)=>en2?en:zh;
        const IC={dl:`<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 4v11"/><path d="M7.5 10.8 12 15.3l4.5-4.5"/><path d="M5 19.5h14"/></svg>`};
        const dlg=document.createElement("div"); dlg.id="trShD"; dlg.className="trShD";   /* 樣式掛在類別上：轉會網站的 CSS 篩選只留 .tr* 類別的規則，#id 選擇器會被濾掉 */
        dlg.innerHTML=`<div class="trShBox" role="dialog" aria-modal="true"><div class="trShHd"><b>${T("截圖與分享","Screenshots")}</b><button class="trShX" aria-label="close">✕</button></div>`
          +`<div class="trShMsg"></div><div class="trShImgs"></div>`
          +`<div class="trShBtns"><button class="trShP trShDl" data-p="dl" disabled>${IC.dl}<span>${T("下載圖片","Download")}</span></button></div><div class="trShHint"></div></div>`;
        document.body.appendChild(dlg);
        const msg=dlg.querySelector(".trShMsg"), grid=dlg.querySelector(".trShImgs"), hint=dlg.querySelector(".trShHint"), st={items:[],sel:new Set(),done:false,err:"",capped:false,closed:false};
        const sink={png:true, max:4,   // png＝每張另外要一份 PNG（複製用）；消息先產生最新 4 頁，其餘按「產生其餘」再畫
          add(it){ if(st.closed)return; it.url=URL.createObjectURL(it.bl); st.items.push(it); if(MODE!=="news"||st.items.length===1)st.sel.add(it); draw(); },
          fail(e){ st.err=T("產生圖片失敗：","Could not render the image: ")+((e&&e.message)||e); } };
        // 鍵盤：放大檢視開著的時候 Esc 只關放大檢視、左右鍵換張；否則 Esc 關整個視窗
        const onKey=e=>{ const z=dlg.querySelector(".trShZ"); if(z){ if(e.key==="Escape")z._shut(); else if(e.key==="ArrowLeft")z._nav(-1); else if(e.key==="ArrowRight")z._nav(1); return; } if(e.key==="Escape")close(); };
        const close=()=>{ st.closed=true; sink.stop=true; st.items.forEach(x=>{ try{ URL.revokeObjectURL(x.url); }catch(_){} }); dlg.remove(); document.removeEventListener("keydown",onKey); };
        document.addEventListener("keydown",onKey); dlg.querySelector(".trShX").onclick=close; dlg.onclick=e=>{ if(e.target===dlg)close(); };
        const draw=()=>{ const n=st.items.length, k=st.sel.size, more=st.done&&st.capped?(sink.total||0)-n:0;
          // 訊息列：進度／已選幾張＋全選、產生其餘（消息頁數多的時候）
          msg.innerHTML=st.err?esc(st.err):(!st.done?T(`產生圖片中… ${n}`,`Rendering images… ${n}`):n>1?T(`已選 ${k} / ${n} 張`,`${k} of ${n} selected`):"")
            +(!st.err&&st.done&&n>1?`<a class="trShA" data-act="all" href="#">${k<n?T("全選","Select all"):T("全不選","Clear")}</a>`:"")
            +(!st.err&&more>0?`<a class="trShA" data-act="more" href="#">${T(`產生其餘 ${more} 頁`,`Render ${more} more`)}</a>`:"");
          // 縮圖用 div 不用 button：手機瀏覽器不支援分享時，要能長按圖片儲存。點圖＝放大看；右上角的圈＝要不要用這張
          grid.classList.toggle("one",n<2);
          grid.innerHTML=st.items.map((x,i)=>`<div class="trShI${st.sel.has(x)?" on":""}" data-i="${i}" title="${esc(x.fn)}"><img src="${x.url}" alt=""><i class="trShCk" role="checkbox" aria-checked="${st.sel.has(x)}"></i><b>${esc(x.tag||"")}</b></div>`).join("");
          dlg.querySelectorAll(".trShP").forEach(b=>{ b.disabled=!n||!k; }); };
        // 複製到剪貼簿（剪貼簿只收 PNG）。一定要在點擊／按鍵的當下直接呼叫、中間不能有 await（Safari 會擋），所以 PNG 在產生圖片時就先備好
        const copyImg=x=>{ try{ if(x&&x.png&&navigator.clipboard&&window.ClipboardItem)return navigator.clipboard.write([new ClipboardItem({"image/png":x.png})]).then(()=>true,()=>false); }catch(_){} return Promise.resolve(false); };
        // 放大檢視（使用者 2026-11-21「分享按完後產生的小圖 要可以點開放大顯示」）：整張縮到螢幕內；再點圖＝放到原尺寸可以拖著看；左右換張；點旁邊或 X 關閉。
        //   開啟與換張的當下把看到的那一張複製到剪貼簿（使用者同一天「改成點開小圖時自動複製」），底下那行字標出有沒有複製成功
        const zoom=i0=>{ let k=i0; const n=()=>st.items.length, z=document.createElement("div"); z.className="trShZ";
          z.innerHTML=`<div class="trShZI"><img alt=""></div><button class="trShX trShZX" aria-label="close">✕</button>`+(n()>1?`<button class="trShZN" data-d="-1" aria-label="previous">‹</button><button class="trShZN" data-d="1" aria-label="next">›</button>`:"")+`<div class="trShZT"></div>`;
          const box=z.querySelector(".trShZI"), im=z.querySelector("img"), tt=z.querySelector(".trShZT");
          const show=()=>{ const x=st.items[k]; if(!x)return; im.src=x.url; box.classList.remove("big"); box.scrollTop=box.scrollLeft=0;
            const cap=esc((x.tag||"")+(n()>1?`　${k+1} / ${n()}`:"")); tt.innerHTML=cap;
            copyImg(x).then(ok=>{ if(st.items[k]===x&&z.isConnected)tt.innerHTML=cap+(ok?`<b>${T("✓ 已複製","✓ Copied")}</b>`:`<b class="no">${T("無法自動複製","Copy failed")}</b>`); }); };
          z._shut=()=>z.remove(); z._nav=d=>{ k=(k+d+n())%n(); show(); };
          z.onclick=e=>{ e.stopPropagation(); if(z._sw&&Date.now()-z._sw<450)return;   // 剛滑完換張的那一下不算點擊
            const nb=e.target.closest(".trShZN"); if(nb){ z._nav(+nb.dataset.d); return; } if(e.target===im){ box.classList.toggle("big"); return; } z._shut(); };
          // 手機：左右滑換張（放到原尺寸時不攔，那時的滑動是在拖圖）
          let tx=null; z.addEventListener("touchstart",e=>{ tx=e.touches.length===1?e.touches[0].clientX:null; },{passive:true});
          z.addEventListener("touchend",e=>{ if(tx==null||box.classList.contains("big")||n()<2)return; const dx=e.changedTouches[0].clientX-tx; tx=null; if(Math.abs(dx)>50){ z._sw=Date.now(); z._nav(dx<0?1:-1); } },{passive:true});
          dlg.appendChild(z); show(); };
        grid.onclick=e=>{ const b=e.target.closest(".trShI"); if(!b)return; const i=+b.dataset.i, x=st.items[i]; if(!x)return;
          if(e.target.closest(".trShCk")){ if(st.items.length<2)return; if(st.sel.has(x))st.sel.delete(x); else st.sel.add(x); draw(); return; }
          zoom(i); };
        msg.onclick=e=>{ const a=e.target.closest("a[data-act]"); if(!a)return; e.preventDefault();
          if(a.dataset.act==="all"){ if(st.sel.size<st.items.length)st.items.forEach(x=>st.sel.add(x)); else st.sel.clear(); draw(); return; }
          if(a.dataset.act==="more"&&st.done){ sink.skip=st.items.length; sink.max=999; st.done=false; draw(); shb.disabled=true; runShot(sink).then(fin); } };
        const dl=(x,i)=>setTimeout(()=>{ const a=document.createElement("a"); a.href=x.url; a.download=x.fn; document.body.appendChild(a); a.click(); a.remove(); },i*350);
        // 下載（原本篩選列上獨立的 📸，使用者 2026-11-21「截圖按鈕放到分享按鈕裡面」）：勾選的每一張存成 JPG
        dlg.querySelector(".trShDl").onclick=()=>{ const its=st.items.filter(x=>st.sel.has(x)); if(!its.length)return; its.forEach(dl); hint.textContent=T(`已下載 ${its.length} 張`,`${its.length} image${its.length>1?"s":""} downloaded`); };
        const fin=()=>{ shb.disabled=false; st.done=true; st.capped=!!sink.capped; if(st.closed)return; if(!st.items.length&&!st.err)st.err=T("沒有可以分享的內容","Nothing to share"); draw();
          if(!st.err)hint.textContent=T("點小圖：放大並自動複製那一張","Tap a thumbnail to enlarge it and copy it"); };
        if(!main.querySelector(".tbRow,.trRow")){ st.done=true; st.err=T("沒有可以分享的內容","Nothing to share"); draw(); return; }   // 篩選到沒有任何列：不產生一張空白圖
        draw(); shb.disabled=true;
        runShot(sink).then(fin); }; }
    // 隊徽視覺大小統一（使用者 2026-11-20「全面檢視隊徽 視覺上統一大小」）：圖檔都是正方形畫布，但圖案本身有扁（T1／DK／SHG）有窄（MKOI／DNS）
    //   ⇒ 用小畫布量圖案的外框，把「圖案面積」調成一樣（扁的放寬、方的略縮），寬最多 1.5 倍、高不超過原本的框；
    //   每個隊徽佔固定寬 1.5 倍的位子、置中 ⇒ 後面的縮寫對齊。量不到（跨網域沒開 CORS、file://）就維持原樣
    const LGF=window._tbLGF||(window._tbLGF=new Map()), LGP=window._tbLGP||(window._tbLGP=new Map());
    // 量外框用另外一張帶 crossOrigin 的圖（轉會網站的隊徽在主站網域；直接在顯示的圖上設 crossorigin，CORS 一失敗圖就整張不見）
    // 隊徽看得見的左右邊界（il／ir＝圖的左右各有多少比例「看起來是空的」）：照實際顯示大小 E、放大 3 倍（＝手機的像素密度）畫在深色底上，
    //   連白色描邊濾鏡一起畫，找第一欄／最後一欄「跟底色差得夠多」的位置——跟從截圖量像素是同一把尺。
    //   為什麼不用外框：外框只要有一個像素就算，可是往旁邊越來越細的尖角、淡淡的尾巴（HLE 左邊那條）縮到 16px 根本看不見，
    //   眼睛看到的邊比外框內縮 1.5px，「與 → 隊徽」就比別隊寬（使用者 2026-11-21「不能一致嗎」）。只拿來對齊左右，大小仍照外框算
    const LG_TH=70;
    const lgEdge=(m,E)=>{ const k=Math.max(8,Math.round(E*2)/2), pd0=(1-m.fw)/2; m.ed=m.ed||{}; if(m.ed[k])return m.ed[k]; let il=pd0, ir=pd0;
      try{ const Z=3, n=Math.round(k*Z), o=3*Z, c=document.createElement("canvas"); c.width=c.height=n+2*o; const g=c.getContext("2d",{willReadFrequently:true});
        g.fillStyle="rgb(27,34,54)"; g.fillRect(0,0,c.width,c.height); try{ g.filter=`drop-shadow(0 0 ${Z}px rgba(255,255,255,.55))`; }catch(_){}
        g.drawImage(m.img,o,o,n,n); const d=g.getImageData(0,0,c.width,c.height).data, W=c.width; let a=-1, b=-1;
        const hit=X=>{ for(let Y=0;Y<W;Y++){ const i=(Y*W+X)*4; if(Math.abs(d[i]-27)+Math.abs(d[i+1]-34)+Math.abs(d[i+2]-54)>LG_TH)return true; } return false; };
        for(let X=0;X<W;X++)if(hit(X)){ a=X; break; }
        for(let X=W-1;X>=0;X--)if(hit(X)){ b=X; break; }
        if(a>=0&&b>=a){ il=(a-o)/n; ir=(o+n-1-b)/n; } }catch(_){}
      return m.ed[k]={il,ir}; };
    // 字的左右留白（墨水到字框邊緣，單位 em）：TextMetrics 的 actualBoundingBox 在這個字型只回整數、左邊的留白還量不到 ⇒ 把字放大 8 倍畫到小畫布上，找第一欄／最後一欄有顏色的位置
    const INKB=window._tbInk||(window._tbInk=new Map());
    const inkB=(el,ch,right)=>{ if(!ch)return 0; const g=getComputedStyle(el), fs=parseFloat(g.fontSize)||14, key=g.fontWeight+"|"+g.fontFamily+"|"+ch+"|"+(right?1:0); if(INKB.has(key))return INKB.get(key)*fs;
      let v=0; try{ const K=8, c=document.createElement("canvas"), W=Math.ceil(fs*K*2.4), H=Math.ceil(fs*K*1.9); c.width=W; c.height=H; const x=c.getContext("2d",{willReadFrequently:true});
        x.font=`${g.fontWeight} ${fs*K}px ${g.fontFamily}`; x.textBaseline="alphabetic"; x.fillStyle="#fff"; const ox=Math.round(fs*K*0.7), adv=x.measureText(ch).width; x.fillText(ch,ox,Math.round(H*0.72));
        const d=x.getImageData(0,0,W,H).data; let l=-1, r=-1;
        for(let X=0;X<W&&l<0;X++)for(let Y=0;Y<H;Y++)if(d[(Y*W+X)*4+3]>60){ l=X; break; }
        for(let X=W-1;X>=0&&r<0;X--)for(let Y=0;Y<H;Y++)if(d[(Y*W+X)*4+3]>60){ r=X; break; }
        if(l>=0)v=right?(ox+adv-1-r)/(fs*K):(l-ox)/(fs*K); }catch(_){ v=0; }
      v=Math.max(-0.1,Math.min(0.7,v)); if(!document.fonts||document.fonts.status==="loaded")INKB.set(key,v);   // 字型還沒載完量到的是替代字型，不存
      return v*fs; };
    const lgGet=(src,cb)=>{ if(LGF.has(src)){ cb(LGF.get(src)); return; } if(LGP.has(src)){ LGP.get(src).push(cb); return; } LGP.set(src,[cb]);
      const done=m=>{ LGF.set(src,m); (LGP.get(src)||[]).forEach(f=>f(m)); LGP.delete(src); };
      const p=new Image(); p.crossOrigin="anonymous";
      p.onload=()=>{ let m=null; try{ const N=36   /* 量測格接近實際顯示大小（16～22px 的兩倍）：細線縮小後本來就看不見，量太細反而把它算成圖案 */, c=document.createElement("canvas"); c.width=c.height=N; const g=c.getContext("2d",{willReadFrequently:true}); g.drawImage(p,0,0,N,N);
          const d=g.getImageData(0,0,N,N).data; let x0=N,y0=N,x1=-1,y1=-1;
          // 圖案邊界＝「疊在深色底上看得見」的範圍：很淡的邊（alpha 低、疊上去跟底色差不多）不算，否則程式以為圖案到那裡、眼睛看到的卻空一截（HLE 左邊多 1.5px；使用者 2026-11-21「不能一致嗎」）
          //   實心的深色部分（alpha 高）有白色描邊濾鏡照著，仍算看得見
          const vis=i=>{ const al=d[i+3]/255; if(al>0.8)return true; if(al<0.1)return false; return (Math.abs(d[i]-27)+Math.abs(d[i+1]-34)+Math.abs(d[i+2]-54))*al>45; };
          for(let y=0;y<N;y++)for(let x=0;x<N;x++)if(vis((y*N+x)*4)){   /* 量測格 48 → 96（門檻維持 24：調高會把 SR 這種半透明邊的隊徽量窄、貼到字）；使用者 2026-11-21「每一種隊徽都大約是半形空格的留空」 */ if(x<x0)x0=x; if(x>x1)x1=x; if(y<y0)y0=y; if(y>y1)y1=y; }
          if(x1>=x0&&y1>=y0)m={fw:(x1-x0+1)/N,fh:(y1-y0+1)/N,img:p}; }catch(_){ m=null; } done(m); };   // img＝帶 CORS 載好的那張圖，lgEdge 要照顯示大小重畫來量左右邊界
      p.onerror=()=>done(null); p.src=src; };
    const lgFit=img=>{ if(img.dataset.fit)return; const S=parseFloat(img.style.height)||img.height||0; if(!S)return; img.dataset.fit="0";
      // 先照「整張圖就是圖案」佔好固定寬的位子、置中：量不到圖案外框的時候（用檔案直接開 index.html、或跨網域沒開 CORS）也跟 FA 徽章對得齊（使用者 2026-11-21 回報本機舊網站沒對齊）
      if(img.closest(".tbTeam,.trTeam")&&!img.classList.contains("tbFaIc")){ img.style.margin=`0 ${(1.5*S-S)/2}px`; }
      lgGet(img.currentSrc||img.src,m=>{ if(!m||!img.isConnected)return; img.dataset.fit="1";
        const r=m.fw/m.fh, A=0.6*S*S, W=1.5*S; let w=Math.sqrt(A*r), h=Math.sqrt(A/r); const k=Math.min(1,W/w,S/h); w*=k; h*=k;
        const E=w/m.fw;   // 整張正方形圖要畫多大，圖案才是 w×h
        // 圖案靠右貼著後面的縮寫（使用者 2026-11-20「有些隊徽的左右間隔比較大 導致跟右邊戰隊縮寫的視覺距離變遠了」）：
        //   每個隊徽仍佔固定寬 W 的位子（縮寫才會對齊），但圖案不再置中——窄的隊徽（DNS、MKOI）置中時兩邊各空一截；改成圖案右緣對齊位子右緣，空的全留在左邊
        const pd=(E-w)/2, ed=m.img?lgEdge(m,E):null, pL=ed?E*ed.il:pd, pR=ed?E*ed.ir:pd;   // pL／pR＝圖檔左右「看起來是空的」那一截（對齊用）；pd＝外框算出來的（舊的，左右一樣）
        img.style.width=img.style.height=E+"px"; // 2026-11-21 使用者「各賽區的隊徽沒有置中 先置中後再寫隊名縮寫 然後隊名縮寫置右」：陣容表的隊名欄＝隊徽在固定寬的位子裡置中（各隊的隊徽對在同一條中線上）、
        //   縮寫接在後面靠左；其他地方（消息的原隊／新隊、小框裡的隊伍）維持圖案左右貼齊，才不會離縮寫太遠
        img.style.margin=img.closest(".tbTeam,.trTeam")?`${(S-E)/2}px ${(W-E)/2}px`:`${(S-E)/2}px ${-pd}px`;   // 消息的原隊／新隊也用同一套（使用者 2026-11-21「都要採取這樣徽章置中放左邊 然後隊名置左的做法」）   /* 2026-11-20 再改「空白也不要留給左邊」：不留固定寬的位子，圖案左右都貼齊（縮寫的左緣因此會隨隊徽寬度不同） */ img.style.maxWidth="none";
        img.style.setProperty("--lgpad",pL+"px"); img.style.setProperty("--lgpadR",pR+"px");
        // 小框裡「與 [隊徽] 縮寫」：字本身左右有留白（與 的右邊、縮寫第一個字母的左邊，每個字不一樣）⇒ 量墨水邊界把它扣掉，圖案兩側的實際空隙才會每一隊都一樣
        //   （使用者 2026-11-21「各隊 與→隊徽 是 5–6.5px、隊徽→縮寫 是 5–6px 不能一致嗎」）
        const chip=img.closest(".tpTm"); if(chip){ try{
            const nx=[...chip.childNodes].find(n=>n.nodeType===3&&n.textContent.trim()), pv=chip.previousSibling;
            const a=nx?inkB(chip,nx.textContent.trim().charAt(0),false):0, b=(pv&&pv.nodeType===3&&pv.textContent.trim())?inkB(chip.parentElement,pv.textContent.trim().slice(-1),true):0;
            img.style.margin=`${(S-E)/2}px ${-pR-a}px ${(S-E)/2}px ${-pL-b}px`; }catch(_){} } }); };   // --lgpad／--lgpadR＝圖檔左右看起來是空的那一截（手機版靠左對齊時扣掉）
    const lgFitAll=root=>root.querySelectorAll(".tbTeam img,.trTeam img,.tpTm img,.rtHd img").forEach(lgFit);
    lgFitAll(main);
    // 手機卡片標題列：評分右邊的留空要跟隊徽左邊的留空一樣（使用者 2026-11-21）。評分靠右對齊時，最後一個字自己右側還有一截字內留白——
    //   數字約 0.3px、中文字（第三賽段成績的「名」）約 1.3px、全形「）」約半個字——三種模式看起來就不一樣寬。
    //   ⇒ 量出最後一個字的右側留白寫進 --rb，手機版 CSS 用負 margin 收掉（電腦版評分欄是置中的，不用）；字型載完再量一次
    const rbFit=()=>{ try{ const cv=rbFit._c||(rbFit._c=document.createElement("canvas").getContext("2d"));
        main.querySelectorAll(".tbRow .tbRate .tbCv").forEach(v=>{ const w=document.createTreeWalker(v,NodeFilter.SHOW_TEXT); let n, last=null; while((n=w.nextNode())){ if(n.textContent.trim())last=n; }
          if(!last)return; const el=last.parentElement, g=getComputedStyle(el), ch=[...last.textContent.trim()].pop(); cv.font=`${g.fontWeight} ${g.fontSize} ${g.fontFamily}`;
          const rb=Math.max(0,inkB(el,ch,true)), pc=el.closest(".rtPc");
          (pc||v).style.setProperty("--rb",rb.toFixed(2)+"px"); if(pc)v.style.setProperty("--rb","0px"); }); }catch(_){} };
    if(MODE!=="news"){ rbFit(); if(document.fonts&&document.fonts.ready)document.fonts.ready.then(()=>{ if(main.isConnected)rbFit(); }); }
    if(MODE!=="news"){ // 格子提示（自建浮層：多行＋排版，原生 title 做不到）
      let tip=document.getElementById("tbTip"); if(!tip){ tip=document.createElement("div"); tip.id="tbTip"; document.body.appendChild(tip);
        addEventListener("scroll",()=>{ if(!tip.classList.contains("sheet"))tip.style.display="none"; },{passive:true});
        // 手機：點格子以外的地方收起底部小框
        document.addEventListener("click",e=>{ if(tip.classList.contains("sheet")&&!e.target.closest(".tbCell")&&!e.target.closest(".tbTeam")&&!e.target.closest("#tbTip"))tip.style.display="none"; });
        tip.addEventListener("click",e=>{ const g=e.target.closest(".tpGo"); if(!g||!tip.classList.contains("sheet")||e.target.closest("a"))return;   /* 點來源連結是開原文，不跳消息頁 */ const [n,d,ab]=String(g.dataset.go||"").split("|"); tip.style.display="none";
          window._trGo={n,d,ab}; Object.assign(V,{trMode:"news",trQ:"",trSrc:"",trSt:"",trRg:"",trKd:""}); saveState(); render(); }); }
      const bd=main.querySelector(".tbBoard");
      // 手機／觸控（使用者 2026-11-20「幫我設計手機點擊時的 UI」）：沒有滑鼠懸停 ⇒ 點格子從畫面底部滑出小框（再點同一格或點別處收起）；格子裡的 wiki 連結在手機不直接跳走
      const touch=()=>matchMedia("(hover:none)").matches||innerWidth<760;
      const show=(c,sheet)=>{ tip.innerHTML=(sheet?`<div class="tbTipXW"><button class="tbTipX" aria-label="close">✕</button></div>`:"")+TIPS[+c.dataset.tb]; tip.classList.toggle("sheet",!!sheet); tip.style.display="block"; lgFitAll(tip); tip.scrollTop=0;   /* 開新的小框一律從最上面開始（原本會停在上一個小框捲到的位置） */
        tip.style.maxHeight=""; tip.style.overflowY=""; tip.style.pointerEvents=""; tip.style.width=""; tip.style.maxWidth="";
        if(sheet){ tip.style.left=tip.style.top=""; tip.dataset.cur=c.dataset.tb; const x=tip.querySelector(".tbTipX"); if(x)x.onclick=()=>{ tip.style.display="none"; }; return; }
        // 電腦版（使用者 2026-11-21「小框會超出螢幕範圍」「滑鼠要可以移動到小框上 離開小框才消失」）：
        //   小框最高不超過視窗、太長就在框內捲；上下都放不下時貼著視窗邊；滑鼠可以移上去（連結點得到），離開格子與小框才收
        // 整頁縮放（主站視窗不是 2560 寬時 <html> 有 zoom）：getBoundingClientRect／innerWidth／innerHeight 是視覺 px，寫進 style 的與 offsetWidth 是版面 px，
        //   兩者差 window._zoomF——直接把 rect 寫進 style，小框會往左上偏一截（1920 寬時偏 25%，蓋到別格）。以下一律先換成版面 px 再算（獨立站沒有縮放，ZF＝1）
        const ZF=window._zoomF||1, vr=el=>{ const q=el.getBoundingClientRect(); return {left:q.left/ZF,top:q.top/ZF,right:q.right/ZF,bottom:q.bottom/ZF,width:q.width/ZF,height:q.height/ZF}; }, IW=innerWidth/ZF, IH=innerHeight/ZF;
        tip.style.pointerEvents="auto"; tip.style.maxHeight=(IH-16)+"px"; tip.style.overflowY="auto";
        // 格子的小框跟那一欄同寬（使用者 2026-11-21「小框的寬度都設定為跟本來欄位寬度一致」）；欄太窄時至少 300px（小框內容本身最少要 260px＋邊距，再窄字會被切掉）。評分小框（五欄的表）維持原本的寬度
        { const cw=vr(c).width, isRate=c.classList.contains("tbRate"); tip.style.width=isRate?(tip.querySelector(".rtS3")?"max-content":""):Math.max(300,Math.round(cw))+"px"; tip.style.maxWidth=isRate?"":"none";   /* 第三賽段的小框內容少，縮成 250px（使用者 2026-11-21） */ tip.style.boxSizing="border-box"; }
        const r=vr(c), w=tip.offsetWidth, h=tip.offsetHeight;
        const bR=vr(bd);   // 小框不貼著螢幕邊：左右都收在陣容表那張卡片的範圍內（使用者 2026-11-21「網頁版 評分小框有點太靠近螢幕右側了」；原本只離螢幕邊 8px）
        // 擺放順序（使用者 2026-11-21「夠短就往下擴展顯示 下方沒位置就往上 如果長到上下都不行 那就往右或往左 不要擋到本來的資料」）：
        //   ①格子下方放得下 ⇒ 下方；②否則上方放得下 ⇒ 上方；③都放不下 ⇒ 放到格子右邊（右邊不夠就左邊），上下置中、收在視窗內——不蓋住這一格
        const cl=v=>Math.max(Math.max(16,bR.left+12),Math.min(Math.min(IW-w-24,bR.right-w-12),v));
        let x=cl(r.left+r.width/2-w/2), y=r.bottom-1;   // 貼著格子、不留縫：滑鼠從格子往下就直接進到小框，才能把「離開就收」做成沒有延遲
        if(y+h>IH-8){
          if(r.top-h+1>=8)y=r.top-h+1;
          else{ y=Math.max(8,Math.min(IH-h-8,r.top+r.height/2-h/2));
            const sr=IW-r.right-16, sl=r.left-16; x=(sr>=w||sr>=sl)?Math.min(r.right+8,IW-w-8):Math.max(8,r.left-w-8); } }
        tip.style.left=x+"px"; tip.style.top=y+"px"; };
      // 隊名那格也算評分那一列：點（手機）或滑過（電腦）隊名一樣開評分小框（使用者 2026-11-20「應該點擊分數那列都會顯示分數小框」）
      // 電腦版觸發範圍＝文字外擴一點（.tbCv 的 padding），不是整格（使用者 2026-11-21）；手機點擊照舊整格都算
      // FA 那一列的標題（隊名格與評分格，手機卡片最上面那條）不開小框：FA 沒有評分，點了只會跳出一個空的框（使用者 2026-11-21「FA的標籤列改成無法點擊」）
      const cellOf=e=>{ const c=e.target.closest(".tbCell"); if(c){ if(c.classList.contains("tbRate")&&c.closest(".tbFA"))return null; return (e.type!=="mouseover"||e.target.closest(".tbCv"))?c:null; } return cellOfT(e); };
      const cellOfT=e=>{ const tm=e.target.closest(".tbTeam"); return tm&&!tm.closest(".tbFA")?tm.closest(".tbRow").querySelector(".tbRate"):null; };
      const keepTip=()=>{ clearTimeout(tip._ht); tip._hp=0; }, hideSoon=()=>{ clearTimeout(tip._ht); tip._hp=1; tip._ht=setTimeout(()=>{ tip._hp=0; if(!tip.classList.contains("sheet")){ tip.style.display="none"; tip._c=null; } },200); };   // _hp＝200ms 的倒數正在跑（mousemove 會一直進來，不能每次都重新倒數）
      // 移到別的地方立刻收（使用者 2026-11-21「往旁邊移開時 延遲又變大了」）：只有還在同一格裡（正要往小框移動）才給 200ms 緩衝
      const hideNow=()=>{ clearTimeout(tip._ht); tip._hp=0; if(!tip.classList.contains("sheet")){ tip.style.display="none"; tip._c=null; } };
      // 通道（使用者 2026-11-21「小框如果太長 放在右邊的時候…移動到小框之前系統就會認為我移出了判定 進而關閉小框」）：
      //   觸發範圍只有文字那一小塊，小框放在格子旁邊時，滑鼠要先橫越格子剩下的空白與 8px 的縫才碰得到小框——空白只給 200ms、縫算「別格」當場就收。
      //   ⇒ 從文字邊緣到小框邊緣之間畫一條通道：起點是格子的高（寬），越靠近小框越寬、到小框邊緣時跟小框一樣高（寬），斜著移過去也不會出界。
      //   滑鼠在通道裡＝正要去小框：不收、不倒數、也不換成路過那一格的小框；一出通道照舊（同一格 200ms、別格立刻收）
      const inBridge=e=>{ const c=tip._c; if(!c||tip.style.display!=="block"||tip.classList.contains("sheet"))return false;
        const r=c.getBoundingClientRect(), t=tip.getBoundingClientRect(), v=c.querySelector(".tbCv"), q=v?v.getBoundingClientRect():r, x=e.clientX, y=e.clientY, mix=(a,b,f)=>a+(b-a)*Math.max(0,Math.min(1,f));
        if(t.left>=r.right-2||t.right<=r.left+2){ const R=t.left>=r.right-2, a=R?q.right:q.left, b=R?t.left:t.right; if(Math.abs(b-a)<3)return false; const f=(x-a)/(b-a);
          return f>=-0.03&&f<=1.03&&y>=mix(r.top,Math.min(r.top,t.top),f)-1&&y<=mix(r.bottom,Math.max(r.bottom,t.bottom),f)+1; }
        if(t.top>=r.bottom-2||t.bottom<=r.top+2){ const D=t.top>=r.bottom-2, a=D?q.bottom:q.top, b=D?t.top:t.bottom; if(Math.abs(b-a)<3)return false; const f=(y-a)/(b-a);
          return f>=-0.03&&f<=1.03&&x>=mix(r.left,Math.min(r.left,t.left),f)-1&&x<=mix(r.right,Math.max(r.right,t.right),f)+1; }
        return false; };
      // 朝小框移動（文字很寬、或從格子中間斜著往小框上半部移時，還沒走到通道就先出了格子）：
      //   「上一個位置」與「小框靠格子那一邊的兩個角（各外擴 24px）」圍成三角形，新位置還在三角形裡＝正朝著小框去 ⇒ 不收、不換成路過那格的小框；
      //   中途停下來 350ms 還沒到小框才收。_pp＝上一個位置（移動不到 4px 的抖動不更新）、_onT＝滑鼠是不是還在觸發範圍（文字／隊名）上
      const aimAt=e=>{ const c=tip._c, P=tip._pp; if(!c||!P||tip.style.display!=="block"||tip.classList.contains("sheet"))return false;
        const t=tip.getBoundingClientRect(), r=c.getBoundingClientRect(), M=24;
        const S=t.left>=r.right-2?[[t.left,t.top-M],[t.left,t.bottom+M]]:t.right<=r.left+2?[[t.right,t.top-M],[t.right,t.bottom+M]]:t.top>=r.bottom-2?[[t.left-M,t.top],[t.right+M,t.top]]:t.bottom<=r.top+2?[[t.left-M,t.bottom],[t.right+M,t.bottom]]:null; if(!S)return false;
        const Q=[e.clientX,e.clientY], cr=(a,b,p)=>(b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]), d1=cr(P,S[0],Q), d2=cr(S[0],S[1],Q), d3=cr(S[1],P,Q);
        return (Q[0]!==P[0]||Q[1]!==P[1])&&!((d1<0||d2<0||d3<0)&&(d1>0||d2>0||d3>0)); };
      const transit=()=>{ clearTimeout(tip._ht); tip._hp=0; tip._ht=setTimeout(()=>{ if(tip._onT||tip.classList.contains("sheet"))return; tip.style.display="none"; tip._c=null; },350); };
      bd.onmouseover=e=>{ if(touch())return; if(inBridge(e)){ keepTip(); return; } if(aimAt(e)){ transit(); return; } const c=cellOf(e); if(!c){ const same=tip._c&&(e.target.closest(".tbCell")===tip._c||(e.target.closest(".tbTeam")&&e.target.closest(".tbRow")===tip._c.closest(".tbRow"))); same?hideSoon():hideNow(); return; } keepTip(); if(tip.style.display==="block"&&tip._c===c)return; tip._c=c; show(c,false); tip._pp=[e.clientX,e.clientY]; tip._onT=1; };
      // 同一格裡面移動不會有 mouseover（沒有跨過元素邊界）⇒ 小框開著的時候用 mousemove 補：在文字上／通道裡＝留著；同一格的其他地方＝開始 200ms 倒數；跑到別格（從通道斜出去）＝立刻收
      bd.onmousemove=e=>{ if(touch()||!tip._c||tip.style.display!=="block"||tip.classList.contains("sheet"))return;
        const P0=tip._pp; if(P0&&Math.abs(e.clientX-P0[0])+Math.abs(e.clientY-P0[1])<4)return;
        const cc=e.target.closest(".tbCell"), tm=e.target.closest(".tbTeam"), row=tip._c.closest(".tbRow");
        const on=!!((cc===tip._c&&e.target.closest(".tbCv"))||(tm&&!tm.closest(".tbFA")&&tm.closest(".tbRow")===row&&tip._c.classList.contains("tbRate")));
        const br=inBridge(e), am=!br&&aimAt(e); tip._pp=[e.clientX,e.clientY]; tip._onT=on;
        if(on||br){ keepTip(); return; }
        if(am){ transit(); return; }
        if(cc===tip._c||(tm&&tm.closest(".tbRow")===row)){ if(!tip._hp)hideSoon(); } else hideNow(); };
      bd.onmouseleave=e=>{ if(touch())return; const am=aimAt(e); clearTimeout(tip._ht); tip._hp=0; tip._ht=setTimeout(hideNow,am?350:50); };   // 50ms：剛好夠滑進小框（小框的 mouseenter 會取消）
      tip.onmouseenter=keepTip; tip.onmouseleave=()=>{ if(!tip.classList.contains("sheet")){ clearTimeout(tip._ht); tip.style.display="none"; tip._c=null; } };   // 離開小框立刻消失（使用者 2026-11-21）；從格子移往小框途中才給 200ms 緩衝
      bd.onclick=e=>{ if(!touch())return; const c=cellOf(e); if(!c)return; if(e.target.closest("a"))e.preventDefault();
        if(tip.style.display==="block"&&tip.classList.contains("sheet")&&tip.dataset.cur===c.dataset.tb){ tip.style.display="none"; return; } show(c,true); };
    } else { const tip=document.getElementById("tbTip"); if(tip)tip.style.display="none"; }
    main.querySelectorAll(".filters .sqLaneBtn[data-k]").forEach(b=>b.onclick=()=>{ V[b.dataset.k]=b.dataset.v; saveState(); render(); });
    if(MODE==="news"&&window._trGo){ const g=window._trGo; window._trGo=null; setTimeout(()=>{ const has=(r,x)=>!x||r.textContent.includes(x), c=[...main.querySelectorAll(".trRow")].filter(r=>has(r,g.n));
        const pick=c.find(r=>r.dataset.d===g.d&&has(r,g.ab))||c.find(r=>r.dataset.d===g.d)||c.find(r=>has(r,g.ab))||c[0];
        if(pick){ pick.scrollIntoView({block:"center"}); pick.classList.add("trFlash"); setTimeout(()=>pick.classList.remove("trFlash"),3000); } },80); }
    main.querySelectorAll(".tbSortT").forEach(b=>b.onclick=()=>{ V.tbSort={d:"pd",pd:"o",o:"d"}[SRT0]||"d"; saveState(); render(); });
    main.querySelectorAll(".filters .sqLaneBtn[data-mk]").forEach(b=>b.onclick=()=>{ const k=b.dataset.mk, S=mset(k), v=b.dataset.v; S.has(v)?S.delete(v):S.add(v); V[k]=[...S].join(","); saveState(); render(); });
    const qi=document.getElementById("trQ");
    qi.oninput=()=>{ clearTimeout(window._trQT); window._trQT=setTimeout(()=>{ V.trQ=qi.value; saveState(); const pos=qi.selectionStart; render(); const q2=document.getElementById("trQ"); q2.focus(); q2.setSelectionRange(pos,pos); },300); };
    main.querySelector('.cx[data-x="trQ"]').onclick=()=>{ V.trQ=""; saveState(); render(); };
    })();
addBase();
const at=document.getElementById("tsAt"), T0=window.TRANSFERS||{}; if(at&&T0.at)at.textContent=(LANG==="en"?"as of ":"截至 ")+T0.at; }
const ls=document.getElementById("tsLang"); if(ls){ ls.value=LANG; ls.onchange=()=>{ try{localStorage.setItem("ts_lang",ls.value);}catch(e){} location.reload(); }; }
render();
})();
