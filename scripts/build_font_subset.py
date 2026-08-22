# -*- coding: utf-8 -*-
"""產生 jf-openhuninn 的子集字型與對應的 @font-face CSS（2026-08-22 效能改善）。

為什麼：內文字型 jf-openhuninn.woff2 是 **2.18MB**，砍完年度資料欄位之後它變成全站最大的單一資產。
字型裡有 11988 個字，但整個專案實際會顯示到的只有 5800 多個 → 子集 1.12MB。

**關鍵：光把子集排在 font-family 第一位擋不住完整字型被下載。**
2026-08-22 實測：即使把堆疊改成「只有子集」、畫面像素完全相同，瀏覽器照樣把 2.18MB 的完整版抓下來
（CDP 顯示是 CSS parser 發的請求），字型流量從 2.18MB 變成 3.30MB，比不做還糟。
瀏覽器真正用來決定「這個 face 要不要下載」的是 **unicode-range**：
  - 子集 face：帶明確的 unicode-range（只涵蓋我們收進去的碼位）
  - 完整 face：不帶 unicode-range（＝補漏，只有碰到範圍外的字才會被下載）
兩個 face **同一個 family 名**，所以 CSS 的字型堆疊完全不用改，寫 "jf-openhuninn" 一種就好。
⚠ 兩個 face 的 ascent/descent-override 必須一模一樣，否則兩種字混排時行高會跳。

字元來源要涵蓋所有「會被顯示出來」的文字：index.html 的字面值、根目錄各資料 JS（版本改動、技能、
道具、wiki…）、以及 data/data_*.js（隊名／選手名）；另外把「執行時才生出來、靜態掃不到」的空白與
標點整區收進來（少一個 U+00A0 就會害完整字型被下載——實測踩過）。
掛在 update.bat 每天重跑，新版本帶進來的新字隔天就會被收進去。

用法：python scripts/build_font_subset.py
輸出：fonts/jf-openhuninn-sub.woff2、fonts/huninn.css（index.html 用 <link> 引它）
"""
import glob, io, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SRC = os.path.join(ROOT, "fonts", "jf-openhuninn.woff2")
DST = os.path.join(ROOT, "fonts", "jf-openhuninn-sub.woff2")
CSS = os.path.join(ROOT, "fonts", "huninn.css")
OVERRIDE = "ascent-override:106.7%;descent-override:26.7%;line-gap-override:0%"


def used_chars():
    chars = set()
    pats = [os.path.join(ROOT, "index.html")] + \
           sorted(glob.glob(os.path.join(ROOT, "*.js"))) + \
           sorted(glob.glob(os.path.join(ROOT, "data", "data_*.js")))
    for p in pats:
        try:
            chars |= set(io.open(p, encoding="utf-8", errors="replace").read())
        except Exception:
            pass
    # 「執行時才生出來、靜態掃不到」的整區收進來。成本很低（這些區塊字很少），
    # 但少一個就會害完整字型被下載——2026-08-22 實測漏了 U+00A0（hiNum() 補半形空格時產生）。
    for a, b in ((0x20, 0x7F),        # ASCII（搜尋框輸入、數字）
                 (0xA0, 0x100),       # Latin-1 補充（U+00A0 不斷行空白、度、正負、乘除號）
                 (0x2000, 0x2070),    # 一般標點（各種空白、零寬、破折號、引號、刪節號）
                 (0x2190, 0x21FF),    # 箭頭
                 (0x2460, 0x24FF),    # 帶圈數字
                 (0x25A0, 0x26FF),    # 幾何圖形／雜項符號
                 (0x3000, 0x3040),    # CJK 標點（含全形空白）
                 (0xFE30, 0xFE50),    # CJK 相容標點
                 (0xFF00, 0xFFF0)):   # 全形英數與標點
        chars |= {chr(c) for c in range(a, b)}
    return chars


def ranges_css(cps):
    """把碼位壓成連續區段（CSS unicode-range 語法）"""
    out, s0, prev = [], None, None
    for c in list(cps) + [None]:
        if prev is not None and c is not None and c == prev + 1:
            prev = c
            continue
        if s0 is not None:
            out.append("U+%04X" % s0 if s0 == prev else "U+%04X-%04X" % (s0, prev))
        s0 = prev = c
    return out


def main():
    if not os.path.exists(SRC):
        sys.exit("[X] 找不到 " + SRC)
    from fontTools.ttLib import TTFont
    cmap = set(TTFont(SRC).getBestCmap().keys())
    need = sorted({ord(c) for c in used_chars()} & cmap)
    print("字型 %d 字；專案用到 %d（%d%%）" % (len(cmap), len(need), len(need) / len(cmap) * 100))

    # 用 API 不用命令列：幾千個碼位串成 --unicodes= 會超過 Windows 的命令列長度上限
    from fontTools import subset as ss
    opt = ss.Options()
    opt.flavor = "woff2"
    opt.layout_features = ["*"]
    opt.hinting = False
    opt.desubroutinize = True
    fnt = ss.load_font(SRC, opt)
    sub = ss.Subsetter(options=opt)
    sub.populate(unicodes=need)
    sub.subset(fnt)
    ss.save_font(fnt, DST, opt)
    if not os.path.exists(DST):
        sys.exit("[X] 子集化失敗")

    rngs = ranges_css(need)
    line1 = ('@font-face{font-family:"jf-openhuninn";src:url("jf-openhuninn-sub.woff2") format("woff2");'
             "font-display:swap;" + OVERRIDE + ";unicode-range:" + ",".join(rngs) + "}")
    # 完整 face 也要標 unicode-range——只標它「真正有的字」（全字型 cmap 減掉子集）。
    # 不標的話它等於宣稱涵蓋 U+0-10FFFF，於是畫面上的 emoji（首殺/首塔那排、ℹ️、↺…）
    # 也會讓瀏覽器把 2.18MB 抓下來「看看有沒有這個字」——2026-08-22 就是卡在這裡，
    # 排在後面、順序也對了，還是照抓。標上之後 emoji 直接掉到系統表情字型，完整版不會被碰。
    rest = ranges_css(sorted(cmap - set(need)))
    line2 = ('@font-face{font-family:"jf-openhuninn";src:url("jf-openhuninn.woff2") format("woff2"),'
             'url("jf-openhuninn.ttf") format("truetype");font-display:swap;' + OVERRIDE +
             ";unicode-range:" + ",".join(rest) + "}")
    # ⚠ 順序有意義：同一個 family 有多個 face 時，**後宣告的優先**。
    # 完整版寫前面、子集寫後面，子集才會在自己的 unicode-range 內勝出；
    # 反過來寫的話完整版（沒有 range＝涵蓋全部）會把子集整個蓋掉，等於白做（2026-08-22 踩過）。
    body = "/* 這個檔案是 scripts/build_font_subset.py 產生的，不要手改 */" + chr(10) + line2 + chr(10) + line1 + chr(10)
    io.open(CSS, "w", encoding="utf-8", newline=chr(10)).write(body)
    a, b = os.path.getsize(SRC), os.path.getsize(DST)
    print("%s %.2fMB -> %s %.2fMB（省 %d%%）" % (os.path.basename(SRC), a / 1e6,
                                                os.path.basename(DST), b / 1e6, (1 - b / a) * 100))
    print("fonts/huninn.css：%d 段 unicode-range，%.1f KB" % (len(rngs), os.path.getsize(CSS) / 1024))


if __name__ == "__main__":
    main()
