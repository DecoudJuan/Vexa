# language: es
Característica: Configuración de AFIP
  Como usuario de Vexa quiero cargar mis datos fiscales de AFIP/ARCA
  para poder facturar electrónicamente. (No se prueba la conexión en vivo.)

  Escenario: Cargar los datos de AFIP y que persistan
    Dado que la base está recién inicializada
    Cuando cargo los datos de AFIP con punto de venta "0001" en entorno "produccion"
    Entonces AFIP queda habilitado
    Y el punto de venta guardado es "0001"
    Y el entorno de AFIP guardado es "produccion"

  Escenario: El interruptor de AFIP persiste al reabrir
    Dado que la base está recién inicializada
    Cuando activo AFIP y guardo
    Entonces al reabrir la configuración de AFIP figura habilitado
