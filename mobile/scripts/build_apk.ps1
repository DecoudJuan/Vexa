# Build de la APK de Vexa FIRMADO con la clave de release del proyecto.
#
# Por qué: Android solo deja ACTUALIZAR una app encima de la instalada si el APK
# nuevo está firmado con la MISMA clave. Si la firma cambia, hay que desinstalar
# (y se pierden los datos del usuario). Este script firma siempre con
# `mobile/signing/vexa-release.keystore` — la misma clave que firmó todas las
# releases hasta hoy (cert SHA256 99:9D:DC:D8:...:5D:A3) — así las actualizaciones
# conservan los datos.
#
# Uso:   powershell -ExecutionPolicy Bypass -File scripts\build_apk.ps1
#        (por defecto compila las 3 ABIs con --split-per-abi; se le pueden pasar
#         otros flags de `flet build`, ej. `... build_apk.ps1 --arch arm64-v8a`)
#
# NOTA: el keystore NO se versiona (está gitignoreado). Guardá un backup: si se
# pierde, no vas a poder publicar actualizaciones que conserven los datos.

$ErrorActionPreference = "Stop"
$mobile   = Split-Path -Parent $PSScriptRoot          # carpeta mobile/
$keystore = Join-Path $mobile "signing\vexa-release.keystore"

if (-not (Test-Path $keystore)) {
    Write-Error "Falta el keystore en $keystore. Copiá ahi tu backup de vexa-release.keystore."
    exit 1
}

$env:PYTHONUTF8 = "1"          # flet build crashea con rich en consola legacy sin esto
$env:PYTHONIOENCODING = "utf-8"

Push-Location $mobile
try {
    python scripts/vendor_core.py     # regenera src/vexa_core desde el core raiz
    # @(...) fuerza array: un if-expression de 1 elemento se desenrolla a string y
    # el splat lo pasaba letra por letra ("- s p l i t ...").
    $abi = @(if ($args.Count -gt 0) { $args } else { "--split-per-abi" })
    flet build apk @abi `
        --android-signing-key-store            $keystore `
        --android-signing-key-store-password   android `
        --android-signing-key-password         android `
        --android-signing-key-alias            androiddebugkey
    Write-Host "`nAPK(s) firmadas en: $(Join-Path $mobile 'build\apk')" -ForegroundColor Green
} finally {
    Pop-Location
}
