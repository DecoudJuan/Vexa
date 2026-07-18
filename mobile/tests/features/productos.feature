# language: es
Característica: Catálogo de productos
  Como usuario de Vexa quiero mantener mi catálogo de productos
  con sus talles y precios para poder facturarlos y etiquetarlos.

  Escenario: Alta de un producto con varios talles
    Dado que no hay productos cargados
    Cuando doy de alta el producto "FAJA LUMBAR" código "020" talles "1, 2, 3" precio 9800
    Entonces hay 1 producto en el catálogo
    Y el producto "FAJA LUMBAR" tiene los talles "1, 2, 3"

  Escenario: Alta de un producto universal sin talles
    Dado que no hay productos cargados
    Cuando doy de alta el producto "HOMBRERA" código "026" talles "" precio 7200
    Entonces hay 1 producto en el catálogo
    Y el producto "HOMBRERA" figura como universal

  Escenario: No se puede crear un producto con precio cero
    Dado que no hay productos cargados
    Cuando intento dar de alta el producto "SIN PRECIO" código "099" talles "" precio 0
    Entonces la operación es rechazada con un aviso de precio inválido
    Y hay 0 productos en el catálogo

  Escenario: No se puede crear un producto sin nombre
    Dado que no hay productos cargados
    Cuando intento dar de alta el producto "" código "099" talles "" precio 100
    Entonces la operación es rechazada con un aviso de dato obligatorio

  Escenario: Editar el precio de un producto
    Dado el producto "FAJA LUMBAR" código "020" talles "1, 2" precio 9800
    Cuando cambio el precio del producto "FAJA LUMBAR" a 10500
    Entonces el producto "FAJA LUMBAR" tiene precio 10500

  Escenario: Borrar un producto del catálogo
    Dado el producto "FAJA LUMBAR" código "020" talles "1" precio 9800
    Cuando borro el producto "FAJA LUMBAR" código "020"
    Entonces hay 0 productos en el catálogo
