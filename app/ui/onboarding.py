"""Asistente de primera ejecución: si la app se abre sin empresa configurada,
pide los datos base (razón social, CUIT, condición IVA, domicilio, logo, moneda)
para poder facturar. La vinculación con AFIP es OPCIONAL: solo si se tilda, se
piden los datos fiscales para la facturación electrónica (que se implementa en
la Fase 4 del roadmap)."""

from PySide6.QtWidgets import (
    QLineEdit, QLabel, QCheckBox, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QMessageBox, QSizePolicy, QComboBox,
)
from PySide6.QtCore import Qt

from ui.modal import BaseModal
from ui.widgets import NoScrollComboBox
from utils.helpers import CONDICIONES_IVA, set_moneda, leer_zoom, leer_tema
from version import APP_NAME


class OnboardingDialog(BaseModal):
    def __init__(self, db, parent=None):
        self.db = db
        super().__init__(
            "Configuración inicial",
            "Cargá los datos de tu empresa para empezar a facturar",
            icon="settings", width=580, scroll=True, height=760,
            zoom=leer_zoom(db), theme=leer_tema(db), parent=parent,
        )
        self._build_form()
        self.set_primary_action("Guardar y empezar", self._accept)

    # ------------------------------------------------------------ armado
    def _campo(self, label: str, icon: str, widget: QWidget) -> None:
        self.content.addWidget(self.section_label(label, icon))
        self.content.addWidget(widget)

    def _build_form(self) -> None:
        self._nombre = QLineEdit(); self._nombre.setObjectName("field")
        self._nombre.setPlaceholderText("Razón social / nombre del negocio")
        self._campo("NOMBRE / RAZÓN SOCIAL *", "user", self._nombre)

        self._cuit = QLineEdit(); self._cuit.setObjectName("field")
        self._cuit.setPlaceholderText("CUIT (ej. 20-12345678-9)")
        self._campo("CUIT", "hash", self._cuit)

        self._condicion_iva = NoScrollComboBox()
        self._condicion_iva.setObjectName("field")
        self._condicion_iva.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self._condicion_iva.addItem("")
        self._condicion_iva.addItems(CONDICIONES_IVA)
        self._campo("CONDICIÓN FRENTE AL IVA", "file-text", self._condicion_iva)

        self._direccion = QLineEdit(); self._direccion.setObjectName("field")
        self._campo("DOMICILIO", "file-text", self._direccion)

        self._localidad = QLineEdit(); self._localidad.setObjectName("field")
        self._provincia = QLineEdit(); self._provincia.setObjectName("field")
        self._campo("LOCALIDAD", "file-text", self._localidad)
        self._campo("PROVINCIA", "file-text", self._provincia)

        self._telefono = QLineEdit(); self._telefono.setObjectName("field")
        self._email = QLineEdit(); self._email.setObjectName("field")
        self._campo("TELÉFONO", "credit-card", self._telefono)
        self._campo("EMAIL", "credit-card", self._email)

        self._moneda = QLineEdit("$"); self._moneda.setObjectName("field")
        self._campo("MONEDA", "dollar-sign", self._moneda)

        # Logo (opcional)
        self._logo = QLineEdit(); self._logo.setObjectName("field")
        self._logo.setPlaceholderText("Ruta al logo (opcional)")
        btn_logo = QPushButton("Elegir…")
        btn_logo.setObjectName("btn_secondary")
        btn_logo.setCursor(Qt.PointingHandCursor)
        btn_logo.clicked.connect(self._on_logo)
        logo_row = QWidget()
        lr = QHBoxLayout(logo_row)
        lr.setContentsMargins(0, 0, 0, 0)
        lr.setSpacing(self._S(8))
        lr.addWidget(self._logo, 1)
        lr.addWidget(btn_logo)
        self._campo("LOGO", "user", logo_row)

        # --- Facturación electrónica AFIP (opcional) ---
        self._afip = QCheckBox("Quiero emitir comprobantes electrónicos (AFIP)")
        self.content.addWidget(self._afip)
        hint = QLabel("La conexión real con AFIP se activa más adelante; por ahora "
                      "se guardan los datos fiscales.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        self.content.addWidget(hint)

        self._afip_box = QWidget()
        box = QVBoxLayout(self._afip_box)
        box.setContentsMargins(0, self._S(6), 0, 0)
        box.setSpacing(self._S(6))
        self._punto_venta = QLineEdit(); self._punto_venta.setObjectName("field")
        self._punto_venta.setPlaceholderText("Ej. 0001")
        self._ingresos_brutos = QLineEdit(); self._ingresos_brutos.setObjectName("field")
        self._inicio_actividades = QLineEdit(); self._inicio_actividades.setObjectName("field")
        for lbl, w in (("PUNTO DE VENTA", self._punto_venta),
                       ("INGRESOS BRUTOS", self._ingresos_brutos),
                       ("INICIO DE ACTIVIDADES", self._inicio_actividades)):
            box.addWidget(self.section_label(lbl, "file-text"))
            box.addWidget(w)
        self._afip_box.setVisible(False)
        self._afip.toggled.connect(self._afip_box.setVisible)
        self.content.addWidget(self._afip_box)
        self.content.addStretch()

    # ------------------------------------------------------------ acciones
    def _on_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Elegir logo", "",
                                              "Imágenes (*.png *.jpg *.jpeg)")
        if path:
            self._logo.setText(path)

    def _accept(self) -> None:
        nombre = self._nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Falta el nombre",
                                "Ingresá el nombre o razón social de la empresa.")
            self._nombre.setFocus()
            return
        afip_on = self._afip.isChecked()
        self.db.update_datos_empresa({
            "nombre": nombre,
            "nif": self._cuit.text().strip() or None,
            "direccion": self._direccion.text().strip() or None,
            "cp": None,
            "localidad": self._localidad.text().strip() or None,
            "provincia": self._provincia.text().strip() or None,
            "telefono": self._telefono.text().strip() or None,
            "fax": None,
            "email": self._email.text().strip() or None,
            "web": None,
            "iva_defecto": 21.0,
            "iva_texto": "IVA",
            "moneda": self._moneda.text().strip() or "$",
            "sufijo": None,
            "pie_pagina": None,
            "logo_path": self._logo.text().strip() or None,
            "ccc1": None, "ccc2": None, "ccc3": None, "ccc4": None,
            "ccce1": None, "ccce2": None,
            "condicion_iva": self._condicion_iva.currentText().strip() or None,
            "ingresos_brutos": self._ingresos_brutos.text().strip() or None,
            "inicio_actividades": self._inicio_actividades.text().strip() or None,
            "punto_venta": self._punto_venta.text().strip() or None,
            "afip_habilitado": 1 if afip_on else 0,
        })
        set_moneda(self._moneda.text().strip() or "$")
        self.db.set_config("onboarding_done", "1")
        self.accept()


class WelcomeDialog(BaseModal):
    """Pantalla simple de bienvenida en la primera ejecución, con un botón
    'Comenzar' que lleva al asistente de configuración."""

    def __init__(self, db, parent=None):
        super().__init__(
            f"¡Bienvenido a {APP_NAME}!",
            "Configuremos tu empresa en un minuto para empezar a facturar.",
            icon="file-invoice", width=460,
            zoom=leer_zoom(db), theme=leer_tema(db), parent=parent,
        )
        msg = QLabel("Vas a cargar los datos de tu negocio (nombre, CUIT, logo…) "
                     "para que aparezcan en tus comprobantes.")
        msg.setObjectName("hint")
        msg.setWordWrap(True)
        self.content.addWidget(msg)
        self.content.addStretch()
        self.set_primary_action("Comenzar", self.accept)


def run_onboarding(db, parent=None) -> None:
    """Muestra la bienvenida y, si el usuario continúa, el asistente de
    configuración inicial."""
    if WelcomeDialog(db, parent).exec() == BaseModal.Accepted:
        OnboardingDialog(db, parent).exec()
