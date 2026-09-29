"""Regresión: editar un precio en el form no debe multiplicarlo por 10^n.

Antes el form precargaba '14000.0' y al guardar borraba TODOS los puntos
(tratados como miles) → 140000; cada edición sumaba otro cero."""
from __future__ import annotations

import flet as ft
import pytest

from vexa_core.utils.helpers import fmt_num_input, parse_float
from views.productos import ProductosView


def _walk(c):
    yield c
    for attr in ("content", "controls"):
        v = getattr(c, attr, None)
        if isinstance(v, list):
            for x in v:
                yield from _walk(x)
        elif isinstance(v, ft.Control):
            yield from _walk(v)


def _campo(sheet, valor):
    return next(c for c in _walk(sheet) if isinstance(c, ft.TextField) and c.value == valor)


def _guardar(sheet):
    for c in _walk(sheet):
        textos = [x.value for x in _walk(c) if isinstance(x, ft.Text)]
        if getattr(c, "on_click", None) and "Guardar" in textos and not isinstance(c, ft.Text):
            c.on_click(None)
            return
    raise AssertionError("sin botón Guardar")


@pytest.mark.parametrize("tipeado, esperado", [
    ("14500", 14500), ("14.500", 14500), ("14500,50", 14500.5), ("14.500,50", 14500.5),
])
def test_editar_precio_desde_form(app, db, tipeado, esperado):
    db.upsert_conceptos([{"nombre": "FAJA", "codigo": "1", "talle": "", "pvp": 14000}])
    ProductosView(app)._editar(db.get_productos()[0])
    sheet = app.page.last_dialog
    campo = _campo(sheet, "14000")          # se precarga sin '.0'
    campo.value = tipeado
    _guardar(sheet)
    assert db.get_productos()[0]["pvp"] == esperado


def test_guardar_sin_tocar_no_cambia_el_precio(app, db):
    db.upsert_conceptos([{"nombre": "FAJA", "codigo": "1", "talle": "", "pvp": 14000.5}])
    for _ in range(3):
        ProductosView(app)._editar(db.get_productos()[0])
        _guardar(app.page.last_dialog)
    assert db.get_productos()[0]["pvp"] == 14000.5


@pytest.mark.parametrize("txt, v", [
    ("14000.0", 14000), ("14.500", 14500), ("1.234.567", 1234567), ("1.234,56", 1234.56),
    ("1234,56", 1234.56), ("1234.56", 1234.56), ("1.5", 1.5), ("$ 14.500", 14500),
    ("-2.500", -2500), ("", 0), ("abc", 0),
])
def test_parse_float(txt, v):
    assert parse_float(txt) == v


@pytest.mark.parametrize("v", [14000, 14000.5, 1.125, 0, -2500.25])
def test_fmt_num_input_roundtrip(v):
    assert "." not in fmt_num_input(v)
    assert parse_float(fmt_num_input(v)) == v
