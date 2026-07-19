# -*- coding: utf-8 -*-
"""為 soloq_accounts.json 中『有 riotId、無 dpmPuuid、非 bad』的帳號（OBGG 新加入者）用 dpm 反查補 dpmPuuid。
OBGG 的 puuid 跟 dpm 自家加密 puuid 不同，一定要用 dpm 搜尋 gameName、比對完整 RiotID 取 puuid 當 dpmPuuid。
補上後 fetch_soloq_update.py（增量）/ fetch_soloq_year.py --missing（新選手整年）才抓得到逐場。
重用 merge_scoregg_gaps 驗證過的 dpm 搜尋端點（/v1/search?gameName=）＋Cloudflare 過盤查。
每 10 筆存一次檔（中途中斷保留進度）。best-effort：過不了 Cloudflare 就跳過、不擋更新鏈。
用法：python scripts\\resolve_obgg_dpmpuuid.py
"""
import io, sys, json, os, time, urllib.parse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS = os.path.join(HERE, "soloq_accounts.json")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
FORMATS = ["/v1/search?gameName=__PROBE__", "/v1/players/search?gameName=__PROBE__",
           "/v1/search/players?query=__PROBE__", "/v1/players?search=__PROBE__"]
JSQ = ("async(u)=>{try{const r=await fetch(u); if(!r.ok)return {st:r.status};"
       "return {st:200, j:await r.json()};}catch(e){return {err:String(e).slice(0,80)}}}")


def _launch(p):
    for kw in ({"channel": "chrome"}, {"channel": "msedge"}, {}):
        try:
            return p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"], **kw)
        except Exception:
            continue
    raise RuntimeError("找不到可用瀏覽器")


def _warm(pg):
    for wait in (4, 14, 25):
        time.sleep(wait)
        try:
            st = pg.evaluate("async()=>{const r=await fetch('/v1/esport/soloq/top-teams');return r.status;}")
        except Exception:
            st = 0
        if st == 200:
            return True
        print(f"  Cloudflare 盤查中（{st}），續等…", flush=True)
    return False


def main():
    acc = json.load(open(ACCOUNTS, encoding="utf-8"))
    todo = [a for a in acc if a.get("riotId") and not a.get("dpmPuuid") and not a.get("bad")]
    print(f"待反查 dpmPuuid 帳號: {len(todo)}", flush=True)
    if not todo:
        return
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("（未安裝 playwright，略過 dpmPuuid 反查）"); return

    good = {"f": None}
    with sync_playwright() as p:
        b = _launch(p); pg = b.new_page(user_agent=UA)
        pg.goto("https://dpm.lol/", wait_until="domcontentloaded")
        if not _warm(pg):
            print("✗ 過不了 Cloudflare，本次略過（下次再補）"); b.close(); return

        def query(nick):
            enc = urllib.parse.quote(nick, safe="")
            fmts = ([good["f"]] + [f for f in FORMATS if f != good["f"]]) if good["f"] else FORMATS
            last = {"st": 0}
            for f in fmts:
                for _ in range(2):
                    last = pg.evaluate(JSQ, f.replace("__PROBE__", enc))
                    if last.get("st") == 200:
                        good["f"] = f; return last
                    if last.get("st") in (429, 403):
                        time.sleep(6)
            return last

        def pick_arr(j):
            if isinstance(j, list):
                return j
            for k in ("players", "data", "results", "items"):
                v = j.get(k)
                if isinstance(v, list):
                    return [(e.get("player") if isinstance(e, dict) and isinstance(e.get("player"), dict) else e) for e in v]
            return []

        n_ok = n_fail = done = 0
        for a in todo:
            rid = a["riotId"]; gn, _, tl = rid.partition("#")
            r = query(gn); hit = None
            if r.get("st") == 200:
                for c in pick_arr(r["j"]):
                    if not isinstance(c, dict):
                        continue
                    if (str(c.get("gameName", "")).strip().lower() == gn.strip().lower()
                            and str(c.get("tagLine", "")).strip().lower() == tl.strip().lower()
                            and c.get("puuid")):
                        hit = c; break
            if hit:
                a["dpmPuuid"] = hit["puuid"]; n_ok += 1
                print(f"  ✓ {a.get('team')}|{a.get('player')} {rid}", flush=True)
            else:
                n_fail += 1
                print(f"  ✗ {a.get('team')}|{a.get('player')} {rid}（查無相符，st={r.get('st')}）", flush=True)
            done += 1
            if done % 10 == 0:
                json.dump(acc, open(ACCOUNTS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            time.sleep(0.8)
        b.close()
    json.dump(acc, open(ACCOUNTS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n完成：補上 {n_ok} 個 dpmPuuid｜查無 {n_fail} 個 → soloq_accounts.json", flush=True)


if __name__ == "__main__":
    main()
