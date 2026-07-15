"""Capa fiscal: facturación electrónica (CAE + QR) desacoplada de la UI.

Punto de entrada único: `get_provider(db)`. La implementación concreta (AFIP u
offline) queda detrás de la interfaz `FiscalProvider`."""

from vexa_core.fiscal.provider import (
    FiscalProvider, NoFiscalProvider, ResultadoAutorizacion, get_provider,
)

__all__ = [
    "FiscalProvider", "NoFiscalProvider", "ResultadoAutorizacion", "get_provider",
]
