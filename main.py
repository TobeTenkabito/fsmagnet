import sys
import io
import os
import time
import threading
import requests
import webview

from api.server import run_server, pump_dialogs
import api.server as srv

# 修复 Windows 打包后 GBK 编码问题
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BACKEND_PORT = 17878
BACKEND_URL  = f"http://127.0.0.1:{BACKEND_PORT}"

DEV_MODE     = not getattr(sys, 'frozen', False)
FRONTEND_URL = "http://localhost:5173" if DEV_MODE else BACKEND_URL


def wait_for_backend(timeout: int = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{BACKEND_URL}/api/download/list", timeout=1)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def start_backend():
    try:
        run_server(port=BACKEND_PORT)
    except Exception as e:
        with open(os.path.join(os.path.dirname(sys.executable), "crash.log"), "w", encoding="utf-8") as f:
            import traceback
            f.write(traceback.format_exc())
        print(f"[FATAL] 后端崩溃: {e}")
        input("按回车退出...")  # ← 让窗口停住


def main_thread_loop(window):
    while True:
        pump_dialogs()
        time.sleep(0.2)


def main():
    backend_thread = threading.Thread(target=start_backend, daemon=True)
    backend_thread.start()

    if not wait_for_backend():
        print("[ERROR] 后端启动超时，退出")
        sys.exit(1)

    window = webview.create_window(
        title="FSMagnet 极速下载器",
        url=FRONTEND_URL,
        width=1100,
        height=720,
        min_size=(800, 500),
        resizable=True,
        text_select=False,
        confirm_close=True,
    )

    srv.webview_window = window

    webview.start(
        func=main_thread_loop,
        args=(window,),
        debug=False,
        private_mode=False,
    )

    # webview 窗口关闭后，强制杀掉整个进程（含所有子线程）
    os._exit(0)


if __name__ == "__main__":
    main()
