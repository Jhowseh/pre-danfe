"""Pré-DANFE Automático (V2): roda em segundo plano, com ícone perto do relógio.

A cada poucos segundos lê (só leitura) as NF-e ainda não transmitidas. Quando
uma nota aparece ou muda, gera o pré-DANFE na pasta configurada, com o nome
PreDANFE_<número>.pdf (sobrescrito a cada alteração da nota).

Para não pegar uma nota no meio da gravação, só gera quando a nota fica igual
em duas verificações seguidas.
"""
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

import tela_config
import tela_sobre
import tema
import util_app
from banco import CONGELADO, PASTA_LOG, ErroConfig, conexao_leitura, ler_config
from gerador import listar_pendentes, montar, nome_arquivo, pasta_saida, pdf_predanfe, salvar
from menu_bandeja import SEPARADOR, MenuBandeja, Opcao

NOME = "PreDANFE-Automatico"
CHAVE_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
ARQ_ESTADO = PASTA_LOG / "automatico_estado.json"

log = logging.getLogger("predanfe.auto")


# ---------------------------------------------------------- iniciar com o Windows

def comando_inicializacao():
    if CONGELADO:
        return f'"{sys.executable}"'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pythonw}" "{Path(__file__).resolve()}"'


def autostart_ativo():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHAVE_RUN) as k:
            winreg.QueryValueEx(k, NOME)
            return True
    except OSError:
        return False


def definir_autostart(ligar):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHAVE_RUN, 0, winreg.KEY_SET_VALUE) as k:
        if ligar:
            winreg.SetValueEx(k, NOME, 0, winreg.REG_SZ, comando_inicializacao())
        else:
            try:
                winreg.DeleteValue(k, NOME)
            except OSError:
                pass


# ---------------------------------------------------------- vigia do banco

class Vigia:
    def __init__(self):
        self.parar = threading.Event()
        self.agora = threading.Event()
        self.status = "Iniciando..."
        self.tipo_status = "neutro"  # cor da bolinha no menu: ok, erro ou neutro
        self.notificar = lambda texto: None
        self.ultimo_erro = None
        self.anterior = {}  # NFSCTR -> hash visto na verificação anterior
        self.estado = self._ler_estado()  # NFSCTR -> {"hash", "arquivo"} já gerados

    @staticmethod
    def _ler_estado():
        try:
            return json.loads(ARQ_ESTADO.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _gravar_estado(self):
        try:
            ARQ_ESTADO.parent.mkdir(parents=True, exist_ok=True)
            ARQ_ESTADO.write_text(json.dumps(self.estado), encoding="utf-8")
        except OSError:
            log.exception("Não gravou o estado")

    def intervalo(self):
        try:
            return max(3, ler_config().getint("automatico", "intervalo_segundos", fallback=10))
        except (ErroConfig, ValueError):
            return 10

    def rodar(self):
        log.info("Modo automático iniciado")
        while not self.parar.is_set():
            self.verificar()
            self.agora.wait(self.intervalo())
            self.agora.clear()

    def _mudar_status(self, texto, tipo="ok"):
        self.status = texto
        self.tipo_status = tipo

    def verificar(self):
        try:
            cfg = ler_config()
            pasta = pasta_saida(cfg)
            gerados, vistos = [], {}
            with conexao_leitura(cfg) as cur:
                pendentes = listar_pendentes(cur)
                for n in pendentes:
                    ctr = n["NFSCTR"]
                    xml, _chave, _avisos = montar(cur, ctr)
                    h = hashlib.sha1(xml.encode("utf-8")).hexdigest()
                    vistos[ctr] = h
                    feito = self.estado.get(ctr, {})
                    if feito.get("hash") == h and Path(feito.get("arquivo", "")).exists():
                        continue  # já gerado e a nota não mudou
                    if self.anterior.get(ctr) != h:
                        continue  # nota nova ou mudando: espera a próxima verificação
                    destino = salvar(pasta, nome_arquivo(n["NFSNUM"]), pdf_predanfe(xml))
                    self.estado[ctr] = {"hash": h, "arquivo": str(destino)}
                    gerados.append((int(n["NFSNUM"]), destino))
            self.anterior = vistos
            # esquece notas que deixaram de estar pendentes (transmitidas ou excluídas)
            self.estado = {k: v for k, v in self.estado.items() if k in vistos}
            self._gravar_estado()

            if self.ultimo_erro:
                log.info("Conexão normalizada")
                self.ultimo_erro = None
            self._mudar_status(f"{len(pendentes)} NF-e pendente(s) – verificado às {datetime.now():%H:%M:%S}")
            for num, destino in gerados:
                log.info("Gerado %s", destino)
                self.notificar(f"Pré-DANFE da NF-e {num} gerado.\n{destino.name}")
        except (Exception, ErroConfig) as e:  # noqa: BLE001 - o vigia não pode parar
            msg = str(e) or type(e).__name__
            self._mudar_status(f"Erro: {msg[:90]}", "erro")
            if msg != self.ultimo_erro:  # avisa uma vez por tipo de erro
                log.exception("Falha na verificação")
                self.notificar(f"Não foi possível ler o banco do SysPDV:\n{msg[:150]}")
                self.ultimo_erro = msg


# ---------------------------------------------------------- ícone perto do relógio

class IconeBandeja(pystray.Icon):
    """Dois cliques abrem a pasta; o botão direito abre o menu desenhado (menu_bandeja),
    no lugar do menu de texto do Windows."""

    WM_LBUTTONDBLCLK = 0x0203
    WM_RBUTTONUP = 0x0205

    def __init__(self, *args, ao_dois_cliques, ao_menu, **kwargs):
        self.ao_dois_cliques = ao_dois_cliques
        self.ao_menu = ao_menu
        super().__init__(*args, **kwargs)

    def _on_notify(self, wparam, lparam):
        if lparam == self.WM_LBUTTONDBLCLK:
            self.ao_dois_cliques()
        elif lparam == self.WM_RBUTTONUP:
            # o Windows só deixa o menu pegar o foco se o programa estiver em primeiro plano
            pystray_win32.SetForegroundWindow(self._hwnd)
            self.ao_menu()


# ---------------------------------------------------------- programa

def main():
    tema.ativar_dpi()
    util_app.configurar_log("automatico")
    util_app.identificar_app("PreDANFE.Automatico")
    root = tk.Tk()
    root.withdraw()
    util_app.aplicar_icone(root)
    util_app.registrar_erros_tk(root, log)

    if not util_app.uma_instancia(NOME):
        messagebox.showinfo("Pré-DANFE Automático",
                            "O Pré-DANFE Automático já está em execução (ícone perto do relógio).")
        return

    try:
        ler_config()
    except ErroConfig:
        if not tela_config.abrir(root, esperar=True):
            return
        if not autostart_ativo() and messagebox.askyesno(
                "Pré-DANFE Automático", "Iniciar o Pré-DANFE Automático junto com o Windows?"):
            definir_autostart(True)

    vigia = Vigia()
    fila = queue.Queue()

    def abrir_pasta():
        try:
            os.startfile(pasta_saida())
        except BaseException as e:  # noqa: BLE001
            vigia.notificar(f"Não abriu a pasta: {e}")

    def alternar_autostart():
        try:
            definir_autostart(not autostart_ativo())
        except OSError as e:
            vigia.notificar(f"Não alterou o início automático: {e}")

    menu = MenuBandeja(root)

    def opcoes_menu():
        return [
            Opcao("pasta", "Abrir pasta dos Pré-DANFEs",
                  "Mostra os PDFs gerados (o mesmo que dar dois cliques no ícone).", abrir_pasta),
            Opcao("atualizar", "Verificar agora",
                  f"Procura notas novas na hora, sem esperar os {vigia.intervalo()} segundos.", vigia.agora.set),
            Opcao("ajustes", "Configurações...", "Muda servidor, senha ou pasta dos PDFs.",
                  lambda: fila.put("config")),
            Opcao("seta", "Iniciar com o Windows", "Liga ou desliga o início automático.",
                  alternar_autostart, ligado=autostart_ativo),
            Opcao("info", "Sobre...", "Versão do programa e contato da PBtec.", lambda: fila.put("sobre")),
            SEPARADOR,
            Opcao("documento", "Sair", "Fecha o programa. Os PDFs param de ser gerados até abrir de novo.",
                  lambda: fila.put("sair")),
        ]

    icone = IconeBandeja(
        NOME,
        util_app.imagem_icone(64),
        "Pré-DANFE Automático",
        ao_dois_cliques=lambda: fila.put("pasta"),
        ao_menu=lambda: fila.put("menu"),
    )

    def notificar(texto):
        try:
            icone.notify(texto, "Pré-DANFE")
        except Exception:  # noqa: BLE001 - notificação é só aviso
            log.exception("Falha ao notificar")

    vigia.notificar = notificar
    icone.run_detached()
    threading.Thread(target=vigia.rodar, name="vigia", daemon=True).start()

    def processar_fila():
        try:
            while True:
                pedido = fila.get_nowait()
                if pedido == "menu":
                    menu.abrir(lambda: (vigia.status, vigia.tipo_status), opcoes_menu())
                elif pedido == "pasta":
                    abrir_pasta()
                elif pedido == "config":
                    tela_config.abrir(root, ao_salvar=vigia.agora.set)
                elif pedido == "sobre":
                    tela_sobre.abrir(root)
                elif pedido == "sair":
                    log.info("Encerrado pelo usuário")
                    menu.fechar()
                    vigia.parar.set()
                    vigia.agora.set()
                    icone.stop()
                    root.destroy()
                    return
        except queue.Empty:
            pass
        root.after(50, processar_fila)  # curto para o menu abrir logo após o clique

    root.after(50, processar_fila)
    root.mainloop()


if __name__ == "__main__":
    main()
