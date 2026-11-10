import os
import shutil
import subprocess
from pathlib import Path

import PyInstaller.__main__

from app_utils import ICON_FILE, save_ico
from version import VERSION

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WORK_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"
APP_DIR = DIST_DIR / "PreDANFE"
ICON = HERE / "resources" / ICON_FILE
SPEC = HERE / "predanfe.spec"
INSTALLER_SCRIPT = HERE / "installer.iss"
PORTABLE_ZIP = DIST_DIR / f"PreDANFE-Portatil-{VERSION}"
MANUAL_NAME = "Manual-PreDANFE.pdf"


def compile_programs():
    PyInstaller.__main__.run([
        "--noconfirm", "--clean",
        f"--workpath={WORK_DIR / 'work'}",
        f"--distpath={DIST_DIR}",
        str(SPEC),
    ])


def copy_documents():
    shutil.copy(ROOT / "docs" / "LEIA-ME.txt", APP_DIR / "LEIA-ME.txt")
    shutil.copy(ROOT / "LICENSE", APP_DIR / "LICENSE.txt")
    shutil.copy(ROOT / "NOTICE", APP_DIR / "NOTICE.txt")
    for manual in (DIST_DIR / MANUAL_NAME, ROOT / MANUAL_NAME):
        if manual.exists():
            shutil.copy(manual, APP_DIR / MANUAL_NAME)
            return
    print(f"Aviso: {MANUAL_NAME} não encontrado; gere com manual/build_manual.py.")


def find_inno_compiler():
    found = shutil.which("ISCC")
    if found:
        return Path(found)
    folders = [os.environ.get(name) for name in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA")]
    candidates = []
    for folder in filter(None, folders):
        for pattern in ("Inno Setup */ISCC.exe", "Programs/Inno Setup */ISCC.exe"):
            candidates += Path(folder).glob(pattern)
    return max(candidates, key=lambda path: path.parent.name, default=None)


def build_installer():
    compiler = find_inno_compiler()
    if compiler is None:
        print("Aviso: Inno Setup não encontrado; o instalador não foi gerado.")
        return
    subprocess.run([
        str(compiler), "/Q",
        f"/DAppVersion={VERSION}",
        f"/DSourceDir={APP_DIR}",
        f"/O{DIST_DIR}",
        str(INSTALLER_SCRIPT),
    ], check=True)


def main():
    WORK_DIR.mkdir(exist_ok=True)
    save_ico(ICON)
    compile_programs()
    copy_documents()
    shutil.make_archive(str(PORTABLE_ZIP), "zip", root_dir=DIST_DIR, base_dir=APP_DIR.name)
    build_installer()
    print(f"\nPronto: {DIST_DIR}")


if __name__ == "__main__":
    main()
