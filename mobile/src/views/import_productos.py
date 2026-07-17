"""Importar lista de precios (Excel/CSV) como subpágina full-screen.

Antes era un BottomSheet que reasignaba su `.content` al cambiar el mapeo, y eso
en este Flet dejaba la pantalla negra. Ahora es una subpágina: cada cambio llama a
`app.render()` (reconstruye el árbol vía page.controls, el camino robusto), sin scrim
ni reasignación de `.content`.
"""
from __future__ import annotations

import flet as ft

from theme import PAD, PADS, MAR, BALL
from widgets import clabel
from vexa_core.utils.helpers import fmt_ar
from vexa_core.utils import excel_import as xls

_CAMPO_LABEL = {"nombre": "Nombre", "precio": "Precio", "codigo": "Código", "talle": "Talle"}


class ImportProductosView:
    def __init__(self, app, path: str):
        self.app = app
        try:
            hojas = xls.listar_hojas(path)
        except Exception:  # noqa: BLE001 — csv u otros sin hojas
            hojas = []
        self._imp = {"path": path, "hojas": hojas, "hoja": hojas[0] if hojas else None,
                     "replace": False}
        self._cargar_hoja()

    def _cargar_hoja(self):
        headers, filas = xls.leer_hoja(self._imp["path"], self._imp["hoja"])
        self._imp["headers"] = headers
        self._imp["filas"] = filas
        self._imp["mapeo"] = xls.sugerir_mapeo(headers)

    # ------------------------------------------------------------------ build
    def build(self) -> ft.Control:
        t = self.app.t
        headers = self._imp.get("headers", [])
        mapeo = self._imp.get("mapeo", {})
        items = xls.filas_a_items(self._imp.get("filas", []), mapeo)

        atras = ft.Container(
            ink=True, border_radius=10, padding=PADS(6, 6),
            on_click=lambda e: self.app.cerrar_subpagina(reopen_config=False),
            content=ft.Row([ft.Icon(ft.Icons.ARROW_BACK, size=20, color=t["ink"]),
                            ft.Text("Productos", size=13.5, weight=ft.FontWeight.W_700,
                                    color=t["muted"])], spacing=8, tight=True,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER))

        controles = []
        if len(self._imp.get("hojas", [])) > 1:
            controles.append(ft.Column([
                clabel(t, "Hoja"),
                ft.Dropdown(value=self._imp["hoja"],
                            options=[ft.DropdownOption(key=h, text=h) for h in self._imp["hojas"]],
                            border_color=t["line2"], filled=True, bgcolor=t["surface2"], text_size=13,
                            content_padding=PADS(8, 12), text_style=ft.TextStyle(color=t["ink"]),
                            on_select=self._set_hoja)], spacing=5, tight=True))
            controles.append(ft.Container(height=12))

        def col_dd(campo):
            val = mapeo.get(campo)
            opts = [ft.DropdownOption(key="-1", text="(ninguno)")]
            opts += [ft.DropdownOption(key=str(i), text=h) for i, h in enumerate(headers)]
            return ft.Column([
                clabel(t, _CAMPO_LABEL[campo]),
                ft.Dropdown(value=(str(val) if val is not None else "-1"), options=opts,
                            border_color=t["line2"], filled=True, bgcolor=t["surface2"], text_size=13,
                            content_padding=PADS(8, 12), text_style=ft.TextStyle(color=t["ink"]),
                            on_select=lambda e, c=campo: self._set_map(c, int(e.control.value)))],
                spacing=5, expand=True, tight=True)

        controles.append(ft.Row([col_dd("nombre"), col_dd("precio")], spacing=12))
        controles.append(ft.Container(height=10))
        controles.append(ft.Row([col_dd("codigo"), col_dd("talle")], spacing=12))

        prev = []
        for it in items[:5]:
            prev.append(ft.Text(
                f'• {it["nombre"]}  —  {fmt_ar(it["pvp"])}'
                + (f'  · T {it["talle"]}' if it.get("talle") else ''),
                size=12.5, color=t["ink"], no_wrap=True))
        preview = ft.Container(
            bgcolor=t["surface2"], border=BALL(1, t["line"]), border_radius=12, padding=PADS(12, 14),
            margin=MAR(top=14),
            content=ft.Column([
                ft.Text(f"{len(items)} productos detectados", size=13, weight=ft.FontWeight.W_700,
                        color=t["accent"] if items else t["danger"]),
                *prev,
            ], spacing=5, tight=True))

        rep = ft.Row([
            ft.Switch(value=self._imp.get("replace", False), active_color=t["accent"],
                      on_change=lambda e: self._imp.__setitem__("replace", e.control.value)),
            ft.Column([ft.Text("Reemplazar catálogo", size=13.5, weight=ft.FontWeight.W_600,
                               color=t["ink"]),
                       ft.Text("Vacía los productos actuales antes de importar", size=11.5,
                               color=t["muted"])], spacing=0, tight=True, expand=True),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=8)

        importar = ft.Container(
            content=ft.Text("Importar", color=t["accent_ink"], weight=ft.FontWeight.W_700, size=15),
            bgcolor=t["accent"], border_radius=14, padding=15, alignment=ft.Alignment.CENTER,
            on_click=lambda e: self._confirmar(), ink=True, margin=MAR(top=16),
            disabled=not items)

        return ft.Column([
            ft.Row([atras], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=6),
            ft.Text("Importar productos", size=24, weight=ft.FontWeight.W_800, color=t["ink"]),
            ft.Text("Asigná qué columna es cada dato y revisá la vista previa.", size=12.5,
                    color=t["muted"]),
            ft.Container(height=18), clabel(t, "Mapeo de columnas"), ft.Container(height=10),
            *controles, preview, ft.Container(height=14), rep, importar, ft.Container(height=16),
        ], spacing=0, scroll=ft.ScrollMode.HIDDEN, expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    # --------------------------------------------------------------- acciones
    def _set_hoja(self, e):
        self._imp["hoja"] = e.control.value
        self._cargar_hoja()
        self.app.render()

    def _set_map(self, campo, idx):
        self._imp["mapeo"][campo] = None if idx < 0 else idx
        self.app.render()

    def _confirmar(self):
        items = xls.filas_a_items(self._imp.get("filas", []), self._imp.get("mapeo", {}))
        if not items:
            self.app.snack("No se detectaron productos con ese mapeo")
            return
        if self._imp.get("replace"):
            self.app.db.clear_conceptos()
        self.app.db.upsert_conceptos(items)
        self.app.cerrar_subpagina(reopen_config=False)   # vuelve a Productos + render
        self.app.snack(f"{len(items)} productos importados ✓")
