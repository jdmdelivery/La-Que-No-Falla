"""Soft delete de tickets falsos/bajos: permisos, auditoría y exclusión de premios."""
from __future__ import annotations

import time

import pytest

FECHA = "2026-05-10"


def _session_admin(client):
    with client.session_transaction() as sess:
        sess["u"] = "admin_test"
        sess["uid"] = 1
        sess["role"] = "admin"
        sess["last_activity"] = time.time()
        sess["last_activity_touch"] = time.time()


def _session_cajero(client):
    with client.session_transaction() as sess:
        sess["u"] = "cajero_test"
        sess["uid"] = 2
        sess["role"] = "cajero"
        sess["last_activity"] = time.time()
        sess["last_activity_touch"] = time.time()


def _seed_ticket(app, cur, *, monto=50.0, ticket_group=1781109657789):
    cur.execute(
        app._sql(
            """
            INSERT INTO tickets (cajero, created_at, pagado, monto, ticket_group, eliminado)
            VALUES ('cajero_test', %s, 0, %s, %s, 0)
            """
        ),
        (f"{FECHA} 12:00:00", monto, ticket_group),
    )
    tid = cur.lastrowid
    cur.execute(
        app._sql(
            """
            INSERT INTO ticket_lines (ticket_id, lottery, draw, number, play, amount, fecha_sorteo)
            VALUES (%s, 'Loteka', '7:55 PM', '12', 'Quiniela', 25, %s)
            """
        ),
        (tid, FECHA),
    )
    lid = cur.lastrowid
    cur.execute(
        app._sql(
            """
            INSERT INTO premios (ticket_id, line_id, estado, premio, fecha_dia, numero, lottery, draw, play)
            VALUES (%s, %s, 'pendiente', 100, %s, '12', 'Loteka', '7:55 PM', 'Quiniela')
            """
        ),
        (tid, lid, FECHA),
    )
    return tid


def test_api_eliminar_ticket_falso_403_cajero(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    tid = _seed_ticket(app, cur)
    c.commit()
    c.close()

    _session_cajero(client)
    r = client.post(
        "/api/admin/eliminar_ticket_falso",
        json={"ticket_id": tid, "motivo": "Ticket falso detectado"},
    )
    assert r.status_code == 403
    assert r.get_json().get("ok") is False


def test_api_eliminar_ticket_falso_admin_ok(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    tid = _seed_ticket(app, cur, monto=75.0, ticket_group=999888777)
    c.commit()
    c.close()

    _session_admin(client)
    r = client.post(
        "/api/admin/eliminar_ticket_falso",
        json={"ticket_id": tid, "motivo": "Jugada de bajo — sin respaldo"},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()
    assert data.get("ok") is True
    assert "eliminado correctamente" in (data.get("message") or "").lower()

    c2 = app.db()
    cur2 = c2.cursor()
    cur2.execute(app._sql("SELECT eliminado FROM tickets WHERE id = %s"), (tid,))
    row = cur2.fetchone()
    elim = row["eliminado"] if hasattr(row, "keys") else row[0]
    assert int(elim or 0) == 1

    cur2.execute(
        app._sql(
            "SELECT ticket_id, eliminado_por, motivo, monto_ticket, serial_ticket FROM tickets_eliminados WHERE ticket_id = %s"
        ),
        (tid,),
    )
    aud = cur2.fetchone()
    assert aud is not None
    if hasattr(aud, "keys"):
        assert aud["eliminado_por"] == "admin_test"
        assert "bajo" in (aud["motivo"] or "").lower()
        assert float(aud["monto_ticket"] or 0) == 75.0
        assert str(aud["serial_ticket"]) == "999888777"
    c2.close()

    cur3 = app.db().cursor()
    pend = app._premios_fetch_por_estado(cur3, "pendiente")
    ids = {int(p.get("ticket_id") or 0) for p in (pend or [])}
    assert tid not in ids


def test_admin_historial_tickets_eliminados_403_cajero(client):
    _session_cajero(client)
    r = client.get("/admin/tickets_eliminados")
    assert r.status_code == 403


def test_sql_coalesce_bool_postgresql(app_mod, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    app = app_mod
    assert app._sql_coalesce_bool("tk.eliminado") == "COALESCE(CAST(tk.eliminado AS INTEGER), 0)"
    assert app._sql_coalesce_bool("tk.pagado") == "COALESCE(CAST(tk.pagado AS INTEGER), 0)"
    assert (
        app._sql_ticket_no_eliminado("tk")
        == " AND COALESCE(CAST(tk.eliminado AS INTEGER), 0) = 0"
    )


def test_sql_ticket_soft_delete_set_postgresql(app_mod, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    app = app_mod
    assert app._sql_ticket_soft_delete_set() == "eliminado = 1, ganador = FALSE"


def test_sql_ticket_soft_delete_set_sqlite(app_mod, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    app = app_mod
    assert app._sql_ticket_soft_delete_set() == "eliminado = 1, ganador = 0"


def test_sql_coalesce_bool_sqlite(app_mod, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    app = app_mod
    assert app._sql_coalesce_bool("eliminado") == "COALESCE(eliminado, 0)"
    assert app._sql_ticket_no_eliminado("tk") == " AND COALESCE(tk.eliminado, 0) = 0"


def test_admin_historial_tickets_eliminados_admin_ok(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    tid = _seed_ticket(app, cur)
    c.commit()
    c.close()

    _session_admin(client)
    r_del = client.post(
        "/api/admin/eliminar_ticket_falso",
        json={"ticket_id": tid, "motivo": "Prueba historial admin"},
    )
    assert r_del.status_code == 200
    r = client.get("/admin/tickets_eliminados")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Historial de Tickets Eliminados" in html
    assert f"#{tid}" in html or str(tid) in html
