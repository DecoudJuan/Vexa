"""Pasos Gherkin — Datos de la empresa y configuración (features/empresa.feature)."""
from __future__ import annotations

from pytest_bdd import scenarios, when, then, parsers

scenarios("features/empresa.feature")


@when(parsers.re(r'guardo la empresa "(?P<nombre>[^"]*)" con calle "(?P<calle>[^"]*)" '
                 r'número "(?P<numero>[^"]*)"'))
def _guardo_dir(app, nombre, calle, numero):
    app.guardar_empresa({"nombre": nombre, "calle": calle, "numero": numero})


@when(parsers.parse('guardo la empresa "{nombre}" con la moneda "{moneda}"'))
def _guardo_moneda(app, nombre, moneda):
    app.guardar_empresa({"nombre": nombre, "moneda": moneda})


@when("intento guardar la empresa sin nombre")
def _sin_nombre(app, context):
    try:
        app.guardar_empresa({"nombre": "   "})
    except ValueError as e:
        context["error"] = e


@then(parsers.parse('la dirección guardada es "{direccion}"'))
def _dir(db, direccion):
    assert db.get_datos_empresa()["direccion"] == direccion


@then(parsers.parse('la moneda guardada es "{moneda}"'))
def _moneda(db, moneda):
    assert db.get_datos_empresa()["moneda"] == moneda
