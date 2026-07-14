from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QTabWidget, QFormLayout,
    QLineEdit, QPushButton, QLabel, QCheckBox, QFileDialog, QFrame, QScrollArea,
    QSizePolicy, QMessageBox,
)
from PySide6.QtCore import Qt

from ui.icons import svg_icon, svg_pixmap
from ui.styles import get_palette
from ui.widgets import fila as _fila, NoScrollComboBox, provincia_combo
from utils.helpers import (
    leer_tema, leer_zoom, valor_valido, set_moneda, CONDICIONES_IVA, MONEDAS,
    formatear_cuit, TELEFONO_EJEMPLO, partir_direccion,
    unir_direccion,
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

    def _half(self, widget: QWidget) -> QWidget:
        """Envuelve un campo para que ocupe solo la mitad izquierda de la fila
        (útil para datos cortos como C.P., localidad o moneda)."""
        box = QWidget()
        h = QHBoxLayout(box)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(widget, 1)
        h.addStretch(1)
        return box

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
        self._btn_guardar.clicked.connect(lambda: self._on_guardar())
        bar.addWidget(self._btn_guardar)
        outer.addLayout(bar)

    def _tab_empresa(self) -> QWidget:
        scroll, v = self._scroll_vbox()
        self._nombre = QLineEdit()
        self._nif = QLineEdit()
        self._nif.textEdited.connect(lambda: self._reformatear(self._nif, formatear_cuit))
        self._condicion_iva = self._combo([""] + CONDICIONES_IVA)
        self._calle = QLineEdit()
        self._numero = QLineEdit()
        self._numero.setPlaceholderText("1234")
        self._cp = QLineEdit()
        self._localidad = QLineEdit()
        self._provincia = provincia_combo(expandir=True, placeholder=None)
        self._telefono = QLineEdit()
        self._telefono.setPlaceholderText(TELEFONO_EJEMPLO)
        self._email = QLineEdit()
        self._web = QLineEdit()
        self._web.setPlaceholderText("https://…")
        self._moneda = self._combo(MONEDAS, con_data=True)

        # Grilla de 4 columnas: full=4, mitad=2, cuarto=1.
        v.addWidget(self._section("file-invoice", "Datos de la empresa", [
            [("Nombre / razón social", self._nombre, 4)],
            [("CUIT", self._nif, 2), ("Condición frente al IVA", self._condicion_iva, 2)],
        ]))
        v.addWidget(self._section("package", "Dirección", [
            [("Calle", self._calle, 2), ("Número", self._numero, 1), ("C.P.", self._cp, 1)],
            [("Localidad", self._localidad, 2), ("Provincia", self._provincia, 2)],
        ]))
        v.addWidget(self._section("credit-card", "Contacto y configuración", [
            [("Teléfono", self._telefono, 2), ("Email", self._email, 2)],
            [("Sitio web", self._web, 2), ("Moneda", self._moneda, 2)],
        ]))
        v.addStretch()
        return scroll

    # ------------------------------------------------------------ secciones
    def _scroll_vbox(self):
        """(scroll, vbox) para armar una página con tarjetas de sección."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        scroll.setWidget(content)
        v = QVBoxLayout(content)
        v.setContentsMargins(28, 22, 28, 22)
        v.setSpacing(16)
        return scroll, v

    def _field(self, label: str, widget: QWidget) -> QWidget:
        """Campo con su etiqueta arriba (estilo formulario moderno)."""
        box = QWidget()
        box.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)
        lbl = QLabel(label)
        lbl.setProperty("role", "field-label")
        lay.addWidget(lbl)
        lay.addWidget(widget)
        return box

    def _section(self, icon: str, titulo: str, filas: list) -> QFrame:
        """Tarjeta de sección: banda con ícono + título y una grilla de campos.
        `filas` = lista de filas; cada fila = [(label, widget, span), ...] en una
        grilla de 4 columnas (full=4, mitad=2, cuarto=1)."""
        card = QFrame()
        card.setObjectName("form_section")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        head = QFrame()
        head.setObjectName("section_head")
        hl = QHBoxLayout(head)
        hl.setContentsMargins(16, 11, 16, 11)
        hl.setSpacing(8)
        ic = QLabel()
        ic.setPixmap(svg_pixmap(icon, 15, self._pal["accent"]))
        ic.setStyleSheet("background: transparent;")
        t = QLabel(titulo)
        t.setProperty("role", "section-title")
        hl.addWidget(ic)
        hl.addWidget(t)
        hl.addStretch()
        outer.addWidget(head)

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        grid = QGridLayout(body)
        grid.setContentsMargins(16, 14, 16, 16)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)
        for col in range(4):
            grid.setColumnStretch(col, 1)
        for r, fila in enumerate(filas):
            c = 0
            for label, widget, span in fila:
                grid.addWidget(self._field(label, widget), r, c, 1, span)
                c += span
        outer.addWidget(body)
        return card

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
                      "comprobantes electrónicos con AFIP. Necesitás el "
                      "certificado y la clave privada (.crt/.key) del "
                      "contribuyente y el punto de venta habilitado por WS.")
        nota.setProperty("role", "page-subtitle")
        nota.setWordWrap(True)
        f.addRow(nota)

        self._btn_ayuda = QPushButton("  ¿Cómo conectarme con ARCA?")
        self._btn_ayuda.setCursor(Qt.PointingHandCursor)
        self._btn_ayuda.clicked.connect(self._on_ayuda_arca)
        self._estilar_link_ayuda()
        cont = QWidget()
        cont.setStyleSheet("background: transparent;")
        hb = QHBoxLayout(cont)
        hb.setContentsMargins(0, 2, 0, 2)
        hb.addWidget(self._btn_ayuda)
        hb.addStretch()
        f.addRow(cont)

        self._afip = QCheckBox("Habilitar facturación electrónica AFIP")
        f.addRow("", self._afip)
        self._punto_venta = QLineEdit()
        self._punto_venta.setPlaceholderText("Ej. 0001")
        self._ingresos_brutos = QLineEdit()
        self._inicio_actividades = QLineEdit()
        f.addRow("Punto de venta", self._half(self._punto_venta))
        f.addRow("Ingresos Brutos", self._ingresos_brutos)
        f.addRow("Inicio de actividades", self._inicio_actividades)

        self._afip_entorno = self._combo(
            [("Homologación (pruebas)", "homologacion"),
             ("Producción (real)", "produccion")], con_data=True)
        f.addRow("Entorno", self._half(self._afip_entorno))

        self._afip_cert = QLineEdit()
        self._afip_cert.setPlaceholderText("Ruta al certificado (.crt / .pem)")
        btn_cert = QPushButton("Elegir…")
        btn_cert.setObjectName("btn_secondary")
        btn_cert.clicked.connect(self._on_elegir_cert)
        f.addRow("Certificado", _fila(self._afip_cert, btn_cert))

        self._afip_key = QLineEdit()
        self._afip_key.setPlaceholderText("Ruta a la clave privada (.key / .pem)")
        btn_key = QPushButton("Elegir…")
        btn_key.setObjectName("btn_secondary")
        btn_key.clicked.connect(self._on_elegir_key)
        f.addRow("Clave privada", _fila(self._afip_key, btn_key))

        self._btn_probar = QPushButton("Probar conexión")
        self._btn_probar.setObjectName("btn_secondary")
        self._btn_probar.setCursor(Qt.PointingHandCursor)
        self._btn_probar.clicked.connect(self._on_probar_conexion)
        f.addRow("", self._btn_probar)
        return scroll

    # ------------------------------------------------------------ helpers
    def _reformatear(self, line: QLineEdit, fmt) -> None:
        line.setText(fmt(line.text()))
        line.setCursorPosition(len(line.text()))


    # ------------------------------------------------------------ datos
    def refresh(self) -> None:
        e = self.db.get_datos_empresa()
        self._nombre.setText(e.get("nombre") or "")
        self._nif.setText(valor_valido(e.get("nif")) or "")
        self._condicion_iva.setCurrentText(e.get("condicion_iva") or "")
        calle, numero = partir_direccion(e.get("direccion"))
        self._calle.setText(calle)
        self._numero.setText(numero)
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
        idx_ent = self._afip_entorno.findData(self.db.get_config("afip_entorno") or "homologacion")
        self._afip_entorno.setCurrentIndex(idx_ent if idx_ent >= 0 else 0)
        self._afip_cert.setText(self.db.get_config("afip_cert_path") or "")
        self._afip_key.setText(self.db.get_config("afip_key_path") or "")

    def set_theme_zoom(self, theme: str, zoom: float) -> None:
        self._pal = get_palette(theme)
        self._btn_guardar.setIcon(svg_icon("check", 14, self._pal["accent_text"]))
        self._estilar_link_ayuda()

    def _on_elegir_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Elegir logo", "",
                                              "Imágenes (*.png *.jpg *.jpeg)")
        if path:
            self._logo_path.setText(path)

    def _on_elegir_carpeta_pdf(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Elegir carpeta para guardar los PDF")
        if path:
            self._pdf_dir.setText(path)

    def _on_elegir_cert(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Elegir certificado", "", "Certificados (*.crt *.pem *.cer);;Todos (*.*)")
        if path:
            self._afip_cert.setText(path)

    def _on_elegir_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Elegir clave privada", "", "Claves (*.key *.pem);;Todos (*.*)")
        if path:
            self._afip_key.setText(path)

    def _estilar_link_ayuda(self) -> None:
        """Botón-enlace discreto (accent, sin caja): más prolijo que un botón
        secundario grande para una acción de ayuda."""
        accent = self._pal["accent"]
        self._btn_ayuda.setIcon(svg_icon("help-circle", 15, accent))
        self._btn_ayuda.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; color: {accent};"
            f" font-weight: 600; font-size: 13px; text-align: left; padding: 2px 0; }}"
            f" QPushButton:hover {{ text-decoration: underline; }}")

    def _on_ayuda_arca(self) -> None:
        from ui.ayuda_arca import AyudaArcaDialog
        AyudaArcaDialog(theme=leer_tema(self.db), zoom=leer_zoom(self.db),
                        parent=self).exec()

    def _on_probar_conexion(self) -> None:
        """Guarda lo cargado y prueba autenticar contra AFIP (WSAA). Sin
        certificado válido o sin red, muestra el motivo sin romper."""
        self._on_guardar(silencioso=True)
        from fiscal import get_provider
        try:
            provider = get_provider(self.db)
            if not provider.disponible():
                QMessageBox.warning(
                    self, "AFIP",
                    "Faltan datos para conectar: habilitá AFIP y cargá CUIT, "
                    "punto de venta, certificado y clave privada.")
                return
            provider.autenticar()
        except Exception as exc:  # noqa: BLE001 — reportar cualquier fallo al usuario
            QMessageBox.critical(self, "AFIP — error de conexión", str(exc))
            return
        QMessageBox.information(
            self, "AFIP", "Conexión exitosa: autenticación con AFIP correcta.")

    def _on_guardar(self, silencioso: bool = False) -> None:
        self.db.set_config("pdf_dir", self._pdf_dir.text().strip())
        self.db.set_config("afip_entorno", self._afip_entorno.currentData() or "homologacion")
        self.db.set_config("afip_cert_path", self._afip_cert.text().strip())
        self.db.set_config("afip_key_path", self._afip_key.text().strip())
        self.db.update_datos_empresa({
            "nombre": self._nombre.text().strip(),
            "nif": self._nif.text().strip() or None,
            "direccion": unir_direccion(self._calle.text(), self._numero.text()),
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
        if not silencioso:
            QMessageBox.information(self, "Guardado", "Datos guardados correctamente.")
