"""Fixtures para los tests de la app mobile (headless, sin ventana Flet).

`FACTURACION_DATA_DIR` se setea ANTES de importar vexa_core (el módulo db congela
DATA_DIR al importarse). Cada test usa su propia base sqlite (db_path por tmp_path)
para quedar aislado. `page` es un doble de ft.Page con lo mínimo que usa la app.
"""
from __future__ import annotations

import os
import sys
import tempfile
import pathlib

# --- rutas y entorno ANTES de importar vexa_core / la app ---
_SRC = pathlib.Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(_SRC))
os.environ.setdefault("FACTURACION_DATA_DIR", tempfile.mkdtemp(prefix="vexa_tests_"))
os.environ.pop("FLET_APP_STORAGE_DATA", None)

import flet as ft  # noqa: E402
import pytest  # noqa: E402

from vexa_core.database.db import DatabaseManager  # noqa: E402


class FakePage:
    """Doble mínimo de ft.Page: registra controles/diálogos, no dibuja nada."""

    def __init__(self):
        self.platform_brightness = ft.Brightness.LIGHT
        self.height = 1400
        self.width = 1080
        self.controls = []
        self.overlay = []
        self.theme_mode = None
        self.bgcolor = None
        self.services = []
        self.dialogs = []
        self.last_dialog = None
        self.opened_url = None

    def update(self):
        pass

    def run_task(self, *_a, **_k):
        pass

    def show_dialog(self, d):
        self.last_dialog = d
        # Los SnackBar no son diálogos modales apilables (no los cierra pop_dialog).
        if d.__class__.__name__ != "SnackBar":
            self.dialogs.append(d)

    def pop_dialog(self):
        # Como el Flet real: al cerrar dispara on_dismiss (donde se difiere el render).
        if self.dialogs:
            d = self.dialogs.pop()
            h = getattr(d, "on_dismiss", None)
            if h:
                try:
                    h(None)
                except TypeError:
                    h()

    def launch_url(self, url):
        self.opened_url = url


@pytest.fixture
def db(tmp_path):
    m = DatabaseManager(db_path=str(tmp_path / "t.db"))
    m.init_db()
    yield m
    m.engine.dispose()


@pytest.fixture
def page():
    return FakePage()


@pytest.fixture
def app(db, page):
    from app import VexaApp
    return VexaApp(page, db)


@pytest.fixture
def context():
    """Bolsa de estado compartida entre pasos Gherkin (given/when/then) de un escenario."""
    return {}


# --------------------------------------------------------------------------- #
# Pasos Gherkin COMPARTIDOS (pytest-bdd los resuelve globalmente desde conftest).
# Los específicos de cada feature viven en su test_bdd_*.py.
# Se usa parsers.re en los pasos con campos entre comillas que pueden ir vacíos
# (p.ej. talles ""), porque parsers.parse exige al menos un carácter.
# --------------------------------------------------------------------------- #
from pytest_bdd import given, when, then, parsers  # noqa: E402


def crear_producto(db, nombre, codigo, talles, precio):
    """Alta directa en el catálogo (una variante por talle; talles vacío = universal)."""
    lista = [x.strip() for x in (talles or "").split(",") if x.strip()] or [""]
    db.upsert_conceptos([{"nombre": nombre, "codigo": codigo, "talle": t, "pvp": precio}
                         for t in lista])


def producto_por_nombre(db, nombre):
    return next(p for p in db.get_productos() if p["nombre"] == nombre)


# --- Givens de precondición ---
@given("que no hay clientes cargados")
def _sin_clientes(db):
    assert db.get_all_clientes() == []


@given("que no hay productos cargados")
def _sin_productos(db):
    assert db.get_productos() == []


@given("que la base está recién inicializada")
def _base_nueva(db):
    assert db.get_all_clientes() == [] and db.get_productos() == []


@given(parsers.parse('un cliente llamado "{nombre}" en "{loc}"'))
def _dado_cliente(db, context, nombre, loc):
    cid = db.create_cliente({"nombre": nombre, "localidad": loc})
    context["cliente_id"] = cid
    context["cliente_nombre"] = nombre


@given(parsers.re(r'el producto "(?P<nombre>[^"]*)" código "(?P<codigo>[^"]*)" '
                  r'talles "(?P<talles>[^"]*)" precio (?P<precio>\d+)'))
def _dado_producto(db, context, nombre, codigo, talles, precio):
    crear_producto(db, nombre, codigo, talles, int(precio))
    context["producto"] = producto_por_nombre(db, nombre)


# --- Thens de conteo / estado, reusados por varias features ---
@then(parsers.re(r'hay (?P<n>\d+) clientes? cargados?'))
def _cant_clientes(db, n):
    assert len(db.get_all_clientes()) == int(n)


@then(parsers.re(r'hay (?P<n>\d+) productos? en el catálogo'))
def _cant_productos(db, n):
    assert len(db.get_productos()) == int(n)


@then(parsers.re(r'hay (?P<n>\d+) facturas? emitidas?'))
def _cant_facturas(db, n):
    assert len(db.get_facturas()) == int(n)


@then("no hay facturas emitidas")
def _sin_facturas(db):
    assert db.get_facturas() == []


@then("la operación es rechazada con un aviso de dato obligatorio")
@then("la operación es rechazada con un aviso de precio inválido")
def _rechazada(context):
    assert isinstance(context.get("error"), ValueError)


@then("se mostró un aviso al usuario")
def _aviso_usuario(app):
    assert app.page.last_dialog.__class__.__name__ == "SnackBar"


@then("la app queda montada sin diálogos ni scrim colgados")
def _app_montada(app):
    assert app.page.controls          # sigue habiendo UI (no pantalla negra)
    assert app.page.dialogs == []     # no quedaron scrims/diálogos apilados


@then("la app no se rompió")
def _app_ok(app):
    assert app.page.controls


@then(parsers.re(r'el producto "(?P<nombre>[^"]*)" tiene los talles "(?P<talles>[^"]*)"'))
def _prod_talles(db, nombre, talles):
    esperados = {x.strip() for x in talles.split(",") if x.strip()}
    assert set(producto_por_nombre(db, nombre)["talles"]) == esperados


@then(parsers.parse('el producto "{nombre}" figura como universal'))
def _prod_universal(db, nombre):
    assert producto_por_nombre(db, nombre)["talles"] == []


@then(parsers.parse('el catálogo no contiene el producto "{nombre}"'))
def _catalogo_sin(db, nombre):
    assert nombre not in {p["nombre"] for p in db.get_productos()}
