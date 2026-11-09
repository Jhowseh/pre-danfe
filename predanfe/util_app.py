"""Apoio comum aos programas de janela: log, ícone e instância única."""
import ctypes
import logging
import threading
import tkinter as tk
from ctypes import wintypes
from logging.handlers import RotatingFileHandler

import tema
from banco import PASTA_LOG, RECURSOS

ARQ_ICONE = "predanfe.ico"  # gerado pelo build.py em recursos/ e usado também como ícone do .exe


def configurar_log(nome):
    PASTA_LOG.mkdir(parents=True, exist_ok=True)
    arq = PASTA_LOG / f"{nome}.log"
    h = RotatingFileHandler(arq, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    raiz.addHandler(h)
    return arq


def imagem_icone(tam=64):
    """Quadrado arredondado em degradê ciano→violeta (como a barra dos assets) com o ícone de documento."""
    img = tema.forma_arredondada(tam, tam, max(2, round(tam * 0.22)), degrade=tema.DEGRADE)
    lado = round(tam * 0.64)
    doc = tema.icone("documento", "#FFFFFF", lado)
    img.alpha_composite(doc, ((tam - lado) // 2, (tam - lado) // 2))
    return img


def salvar_ico(caminho):
    imagem_icone(256).save(caminho, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def identificar_app(nome):
    """Identidade própria na barra de tarefas (chamar antes de criar a janela).

    Sem ela o Windows agrupa a janela pelo programa que a abriu (python.exe ou o Tk
    dentro do .exe) e mostra o ícone dele (a pena do Tk) em vez do nosso.
    """
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"PBtec.{nome}")
    except (AttributeError, OSError):
        pass


def aplicar_icone(root):
    """Põe o mesmo .ico do executável em todas as janelas do programa (título e barra de tarefas).

    O .ico tem todos os tamanhos prontos, então o Windows usa o desenho certo em cada lugar,
    em vez de reduzir uma imagem só. As janelas preparadas por `Tema.preparar_janela` também
    recebem o ícone direto (veja `tema.icone_na_barra`).
    """
    caminho = RECURSOS / "recursos" / ARQ_ICONE
    try:
        if not caminho.exists():  # rodando do código-fonte sem ter feito o build
            caminho = PASTA_LOG / ARQ_ICONE
            PASTA_LOG.mkdir(parents=True, exist_ok=True)
            salvar_ico(caminho)
        root.iconbitmap(default=str(caminho))
        tema.ICONE_JANELAS = caminho
        tema.icone_na_barra(root)
    except (OSError, tk.TclError):
        from PIL import ImageTk

        root._icone = ImageTk.PhotoImage(imagem_icone(64), master=root)
        root.iconphoto(True, root._icone)


def registrar_erros_tk(root, log):
    """Erros dentro das janelas vão para o log (no .exe não há console para mostrá-los)."""
    root.report_callback_exception = lambda tipo, valor, tb: log.error("Erro na janela", exc_info=(tipo, valor, tb))


def em_segundo_plano(widget, trabalho, ao_terminar, intervalo=100):
    """Roda `trabalho()` fora da janela (banco lento não congela a tela) e depois
    chama `ao_terminar(valor, erro)` de volta na janela."""
    resultado = {}

    def rodar():
        try:
            resultado["valor"] = trabalho()
        except BaseException as e:  # noqa: BLE001 - devolvido para a janela tratar
            resultado["erro"] = e

    fio = threading.Thread(target=rodar, daemon=True)
    fio.start()

    def conferir():
        try:
            if fio.is_alive():
                widget.after(intervalo, conferir)
            else:
                ao_terminar(resultado.get("valor"), resultado.get("erro"))
        except tk.TclError:
            pass  # janela fechada enquanto esperava

    widget.after(intervalo, conferir)


_mutex = None


def uma_instancia(nome):
    """False se o programa já está aberto nesta sessão do Windows."""
    global _mutex
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    _mutex = kernel32.CreateMutexW(None, False, f"Local\\{nome}")  # fica aberto até o programa fechar
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


def trazer_para_frente(titulo):
    """Mostra a janela já aberta com este título (restaura se estiver minimizada)."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.FindWindowW.restype = wintypes.HWND
    user32.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
    hwnd = user32.FindWindowW(None, titulo)
    if not hwnd:
        return False
    user32.ShowWindow(hwnd, 9 if user32.IsIconic(hwnd) else 5)  # SW_RESTORE / SW_SHOW
    user32.SetForegroundWindow(hwnd)
    return True
