# Flujo recomendado: Local primero, Render despues

Este proyecto se debe actualizar siempre en este orden:

1. Probar en local (tu PC).
2. Validar codigo (`compileall` + `pytest`).
3. Subir a Render.

## Comandos

### 1) Abrir en local

```powershell
.\run_local.ps1
```

Tambien puedes usar doble clic en `run_local.bat`.

### 2) Validar antes de deploy

```powershell
.\pre_deploy_local.ps1
```

Este script:

- crea `.venv` si no existe
- instala dependencias
- fuerza modo local (sin `DATABASE_URL`)
- ejecuta `compileall` en el codigo del proyecto
- ejecuta `pytest`

Si algo falla, no debes desplegar.

### 3) Subir a Render

```powershell
.\deploy_render.ps1
```

`deploy_render.ps1` ahora ejecuta automaticamente `pre_deploy_local.ps1`.
Solo si la validacion local pasa, dispara el deploy en Render.

## Modo rapido (no recomendado)

Si necesitas saltar la validacion local en una emergencia:

```powershell
.\deploy_render.ps1 -SkipLocalChecks
```

Usalo solo de forma excepcional.
