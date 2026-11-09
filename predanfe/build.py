"""Compila os dois programas (.exe) com PyInstaller e monta a pasta C:\\PreDanfe\\Distribuir.

  python build.py
"""
import shutil
from pathlib import Path

import PyInstaller.__main__

from util_app import ARQ_ICONE, salvar_ico

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
TRABALHO = RAIZ / "build"
DESTINO = RAIZ / "Distribuir"
# o mesmo .ico vira o ícone do .exe e vai junto em recursos/ para as janelas usarem
ICONE = AQUI / "recursos" / ARQ_ICONE


def compilar(nome, script, extras=()):
    PyInstaller.__main__.run([
        "--noconfirm", "--clean", "--onefile", "--windowed",
        f"--name={nome}",
        f"--icon={ICONE}",
        f"--add-data={AQUI / 'fbclient'};fbclient",
        f"--add-data={AQUI / 'recursos'};recursos",
        "--collect-data=brazilfiscalreport",
        "--collect-data=barcode",
        f"--paths={AQUI}",
        f"--workpath={TRABALHO / 'work'}",
        f"--specpath={TRABALHO}",
        f"--distpath={DESTINO}",
        *extras,
        str(AQUI / script),
    ])


def main():
    TRABALHO.mkdir(exist_ok=True)
    salvar_ico(ICONE)
    compilar("PreDANFE", "app_v1.py")
    compilar("PreDANFE-Automatico", "app_v2.py", ["--hidden-import=pystray._win32"])
    shutil.copy(RAIZ / "docs" / "LEIA-ME.txt", DESTINO / "LEIA-ME.txt")
    print(f"\nPronto: {DESTINO}")


if __name__ == "__main__":
    main()
