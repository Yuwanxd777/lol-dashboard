# -*- coding: utf-8 -*-
"""fetch_items／fetch_skills 的 token 求值（2026-11-05 精進迴圈 #2615）。

素材是 16.22 真實 bin 條目的節錄，寫死在這裡：bin 每版會變，正本當素材下一版就紅。
只測純函式，不開任何路徑、不上網。舊版對照釘 fd6094b6，用子程序跑。
環境變數 TOKENS_SCRIPTS 可指到別的 scripts 目錄（突變測試用）。"""
import io, json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.environ.get("TOKENS_SCRIPTS", HERE)
sys.path.insert(0, SCRIPTS)

MANA  = {"mFormulaParts": [{"mCoefficient": 0.02, "__type": "AbilityResourceByCoefficientCalculationPart"}], "__type": "GameCalculation"}
BMANA = {"mFormulaParts": [{"mCoefficient": 0.15, "mStatFormula": 2, "__type": "AbilityResourceByCoefficientCalculationPart"}], "__type": "GameCalculation"}
ITEMS = {
    "split": {"mItemCalculations": {"MeleeItemCalcValue": {"mFormulaParts": [{"mNumber": 0.3, "__type": "NumberCalculationPart"}], "mDisplayAsPercent": True, "__type": "GameCalculation"}, "RangedItemCalcValue": {"mFormulaParts": [{"mNumber": 0.1, "__type": "NumberCalculationPart"}], "mDisplayAsPercent": True, "__type": "GameCalculation"}, "MeleeItemCalcValueB": {"mFormulaParts": [{"mNumber": 0.04, "__type": "NumberCalculationPart"}], "mDisplayAsPercent": True, "__type": "GameCalculation"}, "RangedItemCalcValueB": {"mFormulaParts": [{"mNumber": 0.02, "__type": "NumberCalculationPart"}], "mDisplayAsPercent": True, "__type": "GameCalculation"}}},
    "splitsame": {"mItemCalculations": {"MeleeItemCalcValue": {"mFormulaParts": [{"mNumber": 0.3, "__type": "NumberCalculationPart"}], "mDisplayAsPercent": True, "__type": "GameCalculation"}, "RangedItemCalcValue": {"mFormulaParts": [{"mNumber": 0.3, "__type": "NumberCalculationPart"}], "mDisplayAsPercent": True, "__type": "GameCalculation"}}},
    "hubris": {"mDataValues": [{"mName": "BaseADBonusMelee", "mValue": 15.0}, {"mName": "BaseADRangedMult", "mValue": 0.667}, {"mName": "SpellMaxAmp"}],
               "mItemCalculations": {"BaseADBonus": {"mFormulaParts": [{"mDataValue": "{6c8d1758}", "__type": "NamedDataValueCalculationPart"}],
                                                     "mRangedMultiplier": {"mDataValue": "{4270a530}", "__type": "NamedDataValueCalculationPart"}, "__type": "{e9a3c91d}"}}},
    "shiv": {"mDataValues": [{"mName": "MeleeAuraAttackSpeed", "mValue": 0.3}, {"mName": "RangedAttackSpeedMultiplier", "mValue": 0.667}],
             "mItemCalculations": {"AuraAttackSpeed": {"mFormulaParts": [{"mDataValue": "{eb8d750f}", "__type": "NamedDataValueCalculationPart"}], "mDisplayAsPercent": True,
                                                       "mRangedMultiplier": {"mDataValue": "{ca6deae2}", "__type": "NamedDataValueCalculationPart"}, "__type": "{e9a3c91d}"}}},
    "manamune": {"mDataValues": [{"mName": "MaxMana", "mValue": 360.0}], "mItemCalculations": {"BonusADFromMana": MANA, "Bonus": BMANA}},
    "ember": {"mEffectAmount": [60.0, 25.0, 5.0], "mDataValues": [{"mName": "X", "mValue": 1.0}],
              "mItemCalculations": {"TotalBurnDamage": {"mFormulaParts": [{"mEffectIndex": 1, "__type": "EffectValueCalculationPart"},
                                                                          {"mStat": 12, "mStatFormula": 2, "mCoefficient": 0.02, "__type": "StatByCoefficientCalculationPart"}], "__type": "GameCalculation"},
                                    "Bad": {"mFormulaParts": [{"mEffectIndex": 9, "__type": "EffectValueCalculationPart"}], "__type": "GameCalculation"}}},
    "seer": {"mDataValues": [{"mName": "Y", "mValue": 1.0}],
             "mItemCalculations": {"ManaCalc": {"mMultiplier": {"mNumber": 0.01, "__type": "NumberCalculationPart"},
                                                "mFormulaParts": [{"mNumber": 15.0, "__type": "NumberCalculationPart"},
                                                                  {"mCoefficient": 0.005, "mStatFormula": 2, "__type": "AbilityResourceByCoefficientCalculationPart"}],
                                                "mDisplayAsPercent": True, "__type": "GameCalculation"}}},
    "nullv": {"mDataValues": [{"mName": "Empty"}],
              "mItemCalculations": {"UsesEmpty": {"mFormulaParts": [{"mDataValue": "Empty", "__type": "NamedDataValueCalculationPart"}], "__type": "GameCalculation"}}},
    "hatchet": {"mDataValues": [{"mName": "CurrentHealthBaseDamage", "mValue": 0.07}, {"mName": "MaxMultiplier", "mValue": 3.0}],
                "mItemCalculations": {"CurrentHealthCalc": {"mFormulaParts": [{"mDataValue": "{03df7ad0}", "__type": "NamedDataValueCalculationPart"}], "mDisplayAsPercent": True, "__type": "GameCalculation"},
                                      "MaxCurrentHealthCalc": {"mMultiplier": {"mDataValue": "MaxMultiplier", "__type": "NamedDataValueCalculationPart"},
                                                               "mModifiedGameCalculation": "CurrentHealthCalc", "__type": "GameCalculationModified"}}},
    "hydra": {"mDataValues": [{"mName": "Z", "mValue": 1.0}],
              "mItemCalculations": {"Cleave": {"mFormulaParts": [{"mStat": 12, "mCoefficient": 0.01, "__type": "StatByCoefficientCalculationPart"}], "__type": "GameCalculation"}}},
}
RANK_CHECKS = None

results = []
def check(name, fn):
    try:
        ok = fn()
    except Exception as e:
        ok = False; name += f"（{e!r}）"
    results.append(ok)
    print(("✓ " if ok else "✗ ") + name)

def main():
    out, err = sys.stdout, sys.stderr
    import fetch_items as F
    import fetch_skills as K
    sys.stdout, sys.stderr = out, err  # 模組 import 時會包 stdout
    def fill(item, tpl):
        e = ITEMS[item]
        lut = F.build_lut(e)
        return F.fill(tpl, lut, F.build_calcs(e, lut), F.item_ctx(e))
    check("雜湊 data value 查得到，遠程值取到一位小數", lambda: fill("hubris", "增加@BaseADBonus@物理攻擊") == ("增加15（遠程 10）物理攻擊", 0))
    check("值自帶魔抗標籤又接單位：去掉單位（#2620）", lambda: F.fill("+5% 額外魔抗魔法防禦", {}, {})[0] == "+5% 額外魔抗")
    check("物理致命接模板 %：百分比移到數字後面（公理弧刃 #2621）", lambda: F.fill("返還10（每 1 物理致命 +0.25）%冷卻", {}, {})[0] == "返還10%（每 1 物理致命 +0.25%）冷卻")
    check("物理致命沒接 %：不動（闇影戰戟 #2621）", lambda: F.fill("造成50（每 1 物理致命 +1.5）真實傷害", {}, {})[0] == "造成50（每 1 物理致命 +1.5）真實傷害")
    # #2636：即時統計、沒數字的模板、圖示夾在 + 與數字之間
    WARMOG = "<passive>好戰之心</passive> <br>每秒回復生命。<br><br><passive>好戰活力</passive><br>獲得相當於@HPAmp*100@%道具生命(<healing>@f2@</healing>)的額外生命。"
    check("括號裡的即時統計：拿括號，句子留著（好戰者鎧甲）", lambda: F.drop_live_stats(WARMOG).endswith("<passive>好戰活力</passive><br>獲得相當於@HPAmp*100@%道具生命的額外生命。"))
    check("全形括號也認得", lambda: F.drop_live_stats("A（@f1@）B") == "AB")
    check("整句統計：連只剩標題的上一行一起拿掉", lambda: F.drop_live_stats("<passive>甲</passive><br>乙<br><br><passive>統計</passive><br>造成傷害：@f3@") == "<passive>甲</passive><br>乙")
    check("整句統計的標題拿掉，下一段照留", lambda: F.drop_live_stats("<passive>統計</passive><br>累積@f1@<br><br><passive>丙</passive><br>丁") == "<br><passive>丙</passive><br>丁")
    check("整句統計上一行是內文：內文留著（對照）", lambda: F.drop_live_stats("<passive>甲</passive><br>內文<br>累積@f1@") == "<passive>甲</passive><br>內文")
    check("帶小數編號的統計也算（@f3.1@）", lambda: F.drop_live_stats("內文<br>士兵：@f3.1@") == "內文")
    check("帶小數編號的括號也算", lambda: F.drop_live_stats("擊殺士兵(<b>@f3.1@</b>)來完成") == "擊殺士兵來完成")
    check("括號裡不只統計：不當括號拿，整句剔除", lambda: F.drop_live_stats("內文<br>魔法攻擊(目前@f2@)") == "內文")
    check("沒有統計：原樣（對照）", lambda: F.drop_live_stats(WARMOG.replace("(<healing>@f2@</healing>)", "")) == WARMOG.replace("(<healing>@f2@</healing>)", ""))
    HORN_T = "<mainText><stats><attention>150</attention> 生命</stats><br><br>隨著時間回復生命。</mainText>"
    HORN_D = "<mainText><stats><attention>150</attention> 生命</stats><br><br>每5秒回復<healing>20生命</healing>。</mainText>"
    check("模板沒數字、DDragon 有：換 DDragon（保衛者號角）", lambda: F.prefer_dd_digits(HORN_T, "隨著時間回復生命。", HORN_D, {}) == HORN_D)
    check("模板有數字：不換（對照）", lambda: F.prefer_dd_digits(HORN_T, "回復5生命。", HORN_D, {}) == HORN_T)
    check("DDragon 只有屬性列有數字：不換", lambda: F.prefer_dd_digits(HORN_T, "隨著時間回復生命。", "<mainText><stats><attention>150</attention> 生命</stats><br><br>回復生命。</mainText>", {}) == HORN_T)
    check("DDragon 沒內文：不換", lambda: F.prefer_dd_digits(HORN_T, "隨著時間回復生命。", "<mainText><stats><attention>150</attention> 生命</stats><br><br></mainText>", {}) == HORN_T)
    check("圖示夾在 + 與數字之間：黏回去（雲陶狂箭）", lambda: F.fill("永久獲得+%i:scaleCrit% 0.4%暴擊率", {}, {})[0] == "永久獲得+0.4%暴擊率")
    check("算式的 +：前面是空白不動（對照）", lambda: F.fill("10 秒 + 9 金錢", {}, {})[0] == "10 秒 + 9 金錢")
    check("算式的 +：前面是括號不動（對照）", lambda: F.fill("（15% AP）+ 3%最大生命", {}, {})[0] == "（15% AP）+ 3%最大生命")
    check("算式的 +：前面是數字不動（對照）", lambda: F.fill("500+ 10%", {}, {})[0] == "500+ 10%")
    # #2622：冷卻佔位與「沒有時限」的佔位秒數
    check("冷卻佔位填成秒數（破堡者）", lambda: F.fill("<passive>聚能炸藥</passive> {{Item_Cooldown}}<br>X", {"cooldown": 20.0}, {}) == ("<passive>聚能炸藥（20秒）</passive><br>X", 0))
    check("冷卻佔位有空白也認得（守護天使）", lambda: F.fill("A{{ Item_Cooldown }}", {"cooldown": 300.0}, {}) == ("A（300秒）", 0))
    check("小數冷卻（咒刃 1.5）", lambda: F.fill("A{{ Item_Cooldown}}", {"cooldown": 1.5}, {}) == ("A（1.5秒）", 0))
    check("查不到冷卻：拿掉、不算 miss（不可讓 strip_holes 刪整行）", lambda: F.fill("A{{ Item_Cooldown }}B", {}, {}) == ("AB", 0))
    check("被動名稱帶冒號：冷卻排在冒號前（巫妖之禍）", lambda: F.fill("<passive>魔法彎刀：</passive>{{Item_Cooldown}}使用", {"cooldown": 1.5}, {})[0] == "<passive>魔法彎刀（1.5秒）：</passive>使用")
    check("主動也搬進名稱", lambda: F.fill("<active>新月</active> {{Item_Cooldown}}", {"cooldown": 10.0}, {})[0] == "<active>新月（10秒）</active>")
    check("每個目標：一起搬進名稱（獄火手斧）", lambda: F.fill("<passive>燒焦</passive>每個目標{{ Item_Cooldown }}<br>X", {"cooldown": 8.0}, {})[0] == "<passive>燒焦（每個目標8秒）</passive><br>X")
    check("句中的冷卻留在原位（對照）", lambda: F.fill("<passive>A</passive>造成傷害 {{Item_Cooldown}}。", {"cooldown": 5.0}, {})[0] == "<passive>A</passive>造成傷害 （5秒）。")
    check("模板已印數字：括號內不重複（暮色黑刃）", lambda: F.fill("持續1秒(@Cooldown@{{Item_Cooldown}})，或", {"cooldown": 30.0}, {})[0] == "持續1秒(30秒)，或")
    check("模板已印數字又接秒：不重複（拉克爾之盾）", lambda: F.fill("每@Cooldown@{{ Item_Cooldown }}秒，阻擋", {"cooldown": 8.0}, {})[0] == "每8秒，阻擋")
    check("模板已印數字但查不到：算 miss（舊行為）", lambda: F.fill("(@Cooldown@{{Item_Cooldown}})", {}, {})[1] == 1)
    check("潛行者之爪的雙層括號", lambda: F.fill("範圍({{ Item_Cooldown }}為5秒)。", {"cooldown": 30.0}, {})[0] == "範圍（冷卻30秒，為5秒）。")
    check("模板已印數字：token 大小寫不拘", lambda: F.fill("(@cooldown@{{Item_Cooldown}})", {"cooldown": 30.0}, {})[0] == "(30秒)")
    check("冷卻 0：拿掉，不印（0秒）", lambda: F.fill("A{{Item_Cooldown}}", {"cooldown": 0.0}, {}) == ("A", 0))
    check("其他佔位照舊清掉（對照）", lambda: F.fill("A{{ Item_Ghosting }}", {"cooldown": 5.0}, {}) == ("A", 0))
    check("25000 秒＝沒有時限（破堡者破壞）", lambda: F.fill("獲得破壞效果@BuffDuration@秒。", {"buffduration": 25000.0}, {})[0] == "獲得破壞效果（永久）。")
    check("普通持續秒數不動（對照）", lambda: F.fill("持續@BuffDuration@秒。", {"buffduration": 300.0}, {})[0] == "持續300秒。")
    check("每級清單尾巴不被吃（對照）", lambda: F.fill("1/25000秒", {}, {})[0] == "1/25000秒")
    # #2622：近戰／遠程佔位（死亡之舞、聖裂之杖）與命中效果
    check("近遠程佔位填成兩個值", lambda: fill("split", "所受傷害的{{ Item_Melee_Ranged_Split_Dynamic }}改為") == ("所受傷害的30%（遠程 10%）改為", 0))
    check("沒有 Dynamic 的寫法同一組值", lambda: fill("split", "每秒{{ Item_Melee_Ranged_Split }}") == ("每秒30%（遠程 10%）", 0))
    check("_B 取 B 那一組", lambda: fill("split", "{{ Item_Melee_Ranged_Split_B }}目標") == ("4%（遠程 2%）目標", 0))
    check("Dynamic_B 取 B 那一組", lambda: fill("split", "{{Item_Melee_Ranged_Split_Dynamic_B}}") == ("4%（遠程 2%）", 0))
    check("近遠程相同只印一個", lambda: fill("splitsame", "{{ Item_Melee_Ranged_Split }}") == ("30%", 0))
    check("沒有計算式：拿掉、不算 miss", lambda: fill("split", "{{ Item_Melee_Ranged_Split_C }}X") == ("X", 0))
    check("沒有 ictx 不崩潰", lambda: F.fill("{{ Item_Melee_Ranged_Split }}X", {}, {}) == ("X", 0))
    check("命中效果佔位", lambda: F.fill("逐步冰封：{{ Item_Keyword_OnHit }}，附加", {}, {})[0] == "逐步冰封：命中效果，附加")
    check("命中效果接模板的「效果」不重複", lambda: F.fill("會附加{{ Item_Keyword_OnHit }}效果兩次", {}, {})[0] == "會附加命中效果兩次")
    check("值自帶護甲標籤又接單位：去掉單位（#2620）", lambda: F.fill("+5% 額外護甲物理防禦", {}, {})[0] == "+5% 額外護甲")
    check("純數字接單位不動（對照）", lambda: F.fill("獲得 25 魔法防禦和 30 物理防禦", {}, {})[0] == "獲得 25 魔法防禦和 30 物理防禦")
    check("mValue 缺值的 data value 不會崩潰", lambda: fill("hubris", "@SpellMaxAmp@X")[0] == "X")
    check("計算式引用 mValue 缺值的 data value：當 0、算 miss，不崩潰", lambda: fill("nullv", "A@UsesEmpty@") == ("A", 1))
    check("百分比計算式的遠程值，模板再接 % 不會變 %%", lambda: fill("shiv", "提升@AuraAttackSpeed@%攻速") == ("提升30%（遠程 20%）攻速", 0))
    check("百分比計算式配 *100 不會乘兩次", lambda: fill("shiv", "@AuraAttackSpeed*100@") == ("30%（遠程 20%）", 0))
    check("魔力係數：總魔力", lambda: fill("manamune", "@BonusADFromMana@") == ("+2% 魔力", 0))
    check("魔力係數：mStatFormula 2＝額外魔力，% 不重複", lambda: fill("manamune", "@Bonus@%") == ("+15% 額外魔力", 0))
    check("效果值 1 起算，mStat 12＋額外＝額外生命", lambda: fill("ember", "@TotalBurnDamage@") == ("60（+2% 額外生命）", 0))
    check("效果值索引超出範圍算 miss，不崩潰", lambda: fill("ember", "A@Bad@") == ("A", 1))
    check("mStat 12 沒有 mStatFormula＝最大生命", lambda: fill("hydra", "@Cleave@") == ("+1% 最大生命", 0))
    check("小係數改用每 100 點講，不四捨五入成 +0%", lambda: fill("seer", "@ManaCalc@") == ("15%（每 100 額外魔力 +0.5%）", 0))
    check("GameCalculationModified 保留百分比", lambda: fill("hatchet", "@CurrentHealthCalc@至@MaxCurrentHealthCalc@") == ("7%至21%", 0))
    check("TOK 不收的 token 算 miss，文字裡清掉", lambda: fill("hubris", "A@spell.SummonerSmite:PetDPS@B@spell.Puppy:Amp*100@C") == ("ABC", 2))
    check("4 個外部 token 超過 main 的門檻 3", lambda: fill("hubris", "@spell.a:b@@spell.a:c@@spell.a:d@@spell.a:e@")[1] > 3)
    check("普通 email 樣的文字不誤判（空白隔開不算 token）", lambda: fill("hubris", "a @ b @ c") == ("a @ b @ c", 0))
    # 技能端：小係數門檻與效果值不外溢
    class C: ranks = 1
    def rv(flat, scal, pct=True):
        v = K.Val(flat=flat, scal=scal); v.pct = pct
        return K.render_val(v)
    check("技能：百分比小係數用每 100 點", lambda: rv([5], [([0.04], "AP")]) == "5%（每 100 AP +4%）")
    check("技能：門檻上緣 0.1 維持原寫法", lambda: rv([5], [([0.1], "AP")]) == "5%（+0.1% AP）")
    check("技能：非百分比計算式不受影響", lambda: rv([50], [([0.5], "AP")], False) == "50（+50% AP）")
    check("技能：非百分比的小係數也不改寫", lambda: rv([50], [([0.0005], "AP")], False) == "50（+0.05% AP）")
    def eff_skill():
        ctx = K.SpellCtx({"mSpellCalculations": {}}, 1)
        try:
            K.eval_part(ctx, {"mEffectIndex": 1, "__type": "EffectValueCalculationPart"})
        except K.Miss:
            return True
        return False
    check("技能：沒有 mEffectAmount 時效果值 Miss（有的情況見 fetch_skills_levelval_test）", eff_skill)
    check("技能：Ryze 型魔力係數算得出來", lambda: K.render_val(K.eval_part(K.SpellCtx({}, 1), {"mCoefficient": 0.02, "mStatFormula": 2, "__type": "AbilityResourceByCoefficientCalculationPart"})) == "+2% 額外魔力")
    check("基礎生命標籤", lambda: K._stat_label({"mStat": 12, "mStatFormula": 1}) == "基礎生命")

    # #2623：字串表展開
    ST = {"item_active_consume": "%i:activeEffect% <active>主動─消耗：</active>",
          "item_grievous_wounds": "<status>重創效果</status>降低治療及回復效果的效益。",
          "item_support_spoils_of_war_01": "<li><passive>戰亂之殤：</passive>普攻處決低於  {{ Item_Range_Mod_@ChampRange@_Perc }}最大生命的士兵",
          "item_support_spoils_of_war_02": "<li><passive>戰亂之殤：</passive>普攻處決低於 @Effect2Amount*100@% 最大生命的士兵"}
    X = F.expand_tokens
    check("展開：主動消耗", lambda: X("{{ Item_Active_Consume }}連結", ST) == "<active>主動─消耗：</active>連結")
    check("展開：圖示佔位旁的空白一起拿掉", lambda: X("{{ Item_Melee_Ranged_Rules }}", {"item_melee_ranged_rules": "道具對 %i:meleeInactive% 近戰英雄和 %i:rangedInactive% 遠攻英雄"}) == "道具對近戰英雄和遠攻英雄")
    check("展開：規則說明放進 rules", lambda: X("<rules>{{ Item_Grievous_Wounds }}</rules>", ST) == "<rules><status>重創效果</status>降低治療及回復效果的效益。</rules>")
    check("展開：沒空白也認得", lambda: "重創效果" in X("{{Item_Grievous_Wounds}}", ST))
    check("展開：戰亂之殤 01 帶近戰遠程佔位", lambda: "低於@MeleeValue*100@%（遠程 @RangedValue*100@%）最大生命" in X("{{ Item_Support_Spoils_Of_War_01 }}", ST))
    check("展開：戰亂之殤 02", lambda: "@Effect2Amount*100@%" in X("{{ Item_Support_Spoils_Of_War_02 }}", ST))
    check("展開：字串表沒定義就原樣留著", lambda: X("{{ Item_Ghosting }}", ST) == "{{ Item_Ghosting }}")
    check("展開：名單外的佔位不動", lambda: X("{{ Item_Passive_List }}A", ST) == "{{ Item_Passive_List }}A")
    check("主動名稱不留 active 標籤", lambda: X("獲得 {{ Item_Active_Named_NoBullet }} <active>守衛</active>。", ST) == "獲得 主動─守衛。")
    check("主動佔位黏著也認得", lambda: X("並獲得{{ Item_Active_Named_NoBullet }}<active>守衛</active>", ST) == "並獲得主動─守衛")
    check("別的 active 不受影響", lambda: X("<active>沙刃</active>", ST) == "<active>沙刃</active>")
    check("神話被動整行拿掉、尾端不留換行", lambda: X("A<br><br>{{ Item_Mythic_Passive }} <attention>5</attention> 護甲。", ST) == "A")
    check("神話被動（右括號前沒空白）", lambda: X("A<br>{{ Item_Mythic_Passive}} 5 急速<br>B", ST) == "A<br>B")
    check("沒有神話被動時尾端換行不動", lambda: X("A<br>", ST) == "A<br>")
    def spoils_filled():
        e = {"mEffectAmount": [2.0, 0.5, 0.30000001192092896, 500.0, 35.0, 3.0],
             "mDataValues": [{"mName": "MeleeValue", "mValue": 0.5}, {"mName": "RangedValue", "mValue": 0.30000001192092896}]}
        lut = F.build_lut(e)
        return F.fill(X("{{ Item_Support_Spoils_Of_War_01 }}", ST), lut, F.build_calcs(e, lut), F.item_ctx(e))
    check("戰亂之殤 01 填完是 50%（遠程 30%）", lambda: spoils_filled()[0].endswith("低於50%（遠程 30%）最大生命的士兵") and spoils_filled()[1] == 0)

    # 主動效果在 keyActive（#2634）：素材節錄自 16.22 字串表與 bin
    def E(**lk):
        return {"mItemDataClient": {"mTooltipData": {"mLocKeys": {"keyName": "x", **lk}}}}
    P = F.pick_template
    ZH = {"item_3157_active": "%i:activeEffect% <active>時間暫停</active>{{ Item_Cooldown }}<br>進入凝滯狀態，持續@Duration@秒。",
          "item_3157_tooltipextended": "{{ Item_Only_OnActivation }} (@Cooldown@{{Item_Cooldown}})"}
    check("模板：只有主動就用主動，不用只剩冷卻的 extended（中婭）", lambda: P("3157", E(keyActive="Item_3157_Active"), ZH) == ZH["item_3157_active"])
    GB = {"item_3146_active": "{{ Item_OnActivation }} {{ Item_Cooldown }}<br><active>閃電霹靂</active><br>電擊",
          "item_3146_tooltip": "<passive>技能吸血</passive><br>獲得@SpellVamp*100@%技能吸血"}
    check("模板：過期的 tooltip 不跟，主動名稱排到冷卻前面（槍刃）", lambda: P("3146", E(keyActive="Item_3146_Active"), GB) == "<active>閃電霹靂</active>{{ Item_Cooldown }}<br><br>電擊")
    RA = {"item_3143_active": "<active>謙遜</active>{{ Item_Cooldown }}<br>緩速", "item_3143_tooltip": "<passive>抗壓</passive><br>減少@X@。<br>"}
    check("模板：被動在前、主動在後（蘭頓）", lambda: P("3143", E(keyActive="Item_3143_Active", keyTooltip="Item_3143_Tooltip"), RA) == "<passive>抗壓</passive><br>減少@X@。<br><br><active>謙遜</active>{{ Item_Cooldown }}<br>緩速")
    PO = {"item_2003_active": "<active>喝下</active><br>回復", "item_2003_tooltip": "<br><rules>最多5瓶。</rules>"}
    check("模板：只有規則的 tooltip 要留，放在主動後面（藥水）", lambda: P("2003", E(keyActive="Item_2003_Active"), PO) == "<active>喝下</active><br>回復<br><rules>最多5瓶。</rules>")
    SR = {"item_3095_tooltip": "<passive>強力暴擊</passive><br>舊", "item_3095_tooltip_kiwi": "<passive>充能箭</passive><br>@TotalProcDamage@"}
    check("模板：keyTooltip 指到同一件的新版就跟（狂暴利刃）", lambda: P("3095", E(keyTooltip="Item_3095_Tooltip_Kiwi"), SR) == SR["item_3095_tooltip_kiwi"])
    OB = {"item_3039_tooltip": "<passive>喝采</passive>@A@", "item_223039_tooltip": "<passive>競技場</passive>@B@"}
    check("模板：keyTooltip 指到別件不跟（終末戰戟）", lambda: P("3039", E(keyTooltip="Item_223039_Tooltip"), OB) == OB["item_3039_tooltip"])
    check("模板：沒有 keyActive 維持舊順序（含 @ 優先）", lambda: P("1", E(), {"item_1_tooltip": "簡述", "item_1_tooltipextended": "有@A@"}) == "有@A@")
    check("模板：沒有 mLocKeys 也不炸", lambda: P("1", {}, {"item_1_tooltip": "簡述"}) == "簡述")
    check("模板：字串表沒有 keyActive 那條就當沒有", lambda: P("1", E(keyActive="Item_1_Active"), {"item_1_tooltip": "@A@"}) == "@A@")
    check("模板：同名主動已在 tooltip 不重複", lambda: P("5", E(keyActive="Item_5_Active", keyTooltip="Item_5_Tooltip"), {"item_5_active": "<active>甲</active>乙", "item_5_tooltip": "A<active>甲</active>B"}) == "A<active>甲</active>B")
    NA = {"item_6_active": "{{ Item_OnActivation }}<br>選擇宿敵"}
    check("模板：只有「主動」沒有名字時補上主動", lambda: P("6", E(keyActive="Item_6_Active"), NA) == "<active>主動</active><br>選擇宿敵")
    def filled(e, t):
        lut = F.build_lut(e)
        return F.fill(t, lut, F.build_calcs(e, lut), F.item_ctx(e))[0]
    YM = {"mDataValues": [{"mName": "MeleeItemCalcValueB", "mValue": 20.0}, {"mName": "RangedItemCalcValueB", "mValue": 15.0}]}
    check("近戰遠程值放在 mDataValues 也讀得到，% 兩邊都有（妖夢）", lambda: filled(YM, "增加{{Item_Melee_Ranged_Split_Dynamic_B}}%跑速") == "增加20%（遠程 15%）跑速")
    CDB = {"mDataValues": [{"mName": "ItemCooldown", "mValue": 90.0}, {"mName": "Cooldown", "mValue": 90.0}]}
    check("別名冷卻欄位接佔位不重複", lambda: filled(CDB, "(@ItemCooldown@{{ Item_Cooldown }})") == "(90秒)")
    check("數字接同值冷卻收成一個（神聖之劍）", lambda: filled(CDB, "(90{{ Item_Cooldown }})") == "(90秒)")
    RD = {"item_3107_active": "<active>審判</active>回復", "item_3107_tooltip": "<rules>受到其他<active>審判</active>影響</rules>"}
    check("模板：規則提到同名主動，主動還是要補（贖罪神石）", lambda: P("3107", E(keyActive="Item_3107_Active", keyTooltip="Item_3107_Tooltip"), RD) == "<active>審判</active>回復<rules>受到其他<active>審判</active>影響</rules>")
    BIND = {"mDataValues": [{"mName": "BindCooldown", "mValue": 30.0}, {"mName": "Cooldown", "mValue": 90.0}]}
    check("別名冷卻用自己的值，不被 Cooldown 蓋掉（錫柯）", lambda: filled(BIND, "（@BindCooldown@{{ Item_Cooldown }}）") == "（30秒）")
    check("% 後面的冷卻括號不留空格（狂風之力）", lambda: filled(CDB, "最多50% (@Cooldown@{{ Item_Cooldown }})。") == "最多50%（90秒）。")
    check("數字接不同值冷卻不收", lambda: filled(CDB, "(9{{ Item_Cooldown }})") == "(9（90秒）)")
    # #2635：素材節錄自 16.22 狂熱雙刀 3086、贖罪神石 3107、鷹眼晶球 3363
    ZEAL = {"mEffectAmount": [0.0], "mPercentMovementSpeedMod": 0.04}
    ZT = "<li><passive>狂熱：</passive>獲得 <speed> @Effect1Amount*100@% 跑速</speed>。"
    zl = F.build_lut(ZEAL)
    check("mEffectAmount 的 0 當查不到（狂熱雙刀）", lambda: "effect1amount" not in zl and F.fill(ZT, zl, F.build_calcs(ZEAL, zl), None)[1] == 1)
    check("整行拿掉，不留 0% 跑速（狂熱雙刀）", lambda: F.strip_holes(ZT, zl, F.build_calcs(ZEAL, zl), None) == "")
    check("對照：mEffectAmount 非 0 照填", lambda: F.fill("@Effect2Amount@秒", F.build_lut({"mEffectAmount": [0.0, 3.0]}), {}, None) == ("3秒", 0))
    check("mDataValues 的 0 不受影響", lambda: F.fill("@X@秒", F.build_lut({"mDataValues": [{"mName": "X", "mValue": 0.0}]}), {}, None) == ("0秒", 0))
    check("上一版的 0 不算數字，不會蓋掉修好的版本", lambda: F.digit_runs("<a>15%</a> 4% 獲得 0% 跑速") == F.digit_runs("<a>15%</a> 4%") == 2)
    check("對照：0.5、10、100 照算", lambda: F.digit_runs("0.5秒 10 100") == 4)
    RD = {"healmin": 150.0, "healmax": 350.0}
    check("區間與友軍等級（贖罪神石）", lambda: F.fill("回復@HealMin@ - @HealMax@(友軍%i:scaleLevel%)生命", RD, {}) == ("回復150－350（依友軍等級）生命", 0))
    check("區間（鷹眼晶球）", lambda: F.fill("(@A@ - @B@秒)", {"a": 198.0, "b": 99.0}, {}) == ("(198－99秒)", 0))
    check("對照：減號沒接空白不動", lambda: F.fill("等級1-18", {}, {}) == ("等級1-18", 0))
    check("對照：其他圖示仍清掉", lambda: F.fill("A%i:scaleAD%B", {}, {}) == ("AB", 0))

    # 舊版對照：同一份素材，舊版真的查不到、真的漏 token、真的標當前生命
    if "TOKENS_SCRIPTS" not in os.environ:
        d = tempfile.mkdtemp()
        for f in ("fetch_items.py", "fetch_skills.py"):
            b = subprocess.run(["git", "show", f"fd6094b6:scripts/{f}"], cwd=os.path.dirname(HERE), capture_output=True).stdout
            assert b, f
            open(os.path.join(d, f), "wb").write(b)
        code = ("import json,sys,io\n"
                "sys.path.insert(0,sys.argv[1])\n"
                "import fetch_items as F, fetch_skills as K\n"
                "I=json.loads(sys.argv[2])\n"
                "def fill(i,t):\n"
                " e=I[i];l=F.build_lut(e);return F.fill(t,l,F.build_calcs(e,l),F.item_ctx(e))\n"
                "r=[fill('hubris','@BaseADBonus@'),fill('hubris','A@spell.a:b@'),fill('manamune','@BonusADFromMana@'),K._stat_label({'mStat':12})]\n"
                "open(sys.argv[3],'w',encoding='utf-8').write(json.dumps(r,ensure_ascii=False))\n")
        rf = os.path.join(d, "r.json")
        p = subprocess.run([sys.executable, "-c", code, d, json.dumps(ITEMS), rf], capture_output=True, cwd=d)
        r = json.load(open(rf, encoding="utf-8")) if os.path.exists(rf) else None
        check("舊版對照：跑得起來", lambda: r is not None)
        if r:
            check("舊版對照：雜湊 data value 查不到", lambda: r[0] == ["", 1])
            check("舊版對照：外部 token 留在文字裡", lambda: r[1] == ["A@spell.a:b@", 0])
            check("舊版對照：魔力係數查不到", lambda: r[2] == ["", 1])
            check("舊版對照：mStat 12 標當前生命", lambda: r[3] == "當前生命")
    bad = results.count(False)
    print(f"合計 ✓ {results.count(True)}／✗ {bad}")
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
