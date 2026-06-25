# -*- coding: utf-8 -*-
"""
Conexión PostgreSQL profesional para Render:
- Pool con get_db() timeout 3s (no bloquea infinito)
- /health usa solo caché (HEALTH_DB_CACHE_SEC), sin tocar PostgreSQL
- test_connection() solo para /api/db_probe y refresh explícito
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
import traceback
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

log = logging.getLogger(__name__)

_PG_POOL = None
_PG_POOL_LOCK = None
_DB_READY_CACHE = {"ts": 0.0, "ok": True}


def _health_db_cache_sec() -> float:
    try:
        return max(5.0, min(300.0, float(os.environ.get("HEALTH_DB_CACHE_SEC", "30"))))
    except (TypeError, ValueError):
        return 30.0


def _get_lock():
    global _PG_POOL_LOCK
    if _PG_POOL_LOCK is None:
        _PG_POOL_LOCK = threading.Lock()
    return _PG_POOL_LOCK


def database_url() -> str:
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def pgsslmode() -> str:
    url = database_url()
    if not url:
        return (os.environ.get("PGSSLMODE") or "").strip()
    try:
        q = dict(parse_qsl(urlparse(url).query))
        if q.get("sslmode"):
            return str(q.get("sslmode") or "")
    except Exception:
        pass
    return (os.environ.get("PGSSLMODE") or "").strip()


def _with_sslmode(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return url
    try:
        parsed = urlparse(url)
        q = dict(parse_qsl(parsed.query))
        if q.get("sslmode"):
            return url
        sslm = (os.environ.get("PGSSLMODE") or "").strip()
        if not sslm:
            return url
        q["sslmode"] = sslm
        return urlunparse(parsed._replace(query=urlencode(q)))
    except Exception:
        return url


def _import_psycopg2_fresh():
    import importlib

    mod = sys.modules.get("psycopg2")
    if mod is not None and not hasattr(mod, "connect"):
        try:
            del sys.modules["psycopg2"]
        except Exception:
            pass
        for k in list(sys.modules.keys()):
            if k.startswith("psycopg2."):
                try:
                    del sys.modules[k]
                except Exception:
                    pass
    return importlib.import_module("psycopg2")


def _get_db_timeout_sec() -> float:
    try:
        return max(1.0, min(10.0, float(os.environ.get("GET_DB_TIMEOUT_SEC", "3"))))
    except (TypeError, ValueError):
        return 3.0


def _pool_config():
    try:
        minconn = int(os.environ.get("DB_POOL_MINCONN", "1"))
    except (TypeError, ValueError):
        minconn = 1
    try:
        maxconn = int(os.environ.get("DB_POOL_MAXCONN", "20"))
    except (TypeError, ValueError):
        maxconn = 20
    try:
        connect_timeout = int(os.environ.get("DB_CONNECT_TIMEOUT_SECONDS", "5"))
    except (TypeError, ValueError):
        connect_timeout = 5
    threaded = (os.environ.get("DB_POOL_THREADED", "1") or "").strip().lower() not in (
        "0",
        "false",
        "no",
    )
    return minconn, maxconn, connect_timeout, threaded


def update_db_ready_cache(ok: bool):
    """Actualiza caché de salud (llamar desde db_probe / login exitoso, no desde /health)."""
    _DB_READY_CACHE["ts"] = time.monotonic()
    _DB_READY_CACHE["ok"] = bool(ok)


def db_ready_cached():
    """
    Valor fresco si último refresh fue hace < HEALTH_DB_CACHE_SEC.
    None si expiró (no abre conexión; usar db_ready_for_health() en /health).
    """
    now = time.monotonic()
    ts = float(_DB_READY_CACHE.get("ts") or 0.0)
    if ts > 0 and (now - ts) < _health_db_cache_sec():
        return bool(_DB_READY_CACHE.get("ok"))
    return None


def db_ready_for_health() -> bool:
    """
    Solo para GET /health: nunca abre PostgreSQL ni pool.
    Si el caché expiró, devuelve el último valor conocido (estable).
    """
    fresh = db_ready_cached()
    if fresh is not None:
        return fresh
    return bool(_DB_READY_CACHE.get("ok", True))


def init_pool(force_reinit: bool = False):
    global _PG_POOL
    url = database_url()
    if not url:
        return None
    url = _with_sslmode(url)
    minconn, maxconn, connect_timeout, threaded = _pool_config()

    with _get_lock():
        if _PG_POOL is not None and not force_reinit:
            return _PG_POOL
        if force_reinit and _PG_POOL is not None:
            try:
                _PG_POOL.closeall()
            except Exception:
                pass
            _PG_POOL = None

        log.info("[DB] Pool initializing threaded=%s min=%s max=%s", threaded, minconn, maxconn)
        try:
            psycopg2 = _import_psycopg2_fresh()
            from psycopg2 import extras
            from psycopg2.pool import SimpleConnectionPool, ThreadedConnectionPool

            pool_cls = ThreadedConnectionPool if threaded else SimpleConnectionPool
            _PG_POOL = pool_cls(
                minconn,
                maxconn,
                dsn=url,
                cursor_factory=extras.RealDictCursor,
                connect_timeout=connect_timeout,
            )
            log.info("[DB] Pool initialized class=%s", pool_cls.__name__)
            return _PG_POOL
        except Exception as e:
            log.error(
                "[DB] Pool init failed err=%s sslmode=%s tb=%s",
                e,
                pgsslmode(),
                traceback.format_exc(limit=6).replace("\n", " | "),
            )
            _PG_POOL = None
            return None


def reconnect(clear_health_cache: bool = False):
    """
    Recrea el pool. NO invalidar caché de /health salvo diagnóstico explícito (db_probe).
    """
    log.info("[DB] Reconnecting...")
    if clear_health_cache:
        try:
            _DB_READY_CACHE["ts"] = 0.0
            _DB_READY_CACHE["ok"] = False
        except Exception:
            pass
    return init_pool(force_reinit=True)


def _pool_getconn_timed(pool, timeout_sec=None):
    if pool is None:
        return None, "no_pool"
    timeout_sec = _get_db_timeout_sec() if timeout_sec is None else float(timeout_sec)
    box = {"conn": None, "err": None}

    def _run():
        try:
            box["conn"] = pool.getconn()
        except Exception as exc:
            box["err"] = exc

    th = threading.Thread(target=_run, name="db_pool_getconn", daemon=True)
    th.start()
    th.join(timeout=timeout_sec)
    if th.is_alive():
        return None, "timeout"
    if box["err"] is not None:
        return None, box["err"]
    return box["conn"], None


def get_db():
    """
    Conexión del pool (timeout 3s). reconnect() solo tras fallo getconn, sin tumbar health cache.
    """
    if not database_url():
        return None

    timeout = _get_db_timeout_sec()
    pool = init_pool(force_reinit=False)
    if pool is None:
        pool = init_pool(force_reinit=True)
    if pool is None:
        log.error("[DB] get_db no pool")
        return None

    conn, err = _pool_getconn_timed(pool, timeout)
    if conn is not None:
        log.debug("[DB] Connected (pooled)")
        return conn

    if err == "timeout":
        log.warning("[DB] get_db timeout after %.1fs", timeout)
    else:
        log.warning("[DB] getconn failed err=%s", err)

    reconnect(clear_health_cache=False)
    pool = init_pool(force_reinit=False)
    if pool is None:
        log.error("[DB] get_db retry no pool")
        return None

    conn2, err2 = _pool_getconn_timed(pool, timeout)
    if conn2 is not None:
        log.debug("[DB] Connected (pooled) after reconnect")
        return conn2

    log.error("[DB] get_db failed after reconnect err=%s", err2)
    return None


def put_db(conn):
    global _PG_POOL
    if conn is None:
        return
    with _get_lock():
        pool = _PG_POOL
    if not pool:
        try:
            conn.close()
        except Exception:
            pass
        return
    try:
        try:
            conn.rollback()
        except Exception:
            pass
        pool.putconn(conn)
    except Exception:
        try:
            pool.putconn(conn, close=True)
        except Exception:
            try:
                conn.close()
            except Exception:
                pass


def refresh_db_ready_from_db():
    """Abre conexión directa (no pool) y actualiza caché. Solo db_probe / admin."""
    ok, _info = test_connection()
    update_db_ready_cache(ok)
    return bool(ok)


def db_ready() -> bool:
    """Compat: devuelve caché fresca o último valor (no abre PG)."""
    return db_ready_for_health()


def test_connection():
    """Probe directo psycopg2.connect. Siempre cierra. No usar en /health."""
    url = database_url()
    if not url:
        return False, {"error": "DATABASE_URL missing"}
    conn = None
    cur = None
    try:
        psycopg2 = _import_psycopg2_fresh()
        conn = psycopg2.connect(
            dsn=_with_sslmode(url), connect_timeout=_pool_config()[2]
        )
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.execute("SHOW server_version")
        ver = cur.fetchone()
        return True, {"postgres_version": str(ver[0] if ver else "")}
    except Exception as e:
        return False, {"error": str(e)}
    finally:
        try:
            if cur is not None:
                cur.close()
        except Exception:
            pass
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


def psycopg2_version() -> str:
    try:
        mod = _import_psycopg2_fresh()
        return str(getattr(mod, "__version__", "") or "")
    except Exception:
        return ""
