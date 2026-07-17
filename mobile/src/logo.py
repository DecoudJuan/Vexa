"""Marca Vexa dibujada en canvas (se adapta al tema)."""
from __future__ import annotations

import flet as ft
import flet.canvas as cv


def v_logo(size: float, ink: str, dot: str) -> ft.Control:
    """La V (trazo) + el punto de acento, escalada a `size` px."""
    s = size / 64.0
    trazo = ft.Paint(style=ft.PaintingStyle.STROKE, stroke_width=9 * s,
                     stroke_cap=ft.StrokeCap.ROUND, stroke_join=ft.StrokeJoin.ROUND, color=ink)
    relleno = ft.Paint(style=ft.PaintingStyle.FILL, color=dot)
    return ft.Container(
        width=size, height=size,
        content=cv.Canvas(width=size, height=size, shapes=[
            cv.Path([cv.Path.MoveTo(14 * s, 17 * s), cv.Path.LineTo(30 * s, 47 * s),
                     cv.Path.LineTo(46 * s, 21 * s)], paint=trazo),
            cv.Circle(48 * s, 18 * s, 7 * s, paint=relleno),
        ]),
    )
