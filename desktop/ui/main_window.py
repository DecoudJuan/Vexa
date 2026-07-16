from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QLabel, QStackedWidget, QFrame, QButtonGroup, QApplication,
    QGraphicsOpacityEffect,
)
from PySide6.QtCore import (
    Qt, QSize, QTimer, Signal, QPropertyAnimation, QEasingCurve,
    QRect, QParallelAnimationGroup,
)

from ui.icons import svg_icon
from ui.styles import build_style, get_palette, build_qpalette
from ui.home import HomeWidget, logo_symbol_pixmap, _logo_v_color
from ui.anim import fade_in
from ui.clientes import ClientesWidget
from ui.conceptos import ConceptosWidget
from ui.documentos import DocumentosWidget
from ui.etiquetas import EtiquetasWidget
from ui.configuracion import ConfiguracionWidget
from vexa_core.version import VERSION, APP_NAME

ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 0.8, 1.4, 0.05

_NAV_ITEMS = [
    ("inicio",        "Inicio",        "home"),
    ("clientes",      "Clientes",      "users"),
    ("conceptos",     "Productos",     "layers"),
    ("documentos",    "Facturas",      "file-text"),
    ("etiquetas",     "Etiquetas",     "tag"),
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


class _ClickableWidget(QWidget):
    """QWidget que emite `clicked` al soltar el mouse dentro suyo."""

    clicked = Signal()

    def mouseReleaseEvent(self, e):  # noqa: N802
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(e)


class MainWindow(QMainWindow):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self._theme = db.get_config("theme") or "light"
        self._zoom = float(db.get_config("zoom") or 0.9)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self._persist_preferences)
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(round(1150 * self._zoom), round(700 * self._zoom))
        self.resize(round(1320 * self._zoom), round(780 * self._zoom))
        self._current_key: str | None = None
        self._nav_positioned = False
        self._build_ui()
        self._navigate_to("inicio", animate=False)

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
        home = HomeWidget(self.db)
        home.navigate.connect(self._navigate_to)
        self._add_page("inicio", home)
        self._add_page("clientes", ClientesWidget(self.db))
        self._add_page("conceptos", ConceptosWidget(self.db))
        self._add_page("documentos", DocumentosWidget(self.db))
        self._add_page("etiquetas", EtiquetasWidget(self.db))
        self._add_page("configuracion",
                       ConfiguracionWidget(self.db, on_empresa_changed=self.actualizar_marca))

        self._build_statusbar()

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(round(210 * self._zoom))
        self._sidebar = sidebar

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 0, 12, 16)
        layout.setSpacing(4)

        # Marca clickeable (logo + "Vexa"): vuelve a la pantalla de inicio.
        brand = _ClickableWidget()
        brand.setObjectName("brand_click")
        brand.setCursor(Qt.PointingHandCursor)
        brand.setToolTip("Ir al inicio")
        brand.clicked.connect(lambda: self._navigate_to("inicio"))
        bl = QVBoxLayout(brand)
        bl.setContentsMargins(8, 20, 8, 16)
        bl.setSpacing(2)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        self._brand_logo = QLabel()
        # El QLabel toma por defecto el fondo 'base' (más claro que el 'crust' de
        # la sidebar) y se veía un recuadro blanco alrededor del logo.
        self._brand_logo.setStyleSheet("background: transparent;")
        self._brand_logo.setPixmap(logo_symbol_pixmap(round(26 * self._zoom), _logo_v_color(self._theme)))
        name_lbl = QLabel(APP_NAME)
        name_lbl.setObjectName("brand_name")
        top.addWidget(self._brand_logo)
        top.addWidget(name_lbl)
        top.addStretch()

        sub_lbl = QLabel(self._empresa_nombre())
        sub_lbl.setObjectName("brand_sub")
        self._brand_sub = sub_lbl
        bl.addLayout(top)
        bl.addWidget(sub_lbl)
        layout.addWidget(brand)

        sep = QFrame()
        sep.setObjectName("sidebar_sep")
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        layout.addWidget(sep)
        layout.addSpacing(6)

        # Indicador deslizante del ítem activo (se posiciona detrás de los
        # botones, que tienen fondo transparente). Se crea antes que los botones
        # y se baja en la pila para que el texto/ícono queden por encima.
        self._nav_indicator = QFrame(sidebar)
        self._nav_indicator.setObjectName("nav_indicator")
        self._nav_indicator.hide()

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
        self._brand_logo.setPixmap(logo_symbol_pixmap(round(26 * self._zoom), _logo_v_color(self._theme)))
        for btn in self._nav_btns.values():
            btn.setFixedHeight(round(44 * self._zoom))
        self.setMinimumSize(round(1150 * self._zoom), round(700 * self._zoom))
        # Reubicar el indicador tras recalcular alturas/anchos (sin animar).
        if self._current_key:
            QTimer.singleShot(0, lambda: self._position_nav_indicator(animate=False))

    def _persist_preferences(self) -> None:
        self.db.set_config("theme", self._theme)
        self.db.set_config("zoom", str(self._zoom))
        self._update_toolbar_row()

    def _build_statusbar(self) -> None:
        sb = self.statusBar()
        self._status_lbl = QLabel(f"  {self._empresa_nombre()}")
        self._status_lbl.setObjectName("status_rate")
        sb.addWidget(self._status_lbl)

    def actualizar_marca(self) -> None:
        """Refresca el nombre de la empresa en la sidebar y la barra de estado
        (se llama al guardar los datos de empresa en Configuración)."""
        nombre = self._empresa_nombre()
        if hasattr(self, "_brand_sub"):
            self._brand_sub.setText(nombre)
        if hasattr(self, "_status_lbl"):
            self._status_lbl.setText(f"  {nombre}")

    def _add_page(self, key: str, widget: QWidget) -> None:
        self.pages[key] = widget
        self.stack.addWidget(widget)

    def _position_nav_indicator(self, animate: bool) -> None:
        """Coloca el indicador del ítem activo bajo el botón seleccionado; con
        `animate` se desliza desde su posición actual (cambio entre secciones)."""
        ind = self._nav_indicator
        btn = self._nav_btns.get(self._current_key or "")
        if btn is None:
            return
        target = btn.geometry()
        if target.height() == 0:
            return
        ind.show()
        ind.lower()
        if animate and ind.geometry().height() > 0:
            anim = QPropertyAnimation(ind, b"geometry", self)
            anim.setDuration(220)
            anim.setStartValue(ind.geometry())
            anim.setEndValue(target)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.start()
            self._nav_ind_anim = anim  # evita que lo recolecte el GC
        else:
            ind.setGeometry(target)

    def _navigate_to(self, key: str, animate: bool = True) -> None:
        if key not in self.pages:
            return
        # Ya estamos en esa sección: no recargar ni re-animar.
        if key == self._current_key:
            return
        prev = self._current_key
        self.stack.setCurrentWidget(self.pages[key])
        if key in self._nav_btns:
            self._nav_btns[key].setChecked(True)
        self._current_key = key
        # El indicador se desliza entre ítems cuando ya había una sección activa;
        # en el primer render (prev None) se coloca sin animar. Si aún no se
        # midió la geometría (ventana no mostrada), showEvent lo recoloca.
        self._position_nav_indicator(animate=animate and prev is not None)
        page = self.pages[key]
        if hasattr(page, "refresh"):
            page.refresh()
        if animate:
            fade_in(page)

    def _empresa_nombre(self) -> str:
        empresa = self.db.get_datos_empresa()
        return (empresa.get("nombre") or "").upper() or "MI EMPRESA"

    def showEvent(self, e):  # noqa: N802
        # La geometría de los botones de la sidebar recién existe cuando la
        # ventana se muestra; posicionar el indicador del ítem activo en el
        # primer show (antes salía en 0 porque se midió con layout sin resolver).
        super().showEvent(e)
        if not self._nav_positioned:
            self._nav_positioned = True
            QTimer.singleShot(0, lambda: self._position_nav_indicator(animate=False))

    # ---------------------------------------------------------------- intro
    def play_intro(self, hold_ms: int = 600, move_ms: int = 750) -> None:
        """Arranque: la V aparece centrada sobre toda la ventana; tras una pausa
        se desplaza y encoge hasta el lugar del logo de la marca en la sidebar,
        mientras el fondo opaco se desvanece revelando el dashboard. Se llama al
        abrir el programa, después de show()."""
        pal = get_palette(self._theme)
        zoom = self._zoom
        logo = getattr(self, "_brand_logo", None)

        overlay = QWidget(self)
        overlay.setObjectName("intro_overlay")
        overlay.setGeometry(self.rect())

        # Fondo opaco que se desvanece: al hacerlo, la app (sidebar + dashboard)
        # va "apareciendo" detrás.
        bg = QWidget(overlay)
        bg.setObjectName("intro_bg")
        bg.setStyleSheet(f"#intro_bg {{ background-color: {pal['base']}; }}")
        bg.setGeometry(overlay.rect())

        # La V que viaja del centro al lugar del logo real de la sidebar.
        big = round(150 * zoom)
        small = round(26 * zoom)  # tamaño del logo de la marca en la sidebar
        v = QLabel(overlay)
        v.setScaledContents(True)
        v.setStyleSheet("background: transparent;")
        v.setPixmap(logo_symbol_pixmap(big, _logo_v_color(self._theme)))

        cx, cy = overlay.width() // 2, overlay.height() // 2
        start = QRect(cx - big // 2, cy - big // 2, big, big)

        # Destino = centro del logo real de la sidebar (mapeado a coords de la
        # ventana). Se oculta el logo real durante la intro y se revela al final,
        # así el traspaso entre la V animada y la real es sin salto.
        tx, ty = cx, cy - big
        if logo is not None:
            c = logo.mapTo(self, logo.rect().center())
            tx, ty = c.x(), c.y()
            logo.setGraphicsEffect(QGraphicsOpacityEffect(logo))
            logo.graphicsEffect().setOpacity(0.0)
        end = QRect(tx - small // 2, ty - small // 2, small, small)

        v.setGeometry(start)
        v.raise_()
        overlay.show()
        self._intro_overlay = overlay
        self._intro_bg = bg

        def _start_move() -> None:
            bg_effect = QGraphicsOpacityEffect(bg)
            bg.setGraphicsEffect(bg_effect)

            move = QPropertyAnimation(v, b"geometry", self)
            move.setDuration(move_ms)
            move.setStartValue(start)
            move.setEndValue(end)
            move.setEasingCurve(QEasingCurve.InOutCubic)

            fade = QPropertyAnimation(bg_effect, b"opacity", self)
            fade.setDuration(move_ms)
            fade.setStartValue(1.0)
            fade.setEndValue(0.0)
            fade.setEasingCurve(QEasingCurve.InOutCubic)

            group = QParallelAnimationGroup(self)
            group.addAnimation(move)
            group.addAnimation(fade)

            def _done() -> None:
                if logo is not None:
                    logo.setGraphicsEffect(None)  # revela el logo real
                overlay.deleteLater()

            group.finished.connect(_done)
            group.start()
            self._intro_group = group  # evita que lo recolecte el GC

        QTimer.singleShot(hold_ms, _start_move)

    def resizeEvent(self, e):  # noqa: N802
        # Mientras el overlay de arranque está visible, que cubra toda la ventana
        # aunque se redimensione.
        super().resizeEvent(e)
        overlay = getattr(self, "_intro_overlay", None)
        if overlay is not None and overlay.isVisible():
            overlay.setGeometry(self.rect())
            bg = getattr(self, "_intro_bg", None)
            if bg is not None:
                bg.setGeometry(overlay.rect())
