# -*- coding: utf-8 -*-
"""fetch_player_ids.py 的判定邏輯回歸測試（精進迴圈 #43）。

守的是什麼：這支腳本產生 `scripts/player_disambig.json`，build_career.py 靠它把
「同 ID 其實是不同人」的場次分給正確的人。判錯的代價很實在——
主人格挑錯，career.p[原名] 就不存在，前端查那個選手直接變 0 場（比不拆還糟）。
2026-09-07 新增的 `persons_add`（人工補「LP 有選手頁但 ScoreboardPlayers 一場都沒有」
的人格，例：2013 GPL 的 Demon）當時只有真實資料前後對照，沒有任何自動測試。

怎麼測：判定邏輯已抽成純函式 `personas()`／`build_entry()`（不連網、不讀寫檔、不印字），
直接餵合成列表。**每條斷言都有正控制**——把輸入改成「應該得到相反結果」的那一組，
確認測試真的會翻面，避免恆綠。最後一組用真實快取
（csv_cache/lpedia_players/Demon.json ＋ 真的 player_disambig.json）跑一次端到端。

用法：python scripts/fetch_player_ids_test.py
"""
import collections, io, json, os, sys

if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import fetch_player_ids as F          # noqa: E402

fails = []


def chk(name, cond, note=""):
    print(("  ✓ " if cond else "  ✗ ") + name + (f"　（{note}）" if note else ""))
    if not cond:
        fails.append(name)


def row(nm, lk, tm, n, f, l):
    """一列 export() 的結果"""
    return {"nm": nm, "lk": lk, "tm": tm, "n": n, "f": f + " 00:00:00", "l": l + " 00:00:00"}


def main():
    # ① persons_add：LP 只查得到一位，人工補的那位要讓它變成「拆分」
    print("① persons_add 會把單人變成拆分")
    rows = [row("Demon", "Demon (Wu Yue-Wei)", "Team WE", 12, "2014-01-01", "2022-08-14")]
    manual = {"persons_add": [{"link": "Demon (Tsai Tung-Jung)",
                               "teams": ["e-Sports Dragons Pro"],
                               "games_lp": 0, "first": "2013-04-19", "last": "2013-07-07",
                               "note": "LP 只有名單沒逐場"}]}
    oe = collections.Counter({"E-Sports Dragons Pro": 29, "Team WE": 6})
    ent, st, links, notes = F.build_entry("Demon", rows, manual, oe)
    chk("有 persons_add ⇒ 拆成 2 人", st == "拆成 2 人", st)
    chk("有印出「人工補人格」說明行", any("人工補人格" in s for s in notes), "；".join(notes) or "無")
    # 正控制：拿掉 persons_add，同一份 rows 必須變回「同一人」
    ent0, st0, _, notes0 = F.build_entry("Demon", rows, {}, oe)
    chk("正控制：沒有 persons_add ⇒ 同一人（誤報）", st0 == "同一人", st0)
    chk("正控制：沒有 persons_add 就不印說明行", notes0 == [], str(notes0))

    # ② 主人格＝OE 場次多的那位（不是 LP 場次多的）
    print("② 主人格挑 OE 出賽多的那位，key 沿用原名")
    chk("主人格是人工補的那位（OE 29 場）", ent["persons"][0]["link"] == "Demon (Tsai Tung-Jung)",
        ent["persons"][0]["link"])
    chk("主人格 key＝原名 Demon", ent["persons"][0]["key"] == "Demon", ent["persons"][0]["key"])
    chk("次人格 key＝選手頁", ent["persons"][1]["key"] == "Demon (Wu Yue-Wei)", ent["persons"][1]["key"])
    chk("人工那位 games_oe=29／games_lp=0",
        ent["persons"][0]["games_oe"] == 29 and ent["persons"][0]["games_lp"] == 0,
        f"oe {ent['persons'][0]['games_oe']}／lp {ent['persons'][0]['games_lp']}")
    chk("人工那位標了 manual 註記", ent["persons"][0].get("manual") == "LP 只有名單沒逐場",
        str(ent["persons"][0].get("manual")))
    # 正控制：把 OE 場次反過來 ⇒ 主人格必須換人
    ent2, _, _, _ = F.build_entry("Demon", rows, manual,
                                  collections.Counter({"E-Sports Dragons Pro": 1, "Team WE": 30}))
    chk("正控制：OE 場次對調 ⇒ 主人格換成 LP 那位",
        ent2["persons"][0]["link"] == "Demon (Wu Yue-Wei)", ent2["persons"][0]["link"])
    # persons_add 沒填 note ⇒ 用預設字串
    m2 = {"persons_add": [dict(manual["persons_add"][0])]}
    m2["persons_add"][0].pop("note")
    ent3, _, _, _ = F.build_entry("Demon", rows, m2, oe)
    chk("persons_add 沒填 note ⇒ 有預設註記",
        ent3["persons"][0].get("manual") == "人工補（LP 有頁但無逐場）", str(ent3["persons"][0].get("manual")))

    # ③ persons_add 只補不覆寫：link 已經在 LP 查到就跳過
    print("③ persons_add 不覆寫 LP 查到的人格")
    dup = {"persons_add": [{"link": "Demon (Wu Yue-Wei)", "games_lp": 999, "teams": ["假隊"]}]}
    per, notes3 = F.personas("Demon", rows, dup)
    chk("重複的 link 不再新增一份", len(per) == 1, f"{len(per)} 個人格")
    chk("LP 的場次沒被人工數字蓋掉", per["Demon (Wu Yue-Wei)"]["n"] == 12, str(per["Demon (Wu Yue-Wei)"]["n"]))
    chk("跳過就不印說明行", notes3 == [], str(notes3))
    # 正控制：換一個沒查到的 link ⇒ 必須真的補進去
    per2, notes4 = F.personas("Demon", rows, {"persons_add": [{"link": "Demon (Someone Else)"}]})
    chk("正控制：沒查到的 link 會補進來", len(per2) == 2 and notes4, f"{len(per2)} 個人格")
    chk("沒填 games_lp ⇒ 場次算 0", per2["Demon (Someone Else)"]["n"] == 0, str(per2["Demon (Someone Else)"]["n"]))

    # ④ 查無（LP 一列都沒有）不套 persons_add，也不動舊條目
    print("④ 查無時不套 persons_add（LP 整個查不到多半是網路或名字寫法出問題）")
    entN, stN, linksN, notesN = F.build_entry("Demon", [], manual, oe)
    chk("rows 空 ⇒ status 查無", stN == "查無", stN)
    chk("rows 空 ⇒ 不回傳條目（呼叫端才不會覆寫舊表）", entN is None, str(entN))
    chk("rows 空 ⇒ 沒有 links／notes", linksN == [] and notesN == [], f"{linksN}／{notesN}")

    # ⑤ 改名重導頁要併成一個人（Raven 的真實案例）
    print("⑤ 改名重導頁合併（隊伍集合相同＋link 互為前綴）")
    rr = [row("Raven", "Raven (Kenneth Goh)", "Ascension Gaming", 30, "2017-01-01", "2018-01-01"),
          row("Raven", "Raven (Kenneth Goh Kai Yang)", "Ascension Gaming", 88, "2018-02-01", "2020-01-01")]
    perR, notesR = F.personas("Raven", rr, {})
    chk("兩個頁面併成一位", len(perR) == 1, f"{len(perR)} 個人格")
    chk("有印出「合併重導頁」說明行", any("合併重導頁" in s for s in notesR), "；".join(notesR) or "無")
    chk("併完取兩邊的場次上限與首末日期",
        perR["Raven (Kenneth Goh Kai Yang)"]["n"] == 88
        and perR["Raven (Kenneth Goh Kai Yang)"]["f"] == "2017-01-01"
        and perR["Raven (Kenneth Goh Kai Yang)"]["l"] == "2020-01-01",
        str(perR["Raven (Kenneth Goh Kai Yang)"]))
    # 正控制：隊伍集合不同 ⇒ 不准併（那是兩個真的不同的人）
    rr2 = [row("Raven", "Raven (Kenneth Goh)", "Ascension Gaming", 30, "2017-01-01", "2018-01-01"),
           row("Raven", "Raven (Kenneth Goh Kai Yang)", "Bilibili Gaming", 88, "2018-02-01", "2020-01-01")]
    perR2, _ = F.personas("Raven", rr2, {})
    chk("正控制：隊伍集合不同就不併", len(perR2) == 2, f"{len(perR2)} 個人格")

    # ⑥ _未對應隊伍：OE 有、LP 任何人格都沒列到的隊伍要列出來給人工看
    print("⑥ _未對應隊伍與 teams_add")
    rw = [row("Uzi", "Uzi (Jian Zi-Hao)", "Royal Never Give Up", 300, "2013-01-01", "2020-01-01"),
          row("Uzi", "Uzi (Lê Thanh Hà)", "GAM Esports", 20, "2021-01-01", "2022-01-01")]
    oeU = collections.Counter({"Royal Never Give Up": 300, "GAM Esports": 20, "Topsports Gaming": 40})
    entU, stU, _, _ = F.build_entry("Uzi", rw, {}, oeU)
    chk("對不上的隊伍被列進 _未對應隊伍",
        entU.get("_未對應隊伍") == {"Topsports Gaming": 40}, str(entU.get("_未對應隊伍")))
    # 正控制：用 teams_add 補上對照 ⇒ 該欄必須消失，而且場次要算進那位人格
    entU2, _, _, _ = F.build_entry("Uzi", rw, {"teams_add": {"Uzi (Jian Zi-Hao)": ["Topsports Gaming"]}}, oeU)
    chk("正控制：teams_add 補上後 _未對應隊伍 消失", "_未對應隊伍" not in entU2, str(entU2.get("_未對應隊伍")))
    chk("正控制：teams_add 的場次算進該人格 games_oe（300+40）",
        entU2["persons"][0]["games_oe"] == 340, str(entU2["persons"][0]["games_oe"]))
    chk("teams_add 會記進 teams_oe_manual",
        entU2["persons"][0].get("teams_oe_manual") == ["Topsports Gaming"],
        str(entU2["persons"][0].get("teams_oe_manual")))
    # 舊表裡殘留的 _未對應隊伍，這次對得上就要清掉（不然會一直留著誤導人）
    entU3, _, _, _ = F.build_entry("Uzi", rw, {"teams_add": {"Uzi (Jian Zi-Hao)": ["Topsports Gaming"]},
                                               "_未對應隊伍": {"舊的": 1}}, oeU)
    chk("舊的 _未對應隊伍 會被清掉", "_未對應隊伍" not in entU3, str(entU3.get("_未對應隊伍")))

    # ⑦ 人工欄位的保留與清除規則
    print("⑦ 拆分／同一人兩種結果對既有欄位的處理")
    prev = {"persons_add": manual["persons_add"], "teams_add": {"x": ["y"]},
            "reviewed": "上次判定是同一人", "note": "人工註記"}
    entK, _, _, _ = F.build_entry("Demon", rows, prev, oe)
    chk("拆分時 reviewed 要移除（不然 check_player_dup 會繼續靜音）", "reviewed" not in entK, str(entK.get("reviewed")))
    chk("拆分時 persons_add／teams_add／人工註記全部保留",
        entK.get("persons_add") and entK.get("teams_add") and entK.get("note") == "人工註記")
    chk("拆分時標記來源 leaguepedia", entK.get("source") == "leaguepedia", str(entK.get("source")))
    entS, stS, _, _ = F.build_entry("Demon", rows, {"persons": [{"key": "舊的"}], "note": "人工註記"}, oe)
    chk("同一人時 persons 要移除", stS == "同一人" and "persons" not in entS, stS)
    chk("同一人時寫入 reviewed 與 link",
        "Leaguepedia 只有一位" in entS.get("reviewed", "") and entS.get("link") == "Demon (Wu Yue-Wei)",
        entS.get("reviewed", ""))
    chk("同一人時人工註記保留", entS.get("note") == "人工註記", str(entS.get("note")))

    # ⑧ 真實素材端到端：用快取的 Demon 查詢結果 ＋ 真的 player_disambig.json
    print("⑧ 真實素材（csv_cache/lpedia_players/Demon.json ＋ player_disambig.json）")
    cp = os.path.join(ROOT, "csv_cache", "lpedia_players", "Demon.json")
    dj = os.path.join(HERE, "player_disambig.json")
    if os.path.exists(cp) and os.path.exists(dj):
        real_rows = json.load(open(cp, encoding="utf-8"))
        real_prev = json.load(open(dj, encoding="utf-8")).get("Demon") or {}
        dup_path = os.path.join(ROOT, "csv_cache", "player_dup.json")
        oc = collections.Counter()
        if os.path.exists(dup_path):
            for r in json.load(open(dup_path, encoding="utf-8"))["rows"]:
                if r["name"] == "Demon":
                    for s in r["segs"]:
                        oc[s["tm"]] += s["n"]
        entR, stR, linksR, _ = F.build_entry("Demon", real_rows, real_prev, oc)
        chk("真實 Demon 拆成 4 人", stR == "拆成 4 人", stR)
        chk("主人格是 2013 GPL 那位（人工補的）",
            entR["persons"][0]["link"] == "Demon (Tsai Tung-Jung)", entR["persons"][0]["link"])
        chk("沒有 _未對應隊伍", "_未對應隊伍" not in entR, str(entR.get("_未對應隊伍")))
        chk("四個人格的 link 互不重複", len(set(linksR)) == 4, "｜".join(linksR))
    else:
        chk("真實素材存在（快取被清掉就跳過這組）", False, "找不到 Demon 快取或 player_disambig.json")

    print("\n全部通過 ✓" if not fails else "\n失敗 " + str(len(fails)) + " 條：" + "、".join(fails))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
