"""Productos — catálogo agrupado por talles, búsqueda, alta/edición/borrado e
importación de listas de precios (Excel/CSV) con mapeo de columnas."""
from __future__ import annotations

import flet as ft

from theme import PAD, PADS, MAR, BALL, soft
from widgets import titulo, search, row_card, empty, add_button, clabel
from vexa_core.utils.helpers import fmt_ar
from vexa_core.utils import excel_import as xls

_CAMPO_LABEL = {"nombre": "Nombre", "precio": "Precio", "codigo": "Código", "talle": "Talle"}


def _parse_talles(texto: str) -> list[str]:
    return [x.strip() for x in (texto or "").replace(";", ",").split(",") if x.strip()]


class ProductosView:
    def __init__(self, app):
        self.app = app
        self.lista = ft.Column(spacing=9)
        # estado de importación
        self._imp = {}
        self._imp_sheet = None

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
        self.app.open_form("Nuevo producto", self._campos(), on_save=lambda d: self._guardar(d))

    def _editar(self, p: dict):
        self.app.open_form(
            "Editar producto", self._campos(p),
            on_save=lambda d: self._guardar(d, orig=p),
            on_delete=lambda: self.app.db.delete_producto(p.get("nombre"), p.get("codigo")))

    # -------------------------------------------------------------- importación
    async def _importar(self, _e=None):
        files = await self.app.file_picker.pick_files(
            dialog_title="Lista de precios (Excel/CSV)",
            allowed_extensions=["xlsx", "xlsm", "xls", "csv"], allow_multiple=False)
        if not files:
            return
        path = files[0].path
        try:
            hojas = xls.listar_hojas(path)
        except Exception:  # noqa: BLE001 — csv u otros sin hojas
            hojas = []
        self._imp = {"path": path, "hojas": hojas, "hoja": hojas[0] if hojas else None,
                     "replace": False}
        self._cargar_hoja()
        t = self.app.t
        self._imp_sheet = ft.BottomSheet(
            content=self._imp_content(), show_drag_handle=False, bgcolor=t["ground"],
            on_dismiss=lambda e: setattr(self, "_imp_sheet", None))
        self.app.page.show_dialog(self._imp_sheet)

    def _cargar_hoja(self):
        headers, filas = xls.leer_hoja(self._imp["path"], self._imp["hoja"])
        self._imp["headers"] = headers
        self._imp["filas"] = filas
        self._imp["mapeo"] = xls.sugerir_mapeo(headers)

    def _imp_rerender(self):
        self._imp_sheet.content = self._imp_content()
        self._imp_sheet.update()

    def _imp_content(self) -> ft.Control:
        t = self.app.t
        headers = self._imp.get("headers", [])
        mapeo = self._imp.get("mapeo", {})
        items = xls.filas_a_items(self._imp.get("filas", []), mapeo)

        controles = []
        if len(self._imp.get("hojas", [])) > 1:
            controles.append(ft.Column([
                ft.Text("Hoja", size=11, color=t["muted"]),
                ft.Dropdown(value=self._imp["hoja"],
                            options=[ft.DropdownOption(key=h, text=h) for h in self._imp["hojas"]],
                            border_color=t["line2"], filled=True, bgcolor=t["surface"], text_size=13,
                            content_padding=PADS(6, 10), text_style=ft.TextStyle(color=t["ink"]),
                            on_select=self._imp_set_hoja)], spacing=4, tight=True))
            controles.append(ft.Container(height=10))

        def col_dd(campo):
            val = mapeo.get(campo)
            opts = [ft.DropdownOption(key="-1", text="(ninguno)")]
            opts += [ft.DropdownOption(key=str(i), text=h) for i, h in enumerate(headers)]
            return ft.Column([
                ft.Text(_CAMPO_LABEL[campo], size=11, color=t["muted"]),
                ft.Dropdown(value=(str(val) if val is not None else "-1"), options=opts,
                            border_color=t["line2"], filled=True, bgcolor=t["surface"], text_size=13,
                            content_padding=PADS(6, 10), text_style=ft.TextStyle(color=t["ink"]),
                            on_select=lambda e, c=campo: self._imp_set_map(c, int(e.control.value)))],
                spacing=4, expand=True, tight=True)

        controles.append(ft.Row([col_dd("nombre"), col_dd("precio")], spacing=10))
        controles.append(ft.Container(height=8))
        controles.append(ft.Row([col_dd("codigo"), col_dd("talle")], spacing=10))

        # Preview
        prev = []
        for it in items[:4]:
            prev.append(ft.Text(
                f'• {it["nombre"]}  —  {fmt_ar(it["pvp"])}'
                + (f'  · T {it["talle"]}' if it.get("talle") else ''),
                size=12, color=t["ink"], no_wrap=True))
        preview = ft.Container(
            bgcolor=t["surface2"], border=BALL(1, t["line"]), border_radius=12, padding=PADS(11, 13),
            margin=MAR(top=12),
            content=ft.Column([
                ft.Text(f"{len(items)} productos detectados", size=12.5, weight=ft.FontWeight.W_700,
                        color=t["accent"] if items else t["danger"]),
                *prev,
            ], spacing=4, tight=True))

        rep = ft.Row([
            ft.Switch(value=self._imp.get("replace", False), active_color=t["accent"],
                      on_change=lambda e: self._imp.__setitem__("replace", e.control.value)),
            ft.Column([ft.Text("Reemplazar catálogo", size=13, weight=ft.FontWeight.W_600,
                               color=t["ink"]),
                       ft.Text("Vacía los productos actuales antes de importar", size=11,
                               color=t["muted"])], spacing=0, tight=True, expand=True),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=6)

        importar = ft.Container(
            content=ft.Text("Importar", color=t["accent_ink"], weight=ft.FontWeight.W_700, size=14),
            bgcolor=t["accent"], border_radius=13, padding=13, alignment=ft.Alignment.CENTER,
            on_click=lambda e: self._imp_confirmar(), ink=True, margin=MAR(top=14),
            disabled=not items)

        body = ft.Column([
            ft.Container(alignment=ft.Alignment.CENTER, margin=MAR(bottom=8),
                         content=ft.Container(width=40, height=4, border_radius=2, bgcolor=t["line2"])),
            ft.Row([ft.Text("Importar productos", size=19, weight=ft.FontWeight.W_800, color=t["ink"]),
                    ft.Container(expand=True),
                    ft.IconButton(ft.Icons.CLOSE, icon_color=t["muted"],
                                  on_click=lambda e: self.app.page.pop_dialog())],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=8), clabel(t, "MAPEO DE COLUMNAS"), ft.Container(height=8),
            *controles, preview, ft.Container(height=12), rep, importar,
        ], spacing=0, scroll=ft.ScrollMode.AUTO, tight=True)
        return ft.Container(padding=PAD(16, 10, 16, 24), content=body, bgcolor=t["ground"],
                            border_radius=24)

    def _imp_set_hoja(self, e):
        self._imp["hoja"] = e.control.value
        self._cargar_hoja()
        self._imp_rerender()

    def _imp_set_map(self, campo, idx):
        self._imp["mapeo"][campo] = None if idx < 0 else idx
        self._imp_rerender()

    def _imp_confirmar(self):
        items = xls.filas_a_items(self._imp.get("filas", []), self._imp.get("mapeo", {}))
        if not items:
            self.app.snack("No se detectaron productos con ese mapeo")
            return
        if self._imp.get("replace"):
            self.app.db.clear_conceptos()
        self.app.db.upsert_conceptos(items)
        self.app.page.pop_dialog()
        self.app.render()
        self.app.snack(f"{len(items)} productos importados ✓")

    # -------------------------------------------------------------------- lista
    def _fill(self, texto: str = ""):
        app = self.app
        t = app.t
        productos = app.db.get_productos(texto or None)
        filas = []
        for p in productos:
            chip = ft.Container(bgcolor=soft(t["accent"], 0.12), border_radius=8, padding=PADS(5, 8),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Text(p["codigo"] or "—", size=11.5,
                                                weight=ft.FontWeight.W_800, color=t["accent"],
                                                font_family="monospace"))
            talles = " · ".join(p["talles"]) if p["talles"] else "Universal"
            main = ft.Column([
                ft.Text(p["nombre"] or "", size=14.5, weight=ft.FontWeight.W_700, color=t["ink"],
                        no_wrap=True),
                ft.Text(f"Talles: {talles}", size=11.5, color=t["muted"], no_wrap=True),
            ], spacing=1, expand=True, tight=True)
            precio = ft.Text(fmt_ar(p["pvp"]), size=14, weight=ft.FontWeight.W_800, color=t["ink"])
            filas.append(row_card(
                t, ft.Row([chip, main, precio], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                on_click=lambda e, prod=p: self._editar(prod)))
        self.lista.controls = filas or [empty(t, "Sin productos. Tocá + o importá una lista.")]

    def build(self) -> ft.Control:
        t = self.app.t
        self.lista = ft.Column(spacing=9)
        self._fill()
        importar_btn = ft.Container(
            width=40, height=40, border_radius=12, bgcolor=t["surface2"],
            border=BALL(1, t["line2"]), alignment=ft.Alignment.CENTER, ink=True,
            on_click=self._importar, tooltip="Importar Excel/CSV",
            content=ft.Icon(ft.Icons.UPLOAD_FILE_OUTLINED, color=t["accent"], size=20))
        return ft.Column([
            ft.Row([titulo(t, "Productos", "Catálogo y listas de precios."),
                    ft.Container(expand=True), importar_btn, ft.Container(width=8),
                    add_button(t, self._nuevo)],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=14),
            search(t, "Buscar por código o nombre…",
                   lambda e: (self._fill(e.control.value), self.lista.update())),
            ft.Container(height=12), self.lista,
        ], spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)
