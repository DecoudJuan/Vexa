"""Guía paso a paso, didáctica, para vincular la app con ARCA (ex AFIP) y poder
emitir facturas electrónicas. Se abre desde Configuración → AFIP. Usa BaseModal,
así respeta el tema claro/oscuro y el zoom de la app."""

import webbrowser

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt

from ui.modal import BaseModal, modal_colors
from ui.icons import svg_icon

_WEB_ARCA = "https://www.arca.gob.ar"

# (número, título, cuerpo en HTML). El cuerpo admite <a href> y <b>.
_PASOS = [
    ("Antes de empezar",
     "Necesitás tu <b>CUIT</b> y tu <b>Clave Fiscal</b> (nivel 3 o superior). "
     "El trámite es <b>gratis</b> y se hace una sola vez. Si nunca usaste la "
     "Clave Fiscal, se gestiona en la web de ARCA o en un cajero de tu banco."),
    ("Elegí el entorno",
     "Abajo, en <b>Entorno</b>, dejá <b>Homologación (pruebas)</b> para practicar "
     "sin emitir comprobantes reales. Cuando todo funcione, cambiás a "
     "<b>Producción</b>."),
    ("Generá tu clave y el pedido de certificado",
     "Abrí una consola (CMD/PowerShell) y ejecutá estos dos comandos, "
     "reemplazando el CUIT y el nombre por los tuyos:"),
    ("Pedí el certificado en ARCA",
     "Entrá a ARCA con tu Clave Fiscal y buscá el servicio "
     "<b>«Administración de Certificados Digitales»</b> (para pruebas es el "
     "ambiente de homologación). Subí el archivo <b>vexa.csr</b> y descargá el "
     "certificado que te genera (<b>vexa.crt</b>)."),
    ("Autorizá el certificado para facturar",
     "En <b>«Administrador de Relaciones de Clave Fiscal»</b> agregá el servicio "
     "<b>«Facturación Electrónica»</b> y asocialo al certificado que creaste. "
     "Sin este paso, ARCA no deja usar el web service."),
    ("Creá tu punto de venta",
     "En <b>«ABM de Puntos de Venta»</b> creá uno de tipo <b>«Web Services»</b> "
     "(es distinto del que usa la web de Comprobantes en línea). Anotá el número, "
     "por ejemplo <b>0001</b>."),
    ("Cargá los datos en Vexa",
     "Acá abajo completá: <b>Certificado</b> (vexa.crt), <b>Clave privada</b> "
     "(vexa.key), <b>Punto de venta</b> y <b>Entorno</b>. Después tocá "
     "<b>«Probar conexión»</b> para confirmar que todo esté bien."),
    ("¡Listo para facturar!",
     "Cuando emitas una factura, usá el botón <b>«Autorizar en AFIP»</b>: Vexa le "
     "pide el <b>CAE</b> a ARCA y le agrega el <b>código QR</b> al PDF, dejándolo "
     "como comprobante válido."),
]

_COMANDO = (
    "openssl genrsa -out vexa.key 2048\n"
    "openssl req -new -key vexa.key "
    "-subj \"/C=AR/O=TU NOMBRE/serialNumber=CUIT 20123456789/CN=vexa\" "
    "-out vexa.csr"
)


class AyudaArcaDialog(BaseModal):
    def __init__(self, theme: str = "light", zoom: float = 1.0, parent=None):
        super().__init__(
            "¿Cómo conectarme con ARCA?",
            "Guía para emitir facturas electrónicas (CAE + QR)",
            icon="help-circle", width=580, scroll=True, height=660,
            zoom=zoom, theme=theme, scale_css=True, parent=parent,
        )
        self._construir()

    def extra_css(self) -> str:
        c = modal_colors(self._theme)
        return f"""
        #guia_intro {{ color: {c['ink']}; font-size: 13.5px; }}
        #guia_num {{
            background: #2f6df6; color: #ffffff; font-weight: 800; font-size: 13px;
            border-radius: 13px; min-width: 26px; max-width: 26px;
            min-height: 26px; max-height: 26px;
        }}
        #guia_title {{ color: {c['ink']}; font-size: 14px; font-weight: 700; }}
        #guia_body {{ color: {c['ink']}; font-size: 13px; }}
        #guia_body a {{ color: {c['focus']}; }}
        #guia_row, #guia_cmdwrap {{ background: transparent; }}
        #guia_cmd {{
            background: {c['field']}; color: {c['ink']};
            border: 1px solid {c['border']}; border-radius: 8px; padding: 10px 12px;
            font-family: Consolas, 'Courier New', monospace; font-size: 12px;
        }}
        """

    def _construir(self) -> None:
        intro = QLabel(
            "Para emitir facturas electrónicas válidas hay que vincular Vexa con "
            "ARCA (ex AFIP). Seguí estos pasos:")
        intro.setObjectName("guia_intro")
        intro.setWordWrap(True)
        self.content.addWidget(intro)

        for i, (titulo, cuerpo) in enumerate(_PASOS, start=1):
            self.content.addWidget(self._paso(i, titulo, cuerpo))
            if titulo.startswith("Generá"):
                self.content.addWidget(self._bloque_comando())

        self.content.addSpacing(self._S(4))
        btn_web = QPushButton("  Abrir la web de ARCA")
        btn_web.setObjectName("btn_secondary")
        btn_web.setIcon(svg_icon("download", self._S(14), "#2f6df6"))
        btn_web.setCursor(Qt.PointingHandCursor)
        btn_web.clicked.connect(lambda: webbrowser.open(_WEB_ARCA))
        fila = QHBoxLayout()
        fila.addWidget(btn_web)
        fila.addStretch()
        self.content.addLayout(fila)
        self.content.addStretch()

        # Pie: un único botón "Entendido" que cierra.
        cerrar = QPushButton("  Entendido")
        cerrar.setObjectName("btn_save")
        cerrar.setIcon(svg_icon("check", self._S(15), "#ffffff"))
        cerrar.setCursor(Qt.PointingHandCursor)
        cerrar.setDefault(True)
        cerrar.clicked.connect(self.accept)
        self._footer_row.addWidget(cerrar)

    def _paso(self, numero: int, titulo: str, cuerpo: str) -> QWidget:
        w = QWidget()
        w.setObjectName("guia_row")
        v = QVBoxLayout(w)
        v.setContentsMargins(0, self._S(4), 0, 0)
        v.setSpacing(self._S(4))

        fila = QHBoxLayout()
        fila.setSpacing(self._S(10))
        num = QLabel(str(numero))
        num.setObjectName("guia_num")
        num.setAlignment(Qt.AlignCenter)
        titulo_lbl = QLabel(titulo)
        titulo_lbl.setObjectName("guia_title")
        titulo_lbl.setWordWrap(True)
        fila.addWidget(num, 0, Qt.AlignTop)
        fila.addWidget(titulo_lbl, 1)
        v.addLayout(fila)

        cuerpo_lbl = QLabel(cuerpo)
        cuerpo_lbl.setObjectName("guia_body")
        cuerpo_lbl.setWordWrap(True)
        cuerpo_lbl.setTextFormat(Qt.RichText)
        cuerpo_lbl.setOpenExternalLinks(True)
        cuerpo_lbl.setContentsMargins(self._S(36), 0, 0, 0)
        v.addWidget(cuerpo_lbl)
        return w

    def _bloque_comando(self) -> QWidget:
        cmd = QLabel(_COMANDO)
        cmd.setObjectName("guia_cmd")
        cmd.setWordWrap(True)
        cmd.setTextInteractionFlags(Qt.TextSelectableByMouse)
        wrap = QWidget()
        wrap.setObjectName("guia_cmdwrap")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(self._S(36), 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(cmd)
        nota = QLabel(
            "Te quedan dos archivos: <b>vexa.key</b> (tu clave, no la compartas) y "
            "<b>vexa.csr</b> (el pedido que subís a ARCA).")
        nota.setObjectName("guia_body")
        nota.setWordWrap(True)
        nota.setTextFormat(Qt.RichText)
        lay.addSpacing(self._S(4))
        lay.addWidget(nota)
        return wrap
