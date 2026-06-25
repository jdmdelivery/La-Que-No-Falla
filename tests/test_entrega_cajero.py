"""Registrar entrega de cajero: control interno sin mover Banco General."""
from __future__ import annotations

import time

import pytest


def _session_admin(client):
    with client.session_transaction() as sess:
        sess["u"] = "admin_test"
        sess["uid"] = 1
        sess["role"] = "admin"
        sess["last_activity"] = time.time()
        sess["last_activity_touch"] = time.time()


def _seed_solibel_pendiente(app, *, ventas=5630.0, banco_general=68515.0):
    """Pendiente operativo por tickets; sin movimiento virtual de cajero en banco_movimientos."""
    conn = app.db()
    cur = conn.cursor()
    cur.execute(
        app._sql("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)"),
        ("Solibel", "x", "cajero"),
    )
    solibel_id = int(cur.lastrowid)
    cur.execute(
        app._sql("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)"),
        ("admin_test", "x", "admin"),
    )
    app.banco_configurar_inicial(cur, banco_general, nota="Test apertura")
    created = app.ahora_rd().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        app._sql(
            """
            INSERT INTO tickets (cajero, cajero_id, monto, created_at, pagado, eliminado)
            VALUES (%s, %s, %s, %s, 0, 0)
            """
        ),
        ("Solibel", solibel_id, float(ventas), created),
    )
    conn.commit()
    conn.close()
    return solibel_id


def test_entrega_caso_obligatorio_solibel_sin_tocar_banco(app_mod, client):
    """Banco RD$68,515; pendiente Solibel RD$5,630 → entrega total → banco igual, pendiente RD$0."""
    app = app_mod
    solibel_id = _seed_solibel_pendiente(app, ventas=5630.0, banco_general=68515.0)

    conn = app.db()
    cur = conn.cursor()
    info_antes = app._cajero_pendiente_operativo_entrega(cur, conn, "Solibel", False)
    banco_antes = app.banco_get_balance_general(cur)
    bal_virtual_antes = app.banco_get_balance_cajero(cur, solibel_id)
    cur.execute(app._sql("SELECT COUNT(*) AS c FROM banco_movimientos"))
    movs_antes = int((cur.fetchone() or {"c": 0})["c"])
    conn.close()

    assert round(info_antes["pendiente"], 2) == 5630.0
    assert round(banco_antes, 2) == 68515.0
    assert bal_virtual_antes == 0.0

    _session_admin(client)
    r = client.post(
        "/registrar_entrega",
        data={"user_id": str(solibel_id), "monto_entregado": "5630"},
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["cajero"] == "Solibel"
    assert data["monto"] == 5630.0
    assert data["pendiente_despues"] == 0.0
    assert data["banco_general_antes"] == 68515.0
    assert data["banco_general_despues"] == 68515.0

    conn = app.db()
    cur = conn.cursor()
    info_desp = app._cajero_pendiente_operativo_entrega(cur, conn, "Solibel", False)
    assert round(info_desp["pendiente"], 2) == 0.0
    assert app.banco_get_balance_general(cur) == 68515.0
    assert app.banco_get_balance_cajero(cur, solibel_id) == 0.0

    cur.execute(
        app._sql(
            "SELECT cajero, cajero_id, monto, admin, motivo FROM entregas_cajero WHERE cajero = %s"
        ),
        ("Solibel",),
    )
    row = cur.fetchone()
    assert row is not None
    assert float(row["monto"]) == 5630.0
    assert str(row["cajero_id"]) == str(solibel_id)
    assert (row["admin"] or "").strip() == "admin_test"

    cur.execute(app._sql("SELECT COUNT(*) AS c FROM banco_movimientos"))
    movs_desp = int((cur.fetchone() or {"c": 0})["c"])
    assert movs_desp == movs_antes
    conn.close()


def test_entrega_parcial_reduce_pendiente(app_mod):
    app = app_mod
    _seed_solibel_pendiente(app, ventas=5000.0, banco_general=10000.0)

    conn = app.db()
    cur = conn.cursor()
    res = app._registrar_entrega_cajero_control_interno(
        cur, conn, cajero_ref="Solibel", monto=2000.0, admin_user="admin_test"
    )
    assert res["ok"] is True
    conn.commit()

    info = app._cajero_pendiente_operativo_entrega(cur, conn, "Solibel", False)
    assert round(info["pendiente"], 2) == 3000.0
    assert app.banco_get_balance_general(cur) == 10000.0
    conn.close()


def test_entrega_rechaza_monto_mayor_que_pendiente_positivo(app_mod):
    app = app_mod
    _seed_solibel_pendiente(app, ventas=1000.0, banco_general=5000.0)

    conn = app.db()
    cur = conn.cursor()
    res = app._registrar_entrega_cajero_control_interno(
        cur, conn, cajero_ref="Solibel", monto=1500.0, admin_user="admin_test"
    )
    assert res["ok"] is False
    assert "pendiente" in (res.get("error") or "").lower()
    conn.rollback()
    conn.close()


def test_entrega_no_bloquea_por_balance_virtual_cero(app_mod):
    """Aunque banco_get_balance_cajero sea 0, la entrega operativa debe permitirse."""
    app = app_mod
    solibel_id = _seed_solibel_pendiente(app, ventas=2500.0, banco_general=8000.0)

    conn = app.db()
    cur = conn.cursor()
    assert app.banco_get_balance_cajero(cur, solibel_id) == 0.0
    res = app._registrar_entrega_cajero_control_interno(
        cur, conn, cajero_ref=str(solibel_id), monto=2500.0, admin_user="admin_test"
    )
    assert res["ok"] is True
    assert res["banco_general_antes"] == res["banco_general_despues"] == 8000.0
    conn.commit()
    conn.close()
