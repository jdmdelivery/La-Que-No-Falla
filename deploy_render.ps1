param(
    [string]$DeployHookUrl = "",
    [switch]$SkipLocalChecks
)

# Deploy a Render - Banca
# Requiere: repo Git conectado a Render O RENDER_DEPLOY_HOOK_URL en el entorno.
#
# Uso:
#   .\deploy_render.ps1 -DeployHookUrl "https://api.render.com/deploy/srv-...?key=..."
#   .\deploy_render.ps1                      # con validacion local obligatoria
#   .\deploy_render.ps1 -SkipLocalChecks     # solo emergencia
#   o: $env:RENDER_DEPLOY_HOOK_URL = "..." ; .\deploy_render.ps1
#
# Variables en Render Dashboard (Environment):
#   LOG_LEVEL=INFO, PYTHONUNBUFFERED=1, ENABLE_RESULTADOS_SCHEDULER=1
#   DEBUG_RESULTADOS_KEY=<clave>, DATABASE_URL=<postgres>, APP_BUILD_ID=2026-05-28-fase2-ganadores-banco

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not $SkipLocalChecks) {
    $precheckScript = Join-Path $PSScriptRoot "pre_deploy_local.ps1"
    if (-not (Test-Path $precheckScript)) {
        Write-Host "ERROR: falta pre_deploy_local.ps1. No se puede validar en local." -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "Ejecutando validacion local obligatoria..." -ForegroundColor Cyan
    & $precheckScript
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Deploy cancelado: la validacion local no paso." -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Deploy Render - Banca" -ForegroundColor Cyan
Write-Host "  Produccion: https://banca-la-que-nunca-falla.onrender.com" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Variables recomendadas en Render Dashboard:" -ForegroundColor Yellow
@(
    "APP_BUILD_ID=2026-05-28-fase2-ganadores-banco",
    "LOG_LEVEL=INFO",
    "PYTHONUNBUFFERED=1",
    "ENABLE_RESULTADOS_SCHEDULER=1",
    "RESULTADOS_SCHEDULER_FIRST_DELAY_SEC=120",
    "AUTO_SYNC_GANADORES_ON_RESULTADOS=1",
    "DEBUG_RESULTADOS_KEY=<tu-clave-secreta>"
) | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }

$hook = $DeployHookUrl
if (-not $hook) { $hook = $env:RENDER_DEPLOY_HOOK_URL }
if (-not $hook -and (Test-Path ".render-deploy-hook.local")) {
    $hook = (Get-Content ".render-deploy-hook.local" -Raw).Trim()
}
if (-not $hook) {
    Write-Host ""
    Write-Host "Sin RENDER_DEPLOY_HOOK_URL." -ForegroundColor Yellow
    Write-Host "Opciones:" -ForegroundColor Yellow
    Write-Host "  A) Push al repo Git conectado a Render" -ForegroundColor White
    Write-Host "  B) Render Dashboard: Manual Deploy" -ForegroundColor White
    Write-Host "  C) Settings / Deploy Hook: guardar URL en .render-deploy-hook.local o pasar -DeployHookUrl" -ForegroundColor White
    Write-Host ""
    exit 0
}

Write-Host ""
Write-Host "Disparando deploy hook..." -ForegroundColor Cyan
try {
    $resp = Invoke-WebRequest -Uri $hook -Method POST -UseBasicParsing -TimeoutSec 60
    Write-Host "Deploy iniciado. HTTP $($resp.StatusCode)" -ForegroundColor Green
    if ($resp.Content) { Write-Host $resp.Content }
} catch {
    Write-Host "Error al disparar deploy: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Esperando health check (max 3 min)..." -ForegroundColor Cyan
$healthUrl = "https://banca-la-que-nunca-falla.onrender.com/health"
$buildTag = "2026-05-28-fase2-ganadores-banco"
$deadline = (Get-Date).AddMinutes(3)
do {
    Start-Sleep -Seconds 15
    try {
        $h = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 30
        if ($h.StatusCode -eq 200 -and ($h.Content -match "ok")) {
            $body = $h.Content.Trim()
            Write-Host "Health OK: $healthUrl -> $body" -ForegroundColor Green
            if ($body -match $buildTag) {
                Write-Host "Build fase2 confirmado en produccion." -ForegroundColor Green
            } else {
                Write-Host "AVISO: /health aun no muestra build fase2. Espera el deploy o sube el codigo al repo de Render." -ForegroundColor Yellow
            }
            break
        }
    } catch {
        Write-Host "  Esperando servicio..." -ForegroundColor Gray
    }
} while ((Get-Date) -lt $deadline)

Write-Host ""
Write-Host "Verificacion post-deploy:" -ForegroundColor Cyan
Write-Host "  1. GET /health  debe decir: ok build=2026-05-28-fase2-ganadores-banco" -ForegroundColor White
Write-Host "  2. /admin/banco  sync ventas/premios" -ForegroundColor White
Write-Host "  3. /ganadores    quick_sync" -ForegroundColor White
Write-Host "  4. /api/debug/ganadores?ticket=ID&key=DEBUG_RESULTADOS_KEY" -ForegroundColor White
Write-Host "  5. Logs Render: [GANADORES] [BANCO] [RESULTADOS]" -ForegroundColor White
Write-Host ""
