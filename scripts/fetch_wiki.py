# -*- coding: utf-8 -*-
"""
用 Playwright 抓 LoL Wiki 各英雄 Patch_history 頁面
輸出 wiki_patches.js：補充 fetch_patches.py 抓不到的歷史版本（2019 年以前）

用法：
    python fetch_wiki.py              # 只補缺的（已快取就跳過）
    python fetch_wiki.py --force      # 全部重抓
    python fetch_wiki.py --champ Aatrox  # 只抓特定英雄（測試用）
"""
import json, os, re, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT      = Path(__file__).resolve().parent.parent  # 專案根目錄（本腳本在 scripts\ 內）
OUT_DIR   = ROOT / "csv_cache/wiki"
OUT_JS    = ROOT / "wiki_patches.js"
DDV_URL   = "https://ddragon.leagueoflegends.com/api/versions.json"
WIKI_BASE = "https://wiki.leagueoflegends.com/en-us/{}/Patch_history"
DELAY     = 1.2   # 每頁間隔秒數，避免被封

FORCE  = "--force" in sys.argv
SINGLE = None
if "--champ" in sys.argv:
    i = sys.argv.index("--champ")
    SINGLE = sys.argv[i+1] if i+1 < len(sys.argv) else None

OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── JS：在瀏覽器頁面裡執行，解析 dl+ul 結構 ──────────────────────────────────
EXTRACT_JS = """() => {
    const results = [];
    const content = document.querySelector('.mw-parser-output') || document.body;
    const children = Array.from(content.children);
    let curVer = null;
    for (const el of children) {
        if (el.tagName === 'DL') {
            const a = el.querySelector('dt a');
            if (a) {
                const txt = a.textContent.trim();
                if (/^V\\d/.test(txt)) curVer = txt.replace(/^V/, '');
            }
        } else if (el.tagName === 'UL' && curVer) {
            // li 自身文字（不含巢狀 UL；黑名單制保留小數等內容）
            // inline-image（英雄/道具 icon 連結）取名稱：優先 span 文字→a title→img alt→href 尾段，避免掉字變「、、、」
            const iconName = node => {
                let nm = (node.textContent || '').replace(/\\s+/g, ' ').trim();
                if (nm) return nm;
                const a = node.querySelector && node.querySelector('a');
                const im = node.querySelector && node.querySelector('img');
                nm = (a && (a.getAttribute('title') || '').trim()) ||
                     (im && (im.getAttribute('alt') || '').trim()) || '';
                if (!nm && a) { const h = a.getAttribute('href') || ''; nm = decodeURIComponent((h.split('/').pop() || '')).replace(/_/g, ' '); }
                return nm;
            };
            const ownText = li => {
                let t = '';
                for (const node of li.childNodes) {
                    if (node.nodeType === 3) { t += node.textContent; }
                    else if (node.tagName === 'UL') {}
                    else if (node.nodeType === 1) {
                        if (node.tagName === 'SPAN' && node.classList.contains('inline-image'))
                            t += iconName(node);
                        else
                            t += node.textContent;
                    }
                }
                return t.replace(/\\s+/g, ' ').trim();
            };
            // li 自身（非巢狀子項）的 data-ability
            const abilOf = li => {
                for (const node of li.childNodes) {
                    if (node.nodeType === 1 && node.tagName !== 'UL') {
                        if (node.matches && node.matches('[data-ability]')) return node.getAttribute('data-ability');
                        const a = node.querySelector && node.querySelector('[data-ability]');
                        if (a) return a.getAttribute('data-ability');
                    }
                }
                return null;
            };
            // 巢狀結構：父項是技能名 → 子行繼承為前綴
            // 錯誤修正條目：父行以 Fixed/Rescripted/Bug fix/Undocumented 開頭 → 整棵子樹（含無關鍵字的子行，如
            // "Now uses edge range..."）都前綴 [錯誤修正]，讓前端 COSM 一致過濾（快取攤平後就救不回親子關係，必須在擷取時標）
            const BUGFIX = /^(fixed|rescripted|bug\s?fix|undocumented|no longer (?:incorrectly|erroneously))/i;
            // 修正條目的「接續兄弟行」（wiki 常把說明拆成同層下一顆子彈）：無數值箭頭、以 Now/No longer/It now 開頭 → 一併標記
            const FIXCONT = /^(now |no longer |it (now|no longer) |this )/i;
            let prevFix = false; // 同層前一顆子彈是否為修正行
            const walk = (li, prefix, inFix) => {
                const t = ownText(li);
                const ab = abilOf(li) || prefix;
                const fix = inFix || (t && BUGFIX.test(t)) || (prevFix && t && FIXCONT.test(t) && !/⇒|from \d|to \d/i.test(t));
                const tag = fix ? '[錯誤修正] ' : '';
                const sub = li.querySelector(':scope > ul');
                if (sub) {
                    // 父項若只是技能名（短、無數據箭頭）→ 只當前綴、一律不當內容
                    //（帶 data-ability 的名稱列以前會被推入 → 產生「樂音高亢｜樂音高亢」回音行，2026-07-16 修）
                    const isName = t && t.length <= 40 && !/⇒|reduced|increased|changed/i.test(t);
                    const pfx = abilOf(li) || (isName ? t : prefix);
                    if (t && !isName)
                        results.push({ ver: curVer, line: ab ? (ab + '｜' + tag + t) : (tag + t) });
                    const keep = prevFix; prevFix = false;                       // 子層有自己的兄弟序
                    for (const c of sub.children) if (c.tagName === 'LI') walk(c, pfx, fix);
                    prevFix = keep;
                } else if (t) {
                    results.push({ ver: curVer, line: ab ? (ab + '｜' + tag + t) : (tag + t) });
                }
                prevFix = fix; // 記給同層下一顆子彈
            };
            prevFix = false;
            for (const li of el.children) if (li.tagName === 'LI') walk(li, null, false);
        }
    }
    return results;
}"""

def champ_list():
    """從 DDragon 取全部英雄 key（URL 用名，如 Jarvan IV → JarvanIV）"""
    import urllib.request
    ver = json.loads(urllib.request.urlopen(DDV_URL, timeout=10).read())[0]
    data = json.loads(urllib.request.urlopen(
        f"https://ddragon.leagueoflegends.com/cdn/{ver}/data/en_US/champion.json",
        timeout=15).read())
    return sorted(data["data"].keys())  # e.g. ["Aatrox","Ahri","Akali",...]

def wiki_key(champ_id):
    """DDragon ID → Wiki URL key（空格/撇號/大小寫等差異）"""
    fixes = {
        "MonkeyKing":   "Wukong",
        "AurelionSol":  "Aurelion_Sol",
        "Belveth":      "Bel%27Veth",
        "Chogath":      "Cho%27Gath",
        "DrMundo":      "Dr._Mundo",
        "JarvanIV":     "Jarvan_IV",
        "KSante":       "K%27Sante",
        "Kaisa":        "Kai%27Sa",
        "Khazix":       "Kha%27Zix",
        "KogMaw":       "Kog%27Maw",
        "Leblanc":      "LeBlanc",
        "LeeSin":       "Lee_Sin",
        "MasterYi":     "Master_Yi",
        "MissFortune":  "Miss_Fortune",
        "RekSai":       "Rek%27Sai",
        "Renata":       "Renata_Glasc",
        "TahmKench":    "Tahm_Kench",
        "TwistedFate":  "Twisted_Fate",
        "Velkoz":       "Vel%27Koz",
        "XinZhao":      "Xin_Zhao",
    }
    return fixes.get(champ_id, champ_id)

def parse_page(page):
    """回傳 {patch: [lines], ...}"""
    items = page.evaluate(EXTRACT_JS)
    by_ver = {}
    for it in items:
        v = it["ver"]
        by_ver.setdefault(v, []).append(it["line"])
    return by_ver

def fetch_all():
    force = FORCE
    if SINGLE:
        champs = [SINGLE]
    else:
        print("取得英雄列表…")
        champs = champ_list()
        print(f"共 {len(champs)} 位英雄")

    all_data = {}   # {patch: {champ: [lines]}}
    # 讀已有快取
    for f in OUT_DIR.glob("*.json"):
        champ = f.stem
        cached = json.loads(f.read_text(encoding="utf-8"))
        for ver, lines in cached.items():
            all_data.setdefault(ver, {})[champ] = lines

    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        pg = br.new_page()
        pg.set_extra_http_headers({"Accept-Language": "en-US,en;q=0.9"})

        for i, champ in enumerate(champs):
            cf = OUT_DIR / f"{champ}.json"
            if not force and cf.exists():
                print(f"  [{i+1}/{len(champs)}] {champ} 已快取，跳過")
                continue

            wkey = wiki_key(champ)
            url  = WIKI_BASE.format(wkey)
            print(f"  [{i+1}/{len(champs)}] {champ} → {url}", end=" ", flush=True)
            try:
                pg.goto(url, wait_until="networkidle", timeout=30000)
                by_ver = parse_page(pg)
                if not by_ver:
                    print("⚠ 無資料")
                else:
                    cf.write_text(json.dumps(by_ver, ensure_ascii=False), encoding="utf-8")
                    for ver, lines in by_ver.items():
                        all_data.setdefault(ver, {})[champ] = lines
                    print(f"✓ {len(by_ver)} 版")
            except Exception as e:
                print(f"✗ {e}")
            time.sleep(DELAY)

        br.close()

    return all_data

# ── 繁中化：wiki 句式 → 儀表板標準「X：舊 ⇒ 新」格式，再套 fetch_patches 的術語字典 ──
from fetch_patches import translate, translate_line

# DDragon championFull（en/zh）→ 每隻英雄的技能名對照＋全英雄名對照（官方翻譯，精準）
def load_name_maps():
    import urllib.request
    def getf(lang, ver, tag):
        f = OUT_DIR.parent / f"chfull_{lang}_{tag}.json"
        if not f.exists():
            url = f"https://ddragon.leagueoflegends.com/cdn/{ver}/data/{lang}/championFull.json"
            f.write_bytes(urllib.request.urlopen(url, timeout=120).read())
        return json.loads(f.read_text(encoding="utf-8"))["data"]
    cur = json.loads(urllib.request.urlopen(DDV_URL, timeout=10).read())[0]
    abil = {}   # champ id → {en ability name: zh ability name}
    cname = {}  # en champ name → zh champ name
    # 目前版本優先寫入；再用歷史版本補「重做前的舊技能名」。每年頭尾都取樣，
    # 涵蓋年中改名的技能（如 Sigil of Silence 只存在 4.1–4.9）
    for ver, tag in [(cur, "cur"),
                     ("8.24.1", "8b"), ("8.1.1", "8a"), ("7.24.2", "7b"), ("7.1.1", "7a"),
                     ("6.24.1", "6b"), ("6.1.1", "6a"), ("5.24.2", "5b"), ("5.1.1", "5a"),
                     ("4.21.5", "4b"), ("4.1.2", "4a")]:
        try:
            en, zh = getf("en_US", ver, tag), getf("zh_TW", ver, tag)
        except Exception as e:
            print(f"  （championFull {ver} 載入失敗：{e}）")
            continue
        for cid, e in en.items():
            z = zh.get(cid)
            if not z:
                continue
            cname.setdefault(e["name"], z["name"])
            m = abil.setdefault(cid, {})
            m.setdefault(e["passive"]["name"], z["passive"]["name"])
            for se, sz in zip(e["spells"], z["spells"]):
                m.setdefault(se["name"], sz["name"])
    return abil, cname

_ABIL, _CNAME = None, None
_CNAME_RE = None

RE_CHG  = re.compile(r"^(.*?)\s+(?:increased|decreased|reduced|lowered|changed|adjusted)\s+to\s+(.+?)\s+from\s+(.+?)\.?$", re.I)
RE_NEW  = re.compile(r"^New Effect[:\s]+(.*)$", re.I)
RE_REM  = re.compile(r"^Removed[:\s]+(.*)$", re.I)
JUNK_RE = re.compile(r"^(Stats|General|Abilities|Added|Removed|Sound|Voice|Full Relaunch|New)\.?$", re.I)

def zh_line(body):
    body = body.strip()
    m = RE_CHG.match(body)
    if m:
        body = f"{m.group(1)}：{m.group(3)} ⇒ {m.group(2)}"
    else:
        m = RE_NEW.match(body)
        if m:
            body = "新增：" + m.group(1)
        else:
            m = RE_REM.match(body)
            if m:
                body = "已移除：" + m.group(1)
    return translate_line(body)

def clean_lines(lines, champ=None):
    global _ABIL, _CNAME, _CNAME_RE
    if _ABIL is None:
        try:
            _ABIL, _CNAME = load_name_maps()
            names = sorted(_CNAME, key=len, reverse=True)
            _CNAME_RE = re.compile(r"(?<![A-Za-z])(" + "|".join(re.escape(n) for n in names) + r")(?![A-Za-z])")
        except Exception as e:
            print(f"（技能/英雄名對照載入失敗，僅用術語字典：{e}）")
            _ABIL, _CNAME, _CNAME_RE = {}, {}, None
    amap = _ABIL.get(champ, {})
    out = []
    for l in lines:
        pre, sep, txt = l.partition("｜")
        body = (txt if sep else pre).strip()
        if JUNK_RE.match(body):
            continue
        # 官方對照：本英雄技能名（前綴＋內文）、全英雄名
        if sep and pre in amap:
            pre = amap[pre]
        for en, zh in amap.items():
            if en in body:
                body = body.replace(en, zh)
        if _CNAME_RE:
            body = _CNAME_RE.sub(lambda m: _CNAME[m.group(1)], body)
        t = zh_line(body)
        if not re.search(r"[0-9A-Za-z一-鿿]", t):
            continue  # 內文只剩標點（wiki 圖示行殘渣）→ 丟棄
        out.append(translate_line((pre + sep + t) if sep else t))  # 最終形過精譯表/前綴對照
    return out

def write_js(all_data):
    # 排序版本（數值順序）
    def ver_key(v):
        parts = v.split(".")
        try: return (int(parts[0]), int(parts[1]))
        except: return (0, 0)

    sorted_vers = sorted(all_data.keys(), key=ver_key)
    js_obj = {}
    for v in sorted_vers:
        cs = {c: clean_lines(ls, c) for c, ls in all_data[v].items()}
        js_obj[v] = {c: ls for c, ls in cs.items() if ls}
    js = "window.WIKI_PATCHES=" + json.dumps(js_obj, ensure_ascii=False, separators=(",",":")) + ";"
    OUT_JS.write_text(js, encoding="utf-8")
    total_champs = sum(len(v) for v in all_data.values())
    print(f"\n✅ 寫出 {OUT_JS}：{len(all_data)} 個版本，{total_champs} 筆英雄改動")

if __name__ == "__main__":
    data = fetch_all()
    if data:
        write_js(data)
