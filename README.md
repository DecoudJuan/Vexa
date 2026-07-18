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
| UI (escritorio) | PySide6 (Qt 6) — CSS/QSS propio, tema claro/oscuro |
| UI (mobile)     | Flet (Flutter en Python) — Android/escritorio, tema claro/oscuro |
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
│       ├── clientes.py  conceptos.py  documentos.py  etiquetas.py  configuracion.py
│       ├── modal.py  widgets.py  anim.py  styles.py  icons.py
│
├── mobile/                       # ← app MOBILE Flet (Fase 6.2, spike 6.2a en curso)
│   ├── pyproject.toml            # config de flet build (org com.vexa, deps del core)
│   ├── scripts/vendor_core.py    # copia vexa_core → src/ para `flet build` (Android)
│   └── src/
│       ├── main.py               # app Flet: barra inferior, splash, 4 secciones
│       ├── plataforma.py         # adaptación por plataforma (compartir/abrir PDF)
│       └── vexa_core/            # copia vendorizada del core (gitignoreada)
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

## App mobile (Flet) — Fase 6.2

La app Android vive en `mobile/` y reusa el mismo `vexa_core`. UI con **Flet**
(Flutter en Python), offline, con la identidad de Vexa (azul plano). Estructura modular
(`theme/logo/widgets/seed/app/views`), barra inferior de 5 tabs (Clientes · Productos ·
**Inicio** · Etiquetas · Facturas) e Inicio tipo dashboard. **CRUD completo offline**
(clientes, productos, facturas y datos de empresa; import Excel/CSV; ver/compartir PDF;
etiquetas). Además: **onboarding de primera ejecución**, **página AFIP** con tutorial ARCA,
selectores full-screen (el **cliente se autocrea** si no existe, producto con opción **"Otro"**
de texto libre), nav con pastilla deslizante, **marquee** de nombres largos (se desliza al
mantenerlo apretado, hasta el último carácter) y **compartir/imprimir** el PDF por el share
sheet nativo (con fallback a guardar).

**Tests.** Suite de **119 tests** en `mobile/tests/` (`cd mobile && python -m pytest`): e2e
headless de lógica de vista + **35 escenarios BDD (Gherkin, `pytest-bdd`)** en
`tests/features/*.feature` que cubren cada feature (clientes, productos, facturación,
etiquetas, importación, onboarding, empresa y AFIP). Además hay un **E2E visual tipo Cypress**
con **Appium** sobre el APK en un emulador (`mobile/e2e_visual/`): recorre las pantallas y
saca screenshots para revisar regresiones visuales.

**Arranque optimizado**: `reportlab`/`openpyxl` se importan de forma perezosa (no en el cold
start), y una base **pre-cargada** opcional (`mobile/src/seed_data.db`) hace que la app arranque
directamente con datos y saltee el onboarding.

### Instalar en el celular (Android)

1. Descargá el **APK** desde la [última release](../../releases/latest). Para un celular moderno
   usá el **`vexa-mobile-arm64-v8a.apk`** (~60 MB); si tu teléfono es viejo (32-bit) usá
   `vexa-mobile-armeabi-v7a.apk`. Está adjunto (o dentro del `.zip` de la release).
2. Pasalo al teléfono (cable, Drive, WhatsApp Web…) o descargalo directo desde el celular.
3. En Android, la primera vez te va a pedir permitir **"Instalar apps de fuentes desconocidas"**
   para el navegador/gestor de archivos que uses. Activalo.
4. Tocá el APK → **Instalar**. Al abrir por primera vez arranca el **onboarding** (cargás los
   datos de tu empresa) y listo. Al generar un PDF se abre el **compartir/imprimir** del sistema
   (WhatsApp, Drive, Imprimir…); si tu equipo no lo soporta, cae a **guardar** el archivo.

### Correr en escritorio (iteración rápida)

```bash
pip install flet flet-desktop
cd mobile
flet run src/main.py
```

### Correr los tests

Los tests son **headless** (no necesitan emulador ni ventana Flet):

```bash
cd mobile
pip install pytest pytest-bdd        # dependencias de test
python -m pytest                     # corre los 119 tests
```

Variantes útiles:

```bash
python -m pytest -v                              # detalle de cada test / escenario
python -m pytest tests/test_bdd_facturas.py      # solo un feature (BDD)
python -m pytest -k borrar                        # filtrar por nombre
```

Los **escenarios BDD (Gherkin)** están en `tests/features/*.feature` y sus pasos en
`tests/test_bdd_*.py`; los pasos compartidos y la fixture `context` viven en `tests/conftest.py`.

> **En Windows**, si ves un `UnicodeEncodeError` en la consola, exportá `PYTHONUTF8=1`.

**E2E visual (Appium, opcional):** corre sobre el APK en un emulador y saca screenshots de
cada pantalla para revisar regresiones visuales. Requiere un emulador x86_64 + server Appium;
instrucciones completas en [`mobile/e2e_visual/README.md`](mobile/e2e_visual/README.md).

### Buildear el APK vos mismo

`flet build` instala las dependencias con pip para el target y **no** resuelve rutas
locales, así que primero se **vendoriza** el core dentro de `src/` (queda gitignoreado):

```bash
pip install flet uv
python mobile/scripts/vendor_core.py          # copia vexa_core → mobile/src/vexa_core
cd mobile
flet build apk --split-per-abi                # un APK por arquitectura (~60 MB c/u)
flet build apk --arch arm64-v8a               # una sola ABI (queda como build/apk/vexa-mobile.apk)
# o un único APK "fat" (~153 MB, instala en cualquier ABI): flet build apk
```

Requiere el toolchain de Android: Flutter, JDK 17, Android SDK (con `cmdline-tools`
y licencias aceptadas). Los APK quedan en `mobile/build/apk/` (`vexa-mobile-arm64-v8a.apk`,
`vexa-mobile-armeabi-v7a.apk`, `vexa-mobile-x86_64.apk` con `--split-per-abi`). La base SQLite
en Android vive en el storage privado de la app (`FLET_APP_STORAGE_DATA`), que `main.py`
mapea a `FACTURACION_DATA_DIR` antes de importar el core.

> **En Windows**: exportá `PYTHONUTF8=1` antes de `flet build`, si no `flet` crashea al
> arrancar por un `UnicodeEncodeError` de `rich` en la consola (sin haber compilado nada).

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
