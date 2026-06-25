# Reglas de estabilidad — Banca

Este documento es obligatorio antes de tocar código en producción o en cambios sensibles.

## Checklist antes de cada cambio

```bash
pytest
python -m compileall .
```

Ambos deben pasar sin errores. Si algo falla, **no desplegar** hasta corregir o revertir.

## Reglas de alcance

1. **No tocar módulos no relacionados** con la tarea actual.
2. **No cambiar ventas** si el cambio es de resultados o ganadores.
3. **No cambiar pagos** si el cambio es solo visual o de resultados.
4. **No borrar datos reales** (tickets, premios pagados, resultados confirmados) sin backup y confirmación explícita.
5. **No modificar la base de datos** sin backup automático (`stability_guard.db_backup_before_dangerous_op`).
6. **No cambiar varias cosas a la vez** — un commit = un propósito.
7. **Después de cada cambio**, correr `pytest` y `python -m compileall .`.
8. **Si algo falla**, revertir solo el último cambio (git revert o deshacer el diff), no “arreglar encima” sin entender la causa.

## Pruebas smoke (`tests/test_smoke_app.py`)

Cubren rutas críticas sin modificar lógica de negocio:

| Prueba | Qué valida |
|--------|------------|
| `/health` | 200, sin error |
| `/` (login) | 200, sin traceback |
| `/admin` | 200 con sesión admin |
| `/venta` | 200 con sesión cajero |
| `/ganadores` | 200 o redirect esperado |
| `/actualizar_resultados` | redirect, no 500 |
| `/api/ganadores` | JSON `ok` con sesión |
| `/api/ventas_cajeros` | 200 con sesión staff |

## Backups automáticos

Se crean en la carpeta `backups/` (o `BACKUP_DIR`) antes de:

- Migraciones / `init_db` (SQLite existente)
- Recalcular ganadores (`/api/recalcular_ganadores_fecha`, `/admin/ganadores_recalc_hoy`)
- Recalcular premios del día (`recalcular_premios_dia_seguro`, si no es `dry_run`)

Desactivar solo en desarrollo local si hace falta: `DISABLE_DB_BACKUP=1`.

## Resultados / Conectate

- Fallo del scraper **no** debe tumbar `/ganadores` ni el dashboard.
- Si el scrape no trae datos nuevos, **se conserva** la caché y los resultados ya guardados en BD.
- La tarjeta «Resultados de Hoy» muestra el **último publicado** (gris) hasta que haya fecha de hoy (verde).

## Hora y fecha (America/Santo_Domingo)

- Toda lógica crítica usa `ahora_rd()` → `datetime.now(ZoneInfo("America/Santo_Domingo"))` en el **servidor**.
- El navegador/teléfono **no** define `fecha_sorteo`, cierre de loterías, pagos ni resultados guardados.
- Parámetros `fecha` / `fecha_premios` en URL o JSON solo sirven para **consultar** otro día (validados y acotados).
- Visualización: opcional `GET /api/hora_servidor` (solo mostrar; el backend no confía en ese valor al guardar).

## Qué evitar

- Rediseños o refactors grandes “de paso”.
- Optimizaciones globales no pedidas.
- Invalidar caché de ganadores cuando el scraper falla.
- Commits que mezclen ventas + pagos + resultados sin necesidad.
