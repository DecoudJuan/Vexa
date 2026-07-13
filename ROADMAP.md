# Roadmap — Facturación

Estado de cada ítem: `[x]` hecho · `[~]` en curso · `[ ]` pendiente.
Este documento se mantiene al día a medida que se avanza.

## Visión
Llevar la app (hoy funcional para uso interno, **licencia de escritorio**) a un
**facturador vendible a cualquier negocio**.

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
- [ ] Falta: abrir el PR + merge a main.
- Nota: si se mapea `talle`, por ahora se agrega al nombre; pasa a campo propio
      en la Fase 3.

## Fase 3 — Talles como variantes
- [ ] Esquema: `talle` como columna de `conceptos` o tabla de variantes.
- [ ] Import / listado / selección con talle; backfill desde el nombre.

## Fase 4 — Facturación electrónica AFIP/ARCA (comprobante con CAE)
- [ ] Módulo fiscal enchufable: **WSAA** + **WSFE** reusando librería existente
      (`pyafipws` / `afip` / SDK), no SOAP a mano.
- [ ] CAE, tipos A/B/C, punto de venta, alícuotas de IVA; **QR AFIP** en el PDF.
- [ ] Prerequisitos externos: certificado del contribuyente + punto de venta WS +
      homologación antes de producción.

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
