"""Productos — catálogo agrupado por talles, búsqueda, alta/edición/borrado e
importación de listas de precios (Excel/CSV) con mapeo de columnas."""
from __future__ import annotations

import flet as ft

from theme import PADS, BALL, soft
from widgets import titulo, search, row_card, empty, add_button
from vexa_core.utils.helpers import fmt_ar
from views.import_productos import ImportProductosView


def _parse_talles(texto: str) -> list[str]:
    return [x.strip() for x in (texto or "").replace(";", ",").split(",") if x.strip()]


class ProductosView:
    def __init__(self, app):
        self.app = app
        self.lista = ft.Column(spacing=9)

    # -------------------------------------------------------------- alta/edición
    def _campos(self, p: dict | None = None) -> list[dict]:
        p = p or {}
        return [
            {"key": "nombre", "label": "Nombre", "value": p.get("nombre")},
            {"key": "codigo", "label": "Código", "value": p.get("codigo")},
            {"key": "talles", "label": "Talles (separados por coma; vacío = único)",
             "value": ", ".join(p.get("talles") or [])},
            {"key": "precio", "label": "Precio", "tipo": "number", "value": p.get("pvp") or 0},
        ]

    def _guardar(self, d: dict, orig: dict | None = None):
        nombre = (d.get("nombre") or "").strip()
        if not nombre:
            raise ValueError("El nombre del producto es obligatorio.")
        precio = d.get("precio") or 0
        if precio <= 0:
            raise ValueError("El precio debe ser mayor que 0.")
        data = {"nombre": nombre, "codigo": d["codigo"], "pvp": precio,
                "talles": _parse_talles(d.get("talles"))}
        if orig:
            self.app.db.save_producto(data, orig_nombre=orig.get("nombre"),
                                      orig_codigo=orig.get("codigo"))
        else:
            self.app.db.save_producto(data)

    def _nuevo(self):
        self.app.open_form("Nuevo producto", self._campos(), on_save=lambda d: self._guardar(d),
                           full=False)

    def _editar(self, p: dict):
        self.app.open_form(
            "Editar producto", self._campos(p),
            on_save=lambda d: self._guardar(d, orig=p),
            on_delete=lambda: self.app.db.delete_producto(p.get("nombre"), p.get("codigo")),
            full=False, borrar_texto="¿Seguro que querés eliminar este producto?")

    # -------------------------------------------------------------- importación
    async def _importar(self, _e=None):
        files = await self.app.file_picker.pick_files(
            dialog_title="Lista de precios (Excel/CSV)",
            allowed_extensions=["xlsx", "xlsm", "xls", "csv"], allow_multiple=False)
        if not files:
            return
        # Subpágina full-screen (evita el scrim negro del BottomSheet al re-mapear).
        self.app.abrir_subpagina(ImportProductosView(self.app, files[0].path))

    # -------------------------------------------------------------------- lista
    def _fill(self, texto: str = ""):
        app = self.app
        t = app.t
        productos = app.db.get_productos(texto or None)
        productos = sorted(productos, key=lambda p: (not (p.get("codigo") or ""), (p.get("codigo") or "").lower()))
        filas = []
        for p in productos:
            chip = ft.Container(width=54, bgcolor=soft(t["accent"], 0.12), border_radius=8,
                                padding=PADS(5, 4), alignment=ft.Alignment.CENTER,
                                content=ft.Text(p["codigo"] or "—", size=11.5,
                                                weight=ft.FontWeight.W_800, color=t["accent"],
                                                font_family="monospace", no_wrap=True))
            talles = " · ".join(p["talles"]) if p["talles"] else "Universal"
            main = ft.Column([
                app.marquee(p["nombre"] or "", 14.5, ft.FontWeight.W_700, t["ink"]),
                ft.Text(f"Talles: {talles}", size=11.5, color=t["muted"], no_wrap=True),
            ], spacing=1, expand=True, tight=True,
               horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
            precio = ft.Text(fmt_ar(p["pvp"]), size=14, weight=ft.FontWeight.W_800, color=t["ink"])
            filas.append(row_card(
                t, ft.Row([chip, main, precio], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                on_click=lambda e, prod=p: self._editar(prod)))
        self.lista.controls = filas or [empty(t, "Sin productos. Tocá + o importá una lista.")]

    def build(self) -> ft.Control:
        t = self.app.t
        self.lista = ft.Column(spacing=9, scroll=ft.ScrollMode.HIDDEN, expand=True)
        self._fill()
        importar_btn = ft.Container(
            width=40, height=40, border_radius=12, bgcolor=t["surface2"],
            border=BALL(1, t["line2"]), alignment=ft.Alignment.CENTER, ink=True,
            on_click=self._importar, tooltip="Importar Excel/CSV",
            content=ft.Icon(ft.Icons.UPLOAD_FILE_OUTLINED, color=t["accent"], size=20))
        # Header (título + import + + + buscador) FIJO; solo la lista se desliza.
        return ft.Column([
            ft.Row([titulo(t, "Productos", "Catálogo y listas de precios."),
                    ft.Container(expand=True), importar_btn, ft.Container(width=8),
                    add_button(t, self._nuevo)],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=14),
            search(t, "Buscar por código o nombre…",
                   lambda e: (self._fill(e.control.value), self.lista.update())),
            ft.Container(height=12),
            ft.Container(expand=True, content=self.lista),
        ], spacing=0, expand=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
