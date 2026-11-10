import configparser
import json
import os
import sys
import tkinter as tk
from contextlib import contextmanager
from datetime import datetime, time
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import theme as tm

tm.enable_dpi_awareness()
tm.windows_dark_mode = lambda: False

import app_utils
import app_v1
import config_window
import generator
from PIL import ImageGrab

IMG = HERE / "img"
SCALE = 1.3

INVOICES = [
    {"NFSCTR": "0000001532", "NFSNUM": "0000001532", "NFSSER": "1", "NFSDATEMI": datetime(2026, 11, 6),
     "NFSCLIDES": "TECMAIS SOLUCOES E SERVICOS LTDA", "NFSVLR": Decimal("1169.20")},
    {"NFSCTR": "0000001533", "NFSNUM": "0000001533", "NFSSER": "1", "NFSDATEMI": datetime(2026, 11, 6),
     "NFSCLIDES": "JOÃO DA SILVA", "NFSVLR": Decimal("89.90")},
    {"NFSCTR": "0000001534", "NFSNUM": "0000001534", "NFSSER": "1", "NFSDATEMI": datetime(2026, 11, 6),
     "NFSCLIDES": "PADARIA PÃO QUENTE ME", "NFSVLR": Decimal("642.35")},
]


class _Record(dict):
    def __missing__(self, _key):
        return None


def _item(code, description, ncm, cfop, cst, qty, unit, rate):
    total = (Decimal(qty) * Decimal(unit)).quantize(Decimal("0.01"))
    base = total if rate else Decimal("0")
    icms = (base * Decimal(rate) / 100).quantize(Decimal("0.01"))
    pis_cst = "01" if rate else "06"
    return _Record(
        PROCOD=f"{code:014d}", INFPRODES=description, INFNCM=ncm, CFOCOD=cfop + "0", UNIT="UNID",
        INFQTDEMB=Decimal(qty), INFVLREMB=Decimal(unit), INFVLRTOT=total, INFTABA="0", INFTABB=cst,
        INFBASEICMS=base, INFALQ=Decimal(rate), INFVLRIMP=icms,
        INFCSTPIS=pis_cst, INFBASEPIS=total - icms, INFCSTCOFINS=pis_cst, INFBASECOFINS=total - icms,
    )


class _SampleIBPT:
    def rate(self, ncm, imported=False, text=False):
        pair = (Decimal("14.21"), Decimal("20")) if ncm.startswith("22") else (Decimal("13.45"), Decimal("18"))
        return pair[0], pair[1], "invoices"


def sample_danfe_data():
    items = [
        _item(1001, "ARROZ TIPO 1 5KG", "10063021", "5102", "00", 10, "24.90", 20),
        _item(1002, "FEIJÃO CARIOCA 1KG", "07133399", "5102", "00", 20, "8.45", 20),
        _item(1003, "ÓLEO DE SOJA 900ML", "15079011", "5102", "00", 30, "7.99", 20),
        _item(1004, "REFRIGERANTE COLA 2L", "22021000", "5405", "60", 24, "9.50", 0),
        _item(1005, "CAFÉ TORRADO E MOÍDO 500G", "09012100", "5102", "00", 15, "18.90", 20),
    ]
    total = sum(i["INFVLRTOT"] for i in items)
    invoice = _Record(
        NFSCTR="0000001532", NFSNUM="0000001532", NFSSER="1", CFOCOD="51020",
        NFSDATEMI=datetime(2026, 11, 6), NFSDATSAI=datetime(2026, 11, 6), NFSHORSAI=time(10, 30),
        NFSFINNFE="1", NFSTIPPAGTO="P",
        NFSCLIDES="TECMAIS SOLUCOES E SERVICOS LTDA", NFSCLICPFCGC="12345678000195", NFSCLIRGCGF="ISENTO",
        NFSCLIEND="AV. DAS PALMEIRAS", NFSCLINUM="250", NFSCLIBAI="CENTRO", NFSCLICID="JOAO PESSOA",
        NFSCLIEST="PB", NFSCLICEP="58000000", NFSCLITEL="8332221111",
        NFSVLR=total, NFSVLRBASEICMS=sum(i["INFBASEICMS"] for i in items),
        NFSVLRICMS=sum(i["INFVLRIMP"] for i in items),
        NFSOBSERVACAO="Pedido 4512 - Entregar no período da manhã. Val Aprox Tributos Federais R$ 0,00 "
                      "Val Aprox Tributos Estaduais R$ 0,00 Fonte: IBPT",
    )
    issuer = {
        "PRPDES": "EMPRESA EXEMPLO COMÉRCIO LTDA", "PRPFAN": "EMPRESA EXEMPLO", "PRPCGC": "11222333000181",
        "PRPIERG": "123456789", "PRPINCMUN": None, "PRPEND": "RUA DAS FLORES", "PRPNUM": "100", "PRPCMP": None,
        "PRPBAI": "CENTRO", "PRPMUN": "JOAO PESSOA", "PRPCODIBGE": "2507507", "PRPUF": "PB",
        "PRPCEP": "58000000", "PRPTEL": "8332220000", "PRPCRT": "3", "PRPREGFED": "R",
    }
    return {"invoice": invoice, "items": items, "issuer": issuer, "customer": {"CMUN": "2507507"},
            "cfop": {"CFODES": "VENDA DE MERCADORIA ADQUIRIDA OU RECEBIDA DE TERCEIROS"},
            "carrier": {}, "ibpt": _SampleIBPT(), "referenced_keys": []}


def capture(window, name):
    window.update()
    window.after(500)
    window.update()
    x, y = window.winfo_rootx(), window.winfo_rooty()
    ImageGrab.grab(bbox=(x, y, x + window.winfo_width(), y + window.winfo_height()),
                   all_screens=True).save(IMG / name)
    print("imagem:", name)


def position(widget, window, anchor="center"):
    x = widget.winfo_rootx() - window.winfo_rootx()
    y = widget.winfo_rooty() - window.winfo_rooty()
    w, h = widget.winfo_width(), widget.winfo_height()
    return {"center": (x + w // 2, y + h // 2), "left": (x, y + h // 2), "right": (x + w, y + h // 2),
            "top-left": (x, y)}[anchor]


@contextmanager
def _no_database():
    yield None


def capture_main(markers):
    app_v1.read_only_connection = _no_database
    app_v1.list_pending = lambda _cur: INVOICES
    app_v1.read_config = lambda: None
    os.startfile = lambda _p: None

    root = tk.Tk()
    root.tk.call("tk", "scaling", 96 / 72 * SCALE)
    root.geometry("+30+0")
    app = app_v1.App(root)
    root.update()
    app.refresh()
    for _ in range(30):
        root.update()
        root.after(50)
    app.number.set("1532")
    app.show_message("Pré-DANFE da NF-e 1532 gerado · PreDANFE_1532.pdf", "green")
    root.focus_force()
    root.update()
    capture(root, "main.png")
    first_row = app.invoice_list
    markers["main"] = {
        "scale": app.t.scale,
        "points": [
            position(app.number, root, "left"),
            position(app.generate_button, root, "right"),
            [position(first_row, root, "top-left")[0], position(first_row, root, "top-left")[1] + app.t.px(32)],
            _status_point(app, root),
        ],
    }
    buttons = [w for w in _all_widgets(root) if isinstance(w, tm.Button)]
    by_text = {b.itemcget(b._text_item, "text"): b for b in buttons}
    markers["main"]["points"] += [position(by_text["Atualizar"], root, "left"),
                                  position(by_text["Abrir pasta dos PDFs"], root, "left"),
                                  position(by_text["Configurações"], root, "right"),
                                  position(by_text["Sobre"], root, "left")]
    root.destroy()


def _status_point(app, root):
    header, t = app.header, app.t
    x0, y0 = position(header, root, "top-left")
    return [x0 + header._cx + t.px(26), y0 + header._cy]


def _all_widgets(w):
    for child in w.winfo_children():
        yield child
        yield from _all_widgets(child)


def capture_config(markers):
    def sample_config():
        cfg = configparser.ConfigParser()
        cfg.read_dict({"banco": {"host": "192.168.0.10", "porta": "3050", "arquivo": r"C:\Syspdv\syspdv_srv.fdb",
                                 "usuario": "SYSDBA", "senha": "", "fbclient": ""},
                       "saida": {"pasta_pdf": "pdf"}, "automatico": {"intervalo_segundos": "10"}})
        return cfg

    config_window.current_config = sample_config
    root = tk.Tk()
    root.tk.call("tk", "scaling", 96 / 72 * 1.2)
    root.withdraw()
    t = tm.Theme(root)
    window = config_window.show(root, t)
    window.geometry("+30+0")
    root.update()
    fields = [w for w in _all_widgets(window) if isinstance(w, tm.Field)]
    buttons = {b.itemcget(b._text_item, "text"): b for b in _all_widgets(window) if isinstance(b, tm.Button)}
    fields[4].focus_entry()
    capture(window, "config.png")
    markers["config"] = {"scale": t.scale, "points": [
        position(fields[0], window, "left"), position(fields[4], window, "left"),
        position(fields[5], window, "left"), position(buttons["Testar conexão"], window, "left"),
        position(buttons["Salvar"], window, "right")]}
    root.destroy()


def build_sample_danfe():
    import pypdfium2 as pdfium

    from nfe_xml import build_xml

    xml, _key, _warnings = build_xml(sample_danfe_data(), notice=generator.PREVIEW_NOTICE)
    pdf = generator.predanfe_pdf(xml)
    (IMG / "sample_predanfe.pdf").write_bytes(pdf)
    page = pdfium.PdfDocument(pdf)[0]
    page.render(scale=2.2).to_pil().save(IMG / "sample_predanfe.png")
    print("imagem: sample_predanfe.png")


def main():
    IMG.mkdir(exist_ok=True)
    markers = {}
    capture_main(markers)
    capture_config(markers)
    build_sample_danfe()
    app_utils.icon_image(256).save(IMG / "app_icon.png")
    (IMG / "markers.json").write_text(json.dumps(markers, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
