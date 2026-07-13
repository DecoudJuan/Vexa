"""QR de la factura electrónica AFIP (RG 4291).

El comprobante autorizado lleva un QR que codifica los datos fiscales en una URL
`https://www.afip.gob.ar/fe/qr/?p=<base64>`, donde el payload es un JSON compacto
en base64. Esta función es **pura** (sin red ni estado) para poder testearla sola.
Ver spec: https://www.afip.gob.ar/fe/qr/documentos/QRespecificaciones.pdf
"""

from __future__ import annotations

import base64
import json

QR_BASE_URL = "https://www.afip.gob.ar/fe/qr/?p="

# Símbolo de moneda (el que guarda la app) -> código de moneda AFIP.
_MONEDA_AFIP = {"$": "PES", "US$": "DOL", "USD": "DOL", "u$s": "DOL"}


def moneda_afip(simbolo: str | None) -> str:
    """Código de moneda AFIP a partir del símbolo configurado. Por defecto 'PES'."""
    return _MONEDA_AFIP.get((simbolo or "").strip(), "PES")


def _solo_digitos(texto) -> int:
    """Deja solo los dígitos de un CUIT/documento ('30-71234567-8' -> 30712345678)."""
    d = "".join(c for c in str(texto or "") if c.isdigit())
    return int(d) if d else 0


def construir_url_qr(
    *,
    cuit_emisor,
    pto_venta: int,
    tipo_cmp: int,
    nro_cmp: int,
    importe: float,
    fecha: str,
    cae,
    moneda: str = "PES",
    cotizacion: float = 1.0,
    tipo_doc_receptor: int | None = None,
    nro_doc_receptor=None,
    tipo_cod_aut: str = "E",
    version: int = 1,
) -> str:
    """Arma la URL del QR AFIP. `fecha` en formato 'YYYY-MM-DD'; `cae` es el
    código de autorización (CAE, o CAEA con tipo_cod_aut='A'). El JSON va compacto
    (sin espacios) y codificado en base64 estándar, como exige la especificación."""
    payload = {
        "ver": version,
        "fecha": (fecha or "")[:10],
        "cuit": _solo_digitos(cuit_emisor),
        "ptoVta": int(pto_venta or 0),
        "tipoCmp": int(tipo_cmp or 0),
        "nroCmp": int(nro_cmp or 0),
        "importe": round(float(importe or 0), 2),
        "moneda": moneda or "PES",
        "ctz": round(float(cotizacion or 1), 2),
        "tipoCodAut": tipo_cod_aut,
        "codAut": _solo_digitos(cae),
    }
    # tipoDocRec/nroDocRec son opcionales (van si hay receptor identificado).
    if tipo_doc_receptor:
        payload["tipoDocRec"] = int(tipo_doc_receptor)
        payload["nroDocRec"] = _solo_digitos(nro_doc_receptor)

    crudo = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    b64 = base64.b64encode(crudo.encode("utf-8")).decode("ascii")
    return QR_BASE_URL + b64
