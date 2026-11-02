# -*- coding: utf-8 -*-
"""fill_missing_puuids 不可把別人的 puuid 掛上去（2026-11-02 精進迴圈 #2449）——純離線。

假頁面照 sync Playwright 的真實行為：**事件只在 API 呼叫（goto／wait_for_timeout）期間派送**，
time.sleep 期間收不到；這正是舊版把前一頁的請求算到下一個帳號頭上的原因。

① 正常：名字對得上 ⇒ 收；大小寫／空白不同也算同一個
② 前一頁遲到的回應在下一個 goto 才派送 ⇒ 不收別人的，下一個帳號拿到自己的（11-02 Cosgoat／Cosmoat）
③ 首頁請求帶到別人的 puuid、目標頁 Player Not Found ⇒ 不補（10-17～10-25 JunJia 掛上 Juhan 等人）
④ 429 ⇒ 不補、訊息說限流
⑤ 名字不對的帳號等滿、訊息列出是誰的比賽；沒場次 ⇒ 不補
⑥ listener 用完要拆；寫回只動補到的那筆；全沒補到不寫檔
⑦ 隔離：所有沙盒帳號在暫存目錄、真實帳號檔 md5 前後不變；模組的 ACCOUNTS 沒接管就中止
"""
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
if (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") != "utf8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import fetch_soloq_update as m  # noqa: E402

REAL = os.path.join(HERE, "soloq_accounts.json")
PU_A, PU_B, PU_PRO = "A" * 30, "B" * 30, "P" * 30
fails = []


def check(name, ok, extra=""):
    print(("  ✓ " if ok else "  ✗ ") + name + (f"  {extra}" if extra and not ok else ""))
    if not ok:
        fails.append(name)


class Resp:
    def __init__(self, pu, name=None, status=200, sub="match-history?size=15"):
        self.url = f"https://dpm.lol/v1/players/{pu}/{sub}"
        self.status = status
        self._name = name

    def json(self):
        if self._name is None:
            return {"matches": []}
        g, t = self._name.split("#")
        return {"matches": [{"participants": [{"gameName": g, "tagLine": t}]}]}


class FakePage:
    """script：{網址片段: {"during_goto": [...], "after_wait": [...], "title": str}}"""

    def __init__(self, script):
        self.script, self.h, self.pending, self.ttl = script, [], [], "x - DPM.LOL"
        self.gotos, self.removed = [], False

    def on(self, ev, fn):
        assert ev == "response"
        self.h.append(fn)

    def remove_listener(self, ev, fn):
        self.h.remove(fn)
        self.removed = True

    def _pump(self):
        for r in self.pending:
            for f in list(self.h):
                f(r)
        self.pending = []

    def goto(self, url, **kw):
        self.gotos.append(url)
        s = self.script.get(url.rsplit("/", 1)[-1], {})
        self.ttl = s.get("title", "x - DPM.LOL")
        self.pending = list(s.get("during_goto", []))  # 只有這批會在 goto 期間派送
        self._pump()
        self.pending = list(s.get("after_wait", []))   # 這批留到下一次 API 呼叫

    def wait_for_timeout(self, ms):
        self._pump()

    def title(self):
        return self.ttl


def run(accs, script):
    d = tempfile.mkdtemp(prefix="fillpuuid_")
    p = os.path.join(d, "acc.json")
    json.dump(accs, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    old = m.ACCOUNTS
    m.ACCOUNTS = p
    assert os.path.dirname(m.ACCOUNTS) == d, "ACCOUNTS 沒接管"
    buf, so = io.StringIO(), sys.stdout
    pg = FakePage(script)
    sys.stdout = buf
    mt0 = os.path.getmtime(p)
    try:
        n = m.fill_missing_puuids(pg)
    finally:
        sys.stdout = so
        m.ACCOUNTS = old
    out = json.load(open(p, encoding="utf-8"))
    written = os.path.getmtime(p) != mt0 or out != accs
    shutil.rmtree(d, ignore_errors=True)
    return n, {a["riotId"]: a.get("dpmPuuid") for a in out}, buf.getvalue(), pg, written


def acc(rid):
    return {"player": "X", "team": "T", "platform": "kr", "riotId": rid}


def main():
    md5 = hashlib.md5(open(REAL, "rb").read()).hexdigest()

    print("① 正常")
    n, r, o, pg, _ = run([acc("Foo Bar#TW1")], {"Foo%20Bar-TW1": {"after_wait": [Resp(PU_A, "foobar#tw1")]}})
    check("名字（去空白、不分大小寫）對得上就收", n == 1 and r["Foo Bar#TW1"] == PU_A, o)
    check("listener 拆掉", pg.removed and not pg.h)

    print("② 前一頁遲到的回應")
    s = {"Slow-A": {"after_wait": []},
         "Next-B": {"during_goto": [Resp(PU_A, "Slow#A")], "after_wait": [Resp(PU_B, "Next#B")]}}
    n, r, o, _, _ = run([acc("Slow#A"), acc("Next#B")], s)
    check("Next 不收前一頁的 puuid、收自己的", r["Next#B"] == PU_B, str(r))
    check("Slow 維持沒有 puuid", r["Slow#A"] is None and n == 1, str(r))

    print("③ 首頁帶到別人、目標頁查無此人")
    s = {"NoSuch-KR1": {"title": "Player Not Found - DPM.LOL", "during_goto": [Resp(PU_PRO, "Juhana#OMG")]}}
    n, r, o, pg, w = run([acc("NoSuch#KR1")], s)
    check("不掛別人的 puuid", n == 0 and r["NoSuch#KR1"] is None, str(r))
    check("訊息寫查無此人", "查無此人" in o, o)
    check("全沒補到不寫檔", not w)

    print("④ 限流")
    s = {"Lim-KR1": {"during_goto": [Resp(PU_A, status=429, sub="widgets/pings")]}}
    n, r, o, _, _ = run([acc("Lim#KR1")], s)
    check("429 不補、訊息說限流", n == 0 and "限流" in o, o)
    s = {"Lim-KR1": {"during_goto": [Resp(PU_A, "Lim#KR1", status=429)]}}
    n, r, o, _, _ = run([acc("Lim#KR1")], s)
    check("match-history 429 帶對的 puuid 也不補", n == 0 and r["Lim#KR1"] is None, str(r))

    print("⑤ 名字不對／沒場次")
    s = {"Who-KR1": {"after_wait": [Resp(PU_PRO, "Other#KR1")]}}
    n, r, o, _, _ = run([acc("Who#KR1")], s)
    check("別人的比賽 ⇒ 不收、列名字", n == 0 and "Other#KR1" in o, o)
    s = {"Who-KR1": {"after_wait": [Resp(PU_A, None)]}}
    n, r, o, _, _ = run([acc("Who#KR1")], s)
    check("沒場次 ⇒ 不補、訊息說沒回比賽", n == 0 and "沒回比賽" in o, o)
    s = {"Who-KR1": {"after_wait": [Resp(PU_PRO, "Who#KR1", sub="widgets/pings")]}}
    n, r, o, _, _ = run([acc("Who#KR1")], s)
    check("只有 widgets（無法驗名）⇒ 不補", n == 0, o)

    print("⑥ 寫回")
    accs = [acc("Ok#KR1"), dict(acc("Has#KR1"), dpmPuuid="KEEP"), dict(acc("Bad#KR1"), bad=True)]
    s = {"Ok-KR1": {"after_wait": [Resp(PU_A, "Ok#KR1")]}}
    n, r, o, pg, _ = run(accs, s)
    check("只補缺的、已有的不動、bad 跳過", n == 1 and r == {"Ok#KR1": PU_A, "Has#KR1": "KEEP", "Bad#KR1": None}, str(r))
    check("只訪問該訪問的頁", len(pg.gotos) == 1, str(pg.gotos))

    print("⑦ 隔離")
    check("真實帳號檔沒被動", hashlib.md5(open(REAL, "rb").read()).hexdigest() == md5)

    print(f"\n{'全部通過' if not fails else '失敗 ' + str(len(fails)) + ' 條：' + '；'.join(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
