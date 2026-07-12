import sqlite3

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLineEdit, QPushButton, QLabel, QDialog, QComboBox, QTextEdit,
    QMessageBox, QHeaderView, QFrame, QAbstractItemView,
    QListWidget, QListWidgetItem, QSizePolicy, QCompleter,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QDoubleValidator, QColor, QBrush

from ui.icons import svg_icon, svg_pixmap
from ui.styles import get_palette
from ui.base_page import ListPage
from ui.modal import BaseModal, modal_colors
from ui.widgets import avatar, celda, NoScrollComboBox
from utils.helpers import leer_zoom, leer_tema, valor_valido, fmt_ar, parse_float, PROVINCIAS_AR

_SEARCH_MAXW, _ROW_H = 400, 44
_HEADER_DEFAULT, _HEADER_MIN = 150, 80


class CuitListEditor(QWidget):
    """CUIT/CUIL de un cliente (puede tener varios). Input simple para
    agregar + una tabla compacta donde cada CUIT es una fila con su [x]."""

    _ROW_H = 32

    def __init__(self, theme: str = "dark", parent=None):
        super().__init__(parent)
        self._c = modal_colors(theme)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # --- input simple para agregar ---
        add_row = QHBoxLayout()
        add_row.setSpacing(6)
        self._input = QLineEdit()
        self._input.setObjectName("field")
        self._input.setPlaceholderText("Agregá un CUIT/CUIL y Enter…")
        self._input.returnPressed.connect(self._on_add)
        btn_add = QPushButton()
        btn_add.setObjectName("btn_secondary")
        btn_add.setIcon(svg_icon("plus", 14, self._c["focus"]))
        btn_add.setFixedWidth(44)
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.clicked.connect(self._on_add)
        add_row.addWidget(self._input, 1)
        add_row.addWidget(btn_add)
        layout.addLayout(add_row)

        # --- tabla compacta (una fila por CUIT) ---
        self._table = QTableWidget(0, 2)
        self._table.horizontalHeader().setVisible(False)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setSelectionMode(QAbstractItemView.NoSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setFocusPolicy(Qt.NoFocus)
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Fixed)
        self._table.setColumnWidth(1, 34)
        layout.addWidget(self._table)
        self._update_height()

    def _on_add(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self._add_row(text)
        self._input.clear()
        self._input.setFocus()

    def _add_row(self, cuit: str) -> None:
        r = self._table.rowCount()
        self._table.insertRow(r)
        item = QTableWidgetItem(cuit)
        item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._table.setItem(r, 0, item)
        btn = QPushButton()
        btn.setObjectName("btn_row_delete")
        btn.setIcon(svg_icon("x", 12, self._c["muted"]))
        btn.setIconSize(QSize(12, 12))
        btn.setFixedSize(22, 22)
        btn.setCursor(Qt.PointingHandCursor)
        # buscamos la fila por el item (row(item) sigue a la fila aunque se
        # muevan/borren otras), no por el botón.
        btn.clicked.connect(lambda _=None, it=item: self._remove_item(it))
        wrap = QWidget()
        wrap.setStyleSheet("background: transparent;")
        wl = QHBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(0)
        wl.addStretch()
        wl.addWidget(btn)
        wl.addStretch()
        self._table.setCellWidget(r, 1, wrap)
        self._table.setRowHeight(r, self._ROW_H)
        self._update_height()

    def _remove_item(self, item) -> None:
        r = self._table.row(item)
        if r >= 0:
            self._table.removeRow(r)
        self._update_height()

    def _update_height(self) -> None:
        rows = self._table.rowCount()
        if rows == 0:
            self._table.setVisible(False)
            return
        self._table.setVisible(True)
        visibles = min(rows, 4)
        self._table.setFixedHeight(visibles * self._ROW_H + 2)

    def set_cuits(self, cuits: list[str]) -> None:
        self._table.setRowCount(0)
        for cuit in cuits:
            self._add_row(cuit)
        self._update_height()

    def get_cuits(self) -> list[str]:
        out = []
        for i in range(self._table.rowCount()):
            item = self._table.item(i, 0)
            text = item.text().strip() if item else ""
            if text:
                out.append(text)
        return out


class ClientesWidget(ListPage):
    TITULO = "Clientes"
    SUBTITULO = "Alta, edición y datos fiscales de clientes"
    SEARCH_PLACEHOLDER = "Buscar por nombre, NIF o email..."
    SEARCH_MAXW = _SEARCH_MAXW
    COLUMNS = ["Cliente", "CUIT", "Localidad", "Teléfono", "Bonif.", "Saldo"]
    ROW_H = _ROW_H

    def _header_buttons(self) -> list:
        self._btn_nuevo = self._boton("  Nuevo cliente", "plus", "accent_text",
                                      slot=self._on_nuevo, size=15)
        return [self._btn_nuevo]

    def _action_widgets(self) -> list:
        self._btn_edit = self._boton("  Editar", "edit", "text", "btn_secondary",
                                     self._on_editar, needs_selection=True)
        self._btn_del = self._boton("  Eliminar", "trash", "danger", "btn_danger",
                                    self._on_eliminar, needs_selection=True)
        return [self._btn_edit, self._btn_del]

    def _configure_columns(self, hh) -> None:
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 6):
            hh.setSectionResizeMode(col, QHeaderView.Interactive)
        self._resize_columns(hh)

    def _resize_columns(self, hh) -> None:
        hh.setDefaultSectionSize(round(_HEADER_DEFAULT * self._zoom))
        hh.setMinimumSectionSize(round(_HEADER_MIN * self._zoom))

    def _query(self, search):
        return self.db.get_all_clientes(search)

    def _pre_render(self, items) -> None:
        self._saldos = self.db.get_saldos_clientes()
        self._con_saldo = 0

    @staticmethod
    def _initials(nombre: str) -> str:
        parts = [p for p in (nombre or "").split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[1][0]).upper()

    def _cliente_cell(self, c: dict) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        h = QHBoxLayout(w)
        h.setContentsMargins(12, 4, 8, 4)
        h.setSpacing(10)
        av = avatar(self._initials(c["nombre"]), self._pal["accent"],
                    self._pal["accent_text"], round(32 * self._zoom))
        h.addWidget(av)
        box = QVBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)
        name = QLabel(c["nombre"])
        name.setStyleSheet(f"color:{self._pal['text']}; font-weight:600; background:transparent;")
        box.addWidget(name)
        sub_txt = c.get("persona_contacto") or c.get("localidad") or ""
        if sub_txt:
            sub = QLabel(sub_txt)
            sub.setStyleSheet(f"color:{self._pal['muted1']}; font-size:11px; background:transparent;")
            box.addWidget(sub)
        h.addLayout(box)
        h.addStretch()
        return w

    def _fill_row(self, row: int, c: dict) -> None:
        self._table.setItem(row, 0, QTableWidgetItem(""))
        self._table.setCellWidget(row, 0, self._cliente_cell(c))
        self._table.setItem(row, 1, self._cell(valor_valido(c.get("nif")) or "—"))
        self._table.setItem(row, 2, self._cell(c.get("localidad") or "—"))
        self._table.setItem(row, 3, self._cell(c.get("telefono1") or "—"))
        bonificacion = c.get("bonificacion") or 0
        self._table.setItem(row, 4, self._cell(
            f"{bonificacion:.1f} %" if bonificacion else "—", Qt.AlignRight | Qt.AlignVCenter
        ))
        saldo = self._saldos.get(c.get("id"), 0) or 0
        if saldo > 0.005:
            item = self._cell(fmt_ar(saldo), Qt.AlignRight | Qt.AlignVCenter)
            item.setForeground(QBrush(QColor(self._pal["warn"])))
            self._table.setItem(row, 5, item)
            self._con_saldo += 1
        else:
            self._table.setItem(row, 5, self._cell("—", Qt.AlignRight | Qt.AlignVCenter))

    def _count_text(self, total: int) -> str:
        pl = "s" if total != 1 else ""
        extra = f" · {self._con_saldo} con saldo" if self._con_saldo else ""
        return f"{total} cliente{pl}{extra}"

    def _on_nuevo(self) -> None:
        dlg = ClienteDialog(self.db, parent=self)
        if dlg.exec() == QDialog.Accepted:
            cliente_id = self.db.create_cliente(dlg.get_data())
            self.db.set_cuits_cliente(cliente_id, dlg.get_cuits())
            self.refresh()

    def _on_editar(self) -> None:
        c = self._selected()
        if not c:
            return
        dlg = ClienteDialog(self.db, cliente=c, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.db.update_cliente(c["id"], dlg.get_data())
            self.db.set_cuits_cliente(c["id"], dlg.get_cuits())
            self.refresh()

    def _on_eliminar(self) -> None:
        c = self._selected()
        if not c:
            return
        if self._confirmar(
            f"¿Eliminar al cliente <b>{c['nombre']}</b>?<br><br>Esta acción no se puede deshacer."
        ):
            try:
                self.db.delete_cliente(c["id"])
                self.refresh()
            except sqlite3.IntegrityError:
                QMessageBox.critical(
                    self, "No se puede eliminar",
                    f"El cliente <b>{c['nombre']}</b> tiene documentos asociados.<br>"
                    "Eliminá o reasigná esos documentos primero.",
                )


class ClienteDialog(BaseModal):
    def __init__(self, db, cliente: dict | None = None, parent=None):
        self.db = db
        self._cliente = cliente
        self._data: dict | None = None
        self._pal = get_palette(leer_tema(db))
        self._theme_str = leer_tema(db)
        titulo = "Editar cliente" if cliente else "Nuevo cliente"
        sub = "Modificá los datos del cliente" if cliente else "Cargá un cliente nuevo"
        super().__init__(titulo, sub, icon="user", width=620, scroll=True,
                         height=760, zoom=leer_zoom(db), theme=self._theme_str, parent=parent)

        self._build_form()
        self.set_primary_action("Guardar cambios" if cliente else "Crear cliente", self._accept)
        if cliente:
            self._populate(cliente)

    def _labeled(self, text: str, widget) -> QVBoxLayout:
        box = QVBoxLayout()
        box.setSpacing(self._S(5))
        lbl = QLabel(text)
        lbl.setObjectName("section_label")
        box.addWidget(lbl)
        box.addWidget(widget)
        return box

    def _row2(self, left, right) -> QHBoxLayout:
        r = QHBoxLayout()
        r.setSpacing(self._S(14))
        r.addLayout(left, 1)
        r.addLayout(right, 1)
        return r

    def _build_form(self) -> None:
        c = self.content

        self._nombre = QLineEdit()
        self._nombre.setObjectName("field")
        self._nombre.setPlaceholderText("Razón social / nombre")
        c.addLayout(self._labeled("NOMBRE *", self._nombre))

        self._cuits = CuitListEditor(theme=self._theme_str)
        c.addLayout(self._labeled("CUIT / CUIL", self._cuits))

        self._direccion = QLineEdit()
        self._direccion.setObjectName("field")
        c.addLayout(self._labeled("DIRECCIÓN", self._direccion))

        self._cp = QLineEdit()
        self._cp.setObjectName("field")
        self._localidad = QLineEdit()
        self._localidad.setObjectName("field")
        c.addLayout(self._row2(self._labeled("C.P.", self._cp),
                               self._labeled("LOCALIDAD", self._localidad)))

        self._provincia = NoScrollComboBox()
        self._provincia.setObjectName("field")
        self._provincia.setEditable(True)
        self._provincia.setInsertPolicy(QComboBox.NoInsert)
        self._provincia.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self._provincia.addItem("")
        for prov in PROVINCIAS_AR:
            self._provincia.addItem(prov)
        self._provincia.setCurrentIndex(0)
        self._provincia.lineEdit().setPlaceholderText("Elegí o escribí la provincia...")
        prov_comp = QCompleter(PROVINCIAS_AR)
        prov_comp.setCaseSensitivity(Qt.CaseInsensitive)
        prov_comp.setFilterMode(Qt.MatchContains)
        self._provincia.setCompleter(prov_comp)
        c.addLayout(self._labeled("PROVINCIA", self._provincia))

        self._telefono1 = QLineEdit()
        self._telefono1.setObjectName("field")
        self._fax = QLineEdit()
        self._fax.setObjectName("field")
        c.addLayout(self._row2(self._labeled("TELÉFONO", self._telefono1),
                               self._labeled("FAX", self._fax)))

        self._email = QLineEdit()
        self._email.setObjectName("field")
        self._persona_contacto = QLineEdit()
        self._persona_contacto.setObjectName("field")
        c.addLayout(self._row2(self._labeled("EMAIL", self._email),
                               self._labeled("CONTACTO", self._persona_contacto)))

        self._forma_pago = NoScrollComboBox()
        self._forma_pago.setObjectName("field")
        self._forma_pago.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self._forma_pago.addItem("(sin definir)", None)
        for fp in self.db.get_all_forma_pago():
            self._forma_pago.addItem(fp["tipo"], fp["id"])

        self._bonificacion = QLineEdit()
        self._bonificacion.setObjectName("field")
        self._bonificacion.setPlaceholderText("0,00")
        self._bonificacion.setValidator(QDoubleValidator(0.0, 100.0, 2))
        bon_box = QWidget()
        bh = QHBoxLayout(bon_box)
        bh.setContentsMargins(0, 0, 0, 0)
        bh.setSpacing(self._S(8))
        bh.addWidget(self._bonificacion, 1)
        u = QLabel("%")
        u.setObjectName("unit")
        bh.addWidget(u)
        c.addLayout(self._row2(self._labeled("FORMA DE PAGO", self._forma_pago),
                               self._labeled("BONIFICACIÓN", bon_box)))

        self._banco = QLineEdit()
        self._banco.setObjectName("field")
        c.addLayout(self._labeled("BANCO", self._banco))

        self._comentarios = QTextEdit()
        self._comentarios.setObjectName("comments")
        self._comentarios.setFixedHeight(self._S(72))
        c.addLayout(self._labeled("COMENTARIOS", self._comentarios))
        c.addStretch()

    def _populate(self, c: dict) -> None:
        self._nombre.setText(c.get("nombre", ""))
        cuits = self.db.get_cuits_cliente(c["id"]) if c.get("id") else []
        if not cuits and c.get("nif"):
            cuits = [c["nif"]]
        cuits = [x for x in cuits if valor_valido(x)]
        self._cuits.set_cuits(cuits)
        self._direccion.setText(c.get("direccion") or "")
        self._cp.setText(valor_valido(c.get("cp")) or "")
        self._localidad.setText(c.get("localidad") or "")
        self._provincia.setCurrentText(c.get("provincia") or "")
        self._telefono1.setText(c.get("telefono1") or "")
        self._fax.setText(c.get("fax") or "")
        self._email.setText(c.get("email") or "")
        self._persona_contacto.setText(c.get("persona_contacto") or "")
        idx = self._forma_pago.findData(c.get("forma_pago_id"))
        self._forma_pago.setCurrentIndex(max(idx, 0))
        self._banco.setText(c.get("banco") or "")
        bonif = float(c.get("bonificacion") or 0)
        self._bonificacion.setText(f"{bonif:g}" if bonif else "")
        self._comentarios.setPlainText(c.get("comentarios") or "")

    def _accept(self) -> None:
        nombre = self._nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Campo requerido", "El nombre del cliente es obligatorio.")
            self._nombre.setFocus()
            return

        cuits = self._cuits.get_cuits()
        self._cuits_a_guardar = cuits

        self._data = {
            "nombre": nombre,
            "nif": cuits[0] if cuits else None,
            "direccion": self._direccion.text().strip() or None,
            "cp": self._cp.text().strip() or None,
            "localidad": self._localidad.text().strip() or None,
            "provincia": self._provincia.currentText().strip() or None,
            "telefono1": self._telefono1.text().strip() or None,
            "fax": self._fax.text().strip() or None,
            "email": self._email.text().strip() or None,
            "persona_contacto": self._persona_contacto.text().strip() or None,
            "forma_pago_id": self._forma_pago.currentData(),
            "banco": self._banco.text().strip() or None,
            "ccc1": None, "ccc2": None, "ccc3": None, "ccc4": None,
            # Retención / recargo de equivalencia ya no se editan desde la UI
            # (ver Documentos), pero se preservan tal cual si el cliente ya
            # tenía valores históricos cargados.
            "retencion": self._cliente.get("retencion") if self._cliente else None,
            "recargo_equiv": self._cliente.get("recargo_equiv") if self._cliente else None,
            "bonificacion": parse_float(self._bonificacion.text()),
            "comentarios": self._comentarios.toPlainText().strip() or None,
        }
        self.accept()

    def get_data(self) -> dict:
        return self._data or {}

    def get_cuits(self) -> list[str]:
        return getattr(self, "_cuits_a_guardar", [])
