# -*- coding: utf-8 -*-
"""
英雄技能每級數值：DDragon zh_TW tooltip 模板 + Community Dragon bin 數值 → skills.js

新版英雄的 DDragon tooltip 佔位符（{{ qdamage }} 等）在 DDragon 本身沒有資料，
唯一可靠來源是 CDragon 的 champion bin（DataValues + mSpellCalculations）。
本腳本解析 bin 計算式，把數值填回繁中 tooltip，輸出 skills.js 供 index.html 使用。

用法：
    python fetch_skills.py              # 版本沒變且已有快取的英雄跳過
    python fetch_skills.py --force      # 全部重算
    python fetch_skills.py --champ Taliyah   # 只跑一位（測試）
"""
import json, re, sys, time, urllib.request
from pathlib import Path

ROOT   = Path(__file__).resolve().parent.parent  # 專案根目錄（本腳本在 scripts\ 內）
CACHE  = ROOT / "csv_cache/skills_cache.json"
OUT_JS = ROOT / "skills.js"
DD_API = "https://ddragon.leagueoflegends.com"
CD_BIN = "https://raw.communitydragon.org/latest/game/data/characters/{c}/{c}.bin.json"
URL_ST = "https://raw.communitydragon.org/latest/game/zh_tw/data/menu/en_us/lol.stringtable.json"
ST_F   = ROOT / "csv_cache/items_st_zhtw.json"   # 與 fetch_items.py 共用同一份字串表快取

FORCE  = "--force" in sys.argv
SINGLE = None
if "--champ" in sys.argv:
    i = sys.argv.index("--champ")
    SINGLE = sys.argv[i+1] if i+1 < len(sys.argv) else None

def get_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

# ── 數字格式化 ────────────────────────────────────────────────────────────────
def fmt(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    f = round(f, 2)
    if f == int(f):
        return str(int(f))
    return ("%.2f" % f).rstrip("0").rstrip(".")

def join_ranks(vals):
    """[55,72.5,90] → '55/72.5/90'；全相同 → 單一值"""
    ss = [fmt(v) for v in vals]
    return ss[0] if len(set(ss)) == 1 else "/".join(ss)

# ── bin 計算式求值 ────────────────────────────────────────────────────────────
STAT_ZH = {0: "AP", 1: "護甲", 2: "AD", 3: "攻速", 5: "魔抗", 6: "移動速度",
           8: "暴擊率", 11: "最大生命", 12: "當前生命", 28: "生命"}
SF_ZH   = {1: "基礎", 2: "額外"}   # mStatFormula：1=基礎 2=額外 缺=總

class Miss(Exception):
    pass

def bin_hash(s):
    """CDragon bin 的未知鍵＝FNV-1a 32bit（小寫）雜湊，格式 {8位hex}"""
    h = 0x811c9dc5
    for b in s.lower().encode():
        h = ((h ^ b) * 0x01000193) & 0xffffffff
    return "{%08x}" % h

def hget(d, key):
    """字典查詢：原名 → 雜湊名 fallback"""
    if not d:
        return None
    v = d.get(key)
    return v if v is not None else d.get(bin_hash(key))

class SpellCtx:
    """單一技能的求值環境：DataValues / 計算式 / 等級數 / DDragon effect（e# 的第二來源）"""
    def __init__(self, mspell, ranks, dd_effect=None):
        self.ranks = ranks
        self.fmap = {}
        # DDragon spell.effect：[None, [每級值…], …]（無前置佔位，與 bin 的 mEffectAmount 不同）
        self.dd_effect = dd_effect or []
        self.dv = {}
        for d in (mspell.get("DataValues") or mspell.get("mDataValues") or []):
            name = d.get("name") or d.get("mName")
            vals = d.get("values") or d.get("mValues")
            if name and vals:
                self.dv[name.lower()] = vals
        self.calc = {k.lower(): v for k, v in (mspell.get("mSpellCalculations") or {}).items()}
        # mEffectAmount 兩種格式：[值...] 或 {"value":[值...]}
        self.effect = [e.get("value") if isinstance(e, dict) else e
                       for e in (mspell.get("mEffectAmount") or [])]

    def dvals(self, name):
        vals = hget(self.dv, str(name).lower())
        if not vals:
            raise Miss(name)
        n = min(self.ranks, max(1, len(vals) - 1))
        return [vals[i] for i in range(1, n + 1)]

# 求值結果：flat = 每級固定值 list；scal = [(比例list, 屬性標籤)]；rng = "X－Y" 依等級字串
class Val:
    def __init__(self, flat=None, scal=None, rng=None):
        self.flat = flat or []
        self.scal = scal or []
        self.rng  = rng
        self.pct  = False

def _zip_add(a, b):
    if not a: return list(b)
    if not b: return list(a)
    return [x + y for x, y in zip(a, b)]

def _stat_label(part):
    """屬性標籤；未知代碼回 None＝該係數項略過（整條計算式仍算得出基礎值）。
    以前是丟 Miss 讓整個數值消失（派克 W 只剩「%跑速」），寧可少一個係數也不要沒有數字。"""
    st = part.get("mStat", 0)
    lab = STAT_ZH.get(st)
    if lab is None:
        return None
    pre = SF_ZH.get(part.get("mStatFormula", 0), "")
    if pre and lab in ("AD", "AP", "護甲", "魔抗", "生命", "最大生命", "攻速", "移動速度"):
        lab = pre + lab
    return lab

def eval_part(ctx, part, depth=0):
    if depth > 6 or not isinstance(part, dict):
        raise Miss("depth")
    t = part.get("__type", "")
    if t == "NamedDataValueCalculationPart":
        return Val(flat=ctx.dvals(part.get("mDataValue")))
    if t == "NumberCalculationPart":
        return Val(flat=[part.get("mNumber", 0)] * ctx.ranks)
    if t == "StatByCoefficientCalculationPart":
        lab = _stat_label(part)
        return Val(scal=[([part.get("mCoefficient", 0)] * ctx.ranks, lab)]) if lab else Val()
    if t == "StatByNamedDataValueCalculationPart":
        lab = _stat_label(part)
        return Val(scal=[(ctx.dvals(part.get("mDataValue")), lab)]) if lab else Val()
    if t == "StatBySubPartCalculationPart":
        lab = _stat_label(part)
        sub = eval_part(ctx, part.get("mSubpart") or {}, depth + 1)
        if not lab:
            return Val()
        if sub.flat and not sub.scal:
            return Val(scal=[(sub.flat, lab)])
        raise Miss("statbysub")
    if t == "SumOfSubPartsCalculationPart":
        v = Val()
        for p in part.get("mSubparts") or []:
            s = eval_part(ctx, p, depth + 1)
            v.flat = _zip_add(v.flat, s.flat); v.scal += s.scal
        return v
    if t == "ProductOfSubPartsCalculationPart":
        a = eval_part(ctx, part.get("mPart1") or {}, depth + 1)
        b = eval_part(ctx, part.get("mPart2") or {}, depth + 1)
        for x, y in ((a, b), (b, a)):
            if y.flat and not y.scal:           # 其中一邊是純數 → 乘進另一邊
                m = y.flat
                return Val(flat=[v * k for v, k in zip(x.flat, m)] if x.flat else [],
                           scal=[([r * k for r, k in zip(rs, m)], lb) for rs, lb in x.scal])
        raise Miss("product")
    if t == "CooldownMultiplierCalculationPart":
        # 冷卻倍率＝1/(1+技能加速)，執行時才知道 → 用「無技能加速」的基礎值 1 呈現（賽勒斯 R 的 200%）
        return Val(flat=[1.0] * ctx.ranks)
    if t == "BuffCounterByNamedDataValueCalculationPart":
        # 依當前堆疊層數成長，執行時才知道 → 以 0 層（基礎值）呈現（翱銳龍獸 E 的處決門檻）
        return Val(flat=[0] * ctx.ranks)
    if t == "ByCharLevelInterpolationCalculationPart":
        s, e = part.get("mStartValue", 0), part.get("mEndValue", 0)
        return Val(rng=f"{fmt(s)}－{fmt(e)}（依等級）")
    if t == "ByCharLevelBreakpointsCalculationPart":
        lv1 = part.get("mLevel1Value", 0)
        total = lv1
        for bp in part.get("mBreakpoints") or []:
            total += bp.get("{d5fd07ed}", bp.get("mBonusPerLevelAtAndAfter", 0)) or 0
        return Val(rng=f"{fmt(lv1)}－{fmt(total)}（依等級）" if total != lv1 else None,
                   flat=[lv1] * ctx.ranks if total == lv1 else [])
    raise Miss(t or "part")

def eval_calc(ctx, calc, depth=0):
    if depth > 6:
        raise Miss("depth")
    t = calc.get("__type", "")
    if t == "GameCalculation" or "mFormulaParts" in calc:
        v = Val()
        for p in calc.get("mFormulaParts") or []:
            s = eval_part(ctx, p, depth + 1)
            v.flat = _zip_add(v.flat, s.flat); v.scal += s.scal
            if s.rng: v.rng = s.rng
        # GameCalculation 也可能自帶 mMultiplier（以前只在 GameCalculationModified 處理）——
        # 漏掉它＝關 E 的攻速變 3000%（30 × 0.01 × 100% 被算成 30 × 100%）
        mp = calc.get("mMultiplier")
        if mp:
            mv = eval_part(ctx, mp, depth + 1)
            if mv.flat and not mv.scal:
                m = mv.flat
                v.flat = [x * k for x, k in zip(v.flat, m)] if v.flat else []
                v.scal = [([r * k for r, k in zip(rs, m)], lb) for rs, lb in v.scal]
        if calc.get("mDisplayAsPercent"):
            v.flat = [x * 100 for x in v.flat]
            v.scal = [([r * 100 for r in rs], lb) for rs, lb in v.scal]
            v.pct = True
        return v
    if t == "GameCalculationModified":
        ref = hget(ctx.calc, str(calc.get("mModifiedGameCalculation", "")).lower())
        if not ref:
            raise Miss("modref")
        base = eval_calc(ctx, ref, depth + 1)
        mul = eval_part(ctx, calc.get("mMultiplier") or {}, depth + 1)
        if not (mul.flat and not mul.scal):
            raise Miss("mod-mult")
        m = mul.flat
        return Val(flat=[v * k for v, k in zip(base.flat, m)] if base.flat else [],
                   scal=[([r * k for r, k in zip(rs, m)], lb) for rs, lb in base.scal],
                   rng=base.rng)
    raise Miss(t or "calc")

def render_val(v, mult=1.0):
    """Val → 顯示字串：'55/72.5/90/107.5/125（+50% AP）'"""
    # 百分比不可乘兩次：計算式帶 mDisplayAsPercent 時值已是「38」這種百分數，
    # 模板又寫 {{ token*100 }} 就會變成 3800%（關 E 的 8000% 攻速、赫威 W 的 4000% 跑速就是這樣來的）
    if v.pct and abs(mult - 100) < 1e-9:
        mult = 1.0
    out = ""
    if v.flat and any(abs(x) > 1e-9 for x in v.flat):
        out = join_ranks([x * mult for x in v.flat]) + ("%" if v.pct else "")
    if v.rng:
        out += v.rng
    # 負係數＝執行時公式的殘留項（路西恩 R＝22×(1+暴擊×(攻速−1))，基礎值就是 22）→ 丟掉，
    # 不然會印出「22（+-2200% 暴擊率）」這種東西
    for rs, lab in [(rs, lab) for rs, lab in v.scal if any(r > 1e-9 for r in rs)]:
        pct = join_ranks([r * (1 if v.pct else 100) for r in rs])
        out += f"（+{pct}% {lab}）" if out else f"+{pct}% {lab}"
    return out or None

# ── 被動：CDragon 字串表模板（@token@ 風格）填值 ─────────────────────────────
AT_TOK = re.compile(r"@([A-Za-z_][\w.:]*?)(?:\*(-?[\d.]+))?@\s*(%?)")

def fill_at(tpl, ctx, all_ctx=None):
    """字串表模板的 @Token@ / @Token*100@ 填值（被動用，單一等級）；支援 @spell.X:Y@ 跨技能引用"""
    all_ctx = all_ctx or {}
    miss = []
    def rep(m):
        name, mul, pct = m.group(1), float(m.group(2) or 1), m.group(3)
        try:
            s = resolve_token(ctx, all_ctx, name, mul)   # 含 e#、跨技能(:)、calc、DataValue 解析
            if s:
                return s + pct
        except Miss:
            pass
        miss.append(name); return ""
    t = re.sub(r"<br\s*/?>", "\n", AT_TOK.sub(rep, tpl), flags=re.I)
    return finish(re.sub(r"<[^>]+>", "", t)), miss   # 收尾清理與 fill_tooltip / plain 共用同一套

# ── tooltip 模板填值 ──────────────────────────────────────────────────────────
TAG_RE   = re.compile(r"<br\s*/?>", re.I)
STRIP_RE = re.compile(r"<[^>]+>")
TOKEN_RE = re.compile(r"\{\{\s*([\w.:]+?)(?:\*(-?[\d.]+))?\s*\}\}")
SENT = "\x01"   # 無解 f-token 的標記（見 fill_tooltip：整句／整個括號刪掉，不留殘句）

def finish(t):
    """收尾清理：**三條產文路徑（fill_tooltip / fill_at / plain）必須共用這一套**。
    以前各寫各的，結果同一種殘留物在不同路徑漏掉（庫奇「暴擊：。」、薩科「30 %」就是 fill_at 沒清）。"""
    t = re.sub(r"%i:\w+%", "", t)                     # Riot 內嵌圖示佔位符
    t = re.sub(r"\{\{[^{}]*\}\}", "", t)              # 未填值 token
    t = re.sub(r"@[A-Za-z_][\w.:]*@", "", t)          # 字串表 @token@ 殘留
    t = re.sub(r"%{2,}", "%", t)                      # 「20%%失去生命」
    t = re.sub(r"(AP|AD|物攻|魔攻)\s*%(?![\d])", r"\1", t)   # 「+10% AP% 最大魔力」→ 尾巴那個 % 是模板的，值已自帶
    t = re.sub(r"[（(]\s*[+×xX]?\s*[)）]", "", t)      # 空括號
    t = re.sub(r"(\d)\s+%", r"\1%", t)                # 「25 % 跑速」
    t = re.sub(r"%\s+(?=[（(])", "%", t)              # 「30% （+3% AP）」
    t = re.sub(r"[，、]\s*(?=[，、。])", "", t)        # 值被剝掉後的孤立標點
    t = re.sub(r"[：，、]\s*(?=。)", "", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return re.sub(r"\n{2,}", "\n", t).strip()

def plain(txt):
    """DDragon 純描述（退回時用）"""
    return finish(STRIP_RE.sub("", TAG_RE.sub("\n", txt or "")))

# ── 舊制 formula slot（@f1@／{{ f11.1 }}）─────────────────────────────────────
# DDragon 的 spell.vars 早已停止提供，這些 token 是遊戲端執行時算的，bin 沒有同名欄位。
# 對得到 DataValue 的在此指定（名稱, 倍率）；查不到的一律當「執行時狀態」整句刪除。
# 對照方式：DDragon leveltip 的 effect 運算式＋tooltip 上下文（改版若數值不符，重查一次即可）。
F_MAP = {
    ("XinZhao", "E"): {"f1": ("ASMod", 100)},          # 攻速%：0.38/0.46/0.54/0.62/0.70 → 38…70
    ("Belveth", "Q"): {"f1": ("PerSideCooldown", 1)},  # 每個方向各自的冷卻：16/15/14/13/12 秒
    ("Belveth", "E"): {"f2": ("NumberOfStrikes", 1)},  # 期間攻擊次數：6
    ("Garen",   "E"): {"f1": ("NumTicks", 1)},         # 造成傷害次數：7
    ("Syndra",  "W"): {"f2": ("SlowDuration", 1)},     # 緩速持續：1.5 秒
    # 無解（執行時狀態，整句刪）：Aphelios R（武器名字串鍵）、Bard W（目前神龕數）、
    # Kaisa Q/W/E（當前擁有的攻擊力/攻速）、Malphite W（圖示旁即時護甲）、Sett W（真傷上限）
}
F_TOK = re.compile(r"^(f\d+)(?:\.\d+)?$", re.I)   # f11.1 的 .1＝小數位數指定，不是數值的一部分
SKIP_TOKENS = {"spellmodifierdescriptionappend"}

def resolve_token(ctx, all_ctx, tok, mult):
    tok = tok.lower()
    if tok in SKIP_TOKENS:
        return ""
    tok = re.sub(r"\.\d+$", "", tok)            # 結尾的 .N＝小數位數指定（slowpercent.0 / f11.1），不是名字的一部分
    tok = re.sub(r"^effect(\d+)amount$", r"e\1", tok)   # effect4amount＝e4 的另一種寫法（卡力斯 R 的跨技能引用）
    fm = F_TOK.match(tok)                      # 舊制 formula slot → 走 F_MAP 對照（查不到＝執行時狀態，丟 Miss）
    if fm:
        ent = getattr(ctx, "fmap", {}).get(fm.group(1))
        if not ent:
            raise Miss(tok)
        vals = hget(ctx.dv, ent[0].lower())
        if not vals:
            raise Miss(tok)
        n = min(ctx.ranks, max(1, len(vals) - 1))
        return join_ranks([vals[k] * ent[1] * mult for k in range(1, n + 1)])
    if ":" in tok:                       # spell.xxxq:token → 跨技能
        left, tok2 = tok.rsplit(":", 1)
        leaf = left.split(".")[-1]
        ctx2 = all_ctx.get(leaf)
        if not ctx2:
            raise Miss(tok)
        return resolve_token(ctx2, all_ctx, tok2, mult)
    if tok.startswith("e") and tok[1:].isdigit():   # 舊制 e1..eN
        i = int(tok[1:])
        # **DDragon 的 spell.effect 優先**：tooltip 的 e# 編號就是 DDragon 這個陣列的索引；
        # bin 的 mEffectAmount 排序不一定相同（卡爾瑟斯 W 的 e1 用 bin 會抓到牆寬 800 而不是魔防 25%）。
        de = ctx.dd_effect
        if de and i < len(de) and de[i]:
            vals = de[i]
            n = min(ctx.ranks, max(1, len(vals)))
            return join_ranks([vals[k] * mult for k in range(0, n)])
        if ctx.effect and i < len(ctx.effect) and ctx.effect[i]:
            vals = ctx.effect[i]
            n = min(ctx.ranks, max(1, len(vals) - 1))
            return join_ranks([vals[k] * mult for k in range(1, n + 1)])
        raise Miss(tok)
    c = hget(ctx.calc, tok)
    if c is not None:
        s = render_val(eval_calc(ctx, c), mult)
        if s:
            return s
        raise Miss(tok)
    vals = hget(ctx.dv, tok)
    if vals:
        n = min(ctx.ranks, max(1, len(vals) - 1))
        return join_ranks([vals[k] * mult for k in range(1, n + 1)])
    # 最後手段：只找「本技能的子技能／buff 技能物件」（leaf 名以本技能 leaf 為前綴，如 PykeW → PykeWBuff）。
    # 鐵則：不可跨技能亂找同名欄位——duration/movespeed 這種名字滿場都是，抓錯會填出「持續 0.01 秒」這種錯數字，
    # 錯的數值比缺數值更糟。
    base = getattr(ctx, "leaf", "")
    if base:
        for leaf, ctx2 in (all_ctx or {}).items():
            if ctx2 is ctx or not leaf.startswith(base):
                continue
            v2 = hget(ctx2.dv, tok)
            if v2:
                n = min(ctx.ranks, max(1, len(v2) - 1))
                return join_ranks([v2[k] * mult for k in range(1, n + 1)])
            c2 = hget(ctx2.calc, tok)
            if c2 is not None:
                try:
                    s = render_val(eval_calc(ctx2, c2), mult)
                    if s:
                        return s
                except Miss:
                    pass
    raise Miss(tok)

def fill_tooltip(tpl, ctx, all_ctx):
    miss = []
    def rep(m):
        tok, mul = m.group(1), float(m.group(2) or 1)
        try:
            return resolve_token(ctx, all_ctx, tok, mul)
        except Miss:
            miss.append(tok)
            # 無解的 f-token＝執行時才有的值（凱莎「當前擁有」、巴德「目前神龕數」…）→ 標記後整句刪，
            # 直接換成空字串會留下「當前擁有：/50額外攻速」這種殘句
            return SENT if F_TOK.match(tok) else ""
    t = STRIP_RE.sub("", TAG_RE.sub("\n", TOKEN_RE.sub(rep, tpl)))
    if SENT in t:                                    # 先拆括號註記（墨菲特/賽特那種行內註記），再刪整句（凱莎/巴德那種獨立句）
        t = re.sub(r"[（(][^（()）]*" + SENT + r"[^（()）]*[)）]", "", t)
        t = "".join(p for p in re.split(r"(?<=[。\n])", t) if SENT not in p)
        t = t.replace(SENT, "")
    t = re.sub(r"^\s*[，。：、]\s*", "", finish(t), flags=re.M)
    return t.strip(), miss

# ── 主流程 ────────────────────────────────────────────────────────────────────
def build_champ(cid, ddv, st=None):
    dd = get_json(f"{DD_API}/cdn/{ddv}/data/zh_TW/champion/{cid}.json")["data"][cid]
    low = cid.lower()
    try:
        binj = get_json(CD_BIN.format(c=low), timeout=60)
    except Exception:
        binj = {}
    # 全部技能物件的求值環境（leaf 名 → ctx），供跨技能 token
    all_ctx = {}
    leaf_of = {}
    for k, v in binj.items():
        if isinstance(v, dict) and "mSpell" in v:
            leaf = k.rsplit("/", 1)[-1].lower()
            leaf_of[leaf] = v["mSpell"]
    out = {"n": dd["name"], "t": dd.get("title", ""),
           "p": {"n": dd["passive"]["name"],
                 "d": plain(dd["passive"]["description"])},
           "s": []}
    keys = ["Q", "W", "E", "R"]
    # 先建各技能 ctx。**bin 裡的每個技能物件都要建**（不只 QWER 四個）——
    # 跨技能 token 常指向子技能／被動技能物件（spell.hweiqe:slowpercent、spell.veigarpassive:…），
    # 只放四個主技能的話這些一律 Miss（顯示成缺數字）。
    for leaf, ms in leaf_of.items():
        all_ctx[leaf] = SpellCtx(ms, 5)
        all_ctx[leaf].leaf = leaf
    for i, sp in enumerate(dd["spells"][:4]):
        leaf = str(sp.get("id", "")).lower()
        ms = leaf_of.get(leaf)
        ranks = sp.get("maxrank") or (3 if i == 3 else 5)
        if ms:
            all_ctx[leaf] = SpellCtx(ms, ranks, sp.get("effect"))   # 主技能帶上 DDragon effect（e# 第二來源）
            all_ctx[leaf].leaf = leaf
    # 被動數值：字串表模板（@token@，含跨技能 @spell.X:Y@）＋ bin 被動技能求值；失敗就保留 DDragon 純描述
    if st:
        try:
            rootk = next((k for k in binj if k.endswith("/CharacterRecords/Root")), None)
            ppath = rootk and binj[rootk].get("mCharacterPassiveSpell")
            pspell = binj.get(ppath, {}).get("mSpell") if ppath else None
            lk = ((pspell or {}).get("mClientData") or {}).get("mTooltipData", {}).get("mLocKeys", {})
            tpl = st.get(str(lk.get("keyTooltip", "")).lower())
            if pspell and tpl:
                txt, miss = fill_at(tpl, SpellCtx(pspell, 1), all_ctx)
                if txt and len(miss) <= 2:
                    out["p"]["d"] = txt
        except Exception:
            pass
    for i, sp in enumerate(dd["spells"][:4]):
        leaf = str(sp.get("id", "")).lower()
        ctx = all_ctx.get(leaf)
        if ctx is not None:
            ctx.fmap = F_MAP.get((cid, keys[i]), {})   # 該技能的 f-token 對照（見 F_MAP）
        entry = {"k": keys[i], "n": sp["name"],
                 "cd": sp.get("cooldownBurn", ""), "co": sp.get("costBurn", "")}
        desc_plain = plain(sp.get("description", ""))
        tpl = sp.get("tooltip", "")
        if ctx and tpl:
            txt, miss = fill_tooltip(tpl, ctx, all_ctx)
            if txt and len(miss) <= 2:
                entry["d"] = txt
                if miss:
                    entry["m"] = len(miss)
            else:
                entry["d"] = desc_plain
                entry["fb"] = 1
        else:
            entry["d"] = desc_plain
            entry["fb"] = 1
        # 補充：主要計算式一覽（傷害/治療/護盾類），fallback 時尤其有用
        if ctx:
            extras = []
            for name, c in ctx.calc.items():
                if not re.search(r"damage|heal|shield", name):
                    continue
                if isinstance(c, dict) and c.get("tooltipOnly"):
                    continue
                try:
                    s = render_val(eval_calc(ctx, c))
                except Miss:
                    continue
                if s and s not in (entry.get("d") or ""):
                    extras.append(f"{name}:{s}")
            if entry.get("fb") and extras:
                entry["x"] = extras[:4]
        out["s"].append(entry)
    return out

def main():
    ddv = get_json(f"{DD_API}/api/versions.json")[0]
    champs = sorted(get_json(f"{DD_API}/cdn/{ddv}/data/en_US/champion.json")["data"].keys())
    # zh_TW 字串表（被動模板用），與 fetch_items 共用快取
    st = None
    try:
        if not ST_F.exists():
            import urllib.request as _u
            req = _u.Request(URL_ST, headers={"User-Agent": "Mozilla/5.0"})
            ST_F.parent.mkdir(parents=True, exist_ok=True)
            ST_F.write_bytes(_u.urlopen(req, timeout=180).read())
        st = json.loads(ST_F.read_text(encoding="utf-8")).get("entries")
    except Exception as e:
        print(f"（字串表載入失敗，被動退回 DDragon 描述：{e}）")
    cache = {}
    if CACHE.exists():
        try:
            cache = json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:
            cache = {}
    if cache.get("ver") != ddv:
        cache = {"ver": ddv, "champs": {}}
    done = cache["champs"]
    todo = [SINGLE] if SINGLE else champs
    print(f"DDragon {ddv}｜共 {len(todo)} 位英雄")
    for i, cid in enumerate(todo):
        if not FORCE and cid in done:
            continue
        try:
            done[cid] = build_champ(cid, ddv, st)
            fb = sum(1 for s in done[cid]["s"] if s.get("fb"))
            print(f"  [{i+1}/{len(todo)}] {cid} ✓" + (f"（{fb} 技能退回純描述）" if fb else ""))
        except Exception as e:
            print(f"  [{i+1}/{len(todo)}] {cid} ✗ {e}")
        time.sleep(0.15)
        if (i + 1) % 20 == 0:
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    js = "window.CHAMP_SKILLS=" + json.dumps(
        {"v": ddv, "d": done}, ensure_ascii=False, separators=(",", ":")) + ";"
    OUT_JS.write_text(js, encoding="utf-8")
    ok = sum(1 for c in done.values() if not any(s.get("fb") for s in c["s"]))
    print(f"\n✅ skills.js：{len(done)} 位英雄（{ok} 位全技能含數值）")

if __name__ == "__main__":
    main()
