"""Tests de la página AFIP (datos fiscales + entorno/cert/clave + tutorial)."""
from __future__ import annotations

import flet as ft

from views.afip import AfipView


def test_build_ok(app):
    assert isinstance(AfipView(app).build(), ft.Column)


def test_entorno_default_homologacion(app):
    assert AfipView(app)._entorno == "homologacion"


def test_toggle_flip(app):
    v = AfipView(app)
    v.build()
    assert v._afip_on is False
    v._toggle(None)
    assert v._afip_on is True


def test_guardar_persiste_empresa(app, db):
    v = AfipView(app)
    v.build()
    v._afip_on = True
    v._tf_pv.value = "0001"
    v._tf_ib.value = "901-123456-7"
    v._tf_ia.value = "01/2020"
    v._guardar()
    e = db.get_datos_empresa()
    assert e["afip_habilitado"] == 1
    assert e["punto_venta"] == "0001"
    assert e["ingresos_brutos"] == "901-123456-7"
    assert e["inicio_actividades"] == "01/2020"


def test_guardar_persiste_config(app, db):
    v = AfipView(app)
    v.build()
    v._entorno = "produccion"
    v._cert_path = r"C:\certs\vexa.crt"
    v._key_path = r"C:\certs\vexa.key"
    v._guardar()
    assert db.get_config("afip_entorno") == "produccion"
    assert db.get_config("afip_cert_path") == r"C:\certs\vexa.crt"
    assert db.get_config("afip_key_path") == r"C:\certs\vexa.key"


def test_reabrir_refleja_guardado(app, db):
    v = AfipView(app)
    v.build()
    v._afip_on = True
    v._entorno = "produccion"
    v._guardar()
    v2 = AfipView(app)
    assert v2._afip_on is True
    assert v2._entorno == "produccion"


def test_tutorial_abre_bottomsheet(app):
    v = AfipView(app)
    v.build()
    v._abrir_tutorial()
    assert isinstance(app.page.last_dialog, ft.BottomSheet)


def test_nombre_archivo(app):
    v = AfipView(app)
    assert v._nombre("") == "Ningún archivo elegido"
    assert v._nombre(r"C:\x\y\vexa.crt") == "vexa.crt"
