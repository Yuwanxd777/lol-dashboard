# -*- coding: utf-8 -*-
"""fetch_items 缺值 token 的處理（2026-11-05 精進迴圈 #2616）。

素材是 16.22 真實 bin 與字串表的節錄，寫死在這裡。只測純函式，不開任何路徑、不上網。
環境變數 TOKENS_SCRIPTS 可指到別的 scripts 目錄（突變測試用）。"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get("TOKENS_SCRIPTS", HERE))
import fetch_items as fi

fails = 0
def ok(cond, label):
    global fails
    print(("✓ " if cond else "✗ ") + label)
    if not cond:
        fails += 1

NUM = lambda n, v: {"mName": n, "mValue": v}
GC = "GameCalculation"
REAVER = {"mDataValues": [NUM("BaseADRatio", 1.25), NUM("CritChanceMultiplier", 50.0)],
          "mItemCalculations": {"TotalManaRefund": {"mMultiplier": {"mNumber": 0.5, "__type": "NumberCalculationPart"},
                                                    "mModifiedGameCalculation": "SpellbladeDamage", "__type": "GameCalculationModified"},
                                "SpellbladeDamage": {"mFormulaParts": [{"mStat": 2, "mStatFormula": 1, "mDataValue": "BaseADRatio", "__type": "StatByNamedDataValueCalculationPart"},
                                                                       {"mStat": 8, "mDataValue": "CritChanceMultiplier", "__type": "StatByNamedDataValueCalculationPart"}], "__type": GC}}}
MAW = {"mDataValues": [NUM("LowHealthThreshold", 0.3), NUM("ShieldLifetime", 2.5), NUM("Cooldown", 90.0)],
       "mItemCalculations": {"MeleeItemCalcValue": {"mFormulaParts": [{"mStartValue": 110.0, "mEndValue": 280.0, "__type": "ByCharLevelInterpolationCalculationPart"}], "__type": GC},
                             "RangedItemCalcValue": {"mMultiplier": {"mNumber": 0.75, "__type": "NumberCalculationPart"}, "mModifiedGameCalculation": "MeleeItemCalcValue", "__type": "GameCalculationModified"}}}
FROST = {"mDataValues": [NUM("SlowAmount", 0.25), NUM("RangedSlowAmount", 0.125)],
         "mItemCalculations": {"MeleeItemCalcValue": {"mFormulaParts": [{"mDataValue": "SlowAmount", "__type": "NamedDataValueCalculationPart"}], "mDisplayAsPercent": True, "__type": GC},
                               "RangedItemCalcValue": {"mFormulaParts": [{"mDataValue": "RangedSlowAmount", "__type": "NamedDataValueCalculationPart"}], "mDisplayAsPercent": True, "__type": GC}}}
GUNBLADE = {"mDataValues": [NUM("SlowAmount", 0.25), NUM("SlowDuration", 1.5), NUM("Cooldown", 60.0)],
            "mItemCalculations": {"ActiveDamage": {"mFormulaParts": [{"mStartValue": 175.0, "mEndValue": 253.0, "__type": "ByCharLevelInterpolationCalculationPart"},
                                                                     {"mCoefficient": 0.3, "__type": "StatByCoefficientCalculationPart"}], "__type": GC}}}
COWL = {"mDataValues": [{"mName": "HealthRegenPassive"}, NUM("HealthRegenDuration", 10.0)]}
BOOTS = {"mEffectAmount": [0, 0, 0, 0, 0, 0, 0, 25.0]}
TWOCALC = {"mDataValues": [NUM("Cooldown", 30.0)],
           "mItemCalculations": {"A": {"mFormulaParts": [{"mNumber": 10.0, "__type": "NumberCalculationPart"}], "__type": GC},
                                 "B": {"mFormulaParts": [{"mNumber": 20.0, "__type": "NumberCalculationPart"}], "__type": GC}}}

def fill(e, tpl):
    lut = fi.build_lut(e)
    return fi.fill(tpl, lut, fi.build_calcs(e, lut), fi.item_ctx(e))
def strip(e, tpl):
    lut = fi.build_lut(e)
    return fi.strip_holes(tpl, lut, fi.build_calcs(e, lut), fi.item_ctx(e))
def repair(e, desc):
    return fi.repair_dd(desc, fi.build_lut(e), fi.item_ctx(e))

print("── 近戰／遠程固定名字的一對")
t, m = fill(MAW, "可吸收<shield>@MeleeRangedSplit@魔法傷害的護盾</shield>")
ok(m == 0 and "110－280（依等級）（遠程 82.5－210）" in t, f"吸魔劍護盾帶遠程值：{t}")
t, m = fill(FROST, "緩速@SlowAmountMeleeRangedSplit@的領域")
ok(m == 0 and "25%（遠程 12.5%）" in t, f"寒冰霸拳緩速：{t}")
t, m = fill(COWL, "緩速@SlowAmountMeleeRangedSplit@的領域")
ok(m == 1, "沒有那對計算式仍然算缺值")
t, m = fill(GUNBLADE, "緩速@XMeleeRangedSplit@的領域")
ok(m == 1, "有別的計算式也不可亂套")

SPLIT = {"mDataValues": [NUM("Mult", 0.8)],
         "mItemCalculations": {"Hit": {"mFormulaParts": [{"mStartValue": 100.0, "mEndValue": 200.0, "__type": "ByCharLevelInterpolationCalculationPart"}],
                                       "mRangedMultiplier": {"mDataValue": "Mult", "__type": "NamedDataValueCalculationPart"}, "__type": "{e9a3c91d}"}}}
t, m = fill(SPLIT, "造成@Hit@傷害")
ok(m == 0 and "100－200（依等級）（遠程 80－160）" in t, f"mRangedMultiplier 也要乘依等級的值：{t}")

print("── 依等級的值要吃倍率與百分比")
from fetch_skills import SpellCtx, Val, eval_calc, finish, render_val, scale_rng
def rng_val(calc, dvs=None):
    ctx = SpellCtx({"mDataValues": dvs or [], "mSpellCalculations": {"base": BASE, "x": calc}}, 1)
    return render_val(eval_calc(ctx, calc))
BASE = {"mFormulaParts": [{"mStartValue": 0.015, "mEndValue": 0.3, "__type": "ByCharLevelInterpolationCalculationPart"}], "__type": GC}
PCT = {"mFormulaParts": BASE["mFormulaParts"], "mDisplayAsPercent": True, "__type": GC}
ok(rng_val(PCT) == "1.5－30%（依等級）", f"mDisplayAsPercent 換算，原始精度不失真（0.015 不可變 1%）：{rng_val(PCT)}")
ok(rng_val(BASE) == "0.01－0.3（依等級）", f"一般值顯示才捨入：{rng_val(BASE)}")
MULT = {"mFormulaParts": BASE["mFormulaParts"], "mMultiplier": {"mNumber": 2.0, "__type": "NumberCalculationPart"}, "__type": GC}
ok(rng_val(MULT) == "0.03－0.6（依等級）", f"GameCalculation 自帶 mMultiplier：{rng_val(MULT)}")
MOD = {"mMultiplier": {"mNumber": 0.5, "__type": "NumberCalculationPart"}, "mModifiedGameCalculation": "base", "__type": "GameCalculationModified"}
ok(rng_val(MOD) == "0.01－0.15（依等級）", f"GameCalculationModified：{rng_val(MOD)}")
ok(render_val(Val(rng="10－20（依等級）"), 100.0) == "1000－2000（依等級）", "模板倍率也要乘")
_pv = Val(rng="10－20（依等級）"); _pv.pct = True
ok(render_val(_pv, 100.0) == "10－20%（依等級）", "已是百分比時模板的 *100 不可再乘")
BP = {"mFormulaParts": [{"mLevel1Value": 0.1, "mBreakpoints": [{"mLevel": 10, "mAdditionalBonusAtThisLevel": 0.0125}], "__type": "ByCharLevelBreakpointsCalculationPart"}], "mDisplayAsPercent": True, "__type": GC}
ok(rng_val(BP) == "10－11.25%（依等級）", f"斷點型也一樣：{rng_val(BP)}")
ok(finish("10－25（依等級）%攻速") == "10－25%（依等級）攻速", "模板接的 % 併進去")
ok(finish("5－99%（依等級）% 攻速") == "5－99%（依等級） 攻速", "已有 % 不重複")
ok(finish("3－4（依等級）生命") == "3－4（依等級）生命", "沒有 % 不動")

print("── 平值對暴擊率的係數")
t, m = fill(REAVER, "@SpellbladeDamage@傷害，@TotalManaRefund@魔力")
ok("5000%" not in t and "2500%" not in t, f"不再印 5000%：{t}")
ok("每 1% 暴擊率 +0.5）" in t and "每 1% 暴擊率 +0.25）" in t, "傷害 0.5、魔力 0.25")
from fetch_skills import Val, render_val
ok(render_val(Val(scal=[([1.0], "暴擊率")])) == "+100% 暴擊率", "小係數維持原寫法（燼、路西恩）")
ok(render_val(Val(scal=[([4.0], "暴擊率")])) == "+400% 暴擊率", "+400% 仍是原寫法")
ok("每 1%" not in render_val(Val(scal=[([50.0], "AP")])), "別的屬性不受影響")

print("── 拿掉缺值的行")
tpl = "<passive>無形</passive><br>受到來自英雄的傷害後，獲得<scaleHealth>@HealthRegenPassive*100@%基礎生命回復</scaleHealth>，持續@HealthRegenDuration@秒。"
ok(strip(COWL, tpl) == "", "亡靈斗篷：句子與標題都拿掉")
tpl = "<attention>%i:scaleMS% @Effect8Amount@</attention>跑速<br>脫離戰鬥至少5秒後，效果增加至<attention>%i:scaleMS% @BootsMSBuff@</attention>跑速。"
r = strip(BOOTS, tpl)
ok("25" in r and "脫離戰鬥" not in r, f"疾行之靴：留有值的那行：{r}")
tpl = "<passive>甲</passive><br>持續@HealthRegenDuration@秒。<br><br><passive>乙</passive><br>@Nope@傷害"
r = strip(COWL, tpl)
ok("甲" in r and "10秒" in r and "乙" not in r, f"只拿掉壞的那段：{r}")
ok(not r.endswith("<br>"), "尾端不留 <br>")
ok(strip(COWL, "持續@HealthRegenDuration@秒。<br>") == "持續10秒。", "模板自己結尾的 <br> 也不留")
ok(strip(COWL, "{{ Item_Passive_List }}<li><passive>翱翔：</passive>提供@MovementSpeed*100@%跑速。") == "", "單行模板整行拿掉")

print("── DDragon 原文修補")
STATS = "<mainText><stats><attention>80</attention> 魔法攻擊</stats><br><br>"
r = repair(GUNBLADE, STATS + "<active>主動</active> (0秒)<br>電擊目標，造成0魔法傷害並緩速25%。</mainText>")
ok(r and "(60秒)" in r and "175－253（依等級）（+30% AP）魔法傷害" in r, f"海克斯科技槍刃：{r}")
r = repair(GUNBLADE, STATS + "增加攻速，持續3秒(90(0秒))。</mainText>")
ok(r and "(90秒)" in r and "(0秒)" not in r, f"(90(0秒)) → (90秒)：{r}")
ok(repair(GUNBLADE, STATS + "</mainText>") is None, "只有基礎屬性 ⇒ 不算有內文")
ok(repair(GUNBLADE, "<mainText><stats><attention>80</attention> 魔法攻擊</stats><br><br><br></mainText>") is None, "只有換行也不算")
ok(repair(TWOCALC, STATS + "造成0魔法傷害。</mainText>") is None, "兩條計算式不猜")
ok(repair({"mDataValues": []}, STATS + "造成0魔法傷害。</mainText>") is None, "沒有計算式不猜")
ok("10魔法傷害" in (repair(GUNBLADE, STATS + "造成10魔法傷害。</mainText>") or ""), "10 不可被當成 0")
ok(repair(GUNBLADE, STATS + "持續秒。</mainText>") is None, "DDragon 自己有洞 ⇒ 不用")
r = repair(COWL, STATS + "主動 (0秒) 回復生命。</mainText>")
ok(r and "(0秒)" not in r and "()" not in r, f"查不到冷卻就拿掉：{r}")

print(f"\n失敗 {fails}")
sys.exit(1 if fails else 0)
