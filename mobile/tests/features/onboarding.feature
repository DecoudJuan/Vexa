# language: es
Característica: Primera ejecución (onboarding)
  Como usuario nuevo quiero cargar los datos de mi empresa la primera vez
  para que la app quede lista para facturar.

  Escenario: Con la base vacía se pide el onboarding
    Dado que la base está recién inicializada
    Entonces la app pide completar el onboarding

  Escenario: Guardar los datos de la empresa cierra el onboarding
    Dado que la base está recién inicializada
    Cuando completo el onboarding con la empresa "Kinesio SRL" en "San Martín" "500"
    Entonces la empresa guardada se llama "Kinesio SRL"
    Y la app ya no pide el onboarding

  Escenario: Guardar sin nombre deja el onboarding pendiente
    Dado que la base está recién inicializada
    Cuando completo el onboarding sin nombre de empresa
    Entonces la app pide completar el onboarding
    Y la app no se rompió
