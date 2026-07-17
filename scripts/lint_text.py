# -*- coding: utf-8 -*-
"""
文本庫體檢：把所有資料檔的字串撈出來，逐條套規則找「殘留物」與「壞句」。

用途：Riot 每次改版後、或改動任何 fetch_*.py 之後跑一次，確認沒有把文本弄壞。
    python scripts\lint_text.py            # 摘要（每類最多列 6 筆）
    python scripts\lint_text.py --all      # 每類全部列出
    python scripts\lint_text.py --rule 數字缺失   # 只看某一類（可用關鍵字）
    python scripts\lint_text.py --quiet    # 只印統計數字（給 update.bat 記 log 用）
離開碼：有「錯誤級」問題＝1，只有「提醒級」＝0。

**新增規則就加進 RULES**（(名稱, 正規式, 等級)）。等級：ERR＝一定是 bug；WARN＝可能是 Riot 原文如此，人工判斷。
歷史抓到過的真 bug（別讓它們回來）：
  %i:scaleCrit% 圖示佔位符、{{ }} 未填值、@token@ 未填值、
  「範圍--效果」「每-層」（英文連字號複合詞逐字翻譯殘留）、
  「增加%攻速」（token 解析失敗只剩 %）、「：：」（官方公告標籤重複冒號）、
  「（+ ）」（係數缺失的空括號）、「暴擊：。」（值缺失後的孤立標點）
"""
import json, io, re, os, sys
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["skills.js", "items.js", "patches.js", "patches_en.js", "wiki_patches.js",
         "wiki_extra.js", "jungle.js", "champ_release.js"]

ERR, WARN = "錯誤", "提醒"
# 白名單：本來就會出現在中文句子裡的英文縮寫／專有名詞
EN_OK = re.compile(r"^(?:AD|AP|HP|MP|CD|AoE|DoT|LP|UI|HUD|VFX|SFX|MR|AS|CC|FPS|PvP|PvE|MVP|KDA|DPM|"
                   r"Fearless|Riot|Bug|Fix|New|Effect|Removed|Nerf|Buff|Hail|Blades)$", re.I)

RULES = [
    # ── 錯誤級：一定是資料壞了 ──────────────────────────────────────────────
    ("Riot 圖示佔位符 %i:xxx%",   re.compile(r"%i:\w+%"), ERR),
    ("未填值 token {{ }}",        re.compile(r"\{\{|\}\}"), ERR),
    ("未填值 token @xxx@",        re.compile(r"@[A-Za-z_][\w.]*@"), ERR),
    # 只抓「中文句子裡 % 前面該有數字卻沒有」（增加%攻速）；
    # 英文標籤「% Max HP」、wiki 佔位符「x% 的生命值」「0% – X%」都是合法的，不抓
    ("數字缺失（% 前無數字）",     re.compile(r"(?<![\d.）)\]％%XxＸ])%(?=[一-鿿])"), ERR),
    ("數字與 % 之間有空格",        re.compile(r"\d\s+%"), ERR),   # 「25 % 跑速」→ 應為「25% 跑速」
    ("% 與括號之間有空格",         re.compile(r"%\s+[（(]"), ERR), # 「30% （+3% AP）」→ 應為「30%（+3% AP）」
    ("正負號連用（+-）",           re.compile(r"\+\s*-\d"), ERR),  # 執行時公式殘留項算出負係數
    # 百分比乘兩次（計算式已是百分數、模板又 ×100）：3000% 跑速、8000% 攻速這種。
    # 註：多段傷害的總和係數（好運姐 R 的 +1080% AD）是合法的 → 提醒級，人工判斷
    ("百分比異常（≥1000%）",       re.compile(r"(?<![\d.])[1-9]\d{3,}(?:\.\d+)?%"), WARN),
    ("空括號（係數缺失）",         re.compile(r"[（(]\s*[+×xX]?\s*[)）]"), ERR),
    ("孤立連字號（翻譯殘留）",     re.compile(r"[一-鿿]-+[一-鿿]|(?:^|[｜：，。\s])-{2,}"), ERR),
    ("重複標點",                  re.compile(r"[，。；]\s*[，。；]|：：|、\s*、|：\s*。"), ERR),
    ("undefined/NaN/None",        re.compile(r"(?<![A-Za-z])(?:undefined|NaN|None)(?![A-Za-z])"), ERR),
    ("空內容（只剩標點）",         re.compile(r"^[\s。，、：；()（）%＋+\-]*$"), ERR),
    # ── 提醒級：多半是 Riot 原文如此，人工判斷 ─────────────────────────────
    ("結尾懸空（以 ：，、 結束）",  re.compile(r"[：，、和與或的]\s*$"), WARN),
    ("標點前空白",                re.compile(r"\s+[，。；：）]"), WARN),
    ("連續空白",                  re.compile(r"[ \t]{3,}"), WARN),
    ("殘留 HTML 標籤",            re.compile(r"</?(?:br|span|div|font|li|magicDamage|physicalDamage|trueDamage|"
                                            r"status|attackSpeed|scale\w*|keyword\w*)\b[^>]*>", re.I), WARN),
    ("可疑數值（0.01 秒／負秒數）", re.compile(r"(?<![\d.])-\d+(?:\.\d+)?\s*秒|(?<![\d.])0\.0\d+\s*秒"), WARN),
]
# items.js 的說明本來就是 DDragon 的 HTML 原文（前端會渲染）→ 這兩類不算它的錯
SKIP = {("items.js", "殘留 HTML 標籤"), ("items.js", "中英混雜（未翻完）"),
        ("skills.js", "殘留 HTML 標籤"),
        # 已知 Riot 資料缺口：野區夥伴（熾爪幼犬/馭風幼狐/重踏幼蠑螈）的 DDragon 描述裡數值是 @spell@ 佔位符，
        # Riot 自己沒填 → 清掉佔位符後會留下「傷害為%」「回復最多-生命」。不是我們的 bug。
        ("items.js", "孤立連字號（翻譯殘留）"), ("items.js", "數字缺失（% 前無數字）")}

def strings_of(obj, path=""):
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from strings_of(v, path + "/" + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from strings_of(v, "%s[%d]" % (path, i))

def load(f):
    s = io.open(os.path.join(BASE, f), encoding="utf-8").read()
    body = s[s.find("=") + 1:].strip().rstrip(";")
    out = []
    for p in re.split(r";\s*window\.\w+\s*=", body):
        try:
            out.append(json.loads(p.strip().rstrip(";")))
        except Exception:
            pass
    return out

def main():
    only = None
    if "--rule" in sys.argv:
        i = sys.argv.index("--rule")
        only = sys.argv[i + 1] if i + 1 < len(sys.argv) else None
    show_all, quiet = "--all" in sys.argv, "--quiet" in sys.argv

    hits, total = defaultdict(list), 0
    for f in FILES:
        if not os.path.exists(os.path.join(BASE, f)):
            continue
        for obj in load(f):
            for path, s in strings_of(obj):
                if len(s) < 2 or s.startswith("http") or re.match(r"^[\w.\-/]+\.(?:js|png|json|py)$", s):
                    continue
                total += 1
                for name, rx, lv in RULES:
                    if (f, name) in SKIP or (only and only not in name):
                        continue
                    if rx.search(s):
                        hits[(lv, name)].append((f, s))
                # 中英混雜：中文句子裡夾著非白名單的英文單字（多半是長尾沒翻到）
                if not (only and "混雜" not in only) and ("skills.js", "x") and re.search(r"[一-鿿]", s):
                    en = [w for w in re.findall(r"(?<![A-Za-z])[A-Za-z]{4,}(?![A-Za-z])", s) if not EN_OK.match(w)]
                    if en and (f, "中英混雜（未翻完）") not in SKIP:
                        hits[(WARN, "中英混雜（未翻完）")].append((f, s))

    errs = sum(len(v) for (lv, _), v in hits.items() if lv == ERR)
    warns = sum(len(v) for (lv, _), v in hits.items() if lv == WARN)
    print("文本體檢：掃描 %d 條字串 → 錯誤 %d、提醒 %d" % (total, errs, warns))
    if quiet:
        return 1 if errs else 0
    for (lv, name), lst in sorted(hits.items(), key=lambda x: (x[0][0] != ERR, -len(x[1]))):
        print("\n■ [%s] %s：%d 筆" % (lv, name, len(lst)))
        for f, s in (lst if show_all else lst[:6]):
            print("    (%s) %s" % (f, s.replace("\n", " ⏎ ")[:120]))
        if not show_all and len(lst) > 6:
            print("    …（另 %d 筆，加 --all 看全部）" % (len(lst) - 6))
    return 1 if errs else 0

if __name__ == "__main__":
    sys.exit(main())
