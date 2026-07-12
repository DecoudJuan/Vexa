from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QFormLayout, QLineEdit,
    QPushButton, QLabel, QCheckBox, QFileDialog, QFrame, QScrollArea,
    QSizePolicy, QMessageBox, QComboBox, QCompleter,
)
from PySide6.QtCore import Qt

from ui.icons import svg_icon
from ui.styles import get_palette
from ui.widgets import fila as _fila, NoScrollComboBox
from utils.helpers import (
    leer_tema, valor_valido, set_moneda, CONDICIONES_IVA, MONEDAS, PROVINCIAS_AR,
    formatear_cuit, formatear_telefono,
)


class ConfiguracionWidget(QWidget):
    """Configuración de la empresa, separada en tres solapas (Datos de la
    empresa / Guardado / AFIP opcional) con un único botón Guardar."""

    def __init__(self, db, parent=None, on_empresa_changed=None):
        super().__init__(parent)
        self.db = db
        self._on_empresa_changed = on_empresa_changed
        self._pal = get_palette(leer_tema(db))
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------ armado
    def _scroll_form(self):
        """Devuelve (scroll_widget, form_layout) con scroll vertical."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        scroll.setWidget(content)
        v = QVBoxLayout(content)
        v.setContentsMargins(28, 22, 28, 22)
        v.setSpacing(14)
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        v.addLayout(form)
        v.addStretch()
        return scroll, form

    def _combo(self, items_o_pares, con_data=False) -> NoScrollComboBox:
        combo = NoScrollComboBox()
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if con_data:
            for etiqueta, valor in items_o_pares:
                combo.addItem(etiqueta, valor)
        else:
            combo.addItems(items_o_pares)
        return combo

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.addTab(self._tab_empresa(), "Datos de la empresa")
        self._tabs.addTab(self._tab_guardado(), "Guardado")
        self._tabs.addTab(self._tab_afip(), "AFIP (opcional)")
        outer.addWidget(self._tabs, 1)

        sep = QFrame()
        sep.setObjectName("sidebar_sep")
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        outer.addWidget(sep)

        bar = QHBoxLayout()
        bar.setContentsMargins(28, 12, 28, 14)
        bar.addStretch()
        self._btn_guardar = QPushButton("  Guardar")
        self._btn_guardar.setIcon(svg_icon("check", 14, self._pal["accent_text"]))
        self._btn_guardar.setCursor(Qt.PointingHandCursor)
        self._btn_guardar.clicked.connect(self._on_guardar)
        bar.addWidget(self._btn_guardar)
        outer.addLayout(bar)

    def _tab_empresa(self) -> QWidget:
        scroll, f = self._scroll_form()
        self._nombre = QLineEdit()
        self._nif = QLineEdit()
        self._nif.textEdited.connect(lambda: self._reformatear(self._nif, formatear_cuit))
        self._condicion_iva = self._combo([""] + CONDICIONES_IVA)
        self._direccion = QLineEdit()
        self._cp = QLineEdit()
        self._localidad = QLineEdit()
        self._provincia = self._provincia_combo()
        self._telefono = QLineEdit()
        self._telefono.textEdited.connect(lambda: self._reformatear(self._telefono, formatear_telefono))
        self._email = QLineEdit()
        self._web = QLineEdit()
        self._moneda = self._combo(MONEDAS, con_data=True)

        f.addRow("Nombre / razón social", self._nombre)
        f.addRow("CUIT", self._nif)
        f.addRow("Condición frente al IVA", self._condicion_iva)
        f.addRow("Dirección", self._direccion)
        f.addRow("C.P.", self._cp)
        f.addRow("Localidad", self._localidad)
        f.addRow("Provincia", self._provincia)
        f.addRow("Teléfono", self._telefono)
        f.addRow("Email", self._email)
        f.addRow("Web", self._web)
        f.addRow("Moneda", self._moneda)
        return scroll

    def _tab_guardado(self) -> QWidget:
        scroll, f = self._scroll_form()
        self._logo_path = QLineEdit()
        self._logo_path.setPlaceholderText("Ruta al logo (opcional)")
        btn_logo = QPushButton("Elegir…")
        btn_logo.setObjectName("btn_secondary")
        btn_logo.clicked.connect(self._on_elegir_logo)
        f.addRow("Logo", _fila(self._logo_path, btn_logo))

        self._pdf_dir = QLineEdit()
        self._pdf_dir.setPlaceholderText("Por defecto: Documentos\\Facturacion\\pdf")
        btn_pdf = QPushButton("Elegir carpeta…")
        btn_pdf.setObjectName("btn_secondary")
        btn_pdf.clicked.connect(self._on_elegir_carpeta_pdf)
        btn_reset = QPushButton("Usar por defecto")
        btn_reset.setObjectName("btn_secondary")
        btn_reset.clicked.connect(lambda: self._pdf_dir.setText(""))
        f.addRow("Carpeta para guardar PDF", _fila(self._pdf_dir, btn_pdf, btn_reset))

        self._sufijo = QLineEdit()
        self._pie_pagina = QLineEdit()
        f.addRow("Sufijo numeración", self._sufijo)
        f.addRow("Pie de página (PDF)", self._pie_pagina)
        return scroll

    def _tab_afip(self) -> QWidget:
        scroll, f = self._scroll_form()
        nota = QLabel("Opcional. Completá estos datos solo si vas a emitir "
                      "comprobantes electrónicos con AFIP (Fase 4).")
        nota.setProperty("role", "page-subtitle")
        nota.setWordWrap(True)
        f.addRow(nota)
        self._afip = QCheckBox("Habilitar facturación electrónica AFIP")
        f.addRow("", self._afip)
        self._punto_venta = QLineEdit()
        self._punto_venta.setPlaceholderText("Ej. 0001")
        self._ingresos_brutos = QLineEdit()
        self._inicio_actividades = QLineEdit()
        f.addRow("Punto de venta", self._punto_venta)
        f.addRow("Ingresos Brutos", self._ingresos_brutos)
        f.addRow("Inicio de actividades", self._inicio_actividades)
        return scroll

    # ------------------------------------------------------------ helpers
    def _reformatear(self, line: QLineEdit, fmt) -> None:
        line.setText(fmt(line.text()))
        line.setCursorPosition(len(line.text()))

    def _provincia_combo(self) -> NoScrollComboBox:
        combo = NoScrollComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        combo.addItem("")
        for prov in PROVINCIAS_AR:
            combo.addItem(prov)
        combo.setCurrentIndex(0)
        comp = QCompleter(PROVINCIAS_AR)
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        comp.setFilterMode(Qt.MatchContains)
        comp.setCompletionMode(QCompleter.PopupCompletion)
        combo.setCompleter(comp)
        return combo

    # ------------------------------------------------------------ datos
    def refresh(self) -> None:
        e = self.db.get_datos_empresa()
        self._nombre.setText(e.get("nombre") or "")
        self._nif.setText(valor_valido(e.get("nif")) or "")
        self._condicion_iva.setCurrentText(e.get("condicion_iva") or "")
        self._direccion.setText(e.get("direccion") or "")
        self._cp.setText(valor_valido(e.get("cp")) or "")
        self._localidad.setText(e.get("localidad") or "")
        self._provincia.setCurrentText(e.get("provincia") or "")
        self._telefono.setText(e.get("telefono") or "")
        self._email.setText(e.get("email") or "")
        self._web.setText(e.get("web") or "")
        idx = self._moneda.findData(e.get("moneda") or "$")
        self._moneda.setCurrentIndex(idx if idx >= 0 else 0)
        self._logo_path.setText(e.get("logo_path") or "")
        self._pdf_dir.setText(self.db.get_config("pdf_dir") or "")
        self._sufijo.setText(e.get("sufijo") or "")
        self._pie_pagina.setText(e.get("pie_pagina") or "")
        self._afip.setChecked(bool(e.get("afip_habilitado")))
        self._punto_venta.setText(e.get("punto_venta") or "")
        self._ingresos_brutos.setText(e.get("ingresos_brutos") or "")
        self._inicio_actividades.setText(e.get("inicio_actividades") or "")

    def set_theme_zoom(self, theme: str, zoom: float) -> None:
        self._pal = get_palette(theme)
        self._btn_guardar.setIcon(svg_icon("check", 14, self._pal["accent_text"]))

    def _on_elegir_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Elegir logo", "",
                                              "Imágenes (*.png *.jpg *.jpeg)")
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
            "provincia": self._provincia.currentText().strip() or None,
            "telefono": self._telefono.text().strip() or None,
            "fax": None,
            "email": self._email.text().strip() or None,
            "web": self._web.text().strip() or None,
            "iva_defecto": 21.0,
            "iva_texto": "IVA",
            "moneda": self._moneda.currentData() or "$",
            "sufijo": self._sufijo.text().strip() or None,
            "pie_pagina": self._pie_pagina.text().strip() or None,
            "logo_path": self._logo_path.text().strip() or None,
            "ccc1": None, "ccc2": None, "ccc3": None, "ccc4": None,
            "ccce1": None, "ccce2": None,
            "condicion_iva": self._condicion_iva.currentText().strip() or None,
            "ingresos_brutos": self._ingresos_brutos.text().strip() or None,
            "inicio_actividades": self._inicio_actividades.text().strip() or None,
            "punto_venta": self._punto_venta.text().strip() or None,
            "afip_habilitado": 1 if self._afip.isChecked() else 0,
        })
        set_moneda(self._moneda.currentData() or "$")
        if self._on_empresa_changed:
            self._on_empresa_changed()
        QMessageBox.information(self, "Guardado", "Datos guardados correctamente.")
