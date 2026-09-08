# -*- coding: utf-8 -*-
"""
抓 LoL Wiki 各「物件」頁面的 Patch history 區塊 → wiki_objectives.js
物件＝塔／兵營／主堡／小兵／龍／巴龍／預示者／野區 Buff 與野怪／河蟹…（召喚峽谷地圖目標）。
Riot 官方 patch notes 只到 2019；Wiki 可回溯到 2014 以前，故物件改版史一律走 Wiki。

用法：
    python fetch_wiki_objectives.py            # 每頁重抓並合併(新版本自動補入；抓失敗保留舊快取)
    python fetch_wiki_objectives.py --force    # 忽略舊快取、整頁以最新解析重建
    python fetch_wiki_objectives.py --only Baron_Nashor   # 只抓單一頁（測試用）

輸出 wiki_objectives.js = window.WIKI_OBJECTIVES = { wikiKey: { "patch": [中文改動行, ...], ... }, ... }
（wikiKey 對應 index.html 物件清單裡的 wiki 欄位）

2026-09-08（精進迴圈 #63）：每班 39.8s，17 頁全印「無新版」——17 次真的開頁（networkidle）＋ 17 × 1.2s 固定睡眠，
而這 17 頁一個月改不到幾次。現在先用一次 MediaWiki API 導覽（`API_URL`，urllib 直打會被 Cloudflare 403、
瀏覽器導覽 0.5s 就回來）拿全部頁面的目前 revid，跟 `REV_CACHE`（csv_cache/wiki_obj_revids.json）比：
revid 沒變、頁面快取還在 ⇒ 那頁不開、不睡，直接沿用快取；變了／沒記錄／API 失敗 ⇒ 照舊開頁解析。
睡眠改成「兩次真的開頁之間至少隔 DELAY 秒」（頁面載入本身通常就超過，睡眠幾乎歸零）。
解析規則改了要把 `CACHE_VER` +1（簽章含 EXTRACT_JS），--force 一律全抓。
"""
import hashlib, json, os, re, sys, time, urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT     = Path(__file__).resolve().parent.parent
OUT_DIR  = ROOT / "csv_cache/wiki_obj"
OUT_JS   = ROOT / "wiki_objectives.js"
# revid 快取**不能放進 OUT_DIR**：那裡的 *.json 全部會被當成頁面快取讀進 all_data
REV_CACHE = ROOT / "csv_cache/wiki_obj_revids.json"
WIKI_URL = "https://wiki.leagueoflegends.com/en-us/{}"
API_URL  = ("https://wiki.leagueoflegends.com/en-us/api.php?action=query&prop=revisions&rvprop=ids"
            "&format=json&formatversion=2&titles={}")
DELAY    = 1.2
CACHE_VER = 1   # EXTRACT_JS／norm_pk／parse_page 的規則改了就 +1，讓全部頁面重抓一次

FORCE = "--force" in sys.argv
ONLY  = None
if "--only" in sys.argv:
    i = sys.argv.index("--only"); ONLY = sys.argv[i+1] if i+1 < len(sys.argv) else None

OUT_DIR.mkdir(parents=True, exist_ok=True)

# 物件 → Wiki 頁面 key（召喚峽谷地圖目標）。多個儀表板物件可共用同一頁（各種塔→Turret）
PAGES = [
    "Turret", "Inhibitor", "Nexus",
    "Minion_(League_of_Legends)", "Super_Minion",
    "Baron_Nashor", "Rift_Herald", "Voidgrubs", "Atakhan",
    "Dragon",  # 元素龍＋遠古龍共用（Dragon pit 頁；Elder_Dragon 頁沒有 Patch History 區，2026-07-17 探測）
    "Blue_Sentinel", "Red_Brambleback", "Rift_Scuttler",
    "Gromp", "Ancient_Krug", "Murk_Wolf", "Crimson_Raptor",
]

# 新版 Wiki：標題包在 <div class="mw-heading mw-heading2"> 內；Patch history 內容在該容器後的
# 一個包裹 <div> 裡，DL(版本 dt>a>V26.13) 與 UL(該版改動) 交替。取那個 DIV 的 children 解析。
EXTRACT_JS = r"""() => {
    const results = [];
    let head = document.getElementById('Patch_History');
    if (!head) return results;
    const container = head.closest('.mw-heading') || head;
    let box = container.nextElementSibling;
    // 跳過 dablink 消歧框等雜項：只在「本身是 DL/UL、或內含 DL/UL 的 DIV」停下（Dragon 頁標題後夾一個 DIV.dablink）
    while (box && !(box.classList && box.classList.contains('mw-heading'))
           && box.tagName !== 'DL' && box.tagName !== 'UL'
           && !(box.tagName === 'DIV' && box.querySelector(':scope > dl, :scope > ul'))) box = box.nextElementSibling;
    if (!box || (box.classList && box.classList.contains('mw-heading'))) return results;
    let nodes;
    if (box.tagName === 'DIV') nodes = Array.from(box.children);
    else { nodes = []; let e = box; while (e && !(e.classList && e.classList.contains('mw-heading'))) { nodes.push(e); e = e.nextElementSibling; } }
    let curVer = null;
    const ownText = li => {
        let t = '';
        for (const node of li.childNodes) {
            if (node.nodeType === 3) t += node.textContent;
            else if (node.tagName === 'UL' || node.tagName === 'DL') {}
            else if (node.nodeType === 1) {
                if (node.tagName === 'SPAN' && node.classList.contains('inline-image'))
                    t += (node.textContent || '').replace(/\s+/g, ' ').trim();
                else t += node.textContent;
            }
        }
        return t.replace(/\s+/g, ' ').trim();
    };
    const walk = (li, prefix) => {
        const t = ownText(li);
        const sub = li.querySelector(':scope > ul');
        if (sub) {
            const isName = t && t.length <= 40 && !/⇒|reduced|increased|changed|removed|now/i.test(t);
            const pfx = isName ? t : prefix;
            if (t && !isName) results.push({ ver: curVer, line: prefix ? (prefix + '｜' + t) : t });
            for (const c of sub.children) if (c.tagName === 'LI') walk(c, pfx);
        } else if (t) {
            results.push({ ver: curVer, line: prefix ? (prefix + '｜' + t) : t });
        }
    };
    for (const el of nodes) {
        if (el.tagName === 'DL') {
            const a = el.querySelector('dt a, dt');
            if (a) { const x = a.textContent.trim(); if (/^V\d/.test(x)) curVer = x.replace(/^V/, ''); }
        } else if (el.tagName === 'UL' && curVer) {
            for (const li of el.children) if (li.tagName === 'LI') walk(li, null);
        }
    }
    return results;
}"""

def norm_pk(ver):
    """Wiki 版本字串 → patch key。序號版(4.x=2014…14.x=2024)換成年份%100；2025 起(25.x/26.x)沿用；
    2025 分季版(25.S1.2)保留 S 記法。回傳兩位年.兩位minor（分季版特殊）。"""
    ver = ver.strip()
    m = re.match(r"^(\d+)\.S(\d+)\.(\d+)$", ver)     # 25.S1.2 分季版
    if m:
        yy = int(m.group(1)); yy = yy + 10 if yy <= 14 else yy
        return f"{yy:02d}.S{m.group(2)}.{m.group(3)}"
    m = re.match(r"^(\d+)\.(\d+)([a-z])?$", ver)
    if not m:
        return None
    major, minor = int(m.group(1)), int(m.group(2))
    if major <= 14:
        major += 10                                  # 序號版 4..14 → 年份 14..24
    return f"{major:02d}.{minor:02d}"

def pk_sort(pk):
    """patch key → 可排序 tuple（含分季版 25.S1.2）。"""
    return tuple(int(n) for n in re.findall(r"\d+", pk))

def parse_page(page):
    items = page.evaluate(EXTRACT_JS)
    by_ver = {}
    for it in items:
        pk = norm_pk(it["ver"] or "")
        if not pk:
            continue
        by_ver.setdefault(pk, []).append(it["line"])
    return by_ver

def _parser_sig():
    """解析規則簽章：CACHE_VER 或 EXTRACT_JS 變了，舊 revid 記錄一律作廢（頁面沒變但解析會變）。"""
    return hashlib.sha1((str(CACHE_VER) + EXTRACT_JS).encode("utf-8")).hexdigest()

def _load_revs():
    """讀上次記下的 {key: revid}；檔案沒有／壞掉／解析簽章不同 ⇒ 空 dict（＝全部重抓）。"""
    try:
        d = json.loads(REV_CACHE.read_text(encoding="utf-8"))
        if d.get("parser") == _parser_sig() and isinstance(d.get("pages"), dict):
            return dict(d["pages"])
    except Exception:
        pass
    return {}

def _save_revs(pages):
    REV_CACHE.write_text(json.dumps({"parser": _parser_sig(), "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                                     "pages": pages}, ensure_ascii=False, indent=1), encoding="utf-8")

def _query_revids(pg, keys):
    """一次 API 導覽拿全部頁面目前的 revid → {key: revid}。失敗回 None（呼叫端退回全抓）。
    urllib 直打 api.php 會被 Cloudflare 403；用同一個瀏覽器 goto 就過得去（回應是 <pre> 包的 JSON）。
    API 會把 key 的底線正規化成空白（回應帶 normalized: from→to），用它對回我們的 key。"""
    url = API_URL.format(urllib.parse.quote("|".join(keys), safe="|()"))
    try:
        pg.goto(url, wait_until="domcontentloaded", timeout=30000)
        q = json.loads(pg.inner_text("body"))["query"]
        back = {n["to"]: n["from"] for n in (q.get("normalized") or [])}
        out = {}
        for p in q.get("pages") or []:
            if p.get("missing"):
                continue
            title = p.get("title") or ""
            key = back.get(title, title.replace(" ", "_"))
            rv = (p.get("revisions") or [{}])[0].get("revid")
            if key and rv:
                out[key] = rv
        return out
    except Exception as e:
        print(f"  ⚠ revid 查詢失敗（{str(e)[:80]}）→ 全部重抓")
        return None

def fetch_all():
    pages = [ONLY] if ONLY else PAGES
    all_data = {}
    for f in OUT_DIR.glob("*.json"):
        all_data[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    revs = {} if FORCE else _load_revs()   # --force：不沿用，但抓完仍記下 revid 讓下一班能沿用
    n_skip = n_fetch = 0

    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        pg = br.new_page()
        pg.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})
        cur = _query_revids(pg, pages)          # None＝API 失敗 ⇒ 全部照舊開頁
        last_req = time.time() if cur is not None else 0.0
        for i, key in enumerate(pages):
            cf = OUT_DIR / f"{key}.json"
            old = all_data.get(key, {})   # 既有快取：抓失敗就沿用，抓成功則合併(新版本進來)
            url = WIKI_URL.format(key)
            print(f"  [{i+1}/{len(pages)}] {key} → {url}", end=" ", flush=True)
            rv = (cur or {}).get(key)
            if rv and old and not FORCE and revs.get(key) == rv and cf.exists():
                vs = sorted(old, key=pk_sort)
                print(f"✓ {len(old)} 版（{vs[0]}–{vs[-1]}）｜revid {rv} 沒變 → 沿用快取")
                n_skip += 1
                continue
            # 節流：兩次「真的開頁」之間至少隔 DELAY 秒（載入本身通常就超過 ⇒ 幾乎不睡）；沿用的頁不計
            wait = DELAY - (time.time() - last_req)
            if wait > 0:
                time.sleep(wait)
            last_req = time.time()
            try:
                pg.goto(url, wait_until="networkidle", timeout=40000)
                by_ver = parse_page(pg)
                if not by_ver:
                    print("⚠ 無 Patch history（保留舊快取）")   # 解析不到就不動舊資料、也不記 revid（下一班再試）
                else:
                    merged = by_ver if FORCE else {**old, **by_ver}   # 每次重抓合併：新版本(如 26.14)自動補入、既有版本以最新解析為準；--force 則整頁重建
                    added = sorted(set(merged) - set(old), key=pk_sort)
                    cf.write_text(json.dumps(merged, ensure_ascii=False), encoding="utf-8")
                    all_data[key] = merged
                    if rv:
                        revs[key] = rv
                    vs = sorted(merged, key=pk_sort)
                    print(f"✓ {len(merged)} 版（{vs[0]}–{vs[-1]}）" + (f"｜新增 {added}" if added else "｜無新版"))
                n_fetch += 1
            except Exception as e:
                print(f"✗ {e}（保留舊快取）")
        br.close()
    if cur is not None:
        _save_revs(revs)
    print(f"  revid 沒變沿用 {n_skip} 頁／真的開頁 {n_fetch} 頁")
    return all_data

# ── 繁中化：套 fetch_patches / fetch_wiki 既有的句式轉換與術語字典 ──
from fetch_patches import translate_line

RE_CHG = re.compile(r"^(.*?)\s+(?:increased|decreased|reduced|lowered|changed|adjusted|raised)\s+to\s+(.+?)\s+from\s+(.+?)\.?$", re.I)

def zh_line(body):
    body = re.sub(r"\s+", " ", body).strip()
    m = RE_CHG.match(body)
    if m:
        body = f"{m.group(1)}：{m.group(3)} ⇒ {m.group(2)}"
    elif re.match(r"^New Effect[:\s]", body, re.I):
        body = "新增：" + re.sub(r"^New Effect[:\s]+", "", body, flags=re.I)
    elif re.match(r"^Removed[:\s]", body, re.I):
        body = "已移除：" + re.sub(r"^Removed[:\s]+", "", body, flags=re.I)
    try:
        return translate_line(body)
    except Exception:
        return body

def main():
    data = fetch_all()
    out = {}
    for key, by_ver in data.items():
        vout = {}
        for pk, lines in by_ver.items():
            zh = []
            seen = set()
            for l in lines:
                pre, sep, txt = l.partition("｜")
                body = (txt if sep else pre).strip()
                if len(body) < 2:
                    continue
                z = zh_line(body)
                if sep:
                    z = pre + "｜" + z
                try:
                    z = translate_line(z)   # 整行再過一次：讓 manual_tr.json（網頁版 Claude 翻譯回填，鍵＝整行）生效
                except Exception:
                    pass
                if z not in seen:
                    seen.add(z); zh.append(z)
            if zh:
                vout[pk] = zh
        if vout:
            out[key] = vout
    OUT_JS.write_text("window.WIKI_OBJECTIVES=" + json.dumps(out, ensure_ascii=False) + ";",
                      encoding="utf-8")
    tot = sum(len(v) for v in out.values())
    print(f"\n寫出 {OUT_JS.name}：{len(out)} 個物件、共 {tot} 個版本改動")

if __name__ == "__main__":
    main()
