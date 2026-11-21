# -*- coding: utf-8 -*-
"""transfers_dump.py 的回歸：頁面「背景預熱」進行中也要倒得出正確的一份（2026-11-22 #3542）。

  python scripts/transfers_dump_test.py        約 1 分鐘；只讀，不寫 transfers_review_dump.txt 正本

素材是真實的 index.html 與真實資料（自己起本機 server，port 8868，跟正式那支的 8866 錯開）。
怎麼把「撞上預熱」變成每次都重現：預熱的每一步是用 requestIdleCallback(step,{timeout:800}) 排的，
init script 把這種呼叫延後 N 毫秒 ⇒ 預熱停在「複製品剛蓋上、真的 main 剛藏起來」那一刻，足夠做完對照。
  [1] 平常：倒得出來、每一隊有隊名、隊數＝畫面上的列數
  [2] 正控制（預熱凍住時，舊寫法會怎樣）：按鈕對到 2 顆、陣容表 2 份、藏著那份隊名全空、check_board 擋得下
  [3] 同樣凍住，走新流程 dump() ⇒ 跟 [1] 逐列相同
  [4] 預熱永遠不收尾 ⇒ 報錯，不倒半套
  [5] main(out=暫存檔) 端到端；正本 transfers_review_dump.txt 沒被碰
"""
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import transfers_dump as m  # noqa: E402

PORT = 8868
PORT_E2E = 8869
OK = [0]
NG = [0]


def ck(cond, msg):
    if cond:
        OK[0] += 1
        print("  ✓ " + msg)
    else:
        NG[0] += 1
        print("  ✗ " + msg)


def freeze_js(ms):
    """只攔預熱那種呼叫（timeout:800）；ms<=0＝永遠不跑。別的 requestIdleCallback 照舊。"""
    return ("(()=>{const o=window.requestIdleCallback?window.requestIdleCallback.bind(window):(f=>setTimeout(f,40));"
            "window.requestIdleCallback=(f,opt)=>{if(opt&&opt.timeout===800){window.__frozen=(window.__frozen||0)+1;"
            "return %d>0?setTimeout(f,%d):0;}return o(f,opt);};})()" % (ms, ms))


WARMING = "() => window._warming === true && (window.__frozen || 0) >= 1 && !!document.querySelector('[data-warm-cover]')"
BTN = '.sqLaneBtn[data-k="trMode"][data-v="news"]'


def teams(board):
    return [x for x in board if not x.startswith("==")]


def stat(p):
    try:
        s = os.stat(p)
        return (s.st_mtime_ns, s.st_size)
    except OSError:
        return None


def main():
    from playwright.sync_api import sync_playwright
    real_before = stat(m.OUT)
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"], cwd=m.ROOT,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()

            print("[1] 平常（沒有動手腳）")
            pg = m.open_page(b, PORT)
            pg.wait_for_timeout(4000)
            m.settle(pg)
            n_rows = pg.evaluate("() => document.querySelectorAll('.tbBoard>.tbRow').length")
            news_a, board_a = m.dump(pg)
            ta = teams(board_a)
            ck(len(ta) >= 30 and len(ta) == n_rows, f"陣容表 {len(ta)} 隊＝畫面上 {n_rows} 列（≥30）")
            ck(all(x.split(" : ", 1)[0].strip() for x in ta), "每一隊都有隊名")
            ck(len(news_a) >= 50, f"消息 {len(news_a)} 列（≥50）")
            ck(sum(1 for x in board_a if x.startswith("==")) >= 4, "聯賽標題 ≥4 個")
            pg.close()

            print("[2] 正控制：預熱凍在剛開始那一刻，舊寫法（不 settle 直接擷取）會看到什麼")
            pg = m.open_page(b, PORT, init=freeze_js(8000))
            pg.wait_for_function(WARMING, timeout=60000)
            st = pg.evaluate("() => ({mains: document.querySelectorAll('main').length, boards: document.querySelectorAll('.tbBoard').length,"
                             " hidden: getComputedStyle(document.getElementById('main')).visibility})")
            ck(st["mains"] == 2 and st["boards"] == 2 and st["hidden"] == "hidden",
               f"預熱中：main {st['mains']} 份、.tbBoard {st['boards']} 份、真的 main 是 {st['hidden']}")
            ck(pg.locator(BTN).count() == 2, f"消息按鈕對到 {pg.locator(BTN).count()} 顆（＝複查記的 strict mode violation）")
            old = pg.evaluate(m.BOARD)
            to = teams(old)
            empty = [x for x in to if not x.split(" : ", 1)[0].strip()]
            ck(len(to) == 2 * len(ta) and len(empty) == len(ta),
               f"不 settle 直接倒：{len(to)} 列（平常的 2 倍）、其中 {len(empty)} 列沒有隊名")
            try:
                m.check_board(old)
                ck(False, "check_board 應該擋下這一份")
            except RuntimeError as e:
                ck("沒有隊名" in str(e), "check_board 擋下：" + str(e)[:40])
            try:
                m.check_board(board_a)
                ck(True, "check_board 不擋平常那一份")
            except RuntimeError:
                ck(False, "check_board 誤擋平常那一份")

            print("[3] 同一頁（預熱還凍著）走新流程 dump()")
            ck(pg.evaluate("() => window._warming === true"), "呼叫前預熱確實還在進行")
            news_b, board_b = m.dump(pg)
            ck(board_b == board_a, f"陣容表跟 [1] 逐列相同（{len(teams(board_b))} 隊）")
            ck(news_b == news_a, f"消息跟 [1] 逐列相同（{len(news_b)} 列）")
            ck(pg.evaluate("() => !window._warming && document.querySelectorAll('main').length === 1"), "收尾後 main 只剩 1 份")
            pg.close()

            print("[4] 預熱永遠不收尾 ⇒ 要報錯，不倒半套")
            pg = m.open_page(b, PORT, init=freeze_js(-1))
            pg.wait_for_function(WARMING, timeout=60000)
            try:
                m.dump(pg, timeout=3000)
                ck(False, "dump() 應該報錯")
            except RuntimeError as e:
                ck("預熱沒有收尾" in str(e), "dump() 報錯：" + str(e)[:30])
            pg.close()
            b.close()
    finally:
        srv.kill()

    print("[5] main() 端到端，寫到暫存檔")
    tmp = os.path.join(tempfile.mkdtemp(prefix="trdump_"), "dump.txt")
    ck(os.path.abspath(tmp).lower().find(os.path.abspath(m.ROOT).lower()) != 0, "暫存檔不在 repo 裡")
    m.main(out=tmp, port=PORT_E2E)
    txt = open(tmp, encoding="utf-8").read() if os.path.exists(tmp) else ""
    head, _, tail = txt.partition("\n\n【陣容表】\n")
    ck(head.startswith("【消息】") and head.count("\n") == len(news_a), f"消息段 {head.count(chr(10))} 列＝[1] 的 {len(news_a)}")
    ck(tail.rstrip("\n").split("\n") == board_a, "陣容表段跟 [1] 逐列相同")
    ck(stat(m.OUT) == real_before, "正本 transfers_review_dump.txt 的 mtime／大小沒動")
    try:
        os.remove(tmp)
        os.rmdir(os.path.dirname(tmp))
    except OSError:
        pass

    print(f"\n通過 {OK[0]} 條／失敗 {NG[0]} 條")
    sys.exit(1 if NG[0] else 0)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
