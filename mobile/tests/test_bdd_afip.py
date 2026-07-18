"""Pasos Gherkin — Configuración de AFIP (features/afip.feature). Sin conexión en vivo."""
from __future__ import annotations

from pytest_bdd import scenarios, when, then, parsers

from views.afip import AfipView

scenarios("features/afip.feature")


@when(parsers.re(r'cargo los datos de AFIP con punto de venta "(?P<pv>[^"]*)" '
                 r'en entorno "(?P<entorno>[^"]*)"'))
def _cargo(app, context, pv, entorno):
    v = AfipView(app)
    v.build()
    v._afip_on = True
    v._tf_pv.value = pv
    v._entorno = entorno
    v._cert_path = r"C:\certs\vexa.crt"
    v._key_path = r"C:\certs\vexa.key"
    v._guardar()


@when("activo AFIP y guardo")
def _activo(app):
    v = AfipView(app)
    v.build()
    v._toggle(None)
    v._guardar()


@then("AFIP queda habilitado")
def _habilitado(db):
    assert db.get_datos_empresa()["afip_habilitado"] == 1


@then(parsers.parse('el punto de venta guardado es "{pv}"'))
def _pv(db, pv):
    assert db.get_datos_empresa()["punto_venta"] == pv


@then(parsers.parse('el entorno de AFIP guardado es "{entorno}"'))
def _entorno(db, entorno):
    assert db.get_config("afip_entorno") == entorno


@then("al reabrir la configuración de AFIP figura habilitado")
def _reabrir(app):
    assert AfipView(app)._afip_on is True
