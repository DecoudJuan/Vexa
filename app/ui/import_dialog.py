"""Diálogo de importación de listas de precios con mapeo de columnas.

Flujo: se abre con un archivo (Excel/CSV), detecta encabezados, sugiere qué
columna es cada campo (nombre/precio/código/talle), muestra una vista previa y,
al confirmar, hace el upsert de conceptos."""

from PySide6.QtWidgets import (
    QLabel, QGridLayout, QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox, QSizePolicy,
    QPushButton, QInputDialog, QCheckBox,
)
from PySide6.QtCore import Qt

from ui.modal import BaseModal
from ui.widgets import NoScrollComboBox
from ui.icons import svg_icon
from utils.helpers import fmt_ar, fmt_talle, leer_zoom, leer_tema
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
        self._perfiles: dict = {}
        super().__init__("Importar lista de precios",
                         "Asigná qué columna es cada dato y revisá la vista previa",
                         icon="file-plus", width=680, scroll=True, height=680,
                         zoom=leer_zoom(db), theme=leer_tema(db), parent=parent)
        self._build()
        self.set_primary_action("Importar", self._accept)
        self._recargar_perfiles()
        self._cargar_hoja()

    # ------------------------------------------------------------ armado
    def _build(self) -> None:
        c = self.content

        # Perfil por proveedor: reusa un mapeo guardado (o guarda el actual).
        c.addWidget(self.section_label("PERFIL DEL PROVEEDOR", "users"))
        perfil_row = QWidget()
        perfil_row.setStyleSheet("background: transparent;")
        pr = QHBoxLayout(perfil_row)
        pr.setContentsMargins(0, 0, 0, 0)
        pr.setSpacing(self._S(8))
        self._perfil_combo = NoScrollComboBox()
        self._perfil_combo.setObjectName("field")
        self._perfil_combo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self._perfil_combo.currentIndexChanged.connect(self._on_perfil_changed)
        pr.addWidget(self._perfil_combo, 1)
        self._btn_guardar_perfil = QPushButton("  Guardar")
        self._btn_guardar_perfil.setObjectName("btn_secondary")
        self._btn_guardar_perfil.setIcon(svg_icon("plus", self._S(14), "#8a90a2"))
        self._btn_guardar_perfil.setCursor(Qt.PointingHandCursor)
        self._btn_guardar_perfil.clicked.connect(self._guardar_perfil)
        pr.addWidget(self._btn_guardar_perfil)
        self._btn_del_perfil = QPushButton()
        self._btn_del_perfil.setObjectName("btn_secondary")
        self._btn_del_perfil.setIcon(svg_icon("trash", self._S(14), "#8a90a2"))
        self._btn_del_perfil.setCursor(Qt.PointingHandCursor)
        self._btn_del_perfil.clicked.connect(self._eliminar_perfil)
        pr.addWidget(self._btn_del_perfil)
        c.addWidget(perfil_row)

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
        self._preview.setColumnCount(4)
        self._preview.setHorizontalHeaderLabels(["Código", "Talle", "Nombre", "Precio"])
        self._preview.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._preview.setSelectionMode(QAbstractItemView.NoSelection)
        self._preview.verticalHeader().setVisible(False)
        self._preview.setMinimumHeight(self._S(200))
        hh = self._preview.horizontalHeader()
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        c.addWidget(self._preview)

        # Reemplazar: vacía el catálogo antes de importar (deja la lista limpia,
        # sin duplicados de importaciones previas). Las facturas no se tocan.
        self._reemplazar = QCheckBox("Reemplazar el catálogo (vaciar antes de importar)")
        c.addWidget(self._reemplazar)
        c.addStretch()

    # ------------------------------------------------------------ datos
    def _cargar_hoja(self, *_a) -> None:
        hoja = self._hoja_combo.currentText() if self._hoja_combo else None
        try:
            self._headers, self._filas = excel_import.leer_hoja(self.path, hoja)
        except Exception as exc:
            QMessageBox.critical(self, "Error al leer el archivo", str(exc))
            self._headers, self._filas = [], []
        # Repoblar las opciones de cada combo con los encabezados de la hoja.
        for combo in self._combos.values():
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("(ninguna)", -1)
            for idx, h in enumerate(self._headers):
                combo.addItem(h, idx)
            combo.blockSignals(False)
        # Selección inicial: perfil elegido si aplica, si no, auto-sugerencia.
        perfil = self._perfiles.get(self._perfil_combo.currentData())
        if perfil:
            mapeo = excel_import.columnas_a_mapeo(perfil.get("columnas", {}), self._headers)
        else:
            mapeo = excel_import.sugerir_mapeo(self._headers)
        self._set_mapeo(mapeo)

    def _set_mapeo(self, mapeo: dict) -> None:
        """Aplica un mapeo {campo: indice|None} a los combos de columnas."""
        for campo, combo in self._combos.items():
            idx = mapeo.get(campo)
            combo.blockSignals(True)
            combo.setCurrentIndex((idx + 1) if idx is not None else 0)
            combo.blockSignals(False)
        self._refresh_preview()

    def _mapeo(self) -> dict:
        return {campo: (combo.currentData() if combo.currentData() != -1 else None)
                for campo, combo in self._combos.items()}

    # --------------------------------------------------------- perfiles
    def _recargar_perfiles(self, seleccion: str | None = None) -> None:
        self._perfiles = self.db.get_perfiles_import()
        self._perfil_combo.blockSignals(True)
        self._perfil_combo.clear()
        self._perfil_combo.addItem("(sin perfil)", None)
        for nombre in sorted(self._perfiles):
            self._perfil_combo.addItem(nombre, nombre)
        if seleccion and seleccion in self._perfiles:
            self._perfil_combo.setCurrentText(seleccion)
        self._perfil_combo.blockSignals(False)
        self._btn_del_perfil.setEnabled(bool(self._perfil_combo.currentData()))

    def _on_perfil_changed(self, *_a) -> None:
        nombre = self._perfil_combo.currentData()
        self._btn_del_perfil.setEnabled(bool(nombre))
        perfil = self._perfiles.get(nombre)
        if not perfil:
            return
        hoja = perfil.get("hoja")
        if (self._hoja_combo and hoja and hoja in self._hojas
                and self._hoja_combo.currentText() != hoja):
            # Cambiar de hoja recarga los encabezados y ya reaplica el perfil.
            self._hoja_combo.setCurrentText(hoja)
        else:
            self._set_mapeo(excel_import.columnas_a_mapeo(
                perfil.get("columnas", {}), self._headers))

    def _guardar_perfil(self) -> None:
        if self._combos["nombre"].currentData() == -1 or self._combos["precio"].currentData() == -1:
            QMessageBox.warning(self, "Faltan columnas",
                                "Asigná al menos Nombre y Precio antes de guardar el perfil.")
            return
        sugerido = self._perfil_combo.currentData() or ""
        nombre, ok = QInputDialog.getText(
            self, "Guardar perfil", "Nombre del perfil (p. ej. el proveedor):",
            text=sugerido)
        if not ok or not nombre.strip():
            return
        perfil = {
            "hoja": self._hoja_combo.currentText() if self._hoja_combo else None,
            "columnas": excel_import.mapeo_a_columnas(self._mapeo(), self._headers),
        }
        self.db.save_perfil_import(nombre.strip(), perfil)
        self._recargar_perfiles(seleccion=nombre.strip())

    def _eliminar_perfil(self) -> None:
        nombre = self._perfil_combo.currentData()
        if not nombre:
            return
        if QMessageBox.question(self, "Eliminar perfil",
                                f"¿Eliminar el perfil «{nombre}»?") != QMessageBox.Yes:
            return
        self.db.delete_perfil_import(nombre)
        self._recargar_perfiles()

    def _refresh_preview(self, *_a) -> None:
        items = excel_import.filas_a_items(self._filas, self._mapeo())
        self._items = items
        self._count.setText(f"{len(items)} productos detectados")
        self._preview.setRowCount(0)
        for it in items[:10]:
            r = self._preview.rowCount()
            self._preview.insertRow(r)
            self._preview.setItem(r, 0, QTableWidgetItem(it["codigo"] or "—"))
            talle = QTableWidgetItem(fmt_talle(it.get("talle")) or "—")
            talle.setTextAlignment(Qt.AlignCenter)
            self._preview.setItem(r, 1, talle)
            self._preview.setItem(r, 2, QTableWidgetItem(it["nombre"]))
            precio = QTableWidgetItem(fmt_ar(it["pvp"]))
            precio.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._preview.setItem(r, 3, precio)

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
        if self._reemplazar.isChecked():
            if QMessageBox.question(
                    self, "Reemplazar catálogo",
                    "Se va a vaciar el catálogo actual y cargar solo estos productos.\n"
                    "Las facturas existentes conservan su detalle. ¿Continuar?"
            ) != QMessageBox.Yes:
                return
            self.db.clear_conceptos()
        self.resumen = self.db.upsert_conceptos(items)
        self.accept()
