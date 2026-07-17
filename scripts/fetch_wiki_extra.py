# -*- coding: utf-8 -*-
"""
舊年份的道具/符文/系統改動：LoL Wiki 版本頁（V4.1 …）→ wiki_extra.js

官方繁中公告只回溯到 2019；英雄部分已由 fetch_wiki.py（Patch_history）補齊，
本腳本補「英雄以外」的章節：Items→道具、Summoner Spells→召喚師技能、
Runes/Masteries→符文、其餘（General/Jungle/…）→機制。

用法：
    python scripts/fetch_wiki_extra.py            # 只抓缺的版本
    python scripts/fetch_wiki_extra.py --force
    python scripts/fetch_wiki_extra.py --ver 4.1  # 單一版本測試
"""
import json, re, sys, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
from fetch_patches import translate, translate_line
from fetch_wiki import zh_line, JUNK_RE

ROOT    = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "csv_cache/wikiv"
OUT_JS  = ROOT / "wiki_extra.js"
BASE    = "https://wiki.leagueoflegends.com/en-us/V{v}"
DELAY   = 1.0
MAJORS  = range(4, 13)         # V4.x–V12.x = 2014–2022（2019–2022 官方是英文版面、當時只解析了英雄區；2023+ 繁中官方已含道具/系統）
MINORS  = range(1, 26)

FORCE = "--force" in sys.argv
ONLY  = sys.argv[sys.argv.index("--ver")+1] if "--ver" in sys.argv else None

OUT_DIR.mkdir(parents=True, exist_ok=True)

EXTRACT = """()=>{
  const c=document.querySelector('.mw-parser-output')||document.body;
  const out=[]; let sec='', ent='';
  const ht=el=>el.matches&&el.matches('div.mw-heading,h2,h3,h4')?el.textContent.replace(/\\[edit.*$/,'').trim():null;
  // li 自身文字（排除巢狀 UL/DL）；inline-image 的 alt 就是道具名（合成配方行靠這個）
  const liText=li=>{
    let t='';
    for(const n of li.childNodes){
      if(n.nodeType===3)t+=n.textContent;
      else if(n.tagName==='UL'||n.tagName==='DL'){}
      else if(n.nodeType===1){
        if(n.tagName==='SPAN'&&n.classList.contains('inline-image')){
          const img=n.querySelector('img');
          let alt=(img&&(img.getAttribute('alt')||''))
            .replace(/\\.(png|jpg).*$/i,'')
            .replace(/^(an )?icon (for the item |representing )?/i,'').trim();
          if(/^gold$/i.test(alt)){ t+=' '+n.textContent+' '; alt=''; }
          if(alt)t+=' '+alt+' ';
        } else t+=n.textContent;
      }
    }
    return t.replace(/\\s+/g,' ').trim();
  };
  // 遞迴走 li 樹：子標頭(Tooth/Nail)累進 subPath，葉節點才是改動行；ent=道具名(來自 <p>)
  const walk=(li,subPath)=>{
    const t=liText(li);
    const sub=li.querySelector(':scope > ul');
    if(sub){
      const isChg=t&&/⇒|reduced|increased|removed|new effect|new recipe|old recipe|now /i.test(t);
      const sp=(t&&!isChg)?(subPath?subPath+' / '+t:t):subPath;  // 子項標頭累進
      if(t&&isChg)out.push({sec,ent,line:subPath?subPath+'：'+t:t});
      for(const cl of sub.children)if(cl.tagName==='LI')walk(cl,sp);
    } else if(t){
      out.push({sec,ent,line:subPath?subPath+'：'+t:t});
    }
  };
  for(const el of c.children){
    const h=ht(el);
    if(h){sec=h; ent=''; continue;}
    if(el.tagName==='P'){const t=el.textContent.replace(/\\s+/g,' ').trim(); if(t&&t.length<=60)ent=t; continue;} // 版本頁道具名在 <p> 段落
    if(el.tagName==='DL'){const a=el.querySelector('dt'); if(a)ent=a.textContent.trim();}
    else if(el.tagName==='UL'){ for(const li of el.children)if(li.tagName==='LI')walk(li,''); }
  }
  return out;
}"""

SEC_MAP = [
    (re.compile(r"^Items?$", re.I), "道具"),
    (re.compile(r"^Summoner Spells?$", re.I), "召喚師技能"),
    (re.compile(r"^(Runes?|Masteries)$", re.I), "符文"),
]
SKIP_SEC = re.compile(r"Champions|Skins?|Store|Matchmaking|Contents|References|Hotfix|Client|PVP|Bots|Practice|Twisted Treeline|Ultimate Spellbook|Howling Abyss|ARAM|Cosmetics", re.I)
MECH_SEC = re.compile(r"^Game$|General|Jungle|Minions?|Turrets?|Towers?|Objectives?|Monsters?|Undocumented|Gameplay|Map|Summoner.?s Rift|Neutral buffs", re.I)

def _sample_versions():
    """每個大版本取 新→中→舊 三個取樣點，涵蓋整段期間出現/移除的道具名"""
    try:
        vs = json.loads(urllib.request.urlopen("https://ddragon.leagueoflegends.com/api/versions.json", timeout=30).read())
    except Exception:
        return ["4.20.1", "6.24.1", "8.24.1", "13.13.1"]
    out = ["13.13.1"]
    for maj in ("4", "5", "6", "7", "8", "9", "10", "11", "12"):
        g = [v for v in vs if v.split(".")[0] == maj]
        if g:
            out += [g[0], g[len(g)//2], g[-1]]   # versions.json 新在前
    return out

def item_name_map():
    """DDragon 歷史版本 en/zh item 對照（含 2014 已移除道具）"""
    m = {}
    for v in _sample_versions():
        try:
            en = json.loads(urllib.request.urlopen(f"https://ddragon.leagueoflegends.com/cdn/{v}/data/en_US/item.json", timeout=60).read())["data"]
            zh = json.loads(urllib.request.urlopen(f"https://ddragon.leagueoflegends.com/cdn/{v}/data/zh_TW/item.json", timeout=60).read())["data"]
            for iid, e in en.items():
                z = zh.get(iid)
                if z and e["name"] not in m:
                    m[e["name"]] = z["name"]
        except Exception as ex:
            print(f"  （item 對照 {v} 載入失敗：{ex}）")
    # 符文(runesReforged) + 天賦(mastery) 的 en→官方zh：讓改動實體名(Warlord's Bloodlust…)也用官方中文，不用自創翻譯（UU 原則）
    def _load(v, kind):
        try:
            en = json.loads(urllib.request.urlopen(f"https://ddragon.leagueoflegends.com/cdn/{v}/data/en_US/{kind}.json", timeout=60).read())
            zh = json.loads(urllib.request.urlopen(f"https://ddragon.leagueoflegends.com/cdn/{v}/data/zh_TW/{kind}.json", timeout=60).read())
            return en, zh
        except Exception:
            return None, None
    for v in ("8.24.1", "9.24.2", "10.25.1", "12.23.1", "13.24.1"):   # runesReforged en/zh
        en, zh = _load(v, "runesReforged")
        if not en:
            continue
        zmap = {}
        for t in zh:
            zmap[t["id"]] = t["name"]
            for sl in t["slots"]:
                for r in sl["runes"]:
                    zmap[r["id"]] = r["name"]
        for t in en:
            if t["name"] not in m and zmap.get(t["id"]):
                m[t["name"]] = zmap[t["id"]]
            for sl in t["slots"]:
                for r in sl["runes"]:
                    if r["name"] not in m and zmap.get(r["id"]):
                        m[r["name"]] = zmap[r["id"]]
    for v in ("6.16.2", "6.24.1", "7.16.1", "7.21.1", "5.16.1", "4.16.1"):  # mastery en/zh(7.22 前；含賽季中版——季前賽會換掉部分天賦)
        en, zh = _load(v, "mastery")
        if not en:
            continue
        ed, zd = en.get("data", {}), zh.get("data", {})
        for mid, e in ed.items():
            if e.get("name") and e["name"] not in m and zd.get(mid, {}).get("name"):
                m[e["name"]] = zd[mid]["name"]
    # 飾品類鍵帶「 (Trinket)」後綴（Sweeping Lens (Trinket)），wiki 原文常寫無後綴 → 補無後綴別名（值＝去括號官方名，如 清除者透視鏡）
    for k in list(m):
        if " (Trinket)" in k:
            base = k.replace(" (Trinket)", "")
            zc = re.sub(r"[（(][^（）()]*[)）]", "", m[k]).strip()
            m.setdefault(base, zc or m[k])
    # 召喚師技能 en→官方zh（現行版）：Ghost→鬼步、Flash→閃現…（不進對照就會被詞典逐字翻成「幽靈疾步」等舊譯）
    try:
        cur = json.loads(urllib.request.urlopen("https://ddragon.leagueoflegends.com/api/versions.json", timeout=30).read())[0]
        en, zh = _load(cur, "summoner")
        if en:
            ed, zd = en.get("data", {}), zh.get("data", {})
            for sid, e in ed.items():
                if e.get("name") and e["name"] not in m and zd.get(sid, {}).get("name"):
                    m[e["name"]] = zd[sid]["name"]
    except Exception:
        pass
    return m

def fetch_all():
    vers = [ONLY] if ONLY else [f"{a}.{b}" for a in MAJORS for b in MINORS]
    got = {}
    for f in OUT_DIR.glob("*.json"):
        got[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    todo = [v for v in vers if FORCE or v not in got]
    if todo:
        with sync_playwright() as p:
            br = p.chromium.launch(headless=True)
            pg = br.new_page()
            for i, v in enumerate(todo):
                url = BASE.format(v=v)
                print(f"  [{i+1}/{len(todo)}] V{v}", end=" ", flush=True)
                try:
                    pg.goto(url, wait_until="domcontentloaded", timeout=40000)
                    if "There is currently no text in this page" in pg.content() or pg.title().startswith("Page not found"):
                        print("（無此版本）"); got[v] = {}
                    else:
                        rows = pg.evaluate(EXTRACT)
                        cur = {}
                        for r in rows:
                            cur.setdefault(r["sec"], {}).setdefault(r["ent"] or "", []).append(r["line"])
                        got[v] = cur
                        print(f"✓ {len(rows)} 行")
                    (OUT_DIR / f"{v}.json").write_text(json.dumps(got[v], ensure_ascii=False), encoding="utf-8")
                except Exception as e:
                    print(f"✗ {e}")
                time.sleep(DELAY)
            br.close()
    return got

def build(got):
    imap = item_name_map()
    # 內文道具名替換用（合成公式行「A + B +50g = 750g」的元件名）
    _in = sorted(imap, key=len, reverse=True)
    irx = re.compile(r"(?<![A-Za-z])(" + "|".join(re.escape(n) for n in _in) + r")(?![A-Za-z])") if _in else None
    out = {}
    for v, secs in got.items():
        m = re.match(r"^(\d{1,2})\.(\d{1,2})$", v)
        if not m:
            continue
        yr = 2010 + int(m.group(1))
        pk = f"{yr%100}.{int(m.group(2)):02d}"
        cats = {}
        for sec, ents in secs.items():
            if SKIP_SEC.search(sec):
                continue
            cat = next((c for rx, c in SEC_MAP if rx.match(sec)), None)
            if cat is None:
                if not MECH_SEC.search(sec):
                    continue
                cat = "機制"
            # 段落標頭誤當道具名（<p> 解析副作用）：Overview/Removed items… 一律跳過
            HDR_ENT = re.compile(r"^(Overview|Utility|General|Notes|Summary|Changes|Miscellaneous|Others?|Gameplay|Level Requirements?|(New|Removed|Updated)( items?)?|Items?|Tier \d+|Ferocity|Cunning|Resolve|Offense|Defense|Masteries|Runes?)$", re.I)
            # imap 正規化索引：去 's／引號、壓空白 → 「Skirmisher的 Sabre」這類半翻壞名的英文原字也對得到
            if not hasattr(build, "_imapN"):
                _n = lambda s: re.sub(r"\s+", " ", re.sub(r"\bthe\b", " ", re.sub(r"[’']s\b|[’']", "", s.lower()))).strip()
                build._imapN = { _n(k): v for k, v in imap.items() }
                build._normEn = _n
            imapN, normEn = build._imapN, build._normEn
            zh_one = lambda p: imap.get(p) or imapN.get(normEn(p)) or translate(p)
            for ent, lines in ents.items():
                if ent and HDR_ENT.match(ent.strip()):
                    continue
                # 「Ardent Censer added / Lost Chapter reintroduced」帶狀態後綴：剝後綴查對照，再補中文標注
                ec = re.sub(r"\s*[-–]?\s*[(（]?\s*(added|removed|rework(?:ed)?|remade|new|reintroduced|returned|updated)\s*[)）]?$", "", ent, flags=re.I) if ent else ""
                # 括號長說明後綴（Expose Weakness (new Ferocity tier 2 mastery)）：括號內含狀態關鍵詞就整段剝掉
                ec = re.sub(r"\s*[(（][^)）]*\b(new|added|removed|rework|mastery|tier|keystone)\b[^)）]*[)）]$", "", ec, flags=re.I).strip()
                sfx = ""
                if ec != ent:
                    if re.search(r"(added|new|reintroduced|returned)$", ent, re.I):
                        sfx = "（新增）"
                    elif re.search(r"(rework(?:ed)?|remade|updated)$", ent, re.I):
                        sfx = "（重做）"
                    else:
                        sfx = "（移除）"
                # 複合名「A / B / C」（wiki 常見雙空格）→ 各自查官方名再以「／」連回
                if ec and "/" in ec:
                    zh_ent = "／".join(zh_one(p.strip()) for p in re.split(r"\s*/\s*", ec) if p.strip()) + sfx
                else:
                    zh_ent = (zh_one(ec) + sfx) if ec else ""
                for l in lines:
                    if JUNK_RE.match(l.strip()):
                        continue
                    # 圖示 alt 的敘述性前綴：「An icon for the item X」→「X」；金錢圖示（數字不在文字流）整段拿掉
                    l = re.sub(r"An icon for the item\s*", "", l, flags=re.I)
                    l = re.sub(r"An icon representing \w+\s*", "", l, flags=re.I)
                    if irx:
                        l = irx.sub(lambda m: imap[m.group(1)], l)
                    t = zh_line(l)
                    # 英文 Old/New Effect: 前綴 → 中文，避免「Old Effect:：」雙冒號；一併修 % ( 與 數字 % 的半形空格
                    t = re.sub(r"\bOld Effect\s*[:：]", "舊效果：", t, flags=re.I)
                    t = re.sub(r"\bNew Effect\s*[:：]", "新效果：", t, flags=re.I)
                    t = re.sub(r"([：:])\s*\1", r"\1", t)          # 連續冒號 ：： → ：
                    t = re.sub(r"%\s+([（(])", r"%\1", t).replace("% （", "%（")  # 「% (」→「%（」
                    t = re.sub(r"(\d)\s+%", r"\1%", t)             # 「125 %」→「125%」
                    t = re.sub(r"([一-鿿])\s*,\s*(?=[一-鿿])", r"\1，", t)  # 中文之間的半形逗號 → 全形（友方英雄, 移動中 → 友方英雄，移動中）
                    t = re.sub(r"Cooldown:\s*None\.?", "冷卻時間：無。", t, flags=re.I)  # 「Cooldown: None.」殘留
                    t = t.replace("掃描透鏡", "清除者透視鏡")  # 內文舊自譯 → 官方名（Sweeping Lens）
                    # 子項標頭句式（EXTRACT subPath 帶出的 wiki 寫法）＋高頻未翻詞/句
                    t = re.sub(r"\b(?:An? )?Active named (.+?)\.?\s*：", r"主動（\1）：", t, flags=re.I)
                    t = re.sub(r"\b(?:An? )?Passive named (.+?)\.?\s*：", r"被動（\1）：", t, flags=re.I)
                    t = re.sub(r"\bBase damage\b", "基礎傷害", t, flags=re.I)
                    t = re.sub(r"\bAP ratio\b", "AP 係數", t, flags=re.I)
                    t = re.sub(r"\bAD ratio\b", "AD 係數", t, flags=re.I)
                    t = t.replace("Damage is now dealt instantaneously instead of as a projectile.", "傷害改為立即生效（不再是飛行彈道）。")
                    t = t.replace("Cooldown is shared with other Hextech items.", "冷卻時間與其他海克斯科技道具共用。")
                    if not re.search(r"[0-9A-Za-z一-鿿]", t):
                        continue
                    # 合成配方行的道具名都在圖示裡（已剝除）→ 只剩 + + = 的殘渣，丟棄
                    if re.search(r"recipe|配方", t, re.I) and not re.search(
                            r"[0-9一-鿿]", re.sub(r"recipe|new|old|新增|配方", "", t, flags=re.I)):
                        continue
                    # 數值藏在圖示模板抓不到 → 只剩「…：從 。」的斷句，丟棄
                    if re.search(r"[：:]\s*從?\s*。?$", t):
                        continue
                    # 金錢數字缺失的配方殘尾：「+ =」壓成「=」、句尾懸空的 + / = 去掉
                    t = re.sub(r"[+＋]\s*(?=[=＝])", "", t)
                    t = re.sub(r"\s*[+＋=＝]\s*。?$", "", t).strip()
                    if not re.search(r"[0-9A-Za-z一-鿿]", t):
                        continue
                    cats.setdefault(cat, []).append(translate_line(f"{zh_ent}｜{t}") if zh_ent else translate_line(t))
        if cats:
            out[pk] = cats
    js = "window.WIKI_EXTRA=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";"
    # 輸出前全域舊自譯正名（涵蓋 ent 複合名/irx 漏抓等所有路徑）：舊自譯 → DDragon 官方名
    for old, new in (("掃描透鏡", "清除者透視鏡"), ("餘燼巨人", "巴米灰燼")):
        js = js.replace(old, new)
    OUT_JS.write_text(js, encoding="utf-8")
    print(f"\n✅ wiki_extra.js：{len(out)} 個版本")

if __name__ == "__main__":
    build(fetch_all())
