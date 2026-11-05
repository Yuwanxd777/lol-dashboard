# -*- coding: utf-8 -*-
"""
道具正確數值：CDragon items bin + zh_TW 字串表模板 → items.js

DDragon 的道具描述缺數字（如 電流旋風劍「蒼穹」的 %），
真實數值在 items.cdtb.bin.json（mDataValues / StringCalculations），
繁中模板在 zh_tw 字串表（item_{id}_tooltip，含 @token@）。
本腳本填值後輸出 items.js，index.html 以其覆蓋 DDragon 描述。

快取用兩把鍵（2026-11-05 #2613，同 fetch_skills）：DDragon 版本＋CDragon build。
只看 DDragon 時，它換版後建的那份會卡到下次改版：16.22 上線兩天狂霸血甲還是 12%（bin 與 DDragon 都是 10%），
16.21 破堡者 50（應 40）、破曉之核 10（應 15），16.20 實驗型海克斯板甲遠程 35%（應 25%）。

用法：
    python fetch_items.py            # DDragon 與 CDragon 版本都沒變就跳過
    python fetch_items.py --force
"""
import json, os, re, socket, sys, urllib.error, urllib.request
from pathlib import Path
from fetch_skills import SpellCtx, Val, bin_hash, eval_part, eval_calc, render_val, scale_rng, Miss, hget, HOLE_RE  # 重用技能管線的計算式求值器與破句偵測

ROOT   = Path(__file__).resolve().parent.parent  # 專案根目錄（本腳本在 scripts\ 內）
CACHE_DIR = ROOT / "csv_cache"
BIN_F  = CACHE_DIR / "items_bin.json"
ST_F   = CACHE_DIR / "items_st_zhtw.json"
MARK_F = CACHE_DIR / "items_cache_ver.txt"
CDVER_F = CACHE_DIR / "items_cache_cdver.txt"
OUT_JS = ROOT / "items.js"

DD_API = "https://ddragon.leagueoflegends.com"
URL_BIN = "https://raw.communitydragon.org/latest/game/items.cdtb.bin.json"
URL_ST  = "https://raw.communitydragon.org/latest/game/zh_tw/data/menu/en_us/lol.stringtable.json"
URL_CDVER = "https://raw.communitydragon.org/latest/content-metadata.json"
MIN_KEEP = 0.9   # 件數掉到舊檔這個比例以下＝來源或解析壞了，不寫檔

FORCE = "--force" in sys.argv

def get(url, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=timeout).read()

def _is_transient(e):
    """5xx／429／逾時／連線失敗＝來源暫時掛了（2026-10-07 CDragon 整片 522，這支 Traceback exit 1）。
    這種時候保留上一班的 items.js 與快取、正常結束；items.js 的版本戳會停在舊版，
    update_health 的「遊戲版本」會拿它跟圖鑑素材比，撐過寬限就照樣報不一致——不會被靜默吞掉。"""
    if isinstance(e, urllib.error.HTTPError):
        return e.code >= 500 or e.code == 429
    return isinstance(e, (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError))

def fmt(v):
    f = round(float(v), 2)
    return str(int(f)) if f == int(f) else ("%.2f" % f).rstrip("0").rstrip(".")

TOK   = re.compile(r"@([A-Za-z_]\w*)(?:\*(-?[\d.]+))?@\s*(%?)")
# 引用別的技能（@spell.SummonerSmite:PetDPS@）：這份 bin 查不到，也不可留在文字裡。要在 TOK 之前處理，
# 否則 TOK 會把兩個 token 之間夾的英文字（...@B@spell...）當成 token。
EXT   = re.compile(r"@[^@\s<>*]*[.:][^@\s<>]*@")
ICON  = re.compile(r"%i:\w+%")
BRACE = re.compile(r"\{\{[^}]*\}\}")
# 字串表 item_cooldown＝「(@Cooldown@秒)」。以前跟其他 {{ }} 一起被 BRACE 清掉，守護天使、破堡者等都看不到冷卻（#2622）
CD_TOK = re.compile(r"\{\{\s*Item_Cooldown\s*\}\}")
# bin 拿超大秒數當「沒有時限」：破堡者 BuffDuration 25000，官方 26.21「Sabotage Duration: 90s ⇒ Infinite」（#2622）
NO_LIMIT = re.compile(r"(?<![\d./])(?:9999|\d{5,})秒")
# 近戰／遠程數值佔位：字串表展開後是 @MeleeItemCalcValue[B-D]@ 與 @RangedItemCalcValue[B-D]@。以前被 BRACE 清掉，
# 海神之斧只剩「普攻對鄰近敵軍造成物理傷害」、死亡之舞「所受傷害的改為…」（#2622）
# 舊模板先印數字再接佔位：暮色黑刃「(@Cooldown@{{Item_Cooldown}})」、拉克爾之盾「每@Cooldown@{{ Item_Cooldown }}秒」
CD_DUP = re.compile(r"@(\w*Cooldown\w*)@\s*\{\{\s*Item_Cooldown\s*\}\}(?:\s*秒)?", re.I)
HEAD_CD = re.compile(r"([：:]?)</(passive|active)>\s*(?:(每個目標)\s*)?（([\d.]+秒)）")
SPLIT_TOK = re.compile(r"\{\{\s*Item_Melee_Ranged_Split(?:_Dynamic)?(?:_([B-D]))?\s*\}\}")
ONHIT_TOK = re.compile(r"\{\{\s*Item_Keyword_OnHit\s*\}\}")  # 字串表＝「命中效果」，被清掉就剩「逐步冰封：，附加…」（#2622）
# 這些佔位字串表有完整定義，以前跟其他 {{ }} 一起被 BRACE 清掉（#2623）：
# 鋼鐵護肩等 4 件整段「戰亂之殤」不見、靈魂黑矛與稻草人沒有「主動」字樣、規則說明變成空的 <rules></rules>
EXPAND_NAMES = ("Item_Energized", "Item_Support_Warding_Active", "Item_Support_Spoils_Of_War_01", "Item_Support_Spoils_Of_War_02", "Item_Active_Consume", "Item_Active_Trinket",
                "Item_Grievous_Wounds", "Item_Support_Minion_Warning", "Item_Melee_Ranged_Rules", "Item_Jungle_Rules",
                "Item_Ghosting", "Item_Ally_Scaling")
EXPAND_TOK = re.compile(r"\{\{\s*(" + "|".join(EXPAND_NAMES) + r")\s*\}\}")
# 戰亂之殤：近戰／遠程的斬殺線。ChampRange 只是選邊用的 1／2，數字在 MeleeValue、RangedValue
RANGE_PERC = re.compile(r"\s*\{\{\s*Item_Range_Mod_@ChampRange@_Perc\s*\}\}\s*")
# 「獲得 {{ 主動 }} <active>守衛</active>」不可以留 <active>：index.html 的 parseItemDesc 會切成一段只有「守衛。」的殘句然後濾掉
NAMED_ACTIVE = re.compile(r"\{\{\s*Item_Active_Named_NoBullet\s*\}\}\s*<active>([^<]*)</active>")
# 神話道具 14.1 就取消了，字串表還留著「神話被動：」那行。佔位被清掉後剩「5 物理防禦與魔法防禦。」這種沒頭沒尾的句子，整行拿掉
MYTHIC_TOK = re.compile(r"\{\{\s*Item_Mythic_Passive\s*\}\}")

# 主動效果是獨立的字串（bin 的 mLocKeys.keyActive），不在 item_N_tooltip 裡。以前只讀 tooltip，
# 現行可買 29 件的主動整段不見：中婭沙漏只剩「(120秒)」、生命藥水只剩「最多可攜帶5瓶」（#2634）。
ACTIVE_ONACT = re.compile(r"\{\{\s*Item_OnActivation\s*\}\}\s*(\{\{\s*Item_Cooldown\s*\}\})\s*(?:<br>\s*)?<active>([^<]*)</active>", re.I)
ACTIVE_NAMED = re.compile(r"\{\{\s*Item_Active_Named\s*\}\}\s*([^<：:]{1,20})[：:]\s*", re.I)
ACTIVE_ONLY = re.compile(r"(?:<br>\s*)*\{\{\s*Item_OnActivation\s*\}\}\s*(?:<br>\s*)*", re.I)
RULES_TAIL = re.compile(r"(?:<br>\s*)*<rules>[\s\S]*$")

def pick_template(iid, entry, st):
    """選模板：回傳還沒展開的字串，沒有模板回 None。
    keyTooltip 只有指到同一件的 item_N_ 才採用（狂暴利刃 Item_3095_Tooltip_Kiwi 才是現行，item_3095_tooltip 已過期）；
    指到別件（終末戰戟指到競技場 223039）或 game_／plaintext 的是舊資料，不跟。
    有 keyActive、沒有 keyTooltip 的道具，item_N_tooltip 多半過期（海克斯科技槍刃還寫 Spell Vamp）或只有冷卻（中婭），
    只留裡面的規則說明。"""
    lk = ((entry.get("mItemDataClient") or {}).get("mTooltipData") or {}).get("mLocKeys") or {}
    cands = [st.get(f"item_{iid}_{s}") for s in
             ("tooltip", "tooltipextended", "tooltipinventory", "tooltipexternal")]
    cands = [c for c in cands if c]
    tip = next((c for c in cands if "@" in c), cands[0] if cands else None)  # 含 @token@（有數值）者優先；external 常是無數字的簡述
    tk = (lk.get("keyTooltip") or "").lower()
    ak = (lk.get("keyActive") or "").lower()
    act = st.get(ak) if ak.startswith("item_") else None
    if tk.startswith(f"item_{iid}_") and st.get(tk):
        tip = st[tk]
    elif act and not tk:
        rules = RULES_TAIL.search(tip or "")
        tip = rules.group(0) if rules and not tip[:rules.start()].strip() else None
    if not act:
        return tip
    act = ACTIVE_ONACT.sub(r"<active>\2</active>\1<br>", act)
    act = ACTIVE_ONLY.sub("<active>主動</active><br>", act)
    act = ACTIVE_NAMED.sub(lambda m: f"<active>{m.group(1)}</active><br>", act)
    names = re.findall(r"<active>([^<]*)</active>", act)
    if tip and any(f"<active>{n}</active>" in RULES_TAIL.sub("", tip) for n in names if n not in ("主動", "主動─")):
        return tip  # 模板已經寫了同一段主動
    if not tip:
        return act
    m = RULES_TAIL.search(tip)  # 規則說明放最後
    head, tail = (tip[:m.start()], m.group(0)) if m else (tip, "")
    head = re.sub(r"(?:<br>\s*)+$", "", head)
    return f"{head}<br><br>{act}{tail}" if head.strip() else f"{act}{tail}"

def expand_tokens(tpl, st):
    """fill 之前先展開。字串表查不到就原樣留著，之後由 BRACE 清掉（等於舊行為）。"""
    if MYTHIC_TOK.search(tpl):
        tpl = "<br>".join(seg for seg in tpl.split("<br>") if not MYTHIC_TOK.search(seg))
        tpl = re.sub(r"(?:<br>\s*)+$", "", tpl)
    tpl = EXPAND_TOK.sub(lambda m: re.sub(r"\s*%i:\w+%\s*", "", st.get(m.group(1).lower(), m.group(0))), tpl)  # 圖示旁的空白一起拿掉
    tpl = RANGE_PERC.sub("@MeleeValue*100@%（遠程 @RangedValue*100@%）", tpl)
    return NAMED_ACTIVE.sub(lambda m: f"主動─{m.group(1)}", tpl)

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
    # @Effect3Amount@ 這一族的來源是 mEffectAmount 陣列（2026-08-15 補）。以前沒收 → 模板填不出來，
    # 留下「在 秒內持續造成共 魔法傷害」這種沒有數字的句子（餘燼之刃／支配寶匣／探索者護腕…）。
    # ⚠ 索引是 **1 起算、無前置佔位**（Effect3Amount＝陣列第 3 個）——與**技能** bin 的 mEffectAmount
    #   不同，那邊有前置佔位（見 fetch_skills 的註解）。三筆實測對得上 DDragon 原文：
    #   1035 Effect3=5 秒、4402 Effect1=3 秒、2420 Effect2=2.5 秒。
    ea = entry.get("mEffectAmount")
    if isinstance(ea, list):
        for i, v in enumerate(ea):
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                lut[f"effect{i+1}amount"] = v
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
    pseudo = {"mDataValues": [{"name": d.get("mName"), "values": [d.get("mValue") or 0.0, d.get("mValue") or 0.0]}
                              for d in dvs if d.get("mName") is not None],
              "mSpellCalculations": calcs}
    ctx = SpellCtx(pseudo, 1)
    # 計算式引用 data value 時常寫雜湊（{6c8d1758}＝BaseADBonusMelee），名字在 mDataValues 是明文
    for k in list(ctx.dv):
        ctx.dv[bin_hash(k)] = ctx.dv[k]
    ea = entry.get("mEffectAmount")
    if isinstance(ea, list):
        ctx.effect_1based = ea
    return ctx

def render_split(ictx, c, mu):
    """近戰／遠程分開的計算式（mRangedMultiplier）→ '15（遠程 10）'。
    遠程值取到小數一位：倍率是 0.667，不取整會印出 10.01（遊戲內顯示 10）。"""
    v = eval_calc(ictx, c)
    sm = render_val(v, mu)
    rm = c.get("mRangedMultiplier")
    if not (sm and rm):
        return sm
    k = eval_part(ictx, rm)
    if not k.flat or k.scal:
        return sm
    k = k.flat[0]
    m = 1.0 if v.pct and abs(mu - 100) < 1e-9 else mu
    r = Val(flat=[round(x * k * m, 1) for x in v.flat],
            scal=[([round(a * k, 4) for a in rs], lb) for rs, lb in v.scal], rng=scale_rng(v.rng, k),
            srng=[(scale_rng(x, k), lb) for x, lb in v.srng])
    r.pct = v.pct
    sr = render_val(r)
    return sm if not sr or sr == sm else f"{sm}（遠程 {sr.replace('（依等級）', '')}）"

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
                    s = render_split(ictx, c, float(mul) if mul else 1.0)
                    if s:
                        return s + ("" if "%" in s else pct)  # 值已帶 %，模板再接一個 % 會變 8%%
                except Miss:
                    pass
            # 慣例：@X@ 可能對應 Xmelee / Xranged 兩個計算式（近戰/遠程數值不同）；
            # @…MeleeRangedSplit@ 對應的是固定名字的一對（吸魔劍的護盾、寒冰霸拳的緩速）
            if name.endswith("meleerangedsplit"):
                cm, cr = hget(ictx.calc, "meleeitemcalcvalue"), hget(ictx.calc, "rangeditemcalcvalue")
            else:
                cm, cr = hget(ictx.calc, name + "melee"), hget(ictx.calc, name + "ranged")
            if cm is not None or cr is not None:
                try:
                    mu = float(mul) if mul else 1.0
                    sm = render_val(eval_calc(ictx, cm), mu) if cm is not None else None
                    sr = render_val(eval_calc(ictx, cr), mu) if cr is not None else None
                    if sm and sr and sm != sr:
                        return f"{sm}{pct}（遠程 {sr.replace('（依等級）', '')}{pct}）"
                    if sm or sr:
                        return (sm or sr) + pct
                except Miss:
                    pass
        v = lut.get(name)
        if v is None:
            miss += 1
            return ""
        return fmt(float(v) * (float(mul) if mul else 1)) + pct
    def cooldown(_m):
        s, m2 = fill("@Cooldown@", lut, calcs, ictx)
        # 查不到或不是單純數字就維持舊行為（拿掉）：這個佔位不算 miss，不可讓整行被 strip_holes 刪掉
        return f"（{s}秒）" if not m2 and re.fullmatch(r"[\d.]+", s) and float(s) > 0 else ""
    def split(m):
        suf = (m.group(1) or "").lower()
        cm = hget(ictx.calc, "meleeitemcalcvalue" + suf) if ictx is not None else None
        cr = hget(ictx.calc, "rangeditemcalcvalue" + suf) if ictx is not None else None
        try:
            sm = render_val(eval_calc(ictx, cm), 1.0) if cm is not None else None
            sr = render_val(eval_calc(ictx, cr), 1.0) if cr is not None else None
        except Miss:
            return ""
        # 妖夢鬼刀「惡影步伐」：這組佔位的值放在 mDataValues，不是計算式（官方 20% 近戰／15% 遠程）
        if sm is None and lut.get("meleeitemcalcvalue" + suf) is not None:
            sm = fmt(lut["meleeitemcalcvalue" + suf])
        if sr is None and lut.get("rangeditemcalcvalue" + suf) is not None:
            sr = fmt(lut["rangeditemcalcvalue" + suf])
        if sm and sr and sm != sr:
            return f"{sm}（遠程 {sr.replace('（依等級）', '')}）"
        return sm or sr or ""
    tpl = CD_DUP.sub(r"@\1@秒", tpl)
    if CD_TOK.search(tpl):
        tpl = CD_TOK.sub(cooldown, tpl)
    tpl = SPLIT_TOK.sub(split, tpl)
    tpl = ONHIT_TOK.sub("命中效果", tpl).replace("命中效果效果", "命中效果")
    miss += len(EXT.findall(tpl))  # 算進 miss，超過門檻 main 會退回 DDragon 原文
    t = TOK.sub(rep, EXT.sub("", tpl))
    t = NO_LIMIT.sub("（永久）", t)
    t = re.sub(r"(\d)（遠程 ([\d.]+)）%", r"\1%（遠程 \2%）", t)  # 模板把 % 接在佔位後面
    t = re.sub(r"(?<![\d.])([\d.]+)（\1秒）", r"\1秒", t)  # 模板先印數字再接冷卻佔位：神聖之劍「(90（90秒）)」
    t = re.sub(r"%\s+\(([\d.]+秒)\)", r"%（\1）", t)  # 狂風之力「最多50% (120秒)」：lint 錯誤級
    t = re.sub(r"\(（([\d.]+秒)）為", r"（冷卻\1，為", t).replace("為5秒)", "為5秒）")  # 潛行者之爪「({{ Item_Cooldown }}為5秒)」
    # 冷卻放進被動名稱（遊戲內就排在名稱旁邊）。留在內文的話，index.html 的道具標頭取內文第一行，
    # 破堡者標頭會只剩一行「（20秒）」（#2622）
    t = HEAD_CD.sub(lambda m: f"（{m.group(3) or ''}{m.group(4)}）{m.group(1)}</{m.group(2)}>", t)
    t = ICON.sub("", t)
    t = BRACE.sub("", t)
    # 值自帶屬性標籤，模板又接一次單位：石像鬼磐核「+5% 額外魔抗魔法防禦」（畫面上會變「魔防魔法防禦」）。
    # 道具不走 fetch_skills.finish，要自己清（#2620）
    t = re.sub(r"(護甲)(?:物防|物理防禦)|(魔抗)(?:魔防|魔法防禦)", lambda m: m.group(1) or m.group(2), t)
    t = re.sub(r"(\d)（每 1 物理致命 \+([\d.]+)）\s*%", r"\1%（每 1 物理致命 +\2%）", t)  # 公理弧刃：官方 10% (+.25% per lethality)（#2621）
    return t, miss

HEAD_SEG = re.compile(r"\s*(?:\{\{[^}]*\}\}\s*)*<(\w+)>[^<]*</\1>\s*(?:\{\{[^}]*\}\}\s*)*")

def strip_holes(tpl, lut, calcs, ictx=None):
    """把含查不到 token 的那幾行拿掉，連同只剩標題的上一行。回傳填好的內文。
    bin 沒有值就沒有正確的數字可以說：亡靈斗篷的 HealthRegenPassive 在 bin 是空的，
    飛翼月甲的跑速已經搬進基礎屬性。留著只會是「翱翔：提供跑速」這種沒有數字的句子。"""
    keep = []
    for seg in tpl.split("<br>"):
        if fill(seg, lut, calcs, ictx)[1]:
            while keep and (not keep[-1].strip() or HEAD_SEG.fullmatch(keep[-1])):
                keep.pop()
            continue
        keep.append(seg)
    while keep and not keep[-1].strip():
        keep.pop()
    return fill("<br>".join(keep), lut, calcs, ictx)[0]

def repair_dd(desc, lut, ictx=None):
    """DDragon 原文有基礎屬性以外的內文就修補回傳；沒有內文或修不好回 None。
    DDragon 會把計算式填成 0、冷卻填成 (0秒)：海克斯科技槍刃「(0秒)」「造成0魔法傷害」、
    神聖之劍「(90(0秒))」。"""
    m = re.search(r"</stats>", desc)
    rest = desc[m.end():] if m else desc
    if not re.sub(r"<[^>]+>|\s", "", rest):
        return None
    t = re.sub(r"(\d+)\(0秒\)", r"\1秒", desc)
    cd = lut.get("cooldown")
    t = t.replace("(0秒)", f"({fmt(cd)}秒)" if cd else "")
    zero = re.compile(r"(?<![\d.])0(?=(?:魔法|物理|真實)傷害)")
    if zero.search(t):
        calcs = list((ictx.calc if ictx is not None else {}).values())
        if len(calcs) != 1:
            return None  # 不知道該填哪一條，不猜
        try:
            s = render_split(ictx, calcs[0], 1.0)
        except Miss:
            return None
        if not s:
            return None
        t = zero.sub(s, t)
    return None if HOLE_RE.search(re.sub(r"<[^>]+>", "", t)) else t

def _mark(p):
    return p.read_text().strip() if p.exists() else ""

def _write(p, data):
    """先寫 tmp 再換名：中途被砍不留半個檔"""
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, p)

def read_prev():
    """上一版 items.js → (ITEM_DESC, ITEM_XTRA)；沒有或解不開回 ({}, {})，不擋這次建置"""
    try:
        js = OUT_JS.read_text(encoding="utf-8")
        a = js.index("=") + 1
        b = js.index(";window.ITEM_XTRA=")
        c = js.index(";window.ITEM_DESC_VER=")
        return json.loads(js[a:b]), json.loads(js[b + len(";window.ITEM_XTRA="):c])
    except (OSError, ValueError):
        return {}, {}

def digit_runs(html):
    return len(re.findall(r"\d+", re.sub(r"<[^>]+>", "", html)))

def main():
    ddv = json.loads(get(f"{DD_API}/api/versions.json", 30))[0]
    cdver = ""
    try:
        cdver = str(json.loads(get(URL_CDVER, 30)).get("version", ""))
    except Exception as e:
        print(f"（CDragon 版本查詢失敗，這班只看 DDragon 版本：{e}）")
    same_dd = _mark(MARK_F) == ddv
    same_cd = not cdver or _mark(CDVER_F) == cdver
    if not FORCE and same_dd and same_cd and OUT_JS.exists():
        print(f"items.js 已是 {ddv}（CDragon {cdver or '版本未知'}），跳過")
        return 0
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    need_dl = not (BIN_F.exists() and ST_F.exists() and same_dd and same_cd)
    try:
        if need_dl:  # 兩份都下載成功才寫進快取：不留「新 bin 配舊字串表」的半套
            print("下載 items bin…");   b = get(URL_BIN)
            print("下載 zh_tw 字串表…"); s = get(URL_ST)
            json.loads(b); json.loads(s)
            _write(BIN_F, b); _write(ST_F, s)
        dd = json.loads(get(f"{DD_API}/cdn/{ddv}/data/zh_TW/item.json", 60))["data"]
    except Exception as e:
        if not (_is_transient(e) and OUT_JS.exists()):
            raise
        old = _mark(MARK_F) or "？"
        print(f"⚠ 來源暫時抓不到（{e}），items.js 維持上一班的 {old}（DDragon 已是 {ddv}），下一班再試")
        return 0
    binj = json.loads(BIN_F.read_text(encoding="utf-8"))
    st   = json.loads(ST_F.read_text(encoding="utf-8")).get("entries", {})
    prev, prev_xtra = read_prev()

    out, filled_n, kept = {}, 0, []
    def _not_live(i):
        return not (dd[i].get("gold", {}).get("purchasable") and dd[i].get("maps", {}).get("11"))
    for iid in sorted(dd, key=lambda x: (_not_live(x), int(x))):
        if int(iid) >= 200000:
            continue  # 特殊模式變體（競技場 22xxxx 等）不作為正文來源
        name = dd[iid]["name"]
        if name in out:
            continue  # 同名以現行可買為準，再來才是較小 id
        # 主模板存在但為空字串 → 這道具的說明只有遊戲內統計/附註，正文以 DDragon 為準
        if st.get(f"item_{iid}_tooltip") == "":
            continue
        entry = binj.get(f"Items/{iid}")
        if not entry:
            continue
        tpl = pick_template(iid, entry, st)
        if tpl:  # @f1@/@f2@… 是遊戲內即時統計（已阻擋傷害量等），整句剔除
            tpl = "<br>".join(seg for seg in tpl.split("<br>") if not re.search(r"@f\d+@", seg))
            tpl = expand_tokens(tpl, st)
        if not tpl:
            continue
        lut = build_lut(entry)
        calcs = build_calcs(entry, lut)
        ictx = item_ctx(entry)
        body, miss = fill(tpl, lut, calcs, ictx)
        if miss > 3:
            continue  # 解不出的太多，寧可用 DDragon 原文
        # 值被剝掉留下「持續秒」這種沒有數字的句子 → 整件不收（2026-08-15 加，同 fetch_skills.HOLE_RE）。
        # ⚠ 不要「猜一個名字相近的欄位」來補：狂暴利刃(3097) 的模板要 @BleedDuration@、bin 只有
        #   BuffDuration=1.5，看起來可以套，但那是**字串表模板過期**（描述的是舊版的流血效果，
        #   bin 的值對應的是現版的充能箭）——套了會產生「數字對、文案錯」，比缺值更糟。
        if HOLE_RE.search(re.sub(r"<[^>]+>", "", body)):
            continue
        sm = re.search(r"<stats>[\s\S]*?</stats>", dd[iid].get("description", ""))
        stats = sm.group(0) + "<br><br>" if sm else ""
        text = f"<mainText>{stats}{body}</mainText>"
        # 這版的 token 查不到值，句子會少數字又不一定被 HOLE_RE 抓到（16.21 最終 bin 的傲慢「增加物理攻擊」）。
        # 上一版數字比較多就留上一版，下一次 CDragon 更新會再試。
        # 沒有更好的上一版：DDragon 有內文就用它（字串表模板過期時，例如終末戰戟、神聖之劍），
        # 否則把缺值的行拿掉。比數字時要連替代文字一起比，否則上一輪換上的 DDragon 文字會被當成「上一版比較好」，之後永遠不更新。
        if miss:
            cand = repair_dd(dd[iid].get("description", ""), lut, ictx) or re.sub(
                r"(?:<br>\s*)+(?=</mainText>)", "", f"<mainText>{stats}{strip_holes(tpl, lut, calcs, ictx)}</mainText>")
            if name in prev and digit_runs(prev[name]) > max(digit_runs(text), digit_runs(cand)):
                text = prev[name]
                kept.append(name)
            else:
                text = cand
        out[name] = text
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
            tpl = expand_tokens(tpl, st)
        if not (name and entry and tpl):
            continue
        lut = build_lut(entry)
        body, _m = fill(tpl, lut, build_calcs(entry, lut), item_ctx(entry))
        xtra[name] = {"d": f"<mainText>{body}</mainText>", "base": base,
                      "img": f"https://ddragon.leagueoflegends.com/cdn/{ddv}/img/item/{iid}.png"}
    if not out or len(out) < MIN_KEEP * len(prev):
        print(f"⚠ 只解析出 {len(out)} 件道具（上一版 {len(prev)} 件）⇒ 保留舊的 items.js 不覆寫，下一班重抓")
        return 1
    if kept:
        print(f"⚠ {len(kept)} 件道具這版有值查不到，沿用上一版文字：{'、'.join(kept[:12])}")
    # 只有 CDragon build 變、內容沒變：不換版本戳（換了前端快取會白白失效，也多一個資料 commit）
    if same_dd and out == prev and xtra == prev_xtra:
        if cdver:
            _write(CDVER_F, cdver.encode())
        print(f"items.js 內容沒變（CDragon {cdver}），不重寫")
        return 0
    changed = [k for k in out if k in prev and out[k] != prev[k]]
    from datetime import datetime
    ver = f"{ddv}-{datetime.now().strftime('%m%d%H%M')}"
    js = ("window.ITEM_DESC=" + json.dumps(out, ensure_ascii=False, separators=(",", ":"))
          + ";window.ITEM_XTRA=" + json.dumps(xtra, ensure_ascii=False, separators=(",", ":"))
          + f';window.ITEM_DESC_VER="{ver}";')  # 版本戳：讓前端 localStorage 快取隨 items.js 重建而失效
    _write(OUT_JS, js.encode("utf-8"))
    _write(MARK_F, ddv.encode())
    if cdver:
        _write(CDVER_F, cdver.encode())
    print(f"✅ items.js：{filled_n} 件道具（DDragon {ddv}，CDragon {cdver or '版本未知'}）")
    if same_dd and changed:
        print(f"   同一版內 CDragon 更新，{len(changed)} 件內容變了：{'、'.join(changed[:12])}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
