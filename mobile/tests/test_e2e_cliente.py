"""E2E de flujo: crear / editar / borrar / buscar clientes (nivel lógica de vista)."""
from __future__ import annotations

import flet as ft
import pytest

from views.clientes import ClientesView


def _cliente_full():
    return {
        "nombre": "Kinesio Central", "cuits": ["20-11111111-2", "27-22222222-3"],
        "condicion_iva": "Responsable Inscripto", "direccion": "San Martín 500",
        "cp": "2000", "localidad": "Rosario", "provincia": "Santa Fe",
        "telefono1": "+54 9 341 555-5555", "fax": None, "email": "a@b.com",
        "persona_contacto": "Ana", "bonificacion": 10, "banco": "Nación",
        "comentarios": "cliente de prueba",
    }


def test_crear_cliente_completo(app, db):
    v = ClientesView(app)
    v._guardar(_cliente_full(), {}, None)
    cli = db.get_all_clientes()
    assert len(cli) == 1
    c = cli[0]
    assert c["nombre"] == "Kinesio Central"
    assert c["provincia"] == "Santa Fe"
    assert c["nif"] == "20-11111111-2"       # primer CUIT
    cuits = db.get_cuits_cliente(c["id"])
    assert cuits == ["20-11111111-2", "27-22222222-3"]


def test_crear_cliente_sin_nombre_lanza(app):
    v = ClientesView(app)
    with pytest.raises(ValueError):
        v._guardar({"nombre": "  "}, {}, None)


def test_editar_cliente(app, db):
    v = ClientesView(app)
    v._guardar(_cliente_full(), {}, None)
    c = db.get_all_clientes()[0]
    d = _cliente_full()
    d["nombre"] = "Kinesio Norte"
    d["provincia"] = "Córdoba"
    v._guardar(d, db.get_cliente(c["id"]), c["id"])
    upd = db.get_cliente(c["id"])
    assert upd["nombre"] == "Kinesio Norte"
    assert upd["provincia"] == "Córdoba"
    assert len(db.get_all_clientes()) == 1        # no duplicó


def test_borrar_cliente(app, db):
    v = ClientesView(app)
    v._guardar(_cliente_full(), {}, None)
    c = db.get_all_clientes()[0]
    db.delete_cliente(c["id"])
    assert db.get_all_clientes() == []


def test_boton_nuevo_abre_form(app):
    v = ClientesView(app)
    v.build()
    v._nuevo()
    assert isinstance(app.page.last_dialog, ft.BottomSheet)   # el "+" abre el form


def test_lista_muestra_y_busca(app, db):
    v = ClientesView(app)
    v._guardar(_cliente_full(), {}, None)
    d2 = _cliente_full()
    d2["nombre"] = "Ortopedia Sur"
    d2["cuits"] = []
    v._guardar(d2, {}, None)
    v.build()
    v._fill()
    assert len(v.lista.controls) == 2
    v._fill("kinesio")
    assert len(v.lista.controls) == 1
