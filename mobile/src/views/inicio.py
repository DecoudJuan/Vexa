"""Inicio — dashboard: saludo, KPIs, facturas recientes y accesos rápidos."""
from __future__ import annotations

from datetime import date, datetime

import flet as ft

from theme import PADS, BALL, soft
from widgets import card, clabel, empty
from vexa_core.utils.helpers import fmt_ar, fmt_cantidad_corta


class InicioView:
    def __init__(self, app):
        self.app = app

    def build(self) -> ft.Control:
        app = self.app
        t = app.t
        emp = app.db.get_datos_empresa()
        facturas = app.db.get_facturas()
        n_fact = len(facturas)
        n_cli = len(app.db.get_all_clientes())
        n_prod = len(app.db.get_productos())
        mes = date.today().strftime("%Y-%m")
        n_mes = sum(1 for f in facturas if str(f.get("fecha", "")).startswith(mes))

        hora = datetime.now().hour
        saludo = ("Buenos días" if 6 <= hora < 12
                  else "Buenas tardes" if 12 <= hora < 20 else "Buenas noches")
        nombre = (emp.get("nombre") or "").strip()
        titulo = f"{saludo},\n{nombre}." if nombre else saludo
        fecha_txt = date.today().strftime("%d/%m/%Y")

        def kpi(k, v, d, destacado=False):
            fg = t["accent_ink"] if destacado else t["ink"]
            sub = soft(t["accent_ink"], 0.85) if destacado else t["muted"]
            klr = soft(t["accent_ink"], 0.85) if destacado else t["faint"]
            return ft.Container(
                expand=True, bgcolor=t["accent"] if destacado else t["surface"],
                border=None if destacado else BALL(1, t["line"]), border_radius=16,
                padding=PADS(14, 15),
                content=ft.Column([
                    ft.Text(k.upper(), size=10, weight=ft.FontWeight.W_800, color=klr),
                    ft.Text(v, size=23, weight=ft.FontWeight.W_800, color=fg),
                    ft.Text(d, size=11, color=sub),
                ], spacing=1, tight=True))

        kpis = ft.Column([
            ft.Row([kpi("Facturas este mes", fmt_cantidad_corta(n_mes), "este mes", destacado=True),
                    kpi("Facturas", fmt_cantidad_corta(n_fact), "emitidas")], spacing=10),
            ft.Row([kpi("Clientes", fmt_cantidad_corta(n_cli), "en cartera"),
                    kpi("Productos", fmt_cantidad_corta(n_prod), "en catálogo")], spacing=10),
        ], spacing=10)

        def acceso(icon, texto, on_click):
            return ft.Container(
                expand=True, bgcolor=t["surface"], border=BALL(1, t["line"]), border_radius=14,
                padding=PADS(14, 14), on_click=on_click, ink=True,
                content=ft.Row([
                    ft.Container(width=34, height=34, border_radius=10, bgcolor=soft(t["accent"], 0.12),
                                 alignment=ft.Alignment.CENTER,
                                 content=ft.Icon(icon, size=18, color=t["accent"])),
                    ft.Text(texto, size=12.5, weight=ft.FontWeight.W_600, color=t["ink"],
                            max_lines=2, expand=True),
                ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER))

        accesos = ft.Column([
            ft.Row([acceso(ft.Icons.RECEIPT_LONG_OUTLINED, "Crear factura",
                           lambda e: app.views["facturas"].nueva()),
                    acceso(ft.Icons.LOCAL_OFFER_OUTLINED, "Imprimir etiquetas",
                           lambda e: app.set_tab("etiquetas"))], spacing=10),
            ft.Row([acceso(ft.Icons.PERSON_ADD_ALT, "Nuevo cliente",
                           lambda e: app.views["clientes"]._nuevo()),
                    acceso(ft.Icons.ADD_BOX_OUTLINED, "Nuevo producto",
                           lambda e: app.views["productos"]._nuevo())], spacing=10),
        ], spacing=10)

        return ft.Column([
            ft.Text(fecha_txt, size=12, color=t["muted"]),
            ft.Text(titulo, size=24, weight=ft.FontWeight.W_800, color=t["ink"]),
            ft.Container(height=12), kpis,
            ft.Container(height=12), clabel(t, "ACCESOS RÁPIDOS"), ft.Container(height=8), accesos,
        ], spacing=0, scroll=ft.ScrollMode.HIDDEN, expand=True)
