import configparser
import tkinter as tk
from tkinter import filedialog

import app_utils
import theme as tm
from database import CONFIG_FILE, read_only_connection, save_config, syspdv_defaults

WIDTH = 520


def current_config():
    cfg = configparser.ConfigParser()
    if CONFIG_FILE.exists():
        cfg.read(CONFIG_FILE, encoding="utf-8")
    for section in ("banco", "saida", "automatico"):
        if not cfg.has_section(section):
            cfg.add_section(section)
    for key, value in syspdv_defaults().items():
        if not cfg.get("banco", key, fallback="").strip():
            cfg.set("banco", key, value)
    for section, key, value in (("banco", "senha", ""), ("saida", "pasta_pdf", "pdf"),
                                ("automatico", "intervalo_segundos", "10")):
        if not cfg.has_option(section, key):
            cfg.set(section, key, value)
    return cfg


_open_window = None


def _bring_to_front(window):
    window.deiconify()
    window.lift()
    window.attributes("-topmost", True)
    window.after(300, lambda: window.winfo_exists() and window.attributes("-topmost", False))
    window.focus_force()


def show(master=None, theme=None, on_save=None, wait=False):
    global _open_window
    if _open_window is not None and _open_window.winfo_exists():
        _bring_to_front(_open_window)
        if wait and master:
            master.wait_window(_open_window)
        return _open_window

    cfg = current_config()
    window = tk.Toplevel(master) if master else tk.Tk()
    _open_window = window
    t = theme or tm.Theme(window)
    t.setup_window(window, "Pré-DANFE – Configuração")
    W = t.px(WIDTH)
    gap = t.px(16)

    body = t.frame(window)
    body.pack(padx=t.px(28), pady=(t.px(22), t.px(26)))
    tm.Header(body, t, W, "Configuração", "Conexão com o banco",
              "O Pré-DANFE só lê o banco do SysPDV. Nunca grava nada.", with_status=False).pack(anchor="w")

    fields = {}

    def field(parent, section, key, label, width, **kw):
        box = t.frame(parent)
        t.label(box, label, "small", "muted").pack(anchor="w", pady=(0, t.px(4)))
        f = tm.Field(box, t, width, value=cfg.get(section, key, fallback=""), **kw)
        f.pack(anchor="w")
        fields[(section, key)] = f
        return box

    def row(*items):
        f = t.frame(body)
        f.pack(anchor="w", pady=(t.px(12), 0))
        for i, (section, key, label, width, kw) in enumerate(items):
            field(f, section, key, label, width, **kw).pack(side="left", padx=(0 if i == 0 else gap, 0))
        return f

    tm.section_title(body, t, "database", "Banco de dados do SysPDV").pack(anchor="w", pady=(t.px(18), 0))
    row(("banco", "host", "Servidor", 360, {}), ("banco", "porta", "Porta", 144, {}))
    row(("banco", "arquivo", "Arquivo do banco", 520, {}))
    row(("banco", "usuario", "Usuário", 252, {}), ("banco", "senha", "Senha", 252, {"show": "•"}))

    tm.section_title(body, t, "folder", "Onde salvar os PDFs").pack(anchor="w", pady=(t.px(22), 0))
    folder_row = row(("saida", "pasta_pdf", "Pasta dos PDFs", 464, {}))

    def browse():
        p = filedialog.askdirectory(parent=window, title="Pasta dos Pré-DANFEs")
        if p:
            fields[("saida", "pasta_pdf")].set(p)

    tm.Button(folder_row, t, "", browse, icon="folder", width=44).pack(side="left", anchor="s", padx=(t.px(12), 0))

    result_label = t.label(body, "", "small", "muted", wraplength=W, justify="left", anchor="w")
    result_label.pack(anchor="w", fill="x", pady=(t.px(14), 0))

    result = {"saved": False}

    def config_from_form():
        new = current_config()
        for (section, key), f in fields.items():
            new.set(section, key, f.get())
        return new

    def notify(text, color):
        result_label.config(text=text, fg=t.c[color])

    testing = {"active": False}

    def test_connection():
        if testing["active"]:
            return
        testing["active"] = True
        notify("Testando a conexão…", "muted")
        window.config(cursor="watch")
        test_cfg = config_from_form()

        def count():
            with read_only_connection(test_cfg) as cur:
                cur.execute("SELECT COUNT(*) FROM NOTAFISCAL")
                return cur.fetchone()[0]

        def done(total, error):
            testing["active"] = False
            window.config(cursor="")
            if error is None:
                notify(f"Conectou! {total} notas fiscais no banco.", "green")
            else:
                notify(f"Não conectou: {error}", "red")

        app_utils.run_in_background(window, count, done)

    def save():
        new = config_from_form()
        if not new.get("banco", "senha"):
            notify("Preencha a senha do banco.", "yellow")
            fields[("banco", "senha")].focus_entry()
            return
        try:
            save_config(new)
        except OSError as e:
            notify(f"Não foi possível gravar {CONFIG_FILE}: {e}", "red")
            return
        result["saved"] = True
        window.destroy()
        if on_save:
            on_save()

    buttons = t.frame(body)
    buttons.pack(fill="x", pady=(t.px(16), 0))
    tm.Button(buttons, t, "Salvar", save, primary=True).pack(side="right")
    tm.Button(buttons, t, "Cancelar", window.destroy).pack(side="right", padx=(0, t.px(10)))
    tm.Button(buttons, t, "Testar conexão", test_connection, icon="database").pack(side="left")

    def on_destroy(event):
        global _open_window
        if event.widget is window:
            _open_window = None

    window.bind("<Destroy>", on_destroy)
    window.bind("<Return>", lambda _e: save())
    window.bind("<Escape>", lambda _e: window.destroy())
    _bring_to_front(window)
    if not cfg.get("banco", "senha", fallback=""):
        window.after(200, fields[("banco", "senha")].focus_entry)
    if master is None:
        window.mainloop()
        return result["saved"]
    if wait:
        master.wait_window(window)
        return result["saved"]
    return window
