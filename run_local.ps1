# Arranca Banca en local (SQLite) antes de subir a Render.
# Uso: clic derecho -> "Ejecutar con PowerShell", o en terminal: .\run_local.ps1

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

Write-Host "Instalando dependencias (requirements.txt) ..." -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit 1 }

# Local: SQLite (sin DATABASE_URL). Render usa PostgreSQL via DATABASE_URL.
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
$env:PORT = "5000"
$env:FLASK_DEBUG = "1"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Banca local: http://127.0.0.1:5000" -ForegroundColor Green
Write-Host "  Ganadores:   http://127.0.0.1:5000/ganadores" -ForegroundColor Green
Write-Host "  Ctrl+C para detener" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

& $venvPython app.py
