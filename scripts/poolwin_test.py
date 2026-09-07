# -*- coding: utf-8 -*-
"""依局角色池時間窗：**只作用在直播疊圖，網頁一律照篩選列**（使用者 2026-09-07 定案）。

> 模擬BP頁面的 近一個月按鈕拿掉 網頁上永遠是依照篩選列顯示
> 只有直播疊圖的角色池顯示 遵守之前講的 第一局第二局第三局規則

所以這支要驗的是**兩條路的差異**（2026-09-05 的版本驗的是網頁會不會跟著縮，已整份改寫）：
  ① 📅 按鈕不在了
  ② 網頁的池（`selPool`）**不吃窗**
  ③ 疊圖那條路（`__bpAPI.withPoolWin` 包起來的 `selPool`）**吃窗**，且第 1 局嚴格小於網頁
  ④ 第 1~4 局：疊圖池的隻數單調不減（窗一階一階放寬），第 4 局＝全年＝跟網頁一樣
  ⑤ 場數／勝率不隨窗變（窗只決定成員）
  ⑥ 積分範圍照 🎯 近期積分自己的設定走，不跟著局號變

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

SETUP = """(arg) => {
  // 先把窗清成 null：等一下靠「它又被填回來」判斷**這一拍的重畫真的跑過了**，
  // 而不是沿用上一局留下的舊值（2026-09-07 #54：固定 sleep 1.1 秒在機器忙的時候不保證）。
  try{ window.__bpPoolWin = null; }catch(e){}
  const S = V.bpSim;
  const chs = arg.chs;
  const mk = (full) => { const g = """ + EMPTY + """;
    if (full) { for (let i=0;i<5;i++){ g.b1[i]=chs[i]; g.b2[i]=chs[i+5]; g.p1[i]=chs[i+10]; g.p2[i]=chs[i+15]; } }
    return g; };
  S.g = []; for (let i=0;i<5;i++) S.g.push(mk(i < arg.filled));
  S.n = 5; S.fp = [0,0,0,0,0]; S.side = [0,0,0,0,0]; S.meta = []; S.tm = [];
  S.t1 = arg.t1; S.t2 = arg.t2; S.pk1 = {}; S.pk2 = {};
  V.bpMode = "global";
  if (typeof rerender === 'function') rerender(); else render();
  return true;
}"""

# 網頁那條路 vs 疊圖那條路，**用同一個 selPool 量**（不看 DOM：DOM 還會被 used／版面影響）
READ = """() => {
  const w = window.__bpPoolWin || {};
  const api = window.__bpAPI;
  const count = (wrap) => {
    if (!api) return -1;
    let n = 0;
    api.POSN.forEach(pos => {
      const get = () => {
        const a = api.selPool(api.R1, pos, api.S.pk1, api.S.t1);
        const b = api.selPool(api.R2, pos, api.S.pk2, api.S.t2);
        return Object.keys((a && a.m) || {}).length + Object.keys((b && b.m) || {}).length;
      };
      n += wrap && api.withPoolWin ? api.withPoolWin(get) : get();
    });
    return n;
  };
  return { on: !!w.on, d: w.d, tier: w.tier, sq: w.sq, cut: w.cut || "",
           page: count(false), ovl: count(true),
           hasWith: !!(api && api.withPoolWin),
           chips: document.querySelectorAll(".bpPoolRow .bpChip").length };
}"""

# 便宜的探頭：只讀窗與盤面（不算池），給 settle() 輪詢用。
# ⚠ 不可以「等到 tier 等於期望值」——那樣測試永遠不會紅。這裡等的是**新鮮**（SETUP 清成 null 之後
#   又被重畫填回來）與**穩定**（連兩次一樣），算成什麼由下面的斷言去判。
PEEK = """() => {
  const w = window.__bpPoolWin;
  const S = V.bpSim, slots = g => [...g.b1, ...g.b2, ...g.p1, ...g.p2];
  const gs = S.g || [];
  const board = gs.map(g => slots(g).filter(x => !!x).length);
  let cg = -1;
  for (let i = 0; i < gs.length; i++) { if (slots(gs[i]).some(x => !x)) { cg = i; break; } }
  return { fresh: !!w, tier: w && w.tier, d: w && w.d, board: board, curGi: cg };
}"""


def settle(pg, tries=20, step=250):
    """等這一拍的重畫算完並穩定；回傳最後一次 PEEK（含盤面填充狀態，紅了要印出來）。"""
    prev, r = None, None
    for _ in range(tries):
        pg.wait_for_timeout(step)
        r = pg.evaluate(PEEK)
        if not r["fresh"]:
            continue                      # 還沒重畫（SETUP 已經把它清成 null）
        key = (r["tier"], r["d"], tuple(r["board"]), r["curGi"])
        if prev == key:
            return r                      # 連兩次一樣＝穩了
        prev = key
    return r


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

    print("① 📅 按鈕已移除（網頁不再有依局窗的概念）")
    ok(pg.query_selector("#bpPoolWin") is None, "篩選列沒有 #bpPoolWin")
    ok(pg.evaluate("() => typeof window.__bpPoolWinPaint") == "undefined",
       "__bpPoolWinPaint 掛鉤也拿掉了")

    print("\n② 兩條路：網頁不吃窗、疊圖吃窗")
    seen, peeks = [], []
    for gi in range(4):
        pg.evaluate(SETUP, {"t1": t1, "t2": t2, "chs": chs, "filled": gi})
        pk = settle(pg)
        peeks.append((gi, pk))
        r = pg.evaluate(READ)
        r["gi"] = gi
        seen.append(r)
        print("  第%d局：tier=%s 窗=%s 積分=%s天  網頁池=%d 疊圖池=%d  cut=%s"
              % (gi + 1, r["tier"], r["d"], r["sq"], r["page"], r["ovl"], r["cut"]))

    # 盤面站住了嗎（2026-09-07 #54 加的正控制）：SETUP 填了 gi 局，量的時候還要是那樣。
    #   少了這條，頁面若把盤面重置／去重，測試只會報一個對不上的 tier，
    #   下一輪得從頭猜「是窗算錯，還是盤面根本沒站住」（#52 就卡在這裡兩輪）。
    bad_b = [(gi, pk["board"]) for gi, pk in peeks
             if pk["board"] != [20] * gi + [0] * (5 - gi)]
    ok(not bad_b, "⭐ 每一局：SETUP 寫進去的盤面到量測當下還在",
       ("盤面被改了：" + str(bad_b[:2])) if bad_b else str([pk["board"] for _, pk in peeks]))
    ok(all(pk["fresh"] for _, pk in peeks), "每一局都等到這一拍重畫出來的窗（不是上一局的舊值）",
       str([pk["fresh"] for _, pk in peeks]))
    ok([pk["curGi"] for _, pk in peeks] == [0, 1, 2, 3], "curGi 跟著填好的局數走",
       str([pk["curGi"] for _, pk in peeks]))
    ok(all(s["hasWith"] for s in seen), "__bpAPI 有匯出 withPoolWin（疊圖靠它）")
    ok([s["tier"] for s in seen] == [0, 1, 2, 3], "階梯仍跟著局號走",
       str([s["tier"] for s in seen]))
    ok(seen[3]["d"] == 0 and seen[3]["cut"] == "", "第 4 局＝全年（不設窗）")

    # 網頁那條路：同一個盤面下，窗完全不該影響它 ⇒ 第 1 局的網頁池必須等於第 4 局的「無窗」口徑。
    # ⚠ 不能直接比第 1 局與第 4 局的網頁池——全局模式下前三局選過的英雄會被吃掉（Fearless），
    #   那是另一個機制。所以改成**同一拍**比較 page 與 ovl。
    g1 = seen[0]
    if g1["d"]:
        ok(g1["ovl"] < g1["page"], "⭐ 第 1 局：疊圖池比網頁池小（窗只作用在疊圖）",
           "%d < %d（窗 %s 天）" % (g1["ovl"], g1["page"], g1["d"]))
    else:
        notes.append("第 1 局就被保底放寬到全年（該隊窗內樣本太少），這一局比不出差異")
        ok(True, "第 1 局被保底放寬到全年（跳過差異比較）")
    ok(seen[3]["ovl"] == seen[3]["page"], "第 4 局：兩條路一樣（全年＝不設窗）",
       "%d vs %d" % (seen[3]["ovl"], seen[3]["page"]))

    print("\n③ 疊圖池：第 1~4 局單調不減（窗一階一階放寬）")
    ovs = [s["ovl"] for s in seen]
    pgs = [s["page"] for s in seen]
    ok(all(ovs[i] <= ovs[i + 1] for i in range(3)) or len(set([s["d"] for s in seen[:3]])) == 1,
       "疊圖池隻數不會越後面越小", str(ovs))
    ok(all(ovs[i] <= pgs[i] for i in range(4)), "任何一局：疊圖池都不會比網頁池大", str(list(zip(ovs, pgs))))

    print("\n④ 窗只決定成員，不動場數／勝率")
    pg.evaluate(SETUP, {"t1": t1, "t2": t2, "chs": chs, "filled": 0})
    settle(pg)
    stats = pg.evaluate("""() => {
      const api = window.__bpAPI, out = {};
      api.POSN.forEach(pos => {
        const page = api.selPool(api.R1, pos, api.S.pk1, api.S.t1);
        const ovl = api.withPoolWin(() => api.selPool(api.R1, pos, api.S.pk1, api.S.t1));
        Object.keys((ovl && ovl.m) || {}).forEach(ch => {
          const a = ovl.m[ch], z = (page && page.m || {})[ch];
          if (z) out[pos + "|" + ch] = [a.n, a.w, z.n, z.w];
        });
      });
      return out; }""")
    bad = [k for k, v in stats.items() if v[0] != v[2] or v[1] != v[3]]
    ok(len(stats) > 0, "兩條路有共同的英雄可比", "%d 隻" % len(stats))
    ok(not bad, "同一隻英雄的場數／勝率兩條路完全相同",
       ("不同：" + ", ".join(bad[:4])) if bad else "")

    print("\n⑤ 積分範圍照 🎯 自己的設定（不跟著局號變）")
    sqs = [s["sq"] for s in seen]
    ok(len(set(sqs)) == 1, "積分範圍不跟著局號變", str(sqs))
    ok(sqs[0] == pg.evaluate("() => +V.bpSqDays || 14"), "積分範圍＝🎯 的設定", str(sqs[0]))
    pg.evaluate("() => { V.bpSqDays = 30; }")
    pg.evaluate(SETUP, {"t1": t1, "t2": t2, "chs": chs, "filled": 0})
    settle(pg)
    ok(pg.evaluate(READ)["sq"] == 30, "改 🎯 天數之後 __bpPoolWin.sq 跟著變")

    print("\n⑥ 沒有 JS 錯誤")
    ok(not errs, "頁面沒噴錯", "; ".join(errs[:2]))
    b.close()

for n in notes:
    print("  ※ " + n)
print(("\n✓ 全部通過" if not fails else "\n✗ %d 條失敗" % len(fails)))
sys.exit(1 if fails else 0)
