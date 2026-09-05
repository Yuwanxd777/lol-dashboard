# -*- coding: utf-8 -*-
"""依局角色池時間窗（2026-09-05）的行為驗證。

不是只看「有沒有報錯」——真的把盤面推到第 1/2/3/4 局，量角色池的隻數會不會跟著放寬，
並且每一階都對照「關掉依局窗」的全年基準（正控制＋反控制）。

跑法：python scripts/poolwin_test.py
"""
import io, os, sys, json, pathlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails, notes = [], []


def ok(cond, label, detail=""):
    if cond:
        print("  ✓ " + label + (("  " + detail) if detail else ""))
    else:
        print("  ✗ " + label + (("  " + detail) if detail else ""))
        fails.append(label + " " + detail)


EMPTY = ('{b1:["","","","",""],b2:["","","","",""],p1:["","","","",""],p2:["","","","",""],'
         'pl1:["","","","",""],pl2:["","","","",""],plm1:["","","","",""],plm2:["","","","",""]}')

# 盤面：前 filled 局塞滿（用真的英雄名），其餘留空 → curGi = filled
SETUP = """(arg) => {
  const S = V.bpSim;
  const chs = arg.chs;
  const mk = (full) => { const g = """ + EMPTY + """;
    if (full) { for (let i=0;i<5;i++){ g.b1[i]=chs[i]; g.b2[i]=chs[i+5]; g.p1[i]=chs[i+10]; g.p2[i]=chs[i+15]; } }
    return g; };
  S.g = []; for (let i=0;i<5;i++) S.g.push(mk(i < arg.filled));
  // partial＝在目前這一局塞三手 PICK（局還沒選完，所以 curGi 不動），這樣才有選角評分可比
  if (arg.partial) { const g = S.g[arg.filled];
    for (let i=0;i<3;i++){ g.p1[i]=chs[i]; g.p2[i]=chs[i+3]; } }
  S.n = 5; S.fp = [0,0,0,0,0]; S.side = [0,0,0,0,0]; S.meta = []; S.tm = [];
  S.t1 = arg.t1; S.t2 = arg.t2; S.pk1 = {}; S.pk2 = {};
  V.bpMode = "global";
  if (arg.win === false) V.bpPoolWin = false; else delete V.bpPoolWin;
  if (typeof rerender === 'function') rerender(); else render();
  return true;
}"""

READ = """() => {
  const w = window.__bpPoolWin || {};
  const chips = document.querySelectorAll(".bpPoolRow .bpChip").length;
  return { on: !!w.on, d: w.d, tier: w.tier, sq: w.sq, cut: w.cut || "", chips: chips };
}"""

try:
    from playwright.sync_api import sync_playwright
except Exception as e:
    print("playwright 沒裝：" + str(e)[:80])
    sys.exit(2)

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width": 1920, "height": 1080})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)[:180]))
    pg.goto(pathlib.Path(os.path.join(ROOT, "index.html")).resolve().as_uri() + "?y=2026")
    pg.wait_for_timeout(3000)

    # ── 找一組真的常打的隊伍與 20 隻真英雄名 ────────────────────────────
    picked = pg.evaluate("""() => {
      const cnt = {}, pair = {};
      for (const o of GAMES) {
        const a = o.raw[C.blue_teamname], z = o.raw[C.red_teamname];
        if (!a || !z) continue;
        cnt[a] = (cnt[a]||0)+1; cnt[z] = (cnt[z]||0)+1;
        const k = a < z ? a+"|"+z : z+"|"+a; pair[k] = (pair[k]||0)+1;
      }
      let best = null, bn = 0;
      for (const k in pair) { const [a,z] = k.split("|");
        const s = Math.min(cnt[a]||0, cnt[z]||0);
        if (pair[k] >= 2 && s > bn) { bn = s; best = [a,z]; } }
      const chs = [];
      for (const o of LANES) { const c = o.raw[C.blue_champion];
        if (c && chs.indexOf(c) < 0) chs.push(c); if (chs.length >= 20) break; }
      return { t1: best && best[0], t2: best && best[1], chs: chs, n: bn };
    }""")

    if not picked or not picked.get("t1") or len(picked.get("chs") or []) < 20:
        print("找不到可用的隊伍／英雄樣本：" + json.dumps(picked, ensure_ascii=False)[:160])
        b.close(); sys.exit(2)

    t1, t2, chs = picked["t1"], picked["t2"], picked["chs"]
    print("樣本：%s vs %s（出賽較少的一隊 %d 局）\n" % (t1, t2, picked["n"]))

    pg.click('nav .tab[data-view="模擬BP"]', timeout=6000)
    pg.wait_for_timeout(900)

    # ── ① 關掉依局窗＝全年基準（反控制）──────────────────────────────
    print("① 關掉依局窗（全年基準）")
    pg.evaluate(SETUP, {"t1": t1, "t2": t2, "chs": chs, "filled": 0, "win": False})
    pg.wait_for_timeout(1100)
    base = pg.evaluate(READ)
    ok(base["on"] is False, "關掉時 __bpPoolWin.on = false", json.dumps(base, ensure_ascii=False))
    ok(base["chips"] > 0, "全年基準有池", "%d 隻" % base["chips"])
    FULL = base["chips"]
    # 第 4 局要比的是「同一個盤面、關掉窗」的基準：全局模式下前三局已選的英雄會被 used 吃掉，
    # 拿空盤面的數字去比會多算 18 隻（2026-09-05 這支測試自己踩過的坑）
    pg.evaluate(SETUP, {"t1": t1, "t2": t2, "chs": chs, "filled": 3, "win": False})
    pg.wait_for_timeout(1100)
    FULL3 = pg.evaluate(READ)["chips"]
    print("  （第 4 局用的同盤面基準：%d 隻）" % FULL3)

    # ── ② 第 1~4 局：窗要一階一階放寬，池只能越來越大 ─────────────────
    print("\n② 依局窗開啟：第 1~4 局")
    seen = []
    for gi in range(4):
        pg.evaluate(SETUP, {"t1": t1, "t2": t2, "chs": chs, "filled": gi, "win": True})
        pg.wait_for_timeout(1100)
        r = pg.evaluate(READ)
        r["gi"] = gi
        seen.append(r)
        print("  第%d局：tier=%s 窗=%s 積分=%s天 池=%d 隻  cut=%s"
              % (gi + 1, r["tier"], r["d"], r["sq"], r["chips"], r["cut"]))

    ok(all(s["on"] for s in seen), "四局都認得出局號（on=true）")
    ok([s["tier"] for s in seen] == [0, 1, 2, 3], "階梯跟著局號走",
       str([s["tier"] for s in seen]))
    # 積分範圍照 🎯 的設定走（使用者 2026-09-05）：不可以跟著局號自己變
    sqs = [s["sq"] for s in seen]
    ok(len(set(sqs)) == 1, "積分範圍不跟著局號變（📅 只管比賽池）", str(sqs))
    ok(sqs[0] == pg.evaluate("() => +V.bpSqDays || 14"), "積分範圍＝🎯 的設定", str(sqs[0]))
    ok(seen[3]["d"] == 0 and seen[3]["cut"] == "", "第 4 局＝全年（不設窗）")
    ok(seen[3]["chips"] == FULL3, "第 4 局的池＝同盤面的全年基準",
       "%d vs %d" % (seen[3]["chips"], FULL3))

    sizes = [s["chips"] for s in seen]
    ok(all(sizes[i] <= sizes[i + 1] for i in range(3)), "池的隻數單調不減（越後面局越寬）", str(sizes))

    # 真的有篩到東西（不然「窗」等於沒作用，是最典型的假綠）
    win_days = [s["d"] for s in seen]
    if 0 in win_days[:3]:
        notes.append("第 %d 局就被保底放寬到全年（該隊窗內樣本太少）" % (win_days.index(0) + 1))
        ok(True, "保底有作動（窗內池 < 15 隻 → 放寬）", str(win_days))
    else:
        ok(sizes[0] < FULL, "第 1 局的池真的比全年小（窗有作用）",
           "%d < %d" % (sizes[0], FULL))
        ok(win_days == [30, 90, 180, 0], "窗＝30/90/180/全年", str(win_days))

    # ── ③ 場數與勝率不能跟著窗縮水（只篩成員、不動數字）────────────────
    print("\n③ 窗只篩成員、不動數字")
    pg.evaluate(SETUP, {"t1": t1, "t2": t2, "chs": chs, "filled": 0, "win": True})
    pg.wait_for_timeout(1100)
    g1 = pg.evaluate("""() => { const o = {};
      // ⚠ 一定要**逐列**收（同一隻英雄會出現在好幾位選手的池裡）。只用英雄名當鍵，
      // 隻數多的那一階會用別人的同名英雄蓋掉，看起來就像「場數變了」（這支測試踩過）。
      document.querySelectorAll(".bpPoolRow").forEach((row, ri) => {
        const pl = (row.querySelector(".bpPlName") || {}).textContent || "";
        row.querySelectorAll(".bpChip").forEach(c => { o[ri + "|" + pl + "|" + c.dataset.ch] = c.title; });
      });
      return o; }""")
    pg.evaluate(SETUP, {"t1": t1, "t2": t2, "chs": chs, "filled": 3, "win": True})
    pg.wait_for_timeout(1100)
    g4 = pg.evaluate("""() => { const o = {};
      // ⚠ 一定要**逐列**收（同一隻英雄會出現在好幾位選手的池裡）。只用英雄名當鍵，
      // 隻數多的那一階會用別人的同名英雄蓋掉，看起來就像「場數變了」（這支測試踩過）。
      document.querySelectorAll(".bpPoolRow").forEach((row, ri) => {
        const pl = (row.querySelector(".bpPlName") || {}).textContent || "";
        row.querySelectorAll(".bpChip").forEach(c => { o[ri + "|" + pl + "|" + c.dataset.ch] = c.title; });
      });
      return o; }""")
    import re
    PRO = re.compile("選 (\d+) 場 勝率 (\d+)%｜被對手禁 (\d+) 次")
    def pro(t):
        m = PRO.search(t or "")
        return m.group(0) if m else None
    common = [k for k in g1 if k in g4 and pro(g1[k]) and pro(g4[k])]
    diff = [k for k in common if pro(g1[k]) != pro(g4[k])]
    if diff:
        for k in diff[:3]:
            print("    " + k)
            print("    第1局：" + g1[k])
            print("    第4局：" + g4[k])
    ok(len(common) > 0, "兩階有共同的英雄可比", "%d 隻" % len(common))
    ok(not diff, "同一隻英雄的比賽場數／勝率兩階完全相同",
       ("不同：" + ", ".join(diff[:4])) if diff else "")

    # ── ④ 按鈕：面上寫的就是實際生效的那一階，點一下要能關 ──────────────
    print("\n④ 📅 按鈕")
    btn = pg.query_selector("#bpPoolWin")
    ok(btn is not None, "篩選列有 📅 按鈕")
    if btn:
        pg.evaluate(SETUP, {"t1": t1, "t2": t2, "chs": chs, "filled": 0, "win": True})
        pg.wait_for_timeout(1100)
        face_on = pg.eval_on_selector("#bpPoolWin", "e=>e.textContent")
        cur = pg.evaluate(READ)
        want = {30: "近一個月", 90: "近三個月", 180: "近半年", 0: "全年"}[cur["d"]]
        ok(want in face_on, "鈕面寫的是實際生效的那一階", "面='%s' 期待含 '%s'" % (face_on.strip(), want))
        pg.click("#bpPoolWin"); pg.wait_for_timeout(1100)
        off = pg.evaluate(READ)
        ok(off["on"] is False, "點一下關掉")
        ok(off["chips"] == FULL, "關掉之後回到全年的池", "%d vs %d" % (off["chips"], FULL))
        pg.click("#bpPoolWin"); pg.wait_for_timeout(1100)
        back = pg.evaluate(READ)
        ok(back["on"] is True, "再點一下開回來")

    # ── ④b 改 🎯 的天數，📅 這邊要跟著動（同一個設定只有一個來源）──────
    print("\n④b 積分範圍跟著 🎯 走")
    pg.evaluate("() => { V.bpSqDays = 30; }")
    pg.evaluate(SETUP, {"t1": t1, "t2": t2, "chs": chs, "filled": 0, "win": True})
    pg.wait_for_timeout(1100)
    ok(pg.evaluate(READ)["sq"] == 30, "🎯 改成一個月 → 積分範圍跟著變 30 天")
    pg.evaluate("() => { V.bpSqDays = 14; }")

    # ── ⑤ 選角評分不可以跟著窗變 ────────────────────────────────────
    # 評分問的是「這隻他熟不熟」，那是母體問題，不是「他現在可能選什麼」。
    # 用窗過的池去算，三個月前打過 20 場的英雄會被當成沒打過（熟練度掉成中性 50）。
    print("\n⑤ 選角評分不吃時間窗")
    SC = '''() => [...document.querySelectorAll(".bsScore")].map(e => e.textContent.trim()).filter(t => t)'''
    pg.evaluate(SETUP, {"t1": t1, "t2": t2, "chs": chs, "filled": 0, "win": True, "partial": True})
    pg.wait_for_timeout(1300)
    sc_on = pg.evaluate(SC)
    w_on = pg.evaluate(READ)
    pg.evaluate(SETUP, {"t1": t1, "t2": t2, "chs": chs, "filled": 0, "win": False, "partial": True})
    pg.wait_for_timeout(1300)
    sc_off = pg.evaluate(SC)
    ok(len(sc_on) > 0 and any(any(c.isdigit() for c in t) for t in sc_on), "有算出評分可比", str(sc_on[:1]))
    ok(w_on["d"] and w_on["d"] != 0, "比較時窗確實是開著的（不是兩邊都全年的假綠）", "窗=%s" % w_on["d"])
    ok(sc_on == sc_off, "窗開與窗關的評分完全相同",
       ("開=%s / 關=%s" % (sc_on[:1], sc_off[:1])) if sc_on != sc_off else "")

    # ── ⑥ 沒有任何 JS 例外 ───────────────────────────────────────────
    print("\n⑥ 頁面例外")
    ok(not errs, "全程沒有 pageerror", (errs[0] if errs else ""))
    b.close()

print("")
for nt in notes:
    print("⚠ " + nt)
if fails:
    print("✗ %d 條失敗" % len(fails))
    sys.exit(1)
print("✓ 全部通過")
sys.exit(0)
