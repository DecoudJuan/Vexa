from datetime import date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QDialog, QComboBox, QTextEdit, QMessageBox, QDateEdit, QHeaderView, QFrame,
    QSizePolicy, QCompleter,
    QScrollArea, QApplication,
)
from PySide6.QtCore import Qt, QDate

from ui.icons import svg_icon
from ui.base_page import ListPage
from ui.modal import BaseModal, modal_colors
from ui.widgets import NoScrollComboBox, num_validator
from vexa_core.utils.helpers import (
    fmt_ar, parse_float, leer_zoom, leer_tema, etiqueta_concepto, abrir_archivo,
)
from vexa_core.utils.pdf_generator import generar_pdf_documento

# La app es SÓLO para facturar: no hay presupuestos, pedidos, albaranes ni
# abonos. Queda un único tipo de documento (la factura).
DOCUMENT_TYPES = {
    "FA": {"label": "Factura", "plural": "Facturas", "prefijo": "FA"},
}


class DocumentosWidget(QWidget):
    """Sección Facturas: la lista de facturas (sin pestañas, único tipo)."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._lista = DocumentListWidget(self.db, "FA", parent=self)
        layout.addWidget(self._lista)

    def refresh(self) -> None:
        self._lista.refresh()

    def set_theme_zoom(self, theme: str, zoom: float) -> None:
        self._lista.set_theme_zoom(theme, zoom)


class DocumentListWidget(ListPage):
    SEARCH_PLACEHOLDER = "Buscar por número o cliente..."
    SEARCH_MAXW = 360
    COLUMNS = ["Número", "Fecha", "Cliente", "Total"]
    ROW_H = 42

    SUBTITULO = "Comprobantes emitidos"

    def __init__(self, db, tipo: str, parent=None):
        self.tipo = tipo
        self.cfg = DOCUMENT_TYPES[tipo]
        self.TITULO = self.cfg["plural"]
        super().__init__(db, parent)

    def _header_buttons(self) -> list:
        self._btn_nuevo = self._boton("  Nueva factura", "plus",
                                      "accent_text", slot=self._on_nuevo, size=15)
        return [self._btn_nuevo]

    def _action_widgets(self) -> list:
        self._btn_edit = self._boton("  Editar", "edit", "text", "btn_secondary",
                                     self._on_editar, needs_selection=True)
        self._btn_pdf = self._boton("  Ver PDF", "file-text", "text", "btn_secondary",
                                    self._on_pdf, needs_selection=True)
        widgets = [self._btn_edit, self._btn_pdf]
        # Autorización electrónica solo para la factura (único comprobante fiscal).
        if self.tipo == "FA":
            self._btn_afip = self._boton("  Autorizar en AFIP", "check", "text",
                                         "btn_secondary", self._on_autorizar,
                                         needs_selection=True)
            widgets.append(self._btn_afip)
        self._btn_del = self._boton("  Eliminar", "trash", "danger", "btn_danger",
                                    self._on_eliminar, needs_selection=True)
        widgets.append(self._btn_del)
        return widgets

    def _configure_columns(self, hh) -> None:
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        for col in (0, 1, 3):
            hh.setSectionResizeMode(col, QHeaderView.Interactive)
        self._resize_columns(hh)

    def _resize_columns(self, hh) -> None:
        hh.setDefaultSectionSize(round(120 * self._zoom))

    def _query(self, search):
        return self.db.get_facturas(tipo=self.tipo, search=search)

    def _fill_row(self, row: int, d: dict) -> None:
        numero = f"{self.cfg['prefijo']}-{d.get('ejercicio')}-{d.get('numero') or ''}"
        self._table.setItem(row, 0, self._cell(numero, accent=True))
        self._table.setItem(row, 1, self._cell((d.get("fecha") or "")[:10]))
        self._table.setItem(row, 2, self._cell(d.get("cliente_nombre") or ""))
        self._table.setItem(row, 3, self._cell(fmt_ar(d.get("total") or 0), Qt.AlignRight | Qt.AlignVCenter))

    def _count_text(self, total: int) -> str:
        pl = "s" if total != 1 else ""
        return f"{total} factura{pl}"

    def _on_nuevo(self) -> None:
        dlg = DocumentoDialog(self.db, self.tipo, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.refresh()

    def _on_editar(self) -> None:
        d = self._selected()
        if not d:
            return
        dlg = DocumentoDialog(self.db, self.tipo, factura_id=d["id"], parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.refresh()

    def _on_pdf(self) -> None:
        d = self._selected()
        if not d:
            return
        try:
            path = generar_pdf_documento(self.db, d["id"])
        except Exception as exc:
            QMessageBox.critical(self, "Error al generar PDF", str(exc))
            return
        abrir_archivo(path)

    def _on_autorizar(self) -> None:
        d = self._selected()
        if not d:
            return
        if d.get("cae"):
            QMessageBox.information(
                self, "AFIP",
                f"Este comprobante ya está autorizado (CAE {d['cae']}).")
            return
        from vexa_core.fiscal import get_provider
        provider = get_provider(self.db)
        if not provider.disponible():
            QMessageBox.warning(
                self, "AFIP",
                "La facturación electrónica no está configurada. Andá a "
                "Configuración → AFIP para habilitarla y cargar el certificado.")
            return
        if QMessageBox.question(
                self, "Autorizar en AFIP",
                "¿Solicitar el CAE de este comprobante a AFIP? La operación es "
                "definitiva y le asigna número fiscal.") != QMessageBox.Yes:
            return
        try:
            factura = self.db.get_factura(d["id"])
            cliente = self.db.get_cliente(factura["cliente_id"]) or {}
            empresa = self.db.get_datos_empresa()
            lineas = self.db.get_lineas(d["id"])
            res = provider.autorizar(factura=factura, empresa=empresa,
                                     cliente=cliente, lineas=lineas)
        except Exception as exc:  # noqa: BLE001 — mostrar el motivo al usuario
            QMessageBox.critical(self, "AFIP — error", str(exc))
            return
        if not res.ok:
            QMessageBox.critical(self, "AFIP rechazó el comprobante",
                                 res.mensaje or "\n".join(res.observaciones))
            return
        self.db.guardar_cae(d["id"], res.cae, res.cae_vto, res.qr_url,
                            res.resultado, res.numero)
        self.refresh()
        QMessageBox.information(self, "AFIP", res.mensaje)
        try:
            abrir_archivo(generar_pdf_documento(self.db, d["id"]))
        except Exception:  # noqa: BLE001 — el CAE ya quedó guardado igual
            pass

    def _on_eliminar(self) -> None:
        d = self._selected()
        if not d:
            return
        if self._confirmar(
            f"¿Eliminar el documento <b>{self.cfg['prefijo']}-{d.get('numero')}</b>?"
        ):
            self.db.delete_factura(d["id"])
            self.refresh()


# =====================================================================
#  DIÁLOGO DE ALTA/EDICIÓN DE DOCUMENTO
#  Modal propio (sin marco nativo): cabecera azul + cuerpo blanco +
#  pie con acciones, con esquinas redondeadas y sombra flotante.
# =====================================================================

# Anchos (en px a zoom 1.0) de las columnas fijas de la tabla de líneas.
_COL_W = {"cant": 68, "pvp": 104, "imp": 108, "del": 34}


class DocumentoDialog(BaseModal):
    """Alta/edición de un documento (cabecera + líneas). Reutiliza el chrome
    (cabecera/pie/arrastre/centrado) de BaseModal; acá vive solo el cuerpo
    propio (líneas + totales)."""

    def __init__(self, db, tipo: str, factura_id: int | None = None, parent=None):
        self.db = db
        self.tipo = tipo
        self.cfg = DOCUMENT_TYPES[tipo]
        self.factura_id = factura_id
        # Productos agrupados (uno por nombre+código con sus variantes de talle)
        # y mapa inverso variante_id -> (índice_producto, talle) para reabrir
        # líneas de facturas existentes.
        self._productos = db.get_productos()
        self._variante_por_id: dict = {}
        for pi, p in enumerate(self._productos):
            for v in p["variantes"]:
                self._variante_por_id[v["id"]] = (pi, v["talle"])
        self._lineas: list[dict] = []          # {row, prod, cant, pvp, importe}
        # Campos legacy que ya no se editan pero se preservan al guardar.
        self._legacy_iva = 0
        self._legacy_retencion = 0
        self._legacy_pedido_cliente = None
        self._ultimo_total = 0.0

        titulo, sub = self._titulos()
        super().__init__(titulo, sub, icon="file-invoice", width=860,
                         zoom=leer_zoom(db), theme=leer_tema(db),
                         scale_css=True, parent=parent)
        # Modal grande: apunta al tamaño de diseño pero se limita a un % de la
        # pantalla para entrar en cualquier monitor. La lista de productos
        # (elástica) se lleva el alto sobrante.
        avail = QApplication.primaryScreen().availableGeometry()
        self.setFixedWidth(min(self._S(860), int(avail.width() * 0.94)))
        self.setFixedHeight(min(self._S(900), int(avail.height() * 0.92)))

        self._build_body()
        self.set_primary_action("Guardar", self._accept)

        if factura_id:
            self._cargar_existente(factura_id)
        else:
            self._crear_fila_linea()
            self._sugerir_numero()

        self.enable_unsaved_guard()

        self._recalcular()

    def _titulos(self) -> tuple[str, str]:
        if self.factura_id:
            titulo = f"Editar {self.cfg['label'].lower()}"
            sub = "Modificá los datos del comprobante"
        else:
            titulo = f"Nueva {self.cfg['label']}" if self.tipo == "FA" else f"Nuevo/a {self.cfg['label'].lower()}"
            sub = "Completá los datos del comprobante"
        return titulo, sub

    # --------------------------------------------------------------- UI

    def _build_body(self) -> None:
        v = self.content
        v.setContentsMargins(self._S(22), self._S(12), self._S(22), self._S(12))
        v.setSpacing(self._S(8))

        # ---- CLIENTE
        v.addWidget(self.section_label("CLIENTE *", "user"))
        self._cliente = NoScrollComboBox()
        self._cliente.setObjectName("field")
        self._cliente.setEditable(True)
        self._cliente.setInsertPolicy(QComboBox.NoInsert)
        self._cliente.addItem("", None)
        for c in self.db.get_all_clientes():
            self._cliente.addItem(c["nombre"], c["id"])
        self._cliente.setCurrentIndex(0)
        self._cliente.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self._cliente.lineEdit().setPlaceholderText("Seleccioná o escribí el cliente...")
        comp = QCompleter([self._cliente.itemText(i) for i in range(1, self._cliente.count())])
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        comp.setFilterMode(Qt.MatchContains)
        self._cliente.setCompleter(comp)
        self._cliente.currentIndexChanged.connect(self._on_cliente_changed)
        # Si se escribe el nombre exacto sin elegirlo del popup, engancharlo al
        # ítem al salir del campo (si no coincide, queda como texto para crear).
        self._cliente.lineEdit().editingFinished.connect(
            lambda: self._snap_a_item(self._cliente))
        v.addWidget(self._cliente)

        # ---- DOCUMENTO + FECHA (etiquetas en una fila, campos en la siguiente)
        labels = QHBoxLayout()
        labels.setContentsMargins(0, 0, 0, 0)
        labels.addWidget(self.section_label("DOCUMENTO", "file-text"), 1)
        labels.addWidget(self.section_label("FECHA", "calendar"), 0)
        v.addLayout(labels)

        fields = QHBoxLayout()
        fields.setSpacing(self._S(8))
        badge = QLabel(f"{self.cfg['prefijo']}-")
        badge.setObjectName("doc_badge")
        badge.setAlignment(Qt.AlignCenter)
        self._ejercicio = QLineEdit(str(date.today().year))
        self._ejercicio.setObjectName("field")
        self._ejercicio.setFixedWidth(self._S(86))
        self._ejercicio.setAlignment(Qt.AlignCenter)
        dash = QLabel("—")
        dash.setObjectName("doc_dash")
        self._numero = QLineEdit()
        self._numero.setObjectName("field")
        self._numero.setFixedWidth(self._S(96))
        self._numero.setAlignment(Qt.AlignCenter)
        self._fecha = QDateEdit()
        self._fecha.setObjectName("field")
        self._fecha.setCalendarPopup(True)
        self._fecha.setDate(QDate.currentDate())
        self._fecha.setDisplayFormat("dd/MM/yyyy")
        self._fecha.setFixedWidth(self._S(150))
        fields.addWidget(badge)
        fields.addWidget(self._ejercicio)
        fields.addWidget(dash)
        fields.addWidget(self._numero)
        fields.addStretch()
        fields.addWidget(self._fecha)
        v.addLayout(fields)

        # ---- FORMA DE PAGO
        v.addWidget(self.section_label("FORMA DE PAGO", "credit-card"))
        self._forma_pago = NoScrollComboBox()
        self._forma_pago.setObjectName("field")
        self._forma_pago.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self._forma_pago.addItem("Sin definir", None)
        for fp in self.db.get_all_forma_pago():
            self._forma_pago.addItem(fp["tipo"], fp["id"])
        v.addWidget(self._forma_pago)

        # ---- LÍNEAS DE PRODUCTO (parte elástica: se lleva el alto sobrante)
        v.addWidget(self.section_label("LÍNEAS DE PRODUCTO", "package"))
        v.addWidget(self._build_lineas(), 1)

        add = QPushButton("  Agregar línea")
        add.setObjectName("btn_add_line")
        add.setIcon(svg_icon("plus", self._S(15), "#2f6df6"))
        add.setCursor(Qt.PointingHandCursor)
        add.clicked.connect(lambda: (self._crear_fila_linea(), self._recalcular()))
        v.addWidget(add)

        # ---- COMENTARIOS + TOTALES
        bottom = QHBoxLayout()
        bottom.setSpacing(self._S(16))
        left = QVBoxLayout()
        left.setSpacing(self._S(8))
        left.addWidget(self.section_label("COMENTARIOS", "message-square"))
        self._comentarios = QTextEdit()
        self._comentarios.setObjectName("comments")
        self._comentarios.setPlaceholderText("Notas adicionales o aclaraciones...")
        self._comentarios.setFixedHeight(self._S(72))
        left.addWidget(self._comentarios)
        left.addStretch()
        bottom.addLayout(left, 1)
        bottom.addWidget(self._build_totales(), 0, Qt.AlignTop)
        v.addLayout(bottom)

    def _build_lineas(self) -> QFrame:
        box = QFrame()
        box.setObjectName("lines_box")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)

        head = QWidget()
        head.setObjectName("lines_head")
        hl = QHBoxLayout(head)
        hl.setContentsMargins(self._S(14), self._S(9), self._S(14), self._S(9))
        hl.setSpacing(self._S(10))

        def col(text, key):
            lbl = QLabel(text)
            lbl.setObjectName("col_head")
            lbl.setFixedWidth(self._S(_COL_W[key]))
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            return lbl

        prod = QLabel("PRODUCTO")
        prod.setObjectName("col_head")
        hl.addWidget(prod, 1)
        hl.addWidget(col("CANT.", "cant"))
        hl.addWidget(col("PRECIO UNIT.", "pvp"))
        hl.addWidget(col("IMPORTE", "imp"))
        spacer = QLabel("")
        spacer.setFixedWidth(self._S(_COL_W["del"]))
        hl.addWidget(spacer)
        bl.addWidget(head)

        holder = QWidget()
        holder.setObjectName("lines_holder")
        self._lineas_layout = QVBoxLayout(holder)
        self._lineas_layout.setContentsMargins(0, 0, 0, 0)
        self._lineas_layout.setSpacing(0)
        self._lineas_layout.addStretch()

        scroll = QScrollArea()
        scroll.setObjectName("lines_scroll")
        scroll.setWidgetResizable(True)
        scroll.setWidget(holder)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Piso chico (no 150) para que el alto mínimo del modal entre en
        # pantallas bajas; la lista igual crece y scrollea sola si hay lugar.
        scroll.setMinimumHeight(self._S(66))
        scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        bl.addWidget(scroll, 1)
        return box

    def _build_totales(self) -> QFrame:
        card = QFrame()
        card.setObjectName("totals_card")
        card.setFixedWidth(self._S(288))
        cl = QVBoxLayout(card)
        cl.setContentsMargins(self._S(16), self._S(14), self._S(16), self._S(14))
        cl.setSpacing(self._S(10))

        bonif = QHBoxLayout()
        bonif.setSpacing(self._S(8))
        blbl = QLabel("BONIFICACIÓN")
        blbl.setObjectName("card_label")
        self._bonif_input = QLineEdit("0")
        self._bonif_input.setObjectName("bonif_input")
        self._bonif_input.setFixedWidth(self._S(66))
        self._bonif_input.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._bonif_input.setValidator(num_validator(0.0, 100.0, 2))
        self._bonif_input.textChanged.connect(self._recalcular)
        pct = QLabel("%")
        pct.setObjectName("card_pct")
        bonif.addWidget(blbl)
        bonif.addStretch()
        bonif.addWidget(self._bonif_input)
        bonif.addWidget(pct)
        cl.addLayout(bonif)

        self._lbl_subtotal = self._card_row(cl, "Subtotal")
        self._lbl_bonif_val = self._card_row(cl, "Bonificación")

        total_bar = QFrame()
        total_bar.setObjectName("total_bar")
        tl = QHBoxLayout(total_bar)
        tl.setContentsMargins(self._S(14), self._S(11), self._S(14), self._S(11))
        tw = QLabel("Total")
        tw.setObjectName("total_bar_label")
        self._lbl_total = QLabel(fmt_ar(0))
        self._lbl_total.setObjectName("total_bar_value")
        self._lbl_total.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        tl.addWidget(tw)
        tl.addStretch()
        tl.addWidget(self._lbl_total)
        cl.addWidget(total_bar)

        return card

    def _card_row(self, parent_layout, label_text: str) -> QLabel:
        row = QHBoxLayout()
        row.setSpacing(self._S(8))
        lbl = QLabel(label_text)
        lbl.setObjectName("card_row_label")
        val = QLabel("—")
        val.setObjectName("card_row_value")
        val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(val)
        parent_layout.addLayout(row)
        return val

    # ------------------------------------------------------------- filas

    def _crear_fila_linea(self, concepto_id=None, concepto_libre="", cantidad=1.0, pvp=0.0) -> None:
        row = QWidget()
        row.setObjectName("line_row")
        # Alto fijo y compacto para que entren muchas líneas en la lista.
        row.setFixedHeight(self._S(40))
        rl = QHBoxLayout(row)
        rl.setContentsMargins(self._S(14), self._S(2), self._S(14), self._S(2))
        rl.setSpacing(self._S(10))

        combo = NoScrollComboBox()
        combo.setObjectName("line_combo")
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        # Ignored: el combo NO impone su ancho preferido (que con nombres de
        # producto largos es enorme) al layout; se estira/encoge según el
        # espacio libre que dejan las columnas fijas, sin empujarlas fuera.
        combo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        combo.addItem("", None)
        for pi, p in enumerate(self._productos):
            # Etiqueta "nombre (codigo)" sin talle: en la factura el producto va
            # por nombre, sin discriminar talle.
            combo.addItem(etiqueta_concepto(p["nombre"], p.get("codigo")), pi)
        combo.lineEdit().setPlaceholderText("Nombre del producto...")
        combo.lineEdit().setCursorPosition(0)
        comp = QCompleter([combo.itemText(i) for i in range(combo.count())])
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        comp.setFilterMode(Qt.MatchContains)
        combo.setCompleter(comp)

        cant = QLineEdit(f"{cantidad:g}")
        cant.setObjectName("cell_input")
        cant.setFixedWidth(self._S(_COL_W["cant"]))
        cant.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        cant.setValidator(num_validator(0.0, 1e9, 3))

        pvp_w = QLineEdit(f"{pvp:.2f}")
        pvp_w.setObjectName("cell_input")
        pvp_w.setFixedWidth(self._S(_COL_W["pvp"]))
        pvp_w.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        # Admite negativos: una línea con precio negativo es un crédito "a favor"
        # que resta del total (devoluciones, descuentos por unidad, etc.).
        pvp_w.setValidator(num_validator(-1e12, 1e12, 2))

        favor = QLabel("A favor")
        favor.setObjectName("favor_badge")
        favor.setAlignment(Qt.AlignCenter)
        favor.setVisible(False)

        importe = QLabel(fmt_ar(0))
        importe.setObjectName("cell_importe")
        importe.setFixedWidth(self._S(_COL_W["imp"]))
        importe.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        btn_del = QPushButton()
        btn_del.setObjectName("btn_row_delete")
        btn_del.setIcon(svg_icon("x", self._S(14), "#b3b7c4"))
        btn_del.setFixedSize(self._S(_COL_W["del"]), self._S(28))
        btn_del.setCursor(Qt.PointingHandCursor)

        rl.addWidget(combo, 1)
        rl.addWidget(cant)
        rl.addWidget(pvp_w)
        rl.addWidget(favor)
        rl.addWidget(importe)
        rl.addWidget(btn_del)

        entry = {"row": row, "prod": combo, "cant": cant,
                 "pvp": pvp_w, "favor": favor, "importe": importe}
        self._lineas.append(entry)

        combo.currentIndexChanged.connect(lambda _=None, e=entry: self._on_producto_changed(e))
        # Nombre escrito a mano (sin elegir del popup): al salir del campo lo
        # enganchamos al producto que coincide para tomar su precio.
        combo.lineEdit().editingFinished.connect(lambda e=entry: self._snap_a_item(e["prod"]))
        combo.editTextChanged.connect(lambda _=None: self._recalcular())
        cant.textChanged.connect(self._recalcular)
        pvp_w.textChanged.connect(self._recalcular)
        btn_del.clicked.connect(lambda _=None, e=entry: self._quitar_fila(e))

        # insertar antes del stretch final del layout
        self._lineas_layout.insertWidget(self._lineas_layout.count() - 1, row)

        # Selección inicial (línea nueva vacía, o carga de una factura existente).
        # El talle de la variante no se usa acá: en la factura el producto va por
        # nombre, sin discriminar talle.
        if concepto_id is not None and concepto_id in self._variante_por_id:
            pi, _tl = self._variante_por_id[concepto_id]
            combo.blockSignals(True)
            combo.setCurrentIndex(combo.findData(pi))
            combo.lineEdit().setCursorPosition(0)
            combo.blockSignals(False)
        elif concepto_libre:
            combo.blockSignals(True)
            combo.setEditText(concepto_libre)
            combo.blockSignals(False)
        # El precio de la línea es el guardado (puede diferir del actual).
        pvp_w.setText(f"{pvp:.2f}")

    def _quitar_fila(self, entry) -> None:
        if entry in self._lineas:
            self._lineas.remove(entry)
            entry["row"].setParent(None)
            entry["row"].deleteLater()
        self._recalcular()

    def _producto_de(self, entry) -> dict | None:
        pi = entry["prod"].currentData()
        if isinstance(pi, int) and 0 <= pi < len(self._productos):
            return self._productos[pi]
        return None

    def _aplicar_pvp(self, entry) -> None:
        # El talle no se discrimina en la factura: se toma el precio del
        # producto (el máximo entre sus variantes, que casi siempre coinciden).
        p = self._producto_de(entry)
        if p is not None:
            entry["pvp"].setText(f"{float(p.get('pvp') or 0):.2f}")

    def _on_producto_changed(self, entry) -> None:
        self._aplicar_pvp(entry)
        self._recalcular()

    # ------------------------------------------------------------ totales

    def _leer_lineas(self) -> list[dict]:
        out = []
        for e in self._lineas:
            p = self._producto_de(e)
            # En la factura el producto va por nombre, sin discriminar talle: se
            # guarda una variante representativa (la primera) sólo para enlazar
            # con el concepto. Si no hay producto, es una línea de texto libre.
            concepto_id = p["ids"][0] if p and p.get("ids") else None
            texto = e["prod"].currentText().strip()
            if not texto and concepto_id is None:
                continue
            out.append({
                "concepto_id": concepto_id,
                "concepto_libre": None if concepto_id else (texto or None),
                "cantidad": parse_float(e["cant"].text()),
                "pvp": parse_float(e["pvp"].text()),
            })
        return out

    def _recalcular(self, *_args) -> None:
        subtotal = 0.0
        for e in self._lineas:
            importe = parse_float(e["cant"].text()) * parse_float(e["pvp"].text())
            subtotal += importe
            e["importe"].setText(fmt_ar(importe))
            # Línea "a favor": precio/importe negativo → badge + importe en rojo.
            neg = importe < 0
            e["favor"].setVisible(neg)
            e["importe"].setStyleSheet("color: #e5484d; font-weight: 700;" if neg else "")

        pct = parse_float(self._bonif_input.text())
        aplica = pct > 0
        bonificacion = subtotal * (pct / 100.0) if aplica else 0.0
        total = subtotal - bonificacion

        self._lbl_subtotal.setText(fmt_ar(subtotal))
        self._lbl_bonif_val.setText(f"−{fmt_ar(bonificacion)}" if aplica else "—")
        self._lbl_total.setText(fmt_ar(total))
        self._ultimo_total = total

    # ------------------------------------------------------------- carga

    def _sugerir_numero(self) -> None:
        ejercicio = int(self._ejercicio.text() or date.today().year)
        self._numero.setText(self.db.siguiente_numero(self.tipo, ejercicio))

    def _on_cliente_changed(self) -> None:
        cliente_id = self._cliente.currentData()
        if cliente_id is None:
            return
        cliente = self.db.get_cliente(cliente_id)
        if not cliente:
            return
        bonificacion_cliente = float(cliente.get("bonificacion") or 0)
        if bonificacion_cliente:
            self._bonif_input.setText(f"{bonificacion_cliente:g}")
        fp_id = cliente.get("forma_pago_id")
        if fp_id:
            idx = self._forma_pago.findData(fp_id)
            if idx >= 0:
                self._forma_pago.setCurrentIndex(idx)

    def _cargar_existente(self, factura_id: int) -> None:
        d = self.db.get_factura(factura_id)
        if not d:
            return
        idx = self._cliente.findData(d["cliente_id"])
        self._cliente.setCurrentIndex(max(idx, 0))
        self._ejercicio.setText(str(d.get("ejercicio") or date.today().year))
        self._numero.setText(d.get("numero") or "")
        fecha = QDate.fromString((d.get("fecha") or "")[:10], "yyyy-MM-dd")
        if fecha.isValid():
            self._fecha.setDate(fecha)
        fp_idx = self._forma_pago.findData(d.get("forma_pago_id"))
        self._forma_pago.setCurrentIndex(max(fp_idx, 0))
        self._comentarios.setPlainText(d.get("comentarios") or "")
        self._bonif_input.setText(
            f"{float(d.get('bonificacion') or 0):g}" if d.get("aplica_bonificacion") else "0"
        )
        self._legacy_iva = d.get("iva") or 0
        self._legacy_retencion = d.get("retencion") or 0
        self._legacy_pedido_cliente = d.get("pedido_cliente")

        for ln in self.db.get_lineas(factura_id):
            self._crear_fila_linea(
                concepto_id=ln.get("concepto_id"),
                concepto_libre=ln.get("concepto_libre") or "",
                cantidad=ln.get("cantidad") or 1.0,
                pvp=ln.get("pvp") or 0.0,
            )
        if not self._lineas:
            self._crear_fila_linea()

    # ------------------------------------------------------------ guardar

    def _snap_a_item(self, combo) -> None:
        """Si se tipeó el texto exacto de un ítem sin elegirlo del popup, el
        combo editable queda con índice sin fijar (texto libre) y se pierde su
        dato asociado (id de cliente / variante de producto). Lo enganchamos al
        ítem que coincide para que valga como una selección real; si no coincide
        con ninguno, se deja el texto tal cual."""
        if combo.currentData() is not None:
            return
        txt = combo.currentText().strip()
        if not txt:
            return
        idx = combo.findText(txt, Qt.MatchFixedString)
        if idx > 0:
            combo.setCurrentIndex(idx)

    def _accept(self) -> None:
        # Enganchar textos escritos a mano (cliente y productos) a su ítem real
        # antes de leer, así una selección tipeada vale igual que una elegida
        # (en el producto esto además toma su precio de lista).
        self._snap_a_item(self._cliente)
        for e in self._lineas:
            self._snap_a_item(e["prod"])

        cliente_id = self._cliente.currentData()
        if cliente_id is None:
            # No coincide con ningún cliente: se crea al vuelo con lo escrito,
            # así se puede facturar a un cliente nuevo sin cargarlo aparte antes.
            txt = self._cliente.currentText().strip()
            if txt:
                cliente_id = self.db.create_cliente({"nombre": txt})
        if cliente_id is None:
            self._warn("Campo requerido", "Escribí o elegí un cliente.")
            return
        lineas = self._leer_lineas()
        if not lineas:
            self._warn("Documento vacío", "Agregá al menos una línea.")
            return

        try:
            ejercicio = int(self._ejercicio.text())
        except ValueError:
            ejercicio = date.today().year

        pct = parse_float(self._bonif_input.text())
        data = {
            "cliente_id": cliente_id,
            "tipo": self.tipo,
            "ejercicio": ejercicio,
            "numero": self._numero.text().strip(),
            "fecha": self._fecha.date().toString("yyyy-MM-dd"),
            "total": self._ultimo_total,
            "bonificacion": pct,
            "aplica_bonificacion": 1 if pct > 0 else 0,
            "forma_pago_id": self._forma_pago.currentData(),
            "comentarios": self._comentarios.toPlainText().strip() or None,
            "origen_tipo": None,
            "origen_numero": None,
            "iva": self._legacy_iva,
            "retencion": self._legacy_retencion,
            "pedido_cliente": self._legacy_pedido_cliente,
        }

        if self.factura_id:
            self.db.update_factura(self.factura_id, data, lineas)
        else:
            self.factura_id = self.db.create_factura(data, lineas)

        self.accept()

    # ------------------------------------------------------------- estilo

    def extra_css(self) -> str:
        # Chrome + campos comunes vienen de BaseModal; acá sólo lo propio del
        # modal de factura (tabla de líneas y tarjeta de totales), con los
        # colores del tema. El escalado de px por zoom lo aplica BaseModal.
        extra = """
        #lines_box { background: %BODY%; border: 1px solid %BORDER%; border-radius: 10px; }
        #lines_head { background: %HEAD_BG%; border-top-left-radius: 9px; border-top-right-radius: 9px; }
        #col_head { color: %HEAD_TX%; font-size: 11px; font-weight: 700; letter-spacing: 0.3px; }
        #lines_scroll { background: %BODY%; border: none; }
        #lines_holder { background: %BODY%; }
        #line_row { background: %BODY%; border-bottom: 1px solid %ROW_SEP%; }
        #modal_body QComboBox#line_combo {
            background: transparent; border: none; border-radius: 6px;
            padding: 5px 6px; color: %INK%; font-size: 13px; min-height: 24px;
        }
        #modal_body QComboBox#line_combo:focus { background: %FIELD%; }
        #modal_body QComboBox#line_combo QLineEdit { background: transparent; border: none; padding: 0; color: %INK%; }
        #modal_body QLineEdit#cell_input {
            background: transparent; border: none; border-radius: 6px;
            color: %INK%; font-size: 13px; padding: 5px 4px;
        }
        #modal_body QLineEdit#cell_input:focus { background: %FIELD%; }
        #cell_importe { color: %ACCENT_INK%; font-weight: 700; font-size: 13px; }
        #favor_badge {
            color: #e5484d; background: rgba(229,72,77,0.12); border-radius: 6px;
            padding: 2px 7px; font-size: 11px; font-weight: 700;
        }
        #btn_row_delete { background: transparent; border: none; border-radius: 6px; }
        #btn_row_delete:hover { background: %DEL_HOVER%; }
        #btn_add_line {
            background: %CARD%; border: 1px solid %BORDER%; border-radius: 9px;
            color: %FOCUS%; font-weight: 700; font-size: 13px; padding: 10px; min-height: 18px;
        }
        #btn_add_line:hover { background: %FIELD%; border-color: %FOCUS%; }
        #totals_card { background: %CARD%; border: 1px solid %BORDER%; border-radius: 12px; }
        #card_label { color: %MUTED%; font-size: 11px; font-weight: 700; letter-spacing: 0.3px; }
        #card_pct { color: %MUTED%; font-size: 13px; }
        #bonif_input {
            background: %CARD%; border: 1px solid %BORDER%; border-radius: 7px;
            padding: 6px 8px; color: %INK%; font-size: 13px;
        }
        #bonif_input:focus { border: 1px solid %FOCUS%; }
        #card_row_label { color: %CANCEL_TX%; font-size: 13px; }
        #card_row_value { color: %INK%; font-size: 13px; font-weight: 600; }
        #total_bar { background: #2f6df6; border-radius: 9px; }
        #total_bar_label { color: #ffffff; font-size: 14px; font-weight: 700; }
        #total_bar_value { color: #ffffff; font-size: 17px; font-weight: 800; }
        """
        for key, value in modal_colors(self._theme).items():
            extra = extra.replace("%" + key.upper() + "%", value)
        return extra
