# -*- coding: utf-8 -*-
"""把 待翻譯\done\*.json（網頁版 Claude 的翻譯回覆）合併進 scripts\manual_tr.json，
然後重跑三個建置腳本讓翻譯生效。"""
import io, sys, json, os, glob, re, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAN = os.path.join(HERE, "scripts", "manual_tr.json")

man = {}
if os.path.exists(MAN):
    man = json.load(open(MAN, encoding="utf-8"))
before = len(man)
bad = 0
# 編號制對照表（export_untranslated.py 產出，csv_cache\tr_lines_map.json）：done 檔的 key 若是純數字，用它換回原文行
# _prev＝上一輪批次的對照（re-export 前的備份）：晚到的舊批回覆先查現行、查無再查上一輪
LMAP = {}
for _lm in (os.path.join(HERE, "csv_cache", "tr_lines_map_prev.json"), os.path.join(HERE, "csv_cache", "tr_lines_map.json"), os.path.join(HERE, "待翻譯", "lines_map.json")):
    if os.path.exists(_lm):
        try:
            _d = json.load(open(_lm, encoding="utf-8"))
        except Exception:
            continue
        LMAP.update(_d)   # 後載入者（現行）覆蓋 _prev 同號
for f in sorted(glob.glob(os.path.join(HERE, "待翻譯", "done", "*.json")) + glob.glob(os.path.join(HERE, "待翻譯", "done", "*.txt"))):
    if os.path.basename(f) == "accepted.txt":
        continue  # 白名單誤存檔不是翻譯
    txt = open(f, encoding="utf-8").read()
    # 容錯：回覆可能包 ```json 圍欄
    m = re.search(r"\{[\s\S]*\}", txt)
    if not m:
        print(f"⚠ {os.path.basename(f)} 找不到 JSON，跳過"); continue
    try:
        d = json.loads(m.group(0))
    except Exception as e:
        print(f"⚠ {os.path.basename(f)} JSON 解析失敗：{e}"); continue
    miss = 0
    for k, v in d.items():
        if not isinstance(v, str) or not v.strip():
            bad += 1; continue
        k = k.strip()
        k = re.sub(r"^\d+\.\s*", "", k)      # 「編號. 原文」混合鍵 → 剝掉編號前綴（有的回覆會照抄行號）
        if k.isdigit():                      # 純編號制 → 換回原文行
            src = LMAP.get(k)
            if not src:
                miss += 1; continue
            k = src
        if not k:
            bad += 1; continue
        man[k] = v.strip()
    print(f"✓ {os.path.basename(f)}：{len(d)} 條" + (f"（{miss} 條編號查無、跳過）" if miss else ""))

# 譯文標點正規化（網頁版回覆常見毛病）：標點前空白、%（ 之間空格、重複標點
def _norm_v(v):
    v = re.sub(r"\{\{|\}\}", "", v)                  # wiki 模板殘渣
    v = re.sub(r"\s+([。，、：；！？％）])", r"\1", v)
    v = re.sub(r"%\s+（", "%（", v)
    v = re.sub(r"([。，、：；])\1+", r"\1", v)
    return v.strip()
man = {k: _norm_v(v) for k, v in man.items()}
json.dump(man, open(MAN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"manual_tr.json：{before} → {len(man)} 條（略過空值 {bad}）")
print("── 校閱報告（有列出的條目請人工確認/修正）──")
subprocess.run([sys.executable, os.path.join(HERE, "scripts", "audit_tr.py")], cwd=HERE)
print("重建輸出檔…")
for s in ("fetch_wiki.py", "fetch_wiki_extra.py", "fetch_wiki_objectives.py"):
    subprocess.run([sys.executable, os.path.join(HERE, "scripts", s)], cwd=HERE)
subprocess.run([sys.executable, os.path.join(HERE, "scripts", "fetch_patches.py"), "--skip-discover"], cwd=HERE)
print("完成。重新整理網頁即可看到翻譯。")
