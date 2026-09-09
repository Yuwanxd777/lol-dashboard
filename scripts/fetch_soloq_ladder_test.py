# -*- coding: utf-8 -*-
"""#84 沙盒測試：prefetch_ladders 改成「每平台一條執行緒」之後，結果與日誌要跟循序版一模一樣。

被測的是 scripts/fetch_soloq.py 的 prefetch_ladders／_ladder_one／_REQS／_WAITED。

隔離（照 CLAUDE.md「沙盒要接管被測模組的每一個證據來源」＋「出口與對外入口同樣要點名」）：
  ① 對外入口 `F.riot_get` 換成假的，回傳的 puuid 一律帶 `SBX-` 前綴
     ⇒ 有一條「只有沙盒才有的證據」的正例：LADDER 的 key 全部要帶那個前綴，
       任何一筆沒帶就代表有東西真的連上了 Riot。
  ② 傳輸出口 `F._CONN_CLS` 換成「一被建立就 raise」的假類別
     ⇒ 就算有人繞過 riot_get 直接走 _raw_get，也會當場炸掉而不是靜默去打真 API。
  ③ 模組層路徑常數 `F.OUT`／`F.ACCOUNTS` 指到暫存目錄，並 assert 它們不在真 repo 底下；
     跑完再比對四個真實檔的 mtime 一個位元都沒動。
  ④ 正控制：把 HEAD 那版 fetch_soloq.py 拉出來跑同一套，證明舊版真的紅在該紅的地方。

用法：python scripts/fetch_soloq_ladder_test.py
"""
import io, os, re, sys, time, json, types, shutil, tempfile, subprocess, threading
import importlib.util
import contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PLATS = ["br1", "euw1", "kr", "na1"]
TIERS = ("challenger", "grandmaster", "master")
SIZES = {"challenger": 3, "grandmaster": 5, "master": 9}
DELAY = 0.15                      # 每次假請求的耗時；循序 12 次 ≈ 1.8s、並行 3 次 ≈ 0.45s

OK = [0]
BAD = []


def chk(cond, msg):
    if cond:
        OK[0] += 1
    else:
        BAD.append(msg)
        print("  ✗ " + msg)


def load(path, name):
    """從檔案路徑載入模組（正本與 HEAD 舊版要能同時在記憶體裡，所以名字不同）。"""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class Boom:
    """傳輸出口的地雷：只要有人真的想開連線就炸（沙盒不該有任何真連線）。"""
    def __init__(self, *a, **k):
        raise AssertionError("沙盒外洩：有程式碼繞過 riot_get 直接開了 HTTPS 連線 → " + repr(a))


def make_fake_raw(mod, fail_plat=None, mode="exc", counter=None):
    """假 `_raw_get`——**接管的是最底層的傳輸出口，不是 riot_get**。

    差別很要緊：接管 riot_get 的話，它裡面的 `_throttle`／`_BUCKETS`／`_REQS`／429 重試
    全都不會被執行，測到的是沙盒自己（#84 的突變測試就是這樣抓到「_REQS 不再計數」還全綠）。
    接管 _raw_get ⇒ 除了 socket 之外整條路徑都是真的。

    `fail_plat` 那個平台照 `mode` 出事：
      exc      ＝回 200 但 entries 裡塞非 dict（真的會發生的畸形回應）⇒ _ladder_one 內部丟例外
      http500  ＝回 503（_ladder_one 會 sleep 3 秒再試一次）
    """
    def fake(url, timeout=15):
        m = re.match(r"https://([a-z0-9]+)\.api\.riotgames\.com/lol/league/v4/([a-z]+)leagues/", url)
        assert m, "假 _raw_get 收到沒預期的 URL：" + url
        plat, tier = m.group(1), m.group(2)
        if counter is not None:
            counter.append((plat, tier))
        time.sleep(DELAY)
        if plat == fail_plat and mode == "http500":
            return 503, {}, b""
        ents = [{"puuid": "SBX-%s-%s-%d" % (plat, tier, i), "rank": "I",
                 "leaguePoints": 100 + i, "wins": 10 + i, "losses": i}
                for i in range(SIZES[tier])]
        if plat == fail_plat and mode == "exc":
            ents = [12345] * SIZES[tier]        # 畸形：entry 不是物件 ⇒ e.get() 丟 AttributeError
        body = json.dumps({"tier": tier.upper(), "entries": ents}).encode("utf-8")
        return 200, {}, body
    return fake


def sandbox(mod, td, fail_plat=None, mode="exc"):
    """把模組的每一個證據來源接管掉，回傳 (輸出用的 counter list)。"""
    mod.OUT = os.path.join(td, "soloq.js")
    mod.ACCOUNTS = os.path.join(td, "soloq_accounts.json")
    mod._CONN_CLS = Boom
    counter = []
    mod._raw_get = make_fake_raw(mod, fail_plat, mode, counter)
    mod.LADDER.clear()
    mod._BUCKETS.clear()
    try:
        mod._REQS.clear()
        mod._WAITED[0] = 0.0
    except AttributeError:
        pass                                    # 舊版沒有這兩個 → 正控制那邊會點名
    mod._LIMITS = []                            # 預設不節流；要測 _WAITED 的那條自己設回來
    return counter


def run(mod, argv):
    """跑一次 prefetch_ladders，回傳 (牆鐘, stdout 文字, n)。"""
    old_argv = sys.argv
    sys.argv = ["fetch_soloq.py"] + argv
    buf = io.StringIO()
    t0 = time.time()
    try:
        with contextlib.redirect_stdout(buf):
            n = mod.prefetch_ladders(set(PLATS))
    finally:
        sys.argv = old_argv
    return time.time() - t0, buf.getvalue(), n


def ladder_lines(txt):
    return [l for l in txt.split("\n") if l.strip().startswith("聯盟名單")]


def main():
    td = tempfile.mkdtemp(prefix="r84ladder_")
    os.environ["RIOT_API_KEY"] = "SANDBOX-FAKE-KEY"
    watched = {p: os.path.getmtime(os.path.join(ROOT, p))
               for p in ("scripts/fetch_soloq.py", "scripts/soloq_accounts.json",
                         "soloq.js", "scripts/soloq_played.json")
               if os.path.exists(os.path.join(ROOT, p))}
    print("── ① 沙盒本身站得住 ──")
    # R84_TARGET＝改測另一份 fetch_soloq.py（突變測試 autopilot/_r84_mutate.py 用；
    # 真實檔的 mtime 檢查與 ⑧ 的 git show 正控制照樣對著真 repo）。
    target = os.environ.get("R84_TARGET") or os.path.join(HERE, "fetch_soloq.py")
    if target != os.path.join(HERE, "fetch_soloq.py"):
        print("     被測檔：" + target)
    F = load(target, "_r84_cur")
    sandbox(F, td)
    chk(td in F.OUT and td in F.ACCOUNTS, "模組層路徑常數要指進暫存目錄（F.OUT=%s）" % F.OUT)
    chk(ROOT not in F.OUT and ROOT not in F.ACCOUNTS, "模組層不可以有路徑常數還指著真 repo")
    try:
        F._CONN_CLS("kr.api.riotgames.com")
        chk(False, "傳輸出口地雷沒炸 ⇒ 沙盒沒接管到 _CONN_CLS")
    except AssertionError:
        chk(True, "")

    print("── ② 並行版：結果、日誌、回傳值 ──")
    par_wall, par_txt, par_n = run(F, [])
    par_ladder = dict(F.LADDER)
    exp_n = len(PLATS) * sum(SIZES.values())
    chk(par_n == exp_n, "回傳值應該是 %d，實際 %d" % (exp_n, par_n))
    chk(len(par_ladder) == exp_n, "LADDER 應該有 %d 筆，實際 %d" % (exp_n, len(par_ladder)))
    chk(all(pu.startswith("SBX-") for _, pu in par_ladder),
        "只有沙盒才有的證據：LADDER 的 puuid 全部要帶 SBX- 前綴（有真連線就會破）")
    chk(all(v.get("queueType") == "RANKED_SOLO_5x5" for v in par_ladder.values()),
        "每一筆都要補上 queueType")
    chk(all(v.get("tier") == k[1].split("-")[2].upper() for k, v in par_ladder.items()),
        "每一筆的 tier 要照外層補（challenger→CHALLENGER…）")
    chk("⏱ 聯盟名單預抓" in par_txt, "要印階段計時那行（#56：時間資料要留在 log）")
    chk("每平台一條執行緒" in par_txt, "並行時計時那行要註明是並行")
    chk(sum(F._REQS.values()) == len(PLATS) * len(TIERS),
        "_REQS 要數到 %d 次請求，實際 %d" % (len(PLATS) * len(TIERS), sum(F._REQS.values())))

    print("── ③ 循序版（--ladder-seq）：逐字一樣 ──")
    sandbox(F, td)
    seq_wall, seq_txt, seq_n = run(F, ["--ladder-seq"])
    seq_ladder = dict(F.LADDER)
    chk(seq_n == par_n, "循序與並行的回傳值要一樣（%d vs %d）" % (seq_n, par_n))
    chk(seq_ladder == par_ladder, "循序與並行的 LADDER 要逐鍵逐值相同")
    chk(ladder_lines(seq_txt) == ladder_lines(par_txt),
        "「聯盟名單 …」那幾行要逐字逐序相同\n     seq=%r\n     par=%r"
        % (ladder_lines(seq_txt)[:2], ladder_lines(par_txt)[:2]))
    chk("循序" in par_txt.split("⏱")[-1] or "每平台一條執行緒" in par_txt, "")
    chk("循序" in seq_txt.split("⏱")[-1], "--ladder-seq 的計時那行要註明是循序")

    print("── ④ 並行真的有並行（不是只換了寫法）──")
    print("     循序 %.2fs／並行 %.2fs（假請求各 %.2fs x 12）" % (seq_wall, par_wall, DELAY))
    chk(seq_wall > len(PLATS) * len(TIERS) * DELAY * 0.8,
        "循序版應該 ≈ 12 x %.2fs，實際 %.2fs" % (DELAY, seq_wall))
    chk(par_wall < seq_wall * 0.6,
        "並行版應該明顯比循序快（實際 %.2fs vs %.2fs）" % (par_wall, seq_wall))
    chk(par_wall > DELAY * len(TIERS) * 0.8,
        "並行版還是要等自己那 3 份名單（不能快到像沒抓，實際 %.2fs）" % par_wall)

    print("── ⑤ 一個平台出事不連坐其它平台 ──")
    sandbox(F, td, fail_plat="euw1", mode="exc")
    _, exc_txt, exc_n = run(F, [])
    chk(exc_n == (len(PLATS) - 1) * sum(SIZES.values()),
        "euw1 丟例外時其餘 3 個平台要照抓（應 %d，實際 %d）"
        % ((len(PLATS) - 1) * sum(SIZES.values()), exc_n))
    chk("例外" in exc_txt and "euw1" in exc_txt, "要印出是哪個平台掛了、走逐帳號")
    chk(all(k[0] != "euw1" for k in F.LADDER), "掛掉的平台不可以留半套資料進 LADDER")
    chk(len({k[0] for k in F.LADDER}) == len(PLATS) - 1, "其餘平台要全員到齊")

    sandbox(F, td, fail_plat="br1", mode="http500")
    _, h5_txt, h5_n = run(F, [])
    chk(h5_n == (len(PLATS) - 1) * sum(SIZES.values()), "HTTP 503 的平台要整個跳過、其餘照抓")
    chk("HTTP 503" in h5_txt, "非 200 要照舊印 HTTP 碼")
    chk(sum(F._REQS.values()) == (len(PLATS) - 1) * len(TIERS) + len(TIERS) * 2,
        "5xx 要重試一次 ⇒ br1 打 6 次，實際整體 %d 次" % sum(F._REQS.values()))

    print("── ⑥ 單一平台不開執行緒（走循序那條路）──")
    sandbox(F, td)
    old_argv, sys.argv = sys.argv, ["fetch_soloq.py"]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        one_n = F.prefetch_ladders({"kr"})
    sys.argv = old_argv
    chk(one_n == sum(SIZES.values()), "單平台的回傳值")
    chk("循序" in buf.getvalue(), "只有一個平台時不必開執行緒，計時那行要說「循序」")

    print("── ⑦ _WAITED：節流等待有累計到，四條執行緒都算進去 ──")
    sandbox(F, td)
    F._LIMITS = [(2, 1.0)]            # 每個桶每秒 2 次 ⇒ 每平台第 3 份名單要等約 1s
    F._LIM_SRC = "沙盒"
    w_wall, _, _ = run(F, [])
    chk(F._WAITED[0] > 2.5,
        "四個平台各等約 1s ⇒ 累計應該 >2.5s，實際 %.2fs" % F._WAITED[0])
    chk(F._WAITED[0] > w_wall,
        "並行時「累計等待」要大於牆鐘（四條同時在等，%.2fs vs 牆鐘 %.2fs）" % (F._WAITED[0], w_wall))

    print("── ⑧ 正控制：HEAD 那版跑同一套，該紅的地方要紅 ──")
    old_src = subprocess.run(["git", "show", "HEAD:scripts/fetch_soloq.py"], cwd=ROOT,
                             capture_output=True).stdout.decode("utf-8", "replace")
    old_path = os.path.join(td, "fetch_soloq_head.py")
    io.open(old_path, "w", encoding="utf-8", newline="").write(old_src)
    O = load(old_path, "_r84_old")
    sandbox(O, td)
    _, o_txt, o_n = run(O, [])
    chk("⏱ 聯盟名單預抓" not in o_txt, "正控制：舊版本來就沒有階段計時那行")
    chk(not hasattr(O, "_REQS"), "正控制：舊版本來就沒有 _REQS")
    chk(ladder_lines(o_txt) == ladder_lines(par_txt),
        "舊版與新版的「聯盟名單 …」那幾行要逐字相同（這是改動的核心保證）")
    chk(o_n == par_n, "舊版與新版的回傳值要一樣（%d vs %d）" % (o_n, par_n))
    sandbox(O, td, fail_plat="euw1", mode="exc")
    try:
        run(O, [])
        chk(False, "正控制：舊版遇到畸形回應應該整支炸掉（沒有 try/except）")
    except Exception:
        chk(True, "")
    chk(len(O.LADDER) < (len(PLATS) - 1) * sum(SIZES.values()),
        "正控制：舊版一炸就整段停，後面的平台根本沒抓到（實際 %d 筆）" % len(O.LADDER))

    print("── ⑨ 真實檔一個位元都沒動 ──")
    for p, mt in watched.items():
        chk(os.path.getmtime(os.path.join(ROOT, p)) == mt, "%s 的 mtime 被動到了" % p)
    chk(not os.path.exists(os.path.join(td, "soloq.js")), "沙盒目錄裡不該生出 soloq.js（沒跑 main）")

    shutil.rmtree(td, ignore_errors=True)
    print("\n%d 通過／%d 失敗" % (OK[0], len(BAD)))
    for b in BAD:
        print("   ✗ " + b.split("\n")[0])
    return 1 if BAD else 0


if __name__ == "__main__":
    sys.exit(main())
