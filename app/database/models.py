"""Modelos SQLAlchemy 2.0 (estilo declarativo) de la base de facturación.

Reflejan el mismo esquema que antes definía el SQL crudo en db.py: mismas
tablas, columnas, claves foráneas (con su ON DELETE), CHECK e índices. La app
sigue trabajando con dicts; estos modelos son la fuente de verdad del esquema
y el punto de acceso del ORM.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint, ForeignKey, Index, Integer, Float, Text, text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Tipos de documento soportados por la tabla polimórfica `facturas`.
# FA=Factura, PR=Presupuesto, AL=Albarán, PE=Pedido, AB=Abono (nota de crédito)
TIPOS_DOCUMENTO = ("FA", "PR", "AL", "PE", "AB")

_NOW = text("(datetime('now'))")


class Base(DeclarativeBase):
    pass


class DatosEmpresa(Base):
    __tablename__ = "datos_empresa"
    __table_args__ = (CheckConstraint("id = 1", name="ck_datos_empresa_singleton"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    nombre: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    nif: Mapped[str | None] = mapped_column(Text)
    direccion: Mapped[str | None] = mapped_column(Text)
    cp: Mapped[str | None] = mapped_column(Text)
    localidad: Mapped[str | None] = mapped_column(Text)
    provincia: Mapped[str | None] = mapped_column(Text)
    telefono: Mapped[str | None] = mapped_column(Text)
    fax: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    web: Mapped[str | None] = mapped_column(Text)
    iva_defecto: Mapped[float | None] = mapped_column(Float, server_default=text("21.0"))
    iva_texto: Mapped[str | None] = mapped_column(Text, server_default=text("'IVA'"))
    moneda: Mapped[str | None] = mapped_column(Text, server_default=text("'$'"))
    sufijo: Mapped[str | None] = mapped_column(Text)
    pie_pagina: Mapped[str | None] = mapped_column(Text)
    logo_path: Mapped[str | None] = mapped_column(Text)
    ccc1: Mapped[str | None] = mapped_column(Text)
    ccc2: Mapped[str | None] = mapped_column(Text)
    ccc3: Mapped[str | None] = mapped_column(Text)
    ccc4: Mapped[str | None] = mapped_column(Text)
    ccce1: Mapped[str | None] = mapped_column(Text)
    ccce2: Mapped[str | None] = mapped_column(Text)
    # Datos fiscales (Fase 1). condicion_iva define la letra del comprobante.
    # Los demás y afip_habilitado sostienen la vinculación OPCIONAL con AFIP
    # (la integración real es Fase 4).
    condicion_iva: Mapped[str | None] = mapped_column(Text)
    ingresos_brutos: Mapped[str | None] = mapped_column(Text)
    inicio_actividades: Mapped[str | None] = mapped_column(Text)
    punto_venta: Mapped[str | None] = mapped_column(Text)
    afip_habilitado: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)


class Iva(Base):
    __tablename__ = "iva"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[float] = mapped_column(Float, nullable=False)
    recargo: Mapped[float | None] = mapped_column(Float, server_default=text("0"))
    activo: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)


class FormaPago(Base):
    __tablename__ = "forma_pago"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    genera_recibo: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    vto1: Mapped[str | None] = mapped_column(Text)
    vto2: Mapped[int | None] = mapped_column(Integer)
    vto3: Mapped[int | None] = mapped_column(Integer)
    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)


class Cliente(Base):
    __tablename__ = "clientes"
    __table_args__ = (Index("idx_clientes_nombre", text("nombre COLLATE NOCASE")),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    nif: Mapped[str | None] = mapped_column(Text)
    direccion: Mapped[str | None] = mapped_column(Text)
    cp: Mapped[str | None] = mapped_column(Text)
    localidad: Mapped[str | None] = mapped_column(Text)
    provincia: Mapped[str | None] = mapped_column(Text)
    telefono1: Mapped[str | None] = mapped_column(Text)
    fax: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    persona_contacto: Mapped[str | None] = mapped_column(Text)
    comentarios: Mapped[str | None] = mapped_column(Text)
    forma_pago_id: Mapped[int | None] = mapped_column(
        ForeignKey("forma_pago.id", ondelete="SET NULL")
    )
    banco: Mapped[str | None] = mapped_column(Text)
    ccc1: Mapped[str | None] = mapped_column(Text)
    ccc2: Mapped[str | None] = mapped_column(Text)
    ccc3: Mapped[str | None] = mapped_column(Text)
    ccc4: Mapped[str | None] = mapped_column(Text)
    retencion: Mapped[float | None] = mapped_column(Float, server_default=text("0"))
    recargo_equiv: Mapped[float | None] = mapped_column(Float, server_default=text("0"))
    bonificacion: Mapped[float | None] = mapped_column(Float, server_default=text("0"))
    condicion_iva: Mapped[str | None] = mapped_column(Text)  # receptor: define la letra
    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    created_at: Mapped[str | None] = mapped_column(Text, server_default=_NOW)


class ClienteCuit(Base):
    __tablename__ = "cliente_cuit"
    __table_args__ = (Index("idx_cliente_cuit_cliente", "cliente_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False
    )
    cuit: Mapped[str] = mapped_column(Text, nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))


class Concepto(Base):
    __tablename__ = "conceptos"
    __table_args__ = (
        Index("idx_conceptos_nombre", text("nombre COLLATE NOCASE")),
        Index("idx_conceptos_codigo", text("codigo COLLATE NOCASE")),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    codigo: Mapped[str | None] = mapped_column(Text)
    talle: Mapped[str | None] = mapped_column(Text)
    pvp: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0"))
    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)


class Factura(Base):
    __tablename__ = "facturas"
    __table_args__ = (
        CheckConstraint("tipo IN ('FA','PR','AL','PE','AB')", name="ck_facturas_tipo"),
        CheckConstraint(
            "estado IN ('abierto','facturado','cobrado','anulado')",
            name="ck_facturas_estado",
        ),
        Index("idx_facturas_cliente", "cliente_id"),
        Index("idx_facturas_tipo_fecha", "tipo", "fecha"),
        Index("idx_facturas_asociada", "factura_asociada_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'FA'"))
    ejercicio: Mapped[int] = mapped_column(Integer, nullable=False)
    numero: Mapped[str | None] = mapped_column(Text)
    fecha: Mapped[str] = mapped_column(Text, nullable=False)
    fecha_vencimiento: Mapped[str | None] = mapped_column(Text)
    total: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0"))
    pagado: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0"))
    iva: Mapped[float | None] = mapped_column(Float, server_default=text("0"))
    recargo_equiv: Mapped[float | None] = mapped_column(Float, server_default=text("0"))
    retencion: Mapped[float | None] = mapped_column(Float, server_default=text("0"))
    forma_pago_id: Mapped[int | None] = mapped_column(
        ForeignKey("forma_pago.id", ondelete="SET NULL")
    )
    recibo: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    domicilio_cobro: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    entrega_a_cuenta: Mapped[float | None] = mapped_column(Float, server_default=text("0"))
    provision: Mapped[float | None] = mapped_column(Float, server_default=text("0"))
    total_suplidos: Mapped[float | None] = mapped_column(Float, server_default=text("0"))
    bonificacion: Mapped[float | None] = mapped_column(Float, server_default=text("0"))
    aplica_bonificacion: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    factura_asociada_id: Mapped[int | None] = mapped_column(
        ForeignKey("facturas.id", ondelete="SET NULL")
    )
    origen_tipo: Mapped[str | None] = mapped_column(Text)
    origen_numero: Mapped[str | None] = mapped_column(Text)
    momento_generar: Mapped[str | None] = mapped_column(Text)
    pedido_cliente: Mapped[str | None] = mapped_column(Text)
    comentarios: Mapped[str | None] = mapped_column(Text)
    vista: Mapped[int | None] = mapped_column(Integer, server_default=text("1"))
    estado: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'abierto'"))
    ccc1: Mapped[str | None] = mapped_column(Text)
    ccc2: Mapped[str | None] = mapped_column(Text)
    ccc3: Mapped[str | None] = mapped_column(Text)
    ccc4: Mapped[str | None] = mapped_column(Text)
    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    created_at: Mapped[str | None] = mapped_column(Text, server_default=_NOW)
    # Facturación electrónica AFIP (Fase 4). Vacíos hasta autorizar el
    # comprobante; con cae presente el PDF sale como comprobante fiscal.
    cae: Mapped[str | None] = mapped_column(Text)
    cae_vto: Mapped[str | None] = mapped_column(Text)
    afip_resultado: Mapped[str | None] = mapped_column(Text)
    afip_qr: Mapped[str | None] = mapped_column(Text)

    lineas: Mapped[list["Linea"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )
    suplidos: Mapped[list["Suplido"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )


class Linea(Base):
    __tablename__ = "lineas"
    __table_args__ = (
        CheckConstraint(
            "concepto_id IS NOT NULL OR concepto_libre IS NOT NULL",
            name="ck_lineas_concepto",
        ),
        Index("idx_lineas_factura", "factura_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    factura_id: Mapped[int] = mapped_column(
        ForeignKey("facturas.id", ondelete="CASCADE"), nullable=False
    )
    concepto_id: Mapped[int | None] = mapped_column(
        ForeignKey("conceptos.id", ondelete="SET NULL")
    )
    concepto_libre: Mapped[str | None] = mapped_column(Text)
    cantidad: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("1"))
    pvp: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0"))
    orden: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)


class Suplido(Base):
    __tablename__ = "suplidos"
    __table_args__ = (Index("idx_suplidos_factura", "factura_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    factura_id: Mapped[int] = mapped_column(
        ForeignKey("facturas.id", ondelete="CASCADE"), nullable=False
    )
    concepto: Mapped[str | None] = mapped_column(Text)
    importe: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0"))
    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)


class Remesa(Base):
    __tablename__ = "remesas"

    id: Mapped[int] = mapped_column(primary_key=True)
    descripcion: Mapped[str | None] = mapped_column(Text)
    fecha: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("(date('now'))"))
    fecha_cargo: Mapped[str | None] = mapped_column(Text)
    fecha_vto: Mapped[str | None] = mapped_column(Text)
    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    created_at: Mapped[str | None] = mapped_column(Text, server_default=_NOW)


class Recibo(Base):
    __tablename__ = "recibos"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('pendiente','cobrado','devuelto')", name="ck_recibos_estado"
        ),
        Index("idx_recibos_remesa", "remesa_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    remesa_id: Mapped[int | None] = mapped_column(
        ForeignKey("remesas.id", ondelete="SET NULL")
    )
    factura_id: Mapped[int | None] = mapped_column(
        ForeignKey("facturas.id", ondelete="SET NULL")
    )
    importe: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0"))
    estado: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pendiente'"))
    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)


class Configuracion(Base):
    __tablename__ = "configuracion"

    id: Mapped[int] = mapped_column(primary_key=True)
    clave: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    valor: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str | None] = mapped_column(Text, server_default=_NOW)
