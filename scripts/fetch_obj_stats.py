# -*- coding: utf-8 -*-
"""物件（塔/野怪/小兵）現行數值 → obj_stats.js（圖鑑物件詳情「屬性」卡）
來源＝Community Dragon bin.json（lol-monster-stats-source 判例：野怪數值正解）：
  - game/data/characters/turret/turret.bin.json 的 CharacterRecords/Root＝基準塔（外塔）數值
  - game/data/maps/shipping/map11/map11.bin.json 的 Characters/{單位}/CharacterRecords/Root＝各野怪/小兵
快取 csv_cache/（<20h 不重抓）；欄位：hp/hpLv/ad/adLv/ar/arLv/mr/mrLv/as/rng/ms（缺的省略）。
用法：python scripts\fetch_obj_stats.py [--force]
"""
import io, sys, json, os, re, time, urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
CACHE = os.path.join(ROOT, "csv_cache"); OUT = os.path.join(ROOT, "obj_stats.js")
FORCE = "--force" in sys.argv
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0"}
CD = "https://raw.communitydragon.org/latest/game/data/"

# 顯示名（圖鑑物件清單的 n）→ map11 內的單位鍵；塔另走 turret.bin Root
UNITS = {
    "巴龍": "SRU_Baron", "遠古龍": "sru_dragon_elder", "元素龍（小龍總覽）": "sru_dragon_fire",
    "預示者": "SRU_RiftHerald", "虛空幼蟲（巢蟲）": "SRU_Horde", "亞塔坎（Atakhan）": "SRU_Atakhan",
    "藍 Buff": "SRU_Blue", "紅 Buff": "SRU_Red", "河蟹": "Sru_Crab",
    "雙石像": "SRU_Krug", "啾吉": "SRU_Gromp", "六鳥": "SRU_Razorbeak", "三狼": "SRU_Murkwolf",
    "小兵（Minions）": "SRU_OrderMinionMelee", "超級士兵（Super Minion）": "SRU_OrderMinionSuper",
}
TOWERS = ["外塔（一塔）", "內塔（二塔）", "高地塔（三塔）", "主堡雙塔"]
FIELDS = [("baseHP", "hp"), ("hpPerLevel", "hpLv"), ("baseDamage", "ad"), ("damagePerLevel", "adLv"),
          ("baseArmor", "ar"), ("armorPerLevel", "arLv"), ("baseSpellBlock", "mr"), ("spellBlockPerLevel", "mrLv"),
          ("attackSpeed", "as"), ("attackRange", "rng"), ("baseMoveSpeed", "ms")]


def get(url, fn):
    p = os.path.join(CACHE, fn)
    if not FORCE and os.path.exists(p) and time.time() - os.path.getmtime(p) < 20 * 3600:
        return open(p, encoding="utf-8", errors="replace").read()
    req = urllib.request.Request(url, headers=UA)
    s = urllib.request.urlopen(req, timeout=120).read().decode("utf-8", "replace")
    os.makedirs(CACHE, exist_ok=True)
    open(p, "w", encoding="utf-8").write(s)
    return s


def seg_stats(seg):
    out = {}
    for src, dst in FIELDS:
        m = re.search(r'"' + src + r'(?:Modifiable)?"\s*:\s*(?:\{"baseValue":([\d.\-]+)|([\d.\-]+))', seg)
        if m:
            v = float(m.group(1) or m.group(2))
            out[dst] = round(v, 3) if v % 1 else int(v)
    return out


def main():
    stats = {}
    # 塔：turret.bin Root（外塔基準；內/高地/主堡雙塔共用基準值，加成由遊戲腳本疊加）
    t = get(CD + "characters/turret/turret.bin.json", "turret.bin.json")
    i = t.find('"Characters/Turret/CharacterRecords/Root"')
    if i >= 0:
        st = seg_stats(t[i:i + 4000])
        st.pop("ms", None)
        for nm in TOWERS:
            stats[nm] = dict(st)
    # 野怪/小兵：各單位自己的 bin（map11 只放參照，本體在 characters/{unit}/{unit}.bin.json）
    for disp, unit in UNITS.items():
        u = unit.lower()
        try:
            s = get(CD + f"characters/{u}/{u}.bin.json", f"objbin_{u}.json")
        except Exception as e:
            print(f"  ？{disp}（{u}）抓不到：{e}"); continue
        j = s.find('/CharacterRecords/Root"')
        if j < 0:
            print(f"  ？{disp}（{u}）無 Root 紀錄"); continue
        st = seg_stats(s[j:j + 4500])
        if st: stats[disp] = st
        time.sleep(0.3)
    open(OUT, "w", encoding="utf-8").write("window.OBJ_STATS=" + json.dumps(stats, ensure_ascii=False) + ";")
    print(f"寫出 {OUT}：{len(stats)} 個物件屬性")
    for k in ("外塔（一塔）", "巴龍", "小兵（Minions）"):
        print(" ", k, stats.get(k))


if __name__ == "__main__":
    main()
