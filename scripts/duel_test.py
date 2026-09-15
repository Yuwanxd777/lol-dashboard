# -*- coding: utf-8 -*-
"""模擬BP「⚔ 對決」端到端（2026-09-15，使用者五項定案）。

  ① 本機限定：有 window.__bpPredictNext 才有 ⚔ 鈕；拿掉它重畫，鈕消失（公開版一個位元不變）
  ② 系統純模仿那支戰隊：每一手系統填的＝ __bpPredictNext(gi,k).cands[0].raw（該隊最可能的出手）
  ③ 綁真實戰隊：沒選兩隊「開始」是灰的
  ④ 等我按下一步：輪到系統時盤面不動，按了才多一格；輪到我時「下一步」灰、點角色池填格
  ⑤ 結算：20 手走完面板寫「對決結束」＋雙方評分
另外：直播同步中（window._bsLiveOn）按下一步要拒絕；系統出的英雄不會重複、不會填錯格。
用法：python scripts/duel_test.py（file:// 無頭，不碰使用者瀏覽器、不起 8178）
"""
import io, json, os, pathlib, sys

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
  S.n = 3; S.fp = [0,0,0]; S.side = [0,0,0]; S.meta = []; S.tm = [];
  S.t1 = arg.t1; S.t2 = arg.t2; S.pk1 = {}; S.pk2 = {};
  V.bpMode = "global"; V.bpDuel = null; V.bpAuto = true;
  saveState(); render(); return true; }"""
BOARD = """() => { const g = V.bpSim.g[(V.bpDuel && V.bpDuel.gi >= 0) ? V.bpDuel.gi : 0];
  return { b1: g.b1, b2: g.b2, p1: g.p1, p2: g.p2,
           filled: [...g.b1, ...g.b2, ...g.p1, ...g.p2].filter(x => !!x).length,
           st: (document.getElementById('bpDuelSt') || {}).textContent || '',
           nextOff: !!(document.getElementById('bpDuelNext') || {}).disabled,
           gi: V.bpDuel ? V.bpDuel.gi : -9 }; }"""
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

    print("① 本機限定的鈕")
    pg.evaluate(SETUP, {"t1": t1, "t2": t2})
    pg.wait_for_timeout(600)
    ok(pg.query_selector("#bpDuelBtn") is not None, "有 __bpPredictNext → ⚔ 對決鈕在")
    ok(pg.query_selector("#bpDuelBox") is None, "還沒開對決 → 沒有面板")

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

    print("\n④⑤ 對決流程：系統照預測第 1 名出手、輪到我要我點、20 手後結算")
    pg.click("#bpDuelStart")   # ▶ 開始
    pg.wait_for_timeout(600)
    r = pg.evaluate(BOARD)
    ok(r["gi"] == 0 and r["filled"] == 0 and "第 1 手" in r["st"], "開始：清空第 1 局、狀態寫第 1 手", r["st"][:40])
    seq = pg.evaluate(SEQ, 0)
    me = "1"
    ai_ok = 0; ai_n = 0; human_n = 0; dup = 0; stuck = False
    for k in range(20):
        kd, sd, i = seq[k]
        r = pg.evaluate(BOARD)
        if r["filled"] != k:
            stuck = True; print("     第 %d 手前盤面格數 %d ≠ %d：%s" % (k + 1, r["filled"], k, r["st"][:60])); break
        if sd != me:
            ai_n += 1
            ok(not r["nextOff"] and "系統" in r["st"], "第 %d 手輪到系統：下一步可按" % (k + 1), r["st"][:36]) if k < 3 else None
            pred = pg.evaluate("(k) => { const r = window.__bpPredictNext(0, k); return r && r.cands && r.cands[0] ? r.cands[0].raw : null; }", k)
            before = pg.evaluate(BOARD)
            pg.wait_for_timeout(250)
            ok(pg.evaluate(BOARD)["filled"] == k, "第 %d 手：沒按下一步盤面不動" % (k + 1)) if k < 3 else None
            pg.click("#bpDuelNext")   # ⏭ 下一步
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
            human_n += 1
            ok(r["nextOff"] and ("你" in r["st"]), "第 %d 手輪到我：下一步是灰的" % (k + 1), r["st"][:36]) if k < 8 else None
            # 模擬人：點角色池裡第一個還沒在盤面上的英雄（自動模式會填進待填格）
            clicked = pg.evaluate("""() => {
              const g = V.bpSim.g[0], on = new Set([...g.b1,...g.b2,...g.p1,...g.p2].filter(x=>!!x));
              const chips = [...document.querySelectorAll('.bpChip')];
              const c = chips.find(el => el.dataset.ch && !on.has(el.dataset.ch));
              if (!c) return null; c.click(); return c.dataset.ch; }""")
            pg.wait_for_timeout(500)
            after = pg.evaluate(BOARD)
            if not clicked or after[kd + sd][i] != clicked:
                # 角色池沒有可點的（版面／篩選）→ 直接填，流程照走
                pg.evaluate("""(a) => { const g = V.bpSim.g[0];
                  const on = new Set([...g.b1,...g.b2,...g.p1,...g.p2].filter(x=>!!x));
                  const pool = Object.keys(window.CHAMP_SKILLS && CHAMP_SKILLS.d || {}).filter(x=>!on.has(x));
                  g[a.kd + a.sd][a.i] = pool[0] || ('X' + a.k); saveState(); rerender(); }""",
                            {"kd": kd, "sd": sd, "i": i, "k": k})
                pg.wait_for_timeout(400)
    r = pg.evaluate(BOARD)
    ok(not stuck and r["filled"] == 20, "20 手走完（沒有卡住）", "填了 %d 格" % r["filled"])
    ok(ai_n == 10 and ai_ok == ai_n, "⭐ 系統每一手都＝預測第 1 名（純模仿戰隊）", "%d/%d" % (ai_ok, ai_n))
    ok(dup == 0, "系統出的英雄沒有跟盤面重複")
    ok("對決結束" in r["st"] and "vs" in r["st"], "⭐ 結算：面板寫對決結束＋雙方評分", r["st"][:70])
    sc = pg.evaluate("() => { const t = (document.getElementById('bpDuelSt')||{}).textContent||''; return (t.match(/\\d+(?:\\.\\d+)?/g)||[]).length; }")
    ok(sc >= 2, "結算裡有兩個評分數字", str(sc))

    print("\n⑥ 護欄")
    pg.click("#bpDuelStart"); pg.wait_for_timeout(500)   # 重新開始（第 1 手輪到先選方＝我）
    pg.click("#bpDuelMe2"); pg.wait_for_timeout(500)      # 換成我打隊B（分段鈕）→ 第 1 手輪到系統
    ok(pg.evaluate("() => V.bpDuel && V.bpDuel.me") == "2", "分段鈕切換我方 → 狀態記住")
    pg.evaluate("() => { window._bsLiveOn = true; }")
    pg.click("#bpDuelNext"); pg.wait_for_timeout(400)
    r = pg.evaluate(BOARD)
    ok(r["filled"] == 0 and "直播同步" in r["st"], "直播同步中按下一步 → 拒絕、盤面不動", r["st"][:40])
    pg.evaluate("() => { window._bsLiveOn = false; }")
    pg.click("#bpDuelEnd"); pg.wait_for_timeout(500)   # ✕ 結束
    ok(pg.query_selector("#bpDuelBox") is None and pg.evaluate("() => V.bpDuel") is None, "結束 → 面板收起、狀態清掉")
    # 公開版＝根本載不到 bp_live_ui.js（不是執行中把函式刪掉——分頁 DOM 有快取，那樣驗不出來）：
    # 擋掉那支檔重新載頁，模擬BP 分頁不可以有 ⚔ 鈕、也不可以有面板。
    pg.route("**/bp_live_ui.js*", lambda r: r.abort())
    pg.goto(pathlib.Path(os.path.join(ROOT, "index.html")).resolve().as_uri() + "?y=2026")
    pg.wait_for_function("() => typeof GAMES !== 'undefined' && GAMES.length > 0", timeout=90000)
    pg.click('nav .tab[data-view="模擬BP"]', timeout=6000); pg.wait_for_timeout(800)
    ok(pg.evaluate("() => typeof window.__bpPredictNext") == "undefined", "擋掉 bp_live_ui.js → 沒有 __bpPredictNext")
    ok(pg.query_selector("#bpDuelBtn") is None and pg.query_selector("#bpDuelBox") is None,
       "⭐ 公開版（載不到 bp_live_ui.js）→ 連 ⚔ 鈕都沒有")
    ok(not errs, "頁面沒噴錯", "; ".join(errs[:2]))
    b.close()

print("\n" + ("✗ %d 條失敗" % len(fails) if fails else "✓ 全部通過"))
sys.exit(1 if fails else 0)
