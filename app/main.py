import sys

from PySide6.QtWidgets import QApplication
from database.db import DatabaseManager
from ui.main_window import MainWindow
from ui.styles import build_style, build_qpalette
from utils.helpers import set_moneda
from version import VERSION


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Facturación")
    app.setOrganizationName("Facturacion")
    app.setApplicationVersion(VERSION)

    db = DatabaseManager()
    db.init_db()
    set_moneda(db.get_datos_empresa().get("moneda"))

    theme = db.get_config("theme") or "dark"
    zoom = float(db.get_config("zoom") or 0.9)
    # La paleta va antes que el stylesheet: cubre lo que el CSS no puede
    # (texto de los popups de autocompletado y vistas de items).
    app.setPalette(build_qpalette(theme))
    app.setStyleSheet(build_style(theme, zoom))  # must be set before creating any widgets

    window = MainWindow(db)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
