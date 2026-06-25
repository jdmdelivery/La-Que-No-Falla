"""
Smoke tests: rutas críticas responden sin 500 ni traceback.
Ejecutar antes de cada cambio: pytest && python -m compileall .
"""
from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

_ERROR_MARKERS = (
    "Traceback (most recent call last)",
    "Internal Server Error",
    "500 Internal Server Error",
)


def _assert_ok_body(r, *, allow_redirect: bool = False):
    codes_ok = {200}
    if allow_redirect:
        codes_ok |= {302, 303, 307, 308}
    assert r.status_code in codes_ok, f"status={r.status_code} location={r.headers.get('Location')}"
    if r.status_code == 200:
        body = r.get_data(as_text=True)
        for marker in _ERROR_MARKERS:
            assert marker not in body, f"encontrado {marker!r} en respuesta"


def _session_admin(client):
    with client.session_transaction() as sess:
        sess["u"] = "jose0219"
        sess["uid"] = 1
        sess["role"] = "super_admin"
        sess["last_activity"] = time.time()
        sess["last_activity_touch"] = time.time()


def _session_cajero(client):
    with client.session_transaction() as sess:
        sess["u"] = "cajero_smoke"
        sess["uid"] = 2
        sess["role"] = "cajero"
        sess["last_activity"] = time.time()
        sess["last_activity_touch"] = time.time()


@pytest.fixture
def client(app_mod):
    return app_mod.app.test_client()


def test_ahora_rd_usa_zona_santo_domingo(app_mod):
    from zoneinfo import ZoneInfo

    now = app_mod.ahora_rd()
    assert now.tzinfo is not None
    assert str(now.tzinfo) in ("America/Santo_Domingo", "UTC-04:00", "UTC-05:00")
    assert now.tzinfo.utcoffset(now) is not None


def test_api_hora_servidor(client):
    r = client.get("/api/hora_servidor")
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("ok") is True
    assert data.get("zona") == "America/Santo_Domingo"
    assert data.get("fecha")


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_data(as_text=True).strip() == "ok"


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200


def test_login_page_loads(client):
    r = client.get("/")
    _assert_ok_body(r)
    assert "login" in r.get_data(as_text=True).lower() or "password" in r.get_data(as_text=True).lower()


def test_dashboard_admin_loads(client):
    _session_admin(client)
    r = client.get("/admin")
    _assert_ok_body(r)


def test_venta_loads(client):
    _session_cajero(client)
    r = client.get("/venta")
    _assert_ok_body(r)
    html = r.get_data(as_text=True)
    assert 'id="venta-lotteries-json"' in html


def test_ganadores_loads_or_redirect(client):
    _session_cajero(client)
    r = client.get("/ganadores")
    _assert_ok_body(r, allow_redirect=True)
    if r.status_code == 200:
        html = r.get_data(as_text=True)
        assert "ganadores" in html.lower() or "Cargando" in html


def test_ganadores_requires_login_redirect(client):
    r = client.get("/ganadores")
    assert r.status_code in (302, 303)
    assert r.headers.get("Location")


def test_actualizar_resultados_no_500(client, app_mod, monkeypatch):
    """Scrape mockeado: la ruta debe redirigir sin tumbar la app."""
    monkeypatch.setattr(app_mod, "_parse_conectate_resultados", lambda: {})
    _session_admin(client)
    r = client.get("/actualizar_resultados", follow_redirects=False)
    assert r.status_code in (302, 303), r.status_code
    assert r.headers.get("Location")


def test_api_ganadores_json_ok(client):
    _session_admin(client)
    r = client.get("/api/ganadores")
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    data = r.get_json()
    assert isinstance(data, dict)
    assert data.get("ok") is True
    assert "html" in data
    body = str(data.get("html") or "")
    for marker in _ERROR_MARKERS:
        assert marker not in body


def test_api_ventas_cajeros_ok(client):
    _session_admin(client)
    r = client.get("/api/ventas_cajeros")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, dict)
    assert "cajeros" in data


def test_api_ventas_cajeros_unauthorized_without_session(client):
    r = client.get("/api/ventas_cajeros")
    assert r.status_code == 401


def test_api_resultados_hoy_list(client):
    _session_cajero(client)
    r = client.get("/api/resultados_hoy")
    assert r.status_code == 200
    data = r.get_json()
    assert isinstance(data, list)


def test_compileall_app_modules():
    r = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", str(ROOT)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr or r.stdout


def test_venta_pos_js_syntax_if_node_present():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    path = ROOT / "static" / "venta_pos.js"
    if not path.is_file():
        pytest.skip("venta_pos.js missing")
    r = subprocess.run(
        [node, "--check", str(path)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert r.returncode == 0, r.stderr or r.stdout


def test_stability_backup_sqlite(tmp_path, monkeypatch):
    from stability_guard import db_backup_before_dangerous_op

    db_file = tmp_path / "smoke.db"
    db_file.write_bytes(b"sqlite-test")
    monkeypatch.setenv("SQLITE_DB", str(db_file))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("BACKUP_DIR", str(tmp_path / "bk"))
    dest = db_backup_before_dangerous_op("smoke_test")
    assert dest and pathlib.Path(dest).is_file()
