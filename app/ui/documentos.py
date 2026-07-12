import re
import sqlite3
from datetime import date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLineEdit, QPushButton, QLabel, QDialog, QFormLayout, QDoubleSpinBox,
    QComboBox, QTextEdit, QMessageBox, QDateEdit, QHeaderView, QFrame,
    QAbstractItemView, QTabWidget, QSizePolicy, QCompleter,
    QGraphicsDropShadowEffect, QScrollArea, QApplication,
)
from PySide6.QtCore import Qt, QDate, QSize, QPoint, QRect
from PySide6.QtGui import QColor, QDoubleValidator

from ui.icons import svg_icon, svg_pixmap
from ui.styles import get_palette
from ui.base_page import ListPage
from ui.modal import build_modal_css, modal_colors
from ui.widgets import fila as _fila, NoScrollComboBox
from utils.helpers import fmt_ar, parse_float, leer_zoom, leer_tema, etiqueta_concepto
from utils.pdf_generator import generar_pdf_documento

# FA=Factura, PR=Presupuesto, AL=Albarán, PE=Pedido, AB=Abono (nota de crédito)
DOCUMENT_TYPES = {
    "FA": {"label": "Factura", "plural": "Facturas", "prefijo": "FA",
           "show_suplidos": True, "convierte_a": ["AB"]},
    "PR": {"label": "Presupuesto", "plural": "Presupuestos", "prefijo": "PR",
           "show_suplidos": False, "convierte_a": ["FA"]},
    "AL": {"label": "Albarán", "plural": "Albaranes", "prefijo": "AL",
           "show_suplidos": False, "convierte_a": ["FA"]},
    "PE": {"label": "Pedido", "plural": "Pedidos", "prefijo": "PE",
           "show_suplidos": False, "convierte_a": ["AL", "FA"]},
    "AB": {"label": "Abono", "plural": "Abonos", "prefijo": "AB",
           "show_suplidos": False, "convierte_a": []},
}


class DocumentosWidget(QWidget):
    """Aloja una pestaña por cada tipo de documento (Factura/Presupuesto/Albarán/Pedido/Abono)."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._lists: dict[str, DocumentListWidget] = {}
        for tipo, cfg in DOCUMENT_TYPES.items():
            widget = DocumentListWidget(self.db, tipo, parent=self)
            self._lists[tipo] = widget
            self._tabs.addTab(widget, cfg["plural"])
        self._tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self._tabs)

    def _on_tab_changed(self, index: int) -> None:
        widget = self._tabs.widget(index)
        if isinstance(widget, DocumentListWidget):
            widget.refresh()

    def refresh(self) -> None:
        widget = self._tabs.currentWidget()
        if isinstance(widget, DocumentListWidget):
            widget.refresh()

    def set_theme_zoom(self, theme: str, zoom: float) -> None:
        for widget in self._lists.values():
            widget.set_theme_zoom(theme, zoom)


class DocumentListWidget(ListPage):
    SEARCH_PLACEHOLDER = "Buscar por número o cliente..."
    SEARCH_MAXW = 360
    COLUMNS = ["Número", "Fecha", "Cliente", "Total", "Origen"]
    ROW_H = 42

    def __init__(self, db, tipo: str, parent=None):
        self.tipo = tipo
        self.cfg = DOCUMENT_TYPES[tipo]
        self.TITULO = self.cfg["plural"]
        super().__init__(db, parent)

    def _header_buttons(self) -> list:
        self._btn_nuevo = self._boton(f"  Nuevo/a {self.cfg['label'].lower()}", "plus",
                                      "accent_text", slot=self._on_nuevo, size=15)
        return [self._btn_nuevo]

    def _build_below_header(self):
        return self._build_summary()

    def _action_widgets(self) -> list:
        self._btn_edit = self._boton("  Editar", "edit", "text", "btn_secondary",
                                     self._on_editar, needs_selection=True)
        self._btn_pdf = self._boton("  Ver PDF", "file-text", "text", "btn_secondary",
                                    self._on_pdf, needs_selection=True)
        self._btn_del = self._boton("  Eliminar", "trash", "danger", "btn_danger",
                                    self._on_eliminar, needs_selection=True)
        return [self._btn_edit, self._btn_pdf, self._btn_del]

    def _configure_columns(self, hh) -> None:
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        for col in (0, 1, 3, 4):
            hh.setSectionResizeMode(col, QHeaderView.Interactive)
        self._resize_columns(hh)

    def _resize_columns(self, hh) -> None:
        hh.setDefaultSectionSize(round(120 * self._zoom))

    def _query(self, search):
        return self.db.get_facturas(tipo=self.tipo, search=search)

    def _pre_render(self, items) -> None:
        self._update_summary(items)

    # ---- resumen del período (KPIs) --------------------------------
    def _build_summary(self) -> QWidget:
        wrap = QWidget()
        wrap.setStyleSheet("background: transparent;")
        h = QHBoxLayout(wrap)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(12)
        c1, self._kpi_fact, self._kpi_fact_sub = self._kpi_card()
        c2, self._kpi_docs, self._kpi_docs_sub = self._kpi_card()
        for card in (c1, c2):
            h.addWidget(card)
        h.addStretch()
        return wrap

    def _kpi_card(self):
        card = QFrame()
        card.setObjectName("metric_card")
        v = QVBoxLayout(card)
        v.setContentsMargins(15, 12, 15, 12)
        v.setSpacing(2)
        k = QLabel()
        k.setProperty("role", "kpi-title")
        val = QLabel("—")
        val.setProperty("role", "kpi-value")
        sub = QLabel("")
        sub.setProperty("role", "kpi-sub")
        v.addWidget(k)
        v.addWidget(val)
        v.addWidget(sub)
        card._kpi_title = k  # guardamos para poner el título/estilos luego
        return card, val, sub

    def _update_summary(self, docs: list[dict]) -> None:
        total = sum(d.get("total") or 0 for d in docs)
        n = len(docs)
        pl = "s" if n != 1 else ""

        p = self._pal
        st_title = f"color:{p['muted1']}; font-size:11px; font-weight:700; letter-spacing:0.06em; background:transparent;"
        st_val = f"color:{p['text']}; font-size:21px; font-weight:800; background:transparent;"
        st_sub = f"color:{p['muted1']}; font-size:11px; background:transparent;"

        pairs = [
            (self._kpi_fact, self._kpi_fact_sub, "TOTAL EMITIDO", fmt_ar(total), f"{n} {self.cfg['plural'].lower()}"),
            (self._kpi_docs, self._kpi_docs_sub, self.cfg["plural"].upper(), str(n), "en total"),
        ]
        for val_lbl, sub_lbl, titulo, val_txt, sub_txt in pairs:
            title_lbl = val_lbl.parentWidget()._kpi_title
            title_lbl.setText(titulo)
            title_lbl.setStyleSheet(st_title)
            val_lbl.setText(val_txt)
            val_lbl.setStyleSheet(st_val)
            sub_lbl.setText(sub_txt)
            sub_lbl.setStyleSheet(st_sub)

    def _fill_row(self, row: int, d: dict) -> None:
        numero = f"{self.cfg['prefijo']}-{d.get('ejercicio')}-{d.get('numero') or ''}"
        self._table.setItem(row, 0, self._cell(numero))
        self._table.setItem(row, 1, self._cell((d.get("fecha") or "")[:10]))
        self._table.setItem(row, 2, self._cell(d.get("cliente_nombre") or ""))
        self._table.setItem(row, 3, self._cell(fmt_ar(d.get("total") or 0), Qt.AlignRight | Qt.AlignVCenter))
        origen = f"{d['origen_tipo']} {d.get('origen_numero') or ''}" if d.get("origen_tipo") else "—"
        self._table.setItem(row, 4, self._cell(origen, Qt.AlignCenter))

    def _count_text(self, total: int) -> str:
        pl = "s" if total != 1 else ""
        return f"{total} documento{pl}"

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
        import os
        os.startfile(path)

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

_PX_RE = re.compile(r"(\d+)px")


class DocumentoDialog(QDialog):
    """Alta/edición de un documento (cabecera + líneas), y generación de un
    documento nuevo a partir de otro (origen) para 'convertir presupuesto en
    factura', etc."""

    def __init__(self, db, tipo: str, factura_id: int | None = None, origen: dict | None = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.tipo = tipo
        self.cfg = DOCUMENT_TYPES[tipo]
        self.factura_id = factura_id
        self.origen = origen
        self._conceptos = self.db.get_all_conceptos()
        self._lineas: list[dict] = []          # {row, combo, cant, pvp, importe}
        self._zoom = leer_zoom(self.db)
        self._theme = leer_tema(self.db)
        self._drag_pos: QPoint | None = None
        self._centered = False

        # Campos legacy que ya no se editan pero se preservan al guardar.
        self._legacy_iva = 0
        self._legacy_retencion = 0
        self._legacy_pedido_cliente = None
        self._ultimo_total = 0.0
        self._ultimo_subtotal = 0.0

        titulo = f"{'Editar' if factura_id else 'Nuevo/a'} {self.cfg['label'].lower()}"
        self.setWindowTitle(titulo)
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # Modal grande: ancho fijo y alto generoso pero que siempre entre en
        # la pantalla. La lista de productos (elástica) se lleva el alto
        # sobrante, así se ven muchas líneas de una.
        avail = QApplication.primaryScreen().availableGeometry()
        self.setFixedWidth(min(self._S(860), avail.width() - self._S(40)))
        self.setFixedHeight(min(self._S(900), avail.height() - self._S(56)))

        self._build_ui()
        self.setStyleSheet(self._scoped_style())

        if factura_id:
            self._cargar_existente(factura_id)
        elif origen:
            self._cargar_desde_origen(origen)
        else:
            self._crear_fila_linea()
            self._sugerir_numero()

        self._recalcular()

    # ----------------------------------------------------------- helpers

    def _S(self, px: float) -> int:
        return max(1, round(px * self._zoom))

    # --------------------------------------------------------------- UI

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        m = self._S(18)
        outer.setContentsMargins(m, m, m, m)
        outer.setSpacing(0)

        root = QFrame()
        root.setObjectName("modal_root")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(self._S(46))
        shadow.setOffset(0, self._S(10))
        shadow.setColor(QColor(15, 23, 42, 90))
        root.setGraphicsEffect(shadow)
        outer.addWidget(root)

        root_l = QVBoxLayout(root)
        root_l.setContentsMargins(0, 0, 0, 0)
        root_l.setSpacing(0)
        root_l.addWidget(self._build_header())
        # Cabecera fija arriba, pie fijo abajo (Guardar SIEMPRE visible) y el
        # cuerpo en el medio; la parte elástica que absorbe el sobrante es la
        # lista de líneas, que tiene su propio scroll interno (ver
        # _build_lineas). Los mínimos son chicos para que el modal entre en
        # monitores de baja resolución.
        root_l.addWidget(self._build_body(), 1)
        root_l.addWidget(self._build_footer())

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("modal_header")
        h = QHBoxLayout(header)
        h.setContentsMargins(self._S(18), self._S(10), self._S(12), self._S(10))
        h.setSpacing(self._S(12))

        icon = QLabel()
        icon.setPixmap(svg_pixmap("file-invoice", self._S(22), "#ffffff"))
        h.addWidget(icon, 0, Qt.AlignVCenter)

        texts = QVBoxLayout()
        texts.setSpacing(self._S(2))
        if self.origen and not self.factura_id:
            oc = DOCUMENT_TYPES[self.origen["tipo"]]
            titulo = f"Nuevo/a {self.cfg['label'].lower()}"
            sub = (f"Desde {oc['prefijo']}-{self.origen.get('ejercicio')}-"
                   f"{self.origen.get('numero')} · el original no se modifica")
        elif self.factura_id:
            titulo = f"Editar {self.cfg['label'].lower()}"
            sub = "Modificá los datos del comprobante"
        else:
            titulo = f"Nueva {self.cfg['label']}" if self.tipo == "FA" else f"Nuevo/a {self.cfg['label'].lower()}"
            sub = "Completá los datos del comprobante"
        t = QLabel(titulo)
        t.setObjectName("modal_title")
        s = QLabel(sub)
        s.setObjectName("modal_subtitle")
        s.setWordWrap(True)
        texts.addWidget(t)
        texts.addWidget(s)
        h.addLayout(texts, 1)

        close = QPushButton()
        close.setObjectName("modal_close")
        close.setIcon(svg_icon("x", self._S(18), "#ffffff"))
        close.setFixedSize(self._S(30), self._S(30))
        close.setCursor(Qt.PointingHandCursor)
        close.clicked.connect(self.reject)
        h.addWidget(close, 0, Qt.AlignTop)

        self._header = header
        return header

    def _section_label(self, text: str, icon_name: str) -> QWidget:
        w = QWidget()
        w.setObjectName("section")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(self._S(6))
        ic = QLabel()
        ic.setPixmap(svg_pixmap(icon_name, self._S(14), "#8a90a2"))
        lbl = QLabel(text)
        lbl.setObjectName("section_label")
        lay.addWidget(ic)
        lay.addWidget(lbl)
        lay.addStretch()
        return w

    def _build_body(self) -> QFrame:
        body = QFrame()
        body.setObjectName("modal_body")
        v = QVBoxLayout(body)
        v.setContentsMargins(self._S(22), self._S(12), self._S(22), self._S(12))
        v.setSpacing(self._S(8))

        # ---- CLIENTE
        v.addWidget(self._section_label("CLIENTE *", "user"))
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
        v.addWidget(self._cliente)

        # ---- DOCUMENTO + FECHA (etiquetas en una fila, campos en la siguiente)
        labels = QHBoxLayout()
        labels.setContentsMargins(0, 0, 0, 0)
        labels.addWidget(self._section_label("DOCUMENTO", "file-text"), 1)
        labels.addWidget(self._section_label("FECHA", "calendar"), 0)
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
        v.addWidget(self._section_label("FORMA DE PAGO", "credit-card"))
        self._forma_pago = NoScrollComboBox()
        self._forma_pago.setObjectName("field")
        self._forma_pago.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self._forma_pago.addItem("Sin definir", None)
        for fp in self.db.get_all_forma_pago():
            self._forma_pago.addItem(fp["tipo"], fp["id"])
        v.addWidget(self._forma_pago)

        # ---- LÍNEAS DE PRODUCTO (parte elástica: se lleva el alto sobrante)
        v.addWidget(self._section_label("LÍNEAS DE PRODUCTO", "package"))
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
        left.addWidget(self._section_label("COMENTARIOS", "message-square"))
        self._comentarios = QTextEdit()
        self._comentarios.setObjectName("comments")
        self._comentarios.setPlaceholderText("Notas adicionales o aclaraciones...")
        self._comentarios.setFixedHeight(self._S(72))
        left.addWidget(self._comentarios)
        left.addStretch()
        bottom.addLayout(left, 1)
        bottom.addWidget(self._build_totales(), 0, Qt.AlignTop)
        v.addLayout(bottom)

        return body

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
        self._bonif_input.setValidator(QDoubleValidator(0.0, 100.0, 2))
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

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setObjectName("modal_footer")
        f = QHBoxLayout(footer)
        f.setContentsMargins(self._S(24), self._S(14), self._S(24), self._S(16))
        f.setSpacing(self._S(10))
        f.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("btn_cancel")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        save = QPushButton("  Guardar")
        save.setObjectName("btn_save")
        save.setIcon(svg_icon("check", self._S(15), "#ffffff"))
        save.setCursor(Qt.PointingHandCursor)
        save.clicked.connect(self._accept)
        f.addWidget(cancel)
        f.addWidget(save)
        return footer

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
        sel = 0
        for i, c in enumerate(self._conceptos, start=1):
            # Etiqueta "nombre (codigo)": permite buscar el producto tipeando
            # el código en el combo (el completer filtra por el texto visible).
            combo.addItem(etiqueta_concepto(c["nombre"], c.get("codigo")), c["id"])
            combo.setItemData(i, c["pvp"], Qt.UserRole + 1)
            if concepto_id and c["id"] == concepto_id:
                sel = i
        combo.lineEdit().setPlaceholderText("Nombre del producto...")
        if concepto_libre and not concepto_id:
            combo.setEditText(concepto_libre)
        elif sel:
            combo.setCurrentIndex(sel)
        # Mostrar el comienzo del nombre (no la cola) cuando no entra completo.
        combo.lineEdit().setCursorPosition(0)
        comp = QCompleter([combo.itemText(i) for i in range(combo.count())])
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        comp.setFilterMode(Qt.MatchContains)
        combo.setCompleter(comp)

        cant = QLineEdit(f"{cantidad:g}")
        cant.setObjectName("cell_input")
        cant.setFixedWidth(self._S(_COL_W["cant"]))
        cant.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        cant.setValidator(QDoubleValidator(0.0, 1e9, 3))

        pvp_w = QLineEdit(f"{pvp:.2f}")
        pvp_w.setObjectName("cell_input")
        pvp_w.setFixedWidth(self._S(_COL_W["pvp"]))
        pvp_w.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        pvp_w.setValidator(QDoubleValidator(0.0, 1e12, 2))

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
        rl.addWidget(importe)
        rl.addWidget(btn_del)

        entry = {"row": row, "combo": combo, "cant": cant, "pvp": pvp_w, "importe": importe}
        self._lineas.append(entry)

        combo.currentIndexChanged.connect(lambda _=None, e=entry: self._on_concepto_changed(e))
        combo.editTextChanged.connect(lambda _=None: self._recalcular())
        cant.textChanged.connect(self._recalcular)
        pvp_w.textChanged.connect(self._recalcular)
        btn_del.clicked.connect(lambda _=None, e=entry: self._quitar_fila(e))

        # insertar antes del stretch final del layout
        self._lineas_layout.insertWidget(self._lineas_layout.count() - 1, row)

    def _quitar_fila(self, entry) -> None:
        if entry in self._lineas:
            self._lineas.remove(entry)
            entry["row"].setParent(None)
            entry["row"].deleteLater()
        self._recalcular()

    def _on_concepto_changed(self, entry) -> None:
        pvp = entry["combo"].currentData(Qt.UserRole + 1)
        if pvp is not None:
            entry["pvp"].setText(f"{float(pvp):.2f}")
        self._recalcular()

    # ------------------------------------------------------------ totales

    def _leer_lineas(self) -> list[dict]:
        out = []
        for e in self._lineas:
            concepto_id = e["combo"].currentData()
            texto = e["combo"].currentText().strip()
            if not texto and not concepto_id:
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

        pct = parse_float(self._bonif_input.text())
        aplica = pct > 0
        bonificacion = subtotal * (pct / 100.0) if aplica else 0.0
        total = subtotal - bonificacion

        self._lbl_subtotal.setText(fmt_ar(subtotal))
        self._lbl_bonif_val.setText(f"−{fmt_ar(bonificacion)}" if aplica else "—")
        self._lbl_total.setText(fmt_ar(total))
        self._ultimo_total = total
        self._ultimo_subtotal = subtotal

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

    def _cargar_desde_origen(self, origen: dict) -> None:
        idx = self._cliente.findData(origen["cliente_id"])
        self._cliente.setCurrentIndex(max(idx, 0))
        self._comentarios.setPlainText(origen.get("comentarios") or "")
        self._bonif_input.setText(
            f"{float(origen.get('bonificacion') or 0):g}" if origen.get("aplica_bonificacion") else "0"
        )
        fp_idx = self._forma_pago.findData(origen.get("forma_pago_id"))
        self._forma_pago.setCurrentIndex(max(fp_idx, 0))
        self._sugerir_numero()

        for ln in self.db.get_lineas(origen["id"]):
            self._crear_fila_linea(
                concepto_id=ln.get("concepto_id"),
                concepto_libre=ln.get("concepto_libre") or "",
                cantidad=ln.get("cantidad") or 1.0,
                pvp=ln.get("pvp") or 0.0,
            )
        if not self._lineas:
            self._crear_fila_linea()

        self._origen_tipo = origen.get("tipo")
        self._origen_numero = origen.get("numero")

    # ------------------------------------------------------------ guardar

    def _accept(self) -> None:
        cliente_id = self._cliente.currentData()
        if cliente_id is None:
            # El usuario pudo tipear un nombre exacto sin elegirlo del popup.
            txt = self._cliente.currentText().strip()
            idx = self._cliente.findText(txt, Qt.MatchFixedString) if txt else -1
            if idx > 0:
                cliente_id = self._cliente.itemData(idx)
        if cliente_id is None:
            QMessageBox.warning(self, "Campo requerido", "Elegí un cliente.")
            return
        lineas = self._leer_lineas()
        if not lineas:
            QMessageBox.warning(self, "Documento vacío", "Agregá al menos una línea.")
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
            "origen_tipo": getattr(self, "_origen_tipo", None),
            "origen_numero": getattr(self, "_origen_numero", None),
            "iva": self._legacy_iva,
            "retencion": self._legacy_retencion,
            "pedido_cliente": self._legacy_pedido_cliente,
        }

        if self.factura_id:
            self.db.update_factura(self.factura_id, data, lineas)
        else:
            self.factura_id = self.db.create_factura(data, lineas)

        self.accept()

    # ------------------------------------------------ arrastre / centrado

    def _header_rect(self) -> QRect:
        top_left = self._header.mapTo(self, QPoint(0, 0))
        return QRect(top_left, self._header.size())

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._header_rect().contains(event.position().toPoint()):
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._centered:
            self._centered = True
            screen = self.screen() or QApplication.primaryScreen()
            avail = screen.availableGeometry()
            parent = self.parentWidget()
            center = parent.window().frameGeometry().center() if parent is not None else avail.center()
            geo = self.frameGeometry()
            geo.moveCenter(center)
            # No dejar que el borde superior quede fuera de la pantalla.
            if geo.top() < avail.top():
                geo.moveTop(avail.top())
            self.move(geo.topLeft())

    # ------------------------------------------------------------- estilo

    def _scoped_style(self) -> str:
        # Chrome + campos comunes vienen del módulo compartido (temables);
        # acá sólo agregamos lo propio del modal de factura (tabla de líneas
        # y tarjeta de totales), también con los colores del tema.
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
        css = build_modal_css(self._theme) + extra
        if abs(self._zoom - 1.0) > 1e-6:
            css = _PX_RE.sub(lambda m: f"{max(1, round(int(m.group(1)) * self._zoom))}px", css)
        return css
