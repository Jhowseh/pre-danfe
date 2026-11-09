"""Gera a faixa do topo do README nos temas claro e escuro, no visual da capa do manual.

  python capa_readme.py   -> grava docs/capa-clara.png e docs/capa-escura.png
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))

import tema as tm  # noqa: E402

RECURSOS = AQUI.parent / "recursos"
DOCS = AQUI.parent.parent / "docs"
FONTES = Path(r"C:\Windows\Fonts")

TITULO = "Pré-DANFE"
FRASE = "Veja o DANFE da sua NF-e antes de transmitir no SysPDV."
L, A = 1700, 500  # tamanho da faixa


def faixa(escuro):
    c = tm.ESCURO if escuro else tm.CLARO
    img = tm.forma_arredondada(L, A, 36, fundo=c["bg"], borda=c["borda"], espessura=3)
    d = ImageDraw.Draw(img)

    # logo: colorido no claro; branco e vermelho no escuro (como nas janelas do app)
    if escuro:
        logo = tm.logo_pbtec(270, "#FFFFFF", RECURSOS / "pbtec_logo.png")
    else:
        logo = tm.logo_pronto(270, RECURSOS / "pbtec_logo_light.png")
    img.alpha_composite(logo, (100, (A - logo.height) // 2))

    x = 100 + logo.width + 120
    titulo = ImageFont.truetype(str(FONTES / "segoeuib.ttf"), 150)
    frase = ImageFont.truetype(str(FONTES / "segoeui.ttf"), 46)
    d.text((x - 8, 72), TITULO, font=titulo, fill=c["texto"])
    d.text((x, 270), FRASE, font=frase, fill=c["suave"])
    img.alpha_composite(tm.forma_arredondada(190, 10, 5, degrade=tm.DEGRADE), (x, 390))
    return img


def main():
    DOCS.mkdir(exist_ok=True)
    for nome, escuro in (("capa-clara.png", False), ("capa-escura.png", True)):
        faixa(escuro).save(DOCS / nome, optimize=True)
        print("imagem:", DOCS / nome)


if __name__ == "__main__":
    main()
