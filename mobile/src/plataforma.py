"""Adaptaciones de plataforma para Vexa mobile.

En Android compartimos el PDF vía un share-intent (para que el usuario lo mande
por WhatsApp/mail/lo guarde). En escritorio (durante el spike) lo abrimos con la
app por defecto del sistema. Todo import específico de Android es perezoso y
protegido, así el mismo archivo corre en Windows/macOS/Linux sin romper.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def es_android() -> bool:
    return "ANDROID_ARGUMENT" in os.environ or "ANDROID_ROOT" in os.environ


def carpeta_documentos() -> Path:
    """Carpeta donde se generan los PDF.

    - **Android**: storage privado de la app (`DATA_DIR/pdf`), siempre escribible y
      cubierto por el FileProvider → el PDF se **entrega por el share sheet** (WhatsApp,
      Drive, guardar en Descargas…). Escribir directo a la carpeta Documentos compartida
      necesita permisos/MediaStore (queda para 6.2c).
    - **Escritorio**: `~/Documents/Vexa` (se abre con el visor del sistema).
    Override con `VEXA_DOCS_DIR`."""
    env = os.getenv("VEXA_DOCS_DIR")
    if env:
        base = Path(env)
    elif es_android():
        from vexa_core.database.db import DATA_DIR
        base = Path(DATA_DIR) / "pdf"
    else:
        base = Path.home() / "Documents" / "Vexa"
    try:
        base.mkdir(parents=True, exist_ok=True)
        return base
    except Exception:  # noqa: BLE001 — fallback al storage privado
        from vexa_core.database.db import DATA_DIR
        alt = Path(DATA_DIR) / "pdf"
        alt.mkdir(parents=True, exist_ok=True)
        return alt


def _compartir_android(ruta: str) -> None:
    """Lanza un ACTION_SEND con el PDF usando un FileProvider vía jnius."""
    from jnius import autoclass, cast  # type: ignore

    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    Intent = autoclass("android.content.Intent")
    File = autoclass("java.io.File")
    FileProvider = autoclass("androidx.core.content.FileProvider")

    activity = PythonActivity.mActivity
    archivo = File(ruta)
    # El FileProvider del build de Flet declara el authority `<applicationId>.provider`
    # (antes usábamos `.flutter.share_provider`, que NO existía → el share fallaba).
    authority = activity.getPackageName() + ".provider"
    uri = FileProvider.getUriForFile(activity, authority, archivo)

    intent = Intent(Intent.ACTION_SEND)
    intent.setType("application/pdf")
    intent.putExtra(Intent.EXTRA_STREAM, cast("android.os.Parcelable", uri))
    intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    chooser = Intent.createChooser(intent, cast("java.lang.CharSequence", "Compartir PDF"))
    chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    activity.startActivity(chooser)


def _abrir_escritorio(ruta: str) -> None:
    if sys.platform.startswith("win"):
        os.startfile(ruta)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        os.system(f'open "{ruta}"')
    else:
        os.system(f'xdg-open "{ruta}"')


async def entregar_pdf(app, ruta: str) -> bool:
    """Entrega el PDF al usuario.

    - **Android**: abre el **diálogo nativo para GUARDAR** (`FilePicker.save_file`), donde
      elige la carpeta/app destino (Descargas, Drive, etc.) y Flet escribe los bytes. Es
      confiable (no depende del share-intent nativo, que necesitaba el FileProvider/Activity
      correctos). Devuelve True si eligió destino, False si canceló.
    - **Escritorio**: lo abre con el visor del sistema.
    """
    import os
    if es_android():
        try:
            with open(ruta, "rb") as f:
                data = f.read()
            destino = await app.file_picker.save_file(
                dialog_title="Guardar PDF", file_name=os.path.basename(ruta),
                allowed_extensions=["pdf"], src_bytes=data)
            return destino is not None
        except Exception:  # noqa: BLE001 — el PDF ya está en disco
            return False
    return _abrir_escritorio(ruta) or True


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
