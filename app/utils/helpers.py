import re

_TALLE_RE = re.compile(r"\s*\b\d{2,4}[A-Z]?/\d+\b|\s*\bT\d+\b")

# El código del producto viene embebido en el nombre de la lista de precios:
#   - "CALZA REDUCTORA 060/1"  -> código 060, talle 1  (forma CÓDIGO/TALLE)
#   - "HOMBRERA UNIVERSAL 026"  -> código 026           (código suelto al final)
#   - "... PULGAR 046 U"        -> código 046           (con letra de talle suelta)
# El código puede llevar una letra (ej. "004A"). Productos con solo talle "T1"
# o medidas ("24CM") no tienen código.
_COD_SLASH_RE = re.compile(r"\b(\d{2,4}[A-Z]?)\s*/\s*\d+")
# Código suelto: los del catálogo son de 3 dígitos (con letra opcional, ej.
# "004A"), y pueden aparecer en cualquier parte del nombre ("...VELOUR 071
# 50CM..."). Se excluyen las medidas (24CM, 8MM, 50CM) con un lookahead.
_COD_STANDALONE_RE = re.compile(r"\b(\d{3}[A-Z]?)\b(?!\s*(?:CM|MM|M)\b)")


def nombre_sin_talle(nombre: str | None) -> str:
    """Nombre de producto sin el sufijo de código/talle pegado por la
    migración de Access (ej. "CALZA REDUCTORA 060/1" -> "CALZA REDUCTORA",
    "FAJA ALTA COMPRESION 24CM T1" -> "FAJA ALTA COMPRESION 24CM")."""
    if not nombre:
        return nombre or ""
    limpio = _TALLE_RE.sub("", nombre)
    return re.sub(r"\s{2,}", " ", limpio).strip()


def separar_codigo(nombre: str | None):
    """Separa (nombre_limpio, codigo) a partir del nombre crudo de la lista de
    precios. Devuelve el código embebido (ej. "060", "004A") o "" si no tiene,
    y el nombre sin el código ni el talle (ej. "RODILLERA TUBULAR LISA").

    Contempla el código en la forma "CÓDIGO/TALLE" y también suelto en
    cualquier posición del nombre (algunos nombres viejos lo tienen en el
    medio, ej. "... EN VELOUR 071 50CM ..."). Limpiar el nombre igual que en el
    Excel actual permite que la reimportación empareje por nombre."""
    if not nombre:
        return (nombre or "", "")
    codigo = ""
    limpio = nombre_sin_talle(nombre)
    m = _COD_SLASH_RE.search(nombre)
    if m:
        codigo = m.group(1)
    else:
        matches = list(_COD_STANDALONE_RE.finditer(limpio))
        if matches:
            m2 = matches[-1]  # el último token de 3 dígitos es el código
            codigo = m2.group(1)
            limpio = limpio[: m2.start()] + " " + limpio[m2.end():]
    limpio = re.sub(r"\s{2,}", " ", limpio).strip()
    return (limpio, codigo)


def etiqueta_concepto(nombre: str | None, codigo: str | None = None) -> str:
    """Etiqueta visible de un producto: "nombre (codigo)" si tiene código,
    o solo el nombre. Se usa en el combo de líneas de factura y en el PDF."""
    nombre = (nombre or "").strip()
    codigo = (codigo or "").strip()
    return f"{nombre} ({codigo})" if codigo else nombre


# Las 24 jurisdicciones de Argentina, para el desplegable de Provincia al dar
# de alta un cliente (la localidad se sigue escribiendo a mano).
PROVINCIAS_AR = [
    "Buenos Aires",
    "Ciudad Autónoma de Buenos Aires",
    "Catamarca",
    "Chaco",
    "Chubut",
    "Córdoba",
    "Corrientes",
    "Entre Ríos",
    "Formosa",
    "Jujuy",
    "La Pampa",
    "La Rioja",
    "Mendoza",
    "Misiones",
    "Neuquén",
    "Río Negro",
    "Salta",
    "San Juan",
    "San Luis",
    "Santa Cruz",
    "Santa Fe",
    "Santiago del Estero",
    "Tierra del Fuego",
    "Tucumán",
]


def valor_valido(valor: str | None) -> str | None:
    """Filtra los placeholders "sin dato" que dejó la migración de Access
    en campos que en la vida real siempre tienen números (CUIT/NIF, código
    postal): quedaron guardados como "*", "*-", "*********", etc. Un valor
    real de esos campos siempre tiene al menos un dígito, así que se
    descarta cualquier valor sin ninguno."""
    if valor and any(ch.isdigit() for ch in valor):
        return valor
    return None


def fmt_money(value, moneda: str = "$") -> str:
    try:
        v = float(value or 0)
    except (TypeError, ValueError):
        v = 0.0
    return f"{moneda} {v:,.2f}"


def fmt_ar(value, moneda: str = "$") -> str:
    """Formato argentino: separador de miles '.' y decimales ',' → '$ 1.234,56'."""
    try:
        v = float(value or 0)
    except (TypeError, ValueError):
        v = 0.0
    s = f"{v:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"{moneda} {s}"


def fmt_fecha(iso_date: str | None) -> str:
    if not iso_date:
        return "—"
    partes = iso_date[:10].split("-")
    if len(partes) != 3:
        return iso_date
    y, m, d = partes
    return f"{d}/{m}/{y}"


def leer_tema(db) -> str:
    """Tema actual ('dark'/'light'), usado para elegir colores de ícono
    coherentes con el fondo (los íconos no se repintan solos con el CSS)."""
    return db.get_config("theme") or "dark"


def leer_zoom(db) -> float:
    """Nivel de zoom actual (1.0 = 100%), usado para escalar los tamaños
    fijos en píxeles que el stylesheet no puede recalcular solo (alto de
    fila, ancho de columnas/diálogos, etc.)."""
    try:
        return float(db.get_config("zoom") or 0.9)
    except (TypeError, ValueError):
        return 0.9
