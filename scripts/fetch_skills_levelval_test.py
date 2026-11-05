# -*- coding: utf-8 -*-
"""依等級數值的求值：斷點語意、固定值＋依等級的分隔、係數依等級、捨入時機（#2617）。
純函式，不碰網路也不碰任何檔案。素材照 CDragon bin 真實結構抄。"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
import fetch_skills as K

ng = [0, 0]
def ok(name, fn, want):
    try:
        got = fn()
    except Exception as e:
        got = f"例外 {type(e).__name__}: {e}"
    good = got == want
    ng[0 if good else 1] += 1
    print(("✓ " if good else "✗ ") + name + ("" if good else f"：{got!r}，應為 {want!r}"))

BP = "ByCharLevelBreakpointsCalculationPart"
IP = "ByCharLevelInterpolationCalculationPart"
GC = "GameCalculation"
ctx = lambda dv=None: K.SpellCtx({"DataValues": dv or []}, 5)
def show(calc, dv=None, mult=1.0):
    return K.render_val(K.eval_calc(ctx(dv), calc), mult)
def num(n):
    return {"mNumber": n, "__type": "NumberCalculationPart"}

# ── 斷點語意（Wiki 對得上的三筆）
GAREN = {"mMultiplier": num(0.01), "mDisplayAsPercent": True, "__type": GC, "mFormulaParts": [
    {"mLevel1Value": 1.5, "mInitialBonusPerLevel": 0.2, "__type": BP, "mBreakpoints": [
        {"mLevel": 7, "mBonusPerLevelAtAndAfter": 0.8}, {"mLevel": 14, "mBonusPerLevelAtAndAfter": 0.4}]}]}
ok("蓋倫被動＝1.5－10.1%（Wiki 同；舊版 1.5－2.7，上一輪 1－3）", lambda: show(GAREN), "1.5－10.1%（依等級）")
GNAR_MS = {"__type": GC, "mFormulaParts": [{"mInitialBonusPerLevel": 1.0, "__type": BP,
    "mBreakpoints": [{"mLevel": 16, "mBonusPerLevelAtAndAfter": 2.0}]}]}
ok("小吶兒跑速＝0－20（Wiki 同；舊版 0－2）", lambda: show(GNAR_MS), "0－20（依等級）")
CAM = {"__type": GC, "mFormulaParts": [{"mStat": 12, "__type": "StatBySubPartCalculationPart", "mSubpart": {
    "mLevel1Value": 0.1, "__type": BP, "mBreakpoints": [
        {"mLevel": 7, "mAdditionalBonusAtThisLevel": 0.05}, {"mLevel": 13, "mAdditionalBonusAtThisLevel": 0.05},
        {"mLevel": 19, "mAdditionalBonusAtThisLevel": 0.05}]}}]}
ok("卡蜜兒護盾 10－20%，19 級的斷點碰不到（Wiki 10/15/20）", lambda: show(CAM), "+10－20%（依等級） 最大生命")

ok("速率是取代不是累加", lambda: K.breakpoints_end({"mLevel1Value": 0, "mInitialBonusPerLevel": 1, "mBreakpoints": [{"mLevel": 3, "mBonusPerLevelAtAndAfter": 10}]}), 1 + 16 * 10)
ok("只有一次加的斷點，速率歸零", lambda: K.breakpoints_end({"mLevel1Value": 0, "mInitialBonusPerLevel": 1, "mBreakpoints": [{"mLevel": 3, "mAdditionalBonusAtThisLevel": 10}]}), 1 + 10)
ok("卡蜜兒 Q 轉真傷 40－100%（Meraki 同；空斷點讓速率歸零，不是 108）", lambda: show({"mDisplayAsPercent": True, "__type": GC, "mFormulaParts": [{"mLevel1Value": 0.4, "mInitialBonusPerLevel": 0.04, "__type": BP, "mBreakpoints": [{"mLevel": 17}]}]}), "40－100%（依等級）")
ok("賽娜被動 1－10（Meraki 同）", lambda: K.breakpoints_end({"mLevel1Value": 1, "mInitialBonusPerLevel": 1, "mBreakpoints": [{"mLevel": 11}]}), 10)
ok("睿娜妲被動 1－2%（Meraki 同）", lambda: show({"mDisplayAsPercent": True, "__type": GC, "mFormulaParts": [{"mLevel1Value": 0.01, "mInitialBonusPerLevel": 0.0012, "__type": BP, "mBreakpoints": [{"mLevel": 6, "mBonusPerLevelAtAndAfter": 0.0013}, {"mLevel": 9, "mAdditionalBonusAtThisLevel": 0.0013}]}]}), "1－2%（依等級）")
ok("每個斷點都算（不只第一個）", lambda: K.breakpoints_end({"mLevel1Value": 1, "mBreakpoints": [{"mLevel": 5, "mAdditionalBonusAtThisLevel": 2}, {"mLevel": 18, "mAdditionalBonusAtThisLevel": 3}]}), 6)
ok("雜湊鍵的一次加（舊 bin）", lambda: K.breakpoints_end({"mLevel1Value": 1, "mBreakpoints": [{"mLevel": 5, "{d5fd07ed}": 2}]}), 3)
ok("沒有成長就是固定值，不印範圍", lambda: show({"__type": GC, "mFormulaParts": [{"mLevel1Value": 0.6, "__type": BP, "mBreakpoints": [{"mLevel": 6}, {"mLevel": 11}]}]}), "0.6")

# ── 逐級查表
TBL = [0.0] + [68.18 + (240.02 - 68.18) * i / 17 for i in range(18)] + [257.0, 274.0]
ok("卡特蓮娜匕首查表 68－240（Wiki 同）", lambda: show({"__type": GC, "mFormulaParts": [{"values": TBL, "__type": "ByCharLevelFormulaCalculationPart"}]}), "68－240（依等級）")
ok("查表的 18 級不是最後一格", lambda: K.eval_part(ctx(), {"values": TBL, "__type": "ByCharLevelFormulaCalculationPart"}).rng, "68－240（依等級）")
ok("查表小數值保留 2 位", lambda: K.eval_part(ctx(), {"values": [0, 0.123] + [0.5] * 17, "__type": "ByCharLevelFormulaCalculationPart"}).rng, "0.12－0.5（依等級）")
ok("查表頭尾相同是固定值", lambda: K.eval_part(ctx(), {"values": [0] + [5] * 18, "__type": "ByCharLevelFormulaCalculationPart"}).flat, [5] * 5)
def _short():
    try:
        K.eval_part(ctx(), {"values": [0, 1, 2], "__type": "ByCharLevelFormulaCalculationPart"})
    except K.Miss:
        return "Miss"
    return "沒 Miss"
ok("查表長度不夠：Miss", _short, "Miss")

# ── 兩端相同
ok("內插兩端相同印單一值（貝爾薇斯 20%）", lambda: show({"mDisplayAsPercent": True, "__type": GC, "mFormulaParts": [{"mStartValue": 0.2, "mEndValue": 0.2, "__type": IP}]}), "20%")
ok("內插兩端不同照舊", lambda: show({"__type": GC, "mFormulaParts": [{"mStartValue": 2, "mEndValue": 9, "__type": IP}]}), "2－9（依等級）")

# ── 固定值＋依等級不可黏在一起
DV = [{"name": "Base", "values": [0, 50, 80, 110, 140, 170, 200, 230]}]
ZOE = {"__type": GC, "mFormulaParts": [{"mDataValue": "Base", "__type": "NamedDataValueCalculationPart"},
    {"mStartValue": 2, "mEndValue": 9, "__type": IP}, {"mCoefficient": 0.6, "__type": "StatByCoefficientCalculationPart"}]}
ok("柔依 Q：固定值 + 依等級（舊版 1702－9）", lambda: show(ZOE, DV), "50/80/110/140/170 + 2－9（依等級）（+60% AP）")
ok("百分比也一樣", lambda: show({"mDisplayAsPercent": True, "__type": GC, "mFormulaParts": [{"mDataValue": "B", "__type": "NamedDataValueCalculationPart"}, {"mStartValue": 0.02, "mEndValue": 0.04, "__type": IP}]},
                                [{"name": "B", "values": [0, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09]}]), "3/4/5/6/7% + 2－4%（依等級）")

# ── 捨入只在顯示
ok("0.015 ×100 不失真", lambda: show({"mDisplayAsPercent": True, "__type": GC, "mFormulaParts": [{"mStartValue": 0.015, "mEndValue": 0.027, "__type": IP}]}), "1.5－2.7%（依等級）")
ok("先 ×0.01 再 ×100 不失真", lambda: K.show_rng(K.scale_rng(K.scale_rng("1.5－2.7（依等級）", 0.01), 100)), "1.5－2.7（依等級）")
ok("scale_rng 不捨入", lambda: K.scale_rng("1.5－2.7（依等級）", 0.01), "0.015－0.027（依等級）")
ok("show_rng 才捨到 2 位", lambda: K.show_rng("0.123456－1（依等級）"), "0.12－1（依等級）")

# ── 係數依等級
KAT = {"__type": GC, "mFormulaParts": [{"mStartValue": 68, "mEndValue": 240, "__type": IP},
    {"mCoefficient": 0.6, "mStatFormula": 2, "mStat": 2, "__type": "StatByCoefficientCalculationPart"},
    {"__type": "StatBySubPartCalculationPart", "mSubpart": {"mLevel1Value": 0.7, "__type": BP, "mBreakpoints": [
        {"mLevel": 6, "mAdditionalBonusAtThisLevel": 0.1}, {"mLevel": 11, "mAdditionalBonusAtThisLevel": 0.1}, {"mLevel": 16, "mAdditionalBonusAtThisLevel": 0.1}]}}]}
ok("卡特蓮娜匕首有數字（Wiki 68－240、+60% 額外AD、AP 70→100%）", lambda: show(KAT), "68－240（依等級）（+70－100%（依等級） AP）（+60% 額外AD）")
ok("Sum 裡的依等級不再被丟掉", lambda: show({"__type": GC, "mFormulaParts": [{"__type": "SumOfSubPartsCalculationPart", "mSubparts": [{"mStartValue": 1, "mEndValue": 2, "__type": IP}, {"mStartValue": 10, "mEndValue": 20, "__type": IP}]}]}), "11－22（依等級）")
ok("頂層多段依等級要相加，不是後蓋前", lambda: show({"__type": GC, "mFormulaParts": [{"mStartValue": 1, "mEndValue": 2, "__type": IP}, {"mStartValue": 10, "mEndValue": 20, "__type": IP}]}), "11－22（依等級）")
ok("Product 裡的依等級乘得到（提伯斯型）", lambda: show({"__type": GC, "mFormulaParts": [{"__type": "ProductOfSubPartsCalculationPart", "mPart1": {"mStartValue": 10, "mEndValue": 20, "__type": IP}, "mPart2": num(2)}]}), "20－40（依等級）")
ok("Product 乘數在前面也一樣", lambda: show({"__type": GC, "mFormulaParts": [{"__type": "ProductOfSubPartsCalculationPart", "mPart1": num(2), "mPart2": {"mStartValue": 10, "mEndValue": 20, "__type": IP}}]}), "20－40（依等級）")
ok("1－(依等級) 型負數能算（凱特琳對小兵）", lambda: show({"__type": GC, "mFormulaParts": [{"mStat": 2, "__type": "StatBySubPartCalculationPart", "mSubpart": {"__type": "SumOfSubPartsCalculationPart", "mSubparts": [num(1), {"__type": "ProductOfSubPartsCalculationPart", "mPart1": num(-1), "mPart2": {"mStartValue": 0.5, "mEndValue": 0.2, "__type": IP}}]}}]}), "+50－80%（依等級） AD")
def _srng_mod():
    c = K.SpellCtx({"mSpellCalculations": {"base": {"__type": GC, "mFormulaParts": [{"mStat": 2, "__type": "StatBySubPartCalculationPart", "mSubpart": {"mStartValue": 0.5, "mEndValue": 1, "__type": IP}}]}}}, 5)
    return K.render_val(K.eval_calc(c, {"mMultiplier": num(0.5), "mModifiedGameCalculation": "base", "__type": "GameCalculationModified"}))
ok("Modified 也乘到依等級係數", _srng_mod, "+25－50%（依等級） AD")
ok("GameCalculation 的 mMultiplier 也乘到依等級係數", lambda: show({"mMultiplier": num(0.5), "__type": GC, "mFormulaParts": [{"mStat": 2, "__type": "StatBySubPartCalculationPart", "mSubpart": {"mStartValue": 0.5, "mEndValue": 1, "__type": IP}}]}), "+25－50%（依等級） AD")
ok("mDisplayAsPercent 的依等級係數：百分比不重乘", lambda: show({"mDisplayAsPercent": True, "__type": GC, "mFormulaParts": [{"mStat": 2, "__type": "StatBySubPartCalculationPart", "mSubpart": {"mStartValue": 0.5, "mEndValue": 1, "__type": IP}}]}), "+50－100%（依等級） AD")
def _nonuniform():
    try:
        K.eval_calc(ctx(DV), {"__type": GC, "mFormulaParts": [{"mStat": 2, "__type": "StatBySubPartCalculationPart", "mSubpart": {"__type": "SumOfSubPartsCalculationPart", "mSubparts": [{"mDataValue": "Base", "__type": "NamedDataValueCalculationPart"}, {"mStartValue": 1, "mEndValue": 2, "__type": IP}]}}]})
    except K.Miss:
        return "Miss"
    return "沒 Miss"
ok("每級不同的固定值＋依等級的係數：算不出來就 Miss，不亂印", _nonuniform, "Miss")
ok("Product：依等級 × 每級不同的倍率＝1 級值 × 每級", lambda: show({"__type": GC, "mFormulaParts": [{"__type": "ProductOfSubPartsCalculationPart", "mPart1": {"mStartValue": 1, "mEndValue": 2, "__type": IP}, "mPart2": {"mDataValue": "Base", "__type": "NamedDataValueCalculationPart"}}]}, DV), "50/80/110/140/170")
KE = [{"name": "Cd", "values": [0, 12, 11, 10, 9, 8, 7, 6]}]
KCALC = {"mMultiplier": {"mDataValue": "Cd", "__type": "NamedDataValueCalculationPart"}, "__type": GC, "mFormulaParts": [{"mLevel1Value": 0.78, "__type": BP, "mBreakpoints": [{"mLevel": 6, "mAdditionalBonusAtThisLevel": 0.18}]}]}
ok("卡特蓮娜 E：mMultiplier 每級不同（上一版印 0.78－0.96 秒）", lambda: show(KCALC, KE), "9.36/8.58/7.8/7.02/6.24")
def _mod_nonuniform():
    c = K.SpellCtx({"DataValues": KE, "mSpellCalculations": {"base": {"__type": GC, "mFormulaParts": [{"mLevel1Value": 0.78, "__type": BP, "mBreakpoints": [{"mLevel": 6, "mAdditionalBonusAtThisLevel": 0.18}]}]}}}, 5)
    return K.render_val(K.eval_calc(c, {"mMultiplier": {"mDataValue": "Cd", "__type": "NamedDataValueCalculationPart"}, "mModifiedGameCalculation": "base", "__type": "GameCalculationModified"}))
ok("Modified 倍率每級不同也一樣", _mod_nonuniform, "9.36/8.58/7.8/7.02/6.24")
ok("固定值＋依等級 × 每級不同：固定值也算進去", lambda: K._mul_rng([1, 2], "10－20（依等級）", [2, 3]), ([22, 36], None))
ok("固定值＋依等級 × 同倍率", lambda: K._mul_rng([1, 2], "10－20（依等級）", [2, 2]), ([2, 4], "20－40（依等級）"))
ok("沒有依等級時照舊逐級乘", lambda: K._mul_rng([1, 2], None, [2, 3]), ([2, 6], None))
def _srng_nonuniform():
    try:
        K.eval_calc(ctx(DV), {"__type": GC, "mFormulaParts": [{"__type": "ProductOfSubPartsCalculationPart", "mPart1": {"mStat": 2, "__type": "StatBySubPartCalculationPart", "mSubpart": {"mStartValue": 1, "mEndValue": 2, "__type": IP}}, "mPart2": {"mDataValue": "Base", "__type": "NamedDataValueCalculationPart"}}]})
    except K.Miss:
        return "Miss"
    return "沒 Miss"
ok("依等級的係數 × 每級不同：Miss，不亂印", _srng_nonuniform, "Miss")
ok("finish 清掉重複的生命", lambda: K.finish("回復+10% 最大生命生命。"), "回復+10% 最大生命。")
ok("finish 不動一般的生命", lambda: K.finish("回復 10 生命，生命值"), "回復 10 生命，生命值")

ok("負值 × 負倍率", lambda: K.scale_rng("-0.5－-0.2（依等級）", -1), "0.5－0.2（依等級）")
ok("Product 另一邊帶依等級時不可當純數", lambda: show({"__type": GC, "mFormulaParts": [{"__type": "ProductOfSubPartsCalculationPart", "mPart1": num(2), "mPart2": {"__type": "SumOfSubPartsCalculationPart", "mSubparts": [num(1), {"mStartValue": 10, "mEndValue": 20, "__type": IP}]}}]}), "2 + 20－40（依等級）")
ok("無固定值時依等級係數不加括號", lambda: show({"__type": GC, "mFormulaParts": [{"mStat": 2, "__type": "StatBySubPartCalculationPart", "mSubpart": {"mStartValue": 0.5, "mEndValue": 1, "__type": IP}}]}), "+50－100%（依等級） AD")

# ── 堆疊層數係數（#2618，素材照 bin）
BC = "BuffCounterByCoefficientCalculationPart"
NAMED = lambda n: {"mDataValue": n, "__type": "NamedDataValueCalculationPart"}
STATC = lambda st, c: {"mStat": st, "mCoefficient": c, "__type": "StatByCoefficientCalculationPart"}
DV = lambda n, *v: {"name": n, "values": [0, *v, 0]}
NASUS = {"__type": GC, "mFormulaParts": [NAMED("BonusDamage"), STATC(2, 1.0), {"mBuffName": "x", "mCoefficient": 1.0, "__type": BC}]}
ok("納瑟斯 Q：固定＋AD＋每層", lambda: show(NASUS, [DV("BonusDamage", 30, 50, 70, 90, 110)]), "30/50/70/90/110（+100% AD）（每層 +1）")
THRESH = {"__type": GC, "mFormulaParts": [{"mBuffName": "x", "mCoefficient": 1.7, "__type": BC}]}
ok("瑟雷西 E：只有層數、係數不是 1", lambda: show(THRESH), "每層 +1.7")
ok("達瑞文即時計數：只有層數、係數 1 → 不印", lambda: show({"__type": GC, "mFormulaParts": [{"mCoefficient": 1.0, "__type": BC}]}), None)
KIND = {"__type": GC, "mDisplayAsPercent": True, "mFormulaParts": [NAMED("BaseBonusAS"), {"mCoefficient": 0.05, "__type": BC}]}
ok("鏡爪 Q：百分比固定值＋每層也是百分比", lambda: show(KIND, [DV("BaseBonusAS", .35, .4, .45, .5, .55)]), "35/40/45/50/55%（每層 +5%）")
ok("百分比只有層數、係數 1 不是即時計數（×100 後才是 100）", lambda: show({"__type": GC, "mDisplayAsPercent": True, "mFormulaParts": [{"mCoefficient": 1.0, "__type": BC}]}), "每層 +100%")
ok("模板 *100 也乘到層數", lambda: show({"__type": GC, "mFormulaParts": [{"mCoefficient": 0.05, "__type": BC}]}, mult=100), "每層 +5")
ok("小係數不被 2 位捨入吃掉", lambda: show({"__type": GC, "mFormulaParts": [NAMED("A"), {"mCoefficient": 0.008, "__type": BC}]}, [DV("A", 1, 1, 1, 1, 1)]), "1（每層 +0.008）")
ok("mMultiplier 乘到層數", lambda: show({"__type": GC, "mMultiplier": num(2), "mFormulaParts": [{"mCoefficient": 1.5, "__type": BC}]}), "每層 +3")
ok("Sum 裡的層數不可丟", lambda: show({"__type": GC, "mFormulaParts": [{"__type": "SumOfSubPartsCalculationPart", "mSubparts": [num(5), {"mCoefficient": 1.5, "__type": BC}]}]}), "5（每層 +1.5）")
ok("Product 乘到層數", lambda: show({"__type": GC, "mFormulaParts": [{"__type": "ProductOfSubPartsCalculationPart", "mPart1": {"mCoefficient": 1.5, "__type": BC}, "mPart2": num(2)}]}), "每層 +3")
def _modified_stack():
    c = K.SpellCtx({"mSpellCalculations": {"Base": {"__type": GC, "mFormulaParts": [{"mCoefficient": 1.5, "__type": BC}]},
                                          "M": {"__type": "GameCalculationModified", "mModifiedGameCalculation": "Base", "mMultiplier": num(2)}}}, 5)
    return K.render_val(K.eval_calc(c, c.calc["m"]))
ok("GameCalculationModified 乘到層數", _modified_stack, "每層 +3")
def _miss(calc):
    try:
        K.eval_calc(ctx(), calc)
    except K.Miss:
        return "Miss"
    return "沒 Miss"
ok("層數當倍率（貝爾薇斯）：Miss，不亂印", lambda: _miss({"__type": GC, "mMultiplier": num(1), "mFormulaParts": [{"mStat": 2, "__type": "StatBySubPartCalculationPart", "mSubpart": {"mCoefficient": 1.0, "__type": BC}}]}), "Miss")
def _mod_stackmult():
    c = K.SpellCtx({"mSpellCalculations": {"Base": {"__type": GC, "mFormulaParts": [num(3)]},
                                          "M": {"__type": "GameCalculationModified", "mModifiedGameCalculation": "Base", "mMultiplier": {"mCoefficient": 1.0, "__type": BC}}}}, 5)
    try:
        K.eval_calc(c, c.calc["m"])
    except K.Miss:
        return "Miss"
    return "沒 Miss"
ok("Modified 的倍率是層數：Miss", _mod_stackmult, "Miss")
ok("Product 另一邊是層數時不可當純數", lambda: _miss({"__type": GC, "mFormulaParts": [{"__type": "ProductOfSubPartsCalculationPart", "mPart1": {"mStat": 2, "mCoefficient": 1.0, "__type": "StatByCoefficientCalculationPart"}, "mPart2": {"mCoefficient": 1.0, "__type": BC}}]}), "Miss")

SUMST = {"__type": "SumOfSubPartsCalculationPart", "mSubparts": [num(2), {"mCoefficient": 1.0, "__type": BC}]}
ok("屬性 × (固定＋層數)：Miss，層數不可靜靜丟掉", lambda: _miss({"__type": GC, "mFormulaParts": [{"mStat": 2, "__type": "StatBySubPartCalculationPart", "mSubpart": SUMST}]}), "Miss")
ok("Product 另一邊是固定＋層數：Miss", lambda: _miss({"__type": GC, "mFormulaParts": [{"__type": "ProductOfSubPartsCalculationPart", "mPart1": STATC(2, 1.0), "mPart2": SUMST}]}), "Miss")
def _mod_sumst():
    c = K.SpellCtx({"mSpellCalculations": {"Base": {"__type": GC, "mFormulaParts": [num(3)]},
                                          "M": {"__type": "GameCalculationModified", "mModifiedGameCalculation": "Base", "mMultiplier": SUMST}}}, 5)
    try:
        K.eval_calc(c, c.calc["m"])
    except K.Miss:
        return "Miss"
    return "沒 Miss"
ok("Modified 的倍率是固定＋層數：Miss", _mod_sumst, "Miss")
ok("百分比只有層數、×100 後剛好 1 不是即時計數", lambda: show({"__type": GC, "mDisplayAsPercent": True, "mFormulaParts": [{"mCoefficient": 0.01, "__type": BC}]}), "每層 +1%")

# ── 上下限與技能的 EffectValue（凱莎 E 照 bin）
CL = "ClampSubPartsCalculationPart"
EFF = [{"value": [.55, .55, .6, .65, .7, .75, .75]}, {"value": [4.0, 4, 4, 4, 4, 4, 4]}]
ectx = lambda: K.SpellCtx({"mEffectAmount": EFF}, 5)
KAISA = {"__type": GC, "mDisplayAsPercent": True, "mMultiplier": {"mEffectIndex": 1, "__type": "EffectValueCalculationPart"},
         "mFormulaParts": [{"__type": CL, "mCeiling": 2.0, "mFloor": 1.0, "mSubparts": [STATC(4, 1.0), num(1)]}]}
ok("凱莎 E 跑速 55－75%（Meraki 同），佔位不算", lambda: K.render_val(K.eval_calc(ectx(), KAISA)), "55/60/65/70/75%")
ok("EffectValue 第 2 組", lambda: K.eval_part(ectx(), {"mEffectIndex": 2, "__type": "EffectValueCalculationPart"}).flat, [4, 4, 4, 4, 4])
def _eff(i, c=None):
    try:
        K.eval_part(c or ectx(), {"mEffectIndex": i, "__type": "EffectValueCalculationPart"})
    except K.Miss:
        return "Miss"
    return "沒 Miss"
ok("EffectValue 索引 0：Miss", lambda: _eff(0), "Miss")
ok("EffectValue 超出範圍：Miss", lambda: _eff(3), "Miss")
ok("EffectValue 空組：Miss", lambda: _eff(1, K.SpellCtx({"mEffectAmount": [{"value": []}]}, 5)), "Miss")
ok("EffectValue 大招只取 3 級", lambda: K.eval_part(K.SpellCtx({"mEffectAmount": EFF}, 3), {"mEffectIndex": 1, "__type": "EffectValueCalculationPart"}).flat, [.55, .6, .65])
clamp = lambda **kw: K.eval_part(ctx(), {"__type": CL, **kw}).flat
ok("上限夾住", lambda: clamp(mFloor=1.0, mCeiling=2.0, mSubparts=[num(5)]), [2.0] * 5)
ok("下限夾住", lambda: clamp(mFloor=1.0, mCeiling=2.0, mSubparts=[num(.5)]), [1.0] * 5)
ok("範圍內不動", lambda: clamp(mFloor=1.0, mCeiling=2.0, mSubparts=[num(1.5)]), [1.5] * 5)
ok("mCeiling null＝沒有上限", lambda: clamp(mFloor=1.0, mCeiling=None, mSubparts=[num(9)]), [9] * 5)
ok("mFloor null＝沒有下限", lambda: clamp(mFloor=None, mCeiling=2.0, mSubparts=[num(-9)]), [-9] * 5)
ok("沒寫 mFloor＝0（卡莉絲塔）", lambda: clamp(mCeiling=None, mSubparts=[num(-3), STATC(4, 1.0)]), [0] * 5)
ok("subparts 相加再夾", lambda: clamp(mFloor=0, mCeiling=9.0, mSubparts=[num(1), num(2)]), [3] * 5)
ok("只有屬性項＝0 屬性", lambda: clamp(mFloor=1.0, mCeiling=2.0, mSubparts=[STATC(4, 1.0)]), [1.0] * 5)
ok("subpart 帶依等級：Miss", lambda: _miss({"__type": GC, "mFormulaParts": [{"__type": CL, "mFloor": 0, "mSubparts": [{"mStartValue": 1, "mEndValue": 2, "__type": IP}]}]}), "Miss")
ok("subpart 帶層數：Miss", lambda: _miss({"__type": GC, "mFormulaParts": [{"__type": CL, "mFloor": 0, "mSubparts": [{"mCoefficient": 1.0, "__type": BC}]}]}), "Miss")
ok("subpart 未知型別（銳兒 PercentageOfBuffNameElapsed）：Miss", lambda: _miss({"__type": GC, "mFormulaParts": [{"__type": CL, "mFloor": .2, "mCeiling": 1.0, "mSubparts": [{"__type": "PercentageOfBuffNameElapsed"}]}]}), "Miss")

# ── #2619：屬性代碼、充能欄位、0 層＋每層、DataValue 內插、計算式引用、Conditional、Modified 兩種倍率 ──
_dv = lambda n, *v: {"name": n, "values": [0, *v, 0]}
_nd = lambda n: {"mDataValue": n, "__type": "NamedDataValueCalculationPart"}
_sc = lambda st, c, **kw: {"mStat": st, "mCoefficient": c, "__type": "StatByCoefficientCalculationPart", **kw}
_gc = lambda *p, **kw: {"__type": GC, "mFormulaParts": list(p), **kw}
_cx = lambda dv=(), calc=None, **kw: K.SpellCtx({"DataValues": list(dv), "mSpellCalculations": calc or {}, **kw}, 5)
def _r(cx, calc, mult=1.0):
    try:
        return K.render_val(K.eval_calc(cx, calc), mult)
    except K.Miss:
        return "Miss"
ok("mStat 6 是魔抗（加里歐 R）", lambda: _r(_cx(), _gc(_sc(6, 1.0, mStatFormula=2))), "+100% 額外魔抗")
ok("mStat 7 是移動速度（珍娜 W）", lambda: _r(_cx(), _gc(_sc(7, .3, mStatFormula=2))), "+30% 額外移動速度")
ok("mStat 4（攻速）刻意不標，略過", lambda: _r(_cx([_dv("B", 1, 2, 3, 4, 5)]), _gc(_nd("B"), _sc(4, 3.0))), "1/2/3/4/5")
_am = {"mMaxAmmo": [2, 3, 3, 4, 4, 5, 5], "mAmmoRechargeTime": [38., 26., 22., 18., 14., 10., 10.]}
ok("充能時間（凱特琳 W，Meraki 同）", lambda: K.resolve_token(_cx(**_am), {}, "ammorechargetime", 1.0), "26/22/18/14/10")
ok("最大充能（values[0] 是佔位）", lambda: K.resolve_token(_cx(**_am), {}, "maxammo", 1.0), "3/3/4/4/5")
ok("DataValues 同名優先於技能本體", lambda: K.resolve_token(_cx([_dv("maxammo", 9, 9, 9, 9, 9)], **_am), {}, "maxammo", 1.0), "9")
ok("Modes 開頭且沒定義＝0（奈德麗 W）", lambda: K.eval_part(_cx(), _nd("ModesBonusMaxTraps")).flat, [0] * 5)
ok("Modes 開頭但有定義就用值", lambda: K.eval_part(_cx([_dv("ModesX", 1, 2, 3, 4, 5)]), _nd("ModesX")).flat, [1, 2, 3, 4, 5])
ok("一般名字沒定義仍 Miss", lambda: _r(_cx(), _gc(_nd("BonusMaxTraps"))), "Miss")
_sub = lambda st, inner: {"mStat": st, "mSubpart": inner, "__type": "StatBySubPartCalculationPart"}
_prod = lambda a, b: {"__type": "ProductOfSubPartsCalculationPart", "mPart1": a, "mPart2": b}
_sum = lambda *p: {"__type": "SumOfSubPartsCalculationPart", "mSubparts": list(p)}
_B = [_dv("B", 40, 60, 80, 100, 120), _dv("C", .5, .5, .5, .5, .5)]
ok("二階項略過（逆命藍牌的暴擊加成）", lambda: _r(_cx(_B), _gc(_nd("B"), _sc(2, 1.0), _sub(8, _prod(_nd("C"), _sum(_nd("B"), _sc(2, 1.0)))))), "40/60/80/100/120（+100% AD）")
ok("二階項：純數子項仍算成係數", lambda: _r(_cx(_B), _gc(_nd("B"), _sub(2, _nd("C")))), "40/60/80/100/120（+50% AD）")
ok("二階項：子項不認得仍 Miss", lambda: _r(_cx(_B), _gc(_sub(2, {"__type": "NoSuchPart"}))), "Miss")
_cnt = lambda n: {"mDataValue": n, "__type": "BuffCounterByNamedDataValueCalculationPart"}
_S = [_dv("S", .2, .2, .2, .2, .2), _dv("B", 5, 5, 5, 5, 5)]
ok("0 層＋每層：只有層數", lambda: _r(_cx(_S), _gc(_cnt("S"))), "每層 +0.2")
ok("基礎值＋每層（奧瑞利安 E 處決門檻）", lambda: _r(_cx(_S), _gc(_nd("B"), _cnt("S"))), "5（每層 +0.2）")
ok("每層的 DataValue 沒定義：只留 0 層", lambda: _r(_cx(_S), _gc(_nd("B"), _cnt("NoSuch"))), "5")
ok("每層進百分比", lambda: _r(_cx(_S), _gc(_cnt("S"), mDisplayAsPercent=True)), "每層 +20%")
_itp = lambda a, b: {"StartDataValue": a, "EndDataValue": b, "__type": "{ee18a47b}"}
_I = [_dv("L1", 100, 100, 100, 100, 100), _dv("L18", 500, 500, 500, 500, 500), _dv("V", 1, 2, 3, 4, 5)]
ok("DataValue 內插（洛克 W 治療上限）", lambda: _r(_cx(_I), _gc(_itp("L1", "L18"))), "100－500（依等級）")
ok("DataValue 內插頭尾相同印固定值", lambda: _r(_cx(_I), _gc(_itp("L1", "L1"))), "100")
ok("DataValue 內插每級不同：Miss", lambda: _r(_cx(_I), _gc(_itp("V", "L18"))), "Miss")
ok("DataValue 內插＋係數", lambda: _r(_cx(_I), _gc(_itp("L1", "L18"), _sc(0, .6))), "100－500（依等級）（+60% AP）")
_mod = lambda ref, m: {"__type": "GameCalculationModified", "mModifiedGameCalculation": ref, "mMultiplier": m}
_key = lambda k: {"mSpellCalculationKey": k, "__type": "{f3cbe7b2}"}
_Y = {"Heal": _gc(_nd("B"), _sc(0, .12)), "Perc": _gc({"mStartValue": 1.3, "mEndValue": 1.6, "__type": "ByCharLevelInterpolationCalculationPart"})}
_YD = [_dv("B", 30, 50, 70, 90, 110)]
ok("倍率依等級印在最後（悠咪 R，官方 30－60%）", lambda: _r(_cx(_YD, _Y), _mod("Heal", _key("Perc"))), "30/50/70/90/110（+12% AP） × 1.3－1.6（依等級）")
ok("計算式引用不存在：Miss", lambda: _r(_cx(_YD, _Y), _mod("Heal", _key("NoSuch"))), "Miss")
ok("倍率依等級但基礎也依等級：Miss", lambda: _r(_cx(_YD, {"H": _gc({"mStartValue": 1, "mEndValue": 2, "__type": "ByCharLevelInterpolationCalculationPart"}), **_Y}), _mod("H", _key("Perc"))), "Miss")
_L = [_dv("N", 22, 22, 22, 22, 22), _dv("Base", 15, 30, 45, 60, 75), _dv("AD", .25, .25, .25, .25, .25), _dv("AP", .15, .15, .15, .15, .15)]
_ST = lambda st, n: {"mStat": st, "mDataValue": n, "__type": "StatByNamedDataValueCalculationPart"}
_LC = {"Shots": _gc(_sum(_nd("N"), _prod(_sc(8, 1.0), _nd("Neg"))))}
_L2 = _L + [_dv("Neg", -22, -22, -22, -22, -22)]
ok("基礎純數×倍率帶係數（路西恩 R 總傷害）", lambda: _r(_cx(_L2, _LC), _mod("Shots", _sum(_nd("Base"), _ST(2, "AD"), _ST(0, "AP")))), "330/660/990/1320/1650（+550% AD）（+330% AP）")
_V = {"T": _gc(_nd("Base"), _sc(2, 1.1))}
ok("基礎帶係數×倍率帶係數＝二階項略過（弗力貝爾 W2）", lambda: _r(_cx([_dv("Base", 5, 30, 55, 80, 105), _dv("M", 1.5, 1.5, 1.5, 1.5, 1.5), _dv("K", .0025, .0025, .0025, .0025, .0025)], _V), _mod("T", _sum(_nd("M"), _ST(2, "K")))), "7.5/45/82.5/120/157.5（+165% AD）")
_CD = {"Def": _gc(_nd("B")), "Evo": _gc(_nd("E"))}
_cond = lambda d: {"__type": "GameCalculationConditional", "mDefaultGameCalculation": d, "mConditionalGameCalculation": "Evo"}
ok("Conditional 走平常狀態（凱莎 Q 上限）", lambda: _r(_cx([_dv("B", 1, 2, 3, 4, 5), _dv("E", 9, 9, 9, 9, 9)], _CD), _cond("Def")), "1/2/3/4/5")
ok("Conditional 算式不存在：Miss", lambda: _r(_cx([], _CD), _cond("NoSuch")), "Miss")
ok("同標籤係數合併", lambda: _r(_cx(_YD), _gc(_nd("B"), _sc(0, .5), _sc(2, .1), _sc(0, .3))), "30/50/70/90/110（+80% AP）（+10% AD）")
ok("不同屬性前綴不合併", lambda: _r(_cx(_YD), _gc(_sc(2, .5), _sc(2, .3, mStatFormula=2))), "+50% AD（+30% 額外AD）")
_MM = lambda *p, m: {"__type": GC, "mFormulaParts": list(p), "mMultiplier": m}
_num2 = {"mNumber": 2.0, "__type": "NumberCalculationPart"}
ok("mMultiplier 帶負係數殘留仍算倍率（煙龍被動）", lambda: _r(_cx([_dv("S", .25, .25, .25, .25, .25), _dv("Neg", -2, -2, -2, -2, -2)]), _MM(_cnt("S"), m=_sum(_num2, _prod(_sc(8, 1.0), _nd("Neg"))))), "每層 +0.5")
ok("mMultiplier 帶正係數不套（維持舊行為）", lambda: _r(_cx(_YD), _MM(_nd("B"), m=_sum(_num2, _sc(0, 1.0)))), "30/50/70/90/110")
ok("值自帶護甲標籤又接單位", lambda: K.finish("獲得+16% 護甲物防和+16% 魔抗魔防。"), "獲得+16% 護甲和+16% 魔抗。")
ok("模板的加號接值自帶的加號只留一個", lambda: K.finish("造成 55（+50% AP） + +30% 額外移動速度，(++20% 暴擊率)。"), "造成 55（+50% AP） +30% 額外移動速度，(+20% 暴擊率)。")
ok("單一加號不動（對照）", lambda: K.finish("造成 55 +30% AP 和 10 + 20。"), "造成 55 +30% AP 和 10 + 20。")
ok("值自帶標籤（道具全名）", lambda: K.finish("+5% 額外護甲物理防禦 與 +5% 額外魔抗魔法防禦"), "+5% 額外護甲 與 +5% 額外魔抗")
ok("括號外的單位不動", lambda: K.finish("20（+12% 額外護甲）物防及 20（+12% 額外魔抗）魔防"), "20（+12% 額外護甲）物防及 20（+12% 額外魔抗）魔防")
ok("空值括號註記刪掉", lambda: K.finish("回復 5 生命(上限：)。"), "回復 5 生命。")
ok("有值的括號註記留著", lambda: K.finish("回復 5 生命(上限：9)。"), "回復 5 生命(上限：9)。")
ok("全形空值括號也刪", lambda: K.finish("回復 5 生命（上限：）。"), "回復 5 生命。")
_TST = {"spell_x_tooltip_1": "造成<b>@Dmg@</b>與@Cherry*100@%。{{Spell_Y_Name}}", "spell_x_tooltip_2": "競技場", "spell_y_name": "黑槍"}
ok("字串表模板取 _1（一般模式）", lambda: K.expand_tpl("{{Spell_X_Tooltip_{{ gamemodeinteger }}}}{{ spellmodifierdescriptionappend }}", _TST), "造成<b>{{ Dmg }}</b>與{{ Cherry*100 }}%。黑槍{{ spellmodifierdescriptionappend }}")
ok("模板寫法帶空白也認得", lambda: K.expand_tpl("{{ Spell_X_Tooltip_{{ gamemodeinteger }} }}", {"spell_x_tooltip_1": "甲"}), "甲")
ok("字串表沒這條：原樣", lambda: K.expand_tpl("{{Spell_Z_Tooltip_{{ gamemodeinteger }}}}", _TST), "{{Spell_Z_Tooltip_{{ gamemodeinteger }}}}")
ok("沒字串表：原樣", lambda: K.expand_tpl("{{ a }}", None), "{{ a }}")
ok("技能名查不到：留給 finish 清", lambda: K.expand_tpl("{{ Spell_Q_Name }}", _TST), "{{ Spell_Q_Name }}")
ok("技能名（被動模板）", lambda: K.expand_tpl("施展{{ Spell_Y_Name }}後", _TST), "施展黑槍後")

ok("層數沒定義時仍當 0 參與相乘，不是 Miss", lambda: _r(_cx(), _gc(_prod(_cnt("NoSuch"), _sc(2, 1.0)))), None)
ok("計算式引用不存在，整條 Miss（不可少算一項）", lambda: _r(_cx(_YD), _gc(_nd("B"), _key("NoSuch"))), "Miss")
def _tail_only():
    v = K.Val(); v.tail = "1－2（依等級）"
    return K.render_val(v)
ok("沒有本體時不印倍率", _tail_only, None)
ok("沒字串表碰到巢狀模板：原樣、不崩", lambda: K.expand_tpl("{{Spell_X_Tooltip_{{ gamemodeinteger }}}}", None), "{{Spell_X_Tooltip_{{ gamemodeinteger }}}}")

print(f"合計 ✓ {ng[0]} ✗ {ng[1]}")
sys.exit(1 if ng[1] else 0)
