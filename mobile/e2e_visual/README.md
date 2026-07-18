# E2E visual (Appium) — Vexa mobile

Recorrido automatizado sobre el **APK real corriendo en un emulador Android** que
captura un screenshot de cada pantalla. Es el equivalente a "Cypress para mobile":
Vexa es una app Flutter (via Flet), así que se automatiza con **Appium + UiAutomator2**,
no con Cypress (que es solo web).

## Requisitos (una sola vez)
```bash
npm install -g appium
appium driver install uiautomator2
pip install Appium-Python-Client
```
Además: un AVD **x86_64** (los emuladores comunes son x86_64; el APK arm64-v8a NO
instala ahí). Ya existen `Vexa35` y `Vexa_Pixel`.

## Correr el tour
```bash
# 1) Emulador x86_64
"%ANDROID_HOME%\emulator\emulator.exe" -avd Vexa35 -no-snapshot -no-audio

# 2) Server Appium (otra terminal)
appium --address 127.0.0.1 --port 4723

# 3) APK x86_64 (misma UI que el arm64 de producción)
set PYTHONUTF8=1
flet build apk --arch x86_64

# 4) Tour → screenshots en e2e_visual/shots/
python e2e_visual/tour.py build/apk/vexa-mobile-x86_64.apk
```

## Qué captura
`01_inicio` (dashboard) · `02_clientes` · `03_productos` · `04_etiquetas` ·
`05_facturas` · `06_inicio`. Instala limpio (`full_reset`) para tomar la base
`src/seed_data.db` y saltear el onboarding.

## Notas
- **Navegación por coordenadas**: Flet dibuja sobre un canvas Flutter sin IDs de
  accesibilidad confiables, así que los taps son por fracción de pantalla. Robusto para
  un recorrido de screenshots; si se agregan/mueven tabs, ajustar `RECORRIDO` en `tour.py`.
- Los PNGs en `shots/` están **gitignoreados** (contienen datos reales de clientes).
- Barra inferior (orden real): Clientes · Productos · **Inicio** (centro) · Etiquetas · Facturas.
