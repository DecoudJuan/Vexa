"""E2E de flujo: cargar datos de AFIP desde Configuración + tutorial ARCA."""
from __future__ import annotations

import flet as ft

from views.afip import AfipView


def test_abrir_afip_desde_config(app):
    app._mostrar_afip()
    assert isinstance(app.subpage, AfipView)
    assert app.page.controls   # renderizó la subpágina


def test_cargar_datos_afip_completo(app, db):
    v = AfipView(app)
    v.build()
    v._afip_on = True
    v._tf_pv.value = "0001"
    v._tf_ib.value = "901-123456-7"
    v._tf_ia.value = "01/2020"
    v._entorno = "produccion"
    v._cert_path = r"C:\certs\vexa.crt"
    v._key_path = r"C:\certs\vexa.key"
    v._guardar()
    e = db.get_datos_empresa()
    assert e["afip_habilitado"] == 1
    assert e["punto_venta"] == "0001"
    assert e["ingresos_brutos"] == "901-123456-7"
    assert e["inicio_actividades"] == "01/2020"
    assert db.get_config("afip_entorno") == "produccion"
    assert db.get_config("afip_cert_path").endswith("vexa.crt")
    assert db.get_config("afip_key_path").endswith("vexa.key")


def test_afip_toggle_y_reapertura(app, db):
    v = AfipView(app)
    v.build()
    assert v._afip_on is False
    v._toggle(None)
    assert v._afip_on is True
    v._guardar()
    assert AfipView(app)._afip_on is True   # persiste al reabrir


def test_tutorial_arca_deslizable(app):
    v = AfipView(app)
    v.build()
    v._abrir_tutorial()
    sheet = app.page.last_dialog
    assert isinstance(sheet, ft.BottomSheet)
    assert sheet.draggable is True          # se cierra deslizando


def test_volver_desde_afip_reabre_config(app):
    app._mostrar_afip()
    app.cerrar_subpagina()                  # la flechita atrás (default reopen_config)
    assert app.subpage is None
    assert app._config_sheet is not None
