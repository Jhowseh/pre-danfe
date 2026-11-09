"""Configuração e conexão SOMENTE LEITURA com o banco do SysPDV.

Toda consulta roda numa transação READ ONLY: o próprio Firebird recusa
qualquer INSERT/UPDATE/DELETE nela. Ao final, a transação é desfeita
(rollback), nunca confirmada.
"""
import leve  # noqa: F401 - antes do firebird-driver (economiza memória)

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

CONGELADO = getattr(sys, "frozen", False)  # rodando como .exe (PyInstaller)
# Pasta do programa: onde ficam config.ini e a pasta de PDFs.
PASTA = Path(sys.executable).parent if CONGELADO else Path(__file__).resolve().parent
# Arquivos embutidos no .exe (fbclient); fora do .exe, a pasta do código.
RECURSOS = Path(getattr(sys, "_MEIPASS", PASTA))
ARQ_CONFIG = PASTA / "config.ini"
PASTA_LOG = Path(os.environ.get("LOCALAPPDATA", PASTA)) / "PreDANFE"

CHAVE_REGISTRO_SYSPDV = r"SOFTWARE\WOW6432Node\Syspdv_server\UniConnection"


class ErroConfig(SystemExit):
    """Configuração ausente ou incompleta (na linha de comando, sai com a mensagem)."""


def padroes_do_syspdv():
    """Servidor e banco que o SysPDV desta máquina usa (registro do Windows)."""
    valores = {"host": "127.0.0.1", "porta": "3050", "arquivo": r"C:\Syspdv\syspdv_srv.fdb", "usuario": "SYSDBA"}
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, CHAVE_REGISTRO_SYSPDV) as k:
            for nome, campo in (("Server", "host"), ("Database", "arquivo"), ("Port", "porta")):
                try:
                    v = str(winreg.QueryValueEx(k, nome)[0]).strip()
                except OSError:
                    continue
                if v and v != "0":
                    valores[campo] = v
    except OSError:
        pass
    return valores


def ler_config(exigir_senha=True):
    if not ARQ_CONFIG.exists():
        raise ErroConfig(f"Falta o arquivo de configuração {ARQ_CONFIG}.")
    cfg = configparser.ConfigParser()
    cfg.read(ARQ_CONFIG, encoding="utf-8")
    if not cfg.has_section("banco"):
        raise ErroConfig(f"O arquivo {ARQ_CONFIG} não tem a seção [banco].")
    if exigir_senha and not cfg.get("banco", "senha", fallback="").strip():
        raise ErroConfig(f"Preencha a senha do banco em {ARQ_CONFIG}.")
    return cfg


def salvar_config(cfg):
    # fbclient é opcional: só fica no arquivo se alguém apontou uma DLL.
    if cfg.has_section("banco") and not cfg.get("banco", "fbclient", fallback="").strip():
        cfg.remove_option("banco", "fbclient")
    with open(ARQ_CONFIG, "w", encoding="utf-8") as f:
        cfg.write(f)


def localizar_fbclient(cfg):
    """fbclient.dll 64 bits: o do config.ini, o embutido no programa, ou o do Firebird 5."""
    candidatos = []
    escolhido = cfg.get("banco", "fbclient", fallback="").strip()
    if escolhido:
        candidatos.append(Path(escolhido))
    candidatos += [
        RECURSOS / "fbclient" / "fbclient.dll",
        PASTA / "fbclient" / "fbclient.dll",
        Path(r"C:\Program Files\Firebird\Firebird_5_0\fbclient.dll"),
    ]
    for c in candidatos:
        if c.exists():
            return c
    raise ErroConfig("Não encontrei o fbclient.dll de 64 bits.")


_cliente_carregado = None
_trava_cliente = threading.Lock()


def _preparar_cliente(cfg):
    global _cliente_carregado
    with _trava_cliente:
        if _cliente_carregado is None:
            dll = localizar_fbclient(cfg)
            os.add_dll_directory(str(dll.parent))  # dependências do fbclient
            driver_config.fb_client_library.value = str(dll)
            # tpb() carrega o fbclient; feito aqui, dentro da trava
            tpb(Isolation.READ_COMMITTED_RECORD_VERSION, access_mode=TraAccessMode.READ)
            _cliente_carregado = dll


@contextmanager
def conexao_leitura(cfg=None):
    """Uso: with conexao_leitura() as cur: cur.execute(...)"""
    cfg = cfg or ler_config()
    b = cfg["banco"]
    _preparar_cliente(cfg)
    # Só depois de escolher a DLL: tpb() já carrega o fbclient.
    tpb_leitura = tpb(Isolation.READ_COMMITTED_RECORD_VERSION, access_mode=TraAccessMode.READ)

    porta = b.get("porta", "3050").strip() or "3050"
    dsn = f"{b['host']}/{porta}:{b['arquivo']}"
    con = connect(dsn, user=b["usuario"], password=b["senha"], charset="ISO8859_1")
    try:
        tm = con.transaction_manager(tpb_leitura, DefaultAction.ROLLBACK)
        try:
            yield tm.cursor()
        finally:
            if tm.is_active():
                tm.rollback()
            tm.close()
    finally:
        con.close()


def linhas_dict(cur):
    """Converte o resultado do cursor em lista de dicionários, com texto sem espaços sobrando."""
    nomes = [d[0] for d in cur.description]
    saida = []
    for linha in cur.fetchall():
        reg = {}
        for nome, valor in zip(nomes, linha):
            reg[nome] = valor.strip() if isinstance(valor, str) else valor
        saida.append(reg)
    return saida
