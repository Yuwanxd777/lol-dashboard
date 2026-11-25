# -*- coding: utf-8 -*-
"""fetch_transfers 把 PTT 來源檔的 mv 轉成 Sheep 同格式（synth）時，來源網址要跟著走。

背景：2026-11-23（eec23cd7）在那個字典的同一行中間加了一句行內註解，結果後面的 "url" 鍵整個被吃進註解，
之後所有從 transfers_ptt_src.json 進陣容表的傳聞都沒有 u ⇒ 小框的來源名（PTT／SE／韓網…）點不開原文。
語法完全合法、守門也照過，兩天半沒有人發現（2026-11-26 精進迴圈 #3736 比對陣容表時才看到 101 格傳聞沒有 u）。

兩段檢查，都不讀寫資料檔、不連網：
  A. 原始碼：fetch_transfers.py 裡 "kind": "join" 的那個 synth.append 字典，鍵一定要有 d／st／kind／src／url／zh／en／who／tags。
     （用 ast 看「真的被 Python 讀到的鍵」，註解裡的字不算。）
  B. 接線：帶 url 的 synth 條目丟給 transfers_board.parse_sheep，結果的 u 要等於那個網址；不帶 url 的對照組 u 是空的。

用法：python scripts/fetch_transfers_synth_test.py   （全過離開碼 0）
"""
import ast
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import transfers_board as TB   # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("✓ " if cond else "✗ ") + name + (("｜" + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def synth_dict_keys(src):
    """回傳原始碼裡所有 synth.append({...}) 字典的鍵清單（只收 kind 是 "join" 的）"""
    found = []
    for n in ast.walk(ast.parse(src)):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "append"
                and isinstance(n.func.value, ast.Name) and n.func.value.id == "synth" and n.args and isinstance(n.args[0], ast.Dict)):
            d = n.args[0]
            keys = [k.value for k in d.keys if isinstance(k, ast.Constant)]
            kind = next((v.value for k, v in zip(d.keys, d.values)
                         if isinstance(k, ast.Constant) and k.value == "kind" and isinstance(v, ast.Constant)), None)
            if kind == "join":
                found.append(keys)
    return found


NEED = ["d", "st", "kind", "src", "url", "zh", "en", "who", "tags"]

# A. 真正的原始碼
real = io.open(os.path.join(HERE, "fetch_transfers.py"), encoding="utf-8").read()
ks = synth_dict_keys(real)
check("A 找得到 kind=join 的 synth.append 字典（恰好一個）", len(ks) == 1, "找到 %d 個" % len(ks))
miss = [k for k in NEED if not ks or k not in ks[0]]
check("A 那個字典的鍵齊全（含 url）", not miss, "缺 %s" % miss)

# A 的對照：把 url 那一行塞回註解後面（＝11-23 那個寫法），這支檢查要抓得到
bad = "synth = []\nsynth.append({\"d\": 1, \"st\": 2, \"kind\": \"join\", \"src\": 3,   # 註解 \"url\": 4,\n              \"zh\": 5, \"en\": 6, \"who\": 7, \"tags\": 8})\n"
kb = synth_dict_keys(bad)
check("A 對照：url 被註解吃掉的寫法會被判成缺 url", len(kb) == 1 and "url" not in kb[0] and [k for k in NEED if k not in kb[0]] == ["url"], str(kb))

# B. 接線：url → parse_sheep 的 u
U = "https://x.com/Sheep_Esports/status/2125609200180920403"


def item(url):
    x = {"d": "2026-11-25 23:26", "st": "rumor", "kind": "join", "src": "Sheep Esports", "zh": "Zven 將加入 OpTic Gaming。", "en": "",
         "who": ["Zven", "Zven", "BOT"], "tags": [["", "Cloud9", "out"], ["", "OpTic Gaming", "in"]]}
    if url is not None:
        x["url"] = url
    return x


r1 = TB.parse_sheep([item(U)])
v1 = (r1.get(("optic gaming", "BOT")) or [{}])[0]
check("B 帶 url 的條目 ⇒ parse_sheep 的 u 就是那個網址", v1.get("u") == U, repr(v1.get("u")))
r0 = TB.parse_sheep([item(None)])
v0 = (r0.get(("optic gaming", "BOT")) or [{}])[0]
check("B 對照：不帶 url ⇒ u 是空的（＝修之前的樣子）", v0.get("n") == "Zven" and not v0.get("u"), repr(v0.get("u")))

print("")
print("結果：%s（%d 項沒過）" % ("全過" if not fails else "有沒過的", len(fails)))
sys.exit(1 if fails else 0)
