import ctypes
import logging
import threading
import tkinter as tk
from ctypes import wintypes
from logging.handlers import RotatingFileHandler

import theme
from database import LOG_DIR, RESOURCES

ICON_FILE = "predanfe.ico"


def setup_logging(name):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"{name}.log"
    handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    return path


def icon_image(size=64):
    img = theme.rounded_shape(size, size, max(2, round(size * 0.22)), gradient=theme.GRADIENT)
    side = round(size * 0.64)
    doc = theme.icon("document", "#FFFFFF", side)
    img.alpha_composite(doc, ((size - side) // 2, (size - side) // 2))
    return img


def save_ico(path):
    icon_image(256).save(path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def set_app_id(name):
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"PBtec.{name}")
    except (AttributeError, OSError):
        pass


def apply_icon(root):
    path = RESOURCES / "resources" / ICON_FILE
    try:
        if not path.exists():
            path = LOG_DIR / ICON_FILE
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            save_ico(path)
        root.iconbitmap(default=str(path))
        theme.WINDOW_ICON = path
        theme.set_taskbar_icon(root)
    except (OSError, tk.TclError):
        from PIL import ImageTk

        root._icon = ImageTk.PhotoImage(icon_image(64), master=root)
        root.iconphoto(True, root._icon)


def log_tk_errors(root, log):
    root.report_callback_exception = lambda kind, value, tb: log.error("Erro na janela", exc_info=(kind, value, tb))


def run_in_background(widget, work, on_done, interval=100):
    result = {}

    def run():
        try:
            result["value"] = work()
        except BaseException as e:
            result["error"] = e

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    def check():
        try:
            if thread.is_alive():
                widget.after(interval, check)
            else:
                on_done(result.get("value"), result.get("error"))
        except tk.TclError:
            pass

    widget.after(interval, check)


_mutex = None


def single_instance(name):
    global _mutex
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    _mutex = kernel32.CreateMutexW(None, False, f"Local\\{name}")
    return ctypes.get_last_error() != 183


def bring_to_front(title):
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.FindWindowW.restype = wintypes.HWND
    user32.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        return False
    user32.ShowWindow(hwnd, 9 if user32.IsIconic(hwnd) else 5)
    user32.SetForegroundWindow(hwnd)
    return True
