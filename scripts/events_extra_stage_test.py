# -*- coding: utf-8 -*-
"""fetch_events_extra.cargo_stages 守門：世界賽入圍賽／正賽的日期與隊伍（使用者 2026-10-17）。

前端靠 events_extra.js 的 WLDs.stages：Play-In 起訖日內的 WLDs 局標「入圍賽」（比賽BP 會顯示），
賽事卡的正賽段用 Main Event 名單補齊還沒出賽的隊。
不連網：把 Cargo opener 換成假的，只回固定 JSON。
驗：①兩個子頁都解析出來、TBD 與空隊名剔除、日期只留 YYYY-MM-DD ②查失敗回 []（呼叫端會沿用舊檔）
③反例：Tournaments 沒有子頁 ⇒ 不生出任何階段 ④設定有開 stages。
跑：python events_extra_stage_test.py
"""
import io, json, os, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_events_extra as F  # noqa: E402

PASS = FAIL = 0


def ok(name, got, want=True):
    global PASS, FAIL
    if got == want:
        PASS += 1; print("  ✓ " + name)
    else:
        FAIL += 1; print("  ✗ %s：得到 %r，應為 %r" % (name, got, want))


PG = "2026 Season World Championship"
TOUR = [{"o": PG + "/Play-In", "ds": "2026-10-15", "de": "2026-10-18"},
        {"o": PG + "/Main Event", "ds": "2026-10-23", "de": "2026-11-14 00:00:00"}]
PLAY = [{"o": PG + "/Play-In", "tm": "Karmine Corp"}, {"o": PG + "/Play-In", "tm": "Cloud9"},
        {"o": PG + "/Main Event", "tm": "T1"}, {"o": PG + "/Main Event", "tm": "TBD"},
        {"o": PG + "/Main Event", "tm": ""}, {"o": PG + "/Main Event", "tm": "Gen.G"}]


class Resp:
    def __init__(self, b): self.b = b
    def read(self): return self.b


class Op:
    def __init__(self, tour, play, fail=False):
        self.tour, self.play, self.fail = tour, play, fail

    def open(self, req, timeout=0):
        if self.fail:
            raise OSError("boom")
        u = req.full_url
        return Resp(json.dumps(self.tour if "Tournaments" in u else self.play).encode())


F._throttle = lambda: None
F._mark = lambda: None

print("① 正常")
F._COP = Op(TOUR, PLAY)
st = F.cargo_stages(PG)
ok("兩個階段、順序入圍賽→正賽", [s["name"] for s in st], ["Play-In", "Main Event"])
ok("入圍賽日期", (st[0]["from"], st[0]["to"]), ("2026-10-15", "2026-10-18"))
ok("正賽日期只留日", st[1]["to"], "2026-11-14")
ok("入圍賽隊伍", st[0]["teams"], ["Cloud9", "Karmine Corp"])
ok("正賽剔除 TBD／空白", st[1]["teams"], ["Gen.G", "T1"])

print("② 查失敗")
F._COP = Op(TOUR, PLAY, fail=True)
ok("連線失敗回 []", F.cargo_stages(PG), [])

print("③ 反例：沒有子頁")
F._COP = Op([{"o": PG, "ds": "2026-10-15", "de": "2026-11-14"}], PLAY)
ok("沒有 /Play-In、/Main Event ⇒ 不生階段", F.cargo_stages(PG), [])

print("④ 設定")
ok("2026 WLDs 有開 stages", bool(F.EVENTS[2026]["WLDs"].get("stages")))

print("通過 %d／失敗 %d" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
