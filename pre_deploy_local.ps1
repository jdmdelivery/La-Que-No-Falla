# Valida Banca localmente antes de subir a Render.
# Uso:
#   .\pre_deploy_local.ps1
#   .\pre_deploy_local.ps1 -SkipPipInstall

param(
    [switch]$SkipPipInstall
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "Creando entorno virtual .venv ..." -ForegroundColor Cyan
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: no se pudo crear .venv. Instale Python 3.10+ desde python.org" -ForegroundColor Red
        exit 1
    }
}

if (-not $SkipPipInstall) {
    Write-Host "Instalando dependencias (requirements.txt) ..." -ForegroundColor Cyan
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r requirements.txt
    & $venvPython -m pip install pytest
    if ($LASTEXITCODE -ne 0) { exit 1 }
}

# Forzar entorno local (SQLite) para validar lo mismo que corres en la PC.
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Validacion local antes de deploy" -ForegroundColor Cyan
Write-Host "  1) python -m compileall (codigo del proyecto)" -ForegroundColor Cyan
Write-Host "  2) pytest" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Compilando proyecto (sanity check)..." -ForegroundColor Cyan
@(
    "app.py",
    "database.py",
    "banco_general.py",
    "ticket_thermal.py",
    "scripts",
    "tests"
) | ForEach-Object {
    if (Test-Path $_) {
        & $venvPython -m compileall -q $_
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: compileall fallo en $_. Corrija antes de desplegar." -ForegroundColor Red
            exit 1
        }
    }
}

Write-Host ""
Write-Host "Ejecutando pruebas (pytest)..." -ForegroundColor Cyan
$prevErrorAction = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $venvPython -c "import pytest" *> $null
$pytestInstalled = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $prevErrorAction

if (-not $pytestInstalled) {
    Write-Host "ERROR: pytest no esta instalado en .venv. Ejecute .\\pre_deploy_local.ps1 sin -SkipPipInstall." -ForegroundColor Red
    exit 1
}
& $venvPython -m pytest
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: pytest fallo. No se debe desplegar a Render." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "OK: validacion local completada. Puede subir a Render." -ForegroundColor Green
Write-Host ""
