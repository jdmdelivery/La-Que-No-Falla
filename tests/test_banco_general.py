"""Tests del módulo Banco General + subcuentas por cajero."""
from __future__ import annotations

import sqlite3

import pytest

import banco_general as bg


@pytest.fixture
def banco_db(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            role TEXT
        )
        """
    )
    cur.execute("INSERT INTO users (id, username, role) VALUES (1, 'maria', 'cajero')")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY,
            cajero_id INTEGER,
            cajero TEXT,
            monto REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ticket_lines (
            id INTEGER PRIMARY KEY,
            ticket_id INTEGER,
            amount REAL,
            estado TEXT DEFAULT 'activo'
        )
        """
    )
    bg.banco_init_schema(cur, "INTEGER PRIMARY KEY AUTOINCREMENT")
    conn.commit()
    yield conn, cur
    conn.close()


def test_balance_inicial_y_venta(banco_db):
    conn, cur = banco_db
    bg.banco_configurar_inicial(cur, 50000, usuario_admin_id=99, nota="Apertura")
    assert bg.banco_get_balance_general(cur) == 50000.0
    bg.banco_registrar_venta(cur, 101, 1, 10000, cajero_username="maria")
    conn.commit()
    assert bg.banco_get_balance_general(cur) == 60000.0
    assert bg.banco_get_balance_cajero(cur, 1) == 10000.0


def test_premio_y_entrega_no_toca_banco_general(banco_db):
    conn, cur = banco_db
    bg.banco_configurar_inicial(cur, 50000)
    bg.banco_registrar_venta(cur, 1, 1, 10000)
    bg.banco_registrar_pago(cur, 501, 1, 2000, ticket_id=1)
    assert bg.banco_get_balance_general(cur) == 58000.0
    assert bg.banco_get_balance_cajero(cur, 1) == 8000.0
    bg.banco_entrega_cajero_admin(cur, 1, 5000, nota="Entrega física")
    assert bg.banco_get_balance_general(cur) == 58000.0
    assert bg.banco_get_balance_cajero(cur, 1) == 3000.0
    conn.commit()


def test_fondo_cajero_solo_balance_cajero(banco_db):
    conn, cur = banco_db
    bg.banco_configurar_inicial(cur, 10000)
    bg.banco_entregar_fondo_cajero(cur, 1, 2000, nota="Fondo turno")
    assert bg.banco_get_balance_general(cur) == 10000.0
    assert bg.banco_get_balance_cajero(cur, 1) == 2000.0


def test_idempotencia_venta(banco_db):
    conn, cur = banco_db
    bg.banco_configurar_inicial(cur, 0)
    bg.banco_registrar_venta(cur, 55, 1, 500)
    bg.banco_registrar_venta(cur, 55, 1, 500)
    assert bg.banco_get_balance_general(cur) == 500.0


def test_entrega_rechaza_saldo_insuficiente(banco_db):
    conn, cur = banco_db
    bg.banco_configurar_inicial(cur, 0)
    bg.banco_registrar_venta(cur, 1, 1, 1000)
    with pytest.raises(ValueError, match="saldo_cajero_insuficiente"):
        bg.banco_entrega_cajero_admin(cur, 1, 5000)


def test_resumen_formula_ventas_premios_entrega_no_duplica_banco(banco_db):
    """Inicial + ventas − premios; entregas físicas no restan del Banco General."""
    conn, cur = banco_db
    fr = bg._fecha_hoy_rd_iso()
    bg.banco_configurar_inicial(cur, 0)
    bg.banco_registrar_venta(cur, 201, 1, 545.0)
    bg.banco_registrar_pago(cur, 301, 1, 120.0, ticket_id=201, premio_id=7)
    assert bg.banco_get_balance_general(cur) == 425.0
    bg.banco_entrega_cajero_admin(cur, 1, 200.0)
    assert bg.banco_get_balance_general(cur) == 425.0
    res = bg.banco_resumen_global(
        cur, fr, premios_pendientes=80.0, ciclo_ventas=545.0, ventas_ciclo_ref=545.0,
        premios_ciclo_ref=120.0, entregas_ciclo_ref=200.0,
    )
    assert res["banco_general"] == 425.0
    assert res["ventas_hoy"] == 545.0
    assert res["premios_pagados_hoy"] == 120.0
    assert res["pendiente_premios"] == 80.0
    assert res["dinero_en_cajeros"] == 225.0
    assert res["pendiente_en_manos_cajeros"] == 225.0
    assert res["ciclo_actual"] == 545.0
    conn.commit()


def test_resumen_dinero_cajeros_desde_refs_sin_movimientos(banco_db):
    """Pendiente en cajeros = ventas − premios − entregas aunque no haya movimientos."""
    conn, cur = banco_db
    fr = bg._fecha_hoy_rd_iso()
    bg.banco_configurar_inicial(cur, 44010.0)
    res = bg.banco_resumen_global(
        cur,
        fr,
        premios_pendientes=120.0,
        pendiente_total=120.0,
        ventas_ciclo_ref=545.0,
        ciclo_ventas=545.0,
        ventas_dia_ref=545.0,
        premios_pagados_dia_ref=0.0,
        entregas_dia_ref=0.0,
    )
    assert res["saldo_base"] == 44010.0
    assert res["banco_general"] == 44010.0
    assert res["banco_final"] == 44010.0
    assert res["ventas_hoy"] == 545.0
    assert res["ventas_delta"] == 545.0
    assert res["dinero_en_cajeros"] == 545.0
    assert res["pendiente_premios"] == 120.0
    assert res["neto_disponible"] == 43890.0
    conn.commit()


def test_banco_final_resta_premio_pagado(banco_db):
    conn, cur = banco_db
    fr = bg._fecha_hoy_rd_iso()
    bg.banco_configurar_inicial(cur, 44010.0)
    bg.banco_registrar_venta(cur, 301, 1, 545.0)
    bg.banco_registrar_pago(cur, 401, 1, 120.0, ticket_id=301, premio_id=9)
    res = bg.banco_resumen_global(
        cur,
        fr,
        ventas_ciclo_ref=545.0,
        ciclo_ventas=545.0,
        premios_ciclo_ref=120.0,
        premios_pendientes=0.0,
    )
    assert res["banco_final"] == 44435.0
    assert res["dinero_en_cajeros"] == 425.0
    assert res["premios_pagados_hoy"] == 120.0
    conn.commit()


def test_recalc_alinea_balance_si_hay_venta_sin_reflejar_en_saldo(banco_db):
    """Movimiento venta_ticket existe pero balance_actual desactualizado → recalc corrige."""
    conn, cur = banco_db
    fr = bg._fecha_hoy_rd_iso()
    bg.banco_configurar_inicial(cur, 44010.0)
    bg.banco_registrar_venta(cur, 777, 1, 545.0)
    bid, _, _ = bg._ensure_banco_general_row(cur)
    cur.execute(
        "UPDATE banco_general SET balance_actual = ? WHERE id = ?",
        (44010.0, bid),
    )
    res = bg.banco_resumen_global(
        cur, fr, ventas_ciclo_ref=545.0, ciclo_ventas=545.0, ventas_dia_ref=545.0
    )
    assert res["saldo_base"] == 44555.0
    assert res["banco_final"] == 44555.0
    assert res["dinero_en_cajeros"] == 545.0
    conn.commit()


def test_reversa_pago_excluye_de_premios_pagados_hoy(banco_db):
    conn, cur = banco_db
    fr = bg._fecha_hoy_rd_iso()
    bg.banco_configurar_inicial(cur, 44010.0)
    bg.banco_registrar_venta(cur, 501, 1, 545.0)
    bg.banco_registrar_pago(cur, 601, 1, 40.0, ticket_id=501, premio_id=12)
    res1 = bg.banco_resumen_global(
        cur, fr, ventas_ciclo_ref=545.0, ciclo_ventas=545.0, premios_ciclo_ref=40.0
    )
    assert res1["premios_pagados_hoy"] == 40.0
    assert res1["dinero_en_cajeros"] == 505.0
    cur.execute(
        "SELECT id FROM banco_movimientos WHERE tipo = ? AND ticket_id = ? LIMIT 1",
        (bg.TIPO_PREMIO, 501),
    )
    row = cur.fetchone()
    mov_id = int(row[0])
    bg.banco_revertir_movimiento_premio(cur, mov_id, nota="test reversa")
    res2 = bg.banco_resumen_global(
        cur,
        fr,
        ventas_ciclo_ref=545.0,
        ciclo_ventas=545.0,
        premios_ciclo_ref=0.0,
    )
    assert res2["premios_pagados_hoy"] == 0.0
    assert res2["dinero_en_cajeros"] == 545.0
    assert res2["banco_final"] == 44555.0
    conn.commit()


def test_banco_sync_ventas_idempotente(banco_db):
    conn, cur = banco_db
    fr = bg._fecha_hoy_rd_iso()
    bg.banco_configurar_inicial(cur, 1000.0)
    cur.execute(
        "INSERT INTO tickets (id, cajero_id, cajero, monto, created_at) VALUES (901, 1, 'maria', 250, ?)",
        (fr + " 12:00:00",),
    )
    s1 = bg.banco_sync_ventas(cur, fr)
    assert s1["revisados"] >= 1, s1
    assert s1["creados"] == 1
    assert bg.banco_get_balance_general(cur) == 1250.0
    s2 = bg.banco_sync_ventas(cur, fr)
    assert s2["creados"] == 0
    assert s2["omitidos_duplicado"] >= 1
    assert bg.banco_get_balance_general(cur) == 1250.0
    conn.commit()


def test_retiro_banco_y_ajuste_manual(banco_db):
    conn, cur = banco_db
    fr = bg._fecha_hoy_rd_iso()
    bg.banco_configurar_inicial(cur, 44010.0)
    bg.banco_registrar_venta(cur, 801, 1, 545.0)
    bg.banco_retiro_general(cur, 50.0, nota="Retiro caja fuerte")
    bg.banco_ajuste_manual(cur, 25.0, "+", nota="Corrección inventario")
    res = bg.banco_resumen_global(
        cur, fr, ventas_ciclo_ref=545.0, ciclo_ventas=545.0, ventas_dia_ref=545.0
    )
    assert res["retiros_hoy"] == 50.0
    assert res["ajustes_hoy_neto"] == 25.0
    assert res["banco_final"] == 44530.0  # 44010 + 545 - 50 + 25
    conn.commit()


def test_auditoria_consultar_periodo_hoy(banco_db):
    conn, cur = banco_db
    fr = bg._fecha_hoy_rd_iso()
    bg.banco_configurar_inicial(cur, 1000.0)
    bg.banco_registrar_venta(cur, 901, 1, 100.0)
    bg.banco_registrar_pago(cur, 902, 1, 30.0, ticket_id=901)
    aud = bg.banco_auditoria_consultar(cur, periodo="hoy", fecha_rd=fr)
    assert aud["periodo"] == "hoy"
    tipos = {m["tipo"] for m in aud["movimientos"]}
    assert "venta_ticket" in tipos
    assert "premio_pagado" in tipos
    assert len(aud["movimientos"]) >= 3
    conn.commit()


def test_resumen_ciclo_545_sin_movimientos_ni_tickets_dia(banco_db):
    """Caso producción: ciclo RD$545 en tickets reales, sin movimientos venta_ticket aún."""
    conn, cur = banco_db
    fr = bg._fecha_hoy_rd_iso()
    bg.banco_configurar_inicial(cur, 44010.0)
    res = bg.banco_resumen_global(
        cur,
        fr,
        premios_pendientes=120.0,
        pendiente_total=120.0,
        ventas_ciclo_ref=545.0,
        ciclo_ventas=545.0,
        premios_ciclo_ref=0.0,
        entregas_ciclo_ref=0.0,
    )
    assert res["saldo_base_banco"] == 44010.0
    assert res["ventas_hoy"] == 545.0
    assert res["banco_general"] == 44010.0
    assert res["ventas_delta"] == 545.0
    assert res["pendiente_premios"] == 120.0
    assert res["pendiente_total"] == 120.0
    assert res["dinero_en_cajeros"] == 545.0
    assert res["ciclo_actual"] == 545.0
    conn.commit()


def test_escenario_usuario_44010_545_120(banco_db):
    """44,010 + 545 = 44,555; −120 = 44,435; cajero 425; premios pendientes 0 tras pagar."""
    conn, cur = banco_db
    fr = bg._fecha_hoy_rd_iso()
    bg.banco_configurar_inicial(cur, 44010.0)
    res_antes = bg.banco_resumen_global(
        cur,
        fr,
        ventas_ciclo_ref=545.0,
        ciclo_ventas=545.0,
        ventas_dia_ref=545.0,
        premios_pendientes=120.0,
        pendiente_total=120.0,
    )
    assert res_antes["banco_final"] == 44010.0
    assert res_antes["dinero_en_cajeros"] == 545.0
    assert res_antes["pendiente_premios"] == 120.0
    assert res_antes["ventas_delta"] == 545.0

    bg.banco_registrar_venta(cur, 1001, 1, 545.0)
    bg.banco_registrar_pago(cur, 1002, 1, 120.0, ticket_id=1001, premio_id=55)
    res_despues = bg.banco_resumen_global(
        cur,
        fr,
        ventas_ciclo_ref=545.0,
        ciclo_ventas=545.0,
        ventas_dia_ref=545.0,
        premios_ciclo_ref=120.0,
        premios_pagados_dia_ref=120.0,
        premios_pendientes=0.0,
        pendiente_total=0.0,
    )
    assert res_despues["banco_final"] == 44435.0
    assert res_despues["dinero_en_cajeros"] == 425.0
    assert res_despues["premios_pagados_hoy"] == 120.0
    assert res_despues["pendiente_premios"] == 0.0
    assert res_despues["neto_disponible"] == 44435.0
    assert bg.banco_get_balance_cajero(cur, 1) == 425.0
    conn.commit()


def test_metricas_operativas_cero_si_ciclo_vacio(banco_db):
    """Tras cierre: métricas operativas en cero; Banco General conserva saldo acumulado."""
    conn, cur = banco_db
    fr = bg._fecha_hoy_rd_iso()
    bg.banco_configurar_inicial(cur, 44660.0)
    res = bg.banco_resumen_global(
        cur,
        fr,
        ventas_ciclo_ref=0.0,
        premios_ciclo_ref=0.0,
        entregas_ciclo_ref=0.0,
        ciclo_ventas=0.0,
        premios_pendientes=0.0,
        pendiente_total=0.0,
        ultimo_cierre=fr + " 12:00:00",
    )
    assert res["banco_general"] == 44660.0
    assert res["ciclo_actual"] == 0.0
    assert res["dinero_en_cajeros"] == 0.0
    assert res["pendiente_premios"] == 0.0
    assert res["premios_pagados_hoy"] == 0.0
    assert res["retiros_hoy"] == 0.0
    assert res["ajustes_hoy_neto"] == 0.0
    assert res["neto_disponible"] == 44660.0
    conn.commit()


def test_banco_general_estable_tras_cierre_ciclo(banco_db):
    """Tras cierre: dinero_en_cajeros→0 pero Banco General conserva saldo (sync + sin ventas_delta)."""
    conn, cur = banco_db
    fr = bg._fecha_hoy_rd_iso()
    bg.banco_configurar_inicial(cur, 43338.0)
    cur.execute(
        "INSERT INTO tickets (id, cajero_id, cajero, monto, created_at) VALUES (5001, 1, 'maria', 1890, ?)",
        (fr + " 10:00:00",),
    )
    bg.banco_sync_ventas(cur, fr, desde_cierre=None)
    assert bg.banco_get_balance_general(cur) == 45228.0
    res_antes = bg.banco_resumen_global(
        cur,
        fr,
        ventas_ciclo_ref=1890.0,
        ciclo_ventas=1890.0,
        entregas_ciclo_ref=0.0,
        premios_ciclo_ref=0.0,
    )
    assert res_antes["banco_general"] == 45228.0
    assert res_antes["dinero_en_cajeros"] == 1890.0

    res_despues = bg.banco_resumen_global(
        cur,
        fr,
        ventas_ciclo_ref=0.0,
        ciclo_ventas=0.0,
        entregas_ciclo_ref=0.0,
        premios_ciclo_ref=0.0,
        ultimo_cierre=fr + " 18:00:00",
    )
    assert res_despues["banco_general"] == 45228.0
    assert res_despues["dinero_en_cajeros"] == 0.0
    assert res_despues["ciclo_actual"] == 0.0
    conn.commit()


def test_fondo_y_entrega_balance_cajero(banco_db):
    conn, cur = banco_db
    bg.banco_configurar_inicial(cur, 5000.0)
    bg.banco_registrar_venta(cur, 1101, 1, 1000.0)
    bg.banco_entregar_fondo_cajero(cur, 1, 200.0)
    assert bg.banco_get_balance_cajero(cur, 1) == 1200.0
    bg.banco_entrega_cajero_admin(cur, 1, 300.0)
    assert bg.banco_get_balance_cajero(cur, 1) == 900.0
    conn.commit()
