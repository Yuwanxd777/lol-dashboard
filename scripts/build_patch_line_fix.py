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
    #    使用者定案 2026-08-01：新舊版不要分兩行，直接寫成「舊版的 ⇒ 新版的」
    ("3.10", "MasterYi", "舊：", "主動：易大師閃現至目標敵人身上",
     "先聲奪人｜主動：閃現至目標敵人身上，對該目標與周圍最多三名敵人造成 "
     "100 / 150 / 200 / 250 / 300（+100% AP）魔傷，對小兵與野怪有 50% 機率造成額外傷害"
     "（對野怪 260 / 320 / 380 / 440 / 500）；期間無法被指定，結束後出現在最初目標的位置 "
     "⇒ 變為無法被指定並衝刺穿過 4 個單位，對每個目標造成 25 / 60 / 95 / 130 / 165"
     "（+100% AD）物傷，對小兵額外造成 75 / 100 / 125 / 150 / 175 傷害，且可暴擊"
     "（暴擊造成 160% 傷害）"),
    ("3.10", "MasterYi", "New:", "先聲奪人的冷卻時間降低",
     "先聲奪人｜新增：易大師每次普攻可讓先聲奪人的冷卻時間減少 1 秒。"),
    ("3.10", "MasterYi", "New:", "主動：易大師變為不可被指定", ""),
    ("3.10", "MasterYi", "Old:", "魔法傷害：100 / 150 / 200 / 250 / 300", ""),
    ("3.10", "MasterYi", "Old:", "額外傷害對野怪", ""),

    ("3.10", "MasterYi", "舊：", "主動：易大師引導 5 秒",
     "冥想｜主動：引導 5 秒，期間獲得額外物防／魔防 100 / 150 / 200 / 250 / 300 與"
     "每秒生命回復 40 / 70 / 100 / 130 / 160（+40% AP），最大治療 "
     "200 / 350 / 500 / 650 / 800（+200% AP） ⇒ 引導 4 秒，獲得 "
     "40% / 45% / 50% / 55% / 60% 傷害減免，並每秒回復 30 / 50 / 70 / 90 / 110"
     "（+0.3 魔攻）生命"),
    ("3.10", "MasterYi", "新增：", "易大師每損失 1% 生命值",
     "冥想｜新增：易大師每損失 1% 生命，治療量便提升 1%；對防禦塔的傷害減免減半。"),
    ("3.10", "MasterYi", "新增：", "易大師引導 4 秒", ""),
    ("3.10", "MasterYi", "Old:", "額外物防", ""),
    ("3.10", "MasterYi", "Old:", "額外生命值回復每秒", ""),
    ("3.10", "MasterYi", "Old:", "最大治療", ""),

    ("3.10", "MasterYi", "Old:", "被動：易大師獲得 15",
     "無極劍道｜被動：易大師獲得 15 / 20 / 25 / 30 / 35 物攻 ⇒ 7% / 9% / 11% / 13% / 15% 物攻"),
    ("3.10", "MasterYi", "舊：", "主動：持續 10 秒",
     "無極劍道｜主動：持續 10 秒，獲得相當於被動加成兩倍的額外物攻 ⇒ 攻擊特效造成 "
     "10 / 15 / 20 / 25 / 30（+0.1 / 0.125 / 0.15 / 0.175 / 0.2 總物攻）真實傷害，持續 5 秒；"
     "技能在冷卻中時會失去被動加成"),
    ("3.10", "MasterYi", "New:", "被動：易大師獲得 7%", ""),
    ("3.10", "MasterYi", "新增：", "主動：易大師的攻擊特效", ""),

    ("3.10", "MasterYi", "舊：", "主動：持續數秒",
     "高原血統｜主動：持續 8 / 10 / 12 秒，獲得 40% 額外移速、40% / 60% / 80% 額外攻速與"
     "移速減速免疫（仍會受其他群體控制影響）；期間擊殺英雄重置所有技能冷卻、助攻重置基本技能一半冷卻 "
     "⇒ 持續 10 秒，獲得 30% / 55% / 80% 攻速與 20% / 32.5% / 45% 移速；"
     "期間取得擊殺或助攻可延長 4 秒"),
    ("3.10", "MasterYi", "新增：", "被動：當易大師擊殺英雄時",
     "高原血統｜新增：被動 - 易大師擊殺英雄時，其基本技能的冷卻時間縮短 18 秒（助攻減半）。"),
    ("3.10", "MasterYi", "新增：", "主動：提供易大師 30%", ""),
    ("3.10", "MasterYi", "Old:", "提高攻擊速度", ""),
    ("3.10", "MasterYi", "Old:", "持續時間：8 / 10 / 12 秒", ""),

    ("3.10", "MasterYi", "雙重打擊", "舊版：在 7 次普攻後",
     "雙重打擊｜觸發方式：7 次普攻後的下一次攻擊會對目標攻擊兩次（若第一擊未擊殺目標），"
     "第二擊會觸發攻擊特效並可暴擊 ⇒ 每連續第 4 次普攻會攻擊兩次，第二擊造成 50% 傷害"),
    ("3.10", "MasterYi", "雙重打擊", "新版：易大師每連續第 4 次", ""),

    # ── 枷蘿：兩種植物的名字沒翻（2026-08-01 使用者點名）──────────────────
    ("3.7", "Zyra", "荊棘鞭笞", "新增：Thorn Spitter 與 Vine Lasher",
     "荊棘鞭笞｜新增：荊棘吐刺者與藤蔓鞭笞者"
     "可受指揮旗幟的軍團效果加成。"),

    # ── 特朗德 3.6 重做：機翻語序（2026-08-01 使用者點名）────────────────
    ("3.6", "Trundle", "Rabid Bite", "現在緩速目標 75%",
     "狂野撕咬｜新增：命中時緩速目標 75%，持續 0.1 秒。"),
    ("3.6", "Trundle", "Rabid Bite", "動畫速度隨特朗德",
     "狂野撕咬｜動畫速度改為隨特朗德的攻擊速度調整。"),
    ("3.6", "Trundle", "Contaminate", "現在給予 8",
     "極凍領地｜新增：提高特朗德 8 / 11 / 14 / 17 / 20% 的治療量。"),

    # ── 希維爾 3.6：wiki 把被動的改動掛在 Q 底下，而且主詞漏譯（2026-08-01 使用者點名）
    #    原文 Fleet of Foot: Now also grants its effect when Boomerang Blade and Ricochet
    #    hit enemy champions.
    ("3.6", "Sivir", "迴旋之刃", "新增：觸發當迴旋之刃且十字彈射",
     "戰鬥動能｜新增：迴旋之刃與十字彈射命中敵方英雄時也會觸發。"),

    # ── 希維爾 3.13：兩行講同一件事（彈跳規則）→ 併成「舊 ⇒ 新」───────────
    ("3.13", "Sivir", "十字彈射", "已移除：最大彈跳次數",
     "十字彈射｜彈跳命中規則：同一敵人可被重複命中（無最大彈跳次數上限） ⇒ 每個敵人僅能被命中一次"),
    ("3.13", "Sivir", "十字彈射", "新增：敵人可僅命中一次", ""),

    # ── 勒布朗：模仿版的技能改動要併回原技能（使用者指定寫在 QWE 一起）─────
    ("3.9", "Leblanc", "模仿：沉默封印", "模仿：沉默封印於標記時",
     "沉默封印｜模仿：於標記時與引爆時各造成 100 / 200 / 300（+65% AP）傷害。"),
    ("3.9", "Leblanc", "模仿：移行瞬影", "模仿：移行瞬影於命中時",
     "移行瞬影｜模仿：於命中時造成 150 / 300 / 450（+97.5% AP）傷害。"),
    ("3.9", "Leblanc", "模仿：移形換影", "冷卻時間：返回傳送點後",
     "移行瞬影｜模仿：冷卻時間：返回傳送點後 ⇒ 施放時"),
    ("3.9", "Leblanc", "模仿：幻影鎖鍊", "模仿：幻影鎖鍊於標記時",
     "幻影鎖鍊｜模仿：於標記時與定身時各造成 100 / 200 / 300（+65% AP）傷害。"),

    # ── 2026-08-01 全面稽核補：其餘還掛著 New:/Old:/舊： 前綴或機翻破碎的行 ──
    # 婕莉 12.23 大絕重做（8 行 → 4 行「舊 ⇒ 新」）
    ("12.23", "Zeri", "新增：", "175 / 275 / 375",
     "雷霆萬鈞｜爆發傷害：150 / 250 / 350（+80% 額外 AD）（+80% AP）魔傷 "
     "⇒ 175 / 275 / 375（+100% 額外 AD）（+110% AP）魔傷"),
    ("12.23", "Zeri", "舊：", "150 / 250 / 350", ""),
    ("12.23", "Zeri", "新增：", "持續 5 秒",
     "雷霆萬鈞｜過載持續時間：6 ⇒ 5 秒；期間對敵人造成傷害可延長 1.5 秒（最多延長至原本的持續時間）"),
    ("12.23", "Zeri", "舊：", "持續 6 秒", ""),
    ("12.23", "Zeri", "激電連彈 3", "650 單位",
     "雷霆萬鈞｜超載強化的激電連彈：對第一個目標與 450 單位內最近的可見敵人連鎖（最多 4 個），"
     "並附帶 5 / 10 / 15（+15% AP）額外魔傷 ⇒ 連鎖範圍擴大至 650 單位（最多 4 個）、移除額外魔傷；"
     "超載期間另新增 10% 額外移動速度（原本僅 30% 額外攻速）"),
    ("12.23", "Zeri", "激電連彈 3", "450 單位", ""),
    ("12.23", "Zeri", "普攻 2", "持續 1.5 秒",
     "雷霆萬鈞｜超載層數：每層 0.5% 額外移速並延長超載 2 秒（雷霆萬鈞命中一次 8 層） "
     "⇒ 每層 0.5% 額外移速僅持續 1.5 秒、不再延長超載（技能爆擊 3 層；激電連彈僅第一個命中目標產生層數）"),
    ("12.23", "Zeri", "普攻 2", "8 層", ""),
    # 卡莎碧雅 26.01 被動重做（3 行 → 1 行）
    ("26.01", "Cassiopeia", "新增：", "提升 6%",
     "致命節奏｜移速機制：獲得 4 – 72（依等級）額外移速、無法購買鞋子"
     "（諾克薩斯祝福：額外移速再 +1 – 18，總計 5 – 90） "
     "⇒ 改為將所有移動速度加成的效果提升 6% – 40%（依等級）"),
    ("26.01", "Cassiopeia", "舊：", "4 – 72", ""),
    ("26.01", "Cassiopeia", "舊：", "諾克薩斯祝福", ""),
    # 菲歐拉 25.14 的舊版數值補充
    ("25.14", "Fiora", "頂尖對決", "舊版：先前每秒回復",
     "頂尖對決｜（舊版數值）每秒回復：30 – 75 / 40 – 100 / 50 – 125"
     "（依命中的弱點數與技能等級）（+24% – 60% 額外物攻）生命。"),
    # 珍娜 15.04 被動生效對象（機翻破碎）
    ("5.4", "Janna", "順風而行", "其範圍",
     "順風而行｜額外移動速度的生效對象：範圍內所有友軍 ⇒ 正在朝珍娜移動的友軍"),
    # 達瑞斯 5.16：前綴被寫成英文句子（Now deals Physical damage from Magic.）
    ("5.16", "Darius", "Now deals Physical damage from Magic.", "每層傷害",
     "絞喉｜每層傷害：12 – 36（依等級）魔傷 ⇒ 9 +（每等級 1），即 10 – 27（依等級）物傷"),
    ("5.16", "Darius", "Now deals Physical damage from Magic.", "總傷害",
     "絞喉｜總傷害：60 – 180（依等級）魔傷 ⇒ 45 +（每等級 5），即 50 – 135（依等級）物傷（額外 AD 係數不變）"),
    ("5.16", "Darius", "Now deals Physical damage from Magic.", "係數不變", ""),
    # 卡力斯 4.9 的孤兒 %（缺數字）
    ("4.9", "Khazix", "Evolved Enlarged Claws", "已移除：% 目標已損失生命的",
     "孤獨的恐懼｜強化後 - 已移除：依目標已損失生命百分比的額外傷害。"),
    # 魔提斯深淵 13.09：原文 Passive attack damage increased to 1 per 2% of missing
    # health from 2.5%.（由「已損失生命的 2.5%」改成「每 2% 已損失生命給 1 點」）
    ("13.09", None, "魔提斯深淵", "被動物攻：2.5% ⇒ 1 每 2%",
     "魔提斯深淵｜被動物攻：已損失生命的 2.5% ⇒ 每 2% 已損失生命提供 1 點物攻"),
    # 達瑞文 3.11：機翻語序（現在給予基礎 50 金錢額外於擊殺敵方英雄從 0）
    ("3.11", "Draven", "瑞文聯盟", "現在給予基礎 50 金錢額外於擊殺",
     "瑞文聯盟｜擊殺敵方英雄的基礎額外金錢：0 ⇒ 50"),
    # 16.12 標記／衝刺：章節標記「New：」寫在內容開頭
    ("16.12", None, "標記／衝刺", "New：加入發光效果",
     "標記／衝刺｜新增：加入發光效果，使雪球更明顯。"),
    # 16.01 芮蘭颶風箭：er／cr 是程式碼裡的參數名（effect radius／cast radius）
    ("16.01", None, "芮蘭颶風箭", "次要箭矢現在使用 er 而非 cr",
     "芮蘭颶風箭｜次要箭矢的判定改用效果半徑，而非施放半徑。"),
    # 26.14 亞歐幹的標題梗（On-Hit? More Like On-Destroy）
    ("26.14", "Azir", None, "On-Hit? More Like On-Destroy",
     "砂兵｜灼燒、蘭德里的苦楚、黑燚火炬與海克斯科技交流器現在會在擊中時造成 100% 傷害，而非 50%"),
    # 肯能 4.21 機翻語序（前綴不固定 → None＝任意前綴）
    ("4.21", "Kennen", None, "相同目標超過一次",
     "雷霆風暴｜新增：每 0.5 秒最多只能命中同一目標一次。"),
]


# 進化／強化版技能的行 → 歸回本體技能，內容前面標「強化後」
#（2026-08-01 使用者：Evolved Enlarged Claws 是強化的 Q，要列在 Q 底下）
# 卡力斯四顆技能的進化版在 wiki 上被當成獨立技能名，中英文寫法都有
EVOLVE = {
    "Khazix": {
        "孤獨的恐懼": ["Evolved Enlarged Claws", "進化巨爪", "進化巨型利爪", "進化利爪", "進化死神之爪"],
        "虛空尖刺": ["Evolved Spike Racks", "進化尖刺陣", "進化尖刺", "進化尖刺彈幕"],
        "掠翅飛躍": ["Evolved Wings", "進化之翼", "進化翅膀"],
        "虛空突襲": ["Evolved Active Camouflage", "Evolved Adaptive Cloaking",
                     "進化主動隱蔽", "進化活性迷彩", "進化主動迷彩"],
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


# wiki_extra（道具／符文／召技／機制區）的重寫：
#   (版本或"*", 分區或"*", 原前綴, 內容片段 或 None, 新內容)
#   ‧ 片段為 None ＝「改名模式」：該前綴的每一行都把前綴換成新名（body 不動）
#   ‧ 片段為字串 ＝ 整行重寫（"" ＝ 該行不顯示）
EXTRA = [

    ("14.03", "道具", "靈魂 Stone, 靈魂 Ancient Golem, 靈魂 Elder Lizard 且靈魂 Spectral Wraith",
     None, "靈魂石系列"),
    ("15.01", "道具", "道具 exchanges （utility）", None, "通用道具調整"),
    # 18.x 符文樹卡名（Trait: X）→ 現行譯名
    ("*", "符文", "Trait: Domination", None, "主宰系"),
    ("*", "符文", "Trait: Precision", None, "精密系"),
    ("*", "符文", "Trait: Sorcery", None, "巫術系"),
    ("*", "符文", "Trait: Resolve", None, "堅毅系"),
    ("*", "符文", "Trait: Inspiration", None, "啟迪系"),
    # 卡名是英文或機翻句子（2026-08-01 稽核最後一批）
    ("18.07", "道具", "Circlet Iron Solari 且 Locket Iron Solari", None, "日輪頭冠與日輪的神環"),
    ("22.01", "召喚師技能", "Unleashed Teleport - 新增召喚師技能", None, "強化傳送"),
    ("14.06", "道具", "道具 availability needs updating. Blackfire Torch", None, "黑焰火炬"),
    ("15.01", "符文", "Tier 1 且 2 runes 現在僅 offered 其主要類型：", None, "第 1／2 階符文"),
    ("15.02", "道具", "Devourer／劍聖／Magus／Warrior", None, "附魔：吞噬者／劍聖／賢者／戰士"),
    ("15.24", "道具", "潛行守衛／真視守衛／Farsight 守衛", None, "潛行守衛／真視守衛／遠見守衛"),
    # 機制區的機翻卡名（2026-08-01 稽核）
    ("*", "機制", "攻擊且技能 Queueing", None, "普攻與技能的指令佇列"),
    ("*", "機制", "League 客戶端更新", None, "客戶端更新"),
    ("*", "機制", "守衛 Reveal Rewards", None, "守衛顯現獎勵"),
    ("*", "機制", "飛龍 Slayer", None, "屠龍者"),
    ("*", "*", "飛龍 Slayer", None, "屠龍者"),
    ("*", "*", "Hand 巴龍", None, "巴龍之手"),
    ("*", "*", "Altars", None, "祭壇"),
]


# 「群組卡名｜道具名」的行要翻轉成「道具名｜敘述」——wiki 把一批道具塞在同一張卡底下，
# 畫面上就變成一張卡列了一串道具名，看不出各自發生什麼事（2026-08-01 使用者指定一個一個列）
FLIP = [
    ("following 道具移除從遊戲", "已從遊戲中移除。"),
    ("following 道具 remade（移除）", "重做上線，原版本已移除。"),
    ("Enabled:", "重新啟用。"),
    ("following 圖示更新：", "圖示更新。"),
    ("following Chromas packs 新增 store：", "新增炫彩造型組。"),
]


def flip_rules(EX):
    """群組卡 → 每個項目自己一張卡"""
    out = {}
    for secs in EX.values():
        if not isinstance(secs, dict):
            continue
        for arr in secs.values():
            if not isinstance(arr, list):
                continue
            for line in arr:
                i = line.find("｜")
                if i <= 0:
                    continue
                pre, body = line[:i].strip(), line[i + 1:].strip()
                for p, txt in FLIP:
                    if pre == p and body:
                        out[line] = body + "｜" + txt
                        break
    return out


def load_js(fname, varname):
    p = os.path.join(ROOT, fname)
    s = io.open(p, encoding="utf-8").read()
    i = s.index("=", s.index(varname))
    return json.loads(s[i + 1:s.rindex("}") + 1])


def load_patches():
    return load_js("wiki_patches.js", "window.WIKI_PATCHES")


def main():
    WP = load_patches()
    out, miss, used = {}, [], set()
    EXj = load_js("wiki_extra.js", "window.WIKI_EXTRA")
    for ver, cid, pre, frag, new in FIX:
        if cid is None:                      # 道具／機制區（wiki_extra）
            arr = [l for a in (EXj.get(ver) or {}).values() if isinstance(a, list) for l in a]
        else:
            arr = (WP.get(ver) or {}).get(cid) or []
        hit = None
        for line in arr:
            if line in used:
                continue
            i = line.find("｜")
            if i <= 0:
                continue
            if pre is not None and line[:i].strip() != pre:
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
    # wiki_extra 的重寫（applyPatchLineFix 現在也會套到 WIKI_EXTRA）
    EX = load_js("wiki_extra.js", "window.WIKI_EXTRA")
    fl = flip_rules(EX)
    for k, v in fl.items():
        out.setdefault(k, v)
    print("   群組卡翻轉：%d 行" % len(fl))
    ex_hit = 0
    for pk0, cat0, pre, frag, new in EXTRA:
        for pk, secs in EX.items():
            if pk0 != "*" and pk != pk0:
                continue
            if not isinstance(secs, dict):
                continue
            for cat, arr in secs.items():
                if cat0 != "*" and cat != cat0:
                    continue
                if not isinstance(arr, list):
                    continue
                for line in arr:
                    i = line.find("｜")
                    if i <= 0 or line[:i].strip() != pre:
                        continue
                    if frag is None:                     # 改名模式
                        out.setdefault(line, new + "｜" + line[i + 1:])
                        ex_hit += 1
                    elif frag in line[i + 1:]:
                        out.setdefault(line, new)
                        ex_hit += 1
    print("   wiki_extra 重寫：%d 行" % ex_hit)
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("// 版本改動行的人工重寫（scripts/build_patch_line_fix.py 產生，勿手改）" + chr(10))
        f.write("window.PATCH_LINE_FIX=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";")
    print("OK patch_line_fix.js：%d 行重寫" % len(out))
    for m in miss:
        print("   對不到原行：" + m)


if __name__ == "__main__":
    main()
