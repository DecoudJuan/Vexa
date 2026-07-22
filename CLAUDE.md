# CLAUDE.md

Guía para trabajar en este repo con Claude Code. Mantenela corta y al día; el detalle largo vive en `README.md` y `ROADMAP.md`.

## Qué es

**Vexa** — facturador **offline** para Argentina (reemplazo de una app Access legacy). Monorepo con un **core compartido sin UI** y dos frontends:

- `vexa_core/` — lógica pura (SQLAlchemy 2.0, PDF con ReportLab, import Excel, fiscal AFIP). **No importa Qt ni Flet.** Fuente de verdad.
- `desktop/` — app de escritorio **PySide6** (se distribuye como `.exe` de PyInstaller).
- `mobile/` — app Android **Flet 0.86** (Flutter en Python). Consume `vexa_core`.

Alcance del producto: **solo facturar**. No es un gestor — no hay stock, cobros ni estados de factura. **No reintroducir** eso sin pedido explícito.

## Comandos

Correr **desde la raíz del repo** (para que `-e ./vexa_core` resuelva).

```bash
# Desktop
pip install -r desktop/requirements.txt        # PySide6 + core editable
python desktop/main.py

# Mobile (iterar en escritorio, ventana tamaño celular)
cd mobile && flet run src/main.py

# Tests (headless: unitarios + BDD con pytest-bdd) — deben quedar VERDES
cd mobile && python -m pytest -q

# Build desktop (.exe)
cd desktop/packaging && python -m PyInstaller --noconfirm --clean facturacion.spec

# Build APK de release FIRMADO (conserva datos al actualizar) — Windows
powershell -ExecutionPolicy Bypass -File mobile\scripts\build_apk.ps1
```

## Arquitectura y datos

- **Dónde viven los datos**: `~/Facturacion/data.db` (o `FACTURACION_DATA_DIR`; en Android, el storage privado de la app). **Fuera del repo, nunca se versiona.**
- **Esquema/migraciones**: `db.init_db()` hace `create_all` + `ALTER` idempotentes + backfills + `_correcciones_catalogo()` (correcciones puntuales de catálogo, idempotentes). Corre en ambas apps al arrancar; una base vieja se actualiza en el lugar sin perder datos.
- **Core duplicado en mobile**: `mobile/src/vexa_core/` es una **copia vendorizada** (gitignoreada) que genera `python mobile/scripts/vendor_core.py`. **Editá siempre `vexa_core/vexa_core/` (la raíz) y re-vendorizá**; no edites la copia de mobile (se pisa al buildear).
- **Seed mobile**: si existe `mobile/src/seed_data.db`, `main.py` lo copia al primer arranque (salta onboarding). Las **releases van vacías** (se saca el seed). Al generarlo hay que hacer `PRAGMA wal_checkpoint(TRUNCATE)` (Android copia solo el `.db`, sin `-wal`).

## Convenciones (importante)

- **Commits**: identidad del usuario (Juan Decoud). **Nunca** agregar `Co-Authored-By: Claude`. Commits chicos, por rama/PR. No hay `gh` CLI: se pushea y se pasa el link de compare.
- **Versionado**: subir juntos `vexa_core/vexa_core/version.py`, `mobile/pyproject.toml` y `desktop/packaging/installer.iss` (semver).
- **Docs**: mantener `ROADMAP.md` y `README.md` al día ante cambios de features/estructura.
- **Firma Android**: usar siempre `mobile/signing/vexa-release.keystore` (misma clave que todas las releases → updates sin borrar datos). El keystore está gitignoreado; **hay backup aparte**. Generar una clave nueva NO es retrocompatible.

## Trampas conocidas (Flet 0.86)

- `ft.run` (no `ft.app`); constantes en `ft.Icons/Colors/Alignment.CONST`.
- **No existen** `ft.padding.only/all` ni `ft.border.all` → usar los helpers de `theme.py` (`PAD/PADS/MAR/BALL/BEDGE`).
- `FilePicker`/`Share` son **services** (`page.services`, no `page.overlay`).
- `TextField` usa `label`/`error`, **no** `helper_text`.
- **Re-render**: mutar `.content`/`.controls` de un control montado + `update()` a veces NO re-renderiza (pantalla gris/negra). Patrón usado: `app.render()` reconstruye el árbol; DENTRO de un modal, mutar un sub-control persistente (`Column.controls`) + `update()`.
- Cambios de tema/cierre de sheets/borrados: diferir el `render()` al `on_dismiss` del diálogo (si no, queda el scrim negro).
- Listas largas: usar `ft.ListView` (virtualizado), no `ft.Column(scroll=...)`.
- En Windows, `flet build` necesita `PYTHONUTF8=1` (si no, crashea con `rich`).

## Antes de dar algo por hecho

- Corré `cd mobile && python -m pytest -q` (CI corre lo mismo en `.github/workflows/ci.yml`).
- Bugs que solo aparecen en el `.exe`/APK: rebuildeá y probá el artefacto, no solo `flet run`/`python main.py`.
