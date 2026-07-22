"""Pasos Gherkin — Etiquetas (features/etiquetas.feature)."""
from __future__ import annotations

import asyncio

from pytest_bdd import scenarios, when, then, parsers

import plataforma
from views.etiquetas import EtiquetasView
from conftest import producto_por_nombre

scenarios("features/etiquetas.feature")


@when(parsers.parse('selecciono el producto "{nombre}" para etiquetar'))
def _sel(app, db, context, nombre):
    v = EtiquetasView(app)
    v.build()
    v._sel_producto(producto_por_nombre(db, nombre))
    context["view"] = v


@when(parsers.parse('pongo en la primera fila talle "{talle}" cantidad {cant:d}'))
def _primera_fila(context, talle, cant):
    fila = context["view"].rows[0]
    fila["talle_ctrl"].value = talle
    fila["cant_ctrl"].value = str(cant)


@when(parsers.parse('agrego una fila con talle "{talle}" cantidad {cant:d}'))
def _agrego_fila(context, talle, cant):
    v = context["view"]
    v._add_row()
    v.rows[-1]["talle_ctrl"].value = talle
    v.rows[-1]["cant_ctrl"].value = str(cant)


@when("sumo las filas a la cola")
def _sumo(context):
    context["view"]._add_to_queue()


@when("borro la primera entrada de la cola")
def _borro_cola(context):
    context["view"]._del_queue(0)


@when("limpio la cola")
def _limpio(context):
    context["view"]._clear()


@when("genero el PDF de etiquetas")
def _genero(context, monkeypatch):
    async def _fake(a, ruta, **kwargs):
        context["ruta"] = str(ruta)
        return True
    monkeypatch.setattr(plataforma, "entregar_pdf", _fake)
    asyncio.run(context["view"]._generar())


@then(parsers.parse('hay {n:d} fila de talle'))
def _cant_filas(context, n):
    assert len(context["view"].rows) == n


@then(parsers.parse('la primera fila tiene talle "{talle}"'))
def _primera_talle(context, talle):
    assert context["view"].rows[0]["talle"] == talle


@then(parsers.parse('la cola tiene {n:d} entradas'))
def _cola_n(context, n):
    assert len(context["view"].queue) == n


@then(parsers.re(r'la cola tiene (?P<a>\d+) etiquetas del talle "(?P<ta>[^"]*)" '
                 r'y (?P<b>\d+) del talle "(?P<tb>[^"]*)"'))
def _cola_detalle(context, a, ta, b, tb):
    porcant = {q["talle"]: q["cantidad"] for q in context["view"].queue}
    assert porcant[ta] == int(a) and porcant[tb] == int(b)


@then(parsers.parse('la primera entrada de la cola tiene talle "{talle}" y cantidad {cant:d}'))
def _primera_entrada(context, talle, cant):
    q = context["view"].queue[0]
    assert q["talle"] == talle and q["cantidad"] == cant


@then("se entregó un archivo PDF")
def _pdf(context):
    assert context.get("ruta", "").endswith(".pdf")
