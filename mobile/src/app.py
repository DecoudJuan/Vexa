"""Shell de la app: top bar, barra inferior (con barra azul deslizante + swipe),
hoja de Configuración, tema claro/oscuro y ruteo entre vistas."""
from __future__ import annotations

import flet as ft

from theme import tokens, soft, PAD, PADS, MAR, BALL, BEDGE
from logo import v_logo
from vexa_core.database.db import DatabaseManager
from vexa_core.utils.helpers import (set_moneda, PROVINCIAS_AR, formatear_cuit, CONDICIONES_IVA,
                                      MONEDAS, TELEFONO_EJEMPLO, partir_direccion, unir_direccion)
from vexa_core.version import VERSION
from views.inicio import InicioView
from views.clientes import ClientesView
from views.productos import ProductosView
from views.facturas import FacturasView
from views.etiquetas import EtiquetasView
from views.afip import AfipView

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
        # Tema: respeta el que el usuario eligió (guardado); si nunca eligió, sigue al SO.
        guardado = db.get_config("tema")
        self.dark = (guardado == "oscuro") if guardado in ("oscuro", "claro") \
            else (page.platform_brightness == ft.Brightness.DARK)
        self.tab = "inicio"
        self.views = {
            "inicio": InicioView(self), "clientes": ClientesView(self),
            "productos": ProductosView(self), "facturas": FacturasView(self),
            "etiquetas": EtiquetasView(self),
        }
        self._screen = ft.Container(expand=True)
        self._nav = ft.Container()
        self.subpage = None   # página full-screen fuera del nav (ej. AFIP); None = tab normal
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

    def marquee(self, texto, size, weight, color, fit=18) -> ft.Control:
        """Nombre de una línea. Si es largo, se revela el resto **a demanda**: apretándolo
        (long-press en el celular) o pasándole el puntero por encima (hover en escritorio).
        NO usa scroll con el dedo (chocaba con el swipe de pestañas) NI un loop automático
        (lageaba la app): se anima el offset UNA vez por interacción."""
        texto = texto or ""
        txt = ft.Text(texto, size=size, weight=weight, color=color, no_wrap=True,
                      offset=ft.Offset(0, 0), animate_offset=ft.Animation(1900, ft.AnimationCurve.EASE_IN_OUT))
        clip = ft.Container(content=txt, clip_behavior=ft.ClipBehavior.HARD_EDGE)
        if len(texto) <= 14:   # nombres cortos entran sin recortarse
            return clip
        # cuánto correr para llegar AL FINAL. Como no se puede medir el ancho real, se usa
        # una fracción agresiva (base 7) para que el recorrido alcance el final (mejor pasarse
        # un poco: el nombre se lee mientras se mueve).
        frac = min(0.92, (len(texto) - 7) / len(texto))
        st = {"anim": False}

        async def _reveal():
            import asyncio
            if st["anim"]:
                return
            st["anim"] = True
            try:
                txt.offset = ft.Offset(-frac, 0)   # corre hasta el final (se lee mientras se mueve)
                txt.update()
                await asyncio.sleep(2.4)            # lo deja mostrando el final
                txt.offset = ft.Offset(0, 0)
                txt.update()
                await asyncio.sleep(1.9)
            except Exception:  # noqa: BLE001
                pass
            st["anim"] = False

        def disparar(*_):
            try:
                self.page.run_task(_reveal)
            except Exception:  # noqa: BLE001
                pass

        # long-press (celular) + hover (mouse). El TAP normal NO lo dispara → sigue editando/eligiendo.
        gd = ft.GestureDetector(content=clip, on_long_press=lambda e: disparar())
        return ft.Container(content=gd,
                            on_hover=lambda e: disparar() if getattr(e, "data", None) in ("true", True) else None)

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
        # Slide direccional marcado (como el arranque): el contenido entra desde el
        # lado según el cambio de tab (+der / −izq) con fade.
        # de izq→der (delta>0) el contenido entra desde la derecha y se mueve a la izq;
        # de der→izq entra desde la izquierda. SIN animate_offset al montar (si no, Flutter
        # anima 0→dx en el montaje = dirección al revés no determinística); se activa en el task.
        dx = 0.6 if delta > 0 else -0.6 if delta < 0 else 0.0
        contenido = self.subpage.build() if self.subpage is not None else self.views[self.tab].build()
        # animate_offset EN EL BUILD (si se setea post-montaje Flet no envuelve el widget →
        # el offset salta). `key` único por render = widget nuevo (evita reuse/jitter 0→dx).
        self._rk = getattr(self, "_rk", 0) + 1
        self._screen = ft.Container(
            key=f"scr{self._rk}", expand=True, padding=PAD(16, 12, 16, 8), content=contenido,
            offset=ft.Offset(dx, 0), opacity=0.0,
            animate_offset=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
            animate_opacity=ft.Animation(180))
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
        # La animación de entrada se dispara UN FRAME DESPUÉS de montar: si se cambia el
        # offset en el mismo tick, Flutter ve directo el estado final y no anima (quedaba
        # instantáneo). Con el delay hay un frame con el offset inicial → anima al destino.
        self.page.run_task(self._animar_entrada, self._screen, self._nav_pill)

    async def _animar_entrada(self, screen, pill):
        import asyncio
        await asyncio.sleep(0.05)   # que se pinte el frame inicial (offset de partida)
        # animate_offset ya viene del build → cambiar el offset acá dispara la animación.
        screen.offset = ft.Offset(0, 0)
        screen.opacity = 1.0
        pill.offset = ft.Offset(0, 0)   # desliza desde (prev-cur) hasta su celda
        for ctrl in (screen, pill):
            try:
                ctrl.update()
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
    # Pastilla azul ÚNICA que se DESLIZA de una celda a otra al cambiar de tab
    # (plana, sin sombra/glow/degradé). Stack de 2 capas: la pastilla (en el slot
    # ACTIVO, por eso queda alineada) + los íconos/labels encima. La animación es
    # SOLO el desplazamiento relativo: arranca en offset=(prev-cur) [celda previa] y
    # se lleva a 0. Forma: CÍRCULO si el activo es Inicio, cuadrado redondeado si no.
    _NAV_LADO = 48

    def _nav_icon_cell(self, sid, lbl, ic_out, ic_fill) -> ft.Control:
        t = self.t
        activo = self.tab == sid
        es_inicio = sid == "inicio"
        lado = self._NAV_LADO
        icono = ft.Container(
            width=lado, height=lado, alignment=ft.Alignment.CENTER,
            border_radius=(lado // 2 if es_inicio else 14),
            # anillo sutil para que el círculo de Inicio se vea cuando NO está activo
            border=(BALL(1.5, t["line2"]) if (es_inicio and not activo) else None),
            content=ft.Icon(ic_fill if activo else ic_out, size=23,
                            color=t["accent_ink"] if activo else t["faint"]))
        label = ft.Text(lbl, size=10, weight=ft.FontWeight.W_700,
                        color=t["accent"] if activo else t["faint"])
        inner = ft.Column([icono, label], spacing=2, tight=True,
                          horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        return ft.Container(expand=True, alignment=ft.Alignment.TOP_CENTER, content=inner,
                            on_click=lambda e, s=sid: self.set_tab(s))

    def _build_nav(self) -> ft.Control:
        t = self.t
        cur = NAV_IDS.index(self.tab) if self.tab in NAV_IDS else NAV_IDS.index("inicio")
        prev = getattr(self, "_nav_idx", cur)
        self._nav_idx = cur
        lado = self._NAV_LADO
        # Capa 0: pastilla en el slot ACTIVO (alineada). Círculo si el activo es Inicio.
        radio = lado // 2 if NAV_IDS[cur] == "inicio" else 14
        pastilla = ft.Container(width=lado, height=lado, border_radius=radio, bgcolor=t["accent"])
        self._nav_pill = ft.Container(
            key=f"pill{getattr(self, '_rk', 0)}", expand=True, alignment=ft.Alignment.TOP_CENTER,
            content=pastilla, offset=ft.Offset(prev - cur, 0),   # arranca en la celda previa
            animate_offset=ft.Animation(215, ft.AnimationCurve.EASE_IN_OUT))
        slots = [self._nav_pill if i == cur else ft.Container(expand=True) for i in range(len(NAV))]
        fila_pill = ft.Row(slots, vertical_alignment=ft.CrossAxisAlignment.START)
        # Capa 1: íconos + labels (transparentes) encima de la pastilla.
        fila_iconos = ft.Row([self._nav_icon_cell(*item) for item in NAV],
                             vertical_alignment=ft.CrossAxisAlignment.START)
        self._nav = ft.Container(
            height=74, bgcolor=t["nav_bg"], border=BEDGE(top=(1, t["line"])), padding=PADS(6, 8),
            content=ft.Stack([fila_pill, fila_iconos]))
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

        # Grip: tocar o deslizar hacia abajo cierra la hoja (sin X).
        grip = ft.GestureDetector(
            on_tap=lambda e: self.page.pop_dialog(),
            on_vertical_drag_end=lambda e: (self.page.pop_dialog()
                                            if (getattr(e, "primary_velocity", None) or 0) > 0 else None),
            content=ft.Container(alignment=ft.Alignment.CENTER, padding=PADS(10, 4), bgcolor=t["ground"],
                                 margin=MAR(bottom=6),
                                 content=ft.Container(width=44, height=5, border_radius=3,
                                                      bgcolor=t["line2"])))
        return ft.Column([
            grip,
            ft.Text("Configuración", size=19, weight=ft.FontWeight.W_800, color=t["ink"]),
            ft.Container(height=6), label("Apariencia"), ft.Container(height=8), theme_seg,
            ft.Container(height=14), label("Empresa"), ft.Container(height=8),
            setrow(ft.Icons.BUSINESS_OUTLINED, "Datos de la empresa",
                   "Razón social, CUIT, domicilio, moneda", accion=self._empresa_form),
            ft.Container(height=6), label("Facturación electrónica"), ft.Container(height=8),
            setrow(ft.Icons.RECEIPT_OUTLINED, "AFIP / ARCA (opcional)",
                   "Datos fiscales y conexión con ARCA", accion=self._abrir_afip),
            ft.Container(height=10),
            ft.Text(f"Vexa · v{VERSION}", size=11, color=t["faint"], text_align=ft.TextAlign.CENTER),
        ], spacing=0, scroll=ft.ScrollMode.HIDDEN, tight=True)

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
        # size_constraints sube el tope de altura (Flutter capa las hojas a ~9/16 por
        # defecto y cortaba AFIP/versión); así toma el alto del contenido completo.
        alto_max = int((self.page.height or 900) * 0.92)
        self._config_sheet = ft.BottomSheet(
            content=self._config_container(), show_drag_handle=False, bgcolor=t["ground"],
            size_constraints=ft.BoxConstraints(max_height=alto_max),
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

    def empresa_campos(self, emp: dict) -> list:
        """Campos del form de empresa, idénticos al onboarding de desktop
        (`desktop/ui/onboarding.py`). Compartido por Configuración y onboarding.
        La dirección se muestra separada en Calle/Número (se une al guardar)."""
        calle, numero = partir_direccion(emp.get("direccion"))
        return [
            {"key": "nombre", "label": "Nombre / razón social", "value": emp.get("nombre"),
             "hint": "Razón social / nombre del negocio"},
            [{"key": "nif", "label": "CUIT", "value": emp.get("nif"),
              "hint": "20-12345678-9", "format": "cuit"},
             {"key": "condicion_iva", "label": "Condición frente al IVA", "tipo": "dropdown",
              "value": emp.get("condicion_iva") or "", "options": [""] + list(CONDICIONES_IVA)}],
            [{"key": "calle", "label": "Calle", "value": calle, "hint": "Av. Corrientes"},
             {"key": "numero", "label": "Número", "value": numero, "hint": "1234"}],
            [{"key": "localidad", "label": "Localidad", "value": emp.get("localidad")},
             {"key": "provincia", "label": "Provincia", "tipo": "dropdown", "editable": True,
              "value": emp.get("provincia") or "", "options": [""] + list(PROVINCIAS_AR)}],
            [{"key": "telefono", "label": "Teléfono", "value": emp.get("telefono"),
              "hint": TELEFONO_EJEMPLO},
             {"key": "email", "label": "Email", "value": emp.get("email")}],
            {"key": "moneda", "label": "Moneda", "tipo": "dropdown",
             "value": emp.get("moneda") or "$", "options": list(MONEDAS)},
        ]

    def guardar_empresa(self, d: dict):
        """Transforma + persiste los datos de empresa (Calle/Número → dirección).
        Lanza ValueError si falta el nombre (open_form lo avisa). Los datos de AFIP
        se manejan aparte en la página de AFIP → no se tocan acá."""
        if not (d.get("nombre") or "").strip():
            raise ValueError("Ingresá el nombre o razón social de la empresa")
        d = dict(d)
        d["direccion"] = unir_direccion(d.pop("calle", ""), d.pop("numero", ""))
        e = self.db.get_datos_empresa()
        e.update(d)
        self.db.update_datos_empresa(e)
        set_moneda(e.get("moneda"))

    def _abrir_empresa_form(self):
        campos = self.empresa_campos(self.db.get_datos_empresa())
        self.open_form("Datos de la empresa", campos, on_save=self.guardar_empresa)

    def _abrir_afip(self):
        # Cerrar Configuración y abrir la página AFIP recién en su on_dismiss.
        self._pending_after_config = self._mostrar_afip
        self.page.pop_dialog()

    def _mostrar_afip(self):
        self.abrir_subpagina(AfipView(self))

    def set_theme(self, dark: bool):
        # Cambia el tema SIN cerrar la hoja: reconstruye el fondo (page.controls) y
        # re-tematiza el contenido completo de la hoja abierta.
        if self.dark == dark:
            return
        self.dark = dark
        self.db.set_config("tema", "oscuro" if dark else "claro")   # persiste la elección
        self.render()
        sheet = getattr(self, "_config_sheet", None)
        if sheet is not None:
            sheet.bgcolor = self.t["ground"]
            sheet.content = self._config_container()
            sheet.update()

    # ------------------------------------------------------------- selector
    def abrir_selector(self, titulo, opciones, on_select, valor=None):
        """Hoja inferior con búsqueda para elegir de una lista larga (provincia, etc.).
        Abre desde abajo (nunca tapa el input) y se cierra deslizando. `opciones`: lista
        de str; `on_select(valor)` recibe la opción elegida."""
        t = self.t
        lista = ft.Column(spacing=2, scroll=ft.ScrollMode.HIDDEN, expand=True)

        def elegir(v):
            self.page.pop_dialog()
            on_select(v)

        def fila(o):
            sel = o == (valor or "")
            return ft.Container(
                padding=PADS(11, 14), ink=True, border_radius=10,
                bgcolor=soft(t["accent"], 0.12) if sel else None,
                on_click=lambda e, v=o: elegir(v),
                content=ft.Row([
                    ft.Text(o or "(sin especificar)", size=14, expand=True,
                            color=t["accent"] if sel else t["ink"]),
                    ft.Icon(ft.Icons.CHECK, size=16, color=t["accent"]) if sel else ft.Container(),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER))

        def fill(q=""):
            q = (q or "").lower().strip()
            its = [o for o in opciones if not q or q in (o or "").lower()]
            lista.controls = [fila(o) for o in its] or [
                ft.Container(padding=20, content=ft.Text("Sin resultados", color=t["faint"]))]

        buscar = ft.TextField(
            hint_text="Buscar…", prefix_icon=ft.Icons.SEARCH, border_radius=12, filled=True,
            bgcolor=t["surface2"], border_color=t["line2"], focused_border_color=t["accent"],
            color=t["ink"], hint_style=ft.TextStyle(color=t["faint"]), text_size=14,
            content_padding=PADS(10, 13),
            on_change=lambda e: (fill(e.control.value), lista.update()))
        fill()
        cuerpo = ft.Column([
            ft.Container(alignment=ft.Alignment.CENTER, margin=MAR(bottom=8),
                         content=ft.Container(width=40, height=4, border_radius=2, bgcolor=t["line2"])),
            ft.Text(titulo, size=18, weight=ft.FontWeight.W_800, color=t["ink"]),
            ft.Container(height=10), buscar, ft.Container(height=10),
            ft.Container(content=lista, height=320),
        ], spacing=0, tight=True)
        cont = ft.Container(padding=PAD(16, 12, 16, 20), content=cuerpo, bgcolor=t["ground"],
                            border_radius=24)
        self.page.show_dialog(ft.BottomSheet(content=cont, bgcolor=t["ground"],
                                             show_drag_handle=False, draggable=True))

    def abrir_selector_full(self, titulo, opciones, on_select, on_nuevo=None,
                            nuevo_prefix="Usar", valor=None):
        """Selector a PANTALLA COMPLETA con búsqueda (ocupa toda la pestaña). `opciones`:
        lista de (label, valor). `on_select(valor)`. Si `on_nuevo`, al tipear aparece arriba
        una opción `{nuevo_prefix} «texto»` que llama `on_nuevo(texto)` (crear cliente / nombre
        libre)."""
        t = self.t
        lista = ft.Column(spacing=2, scroll=ft.ScrollMode.HIDDEN, expand=True)

        def _u():
            try:
                lista.update()
            except Exception:  # noqa: BLE001
                pass

        def elegir(v):
            self.page.pop_dialog()
            on_select(v)

        def crear(txt):
            self.page.pop_dialog()
            if on_nuevo:
                on_nuevo(txt)

        def fila(label, v):
            sel = valor is not None and v == valor
            return ft.Container(
                padding=PADS(13, 14), ink=True, border_radius=10,
                bgcolor=soft(t["accent"], 0.12) if sel else None,
                on_click=lambda e, val=v: elegir(val),
                content=ft.Row([ft.Text(str(label), size=14, expand=True,
                                        color=t["accent"] if sel else t["ink"]),
                                ft.Icon(ft.Icons.CHECK, size=16, color=t["accent"]) if sel else ft.Container()],
                               vertical_alignment=ft.CrossAxisAlignment.CENTER))

        def fila_nuevo(txt):
            return ft.Container(
                padding=PADS(13, 14), ink=True, border_radius=10, bgcolor=soft(t["accent"], 0.12),
                on_click=lambda e: crear(txt),
                content=ft.Row([ft.Icon(ft.Icons.ADD, size=18, color=t["accent"]),
                                ft.Text(f'{nuevo_prefix} «{txt}»', size=14, weight=ft.FontWeight.W_700,
                                        color=t["accent"], expand=True)],
                               spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER))

        def fill(q=""):
            ql = (q or "").lower().strip()
            items = [(l, v) for (l, v) in opciones if not ql or ql in str(l).lower()]
            ctrls = []
            if on_nuevo and ql:
                ctrls.append(fila_nuevo(q.strip()))
            ctrls += [fila(l, v) for (l, v) in items]
            if not ctrls:
                ctrls = [ft.Container(padding=20, content=ft.Text("Sin resultados", color=t["faint"]))]
            lista.controls = ctrls

        buscar = ft.TextField(
            hint_text="Buscar…", prefix_icon=ft.Icons.SEARCH, border_radius=12, filled=True,
            autofocus=True, bgcolor=t["surface2"], border_color=t["line2"],
            focused_border_color=t["accent"], color=t["ink"], hint_style=ft.TextStyle(color=t["faint"]),
            text_size=14, content_padding=PADS(11, 13),
            on_change=lambda e: (fill(e.control.value), _u()))
        fill()
        header = ft.Row([ft.Text(titulo, size=19, weight=ft.FontWeight.W_800, color=t["ink"], expand=True),
                         ft.IconButton(ft.Icons.CLOSE, icon_color=t["muted"],
                                       on_click=lambda e: self.page.pop_dialog())],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER)
        cont = ft.Container(
            padding=PAD(18, 14, 18, 18), bgcolor=t["ground"], expand=True,
            content=ft.Column([header, ft.Container(height=12), buscar, ft.Container(height=12), lista],
                              spacing=0, expand=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH))
        self.page.show_dialog(ft.BottomSheet(content=cont, bgcolor=t["ground"], fullscreen=True,
                                             dismissible=False, show_drag_handle=False))

    # -------------------------------------------------------- formulario genérico
    def open_form(self, titulo, campos, on_save, on_delete=None, guardar_label="Guardar", full=True,
                  borrar_texto="¿Seguro que querés eliminar?"):
        """Formulario full-screen. `campos`: items sueltos o listas [c1,c2] (2 col).
        Tipos: text|number|multiline|dropdown|chips|check. dropdown.options: str o (label,valor),
        editable=True para escribir/filtrar. text.format='cuit' formatea en vivo. chips.format='cuit'
        formatea al agregar. check: casilla que despliega los campos de `reveal` (mismos formatos
        que `campos`) al marcarse; su valor es 0/1. Se construye UNA sola vez; chips/reveal/aviso se
        actualizan puntualmente. Escape/Cancelar/grip cierran pasando por el chequeo de cambios."""
        t = self.t

        def _expand(items):  # aplana items sueltos, filas de 2 col y los reveal de los check
            out = []
            for item in items:
                for c in (item if isinstance(item, list) else [item]):
                    out.append(c)
                    if c.get("tipo") == "check":
                        out.extend(_expand(c.get("reveal", [])))
            return out
        flat = _expand(campos)
        estado = {"dirty": False}
        pendiente = {"fn": None}   # acción a correr en on_dismiss (evita scrim negro de pop+render)
        chips, chip_rows, chip_inputs, chip_fmt, ctrls = {}, {}, {}, {}, {}
        checks = {}  # key -> {"on": bool} para los campos tipo check

        def mark_dirty(*_):
            estado["dirty"] = True

        def _fmt_text_cuit(key):
            estado["dirty"] = True
            tf = ctrls[key][1]
            nuevo = formatear_cuit(tf.value or "")
            if nuevo != tf.value:
                tf.value = nuevo
                try:
                    tf.update()
                except Exception:  # noqa: BLE001
                    pass

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
            if tipo == "check":
                checks[key] = {"on": bool(val)}
                ctrls[key] = ("check", None)
            elif tipo == "chips":
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
            elif tipo == "dropdown" and c.get("editable"):
                # Editable (ej. provincia): picker en hoja inferior. El autocomplete de
                # Flet abría el listado ENCIMA del input; el picker abre desde abajo.
                opciones = [o if not isinstance(o, tuple) else o[0] for o in c.get("options", [])]
                ctrls[key] = ("picker", {"value": (val if val not in (None,) else ""),
                                         "opciones": opciones, "label": c.get("label"), "txt": None})
            elif tipo == "dropdown":
                pairs = [(o, o) if not isinstance(o, tuple) else o for o in c.get("options", [])]
                cur = next((i for i, (lbl, v) in enumerate(pairs) if v == val), None)
                dd = ft.Dropdown(
                    value=(str(cur) if cur is not None else None), border_radius=12,
                    options=[ft.DropdownOption(key=str(i), text=str(lbl)) for i, (lbl, v) in enumerate(pairs)],
                    on_select=mark_dirty, border_color=t["line2"], filled=True, bgcolor=t["surface2"],
                    text_size=14, content_padding=PADS(11, 13), text_style=ft.TextStyle(color=t["ink"]))
                ctrls[key] = ("dropdown", dd, pairs)
            else:
                on_ch = (lambda e, k=key: _fmt_text_cuit(k)) if c.get("format") == "cuit" else mark_dirty
                tf = ft.TextField(
                    value=("" if val is None else str(val)), border_radius=12,
                    keyboard_type=ft.KeyboardType.NUMBER if tipo == "number" else ft.KeyboardType.TEXT,
                    multiline=(tipo == "multiline"), min_lines=2 if tipo == "multiline" else 1,
                    max_lines=4 if tipo == "multiline" else 1, on_change=on_ch,
                    hint_text=c.get("hint"), hint_style=ft.TextStyle(color=t["faint"]),
                    border_color=t["line2"], focused_border_color=t["accent"], filled=True,
                    bgcolor=t["surface2"], color=t["ink"], text_size=14, content_padding=PADS(11, 13))
                ctrls[key] = (tipo, tf)

        def _render_group(items):
            """Construye la lista de controles de una lista de campos (items sueltos
            o filas [c1, c2] de 2 columnas). Reusado por el cuerpo y por los reveal."""
            out = []
            for item in items:
                if isinstance(item, list):
                    out.append(ft.Row([ft.Container(expand=True, content=_field(c)) for c in item],
                                       spacing=12, vertical_alignment=ft.CrossAxisAlignment.START))
                else:
                    out.append(_field(item))
                out.append(ft.Container(height=13))
            return out

        def _check_field(c):
            key = c["key"]
            st = checks[key]

            def marca():  # el cuadradito, según el estado
                return ft.Container(
                    width=22, height=22, border_radius=6, border=BALL(1.6, t["line2"]),
                    bgcolor=t["accent"] if st["on"] else t["surface2"], alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.CHECK, size=15, color=t["accent_ink"]) if st["on"] else None)

            box = marca()
            reveal = ft.Column(_render_group(c.get("reveal", [])), spacing=0, visible=st["on"],
                               horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

            def toggle(e):
                st["on"] = not st["on"]
                estado["dirty"] = True
                nueva = marca()
                box.bgcolor, box.content = nueva.bgcolor, nueva.content
                reveal.visible = st["on"]
                try:
                    box.update()
                    reveal.update()
                except Exception:  # noqa: BLE001
                    pass

            fila = ft.Container(
                ink=True, border_radius=10, padding=PADS(6, 4), on_click=toggle,
                content=ft.Row([box, ft.Text(c["label"], size=13.5, weight=ft.FontWeight.W_600,
                                              color=t["ink"], expand=True)],
                               spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER))
            partes = [fila]
            if c.get("hint"):
                partes.append(ft.Container(padding=PAD(38, 0, 0, 6),
                                           content=ft.Text(c["hint"], size=11.5, color=t["muted"])))
            partes.append(reveal)
            return ft.Column(partes, spacing=4, tight=True,
                             horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

        def _picker_field(c):
            key = c["key"]
            st = ctrls[key][1]
            ph = "Elegí una opción"
            st["txt"] = ft.Text(st["value"] or ph, size=14, expand=True,
                                color=t["ink"] if st["value"] else t["faint"])

            def abrir(_e):
                def elegir(v):
                    st["value"] = v
                    estado["dirty"] = True
                    st["txt"].value = v or ph
                    st["txt"].color = t["ink"] if v else t["faint"]
                    try:
                        st["txt"].update()
                    except Exception:  # noqa: BLE001
                        pass
                self.abrir_selector(st["label"], st["opciones"], elegir, valor=st["value"])

            campo = ft.Container(
                on_click=abrir, ink=True, bgcolor=t["surface2"], border=BALL(1, t["line2"]),
                border_radius=12, padding=PADS(13, 13),
                content=ft.Row([st["txt"], ft.Icon(ft.Icons.ARROW_DROP_DOWN, color=t["faint"])],
                               vertical_alignment=ft.CrossAxisAlignment.CENTER))
            label = ft.Text((c["label"] or "").upper(), size=10.5, weight=ft.FontWeight.W_800,
                            color=t["faint"])
            return ft.Column([label, campo], spacing=5, tight=True,
                             horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

        def _field(c):
            key, tipo = c["key"], c.get("tipo", "text")
            if tipo == "check":
                return _check_field(c)
            if tipo == "dropdown" and c.get("editable"):
                return _picker_field(c)
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
                if tipo == "check":
                    data[key] = 1 if checks[key]["on"] else 0
                elif tipo == "picker":
                    data[key] = (meta[1].get("value") or None)
                elif tipo == "chips":
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

        def _run_pendiente(_e=None):
            # Corre cuando la hoja YA cerró → render() sin dejar scrim negro.
            fn = pendiente["fn"]
            pendiente["fn"] = None
            if fn:
                fn()

        def guardar(_e):
            data = collect()
            try:
                on_save(data)
            except ValueError as ve:
                self.snack(str(ve))
                return
            except Exception as ex:  # noqa: BLE001
                pendiente["fn"] = lambda ex=ex: self.snack(f"Error al guardar: {ex}")
                _close()
                return
            pendiente["fn"] = lambda: (self.render(), self.snack("Guardado"))
            _close()

        def borrar(_e):
            try:
                on_delete()
            except Exception as ex:  # noqa: BLE001
                self.snack(f"Error al eliminar: {ex}")
                return
            pendiente["fn"] = lambda: (self.render(), self.snack("Eliminado"))
            _close()

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

        def _hide_del(*_):
            banner_del.visible = False
            try:
                banner_del.update()
            except Exception:  # noqa: BLE001
                pass

        def _pedir_borrar(*_):
            banner_del.visible = True
            try:
                banner_del.update()
            except Exception:  # noqa: BLE001
                pass

        # Confirmación de borrado: mismo formato que el aviso de cambios, en rojo suave.
        # Base OPACA (surface) + tinte rojo encima, así no se transparenta el form de atrás.
        banner_del = ft.Container(
            visible=False, top=8, left=12, right=12, bgcolor=t["surface"], border_radius=14,
            content=ft.Container(
                bgcolor=soft(t["danger"], 0.12), border=BALL(1, soft(t["danger"], 0.5)),
                border_radius=14, padding=PADS(12, 16),
                content=ft.Column([
                    ft.Text(borrar_texto, size=13, weight=ft.FontWeight.W_600, color=t["ink"]),
                    ft.Container(height=8),
                    ft.Row([
                        ft.Container(content=ft.Text("Cancelar", color=t["muted"], size=13,
                                                     weight=ft.FontWeight.W_600), padding=PADS(8, 12),
                                     ink=True, border_radius=10, on_click=_hide_del),
                        ft.Container(expand=True),
                        ft.Container(content=ft.Text("Eliminar", color="#ffffff", size=13,
                                                     weight=ft.FontWeight.W_700), bgcolor=t["danger"],
                                     border_radius=10, padding=PADS(8, 16), ink=True, on_click=borrar),
                    ]),
                ], spacing=0, tight=True)))

        cuerpo = _render_group(campos)

        acciones = [ft.Container(content=ft.Text("Cancelar", color=t["muted"], size=14,
                                                 weight=ft.FontWeight.W_600),
                                 padding=PADS(12, 14), on_click=try_close, ink=True, border_radius=12),
                    ft.Container(expand=True)]
        if on_delete is not None:
            acciones.append(ft.Container(width=50, height=48, bgcolor=soft(t["danger"], 0.12),
                                         border_radius=13, alignment=ft.Alignment.CENTER, ink=True,
                                         on_click=_pedir_borrar,
                                         content=ft.Icon(ft.Icons.DELETE_OUTLINE, color=t["danger"], size=20)))
            acciones.append(ft.Container(width=8))
        acciones.append(ft.Container(bgcolor=t["accent"], border_radius=13, padding=PADS(13, 22),
                                     ink=True, on_click=guardar,
                                     content=ft.Text(guardar_label, color=t["accent_ink"],
                                                     weight=ft.FontWeight.W_700, size=14)))

        # Grip: tocar o deslizar hacia abajo cierra (pasando por el chequeo de cambios).
        # El contenedor lleva bgcolor (opaco) para ser hit-testable en toda su área.
        grip = ft.GestureDetector(
            on_tap=lambda e: try_close(),
            on_vertical_drag_end=lambda e: (try_close() if (getattr(e, "primary_velocity", None) or 0) > 0 else None),
            content=ft.Container(alignment=ft.Alignment.CENTER, padding=PADS(12, 4), bgcolor=t["ground"],
                                 content=ft.Container(width=44, height=5, border_radius=3,
                                                      bgcolor=t["line2"])))
        # full=True → fullscreen. full=False → media pantalla con ALTO ACOTADO: los campos
        # scrollean y el footer (Guardar) queda SIEMPRE fijo abajo y visible (responsive).
        scroll_col = ft.Column(
            [ft.Text(titulo, size=20, weight=ft.FontWeight.W_800, color=t["ink"]),
             ft.Container(height=14), *cuerpo],
            spacing=0, scroll=ft.ScrollMode.HIDDEN, expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        footer = ft.Container(padding=PAD(0, 12, 0, 0), border=BEDGE(top=(1, t["line"])),
                              content=ft.Row(acciones, vertical_alignment=ft.CrossAxisAlignment.CENTER))
        cuerpo_col = ft.Column([grip, ft.Container(expand=True, content=scroll_col), footer],
                               spacing=0, expand=True,
                               horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        if full:
            base = ft.Container(padding=PAD(18, 8, 18, 18), bgcolor=t["ground"], expand=True,
                                content=cuerpo_col)
            sheet = ft.BottomSheet(
                content=ft.Stack([base, banner, banner_del], expand=True), bgcolor=t["ground"],
                fullscreen=True, dismissible=False, draggable=False, show_drag_handle=False,
                on_dismiss=_run_pendiente)
        else:
            # Media pantalla. size_constraints SUBE el tope (Flutter capa a ~9/16 y cortaba el
            # footer/precio). dismissible=True → tocar afuera cierra (además del grip/Cancelar).
            alto = int((self.page.height or 900) * 0.66)
            base = ft.Container(padding=PAD(18, 8, 18, 20), bgcolor=t["ground"], height=alto,
                                content=cuerpo_col)
            sheet = ft.BottomSheet(
                content=ft.Stack([base, banner, banner_del]), bgcolor=t["ground"],
                fullscreen=False, dismissible=True, draggable=False, show_drag_handle=False,
                size_constraints=ft.BoxConstraints(max_height=alto + 12),
                on_dismiss=_run_pendiente)
        self._form_escape = try_close
        self.page.show_dialog(sheet)

    # ------------------------------------------------------------- navegación
    def set_tab(self, sid: str):
        if sid != self.tab or self.subpage is not None:
            self.subpage = None
            self.tab = sid
            self.render()

    def abrir_subpagina(self, view):
        """Muestra una página full-screen fuera del nav (mantiene header + barra)."""
        self.subpage = view
        self.render()

    def cerrar_subpagina(self, reopen_config: bool = True):
        """Cierra la subpágina y vuelve. Por defecto reabre Configuración (ej. AFIP,
        que se abre desde ahí); con reopen_config=False vuelve al tab actual (ej. import)."""
        self.subpage = None
        self.render()
        if reopen_config:
            self.open_config()

    def _on_swipe(self, e):
        v = getattr(e, "primary_velocity", None) or 0
        if v == 0:
            return
        i = NAV_IDS.index(self.tab)
        i = max(0, min(len(NAV_IDS) - 1, i + (-1 if v > 0 else 1)))
        self.set_tab(NAV_IDS[i])
