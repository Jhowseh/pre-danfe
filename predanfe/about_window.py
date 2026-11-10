import tkinter as tk

import theme as tm
from version import COMPANY, DEVELOPERS, PHONE, VERSION

WIDTH = 380
CARD_HEIGHT = 198
_open_window = None


def info_card(parent, t, width):
    W, H = t.px(width), t.px(CARD_HEIGHT)
    card = tk.Canvas(parent, width=W, height=H, bg=t.c["bg"], highlightthickness=0, bd=0)
    background = t.photo(("about-card", W, t.dark),
                         lambda: tm.rounded_shape(W, H, t.px(12), t.c["card"], t.c["border"]))
    card.create_image(0, 0, image=background, anchor="nw")
    m, y = t.px(18), t.px(18)
    f = t.fonts

    def icon_line(icon, text, font, y):
        card.create_image(m, y, image=t.icon(icon, tm.VIOLET, 18), anchor="w")
        card.create_text(m + t.px(28), y, text=text, anchor="w", font=f[font], fill=t.c["text"])

    icon_line("layers", COMPANY, "strong", y + t.px(10))
    icon_line("phone", PHONE, "body", y + t.px(40))
    card.create_line(m, y + t.px(66), W - m, y + t.px(66), fill=t.c["border"])
    card.create_text(m, y + t.px(86), text="DESENVOLVIMENTO E ANÁLISE", anchor="w",
                     font=f["label"], fill=t.c["muted"])
    for i, name in enumerate(DEVELOPERS):
        icon_line("user", name, "body", y + t.px(114 + 30 * i))
    return card


def _version_label(parent, t):
    return t.label(parent, " ".join(f"VERSÃO {VERSION}"), "label", "muted")


class Panel(tk.Frame):
    def __init__(self, parent, t, width, on_back):
        super().__init__(parent, bg=t.c["bg"])
        top = t.frame(self)
        top.pack(fill="x", pady=(t.px(18), t.px(10)))
        tm.section_title(top, t, "info", "Sobre o Pré-DANFE").pack(side="left")
        tm.Button(top, t, "Voltar", on_back, height=32).pack(side="right")
        _version_label(self, t).pack(anchor="w", pady=(0, t.px(10)))
        info_card(self, t, width).pack(anchor="w")


def show(master, theme=None):
    global _open_window
    if _open_window is not None and _open_window.winfo_exists():
        _open_window.deiconify()
        _open_window.lift()
        _open_window.focus_force()
        return _open_window

    window = tk.Toplevel(master)
    _open_window = window
    t = theme or tm.Theme(window)
    t.setup_window(window, "Sobre o Pré-DANFE")
    W = t.px(WIDTH)

    body = t.frame(window)
    body.pack(padx=t.px(32), pady=(t.px(26), t.px(24)))

    logo = t.logo(92)
    if logo is not None:
        tk.Label(body, image=logo, bg=t.c["bg"]).pack()
    t.label(body, "Pré-DANFE", "title").pack(pady=(t.px(10), 0))
    t.label(body, "Veja o DANFE da nota antes de transmitir no SysPDV.", "body", "muted",
            wraplength=W, justify="center").pack(pady=(t.px(2), 0))
    bar = t.photo(("about-bar", t.px(56)), lambda: tm.rounded_shape(t.px(56), max(2, t.px(3)),
                                                                    max(1, t.px(1.5)), gradient=tm.GRADIENT))
    tk.Label(body, image=bar, bg=t.c["bg"]).pack(pady=(t.px(10), t.px(6)))
    _version_label(body, t).pack()

    info_card(body, t, WIDTH).pack(pady=(t.px(18), 0))
    tm.Button(body, t, "Fechar", window.destroy, primary=True, width=WIDTH).pack(pady=(t.px(18), 0))

    def on_destroy(event):
        global _open_window
        if event.widget is window:
            _open_window = None

    window.bind("<Destroy>", on_destroy)
    window.bind("<Escape>", lambda _e: window.destroy())
    window.bind("<Return>", lambda _e: window.destroy())
    window.lift()
    window.attributes("-topmost", True)
    window.after(300, lambda: window.winfo_exists() and window.attributes("-topmost", False))
    window.focus_force()
    return window
