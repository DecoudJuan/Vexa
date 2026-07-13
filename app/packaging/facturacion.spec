# -*- mode: python -*-
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

block_cipher = None

datas = [
    ("../assets/logo.png", "assets"),
    ("../assets/icon.ico", "assets"),
    ("../assets/vexa_logo.png", "assets"),
    ("../assets/vexa_icon.png", "assets"),
    ("../assets/vexa_icon.ico", "assets"),
    ("../assets/chevron.png", "assets"),
]
# zeep (SOAP AFIP, Fase 4): sus WSDL/plantillas y su metadata de versión, que
# PyInstaller no descubre solo (los carga por importlib en runtime).
datas += collect_data_files("zeep")
datas += copy_metadata("zeep")

a = Analysis(
    ["../main.py"],
    pathex=["../"],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "sqlalchemy.dialects.sqlite",
        "fiscal.afip", "fiscal.qr", "fiscal.provider",
    ],
    excludes=["matplotlib", "tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Facturacion",
    icon="../assets/vexa_icon.ico",
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(exe, a.binaries, a.datas, name="Facturacion")
