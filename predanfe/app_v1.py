import logging
import os
import time
import tkinter as tk
from tkinter import messagebox

import about_window
import app_utils
import config_window
import theme as tm
from database import ConfigError, read_config, read_only_connection
from generator import build, file_name, find_by_number, list_pending, output_dir, predanfe_pdf, save

log = logging.getLogger("predanfe")

TITLE = "Pré-DANFE – SysPDV"
WIDTH = 540
TRANSITION_MS = 240


def currency(v):
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class InvoiceList(tk.Canvas):
    ROW_HEIGHT, GAP = 64, 8
    WHEEL_STEP = 56
    SMOOTHING = 0.22

    def __init__(self, parent, theme, width, visible_rows, on_select):
        t = self.t = theme
        self.w = t.px(width)
        self.row_h, self.gap = t.px(self.ROW_HEIGHT), t.px(self.GAP)
        height = int(self.row_h * visible_rows + self.gap * (visible_rows - 1))
        super().__init__(parent, width=self.w, height=height, bg=t.c["bg"], highlightthickness=0, bd=0,
                         yscrollincrement=1)
        self.on_select = on_select
        r = t.px(12)
        self.img_normal = t.photo(("ln", self.w, self.row_h, t.dark),
                                  lambda: tm.rounded_shape(self.w, self.row_h, r, t.c["card"], t.c["border"]))
        self.img_hover = t.photo(("lh", self.w, self.row_h, t.dark),
                                 lambda: tm.rounded_shape(self.w, self.row_h, r, t.c["hover"], t.c["link"]))
        self._total_height = 0
        self._pos = 0.0
        self._target = 0.0
        self._anim = None
        self._last_frame = 0.0
        self.bind("<Enter>", lambda _e: self.bind_all("<MouseWheel>", self._scroll))
        self.bind("<Leave>", lambda _e: self.unbind_all("<MouseWheel>"))

    def _max_scroll(self):
        return max(0, self._total_height - self.winfo_height())

    def _scroll(self, event):
        maximum = self._max_scroll()
        if maximum <= 0:
            return
        self._target = min(max(self._target - event.delta / 120 * self.t.px(self.WHEEL_STEP), 0), maximum)
        if self._anim is None:
            self._last_frame = time.perf_counter()
            self._animate()

    def _animate(self):
        now = time.perf_counter()
        dt = max(now - self._last_frame, 0.001)
        self._last_frame = now
        factor = 1 - (1 - self.SMOOTHING) ** (dt / 0.016)
        remaining = self._target - self._pos
        if abs(remaining) < 0.5:
            self._pos = self._target
            self._anim = None
        else:
            self._pos += remaining * factor
            self._anim = self.after(8, self._animate)
        self.yview_moveto(self._pos / self._total_height)

    def _reset_scroll(self, total_height):
        if self._anim is not None:
            self.after_cancel(self._anim)
            self._anim = None
        self._total_height = total_height
        self._pos = self._target = 0.0
        self.yview_moveto(0)

    def _truncate(self, text, font, width):
        if font.measure(text) <= width:
            return text
        while text and font.measure(text + "…") > width:
            text = text[:-1]
        return text + "…"

    def _fit_height(self, rows):
        rows = min(rows, 4.5)
        self.config(height=int(self.row_h * rows + self.gap * (max(1, rows) - 1)))

    def message(self, text, color="muted", icon="layers"):
        self.delete("all")
        self._fit_height(1.8)
        h = int(self["height"])
        self._reset_scroll(h)
        box = self.t.photo(("lv", self.w, h, self.t.dark),
                           lambda: tm.rounded_shape(self.w, h, self.t.px(12), self.t.c["bg"], self.t.c["border"]))
        self.create_image(0, 0, image=box, anchor="nw")
        self.create_image(self.w // 2, h // 2 - self.t.px(16), image=self.t.icon(icon, self.t.c["faint"], 26))
        self.create_text(self.w // 2, h // 2 + self.t.px(16), text=text, font=self.t.fonts["body"],
                         fill=self.t.c[color], width=self.w - self.t.px(40), justify="center")
        self.config(scrollregion=(0, 0, self.w, h))

    def show(self, invoices):
        if not invoices:
            self.message("Nenhuma NF-e aguardando transmissão.")
            return
        t, f = self.t, self.t.fonts
        self.delete("all")
        self._fit_height(len(invoices) if len(invoices) <= 4 else 4.5)
        m = t.px(16)
        for i, inv in enumerate(invoices):
            y = i * (self.row_h + self.gap)
            tag = f"l{i}"
            number = int(inv["NFSNUM"])
            bg_item = self.create_image(0, y, image=self.img_normal, anchor="nw", tags=(tag,))
            self.create_image(m, y + self.row_h // 2, image=t.icon("document", t.c["muted"], 20), anchor="w",
                              tags=(tag,))
            x = m + t.px(32)
            self.create_text(x, y + t.px(12), text=f"NF-e {number}", anchor="nw", font=f["strong"],
                             fill=t.c["link"], tags=(tag,))
            value = currency(inv["NFSVLR"])
            date = inv["NFSDATEMI"].strftime("%d/%m/%Y") if inv["NFSDATEMI"] else ""
            self.create_text(self.w - m, y + t.px(12), text=value, anchor="ne", font=f["strong"],
                             fill=t.c["text"], tags=(tag,))
            customer_w = self.w - x - m - max(f["small"].measure(date), f["strong"].measure(value)) - t.px(16)
            customer = self._truncate(inv["NFSCLIDES"] or "", f["body"], customer_w)
            self.create_text(x, y + t.px(37), text=customer, anchor="nw", font=f["body"], fill=t.c["muted"],
                             tags=(tag,))
            self.create_text(self.w - m, y + t.px(39), text=date, anchor="ne", font=f["small"],
                             fill=t.c["faint"], tags=(tag,))
            self.tag_bind(tag, "<Enter>", lambda _e, bi=bg_item: (self.itemconfig(bi, image=self.img_hover),
                                                                  self.config(cursor="hand2")))
            self.tag_bind(tag, "<Leave>", lambda _e, bi=bg_item: (self.itemconfig(bi, image=self.img_normal),
                                                                  self.config(cursor="")))
            self.tag_bind(tag, "<Button-1>", lambda _e, nu=number: self.on_select(nu))
        height = max(len(invoices) * (self.row_h + self.gap) - self.gap, int(self["height"]))
        self.config(scrollregion=(0, 0, self.w, height))
        self._reset_scroll(height)


class App:
    def __init__(self, root):
        self.root = root
        t = self.t = tm.Theme(root)
        t.setup_window(root, TITLE)
        app_utils.apply_icon(root)
        W = t.px(WIDTH)
        self._busy = False

        body = t.frame(root)
        body.pack(padx=t.px(28), pady=(t.px(22), t.px(26)))

        self.header = tm.Header(body, t, W, "Pré-visualização de NF-e", "Pré-DANFE",
                                "Veja o DANFE da nota antes de transmitir no SysPDV.")
        self.header.pack(anchor="w")
        self.header.status("Conectando ao banco do SysPDV…", "neutral")

        self.stage = t.frame(body)
        self.stage.pack(fill="x")
        self.content = content = t.frame(self.stage)
        content.pack(fill="x")
        self.about_panel = None
        self._animation = None

        tm.section_title(content, t, "document", "Gerar por número").pack(anchor="w", pady=(t.px(18), t.px(10)))
        row = t.frame(content)
        row.pack(anchor="w")
        self.number = tm.Field(row, t, 190, height=48, font="number", hint="Nº da NF-e", justify="center")
        self.number.pack(side="left")
        self.generate_button = tm.Button(row, t, "Gerar Pré-DANFE", self.generate, icon="document", primary=True,
                                         height=48)
        self.generate_button.pack(side="left", padx=(t.px(12), 0))
        self.number.entry.bind("<Return>", lambda _e: self.generate())

        self.status_label = t.label(content, "", "small", "muted", wraplength=W, justify="left", anchor="w")
        self.status_label.pack(anchor="w", fill="x", pady=(t.px(8), 0))

        list_header = t.frame(content)
        list_header.pack(fill="x", pady=(t.px(16), t.px(10)))
        tm.section_title(list_header, t, "layers", "Aguardando transmissão").pack(side="left")
        tm.Button(list_header, t, "Atualizar", self.refresh, icon="refresh", height=32).pack(side="right")

        self.invoice_list = InvoiceList(content, t, WIDTH, 3.5, self.generate_number)
        self.invoice_list.pack(anchor="w")

        footer = t.frame(body)
        footer.pack(fill="x", pady=(t.px(18), 0))
        tm.Button(footer, t, "Abrir pasta dos PDFs", self.open_folder, icon="folder").pack(side="left")
        tm.Button(footer, t, "Configurações", self.configure, icon="sliders").pack(side="left", padx=(t.px(10), 0))
        tm.Button(footer, t, "Sobre", self.toggle_about, icon="info").pack(side="right")
        root.bind("<Escape>", lambda _e: self.close_about())

        root.after(150, self.start)

    def toggle_about(self):
        if self._animation is not None:
            return
        if self.about_panel is not None:
            self.close_about()
            return
        self.stage.update_idletasks()
        self.about_panel = about_window.Panel(self.stage, self.t, WIDTH, self.close_about)
        self.about_panel.update_idletasks()
        height = max(self.stage.winfo_height(), self.about_panel.winfo_reqheight())
        self.stage.config(width=self.stage.winfo_width(), height=height)
        self.stage.pack_propagate(False)
        self._slide(self.content, self.about_panel, 1, lambda: None)

    def close_about(self):
        if self.about_panel is None or self._animation is not None:
            return
        panel = self.about_panel

        def finish():
            panel.destroy()
            self.about_panel = None
            self.stage.pack_propagate(True)
            self.number.focus_entry()

        self._slide(panel, self.content, -1, finish)

    def _slide(self, leaving, entering, direction, on_finish):
        width = self.stage.winfo_width()
        leaving.pack_forget()
        start = time.perf_counter()

        def step():
            p = min(1.0, (time.perf_counter() - start) * 1000 / TRANSITION_MS)
            dx = round(width * (1 - (1 - p) ** 3)) * direction
            leaving.place(x=-dx, y=0, width=width)
            entering.place(x=direction * width - dx, y=0, width=width)
            if p < 1:
                self._animation = self.root.after(15, step)
                return
            leaving.place_forget()
            entering.place_forget()
            entering.pack(fill="x")
            self._animation = None
            on_finish()

        step()

    def start(self):
        self.number.focus_entry()
        try:
            read_config()
        except ConfigError:
            self.not_configured()
            self.configure()
            return
        self.refresh()

    def not_configured(self):
        self.header.status("Sem conexão: configure o acesso ao banco do SysPDV", "error")
        self.invoice_list.message("Clique em Configurações e informe a senha do banco do SysPDV.", "muted",
                                  "database")

    def configure(self):
        config_window.show(self.root, self.t, on_save=self.refresh)

    def open_folder(self):
        try:
            os.startfile(output_dir())
        except BaseException as e:
            self.show_message(f"Não foi possível abrir a pasta: {e}", "red")

    def show_message(self, text, color="muted"):
        self.status_label.config(text=text, fg=self.t.c[color])

    def set_busy(self, busy):
        self._busy = busy
        self.root.config(cursor="watch" if busy else "")
        self.generate_button.set_enabled(not busy)

    def refresh(self):
        if self._busy:
            return
        try:
            read_config()
        except ConfigError:
            self.not_configured()
            return
        self.set_busy(True)

        def fetch():
            with read_only_connection() as cur:
                return list_pending(cur)

        def done(pending, error):
            self.set_busy(False)
            if error is not None:
                log.error("Falha ao listar pendentes: %s", error)
                self.header.status("Sem conexão com o banco do SysPDV", "error")
                self.invoice_list.message(f"Não foi possível ler o banco:\n{error}", "red", "database")
                return
            self.invoice_list.show(pending)
            count = len(pending)
            text = ("nenhuma NF-e aguardando transmissão" if count == 0 else
                    f"{count} NF-e aguardando transmissão" if count > 1 else "1 NF-e aguardando transmissão")
            self.header.status(f"Conectado ao SysPDV · {text}", "ok")

        app_utils.run_in_background(self.root, fetch, done)

    def generate_number(self, number):
        if self._busy:
            return
        self.number.set(str(number))
        self.generate()

    def generate(self):
        if self._busy:
            return
        text = self.number.get()
        if not text.isdigit():
            self.show_message("Digite o número da NF-e (só números).", "yellow")
            self.number.focus_entry()
            return
        number = int(text)
        self.set_busy(True)
        self.show_message(f"Procurando a NF-e {number}…")

        def search():
            with read_only_connection() as cur:
                return find_by_number(cur, text)

        def found(matches, error):
            if error is not None:
                return self._failed(number, error)
            if not matches:
                self.set_busy(False)
                self.show_message(f"A NF-e {number} não foi encontrada.", "yellow")
                return
            invoice = matches[0]
            if invoice["HAS_XML"] == "S" and not messagebox.askyesno(
                    "Pré-DANFE",
                    f"A NF-e {number} já foi transmitida.\n\n"
                    "Gerar o pré-DANFE mesmo assim? (Para a nota transmitida, use o DANFE do SysPDV.)",
                    parent=self.root):
                self.set_busy(False)
                self.show_message("")
                return
            self.show_message(f"Gerando o pré-DANFE da NF-e {number}…")
            app_utils.run_in_background(self.root, lambda: self._generate_pdf(invoice), lambda r, e: ready(r, e))

        def ready(result, error):
            if error is not None:
                return self._failed(number, error)
            self.set_busy(False)
            target, warnings = result
            log.info("Gerado %s", target)
            msg = f"Pré-DANFE da NF-e {number} gerado · {target.name}"
            if warnings:
                msg += "\nAtenção: " + " ".join(warnings)
            self.show_message(msg, "green" if not warnings else "yellow")
            try:
                os.startfile(target)
            except OSError as e:
                self.show_message(f"{msg}\nNão foi possível abrir o PDF: {e}", "yellow")

        app_utils.run_in_background(self.root, search, found)

    @staticmethod
    def _generate_pdf(invoice):
        with read_only_connection() as cur:
            xml, _key, warnings = build(cur, invoice["NFSCTR"])
        target = save(output_dir(), file_name(invoice["NFSNUM"]), predanfe_pdf(xml))
        return target, warnings

    def _failed(self, number, error):
        self.set_busy(False)
        if isinstance(error, ConfigError):
            self.show_message(str(error), "red")
            return
        log.error("Falha ao gerar a nota %s: %r", number, error)
        self.show_message(f"Não foi possível gerar o pré-DANFE: {error}", "red")


def main():
    if not app_utils.single_instance("PreDANFE"):
        app_utils.bring_to_front(TITLE)
        return
    tm.enable_dpi_awareness()
    app_utils.setup_logging("predanfe")
    app_utils.set_app_id("PreDANFE")
    root = tk.Tk()
    app_utils.log_tk_errors(root, log)
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
