"""Shell de la app: top bar, barra inferior (con barra azul deslizante + swipe),
hoja de Configuración, tema claro/oscuro y ruteo entre vistas."""
from __future__ import annotations

import flet as ft

from theme import tokens, soft, PAD, PADS, MAR, BALL, BEDGE
from logo import v_logo
from vexa_core.database.db import DatabaseManager
from vexa_core.utils.helpers import set_moneda, PROVINCIAS_AR, formatear_cuit
from vexa_core.version import VERSION
from views.inicio import InicioView
from views.clientes import ClientesView, IVA_OPTS
from views.productos import ProductosView
from views.facturas import FacturasView
from views.etiquetas import EtiquetasView

# Barra inferior: (id, label, icono outline, icono filled). Inicio va al medio.
NAV = [
    ("clientes", "Clientes", ft.Icons.PEOPLE_OUTLINE, ft.Icons.PEOPLE),
    ("productos", "Productos", ft.Icons.INVENTORY_2_OUTLINED, ft.Icons.INVENTORY_2),
    ("inicio", "Inicio", ft.Icons.HOME_OUTLINED, ft.Icons.HOME_ROUNDED),
    ("etiquetas", "Etiquetas", ft.Icons.LOCAL_OFFER_OUTLINED, ft.Icons.LOCAL_OFFER),
    ("facturas", "Facturas", ft.Icons.RECEIPT_LONG_OUTLINED, ft.Icons.RECEIPT_LONG),
]
NAV_IDS = [x[0] for x in NAV]


class VexaApp:
    def __init__(self, page: ft.Page, db: DatabaseManager):
        self.page = page
        self.db = db
        self.dark = page.platform_brightness == ft.Brightness.DARK
        self.tab = "inicio"
        self.views = {
            "inicio": InicioView(self), "clientes": ClientesView(self),
            "productos": ProductosView(self), "facturas": FacturasView(self),
            "etiquetas": EtiquetasView(self),
        }
        self._screen = ft.Container(expand=True)
        self._nav = ft.Container()
        self._config_sheet = None
        self._pending_after_config = None
        self._form_escape = None   # callback de cierre del form abierto (para Escape)
        self.file_picker = ft.FilePicker()  # se agrega a page.services en main
        self.root = None

    def on_key(self, e):
        # Escape: cerrar el form activo pasando por el chequeo de cambios.
        if getattr(e, "key", None) == "Escape" and self._form_escape:
            self._form_escape()

    @property
    def t(self) -> dict:
        return tokens(self.dark)

    def snack(self, texto: str):
        self.page.show_dialog(ft.SnackBar(ft.Text(texto)))

    def confirm_toast(self, mensaje: str, on_confirm):
        """Toast arriba de todo (sobre la pantalla) con acción de confirmar.
        'Descartar' ejecuta on_confirm; 'Seguir editando' solo lo cierra."""
        t = self.t

        def cerrar():
            try:
                self.page.overlay.remove(box)
            except ValueError:
                pass
            self.page.update()

        box = ft.Container(
            top=12, left=14, right=14, bgcolor=t["surface"], border=BALL(1, t["line2"]),
            border_radius=14, padding=PADS(12, 16),
            content=ft.Column([
                ft.Text(mensaje, size=13, weight=ft.FontWeight.W_600, color=t["ink"]),
                ft.Container(height=8),
                ft.Row([
                    ft.Container(content=ft.Text("Seguir editando", color=t["muted"], size=13,
                                                 weight=ft.FontWeight.W_600),
                                 padding=PADS(8, 12), ink=True, border_radius=10,
                                 on_click=lambda e: cerrar()),
                    ft.Container(expand=True),
                    ft.Container(content=ft.Text("Descartar", color="#ffffff", size=13,
                                                 weight=ft.FontWeight.W_700), bgcolor=t["danger"],
                                 border_radius=10, padding=PADS(8, 16), ink=True,
                                 on_click=lambda e: (cerrar(), on_confirm())),
                ]),
            ], spacing=0, tight=True))
        self.page.overlay.append(box)
        self.page.update()

    def render(self):
        """Reconstruye TODO el árbol y reemplaza `page.controls`. En este Flet,
        mutar el `.content` de un control ya montado + `update()` no re-renderiza
        (la pantalla quedaba gris/negra), así que se rearma como en el arranque."""
        t = self.t
        self.page.theme_mode = ft.ThemeMode.DARK if self.dark else ft.ThemeMode.LIGHT
        self.page.bgcolor = t["ground"]
        # Transición direccional: el contenido entra deslizándose desde el lado
        # correspondiente al cambio de tab (+der / −izq) con un fade.
        prev = getattr(self, "_last_tab", self.tab)
        try:
            delta = NAV_IDS.index(self.tab) - NAV_IDS.index(prev)
        except ValueError:
            delta = 0
        self._last_tab = self.tab
        dx = 0.05 if delta > 0 else -0.05 if delta < 0 else 0.0
        self._screen = ft.Container(
            expand=True, padding=PAD(16, 12, 16, 8), content=self.views[self.tab].build(),
            offset=ft.Offset(dx, 0), opacity=0.0,
            animate_offset=ft.Animation(230, ft.AnimationCurve.EASE_OUT),
            animate_opacity=ft.Animation(200))
        gestos = ft.GestureDetector(content=self._screen, on_horizontal_drag_end=self._on_swipe,
                                    expand=True)
        self._build_nav()
        # Barras extendidas a los bordes: el color de la top bar (surface) sigue
        # hacia arriba detrás de la barra de estado, y el de la nav (nav_bg) hacia
        # abajo. SafeArea agrega SOLO el inset necesario (si no hay intrusión, 0).
        topbar = ft.Container(bgcolor=t["surface"], content=ft.SafeArea(
            self.top_bar(), avoid_intrusions_bottom=False,
            avoid_intrusions_left=False, avoid_intrusions_right=False))
        navbar = ft.Container(bgcolor=t["nav_bg"], content=ft.SafeArea(
            self._nav, avoid_intrusions_top=False,
            avoid_intrusions_left=False, avoid_intrusions_right=False))
        col = ft.Column([topbar, ft.Container(gestos, expand=True), navbar],
                        spacing=0, expand=True)
        self.root = ft.Container(expand=True, bgcolor=t["ground"], content=col)
        self.page.controls[:] = [self.root]
        self.page.update()
        # Disparar la animación de entrada (ya montado).
        try:
            self._screen.offset = ft.Offset(0, 0)
            self._screen.opacity = 1.0
            self._screen.update()
        except Exception:  # noqa: BLE001 — sin página montada (tests) no anima
            pass

    # Alias histórico.
    refresh = render

    # -------------------------------------------------------------- top bar
    def top_bar(self) -> ft.Control:
        t = self.t
        razon = (self.db.get_datos_empresa().get("nombre") or "").strip().upper() or "TU EMPRESA"
        marca = ft.Container(  # tocar la marca vuelve a Inicio
            on_click=lambda e: self.set_tab("inicio"), ink=True, border_radius=8,
            padding=PADS(2, 2),
            content=ft.Row([
                v_logo(26, t["v_ink"], t["dot"]),
                ft.Column([
                    ft.Text("Vexa", size=19, weight=ft.FontWeight.W_800, color=t["accent"]),
                    ft.Text(razon, size=9, weight=ft.FontWeight.BOLD, color=t["faint"], no_wrap=True),
                ], spacing=0, tight=True),
            ], spacing=9, vertical_alignment=ft.CrossAxisAlignment.CENTER, tight=True))
        gear = ft.Container(
            width=38, height=38, border_radius=12, bgcolor=t["surface2"],
            border=BALL(1, t["line2"]), alignment=ft.Alignment.CENTER, ink=True,
            content=ft.Icon(ft.Icons.SETTINGS_OUTLINED, size=20, color=t["muted"]),
            on_click=lambda e: self.open_config(), tooltip="Configuración")
        return ft.Container(
            bgcolor=t["surface"], padding=PAD(16, 14, 16, 12),
            border=BEDGE(bottom=(1, t["line"])),
            content=ft.Row([marca, ft.Container(expand=True), gear],
                           vertical_alignment=ft.CrossAxisAlignment.CENTER))

    # ------------------------------------------------------------ bottom nav
    # Todos los tabs iguales: activo = pastilla azul iluminada EN SU LUGAR
    # (sin sombra/glow/degradé); inactivo = faint. Inicio va centrado y un
    # poquito más arriba, con el mismo tratamiento de color que el resto.
    def _nav_cell(self, sid, lbl, ic_out, ic_fill) -> ft.Control:
        t = self.t
        activo = self.tab == sid
        es_inicio = sid == "inicio"
        # La forma que se pinta de azul cuando el tab está activo: CÍRCULO para
        # Inicio, CUADRADO redondeado para el resto. Mismo tamaño → alineados.
        lado = 48
        forma = ft.Container(
            width=lado, height=lado, border_radius=(lado // 2 if es_inicio else 14),
            alignment=ft.Alignment.CENTER, bgcolor=t["accent"] if activo else t["nav_bg"],
            border=(BALL(1.5, t["line2"]) if (es_inicio and not activo) else None),
            content=ft.Icon(ic_fill if activo else ic_out, size=23,
                            color=t["accent_ink"] if activo else t["faint"]))
        label = ft.Text(lbl, size=10, weight=ft.FontWeight.W_700,
                        color=t["accent"] if activo else t["faint"])
        inner = ft.Column([forma, label], spacing=2, alignment=ft.MainAxisAlignment.CENTER,
                          horizontal_alignment=ft.CrossAxisAlignment.CENTER, tight=True)
        # Inicio (círculo) va al MISMO nivel que el resto (sin elevación).
        cell = ft.Container(content=inner, alignment=ft.Alignment.CENTER)
        return ft.Container(expand=True, alignment=ft.Alignment.CENTER, content=cell,
                            on_click=lambda e, s=sid: self.set_tab(s))

    def _build_nav_row(self) -> ft.Control:
        return ft.Row([self._nav_cell(*item) for item in NAV],
                      alignment=ft.MainAxisAlignment.SPACE_AROUND,
                      vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _build_nav(self) -> ft.Control:
        t = self.t
        self._nav = ft.Container(
            height=74, bgcolor=t["nav_bg"], border=BEDGE(top=(1, t["line"])), padding=PADS(8, 8),
            content=self._build_nav_row())
        return self._nav

    # ---------------------------------------------------------- config sheet
    def _config_body(self) -> ft.Control:
        """Contenido de la hoja de Configuración (se reconstruye al cambiar tema)."""
        t = self.t

        def theme_btn(dark: bool, icon, label):
            on = self.dark == dark
            return ft.Container(
                expand=True, bgcolor=t["accent"] if on else None, border_radius=9, padding=11,
                alignment=ft.Alignment.CENTER,
                content=ft.Row([ft.Icon(icon, size=17, color=t["accent_ink"] if on else t["muted"]),
                                ft.Text(label, size=13.5, weight=ft.FontWeight.W_700,
                                        color=t["accent_ink"] if on else t["muted"])],
                               alignment=ft.MainAxisAlignment.CENTER, spacing=7),
                on_click=lambda e, d=dark: self.set_theme(d), ink=True)

        theme_seg = ft.Container(
            bgcolor=t["surface"], border=BALL(1, t["line"]), border_radius=13, padding=5,
            content=ft.Row([theme_btn(False, ft.Icons.LIGHT_MODE_OUTLINED, "Claro"),
                            theme_btn(True, ft.Icons.DARK_MODE_OUTLINED, "Oscuro")], spacing=5))

        def setrow(icon, titulo_txt, sub, accion=None):
            cb = (lambda e: accion()) if accion else (lambda e, ti=titulo_txt: self.snack(ti + " — (pendiente 6.2b)"))
            return ft.Container(
                bgcolor=t["surface"], border=BALL(1, t["line"]), border_radius=14, padding=14,
                margin=MAR(bottom=9),
                content=ft.Row([
                    ft.Container(width=38, height=38, border_radius=11, bgcolor=soft(t["accent"], 0.12),
                                 alignment=ft.Alignment.CENTER,
                                 content=ft.Icon(icon, size=20, color=t["accent"])),
                    ft.Column([ft.Text(titulo_txt, size=14, weight=ft.FontWeight.W_700, color=t["ink"]),
                               ft.Text(sub, size=11.5, color=t["muted"])], spacing=1, expand=True,
                              tight=True),
                    ft.Text("›", size=18, color=t["faint"]),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=13),
                on_click=cb, ink=True)

        def label(txt):
            return ft.Text(txt.upper(), size=10.5, weight=ft.FontWeight.W_800, color=t["faint"])

        return ft.Column([
            ft.Container(alignment=ft.Alignment.CENTER, margin=MAR(bottom=8),
                         content=ft.Container(width=40, height=4, border_radius=2,
                                              bgcolor=t["line2"])),
            ft.Row([ft.Text("Configuración", size=19, weight=ft.FontWeight.W_800, color=t["ink"]),
                    ft.Container(expand=True),
                    ft.IconButton(ft.Icons.CLOSE, icon_color=t["muted"],
                                  on_click=lambda e: self.page.pop_dialog())],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=6), label("Apariencia"), ft.Container(height=8), theme_seg,
            ft.Container(height=14), label("Empresa"), ft.Container(height=8),
            setrow(ft.Icons.BUSINESS_OUTLINED, "Datos de la empresa",
                   "Razón social, CUIT, domicilio, moneda", accion=self._empresa_form),
            setrow(ft.Icons.SAVE_OUTLINED, "Guardado", "Logo, carpeta de PDF, pie de página"),
            ft.Container(height=6), label("Facturación electrónica"), ft.Container(height=8),
            setrow(ft.Icons.RECEIPT_OUTLINED, "AFIP / ARCA (opcional)",
                   "Facturación electrónica — se configura en el escritorio",
                   accion=lambda: self.page.launch_url("https://www.arca.gob.ar")),
            ft.Container(height=10),
            ft.Text(f"Vexa · v{VERSION}", size=11, color=t["faint"], text_align=ft.TextAlign.CENTER),
        ], spacing=0, scroll=ft.ScrollMode.AUTO, tight=True)

    def _config_container(self) -> ft.Control:
        t = self.t
        # Grip y esquinas redondeadas propios (show_drag_handle=False) para que al
        # cambiar de tema con la hoja abierta se re-tematice TODO (antes el chrome
        # de Material quedaba con el color viejo hasta reabrir).
        return ft.Container(padding=PAD(16, 10, 16, 24), content=self._config_body(),
                            bgcolor=t["ground"], border_radius=24)

    def open_config(self):
        t = self.t
        self._pending_after_config = None
        self._config_sheet = ft.BottomSheet(
            content=self._config_container(), show_drag_handle=False, bgcolor=t["ground"],
            on_dismiss=lambda e: self._on_config_closed())
        self.page.show_dialog(self._config_sheet)

    def _on_config_closed(self):
        self._config_sheet = None
        accion = getattr(self, "_pending_after_config", None)
        self._pending_after_config = None
        if accion:  # abrir el form DESPUÉS de que la hoja cerró (evita scrim negro)
            accion()

    def _empresa_form(self):
        # Cerrar Configuración y abrir el form recién en su on_dismiss.
        self._pending_after_config = self._abrir_empresa_form
        self.page.pop_dialog()

    def _abrir_empresa_form(self):
        emp = self.db.get_datos_empresa()
        campos = [
            {"key": "nombre", "label": "Razón social", "value": emp.get("nombre")},
            {"key": "nif", "label": "CUIT", "value": emp.get("nif")},
            {"key": "condicion_iva", "label": "Condición IVA", "tipo": "dropdown",
             "value": emp.get("condicion_iva") or "Responsable Inscripto", "options": IVA_OPTS},
            {"key": "direccion", "label": "Domicilio", "value": emp.get("direccion")},
            [{"key": "cp", "label": "C.P.", "value": emp.get("cp")},
             {"key": "localidad", "label": "Localidad", "value": emp.get("localidad")}],
            {"key": "provincia", "label": "Provincia", "tipo": "dropdown", "editable": True,
             "value": emp.get("provincia") or "", "options": [""] + list(PROVINCIAS_AR)},
            [{"key": "telefono", "label": "Teléfono", "value": emp.get("telefono")},
             {"key": "email", "label": "Email", "value": emp.get("email")}],
            {"key": "web", "label": "Sitio web", "value": emp.get("web")},
            [{"key": "moneda", "label": "Moneda", "tipo": "dropdown",
              "value": emp.get("moneda") or "$", "options": ["$", "US$"]},
             {"key": "punto_venta", "label": "Punto de venta", "value": emp.get("punto_venta")}],
        ]

        def guardar(d):
            e = self.db.get_datos_empresa()
            e.update(d)
            self.db.update_datos_empresa(e)
            set_moneda(e.get("moneda"))

        self.open_form("Datos de la empresa", campos, on_save=guardar)

    def set_theme(self, dark: bool):
        # Cambia el tema SIN cerrar la hoja: reconstruye el fondo (page.controls) y
        # re-tematiza el contenido completo de la hoja abierta.
        if self.dark == dark:
            return
        self.dark = dark
        self.render()
        sheet = getattr(self, "_config_sheet", None)
        if sheet is not None:
            sheet.bgcolor = self.t["ground"]
            sheet.content = self._config_container()
            sheet.update()

    # -------------------------------------------------------- formulario genérico
    def open_form(self, titulo, campos, on_save, on_delete=None):
        """Formulario full-screen. `campos`: items sueltos o listas [c1,c2] (2 col).
        Tipos: text|number|multiline|dropdown|chips. dropdown.options: str o (label,valor),
        editable=True para escribir/filtrar. chips.format='cuit' formatea al agregar.
        Se construye UNA sola vez; chips y aviso se actualizan puntualmente (sin recrear
        el modal). Escape/Cancelar/grip cierran pasando por el chequeo de cambios."""
        t = self.t
        flat = [c for item in campos for c in (item if isinstance(item, list) else [item])]
        estado = {"dirty": False}
        chips, chip_rows, chip_inputs, chip_fmt, ctrls = {}, {}, {}, {}, {}

        def mark_dirty(*_):
            estado["dirty"] = True

        def _fmt_chip_input(key):
            estado["dirty"] = True
            if chip_fmt.get(key) != "cuit":
                return
            inp = chip_inputs[key]
            nuevo = formatear_cuit(inp.value or "")
            if nuevo != inp.value:
                inp.value = nuevo
                try:
                    inp.update()
                except Exception:  # noqa: BLE001
                    pass

        def _chip_widget(key, i, ch):
            return ft.Container(
                bgcolor=soft(t["accent"], 0.12), border_radius=999, padding=PAD(12, 5, 6, 5),
                content=ft.Row([
                    ft.Text(ch, size=12.5, weight=ft.FontWeight.W_700, color=t["accent"]),
                    ft.Container(ink=True, border_radius=999,
                                 on_click=lambda e, k=key, idx=i: _del_chip(k, idx),
                                 content=ft.Icon(ft.Icons.CLOSE, size=14, color=t["accent"])),
                ], spacing=6, tight=True))

        def _refresh_chips(key):
            chip_rows[key].controls = [_chip_widget(key, i, ch) for i, ch in enumerate(chips[key])]
            try:
                chip_rows[key].update()
            except Exception:  # noqa: BLE001
                pass

        def _add_chip(key):
            inp = chip_inputs[key]
            txt = (inp.value or "").strip()
            if not txt:
                return
            if chip_fmt.get(key) == "cuit":
                txt = formatear_cuit(txt)
            chips[key].append(txt)
            inp.value = ""
            estado["dirty"] = True
            try:
                inp.update()
            except Exception:  # noqa: BLE001
                pass
            _refresh_chips(key)

        def _del_chip(key, i):
            if 0 <= i < len(chips[key]):
                chips[key].pop(i)
            estado["dirty"] = True
            _refresh_chips(key)

        for c in flat:
            key, tipo, val = c["key"], c.get("tipo", "text"), c.get("value")
            if tipo == "chips":
                chips[key] = [str(x) for x in (val or [])]
                chip_fmt[key] = c.get("format")
                chip_rows[key] = ft.Row(wrap=True, spacing=6, run_spacing=6)
                chip_inputs[key] = ft.TextField(
                    hint_text=c.get("hint", "Agregar y Enter…"), border_radius=12,
                    border_color=t["line2"], focused_border_color=t["accent"], filled=True,
                    bgcolor=t["surface2"], color=t["ink"], text_size=14, content_padding=PADS(11, 13),
                    hint_style=ft.TextStyle(color=t["faint"]), expand=True,
                    on_change=lambda e, k=key: _fmt_chip_input(k),
                    on_submit=lambda e, k=key: _add_chip(k))
                ctrls[key] = ("chips", None)
            elif tipo == "dropdown":
                pairs = [(o, o) if not isinstance(o, tuple) else o for o in c.get("options", [])]
                cur = next((i for i, (lbl, v) in enumerate(pairs) if v == val), None)
                dd = ft.Dropdown(
                    value=(str(cur) if cur is not None else None), border_radius=12,
                    editable=bool(c.get("editable")), enable_filter=bool(c.get("editable")),
                    options=[ft.DropdownOption(key=str(i), text=str(lbl)) for i, (lbl, v) in enumerate(pairs)],
                    on_select=mark_dirty, border_color=t["line2"], filled=True, bgcolor=t["surface2"],
                    text_size=14, content_padding=PADS(11, 13), text_style=ft.TextStyle(color=t["ink"]))
                ctrls[key] = ("dropdown", dd, pairs)
            else:
                tf = ft.TextField(
                    value=("" if val is None else str(val)), border_radius=12,
                    keyboard_type=ft.KeyboardType.NUMBER if tipo == "number" else ft.KeyboardType.TEXT,
                    multiline=(tipo == "multiline"), min_lines=2 if tipo == "multiline" else 1,
                    max_lines=4 if tipo == "multiline" else 1, on_change=mark_dirty,
                    hint_text=c.get("hint"), hint_style=ft.TextStyle(color=t["faint"]),
                    border_color=t["line2"], focused_border_color=t["accent"], filled=True,
                    bgcolor=t["surface2"], color=t["ink"], text_size=14, content_padding=PADS(11, 13))
                ctrls[key] = (tipo, tf)

        def _field(c):
            key, tipo = c["key"], c.get("tipo", "text")
            label = ft.Text((c["label"] or "").upper(), size=10.5, weight=ft.FontWeight.W_800,
                            color=t["faint"])
            if tipo == "chips":
                _refresh_chips(key)
                addbtn = ft.Container(width=46, height=46, border_radius=12,
                                      bgcolor=soft(t["accent"], 0.12), alignment=ft.Alignment.CENTER,
                                      ink=True, on_click=lambda e, k=key: _add_chip(k),
                                      content=ft.Icon(ft.Icons.ADD, color=t["accent"], size=20))
                return ft.Column([label, ft.Row([chip_inputs[key], addbtn], spacing=8,
                                                 vertical_alignment=ft.CrossAxisAlignment.CENTER),
                                  chip_rows[key]], spacing=6, tight=True,
                                 horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
            return ft.Column([label, ctrls[key][1]], spacing=5, tight=True,
                             horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

        def collect():
            data = {}
            for key, meta in ctrls.items():
                tipo = meta[0]
                if tipo == "chips":
                    data[key] = list(chips[key])
                elif tipo == "dropdown":
                    dd, pairs = meta[1], meta[2]
                    v = dd.value
                    data[key] = pairs[int(v)][1] if v is not None else None
                else:
                    v = meta[1].value
                    if tipo == "number":
                        try:
                            v = float(str(v).replace(".", "").replace(",", ".")) if v not in (None, "") else 0
                        except ValueError:
                            v = 0
                    data[key] = v
            return data

        def _close():
            self._form_escape = None
            self.page.pop_dialog()

        def guardar(_e):
            data = collect()
            try:
                on_save(data)
            except ValueError as ve:
                self.snack(str(ve))
                return
            except Exception as ex:  # noqa: BLE001
                _close()
                self.snack(f"Error al guardar: {ex}")
                return
            _close()
            self.render()
            self.snack("Guardado")

        def borrar(_e):
            _close()
            try:
                on_delete()
            except Exception as ex:  # noqa: BLE001
                self.snack(f"Error al eliminar: {ex}")
                return
            self.render()
            self.snack("Eliminado")

        def _hide_banner():
            banner.visible = False
            try:
                banner.update()
            except Exception:  # noqa: BLE001
                pass

        def try_close(*_):
            if estado["dirty"]:
                banner.visible = True
                try:
                    banner.update()
                except Exception:  # noqa: BLE001
                    pass
            else:
                _close()

        banner = ft.Container(
            visible=False, top=8, left=12, right=12, bgcolor=t["surface"], border=BALL(1, t["line2"]),
            border_radius=14, padding=PADS(12, 16),
            content=ft.Column([
                ft.Text("Tenes cambios sin guardar. Descartarlos?", size=13,
                        weight=ft.FontWeight.W_600, color=t["ink"]),
                ft.Container(height=8),
                ft.Row([
                    ft.Container(content=ft.Text("Seguir editando", color=t["muted"], size=13,
                                                 weight=ft.FontWeight.W_600), padding=PADS(8, 12),
                                 ink=True, border_radius=10, on_click=lambda e: _hide_banner()),
                    ft.Container(expand=True),
                    ft.Container(content=ft.Text("Descartar", color="#ffffff", size=13,
                                                 weight=ft.FontWeight.W_700), bgcolor=t["danger"],
                                 border_radius=10, padding=PADS(8, 16), ink=True,
                                 on_click=lambda e: _close()),
                ]),
            ], spacing=0, tight=True))

        cuerpo = []
        for item in campos:
            if isinstance(item, list):
                cuerpo.append(ft.Row([ft.Container(expand=True, content=_field(c)) for c in item],
                                     spacing=12, vertical_alignment=ft.CrossAxisAlignment.START))
            else:
                cuerpo.append(_field(item))
            cuerpo.append(ft.Container(height=13))

        acciones = [ft.Container(content=ft.Text("Cancelar", color=t["muted"], size=14,
                                                 weight=ft.FontWeight.W_600),
                                 padding=PADS(12, 14), on_click=try_close, ink=True, border_radius=12),
                    ft.Container(expand=True)]
        if on_delete is not None:
            acciones.append(ft.Container(width=50, height=48, bgcolor=soft(t["danger"], 0.12),
                                         border_radius=13, alignment=ft.Alignment.CENTER, ink=True,
                                         on_click=borrar,
                                         content=ft.Icon(ft.Icons.DELETE_OUTLINE, color=t["danger"], size=20)))
            acciones.append(ft.Container(width=8))
        acciones.append(ft.Container(bgcolor=t["accent"], border_radius=13, padding=PADS(13, 22),
                                     ink=True, on_click=guardar,
                                     content=ft.Text("Guardar", color=t["accent_ink"],
                                                     weight=ft.FontWeight.W_700, size=14)))

        # Grip: tocar o deslizar hacia abajo cierra (pasando por el chequeo de cambios).
        # El contenedor lleva bgcolor (opaco) para ser hit-testable en toda su área.
        grip = ft.GestureDetector(
            on_tap=lambda e: try_close(),
            on_vertical_drag_end=lambda e: (try_close() if (getattr(e, "primary_velocity", None) or 0) > 0 else None),
            content=ft.Container(alignment=ft.Alignment.CENTER, padding=PADS(12, 4), bgcolor=t["ground"],
                                 content=ft.Container(width=44, height=5, border_radius=3,
                                                      bgcolor=t["line2"])))
        scroll_col = ft.Column(
            [ft.Text(titulo, size=20, weight=ft.FontWeight.W_800, color=t["ink"]),
             ft.Container(height=14), *cuerpo],
            spacing=0, scroll=ft.ScrollMode.HIDDEN, expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        footer = ft.Container(padding=PAD(0, 12, 0, 0), border=BEDGE(top=(1, t["line"])),
                              content=ft.Row(acciones, vertical_alignment=ft.CrossAxisAlignment.CENTER))
        base = ft.Container(padding=PAD(18, 8, 18, 18), bgcolor=t["ground"], expand=True,
                            content=ft.Column([grip, ft.Container(expand=True, content=scroll_col), footer],
                                              spacing=0, expand=True,
                                              horizontal_alignment=ft.CrossAxisAlignment.STRETCH))
        self._form_escape = try_close
        self.page.show_dialog(ft.BottomSheet(
            content=ft.Stack([base, banner], expand=True), bgcolor=t["ground"], fullscreen=True,
            dismissible=False, draggable=False, show_drag_handle=False))

    # ------------------------------------------------------------- navegación
    def set_tab(self, sid: str):
        if sid != self.tab:
            self.tab = sid
            self.render()

    def _on_swipe(self, e):
        v = getattr(e, "primary_velocity", None) or 0
        if v == 0:
            return
        i = NAV_IDS.index(self.tab)
        i = max(0, min(len(NAV_IDS) - 1, i + (-1 if v > 0 else 1)))
        self.set_tab(NAV_IDS[i])
