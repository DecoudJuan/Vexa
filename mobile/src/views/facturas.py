"""Facturas — KPIs + búsqueda + listado (PDF) + alta/edición con líneas dinámicas.

Paridad con desktop: cliente y producto se ELIGEN o ESCRIBEN (dropdown editable con
filtro); líneas por nombre (sin talle); precio auto pero editable; bonificación %,
forma de pago y comentarios; total = subtotal − bonif; se EDITAN facturas existentes.

El modal se construye UNA sola vez; agregar/quitar líneas actualiza solo la columna
persistente `_lineas_col` (no se recrea el modal). Cierre con chequeo de cambios
(grip / Escape) y aviso como banner arriba dentro del modal.
"""
from __future__ import annotations

import os
from datetime import date

import flet as ft

from theme import PAD, PADS, MAR, BALL, BEDGE, soft
from widgets import titulo, search, row_card, empty, add_button, clabel
from vexa_core.utils.helpers import fmt_ar, fmt_cantidad_corta, parse_float, etiqueta_concepto
from vexa_core.utils.pdf_generator import generar_pdf_documento
import plataforma


class FacturasView:
    def __init__(self, app):
        self.app = app
        self.lista = ft.Column(spacing=9)

    # ============================================================ alta/edición
    def nueva(self):
        self._abrir(None)

    def _editar(self, f: dict):
        self._abrir(f["id"])

    def _abrir(self, factura_id):
        db = self.app.db
        self._clientes = db.get_all_clientes()
        self._prods = db.get_productos()
        self._id2idx = {}
        for i, p in enumerate(self._prods):
            for cid in p.get("ids", []):
                self._id2idx[cid] = i
        self._fid = factura_id
        self._dirty = False
        if factura_id is not None:
            d = db.get_factura(factura_id) or {}
            self._cliente_id = d.get("cliente_id")
            self._ejercicio = d.get("ejercicio") or date.today().year
            self._numero = d.get("numero") or ""
            self._fecha = (d.get("fecha") or date.today().isoformat())[:10]
            self._fp = d.get("forma_pago_id")
            self._coment = d.get("comentarios") or ""
            self._bonif = float(d.get("bonificacion") or 0)
            self._rows = []
            for ln in db.get_lineas(factura_id):
                idx = self._id2idx.get(ln.get("concepto_id"))
                self._rows.append({"prod": idx, "texto": ln.get("concepto_libre") or "",
                                   "cant": ln.get("cantidad") or 1, "pvp": ln.get("pvp") or 0,
                                   "cant_ctrl": None, "pvp_ctrl": None})
            if not self._rows:
                self._rows = [self._new_row()]
        else:
            self._ejercicio = date.today().year
            self._cliente_id = self._clientes[0]["id"] if self._clientes else None
            self._numero = db.siguiente_numero("FA", self._ejercicio)
            self._fecha = date.today().isoformat()
            self._fp = None
            self._coment = ""
            self._bonif = 0.0
            self._rows = [self._new_row()]

        t = self.app.t
        self._alto = int((self.app.page.height or 900) * 0.9)
        self._lineas_col = ft.Column(spacing=0, tight=True)
        self._total_lbl = ft.Text(fmt_ar(self._total()), size=22, weight=ft.FontWeight.W_800,
                                  color=t["accent"])
        self._banner = ft.Container(visible=False, top=8, left=12, right=12, bgcolor=t["surface"],
                                    border=BALL(1, t["line2"]), border_radius=14, padding=PADS(12, 16),
                                    content=self._banner_content())
        self._refresh_lineas()
        self.app._form_escape = self._try_close
        self._sheet = ft.BottomSheet(
            content=ft.Stack([self._content(), self._banner], expand=True), bgcolor=t["ground"],
            fullscreen=True, dismissible=False, draggable=False, show_drag_handle=False)
        self.app.page.show_dialog(self._sheet)

    def _new_row(self) -> dict:
        return {"prod": None, "texto": "", "cant": 1, "pvp": 0.0, "cant_ctrl": None, "pvp_ctrl": None}

    # -------- líneas (columna persistente; se actualiza sin recrear el modal)
    def _build_line(self, i: int, r: dict) -> ft.Control:
        t = self.app.t
        prod_dd = ft.Dropdown(
            value=(str(r["prod"]) if r["prod"] is not None else None),
            editable=True, enable_filter=True, expand=True, border_radius=10,
            options=[ft.DropdownOption(key=str(j), text=etiqueta_concepto(p["nombre"], p.get("codigo")))
                     for j, p in enumerate(self._prods)],
            border_color=t["line2"], filled=True, bgcolor=t["surface2"], text_size=13,
            content_padding=PADS(8, 10), text_style=ft.TextStyle(color=t["ink"]),
            hint_text="Producto…", on_select=lambda e, idx=i: self._on_prod(idx, e.control.value))
        cant_tf = ft.TextField(value=f'{r["cant"]:g}', keyboard_type=ft.KeyboardType.NUMBER,
                               border_color=t["line2"], filled=True, border_radius=10,
                               bgcolor=t["surface2"], color=t["ink"], text_size=13,
                               content_padding=PADS(8, 8), width=54, text_align=ft.TextAlign.CENTER,
                               on_change=lambda e: self._recalc_total())
        pvp_tf = ft.TextField(value=f'{r["pvp"]:.2f}', keyboard_type=ft.KeyboardType.NUMBER,
                              border_color=t["line2"], filled=True, border_radius=10,
                              bgcolor=t["surface2"], color=t["ink"], text_size=13,
                              content_padding=PADS(8, 8), width=84, text_align=ft.TextAlign.RIGHT,
                              on_change=lambda e: self._recalc_total())
        r["cant_ctrl"], r["pvp_ctrl"] = cant_tf, pvp_tf
        x = ft.IconButton(ft.Icons.CLOSE, icon_size=16, icon_color=t["faint"],
                          on_click=lambda e, idx=i: self._del_row(idx))
        return ft.Container(margin=MAR(bottom=12), content=ft.Row(
            [prod_dd, cant_tf, pvp_tf, x], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=6))

    def _refresh_lineas(self):
        self._lineas_col.controls = [self._build_line(i, r) for i, r in enumerate(self._rows)]
        try:
            self._lineas_col.update()
        except Exception:  # noqa: BLE001
            pass

    def _sync(self):
        for r in self._rows:
            if r.get("cant_ctrl") is not None:
                r["cant"] = parse_float(str(r["cant_ctrl"].value)) or 0
            if r.get("pvp_ctrl") is not None:
                r["pvp"] = parse_float(str(r["pvp_ctrl"].value)) or 0

    def _subtotal(self) -> float:
        return sum((r["cant"] or 0) * (r["pvp"] or 0) for r in self._rows)

    def _total(self) -> float:
        sub = self._subtotal()
        return sub - (sub * (self._bonif / 100.0) if self._bonif > 0 else 0)

    def _recalc_total(self):
        self._sync()
        self._total_lbl.value = fmt_ar(self._total())
        try:
            self._total_lbl.update()
        except Exception:  # noqa: BLE001
            pass

    def _on_prod(self, idx, val):
        self._sync()
        if str(val).isdigit():
            p = self._prods[int(val)]
            self._rows[idx]["prod"] = int(val)
            self._rows[idx]["texto"] = ""
            self._rows[idx]["pvp"] = p["pvp"] or 0
        self._dirty = True
        self._refresh_lineas()
        self._recalc_total()

    def _add_row(self):
        self._sync()
        self._rows.append(self._new_row())
        self._dirty = True
        self._refresh_lineas()
        self._recalc_total()

    def _del_row(self, idx):
        self._sync()
        if 0 <= idx < len(self._rows):
            self._rows.pop(idx)
        if not self._rows:
            self._rows = [self._new_row()]
        self._dirty = True
        self._refresh_lineas()
        self._recalc_total()

    def _on_bonif(self, e):
        self._bonif = parse_float(str(e.control.value)) or 0
        self._dirty = True
        self._recalc_total()

    def _on_coment(self, e):
        self._coment = e.control.value
        self._dirty = True

    def _on_cliente(self, e):
        self._cliente_id = int(e.control.value) if str(e.control.value).isdigit() else None
        self._dirty = True

    # -------- cierre con chequeo (grip / Escape / Cancelar)
    def _banner_content(self):
        t = self.app.t
        return ft.Column([
            ft.Text("Tenés cambios sin guardar. ¿Descartarlos?", size=13,
                    weight=ft.FontWeight.W_600, color=t["ink"]),
            ft.Container(height=8),
            ft.Row([
                ft.Container(content=ft.Text("Seguir editando", color=t["muted"], size=13,
                                             weight=ft.FontWeight.W_600), padding=PADS(8, 12),
                             ink=True, border_radius=10, on_click=lambda e: self._hide_banner()),
                ft.Container(expand=True),
                ft.Container(content=ft.Text("Descartar", color="#ffffff", size=13,
                                             weight=ft.FontWeight.W_700), bgcolor=t["danger"],
                             border_radius=10, padding=PADS(8, 16), ink=True,
                             on_click=lambda e: self._close()),
            ]),
        ], spacing=0, tight=True)

    def _hide_banner(self):
        self._banner.visible = False
        try:
            self._banner.update()
        except Exception:  # noqa: BLE001
            pass

    def _try_close(self):
        if self._dirty:
            self._banner.visible = True
            try:
                self._banner.update()
            except Exception:  # noqa: BLE001
                pass
        else:
            self._close()

    def _close(self):
        self.app._form_escape = None
        self.app.page.pop_dialog()

    def _guardar(self):
        self._sync()
        if self._cliente_id is None:
            self.app.snack("Elegí un cliente")
            return
        lineas = []
        for r in self._rows:
            if r["prod"] is not None:
                p = self._prods[r["prod"]]
                cid = p["ids"][0] if p.get("ids") else None
                libre = None if cid else p["nombre"]
            else:
                cid, libre = None, (r["texto"].strip() or None)
            if cid is None and not libre:
                continue
            lineas.append({"concepto_id": cid, "concepto_libre": libre,
                           "cantidad": r["cant"] or 1, "pvp": r["pvp"] or 0})
        if not lineas:
            self.app.snack("Agregá al menos una línea")
            return
        data = {"cliente_id": self._cliente_id, "tipo": "FA", "ejercicio": int(self._ejercicio),
                "numero": self._numero, "fecha": self._fecha, "forma_pago_id": self._fp,
                "comentarios": self._coment or None, "bonificacion": self._bonif,
                "aplica_bonificacion": 1 if self._bonif > 0 else 0, "total": self._total()}
        if self._fid:
            self.app.db.update_factura(self._fid, data, lineas)
        else:
            self.app.db.create_factura(data, lineas)
        self._close()
        self.app.render()
        self.app.snack("Factura guardada")

    # -------- contenido (se arma una sola vez)
    def _content(self) -> ft.Control:
        t = self.app.t
        titulo_txt = "Editar factura" if self._fid else "Nueva factura"

        def lab(txt, ctl):
            return ft.Column([ft.Text(txt, size=10.5, weight=ft.FontWeight.W_800, color=t["faint"]),
                              ctl], spacing=5, tight=True,
                             horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

        grip = ft.GestureDetector(
            on_tap=lambda e: self._try_close(),
            on_vertical_drag_end=lambda e: (self._try_close() if (getattr(e, "primary_velocity", None) or 0) > 0 else None),
            content=ft.Container(alignment=ft.Alignment.CENTER, padding=PADS(12, 4), bgcolor=t["ground"],
                                 content=ft.Container(width=44, height=5, border_radius=3,
                                                      bgcolor=t["line2"])))

        if not self._clientes:
            middle = ft.Column([empty(t, "Primero cargá un cliente.")], expand=True)
            footer = None
        elif not self._prods:
            middle = ft.Column([empty(t, "Primero cargá un producto.")], expand=True)
            footer = None
        else:
            cli_dd = ft.Dropdown(
                value=(str(self._cliente_id) if self._cliente_id is not None else None),
                editable=True, enable_filter=True, border_radius=12,
                options=[ft.DropdownOption(key=str(c["id"]), text=c["nombre"]) for c in self._clientes],
                border_color=t["line2"], filled=True, bgcolor=t["surface2"], text_size=14,
                content_padding=PADS(11, 13), text_style=ft.TextStyle(color=t["ink"]),
                on_select=self._on_cliente)
            add = ft.Container(
                content=ft.Text("＋ Agregar línea", size=12.5, weight=ft.FontWeight.W_600,
                                color=t["accent"]), border=BALL(1, soft(t["accent"], 0.45)),
                border_radius=10, padding=PADS(8, 12), on_click=lambda e: self._add_row(), ink=True)
            coment_tf = ft.TextField(value=self._coment, multiline=True, min_lines=2, max_lines=4,
                                     border_color=t["line2"], filled=True, bgcolor=t["surface2"],
                                     color=t["ink"], text_size=14, border_radius=12,
                                     content_padding=PADS(11, 13), on_change=self._on_coment)
            bonif_tf = ft.TextField(value=f"{self._bonif:g}", keyboard_type=ft.KeyboardType.NUMBER,
                                    border_color=t["line2"], filled=True, border_radius=12,
                                    bgcolor=t["surface2"], color=t["ink"], text_size=14,
                                    content_padding=PADS(11, 13), on_change=self._on_bonif, width=110)
            guardar = ft.Container(
                content=ft.Text("Guardar factura", color=t["accent_ink"], weight=ft.FontWeight.W_700,
                                size=14), bgcolor=t["accent"], border_radius=13, padding=13,
                alignment=ft.Alignment.CENTER, on_click=lambda e: self._guardar(), ink=True)
            header_cols = ft.Row([
                ft.Text("PRODUCTO", size=9.5, weight=ft.FontWeight.W_800, color=t["faint"], expand=True),
                ft.Text("CANT", size=9.5, weight=ft.FontWeight.W_800, color=t["faint"], width=54,
                        text_align=ft.TextAlign.CENTER),
                ft.Text("PRECIO", size=9.5, weight=ft.FontWeight.W_800, color=t["faint"], width=84,
                        text_align=ft.TextAlign.RIGHT),
                ft.Container(width=40)], spacing=6)

            middle = ft.Column([
                ft.Text(f"FA {self._ejercicio}-{self._numero}  ·  {self._fecha}", size=12,
                        color=t["muted"]),
                ft.Container(height=12), lab("CLIENTE", cli_dd), ft.Container(height=18),
                header_cols, ft.Container(height=8), self._lineas_col, add,
                ft.Container(height=16), lab("COMENTARIOS", coment_tf), ft.Container(height=8),
            ], spacing=0, scroll=ft.ScrollMode.HIDDEN, expand=True,
               horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

            footer = ft.Container(
                padding=PAD(0, 12, 0, 0), border=BEDGE(top=(1, t["line"])),
                content=ft.Column([
                    ft.Row([
                        ft.Column([ft.Text("BONIF. %", size=10, weight=ft.FontWeight.W_800,
                                           color=t["faint"]), bonif_tf], spacing=4, tight=True),
                        ft.Container(expand=True),
                        ft.Column([ft.Text("TOTAL", size=10, weight=ft.FontWeight.W_800, color=t["faint"]),
                                   self._total_lbl], spacing=2, tight=True,
                                  horizontal_alignment=ft.CrossAxisAlignment.END),
                    ], vertical_alignment=ft.CrossAxisAlignment.END),
                    ft.Container(height=12), guardar,
                ], spacing=0, tight=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH))

        cols = [grip, ft.Text(titulo_txt, size=20, weight=ft.FontWeight.W_800, color=t["ink"]),
                ft.Container(height=12), ft.Container(expand=True, content=middle)]
        if footer is not None:
            cols.append(footer)
        return ft.Container(padding=PAD(18, 8, 18, 18), bgcolor=t["ground"], expand=True,
                            content=ft.Column(cols, spacing=0, expand=True,
                                              horizontal_alignment=ft.CrossAxisAlignment.STRETCH))

    # ============================================================ listado + PDF
    def _pdf_handler(self, factura_id: int):
        app = self.app

        def _h(_e):
            try:
                ruta = generar_pdf_documento(app.db, factura_id)
                plataforma.abrir_o_compartir_pdf(app.page, ruta)
                app.snack(f"PDF: {os.path.basename(ruta)}")
            except Exception as ex:  # noqa: BLE001
                app.snack(f"Error al generar PDF: {ex}")
        return _h

    def _fill(self, texto: str = ""):
        t = self.app.t
        facturas = self.app.db.get_facturas(search=texto or None)
        filas = []
        for f in facturas:
            main = ft.Column([
                ft.Text(f"FA {f.get('numero', '')}", size=14.5, weight=ft.FontWeight.W_700,
                        color=t["ink"]),
                ft.Text(f"{f.get('fecha', '')} · {f.get('cliente_nombre', '')}", size=12,
                        color=t["muted"], no_wrap=True),
            ], spacing=1, expand=True, tight=True)
            der = ft.Row([
                ft.Text(fmt_ar(f.get("total") or 0), size=14, weight=ft.FontWeight.W_800,
                        color=t["ink"]),
                ft.IconButton(ft.Icons.PICTURE_AS_PDF_OUTLINED, icon_color=t["accent"],
                              tooltip="Ver / compartir PDF", on_click=self._pdf_handler(f["id"])),
            ], spacing=4, tight=True)
            filas.append(row_card(
                t, ft.Row([main, der], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                on_click=lambda e, fac=f: self._editar(fac)))
        self.lista.controls = filas or [empty(t, "No hay facturas. Tocá + para crear una.")]

    def build(self) -> ft.Control:
        app = self.app
        t = app.t
        facturas = app.db.get_facturas()
        total = sum(f.get("total") or 0 for f in facturas)

        def kpi(k, v, d):
            return ft.Container(expand=True, bgcolor=t["surface"], border=BALL(1, t["line"]),
                                border_radius=14, padding=PADS(13, 14),
                                content=ft.Column([
                                    ft.Text(k.upper(), size=10, weight=ft.FontWeight.W_800,
                                            color=t["faint"]),
                                    ft.Text(v, size=21, weight=ft.FontWeight.W_800, color=t["ink"]),
                                    ft.Text(d, size=11, color=t["muted"]),
                                ], spacing=1, tight=True))

        kpis = ft.Row([kpi("Total emitido", fmt_ar(total), "en total"),
                       kpi("Facturas", fmt_cantidad_corta(len(facturas)), "en total")], spacing=10)
        self.lista = ft.Column(spacing=9)
        self._fill()
        return ft.Column([
            ft.Row([titulo(t, "Facturas", "Emití y gestioná tus facturas."),
                    ft.Container(expand=True), add_button(t, self.nueva)],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=14), kpis, ft.Container(height=12),
            search(t, "Buscar por número o cliente…",
                   lambda e: (self._fill(e.control.value), self.lista.update())),
            ft.Container(height=12), self.lista,
        ], spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)
