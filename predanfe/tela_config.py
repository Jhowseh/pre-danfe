"""Tela de configuração (servidor, banco, senha, pasta dos PDFs), usada pelos dois programas."""
import configparser
import tkinter as tk
from tkinter import filedialog

import tema as tm
import util_app
from banco import ARQ_CONFIG, conexao_leitura, padroes_do_syspdv, salvar_config

LARGURA = 520


def config_atual():
    """Config do arquivo, completada com o que o SysPDV desta máquina usa."""
    cfg = configparser.ConfigParser()
    if ARQ_CONFIG.exists():
        cfg.read(ARQ_CONFIG, encoding="utf-8")
    for secao in ("banco", "saida", "automatico"):
        if not cfg.has_section(secao):
            cfg.add_section(secao)
    for chave, valor in padroes_do_syspdv().items():
        if not cfg.get("banco", chave, fallback="").strip():
            cfg.set("banco", chave, valor)
    for secao, chave, valor in (("banco", "senha", ""), ("saida", "pasta_pdf", "pdf"),
                                ("automatico", "intervalo_segundos", "10")):
        if not cfg.has_option(secao, chave):
            cfg.set(secao, chave, valor)
    return cfg


_aberta = None  # só uma tela de configuração por vez


def _trazer_para_frente(janela):
    janela.deiconify()
    janela.lift()
    janela.attributes("-topmost", True)
    janela.after(300, lambda: janela.winfo_exists() and janela.attributes("-topmost", False))
    janela.focus_force()


def abrir(master=None, tema=None, ao_salvar=None, esperar=False):
    """Mostra a tela de configuração.

    Ela é uma janela independente (com botão próprio na barra de tarefas) e não
    bloqueia a janela principal. `ao_salvar` é chamado depois de salvar.
    Com esperar=True (ou sem master), só retorna quando a tela fecha: True se salvou.
    """
    global _aberta
    if _aberta is not None and _aberta.winfo_exists():
        _trazer_para_frente(_aberta)
        if esperar and master:
            master.wait_window(_aberta)
        return _aberta

    cfg = config_atual()
    janela = tk.Toplevel(master) if master else tk.Tk()
    _aberta = janela
    t = tema or tm.Tema(janela)
    t.preparar_janela(janela, "Pré-DANFE – Configuração")
    W = t.px(LARGURA)
    gap = t.px(16)

    corpo = t.frame(janela)
    corpo.pack(padx=t.px(28), pady=(t.px(22), t.px(26)))
    tm.Cabecalho(corpo, t, W, "Configuração", "Conexão com o banco",
                 "O Pré-DANFE só lê o banco do SysPDV. Nunca grava nada.", com_status=False).pack(anchor="w")

    campos = {}

    def campo(pai, secao, chave, rotulo, largura, **kw):
        caixa = t.frame(pai)
        t.label(caixa, rotulo, "pequeno", "suave").pack(anchor="w", pady=(0, t.px(4)))
        c = tm.Campo(caixa, t, largura, valor=cfg.get(secao, chave, fallback=""), **kw)
        c.pack(anchor="w")
        campos[(secao, chave)] = c
        return caixa

    def linha(*itens):
        f = t.frame(corpo)
        f.pack(anchor="w", pady=(t.px(12), 0))
        for i, (secao, chave, rotulo, largura, kw) in enumerate(itens):
            campo(f, secao, chave, rotulo, largura, **kw).pack(side="left", padx=(0 if i == 0 else gap, 0))
        return f

    tm.titulo_secao(corpo, t, "banco", "Banco de dados do SysPDV").pack(anchor="w", pady=(t.px(18), 0))
    linha(("banco", "host", "Servidor", 360, {}), ("banco", "porta", "Porta", 144, {}))
    linha(("banco", "arquivo", "Arquivo do banco", 520, {}))
    linha(("banco", "usuario", "Usuário", 252, {}), ("banco", "senha", "Senha", 252, {"show": "•"}))

    tm.titulo_secao(corpo, t, "pasta", "Onde salvar os PDFs").pack(anchor="w", pady=(t.px(22), 0))
    f = linha(("saida", "pasta_pdf", "Pasta dos PDFs", 464, {}))

    def procurar():
        p = filedialog.askdirectory(parent=janela, title="Pasta dos Pré-DANFEs")
        if p:
            campos[("saida", "pasta_pdf")].set(p)

    tm.Botao(f, t, "", procurar, icone="pasta", largura=44).pack(side="left", anchor="s", padx=(t.px(12), 0))

    resultado_txt = t.label(corpo, "", "pequeno", "suave", wraplength=W, justify="left", anchor="w")
    resultado_txt.pack(anchor="w", fill="x", pady=(t.px(14), 0))

    resultado = {"salvou": False}

    def cfg_da_tela():
        novo = config_atual()
        for (secao, chave), c in campos.items():
            novo.set(secao, chave, c.get())
        return novo

    def aviso(texto, cor):
        resultado_txt.config(text=texto, fg=t.c[cor])

    testando = {"sim": False}

    def testar():
        if testando["sim"]:
            return
        testando["sim"] = True
        aviso("Testando a conexão…", "suave")
        janela.config(cursor="watch")
        cfg_teste = cfg_da_tela()

        def contar():
            with conexao_leitura(cfg_teste) as cur:
                cur.execute("SELECT COUNT(*) FROM NOTAFISCAL")
                return cur.fetchone()[0]

        def terminou(total, erro):
            testando["sim"] = False
            janela.config(cursor="")
            if erro is None:
                aviso(f"Conectou! {total} notas fiscais no banco.", "verde")
            else:
                aviso(f"Não conectou: {erro}", "vermelho")

        util_app.em_segundo_plano(janela, contar, terminou)

    def salvar():
        novo = cfg_da_tela()
        if not novo.get("banco", "senha"):
            aviso("Preencha a senha do banco.", "amarelo")
            campos[("banco", "senha")].focar()
            return
        try:
            salvar_config(novo)
        except OSError as e:
            aviso(f"Não foi possível gravar {ARQ_CONFIG}: {e}", "vermelho")
            return
        resultado["salvou"] = True
        janela.destroy()
        if ao_salvar:
            ao_salvar()

    botoes = t.frame(corpo)
    botoes.pack(fill="x", pady=(t.px(16), 0))
    tm.Botao(botoes, t, "Salvar", salvar, primario=True).pack(side="right")
    tm.Botao(botoes, t, "Cancelar", janela.destroy).pack(side="right", padx=(0, t.px(10)))
    tm.Botao(botoes, t, "Testar conexão", testar, icone="banco").pack(side="left")

    def ao_fechar(evento):
        global _aberta
        if evento.widget is janela:
            _aberta = None

    janela.bind("<Destroy>", ao_fechar)
    janela.bind("<Return>", lambda _e: salvar())
    janela.bind("<Escape>", lambda _e: janela.destroy())
    _trazer_para_frente(janela)
    if not cfg.get("banco", "senha", fallback=""):
        janela.after(200, campos[("banco", "senha")].focar)
    # Sem "transient"/"grab": se a janela principal for minimizada, esta não
    # some junto, e a principal nunca fica presa esperando por ela.
    if master is None:
        janela.mainloop()
        return resultado["salvou"]
    if esperar:
        master.wait_window(janela)
        return resultado["salvou"]
    return janela
