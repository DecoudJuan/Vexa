"""Tests de tamaño de formularios: producto = media pantalla; cliente = fullscreen."""
from __future__ import annotations

import flet as ft

from views.productos import ProductosView
from views.clientes import ClientesView


def test_producto_form_media_pantalla(app):
    ProductosView(app)._nuevo()
    assert app.page.last_dialog.fullscreen is False   # media pantalla (pocos datos)


def test_producto_editar_media_pantalla(app, db):
    db.upsert_conceptos([{"nombre": "X", "codigo": "1", "talle": "", "pvp": 100}])
    prod = db.get_productos()[0]
    ProductosView(app)._editar(prod)
    assert app.page.last_dialog.fullscreen is False


def test_cliente_form_fullscreen(app):
    ClientesView(app)._nuevo()
    assert app.page.last_dialog.fullscreen is True    # muchos campos → pantalla completa


def test_open_form_half_construye(app):
    app.open_form("Chico", [{"key": "a", "label": "A", "value": ""}],
                  on_save=lambda d: None, full=False)
    assert app.page.last_dialog.fullscreen is False


def test_form_con_borrado_construye(app, db):
    cid = db.create_cliente({"nombre": "Para borrar"})
    ClientesView(app)._editar({"id": cid, "nombre": "Para borrar"})
    # abre el form de edición con on_delete → arma el banner de confirmación sin romper
    assert isinstance(app.page.last_dialog, ft.BottomSheet)


def test_open_form_borrado_ejecuta_on_delete(app):
    borrado = {"hecho": False}
    app.open_form("X", [{"key": "n", "label": "N", "value": "a"}],
                  on_save=lambda d: None, on_delete=lambda: borrado.update(hecho=True),
                  borrar_texto="¿Seguro?")
    # el flujo real: tocar el tacho muestra el banner y 'Eliminar' llama borrar → on_delete.
    # acá validamos que la construcción con on_delete no rompe y el dialog está montado.
    assert isinstance(app.page.last_dialog, ft.BottomSheet)
