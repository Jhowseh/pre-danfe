"""Pré-DANFE (V1): o usuário digita o número da NF-e e clica para gerar o PDF."""
import logging
import os
import time
import tkinter as tk
from tkinter import messagebox

import tela_config
import tela_sobre
import tema as tm
import util_app
from banco import ErroConfig, conexao_leitura, ler_config
from gerador import buscar_por_numero, listar_pendentes, montar, nome_arquivo, pasta_saida, pdf_predanfe, salvar

log = logging.getLogger("predanfe")

TITULO = "Pré-DANFE – SysPDV"
LARGURA = 540  # largura do conteúdo, em pixels "de 100%"
DURACAO_TRANSICAO = 240  # ms da troca entre a tela principal e o Sobre


def moeda(v):
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class ListaNotas(tk.Canvas):
    """NF-e pendentes em cartões (como os cartões de projeto dos assets). Clique gera o PDF."""

    ALTURA_LINHA, ESPACO = 64, 8
    PASSO_RODA = 56  # px "de 100%" por clique da roda do mouse
    SUAVIDADE = 0.22  # fração do caminho que falta percorrida a cada ~16 ms

    def __init__(self, pai, tema, largura, linhas_visiveis, ao_escolher):
        t = self.t = tema
        self.w = t.px(largura)
        self.hl, self.esp = t.px(self.ALTURA_LINHA), t.px(self.ESPACO)
        altura = int(self.hl * linhas_visiveis + self.esp * (linhas_visiveis - 1))
        super().__init__(pai, width=self.w, height=altura, bg=t.c["bg"], highlightthickness=0, bd=0,
                         yscrollincrement=1)
        self.ao_escolher = ao_escolher
        r = t.px(12)
        self.img_normal = t.foto(("ln", self.w, self.hl, t.escuro),
                                 lambda: tm.forma_arredondada(self.w, self.hl, r, t.c["card"], t.c["borda"]))
        self.img_sobre = t.foto(("lh", self.w, self.hl, t.escuro),
                                lambda: tm.forma_arredondada(self.w, self.hl, r, t.c["hover"], t.c["link"]))
        # rolagem animada: a roda só muda o destino; _animar desliza até ele
        self._altura_total = 0
        self._pos = 0.0  # topo visível, em px (fracionário, para não "travar" em arredondamentos)
        self._alvo = 0.0
        self._anim = None
        self._ultimo_quadro = 0.0
        self.bind("<Enter>", lambda _e: self.bind_all("<MouseWheel>", self._rolar))
        self.bind("<Leave>", lambda _e: self.unbind_all("<MouseWheel>"))

    def _maximo(self):
        return max(0, self._altura_total - self.winfo_height())

    def _rolar(self, evento):
        maximo = self._maximo()
        if maximo <= 0:
            return
        # touchpads mandam deltas pequenos; somar no destino deixa tudo proporcional
        self._alvo = min(max(self._alvo - evento.delta / 120 * self.t.px(self.PASSO_RODA), 0), maximo)
        if self._anim is None:
            self._ultimo_quadro = time.perf_counter()
            self._animar()

    def _animar(self):
        agora = time.perf_counter()
        dt = max(agora - self._ultimo_quadro, 0.001)
        self._ultimo_quadro = agora
        # mesma velocidade independentemente do intervalo real entre quadros
        fator = 1 - (1 - self.SUAVIDADE) ** (dt / 0.016)
        falta = self._alvo - self._pos
        if abs(falta) < 0.5:
            self._pos = self._alvo
            self._anim = None
        else:
            self._pos += falta * fator
            self._anim = self.after(8, self._animar)
        self.yview_moveto(self._pos / self._altura_total)

    def _reiniciar_rolagem(self, altura_total):
        if self._anim is not None:
            self.after_cancel(self._anim)
            self._anim = None
        self._altura_total = altura_total
        self._pos = self._alvo = 0.0
        self.yview_moveto(0)

    def _cortar(self, texto, fonte, largura):
        if fonte.measure(texto) <= largura:
            return texto
        while texto and fonte.measure(texto + "…") > largura:
            texto = texto[:-1]
        return texto + "…"

    def _ajustar_altura(self, linhas):
        """Altura acompanha a quantidade de notas (de 1 a 4 cartões; acima disso, rola)."""
        linhas = min(linhas, 4.5)
        self.config(height=int(self.hl * linhas + self.esp * (max(1, linhas) - 1)))

    def mensagem(self, texto, cor="suave", icone="camadas"):
        self.delete("all")
        self._ajustar_altura(1.8)
        h = int(self["height"])
        self._reiniciar_rolagem(h)
        caixa = self.t.foto(("lv", self.w, h, self.t.escuro),
                            lambda: tm.forma_arredondada(self.w, h, self.t.px(12), self.t.c["bg"], self.t.c["borda"]))
        self.create_image(0, 0, image=caixa, anchor="nw")
        self.create_image(self.w // 2, h // 2 - self.t.px(16), image=self.t.icone(icone, self.t.c["fraco"], 26))
        self.create_text(self.w // 2, h // 2 + self.t.px(16), text=texto, font=self.t.fontes["corpo"],
                         fill=self.t.c[cor], width=self.w - self.t.px(40), justify="center")
        self.config(scrollregion=(0, 0, self.w, h))

    def mostrar(self, notas):
        if not notas:
            self.mensagem("Nenhuma NF-e aguardando transmissão.")
            return
        t, f = self.t, self.t.fontes
        self.delete("all")
        self._ajustar_altura(len(notas) if len(notas) <= 4 else 4.5)
        m = t.px(16)
        for i, n in enumerate(notas):
            y = i * (self.hl + self.esp)
            tag = f"l{i}"
            num = int(n["NFSNUM"])
            fundo = self.create_image(0, y, image=self.img_normal, anchor="nw", tags=(tag,))
            self.create_image(m, y + self.hl // 2, image=t.icone("documento", t.c["suave"], 20), anchor="w", tags=(tag,))
            x = m + t.px(32)
            self.create_text(x, y + t.px(12), text=f"NF-e {num}", anchor="nw", font=f["forte"],
                             fill=t.c["link"], tags=(tag,))
            valor = moeda(n["NFSVLR"])
            data = n["NFSDATEMI"].strftime("%d/%m/%Y") if n["NFSDATEMI"] else ""
            self.create_text(self.w - m, y + t.px(12), text=valor, anchor="ne", font=f["forte"],
                             fill=t.c["texto"], tags=(tag,))
            larg_cliente = self.w - x - m - max(f["pequeno"].measure(data), f["forte"].measure(valor)) - t.px(16)
            cliente = self._cortar(n["NFSCLIDES"] or "", f["corpo"], larg_cliente)
            self.create_text(x, y + t.px(37), text=cliente, anchor="nw", font=f["corpo"], fill=t.c["suave"],
                             tags=(tag,))
            self.create_text(self.w - m, y + t.px(39), text=data, anchor="ne", font=f["pequeno"],
                             fill=t.c["fraco"], tags=(tag,))
            self.tag_bind(tag, "<Enter>", lambda _e, fu=fundo: (self.itemconfig(fu, image=self.img_sobre),
                                                                  self.config(cursor="hand2")))
            self.tag_bind(tag, "<Leave>", lambda _e, fu=fundo: (self.itemconfig(fu, image=self.img_normal),
                                                                  self.config(cursor="")))
            self.tag_bind(tag, "<Button-1>", lambda _e, nu=num: self.ao_escolher(nu))
        altura = max(len(notas) * (self.hl + self.esp) - self.esp, int(self["height"]))
        self.config(scrollregion=(0, 0, self.w, altura))
        self._reiniciar_rolagem(altura)


class App:
    def __init__(self, root):
        self.root = root
        t = self.t = tm.Tema(root)
        t.preparar_janela(root, TITULO)
        util_app.aplicar_icone(root)
        W = t.px(LARGURA)

        corpo = t.frame(root)
        corpo.pack(padx=t.px(28), pady=(t.px(22), t.px(26)))

        self.cabecalho = tm.Cabecalho(corpo, t, W, "Pré-visualização de NF-e", "Pré-DANFE",
                                      "Veja o DANFE da nota antes de transmitir no SysPDV.")
        self.cabecalho.pack(anchor="w")
        self.cabecalho.status("Conectando ao banco do SysPDV…", "neutro")

        # miolo: troca entre o conteúdo normal e o painel Sobre, na mesma janela
        self.miolo = t.frame(corpo)
        self.miolo.pack(fill="x")
        self.conteudo = conteudo = t.frame(self.miolo)
        conteudo.pack(fill="x")
        self.painel_sobre = None
        self._animacao = None  # id do after() da transição em andamento

        tm.titulo_secao(conteudo, t, "documento", "Gerar por número").pack(anchor="w", pady=(t.px(18), t.px(10)))
        linha = t.frame(conteudo)
        linha.pack(anchor="w")
        self.numero = tm.Campo(linha, t, 190, altura=48, fonte="numero", dica="Nº da NF-e", justify="center")
        self.numero.pack(side="left")
        self.botao = tm.Botao(linha, t, "Gerar Pré-DANFE", self.gerar, icone="documento", primario=True, altura=48)
        self.botao.pack(side="left", padx=(t.px(12), 0))
        self.numero.entry.bind("<Return>", lambda _e: self.gerar())

        self.msg = t.label(conteudo, "", "pequeno", "suave", wraplength=W, justify="left", anchor="w")
        self.msg.pack(anchor="w", fill="x", pady=(t.px(8), 0))

        topo_lista = t.frame(conteudo)
        topo_lista.pack(fill="x", pady=(t.px(16), t.px(10)))
        tm.titulo_secao(topo_lista, t, "camadas", "Aguardando transmissão").pack(side="left")
        tm.Botao(topo_lista, t, "Atualizar", self.atualizar, icone="atualizar", altura=32).pack(side="right")

        self.lista = ListaNotas(conteudo, t, LARGURA, 3.5, self.gerar_numero)
        self.lista.pack(anchor="w")

        rodape = t.frame(corpo)
        rodape.pack(fill="x", pady=(t.px(18), 0))
        tm.Botao(rodape, t, "Abrir pasta dos PDFs", self.abrir_pasta, icone="pasta").pack(side="left")
        tm.Botao(rodape, t, "Configurações", self.configurar, icone="ajustes").pack(side="left", padx=(t.px(10), 0))
        tm.Botao(rodape, t, "Sobre", self.alternar_sobre, icone="info").pack(side="right")
        root.bind("<Escape>", lambda _e: self.fechar_sobre())

        root.after(150, self.iniciar)

    # ------------------------------------------------------------------ sobre

    def alternar_sobre(self):
        if self._animacao is not None:
            return  # ignora cliques durante a transição
        if self.painel_sobre is not None:
            self.fechar_sobre()
            return
        # trava o tamanho do miolo para a janela não "pular" na troca
        self.miolo.update_idletasks()
        self.painel_sobre = tela_sobre.Painel(self.miolo, self.t, LARGURA, self.fechar_sobre)
        self.painel_sobre.update_idletasks()
        altura = max(self.miolo.winfo_height(), self.painel_sobre.winfo_reqheight())
        self.miolo.config(width=self.miolo.winfo_width(), height=altura)
        self.miolo.pack_propagate(False)
        self._deslizar(self.conteudo, self.painel_sobre, 1, lambda: None)

    def fechar_sobre(self):
        if self.painel_sobre is None or self._animacao is not None:
            return
        painel = self.painel_sobre

        def fim():
            painel.destroy()
            self.painel_sobre = None
            self.miolo.pack_propagate(True)
            self.numero.focar()

        self._deslizar(painel, self.conteudo, -1, fim)

    def _deslizar(self, sai, entra, direcao, ao_fim):
        """Troca dois painéis do miolo deslizando na horizontal.

        direcao 1: o novo entra pela direita; -1: entra pela esquerda (volta).
        """
        largura = self.miolo.winfo_width()
        sai.pack_forget()
        inicio = time.perf_counter()

        def passo():
            p = min(1.0, (time.perf_counter() - inicio) * 1000 / DURACAO_TRANSICAO)
            dx = round(largura * (1 - (1 - p) ** 3)) * direcao  # desacelera no fim
            sai.place(x=-dx, y=0, width=largura)
            entra.place(x=direcao * largura - dx, y=0, width=largura)
            if p < 1:
                self._animacao = self.root.after(15, passo)
                return
            sai.place_forget()
            entra.place_forget()
            entra.pack(fill="x")
            self._animacao = None
            ao_fim()

        passo()

    # ------------------------------------------------------------------ ações

    def iniciar(self):
        self.numero.focar()
        try:
            ler_config()
        except ErroConfig:
            self.sem_configuracao()
            self.configurar()
            return
        self.atualizar()

    def sem_configuracao(self):
        self.cabecalho.status("Sem conexão: configure o acesso ao banco do SysPDV", "erro")
        self.lista.mensagem("Clique em Configurações e informe a senha do banco do SysPDV.", "suave", "banco")

    def configurar(self):
        # janela independente: não bloqueia esta; ao salvar, recarrega a lista
        tela_config.abrir(self.root, self.t, ao_salvar=self.atualizar)

    def abrir_pasta(self):
        try:
            os.startfile(pasta_saida())
        except BaseException as e:  # noqa: BLE001
            self.mensagem(f"Não foi possível abrir a pasta: {e}", "vermelho")

    def mensagem(self, texto, cor="suave"):
        self.msg.config(text=texto, fg=self.t.c[cor])

    def ocupado(self, sim):
        self._ocupado = sim
        self.root.config(cursor="watch" if sim else "")
        self.botao.habilitar(not sim)

    # O acesso ao banco roda em segundo plano (util_app.em_segundo_plano): se o
    # servidor demorar a responder, a janela continua respondendo.

    def atualizar(self):
        if getattr(self, "_ocupado", False):
            return
        try:
            ler_config()
        except ErroConfig:
            self.sem_configuracao()
            return
        self.ocupado(True)

        def buscar():
            with conexao_leitura() as cur:
                return listar_pendentes(cur)

        def terminou(pendentes, erro):
            self.ocupado(False)
            if erro is not None:
                log.error("Falha ao listar pendentes: %s", erro)
                self.cabecalho.status("Sem conexão com o banco do SysPDV", "erro")
                self.lista.mensagem(f"Não foi possível ler o banco:\n{erro}", "vermelho", "banco")
                return
            self.lista.mostrar(pendentes)
            qtd = len(pendentes)
            texto = ("nenhuma NF-e aguardando transmissão" if qtd == 0 else
                     f"{qtd} NF-e aguardando transmissão" if qtd > 1 else "1 NF-e aguardando transmissão")
            self.cabecalho.status(f"Conectado ao SysPDV · {texto}", "ok")

        util_app.em_segundo_plano(self.root, buscar, terminou)

    def gerar_numero(self, numero):
        if getattr(self, "_ocupado", False):
            return
        self.numero.set(str(numero))
        self.gerar()

    def gerar(self):
        if getattr(self, "_ocupado", False):
            return
        texto = self.numero.get()
        if not texto.isdigit():
            self.mensagem("Digite o número da NF-e (só números).", "amarelo")
            self.numero.focar()
            return
        num = int(texto)
        self.ocupado(True)
        self.mensagem(f"Procurando a NF-e {num}…")

        def procurar():
            with conexao_leitura() as cur:
                return buscar_por_numero(cur, texto)

        def achou(achadas, erro):
            if erro is not None:
                return self._falhou(num, erro)
            if not achadas:
                self.ocupado(False)
                self.mensagem(f"A NF-e {num} não foi encontrada.", "amarelo")
                return
            nota = achadas[0]
            if nota["TEM_XML"] == "S" and not messagebox.askyesno(
                    "Pré-DANFE",
                    f"A NF-e {num} já foi transmitida.\n\n"
                    "Gerar o pré-DANFE mesmo assim? (Para a nota transmitida, use o DANFE do SysPDV.)",
                    parent=self.root):
                self.ocupado(False)
                self.mensagem("")
                return
            self.mensagem(f"Gerando o pré-DANFE da NF-e {num}…")
            util_app.em_segundo_plano(self.root, lambda: self._gerar_pdf(nota), lambda r, e: pronto(r, e))

        def pronto(resultado, erro):
            if erro is not None:
                return self._falhou(num, erro)
            self.ocupado(False)
            destino, avisos = resultado
            log.info("Gerado %s", destino)
            msg = f"Pré-DANFE da NF-e {num} gerado · {destino.name}"
            if avisos:
                msg += "\nAtenção: " + " ".join(avisos)
            self.mensagem(msg, "verde" if not avisos else "amarelo")
            try:
                os.startfile(destino)
            except OSError as e:
                self.mensagem(f"{msg}\nNão foi possível abrir o PDF: {e}", "amarelo")

        util_app.em_segundo_plano(self.root, procurar, achou)

    @staticmethod
    def _gerar_pdf(nota):
        with conexao_leitura() as cur:
            xml, _chave, avisos = montar(cur, nota["NFSCTR"])
        destino = salvar(pasta_saida(), nome_arquivo(nota["NFSNUM"]), pdf_predanfe(xml))
        return destino, avisos

    def _falhou(self, num, erro):
        self.ocupado(False)
        if isinstance(erro, ErroConfig):
            self.mensagem(str(erro), "vermelho")
            return
        log.error("Falha ao gerar a nota %s: %r", num, erro)
        self.mensagem(f"Não foi possível gerar o pré-DANFE: {erro}", "vermelho")


def main():
    if not util_app.uma_instancia("PreDANFE"):
        # já aberto: mostra a janela existente em vez de abrir outra
        util_app.trazer_para_frente(TITULO)
        return
    tm.ativar_dpi()
    util_app.configurar_log("predanfe")
    util_app.identificar_app("PreDANFE")
    root = tk.Tk()
    util_app.registrar_erros_tk(root, log)
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
