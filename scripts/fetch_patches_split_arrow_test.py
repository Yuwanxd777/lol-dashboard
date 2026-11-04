# -*- coding: utf-8 -*-
"""fetch_patches._champ_blocks：官方把一條改動拆成兩個 <li>（「舊值」＋「⇒ 新值」）時要併回一行（精進迴圈 #2549）。
素材片段照抄 26.22 官方頁的札亨段（繁中／英文結構相同）。純函式、不碰檔案也不連網。"""
import io, os, sys

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_patches as fp  # noqa: E402

IMG = '<img src="https://x/cdn/16.22.1/img/champion/Zaahen.png"/>'
fails = 0


def blk(body):
    return fp._champ_blocks(IMG + body).get("Zaahen") or []


def check(name, got, want):
    global fails
    ok = got == want
    fails += not ok
    print(("✓" if ok else "✗"), name, "" if ok else f"\n   實得 {got}\n   應為 {want}")


SPLIT = '<h4>冥血大刀（Q）</h4><ul><li><strong>冷卻時間</strong>：10 / 9 / 8 / 7 / 6秒</li><li style="list-style:none;">⇒ <strong>8 / 7.5 / 7 / 6.5 / 6秒</strong></li></ul>'
check("① 拆成兩個 li ⇒ 併回一行", blk(SPLIT), ["冥血大刀（Q）｜冷卻時間：10 / 9 / 8 / 7 / 6秒 ⇒ 8 / 7.5 / 7 / 6.5 / 6秒"])

# 正控制：這些都不可以被併
NORMAL = '<h4>冥血大刀（Q）</h4><ul><li>冷卻時間：10 ⇒ 8</li><li>傷害：5 ⇒ 6</li></ul>'
check("② 正常兩行不動", blk(NORMAL), ["冥血大刀（Q）｜冷卻時間：10 ⇒ 8", "冥血大刀（Q）｜傷害：5 ⇒ 6"])
HAS = '<h4>冥血大刀（Q）</h4><ul><li>冷卻時間：10 ⇒ 8</li><li>⇒ 7</li></ul>'
check("③ 前一行已有 ⇒ 不併", blk(HAS), ["冥血大刀（Q）｜冷卻時間：10 ⇒ 8", "冥血大刀（Q）｜⇒ 7"])
CROSS = '<h4>冥血大刀（Q）</h4><ul><li>冷卻時間：10</li></ul><h4>別招（W）</h4><ul><li>⇒ 7</li></ul>'
check("④ 跨技能標題不併", blk(CROSS), ["冥血大刀（Q）｜冷卻時間：10", "別招（W）｜⇒ 7"])
TWO = '<h4>冥血大刀（Q）</h4><ul><li>冷卻時間：10</li><li>⇒ 8</li><li>傷害：5</li><li>⇒ 6</li></ul>'
check("⑤ 連續兩組各自併", blk(TWO), ["冥血大刀（Q）｜冷卻時間：10 ⇒ 8", "冥血大刀（Q）｜傷害：5 ⇒ 6"])

print(f"失敗 {fails}")
sys.exit(1 if fails else 0)
