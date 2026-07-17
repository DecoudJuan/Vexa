"""Datos de demostración para el primer arranque (base vacía)."""
from __future__ import annotations

from datetime import date

from vexa_core.database.db import DatabaseManager


def seed_demo(db: DatabaseManager) -> None:
    if db.get_all_clientes():
        return
    # Nombre de empresa demo (para el saludo del Inicio). En uso real lo carga el
    # usuario en Configuración → Datos de la empresa.
    emp = db.get_datos_empresa()
    if not (emp.get("nombre") or "").strip():
        emp["nombre"] = "Vexa Demo"
        db.update_datos_empresa(emp)
    demo = [("Distribuidora del Litoral SRL", "Santa Fe"), ("Ortopedia San Martín", "Rosario"),
            ("Farmacia Belgrano", "Córdoba"), ("Kinesiología Central", "Rosario")]
    ids = [db.create_cliente({"nombre": n, "localidad": loc, "condicion_iva": "Consumidor Final"})
           for n, loc in demo]
    db.upsert_conceptos([
        {"nombre": "FAJA LUMBAR", "codigo": "020", "talle": "1", "pvp": 9800},
        {"nombre": "FAJA LUMBAR", "codigo": "020", "talle": "2", "pvp": 9800},
        {"nombre": "CALZA REDUCTORA", "codigo": "060", "talle": "1", "pvp": 12400},
        {"nombre": "HOMBRERA UNIVERSAL", "codigo": "026", "talle": "", "pvp": 7200},
    ])
    ej = date.today().year
    lineas = [{"concepto_libre": "Servicio de prueba", "cantidad": 2, "pvp": 1500.0},
              {"concepto_libre": "Otro ítem", "cantidad": 1, "pvp": 3000.0}]
    total = sum(l["cantidad"] * l["pvp"] for l in lineas)
    db.create_factura({"cliente_id": ids[0], "tipo": "FA", "ejercicio": ej,
                       "numero": db.siguiente_numero("FA", ej), "fecha": date.today().isoformat(),
                       "total": total}, lineas)
