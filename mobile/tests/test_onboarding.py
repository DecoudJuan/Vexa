"""Tests del onboarding de primera ejecución (gate + slide + guardado)."""
from __future__ import annotations

import pytest

from onboarding import Onboarding, necesita_onboarding


def test_gate_base_vacia(db):
    assert necesita_onboarding(db) is True


def test_gate_con_empresa(db):
    e = db.get_datos_empresa()
    e["nombre"] = "Algo SRL"
    db.update_datos_empresa(e)
    assert necesita_onboarding(db) is False


def test_gate_con_flag(db):
    db.set_config("onboarding_done", "1")
    assert necesita_onboarding(db) is False


def test_start_arma_dos_capas(app):
    ob = Onboarding(app)
    ob.start()
    # welcome visible (offset 0), form fuera a la derecha (offset x=1)
    assert ob._welcome.offset.x == 0
    assert ob._form.offset.x == 1
    assert app.page.controls, "no montó controles"


def test_ir_a_form_desliza(app):
    ob = Onboarding(app)
    ob.start()
    ob._ir_a_form()
    assert ob._welcome.offset.x == -1  # sale por la izquierda
    assert ob._form.offset.x == 0      # entra el form


def test_volver_bienvenida(app):
    ob = Onboarding(app)
    ob.start()
    ob._ir_a_form()
    ob._volver_bienvenida()
    assert ob._welcome.offset.x == 0
    assert ob._form.offset.x == 1


def test_guardar_persiste_y_cierra_gate(app, db):
    ob = Onboarding(app)
    ob.start()
    ob._ctrls["nombre"].value = "Kinesio SRL"
    ob._ctrls["calle"].value = "San Martín"
    ob._ctrls["numero"].value = "500"
    ob._guardar()
    e = db.get_datos_empresa()
    assert e["nombre"] == "Kinesio SRL"
    assert e["direccion"] == "San Martín 500"
    assert necesita_onboarding(db) is False


def test_guardar_nombre_vacio_no_rompe(app, db):
    ob = Onboarding(app)
    ob.start()
    ob._guardar()  # sin nombre
    assert necesita_onboarding(db) is True          # sigue pendiente
    assert app.page.controls                          # no crasheó


def test_moneda_default_peso(app):
    ob = Onboarding(app)
    ob.start()
    data = ob._collect()
    assert data["moneda"] == "$"


def test_condicion_default_vacia(app):
    ob = Onboarding(app)
    ob.start()
    data = ob._collect()
    assert data["condicion_iva"] in ("", None)
