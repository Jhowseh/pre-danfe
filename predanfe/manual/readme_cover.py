import sys
from pathlib import Path

from PIL import ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import theme as tm

RESOURCES = HERE.parent / "resources"
DOCS = HERE.parent.parent / "docs"
FONTS = Path(r"C:\Windows\Fonts")

TITLE = "Pré-DANFE"
TAGLINE = "Veja o DANFE da sua NF-e antes de transmitir no SysPDV."
WIDTH, HEIGHT = 1700, 500


def banner(dark):
    c = tm.DARK if dark else tm.LIGHT
    img = tm.rounded_shape(WIDTH, HEIGHT, 36, fill=c["bg"], border=c["border"], border_width=3)
    d = ImageDraw.Draw(img)

    if dark:
        logo = tm.pbtec_logo(270, "#FFFFFF", RESOURCES / "pbtec_logo.png")
    else:
        logo = tm.transparent_logo(270, RESOURCES / "pbtec_logo_light.png")
    img.alpha_composite(logo, (100, (HEIGHT - logo.height) // 2))

    x = 100 + logo.width + 120
    title_font = ImageFont.truetype(str(FONTS / "segoeuib.ttf"), 150)
    tagline_font = ImageFont.truetype(str(FONTS / "segoeui.ttf"), 46)
    d.text((x - 8, 72), TITLE, font=title_font, fill=c["text"])
    d.text((x, 270), TAGLINE, font=tagline_font, fill=c["muted"])
    img.alpha_composite(tm.rounded_shape(190, 10, 5, gradient=tm.GRADIENT), (x, 390))
    return img


def main():
    DOCS.mkdir(exist_ok=True)
    for name, dark in (("capa-clara.png", False), ("capa-escura.png", True)):
        banner(dark).save(DOCS / name, optimize=True)
        print("imagem:", DOCS / name)


if __name__ == "__main__":
    main()
