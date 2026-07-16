"""Sección Inicio: dashboard con saludo, métricas, facturas recientes y accesos.

Reemplaza el viejo landing de tarjetas 2×2. Es una sección más de la app (el
sidebar queda siempre visible); emite `navigate(key)` cuando el usuario toca un
acceso rápido o un CTA del encabezado."""

from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
    QScrollArea, QPushButton, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QImage, QColor

from ui.icons import svg_pixmap, svg_icon
from ui.styles import get_palette
from vexa_core.utils.helpers import leer_tema, leer_zoom, fmt_ar
from resources import resource_path


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


_DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _fecha_larga(d: datetime) -> str:
    return f"{_DIAS[d.weekday()]}, {d.day} de {_MESES[d.month - 1]} {d.year}"


def _saludo(d: datetime) -> str:
    h = d.hour
    if 6 <= h < 13:
        return "Buen día"
    if 13 <= h < 20:
        return "Buenas tardes"
    return "Buenas noches"


class HomeWidget(QWidget):
    """Dashboard de la sección Inicio."""

    navigate = Signal(str)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._theme = leer_tema(db)
        self._zoom = leer_zoom(db)
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._build()

    # ---------------------------------------------------------------- datos
    def _metrics(self) -> dict:
        facturas = self.db.get_facturas(tipo="FA")
        mes = datetime.now().strftime("%Y-%m")
        del_mes = [f for f in facturas if (f.get("fecha") or "")[:7] == mes]
        return {
            "fac_mes": len(del_mes),
            "fac_total": len(facturas),
            "clientes": len(self.db.get_all_clientes()),
            "productos": len(self.db.get_productos()),
            "recientes": facturas[:5],
        }

    # ---------------------------------------------------------------- build
    def _build(self) -> None:
        # Rehace todo el contenido (se llama al abrir, refrescar y cambiar tema/
        # zoom): la data y los colores de íconos dependen del estado actual.
        while self._outer.count():
            item = self._outer.takeAt(0)
            w = item.widget()
            if w is not None:
                # setParent(None) lo saca del árbol visual YA; deleteLater() solo
                # libera memoria en el próximo ciclo de eventos, así que sin esto
                # el contenido viejo seguía dibujándose debajo del nuevo (fantasma).
                w.setParent(None)
                w.deleteLater()

        pal = get_palette(self._theme)
        z = self._zoom
        m = self._metrics()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        # El dashboard nunca hace scroll horizontal: el contenido se comprime al
        # ancho del viewport (las tarjetas se achican para entrar).
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content = QWidget()
        scroll.setWidget(content)
        self._outer.addWidget(scroll)

        col = QVBoxLayout(content)
        col.setContentsMargins(round(34 * z), round(30 * z), round(34 * z), round(30 * z))
        col.setSpacing(round(18 * z))

        col.addLayout(self._header(pal, z))
        col.addLayout(self._kpis(pal, z, m))
        col.addLayout(self._bottom(pal, z, m))
        col.addStretch()

    def _header(self, pal, z) -> QHBoxLayout:
        now = datetime.now()
        row = QHBoxLayout()
        row.setSpacing(round(10 * z))

        left = QVBoxLayout()
        left.setSpacing(round(4 * z))
        fecha = QLabel(_fecha_larga(now))
        fecha.setProperty("role", "dash-date")
        empresa = (self.db.get_datos_empresa().get("nombre") or "").strip() or "Vexa"
        greet = QLabel(f"{_saludo(now)}, {empresa}.")
        greet.setProperty("role", "dash-greeting")
        left.addWidget(fecha)
        left.addWidget(greet)
        row.addLayout(left)
        row.addStretch()

        # Sólo "Nueva factura": Etiquetas ya está en el sidebar, en los accesos
        # rápidos y en la tarjeta promo, así que acá sería un botón duplicado.
        btn_fa = self._cta("  Nueva factura", "plus", pal, z, lambda: self.navigate.emit("documentos"))
        row.addWidget(btn_fa, alignment=Qt.AlignBottom)
        return row

    def _cta(self, text, icon, pal, z, slot) -> QPushButton:
        b = QPushButton(text)
        b.setIcon(svg_icon(icon, round(16 * z), pal["accent_text"]))
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(slot)
        return b

    def _kpis(self, pal, z, m) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(round(16 * z))
        row.addWidget(self._hero_card(pal, z, str(m["fac_mes"]),
                                      f"en {_MESES[datetime.now().month - 1]}"))
        row.addWidget(self._kpi_card(pal, z, "file-text", "Facturas",
                                     str(m["fac_total"]), "emitidas"))
        row.addWidget(self._kpi_card(pal, z, "users", "Clientes",
                                     str(m["clientes"]), "en cartera"))
        row.addWidget(self._kpi_card(pal, z, "layers", "Productos",
                                     str(m["productos"]), "en catálogo"))
        return row

    def _hero_card(self, pal, z, value, sub) -> QFrame:
        card = QFrame()
        card.setObjectName("dash_hero")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(round(20 * z), round(20 * z), round(20 * z), round(20 * z))
        lay.setSpacing(round(4 * z))
        cap = QLabel("FACTURAS ESTE MES")
        cap.setProperty("role", "hero-cap")
        val = QLabel(value)
        val.setProperty("role", "hero-value")
        s = QLabel(sub)
        s.setProperty("role", "hero-sub")
        lay.addWidget(cap)
        lay.addWidget(val)
        lay.addWidget(s)
        return card

    def _kpi_card(self, pal, z, icon, cap, value, sub) -> QFrame:
        card = QFrame()
        card.setObjectName("dash_kpi")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(round(20 * z), round(20 * z), round(20 * z), round(20 * z))
        lay.setSpacing(round(4 * z))
        head = QHBoxLayout()
        head.setSpacing(round(8 * z))
        ico = QLabel()
        ico.setPixmap(svg_pixmap(icon, round(16 * z), pal["muted1"]))
        c = QLabel(cap.upper())
        c.setProperty("role", "kpi-cap")
        head.addWidget(ico)
        head.addWidget(c)
        head.addStretch()
        val = QLabel(value)
        val.setProperty("role", "kpi-value")
        s = QLabel(sub)
        s.setProperty("role", "kpi-sub")
        lay.addLayout(head)
        lay.addWidget(val)
        lay.addWidget(s)
        return card

    def _bottom(self, pal, z, m) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(round(16 * z))
        row.addWidget(self._recientes(pal, z, m["recientes"]), 17)
        right = QVBoxLayout()
        right.setSpacing(round(16 * z))
        right.addWidget(self._accesos(pal, z))
        right.addWidget(self._promo(pal, z))
        right.addStretch()
        wrap = QWidget()
        wrap.setObjectName("plain_box")
        wrap.setLayout(right)
        row.addWidget(wrap, 10)
        return row

    def _recientes(self, pal, z, facturas) -> QFrame:
        card = QFrame()
        card.setObjectName("dash_panel")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(round(22 * z), round(18 * z), round(22 * z), round(18 * z))
        lay.setSpacing(round(10 * z))

        head = QHBoxLayout()
        title = QLabel("Facturas recientes")
        title.setProperty("role", "panel-title")
        link = QLabel("Ver todas →")
        link.setProperty("role", "panel-link")
        link.setCursor(Qt.PointingHandCursor)
        link.mouseReleaseEvent = lambda e: self.navigate.emit("documentos")
        head.addWidget(title)
        head.addStretch()
        head.addWidget(link)
        lay.addLayout(head)

        cols = self._rec_row(z, "NÚMERO", "CLIENTE", "TOTAL", role="col-head")
        lay.addLayout(cols)

        if not facturas:
            empty = QLabel("Todavía no emitiste facturas.")
            empty.setProperty("role", "rec-empty")
            lay.addWidget(empty)
        for f in facturas:
            sep = QFrame()
            sep.setObjectName("dash_row_sep")
            sep.setFixedHeight(1)
            lay.addWidget(sep)
            num = f"FA-{f.get('ejercicio')}-{f.get('numero') or ''}"
            cli = f.get("cliente_nombre") or "—"
            tot = fmt_ar(f.get("total") or 0)
            lay.addLayout(self._rec_row(z, num, cli, tot))
        lay.addStretch()
        return card

    def _rec_row(self, z, num, cli, tot, role=None) -> QGridLayout:
        g = QGridLayout()
        g.setContentsMargins(0, round(3 * z), 0, round(3 * z))
        g.setColumnMinimumWidth(0, round(96 * z))
        g.setColumnStretch(1, 1)
        g.setColumnMinimumWidth(2, round(96 * z))
        a = QLabel(num); b = QLabel(cli); c = QLabel(tot)
        c.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if role:
            for lb in (a, b, c):
                lb.setProperty("role", role)
        else:
            a.setProperty("role", "rec-num")
            b.setProperty("role", "rec-cli")
            c.setProperty("role", "rec-total")
        g.addWidget(a, 0, 0)
        g.addWidget(b, 0, 1)
        g.addWidget(c, 0, 2)
        return g

    def _accesos(self, pal, z) -> QFrame:
        card = QFrame()
        card.setObjectName("dash_panel")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(round(20 * z), round(18 * z), round(20 * z), round(18 * z))
        lay.setSpacing(round(12 * z))
        title = QLabel("Accesos rápidos")
        title.setProperty("role", "panel-title")
        lay.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(round(10 * z))
        acc = [
            ("Nueva factura", "plus", "documentos"),
            ("Imprimir etiquetas", "tag", "etiquetas"),
            ("Nuevo cliente", "users", "clientes"),
            ("Nuevo producto", "layers", "conceptos"),
        ]
        for i, (label, icon, key) in enumerate(acc):
            grid.addWidget(self._quick(pal, z, label, icon, key), i // 2, i % 2)
        lay.addLayout(grid)
        return card

    def _quick(self, pal, z, label, icon, key) -> QPushButton:
        b = QPushButton(f"  {label}")
        b.setObjectName("dash_quick")
        b.setIcon(svg_icon(icon, round(18 * z), pal["accent"]))
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda: self.navigate.emit(key))
        return b

    def _promo(self, pal, z) -> QFrame:
        card = QFrame()
        card.setObjectName("dash_promo")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(round(20 * z), round(18 * z), round(20 * z), round(18 * z))
        lay.setSpacing(round(8 * z))
        head = QHBoxLayout()
        head.setSpacing(round(10 * z))
        ico = QLabel()
        ico.setPixmap(svg_pixmap("tag", round(18 * z), pal["accent"]))
        title = QLabel("Generador de etiquetas")
        title.setProperty("role", "panel-title")
        head.addWidget(ico)
        head.addWidget(title)
        head.addStretch()
        lay.addLayout(head)
        desc = QLabel("Armá la cola de impresión por código y talle, y generá las "
                      "planchas A4 listas para imprimir.")
        desc.setProperty("role", "home-sub")
        desc.setWordWrap(True)
        lay.addWidget(desc)
        btn = QPushButton("Abrir generador →")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: self.navigate.emit("etiquetas"))
        lay.addWidget(btn, alignment=Qt.AlignLeft)
        return card

    # ---------------------------------------------------------------- API
    def refresh(self) -> None:
        self._build()

    def set_theme_zoom(self, theme: str, zoom: float) -> None:
        self._theme = theme
        self._zoom = zoom
        self._build()
