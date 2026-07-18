# language: es
Característica: Facturación
  Como usuario de Vexa quiero emitir facturas eligiendo cliente y productos
  para dejar registro de las ventas y generar el comprobante.

  Escenario: Emitir una factura a un cliente y producto existentes
    Dado un cliente llamado "Farmacia Belgrano" en "Córdoba"
    Y el producto "FAJA LUMBAR" código "020" talles "" precio 9800
    Cuando armo una factura para "Farmacia Belgrano" con 2 unidades del producto existente
    Y guardo la factura
    Entonces hay 1 factura emitida
    Y el total de la factura es 19600

  Escenario: Emitir una factura crea al cliente si no existe
    Dado que no hay clientes cargados
    Cuando armo una factura para el cliente nuevo "Cliente Nuevo" con un ítem libre "Servicio" a 1500 por 2 unidades
    Y guardo la factura
    Entonces hay 1 cliente cargado
    Y hay 1 factura emitida

  Escenario: Un ítem libre no crea un producto en el catálogo
    Dado que no hay productos cargados
    Cuando armo una factura para el cliente nuevo "Cliente X" con un ítem libre "Rodillera especial" a 1200 por 1 unidades
    Y guardo la factura
    Entonces hay 0 productos en el catálogo
    Y la factura incluye el ítem libre "Rodillera especial"

  Escenario: No se guarda una factura con un ítem en precio cero
    Dado que no hay clientes cargados
    Cuando armo una factura para el cliente nuevo "Cliente Z" con un ítem libre "Item sin precio" a 0 por 1 unidades
    Y guardo la factura
    Entonces no hay facturas emitidas
    Y se mostró un aviso al usuario

  Escenario: La factura toma la bonificación del cliente
    Dado un cliente llamado "Mayorista" en "Rosario" con bonificación 15
    Cuando elijo a "Mayorista" como cliente de una factura nueva
    Entonces la factura aplica una bonificación de 15

  Escenario: La numeración de facturas es correlativa
    Dado un cliente llamado "Farmacia Belgrano" en "Córdoba"
    Y el producto "FAJA LUMBAR" código "020" talles "" precio 9800
    Cuando emito 3 facturas al cliente "Farmacia Belgrano"
    Entonces los números de factura son correlativos sin huecos
