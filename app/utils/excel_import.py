"""Importador de listas de precios en Excel: busca en cada hoja una tabla con
columnas 'ARTICULOS' / 'PRECIO' (saltando filas de membrete).

Soporta .xlsx / .xlsm (vía openpyxl). El formato binario legacy .xls no está
soportado. (La Fase 2 del roadmap lo reemplaza por un importador con mapeo de
columnas configurable.)
"""

import openpyxl

from utils.helpers import separar_codigo


def leer_lista_precios(path: str) -> list[dict]:
    """Devuelve una lista de {"nombre": str, "pvp": float} leída de cualquier
    hoja del archivo que tenga columnas 'ARTICULOS' y 'PRECIO'. Busca el
    encabezado automáticamente entre las primeras filas de cada hoja, ya que
    las planillas tienen unas filas de membrete (empresa, título, dirección)
    antes de la tabla de precios."""
    wb = openpyxl.load_workbook(path, data_only=True)
    items: list[dict] = []

    for ws in wb.worksheets:
        col_nombre = col_precio = header_row = None
        max_scan = min(ws.max_row or 0, 40)
        for r in range(1, max_scan + 1):
            for c in range(1, (ws.max_column or 0) + 1):
                val = ws.cell(row=r, column=c).value
                if not isinstance(val, str):
                    continue
                texto = val.strip().upper()
                if texto.startswith("ARTICULO"):
                    col_nombre, header_row = c, r
                elif texto.startswith("PRECIO"):
                    col_precio = c
            if header_row and col_precio:
                break

        if not header_row or not col_nombre or not col_precio:
            continue

        for r in range(header_row + 1, (ws.max_row or header_row) + 1):
            nombre = ws.cell(row=r, column=col_nombre).value
            precio = ws.cell(row=r, column=col_precio).value
            if not isinstance(nombre, str):
                continue
            nombre = nombre.strip()
            if not nombre or nombre.startswith("*") or "CONSULTAR" in nombre.upper():
                continue
            if not isinstance(precio, (int, float)):
                continue
            limpio, codigo = separar_codigo(nombre)
            items.append({"nombre": limpio or nombre, "codigo": codigo, "pvp": float(precio)})

    return items
