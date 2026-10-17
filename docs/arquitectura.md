# Arquitectura

Vexa es un monorepo con un **core compartido sin interfaz** y dos aplicaciones que lo consumen. Todo funciona offline
sobre SQLite; no hay servidor propio. Los detalles de uso están en el [README](../README.md) y las trampas de cada
framework en [CLAUDE.md](../CLAUDE.md).

## Piezas

```
vexa_core/   lógica pura, sin Qt ni Flet (paquete instalable con pip install -e ./vexa_core)
desktop/     app de escritorio PySide6 (Qt 6), se distribuye como .exe de PyInstaller + instalador Inno Setup
mobile/      app Android con Flet, consume vexa_core
```

Las dependencias van en un sentido: `desktop` y `mobile` importan `vexa_core`; el core nunca importa una UI.

## vexa_core

- `database/models.py`: el esquema, con modelos SQLAlchemy 2.0. `database/db.py` (`DatabaseManager`) hace todo el
  acceso a datos con `Session` y devuelve `dict`, así que se testea sin interfaz. `database/migration.py` importa una
  sola vez los datos del sistema legacy en Access (`.mdb`), sin Access ni ODBC.
- `utils/`: funciones puras. `facturas.py` (totales y reglas de la factura), `pdf_generator.py` (PDF con ReportLab),
  `excel_import.py` (listas de precios `.xlsx`, `.xlsm` y CSV), `helpers.py` (formato de dinero y fecha, código y
  talle embebidos en el nombre del producto).
- `fiscal/`: facturación electrónica con ARCA (ex AFIP), enchufable. `provider.py` define `FiscalProvider` y un
  `NoFiscalProvider` por defecto; `afip.py` implementa WSAA (firma CMS) y WSFEv1 (CAE) con zeep; `qr.py` arma la URL
  del QR de la RG 4291. Sin configurar, los documentos salen como no fiscales.
- `version.py`: la versión única que muestran las UIs y se usa al empaquetar.

## Datos

La base vive en `~/Facturacion/data.db` (o en `FACTURACION_DATA_DIR`; en Android, en el almacenamiento privado de la
app), fuera del repo. Se crea y actualiza sola al arrancar: `init_db()` hace `create_all`, aplica migraciones de
columnas idempotentes y mantiene el modo WAL con `foreign_keys=ON`. Tablas principales: `datos_empresa`, `clientes`,
`conceptos`, `facturas` (polimórfica por `tipo`: FA, PR, PE), `lineas`, `suplidos`, `forma_pago`, `iva` y `configuracion`.

## Desktop

Tres capas: `ui/` (cada pantalla es un `QWidget` que recibe el `DatabaseManager`; `main_window.py` las apila en un
`QStackedWidget`), `vexa_core/utils` y `vexa_core/database`. El tema claro y oscuro y el zoom son preferencias
guardadas en `configuracion`; el stylesheet de `ui/styles.py` se genera desde una paleta y un nivel de zoom y se
reaplica en caliente. El empaquetado está en `desktop/packaging/` (`facturacion.spec`, `installer.iss`).

## Mobile

App Flet con barra inferior de cinco secciones, onboarding de primera ejecución y la misma lógica del core. Como
`flet build` necesita el core dentro de `mobile/src/`, `mobile/scripts/vendor_core.py` lo copia ahí (copia ignorada por
git): se edita siempre `vexa_core/vexa_core/` y se vuelve a copiar. Los tests (`mobile/tests/`, pytest y pytest-bdd,
sin interfaz gráfica) corren en CI.

## Release

El tag `vX.Y.Z` sale de `main`. La versión se sube junta en `vexa_core/vexa_core/version.py`, `mobile/pyproject.toml` y
`desktop/packaging/installer.iss`. Los APK se firman siempre con el mismo keystore (que no está en el repo) para que
las actualizaciones conserven los datos.
