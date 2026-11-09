"""Núcleo do Pré-DANFE, usado pela linha de comando, pela janela (V1) e pelo
modo automático (V2): busca notas, monta o XML e desenha o PDF."""
import leve  # noqa: F401 - antes do brazilfiscalreport (economiza memória)

from datetime import datetime
from pathlib import Path

from brazilfiscalreport.danfe import Danfe, DanfeConfig
from brazilfiscalreport.danfe.config import DanfeLayout
from brazilfiscalreport.danfe.danfe import DanfeMoc70, DanfeNt2026010, resolve_layout

from banco import PASTA, ler_config, linhas_dict
from nfe_xml import carregar_nota, montar_xml

AVISO_INFCPL = "*** PRE-VISUALIZACAO GERADA PELO PREDANFE - SEM VALOR FISCAL ***"

# Pendente = não cancelada, sem status de envio e sem XML gravado.
SQL_PENDENTES = """
SELECT NFSCTR, NFSNUM, NFSSER, NFSDATEMI, NFSCLIDES, NFSVLR
  FROM NOTAFISCAL
 WHERE NFSTIP <> 'CAN'
   AND COALESCE(TRIM(NFSSTATNFE), '') = ''
   AND NFSXMLEMINFE IS NULL
 ORDER BY NFSDATEMI DESC, NFSNUM DESC
"""

SQL_POR_NUMERO = """
SELECT NFSCTR, NFSNUM, NFSSER, NFSTIP, NFSSTATNFE, NFSCLIDES, NFSVLR,
       IIF(NFSXMLEMINFE IS NULL, 'N', 'S') AS TEM_XML
  FROM NOTAFISCAL
 WHERE TRIM(LEADING '0' FROM TRIM(NFSNUM)) = ? AND NFSTIP <> 'CAN'
"""


def listar_pendentes(cur):
    cur.execute(SQL_PENDENTES)
    return linhas_dict(cur)


def buscar_por_numero(cur, numero):
    cur.execute(SQL_POR_NUMERO, (str(int(numero)),))
    return linhas_dict(cur)


def classe_predanfe(xml):
    """Escolhe o layout oficial pela data de emissão e troca marca d'água e protocolo."""
    base = DanfeMoc70 if resolve_layout(xml, DanfeLayout.AUTO) == DanfeLayout.MOC_7_0 else DanfeNt2026010

    class PreDanfe(base):
        def _get_usage_protocol(self):
            return "NAO TRANSMITIDA - PRE-VISUALIZACAO"

        def _draw_void_watermark(self):
            linhas = ["SEM VALOR FISCAL", "PRÉ-VISUALIZAÇÃO"]
            tamanho = 54
            self.set_font(self.default_font, "B", tamanho)
            self.set_text_color(r=220, g=150, b=150)
            cx, cy = self.w / 2, self.h / 2
            altura = tamanho * 0.3528  # pt -> mm
            with self.rotation(55, cx, cy):
                for i, texto in enumerate(linhas):
                    larg = self.get_string_width(texto)
                    y = cy + (i - (len(linhas) - 1) / 2) * altura * 1.3 + altura / 3
                    self.text(cx - larg / 2, y, texto)
            self.set_text_color(r=0, g=0, b=0)

    return PreDanfe


def config_danfe():
    return DanfeConfig(display_pis_cofins=True)


def montar(cur, nfsctr):
    """XML montado das tabelas: (xml, chave, avisos)."""
    return montar_xml(carregar_nota(cur, nfsctr), aviso=AVISO_INFCPL)


def pdf_predanfe(xml):
    return bytes(classe_predanfe(xml)(xml, config=config_danfe()).output())


def pdf_oficial(cur, nfsctr):
    """DANFE do XML que o SysPDV gravou após a transmissão (para comparar)."""
    cur.execute("SELECT NFSXMLEMINFE FROM NOTAFISCAL WHERE NFSCTR = ?", (nfsctr,))
    blob = cur.fetchone()[0]
    dados = blob.read() if hasattr(blob, "read") else blob
    xml = dados.decode("utf-8") if isinstance(dados, bytes) else dados
    return bytes(Danfe(xml, config_danfe()).output())


def pasta_saida(cfg=None):
    cfg = cfg or ler_config()
    pasta = Path(cfg.get("saida", "pasta_pdf", fallback="pdf").strip() or "pdf")
    if not pasta.is_absolute():
        pasta = PASTA / pasta
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def salvar(pasta, nome, conteudo):
    """Grava `nome` na pasta. Se o arquivo estiver aberto (bloqueado), grava com horário no nome."""
    destino = Path(pasta) / nome
    try:
        destino.write_bytes(conteudo)
    except PermissionError:
        destino = destino.with_name(f"{destino.stem}_{datetime.now():%H%M%S}{destino.suffix}")
        destino.write_bytes(conteudo)
    return destino


def nome_arquivo(numero, prefixo="PreDANFE", extensao=".pdf"):
    return f"{prefixo}_{int(numero)}{extensao}"
