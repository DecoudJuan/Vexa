# Roadmap — Facturación

Estado de cada ítem: `[x]` hecho · `[~]` en curso · `[ ]` pendiente.
Este documento se mantiene al día a medida que se avanza.

## Visión
Llevar la app (hoy funcional para uso interno, **licencia de escritorio**) a un
**facturador vendible a cualquier negocio**.

## Lo que queda (resumen 2026-09-29)
Estado del rework de escritorio: **completo** (6.0b solo Facturas, 6.1b Etiquetas,
6.1c rework visual). Lo pendiente:
- **Escritorio — Fase 5 (pulido, en curso)**: corrección de bugs de uso real y ajustes
  finos de UX/UI. Hecho en **v2.9.10**: paridad con mobile, estilo Fusion + selección por QSS,
  contraste en modo oscuro, cola de etiquetas con nombres completos (ver 6.2k).
- **Escritorio — Transversal**: licenciamiento/activación + empaquetado por marca
  (nombre/ícono/publisher configurables) para vender white-label.
- **Gated por AFIP (Fase 4)**: test en vivo contra homologación/producción (necesita
  certificado + punto de venta habilitado). Futuro: `.pfx`, percepciones, monedas ≠ ARS.
- **Mobile — EN CURSO** (Flet, offline): 6.2a–6.2e (toolchain, CRUD completo + import Excel,
  onboarding, página AFIP, PDFs a Documentos) · 6.2f (pulido en device + share nativo, v2.9.6) ·
  **6.2g** (fix pantalla negra al borrar, optimización de arranque, base pre-cargada, tests BDD +
  **E2E visual con Appium**, v2.9.7) · **6.2h** (talle visible en la cola de etiquetas + fusión de
  ítems, "A favor" por precio negativo, "Universal"→talle U, **121 tests**) → **hechos, release
  v2.9.8** · **6.2j** (fix precio que se multiplicaba al editarlo + tabs más ágiles, v2.9.9) ·
  **6.2k** (escritorio acoplado a mobile + pulido visual, v2.9.10).
  Luego 6.3 (conexión AFIP en mobile).

## Base (hecho)
- [x] Sin dependencia de Access en runtime: arranca con base vacía y permite
      crear clientes/productos/documentos desde cero.
- [x] Refactor de UI: `ListPage` (base de las pantallas de listado) y
      `DocumentoDialog` sobre `BaseModal` — PR #1.
- [x] Capa de datos con **SQLAlchemy 2.0** (ORM), misma API pública — PR #2.
- [x] Moneda configurable (AR por defecto, USD opcional) y carpeta de datos
      configurable vía `FACTURACION_DATA_DIR`.

## Fase 1 — White-label + onboarding + factura modelo AR
- [x] Quitar hardcodes: `(Hernan)` en `utils/pdf_generator.py`,
      `AppPublisher=ADHER-NEO` en `packaging/installer.iss`, docstring de
      `utils/excel_import.py`.
- [x] **Wizard de primera ejecución** (si no hay empresa configurada): razón
      social, CUIT, condición frente al IVA, Ingresos Brutos, inicio de
      actividades, domicilio, logo, moneda, punto de venta. (AFIP opcional vía
      toggle; los campos fiscales se editan también en Configuración.)
- [x] **PDF con layout de factura argentina**: recuadro con letra (A/B/C/X),
      emisor + condición IVA, receptor + CUIT, IVA discriminado (letra A), pie.
- [x] **Factura simple / no fiscal**: se emite con la leyenda "DOCUMENTO NO
      VÁLIDO COMO FACTURA" hasta integrar AFIP (Fase 4), con el mismo layout.

## Fase 2 — Import flexible (mapeo de columnas)  ← HECHO (rama `fase2-import-flexible`)
- [x] Lector con mapeo configurable (`nombre`/`precio`/`codigo`/`talle`) +
      auto-detección de encabezados. Soporta **.xlsx/.xlsm y CSV** (detecta
      separador). `utils/excel_import.py` reescrito (listar_hojas, leer_hoja,
      sugerir_mapeo, filas_a_items).
- [x] Diálogo de importación (`ui/import_dialog.py`) con selector de hoja,
      mapeo de columnas (combos con auto-sugerencia) y **vista previa**.
- [x] **Perfiles por proveedor**: guardar/aplicar/eliminar un mapeo con nombre.
      Se guarda por **nombre de columna** (no índice) para tolerar cambios de
      orden entre planillas del mismo proveedor; persiste en `Configuracion`
      (JSON, clave `import_perfiles`) vía `db.get/save/delete_perfil_import`.
- [x] Probado con planilla real (encabezado con membrete, filas `* CONSULTAR`
      descartadas, precio con coma decimal, reaplicar perfil).
- [x] Mergeado a main (junto con Fase 3) y liberado en release `v2.3.1`.
- Nota: si se mapea `talle`, por ahora se agrega al nombre; pasa a campo propio
      en la Fase 3.

## Fase 3 — Talles como variantes  ← HECHO (opción A: columna en `conceptos`)
- [x] Esquema: `talle` como **columna de `conceptos`** (ALTER idempotente). La
      identidad de variante pasa a ser `(nombre, talle)` en `upsert_conceptos`.
- [x] Import (columna `talle` en su campo, ya no pegada al nombre) y PDF con
      talle (`etiqueta_concepto` + JOIN de `get_lineas`).
- [x] **Producto agrupado**: en el listado el producto aparece **una sola vez**
      con una columna Talles (`db.get_productos` agrupa por nombre+código); el
      alta/edición maneja los talles como conjunto (`save_producto` reconcilia
      variantes). En la factura se elige **producto y luego talle** (combo
      dependiente que resuelve la variante). Import con opción **Reemplazar
      catálogo** (vacía antes de importar, sin duplicados).
- [x] Borrado seguro: al eliminar un producto se congela su nombre en las
      líneas que lo usan (`_snapshot_concepto_en_lineas`), así las facturas
      viejas no pierden el detalle (la FK es ON DELETE SET NULL).
- [x] Backfill desde el nombre: `separar_codigo_talle()` extrae `060/1`/`T1` en
      una sola pasada junto con el código, sin perder el talle al limpiar.
- Nota: como con el código (Fase previa), los productos existentes cuyo nombre
      ya venía limpio recién toman talle al **reimportar** la lista con la
      columna de talle mapeada. Retrocompatible: reimport sin talle actualiza por
      nombre como antes; las facturas viejas rinden igual (talle vacío no se
      muestra).
- Descartado por ahora: tabla de variantes separada (opción B) — implicaría
      reapuntar las líneas de factura históricas; no aporta lo suficiente hoy.

## Fase 4 — Facturación electrónica AFIP/ARCA (comprobante con CAE)  ← ANDAMIAJE HECHO (release v2.4.0)
- [x] **Módulo fiscal enchufable** (`app/fiscal/`): interfaz `FiscalProvider` +
      `NoFiscalProvider` (offline, comportamiento actual) + `get_provider(db)` como
      único punto de acoplamiento. Decisión: **wrapper propio** con `zeep` (SOAP) +
      `cryptography` (firma CMS del ticket), sin dependencias GPL, offline. No pyafipws.
- [x] **WSAA**: `LoginTicketRequest` firmado en CMS/PKCS#7, `loginCms`, cacheo del
      TA (~12 h) en `DATA_DIR/afip/`.
- [x] **WSFEv1**: `FECompUltimoAutorizado` + `FECAESolicitar`; tipos A/B/C (factura y
      nota de crédito), DocTipo/DocNro del receptor, ImpNeto/ImpIVA/alícuota, CAE + vto.
- [x] **QR AFIP** en el PDF (spec RG 4291) con el generador nativo de reportlab (sin
      dep nueva); CAE + vencimiento en el pie. La leyenda "no válido" desaparece sola
      cuando hay CAE.
- [x] Esquema: columnas `cae`, `cae_vto`, `afip_resultado`, `afip_qr` en `facturas`
      (ALTER idempotente) + `db.guardar_cae`.
- [x] Config (Configuración → AFIP): entorno (homologación/producción), certificado y
      clave privada (.crt/.key), botón **Probar conexión**. Acción **Autorizar en AFIP**
      en el listado de facturas/abonos.
- [x] Verificado sin cert: QR (unit), firma CMS (cert autofirmado), migración, PDF con
      CAE simulado, alta/guardado de config.
- [ ] **Pendiente (gated por AFIP)**: test en vivo contra homologación/producción.
      Prerequisitos externos: **certificado del contribuyente + punto de venta WS +
      homologación** antes de producción.
- [ ] Futuro: certificados `.pfx`, percepciones/otros tributos, monedas ≠ ARS.

## Fase 5 — Pulido de bugs + UX/UI  ← EN CURSO
Fase dedicada a la experiencia de uso, a abrir después de liberar la Fase 4.
Liberado hasta ahora: pantalla de inicio + animaciones (v2.5.0), guard de cambios
sin guardar + barra de selección deslizante (v2.6.0).
- [x] **Pantalla de inicio** (`ui/home.py`): al abrir, tarjetas de acceso a las 4
      secciones con íconos grandes; la barra lateral aparece recién al elegir una
      (y se vuelve al inicio tocando el logo/marca). Logo de marca (símbolo V)
      adaptable al tema en sidebar e inicio.
- [x] **Animaciones** (`ui/anim.py` + integración): arranque con la V que se
      desplaza al lugar del logo revelando las tarjetas; slide-in de la barra
      lateral; indicador deslizante del ítem activo (sidebar) y de las solapas
      (Configuración/Documentos); fade al cambiar de sección; apertura de modales
      con fade + deslizamiento.
- [x] Consistencia de datos/docs: `CHECK` de `facturas.tipo` derivado de
      `TIPOS_DOCUMENTO`; README al día con el código.
- [x] **Cambios sin guardar**: al cerrar un diálogo de edición (cliente/producto/
      factura) con cambios, confirma antes de descartar (Escape/Cancelar/X).
- [x] ~~**Selección de fila deslizante**~~: la barra animada casera se **quitó en v2.9.10** (dejaba
      filas pintadas al cambiar rápido). Hoy la selección la pinta Qt por QSS (`ui/anim.ListTable`,
      estilo Fusion).
- [x] **Paridad con mobile** (rama `feat/desktop-paridad-mobile`): reglas de factura en el core
      (`vexa_core/utils/facturas.py`: totales, "a favor", **bloqueo de precio 0**); bonificación
      siempre del cliente; cliente nuevo creado solo al guardar una factura válida; CUIT de
      clientes con formateo en vivo (sin duplicados); aviso de soft-delete al borrar un cliente
      con facturas; talles con `,` o `;`; "En la última hoja" en etiquetas; total emitido en el
      listado de facturas. Suite a **148 tests**.
- [ ] Corrección de bugs reportados en el uso real.
- [ ] Más mejoras de UI/UX (accesibilidad, flujos).
- Ya adelantado en v2.4.0 (entra con Fase 4): teléfono libre con código de país/área
      (placeholder `+54 9 11 5555-5555`), domicilio separado en Calle/Número (empresa),
      vista previa del import agrupada por producto (talles juntos), popups/QMessageBox
      sin fondo negro en Windows con tema oscuro, selección de filas en azul tenue,
      guía "¿Cómo conectarme con ARCA?".

## Fase 6 — App Android (Flet) + monorepo con core compartido  ← EN CURSO
Llevar Vexa a una **APK Android** descargable, responsive y sin perder funcionalidad,
manteniendo también el escritorio. Framework mobile elegido: **Flet** (UI Flutter en
Python, buildea APK desde Windows, soporta cryptography+lxml+pillow). El core ya es
Qt-free y reutilizable. Repo pasa a monorepo y se renombra a **`Vexa`**.

- [x] **Pre-paso**: quitar la leyenda "DOCUMENTO NO VÁLIDO COMO FACTURA" del PDF
      (`utils/pdf_generator.py`).
- [x] **Fase 6.1 — Monorepo + `vexa_core`** (liberado v2.6.1): core extraído a
      `vexa_core` (paquete instalable); UI de escritorio en `desktop/`; imports a
      `vexa_core.*`; `.spec`/`installer.iss` actualizados; escritorio verificado.

- [x] **Fase 6.0b — Reducir a solo Facturas (escritorio)**: `TIPOS_DOCUMENTO=("FA",)`;
      Documentos pasa a **"Facturas"** (sin solapas PR/PE, sin resumen KPI ni columna
      Origen). (Mobile hereda el core; su UI se hace en la fase mobile.)

- [x] **Fase 6.1b — Nueva sección "Etiquetas" (escritorio)**: generador con
      **catálogo = productos de Vexa** (buscar producto → talles + cantidad → cola →
      hoja A4 de 14 etiquetas, se abre para imprimir). Core en `vexa_core/utils/etiquetas.py`
      (agnóstico de plataforma, para reusar en mobile). En la sidebar tras Facturas.
      (Grilla de inicio / pestaña mobile: cuando se haga la fase mobile.)

- [x] **Fase 6.1c — Rework visual del ESCRITORIO** (diseño "Vexa Rework"): paleta nueva
      (azul liso `#2f5bea`, **sin degradés**), **Inicio tipo dashboard** (saludo + KPIs +
      facturas recientes + accesos), **sidebar siempre visible** con Inicio como ítem del nav,
      fuente del sistema (Segoe UI). Detalle en `desktop-rework.local.md`.

- [~] **Fase 6.2 — Mobile offline (Flet)**: carpeta `mobile/` que consume `vexa_core`
      (framework **Flet 0.86**), estructura modular (`theme/logo/widgets/seed/app/views`).
      Diseño: **barra inferior** de 5 tabs (Clientes · Productos · **Inicio** central circular ·
      Etiquetas · Facturas), Inicio = dashboard (KPIs + facturas recientes + accesos rápidos),
      **azul plano**, tema claro/oscuro (switch en Configuración). Estado:
  - [x] **6.2a — Spike/toolchain**: Android SDK completo (Flutter 3.44.6 + JDK/JBR +
        cmdline-tools + licencias + `uv`); **`flet build apk` OK e instalado en emulador**;
        reportlab validado. El core se **vendoriza** a `mobile/src/vexa_core`
        (`scripts/vendor_core.py`) antes de buildear (flet build usa pip --target y no resuelve
        rutas locales; había un `vexa-core` ajeno en PyPI).
  - [x] **6.2b — CRUD offline (paridad con desktop)**: alta/edición/borrado de **Clientes**
        (todos los campos, **CUIT/CUIL múltiples** con formateo en vivo, provincia editable),
        **Productos** (+ **import Excel/CSV** con FilePicker + mapeo), **Facturas** (líneas
        dinámicas, cliente/producto escribibles, bonificación, edición) y **Datos de empresa**.
        Ver/compartir PDF y generar etiquetas. Forma de pago quitada de cliente/factura (no se
        usa en PDF ni AFIP). Verificado corriendo en escritorio (`flet run`, ventana celular).
  - [x] **Onboarding de primera ejecución** (`mobile/src/onboarding.py`): si no hay empresa
        (nombre vacío) y no está la flag `onboarding_done`, se muestra en vez de sembrar el demo.
        Bienvenida con la V que **sube con transición** + botón **"Comenzar"** que aparece abajo →
        form **idéntico al de escritorio** ("Guardar y empezar"). El form de empresa se unificó
        (onboarding y Configuración usan el mismo set de campos que desktop: nombre, CUIT con
        formateo en vivo, condición IVA, Calle/Número, localidad/provincia, teléfono/email, moneda
        y **bloque AFIP opcional** con checkbox → punto de venta/ingresos brutos/inicio actividades).
  - [x] **6.2e — Pulido UX + página AFIP + PDFs a Documentos + tests** (release **v2.9.0**):
        **Página AFIP** propia (`views/afip.py`, subpágina full-screen con datos fiscales +
        tutorial ARCA deslizable). **Import** pasa a **subpágina** (arregla la pantalla negra).
        **Selector de provincia** en hoja inferior (abre hacia abajo, no tapa el input) y
        **selectores full-screen en factura**: cliente **se autocrea** si no existe, producto
        con opción **"Otro"** (texto libre). **Nav con pastilla azul deslizante** + **slide de
        contenido** entre secciones (animación determinística). **Marquee** de nombres largos
        (scroll real, revela todo). **Render diferido** al cerrar (arregla pantalla negra al
        guardar factura/cliente), **confirmación de borrado** (banner rojo), aviso de **precio 0**.
        **PDFs (facturas/etiquetas) van a la carpeta Documentos** del dispositivo. Header fijo +
        solo la lista scrollea; barras de scroll ocultas; form de producto a media pantalla.
        **Suite de 83 tests** headless (`mobile/tests/`, pytest). Detalle en `mobile-roadmap.local.md`.
  - [x] **6.2f — Pulido en device (emulador Vexa35) + share nativo** (release **v2.9.6**):
        **Marquee resuelto** — el nombre largo se desliza suave hasta el último carácter sin
        chocar con el swipe de pestañas (`Text` posicionado en un `Stack` → render completo, se
        mide el ancho real con `on_size_change` y se anima `left` numérico). **Confirmación de
        borrado** a pantalla completa (dim) sobre el form. **PDF por el share sheet nativo**
        (`ft.Share.share_files`: WhatsApp/Imprimir/Drive), con **fallback a guardar** si el share
        no responde. **"Agregar otro talle"** a todo el ancho. **Factura arranca sin cliente**.
        **Borrar cliente con facturas** → soft-delete (conserva el nombre en el comprobante).
        Verificado instalando el APK en el emulador Android (Vexa35, x86_64).
  - [x] **6.2g — Fix borrado + optimizaciones + tests BDD + E2E visual** (release **v2.9.7**):
        **Fix pantalla negra al borrar** (cliente/producto): se secuencian los cierres de los
        diálogos (la confirmación se cierra y recién en su `on_dismiss` se cierra el form y se
        renderiza) para no dejar dos scrims desmontándose a la vez. **Optimización de arranque**:
        `reportlab`/`openpyxl` con import perezoso (fuera del cold start) + `PRAGMA
        synchronous=NORMAL`. **Base pre-cargada** opcional (`src/seed_data.db`) → arranca con datos
        y saltea el onboarding. **Suite a 119 tests**: e2e de vista + **35 escenarios BDD (Gherkin,
        `pytest-bdd`)** por feature. **E2E visual tipo Cypress** con **Appium** sobre el APK en el
        emulador (`mobile/e2e_visual/`): recorre pantallas y saca screenshots.
  - [x] **6.2h — Etiquetas/facturas: talle visible, "A favor" y catálogo** (release **v2.9.8**):
        en la **cola de etiquetas** el talle se muestra entre paréntesis (`(T1)`, y `(U)` para
        Universal) debajo del nombre, a la izquierda del código (mobile y desktop); **agregar el
        mismo producto+talle** varias veces **fusiona** en una sola línea sumando la cantidad.
        En **facturas** se admite **precio negativo** como línea **"A favor"** (crédito que resta
        del total, marcado en pantalla y en el PDF). **"Universal"** en la lista de precios se toma
        como **talle "U"** (import + backfill en `init_db`). Correcciones puntuales de catálogo
        idempotentes en `init_db` (`_correcciones_catalogo`): pulgar 046 y fajas alta compresión
        24CM→624 / 28CM→628. Suite a **121 tests**.
  - [~] **6.2i — Performance mobile** (reducir el lag en dispositivos): listas migradas de
        `ft.Column(scroll)` a **`ft.ListView`** (virtualizado: solo construye/pinta lo visible) en
        Productos/Facturas/Clientes — abarata el scroll y el `build()` de cada tab; **debounce** de
        ~250 ms en los buscadores (no reconstruir la lista en cada tecla). El marquee ya corre solo
        en el ítem que se mantiene apretado. Pendiente/futuro: evitar el rebuild completo del árbol
        en `render()` al cambiar de tab (cachear/alternar vistas) — diferido por el fix delicado de
        pantalla negra; medir antes.
  - [x] **6.2j — Fix precio ×10ⁿ + cambio de pestañas más ágil** (release **v2.9.9**): el form
        precargaba `14000.0` y al guardar borraba todos los puntos (como miles) → cada edición
        sumaba ceros. Ahora los números se precargan en es-AR (`fmt_num_input`: `14000`,
        `14000,5`) y se leen con `parse_float`, que además toma `14.500` / `1.234.567` como miles.
        Perf: el marquee ya no manda un evento de tamaño por fila al montarse (trababa el puente
        Flutter↔Python al entrar a cada lista) y la transición de tab es más corta y arranca
        semi-visible. Suite a **142 tests** (regresión del precio vía form real).
  - [x] **6.2k — Escritorio acoplado a mobile + pulido visual**: paridad de reglas de factura/clientes/
        etiquetas (core `utils/facturas.py`); sin forma de pago ni columna saldo; números es-AR
        (`parse_float`/`fmt_num_input`). Visual: estilo **Fusion** + selección por QSS (reemplaza el
        delegate/banda animada casera que dejaba filas pintadas), combo sin borde cortado, cola de
        etiquetas en `QScrollArea` con nombres en 2+ líneas, contraste en oscuro (`faint_tx`),
        filas de talle más compactas e Inicio sin el botón "Nueva factura" de arriba (queda en
        accesos rápidos). Suite a **148 tests**. Release **v2.9.10**.
  - [ ] **Menores**: líneas de texto libre "sueltas" en factura (ya cubierto por "Otro"),
        Guardado (logo/pie de PDF), share nativo del PDF a afinar en device real (hoy cae a guardar).
        Detalle en `mobile-roadmap.local.md`.
- [ ] **Fase 6.3 — AFIP en mobile** (viable — verificado 2026-07-17): `cryptography` y `lxml` ya
      están **prebuilt para Android** en el índice de Flet (pypi.flet.dev) y `zeep` es pure-Python,
      así que no hay bloqueo de wheels nativas. Trabajo: agregarlas al build + permiso INTERNET,
      cert/key vía FilePicker, reactivar "Autorizar en AFIP" y solapa AFIP, QR fiscal + CAE, y
      confirmar con un APK real contra homologación.

## Transversal
- [x] **CI (GitHub Actions)**: corre la suite de tests (pytest + pytest-bdd) en cada push/PR
      (`.github/workflows/ci.yml`). No buildea la APK firmada (necesita el keystore fuera del repo).
- [ ] Licenciamiento / activación de escritorio + empaquetado por marca
      (nombre/ícono/publisher configurables).

## Tracks
- **Track A** (sin dependencias externas, accionable ya): Fase 1 + Fase 2 +
  factura simple.
- **Track B** (gated por el certificado de AFIP): Fase 4.
- **Fase 3** se intercala cuando se decida.

## Cómo trabajamos
- Se mantiene este `ROADMAP.md` al día (ejecutado/pendiente).
- Se actualiza el `README.md` ante cambios de estructura / stack / uso.
- Commits chicos, por rama y PR.
