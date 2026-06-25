"""API control global de límites por banca."""
from __future__ import annotations

import time


def _session_super(client):
    with client.session_transaction() as sess:
        sess["u"] = "super_test"
        sess["uid"] = 1
        sess["role"] = "super_admin"
        sess["last_activity"] = time.time()
        sess["last_activity_touch"] = time.time()


def _seed_lottery(cur, app):
    try:
        cur.execute(
            app._sql("INSERT INTO lotteries (lottery, draw) VALUES (%s, %s)"),
            ("Loteka Test", "7:55 PM"),
        )
    except Exception:
        pass


def test_api_guardar_limite_un_numero_todas_loterias(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    cur.execute(app._sql("INSERT INTO users (username, role) VALUES (%s, %s)"), ("anabel_lim", "cajero"))
    bid = cur.lastrowid
    _seed_lottery(cur, app)
    c.commit()
    c.close()

    _session_super(client)
    r = client.post(
        "/api/admin/limites/global",
        json={
            "accion": "upsert",
            "banca_id": bid,
            "usuario_id": 0,
            "lottery": "__TODAS__",
            "draw": "__TODOS__",
            "numero": "78",
            "limite": 300,
            "fecha_rd": "2026-06-12",
            "all_lotteries": True,
            "all_draws": True,
            "aplicar_todos_numeros": True,
            "activo": 1,
        },
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()
    assert data.get("ok") is True
    assert (data.get("total") or 0) >= 1

    c2 = app.db()
    cur2 = c2.cursor()
    cur2.execute(
        app._sql(
            """
            SELECT limite FROM limites_numeros
            WHERE banca_id=%s AND numero=%s AND lottery=%s AND draw=%s
            """
        ),
        (bid, "78", "Loteka Test", "7:55 PM"),
    )
    row = cur2.fetchone()
    c2.close()
    assert row is not None
    lim = row["limite"] if hasattr(row, "keys") else row[0]
    assert float(lim) == 300.0


def test_api_guardar_limite_numero_ignora_00_99_accidental(app_mod, client):
    """Con número 78 escrito, guardar solo 78 aunque venga aplicar_todos_numeros=true."""
    app = app_mod
    c = app.db()
    cur = c.cursor()
    cur.execute(app._sql("INSERT INTO users (username, role) VALUES (%s, %s)"), ("banca_lim2", "cajero"))
    bid = cur.lastrowid
    _seed_lottery(cur, app)
    c.commit()
    c.close()

    _session_super(client)
    r = client.post(
        "/api/admin/limites/global",
        json={
            "accion": "upsert",
            "banca_id": bid,
            "lottery": "__TODAS__",
            "draw": "__TODOS__",
            "numero": "78",
            "limite": 250,
            "all_lotteries": True,
            "all_draws": True,
            "aplicar_todos_numeros": True,
        },
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("ok") is True
    assert data.get("numeros") == 1
    assert (data.get("total") or 0) >= 1

    c2 = app.db()
    cur2 = c2.cursor()
    cur2.execute(
        app._sql("SELECT COUNT(*) AS n FROM limites_numeros WHERE banca_id=%s AND numero=%s"),
        (bid, "78"),
    )
    row = cur2.fetchone()
    cur2.execute(
        app._sql("SELECT COUNT(*) AS n FROM limites_numeros WHERE banca_id=%s AND numero<>%s"),
        (bid, "78"),
    )
    otros = cur2.fetchone()
    c2.close()
    n = row["n"] if hasattr(row, "keys") else row[0]
    n_otros = otros["n"] if hasattr(otros, "keys") else otros[0]
    assert int(n) == int(data.get("total") or 0)
    assert int(n_otros) == 0


def test_api_aplicar_masivo_00_99_bulk(app_mod, client):
    """100 números × 1 sorteo debe completarse rápido (bulk upsert, no 100 queries)."""
    app = app_mod
    c = app.db()
    cur = c.cursor()
    cur.execute(app._sql("INSERT INTO users (username, role) VALUES (%s, %s)"), ("bulk_lim", "cajero"))
    bid = cur.lastrowid
    _seed_lottery(cur, app)
    c.commit()
    c.close()

    _session_super(client)
    t0 = time.monotonic()
    r = client.post(
        "/api/admin/limites/global",
        json={
            "accion": "aplicar_masivo",
            "banca_id": bid,
            "lottery": "Loteka Test",
            "draw": "7:55 PM",
            "limite": 150,
            "aplicar_todos_numeros": True,
            "all_lotteries": False,
            "all_draws": False,
        },
    )
    elapsed = time.monotonic() - t0
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()
    assert data.get("ok") is True
    assert data.get("total") == 100
    assert data.get("numeros") == 100
    assert elapsed < 5.0, "bulk demasiado lento: %.2fs" % elapsed

    c2 = app.db()
    cur2 = c2.cursor()
    cur2.execute(
        app._sql("SELECT COUNT(*) AS n FROM limites_numeros WHERE banca_id=%s"),
        (bid,),
    )
    row = cur2.fetchone()
    c2.close()
    n = row["n"] if hasattr(row, "keys") else row[0]
    assert int(n) == 100


def test_api_vista_cajero_lista_y_resumen(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    cur.execute(app._sql("INSERT INTO users (username, role) VALUES (%s, %s)"), ("vista_caj", "cajero"))
    bid = cur.lastrowid
    _seed_lottery(cur, app)
    cur.execute(
        app._sql(
            """
            INSERT INTO limites_numeros (banca_id, lottery, draw, numero, limite, fecha_rd, activo)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
        ),
        (bid, "Loteka Test", "7:55 PM", "78", 300, "2026-06-12", 1),
    )
    cur.execute(
        app._sql(
            """
            INSERT INTO limites_numeros (banca_id, lottery, draw, numero, limite, fecha_rd, activo)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
        ),
        (bid, "Loteka Test", "7:55 PM", "55", 500, "2026-06-12", 1),
    )
    c.commit()
    c.close()

    _session_super(client)
    r = client.get("/api/admin/limites/global?vista=cajero&banca_id=%s" % bid)
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()
    assert data.get("ok") is True
    assert data.get("total") == 2
    assert len(data.get("items") or []) == 2
    res = data.get("resumen") or {}
    assert res.get("cajeros_con_limites") == 1
    assert res.get("numeros_limitados") == 2
    nums = {it["numero"] for it in data["items"]}
    assert nums == {"78", "55"}


def test_api_eliminar_cajero(app_mod, client):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    cur.execute(app._sql("INSERT INTO users (username, role) VALUES (%s, %s)"), ("del_caj", "cajero"))
    bid = cur.lastrowid
    cur.execute(
        app._sql(
            "INSERT INTO limites_numeros (banca_id, lottery, draw, numero, limite) VALUES (%s,%s,%s,%s,%s)"
        ),
        (bid, "L", "D", "01", 100),
    )
    c.commit()
    c.close()

    _session_super(client)
    r = client.post("/api/admin/limites/global", json={"accion": "eliminar_cajero", "banca_id": bid})
    assert r.status_code == 200
    assert r.get_json().get("borrados") == 1

    c2 = app.db()
    cur2 = c2.cursor()
    cur2.execute(app._sql("SELECT COUNT(*) AS n FROM limites_numeros WHERE banca_id=%s"), (bid,))
    row = cur2.fetchone()
    c2.close()
    n = row["n"] if hasattr(row, "keys") else row[0]
    assert int(n) == 0


def _session_admin(client):
    with client.session_transaction() as sess:
        sess["u"] = "admin_lim"
        sess["uid"] = 1
        sess["role"] = "admin"
        sess["last_activity"] = time.time()
        sess["last_activity_touch"] = time.time()


def test_admin_limites_post_guardar_rapido_sin_timeout(app_mod, client):
    """POST /admin/limites con todos los números no debe hacer upsert fila a fila."""
    app = app_mod
    c = app.db()
    cur = c.cursor()
    cur.execute(app._sql("INSERT INTO users (username, role) VALUES (%s, %s)"), ("banca_lim", "cajero"))
    bid = cur.lastrowid
    for i, draw in enumerate(("12:00 PM", "7:55 PM", "9:00 PM")):
        try:
            cur.execute(
                app._sql("INSERT INTO lotteries (lottery, draw) VALUES (%s, %s)"),
                ("Loteria %s" % i, draw),
            )
        except Exception:
            pass
    c.commit()
    c.close()

    _session_super(client)
    t0 = time.monotonic()
    r = client.post(
        "/admin/limites",
        data={
            "banca_id": str(bid),
            "limite": "150",
            "aplicar_todos": "on",
            "activar": "on",
            "meta_diaria": "5000",
        },
        follow_redirects=False,
    )
    elapsed_ms = int((time.monotonic() - t0) * 1000)
    assert r.status_code in (302, 303), r.get_data(as_text=True)[:500]
    assert elapsed_ms < 15000, "Guardar límites tardó demasiado: %sms" % elapsed_ms

    c2 = app.db()
    cur2 = c2.cursor()
    cur2.execute(
        app._sql("SELECT COUNT(*) AS n FROM limites_numeros WHERE banca_id=%s AND limite=%s"),
        (bid, 150.0),
    )
    row = cur2.fetchone()
    n = int(row["n"] if hasattr(row, "keys") else row[0])
    assert n >= 100
    cur2.execute(app._sql("SELECT value FROM config WHERE key=%s"), ("usar_limites",))
    cfg = cur2.fetchone()
    c2.close()
    val = cfg["value"] if hasattr(cfg, "keys") else cfg[0]
    assert str(val) == "1"
