"""Tests de tokens de tema, helpers de layout y el logo."""
from __future__ import annotations

import flet as ft

from theme import tokens, soft, PAD, PADS, BALL, BEDGE
from logo import v_logo

_CLAVES = ["ground", "surface", "surface2", "ink", "muted", "faint", "line", "line2",
           "accent", "accent_ink", "dot", "v_ink", "nav_bg", "ok", "warn", "danger"]


def test_tokens_claro_tiene_todas_las_claves():
    t = tokens(False)
    for k in _CLAVES:
        assert k in t, f"falta {k} en tema claro"


def test_tokens_oscuro_tiene_todas_las_claves():
    t = tokens(True)
    for k in _CLAVES:
        assert k in t, f"falta {k} en tema oscuro"


def test_tokens_claro_distinto_de_oscuro():
    assert tokens(False)["ground"] != tokens(True)["ground"]


def test_soft_devuelve_color():
    c = soft("#1e66f5", 0.12)
    assert isinstance(c, str) and c


def test_pad_y_pads():
    assert isinstance(PAD(1, 2, 3, 4), ft.Padding)
    assert isinstance(PADS(5, 10), ft.Padding)


def test_ball_y_bedge():
    assert isinstance(BALL(1, "#000"), ft.Border)
    assert isinstance(BEDGE(top=(1, "#000")), ft.Border)


def test_v_logo_construye():
    assert isinstance(v_logo(64, "#000", "#00f"), ft.Control)
