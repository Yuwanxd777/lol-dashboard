# -*- coding: utf-8 -*-
"""
英文版英雄技能數值：skills_en.js（window.CHAMP_SKILLS_EN={v,d}）

英文模式原本走 DDragon 原文，692 個技能只有 83 個帶數字（原文的 tooltip 是 {{ token }} 空殼）。
這支沿用 fetch_skills 的求值核心，只把三樣東西換成英文：
  ①DDragon 的 zh_TW 換 en_US  ②被動模板換英文字串表  ③render_val 吐出的中文單位換成英文
另外英文需要空白（中文不用）：fill_at／fill_tooltip 換成不吃 token 後面空白的版本。

⚠ 這支用 monkeypatch 改 fetch_skills 的模組層函式，所以**一定要自己一個進程跑**，
  不可以被別的腳本 import 進去跟 fetch_skills 混用（中文那份會被改成英文）。

快取 csv_cache/skills_en_cache.json：每位英雄記「DDragon 版本|CDragon build」，兩者任一變了才重建；
抓不到的英雄沿用上一次的條目，下一班再試。

用法：python scripts/fetch_skills_en.py [--force]
"""
import json, os, re, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_skills as fs

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "csv_cache"
CACHE = CACHE_DIR / "skills_en_cache.json"
ST_EN_F = CACHE_DIR / "items_st_enus.json"      # 跟 fetch_items 共用；這支只讀，抓不到線上版才退回它
OUT_JS = ROOT / "skills_en.js"
URL_ST_EN = "https://raw.communitydragon.org/latest/game/en_us/data/menu/en_us/lol.stringtable.json"
FORCE = "--force" in sys.argv
MIN_KEEP = 0.9

# ── ① DDragon 語系 ──
_get_json = fs.get_json
def get_json_en(url, timeout=30):
    return _get_json(url.replace("/data/zh_TW/", "/data/en_US/"), timeout)
fs.get_json = get_json_en

# ── ③ 單位標籤 ──
LAB = [("基礎生命", "base Health"), ("額外生命", "bonus Health"), ("最大生命", "max Health"), ("基礎魔力", "base Mana"),
       ("額外魔力", "bonus Mana"), ("魔力", "Mana"), ("額外AD", "bonus AD"), ("基礎AD", "base AD"), ("額外AP", "bonus AP"),
       ("額外護甲", "bonus Armor"), ("基礎護甲", "base Armor"), ("護甲", "Armor"), ("額外魔抗", "bonus MR"), ("基礎魔抗", "base MR"),
       ("魔抗", "MR"), ("額外移動速度", "bonus Move Speed"), ("移動速度", "Move Speed"), ("暴擊率", "Crit Chance"), ("物理致命", "Lethality"), ("生命", "Health")]
_render_val = fs.render_val
def en(s):
    if not s:
        return s
    s = re.sub(r"每層 \+([\d./]+%?)", r"+\1 per stack", s)
    s = re.sub(r"每 (\d+%?) (\S+) \+", r"per \1 \2 +", s)
    s = s.replace("（依等級）", " (based on level)").replace("（", " (").replace("）", ")")
    for a, b in LAB:
        s = s.replace(a, b)
    return s.strip()
fs.render_val = lambda v, mult=1.0: en(_render_val(v, mult))

# ── 英文破句：動詞／介系詞後面直接接單位（值被剝掉）。有缺 token 才算，否則「Deals true damage」這種正常句會被誤判 ──
_HOLE = re.compile(
    r"\b(?:for|over|within|deals?|dealing|heals?|healing|restores?|restoring|gains?|gaining|grants?|granting|"
    r"increased? by|reduced? by|up to|every|by|additional)\s+"
    r"(?:seconds?\b|%|stacks?\b|(?:magic|physical|true) damage|(?:bonus )?(?:Move Speed|Attack Speed|Armor|Magic Resist|Health)\b)", re.I)
_tl = threading.local()
class _Hole:
    def search(self, t):
        return _HOLE.search(t) if getattr(_tl, "miss", None) else None
fs.HOLE_RE = _Hole()

LI = re.compile(r"</li>\s*<li>|</?li>", re.I)
def tidy(t):
    t = t.replace("－", "-").replace("，", ", ").replace("：", ": ")
    t = re.sub(r"(?<=\d)(?=(?:seconds?|stacks?|Health|Mana|Armor|Attack|Fragments)\b)", " ", t)
    t = re.sub(r"%\s*\(", "% (", t)
    t = re.sub(r"\)(?=[A-Za-z])", ") ", t)
    t = re.sub(r"(?<=[a-z])\.(?=[A-Z])", ". ", t)
    t = re.sub(r"[ \t]+(?=[.,:;!?)])", "", t)
    t = re.sub(r"(\d[\d./-]*)((?: \([^()]*\))+)%", r"\1%\2", t)   # 8 (+4% AP)% → 8% (+4% AP)
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()

# fill_at 的 AT_TOK 尾端 \s* 會吃掉 token 後面的空白（中文沒差，英文變 8seconds）
fs.AT_TOK = re.compile(r"@([A-Za-z_][\w.:]*?)(?:\*(-?[\d.]+))?@(\s*%)?")
def fill_at_en(tpl, ctx, all_ctx=None):
    all_ctx = all_ctx or {}
    miss = []
    def rep(m):
        name, mul, pct = m.group(1), float(m.group(2) or 1), (m.group(3) or "").strip()
        try:
            s = fs.resolve_token(ctx, all_ctx, name, mul)
            if s:
                return s + pct
        except fs.Miss:
            pass
        miss.append(name)
        return ""
    t = re.sub(r"<br\s*/?>", "\n", fs.AT_TOK.sub(rep, LI.sub("\n", tpl)), flags=re.I)
    return tidy(fs.finish(re.sub(r"<[^>]+>", "", t))), miss
fs.fill_at = fill_at_en

def fill_tooltip_en(tpl, ctx, all_ctx, strict=False):
    miss = []
    def rep(m):
        tok, mul = m.group(1), float(m.group(2) or 1)
        try:
            return fs.resolve_token(ctx, all_ctx, tok, mul)
        except fs.Miss:
            miss.append(tok)
            return fs.SENT if (strict or fs.F_TOK.match(tok)) else ""
    t = fs.STRIP_RE.sub("", fs.TAG_RE.sub("\n", LI.sub("\n", fs.TOKEN_RE.sub(rep, tpl))))
    if fs.SENT in t:
        t = re.sub(r"[（(][^（()）]*" + fs.SENT + r"[^（()）]*[)）]", "", t)
        t = "".join(p for p in re.split(r"(?<=[.!?\n])(?=\s)|(?<=\n)", t) if fs.SENT not in p)
        t = t.replace(fs.SENT, "")
    _tl.miss = miss
    return tidy(fs.finish(t)), miss
fs.fill_tooltip = fill_tooltip_en

CJK = re.compile(r"[一-鿿]")

def load_st():
    try:
        req = urllib.request.Request(URL_ST_EN, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=180) as r:
            j = json.loads(r.read().decode("utf-8"))
        ent = j.get("entries", j)
        if ent:
            return ent
    except Exception as e:
        print(f"（英文字串表線上抓不到：{e}；改用快取檔）")
    if ST_EN_F.exists():
        j = json.loads(ST_EN_F.read_text(encoding="utf-8"))
        return j.get("entries", j)
    return None

def has_cjk(c):
    return bool(CJK.search(c["p"]["d"] + "".join(s.get("d", "") + s.get("n", "") for s in c["s"])))

def main():
    ddv = fs.get_json(f"{fs.DD_API}/api/versions.json")[0]
    cdver = ""
    try:
        cdver = str(fs.get_json("https://raw.communitydragon.org/latest/content-metadata.json").get("version", ""))
    except Exception as e:
        print(f"（CDragon 版本查詢失敗：{e}）")
    cache = {}
    if CACHE.exists():
        try:
            cache = json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:
            cache = {}
    done = cache.setdefault("champs", {})
    built = cache.setdefault("built", {})
    tag = f"{ddv}|{cdver}"
    champs = sorted(k for k in fs.get_json(f"{fs.DD_API}/cdn/{ddv}/data/en_US/champion.json")["data"]
                    if not fs.CLASSIC_RE.match(k))
    # CDragon 版本這班查不到：只補還沒有的，不拿舊標籤當理由整批重建
    pend = [c for c in champs if FORCE or c not in done or (cdver and built.get(c) != tag)]
    if not pend and OUT_JS.exists():
        print(f"skills_en.js 已是 {ddv}（CDragon {cdver or '版本未知'}），跳過")
        return 0
    st = load_st() if pend else None
    if pend and not st:
        print("⚠ 沒有英文字串表（線上與快取都沒有）⇒ 這班不重建，skills_en.js 維持原樣")
        return 0
    print(f"DDragon {ddv}｜重建 {len(pend)}／{len(champs)} 位英雄")
    fail = dirty = 0
    def job(cid):
        try:
            return fs.build_champ(cid, ddv, st)
        finally:
            time.sleep(0.15)
    with ThreadPoolExecutor(max_workers=getattr(fs, "SKILL_WORKERS", 6)) as ex:
        futs = {ex.submit(job, c): c for c in pend}
        for fu in as_completed(futs):
            cid = futs[fu]
            try:
                new = fu.result()
            except Exception as e:
                fail += 1
                print(f"  {cid} ✗ {e}" + ("（沿用舊條目）" if cid in done else ""), flush=True)
                continue
            if has_cjk(new):   # 夾中文的不收：英文模式寧可退回 DDragon 原文
                dirty += 1
                print(f"  {cid} ✗ 產出夾中文，不收", flush=True)
                done.pop(cid, None)
                built[cid] = tag
                continue
            done[cid] = new
            built[cid] = tag
    for k in [k for k in done if k not in champs]:
        del done[k]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fs._write_atomic(CACHE, json.dumps(cache, ensure_ascii=False))
    if fail:
        print(f"⚠ {fail} 位英雄這班抓不到，沿用舊條目，下一班再試")
    old_n = 0
    if OUT_JS.exists():
        try:
            t = OUT_JS.read_text(encoding="utf-8")
            old_n = len(json.loads(t[t.index("{"):t.rindex("}") + 1])["d"])
        except Exception:
            old_n = 0
    if not done or len(done) < MIN_KEEP * old_n:
        print(f"⚠ 只有 {len(done)} 位英雄（上一版 {old_n} 位）⇒ 保留舊的 skills_en.js 不覆寫")
        return 1
    # 只留英文提示用得到的欄位（rg 是模擬BP 評分用的，讀中文那份）
    d = {}
    for k in sorted(done):
        c = done[k]
        d[k] = {"n": c["n"], "t": c.get("t", ""), "p": {"n": c["p"]["n"], "d": c["p"]["d"]},
                "s": [{x: s[x] for x in ("k", "n", "cd", "co", "d", "fb", "x") if x in s} for s in c["s"]]}
    js = "window.CHAMP_SKILLS_EN=" + json.dumps({"v": ddv, "d": d}, ensure_ascii=False, separators=(",", ":")) + ";"
    fs._write_atomic(OUT_JS, js)
    tot = sum(len(c["s"]) for c in d.values())
    dig = sum(bool(re.search(r"\d", s.get("d", ""))) for c in d.values() for s in c["s"])
    fb = sum(bool(s.get("fb")) for c in d.values() for s in c["s"])
    print(f"✅ skills_en.js：{len(d)} 位英雄，技能 {tot} 個、帶數字 {dig}、退回純描述 {fb}" + (f"、夾中文不收 {dirty} 位" if dirty else ""))
    return 0

if __name__ == "__main__":
    sys.exit(main())
