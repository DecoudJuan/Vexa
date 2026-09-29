"""Reglas de la factura compartidas por desktop y mobile (sin UI).

- Total = subtotal − bonificación %. El subtotal es la suma de cantidad × precio
  de cada línea; una línea con precio NEGATIVO es un crédito "a favor" (resta del
  total: devoluciones, descuentos por unidad, etc.).
- Una línea con precio 0 no se guarda: casi siempre es un precio sin cargar.
  El negativo sí es válido (es la línea "a favor").
"""
from __future__ import annotations


def _num(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def es_a_favor(pvp) -> bool:
    """True si la línea es un crédito "a favor" (precio negativo)."""
    return _num(pvp) < 0


def calcular_totales(lineas, bonificacion_pct=0) -> dict:
    """Totales de una factura. `lineas` = iterable de dicts con `cantidad` y `pvp`.
    Devuelve {subtotal, bonificacion (monto), total}. Un % <= 0 no bonifica."""
    subtotal = sum(_num(ln.get("cantidad")) * _num(ln.get("pvp")) for ln in lineas)
    pct = _num(bonificacion_pct)
    bonif = subtotal * (pct / 100.0) if pct > 0 else 0.0
    return {"subtotal": subtotal, "bonificacion": bonif, "total": subtotal - bonif}


def lineas_con_precio_cero(lineas) -> list[int]:
    """Índices de las líneas con precio 0 (precio sin cargar). Los negativos no
    cuentan: son líneas "a favor" válidas."""
    return [i for i, ln in enumerate(lineas) if _num(ln.get("pvp")) == 0]
