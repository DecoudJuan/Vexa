# -*- mode: python -*-
from PyInstaller.utils.hooks import (
    collect_data_files, copy_metadata, collect_submodules,
)

block_cipher = None

datas = [
    ("../assets/logo.png", "assets"),
    ("../assets/icon.ico", "assets"),
    ("../assets/vexa_logo.png", "assets"),
    ("../assets/vexa_icon.png", "assets"),
    ("../assets/vexa_icon.ico", "assets"),
    ("../assets/vexa_symbol.png", "assets"),
    ("../assets/vexa_symbol.ico", "assets"),
    ("../assets/chevron.png", "assets"),
    ("../assets/arrow_up.png", "assets"),
    ("../assets/arrow_down.png", "assets"),
]
# zeep (SOAP AFIP, Fase 4): sus WSDL/plantillas y su metadata de versión, que
# PyInstaller no descubre solo (los carga por importlib en runtime).
datas += collect_data_files("zeep")
datas += copy_metadata("zeep")

a = Analysis(
    ["../main.py"],
    pathex=["../", "../../vexa_core"],  # desktop/ + raíz del paquete vexa_core
    binaries=[],
    datas=datas,
    hiddenimports=[
        "sqlalchemy.dialects.sqlite",
        "vexa_core.fiscal.afip", "vexa_core.fiscal.qr", "vexa_core.fiscal.provider",
    # reportlab.graphics.barcode importa sus submódulos por nombre (dinámico) al
    # inicializarse; sin esto, el QR arrastra un import que rompe el .exe
    # (ModuleNotFoundError: reportlab.graphics.barcode.code128).
    ] + collect_submodules("reportlab.graphics.barcode"),
    excludes=["matplotlib", "tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Facturacion",
    icon="../assets/vexa_symbol.ico",
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(exe, a.binaries, a.datas, name="Facturacion")
