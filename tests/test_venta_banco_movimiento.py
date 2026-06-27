"""Venta → banco_movimientos (afecta_banco INTEGER en schema app)."""
import sqlite3

import pytest


def _app_banco_schema(cur):
    cur.execute(
        """
        CREATE TABLE banco_general (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            balance_inicial REAL NOT NULL DEFAULT 0,
            balance_actual REAL NOT NULL DEFAULT 0,
            creado_por TEXT,
            updated_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE banco_movimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            monto REAL NOT NULL DEFAULT 0,
            afecta_banco INTEGER NOT NULL DEFAULT 0,
            suma_o_resta TEXT NOT NULL DEFAULT '+',
            balance_general_antes REAL NOT NULL DEFAULT 0,
            balance_general_despues REAL NOT NULL DEFAULT 0,
            cajero_balance_antes REAL,
            cajero_balance_despues REAL,
            cajero_id INTEGER,
            usuario_admin_id INTEGER,
            ticket_id INTEGER,
            pago_id INTEGER,
            descripcion TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL)")
    cur.execute("INSERT INTO users (id, username) VALUES (1, 'cajero1')")


def test_banco_bool_for_db_integer_on_pg(app_mod, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    assert app_mod._banco_bool_for_db(True) == 1
    assert app_mod._banco_bool_for_db(False) == 0
    assert isinstance(app_mod._banco_bool_for_db(True), int)


def test_banco_registrar_venta_integer_afecta_banco(app_mod):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    _app_banco_schema(cur)
    app_mod.banco_configurar_inicial(cur, 1000.0, usuario_admin_id=99)
    out = app_mod.banco_registrar_venta(cur, 42, 1, 50.0, descripcion="Venta ticket #42")
    assert out.get("duplicado") is not True
    assert app_mod.banco_get_balance_general(cur) == 1050.0
    cur.execute("SELECT afecta_banco FROM banco_movimientos WHERE ticket_id = 42")
    row = cur.fetchone()
    assert int(row[0]) == 1
    conn.close()
