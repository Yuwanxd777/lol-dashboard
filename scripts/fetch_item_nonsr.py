# -*- coding: utf-8 -*-
"""產生 item_nonsr.js（window.ITEM_NONSR）＝**逐年**的「非召喚峽谷道具」中文名清單。

為什麼要這份（2026-07-31 使用者回報）：圖鑑「版本」分頁的道具改動是從 wiki 版本頁抓的，
那裡連扭曲叢林／統治戰場／決勝慶典的道具改動都寫在一起（光之使者、海克斯清除者、
格雷提燈、烏莉特的法帽…）。圖鑑的道具**清單**已經用 srItemOK 過濾過，但版本改動那條路
只有文字、沒有 id，無從判斷 → 改用這份名單擋掉。

**為什麼要分年份**：中譯會撞名。2013 的「黑焰火炬」(id 3188) 是扭曲叢林道具，
而現代的黑焰火炬 (Liandry's Torment, id 3151) 是正規峽谷道具；「急凍戰鎚」也一樣。
不分年份就會把現代那件一起濾掉。

判定依 DDragon item.json 的 maps 旗標，與 index.html 的 srItemOK 同一套規則。
同一年內多數決：該年各取樣版本被判非峽谷的次數 > 被判峽谷的次數才收。

用法：python scripts\\fetch_item_nonsr.py
"""
import io, json, os, re, sys, urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "item_nonsr.js")
UA = {"User-Agent": "Mozilla/5.0"}

# 年份 → 該年取樣版本（DDragon 主版號＋2010＝賽季年；早年只有這幾個三段號拿得到）
VERS = {
    2013: ["3.6.15", "3.10.3", "3.13.8", "3.15.5"],
    2014: ["4.1.2", "4.16.1", "4.21.5"],
    2015: ["5.1.1", "5.16.1", "5.24.2"],
    2016: ["6.1.1", "6.24.1"],
    2017: ["7.1.1", "7.24.2"],
    2018: ["8.1.1", "8.24.1"],
    2019: ["9.1.1", "9.24.2"],
}


def get(v, loc="zh_TW"):
    u = "https://ddragon.leagueoflegends.com/cdn/%s/data/%s/item.json" % (v, loc)
    try:
        return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60).read())["data"]
    except Exception as e:
        print("   %s：跳過（%s）" % (v, type(e).__name__))
        return {}


def non_sr(d, iid):
    """與 index.html srItemOK 相反：True＝**不是**召喚峽谷道具"""
    m = d.get("maps") or {}
    if m.get("1") is False and m.get("11") is not True:
        return True
    if m.get("11") is False:
        return True
    if (m.get("8") is True or m.get("10") is True) and m.get("11") is not True:
        return True
    try:
        if int(iid) >= 200000:
            return True
    except ValueError:
        pass
    return False


def clname(n):
    n = re.sub(r"：\s+", "：", str(n or ""))
    return re.sub(r"\s*[（(][^（）()]*[）)]\s*$", "", n).strip()


def main():
    out = {}
    for yr in sorted(VERS):
        bad, ok = {}, {}
        for v in VERS[yr]:
            d = get(v)
            if not d:
                continue
            # 也收英文名：版本改動頁常常直接寫英文道具名（Moonflair Spellblade），
            # 只有中文名的話對不上、擋不掉（2026-07-31 使用者回報）
            den = get(v, "en_US")
            nb = 0
            for iid, it in d.items():
                nm = clname(it.get("name"))
                en = clname((den.get(iid) or {}).get("name")) if den else ""
                if not nm:
                    continue
                _keys = [nm] + ([en] if en and en != nm else [])
                if non_sr(it, iid):
                    for _k in _keys:
                        bad[_k] = bad.get(_k, 0) + 1
                    nb += 1
                else:
                    for _k in _keys:
                        ok[_k] = ok.get(_k, 0) + 1
            print("   %s：%d 件，非峽谷 %d 件" % (v, len(d), nb))
        y = {nm: 1 for nm, n in bad.items() if n > ok.get(nm, 0)}
        if y:
            out[str(yr)] = y
        print("  => %d：%d 個非峽谷道具名" % (yr, len(y)))
    # 人工補充：DDragon 的 maps 旗標認不出、但確定不是召喚峽谷的（中譯與英文名都要收，
    # 版本改動頁兩種寫法都會出現）。2026-07-31 使用者點名：月華法刃 Moonflair Spellblade
    MANUAL = {
        2013: ["月華法刃", "Moonflair Spellblade", "光之使者", "Lightbringer",
               "海克斯清除者", "Hextech Sweeper", "格雷提燈", "Grez's Spectral Lantern",
               "烏莉特的法帽", "Ohmwrecker", "奧丁面紗", "Odyn's Veil"],
        2014: ["月華法刃", "Moonflair Spellblade", "光之使者", "Lightbringer"],
        2015: ["月華法刃", "Moonflair Spellblade", "光之使者", "Lightbringer"],
    }
    for yr, names in MANUAL.items():
        y2 = out.setdefault(str(yr), {})
        for nm in names:
            y2[nm] = 1
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.ITEM_NONSR=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";")
    print("")
    print("OK item_nonsr.js：%d 筆（%d 個年份）" % (sum(len(v) for v in out.values()), len(out)))


if __name__ == "__main__":
    main()
