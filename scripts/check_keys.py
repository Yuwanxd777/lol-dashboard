# -*- coding: utf-8 -*-
"""金鑰健康檢查（update.bat 最後一步，把狀態印進 update_log.txt）

為什麼要有這支：整條管線吃憑證的只有三個地方，而且壞掉**全部都是靜默失效**——
  ①Riot 金鑰過期／被撤銷 → 牌位(soloq.js)停更，fetch_soloq_auto 印一行就跳過、exit 0
  ②Google 服務帳號憑證不見／被停用 → OE 主資料(data_*.js)整站基礎抓不到
  ③GS_API_KEY 沒設 → 刷野備註「有資料但連結全沒了」，畫面看起來正常
每天在日誌最後印一塊明顯的狀態＋修法，壞了一眼看得到。**永遠 exit 0，不擋更新鏈。**

判定原則：**憑證本身 ＋ 它的產物新鮮度**兩層都看。
  只看憑證會漏掉「金鑰有效但腳本壞了」；只看產物會漏掉「今天剛過期、產物還新鮮」。
  產物新鮮度一律用**檔案 mtime**（腳本只有成功才會重寫檔案），不用檔內的 updated 欄位——
  data.js 的 updated 是 stamp_updated.py 無條件蓋上去的，fetch_data 失敗了它照樣是新的。

用法：
  python scripts\check_keys.py            # 完整檢查（含 Riot 金鑰線上驗證，1 次請求）
  python scripts\check_keys.py --no-live  # 不打 Riot API（離線時用）
  python scripts\check_keys.py --quiet    # 只印有問題的項目＋結論
"""
import argparse, io, json, os, re, sys, time, urllib.error, urllib.request

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
KEYF = os.path.join(HERE, "riot_key.local.json")
SA_JSON = os.path.join(ROOT, "..", "字幕", "app", "mslol-500204-37d9f63f8b81.json")  # 與 fetch_data.py 同一條路徑
CACHE = os.path.join(ROOT, "csv_cache")

STALE_H = 30.0      # 排程一天兩次(10:00/22:00) → 超過 30 小時沒重寫＝那一步壞了
FILL_STALE_H = 48.0  # 補資料另計：OE 追上後本來就會停止重寫，門檻放寬
DEV_MAX_H = 23.0    # dev 金鑰 24h 過期（與 fetch_soloq_auto.py 同步）

OK, WARN, BAD = "✅", "⚠", "❌"
rows = []   # (狀態, 標題, 明細, 修法, 影響)


def add(state, title, detail, fix="", hit=""):
    rows.append((state, title, detail, fix, hit))


def ago(ts):
    """時間戳 → 『8.2 小時前』人話"""
    if not ts:
        return "時間不明"
    h = (time.time() - ts) / 3600
    if h < 1:
        return f"{h*60:.0f} 分鐘前"
    if h < 48:
        return f"{h:.1f} 小時前"
    return f"{h/24:.1f} 天前"


def mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def stamp(ts):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else "—"


def fresh(path, label, stale_h=STALE_H, note=""):
    """產物新鮮度：回傳 (狀態, 敘述)"""
    t = mtime(path)
    if not t:
        return BAD, f"{label}：檔案不存在（{os.path.relpath(path, ROOT)}）"
    h = (time.time() - t) / 3600
    st = OK if h <= stale_h else WARN
    return st, f"{label}：{stamp(t)}（{ago(t)}）{note}"


def head(path, n=800):
    try:
        with io.open(path, encoding="utf-8") as f:
            return f.read(n)
    except OSError:
        return ""


# ────────────────────────── ①Riot 金鑰（牌位） ──────────────────────────
def riot_live(key, timeout=8):
    """→ (狀態, 說明)。用最輕的 status-v4 驗證金鑰是否還活著"""
    req = urllib.request.Request(
        "https://kr.api.riotgames.com/lol/status/v4/platform-data",
        headers={"X-Riot-Token": key, "User-Agent": "lol-dashboard-healthcheck"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return (OK, f"線上驗證 {r.status} OK") if r.status == 200 else (WARN, f"線上驗證回 {r.status}")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            return OK, "線上驗證 429（被限流＝金鑰有效）"
        if e.code in (401, 403):
            return BAD, f"線上驗證 {e.code}：金鑰已失效或被撤銷"
        return WARN, f"線上驗證 HTTP {e.code}"
    except Exception as e:
        return WARN, f"無法連線驗證（{type(e).__name__}）"


def check_riot(live=True):
    T = "Riot 金鑰 ── 積分頁排位段位(soloq.js)"
    FIX = "開儀表板積分頁按「添加API」貼上新金鑰（https://developer.riotgames.com/）"
    HIT = "只有牌位(段位/LP)停更，比賽與積分逐場資料照常"
    if not os.path.exists(KEYF):
        add(BAD, T, "尚未添加金鑰（scripts/riot_key.local.json 不存在）", FIX, HIT)
    else:
        try:
            d = json.load(io.open(KEYF, encoding="utf-8"))
        except Exception as e:
            add(BAD, T, f"金鑰檔讀取失敗：{e}", FIX, HIT)
            d = None
        if d is not None:
            key = str(d.get("key", "")).strip()
            saved = float(d.get("saved", 0) or 0)
            perm = bool(d.get("permanent"))
            age_h = (time.time() - saved) / 3600 if saved else 9e9
            kind = "長期金鑰" if perm else "dev 金鑰"
            base = f"{kind}（{stamp(saved)} 添加，{ago(saved)}）"
            if not key.startswith("RGAPI-"):
                add(BAD, T, f"金鑰格式不對（不是 RGAPI- 開頭）· {base}", FIX, HIT)
            elif not perm and age_h > DEV_MAX_H:
                add(BAD, T, f"已過期 · {base} · 24 小時失效", FIX, HIT)
            else:
                st, msg = riot_live(key) if live else (OK, "未做線上驗證（--no-live）")
                add(st, T, f"{base} · {msg}",
                    FIX if st == BAD else "", HIT if st == BAD else "")
    st, msg = fresh(os.path.join(ROOT, "soloq.js"), "└ 牌位資料 soloq.js")
    add(st, "", msg, "同上（金鑰過期時這裡會先看到停更）" if st != OK else "")


# ────────────────────── ②Google 服務帳號（OE 主資料） ──────────────────────
def check_sa():
    T = "Google 服務帳號 ── OE 主資料(data_*.js，整站基礎)"
    FIX = "確認 " + os.path.normpath(SA_JSON) + " 還在（字幕系統共用同一份憑證）"
    HIT = "比賽資料完全不更新（整個儀表板停在舊資料）"
    if not os.path.exists(SA_JSON):
        add(BAD, T, f"憑證檔不存在：{os.path.normpath(SA_JSON)}", FIX, HIT)
    else:
        try:
            d = json.load(io.open(SA_JSON, encoding="utf-8"))
            mail = d.get("client_email", "?")
            missing = [k for k in ("client_email", "private_key", "project_id") if not d.get(k)]
            if missing:
                add(BAD, T, f"憑證檔缺欄位：{'、'.join(missing)}", FIX, HIT)
            else:
                add(OK, T, f"{mail} · 憑證檔正常")
        except Exception as e:
            add(BAD, T, f"憑證檔解析失敗：{e}", FIX, HIT)
    try:
        import google.oauth2.service_account  # noqa: F401
        add(OK, "", "└ google-auth 套件：已安裝")
    except ImportError:
        add(BAD, "", "└ google-auth 套件未安裝（fetch_data 會退回匿名下載 → Quota exceeded）",
            "pip install google-auth google-api-python-client", HIT)
    # 產物：今年的年份檔（fetch_data 每次成功都會重寫）
    yrs = sorted(int(m.group(1)) for m in
                 (re.match(r"data_(\d{4})\.js$", f) for f in os.listdir(os.path.join(ROOT, "data")))
                 if m)
    if yrs:
        st, msg = fresh(os.path.join(ROOT, "data", f"data_{yrs[-1]}.js"), f"└ 比賽資料 data_{yrs[-1]}.js")
        add(st, "", msg, "看 update_log.txt 裡 fetch_data.py 那段的錯誤" if st != OK else "")


# ─────────────────── ③GS_API_KEY（刷野備註超連結，選用） ───────────────────
def check_gs():
    T = "GS_API_KEY ── 刷野備註超連結(jungle.js)"
    has = bool(os.environ.get("GS_API_KEY", "").strip())
    links = head(os.path.join(ROOT, "jungle.js"), 10 ** 7).count('"link"')
    if has and links:
        add(OK, T, f"環境變數已設定 · jungle.js 含 {links} 條連結")
    elif has and not links:
        add(WARN, T, "環境變數已設定，但 jungle.js 一條連結都沒有（Sheets 端可能改版）",
            "跑 python scripts\\fetch_jungle.py 看訊息", "刷野備註沒有參考連結")
    else:
        add(WARN, T, f"環境變數未設定 → 走公開 CSV（jungle.js 現有 {links} 條連結）",
            '設使用者環境變數 GS_API_KEY（PowerShell：[Environment]::SetEnvironmentVariable("GS_API_KEY","...","User")）',
            "刷野備註照常有資料，只是沒有超連結")


# ──────────────── ④免金鑰但會靜默失效的來源（一併看時間） ────────────────
def check_keyless():
    add("", "免金鑰來源（不吃憑證，但一樣會靜默失效）", "")
    # gol.gg 補資料
    yr = time.localtime().tm_year
    fp = os.path.join(CACHE, f"fill_{yr}.json")
    if os.path.exists(fp):
        try:
            d = json.load(io.open(fp, encoding="utf-8"))
            seg = "、".join(f"{k} {len(v.get('games') or [])} 局" for k, v in d.items())
        except Exception:
            seg = "（解析失敗）"
        t = mtime(fp)
        h = (time.time() - t) / 3600
        add(OK if h <= FILL_STALE_H else WARN, "",
            f"└ gol.gg 補資料：{seg}（{stamp(t)}，{ago(t)}）",
            "OE 收錄後本來就會停止重寫；真的少比賽再跑 python scripts\\fetch_fill.py --force"
            if h > FILL_STALE_H else "")
    else:
        add(OK, "", f"└ gol.gg 補資料：無 fill_{yr}.json（OE 已收錄全部賽段＝正常）")
    # dpm 積分逐場
    st, msg = fresh(os.path.join(ROOT, "soloq_recent.js"), "└ dpm 積分逐場 soloq_recent.js")
    add(st, "", msg, "看 update_log.txt 裡 fetch_soloq_update.py 那段" if st != OK else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-live", action="store_true", help="不打 Riot API 驗證金鑰")
    ap.add_argument("--quiet", action="store_true", help="只印有問題的項目")
    a = ap.parse_args()

    # 逐項包起來：健檢工具自己爆掉不能連帶吃掉整份報告（也絕不能讓 update.bat 收到非 0）
    for fn, label in ((lambda: check_riot(live=not a.no_live), "Riot 金鑰"),
                      (check_sa, "Google 服務帳號"), (check_gs, "GS_API_KEY"),
                      (check_keyless, "免金鑰來源")):
        try:
            fn()
        except Exception as e:
            add(BAD, f"{label} ── 檢查本身出錯", f"{type(e).__name__}: {e}",
                "跑 python scripts\\check_keys.py 看完整錯誤")

    bad = sum(1 for r in rows if r[0] == BAD)
    warn = sum(1 for r in rows if r[0] == WARN)
    print("\n" + "━" * 62)
    print("金鑰健康檢查" + ("（只列問題）" if a.quiet else ""))
    print("━" * 62)
    pending = None                        # 區塊標題先擱著，底下真的有東西要印才印（--quiet 全綠時不留空標題）
    for st, title, detail, fix, hit in rows:
        if title and not detail:
            pending = title
            continue
        if a.quiet and st == OK:
            continue
        if pending:
            print(f"── {pending} ──")
            pending = None
        if title:
            print(f"{st} {title}")
            print(f"     {detail}")
        else:
            print(f"  {st} {detail}")
        if fix:
            print(f"     ↳ 修法：{fix}")
        if hit:
            print(f"     ↳ 影響：{hit}")
    verdict = ("全部正常" if not bad and not warn else
               "、".join(x for x in [f"{BAD} {bad} 項失效" if bad else "",
                                     f"{WARN} {warn} 項要注意" if warn else ""] if x))
    print("━" * 62)
    print(f"結論：{verdict}")
    print("━" * 62)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:                      # 永遠 exit 0，不擋更新鏈
        print(f"金鑰健康檢查：本身執行失敗（{type(e).__name__}: {e}）")
    sys.exit(0)
