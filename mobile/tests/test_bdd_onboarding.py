"""Pasos Gherkin — Primera ejecución / onboarding (features/onboarding.feature)."""
from __future__ import annotations

from pytest_bdd import scenarios, when, then, parsers

from onboarding import Onboarding, necesita_onboarding

scenarios("features/onboarding.feature")


@when(parsers.re(r'completo el onboarding con la empresa "(?P<nombre>[^"]*)" en '
                 r'"(?P<calle>[^"]*)" "(?P<numero>[^"]*)"'))
def _completo(app, context, nombre, calle, numero):
    ob = Onboarding(app)
    ob.start()
    ob._ctrls["nombre"].value = nombre
    ob._ctrls["calle"].value = calle
    ob._ctrls["numero"].value = numero
    ob._guardar()


@when("completo el onboarding sin nombre de empresa")
def _sin_nombre(app):
    ob = Onboarding(app)
    ob.start()
    ob._guardar()


@then("la app pide completar el onboarding")
def _pide(db):
    assert necesita_onboarding(db) is True


@then("la app ya no pide el onboarding")
def _no_pide(db):
    assert necesita_onboarding(db) is False


@then(parsers.parse('la empresa guardada se llama "{nombre}"'))
def _empresa(db, nombre):
    assert db.get_datos_empresa()["nombre"] == nombre
