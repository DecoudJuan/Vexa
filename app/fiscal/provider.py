"""Contrato enchufable de facturación fiscal.

El resto de la app depende solo de `get_provider(db)` y de la interfaz
`FiscalProvider`; la implementación concreta (AFIP u offline) queda desacoplada.
Así se puede sumar otra jurisdicción/servicio más adelante sin tocar la UI.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ResultadoAutorizacion:
    """Resultado de pedir la autorización de un comprobante.

    ok=True y cae presente ⇒ el comprobante quedó autorizado (fiscal).
    Si ok=False, `mensaje`/`observaciones` explican por qué (config incompleta,
    rechazo de AFIP, error de red…)."""
    ok: bool
    cae: str | None = None
    cae_vto: str | None = None          # 'YYYY-MM-DD'
    qr_url: str | None = None
    numero: int | None = None           # nº de comprobante asignado por AFIP
    resultado: str | None = None        # 'A' aprobado, 'R' rechazado, 'P' parcial
    observaciones: list[str] = field(default_factory=list)
    mensaje: str = ""


class FiscalProvider(ABC):
    """Interfaz de un proveedor de comprobantes fiscales."""

    @abstractmethod
    def disponible(self) -> bool:
        """True si el proveedor está configurado y puede operar."""

    @abstractmethod
    def autenticar(self) -> None:
        """Verifica credenciales/conexión (para 'Probar conexión').
        Lanza excepción con un mensaje claro si algo falla."""

    @abstractmethod
    def autorizar(self, *, factura: dict, empresa: dict, cliente: dict,
                  lineas: list[dict]) -> ResultadoAutorizacion:
        """Solicita la autorización (CAE) del comprobante ante el organismo."""


class NoFiscalProvider(FiscalProvider):
    """Proveedor por defecto (offline): no emite comprobantes fiscales. Es el
    comportamiento histórico de la app; los documentos salen 'no válidos como
    factura' hasta configurar AFIP."""

    def disponible(self) -> bool:
        return False

    def autenticar(self) -> None:
        raise RuntimeError(
            "La facturación electrónica AFIP no está habilitada. Activala y "
            "cargá el certificado en Configuración → AFIP."
        )

    def autorizar(self, **_kwargs) -> ResultadoAutorizacion:
        return ResultadoAutorizacion(
            ok=False,
            mensaje="Facturación electrónica no habilitada (documento no fiscal).",
        )


def get_provider(db) -> FiscalProvider:
    """Fábrica: devuelve el proveedor AFIP si está habilitado y con certificado
    cargado; si no, el proveedor offline. Único punto de acoplamiento."""
    empresa = db.get_datos_empresa()
    if not empresa.get("afip_habilitado"):
        return NoFiscalProvider()
    cert = db.get_config("afip_cert_path")
    key = db.get_config("afip_key_path")
    if not (cert and key):
        return NoFiscalProvider()

    # Import perezoso: no cargar zeep/cryptography salvo que se use AFIP.
    from fiscal.afip import AfipProvider

    return AfipProvider(
        cuit=empresa.get("nif"),
        pto_venta=empresa.get("punto_venta"),
        cert_path=cert,
        key_path=key,
        entorno=db.get_config("afip_entorno") or "homologacion",
    )
