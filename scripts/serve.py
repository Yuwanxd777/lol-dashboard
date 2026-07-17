# -*- coding: utf-8 -*-
"""本機儀表板伺服器：提供靜態檔 + /update 端點。
按頁面右上角 🔄 會呼叫 /update 重抓資料（fetch_data.py + fetch_patches.py），完成後自動重整。
用法：雙擊 start.bat（會開伺服器並自動開啟瀏覽器）。關掉黑視窗即停止伺服器。
（一般網頁重整請按 F5，不會重抓。）"""
import http.server
import socketserver
import subprocess
import os
import sys
import threading
import webbrowser

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 專案根目錄（本腳本在 scripts\ 內）
PORT = 8770
PY = sys.executable or "python"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=HERE, **k)

    def end_headers(self):
        # 本機開發：一律不快取，避免改了 index.html 後瀏覽器仍載到舊版（F5 就會拿到最新）
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_POST(self):
        if self.path.rstrip("/") == "/update":
            code = 0
            try:
                for script in (os.path.join("scripts", "fetch_data.py"),
                               os.path.join("scripts", "fetch_patches.py")):
                    print(f"  執行 {script} ...")
                    r = subprocess.run([PY, script], cwd=HERE)
                    code = code or r.returncode
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode("utf-8"))
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(('{"ok":true,"code":%d}' % code).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *a):
        pass  # 靜音一般存取紀錄


def main():
    os.chdir(HERE)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", PORT), Handler) as httpd:
        url = f"http://127.0.0.1:{PORT}/index.html"
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
        print("=" * 52)
        print(f"  儀表板伺服器已啟動： {url}")
        print("  右上角 🔄 = 重抓最新資料；一般重整請按 F5。")
        print("  關掉此視窗即停止伺服器。")
        print("=" * 52)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
