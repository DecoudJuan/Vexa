import os
import sys

# En Windows, Qt sigue por defecto el modo oscuro del SISTEMA y pisa nuestra
# paleta en diálogos/popups nativos (QMessageBox, desplegables de combo), que
# salían con fondo negro si el SO estaba en oscuro. El tema claro/oscuro lo
# maneja la app por su cuenta, así que desactivamos ese seguimiento automático.
# Debe fijarse ANTES de crear la QApplication.
if sys.platform == "win32":
    os.environ.setdefault("QT_QPA_PLATFORM", "windows:darkmode=0")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from vexa_core.database.db import DatabaseManager
from ui.main_window import MainWindow
from ui.styles import build_style, build_qpalette
from vexa_core.utils.helpers import set_moneda
from resources import resource_path
from vexa_core.version import VERSION, APP_NAME


def main() -> None:
    # En Windows, sin un AppUserModelID propio la barra de tareas no toma el
    # ícono de la ventana (queda el genérico). Debe setearse antes de crear la
    # ventana.
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("com.vexa.facturacion")
        except Exception:
            pass

    app = QApplication(sys.argv)
    # Fusion: el estilo multiplataforma de Qt, el recomendado para apps con QSS.
    # El nativo "windows11" pinta la selección y el foco con el acento del SISTEMA
    # (violeta en algunas PCs: barritas en las filas) y recorta bordes con QSS.
    app.setStyle("Fusion")
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("Facturacion")
    app.setApplicationVersion(VERSION)
    app.setWindowIcon(QIcon(str(resource_path("assets/vexa_symbol.ico"))))

    db = DatabaseManager()
    db.init_db()
    set_moneda(db.get_datos_empresa().get("moneda"))

    theme = db.get_config("theme") or "light"
    zoom = float(db.get_config("zoom") or 0.9)
    # La paleta va antes que el stylesheet: cubre lo que el CSS no puede
    # (texto de los popups de autocompletado y vistas de items).
    app.setPalette(build_qpalette(theme))
    app.setStyleSheet(build_style(theme, zoom))  # must be set before creating any widgets

    # Primera ejecución: si no hay empresa configurada, pedir los datos base.
    empresa = db.get_datos_empresa()
    if not (empresa.get("nombre") or "").strip() and not db.get_config("onboarding_done"):
        from ui.onboarding import run_onboarding
        if not run_onboarding(db):
            sys.exit(0)  # cerró sin completar: no se entra a la app
        set_moneda(db.get_datos_empresa().get("moneda"))

    window = MainWindow(db)
    window.show()
    window.play_intro()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
