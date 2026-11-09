"""Gera o manual do usuário em PDF (C:\\PreDanfe\\Distribuir\\Manual-PreDANFE.pdf).

  python capturas.py      (só quando as telas mudarem)
  python gerar_manual.py
"""
import json
import sys
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace
from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
import tema as tm  # noqa: E402
from versao import DESENVOLVIMENTO, EMPRESA, TELEFONE, VERSAO  # noqa: E402

IMG = AQUI / "img"
TMP = AQUI / "img" / "gerado"
SAIDA = AQUI.parent.parent / "Distribuir" / "Manual-PreDANFE.pdf"
FONTES = Path(r"C:\Windows\Fonts")

TEXTO, SUAVE, FRACO = (31, 35, 40), (89, 99, 110), (101, 109, 118)
BORDA, CARD, LINK = (209, 217, 224), (246, 248, 250), (9, 105, 218)
VIOLETA, VERDE, AMARELO = (139, 92, 246), (63, 185, 80), (154, 103, 0)
FUNDO_AVISO, BORDA_AVISO = (255, 248, 197), (212, 167, 44)
FUNDO_DICA, BORDA_DICA = (240, 236, 254), (196, 181, 253)


# ------------------------------------------------------------------ imagens auxiliares

def preparar_imagens():
    TMP.mkdir(parents=True, exist_ok=True)
    tm.logo_pronto(600, AQUI.parent / "recursos" / "pbtec_logo_light.png").save(TMP / "logo.png")
    tm.forma_arredondada(600, 24, 12, degrade=tm.DEGRADE).save(TMP / "barra.png")
    for nome in ("documento", "camadas", "pasta", "ajustes", "banco", "atualizar", "seta", "info", "telefone",
                 "usuario"):
        tm.icone(nome, tm.VIOLETA, 96).save(TMP / f"ic_{nome}.png")
    tm.icone("documento", "#FFFFFF", 96).save(TMP / "ic_documento_branco.png")
    marcas = json.loads((IMG / "marcas.json").read_text(encoding="utf-8"))
    # lado de cada marcação: e = à esquerda do item, d = à direita, c = no próprio ponto
    marcar(IMG / "principal.png", marcas["principal"], "edeceede", TMP / "principal.png")
    marcar(IMG / "configuracao.png", marcas["configuracao"], "eeeed", TMP / "configuracao.png")
    # exemplo de DANFE: só a parte de cima (até os itens), para ficar legível
    with Image.open(IMG / "exemplo_predanfe.png") as im:
        im.crop((0, 0, im.width, round(im.height * 0.585))).save(TMP / "exemplo_recorte.png")
    moldura(TMP / "exemplo_recorte.png", TMP / "exemplo.png", raio=10)


def moldura(origem, destino, raio=18):
    """Cantos arredondados e borda fina, como os cartões das janelas."""
    img = Image.open(origem).convert("RGBA")
    ss = 3
    W, H = img.width * ss, img.height * ss
    mascara = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mascara).rounded_rectangle([0, 0, W - 1, H - 1], raio * ss, fill=255)
    mascara = mascara.resize(img.size, Image.LANCZOS)
    saida = Image.new("RGBA", img.size, (255, 255, 255, 0))
    saida.paste(img, (0, 0), mascara)
    borda = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(borda).rounded_rectangle([1, 1, W - 2, H - 2], raio * ss, outline=BORDA + (255,), width=2 * ss)
    saida.alpha_composite(borda.resize(img.size, Image.LANCZOS))
    saida.save(destino)
    return destino


def marcar(origem, marcas, lados, destino):
    """Círculos numerados (violeta, borda branca) ao lado dos itens da captura.

    A captura ganha uma faixa livre dos dois lados, para as marcações ficarem
    fora dos campos e não cobrirem o texto.
    """
    tela = Image.open(moldura(origem, destino.with_suffix(".tmp.png")))
    ss = 3
    r = round(13 * marcas["escala"])
    folga = 2 * r + 10
    img = Image.new("RGBA", (tela.width + 2 * folga, tela.height), (255, 255, 255, 0))
    img.alpha_composite(tela, (folga, 0))
    camada = Image.new("RGBA", (img.width * ss, img.height * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    fonte = ImageFont.truetype(str(FONTES / "segoeuib.ttf"), round(r * ss * 1.15))
    for n, ((x, y), lado) in enumerate(zip(marcas["pontos"], lados), start=1):
        x += folga + {"e": -(r + 7), "d": r + 7, "c": 0}[lado]
        x, y, R = x * ss, y * ss, r * ss
        d.ellipse([x - R - 3 * ss, y - R - 3 * ss, x + R + 3 * ss, y + R + 3 * ss], fill=(255, 255, 255, 255))
        d.ellipse([x - R, y - R, x + R, y + R], fill=VIOLETA + (255,))
        d.text((x, y + ss), str(n), font=fonte, fill=(255, 255, 255, 255), anchor="mm")
    img.alpha_composite(camada.resize(img.size, Image.LANCZOS))
    img.save(destino)


def proporcao(caminho):
    with Image.open(caminho) as im:
        return im.height / im.width


# ------------------------------------------------------------------ documento

class Manual(FPDF):
    def __init__(self):
        super().__init__(format="A4", unit="mm")
        self.set_margins(18, 22, 18)
        self.set_auto_page_break(True, 22)
        for familia, estilo, arq in (("Segoe", "", "segoeui.ttf"), ("Segoe", "B", "segoeuib.ttf"),
                                     ("Segoe", "I", "segoeuii.ttf"), ("SegoeSB", "", "seguisb.ttf"),
                                     ("SegoeSB", "B", "segoeuib.ttf"),
                                     ("Mono", "", "consola.ttf")):
            self.add_font(familia, estilo, str(FONTES / arq))
        self.set_title("Pré-DANFE – Manual do usuário")
        self.set_author("PBtec")
        self.set_creator("PBtec")

    # cabeçalho e rodapé das páginas internas
    def header(self):
        if self.page_no() == 1:
            return
        self.set_xy(18, 10)
        self.set_font("Mono", size=7.5)
        self.set_char_spacing(1.6)
        self.set_text_color(*SUAVE)
        self.cell(0, 4, "PRÉ-DANFE · MANUAL DO USUÁRIO")
        self.set_char_spacing(0)
        self.image(str(TMP / "barra.png"), x=self.w - 18 - 16, y=11.2, w=16)
        self.set_y(22)

    def footer(self):
        if self.page_no() == 1:
            return
        self.set_draw_color(*BORDA)
        self.set_line_width(0.2)
        self.line(18, self.h - 16, self.w - 18, self.h - 16)
        self.image(str(TMP / "logo.png"), x=18, y=self.h - 13.5, h=8)
        self.set_xy(30, self.h - 11.5)
        self.set_font("Segoe", size=8)
        self.set_text_color(*FRACO)
        self.cell(80, 4, "PBtec · soluções em automação")
        self.set_xy(self.w - 18 - 60, self.h - 11.5)
        self.cell(60, 4, f"Página {self.page_no()}", align="R")

    # ---------------------------------------------------------- blocos

    @property
    def largura(self):
        return self.w - self.l_margin - self.r_margin

    def espaco(self, mm):
        self.set_y(self.get_y() + mm)

    def garantir(self, mm):
        if self.get_y() + mm > self.page_break_trigger:
            self.add_page()

    def secao(self, numero, icone, titulo, subtitulo=None):
        self.garantir(30)
        self.set_font("Mono", size=8)
        self.set_char_spacing(1.6)
        self.set_text_color(*SUAVE)
        self.cell(0, 4, f"PASSO {numero:02d}" if isinstance(numero, int) else numero,
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_char_spacing(0)
        self.espaco(1.5)
        y = self.get_y()
        self.image(str(TMP / f"ic_{icone}.png"), x=self.l_margin, y=y + 0.8, w=6.5)
        self.set_xy(self.l_margin + 9, y)
        self.set_font("Segoe", "B", 18)
        self.set_text_color(*TEXTO)
        self.cell(0, 8, titulo, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if subtitulo:
            self.set_font("Segoe", size=10.5)
            self.set_text_color(*SUAVE)
            self.multi_cell(0, 5.4, subtitulo, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.espaco(1.5)
        self.image(str(TMP / "barra.png"), x=self.l_margin, y=self.get_y(), w=14)
        self.espaco(6)

    def paragrafo(self, texto, cor=TEXTO, tam=10.5, largura=0, x=None):
        self.set_font("Segoe", size=tam)
        self.set_text_color(*cor)
        if x is not None:
            self.set_x(x)
        self.multi_cell(largura, 5.6, texto, markdown=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.espaco(2.5)

    def subtitulo(self, texto):
        self.garantir(14)
        self.set_font("SegoeSB", size=12)
        self.set_text_color(*TEXTO)
        self.cell(0, 7, texto, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.espaco(1.5)

    def bolinha(self, x, y, numero, d=6.2, cor=VIOLETA, tam=9.5):
        self.set_fill_color(*cor)
        self.ellipse(x, y, d, d, style="F")
        self.set_font("Segoe", "B", tam)
        self.set_text_color(255, 255, 255)
        self.set_xy(x, y + 0.1)
        self.cell(d, d, str(numero), align="C")

    def passos(self, itens, x=None, largura=None, d=6.2):
        x = self.l_margin if x is None else x
        largura = largura or (self.w - self.r_margin - x)
        for i, texto in enumerate(itens, start=1):
            self.garantir(12)
            y = self.get_y()
            self.bolinha(x, y, i, d)
            self.set_font("Segoe", size=10.5)
            self.set_text_color(*TEXTO)
            self.set_xy(x + d + 3.5, y + 0.4)
            self.multi_cell(largura - d - 3.5, 5.6, texto, markdown=True, align="L",
                            new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_y(max(self.get_y(), y + d) + 2.2)

    def marcadores(self, itens, x=None, largura=None, tam=10.5):
        x = self.l_margin if x is None else x
        largura = largura or (self.w - self.r_margin - x)
        for texto in itens:
            self.garantir(10)
            y = self.get_y()
            self.set_fill_color(*VIOLETA)
            self.ellipse(x + 0.6, y + 2.1, 1.7, 1.7, style="F")
            self.set_font("Segoe", size=tam)
            self.set_text_color(*TEXTO)
            self.set_xy(x + 5, y)
            self.multi_cell(largura - 5, 5.6, texto, markdown=True, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.espaco(1.6)

    def tabela(self, larguras, linhas, primeira_coluna_forte=True):
        """Tabela simples: cabeçalho em azul sobre cinza claro, linhas brancas."""
        self.set_font("Segoe", size=9.5)
        self.set_text_color(*TEXTO)
        self.set_fill_color(255, 255, 255)
        self.set_draw_color(*BORDA)
        self.set_line_width(0.2)
        forte = FontFace(family="SegoeSB", color=SUAVE, size_pt=9.5)
        with self.table(col_widths=larguras, line_height=5.6, padding=(1.8, 2.6), markdown=True,
                        headings_style=FontFace(family="SegoeSB", color=LINK, fill_color=CARD, size_pt=9.5),
                        cell_fill_mode="NONE", text_align="LEFT") as t:
            for i, linha in enumerate(linhas):
                r = t.row()
                for j, valor in enumerate(linha):
                    r.cell(valor, style=forte if (i and j == 0 and primeira_coluna_forte) else None)
        self.espaco(4)

    def caixa(self, titulo, texto, tipo="dica"):
        """Caixa de destaque (dica em violeta claro, atenção em amarelo)."""
        fundo, borda, cor_tit = ((FUNDO_AVISO, BORDA_AVISO, AMARELO) if tipo == "atencao"
                                 else (FUNDO_DICA, BORDA_DICA, (109, 40, 217)))
        larg = self.largura - 10
        self.set_font("Segoe", size=10)
        linhas = self.multi_cell(larg, 5.3, texto, markdown=True, align="L", dry_run=True, output="LINES")
        altura = 7 + 6 + len(linhas) * 5.3 + 3
        self.garantir(altura + 4)
        x, y = self.l_margin, self.get_y()
        self.set_fill_color(*fundo)
        self.set_draw_color(*borda)
        self.set_line_width(0.3)
        self.rect(x, y, self.largura, altura, style="DF", round_corners=True, corner_radius=3)
        self.set_xy(x + 5, y + 4)
        self.set_font("SegoeSB", size=10.5)
        self.set_text_color(*cor_tit)
        self.cell(0, 6, titulo, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_x(x + 5)
        self.set_font("Segoe", size=10)
        self.set_text_color(*TEXTO)
        self.multi_cell(larg, 5.3, texto, markdown=True, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_y(y + altura + 5)

    def figura(self, caminho, largura, legenda=None, x=None):
        altura = largura * proporcao(caminho)
        self.garantir(altura + (8 if legenda else 2))
        x = self.l_margin + (self.largura - largura) / 2 if x is None else x
        y = self.get_y()
        self.image(str(caminho), x=x, y=y, w=largura)
        self.set_y(y + altura + 2)
        if legenda:
            self.set_font("Segoe", "I", 8.5)
            self.set_text_color(*FRACO)
            self.cell(0, 4, legenda, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.espaco(4)

    def cartao_app(self, x, y, w, h, nome, descricao, rotulo):
        self.set_fill_color(*CARD)
        self.set_draw_color(*BORDA)
        self.set_line_width(0.3)
        self.rect(x, y, w, h, style="DF", round_corners=True, corner_radius=4)
        self.image(str(IMG / "icone_app.png"), x=x + 6, y=y + 6, w=11)
        self.set_xy(x + 20, y + 6.5)
        self.set_font("SegoeSB", size=12.5)
        self.set_text_color(*LINK)
        self.cell(w - 24, 5.5, nome)
        self.set_xy(x + 20, y + 12.5)
        self.set_font("Segoe", size=9)
        self.set_text_color(*FRACO)
        self.cell(w - 24, 4.5, rotulo)
        self.set_xy(x + 6, y + 21)
        self.set_font("Segoe", size=10)
        self.set_text_color(*SUAVE)
        self.multi_cell(w - 12, 5.2, descricao, align="L")


# ------------------------------------------------------------------ conteúdo

def capa(pdf):
    pdf.add_page()
    pdf.image(str(TMP / "logo.png"), x=18, y=22, h=30)
    y = 92
    pdf.set_xy(18, y)
    pdf.set_font("Mono", size=10)
    pdf.set_char_spacing(2.4)
    pdf.set_text_color(*SUAVE)
    pdf.cell(0, 5, "MANUAL DO USUÁRIO")
    pdf.set_char_spacing(0)
    pdf.set_xy(16.5, y + 8)
    pdf.set_font("Segoe", "B", 46)
    pdf.set_text_color(*TEXTO)
    pdf.cell(0, 20, "Pré-DANFE")
    pdf.set_xy(18, y + 31)
    pdf.set_font("Segoe", size=15)
    pdf.set_text_color(*SUAVE)
    pdf.multi_cell(150, 7.5, "Veja o DANFE da sua NF-e antes de transmitir no SysPDV.")
    pdf.image(str(TMP / "barra.png"), x=18, y=y + 51, w=22)
    pdf.set_fill_color(*VERDE)
    pdf.ellipse(45, y + 49.9, 2.6, 2.6, style="F")
    pdf.set_xy(50, y + 48.7)
    pdf.set_font("Segoe", size=10)
    pdf.set_text_color(*FRACO)
    pdf.cell(0, 5, "Instalação, configuração e uso dos dois programas")

    y = 172
    w = (pdf.largura - 8) / 2
    pdf.cartao_app(18, y, w, 52, "PreDANFE.exe", "Você digita o número da NF-e, clica em Gerar e o PDF abre na hora.",
                   "Sob demanda")
    pdf.cartao_app(18 + w + 8, y, w, 52, "PreDANFE-Automatico.exe",
                   "Fica ao lado do relógio e gera sozinho o PDF de cada NF-e salva e ainda não transmitida.",
                   "Automático, em segundo plano")

    pdf.set_xy(18, 262)
    pdf.set_font("Segoe", size=9)
    pdf.set_text_color(*FRACO)
    pdf.cell(0, 5, f"Versão {VERSAO} · novembro de 2026")
    pdf.set_xy(18, 267)
    pdf.cell(0, 5, f"PBtec · soluções em automação · {TELEFONE}")


def pagina_inicio(pdf):
    pdf.add_page()
    pdf.secao("ANTES DE COMEÇAR", "documento", "O que é o Pré-DANFE")
    pdf.paragrafo(
        "O SysPDV só mostra o DANFE **depois** que a NF-e é transmitida. O Pré-DANFE resolve isso: ele lê a "
        "nota que você digitou e salvou na retaguarda e gera um PDF no **mesmo formato do DANFE**, para você "
        "conferir cliente, produtos, quantidades, valores e impostos **antes** de transmitir.")
    pdf.paragrafo("Se encontrar algum erro, corrija a nota no SysPDV, salve e gere o pré-DANFE de novo.")
    pdf.marcadores([
        "Funciona com **NF-e modelo 55** digitada na retaguarda do SysPDV.",
        "O Pré-DANFE **só lê** as informações. Ele nunca altera, transmite ou apaga nenhuma nota.",
    ])
    pdf.espaco(2)
    pdf.caixa("Atenção: o pré-DANFE não tem valor fiscal",
              "O PDF sai com a marca **SEM VALOR FISCAL – PRÉ-VISUALIZAÇÃO**. Ele serve só para conferência. "
              "Não envie ao cliente nem use como documento da mercadoria: depois de transmitir, imprima o DANFE "
              "normal pelo SysPDV.", "atencao")

    pdf.subtitulo("Qual programa usar?")
    linhas = [
        ("", "PreDANFE.exe", "PreDANFE-Automatico.exe"),
        ("Como funciona", "Você digita o número da nota e clica em Gerar", "Gera sozinho, sem precisar abrir nada"),
        ("Quando o PDF é gerado", "Na hora em que você pede", "De 10 a 20 segundos depois que a nota é salva"),
        ("O PDF abre sozinho?", "Sim", "Não: fica na pasta e aparece um aviso"),
        ("Indicado para", "Conferir uma nota específica", "Quem emite muitas notas e quer tudo pronto"),
    ]
    pdf.tabela((32, 69, 73), linhas)
    pdf.paragrafo("Você pode usar os dois no mesmo computador.", SUAVE, 10)


def pagina_instalacao(pdf):
    pdf.secao(1, "pasta", "Instalação", "Faça uma vez em cada computador que emite notas.")
    pdf.passos([
        "Crie a pasta **C:\\PreDanfe** no computador.",
        "Copie para ela o **PreDANFE.exe** e/ou o **PreDANFE-Automatico.exe**.",
        "Abra um dos programas com dois cliques. Na primeira vez aparece a tela de **Configuração** "
        "(próximo passo).",
        "Se quiser, crie um atalho na Área de Trabalho: clique com o botão direito no programa → "
        "**Enviar para** → **Área de trabalho (criar atalho)**.",
    ])
    pdf.caixa("O Windows pode pedir confirmação na primeira vez",
              "Se aparecer \"O Windows protegeu o computador\", clique em **Mais informações** → **Executar assim "
              "mesmo**. Se o antivírus bloquear, libere a pasta C:\\PreDanfe.")
    pdf.subtitulo("Requisitos")
    pdf.marcadores([
        "Windows 10 ou 11 (64 bits).",
        "O SysPDV funcionando nesse computador (o Pré-DANFE usa a mesma conexão com o servidor).",
        "Uma pasta onde o usuário possa gravar, como C:\\PreDanfe. Evite \"Arquivos de Programas\".",
    ])
    pdf.espaco(2)
    pdf.subtitulo("Como a pasta fica depois de usar")
    arvore = [
        ("pasta", "C:\\PreDanfe", "", TEXTO),
        ("documento", "PreDANFE.exe", "programa sob demanda", TEXTO),
        ("documento", "PreDANFE-Automatico.exe", "programa automático", TEXTO),
        ("ajustes", "config.ini", "criado ao salvar a configuração", TEXTO),
        ("pasta", "pdf", "os pré-DANFEs gerados (PreDANFE_1532.pdf, ...)", TEXTO),
    ]
    altura = 8 + len(arvore) * 8
    x, y = pdf.l_margin, pdf.get_y()
    pdf.set_fill_color(*CARD)
    pdf.set_draw_color(*BORDA)
    pdf.set_line_width(0.3)
    pdf.rect(x, y, pdf.largura, altura, style="DF", round_corners=True, corner_radius=4)
    for i, (ic, nome, obs, cor) in enumerate(arvore):
        recuo = 0 if i == 0 else 8
        yy = y + 5 + i * 8
        if i:
            pdf.set_draw_color(*BORDA)
            pdf.line(x + 8.5, yy - 4.5, x + 8.5, yy + 2.6)
            pdf.line(x + 8.5, yy + 2.6, x + 12, yy + 2.6)
        pdf.image(str(TMP / f"ic_{ic}.png"), x=x + 6 + recuo, y=yy, w=5)
        pdf.set_xy(x + 13 + recuo, yy)
        pdf.set_font("Mono", size=10)
        pdf.set_text_color(*cor)
        pdf.cell(62, 5, nome)
        pdf.set_font("Segoe", size=9.5)
        pdf.set_text_color(*FRACO)
        pdf.cell(0, 5, obs)
    pdf.set_y(y + altura + 4)


def pagina_config(pdf):
    pdf.add_page()
    pdf.secao(2, "banco", "Primeira configuração",
              "Na primeira vez, os programas pedem os dados de acesso ao banco do SysPDV.")
    pdf.figura(TMP / "configuracao.png", 128, "Tela de configuração (os números indicam os itens explicados abaixo)")
    itens = [
        "**Servidor, porta e arquivo do banco** já vêm preenchidos com o que o SysPDV deste computador usa. "
        "Normalmente não é preciso mudar.",
        "**Senha**: digite a senha do banco do SysPDV (**masterkey**).",
        "**Pasta dos PDFs**: onde os pré-DANFEs serão salvos. O padrão é a pasta **pdf**, dentro de C:\\PreDanfe.",
        "**Testar conexão**: confere se está tudo certo. Deve aparecer \"Conectou!\" em verde.",
        "**Salvar**: grava a configuração. Pronto, não será pedida de novo.",
    ]
    pdf.passos(itens)
    pdf.caixa("Dica para vários computadores",
              "A configuração fica no arquivo **config.ini**, ao lado dos programas. Depois de configurar um "
              "computador, copie esse arquivo para os outros que usam o mesmo servidor e pule este passo.")


def pagina_v1(pdf):
    pdf.add_page()
    pdf.secao(3, "documento", "Gerar por número (PreDANFE.exe)",
              "Para conferir uma nota específica antes de transmitir.")
    pdf.figura(TMP / "principal.png", 88, "Janela do PreDANFE.exe (dados fictícios)")
    pdf.subtitulo("O que tem na janela")
    pdf.passos([
        "**Número da NF-e**: digite o número da nota.",
        "**Gerar Pré-DANFE**: gera o PDF e abre na tela (ou tecle **Enter**).",
        "**Aguardando transmissão**: as notas salvas e ainda não transmitidas. **Clique em uma delas** para "
        "gerar o PDF direto, sem digitar o número.",
        "**Status da conexão**: bolinha verde = conectado ao SysPDV; vermelha = sem conexão. "
        "Passe o mouse sobre ela para ver os detalhes.",
        "**Atualizar**: recarrega a lista depois de salvar uma nota nova no SysPDV.",
        "**Abrir pasta dos PDFs**: mostra os pré-DANFEs já gerados.",
        "**Configurações**: muda servidor, senha ou pasta dos PDFs.",
        "**Sobre**: versão do programa e contato da PBtec.",
    ])
    pdf.subtitulo("Passo a passo")
    pdf.marcadores([
        "Digite a NF-e na retaguarda do SysPDV e **salve sem transmitir**.",
        "No Pré-DANFE, digite o número e clique em **Gerar Pré-DANFE** (ou clique na nota da lista).",
        "Confira o PDF. Achou erro? Corrija a nota no SysPDV, salve e gere de novo.",
        "Tudo certo? Transmita a nota normalmente pelo SysPDV.",
    ])


def pagina_v2(pdf):
    pdf.add_page()
    pdf.secao(4, "camadas", "Modo automático (PreDANFE-Automatico.exe)",
              "Gera o pré-DANFE sozinho, sem você precisar abrir nada.")
    pdf.paragrafo(
        "Depois de aberto, o programa fica rodando **ao lado do relógio do Windows** (perto da data e hora). "
        "A cada 10 segundos ele verifica se há NF-e salva e ainda não transmitida. Para cada nota nova ou "
        "alterada, ele gera o PDF na pasta dos pré-DANFEs e mostra um aviso no canto da tela.")
    pdf.subtitulo("Como ligar")
    pdf.passos([
        "Abra o **PreDANFE-Automatico.exe** com dois cliques. Nenhuma janela abre: aparece só o ícone "
        "perto do relógio.",
        "Na primeira vez, preencha a configuração (Passo 2).",
        "Responda **Sim** em \"Iniciar junto com o Windows\". Assim ele liga sozinho todo dia.",
    ])
    pdf.caixa("Não achou o ícone?",
              "O Windows às vezes esconde ícones. Clique na **setinha ( ^ )** ao lado do relógio para ver os "
              "ícones ocultos. Você pode arrastar o ícone do Pré-DANFE para a barra, para deixá-lo sempre visível.")

    # cartão com o menu do ícone
    pdf.subtitulo("Menu do ícone (clique com o botão direito)")
    itens = [("pasta", "Abrir pasta dos Pré-DANFEs", "Mostra os PDFs gerados (o mesmo que dar dois cliques no ícone)."),
             ("atualizar", "Verificar agora", "Procura notas novas na hora, sem esperar os 10 segundos."),
             ("ajustes", "Configurações...", "Muda servidor, senha ou pasta dos PDFs."),
             ("seta", "Iniciar com o Windows", "Liga ou desliga o início automático."),
             ("info", "Sobre...", "Versão do programa e contato da PBtec."),
             ("documento", "Sair", "Fecha o programa. Os PDFs param de ser gerados até abrir de novo.")]
    altura = 10 + len(itens) * 10
    pdf.garantir(altura + 4)
    x, y = pdf.l_margin, pdf.get_y()
    pdf.set_fill_color(*CARD)
    pdf.set_draw_color(*BORDA)
    pdf.rect(x, y, pdf.largura, altura, style="DF", round_corners=True, corner_radius=4)
    pdf.set_xy(x + 6, y + 4)
    pdf.set_font("Segoe", size=9)
    pdf.set_text_color(*FRACO)
    pdf.cell(0, 4, "Primeira linha do menu: quantas notas estão pendentes e a hora da última verificação.")
    for i, (ic, nome, desc) in enumerate(itens):
        yy = y + 10.5 + i * 10
        pdf.image(str(TMP / f"ic_{ic}.png"), x=x + 6, y=yy + 0.6, w=5)
        pdf.set_xy(x + 14, yy)
        pdf.set_font("SegoeSB", size=10.5)
        pdf.set_text_color(*TEXTO)
        pdf.cell(60, 5, nome)
        pdf.set_xy(x + 14, yy + 5)
        pdf.set_font("Segoe", size=9.5)
        pdf.set_text_color(*SUAVE)
        pdf.cell(0, 4.5, desc)
    pdf.set_y(y + altura + 6)

    pdf.subtitulo("Bom saber")
    pdf.marcadores([
        "Os arquivos se chamam **PreDANFE_número.pdf** (exemplo: PreDANFE_1532.pdf).",
        "Se você alterar a nota no SysPDV, o PDF é refeito sozinho com as alterações.",
        "O programa espera a nota ficar igual por duas verificações seguidas antes de gerar, para não pegar "
        "a nota no meio da digitação. Por isso o PDF aparece de 10 a 20 segundos depois de salvar.",
        "Ele gera o PDF de **todas** as notas pendentes do banco, inclusive as digitadas em outros computadores.",
    ])


def pagina_predanfe(pdf):
    pdf.add_page()
    pdf.secao(5, "documento", "Entendendo o pré-DANFE", "O que conferir antes de transmitir.")
    pdf.figura(TMP / "exemplo.png", pdf.largura, "Parte de cima de um pré-DANFE (dados fictícios)")

    def coluna(x, w, titulo, itens):
        pdf.set_xy(x, pdf.get_y())
        pdf.set_font("SegoeSB", size=12)
        pdf.set_text_color(*TEXTO)
        pdf.cell(w, 7, titulo, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.espaco(1)
        pdf.marcadores(itens, x=x, largura=w, tam=10)

    meio = (pdf.largura - 8) / 2
    x1, x2 = pdf.l_margin, pdf.l_margin + meio + 8
    y0 = pdf.get_y()
    coluna(x1, meio, "Igual ao DANFE final", [
        "Emitente, destinatário e chave de acesso",
        "Produtos, quantidades, valores, CFOP, NCM e CST",
        "ICMS e substituição tributária",
        "**PIS e COFINS** (calculados como o SysPDV faz ao transmitir)",
        "**Valor aproximado dos tributos** (IBPT) e o texto com os valores federal e estadual",
        "Fatura e totais da nota",
    ])
    fim1 = pdf.get_y()
    pdf.set_y(y0)
    coluna(x2, meio, "Pode ser só uma estimativa", [
        "**Tributos aproximados** de produto cujo NCM ainda não saiu em nenhuma nota transmitida. "
        "O pré-DANFE avisa: \"TRIBUTOS APROXIMADOS ESTIMADOS PARA NCM ...\".",
    ])
    pdf.espaco(1)
    coluna(x2, meio, "Como reconhecer", [
        "Marca **SEM VALOR FISCAL – PRÉ-VISUALIZAÇÃO**",
        "Protocolo: **NÃO TRANSMITIDA**",
    ])
    pdf.set_y(max(fim1, pdf.get_y()) + 2)


def pagina_duvidas(pdf):
    pdf.add_page()
    pdf.secao("DÚVIDAS", "ajustes", "Problemas comuns e soluções")
    linhas = [
        ("O status está vermelho: \"Sem conexão com o banco\"",
         "Confira se o SysPDV abre normalmente neste computador. Depois abra **Configurações**, confira o "
         "servidor e a senha e clique em **Testar conexão**."),
        ("\"A NF-e não foi encontrada\"",
         "Confira o número. A nota precisa estar **salva** na retaguarda do SysPDV."),
        ("\"Esta nota já foi transmitida\"",
         "Para nota transmitida, imprima o DANFE normal pelo SysPDV. O pré-DANFE é só para notas ainda não "
         "transmitidas."),
        ("A nota não aparece na lista \"Aguardando transmissão\"",
         "Clique em **Atualizar**. Notas já transmitidas ou canceladas não aparecem na lista."),
        ("O automático não gerou o PDF",
         "Veja se o ícone está ao lado do relógio (ou na setinha ^). Use **Verificar agora** e espere até 20 "
         "segundos. Se o ícone não estiver lá, abra o PreDANFE-Automatico.exe de novo."),
        ("O PDF foi gerado com outro nome, com um horário no final",
         "O PDF anterior estava aberto. Feche o PDF antigo; o novo arquivo é o que tem o horário no nome."),
        ("O Windows ou o antivírus bloqueou o programa",
         "Clique em **Mais informações** → **Executar assim mesmo**, ou libere a pasta C:\\PreDanfe no antivírus."),
        ("Apareceu \"TRIBUTOS APROXIMADOS ESTIMADOS PARA NCM ...\"",
         "O produto nunca saiu numa nota transmitida, então o valor aproximado dos tributos dele é uma "
         "estimativa. Depois que a primeira nota com ele for transmitida, o Pré-DANFE passa a usar o "
         "valor exato."),
    ]
    pdf.tabela((62, 112), [("Situação", "O que fazer")] + linhas)
    pdf.espaco(2)
    pdf.caixa("Precisa de ajuda?",
              f"Fale com a **{EMPRESA}** pelo telefone **{TELEFONE}**. Se for um erro, informe o que apareceu "
              "na tela. O programa também guarda um registro de erros na pasta **%LOCALAPPDATA%\\PreDANFE** "
              "(digite esse endereço na barra do Explorador de Arquivos).")


def creditos(pdf):
    """Créditos (os mesmos da janela Sobre do programa)."""
    pdf.espaco(2)
    altura = max(32, 16 + 8 * len(DESENVOLVIMENTO))
    pdf.garantir(altura + 12)
    pdf.subtitulo("Créditos")
    x, y = pdf.l_margin, pdf.get_y()
    pdf.set_fill_color(*CARD)
    pdf.set_draw_color(*BORDA)
    pdf.set_line_width(0.3)
    pdf.rect(x, y, pdf.largura, altura, style="DF", round_corners=True, corner_radius=4)
    meio = x + pdf.largura * 0.52

    def linha(x0, icone, texto, yy, familia="Segoe", tam=10.5):
        pdf.image(str(TMP / f"ic_{icone}.png"), x=x0, y=yy + 0.2, w=5)
        pdf.set_xy(x0 + 8, yy)
        pdf.set_font(familia, size=tam)
        pdf.set_text_color(*TEXTO)
        pdf.cell(80, 5.5, texto)

    # esquerda: programa e empresa (como na janela Sobre)
    linha(x + 7, "documento", f"Pré-DANFE · versão {VERSAO}", y + 6, "SegoeSB", 11)
    linha(x + 7, "camadas", EMPRESA, y + 14)
    linha(x + 7, "telefone", TELEFONE, y + 22)
    # direita: desenvolvimento e análise
    pdf.set_draw_color(*BORDA)
    pdf.line(meio - 4, y + 6, meio - 4, y + altura - 6)
    pdf.set_xy(meio + 2, y + 6)
    pdf.set_font("Mono", size=8)
    pdf.set_char_spacing(1.6)
    pdf.set_text_color(*SUAVE)
    pdf.cell(0, 5.5, "DESENVOLVIMENTO E ANÁLISE")
    pdf.set_char_spacing(0)
    for i, nome in enumerate(DESENVOLVIMENTO):
        linha(meio + 2, "usuario", nome, y + 14 + 8 * i)
    pdf.set_y(y + altura + 4)


def main():
    preparar_imagens()
    pdf = Manual()
    capa(pdf)
    pagina_inicio(pdf)
    pdf.add_page()
    pagina_instalacao(pdf)
    pagina_config(pdf)
    pagina_v1(pdf)
    pagina_v2(pdf)
    pagina_predanfe(pdf)
    pagina_duvidas(pdf)
    creditos(pdf)
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(SAIDA))
    print("Manual gerado:", SAIDA, f"({pdf.page_no()} páginas)")


if __name__ == "__main__":
    main()
