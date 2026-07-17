# -*- coding: utf-8 -*-
"""改版文本清理（patches.js 的 LOL_PATCHES ＋ wiki_patches.js）：
① 刪「售價」行（造型售價＝場外更新，不屬對局改動）
② 前綴翻中：new：→新增：、updated：→調整：、BUGFIX：→錯誤修正：、Bug Fix:/Undocumented: 等
③ 術語：AP→魔攻、AD→物攻（獨立詞才換；K/DA、ADC 等不動）
④ 英文技能／道具／符文／召技名 → 官方繁中（DDragon championFull＋runesReforged＋summoner 對照，
   道具用 assets.js 的 zh/en；只處理「行內含中文」的混合行——純英文長句留給人工翻譯）
⑤ scripts/tr_fix.json＝人工逐行翻譯表（原行→翻譯行），優先套用
冪等：跑兩次結果相同。剩餘含英文的行輸出到 scripts/remaining_en.txt 供人工翻譯。
用法：python scripts/clean_patch_text.py  （在 fetch_patches.py / fetch_wiki.py / merge_tr.py 重建後跑）"""
import io, sys, os, re, json, urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)

def fetch(u):
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    return json.load(urllib.request.urlopen(req, timeout=60))

# ── 英名→繁中 對照表（快取到 scripts/tr_names.json，DDragon 版本變了就重抓）──
def build_name_map():
    ver = fetch("https://ddragon.leagueoflegends.com/api/versions.json")[0]
    cache_p = os.path.join(HERE, "tr_names.json")
    if os.path.exists(cache_p):
        try:
            c = json.load(open(cache_p, encoding="utf-8"))
            if c.get("_ver") == ver: return c["map"]
        except Exception: pass
    m = {}
    en = fetch(f"https://ddragon.leagueoflegends.com/cdn/{ver}/data/en_US/championFull.json")["data"]
    zh = fetch(f"https://ddragon.leagueoflegends.com/cdn/{ver}/data/zh_TW/championFull.json")["data"]
    for cid, d in en.items():
        z = zh.get(cid)
        if not z: continue
        if d.get("name") and z.get("name") and d["name"] != z["name"]: m[d["name"]] = z["name"]
        pe, pz = d.get("passive") or {}, z.get("passive") or {}
        if pe.get("name") and pz.get("name") and pe["name"] != pz["name"]: m[pe["name"]] = pz["name"]
        for se, sz in zip(d.get("spells") or [], z.get("spells") or []):
            if se.get("name") and sz.get("name") and se["name"] != sz["name"]: m[se["name"]] = sz["name"]
    rune_en = fetch(f"https://ddragon.leagueoflegends.com/cdn/{ver}/data/en_US/runesReforged.json")
    rune_zh = fetch(f"https://ddragon.leagueoflegends.com/cdn/{ver}/data/zh_TW/runesReforged.json")
    for te, tz in zip(rune_en, rune_zh):
        if te["name"] != tz["name"]: m[te["name"]] = tz["name"]
        for sle, slz in zip(te["slots"], tz["slots"]):
            for re_, rz in zip(sle["runes"], slz["runes"]):
                if re_["name"] != rz["name"]: m[re_["name"]] = rz["name"]
    sm_en = fetch(f"https://ddragon.leagueoflegends.com/cdn/{ver}/data/en_US/summoner.json")["data"]
    sm_zh = fetch(f"https://ddragon.leagueoflegends.com/cdn/{ver}/data/zh_TW/summoner.json")["data"]
    for k, d in sm_en.items():
        z = sm_zh.get(k)
        if z and d.get("name") and z.get("name") and d["name"] != z["name"]: m[d["name"]] = z["name"]
    # 道具：assets.js 歷年 zh/en 對照（含已移除舊裝）
    at = open(os.path.join(ROOT, "assets.js"), encoding="utf-8").read()
    aj = json.loads(at[at.find("{"):at.rfind("}") + 1])
    for _id, e in (aj.get("item") or {}).items():
        ze, ee = (e.get("zh") or "").strip(), (e.get("en") or "").strip()
        if ze and ee and ze != ee and re.search(r"[A-Za-z]", ee) and not re.search(r"[一-鿿]", ee):
            m.setdefault(ee, ze)
    # 複合名拆開（Jayce「To the Skies! / Shock Blast」⇔「衝天轟擊！／電磁砲」各自成對）
    for k in list(m.keys()):
        if " / " in k:
            zs = re.split(r"\s*[/／]\s*", m[k])
            es = [p.strip() for p in k.split(" / ")]
            if len(zs) == len(es):
                for e2, z2 in zip(es, zs):
                    if e2 and z2: m.setdefault(e2, z2)
    json.dump({"_ver": ver, "map": m}, open(cache_p, "w", encoding="utf-8"), ensure_ascii=False)
    return m

def finalize_map(m):
    """快取外的最後處理（人工補充表改了不用清快取就生效）：合併 tr_names_extra ＋長度/中文過濾"""
    xp = os.path.join(HERE, "tr_names_extra.json")
    if os.path.exists(xp):
        for k, v in json.load(open(xp, encoding="utf-8")).items(): m[k] = v
    return {k: v for k, v in m.items() if len(k) >= 4 and re.search(r"[A-Za-z]", k) and re.search(r"[一-鿿]", v)}

# ── 行級轉換 ──
PREFIX_RULES = [
    (re.compile(r"\bnew：", re.I), "新增："), (re.compile(r"\bupdated：", re.I), "調整："),
    (re.compile(r"\bremoved：", re.I), "移除："), (re.compile(r"\badjusted：", re.I), "調整："),
    (re.compile(r"\bBugfix:\s*", re.I), "錯誤修正："),
    (re.compile(r"\bBUGFIX："), "錯誤修正："), (re.compile(r"\bTOOLTIP FIX："), "提示文字修正："),
    (re.compile(r"\bRECOMMENDED ITEMS：Updated!?"), "推薦裝備：已更新"),
    (re.compile(r"\bRECOMMENDED ITEMS："), "推薦裝備："),
    (re.compile(r"\[錯誤修正\] Undocumented / Bug Fix:\s*"), "[錯誤修正] 未記載："),
    (re.compile(r"\[錯誤修正\] Bug Fix:\s*"), "[錯誤修正] "),
    (re.compile(r"\[錯誤修正\] Undocumented:\s*"), "[錯誤修正] 未記載："),
    (re.compile(r"\bUndocumented / Bug Fix:\s*"), "未記載："),
    (re.compile(r"\bBug Fix:\s*"), "錯誤修正："),
    (re.compile(r"\bUndocumented:\s*"), "未記載："),
]
APAD = [(re.compile(r"(?<![A-Za-z/])AP(?![A-Za-z])"), "魔攻"), (re.compile(r"(?<![A-Za-z/])AD(?![A-Za-z])"), "物攻"),
        (re.compile(r"([一-鿿]) (魔攻|物攻)"), r"\1\2")]  # 「基礎 物攻」「額外 魔攻」等中文間空格收斂（原 AD/AP 前的空格）

def transform_line(ln, name_map, name_keys, manual):
    if "售價：" in ln: return None  # 造型售價＝場外，刪
    if ln in manual: return manual[ln]
    out = ln
    for rx, rep in PREFIX_RULES: out = rx.sub(rep, out)
    for rx, rep in APAD: out = rx.sub(rep, out)
    if re.search(r"[A-Za-z][’‘][A-Za-z ]", out): out = out.replace("’", "'").replace("‘", "'")  # 英文名內彎引號→直引號（Bop ‘n’ Block 等才能對上官方表）
    if re.search(r"[A-Za-z]{4,}", out) and re.search(r"[一-鿿]", out):  # 混合行才做英名對照
        for k in name_keys:
            if k in out:
                out = re.sub(r"(?<![A-Za-z])" + re.escape(k) + r"(?![A-Za-z])", name_map[k], out)
            elif k.upper() != k and k.upper() in out:  # 全大寫標頭（W - WARRIOR TRICKSTER）也對照
                out = re.sub(r"(?<![A-Za-z])" + re.escape(k.upper()) + r"(?![A-Za-z])", name_map[k], out)
        out = re.sub(r"([一-鿿！？」]) ([一-鿿「])", r"\1\2", out)  # 對照後中文間殘留空格收斂（衝天轟擊！ 傷害→衝天轟擊！傷害 不收——僅中文-中文）
    return out

def process(path, var_name):
    t = open(path, encoding="utf-8").read()
    i = t.find(f"window.{var_name}=")
    j = i + len(f"window.{var_name}=")
    d, end = json.JSONDecoder().raw_decode(t, j)
    stats = {"del": 0, "chg": 0, "tot": 0}
    remain = []
    for ver, pd in d.items():
        if not isinstance(pd, dict): continue
        for key in list(pd.keys()):
            v = pd[key]
            def do(lines, tag):
                out = []
                for ln in lines:
                    if not isinstance(ln, str): out.append(ln); continue
                    stats["tot"] += 1
                    nl = transform_line(ln, NAME_MAP, NAME_KEYS, MANUAL)
                    if nl is None: stats["del"] += 1; continue
                    if nl != ln: stats["chg"] += 1
                    _chk = re.sub(r"%i:[A-Za-z0-9_]+%", "", nl)  # 圖示占位符（%i:ornnIcon%）非文字，不算殘英
                    _chk = re.sub(r"[（(][A-Za-z'’\- ]+[)）]", "", _chk)  # 括號內英文原名註記（（WARMONGER））＝刻意保留，不算殘英
                    _chk = re.sub(r"(?<![A-Za-z])(ARAM|ARURF|URF|PVP|Clash|Ctrl|Shift|Buff|buff|VFX|Riot|Gamma|BUG|Ping)(?![A-Za-z])", "", _chk)  # 通用縮寫白名單（\b 在中文旁失效→用拉丁邊界）
                    if re.search(r"[A-Za-z]{4,}", re.sub(r"[A-Za-z']+[’']s\b", "", _chk)): remain.append(f"{os.path.basename(path)}|{ver}|{tag}|{nl}")
                    out.append(nl)
                return out
            if key == "_extra" and isinstance(v, dict):
                for c2 in list(v.keys()):
                    if isinstance(v[c2], list): v[c2] = do(v[c2], "_extra/" + c2)
            elif isinstance(v, list):
                pd[key] = do(v, key)
    new_seg = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    open(path, "w", encoding="utf-8", newline="\n").write(t[:j] + new_seg + t[end:])
    return stats, remain

if __name__ == "__main__":
    NAME_MAP = finalize_map(build_name_map())
    NAME_KEYS = sorted(NAME_MAP.keys(), key=len, reverse=True)
    mp = os.path.join(HERE, "tr_fix.json")
    MANUAL = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {}
    all_remown = []
    for fn, var in [("patches.js", "LOL_PATCHES"), ("wiki_patches.js", "WIKI_PATCHES")]:
        st, rem = process(os.path.join(ROOT, fn), var)
        all_remown += rem
        print(f"{fn}: 掃 {st['tot']} 行｜改 {st['chg']}｜刪(售價) {st['del']}｜殘英 {len(rem)}")
    rp = os.path.join(HERE, "remaining_en.txt")
    open(rp, "w", encoding="utf-8").write("\n".join(all_remown))
    print(f"英名對照 {len(NAME_MAP)} 條｜人工表 tr_fix.json {len(MANUAL)} 條｜殘英清單 → {rp}")
