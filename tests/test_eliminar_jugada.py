"""Eliminar jugada (historial): mismo endpoint Web/APK, permisos y ventana de tiempo."""
from __future__ import annotations

import time
from datetime import timedelta

import pytest

FECHA = "2026-05-10"


def _session_admin(client):
    with client.session_transaction() as sess:
        sess["u"] = "admin_test"
        sess["uid"] = 1
        sess["role"] = "admin"
        sess["last_activity"] = time.time()
        sess["last_activity_touch"] = time.time()


def _session_cajero(client, username="cajero_test"):
    with client.session_transaction() as sess:
        sess["u"] = username
        sess["uid"] = 2
        sess["role"] = "cajero"
        sess["last_activity"] = time.time()
        sess["last_activity_touch"] = time.time()


def _seed_jugada(app, cur, *, cajero="cajero_test", created_at=None):
    if created_at is None:
        created_at = app.ahora_rd().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        app._sql(
            """
            INSERT INTO tickets (cajero, created_at, pagado, monto, ticket_group, eliminado)
            VALUES (%s, %s, 0, 25, 1781109657789, 0)
            """
        ),
        (cajero, created_at),
    )
    tid = cur.lastrowid
    cur.execute(
        app._sql(
            """
            INSERT INTO ticket_lines (ticket_id, lottery, draw, number, play, amount, fecha_sorteo, estado)
            VALUES (%s, 'Loteka', '7:55 PM', '12', 'Quiniela', 25, %s, 'activo')
            """
        ),
        (tid, FECHA),
    )
    cur.execute(
        app._sql(
            """
            INSERT INTO historial_jugadas (ticket_id, lottery, number, play, amount, created_at, estado)
            VALUES (%s, 'Loteka', '12', 'Quiniela', 25, %s, 'activo')
            """
        ),
        (tid, created_at),
    )
    jid = cur.lastrowid
    return tid, jid


def _ajax_headers():
    return {
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json",
    }


def test_eliminar_jugada_admin_json_ok(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    tid, jid = _seed_jugada(app, cur)
    c.commit()
    c.close()

    _session_admin(client)
    r = client.post(f"/admin/eliminar_jugada/{jid}", headers=_ajax_headers())
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("ok") is True
    assert body.get("ticket_id") == tid


def test_eliminar_jugada_cajero_otro_ticket_403(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    _tid, jid = _seed_jugada(app, cur, cajero="otro_cajero")
    c.commit()
    c.close()

    _session_cajero(client, "cajero_test")
    r = client.post(f"/admin/eliminar_jugada/{jid}", headers=_ajax_headers())
    assert r.status_code == 403
    assert r.get_json().get("error") == "No autorizado"


def test_eliminar_jugada_cajero_propio_ok(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    tid, jid = _seed_jugada(app, cur, cajero="cajero_test")
    c.commit()
    c.close()

    _session_cajero(client, "cajero_test")
    r = client.post(f"/admin/eliminar_jugada/{jid}", headers=_ajax_headers())
    assert r.status_code == 200
    assert r.get_json().get("ok") is True


def test_eliminar_jugada_pagina_incluye_fetch_y_session(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    _seed_jugada(app, cur)
    c.commit()
    c.close()

    _session_admin(client)
    r = client.get("/admin/jugadas")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "/admin/eliminar_jugada/" in html
    assert "/api/eliminar_jugada/" in html
    assert "logEliminarJugadaApi" in html
    assert "__BANCA_SESSION" in html
    assert "fetch(apiUrl" in html


def test_api_eliminar_jugada_post_ok(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    tid, jid = _seed_jugada(app, cur)
    c.commit()
    c.close()

    _session_cajero(client, "cajero_test")
    r = client.post(f"/api/eliminar_jugada/{jid}")
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("ok") is True
    assert body.get("ticket_id") == tid


def test_api_eliminar_jugada_delete_ok(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    tid, jid = _seed_jugada(app, cur)
    c.commit()
    c.close()

    _session_admin(client)
    r = client.delete(f"/api/eliminar_jugada/{jid}")
    assert r.status_code == 200
    assert r.get_json().get("ok") is True


def test_api_eliminar_jugada_android_ua_sin_headers_ajax(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    tid, jid = _seed_jugada(app, cur)
    c.commit()
    c.close()

    _session_cajero(client, "cajero_test")
    r = client.post(
        f"/api/eliminar_jugada/{jid}",
        headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; wv) AppleWebKit/537.36",
            "X-Client-Source": "apk",
        },
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("ticket_id") == tid
    assert body.get("monto_anulado") == 25.0


def test_api_eliminar_jugada_ticket_pagado_409(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    tid, jid = _seed_jugada(app, cur)
    cur.execute(app._sql("UPDATE tickets SET pagado = 1 WHERE id = %s"), (tid,))
    c.commit()
    c.close()

    _session_admin(client)
    r = client.post(f"/api/eliminar_jugada/{jid}")
    assert r.status_code == 409
    assert "pagado" in (r.get_json().get("error") or "").lower()


def test_api_eliminar_jugada_ya_cancelada_409(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    tid, jid = _seed_jugada(app, cur)
    cur.execute(app._sql("UPDATE historial_jugadas SET estado = 'cancelado' WHERE id = %s"), (jid,))
    c.commit()
    c.close()

    _session_admin(client)
    r = client.post(f"/api/eliminar_jugada/{jid}")
    assert r.status_code == 409
    body = r.get_json()
    assert body.get("ok") is False
    assert "cancelada" in (body.get("error") or "").lower()


def test_api_eliminar_jugada_revierte_banco_ticket_50(app_mod, client):
    """Ticket RD$50: al borrar jugada debe revertir venta en Banco General."""
    app = app_mod
    c = app.db()
    cur = c.cursor()
    created = app.ahora_rd().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        app._sql(
            """
            INSERT INTO tickets (cajero, cajero_id, created_at, pagado, monto, ticket_group, eliminado)
            VALUES ('cajero_test', 2, %s, 0, 50, 1781109657789, 0)
            """
        ),
        (created,),
    )
    tid = cur.lastrowid
    cur.execute(
        app._sql(
            """
            INSERT INTO ticket_lines (ticket_id, lottery, draw, number, play, amount, fecha_sorteo, estado)
            VALUES (%s, 'Loteka', '7:55 PM', '12', 'Quiniela', 50, %s, 'activo')
            """
        ),
        (tid, FECHA),
    )
    cur.execute(
        app._sql(
            """
            INSERT INTO historial_jugadas (ticket_id, lottery, number, play, amount, created_at, estado)
            VALUES (%s, 'Loteka', '12', 'Quiniela', 50, %s, 'activo')
            """
        ),
        (tid, created),
    )
    jid = cur.lastrowid
    app.banco_registrar_venta(cur, tid, 2, 50.0, descripcion="Venta ticket #%s" % tid)
    c.commit()
    c.close()

    _session_cajero(client, "cajero_test")
    r = client.post(
        f"/api/eliminar_jugada/{jid}",
        headers={"User-Agent": "Mozilla/5.0 (Linux; Android 13; wv) AppleWebKit/537.36"},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("ok") is True
    assert body.get("monto_anulado") == 50.0
    assert body.get("banco_revertido") is True

    c2 = app.db()
    cur2 = c2.cursor()
    cur2.execute(
        app._sql(
            "SELECT COUNT(*) AS n FROM banco_movimientos WHERE ticket_id = %s AND tipo = %s"
        ),
        (tid, app.BANCO_TIPO_ANULACION),
    )
    row = cur2.fetchone()
    n_anul = int((row["n"] if hasattr(row, "keys") else row[0]) or 0)
    cur2.execute(app._sql("SELECT eliminado, monto FROM tickets WHERE id = %s"), (tid,))
    tk = cur2.fetchone()
    c2.close()
    assert n_anul >= 1
    eliminado = int((tk["eliminado"] if hasattr(tk, "keys") else tk[0]) or 0)
    monto = float((tk["monto"] if hasattr(tk, "keys") else tk[1]) or 0)
    assert eliminado == 1
    assert monto <= 0.004


def test_eliminar_jugada_bloquea_despues_5_minutos_web(app_mod, client, monkeypatch):
    monkeypatch.setenv("JUGADA_ELIMINAR_MAX_SEGUNDOS", "300")
    app = app_mod
    created = (app.ahora_rd() - timedelta(minutes=6)).strftime("%Y-%m-%d %H:%M:%S")
    c = app.db()
    cur = c.cursor()
    tid, jid = _seed_jugada(app, cur, created_at=created)
    c.commit()
    c.close()

    _session_cajero(client, "cajero_test")
    r = client.post(f"/api/eliminar_jugada/{jid}")
    assert r.status_code == 403
    body = r.get_json()
    assert body.get("ok") is False
    assert body.get("error") == app.MSG_ELIMINAR_JUGADA_TIEMPO_EXPIRADO


def test_eliminar_jugada_bloquea_despues_5_minutos_admin(app_mod, client, monkeypatch):
    monkeypatch.setenv("JUGADA_ELIMINAR_MAX_SEGUNDOS", "300")
    app = app_mod
    created = (app.ahora_rd() - timedelta(minutes=6)).strftime("%Y-%m-%d %H:%M:%S")
    c = app.db()
    cur = c.cursor()
    _tid, jid = _seed_jugada(app, cur, created_at=created)
    c.commit()
    c.close()

    _session_admin(client)
    r = client.post(f"/admin/eliminar_jugada/{jid}", headers=_ajax_headers())
    assert r.status_code == 403
    assert r.get_json().get("error") == app.MSG_ELIMINAR_JUGADA_TIEMPO_EXPIRADO


def test_eliminar_jugada_bloqueada_no_toca_banco(app_mod, client, monkeypatch):
    monkeypatch.setenv("JUGADA_ELIMINAR_MAX_SEGUNDOS", "300")
    app = app_mod
    created = (app.ahora_rd() - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    c = app.db()
    cur = c.cursor()
    cur.execute(
        app._sql(
            """
            INSERT INTO tickets (cajero, cajero_id, created_at, pagado, monto, ticket_group, eliminado)
            VALUES ('cajero_test', 2, %s, 0, 50, 1781109657789, 0)
            """
        ),
        (created,),
    )
    tid = cur.lastrowid
    cur.execute(
        app._sql(
            """
            INSERT INTO ticket_lines (ticket_id, lottery, draw, number, play, amount, fecha_sorteo, estado)
            VALUES (%s, 'Loteka', '7:55 PM', '12', 'Quiniela', 50, %s, 'activo')
            """
        ),
        (tid, FECHA),
    )
    cur.execute(
        app._sql(
            """
            INSERT INTO historial_jugadas (ticket_id, lottery, number, play, amount, created_at, estado)
            VALUES (%s, 'Loteka', '12', 'Quiniela', 50, %s, 'activo')
            """
        ),
        (tid, created),
    )
    jid = cur.lastrowid
    app.banco_registrar_venta(cur, tid, 2, 50.0, descripcion="Venta ticket #%s" % tid)
    c.commit()
    c.close()

    _session_cajero(client, "cajero_test")
    r = client.post(
        f"/api/eliminar_jugada/{jid}",
        headers={"User-Agent": "Mozilla/5.0 (Linux; Android 13; wv) AppleWebKit/537.36"},
    )
    assert r.status_code == 403

    c2 = app.db()
    cur2 = c2.cursor()
    cur2.execute(
        app._sql(
            "SELECT COUNT(*) AS n FROM banco_movimientos WHERE ticket_id = %s AND tipo = %s"
        ),
        (tid, app.BANCO_TIPO_ANULACION),
    )
    row = cur2.fetchone()
    n_anul = int((row["n"] if hasattr(row, "keys") else row[0]) or 0)
    cur2.execute(app._sql("SELECT eliminado, monto FROM tickets WHERE id = %s"), (tid,))
    tk = cur2.fetchone()
    cur2.execute(app._sql("SELECT estado FROM historial_jugadas WHERE id = %s"), (jid,))
    jg = cur2.fetchone()
    c2.close()
    assert n_anul == 0
    assert int((tk["eliminado"] if hasattr(tk, "keys") else tk[0]) or 0) == 0
    assert float((tk["monto"] if hasattr(tk, "keys") else tk[1]) or 0) == 50.0
    assert (jg["estado"] if hasattr(jg, "keys") else jg[0]) == "activo"


def test_eliminar_jugada_usa_ticket_created_at_si_falta_jugada(app_mod, client, monkeypatch):
    monkeypatch.setenv("JUGADA_ELIMINAR_MAX_SEGUNDOS", "300")
    app = app_mod
    reciente = app.ahora_rd().strftime("%Y-%m-%d %H:%M:%S")
    c = app.db()
    cur = c.cursor()
    cur.execute(
        app._sql(
            """
            INSERT INTO tickets (cajero, created_at, pagado, monto, ticket_group, eliminado)
            VALUES ('cajero_test', %s, 0, 25, 1781109657789, 0)
            """
        ),
        (reciente,),
    )
    tid = cur.lastrowid
    cur.execute(
        app._sql(
            """
            INSERT INTO historial_jugadas (ticket_id, lottery, number, play, amount, created_at, estado)
            VALUES (%s, 'Loteka', '12', 'Quiniela', 25, NULL, 'activo')
            """
        ),
        (tid,),
    )
    jid = cur.lastrowid
    c.commit()
    c.close()

    _session_cajero(client, "cajero_test")
    r = client.post(f"/api/eliminar_jugada/{jid}")
    assert r.status_code == 200
    assert r.get_json().get("ok") is True
