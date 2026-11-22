# -*- coding: utf-8 -*-
"""轉會每小時更新（使用者 2026-11-20「新網頁每一個小時更新一次」「轉會分頁也每小時更新一次 轉會分頁先更新 10 分鐘後再更新新網頁」）。

  python scripts/transfers_hourly.py main   每小時 :10：抓轉會（fetch_transfers）→ 匯出轉會網站檔（export_transfer_site）
                                            → 只 commit 這三個檔 → preflight 通過才 push（主站轉會分頁更新）
  python scripts/transfers_hourly.py site   :40：先翻 PTT／看上一班 Sheep 有沒有失敗，有新東西就改跑整套 main（--plain＝只部署）；否則
                                            三個檔複製到 轉會網站\\www\\fallback → wrangler 部署 lol-transfer.pages.dev

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
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SITE = os.path.join(os.path.dirname(ROOT), "轉會網站")
LOG = os.path.join(ROOT, "transfers_hourly_log.txt")
FILES = ["transfers.js", "transfers_site.js", "transfers_site_code.js"]
# 發布時一起提交的檔：上面三個資料檔＋補抓到的隊徽（img/teams 整個資料夾）與隊徽清單。do_site 只複製 FILES（隊徽走主站網域）
PUB = FILES + ["img/teams", "img_manifest.js", "transfers_career.js"]   # transfers_career.js＝主站轉會分頁的生涯評分（2026-11-22 檢視：原本只有 10／22 點才帶上去）
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
- 只能改這四個資料檔：transfers_ptt_src.json、transfers_official_src.json、transfers_sheep_src.json、transfers_fa_manual.json（JSON，UTF-8，縮排 1，改完要能被 json.load 讀回）。
- 不可以改 index.html、scripts/、autopilot/、.gitignore、任何 .bat；不可以 git commit／push；不可以開使用者的 Chrome；不可以呼叫任何付費 API。
- 可以跑：python scripts/fetch_transfers.py（重算 transfers.js）、python scripts/transfers_dump.py（把畫面實際顯示的消息與陣容表倒成 transfers_review_dump.txt）。
- 要查證可以用 WebFetch／WebSearch（查 Leaguepedia lol.fandom.com 的選手頁確認路線、現在的隊伍、二隊隊名）。
- 內文貼的圖片可以抓下來看：只限 pbs.twimg.com、i.imgur.com、i.redd.it、i.mopix.cc 這幾個圖床的連結，用 curl 存到專案根目錄的 _review_tmp/（自己建），用 Read 工具打開看，看完把整個 _review_tmp/ 刪掉。

【步驟】
1. 讀 transfers_ptt_src.json，找出沒有 zh_fix 也沒有 hide 的條目（＝還沒複查）。每一則都要讀 body（只看內文，不看推文；內文在「※ 發信站」之前），然後擇一處理：
   a. 不是轉會消息（閒聊、問卦、影片、網友留言翻譯、純討論、選手日常、重複舊聞）⇒ 加 "hide": "原因"。
      例外——**退役或沒有隊的人公開表示想復出（或想轉任教練）不算閒聊**（使用者 2026-11-21「以後這種退役後想復出的人 都去看他講了什麼 並且依照他的國籍所屬的賽區放到FA區」）：
      ①把內文（必要時連原文）讀完，看他到底說了什麼；②照 b 重寫上架（沒有隊伍可標，用 "tags": [[賽區, "", ""]]、"kind": "other"）；
      ③在 transfers_fa_manual.json 加一筆：{{"n": ID, "p": wiki 頁名, "lg": 聯賽, "rr": 路線, "cb": 1, "why": 一句理由, "tips": [{{"d": 日期, "src": "PTT"|"韓網"|"Sheep Esports", "u": 連結, "tip": 他說了什麼（一句中文）, "tipE": 英文}}]}}。
        lg＝他**國籍**所屬的賽區（查 Leaguepedia 選手頁的 Country）：韓國 LCK、中國 LPL、歐洲與中東非洲 LEC、美國加拿大 LCS、巴西與拉丁美洲 CBLOL、台港澳／日本／越南／東南亞／大洋洲 LCP。
        rr＝講明要回來當選手就填他的路線（TOP／JNG／MID／BOT／SUP）；講到想當教練、或選手與教練都在考慮（例：Rekkles）填 "COACH" 再加 "sr": "C"（會列在後勤欄）。
        名單裡已經有這個人就只在他的 tips 最前面加一則新的（最多留三則）；他已經有隊或已經在陣容表上就不用加。
   b. 是轉會消息 ⇒ 重寫 "zh"（規則見下）、補 "mv"／"stay"／"tags"／"kind"，最後加 "zh_fix": "重寫（複查 {now}）"。
      同時寫一份英文稿 "en"（英文版網站用；使用者 2026-11-20「消息當中很多中文資料沒有翻譯成英文」）：照 "zh" 的內容直接翻成自然的英文一句到兩句，
      人名、戰隊縮寫照原樣，§TOP§、‹頁|名› 這類記號原封不動搬過去；你自己翻，不要呼叫任何翻譯服務。
2. zh 怎麼寫：一到兩句完整的話、有標點、句尾句號；不寫「乳摸」「傳聞」「爆料」（狀態欄已經標了）；中文與英文、數字之間留一個半形空格（Viper 將以年薪 1500 萬…）；
   括號用全形（）、並列用頓號、斜線用全形／；隊名用縮寫（GEN、KRX、BLG）；選手用 ID 原樣（大小寫照 Leaguepedia）。
   同名選手或畫面上抓不到路線的人，直接寫記號：§SUP§‹Cloud (Moon Hyeon-ho)|Cloud›（§路線§‹wiki 頁名|顯示名›，路線＝TOP／JNG／MID／BOT／SUP，教練用 §COACH§）。
   選手名字前面不要寫路線（上路／打野／中路／下路／輔助）或「選手」：畫面會自動在名字前加路線圖，寫了會變成「下路 [下路圖] SamD」。
   ‹頁|名› 這種連結記號只用在 transfers_ptt_src.json；transfers_sheep_src.json 的 zh 只寫 §路線§名字（例：§COACH§Mowgli、§SUP§Targamas），連結程式會自己補，寫了 ‹› 反而會包兩層壞掉。
   方向要對：「A 加入 B」＝原隊 A 的舊東家、新隊 B。內文很雜、一篇講很多隊 ⇒ 一句話濃縮每一隊的重點，並加 "nosplit": 1。
3. mv＝這則消息裡「誰傳出要去哪」：[[選手 ID, 路線, 新隊全名, 原隊全名], …]。隊名一定用 Leaguepedia 全名（Gen.G、Kiwoom DRX、Hanwha Life Esports、Dplus Kia、Bilibili Gaming、JD Gaming、
   T1 Esports Academy、Hanwha Life Esports Challengers、Dplus Kia Challengers…；不確定就查 wiki）。原隊不知道填 ""。只是「有興趣」「接觸中」而已也可以列，但同一則不要超過五筆。一則講到兩個人以上時，每筆後面加第五格＝只講這個人的一句話（陣容表小框會顯示它），例：["Cloud", "SUP", "Gen.G", "T1 Esports Academy", "Cloud 被多隊追逐，最可能落腳 GEN。"]。
   教練、分析師的 mv 路線寫 COACH；報導講明是「主教練」的，另外在條目加 "hc": [那個人的 ID]（陣容表會放進主教練欄，沒標的放後勤欄）。
   **教練的傳聞一樣要寫 mv**，不要只改句子（使用者 2026-11-21：Inven 報 Roach 將任 T1 主教練、Xportsnews 報 UmTi 有望進 T1 教練團，兩則都沒寫 mv，陣容表上就完全沒有）。
   Sheep 的教練推文：在 transfers_sheep_src.json 那則的 zh 把名字寫成 §COACH§名字，程式會放進陣容表的教練格（句子寫「出任／擔任…主教練」的進主教練欄，其餘進後勤欄）。
   名字照 Leaguepedia 的 ID 寫（大小寫也照：HOYA 不是 Hoya、frosty 不是 Frosty）；寫錯大小寫程式會自動改回 wiki 的寫法，但句子裡最好一開始就寫對。
   一篇講很多隊（各隊陣容彙整、整理圖）⇒ 一隊拆一則：新條目的 id＝原 id 後面加 -1、-2…（照抄 title／ptt／st，各自寫 zh／en／mv），原條目留著當總結或其中一則；
   新條目的 body 只放跟那一隊有關的段落，而且不可以含 Sheep_Esports/status/ 的連結（程式會把它當成已收錄的 Sheep 轉貼，整則不列）。範例：M.1795235805.A.82F 與它的 -1～-12。
   整理文的重點在圖上（各隊名單表、整理圖）⇒ 一定要把圖抓下來看（使用者 2026-11-21「這篇…要點進去看圖」），而且圖上**每一隊都要拆一則**，不要只拆「之前沒有個別消息」的隊：
   句子寫完整陣容（誰留隊、誰接替誰、教練）；陣容表上已經有的人不必重複寫 mv（保留原本比較詳細的那句），只補陣容表上還沒有的人；沒有 mv 的那幾則用 "tags": [[賽區, 隊全名, ""]]＋"kind": "other"。
   合約已到期、圖上寫留隊的人放 stay；「不在新名單上、去向不明」的人只寫在句子裡，**不要放 stay**（stay 會被拿去判這則傳聞準不準）。範例：M.1795237153.A.60B 與它的 -1～-10。
   stay＝傳出或宣布續留：[[選手 ID, 隊全名], …]（會蓋掉他之前的轉隊傳聞）。純隊伍消息（解散、退出聯賽）用 "tags": [[賽區中文, 隊全名, "in"|"out"]]（賽區＝韓國／中國／歐洲／北美／巴西／亞太）加 "kind": "join"|"leave"|"both"|"other"。
4. st（狀態）：戰隊官方帳號的公告＝"official"；媒體報導、記者、爆料、韓網、Sheep Esports 一律 "rumor"。舊傳聞被官方推翻或闢謠 ⇒ 在那一則舊傳聞加 "fake": "依據"；被證實不用手動標（程式會判）。
   內文貼的是 Sheep Esports 的推文 ⇒ src 改 "Sheep Esports"、url 改成那則 x.com 連結；引用韓網（fmkorea、inven、naver…）⇒ src "韓網"、url 用韓網原文。
5. 全部處理完：跑 python scripts/fetch_transfers.py，再跑 python scripts/transfers_dump.py，讀 transfers_review_dump.txt 檢查「這一輪要看的」那幾則實際顯示：
   - 內文：標點、空格、有沒有「乳摸：」殘留、選手前面有沒有路線圖 [上路] 這種（沒有就在 zh 用 §路線§‹頁|名› 補）、有沒有把隊名或普通單字誤認成選手。
   - 原隊／新隊：方向對不對、有沒有漏；賽區欄對不對。
   - 重複：同一件事已經有另一則（Sheep、WIKI、官方）⇒ 把 PTT 這則 hide（原因寫重複哪一則）。
     使用者 2026-11-22 定的鐵則：相同的資訊 24 小時內不要重複——PTT 與 PTT 之間也一樣，同一件事只留最完整的一則（其餘 hide）。
   - 陣容表：mv 裡的人有沒有出現在新隊那一格（rumor）、路線對不對。
   有問題就回去改資料檔再重跑，直到乾淨。WIKI 與 Sheep 的新消息只檢查顯示，內容有明顯錯（翻譯錯、方向反）才改 transfers_sheep_src.json 的 zh／tags；WIKI 那邊是程式產生的，有錯就記在紀錄裡不要硬改。
   【使用者已經定案的顯示方式——不是錯，不要改、也不要記成待人工】
   - 教練、分析師、後勤人員名字前面一律只畫同一顆後勤圖示，不寫職稱（dump 裡看到的是 [教]）。
   - 已宣布離隊的人不留在原隊那一格，只列在該聯賽最後的 FA；退役的人也列在 FA（灰字刪除線）。
   - 退役選手的「離隊」與「宣布退役」併成一則（寫「離隊並宣布退役」；Sheep 也報了就留 Sheep 那則），WIKI 那則離隊名單會少他一個人。
   - 同一路官方已確認兩人以上，評分只拿分數最高的那位算；合約到期又有傳聞的人是綠字，FA 裡有傳聞去向的人是黃字。
   - WIKI 的同一則公告同時有人加入又有人離隊時，隊伍只放在原隊那一欄、不畫箭頭（那一欄在這種列代表「這支隊伍」）。
   - 媒體報導的續約／留隊（stay、狀態是傳聞）不會改陣容表的顏色，仍顯示合約到期（藍字），只在那個人的小框多一則報導；戰隊官方公告才變粉色。
   - 圖例把續約與升職併成「續約升職」，兩種都是粉色；小框的標籤仍分開寫「續約」「升職」。
   - 手機版的 FA 卡把主教練與後勤併成一格（dump 是電腦版，仍分 HC／STF 兩欄）。
   - FA 的位置照最新傳聞：選手被傳去當教練就列在教練格（Shini 在主教練欄不在打野欄）；傳聞人選現在沒有隊的，會列進傳聞那一隊所在聯賽的 FA（Croc）；
     有傳聞去別的聯賽的人，兩邊聯賽的 FA 都會列（Naak Nako 同時在 LEC 與 LCS）；退役的人排在那一格最後。
   - 五路都沒有人可以算分的隊（全員已宣布離隊，CFO、LEV），選手評分顯示「–」。
   - LPL 新生訓練場的臨時名單（11/06 登錄、11/15 到期）那批選手不列在隊伍格子，列在 LPL 的 FA（合約到期 11/15）。
   - 這個休賽期 wiki 記了離隊、現在沒有隊的教練與分析師，都會列在該聯賽 FA 的教練格（不管他原本的位置後來有沒有人補上）。
   - 截圖跟網頁不一樣是刻意的：截圖只有五路＋教練（主教練與後勤併一欄，後勤裡合約到期的不列）、照第三賽段成績排、成績寫在隊名下面。
   - 同一件事三天內 Sheep 已經發過（同隊、句子裡的人名也對得上）⇒ PTT 那則畫面上不會列，這是去重，不用再 hide 也不用記成問題。
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


def publish(tag):
    """匯出 → commit → preflight → push。回傳 True＝這次有新的內容（commit 了或有東西推出去）。"""
    py = sys.executable
    if run([py, "scripts/export_transfer_site.py", "--head"]) != 0:
        log(f"  [{tag}] export_transfer_site 失敗，不推")
        return False
    if "--dry" in sys.argv:
        log("  --dry：不 commit／不推")
        return False
    run([GIT, "add", "--"] + PUB)
    changed = subprocess.run([GIT, "diff", "--cached", "--quiet", "--"] + PUB, cwd=ROOT, env=ENV).returncode != 0
    if not changed:
        log(f"  [{tag}] 轉會資料沒變")
    else:
        run([GIT, "commit", "-m", f"轉會每小時更新 {datetime.datetime.now():%Y-%m-%d %H:%M}（{tag}）", "--"] + PUB)
    ahead = subprocess.run([GIT, "rev-list", "--count", "@{u}..HEAD"], cwd=ROOT, env=ENV, capture_output=True, text=True).stdout.strip()
    if ahead in ("", "0"):
        log(f"  [{tag}] 沒有要推的 commit")
        return changed
    if run([py, "scripts/preflight_check.py"], timeout=1800) != 0:
        log("  ⚠ preflight 失敗，不推（下一班 publish 會再試）")
        return changed
    run([GIT, "push"], timeout=600)
    return True


def logos():
    """轉會資料裡新出現的隊伍（傳聞的原隊／去向，多半是次級聯賽的隊）補隊徽。
    使用者 2026-11-21 一個小時內回報兩次「缺的隊徽要補上」（FURY／NERD、ZYB）：原本只有每天兩班的大更新會抓，
    複查員中途加進來的新隊要等半天才有圖。抓不到不影響發布（腳本自己記 30 天不重查）；要放在匯出之前，匯出時才認得到新圖。"""
    try:   # run() 逾時會丟例外——這一步只是加分項，卡住或出錯都不能拖垮整班更新
        if run([sys.executable, "scripts/fetch_team_logos_wiki.py"], timeout=420) != 0:
            log("  隊徽補抓失敗（略過，不影響發布）")
    except Exception as e:
        log(f"  隊徽補抓出錯（略過，不影響發布）：{type(e).__name__} {str(e)[:120]}")


def do_main():
    # 先送再查（使用者 2026-11-20「資料更新的流程可以更快速嗎 可以先初步送上 再慢慢檢查複查」）：
    #   ① 抓資料 → 馬上發布主站＋部署轉會網站（約 2 分鐘；還沒複查的 PTT 文本來就先扣著不上架，所以初版不會有沒看過的 PTT 稿）
    #   ② 再叫 claude 複查（10 分鐘上下）→ 有改動才重抓、再發布、再部署一次
    py = sys.executable
    if run([py, "scripts/fetch_transfers.py"]) != 0:
        log("  fetch_transfers 失敗，沿用舊資料繼續")
    logos()
    if publish("初步") and "--dry" not in sys.argv:
        do_site()
    if "--dry" in sys.argv or "--no-review" in sys.argv:
        return
    if not do_review():
        return
    if run([py, "scripts/fetch_transfers.py"]) != 0:
        log("  複查後重抓失敗，沿用複查前的資料")
    logos()
    if publish("複查後"):
        do_site()


def do_site():
    dst = os.path.join(SITE, "www", "fallback")
    os.makedirs(dst, exist_ok=True)
    for f in FILES:
        shutil.copy2(os.path.join(ROOT, f), os.path.join(dst, f))
    # 一定要在 轉會網站 資料夾跑（在 C:\fit 跑會把訓練計畫的 functions 一起傳上去）
    cmd = [NPX, "--yes", "wrangler", "pages", "deploy", "www", "--project-name", "lol-transfer", "--branch", "main", "--commit-dirty=true"]
    rc = run(cmd, cwd=SITE, timeout=600)
    if rc != 0:
        # wrangler 的登入權杖約一小時到期。到期點剛好落在一次部署的兩個 API 請求之間 ⇒ 第二個請求 401
        # 「Authentication error [code: 10000]」，wrangler 不重試、離開碼 1，但離開前會把權杖換新 ⇒ 馬上再跑一次就會過。
        # 2026-11-20 13:10／11-21 00:40／11-22 04:40 三次都是這個長相（277 次部署裡 3 次；看 wrangler 自己的 log 檔）。
        # 只重試一次：真的壞掉（沒登入、網路斷）重試也沒用，下一趟 30 分鐘內會再部署。改這段跑 transfers_hourly_site_test.py。
        log("  ⚠ 部署失敗（多半是登入權杖剛好到期），10 秒後重試一次")
        time.sleep(10)
        rc = run(cmd, cwd=SITE, timeout=600)
        if rc != 0:
            log("  ⚠ 部署重試仍失敗，轉會網站這一趟沒更新（下一趟會再部署；連續出現就看 wrangler 的 log 檔，可能要重新 wrangler login）")
    return rc


def site_needs_main():
    """:40 那班先做兩個便宜的檢查（使用者 2026-11-22 選的精進第 4、5 項：PTT 新文不用等整點、Sheep 被 429 擋的那班補抓）：
      ① 翻 PTT 看板（只有幾頁，幾秒）：有還沒複查的新文 ⇒ 整套 main（抓→發布→複查→再發布）
      ② 上一班 Sheep 抓取失敗（csv_cache/sheep_fail.txt）⇒ 整套 main 再試一次
    直播中／publish.bat 正在跑就不做（跟 main 同一套跳過條件，但 10／22 點的 :40 照做：那時 publish.bat 多半已經跑完）。回傳原因字串，空字串＝只部署。"""
    if publish_running() or os.path.exists(os.path.join(ROOT, "autopilot", "STREAM")):
        return ""
    why = []
    if os.path.exists(os.path.join(ROOT, "csv_cache", "sheep_fail.txt")):
        why.append("上一班 Sheep 抓取失敗")
    try:
        sys.path.insert(0, HERE)
        import fetch_ptt_transfers
        before = {x["id"] for x in _pending_ptt()}
        fetch_ptt_transfers.main("2026-11-15T12:00")
        new = [x for x in _pending_ptt() if x["id"] not in before]
        if new or before:
            why.append(f"PTT 待複查 {len(before) + len(new)} 則（新 {len(new)}）")
    except Exception as e:
        log(f"  PTT 檢查失敗（略過）：{type(e).__name__} {str(e)[:120]}")
    return "、".join(why)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode not in ("main", "site"):
        raise SystemExit("用法：transfers_hourly.py main|site")
    why = skip_reason() if mode == "main" else ""
    if why:
        log(f"[{mode}] 跳過：{why}")
        return
    log(f"[{mode}] 開始")
    if mode == "site" and "--plain" not in sys.argv:
        why = site_needs_main()
        if why:
            log(f"  {why} ⇒ 這班改跑整套 main")
            mode = "main"
    (do_main if mode == "main" else do_site)()
    log(f"[{mode}] 結束")


if __name__ == "__main__":
    main()
