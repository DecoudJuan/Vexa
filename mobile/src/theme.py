"""Tokens de color (claro/oscuro) y helpers de layout de Flet.

Identidad Vexa: azul de acento plano, sin degradés ni sombras. flet 0.86 no trae
`ft.padding.only` / `ft.border.all` / `ft.margin.only`, así que se usan las clases
directamente; estos wrappers dejan el código legible.
"""
from __future__ import annotations

import flet as ft


def tokens(dark: bool) -> dict:
    if not dark:
        return dict(
            ground="#eef1f6", surface="#ffffff", surface2="#f4f6fb",
            ink="#33374d", muted="#6c6f85", faint="#9aa0b4",
            line="#e2e6ef", line2="#d3d8e4",
            accent="#1e66f5", accent_ink="#ffffff", dot="#4355f5",
            ok="#2e9e4f", warn="#df8e1d", danger="#d20f39",
            v_ink="#12183a", nav_bg="#ffffff",
        )
    return dict(
        ground="#15161f", surface="#20222e", surface2="#282b39",
        ink="#e5e8f5", muted="#9aa0b8", faint="#6b7191",
        line="#31344a", line2="#3b3f58",
        accent="#5b8bff", accent_ink="#0b1020", dot="#7b8cff",
        ok="#57c777", warn="#eab24a", danger="#f2708c",
        v_ink="#e5e8f5", nav_bg="#20222e",
    )


def soft(color: str, o: float = 0.13) -> str:
    """Color con opacidad (para fondos suaves de acento/estado)."""
    return ft.Colors.with_opacity(o, color)


def PAD(left=0, top=0, right=0, bottom=0) -> ft.Padding:
    return ft.Padding(left, top, right, bottom)


def PADS(v=0, h=0) -> ft.Padding:  # symmetric(vertical, horizontal)
    return ft.Padding(h, v, h, v)


def MAR(left=0, top=0, right=0, bottom=0) -> ft.Margin:
    return ft.Margin(left, top, right, bottom)


def BALL(w, color) -> ft.Border:
    """Borde en los 4 lados."""
    bs = ft.BorderSide(w, color)
    return ft.Border(top=bs, right=bs, bottom=bs, left=bs)


def BEDGE(*, top=None, right=None, bottom=None, left=None) -> ft.Border:
    """Borde por lado; cada arg es una tupla (ancho, color) o None."""
    def s(v):
        return ft.BorderSide(v[0], v[1]) if v else None
    return ft.Border(top=s(top), right=s(right), bottom=s(bottom), left=s(left))
