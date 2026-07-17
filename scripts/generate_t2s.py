# -*- coding: utf-8 -*-
"""產生繁→簡 單字對照 t2s.js（給儀表板「簡體中文」用；純字級簡繁轉換）。
用 opencc t2s。只收「單字→單字且有變」的映射，覆蓋 CJK 常用區＋擴充A。"""
import opencc, json, os
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
cc=opencc.OpenCC('t2s')
m={}
ranges=[(0x4E00,0x9FFF),(0x3400,0x4DBF),(0xF900,0xFAFF)]  # CJK 基本+擴充A+相容
for lo,hi in ranges:
    for cp in range(lo,hi+1):
        ch=chr(cp)
        try: s=cc.convert(ch)
        except Exception: continue
        if len(s)==1 and s!=ch:
            m[ch]=s
out=os.path.join(ROOT,"t2s.js")
with open(out,"w",encoding="utf-8") as f:
    f.write("window.T2S="+json.dumps(m,ensure_ascii=False,separators=(',',':'))+";\n")
print(f"完成：{len(m)} 個繁→簡字 → {out}（{os.path.getsize(out)/1024:.0f} KB）")
print("樣本:", {k:m[k] for k in list(m)[:8]})
print("測試:", "".join(m.get(c,c) for c in "繁體中文測試龍蝦禁用勝率選手戰隊"))
