"""Clientes — listado con búsqueda + alta/edición/borrado (paridad con desktop)."""
from __future__ import annotations

import flet as ft

from theme import soft
from widgets import titulo, search, row_card, empty, add_button
from vexa_core.utils.helpers import CONDICIONES_IVA, PROVINCIAS_AR, valor_valido, parse_float

IVA_OPTS = list(CONDICIONES_IVA)


class ClientesView:
    def __init__(self, app):
        self.app = app
        self.lista = ft.Column(spacing=9)

    # -------------------------------------------------------------- alta/edición
    def _campos(self, c: dict, cuits: list[str]) -> list:
        return [
            {"key": "nombre", "label": "Nombre *", "value": c.get("nombre")},
            {"key": "cuits", "label": "CUIT / CUIL", "tipo": "chips", "value": cuits,
             "format": "cuit", "hint": "Agregá un CUIT/CUIL y Enter…"},
            {"key": "condicion_iva", "label": "Condición IVA", "tipo": "dropdown",
             "value": c.get("condicion_iva") or "", "options": [""] + IVA_OPTS},
            {"key": "direccion", "label": "Dirección", "value": c.get("direccion")},
            [{"key": "cp", "label": "C.P.", "value": valor_valido(c.get("cp"))},
             {"key": "localidad", "label": "Localidad", "value": c.get("localidad")}],
            {"key": "provincia", "label": "Provincia", "tipo": "dropdown", "editable": True,
             "value": c.get("provincia") or "", "options": [""] + list(PROVINCIAS_AR)},
            [{"key": "telefono1", "label": "Teléfono", "value": c.get("telefono1"),
              "hint": "+54 9 11 5555-5555"},
             {"key": "fax", "label": "Fax", "value": c.get("fax")}],
            [{"key": "email", "label": "Email", "value": c.get("email")},
             {"key": "persona_contacto", "label": "Contacto", "value": c.get("persona_contacto")}],
            {"key": "bonificacion", "label": "Bonificación (%)", "tipo": "number",
             "value": c.get("bonificacion") or 0},
            {"key": "banco", "label": "Banco", "value": c.get("banco")},
            {"key": "comentarios", "label": "Comentarios", "tipo": "multiline",
             "value": c.get("comentarios")},
        ]

    def _guardar(self, d: dict, orig: dict, cid: int | None):
        nombre = (d.get("nombre") or "").strip()
        if not nombre:
            raise ValueError("El nombre del cliente es obligatorio.")
        cuits = [x for x in (d.get("cuits") or []) if str(x).strip()]
        data = {k: (d.get(k) or None) for k in (
            "condicion_iva", "direccion", "cp", "localidad", "provincia", "telefono1", "fax",
            "email", "persona_contacto", "banco", "comentarios")}
        data["nombre"] = nombre
        data["nif"] = cuits[0] if cuits else None
        data["bonificacion"] = parse_float(str(d.get("bonificacion") or 0))
        # preservar valores históricos que la UI no edita
        data["retencion"] = orig.get("retencion")
        data["recargo_equiv"] = orig.get("recargo_equiv")
        if cid:
            self.app.db.update_cliente(cid, data)
            self.app.db.set_cuits_cliente(cid, cuits)
        else:
            nid = self.app.db.create_cliente(data)
            self.app.db.set_cuits_cliente(nid, cuits)

    def _nuevo(self):
        self.app.open_form("Nuevo cliente", self._campos({}, []),
                           on_save=lambda d: self._guardar(d, {}, None))

    def _editar(self, c: dict):
        cid = c["id"]
        full = self.app.db.get_cliente(cid) or c
        cuits = self.app.db.get_cuits_cliente(cid)
        if not cuits and valor_valido(full.get("nif")):
            cuits = [full["nif"]]
        cuits = [x for x in cuits if valor_valido(x)]
        self.app.open_form(
            "Editar cliente", self._campos(full, cuits),
            on_save=lambda d: self._guardar(d, full, cid),
            on_delete=lambda: self.app.db.delete_cliente(cid),
            borrar_texto="¿Seguro que querés eliminar este cliente?")

    # -------------------------------------------------------------------- lista
    def _fill(self, texto: str = ""):
        app = self.app
        t = app.t
        clientes = app.db.get_all_clientes(texto or None)

        def inicial(n: str) -> str:
            parts = [w[0] for w in (n or "").split() if w and w[0].isupper()]
            return "".join(parts[:2]) or (n or "?")[:1].upper()

        filas = []
        for c in clientes:
            avatar = ft.Container(width=42, height=42, border_radius=12,
                                  bgcolor=soft(t["accent"], 0.12), alignment=ft.Alignment.CENTER,
                                  content=ft.Text(inicial(c["nombre"]), weight=ft.FontWeight.W_800,
                                                  size=14, color=t["accent"]))
            main = ft.Column([
                ft.Text(c["nombre"] or "(sin nombre)", size=14, weight=ft.FontWeight.W_700,
                        color=t["ink"], no_wrap=True),
                ft.Text(c.get("localidad") or "", size=12, color=t["muted"], no_wrap=True),
            ], spacing=1, expand=True, tight=True)
            filas.append(row_card(
                t, ft.Row([avatar, main, ft.Text("›", size=18, color=t["faint"])],
                          vertical_alignment=ft.CrossAxisAlignment.CENTER),
                on_click=lambda e, cli=c: self._editar(cli)))
        self.lista.controls = filas or [empty(t, "Sin resultados")]

    def build(self) -> ft.Control:
        t = self.app.t
        self.lista = ft.ListView(spacing=9, expand=True)   # virtualizado (solo pinta lo visible)
        self._fill()
        # Header (título + + + buscador) FIJO arriba; solo la lista se desliza.
        return ft.Column([
            ft.Row([titulo(t, "Clientes", "Alta y gestión de clientes."), ft.Container(expand=True),
                    add_button(t, self._nuevo)], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=14),
            search(t, "Buscar por nombre, CUIT o email…",
                   lambda e: self.app.debounce("cli_search", 0.25,
                                               lambda: (self._fill(e.control.value), self.lista.update()))),
            ft.Container(height=12),
            ft.Container(expand=True, content=self.lista),
        ], spacing=0, expand=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
