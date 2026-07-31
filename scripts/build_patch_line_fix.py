# -*- coding: utf-8 -*-
"""產生 patch_line_fix.js（window.PATCH_LINE_FIX）＝wiki 改動行的**人工重寫表**。

為什麼要這份（2026-07-31 使用者指定重寫索娜／易大師／勒布朗的 2013 資料）：
  wiki 早年的中文頁有三種毛病，靠通用規則救不回來——
  ① 技能名欄位寫成「New:／Old:／舊：／新增：」，根本不是技能名，畫面上就變成一堆
     沒有歸屬的區塊（易大師 3.10 大重做整整 20 行都這樣）
  ② 內容夾雜英文（Staccato／Diminuendo／Tempo）或機翻語序
  ③ 同一顆技能被拆成兩個名字（勒布朗「模仿：沉默封印」應該併回「沉默封印」）

做法：人工寫「(版本, 原技能名, 內容開頭片段) → 重寫後的整行」，腳本去 wiki_patches.js
把原行全文撈出來當 key，輸出 {原行: 新行}。顯示層在資料載入後套用（見 index.html）。
改的是顯示，不動 wiki_patches.js 本身，重抓 wiki 不會覆蓋這份。

用法：python scripts\\build_patch_line_fix.py
"""
import io, json, os, re, sys

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "patch_line_fix.js")

# (版本, 英雄id, 原技能名, 內容開頭片段) → 重寫後的整行（"" ＝ 這行不要顯示）
FIX = [
    # ── 索娜：力量和絃的三種和絃名沒翻（音樂術語）──────────────────────────
    # 三種和絃是同一件事（各自加了 AP 加成）→ 併成一行，後兩行不再單獨列
    ("3.14", "Sona", "力量和絃", "新增：Staccato",
     "力量和絃｜新增：三種和絃各自獲得 AP 加成——斷奏（+20% AP）、"
     "漸弱（每 100 AP +2%）、節拍（每 100 AP +4%）。"),
    ("3.14", "Sona", "力量和絃", "新增：Diminuendo", ""),
    ("3.14", "Sona", "力量和絃", "新增：Tempo", ""),
    ("3.8", "Sona", "力量和絃", "Diminuendo 持續時間",
     "力量和絃｜漸弱持續時間：4 ⇒ 3 秒"),
    ("3.8", "Sona", "堅毅詠嘆調", "光環額外雙抗光環",     # 「光環」重複了兩次
     "堅毅詠嘆調｜光環額外雙抗：3 / 6 / 9 / 12 / 15 ⇒ 6 / 7 / 8 / 9 / 10"),
    ("3.02", "Sona", "力量和絃", "已移除：力量和絃消耗當",
     "力量和絃｜已移除：攻擊守衛時會消耗力量和絃。"),

    # ── 易大師 3.10 大重做：New:／Old:／舊：／新增： 全部歸回正確技能 ──────
    ("3.10", "MasterYi", "New:", "主動：易大師變為不可被指定",
     "先聲奪人｜新版 - 主動：易大師變為無法被指定並衝刺穿過 4 個單位，對每個目標造成 "
     "25 / 60 / 95 / 130 / 165（+100% AD）物傷，對小兵額外造成 75 / 100 / 125 / 150 / 175 傷害。"
     "先聲奪人可以暴擊，暴擊時造成 160% 傷害。"),
    ("3.10", "MasterYi", "New:", "先聲奪人的冷卻時間降低",
     "先聲奪人｜新版 - 易大師每次普攻可讓先聲奪人的冷卻時間減少 1 秒。"),
    ("3.10", "MasterYi", "舊：", "主動：易大師閃現至目標敵人身上",
     "先聲奪人｜舊版 - 主動：易大師閃現至目標敵人身上，對該目標與周圍小範圍內最多三名敵人造成魔傷，"
     "並有 50% 機率對小兵與野怪造成額外傷害。先聲奪人期間易大師無法被指定，結束後會出現在最初目標的位置；"
     "若最初目標在結束前死亡，易大師則回到原本的位置。"),
    ("3.10", "MasterYi", "Old:", "魔法傷害：100 / 150 / 200 / 250 / 300",
     "先聲奪人｜舊版 - 魔傷：100 / 150 / 200 / 250 / 300（+100% AP）"),
    ("3.10", "MasterYi", "Old:", "額外傷害對野怪",
     "先聲奪人｜舊版 - 對野怪的額外傷害：260 / 320 / 380 / 440 / 500"),
    ("3.10", "MasterYi", "新增：", "易大師引導 4 秒",
     "冥想｜新版 - 主動：易大師引導 4 秒，獲得 40% / 45% / 50% / 55% / 60% 傷害減免，"
     "並每秒回復 30 / 50 / 70 / 90 / 110（+0.3 魔攻）生命。"),
    ("3.10", "MasterYi", "新增：", "易大師每損失 1% 生命值",
     "冥想｜新版 - 易大師每損失 1% 生命，治療量便提升 1%；對防禦塔的傷害減免減半。"),
    ("3.10", "MasterYi", "舊：", "主動：易大師引導 5 秒",
     "冥想｜舊版 - 主動：易大師引導 5 秒，期間獲得額外物防、魔防與生命回復；"
     "引導開始時與結束時（若完整引導滿 5 秒）各回復一次生命。"),
    ("3.10", "MasterYi", "Old:", "額外物防",
     "冥想｜舊版 - 額外物防／魔防：100 / 150 / 200 / 250 / 300"),
    ("3.10", "MasterYi", "Old:", "額外生命值回復每秒",
     "冥想｜舊版 - 每秒額外生命回復：40 / 70 / 100 / 130 / 160（+40% AP）"),
    ("3.10", "MasterYi", "Old:", "最大治療",
     "冥想｜舊版 - 最大治療：200 / 350 / 500 / 650 / 800（+200% AP）"),
    ("3.10", "MasterYi", "New:", "被動：易大師獲得 7%",
     "無極劍道｜新版 - 被動：易大師獲得 7% / 9% / 11% / 13% / 15% 物攻。"),
    ("3.10", "MasterYi", "新增：", "主動：易大師的攻擊特效",
     "無極劍道｜新版 - 主動：易大師的攻擊特效造成 10 / 15 / 20 / 25 / 30"
     "（+0.1 / 0.125 / 0.15 / 0.175 / 0.2 總物攻）真實傷害，持續 5 秒；"
     "技能在冷卻中時會失去無極劍道的被動加成。"),
    ("3.10", "MasterYi", "Old:", "被動：易大師獲得 15",
     "無極劍道｜舊版 - 被動：易大師獲得 15 / 20 / 25 / 30 / 35 物攻。"),
    ("3.10", "MasterYi", "舊：", "主動：持續 10 秒",
     "無極劍道｜舊版 - 主動：持續 10 秒，易大師獲得相當於被動加成兩倍的額外物攻。"),
    ("3.10", "MasterYi", "新增：", "被動：當易大師擊殺英雄時",
     "高原血統｜新版 - 被動：易大師擊殺英雄時，其基本技能的冷卻時間縮短 18 秒（助攻減半）。"),
    ("3.10", "MasterYi", "新增：", "主動：提供易大師 30%",
     "高原血統｜新版 - 主動：易大師獲得 30% / 55% / 80% 攻速與 20% / 32.5% / 45% 移速，持續 10 秒；"
     "期間取得擊殺或助攻可延長持續時間 4 秒。"),
    ("3.10", "MasterYi", "舊：", "主動：持續數秒",
     "高原血統｜舊版 - 主動：持續數秒，易大師獲得 40% 額外移速、額外攻速，"
     "以及移速減速免疫（仍會受其他群體控制影響）；期間擊殺英雄會重置所有技能冷卻，"
     "助攻則重置基本技能一半的冷卻。"),
    ("3.10", "MasterYi", "Old:", "提高攻擊速度",
     "高原血統｜舊版 - 攻速加成：40% / 60% / 80%"),
    ("3.10", "MasterYi", "Old:", "持續時間：8 / 10 / 12 秒",
     "高原血統｜舊版 - 持續時間：8 / 10 / 12 秒"),
    ("3.10", "MasterYi", "雙重打擊", "新版：易大師每連續第 4 次",
     "雙重打擊｜新版 - 易大師每連續第 4 次普攻會攻擊兩次，第二擊造成 50% 傷害。"),
    ("3.10", "MasterYi", "雙重打擊", "舊版：在 7 次普攻後",
     "雙重打擊｜舊版 - 在 7 次普攻後，易大師的下一次攻擊會對目標攻擊兩次（若第一擊未擊殺目標）；"
     "第二擊會觸發攻擊特效（含雙重打擊自身的計數），且可造成暴擊。"),

    # ── 枷蘿：兩種植物的名字沒翻（2026-08-01 使用者點名）──────────────────
    ("3.7", "Zyra", "荊棘鞭笞", "新增：Thorn Spitter 與 Vine Lasher",
     "荊棘鞭笞｜新增：荊棘吐刺者與藤蔓鞭笞者"
     "可受指揮旗幟的軍團效果加成。"),

    # ── 勒布朗：模仿版的技能改動要併回原技能（使用者指定寫在 QWE 一起）─────
    ("3.9", "Leblanc", "模仿：沉默封印", "模仿：沉默封印於標記時",
     "沉默封印｜模仿：於標記時與引爆時各造成 100 / 200 / 300（+65% AP）傷害。"),
    ("3.9", "Leblanc", "模仿：移行瞬影", "模仿：移行瞬影於命中時",
     "移行瞬影｜模仿：於命中時造成 150 / 300 / 450（+97.5% AP）傷害。"),
    ("3.9", "Leblanc", "模仿：移形換影", "冷卻時間：返回傳送點後",
     "移行瞬影｜模仿：冷卻時間：返回傳送點後 ⇒ 施放時"),
    ("3.9", "Leblanc", "模仿：幻影鎖鍊", "模仿：幻影鎖鍊於標記時",
     "幻影鎖鍊｜模仿：於標記時與定身時各造成 100 / 200 / 300（+65% AP）傷害。"),
]


# 進化／強化版技能的行 → 歸回本體技能，內容前面標「強化後」
#（2026-08-01 使用者：Evolved Enlarged Claws 是強化的 Q，要列在 Q 底下）
# 卡力斯四顆技能的進化版在 wiki 上被當成獨立技能名，中英文寫法都有
EVOLVE = {
    "Khazix": {
        "孤獨的恐懼": ["Evolved Enlarged Claws", "進化巨爪", "進化巨型利爪", "進化利爪"],
        "虛空尖刺": ["Evolved Spike Racks", "進化尖刺陣", "進化尖刺"],
        "掠翅飛躍": ["Evolved Wings", "進化之翼", "進化翅膀"],
        "虛空突襲": ["Evolved Active Camouflage", "Evolved Adaptive Cloaking",
                     "進化主動隱蔽", "進化活性迷彩"],
    },
}


def evolve_rules(WP):
    """掃全部版本，把進化版技能名的行改寫成「本體技能｜強化後…」"""
    out = {}
    for cid, mp in EVOLVE.items():
        alias = {a: main for main, arr in mp.items() for a in arr}
        for cs in WP.values():
            arr = (cs or {}).get(cid)
            if not isinstance(arr, list):
                continue
            for line in arr:
                i = line.find("｜")
                if i <= 0:
                    continue
                main = alias.get(line[:i].strip())
                if not main:
                    continue
                body = line[i + 1:].strip()
                # 「新增：…」這種本身就有冒號的，用「強化後 - 」接才通順
                body = ("強化後 - " + body) if re.match(r"^(新增|已移除|移除|舊版|新版)[：:]", body)                     else ("強化後" + body)
                out[line] = main + "｜" + body
    return out


def load_patches():
    p = os.path.join(ROOT, "wiki_patches.js")
    s = io.open(p, encoding="utf-8").read()
    i = s.index("=", s.index("window.WIKI_PATCHES"))
    return json.loads(s[i + 1:s.rindex("}") + 1])


def main():
    WP = load_patches()
    out, miss, used = {}, [], set()
    for ver, cid, pre, frag, new in FIX:
        arr = (WP.get(ver) or {}).get(cid) or []
        hit = None
        for line in arr:
            if line in used:
                continue
            i = line.find("｜")
            if i <= 0:
                continue
            if line[:i].strip() != pre:
                continue
            if frag not in line[i + 1:]:
                continue
            hit = line
            break
        if not hit:
            miss.append("%s %s %s｜%s" % (ver, cid, pre, frag))
            continue
        used.add(hit)
        out[hit] = new
    for k, v in evolve_rules(WP).items():
        out.setdefault(k, v)
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("// 版本改動行的人工重寫（scripts/build_patch_line_fix.py 產生，勿手改）" + chr(10))
        f.write("window.PATCH_LINE_FIX=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";")
    print("OK patch_line_fix.js：%d 行重寫" % len(out))
    for m in miss:
        print("   對不到原行：" + m)


if __name__ == "__main__":
    main()
