import sys
from pathlib import Path


def resource_path(relative: str) -> Path:
    """Resuelve una ruta de recurso empaquetado, tanto en desarrollo
    (python main.py) como una vez congelado con PyInstaller."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative
