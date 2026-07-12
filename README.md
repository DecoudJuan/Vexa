# Facturación

Aplicación de escritorio para **facturación** (clientes, productos y documentos),
construida en **Python + PySide6 (Qt)** sobre **SQLite**.

Reemplaza a la aplicación legacy en Microsoft Access (*ADHER*): la migración de
datos desde Access es un paso **único** de puesta en marcha; en tiempo de
ejecución la app **no depende de Access** ni de ningún driver ODBC.

> Alcance: es una herramienta **para facturar**, no un gestor integral. El foco
> está en dar de alta clientes/productos y emitir documentos con su PDF.

---

## Stack

| Área            | Tecnología                                   |
|-----------------|----------------------------------------------|
| UI              | PySide6 (Qt 6) — CSS/QSS propio, tema claro/oscuro |
| Base de datos   | SQLite (modo WAL), sin ORM — SQL directo     |
| Generación PDF  | ReportLab                                    |
| Importación     | openpyxl (listas de precios `.xlsx`/`.xlsm`) |
| Migración       | access_parser (lee `.mdb` sin Access/ODBC)   |
| Empaquetado     | PyInstaller + Inno Setup (instalador Windows)|

---

## Estructura del proyecto

```
facturacion/
├── README.md
├── .gitignore
├── app/                          # ← código de la aplicación
│   ├── main.py                   # punto de entrada: crea QApplication, DB y ventana
│   ├── version.py                # VERSION única (mostrada en UI y usada al empaquetar)
│   ├── requirements.txt          # dependencias de ejecución
│   ├── requirements-build.txt    # dependencias solo para buildear/migrar
│   │
│   ├── database/                 # capa de datos (sin dependencias de Qt)
│   │   ├── db.py                 # DatabaseManager: esquema + todo el acceso SQL
│   │   └── migration.py          # importador único desde Access legacy (.mdb)
│   │
│   ├── ui/                       # capa de presentación (todo lo que toca Qt)
│   │   ├── main_window.py        # ventana principal: sidebar, navegación, zoom/tema
│   │   ├── clientes.py           # ABM de clientes (+ CUIT/CUIL, saldos)
│   │   ├── conceptos.py          # ABM de productos + importación de listas de precios
│   │   ├── documentos.py         # listado y alta/edición de documentos (facturas…)
│   │   ├── cobros.py             # recibos y remesas
│   │   ├── configuracion.py      # datos de empresa, IVA, formas de pago, apariencia
│   │   ├── modal.py              # BaseModal: diálogo/tarjeta reutilizable de la app
│   │   ├── widgets.py            # widgets chicos compartidos (NoScrollComboBox, fila…)
│   │   ├── styles.py             # stylesheet (QSS) y paletas de color por tema
│   │   └── icons.py              # íconos SVG inline renderizados a QIcon/QPixmap
│   │
│   ├── utils/                    # helpers puros, reutilizables y sin estado de UI
│   │   ├── helpers.py            # formato ($/fecha), parseo de código de producto…
│   │   ├── pdf_generator.py      # armado de PDF de documentos y remesas (ReportLab)
│   │   ├── excel_import.py       # lectura de listas de precios en Excel
│   │   └── resources.py          # resolución de rutas de assets (dev y PyInstaller)
│   │
│   ├── assets/                   # ícono e imagen de la app (icon.ico, logo.png)
│   └── packaging/                # config de empaquetado (.spec, installer.iss)
│
├── design/                       # bocetos HTML de referencia visual (no se empaqueta)
├── Distribucion/                 # paquete final para el usuario (ignorado en git)
└── "Modelo Actual - Access"/     # app Access legacy (DATOS REALES — ignorado en git)
```

---

## Arquitectura

La app está organizada en **tres capas** con dependencias en una sola dirección
(`ui → utils/database`, nunca al revés):

- **`database/`** — Todo el SQL vive acá. `DatabaseManager` (`db.py`) expone
  métodos por entidad (`get_all_clientes`, `create_factura`, …) y es la única
  parte que conoce el esquema. No importa nada de Qt, así que es testeable en
  aislamiento.
- **`ui/`** — Cada pantalla del menú lateral es un `QWidget` autónomo que recibe
  el `DatabaseManager` por constructor. La ventana principal (`main_window.py`)
  los apila en un `QStackedWidget` y coordina navegación, zoom y tema.
- **`utils/`** — Funciones puras sin estado de UI (formato de dinero/fecha,
  extracción del código embebido en el nombre del producto, generación de PDF,
  importación de Excel). Reutilizables desde cualquier capa.

**Tema y zoom** son preferencias persistidas en la tabla `configuracion`. El
stylesheet (`styles.py`) se genera a partir de una paleta + nivel de zoom y se
reaplica en caliente; los tamaños fijos en píxeles que Qt no recalcula solo
(anchos de sidebar, alto de fila) se ajustan por código.

### Base de datos

- Ubicación: **`~/Facturacion/data.db`** (fuera del repo — nunca se versiona).
- Se crea/actualiza sola al arrancar: `DatabaseManager.init_db()` corre el
  esquema (`CREATE TABLE IF NOT EXISTS …`) y aplica migraciones incrementales
  de columnas nuevas sobre bases ya existentes.
- Modo **WAL** para mejor concurrencia de lectura/escritura.
- Entidades principales: `clientes`, `conceptos` (productos), `facturas`
  (tabla polimórfica por `tipo`: FA/PR/AL/PE/AB), `lineas`, `forma_pago`, `iva`,
  `remesas`/`recibos` y `configuracion`.

---

## Puesta en marcha (desarrollo)

Requiere **Python 3.10+** (se usan anotaciones `str | None`).

```bash
cd app
python -m venv .venv
.venv\Scripts\activate            # Windows (PowerShell/CMD)
pip install -r requirements.txt
python main.py
```

En el primer arranque se crea la base vacía en `~/Facturacion/data.db`.

### Migrar datos desde Access (paso único)

Solo la primera vez, para poblar SQLite con los datos históricos del `.mdb`:

```bash
cd app
pip install -r requirements-build.txt   # incluye access_parser
python -m database.migration --source "C:\ruta\a\datos.mdb" [--force]
```

Este script **no** se incluye en el ejecutable final: es una herramienta de
desarrollo.

---

## Build del ejecutable (Windows)

Se empaqueta con PyInstaller usando el `.spec` de `app/packaging/`:

```bash
cd app
pip install -r requirements-build.txt
pyinstaller packaging/facturacion.spec
```

El resultado queda en `app/packaging/dist/`. El instalador de Windows se arma
con Inno Setup a partir de `app/packaging/installer.iss`.

> La app se corre desde el `.exe` generado (vía acceso directo). Tras cambios de
> código hay que **rebuildear** para verlos reflejados en el ejecutable.

---

## Datos y privacidad

El `.gitignore` excluye deliberadamente todo lo que contiene **datos reales de
clientes** o es un artefacto generado:

- La base Access legacy (`Modelo Actual - Access/`) y cualquier `.mdb/.accdb`.
- La base SQLite (`*.db`) y los paquetes de datos (`Distribucion/*.zip`).
- Listas de precios en Excel y PDFs generados.
- Artefactos de build (`dist/`, `build/`, `__pycache__/`) e IDE (`.idea/`).

Antes del primer `git push`, verificá que no quede ningún dato sensible
trackeado:

```bash
git status --ignored
```

---

## Licencia

Software **propietario** — todos los derechos reservados. Ver [`LICENSE`](LICENSE).
No está permitido copiar, distribuir ni modificar el código sin autorización
previa y por escrito del titular.
