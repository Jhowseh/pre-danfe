"""Visual das janelas, no estilo dos SVGs de docs/referencia-visual (paleta Primer
do GitHub, claro/escuro, barra em degradê ciano→violeta, ícones de traço violeta,
cartões com cantos de 12 px e botões em pílula).

As formas arredondadas e os ícones são desenhados com Pillow em resolução maior
e reduzidos, para ficarem suaves (o Canvas do Tk não suaviza bordas).
"""
import ctypes
import math
import time
import tkinter as tk
import tkinter.font as tkfont

from PIL import Image, ImageDraw, ImageTk

CLARO = {
    "bg": "#FFFFFF", "card": "#F6F8FA", "borda": "#D1D9E0", "texto": "#1F2328",
    "suave": "#59636E", "fraco": "#656D76", "link": "#0969DA", "hover": "#EEF1F4",
    "campo": "#FFFFFF", "verde": "#1A7F37", "vermelho": "#CF222E", "amarelo": "#9A6700",
}
ESCURO = {
    "bg": "#0D1117", "card": "#151B23", "borda": "#30363D", "texto": "#E6EDF3",
    "suave": "#9198A1", "fraco": "#7D8590", "link": "#4493F8", "hover": "#1C232D",
    "campo": "#0D1117", "verde": "#3FB950", "vermelho": "#F85149", "amarelo": "#D29922",
}
DEGRADE = ("#22D3EE", "#8B5CF6")
VIOLETA = "#8B5CF6"
PONTO = {"ok": "#3FB950", "erro": "#F85149", "aviso": "#D29922", "neutro": "#8C959F"}

FONTE = "Segoe UI"
FONTE_MONO = "Consolas"


def ativar_dpi():
    """Janelas nítidas em telas com zoom (125%, 150%...). Chamar antes de criar o Tk."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


ICONE_JANELAS = None  # caminho do .ico do programa (definido por util_app.aplicar_icone)
_icones_carregados = []  # o Windows usa os ícones enquanto a janela existir


def icone_na_barra(janela):
    """Manda o .ico direto para a janela (WM_SETICON).

    Sem isso a barra de tarefas fica com a pena do Tk: ela guarda o ícone que a janela
    tinha ao nascer e não percebe a troca feita pelo `iconbitmap`.
    """
    if ICONE_JANELAS is None:
        return
    try:
        u = ctypes.windll.user32
        u.LoadImageW.restype = ctypes.c_void_p
        u.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_uint]
        u.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p]
        hwnd = u.GetParent(janela.winfo_id())  # a moldura da janela, que aparece na barra
        # ICON_BIG (barra de tarefas, Alt+Tab) e ICON_SMALL (barra de título), no tamanho do DPI atual
        for tipo, metrica in ((1, 11), (0, 49)):  # SM_CXICON, SM_CXSMICON
            tam = u.GetSystemMetrics(metrica)
            h = u.LoadImageW(None, str(ICONE_JANELAS), 1, tam, tam, 0x10)  # IMAGE_ICON, LR_LOADFROMFILE
            if h:
                _icones_carregados.append(h)
                u.SendMessageW(hwnd, 0x80, tipo, h)  # WM_SETICON
    except (AttributeError, OSError, tk.TclError):
        pass


def windows_escuro():
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def _rgb(cor):
    cor = cor.lstrip("#")
    return tuple(int(cor[i:i + 2], 16) for i in (0, 2, 4))


def misturar(c1, c2, t):
    a, b = _rgb(c1), _rgb(c2)
    return "#%02X%02X%02X" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


PULSO_CICLO = 2.0      # segundos por pulso
PULSO_QUADROS = 120    # quadros por ciclo (~60 por segundo)


def _pulso_imagem(cor, f, escala, ss=4):
    """Um quadro do ponto de status: anel que cresce de 4 a 10 px e some, com o ponto por cima.
    Desenhado em resolução 4x e reduzido, para crescer sem 'saltos' de pixel inteiro."""
    esp = max(1.0, 1.5 * escala)
    lado = int(math.ceil(2 * (10 * escala + esp))) + 2
    grande = lado * ss
    c = grande / 2
    rgb = _rgb(cor)

    anel = Image.new("RGBA", (grande, grande), rgb + (0,))
    suave = 1 - (1 - f) ** 3  # rápido no começo, desacelera no fim
    r = (4 + 6 * suave) * escala * ss + esp * ss / 2
    ImageDraw.Draw(anel).ellipse((c - r, c - r, c + r, c + r), outline=rgb + (255,), width=max(1, round(esp * ss)))
    anel = anel.resize((lado, lado), Image.LANCZOS)
    opacidade = 0.8 * (1 - f)  # chega a zero no fim do ciclo, sem "estalo" ao recomeçar
    anel.putalpha(anel.getchannel("A").point(lambda v: round(v * opacidade)))

    ponto = Image.new("RGBA", (grande, grande), rgb + (0,))
    rp = 4 * escala * ss
    ImageDraw.Draw(ponto).ellipse((c - rp, c - rp, c + rp, c + rp), fill=rgb + (255,))
    ponto = ponto.resize((lado, lado), Image.LANCZOS)
    return Image.alpha_composite(anel, ponto)


def _degrade(w, h, cores):
    linha = Image.new("RGBA", (max(w, 2), 1))
    for x in range(linha.width):
        linha.putpixel((x, 0), _rgb(misturar(cores[0], cores[1], x / (linha.width - 1))) + (255,))
    return linha.resize((w, h))


def forma_arredondada(w, h, raio, fundo=None, borda=None, degrade=None, espessura=1, ss=4):
    """Retângulo arredondado suave (Pillow) com fundo liso ou em degradê."""
    W, H, R = w * ss, h * ss, raio * ss
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    mascara = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mascara).rounded_rectangle([0, 0, W - 1, H - 1], R, fill=255)
    base = _degrade(W, H, degrade) if degrade else Image.new("RGBA", (W, H), _rgb(fundo) + (255,))
    img.paste(base, (0, 0), mascara)
    if borda:
        e = espessura * ss
        ImageDraw.Draw(img).rounded_rectangle([e / 2, e / 2, W - 1 - e / 2, H - 1 - e / 2], R - e / 2,
                                              outline=_rgb(borda) + (255,), width=e)
    return img.resize((w, h), Image.LANCZOS)


# ------------------------------------------------------------------ ícones

def _desenhar_icone(nome, d, k, cor, w):
    """Ícones de traço no estilo dos SVGs (grade 24x24, traço 2, pontas redondas)."""
    def p(x, y):
        return (x * k, y * k)

    def linha(*pts):
        pts = [p(*q) for q in pts]
        d.line(pts, fill=cor, width=w, joint="curve")
        for x, y in (pts[0], pts[-1]):
            d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=cor)

    def arco(cx, cy, r, ini, fim):
        d.arc([p(cx - r, cy - r), p(cx + r, cy + r)], ini, fim, fill=cor, width=w)

    def elipse(x0, y0, x1, y1):
        d.ellipse([p(x0, y0), p(x1, y1)], outline=cor, width=w)

    if nome == "documento":  # file-text
        linha((14, 2), (6, 2))
        arco(6, 4, 2, 180, 270)
        linha((4, 4), (4, 20))
        arco(6, 20, 2, 90, 180)
        linha((6, 22), (18, 22))
        arco(18, 20, 2, 0, 90)
        linha((20, 20), (20, 8), (14, 2))
        linha((14, 2), (14, 8), (20, 8))
        linha((8, 13), (16, 13))
        linha((8, 17), (16, 17))
        linha((8, 9), (10, 9))
    elif nome == "pasta":  # folder (docs/referencia-visual/icons/folder.svg)
        linha((4.5, 5), (9, 5), (11, 7.5), (19.5, 7.5), (21, 9), (21, 18.5), (19.5, 20),
              (4.5, 20), (3, 18.5), (3, 6.5), (4.5, 5))
    elif nome == "camadas":  # layers (docs/referencia-visual/icons/layers.svg)
        linha((12, 3), (2, 8), (12, 13), (22, 8), (12, 3))
        linha((2, 13), (12, 18), (22, 13))
        linha((2, 17.5), (12, 22.5), (22, 17.5))
    elif nome == "atualizar":  # refresh-cw
        arco(12, 12, 9, 185, 320)
        linha((21, 3), (21, 8), (16, 8))
        arco(12, 12, 9, 5, 140)
        linha((3, 21), (3, 16), (8, 16))
    elif nome == "ajustes":  # sliders-horizontal
        for y, a, b in ((4, 14, 10), (12, 12, 8), (20, 16, 12)):
            linha((21, y), (a, y))
            linha((b, y), (3, y))
        linha((14, 2), (14, 6))
        linha((8, 10), (8, 14))
        linha((16, 18), (16, 22))
    elif nome == "banco":  # database
        elipse(3, 2, 21, 8)
        linha((3, 5), (3, 19))
        linha((21, 5), (21, 19))
        d.arc([p(3, 9), p(21, 15)], 0, 180, fill=cor, width=w)   # meio do cilindro
        d.arc([p(3, 16), p(21, 22)], 0, 180, fill=cor, width=w)  # base
    elif nome == "seta":  # arrow-right
        linha((5, 12), (19, 12))
        linha((12, 5), (19, 12), (12, 19))
    elif nome == "info":  # info
        elipse(2, 2, 22, 22)
        linha((12, 16), (12, 12))
        r = w * 0.65
        cx, cy = p(12, 8)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=cor)
    elif nome == "usuario":  # docs/referencia-visual/icons/user.svg
        elipse(8, 4, 16, 12)
        arco(12, 21, 8, 180, 360)  # ombros: meia-volta de (4,21) a (20,21)
    elif nome == "telefone":  # smartphone
        d.rounded_rectangle([p(5, 2), p(19, 22)], radius=2.5 * k, outline=cor, width=w)
        linha((11, 18), (13, 18))


def logo_pbtec(altura, cor_clara, caminho):
    """Logo da PBtec sem o fundo preto, na altura pedida.

    A transparência vem do brilho de cada ponto (preto = transparente). O
    vermelho do "PB" é mantido; o branco vira `cor_clara` (branco no tema escuro,
    grafite no tema claro, para aparecer sobre fundo branco).
    """
    img = Image.open(caminho).convert("RGB")
    nova = Image.new("RGBA", img.size)
    cor_clara = _rgb(cor_clara)
    pontos = []
    dados = img.get_flattened_data() if hasattr(img, "get_flattened_data") else img.getdata()
    for r, g, b in dados:
        a = max(r, g, b)
        if a < 24:
            pontos.append((0, 0, 0, 0))
        elif r > 90 and r > g * 1.8 and r > b * 1.8:  # vermelho do "PB"
            pontos.append((round(r * 255 / a), round(g * 255 / a), round(b * 255 / a), a))
        else:
            pontos.append(cor_clara + (a,))
    nova.putdata(pontos)
    nova = nova.crop(nova.getbbox())
    largura = max(1, round(nova.width * altura / nova.height))
    return nova.resize((largura, altura), Image.LANCZOS)


def logo_pronto(altura, caminho):
    """Logo que já vem com fundo transparente (versão colorida, para tema claro)."""
    img = Image.open(caminho).convert("RGBA")
    img = img.crop(img.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox())
    largura = max(1, round(img.width * altura / img.height))
    return img.resize((largura, altura), Image.LANCZOS)


def icone(nome, cor, tam, ss=8):
    S = tam * ss
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    _desenhar_icone(nome, ImageDraw.Draw(img), S / 24, _rgb(cor) + (255,), max(1, round(2 * S / 24)))
    return img.resize((tam, tam), Image.LANCZOS)


# ------------------------------------------------------------------ tema

class Tema:
    def __init__(self, janela, escuro=None):
        self.escuro = windows_escuro() if escuro is None else escuro
        self.c = ESCURO if self.escuro else CLARO
        self.escala = max(1.0, janela.winfo_fpixels("1i") / 96)
        self._imagens = {}
        self.fontes = {
            "rotulo": tkfont.Font(janela, family=FONTE_MONO, size=9),
            "titulo": tkfont.Font(janela, family=FONTE, size=22, weight="bold"),
            "subtitulo": tkfont.Font(janela, family=FONTE, size=11),
            "secao": tkfont.Font(janela, family=FONTE + " Semibold", size=12),
            "corpo": tkfont.Font(janela, family=FONTE, size=10),
            "pequeno": tkfont.Font(janela, family=FONTE, size=9),
            "forte": tkfont.Font(janela, family=FONTE + " Semibold", size=11),
            "botao": tkfont.Font(janela, family=FONTE + " Semibold", size=10),
            "numero": tkfont.Font(janela, family=FONTE + " Semibold", size=16),
        }

    def px(self, v):
        return int(round(v * self.escala))

    def foto(self, chave, criar):
        """PhotoImage em cache (o Tk apaga imagens sem referência)."""
        if chave not in self._imagens:
            self._imagens[chave] = ImageTk.PhotoImage(criar())
        return self._imagens[chave]

    def icone(self, nome, cor=VIOLETA, tam=18):
        t = self.px(tam)
        return self.foto(("ic", nome, cor, t), lambda: icone(nome, cor, t))

    def logo(self, altura):
        """Logo da PBtec para o tema atual (None se o arquivo não estiver disponível).

        Tema claro: logo colorido (pbtec_logo_light.png). Tema escuro: logo
        branco e vermelho (pbtec_logo.png, sem o fundo preto).
        """
        from banco import RECURSOS

        h = self.px(altura)
        if not self.escuro:
            claro = RECURSOS / "recursos" / "pbtec_logo_light.png"
            if claro.exists():
                return self.foto(("logo-claro", h), lambda: logo_pronto(h, claro))
        caminho = RECURSOS / "recursos" / "pbtec_logo.png"
        if not caminho.exists():
            return None
        cor = "#FFFFFF" if self.escuro else self.c["texto"]
        return self.foto(("logo", h, cor), lambda: logo_pbtec(h, cor, caminho))

    def preparar_janela(self, janela, titulo):
        janela.title(titulo)
        janela.configure(bg=self.c["bg"])
        janela.resizable(False, False)
        janela.update_idletasks()
        icone_na_barra(janela)
        if self.escuro:  # barra de título escura no Windows 10/11
            try:
                hwnd = ctypes.windll.user32.GetParent(janela.winfo_id())
                valor = ctypes.c_int(1)
                for atributo in (20, 19):
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, atributo, ctypes.byref(valor), 4)
            except (AttributeError, OSError):
                pass

    def label(self, pai, texto="", fonte="corpo", cor="texto", fundo="bg", **kw):
        return tk.Label(pai, text=texto, font=self.fontes[fonte], fg=self.c.get(cor, cor),
                        bg=self.c.get(fundo, fundo), **kw)

    def frame(self, pai, fundo="bg", **kw):
        return tk.Frame(pai, bg=self.c.get(fundo, fundo), **kw)


# ------------------------------------------------------------------ componentes

class Cabecalho(tk.Canvas):
    """Rótulo em monoespaçada, título, subtítulo, barra em degradê e ponto de status pulsando."""

    def __init__(self, pai, tema, largura, rotulo, titulo, subtitulo, com_status=True, com_logo=True):
        t = tema
        self.t = t
        altura = t.px(122 if com_status else 104)
        super().__init__(pai, width=largura, height=altura, bg=t.c["bg"], highlightthickness=0, bd=0)
        logo = t.logo(96 if com_status else 84) if com_logo else None
        if logo is not None:  # logo da PBtec no canto direito
            self.create_image(largura, t.px(2), image=logo, anchor="ne")
        x = 0
        espaco = t.px(2.5)
        for ch in rotulo.upper():
            self.create_text(x, t.px(6), text=ch, anchor="nw", font=t.fontes["rotulo"], fill=t.c["suave"])
            x += t.fontes["rotulo"].measure(ch) + espaco
        self.create_text(-t.px(2), t.px(22), text=titulo, anchor="nw", font=t.fontes["titulo"], fill=t.c["texto"])
        self.create_text(0, t.px(66), text=subtitulo, anchor="nw", font=t.fontes["subtitulo"], fill=t.c["suave"])
        y = t.px(100)
        barra = t.foto(("barra", t.px(56)), lambda: forma_arredondada(t.px(56), max(2, t.px(3)), max(1, t.px(1.5)),
                                                                    degrade=DEGRADE))
        self.create_image(0, y, image=barra, anchor="w")
        self._fase = 0
        self._cor = PONTO["ok"]
        if com_status:
            cx = t.px(80)
            self._cx, self._cy = cx, y
            self._quadros = {}  # (cor, índice) -> PhotoImage, gerados sob demanda
            self._inicio = time.perf_counter()
            self._pulso = self.create_image(cx, y, image=self._quadro(0), anchor="center")
            # só a bolinha aparece; a frase do status fica numa dica ao passar o mouse
            zona = t.px(12)
            self.create_rectangle(cx - zona, y - zona, cx + zona, y + zona, outline="", fill="", tags=("status",))
            self.tag_raise("status")
            self._dica_texto = ""
            self._dica = None
            self.tag_bind("status", "<Enter>", self._mostrar_dica)
            self.tag_bind("status", "<Leave>", self._esconder_dica)
            self._animacao = self.after(16, self._pulsar)
            self.bind("<Destroy>", lambda _e: (self.after_cancel(self._animacao), self._esconder_dica()))

    def status(self, texto, tipo="ok"):
        """Verde = conectado; vermelho = sem conexão; cinza = conectando. A frase vira dica."""
        self._cor = PONTO.get(tipo, PONTO["neutro"])
        self._fase = -1  # força redesenhar já com a cor nova
        self._desenhar_pulso()
        self._dica_texto = texto
        if self._dica is not None:
            self._esconder_dica()
            self._mostrar_dica()

    def _mostrar_dica(self, _evento=None):
        if not self._dica_texto or self._dica is not None:
            return
        t = self.t
        dica = tk.Toplevel(self)
        dica.overrideredirect(True)
        dica.attributes("-topmost", True)
        dica.configure(bg=t.c["borda"])
        tk.Label(dica, text=self._dica_texto, font=t.fontes["pequeno"], fg=t.c["texto"], bg=t.c["card"],
                 padx=t.px(10), pady=t.px(5)).pack(padx=1, pady=1)
        x = self.winfo_rootx() + self._cx + t.px(14)
        y = self.winfo_rooty() + self._cy - t.px(14)
        dica.geometry(f"+{x}+{y}")
        self._dica = dica

    def _esconder_dica(self, _evento=None):
        if self._dica is not None:
            try:
                self._dica.destroy()
            except tk.TclError:
                pass
            self._dica = None

    def _quadro(self, i):
        chave = (self._cor, i)
        foto = self._quadros.get(chave)
        if foto is None:
            img = _pulso_imagem(self._cor, i / PULSO_QUADROS, self.t.escala)
            foto = self._quadros[chave] = ImageTk.PhotoImage(img, master=self)
        return foto

    def _desenhar_pulso(self):
        # a fase vem do relógio, então um atraso do Tk não deixa o pulso mais lento
        fase = ((time.perf_counter() - self._inicio) % PULSO_CICLO) / PULSO_CICLO
        i = int(fase * PULSO_QUADROS) % PULSO_QUADROS
        if i != self._fase:
            self._fase = i
            self.itemconfig(self._pulso, image=self._quadro(i))

    def _pulsar(self):
        # anel que cresce de 4 a 10 px e some em 2 s, como no header-*.svg
        self._desenhar_pulso()
        # o relógio do Windows anda de ~15,6 em ~15,6 ms: pedir 8 ms dá ~60 quadros/s (16 daria ~30)
        self._animacao = self.after(8, self._pulsar)


class Botao(tk.Canvas):
    """Botão em pílula. primario=True: fundo em degradê e texto branco."""

    def __init__(self, pai, tema, texto, comando, icone=None, primario=False, altura=40, fundo="bg", largura=None):
        t = self.t = tema
        self.comando = comando
        self.ativo = True
        h = t.px(altura)
        fonte = t.fontes["botao"]
        tam_ic = t.px(16) if icone else 0
        folga = t.px(8) if icone and texto else 0
        conteudo = tam_ic + folga + fonte.measure(texto)
        w = t.px(largura) if largura else conteudo + t.px(40)
        super().__init__(pai, width=w, height=h, bg=t.c.get(fundo, fundo), highlightthickness=0, bd=0, cursor="hand2")

        r = h // 2
        if primario:
            cor_txt = "#FFFFFF"
            normal = t.foto(("bp", w, h), lambda: forma_arredondada(w, h, r, degrade=DEGRADE))
            claro = tuple(misturar(c, "#FFFFFF", 0.15) for c in DEGRADE)
            sobre = t.foto(("bph", w, h), lambda: forma_arredondada(w, h, r, degrade=claro))
            apagado = tuple(misturar(c, t.c["bg"], 0.55) for c in DEGRADE)
            inativo = t.foto(("bpi", w, h, t.escuro), lambda: forma_arredondada(w, h, r, degrade=apagado))
            cor_ic = "#FFFFFF"
        else:
            cor_txt = t.c["texto"]
            normal = t.foto(("bs", w, h, t.escuro), lambda: forma_arredondada(w, h, r, t.c["card"], t.c["borda"]))
            sobre = t.foto(("bsh", w, h, t.escuro), lambda: forma_arredondada(w, h, r, t.c["hover"], t.c["borda"]))
            inativo = normal
            cor_ic = VIOLETA
        self._imgs = {"normal": normal, "sobre": sobre, "inativo": inativo}
        self._fundo = self.create_image(0, 0, image=normal, anchor="nw")
        x = (w - conteudo) // 2
        if icone:
            self.create_image(x, h // 2, image=t.icone(icone, cor_ic, 16), anchor="w")
            x += tam_ic + folga
        self._txt = self.create_text(x, h // 2, text=texto, anchor="w", font=fonte, fill=cor_txt)
        self._cor_txt = cor_txt
        self.bind("<Enter>", lambda _e: self.ativo and self.itemconfig(self._fundo, image=sobre))
        self.bind("<Leave>", lambda _e: self.ativo and self.itemconfig(self._fundo, image=normal))
        self.bind("<ButtonRelease-1>", self._clique)

    def _clique(self, evento):
        dentro = 0 <= evento.x <= self.winfo_width() and 0 <= evento.y <= self.winfo_height()
        if self.ativo and dentro and self.comando:
            self.comando()

    def habilitar(self, sim):
        self.ativo = sim
        self.itemconfig(self._fundo, image=self._imgs["normal" if sim else "inativo"])
        self.itemconfig(self._txt, fill=self._cor_txt if sim else misturar(self._cor_txt, self.t.c["bg"], 0.4))
        self.config(cursor="hand2" if sim else "arrow")


class Campo(tk.Canvas):
    """Caixa de texto arredondada; a borda fica azul quando recebe o foco."""

    def __init__(self, pai, tema, largura, altura=40, fonte="corpo", show="", dica="", justify="left",
                 valor="", fundo="bg"):
        t = self.t = tema
        w, h = t.px(largura), t.px(altura)
        super().__init__(pai, width=w, height=h, bg=t.c.get(fundo, fundo), highlightthickness=0, bd=0)
        r = t.px(8)
        normal = t.foto(("cp", w, h, t.escuro), lambda: forma_arredondada(w, h, r, t.c["campo"], t.c["borda"]))
        foco = t.foto(("cpf", w, h, t.escuro),
                      lambda: forma_arredondada(w, h, r, t.c["campo"], t.c["link"], espessura=2))
        self._fundo = self.create_image(0, 0, image=normal, anchor="nw")
        self.dica, self._show, self._na_dica = dica, show, False
        self.entry = tk.Entry(self, relief="flat", bd=0, highlightthickness=0, font=t.fontes[fonte],
                              bg=t.c["campo"], fg=t.c["texto"], insertbackground=t.c["texto"],
                              justify=justify, show=show, disabledbackground=t.c["campo"])
        m = t.px(12)
        self.create_window(m, h // 2, window=self.entry, anchor="w", width=w - 2 * m)
        self.entry.bind("<FocusIn>", lambda _e: (self.itemconfig(self._fundo, image=foco), self._tirar_dica()))
        self.entry.bind("<FocusOut>", lambda _e: (self.itemconfig(self._fundo, image=normal), self._por_dica()))
        self.bind("<Button-1>", lambda _e: self.entry.focus_set())
        if valor:
            self.entry.insert(0, valor)
        self._por_dica()

    def _por_dica(self):
        if self.dica and not self.entry.get():
            self._na_dica = True
            self.entry.config(show="", fg=self.t.c["fraco"])
            self.entry.insert(0, self.dica)

    def _tirar_dica(self):
        if self._na_dica:
            self._na_dica = False
            self.entry.delete(0, "end")
            self.entry.config(show=self._show, fg=self.t.c["texto"])

    def get(self):
        return "" if self._na_dica else self.entry.get().strip()

    def set(self, texto):
        self._tirar_dica()
        self.entry.delete(0, "end")
        self.entry.insert(0, texto)
        if self.focus_get() is not self.entry:
            self._por_dica()

    def focar(self):
        self.entry.focus_set()


def titulo_secao(pai, tema, icone_nome, texto, fundo="bg"):
    """Ícone violeta + título, como os '### <ícone> Seção' do README."""
    f = tema.frame(pai, fundo)
    tk.Label(f, image=tema.icone(icone_nome, VIOLETA, 20), bg=tema.c[fundo]).pack(side="left")
    tema.label(f, texto, "secao", fundo=fundo).pack(side="left", padx=(tema.px(8), 0))
    return f
