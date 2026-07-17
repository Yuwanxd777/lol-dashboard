# -*- coding: utf-8 -*-
"""
道具正確數值：CDragon items bin + zh_TW 字串表模板 → items.js

DDragon 的道具描述缺數字（如 電流旋風劍「蒼穹」的 %），
真實數值在 items.cdtb.bin.json（mDataValues / StringCalculations），
繁中模板在 zh_tw 字串表（item_{id}_tooltip，含 @token@）。
本腳本填值後輸出 items.js，index.html 以其覆蓋 DDragon 描述。

用法：
    python fetch_items.py            # 版本沒變就跳過
    python fetch_items.py --force
"""
import json, re, sys, urllib.request
from pathlib import Path
from fetch_skills import SpellCtx, eval_calc, render_val, Miss, hget  # 重用技能管線的計算式求值器

ROOT   = Path(__file__).resolve().parent.parent  # 專案根目錄（本腳本在 scripts\ 內）
CACHE_DIR = ROOT / "csv_cache"
BIN_F  = CACHE_DIR / "items_bin.json"
ST_F   = CACHE_DIR / "items_st_zhtw.json"
MARK_F = CACHE_DIR / "items_cache_ver.txt"
OUT_JS = ROOT / "items.js"

DD_API = "https://ddragon.leagueoflegends.com"
URL_BIN = "https://raw.communitydragon.org/latest/game/items.cdtb.bin.json"
URL_ST  = "https://raw.communitydragon.org/latest/game/zh_tw/data/menu/en_us/lol.stringtable.json"

FORCE = "--force" in sys.argv

def get(url, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=timeout).read()

def fmt(v):
    f = round(float(v), 2)
    return str(int(f)) if f == int(f) else ("%.2f" % f).rstrip("0").rstrip(".")

TOK   = re.compile(r"@([A-Za-z_]\w*)(?:\*(-?[\d.]+))?@\s*(%?)")
ICON  = re.compile(r"%i:\w+%")
BRACE = re.compile(r"\{\{[^}]*\}\}")

def build_lut(entry):
    """bin 條目 → token 對照（小寫）：mDataValues + 頂層數值欄位（去 m 前綴也收）"""
    lut = {}
    for k, v in entry.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            lut[k.lower()] = v
            if len(k) > 1 and k[0] == "m" and k[1].isupper():
                lut[k[1:].lower()] = v
    for d in entry.get("mDataValues") or []:
        n, v = d.get("mName"), d.get("mValue")
        if n is not None and v is not None:
            lut[n.lower()] = v
    return lut

def build_calcs(entry, lut):
    """StringCalculations → {名稱小寫: (近戰值, 遠程值)}"""
    out = {}
    def resolve(expr):
        if not isinstance(expr, str):
            return None
        m = TOK.fullmatch(expr.strip()) or re.fullmatch(r"@(\w+)@", expr.strip())
        if not m:
            return None
        v = lut.get(m.group(1).lower())
        return None if v is None else float(v)
    for name, c in (entry.get("StringCalculations") or {}).items():
        if not isinstance(c, dict):
            continue
        a = resolve(c.get("MeleeResult") or c.get("DefaultResult"))
        b = resolve(c.get("RangedResult"))
        if a is not None:
            out[name.lower()] = (a, b)
    return out

def item_ctx(entry):
    """道具條目 → 計算式求值環境（mItemCalculations 用 GameCalculation，同技能）"""
    calcs = entry.get("mItemCalculations")
    dvs = entry.get("mDataValues") or []
    if not calcs:
        return None
    pseudo = {"mDataValues": [{"name": d.get("mName"), "values": [d.get("mValue"), d.get("mValue")]}
                              for d in dvs if d.get("mName") is not None],
              "mSpellCalculations": calcs}
    return SpellCtx(pseudo, 1)

def fill(tpl, lut, calcs, ictx=None):
    miss = 0
    def rep(m):
        nonlocal miss
        name, mul, pct = m.group(1).lower(), m.group(2), m.group(3)
        if name in calcs:
            a, b = calcs[name]
            if b is None or a == b:
                return fmt(a) + pct
            return f"{fmt(a)}{pct}（遠程 {fmt(b)}{pct}）"
        if ictx is not None:
            c = hget(ictx.calc, name)
            if c is not None:
                try:
                    s = render_val(eval_calc(ictx, c), float(mul) if mul else 1.0)
                    if s:
                        return s + pct
                except Miss:
                    pass
            # 慣例：@X@ 可能對應 Xmelee / Xranged 兩個計算式（近戰/遠程數值不同）
            cm, cr = hget(ictx.calc, name + "melee"), hget(ictx.calc, name + "ranged")
            if cm is not None or cr is not None:
                try:
                    mu = float(mul) if mul else 1.0
                    sm = render_val(eval_calc(ictx, cm), mu) if cm is not None else None
                    sr = render_val(eval_calc(ictx, cr), mu) if cr is not None else None
                    if sm and sr and sm != sr:
                        return f"{sm}{pct}（遠程 {sr}{pct}）"
                    if sm or sr:
                        return (sm or sr) + pct
                except Miss:
                    pass
        v = lut.get(name)
        if v is None:
            miss += 1
            return ""
        return fmt(float(v) * (float(mul) if mul else 1)) + pct
    t = TOK.sub(rep, tpl)
    t = ICON.sub("", t)
    t = BRACE.sub("", t)
    return t, miss

def main():
    ddv = json.loads(get(f"{DD_API}/api/versions.json", 30))[0]
    if not FORCE and MARK_F.exists() and MARK_F.read_text().strip() == ddv and OUT_JS.exists():
        print(f"items.js 已是 {ddv}，跳過")
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    need_dl = not (BIN_F.exists() and ST_F.exists()
                   and MARK_F.exists() and MARK_F.read_text().strip() == ddv)
    if need_dl:
        print("下載 items bin…");   BIN_F.write_bytes(get(URL_BIN))
        print("下載 zh_tw 字串表…"); ST_F.write_bytes(get(URL_ST))
    binj = json.loads(BIN_F.read_text(encoding="utf-8"))
    st   = json.loads(ST_F.read_text(encoding="utf-8")).get("entries", {})
    dd   = json.loads(get(f"{DD_API}/cdn/{ddv}/data/zh_TW/item.json", 60))["data"]

    out, filled_n = {}, 0
    for iid in sorted(dd, key=lambda x: int(x)):
        if int(iid) >= 200000:
            continue  # 特殊模式變體（競技場 22xxxx 等）不作為正文來源
        name = dd[iid]["name"]
        if name in out:
            continue  # 同名以較小 id 為準
        # 主模板存在但為空字串 → 這道具的說明只有遊戲內統計/附註，正文以 DDragon 為準
        if st.get(f"item_{iid}_tooltip") == "":
            continue
        # 模板變體優先序：含 @token@（有數值）者優先；external 版常是無數字的簡述
        cands = [st.get(f"item_{iid}_{s}") for s in
                 ("tooltip", "tooltipextended", "tooltipinventory", "tooltipexternal")]
        cands = [c for c in cands if c]
        tpl = next((c for c in cands if "@" in c), cands[0] if cands else None)
        if tpl:  # @f1@/@f2@… 是遊戲內即時統計（已阻擋傷害量等），整句剔除
            tpl = "<br>".join(seg for seg in tpl.split("<br>") if not re.search(r"@f\d+@", seg))
        entry = binj.get(f"Items/{iid}")
        if not tpl or not entry:
            continue
        lut = build_lut(entry)
        calcs = build_calcs(entry, lut)
        body, miss = fill(tpl, lut, calcs, item_ctx(entry))
        if miss > 3:
            continue  # 解不出的太多，寧可用 DDragon 原文
        sm = re.search(r"<stats>[\s\S]*?</stats>", dd[iid].get("description", ""))
        stats = sm.group(0) + "<br><br>" if sm else ""
        out[name] = f"<mainText>{stats}{body}</mainText>"
        filled_n += 1

    # 轉化裝：遊戲內存在、但 DDragon item.json 已不列（水滴疊滿升級系）
    TRANSFORMS = {3040: "大天使之杖", 3042: "魔劍正宗", 3121: "凜冬將至", 2530: "低語之環"}  # id → 升級前本體（水滴四系）
    xtra = {}
    for iid, base in TRANSFORMS.items():
        name = st.get(f"item_{iid}_name")
        entry = binj.get(f"Items/{iid}")
        cands = [st.get(f"item_{iid}_{s}") for s in
                 ("tooltip", "tooltipextended", "tooltipinventory", "tooltipexternal")]
        cands = [c for c in cands if c]
        tpl = next((c for c in cands if "@" in c), cands[0] if cands else None)
        if tpl:
            tpl = "<br>".join(seg for seg in tpl.split("<br>") if not re.search(r"@f\d+@", seg))
        if not (name and entry and tpl):
            continue
        lut = build_lut(entry)
        body, _m = fill(tpl, lut, build_calcs(entry, lut), item_ctx(entry))
        xtra[name] = {"d": f"<mainText>{body}</mainText>", "base": base,
                      "img": f"https://ddragon.leagueoflegends.com/cdn/{ddv}/img/item/{iid}.png"}
    from datetime import datetime
    ver = f"{ddv}-{datetime.now().strftime('%m%d%H%M')}"
    js = ("window.ITEM_DESC=" + json.dumps(out, ensure_ascii=False, separators=(",", ":"))
          + ";window.ITEM_XTRA=" + json.dumps(xtra, ensure_ascii=False, separators=(",", ":"))
          + f';window.ITEM_DESC_VER="{ver}";')  # 版本戳：讓前端 localStorage 快取隨 items.js 重建而失效
    OUT_JS.write_text(js, encoding="utf-8")
    MARK_F.write_text(ddv)
    print(f"✅ items.js：{filled_n} 件道具（DDragon {ddv}）")

if __name__ == "__main__":
    main()
