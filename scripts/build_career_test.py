# -*- coding: utf-8 -*-
"""build_career.py 的決定性回歸測試（精進迴圈 #40）。

守的是什麼：career.js 12.2 MB、每天 10:00／22:00 都重建一次。只要輸出不是決定性的，
沒有新比賽的日子 git 也得整份重存。2026-09-07 的根因是逐場對手 ban 那個迴圈用了
`set(...)` —— 它的迭代順序跟著字串 hash（PYTHONHASHSEED 每次執行都不同）走，
決定了英雄字典 chI 的插入順序，而字典順序決定逐場列 g 裡每一個 base36 索引 ⇒ 整份不一樣。

怎麼測（不碰真的 data/ 與 career.js）：用 CAREER_ROOT 指到臨時目錄、放小型合成資料，
用三個不同的 PYTHONHASHSEED 各跑一次，比 career.js 的 md5。
**每條斷言都有正控制**：同時把原始碼裡的 `dict.fromkeys(` 換回 `set(`，
確認那個變體在同一份測試資料下真的會產生不同的 md5 —— 否則就是測試資料太單薄、
這支測試永遠綠燈也抓不到回歸。

用法：python scripts/build_career_test.py
"""
import hashlib, io, json, os, re, shutil, subprocess, sys, tempfile

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "build_career.py")
SEEDS = ("1", "12345", "98765")

# 欄位順序要讓 red_* 相對 blue_* 的偏移一致（build_career 用 RB = red_champion - blue_champion）
HDR = ["participantid", "date", "result", "patch",
       "blue_teamname", "blue_playername", "blue_champion", "blue_banlist",
       "red_teamname", "red_playername", "red_champion", "red_banlist"]
POSN = {1: "TOP", 2: "JNG", 3: "MID", 4: "BOT", 5: "SUP"}
CH = ["Aatrox", "Ahri", "Akali", "Alistar", "Amumu", "Anivia", "Annie", "Ashe",
      "Bard", "Blitzcrank", "Brand", "Braum", "Caitlyn", "Camille", "Cassiopeia",
      "Corki", "Darius", "Diana", "Draven", "Ekko", "Elise", "Evelynn", "Ezreal",
      "Fiora", "Fizz", "Galio", "Gangplank", "Garen", "Gnar", "Gragas"]


def make_rows(year, ngame):
    """合成一年的資料：每場 5 列（一路一列，含藍紅兩方），每方 ban 5 隻不同英雄。

    ban 名單刻意每場都換一組英雄、且藍紅不同 —— 這樣「第一次見到某隻英雄」的時機
    才會落在 ban 迴圈裡，set() 的迭代順序才真的會改變英雄字典。
    """
    rows = [list(HDR)]
    for g in range(ngame):
        day = f"{year}-{(g % 12) + 1:02d}-{(g % 27) + 1:02d}"
        patch = f"{year[2:]}.{(g % 20) + 1:02d}"
        res = 1 if g % 2 == 0 else 2
        bb = [CH[(g * 7 + i) % len(CH)] for i in range(5)]
        rb = [CH[(g * 11 + i + 3) % len(CH)] for i in range(5)]
        for p in POSN:
            bc = CH[(g * 3 + p) % len(CH)]
            rc = CH[(g * 5 + p + 1) % len(CH)]
            rows.append([p, day, res, patch,
                         f"Blue{g % 4}", f"BP{p}_{g % 6}", bc, "|".join(bb),
                         f"Red{g % 3}", f"RP{p}_{g % 5}", rc, "|".join(rb)])
    return rows


def build_fixture(root):
    os.makedirs(os.path.join(root, "data"), exist_ok=True)
    for year, n in (("2013", 40), ("2014", 60), ("2015", 50)):
        j = {"tabs": {"RAW_DATA": make_rows(year, n)}}
        with open(os.path.join(root, "data", f"data_{year}.js"), "w", encoding="utf-8") as f:
            f.write("window.LOL_DATA=" + json.dumps(j, ensure_ascii=False) + ";\n")


def run_build(script, root, seed):
    env = dict(os.environ, CAREER_ROOT=root, PYTHONHASHSEED=seed, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, script], env=env, cwd=root,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = os.path.join(root, "career.js")
    if r.returncode != 0 or not os.path.exists(out):
        raise AssertionError(f"build 失敗 (exit {r.returncode})：\n"
                             + r.stdout.decode("utf-8", "replace")[-2000:])
    return hashlib.md5(open(out, "rb").read()).hexdigest()


def md5s(script, root):
    got = []
    for s in SEEDS:
        got.append(run_build(script, root, s))
        os.remove(os.path.join(root, "career.js"))
    return got


def main():
    fails = []

    def chk(name, ok, detail=""):
        print(("  ✓ " if ok else "  ✗ ") + name + (("　" + detail) if detail else ""))
        if not ok:
            fails.append(name)

    tmp = tempfile.mkdtemp(prefix="career_det_")
    try:
        build_fixture(tmp)

        # ① 現行版本：三個 hash seed 的輸出要 byte-identical
        h = md5s(SRC, tmp)
        chk("現行 build_career.py 三種 PYTHONHASHSEED 輸出相同",
            len(set(h)) == 1, h[0][:12] + f"（{len(set(h))} 種）")

        # ② 正控制：把 dict.fromkeys 換回 set，同一份資料就該出現不同的 md5。
        #    這條若「也相同」＝測試資料太單薄，①的綠燈沒有意義。
        src = open(SRC, encoding="utf-8").read()
        bad_src = src.replace("dict.fromkeys(str(r[col]).split(", "set(str(r[col]).split(")
        chk("正控制原始碼替換成功（找得到那行 dict.fromkeys）", bad_src != src)
        bad = os.path.join(tmp, "build_career_setver.py")
        with open(bad, "w", encoding="utf-8") as f:
            f.write(bad_src)
        hb = md5s(bad, tmp)
        chk("正控制：改回 set() 後三種 seed 輸出不同（＝這份資料抓得到非決定性）",
            len(set(hb)) > 1, f"{len(set(hb))} 種")

        # ③ 決定性以外，語意也不能被②那種改動影響：兩版的「場次總和／選手數」要一樣
        run_build(SRC, tmp, "1")
        a = json.loads(open(os.path.join(tmp, "career.js"), encoding="utf-8")
                       .read().split("=", 1)[1].strip().rstrip(";"))
        os.remove(os.path.join(tmp, "career.js"))
        run_build(bad, tmp, "1")
        b = json.loads(open(os.path.join(tmp, "career.js"), encoding="utf-8")
                       .read().split("=", 1)[1].strip().rstrip(";"))
        sa = sum(v["n"] for v in a["p"].values())
        sb = sum(v["n"] for v in b["p"].values())
        chk("保序去重不改變語意：選手數與場次總和與 set() 版相同",
            len(a["p"]) == len(b["p"]) and sa == sb, f"{len(a['p'])} 人 / {sa} 場")
        chk("英雄字典兩版內容相同（只有順序差）", set(a["ch"]) == set(b["ch"]),
            f"{len(a['ch'])} 隻")

        # ④ 合成資料本身要夠有代表性：ban 迴圈真的建了英雄字典的一部分
        chk("測試資料有效：逐場列與英雄字典非空", len(a["ch"]) > 5 and any(v.get("g") for v in a["p"].values()),
            f"ch {len(a['ch'])}｜選手 {len(a['p'])}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(("\n全部通過 ✓" if not fails else "\n失敗 " + str(len(fails)) + " 條：" + "、".join(fails)))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
