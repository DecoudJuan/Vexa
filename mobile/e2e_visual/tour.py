"""E2E visual de Vexa mobile con Appium (equivalente a "Cypress para mobile").

Instala el APK en el emulador, recorre cada pantalla de la barra inferior y guarda
un screenshot PNG de cada una en `e2e_visual/shots/`. Sirve para revisar regresiones
visuales entre releases.

Requisitos (una vez):
    npm install -g appium
    appium driver install uiautomator2
    pip install Appium-Python-Client

Uso:
    1) Prender un emulador x86_64:  emulator -avd Vexa35
    2) Server Appium:               appium --address 127.0.0.1 --port 4723
    3) Buildear un APK x86_64:      flet build apk --arch x86_64
    4) Correr el tour:              python e2e_visual/tour.py [ruta_apk]

La barra inferior tiene 5 tabs: Clientes · Productos · Inicio(centro) · Etiquetas · Facturas.
Se navega por coordenadas proporcionales (Flet dibuja sobre un canvas Flutter, sin IDs
de accesibilidad confiables), que es robusto para un recorrido de screenshots.
"""
from __future__ import annotations

import sys
import time
import pathlib

from appium import webdriver
from appium.options.android import UiAutomator2Options

AQUI = pathlib.Path(__file__).resolve().parent
APK = sys.argv[1] if len(sys.argv) > 1 else str(AQUI.parent / "build" / "apk" / "vexa-mobile.apk")
OUT = AQUI / "shots"
OUT.mkdir(exist_ok=True)

# Orden de captura: arranca en Inicio (landing con la base seed), luego cada tab.
# (nombre_archivo, fracción_x del centro del tab en la barra inferior)
RECORRIDO = [
    ("02_clientes", 0.10),
    ("03_productos", 0.30),
    ("04_etiquetas", 0.70),
    ("05_facturas", 0.90),
    ("06_inicio", 0.50),
]
Y_BARRA = 0.955   # altura (fracción) de la barra inferior


def main() -> int:
    opts = UiAutomator2Options()
    opts.platform_name = "Android"
    opts.device_name = "emulator-5554"
    opts.automation_name = "UiAutomator2"
    opts.app = APK
    opts.auto_grant_permissions = True
    opts.full_reset = True          # instala limpio → toma el seed y saltea onboarding
    opts.app_wait_activity = "*"
    opts.new_command_timeout = 300

    print(f"APK: {APK}")
    driver = webdriver.Remote("http://127.0.0.1:4723", options=opts)
    try:
        time.sleep(6)               # splash de la V + primer render
        sz = driver.get_window_size()
        w, h = sz["width"], sz["height"]
        print(f"pantalla: {w}x{h}")

        def tap(fx: float, fy: float):
            driver.tap([(int(w * fx), int(h * fy))], 120)

        def shot(nombre: str):
            ruta = OUT / f"{nombre}.png"
            driver.get_screenshot_as_file(str(ruta))
            print("  screenshot:", ruta.name)

        shot("01_inicio")
        for nombre, fx in RECORRIDO:
            tap(fx, Y_BARRA)
            time.sleep(1.8)
            shot(nombre)
        print("OK: tour completo")
        return 0
    finally:
        driver.quit()


if __name__ == "__main__":
    raise SystemExit(main())
