"""Pasos Gherkin — Facturación (features/facturas.feature).

Los selectores de cliente/producto se interceptan (como en los e2e existentes)
capturando los callbacks de `abrir_selector_full`, para dirigir el flujo sin UI real."""
from __future__ import annotations

from datetime import date

from pytest_bdd import scenarios, given, when, then, parsers

from views.facturas import FacturasView

scenarios("features/facturas.feature")


def _cap(app, monkeypatch):
    cap = {}
    monkeypatch.setattr(app, "abrir_selector_full",
                        lambda titulo, ops, on_select, **k: cap.update(
                            sel=on_select, nuevo=k.get("on_nuevo"), ops=ops))
    return cap


@given(parsers.parse('un cliente llamado "{nombre}" en "{loc}" con bonificación {bonif:d}'))
def _cliente_bonif(db, context, nombre, loc, bonif):
    cid = db.create_cliente({"nombre": nombre, "localidad": loc, "bonificacion": bonif})
    context.update(cliente_id=cid, cliente_nombre=nombre)


@when(parsers.parse('armo una factura para "{nombre}" con {cant:d} unidades del producto existente'))
def _factura_existentes(app, context, monkeypatch, nombre, cant):
    cap = _cap(app, monkeypatch)
    fv = FacturasView(app)
    fv.nueva()
    fv._abrir_sel_cliente()
    cap["sel"](context["cliente_id"])
    fv._rows = [fv._new_row()]
    fv._abrir_sel_prod(0)
    cap["sel"](0)                                   # primer producto del catálogo
    fv._rows[0]["cant_ctrl"].value = str(cant)
    context["fv"] = fv


@when(parsers.re(r'armo una factura para el cliente nuevo "(?P<nombre>[^"]*)" con un ítem '
                 r'libre "(?P<texto>[^"]*)" a (?P<precio>\d+) por (?P<cant>\d+) unidades'))
def _factura_nuevo_libre(app, context, monkeypatch, nombre, texto, precio, cant):
    cap = _cap(app, monkeypatch)
    fv = FacturasView(app)
    fv.nueva()
    fv._abrir_sel_cliente()
    cap["nuevo"](nombre)                            # autocrea el cliente
    fv._rows = [fv._new_row()]
    fv._abrir_sel_prod(0)
    cap["nuevo"](texto)                             # 'Otro' ítem de texto libre
    fv._rows[0]["cant_ctrl"].value = str(cant)
    fv._rows[0]["pvp_ctrl"].value = str(precio)
    context["fv"] = fv


@when(parsers.parse('elijo a "{nombre}" como cliente de una factura nueva'))
def _elijo_cliente(app, context, monkeypatch, nombre):
    cap = _cap(app, monkeypatch)
    fv = FacturasView(app)
    fv.nueva()
    fv._abrir_sel_cliente()
    cap["sel"](context["cliente_id"])
    context["fv"] = fv


@when("guardo la factura")
def _guardo(context):
    context["fv"]._guardar()


@when(parsers.parse('emito {n:d} facturas al cliente "{nombre}"'))
def _emito_varias(db, context, n, nombre):
    ej = date.today().year
    prod = db.get_productos()[0]
    for _ in range(n):
        num = db.siguiente_numero("FA", ej)
        lineas = [{"concepto_libre": prod["nombre"], "cantidad": 1, "pvp": prod["pvp"]}]
        db.create_factura({"cliente_id": context["cliente_id"], "tipo": "FA", "ejercicio": ej,
                           "numero": num, "fecha": date.today().isoformat(),
                           "total": prod["pvp"]}, lineas)


@then(parsers.parse('el total de la factura es {total:d}'))
def _total(db, total):
    assert db.get_facturas()[0]["total"] == total


@then(parsers.parse('la factura incluye el ítem libre "{texto}"'))
def _incluye_libre(db, texto):
    fid = db.get_facturas()[0]["id"]
    assert any(l.get("concepto_libre") == texto for l in db.get_lineas(fid))


@then(parsers.parse('la factura aplica una bonificación de {bonif:d}'))
def _bonif(context, bonif):
    assert context["fv"]._bonif == bonif


@then("los números de factura son correlativos sin huecos")
def _correlativos(db):
    nums = sorted(int(f["numero"]) for f in db.get_facturas())
    assert nums == list(range(nums[0], nums[0] + len(nums)))
