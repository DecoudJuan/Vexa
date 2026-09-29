"""Helpers de animación reutilizables de la UI."""

from PySide6.QtWidgets import (
    QFrame, QTabWidget, QTableWidget, QGraphicsOpacityEffect, QWidget,
)
from PySide6.QtCore import Qt, QEvent, QRect, QPropertyAnimation, QEasingCurve


class TabUnderline(QFrame):
    """Barra fina que se desliza bajo la solapa activa de un QTabWidget.

    Reemplaza el subrayado estático del CSS por uno que se anima de una solapa a
    otra. El color lo pone el stylesheet global (`QFrame#tab_underline` → accent),
    así acompaña al tema sin código extra."""

    def __init__(self, tabs: QTabWidget, thickness: int = 2):
        bar = tabs.tabBar()
        super().__init__(bar)
        self._tabs = tabs
        self._bar = bar
        self._thickness = thickness
        self._anim: QPropertyAnimation | None = None
        self.setObjectName("tab_underline")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        tabs.currentChanged.connect(lambda _=None: self._reposition(animate=True))
        bar.installEventFilter(self)
        self._reposition(animate=False)

    def _target(self) -> QRect:
        r = self._bar.tabRect(self._tabs.currentIndex())
        if r.isNull() or r.width() == 0:
            return self.geometry()
        return QRect(r.x(), self._bar.height() - self._thickness, r.width(), self._thickness)

    def _reposition(self, animate: bool) -> None:
        target = self._target()
        if animate and self.isVisible() and self.width() > 0:
            self._anim = QPropertyAnimation(self, b"geometry", self)
            self._anim.setDuration(240)
            self._anim.setStartValue(self.geometry())
            self._anim.setEndValue(target)
            self._anim.setEasingCurve(QEasingCurve.OutCubic)
            self._anim.start()
        else:
            self.setGeometry(target)
        self.raise_()

    def eventFilter(self, obj, e):  # noqa: N802
        # Cuando la barra se re-dispone (mostrar, redimensionar, cambio de zoom)
        # hay que recolocar el subrayado sin animar (salto directo).
        if obj is self._bar and e.type() in (
            QEvent.Resize, QEvent.Show, QEvent.LayoutRequest,
        ):
            self._reposition(animate=False)
        return False


def fade_in(widget: QWidget, duration: int = 160) -> QPropertyAnimation:
    """Aparición suave de un widget (opacidad 0 → 1). El efecto se retira al
    terminar para no dejar overhead ni afectar el repintado."""
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    anim.start()
    return anim


class ListTable(QTableWidget):
    """Tabla base de TODAS las listas (clientes/productos/facturas/etiquetas).

    Es un QTableWidget estándar: la selección la pinta Qt con el stylesheet
    (`QTableWidget::item:selected` en styles.py). Antes había un delegate propio
    + una banda animada detrás del texto para tapar la selección violeta del
    estilo nativo; al cambiar rápido de fila o arrastrar, la banda quedaba
    pintada sobre varias filas. Con el estilo Fusion (main.py) ya no hace falta."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAlternatingRowColors(False)
        self.setShowGrid(False)
        self.setFocusPolicy(Qt.NoFocus)
        # Barra vertical invisible (se scrollea con la rueda); pedido del usuario.
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
