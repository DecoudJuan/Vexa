import os
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


# Talle embebido en el nombre: el número tras la barra de "CÓDIGO/TALLE"
# ("060/1" -> "1") o el de la forma "T1". Los talles por letra ("U", "M",
# "S/M/L") no se detectan solos: entran por la columna de talle al importar.
_TALLE_SLASH_RE = re.compile(r"\b\d{2,4}[A-Z]?\s*/\s*(\d+)\b")
_TALLE_T_RE = re.compile(r"\bT(\d+)\b")


def separar_codigo_talle(nombre: str | None):
    """Como separar_codigo(), pero además devuelve el talle embebido:
    (nombre_limpio, codigo, talle). "CALZA REDUCTORA 060/1" ->
    ("CALZA REDUCTORA", "060", "1"); "FAJA COMPRESION 24CM T1" ->
    ("FAJA COMPRESION 24CM", "", "1"). Talle "" si no hay."""
    if not nombre:
        return (nombre or "", "", "")
    limpio, codigo = separar_codigo(nombre)
    m = _TALLE_SLASH_RE.search(nombre) or _TALLE_T_RE.search(nombre)
    talle = m.group(1) if m else ""
    return (limpio, codigo, talle)


def fmt_talle(talle: str | None) -> str:
    """Talle para mostrar: "T1" si es numérico, o el texto tal cual (M, XL, U).
    Vacío si no hay."""
    t = (talle or "").strip()
    return f"T{t}" if t.isdigit() else t


def ordenar_talles(talles) -> list[str]:
    """Ordena talles: numéricos primero por valor (1, 2, 10), luego los de
    letra alfabéticamente (M, U, XL). Deduplica preservando el texto."""
    def clave(t: str):
        t = t.strip()
        return (0, int(t), "") if t.isdigit() else (1, 0, t.upper())
    return sorted({t.strip() for t in talles if t and t.strip()}, key=clave)


def etiqueta_concepto(nombre: str | None, codigo: str | None = None,
                      talle: str | None = None) -> str:
    """Etiqueta visible de un producto: "nombre T1 (codigo)" combinando lo que
    haya. Se usa en el combo de líneas de factura y en el PDF."""
    nombre = (nombre or "").strip()
    t = fmt_talle(talle)
    if t:
        nombre = f"{nombre} {t}"
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


# Condiciones frente al IVA (AR). Se usan en el alta de empresa y de cliente,
# y definen la letra del comprobante.
CONDICIONES_IVA = [
    "Responsable Inscripto",
    "Monotributo",
    "Exento",
    "Consumidor Final",
]


# Monedas ofrecidas (etiqueta, símbolo). El símbolo es lo que guarda/usa fmt_ar.
MONEDAS = [
    ("Peso argentino ($)", "$"),
    ("Dólar estadounidense (US$)", "US$"),
    ("Euro (€)", "€"),
    ("Real brasileño (R$)", "R$"),
]


def formatear_cuit(texto: str | None) -> str:
    """Formatea un CUIT/CUIL a 'XX-XXXXXXXX-X' a medida que se tipea (solo
    dígitos, máximo 11)."""
    d = "".join(c for c in (texto or "") if c.isdigit())[:11]
    if len(d) <= 2:
        return d
    if len(d) <= 10:
        return f"{d[:2]}-{d[2:]}"
    return f"{d[:2]}-{d[2:10]}-{d[10:]}"


# Placeholder de ejemplo para los campos de teléfono. Los campos son de texto
# libre (código de país + área + número) — no se fuerza un formato AR, así se
# admiten teléfonos de cualquier país.
TELEFONO_EJEMPLO = "+54 9 11 5555-5555"


def partir_direccion(direccion: str | None) -> tuple[str, str]:
    """Separa un domicilio guardado ('Av. Corrientes 1234') en (calle, número).
    Best-effort: el último token que tiene algún dígito se toma como número
    (ej. '1234', '1234B'). Si no hay número, devuelve ('...', '')."""
    s = (direccion or "").strip()
    if not s:
        return ("", "")
    partes = s.rsplit(" ", 1)
    if len(partes) == 2 and any(ch.isdigit() for ch in partes[1]):
        return (partes[0].strip(), partes[1].strip())
    return (s, "")


def unir_direccion(calle: str | None, numero: str | None) -> str | None:
    """Une calle y número en un solo domicilio ('Av. Corrientes 1234'). Devuelve
    None si no hay calle (para guardar NULL en la base)."""
    calle = (calle or "").strip()
    numero = (numero or "").strip()
    if not calle:
        return None
    return f"{calle} {numero}".strip() if numero else calle


def letra_comprobante(emisor_cond: str | None, receptor_cond: str | None) -> str:
    """Letra del comprobante según la condición frente al IVA del emisor y el
    receptor (regla AR simplificada):
      - Emisor Responsable Inscripto → 'A' a otro RI, 'B' al resto.
      - Emisor Monotributo o Exento → 'C'.
      - Sin condición de emisor definida → 'X' (comprobante no fiscal)."""
    emisor = (emisor_cond or "").strip().lower()
    receptor = (receptor_cond or "").strip().lower()
    if emisor.startswith("responsable"):
        return "A" if receptor.startswith("responsable") else "B"
    if emisor.startswith("monotributo") or emisor.startswith("exento"):
        return "C"
    return "X"


def valor_valido(valor: str | None) -> str | None:
    """Filtra los placeholders "sin dato" que dejó la migración de Access
    en campos que en la vida real siempre tienen números (CUIT/NIF, código
    postal): quedaron guardados como "*", "*-", "*********", etc. Un valor
    real de esos campos siempre tiene al menos un dígito, así que se
    descarta cualquier valor sin ninguno."""
    if valor and any(ch.isdigit() for ch in valor):
        return valor
    return None


# Símbolo de moneda actual (configurable desde Configuración > Mi empresa).
# Por defecto pesos argentinos ('$'); se puede cambiar a dólares ('US$', 'USD',
# etc.). Lo fija set_moneda() al arrancar y al guardar la configuración, así
# fmt_ar() lo toma solo, sin que cada llamador tenga que pasar el símbolo.
_MONEDA = "$"


def set_moneda(simbolo: str | None) -> None:
    """Fija el símbolo de moneda global que usa fmt_ar() por defecto."""
    global _MONEDA
    _MONEDA = (simbolo or "").strip() or "$"


def fmt_ar(value, moneda: str | None = None) -> str:
    """Importe en formato argentino: miles con '.' y decimales con ',' →
    '$ 1.234,56'. Usa el símbolo de moneda configurado (ver set_moneda) salvo
    que se pase uno explícito."""
    try:
        v = float(value or 0)
    except (TypeError, ValueError):
        v = 0.0
    s = f"{v:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return f"{moneda or _MONEDA} {s}"


def parse_float(text, default: float = 0.0) -> float:
    """Convierte texto a float aceptando la coma decimal es-AR: '1234,56',
    '1.234,56' y '1234.56' se leen todos correctamente. Devuelve `default`
    (0.0) si el texto está vacío o no es un número."""
    if text is None:
        return default
    s = str(text).strip()
    if not s:
        return default
    if "," in s:
        # Coma decimal: los puntos son separadores de miles.
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return default


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
    return db.get_config("theme") or "light"


def abrir_archivo(path: str) -> None:
    """Abre un archivo con la aplicación por defecto del sistema (Windows)."""
    os.startfile(path)


def leer_zoom(db) -> float:
    """Nivel de zoom actual (1.0 = 100%), usado para escalar los tamaños
    fijos en píxeles que el stylesheet no puede recalcular solo (alto de
    fila, ancho de columnas/diálogos, etc.)."""
    try:
        return float(db.get_config("zoom") or 0.9)
    except (TypeError, ValueError):
        return 0.9
