from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QFormLayout, QLineEdit,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QDialog, QCheckBox, QMessageBox,
    QFileDialog, QFrame, QScrollArea,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator, QIntValidator

from ui.icons import svg_icon
from ui.styles import get_palette
from ui.modal import BaseModal
from ui.widgets import fila as _fila
from utils.helpers import leer_tema, valor_valido, parse_float, set_moneda


class ConfiguracionWidget(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._empresa = EmpresaTab(db, parent=self)
        self._iva = IvaTab(db, parent=self)
        self._forma_pago = FormaPagoTab(db, parent=self)
        self._tabs.addTab(self._empresa, "Mi empresa")
        self._tabs.addTab(self._iva, "IVA")
        self._tabs.addTab(self._forma_pago, "Formas de pago")
        layout.addWidget(self._tabs)

    def refresh(self) -> None:
        self._empresa.refresh()
        self._iva.refresh()
        self._forma_pago.refresh()

    def set_theme_zoom(self, theme: str, zoom: float) -> None:
        self._empresa.set_theme_zoom(theme, zoom)
        self._iva.set_theme_zoom(theme, zoom)
        self._forma_pago.set_theme_zoom(theme, zoom)


class EmpresaTab(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._pal = get_palette(leer_tema(db))

        # A zoom alto (o ventana chica) las 14 filas del formulario más el
        # logo/carpeta PDF no entran en el alto disponible; sin scroll, Qt
        # comprimía las filas por debajo de su tamaño mínimo y los bordes
        # de los inputs quedaban superpuestos. El scroll garantiza que cada
        # fila siempre respete su alto natural.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        h = QLabel("Datos de la empresa")
        h.setProperty("role", "page-title")
        layout.addWidget(h)

        f = QFormLayout()
        f.setSpacing(10)
        f.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        f.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self._nombre = QLineEdit()
        self._nif = QLineEdit()
        self._direccion = QLineEdit()
        self._cp = QLineEdit()
        self._localidad = QLineEdit()
        self._provincia = QLineEdit()
        self._telefono = QLineEdit()
        self._email = QLineEdit()
        self._web = QLineEdit()
        self._moneda = QLineEdit()
        self._sufijo = QLineEdit()
        self._pie_pagina = QLineEdit()

        f.addRow("Nombre / razón social", self._nombre)
        f.addRow("NIF/CUIT", self._nif)
        f.addRow("Dirección", self._direccion)
        f.addRow("C.P.", self._cp)
        f.addRow("Localidad", self._localidad)
        f.addRow("Provincia", self._provincia)
        f.addRow("Teléfono", self._telefono)
        f.addRow("Email", self._email)
        f.addRow("Web", self._web)
        f.addRow("Moneda", self._moneda)
        f.addRow("Sufijo numeración", self._sufijo)
        f.addRow("Pie de página (PDF)", self._pie_pagina)
        layout.addLayout(f)

        self._logo_path = QLineEdit()
        self._logo_path.setPlaceholderText("Ruta al logo (opcional, usa el logo por defecto si se deja vacío)")
        btn_logo = QPushButton("Elegir...")
        btn_logo.setObjectName("btn_secondary")
        btn_logo.clicked.connect(self._on_elegir_logo)
        f.addRow("Logo", _fila(self._logo_path, btn_logo))

        self._pdf_dir = QLineEdit()
        self._pdf_dir.setPlaceholderText("Por defecto: Documentos\\Facturacion\\pdf")
        btn_pdf_dir = QPushButton("Elegir carpeta...")
        btn_pdf_dir.setObjectName("btn_secondary")
        btn_pdf_dir.clicked.connect(self._on_elegir_carpeta_pdf)
        btn_pdf_dir_reset = QPushButton("Usar por defecto")
        btn_pdf_dir_reset.setObjectName("btn_secondary")
        btn_pdf_dir_reset.clicked.connect(lambda: self._pdf_dir.setText(""))
        f.addRow("Carpeta para guardar PDF", _fila(self._pdf_dir, btn_pdf_dir, btn_pdf_dir_reset))

        layout.addStretch()

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background: #313244; border: none; max-height: 1px;")
        layout.addWidget(sep)

        btns = QHBoxLayout()
        btns.addStretch()
        self._btn_guardar = QPushButton("  Guardar")
        self._btn_guardar.setIcon(svg_icon("check", 14, self._pal["accent_text"]))
        self._btn_guardar.setCursor(Qt.PointingHandCursor)
        self._btn_guardar.clicked.connect(self._on_guardar)
        btns.addWidget(self._btn_guardar)
        layout.addLayout(btns)

    def set_theme_zoom(self, theme: str, zoom: float) -> None:
        self._pal = get_palette(theme)
        self._btn_guardar.setIcon(svg_icon("check", 14, self._pal["accent_text"]))

    def refresh(self) -> None:
        e = self.db.get_datos_empresa()
        self._nombre.setText(e.get("nombre") or "")
        self._nif.setText(valor_valido(e.get("nif")) or "")
        self._direccion.setText(e.get("direccion") or "")
        self._cp.setText(valor_valido(e.get("cp")) or "")
        self._localidad.setText(e.get("localidad") or "")
        self._provincia.setText(e.get("provincia") or "")
        self._telefono.setText(e.get("telefono") or "")
        self._email.setText(e.get("email") or "")
        self._web.setText(e.get("web") or "")
        self._moneda.setText(e.get("moneda") or "$")
        self._sufijo.setText(e.get("sufijo") or "")
        self._pie_pagina.setText(e.get("pie_pagina") or "")
        self._logo_path.setText(e.get("logo_path") or "")
        self._pdf_dir.setText(self.db.get_config("pdf_dir") or "")

    def _on_elegir_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Elegir logo", "", "Imágenes (*.png *.jpg *.jpeg)")
        if path:
            self._logo_path.setText(path)

    def _on_elegir_carpeta_pdf(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Elegir carpeta para guardar los PDF")
        if path:
            self._pdf_dir.setText(path)

    def _on_guardar(self) -> None:
        self.db.set_config("pdf_dir", self._pdf_dir.text().strip())
        self.db.update_datos_empresa({
            "nombre": self._nombre.text().strip(),
            "nif": self._nif.text().strip() or None,
            "direccion": self._direccion.text().strip() or None,
            "cp": self._cp.text().strip() or None,
            "localidad": self._localidad.text().strip() or None,
            "provincia": self._provincia.text().strip() or None,
            "telefono": self._telefono.text().strip() or None,
            "fax": None,
            "email": self._email.text().strip() or None,
            "web": self._web.text().strip() or None,
            "iva_defecto": 21.0,
            "iva_texto": "IVA",
            "moneda": self._moneda.text().strip() or "$",
            "sufijo": self._sufijo.text().strip() or None,
            "pie_pagina": self._pie_pagina.text().strip() or None,
            "logo_path": self._logo_path.text().strip() or None,
            "ccc1": None, "ccc2": None, "ccc3": None, "ccc4": None,
            "ccce1": None, "ccce2": None,
        })
        # Actualizar la moneda global para que los importes se reformateen
        # (ej. cambiar de '$' a 'US$') sin reiniciar la app.
        set_moneda(self._moneda.text().strip() or "$")
        QMessageBox.information(self, "Guardado", "Datos de la empresa actualizados.")


class IvaTab(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._pal = get_palette(leer_tema(db))
        self._ivas: list[dict] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        header = QHBoxLayout()
        h = QLabel("Tasas de IVA")
        h.setProperty("role", "page-title")
        header.addWidget(h)
        header.addStretch()
        self._btn_nuevo = QPushButton("  Nueva tasa")
        self._btn_nuevo.setIcon(svg_icon("plus", 14, self._pal["accent_text"]))
        self._btn_nuevo.clicked.connect(self._on_nuevo)
        header.addWidget(self._btn_nuevo)
        layout.addLayout(header)

        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Tasa (%)", "Recargo equiv. (%)", "Activo"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        layout.addWidget(self._table)

        actions = QHBoxLayout()
        self._btn_del = QPushButton("  Eliminar")
        self._btn_del.setIcon(svg_icon("trash", 14, self._pal["danger"]))
        self._btn_del.setObjectName("btn_danger")
        self._btn_del.clicked.connect(self._on_eliminar)
        actions.addWidget(self._btn_del)
        actions.addStretch()
        layout.addLayout(actions)

    def set_theme_zoom(self, theme: str, zoom: float) -> None:
        self._pal = get_palette(theme)
        self._btn_nuevo.setIcon(svg_icon("plus", 14, self._pal["accent_text"]))
        self._btn_del.setIcon(svg_icon("trash", 14, self._pal["danger"]))

    def refresh(self) -> None:
        self._ivas = self.db.get_all_iva()
        self._table.setRowCount(len(self._ivas))
        for row, iva in enumerate(self._ivas):
            self._table.setItem(row, 0, QTableWidgetItem(f"{iva['tipo']:g}"))
            self._table.setItem(row, 1, QTableWidgetItem(f"{iva['recargo']:g}"))
            self._table.setItem(row, 2, QTableWidgetItem("Sí" if iva["activo"] else "No"))

    def _on_nuevo(self) -> None:
        dlg = IvaDialog(theme=leer_tema(self.db), parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.db.create_iva(dlg.get_data())
            self.refresh()

    def _on_eliminar(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._ivas):
            return
        self.db.delete_iva(self._ivas[row]["id"])
        self.refresh()


class IvaDialog(BaseModal):
    def __init__(self, theme: str = "dark", parent=None):
        self._data = None
        super().__init__("Nueva tasa de IVA", "Agregá una alícuota", icon="percent",
                         width=440, theme=theme, parent=parent)
        self.content.addWidget(self.section_label("TASA", "percent"))
        self._tipo = QLineEdit()
        self._tipo.setObjectName("field")
        self._tipo.setPlaceholderText("0,00")
        self._tipo.setValidator(QDoubleValidator(0.0, 100.0, 2))
        self.content.addLayout(self._pct_row(self._tipo))

        self.content.addWidget(self.section_label("RECARGO EQUIVALENCIA", "percent"))
        self._recargo = QLineEdit()
        self._recargo.setObjectName("field")
        self._recargo.setPlaceholderText("0,00")
        self._recargo.setValidator(QDoubleValidator(0.0, 100.0, 2))
        self.content.addLayout(self._pct_row(self._recargo))
        self.content.addStretch()

        self.set_primary_action("Guardar", self._accept)

    def _pct_row(self, field) -> QHBoxLayout:
        r = QHBoxLayout()
        r.setSpacing(self._S(8))
        r.addWidget(field, 1)
        u = QLabel("%")
        u.setObjectName("unit")
        r.addWidget(u)
        return r

    def _accept(self):
        self._data = {"tipo": parse_float(self._tipo.text()),
                      "recargo": parse_float(self._recargo.text()), "activo": 1}
        self.accept()

    def get_data(self):
        return self._data or {}


class FormaPagoTab(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._pal = get_palette(leer_tema(db))
        self._formas: list[dict] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        header = QHBoxLayout()
        h = QLabel("Formas de pago")
        h.setProperty("role", "page-title")
        header.addWidget(h)
        header.addStretch()
        self._btn_nuevo = QPushButton("  Nueva")
        self._btn_nuevo.setIcon(svg_icon("plus", 14, self._pal["accent_text"]))
        self._btn_nuevo.clicked.connect(self._on_nuevo)
        header.addWidget(self._btn_nuevo)
        layout.addLayout(header)

        self._table = QTableWidget()
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["Tipo", "Genera recibo"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(self._table)

        actions = QHBoxLayout()
        self._btn_del = QPushButton("  Eliminar")
        self._btn_del.setIcon(svg_icon("trash", 14, self._pal["danger"]))
        self._btn_del.setObjectName("btn_danger")
        self._btn_del.clicked.connect(self._on_eliminar)
        actions.addWidget(self._btn_del)
        actions.addStretch()
        layout.addLayout(actions)

    def set_theme_zoom(self, theme: str, zoom: float) -> None:
        self._pal = get_palette(theme)
        self._btn_nuevo.setIcon(svg_icon("plus", 14, self._pal["accent_text"]))
        self._btn_del.setIcon(svg_icon("trash", 14, self._pal["danger"]))

    def refresh(self) -> None:
        self._formas = self.db.get_all_forma_pago()
        self._table.setRowCount(len(self._formas))
        for row, fp in enumerate(self._formas):
            self._table.setItem(row, 0, QTableWidgetItem(fp["tipo"]))
            self._table.setItem(row, 1, QTableWidgetItem("Sí" if fp["genera_recibo"] else "No"))

    def _on_nuevo(self) -> None:
        dlg = FormaPagoDialog(theme=leer_tema(self.db), parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.db.create_forma_pago(dlg.get_data())
            self.refresh()

    def _on_eliminar(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._formas):
            return
        self.db.delete_forma_pago(self._formas[row]["id"])
        self.refresh()


class FormaPagoDialog(BaseModal):
    def __init__(self, theme: str = "dark", parent=None):
        self._data = None
        super().__init__("Nueva forma de pago", "Definí una forma de pago",
                         icon="credit-card", width=480, theme=theme, parent=parent)
        self.content.addWidget(self.section_label("NOMBRE *", "credit-card"))
        self._tipo = QLineEdit()
        self._tipo.setObjectName("field")
        self._tipo.setPlaceholderText("Ej.: Efectivo, Transferencia…")
        self.content.addWidget(self._tipo)

        self._genera_recibo = QCheckBox("Genera recibo")
        self.content.addWidget(self._genera_recibo)

        self.content.addWidget(self.section_label("NOTA DE VENCIMIENTO", "file-text"))
        self._vto1 = QLineEdit()
        self._vto1.setObjectName("field")
        self.content.addWidget(self._vto1)

        self.content.addWidget(self.section_label("DÍAS DE VENCIMIENTO", "calendar"))
        self._vto2 = QLineEdit()
        self._vto2.setObjectName("field")
        self._vto2.setPlaceholderText("0")
        self._vto2.setValidator(QIntValidator(0, 365))
        drow = QHBoxLayout()
        drow.setSpacing(self._S(8))
        drow.addWidget(self._vto2, 1)
        u = QLabel("días")
        u.setObjectName("unit")
        drow.addWidget(u)
        self.content.addLayout(drow)
        self.content.addStretch()

        self.set_primary_action("Guardar", self._accept)

    def _accept(self):
        nombre = self._tipo.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Campo requerido", "El nombre es obligatorio.")
            return
        try:
            dias = int(self._vto2.text() or 0)
        except ValueError:
            dias = 0
        self._data = {
            "tipo": nombre,
            "genera_recibo": 1 if self._genera_recibo.isChecked() else 0,
            "vto1": self._vto1.text().strip() or None,
            "vto2": dias,
            "vto3": 0,
        }
        self.accept()

    def get_data(self):
        return self._data or {}
