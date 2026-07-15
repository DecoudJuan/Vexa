from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QTableWidgetItem,
    QLineEdit, QLabel, QDialog, QMessageBox, QHeaderView,
    QFileDialog,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator, QColor, QBrush

from ui.icons import svg_pixmap
from ui.base_page import ListPage
from ui.modal import BaseModal
from ui.import_dialog import ImportDialog
from utils.helpers import leer_tema, fmt_ar, parse_float

_SEARCH_MAXW, _ROW_H = 400, 40
_COD_W = 110
_TALLE_W = 80


class ConceptosWidget(ListPage):
    TITULO = "Productos"
    SUBTITULO = "Catálogo de productos y servicios"
    SEARCH_PLACEHOLDER = "Buscar por código o nombre..."
    SEARCH_MAXW = _SEARCH_MAXW
    COLUMNS = ["Código", "Talle", "Nombre", "Precio"]
    ROW_H = _ROW_H
    _order = "nombre"   # 'nombre' | 'codigo' (clic en el encabezado)

    def _header_buttons(self) -> list:
        self._btn_importar = self._boton("  Importar lista de precios", "file-plus",
                                         "text", "btn_secondary", self._on_importar, size=15)
        self._btn_nuevo = self._boton("  Nuevo producto", "plus", "accent_text",
                                      slot=self._on_nuevo, size=15)
        return [self._btn_importar, self._btn_nuevo]

    def _action_widgets(self) -> list:
        self._btn_edit = self._boton("  Editar", "edit", "text", "btn_secondary",
                                     self._on_editar, needs_selection=True)
        self._btn_del = self._boton("  Eliminar", "trash", "danger", "btn_danger",
                                    self._on_eliminar, needs_selection=True)
        return [self._btn_edit, self._btn_del]

    def _configure_columns(self, hh) -> None:
        # Código y Talle = ancho fijo; Nombre = se estira; Precio = ancho fijo
        # pegado al borde derecho.
        hh.setSectionResizeMode(0, QHeaderView.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.Interactive)
        self._resize_columns(hh)
        # Clic en Código/Nombre reordena (re-consultamos la base en vez del sort
        # nativo, que se pelea con los cell-widgets de las filas "sin precio").
        hh.setSectionsClickable(True)
        hh.sectionClicked.connect(self._on_header_clicked)
        precio_head = self._table.horizontalHeaderItem(3)
        if precio_head is not None:
            precio_head.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def _resize_columns(self, hh) -> None:
        self._table.setColumnWidth(0, round(_COD_W * self._zoom))
        self._table.setColumnWidth(1, round(_TALLE_W * self._zoom))
        self._table.setColumnWidth(3, round(150 * self._zoom))

    def _query(self, search):
        return self.db.get_productos(search, order=self._order)

    def _on_header_clicked(self, index: int) -> None:
        # Solo Código (0) y Nombre (2) reordenan; Talle (1) y Precio (3) no.
        if index not in (0, 2):
            return
        nuevo = "codigo" if index == 0 else "nombre"
        if nuevo != self._order:
            self._order = nuevo
            self.refresh()

    def _pre_render(self, items) -> None:
        self._sin_precio = 0

    def _fill_row(self, row: int, c: dict) -> None:
        self._table.setItem(row, 0, self._cell(
            (c.get("codigo") or "").strip() or "—", Qt.AlignCenter))
        talles = c.get("talles") or []
        self._table.setItem(row, 1, self._cell(
            ", ".join(talles) if talles else "—", Qt.AlignCenter))
        pvp = c.get("pvp") or 0
        if pvp <= 0:
            self._sin_precio += 1
            self._table.setItem(row, 2, QTableWidgetItem(""))
            self._table.setCellWidget(row, 2, self._nombre_sin_precio(c["nombre"]))
            price = self._cell(fmt_ar(0), Qt.AlignRight | Qt.AlignVCenter)
            price.setForeground(QBrush(QColor(self._pal["warn"])))
            self._table.setItem(row, 3, price)
        else:
            self._table.setItem(row, 2, QTableWidgetItem(c["nombre"]))
            # Si los talles tienen precios distintos, mostrar "desde …".
            texto = fmt_ar(pvp)
            if (c.get("pvp_min") or 0) not in (0, pvp):
                texto = f"desde {fmt_ar(c['pvp_min'])}"
            self._table.setItem(row, 3, self._cell(texto, Qt.AlignRight | Qt.AlignVCenter))

    def _count_text(self, total: int) -> str:
        pl = "s" if total != 1 else ""
        extra = f" · {self._sin_precio} sin precio" if self._sin_precio else ""
        return f"{total} producto{pl}{extra}"

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

    def _on_nuevo(self) -> None:
        dlg = ProductoDialog(zoom=self._zoom, theme=leer_tema(self.db), parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.db.save_producto(dlg.get_data())
            self.refresh()

    def _on_editar(self) -> None:
        p = self._selected()
        if not p:
            return
        dlg = ProductoDialog(producto=p, zoom=self._zoom, theme=leer_tema(self.db), parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.db.save_producto(dlg.get_data(), orig_nombre=p["nombre"],
                                  orig_codigo=p.get("codigo"))
            self.refresh()

    def _on_eliminar(self) -> None:
        p = self._selected()
        if not p:
            return
        talles = p.get("talles") or []
        extra = f" y sus {len(talles)} talles" if talles else ""
        if self._confirmar(f"¿Eliminar el producto <b>{p['nombre']}</b>{extra}?"):
            self.db.delete_producto(p["nombre"], p.get("codigo"))
            self.refresh()

    def _on_importar(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar lista de precios", "", "Planillas (*.xlsx *.xlsm *.csv)"
        )
        if not path:
            return
        dlg = ImportDialog(self.db, path, parent=self)
        if dlg.exec() == QDialog.Accepted and dlg.resumen:
            QMessageBox.information(
                self, "Importación completa",
                f"{dlg.resumen['creados']} productos nuevos, "
                f"{dlg.resumen['actualizados']} con precio actualizado.",
            )
            self.refresh()


class ProductoDialog(BaseModal):
    """Alta/edición de un producto y sus talles. El producto aparece una sola
    vez; los talles se cargan separados por coma y cada uno es una variante
    (comparten nombre, código y precio)."""

    def __init__(self, producto: dict | None = None, zoom: float = 1.0,
                 theme: str = "dark", parent=None):
        self._producto = producto
        self._data: dict | None = None
        titulo = "Editar producto" if producto else "Nuevo producto"
        sub = "Modificá los datos del producto" if producto else "Cargá un producto al catálogo"
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

        self.content.addWidget(self.section_label("TALLES", "layers"))
        self._talles = QLineEdit()
        self._talles.setObjectName("field")
        self._talles.setPlaceholderText("Separados por coma. Ej. 1, 2, 3, 4 (vacío = sin talle)")
        self.content.addWidget(self._talles)

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
        hint = QLabel("El precio se aplica a todos los talles del producto.")
        hint.setObjectName("hint")
        self.content.addWidget(hint)
        self.content.addStretch()

        self.set_primary_action("Guardar", self._accept)

        if producto:
            self._nombre.setText(producto.get("nombre", ""))
            self._codigo.setText((producto.get("codigo") or "").strip())
            self._talles.setText(", ".join(producto.get("talles") or []))
            self._pvp.setText(f"{float(producto.get('pvp') or 0):.2f}")

    def _accept(self) -> None:
        nombre = self._nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Campo requerido", "El nombre es obligatorio.")
            return
        pvp = parse_float(self._pvp.text())
        if pvp <= 0:
            QMessageBox.warning(self, "Falta el precio",
                                "El precio debe ser mayor que 0. Un producto no puede quedar sin precio.")
            self._pvp.setFocus()
            return
        talles = [t.strip() for t in self._talles.text().split(",") if t.strip()]
        self._data = {"nombre": nombre, "codigo": self._codigo.text().strip(),
                      "talles": talles, "pvp": pvp}
        self.accept()

    def get_data(self) -> dict:
        return self._data or {}
