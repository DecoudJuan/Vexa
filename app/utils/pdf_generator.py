import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_LEFT

from database.db import DATA_DIR
from utils.helpers import fmt_money, fmt_fecha, nombre_sin_talle, valor_valido, etiqueta_concepto
from utils.resources import resource_path

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

    carpeta = obtener_carpeta_pdf(db)
    carpeta.mkdir(parents=True, exist_ok=True)
    out_path = carpeta / f"{_slug(numero_doc)}.pdf"

    pdf_doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        topMargin=45 * mm, bottomMargin=20 * mm,
        leftMargin=18 * mm, rightMargin=18 * mm,
    )

    def _on_page(canvas, _doc):
        canvas.saveState()
        _dibujar_encabezado(canvas, empresa, cliente, titulo, numero_doc, doc)
        canvas.restoreState()

    story = []
    story.append(Spacer(1, 4 * mm))
    story.append(_tabla_lineas(lineas))
    story.append(Spacer(1, 6 * mm))
    story.append(_tabla_totales(doc, lineas, suplidos, tipo))

    if doc.get("comentarios"):
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph(f"<b>Comentarios:</b> {doc['comentarios']}", _style_small))

    pdf_doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return str(out_path)


def _dibujar_encabezado(canvas, empresa, cliente, titulo, numero_doc, doc):
    from reportlab.lib.pagesizes import A4
    width, height = A4

    logo_path = empresa.get("logo_path") or str(resource_path("assets/logo.png"))
    try:
        from reportlab.lib.utils import ImageReader
        img = ImageReader(logo_path)
        canvas.drawImage(img, 18 * mm, height - 38 * mm, width=28 * mm, height=20 * mm,
                          preserveAspectRatio=True, mask="auto")
    except Exception:
        pass

    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(50 * mm, height - 22 * mm, empresa.get("nombre") or "")
    canvas.setFont("Helvetica", 8)
    lineas_empresa = [
        empresa.get("direccion") or "",
        f"{valor_valido(empresa.get('cp')) or ''} {empresa.get('localidad') or ''}".strip(),
        f"Tel: {empresa.get('telefono')} (Hernan)" if empresa.get("telefono") else "",
    ]
    y = height - 27 * mm
    for linea in lineas_empresa:
        if linea:
            canvas.drawString(50 * mm, y, linea)
            y -= 4 * mm

    canvas.setFont("Helvetica-Bold", 18)
    canvas.drawRightString(width - 18 * mm, height - 20 * mm, titulo)
    canvas.setFont("Helvetica", 10)
    canvas.drawRightString(width - 18 * mm, height - 27 * mm, numero_doc)
    canvas.drawRightString(width - 18 * mm, height - 32 * mm, f"Fecha: {fmt_fecha(doc.get('fecha'))}")

    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(18 * mm, height - 45 * mm, "Cliente:")
    canvas.setFont("Helvetica", 9)
    canvas.drawString(35 * mm, height - 45 * mm, cliente.get("nombre") or "")
    canvas.setFont("Helvetica", 8)
    detalle_cliente = f"{valor_valido(cliente.get('nif')) or ''}  {cliente.get('direccion') or ''}  {cliente.get('localidad') or ''}".strip()
    canvas.drawString(35 * mm, height - 49 * mm, detalle_cliente)

    canvas.setStrokeColor(colors.HexColor("#888888"))
    canvas.line(18 * mm, height - 52 * mm, width - 18 * mm, height - 52 * mm)


def _tabla_lineas(lineas: list[dict]) -> Table:
    header = ["Producto", "Cantidad", "Precio unit.", "Importe"]
    rows = [header]
    for ln in lineas:
        base = nombre_sin_talle(ln.get("concepto_nombre") or ln.get("concepto_libre") or "")
        nombre = etiqueta_concepto(base, ln.get("concepto_codigo"))
        cantidad = ln.get("cantidad") or 0
        pvp = ln.get("pvp") or 0
        importe = cantidad * pvp
        rows.append([
            Paragraph(nombre, _style_small),
            f"{cantidad:g}",
            fmt_money(pvp),
            fmt_money(importe),
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


def _tabla_totales(doc: dict, lineas: list[dict], suplidos: list[dict], tipo: str) -> Table:
    subtotal = sum((ln.get("cantidad") or 0) * (ln.get("pvp") or 0) for ln in lineas)
    total_suplidos = sum(s.get("importe") or 0 for s in suplidos)
    aplica_bonif = bool(doc.get("aplica_bonificacion"))
    bonificacion_pct = doc.get("bonificacion") or 0
    bonificacion = subtotal * bonificacion_pct / 100.0 if aplica_bonif else 0.0

    rows = [["Subtotal", fmt_money(subtotal)]]
    if aplica_bonif and bonificacion_pct:
        rows.append([f"Bonificación ({bonificacion_pct:g}%)", f"−{fmt_money(bonificacion)}"])
    if total_suplidos:
        rows.append(["Suplidos", fmt_money(total_suplidos)])
    total = subtotal - bonificacion + total_suplidos
    rows.append(["TOTAL", fmt_money(total)])

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
                     fmt_money(r.get("importe") or 0)])
    rows.append(["", "TOTAL", fmt_money(sum(r.get("importe") or 0 for r in recibos))])
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
