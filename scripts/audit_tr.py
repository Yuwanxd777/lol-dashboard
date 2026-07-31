# -*- coding: utf-8 -*-
"""校閱 manual_tr.json：詞彙規範/標點/殘留英文/空泛翻譯"""
import io, sys, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import os
_HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(_HERE, "manual_tr.json"), encoding="utf-8"))
print("總條數:", len(d))

probs = {"屬性未簡稱": [], "半形標點": [], "殘留英文": [], "空泛/缺主詞": [], "簡體字": []}
ALLOW = re.compile(r"(?<![A-Za-z])(AP|AD|HP|MP|MS|CD|CS|XP|DPM|KDA|BUFF|ARAM|ARURF|URF|VS|G|Lv|LV|[QWERXV]\d?)(?![A-Za-z])", re.I)
SIMP = "体术胜负后种战应对经维护务优败伤挡药剂宝团队长风脉冲级击杀锁链闪电动画视觉设计变换调整状态".translate(str.maketrans("", "", "術勝負後種戰應對經維護務優敗傷擋藥劑寶團隊長風脈衝級擊殺鎖鏈閃電動畫視覺設計變換調整狀態"))
# 誤報白名單：檢查前先擦掉，免得每次校閱都被同一批合法用詞洗版
PUNC_OK = re.compile(r"PROJECT:")                      # 台服造型系列名本來就帶半形冒號
SIMP_OK = re.compile(r"皇后|太后|后冠|后羿|后宮|王后")  # 「后」在這些詞是正體，不是「後」的簡體
# 「護甲」是符文／技能／道具的專有名稱，不是 Armor 屬性，不該提醒改成「物防」
ARMOR_OK = re.compile(r"(反塔|魔法|適應|毒性|毒素|冰川|嚴冬之霜|防禦塔|強化|冰霜|排位)護甲"
                      r"|護甲紋路|武器與護甲|護甲化為坐騎|轉化為堅固護甲")
for k, v in d.items():
    if re.search(r"法術強度|攻擊力(?!成長|道)|(?<![物魔])護甲|魔法抗性|(?<![物魔])魔抗", ARMOR_OK.sub("", v)):
        probs["屬性未簡稱"].append(v)
    if re.search(r"[一-鿿]\s*[:(]|[):]\s*[一-鿿]", PUNC_OK.sub("", v)):
        probs["半形標點"].append(v)
    if re.search(r"[A-Za-z]{4,}", ALLOW.sub("", v)):
        probs["殘留英文"].append(v)
    # \s+ 而非 \s*：原意是抓「A 與 。」這種缺值殘句，\s* 會把正常句尾「擊殺參與。」也算進去
    if re.search(r"(對應技能|相關技能|對應目標)。$", v) or re.search(r"(與|至|從)\s+。", v):
        probs["空泛/缺主詞"].append(v)
    if re.search(r"[体术后战应对经护优败伤药宝团队风级杀锁闪动视设变调状]", SIMP_OK.sub("", v)):
        probs["簡體字"].append(v)
for cat, ls in probs.items():
    print(f"\n== {cat}: {len(ls)} ==")
    for x in ls[:12]:
        print("  ", x[:110])
