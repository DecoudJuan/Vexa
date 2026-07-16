"""Generador de etiquetas de productos (hoja A4, 14 por hoja).

Núcleo compartido y **agnóstico de plataforma** (no importa PySide ni nada de
`desktop/`): tanto la app de escritorio como el futuro cliente mobile (Flet)
arman una cola de items y llaman a `generar_pdf_etiquetas()`. El catálogo son
los productos de la lista de precios de Vexa (`db.get_productos()`); acá sólo se
recibe la cola ya armada.

Formato adaptado del generador de AdherNeo (`adherneo/etiquetas.html`): grilla
2×7, bordes redondeados, texto Times bold centrado y tamaño de fuente dinámico
según el largo del texto.
"""

from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from vexa_core.utils.helpers import nombre_sin_talle

# Layout de la hoja (idéntico al de AdherNeo).
PERPAGE = 14
COLS, ROWS = 2, 7
_MARGIN = 10 * mm
_GAP_X = 5 * mm
_GAP_Y = 2 * mm
_RADIUS = 4 * mm
_PAD = 3 * mm  # margen interno de la etiqueta (para que el texto no toque el borde)
_FONT = "Times-Bold"
_MAX_FS = 23  # pt
_MIN_FS = 8


def etiqueta_lineas(codigo: str | None, nombre: str | None,
                    talle: str | None) -> list[str]:
    """Las líneas de texto de una etiqueta a partir de un producto.

    - Con talle: ["<código>. <nombre>", "T: <talle>"].
    - Sin talle (universal): ["<código>. <nombre>"].
    Si no hay código se omite el prefijo. El nombre se limpia del código/talle
    que la migración de Access dejó pegado (`nombre_sin_talle`)."""
    nom = nombre_sin_talle(nombre) or (nombre or "").strip()
    cod = (codigo or "").strip()
    cabecera = f"{cod}. {nom}" if cod else nom
    lineas = [cabecera]
    t = (talle or "").strip()
    if t:
        lineas.append(f"T: {t}")
    return lineas


def resumen_cola(total_etiquetas: int) -> dict:
    """Resumen de paginado de la cola: cuántas hojas ocupa y cuántas etiquetas
    faltan para completar la última (para avisar antes de imprimir)."""
    total = max(0, int(total_etiquetas or 0))
    completas = total // PERPAGE
    ultima = total % PERPAGE
    paginas = completas + (1 if ultima else 0)
    faltan = (PERPAGE - ultima) if ultima else 0
    return {
        "total": total,
        "paginas": paginas,
        "ultima": ultima or (PERPAGE if total else 0),
        "faltan": faltan,
    }


def expandir_cola(items: list[dict]) -> list[list[str]]:
    """Aplana la cola en una lista de etiquetas (una por unidad). Cada item es
    {codigo, nombre, talle, cantidad}."""
    labels: list[list[str]] = []
    for it in items:
        lineas = etiqueta_lineas(it.get("codigo"), it.get("nombre"), it.get("talle"))
        cant = max(1, int(it.get("cantidad") or 1))
        labels.extend([lineas] * cant)
    return labels


def _wrap(c, texto: str, max_w: float, size: float) -> list[str]:
    """Parte `texto` en varias líneas para que cada una entre en `max_w` a ese
    tamaño de fuente (corta por palabras)."""
    palabras = texto.split()
    lineas: list[str] = []
    actual = ""
    for p in palabras:
        prueba = f"{actual} {p}".strip()
        if not actual or c.stringWidth(prueba, _FONT, size) <= max_w:
            actual = prueba
        else:
            lineas.append(actual)
            actual = p
    if actual:
        lineas.append(actual)
    return lineas or [texto]


def _ajustar(c, lineas: list[str], max_w: float, max_h: float):
    """Elige el mayor tamaño de fuente con el que el nombre (envuelto en varias
    líneas si hace falta) + el talle entran en la caja, sin salirse ni a lo
    ancho ni a lo alto. Devuelve (tamaño, lista_de_líneas_finales)."""
    cabecera = lineas[0]
    extra = lineas[1:]  # p.ej. "T: 1"
    for size in range(_MAX_FS, _MIN_FS - 1, -1):
        envuelto = _wrap(c, cabecera, max_w, size)
        todas = envuelto + extra
        if any(c.stringWidth(l, _FONT, size) > max_w for l in todas):
            continue
        if size * 1.22 * len(todas) <= max_h:
            return size, todas
    envuelto = _wrap(c, cabecera, max_w, _MIN_FS)
    return _MIN_FS, envuelto + extra


def _dibujar_celda(c, x: float, y: float, w: float, h: float,
                   lineas: list[str] | None) -> None:
    if not lineas:
        # Celda vacía de la última hoja: borde tenue punteado.
        c.saveState()
        c.setDash(2, 3)
        c.setStrokeColorRGB(0.8, 0.8, 0.8)
        c.roundRect(x, y, w, h, _RADIUS, stroke=1, fill=0)
        c.restoreState()
        return

    c.setStrokeColorRGB(0.1, 0.1, 0.1)
    c.setLineWidth(1.3)
    c.roundRect(x, y, w, h, _RADIUS, stroke=1, fill=0)

    size, todas = _ajustar(c, lineas, w - 2 * _PAD, h - 2 * _PAD)
    leading = size * 1.22
    cx = x + w / 2
    total_alto = leading * len(todas)
    # Baseline de la primera línea (bloque centrado verticalmente).
    top_baseline = y + h / 2 + total_alto / 2 - leading + size * 0.28
    c.setFont(_FONT, size)
    c.setFillColorRGB(0, 0, 0)
    for i, linea in enumerate(todas):
        c.drawCentredString(cx, top_baseline - i * leading, linea)


def generar_pdf_etiquetas(items: list[dict], carpeta: str | Path,
                          nombre_archivo: str | None = None) -> str:
    """Genera la hoja/s A4 de etiquetas y devuelve la ruta del PDF.

    `items`: cola ya armada, cada uno {codigo, nombre, talle, cantidad}.
    `carpeta`: dónde guardar (la UI pasa la carpeta de PDFs configurada)."""
    labels = expandir_cola(items)
    if not labels:
        raise ValueError("La cola de etiquetas está vacía.")

    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    if not nombre_archivo:
        nombre_archivo = f"etiquetas_{datetime.now():%Y%m%d_%H%M%S}.pdf"
    ruta = carpeta / nombre_archivo

    page_w, page_h = A4
    cell_w = (page_w - 2 * _MARGIN - _GAP_X) / COLS
    cell_h = (page_h - 2 * _MARGIN - (ROWS - 1) * _GAP_Y) / ROWS
    top = page_h - _MARGIN  # borde superior del área útil

    c = canvas.Canvas(str(ruta), pagesize=A4)
    for i in range(0, len(labels), PERPAGE):
        pagina = labels[i:i + PERPAGE]
        pagina += [None] * (PERPAGE - len(pagina))
        for idx, lineas in enumerate(pagina):
            col = idx % COLS
            fila = idx // COLS
            x = _MARGIN + col * (cell_w + _GAP_X)
            y = top - (fila + 1) * cell_h - fila * _GAP_Y
            _dibujar_celda(c, x, y, cell_w, cell_h, lineas)
        c.showPage()
    c.save()
    return str(ruta)
