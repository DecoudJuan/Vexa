# language: es
Característica: Etiquetas
  Como usuario de Vexa quiero armar una cola de etiquetas por producto y talle
  para imprimir el pliego en PDF.

  Antecedentes:
    Dado el producto "FAJA LUMBAR" código "020" talles "1, 2, 3" precio 9800

  Escenario: Elegir un producto arma la primera fila de talle
    Cuando selecciono el producto "FAJA LUMBAR" para etiquetar
    Entonces hay 1 fila de talle
    Y la primera fila tiene talle "1"

  Escenario: Modificar talles y cantidades y sumarlas a la cola
    Cuando selecciono el producto "FAJA LUMBAR" para etiquetar
    Y pongo en la primera fila talle "2" cantidad 5
    Y agrego una fila con talle "3" cantidad 3
    Y sumo las filas a la cola
    Entonces la cola tiene 2 entradas
    Y la cola tiene 5 etiquetas del talle "2" y 3 del talle "3"

  Escenario: Borrar una entrada de la cola y limpiarla
    Cuando selecciono el producto "FAJA LUMBAR" para etiquetar
    Y sumo las filas a la cola
    Y sumo las filas a la cola
    Y borro la primera entrada de la cola
    Entonces la cola tiene 1 entradas
    Cuando limpio la cola
    Entonces la cola tiene 0 entradas

  Escenario: Generar el PDF de la cola
    Cuando selecciono el producto "FAJA LUMBAR" para etiquetar
    Y pongo en la primera fila talle "1" cantidad 14
    Y sumo las filas a la cola
    Y genero el PDF de etiquetas
    Entonces se entregó un archivo PDF
