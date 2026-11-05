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

⚠ 快取用**兩把鍵**：DDragon 版本（變了整份重建）＋ CDragon build 版本（變了全部英雄重建）。
  只用 DDragon 版本會讓「改版當天 CDragon 還沒跟上」建出的舊數值卡整個版本週期，見 main() 的註解。
"""
import json, os, re, socket, sys, threading, time, urllib.error, urllib.request
from pathlib import Path
# 經典服（LoL Classic，DDragon 內部代號 Jade_*）不是我們要的資料（2026-07-31 使用者回報：
# 英雄Tier 出現經典服頭像）——它的 zh/en 名稱與現行英雄**完全相同**，混進來會造成同名重複與圖片誤植。
# 日後若 Riot 再開別的分支服，一樣在這裡擋掉。
CLASSIC_RE = re.compile(r"^(Jade|Classic|Legacy)_", re.I)   # 分支服前綴：不進資料

ROOT   = Path(__file__).resolve().parent.parent  # 專案根目錄（本腳本在 scripts\ 內）
CACHE  = ROOT / "csv_cache/skills_cache.json"
OUT_JS = ROOT / "skills.js"
DD_API = "https://ddragon.leagueoflegends.com"
CD_BIN = "https://raw.communitydragon.org/latest/game/data/characters/{c}/{c}.bin.json"
URL_ST = "https://raw.communitydragon.org/latest/game/zh_tw/data/menu/en_us/lol.stringtable.json"
ST_F   = ROOT / "csv_cache/items_st_zhtw.json"   # 與 fetch_items.py 共用同一份字串表快取

FORCE  = "--force" in sys.argv
SKILL_WORKERS = 6   # 逐英雄抓取的並行數（DDragon／CDragon 都是 CDN；見 main() 的註解）
BREAK_AFTER = 18    # 連續這麼多位暫時性失敗就不再上網（逾時 60 秒 × 18 ÷ 6 工人 ≈ 3 分鐘，下一班從沒建成的接著做）
ABORT_MSG = "這班不再上網"
SINGLE = None
if "--champ" in sys.argv:
    i = sys.argv.index("--champ")
    SINGLE = sys.argv[i+1] if i+1 < len(sys.argv) else None

class Transient(Exception):
    """CDragon bin 暫時抓不到（5xx／429／逾時／連線失敗）。跟 404（真的沒有 bin）分開：
    暫時性失敗不能建成「退回純描述」的條目——那會蓋掉上一版有數值的條目，見 main() 的「沿用上一版」。"""

def _is_transient(e):
    if isinstance(e, urllib.error.HTTPError):
        return e.code >= 500 or e.code == 429
    return isinstance(e, (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError))

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
# 代碼是掃全庫 bin 的計算式名稱認出來的（#2619）：6 是魔抗（加里歐 W MRRatio、波比 W BonusMR、奧恩 E MRRatio），
# 7 是移動速度（DashSpeed、珍娜 MSBonusMagicDamage）。舊表把 6 標成移動速度：加里歐 R 印「+100% 額外移動速度」，
# 其實是額外魔抗。3、5 全庫沒有人用。
# 4 是攻速（燼 CritMoveSpeedPercentASRatio）但刻意不標：它的係數尺度不一致（維爾戈、法洛士會印 +500%、+1400%），
# 卡特蓮娜 R 還是 AD × (1＋攻速) 的二階項，標了反而整條 Miss。略過就是基礎值。
# 29 是物理致命（#2621）：派克 W 官方 45% (+2% per 1 Lethality)，bin 係數 2.0；係數是「每 1 點」不是百分比，render_val 另外印。
STAT_ZH = {0: "AP", 1: "護甲", 2: "AD", 6: "魔抗", 7: "移動速度",
           8: "暴擊率", 11: "最大生命", 28: "生命", 29: "物理致命"}
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
        # 充能數與充能時間不在 DataValues，在技能本體；陣列格式相同（values[0] 是佔位）。
        # 舊版模板的 {{ ammorechargetime }} 一律空白：凱特琳 W「(充能時間秒)」
        for tok, field in (("maxammo", "mMaxAmmo"), ("ammorechargetime", "mAmmoRechargeTime")):
            if mspell.get(field) and tok not in self.dv:
                self.dv[tok] = mspell[field]
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

def _raw(v):
    """rng 字串先存原始精度，render_val 才四捨五入。先捨入再乘 100 會失真：娜妲 0.015 存成 0.01 再變 1%。"""
    return ("%.6f" % float(v)).rstrip("0").rstrip(".")

# 求值結果：flat = 每級固定值 list；scal = [(比例list, 屬性標籤)]；rng = "X－Y" 依等級字串
class Val:
    def __init__(self, flat=None, scal=None, rng=None, srng=None):
        self.flat = flat or []
        self.scal = scal or []
        self.rng  = rng
        self.srng = srng or []   # 係數本身依等級：[(rng 字串, 屬性標籤)]（卡特蓮娜匕首 +70－100% AP）
        self.stack = []          # 每層堆疊加多少：[每級係數 list]（納瑟斯 Q 每層 +1、姍娜 R 護盾每層 +1.5）
        self.tail = ""           # 倍率本身依等級：印在最後（悠咪 R 摯友治療「× 1.3－1.6（依等級）」）
        self.pct  = False

def _pos_scal(v):
    """有沒有印得出來的係數。負係數是執行時公式的殘留（暴擊×(攻速−1)，基礎值為 0），render_val 本來就丟掉。"""
    return any(any(r > 1e-9 for r in rs) for rs, _ in v.scal)

def _mk_rng(lo, hi):
    return f"{_raw(lo)}－{_raw(hi)}（依等級）"

def _rng_pair(rng):
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)－(-?\d+(?:\.\d+)?)（依等級）", rng)
    if not m:
        raise Miss("rng")
    return float(m.group(1)), float(m.group(2))

def _add_rng(a, b):
    """兩段依等級相加。以前後段直接蓋掉前段，Sum 裡的則整個丟掉。"""
    if not a or not b:
        return a or b
    (x1, x2), (y1, y2) = _rng_pair(a), _rng_pair(b)
    return _mk_rng(x1 + y1, x2 + y2)

MAX_LEVEL = 18

def breakpoints_end(part):
    """ByCharLevelBreakpoints 在 18 級的值。mBonusPerLevelAtAndAfter 是「從這級起每級加多少」且**取代**前一個速率，
    mAdditionalBonusAtThisLevel 是這一級一次加。**斷點沒寫速率＝速率歸零**：卡蜜兒 Q 40＋4/級、17 級的空斷點＝100（不是 108），
    賽娜被動 1＋1/級、11 級空斷點＝10，睿娜妲 9 級只有一次加＝2（Meraki 都對得上）。舊版把前者當一次加、後者與 mInitialBonusPerLevel 整個沒算：
    蓋倫被動 1.5＋0.2/級，7 級起 0.8/級，14 級起 0.4/級＝10.1（Wiki 同），舊版印 2.7；小吶兒跑速 0－20 印 0－2。"""
    v = hget(part, "mLevel1Value") or 0
    rate = hget(part, "mInitialBonusPerLevel") or 0
    bps = part.get("mBreakpoints") or []
    for lv in range(2, MAX_LEVEL + 1):
        for bp in bps:
            if bp.get("mLevel") != lv:
                continue
            v += hget(bp, "mAdditionalBonusAtThisLevel") or 0
            rate = hget(bp, "mBonusPerLevelAtAndAfter") or 0
        v += rate
    return v

def _mul_rng(flat, rng, m):
    """(固定值 + 依等級) × 倍率，回 (flat, rng)。倍率每級不同時範圍乘不出一個字串，
    改印「1 級值 × 每級倍率」：卡特蓮娜 E 重置 78－96%（依等級）× 冷卻 12/11/10/9/8 → 9.36/8.58/7.8/7.02/6.24 秒。"""
    if not rng or not m:
        return [x * k for x, k in zip(flat, m)] if flat else [], rng
    if len(set(m)) == 1:
        return [x * m[0] for x in flat], scale_rng(rng, m[0])
    lo = _rng_pair(rng)[0]
    return [((flat[i] if flat else 0) + lo) * k for i, k in enumerate(m)], None

def _zip_add(a, b):
    if not a: return list(b)
    if not b: return list(a)
    return [x + y for x, y in zip(a, b)]

def _stat_label(part):
    """屬性標籤；未知代碼回 None＝該係數項略過（整條計算式仍算得出基礎值）。
    以前是丟 Miss 讓整個數值消失（派克 W 只剩「%跑速」），寧可少一個係數也不要沒有數字。"""
    st = part.get("mStat", 0)
    if st == 12:
        # 12 是最大生命，配 mStatFormula 2 是額外生命（迦棱 W 的 18%、泰坦九頭蛇的 1%）。
        # 這裡以前標「當前生命」。真正吃當前生命的技能（蒙多 Q）文字寫在模板裡，不走這裡。
        return {1: "基礎生命", 2: "額外生命"}.get(part.get("mStatFormula", 0), "最大生命")
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
        name = str(part.get("mDataValue"))
        if name.lower().startswith("modes") and not hget(ctx.dv, name.lower()):
            return Val(flat=[0] * ctx.ranks)   # 其他模式才有的加值，一般模式沒定義＝0（奈德麗 W ModesBonusMaxTraps）
        return Val(flat=ctx.dvals(name))
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
        if sub.stack:   # 屬性 × 層數印不出來，別把層數那項靜靜丟掉
            raise Miss("statbysub")
        if sub.rng:
            # 係數依等級（路西恩 +50－60% AD）。舊版這裡一律 Miss，卡特蓮娜被動就只剩「造成 魔法傷害」。
            # sub.scal 是爆頭那種暴擊加成，略過：寧可少一個係數也不要沒有數字。
            if len(set(sub.flat)) > 1:
                raise Miss("statbysub")
            k = sub.flat[0] if sub.flat else 0
            lo, hi = _rng_pair(sub.rng)
            return Val(srng=[(_mk_rng(lo + k, hi + k), lab)])
        if sub.flat and not sub.scal:
            return Val(scal=[(sub.flat, lab)])
        if sub.scal:
            # 屬性 × 另一個屬性是二階項（逆命藍牌的暴擊加成、塔姆被動的「每 100 額外生命的 AP」），印不出來就略過。
            # 舊版整條 Miss：逆命 W 三種牌全空，退回純描述。
            return Val()
        raise Miss("statbysub")
    if t == "SumOfSubPartsCalculationPart":
        v = Val()
        for p in part.get("mSubparts") or []:
            s = eval_part(ctx, p, depth + 1)
            v.flat = _zip_add(v.flat, s.flat); v.scal += s.scal
            v.rng = _add_rng(v.rng, s.rng); v.srng += s.srng; v.stack += s.stack
        return v
    if t == "ProductOfSubPartsCalculationPart":
        a = eval_part(ctx, part.get("mPart1") or {}, depth + 1)
        b = eval_part(ctx, part.get("mPart2") or {}, depth + 1)
        for x, y in ((a, b), (b, a)):
            if y.flat and not y.scal and not y.rng and not y.srng and not y.stack:   # 其中一邊是純數 → 乘進另一邊
                m = y.flat
                if x.srng and len(set(m)) > 1:
                    raise Miss("product")
                flat, rng = _mul_rng(x.flat, x.rng, m)
                out = Val(flat=flat,
                          scal=[([r * k for r, k in zip(rs, m)], lb) for rs, lb in x.scal],
                          rng=rng,
                          srng=[(scale_rng(r, m[0]), lb) for r, lb in x.srng])
                out.stack = [[r * k for r, k in zip(rs, m)] for rs in x.stack]
                return out
        raise Miss("product")
    if t == "CooldownMultiplierCalculationPart":
        # 冷卻倍率＝1/(1+技能加速)，執行時才知道 → 用「無技能加速」的基礎值 1 呈現（賽勒斯 R 的 200%）
        return Val(flat=[1.0] * ctx.ranks)
    if t == "AbilityResourceByCoefficientCalculationPart":
        # 依魔力成長（水滴系的「2% 魔力轉物理攻擊」），bin 沒有 mStat，mStatFormula 2＝額外魔力
        lab = SF_ZH.get(part.get("mStatFormula", 0), "") + "魔力"
        return Val(scal=[([part.get("mCoefficient", 0)] * ctx.ranks, lab)])
    if t == "EffectValueCalculationPart" and getattr(ctx, "effect_1based", None) is not None:
        # 只有道具走這裡：道具的 mEffectAmount 是 1 起算、無前置佔位，技能有佔位，不可共用
        i = part.get("mEffectIndex", 0)
        if not 1 <= i <= len(ctx.effect_1based):
            raise Miss("effect")
        return Val(flat=[ctx.effect_1based[i - 1]] * ctx.ranks)
    if t == "EffectValueCalculationPart":
        # 技能：mEffectIndex 1 起算（第 1 組＝effect[0]），每組的 values[0] 是佔位，1～N 才是等級。
        # 凱莎 E：mEffectAmount[0]＝[.55, .55, .6, .65, .7, .75, .75] → 55/60/65/70/75%（Meraki 同）
        i = part.get("mEffectIndex", 0)
        vals = ctx.effect[i - 1] if 1 <= i <= len(ctx.effect) else None
        if not vals:
            raise Miss("effect")
        return Val(flat=vals[1:min(ctx.ranks, max(1, len(vals) - 1)) + 1])
    if t == "BuffCounterByCoefficientCalculationPart":
        # 每層加多少，層數執行時才知道 → 印係數，不當 0。舊版整條 Miss：納瑟斯 Q「造成物理傷害」沒有數字
        out = Val()
        out.stack = [[part.get("mCoefficient", 0)] * ctx.ranks]
        return out
    if t == "ClampSubPartsCalculationPart":
        # 夾在上下限之間。屬性項執行時才知道，以 0 屬性呈現（凱莎 E＝clamp(1 + 額外攻速, 1, 2) × 55%）。
        # 沒寫 mFloor＝0（bin 省略預設值）；寫 null＝沒有下限。卡莉絲塔 max(0, 攻速 - 上限) 的基礎值就是 0。
        v = Val()
        for p in part.get("mSubparts") or []:
            s = eval_part(ctx, p, depth + 1)
            if s.rng or s.srng or s.stack:
                raise Miss("clamp")
            v.flat = _zip_add(v.flat, s.flat)
        lo, hi = part.get("mFloor", 0), part.get("mCeiling")
        return Val(flat=[max(lo if lo is not None else x, min(hi if hi is not None else x, x))
                         for x in (v.flat or [0] * ctx.ranks)])
    if t == "BuffCounterByNamedDataValueCalculationPart":
        # 依當前堆疊層數成長，執行時才知道 → 以 0 層（基礎值）呈現，並印每層多少（翱銳龍獸 E 的處決門檻）
        out = Val(flat=[0] * ctx.ranks)
        try:
            out.stack = [ctx.dvals(part.get("mDataValue"))]
        except Miss:
            pass
        return out
    if "StartDataValue" in part:
        # 型別名是雜湊（{ee18a47b}）：ByCharLevelInterpolation 的 DataValue 版，頭尾各是一個 DataValue
        # （烏迪爾 Q 覺醒攻速、洛克 W 治療上限 100－500）。每級不同就印不成一個範圍。
        s, e = ctx.dvals(part["StartDataValue"]), ctx.dvals(part.get("EndDataValue"))
        if len(set(s)) > 1 or len(set(e)) > 1:
            raise Miss("interp-dv")
        return Val(flat=[s[0]] * ctx.ranks) if s[0] == e[0] else Val(rng=_mk_rng(s[0], e[0]))
    if "mSpellCalculationKey" in part:
        # 型別名是雜湊（{f3cbe7b2}）：引用同一技能的另一條計算式（悠咪 R 的 AllyHealingPerc）
        ref = hget(ctx.calc, str(part["mSpellCalculationKey"]).lower())
        if not ref:
            raise Miss("calckey")
        return eval_calc(ctx, ref, depth + 1)
    if t == "ByCharLevelInterpolationCalculationPart":
        s, e = part.get("mStartValue", 0), part.get("mEndValue", 0)
        if s == e:   # 兩端相同就不是依等級（貝爾薇斯被動舊版印 20－20%）
            return Val(flat=[s] * ctx.ranks)
        return Val(rng=_mk_rng(s, e))
    if t == "ByCharLevelFormulaCalculationPart":
        # 逐級查表：values[0] 是佔位，1～18 才是等級（之後是溢位用）。卡特蓮娜匕首 68.18…240.02（Wiki 68－240）。
        vals = part.get("values") or part.get("mValues") or []
        if len(vals) <= MAX_LEVEL:
            raise Miss("formula")
        lo, hi = [round(x) if abs(x) >= 10 else round(x, 2) for x in (vals[1], vals[MAX_LEVEL])]
        return Val(flat=[lo] * ctx.ranks) if lo == hi else Val(rng=_mk_rng(lo, hi))
    if t == "ByCharLevelBreakpointsCalculationPart":
        lv1 = part.get("mLevel1Value", 0)
        total = breakpoints_end(part)
        return Val(rng=_mk_rng(lv1, total) if abs(total - lv1) > 1e-6 else None,
                   flat=[lv1] * ctx.ranks if abs(total - lv1) <= 1e-6 else [])
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
            v.rng = _add_rng(v.rng, s.rng); v.srng += s.srng; v.stack += s.stack
        # GameCalculation 也可能自帶 mMultiplier（以前只在 GameCalculationModified 處理）——
        # 漏掉它＝關 E 的攻速變 3000%（30 × 0.01 × 100% 被算成 30 × 100%）
        mp = calc.get("mMultiplier")
        if mp:
            mv = eval_part(ctx, mp, depth + 1)
            if mv.flat and not _pos_scal(mv):
                m = mv.flat
                v.flat, v.rng = _mul_rng(v.flat, v.rng, m)
                v.scal = [([r * k for r, k in zip(rs, m)], lb) for rs, lb in v.scal]
                v.stack = [[r * k for r, k in zip(rs, m)] for rs in v.stack]
                if len(set(m)) == 1:
                    v.srng = [(scale_rng(r, m[0]), lb) for r, lb in v.srng]
        if calc.get("mDisplayAsPercent"):
            v.flat = [x * 100 for x in v.flat]
            v.scal = [([r * 100 for r in rs], lb) for rs, lb in v.scal]
            v.rng = scale_rng(v.rng, 100)  # 艾希被動緩速 0.2－0.3 其實是 20－30%
            v.srng = [(scale_rng(r, 100), lb) for r, lb in v.srng]
            v.stack = [[r * 100 for r in rs] for rs in v.stack]
            v.pct = True
        return v
    if t == "GameCalculationConditional":
        # 有沒有某個 buff 才換算式，tooltip 看的是平常的狀態（凱莎 Q 進化前的傷害上限）
        ref = hget(ctx.calc, str(calc.get("mDefaultGameCalculation", "")).lower())
        if not ref:
            raise Miss("condref")
        return eval_calc(ctx, ref, depth + 1)
    if t == "GameCalculationModified":
        ref = hget(ctx.calc, str(calc.get("mModifiedGameCalculation", "")).lower())
        if not ref:
            raise Miss("modref")
        base = eval_calc(ctx, ref, depth + 1)
        mul = eval_part(ctx, calc.get("mMultiplier") or {}, depth + 1)
        if mul.stack:
            raise Miss("mod-mult")
        if mul.rng and not mul.flat and not mul.scal and not mul.srng and not base.rng and not base.srng:
            # 倍率依等級：範圍乘不進每級數值，把倍率印在最後（悠咪 R：30/50/70/90/110（+12% AP）× 1.3－1.6（依等級））
            base.tail = mul.rng
            return base
        if not mul.flat:
            raise Miss("mod-mult")
        if _pos_scal(mul) and not _pos_scal(base) and not base.rng and not base.srng and not base.stack and not base.pct:
            # 基礎是純數，係數在倍率這邊：路西恩 R＝發數 × (基礎＋AD＋AP)
            out = Val(flat=[a * b for a, b in zip(base.flat, mul.flat)],
                      scal=[([a * r for a, r in zip(base.flat, rs)], lb) for rs, lb in mul.scal])
            return out
        # 其餘情況倍率裡的係數是二階項（弗力貝爾 W2＝傷害 × (1.5＋額外AD×0.25%)），略過
        m = mul.flat
        flat, rng = _mul_rng(base.flat, base.rng, m)
        out = Val(flat=flat,
                  scal=[([r * k for r, k in zip(rs, m)], lb) for rs, lb in base.scal],
                  rng=rng,
                  srng=[(scale_rng(r, m[0]), lb) for r, lb in base.srng] if len(set(m)) == 1 else base.srng)
        out.stack = [[r * k for r, k in zip(rs, m)] for rs in base.stack]
        out.pct = base.pct  # 少了這個，獄火手斧會印「7% 至 21」
        return out
    raise Miss(t or "calc")

def scale_rng(rng, k):
    """'110－280（依等級）' 乘倍率。rng 是字串，乘法算不到它：吸魔劍遠程 ×0.75 舊版印得跟近戰一樣。
    這裡不可捨入：蓋倫 1.5×0.01 捨成 0.01、再 ×100 就變 1%。捨入只在 show_rng（顯示那一刻）。"""
    if not rng:
        return rng
    return re.sub(r"-?\d+(?:\.\d+)?", lambda x: _raw(float(x.group(0)) * k), rng)

def show_rng(rng, k=1.0):
    return re.sub(r"-?\d+(?:\.\d+)?", lambda x: fmt(round(float(x.group(0)) * k, 2)), rng)

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
        rng = show_rng(v.rng, mult)
        rng = rng.replace("（依等級）", "%（依等級）") if v.pct else rng
        # 固定值加依等級：柔依 Q 舊版黏成「50/80/110/140/1702－9（依等級）」
        out = f"{out} + {rng}" if out else rng
    for r, lab in v.srng:
        piece = "+" + show_rng(r, 1 if v.pct else 100).replace("（依等級）", f"%（依等級） {lab}")
        out += f"（{piece}）" if out else piece
    # 負係數＝執行時公式的殘留項（路西恩 R＝22×(1+暴擊×(攻速−1))，基礎值就是 22）→ 丟掉，
    # 不然會印出「22（+-2200% 暴擊率）」這種東西
    merged = {}   # 同一屬性分兩項時合併（凱莎 Q 上限：+55% 額外AD 與 +68.75% 額外AD 分開印）
    for rs, lab in v.scal:
        if any(r > 1e-9 for r in rs):
            merged[lab] = [a + b for a, b in zip(merged[lab], rs)] if lab in merged else list(rs)
    for lab, rs in merged.items():
        vals = [r * (1 if v.pct else 100) for r in rs]
        if lab == "物理致命":
            # 係數是每 1 點（派克 R 2.0 不是 +200%），舊版沒標 29：R 的斬殺線少印一個係數
            piece = f"每 1 {lab} +{join_ranks(rs)}" + ("%" if v.pct else "")   # 派克被動 9%（每 1 +0.2%）
            out += f"（{piece}）" if out else piece
            continue
        if v.pct and max(vals) < 0.1:
            # 百分比裡的小係數（時現者每點額外魔力 +0.005%）四捨五入會變 +0%，改用每 100 點講
            piece = f"每 100 {lab} +{join_ranks([x * 100 for x in vals])}%"
            out += f"（{piece}）" if out else piece
            continue
        if lab == "暴擊率" and not v.pct and max(vals) >= 1000:
            # 平值對暴擊率的係數（奪魄之鐮 50＝滿暴擊 +50），舊寫法印「+5000% 暴擊率」
            piece = f"每 1% {lab} +{join_ranks([x / 10000 for x in vals])}"
            out += f"（{piece}）" if out else piece
            continue
        pct = join_ranks(vals)
        out += f"（+{pct}% {lab}）" if out else f"+{pct}% {lab}"
    for rs in v.stack:
        vals = [r * mult for r in rs]
        # 整條只有層數、係數 1 ＝遊戲裡的即時計數（達瑞文「獲得金幣總量」），沒有可以印的數字
        if not out and not v.pct and all(abs(x - 1) < 1e-9 for x in rs):
            continue
        # fmt 只留 2 位，煙龍 Q 每層 0.008 會變 0.01
        nums = "/".join(dict.fromkeys(("%.3f" % x).rstrip("0").rstrip(".") if abs(x) < 0.1 else fmt(x) for x in vals))
        piece = f"每層 +{nums}" + ("%" if v.pct else "")
        out += f"（{piece}）" if out else piece
    if out and v.tail:
        out += " × " + show_rng(v.tail)
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
    t = re.sub(r"(最大|額外|基礎)生命生命", r"\1生命", t)  # 模板「回復 X 生命」，X 自帶標籤
    # 同一種：波比 W「+16% 護甲物防」、道具「+5% 額外魔抗魔法防禦」，畫面上 chDispTxt 還會再變成「物防物防」
    t = re.sub(r"(護甲)(?:物防|物理防禦)|(魔抗)(?:魔防|魔法防禦)", lambda m: m.group(1) or m.group(2), t)
    t = re.sub(r"\+\s*\+(?=\d)", "+", t)              # 模板寫「+ 」、值又自帶 +：珍娜 W「+ +30%」、尼菈 R「(++20%」（#2620）
    t = re.sub(r"(\d%?)（依等級）\s*%", lambda m: m.group(1).rstrip("%") + "%（依等級）", t)  # 模板在 token 後面接的 %
    t = re.sub(r"(\d)（每 1 物理致命 \+([\d.]+)）\s*%", r"\1%（每 1 物理致命 +\2%）", t)  # 派克 W 模板 {{ movespeed }}%
    t = re.sub(r"(AP|AD|物攻|魔攻)\s*%(?![\d])", r"\1", t)   # 「+10% AP% 最大魔力」→ 尾巴那個 % 是模板的，值已自帶
    t = re.sub(r"[（(]\s*[+×xX]?\s*[)）]", "", t)      # 空括號
    t = re.sub(r"\s*[（(][^（()）]{1,6}[：:]\s*[)）]", "", t)   # 值沒填的括號註記：泰達米爾 Q「(上限：)」
    t = re.sub(r"(\d)\s+%", r"\1%", t)                # 「25 % 跑速」
    t = re.sub(r"%\s+(?=[（(])", "%", t)              # 「30% （+3% AP）」
    t = re.sub(r"[，、]\s*(?=[，、。])", "", t)        # 值被剝掉後的孤立標點
    t = re.sub(r"[：，、]\s*(?=。)", "", t)
    t = re.sub(r"[ \t]+(?=[。，、：；！？）])", "", t)     # 標點前空白（2026-09-07；merge_tr 早就有這條）
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

# ── 破句偵測（2026-08-15 加）────────────────────────────────────────────────
# token 填不出來時 finish() 會把 {{ }} 清掉，留下「持續秒」「在秒內」「賦予%最大生命」
# 這種**沒有數字的句子**——比整句不見還糟（使用者看到的是壞掉的文案，而不是少一句）。
# 只認「期待數值的動詞／副詞後面直接接單位或百分號」，才不會誤傷「一層堆層」「三次」「地點」
# 這類正常中文（那是我第一版規則踩過的坑：208 筆裡只有 4 筆是真的）。
# 實測：這條規則套過全庫 173 位英雄＋323 件道具，命中全部是真破句、零誤判（2026-08-15）。
# 要加單位字之前先跑一次全庫檢視——誤判的代價是好句子被整句刪掉。
# ⚠「發／顆／隻」已試過並移除：「持續發射兩列飛彈」（風暴手套）會被「持續」＋「發」打到。
#   單位字只留下不會當動詞用的那幾個。
# ⚠ 單位字後面要排掉「它其實是另一個詞的第一個字」的情形：秒表(Stopwatch)、個人檔案、名字…
HOLE_RE = re.compile(
    r"(?:持續|在|最多|最少|共|達|增加|獲得|回復|提升|縮短|延長|緩速|賦予)\s*"
    r"(?:秒(?![表錶])|層|次|碼|％|名(?![字稱單義])|個(?![人別體性月案]))(?![數量])"
    r"|(?<![\d.）)\]％%XxＸ])%(?=[一-鿿])")

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

def fill_tooltip(tpl, ctx, all_ctx, strict=False):
    """strict＝**任何**填不出來的 token 都比照 f-token 整句刪掉。
    只在第一輪填出破句（HOLE_RE）時才用，見 build_champ。"""
    miss = []
    def rep(m):
        tok, mul = m.group(1), float(m.group(2) or 1)
        try:
            return resolve_token(ctx, all_ctx, tok, mul)
        except Miss:
            miss.append(tok)
            # 無解的 f-token＝執行時才有的值（凱莎「當前擁有」、巴德「目前神龕數」…）→ 標記後整句刪，
            # 直接換成空字串會留下「當前擁有：/50額外攻速」這種殘句
            return SENT if (strict or F_TOK.match(tok)) else ""
    t = STRIP_RE.sub("", TAG_RE.sub("\n", TOKEN_RE.sub(rep, tpl)))
    if SENT in t:                                    # 先拆括號註記（墨菲特/賽特那種行內註記），再刪整句（凱莎/巴德那種獨立句）
        t = re.sub(r"[（(][^（()）]*" + SENT + r"[^（()）]*[)）]", "", t)
        t = "".join(p for p in re.split(r"(?<=[。\n])", t) if SENT not in p)
        t = t.replace(SENT, "")
    t = re.sub(r"^\s*[，。：、]\s*", "", finish(t), flags=re.M)
    return t.strip(), miss

NESTED_TPL = re.compile(r"\{\{\s*(Spell_\w+?_Tooltip_)\{\{\s*gamemodeinteger\s*\}\}\s*\}\}", re.I)
ST_NAME = re.compile(r"\{\{\s*(Spell_\w+?_Name)\s*\}\}", re.I)

def expand_tpl(tpl, st):
    """DDragon 只給殼的模板（甘普朗克 Q、阿克尚 W）：本文在字串表，_1 是一般模式，_2 是競技場。
    字串表用 @Token@ 寫法，轉成 {{ token }} 走同一套填值。沒字串表或查不到就原樣回傳（會退回純描述）。"""
    if not st or not tpl:
        return tpl
    def rep(m):
        body = st.get(m.group(1).lower() + "1")
        return re.sub(r"@([\w.:*-]+)@", r"{{ \1 }}", body) if body else m.group(0)
    tpl = NESTED_TPL.sub(rep, tpl)
    return ST_NAME.sub(lambda m: st.get(m.group(1).lower()) or m.group(0), tpl)

# ── 主流程 ────────────────────────────────────────────────────────────────────
def build_champ(cid, ddv, st=None):
    dd = get_json(f"{DD_API}/cdn/{ddv}/data/zh_TW/champion/{cid}.json")["data"][cid]
    low = cid.lower()
    try:
        binj = get_json(CD_BIN.format(c=low), timeout=60)
    except Exception as e:
        if _is_transient(e):
            raise Transient(f"CDragon bin 暫時抓不到：{e}") from e
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
            if sp.get("cost") and "cost" not in all_ctx[leaf].dv:   # {{ cost }}：卡莎碧雅 E 擊殺回魔。DDragon 陣列無佔位
                all_ctx[leaf].dv["cost"] = [0] + list(sp["cost"])
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
                txt, miss = fill_at(expand_tpl(tpl, st), SpellCtx(pspell, 1), all_ctx)
                if txt and len(miss) <= 2:
                    out["p"]["d"] = txt
        except Exception:
            pass
    for i, sp in enumerate(dd["spells"][:4]):
        leaf = str(sp.get("id", "")).lower()
        ctx = all_ctx.get(leaf)
        if ctx is not None:
            ctx.fmap = F_MAP.get((cid, keys[i]), {})   # 該技能的 f-token 對照（見 F_MAP）
        # rg＝施放距離（取各級最大；DDragon 的 range 是每級一個值）。
        # 給模擬BP 選角評分的「開戰能力」判定用（使用者定義 2026-08-08）：
        # 能在 >700 碼打出硬控、或能位移 >=700 碼者算開戰手段。原本用人工清單，
        # 使用者給了客觀定義後改成由這個數值＋技能敘述的硬控關鍵字自動判。
        # 全域技能（艾希R、逆命R 等）DDragon 給 25000，照收——那本來就是超遠距離起手。
        _rg = sp.get("range")
        _rg = max([v for v in _rg if isinstance(v, (int, float))] or [0]) if isinstance(_rg, list) else 0
        entry = {"k": keys[i], "n": sp["name"], "rg": int(_rg),
                 "cd": sp.get("cooldownBurn", ""), "co": sp.get("costBurn", "")}
        desc_plain = plain(sp.get("description", ""))
        tpl = expand_tpl(sp.get("tooltip", ""), st)
        if ctx and tpl:
            txt, miss = fill_tooltip(tpl, ctx, all_ctx)
            holed = 0
            # 值被剝掉後留下「持續秒」「賦予%最大生命」這種破句 → 改成把**那一句**丟掉。
            # 寧可少一句也不要沒有數字的句子（塔里克 W 就是這樣：被動那句是好的、主動那句壞掉）。
            if txt and HOLE_RE.search(txt):
                txt2, _m2 = fill_tooltip(tpl, ctx, all_ctx, strict=True)
                txt, holed = (txt2 if txt2 and not HOLE_RE.search(txt2) else ""), 1
            if txt and len(miss) <= 2:
                entry["d"] = txt
                if miss:
                    entry["m"] = len(miss)
                if holed:
                    entry["hole"] = 1      # 給快取失效用：CDragon 補上數值後要重建（見 main）
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

def _write_atomic(path, text):
    """先寫 tmp 再換名：被 run_update 的時間上限砍掉時，不留半個檔"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)

def _gaps(c):
    """條目缺值的技能數（退回純描述或有句子被略過）"""
    return sum(1 for s in c.get("s", []) if s.get("fb") or s.get("hole"))

def load_st(cdver):
    """zh_TW 字串表（被動模板用）。快取檔與 fetch_items 共用，由 fetch_items 跟著 CDragon build 更新；
    但兩支在同一階段並行，這邊可能先跑，所以快取比這個 build 舊時直接抓一份用（不寫檔，更新歸 fetch_items）。
    回傳 entries；抓不到退回快取檔；都沒有回 None。"""
    mark = ST_F.with_name("items_cache_cdver.txt")
    cur = mark.read_text(encoding="utf-8").strip() if mark.exists() else ""
    if ST_F.exists() and (not cdver or cur == cdver):
        return json.loads(ST_F.read_text(encoding="utf-8")).get("entries")
    try:
        req = urllib.request.Request(URL_ST, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=180) as r:
            raw = r.read().decode("utf-8")
        entries = json.loads(raw).get("entries")
        if entries:
            if not ST_F.exists():
                _write_atomic(ST_F, raw)
            return entries
        print("（字串表抓到空的）")
    except Exception as e:
        print(f"（字串表抓不到：{e}）")
    return json.loads(ST_F.read_text(encoding="utf-8")).get("entries") if ST_F.exists() else None

def main():
    ddv = get_json(f"{DD_API}/api/versions.json")[0]
    champs = sorted(k for k in get_json(f"{DD_API}/cdn/{ddv}/data/en_US/champion.json")["data"]
                    if not CLASSIC_RE.match(k))   # 濾掉經典服（見檔頭 CLASSIC_RE）
    cache = {}
    if CACHE.exists():
        try:
            cache = json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:
            cache = {}
    if cache.get("ver") != ddv:
        # 換版時把上一版的條目留成 prev：CDragon 暫時掛掉（Transient）的英雄沿用上一版，
        # 不要整份變成沒數值的純描述（2026-10-07 真實案發：26.20 當天 CDragon 全面 522，173 位全退回純描述）
        old = cache.get("champs") or {}
        prev = dict((cache.get("prev") or {}).get("champs") or {})
        prev.update({k: v for k, v in old.items()   # 舊版缺過值的條目不蓋掉更早一版完整的
                     if k not in prev or not any(s.get("fb") or s.get("hole") for s in v.get("s", []))})
        cache = {"ver": ddv, "champs": {},
                 "prev": {"ver": cache.get("ver") or (cache.get("prev") or {}).get("ver"), "champs": prev}}
    done = cache["champs"]
    # ★快取只以 DDragon 版本為鍵是不夠的：改版當天 CDragon 的 bin 常常還沒跟上，這時建出來的條目
    #   是上一版的數值，而 DDragon 版本一整個週期都不會再變。
    #   2026-08-15 案發：缺值的條目破句（卡特蓮娜 W「在秒內衰減至失效的%跑速」）⇒ 當時只重建 fb／hole 的英雄。
    #   2026-11-05 案發：沒缺值但數值是舊的，只重建缺值的抓不到。26.22 上線兩天，瑟雷西 R 還是 250/400/550
    #   （官方 patch notes 與 CDragon 都是 200/350/500），量到 11 位。
    #   所以 CDragon build 一變就全部重建（cdv_of 記每位是哪個 build 建的；一班全量約 30 秒）：
    #   中途被砍或有人抓不到，下一班只補沒建成的；舊條目留到新的建成才換。
    cdver = ""
    try:
        cdver = str(get_json("https://raw.communitydragon.org/latest/content-metadata.json").get("version", ""))
    except Exception as e:
        print(f"（CDragon 版本查詢失敗，這班不重建已有的條目：{e}）")
    cdv_of = cache.setdefault("cdv_of", {})
    if cdver:
        cache["cdver"] = cdver
    # 快取自我清理：上面的過濾只擋「這次要建的清單」，之前建過的分支服條目會留在快取裡、
    # 原封不動寫進 skills.js（2026-08-06 使用者回報英雄Tier 又出現舊版頭像）
    _cl = [k for k in done if CLASSIC_RE.match(k)]
    for _k in _cl:
        del done[_k]
    if _cl:
        print(f"（快取清掉 {len(_cl)} 位分支服英雄）")
    todo = [SINGLE] if SINGLE else champs
    print(f"DDragon {ddv}｜共 {len(todo)} 位英雄")
    # ★逐英雄抓取走小型執行緒池（2026-10-07 真實案發）：改版當天 172 位全量重建，CDragon 源站又慢
    #   （每份 bin 首位元組 ~20s、不少回 522），循序跑要 60 分鐘 ⇒ 被 run_update 的 30 分鐘上限砍掉（exit 124），
    #   skills.js 卡在上一版。build_champ 只讀不寫共用狀態，可以並行；done／快取只在主執行緒寫。
    from concurrent.futures import ThreadPoolExecutor, as_completed
    pend = [(i, cid) for i, cid in enumerate(todo)
            if FORCE or cid not in done or (cdver and cdv_of.get(cid) != cdver)]
    st = None
    if pend:
        try:
            st = load_st(cdver)
        except Exception as e:
            print(f"（字串表載入失敗：{e}）")
        if not st:   # 沒有字串表時重建會讓被動退回純描述，不拿它蓋掉這版已有的條目
            print("（字串表載入失敗，被動退回 DDragon 描述；這班不重建已有的條目）")
            st = None
            pend = [(i, cid) for i, cid in pend if FORCE or cid not in done]
    if any(cid in done for _, cid in pend):
        print(f"（CDragon build {cdver or '未知'}：重建 {len(pend)} 位）")
    abort = threading.Event()
    lock = threading.Lock()
    streak = [0]          # 連續次數在工人裡算：主執行緒收到結果時，工人已經把後面幾位打出去了
    aborted = kept = 0
    def _job(cid):
        if abort.is_set():
            raise Transient(ABORT_MSG)
        try:
            r = build_champ(cid, ddv, st)
            with lock:
                streak[0] = 0
            return r
        except Exception as e:
            if isinstance(e, Transient) or _is_transient(e):
                with lock:
                    streak[0] += 1
                    if streak[0] >= BREAK_AFTER:
                        abort.set()
            raise
        finally:
            time.sleep(0.15)
    with ThreadPoolExecutor(max_workers=SKILL_WORKERS) as ex:
        futs = {ex.submit(_job, cid): (i, cid) for i, cid in pend}
        for k, fu in enumerate(as_completed(futs), 1):
            i, cid = futs[fu]
            try:
                new = fu.result()
                # 同一版重建後缺值變多＝來源這班有問題（bin 404 或內容不全）：留舊條目，不記 build，下一班再試
                if not FORCE and cid in done and _gaps(new) > _gaps(done[cid]):
                    kept += 1
                    print(f"  [{i+1}/{len(todo)}] {cid} 這班缺值變多（{_gaps(done[cid])}→{_gaps(new)}），留舊條目", flush=True)
                else:
                    done[cid] = new
                    if cdver:
                        cdv_of[cid] = cdver
                    fb = sum(1 for s in new["s"] if s.get("fb"))
                    print(f"  [{i+1}/{len(todo)}] {cid} ✓" + (f"（{fb} 技能退回純描述）" if fb else ""), flush=True)
            except Exception as e:
                if str(e) == ABORT_MSG:
                    aborted += 1
                else:
                    kept += cid in done
                    print(f"  [{i+1}/{len(todo)}] {cid} ✗ {e}"
                          + ("（沿用這版舊條目）" if cid in done
                             else "（沿用上一版）" if cid in (cache.get("prev") or {}).get("champs", {}) else ""), flush=True)
            if k % 20 == 0:   # 每 20 位寫回一次：被上限砍掉時下一班從這裡接著做
                _write_atomic(CACHE, json.dumps(cache, ensure_ascii=False))
    _write_atomic(CACHE, json.dumps(cache, ensure_ascii=False))
    if abort.is_set():
        print(f"⚠ 連續 {BREAK_AFTER} 位暫時抓不到，{ABORT_MSG}")
    if kept or aborted:
        print(f"⚠ 重建沒完成：{kept} 位留舊條目、{aborted} 位這班沒試；數值可能還是舊的，下一班會再試")
    # 這一版沒建成的英雄沿用上一版（只補現行英雄清單裡的）；有沿用就把 v 留在上一版，
    # 讓健檢的「遊戲版本」那行繼續顯示不一致（技能其實還是舊版），不要假裝已經跟上
    pv = cache.get("prev") or {}
    fill = {k: v for k, v in (pv.get("champs") or {}).items() if k in champs and k not in done}
    if fill:
        print(f"⚠ {len(fill)} 位英雄這一版沒建成（CDragon 暫時抓不到）⇒ 沿用上一版 {pv.get('ver')}，"
              f"skills.js 的 v 維持 {pv.get('ver')}；下一班會再試")
    out_d = {**fill, **done}
    js = "window.CHAMP_SKILLS=" + json.dumps(   # 輸出層再擋一次分支服，任何來源都進不了 skills.js
        {"v": pv.get("ver") if fill else ddv,
         "d": {k: out_d[k] for k in sorted(out_d) if not CLASSIC_RE.match(k)}},   # 排序：並行完成順序不定
        ensure_ascii=False, separators=(",", ":")) + ";"
    _write_atomic(OUT_JS, js)
    ok = sum(1 for c in out_d.values() if not any(s.get("fb") for s in c["s"]))
    hole = sum(1 for c in out_d.values() for s in c["s"] if s.get("hole"))
    print(f"\n✅ skills.js：{len(out_d)} 位英雄（{ok} 位全技能含數值）"
          + (f"，{hole} 個技能有句子因缺值被略過（CDragon build 更新後會自動重建）" if hole else ""))

if __name__ == "__main__":
    main()
