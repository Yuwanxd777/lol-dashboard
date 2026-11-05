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
    check("技能：效果值維持 Miss（技能的 mEffectAmount 有前置佔位）", eff_skill)
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
