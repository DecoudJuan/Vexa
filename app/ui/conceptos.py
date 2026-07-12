import sqlite3

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLineEdit, QPushButton, QLabel, QDialog, QMessageBox, QHeaderView,
    QFrame, QAbstractItemView, QFileDialog,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QDoubleValidator, QColor, QBrush

from ui.icons import svg_icon, svg_pixmap
from ui.styles import get_palette
from ui.modal import BaseModal
from utils.excel_import import leer_lista_precios
from utils.helpers import leer_zoom, leer_tema, fmt_ar

_SEARCH_MAXW, _ROW_H = 400, 40
_COD_W = 110


class ConceptosWidget(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._zoom = leer_zoom(db)
        self._pal = get_palette(leer_tema(db))
        self._conceptos: list[dict] = []
        self._order = "nombre"   # 'nombre' | 'codigo' (clic en el encabezado)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        h = QLabel("Productos")
        h.setProperty("role", "page-title")
        s = QLabel("Catálogo de productos y servicios")
        s.setProperty("role", "page-subtitle")
        titles.addWidget(h)
        titles.addWidget(s)
        header.addLayout(titles)
        header.addStretch()

        self._btn_importar = QPushButton("  Importar lista de precios")
        self._btn_importar.setIcon(svg_icon("file-plus", 15, self._pal["text"]))
        self._btn_importar.setIconSize(QSize(15, 15))
        self._btn_importar.setObjectName("btn_secondary")
        self._btn_importar.setCursor(Qt.PointingHandCursor)
        self._btn_importar.clicked.connect(self._on_importar)
        header.addWidget(self._btn_importar)

        self._btn_nuevo = QPushButton("  Nuevo producto")
        self._btn_nuevo.setIcon(svg_icon("plus", 15, self._pal["accent_text"]))
        self._btn_nuevo.setIconSize(QSize(15, 15))
        self._btn_nuevo.setCursor(Qt.PointingHandCursor)
        self._btn_nuevo.clicked.connect(self._on_nuevo)
        header.addWidget(self._btn_nuevo)
        layout.addLayout(header)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self._search_icon_lbl = QLabel()
        self._search_icon_lbl.setPixmap(svg_pixmap("search", 16, self._pal["muted2"]))
        self._search_icon_lbl.setFixedSize(round(16 * self._zoom), round(16 * self._zoom))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Buscar por código o nombre...")
        self._search.setMaximumWidth(round(_SEARCH_MAXW * self._zoom))
        self._search.textChanged.connect(lambda _: self.refresh())
        search_row.addWidget(self._search_icon_lbl)
        search_row.addWidget(self._search)
        search_row.addStretch()
        layout.addLayout(search_row)

        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Código", "Nombre", "Precio"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setFocusPolicy(Qt.ClickFocus)
        # Sin esto, al seleccionar una fila el borde-izquierdo de 3px roba
        # ancho y el precio ("$ 7.173,93") se parte en dos renglones.
        self._table.setWordWrap(False)

        # Código = ancho fijo (clic para ordenar por código); Nombre = se
        # estira; Precio = ancho fijo pegado al borde derecho.
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Interactive)
        self._table.setColumnWidth(0, round(_COD_W * self._zoom))
        self._table.setColumnWidth(2, round(150 * self._zoom))
        # Clic en el encabezado Código/Nombre → reordena (por eso re-consultamos
        # a la base en vez de usar el sort nativo, que se pelea con los
        # cell-widgets de las filas "sin precio").
        hh.setSectionsClickable(True)
        hh.sectionClicked.connect(self._on_header_clicked)
        precio_head = self._table.horizontalHeaderItem(2)
        if precio_head is not None:
            precio_head.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._table.doubleClicked.connect(self._on_editar)
        self._table.selectionModel().selectionChanged.connect(self._update_actions)
        layout.addWidget(self._table)

        actions = QHBoxLayout()
        actions.setSpacing(8)

        self._btn_edit = QPushButton("  Editar")
        self._btn_edit.setIcon(svg_icon("edit", 14, self._pal["text"]))
        self._btn_edit.setIconSize(QSize(14, 14))
        self._btn_edit.setObjectName("btn_secondary")
        self._btn_edit.setCursor(Qt.PointingHandCursor)
        self._btn_edit.clicked.connect(self._on_editar)

        self._btn_del = QPushButton("  Eliminar")
        self._btn_del.setIcon(svg_icon("trash", 14, self._pal["danger"]))
        self._btn_del.setIconSize(QSize(14, 14))
        self._btn_del.setObjectName("btn_danger")
        self._btn_del.setCursor(Qt.PointingHandCursor)
        self._btn_del.clicked.connect(self._on_eliminar)

        for btn in (self._btn_edit, self._btn_del):
            actions.addWidget(btn)
        actions.addStretch()

        self._count_lbl = QLabel()
        self._count_lbl.setProperty("role", "page-subtitle")
        actions.addWidget(self._count_lbl)
        layout.addLayout(actions)
        self._update_actions()

    def _on_header_clicked(self, index: int) -> None:
        # Solo Código (0) y Nombre (1) reordenan; Precio (2) no.
        if index not in (0, 1):
            return
        nuevo = "codigo" if index == 0 else "nombre"
        if nuevo != self._order:
            self._order = nuevo
            self.refresh()

    def refresh(self) -> None:
        search = self._search.text().strip() if hasattr(self, "_search") else None
        self._conceptos = self.db.get_all_conceptos(search or None, order=self._order)
        # setRowCount(0) primero limpia cell-widgets viejos (badges) que si no
        # quedarían pegados al reordenarse/filtrarse las filas.
        self._table.setRowCount(0)
        self._table.setRowCount(len(self._conceptos))
        sin_precio = 0
        for row, c in enumerate(self._conceptos):
            cod = QTableWidgetItem((c.get("codigo") or "").strip() or "—")
            cod.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 0, cod)
            pvp = c["pvp"] or 0
            if pvp <= 0:
                sin_precio += 1
                self._table.setItem(row, 1, QTableWidgetItem(""))
                self._table.setCellWidget(row, 1, self._nombre_sin_precio(c["nombre"]))
                price = QTableWidgetItem(fmt_ar(0))
                price.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                price.setForeground(QBrush(QColor(self._pal["warn"])))
                self._table.setItem(row, 2, price)
            else:
                self._table.setItem(row, 1, QTableWidgetItem(c["nombre"]))
                price = QTableWidgetItem(fmt_ar(pvp))
                price.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self._table.setItem(row, 2, price)
            self._table.setRowHeight(row, round(_ROW_H * self._zoom))
        if hasattr(self, "_count_lbl"):
            total = len(self._conceptos)
            pl = "s" if total != 1 else ""
            extra = f" · {sin_precio} sin precio" if sin_precio else ""
            self._count_lbl.setText(f"{total} producto{pl}{extra}")
        self._update_actions()

    def _nombre_sin_precio(self, nombre: str) -> QWidget:
        """Celda de nombre para productos en $0: nombre + ícono SVG de alerta
        y el texto 'sin precio', SIN recuadro (fondo transparente)."""
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        h = QHBoxLayout(w)
        h.setContentsMargins(12, 0, 12, 0)
        h.setSpacing(8)
        name = QLabel(nombre)
        name.setStyleSheet(f"color:{self._pal['text']}; background: transparent;")
        ico = QLabel()
        ico.setPixmap(svg_pixmap("alert-triangle", round(14 * self._zoom), self._pal["warn"]))
        ico.setStyleSheet("background: transparent;")
        tag = QLabel("sin precio")
        tag.setStyleSheet(
            f"color:{self._pal['warn']}; font-size:11px; font-weight:700; background: transparent;"
        )
        h.addWidget(name)
        h.addSpacing(round(4 * self._zoom))
        h.addWidget(ico)
        h.addWidget(tag)
        h.addStretch()
        return w

    def _selected(self) -> dict | None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._conceptos):
            return None
        return self._conceptos[row]

    def _update_actions(self) -> None:
        has = self._selected() is not None
        for btn in (self._btn_edit, self._btn_del):
            btn.setEnabled(has)

    def set_theme_zoom(self, theme: str, zoom: float) -> None:
        self._zoom = zoom
        self._pal = get_palette(theme)
        self._search_icon_lbl.setFixedSize(round(16 * zoom), round(16 * zoom))
        self._search_icon_lbl.setPixmap(svg_pixmap("search", 16, self._pal["muted2"]))
        self._search.setMaximumWidth(round(_SEARCH_MAXW * zoom))
        self._table.setColumnWidth(0, round(_COD_W * zoom))
        self._table.setColumnWidth(2, round(150 * zoom))
        self._btn_importar.setIcon(svg_icon("file-plus", 15, self._pal["text"]))
        self._btn_nuevo.setIcon(svg_icon("plus", 15, self._pal["accent_text"]))
        self._btn_edit.setIcon(svg_icon("edit", 14, self._pal["text"]))
        self._btn_del.setIcon(svg_icon("trash", 14, self._pal["danger"]))

    def _on_nuevo(self) -> None:
        dlg = ConceptoDialog(zoom=self._zoom, theme=leer_tema(self.db), parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.db.create_concepto(dlg.get_data())
            self.refresh()

    def _on_editar(self) -> None:
        c = self._selected()
        if not c:
            return
        dlg = ConceptoDialog(concepto=c, zoom=self._zoom, theme=leer_tema(self.db), parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.db.update_concepto(c["id"], dlg.get_data())
            self.refresh()

    def _on_eliminar(self) -> None:
        c = self._selected()
        if not c:
            return
        resp = QMessageBox.question(
            self, "Confirmar eliminación",
            f"¿Eliminar el producto <b>{c['nombre']}</b>?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if resp == QMessageBox.Yes:
            try:
                self.db.delete_concepto(c["id"])
                self.refresh()
            except sqlite3.IntegrityError:
                QMessageBox.critical(
                    self, "No se puede eliminar",
                    "Este producto está usado en líneas de documentos existentes.",
                )

    def _on_importar(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar lista de precios", "", "Excel (*.xlsx *.xlsm)"
        )
        if not path:
            return
        try:
            items = leer_lista_precios(path)
        except Exception as exc:
            QMessageBox.critical(self, "Error al leer el archivo", str(exc))
            return
        if not items:
            QMessageBox.warning(
                self, "Sin datos",
                "No se encontraron artículos con precio en el archivo.\n"
                "Se esperan columnas 'ARTICULOS' y 'PRECIO'.",
            )
            return
        resumen = self.db.upsert_conceptos(items)
        QMessageBox.information(
            self, "Importación completa",
            f"{resumen['creados']} productos nuevos, "
            f"{resumen['actualizados']} con precio actualizado.",
        )
        self.refresh()


class ConceptoDialog(BaseModal):
    def __init__(self, concepto: dict | None = None, zoom: float = 1.0,
                 theme: str = "dark", parent=None):
        self._concepto = concepto
        self._data: dict | None = None
        titulo = "Editar producto" if concepto else "Nuevo producto"
        sub = "Modificá los datos del producto" if concepto else "Cargá un producto al catálogo"
        super().__init__(titulo, sub, icon="package", width=480, zoom=zoom, theme=theme, parent=parent)

        self.content.addWidget(self.section_label("NOMBRE *", "package"))
        self._nombre = QLineEdit()
        self._nombre.setObjectName("field")
        self._nombre.setPlaceholderText("Nombre del producto")
        self.content.addWidget(self._nombre)

        self.content.addWidget(self.section_label("CÓDIGO", "hash"))
        self._codigo = QLineEdit()
        self._codigo.setObjectName("field")
        self._codigo.setPlaceholderText("Ej. 020 (opcional)")
        self.content.addWidget(self._codigo)

        self.content.addWidget(self.section_label("PRECIO", "dollar-sign"))
        prow = QHBoxLayout()
        prow.setSpacing(self._S(8))
        unit = QLabel("$")
        unit.setObjectName("unit")
        self._pvp = QLineEdit()
        self._pvp.setObjectName("field")
        self._pvp.setPlaceholderText("0,00")
        self._pvp.setValidator(QDoubleValidator(0.0, 99_999_999.0, 2))
        prow.addWidget(unit)
        prow.addWidget(self._pvp, 1)
        self.content.addLayout(prow)
        self.content.addStretch()

        self.set_primary_action("Guardar", self._accept)

        if concepto:
            self._nombre.setText(concepto.get("nombre", ""))
            self._codigo.setText((concepto.get("codigo") or "").strip())
            self._pvp.setText(f"{float(concepto.get('pvp') or 0):.2f}")

    def _accept(self) -> None:
        nombre = self._nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Campo requerido", "El nombre es obligatorio.")
            return
        try:
            pvp = float((self._pvp.text() or "0").replace(",", "."))
        except ValueError:
            pvp = 0.0
        if pvp <= 0:
            QMessageBox.warning(self, "Falta el precio",
                                "El precio debe ser mayor que 0. Un producto no puede quedar sin precio.")
            self._pvp.setFocus()
            return
        self._data = {"nombre": nombre, "codigo": self._codigo.text().strip(), "pvp": pvp}
        self.accept()

    def get_data(self) -> dict:
        return self._data or {}
