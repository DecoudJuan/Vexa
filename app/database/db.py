import sqlite3
from contextlib import contextmanager
from pathlib import Path

DATA_DIR = Path.home() / "Facturacion"
DEFAULT_DB = DATA_DIR / "data.db"

# Tipos de documento soportados por la tabla polimórfica `facturas`.
# FA=Factura, PR=Presupuesto, AL=Albarán, PE=Pedido, AB=Abono (nota de crédito)
TIPOS_DOCUMENTO = ("FA", "PR", "AL", "PE", "AB")

_SCHEMA = """
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS datos_empresa (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    nombre        TEXT NOT NULL DEFAULT '',
    nif           TEXT,
    direccion     TEXT,
    cp            TEXT,
    localidad     TEXT,
    provincia     TEXT,
    telefono      TEXT,
    fax           TEXT,
    email         TEXT,
    web           TEXT,
    iva_defecto   REAL DEFAULT 21.0,
    iva_texto     TEXT DEFAULT 'IVA',
    moneda        TEXT DEFAULT '$',
    sufijo        TEXT,
    pie_pagina    TEXT,
    logo_path     TEXT,
    ccc1 TEXT, ccc2 TEXT, ccc3 TEXT, ccc4 TEXT,
    ccce1 TEXT, ccce2 TEXT,
    legacy_id     INTEGER UNIQUE
);
INSERT OR IGNORE INTO datos_empresa (id, nombre) VALUES (1, '');

CREATE TABLE IF NOT EXISTS iva (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo        REAL NOT NULL,
    recargo     REAL DEFAULT 0,
    activo      INTEGER NOT NULL DEFAULT 1,
    legacy_id   INTEGER UNIQUE
);

CREATE TABLE IF NOT EXISTS forma_pago (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo          TEXT NOT NULL,
    genera_recibo INTEGER NOT NULL DEFAULT 0,
    vto1          TEXT,
    vto2          INTEGER,
    vto3          INTEGER,
    legacy_id     INTEGER UNIQUE
);

CREATE TABLE IF NOT EXISTS clientes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre              TEXT NOT NULL,
    nif                 TEXT,
    direccion           TEXT,
    cp                  TEXT,
    localidad           TEXT,
    provincia           TEXT,
    telefono1           TEXT,
    fax                 TEXT,
    email               TEXT,
    persona_contacto    TEXT,
    comentarios         TEXT,
    forma_pago_id       INTEGER REFERENCES forma_pago(id) ON DELETE SET NULL,
    banco               TEXT,
    ccc1 TEXT, ccc2 TEXT, ccc3 TEXT, ccc4 TEXT,
    retencion           REAL DEFAULT 0,
    recargo_equiv       REAL DEFAULT 0,
    bonificacion        REAL DEFAULT 0,
    legacy_id           INTEGER UNIQUE,
    created_at          TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_clientes_nombre ON clientes(nombre COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS cliente_cuit (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id  INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    cuit        TEXT NOT NULL,
    orden       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_cliente_cuit_cliente ON cliente_cuit(cliente_id);

CREATE TABLE IF NOT EXISTS conceptos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT NOT NULL,
    codigo      TEXT,
    pvp         REAL NOT NULL DEFAULT 0,
    legacy_id   INTEGER UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_conceptos_nombre ON conceptos(nombre COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS facturas (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id            INTEGER NOT NULL REFERENCES clientes(id) ON DELETE RESTRICT,
    tipo                  TEXT NOT NULL DEFAULT 'FA' CHECK (tipo IN ('FA','PR','AL','PE','AB')),
    ejercicio             INTEGER NOT NULL,
    numero                TEXT,
    fecha                 TEXT NOT NULL,
    fecha_vencimiento     TEXT,
    total                 REAL NOT NULL DEFAULT 0,
    pagado                REAL NOT NULL DEFAULT 0,
    iva                   REAL DEFAULT 0,
    recargo_equiv         REAL DEFAULT 0,
    retencion             REAL DEFAULT 0,
    forma_pago_id         INTEGER REFERENCES forma_pago(id) ON DELETE SET NULL,
    recibo                INTEGER DEFAULT 0,
    domicilio_cobro       INTEGER DEFAULT 0,
    entrega_a_cuenta      REAL DEFAULT 0,
    provision             REAL DEFAULT 0,
    total_suplidos        REAL DEFAULT 0,
    bonificacion          REAL DEFAULT 0,
    aplica_bonificacion   INTEGER DEFAULT 0,
    factura_asociada_id   INTEGER REFERENCES facturas(id) ON DELETE SET NULL,
    origen_tipo           TEXT,
    origen_numero         TEXT,
    momento_generar       TEXT,
    pedido_cliente        TEXT,
    comentarios           TEXT,
    vista                 INTEGER DEFAULT 1,
    estado                TEXT NOT NULL DEFAULT 'abierto' CHECK (estado IN ('abierto','facturado','cobrado','anulado')),
    ccc1 TEXT, ccc2 TEXT, ccc3 TEXT, ccc4 TEXT,
    legacy_id             INTEGER UNIQUE,
    created_at            TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_facturas_cliente    ON facturas(cliente_id);
CREATE INDEX IF NOT EXISTS idx_facturas_tipo_fecha ON facturas(tipo, fecha);
CREATE INDEX IF NOT EXISTS idx_facturas_asociada   ON facturas(factura_asociada_id);

CREATE TABLE IF NOT EXISTS lineas (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    factura_id         INTEGER NOT NULL REFERENCES facturas(id) ON DELETE CASCADE,
    concepto_id        INTEGER REFERENCES conceptos(id) ON DELETE SET NULL,
    concepto_libre     TEXT,
    cantidad           REAL NOT NULL DEFAULT 1,
    pvp                REAL NOT NULL DEFAULT 0,
    orden              INTEGER NOT NULL DEFAULT 0,
    legacy_id          INTEGER UNIQUE,
    CHECK (concepto_id IS NOT NULL OR concepto_libre IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_lineas_factura ON lineas(factura_id);

CREATE TABLE IF NOT EXISTS suplidos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    factura_id  INTEGER NOT NULL REFERENCES facturas(id) ON DELETE CASCADE,
    concepto    TEXT,
    importe     REAL NOT NULL DEFAULT 0,
    legacy_id   INTEGER UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_suplidos_factura ON suplidos(factura_id);

CREATE TABLE IF NOT EXISTS remesas (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    descripcion    TEXT,
    fecha          TEXT NOT NULL DEFAULT (date('now')),
    fecha_cargo    TEXT,
    fecha_vto      TEXT,
    legacy_id      INTEGER UNIQUE,
    created_at     TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS recibos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    remesa_id   INTEGER REFERENCES remesas(id) ON DELETE SET NULL,
    factura_id  INTEGER REFERENCES facturas(id) ON DELETE SET NULL,
    importe     REAL NOT NULL DEFAULT 0,
    estado      TEXT NOT NULL DEFAULT 'pendiente' CHECK (estado IN ('pendiente','cobrado','devuelto')),
    legacy_id   INTEGER UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_recibos_remesa ON recibos(remesa_id);

CREATE TABLE IF NOT EXISTS configuracion (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    clave      TEXT UNIQUE NOT NULL,
    valor      TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now'))
);
INSERT OR IGNORE INTO configuracion (clave, valor) VALUES
    ('iva_defecto',    '21.0'),
    ('retencion_defecto', '0'),
    ('schema_version', '1');
"""


class DatabaseManager:
    def __init__(self, db_path: str | None = None):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path or str(DEFAULT_DB)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # Columnas agregadas después del primer release: init_db() las suma a
    # bases ya existentes, ya que `CREATE TABLE IF NOT EXISTS` no las crea
    # en tablas que ya existían antes de este cambio.
    _COLUMNAS_NUEVAS = {
        "clientes": [("bonificacion", "REAL DEFAULT 0")],
        "facturas": [
            ("bonificacion", "REAL DEFAULT 0"),
            ("aplica_bonificacion", "INTEGER DEFAULT 0"),
        ],
        "conceptos": [("codigo", "TEXT")],
    }

    def init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(_SCHEMA)
            for tabla, columnas in self._COLUMNAS_NUEVAS.items():
                existentes = {row["name"] for row in conn.execute(f"PRAGMA table_info({tabla})")}
                for nombre, ddl in columnas:
                    if nombre not in existentes:
                        conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {ddl}")
            # El índice de código se crea acá (no en _SCHEMA) porque en bases
            # ya existentes la columna 'codigo' recién se agrega en el ALTER de
            # arriba; crearlo dentro del schema fallaría con "no such column".
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_conceptos_codigo ON conceptos(codigo COLLATE NOCASE)"
            )
        self._backfill_codigos_concepto()

    def _backfill_codigos_concepto(self) -> None:
        """Rellena el código de los productos ya cargados que todavía no lo
        tienen (codigo NULL), extrayéndolo del propio nombre y limpiándolo.
        Idempotente: una vez que un producto queda con código '' o con valor,
        no se vuelve a tocar. Renombrar es seguro: las líneas de factura
        referencian al producto por id, no por nombre."""
        from utils.helpers import separar_codigo

        with self._conn() as conn:
            filas = conn.execute(
                "SELECT id, nombre FROM conceptos WHERE codigo IS NULL"
            ).fetchall()
            for f in filas:
                limpio, codigo = separar_codigo(f["nombre"])
                if codigo:
                    conn.execute(
                        "UPDATE conceptos SET nombre = ?, codigo = ? WHERE id = ?",
                        (limpio or f["nombre"], codigo, f["id"]),
                    )
                else:
                    # Sin código detectable: marcar como '' para no reprocesar.
                    conn.execute(
                        "UPDATE conceptos SET codigo = '' WHERE id = ?", (f["id"],)
                    )

    # ------------------------------------------------------------------ config

    def get_config(self, clave: str) -> str | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT valor FROM configuracion WHERE clave = ?", (clave,)
            ).fetchone()
            return row["valor"] if row else None

    def set_config(self, clave: str, valor) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO configuracion (clave, valor, updated_at)
                   VALUES (?, ?, datetime('now'))
                   ON CONFLICT(clave) DO UPDATE
                   SET valor = excluded.valor,
                       updated_at = excluded.updated_at""",
                (clave, str(valor)),
            )

    # ------------------------------------------------------------- datos_empresa

    def get_datos_empresa(self) -> dict:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM datos_empresa WHERE id = 1").fetchone()
            return dict(row) if row else {}

    def update_datos_empresa(self, data: dict) -> None:
        campos = [
            "nombre", "nif", "direccion", "cp", "localidad", "provincia",
            "telefono", "fax", "email", "web", "iva_defecto", "iva_texto",
            "moneda", "sufijo", "pie_pagina", "logo_path",
            "ccc1", "ccc2", "ccc3", "ccc4", "ccce1", "ccce2",
        ]
        sets = ", ".join(f"{c} = :{c}" for c in campos)
        payload = {c: data.get(c) for c in campos}
        with self._conn() as conn:
            conn.execute(f"UPDATE datos_empresa SET {sets} WHERE id = 1", payload)

    # ----------------------------------------------------------------------- iva

    def get_all_iva(self, solo_activos: bool = False) -> list[dict]:
        with self._conn() as conn:
            q = "SELECT * FROM iva"
            if solo_activos:
                q += " WHERE activo = 1"
            q += " ORDER BY tipo DESC"
            return [dict(r) for r in conn.execute(q).fetchall()]

    def create_iva(self, data: dict) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO iva (tipo, recargo, activo) VALUES (:tipo, :recargo, :activo)",
                data,
            )
            return cur.lastrowid

    def update_iva(self, iva_id: int, data: dict) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE iva SET tipo = :tipo, recargo = :recargo, activo = :activo WHERE id = :id",
                {**data, "id": iva_id},
            )

    def delete_iva(self, iva_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM iva WHERE id = ?", (iva_id,))

    # ------------------------------------------------------------------ forma_pago

    def get_all_forma_pago(self) -> list[dict]:
        with self._conn() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM forma_pago ORDER BY tipo COLLATE NOCASE"
            ).fetchall()]

    def create_forma_pago(self, data: dict) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO forma_pago (tipo, genera_recibo, vto1, vto2, vto3)
                   VALUES (:tipo, :genera_recibo, :vto1, :vto2, :vto3)""",
                data,
            )
            return cur.lastrowid

    def update_forma_pago(self, forma_pago_id: int, data: dict) -> None:
        with self._conn() as conn:
            conn.execute(
                """UPDATE forma_pago SET tipo = :tipo, genera_recibo = :genera_recibo,
                   vto1 = :vto1, vto2 = :vto2, vto3 = :vto3 WHERE id = :id""",
                {**data, "id": forma_pago_id},
            )

    def delete_forma_pago(self, forma_pago_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM forma_pago WHERE id = ?", (forma_pago_id,))

    # --------------------------------------------------------------------- clientes

    def get_all_clientes(self, search: str | None = None) -> list[dict]:
        with self._conn() as conn:
            if search:
                q = f"%{search}%"
                rows = conn.execute(
                    """SELECT * FROM clientes
                       WHERE nombre LIKE ? OR nif LIKE ? OR email LIKE ?
                       ORDER BY nombre COLLATE NOCASE""",
                    (q, q, q),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM clientes ORDER BY nombre COLLATE NOCASE"
                ).fetchall()
            return [dict(r) for r in rows]

    def get_cliente(self, cliente_id: int) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM clientes WHERE id = ?", (cliente_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_saldos_clientes(self) -> dict:
        """Saldo pendiente por cliente = suma de (total - pagado) de sus
        facturas (tipo FA) que todavía no están saldadas. Devuelve
        {cliente_id: saldo}."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT cliente_id, SUM(total - pagado) AS saldo
                   FROM facturas
                   WHERE tipo = 'FA' AND (total - pagado) > 0.005
                   GROUP BY cliente_id"""
            ).fetchall()
            return {r["cliente_id"]: (r["saldo"] or 0) for r in rows}

    _CLIENTE_CAMPOS = [
        "nombre", "nif", "direccion", "cp", "localidad", "provincia",
        "telefono1", "fax", "email", "persona_contacto", "comentarios",
        "forma_pago_id", "banco", "ccc1", "ccc2", "ccc3", "ccc4",
        "retencion", "recargo_equiv", "bonificacion",
    ]
    _CLIENTE_DEFAULTS = {"retencion": 0, "recargo_equiv": 0, "bonificacion": 0}

    def create_cliente(self, data: dict) -> int:
        payload = {
            c: (data[c] if data.get(c) is not None else self._CLIENTE_DEFAULTS.get(c))
            for c in self._CLIENTE_CAMPOS
        }
        cols = ", ".join(self._CLIENTE_CAMPOS)
        placeholders = ", ".join(f":{c}" for c in self._CLIENTE_CAMPOS)
        with self._conn() as conn:
            cur = conn.execute(
                f"INSERT INTO clientes ({cols}) VALUES ({placeholders})", payload
            )
            return cur.lastrowid

    def update_cliente(self, cliente_id: int, data: dict) -> None:
        payload = {
            c: (data[c] if data.get(c) is not None else self._CLIENTE_DEFAULTS.get(c))
            for c in self._CLIENTE_CAMPOS
        }
        sets = ", ".join(f"{c} = :{c}" for c in self._CLIENTE_CAMPOS)
        with self._conn() as conn:
            conn.execute(
                f"UPDATE clientes SET {sets} WHERE id = :id",
                {**payload, "id": cliente_id},
            )

    def delete_cliente(self, cliente_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM clientes WHERE id = ?", (cliente_id,))

    # ------------------------------------------------------------ cliente_cuit

    def get_cuits_cliente(self, cliente_id: int) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT cuit FROM cliente_cuit WHERE cliente_id = ? ORDER BY orden, id",
                (cliente_id,),
            ).fetchall()
            return [r["cuit"] for r in rows]

    def set_cuits_cliente(self, cliente_id: int, cuits: list[str]) -> None:
        """Reemplaza la lista completa de CUIT/CUIL de un cliente."""
        with self._conn() as conn:
            conn.execute("DELETE FROM cliente_cuit WHERE cliente_id = ?", (cliente_id,))
            for i, cuit in enumerate(c.strip() for c in cuits if c and c.strip()):
                conn.execute(
                    "INSERT INTO cliente_cuit (cliente_id, cuit, orden) VALUES (?, ?, ?)",
                    (cliente_id, cuit, i),
                )

    # -------------------------------------------------------------------- conceptos

    def get_all_conceptos(self, search: str | None = None, order: str = "nombre") -> list[dict]:
        # Los productos se pueden ordenar por nombre o por código; un código
        # vacío ('') se manda al final para que no encabece la lista.
        if order == "codigo":
            order_sql = ("CASE WHEN codigo IS NULL OR codigo = '' THEN 1 ELSE 0 END, "
                         "codigo COLLATE NOCASE, nombre COLLATE NOCASE")
        else:
            order_sql = "nombre COLLATE NOCASE"
        with self._conn() as conn:
            if search:
                q = f"%{search}%"
                rows = conn.execute(
                    f"""SELECT * FROM conceptos
                        WHERE nombre LIKE ? OR codigo LIKE ?
                        ORDER BY {order_sql}""",
                    (q, q),
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT * FROM conceptos ORDER BY {order_sql}"
                ).fetchall()
            return [dict(r) for r in rows]

    def create_concepto(self, data: dict) -> int:
        payload = {"nombre": data.get("nombre"), "codigo": data.get("codigo") or "",
                   "pvp": data.get("pvp") or 0}
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO conceptos (nombre, codigo, pvp) VALUES (:nombre, :codigo, :pvp)",
                payload,
            )
            return cur.lastrowid

    def update_concepto(self, concepto_id: int, data: dict) -> None:
        payload = {"nombre": data.get("nombre"), "codigo": data.get("codigo") or "",
                   "pvp": data.get("pvp") or 0, "id": concepto_id}
        with self._conn() as conn:
            conn.execute(
                "UPDATE conceptos SET nombre = :nombre, codigo = :codigo, pvp = :pvp WHERE id = :id",
                payload,
            )

    def delete_concepto(self, concepto_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM conceptos WHERE id = ?", (concepto_id,))

    def upsert_conceptos(self, items: list[dict]) -> dict:
        """Alta/actualización masiva de conceptos por nombre (usado por la
        importación de listas de precios). Devuelve {'creados', 'actualizados'}."""
        creados = actualizados = 0
        with self._conn() as conn:
            for item in items:
                nombre = (item.get("nombre") or "").strip()
                if not nombre:
                    continue
                pvp = float(item.get("pvp") or 0)
                codigo = (item.get("codigo") or "").strip()
                row = conn.execute(
                    "SELECT id FROM conceptos WHERE nombre = ? COLLATE NOCASE", (nombre,)
                ).fetchone()
                if row:
                    # El código de la lista siempre pisa; si la fila viene sin
                    # código, se conserva el que ya tuviera (COALESCE).
                    conn.execute(
                        "UPDATE conceptos SET pvp = ?, codigo = COALESCE(NULLIF(?, ''), codigo) WHERE id = ?",
                        (pvp, codigo, row["id"]),
                    )
                    actualizados += 1
                else:
                    conn.execute(
                        "INSERT INTO conceptos (nombre, codigo, pvp) VALUES (?, ?, ?)",
                        (nombre, codigo, pvp),
                    )
                    creados += 1
        return {"creados": creados, "actualizados": actualizados}

    # -------------------------------------------------------------------- facturas

    def get_facturas(
        self,
        tipo: str | None = None,
        cliente_id: int | None = None,
        ejercicio: int | None = None,
        estado: str | None = None,
        search: str | None = None,
    ) -> list[dict]:
        wheres, params = [], []
        if tipo:
            wheres.append("f.tipo = ?")
            params.append(tipo)
        if cliente_id is not None:
            wheres.append("f.cliente_id = ?")
            params.append(cliente_id)
        if ejercicio is not None:
            wheres.append("f.ejercicio = ?")
            params.append(ejercicio)
        if estado:
            wheres.append("f.estado = ?")
            params.append(estado)
        if search:
            wheres.append("(f.numero LIKE ? OR c.nombre LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        where_sql = ("WHERE " + " AND ".join(wheres)) if wheres else ""
        with self._conn() as conn:
            rows = conn.execute(
                f"""SELECT f.*, c.nombre AS cliente_nombre
                    FROM facturas f JOIN clientes c ON f.cliente_id = c.id
                    {where_sql}
                    ORDER BY f.fecha DESC, f.id DESC""",
                params,
            ).fetchall()
            return [dict(r) for r in rows]

    def get_factura(self, factura_id: int) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                """SELECT f.*, c.nombre AS cliente_nombre
                   FROM facturas f JOIN clientes c ON f.cliente_id = c.id
                   WHERE f.id = ?""",
                (factura_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_lineas(self, factura_id: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT l.*, co.nombre AS concepto_nombre, co.codigo AS concepto_codigo
                   FROM lineas l LEFT JOIN conceptos co ON l.concepto_id = co.id
                   WHERE l.factura_id = ?
                   ORDER BY l.orden, l.id""",
                (factura_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_suplidos(self, factura_id: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM suplidos WHERE factura_id = ? ORDER BY id", (factura_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def siguiente_numero(self, tipo: str, ejercicio: int) -> str:
        """Próximo número secuencial para un tipo+ejercicio (ej. 4 dígitos: 0001)."""
        with self._conn() as conn:
            row = conn.execute(
                """SELECT MAX(CAST(numero AS INTEGER)) AS mx FROM facturas
                   WHERE tipo = ? AND ejercicio = ?""",
                (tipo, ejercicio),
            ).fetchone()
            siguiente = (row["mx"] or 0) + 1
            return f"{siguiente:04d}"

    _FACTURA_DEFAULTS = {
        "tipo": "FA", "total": 0, "pagado": 0, "iva": 0, "recargo_equiv": 0,
        "retencion": 0, "recibo": 0, "domicilio_cobro": 0, "entrega_a_cuenta": 0,
        "provision": 0, "total_suplidos": 0, "bonificacion": 0, "aplica_bonificacion": 0,
        "vista": 1, "estado": "abierto",
    }
    _FACTURA_CAMPOS = [
        "cliente_id", "tipo", "ejercicio", "numero", "fecha", "fecha_vencimiento",
        "total", "pagado", "iva", "recargo_equiv", "retencion", "forma_pago_id",
        "recibo", "domicilio_cobro", "entrega_a_cuenta", "provision", "total_suplidos",
        "bonificacion", "aplica_bonificacion",
        "factura_asociada_id", "origen_tipo", "origen_numero", "momento_generar",
        "pedido_cliente", "comentarios", "vista", "estado",
    ]

    def create_factura(self, data: dict, lineas: list[dict], suplidos: list[dict] | None = None) -> int:
        campos = self._FACTURA_CAMPOS
        payload = {
            c: (data[c] if data.get(c) is not None else self._FACTURA_DEFAULTS.get(c))
            for c in campos
        }
        cols = ", ".join(campos)
        placeholders = ", ".join(f":{c}" for c in campos)
        with self._conn() as conn:
            cur = conn.execute(f"INSERT INTO facturas ({cols}) VALUES ({placeholders})", payload)
            factura_id = cur.lastrowid
            for i, ln in enumerate(lineas):
                conn.execute(
                    """INSERT INTO lineas (factura_id, concepto_id, concepto_libre, cantidad, pvp, orden)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (factura_id, ln.get("concepto_id"), ln.get("concepto_libre"),
                     ln.get("cantidad", 1), ln.get("pvp", 0), i),
                )
            for sp in (suplidos or []):
                conn.execute(
                    "INSERT INTO suplidos (factura_id, concepto, importe) VALUES (?, ?, ?)",
                    (factura_id, sp.get("concepto"), sp.get("importe", 0)),
                )
            return factura_id

    def update_factura(self, factura_id: int, data: dict, lineas: list[dict], suplidos: list[dict] | None = None) -> None:
        campos = self._FACTURA_CAMPOS
        payload = {
            c: (data[c] if data.get(c) is not None else self._FACTURA_DEFAULTS.get(c))
            for c in campos
        }
        sets = ", ".join(f"{c} = :{c}" for c in campos)
        with self._conn() as conn:
            conn.execute(f"UPDATE facturas SET {sets} WHERE id = :id", {**payload, "id": factura_id})
            conn.execute("DELETE FROM lineas WHERE factura_id = ?", (factura_id,))
            for i, ln in enumerate(lineas):
                conn.execute(
                    """INSERT INTO lineas (factura_id, concepto_id, concepto_libre, cantidad, pvp, orden)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (factura_id, ln.get("concepto_id"), ln.get("concepto_libre"),
                     ln.get("cantidad", 1), ln.get("pvp", 0), i),
                )
            conn.execute("DELETE FROM suplidos WHERE factura_id = ?", (factura_id,))
            for sp in (suplidos or []):
                conn.execute(
                    "INSERT INTO suplidos (factura_id, concepto, importe) VALUES (?, ?, ?)",
                    (factura_id, sp.get("concepto"), sp.get("importe", 0)),
                )

    def update_factura_estado(self, factura_id: int, estado: str) -> None:
        with self._conn() as conn:
            conn.execute("UPDATE facturas SET estado = ? WHERE id = ?", (estado, factura_id))

    def delete_factura(self, factura_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM facturas WHERE id = ?", (factura_id,))

    # --------------------------------------------------------------- remesas / recibos

    def get_all_remesas(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT r.*,
                          (SELECT COUNT(*) FROM recibos WHERE remesa_id = r.id) AS n_recibos,
                          (SELECT COALESCE(SUM(importe), 0) FROM recibos WHERE remesa_id = r.id) AS total
                   FROM remesas r ORDER BY r.fecha DESC, r.id DESC"""
            ).fetchall()
            return [dict(r) for r in rows]

    def get_recibos_pendientes(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT re.*, f.numero AS factura_numero, f.tipo AS factura_tipo,
                          c.nombre AS cliente_nombre
                   FROM recibos re
                   JOIN facturas f ON re.factura_id = f.id
                   JOIN clientes c ON f.cliente_id = c.id
                   WHERE re.estado = 'pendiente' AND re.remesa_id IS NULL
                   ORDER BY c.nombre COLLATE NOCASE"""
            ).fetchall()
            return [dict(r) for r in rows]

    def get_recibos_de_remesa(self, remesa_id: int) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT re.*, f.numero AS factura_numero, f.tipo AS factura_tipo,
                          c.nombre AS cliente_nombre, c.ccc1, c.ccc2, c.ccc3, c.ccc4
                   FROM recibos re
                   JOIN facturas f ON re.factura_id = f.id
                   JOIN clientes c ON f.cliente_id = c.id
                   WHERE re.remesa_id = ?
                   ORDER BY c.nombre COLLATE NOCASE""",
                (remesa_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def create_recibo(self, factura_id: int, importe: float) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO recibos (factura_id, importe) VALUES (?, ?)",
                (factura_id, importe),
            )
            return cur.lastrowid

    def create_remesa(self, recibo_ids: list[int], data: dict) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO remesas (descripcion, fecha, fecha_cargo, fecha_vto)
                   VALUES (:descripcion, :fecha, :fecha_cargo, :fecha_vto)""",
                data,
            )
            remesa_id = cur.lastrowid
            conn.executemany(
                "UPDATE recibos SET remesa_id = ? WHERE id = ?",
                [(remesa_id, rid) for rid in recibo_ids],
            )
            return remesa_id

    # ------------------------------------------------------------------ dashboard

    def get_resumen(self, ejercicio: int) -> dict:
        with self._conn() as conn:
            totales = conn.execute(
                """SELECT tipo, COUNT(*) AS cantidad, COALESCE(SUM(total), 0) AS total
                   FROM facturas WHERE ejercicio = ? GROUP BY tipo""",
                (ejercicio,),
            ).fetchall()
            n_clientes = conn.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
            return {
                "por_tipo": [dict(r) for r in totales],
                "n_clientes": n_clientes,
            }
