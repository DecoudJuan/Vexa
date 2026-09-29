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

- **Commits**: identidad del usuario (Juan Decoud). **Nunca** agregar `Co-Authored-By: Claude`. Commits chicos, por rama/PR. `gh` está instalado: PRs/releases con la cuenta **`DecoudJuan`** (verificar `gh auth status`).
- **Librerías conocidas antes que inventar**: usar lo estándar del framework (estilo/QSS/layouts de Qt, controles de Flet, helpers de `vexa_core`) antes de escribir un componente propio. Los parches caseros (delegates, animaciones, tamaños calculados a mano) terminaron en bugs visuales.
- **Parseo/formato de números**: leer SIEMPRE con `parse_float` (acepta `14500`, `14.500`, `14500,50`, `14.500,50`) y precargar campos editables con `fmt_num_input` (es-AR, sin miles: `14000`, `14000,5`). Nunca `float(x.replace(".", ""))` ni `f"{x:.2f}"` en un campo editable (así nació el bug del precio ×10ⁿ).
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

## Trampas conocidas (desktop PySide6)

- **Estilo Fusion** (`app.setStyle("Fusion")` en `main.py`): el nativo `windows11` pinta selección/foco con el acento del **sistema** (barritas violetas) y choca con el QSS. No volver a taparlo con delegates.
- **Selección de listas** (`ListTable` en `anim.py`): la pinta el QSS (`QTableWidget::item:selected`). **No** poner `color:` en `::item`: pisa el `ForegroundRole` de cada celda (ej. código en acento).
- **Especificidad QSS**: `QFrame#x QLabel` le gana a `QLabel#chip`. Para un hijo con estilo propio, usar `QFrame#x QLabel#chip`.
- **Colores**: `muted2` es para bordes/fondos, **no para texto**. En oscuro no se lee. Texto tenue/deshabilitado/placeholder → `faint_tx`. Íconos de botones que se deshabilitan → `svg_icon(..., disabled_color=pal["faint_tx"])`.
- **`QComboBox::drop-down`** sin fondo propio (`background: transparent`, `subcontrol-origin: padding`). Si no, tapa el borde derecho del combo, que se ve cortado.
- **Texto largo**: word wrap + layouts (`QScrollArea` + `QVBoxLayout`) o `verticalHeader().setSectionResizeMode(ResizeToContents)`. No `QListWidget` + `setItemWidget` con `sizeHint` fijado a mano. Con word wrap, dejar poco padding vertical en `::item` (Qt no lo descuenta del alto).
- **Colores inline** (`setStyleSheet(f"color:{pal[...]}")`) se congelan con el tema de ese momento. Preferir `objectName`/propiedades + QSS global.
- **Verificar UI con capturas**: `widget.grab().save(...)` (Qt offscreen o ventana real), en tema claro **y** oscuro, con el tema guardado en la base (`db.set_config("theme", ...)`).
- **Entorno**: `vexa_core` tiene que estar instalado editable desde ESTE repo (`pip install -e ./vexa_core`). Si `pip show vexa_core` apunta a otra carpeta (ej. la vieja `projects/facturacion`), desktop importa un core viejo.

## Build / release (trampas)

- Tras cambiar el core: `python mobile/scripts/vendor_core.py` antes de correr los tests de mobile (si no, importan la copia vieja).
- `flet build` puede pedir instalar el Flutter SDK con un prompt interactivo. Sin consola: `yes y | powershell -File mobile\scripts\build_apk.ps1`.
- Verificar la firma del APK: `apksigner verify --print-certs` (build-tools del SDK, con `JAVA_HOME` apuntando a un JDK válido). El SHA-256 tiene que empezar con `999ddcd8…`.
- Release: tag `vX.Y.Z` en `main` + `gh release create` con los 3 APK (`arm64-v8a`, `armeabi-v7a`, `x86_64`) + `Vexa-vX.Y.Z.zip` (carpeta `desktop/packaging/dist/Facturacion`).

## Antes de dar algo por hecho

- Corré `cd mobile && python -m pytest -q` (CI corre lo mismo en `.github/workflows/ci.yml`).
- Bugs que solo aparecen en el `.exe`/APK: rebuildeá y probá el artefacto, no solo `flet run`/`python main.py`.
