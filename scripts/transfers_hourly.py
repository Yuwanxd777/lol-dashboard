# -*- coding: utf-8 -*-
"""轉會每小時更新（使用者 2026-11-20「新網頁每一個小時更新一次」「轉會分頁也每小時更新一次 轉會分頁先更新 10 分鐘後再更新新網頁」）。

  python scripts/transfers_hourly.py main   每小時 :10：抓轉會（fetch_transfers）→ 匯出轉會網站檔（export_transfer_site）
                                            → 只 commit 這三個檔 → preflight 通過才 push（主站轉會分頁更新）
  python scripts/transfers_hourly.py site   10 分：三個檔複製到 轉會網站\\www\\fallback → wrangler 部署 lol-transfer.pages.dev

排程：工作排程器 LOL_Transfers_Main（每小時 :10；使用者 2026-11-20「每個小時的10分時更新」）、LOL_Transfers_Site（每小時 :40），由 transfers_hourly.vbs 隱藏執行。
跳過條件：10／22 點（publish.bat 那班本來就會更新＋推）、LOL_Dashboard_Update 正在跑、autopilot\\STREAM 存在（直播中不跑吃 CPU 的無頭頁）。
⚠ push 會把本機所有還沒推的 commit 一起推上去（GitHub Pages 只有一條分支）⇒ 推之前一定跑 preflight，失敗就不推。
紀錄寫自己的 transfers_hourly_log.txt（不要寫進 update_log.txt：那是 publish 的）。
"""
import datetime
import io
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SITE = os.path.join(os.path.dirname(ROOT), "轉會網站")
LOG = os.path.join(ROOT, "transfers_hourly_log.txt")
FILES = ["transfers.js", "transfers_site.js", "transfers_site_code.js"]
GIT = r"C:\Program Files\Git\cmd\git.exe"
NPX = r"C:\Program Files\nodejs\npx.cmd"
ENV = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never", GIT_HTTP_LOW_SPEED_LIMIT="1000", GIT_HTTP_LOW_SPEED_TIME="60",
           PYTHONIOENCODING="utf-8")


def log(msg):
    line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line)
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(cmd, cwd=ROOT, timeout=1200):
    r = subprocess.run(cmd, cwd=cwd, env=ENV, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    tail = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-3:]
    log(f"  {' '.join(os.path.basename(str(c)) for c in cmd[:3])} → {r.returncode}｜{' / '.join(tail)[:300]}")
    return r.returncode


def publish_running():
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-ScheduledTask -TaskName LOL_Dashboard_Update).State"],
                           capture_output=True, text=True, timeout=30)
        return "Running" in (r.stdout or "")
    except Exception:
        return False


def skip_reason():
    h = datetime.datetime.now().hour
    if h in (10, 22):
        return "10／22 點由 publish.bat 那班更新"
    if publish_running():
        return "LOL_Dashboard_Update 正在跑"
    if os.path.exists(os.path.join(ROOT, "autopilot", "STREAM")):
        return "直播中（autopilot\\STREAM）"
    return ""


# ── 每小時複查（使用者 2026-11-20「每一個小時更新消息 終端機要幫我重新確認資訊正確性與排版」）──
#   抓完資料後，有「還沒複查的 PTT 文」或「上次複查之後才出現的消息」就叫一次 headless claude 照下面這份交辦整理，
#   整理完重抓一次再匯出／推。叫不動（沒登入、逾時、額度用完）就照舊發布——沒複查的 PTT 文 fetch_transfers 本來就不上架，不會把亂的東西推出去。
REVIEW_STATE = os.path.join(ROOT, "transfers_review_state.json")
REVIEW_LOG = os.path.join(ROOT, "transfers_review_log.txt")
REVIEW_BRIEF = """你是 LOL 儀表板「轉會」分頁的每小時複查員（無人值守，沒有人可以問，全部自己判斷做完）。一律用繁體中文。

【這一輪要看的】
{todo}

【只准做的事】
- 只能改這三個資料檔：transfers_ptt_src.json、transfers_official_src.json、transfers_sheep_src.json（JSON，UTF-8，縮排 1，改完要能被 json.load 讀回）。
- 不可以改 index.html、scripts/、autopilot/、.gitignore、任何 .bat；不可以 git commit／push；不可以開使用者的 Chrome；不可以呼叫任何付費 API。
- 可以跑：python scripts/fetch_transfers.py（重算 transfers.js）、python scripts/transfers_dump.py（把畫面實際顯示的消息與陣容表倒成 transfers_review_dump.txt）。
- 要查證可以用 WebFetch／WebSearch（查 Leaguepedia lol.fandom.com 的選手頁確認路線、現在的隊伍、二隊隊名）。

【步驟】
1. 讀 transfers_ptt_src.json，找出沒有 zh_fix 也沒有 hide 的條目（＝還沒複查）。每一則都要讀 body（只看內文，不看推文；內文在「※ 發信站」之前），然後擇一處理：
   a. 不是轉會消息（閒聊、問卦、影片、網友留言翻譯、純討論、選手日常、重複舊聞）⇒ 加 "hide": "原因"。
   b. 是轉會消息 ⇒ 重寫 "zh"（規則見下）、補 "mv"／"stay"／"tags"／"kind"，最後加 "zh_fix": "重寫（複查 {now}）"。
2. zh 怎麼寫：一到兩句完整的話、有標點、句尾句號；不寫「乳摸」「傳聞」「爆料」（狀態欄已經標了）；中文與英文、數字之間留一個半形空格（Viper 將以年薪 1500 萬…）；
   括號用全形（）、並列用頓號、斜線用全形／；隊名用縮寫（GEN、KRX、BLG）；選手用 ID 原樣（大小寫照 Leaguepedia）。
   同名選手或畫面上抓不到路線的人，直接寫記號：§SUP§‹Cloud (Moon Hyeon-ho)|Cloud›（§路線§‹wiki 頁名|顯示名›，路線＝TOP／JNG／MID／BOT／SUP，教練用 §COACH§）。
   選手名字前面不要寫路線（上路／打野／中路／下路／輔助）或「選手」：畫面會自動在名字前加路線圖，寫了會變成「下路 [下路圖] SamD」。
   ‹頁|名› 這種連結記號只用在 transfers_ptt_src.json；transfers_sheep_src.json 的 zh 只寫 §路線§名字（例：§COACH§Mowgli、§SUP§Targamas），連結程式會自己補，寫了 ‹› 反而會包兩層壞掉。
   方向要對：「A 加入 B」＝原隊 A 的舊東家、新隊 B。內文很雜、一篇講很多隊 ⇒ 一句話濃縮每一隊的重點，並加 "nosplit": 1。
3. mv＝這則消息裡「誰傳出要去哪」：[[選手 ID, 路線, 新隊全名, 原隊全名], …]。隊名一定用 Leaguepedia 全名（Gen.G、Kiwoom DRX、Hanwha Life Esports、Dplus Kia、Bilibili Gaming、JD Gaming、
   T1 Esports Academy、Hanwha Life Esports Challengers、Dplus Kia Challengers…；不確定就查 wiki）。原隊不知道填 ""。只是「有興趣」「接觸中」而已也可以列，但同一則不要超過五筆。一則講到兩個人以上時，每筆後面加第五格＝只講這個人的一句話（陣容表小框會顯示它），例：["Cloud", "SUP", "Gen.G", "T1 Esports Academy", "Cloud 被多隊追逐，最可能落腳 GEN。"]。
   stay＝傳出或宣布續留：[[選手 ID, 隊全名], …]（會蓋掉他之前的轉隊傳聞）。純隊伍消息（解散、退出聯賽）用 "tags": [[賽區中文, 隊全名, "in"|"out"]]（賽區＝韓國／中國／歐洲／北美／巴西／亞太）加 "kind": "join"|"leave"|"both"|"other"。
4. st（狀態）：戰隊官方帳號的公告＝"official"；媒體報導、記者、爆料、韓網、Sheep Esports 一律 "rumor"。舊傳聞被官方推翻或闢謠 ⇒ 在那一則舊傳聞加 "fake": "依據"；被證實不用手動標（程式會判）。
   內文貼的是 Sheep Esports 的推文 ⇒ src 改 "Sheep Esports"、url 改成那則 x.com 連結；引用韓網（fmkorea、inven、naver…）⇒ src "韓網"、url 用韓網原文。
5. 全部處理完：跑 python scripts/fetch_transfers.py，再跑 python scripts/transfers_dump.py，讀 transfers_review_dump.txt 檢查「這一輪要看的」那幾則實際顯示：
   - 內文：標點、空格、有沒有「乳摸：」殘留、選手前面有沒有路線圖 [上路] 這種（沒有就在 zh 用 §路線§‹頁|名› 補）、有沒有把隊名或普通單字誤認成選手。
   - 原隊／新隊：方向對不對、有沒有漏；賽區欄對不對。
   - 重複：同一件事已經有另一則（Sheep、WIKI、官方）⇒ 把 PTT 這則 hide（原因寫重複哪一則）。
   - 陣容表：mv 裡的人有沒有出現在新隊那一格（rumor）、路線對不對。
   有問題就回去改資料檔再重跑，直到乾淨。WIKI 與 Sheep 的新消息只檢查顯示，內容有明顯錯（翻譯錯、方向反）才改 transfers_sheep_src.json 的 zh／tags；WIKI 那邊是程式產生的，有錯就記在紀錄裡不要硬改。
6. 最後把這一輪做了什麼追加寫進 transfers_review_log.txt（一行日期時間，底下每則一行：id、處置、理由；有解決不了的問題寫「⚠ 待人工」開頭）。然後結束，不要做別的事。
"""


def _pending_ptt():
    import json
    p = os.path.join(ROOT, "transfers_ptt_src.json")
    try:
        return [x for x in json.load(io.open(p, encoding="utf-8")) if not x.get("hide") and not x.get("zh_fix")]
    except Exception:
        return []


def _news_keys():
    import json
    try:
        s = io.open(os.path.join(ROOT, "transfers.js"), encoding="utf-8").read()
        D = json.loads(s[s.index("{"):s.rindex("}") + 1])
    except Exception:
        return {}
    out = {}
    for src in ("wiki", "sheep", "extra"):
        for x in D.get(src) or []:
            k = src + ":" + str(x.get("id") or (str(x.get("d")) + "|" + str(x.get("en") or x.get("zh") or "")[:60]))
            out[k] = f"[{src}] {x.get('d', '')} {str(x.get('zh') or x.get('en') or '')[:70]}"
    return out


def do_review():
    """回傳 True＝有叫 claude 複查（之後要重抓一次）。"""
    import json
    pend = _pending_ptt()
    keys = _news_keys()
    try:
        seen = set(json.load(io.open(REVIEW_STATE, encoding="utf-8")))
    except Exception:
        seen = None
    fresh = [] if seen is None else [v for k, v in keys.items() if k not in seen]

    def save():
        with io.open(REVIEW_STATE, "w", encoding="utf-8") as f:
            json.dump(sorted(set(_news_keys()) | set(keys)), f, ensure_ascii=False)

    if not pend and not fresh:
        save()
        return False
    exe = shutil.which("claude") or r"C:\Users\USER\.local\bin\claude.exe"
    if not os.path.exists(exe):
        log("  複查：找不到 claude 執行檔，跳過（沒複查的 PTT 文不會上架）")
        return False
    try:
        perm = [x for x in io.open(os.path.join(ROOT, "autopilot", "perm_flag.txt"), encoding="utf-8").read().split() if x]
    except Exception:
        perm = ["--dangerously-skip-permissions"]
    todo = "\n".join([f"- 還沒複查的 PTT 文 {len(pend)} 則：" + "；".join(f"{x['id']}《{x.get('title', '')[:30]}》" for x in pend)] if pend else [])
    todo += ("\n" if todo else "") + (f"- 上次複查之後新出現的消息 {len(fresh)} 則（只檢查顯示）：\n" + "\n".join("  " + v for v in fresh[:30]) if fresh else "")
    prompt = REVIEW_BRIEF.replace("{todo}", todo).replace("{now}", f"{datetime.datetime.now():%Y-%m-%d %H:%M}")
    log(f"  複查：PTT 待複查 {len(pend)} 則、新消息 {len(fresh)} 則 → 叫 claude")
    try:
        r = subprocess.run([exe, "-p", prompt] + perm + ["--add-dir", ROOT], cwd=ROOT, env=ENV, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=1500, stdin=subprocess.DEVNULL)
        log(f"  複查結束 → {r.returncode}｜{((r.stdout or '') + (r.stderr or '')).strip().replace(chr(10), ' ')[-300:]}")
        ok = r.returncode == 0
    except subprocess.TimeoutExpired:
        log("  複查逾時（25 分鐘），照目前的資料繼續")
        ok = False
    try:   # 複查把 JSON 改壞了 ⇒ 還原成 git 沒有的話就只能擋發布
        for fn in ("transfers_ptt_src.json", "transfers_official_src.json", "transfers_sheep_src.json"):
            json.load(io.open(os.path.join(ROOT, fn), encoding="utf-8"))
    except Exception as e:
        log(f"  ⚠ 複查後資料檔讀不回來（{type(e).__name__}：{str(e)[:120]}）⇒ 這一班不發布")
        raise SystemExit(1)
    if ok:
        save()
    return True


def do_main():
    py = sys.executable
    if run([py, "scripts/fetch_transfers.py"]) != 0:
        log("  fetch_transfers 失敗，沿用舊資料繼續")
    reviewed = False
    if "--dry" not in sys.argv and "--no-review" not in sys.argv:
        reviewed = do_review()
        if reviewed and run([py, "scripts/fetch_transfers.py"]) != 0:
            log("  複查後重抓失敗，沿用複查前的資料")
    if run([py, "scripts/export_transfer_site.py", "--head"]) != 0:
        log("  export_transfer_site 失敗，不推")
        return
    if "--dry" in sys.argv:
        log("  --dry：不 commit／不推")
        return
    run([GIT, "add", "--"] + FILES)
    if subprocess.run([GIT, "diff", "--cached", "--quiet", "--"] + FILES, cwd=ROOT, env=ENV).returncode == 0:
        log("  轉會資料沒變")
    else:
        run([GIT, "commit", "-m", f"轉會每小時更新 {datetime.datetime.now():%Y-%m-%d %H:%M}", "--"] + FILES)
    ahead = subprocess.run([GIT, "rev-list", "--count", "@{u}..HEAD"], cwd=ROOT, env=ENV, capture_output=True, text=True).stdout.strip()
    if ahead in ("", "0"):
        log("  沒有要推的 commit")
        return
    if run([py, "scripts/preflight_check.py"], timeout=1800) != 0:
        log("  ⚠ preflight 失敗，不推（下一班 publish 會再試）")
        return
    run([GIT, "push"], timeout=600)
    if reviewed:   # 複查花掉的時間多半已經超過 :40 那班 ⇒ 這裡直接補部署轉會網站
        do_site()


def do_site():
    dst = os.path.join(SITE, "www", "fallback")
    os.makedirs(dst, exist_ok=True)
    for f in FILES:
        shutil.copy2(os.path.join(ROOT, f), os.path.join(dst, f))
    # 一定要在 轉會網站 資料夾跑（在 C:\fit 跑會把訓練計畫的 functions 一起傳上去）
    run([NPX, "--yes", "wrangler", "pages", "deploy", "www", "--project-name", "lol-transfer", "--branch", "main", "--commit-dirty=true"],
        cwd=SITE, timeout=600)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode not in ("main", "site"):
        raise SystemExit("用法：transfers_hourly.py main|site")
    why = skip_reason() if mode == "main" else ""
    if why:
        log(f"[{mode}] 跳過：{why}")
        return
    log(f"[{mode}] 開始")
    (do_main if mode == "main" else do_site)()
    log(f"[{mode}] 結束")


if __name__ == "__main__":
    main()
