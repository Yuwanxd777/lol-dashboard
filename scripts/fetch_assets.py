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

抓不到時（2026-11-05 精進迴圈 #2607）：
 - 該版本整筆不進快取，下一班重抓。舊版把殘缺的 ent 存進去，該版本從此不再重抓。
   例外只有 8.x 以前的 runesReforged：DDragon 回 403 是本來就沒有。不存在的版本連 item.json 也回 403，
   所以 8.x 以後的 403 不能當「沒有」。
 - 圖片簽章抓不到不記 None，下一班重試。舊版記 None 後永遠不重試，還會切出假的換圖段（8.24.1 的 3637.png）。
 - 分類標籤抓不到沿用上一版 assets.js。
 - 連 2 個版本抓不到、或圖片連續 8 次連線失敗，這班就不再上網。
 - 道具或英雄一筆都沒有時不寫檔並 exit 1。
"""
import json, os, sys, time, hashlib, urllib.request, urllib.error
import re
# 經典服（LoL Classic，DDragon 內部代號 Jade_*）不是我們要的資料（2026-07-31 使用者回報：
# 英雄Tier 出現經典服頭像）——它的 zh/en 名稱與現行英雄**完全相同**，混進來會造成同名重複與圖片誤植。
# 日後若 Riot 再開別的分支服，一樣在這裡擋掉。
CLASSIC_RE = re.compile(r"^(Jade|Classic|Legacy)_", re.I)   # 分支服前綴：不進資料

from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "csv_cache", "assets_cache.json")
OUT = os.path.join(ROOT, "assets.js")
CDN = "https://ddragon.leagueoflegends.com/cdn"
FORCE = "--force" in sys.argv
NOHASH = "--nohash" in sys.argv          # 只建名稱/年份索引，不下載圖片算雜湊（快，但沒有「歷代頭像」分段）

# 各年最後一版（與 index.html 的 HIST_VER 一致；當年用最新版）
# 2013＝3.15.5（S3 最後一版，資產完整）。只有「實際發佈過的三段號」拿得到，
# lolpatch_3.15／3.15.3／4.1.1 這類寫法一律 403。與 index.html 的 HIST_VER 一致（2026-07-31）
HIST_VER = {2013: "3.15.5", 2014: "4.21.5", 2015: "5.24.2", 2016: "6.24.1", 2017: "7.24.2", 2018: "8.24.1",
            2019: "9.24.2", 2020: "10.25.1", 2021: "11.24.1", 2022: "12.23.1", 2023: "13.24.1",
            2024: "14.24.1", 2025: "15.24.1"}

RUNE_FROM_MAJOR = 8   # runesReforged 從 8.1.1 起才有（7.22～7.24 只有 en_US，zh_TW 是 403）
NET_TRIES = 2
GIVE_UP_VERSIONS = 2  # 連幾個版本抓不到就不再上網
GIVE_UP_IMGS = 8      # 圖片連續幾次連線失敗就不再上網（403／404 不算）

def _is_gone(e):
    return isinstance(e, urllib.error.HTTPError) and e.code in (403, 404)

def gj(url, timeout=30):
    """403／404 不重試（重試也一樣）；其他失敗試 NET_TRIES 次。"""
    for i in range(NET_TRIES):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if _is_gone(e) or i == NET_TRIES - 1:
                raise
            time.sleep(2)

def write_atomic(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)

def save_cache(cache):
    write_atomic(CACHE, json.dumps(cache, ensure_ascii=False))

def prev_ctag():
    """上一版 assets.js 的分類標籤；沒有或讀不出來回空。"""
    try:
        raw = open(OUT, encoding="utf-8").read()
        head = "window.LOL_ASSETS="
        if not raw.startswith(head):
            return {}
        return json.loads(raw[len(head):].rstrip().rstrip(";")).get("ctag") or {}
    except Exception:
        return {}

try:
    from PIL import Image
    import io as _io
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False

SIG_N = 16   # 感知簽章：縮成 16×16 灰階（256 值）→ 比對「平均像素差」判斷是否同一張圖

_img_fails = [0]      # 連續連線失敗次數
_img_gone = set()     # 這班回 403／404 的圖（目前 3 張 .dds，來源就沒有，每班問一次、不算警告）

def img_sig(url):
    """感知簽章（不是 md5）：把圖縮成 16×16 灰階的 hex 字串。
    為何不用 md5：Riot 常把同一張圖重新壓縮或改尺寸（120→128），位元組變了但畫面沒變，
    md5 會把它們當成「換圖」→ 卡瑪其實沒改過卻分成 3 段。改用縮圖像素比對就能忽略壓縮雜訊。"""
    if _img_fails[0] >= GIVE_UP_IMGS:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        _img_fails[0] = 0
    except Exception as e:
        if _is_gone(e):
            _img_gone.add(url)
        else:
            _img_fails[0] += 1
        return None
    try:
        if not _HAS_PIL:
            return "md5:" + hashlib.md5(data).hexdigest()[:10]   # 沒裝 PIL → 退回 md5（會過度分段，但不會壞）
        im = Image.open(_io.BytesIO(data)).convert("L").resize((SIG_N, SIG_N))
        return im.tobytes().hex()   # L 模式每像素 1 byte，等於舊寫法的逐像素 %02x
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

def same_seg(prev_sig, prev_f, sig, f):
    """圖示要不要併進上一段。簽章不明（抓不到）不算換圖：檔名相同就併。"""
    if prev_sig is None or sig is None:
        return prev_f == f
    return sig_same(prev_sig, sig)

def fetch_version(y, v):
    """抓一個版本。回 (ent, 失敗清單)；失敗清單非空代表這筆不可進快取。"""
    ent = {"v": v, "item": {}, "rune": {}, "champ": {}}
    failed = []
    major = int(v.split(".")[0])
    try:
        zi, ei = gj(f"{CDN}/{v}/data/zh_TW/item.json")["data"], gj(f"{CDN}/{v}/data/en_US/item.json")["data"]
        for iid, d in zi.items():
            ent["item"][iid] = {"zh": d["name"], "en": (ei.get(iid) or {}).get("name", ""),
                                "img": d["image"]["full"]}
        if not ent["item"]:
            raise ValueError("回傳 0 筆")
    except Exception as e:
        ent["item"] = {}
        failed.append("item")
        print(f"  ⚠ {y}（{v}）item 失敗：{e}")
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
        if not ent["rune"] and major >= RUNE_FROM_MAJOR:
            raise ValueError("回傳 0 筆")
    except Exception as e:
        ent["rune"] = {}
        if not (_is_gone(e) and major < RUNE_FROM_MAJOR):   # 8.x 以前本來就沒有
            failed.append("rune")
            print(f"  ⚠ {y}（{v}）rune 失敗：{e}")
    try:
        zc, ec = gj(f"{CDN}/{v}/data/zh_TW/champion.json")["data"], gj(f"{CDN}/{v}/data/en_US/champion.json")["data"]
        zc = {k: v2 for k, v2 in zc.items() if not CLASSIC_RE.match(k)}   # 濾掉經典服（見檔頭 CLASSIC_RE）
        ec = {k: v2 for k, v2 in ec.items() if not CLASSIC_RE.match(k)}
        for cid, d in zc.items():
            ent["champ"][cid] = {"zh": d["name"], "en": (ec.get(cid) or {}).get("name", cid),
                                 "img": d["image"]["full"]}
        if not ent["champ"]:
            raise ValueError("回傳 0 筆")
    except Exception as e:
        ent["champ"] = {}
        failed.append("champ")
        print(f"  ⚠ {y}（{v}）champ 失敗：{e}")
    return ent, failed

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
        if y < 2013:
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
    # 快取自我清理：抓取當下的過濾（見下方 CLASSIC_RE）只擋「這次新抓的版本」，
    # 之前抓過、已經帶著分支服的快取條目會原封不動流進輸出——2026-08-06 使用者第二次回報
    # 英雄Tier 出現舊版頭像，就是 2026|16.15.1 這筆卡在快取裡。舊快取一律就地清掉，不必重抓。
    _cl = 0
    for _ent in cache["kinds"].values():
        for _k in ("item", "rune", "champ"):
            _m = _ent.get(_k)
            if not _m:
                continue
            for _id in [x for x in _m if CLASSIC_RE.match(x)]:
                del _m[_id]; _cl += 1
    if _cl:
        print(f"（快取清掉 {_cl} 筆分支服資料）")

    # kinds[年_版本] = {"item":{id:{zh,en,img}}, "rune":…, "champ":…}；同一年會有多個取樣版本
    jobs = []
    for y in sorted(YV):
        for v in YV[y]:
            jobs.append((y, v))
    bad_run = skipped = 0
    for y, v in jobs:
        key = "%d|%s" % (y, v)
        if key in cache["kinds"] and cache["kinds"][key].get("v") == v:
            continue
        if bad_run >= GIVE_UP_VERSIONS:
            skipped += 1
            continue
        ent, failed = fetch_version(y, v)
        if failed:
            bad_run += 1
            print(f"  ⚠ {y}（{v}）抓不到 {'、'.join(failed)}：這版不進快取，下一班重抓")
            continue
        bad_run = 0
        cache["kinds"][key] = ent
        print(f"  {y}（{v}）：道具 {len(ent['item'])}、符文 {len(ent['rune'])}、英雄 {len(ent['champ'])}")
        save_cache(cache)
    if skipped:
        print(f"  ⚠ 連 {GIVE_UP_VERSIONS} 個版本抓不到，其餘 {skipped} 個版本這班不再上網")

    cache["cur"] = cur

    # ── 每年每個 id 的「代表版本」＝該年最後一個「還存在」的取樣版本 ──────────
    # （年中被移除的東西才抓得到圖：貪婪獵人在 2021 年末的版本已經不存在了）
    KINDS = (("item", "img/item"), ("rune", "img"), ("champ", "img/champion"))
    rep = {k: {} for k, _ in KINDS}          # rep[kind][id][year] = (version, imgfile, zh, en)
    for key in sorted(cache["kinds"], key=lambda s: (int(s.split("|")[0]), [int(x) for x in s.split("|")[1].split(".")])):
        y = int(key.split("|")[0]); ent = cache["kinds"][key]; v = ent["v"]
        for kind, _ in KINDS:
            for iid, d in ent[kind].items():
                if CLASSIC_RE.match(iid):        # 輸出層再擋一次：任何來源（快取／上游）都進不了 assets.js
                    continue
                rep[kind].setdefault(iid, {})[y] = (v, d["img"], d["zh"], d["en"])

    def url_of(kind, v, f):
        return f"{CDN}/img/{f}" if kind == "rune" else f"{CDN}/{v}/img/{'item' if kind=='item' else 'champion'}/{f}"

    # ── 圖片感知簽章（判斷 Riot 哪一年「真的」換了圖）：只抓代表版本的圖 ──────
    hashes = cache.setdefault("sig", {})   # 用新 key "sig"（舊 "hash" 是 md5，語意不同）
    if not NOHASH:
        todo = [url_of(kind, v, f) for kind, _ in KINDS for iid, ys in rep[kind].items()
                for (v, f, _z, _e) in ys.values()]
        todo = [u for u in dict.fromkeys(todo) if hashes.get(u) is None]   # 舊快取記的 None 也重試
        if todo:
            print(f"下載圖片算感知簽章：{len(todo)} 張…（PIL={_HAS_PIL}）")
            done = [0]
            def work(u):
                sg = img_sig(u)
                if sg is None:              # 抓不到不記，下一班重試
                    hashes.pop(u, None)
                else:
                    hashes[u] = sg
                done[0] += 1
                if done[0] % 500 == 0:
                    print(f"   {done[0]}/{len(todo)}")
            with ThreadPoolExecutor(max_workers=12) as ex:
                list(ex.map(work, todo))
            miss = sum(1 for u in todo if hashes.get(u) is None and u not in _img_gone)
            if _img_gone:
                print(f"  （來源回 403／404 的圖 {len(_img_gone)} 張，沒有簽章）")
            if miss:
                print(f"  ⚠ 圖片簽章 {miss}/{len(todo)} 張抓不到，下一班重試"
                      + ("（連線連續失敗，這班中途停手）" if _img_fails[0] >= GIVE_UP_IMGS else ""))
            save_cache(cache)

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
                if e["g"] and same_seg(e["g"][-1].get("_sig"), e["g"][-1]["f"], sg, f):
                    e["g"][-1]["y2"] = y
                    e["g"][-1]["_sig"] = e["g"][-1].get("_sig") or sg   # 上一段簽章不明時，用這張當比對基準
                else:
                    e["g"].append({"_sig": sg, "v": v, "f": f, "y1": y, "y2": y})
            for g in e["g"]:
                g.pop("_sig", None)   # 簽章只用於分段，不寫進輸出（省體積）
            acc[iid] = e
    # 英雄分類標籤（模擬BP 選角評分的「陣容」項用）：只取**現行版本**，不需要逐年歷史——
    # 那一項問的是「這套陣容配置合不合理」，用當下的分類即可。
    #   t＝Riot 官方分類（Tank/Fighter/Mage/Assassin/Marksman/Support）
    #   i＝設計面評分 0~10 的 [攻擊, 防禦, 魔法]，用來判斷傷害類型偏向（比賽資料沒有物理/魔法拆分）
    try:
        _cj = gj(f"{CDN}/{cur}/data/en_US/champion.json")["data"]
        if not _cj:
            raise ValueError("回傳 0 筆")
        out["ctag"] = {cid: {"t": d.get("tags") or [],
                             "i": [(d.get("info") or {}).get("attack", 0),
                                   (d.get("info") or {}).get("defense", 0),
                                   (d.get("info") or {}).get("magic", 0)]}
                       for cid, d in _cj.items() if not CLASSIC_RE.match(cid)}
        print(f"  英雄分類標籤：{len(out['ctag'])} 隻")
    except Exception as e:
        out["ctag"] = prev_ctag()
        print(f"  ⚠ 英雄分類標籤失敗，沿用上一版 {len(out['ctag'])} 隻：{e}")
    if not out["item"] or not out["champ"]:   # 快取壞掉又抓不到才會走到這裡：保留線上那份
        print(f"❌ 道具 {len(out['item'])}、英雄 {len(out['champ'])}：不寫 assets.js")
        sys.exit(1)
    write_atomic(OUT, "window.LOL_ASSETS=" + json.dumps(out, ensure_ascii=False) + ";\n")
    print("✅ assets.js：道具 %d、符文 %d、英雄 %d（%d 年）、分類標籤 %d"
          % (len(out["item"]), len(out["rune"]), len(out["champ"]), len(out["years"]), len(out.get("ctag") or {})))

if __name__ == "__main__":
    main()
