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
| Base de datos   | SQLite (modo WAL) vía **SQLAlchemy 2.0** (ORM) |
| Generación PDF  | ReportLab                                    |
| Importación     | openpyxl + csv (listas de precios `.xlsx`/`.xlsm`/CSV, mapeo flexible con perfiles) |
| Facturación electrónica | zeep (SOAP WSAA/WSFEv1) + cryptography (firma CMS) — AFIP/ARCA, QR con reportlab |
| Migración       | access_parser (lee `.mdb` sin Access/ODBC)   |
| Empaquetado     | PyInstaller + Inno Setup (instalador Windows)|

---

## Estructura del proyecto

Monorepo: un **core compartido** (`vexa_core`, sin Qt) + una app de **escritorio**
(PySide6) y, más adelante, una **mobile** (Flet). Cada UI importa `vexa_core`.

```
Vexa/
├── README.md   ROADMAP.md   .gitignore
│
├── vexa_core/                    # ← paquete compartido, SIN dependencias de UI (pip install -e ./vexa_core)
│   ├── pyproject.toml            # deps del core (+ extras: [afip], [migrate])
│   └── vexa_core/
│       ├── version.py            # VERSION única (mostrada en UI y usada al empaquetar)
│       ├── database/             # capa de datos
│       │   ├── models.py         # modelos SQLAlchemy 2.0 (el esquema)
│       │   ├── db.py             # DatabaseManager: acceso a datos vía ORM (Session)
│       │   └── migration.py      # importador único desde Access legacy (.mdb)
│       ├── utils/                # helpers puros sin estado de UI
│       │   ├── helpers.py        # formato ($/fecha), parseo de código y talle…
│       │   ├── pdf_generator.py  # armado de PDF de documentos (ReportLab)
│       │   └── excel_import.py   # lectura de listas de precios en Excel
│       └── fiscal/               # facturación electrónica AFIP, enchufable
│           ├── provider.py       # FiscalProvider + NoFiscalProvider + get_provider
│           ├── afip.py           # WSAA (firma CMS) + WSFEv1 (CAE) vía zeep
│           └── qr.py             # URL del QR AFIP (RG 4291) — función pura
│
├── desktop/                      # ← app de ESCRITORIO (PySide6)
│   ├── main.py                   # punto de entrada: QApplication, DB y ventana
│   ├── resources.py              # resolución de rutas de assets (dev y PyInstaller)
│   ├── requirements.txt          # PySide6 + -e ./vexa_core[afip]
│   ├── requirements-build.txt    # pyinstaller (+ core con extras)
│   ├── assets/                   # íconos e imágenes de la app
│   ├── packaging/                # config de empaquetado (.spec, installer.iss)
│   └── ui/                       # capa de presentación (todo lo que toca Qt)
│       ├── main_window.py  home.py  onboarding.py  base_page.py
│       ├── clientes.py  conceptos.py  documentos.py  configuracion.py
│       ├── modal.py  widgets.py  anim.py  styles.py  icons.py
│
├── mobile/                       # ← app MOBILE Flet (Fase 6.2, aún no creada)
│
├── Distribucion/                 # paquete final para el usuario (ignorado en git)
└── "Modelo Actual - Access"/     # app Access legacy (DATOS REALES — ignorado en git)
```
```

---

## Arquitectura

La app está organizada en **tres capas** con dependencias en una sola dirección
(`ui → utils/database`, nunca al revés):

- **`database/`** — El esquema se define con modelos **SQLAlchemy 2.0**
  (`models.py`) y `DatabaseManager` (`db.py`) hace todo el acceso a datos con
  `Session`/`select()`, exponiendo métodos por entidad (`get_all_clientes`,
  `create_factura`, …) que devuelven `dict`. No importa nada de Qt, así que es
  testeable en aislamiento.
- **`ui/`** — Cada pantalla del menú lateral es un `QWidget` autónomo que recibe
  el `DatabaseManager` por constructor. La ventana principal (`main_window.py`)
  los apila en un `QStackedWidget` y coordina navegación, zoom y tema.
- **`utils/`** — Funciones puras sin estado de UI (formato de dinero/fecha,
  extracción del código y talle embebidos en el nombre del producto, generación
  de PDF, importación de Excel). Reutilizables desde cualquier capa.

**Tema y zoom** son preferencias persistidas en la tabla `configuracion`. El
stylesheet (`styles.py`) se genera a partir de una paleta + nivel de zoom y se
reaplica en caliente; los tamaños fijos en píxeles que Qt no recalcula solo
(anchos de sidebar, alto de fila) se ajustan por código.

### Base de datos

- Ubicación: **`~/Facturacion/data.db`** (fuera del repo — nunca se versiona).
  Se puede apuntar a otra carpeta con la variable de entorno
  **`FACTURACION_DATA_DIR`** (útil para un entorno de pruebas aislado).
- Se crea/actualiza sola al arrancar: `DatabaseManager.init_db()` hace
  `create_all` de los modelos y aplica migraciones incrementales de columnas
  nuevas sobre bases ya existentes (compatibilidad hacia atrás).
- Modo **WAL** y `foreign_keys=ON` vía listener del engine.
- Entidades principales: `datos_empresa`, `clientes` (+ `cliente_cuit`),
  `conceptos` (productos), `facturas` (tabla polimórfica por `tipo`: FA/PR/PE),
  `lineas`, `suplidos`, `forma_pago`, `iva` y `configuracion`.

---

## Puesta en marcha (desarrollo)

Requiere **Python 3.10+** (se usan anotaciones `str | None`).

Todo se corre **desde la raíz del repo** (para que `-e ./vexa_core` resuelva bien):

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows (PowerShell/CMD)
pip install -r desktop/requirements.txt   # instala el core (-e ./vexa_core) + PySide6
python desktop/main.py
```

En el primer arranque se crea la base vacía en `~/Facturacion/data.db`.

### Migrar datos desde Access (paso único)

Solo la primera vez, para poblar SQLite con los datos históricos del `.mdb`:

```bash
pip install -e ./vexa_core[migrate]   # incluye access_parser
python -m vexa_core.database.migration --source "C:\ruta\a\datos.mdb" [--force]
```

Este script **no** se incluye en el ejecutable final: es una herramienta de
desarrollo.

---

## Build del ejecutable (Windows)

Se empaqueta con PyInstaller usando el `.spec` de `desktop/packaging/` (requiere el
core instalado en editable):

```bash
pip install -r desktop/requirements-build.txt
pip install -e ./vexa_core[afip,migrate]
cd desktop/packaging
pyinstaller --noconfirm --clean facturacion.spec
```

El resultado queda en `desktop/packaging/dist/`. El instalador de Windows se arma
con Inno Setup a partir de `desktop/packaging/installer.iss`.

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

## Facturación electrónica (ARCA / AFIP)

La app puede pedir el **CAE** a ARCA (ex AFIP) y estampar el **código QR** en el
PDF, dejándolo como comprobante fiscal válido. Se hace con **web services**
(WSAA + WSFEv1) desde la propia máquina — sin intermediarios ni servicios en la
nube. Se puede con una cuenta **común** de ARCA (CUIT + Clave Fiscal); el trámite
es gratis y se hace una sola vez.

> Dentro de la app, en **Configuración → AFIP**, el botón
> **«¿Cómo conectarme con ARCA?»** abre esta misma guía paso a paso.

### Cómo vincularlo (paso a paso)

1. **Tené a mano** tu CUIT y tu Clave Fiscal (nivel 3 o superior).
2. **Elegí el entorno**: empezá por *Homologación* (pruebas) y, cuando funcione,
   pasá a *Producción*.
3. **Generá tu clave privada y el pedido de certificado** (CSR) con OpenSSL,
   reemplazando el CUIT y el nombre:
   ```bash
   openssl genrsa -out vexa.key 2048
   openssl req -new -key vexa.key \
     -subj "/C=AR/O=TU NOMBRE/serialNumber=CUIT 20123456789/CN=vexa" \
     -out vexa.csr
   ```
   Te quedan `vexa.key` (tu **clave privada**, no la compartas) y `vexa.csr`.
4. **Pedí el certificado en ARCA**: con tu Clave Fiscal, en *«Administración de
   Certificados Digitales»*, subí `vexa.csr` y descargá el certificado (`vexa.crt`).
5. **Autorizá el certificado** para el servicio *«Facturación Electrónica»*
   (WSFE) en *«Administrador de Relaciones de Clave Fiscal»*.
6. **Creá el punto de venta** de tipo *«Web Services»* en *«ABM de Puntos de
   Venta»* (es distinto del de *Comprobantes en línea*).
7. **Cargá todo en Vexa** (Configuración → AFIP): certificado, clave privada,
   punto de venta y entorno; tocá **«Probar conexión»**.
8. En cada factura, usá **«Autorizar en AFIP»**: se pide el CAE y se agrega el QR.

> Notas: la clave `.key` debe quedar **sin contraseña**; el CUIT del certificado
> tiene que ser el **mismo** que el de *Datos de la empresa*. La arquitectura es
> enchufable (`vexa_core/fiscal/`), así que el resto de la app no depende de AFIP: sin
> configurar, los documentos salen como no fiscales, igual que antes.

## Roadmap

El plan de evolución hacia un facturador vendible (white-label, import flexible,
talles, facturación electrónica AFIP) vive en [`ROADMAP.md`](ROADMAP.md), con el
estado de cada ítem (hecho / pendiente).

---

## Licencia

Software **propietario** — todos los derechos reservados. Ver [`LICENSE`](LICENSE).
No está permitido copiar, distribuir ni modificar el código sin autorización
previa y por escrito del titular.
