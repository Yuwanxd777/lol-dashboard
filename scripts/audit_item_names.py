# -*- coding: utf-8 -*-
"""道具名校對：把 patches.js 的「道具改動名稱」跟圖鑑（items.js／assets.js）的名稱對一遍。

為什麼需要：官方公告的譯名跟遊戲內名稱**經常不一致**，而且同一份 patches.js 裡兩種寫法會並存
（2026-08-17 實測：Eclipse 有 10 行寫「日蝕」、11 行寫「星蝕」）。名稱對不上圖鑑，
版本改動那邊就抓不到道具圖示、也連不到詳情頁。

⚠ 不要自動改：日蝕同時是雷歐娜 W 的技能名，硬改會把英雄改動改壞。這支只**列出候選**，
人工判斷後寫進 scripts/item_name_fix.json（clean_patch_text.py 會套用，只套 _extra 區）。

用法：python scripts/audit_item_names.py        # 預設只看近兩年
      python scripts/audit_item_names.py --all  # 全部年份
"""
import difflib
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def grab(var, txt):
    """抓 window.VAR={...} 的物件（檔案是單行大 JSON，用括號配對切）"""
    m = re.search(r"window\." + var + r"=(\{)", txt)
    if not m:
        return {}
    i, d = m.start(1), 0
    for j in range(i, len(txt)):
        if txt[j] == "{":
            d += 1
        elif txt[j] == "}":
            d -= 1
            if d == 0:
                return json.loads(txt[i:j + 1])
    return {}


def read(name):
    p = os.path.join(ROOT, name)
    return io.open(p, encoding="utf-8").read() if os.path.exists(p) else ""


def official_names():
    s = read("items.js")
    off = set(grab("ITEM_DESC", s)) | set(grab("ITEM_XTRA", s))
    A = grab("LOL_ASSETS", read("assets.js"))

    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, str) and re.search(r"[一-鿿]", o):
            off.add(o)
    walk(A.get("item", {}))
    return off


def main():
    all_years = "--all" in sys.argv
    off = official_names()
    fix = {k: v for k, v in json.load(open(os.path.join(HERE, "item_name_fix.json"), encoding="utf-8")).items()
           if not k.startswith("_")} if os.path.exists(os.path.join(HERE, "item_name_fix.json")) else {}
    P = grab("LOL_PATCHES", read("patches.js"))
    cand = {}
    for pk, pd in P.items():
        if not all_years and not pk.startswith(("25.", "26.")):
            continue
        for cat in ("道具", "裝備"):
            for l in pd.get("_extra", {}).get(cat, []):
                if "｜" not in l:
                    continue
                n = l.split("｜")[0].strip()
                # 區段標籤／技能格式／已知修正過的名字都不是候選
                if n in off or n in fix or re.match(r"^[QWER]\s*[-－]|^被動|^基礎|^新增|^經典|^\[", n):
                    continue
                e = cand.setdefault(n, {"pk": set(), "near": difflib.get_close_matches(n, off, n=3, cutoff=0.34)})
                e["pk"].add(pk)
    if not cand:
        print("道具名校對：沒有對不上圖鑑的名稱" + ("" if all_years else "（近兩年）"))
        return
    print(f"道具名校對：{len(cand)} 個名稱對不上圖鑑" + ("" if all_years else "（近兩年）")
          + "　※ 系統／符文／英雄名混進道具區也會被列出，人工判斷")
    for n, e in sorted(cand.items(), key=lambda x: -len(x[1]["pk"])):
        near = "｜".join(e["near"]) if e["near"] else "（找不到相近的）"
        print(f"  {n:<22} 版本 {sorted(e['pk'])[:4]}\n      圖鑑最接近 → {near}")
    print("\n判定後把「公告名: 圖鑑名」寫進 scripts/item_name_fix.json，再跑 clean_patch_text.py。")


if __name__ == "__main__":
    main()
