"""Pale: no debe pagarse como Quiniela con un solo acierto."""
from __future__ import annotations


R1, R2, R3 = "05", "12", "30"


def test_quiniela_05_gana(app_mod):
    app = app_mod
    p = float(app.calcular_premio("Quiniela", "05", 10.0, R1, R2, R3) or 0)
    assert p > 0


def test_pale_05_50_no_gana_con_solo_05(app_mod):
    app = app_mod
    p = float(app.calcular_premio("Pale", "05-50", 10.0, R1, R2, R3) or 0)
    assert p == 0.0
    p2 = float(app.calcular_premio("Quiniela", "05-50", 10.0, R1, R2, R3) or 0)
    assert p2 == 0.0


def test_pale_05_12_gana(app_mod):
    app = app_mod
    p = float(app.calcular_premio("Pale", "05-12", 10.0, R1, R2, R3) or 0)
    esperado = 10.0 * float(app.PAGO_PALE)
    assert abs(p - esperado) < 0.01


def test_tripleta_completa_gana(app_mod):
    app = app_mod
    p = float(app.calcular_premio("Tripleta", "05-12-30", 2.0, R1, R2, R3) or 0)
    esperado = 2.0 * float(app.PAGOS["tripleta"])
    assert abs(p - esperado) < 0.01


def test_tripleta_parcial_no_gana(app_mod):
    app = app_mod
    p = float(app.calcular_premio("Tripleta", "05-12-40", 2.0, R1, R2, R3) or 0)
    assert p == 0.0


def test_play_efectivo_cruce_infiere_pale(app_mod):
    app = app_mod
    assert app._play_efectivo_cruce("Quiniela", "05-50") == "Pale"
    assert app._quiniela_jugados_desde_campo("05-50") == []


def test_coincide_resultado_pale_parcial_falso(app_mod):
    app = app_mod
    assert app._ganadores_numero_coincide_resultado("Pale", "05-50", R1, R2, R3) is False
    assert app._ganadores_numero_coincide_resultado("Quiniela", "05-50", R1, R2, R3) is False


def test_procesar_filas_pale_mal_play_no_ganador(app_mod):
    app = app_mod
    from tests.test_ganadores_strict import _seed_resultado_row

    c = app.db()
    cur = c.cursor()
    lot = "Loteria Nacional"
    drw = "2:30 PM"
    fe = "2026-06-12"
    _seed_resultado_row(app, cur, lot, drw, fe, R1, R2, R3)
    cur.execute(
        app._sql(
            """
            INSERT INTO tickets (cajero, created_at, pagado) VALUES ('test', %s, 0)
            """
        ),
        ("%s 10:00:00" % fe,),
    )
    tid = cur.lastrowid
    cur.execute(
        app._sql(
            """
            INSERT INTO ticket_lines (ticket_id, lottery, draw, number, play, amount, fecha_sorteo, pagado, premio_linea_pagada)
            VALUES (%s, %s, %s, %s, 'Quiniela', %s, %s, 0, 0)
            """
        ),
        (tid, lot, drw, "05-50", 10.0, fe),
    )
    c.commit()

    join_rows = app._ganadores_fetch_lineas_vs_resultados(cur, fe, ticket_id=tid)
    lista = app._ganadores_procesar_filas(
        join_rows, pagos=app.PAGOS, hoy_rd_str=fe, cur=cur
    )
    assert lista == []
    c.close()


def test_prueba_obligatoria_resultado_05_12_30(app_mod):
    """Caso del reporte: resultado 05-12-30."""
    app = app_mod
    r1, r2, r3 = R1, R2, R3
    assert float(app.calcular_premio("Pale", "05-50", 10.0, r1, r2, r3) or 0) == 0.0
    assert float(app.calcular_premio("Pale", "05-12", 10.0, r1, r2, r3) or 0) > 0.0
    assert float(app.calcular_premio("Quiniela", "05", 10.0, r1, r2, r3) or 0) > 0.0
    assert app._play_efectivo_cruce("Quiniela", "05-50") == "Pale"
    assert app._ganadores_numero_coincide_resultado("Quiniela", "05-50", r1, r2, r3) is False
