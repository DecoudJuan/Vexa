"""Tests de la importación de productos (mapeo core + subpágina)."""
from __future__ import annotations

import flet as ft
import pytest

from views.import_productos import ImportProductosView
from vexa_core.utils import excel_import as xls


@pytest.fixture
def csv(tmp_path):
    p = tmp_path / "lista.csv"
    p.write_text("nombre,precio,codigo,talle\n"
                 "FAJA LUMBAR,9800,020,1\n"
                 "FAJA LUMBAR,9800,020,2\n"
                 "CALZA,12400,060,\n", encoding="utf-8")
    return str(p)


def test_sugerir_mapeo(csv):
    headers, _filas = xls.leer_hoja(csv, None)
    mapeo = xls.sugerir_mapeo(headers)
    assert mapeo["nombre"] == 0
    assert mapeo["precio"] == 1
    assert mapeo["codigo"] == 2
    assert mapeo["talle"] == 3


def test_filas_a_items(csv):
    _h, filas = xls.leer_hoja(csv, None)
    items = xls.filas_a_items(filas, xls.sugerir_mapeo(_h))
    assert len(items) == 3
    assert items[0]["nombre"] == "FAJA LUMBAR"
    assert items[0]["pvp"] == 9800


def test_build_ok(app, csv):
    v = ImportProductosView(app, csv)
    assert isinstance(v.build(), ft.Column)
    assert v._imp["mapeo"]["nombre"] == 0


def test_confirmar_importa(app, db, csv):
    v = ImportProductosView(app, csv)
    n0 = len(db.get_productos())
    v._confirmar()
    assert len(db.get_productos()) > n0
    assert app.subpage is None  # cerró la subpágina


def test_confirmar_replace_vacia_antes(app, db, csv):
    db.upsert_conceptos([{"nombre": "VIEJO", "codigo": "999", "talle": "", "pvp": 1}])
    v = ImportProductosView(app, csv)
    v._imp["replace"] = True
    v._confirmar()
    nombres = {p["nombre"] for p in db.get_productos()}
    assert "VIEJO" not in nombres


def test_set_map_rerenderea(app, csv):
    app.abrir_subpagina(ImportProductosView(app, csv))
    v = app.subpage
    v._set_map("codigo", -1)         # quitar mapeo de código
    assert v._imp["mapeo"]["codigo"] is None
    assert app.subpage is v          # sigue en la subpágina (no crasheó)


def test_confirmar_sin_items_no_importa(app, db, csv):
    v = ImportProductosView(app, csv)
    v._imp["mapeo"] = {"nombre": None, "precio": None, "codigo": None, "talle": None}
    n0 = len(db.get_productos())
    v._confirmar()
    assert len(db.get_productos()) == n0  # nada importado
