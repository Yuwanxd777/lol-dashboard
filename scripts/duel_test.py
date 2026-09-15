# -*- coding: utf-8 -*-
"""模擬BP「⚔ 對決」端到端（2026-09-15，使用者兩輪定案）。

第一輪：本機限定（有 window.__bpPredictNext 才有鈕）、系統純模仿戰隊（預測第 1 名）、綁真實戰隊、結算看雙方評分。
第二輪：▶ 開始＝**新開一局**；輪到系統 **5 秒後自動出手**（⏭ 下一步＝立刻）；可選「雙方都系統」整局自己跑；
        「⏵ 自動」鈕拿掉、自動模式永遠開。
另外：對決中人的點擊要落在對決那一局（前面有沒填完的局也不管）；直播同步中拒絕出手；
      公開版（載不到 bp_live_ui.js）連鈕都沒有。
用法：python scripts/duel_test.py（file:// 無頭，不碰使用者瀏覽器、不起 8178）
"""
import io, json, os, pathlib, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
fails = []


def ok(cond, label, detail=""):
    print(("  ✓ " if cond else "  ✗ ") + label + (("  " + detail) if detail else ""))
    if not cond:
        fails.append(label)


EMPTY = ('{b1:["","","","",""],b2:["","","","",""],p1:["","","","",""],p2:["","","","",""],'
         'pl1:["","","","",""],pl2:["","","","",""],plm1:["","","","",""],plm2:["","","","",""]}')
SETUP = """(arg) => {
  const S = V.bpSim;
  S.g = []; for (let i=0;i<3;i++) S.g.push(""" + EMPTY + """);
  S.n = 3; S.fp = [0,0,0]; S.side = [0,0,0]; S.meta = [{id:1},{id:2},{id:3}]; S.tm = [null,null,null]; S.uid = 3;
  S.t1 = arg.t1; S.t2 = arg.t2; S.pk1 = {}; S.pk2 = {};
  V.bpMode = "normal"; V.bpDuel = null;
  window.__bpDuelDelayMs = arg.delay;
  saveState(); render(); return true; }"""
BOARD = """() => { const gi = (V.bpDuel && V.bpDuel.gi >= 0) ? V.bpDuel.gi : 0, g = V.bpSim.g[gi];
  return { b1: g.b1, b2: g.b2, p1: g.p1, p2: g.p2,
           filled: [...g.b1, ...g.b2, ...g.p1, ...g.p2].filter(x => !!x).length,
           st: (document.getElementById('bpDuelSt') || {}).textContent || '',
           nextOff: !!(document.getElementById('bpDuelNext') || {}).disabled,
           cd: !!document.getElementById('bpDuelCd'),
           n: V.bpSim.n, gi: V.bpDuel ? V.bpDuel.gi : -9,
           others: V.bpSim.g.filter((_, j) => j !== gi).map(g2 => [...g2.b1, ...g2.b2, ...g2.p1, ...g2.p2].filter(x => !!x).length) }; }"""
SEQ = """(gi) => { const S = V.bpSim; const F=(S.fp[gi]||0)===0?"1":"2", L=F==="1"?"2":"1";
  return [["b",F,0],["b",L,0],["b",F,1],["b",L,1],["b",F,2],["b",L,2],
          ["p",F,0],["p",L,0],["p",L,1],["p",F,1],["p",F,2],["p",L,2],
          ["b",L,3],["b",F,3],["b",L,4],["b",F,4],
          ["p",L,3],["p",F,3],["p",F,4],["p",L,4]]; }"""

from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width": 1920, "height": 1080})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:180]))
    pg.goto(pathlib.Path(os.path.join(ROOT, "index.html")).resolve().as_uri() + "?y=2026")
    pg.wait_for_function("() => typeof GAMES !== 'undefined' && GAMES.length > 0 && typeof window.__bpPredictNext === 'function'",
                         timeout=90000)
    picked = pg.evaluate("""() => {
      const cnt = {}, pair = {};
      for (const o of GAMES) { const a = o.raw[C.blue_teamname], z = o.raw[C.red_teamname];
        if (!a || !z) continue; cnt[a]=(cnt[a]||0)+1; cnt[z]=(cnt[z]||0)+1;
        const k = a < z ? a+"|"+z : z+"|"+a; pair[k]=(pair[k]||0)+1; }
      let best = null, bn = 0;
      for (const k in pair) { const [a,z] = k.split("|"); const s = Math.min(cnt[a]||0, cnt[z]||0);
        if (pair[k] >= 2 && s > bn) { bn = s; best = [a,z]; } }
      return { t1: best && best[0], t2: best && best[1], n: bn }; }""")
    if not picked or not picked.get("t1"):
        print("找不到可用的隊伍"); b.close(); sys.exit(2)
    t1, t2 = picked["t1"], picked["t2"]
    print("樣本：%s vs %s\n" % (t1, t2))
    pg.click('nav .tab[data-view="模擬BP"]', timeout=6000)
    pg.wait_for_timeout(800)

    print("① 本機限定的鈕＋自動模式永遠開")
    pg.evaluate(SETUP, {"t1": t1, "t2": t2, "delay": 60000})
    pg.wait_for_timeout(600)
    ok(pg.query_selector("#bpDuelBtn") is not None, "有 __bpPredictNext → ⚔ 對決鈕在")
    ok(pg.query_selector("#bpDuelBox") is None, "還沒開對決 → 沒有面板")
    ok(pg.query_selector("#bpAutoBtn") is None, "⭐「⏵ 自動」鈕已拿掉")
    pg.evaluate("() => { V.bpAuto = false; saveState(); render(); }"); pg.wait_for_timeout(500)
    ok(pg.evaluate("() => V.bpAuto === true"), "⭐ 就算存檔裡是關的，重畫後自動模式也是開的")

    print("\n③ 綁真實戰隊")
    pg.evaluate("() => { V.bpSim.t2 = ''; saveState(); render(); }")
    pg.wait_for_timeout(500)
    pg.click("#bpDuelBtn"); pg.wait_for_timeout(500)
    r = pg.evaluate("""() => { const b0 = document.getElementById('bpDuelStart');
      return { box: !!document.getElementById('bpDuelBox'), startOff: b0 ? b0.disabled : null,
               st: (document.getElementById('bpDuelSt')||{}).textContent || '' }; }""")
    ok(r["box"], "按 ⚔ → 面板出現")
    ok(r["startOff"] is True and "戰隊" in r["st"], "沒選好兩隊 →「開始」灰、狀態提示先選戰隊", r["st"][:40])
    pg.evaluate("(t2) => { V.bpSim.t2 = t2; saveState(); render(); }", t2)
    pg.wait_for_timeout(500)

    print("\n④⑤ 對決流程（人 vs 系統，系統用「下一步」立刻出手；自動計時設 60 秒不會搶）")
    pg.click("#bpDuelStart"); pg.wait_for_timeout(700)
    r = pg.evaluate(BOARD)
    ok(r["n"] == 3 and r["gi"] == 2, "⭐ 開始：已有空局就用最後一個空局（第 3 局），不多開", "n=%s gi=%s" % (r["n"], r["gi"]))
    ok(r["filled"] == 0 and "第 1 手" in r["st"], "新局是空的、狀態寫第 1 手", r["st"][:40])
    gi = r["gi"]
    seq = pg.evaluate(SEQ, gi)
    me = "1"
    ai_ok = 0; ai_n = 0; dup = 0; stuck = False
    for k in range(20):
        kd, sd, i = seq[k]
        r = pg.evaluate(BOARD)
        if r["filled"] != k:
            stuck = True; print("     第 %d 手前盤面格數 %d ≠ %d：%s" % (k + 1, r["filled"], k, r["st"][:60])); break
        if sd != me:
            ai_n += 1
            if k < 3:
                ok(not r["nextOff"] and "系統" in r["st"] and r["cd"], "第 %d 手輪到系統：下一步可按、有倒數" % (k + 1), r["st"][:44])
            pred = pg.evaluate("(a) => { const r = window.__bpPredictNext(a.gi, a.k); return r && r.cands && r.cands[0] ? r.cands[0].raw : null; }", {"gi": gi, "k": k})
            pg.click("#bpDuelNext")
            pg.wait_for_timeout(500)
            after = pg.evaluate(BOARD)
            cell = after[kd + sd][i]
            if pred and cell == pred:
                ai_ok += 1
            elif cell:
                print("     第 %d 手系統填 %s，預測第 1 名是 %s" % (k + 1, cell, pred))
            allc = [x for x in after["b1"] + after["b2"] + after["p1"] + after["p2"] if x]
            if len(allc) != len(set(allc)):
                dup += 1
        else:
            if k < 8:
                ok(r["nextOff"] and ("你" in r["st"]), "第 %d 手輪到我：下一步是灰的" % (k + 1), r["st"][:36])
            clicked = pg.evaluate("""() => {
              const g = V.bpSim.g[V.bpDuel.gi], on = new Set([...g.b1,...g.b2,...g.p1,...g.p2].filter(x=>!!x));
              const c = [...document.querySelectorAll('.bpChip')].find(el => el.dataset.ch && !on.has(el.dataset.ch));
              if (!c) return null; c.click(); return c.dataset.ch; }""")
            pg.wait_for_timeout(500)
            after = pg.evaluate(BOARD)
            if not clicked or after[kd + sd][i] != clicked:
                pg.evaluate("""(a) => { const g = V.bpSim.g[V.bpDuel.gi];
                  const on = new Set([...g.b1,...g.b2,...g.p1,...g.p2].filter(x=>!!x));
                  const pool = Object.keys(window.CHAMP_SKILLS && CHAMP_SKILLS.d || {}).filter(x=>!on.has(x));
                  g[a.kd + a.sd][a.i] = pool[0] || ('X' + a.k); saveState(); render(); }""",
                            {"kd": kd, "sd": sd, "i": i, "k": k})
                pg.wait_for_timeout(400)
            elif k == 0 or k == 6:
                ok(True, "第 %d 手：我點角色池 → 填進**對決那一局**（前面三局是空的也不會被搶走）" % (k + 1))
    r = pg.evaluate(BOARD)
    ok(not stuck and r["filled"] == 20, "20 手走完（沒有卡住）", "填了 %d 格" % r["filled"])
    ok(all(x == 0 for x in r["others"]), "⭐ 其他局一格都沒被動到（點擊只落在對決局）", str(r["others"]))
    ok(ai_n == 10 and ai_ok == ai_n, "⭐ 系統每一手都＝預測第 1 名（純模仿戰隊）", "%d/%d" % (ai_ok, ai_n))
    ok(dup == 0, "系統出的英雄沒有跟盤面重複")
    ok("對決結束" in r["st"] and "vs" in r["st"], "⭐ 結算：面板寫對決結束＋雙方評分", r["st"][:70])

    print("\n⑦ 兩顆都按＝整局系統＋自動出手（計時縮到 0.3 秒）")
    ok(pg.query_selector("#bpDuelMe0") is None, "沒有「雙方都系統」鈕（拿掉了）")
    ok(pg.evaluate("() => V.bpDuel && V.bpDuel.ai && !V.bpDuel.ai['1'] && V.bpDuel.ai['2']"), "預設：隊B 交給系統、隊A 自己點")
    pg.evaluate("() => { window.__bpDuelDelayMs = 300; }")
    pg.click("#bpDuelMe1"); pg.wait_for_timeout(400)
    ok(pg.evaluate("() => V.bpDuel && V.bpDuel.ai['1'] && V.bpDuel.ai['2']"), "⭐ 兩顆都按下 → 兩邊都交給系統")
    pg.click("#bpDuelStart"); pg.wait_for_timeout(300)
    r0 = pg.evaluate(BOARD)
    ok(r0["n"] == 3 and r0["gi"] == 1, "再按開始 → 用剩下的空局（第 2 局）", "n=%s gi=%s" % (r0["n"], r0["gi"]))
    t0 = time.time()
    while time.time() - t0 < 40:
        pg.wait_for_timeout(500)
        r = pg.evaluate(BOARD)
        if r["filled"] >= 20:
            break
    ok(r["filled"] == 20, "⭐ 沒按任何鍵，整局 20 手自己跑完", "%d 格、%.1f 秒" % (r["filled"], time.time() - t0))
    allc = [x for x in r["b1"] + r["b2"] + r["p1"] + r["p2"] if x]
    ok(len(allc) == len(set(allc)), "自己跑完的一局沒有重複英雄")
    ok("對決結束" in r["st"], "跑完有結算", r["st"][:60])
    ok(pg.evaluate("() => !window.__bpDuelT && !window.__bpDuelCd"), "結束後計時器都清掉了")

    print("\n⑧ 沒有空局才新開一局；全局模式滿 5 局改清一局")
    pg.evaluate("() => { window.__bpDuelDelayMs = 60000; }")
    pg.click("#bpDuelStart"); pg.wait_for_timeout(600)
    r = pg.evaluate(BOARD); ok(r["n"] == 3 and r["gi"] == 0, "還有空局（第 1 局）→ 用它", "n=%s gi=%s" % (r["n"], r["gi"]))
    pg.evaluate("() => { V.bpSim.g[0].b1[0] = 'Aatrox'; saveState(); render(); }"); pg.wait_for_timeout(500)
    pg.click("#bpDuelStart"); pg.wait_for_timeout(600)
    r = pg.evaluate(BOARD); ok(r["n"] == 4 and r["gi"] == 3 and r["filled"] == 0, "⭐ 沒有空局 → 新開一局（第 4 局）", "n=%s gi=%s" % (r["n"], r["gi"]))
    pg.evaluate("() => { V.bpMode = 'global'; V.bpSim.g[3].b1[0] = 'Ahri'; saveState(); render(); }"); pg.wait_for_timeout(500)
    pg.click("#bpDuelStart"); pg.wait_for_timeout(600)
    r = pg.evaluate(BOARD); ok(r["n"] == 5 and r["gi"] == 4, "全局模式未滿 5 局 → 還是新開（第 5 局）", "n=%s gi=%s" % (r["n"], r["gi"]))
    pg.evaluate("() => { V.bpSim.g[4].b1[0] = 'Akali'; saveState(); render(); }"); pg.wait_for_timeout(500)
    pg.click("#bpDuelStart"); pg.wait_for_timeout(600)
    r = pg.evaluate(BOARD); ok(r["n"] == 5 and r["filled"] == 0, "⭐ 全局模式滿 5 局 → 不加局、清一局來打", "n=%s gi=%s" % (r["n"], r["gi"]))

    # 模擬BP 的 + 加局也是同一條規矩：最新一局是空的就不再加（使用者 2026-09-15）
    n0 = pg.evaluate("() => V.bpSim.n")
    pg.evaluate("() => { const el = document.querySelector('.bsGAddCol'); if (el) el.click(); }"); pg.wait_for_timeout(500)
    ok(pg.evaluate("() => V.bpSim.n") == n0, "⭐ + 加局：最新一局是空的 → 不多開（局數不變）", "n=%d" % n0)
    pg.evaluate("() => { V.bpMode = 'normal'; V.bpSim.g[V.bpSim.n-1].b1[0] = 'Annie'; saveState(); render(); }"); pg.wait_for_timeout(500)
    pg.evaluate("() => { const el = document.querySelector('.bsGAddCol'); if (el) el.click(); }"); pg.wait_for_timeout(500)
    ok(pg.evaluate("() => V.bpSim.n") == n0 + 1, "+ 加局：最新一局有東西 → 照常加一局", "n=%d" % (n0 + 1))

    print("\n⑥ 護欄")
    pg.evaluate("() => { window._bsLiveOn = true; }")
    pg.click("#bpDuelNext"); pg.wait_for_timeout(400)
    r = pg.evaluate(BOARD)
    ok(r["filled"] == 0 and "直播同步" in r["st"], "直播同步中按下一步 → 拒絕、盤面不動", r["st"][:40])
    pg.evaluate("() => { window._bsLiveOn = false; }")
    pg.click("#bpDuelEnd"); pg.wait_for_timeout(500)
    ok(pg.query_selector("#bpDuelBox") is None and pg.evaluate("() => V.bpDuel") is None, "結束 → 面板收起、狀態清掉")
    ok(pg.evaluate("() => !window.__bpDuelT && !window.__bpDuelCd"), "結束 → 計時器清掉")
    # 重整網頁＝對決自動關閉（使用者 2026-09-15）
    pg.click("#bpDuelBtn"); pg.wait_for_timeout(400)
    ok(pg.evaluate("() => !!V.bpDuel") and pg.query_selector("#bpDuelBox") is not None, "先把對決打開")
    pg.reload(); pg.wait_for_function("() => typeof GAMES !== 'undefined' && GAMES.length > 0", timeout=90000)
    pg.click('nav .tab[data-view="模擬BP"]', timeout=6000); pg.wait_for_timeout(800)
    ok(pg.evaluate("() => V.bpDuel") is None and pg.query_selector("#bpDuelBox") is None, "⭐ 重整後對決自動關閉（沒有面板、狀態清掉）")
    ok(pg.query_selector("#bpDuelBtn") is not None, "重整後 ⚔ 鈕還在（只是關著）")
    # 公開版＝根本載不到 bp_live_ui.js：擋掉那支檔重新載頁，模擬BP 分頁不可以有 ⚔ 鈕、也不可以有面板。
    pg.route("**/bp_live_ui.js*", lambda r: r.abort())
    pg.goto(pathlib.Path(os.path.join(ROOT, "index.html")).resolve().as_uri() + "?y=2026")
    pg.wait_for_function("() => typeof GAMES !== 'undefined' && GAMES.length > 0", timeout=90000)
    pg.click('nav .tab[data-view="模擬BP"]', timeout=6000); pg.wait_for_timeout(800)
    ok(pg.evaluate("() => typeof window.__bpPredictNext") == "undefined", "擋掉 bp_live_ui.js → 沒有 __bpPredictNext")
    ok(pg.query_selector("#bpDuelBtn") is None and pg.query_selector("#bpDuelBox") is None,
       "⭐ 公開版（載不到 bp_live_ui.js）→ 連 ⚔ 鈕都沒有")
    ok(pg.query_selector("#bpAutoBtn") is None, "公開版也沒有「⏵ 自動」鈕")
    ok(not errs, "頁面沒噴錯", "; ".join(errs[:2]))
    b.close()

print("\n" + ("✗ %d 條失敗" % len(fails) if fails else "✓ 全部通過"))
sys.exit(1 if fails else 0)
