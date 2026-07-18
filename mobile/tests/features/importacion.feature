# language: es
Característica: Importación de listas de precios
  Como usuario de Vexa quiero importar mi lista de precios desde Excel o CSV
  para cargar el catálogo sin tipear producto por producto.

  Escenario: Importar un CSV agrupa los talles de un mismo producto
    Dado un archivo CSV de lista de precios con dos talles de "FAJA LUMBAR" y un "CALZA REDUCTORA"
    Cuando confirmo la importación
    Entonces hay 2 productos en el catálogo
    Y el producto "FAJA LUMBAR" tiene los talles "1, 2"

  Escenario: Importar un XLSX toma la primera hoja
    Dado un archivo XLSX con la hoja "Precios" con 2 productos y una hoja "Otra"
    Cuando confirmo la importación
    Entonces hay 2 productos en el catálogo

  Escenario: Importar en modo reemplazo vacía el catálogo previo
    Dado el producto "VIEJO" código "999" talles "" precio 1
    Y un archivo CSV de lista de precios con dos talles de "FAJA LUMBAR" y un "CALZA REDUCTORA"
    Cuando activo el modo reemplazo
    Y confirmo la importación
    Entonces el catálogo no contiene el producto "VIEJO"

  Escenario: Sin columnas mapeadas no se importa nada
    Dado un archivo CSV de lista de precios con dos talles de "FAJA LUMBAR" y un "CALZA REDUCTORA"
    Cuando quito todo el mapeo de columnas
    Y confirmo la importación
    Entonces hay 0 productos en el catálogo
