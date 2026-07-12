from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QLabel, QStackedWidget, QFrame, QButtonGroup, QApplication,
)
from PySide6.QtCore import Qt, QSize, QTimer

from ui.icons import svg_icon
from ui.styles import build_style, get_palette, build_qpalette
from ui.clientes import ClientesWidget
from ui.conceptos import ConceptosWidget
from ui.documentos import DocumentosWidget
from ui.cobros import CobrosWidget
from ui.configuracion import ConfiguracionWidget
from version import VERSION, APP_NAME

ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 0.8, 1.4, 0.05

_NAV_ITEMS = [
    ("clientes",      "Clientes",      "users"),
    ("conceptos",     "Productos",     "layers"),
    ("documentos",    "Documentos",    "file-text"),
    ("cobros",        "Cobros",        "credit-card"),
    ("configuracion", "Configuración", "settings"),
]


class _NavButton(QPushButton):
    def __init__(self, icon_name: str, label: str, zoom: float = 1.0, pal: dict | None = None, parent=None):
        super().__init__(parent)
        self._icon_name = icon_name
        pal = pal or get_palette("dark")
        self._icon_off = svg_icon(icon_name, 17, pal["muted1"])
        self._icon_on = svg_icon(icon_name, 17, pal["accent"])
        self.setIcon(self._icon_off)
        self.setIconSize(QSize(17, 17))
        self.setText(f"  {label}")
        self.setCheckable(True)
        self.setObjectName("nav_button")
        self.setFixedHeight(round(44 * zoom))
        self.setCursor(Qt.PointingHandCursor)
        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool) -> None:
        self.setIcon(self._icon_on if checked else self._icon_off)

    def set_pal(self, pal: dict) -> None:
        """Regenera los íconos con la paleta del tema actual (se llama al
        cambiar de tema; los íconos no forman parte del stylesheet y por
        eso no se repintan solos)."""
        self._icon_off = svg_icon(self._icon_name, 17, pal["muted1"])
        self._icon_on = svg_icon(self._icon_name, 17, pal["accent"])
        self.setIcon(self._icon_on if self.isChecked() else self._icon_off)


class MainWindow(QMainWindow):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self._theme = db.get_config("theme") or "dark"
        self._zoom = float(db.get_config("zoom") or 0.9)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self._persist_preferences)
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(round(1150 * self._zoom), round(700 * self._zoom))
        self.resize(round(1320 * self._zoom), round(780 * self._zoom))
        self._build_ui()
        self._navigate_to("clientes")

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        self.pages: dict[str, QWidget] = {}
        self._add_page("clientes", ClientesWidget(self.db))
        self._add_page("conceptos", ConceptosWidget(self.db))
        self._add_page("documentos", DocumentosWidget(self.db))
        self._add_page("cobros", CobrosWidget(self.db))
        self._add_page("configuracion", ConfiguracionWidget(self.db))

        self._build_statusbar()

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(round(210 * self._zoom))
        self._sidebar = sidebar

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 0, 12, 16)
        layout.setSpacing(4)

        brand = QWidget()
        bl = QVBoxLayout(brand)
        bl.setContentsMargins(8, 20, 8, 16)
        bl.setSpacing(2)
        name_lbl = QLabel(APP_NAME)
        name_lbl.setObjectName("brand_name")
        sub_lbl = QLabel(self._empresa_nombre())
        sub_lbl.setObjectName("brand_sub")
        self._brand_sub = sub_lbl
        bl.addWidget(name_lbl)
        bl.addWidget(sub_lbl)
        layout.addWidget(brand)

        sep = QFrame()
        sep.setObjectName("sidebar_sep")
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        layout.addWidget(sep)
        layout.addSpacing(6)

        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)
        self._nav_btns: dict[str, _NavButton] = {}

        pal = get_palette(self._theme)
        for key, label, icon_name in _NAV_ITEMS:
            btn = _NavButton(icon_name, label, zoom=self._zoom, pal=pal)
            btn.clicked.connect(lambda _, k=key: self._navigate_to(k))
            layout.addWidget(btn)
            self._btn_group.addButton(btn)
            self._nav_btns[key] = btn

        layout.addStretch()

        layout.addWidget(self._build_toolbar_row())
        layout.addSpacing(6)

        ver_lbl = QLabel(f"v{VERSION}")
        ver_lbl.setObjectName("version_label")
        ver_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(ver_lbl)

        return sidebar

    def _build_toolbar_row(self) -> QWidget:
        """Fila compacta con zoom (−/+) y el toggle de tema, sin ocupar
        espacio de más en la sidebar."""
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(2, 0, 2, 0)
        h.setSpacing(4)

        self._btn_zoom_out = QPushButton("−")
        self._btn_zoom_out.setObjectName("zoom_button")
        self._btn_zoom_out.setCursor(Qt.PointingHandCursor)
        self._btn_zoom_out.setToolTip("Alejar")
        self._btn_zoom_out.clicked.connect(self._on_zoom_out)

        self._zoom_lbl = QLabel()
        self._zoom_lbl.setObjectName("zoom_label")
        self._zoom_lbl.setAlignment(Qt.AlignCenter)
        self._zoom_lbl.setFixedWidth(round(34 * self._zoom))

        self._btn_zoom_in = QPushButton("+")
        self._btn_zoom_in.setObjectName("zoom_button")
        self._btn_zoom_in.setCursor(Qt.PointingHandCursor)
        self._btn_zoom_in.setToolTip("Acercar")
        self._btn_zoom_in.clicked.connect(self._on_zoom_in)

        self._btn_theme = QPushButton()
        self._btn_theme.setObjectName("theme_button")
        self._btn_theme.setCursor(Qt.PointingHandCursor)
        self._btn_theme.setToolTip("Cambiar entre modo claro y oscuro")
        self._btn_theme.setIconSize(QSize(round(15 * self._zoom), round(15 * self._zoom)))
        self._btn_theme.clicked.connect(self._on_toggle_theme)

        h.addWidget(self._btn_zoom_out)
        h.addWidget(self._zoom_lbl)
        h.addWidget(self._btn_zoom_in)
        h.addStretch()
        h.addWidget(self._btn_theme)

        self._update_toolbar_row()
        return row

    def _update_toolbar_row(self) -> None:
        self._zoom_lbl.setText(f"{round(self._zoom * 100)}%")
        self._zoom_lbl.setFixedWidth(round(34 * self._zoom))
        # El tamaño de los tres botones (−, +, tema) lo fija el CSS por #id
        # (min/max height y width iguales), que le gana a la regla general de
        # QPushButton y los mantiene compactos y del mismo alto. Acá solo se
        # actualiza el ícono del tema y su tamaño interno.
        pal = get_palette(self._theme)
        icono = "sun" if self._theme == "dark" else "moon"
        self._btn_theme.setIcon(svg_icon(icono, 15, pal["muted1"]))
        self._btn_theme.setIconSize(QSize(round(15 * self._zoom), round(15 * self._zoom)))

    def _on_zoom_in(self) -> None:
        self._zoom = min(ZOOM_MAX, round(self._zoom + ZOOM_STEP, 2))
        self._apply_style()

    def _on_zoom_out(self) -> None:
        self._zoom = max(ZOOM_MIN, round(self._zoom - ZOOM_STEP, 2))
        self._apply_style()

    def _on_toggle_theme(self) -> None:
        self._theme = "light" if self._theme == "dark" else "dark"
        self._apply_style()

    def _apply_style(self) -> None:
        # El estilo se reaplica al toque para que se sienta instantáneo;
        # el guardado a disco se posterga (debounce) para que clickear
        # zoom repetidas veces seguido no se sienta lento.
        QApplication.instance().setPalette(build_qpalette(self._theme))
        QApplication.instance().setStyleSheet(build_style(self._theme, self._zoom))
        self._update_toolbar_row()
        self._resize_for_zoom()
        self._update_nav_icons()
        self._propagate_appearance()
        self._save_timer.start()

    def _update_nav_icons(self) -> None:
        pal = get_palette(self._theme)
        for btn in self._nav_btns.values():
            btn.set_pal(pal)

    def _propagate_appearance(self) -> None:
        """Los widgets de cada página se crean una sola vez al arrancar la
        app y quedan vivos en el QStackedWidget; si no se les avisa acá,
        se quedan con el zoom/tema de ese momento para siempre y quedan
        descalibrados frente al stylesheet (que sí se reaplica solo),
        provocando que las filas de las tablas y los íconos queden
        superpuestos o con colores del tema viejo apenas se toca zoom o
        tema después de abierta la app."""
        for page in self.pages.values():
            if hasattr(page, "set_theme_zoom"):
                page.set_theme_zoom(self._theme, self._zoom)
            if hasattr(page, "refresh"):
                page.refresh()

    def _resize_for_zoom(self) -> None:
        """Ajusta las dimensiones que Qt no recalcula solo a partir del
        stylesheet (anchos/altos fijados por código, no por CSS), para que
        el zoom no termine recortando el texto de la sidebar."""
        self._sidebar.setFixedWidth(round(210 * self._zoom))
        for btn in self._nav_btns.values():
            btn.setFixedHeight(round(44 * self._zoom))
        self.setMinimumSize(round(1150 * self._zoom), round(700 * self._zoom))

    def _persist_preferences(self) -> None:
        self.db.set_config("theme", self._theme)
        self.db.set_config("zoom", str(self._zoom))
        self._update_toolbar_row()

    def _build_statusbar(self) -> None:
        sb = self.statusBar()
        lbl = QLabel(f"  {self._empresa_nombre()}")
        lbl.setObjectName("status_rate")
        sb.addWidget(lbl)

    def _add_page(self, key: str, widget: QWidget) -> None:
        self.pages[key] = widget
        self.stack.addWidget(widget)

    def _navigate_to(self, key: str) -> None:
        if key not in self.pages:
            return
        self.stack.setCurrentWidget(self.pages[key])
        if key in self._nav_btns:
            self._nav_btns[key].setChecked(True)
        page = self.pages[key]
        if hasattr(page, "refresh"):
            page.refresh()

    def _empresa_nombre(self) -> str:
        empresa = self.db.get_datos_empresa()
        return (empresa.get("nombre") or "").upper() or "MI EMPRESA"
