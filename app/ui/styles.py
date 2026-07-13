import re

from utils.resources import resource_path

_TEMPLATE = """
/* =====================================================================
   BASE
   ===================================================================== */
QMainWindow, QDialog {{
    background-color: {base};
}}

QWidget {{
    background-color: {base};
    color: {text};
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 13px;
}}

/* =====================================================================
   TABS (ej. Facturas / Presupuestos / Albaranes / Pedidos / Abonos)
   Se estilan explícitamente porque el look nativo de Windows para pestañas
   no tiene suficiente contraste con nuestra paleta (se veían casi
   invisibles en modo claro).
   ===================================================================== */
QTabWidget::pane {{
    border: none;
    background: transparent;
}}

QTabBar {{
    background: transparent;
}}

QTabBar::tab {{
    background: transparent;
    color: {subtext};
    padding: 10px 18px;
    margin-right: 2px;
    border: none;
    border-bottom: 2px solid transparent;
    font-weight: 600;
}}

QTabBar::tab:hover {{
    color: {text};
}}

QTabBar::tab:selected {{
    color: {accent};
    border-bottom: 2px solid {accent};
}}

/* =====================================================================
   SIDEBAR
   ===================================================================== */
QFrame#sidebar {{
    background-color: {crust};
    border-right: 1px solid {line};
}}

QLabel#brand_name {{
    font-size: 20px;
    font-weight: 700;
    color: {accent};
    letter-spacing: 0.5px;
    background: transparent;
}}

QLabel#brand_sub {{
    font-size: 10px;
    color: {subtext};
    letter-spacing: 2px;
    background: transparent;
}}

QFrame#sidebar_sep {{
    background-color: {line};
    border: none;
    max-height: 1px;
}}

QLabel#version_label {{
    color: {muted2};
    font-size: 11px;
    background: transparent;
}}

QPushButton#nav_button {{
    background-color: transparent;
    color: {muted1};
    border: none;
    border-radius: 8px;
    text-align: left;
    padding: 0px 10px;
    font-size: 13px;
}}

QPushButton#nav_button:hover {{
    background-color: {base};
    color: {text};
}}

QPushButton#nav_button:checked {{
    background-color: rgba({accent_rgb}, 0.12);
    color: {accent};
    font-weight: 600;
}}

/* =====================================================================
   ZOOM / THEME TOOLBAR (sidebar footer)
   ===================================================================== */
QPushButton#zoom_button {{
    background-color: transparent;
    color: {muted1};
    border: 1px solid {line};
    border-radius: 6px;
    font-weight: 700;
    font-size: 13px;
    padding: 0px;
    min-height: 26px;
    max-height: 26px;
    min-width: 28px;
    max-width: 28px;
}}

QPushButton#zoom_button:hover {{
    background-color: {line};
    color: {text};
}}

QLabel#zoom_label {{
    color: {muted1};
    font-size: 10px;
    background: transparent;
}}

QPushButton#theme_button {{
    background-color: transparent;
    border: 1px solid {line};
    border-radius: 6px;
    padding: 0px;
    min-height: 26px;
    max-height: 26px;
    min-width: 30px;
    max-width: 30px;
}}

QPushButton#theme_button:hover {{
    background-color: {line};
    color: {text};
}}

/* =====================================================================
   SCROLL AREAS
   ===================================================================== */
QScrollArea {{
    border: none;
    background: transparent;
}}

QScrollArea > QWidget > QWidget {{
    background: transparent;
}}

/* =====================================================================
   CONVERSION BANNER (Documentos: "generar factura desde presupuesto", etc.)
   ===================================================================== */
QLabel#conversion_banner {{
    background-color: rgba({accent_rgb}, 0.12);
    border: 1px solid rgba({accent_rgb}, 0.4);
    border-radius: 8px;
    padding: 10px 14px;
    color: {text};
    font-weight: 600;
}}

/* =====================================================================
   TYPOGRAPHY — dynamic property [role="..."]
   ===================================================================== */
QLabel[role="page-title"] {{
    font-size: 22px;
    font-weight: 700;
    color: {text};
    background: transparent;
}}

QLabel[role="page-subtitle"] {{
    font-size: 12px;
    color: {subtext};
    background: transparent;
}}

QLabel[role="form-section"] {{
    font-size: 10px;
    font-weight: 700;
    color: {muted1};
    letter-spacing: 1px;
    background: transparent;
    padding-top: 4px;
}}

QLabel[role="card-title"] {{
    font-size: 10px;
    font-weight: 700;
    color: {muted1};
    letter-spacing: 1px;
    background: transparent;
}}

QLabel[role="card-value"] {{
    font-size: 24px;
    font-weight: 700;
    color: {text};
    background: transparent;
}}

QLabel[role="card-subtitle"] {{
    font-size: 11px;
    color: {muted1};
    background: transparent;
}}

QLabel[role="placeholder-title"] {{
    font-size: 18px;
    font-weight: 600;
    color: {muted2};
    background: transparent;
}}

QLabel[role="placeholder-sub"] {{
    font-size: 13px;
    color: {line};
    background: transparent;
}}

/* =====================================================================
   METRIC CARDS
   ===================================================================== */
QFrame#metric_card {{
    background-color: {surface};
    border: 1px solid {line};
    border-radius: 12px;
}}

QFrame#chart_card {{
    background-color: {surface};
    border: 1px solid {line};
    border-radius: 12px;
}}

/* =====================================================================
   TABLE
   ===================================================================== */
QTableWidget {{
    background-color: {surface};
    border: 1px solid {line};
    border-radius: 8px;
    gridline-color: transparent;
    outline: none;
    selection-background-color: transparent;
}}

QTableWidget::item {{
    padding: 0px 12px;
    border: none;
    color: {text};
    border-bottom: 1px solid {base};
}}

QTableWidget::item:alternate {{
    background-color: {base};
}}

/* Va DESPUÉS de :alternate a propósito: en Qt, cuando una fila alternada
   además está seleccionada, gana la regla declarada más abajo. Si :selected
   fuera la primera, la selección quedaba invisible en las filas alternadas
   (parecía que el click "no hacía nada" en esas filas). */
QTableWidget::item:selected,
QTableWidget::item:alternate:selected {{
    background-color: rgba({accent_rgb}, 0.14);
    color: {text};
    border-left: 3px solid {accent};
}}

QHeaderView {{
    background-color: {crust};
    border: none;
}}

QHeaderView::section {{
    background-color: {crust};
    color: {subtext};
    padding: 10px 12px;
    border: none;
    border-bottom: 1px solid {line};
    font-weight: 700;
    font-size: 10px;
    letter-spacing: 0.5px;
}}

/* =====================================================================
   BUTTONS
   ===================================================================== */
QPushButton {{
    background-color: {accent};
    color: {accent_text};
    border: none;
    border-radius: 8px;
    padding: 8px 18px;
    font-weight: 700;
    font-size: 13px;
    min-height: 34px;
}}

/* Chips de filtro rápido (Todos / Abiertos / Facturados) */
QPushButton#chipfilter {{
    background-color: transparent;
    color: {subtext};
    border: 1px solid {line};
    border-radius: 999px;
    padding: 6px 14px;
    font-weight: 600;
    font-size: 12px;
    min-height: 0px;
}}
QPushButton#chipfilter:hover {{
    color: {text};
    border-color: {muted2};
}}
QPushButton#chipfilter:checked {{
    background-color: rgba({accent_rgb}, 0.14);
    border-color: transparent;
    color: {accent};
    font-weight: 700;
}}

QPushButton:hover {{
    background-color: {accent_hover};
}}

QPushButton:pressed {{
    background-color: {accent_pressed};
}}

QPushButton:disabled {{
    background-color: {disabled_bg};
    color: {muted2};
}}

QPushButton#btn_secondary {{
    background-color: {line};
    color: {text};
    border: 1px solid {muted2};
}}

QPushButton#btn_secondary:hover {{
    background-color: {muted2};
    border-color: {muted1};
}}

QPushButton#btn_secondary:pressed {{
    background-color: {line};
}}

QPushButton#btn_secondary:disabled {{
    background-color: {base};
    color: {muted2};
    border-color: {line};
}}

QPushButton#btn_danger {{
    background-color: transparent;
    color: {danger};
    border: 1px solid rgba({danger_rgb}, 0.3);
}}

QPushButton#btn_danger:hover {{
    background-color: rgba({danger_rgb}, 0.1);
    border-color: rgba({danger_rgb}, 0.6);
}}

QPushButton#btn_danger:pressed {{
    background-color: rgba({danger_rgb}, 0.2);
}}

QPushButton#btn_danger:disabled {{
    color: {muted2};
    border-color: {line};
    background-color: transparent;
}}

/* =====================================================================
   LINE EDIT
   ===================================================================== */
QLineEdit {{
    background-color: {surface};
    border: 1px solid {line};
    border-radius: 8px;
    padding: 8px 12px;
    color: {text};
    selection-background-color: rgba({accent_rgb}, 0.3);
    min-height: 34px;
}}

QLineEdit:focus {{
    border-color: {accent};
}}

QLineEdit:disabled {{
    background-color: {base};
    color: {muted2};
}}

QLineEdit::placeholder {{
    color: {muted2};
}}

/* =====================================================================
   TEXT EDIT
   ===================================================================== */
QTextEdit {{
    background-color: {surface};
    border: 1px solid {line};
    border-radius: 8px;
    padding: 8px 12px;
    color: {text};
    selection-background-color: rgba({accent_rgb}, 0.3);
}}

QTextEdit:focus {{
    border-color: {accent};
}}

/* =====================================================================
   SPINBOXES
   ===================================================================== */
QSpinBox, QDoubleSpinBox {{
    background-color: {surface};
    border: 1px solid {line};
    border-radius: 8px;
    padding: 8px 12px;
    color: {text};
    min-height: 34px;
}}

QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {accent};
}}

QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 22px;
    height: 17px;
    border-left: 1px solid {line};
    border-bottom: 1px solid {line};
    border-top-right-radius: 7px;
    background-color: {line};
}}

QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 22px;
    height: 17px;
    border-left: 1px solid {line};
    border-bottom-right-radius: 7px;
    background-color: {line};
}}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {muted2};
}}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow,
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: none;
    width: 0px;
    height: 0px;
}}

/* =====================================================================
   COMBOBOX
   ===================================================================== */
QComboBox {{
    background-color: {surface};
    border: 1px solid {line};
    border-radius: 8px;
    padding: 8px 12px;
    color: {text};
    min-height: 34px;
}}

QComboBox:focus {{
    border-color: {accent};
}}

QComboBox::drop-down {{
    border: none;
    background-color: {surface};
    width: 28px;
}}

QComboBox::down-arrow {{
    image: url({chevron});
    width: 13px;
    height: 13px;
}}

QComboBox QAbstractItemView {{
    background-color: {surface};
    border: 1px solid {muted2};
    border-radius: 6px;
    selection-background-color: {line};
    selection-color: {text};
    color: {text};
    padding: 4px;
    outline: none;
}}

/* =====================================================================
   DATE EDIT
   ===================================================================== */
QDateEdit {{
    background-color: {surface};
    border: 1px solid {line};
    border-radius: 8px;
    padding: 8px 12px;
    color: {text};
    min-height: 34px;
}}

QDateEdit:focus {{
    border-color: {accent};
}}

QDateEdit::drop-down {{
    subcontrol-origin: border;
    subcontrol-position: center right;
    width: 28px;
    border-left: none;
    background-color: {surface};
}}

QDateEdit::down-arrow {{
    image: url({chevron});
    width: 13px;
    height: 13px;
}}

/* =====================================================================
   CALENDAR
   ===================================================================== */
QCalendarWidget {{
    background-color: {surface};
    border: 1px solid {line};
    border-radius: 8px;
}}

QCalendarWidget QWidget {{
    background-color: {surface};
    color: {text};
    alternate-background-color: {base};
}}

QCalendarWidget QAbstractItemView {{
    background-color: {surface};
    color: {text};
    selection-background-color: {accent};
    selection-color: {accent_text};
    outline: none;
}}

QCalendarWidget QToolButton {{
    background-color: transparent;
    color: {text};
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
}}

QCalendarWidget QToolButton:hover {{
    background-color: {line};
}}

QCalendarWidget QToolButton::menu-indicator {{
    image: none;
}}

QCalendarWidget #qt_calendar_navigationbar {{
    background-color: {crust};
    border-bottom: 1px solid {line};
    padding: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}}

QCalendarWidget #qt_calendar_prevmonth,
QCalendarWidget #qt_calendar_nextmonth {{
    color: {muted1};
    border: none;
    background: transparent;
    padding: 4px;
}}

QCalendarWidget #qt_calendar_prevmonth:hover,
QCalendarWidget #qt_calendar_nextmonth:hover {{
    background-color: {line};
    border-radius: 4px;
}}

/* =====================================================================
   SCROLLBARS
   ===================================================================== */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {line};
    border-radius: 4px;
    min-height: 24px;
}}

QScrollBar::handle:vertical:hover {{
    background: {muted2};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background: transparent;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background: {line};
    border-radius: 4px;
    min-width: 24px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {muted2};
}}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* =====================================================================
   DIALOG
   ===================================================================== */
QDialog {{
    background-color: {base};
}}

/* =====================================================================
   MESSAGE BOX
   ===================================================================== */
QMessageBox {{
    background-color: {base};
}}

QMessageBox QLabel {{
    color: {text};
    background: transparent;
}}

QMessageBox QPushButton {{
    min-width: 88px;
}}

/* =====================================================================
   STATUS BAR
   ===================================================================== */
QStatusBar {{
    background-color: {crust};
    color: {muted2};
    border-top: 1px solid {line};
    font-size: 11px;
}}

QStatusBar QLabel {{
    background: transparent;
    color: {muted2};
    padding: 0 8px;
}}

/* =====================================================================
   TOOLTIP
   ===================================================================== */
QToolTip {{
    background-color: {line};
    color: {text};
    border: 1px solid {muted2};
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 12px;
}}

/* =====================================================================
   FORM LABEL (inside QFormLayout)
   ===================================================================== */
QFormLayout QLabel {{
    color: {subtext};
    background: transparent;
}}
"""

# Catppuccin Mocha (dark) / Catppuccin Latte (light) inspired palettes.
# Every color used anywhere in the stylesheet is a named token here, so the
# two themes are guaranteed to cover exactly the same selectors.
_PALETTES = {
    "dark": {
        "base": "#1e1e2e",
        "crust": "#11111b",
        "surface": "#181825",
        "line": "#313244",
        "muted2": "#45475a",
        "muted1": "#6c7086",
        "subtext": "#a6adc8",
        "text": "#cdd6f4",
        "accent": "#89b4fa",
        "accent_hover": "#b4d0ff",
        "accent_pressed": "#74a8f5",
        "accent_text": "#11111b",
        "accent_rgb": "137, 180, 250",
        "select_bg": "#34406a",
        "select_tx": "#cdd6f4",
        "danger": "#f38ba8",
        "danger_rgb": "243, 139, 168",
        "warn": "#f9e2af",
        "warn_rgb": "249, 226, 175",
        "ok": "#a6e3a1",
        "ok_rgb": "166, 227, 161",
        "disabled_bg": "#24273a",
    },
    "light": {
        "base": "#eff1f5",
        "crust": "#dce0e8",
        "surface": "#ffffff",
        "line": "#ccd0da",
        "muted2": "#9ca0b0",
        "muted1": "#6c6f85",
        "subtext": "#5c5f77",
        "text": "#3c3f58",
        "accent": "#1e66f5",
        "accent_hover": "#4885f7",
        "accent_pressed": "#1755c9",
        "accent_text": "#ffffff",
        "accent_rgb": "30, 102, 245",
        "select_bg": "#dbe6fd",
        "select_tx": "#3c3f58",
        "danger": "#d20f39",
        "danger_rgb": "210, 15, 57",
        "warn": "#df8e1d",
        "warn_rgb": "223, 142, 29",
        "ok": "#40a02b",
        "ok_rgb": "64, 160, 43",
        "disabled_bg": "#dce0e8",
    },
}

# El zoom escala SOLO estas propiedades (tamaño de texto y de los
# contenedores que lo alojan). Deliberadamente NO tocamos declaraciones
# border-* (border, border-left, border-top, ...): varias de ellas dibujan
# las flechitas de QComboBox/QDateEdit con el truco de "borde ancho +
# transparente" (triángulo), y escalarlas de forma genérica por magnitud
# rompía ese truco (se veía una caja gris sin flecha en vez del triángulo).
# Dejar esos bordes con su tamaño fijo es seguro: son íconos decorativos
# chicos, no necesitan crecer para seguir siendo legibles ni clickeables.
_SCALABLE_PROPS = (
    "font-size", "min-height", "max-height", "min-width", "max-width",
    "padding", "border-radius", "width", "height",
)
_PROP_RE = re.compile(
    r"(?<![\w-])(" + "|".join(_SCALABLE_PROPS) + r")(\s*:\s*)([^;{}]+)(;)"
)
_PX_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)px")


def _scale_px_numbers(text: str, zoom: float) -> str:
    return _PX_NUM_RE.sub(
        lambda m: f"{max(1, round(float(m.group(1)) * zoom))}px", text
    )


def build_style(theme: str = "dark", zoom: float = 1.0) -> str:
    """Genera la hoja de estilos completa para el tema ('dark'/'light') y
    nivel de zoom dado (1.0 = 100%). El zoom escala tamaños de fuente y
    también las dimensiones de los controles (alto mínimo, padding, radios),
    para que el texto más grande siga entrando bien en botones/campos."""
    palette = _PALETTES.get(theme, _PALETTES["dark"])
    chevron = resource_path("assets/chevron.png").as_posix()
    css = _TEMPLATE.format(**palette, chevron=chevron)
    if zoom and abs(zoom - 1.0) > 1e-6:
        css = _PROP_RE.sub(
            lambda m: m.group(1) + m.group(2) + _scale_px_numbers(m.group(3), zoom) + m.group(4),
            css,
        )
    return css


def get_palette(theme: str = "dark") -> dict:
    """Paleta de colores del tema, para que los íconos (que no son parte
    del stylesheet, se pintan aparte como QIcon) usen exactamente los
    mismos colores que el resto de la interfaz en vez de valores propios
    hardcodeados que solo tenían sentido en modo oscuro."""
    return _PALETTES.get(theme, _PALETTES["dark"])


def build_qpalette(theme: str = "dark"):
    """QPalette del tema para aplicar a la QApplication.

    Imprescindible además del stylesheet: los popups de autocompletado
    (QCompleter) y otras vistas de items dibujan su texto con la QPalette
    (roles Text/HighlightedText), NO con la propiedad `color` del CSS. Si no
    se fija la paleta, en Windows con tema claro del sistema el texto sale
    oscuro sobre nuestro fondo oscuro y queda invisible (bug que no aparece
    en equipos con el tema del sistema en oscuro)."""
    from PySide6.QtGui import QPalette, QColor

    p = _PALETTES.get(theme, _PALETTES["dark"])
    c = QColor
    pal = QPalette()
    pal.setColor(QPalette.Window, c(p["base"]))
    pal.setColor(QPalette.WindowText, c(p["text"]))
    pal.setColor(QPalette.Base, c(p["surface"]))
    pal.setColor(QPalette.AlternateBase, c(p["base"]))
    pal.setColor(QPalette.Text, c(p["text"]))
    pal.setColor(QPalette.Button, c(p["surface"]))
    pal.setColor(QPalette.ButtonText, c(p["text"]))
    pal.setColor(QPalette.ToolTipBase, c(p["line"]))
    pal.setColor(QPalette.ToolTipText, c(p["text"]))
    pal.setColor(QPalette.PlaceholderText, c(p["muted2"]))
    pal.setColor(QPalette.BrightText, c(p["danger"]))
    # Selección tenue (no el accent pleno): el azul saturado en filas/listas
    # resultaba agresivo al clickear clientes/productos.
    pal.setColor(QPalette.Highlight, c(p["select_bg"]))
    pal.setColor(QPalette.HighlightedText, c(p["select_tx"]))
    for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, c(p["muted2"]))
    return pal


# Compatibilidad con código existente que importaba el estilo oscuro fijo.
APP_STYLE = build_style("dark", 1.0)
