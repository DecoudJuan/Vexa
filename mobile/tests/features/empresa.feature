# language: es
Característica: Datos de la empresa y configuración
  Como usuario de Vexa quiero configurar los datos de mi empresa y la moneda
  para que aparezcan en los comprobantes.

  Escenario: Guardar une la calle y el número en la dirección
    Dado que la base está recién inicializada
    Cuando guardo la empresa "Mi Empresa" con calle "9 de Julio" número "10"
    Entonces la dirección guardada es "9 de Julio 10"

  Escenario: Guardar sin número deja solo la calle
    Dado que la base está recién inicializada
    Cuando guardo la empresa "Mi Empresa" con calle "Ruta 8" número ""
    Entonces la dirección guardada es "Ruta 8"

  Escenario: No se puede guardar la empresa sin nombre
    Dado que la base está recién inicializada
    Cuando intento guardar la empresa sin nombre
    Entonces la operación es rechazada con un aviso de dato obligatorio

  Escenario: Cambiar la moneda
    Dado que la base está recién inicializada
    Cuando guardo la empresa "Mi Empresa" con la moneda "US$"
    Entonces la moneda guardada es "US$"
