"""Vexa mobile — entrypoint.

Arranca la app Flet sobre `vexa_core`. Estructura modular:
  theme.py    tokens + helpers de layout        logo.py     marca Vexa (canvas)
  widgets.py  componentes de UI compartidos      seed.py     datos demo
  app.py      shell (barra, nav, config, tema)   views/      una vista por pantalla
  plataforma.py  compartir/abrir PDF por SO

IMPORTANTE: `FACTURACION_DATA_DIR` se setea ANTES de importar `vexa_core`, porque
el módulo `db` congela `DATA_DIR` al importarse. En Android apunta al storage
privado de la app (`FLET_APP_STORAGE_DATA`).
"""
from __future__ import annotations

import os

# --- 1) Carpeta de datos ANTES de importar el core --------------------------
_storage = os.getenv("FLET_APP_STORAGE_DATA")
if _storage:
    os.environ["FACTURACION_DATA_DIR"] = _storage

# --- 2) Core + Flet + módulos de la app -------------------------------------
import flet as ft  # noqa: E402

from vexa_core.database.db import DatabaseManager  # noqa: E402
from vexa_core.utils.helpers import set_moneda  # noqa: E402

from app import VexaApp  # noqa: E402
from logo import v_logo  # noqa: E402
from onboarding import Onboarding, necesita_onboarding  # noqa: E402
from seed import seed_demo  # noqa: E402


async def _hide_splash(page: ft.Page, splash: ft.Container):
    import asyncio
    await asyncio.sleep(1.05)
    splash.opacity = 0
    page.update()
    await asyncio.sleep(0.5)
    splash.visible = False
    page.update()


def main(page: ft.Page):
    page.title = "Vexa"
    page.padding = 0
    # Desktop: abrir en tamaño celular para iterar sin buildear el APK (Android
    # ignora el tamaño de ventana). Tamaño override por env (VEXA_WIN_W/H) sin tocar
    # el default.
    try:
        page.window.width = int(os.getenv("VEXA_WIN_W") or 1080)
        page.window.height = int(os.getenv("VEXA_WIN_H") or 1400)
    except Exception:
        pass

    db = DatabaseManager()
    db.init_db()
    set_moneda(db.get_datos_empresa().get("moneda"))
    # Los PDF (facturas y etiquetas) se guardan en la carpeta Documentos del dispositivo.
    from plataforma import carpeta_documentos  # noqa: E402
    db.set_config("pdf_dir", str(carpeta_documentos()))

    app = VexaApp(page, db)
    page.on_keyboard_event = app.on_key   # Escape cierra forms con chequeo de cambios
    page.services.append(app.file_picker)  # FilePicker es un service en flet 0.86
    page.services.append(app.share)        # Share nativo (compartir/imprimir el PDF)

    # Primera ejecución (base vacía, sin empresa): onboarding en vez de sembrar demo.
    if necesita_onboarding(db):
        Onboarding(app).start()   # bienvenida (V que sube + "Comenzar") → form → app
        return

    seed_demo(db)
    app.render()
    tk = app.t
    splash = ft.Container(expand=True, bgcolor=tk["ground"], alignment=ft.Alignment.CENTER,
                          content=v_logo(96, tk["v_ink"], tk["dot"]), opacity=1,
                          animate_opacity=ft.Animation(500), left=0, top=0, right=0, bottom=0)
    page.overlay.append(splash)
    page.update()
    page.run_task(_hide_splash, page, splash)


if __name__ == "__main__":
    ft.run(main)
