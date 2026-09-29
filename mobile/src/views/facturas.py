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
from vexa_core.utils.helpers import fmt_ar, fmt_cantidad_corta, fmt_num_input, parse_float, etiqueta_concepto
import plataforma
# NOTA: `pdf_generator` (reportlab) NO se importa acá arriba a propósito: arrastra
# reportlab al cold start aunque el usuario nunca genere un PDF. Se importa perezoso
# dentro del handler de PDF (más abajo). Ídem etiquetas.py e import_productos.py.


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
            self._cliente_id = None   # arranca vacío: el usuario elige o crea el cliente
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
        self._post = None
        self.app._form_escape = self._try_close
        self._sheet = ft.BottomSheet(
            content=ft.Stack([self._content(), self._banner], expand=True), bgcolor=t["ground"],
            fullscreen=True, dismissible=False, draggable=False, show_drag_handle=False,
            on_dismiss=lambda e: self._on_sheet_dismiss())
        self.app.page.show_dialog(self._sheet)

    def _new_row(self) -> dict:
        return {"prod": None, "texto": "", "cant": 1, "pvp": 0.0, "cant_ctrl": None, "pvp_ctrl": None}

    # -------- líneas (columna persistente; se actualiza sin recrear el modal)
    def _prod_label(self, r: dict) -> str:
        if r["prod"] is not None:
            p = self._prods[r["prod"]]
            return etiqueta_concepto(p["nombre"], p.get("codigo"))
        return r["texto"] or "Elegí un producto"

    def _build_line(self, i: int, r: dict) -> ft.Control:
        t = self.app.t
        tiene = r["prod"] is not None or bool(r["texto"])
        # Campo full-width que abre el selector full-screen (evita el dropdown que tapaba).
        prod_dd = ft.Container(
            expand=True, ink=True, on_click=lambda e, idx=i: self._abrir_sel_prod(idx),
            bgcolor=t["surface2"], border=BALL(1, t["line2"]), border_radius=10, padding=PADS(9, 10),
            content=ft.Row([ft.Container(expand=True, content=self.app.marquee(
                                self._prod_label(r), 13, None, t["ink"] if tiene else t["faint"])),
                            ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=18, color=t["faint"])],
                           vertical_alignment=ft.CrossAxisAlignment.CENTER))
        cant_tf = ft.TextField(value=fmt_num_input(r["cant"]), keyboard_type=ft.KeyboardType.NUMBER,
                               border_color=t["line2"], filled=True, border_radius=10,
                               bgcolor=t["surface2"], color=t["ink"], text_size=13,
                               content_padding=PADS(8, 8), width=54, text_align=ft.TextAlign.CENTER,
                               on_change=lambda e: self._recalc_total())
        neg = (r["pvp"] or 0) < 0   # precio negativo = línea "a favor" (crédito)
        pvp_tf = ft.TextField(value=fmt_num_input(r["pvp"]), keyboard_type=ft.KeyboardType.NUMBER,
                              border_color=t["line2"], filled=True, border_radius=10,
                              bgcolor=t["surface2"], color=t["danger"] if neg else t["ink"],
                              text_size=13, content_padding=PADS(8, 8), width=84,
                              text_align=ft.TextAlign.RIGHT,
                              label="A favor" if neg else None,
                              label_style=ft.TextStyle(color=t["danger"], size=10,
                                                       weight=ft.FontWeight.W_700),
                              on_change=lambda e, row=r: (self._recalc_total(), self._upd_favor(row)))
        r["cant_ctrl"], r["pvp_ctrl"] = cant_tf, pvp_tf
        x = ft.IconButton(ft.Icons.CLOSE, icon_size=16, icon_color=t["faint"],
                          on_click=lambda e, idx=i: self._del_row(idx))
        return ft.Container(margin=MAR(bottom=12), content=ft.Row(
            [prod_dd, cant_tf, pvp_tf, x], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=6))

    def _upd_favor(self, r: dict):
        """Marca la línea como «A favor» (rojo + leyenda) cuando el precio es
        negativo, sin recrear la fila (se actualiza en vivo al tipear)."""
        tf = r.get("pvp_ctrl")
        if tf is None:
            return
        t = self.app.t
        neg = parse_float(str(tf.value)) < 0
        tf.color = t["danger"] if neg else t["ink"]
        tf.label = "A favor" if neg else None
        try:
            tf.update()
        except Exception:  # noqa: BLE001
            pass

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

    def _abrir_sel_prod(self, idx):
        ops = [(etiqueta_concepto(p["nombre"], p.get("codigo")), j) for j, p in enumerate(self._prods)]

        def elegir(j):
            self._sync()
            self._rows[idx]["prod"] = j
            self._rows[idx]["texto"] = ""
            self._rows[idx]["pvp"] = self._prods[j]["pvp"] or 0
            self._dirty = True
            self._refresh_lineas()
            self._recalc_total()

        def otro(txt):
            self._sync()
            self._rows[idx]["prod"] = None
            self._rows[idx]["texto"] = txt.strip()
            self._dirty = True
            self._refresh_lineas()
            self._recalc_total()

        self.app.abrir_selector_full("Elegí un producto", ops, elegir, on_nuevo=otro,
                                     nuevo_prefix="Otro:", valor=self._rows[idx]["prod"])

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

    def _cliente_nombre(self):
        return next((c["nombre"] for c in self._clientes if c["id"] == self._cliente_id), None)

    def _upd_cli_txt(self):
        nombre = self._cliente_nombre()
        t = self.app.t
        self._cli_txt.value = nombre or "Elegí o creá un cliente"
        self._cli_txt.color = t["ink"] if nombre else t["faint"]
        try:
            self._cli_txt.update()
        except Exception:  # noqa: BLE001
            pass

    def _aplicar_bonif_cliente(self):
        """Autocompleta la bonificación de la factura con la del cliente elegido."""
        if not self._cliente_id:
            return
        c = self.app.db.get_cliente(self._cliente_id) or {}
        self._bonif = float(c.get("bonificacion") or 0)
        tf = getattr(self, "_bonif_tf", None)
        if tf is not None:
            tf.value = f"{self._bonif:g}"
            try:
                tf.update()
            except Exception:  # noqa: BLE001
                pass
        self._recalc_total()

    def _abrir_sel_cliente(self):
        ops = [(c["nombre"], c["id"]) for c in self._clientes]

        def elegir(cid):
            self._cliente_id = cid
            self._dirty = True
            self._upd_cli_txt()
            self._aplicar_bonif_cliente()

        def crear(txt):
            txt = (txt or "").strip()
            if not txt:
                return
            nid = self.app.db.create_cliente({"nombre": txt})
            self._clientes = self.app.db.get_all_clientes()
            self._cliente_id = nid
            self._dirty = True
            self._upd_cli_txt()
            self.app.snack(f"Cliente «{txt}» creado")

        self.app.abrir_selector_full("Elegí o creá un cliente", ops, elegir, on_nuevo=crear,
                                     nuevo_prefix="Crear cliente", valor=self._cliente_id)

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

    def _on_sheet_dismiss(self):
        # Corre cuando la hoja YA cerró: acá sí se puede render() sin dejar scrim negro.
        fn = getattr(self, "_post", None)
        self._post = None
        if fn:
            fn()

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
            if (r["pvp"] or 0) == 0:      # aviso rápido si falta el precio
                # Un precio negativo es válido: es una línea "a favor" (crédito)
                # que resta del total; solo se bloquea el 0 (precio sin cargar).
                self.app.snack(f"«{self._prod_label(r)}» tiene precio en 0")
                return
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
        # Diferir el render al cierre de la hoja (evita el scrim negro de pop+render).
        self._post = lambda: (self.app.render(), self.app.snack("Factura guardada"))
        self._close()

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

        if True:
            # Cliente: campo full-width que abre el selector full-screen (elegir o crear).
            nombre_cli = self._cliente_nombre()
            self._cli_txt = ft.Text(nombre_cli or "Elegí o creá un cliente", size=14, expand=True,
                                    no_wrap=True, color=t["ink"] if nombre_cli else t["faint"])
            cli_dd = ft.Container(
                expand=True, ink=True, on_click=lambda e: self._abrir_sel_cliente(),
                bgcolor=t["surface2"], border=BALL(1, t["line2"]), border_radius=12, padding=PADS(11, 13),
                content=ft.Row([self._cli_txt, ft.Icon(ft.Icons.ARROW_DROP_DOWN, color=t["faint"])],
                               vertical_alignment=ft.CrossAxisAlignment.CENTER))
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
            self._bonif_tf = bonif_tf   # ref para autocompletar con la bonif del cliente
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

        async def _h(_e):
            try:
                from vexa_core.utils.pdf_generator import generar_pdf_documento  # perezoso
                ruta = generar_pdf_documento(app.db, factura_id)
                ok = await plataforma.entregar_pdf(app, ruta)
                if not ok:
                    app.snack("Guardado cancelado")
            except Exception as ex:  # noqa: BLE001
                app.snack(f"Error al generar PDF: {ex}")
        return _h

    def _fill(self, texto: str = "", facturas=None):
        t = self.app.t
        # `facturas` pre-cargadas (las reusa build() para no consultar dos veces).
        if facturas is None:
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
        self.lista = ft.ListView(spacing=9, expand=True)   # virtualizado (solo pinta lo visible)
        self._fill(facturas=facturas)   # reusa la lista ya traída (sin re-consultar)
        # Header (título + + + KPIs + buscador) FIJO; solo la lista se desliza.
        return ft.Column([
            ft.Row([titulo(t, "Facturas", "Emití y gestioná tus facturas."),
                    ft.Container(expand=True), add_button(t, self.nueva)],
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=14), kpis, ft.Container(height=12),
            search(t, "Buscar por número o cliente…",
                   lambda e: self.app.debounce("fac_search", 0.25,
                                               lambda: (self._fill(e.control.value), self.lista.update()))),
            ft.Container(height=12),
            ft.Container(expand=True, content=self.lista),
        ], spacing=0, expand=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
