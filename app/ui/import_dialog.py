"""Diálogo de importación de listas de precios con mapeo de columnas.

Flujo: se abre con un archivo (Excel/CSV), detecta encabezados, sugiere qué
columna es cada campo (nombre/precio/código/talle), muestra una vista previa y,
al confirmar, hace el upsert de conceptos."""

from PySide6.QtWidgets import (
    QLabel, QGridLayout, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox, QSizePolicy,
)
from PySide6.QtCore import Qt

from ui.modal import BaseModal
from ui.widgets import NoScrollComboBox
from utils.helpers import fmt_ar, leer_zoom, leer_tema
from utils import excel_import

_CAMPOS_UI = [
    ("nombre", "NOMBRE / DESCRIPCIÓN *"),
    ("precio", "PRECIO *"),
    ("codigo", "CÓDIGO"),
    ("talle", "TALLE"),
]


class ImportDialog(BaseModal):
    def __init__(self, db, path: str, parent=None):
        self.db = db
        self.path = path
        self.resumen = None            # {'creados','actualizados'} tras importar
        self._headers: list[str] = []
        self._filas: list[list] = []
        self._combos: dict = {}
        super().__init__("Importar lista de precios",
                         "Asigná qué columna es cada dato y revisá la vista previa",
                         icon="file-plus", width=680, scroll=True, height=680,
                         zoom=leer_zoom(db), theme=leer_tema(db), parent=parent)
        self._build()
        self.set_primary_action("Importar", self._accept)
        self._cargar_hoja()

    # ------------------------------------------------------------ armado
    def _build(self) -> None:
        c = self.content

        # Selector de hoja (solo si hay más de una)
        self._hojas = excel_import.listar_hojas(self.path)
        self._hoja_combo = None
        if len(self._hojas) > 1:
            c.addWidget(self.section_label("HOJA", "layers"))
            self._hoja_combo = NoScrollComboBox()
            self._hoja_combo.setObjectName("field")
            self._hoja_combo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            self._hoja_combo.addItems(self._hojas)
            self._hoja_combo.currentIndexChanged.connect(self._cargar_hoja)
            c.addWidget(self._hoja_combo)

        # Mapeo de columnas
        c.addWidget(self.section_label("COLUMNAS", "grid"))
        grid_box = QWidget()
        grid_box.setStyleSheet("background: transparent;")
        self._grid = QGridLayout(grid_box)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(self._S(14))
        self._grid.setVerticalSpacing(self._S(8))
        for i, (campo, etiqueta) in enumerate(_CAMPOS_UI):
            lbl = QLabel(etiqueta)
            lbl.setObjectName("section_label")
            combo = NoScrollComboBox()
            combo.setObjectName("field")
            combo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            combo.currentIndexChanged.connect(self._refresh_preview)
            self._combos[campo] = combo
            r, col = divmod(i, 2)
            cell = QVBoxLayout()
            cell.setSpacing(self._S(4))
            cell.addWidget(lbl)
            cell.addWidget(combo)
            wrap = QWidget()
            wrap.setStyleSheet("background: transparent;")
            wrap.setLayout(cell)
            self._grid.addWidget(wrap, r, col)
        c.addWidget(grid_box)

        # Vista previa
        c.addWidget(self.section_label("VISTA PREVIA", "file-text"))
        self._count = QLabel("")
        self._count.setObjectName("hint")
        c.addWidget(self._count)
        self._preview = QTableWidget()
        self._preview.setColumnCount(3)
        self._preview.setHorizontalHeaderLabels(["Código", "Nombre", "Precio"])
        self._preview.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._preview.setSelectionMode(QAbstractItemView.NoSelection)
        self._preview.verticalHeader().setVisible(False)
        self._preview.setMinimumHeight(self._S(200))
        hh = self._preview.horizontalHeader()
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        c.addWidget(self._preview)
        c.addStretch()

    # ------------------------------------------------------------ datos
    def _cargar_hoja(self, *_a) -> None:
        hoja = self._hoja_combo.currentText() if self._hoja_combo else None
        try:
            self._headers, self._filas = excel_import.leer_hoja(self.path, hoja)
        except Exception as exc:
            QMessageBox.critical(self, "Error al leer el archivo", str(exc))
            self._headers, self._filas = [], []
        sug = excel_import.sugerir_mapeo(self._headers)
        for campo, combo in self._combos.items():
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("(ninguna)", -1)
            for idx, h in enumerate(self._headers):
                combo.addItem(h, idx)
            sugerido = sug.get(campo)
            combo.setCurrentIndex((sugerido + 1) if sugerido is not None else 0)
            combo.blockSignals(False)
        self._refresh_preview()

    def _mapeo(self) -> dict:
        return {campo: (combo.currentData() if combo.currentData() != -1 else None)
                for campo, combo in self._combos.items()}

    def _refresh_preview(self, *_a) -> None:
        items = excel_import.filas_a_items(self._filas, self._mapeo())
        self._items = items
        self._count.setText(f"{len(items)} productos detectados")
        self._preview.setRowCount(0)
        for it in items[:10]:
            r = self._preview.rowCount()
            self._preview.insertRow(r)
            self._preview.setItem(r, 0, QTableWidgetItem(it["codigo"] or "—"))
            self._preview.setItem(r, 1, QTableWidgetItem(it["nombre"]))
            precio = QTableWidgetItem(fmt_ar(it["pvp"]))
            precio.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._preview.setItem(r, 2, precio)

    def _accept(self) -> None:
        if self._combos["nombre"].currentData() == -1 or self._combos["precio"].currentData() == -1:
            QMessageBox.warning(self, "Faltan columnas",
                                "Asigná al menos las columnas de Nombre y Precio.")
            return
        items = excel_import.filas_a_items(self._filas, self._mapeo())
        if not items:
            QMessageBox.warning(self, "Sin datos",
                                "No se detectaron productos con el mapeo actual.")
            return
        self.resumen = self.db.upsert_conceptos(items)
        self.accept()
