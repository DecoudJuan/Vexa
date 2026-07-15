"""Capa de acceso a datos sobre SQLAlchemy 2.0 (SQLite).

`DatabaseManager` expone la misma API que consumen las pantallas y el generador
de PDF (get_all_clientes, create_factura, get_saldos_clientes, …) y sigue
devolviendo `dict`, para que el resto de la app no dependa del ORM. El esquema
vive en models.py; acá va la lógica de consultas y el arranque de la base.
"""

import json
import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import (
    create_engine, event, select, update, delete, func, cast, Integer, inspect, text,
)
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from database.models import (
    Base, DatosEmpresa, FormaPago, Cliente, ClienteCuit, Concepto,
    Factura, Linea, Suplido, Configuracion, TIPOS_DOCUMENTO,
)

# Carpeta de datos: por defecto ~/Facturacion, pero se puede apuntar a otra
# (ej. un entorno de pruebas aislado) con la variable FACTURACION_DATA_DIR.
DATA_DIR = Path(os.environ.get("FACTURACION_DATA_DIR") or (Path.home() / "Facturacion"))
DEFAULT_DB = DATA_DIR / "data.db"

# Reexportado por compatibilidad (antes vivía acá como constante del esquema).
__all__ = ["DatabaseManager", "DATA_DIR", "DEFAULT_DB", "TIPOS_DOCUMENTO"]

# Clave de Configuracion donde se guardan los perfiles de importación (JSON).
_PERFILES_IMPORT_KEY = "import_perfiles"


def _as_dict(obj) -> dict:
    """Instancia de modelo -> dict de sus columnas (como devolvía sqlite3.Row)."""
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


class DatabaseManager:
    def __init__(self, db_path: str | None = None):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path or str(DEFAULT_DB)
        self.engine = create_engine(f"sqlite:///{self.db_path}", future=True)

        @event.listens_for(self.engine, "connect")
        def _set_pragmas(dbapi_conn, _rec):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode = WAL")
            cur.execute("PRAGMA foreign_keys = ON")
            cur.close()

    @contextmanager
    def _session(self):
        session = Session(self.engine)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # Columnas agregadas después del primer release: se suman a bases ya
    # existentes (create_all no toca tablas que ya existen). Es DDL puntual de
    # compatibilidad, no consultas de datos.
    _COLUMNAS_NUEVAS = {
        "clientes": [
            ("bonificacion", "REAL DEFAULT 0"),
            ("condicion_iva", "TEXT"),
        ],
        "facturas": [
            ("bonificacion", "REAL DEFAULT 0"),
            ("aplica_bonificacion", "INTEGER DEFAULT 0"),
            ("cae", "TEXT"),
            ("cae_vto", "TEXT"),
            ("afip_resultado", "TEXT"),
            ("afip_qr", "TEXT"),
        ],
        "conceptos": [("codigo", "TEXT"), ("talle", "TEXT")],
        "datos_empresa": [
            ("condicion_iva", "TEXT"),
            ("ingresos_brutos", "TEXT"),
            ("inicio_actividades", "TEXT"),
            ("punto_venta", "TEXT"),
            ("afip_habilitado", "INTEGER DEFAULT 0"),
        ],
    }

    def init_db(self) -> None:
        Base.metadata.create_all(self.engine)
        insp = inspect(self.engine)
        with self.engine.begin() as conn:
            for tabla, columnas in self._COLUMNAS_NUEVAS.items():
                existentes = {c["name"] for c in insp.get_columns(tabla)}
                for nombre, ddl in columnas:
                    if nombre not in existentes:
                        conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {ddl}"))
            # El índice de código se asegura acá porque en bases viejas la
            # columna 'codigo' recién se agrega en el ALTER de arriba.
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_conceptos_codigo "
                "ON conceptos(codigo COLLATE NOCASE)"
            ))
        with self._session() as s:
            s.execute(sqlite_insert(DatosEmpresa).values(id=1, nombre="")
                      .on_conflict_do_nothing(index_elements=["id"]))
            for clave, valor in (("iva_defecto", "21.0"),
                                 ("retencion_defecto", "0"),
                                 ("schema_version", "1")):
                s.execute(sqlite_insert(Configuracion).values(clave=clave, valor=valor)
                          .on_conflict_do_nothing(index_elements=["clave"]))
        self._backfill_codigos_concepto()
        self._backfill_talles_concepto()

    def _backfill_codigos_concepto(self) -> None:
        """Rellena código y talle de productos ya cargados sin código (codigo
        NULL), extrayéndolos del nombre en una sola pasada (así el talle no se
        pierde al limpiar el nombre). Idempotente: una vez con '' o valor, no se
        vuelve a tocar. Renombrar es seguro (las líneas referencian por id)."""
        from utils.helpers import separar_codigo_talle

        with self._session() as s:
            filas = s.execute(select(Concepto).where(Concepto.codigo.is_(None))).scalars().all()
            for c in filas:
                limpio, codigo, talle = separar_codigo_talle(c.nombre)
                if codigo or talle:
                    c.nombre = limpio or c.nombre
                c.codigo = codigo   # '' si no hay, para no reprocesar
                if c.talle is None:
                    c.talle = talle

    def _backfill_talles_concepto(self) -> None:
        """Rellena el talle de productos que ya tenían código pero no talle
        (bases actualizadas desde una versión previa a la Fase 3). Sólo recupera
        el talle si aún quedó en el nombre; para el resto hay que reimportar la
        lista con la columna de talle mapeada. Idempotente."""
        from utils.helpers import separar_codigo_talle

        with self._session() as s:
            filas = s.execute(select(Concepto).where(Concepto.talle.is_(None))).scalars().all()
            for c in filas:
                limpio, _codigo, talle = separar_codigo_talle(c.nombre)
                if talle:
                    c.nombre = limpio or c.nombre
                c.talle = talle   # '' si no hay, para no reprocesar

    # ------------------------------------------------------------------ config

    def get_config(self, clave: str) -> str | None:
        with self._session() as s:
            return s.execute(
                select(Configuracion.valor).where(Configuracion.clave == clave)
            ).scalar_one_or_none()

    def set_config(self, clave: str, valor) -> None:
        with self._session() as s:
            stmt = sqlite_insert(Configuracion).values(
                clave=clave, valor=str(valor), updated_at=func.datetime("now")
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["clave"],
                set_={"valor": stmt.excluded.valor, "updated_at": stmt.excluded.updated_at},
            )
            s.execute(stmt)

    # ---------------------------------------------------- perfiles de importación

    def get_perfiles_import(self) -> dict:
        """Perfiles de importación guardados, por proveedor:
        {nombre: {'hoja': str|None, 'columnas': {campo: nombre_columna}}}."""
        raw = self.get_config(_PERFILES_IMPORT_KEY)
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return {}
        return data if isinstance(data, dict) else {}

    def save_perfil_import(self, nombre: str, perfil: dict) -> None:
        nombre = (nombre or "").strip()
        if not nombre:
            return
        perfiles = self.get_perfiles_import()
        perfiles[nombre] = perfil
        self.set_config(_PERFILES_IMPORT_KEY, json.dumps(perfiles, ensure_ascii=False))

    def delete_perfil_import(self, nombre: str) -> None:
        perfiles = self.get_perfiles_import()
        if perfiles.pop(nombre, None) is not None:
            self.set_config(_PERFILES_IMPORT_KEY, json.dumps(perfiles, ensure_ascii=False))

    # ------------------------------------------------------------- datos_empresa

    def get_datos_empresa(self) -> dict:
        with self._session() as s:
            obj = s.get(DatosEmpresa, 1)
            return _as_dict(obj) if obj else {}

    def update_datos_empresa(self, data: dict) -> None:
        campos = [
            "nombre", "nif", "direccion", "cp", "localidad", "provincia",
            "telefono", "fax", "email", "web", "iva_defecto", "iva_texto",
            "moneda", "sufijo", "pie_pagina", "logo_path",
            "ccc1", "ccc2", "ccc3", "ccc4", "ccce1", "ccce2",
            "condicion_iva", "ingresos_brutos", "inicio_actividades",
            "punto_venta", "afip_habilitado",
        ]
        with self._session() as s:
            obj = s.get(DatosEmpresa, 1)
            for c in campos:
                setattr(obj, c, data.get(c))

    # ------------------------------------------------------------------ forma_pago

    def get_all_forma_pago(self) -> list[dict]:
        with self._session() as s:
            stmt = select(FormaPago).order_by(FormaPago.tipo.collate("NOCASE"))
            return [_as_dict(o) for o in s.execute(stmt).scalars()]

    # --------------------------------------------------------------------- clientes

    def get_all_clientes(self, search: str | None = None) -> list[dict]:
        with self._session() as s:
            stmt = select(Cliente)
            if search:
                like = f"%{search}%"
                stmt = stmt.where(
                    Cliente.nombre.like(like) | Cliente.nif.like(like) | Cliente.email.like(like)
                )
            stmt = stmt.order_by(Cliente.nombre.collate("NOCASE"))
            return [_as_dict(o) for o in s.execute(stmt).scalars()]

    def get_cliente(self, cliente_id: int) -> dict | None:
        with self._session() as s:
            obj = s.get(Cliente, cliente_id)
            return _as_dict(obj) if obj else None

    def get_saldos_clientes(self) -> dict:
        """Saldo pendiente por cliente = suma de (total - pagado) de sus
        facturas (tipo FA) todavía no saldadas. Devuelve {cliente_id: saldo}."""
        with self._session() as s:
            stmt = (
                select(Factura.cliente_id, func.sum(Factura.total - Factura.pagado).label("saldo"))
                .where(Factura.tipo == "FA", (Factura.total - Factura.pagado) > 0.005)
                .group_by(Factura.cliente_id)
            )
            return {cid: (saldo or 0) for cid, saldo in s.execute(stmt)}

    _CLIENTE_CAMPOS = [
        "nombre", "nif", "direccion", "cp", "localidad", "provincia",
        "telefono1", "fax", "email", "persona_contacto", "comentarios",
        "forma_pago_id", "banco", "ccc1", "ccc2", "ccc3", "ccc4",
        "retencion", "recargo_equiv", "bonificacion", "condicion_iva",
    ]
    _CLIENTE_DEFAULTS = {"retencion": 0, "recargo_equiv": 0, "bonificacion": 0}

    def _cliente_payload(self, data: dict) -> dict:
        return {
            c: (data[c] if data.get(c) is not None else self._CLIENTE_DEFAULTS.get(c))
            for c in self._CLIENTE_CAMPOS
        }

    def create_cliente(self, data: dict) -> int:
        with self._session() as s:
            obj = Cliente(**self._cliente_payload(data))
            s.add(obj)
            s.flush()
            return obj.id

    def update_cliente(self, cliente_id: int, data: dict) -> None:
        payload = self._cliente_payload(data)
        with self._session() as s:
            obj = s.get(Cliente, cliente_id)
            for k, v in payload.items():
                setattr(obj, k, v)

    def delete_cliente(self, cliente_id: int) -> None:
        with self._session() as s:
            obj = s.get(Cliente, cliente_id)
            if obj is None:
                return
            try:
                s.delete(obj)
                s.flush()
            except IntegrityError as e:
                # Preserva el contrato con la UI (captura sqlite3.IntegrityError).
                raise e.orig if e.orig else e

    # ------------------------------------------------------------ cliente_cuit

    def get_cuits_cliente(self, cliente_id: int) -> list[str]:
        with self._session() as s:
            stmt = (select(ClienteCuit.cuit)
                    .where(ClienteCuit.cliente_id == cliente_id)
                    .order_by(ClienteCuit.orden, ClienteCuit.id))
            return list(s.execute(stmt).scalars())

    def set_cuits_cliente(self, cliente_id: int, cuits: list[str]) -> None:
        """Reemplaza la lista completa de CUIT/CUIL de un cliente."""
        with self._session() as s:
            s.execute(delete(ClienteCuit).where(ClienteCuit.cliente_id == cliente_id))
            for i, cuit in enumerate(c.strip() for c in cuits if c and c.strip()):
                s.add(ClienteCuit(cliente_id=cliente_id, cuit=cuit, orden=i))

    # -------------------------------------------------------------------- conceptos

    def get_all_conceptos(self, search: str | None = None, order: str = "nombre") -> list[dict]:
        # Los productos se ordenan por nombre o por código; un código vacío ('')
        # va al final para que no encabece la lista.
        if order == "codigo":
            order_by = [
                text("CASE WHEN codigo IS NULL OR codigo = '' THEN 1 ELSE 0 END"),
                Concepto.codigo.collate("NOCASE"),
                Concepto.nombre.collate("NOCASE"),
            ]
        else:
            order_by = [Concepto.nombre.collate("NOCASE")]
        with self._session() as s:
            stmt = select(Concepto)
            if search:
                like = f"%{search}%"
                stmt = stmt.where(Concepto.nombre.like(like) | Concepto.codigo.like(like)
                                  | Concepto.talle.like(like))
            stmt = stmt.order_by(*order_by)
            return [_as_dict(o) for o in s.execute(stmt).scalars()]

    @staticmethod
    def _snapshot_concepto_en_lineas(s, obj) -> None:
        """Antes de borrar un producto, congela su nombre (con código y talle)
        en el texto libre de las líneas que lo referencian. La FK es ON DELETE
        SET NULL: sin esto, las facturas viejas perderían el nombre del producto
        en el PDF. Sólo pisa líneas sin texto libre propio."""
        from utils.helpers import etiqueta_concepto
        etq = etiqueta_concepto(obj.nombre, obj.codigo, obj.talle)
        s.execute(
            update(Linea)
            .where(Linea.concepto_id == obj.id, Linea.concepto_libre.is_(None))
            .values(concepto_libre=etq)
        )

    # ------------------------------------------------------ productos agrupados

    def get_productos(self, search: str | None = None, order: str = "nombre") -> list[dict]:
        """Conceptos agrupados por producto (nombre + código): una entrada por
        producto con sus talles y variantes, para el listado y la factura. Cada
        variante es un concepto real (id) reusable como línea de factura."""
        conceptos = self.get_all_conceptos(search, order)
        grupos: dict = {}
        orden: list = []
        for c in conceptos:
            clave = ((c["nombre"] or "").strip().lower(), (c["codigo"] or "").strip())
            g = grupos.get(clave)
            if g is None:
                g = {"nombre": c["nombre"], "codigo": (c["codigo"] or "").strip(),
                     "variantes": []}
                grupos[clave] = g
                orden.append(clave)
            g["variantes"].append({"id": c["id"], "talle": (c["talle"] or "").strip(),
                                   "pvp": c["pvp"] or 0})
        from utils.helpers import ordenar_talles
        productos = []
        for clave in orden:
            g = grupos[clave]
            precios = [v["pvp"] for v in g["variantes"]]
            g["talles"] = ordenar_talles(v["talle"] for v in g["variantes"])
            g["pvp_min"] = min(precios) if precios else 0
            g["pvp_max"] = max(precios) if precios else 0
            g["pvp"] = g["pvp_max"]
            g["ids"] = [v["id"] for v in g["variantes"]]
            productos.append(g)
        return productos

    def save_producto(self, data: dict, orig_nombre: str | None = None,
                      orig_codigo: str | None = None) -> None:
        """Crea o edita un producto y reconcilia sus variantes de talle en un
        solo lugar. `data` = {nombre, codigo, pvp, talles:[...]}. Sin talles se
        guarda una única variante con talle ''. En edición, pasar la clave
        original (nombre/código) para reubicar las variantes existentes; los
        talles que se quiten se borran (con snapshot a las líneas)."""
        nombre = (data.get("nombre") or "").strip()
        codigo = (data.get("codigo") or "").strip()
        pvp = float(data.get("pvp") or 0)
        talles = [t.strip() for t in (data.get("talles") or []) if t.strip()] or [""]
        with self._session() as s:
            if orig_nombre is not None:
                existentes = s.execute(
                    select(Concepto).where(
                        Concepto.nombre.collate("NOCASE") == orig_nombre.strip(),
                        func.coalesce(Concepto.codigo, "") == (orig_codigo or "").strip(),
                    )
                ).scalars().all()
            else:
                existentes = []
            por_talle = {(c.talle or "").strip(): c for c in existentes}
            objetivo = set(talles)
            for t in talles:
                obj = por_talle.get(t)
                if obj is not None:
                    obj.nombre, obj.codigo, obj.talle, obj.pvp = nombre, codigo, t, pvp
                else:
                    s.add(Concepto(nombre=nombre, codigo=codigo, talle=t, pvp=pvp))
            for t, obj in por_talle.items():
                if t not in objetivo:
                    self._snapshot_concepto_en_lineas(s, obj)
                    s.delete(obj)

    def delete_producto(self, nombre: str, codigo: str | None = None) -> None:
        with self._session() as s:
            objs = s.execute(
                select(Concepto).where(
                    Concepto.nombre.collate("NOCASE") == (nombre or "").strip(),
                    func.coalesce(Concepto.codigo, "") == (codigo or "").strip(),
                )
            ).scalars().all()
            for obj in objs:
                self._snapshot_concepto_en_lineas(s, obj)
                s.delete(obj)

    def clear_conceptos(self) -> int:
        """Vacía el catálogo de productos (para 'limpiar y reimportar'),
        congelando antes el nombre en las líneas que los usan para no romper las
        facturas. Devuelve cuántos productos borró."""
        with self._session() as s:
            objs = s.execute(select(Concepto)).scalars().all()
            for obj in objs:
                self._snapshot_concepto_en_lineas(s, obj)
                s.delete(obj)
            return len(objs)

    def upsert_conceptos(self, items: list[dict]) -> dict:
        """Alta/actualización masiva de conceptos por (nombre, talle) —cada
        talle es una variante distinta— en la importación de listas de precios.
        Devuelve {'creados', 'actualizados'}."""
        creados = actualizados = 0
        with self._session() as s:
            for item in items:
                nombre = (item.get("nombre") or "").strip()
                if not nombre:
                    continue
                pvp = float(item.get("pvp") or 0)
                codigo = (item.get("codigo") or "").strip()
                talle = (item.get("talle") or "").strip()
                obj = s.execute(
                    select(Concepto).where(
                        Concepto.nombre.collate("NOCASE") == nombre,
                        func.coalesce(Concepto.talle, "") == talle,
                    )
                ).scalars().first()
                if obj:
                    # El código de la lista pisa; si viene vacío, se conserva.
                    obj.pvp = pvp
                    if codigo:
                        obj.codigo = codigo
                    actualizados += 1
                else:
                    s.add(Concepto(nombre=nombre, codigo=codigo, talle=talle, pvp=pvp))
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
        with self._session() as s:
            stmt = (select(Factura, Cliente.nombre.label("cliente_nombre"))
                    .join(Cliente, Factura.cliente_id == Cliente.id))
            if tipo:
                stmt = stmt.where(Factura.tipo == tipo)
            if cliente_id is not None:
                stmt = stmt.where(Factura.cliente_id == cliente_id)
            if ejercicio is not None:
                stmt = stmt.where(Factura.ejercicio == ejercicio)
            if estado:
                stmt = stmt.where(Factura.estado == estado)
            if search:
                like = f"%{search}%"
                stmt = stmt.where(Factura.numero.like(like) | Cliente.nombre.like(like))
            stmt = stmt.order_by(Factura.fecha.desc(), Factura.id.desc())
            return [{**_as_dict(f), "cliente_nombre": nombre}
                    for f, nombre in s.execute(stmt)]

    def get_factura(self, factura_id: int) -> dict | None:
        with self._session() as s:
            row = s.execute(
                select(Factura, Cliente.nombre.label("cliente_nombre"))
                .join(Cliente, Factura.cliente_id == Cliente.id)
                .where(Factura.id == factura_id)
            ).first()
            if not row:
                return None
            f, nombre = row
            return {**_as_dict(f), "cliente_nombre": nombre}

    def guardar_cae(self, factura_id: int, cae: str, cae_vto: str | None,
                    qr_url: str | None, resultado: str | None = "A",
                    numero: int | None = None) -> None:
        """Persiste el CAE y datos de AFIP tras autorizar el comprobante. Si AFIP
        asignó un número (numero), lo guarda también para que coincida con el
        último autorizado del punto de venta."""
        valores = {
            "cae": cae, "cae_vto": cae_vto, "afip_qr": qr_url,
            "afip_resultado": resultado,
        }
        if numero is not None:
            valores["numero"] = str(numero)
        with self._session() as s:
            s.execute(update(Factura).where(Factura.id == factura_id).values(**valores))

    def get_lineas(self, factura_id: int) -> list[dict]:
        with self._session() as s:
            stmt = (select(Linea,
                           Concepto.nombre.label("concepto_nombre"),
                           Concepto.codigo.label("concepto_codigo"),
                           Concepto.talle.label("concepto_talle"))
                    .outerjoin(Concepto, Linea.concepto_id == Concepto.id)
                    .where(Linea.factura_id == factura_id)
                    .order_by(Linea.orden, Linea.id))
            return [{**_as_dict(ln), "concepto_nombre": cn, "concepto_codigo": cc,
                     "concepto_talle": ct}
                    for ln, cn, cc, ct in s.execute(stmt)]

    def get_suplidos(self, factura_id: int) -> list[dict]:
        with self._session() as s:
            stmt = select(Suplido).where(Suplido.factura_id == factura_id).order_by(Suplido.id)
            return [_as_dict(o) for o in s.execute(stmt).scalars()]

    def siguiente_numero(self, tipo: str, ejercicio: int) -> str:
        """Próximo número secuencial para un tipo+ejercicio (4 dígitos: 0001)."""
        with self._session() as s:
            mx = s.execute(
                select(func.max(cast(Factura.numero, Integer)))
                .where(Factura.tipo == tipo, Factura.ejercicio == ejercicio)
            ).scalar()
            return f"{(mx or 0) + 1:04d}"

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

    def _factura_payload(self, data: dict) -> dict:
        return {
            c: (data[c] if data.get(c) is not None else self._FACTURA_DEFAULTS.get(c))
            for c in self._FACTURA_CAMPOS
        }

    @staticmethod
    def _nuevas_lineas(lineas: list[dict]) -> list[Linea]:
        return [
            Linea(concepto_id=ln.get("concepto_id"),
                  concepto_libre=ln.get("concepto_libre"),
                  cantidad=ln.get("cantidad", 1),
                  pvp=ln.get("pvp", 0),
                  orden=i)
            for i, ln in enumerate(lineas)
        ]

    @staticmethod
    def _nuevos_suplidos(suplidos: list[dict] | None) -> list[Suplido]:
        return [
            Suplido(concepto=sp.get("concepto"), importe=sp.get("importe", 0))
            for sp in (suplidos or [])
        ]

    def create_factura(self, data: dict, lineas: list[dict], suplidos: list[dict] | None = None) -> int:
        with self._session() as s:
            factura = Factura(**self._factura_payload(data))
            factura.lineas = self._nuevas_lineas(lineas)
            factura.suplidos = self._nuevos_suplidos(suplidos)
            s.add(factura)
            s.flush()
            return factura.id

    def update_factura(self, factura_id: int, data: dict, lineas: list[dict],
                       suplidos: list[dict] | None = None) -> None:
        payload = self._factura_payload(data)
        with self._session() as s:
            factura = s.get(Factura, factura_id)
            for k, v in payload.items():
                setattr(factura, k, v)
            # delete-orphan reemplaza líneas y suplidos por los nuevos.
            factura.lineas = self._nuevas_lineas(lineas)
            factura.suplidos = self._nuevos_suplidos(suplidos)

    def delete_factura(self, factura_id: int) -> None:
        with self._session() as s:
            obj = s.get(Factura, factura_id)
            if obj is not None:
                s.delete(obj)
