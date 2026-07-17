"""E2E de flujo: importar catálogo mockeado (CSV y XLSX) → mapeo → confirmar."""
from __future__ import annotations

import flet as ft
import pytest

from views.import_productos import ImportProductosView


@pytest.fixture
def csv(tmp_path):
    p = tmp_path / "lista.csv"
    p.write_text("nombre,precio,codigo,talle\n"
                 "FAJA LUMBAR,9800,020,1\n"
                 "FAJA LUMBAR,9800,020,2\n"
                 "CALZA REDUCTORA,12400,060,\n", encoding="utf-8")
    return str(p)


@pytest.fixture
def xlsx(tmp_path):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Precios"
    ws.append(["nombre", "precio", "codigo"])
    ws.append(["GUANTE", "500", "G1"])
    ws.append(["MEDIA", "300", "M1"])
    wb.create_sheet("Otra").append(["basura"])
    p = tmp_path / "cat.xlsx"
    wb.save(str(p))
    return str(p)


def test_import_csv_detecta_y_agrupa(app, db, csv):
    v = ImportProductosView(app, csv)
    assert v._imp["mapeo"]["nombre"] == 0
    v._confirmar()
    prods = db.get_productos()
    # FAJA LUMBAR agrupa 2 talles en 1 fila + CALZA = 2 productos
    assert len(prods) == 2
    faja = [p for p in prods if p["nombre"] == "FAJA LUMBAR"][0]
    assert set(faja["talles"]) == {"1", "2"}
    assert app.subpage is None


def test_import_replace_vacia_antes(app, db, csv):
    db.upsert_conceptos([{"nombre": "VIEJO", "codigo": "999", "talle": "", "pvp": 1}])
    v = ImportProductosView(app, csv)
    v._imp["replace"] = True
    v._confirmar()
    assert "VIEJO" not in {p["nombre"] for p in db.get_productos()}


def test_import_quitar_mapeo_no_rompe(app, csv):
    app.abrir_subpagina(ImportProductosView(app, csv))
    v = app.subpage
    v._set_map("talle", -1)
    assert v._imp["mapeo"]["talle"] is None
    assert isinstance(v.build(), ft.Column)


def test_import_xlsx_hojas(app, db, xlsx):
    v = ImportProductosView(app, xlsx)
    assert v._imp["hojas"] == ["Precios", "Otra"]
    assert v._imp["hoja"] == "Precios"
    v._confirmar()
    assert len(db.get_productos()) == 2


def test_import_sin_mapeo_no_importa(app, db, csv):
    v = ImportProductosView(app, csv)
    v._imp["mapeo"] = {"nombre": None, "precio": None, "codigo": None, "talle": None}
    v._confirmar()
    assert db.get_productos() == []
