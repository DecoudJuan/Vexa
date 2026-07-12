"""Migración única desde el back-end Access legacy (datos.mdb) a la nueva base SQLite.

No depende de ODBC ni de tener MS Access instalado: usa `access_parser`
(librería Python pura que lee el formato binario .mdb directamente), porque
esta máquina solo tiene el driver ODBC de 32 bits y Python de 64 bits.

Uso:
    python -m database.migration --source "C:\\ruta\\datos.mdb" [--force]

Este script NO se empaqueta en el ejecutable final: es una herramienta de
desarrollo que se corre una sola vez para poblar la base SQLite nueva.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from access_parser import AccessParser

from database.db import DatabaseManager, DEFAULT_DB, _SCHEMA

import sqlite3


def _none_if_blank(v):
    if v is None:
        return None
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


def _to_float(v) -> float:
    """Access a veces guarda campos numéricos como texto con coma decimal
    (formato argentino, ej. '25341,73' con o sin separador de miles '.')."""
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _bool_to_int(v) -> int:
    """Access Yes/No: True/-1 = verdadero, False/0 = falso."""
    if v in (True, -1):
        return 1
    return 0


def _split_tipo_ejercicio(fact_tipo: str) -> tuple[str, int]:
    """'PR24' -> ('PR', 2024). Si no matchea el patrón, año actual y tipo crudo."""
    fact_tipo = (fact_tipo or "").strip()
    prefijo = fact_tipo[:2].upper()
    resto = fact_tipo[2:]
    if prefijo not in ("FA", "PR", "AL", "PE", "AB"):
        return "FA", 2000
    try:
        yy = int(resto)
        ejercicio = 2000 + yy if yy < 100 else yy
    except ValueError:
        ejercicio = 2000
    return prefijo, ejercicio


class MigrationReport:
    def __init__(self):
        self.counts: dict[str, int] = {}
        self.warnings: list[str] = []

    def add(self, table: str, n: int):
        self.counts[table] = n

    def warn(self, msg: str):
        self.warnings.append(msg)

    def print_summary(self):
        print("\n=== Resumen de migración ===")
        for table, n in self.counts.items():
            print(f"  {table}: {n} filas migradas")
        if self.warnings:
            print(f"\n  {len(self.warnings)} advertencias:")
            for w in self.warnings[:50]:
                print(f"    - {w}")
            if len(self.warnings) > 50:
                print(f"    ... y {len(self.warnings) - 50} más")


def run_migration(access_path: str, sqlite_path: str | None = None, force: bool = False) -> MigrationReport:
    sqlite_path = sqlite_path or str(DEFAULT_DB)
    report = MigrationReport()

    db = DatabaseManager(sqlite_path)
    db.init_db()

    with sqlite3.connect(sqlite_path) as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.row_factory = sqlite3.Row

        already = conn.execute(
            "SELECT valor FROM configuracion WHERE clave = 'migration_completed_at'"
        ).fetchone()
        if already and not force:
            print(
                f"La migración ya se corrió el {already['valor']}. "
                "Usá --force para volver a migrar (esto borra y recarga todas las tablas)."
            )
            return report

        print(f"Abriendo {access_path} ...")
        src = AccessParser(access_path)
        tablas_esperadas = {
            "Clientes", "Conceptos", "DatosEmpresa", "Factura", "FormaPago",
            "Iva", "Lineas", "Recibos", "Remesas", "Suplidos",
        }
        tablas_reales = set(src.catalog.keys())
        extra = tablas_reales - tablas_esperadas - {
            t for t in tablas_reales if t.startswith("MSys")
        }
        for t in extra:
            report.warn(f"Tabla inesperada encontrada en el .mdb (ignorada): {t}")

        # Borrado + recarga completa (migración idempotente, no incremental).
        conn.execute("BEGIN")
        for tabla in (
            "recibos", "suplidos", "lineas", "facturas", "remesas",
            "conceptos", "clientes", "forma_pago", "iva",
        ):
            conn.execute(f"DELETE FROM {tabla}")

        # ------------------------------------------------------------- DatosEmpresa
        empresa = src.parse_table("DatosEmpresa")
        if empresa and empresa.get("datos_nombre"):
            conn.execute(
                """UPDATE datos_empresa SET
                   nombre=?, nif=?, direccion=?, cp=?, localidad=?, provincia=?,
                   telefono=?, fax=?, email=?, web=?, iva_defecto=?, iva_texto=?,
                   moneda=?, sufijo=?, pie_pagina=?, ccc1=?, ccc2=?, ccc3=?, ccc4=?,
                   ccce1=?, ccce2=?, legacy_id=1
                   WHERE id = 1""",
                (
                    _none_if_blank(empresa["datos_nombre"][0]),
                    _none_if_blank(empresa["datos_nif"][0]),
                    _none_if_blank(empresa["datos_direccion"][0]),
                    _none_if_blank(empresa["datos_cp"][0]),
                    _none_if_blank(empresa["datos_localidad"][0]),
                    _none_if_blank(empresa["datos_provincia"][0]),
                    _none_if_blank(empresa["datos_telefono"][0]),
                    _none_if_blank(empresa["datos_fax"][0]),
                    _none_if_blank(empresa["datos_email"][0]),
                    _none_if_blank(empresa["datos_web"][0]),
                    _to_float(empresa["datos_iva"][0]) or 21.0,
                    _none_if_blank(empresa["datos_txtiva"][0]) or "IVA",
                    _none_if_blank(empresa["datos_moneda"][0]) or "$",
                    _none_if_blank(empresa["datos_sufijo"][0]),
                    _none_if_blank(empresa["datos_abajo"][0]),
                    _none_if_blank(empresa["datos_CCC1"][0]),
                    _none_if_blank(empresa["datos_CCC2"][0]),
                    _none_if_blank(empresa["datos_CCC3"][0]),
                    _none_if_blank(empresa["datos_CCC4"][0]),
                    _none_if_blank(empresa["datos_CCCE1"][0]),
                    _none_if_blank(empresa["datos_CCCE2"][0]),
                ),
            )
            report.add("datos_empresa", 1)

        # ------------------------------------------------------------------------ Iva
        iva_map: dict[int, int] = {}
        iva_data = src.parse_table("Iva")
        n = len(iva_data.get("iva_id", []))
        for i in range(n):
            legacy_id = iva_data["iva_id"][i]
            cur = conn.execute(
                "INSERT INTO iva (tipo, recargo, activo, legacy_id) VALUES (?, ?, 1, ?)",
                (_to_float(iva_data["iva_tipo"][i]), _to_float(iva_data["iva_rec"][i]), legacy_id),
            )
            iva_map[legacy_id] = cur.lastrowid
        report.add("iva", n)

        # ------------------------------------------------------------------ FormaPago
        forma_pago_map: dict[int, int] = {}
        fp_data = src.parse_table("FormaPago")
        n = len(fp_data.get("formapago_id", []))
        for i in range(n):
            legacy_id = fp_data["formapago_id"][i]
            cur = conn.execute(
                """INSERT INTO forma_pago (tipo, genera_recibo, vto1, vto2, vto3, legacy_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    _none_if_blank(fp_data["formapago_tipo"][i]) or "",
                    _bool_to_int(fp_data["formapago_recibo"][i]),
                    _none_if_blank(fp_data["formapago_vto1"][i]),
                    fp_data["formapago_vto2"][i] if isinstance(fp_data["formapago_vto2"][i], (int, float)) else None,
                    _bool_to_int(fp_data["formapago_vto3"][i]),
                    legacy_id,
                ),
            )
            forma_pago_map[legacy_id] = cur.lastrowid
        report.add("forma_pago", n)

        # ------------------------------------------------------------------- Clientes
        cliente_map: dict[int, int] = {}
        cli_data = src.parse_table("Clientes")
        n = len(cli_data.get("clientes_id", []))
        for i in range(n):
            legacy_id = cli_data["clientes_id"][i]
            comentarios = _none_if_blank(cli_data["clientes_comentarios"][i])
            auto = _none_if_blank(cli_data.get("clientes_comenauto", [None] * n)[i])
            if auto:
                comentarios = f"{comentarios}\n[Auto] {auto}" if comentarios else f"[Auto] {auto}"
            fp_legacy = cli_data["clientes_formapago"][i]
            cur = conn.execute(
                """INSERT INTO clientes
                   (nombre, nif, direccion, cp, localidad, provincia, telefono1, fax,
                    email, persona_contacto, comentarios, forma_pago_id, banco,
                    ccc1, ccc2, ccc3, ccc4, retencion, recargo_equiv, legacy_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    _none_if_blank(cli_data["clientes_nombre"][i]) or f"Cliente {legacy_id}",
                    _none_if_blank(cli_data["clientes_nif"][i]),
                    _none_if_blank(cli_data["clientes_direccion"][i]),
                    _none_if_blank(cli_data["clientes_cp"][i]),
                    _none_if_blank(cli_data["clientes_localidad"][i]),
                    _none_if_blank(cli_data["clientes_provincia"][i]),
                    _none_if_blank(cli_data["clientes_telefono1"][i]),
                    _none_if_blank(cli_data["clientes_fax"][i]),
                    _none_if_blank(cli_data["clientes_email"][i]),
                    _none_if_blank(cli_data["clientes_personacontacto"][i]),
                    comentarios,
                    forma_pago_map.get(fp_legacy),
                    _none_if_blank(cli_data["clientes_banco"][i]),
                    _none_if_blank(cli_data["clientes_CCC1"][i]),
                    _none_if_blank(cli_data["clientes_CCC2"][i]),
                    _none_if_blank(cli_data["clientes_CCC3"][i]),
                    _none_if_blank(cli_data["clientes_CCC4"][i]),
                    _to_float(cli_data["clientes_irpf"][i]),
                    _to_float(cli_data["clientes_rec"][i]),
                    legacy_id,
                ),
            )
            cliente_map[legacy_id] = cur.lastrowid
        report.add("clientes", n)

        # ------------------------------------------------------------------ Conceptos
        concepto_map: dict[int, int] = {}
        conc_data = src.parse_table("Conceptos")
        n = len(conc_data.get("conc_id", []))
        for i in range(n):
            legacy_id = conc_data["conc_id"][i]
            cur = conn.execute(
                "INSERT INTO conceptos (nombre, pvp, legacy_id) VALUES (?, ?, ?)",
                (_none_if_blank(conc_data["conc_nombre"][i]) or f"Concepto {legacy_id}",
                 _to_float(conc_data["conc_pvp"][i]), legacy_id),
            )
            concepto_map[legacy_id] = cur.lastrowid
        report.add("conceptos", n)

        # -------------------------------------------------------------------- Remesas
        remesa_map: dict[int, int] = {}
        rem_data = src.parse_table("Remesas")
        n = len(rem_data.get("remesas_id", []))
        for i in range(n):
            legacy_id = rem_data["remesas_id"][i]
            cur = conn.execute(
                """INSERT INTO remesas (descripcion, fecha, fecha_cargo, fecha_vto, legacy_id)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    _none_if_blank(rem_data["remesas_descripcion"][i]),
                    _none_if_blank(rem_data["remesas_fecha"][i]) or "2000-01-01",
                    _none_if_blank(rem_data["remesas_cargo"][i]),
                    _none_if_blank(rem_data["remesas_vto"][i]),
                    legacy_id,
                ),
            )
            remesa_map[legacy_id] = cur.lastrowid
        report.add("remesas", n)

        # ------------------------------------------------------------------- Factura
        fact_data = src.parse_table("Factura")
        n = len(fact_data.get("fact_id", []))
        factura_map: dict[int, int] = {}
        pending_asociada: dict[int, object] = {}  # nueva_id -> legacy fact_facturaasociada

        for i in range(n):
            legacy_id = fact_data["fact_id"][i]
            cliente_legacy = fact_data["fact_cliente"][i]
            nuevo_cliente_id = cliente_map.get(cliente_legacy)
            if nuevo_cliente_id is None:
                report.warn(f"Factura legacy_id={legacy_id}: cliente {cliente_legacy} no existe, se omite")
                continue

            tipo, ejercicio = _split_tipo_ejercicio(fact_data["fact_tipo"][i])

            origen_tipo = origen_numero = None
            for col, code in (("fact_PR", "PR"), ("fact_AL", "AL"), ("fact_PE", "PE")):
                val = _none_if_blank(fact_data.get(col, [None] * n)[i])
                if val:
                    origen_tipo, origen_numero = code, val
                    break

            fp_legacy = fact_data["fact_formapago"][i]

            cur = conn.execute(
                """INSERT INTO facturas
                   (cliente_id, tipo, ejercicio, numero, fecha, fecha_vencimiento,
                    total, pagado, iva, recargo_equiv, retencion, forma_pago_id,
                    recibo, domicilio_cobro, entrega_a_cuenta, provision, total_suplidos,
                    origen_tipo, origen_numero, momento_generar, pedido_cliente,
                    comentarios, vista, estado, ccc1, ccc2, ccc3, ccc4, legacy_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    nuevo_cliente_id, tipo, ejercicio,
                    _none_if_blank(fact_data["fact_num"][i]),
                    _none_if_blank(fact_data["fact_fecha"][i]) or "2000-01-01",
                    _none_if_blank(fact_data["fact_vto"][i]),
                    _to_float(fact_data["fact_total"][i]),
                    _to_float(fact_data["fact_pagado"][i]),
                    _to_float(fact_data["fact_iva"][i]),
                    _to_float(fact_data["fact_rec"][i]),
                    _to_float(fact_data["fact_irpf"][i]),
                    forma_pago_map.get(fp_legacy),
                    _bool_to_int(fact_data["fact_recibo"][i]),
                    _bool_to_int(fact_data["fact_domiciliocobro"][i]),
                    _to_float(fact_data["fact_entregaacuenta"][i]),
                    _to_float(fact_data["fact_provision"][i]),
                    _to_float(fact_data["fact_totalsuplidos"][i]),
                    origen_tipo, origen_numero,
                    _none_if_blank(fact_data["fact_momengenerar"][i]),
                    _none_if_blank(fact_data["fact_pedidocliente"][i]),
                    _none_if_blank(fact_data["fact_comentarios"][i]),
                    _bool_to_int(fact_data["fact_ver"][i]),
                    "abierto",
                    _none_if_blank(fact_data["fact_CCC1"][i]),
                    _none_if_blank(fact_data["fact_CCC2"][i]),
                    _none_if_blank(fact_data["fact_CCC3"][i]),
                    _none_if_blank(fact_data["fact_CCC4"][i]),
                    legacy_id,
                ),
            )
            nueva_id = cur.lastrowid
            factura_map[legacy_id] = nueva_id
            asociada = fact_data["fact_facturaasociada"][i]
            if asociada not in (None, "", "0", 0):
                pending_asociada[nueva_id] = asociada

        report.add("facturas", len(factura_map))

        # pase 2: resolver auto-referencia factura_asociada_id
        for nueva_id, legacy_asociada in pending_asociada.items():
            try:
                legacy_asociada_int = int(legacy_asociada)
            except (TypeError, ValueError):
                report.warn(f"factura id={nueva_id}: fact_facturaasociada inválido ({legacy_asociada!r})")
                continue
            asociada_nueva = factura_map.get(legacy_asociada_int)
            if asociada_nueva:
                conn.execute(
                    "UPDATE facturas SET factura_asociada_id = ? WHERE id = ?",
                    (asociada_nueva, nueva_id),
                )
            else:
                report.warn(f"factura id={nueva_id}: no se encontró la asociada legacy_id={legacy_asociada}")

        # -------------------------------------------------------------------- Lineas
        lin_data = src.parse_table("Lineas")
        n = len(lin_data.get("linea_id", []))
        migradas = 0
        for i in range(n):
            factura_legacy = lin_data["linea_factura"][i]
            nueva_factura_id = factura_map.get(factura_legacy)
            if nueva_factura_id is None:
                report.warn(f"Linea legacy_id={lin_data['linea_id'][i]}: factura {factura_legacy} no migrada, se omite")
                continue
            concepto_legacy = lin_data["linea_concepto"][i]
            nuevo_concepto_id = concepto_map.get(concepto_legacy) if concepto_legacy else None
            concepto_libre = _none_if_blank(lin_data["linea_conceptolibre"][i])
            if nuevo_concepto_id is None and concepto_libre is None:
                concepto_libre = "(sin descripción)"
            conn.execute(
                """INSERT INTO lineas (factura_id, concepto_id, concepto_libre, cantidad, pvp, orden, legacy_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    nueva_factura_id, nuevo_concepto_id, concepto_libre,
                    _to_float(lin_data["linea_cantidad"][i]),
                    _to_float(lin_data["linea_pvp"][i]),
                    i, lin_data["linea_id"][i],
                ),
            )
            migradas += 1
        report.add("lineas", migradas)

        # ------------------------------------------------------------------- Suplidos
        sup_data = src.parse_table("Suplidos")
        n = len(sup_data.get("sup_id", []))
        migradas = 0
        for i in range(n):
            factura_legacy = sup_data["sup_factura"][i]
            nueva_factura_id = factura_map.get(factura_legacy)
            if nueva_factura_id is None:
                report.warn(f"Suplido legacy_id={sup_data['sup_id'][i]}: factura {factura_legacy} no migrada, se omite")
                continue
            conn.execute(
                "INSERT INTO suplidos (factura_id, concepto, importe, legacy_id) VALUES (?, ?, ?, ?)",
                (nueva_factura_id, _none_if_blank(sup_data["sup_concepto"][i]),
                 _to_float(sup_data["sup_importe"][i]), sup_data["sup_id"][i]),
            )
            migradas += 1
        report.add("suplidos", migradas)

        # -------------------------------------------------------------------- Recibos
        rec_data = src.parse_table("Recibos")
        n = len(rec_data.get("recibos_id", []))
        migradas = 0
        for i in range(n):
            remesa_legacy = rec_data["recibos_remesa"][i]
            conn.execute(
                "INSERT INTO recibos (remesa_id, legacy_id) VALUES (?, ?)",
                (remesa_map.get(remesa_legacy), rec_data["recibos_id"][i]),
            )
            migradas += 1
        report.add("recibos", migradas)

        conn.execute(
            """INSERT INTO configuracion (clave, valor) VALUES ('migration_completed_at', datetime('now'))
               ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor""",
        )
        conn.execute(
            """INSERT INTO configuracion (clave, valor) VALUES ('migration_source_path', ?)
               ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor""",
            (access_path,),
        )
        conn.commit()

    return report


def main():
    parser = argparse.ArgumentParser(description="Migra datos.mdb (Access legacy) a SQLite")
    parser.add_argument("--source", required=True, help="Ruta al archivo datos.mdb")
    parser.add_argument("--db", default=None, help="Ruta de la base SQLite destino (default: %AppData%)")
    parser.add_argument("--force", action="store_true", help="Re-migrar aunque ya se haya corrido antes")
    args = parser.parse_args()

    if not Path(args.source).exists():
        print(f"No se encontró el archivo: {args.source}", file=sys.stderr)
        sys.exit(1)

    report = run_migration(args.source, args.db, force=args.force)
    report.print_summary()


if __name__ == "__main__":
    main()
