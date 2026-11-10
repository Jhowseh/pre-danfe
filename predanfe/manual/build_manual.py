import json
import sys
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import theme as tm
from version import COMPANY, DEVELOPERS, PHONE, VERSION

IMG = HERE / "img"
TMP = HERE / "img" / "generated"
OUTPUT = HERE.parent.parent / "dist" / "Manual-PreDANFE.pdf"
FONTS = Path(r"C:\Windows\Fonts")

TEXT, MUTED, FAINT = (31, 35, 40), (89, 99, 110), (101, 109, 118)
BORDER, CARD, LINK = (209, 217, 224), (246, 248, 250), (9, 105, 218)
VIOLET, GREEN, YELLOW = (139, 92, 246), (63, 185, 80), (154, 103, 0)
WARNING_BG, WARNING_BORDER = (255, 248, 197), (212, 167, 44)
TIP_BG, TIP_BORDER = (240, 236, 254), (196, 181, 253)


def prepare_images():
    TMP.mkdir(parents=True, exist_ok=True)
    tm.transparent_logo(600, HERE.parent / "resources" / "pbtec_logo_light.png").save(TMP / "logo.png")
    tm.rounded_shape(600, 24, 12, gradient=tm.GRADIENT).save(TMP / "bar.png")
    for name in ("document", "layers", "folder", "sliders", "database", "refresh", "arrow", "info", "phone",
                 "user"):
        tm.icon(name, tm.VIOLET, 96).save(TMP / f"ic_{name}.png")
    tm.icon("document", "#FFFFFF", 96).save(TMP / "ic_document_white.png")
    markers = json.loads((IMG / "markers.json").read_text(encoding="utf-8"))
    annotate(IMG / "main.png", markers["main"], "lrlcllrl", TMP / "main.png")
    annotate(IMG / "config.png", markers["config"], "llllr", TMP / "config.png")
    with Image.open(IMG / "sample_predanfe.png") as im:
        im.crop((0, 0, im.width, round(im.height * 0.585))).save(TMP / "sample_crop.png")
    frame(TMP / "sample_crop.png", TMP / "sample.png", radius=10)


def frame(source, target, radius=18):
    img = Image.open(source).convert("RGBA")
    ss = 3
    W, H = img.width * ss, img.height * ss
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], radius * ss, fill=255)
    mask = mask.resize(img.size, Image.LANCZOS)
    out = Image.new("RGBA", img.size, (255, 255, 255, 0))
    out.paste(img, (0, 0), mask)
    border = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(border).rounded_rectangle([1, 1, W - 2, H - 2], radius * ss, outline=BORDER + (255,), width=2 * ss)
    out.alpha_composite(border.resize(img.size, Image.LANCZOS))
    out.save(target)
    return target


def annotate(source, markers, sides, target):
    screen = Image.open(frame(source, target.with_suffix(".tmp.png")))
    ss = 3
    r = round(13 * markers["scale"])
    margin = 2 * r + 10
    img = Image.new("RGBA", (screen.width + 2 * margin, screen.height), (255, 255, 255, 0))
    img.alpha_composite(screen, (margin, 0))
    layer = Image.new("RGBA", (img.width * ss, img.height * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    font = ImageFont.truetype(str(FONTS / "segoeuib.ttf"), round(r * ss * 1.15))
    for n, ((x, y), side) in enumerate(zip(markers["points"], sides), start=1):
        x += margin + {"l": -(r + 7), "r": r + 7, "c": 0}[side]
        x, y, R = x * ss, y * ss, r * ss
        d.ellipse([x - R - 3 * ss, y - R - 3 * ss, x + R + 3 * ss, y + R + 3 * ss], fill=(255, 255, 255, 255))
        d.ellipse([x - R, y - R, x + R, y + R], fill=VIOLET + (255,))
        d.text((x, y + ss), str(n), font=font, fill=(255, 255, 255, 255), anchor="mm")
    img.alpha_composite(layer.resize(img.size, Image.LANCZOS))
    img.save(target)


def aspect_ratio(path):
    with Image.open(path) as im:
        return im.height / im.width


class Manual(FPDF):
    def __init__(self):
        super().__init__(format="A4", unit="mm")
        self.set_margins(18, 22, 18)
        self.set_auto_page_break(True, 22)
        for family, style, file in (("Segoe", "", "segoeui.ttf"), ("Segoe", "B", "segoeuib.ttf"),
                                    ("Segoe", "I", "segoeuii.ttf"), ("SegoeSB", "", "seguisb.ttf"),
                                    ("SegoeSB", "B", "segoeuib.ttf"),
                                    ("Mono", "", "consola.ttf")):
            self.add_font(family, style, str(FONTS / file))
        self.set_title("Pré-DANFE – Manual do usuário")
        self.set_author("PBtec")
        self.set_creator("PBtec")

    def header(self):
        if self.page_no() == 1:
            return
        self.set_xy(18, 10)
        self.set_font("Mono", size=7.5)
        self.set_char_spacing(1.6)
        self.set_text_color(*MUTED)
        self.cell(0, 4, "PRÉ-DANFE · MANUAL DO USUÁRIO")
        self.set_char_spacing(0)
        self.image(str(TMP / "bar.png"), x=self.w - 18 - 16, y=11.2, w=16)
        self.set_y(22)

    def footer(self):
        if self.page_no() == 1:
            return
        self.set_draw_color(*BORDER)
        self.set_line_width(0.2)
        self.line(18, self.h - 16, self.w - 18, self.h - 16)
        self.image(str(TMP / "logo.png"), x=18, y=self.h - 13.5, h=8)
        self.set_xy(30, self.h - 11.5)
        self.set_font("Segoe", size=8)
        self.set_text_color(*FAINT)
        self.cell(80, 4, "PBtec · soluções em automação")
        self.set_xy(self.w - 18 - 60, self.h - 11.5)
        self.cell(60, 4, f"Página {self.page_no()}", align="R")

    @property
    def content_width(self):
        return self.w - self.l_margin - self.r_margin

    def space(self, mm):
        self.set_y(self.get_y() + mm)

    def ensure_space(self, mm):
        if self.get_y() + mm > self.page_break_trigger:
            self.add_page()

    def section(self, number, icon, title, subtitle=None):
        self.ensure_space(30)
        self.set_font("Mono", size=8)
        self.set_char_spacing(1.6)
        self.set_text_color(*MUTED)
        self.cell(0, 4, f"PASSO {number:02d}" if isinstance(number, int) else number,
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_char_spacing(0)
        self.space(1.5)
        y = self.get_y()
        self.image(str(TMP / f"ic_{icon}.png"), x=self.l_margin, y=y + 0.8, w=6.5)
        self.set_xy(self.l_margin + 9, y)
        self.set_font("Segoe", "B", 18)
        self.set_text_color(*TEXT)
        self.cell(0, 8, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if subtitle:
            self.set_font("Segoe", size=10.5)
            self.set_text_color(*MUTED)
            self.multi_cell(0, 5.4, subtitle, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.space(1.5)
        self.image(str(TMP / "bar.png"), x=self.l_margin, y=self.get_y(), w=14)
        self.space(6)

    def paragraph(self, text, color=TEXT, size=10.5, width=0, x=None):
        self.set_font("Segoe", size=size)
        self.set_text_color(*color)
        if x is not None:
            self.set_x(x)
        self.multi_cell(width, 5.6, text, markdown=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.space(2.5)

    def subtitle(self, text):
        self.ensure_space(14)
        self.set_font("SegoeSB", size=12)
        self.set_text_color(*TEXT)
        self.cell(0, 7, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.space(1.5)

    def number_badge(self, x, y, number, d=6.2, color=VIOLET, size=9.5):
        self.set_fill_color(*color)
        self.ellipse(x, y, d, d, style="F")
        self.set_font("Segoe", "B", size)
        self.set_text_color(255, 255, 255)
        self.set_xy(x, y + 0.1)
        self.cell(d, d, str(number), align="C")

    def steps(self, items, x=None, width=None, d=6.2):
        x = self.l_margin if x is None else x
        width = width or (self.w - self.r_margin - x)
        for i, text in enumerate(items, start=1):
            self.ensure_space(12)
            y = self.get_y()
            self.number_badge(x, y, i, d)
            self.set_font("Segoe", size=10.5)
            self.set_text_color(*TEXT)
            self.set_xy(x + d + 3.5, y + 0.4)
            self.multi_cell(width - d - 3.5, 5.6, text, markdown=True, align="L",
                            new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_y(max(self.get_y(), y + d) + 2.2)

    def bullets(self, items, x=None, width=None, size=10.5):
        x = self.l_margin if x is None else x
        width = width or (self.w - self.r_margin - x)
        for text in items:
            self.ensure_space(10)
            y = self.get_y()
            self.set_fill_color(*VIOLET)
            self.ellipse(x + 0.6, y + 2.1, 1.7, 1.7, style="F")
            self.set_font("Segoe", size=size)
            self.set_text_color(*TEXT)
            self.set_xy(x + 5, y)
            self.multi_cell(width - 5, 5.6, text, markdown=True, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.space(1.6)

    def table_rows(self, widths, rows, bold_first_column=True):
        self.set_font("Segoe", size=9.5)
        self.set_text_color(*TEXT)
        self.set_fill_color(255, 255, 255)
        self.set_draw_color(*BORDER)
        self.set_line_width(0.2)
        bold = FontFace(family="SegoeSB", color=MUTED, size_pt=9.5)
        with self.table(col_widths=widths, line_height=5.6, padding=(1.8, 2.6), markdown=True,
                        headings_style=FontFace(family="SegoeSB", color=LINK, fill_color=CARD, size_pt=9.5),
                        cell_fill_mode="NONE", text_align="LEFT") as t:
            for i, row in enumerate(rows):
                r = t.row()
                for j, value in enumerate(row):
                    r.cell(value, style=bold if (i and j == 0 and bold_first_column) else None)
        self.space(4)

    def callout(self, title, text, kind="tip"):
        background, border, title_color = ((WARNING_BG, WARNING_BORDER, YELLOW) if kind == "warning"
                                           else (TIP_BG, TIP_BORDER, (109, 40, 217)))
        inner_width = self.content_width - 10
        self.set_font("Segoe", size=10)
        lines = self.multi_cell(inner_width, 5.3, text, markdown=True, align="L", dry_run=True, output="LINES")
        height = 7 + 6 + len(lines) * 5.3 + 3
        self.ensure_space(height + 4)
        x, y = self.l_margin, self.get_y()
        self.set_fill_color(*background)
        self.set_draw_color(*border)
        self.set_line_width(0.3)
        self.rect(x, y, self.content_width, height, style="DF", round_corners=True, corner_radius=3)
        self.set_xy(x + 5, y + 4)
        self.set_font("SegoeSB", size=10.5)
        self.set_text_color(*title_color)
        self.cell(0, 6, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_x(x + 5)
        self.set_font("Segoe", size=10)
        self.set_text_color(*TEXT)
        self.multi_cell(inner_width, 5.3, text, markdown=True, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_y(y + height + 5)

    def figure(self, path, width, caption=None, x=None):
        height = width * aspect_ratio(path)
        self.ensure_space(height + (8 if caption else 2))
        x = self.l_margin + (self.content_width - width) / 2 if x is None else x
        y = self.get_y()
        self.image(str(path), x=x, y=y, w=width)
        self.set_y(y + height + 2)
        if caption:
            self.set_font("Segoe", "I", 8.5)
            self.set_text_color(*FAINT)
            self.cell(0, 4, caption, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.space(4)

    def app_card(self, x, y, w, h, name, description, label):
        self.set_fill_color(*CARD)
        self.set_draw_color(*BORDER)
        self.set_line_width(0.3)
        self.rect(x, y, w, h, style="DF", round_corners=True, corner_radius=4)
        self.image(str(IMG / "app_icon.png"), x=x + 6, y=y + 6, w=11)
        self.set_xy(x + 20, y + 6.5)
        self.set_font("SegoeSB", size=12.5)
        self.set_text_color(*LINK)
        self.cell(w - 24, 5.5, name)
        self.set_xy(x + 20, y + 12.5)
        self.set_font("Segoe", size=9)
        self.set_text_color(*FAINT)
        self.cell(w - 24, 4.5, label)
        self.set_xy(x + 6, y + 21)
        self.set_font("Segoe", size=10)
        self.set_text_color(*MUTED)
        self.multi_cell(w - 12, 5.2, description, align="L")


def cover(pdf):
    pdf.add_page()
    pdf.image(str(TMP / "logo.png"), x=18, y=22, h=30)
    y = 92
    pdf.set_xy(18, y)
    pdf.set_font("Mono", size=10)
    pdf.set_char_spacing(2.4)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 5, "MANUAL DO USUÁRIO")
    pdf.set_char_spacing(0)
    pdf.set_xy(16.5, y + 8)
    pdf.set_font("Segoe", "B", 46)
    pdf.set_text_color(*TEXT)
    pdf.cell(0, 20, "Pré-DANFE")
    pdf.set_xy(18, y + 31)
    pdf.set_font("Segoe", size=15)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(150, 7.5, "Veja o DANFE da sua NF-e antes de transmitir no SysPDV.")
    pdf.image(str(TMP / "bar.png"), x=18, y=y + 51, w=22)
    pdf.set_fill_color(*GREEN)
    pdf.ellipse(45, y + 49.9, 2.6, 2.6, style="F")
    pdf.set_xy(50, y + 48.7)
    pdf.set_font("Segoe", size=10)
    pdf.set_text_color(*FAINT)
    pdf.cell(0, 5, "Instalação, configuração e uso dos dois programas")

    y = 172
    w = (pdf.content_width - 8) / 2
    pdf.app_card(18, y, w, 52, "PreDANFE.exe", "Você digita o número da NF-e, clica em Gerar e o PDF abre na hora.",
                 "Sob demanda")
    pdf.app_card(18 + w + 8, y, w, 52, "PreDANFE-Automatico.exe",
                 "Fica ao lado do relógio e gera sozinho o PDF de cada NF-e salva e ainda não transmitida.",
                 "Automático, em segundo plano")

    pdf.set_xy(18, 262)
    pdf.set_font("Segoe", size=9)
    pdf.set_text_color(*FAINT)
    pdf.cell(0, 5, f"Versão {VERSION} · novembro de 2026")
    pdf.set_xy(18, 267)
    pdf.cell(0, 5, f"PBtec · soluções em automação · {PHONE}")


def page_intro(pdf):
    pdf.add_page()
    pdf.section("ANTES DE COMEÇAR", "document", "O que é o Pré-DANFE")
    pdf.paragraph(
        "O SysPDV só mostra o DANFE **depois** que a NF-e é transmitida. O Pré-DANFE resolve isso: ele lê a "
        "nota que você digitou e salvou na retaguarda e gera um PDF no **mesmo formato do DANFE**, para você "
        "conferir cliente, produtos, quantidades, valores e impostos **antes** de transmitir.")
    pdf.paragraph("Se encontrar algum erro, corrija a nota no SysPDV, salve e gere o pré-DANFE de novo.")
    pdf.bullets([
        "Funciona com **NF-e modelo 55** digitada na retaguarda do SysPDV.",
        "O Pré-DANFE **só lê** as informações. Ele nunca altera, transmite ou apaga nenhuma nota.",
    ])
    pdf.space(2)
    pdf.callout("Atenção: o pré-DANFE não tem valor fiscal",
                "O PDF sai com a marca **SEM VALOR FISCAL – PRÉ-VISUALIZAÇÃO**. Ele serve só para conferência. "
                "Não envie ao cliente nem use como documento da mercadoria: depois de transmitir, imprima o DANFE "
                "normal pelo SysPDV.", "warning")

    pdf.subtitle("Qual programa usar?")
    rows = [
        ("", "PreDANFE.exe", "PreDANFE-Automatico.exe"),
        ("Como funciona", "Você digita o número da nota e clica em Gerar", "Gera sozinho, sem precisar abrir nada"),
        ("Quando o PDF é gerado", "Na hora em que você pede", "De 10 a 20 segundos depois que a nota é salva"),
        ("O PDF abre sozinho?", "Sim", "Não: fica na pasta e aparece um aviso"),
        ("Indicado para", "Conferir uma nota específica", "Quem emite muitas notas e quer tudo pronto"),
    ]
    pdf.table_rows((32, 69, 73), rows)
    pdf.paragraph("Você pode usar os dois no mesmo computador.", MUTED, 10)


def page_install(pdf):
    pdf.section(1, "folder", "Instalação", "Faça uma vez em cada computador que emite notas.")
    pdf.steps([
        "Crie a pasta **C:\\PreDanfe** no computador.",
        "Copie para ela o **PreDANFE.exe** e/ou o **PreDANFE-Automatico.exe**.",
        "Abra um dos programas com dois cliques. Na primeira vez aparece a tela de **Configuração** "
        "(próximo passo).",
        "Se quiser, crie um atalho na Área de Trabalho: clique com o botão direito no programa → "
        "**Enviar para** → **Área de trabalho (criar atalho)**.",
    ])
    pdf.callout("O Windows pode pedir confirmação na primeira vez",
                "Se aparecer \"O Windows protegeu o computador\", clique em **Mais informações** → **Executar assim "
                "mesmo**. Se o antivírus bloquear, libere a pasta C:\\PreDanfe.")
    pdf.subtitle("Requisitos")
    pdf.bullets([
        "Windows 10 ou 11 (64 bits).",
        "O SysPDV funcionando nesse computador (o Pré-DANFE usa a mesma conexão com o servidor).",
        "Uma pasta onde o usuário possa gravar, como C:\\PreDanfe. Evite \"Arquivos de Programas\".",
    ])
    pdf.space(2)
    pdf.subtitle("Como a pasta fica depois de usar")
    tree = [
        ("folder", "C:\\PreDanfe", "", TEXT),
        ("document", "PreDANFE.exe", "programa sob demanda", TEXT),
        ("document", "PreDANFE-Automatico.exe", "programa automático", TEXT),
        ("sliders", "config.ini", "criado ao salvar a configuração", TEXT),
        ("folder", "pdf", "os pré-DANFEs gerados (PreDANFE_1532.pdf, ...)", TEXT),
    ]
    height = 8 + len(tree) * 8
    x, y = pdf.l_margin, pdf.get_y()
    pdf.set_fill_color(*CARD)
    pdf.set_draw_color(*BORDER)
    pdf.set_line_width(0.3)
    pdf.rect(x, y, pdf.content_width, height, style="DF", round_corners=True, corner_radius=4)
    for i, (icon, name, note, color) in enumerate(tree):
        indent = 0 if i == 0 else 8
        yy = y + 5 + i * 8
        if i:
            pdf.set_draw_color(*BORDER)
            pdf.line(x + 8.5, yy - 4.5, x + 8.5, yy + 2.6)
            pdf.line(x + 8.5, yy + 2.6, x + 12, yy + 2.6)
        pdf.image(str(TMP / f"ic_{icon}.png"), x=x + 6 + indent, y=yy, w=5)
        pdf.set_xy(x + 13 + indent, yy)
        pdf.set_font("Mono", size=10)
        pdf.set_text_color(*color)
        pdf.cell(62, 5, name)
        pdf.set_font("Segoe", size=9.5)
        pdf.set_text_color(*FAINT)
        pdf.cell(0, 5, note)
    pdf.set_y(y + height + 4)


def page_config(pdf):
    pdf.add_page()
    pdf.section(2, "database", "Primeira configuração",
                "Na primeira vez, os programas pedem os dados de acesso ao banco do SysPDV.")
    pdf.figure(TMP / "config.png", 128, "Tela de configuração (os números indicam os itens explicados abaixo)")
    items = [
        "**Servidor, porta e arquivo do banco** já vêm preenchidos com o que o SysPDV deste computador usa. "
        "Normalmente não é preciso mudar.",
        "**Senha**: digite a senha do banco do SysPDV (**masterkey**).",
        "**Pasta dos PDFs**: onde os pré-DANFEs serão salvos. O padrão é a pasta **pdf**, dentro de C:\\PreDanfe.",
        "**Testar conexão**: confere se está tudo certo. Deve aparecer \"Conectou!\" em verde.",
        "**Salvar**: grava a configuração. Pronto, não será pedida de novo.",
    ]
    pdf.steps(items)
    pdf.callout("Dica para vários computadores",
                "A configuração fica no arquivo **config.ini**, ao lado dos programas. Depois de configurar um "
                "computador, copie esse arquivo para os outros que usam o mesmo servidor e pule este passo.")


def page_v1(pdf):
    pdf.add_page()
    pdf.section(3, "document", "Gerar por número (PreDANFE.exe)",
                "Para conferir uma nota específica antes de transmitir.")
    pdf.figure(TMP / "main.png", 88, "Janela do PreDANFE.exe (dados fictícios)")
    pdf.subtitle("O que tem na janela")
    pdf.steps([
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
    pdf.subtitle("Passo a passo")
    pdf.bullets([
        "Digite a NF-e na retaguarda do SysPDV e **salve sem transmitir**.",
        "No Pré-DANFE, digite o número e clique em **Gerar Pré-DANFE** (ou clique na nota da lista).",
        "Confira o PDF. Achou erro? Corrija a nota no SysPDV, salve e gere de novo.",
        "Tudo certo? Transmita a nota normalmente pelo SysPDV.",
    ])


def page_v2(pdf):
    pdf.add_page()
    pdf.section(4, "layers", "Modo automático (PreDANFE-Automatico.exe)",
                "Gera o pré-DANFE sozinho, sem você precisar abrir nada.")
    pdf.paragraph(
        "Depois de aberto, o programa fica rodando **ao lado do relógio do Windows** (perto da data e hora). "
        "A cada 10 segundos ele verifica se há NF-e salva e ainda não transmitida. Para cada nota nova ou "
        "alterada, ele gera o PDF na pasta dos pré-DANFEs e mostra um aviso no canto da tela.")
    pdf.subtitle("Como ligar")
    pdf.steps([
        "Abra o **PreDANFE-Automatico.exe** com dois cliques. Nenhuma janela abre: aparece só o ícone "
        "perto do relógio.",
        "Na primeira vez, preencha a configuração (Passo 2).",
        "Responda **Sim** em \"Iniciar junto com o Windows\". Assim ele liga sozinho todo dia.",
    ])
    pdf.callout("Não achou o ícone?",
                "O Windows às vezes esconde ícones. Clique na **setinha ( ^ )** ao lado do relógio para ver os "
                "ícones ocultos. Você pode arrastar o ícone do Pré-DANFE para a barra, para deixá-lo sempre visível.")

    pdf.subtitle("Menu do ícone (clique com o botão direito)")
    items = [("folder", "Abrir pasta dos Pré-DANFEs",
              "Mostra os PDFs gerados (o mesmo que dar dois cliques no ícone)."),
             ("refresh", "Verificar agora", "Procura notas novas na hora, sem esperar os 10 segundos."),
             ("sliders", "Configurações...", "Muda servidor, senha ou pasta dos PDFs."),
             ("arrow", "Iniciar com o Windows", "Liga ou desliga o início automático."),
             ("info", "Sobre...", "Versão do programa e contato da PBtec."),
             ("document", "Sair", "Fecha o programa. Os PDFs param de ser gerados até abrir de novo.")]
    height = 10 + len(items) * 10
    pdf.ensure_space(height + 4)
    x, y = pdf.l_margin, pdf.get_y()
    pdf.set_fill_color(*CARD)
    pdf.set_draw_color(*BORDER)
    pdf.rect(x, y, pdf.content_width, height, style="DF", round_corners=True, corner_radius=4)
    pdf.set_xy(x + 6, y + 4)
    pdf.set_font("Segoe", size=9)
    pdf.set_text_color(*FAINT)
    pdf.cell(0, 4, "Primeira linha do menu: quantas notas estão pendentes e a hora da última verificação.")
    for i, (icon, name, desc) in enumerate(items):
        yy = y + 10.5 + i * 10
        pdf.image(str(TMP / f"ic_{icon}.png"), x=x + 6, y=yy + 0.6, w=5)
        pdf.set_xy(x + 14, yy)
        pdf.set_font("SegoeSB", size=10.5)
        pdf.set_text_color(*TEXT)
        pdf.cell(60, 5, name)
        pdf.set_xy(x + 14, yy + 5)
        pdf.set_font("Segoe", size=9.5)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 4.5, desc)
    pdf.set_y(y + height + 6)

    pdf.subtitle("Bom saber")
    pdf.bullets([
        "Os arquivos se chamam **PreDANFE_número.pdf** (exemplo: PreDANFE_1532.pdf).",
        "Se você alterar a nota no SysPDV, o PDF é refeito sozinho com as alterações.",
        "O programa espera a nota ficar igual por duas verificações seguidas antes de gerar, para não pegar "
        "a nota no meio da digitação. Por isso o PDF aparece de 10 a 20 segundos depois de salvar.",
        "Ele gera o PDF de **todas** as notas pendentes do banco, inclusive as digitadas em outros computadores.",
    ])


def page_predanfe(pdf):
    pdf.add_page()
    pdf.section(5, "document", "Entendendo o pré-DANFE", "O que conferir antes de transmitir.")
    pdf.figure(TMP / "sample.png", pdf.content_width, "Parte de cima de um pré-DANFE (dados fictícios)")

    def column(x, w, title, items):
        pdf.set_xy(x, pdf.get_y())
        pdf.set_font("SegoeSB", size=12)
        pdf.set_text_color(*TEXT)
        pdf.cell(w, 7, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.space(1)
        pdf.bullets(items, x=x, width=w, size=10)

    half = (pdf.content_width - 8) / 2
    x1, x2 = pdf.l_margin, pdf.l_margin + half + 8
    y0 = pdf.get_y()
    column(x1, half, "Igual ao DANFE final", [
        "Emitente, destinatário e chave de acesso",
        "Produtos, quantidades, valores, CFOP, NCM e CST",
        "ICMS e substituição tributária",
        "**PIS e COFINS** (calculados como o SysPDV faz ao transmitir)",
        "**Valor aproximado dos tributos** (IBPT) e o texto com os valores federal e estadual",
        "Fatura e totais da nota",
    ])
    end_left = pdf.get_y()
    pdf.set_y(y0)
    column(x2, half, "Pode ser só uma estimativa", [
        "**Tributos aproximados** de produto cujo NCM ainda não saiu em nenhuma nota transmitida. "
        "O pré-DANFE avisa: \"TRIBUTOS APROXIMADOS ESTIMADOS PARA NCM ...\".",
    ])
    pdf.space(1)
    column(x2, half, "Como reconhecer", [
        "Marca **SEM VALOR FISCAL – PRÉ-VISUALIZAÇÃO**",
        "Protocolo: **NÃO TRANSMITIDA**",
    ])
    pdf.set_y(max(end_left, pdf.get_y()) + 2)


def page_faq(pdf):
    pdf.add_page()
    pdf.section("DÚVIDAS", "sliders", "Problemas comuns e soluções")
    rows = [
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
    pdf.table_rows((62, 112), [("Situação", "O que fazer")] + rows)
    pdf.space(2)
    pdf.callout("Precisa de ajuda?",
                f"Fale com a **{COMPANY}** pelo telefone **{PHONE}**. Se for um erro, informe o que apareceu "
                "na tela. O programa também guarda um registro de erros na pasta **%LOCALAPPDATA%\\PreDANFE** "
                "(digite esse endereço na barra do Explorador de Arquivos).")


def credits(pdf):
    pdf.space(2)
    height = max(32, 16 + 8 * len(DEVELOPERS))
    pdf.ensure_space(height + 12)
    pdf.subtitle("Créditos")
    x, y = pdf.l_margin, pdf.get_y()
    pdf.set_fill_color(*CARD)
    pdf.set_draw_color(*BORDER)
    pdf.set_line_width(0.3)
    pdf.rect(x, y, pdf.content_width, height, style="DF", round_corners=True, corner_radius=4)
    middle = x + pdf.content_width * 0.52

    def line(x0, icon, text, yy, family="Segoe", size=10.5):
        pdf.image(str(TMP / f"ic_{icon}.png"), x=x0, y=yy + 0.2, w=5)
        pdf.set_xy(x0 + 8, yy)
        pdf.set_font(family, size=size)
        pdf.set_text_color(*TEXT)
        pdf.cell(80, 5.5, text)

    line(x + 7, "document", f"Pré-DANFE · versão {VERSION}", y + 6, "SegoeSB", 11)
    line(x + 7, "layers", COMPANY, y + 14)
    line(x + 7, "phone", PHONE, y + 22)
    pdf.set_draw_color(*BORDER)
    pdf.line(middle - 4, y + 6, middle - 4, y + height - 6)
    pdf.set_xy(middle + 2, y + 6)
    pdf.set_font("Mono", size=8)
    pdf.set_char_spacing(1.6)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 5.5, "DESENVOLVIMENTO E ANÁLISE")
    pdf.set_char_spacing(0)
    for i, name in enumerate(DEVELOPERS):
        line(middle + 2, "user", name, y + 14 + 8 * i)
    pdf.set_y(y + height + 4)


def main():
    prepare_images()
    pdf = Manual()
    cover(pdf)
    page_intro(pdf)
    pdf.add_page()
    page_install(pdf)
    page_config(pdf)
    page_v1(pdf)
    page_v2(pdf)
    page_predanfe(pdf)
    page_faq(pdf)
    credits(pdf)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUTPUT))
    print("Manual gerado:", OUTPUT, f"({pdf.page_no()} páginas)")


if __name__ == "__main__":
    main()
