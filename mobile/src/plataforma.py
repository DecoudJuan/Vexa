"""Adaptaciones de plataforma para Vexa mobile.

En Android compartimos el PDF vía un share-intent (para que el usuario lo mande
por WhatsApp/mail/lo guarde). En escritorio (durante el spike) lo abrimos con la
app por defecto del sistema. Todo import específico de Android es perezoso y
protegido, así el mismo archivo corre en Windows/macOS/Linux sin romper.
"""
from __future__ import annotations

import os
import sys


def es_android() -> bool:
    return "ANDROID_ARGUMENT" in os.environ or "ANDROID_ROOT" in os.environ


def _compartir_android(ruta: str) -> None:
    """Lanza un ACTION_SEND con el PDF usando un FileProvider vía jnius."""
    from jnius import autoclass, cast  # type: ignore

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Intent = autoclass("android.content.Intent")
    File = autoclass("java.io.File")
    FileProvider = autoclass("androidx.core.content.FileProvider")

    activity = PythonActivity.mActivity
    archivo = File(ruta)
    authority = activity.getPackageName() + ".flutter.share_provider"
    uri = FileProvider.getUriForFile(activity, authority, archivo)

    intent = Intent(Intent.ACTION_SEND)
    intent.setType("application/pdf")
    intent.putExtra(Intent.EXTRA_STREAM, cast("android.os.Parcelable", uri))
    intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    chooser = Intent.createChooser(intent, cast("java.lang.CharSequence", "Compartir factura"))
    chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    activity.startActivity(chooser)


def _abrir_escritorio(ruta: str) -> None:
    if sys.platform.startswith("win"):
        os.startfile(ruta)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        os.system(f'open "{ruta}"')
    else:
        os.system(f'xdg-open "{ruta}"')


def abrir_o_compartir_pdf(page, ruta: str) -> bool:
    """Comparte (Android) o abre (escritorio) el PDF en `ruta`.

    Devuelve True si logró abrir/compartir; False si solo quedó guardado (el
    archivo ya existe en `ruta` igual). No propaga errores del share: en el spike
    lo importante es que el PDF se haya generado; compartir es best-effort.
    """
    try:
        if es_android():
            _compartir_android(ruta)
        else:
            _abrir_escritorio(ruta)
        return True
    except Exception:  # noqa: BLE001 — el PDF ya está en disco; el share es opcional
        return False
