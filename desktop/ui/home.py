"""Pantalla de inicio (landing): tarjetas de acceso a las 4 secciones.

Es la primera pantalla al abrir la app; la barra lateral recién aparece cuando
se elige una sección. Cada tarjeta emite `clicked(key)` con la clave de la
sección, que la ventana principal usa para navegar."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QImage, QColor

from ui.icons import svg_pixmap
from ui.styles import get_palette
from utils.helpers import leer_tema, leer_zoom
from utils.resources import resource_path
from version import APP_NAME


def logo_symbol_pixmap(size: int, v_color: str | None = None) -> QPixmap:
    """Símbolo de la marca (la V con el punto), fondo transparente, escalado.

    La V es azul muy oscuro (casi negra): en tema oscuro se pierde contra el
    fondo, así que `v_color` permite recolorearla (ej. al color de texto claro)
    conservando el punto violeta. Sin `v_color` se usa tal cual (tema claro)."""
    pm = QPixmap(str(resource_path("assets/vexa_symbol.png")))
    if v_color:
        col = QColor(v_color)
        img = pm.toImage().convertToFormat(QImage.Format_ARGB32)
        for y in range(img.height()):
            for x in range(img.width()):
                c = img.pixelColor(x, y)
                if c.alpha() == 0:
                    continue
                # El punto es netamente azul (blue domina); la V es casi negra.
                # Sólo se recolorea la V, preservando el alfa (antialias suave).
                if c.blue() > c.red() + 40 and c.blue() > 120:
                    continue
                img.setPixelColor(x, y, QColor(col.red(), col.green(), col.blue(), c.alpha()))
        pm = QPixmap.fromImage(img)
    return pm.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def _logo_v_color(theme: str) -> str | None:
    """Color para la V del logo según el tema (None = original, tema claro)."""
    return get_palette(theme)["text"] if theme == "dark" else None

# (clave, título, subtítulo, ícono) — la clave coincide con la de _NAV_ITEMS.
_CARDS = [
    ("clientes",      "Clientes",      "Alta y gestión de clientes",       "users"),
    ("conceptos",     "Productos",     "Catálogo y listas de precios",     "layers"),
    ("documentos",    "Documentos",    "Facturas, presupuestos y pedidos", "file-text"),
    ("configuracion", "Configuración", "Datos de la empresa y AFIP",       "settings"),
]


class _HomeCard(QFrame):
    """Tarjeta clickeable con ícono grande, título y subtítulo."""

    clicked = Signal(str)

    def __init__(self, key, title, subtitle, icon_name, zoom, pal, parent=None):
        super().__init__(parent)
        self._key = key
        self._icon_name = icon_name
        self.setObjectName("home_card")
        self.setCursor(Qt.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 28, 28, 28)
        lay.setSpacing(6)
        lay.setAlignment(Qt.AlignCenter)

        self._chip = QLabel()
        self._chip.setObjectName("home_icon_chip")
        self._chip.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._chip, alignment=Qt.AlignHCenter)
        lay.addSpacing(6)

        title_lbl = QLabel(title)
        title_lbl.setProperty("role", "home-title")
        title_lbl.setAlignment(Qt.AlignCenter)
        sub_lbl = QLabel(subtitle)
        sub_lbl.setProperty("role", "home-sub")
        sub_lbl.setAlignment(Qt.AlignCenter)
        sub_lbl.setWordWrap(True)
        lay.addWidget(title_lbl)
        lay.addWidget(sub_lbl)

        self.set_theme_zoom(pal, zoom)

    def set_theme_zoom(self, pal: dict, zoom: float) -> None:
        chip = round(72 * zoom)
        icon = round(34 * zoom)
        self._chip.setFixedSize(chip, chip)
        self._chip.setPixmap(svg_pixmap(self._icon_name, icon, pal["accent"]))
        self.setMinimumSize(round(230 * zoom), round(190 * zoom))

    def mouseReleaseEvent(self, e):  # noqa: N802
        # Sólo dispara si el click suelta dentro de la tarjeta (arrastrar afuera
        # cancela), como cualquier botón.
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit(self._key)
        super().mouseReleaseEvent(e)


class HomeWidget(QWidget):
    """Landing con las 4 tarjetas de sección centradas."""

    navigate = Signal(str)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._theme = leer_tema(db)
        self._zoom = leer_zoom(db)
        self._cards: list[_HomeCard] = []
        self._build_ui()

    def _build_ui(self) -> None:
        pal = get_palette(self._theme)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 40, 40, 40)
        outer.addStretch()

        self._logo = QLabel()
        self._logo.setAlignment(Qt.AlignCenter)
        self._logo.setPixmap(logo_symbol_pixmap(round(64 * self._zoom), _logo_v_color(self._theme)))
        outer.addWidget(self._logo)
        outer.addSpacing(10)

        self._brand = QLabel(APP_NAME)
        self._brand.setObjectName("home_brand")
        self._brand.setAlignment(Qt.AlignCenter)
        self._sub = QLabel(self._empresa_nombre())
        self._sub.setObjectName("home_brand_sub")
        self._sub.setAlignment(Qt.AlignCenter)
        outer.addWidget(self._brand)
        outer.addWidget(self._sub)
        outer.addSpacing(34)

        # Grid 2×2 centrado (no se estira a todo el ancho).
        row = QHBoxLayout()
        row.addStretch()
        holder = QWidget()
        grid = QGridLayout(holder)
        grid.setSpacing(round(20 * self._zoom))
        grid.setContentsMargins(0, 0, 0, 0)
        for i, (key, title, subtitle, icon_name) in enumerate(_CARDS):
            card = _HomeCard(key, title, subtitle, icon_name, self._zoom, pal)
            card.clicked.connect(self.navigate.emit)
            grid.addWidget(card, i // 2, i % 2)
            self._cards.append(card)
        row.addWidget(holder)
        row.addStretch()
        outer.addLayout(row)

        outer.addStretch()

    def refresh(self) -> None:
        self._sub.setText(self._empresa_nombre())

    def set_theme_zoom(self, theme: str, zoom: float) -> None:
        self._theme = theme
        self._zoom = zoom
        pal = get_palette(theme)
        self._logo.setPixmap(logo_symbol_pixmap(round(64 * zoom), _logo_v_color(theme)))
        for card in self._cards:
            card.set_theme_zoom(pal, zoom)

    def _empresa_nombre(self) -> str:
        nombre = (self.db.get_datos_empresa().get("nombre") or "").upper()
        return nombre or "MI EMPRESA"
