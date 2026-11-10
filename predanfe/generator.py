import lazy_imports

from datetime import datetime
from pathlib import Path

from brazilfiscalreport.danfe import Danfe, DanfeConfig
from brazilfiscalreport.danfe.config import DanfeLayout
from brazilfiscalreport.danfe.danfe import DanfeMoc70, DanfeNt2026010, resolve_layout

from database import APP_DIR, read_config, rows_as_dicts
from nfe_xml import build_xml, load_invoice

PREVIEW_NOTICE = "*** PRE-VISUALIZACAO GERADA PELO PREDANFE - SEM VALOR FISCAL ***"

SQL_PENDING = """
SELECT NFSCTR, NFSNUM, NFSSER, NFSDATEMI, NFSCLIDES, NFSVLR
  FROM NOTAFISCAL
 WHERE NFSTIP <> 'CAN'
   AND COALESCE(TRIM(NFSSTATNFE), '') = ''
   AND NFSXMLEMINFE IS NULL
 ORDER BY NFSDATEMI DESC, NFSNUM DESC
"""

SQL_BY_NUMBER = """
SELECT NFSCTR, NFSNUM, NFSSER, NFSTIP, NFSSTATNFE, NFSCLIDES, NFSVLR,
       IIF(NFSXMLEMINFE IS NULL, 'N', 'S') AS HAS_XML
  FROM NOTAFISCAL
 WHERE TRIM(LEADING '0' FROM TRIM(NFSNUM)) = ? AND NFSTIP <> 'CAN'
"""


def list_pending(cur):
    cur.execute(SQL_PENDING)
    return rows_as_dicts(cur)


def find_by_number(cur, number):
    cur.execute(SQL_BY_NUMBER, (str(int(number)),))
    return rows_as_dicts(cur)


def predanfe_class(xml):
    base = DanfeMoc70 if resolve_layout(xml, DanfeLayout.AUTO) == DanfeLayout.MOC_7_0 else DanfeNt2026010

    class PreDanfe(base):
        def _get_usage_protocol(self):
            return "NAO TRANSMITIDA - PRE-VISUALIZACAO"

        def _draw_void_watermark(self):
            lines = ["SEM VALOR FISCAL", "PRÉ-VISUALIZAÇÃO"]
            font_size = 54
            self.set_font(self.default_font, "B", font_size)
            self.set_text_color(r=220, g=150, b=150)
            cx, cy = self.w / 2, self.h / 2
            line_height = font_size * 0.3528
            with self.rotation(55, cx, cy):
                for i, text in enumerate(lines):
                    text_width = self.get_string_width(text)
                    y = cy + (i - (len(lines) - 1) / 2) * line_height * 1.3 + line_height / 3
                    self.text(cx - text_width / 2, y, text)
            self.set_text_color(r=0, g=0, b=0)

    return PreDanfe


def danfe_config():
    return DanfeConfig(display_pis_cofins=True)


def build(cur, nfsctr):
    return build_xml(load_invoice(cur, nfsctr), notice=PREVIEW_NOTICE)


def predanfe_pdf(xml):
    return bytes(predanfe_class(xml)(xml, config=danfe_config()).output())


def official_pdf(cur, nfsctr):
    cur.execute("SELECT NFSXMLEMINFE FROM NOTAFISCAL WHERE NFSCTR = ?", (nfsctr,))
    blob = cur.fetchone()[0]
    data = blob.read() if hasattr(blob, "read") else blob
    xml = data.decode("utf-8") if isinstance(data, bytes) else data
    return bytes(Danfe(xml, danfe_config()).output())


def output_dir(cfg=None):
    cfg = cfg or read_config()
    folder = Path(cfg.get("saida", "pasta_pdf", fallback="pdf").strip() or "pdf")
    if not folder.is_absolute():
        folder = APP_DIR / folder
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save(folder, name, content):
    target = Path(folder) / name
    try:
        target.write_bytes(content)
    except PermissionError:
        target = target.with_name(f"{target.stem}_{datetime.now():%H%M%S}{target.suffix}")
        target.write_bytes(content)
    return target


def file_name(number, prefix="PreDANFE", extension=".pdf"):
    return f"{prefix}_{int(number)}{extension}"
