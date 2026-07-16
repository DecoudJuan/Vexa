"""Sección Etiquetas: generador de planchas A4 de etiquetas de productos.

Flujo (3 columnas, adaptado de `adherneo/etiquetas.html`):
  1. Buscar y elegir un producto de la lista de precios de Vexa.
  2. Configurar talle(s) + cantidad y agregarlo a la cola.
  3. Revisar la cola (resumen 14/hoja) y generar el PDF, que se abre para imprimir.

La generación del PDF vive en el core (`vexa_core.utils.etiquetas`), compartida
con el futuro cliente mobile; acá sólo se arma la cola y se abre el archivo."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
    QLineEdit, QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QSpinBox, QPushButton, QMessageBox,
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt

from ui.icons import svg_icon
from ui.anim import RowHighlight, fade_in
from ui.styles import get_palette
from ui.widgets import NoScrollComboBox
from vexa_core.utils.helpers import (
    nombre_sin_talle, abrir_archivo, leer_tema, leer_zoom,
)
from vexa_core.utils.etiquetas import resumen_cola, generar_pdf_etiquetas
from vexa_core.utils.pdf_generator import obtener_carpeta_pdf


class _NoScrollSpin(QSpinBox):
    """QSpinBox que ignora la rueda del mouse (para no cambiar la cantidad sin
    querer al hacer scroll sobre el panel)."""

    def wheelEvent(self, e):  # noqa: N802
        e.ignore()


class EtiquetasWidget(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._theme = leer_tema(db)
        self._zoom = leer_zoom(db)
        self._productos: list[dict] = []
        self._selected: dict | None = None
        self._queue: list[dict] = []
        self._talle_rows: list[dict] = []
        self._build()
        self._load_products()

    # ---------------------------------------------------------------- build
    def _S(self, v: int) -> int:
        return round(v * self._zoom)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(self._S(34), self._S(28), self._S(34), self._S(28))
        root.setSpacing(self._S(16))

        head = QVBoxLayout()
        head.setSpacing(self._S(2))
        titulo = QLabel("Etiquetas")
        titulo.setProperty("role", "page-title")
        sub = QLabel("Armá la cola por producto y talle, y generá las planchas A4 para imprimir")
        sub.setProperty("role", "page-subtitle")
        head.addWidget(titulo)
        head.addWidget(sub)
        root.addLayout(head)

        cols = QHBoxLayout()
        cols.setSpacing(self._S(16))
        cols.addWidget(self._card_productos(), 10)
        cols.addWidget(self._card_config(), 10)
        cols.addWidget(self._card_cola(), 11)
        root.addLayout(cols, 1)

    def _panel(self, step: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("dash_panel")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(self._S(18), self._S(16), self._S(18), self._S(16))
        lay.setSpacing(self._S(12))
        lbl = QLabel(step)
        lbl.setProperty("role", "step-title")
        lay.addWidget(lbl)
        return card, lay

    # ---------------------------------------------------------- col 1: productos
    def _card_productos(self) -> QFrame:
        card, lay = self._panel("1 — SELECCIONAR PRODUCTO")

        self._search = QLineEdit()
        self._search.setObjectName("search_input")
        self._search.setPlaceholderText("Buscar por código o nombre…")
        self._search.addAction(svg_icon("search", 16, get_palette(self._theme)["muted1"]),
                               QLineEdit.LeadingPosition)
        self._search.textChanged.connect(lambda t: self._load_products(t))
        lay.addWidget(self._search)

        # Tabla (no lista) para compartir con el resto de la app el color de
        # selección (row_sel) y la barra que se desliza entre filas (RowHighlight).
        self._prod_table = QTableWidget(0, 2)
        self._prod_table.setObjectName("prod_table")
        self._prod_table.horizontalHeader().hide()
        self._prod_table.verticalHeader().hide()
        self._prod_table.setShowGrid(False)
        self._prod_table.setWordWrap(True)
        self._prod_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._prod_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._prod_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._prod_table.setFocusPolicy(Qt.NoFocus)
        hh = self._prod_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        self._prod_table.setColumnWidth(0, self._S(52))
        self._prod_table.itemSelectionChanged.connect(self._on_select_product)
        lay.addWidget(self._prod_table, 1)
        self._row_hl = RowHighlight(self._prod_table, get_palette(self._theme))
        return card

    # ---------------------------------------------------------- col 2: configurar
    def _card_config(self) -> QFrame:
        card, lay = self._panel("2 — CONFIGURAR ETIQUETAS")
        self._config_lay = lay

        self._config_hint = QLabel("Elegí un producto de la lista para configurar sus etiquetas.")
        self._config_hint.setProperty("role", "empty-hint")
        self._config_hint.setWordWrap(True)
        self._config_hint.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._config_hint)

        # Contenedor que se puebla al elegir producto.
        self._config_body = QWidget()
        self._config_body.setObjectName("plain_box")
        body = QVBoxLayout(self._config_body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(self._S(10))

        self._selected_box = QFrame()
        self._selected_box.setObjectName("etq_selected")
        sb = QVBoxLayout(self._selected_box)
        sb.setContentsMargins(self._S(12), self._S(10), self._S(12), self._S(10))
        sb.setSpacing(self._S(2))
        self._sel_code = QLabel("")
        self._sel_code.setProperty("role", "etq-code")
        self._sel_name = QLabel("")
        self._sel_name.setProperty("role", "etq-name")
        self._sel_name.setWordWrap(True)
        self._sel_type = QLabel("")
        self._sel_type.setProperty("role", "etq-type")
        sb.addWidget(self._sel_code)
        sb.addWidget(self._sel_name)
        sb.addWidget(self._sel_type)
        body.addWidget(self._selected_box)

        self._rows_holder = QWidget()
        self._rows_holder.setObjectName("plain_box")
        self._rows_lay = QVBoxLayout(self._rows_holder)
        self._rows_lay.setContentsMargins(0, 0, 0, 0)
        self._rows_lay.setSpacing(self._S(8))
        body.addWidget(self._rows_holder)

        self._btn_add_row = QPushButton("  Agregar otro talle")
        self._btn_add_row.setObjectName("btn_secondary")
        self._btn_add_row.setIcon(svg_icon("plus", 14, get_palette(self._theme)["text"]))
        self._btn_add_row.setCursor(Qt.PointingHandCursor)
        self._btn_add_row.clicked.connect(lambda: self._add_talle_row())
        body.addWidget(self._btn_add_row)

        body.addStretch()

        self._btn_add_queue = QPushButton("  Agregar a la cola  →")
        self._btn_add_queue.setIcon(svg_icon("plus", 15, get_palette(self._theme)["accent_text"]))
        self._btn_add_queue.setCursor(Qt.PointingHandCursor)
        self._btn_add_queue.clicked.connect(self._on_add_to_queue)
        body.addWidget(self._btn_add_queue)

        self._config_body.hide()
        lay.addWidget(self._config_body, 1)
        return card

    # ---------------------------------------------------------- col 3: cola
    def _card_cola(self) -> QFrame:
        card, lay = self._panel("3 — COLA DE IMPRESIÓN")

        self._queue_list = QListWidget()
        self._queue_list.setObjectName("queue_list")
        self._queue_list.setSelectionMode(QListWidget.NoSelection)
        self._queue_list.setFocusPolicy(Qt.NoFocus)
        lay.addWidget(self._queue_list, 1)

        self._queue_empty = QLabel("No hay etiquetas en la cola todavía.")
        self._queue_empty.setProperty("role", "empty-hint")
        self._queue_empty.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._queue_empty)

        # Resumen.
        self._summary = QFrame()
        self._summary.setObjectName("etq_summary")
        sg = QGridLayout(self._summary)
        sg.setContentsMargins(self._S(14), self._S(10), self._S(14), self._S(10))
        sg.setVerticalSpacing(self._S(3))
        self._sum_total = QLabel("0")
        self._sum_total.setProperty("role", "sum-strong")
        self._sum_pages = QLabel("0")
        self._sum_pages.setProperty("role", "sum-strong")
        for r, (txt, val) in enumerate([("Total de etiquetas", self._sum_total),
                                        ("Hojas A4", self._sum_pages)]):
            sg.addWidget(QLabel(txt), r, 0)
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            sg.addWidget(val, r, 1)
        sg.setColumnStretch(0, 1)
        lay.addWidget(self._summary)

        # Aviso de hoja incompleta.
        self._warn = QFrame()
        self._warn.setObjectName("etq_warn")
        wl = QHBoxLayout(self._warn)
        wl.setContentsMargins(self._S(12), self._S(9), self._S(12), self._S(9))
        self._warn_lbl = QLabel("")
        self._warn_lbl.setWordWrap(True)
        wl.addWidget(self._warn_lbl)
        lay.addWidget(self._warn)

        btns = QHBoxLayout()
        btns.setSpacing(self._S(8))
        self._btn_clear = QPushButton("  Limpiar cola")
        self._btn_clear.setObjectName("btn_danger")
        self._btn_clear.setIcon(svg_icon("trash", 15, get_palette(self._theme)["danger"]))
        self._btn_clear.setCursor(Qt.PointingHandCursor)
        self._btn_clear.clicked.connect(self._on_clear)
        self._btn_generate = QPushButton("  Generar e imprimir")
        self._btn_generate.setIcon(svg_icon("file-text", 15, get_palette(self._theme)["accent_text"]))
        self._btn_generate.setCursor(Qt.PointingHandCursor)
        self._btn_generate.clicked.connect(self._on_generate)
        btns.addWidget(self._btn_clear)
        btns.addWidget(self._btn_generate, 1)
        lay.addLayout(btns)

        self._render_queue()
        return card

    # ---------------------------------------------------------------- productos
    def _load_products(self, search: str = "") -> None:
        self._productos = self.db.get_productos(search=search or None)
        self._prod_table.blockSignals(True)
        self._prod_table.clearContents()
        self._prod_table.setRowCount(len(self._productos))
        pal = get_palette(self._theme)
        for row, p in enumerate(self._productos):
            cod = (p.get("codigo") or "").strip()
            nom = nombre_sin_talle(p.get("nombre")) or (p.get("nombre") or "")
            cod_item = QTableWidgetItem(cod)
            cod_item.setForeground(QColor(pal["accent"]))
            cod_item.setData(Qt.UserRole, p)
            nom_item = QTableWidgetItem(nom)
            self._prod_table.setItem(row, 0, cod_item)
            self._prod_table.setItem(row, 1, nom_item)
        self._prod_table.resizeRowsToContents()
        self._prod_table.blockSignals(False)

    def _talles_de(self, p: dict) -> list[str]:
        return [t for t in (p.get("talles") or []) if (t or "").strip()]

    def _on_select_product(self) -> None:
        row = self._prod_table.currentRow()
        if row < 0:
            return
        cod_item = self._prod_table.item(row, 0)
        p = cod_item.data(Qt.UserRole) if cod_item else None
        if not p:
            return
        self._selected = p
        cod = (p.get("codigo") or "").strip()
        nom = nombre_sin_talle(p.get("nombre")) or (p.get("nombre") or "")
        talles = self._talles_de(p)
        self._sel_code.setText(cod or "—")
        self._sel_name.setText(nom)
        self._sel_type.setText(
            f"Talles: {', '.join(talles)}" if talles else "Universal (sin talle)")

        # Reiniciar filas de talle.
        self._clear_talle_rows()
        self._btn_add_row.setVisible(bool(talles))
        self._add_talle_row()

        self._config_hint.hide()
        self._config_body.show()
        # Aparece con un fade al cambiar de producto (mismo gesto que el resto
        # de la app al cambiar de sección).
        fade_in(self._config_body)

    # ---------------------------------------------------------------- filas talle
    def _clear_talle_rows(self) -> None:
        for r in self._talle_rows:
            r["frame"].setParent(None)
            r["frame"].deleteLater()
        self._talle_rows = []

    def _add_talle_row(self) -> None:
        if not self._selected:
            return
        talles = self._talles_de(self._selected)
        pal = get_palette(self._theme)

        frame = QFrame()
        frame.setObjectName("etq_row")
        row = QHBoxLayout(frame)
        row.setContentsMargins(self._S(10), self._S(8), self._S(10), self._S(8))
        row.setSpacing(self._S(8))

        combo = None
        if talles:
            box = QVBoxLayout()
            box.setSpacing(self._S(2))
            lbl = QLabel("Talle")
            lbl.setProperty("role", "field-label")
            combo = NoScrollComboBox()
            combo.addItems(talles)
            box.addWidget(lbl)
            box.addWidget(combo)
            row.addLayout(box, 1)

        qbox = QVBoxLayout()
        qbox.setSpacing(self._S(2))
        qlbl = QLabel("Cantidad")
        qlbl.setProperty("role", "field-label")
        spin = _NoScrollSpin()
        spin.setRange(1, 999)
        spin.setValue(1)
        spin.setFixedWidth(self._S(90))
        qbox.addWidget(qlbl)
        qbox.addWidget(spin)
        row.addLayout(qbox)

        btn_del = QPushButton()
        btn_del.setObjectName("icon_btn")
        btn_del.setIcon(svg_icon("x", 15, pal["danger"]))
        btn_del.setFixedSize(self._S(28), self._S(28))
        btn_del.setCursor(Qt.PointingHandCursor)
        row.addWidget(btn_del, alignment=Qt.AlignBottom)

        entry = {"frame": frame, "combo": combo, "spin": spin}
        btn_del.clicked.connect(lambda: self._remove_talle_row(entry))
        self._talle_rows.append(entry)
        self._rows_lay.addWidget(frame)
        self._update_row_delete_buttons()

    def _remove_talle_row(self, entry: dict) -> None:
        if len(self._talle_rows) <= 1:
            return
        entry["frame"].setParent(None)
        entry["frame"].deleteLater()
        self._talle_rows.remove(entry)
        self._update_row_delete_buttons()

    def _update_row_delete_buttons(self) -> None:
        # El botón de borrar sólo tiene sentido con más de una fila.
        solo = len(self._talle_rows) <= 1
        for r in self._talle_rows:
            btn = r["frame"].findChild(QPushButton)
            if btn:
                btn.setDisabled(solo)

    # ---------------------------------------------------------------- cola
    def _on_add_to_queue(self) -> None:
        if not self._selected:
            return
        p = self._selected
        cod = (p.get("codigo") or "").strip()
        nom = nombre_sin_talle(p.get("nombre")) or (p.get("nombre") or "")
        for r in self._talle_rows:
            talle = r["combo"].currentText().strip() if r["combo"] else ""
            qty = r["spin"].value()
            self._push_queue(cod, nom, talle, qty)
        self._render_queue()

    def _push_queue(self, cod: str, nom: str, talle: str, qty: int) -> None:
        # Fusiona con un item igual (mismo código/nombre/talle) sumando cantidad.
        for it in self._queue:
            if it["codigo"] == cod and it["nombre"] == nom and it["talle"] == talle:
                it["cantidad"] += qty
                return
        self._queue.append({"codigo": cod, "nombre": nom, "talle": talle, "cantidad": qty})

    def _remove_from_queue(self, it: dict) -> None:
        if it in self._queue:
            self._queue.remove(it)
        self._render_queue()

    def _on_clear(self) -> None:
        if not self._queue:
            return
        if QMessageBox.question(self, "Limpiar cola", "¿Vaciar toda la cola de etiquetas?") \
                == QMessageBox.Yes:
            self._queue = []
            self._render_queue()

    def _render_queue(self) -> None:
        self._queue_list.clear()
        pal = get_palette(self._theme)
        for it in self._queue:
            row = QFrame()
            row.setObjectName("queue_item")
            h = QHBoxLayout(row)
            h.setContentsMargins(self._S(10), self._S(8), self._S(10), self._S(8))
            h.setSpacing(self._S(10))

            chip = QLabel((it["codigo"] or "—")[:6])
            chip.setObjectName("etq_chip")
            chip.setAlignment(Qt.AlignCenter)
            chip.setFixedSize(self._S(40), self._S(30))
            h.addWidget(chip)

            info = QVBoxLayout()
            info.setSpacing(self._S(1))
            lbl = QLabel(it["nombre"] + (f" — T: {it['talle']}" if it["talle"] else ""))
            lbl.setProperty("role", "qi-label")
            det = QLabel(f"Código: {it['codigo'] or '—'}")
            det.setProperty("role", "qi-detail")
            info.addWidget(lbl)
            info.addWidget(det)
            h.addLayout(info, 1)

            qty = QLabel(f"×{it['cantidad']}")
            qty.setProperty("role", "qi-qty")
            h.addWidget(qty)

            btn = QPushButton()
            btn.setObjectName("icon_btn")
            btn.setIcon(svg_icon("x", 15, pal["danger"]))
            btn.setFixedSize(self._S(28), self._S(28))
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, i=it: self._remove_from_queue(i))
            h.addWidget(btn)

            item = QListWidgetItem()
            item.setSizeHint(row.sizeHint())
            self._queue_list.addItem(item)
            self._queue_list.setItemWidget(item, row)

        self._update_summary()

    def _update_summary(self) -> None:
        total = sum(it["cantidad"] for it in self._queue)
        r = resumen_cola(total)
        vacio = total == 0
        self._queue_empty.setVisible(vacio)
        self._queue_list.setVisible(not vacio)
        self._summary.setVisible(not vacio)
        self._btn_generate.setEnabled(not vacio)
        self._btn_clear.setEnabled(not vacio)

        self._sum_total.setText(str(r["total"]))
        self._sum_pages.setText(str(r["paginas"]))
        if not vacio and r["faltan"] > 0:
            self._warn_lbl.setText(
                f"Podés agregar {r['faltan']} etiqueta(s) más para completar la última hoja, "
                f"o dejar el espacio en blanco.")
            self._warn.show()
        else:
            self._warn.hide()

    # ---------------------------------------------------------------- generar
    def _on_generate(self) -> None:
        if not self._queue:
            return
        try:
            ruta = generar_pdf_etiquetas(self._queue, obtener_carpeta_pdf(self.db))
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"No se pudo generar el PDF:\n{e}")
            return
        abrir_archivo(ruta)

    # ---------------------------------------------------------------- API
    def refresh(self) -> None:
        # Recargar productos por si cambió la lista de precios.
        self._load_products(self._search.text() if hasattr(self, "_search") else "")

    def set_theme_zoom(self, theme: str, zoom: float) -> None:
        self._theme = theme
        self._zoom = zoom
        pal = get_palette(theme)
        # Recolorear los íconos que no son parte del stylesheet.
        self._search.actions()[0].setIcon(svg_icon("search", 16, pal["muted1"])) \
            if self._search.actions() else None
        self._btn_add_row.setIcon(svg_icon("plus", 14, pal["text"]))
        self._btn_add_queue.setIcon(svg_icon("plus", 15, pal["accent_text"]))
        self._btn_clear.setIcon(svg_icon("trash", 15, pal["danger"]))
        self._btn_generate.setIcon(svg_icon("file-text", 15, pal["accent_text"]))
        self._row_hl.set_palette(pal)
        self._prod_table.setColumnWidth(0, self._S(52))
        # Recargar productos recolorea el código con el acento del tema nuevo.
        self._load_products(self._search.text())
        self._render_queue()
