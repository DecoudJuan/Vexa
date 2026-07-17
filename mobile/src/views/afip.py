"""Página AFIP / ARCA (subpágina full-screen de Configuración).

Réplica de la solapa AFIP del escritorio (`desktop/ui/configuracion.py` + guía
`desktop/ui/ayuda_arca.py`): datos fiscales (punto de venta, ingresos brutos,
inicio de actividades), entorno, certificado y clave privada. Arriba una flecha
para volver al menú. El botón "Cómo conectar con ARCA" abre desde abajo una hoja
con el tutorial paso a paso.

La *conexión* real con ARCA (autorizar, CAE, QR) llega en la Fase 6.3; esta página
ya recolecta y guarda los datos.
"""
from __future__ import annotations

import os

import flet as ft

from theme import PAD, PADS, MAR, BALL, BEDGE, soft
from widgets import titulo, clabel

_ENTORNOS = [("Homologación (pruebas)", "homologacion"), ("Producción", "produccion")]

# Guía paso a paso (portada de desktop/ui/ayuda_arca.py; <b> se quita al render).
_INTRO = ("Para emitir facturas electrónicas válidas hay que vincular Vexa con "
          "ARCA (ex AFIP). Seguí estos pasos:")
_PASOS = [
    ("Antes de empezar",
     "Necesitás tu CUIT y tu Clave Fiscal (nivel 3 o superior). El trámite es gratis y se "
     "hace una sola vez. Si nunca usaste la Clave Fiscal, se gestiona en la web de ARCA o "
     "en un cajero de tu banco."),
    ("Elegí el entorno",
     "Arriba, en Entorno, dejá Homologación (pruebas) para practicar sin emitir comprobantes "
     "reales. Cuando todo funcione, cambiás a Producción."),
    ("Generá tu clave y el pedido de certificado",
     "En una PC, abrí una consola y ejecutá estos dos comandos, reemplazando el CUIT y el "
     "nombre por los tuyos:"),
    ("Pedí el certificado en ARCA",
     "Entrá a ARCA con tu Clave Fiscal y buscá el servicio «Administración de Certificados "
     "Digitales» (para pruebas es el ambiente de homologación). Subí el archivo vexa.csr y "
     "descargá el certificado que te genera (vexa.crt)."),
    ("Autorizá el certificado para facturar",
     "En «Administrador de Relaciones de Clave Fiscal» agregá el servicio «Facturación "
     "Electrónica» y asocialo al certificado que creaste. Sin este paso, ARCA no deja usar "
     "el web service."),
    ("Creá tu punto de venta",
     "En «ABM de Puntos de Venta» creá uno de tipo «Web Services» (es distinto del que usa la "
     "web de Comprobantes en línea). Anotá el número, por ejemplo 0001."),
    ("Cargá los datos en Vexa",
     "Acá arriba completá: Certificado (vexa.crt), Clave privada (vexa.key), Punto de venta y "
     "Entorno. En la próxima versión vas a poder tocar «Probar conexión» para confirmar."),
    ("¡Listo para facturar!",
     "Cuando emitas una factura, usá «Autorizar en AFIP»: Vexa le pide el CAE a ARCA y le "
     "agrega el código QR al PDF, dejándolo como comprobante válido."),
]
_COMANDO = ('openssl genrsa -out vexa.key 2048\n'
            'openssl req -new -key vexa.key \\\n'
            '  -subj "/C=AR/O=TU NOMBRE/serialNumber=CUIT 20123456789/CN=vexa" \\\n'
            '  -out vexa.csr')
_WEB_ARCA = "https://www.arca.gob.ar"


class AfipView:
    def __init__(self, app):
        self.app = app
        e = app.db.get_datos_empresa()
        self._afip_on = bool(e.get("afip_habilitado"))
        self._entorno = app.db.get_config("afip_entorno") or "homologacion"
        self._cert_path = app.db.get_config("afip_cert_path") or ""
        self._key_path = app.db.get_config("afip_key_path") or ""
        self._e = e

    # ------------------------------------------------------------------ build
    def build(self) -> ft.Control:
        t = self.app.t
        e = self._e

        # Flechita para volver, debajo del header (a la altura del logo).
        volver = ft.Container(
            ink=True, border_radius=10, padding=PADS(6, 6), on_click=lambda _e: self.app.cerrar_subpagina(),
            content=ft.Row([ft.Icon(ft.Icons.ARROW_BACK, size=20, color=t["ink"]),
                            ft.Text("Configuración", size=13.5, weight=ft.FontWeight.W_700,
                                    color=t["muted"])], spacing=8, tight=True,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER))

        # Casilla habilitar (mismo tratamiento plano del resto).
        self._box = self._marca()
        toggle = ft.Container(
            ink=True, border_radius=12, padding=PADS(10, 12), bgcolor=t["surface"],
            border=BALL(1, t["line"]), on_click=self._toggle,
            content=ft.Row([self._box, ft.Text("Habilitar facturación electrónica (AFIP)",
                                                size=14, weight=ft.FontWeight.W_700, color=t["ink"],
                                                expand=True)],
                           spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER))

        self._dd_entorno = self._dropdown_entorno()
        self._tf_pv = self._campo(e.get("punto_venta"), "Ej. 0001", num=False)
        self._tf_ib = self._campo(e.get("ingresos_brutos"))
        self._tf_ia = self._campo(e.get("inicio_actividades"), "Ej. 01/2020")
        self._cert_txt = ft.Text(self._nombre(self._cert_path), size=13, color=t["ink"], expand=True,
                                 no_wrap=True)
        self._key_txt = ft.Text(self._nombre(self._key_path), size=13, color=t["ink"], expand=True,
                                no_wrap=True)

        guardar = ft.Container(
            bgcolor=t["accent"], border_radius=13, padding=PADS(14, 22), ink=True, on_click=self._guardar,
            alignment=ft.Alignment.CENTER,
            content=ft.Text("Guardar", color=t["accent_ink"], weight=ft.FontWeight.W_700, size=14.5))

        # Botón "Cómo conectar con ARCA": texto plano, sin fondo ni hover.
        ayuda = ft.Container(
            ink=False, padding=PADS(6, 2), on_click=lambda _e: self._abrir_tutorial(),
            content=ft.Row([ft.Icon(ft.Icons.HELP_OUTLINE, size=18, color=t["accent"]),
                            ft.Text("Cómo conectar con ARCA", size=14, weight=ft.FontWeight.W_700,
                                    color=t["accent"])], spacing=8, tight=True,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER))

        col = ft.Column([
            volver,
            ft.Container(height=6),
            titulo(t, "Facturación electrónica", "Datos de AFIP / ARCA para emitir con CAE"),
            ft.Container(height=16),
            toggle,
            ft.Container(height=16),
            clabel(t, "Entorno"), ft.Container(height=6), self._dd_entorno,
            ft.Container(height=14),
            clabel(t, "Punto de venta"), ft.Container(height=6), self._tf_pv,
            ft.Container(height=14),
            clabel(t, "Ingresos brutos"), ft.Container(height=6), self._tf_ib,
            ft.Container(height=14),
            clabel(t, "Inicio de actividades"), ft.Container(height=6), self._tf_ia,
            ft.Container(height=16),
            clabel(t, "Certificado (.crt)"), ft.Container(height=6),
            self._fila_archivo(self._cert_txt, self._pick_cert),
            ft.Container(height=14),
            clabel(t, "Clave privada (.key)"), ft.Container(height=6),
            self._fila_archivo(self._key_txt, self._pick_key),
            ft.Container(height=22),
            guardar,
            ft.Container(height=10),
            ft.Container(content=ayuda, alignment=ft.Alignment.CENTER),
            ft.Container(height=8),
        ], spacing=0, scroll=ft.ScrollMode.HIDDEN,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH, expand=True)
        return col

    # --------------------------------------------------------------- widgets
    def _marca(self) -> ft.Container:
        t = self.app.t
        on = self._afip_on
        return ft.Container(
            width=24, height=24, border_radius=7, border=BALL(1.6, t["line2"]),
            bgcolor=t["accent"] if on else t["surface2"], alignment=ft.Alignment.CENTER,
            content=ft.Icon(ft.Icons.CHECK, size=16, color=t["accent_ink"]) if on else None)

    def _toggle(self, _e):
        self._afip_on = not self._afip_on
        nueva = self._marca()
        self._box.bgcolor, self._box.content = nueva.bgcolor, nueva.content
        try:
            self._box.update()
        except Exception:  # noqa: BLE001
            pass

    def _dropdown_entorno(self) -> ft.Dropdown:
        t = self.app.t
        cur = next((i for i, (_l, v) in enumerate(_ENTORNOS) if v == self._entorno), 0)

        def on_sel(e):
            v = self._dd_entorno.value
            if v is not None:
                self._entorno = _ENTORNOS[int(v)][1]

        return ft.Dropdown(
            value=str(cur), border_radius=12, on_select=on_sel, border_color=t["line2"],
            filled=True, bgcolor=t["surface2"], text_size=14, content_padding=PADS(11, 13),
            text_style=ft.TextStyle(color=t["ink"]),
            options=[ft.DropdownOption(key=str(i), text=lbl) for i, (lbl, _v) in enumerate(_ENTORNOS)])

    def _campo(self, val, hint=None, num=False) -> ft.TextField:
        t = self.app.t
        return ft.TextField(
            value=("" if val is None else str(val)), border_radius=12, hint_text=hint,
            keyboard_type=ft.KeyboardType.NUMBER if num else ft.KeyboardType.TEXT,
            hint_style=ft.TextStyle(color=t["faint"]), border_color=t["line2"],
            focused_border_color=t["accent"], filled=True, bgcolor=t["surface2"], color=t["ink"],
            text_size=14, content_padding=PADS(11, 13))

    def _fila_archivo(self, txt_ctrl, on_pick) -> ft.Control:
        t = self.app.t
        boton = ft.Container(
            ink=True, border_radius=10, padding=PADS(9, 14), bgcolor=soft(t["accent"], 0.12),
            on_click=on_pick, alignment=ft.Alignment.CENTER,
            content=ft.Text("Elegir", color=t["accent"], size=13, weight=ft.FontWeight.W_700))
        return ft.Container(
            bgcolor=t["surface2"], border=BALL(1, t["line2"]), border_radius=12, padding=PAD(12, 6, 6, 6),
            content=ft.Row([txt_ctrl, boton], spacing=10,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER))

    # ------------------------------------------------------------- acciones
    def _nombre(self, path: str) -> str:
        return os.path.basename(path) if path else "Ningún archivo elegido"

    async def _pick_cert(self, _e=None):
        f = await self.app.file_picker.pick_files(
            dialog_title="Certificado (.crt / .pem)",
            allowed_extensions=["crt", "pem", "cer"], allow_multiple=False)
        if f:
            self._cert_path = f[0].path
            self._cert_txt.value = self._nombre(self._cert_path)
            self._cert_txt.update()

    async def _pick_key(self, _e=None):
        f = await self.app.file_picker.pick_files(
            dialog_title="Clave privada (.key / .pem)",
            allowed_extensions=["key", "pem"], allow_multiple=False)
        if f:
            self._key_path = f[0].path
            self._key_txt.value = self._nombre(self._key_path)
            self._key_txt.update()

    def _guardar(self, _e=None):
        db = self.app.db
        e = db.get_datos_empresa()
        e["punto_venta"] = (self._tf_pv.value or "").strip() or None
        e["ingresos_brutos"] = (self._tf_ib.value or "").strip() or None
        e["inicio_actividades"] = (self._tf_ia.value or "").strip() or None
        e["afip_habilitado"] = 1 if self._afip_on else 0
        db.update_datos_empresa(e)
        db.set_config("afip_entorno", self._entorno)
        db.set_config("afip_cert_path", self._cert_path)
        db.set_config("afip_key_path", self._key_path)
        self._e = db.get_datos_empresa()
        self.app.snack("Datos de AFIP guardados")

    # -------------------------------------------------------- tutorial ARCA
    def _abrir_tutorial(self):
        t = self.app.t

        def paso(i, tit, cuerpo, extra=None):
            num = ft.Container(width=26, height=26, border_radius=13, bgcolor=t["accent"],
                               alignment=ft.Alignment.CENTER,
                               content=ft.Text(str(i), size=13, weight=ft.FontWeight.W_800,
                                               color=t["accent_ink"]))
            cab = ft.Row([num, ft.Text(tit, size=14, weight=ft.FontWeight.W_700, color=t["ink"],
                                       expand=True)], spacing=10,
                         vertical_alignment=ft.CrossAxisAlignment.CENTER)
            hijos = [cab, ft.Container(padding=PAD(36, 4, 0, 0),
                                       content=ft.Text(cuerpo, size=13, color=t["muted"]))]
            if extra is not None:
                hijos.append(ft.Container(padding=PAD(36, 8, 0, 0), content=extra))
            return ft.Container(margin=MAR(bottom=14),
                                content=ft.Column(hijos, spacing=0, tight=True))

        cmd_box = ft.Container(
            bgcolor=t["surface2"], border=BALL(1, t["line2"]), border_radius=10, padding=PADS(11, 13),
            content=ft.Text(_COMANDO, size=12, color=t["ink"],
                            font_family="Consolas, monospace", selectable=True))

        pasos_ctrls = []
        for i, (tit, cuerpo) in enumerate(_PASOS, start=1):
            pasos_ctrls.append(paso(i, tit, cuerpo, extra=cmd_box if i == 3 else None))

        abrir_web = ft.Container(
            ink=True, border_radius=12, padding=PADS(12, 16), border=BALL(1, t["line2"]),
            on_click=lambda _e: self.app.page.launch_url(_WEB_ARCA), alignment=ft.Alignment.CENTER,
            content=ft.Row([ft.Icon(ft.Icons.OPEN_IN_NEW, size=17, color=t["accent"]),
                            ft.Text("Abrir la web de ARCA", color=t["accent"], size=14,
                                    weight=ft.FontWeight.W_700)], spacing=8, tight=True,
                           alignment=ft.MainAxisAlignment.CENTER))

        cuerpo = ft.Column([
            ft.Container(alignment=ft.Alignment.CENTER, margin=MAR(bottom=8),
                         content=ft.Container(width=40, height=4, border_radius=2, bgcolor=t["line2"])),
            ft.Row([ft.Text("¿Cómo conectarme con ARCA?", size=19, weight=ft.FontWeight.W_800,
                            color=t["ink"], expand=True),
                    ft.IconButton(ft.Icons.CLOSE, icon_color=t["muted"],
                                  on_click=lambda _e: self.app.page.pop_dialog())],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Text("Guía para emitir facturas electrónicas (CAE + QR).", size=12.5, color=t["muted"]),
            ft.Container(height=14),
            ft.Text(_INTRO, size=13.5, color=t["ink"]),
            ft.Container(height=14),
            *pasos_ctrls,
            abrir_web,
            ft.Container(height=6),
        ], spacing=0, scroll=ft.ScrollMode.HIDDEN, tight=True)

        cont = ft.Container(padding=PAD(18, 12, 18, 22), content=cuerpo, bgcolor=t["ground"],
                            border_radius=24)
        # Hoja inferior deslizable: se cierra arrastrando hacia abajo (como el resto).
        self.app.page.show_dialog(ft.BottomSheet(content=cont, show_drag_handle=False,
                                                 bgcolor=t["ground"], draggable=True))
