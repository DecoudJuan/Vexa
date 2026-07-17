"""Tests del shell: navegación entre tabs y subpáginas."""
from __future__ import annotations

import flet as ft


class _StubView:
    def __init__(self):
        self.built = 0

    def build(self):
        self.built += 1
        return ft.Text("stub")


def test_set_tab_cambia(app):
    app.set_tab("clientes")
    assert app.tab == "clientes"


def test_set_tab_limpia_subpagina(app):
    app.abrir_subpagina(_StubView())
    assert app.subpage is not None
    app.set_tab("productos")
    assert app.subpage is None
    assert app.tab == "productos"


def test_abrir_subpagina_render_usa_build(app):
    sv = _StubView()
    app.abrir_subpagina(sv)
    assert app.subpage is sv
    assert sv.built >= 1          # render() la construyó
    assert app.page.controls       # montó el árbol


def test_cerrar_subpagina_default_reabre_config(app):
    app.abrir_subpagina(_StubView())
    app.cerrar_subpagina()        # default reopen_config=True
    assert app.subpage is None
    assert app._config_sheet is not None   # Configuración reabierta


def test_cerrar_subpagina_sin_config(app):
    app.abrir_subpagina(_StubView())
    app.cerrar_subpagina(reopen_config=False)
    assert app.subpage is None
    assert app._config_sheet is None


def test_brand_vuelve_a_inicio_desde_subpagina(app):
    app.tab = "inicio"
    app.abrir_subpagina(_StubView())
    app.set_tab("inicio")         # tocar la marca estando en subpágina
    assert app.subpage is None
    assert app.tab == "inicio"
