# -*- coding: utf-8 -*-
"""精進迴圈 #208（2026-09-22）：preflight_check.py 總上限的沙盒測試。

為什麼要有這條：publish.bat 裡 run_update 有逐步 1800 秒（#202）、auto_fix 有 WaitForExit(600000)，
但守門自己沒有上限——`pg.evaluate` 沒有 timeout 參數可下（#203 探針：頁面載完後主執行緒 for(;;){}
⇒ goto／wait_for_timeout 都回來、evaluate 到 45 秒還在等）。守門卡死 ⇒ 走不到 push、也走不到健檢
⇒ 不留 HEALTH_ALERT.txt，排程 IgnoreNew＋PT72H ⇒ 後面最多 6 班被跳過。

做法（沙盒＝每個情境一個 tempfile 目錄）：preflight_check.py 的 ROOT 是從自己的位置推的，
所以把它複製到 <box>/scripts/ 配一份假 index.html 就自然指向沙盒——不用 monkeypatch，也沒有任何
路徑常數還指著真的 repo（斷言：沙盒裡「① 資料檔 0 個」，真 repo 是 51 個）。
  A 正例   ：現版＋卡死頁面、上限縮到 8 秒（環境變數 PREFLIGHT_TMO_S）⇒ 8＋寬限秒內 exit 1、
             印「守門逾時」、5 秒時記下的 headless_shell／node 子孫 PID 事後一個都不在（比 PID 不比數量，
             site_audit 可能同時在跑）。
  B 正控制 ：舊版（git show 1a5cd582，沒有總上限）＋同一份卡死頁面 ⇒ 到點還活著（測試才收掉它）。
             這條紅了代表卡死頁面沒卡住（素材壞了），A 的綠就不算數。
  C 對照   ：乾淨頁面（過得了①②③每一項）新舊版都 exit 0，stdout 逐行相同（總上限在正常路徑上零痕跡），
             而且 5 秒內自己結束（計時器是 daemon，不會把程序多留 180 秒）。
用法：python scripts/preflight_tmo_test.py   （exit 0＝全過）
"""
import io
import os
import subprocess
import sys
import tempfile
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "scripts", "preflight_check.py")
OLDREV = "1a5cd582"      # 沒有總上限的舊版（正控制）
TMO = 20                 # 沙盒把上限縮到 20 秒（乾淨頁面固定睡眠合計 6.9 秒＋啟動 ≈ 8～9 秒，8 秒會誤觸）
GRACE = 25               # 到點後給 powershell 列子程序＋taskkill 的寬限
CLEAN_MAX = TMO          # 乾淨頁面要在上限之前自己結束（計時器是 daemon，不會把程序撐到 TMO）

FAILS = []


def ck(cond, msg):
    print(("  OK  " if cond else "  紅  ") + msg)
    if not cond:
        FAILS.append(msg)


# 過得了守門①②③每一項的最小頁面：nav 三個分頁籤、#tbl 四欄五列、內容 > 5000 字、
# 欄寬固定＋置中 ⇒ 空隙全等、左右邊距對稱且 ≥ 20px。
CLEAN = (
    '<!doctype html><html><head><meta charset="utf-8"><style>'
    'body{margin:0;padding:20px;font:14px Arial}'
    'nav .tab{display:inline-block;padding:6px 12px;cursor:pointer}'
    '.tblwrap{display:inline-block;padding:0 40px}'
    'table{border-collapse:collapse;table-layout:fixed;width:480px}'
    'th,td{width:120px;text-align:center;padding:4px 0;overflow:hidden;white-space:nowrap}'
    '</style></head><body>'
    '<nav><span class="tab" data-view="英雄">英雄</span><span class="tab" data-view="選手">選手</span>'
    '<span class="tab" data-view="戰隊">戰隊</span></nav>'
    '<div class="tblwrap"><table id="tbl"><thead><tr><th>A</th><th>B</th><th>C</th><th>D</th></tr></thead><tbody>'
    + "".join("<tr><td>1234</td><td>1234</td><td>1234</td><td>1234</td></tr>" for _ in range(5))
    + '</tbody></table></div><div hidden>' + ("x" * 6000) + '</div>'
    '%s</body></html>'
)
WEDGE_JS = "<script>setTimeout(function(){for(;;){}},500)</script>"   # 載完 0.5 秒後主執行緒卡死


def make_box(tag, src_text, html):
    d = tempfile.mkdtemp(prefix="pf_tmo_%s_" % tag)
    os.makedirs(os.path.join(d, "scripts"))
    io.open(os.path.join(d, "scripts", "preflight_check.py"), "w",
            encoding="utf-8", newline="\n").write(src_text)
    io.open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(html)
    return d


def snapshot():
    """全機程序表 {pid: (ppid, name)}，一次 CIM 查詢。"""
    ps = ("Get-CimInstance Win32_Process | ForEach-Object { '{0} {1} {2}' -f "
          "$_.ProcessId, $_.ParentProcessId, $_.Name }")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, text=True, timeout=90)
    out = {}
    for l in r.stdout.splitlines():
        p = l.split(None, 2)
        if len(p) >= 2 and p[0].isdigit() and p[1].isdigit():
            out[int(p[0])] = (int(p[1]), p[2] if len(p) > 2 else "")
    return out


def descendants(pid, snap):
    got, q = [], [pid]
    while q:
        cur = q.pop()
        for k, (pp, nm) in snap.items():
            if pp == cur and k != pid and k not in [g[0] for g in got]:
                got.append((k, nm))
                q.append(k)
    return got


def run(box, tmo, wait, peek_at=5):
    env = dict(os.environ, PREFLIGHT_TMO_S=str(tmo))
    t0 = time.time()
    pr = subprocess.Popen([sys.executable, os.path.join(box, "scripts", "preflight_check.py")],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, cwd=box)
    kids = []
    try:
        pr.wait(timeout=peek_at)             # 幾秒內就結束（乾淨頁面）⇒ 不用記子孫
    except subprocess.TimeoutExpired:
        kids = descendants(pr.pid, snapshot())
    alive_at_end = False
    try:
        out = pr.communicate(timeout=max(0.1, wait - (time.time() - t0)))[0]
    except subprocess.TimeoutExpired:
        alive_at_end = True
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pr.pid)], capture_output=True)
        try:
            out = pr.communicate(timeout=30)[0]
        except subprocess.TimeoutExpired:
            pr.kill()
            out = b""
    return pr.returncode, out.decode("utf-8", "replace"), time.time() - t0, kids, alive_at_end


def main():
    new_src = io.open(SRC, encoding="utf-8").read()
    old_src = subprocess.run(["git", "show", "%s:scripts/preflight_check.py" % OLDREV],
                             capture_output=True, cwd=ROOT).stdout.decode("utf-8", "replace")
    ck("PREFLIGHT_TMO_S" in new_src, "現版有總上限（PREFLIGHT_TMO_S）")
    ck(old_src and "PREFLIGHT_TMO_S" not in old_src, "正控制舊版 %s 真的沒有總上限" % OLDREV)

    print("[A] 現版＋卡死頁面（上限 %ds）" % TMO)
    bx = make_box("new_wedge", new_src, CLEAN % WEDGE_JS)
    rc, out, dt, kids, alive = run(bx, TMO, TMO + GRACE)
    tail = "\n".join("      " + l[:150] for l in out.strip().splitlines()[-6:])
    print(tail)
    ck(not alive, "到點後自己結束（不用測試去收）")
    ck(rc == 1, "離開碼 1＝守門沒過＝不 push，實際 %s" % rc)
    ck(dt < TMO + GRACE, "%.1f 秒內結束（上限 %d＋寬限 %d）" % (dt, TMO, GRACE))
    ck("守門逾時" in out, "印了「守門逾時」那一行（日誌看得出為什麼沒 push）")
    ck("① 資料檔 0 個" in out, "跑的是沙盒（沙盒 0 個資料檔；真 repo 是 51 個）")
    heads = [k for k in kids if any(s in k[1].lower() for s in ("headless", "chrome", "node"))]
    ck(bool(heads), "5 秒時 headless／node 子孫真的起來了（%d 個：%s）——否則「沒留孤兒」是空測"
       % (len(heads), sorted(set(n for _, n in heads))))
    time.sleep(2)
    snap = snapshot()
    left = [k for k in kids if k[0] in snap]
    ck(not left, "記下的子孫 PID 事後一個都不在（比 PID）：剩 %s" % left)
    for k, _ in left:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(k)], capture_output=True)

    print("[B] 正控制：舊版 %s＋同一份卡死頁面（到點應該還活著）" % OLDREV)
    bx = make_box("old_wedge", old_src, CLEAN % WEDGE_JS)
    rc, out, dt, kids, alive = run(bx, TMO, TMO + GRACE)
    ck(alive, "舊版到 %d 秒還活著（素材真的會卡；測試收掉了它）" % (TMO + GRACE))
    ck("守門逾時" not in out, "舊版沒有「守門逾時」字樣")
    time.sleep(2)
    snap = snapshot()
    for k, _ in [k for k in kids if k[0] in snap]:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(k)], capture_output=True)

    print("[C] 對照：乾淨頁面新舊版逐行相同、都 exit 0、自己結束")
    bn = make_box("new_clean", new_src, CLEAN % "")
    bo = make_box("old_clean", old_src, CLEAN % "")
    rcn, outn, dtn, _, aln = run(bn, TMO, CLEAN_MAX, peek_at=CLEAN_MAX)
    rco, outo, dto, _, alo = run(bo, TMO, CLEAN_MAX, peek_at=CLEAN_MAX)
    ck(rcn == 0 and "✓ 守門通過" in outn, "現版乾淨頁面 exit 0、印「✓ 守門通過」（實際 rc %s）" % rcn)
    ck(rco == 0, "舊版乾淨頁面 exit 0（實際 rc %s）" % rco)
    ck(not aln and dtn < TMO, "現版 %.1f 秒自己結束（< 上限 %d：daemon 計時器沒把程序多留住）" % (dtn, TMO))
    ln, lo = outn.strip().splitlines(), outo.strip().splitlines()
    ck(ln == lo, "stdout 逐行相同（%d 行）" % len(ln) if ln == lo else
       "stdout 不同：新 %s ／舊 %s" % (ln, lo))

    ok = not FAILS
    print("結果：%s" % ("全過" if ok else "紅 %d 條：%s" % (len(FAILS), "；".join(FAILS))))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
