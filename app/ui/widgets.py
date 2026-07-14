"""Widgets chicos compartidos entre pantallas."""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox
from PySide6.QtCore import Qt


class NoScrollComboBox(QComboBox):
    """QComboBox que IGNORA la rueda del mouse: girar la rueda no cambia la
    selección (peligroso al armar una factura, cambiaba el producto sin
    querer). Al ignorar el evento, éste se propaga al área de scroll, así la
    rueda sube/baja la lista como se espera. El desplegable sigue abriéndose
    con el clic y, ya abierto, la rueda scrollea sus opciones normalmente."""

    def wheelEvent(self, event) -> None:  # noqa: N802 (API de Qt)
        event.ignore()


def avatar(initials: str, bg: str, fg: str, size: int = 32) -> QLabel:
    lbl = QLabel(initials)
    lbl.setFixedSize(size, size)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(
        f"background: {bg}; color: {fg}; border-radius: 8px;"
        f"font-weight: 800; font-size: 12px;"
    )
    return lbl


def fila(*widgets: QWidget) -> QWidget:
    """Envuelve varios widgets en una fila horizontal DENTRO de un QWidget
    contenedor (no un QLayout suelto). Pasarle un QLayout pelado a
    QFormLayout.addRow() como campo hace que Qt calcule mal el alto de esa
    fila y de la siguiente, y terminan superpuestas — se notaba apenas el
    zoom no estaba en exactamente 100%."""
    contenedor = QWidget()
    h = QHBoxLayout(contenedor)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(8)
    for w in widgets:
        h.addWidget(w)
    return contenedor
