"""Capturas de tela para o manual, com DADOS FICTÍCIOS (nada é lido do banco).

  python capturas.py   -> grava as imagens em manual\\img

As janelas abrem por alguns segundos na tela (tema claro, escala 1,4x para
ficarem nítidas no PDF) e fecham sozinhas.
"""
import configparser
import json
import os
import sys
import tkinter as tk
from contextlib import contextmanager
from datetime import datetime, time
from decimal import Decimal
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))

import tema as tm  # noqa: E402

tm.ativar_dpi()
tm.windows_escuro = lambda: False  # capturas do manual no tema claro

import app_v1  # noqa: E402
import gerador  # noqa: E402
import tela_config  # noqa: E402
import util_app  # noqa: E402
from PIL import ImageGrab  # noqa: E402

IMG = AQUI / "img"
ESCALA = 1.3  # maior que isso, a janela encosta na barra de tarefas em telas de 1080 px

# ------------------------------------------------------------------ dados fictícios

NOTAS = [
    {"NFSCTR": "0000001532", "NFSNUM": "0000001532", "NFSSER": "1", "NFSDATEMI": datetime(2026, 11, 6),
     "NFSCLIDES": "TECMAIS SOLUCOES E SERVICOS LTDA", "NFSVLR": Decimal("1169.20")},
    {"NFSCTR": "0000001533", "NFSNUM": "0000001533", "NFSSER": "1", "NFSDATEMI": datetime(2026, 11, 6),
     "NFSCLIDES": "JOÃO DA SILVA", "NFSVLR": Decimal("89.90")},
    {"NFSCTR": "0000001534", "NFSNUM": "0000001534", "NFSSER": "1", "NFSDATEMI": datetime(2026, 11, 6),
     "NFSCLIDES": "PADARIA PÃO QUENTE ME", "NFSVLR": Decimal("642.35")},
]


class _Registro(dict):
    def __missing__(self, _chave):
        return None


def _item(codigo, descricao, ncm, cfop, cst, qtd, unit, aliq):
    total = (Decimal(qtd) * Decimal(unit)).quantize(Decimal("0.01"))
    base = total if aliq else Decimal("0")
    icms = (base * Decimal(aliq) / 100).quantize(Decimal("0.01"))
    cst_pis = "01" if aliq else "06"  # base do PIS/COFINS = valor - ICMS, como o SysPDV grava
    return _Registro(
        PROCOD=f"{codigo:014d}", INFPRODES=descricao, INFNCM=ncm, CFOCOD=cfop + "0", UNIDADE="UNID",
        INFQTDEMB=Decimal(qtd), INFVLREMB=Decimal(unit), INFVLRTOT=total, INFTABA="0", INFTABB=cst,
        INFBASEICMS=base, INFALQ=Decimal(aliq), INFVLRIMP=icms,
        INFCSTPIS=cst_pis, INFBASEPIS=total - icms, INFCSTCOFINS=cst_pis, INFBASECOFINS=total - icms,
    )


class _IbptExemplo:
    """% do IBPT fictícios para o exemplo (alimentos 13,45+18; bebidas 14,21+20)."""

    def taxa(self, ncm, importado=False, texto=False):
        par = (Decimal("14.21"), Decimal("20")) if ncm.startswith("22") else (Decimal("13.45"), Decimal("18"))
        return par[0], par[1], "notas"


def dados_danfe():
    itens = [
        _item(1001, "ARROZ TIPO 1 5KG", "10063021", "5102", "00", 10, "24.90", 20),
        _item(1002, "FEIJÃO CARIOCA 1KG", "07133399", "5102", "00", 20, "8.45", 20),
        _item(1003, "ÓLEO DE SOJA 900ML", "15079011", "5102", "00", 30, "7.99", 20),
        _item(1004, "REFRIGERANTE COLA 2L", "22021000", "5405", "60", 24, "9.50", 0),
        _item(1005, "CAFÉ TORRADO E MOÍDO 500G", "09012100", "5102", "00", 15, "18.90", 20),
    ]
    total = sum(i["INFVLRTOT"] for i in itens)
    nota = _Registro(
        NFSCTR="0000001532", NFSNUM="0000001532", NFSSER="1", CFOCOD="51020",
        NFSDATEMI=datetime(2026, 11, 6), NFSDATSAI=datetime(2026, 11, 6), NFSHORSAI=time(10, 30),
        NFSFINNFE="1", NFSTIPPAGTO="P",
        NFSCLIDES="TECMAIS SOLUCOES E SERVICOS LTDA", NFSCLICPFCGC="12345678000195", NFSCLIRGCGF="ISENTO",
        NFSCLIEND="AV. DAS PALMEIRAS", NFSCLINUM="250", NFSCLIBAI="CENTRO", NFSCLICID="JOAO PESSOA",
        NFSCLIEST="PB", NFSCLICEP="58000000", NFSCLITEL="8332221111",
        NFSVLR=total, NFSVLRBASEICMS=sum(i["INFBASEICMS"] for i in itens),
        NFSVLRICMS=sum(i["INFVLRIMP"] for i in itens),
        NFSOBSERVACAO="Pedido 4512 - Entregar no período da manhã. Val Aprox Tributos Federais R$ 0,00 "
                      "Val Aprox Tributos Estaduais R$ 0,00 Fonte: IBPT",
    )
    emitente = {
        "PRPDES": "EMPRESA EXEMPLO COMÉRCIO LTDA", "PRPFAN": "EMPRESA EXEMPLO", "PRPCGC": "11222333000181",
        "PRPIERG": "123456789", "PRPINCMUN": None, "PRPEND": "RUA DAS FLORES", "PRPNUM": "100", "PRPCMP": None,
        "PRPBAI": "CENTRO", "PRPMUN": "JOAO PESSOA", "PRPCODIBGE": "2507507", "PRPUF": "PB",
        "PRPCEP": "58000000", "PRPTEL": "8332220000", "PRPCRT": "3", "PRPREGFED": "R",
    }
    return {"nota": nota, "itens": itens, "emitente": emitente, "cliente": {"CMUN": "2507507"},
            "cfop": {"CFODES": "VENDA DE MERCADORIA ADQUIRIDA OU RECEBIDA DE TERCEIROS"},
            "transp": {}, "ibpt": _IbptExemplo(), "chaves_ref": []}


# ------------------------------------------------------------------ captura

def foto(janela, nome):
    janela.update()
    janela.after(500)
    janela.update()
    x, y = janela.winfo_rootx(), janela.winfo_rooty()
    ImageGrab.grab(bbox=(x, y, x + janela.winfo_width(), y + janela.winfo_height()), all_screens=True).save(IMG / nome)
    print("imagem:", nome)


def posicao(widget, janela, ancora="centro"):
    """Ponto do widget em relação ao canto da janela (para as marcações numeradas)."""
    x = widget.winfo_rootx() - janela.winfo_rootx()
    y = widget.winfo_rooty() - janela.winfo_rooty()
    w, h = widget.winfo_width(), widget.winfo_height()
    return {"centro": (x + w // 2, y + h // 2), "esquerda": (x, y + h // 2), "direita": (x + w, y + h // 2),
            "topo-esq": (x, y)}[ancora]


@contextmanager
def _sem_banco():
    yield None


def capturar_principal(marcas):
    app_v1.conexao_leitura = _sem_banco
    app_v1.listar_pendentes = lambda _cur: NOTAS
    app_v1.ler_config = lambda: None
    os.startfile = lambda _p: None

    root = tk.Tk()
    root.tk.call("tk", "scaling", 96 / 72 * ESCALA)  # pontos por pixel; 96 dpi = 100%
    root.geometry("+30+0")
    app = app_v1.App(root)
    root.update()
    app.atualizar()
    for _ in range(30):
        root.update()
        root.after(50)
    app.numero.set("1532")
    app.mensagem("Pré-DANFE da NF-e 1532 gerado · PreDANFE_1532.pdf", "verde")
    root.focus_force()
    root.update()
    foto(root, "principal.png")
    linha1 = app.lista
    marcas["principal"] = {
        "escala": app.t.escala,
        "pontos": [
            posicao(app.numero, root, "esquerda"),
            posicao(app.botao, root, "direita"),
            [posicao(linha1, root, "topo-esq")[0], posicao(linha1, root, "topo-esq")[1] + app.t.px(32)],
            _ponto_status(app, root),
        ],
    }
    # botões do rodapé e "Atualizar"
    botoes = [w for w in _todos(root) if isinstance(w, tm.Botao)]
    por_texto = {b.itemcget(b._txt, "text"): b for b in botoes}
    marcas["principal"]["pontos"] += [posicao(por_texto["Atualizar"], root, "esquerda"),
                                      posicao(por_texto["Abrir pasta dos PDFs"], root, "esquerda"),
                                      posicao(por_texto["Configurações"], root, "direita"),
                                      posicao(por_texto["Sobre"], root, "esquerda")]
    root.destroy()


def _ponto_status(app, root):
    """Logo à direita da bolinha de status do cabeçalho."""
    cab, t = app.cabecalho, app.t
    x0, y0 = posicao(cab, root, "topo-esq")
    return [x0 + cab._cx + t.px(26), y0 + cab._cy]


def _todos(w):
    for f in w.winfo_children():
        yield f
        yield from _todos(f)


def capturar_config(marcas):
    def config_exemplo():
        cfg = configparser.ConfigParser()
        cfg.read_dict({"banco": {"host": "192.168.0.10", "porta": "3050", "arquivo": r"C:\Syspdv\syspdv_srv.fdb",
                                 "usuario": "SYSDBA", "senha": "", "fbclient": ""},
                       "saida": {"pasta_pdf": "pdf"}, "automatico": {"intervalo_segundos": "10"}})
        return cfg

    tela_config.config_atual = config_exemplo
    root = tk.Tk()
    # a tela de configuração é alta: escala menor para caber inteira na tela
    root.tk.call("tk", "scaling", 96 / 72 * 1.2)
    root.withdraw()
    t = tm.Tema(root)
    janela = tela_config.abrir(root, t)
    janela.geometry("+30+0")
    root.update()
    campos = [w for w in _todos(janela) if isinstance(w, tm.Campo)]
    botoes = {b.itemcget(b._txt, "text"): b for b in _todos(janela) if isinstance(b, tm.Botao)}
    campos[4].focar()  # senha em foco, como na primeira vez
    foto(janela, "configuracao.png")
    marcas["configuracao"] = {"escala": t.escala, "pontos": [
        posicao(campos[0], janela, "esquerda"), posicao(campos[4], janela, "esquerda"),
        posicao(campos[5], janela, "esquerda"), posicao(botoes["Testar conexão"], janela, "esquerda"),
        posicao(botoes["Salvar"], janela, "direita")]}
    root.destroy()


def gerar_exemplo_danfe():
    import pypdfium2 as pdfium

    from nfe_xml import montar_xml

    xml, _chave, _avisos = montar_xml(dados_danfe(), aviso=gerador.AVISO_INFCPL)
    pdf = gerador.pdf_predanfe(xml)
    (IMG / "exemplo_predanfe.pdf").write_bytes(pdf)
    pagina = pdfium.PdfDocument(pdf)[0]
    pagina.render(scale=2.2).to_pil().save(IMG / "exemplo_predanfe.png")
    print("imagem: exemplo_predanfe.png")


def main():
    IMG.mkdir(exist_ok=True)
    marcas = {}
    capturar_principal(marcas)
    capturar_config(marcas)
    gerar_exemplo_danfe()
    util_app.imagem_icone(256).save(IMG / "icone_app.png")
    (IMG / "marcas.json").write_text(json.dumps(marcas, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
