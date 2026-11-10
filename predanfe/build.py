import shutil
from pathlib import Path

import PyInstaller.__main__

from app_utils import ICON_FILE, save_ico

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WORK_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"
ICON = HERE / "resources" / ICON_FILE


def compile_exe(name, script, extra=()):
    PyInstaller.__main__.run([
        "--noconfirm", "--clean", "--onefile", "--windowed",
        f"--name={name}",
        f"--icon={ICON}",
        f"--add-data={HERE / 'fbclient'};fbclient",
        f"--add-data={HERE / 'resources'};resources",
        "--collect-data=brazilfiscalreport",
        "--collect-data=barcode",
        f"--paths={HERE}",
        f"--workpath={WORK_DIR / 'work'}",
        f"--specpath={WORK_DIR}",
        f"--distpath={DIST_DIR}",
        *extra,
        str(HERE / script),
    ])


def main():
    WORK_DIR.mkdir(exist_ok=True)
    save_ico(ICON)
    compile_exe("PreDANFE", "app_v1.py")
    compile_exe("PreDANFE-Automatico", "app_v2.py", ["--hidden-import=pystray._win32"])
    shutil.copy(ROOT / "docs" / "LEIA-ME.txt", DIST_DIR / "LEIA-ME.txt")
    shutil.copy(ROOT / "LICENSE", DIST_DIR / "LICENSE.txt")
    shutil.copy(ROOT / "NOTICE", DIST_DIR / "NOTICE.txt")
    print(f"\nPronto: {DIST_DIR}")


if __name__ == "__main__":
    main()
