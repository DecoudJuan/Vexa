"""E2E de flujo: alta de factura — selector de cliente (con auto-crear), selector de
producto (con 'Otro' texto libre), y guardado."""
from __future__ import annotations

import flet as ft
import pytest

from views.facturas import FacturasView


def _cap_selector(app, monkeypatch):
    """Intercepta abrir_selector_full y devuelve un dict con {sel, nuevo, ops}."""
    cap = {}
    monkeypatch.setattr(app, "abrir_selector_full",
                        lambda titulo, ops, on_select, **k: cap.update(
                            sel=on_select, nuevo=k.get("on_nuevo"), ops=ops))
    return cap


def test_nueva_factura_abre_con_base_vacia(app):
    fv = FacturasView(app)
    fv.nueva()   # sin clientes ni productos, igual debe abrir el editor
    assert isinstance(app.page.last_dialog, ft.BottomSheet)


def test_cliente_autocrear_inexistente(app, db, monkeypatch):
    cap = _cap_selector(app, monkeypatch)
    fv = FacturasView(app)
    fv.nueva()
    fv._abrir_sel_cliente()
    assert len(db.get_all_clientes()) == 0
    cap["nuevo"]("Farmacia Belgrano")     # escribo uno que no existe → se crea
    assert len(db.get_all_clientes()) == 1
    assert fv._cliente_nombre() == "Farmacia Belgrano"


def test_cliente_elegir_existente(app, db, monkeypatch):
    cid = db.create_cliente({"nombre": "Cliente Uno"})
    cap = _cap_selector(app, monkeypatch)
    fv = FacturasView(app)
    fv.nueva()
    fv._abrir_sel_cliente()
    cap["sel"](cid)
    assert fv._cliente_id == cid


def test_producto_otro_texto_libre_no_crea(app, db, monkeypatch):
    cap = _cap_selector(app, monkeypatch)
    fv = FacturasView(app)
    fv.nueva()
    fv._rows = [fv._new_row()]
    fv._abrir_sel_prod(0)
    cap["nuevo"]("Rodillera especial")    # 'Otro' con nombre libre
    assert fv._rows[0]["prod"] is None
    assert fv._rows[0]["texto"] == "Rodillera especial"
    assert db.get_productos() == []       # NO creó producto


def test_producto_elegir_existente_pone_precio(app, db, monkeypatch):
    db.upsert_conceptos([{"nombre": "FAJA", "codigo": "020", "talle": "", "pvp": 9800}])
    cap = _cap_selector(app, monkeypatch)
    fv = FacturasView(app)
    fv.nueva()
    fv._rows = [fv._new_row()]
    fv._abrir_sel_prod(0)
    cap["sel"](0)
    assert fv._rows[0]["prod"] == 0
    assert fv._rows[0]["pvp"] == 9800


def test_guardar_factura_con_cliente_autocreado_y_otro(app, db, monkeypatch):
    cap = _cap_selector(app, monkeypatch)
    fv = FacturasView(app)
    fv.nueva()
    fv._abrir_sel_cliente()
    cap["nuevo"]("Farmacia X")
    fv._rows = [fv._new_row()]
    fv._abrir_sel_prod(0)
    cap["nuevo"]("Servicio especial")
    fv._rows[0]["cant_ctrl"].value = "2"
    fv._rows[0]["pvp_ctrl"].value = "1500"
    fv._guardar()
    facturas = db.get_facturas()
    assert len(facturas) == 1
    lineas = db.get_lineas(facturas[0]["id"])
    assert any(l.get("concepto_libre") == "Servicio especial" for l in lineas)


def test_precio_cero_avisa_y_no_guarda(app, db, monkeypatch):
    cap = _cap_selector(app, monkeypatch)
    fv = FacturasView(app)
    fv.nueva()
    fv._abrir_sel_cliente()
    cap["nuevo"]("Cliente Z")
    fv._rows = [fv._new_row()]
    fv._abrir_sel_prod(0)
    cap["nuevo"]("Item sin precio")     # queda con pvp 0
    fv._guardar()
    assert db.get_facturas() == []      # NO guardó
    # el aviso salió como SnackBar
    assert app.page.last_dialog.__class__.__name__ == "SnackBar"


def test_guardar_factura_cierra_y_renderiza_sin_negro(app, db, monkeypatch):
    """Reproduce el flujo de guardado: la hoja se cierra (pop → on_dismiss) y el render
    diferido corre. Verifica que _post se limpia y la app queda montada (sin quedar colgada)."""
    cap = _cap_selector(app, monkeypatch)
    fv = FacturasView(app)
    fv.nueva()
    fv._abrir_sel_cliente()
    cap["nuevo"]("Cliente Y")
    fv._rows = [fv._new_row()]
    fv._abrir_sel_prod(0)
    cap["nuevo"]("Servicio")
    fv._rows[0]["cant_ctrl"].value = "1"
    fv._rows[0]["pvp_ctrl"].value = "500"
    fv._guardar()
    assert len(db.get_facturas()) == 1
    assert fv._post is None            # el render diferido corrió (on_dismiss lo limpió)
    assert app.page.controls           # la app quedó montada (no pantalla vacía/negra)
    assert app.page.dialogs == []      # no quedaron diálogos/scrim colgados


def test_bonif_cliente_autocompleta(app, db, monkeypatch):
    cid = db.create_cliente({"nombre": "Mayorista", "bonificacion": 15})
    cap = _cap_selector(app, monkeypatch)
    fv = FacturasView(app)
    fv.nueva()
    fv._abrir_sel_cliente()
    cap["sel"](cid)                       # elegir el cliente
    assert fv._bonif == 15                # la factura tomó su bonificación


def test_selector_full_construye(app):
    picked = {}
    app.abrir_selector_full("Elegí", [("Uno", 1), ("Dos", 2)],
                            lambda v: picked.setdefault("v", v),
                            on_nuevo=lambda t: picked.setdefault("n", t))
    sheet = app.page.last_dialog
    assert isinstance(sheet, ft.BottomSheet)
    assert sheet.fullscreen is True       # ocupa toda la pestaña
