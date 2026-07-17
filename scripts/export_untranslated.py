# -*- coding: utf-8 -*-
"""把仍顯示英文原文的改動行匯出成分批記事本（丟給網頁版 Claude 翻譯用）。
輸出：待翻譯\part_XX.txt（每檔含翻譯指示＋500 行）
回收：把網頁版回覆的 JSON 存成 待翻譯\done\任意名.json，跑 merge_tr.py 合併。"""
import io, sys, json, re, collections, os, glob
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "scripts"))
from fetch_patches import mixed_en, _manual_tr

PROMPT = """請把下面每一行英文（或中英混雜）的《英雄聯盟》版本改動文本，翻成台灣繁體中文的官方公告風格。每行開頭的「編號. 」不是內文，是行號。規則：
1. 屬性一律用簡稱：物攻／物防／魔攻／魔防；Ability Power=魔攻、Attack Damage=物攻、Armor=物防、Magic Resist=魔防
2. 標點全形（：、（）、。），「⇒」與數字原樣保留，AP/AD/HP 等縮寫保留
3. 行內「名稱｜」結構要保留：名稱若是英文技能／道具名請意譯成通行繁中譯名，「｜」後面才是內文
4. 台灣用語（例如：冷卻時間、普攻、擊殺參與、召喚峽谷）
5. 站內用語統一：Armor Penetration/Lethality＝物穿、Magic Penetration＝法穿、Life Steal＝吸血、Magic Damage＝魔傷、Physical Damage＝物傷、Ghost＝鬼步、Mana Growth＝成長魔力、生命值一律寫「生命」
6. 道具／符文／天賦名用《英雄聯盟》台服官方譯名（例：Sweeping Lens＝清除者透視鏡、Bami's Cinder＝巴米灰燼、Warlord's Bloodlust＝軍閥血嗜）；不確定的專有名詞保留英文
輸出格式：單一 JSON 物件，key＝行編號（字串），value＝該行完整譯文（含「名稱｜」前綴）。不要重複原文、除了 JSON 不要輸出任何其他文字、不要 ``` 圍欄。
例：{"37":"軍閥血嗜｜吸血：15% ⇒ 12%"}

"""

def lines_of(path, key):
    t = open(os.path.join(HERE, path), encoding="utf-8").read()
    m = re.search(r"window\." + key + r"=(\{.*?\});", t, re.S)
    d = json.loads(m.group(1))
    out = []
    def walk(x):
        if isinstance(x, str): out.append(x)
        elif isinstance(x, list):
            for y in x: walk(y)
        elif isinstance(x, dict):
            for y in x.values(): walk(y)
    walk(d)
    return out

COSM = re.compile(r"原畫|造型|背景故事|中版美術|重新上色|推薦裝備|語音(更新|台詞)|(技能)?圖示更新|更新[了]?圖示|特效(已)?更新|視覺效果|粒子效果|模型更新|動畫更新|說明更新|新增語音|音效|現在(能|會)?正確|嚎哭深淵|極地大亂鬥|扭曲叢林|統治戰場|Howling Abyss|Twisted Treeline|Crystal Scar|Dominion|[（(]ARAM[)）]|Level Requirements?|更名|重新命名|renamed|[Nn]ame changed|名稱[：:][^⇒\n]*⇒|(^|｜|\[)\s*(未公告|錯誤修正|錯誤|修正了|修復|[Uu]ndocumented|[Bb]ug\s?[Ff]ix|BUG)|編按|附註[：:]|並未實裝|官方未記載|並非刻意|此問題可能是在|未列於公告|(邊緣|中心)判定距離|(重新)?編寫程式(碼)?|rescripted?|visual (upgrade|update|effects?)|splash art|voice.?over|icons? (are |have been )?updated|recommended items|lore|chroma|texture|animations? updated|now (correctly|properly)|tooltip", re.I)
JUNK = re.compile(r"^(Stats|General|Abilities|Added|Removed|Sound|Voice|Full Relaunch|New)\.?$", re.I)

def eng_only(s):
    return not re.search(r"[一-鿿]", s) and bool(re.search(r"[A-Za-z]{3,}", s))

man = _manual_tr()
# 之前已翻譯過的都排除、不再提醒：manual_tr.json（已合併）＋ 待翻譯\done\*.json（已翻但尚未 merge）
done_keys = set()
for f in glob.glob(os.path.join(HERE, "待翻譯", "done", "*.json")):
    try:
        for k in json.load(open(f, encoding="utf-8")):
            done_keys.add(k.strip())
    except Exception as e:
        print(f"⚠ 讀取 {os.path.basename(f)} 失敗，略過：{e}")
# 人工確認「已足夠、以後別再列」的行（多為已翻好、只剩專有名詞英文）：scripts\tr_accepted.txt 一行一條
# （原在 待翻譯\accepted.txt；使用者要求 待翻譯 資料夾只放待翻批次，白名單移到 scripts）
accepted = set()
_acc_path = os.path.join(HERE, "scripts", "tr_accepted.txt")
if os.path.exists(_acc_path):
    for line in open(_acc_path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#"):
            accepted.add(line)
pool = collections.Counter()
for path, key in (("patches.js", "LOL_PATCHES"), ("wiki_patches.js", "WIKI_PATCHES"), ("wiki_extra.js", "WIKI_EXTRA"), ("wiki_objectives.js", "WIKI_OBJECTIVES")):
    for l in lines_of(path, key):
        l = l.strip()
        if len(l) < 6 or l.startswith("http") or l in man or l in done_keys or l in accepted: continue
        if COSM.search(l) or JUNK.match(l): continue
        body = l.split("｜", 1)[1] if "｜" in l else l
        if eng_only(body) or mixed_en(body):
            pool[l] += 1

items = [l for l, _ in sorted(pool.items(), key=lambda x: (-x[1], x[0]))]
outdir = os.path.join(HERE, "待翻譯")
os.makedirs(outdir, exist_ok=True)
os.makedirs(os.path.join(outdir, "done"), exist_ok=True)
# 清掉上一輪殘留的 part_*.txt，避免新舊批次混在一起（done\*.json 不動）
for old in glob.glob(os.path.join(outdir, "part_*.txt")):
    os.remove(old)
# 編號制：輸出只回「編號→譯文」（不用重抄原文），單則回覆量減半才不會撞到網頁版輸出上限。
# 編號→原文對照放 csv_cache\tr_lines_map.json（機器檔不佔 待翻譯 資料夾）；覆寫前備份成 _prev
# → 上一輪批次晚到的純編號回覆仍可解析（merge_tr 會先查現行、再查 _prev）。
line_map = {str(i + 1): l for i, l in enumerate(items)}
_lm_path = os.path.join(HERE, "csv_cache", "tr_lines_map.json")
if os.path.exists(_lm_path):
    try:
        os.replace(_lm_path, os.path.join(HERE, "csv_cache", "tr_lines_map_prev.json"))
    except Exception:
        pass
json.dump(line_map, open(_lm_path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
CH = 150
nf = 0
for i in range(0, len(items), CH):
    nf += 1
    with open(os.path.join(outdir, f"part_{nf:02d}.txt"), "w", encoding="utf-8") as f:
        f.write(PROMPT)
        f.write("\n".join(f"{i + j + 1}. {l}" for j, l in enumerate(items[i:i+CH])))
print(f"共 {len(items)} 行 → {nf} 個檔案（每檔 {CH} 行，編號制）→ {outdir}")
print("流程：把 part_XX.txt 整檔貼給網頁版 Claude → 回覆的 JSON 存成 待翻譯\\done\\任意名.json → 跑 python scripts\\merge_tr.py")
