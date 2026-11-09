"""Menu do ícone perto do relógio, no mesmo visual das outras telas e do manual:
ícone violeta, título e uma linha de explicação em cada opção.

O menu padrão do Windows só mostra texto, por isso este é uma janelinha sem
moldura que abre onde o mouse está e fecha ao clicar fora ou teclar Esc.
"""
import ctypes
import tkinter as tk
from ctypes import wintypes

from PIL import Image

import tema as tm

_u32 = ctypes.WinDLL("user32")
_u32.GetForegroundWindow.restype = wintypes.HWND
_u32.SetForegroundWindow.argtypes = [wintypes.HWND]
_u32.GetAncestor.restype = wintypes.HWND
_u32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
_u32.GetAsyncKeyState.restype = ctypes.c_short
_u32.MonitorFromPoint.restype = wintypes.HMONITOR
_u32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]


class _InfoMonitor(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


_u32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(_InfoMonitor)]


def _area_util(x, y):
    """Área livre (sem a barra de tarefas) do monitor onde está o mouse."""
    try:
        mon = _u32.MonitorFromPoint(wintypes.POINT(x, y), 2)  # MONITOR_DEFAULTTONEAREST
        info = _InfoMonitor()
        info.cbSize = ctypes.sizeof(info)
        if mon and _u32.GetMonitorInfoW(mon, ctypes.byref(info)):
            r = info.rcWork
            return r.left, r.top, r.right, r.bottom
    except (AttributeError, OSError):
        pass
    return None


class Opcao:
    """Uma linha do menu. Com `ligado` (função que diz se está ligado), mostra uma
    chavinha à direita e o clique só liga/desliga, sem fechar o menu."""

    def __init__(self, icone, titulo, descricao, acao, ligado=None):
        self.icone, self.titulo, self.descricao = icone, titulo, descricao
        self.acao, self.ligado = acao, ligado


SEPARADOR = None


class MenuBandeja:
    def __init__(self, root):
        self.root = root
        self.janela = None

    # ------------------------------------------------------------ abrir / fechar

    def fechar(self, _evento=None):
        if self.janela is not None:
            janela, self.janela = self.janela, None
            try:
                janela.destroy()
            except tk.TclError:
                pass

    def abrir(self, status, opcoes):
        """status: função que devolve (texto, tipo) com tipo "ok", "erro" ou "neutro"."""
        self.fechar()
        t = self.t = tm.Tema(self.root)
        c = t.c
        self._status = status
        fundo = c["card"]
        sobre = tm.misturar(fundo, tm.VIOLETA, 0.12 if t.escuro else 0.08)
        f_titulo, f_desc = t.fontes["forte"], t.fontes["pequeno"]

        j = self.janela = tk.Toplevel(self.root)
        j.withdraw()
        j.overrideredirect(True)
        j.attributes("-topmost", True)
        j.configure(bg=c["borda"])  # 1 px de borda em volta do corpo
        corpo = tk.Frame(j, bg=fundo)
        corpo.pack(padx=1, pady=1)

        # medidas (todas as linhas com a mesma largura)
        fora, esq, ic, vao, dir_ = t.px(6), t.px(12), t.px(20), t.px(12), t.px(16)
        sw_w, sw_h = t.px(34), t.px(18)
        tem_chave = any(o is not SEPARADOR and o.ligado for o in opcoes)
        texto_w = max(max(f_titulo.measure(o.titulo), f_desc.measure(o.descricao))
                      for o in opcoes if o is not SEPARADOR)
        W = esq + ic + vao + texto_w + (sw_w + t.px(20) if tem_chave else 0) + dir_
        alt_t, alt_d = f_titulo.metrics("linespace"), f_desc.metrics("linespace")
        topo_txt = t.px(7)
        H = topo_txt + alt_t + t.px(1) + alt_d + t.px(8)
        destaque = t.foto(("menu-sobre", W, H, t.escuro), lambda: tm.forma_arredondada(W, H, t.px(6), sobre))

        # primeira linha: status do vigia
        topo = tk.Frame(corpo, bg=fundo)
        topo.pack(fill="x", padx=(fora + esq, fora + dir_), pady=(t.px(10), t.px(6)))
        self._ponto = tk.Label(topo, bg=fundo)
        self._ponto.pack(side="left", padx=(t.px(5), t.px(15)))
        self._texto_status = tk.Label(topo, font=f_desc, fg=c["fraco"], bg=fundo, anchor="w", justify="left",
                                      wraplength=W - esq - ic - vao)
        self._texto_status.pack(side="left", fill="x")
        self._atualizar_status()

        for op in opcoes:
            if op is SEPARADOR:
                tk.Frame(corpo, bg=c["borda"], height=1).pack(fill="x", padx=fora + t.px(6), pady=t.px(4))
                continue
            cv = tk.Canvas(corpo, width=W, height=H, bg=fundo, highlightthickness=0, bd=0, cursor="hand2")
            cv.pack(padx=fora)
            fundo_item = cv.create_image(0, 0, image=destaque, anchor="nw", state="hidden")
            meio_titulo = topo_txt + alt_t // 2
            cv.create_image(esq, meio_titulo, image=t.icone(op.icone, tm.VIOLETA, 20), anchor="w")
            x = esq + ic + vao
            cv.create_text(x, topo_txt, text=op.titulo, anchor="nw", font=f_titulo, fill=c["texto"])
            cv.create_text(x, topo_txt + alt_t + t.px(1), text=op.descricao, anchor="nw", font=f_desc,
                           fill=c["suave"])
            chave = None
            if op.ligado:
                chave = cv.create_image(W - dir_, H // 2, image=self._chave(op.ligado(), sw_w, sw_h), anchor="e")
            cv.bind("<Enter>", lambda _e, cv=cv, i=fundo_item: cv.itemconfig(i, state="normal"))
            cv.bind("<Leave>", lambda _e, cv=cv, i=fundo_item: cv.itemconfig(i, state="hidden"))
            cv.bind("<ButtonRelease-1>", lambda e, op=op, cv=cv, ch=chave: self._clique(e, op, cv, ch, sw_w, sw_h))
        tk.Frame(corpo, bg=fundo, height=t.px(6)).pack()

        j.bind("<Escape>", self.fechar)
        self._posicionar()
        j.deiconify()
        j.update_idletasks()
        self._hwnd = _u32.GetAncestor(j.winfo_id(), 2)  # GA_ROOT: a janela de verdade, não o miolo do Tk
        self._arredondar()
        try:
            _u32.SetForegroundWindow(self._hwnd)
        except OSError:
            pass
        j.focus_force()
        self._teve_foco = False
        j.after(60, self._vigiar)
        j.after(500, self._repetir_status)

    # ------------------------------------------------------------ desenho

    def _chave(self, ligado, w, h):
        """Chavinha liga/desliga: violeta com a bolinha à direita quando ligada."""
        t = self.t

        def criar():
            if ligado:
                img = tm.forma_arredondada(w, h, h // 2, degrade=tm.DEGRADE)
            else:
                img = tm.forma_arredondada(w, h, h // 2, t.c["borda"])
            d = h - t.px(4)
            bola = tm.forma_arredondada(d, d, d // 2, "#FFFFFF")
            camada = Image.new("RGBA", img.size, (0, 0, 0, 0))
            camada.paste(bola, (w - d - t.px(2) if ligado else t.px(2), t.px(2)))
            return Image.alpha_composite(img, camada)

        return t.foto(("chave", ligado, w, h, t.escuro), criar)

    def _atualizar_status(self):
        texto, tipo = self._status()
        t = self.t
        cor = tm.PONTO.get(tipo, tm.PONTO["neutro"])
        d = t.px(8)
        self._ponto.config(image=t.foto(("ponto", cor, d), lambda: tm.forma_arredondada(d, d, d // 2, cor)))
        self._texto_status.config(text=texto)

    def _repetir_status(self):
        if self.janela is None:
            return
        self._atualizar_status()
        self.janela.after(500, self._repetir_status)

    def _posicionar(self):
        """Canto de baixo à direita no mouse, como o menu do Windows, sem passar da área livre da tela."""
        j = self.janela
        j.update_idletasks()
        w, h = j.winfo_reqwidth(), j.winfo_reqheight()
        mx, my = j.winfo_pointerxy()
        area = _area_util(mx, my) or (0, 0, j.winfo_screenwidth(), j.winfo_screenheight())
        esq, cima, dir_, baixo = area
        x = mx - w if mx - w >= esq else mx
        x = max(esq, min(x, dir_ - w))
        y = min(my, baixo) - h
        if y < cima:  # barra de tarefas em cima: abre para baixo
            y = max(my, cima)
        y = max(cima, min(y, baixo - h))
        j.geometry(f"+{x}+{y}")

    def _arredondar(self):
        """Cantos arredondados no Windows 11 (no 10 o pedido é ignorado)."""
        try:
            valor = ctypes.c_int(2)  # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(self._hwnd, 33, ctypes.byref(valor), 4)
        except (AttributeError, OSError):
            pass

    # ------------------------------------------------------------ cliques

    def _clique(self, evento, op, cv, chave, sw_w, sw_h):
        if not (0 <= evento.x <= cv.winfo_width() and 0 <= evento.y <= cv.winfo_height()):
            return
        if op.ligado:
            op.acao()
            cv.itemconfig(chave, image=self._chave(op.ligado(), sw_w, sw_h))
            return
        self.fechar()
        self.root.after(10, op.acao)

    def _vigiar(self):
        """Fecha o menu quando outra janela ganha o foco ou quando há clique fora dele."""
        j = self.janela
        if j is None:
            return
        try:
            if _u32.GetForegroundWindow() == self._hwnd:
                self._teve_foco = True
            elif self._teve_foco:
                return self.fechar()
            if any(_u32.GetAsyncKeyState(b) & 0x8000 for b in (0x01, 0x02, 0x04)):
                mx, my = j.winfo_pointerxy()
                x0, y0 = j.winfo_rootx(), j.winfo_rooty()
                if not (x0 <= mx < x0 + j.winfo_width() and y0 <= my < y0 + j.winfo_height()):
                    return self.fechar()
        except tk.TclError:
            return
        j.after(60, self._vigiar)
