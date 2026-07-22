"""E2E de flujo: etiquetas — elegir producto, modificar talle, agregar varias,
armar la cola y generar el PDF."""
from __future__ import annotations

import pytest

from views.etiquetas import EtiquetasView


@pytest.fixture
def faja(db):
    db.upsert_conceptos([
        {"nombre": "FAJA LUMBAR", "codigo": "020", "talle": "1", "pvp": 9800},
        {"nombre": "FAJA LUMBAR", "codigo": "020", "talle": "2", "pvp": 9800},
        {"nombre": "FAJA LUMBAR", "codigo": "020", "talle": "3", "pvp": 9800},
    ])
    return [p for p in db.get_productos() if p["nombre"] == "FAJA LUMBAR"][0]


def test_seleccionar_producto_arma_primera_fila(app, faja):
    v = EtiquetasView(app)
    v.build()
    v._sel_producto(faja)
    assert v.sel["nombre"] == "FAJA LUMBAR"
    assert len(v.rows) == 1
    assert v.rows[0]["talle"] == "1"


def test_modificar_talle_y_agregar_varias(app, faja):
    v = EtiquetasView(app)
    v.build()
    v._sel_producto(faja)
    # modificar la primera fila (talle 2, cantidad 5)
    v.rows[0]["talle_ctrl"].value = "2"
    v.rows[0]["cant_ctrl"].value = "5"
    # agregar una segunda fila (talle 3, cantidad 3)
    v._add_row()
    v.rows[1]["talle_ctrl"].value = "3"
    v.rows[1]["cant_ctrl"].value = "3"
    v._add_to_queue()
    assert len(v.queue) == 2
    assert {q["talle"] for q in v.queue} == {"2", "3"}
    porcant = {q["talle"]: q["cantidad"] for q in v.queue}
    assert porcant["2"] == 5 and porcant["3"] == 3


def test_borrar_fila_de_talle(app, faja):
    v = EtiquetasView(app)
    v.build()
    v._sel_producto(faja)
    v._add_row()
    assert len(v.rows) == 2
    v._del_row(1)
    assert len(v.rows) == 1


def test_cola_borrar_y_limpiar(app, faja):
    v = EtiquetasView(app)
    v.build()
    v._sel_producto(faja)
    v.rows[0]["talle_ctrl"].value = "1"
    v._add_to_queue()
    v.rows[0]["talle_ctrl"].value = "2"   # otro talle → segunda entrada distinta
    v._add_to_queue()
    assert len(v.queue) == 2
    v._del_queue(0)
    assert len(v.queue) == 1
    v._clear()
    assert v.queue == []


def test_cola_fusiona_mismo_producto_y_talle(app, faja):
    """Agregar el mismo producto+talle dos veces suma la cantidad en una sola
    entrada, en vez de duplicar la fila."""
    v = EtiquetasView(app)
    v.build()
    v._sel_producto(faja)
    v.rows[0]["talle_ctrl"].value = "1"
    v._add_to_queue()
    v._add_to_queue()
    assert len(v.queue) == 1
    assert v.queue[0]["talle"] == "1"
    assert v.queue[0]["cantidad"] == 2


def test_generar_pdf(app, faja, monkeypatch):
    import asyncio
    import plataforma
    capt = {}

    async def _fake(a, ruta, **kwargs):
        capt["ruta"] = str(ruta)
        return True

    monkeypatch.setattr(plataforma, "entregar_pdf", _fake)
    v = EtiquetasView(app)
    v.build()
    v._sel_producto(faja)
    v.rows[0]["cant_ctrl"].value = "14"
    v._add_to_queue()
    asyncio.run(v._generar())
    assert capt.get("ruta", "").endswith(".pdf")


def test_producto_universal_sin_talles(app, db):
    db.upsert_conceptos([{"nombre": "HOMBRERA", "codigo": "026", "talle": "", "pvp": 7200}])
    prod = [p for p in db.get_productos() if p["nombre"] == "HOMBRERA"][0]
    v = EtiquetasView(app)
    v.build()
    v._sel_producto(prod)
    v._add_to_queue()
    assert len(v.queue) == 1
    assert v.queue[0]["talle"] == ""
