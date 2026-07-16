"""Helpers de animación reutilizables de la UI."""

from PySide6.QtWidgets import (
    QFrame, QTabWidget, QTableWidget, QGraphicsOpacityEffect, QWidget,
    QStyledItemDelegate,
)
from PySide6.QtCore import (
    Qt, QEvent, QRect, QPropertyAnimation, QEasingCurve, QAbstractAnimation,
    Property,
)
from PySide6.QtGui import QColor, QPalette


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


class _CleanItemDelegate(QStyledItemDelegate):
    """Pinta cada celda por completo: primero el fondo del resaltado (si la celda
    cae dentro de la banda celeste animada de la tabla) y después SOLO el texto.

    No llama al pintado por defecto de Qt, así no se dibuja ninguna decoración de
    selección/foco/grilla (que aparecía como líneas verticales violetas en los
    bordes de columna). Como cada celda rellena su ancho completo, las celdas
    contiguas se tocan y el celeste queda continuo, sin líneas entre columnas.
    El texto va encima del celeste (no lo tapa)."""

    _PAD = 12  # coincide con el padding del CSS (QTableWidget::item)

    def paint(self, painter, option, index):  # noqa: N802
        painter.save()
        view = self.parent()
        band = getattr(view, "_hl_rect", None)
        color = getattr(view, "_hl_color", None)
        if band is not None and not band.isNull() and color is not None and color.alpha() > 0:
            inter = option.rect.intersected(band)
            if not inter.isEmpty():
                painter.fillRect(inter, color)
        text = index.data(Qt.DisplayRole)
        if text:
            font = index.data(Qt.FontRole)
            if font is not None:
                painter.setFont(font)
            fg = index.data(Qt.ForegroundRole)
            painter.setPen(fg.color() if fg is not None else option.palette.color(QPalette.Text))
            align = index.data(Qt.TextAlignmentRole)
            align = int(align) if align is not None else int(Qt.AlignLeft | Qt.AlignVCenter)
            rect = option.rect.adjusted(self._PAD, 0, -self._PAD, 0)
            if view is not None and view.wordWrap():
                # Respeta el ajuste de línea (ej. nombres largos en Etiquetas).
                painter.drawText(rect, align | int(Qt.TextWordWrap), str(text))
            else:
                elided = painter.fontMetrics().elidedText(str(text), Qt.ElideRight, rect.width())
                painter.drawText(rect, align, elided)
        painter.restore()


class AnimatedTable(QTableWidget):
    """QTableWidget con el resaltado de selección dibujado DETRÁS del texto (no
    un overlay por encima) que se desliza de una fila a otra.

    Al pintarse por debajo del texto, el celeste es SIEMPRE el mismo tono suave
    —igual al deslizar que en reposo— y nunca tapa el texto. Reemplaza al viejo
    overlay translúcido (que se veía gris o, si era opaco, tapaba el texto) y al
    resaltado del CSS. Es el componente ÚNICO de todas las listas de la app
    (clientes/productos/facturas/etiquetas): cambiar el color/duración/redondeo
    acá afecta a todas por igual."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._hl_rect = QRect()
        self._hl_color = QColor(0, 0, 0, 0)
        self._hl_anim: QPropertyAnimation | None = None
        self.setAlternatingRowColors(False)
        self.setShowGrid(False)
        self.setGridStyle(Qt.NoPen)
        self.setItemDelegate(_CleanItemDelegate(self))
        self.setFocusPolicy(Qt.NoFocus)
        # Barra vertical invisible (se scrollea con la rueda); pedido del usuario.
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # El fondo de selección de Qt usa el color de acento del SISTEMA (violeta
        # en esta PC) y se dibujaba como líneas en los bordes de columna. Lo
        # anulamos poniéndolo transparente; el celeste lo pinta el delegate.
        pal = self.palette()
        pal.setColor(QPalette.Highlight, QColor(0, 0, 0, 0))
        self.setPalette(pal)
        self.selectionModel().selectionChanged.connect(self._on_sel_changed)
        self.verticalScrollBar().valueChanged.connect(self._snap)

    def set_highlight_color(self, color) -> None:
        """Color (sólido) del resaltado. Se pasa el celeste suave de la paleta
        (`row_sel`); al ir detrás del texto, sólido no lo tapa."""
        self._hl_color = QColor(color)
        self.viewport().update()

    def _get_hl(self) -> QRect:
        return self._hl_rect

    def _set_hl(self, r: QRect) -> None:
        self._hl_rect = r
        self.viewport().update()

    # Propiedad animable por QPropertyAnimation (interpola el QRect).
    highlightRect = Property(QRect, _get_hl, _set_hl)

    def _row_rect(self, row: int) -> QRect:
        if row is None or row < 0:
            return QRect()
        r = self.visualRect(self.model().index(row, 0))
        if r.height() <= 0:
            return QRect()
        # Ancho completo del viewport, sin inset lateral: así las celdas rellenan
        # borde a borde y el celeste queda continuo (sin gaps entre columnas).
        return QRect(0, r.y(), self.viewport().width(), r.height())

    def _on_sel_changed(self, selected, deselected) -> None:
        new = self._row_rect(self.currentRow())
        if new.isNull():
            self._stop()
            self._set_hl(QRect())
            return
        old_idx = deselected.indexes()
        old = self._row_rect(old_idx[0].row()) if old_idx else QRect()
        self._stop()
        if not old.isNull() and old != new:
            # La banda arranca cubriendo old+new (unión) y se "retrae" hasta new.
            # Así la fila nueva queda tapada por el celeste DESDE el primer frame
            # (mismo repintado en que Qt dibujaría su selección violeta), y esa
            # violeta nunca llega a verse. Igual hay movimiento (el celeste se
            # desliza desde la fila anterior hacia la nueva).
            start = old.united(new)
            self._set_hl(start)
            self._hl_anim = QPropertyAnimation(self, b"highlightRect", self)
            self._hl_anim.setDuration(220)
            self._hl_anim.setStartValue(start)
            self._hl_anim.setEndValue(new)
            self._hl_anim.setEasingCurve(QEasingCurve.OutCubic)
            self._hl_anim.start()
        else:
            self._set_hl(new)

    def _snap(self) -> None:
        # Al hacer scroll, seguir a la fila seleccionada (sin pelear con la anim).
        if self._hl_anim is not None and self._hl_anim.state() == QAbstractAnimation.Running:
            return
        self._set_hl(self._row_rect(self.currentRow()))

    def _stop(self) -> None:
        if self._hl_anim is not None:
            self._hl_anim.stop()
            self._hl_anim = None
