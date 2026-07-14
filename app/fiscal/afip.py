"""Proveedor AFIP: autenticación WSAA + autorización de comprobantes WSFEv1.

Wrapper propio (sin librerías GPL): SOAP con `zeep` y firma del ticket de acceso
con `cryptography` (CMS/PKCS#7). Offline salvo las dos llamadas a AFIP. Diseñado
para activarse cuando se cargue el certificado del contribuyente; hasta entonces
el código queda listo pero sin probar en vivo (no hay homologación sin cert).

Refs:
- WSAA: https://www.afip.gob.ar/ws/documentacion/wsaa.asp
- WSFEv1: https://www.afip.gob.ar/fe/documentos/manual_desarrollador_COMPG_v4.pdf
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from fiscal.provider import FiscalProvider, ResultadoAutorizacion
from fiscal.qr import construir_url_qr, moneda_afip

# Zona horaria de Argentina (UTC-3), para los timestamps del ticket WSAA.
_TZ_AR = timezone(timedelta(hours=-3))

# Endpoints por entorno. 'homologacion' = testing de AFIP; 'produccion' = real.
_ENDPOINTS = {
    "homologacion": {
        "wsaa": "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?wsdl",
        "wsfe": "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL",
    },
    "produccion": {
        "wsaa": "https://wsaa.afip.gov.ar/ws/services/LoginCms?wsdl",
        "wsfe": "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL",
    },
}

# Letra del comprobante -> código de tipo AFIP (WSFE).
#   Factura: A=1, B=6, C=11
_TIPO_CMP = {
    "FA": {"A": 1, "B": 6, "C": 11},
}

# Alícuota de IVA (%) -> Id de alícuota AFIP.
_ALIC_IVA = {0: 3, 10.5: 4, 21: 5, 27: 6, 5: 8, 2.5: 9}


class AfipError(RuntimeError):
    """Error de negocio de AFIP (rechazo, observación, credencial)."""


class AfipProvider(FiscalProvider):
    def __init__(self, *, cuit, pto_venta, cert_path, key_path,
                 entorno: str = "homologacion"):
        self.cuit = "".join(c for c in str(cuit or "") if c.isdigit())
        self.pto_venta = int("".join(c for c in str(pto_venta or "") if c.isdigit()) or 0)
        self.cert_path = cert_path
        self.key_path = key_path
        self.entorno = entorno if entorno in _ENDPOINTS else "homologacion"

    # ------------------------------------------------------------------ estado
    def disponible(self) -> bool:
        return bool(
            self.cuit and self.pto_venta and self.cert_path and self.key_path
            and Path(self.cert_path).is_file() and Path(self.key_path).is_file()
        )

    def _validar_config(self) -> None:
        if not self.cuit:
            raise AfipError("Falta el CUIT del emisor (Configuración → Datos de la empresa).")
        if not self.pto_venta:
            raise AfipError("Falta el punto de venta (Configuración → AFIP).")
        for etiqueta, ruta in (("certificado", self.cert_path), ("clave privada", self.key_path)):
            if not ruta or not Path(ruta).is_file():
                raise AfipError(f"No se encuentra el archivo de {etiqueta}: {ruta or '(vacío)'}")

    # -------------------------------------------------------------- WSAA (auth)
    def autenticar(self) -> dict:
        """Obtiene un Ticket de Acceso (TA) válido para WSFE: token + sign.
        Reusa el TA cacheado mientras no expire; si no, hace login contra WSAA."""
        self._validar_config()
        cache = self._ta_cache_path()
        ta = self._leer_ta_cache(cache)
        if ta:
            return ta
        ta = self._login_wsaa("wsfe")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(ta), encoding="utf-8")
        return ta

    def _ta_cache_path(self) -> Path:
        from database.db import DATA_DIR
        return DATA_DIR / "afip" / f"ta_wsfe_{self.entorno}.json"

    def _leer_ta_cache(self, cache: Path) -> dict | None:
        try:
            ta = json.loads(cache.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        try:
            vto = datetime.fromisoformat(ta.get("expiration", ""))
        except ValueError:
            return None
        # Margen de 10 min para no usar un TA a punto de expirar.
        if vto - timedelta(minutes=10) > datetime.now(_TZ_AR):
            return ta
        return None

    def _login_wsaa(self, servicio: str) -> dict:
        tra = self._login_ticket_request(servicio)
        cms = self._firmar_cms(tra)
        client = self._soap_client(_ENDPOINTS[self.entorno]["wsaa"])
        try:
            respuesta = client.service.loginCms(cms)
        except Exception as exc:  # zeep.exceptions.Fault y de red
            raise AfipError(f"WSAA rechazó la autenticación: {exc}") from exc
        return self._parsear_ta(respuesta)

    def _login_ticket_request(self, servicio: str) -> bytes:
        """XML del LoginTicketRequest con ventana de validez de ~12 h."""
        ahora = datetime.now(_TZ_AR)
        unique_id = str(int(ahora.timestamp()))
        root = ET.Element("loginTicketRequest", version="1.0")
        header = ET.SubElement(root, "header")
        ET.SubElement(header, "uniqueId").text = unique_id
        ET.SubElement(header, "generationTime").text = (ahora - timedelta(minutes=10)).isoformat()
        ET.SubElement(header, "expirationTime").text = (ahora + timedelta(hours=12)).isoformat()
        ET.SubElement(root, "service").text = servicio
        return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="utf-8")

    def _firmar_cms(self, datos: bytes) -> str:
        """Firma CMS/PKCS#7 (contenido embebido, DER, base64) del TRA con el
        certificado y la clave privada PEM del contribuyente."""
        from cryptography import x509
        from cryptography.hazmat.primitives.serialization import (
            load_pem_private_key, pkcs7, Encoding,
        )

        cert = x509.load_pem_x509_certificate(Path(self.cert_path).read_bytes())
        key = load_pem_private_key(Path(self.key_path).read_bytes(), password=None)
        cms = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(datos)
            .add_signer(cert, key, _hash_sha256())
            .sign(Encoding.DER, [pkcs7.PKCS7Options.Binary])
        )
        return base64.b64encode(cms).decode("ascii")

    def _parsear_ta(self, xml_texto: str) -> dict:
        root = ET.fromstring(xml_texto)
        token = root.findtext(".//credentials/token")
        sign = root.findtext(".//credentials/sign")
        expiration = root.findtext(".//header/expirationTime")
        if not (token and sign):
            raise AfipError("WSAA no devolvió credenciales válidas.")
        return {"token": token, "sign": sign, "expiration": expiration or ""}

    # -------------------------------------------------------------- WSFE (CAE)
    def autorizar(self, *, factura: dict, empresa: dict, cliente: dict,
                  lineas: list[dict]) -> ResultadoAutorizacion:
        from utils.helpers import letra_comprobante

        self._validar_config()
        tipo_doc = factura.get("tipo") or "FA"
        letra = letra_comprobante(empresa.get("condicion_iva"), cliente.get("condicion_iva"))
        tipo_cmp = _TIPO_CMP.get(tipo_doc, {}).get(letra)
        if not tipo_cmp:
            raise AfipError(
                f"No se puede emitir un comprobante fiscal tipo {tipo_doc} letra "
                f"{letra}. Revisá la condición frente al IVA del emisor y del cliente."
            )

        ta = self.autenticar()
        auth = {"Token": ta["token"], "Sign": ta["sign"], "Cuit": self.cuit}
        client = self._soap_client(_ENDPOINTS[self.entorno]["wsfe"])

        proximo = self._ultimo_autorizado(client, auth, tipo_cmp) + 1
        doc_tipo, doc_nro = _receptor(cliente)   # se calcula una sola vez
        detalle = self._armar_detalle(factura, empresa, letra, proximo, doc_tipo, doc_nro)
        req = {
            "FeCabReq": {"CantReg": 1, "PtoVta": self.pto_venta, "CbteTipo": tipo_cmp},
            "FeDetReq": {"FECAEDetRequest": [detalle]},
        }
        try:
            resp = client.service.FECAESolicitar(Auth=auth, FeCAEReq=req)
        except Exception as exc:
            raise AfipError(f"Error al solicitar el CAE: {exc}") from exc

        return self._interpretar_respuesta(
            resp, factura, empresa, tipo_cmp, proximo, doc_tipo, doc_nro
        )

    def _ultimo_autorizado(self, client, auth, tipo_cmp: int) -> int:
        try:
            r = client.service.FECompUltimoAutorizado(
                Auth=auth, PtoVta=self.pto_venta, CbteTipo=tipo_cmp
            )
        except Exception as exc:
            raise AfipError(f"No se pudo consultar el último comprobante: {exc}") from exc
        errores = _errores(r)
        if errores:
            raise AfipError("AFIP: " + " | ".join(errores))
        return int(getattr(r, "CbteNro", 0) or 0)

    def _armar_detalle(self, factura: dict, empresa: dict, letra: str,
                       numero: int, doc_tipo: int, doc_nro: int) -> dict:
        total = round(float(factura.get("total") or 0), 2)
        fecha_cmp = (factura.get("fecha") or "")[:10].replace("-", "")

        detalle = {
            "Concepto": 1,               # 1 = productos
            "DocTipo": doc_tipo,
            "DocNro": doc_nro,
            "CbteDesde": numero,
            "CbteHasta": numero,
            "CbteFch": fecha_cmp,
            "ImpTotal": total,
            "ImpTotConc": 0.0,           # neto no gravado
            "ImpOpEx": 0.0,              # exento
            "ImpTrib": 0.0,              # otros tributos
            "MonId": moneda_afip(empresa.get("moneda")),
            "MonCotiz": 1.0,
        }
        if letra == "C":
            # Monotributo/Exento: no se discrimina IVA.
            detalle["ImpNeto"] = total
            detalle["ImpIVA"] = 0.0
        else:
            rate = float(empresa.get("iva_defecto") or 21.0)
            neto = round(total / (1 + rate / 100.0), 2)
            iva = round(total - neto, 2)
            detalle["ImpNeto"] = neto
            detalle["ImpIVA"] = iva
            detalle["Iva"] = {"AlicIva": [{
                "Id": _ALIC_IVA.get(rate, 5),
                "BaseImp": neto,
                "Importe": iva,
            }]}
        return detalle

    def _interpretar_respuesta(self, resp, factura, empresa, tipo_cmp, numero,
                               doc_tipo, doc_nro) -> ResultadoAutorizacion:
        errores = _errores(resp)
        if errores:
            raise AfipError("AFIP: " + " | ".join(errores))
        cab = getattr(resp, "FeCabResp", None)
        resultado = getattr(cab, "Resultado", None) if cab else None
        det = None
        det_resp = getattr(getattr(resp, "FeDetResp", None), "FECAEDetResponse", None)
        if det_resp:
            det = det_resp[0]
        observaciones = _observaciones(det)

        if resultado != "A" or not det or not getattr(det, "CAE", None):
            return ResultadoAutorizacion(
                ok=False, resultado=resultado, observaciones=observaciones,
                mensaje="AFIP rechazó el comprobante. " + " | ".join(observaciones),
            )

        cae = str(det.CAE)
        vto_raw = str(getattr(det, "CAEFchVto", "") or "")   # yyyymmdd
        cae_vto = f"{vto_raw[:4]}-{vto_raw[4:6]}-{vto_raw[6:8]}" if len(vto_raw) == 8 else None
        qr_url = construir_url_qr(
            cuit_emisor=self.cuit,
            pto_venta=self.pto_venta,
            tipo_cmp=tipo_cmp,
            nro_cmp=numero,
            importe=float(factura.get("total") or 0),
            fecha=(factura.get("fecha") or "")[:10],
            cae=cae,
            moneda=moneda_afip(empresa.get("moneda")),
            tipo_doc_receptor=doc_tipo or None,
            nro_doc_receptor=doc_nro or None,
        )
        return ResultadoAutorizacion(
            ok=True, cae=cae, cae_vto=cae_vto, qr_url=qr_url, numero=numero,
            resultado=resultado, observaciones=observaciones,
            mensaje=f"Comprobante autorizado. CAE {cae} (vto {cae_vto}).",
        )

    # ------------------------------------------------------------------ SOAP
    def _soap_client(self, wsdl: str):
        from zeep import Client, Settings
        from zeep.transports import Transport

        settings = Settings(strict=False, xml_huge_tree=True)
        return Client(wsdl, settings=settings, transport=Transport(timeout=30))


def _hash_sha256():
    from cryptography.hazmat.primitives import hashes
    return hashes.SHA256()


def _receptor(cliente: dict) -> tuple[int, int]:
    """(DocTipo, DocNro) del receptor. CUIT=80, DNI=96, Consumidor Final=99.
    En comprobante A el receptor debe tener CUIT; si no hay documento se informa
    Consumidor Final con 0 (válido en B/C por debajo del umbral)."""
    from utils.helpers import valor_valido

    nif = valor_valido(cliente.get("nif"))
    solo = "".join(c for c in (nif or "") if c.isdigit())
    if solo and len(solo) == 11:
        return 80, int(solo)          # CUIT
    if solo and len(solo) in (7, 8):
        return 96, int(solo)          # DNI
    return 99, 0                       # Consumidor Final


def _errores(resp) -> list[str]:
    salida = []
    errs = getattr(resp, "Errors", None)
    lista = getattr(errs, "Err", None) if errs else None
    for e in (lista or []):
        salida.append(f"[{getattr(e, 'Code', '?')}] {getattr(e, 'Msg', '')}".strip())
    return salida


def _observaciones(det) -> list[str]:
    if not det:
        return []
    obs = getattr(det, "Observaciones", None)
    lista = getattr(obs, "Obs", None) if obs else None
    return [f"[{getattr(o, 'Code', '?')}] {getattr(o, 'Msg', '')}".strip() for o in (lista or [])]
