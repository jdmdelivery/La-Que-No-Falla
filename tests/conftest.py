"""
Pytest: una BD SQLite nueva por test (evita UNIQUE compartido y «database is locked»).
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture
def app_mod(monkeypatch, tmp_path):
    db_path = tmp_path / "ganadores_test.db"
    monkeypatch.setenv("SQLITE_DB", str(db_path))
    monkeypatch.setenv("DEBUG_JOIN_SIN_ESPERA", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("ENABLE_RESULTADOS_SCHEDULER", "")

    import app as app_module

    app_module._DB_SCHEMA_READY = False
    app_module.init_db()
    for _bucket in (
        "premios_sync_done",
        "lineas_eval_per",
        "resultados",
        "dashboard_pend",
    ):
        try:
            app_module._ttl_cache_invalidate_bucket(_bucket)
        except Exception:
            pass
    try:
        with app_module._ganadores_page_cache["lock"]:
            app_module._ganadores_page_cache["exp"] = 0.0
            app_module._ganadores_page_cache["key"] = None
            app_module._ganadores_page_cache["html"] = None
    except Exception:
        pass
    try:
        with app_module._admin_lineas_eval_cache["lock"]:
            app_module._admin_lineas_eval_cache["exp"] = 0.0
            app_module._admin_lineas_eval_cache["key"] = None
    except Exception:
        pass
    yield app_module


@pytest.fixture
def client(app_mod):
    return app_mod.app.test_client()
