"""Tela "Sobre" do Pré-DANFE.

- PreDANFE (V1): `Painel`, mostrado dentro da janela principal, no lugar da lista.
- Automático (V2): `abrir`, janela própria (ele não tem janela principal, só o ícone perto do relógio).
"""
import tkinter as tk

import tema as tm
from versao import DESENVOLVIMENTO, EMPRESA, TELEFONE, VERSAO

LARGURA = 380
ALTURA_CARTAO = 198
_aberta = None  # só uma janela Sobre por vez


def cartao_dados(pai, t, largura):
    """Cartão com empresa, telefone e quem desenvolveu."""
    W, H = t.px(largura), t.px(ALTURA_CARTAO)
    cartao = tk.Canvas(pai, width=W, height=H, bg=t.c["bg"], highlightthickness=0, bd=0)
    fundo = t.foto(("sobre-cartao", W, t.escuro),
                   lambda: tm.forma_arredondada(W, H, t.px(12), t.c["card"], t.c["borda"]))
    cartao.create_image(0, 0, image=fundo, anchor="nw")
    m, y = t.px(18), t.px(18)
    f = t.fontes

    def linha_icone(icone, texto, fonte, y):
        cartao.create_image(m, y, image=t.icone(icone, tm.VIOLETA, 18), anchor="w")
        cartao.create_text(m + t.px(28), y, text=texto, anchor="w", font=f[fonte], fill=t.c["texto"])

    linha_icone("camadas", EMPRESA, "forte", y + t.px(10))
    linha_icone("telefone", TELEFONE, "corpo", y + t.px(40))
    cartao.create_line(m, y + t.px(66), W - m, y + t.px(66), fill=t.c["borda"])
    cartao.create_text(m, y + t.px(86), text="DESENVOLVIMENTO E ANÁLISE", anchor="w",
                       font=f["rotulo"], fill=t.c["suave"])
    for i, nome in enumerate(DESENVOLVIMENTO):
        linha_icone("usuario", nome, "corpo", y + t.px(114 + 30 * i))
    return cartao


def _rotulo_versao(pai, t):
    return t.label(pai, " ".join(f"VERSÃO {VERSAO}"), "rotulo", "suave")


class Painel(tk.Frame):
    """Sobre dentro da janela principal: título com botão Voltar, versão e o cartão de dados."""

    def __init__(self, pai, t, largura, ao_voltar):
        super().__init__(pai, bg=t.c["bg"])
        topo = t.frame(self)
        topo.pack(fill="x", pady=(t.px(18), t.px(10)))
        tm.titulo_secao(topo, t, "info", "Sobre o Pré-DANFE").pack(side="left")
        tm.Botao(topo, t, "Voltar", ao_voltar, altura=32).pack(side="right")
        _rotulo_versao(self, t).pack(anchor="w", pady=(0, t.px(10)))
        cartao_dados(self, t, largura).pack(anchor="w")


def abrir(master, tema=None):
    """Mostra a janela Sobre (independente, não bloqueia o programa)."""
    global _aberta
    if _aberta is not None and _aberta.winfo_exists():
        _aberta.deiconify()
        _aberta.lift()
        _aberta.focus_force()
        return _aberta

    janela = tk.Toplevel(master)
    _aberta = janela
    t = tema or tm.Tema(janela)
    t.preparar_janela(janela, "Sobre o Pré-DANFE")
    W = t.px(LARGURA)

    corpo = t.frame(janela)
    corpo.pack(padx=t.px(32), pady=(t.px(26), t.px(24)))

    # logo, nome e versão
    logo = t.logo(92)
    if logo is not None:
        tk.Label(corpo, image=logo, bg=t.c["bg"]).pack()
    t.label(corpo, "Pré-DANFE", "titulo").pack(pady=(t.px(10), 0))
    t.label(corpo, "Veja o DANFE da nota antes de transmitir no SysPDV.", "corpo", "suave",
            wraplength=W, justify="center").pack(pady=(t.px(2), 0))
    barra = t.foto(("barra-sobre", t.px(56)), lambda: tm.forma_arredondada(t.px(56), max(2, t.px(3)),
                                                                         max(1, t.px(1.5)), degrade=tm.DEGRADE))
    tk.Label(corpo, image=barra, bg=t.c["bg"]).pack(pady=(t.px(10), t.px(6)))
    _rotulo_versao(corpo, t).pack()

    cartao_dados(corpo, t, LARGURA).pack(pady=(t.px(18), 0))
    tm.Botao(corpo, t, "Fechar", janela.destroy, primario=True, largura=LARGURA).pack(pady=(t.px(18), 0))

    def ao_fechar(evento):
        global _aberta
        if evento.widget is janela:
            _aberta = None

    janela.bind("<Destroy>", ao_fechar)
    janela.bind("<Escape>", lambda _e: janela.destroy())
    janela.bind("<Return>", lambda _e: janela.destroy())
    janela.lift()
    janela.attributes("-topmost", True)
    janela.after(300, lambda: janela.winfo_exists() and janela.attributes("-topmost", False))
    janela.focus_force()
    return janela
