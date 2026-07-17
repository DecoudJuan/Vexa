"""Etiquetas — catálogo (productos de Vexa) → talles/cantidad → cola → generar."""
from __future__ import annotations

import os

import flet as ft

from theme import PADS, MAR, BALL, BEDGE, soft
from widgets import titulo, search, card, clabel, empty
from vexa_core.utils.etiquetas import resumen_cola, generar_pdf_etiquetas
from vexa_core.utils.pdf_generator import obtener_carpeta_pdf
import plataforma


class EtiquetasView:
    def __init__(self, app):
        self.app = app
        self.sel = None                 # producto elegido
        self.rows: list[dict] = []      # {talle, cant, talle_ctrl, cant_ctrl}
        self.queue: list[dict] = []     # cola de impresión
        self._lista = ft.Column(spacing=0, scroll=ft.ScrollMode.HIDDEN, height=210)
        self._paso2 = ft.Container()
        self._paso3 = ft.Container()

    def _u(self, ctrl):
        """Update defensivo: si el control no está montado (tests), no rompe."""
        try:
            ctrl.update()
        except Exception:  # noqa: BLE001
            pass

    # ---------------------------------------------------------------- build
    def build(self) -> ft.Control:
        app = self.app
        t = app.t
        self._lista = ft.Column(spacing=0, scroll=ft.ScrollMode.HIDDEN, height=210)
        self._fill_prod()
        paso1 = card(t, [
            clabel(t, "1 · ELEGÍ UN PRODUCTO"), ft.Container(height=11),
            search(t, "Buscar por código o nombre…",
                   lambda e: (self._fill_prod(e.control.value), self._u(self._lista))),
            ft.Container(height=10),
            ft.Container(border=BALL(1, t["line"]), border_radius=12, content=self._lista,
                         clip_behavior=ft.ClipBehavior.ANTI_ALIAS),
        ])
        self._paso2 = ft.Container(visible=self.sel is not None)
        self._render_paso2()
        self._paso3 = ft.Container()
        self._render_cola()
        return ft.Column([
            titulo(t, "Etiquetas", "Generá e imprimí etiquetas de tus productos."),
            ft.Container(height=14), paso1, ft.Container(height=12), self._paso2,
            ft.Container(height=12), self._paso3,
        ], spacing=0, scroll=ft.ScrollMode.HIDDEN, expand=True)

    # ------------------------------------------------------------- paso 1
    def _fill_prod(self, texto: str = ""):
        t = self.app.t
        productos = self.app.db.get_productos()
        productos = sorted(productos, key=lambda p: (not (p.get("codigo") or ""), (p.get("codigo") or "").lower()))
        s = (texto or "").lower().strip()
        filt = [p for p in productos
                if not s or s in (p["codigo"] or "").lower() or s in (p["nombre"] or "").lower()]
        items = []
        for p in filt:
            sel = (self.sel and self.sel["nombre"] == p["nombre"]
                   and self.sel["codigo"] == p["codigo"])
            items.append(ft.Container(
                padding=PADS(10, 12), bgcolor=soft(t["accent"], 0.12) if sel else None,
                border=BEDGE(left=(3, t["accent"])) if sel else None,
                content=ft.Row([
                    ft.Container(width=54, bgcolor=soft(t["accent"], 0.12), border_radius=8,
                                 padding=PADS(4, 4), alignment=ft.Alignment.CENTER,
                                 content=ft.Text(p["codigo"] or "—", size=11.5, weight=ft.FontWeight.W_800,
                                                 color=t["accent"], font_family="monospace", no_wrap=True)),
                    ft.Container(expand=True,
                                 content=self.app.marquee(p["nombre"] or "", 12.5, None, t["ink"])),
                ], spacing=9),
                on_click=lambda e, prod=p: self._sel_producto(prod), ink=True))
        self._lista.controls = items or [empty(t, "Sin resultados")]

    def _sel_producto(self, prod: dict):
        self.sel = prod
        talles = prod["talles"] or []
        self.rows = [{"talle": talles[0] if talles else "", "cant": 1,
                      "talle_ctrl": None, "cant_ctrl": None}]
        self._fill_prod()
        self._u(self._lista)
        self._paso2.visible = True
        self._render_paso2()
        self._u(self._paso2)

    # ------------------------------------------------------------- paso 2
    def _sync_rows(self):
        for r in self.rows:
            if r.get("talle_ctrl") is not None:
                r["talle"] = r["talle_ctrl"].value
            if r.get("cant_ctrl") is not None:
                v = r["cant_ctrl"].value
                r["cant"] = int(v) if str(v).isdigit() else 1

    def _render_paso2(self):
        if not self.sel:
            self._paso2.content = None
            return
        t = self.app.t
        p = self.sel
        universal = not p["talles"]
        ty = "Universal" if universal else f"{len(p['talles'])} talles"
        # Rectángulo alargado (ancho completo, bajo): código + nombre en una línea.
        selinfo = ft.Container(
            bgcolor=soft(t["accent"], 0.12), border_radius=12, border=BALL(1, soft(t["accent"], 0.3)),
            padding=PADS(10, 13), content=ft.Row([
                ft.Text(p["codigo"] or "—", size=12, weight=ft.FontWeight.W_800, color=t["accent"],
                        font_family="monospace"),
                ft.Container(expand=True,
                             content=self.app.marquee(p["nombre"] or "", 14, ft.FontWeight.W_700, t["ink"])),
                ft.Text(ty, size=11.5, color=t["muted"]),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER))

        filas_ctrl = []
        for i, row in enumerate(self.rows):
            campos = []
            if not universal:
                dd = ft.Dropdown(value=row["talle"] or (p["talles"][0] if p["talles"] else ""),
                                 options=[ft.DropdownOption(key=x, text=x) for x in p["talles"]],
                                 border_radius=12, border_color=t["line2"], filled=True,
                                 bgcolor=t["surface"], text_size=13, content_padding=PADS(9, 12),
                                 text_style=ft.TextStyle(color=t["ink"]))
                row["talle_ctrl"] = dd
                campos.append(ft.Column([ft.Text("Talle", size=11, color=t["muted"]), dd],
                                        spacing=4, expand=True, tight=True))
            tf = ft.TextField(value=str(row["cant"]), keyboard_type=ft.KeyboardType.NUMBER,
                              border_radius=12, border_color=t["line2"], filled=True,
                              bgcolor=t["surface"], color=t["ink"], text_size=13,
                              content_padding=PADS(9, 12), width=96)
            row["cant_ctrl"] = tf
            campos.append(ft.Column([ft.Text("Cantidad", size=11, color=t["muted"]), tf],
                                    spacing=4, tight=True))
            x = (ft.IconButton(ft.Icons.CLOSE, icon_size=18, icon_color=t["faint"],
                               on_click=lambda e, idx=i: self._del_row(idx))
                 if i > 0 else ft.Container(width=40))
            filas_ctrl.append(ft.Container(
                bgcolor=t["surface2"], border=BALL(1, t["line"]), border_radius=14, padding=12,
                margin=MAR(bottom=8),
                content=ft.Row(campos + [x], vertical_alignment=ft.CrossAxisAlignment.END, spacing=9)))

        hijos = [clabel(t, "2 · CONFIGURÁ TALLES Y CANTIDAD"), ft.Container(height=11),
                 selinfo, ft.Container(height=10)] + filas_ctrl
        if not universal:
            hijos.append(ft.Container(
                content=ft.Text("＋ Agregar otro talle", size=12.5, weight=ft.FontWeight.W_600,
                                color=t["accent"]),
                border=BALL(1, soft(t["accent"], 0.45)), border_radius=10, padding=PADS(8, 12),
                on_click=lambda e: self._add_row(), ink=True, margin=MAR(bottom=4)))
        hijos.append(ft.Container(
            content=ft.Text("Agregar a la cola →", color=t["accent_ink"], weight=ft.FontWeight.W_700,
                            size=14),
            bgcolor=t["accent"], border_radius=13, padding=13, alignment=ft.Alignment.CENTER,
            on_click=lambda e: self._add_to_queue(), ink=True, margin=MAR(top=6)))
        self._paso2.content = card(t, hijos)

    def _add_row(self):
        self._sync_rows()
        talles = self.sel["talles"] if self.sel else []
        self.rows.append({"talle": talles[0] if talles else "", "cant": 1,
                          "talle_ctrl": None, "cant_ctrl": None})
        self._render_paso2()
        self._u(self._paso2)

    def _del_row(self, idx: int):
        self._sync_rows()
        if 0 <= idx < len(self.rows):
            self.rows.pop(idx)
        self._render_paso2()
        self._u(self._paso2)

    def _add_to_queue(self):
        if not self.sel:
            return
        self._sync_rows()
        p = self.sel
        for row in self.rows:
            self.queue.append({"codigo": p["codigo"], "nombre": p["nombre"],
                               "talle": row["talle"], "cantidad": max(1, int(row["cant"] or 1))})
        self._render_cola()
        self._u(self._paso3)

    # ------------------------------------------------------------- paso 3
    def _render_cola(self):
        t = self.app.t
        hijos = [clabel(t, "3 · COLA DE IMPRESIÓN"), ft.Container(height=11)]
        if not self.queue:
            hijos.append(empty(t, "Todavía no agregaste etiquetas."))
            self._paso3.content = card(t, hijos)
            return
        for i, q in enumerate(self.queue):
            ico = ft.Container(width=36, height=36, border_radius=9, bgcolor=t["accent"],
                               alignment=ft.Alignment.CENTER,
                               content=ft.Text(q["codigo"] or "—", size=10, weight=ft.FontWeight.W_800,
                                               color=t["accent_ink"], font_family="monospace"))
            titulo_it = q["nombre"] + (f" — T {q['talle']}" if q["talle"] else "")
            main = ft.Column([
                ft.Text(titulo_it, size=13, weight=ft.FontWeight.W_700, color=t["ink"], no_wrap=True),
                ft.Text(f"Código {q['codigo']}", size=11, color=t["muted"]),
            ], spacing=1, expand=True, tight=True)
            qty = ft.Container(bgcolor=soft(t["accent"], 0.12), border_radius=8, padding=PADS(3, 9),
                               content=ft.Text(f"×{q['cantidad']}", size=12.5,
                                               weight=ft.FontWeight.W_800, color=t["accent"]))
            xb = ft.IconButton(ft.Icons.CLOSE, icon_size=18, icon_color=t["faint"],
                               on_click=lambda e, idx=i: self._del_queue(idx))
            hijos.append(ft.Container(
                border=BALL(1, t["line"]), border_radius=12, padding=11, margin=MAR(bottom=8),
                bgcolor=t["surface"],
                content=ft.Row([ico, main, qty, xb], spacing=11,
                               vertical_alignment=ft.CrossAxisAlignment.CENTER)))

        r = resumen_cola(sum(q["cantidad"] for q in self.queue))

        def sumrow(lbl, val):
            return ft.Row([ft.Text(lbl, size=12.5, color=t["muted"]),
                           ft.Text(str(val), size=12.5, weight=ft.FontWeight.W_700, color=t["ink"])],
                          alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        hijos.append(ft.Container(
            bgcolor=t["surface2"], border=BALL(1, t["line"]), border_radius=12, padding=PADS(12, 14),
            margin=MAR(top=6), content=ft.Column([
                sumrow("Total de etiquetas", r["total"]), sumrow("Hojas (14 por hoja)", r["paginas"]),
                sumrow("En la última hoja", r["ultima"]),
            ], spacing=3, tight=True)))
        if r["faltan"]:
            hijos.append(ft.Container(
                margin=MAR(top=10),
                content=ft.Row([ft.Container(
                    expand=True, bgcolor=soft(t["warn"], 0.15), border=BALL(1, soft(t["warn"], 0.45)),
                    border_radius=11, padding=PADS(10, 12),
                    content=ft.Row([
                        ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=18, color=t["warn"]),
                        ft.Text(f"Quedan {r['faltan']} espacios libres en la última hoja.",
                                size=11.5, color=t["warn"], expand=True),
                    ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER))])))
        hijos.append(ft.Container(
            content=ft.Row([ft.Icon(ft.Icons.PRINT_OUTLINED, color=t["accent_ink"], size=20),
                            ft.Text("Generar e imprimir", color=t["accent_ink"],
                                    weight=ft.FontWeight.W_700, size=14)],
                           alignment=ft.MainAxisAlignment.CENTER, spacing=8),
            bgcolor=t["accent"], border_radius=13, padding=13, margin=MAR(top=12),
            on_click=self._generar, ink=True))
        hijos.append(ft.Container(
            content=ft.Text("Limpiar cola", color=t["muted"], size=12.5),
            border=BALL(1, t["line2"]), border_radius=13, padding=9, alignment=ft.Alignment.CENTER,
            margin=MAR(top=8), on_click=lambda e: self._clear(), ink=True))
        self._paso3.content = card(t, hijos)

    def _del_queue(self, idx: int):
        if 0 <= idx < len(self.queue):
            self.queue.pop(idx)
        self._render_cola()
        self._u(self._paso3)

    def _clear(self):
        self.queue = []
        self._render_cola()
        self._u(self._paso3)

    async def _generar(self, _e=None):
        try:
            ruta = generar_pdf_etiquetas(self.queue, obtener_carpeta_pdf(self.app.db))
            ok = await plataforma.entregar_pdf(self.app, ruta)
            if not ok:
                self.app.snack("Guardado cancelado")
        except Exception as ex:  # noqa: BLE001
            self.app.snack(f"Error al generar etiquetas: {ex}")
