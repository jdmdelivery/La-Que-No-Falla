#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recalcula premios pendientes de un día tras corregir el cruce con `resultados`.

- Pendientes inconsistentes: se eliminan y se vuelve a sincronizar con la lógica actual.
- Pagados inconsistentes: NO se borran ni se altera el monto; se registra en `premios_inconsistentes`.

Uso:
  python scripts/recalcular_premios_dia.py --fecha 2026-05-05
  python scripts/recalcular_premios_dia.py --fecha 2026-05-05 --dry-run
  set SQLITE_DB=banca.db && python scripts/recalcular_premios_dia.py --fecha 2026-05-05
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main():
    parser = argparse.ArgumentParser(
        description="Recalcular premios del día (seguro: no toca pagados salvo auditoría)."
    )
    parser.add_argument(
        "--fecha",
        required=True,
        help="Fecha RD en formato YYYY-MM-DD (ej. 2026-05-05 para sorteo del 05-05)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo simula: no borra, no inserta auditoría ni premios nuevos",
    )
    parser.add_argument(
        "--cajero",
        default="",
        help="Opcional: limitar a premios de ese cajero (misma lógica que sync)",
    )
    parser.add_argument("--json", action="store_true", help="Salida solo JSON")
    args = parser.parse_args()

    import app

    conn = app.db()
    if not conn:
        print("ERROR: no hay conexión a la base de datos.", file=sys.stderr)
        sys.exit(2)

    try:
        res = app.recalcular_premios_dia_seguro(
            conn,
            args.fecha,
            dry_run=args.dry_run,
            cajero_username=(args.cajero or None),
        )
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        sys.exit(0 if res.get("ok") else 1)

    print("=== Recálculo premios día %s ===" % res.get("fecha"))
    print("Dry-run:", res.get("dry_run"))
    print("OK:", res.get("ok"))
    if res.get("message"):
        print("Mensaje:", res.get("message"))
    print("Premios pendientes eliminados (inconsistentes):", res.get("eliminados_pendiente"))
    print("Premios insertados por sync:", res.get("insertados_sync"))
    print("Premios pagados marcados inconsistentes (auditoría):", res.get("pagados_inconsistentes"))
    print("Premios omitidos (ya en premios_inconsistentes):", res.get("omitidos_ya_auditados"))
    print("Premios consistentes (sin acción):", res.get("consistentes"))
    print(
        "Monto total premios pagados afectados (RD$):",
        "%.2f" % float(res.get("monto_total_pagado_afectado") or 0),
    )
    sys.exit(0 if res.get("ok") else 1)


if __name__ == "__main__":
    main()
