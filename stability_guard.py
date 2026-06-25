"""
Protecciones de estabilidad: backup de BD y utilidades compartidas.
No altera lógica de negocio; solo salvaguardas operativas.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from datetime import datetime

log = logging.getLogger(__name__)


def backup_dir() -> str:
    base = os.environ.get("BACKUP_DIR") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "backups"
    )
    os.makedirs(base, exist_ok=True)
    return base


def db_backup_before_dangerous_op(label: str) -> str | None:
    """
    Copia SQLite o intenta pg_dump antes de operaciones peligrosas.
    Devuelve ruta del backup o None si no se pudo / está deshabilitado.
    """
    if os.environ.get("DISABLE_DB_BACKUP", "").strip().lower() in ("1", "true", "yes"):
        return None
    if (
        (label or "").strip() == "init_db_migraciones"
        and not os.environ.get("DATABASE_URL")
        and os.environ.get("INIT_DB_SKIP_BACKUP", "1").strip().lower() in ("1", "true", "yes")
    ):
        log.info("[BACKUP] omitido en init_db local (INIT_DB_SKIP_BACKUP)")
        return None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in (label or "op"))[:48]
    dest_dir = backup_dir()

    pg_url = (os.environ.get("DATABASE_URL") or "").strip()
    if pg_url:
        dest = os.path.join(dest_dir, f"pg_{safe}_{ts}.sql")
        pg_dump = shutil.which("pg_dump")
        if not pg_dump:
            log.warning("[BACKUP] pg_dump no disponible; omitido label=%s", label)
            return None
        try:
            with open(dest, "w", encoding="utf-8", errors="replace") as out:
                r = subprocess.run(
                    [pg_dump, pg_url],
                    stdout=out,
                    stderr=subprocess.PIPE,
                    timeout=int(os.environ.get("BACKUP_PG_TIMEOUT_SEC", "120")),
                    check=False,
                )
            if r.returncode != 0:
                log.warning(
                    "[BACKUP] pg_dump falló rc=%s label=%s stderr=%s",
                    r.returncode,
                    label,
                    (r.stderr or b"")[:500],
                )
                try:
                    os.remove(dest)
                except OSError:
                    pass
                return None
            log.info("[BACKUP] PostgreSQL guardado: %s (label=%s)", dest, label)
            return dest
        except Exception as e:
            log.warning("[BACKUP] pg_dump error label=%s: %s", label, e)
            return None

    src = os.environ.get("SQLITE_DB", "banca.db")
    if not os.path.isfile(src):
        log.debug("[BACKUP] SQLite no existe aún: %s", src)
        return None
    try:
        if os.path.getsize(src) < 1:
            return None
    except OSError:
        return None
    dest = os.path.join(dest_dir, f"sqlite_{safe}_{ts}.db")
    try:
        shutil.copy2(src, dest)
        log.info("[BACKUP] SQLite copiado: %s (label=%s)", dest, label)
        return dest
    except Exception as e:
        log.warning("[BACKUP] SQLite copy falló label=%s: %s", label, e)
        return None
