# -*- coding: utf-8 -*-
"""產生 skill_keys.js（window.SKILL_KEYS）＝**歷代**技能名 → 按鍵（Q/W/E/R/被動）對照。

為什麼要這份（2026-07-31 使用者回報）：版本改動的技能名後面要標按鍵（「杜蘭德石像（R）」），
但 index.html 的 SKMAP 是從 skills.js（**現行版**）建的 → 英雄重做過的舊技能名一律對不到。
加里歐 2013 的 R 叫「杜蘭德石像」，現代叫「英雄登場」，所以 2013 的改動就沒有按鍵標註。

做法：抓各年 DDragon 的 championFull.json（一年一個請求就含全部英雄的 spells），
收 {英雄id: {技能名: 按鍵}}。同名衝突時以**較舊的版本**為準——這份的用途就是補舊名，
現行名 index.html 本來就有。

用法：python scripts\\fetch_skill_keys.py
"""
import io, json, os, sys, urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "skill_keys.js")
UA = {"User-Agent": "Mozilla/5.0"}

# 各年取樣版本（新→舊；同名衝突時舊的優先，因為這份是拿來補舊名的）
VERS = ["16.15.1", "15.24.1", "14.24.1", "13.24.1", "12.23.1", "11.24.1", "10.25.1",
        "9.24.2", "8.24.1", "7.24.2", "6.24.1", "5.24.2", "5.1.1", "4.21.5", "4.1.2",
        "3.15.5", "3.13.8", "3.10.3", "3.6.15"]
KEYS = ["Q", "W", "E", "R"]


def get(v):
    u = "https://ddragon.leagueoflegends.com/cdn/%s/data/zh_TW/championFull.json" % v
    try:
        return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=90).read())["data"]
    except Exception as e:
        print("   %s：跳過（%s）" % (v, type(e).__name__))
        return {}


def main():
    out = {}
    for v in VERS:
        d = get(v)
        if not d:
            continue
        add = 0
        for cid, c in d.items():
            o = out.setdefault(cid, {})
            p = (c.get("passive") or {}).get("name")
            if p and p not in o:
                o[p] = "被動"; add += 1
            for i, sp in enumerate(c.get("spells") or []):
                nm = sp.get("name")
                if nm and i < 4 and nm not in o:
                    o[nm] = KEYS[i]; add += 1
        print("   %s：%d 隻英雄，新增 %d 個技能名" % (v, len(d), add))
    tot = sum(len(v) for v in out.values())
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.SKILL_KEYS=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";")
    print("")
    print("OK skill_keys.js：%d 隻英雄、%d 個技能名" % (len(out), tot))
    g = out.get("Galio") or {}
    print("   驗證 Galio：" + "、".join("%s=%s" % (k, x) for k, x in g.items()))


if __name__ == "__main__":
    main()
