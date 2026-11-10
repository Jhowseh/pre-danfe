import lazy_imports

import configparser
import os
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

from firebird.driver import (
    DefaultAction,
    Isolation,
    TraAccessMode,
    connect,
    driver_config,
    tpb,
)

FROZEN = getattr(sys, "frozen", False)
APP_DIR = Path(sys.executable).parent if FROZEN else Path(__file__).resolve().parent
RESOURCES = Path(getattr(sys, "_MEIPASS", APP_DIR))
CONFIG_FILE = APP_DIR / "config.ini"
LOG_DIR = Path(os.environ.get("LOCALAPPDATA", APP_DIR)) / "PreDANFE"

SYSPDV_REGISTRY_KEY = r"SOFTWARE\WOW6432Node\Syspdv_server\UniConnection"


class ConfigError(SystemExit):
    pass


def syspdv_defaults():
    values = {"host": "127.0.0.1", "porta": "3050", "arquivo": r"C:\Syspdv\syspdv_srv.fdb", "usuario": "SYSDBA"}
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, SYSPDV_REGISTRY_KEY) as key:
            for name, field in (("Server", "host"), ("Database", "arquivo"), ("Port", "porta")):
                try:
                    value = str(winreg.QueryValueEx(key, name)[0]).strip()
                except OSError:
                    continue
                if value and value != "0":
                    values[field] = value
    except OSError:
        pass
    return values


def read_config(require_password=True):
    if not CONFIG_FILE.exists():
        raise ConfigError(f"Falta o arquivo de configuração {CONFIG_FILE}.")
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_FILE, encoding="utf-8")
    if not cfg.has_section("banco"):
        raise ConfigError(f"O arquivo {CONFIG_FILE} não tem a seção [banco].")
    if require_password and not cfg.get("banco", "senha", fallback="").strip():
        raise ConfigError(f"Preencha a senha do banco em {CONFIG_FILE}.")
    return cfg


def save_config(cfg):
    if cfg.has_section("banco") and not cfg.get("banco", "fbclient", fallback="").strip():
        cfg.remove_option("banco", "fbclient")
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        cfg.write(f)


def find_fbclient(cfg):
    candidates = []
    chosen = cfg.get("banco", "fbclient", fallback="").strip()
    if chosen:
        candidates.append(Path(chosen))
    candidates += [
        RESOURCES / "fbclient" / "fbclient.dll",
        APP_DIR / "fbclient" / "fbclient.dll",
        Path(r"C:\Program Files\Firebird\Firebird_5_0\fbclient.dll"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise ConfigError("Não encontrei o fbclient.dll de 64 bits.")


_loaded_client = None
_client_lock = threading.Lock()


def _prepare_client(cfg):
    global _loaded_client
    with _client_lock:
        if _loaded_client is None:
            dll = find_fbclient(cfg)
            os.add_dll_directory(str(dll.parent))
            driver_config.fb_client_library.value = str(dll)
            tpb(Isolation.READ_COMMITTED_RECORD_VERSION, access_mode=TraAccessMode.READ)
            _loaded_client = dll


@contextmanager
def read_only_connection(cfg=None):
    cfg = cfg or read_config()
    db = cfg["banco"]
    _prepare_client(cfg)
    read_tpb = tpb(Isolation.READ_COMMITTED_RECORD_VERSION, access_mode=TraAccessMode.READ)

    port = db.get("porta", "3050").strip() or "3050"
    dsn = f"{db['host']}/{port}:{db['arquivo']}"
    con = connect(dsn, user=db["usuario"], password=db["senha"], charset="ISO8859_1")
    try:
        tm = con.transaction_manager(read_tpb, DefaultAction.ROLLBACK)
        try:
            yield tm.cursor()
        finally:
            if tm.is_active():
                tm.rollback()
            tm.close()
    finally:
        con.close()


def rows_as_dicts(cur):
    names = [d[0] for d in cur.description]
    rows = []
    for row in cur.fetchall():
        record = {}
        for name, value in zip(names, row):
            record[name] = value.strip() if isinstance(value, str) else value
        rows.append(record)
    return rows
