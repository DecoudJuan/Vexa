# Roadmap — Facturación

Estado de cada ítem: `[x]` hecho · `[~]` en curso · `[ ]` pendiente.
Este documento se mantiene al día a medida que se avanza.

## Visión
Llevar la app (hoy funcional para uso interno, **licencia de escritorio**) a un
**facturador vendible a cualquier negocio**.

## Lo que queda (resumen 2026-07-15)
Estado del rework de escritorio: **completo** (6.0b solo Facturas, 6.1b Etiquetas,
6.1c rework visual). Lo pendiente:
- **Escritorio — Fase 5 (pulido, en curso)**: corrección de bugs de uso real y ajustes
  finos de UX/UI (colores, selección de fila, etc.).
- **Escritorio — Transversal**: licenciamiento/activación + empaquetado por marca
  (nombre/ícono/publisher configurables) para vender white-label.
- **Gated por AFIP (Fase 4)**: test en vivo contra homologación/producción (necesita
  certificado + punto de venta habilitado). Futuro: `.pfx`, percepciones, monedas ≠ ARS.
- **Mobile — DIFERIDO por decisión del usuario** (se retoma después): Fase 6.2 (app
  Android en Flet, offline) y 6.3 (AFIP en mobile). El core `vexa_core` ya está listo
  para reusar.

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
- [x] **Selección de fila deslizante**: la barra de selección se desliza de una
      fila a otra en los listados (`ui/anim.RowHighlight`).
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

- [ ] **Fase 6.2 — Mobile offline (Flet)**: carpeta `mobile/` que consume `vexa_core`.
      Diseño acordado (mockup navegable, ver `mobile-roadmap.local.md`): **barra inferior
      estilo Clash Royale** con Clientes/Productos/Etiquetas/Facturas (ítem activo
      elevado); **Configuración** = ruedita arriba a la derecha (con switch claro/oscuro
      adentro); **splash** de la V con fade → abre directo en **Etiquetas**; **animaciones
      direccionales** al cambiar de pestaña; **Clientes** sin saldo/chips (solo el cliente);
      **azul estático** (sin degradés). Spike técnico (Flet + DB + PDF en dispositivo;
      validar reportlab, plan B fpdf2+qrcode). Adaptaciones Android (compartir PDF, 
      `FilePicker`, `FACTURACION_DATA_DIR` → storage). `flet build apk` y entregar APK.
- [ ] **Fase 6.3 — AFIP en mobile**: `cryptography`+`lxml`+`zeep` en el build; reactivar
      "Autorizar en AFIP" y solapa AFIP (cert/key vía FilePicker); QR fiscal + CAE.

## Transversal
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
