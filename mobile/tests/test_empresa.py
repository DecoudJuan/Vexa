"""Tests del form de empresa unificado (campos = desktop, guardado, sin AFIP)."""
from __future__ import annotations

import pytest

_ESPERADOS = ["nombre", "nif", "condicion_iva", "calle", "numero", "localidad",
              "provincia", "telefono", "email", "moneda"]


def _keys(campos):
    return [c["key"] for it in campos for c in (it if isinstance(it, list) else [it])]


def test_campos_iguales_a_desktop_sin_afip(app, db):
    keys = _keys(app.empresa_campos(db.get_datos_empresa()))
    assert keys == _ESPERADOS
    assert "afip_habilitado" not in keys
    assert "punto_venta" not in keys


def test_campos_parten_direccion(app, db):
    e = db.get_datos_empresa()
    e["direccion"] = "Av. Corrientes 1234"
    db.update_datos_empresa(e)
    campos = {c["key"]: c for it in app.empresa_campos(db.get_datos_empresa())
              for c in (it if isinstance(it, list) else [it])}
    assert campos["calle"]["value"] == "Av. Corrientes"
    assert campos["numero"]["value"] == "1234"


def test_guardar_une_direccion(app, db):
    app.guardar_empresa({"nombre": "X", "calle": "9 de Julio", "numero": "10"})
    assert db.get_datos_empresa()["direccion"] == "9 de Julio 10"


def test_guardar_sin_numero(app, db):
    app.guardar_empresa({"nombre": "X", "calle": "Ruta 8", "numero": ""})
    assert db.get_datos_empresa()["direccion"] == "Ruta 8"


def test_guardar_nombre_vacio_lanza(app):
    with pytest.raises(ValueError):
        app.guardar_empresa({"nombre": "   "})


def test_guardar_no_pisa_flag_afip(app, db):
    e = db.get_datos_empresa()
    e["afip_habilitado"] = 1
    db.update_datos_empresa(e)
    app.guardar_empresa({"nombre": "X SRL", "moneda": "$"})
    assert db.get_datos_empresa()["afip_habilitado"] == 1


def test_guardar_moneda(app, db):
    app.guardar_empresa({"nombre": "X", "moneda": "US$"})
    assert db.get_datos_empresa()["moneda"] == "US$"


def test_empresa_form_no_crashea(app):
    # abre el form genérico (construye todos los tipos de campo)
    app._abrir_empresa_form()
    assert app.page.last_dialog is not None
