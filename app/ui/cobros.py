from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QTabWidget, QHeaderView, QAbstractItemView,
    QMessageBox, QDialog, QFormLayout, QDateEdit, QLineEdit,
)
from PySide6.QtCore import Qt, QDate, QSize

from ui.icons import svg_icon
from ui.styles import get_palette
from utils.helpers import fmt_money, leer_tema
from utils.pdf_generator import generar_reporte_remesa


class CobrosWidget(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._recibos = RecibosWidget(db, parent=self)
        self._remesas = RemesasWidget(db, parent=self)
        self._tabs.addTab(self._recibos, "Recibos pendientes")
        self._tabs.addTab(self._remesas, "Remesas")
        self._tabs.currentChanged.connect(lambda i: self._tabs.widget(i).refresh())
        layout.addWidget(self._tabs)

    def refresh(self) -> None:
        self._tabs.currentWidget().refresh()

    def set_theme_zoom(self, theme: str, zoom: float) -> None:
        self._recibos.set_theme_zoom(theme, zoom)
        self._remesas.set_theme_zoom(theme, zoom)


class RecibosWidget(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._pal = get_palette(leer_tema(db))
        self._recibos: list[dict] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        h = QLabel("Recibos pendientes de remesa")
        h.setProperty("role", "page-title")
        layout.addWidget(h)

        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Cliente", "Documento", "Importe"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        layout.addWidget(self._table)

        actions = QHBoxLayout()
        self._btn_remesa = QPushButton("  Generar remesa con seleccionados")
        self._btn_remesa.setIcon(svg_icon("layers", 14, self._pal["text"]))
        self._btn_remesa.setIconSize(QSize(14, 14))
        self._btn_remesa.setObjectName("btn_secondary")
        self._btn_remesa.setCursor(Qt.PointingHandCursor)
        self._btn_remesa.clicked.connect(self._on_generar_remesa)
        actions.addWidget(self._btn_remesa)
        actions.addStretch()
        layout.addLayout(actions)

        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)

    def refresh(self) -> None:
        self._recibos = self.db.get_recibos_pendientes()
        self._table.setRowCount(len(self._recibos))
        for row, r in enumerate(self._recibos):
            self._table.setItem(row, 0, QTableWidgetItem(r.get("cliente_nombre", "")))
            self._table.setItem(row, 1, QTableWidgetItem(f"{r.get('factura_tipo','')}-{r.get('factura_numero','')}"))
            item = QTableWidgetItem(fmt_money(r.get("importe") or 0))
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._table.setItem(row, 2, item)

    def _on_generar_remesa(self) -> None:
        filas = sorted({i.row() for i in self._table.selectedIndexes()})
        if not filas:
            QMessageBox.information(self, "Seleccioná recibos", "Elegí uno o más recibos para agrupar en una remesa.")
            return
        recibo_ids = [self._recibos[f]["id"] for f in filas]
        data = {
            "descripcion": f"Remesa {QDate.currentDate().toString('dd/MM/yyyy')}",
            "fecha": QDate.currentDate().toString("yyyy-MM-dd"),
            "fecha_cargo": None,
            "fecha_vto": None,
        }
        self.db.create_remesa(recibo_ids, data)
        QMessageBox.information(self, "Remesa creada", f"Se agruparon {len(recibo_ids)} recibos.")
        self.refresh()

    def set_theme_zoom(self, theme: str, zoom: float) -> None:
        self._pal = get_palette(theme)
        self._btn_remesa.setIcon(svg_icon("layers", 14, self._pal["text"]))


class RemesasWidget(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._pal = get_palette(leer_tema(db))
        self._remesas: list[dict] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        h = QLabel("Remesas")
        h.setProperty("role", "page-title")
        s = QLabel("Agrupación de recibos para presentación al banco (reporte, no archivo SEPA)")
        s.setProperty("role", "page-subtitle")
        layout.addWidget(h)
        layout.addWidget(s)

        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Fecha", "Descripción", "Recibos", "Total"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self._table)

        actions = QHBoxLayout()
        self._btn_pdf = QPushButton("  Ver reporte PDF")
        self._btn_pdf.setIcon(svg_icon("file-text", 14, self._pal["text"]))
        self._btn_pdf.setObjectName("btn_secondary")
        self._btn_pdf.setCursor(Qt.PointingHandCursor)
        self._btn_pdf.clicked.connect(self._on_pdf)
        actions.addWidget(self._btn_pdf)
        actions.addStretch()
        layout.addLayout(actions)

    def refresh(self) -> None:
        self._remesas = self.db.get_all_remesas()
        self._table.setRowCount(len(self._remesas))
        for row, r in enumerate(self._remesas):
            self._table.setItem(row, 0, QTableWidgetItem((r.get("fecha") or "")[:10]))
            self._table.setItem(row, 1, QTableWidgetItem(r.get("descripcion") or ""))
            self._table.setItem(row, 2, QTableWidgetItem(str(r.get("n_recibos") or 0)))
            item = QTableWidgetItem(fmt_money(r.get("total") or 0))
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._table.setItem(row, 3, item)

    def _on_pdf(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._remesas):
            QMessageBox.information(self, "Seleccioná una remesa", "Elegí una remesa para ver su reporte.")
            return
        path = generar_reporte_remesa(self.db, self._remesas[row]["id"])
        import os
        os.startfile(path)

    def set_theme_zoom(self, theme: str, zoom: float) -> None:
        self._pal = get_palette(theme)
        self._btn_pdf.setIcon(svg_icon("file-text", 14, self._pal["text"]))
