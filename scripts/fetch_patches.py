# -*- coding: utf-8 -*-
"""
抓 Riot 官方 patch notes（繁中）→ 解析各英雄改動 → patches.js
給儀表板英雄詳情頁的「版本趨勢」顯示真實改動（比 DataDragon 準）。
patch 已發布就不再變 → 解析結果永久快取，只補缺的。

用法：
  python fetch_patches.py                  # 補缺：先掃 tag 頁取得 URL，再補缺版本
  python fetch_patches.py --force          # 全部重抓（含 URL 目錄）
  python fetch_patches.py --skip-discover  # 不重掃 tag 頁，用既有 URL 快取
  python fetch_patches.py --ai-translate   # 英文版用 Claude API 翻譯（需 pip install anthropic）

排程邏輯：
  - 當年版本：每次執行都嘗試抓（版本剛發布就自動補進來）
  - 舊年版本：404 後永久跳過（不再重試）
  - 未來版本：估算發布日尚未到 → 直接跳過，不發 404 請求
"""
import urllib.request, re, json, os, html as H
from datetime import datetime, date, timedelta

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 專案根目錄（本腳本在 scripts\ 內）
CACHE = os.path.join(HERE, "csv_cache")
NOW_YEAR = datetime.now().year
TODAY = datetime.now().date()


def patch_est_date(year, minor):
    """估算版本釋出日（依 Riot 慣例：每年第一個版本約 1/8，此後每 14 天一個版本）。
    用來避免對未來版本發出 404 請求，也不把它們放進負快取。
    """
    first = date(year, 1, 8)
    return first + timedelta(days=(minor - 1) * 14)

FIRST_YEAR = 2019  # 官方頁最早只到 2019(patch 9.x)；2018 以前繁中/英文都沒保留

def riot_major(year):
    # 官方版號：2011~2024 是序號版(2014→4 … 2024→14)，2025 起改年份版(25.x, 26.x)
    return year - 2010 if year <= 2024 else year % 100

# 涵蓋整個數據庫：2019~今年，每年 minor 1~26（快取鍵用 OE 標籤 年份%100.minor 以對上比賽資料）
def target_patches():
    return [(y, m) for y in range(FIRST_YEAR, NOW_YEAR + 1) for m in range(1, 27)]


def fetch(u):
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")


# ── URL 發現：從 tag 頁掃出所有 patch note URL ──────────────────────────────

def _url_to_pk(href):
    """把 /zh-tw/news/game-updates/patch-26-13-notes → '26.13'
    支援三種格式：
      patch-26-13-notes       → major=26（兩位年份）
      patch-25-s1-1-notes     → major=25, s1格式
      patch-2025-s1-3-notes   → major=2025（完整四位年份）
    """
    slug = href.rstrip("/").split("/")[-1]
    slug = re.sub(r"^league-of-legends-", "", slug)
    slug = re.sub(r"^patch-|-notes$", "", slug)
    m = re.match(r"^(\d+)-s\d+-(\d+)$", slug)
    if m:
        major, minor = int(m.group(1)), int(m.group(2))
    else:
        m = re.match(r"^(\d+)-(\d+)$", slug)
        if not m:
            return None
        major, minor = int(m.group(1)), int(m.group(2))
    # major 可能是完整西元年(>=2000)、兩位年份(>=15)、或舊序號(<=14)
    if major >= 2000:
        year = major
    elif major <= 14:
        year = major + 2010
    else:
        year = major + 2000
    return f"{year % 100}.{minor:02d}"


def discover_urls(force=False):
    """用 Playwright 滾動 tag 頁取得所有 patch note 的真實 URL；結果快取到 patch_urls.json。"""
    urls_path = os.path.join(CACHE, "patch_urls.json")
    if os.path.exists(urls_path) and not force:
        return json.load(open(urls_path, encoding="utf-8"))

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("⚠ 未安裝 playwright，跳過 URL 發現（pip install playwright && python -m playwright install chromium）")
        return {}

    print("掃描 Riot tag 頁取得所有版本 URL…")
    url_map = {}  # pk → full_url (zh-tw 優先)

    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        pg = br.new_page()

        for lang in ("zh-tw", "en-us"):
            tag_url = f"https://www.leagueoflegends.com/{lang}/news/tags/patch-notes/"
            pg.goto(tag_url, wait_until="networkidle", timeout=30000)
            prev = 0
            stale = 0
            while stale < 3:
                pg.keyboard.press("End")
                pg.wait_for_timeout(2000)
                links = pg.evaluate("""() =>
                    Array.from(document.querySelectorAll('a[href]'))
                        .map(a => a.getAttribute('href'))
                        .filter(h => h && /patch.*notes/.test(h))
                """)
                if len(links) == prev:
                    stale += 1
                else:
                    stale = 0
                    prev = len(links)

            for href in links:
                pk = _url_to_pk(href)
                if not pk:
                    continue
                if href.startswith("/"):
                    href = f"https://www.leagueoflegends.com{href}"
                # zh-tw 優先；en-us 只補沒被 zh-tw 填到的
                if pk not in url_map or lang == "zh-tw":
                    url_map[pk] = href

            print(f"  {lang}：找到 {len(url_map)} 個版本")
            if lang == "zh-tw" and url_map:
                break  # zh-tw 就夠了，en-us 當 fallback 備而不用

        br.close()

    os.makedirs(CACHE, exist_ok=True)
    json.dump(url_map, open(urls_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"URL 目錄：{len(url_map)} 版本 → {urls_path}")
    return url_map


def get_html(major, minor, url_map=None):
    """先用已知 URL；沒有再猜格式。先試繁中，繁中 404 再試英文。"""
    year = (major + 2010) if major <= 14 else (major + 2000)
    pk = f"{year % 100}.{minor:02d}"

    # 從 tag 頁發現的 URL 直接取用（不用猜）
    if url_map and pk in url_map:
        discovered = url_map[pk]
        for lang in ("zh-tw", "en-us"):
            u = discovered.replace("/zh-tw/", f"/{lang}/").replace("/en-us/", f"/{lang}/")
            try:
                return fetch(u), u, lang
            except Exception:
                continue

    # fallback：格式猜測（9.1 以前的舊版，或 tag 頁沒掃到的版本）
    for lang in ("zh-tw", "en-us"):
        m2 = f"{minor:02d}"
        for fmt in (f"patch-{major}-{minor}-notes", f"patch-{major}-{m2}-notes",
                    f"patch-{major}-s1-{minor}-notes", f"patch-{major}-s1-{m2}-notes",
                    f"patch-{year}-s1-{minor}-notes", f"patch-{year}-s1-{m2}-notes",
                    f"league-of-legends-patch-{major}-{minor}-notes",
                    f"league-of-legends-patch-{major}-{m2}-notes"):
            u = f"https://www.leagueoflegends.com/{lang}/news/game-updates/{fmt}/"
            try:
                return fetch(u), u, lang
            except Exception:
                continue
    return None, None, None


def clean(s):
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", H.unescape(s)).strip()


# 非英雄的分區標題：一遇到就代表英雄段落結束，後面（競技場增幅裝置/道具/系統/錯誤修正/
# 頁尾相關文章…）不屬於這隻英雄。字母序最後的英雄最容易把整個尾巴吃進來。
BREAK_TITLES = (
    "增幅裝置", "特別嘉賓", "系統", "道具", "裝備", "英雄", "符文", "錯誤修正", "遊戲更新",
    "競技場", "旅法師", "小兵", "野怪", "地圖", "史詩級", "電競", "活動", "商城", "新內容",
    "即將到來", "實用資訊", "回饋", "平衡", "資訊",
    # 英文頁的分區標題(2019~2022 抓英文版時用)
    "Items", "Item", "Runes", "Rune", "Arena", "Bugfixes", "Bug Fixes", "Systems", "System",
    "ARAM", "Jungle", "Minions", "Summoner Spells", "Objectives", "Map", "Emotes", "Store",
    "Upcoming", "Behavioral", "Ranked", "Skins", "Champion Skins", "Chromas", "Esports",
)


# 英文 → 繁中 術語對照(規則式；長片語在前，短詞在後，避免被先吃掉)。技能名與複雜句可能殘留英文。
GLOSSARY = [
    ("Base Attack Damage", "基礎攻擊力"), ("Bonus Attack Damage", "額外攻擊力"), ("Attack Damage", "攻擊力"),
    ("Base Attack Speed", "基礎攻擊速度"), ("Attack Speed", "攻擊速度"), ("Attack Range", "攻擊距離"),
    ("Ability Power", "法術強度"), ("Ability Haste", "技能急速"), ("Haste", "急速"),
    ("Base Health Regen", "基礎生命回復"), ("Health Regen", "生命回復"),
    ("Max Health", "最大生命值"), ("Base Health", "基礎生命值"), ("Health", "生命值"),
    ("Base Mana Regen", "基礎魔力回復"), ("Mana Regen", "魔力回復"),
    ("Mana Cost", "魔力消耗"), ("Base Mana", "基礎魔力"), ("Mana", "魔力"),
    ("Energy Cost", "能量消耗"), ("Energy", "能量"),
    ("Cooldown", "冷卻時間"),
    ("Magic Resistance", "魔法抗性"), ("Magic Resist", "魔法抗性"), ("Armor", "護甲"),
    ("Movement Speed", "移動速度"),
    ("Bonus Magic Damage", "額外魔法傷害"), ("Base Damage", "基礎傷害"),
    ("Magic Damage", "魔法傷害"), ("Physical Damage", "物理傷害"), ("True Damage", "真實傷害"),
    ("Bonus Damage", "額外傷害"), ("Total Damage", "總傷害"), ("Damage", "傷害"),
    ("Shield Strength", "護盾值"), ("Shield", "護盾"), ("Healing", "治療量"), ("Heal", "治療"),
    ("Slow Duration", "減速持續時間"), ("Stun Duration", "暈眩持續時間"), ("Duration", "持續時間"),
    ("Slow", "減速"), ("Stun", "暈眩"), ("Root", "定身"), ("Knockup", "擊飛"),
    ("Cast Range", "施法距離"), ("Range", "範圍"), ("Ratio", "係數"),
    ("Critical Strike", "暴擊"), ("Crit", "暴擊"), ("Lifesteal", "生命偷取"), ("Omnivamp", "全能吸血"),
    ("Spellvamp", "法術吸血"), ("Spell Vamp", "法術吸血"),
    ("New Effect", "新效果"), ("Removed", "移除"), ("New", "新增"),
    ("Maximum", "最大"), ("Minimum", "最小"), ("Base", "基礎"), ("Bonus", "額外"), ("Total", "總"),
    ("Max", "最大"), ("Min", "最小"),
    ("per second", "每秒"), ("per level", "每級"), ("per stack", "每層"), ("per", "每"),
    ("seconds", "秒"), ("second", "秒"),
    ("all ranks", "所有等級"),
    ("increased", "提高"), ("decreased", "降低"), ("reduced", "降低"), ("lowered", "降低"),
    ("Passive", "被動"), ("Active", "主動"),
    ("Bug Fix", "錯誤修正"), ("Bugfix", "錯誤修正"),
    ("stacks", "層數"), ("stack", "層"), ("now", "現在"), ("Attack", "攻擊"),  # 複數＝層數（單獨當標籤時「層」看不懂）
]


# 前置詞庫：長片語/句型優先於 GLOSSARY 處理（皆以原始英文撰寫，順序=先長後短）
GLOSSARY_PRE = [
    ("Calibrum", "通碧"), ("Severum", "斷魄"), ("Gravitum", "墜明"),
    ("Infernum", "熒焰"), ("Crescendum", "折鏡"),  # 亞菲利歐五把武器官方譯名
    ("Undocumented / Bug fix:", "（官方未記載／錯誤修正）"), ("Undocumented/Bug fix:", "（官方未記載／錯誤修正）"),
    ("Undocumented / Bug Fix:", "（官方未記載／錯誤修正）"), ("Undocumented:", "（官方未記載）"),
    ("Undocumented", "（官方未記載）"),
    ("draws nearby minion aggro when targeting an enemy champion", "指向敵方英雄時會吸引附近小兵的仇恨"),
    ("Fixed a bug where", "錯誤修正："), ("Fixed an issue where", "錯誤修正："),
    ("Fixed a bug that", "錯誤修正："), ("Fixed an error where", "錯誤修正："),
    ("recommended items updated", "推薦裝備更新"), ("updated recommended items", "推薦裝備更新"),
    ("ability tooltips updated", "技能說明更新"), ("tooltips updated", "說明更新"),
    ("tooltip updated", "說明更新"), ("updated tooltip", "說明更新"),
    ("updated visual effects", "視覺效果更新"), ("new visual effects", "視覺效果更新"),
    ("visual effects", "視覺效果"),
    ("new ability icons", "技能圖示更新"), ("updated ability icons", "技能圖示更新"),
    ("new ability icon", "技能圖示更新"), ("ability icons", "技能圖示"), ("ability icon", "技能圖示"),
    ("new splash artwork", "原畫更新"), ("updated splash artwork", "原畫更新"), ("splash artwork", "原畫"),
    ("new lore", "背景故事更新"),
    ("new voice over", "語音更新"), ("new voiceover", "語音更新"), ("new voice-over", "語音更新"),
    ("updated voice over", "語音更新"),
    ("complete overhaul", "全面重做"), ("full relaunch", "全面重製"),
    ("recolored from base", "由基礎造型重新上色"),
    ("based on level", "依等級"), ("at all levels", "（所有等級）"),
    ("of the target's maximum health", "目標最大生命的"), ("target's maximum health", "目標最大生命"),
    ("of the target's current health", "目標當前生命的"), ("target's current health", "目標當前生命"),
    ("of target's missing health", "目標已損失生命的"), ("target's missing health", "目標已損失生命"),
    ("grievous wounds", "重傷"),
    ("cast time", "施放時間"),
    ("effect radius", "作用半徑"), ("selection radius", "選取半徑"),
    ("projectile speed", "彈道速度"), ("missile speed", "彈道速度"),
    ("basic attacks", "普攻"), ("basic attack", "普攻"),
    ("on-hit effects", "命中效果"), ("on-hit", "命中觸發"),
    ("against enemy champions", "對敵方英雄"), ("against champions", "對英雄"),
    ("against monsters", "對野怪"), ("to monsters", "對野怪"), ("against minions", "對小兵"),
    ("enemy champions", "敵方英雄"), ("enemy champion", "敵方英雄"), ("allied champions", "友方英雄"),
    ("no longer deals", "不再造成"), ("is no longer", "不再是"), ("no longer", "不再"),
    ("now deals", "現在造成"), ("damage dealt", "造成的傷害"), ("damage taken", "受到的傷害"),
    ("now scales with", "改為隨"), ("scales with", "隨"),
    ("instead of", "而非"),
    ("regeneration growth", "回復成長"), ("regeneration", "回復"),
    ("resistances", "雙抗"), ("tenacity", "韌性"),
    ("undocumented", "（官方未記載）"),
    ("empowered", "強化的"), ("unchanged", "不變"),
    ("capped at", "上限為"), ("equal to", "等同"),
    ("second cast", "第二段施放"), ("first cast", "第一段施放"), ("recast", "再次施放"),
    ("knocked up", "被擊飛"), ("knocked back", "被擊退"),
    ("stunned", "被暈眩"), ("rooted", "被定身"), ("slowed", "被緩速"), ("shielded", "獲得護盾的"),
    ("rift herald", "預示者"), ("red buff", "紅BUFF"), ("blue buff", "藍BUFF"),
    ("experience", "經驗值"), ("smite", "重擊"),
    ("turrets", "防禦塔"), ("turret", "防禦塔"), ("towers", "防禦塔"), ("tower", "防禦塔"),
    ("inhibitors", "水晶兵營"), ("inhibitor", "水晶兵營"), ("nexus", "主堡"),
    ("baron nashor", "巴龍"), ("baron", "巴龍"), ("elder dragon", "遠古巨龍"), ("dragon", "飛龍"),
    ("monsters", "野怪"), ("monster", "野怪"), ("minions", "小兵"), ("minion", "小兵"),
    ("champions", "英雄"), ("champion", "英雄"),
    ("enemies", "敵人"), ("enemy", "敵方"), ("allies", "友方"), ("ally", "友方"),
    ("targets", "目標"), ("target", "目標"), ("units", "單位"), ("unit", "單位"),
    ("dealing", "造成"), ("deals", "造成"),
    ("restores", "回復"), ("gains", "獲得"), ("grants", "給予"),
    ("melee", "近戰"), ("ranged", "遠程"),
    ("charges", "充能次數"), ("modifier", "加成"), ("growth", "成長"),
    ("ultimate", "大絕"), ("ability", "技能"), ("abilities", "技能"),
    ("properly", "正確"), ("additionally", "此外"),
    ("percent", "百分比"), ("vfx", "特效"), ("sfx", "音效"),
    ("cost", "費用"), ("price", "價格"), ("gold", "金錢"), ("recipe", "合成公式"),
    # 第四輪內容詞
    ("unique", "唯一"), ("chance", "機率"), ("within", "在"), ("nearby", "附近"),
    ("missing", "已損失"), ("original", "原本"), ("adjusted", "調整"), ("applies", "套用"),
    ("attacks", "攻擊"), ("attacking", "攻擊"), ("charges", "充能"), ("charge", "充能"),
    ("triggers", "觸發"), ("trigger", "觸發"), ("location", "位置"),
    ("restored", "回復"), ("restore", "回復"), ("minutes", "分鐘"), ("minute", "分鐘"),
    ("additional", "額外"), ("affected", "受影響"), ("initial", "初始"), ("innate", "被動"),
    ("increases", "提高"), ("increase", "提高"), ("direction", "方向"), ("hitting", "命中"),
    ("intended", "預期"), ("killing", "擊殺"), ("kills", "擊殺"), ("kill", "擊殺"),
    ("reduces", "降低"), ("reduce", "降低"), ("causes", "使"), ("cause", "使"),
    ("scaling", "係數"), ("granting", "給予"), ("slowing", "緩速"), ("damaging", "傷害"),
    ("secondary", "次要"), ("current", "當前"), ("rather", "而"), ("remaining", "剩餘"),
    ("strength", "強度"), ("power", "強度"), ("structures", "建築物"), ("physical", "物理"),
    ("taking", "受到"), ("deal", "造成"), ("gain", "獲得"), ("every", "每"),
    ("next", "下一次"), ("other", "其他"), ("but", "但"), ("sometimes", "有時"),
    ("correctly", "正確"), ("using", "使用"), ("radius", "半徑"), ("same", "相同"),
    ("through", "穿過"), ("timer", "計時器"), ("game", "遊戲"), ("added", "新增"),
    ("death", "死亡"), ("amount", "數值"), ("old", "舊"), ("tick", "跳動"),
    ("items", "道具"), ("item", "道具"), ("displays", "顯示"), ("speed", "速度"),
    ("even", "即使"), ("any", "任何"), ("indicator", "指示器"), ("delay", "延遲"),
    ("quest", "任務"), ("skins", "造型"), ("terrain", "地形"), ("large", "大型"),
    ("wards", "守衛"), ("ward", "守衛"), ("distance", "距離"), ("performs", "執行"),
    ("your", "你的"), ("you", "你"), ("one", "一"), ("besides", "除了"),
    # 第五輪內容詞
    ("movement", "移動"), ("based", "依"), ("level", "等級"), ("tooltip", "說明"),
    ("dashes", "衝刺"), ("dash", "衝刺"), ("fixed", "修正"), ("non-", "非"),
    ("stats", "屬性"), ("combat", "戰鬥"), ("missile", "彈道"),
    ("strikes", "打擊"), ("strike", "打擊"), ("both", "兩者"), ("used", "使用"),
    ("vision", "視野"), ("allied", "友方"), ("marked", "被標記"), ("mark", "印記"),
    ("jungle", "野區"), ("around", "周圍"), ("skin", "造型"), ("changed", "變更"),
    ("applying", "套用"), ("applied", "套用"), ("apply", "套用"),
    ("critically", "暴擊"), ("critical", "暴擊"), ("between", "之間"), ("dies", "死亡"),
    ("team", "隊伍"), ("moving", "移動中"), ("mist", "迷霧"), ("incorrectly", "錯誤地"),
    ("display", "顯示"), ("spawn", "生成"), ("no", "無"), ("summoner", "召喚師"),
    ("bug", "錯誤"), ("stealth", "隱形"), ("until", "直到"),
    ("takes", "受到"), ("take", "受到"), ("could", "可能"), ("uses", "使用"), ("use", "使用"),
    ("ends", "結束"), ("end", "結束"), ("below", "低於"), ("rank", "等級"),
    ("visible", "可見"), ("ground", "地面"), ("slows", "緩速"),
    ("plays", "播放"), ("play", "播放"), ("number", "數量"), ("immediately", "立即"),
    ("full", "完整"), ("form", "型態"), ("towards", "朝向"), ("toward", "朝向"),
    ("cap", "上限"), ("killed", "被擊殺"), ("certain", "特定"), ("does", "會"),
    ("able", "能夠"), ("targeting", "指定"), ("two", "兩"), ("clone", "分身"),
    ("then", "然後"), ("last", "最後"), ("shields", "護盾"), ("value", "數值"),
    ("basic", "基礎"), ("size", "大小"), ("near", "靠近"), ("renamed", "更名"),
    ("always", "總是"), ("explosion", "爆炸"), ("brush", "草叢"), ("match", "對局"),
    ("sight", "視野"), ("particles", "粒子效果"), ("particle", "粒子效果"), ("stacking", "疊加"),
    ("width", "寬度"), ("caused", "導致"), ("causing", "導致"), ("gaining", "獲得"),
    ("correct", "正確"), ("automatically", "自動"), ("model", "模型"), ("move", "移動"),
    ("instantly", "立即"), ("heals", "治療"), ("becomes", "變為"), ("fires", "發射"), ("fire", "發射"),
    ("away", "遠離"), ("without", "無需"), ("fury", "怒氣"), ("start", "開始"),
    ("multiple", "多個"), ("wall", "牆體"), ("consumed", "消耗"), ("consumes", "消耗"),
    ("reveals", "顯現"), ("triggered", "被觸發"), ("triggering", "觸發"), ("subsequent", "後續"),
    ("caster", "施放者"), ("energized", "充能"), ("players", "玩家"), ("player", "玩家"),
    ("himself", "自身"), ("herself", "自身"), ("itself", "自身"), ("another", "另一個"),
    ("available", "可用"), ("collision", "碰撞"), ("recall", "回城"), ("line", "直線"),
    ("spirit", "靈魂"), ("point", "點"), ("third", "第三"), ("resets", "重置"), ("reset", "重置"),
    ("upgrade", "升級"), ("cursor", "游標"), ("gained", "獲得"), ("some", "某些"),
    ("note", "附註"), ("rift", "峽谷"), ("bounty", "賞金"), ("vo", "語音"),
    ("activation", "啟動"), ("aura", "光環"), ("hud", "介面"), ("under", "於"),
    ("improved", "改善"), ("windup", "前搖"), ("reward", "獎勵"), ("projectile", "射彈"),
    ("twice", "兩次"), ("threshold", "門檻"), ("increasing", "提高"), ("least", "至少"),
    ("disabled", "停用"), ("type", "類型"), ("primary", "主要"), ("untargetable", "不可被指定"),
    ("changes", "改動"), ("shot", "射擊"), ("fixes", "修正"), ("fix", "修正"),
    ("on", ""), ("in", ""), ("as", ""), ("be", ""), ("up", ""), ("of", ""), ("into", ""), ("which", ""), ("out", ""),
    ("off", ""), ("were", ""), ("who", ""), ("well", ""), ("so", ""), ("back", ""),
]

# 最優先片語（必須先於 GLOSSARY_PRE 內的短片語）
PRE_TOP = [
    # ── 片語一定要放這張最高優先表 ──
    # GLOSSARY_PRE 會先把 damage/max 等單字換成中文，片語表若放在 GLOSSARY 就永遠比對不到英文原文
    # （曾因此把 Max stacks 翻成只剩「層」、Damage per stack 翻成「傷害每層」）
    ("max stacks", "最大層數"), ("maximum stacks", "最大層數"), ("max stack", "最大層數"),
    ("stacks required", "所需層數"),
    ("damage per stack", "每層傷害"), ("damage per second", "每秒傷害"),   # 「X per Y」中文要倒過來講
    ("damage per hit", "每次命中傷害"), ("damage per tick", "每跳傷害"),
    ("can no longer", "不再能"), ("now specifies that", "現在會標明"),
    ("damage reduction", "傷害減免"), ("crowd control", "控場"),
    ("fixed a bug", "錯誤修正"), ("fixed an issue", "錯誤修正"),
    ("more than", "超過"), ("less than", "低於"),
    # 連字號複合詞：必須在逐字翻譯前整組吃掉，否則「of」被翻成空字串後連字號會留下來變成
    # 「範圍--效果」「--戰鬥計時器」（連字號殘留 bug，2026-07-15 修）
    ("out-of-combat", "脫離戰鬥"), ("out of combat", "脫離戰鬥"),
    ("area-of-effect", "範圍效果"), ("area of effect", "範圍效果"),
    ("damage-over-time", "持續傷害"), ("damage over time", "持續傷害"),
    ("per cast", "每次施放"),
    ("range indicator", "範圍指示器"),
    # 道具價格類（對照官方繁中公告用詞）
    ("recipe cost", "合成費用"), ("combine cost", "合成費用"), ("combination cost", "合成費用"),
    ("total gold cost", "總價"), ("total cost", "總價"),
    ("sell value", "售價"), ("sells for", "售價"), ("sell price", "售價"),
    # 第四輪片語
    ("fog of war", "戰爭迷霧"), ("tick interval", "跳動間隔"),
    ("on-cast", "施放時"), ("on-kill", "擊殺時"), ("on-attack", "攻擊時"),
    ("chinese art", "中版美術"), ("life steal", "生命偷取"), ("builds into", "可合成為"),
    ("magic penetration", "法術穿透"), ("armor penetration", "物理穿透"),
    ("critical strike chance", "暴擊率"), ("maximum hits", "最大命中次數"), ("max hits", "最大命中次數"),
    ("additional checks", "額外判定"), ("control wards", "控制守衛"), ("stealth wards", "隱形守衛"),
    ("voice lines", "語音台詞"), ("health bar", "血條"), ("combat text", "戰鬥文字"),
    ("movement speed", "移動速度"), ("at least", "至少"),
    ("at all ranks", "（所有等級）"), ("bug fixes", "錯誤修正"),
]
# 尾端語綴：代名詞/連接詞/冠詞清理（在術語都換完後才跑，降低誤傷）
GLOSSARY_TAIL = [
    ("interrupted", "被中斷"), ("channeling", "引導"), ("channel", "引導"),
    ("debuff", "減益效果"), ("buff", "增益效果"),
    ("loses", "失去"), ("lose", "失去"), ("granted", "給予"), ("grant", "給予"),
    ("reduction", "減免"),
    ("casting", "施放"), ("casts", "施放"), ("cast", "施放"),
    ("hits", "命中"), ("hit", "命中"),
    ("effects", "效果"), ("effect", "效果"),
    ("times", "次"), ("time", "時間"),
    ("updated", "更新"), ("update", "更新"),
    ("based on", "依"), ("shows", "顯示"), ("show", "顯示"),
    ("will", "將"), ("cannot", "無法"), ("can", "可"),
    ("when", "當"), ("while", "期間"), ("during", "期間"),
    ("after", "之後"), ("before", "之前"), ("if", "若"),
    ("all", "所有"), ("longer", "更長"), ("not", "不"),
    ("and", "且"), ("or", "或"),
    ("his", "其"), ("her", "其"), ("their", "其"), ("its", "其"),
    ("animations", "動畫"), ("animation", "動畫"),
    ("spells", "技能"), ("spell", "技能"),
    ("area", "範圍"), ("each", "每個"), ("only", "僅"),
    ("this", "此"), ("these", "這些"), ("those", "那些"),
    ("more", "更多"), ("less", "更少"),
    ("upon", "於"), ("against", "對"), ("from", "從"),
    ("would", "會"), ("should", "應"),
    ("them", "其"), ("they", "其"), ("she", "她"), ("him", "他"), ("he", "他"),
    ("first", "首次"), ("also", "同時"), ("still", "仍"), ("again", "再次"), ("once", "一次"),
    ("slightly", "略微"), ("significantly", "大幅"),
    ("visual", "視覺"), ("sound", "音效"), ("icons", "圖示"), ("icon", "圖示"),
    ("the", ""), ("an", ""), ("a", ""), ("is", ""), ("are", ""), ("was", ""),
    ("has", ""), ("have", ""), ("had", ""), ("been", ""), ("being", ""),
    ("that", ""), ("to", ""), ("with", ""), ("where", ""), ("than", ""),
    ("at", ""), ("by", ""), ("it", ""),
]

_COMPILED = None
def _compiled():
    """詞條總數超過 re 模組 512 條快取上限，必須預編譯否則每行重編譯、慢一個數量級"""
    global _COMPILED
    if _COMPILED is None:
        # 詞條裡的空格編成 [\s-]+：wiki 原文常寫連字號複合詞（per-stack / out-of-combat / area-of-effect），
        # 只收空格版的話會逐字翻成「每-層」「--戰鬥」（連字號殘留 bug，2026-07-15 修）
        _COMPILED = [(re.compile(r"(?<![A-Za-z])" + re.escape(en).replace(r"\ ", r"[\s\-]+") + r"(?![A-Za-z])", re.I), zh)
                     for tbl in (PRE_TOP, GLOSSARY_PRE, GLOSSARY, GLOSSARY_TAIL) for en, zh in tbl]
    return _COMPILED

def translate(line):
    for rx, zh in _compiled():
        line = rx.sub(zh, line)
    line = re.sub(r"(?<![A-Za-z])for\s+(?=\d)", "持續 ", line, flags=re.I)  # for 3 秒 → 持續 3 秒
    line = re.sub(r"(?<![A-Za-z])for(?![A-Za-z])", "", line, flags=re.I)
    line = re.sub(r"(?<![A-Za-z])over\s+(?=\d)", "歷時 ", line, flags=re.I)  # over 3 秒 → 歷時 3 秒
    line = re.sub(r"(?<![A-Za-z])over(?![A-Za-z])", "", line, flags=re.I)
    line = re.sub(r"(\d)\s*g(?![A-Za-z])", r"\1金", line)                    # 300g → 300金
    line = re.sub(r"'s(?![A-Za-z])", "的", line)                             # target's → 目標的
    for a in ("Q", "W", "E", "R"):
        line = line.replace("(" + a + ")", "（" + a + "）")
    line = line.replace("(Passive)", "（被動）").replace("(Innate)", "（被動）")
    # 收尾：中文字之間的殘留空格收攏、英式標點轉全形、多空格壓一
    if re.search(r"[一-鿿]", line):
        line = re.sub(r"(?<=[一-鿿）」])\s+(?=[一-鿿（「])", "", line)
        line = re.sub(r"\.\s*$", "。", line).replace(" ,", "，").replace(" .", "。")
        line = line.replace("(", "（").replace(")", "）")  # 半形括號一律轉全形
        # 屬性同義詞統一（使用者指定簡稱：物攻/物防/魔攻/魔防）
        line = re.sub(r"物理攻擊力|物理攻擊|攻擊力", "物攻", line)
        line = re.sub(r"物理防禦|護甲", "物防", line)
        line = re.sub(r"魔法防禦|魔法抗性|魔抗", "魔防", line)
        line = re.sub(r"法術強度|法強", "魔攻", line)
        line = re.sub(r"(?<=\d):(?=\d)", "\x00", line)      # 保護 比例/時間 的 數字:數字
        line = re.sub(r"\s*:\s*", "：", line)                # 其餘半形冒號 → 全形
        line = line.replace("\x00", ":")
    line = re.sub(r"\+\s+(?=\d)", "+", line)                 # + 與數字之間不留空格
    # 空連字號清理（保險層）：詞庫沒收到的連字號複合詞，逐字翻譯後會留下孤立的 - / --
    line = re.sub(r"-{2,}(?=戰鬥)", "脫離", line)             # out-of-combat：直接刪連字號會掉「脫離」語意
    line = re.sub(r"([一-鿿])-+(?=[一-鿿])", r"\1", line)      # 中文之間
    line = re.sub(r"(^|[｜|：、，。\s])-+(?=[一-鿿])", r"\1", line)  # 句首/分隔後
    line = re.sub(r"-{2,}", "-", line)                       # 其餘多重連字號（英文專名）
    line = re.sub(r"：{2,}", "：", line)                      # 標籤本身已帶冒號時會變「魔力消耗：：」
    line = re.sub(r"[（(]\s*[+＋×xX]?\s*[)）]", "", line)      # 係數被剝掉後留下的空括號「（+ ）」
    line = re.sub(r"(\d)\s+%", r"\1%", line)                 # 「25 % 跑速」→「25%」（% 黏著數字）
    line = re.sub(r"%\s+(?=[（(])", "%", line)               # 「30% （+3% AP）」→「30%（+3% AP）」
    # wiki 連結/圖示被剝掉後留下的孤立標點：「更新音效效果，， 且。」
    line = re.sub(r"[，、]\s*(?=[，、。])", "", line)
    line = re.sub(r"[：，、]\s*(?=。)", "", line)
    line = re.sub(r"，\s*(?:且|或|和)\s*。", "。", line)
    line = re.sub(r"[ \t]{2,}", " ", line).strip()
    return line


# ── 翻譯品質守門：人工精譯表優先；規則式翻完仍中英混雜 → 整段顯示英文原文 ──
_MANUAL_TR = None

def _manual_tr():
    global _MANUAL_TR
    if _MANUAL_TR is None:
        try:
            _MANUAL_TR = json.load(open(os.path.join(HERE, "scripts", "manual_tr.json"), encoding="utf-8"))
        except Exception:
            _MANUAL_TR = {}
    return _MANUAL_TR

# 白名單：台灣慣例保留英文的縮寫／模式名／UI詞（這些出現在中文行裡不算「未翻譯殘留」）
_ALLOW_EN = re.compile(
    r"(?<![A-Za-z])("
    r"AP|AD|HP|MP|MS|CD|CS|XP|DPM|KDA|Lv|LV|"
    r"ARAM|ARURF|ARSR|URF|ARSR|"                         # 遊戲模式
    r"HUD|UI|UX|FPS|IP|LP|DoT|AoE|PvP|PvE|PVP|PVE|"       # 介面／系統
    r"PT|PST|PDT|PBE|NA|OCE|SEA|EUW|EUNE|"                # 時區／伺服器
    r"DX9|DX11|Alt|Ctrl|Shift|BUFF|Clash|MISSION|"        # 快捷鍵／雜項
    r"[QWERXV]"
    r")(?![A-Za-z])")

def mixed_en(t):
    """中英混雜（翻譯殘留）：有中文且仍含 ≥2 字母的英文詞（白名單縮寫除外）"""
    if not re.search(r"[一-鿿]", t):
        return False
    return bool(re.search(r"[A-Za-z]{2,}", _ALLOW_EN.sub("", t)))

# 行前綴（wiki 章節/野怪營地等）對照：前綴英文不算混雜，直接換繁中
PREFIX_MAP = {
    "Stats": "屬性", "General": "通用", "Abilities": "技能",
    "Krug camp": "石甲蟲營地", "Raptor camp": "猛禽營地", "Murk Wolf camp": "暗狼營地",
    "Gromp camp": "蛤蟆營地", "Gromp": "蛤蟆", "Krug": "石甲蟲", "Raptor": "猛禽",
    "Murk Wolf": "暗狼", "Wolf": "暗狼", "Blue Sentinel": "藍色哨兵", "Red Brambleback": "紅色荊棘背魔",
    "Rift Scuttler": "河道潛行者", "Rift Herald": "峽谷先鋒", "Baron Nashor": "巴龍",
    "Dragon": "小龍", "Elemental Drakes": "元素龍", "Turrets": "防禦塔", "Turret": "防禦塔",
    "Minions": "小兵", "Monsters": "野怪", "Jungle": "野區",
}

def translate_line(l):
    man = _manual_tr()
    key = l.strip()
    if key in man:
        return man[key]
    i = l.find("｜")
    if i > 0:
        pre, body = l[:i].strip(), l[i+1:]
        pre = PREFIX_MAP.get(pre, pre)
        t = translate(body)
        if mixed_en(t):                    # 內文翻不乾淨 → 內文顯示原文（前綴照換）
            res = f"{pre}｜{body.strip()}"
        else:
            res = f"{pre}｜{t}"
    else:
        t = translate(l)
        res = l if mixed_en(t) else t
    return man.get(res.strip(), res)       # 精譯表也可用「輸出形」當 key


_ai_client = None

def _get_ai_client():
    global _ai_client
    if _ai_client is None:
        try:
            import anthropic
            _ai_client = anthropic.Anthropic()
        except Exception as e:
            print(f"⚠ 無法初始化 Claude API：{e}")
            _ai_client = False
    return _ai_client if _ai_client else None


def ai_translate_champ(champ_en, lines_en):
    """用 Claude API 把英文 patch note 改動翻成台灣繁中官方公告風格。
    lines_en: list of strings，每行格式可能是 "技能名｜文字" 或純文字。
    回傳 list of strings。
    """
    client = _get_ai_client()
    if not client:
        return [translate(l) for l in lines_en]
    try:
        content = "\n".join(lines_en)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            messages=[{"role": "user", "content":
                f"以下是英雄聯盟官方版本公告的英雄改動內容（英雄：{champ_en}）。"
                "請翻譯成台灣官方版本公告的繁體中文風格，保留⇒符號、｜分隔符、數字格式、Q/W/E/R/被動等縮寫。"
                "每行輸入對應一行輸出，不要加說明。\n\n" + content
            }]
        )
        result = msg.content[0].text.strip().split("\n")
        out = [l.strip() for l in result if l.strip()]
        # 如果行數對不上就 fallback
        return out if len(out) == len(lines_en) else [translate(l) for l in lines_en]
    except Exception as e:
        print(f"  ⚠ AI 翻譯失敗({champ_en}): {e}")
        return [translate(l) for l in lines_en]


def cut_at_section(blk):
    """把英雄區塊截斷到第一個「非英雄分區標題」之前，濾掉被誤灌進來的其他段落。"""
    cut = len(blk)
    for hm in re.finditer(r"<h[2-5][^>]*>(.*?)</h[2-5]>", blk, re.S):
        t = clean(hm.group(1))
        if t and any(t == b or t.startswith(b) for b in BREAK_TITLES):
            cut = hm.start()
            break
    return blk[:cut]


# 非英雄的改動分類(給版本改動第六欄)：道具/符文/機制/召喚師技能
EXTRA_CATS = [
    ("道具", ("道具", "裝備")),
    ("符文", ("符文",)),
    ("機制", ("系統", "機制")),
    ("召喚師技能", ("召喚師",)),
]


# 遇到這些標題代表已離開道具/符文/機制區(進入競技場/積分/活動…)→ 停止
STOP_HEADERS = ("召喚峽谷積分", "競技場", "活動", "增幅裝置", "特別嘉賓", "電競", "實用資訊",
                "遊戲更新", "即將", "賽事", "隨機單中", "大亂鬥", "ARAM")


_ITEM_NAMES = None
def item_names():
    """全時代道具名單（來源：CDragon zh_tw 字串表快取，含已移除道具）——新道具介紹行的白名單"""
    global _ITEM_NAMES
    if _ITEM_NAMES is None:
        _ITEM_NAMES = set()
        try:
            ents = json.load(open(os.path.join(CACHE, "items_st_zhtw.json"), encoding="utf-8"))["entries"]
            for k, v in ents.items():
                if re.fullmatch(r"item_\d+_name", k) and isinstance(v, str) and v.strip():
                    _ITEM_NAMES.add(v.strip())
        except Exception:
            pass
    return _ITEM_NAMES

SECTION_WORDS = {"道具", "符文", "機制", "裝備", "召喚師技能", "系統"}   # 區段標題（不是道具/符文名）

def _grab(seg):
    """抓 seg 內的 子項標題(道具/符文名)＋改動(含 ⇒)，子項標題用 ｜ 帶上。
    **Riot 版型不一致**：有些版本道具名放 <h3>（26.13），有些放獨立 <strong>/<b>（26.12），
    區段標題可能是 <h4>道具</h4>——不能把它當道具名。用「線性掃描」統一處理：
      - 標題來源＝h3~5 或「li 之外」的 strong/b（li 內的 strong 是屬性標籤，會被 li 整段吃掉、不會單獨命中）
      - 排除區段標題字（道具/符文…）與屬性標籤（結尾是 ：/含 ⇒）
    子項標題是已知道具名時，無 ⇒ 的行也收（新道具首發介紹）。"""
    names = item_names()
    lines, cur = [], ""
    for m in re.finditer(r"<(h[3-5])[^>]*>(.*?)</\1>|<li[^>]*>(.*?)</li>|<(strong|b)[^>]*>(.*?)</\4>", seg, re.S):
        if m.group(1):                          # h3~5 標題
            txt = clean(m.group(2))
            if txt and txt not in SECTION_WORDS:
                cur = txt
        elif m.group(3) is not None:            # li 改動行
            t = clean(m.group(3))
            if t and "⇒" in t:
                lines.append(f"{cur}｜{t}" if cur else t)
            elif t and cur and cur in names:
                lines.append(f"{cur}｜{t}")     # 新道具首發介紹
        else:                                   # li 之外的 strong/b＝可能是道具名區塊標題
            txt = clean(m.group(5))
            if txt and txt not in SECTION_WORDS and "⇒" not in txt and not txt.rstrip().endswith(("：", ":")):
                cur = txt
    if not lines:                               # 完全沒抓到標題結構 → 至少收帶 ⇒ 的行
        for li in re.findall(r"<li[^>]*>(.*?)</li>", seg, re.S):
            t = clean(li)
            if t and "⇒" in t:
                lines.append(t)
    seen, uniq = set(), []
    for l in lines:
        if l not in seen:
            seen.add(l); uniq.append(l)
    return uniq


def _cut_stop(seg):
    for hm in re.finditer(r"<h[2-4][^>]*>(.*?)</h[2-4]>", seg, re.S):
        t = clean(hm.group(1))
        if t and any(s in t for s in STOP_HEADERS):
            return seg[:hm.start()]
    return seg


def _sec(html_text, start_id, end_ids):
    i = html_text.find(start_id)
    if i < 0:
        return ""
    ends = [e for e in (html_text.find(x, i + len(start_id)) for x in end_ids) if e >= 0]
    return html_text[i: min(ends) if ends else len(html_text)]


def extract_extra(html_text):
    """抓 道具/符文/機制/召喚師技能 的數值改動(含 ⇒)。用 id 錨點定位、停止標題防止吃到競技場/積分。"""
    out = {}
    # 機制：英雄段之前的所有 patch-* 段(路線任務/遊戲系統/未來新段落都涵蓋)，排除容器/頂部/亮點
    anchors = [(m.group(1), m.start()) for m in re.finditer(r'id="(patch-[a-z0-9\-]+)"', html_text)]
    champ_pos = next((p for n, p in anchors if n == "patch-champions"), len(html_text))
    SKIP = {"patch-notes-container", "patch-top", "patch-patch-highlights",
            "patch-champions", "patch-items", "patch-wasd"}
    mech = []
    for i, (name, pos) in enumerate(anchors):
        if name in SKIP or pos >= champ_pos:
            continue
        end = anchors[i + 1][1] if i + 1 < len(anchors) else len(html_text)
        for l in _grab(_cut_stop(html_text[pos:end])):
            if l not in mech:
                mech.append(l)
    if mech:
        out["機制"] = mech
    # 道具＋符文：patch-items 段(到競技場/其他錨點)，內部再以「符文」標題切開
    it = _sec(html_text, 'id="patch-items"',
              ['id="patch-wasd"', 'id="patch-arena"', 'id="patch-esports"', 'id="patch-download"'])
    if not it:  # 新版型(Riot 2026 改版，只剩 patch-notes-container 錨點)：改用 <h*>道具</h*> 標題定位
        # **只在「競技場之前」找道具**：patch-arena 之後全是競技場專屬道具改動（女妖面紗/魔提斯深/機會…都是競技場的，
        # 不是召喚峽谷的），若整份文件搜尋會抓到競技場的 <h4>道具</h4>。用 patch-arena／<h*>競技場</h*> 當上界。
        arena = re.search(r'id="patch-arena"|id="patch-esports"|<h[1-4][^>]*>\s*競技場\s*</h[1-4]>', html_text)
        scope = html_text[:arena.start()] if arena else html_text
        hm2 = re.search(r'<h[1-4][^>]*>\s*道具\s*</h[1-4]>', scope)
        if hm2:
            it = _cut_stop(scope[hm2.start():])  # _grab 只收 ⇒/已知道具名行，後面系統段會被濾掉
    if it:
        rm = re.search(r"<h[2-4][^>]*>\s*符文\s*</h[2-4]>", it)
        item_seg = _cut_stop(it[:rm.start()] if rm else it)
        li_it = _grab(item_seg)
        if li_it:
            out["道具"] = li_it
        if rm:
            lr = _grab(_cut_stop(it[rm.start():]))
            if lr:
                out["符文"] = lr
    # 召喚師技能：文字標題(若有)
    sm = re.search(r"<h[2-4][^>]*>[^<]*召喚師技能[^<]*</h[2-4]>", html_text)
    if sm:
        seg = html_text[sm.start():]
        nid = re.search(r'id="patch-', seg[20:])
        seg = _cut_stop(seg[: nid.start() + 20] if nid else seg)
        ls = _grab(seg)
        if ls:
            out["召喚師技能"] = ls
    return out


def _champ_slugs():
    """slug → DDragon 英雄 Key（patch-shyvana-update / patch-aurelion-sol-update 這種錨點解析用）。
    快取 csv_cache/champ_slugs.json；slug 取 id 與英文名的純小寫字母形。"""
    cf = os.path.join(CACHE, "champ_slugs.json")
    if os.path.exists(cf):
        return json.load(open(cf, encoding="utf-8"))
    m = {}
    try:
        ver = json.loads(urllib.request.urlopen("https://ddragon.leagueoflegends.com/api/versions.json", timeout=30).read())[0]
        data = json.loads(urllib.request.urlopen(f"https://ddragon.leagueoflegends.com/cdn/{ver}/data/en_US/champion.json", timeout=30).read())["data"]
        for k, v in data.items():
            for s in (k, v.get("name", "")):
                slug = re.sub(r"[^a-z]", "", str(s).lower())
                if slug: m[slug] = k
        json.dump(m, open(cf, "w", encoding="utf-8"))
    except Exception:
        pass
    return m

def champ_spotlights(html_text):
    """官方公告「英雄專屬大區塊」（大型重製/新英雄，位於英雄改動區之前，如 26.06 id=patch-shyvana-update）
    → [(英雄Key, [該區塊解析出的改動行])]；區塊自帶完整改動內容（該英雄通常不再出現在下方英雄區）。"""
    slugs = _champ_slugs()
    end = html_text.find('id="patch-champions"')
    seg = html_text[: end if end > 0 else len(html_text)]
    out, seen = [], set()
    for mm in re.finditer(r'id="patch-([a-z0-9-]+?)-(?:update|rework)"', seg):
        key = slugs.get(re.sub(r"[^a-z]", "", mm.group(1)))
        if not key or key in seen:
            continue
        seen.add(key)
        blk_end = seg.find('id="patch-', mm.end())
        blk = seg[mm.end(): blk_end if blk_end > 0 else len(seg)]
        lines = []
        for am in re.finditer(r"<h4[^>]*>(.*?)</h4>(.*?)(?=<h4|$)", blk, re.S):
            title = clean(am.group(1))
            for li in re.findall(r"<li[^>]*>(.*?)</li>", am.group(2), re.S):
                t = clean(li)
                if t:
                    lines.append(f"{title}｜{t}" if title else t)
        if not lines:
            for li in re.findall(r"<li[^>]*>(.*?)</li>", blk, re.S):
                t = clean(li)
                if t:
                    lines.append(t)
        out.append((key, lines))
    return out

def parse(html_text):
    # 2019~2022 舊版型：用 <div class="attribute-change"> + attribute-before/after；否則走新版型
    if 'class="attribute-change"' in html_text or "attribute-change" in html_text:
        out = parse_old(html_text)
    else:
        out = parse_new(html_text)
    sp = champ_spotlights(html_text)
    if sp:
        out["_spotlight"] = [k for k, _ in sp]   # 大型重製/新英雄專區（前端加註記；_ 開頭中繼欄位，渲染迴圈一律跳過）
        for k, ls in sp:
            if ls:
                out[k] = (out.get(k) or []) + ls  # 專區內容＝該英雄的改動行（重製英雄通常不再出現在下方英雄區）
    return out


def parse_old(html_text):
    """舊版型(2019~2022 英文頁，attribute-change)。英雄段落用「英雄頭像」分界——頭像可能在 <h4> 內(2022)，
    也可能在 <h3 class="change-title"> 前的 <a class="reference-link"><img> 裡(2019~2021)，故一律以頭像出現位置切段。
    限縮在 patch-champions ~ patch-items 之間，避免 Mid-Patch/道具/野怪等誤灌；JUNK_LABEL 再擋非英雄屬性行。"""
    JUNK_LABEL = ("BARON", "DRAGON", "DRAKE", "HERALD", "OBJECTIVE", "BOUNTY", "TURRET",
                  "PLATE", "MINION", "MONSTER", "INHIBITOR", "NEXUS", "GOLD", "XP ")
    # 上界＝道具區(patch-items)起點，排除道具/野怪/相關文章；下界＝頁首(含 Mid-Patch Updates 中期更新，
    # 那也是正式英雄改動、常在 patch-champions 之前)。非改動區塊沒有 attribute-change → 不會誤灌。
    a = html_text.find('id="patch-champions"')
    b = html_text.find('id="patch-items"', a if a >= 0 else 0)
    seg = html_text[: b] if b > 0 else html_text
    heads = list(re.finditer(r"/img/champion/([A-Za-z0-9_]+)\.png", seg))  # 以英雄頭像切段
    out = {}
    for i, m in enumerate(heads):
        key = m.group(1)
        blk = seg[m.start(): heads[i + 1].start() if i + 1 < len(heads) else len(seg)]
        lines = []
        for am in re.finditer(r'<div class="attribute-change">(.*?)</div>', blk, re.S):
            body = am.group(1)
            lb = re.search(r'class="attribute">(.*?)</span>', body, re.S)
            bf = re.search(r'class="attribute-before">(.*?)</span>', body, re.S)
            af = re.search(r'class="attribute-after">(.*?)</span>', body, re.S)
            label = clean(lb.group(1)) if lb else ""
            if any(w in label.upper() for w in JUNK_LABEL):
                continue  # 目標/野怪/金錢等非英雄改動
            bef = clean(bf.group(1)) if bf else ""
            aft = clean(af.group(1)) if af else ""
            if bef and aft:
                lines.append(f"{label}：{bef} ⇒ {aft}" if label else f"{bef} ⇒ {aft}")
            elif aft:
                lines.append(f"{label}：{aft}" if label else aft)
        if lines:
            out[key] = out.get(key, []) + lines
    return out


def parse_new(html_text):
    # 起點：id="patch-champions"；無錨點新版 → 第一個英雄頭像
    a = html_text.find('id="patch-champions"')
    if a < 0:
        fm = re.search(r'/img/champion/[A-Za-z0-9_]+\.png', html_text)
        a = fm.start() if fm else -1
    if a < 0:
        return {}
    # 終點：id="patch-items"；無則第一個道具/符文圖
    b = html_text.find('id="patch-items"', a)
    if b < 0:
        im = re.search(r'/img/(?:item|perk)', html_text[a:])
        b = a + im.start() if im else len(html_text)
    seg = html_text[a:b]
    heads = list(re.finditer(r'/img/champion/([A-Za-z0-9_]+)\.png', seg))
    out = {}
    for i, m in enumerate(heads):
        key = m.group(1)
        blk = seg[m.start(): heads[i + 1].start() if i + 1 < len(heads) else len(seg)]
        blk = cut_at_section(blk)  # 截掉尾巴誤灌的競技場/道具/系統等非英雄內容
        lines, had_h4 = [], False
        # 有 h4 技能標題就帶上（新版）
        for am in re.finditer(r'<h4[^>]*>(.*?)</h4>(.*?)(?=<h4|$)', blk, re.S):
            title = clean(am.group(1))
            for li in re.findall(r'<li[^>]*>(.*?)</li>', am.group(2), re.S):
                t = clean(li)
                if t:
                    lines.append(f"{title}｜{t}" if title else t)
                    if title:
                        had_h4 = True
        # 無 h4 的版型 → 直接抓所有 li
        if not lines:
            for li in re.findall(r'<li[^>]*>(.*?)</li>', blk, re.S):
                t = clean(li)
                if t and ("⇒" in t or "：" in t):
                    lines.append(t)
        # 保留條件：有數值改動(⇒)，或有技能標題結構的純文字改動（如 26.04 雷茲 R 機制修正）
        # ——摘要區誤入的頭像沒有技能標題，仍會被濾掉
        if lines and (any("⇒" in x for x in lines) or had_h4):
            if key not in out or len(lines) > len(out[key]):
                out[key] = lines
    extra = extract_extra(html_text)  # 道具/符文/機制/召喚師技能(用 id 錨點定位)
    if extra:
        out["_extra"] = extra
    return out


def item_debuts():
    """當季新道具首發偵測：掃 DDragon 本季各小版本 item.json 做差集。
    回傳 {道具名: {"pk": "26.05", "lines": [首發介紹行...]}}；結果快取，最新版號沒變就沿用。"""
    vf = os.path.join(CACHE, "item_debut.json")
    try:
        vers = json.loads(urllib.request.urlopen(
            "https://ddragon.leagueoflegends.com/api/versions.json", timeout=30).read())
    except Exception:
        vers = []
    if not vers:
        try: return json.load(open(vf, encoding="utf-8"))["debut"]
        except Exception: return {}
    cur_major = vers[0].split(".")[0]
    minors = sorted({v for v in vers if v.split(".")[0] == cur_major},
                    key=lambda v: int(v.split(".")[1]))
    try:
        cached = json.load(open(vf, encoding="utf-8"))
        if cached.get("_last") == minors[-1]:
            return cached["debut"]
    except Exception:
        pass
    yy = (2010 + int(cur_major)) % 100
    prev, debut, seen_names = None, {}, set()
    # 種子：前三季各取最後版本的道具名——歷史上存在過、本季重新加入的算「重做登場」（如 26.09 貪婪護脛）
    for back in (1, 2, 3):
        pv = next((v for v in vers if v.split(".")[0] == str(int(cur_major) - back)), None)
        if not pv: continue
        try:
            d0 = json.loads(urllib.request.urlopen(
                f"https://ddragon.leagueoflegends.com/cdn/{pv}/data/zh_TW/item.json", timeout=60).read())["data"]
            seen_names |= {x["name"] for x in d0.values()}
        except Exception:
            pass
    for v in minors:
        try:
            d = json.loads(urllib.request.urlopen(
                f"https://ddragon.leagueoflegends.com/cdn/{v}/data/zh_TW/item.json", timeout=60).read())["data"]
        except Exception:
            continue
        cur = {}
        for iid, x in d.items():
            if int(iid) >= 200000: continue
            if (x.get("maps") or {}).get("11") is False: continue
            if (x.get("gold") or {}).get("purchasable") is False: continue
            cur[iid] = x   # 以 id 為鍵：改名（剔除鐮刀↔汰除品）不會被誤判成新道具
        if prev is not None:
            pk = f"{yy}.{int(v.split('.')[1]):02d}"
            for iid2 in set(cur) - set(prev):
                x = cur[iid2]; n = x["name"]
                relaunch = n in seen_names  # 本季曾出現過同名＝重做版（如 26.09 貪婪護脛換新 id）
                desc = x.get("description", "")
                sm = re.search(r"<stats>(.*?)</stats>", desc, re.S)
                stats = re.sub(r"\s+", " ", clean(sm.group(1))) if sm else ""
                eff = [clean(p) for p in re.findall(r"<passive>(.*?)</passive>|<active>(.*?)</active>", desc)
                       for p in (p if isinstance(p, str) else "".join(p),) if clean(p)]
                tag = "重做登場" if relaunch else "全新道具登場"
                lines = [f"{n}｜{tag}（總價 {x.get('gold',{}).get('total','?')} 金）"]
                if stats: lines.append(f"{n}｜屬性：{stats}")
                if eff:   lines.append(f"{n}｜效果：{'、'.join(dict.fromkeys(eff))}")
                debut.setdefault(n, {"pk": pk, "lines": lines})
        seen_names |= {x["name"] for x in cur.values()}
        prev = cur
    json.dump({"_last": minors[-1], "debut": debut}, open(vf, "w", encoding="utf-8"), ensure_ascii=False)
    return debut


def item_removals():
    """道具移除/回歸版本偵測：掃 DDragon 歷季各小版本 item.json（2014 起）。
    移除＝名稱從上一版消失且其 id 也不在新版（排除改名）；
    回歸＝名稱重新出現且過去（任何較早版本）出現過（排除全新道具）；
    首發＝名稱第一次出現且非改名（4.x 首版是基準線不算）。
    回傳 ({名: 移除pk}, {名: 回歸pk}, {名: 首發pk})；已結束的賽季永久快取，只重掃當季。"""
    vf = os.path.join(CACHE, "item_removed.json")
    def _flat(bm):
        rm_all, ret_all, new_all = {}, {}, {}
        for m in sorted(bm, key=int):
            rm_all.update(bm[m].get("rm") or {})
            ret_all.update(bm[m].get("ret") or {})
            new_all.update(bm[m].get("new") or {})
        return rm_all, ret_all, new_all
    try:
        vers = json.loads(urllib.request.urlopen(
            "https://ddragon.leagueoflegends.com/api/versions.json", timeout=30).read())
    except Exception:
        vers = []
    try:
        cached = json.load(open(vf, encoding="utf-8"))
    except Exception:
        cached = {"_last": "", "by_major": {}}
    bm0 = cached.get("by_major", {})
    # 舊快取格式（缺 new 欄位）→ 作廢重掃
    if bm0 and not all(isinstance(v, dict) and "rm" in v and "new" in v for v in bm0.values()):
        bm0 = {}
    if not vers:
        return _flat(bm0)
    cur_major = int(vers[0].split(".")[0])

    def snap(v):
        """該版本可購買道具 {id: name}（過濾規則與 item_debuts 一致）"""
        d = json.loads(urllib.request.urlopen(
            f"https://ddragon.leagueoflegends.com/cdn/{v}/data/zh_TW/item.json", timeout=60).read())["data"]
        out = {}
        for iid, x in d.items():
            if int(iid) >= 200000: continue
            if (x.get("maps") or {}).get("11") is False: continue
            if (x.get("gold") or {}).get("purchasable") is False: continue
            out[iid] = x["name"]
        return out

    by_major = bm0
    prev = None          # 上一個掃過的版本快照（跨季沿用：季末→次季首版的移除也抓）
    seen_prior = set()   # 較早賽季出現過的所有道具名（回歸判定用）
    for maj in range(4, cur_major + 1):
        # 每個 minor 取最高修訂版（4.20.1/4.20.2 只留一個）
        pool = {}
        for v in vers:
            p = v.split(".")
            if not (len(p) >= 2 and p[0].isdigit() and p[1].isdigit()): continue  # lolpatch_7.20 等舊格式
            if int(p[0]) != maj: continue
            mn = int(p[1])
            if mn not in pool or [int(x) for x in v.split(".")] > [int(x) for x in pool[mn].split(".")]:
                pool[mn] = v
        minors = [pool[mn] for mn in sorted(pool)]
        if not minors: continue
        done = str(maj) in by_major and maj < cur_major
        if done:
            seen_prior |= set(by_major[str(maj)].get("names") or [])
            # 次一季要重掃時，需要本季最後版本快照供跨季比對
            if str(maj + 1) not in by_major or maj + 1 == cur_major:
                try: prev = snap(minors[-1])
                except Exception: prev = None
            continue
        yy = (2010 + maj) % 100
        rm, ret, new, names = {}, {}, {}, set()
        for v in minors:
            try:
                cur = snap(v)
            except Exception:
                continue
            cn = set(cur.values())
            if prev is not None:
                pk = f"{yy}.{int(v.split('.')[1]):02d}"
                pn = set(prev.values())
                for iid, n in prev.items():
                    if n in cn: continue                 # 名稱還在（重做換 id）→ 沒移除
                    if iid in cur: continue              # id 還在（改名）→ 沒移除
                    rm[n] = pk                           # 之後回歸的照留：移除與回歸各自顯示
                for iid, n in cur.items():
                    if n in pn: continue                 # 上一版就有 → 不是新出現
                    if iid in prev: continue             # 改名 → 不是新出現
                    if n in seen_prior or n in names:    # 過去出現過＝回歸
                        ret[n] = pk
                    else:                                # 第一次出現＝全新道具首發
                        new.setdefault(n, pk)
            names |= cn
            prev = cur
        by_major[str(maj)] = {"rm": rm, "ret": ret, "new": new, "names": sorted(names)}
        seen_prior |= names
    json.dump({"_last": vers[0], "by_major": by_major}, open(vf, "w", encoding="utf-8"), ensure_ascii=False)
    return _flat(by_major)


def main():
    import sys
    force        = "--force"          in sys.argv
    skip_disc    = "--skip-discover"  in sys.argv
    ai_translate = "--ai-translate"   in sys.argv   # 需要 pip install anthropic
    os.makedirs(CACHE, exist_ok=True)

    # ── Step 1：從 tag 頁掃出所有真實 URL（Playwright；可跳過） ──────────────
    url_map = {}
    if not skip_disc:
        url_map = discover_urls(force=force)
        # tag 頁只有 9.1 以後；把已知 URL 反向補進 target_patches 的缺口
        # (不影響抓取邏輯，只是讓下面迴圈多一批可用 URL)

    # ── Step 2：以 url_map 決定要嘗試哪些版本 ─────────────────────────────────
    # 來源 A：原本 target_patches（2019~今年所有 minor 1-26）
    # 來源 B：tag 頁掃到的 URL（可能有 target_patches 之外的舊版，如 9.x）
    targets_from_tag = set(url_map.keys()) if url_map else set()
    targets_from_range = {f"{y%100}.{m:02d}" for y, m in target_patches()}
    all_targets = targets_from_tag | targets_from_range

    # 負快取
    miss_path = os.path.join(CACHE, "patch_missing.json")
    missing = set()
    if os.path.exists(miss_path) and not force:
        try:
            missing = set(json.load(open(miss_path, encoding="utf-8")))
        except Exception:
            pass

    all_patches = {}
    for pk in sorted(all_targets):
        cf = os.path.join(CACHE, f"patch_{pk}.json")
        # 把 pk 還原成 (year, minor)
        parts = pk.split(".")
        yy, mm = int(parts[0]), int(parts[1])
        year   = yy + (2010 if yy <= 14 else 2000)   # 19→2019, 25→2025, 26→2026
        if os.path.exists(cf) and not force:
            cached = json.load(open(cf, encoding="utf-8"))
            # 語言優先序：繁中公告 > 英文公告(字典轉譯) > Wiki。當年版本若先前只抓到英文
            # （繁中公告比英文晚上線，如 26.14），之後每次重跑都重試繁中，抓到就覆蓋快取。
            was_en = cached.get("_lang") == "en-us" or "/en-us/" in str(cached.get("_url", ""))
            if not (was_en and year == NOW_YEAR):
                all_patches[pk] = cached
                continue
            all_patches[pk] = cached   # 先保留舊(英文)內容當保底，繁中重試成功才覆蓋
            print(f"  {pk}: 快取為英文公告 → 重試繁中…")
        major  = riot_major(year)

        # 估算版本釋出日：Riot 每年 1/8 前後開始，每 14 天一版
        est = patch_est_date(year, mm)
        if est > TODAY and not force:
            continue  # 還沒發布的版本直接跳過，不加進 missing

        # 負快取：舊年份永久跳過；當年版本永遠重試（可能剛發布）
        if pk in missing and not force:
            if year < NOW_YEAR:
                continue   # 舊年份確認沒有 → 永久跳過
            # 當年版本即使曾 404 也繼續嘗試（發布後自動補抓）
            missing.discard(pk)

        html_text, url, lang = get_html(major, mm, url_map)
        if not html_text:
            if pk not in all_patches: missing.add(pk)   # 英文保底重試失敗 → 保留舊內容、不記缺
            continue
        champs = parse(html_text)
        if not champs:
            print(f"  {pk}: 頁面存在但解析 0 隻，略過")
            if pk not in all_patches: missing.add(pk)
            continue
        if lang == "en-us":
            if ai_translate:
                champs = {k: (ai_translate_champ(k, v) if isinstance(v, list) else v)
                          for k, v in champs.items()}
            else:
                champs = {k: ([translate_line(x) for x in v] if isinstance(v, list) else v)
                          for k, v in champs.items()}
        champs["_url"] = url
        champs["_lang"] = lang   # 記語言：當年版本若只抓到英文(繁中公告較晚上線)，之後每次重跑會重試繁中
        all_patches[pk] = champs
        json.dump(champs, open(cf, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"  {pk}: {len([k for k in champs if not k.startswith('_')])} 隻 ({lang}) → 快取")

    json.dump(sorted(missing), open(miss_path, "w", encoding="utf-8"), ensure_ascii=False)
    # 新道具首發資訊（官方放在賽季文章、不在 patch notes）→ 從 DDragon 差集合成，注入首發版的道具區
    for n, info in item_debuts().items():
        pd = all_patches.get(info["pk"])
        if pd is None: continue
        cat = pd.setdefault("_extra", {}).setdefault("道具", [])
        if not any(l.startswith(n + "｜全新道具") or l.startswith(n + "｜重做登場") for l in cat):
            cat[:0] = info["lines"]
    # 道具移除/回歸版本（DDragon 差集）：有官方公告的版本注入道具區；
    # 全表另存 ITEM_REMOVED / ITEM_RETURNED 給詳情頁（老年份沒官方公告也能標）
    removed, returned, debuted = item_removals()
    for n, rpk in removed.items():
        pd = all_patches.get(rpk)
        if pd is None: continue
        cat = pd.setdefault("_extra", {}).setdefault("道具", [])
        if not any(l.startswith(n + "｜已從遊戲中移除") for l in cat):
            cat[:0] = [f"{n}｜已從遊戲中移除"]
    for n, rpk in returned.items():
        pd = all_patches.get(rpk)
        if pd is None: continue
        cat = pd.setdefault("_extra", {}).setdefault("道具", [])
        # 已有首發/重做行（item_debuts 當季注入）就不重覆
        if not any(l.startswith(n + "｜") and ("登場" in l or "重返" in l) for l in cat):
            cat[:0] = [f"{n}｜重返遊戲"]
    for n, rpk in debuted.items():
        pd = all_patches.get(rpk)
        if pd is None: continue
        cat = pd.setdefault("_extra", {}).setdefault("道具", [])
        if not any(l.startswith(n + "｜") and "登場" in l for l in cat):
            cat[:0] = [f"{n}｜全新道具登場"]
    # 輸出前全部重過一次翻譯：詞庫擴充後，舊快取裡的英文殘留也會被修正（中文行不受影響）
    for pk, pd in all_patches.items():
        for k, v in list(pd.items()):
            if k == "_url":
                continue
            if k == "_extra":
                for cat, ls in v.items():
                    v[cat] = [translate_line(l) for l in ls]
            elif isinstance(v, list):
                pd[k] = [translate_line(l) for l in v]
    js = json.dumps(all_patches, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(HERE, "patches.js"), "w", encoding="utf-8") as f:
        f.write("window.LOL_PATCHES=" + js + ";")
        f.write("window.ITEM_REMOVED=" + json.dumps(removed, ensure_ascii=False, separators=(",", ":")) + ";")
        try:   # 逐 major 的移除版本表（圖鑑逐年顯示精確移除版本用；扁平表跨年會互蓋）
            _bm = json.load(open(os.path.join(CACHE, "item_removed.json"), encoding="utf-8")).get("by_major", {})
            _rm_by = {m: (v.get("rm") or {}) for m, v in _bm.items()}
        except Exception:
            _rm_by = {}
        f.write("window.ITEM_REMOVED_BY=" + json.dumps(_rm_by, ensure_ascii=False, separators=(",", ":")) + ";")
        f.write("window.ITEM_RETURNED=" + json.dumps(returned, ensure_ascii=False, separators=(",", ":")) + ";")
        f.write("window.ITEM_DEBUT=" + json.dumps(debuted, ensure_ascii=False, separators=(",", ":")) + ";")
    print(f"完成：{len(all_patches)} 個版本 → patches.js "
          f"({os.path.getsize(os.path.join(HERE,'patches.js'))//1024} KB)")


if __name__ == "__main__":
    main()
