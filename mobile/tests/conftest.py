"""Fixtures para los tests de la app mobile (headless, sin ventana Flet).

`FACTURACION_DATA_DIR` se setea ANTES de importar vexa_core (el módulo db congela
DATA_DIR al importarse). Cada test usa su propia base sqlite (db_path por tmp_path)
para quedar aislado. `page` es un doble de ft.Page con lo mínimo que usa la app.
"""
from __future__ import annotations

import os
import sys
import tempfile
import pathlib

# --- rutas y entorno ANTES de importar vexa_core / la app ---
_SRC = pathlib.Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(_SRC))
os.environ.setdefault("FACTURACION_DATA_DIR", tempfile.mkdtemp(prefix="vexa_tests_"))
os.environ.pop("FLET_APP_STORAGE_DATA", None)

import flet as ft  # noqa: E402
import pytest  # noqa: E402

from vexa_core.database.db import DatabaseManager  # noqa: E402


class FakePage:
    """Doble mínimo de ft.Page: registra controles/diálogos, no dibuja nada."""

    def __init__(self):
        self.platform_brightness = ft.Brightness.LIGHT
        self.height = 1400
        self.width = 1080
        self.controls = []
        self.overlay = []
        self.theme_mode = None
        self.bgcolor = None
        self.services = []
        self.dialogs = []
        self.last_dialog = None
        self.opened_url = None

    def update(self):
        pass

    def run_task(self, *_a, **_k):
        pass

    def show_dialog(self, d):
        self.last_dialog = d
        # Los SnackBar no son diálogos modales apilables (no los cierra pop_dialog).
        if d.__class__.__name__ != "SnackBar":
            self.dialogs.append(d)

    def pop_dialog(self):
        # Como el Flet real: al cerrar dispara on_dismiss (donde se difiere el render).
        if self.dialogs:
            d = self.dialogs.pop()
            h = getattr(d, "on_dismiss", None)
            if h:
                try:
                    h(None)
                except TypeError:
                    h()

    def launch_url(self, url):
        self.opened_url = url


@pytest.fixture
def db(tmp_path):
    m = DatabaseManager(db_path=str(tmp_path / "t.db"))
    m.init_db()
    yield m
    m.engine.dispose()


@pytest.fixture
def page():
    return FakePage()


@pytest.fixture
def app(db, page):
    from app import VexaApp
    return VexaApp(page, db)
