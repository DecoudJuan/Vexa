"""Pasos Gherkin — Gestión de clientes (features/clientes.feature).

El escenario de borrado dispara el flujo REAL de `open_form` recorriendo el árbol
de controles (tacho → confirmar "Eliminar"), para validar que la secuencia de cierres
no deja la pantalla en negro."""
from __future__ import annotations

from pytest_bdd import scenarios, when, then, parsers

from views.clientes import ClientesView

scenarios("features/clientes.feature")


# --------------------------------------------------------------- helpers de árbol
def _walk(ctrl):
    """Recorre el árbol de controles Flet (content + controls) en profundidad."""
    stack = [ctrl]
    while stack:
        c = stack.pop()
        if c is None:
            continue
        yield c
        cont = getattr(c, "content", None)
        if cont is not None:
            stack.append(cont)
        kids = getattr(c, "controls", None)
        if kids:
            stack.extend(kids)


def _buscar(root, pred):
    for c in _walk(root):
        try:
            if pred(c):
                return c
        except Exception:  # noqa: BLE001 — atributos ausentes en algunos controles
            pass
    return None


def _handler_es(c, nombre):
    """True si el on_click del control es la función llamada `nombre`."""
    return getattr(getattr(c, "on_click", None), "__name__", "") == nombre


def _es_boton_texto(c, texto):
    cont = getattr(c, "content", None)
    return getattr(c, "on_click", None) is not None \
        and getattr(cont, "value", None) == texto


# ------------------------------------------------------------------------- pasos
@when(parsers.re(r'doy de alta un cliente "(?P<nombre>[^"]*)" en "(?P<loc>[^"]*)" '
                 r'con CUITs "(?P<cuits>[^"]*)"'))
def _alta(app, nombre, loc, cuits):
    lista = [c.strip() for c in cuits.split(",") if c.strip()]
    ClientesView(app)._guardar(
        {"nombre": nombre, "localidad": loc, "cuits": lista,
         "condicion_iva": "Responsable Inscripto"}, {}, None)


@when("intento dar de alta un cliente sin nombre")
def _alta_sin_nombre(app, context):
    try:
        ClientesView(app)._guardar({"nombre": "  "}, {}, None)
    except ValueError as e:
        context["error"] = e


@then(parsers.re(r'el cliente "(?P<nombre>[^"]*)" tiene los CUITs "(?P<cuits>[^"]*)"'))
def _check_cuits(db, nombre, cuits):
    esperados = [c.strip() for c in cuits.split(",") if c.strip()]
    c = next(x for x in db.get_all_clientes() if x["nombre"] == nombre)
    assert db.get_cuits_cliente(c["id"]) == esperados


@then(parsers.parse('el CUIT principal del cliente "{nombre}" es "{cuit}"'))
def _check_cuit_principal(db, nombre, cuit):
    c = next(x for x in db.get_all_clientes() if x["nombre"] == nombre)
    assert c["nif"] == cuit


@when(parsers.parse('renombro ese cliente a "{nuevo}" en "{loc}"'))
def _renombrar(app, db, context, nuevo, loc):
    cid = context["cliente_id"]
    orig = db.get_cliente(cid)
    data = dict(orig)
    data.update(nombre=nuevo, localidad=loc, cuits=db.get_cuits_cliente(cid))
    ClientesView(app)._guardar(data, orig, cid)


@then(parsers.parse('existe un cliente llamado "{nombre}"'))
def _existe(db, nombre):
    assert any(c["nombre"] == nombre for c in db.get_all_clientes())


@when("borro ese cliente")
def _borro(db, context):
    db.delete_cliente(context["cliente_id"])


@when(parsers.parse('busco clientes por "{texto}"'))
def _busco(app, context, texto):
    v = ClientesView(app)
    v.build()
    v._fill(texto)
    context["view"] = v


@then(parsers.parse('la lista de clientes muestra {n:d} resultado'))
def _lista(context, n):
    assert len(context["view"].lista.controls) == n


@when("abro el formulario del cliente y confirmo el borrado")
def _borrar_por_form(app, db, context):
    ClientesView(app)._editar(db.get_cliente(context["cliente_id"]))
    form = app.page.last_dialog
    tacho = _buscar(form, lambda c: _handler_es(c, "_pedir_borrar"))
    assert tacho is not None, "no encontré el botón de borrar en el formulario"
    tacho.on_click(None)                       # abre la confirmación (segundo sheet)
    confirm = app.page.last_dialog
    boton = _buscar(confirm, lambda c: _es_boton_texto(c, "Eliminar"))
    assert boton is not None, "no encontré el botón 'Eliminar' en la confirmación"
    boton.on_click(None)                       # confirma → secuencia de cierres → render
