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

print(f"合計 ✓ {ng[0]} ✗ {ng[1]}")
sys.exit(1 if ng[1] else 0)
