"""Base común de las pantallas de listado (Clientes, Productos, Documentos).

Las tres compartían casi el mismo esqueleto (header con título + botones,
barra de búsqueda, tabla, fila de acciones con contador, selección y repintado
de íconos al cambiar tema/zoom). `ListPage` centraliza todo eso y deja a cada
subclase solo lo propio: qué columnas tiene, cómo llena cada fila y qué
consulta a la base.

Ganchos que implementa la subclase:
    COLUMNS, TITULO, SUBTITULO, SEARCH_PLACEHOLDER, SEARCH_MAXW, ROW_H
    _header_buttons()      -> botones de la derecha del header (ej. "Nuevo")
    _action_widgets()      -> botones de la fila inferior (Editar/Eliminar/...)
    _configure_columns(hh) -> modos de resize / anchos / orden de la tabla
    _resize_columns(hh)    -> reajuste de anchos al cambiar zoom (opcional)
    _query(search)         -> filas desde la base
    _pre_render(items)     -> preparación previa al llenado (opcional)
    _fill_row(row, item)   -> celdas de una fila
    _count_text(total)     -> texto del contador
    _on_nuevo / _on_editar / _on_eliminar
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QMessageBox,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor

from ui.icons import svg_icon
from ui.styles import get_palette
from utils.helpers import leer_zoom, leer_tema


class ListPage(QWidget):
    TITULO = ""
    SUBTITULO = ""
    SEARCH_PLACEHOLDER = "Buscar..."
    SEARCH_MAXW = 400
    COLUMNS: list[str] = []
    ROW_H = 42

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._zoom = leer_zoom(db)
        self._pal = get_palette(leer_tema(db))
        self._items: list[dict] = []
        # (boton, icon_name, size, color_key) para repintar al cambiar tema.
        self._theme_icons: list[tuple] = []
        # botones que dependen de que haya una fila seleccionada.
        self._action_buttons: list[QPushButton] = []
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------ armado
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        layout.addLayout(self._build_header())
        extra = self._build_below_header()
        if extra is not None:
            layout.addWidget(extra)
        layout.addLayout(self._build_search())
        self._table = self._build_table()
        layout.addWidget(self._table)
        layout.addLayout(self._build_actions())
        self._update_actions()

    def _build_header(self) -> QHBoxLayout:
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        h = QLabel(self.TITULO)
        h.setProperty("role", "page-title")
        titles.addWidget(h)
        if self.SUBTITULO:
            s = QLabel(self.SUBTITULO)
            s.setProperty("role", "page-subtitle")
            titles.addWidget(s)
        header.addLayout(titles)
        header.addStretch()
        for btn in self._header_buttons():
            header.addWidget(btn)
        return header

    def _build_below_header(self):
        """Widget opcional entre el header y la búsqueda (ej. KPIs)."""
        return None

    def _build_search(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setObjectName("search_input")
        self._search.setPlaceholderText(self.SEARCH_PLACEHOLDER)
        # Ícono de lupa dentro del campo, a la izquierda (look moderno).
        self._search_action = self._search.addAction(
            svg_icon("search", 16, self._pal["muted2"]), QLineEdit.LeadingPosition)
        self._search.textChanged.connect(lambda _: self.refresh())
        row.addWidget(self._search)
        return row

    def _build_table(self) -> QTableWidget:
        table = QTableWidget()
        # Asignado ya acá (además de en _build_ui) para que _configure_columns
        # pueda tocar self._table (ej. alinear un header) durante el armado.
        self._table = table
        table.setColumnCount(len(self.COLUMNS))
        table.setHorizontalHeaderLabels(self.COLUMNS)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setWordWrap(False)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setFocusPolicy(Qt.ClickFocus)
        table.doubleClicked.connect(self._on_editar)
        table.selectionModel().selectionChanged.connect(self._update_actions)
        self._configure_columns(table.horizontalHeader())
        return table

    def _build_actions(self) -> QHBoxLayout:
        actions = QHBoxLayout()
        actions.setSpacing(8)
        for btn in self._action_widgets():
            actions.addWidget(btn)
        actions.addStretch()
        self._count_lbl = QLabel()
        self._count_lbl.setProperty("role", "page-subtitle")
        actions.addWidget(self._count_lbl)
        return actions

    # ------------------------------------------------- helpers subclase
    def _boton(self, text, icon, color_key, obj_name=None, slot=None,
               size=14, needs_selection=False) -> QPushButton:
        """Crea un botón de acción con su ícono registrado para repintarse al
        cambiar tema. `needs_selection` lo deshabilita si no hay fila elegida."""
        btn = QPushButton(text)
        btn.setIcon(svg_icon(icon, size, self._pal[color_key]))
        btn.setIconSize(QSize(size, size))
        if obj_name:
            btn.setObjectName(obj_name)
        btn.setCursor(Qt.PointingHandCursor)
        if slot is not None:
            btn.clicked.connect(slot)
        self._theme_icons.append((btn, icon, size, color_key))
        if needs_selection:
            self._action_buttons.append(btn)
        return btn

    def _cell(self, text: str, align=Qt.AlignLeft | Qt.AlignVCenter,
              accent=False) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(align)
        if accent:   # identificador destacado (estilo enlace) en la 1ª columna
            item.setForeground(QColor(self._pal["accent"]))
            f = item.font()
            f.setBold(True)
            item.setFont(f)
        return item

    def _confirmar(self, mensaje: str, titulo: str = "Confirmar eliminación") -> bool:
        resp = QMessageBox.question(
            self, titulo, mensaje, QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        return resp == QMessageBox.Yes

    # ----------------------------------------------- selección / refresh
    def _selected(self) -> dict | None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._items):
            return None
        return self._items[row]

    def _update_actions(self) -> None:
        has = self._selected() is not None
        for btn in self._action_buttons:
            btn.setEnabled(has)

    def refresh(self) -> None:
        search = self._search.text().strip() if hasattr(self, "_search") else None
        self._items = self._query(search or None)
        self._pre_render(self._items)
        self._table.setRowCount(0)
        self._table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            self._fill_row(row, item)
            self._table.setRowHeight(row, round(self.ROW_H * self._zoom))
        if hasattr(self, "_count_lbl"):
            self._count_lbl.setText(self._count_text(len(self._items)))
        self._update_actions()

    def set_theme_zoom(self, theme: str, zoom: float) -> None:
        self._zoom = zoom
        self._pal = get_palette(theme)
        self._search_action.setIcon(svg_icon("search", 16, self._pal["muted2"]))
        for btn, icon, size, color_key in self._theme_icons:
            btn.setIcon(svg_icon(icon, size, self._pal[color_key]))
        self._resize_columns(self._table.horizontalHeader())

    # -------------------------------------------- ganchos por defecto
    def _header_buttons(self) -> list:
        return []

    def _action_widgets(self) -> list:
        return []

    def _configure_columns(self, header) -> None:
        pass

    def _resize_columns(self, header) -> None:
        pass

    def _pre_render(self, items) -> None:
        pass

    def _count_text(self, total: int) -> str:
        return str(total)

    def _query(self, search):
        raise NotImplementedError

    def _fill_row(self, row: int, item: dict) -> None:
        raise NotImplementedError

    def _on_nuevo(self) -> None:
        pass

    def _on_editar(self) -> None:
        pass

    def _on_eliminar(self) -> None:
        pass
