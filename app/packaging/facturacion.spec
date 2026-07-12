# -*- mode: python -*-
block_cipher = None

datas = [
    ("../assets/logo.png", "assets"),
    ("../assets/icon.ico", "assets"),
]

a = Analysis(
    ["../main.py"],
    pathex=["../"],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    excludes=["matplotlib", "tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Facturacion",
    icon="../assets/icon.ico",
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(exe, a.binaries, a.datas, name="Facturacion")
