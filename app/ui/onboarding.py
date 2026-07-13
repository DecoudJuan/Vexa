"""Asistente de primera ejecución (a pantalla completa de la app).

Página 1: bienvenida con el logo de Vexa y un botón "Comenzar".
Página 2: datos base de la empresa (aparecen en los comprobantes).

Es obligatorio: la app solo continúa a la pantalla principal si se completan
los datos (ver run_onboarding + main.py). La vinculación con AFIP es opcional
(la integración real es la Fase 4 del roadmap)."""

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QCheckBox, QPushButton, QStackedWidget, QScrollArea, QMessageBox,
    QSizePolicy, QApplication, QComboBox,
)
from PySide6.QtWidgets import QCompleter
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from ui.widgets import NoScrollComboBox
from utils.helpers import (
    CONDICIONES_IVA, MONEDAS, PROVINCIAS_AR, set_moneda, leer_zoom,
    formatear_cuit, TELEFONO_EJEMPLO, unir_direccion,
)
from utils.resources import resource_path
from version import APP_NAME

# Pantalla branded, independiente del tema oscuro/claro de la app.
_INK = "#0F1B2D"
_MUTED = "#6B7280"
_BLUE = "#3B4DF0"
_CHEVRON = resource_path("assets/chevron.png").as_posix()

_QSS = f"""
QDialog {{ background: #ffffff; }}
QScrollArea {{ background: #ffffff; border: none; }}
QScrollArea > QWidget {{ background: #ffffff; }}
#page {{ background: #ffffff; }}
QLabel {{ background: transparent; }}
QCheckBox {{ background: transparent; }}
#welcome_title {{ color: {_INK}; font-size: 30px; font-weight: 800; }}
#welcome_sub {{ color: {_MUTED}; font-size: 15px; }}
#form_header {{ background: #ffffff; border-bottom: 1px solid #EDEFF5; }}
#form_title {{ color: {_INK}; font-size: 20px; font-weight: 700; }}
#form_sub {{ color: {_MUTED}; font-size: 12.5px; }}
#form_footer {{ background: #ffffff; border-top: 1px solid #EDEFF5; }}
QLabel#field_label {{ color: {_MUTED}; font-size: 11px; font-weight: 700; letter-spacing: 0.4px; }}
QLabel#hint {{ color: {_MUTED}; font-size: 12px; }}
#page QLineEdit, #page QComboBox {{
    background: #F4F6FB; border: 1px solid #E3E6EF; border-radius: 8px;
    padding: 9px 12px; color: {_INK}; font-size: 13.5px; min-height: 20px;
}}
#page QLineEdit:focus, #page QComboBox:focus {{ border: 1px solid {_BLUE}; background: #ffffff; }}
#page QComboBox::drop-down {{ border: none; background: transparent; width: 26px; }}
#page QComboBox::down-arrow {{ image: url("{_CHEVRON}"); width: 13px; height: 13px; }}
#page QComboBox QAbstractItemView {{
    background: #ffffff; color: {_INK}; border: 1px solid #E3E6EF;
    selection-background-color: #E8ECFD; selection-color: {_INK}; outline: none;
}}
#page QCheckBox {{ color: {_INK}; font-size: 13.5px; spacing: 8px; }}
#page QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid #CFD4E0; border-radius: 5px; background: #fff; }}
#page QCheckBox::indicator:checked {{ background: {_BLUE}; border-color: {_BLUE}; }}
#btn_primary {{
    background: {_BLUE}; color: #ffffff; border: none; border-radius: 10px;
    padding: 12px 20px; font-size: 14px; font-weight: 700;
}}
#btn_primary:hover {{ background: #313fd0; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #DFE2EC; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


class OnboardingWindow(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._zoom = leer_zoom(db)
        self._completed = False
        self.setWindowTitle(APP_NAME)
        self.setModal(True)
        avail = QApplication.primaryScreen().availableGeometry()
        self.resize(min(self._S(1120), avail.width() - 40),
                    min(self._S(720), avail.height() - 60))
        self.setStyleSheet(_QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self._stack = QStackedWidget()
        root.addWidget(self._stack)
        self._stack.addWidget(self._welcome_page())
        self._stack.addWidget(self._form_page())

    def _S(self, px) -> int:
        return max(1, round(px * self._zoom))

    # ------------------------------------------------------------ bienvenida
    def _welcome_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        v = QVBoxLayout(page)
        v.setContentsMargins(40, 40, 40, 40)
        v.setSpacing(self._S(10))
        v.addStretch()

        logo = QLabel()
        logo.setAlignment(Qt.AlignCenter)
        pm = QPixmap(str(resource_path("assets/vexa_logo.png")))
        if not pm.isNull():
            logo.setPixmap(pm.scaledToWidth(self._S(320), Qt.SmoothTransformation))
        v.addWidget(logo)

        title = QLabel(f"¡Bienvenido a {APP_NAME}!")
        title.setObjectName("welcome_title")
        title.setAlignment(Qt.AlignCenter)
        v.addWidget(title)

        sub = QLabel("Configurá tu empresa para empezar a facturar.")
        sub.setObjectName("welcome_sub")
        sub.setAlignment(Qt.AlignCenter)
        v.addWidget(sub)

        v.addSpacing(self._S(26))
        row = QHBoxLayout()
        row.addStretch()
        btn = QPushButton("Comenzar")
        btn.setObjectName("btn_primary")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedWidth(self._S(240))
        btn.clicked.connect(lambda: self._stack.setCurrentIndex(1))
        row.addWidget(btn)
        row.addStretch()
        v.addLayout(row)
        v.addStretch()
        return page

    # ------------------------------------------------------------ helpers
    def _reformatear(self, line: QLineEdit, fmt) -> None:
        """Aplica un formateador al texto mientras se escribe (textEdited no
        se re-dispara con setText, así que no hay recursión)."""
        line.setText(fmt(line.text()))
        line.setCursorPosition(len(line.text()))

    def _provincia_combo(self) -> NoScrollComboBox:
        combo = NoScrollComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        combo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        combo.addItem("")
        for prov in PROVINCIAS_AR:
            combo.addItem(prov)
        combo.setCurrentIndex(0)
        combo.lineEdit().setPlaceholderText("Elegí o escribí la provincia…")
        comp = QCompleter(PROVINCIAS_AR)
        comp.setCaseSensitivity(Qt.CaseInsensitive)
        comp.setFilterMode(Qt.MatchContains)
        comp.setCompletionMode(QCompleter.PopupCompletion)
        combo.setCompleter(comp)
        return combo

    # ------------------------------------------------------------ formulario
    def _labeled(self, texto: str, widget: QWidget) -> QWidget:
        box = QWidget()
        box.setObjectName("page")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(self._S(5))
        lbl = QLabel(texto)
        lbl.setObjectName("field_label")
        lay.addWidget(lbl)
        lay.addWidget(widget)
        return box

    def _form_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("page")
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QWidget()
        header.setObjectName("form_header")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(self._S(56), self._S(28), self._S(56), self._S(18))
        hl.setSpacing(self._S(4))
        ht = QLabel("Datos de tu empresa")
        ht.setObjectName("form_title")
        hs = QLabel("Aparecen en tus comprobantes. Podés cambiarlos después en Configuración.")
        hs.setObjectName("form_sub")
        hl.addWidget(ht)
        hl.addWidget(hs)
        outer.addWidget(header)

        scroll = QScrollArea()
        scroll.setObjectName("page")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        content.setObjectName("page")
        grid = QGridLayout(content)
        grid.setContentsMargins(self._S(56), self._S(12), self._S(56), self._S(24))
        grid.setHorizontalSpacing(self._S(24))
        grid.setVerticalSpacing(self._S(16))

        self._nombre = QLineEdit()
        self._nombre.setPlaceholderText("Razón social / nombre del negocio")
        self._cuit = QLineEdit()
        self._cuit.setPlaceholderText("20-12345678-9")
        self._cuit.textEdited.connect(lambda: self._reformatear(self._cuit, formatear_cuit))
        self._condicion = NoScrollComboBox()
        self._condicion.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self._condicion.addItem("")
        self._condicion.addItems(CONDICIONES_IVA)
        self._calle = QLineEdit()
        self._calle.setPlaceholderText("Av. Corrientes")
        self._numero = QLineEdit()
        self._numero.setPlaceholderText("1234")
        self._localidad = QLineEdit()
        self._provincia = self._provincia_combo()
        self._telefono = QLineEdit()
        self._telefono.setPlaceholderText(TELEFONO_EJEMPLO)
        self._email = QLineEdit()
        self._moneda = NoScrollComboBox()
        self._moneda.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        for etiqueta, simbolo in MONEDAS:
            self._moneda.addItem(etiqueta, simbolo)

        grid.addWidget(self._labeled("NOMBRE / RAZÓN SOCIAL *", self._nombre), 0, 0, 1, 2)
        grid.addWidget(self._labeled("CUIT", self._cuit), 1, 0)
        grid.addWidget(self._labeled("CONDICIÓN FRENTE AL IVA", self._condicion), 1, 1)
        grid.addWidget(self._labeled("CALLE", self._calle), 2, 0)
        grid.addWidget(self._labeled("NÚMERO", self._numero), 2, 1)
        grid.addWidget(self._labeled("LOCALIDAD", self._localidad), 3, 0)
        grid.addWidget(self._labeled("PROVINCIA", self._provincia), 3, 1)
        grid.addWidget(self._labeled("TELÉFONO", self._telefono), 4, 0)
        grid.addWidget(self._labeled("EMAIL", self._email), 4, 1)
        grid.addWidget(self._labeled("MONEDA", self._moneda), 5, 0)

        # --- AFIP (opcional) ---
        self._afip = QCheckBox("Quiero emitir comprobantes electrónicos (AFIP)")
        grid.addWidget(self._afip, 6, 0, 1, 2)
        hint = QLabel("La conexión con AFIP se activa más adelante; por ahora solo se "
                      "guardan los datos.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        grid.addWidget(hint, 7, 0, 1, 2)

        self._afip_box = QWidget()
        self._afip_box.setObjectName("page")
        abox = QGridLayout(self._afip_box)
        abox.setContentsMargins(0, 0, 0, 0)
        abox.setHorizontalSpacing(self._S(24))
        abox.setVerticalSpacing(self._S(16))
        self._punto_venta = QLineEdit()
        self._punto_venta.setPlaceholderText("0001")
        self._ingresos_brutos = QLineEdit()
        self._inicio_actividades = QLineEdit()
        abox.addWidget(self._labeled("PUNTO DE VENTA", self._punto_venta), 0, 0)
        abox.addWidget(self._labeled("INGRESOS BRUTOS", self._ingresos_brutos), 0, 1)
        abox.addWidget(self._labeled("INICIO DE ACTIVIDADES", self._inicio_actividades), 1, 0)
        self._afip_box.setVisible(False)
        self._afip.toggled.connect(self._afip_box.setVisible)
        grid.addWidget(self._afip_box, 8, 0, 1, 2)

        grid.setRowStretch(9, 1)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        footer = QWidget()
        footer.setObjectName("form_footer")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(self._S(56), self._S(16), self._S(56), self._S(16))
        fl.addStretch()
        save = QPushButton("Guardar y empezar")
        save.setObjectName("btn_primary")
        save.setCursor(Qt.PointingHandCursor)
        save.setFixedWidth(self._S(240))
        save.clicked.connect(self._accept)
        fl.addWidget(save)
        outer.addWidget(footer)
        return page

    # ------------------------------------------------------------ guardar
    def _accept(self) -> None:
        nombre = self._nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Falta el nombre",
                                "Ingresá el nombre o razón social de la empresa.")
            self._stack.setCurrentIndex(1)
            self._nombre.setFocus()
            return
        afip_on = self._afip.isChecked()
        self.db.update_datos_empresa({
            "nombre": nombre,
            "nif": self._cuit.text().strip() or None,
            "direccion": unir_direccion(self._calle.text(), self._numero.text()),
            "cp": None,
            "localidad": self._localidad.text().strip() or None,
            "provincia": self._provincia.currentText().strip() or None,
            "telefono": self._telefono.text().strip() or None,
            "fax": None,
            "email": self._email.text().strip() or None,
            "web": None,
            "iva_defecto": 21.0,
            "iva_texto": "IVA",
            "moneda": self._moneda.currentData() or "$",
            "sufijo": None,
            "pie_pagina": None,
            "logo_path": None,  # los comprobantes no llevan logo
            "ccc1": None, "ccc2": None, "ccc3": None, "ccc4": None,
            "ccce1": None, "ccce2": None,
            "condicion_iva": self._condicion.currentText().strip() or None,
            "ingresos_brutos": self._ingresos_brutos.text().strip() or None,
            "inicio_actividades": self._inicio_actividades.text().strip() or None,
            "punto_venta": self._punto_venta.text().strip() or None,
            "afip_habilitado": 1 if afip_on else 0,
        })
        set_moneda(self._moneda.currentData() or "$")
        self.db.set_config("onboarding_done", "1")
        self._completed = True
        self.accept()


def run_onboarding(db, parent=None) -> bool:
    """Muestra el asistente. Devuelve True solo si el usuario completó los datos
    (si cierra la ventana antes, devuelve False y la app no debe continuar)."""
    dlg = OnboardingWindow(db, parent)
    dlg.exec()
    return dlg._completed
