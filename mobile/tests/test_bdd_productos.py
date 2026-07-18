"""Pasos Gherkin — Catálogo de productos (features/productos.feature)."""
from __future__ import annotations

from pytest_bdd import scenarios, when, then, parsers

from views.productos import ProductosView
from conftest import producto_por_nombre

scenarios("features/productos.feature")


@when(parsers.re(r'doy de alta el producto "(?P<nombre>[^"]*)" código "(?P<codigo>[^"]*)" '
                 r'talles "(?P<talles>[^"]*)" precio (?P<precio>\d+)'))
def _alta(app, nombre, codigo, talles, precio):
    ProductosView(app)._guardar(
        {"nombre": nombre, "codigo": codigo, "talles": talles, "precio": int(precio)})


@when(parsers.re(r'intento dar de alta el producto "(?P<nombre>[^"]*)" código "(?P<codigo>[^"]*)" '
                 r'talles "(?P<talles>[^"]*)" precio (?P<precio>\d+)'))
def _alta_falla(app, context, nombre, codigo, talles, precio):
    try:
        ProductosView(app)._guardar(
            {"nombre": nombre, "codigo": codigo, "talles": talles, "precio": int(precio)})
    except ValueError as e:
        context["error"] = e


@when(parsers.parse('cambio el precio del producto "{nombre}" a {precio:d}'))
def _cambio_precio(app, db, nombre, precio):
    prod = producto_por_nombre(db, nombre)
    ProductosView(app)._guardar(
        {"nombre": nombre, "codigo": prod["codigo"],
         "talles": ", ".join(prod["talles"]), "precio": precio}, orig=prod)


@then(parsers.parse('el producto "{nombre}" tiene precio {precio:d}'))
def _check_precio(db, nombre, precio):
    assert producto_por_nombre(db, nombre)["pvp"] == precio


@when(parsers.parse('borro el producto "{nombre}" código "{codigo}"'))
def _borro(db, nombre, codigo):
    db.delete_producto(nombre, codigo)
