#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Limpieza masiva: columnas `draw` → formato estándar «H:MM AM/PM» (900pm → 9:00 PM, etc.).

Esta app no usa `tickets.sorteo` ni `resultados.sorteo`; las horas de sorteo están en `draw` en:
  ticket_lines, resultados, lotteries, premios, limites_numeros

Uso (desde la raíz del proyecto, mismo entorno que la app):
  python scripts/limpiar_horarios_sorteo_db.py
  python scripts/limpiar_horarios_sorteo_db.py --dry-run

Backup obligatorio antes de escribir (SQLite: copia del archivo; PostgreSQL: pg_dump).
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BACKUP_DIR = ROOT / "backups"


def _backup_sqlite(db_path: Path) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"sqlite_pre_horarios_{ts}_{db_path.name}"
    shutil.copy2(db_path, dest)
    return dest


def _backup_postgres(database_url: str) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_DIR / f"pg_pre_horarios_{ts}.dump"
    exe = shutil.which("pg_dump")
    if not exe:
        raise RuntimeError(
            "pg_dump no está en PATH; instala PostgreSQL client tools o exporta un snapshot manual."
        )
    r = subprocess.run(
        [exe, "--dbname", database_url, "--format", "custom", "--file", str(dest)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"pg_dump falló: {r.stderr or r.stdout}")
    return dest


def _row_dict(row, pk: str):
    if hasattr(row, "keys"):
        return dict(row)
    return None


# Equivalencia a «sin ':' y con 3–4 dígitos seguidos de am/pm» (900pm, 1230pm)
def _tiene_compacto_sin_dos_puntos(draw: str) -> bool:
    s = (draw or "").strip()
    if not s or ":" in s:
        return False
    return bool(re.search(r"(?i)[0-9]{3,4}\s*(a\.?m\.?|p\.?m\.?)", s))


_RE_SOLO_24H = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _es_solo_24h(draw: str) -> bool:
    s = (draw or "").strip()
    return bool(s and _RE_SOLO_24H.match(s))


def migrate_tables(cur, sql_fn, dry_run: bool) -> int:
    from app import (
        _draw_efectivo_jugada,
        _loteria_texto_sin_hora_embebida,
        draw_almacen_canonico,
    )

    tables = (
        ("ticket_lines", "id"),
        ("resultados", "id"),
        ("lotteries", "id"),
        ("premios", "id"),
        ("limites_numeros", "id"),
    )
    n_changes = 0
    for table, pk in tables:
        try:
            cur.execute(sql_fn(f"SELECT {pk}, lottery, draw FROM {table}"))
            rows = cur.fetchall() or []
        except Exception as e:
            print(f"[omitir] {table}: {e}")
            continue
        for row in rows:
            d = _row_dict(row, pk)
            if d is None:
                rid = row[0]
                lot = row[1] if len(row) > 1 else ""
                dr = row[2] if len(row) > 2 else ""
            else:
                rid = d.get(pk)
                lot = d.get("lottery")
                dr = d.get("draw")
            if rid is None:
                continue
            new_l = _loteria_texto_sin_hora_embebida(lot) or (str(lot or "").strip())
            eff = _draw_efectivo_jugada(lot, dr)
            new_d = draw_almacen_canonico(eff) if eff else draw_almacen_canonico(dr)
            if not new_d and (dr or "").strip():
                new_d = str(dr or "").strip()
            old_l = str(lot or "").strip()
            old_d = str(dr or "").strip()
            if old_l == new_l and old_d == new_d:
                continue
            print(
                f"Actualizado [{table} id={rid}]: "
                f"lottery {old_l!r} → {new_l!r} | draw {old_d!r} → {new_d!r}"
            )
            n_changes += 1
            if not dry_run:
                cur.execute(
                    sql_fn(f"UPDATE {table} SET lottery = %s, draw = %s WHERE {pk} = %s"),
                    (new_l, new_d, rid),
                )
    return n_changes


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalizar columnas draw a H:MM AM/PM")
    parser.add_argument("--dry-run", action="store_true", help="Muestra cambios sin backup ni UPDATE")
    args = parser.parse_args()

    os.chdir(ROOT)

    import app as app_module

    from app import db

    sql_fn = app_module._sql
    database_url = os.environ.get("DATABASE_URL")

    conn = db()
    if not conn:
        print("No se pudo conectar a la base de datos.", file=sys.stderr)
        return 2

    if args.dry_run:
        print("MODO --dry-run: sin backup ni escritura.")
        try:
            cur = conn.cursor()
            n = migrate_tables(cur, sql_fn, dry_run=True)
            print(f"Filas que se actualizarían: {n}")
        finally:
            try:
                conn.close()
            except Exception:
                pass
        return 0

    if database_url:
        print("Creando backup PostgreSQL (custom format)…")
        dest = _backup_postgres(database_url)
        print(f"Backup: {dest}")
    else:
        db_path = Path(os.environ.get("SQLITE_DB", "banca.db")).resolve()
        if not db_path.is_file():
            print(f"No existe {db_path}; define SQLITE_DB o DATABASE_URL.", file=sys.stderr)
            try:
                conn.close()
            except Exception:
                pass
            return 2
        print(f"Backup SQLite desde {db_path}…")
        dest = _backup_sqlite(db_path)
        print(f"Backup: {dest}")

    try:
        cur = conn.cursor()
        n = migrate_tables(cur, sql_fn, dry_run=False)
        conn.commit()
        print(f"Filas actualizadas: {n}")
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"Error durante migración: {e}", file=sys.stderr)
        return 2
    finally:
        try:
            conn.close()
        except Exception:
            pass

    conn2 = db()
    if not conn2:
        return 0
    try:
        cur2 = conn2.cursor()
        bad_compact = 0
        bad_24h = 0
        samples: list[str] = []
        tables = (
            "ticket_lines",
            "resultados",
            "lotteries",
            "premios",
            "limites_numeros",
        )
        for table in tables:
            try:
                cur2.execute(sql_fn(f"SELECT draw FROM {table} WHERE COALESCE(draw,'') <> ''"))
                for row in cur2.fetchall() or []:
                    dr = list(row.values())[0] if hasattr(row, "values") else row[0]
                    s = str(dr or "").strip()
                    if _tiene_compacto_sin_dos_puntos(s):
                        bad_compact += 1
                        if len(samples) < 25:
                            samples.append(f"{table}: {s!r}")
                    if _es_solo_24h(s):
                        bad_24h += 1
                        if len(samples) < 25:
                            samples.append(f"{table} (HH:MM 24h): {s!r}")
            except Exception:
                continue
        print("--- Validación (equivalente a buscar 900pm / 1230pm sin ':') ---")
        print(f"Registros sospechosos (compacto sin ':'): {bad_compact}")
        print(f"Registros solo 24h HH:MM: {bad_24h}")
        if samples:
            for ln in samples:
                print(" ", ln)
        if bad_compact or bad_24h:
            print("Revisar muestras anteriores.", file=sys.stderr)
            return 1
        print("OK: barrido sin compactos tipo 900pm ni draw exclusivamente 24h.")
    finally:
        try:
            conn2.close()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
