# -*- coding: utf-8 -*-
"""產生 skill_keys.js（window.SKILL_KEYS）＝**歷代**技能名 → 按鍵（Q/W/E/R/被動）對照。

為什麼要這份（2026-07-31 使用者回報）：版本改動的技能名後面要標按鍵（「杜蘭德石像（R）」），
但 index.html 的 SKMAP 是從 skills.js（**現行版**）建的 → 英雄重做過的舊技能名一律對不到。
加里歐 2013 的 R 叫「杜蘭德石像」，現代叫「英雄登場」，所以 2013 的改動就沒有按鍵標註。

做法：抓各年 DDragon 的 championFull.json（一年一個請求就含全部英雄的 spells），
收 {英雄id: {技能名: 按鍵}}。同名衝突時以**較舊的版本**為準——這份的用途就是補舊名，
現行名 index.html 本來就有。

**中英對照**（2026-07-31 使用者回報：2013 希維爾「On the Hunt」既沒翻中文也沒標 R）：
早年 wiki 的改動文字有些技能名是英文原名，中文對照表當然對不到。所以這裡連 en_US 一起抓，
同一個 spell 的英文名也寫進 SKILL_KEYS（讓按鍵標註吃得到），另外輸出 SKILL_ZH＝
{英雄id: {英文技能名: 中文技能名}} 給顯示層把前綴換成中文。

用法：python scripts\\fetch_skill_keys.py
"""
import io, json, os, re, sys, urllib.request

# 經典服（LoL Classic，DDragon 內部代號 Jade_*）不是我們要的資料（2026-07-31、2026-08-06 使用者兩度
# 回報英雄Tier 出現舊版頭像）——它的 zh/en 名稱與現行英雄**完全相同**，混進來會造成同名重複與圖片誤植。
# 日後若 Riot 再開別的分支服，一樣在這裡擋掉。
CLASSIC_RE = re.compile(r"^(Jade|Classic|Legacy)_", re.I)   # 分支服前綴：不進資料

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


def get(v, loc="zh_TW"):
    u = "https://ddragon.leagueoflegends.com/cdn/%s/data/%s/championFull.json" % (v, loc)
    try:
        return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=90).read())["data"]
    except Exception as e:
        print("   %s：跳過（%s）" % (v, type(e).__name__))
        return {}


def main():
    out, zh = {}, {}
    for v in VERS:
        d = get(v)
        if not d:
            continue
        de = get(v, "en_US") or {}
        add = 0
        for cid, c in d.items():
            if CLASSIC_RE.match(cid):          # 濾掉分支服（見檔頭 CLASSIC_RE）
                continue
            o = out.setdefault(cid, {})
            z = zh.setdefault(cid, {})
            ce = de.get(cid) or {}
            # 被動
            p = (c.get("passive") or {}).get("name")
            pe = (ce.get("passive") or {}).get("name")
            for nm in (p, pe):
                if nm and nm not in o:
                    o[nm] = "被動"; add += 1
            if p and pe and pe != p and pe not in z:
                z[pe] = p
            # Q/W/E/R
            sl, se = c.get("spells") or [], ce.get("spells") or []
            for i, sp in enumerate(sl):
                if i >= 4:
                    break
                nm = sp.get("name")
                en = (se[i].get("name") if i < len(se) else "") or ""
                for x in (nm, en):
                    if x and x not in o:
                        o[x] = KEYS[i]; add += 1
                if nm and en and en != nm and en not in z:
                    z[en] = nm
        print("   %s：%d 隻英雄，新增 %d 個技能名" % (v, len(d), add))
    out = {k: v for k, v in out.items() if v}
    zh = {k: v for k, v in zh.items() if v}
    tot = sum(len(v) for v in out.values())
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.SKILL_KEYS=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";" + chr(10))
        f.write("window.SKILL_ZH=" + json.dumps(zh, ensure_ascii=False, separators=(",", ":")) + ";")
    print("")
    print("OK skill_keys.js：%d 隻英雄、%d 個技能名、%d 組英→中對照"
          % (len(out), tot, sum(len(v) for v in zh.values())))
    for cid in ("Galio", "Sivir"):
        g = out.get(cid) or {}
        print("   驗證 %s：%s" % (cid, "、".join("%s=%s" % (k, x) for k, x in g.items())))
        print("     英→中：%s" % "、".join("%s→%s" % (k, x) for k, x in (zh.get(cid) or {}).items()))


if __name__ == "__main__":
    main()
