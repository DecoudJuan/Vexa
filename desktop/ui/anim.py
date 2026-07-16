"""Helpers de animación reutilizables de la UI."""

from PySide6.QtWidgets import (
    QFrame, QTabWidget, QTableWidget, QGraphicsOpacityEffect, QWidget,
)
from PySide6.QtCore import Qt, QEvent, QRect, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor


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


class RowHighlight(QFrame):
    """Da la sensación de que el resaltado de fila "se desliza" de una a otra.

    El resaltado en reposo lo dibuja el CSS (sólido, legible). Este overlay solo
    aparece DURANTE el cambio de selección: arranca sobre la fila anterior, se
    desliza hasta la nueva y se oculta, dejando el resaltado del CSS. Así no
    atenúa el texto en reposo ni revela separadores de columna."""

    def __init__(self, table: QTableWidget, pal: dict):
        super().__init__(table.viewport())
        self._table = table
        self._anim: QPropertyAnimation | None = None
        self.setObjectName("row_highlight")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.set_palette(pal)
        self.hide()
        table.selectionModel().selectionChanged.connect(self._on_selection_changed)

    def set_palette(self, pal: dict) -> None:
        # Translúcido para NO tapar el texto mientras el bar se desliza, pero con
        # el celeste más saturado (`row_sel_bar`, no el `row_sel` casi blanco):
        # así el deslizamiento se lee claramente en celeste y no como un gris.
        # En reposo el resaltado lo dibuja el CSS (sólido, bajo el texto).
        c = QColor(pal["row_sel_bar"])
        self.setStyleSheet(
            f"#row_highlight {{ background-color: rgba({c.red()},{c.green()},{c.blue()},0.5);"
            f" border: none; border-radius: 6px; }}"
        )

    def _rect_for(self, index) -> QRect | None:
        r = self._table.visualRect(index)
        if r.height() <= 0:
            return None
        vp = self._table.viewport()
        return QRect(0, r.y(), vp.width(), r.height())

    def _on_selection_changed(self, selected, deselected) -> None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            self._stop()
            self.hide()
            return
        new_rect = self._rect_for(rows[0])
        old_idx = deselected.indexes()
        # Sin fila anterior (primera selección, o repoblado): lo muestra el CSS.
        if new_rect is None or not old_idx:
            self._stop()
            self.hide()
            return
        old_rect = self._rect_for(old_idx[0])
        if old_rect is None:
            self.hide()
            return
        self._stop()
        self.setGeometry(old_rect)
        self.show()
        self.raise_()
        self._anim = QPropertyAnimation(self, b"geometry", self)
        self._anim.setDuration(260)
        self._anim.setStartValue(old_rect)
        self._anim.setEndValue(new_rect)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.finished.connect(self.hide)
        self._anim.start()

    def _stop(self) -> None:
        if self._anim is not None:
            self._anim.stop()
            self._anim = None
