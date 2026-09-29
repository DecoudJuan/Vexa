"""Reglas de la factura del core (`vexa_core.utils.facturas`), compartidas por
desktop y mobile: totales con bonificación, líneas "a favor" y precio en 0."""
from __future__ import annotations

import pytest

from vexa_core.utils.facturas import calcular_totales, es_a_favor, lineas_con_precio_cero


def test_totales_sin_bonificacion():
    t = calcular_totales([{"cantidad": 2, "pvp": 100}, {"cantidad": 1, "pvp": 50}])
    assert t == {"subtotal": 250, "bonificacion": 0.0, "total": 250}


def test_totales_con_bonificacion():
    t = calcular_totales([{"cantidad": 4, "pvp": 250}], 10)
    assert t["subtotal"] == 1000
    assert t["bonificacion"] == pytest.approx(100)
    assert t["total"] == pytest.approx(900)


def test_linea_a_favor_resta_del_total():
    lineas = [{"cantidad": 1, "pvp": 1000}, {"cantidad": 1, "pvp": -200}]
    assert calcular_totales(lineas)["total"] == 800
    assert es_a_favor(-200) and not es_a_favor(200) and not es_a_favor(0)


def test_bonificacion_negativa_o_vacia_no_bonifica():
    lineas = [{"cantidad": 1, "pvp": 100}]
    assert calcular_totales(lineas, -5)["total"] == 100
    assert calcular_totales(lineas, None)["total"] == 100


def test_valores_vacios_cuentan_como_cero():
    assert calcular_totales([{"cantidad": None, "pvp": "abc"}])["total"] == 0


def test_precio_cero_se_detecta_pero_negativo_no():
    lineas = [{"cantidad": 1, "pvp": 100}, {"cantidad": 1, "pvp": 0},
              {"cantidad": 1, "pvp": -50}, {"cantidad": 2, "pvp": None}]
    assert lineas_con_precio_cero(lineas) == [1, 3]
