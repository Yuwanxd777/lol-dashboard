# -*- coding: utf-8 -*-
"""
本機 file:// 快速讀取檔：data/data_YYYY.js → data_local/data_YYYY.js（內容相同，包成 JSON 字串）。

為什麼：file:// 不能 fetch，年度資料只能用 <script> 載入，而 `window.LOL_DATA={...}` 這種 26MB 物件字面值
要 V8 整個當程式碼編譯（實測 2026 年檔 1.56 秒）；改成 `window.LOL_DATA_S="..."` 再 JSON.parse 只要 0.14 秒。
（使用者 2026-10-21：F5 後開英雄Tier 比賽數據讀很久。）

- data/data_YYYY.js 的格式一律不動（20 支腳本共用）；這裡只是多產一份本機用的。
- data_local/ 不在 .gitignore 白名單 ⇒ 不會被發布（網路版本來就走 fetch＋JSON.parse 的快路徑）。
- 只重做「來源比較新」的年份；來源大小也寫進檔裡（LOL_DATA_S_SIZE），index.html 端只拿來除錯，不做比對。
- 管線 ⑥b 與 preflight_check 都會呼叫 ⇒ 改了年度資料檔後跑一次 preflight 就會更新。

用法：python scripts/build_local_data.py [--force]
"""
import os, sys, json, glob, re

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "data"); DST = os.path.join(ROOT, "data_local")


def main():
    force = "--force" in sys.argv
    os.makedirs(DST, exist_ok=True)
    made = kept = bad = 0
    for p in sorted(glob.glob(os.path.join(SRC, "data_*.js"))):
        name = os.path.basename(p)
        if not re.fullmatch(r"data_\d{4}\.js", name):
            continue
        out = os.path.join(DST, name)
        if not force and os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(p):
            kept += 1
            continue
        t = open(p, encoding="utf-8").read()
        i = t.find("=")
        if i < 0 or t[:i].strip() != "window.LOL_DATA":
            print("  ⚠ 格式不符，略過：%s" % name); bad += 1; continue
        body = t[i + 1:].strip()
        if body.endswith(";"):
            body = body[:-1]
        try:
            json.loads(body)          # 確認是合法 JSON（前端要 JSON.parse）
        except Exception as e:
            print("  ⚠ 不是合法 JSON，略過：%s（%s）" % (name, e)); bad += 1; continue
        tmp = out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("window.LOL_DATA_S=" + json.dumps(body, ensure_ascii=False) + ";\n")
            f.write("window.LOL_DATA_S_SIZE=%d;\n" % os.path.getsize(p))
        os.replace(tmp, out)
        made += 1
    print("本機快速讀取檔：重做 %d 個、沿用 %d 個%s → %s" % (made, kept, ("、略過 %d 個" % bad) if bad else "", DST))
    return 0


if __name__ == "__main__":
    sys.exit(main())
