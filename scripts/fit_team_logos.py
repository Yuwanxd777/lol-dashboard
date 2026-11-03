# -*- coding: utf-8 -*-
"""隊徽視覺大小統一（使用者 2026-11-04：「有些隊徽視覺上特別小」「例如 PSG Talon」）

前端把隊徽放進 size×size 的正方形框（object-fit:contain），圖檔本身不是正方形或四周留一大圈透明邊，
畫出來就會縮成一小塊：dpm 有一批是 60×25 的扁圖（PSG 的盾牌只佔中間 33×25 ⇒ 22px 框裡剩 9px 高），
Leaguepedia 的 square 圖也有一成左右四周留白 10～20%。

  ① 裁透明邊：alpha > 24 的外框（半透明陰影不算）
  ② 補成正方形：短邊兩側補透明，四周留 4% 呼吸空間，縮到最長 128px（原圖 3335px 的 GEN 一起瘦身）
  ③ --refetch：60×25 這種低解析扁圖 → 先去 Leaguepedia 換「{隊名}logo square.png」再做 ①②
     （要開無頭頁面算縮寫＋連網，只手動跑；管線 ④ 後處理只跑 ①②，純本機、已正規化的檔直接跳過）

冪等：已經是正方形且內容佔滿（≥ 90%）的檔不重寫。
用法：  python scripts\\fit_team_logos.py [--refetch] [--dry]
"""
import io, json, os, sys

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "img", "teams")
PX = 128
PAD = 0.04
LOWRES = 100     # 最長邊小於這個＝低解析（dpm 的 60×25），--refetch 會去 wiki 換


def fit(im):
    """RGBA 圖 → 裁透明邊＋補成正方形；回傳 (新圖, 是否有變)"""
    im = im.convert("RGBA")
    bb = im.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
    if not bb:
        return im, False
    W, H = im.size
    bw, bh = bb[2] - bb[0], bb[3] - bb[1]
    if W == H and max(bw, bh) / W >= 0.90 and W <= PX:
        return im, False
    from PIL import Image
    c = im.crop(bb)
    side = round(max(bw, bh) * (1 + 2 * PAD))
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(c, ((side - bw) // 2, (side - bh) // 2))
    if side > PX:
        sq = sq.resize((PX, PX), Image.LANCZOS)
    return sq, True


def refetch(files, dry):
    """低解析檔 → Leaguepedia square 原圖（隊名用跟 fetch_team_logos_wiki 一樣的主人規則）"""
    sys.path.insert(0, HERE)
    import fetch_team_logos_wiki as W
    import urllib.request
    info = W.all_names()
    ab = W.abbrs(sorted(info))
    alias = json.load(open(W.ALIAS, encoding="utf-8")) if os.path.exists(W.ALIAS) else {}
    grp = {}
    for n, a in ab.items():
        if a:
            grp.setdefault(a, []).append(n)
    owner = {a: max(ns, key=lambda n: info[n]) for a, ns in grp.items()}
    rev = {v: k for k, v in alias.items() if v != "-"}
    name = {}
    for f in files:
        k = f[:-5]
        n = rev.get(k) or owner.get(k)
        if n:
            name[k] = n
        else:
            print("   找不到隊名：", k)
    got = W.lookup(sorted(set(name.values())))
    ok = 0
    for k, n in sorted(name.items()):
        u = got.get(n)
        if not u or "logo_std" in u or "logostd" in u.replace(" ", "").lower():
            print(f"   {k}（{n}）wiki 沒有 square 圖，只做裁切")
            continue
        print(f"   {k} ← {n}")
        if dry:
            continue
        try:
            from PIL import Image
            d = urllib.request.urlopen(urllib.request.Request(u, headers=W.UA), timeout=30).read()
            im = Image.open(io.BytesIO(d)).convert("RGBA")
            if max(im.size) > PX:
                im.thumbnail((PX, PX), Image.LANCZOS)
            im.save(os.path.join(OUT, k + ".webp"), "WEBP", quality=90, method=6)
            ok += 1
        except Exception as e:
            print(f"   {k} 下載失敗：{str(e)[:80]}")
    print(f"低解析換 wiki 圖：{ok}／{len(files)}")


def main():
    dry = "--dry" in sys.argv
    from PIL import Image
    fs = sorted(f for f in os.listdir(OUT) if f.endswith(".webp"))
    if "--refetch" in sys.argv:
        low = [f for f in fs if max(Image.open(os.path.join(OUT, f)).size) < LOWRES]
        print(f"低解析 {len(low)} 個")
        if low:
            refetch(low, dry)
    n = 0
    for f in fs:
        p = os.path.join(OUT, f)
        im, ch = fit(Image.open(p))
        if not ch:
            continue
        n += 1
        if dry:
            print("   要調", f)
        else:
            im.save(p, "WEBP", quality=90, method=6)
    print(f"隊徽正規化（裁透明邊＋補正方形）：{n}／{len(fs)} 個{'（dry）' if dry else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
