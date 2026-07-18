"""Pasos Gherkin — Importación de listas de precios (features/importacion.feature)."""
from __future__ import annotations

from pytest_bdd import scenarios, given, when, parsers

from views.import_productos import ImportProductosView

scenarios("features/importacion.feature")


def _view(app, context):
    if "import_view" not in context:
        context["import_view"] = ImportProductosView(app, context["path"])
    return context["import_view"]


@given("un archivo CSV de lista de precios con dos talles de \"FAJA LUMBAR\" y un \"CALZA REDUCTORA\"")
def _csv(tmp_path, context):
    p = tmp_path / "lista.csv"
    p.write_text("nombre,precio,codigo,talle\n"
                 "FAJA LUMBAR,9800,020,1\n"
                 "FAJA LUMBAR,9800,020,2\n"
                 "CALZA REDUCTORA,12400,060,\n", encoding="utf-8")
    context["path"] = str(p)


@given("un archivo XLSX con la hoja \"Precios\" con 2 productos y una hoja \"Otra\"")
def _xlsx(tmp_path, context):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Precios"
    ws.append(["nombre", "precio", "codigo"])
    ws.append(["GUANTE", "500", "G1"])
    ws.append(["MEDIA", "300", "M1"])
    wb.create_sheet("Otra").append(["basura"])
    p = tmp_path / "cat.xlsx"
    wb.save(str(p))
    context["path"] = str(p)


@when("activo el modo reemplazo")
def _replace(app, context):
    _view(app, context)._imp["replace"] = True


@when("quito todo el mapeo de columnas")
def _sin_mapeo(app, context):
    _view(app, context)._imp["mapeo"] = {"nombre": None, "precio": None,
                                         "codigo": None, "talle": None}


@when("confirmo la importación")
def _confirmo(app, context):
    _view(app, context)._confirmar()
