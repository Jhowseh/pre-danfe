import hashlib
import json
import logging
import os
import queue
import sys
import threading
import tkinter as tk
import winreg
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

import pystray
from pystray._util import win32 as pystray_win32

import about_window
import app_utils
import config_window
import theme
from database import FROZEN, LOG_DIR, ConfigError, read_config, read_only_connection
from generator import build, file_name, list_pending, output_dir, predanfe_pdf, save
from tray_menu import SEPARATOR, MenuItem, TrayMenu

NAME = "PreDANFE-Automatico"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
STATE_FILE = LOG_DIR / "automatico_estado.json"

log = logging.getLogger("predanfe.auto")


def startup_command():
    if FROZEN:
        return f'"{sys.executable}"'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pythonw}" "{Path(__file__).resolve()}"'


def autostart_enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, NAME)
            return True
    except OSError:
        return False


def set_autostart(enabled):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, NAME, 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, NAME)
            except OSError:
                pass


class Watcher:
    def __init__(self):
        self.stop = threading.Event()
        self.now = threading.Event()
        self.status = "Iniciando..."
        self.status_kind = "neutral"
        self.notify = lambda text: None
        self.last_error = None
        self.previous = {}
        self.state = self._read_state()

    @staticmethod
    def _read_state():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _write_state(self):
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps(self.state), encoding="utf-8")
        except OSError:
            log.exception("Não gravou o estado")

    def interval(self):
        try:
            return max(3, read_config().getint("automatico", "intervalo_segundos", fallback=10))
        except (ConfigError, ValueError):
            return 10

    def run(self):
        log.info("Modo automático iniciado")
        while not self.stop.is_set():
            self.check()
            self.now.wait(self.interval())
            self.now.clear()

    def _set_status(self, text, kind="ok"):
        self.status = text
        self.status_kind = kind

    def check(self):
        try:
            cfg = read_config()
            folder = output_dir(cfg)
            generated, seen = [], {}
            with read_only_connection(cfg) as cur:
                pending = list_pending(cur)
                for inv in pending:
                    ctr = inv["NFSCTR"]
                    xml, _key, _warnings = build(cur, ctr)
                    h = hashlib.sha1(xml.encode("utf-8")).hexdigest()
                    seen[ctr] = h
                    done = self.state.get(ctr, {})
                    if done.get("hash") == h and Path(done.get("arquivo", "")).exists():
                        continue
                    if self.previous.get(ctr) != h:
                        continue
                    target = save(folder, file_name(inv["NFSNUM"]), predanfe_pdf(xml))
                    self.state[ctr] = {"hash": h, "arquivo": str(target)}
                    generated.append((int(inv["NFSNUM"]), target))
            self.previous = seen
            self.state = {k: v for k, v in self.state.items() if k in seen}
            self._write_state()

            if self.last_error:
                log.info("Conexão normalizada")
                self.last_error = None
            self._set_status(f"{len(pending)} NF-e pendente(s) – verificado às {datetime.now():%H:%M:%S}")
            for number, target in generated:
                log.info("Gerado %s", target)
                self.notify(f"Pré-DANFE da NF-e {number} gerado.\n{target.name}")
        except (Exception, ConfigError) as e:
            msg = str(e) or type(e).__name__
            self._set_status(f"Erro: {msg[:90]}", "error")
            if msg != self.last_error:
                log.exception("Falha na verificação")
                self.notify(f"Não foi possível ler o banco do SysPDV:\n{msg[:150]}")
                self.last_error = msg


class TrayIcon(pystray.Icon):
    WM_LBUTTONDBLCLK = 0x0203
    WM_RBUTTONUP = 0x0205

    def __init__(self, *args, on_double_click, on_menu, **kwargs):
        self.on_double_click = on_double_click
        self.on_menu = on_menu
        super().__init__(*args, **kwargs)

    def _on_notify(self, wparam, lparam):
        if lparam == self.WM_LBUTTONDBLCLK:
            self.on_double_click()
        elif lparam == self.WM_RBUTTONUP:
            pystray_win32.SetForegroundWindow(self._hwnd)
            self.on_menu()


def main():
    theme.enable_dpi_awareness()
    app_utils.setup_logging("automatico")
    app_utils.set_app_id("PreDANFE.Automatico")
    root = tk.Tk()
    root.withdraw()
    app_utils.apply_icon(root)
    app_utils.log_tk_errors(root, log)

    if not app_utils.single_instance(NAME):
        messagebox.showinfo("Pré-DANFE Automático",
                            "O Pré-DANFE Automático já está em execução (ícone perto do relógio).")
        return

    try:
        read_config()
    except ConfigError:
        if not config_window.show(root, wait=True):
            return
        if not autostart_enabled() and messagebox.askyesno(
                "Pré-DANFE Automático", "Iniciar o Pré-DANFE Automático junto com o Windows?"):
            set_autostart(True)

    watcher = Watcher()
    requests = queue.Queue()

    def open_folder():
        try:
            os.startfile(output_dir())
        except BaseException as e:
            watcher.notify(f"Não abriu a pasta: {e}")

    def toggle_autostart():
        try:
            set_autostart(not autostart_enabled())
        except OSError as e:
            watcher.notify(f"Não alterou o início automático: {e}")

    menu = TrayMenu(root)

    def menu_items():
        return [
            MenuItem("folder", "Abrir pasta dos Pré-DANFEs",
                     "Mostra os PDFs gerados (o mesmo que dar dois cliques no ícone).", open_folder),
            MenuItem("refresh", "Verificar agora",
                     f"Procura notas novas na hora, sem esperar os {watcher.interval()} segundos.", watcher.now.set),
            MenuItem("sliders", "Configurações...", "Muda servidor, senha ou pasta dos PDFs.",
                     lambda: requests.put("config")),
            MenuItem("arrow", "Iniciar com o Windows", "Liga ou desliga o início automático.",
                     toggle_autostart, is_on=autostart_enabled),
            MenuItem("info", "Sobre...", "Versão do programa e contato da PBtec.", lambda: requests.put("about")),
            SEPARATOR,
            MenuItem("document", "Sair", "Fecha o programa. Os PDFs param de ser gerados até abrir de novo.",
                     lambda: requests.put("quit")),
        ]

    icon = TrayIcon(
        NAME,
        app_utils.icon_image(64),
        "Pré-DANFE Automático",
        on_double_click=lambda: requests.put("folder"),
        on_menu=lambda: requests.put("menu"),
    )

    def notify(text):
        try:
            icon.notify(text, "Pré-DANFE")
        except Exception:
            log.exception("Falha ao notificar")

    watcher.notify = notify
    icon.run_detached()
    threading.Thread(target=watcher.run, name="watcher", daemon=True).start()

    def process_requests():
        try:
            while True:
                request = requests.get_nowait()
                if request == "menu":
                    menu.show(lambda: (watcher.status, watcher.status_kind), menu_items())
                elif request == "folder":
                    open_folder()
                elif request == "config":
                    config_window.show(root, on_save=watcher.now.set)
                elif request == "about":
                    about_window.show(root)
                elif request == "quit":
                    log.info("Encerrado pelo usuário")
                    menu.close()
                    watcher.stop.set()
                    watcher.now.set()
                    icon.stop()
                    root.destroy()
                    return
        except queue.Empty:
            pass
        root.after(50, process_requests)

    root.after(50, process_requests)
    root.mainloop()


if __name__ == "__main__":
    main()
