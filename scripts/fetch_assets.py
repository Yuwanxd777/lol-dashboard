# -*- coding: utf-8 -*-
"""
歷史資產索引：道具／符文／英雄的「歷代圖示＋服役年份＋中英名對照」→ assets.js

解決三件事：
 1) 舊道具在歷史年份沒圖（圖示 URL 被改寫成該年版本，但該道具那年不存在／id 不同 → 404）
 2) 舊符文只顯示英文名沒有圖（wiki 改動行用英文名，現行 zh 對照表查不到）
 3) 圖鑑詳情要能列出「歷代頭像 + 服役年份」（Riot 改過圖的會分段顯示）

做法：每年取該年最後一版 DDragon（HIST_VER），抓 zh_TW + en_US 的 item/runesReforged/champion，
記錄每個 id 在哪些年存在、每年的圖檔名與圖片雜湊（雜湊相同＝同一張圖 → 前端合併成一段年份區間）。

用法：
    python scripts\fetch_assets.py            # 有快取就沿用（只補新年份）
    python scripts\fetch_assets.py --force    # 全部重抓
圖片雜湊會下載每年的小圖（約 6000 張、~30MB），第一次跑約 5-10 分鐘，之後永久快取。
"""
import json, os, sys, time, hashlib, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "csv_cache", "assets_cache.json")
OUT = os.path.join(ROOT, "assets.js")
CDN = "https://ddragon.leagueoflegends.com/cdn"
FORCE = "--force" in sys.argv
NOHASH = "--nohash" in sys.argv          # 只建名稱/年份索引，不下載圖片算雜湊（快，但沒有「歷代頭像」分段）

# 各年最後一版（與 index.html 的 HIST_VER 一致；當年用最新版）
HIST_VER = {2014: "4.21.5", 2015: "5.24.2", 2016: "6.24.1", 2017: "7.24.2", 2018: "8.24.1",
            2019: "9.24.2", 2020: "10.25.1", 2021: "11.24.1", 2022: "12.23.1", 2023: "13.24.1",
            2024: "14.24.1", 2025: "15.24.1"}

def gj(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

try:
    from PIL import Image
    import io as _io
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False

SIG_N = 16   # 感知簽章：縮成 16×16 灰階（256 值）→ 比對「平均像素差」判斷是否同一張圖

def img_sig(url):
    """感知簽章（不是 md5）：把圖縮成 16×16 灰階的 hex 字串。
    為何不用 md5：Riot 常把同一張圖重新壓縮或改尺寸（120→128），位元組變了但畫面沒變，
    md5 會把它們當成「換圖」→ 卡瑪其實沒改過卻分成 3 段。改用縮圖像素比對就能忽略壓縮雜訊。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        if not _HAS_PIL:
            return "md5:" + hashlib.md5(data).hexdigest()[:10]   # 沒裝 PIL → 退回 md5（會過度分段，但不會壞）
        im = Image.open(_io.BytesIO(data)).convert("L").resize((SIG_N, SIG_N))
        return "".join("%02x" % p for p in im.getdata())
    except Exception:
        return None

def sig_same(a, b, thr=8):
    """兩個感知簽章是否「同一張圖」：平均像素差 < thr（校準：真改圖 16~41、重壓縮/改尺寸 0~2）"""
    if a is None or b is None:
        return False
    if a.startswith("md5:") or b.startswith("md5:"):
        return a == b
    if len(a) != len(b):
        return False
    va = bytes.fromhex(a); vb = bytes.fromhex(b)
    return sum(abs(x - y) for x, y in zip(va, vb)) / len(va) < thr

def year_versions():
    """每年取樣 4 個版本（年初/年中兩點/年末）。
    只取年末會漏掉「年中就被移除」的東西（貪婪獵人 Ravenous Hunter 2021 年中砍掉 → 年末版查無 → 沒圖沒中文名）。"""
    all_v = [v for v in gj("https://ddragon.leagueoflegends.com/api/versions.json") if v.count(".") == 2 and v[0].isdigit()]
    by_season = {}
    for v in all_v:
        try:
            major = int(v.split(".")[0])
        except ValueError:
            continue
        by_season.setdefault(major, []).append(v)
    def season_year(major):          # 4=2014 … 13=2023、14=2024、15=2025、16=2026（DDragon 主版號＝賽季）
        return 2010 + major if major <= 13 else 2010 + major
    out = {}
    for major, vs in by_season.items():
        y = season_year(major)
        if y < 2014:
            continue
        vs = sorted(set(vs), key=lambda s: [int(x) for x in s.split(".")])
        pick = [vs[0], vs[len(vs)//3], vs[2*len(vs)//3], vs[-1]] if len(vs) >= 4 else vs
        out[y] = sorted(set(pick), key=lambda s: [int(x) for x in s.split(".")])
    return out

def main():
    cur = gj("https://ddragon.leagueoflegends.com/api/versions.json")[0]
    years = dict(HIST_VER)
    years[time.localtime().tm_year] = cur
    YV = year_versions()

    cache = {}
    if os.path.exists(CACHE) and not FORCE:
        try:
            cache = json.load(open(CACHE, encoding="utf-8"))
        except Exception:
            cache = {}
    if cache.get("cur") != cur:
        cache.setdefault("kinds", {})          # 版本變了：當年那筆要重抓，其餘沿用
        cache["kinds"].pop(str(max(years)), None)
    cache.setdefault("kinds", {})

    # kinds[年_版本] = {"item":{id:{zh,en,img}}, "rune":…, "champ":…}；同一年會有多個取樣版本
    jobs = []
    for y in sorted(YV):
        for v in YV[y]:
            jobs.append((y, v))
    for y, v in jobs:
        key = "%d|%s" % (y, v)
        if key in cache["kinds"] and cache["kinds"][key].get("v") == v:
            continue
        ent = {"v": v, "item": {}, "rune": {}, "champ": {}}
        try:
            zi, ei = gj(f"{CDN}/{v}/data/zh_TW/item.json")["data"], gj(f"{CDN}/{v}/data/en_US/item.json")["data"]
            for iid, d in zi.items():
                ent["item"][iid] = {"zh": d["name"], "en": (ei.get(iid) or {}).get("name", ""),
                                    "img": d["image"]["full"]}
        except Exception as e:
            print(f"  {y} item 失敗：{e}")
        try:
            zr, er = gj(f"{CDN}/{v}/data/zh_TW/runesReforged.json"), gj(f"{CDN}/{v}/data/en_US/runesReforged.json")
            emap = {}
            for t in er:
                emap[t["id"]] = t["name"]
                for s in t["slots"]:
                    for r in s["runes"]:
                        emap[r["id"]] = r["name"]
            for t in zr:
                ent["rune"][str(t["id"])] = {"zh": t["name"], "en": emap.get(t["id"], ""), "img": t["icon"]}
                for s in t["slots"]:
                    for r in s["runes"]:
                        ent["rune"][str(r["id"])] = {"zh": r["name"], "en": emap.get(r["id"], ""), "img": r["icon"]}
        except Exception as e:
            print(f"  {y} rune 失敗：{e}")
        try:
            zc, ec = gj(f"{CDN}/{v}/data/zh_TW/champion.json")["data"], gj(f"{CDN}/{v}/data/en_US/champion.json")["data"]
            for cid, d in zc.items():
                ent["champ"][cid] = {"zh": d["name"], "en": (ec.get(cid) or {}).get("name", cid),
                                     "img": d["image"]["full"]}
        except Exception as e:
            print(f"  {y} champ 失敗：{e}")
        cache["kinds"][key] = ent
        print(f"  {y}（{v}）：道具 {len(ent['item'])}、符文 {len(ent['rune'])}、英雄 {len(ent['champ'])}")
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)

    cache["cur"] = cur

    # ── 每年每個 id 的「代表版本」＝該年最後一個「還存在」的取樣版本 ──────────
    # （年中被移除的東西才抓得到圖：貪婪獵人在 2021 年末的版本已經不存在了）
    KINDS = (("item", "img/item"), ("rune", "img"), ("champ", "img/champion"))
    rep = {k: {} for k, _ in KINDS}          # rep[kind][id][year] = (version, imgfile, zh, en)
    for key in sorted(cache["kinds"], key=lambda s: (int(s.split("|")[0]), [int(x) for x in s.split("|")[1].split(".")])):
        y = int(key.split("|")[0]); ent = cache["kinds"][key]; v = ent["v"]
        for kind, _ in KINDS:
            for iid, d in ent[kind].items():
                rep[kind].setdefault(iid, {})[y] = (v, d["img"], d["zh"], d["en"])

    def url_of(kind, v, f):
        return f"{CDN}/img/{f}" if kind == "rune" else f"{CDN}/{v}/img/{'item' if kind=='item' else 'champion'}/{f}"

    # ── 圖片感知簽章（判斷 Riot 哪一年「真的」換了圖）：只抓代表版本的圖 ──────
    hashes = cache.setdefault("sig", {})   # 用新 key "sig"（舊 "hash" 是 md5，語意不同）
    if not NOHASH:
        todo = [url_of(kind, v, f) for kind, _ in KINDS for iid, ys in rep[kind].items()
                for (v, f, _z, _e) in ys.values()]
        todo = [u for u in dict.fromkeys(todo) if u not in hashes]
        if todo:
            print(f"下載圖片算感知簽章：{len(todo)} 張…（PIL={_HAS_PIL}）")
            done = [0]
            def work(u):
                hashes[u] = img_sig(u)
                done[0] += 1
                if done[0] % 500 == 0:
                    print(f"   {done[0]}/{len(todo)}")
            with ThreadPoolExecutor(max_workers=12) as ex:
                list(ex.map(work, todo))
            json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)

    # ── 產出 assets.js ────────────────────────────────────────────────────
    out = {"years": {str(y): years[y] for y in sorted(years)}, "item": {}, "rune": {}, "champ": {}}
    for kind, _ in KINDS:
        acc = out[kind]
        for iid, ys in rep[kind].items():
            # zh/en＝最新年份的名字（預設顯示用）；nm＝歷代名字段（Riot 重用 id 時同一 id 會有多個名字，
            # 如符文 8135：2021「嗜血獵人 Ravenous Hunter」→ 2026「寶藏獵人 Treasure Hunter」）
            e = {"zh": "", "en": "", "y": [], "g": [], "nm": []}
            for y in sorted(ys):
                v, f, zh, en = ys[y]
                e["zh"], e["en"] = zh or e["zh"], en or e["en"]
                e["y"].append(y)
                # 名字段：與上一段同名就併年份，換名就開新段
                if e["nm"] and e["nm"][-1]["zh"] == zh and e["nm"][-1]["en"] == en:
                    e["nm"][-1]["y2"] = y
                else:
                    e["nm"].append({"zh": zh, "en": en, "y1": y, "y2": y})
                # 圖示段：感知簽章「近似」就併年份（忽略重壓縮/改尺寸），真換圖才開新段
                sg = hashes.get(url_of(kind, v, f))
                if e["g"] and sig_same(e["g"][-1].get("_sig"), sg):
                    e["g"][-1]["y2"] = y
                else:
                    e["g"].append({"_sig": sg, "v": v, "f": f, "y1": y, "y2": y})
            for g in e["g"]:
                g.pop("_sig", None)   # 簽章只用於分段，不寫進輸出（省體積）
            acc[iid] = e
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    raw = open(OUT, encoding="utf-8").read()
    open(OUT, "w", encoding="utf-8").write("window.LOL_ASSETS=" + raw + ";\n")
    print("✅ assets.js：道具 %d、符文 %d、英雄 %d（%d 年）"
          % (len(out["item"]), len(out["rune"]), len(out["champ"]), len(out["years"])))

if __name__ == "__main__":
    main()
