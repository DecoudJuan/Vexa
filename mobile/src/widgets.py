"""Componentes de UI compartidos entre las vistas. Cada uno recibe el dict de
tokens `t` (ver theme.tokens) para pintarse según el tema actual."""
from __future__ import annotations

import flet as ft

from theme import PAD, PADS, BALL, BEDGE


def titulo(t: dict, titulo_txt: str, sub: str) -> ft.Control:
    return ft.Column([
        ft.Text(titulo_txt, size=23, weight=ft.FontWeight.W_800, color=t["ink"]),
        ft.Text(sub, size=12, color=t["muted"]),
    ], spacing=2, tight=True)


def search(t: dict, hint: str, on_change) -> ft.Control:
    return ft.TextField(
        hint_text=hint, prefix_icon=ft.Icons.SEARCH, border_radius=13, filled=True,
        bgcolor=t["surface"], border_color=t["line2"], focused_border_color=t["accent"],
        color=t["ink"], hint_style=ft.TextStyle(color=t["faint"]),
        content_padding=PADS(10, 14), text_size=14, on_change=on_change)


def row_card(t: dict, content: ft.Control, on_click=None) -> ft.Control:
    return ft.Container(bgcolor=t["surface"], border=BALL(1, t["line"]), border_radius=14,
                        padding=12, content=content, ink=on_click is not None, on_click=on_click)


def card(t: dict, children: list) -> ft.Control:
    return ft.Container(bgcolor=t["surface"], border=BALL(1, t["line"]), border_radius=16,
                        padding=15, content=ft.Column(children, spacing=0, tight=True))


def clabel(t: dict, txt: str) -> ft.Control:
    return ft.Text(txt, size=10.5, weight=ft.FontWeight.W_800, color=t["faint"])


def empty(t: dict, txt: str) -> ft.Control:
    return ft.Container(padding=26, alignment=ft.Alignment.CENTER,
                        content=ft.Text(txt, color=t["faint"], size=12.5))


def add_button(t: dict, on_click, tooltip: str = "Nuevo") -> ft.Control:
    """Botón "+" de acento para el encabezado de una sección."""
    return ft.Container(
        width=40, height=40, border_radius=12, bgcolor=t["accent"], alignment=ft.Alignment.CENTER,
        ink=True, on_click=lambda e: on_click(), tooltip=tooltip,
        content=ft.Icon(ft.Icons.ADD, color=t["accent_ink"], size=22))
