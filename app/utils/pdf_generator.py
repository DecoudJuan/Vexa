import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF

from database.db import DATA_DIR
from utils.helpers import (
    fmt_ar, fmt_fecha, nombre_sin_talle, valor_valido, texto_valido,
    etiqueta_concepto, letra_comprobante,
)

PDF_DIR_DEFECTO = DATA_DIR / "pdf"


def obtener_carpeta_pdf(db) -> Path:
    """Carpeta donde se guardan los PDF generados. Por defecto vive junto a
    la base de datos, pero el usuario puede cambiarla (ej. a Descargas)
    desde Configuración > Mi empresa."""
    personalizada = db.get_config("pdf_dir")
    return Path(personalizada) if personalizada else PDF_DIR_DEFECTO


_TITULOS = {
    "FA": "FACTURA", "PR": "PRESUPUESTO", "AL": "ALBARÁN",
    "PE": "PEDIDO", "AB": "ABONO",
}

_styles = getSampleStyleSheet()
_style_normal = _styles["Normal"]
_style_small = ParagraphStyle("small", parent=_style_normal, fontSize=8, leading=10)
_style_titulo = ParagraphStyle("titulo", parent=_styles["Title"], alignment=TA_RIGHT, fontSize=20)
_style_right = ParagraphStyle("right", parent=_style_normal, alignment=TA_RIGHT)


def _slug(texto: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", texto or "doc")


def generar_pdf_documento(db, factura_id: int) -> str:
    doc = db.get_factura(factura_id)
    if not doc:
        raise ValueError(f"Documento {factura_id} no encontrado")
    cliente = db.get_cliente(doc["cliente_id"]) or {}
    lineas = db.get_lineas(factura_id)
    suplidos = db.get_suplidos(factura_id)
    empresa = db.get_datos_empresa()

    tipo = doc["tipo"]
    titulo = _TITULOS.get(tipo, tipo)
    numero_doc = f"{tipo}-{doc.get('ejercicio')}-{doc.get('numero') or ''}"

    # Letra del comprobante según condición IVA de emisor y receptor.
    letra = letra_comprobante(empresa.get("condicion_iva"), cliente.get("condicion_iva"))
    # Numeración modelo AR (Punto de venta - Nº) si hay punto de venta cargado.
    pv = (empresa.get("punto_venta") or "").strip()
    num = (doc.get("numero") or "").strip()
    numero_fmt = f"{pv.zfill(4)}-{num.zfill(8)}" if pv else numero_doc
    # Sin CAE de AFIP todavía (Fase 4) → todos los comprobantes son no fiscales.
    no_valido = not doc.get("cae")

    carpeta = obtener_carpeta_pdf(db)
    carpeta.mkdir(parents=True, exist_ok=True)
    out_path = carpeta / f"{_slug(numero_doc)}.pdf"

    pdf_doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        topMargin=64 * mm, bottomMargin=20 * mm,
        leftMargin=18 * mm, rightMargin=18 * mm,
    )

    def _on_page(canvas, _doc):
        canvas.saveState()
        _dibujar_encabezado(canvas, empresa, cliente, titulo, numero_fmt, letra, doc, no_valido)
        if not no_valido:
            _dibujar_pie_fiscal(canvas, doc)
        canvas.restoreState()

    story = []
    story.append(Spacer(1, 4 * mm))
    story.append(_tabla_lineas(lineas))
    story.append(Spacer(1, 6 * mm))
    story.append(_tabla_totales(doc, lineas, suplidos, tipo, empresa, letra))

    if doc.get("comentarios"):
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph(f"<b>Comentarios:</b> {doc['comentarios']}", _style_small))

    pdf_doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return str(out_path)


def _dibujar_encabezado(canvas, empresa, cliente, titulo, numero_fmt, letra, doc, no_valido):
    """Encabezado con el layout de comprobante argentino: marco con recuadro de
    letra (A/B/C/X) centrado arriba, emisor a la izquierda y datos del
    comprobante a la derecha; bajo una línea separadora, el receptor. Cada
    columna fluye con un cursor de `y` para que las líneas nunca se pisen. Si
    aún no es fiscal, leyenda 'no válido' bajo el marco."""
    width, height = A4
    left = 18 * mm
    right = width - 18 * mm
    top = height - 12 * mm
    box_bottom = height - 54 * mm
    mid_x = width / 2
    band_split = top - 26 * mm      # separa emisor/comprobante (arriba) del receptor (abajo)
    xL = left + 2 * mm

    canvas.setStrokeColor(colors.HexColor("#333333"))
    canvas.setLineWidth(0.8)
    canvas.rect(left, box_bottom, right - left, top - box_bottom)
    canvas.line(left, band_split, right, band_split)   # separador horizontal

    # --- Recuadro de la letra (centrado arriba, contenido dentro del marco) ---
    lb = 13 * mm
    lb_top = top - 1.5 * mm
    # Divisor vertical de la banda superior: sube hasta el pie del recuadro para
    # no sobresalir por encima de él.
    canvas.line(mid_x, band_split, mid_x, lb_top - lb)
    canvas.setFillColor(colors.white)
    canvas.rect(mid_x - lb / 2, lb_top - lb, lb, lb, stroke=1, fill=1)
    canvas.setFillColor(colors.black)
    canvas.setFont("Helvetica-Bold", 20)
    canvas.drawCentredString(mid_x, lb_top - lb + 4.3 * mm, letra or "X")
    canvas.setFont("Helvetica", 5)
    canvas.drawCentredString(mid_x, lb_top - lb + 1 * mm, "COMPROBANTE")

    # --- Emisor (izquierda) --- (los comprobantes NO llevan logo)
    canvas.setFont("Helvetica-Bold", 13)
    canvas.drawString(xL, top - 6.5 * mm, empresa.get("nombre") or "")
    fiscal = []
    if empresa.get("condicion_iva"):
        fiscal.append(f"IVA: {empresa['condicion_iva']}")
    if empresa.get("ingresos_brutos"):
        fiscal.append(f"IIBB: {empresa['ingresos_brutos']}")
    if empresa.get("inicio_actividades"):
        fiscal.append(f"Inicio: {empresa['inicio_actividades']}")
    canvas.setFont("Helvetica", 8)
    y = top - 11.5 * mm
    for linea in (
        empresa.get("direccion") or "",
        f"{valor_valido(empresa.get('cp')) or ''} {empresa.get('localidad') or ''} "
        f"{empresa.get('provincia') or ''}".strip(),
        f"Tel: {empresa.get('telefono')}" if empresa.get("telefono") else "",
        "   ".join(fiscal),
    ):
        if linea:
            canvas.drawString(xL, y, linea)
            y -= 3.8 * mm

    # --- Comprobante (derecha) ---
    rx = mid_x + 10 * mm
    canvas.setFont("Helvetica-Bold", 15)
    canvas.drawString(rx, top - 6.5 * mm, titulo)
    canvas.setFont("Helvetica", 9)
    canvas.drawString(rx, top - 13 * mm, f"Comp. Nº: {numero_fmt}")
    canvas.drawString(rx, top - 18 * mm, f"Fecha: {fmt_fecha(doc.get('fecha'))}")
    canvas.drawString(rx, top - 23 * mm, f"CUIT: {valor_valido(empresa.get('nif')) or '—'}")

    # --- Receptor (debajo del separador) ---
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(xL, band_split - 6 * mm, "Cliente:")
    canvas.setFont("Helvetica", 9)
    canvas.drawString(xL + 18 * mm, band_split - 6 * mm, cliente.get("nombre") or "")
    rec = []
    if valor_valido(cliente.get("nif")):
        rec.append(f"CUIT: {cliente['nif']}")
    if cliente.get("condicion_iva"):
        rec.append(f"IVA: {cliente['condicion_iva']}")
    if texto_valido(cliente.get("direccion")):
        rec.append(cliente["direccion"])
    if texto_valido(cliente.get("localidad")):
        rec.append(cliente["localidad"])
    if rec:
        canvas.setFont("Helvetica", 8)
        canvas.drawString(xL + 18 * mm, band_split - 10.5 * mm, "   ".join(rec))

    # --- Leyenda no fiscal (hasta integrar AFIP/CAE en Fase 4) ---
    if no_valido:
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(colors.HexColor("#b00000"))
        canvas.drawCentredString(mid_x, box_bottom - 5 * mm, "DOCUMENTO NO VÁLIDO COMO FACTURA")
        canvas.setFillColor(colors.black)


def _draw_qr(canvas, url: str, x: float, y: float, size: float) -> None:
    """Dibuja el QR de la URL AFIP en (x, y) escalado a `size` x `size`."""
    qr = QrCodeWidget(url)
    b = qr.getBounds()
    w, h = (b[2] - b[0]) or 1, (b[3] - b[1]) or 1
    dibujo = Drawing(size, size, transform=[size / w, 0, 0, size / h, 0, 0])
    dibujo.add(qr)
    renderPDF.draw(dibujo, canvas, x, y)


def _dibujar_pie_fiscal(canvas, doc: dict) -> None:
    """Pie del comprobante autorizado: QR de AFIP (abajo-izquierda) + CAE y su
    vencimiento. Solo se dibuja cuando el documento tiene CAE (es fiscal)."""
    left = 18 * mm
    y = 4 * mm
    size = 24 * mm
    qr_url = doc.get("afip_qr")
    if qr_url:
        _draw_qr(canvas, qr_url, left, y, size)
    tx = left + size + 4 * mm if qr_url else left
    canvas.setFillColor(colors.black)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(tx, y + size - 4 * mm, "Comprobante autorizado por AFIP")
    canvas.setFont("Helvetica", 8)
    canvas.drawString(tx, y + size - 10 * mm, f"CAE N.º: {doc.get('cae')}")
    canvas.drawString(tx, y + size - 14 * mm, f"Vto. CAE: {fmt_fecha(doc.get('cae_vto'))}")


def _tabla_lineas(lineas: list[dict]) -> Table:
    header = ["Producto", "Cantidad", "Precio unit.", "Importe"]
    rows = [header]
    for ln in lineas:
        if ln.get("concepto_nombre"):
            # Producto vivo: nombre + código, sin talle (en la factura el
            # producto va por nombre, indiferente al talle de la variante).
            base = nombre_sin_talle(ln["concepto_nombre"])
            nombre = etiqueta_concepto(base, ln.get("concepto_codigo"))
        else:
            # Texto libre o snapshot de un producto borrado: mostrar tal cual.
            nombre = (ln.get("concepto_libre") or "").strip()
        cantidad = ln.get("cantidad") or 0
        pvp = ln.get("pvp") or 0
        importe = cantidad * pvp
        rows.append([
            Paragraph(nombre, _style_small),
            f"{cantidad:g}",
            fmt_ar(pvp),
            fmt_ar(importe),
        ])

    table = Table(rows, colWidths=[90 * mm, 25 * mm, 30 * mm, 30 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b2b2b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _tabla_totales(doc: dict, lineas: list[dict], suplidos: list[dict], tipo: str,
                   empresa: dict | None = None, letra: str = "X") -> Table:
    subtotal = sum((ln.get("cantidad") or 0) * (ln.get("pvp") or 0) for ln in lineas)
    total_suplidos = sum(s.get("importe") or 0 for s in suplidos)
    aplica_bonif = bool(doc.get("aplica_bonificacion"))
    bonificacion_pct = doc.get("bonificacion") or 0
    bonificacion = subtotal * bonificacion_pct / 100.0 if aplica_bonif else 0.0

    rows = [["Subtotal", fmt_ar(subtotal)]]
    if aplica_bonif and bonificacion_pct:
        rows.append([f"Bonificación ({bonificacion_pct:g}%)", f"−{fmt_ar(bonificacion)}"])
    if total_suplidos:
        rows.append(["Suplidos", fmt_ar(total_suplidos)])
    total = subtotal - bonificacion + total_suplidos
    # En comprobante 'A' se discrimina el IVA (precios tomados como IVA incluido).
    if letra == "A":
        iva_rate = float((empresa or {}).get("iva_defecto") or 21.0)
        neto = total / (1 + iva_rate / 100.0)
        iva_amt = total - neto
        rows.append(["Neto gravado", fmt_ar(neto)])
        rows.append([f"IVA {iva_rate:g}%", fmt_ar(iva_amt)])
    rows.append(["TOTAL", fmt_ar(total)])

    table = Table(rows, colWidths=[110 * mm, 40 * mm], hAlign="RIGHT")
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 11),
        ("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.black),
    ]
    table.setStyle(TableStyle(style))
    return table


def generar_reporte_remesa(db, remesa_id: int) -> str:
    """Reporte PDF simple de una remesa (no es un archivo bancario SEPA/AEB real)."""
    remesas = db.get_all_remesas()
    remesa = next((r for r in remesas if r["id"] == remesa_id), None)
    if not remesa:
        raise ValueError(f"Remesa {remesa_id} no encontrada")
    recibos = db.get_recibos_de_remesa(remesa_id)

    carpeta = obtener_carpeta_pdf(db)
    carpeta.mkdir(parents=True, exist_ok=True)
    out_path = carpeta / f"remesa_{remesa_id}.pdf"

    pdf_doc = SimpleDocTemplate(str(out_path), pagesize=A4, topMargin=20 * mm)
    story = [
        Paragraph(f"Remesa #{remesa_id} — {remesa.get('descripcion') or ''}", _styles["Title"]),
        Spacer(1, 6 * mm),
    ]
    rows = [["Cliente", "Documento", "Importe"]]
    for r in recibos:
        rows.append([r.get("cliente_nombre", ""), f"{r.get('factura_tipo','')}-{r.get('factura_numero','')}",
                     fmt_ar(r.get("importe") or 0)])
    rows.append(["", "TOTAL", fmt_ar(sum(r.get("importe") or 0 for r in recibos))])
    table = Table(rows, colWidths=[80 * mm, 50 * mm, 30 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2b2b2b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    story.append(table)
    pdf_doc.build(story)
    return str(out_path)
