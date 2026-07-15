"""Modal base reutilizable: tarjeta flotante sin marco nativo con cabecera
azul, cuerpo blanco y pie con acciones. Es el mismo lenguaje visual del
formulario de factura (DocumentoDialog), extraído para que TODOS los
diálogos de la app (producto, cliente, IVA, forma de pago) se vean igual.

Uso:
    class MiDialogo(BaseModal):
        def __init__(self, parent=None):
            super().__init__("Título", "subtítulo", icon="user", width=480, parent=parent)
            self.content.addWidget(self.section_label("NOMBRE *", "user"))
            self._campo = QLineEdit(); self._campo.setObjectName("field")
            self.content.addWidget(self._campo)
            self.set_primary_action("Guardar", self._accept)
"""

import re

from PySide6.QtWidgets import (
    QDialog, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget,
    QGraphicsDropShadowEffect, QScrollArea, QApplication,
)
from PySide6.QtCore import (
    Qt, QPoint, QRect, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup,
)
from PySide6.QtGui import QColor

from ui.icons import svg_icon, svg_pixmap
from utils.resources import resource_path

_PX_RE = re.compile(r"(\d+)px")


def _scale_px(css: str, zoom: float) -> str:
    """Escala los valores en px del QSS por el zoom, para que padding, radios y
    tipografías acompañen a los tamaños que el código fija con _S()."""
    if abs(zoom - 1.0) <= 1e-6:
        return css
    return _PX_RE.sub(lambda m: f"{max(1, round(int(m.group(1)) * zoom))}px", css)

# Paletas del modal por tema. La cabecera y el botón Guardar quedan azules
# (identidad) en ambos temas; el resto acompaña al tema oscuro/claro de la app.
_MODAL_THEMES = {
    "light": {
        "card": "#ffffff", "body": "#ffffff", "ink": "#2f3345", "muted": "#8a90a2",
        "field": "#f4f6fb", "border": "#e3e6ef", "focus": "#2f6df6",
        "badge_bg": "#e8f0fe", "badge_tx": "#2456d8", "footer_border": "#edeef3",
        "cancel_tx": "#6b7180", "cancel_hover": "#f2f3f7", "list_sel": "#e8f0fe",
        "sb_bg": "#ffffff", "sb_handle": "#dfe2ec", "sb_handle_h": "#c7ccda",
        "check_border": "#cfd4e0",
        # extras usados por el modal de factura (líneas/totales):
        "head_bg": "#eef3fe", "head_tx": "#4a5a86", "row_sep": "#f1f2f7",
        "accent_ink": "#2456d8", "del_hover": "#fdecef",
    },
    "dark": {
        "card": "#24273a", "body": "#24273a", "ink": "#cdd6f4", "muted": "#8087a0",
        "field": "#1a1b2a", "border": "#363a52", "focus": "#89b4fa",
        "badge_bg": "rgba(137,180,250,0.16)", "badge_tx": "#b4c4f5", "footer_border": "#363a52",
        "cancel_tx": "#a6adc8", "cancel_hover": "#313244", "list_sel": "#34406a",
        "sb_bg": "#24273a", "sb_handle": "#45475a", "sb_handle_h": "#585b70",
        "check_border": "#45475a",
        "head_bg": "#2c3350", "head_tx": "#b4c4f5", "row_sep": "#2f3348",
        "accent_ink": "#89b4fa", "del_hover": "rgba(243,139,168,0.16)",
    },
}

_MODAL_TEMPLATE = """
QDialog { background: transparent; }

#modal_root { background: %CARD%; border-radius: 16px; }

#modal_header {
    background: #2f6df6;
    border-top-left-radius: 16px;
    border-top-right-radius: 16px;
}
#modal_title { color: #ffffff; font-size: 16px; font-weight: 700; }
#modal_subtitle { color: rgba(255,255,255,0.82); font-size: 12px; }
#modal_close { background: transparent; border: none; border-radius: 8px; }
#modal_close:hover { background: rgba(255,255,255,0.22); }

#modal_scroll { background: %BODY%; border: none; }
#modal_body { background: %BODY%; }
QLabel { background: transparent; }
#section { background: transparent; }
#section_label { color: %MUTED%; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; }
#unit { color: %MUTED%; font-size: 13px; font-weight: 600; }
#hint { color: %MUTED%; font-size: 12px; }

#modal_body QLineEdit#field,
#modal_body QComboBox#field,
#modal_body QDateEdit#field,
#modal_body QSpinBox#field,
#modal_body QDoubleSpinBox#field {
    background: %FIELD%;
    border: 1px solid %BORDER%;
    border-radius: 9px;
    padding: 9px 12px;
    color: %INK%;
    font-size: 13.5px;
    min-height: 20px;
}
#modal_body QLineEdit#field:focus,
#modal_body QComboBox#field:focus,
#modal_body QDateEdit#field:focus {
    border: 1px solid %FOCUS%;
    background: %CARD%;
}
#modal_body QComboBox#field QLineEdit { background: transparent; border: none; padding: 0; color: %INK%; }
#modal_body QComboBox::drop-down, #modal_body QDateEdit::drop-down {
    border: none; background: transparent; width: 24px;
}
#modal_body QComboBox::down-arrow, #modal_body QDateEdit::down-arrow {
    image: url(%CHEVRON%); width: 13px; height: 13px;
}
#modal_body QComboBox QAbstractItemView {
    background: %CARD%; color: %INK%; border: 1px solid %BORDER%; border-radius: 8px;
    selection-background-color: %LIST_SEL%; selection-color: %INK%; outline: none; padding: 4px;
}

/* spinboxes: se ven como campos, sin las flechitas rotas */
#modal_body QSpinBox::up-button, #modal_body QSpinBox::down-button,
#modal_body QDoubleSpinBox::up-button, #modal_body QDoubleSpinBox::down-button { width: 0; height: 0; border: none; }

#modal_body QTextEdit#comments, #modal_body QTextEdit#field {
    background: %FIELD%; border: 1px solid %BORDER%; border-radius: 10px;
    color: %INK%; padding: 8px; font-size: 13.5px;
}
#modal_body QTextEdit#comments:focus, #modal_body QTextEdit#field:focus { border-color: %FOCUS%; background: %CARD%; }

#modal_body QListWidget {
    background: %FIELD%; border: 1px solid %BORDER%; border-radius: 9px; color: %INK%; padding: 2px;
}
#modal_body QListWidget::item { padding: 4px 6px; border-radius: 6px; }
#modal_body QListWidget::item:selected { background: %LIST_SEL%; color: %INK%; }

#modal_body QTableWidget {
    background: %FIELD%; border: 1px solid %BORDER%; border-radius: 9px;
    color: %INK%; gridline-color: transparent; outline: none;
}
#modal_body QTableWidget::item { padding: 3px 8px; border: none; color: %INK%; }
#modal_body QPushButton#btn_row_delete { background: transparent; border: none; border-radius: 6px; min-height: 0px; padding: 0px; }
#modal_body QPushButton#btn_row_delete:hover { background: %DEL_HOVER%; }

#modal_body QPushButton#btn_secondary {
    background: %CARD%; border: 1px solid %BORDER%; color: %INK%;
    border-radius: 8px; padding: 7px 12px; font-weight: 600; font-size: 13px;
}
#modal_body QPushButton#btn_secondary:hover { background: %FIELD%; border-color: %FOCUS%; }

#modal_body QCheckBox { color: %INK%; font-size: 13.5px; spacing: 8px; background: transparent; }
#modal_body QCheckBox::indicator {
    width: 18px; height: 18px; border: 1px solid %CHECK_BORDER%; border-radius: 5px; background: %CARD%;
}
#modal_body QCheckBox::indicator:checked { background: #2f6df6; border-color: #2f6df6; }

#doc_badge { background: %BADGE_BG%; color: %BADGE_TX%; font-weight: 800; font-size: 13.5px; border-radius: 9px; padding: 10px 12px; }
#doc_dash { color: %MUTED%; font-size: 15px; }

#modal_footer {
    background: %CARD%; border-top: 1px solid %FOOTER_BORDER%;
    border-bottom-left-radius: 16px; border-bottom-right-radius: 16px;
}
#btn_cancel {
    background: transparent; border: none; color: %CANCEL_TX%; font-weight: 600; font-size: 13px;
    padding: 9px 16px; border-radius: 8px;
}
#btn_cancel:hover { background: %CANCEL_HOVER%; color: %INK%; }
#btn_save {
    background: #2f6df6; border: none; color: #ffffff; font-weight: 700; font-size: 13px;
    padding: 9px 20px; border-radius: 9px; min-height: 20px;
}
#btn_save:hover { background: #2b62dd; }

QScrollBar:vertical { background: %SB_BG%; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: %SB_HANDLE%; border-radius: 4px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: %SB_HANDLE_H%; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: %SB_BG%; }
"""


def modal_colors(theme: str = "dark") -> dict:
    return _MODAL_THEMES.get(theme, _MODAL_THEMES["light"])


def build_modal_css(theme: str = "dark") -> str:
    css = _MODAL_TEMPLATE
    for key, value in modal_colors(theme).items():
        css = css.replace("%" + key.upper() + "%", value)
    css = css.replace("%CHEVRON%", resource_path("assets/chevron.png").as_posix())
    return css


class BaseModal(QDialog):
    def __init__(self, title, subtitle="", icon="file-invoice", width=520,
                 scroll=False, zoom=1.0, height=None, theme="dark",
                 scale_css=False, parent=None):
        super().__init__(parent)
        self._zoom = zoom
        self._theme = theme
        self._scale_css = scale_css
        self._drag_pos = None
        self._centered = False
        self._scroll = scroll

        self.setWindowTitle(title)
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # Tamaño responsivo: el px de diseño (× zoom) es el objetivo, pero nunca
        # más que un % de la pantalla disponible, así entra en cualquier monitor
        # (notebooks, pantallas chicas) sin salirse ni recortarse.
        avail = QApplication.primaryScreen().availableGeometry()
        self.setFixedWidth(min(self._S(width), int(avail.width() * 0.94)))
        if scroll:
            self.setFixedHeight(min(self._S(height or 720), int(avail.height() * 0.92)))

        self._build_chrome(title, subtitle, icon)
        css = build_modal_css(theme) + self.extra_css()
        self.setStyleSheet(_scale_px(css, self._zoom) if self._scale_css else css)

    # -------------------------------------------------------- helpers
    def _S(self, px) -> int:
        return max(1, round(px * self._zoom))

    def extra_css(self) -> str:
        """Reglas QSS adicionales del subdiálogo (opcional)."""
        return ""

    def section_label(self, text: str, icon_name: str) -> QWidget:
        w = QWidget()
        w.setObjectName("section")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(self._S(6))
        ic = QLabel()
        ic.setPixmap(svg_pixmap(icon_name, self._S(14), "#8a90a2"))
        lbl = QLabel(text)
        lbl.setObjectName("section_label")
        lay.addWidget(ic)
        lay.addWidget(lbl)
        lay.addStretch()
        return w

    def set_primary_action(self, text: str, slot) -> None:
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("btn_cancel")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        save = QPushButton(f"  {text}")
        save.setObjectName("btn_save")
        save.setIcon(svg_icon("check", self._S(15), "#ffffff"))
        save.setCursor(Qt.PointingHandCursor)
        save.setDefault(True)
        save.clicked.connect(slot)
        self._footer_row.addWidget(cancel)
        self._footer_row.addWidget(save)

    # -------------------------------------------------------- chrome
    def _build_chrome(self, title, subtitle, icon) -> None:
        outer = QVBoxLayout(self)
        m = self._S(18)
        outer.setContentsMargins(m, m, m, m)
        outer.setSpacing(0)

        root = QFrame()
        root.setObjectName("modal_root")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(self._S(46))
        shadow.setOffset(0, self._S(10))
        shadow.setColor(QColor(15, 23, 42, 90))
        root.setGraphicsEffect(shadow)
        outer.addWidget(root)

        rl = QVBoxLayout(root)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        rl.addWidget(self._build_header(title, subtitle, icon))

        self.content = QVBoxLayout()
        self.content.setContentsMargins(self._S(24), self._S(16), self._S(24), self._S(16))
        self.content.setSpacing(self._S(11))
        body = QFrame()
        body.setObjectName("modal_body")
        body.setLayout(self.content)

        if self._scroll:
            sc = QScrollArea()
            sc.setObjectName("modal_scroll")
            sc.setWidgetResizable(True)
            sc.setFrameShape(QFrame.NoFrame)
            sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            sc.setWidget(body)
            rl.addWidget(sc, 1)
        else:
            rl.addWidget(body, 1)

        rl.addWidget(self._build_footer())

    def _build_header(self, title, subtitle, icon) -> QFrame:
        header = QFrame()
        header.setObjectName("modal_header")
        h = QHBoxLayout(header)
        h.setContentsMargins(self._S(18), self._S(10), self._S(12), self._S(10))
        h.setSpacing(self._S(12))
        ic = QLabel()
        ic.setPixmap(svg_pixmap(icon, self._S(22), "#ffffff"))
        h.addWidget(ic, 0, Qt.AlignVCenter)
        texts = QVBoxLayout()
        texts.setSpacing(self._S(2))
        t = QLabel(title)
        t.setObjectName("modal_title")
        texts.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setObjectName("modal_subtitle")
            s.setWordWrap(True)
            texts.addWidget(s)
        h.addLayout(texts, 1)
        close = QPushButton()
        close.setObjectName("modal_close")
        close.setIcon(svg_icon("x", self._S(18), "#ffffff"))
        close.setFixedSize(self._S(30), self._S(30))
        close.setCursor(Qt.PointingHandCursor)
        close.clicked.connect(self.reject)
        h.addWidget(close, 0, Qt.AlignTop)
        self._header = header
        return header

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setObjectName("modal_footer")
        self._footer_row = QHBoxLayout(footer)
        self._footer_row.setContentsMargins(self._S(24), self._S(14), self._S(24), self._S(16))
        self._footer_row.setSpacing(self._S(10))
        self._footer_row.addStretch()
        return footer

    # ------------------------------------------------ arrastre / centrado
    def _header_rect(self) -> QRect:
        return QRect(self._header.mapTo(self, QPoint(0, 0)), self._header.size())

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._header_rect().contains(event.position().toPoint()):
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._centered:
            self._centered = True
            screen = self.screen() or QApplication.primaryScreen()
            avail = screen.availableGeometry()
            parent = self.parentWidget()
            center = parent.window().frameGeometry().center() if parent is not None else avail.center()
            geo = self.frameGeometry()
            geo.moveCenter(center)
            if geo.top() < avail.top():
                geo.moveTop(avail.top())
            self.move(geo.topLeft())
            self._animate_open(geo.topLeft())

    def _animate_open(self, final_pos: QPoint) -> None:
        """Aparición del modal: fade + un leve deslizamiento hacia arriba."""
        offset = self._S(14)
        start_pos = QPoint(final_pos.x(), final_pos.y() + offset)
        self.setWindowOpacity(0.0)
        self.move(start_pos)

        fade = QPropertyAnimation(self, b"windowOpacity", self)
        fade.setDuration(190)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)

        slide = QPropertyAnimation(self, b"pos", self)
        slide.setDuration(220)
        slide.setStartValue(start_pos)
        slide.setEndValue(final_pos)
        slide.setEasingCurve(QEasingCurve.OutCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(fade)
        group.addAnimation(slide)
        group.start()
        self._open_anim = group  # evita que lo recolecte el GC
