# Checklist pre-deploy — validación de sorteos y premios

## 1. Debug temporal

Tras el deploy, activar en el entorno (quitar en cuanto el monitoreo confirme estabilidad):

- `DEBUG_VALIDACION_SORTEO=1`

## 2. Logs a vigilar

Buscar líneas `[VALIDANDO]` con:

- `estado=ok`
- `estado=no_encontrado`
- `estado=duplicado_sorteo`

## 3. Lo que no debería aparecer en producción estable

- `JOIN mismatch` o `resultado usado distinto` (indica fila JOIN incoherente con el triple oficial).
- Pagos inesperados: revisar alertas de `pagos_premios` / auditoría y premios inconsistentes.

## 4. Unicidad en `resultados`

Tras `init_db`, existe el índice `resultados_unique_norm` sobre
`(normalized_lottery, normalized_draw, fecha_rd)`, alineado con la resolución estricta en Python.
Impide duplicados lógicos del mismo sorteo aunque varíe el texto de `lottery`/`draw`.

## 5. Métricas en proceso

Función `sorteo_validacion_metricas()` en `app.py`:

- `premios_incorrectos_detectados`
- `duplicado_sorteo_detectado`
- `resultado_no_encontrado`

Son contadores en memoria del proceso (reinicio los pone a cero). Para tests: `sorteo_validacion_metricas_reset()`.

## 6. Recálculo histórico (antes de tocar producción)

Dry-run (no escribe premios ni auditoría):

```bash
set SQLITE_DB=ruta\banca.db
python scripts/recalcular_premios_dia.py --fecha YYYY-MM-DD --dry-run
```

En PostgreSQL, configurar `DATABASE_URL` y el mismo comando.

En Windows, si `DATABASE_URL` apunta a un valor inválido de otro entorno, quitarla temporalmente para forzar SQLite local:

`Remove-Item Env:DATABASE_URL` (PowerShell) antes de fijar `SQLITE_DB`.

Revisar el resumen; si es coherente, repetir sin `--dry-run` solo cuando corresponda el cambio real.
