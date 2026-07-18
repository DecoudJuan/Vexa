# language: es
Característica: Gestión de clientes
  Como usuario de Vexa quiero administrar mi cartera de clientes
  para poder facturarles y mantener sus datos.

  Escenario: Alta de un cliente completo con varios CUIT
    Dado que no hay clientes cargados
    Cuando doy de alta un cliente "Kinesio Central" en "Rosario" con CUITs "20-11111111-2, 27-22222222-3"
    Entonces hay 1 cliente cargado
    Y el cliente "Kinesio Central" tiene los CUITs "20-11111111-2, 27-22222222-3"
    Y el CUIT principal del cliente "Kinesio Central" es "20-11111111-2"

  Escenario: No se puede crear un cliente sin nombre
    Dado que no hay clientes cargados
    Cuando intento dar de alta un cliente sin nombre
    Entonces la operación es rechazada con un aviso de dato obligatorio
    Y hay 0 clientes cargados

  Escenario: Editar un cliente existente no lo duplica
    Dado un cliente llamado "Kinesio Central" en "Rosario"
    Cuando renombro ese cliente a "Kinesio Norte" en "Córdoba"
    Entonces hay 1 cliente cargado
    Y existe un cliente llamado "Kinesio Norte"

  Escenario: Borrar un cliente lo saca de la cartera
    Dado un cliente llamado "Para borrar" en "Rosario"
    Cuando borro ese cliente
    Entonces hay 0 clientes cargados

  Escenario: Buscar filtra la lista por nombre
    Dado un cliente llamado "Kinesio Central" en "Rosario"
    Y un cliente llamado "Ortopedia Sur" en "Santa Fe"
    Cuando busco clientes por "kinesio"
    Entonces la lista de clientes muestra 1 resultado

  # Regresión del bug reportado: al confirmar el borrado en el formulario, la
  # pantalla quedaba en negro (dos scrims desmontándose a la vez). El fix secuencia
  # los cierres; este escenario ejercita ese flujo completo por el árbol real.
  Escenario: Borrar un cliente desde el formulario no deja la pantalla en negro
    Dado un cliente llamado "Para borrar" en "Rosario"
    Cuando abro el formulario del cliente y confirmo el borrado
    Entonces hay 0 clientes cargados
    Y la app queda montada sin diálogos ni scrim colgados
