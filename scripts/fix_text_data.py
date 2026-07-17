# -*- coding: utf-8 -*-
"""
資料檔文本就地修正（JSON 安全版：只改「字串值」，絕不對原始檔文字做正規式取代）。

為什麼需要這支：wiki_patches.js / wiki_extra.js / patches.js 的內容來自永久快取
（fetch_wiki 不在 update.bat 裡、patch 快取發布後不再變），改了 fetch_*.py 的清理規則
也不會自動套用到既有資料 → 用這支把同一套規則補套到已產出的檔案上。

規則與 fetch_patches.translate()／fetch_skills.fill_tooltip() 的收尾清理保持一致。
    python scripts\fix_text_data.py            # 修正並回報
    python scripts\fix_text_data.py --dry      # 只看會改幾筆，不寫檔

鐵則：**絕不用 s.replace("}}", "") 這種手法直接改檔案文字**——會把 JSON 的結尾大括號吃掉，整份資料報廢。
"""
import json, io, re, os, sys, shutil

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["patches.js", "patches_en.js", "wiki_patches.js", "wiki_extra.js", "items.js"]
# items.js 的說明是 DDragon 的 HTML 原文（前端會渲染標籤）→ 只做「不動標籤」的清理
HTML_FILES = {"items.js"}
DRY = "--dry" in sys.argv

PHRASE = [
    ("範圍--效果", "範圍效果"), ("魔法傷害--時間", "魔法持續傷害"), ("傷害--時間", "持續傷害"),
    ("--戰鬥", "脫離戰鬥"),                       # out-of-combat（刪連字號會掉「脫離」語意）
    ("Grandmaster--Arms", "Grandmaster-at-Arms"),
    ("永恆飢渴｜層：", "永恆飢渴｜最大層數："),      # 英文原文＝Max stacks，只翻成「層」看不懂
    ("Clockwork Winding｜層：", "Clockwork Winding｜最大層數："),
    ("不潔射擊｜層：", "不潔射擊｜最大層數："),
    ("爆頭｜層：", "爆頭｜層數："),                 # 這個是「觸發所需層數」不是上限
]

def fix_html(s):
    """HTML 原文檔（items.js）：只清 Riot 沒填的 @token@ 與 %% 之類，不碰標籤"""
    o = s
    s = re.sub(r"@[A-Za-z_][\w.:*]*@", "", s)           # Riot 自己沒填的 @spell.SRU_xxx@
    s = re.sub(r"%i:\w+%", "", s)
    s = re.sub(r"%{2,}", "%", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s, s != o

def fix(s):
    o = s
    for a, b in PHRASE:
        s = s.replace(a, b)
    s = re.sub(r"%i:\w+%", "", s)                       # Riot 內嵌圖示佔位符
    s = re.sub(r"@[A-Za-z_][\w.:*]*@", "", s)           # 字串表 @token@ 殘留
    s = re.sub(r"%{2,}", "%", s)                        # 「20%%失去生命」
    s = re.sub(r"(?<=\s)%(?=\s)", "", s)                # 孤零零的 %（原文的圖示/逗號被剝掉後留下）
    s = re.sub(r"(AP|AD|物攻|魔攻|暴擊率|攻速)\s*%(?![\d])", r"\1", s)   # 「115% + 暴擊率%」尾巴那個 % 是多的
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)                # 未填值 token
    s = s.replace("{{", "").replace("}}", "")           # 落單的大括號（字串內，安全）
    s = re.sub(r"([一-鿿])-+(?=[一-鿿])", r"\1", s)      # 中文之間的空連字號（英文複合詞逐字翻譯殘留）
    s = re.sub(r"(^|[｜|：、，。\s])-+(?=[一-鿿])", r"\1", s)
    s = re.sub(r"-{2,}", "-", s)
    s = re.sub(r"：{2,}", "：", s)                       # 標籤自帶冒號 → 「魔力消耗：：」
    s = re.sub(r"[（(]\s*[+＋×xX]?\s*[)）]", "", s)      # 係數被剝掉的空括號「（+ ）」
    s = re.sub(r"(\d)\s+%", r"\1%", s)                  # 「25 % 跑速」→「25%」
    s = re.sub(r"%\s+(?=[（(])", "%", s)                # 「30% （+3% AP）」→「30%（+3% AP）」
    s = re.sub(r"[，、]\s*(?=[，、。])", "", s)          # 連結被剝掉後的孤立標點
    s = re.sub(r"[：，、]\s*(?=。)", "", s)
    s = re.sub(r"，\s*(?:且|或|和)\s*。", "。", s)
    s = re.sub(r"(：|:)\s*None\s*(?=⇒)", r"\1 — ", s)   # ARAM 平衡：原本沒有調整
    s = re.sub(r"(⇒)\s*None\s*$", r"\1 —", s)
    s = re.sub(r"[ \t]{2,}", " ", s).strip()
    return s, s != o

def walk(o, cnt, html=False):
    if isinstance(o, str):
        s, ch = (fix_html(o) if html else fix(o))
        if ch:
            cnt[0] += 1
        return s
    if isinstance(o, dict):
        return {k: walk(v, cnt, html) for k, v in o.items()}
    if isinstance(o, list):
        return [walk(v, cnt, html) for v in o]
    return o

for f in FILES:
    p = os.path.join(BASE, f)
    if not os.path.exists(p):
        continue
    raw = io.open(p, encoding="utf-8").read()
    # 檔案結構：window.NAME={...};（可能多個宣告）
    parts = re.findall(r"(window\.\w+\s*=\s*)(.+?)(?=;?\s*window\.\w+\s*=|\s*;?\s*$)", raw, re.S)
    if not parts:
        print("%-16s 解析不出結構，跳過" % f)
        continue
    cnt, out = [0], []
    ok = True
    for prefix, body in parts:
        try:
            obj = json.loads(body.strip().rstrip(";"))
        except Exception as e:
            print("%-16s JSON 解析失敗：%s" % (f, e)); ok = False; break
        out.append(prefix + json.dumps(walk(obj, cnt, f in HTML_FILES), ensure_ascii=False, separators=(",", ":")) + ";")
    if not ok:
        continue
    if cnt[0] and not DRY:
        shutil.copy(p, p + ".bak")
        io.open(p, "w", encoding="utf-8").write("\n".join(out) + "\n")
        json.loads(re.split(r"window\.\w+\s*=", io.open(p, encoding="utf-8").read())[1].strip().rstrip(";"))  # 寫完立刻驗
        os.remove(p + ".bak")
    print("%-16s 修正 %d 條字串%s" % (f, cnt[0], "（dry-run，未寫檔）" if DRY else ""))
