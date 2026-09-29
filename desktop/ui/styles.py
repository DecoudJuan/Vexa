import re

from resources import resource_path

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
   TABS (ej. Facturas / Presupuestos / Pedidos)
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
    /* El subrayado lo dibuja un indicador que se desliza (ui/anim.TabUnderline),
       no un borde estático, para animar el cambio de solapa. */
    border-bottom: 2px solid transparent;
}}

/* Indicador deslizante bajo la solapa activa. */
QFrame#tab_underline {{
    background-color: {accent};
    border: none;
    border-radius: 1px;
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
    color: {faint_tx};
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
    background-color: rgba({accent_rgb}, 0.06);
    color: {text};
}}

QPushButton#nav_button:checked {{
    /* El resaltado del ítem activo lo dibuja un indicador que se desliza
       (ver MainWindow._nav_indicator); acá sólo el color/negrita del texto. */
    background-color: transparent;
    color: {accent};
    font-weight: 600;
}}

/* Indicador deslizante del ítem activo de la sidebar. */
QFrame#nav_indicator {{
    background-color: rgba({accent_rgb}, 0.12);
    border: none;
    border-radius: 8px;
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
    color: {subtext};
    background: transparent;
}}

QLabel[role="placeholder-sub"] {{
    font-size: 13px;
    color: {muted1};
    background: transparent;
}}

/* Etiqueta de campo (arriba del input, estilo formulario moderno). */
QLabel[role="field-label"] {{
    font-size: 11px;
    font-weight: 600;
    color: {subtext};
    background: transparent;
}}

/* =====================================================================
   SECCIONES DE FORMULARIO (Configuración): banda con ícono + título
   ===================================================================== */
QFrame#form_section {{
    background-color: {surface};
    border: 1px solid {line};
    border-radius: 12px;
}}

QFrame#section_head {{
    background-color: rgba({accent_rgb}, 0.07);
    border: none;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
}}

QLabel[role="section-title"] {{
    font-size: 13px;
    font-weight: 700;
    color: {accent};
    background: transparent;
}}

/* Barra de búsqueda ancha de las listas (ícono adentro, a la izquierda). */
QLineEdit#search_input {{
    background-color: {surface};
    border: 1px solid {line};
    border-radius: 10px;
    padding: 10px 14px;
    min-height: 22px;
    font-size: 13.5px;
}}
QLineEdit#search_input:focus {{
    border-color: {accent};
}}

/* =====================================================================
   HOME / LANDING (tarjetas de acceso a las secciones)
   ===================================================================== */
QLabel#home_brand {{
    font-size: 30px;
    font-weight: 800;
    color: {accent};
    letter-spacing: 0.5px;
    background: transparent;
}}

QLabel#home_brand_sub {{
    font-size: 12px;
    color: {subtext};
    letter-spacing: 3px;
    background: transparent;
}}

QFrame#home_card {{
    background-color: {surface};
    border: 1px solid {line};
    border-radius: 16px;
}}

QFrame#home_card:hover {{
    border-color: {accent};
    background-color: rgba({accent_rgb}, 0.05);
}}

QLabel#home_icon_chip {{
    background-color: rgba({accent_rgb}, 0.12);
    border: none;
    border-radius: 18px;
}}

QLabel[role="home-title"] {{
    font-size: 16px;
    font-weight: 700;
    color: {text};
    background: transparent;
}}

QLabel[role="home-sub"] {{
    font-size: 12px;
    color: {subtext};
    background: transparent;
}}

/* =====================================================================
   DASHBOARD (sección Inicio): saludo + KPIs + facturas recientes + accesos
   ===================================================================== */
QLabel[role="dash-date"] {{
    font-size: 13px;
    font-weight: 700;
    color: {muted1};
    letter-spacing: 0.3px;
    background: transparent;
}}

QLabel[role="dash-greeting"] {{
    font-size: 30px;
    font-weight: 800;
    color: {text};
    background: transparent;
}}

/* Tarjeta KPI destacada (azul liso, sin degradé). */
QFrame#dash_hero {{
    background-color: {accent};
    border: none;
    border-radius: 16px;
}}
QFrame#dash_hero QLabel {{ background: transparent; color: {accent_text}; }}
QLabel[role="hero-cap"] {{
    font-size: 12px; font-weight: 700; letter-spacing: 0.5px;
    color: {accent_text};
}}
QLabel[role="hero-value"] {{
    font-size: 30px; font-weight: 800; color: {accent_text};
}}
QLabel[role="hero-sub"] {{
    font-size: 12px; font-weight: 600; color: {accent_text};
}}

/* Tarjeta KPI neutra. */
QFrame#dash_kpi {{
    background-color: {surface};
    border: 1px solid {line};
    border-radius: 16px;
}}
QFrame#dash_kpi QLabel {{ background: transparent; }}
QLabel[role="kpi-cap"] {{
    font-size: 12px; font-weight: 700; letter-spacing: 0.4px;
    color: {muted1};
}}
QLabel[role="kpi-value"] {{
    font-size: 30px; font-weight: 800; color: {text};
}}
QLabel[role="kpi-sub"] {{
    font-size: 12px; font-weight: 600; color: {muted1};
}}

/* Paneles inferiores (facturas recientes / accesos). */
QFrame#dash_panel {{
    background-color: {surface};
    border: 1px solid {line};
    border-radius: 16px;
}}
QFrame#dash_panel QLabel {{ background: transparent; }}
QLabel[role="panel-title"] {{
    font-size: 16px; font-weight: 800; color: {text};
    background: transparent;
}}
QLabel[role="panel-link"] {{
    font-size: 13px; font-weight: 700; color: {accent};
    background: transparent;
}}
QLabel[role="col-head"] {{
    font-size: 11px; font-weight: 800; color: {muted1};
    letter-spacing: 0.5px; background: transparent;
}}
QLabel[role="rec-num"] {{ font-weight: 800; color: {accent}; background: transparent; }}
QLabel[role="rec-cli"] {{ color: {subtext}; font-weight: 600; background: transparent; }}
QLabel[role="rec-total"] {{ font-weight: 700; color: {text}; background: transparent; }}
QLabel[role="rec-empty"] {{ color: {muted1}; background: transparent; }}
QFrame#dash_row_sep {{ background-color: {line}; border: none; max-height: 1px; }}

/* Botón de acceso rápido (ícono arriba + texto), fondo tenue. */
QPushButton#dash_quick {{
    background-color: {base};
    color: {text};
    border: 1px solid {line};
    border-radius: 12px;
    text-align: left;
    padding: 14px;
    font-size: 13px;
    font-weight: 700;
    min-height: 56px;
}}
QPushButton#dash_quick:hover {{
    border-color: {accent};
    background-color: rgba({accent_rgb}, 0.06);
}}

/* Tarjeta promo del generador de etiquetas. */
QFrame#dash_promo {{
    background-color: rgba({accent_rgb}, 0.06);
    border: 1px solid rgba({accent_rgb}, 0.22);
    border-radius: 16px;
}}
QFrame#dash_promo QLabel {{ background: transparent; }}

/* =====================================================================
   ETIQUETAS (generador): pasos, lista de productos, cola
   ===================================================================== */
QLabel[role="step-title"] {{
    font-size: 11px;
    font-weight: 800;
    color: {muted1};
    letter-spacing: 0.7px;
    background: transparent;
    padding-bottom: 8px;
    border-bottom: 1px solid {line};
}}

QScrollArea#queue_list {{
    background-color: {surface};
    border: 1px solid {line};
    border-radius: 10px;
}}
QWidget#queue_holder {{ background: transparent; }}

/* La lista de productos es una QTableWidget (como Clientes/Productos/Facturas)
   para compartir el mismo color de selección y la barra deslizante. */
QTableWidget#prod_table {{
    background-color: {surface};
    border: 1px solid {line};
    border-radius: 10px;
    gridline-color: transparent;
    outline: none;
    selection-background-color: transparent;
}}
/* Padding chico: el alto de fila (ResizeToContents / mínimo 39px) se calcula
   sin el padding del QSS; con 4px arriba/abajo un nombre que Qt parte en 2
   líneas no entraba y salía con "…". Con 2px las 2 líneas entran siempre. */
QTableWidget#prod_table::item {{
    padding: 2px 4px;
    border: none;
    border-bottom: 1px solid {base};
}}
QTableWidget#prod_table::item:selected {{
    background-color: {row_sel_bar};
}}

/* Botón sólo-ícono (ej. la X para quitar), sin borde ni caja. */
QPushButton#icon_btn {{
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 0px;
    min-height: 0px;
    min-width: 0px;
}}
QPushButton#icon_btn:hover {{
    background-color: rgba({danger_rgb}, 0.14);
}}
QPushButton#icon_btn:disabled {{
    background-color: transparent;
}}

/* Recuadro con el producto elegido. */
QFrame#etq_selected {{
    background-color: rgba({accent_rgb}, 0.06);
    border: 1px solid rgba({accent_rgb}, 0.22);
    border-radius: 10px;
}}
QFrame#etq_selected QLabel {{ background: transparent; }}
QLabel[role="etq-code"] {{
    font-size: 12px; font-weight: 800; color: {accent}; background: transparent;
}}
QLabel[role="etq-name"] {{
    font-size: 14px; font-weight: 700; color: {text}; background: transparent;
}}
QLabel[role="etq-type"] {{
    font-size: 11px; color: {subtext}; background: transparent;
}}

/* Fila de talle+cantidad. */
QFrame#etq_row {{
    background-color: {base};
    border: 1px solid {line};
    border-radius: 8px;
}}
QFrame#etq_row QLabel {{ background: transparent; }}
/* Campos más compactos dentro de la fila (el alto general de 34px sobraba acá). */
QFrame#etq_row QComboBox, QFrame#etq_row QSpinBox {{
    min-height: 24px;
    padding: 4px 10px;
}}

/* Ítem de la cola: chip de código + nombre/talle + cantidad. */
QFrame#queue_item {{
    background-color: {surface};
    border: 1px solid {line};
    border-radius: 9px;
}}
QFrame#queue_item QLabel {{ background: transparent; }}
/* Con el prefijo #queue_item: si no, "QFrame#queue_item QLabel" (más
   específica) le ponía fondo transparente y en oscuro el código no se leía. */
QFrame#queue_item QLabel#etq_chip, QLabel#etq_chip {{
    background-color: {accent};
    color: {accent_text};
    border-radius: 6px;
    font-size: 10px;
    font-weight: 800;
}}
QLabel[role="qi-label"] {{ font-size: 12px; font-weight: 700; color: {text}; background: transparent; }}
QLabel[role="qi-detail"] {{ font-size: 11px; color: {subtext}; background: transparent; }}
QLabel[role="qi-qty"] {{
    font-size: 12px; font-weight: 800; color: {accent};
    background-color: rgba({accent_rgb}, 0.12);
    border-radius: 5px; padding: 2px 8px;
}}

/* Resumen y aviso de la cola. */
QFrame#etq_summary {{
    background-color: {base};
    border: 1px solid {line};
    border-radius: 10px;
}}
QFrame#etq_summary QLabel {{ background: transparent; color: {subtext}; font-size: 12px; }}
QLabel[role="sum-strong"] {{ font-weight: 800; color: {text}; font-size: 13px; background: transparent; }}
QFrame#etq_warn {{
    background-color: rgba({warn_rgb}, 0.14);
    border: 1px solid rgba({warn_rgb}, 0.4);
    border-radius: 9px;
}}
QFrame#etq_warn QLabel {{ background: transparent; color: {warn}; font-size: 12px; }}

QLabel[role="empty-hint"] {{
    color: {muted1}; font-size: 13px; background: transparent;
}}

/* Contenedor sin fondo propio. Se targetea por objectName para NO pisar el
   fondo de los hijos (un `background: transparent` puesto inline sobre el widget
   se filtra a los QPushButton adentro y les borra el color de acento). */
QWidget#plain_box {{ background: transparent; }}

/* Marca de la sidebar: clickeable para volver al inicio. */
QWidget#brand_click {{
    background: transparent;
    border-radius: 8px;
}}

QWidget#brand_click:hover {{
    background-color: rgba({accent_rgb}, 0.08);
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
    border-radius: 10px;
    gridline-color: transparent;
    outline: none;
    color: {text};
    selection-background-color: {row_sel_bar};
    selection-color: {text};
}}

/* Sin `color` en ::item: si no, pisa el color propio de cada celda
   (ForegroundRole, ej. el código en acento). El default viene de QTableWidget. */
QTableWidget::item {{
    padding: 0px 12px;
    border: none;
}}

QTableWidget::item:alternate {{
    background-color: {base};
}}

/* Va DESPUÉS de :alternate a propósito: en Qt, cuando una fila alternada
   además está seleccionada, gana la regla declarada más abajo. Si :selected
   fuera la primera, la selección quedaba invisible en las filas alternadas
   (parecía que el click "no hacía nada" en esas filas). */
/* Selección: celeste suave pintado por Qt (estilo Fusion + este QSS). */
QTableWidget::item:selected,
QTableWidget::item:alternate:selected {{
    background-color: {row_sel_bar};
}}

QHeaderView {{
    background-color: {crust};
    border: none;
}}

/* border-right: una fina línea divisoria entre columnas que además señala el
   borde arrastrable para ensanchar/achicar cada columna. */
QHeaderView::section {{
    background-color: {crust};
    color: {subtext};
    padding: 10px 12px;
    border: none;
    border-bottom: 1px solid {line};
    border-right: 1px solid {line};
    font-weight: 700;
    font-size: 10px;
    letter-spacing: 0.5px;
}}

QHeaderView::section:last {{
    border-right: none;
}}

/* Esquinas superiores redondeadas para que el borde redondeado de la lista se
   vea también arriba (si no, el header cuadrado tapa las esquinas de la tabla). */
QHeaderView::section:first {{
    border-top-left-radius: 10px;
}}
QHeaderView::section:last {{
    border-top-right-radius: 10px;
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
    color: {faint_tx};
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
    color: {faint_tx};
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
    color: {faint_tx};
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
    color: {faint_tx};
}}

QLineEdit::placeholder {{
    color: {faint_tx};
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

/* Sin botones de subir/bajar: campo numérico limpio (la cantidad se escribe).
   Ocultarlos por completo evita las cajitas grises que quedaban "rotas". */
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    width: 0px;
    height: 0px;
    border: none;
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

/* Flechita DENTRO del padding y sin fondo propio: con fondo opaco tapaba el
   borde derecho del combo (se veía "cortado", sobre todo con foco). */
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    border: none;
    background: transparent;
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
    color: {faint_tx};
    border-top: 1px solid {line};
    font-size: 11px;
}}

QStatusBar QLabel {{
    background: transparent;
    color: {faint_tx};
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

# Paleta "Vexa Rework" (2026-07-15): azul plano #2f5bea sobre superficies casi
# blancas en claro; derivada neutra con acento azul en oscuro. Cada color usado
# en el stylesheet es un token nombrado acá, así ambos temas cubren exactamente
# los mismos selectores.
_PALETTES = {
    "dark": {
        "base": "#171922",
        "crust": "#1e2029",
        "surface": "#20222e",
        "line": "#2b2f3d",
        "muted2": "#3b4052",      # bordes/fondos; NO para texto (no se lee)
        "faint_tx": "#848ba0",    # texto tenue legible: deshabilitado, placeholder, versión
        "muted1": "#6b7191",
        "subtext": "#9aa2b1",
        "text": "#e5e8ee",
        "accent": "#5b8bff",
        "accent_hover": "#74a0ff",
        "accent_pressed": "#3b6bff",
        "accent_text": "#0b1020",
        "accent_rgb": "91, 139, 255",
        "select_bg": "#2c3450",
        "select_tx": "#e5e8ee",
        "row_sel": "#232838",
        "row_sel_bar": "#37436a",
        "danger": "#f2708c",
        "danger_rgb": "242, 112, 140",
        "warn": "#eab24a",
        "warn_rgb": "234, 178, 74",
        "disabled_bg": "#24273a",
    },
    "light": {
        "base": "#f4f5f8",
        "crust": "#ffffff",
        "surface": "#ffffff",
        "line": "#e5e8ee",
        "muted2": "#c3c9d3",      # bordes/fondos; NO para texto (no se lee)
        "faint_tx": "#8b93a1",    # texto tenue legible: deshabilitado, placeholder, versión
        "muted1": "#8a92a2",
        "subtext": "#6b7280",
        "text": "#1f2430",
        "accent": "#2f5bea",
        "accent_hover": "#3b6bff",
        "accent_pressed": "#1e40af",
        "accent_text": "#ffffff",
        "accent_rgb": "47, 91, 234",
        "select_bg": "#dbe6ff",
        "select_tx": "#1f2430",
        "row_sel": "#eef3ff",
        "row_sel_bar": "#b9cbff",
        "danger": "#d20f39",
        "danger_rgb": "210, 15, 57",
        "warn": "#df8e1d",
        "warn_rgb": "223, 142, 29",
        "disabled_bg": "#eceef3",
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
    pal.setColor(QPalette.PlaceholderText, c(p["faint_tx"]))
    pal.setColor(QPalette.BrightText, c(p["danger"]))
    # Selección tenue (no el accent pleno): el azul saturado en filas/listas
    # resultaba agresivo al clickear clientes/productos.
    pal.setColor(QPalette.Highlight, c(p["select_bg"]))
    pal.setColor(QPalette.HighlightedText, c(p["select_tx"]))
    if hasattr(QPalette, "Accent"):   # Qt ≥ 6.6: si no, toma el acento de Windows
        pal.setColor(QPalette.Accent, c(p["accent"]))
    for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, c(p["faint_tx"]))
    return pal
