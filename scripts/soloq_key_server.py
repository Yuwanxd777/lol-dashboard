# -*- coding: utf-8 -*-
"""積分牌位更新本機服務（給儀表板「🔑 添加API」按鈕用）
- 只綁 127.0.0.1:8177，外部連不進來；金鑰只放環境變數傳給 fetch_soloq.py，不寫檔、不記錄。
- 端點：GET /ping、GET /status、POST /update {"key":"RGAPI-…"}（金鑰格式不對直接 400，不會打 Riot）。
- 啟動：雙擊「積分牌位更新服務.bat」，關閉視窗即停止。
"""
import io, sys, json, os, re, threading, subprocess, time
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
PORT = 8177
ST = {"busy": False, "done": False, "ok": None, "log": ""}


def run_update(key):
    ST.update(busy=True, done=False, ok=None, log="開始更新牌位（fetch_soloq.py）…\n")
    t0 = time.time()
    sq = os.path.join(ROOT, "soloq.js")
    mt0 = os.path.getmtime(sq) if os.path.exists(sq) else 0
    env = dict(os.environ); env["RIOT_API_KEY"] = key
    try:
        p = subprocess.Popen([sys.executable, "-u", os.path.join(HERE, "fetch_soloq.py")],  # -u：不緩衝→彈窗能看到即時進度
                             cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace")
        for line in p.stdout:
            ST["log"] = (ST["log"] + line)[-6000:]
            print(line, end="")
        rc = p.wait()
        wrote = os.path.exists(sq) and os.path.getmtime(sq) > mt0
        denied = len(re.findall(r"401|403|Forbidden|Unauthorized", ST["log"]))
        ST["ok"] = bool(rc == 0 and wrote and denied <= 3)  # 一堆 401/403＝金鑰過期/無效
        if denied > 3:
            ST["log"] += f"\n⚠ 偵測到 {denied} 次 401/403：金鑰大概過期或貼錯，請到開發者頁 REGENERATE 後重貼。"
    except Exception as e:
        ST["log"] += f"\n執行失敗：{e}"; ST["ok"] = False
    ST["log"] += f"\n（耗時 {time.time()-t0:.0f} 秒）"
    ST["busy"] = False; ST["done"] = True


class H(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code); self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.end_headers()

    def do_GET(self):
        if self.path.startswith("/ping"):
            return self._json(200, {"ok": True, "busy": ST["busy"]})
        if self.path.startswith("/status"):
            return self._json(200, {"busy": ST["busy"], "done": ST["done"], "ok": ST["ok"], "log": ST["log"][-2000:]})
        self._json(404, {"err": "not found"})

    def do_POST(self):
        if self.path == "/flag":  # 事後補記「長期金鑰」旗標（貼完才勾選也能生效）
            n = int(self.headers.get("Content-Length") or 0)
            try:
                perm = bool(json.loads(self.rfile.read(n) or b"{}").get("permanent"))
                kf = os.path.join(HERE, "riot_key.local.json")
                d = json.load(open(kf, encoding="utf-8"))
                d["permanent"] = perm
                json.dump(d, open(kf, "w", encoding="utf-8"))
                return self._json(200, {"ok": True, "permanent": perm})
            except Exception as e:
                return self._json(200, {"ok": False, "err": str(e)})
        if self.path != "/update":
            return self._json(404, {"err": "not found"})
        if ST["busy"]:
            return self._json(409, {"err": "已有更新在執行中"})
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
            key = str(body.get("key", "")).strip()
            perm = bool(body.get("permanent"))
        except Exception:
            key, perm = "", False
        if not re.match(r"^RGAPI-[0-9a-fA-F-]{20,60}$", key):
            return self._json(400, {"err": "金鑰格式不對（應為 RGAPI- 開頭）"})
        try:  # 存本機（gitignore 非白名單、絕不會推上 git）：每天 10:00 排程的 fetch_soloq_auto.py 沿用
            json.dump({"key": key, "saved": time.time(), "permanent": perm},
                      open(os.path.join(HERE, "riot_key.local.json"), "w", encoding="utf-8"))
        except Exception as e:
            ST["log"] += f"（金鑰存檔失敗：{e}）\n"
        threading.Thread(target=run_update, args=(key,), daemon=True).start()
        self._json(200, {"started": True})

    def log_message(self, *a):
        pass  # 不記錄請求（避免金鑰進日誌）


if __name__ == "__main__":
    print(f"積分牌位更新服務啟動：http://127.0.0.1:{PORT}（關閉視窗即停止）")
    HTTPServer(("127.0.0.1", PORT), H).serve_forever()
