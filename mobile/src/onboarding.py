"""Onboarding de primera ejecución (mobile).

Dos pasos con slide horizontal (sin modal): (1) bienvenida con la V que sube y el
botón "Comenzar"; (2) los datos de empresa (mismos campos que el escritorio, menos
AFIP) con "Guardar y empezar". Se muestra solo si no hay empresa (nombre vacío) y no
está la flag `onboarding_done`; al completarse marca la flag y entra a la app. Si la
base estaba vacía NO se siembra el demo.
"""
from __future__ import annotations

import flet as ft

from theme import PAD, PADS, BALL, soft
from logo import v_logo
from vexa_core.utils.helpers import (CONDICIONES_IVA, MONEDAS, PROVINCIAS_AR, formatear_cuit)


def necesita_onboarding(db) -> bool:
    nombre = (db.get_datos_empresa().get("nombre") or "").strip()
    return not nombre and not db.get_config("onboarding_done")


class Onboarding:
    """Primera pantalla: bienvenida animada → (slide) datos de empresa → app."""

    def __init__(self, app):
        self.app = app
        self.page = app.page
        self.db = app.db
        self._ctrls = {}   # key -> control del form (para leer al guardar)

    # --------------------------------------------------------------- arranque
    def start(self):
        t = self.app.t
        self.page.theme_mode = ft.ThemeMode.DARK if self.app.dark else ft.ThemeMode.LIGHT
        self.page.bgcolor = t["ground"]

        self._welcome = ft.Container(
            left=0, top=0, right=0, bottom=0, offset=ft.Offset(0, 0),
            animate_offset=ft.Animation(360, ft.AnimationCurve.EASE_IN_OUT),
            content=self._pantalla_bienvenida())
        self._form = ft.Container(
            left=0, top=0, right=0, bottom=0, offset=ft.Offset(1, 0),  # fuera, a la derecha
            animate_offset=ft.Animation(360, ft.AnimationCurve.EASE_IN_OUT),
            bgcolor=t["ground"], content=self._pantalla_form())

        self.page.controls[:] = [ft.Container(expand=True, bgcolor=t["ground"],
                                              content=ft.Stack([self._welcome, self._form], expand=True))]
        self.page.update()
        self.page.run_task(self._animar_v)

    async def _animar_v(self):
        import asyncio
        await asyncio.sleep(0.55)      # la V se ve centrada un instante
        self._bloque.offset = ft.Offset(0, -0.26)   # sube un poco
        self.page.update()
        await asyncio.sleep(0.28)
        self._boton_wrap.opacity = 1
        self._boton_wrap.offset = ft.Offset(0, 0)
        self.page.update()

    # ------------------------------------------------------ paso 1: bienvenida
    def _pantalla_bienvenida(self) -> ft.Control:
        t = self.app.t
        columna = ft.Column(
            [ft.Row([v_logo(108, t["v_ink"], t["dot"])], alignment=ft.MainAxisAlignment.CENTER),
             ft.Container(height=26),
             ft.Text("¡Bienvenido a Vexa!", size=27, weight=ft.FontWeight.W_800,
                     color=t["ink"], text_align=ft.TextAlign.CENTER),
             ft.Container(height=10),
             ft.Text("Configurá tu empresa para empezar a facturar.", size=15,
                     color=t["muted"], text_align=ft.TextAlign.CENTER)],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0, tight=True)
        self._bloque = ft.Container(
            content=columna, offset=ft.Offset(0, 0),
            animate_offset=ft.Animation(700, ft.AnimationCurve.EASE_IN_OUT))
        centro = ft.Container(content=self._bloque, alignment=ft.Alignment.CENTER,
                              expand=True, padding=PADS(0, 36))

        boton = ft.Container(
            bgcolor=t["accent"], border_radius=15, padding=PADS(17, 0), ink=True,
            alignment=ft.Alignment.CENTER, on_click=lambda e: self._ir_a_form(),
            content=ft.Text("Comenzar", color=t["accent_ink"], size=16, weight=ft.FontWeight.W_800))
        self._boton_wrap = ft.Container(
            left=24, right=24, bottom=44, opacity=0, offset=ft.Offset(0, 0.7),
            animate_opacity=ft.Animation(450), animate_offset=ft.Animation(550, ft.AnimationCurve.EASE_OUT),
            content=boton)
        return ft.Stack([centro, self._boton_wrap], expand=True)

    def _ir_a_form(self):
        # Slide: la bienvenida sale por la izquierda y el form entra desde la derecha.
        self._welcome.offset = ft.Offset(-1, 0)
        self._form.offset = ft.Offset(0, 0)
        self.page.update()

    def _volver_bienvenida(self):
        self._welcome.offset = ft.Offset(0, 0)
        self._form.offset = ft.Offset(1, 0)
        self.page.update()

    # ------------------------------------------------------- paso 2: datos
    def _pantalla_form(self) -> ft.Control:
        t = self.app.t
        atras = ft.Container(
            ink=True, border_radius=10, padding=PADS(6, 6), on_click=lambda e: self._volver_bienvenida(),
            content=ft.Icon(ft.Icons.ARROW_BACK, size=22, color=t["ink"]))

        campos = ft.Column([
            self._campo("nombre", "Nombre / razón social", hint="Razón social / nombre del negocio"),
            self._fila([("nif", "CUIT", {"hint": "20-12345678-9", "cuit": True}),
                        ("condicion_iva", "Condición frente al IVA",
                         {"dd": [""] + list(CONDICIONES_IVA)})]),
            self._fila([("calle", "Calle", {"hint": "Av. Corrientes"}),
                        ("numero", "Número", {"hint": "1234"})]),
            self._fila([("localidad", "Localidad", {}),
                        ("provincia", "Provincia", {"picker": [""] + list(PROVINCIAS_AR)})]),
            self._fila([("telefono", "Teléfono", {"hint": "+54 9 11 5555-5555"}),
                        ("email", "Email", {})]),
            self._campo("moneda", "Moneda", dd=list(MONEDAS)),
        ], spacing=13, horizontal_alignment=ft.CrossAxisAlignment.STRETCH, tight=True)

        guardar = ft.Container(
            bgcolor=t["accent"], border_radius=14, padding=PADS(15, 0), ink=True,
            alignment=ft.Alignment.CENTER, on_click=self._guardar,
            content=ft.Text("Guardar y empezar", color=t["accent_ink"], size=15.5,
                            weight=ft.FontWeight.W_800))

        scroll = ft.Column([
            ft.Row([atras], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=6),
            ft.Text("Datos de tu empresa", size=24, weight=ft.FontWeight.W_800, color=t["ink"]),
            ft.Text("Aparecen en tus comprobantes. Podés cambiarlos después en Configuración.",
                    size=12.5, color=t["muted"]),
            ft.Container(height=18),
            campos,
            ft.Container(height=22),
            guardar,
            ft.Container(height=16),
        ], spacing=0, scroll=ft.ScrollMode.HIDDEN, expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        return ft.Container(padding=PAD(22, 18, 22, 12), expand=True, bgcolor=t["ground"], content=scroll)

    # ---------------------------------------------------------- helpers form
    def _fmt_cuit(self, key):
        tf = self._ctrls[key]
        nuevo = formatear_cuit(tf.value or "")
        if nuevo != tf.value:
            tf.value = nuevo
            try:
                tf.update()
            except Exception:  # noqa: BLE001
                pass

    def _input(self, key, opts) -> ft.Control:
        t = self.app.t
        picker = opts.get("picker")
        if picker is not None:
            ph = "Elegí una opción"
            st = {"value": "", "opciones": list(picker), "txt": None}
            st["txt"] = ft.Text(ph, size=14, expand=True, color=t["faint"])
            titulo_sel = opts.get("_label", "Elegí")

            def abrir(_e):
                def elegir(v):
                    st["value"] = v
                    st["txt"].value = v or ph
                    st["txt"].color = t["ink"] if v else t["faint"]
                    try:
                        st["txt"].update()
                    except Exception:  # noqa: BLE001
                        pass
                self.app.abrir_selector(titulo_sel, st["opciones"], elegir, valor=st["value"])

            self._ctrls[key] = ("picker", st)
            return ft.Container(
                on_click=abrir, ink=True, bgcolor=t["surface2"], border=BALL(1, t["line2"]),
                border_radius=12, padding=PADS(13, 13),
                content=ft.Row([st["txt"], ft.Icon(ft.Icons.ARROW_DROP_DOWN, color=t["faint"])],
                               vertical_alignment=ft.CrossAxisAlignment.CENTER))
        dd = opts.get("dd")
        if dd is not None:
            pairs = [(o, o) if not isinstance(o, tuple) else o for o in dd]
            ctrl = ft.Dropdown(
                value="0", border_radius=12, editable=bool(opts.get("editable")),
                enable_filter=bool(opts.get("editable")), border_color=t["line2"], filled=True,
                bgcolor=t["surface2"], text_size=14, content_padding=PADS(11, 13),
                text_style=ft.TextStyle(color=t["ink"]),
                options=[ft.DropdownOption(key=str(i), text=str(lbl)) for i, (lbl, _v) in enumerate(pairs)])
            self._ctrls[key] = ("dd", ctrl, pairs)
            return ctrl
        on_ch = (lambda e, k=key: self._fmt_cuit(k)) if opts.get("cuit") else None
        tf = ft.TextField(
            border_radius=12, hint_text=opts.get("hint"), on_change=on_ch,
            hint_style=ft.TextStyle(color=t["faint"]), border_color=t["line2"],
            focused_border_color=t["accent"], filled=True, bgcolor=t["surface2"], color=t["ink"],
            text_size=14, content_padding=PADS(11, 13))
        self._ctrls[key] = tf
        return tf

    def _label(self, texto) -> ft.Control:
        return ft.Text((texto or "").upper(), size=10.5, weight=ft.FontWeight.W_800,
                       color=self.app.t["faint"])

    def _campo(self, key, label, hint=None, dd=None) -> ft.Control:
        opts = {"hint": hint}
        if dd is not None:
            opts["dd"] = dd
        return ft.Column([self._label(label), self._input(key, opts)], spacing=5, tight=True,
                         horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    def _fila(self, items) -> ft.Control:
        cols = []
        for key, label, opts in items:
            o = {**opts, "_label": label}
            cols.append(ft.Container(expand=True, content=ft.Column(
                [self._label(label), self._input(key, o)], spacing=5, tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH)))
        return ft.Row(cols, spacing=12, vertical_alignment=ft.CrossAxisAlignment.START)

    def _collect(self) -> dict:
        data = {}
        for key, meta in self._ctrls.items():
            if isinstance(meta, tuple) and meta[0] == "dd":
                _tag, ctrl, pairs = meta
                v = ctrl.value
                data[key] = pairs[int(v)][1] if v is not None else None
            elif isinstance(meta, tuple) and meta[0] == "picker":
                data[key] = meta[1].get("value") or None
            else:
                data[key] = (meta.value or "").strip() or None
        return data

    def _guardar(self, _e=None):
        data = self._collect()
        try:
            self.app.guardar_empresa(data)   # valida nombre + une dirección + persiste
        except ValueError as ve:
            self.app.snack(str(ve))
            return
        self.db.set_config("onboarding_done", "1")
        self.app.render()                    # entra a la app (reemplaza page.controls)
        self.app.snack("¡Listo! Ya podés empezar a facturar")
