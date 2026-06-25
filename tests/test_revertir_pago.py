"""Reversa / eliminar pago de premio (pagos_premios + premios + caja)."""
from __future__ import annotations


def _seed_ticket_pagado(app_mod, ticket_id=66, monto=420.0, cajero="Anabel"):
    conn = app_mod.db()
    cur = conn.cursor()
    cur.execute(
        app_mod._sql(
            "INSERT INTO tickets (id, pagado, ganador, cajero) VALUES (%s, %s, %s, %s)"
        ),
        (ticket_id, 1, 1, cajero),
    )
    cur.execute(
        app_mod._sql(
            """
            INSERT INTO premios (ticket_id, line_id, numero, monto, premio, lottery, draw, play, estado, fecha_pago)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
        ),
        (ticket_id, 1, "147179", 10.0, monto, "Nacional", "2:30 PM", "Tripleta", "pagado", "2026-05-20"),
    )
    premio_id = cur.lastrowid
    cur.execute(
        app_mod._sql(
            """
            INSERT INTO pagos_premios (ticket_id, monto, cajero, premio_id, revertido)
            VALUES (%s, %s, %s, %s, 0)
            """
        ),
        (ticket_id, monto, cajero, premio_id),
    )
    cur.execute(
        app_mod._sql(
            "INSERT INTO movimientos_caja (cajero_id, tipo, monto, descripcion) VALUES (%s, %s, %s, %s)"
        ),
        (cajero, "salida", monto, "test pago"),
    )
    conn.commit()
    conn.close()
    return premio_id


def test_revertir_pago_ticket_marca_eliminado_y_devuelve_caja(app_mod, monkeypatch):
    monkeypatch.setattr(app_mod, "is_admin_or_super", lambda: True)
    _seed_ticket_pagado(app_mod, ticket_id=66, monto=420.0, cajero="Anabel")

    conn = app_mod.db()
    res = app_mod._revertir_pago_premio_ticket(
        conn, 66, "admin_test", motivo="test", admin_uid=1
    )
    assert res.get("ok") is True, res

    cur = conn.cursor()
    cur.execute(
        app_mod._sql(
            "SELECT COUNT(*) AS c FROM pagos_premios WHERE ticket_id = %s AND "
            + app_mod._pp_sin_revertir_sql("pagos_premios")
        ),
        (66,),
    )
    assert int(cur.fetchone()[0]) == 0

    cur.execute(
        app_mod._sql(
            "SELECT lower(trim(COALESCE(estado,''))) FROM premios WHERE ticket_id = %s"
        ),
        (66,),
    )
    assert cur.fetchone()[0] == "pendiente"

    cur.execute(app_mod._sql("SELECT pagado FROM tickets WHERE id = %s"), (66,))
    assert app_mod._pago_premio_es_truthy_pagado(cur.fetchone()[0]) is False

    cur.execute(
        app_mod._sql(
            "SELECT COALESCE(SUM(CASE WHEN tipo='entrada' THEN monto ELSE -monto END), 0) FROM movimientos_caja WHERE cajero_id = %s"
        ),
        ("Anabel",),
    )
    net = float(cur.fetchone()[0] or 0)
    assert abs(net) < 0.01
    conn.close()


def test_revertir_pago_legacy_pagos(app_mod, monkeypatch):
    monkeypatch.setattr(app_mod, "is_admin_or_super", lambda: True)
    conn = app_mod.db()
    cur = conn.cursor()
    cur.execute(
        app_mod._sql(
            "INSERT INTO tickets (id, pagado, ganador, cajero) VALUES (%s, %s, %s, %s)"
        ),
        (77, 1, 1, "Anabel"),
    )
    cur.execute(
        app_mod._sql(
            """
            INSERT INTO pagos (ticket_id, numero, jugada, monto, fecha, pagado_por, revertido)
            VALUES (%s, %s, %s, %s, %s, %s, 0)
            """
        ),
        (77, "147179", "Tripleta", 420.0, "2026-05-20", "Anabel"),
    )
    conn.commit()

    res = app_mod._revertir_pago_premio_ticket(conn, 77, "admin_test", admin_uid=1)
    assert res.get("ok") is True, res

    cur.execute(
        app_mod._sql(
            "SELECT COUNT(*) FROM pagos WHERE ticket_id = %s AND "
            + app_mod._pagos_legacy_sin_revertir_sql("pagos")
        ),
        (77,),
    )
    assert int(cur.fetchone()[0]) == 0
    conn.close()
