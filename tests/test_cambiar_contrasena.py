"""Permisos y flujo de /superadmin/cambiar-contrasena."""
from __future__ import annotations

import time

from werkzeug.security import check_password_hash


def _session(client, *, role: str, username: str = "tester", uid: int = 99):
    with client.session_transaction() as sess:
        sess["u"] = username
        sess["uid"] = uid
        sess["role"] = role
        sess["last_activity"] = time.time()
        sess["last_activity_touch"] = time.time()


def _insert_cajero(app_mod):
    conn = app_mod.db()
    cur = conn.cursor()
    cur.execute(
        app_mod._sql("INSERT INTO users (username, role, password_hash) VALUES (%s, %s, %s)"),
        ("cajero_pw", "cajero", app_mod.generate_password_hash("vieja")),
    )
    conn.commit()
    uid = cur.lastrowid
    conn.close()
    return uid


def test_cambiar_contrasena_solo_super_admin(client, app_mod):
    target_id = _insert_cajero(app_mod)

    _session(client, role="cajero", username="cajero1", uid=2)
    r = client.post(
        f"/superadmin/cambiar-contrasena/{target_id}",
        json={"password": "nueva123", "password_confirm": "nueva123"},
    )
    assert r.status_code == 403

    _session(client, role="admin", username="admin1", uid=3)
    r = client.post(
        f"/superadmin/cambiar-contrasena/{target_id}",
        json={"password": "nueva123", "password_confirm": "nueva123"},
    )
    assert r.status_code == 403

    _session(client, role="super_admin", username="jose0219", uid=1)
    r = client.get("/superadmin/control-usuarios")
    assert r.status_code == 200
    assert "Cambiar contraseña" in r.get_data(as_text=True)
    assert f'href="/superadmin/cambiar-contrasena/{target_id}"' in r.get_data(as_text=True)

    r = client.get(f"/superadmin/cambiar-contrasena/{target_id}")
    assert r.status_code == 200
    assert "Nueva contraseña" in r.get_data(as_text=True)
    assert "cajero_pw" in r.get_data(as_text=True)

    r = client.post(
        f"/superadmin/cambiar-contrasena/{target_id}",
        json={"password": "nueva123", "password_confirm": "nueva123"},
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("ok") is True
    assert data.get("message") == "Contraseña actualizada correctamente"

    r = client.post(
        f"/superadmin/cambiar-contrasena/{target_id}",
        data={"password": "otra789", "password_confirm": "otra789"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert "Contraseña actualizada correctamente" in r.get_data(as_text=True)

    conn = app_mod.db()
    cur = conn.cursor()
    cur.execute(app_mod._sql("SELECT password_hash FROM users WHERE id=%s"), (target_id,))
    row = cur.fetchone()
    conn.close()
    pwd_hash = row["password_hash"] if hasattr(row, "keys") else row[0]
    assert check_password_hash(pwd_hash, "otra789")
    assert not check_password_hash(pwd_hash, "nueva123")


def test_control_usuarios_403_admin_cajero(client, app_mod):
    target_id = _insert_cajero(app_mod)

    _session(client, role="admin", username="admin1", uid=3)
    assert client.get("/superadmin/control-usuarios").status_code == 403
    assert client.get(f"/superadmin/cambiar-contrasena/{target_id}").status_code == 403

    _session(client, role="cajero", username="cajero1", uid=2)
    assert client.get("/superadmin/control-usuarios").status_code == 403
    assert client.get(f"/superadmin/cambiar-contrasena/{target_id}").status_code == 403
