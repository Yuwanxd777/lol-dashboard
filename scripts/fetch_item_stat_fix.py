# -*- coding: utf-8 -*-
"""產生 item_stat_fix.js（window.ITEM_STAT_FIX）＝把版本改動裡「屬性：a, b, c。」這種
**只寫改完後數值、沒寫改動前**的行，補成全站統一的「舊 ⇒ 新」寫法。

為什麼要這份（2026-07-31 使用者回報）：
  遠古意志 13.14「屬性：10 魔力回復, 10% 冷卻時間減免, 20% 法術吸血, 50 技能強度。」
  → 看不出哪一項變強變弱，判向也判不出來（白字）。使用者要求「去翻 DD 看以前的數值多少」。

做法：只針對 wiki_extra.js 裡真的出現這種行的 (版本, 道具) 去抓，不整包下載。
  wiki 版本 YY.MM → DDragon 主版號 (YY-10).MM（13.14＝2013 賽季 patch 3.14）。
  用 versions.json 找該 minor 的實際三段號，再找**前一個 minor** 的三段號，
  兩邊的 item.json stats 逐項比對，只列有變動的項目。
輸出 {原始行文字: 改寫後文字}，顯示層直接查表替換（renderChgLines）。

用法：python scripts\\fetch_item_stat_fix.py
"""
import io, json, os, re, sys, urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "item_stat_fix.js")
UA = {"User-Agent": "Mozilla/5.0"}

# DDragon stats 欄位 → 全站用語（與 index.html 的 normTerm 對齊）
STAT_ZH = {
    "FlatPhysicalDamageMod": "物攻", "FlatMagicDamageMod": "魔攻",
    "FlatHPPoolMod": "生命", "FlatMPPoolMod": "魔力",
    "FlatArmorMod": "物防", "FlatSpellBlockMod": "魔防",
    "FlatHPRegenMod": "生命回復", "FlatMPRegenMod": "魔力回復",
    "FlatCritChanceMod": "爆擊率", "FlatMovementSpeedMod": "移速",
    "PercentAttackSpeedMod": "攻速", "PercentLifeStealMod": "吸血",
    "PercentMovementSpeedMod": "移速", "PercentCritChanceMod": "爆擊率",
    "PercentHPPoolMod": "生命", "PercentMPPoolMod": "魔力",
    "PercentHPRegenMod": "生命回復", "PercentMPRegenMod": "魔力回復",
    "PercentArmorMod": "物防", "PercentSpellBlockMod": "魔防",
}
PCT = {"PercentAttackSpeedMod", "PercentLifeStealMod", "PercentMovementSpeedMod",
       "PercentCritChanceMod", "PercentHPPoolMod", "PercentMPPoolMod",
       "PercentHPRegenMod", "PercentMPRegenMod", "PercentArmorMod",
       "PercentSpellBlockMod", "FlatCritChanceMod"}


def geturl(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read()


def clname(n):
    n = re.sub(r"：\s+", "：", str(n or ""))
    return re.sub(r"\s*[（(][^（）()]*[）)]\s*$", "", n).strip()


def load_extra():
    p = os.path.join(ROOT, "wiki_extra.js")
    s = io.open(p, encoding="utf-8").read()
    i = s.index("=", s.index("window.WIKI_EXTRA"))
    return json.loads(s[i + 1:s.rindex("}") + 1])


def num(v, key):
    f = float(v)
    if key in PCT:
        f *= 100
    return round(f, 2)


def fmt(f):
    return str(int(f)) if abs(f - int(f)) < 1e-9 else str(f)


def clean_recipe(s):
    return re.sub(r"[\s＋+金＝=]", "", str(s))


# 「不再提供◯◯」裡的屬性 → DDragon stats 欄位（查道具自身屬性用）
STAT_KEY = {
    "物防": ["FlatArmorMod"], "魔防": ["FlatSpellBlockMod"],
    "物攻": ["FlatPhysicalDamageMod"], "魔攻": ["FlatMagicDamageMod"],
    "生命": ["FlatHPPoolMod"], "魔力": ["FlatMPPoolMod"],
    "生命回復": ["FlatHPRegenMod"], "魔力回復": ["FlatMPRegenMod"],
    "移動速度": ["FlatMovementSpeedMod", "PercentMovementSpeedMod"],
    "攻速": ["PercentAttackSpeedMod"], "爆擊率": ["FlatCritChanceMod"],
}
# 同上 → 說明文字裡的寫法（光環數值只寫在 description，stats 抓不到）
STAT_DESC = {
    "物防": ["物理防禦", "護甲", "物防"], "魔防": ["魔法防禦", "魔抗", "魔防"],
    "物攻": ["攻擊力", "物理傷害", "物攻"], "魔攻": ["法術強度", "技能強度", "魔攻"],
    "生命": ["生命"], "魔力": ["魔力", "法力"],
    "生命回復": ["生命回復"], "魔力回復": ["魔力回復"],
    "移動速度": ["移動速度", "移速", "跑速"], "攻速": ["攻擊速度", "攻速"],
    "法術吸血": ["法術吸血"], "冷卻縮減": ["冷卻縮減", "冷卻時間減免"],
}
# 早年說明文字的特殊寫法（不是「N 生命回復」而是「每 5 秒回復 10 生命」這種）
STAT_ALT = {
    "生命回復": [r"每\s*5\s*秒回復\s*([\d.]+)()\s*點?\s*生命"],
    "魔力回復": [r"每\s*5\s*秒回復\s*([\d.]+)()\s*點?\s*魔力"],
    "魔力": [r"([\d.]+)\s*(%)\s*基礎魔力"],
    "生命": [r"([\d.]+)\s*(%)\s*基礎生命"],
}
_STAT_PAT = "|".join(sorted(STAT_DESC, key=len, reverse=True))


def main():
    EX = load_extra()
    # 1) 收集需要補值的行
    #    todo    ＝「屬性：a, b, c。」只寫改完後、沒寫改動前
    #    recipes ＝「新增合成公式：X」而同一張卡沒有「舊合成公式」可配對
    todo, recipes, nolonger = {}, {}, {}
    for ver, secs in EX.items():
        if not isinstance(secs, dict):
            continue
        m = re.match(r"^(\d{2})\.(\d{1,2})$", str(ver))
        if not m:
            continue
        major, minor = int(m.group(1)) - 10, int(m.group(2))
        for sec, arr in secs.items():
            if sec != "道具" or not isinstance(arr, list):
                continue
            by_item = {}
            for line in arr:
                p = line.find("｜")
                if p > 0:
                    by_item.setdefault(line[:p], []).append(line)
            for pre, ls in by_item.items():
                if re.search(r"新增道具|全新道具|新道具登場", pre):
                    continue
                nm = clname(pre)
                has_old = any(re.match(r"^\s*舊合成公式", l[l.find("｜") + 1:]) for l in ls)
                for line in ls:
                    body = line[line.find("｜") + 1:]
                    if "⇒" not in line and re.match(r"^\s*屬性[：:]", body):
                        todo.setdefault((major, minor), []).append((line, nm))
                    elif not has_old and re.match(r"^\s*新增合成公式[：:]", body):
                        recipes.setdefault((major, minor), []).append((line, nm))
                    elif "⇒" not in line and re.search(r"不再(提供|給予|附帶)", body):
                        # 只收「沒寫數值」的（有寫的顯示層自己會改成 X ⇒ 0）
                        tail = body[body.find("不再"):]
                        if re.search(r"\d", tail):
                            continue
                        m3 = re.search(_STAT_PAT, tail)
                        if m3:
                            nolonger.setdefault((major, minor), []).append((line, nm, m3.group(0)))
                        elif re.search(r"不再(給予|提供|附帶)\s*(唯一)?(光環|靈氣)", tail):
                            nolonger.setdefault((major, minor), []).append((line, nm, "光環"))
                    elif "⇒" not in line and not re.search(r"\d", body):
                        # 「物防移除。」「生命回復移除。」這種也沒寫原本多少
                        #（2026-07-31 使用者：指揮旗幟 13.14、歐姆破壞者 13.14）
                        m5 = re.match(r"^\s*(%s)\s*移除\s*[。.]?\s*$" % _STAT_PAT, body)
                        if m5:
                            nolonger.setdefault((major, minor), []).append((line, nm, m5.group(1)))
    print("需要補前後值的行：屬性 %d 行、落單合成公式 %d 行、不再提供 %d 行（涉及 %d 個版本）"
          % (sum(len(v) for v in todo.values()), sum(len(v) for v in recipes.values()),
             sum(len(v) for v in nolonger.values()), len(set(todo) | set(recipes) | set(nolonger))))
    if not todo and not recipes and not nolonger:
        return

    # 2) DDragon 版本清單：每個 major.minor 取最後（最新）的三段號
    vs = json.loads(geturl("https://ddragon.leagueoflegends.com/api/versions.json"))
    last = {}
    for v in vs:                                    # versions.json 由新到舊
        m = re.match(r"^(\d+)\.(\d+)\.", v)
        if m:
            last.setdefault((int(m.group(1)), int(m.group(2))), v)
    keys = sorted(last)
    cache = {}

    def items_of(v):
        """回傳 (依名稱查道具, 依 id 查名稱)"""
        if v in cache:
            return cache[v]
        try:
            d = json.loads(geturl(
                "https://ddragon.leagueoflegends.com/cdn/%s/data/zh_TW/item.json" % v))["data"]
            by_name = {clname(it.get("name")): it for it in d.values()}
            by_id = {str(k): clname(it.get("name")) for k, it in d.items()}
            cache[v] = (by_name, by_id)
        except Exception as e:
            print("   %s：抓不到（%s）" % (v, type(e).__name__))
            cache[v] = ({}, {})
        return cache[v]

    def recipe_of(it, by_id):
        """DDragon 道具 → 「材料A＋材料B＋合成費 金 = 總價 金」"""
        g = it.get("gold") or {}
        parts = [by_id.get(str(x), "") for x in (it.get("from") or [])]
        parts = [p for p in parts if p]
        if not parts:
            return ""
        base, total = g.get("base"), g.get("total")
        s = "＋".join(parts)
        if base:
            s += "＋%d 金" % base
        return s + (" = %d 金" % total if total else "")

    def pick(major, minor):
        """(改動後的版本, 改動前的版本)。DDragon 早年不是每個 minor 都有（沒有 3.8、3.14…），
        找不到精確版本時：改動後＝第一個比它新的版本、改動前＝最後一個比它舊的版本。"""
        older = [k for k in keys if k < (major, minor)]
        if (major, minor) in last:
            cur = last[(major, minor)]
        else:
            newer = [k for k in keys if k > (major, minor)]
            cur = last[newer[0]] if newer else None
        prev = last[older[-1]] if older else None
        return cur, prev

    out, hit, miss, why = {}, 0, 0, {}
    for (major, minor) in sorted(set(todo) | set(recipes) | set(nolonger)):
        rows = todo.get((major, minor), [])
        n_all = len(rows) + len(recipes.get((major, minor), [])) + len(nolonger.get((major, minor), []))
        cur, prev = pick(major, minor)
        if not cur or not prev:
            print("  %d.%d：DDragon 沒有可比對的版本，跳過（%d 行）" % (major, minor, n_all))
            miss += n_all
            why.setdefault("DDragon 沒有可比對的版本", []).append("%d.%d（%d 行）" % (major, minor, n_all))
            continue
        (An, Ai), (Bn, Bi) = items_of(prev), items_of(cur)
        # ── 「不再提供◯◯。」但沒寫本來多少（2026-07-31 使用者判例：
        #    軍團聖盾 13.10「唯一光環 – 軍團：不再提供物防。」）
        #    先查道具自身屬性（stats），查不到再從前一版的說明文字撈光環數值
        for line, nm, stat in nolonger.get((major, minor), []):
            it_a, it_b = An.get(nm), Bn.get(nm)
            if not it_a:
                miss += 1
                why.setdefault("不再提供：前一版沒有這件道具", []).append("%d.%d %s" % (major, minor, nm))
                continue
            # 「不再給予光環。」整個光環沒了、連內容都沒寫 → 把前一版的光環敘述整段補進來
            #（2026-07-31 使用者：遠古意志「不再給予光環」也是沒寫光環是什麼）
            if stat == "光環":
                desc = re.sub(r"<[^>]+>", " ", it_a.get("description") or "")
                desc = re.sub(r"\s+", " ", desc)
                m0 = re.search(r"(?:唯一)?\s*(?:光環|靈氣)\s*[：:]\s*([^。]{4,80})", desc)
                if not m0:
                    miss += 1
                    why.setdefault("不再提供：DDragon 查不到原本數值", []).append("%d.%d %s 光環" % (major, minor, nm))
                    continue
                p = line.find("｜")
                txt = m0.group(1).strip().rstrip("。.")
                out[line] = line[:p + 1] + re.sub(r"[。.]?\s*$", "", line[p + 1:]) + "（原本：" + txt + "）"
                hit += 1
                print("   %s 光環 → %s" % (nm, txt[:50]))
                continue
            # 講「光環／靈氣」的行不能用道具自身屬性回答：軍團聖盾自己 +20 物防，
            # 但光環給友軍的是 10 → 只從說明文字裡「光環／靈氣」之後那一段找（2026-07-31 判例）
            is_aura = bool(re.search(r"光環|靈氣|aura", line, re.I))
            val = ""
            if not is_aura:
                sa, sb = (it_a.get("stats") or {}), ((it_b or {}).get("stats") or {})
                for k in (STAT_KEY.get(stat) or []):
                    va, vb = num(sa.get(k, 0), k), num(sb.get(k, 0), k)
                    if va and not vb:
                        val = fmt(va) + ("%" if k in PCT else "")
                        break
            if not val:                                   # 光環類：數值只寫在說明文字裡
                desc = re.sub(r"<[^>]+>", " ", it_a.get("description") or "")
                desc = re.sub(r"\s+", " ", desc)
                if is_aura:
                    m0 = re.search(r"(唯一)?\s*(光環|靈氣)", desc)
                    desc = desc[m0.end():] if m0 else ""
                for word in (STAT_DESC.get(stat) or []):
                    m2 = re.search(r"([\d.]+)\s*(%?)\s*點?\s*(?:基礎|額外|最大|總|周圍|友軍的)*\s*" + word, desc)
                    if m2:
                        val = m2.group(1) + m2.group(2)
                        break
                if not val:
                    for pat in (STAT_ALT.get(stat) or []):
                        m2 = re.search(pat, desc)
                        if m2:
                            val = m2.group(1) + (m2.group(2) or "")
                            break
            if not val:
                miss += 1
                why.setdefault("不再提供：DDragon 查不到原本數值", []).append("%d.%d %s %s" % (major, minor, nm, stat))
                continue
            p = line.find("｜")
            body = line[p + 1:]
            new_body = re.sub(r"不再(提供|給予|附帶)[^｜。，,]*[。.]?$", "%s：%s ⇒ 0" % (stat, val), body)
            out[line] = line[:p + 1] + new_body
            hit += 1
            print("   %s %s → %s：%s ⇒ 0" % (nm, stat, stat, val))
        # ── 落單的「新增合成公式：X」（同一張卡沒有「舊合成公式」可配對）：
        #    去前一版 DDragon 撈當時的公式，補成「舊 ⇒ 新」，recipeDir 才判得出方向
        #    （2026-07-31 使用者判例：智慧末刃 13.08「新增合成公式：反曲弓＋抗魔斗篷＋短劍＋700 金 = 2400 金」）
        for line, nm in recipes.get((major, minor), []):
            it = An.get(nm)
            if not it:
                miss += 1
                why.setdefault("合成公式：前一版沒有這件道具", []).append("%d.%d %s" % (major, minor, nm))
                continue
            old_r = recipe_of(it, Ai)
            if not old_r:
                miss += 1
                why.setdefault("合成公式：前一版沒有合成路徑", []).append("%d.%d %s" % (major, minor, nm))
                continue
            p = line.find("｜")
            body = line[p + 1:]
            new_r = re.sub(r"^\s*新增合成公式[：:]\s*", "", body).rstrip("。.")
            if clean_recipe(old_r) == clean_recipe(new_r):
                miss += 1
                why.setdefault("合成公式：前後版一樣", []).append("%d.%d %s" % (major, minor, nm))
                continue
            out[line] = line[:p + 1] + "合成公式：" + old_r + " ⇒ " + new_r
            hit += 1
            print("   %s 合成公式 → %s ⇒ %s" % (nm, old_r, new_r))
        for line, nm in rows:
            a, b = (An.get(nm) or {}).get("stats"), (Bn.get(nm) or {}).get("stats")
            if nm not in An or nm not in Bn:
                miss += 1
                why.setdefault("道具名對不到 DDragon", []).append("%d.%d %s" % (major, minor, nm))
                continue
            diff = []
            for k in sorted(set(a) | set(b), key=lambda x: STAT_ZH.get(x, "zz")):
                zh = STAT_ZH.get(k)
                if not zh:
                    continue
                va, vb = num(a.get(k, 0), k), num(b.get(k, 0), k)
                if abs(va - vb) < 1e-9:
                    continue
                unit = "%" if k in PCT else ""
                diff.append("%s：%s%s ⇒ %s%s" % (zh, fmt(va), unit, fmt(vb), unit))
            if not diff:
                miss += 1
                why.setdefault("DDragon 前後版屬性完全沒變", []).append("%d.%d %s" % (major, minor, nm))
                continue
            # 保留 wiki 原文（那是改完後的完整屬性表），後面附上「真正有變動的項目」。
            # 直接改寫會跟原文打架：wiki 的魔力回復是每 5 秒、DDragon 是每秒，單位不同。
            out[line] = line.rstrip("。.") + "。（與上一版相比：" + "；".join(diff) + "）"
            hit += 1
            print("   %s → %s" % (nm, "；".join(diff)))
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("window.ITEM_STAT_FIX=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";")
    print("")
    print("OK item_stat_fix.js：補到 %d 行、補不到 %d 行" % (hit, miss))
    for k, v in why.items():
        print("   補不到（%s）%d 筆：%s" % (k, len(v), "、".join(v[:8])))


if __name__ == "__main__":
    main()
