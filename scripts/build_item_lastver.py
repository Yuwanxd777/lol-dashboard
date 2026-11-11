# -*- coding: utf-8 -*-
"""
年中被移除的道具 → 它在那一年「最後出現的版本」：item_lastver.js（window.ITEM_LASTVER={年:{版本:[道具 id]}}）

歷史年份的道具提示讀的是該年年末版本的 DDragon item.json。年中被移除的道具（2020 最嚴重：10.23 季前
大改一次拿掉 26 件）年末版本已經沒有，提示就落回 2026 的現行資料。這張小表讓前端在查不到時，
只補抓表上列的那幾個版本（一年 0～6 份），用當年真正的資料畫提示。

表用道具 id 當鍵（中英文共用）：assets.js 記了每件道具服役的年份，年末版本沒有這個 id 的才列入。

不在每日管線裡：過去年份的版本不會再變。**每年換季（多一個歷史年份）之後手動跑一次。**
快取 csv_cache/item_hist/item_<版本>.json（過去版本的 item.json 不會變，抓過就不再抓）。

用法：python scripts/build_item_lastver.py
"""
import io, json, os, re, shutil, sys, urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "csv_cache", "item_hist")
SEED = os.path.join(ROOT, "autopilot", "_m2647_dd")     # 之前量測留下的同一批檔，有就直接沿用
OUT = os.path.join(ROOT, "item_lastver.js")
DD = "https://ddragon.leagueoflegends.com"

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read()

def item_json(ver):
    """→ data 字典；這一版沒有 item.json（很早期的版本）回 None"""
    p = os.path.join(CACHE, f"item_{ver}.json")
    if not os.path.exists(p):
        s = os.path.join(SEED, f"item_{ver}.json")
        if os.path.exists(s):
            shutil.copyfile(s, p)
        else:
            try:
                raw = fetch(f"{DD}/cdn/{ver}/data/zh_TW/item.json")
                json.loads(raw)
            except Exception as e:
                print(f"   （{ver} 抓不到：{e}）")
                return None
            with open(p, "wb") as f:
                f.write(raw)
    try:
        return json.load(io.open(p, encoding="utf-8"))["data"]
    except Exception:
        return None

def main():
    os.makedirs(CACHE, exist_ok=True)
    t = io.open(os.path.join(ROOT, "assets.js"), encoding="utf-8").read()
    A = json.loads(t[t.index("{"):t.rindex("}") + 1])
    years = {int(y): v for y, v in A["years"].items()}
    cur = max(years)
    vers = json.loads(fetch(f"{DD}/api/versions.json"))          # 新到舊
    out, total = {}, 0
    for y in sorted(years):
        if y == cur:
            continue
        end = years[y]
        endd = item_json(end)
        if endd is None:
            print(f"⚠ {y} 年末版本 {end} 讀不到，跳過")
            continue
        major = end.split(".")[0]
        older = [v for v in vers if re.fullmatch(r"\d+\.\d+\.\d+", v) and v.split(".")[0] == major]
        older = older[older.index(end) + 1:] if end in older else older
        # 13.x 起同名的模式複本是長 id，前端一律以短 id 為準，這裡也只看短 id
        want = [i for i, e in A["item"].items() if y in (e.get("y") or []) and i not in endd and len(i) <= 4]
        got = {}
        for v in older:
            left = [i for i in want if i not in got]
            if not left:
                break
            d = item_json(v)
            if not d:
                continue
            for i in left:
                if i in d:
                    got[i] = v
        by = {}
        for i, v in got.items():
            by.setdefault(v, []).append(i)
        miss = [i for i in want if i not in got]
        if by:
            out[str(y)] = {v: sorted(by[v], key=int) for v in sorted(by)}
        total += len(got)
        print(f"{y} 年末 {end}：年末沒有 {len(want)} 件 → 找到最後版本 {len(got)} 件（{len(by)} 個版本）"
              + (f"；整年都找不到 {len(miss)} 件：{miss[:12]}" if miss else ""))
    if not out:
        print("⚠ 一件都沒有 ⇒ 不寫檔")
        return 1
    js = "window.ITEM_LASTVER=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";"
    tmp = OUT + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(js)
    os.replace(tmp, OUT)
    print(f"✅ item_lastver.js：{len(out)} 個年份、{total} 件道具、{sum(len(v) for v in out.values())} 個版本，{len(js)} bytes")
    return 0

if __name__ == "__main__":
    sys.exit(main())
