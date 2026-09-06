# -*- coding: utf-8 -*-
"""網站本身的錯誤與英文版介面問題 —— 每一輪都掃，8 小時彙報一次（使用者 2026-09-06）。

掃什麼（每個分頁 × 繁中／英文）：
  ① pageerror（JS 未攔截的例外）與 console.error
  ② 破圖：可見的 <img> 載入失敗（naturalWidth=0）
  ③ 英文模式漏中文：#main 裡可見文字仍含 CJK（英雄名／說明文字沒翻到）
  ④ 分頁空白：切過去之後 #main 幾乎沒有內容
  ⑤ 網路 404（本站自己的資源）

**只讀**：不動 index.html、不動任何資料檔。發現寫進 autopilot/SITE_FINDINGS.json（指紋去重、
記首見／末見／次數）與 SITE_FINDINGS.md（給人看）。使用者定案：**這一線的改動要他同意才動**。

用法：
    python scripts/site_audit.py            # 掃一輪，印「這輪新增／仍在／消失」
    python scripts/site_audit.py --report   # 不掃，只把目前所有未解的發現整理成 8 小時彙報用的 Markdown
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
    L = ["# 網站稽核發現（自動產生，只讀掃描）", "",
         "最近一輪：%s　未解 %d 筆／已消失 %d 筆" % (db["runs"][-1]["at"] if db["runs"] else "–", len(open_), len(gone)), ""]
    if open_:
        L.append("## 未解")
        L.append("")
        L.append("| 分頁 | 語言 | 類型 | 內容 | 首見 | 末見 | 次數 |")
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
    io.open(MD, "w", encoding="utf-8").write("\n".join(L) + "\n")


def report(db):
    """8 小時彙報用：只列未解，按類型分組，附上「這段時間新出現的」標記。"""
    open_ = [(k, v) for k, v in db["findings"].items() if not v.get("gone")]
    if not open_:
        return "網站稽核：目前**沒有**未解的發現（分頁 × 繁中／英文全掃過）。"
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
    return "\n".join(L)


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
    if (el.closest('script,style,noscript,[lang="zh"],.zhOnly,.acctLink,a.acctLink')) continue;
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


def scan():
    from playwright.sync_api import sync_playwright
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"], cwd=ROOT,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    found = []          # (lang, tab, kind, text)
    tabs_seen = []
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(headless=True)
            for lang in LANGS:
                pg = br.new_page(viewport={"width": 1920, "height": 1080})
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
                for tb in tabs:
                    cur["tab"] = tb
                    okc = pg.evaluate("""(t) => { const el = [...document.querySelectorAll('nav .tab')]
                        .find(e => (e.dataset.view || e.textContent.trim()) === t); if (!el) return false; el.click(); return true; }""", tb)
                    if not okc:
                        found.append((lang, tb, "empty", "分頁籤點不到"))
                        continue
                    pg.wait_for_timeout(1400)
                    for it in pg.evaluate(COLLECT):
                        if it["kind"] == "cjk" and lang != "en":
                            continue
                        found.append((lang, tb, it["kind"], it["text"]))
                for tb, e in errs:
                    found.append((lang, tb, "pageerror", e))
                for tb, e in cons:
                    found.append((lang, tb, "console", e))
                for tb, u in nets:
                    found.append((lang, tb, "404", u))
                pg.close()
            br.close()
    finally:
        srv.kill()
    return found, tabs_seen


def main():
    db = load()
    if "--report" in sys.argv:
        print(report(db))
        return 0
    t0 = time.time()
    found, tabs = scan()
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
    for fp, v in db["findings"].items():
        if fp not in fps and not v.get("gone"):
            v["gone"] = True; gone.append(fp)
    db["runs"].append({"at": now, "tabs": len(tabs), "found": len(found), "new": len(new),
                       "gone": len(gone), "secs": round(time.time() - t0)})
    db["runs"] = db["runs"][-200:]
    save(db)
    print("網站稽核 %s：分頁 %d × %d 語言，%.0f 秒" % (now, len(tabs), len(LANGS), time.time() - t0))
    print("  發現 %d 筆：新增 %d／仍在 %d／消失 %d" % (len(found), len(new), len(still), len(gone)))
    for fp in new[:15]:
        v = db["findings"][fp]
        print("   + %s／%s／%s：%s" % (v["tab"], v["lang"], v["kind"], v["text"][:90]))
    if len(new) > 15:
        print("   …另 %d 筆新增" % (len(new) - 15))
    return 0


if __name__ == "__main__":
    sys.exit(main())
