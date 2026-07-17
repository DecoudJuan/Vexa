"""Copia (vendoriza) `vexa_core` dentro de `mobile/src/vexa_core`.

`flet build` instala las dependencias con pip --target para Android y NO respeta
rutas locales (`[tool.uv.sources]`): intentaría bajar `vexa_core` de PyPI (donde hay
un paquete ajeno del mismo nombre). Por eso el core se copia como código de la app.

La copia está gitignoreada; se regenera antes de cada `flet build`. En escritorio no
hace falta (se usa el `vexa_core` instalado en modo editable).
"""
from __future__ import annotations

import shutil
from pathlib import Path

AQUI = Path(__file__).resolve().parent
MOBILE = AQUI.parent
ORIGEN = MOBILE.parent / "vexa_core" / "vexa_core"
DESTINO = MOBILE / "src" / "vexa_core"

_IGNORAR = shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info")


def main() -> None:
    if not ORIGEN.is_dir():
        raise SystemExit(f"No encuentro el core en {ORIGEN}")
    if DESTINO.exists():
        shutil.rmtree(DESTINO)
    shutil.copytree(ORIGEN, DESTINO, ignore=_IGNORAR)
    print(f"vexa_core vendorizado -> {DESTINO}")


if __name__ == "__main__":
    main()
