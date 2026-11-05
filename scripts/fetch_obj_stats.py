# -*- coding: utf-8 -*-
"""物件（塔/野怪/小兵）現行數值 → obj_stats.js（圖鑑物件詳情「屬性」卡）
來源＝Community Dragon bin.json（lol-monster-stats-source 判例：野怪數值正解）：
  - game/data/characters/turret/turret.bin.json 的 CharacterRecords/Root＝基準塔（外塔）數值
  - game/data/maps/shipping/map11/map11.bin.json 的 Characters/{單位}/CharacterRecords/Root＝各野怪/小兵
快取 csv_cache/（<20h 不重抓）；欄位：hp/hpLv/ad/adLv/ar/arLv/mr/mrLv/as/rng/ms（缺的省略）。
用法：python scripts\fetch_obj_stats.py [--force]
"""
import io, sys, json, os, re, time, urllib.request, urllib.error

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


# 抓不到時的處置（2026-11-05 精進迴圈 #2605）：11-05 10:00 班紅 Buff 交握逾時，舊版吞掉例外、少一隻照寫 ⇒
# 上線的圖鑑少一張屬性卡，還卡了 120 秒。現在 重試 → 過期快取 → 上一版 obj_stats.js；全掛才不寫檔。
TIMEOUT = 30      # 單次逾時（這些檔都不大，慢到 30 秒就不值得等）
TRIES = 2         # 同一個檔最多試幾次
RETRY_WAIT = 3    # 重試前等幾秒
DOWN_AFTER = 2    # 連續幾個檔整個抓不到就當來源掛了，後面不再上網（否則來源全掛時每個檔都要等滿）
_fails = 0        # 連續抓不到的檔數


def _fetch(url):
    """回傳內容；4xx 不重試（來源明確說沒有），其餘重試到 TRIES 次。連續失敗達 DOWN_AFTER 就不再上網。"""
    global _fails
    if _fails >= DOWN_AFTER:
        raise OSError(f"來源連續 {_fails} 個檔抓不到，不再嘗試")
    err = None
    for i in range(TRIES):
        if i:
            time.sleep(RETRY_WAIT)
        try:
            req = urllib.request.Request(url, headers=UA)
            s = urllib.request.urlopen(req, timeout=TIMEOUT).read().decode("utf-8", "replace")
            _fails = 0
            return s
        except urllib.error.HTTPError as e:
            err = e
            if 400 <= e.code < 500:
                raise      # 伺服器有回應，不算來源掛了
        except Exception as e:
            err = e
    _fails += 1
    raise err


def get(url, fn):
    p = os.path.join(CACHE, fn)
    if not FORCE and os.path.exists(p) and time.time() - os.path.getmtime(p) < 20 * 3600:
        return open(p, encoding="utf-8", errors="replace").read()
    try:
        s = _fetch(url)
    except Exception as e:
        if os.path.exists(p):   # 不碰 mtime：快取維持過期，下一班才會再試
            print(f"  ⚠ {fn} 抓不到（{e}），先用過期快取")
            return open(p, encoding="utf-8", errors="replace").read()
        raise
    os.makedirs(CACHE, exist_ok=True)
    open(p, "w", encoding="utf-8").write(s)
    return s


def load_prev():
    """上一版 obj_stats.js；讀不到或壞掉回空表。"""
    try:
        t = open(OUT, encoding="utf-8").read()
        return json.loads(t[t.index("{"):t.rindex("}") + 1])
    except (OSError, ValueError):
        return {}


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
    prev = load_prev()
    kept = []

    def keep(disp, why):
        """這一項這班拿不到：有上一版就沿用，一項都不因為一次網路問題從線上消失。"""
        if disp in prev:
            stats[disp] = prev[disp]
            kept.append(disp)
            print(f"  ⚠ {disp}：{why}，沿用上一版")
        else:
            print(f"  ？{disp}：{why}，上一版也沒有")

    # 塔：turret.bin Root（外塔基準；內/高地/主堡雙塔共用基準值，加成由遊戲腳本疊加）
    st, why = {}, "turret.bin 無 Root 紀錄"
    try:
        t = get(CD + "characters/turret/turret.bin.json", "turret.bin.json")
        i = t.find('"Characters/Turret/CharacterRecords/Root"')
        if i >= 0:
            st = seg_stats(t[i:i + 4000])
            st.pop("ms", None)
    except Exception as e:
        why = f"turret.bin 抓不到（{e}）"
    for nm in TOWERS:
        if st:
            stats[nm] = dict(st)
        else:
            keep(nm, why)
    # 野怪/小兵：各單位自己的 bin（map11 只放參照，本體在 characters/{unit}/{unit}.bin.json）
    for disp, unit in UNITS.items():
        u = unit.lower()
        try:
            s = get(CD + f"characters/{u}/{u}.bin.json", f"objbin_{u}.json")
        except Exception as e:
            keep(disp, f"抓不到（{e}）"); continue
        j = s.find('/CharacterRecords/Root"')
        st = seg_stats(s[j:j + 4500]) if j >= 0 else {}
        if st:
            stats[disp] = st
        else:
            keep(disp, "無 Root 紀錄")
        time.sleep(0.3)
    if not stats:     # 全掛又沒有上一版：不要寫一個空表蓋掉線上
        print("✗ 一個物件都拿不到，不寫檔")
        sys.exit(1)
    open(OUT, "w", encoding="utf-8").write("window.OBJ_STATS=" + json.dumps(stats, ensure_ascii=False) + ";")
    print(f"寫出 {OUT}：{len(stats)} 個物件屬性" + (f"（其中 {len(kept)} 個沿用上一版）" if kept else ""))
    for k in ("外塔（一塔）", "巴龍", "小兵（Minions）"):
        print(" ", k, stats.get(k))


if __name__ == "__main__":
    main()
