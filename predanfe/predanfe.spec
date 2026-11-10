import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

HERE = Path(SPECPATH)
sys.path.insert(0, str(HERE))

from app_utils import ICON_FILE
from version import COMPANY, PRODUCT, VERSION

ICON = str(HERE / "resources" / ICON_FILE)
DATAS = [
    (str(HERE / "fbclient"), "fbclient"),
    (str(HERE / "resources"), "resources"),
    *collect_data_files("brazilfiscalreport"),
    *collect_data_files("barcode"),
]


def version_info(name, description):
    numbers = tuple(([int(part) for part in VERSION.split(".")] + [0, 0, 0, 0])[:4])
    text = ".".join(map(str, numbers))
    return VSVersionInfo(
        ffi=FixedFileInfo(filevers=numbers, prodvers=numbers),
        kids=[
            StringFileInfo([StringTable("041604B0", [
                StringStruct("CompanyName", COMPANY),
                StringStruct("FileDescription", description),
                StringStruct("FileVersion", text),
                StringStruct("InternalName", name),
                StringStruct("LegalCopyright", f"© {COMPANY}"),
                StringStruct("OriginalFilename", f"{name}.exe"),
                StringStruct("ProductName", PRODUCT),
                StringStruct("ProductVersion", text),
            ])]),
            VarFileInfo([VarStruct("Translation", [0x0416, 1200])]),
        ],
    )


def program(script, name, description, hidden_imports=()):
    analysis = Analysis([str(HERE / script)], pathex=[str(HERE)], datas=DATAS,
                        hiddenimports=list(hidden_imports))
    exe = EXE(PYZ(analysis.pure), analysis.scripts, exclude_binaries=True, name=name, icon=ICON,
              console=False, upx=False, version=version_info(name, description))
    return analysis, exe


on_demand, on_demand_exe = program("app_v1.py", "PreDANFE", PRODUCT)
automatic, automatic_exe = program("app_v2.py", "PreDANFE-Automatico", f"{PRODUCT} - Automático",
                                   ["pystray._win32"])

COLLECT(on_demand_exe, on_demand.binaries, on_demand.datas,
        automatic_exe, automatic.binaries, automatic.datas,
        name="PreDANFE", upx=False)
