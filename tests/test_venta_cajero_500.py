"""Reproduce /venta 500 scenarios for cajero."""
import time

import sqlite3


def test_venta_all_cajeros_in_db(app_mod):
    conn = sqlite3.connect("banca_local.db")
    rows = conn.execute(
        "SELECT id, username, role FROM users WHERE lower(role) IN ('cajero','user','supervisor','collector')"
    ).fetchall()
    conn.close()
    client = app_mod.app.test_client()
    failures = []
    for uid, username, role in rows:
        with client.session_transaction() as sess:
            sess.clear()
            sess["u"] = username
            sess["uid"] = uid
            sess["role"] = role
            sess["last_activity"] = time.time()
            sess["last_activity_touch"] = time.time()
        r = client.get("/venta")
        if r.status_code != 200:
            failures.append((username, uid, role, r.status_code, r.get_data(as_text=True)[:300]))
    assert not failures, failures


def test_venta_cajero_no_uid(app_mod):
    client = app_mod.app.test_client()
    with client.session_transaction() as sess:
        sess.clear()
        sess["u"] = "cajero_test"
        sess["role"] = "cajero"
        sess["last_activity"] = time.time()
        sess["last_activity_touch"] = time.time()
    r = client.get("/venta")
    assert r.status_code == 200, (r.status_code, r.get_data(as_text=True)[:500])


def test_venta_cajero_empty_role(app_mod):
    client = app_mod.app.test_client()
    with client.session_transaction() as sess:
        sess.clear()
        sess["u"] = "jose0219"
        sess["uid"] = 1
        sess["role"] = ""
        sess["last_activity"] = time.time()
        sess["last_activity_touch"] = time.time()
    r = client.get("/venta")
    assert r.status_code == 200, (r.status_code, r.get_data(as_text=True)[:500])


def test_caja_cerrada_hoy_no_crash(app_mod):
    app_mod.caja_cerrada_hoy()


def test_ventas_hoy_pg_fallback_on_at_timezone_fail(app_mod, monkeypatch):
    """Simula PG con created_at TEXT: AT TIME ZONE falla, prefijo texto funciona."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://local/test")
    calls = []

    class FakeCur:
        def execute(self, sql, params=None):
            calls.append(sql)
            if "AT TIME ZONE" in sql:
                raise Exception("operator does not exist: text AT TIME ZONE")

        def fetchone(self):
            return {"ventas_hoy": 55.0}

    v = app_mod._fetch_ventas_hoy_para_venta(
        FakeCur(), "2026-06-24", "cajero1", False, None
    )
    assert v == 55.0
    assert len(calls) >= 2
    assert any("AT TIME ZONE" in s for s in calls)

