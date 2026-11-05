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
