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


def main():
    EX = load_extra()
    # 1) 收集需要補值的行
    #    todo    ＝「屬性：a, b, c。」只寫改完後、沒寫改動前
    #    recipes ＝「新增合成公式：X」而同一張卡沒有「舊合成公式」可配對
    todo, recipes = {}, {}
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
    print("需要補前後值的行：屬性 %d 行、落單合成公式 %d 行（涉及 %d 個版本）"
          % (sum(len(v) for v in todo.values()), sum(len(v) for v in recipes.values()),
             len(set(todo) | set(recipes))))
    if not todo and not recipes:
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

    out, hit, miss, why = {}, 0, 0, {}
    for (major, minor) in sorted(set(todo) | set(recipes)):
        rows = todo.get((major, minor), [])
        if (major, minor) not in last:
            n2 = len(rows) + len(recipes.get((major, minor), []))
            print("  %d.%d：DDragon 沒有這個版本，跳過（%d 行）" % (major, minor, n2))
            miss += n2
            why.setdefault("DDragon 沒有這個版本", []).append("%d.%d（%d 行）" % (major, minor, len(rows)))
            continue
        cur = last[(major, minor)]
        i = keys.index((major, minor))
        prev = last[keys[i - 1]] if i > 0 else None
        if not prev:
            miss += len(rows) + len(recipes.get((major, minor), []))
            continue
        (An, Ai), (Bn, Bi) = items_of(prev), items_of(cur)
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
