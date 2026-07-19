# -*- coding: utf-8 -*-
"""產生 item_nostore.js（window.ITEM_NOSTORE）＝CDragon 標記 inStore=False 的召喚峽谷區道具中文名清單。
原因：DDragon 是殭屍資料——遊戲裡已移除的道具（如闇夜收割者 24.01 移除）仍留在 DDragon item.json，
甚至還掛在其他道具的 into（可合成）裡；DDragon 版本 diff 抓不到（它還在）。CDragon 的 inStore=False
才是「已下架」的可靠訊號。圖鑑「當前年份」用這份把已移除道具從清單/合成鏈濾掉（歷史年份仍用 assets.js 服役年份判定）。
用法：python scripts\\fetch_item_nostore.py
"""
import io, sys, os, re, json, urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
UA = {"User-Agent": "Mozilla/5.0"}


def g(u):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read())


def clname(n):  # 對齊 index.html clItemName：去括號尾綴、收全形冒號後空白
    n = re.sub(r"：\s+", "：", str(n or ""))
    n = re.sub(r"[（(][^（）()]*[)）]", "", n)
    return n.strip()


def main():
    ddv = g("https://ddragon.leagueoflegends.com/api/versions.json")[0]
    dd = g(f"https://ddragon.leagueoflegends.com/cdn/{ddv}/data/zh_TW/item.json")["data"]
    cd = g("https://raw.communitydragon.org/latest/plugins/rcp-be-lol-game-data/global/default/v1/items.json")
    instore = {str(x.get("id")): x.get("inStore") for x in cd}
    nostore = {}
    for i, d in dd.items():
        if int(i) >= 200000:              # 競技場/特殊模式 id（srItemOK 已排除），不列
            continue
        if instore.get(i) is False:       # CDragon 標為已下架＝遊戲裡已移除
            nm = clname(d.get("name"))
            if nm:
                nostore[nm] = 1
    out = os.path.join(ROOT, "item_nostore.js")
    open(out, "w", encoding="utf-8").write("window.ITEM_NOSTORE=" + json.dumps(nostore, ensure_ascii=False) + ";\n")
    print(f"寫出 item_nostore.js：{len(nostore)} 個已下架道具（CDragon inStore=False，id<200000）")
    print("範例:", list(nostore)[:25])


if __name__ == "__main__":
    main()
