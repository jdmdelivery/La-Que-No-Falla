"""Tripleta: no debe pagarse como Quiniela con un solo acierto."""
from __future__ import annotations


def test_tripleta_solo_primer_numero_no_premia(app_mod):
    app = app_mod
    # Resultado: 41-20-30 — solo acertó el 41
    p = float(
        app.calcular_premio("Tripleta", "41-39-71", 10.0, "41", "20", "30") or 0
    )
    assert p == 0.0


def test_tripleta_mal_play_quiniela_no_premia(app_mod):
    """Formato tripleta nunca entra en lógica Quiniela aunque play diga Quiniela."""
    app = app_mod
    p = float(
        app.calcular_premio("Quiniela", "41-39-71", 10.0, "41", "20", "30") or 0
    )
    assert p == 0.0


def test_tripleta_tres_aciertos_premia(app_mod):
    app = app_mod
    p = float(
        app.calcular_premio("Tripleta", "41-39-71", 2.0, "41", "39", "71") or 0
    )
    esperado = 2.0 * float(app.PAGOS["tripleta"])
    assert abs(p - esperado) < 0.01


def test_coincide_resultado_tripleta_parcial_falso(app_mod):
    app = app_mod
    ok = app._ganadores_numero_coincide_resultado(
        "Tripleta", "41-39-71", "41", "20", "30"
    )
    assert ok is False


def test_quiniela_jugados_no_descompone_tripleta(app_mod):
    app = app_mod
    assert app._quiniela_jugados_desde_campo("41-39-71") == []


def test_procesar_filas_tripleta_parcial_sin_ganador(app_mod):
    app = app_mod
    from tests.test_ganadores_strict import _seed_resultado_row

    c = app.db()
    cur = c.cursor()
    lot = "Loteria Nacional"
    drw = "2:30 PM"
    fe = "2026-06-11"
    _seed_resultado_row(app, cur, lot, drw, fe, "41", "20", "30")
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
            VALUES (%s, %s, %s, %s, 'Tripleta', %s, %s, 0, 0)
            """
        ),
        (tid, lot, drw, "41-39-71", 10.0, fe),
    )
    c.commit()

    join_rows = app._ganadores_fetch_lineas_vs_resultados(cur, fe, ticket_id=tid)
    lista = app._ganadores_procesar_filas(
        join_rows, pagos=app.PAGOS, hoy_rd_str=fe, cur=cur
    )
    assert lista == []
