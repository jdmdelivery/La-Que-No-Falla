"""
Regresión obligatoria: recálculo/detección de premios ganadores.
"""
from __future__ import annotations

import logging
from datetime import datetime

import pytest

from tests.test_ganadores_strict import (
    DRAW,
    FECHA,
    LOTERY,
    _seed_resultado_row,
    _seed_ticket_line,
)


def _monkey_hoy(app, monkeypatch, fe, hora=20):
    try:
        import pytz
    except ImportError:
        pytest.skip("pytz requerido")
    tz = pytz.timezone("America/Santo_Domingo")
    y, m, d = [int(x) for x in fe.split("-")]
    monkeypatch.setattr(app, "ahora_rd", lambda: tz.localize(datetime(y, m, d, hora, 0, 0)))


def _recalc(app, cur, fe, cajero=None):
    sync = app._recalcular_ganadores_fecha_completo(cur, fe, cajero_username=cajero)
    assert sync.get("ok") is True
    return sync


def _premios_linea(cur, app, fe, line_id):
    cur.execute(
        app._sql(
            "SELECT COUNT(*) AS n, COALESCE(SUM(premio), 0) AS s FROM premios WHERE line_id = %s"
        ),
        (line_id,),
    )
    row = cur.fetchone()
    if hasattr(row, "keys"):
        return int(row["n"] or 0), float(row["s"] or 0)
    return int(row[0] or 0), float(row[1] or 0)


def test_ticket_526_la_primera_12pm_quiniela_40_tercer_premio(app_mod, monkeypatch):
    app = app_mod
    fe = "2026-06-17"
    _monkey_hoy(app, monkeypatch, fe, 14)
    c = app.db()
    cur = c.cursor()
    app._premios_migrate_unique_constraints(cur)
    _seed_resultado_row(app, cur, "La Primera", "12:00 PM", fe, "00", "18", "40")

    tid, _ = _seed_ticket_line(
        app, cur, "09", 100.0, fecha_sorteo=fe, lottery="La Primera", draw="12:00 PM"
    )
    _, lid_40 = _seed_ticket_line(
        app, cur, "40", 100.0, fecha_sorteo=fe, lottery="La Primera", draw="12:00 PM", ticket_id=tid
    )
    c.commit()

    sync = _recalc(app, cur, fe)
    assert int(sync.get("filas_cruce") or 0) >= 1
    c.commit()

    n, total = _premios_linea(cur, app, fe, lid_40)
    assert n == 1
    assert total > 0
    c.close()


@pytest.mark.parametrize(
    "numero,pos",
    [
        ("45", 1),
        ("70", 2),
        ("52", 3),
    ],
)
def test_quiniela_gana_en_cada_premio(app_mod, monkeypatch, numero, pos):
    """Quiniela gana si el número coincide con 1er, 2do o 3er premio."""
    app = app_mod
    fe = FECHA
    _monkey_hoy(app, monkeypatch, fe)
    premios = ["99", "99", "99"]
    premios[pos - 1] = numero
    c = app.db()
    cur = c.cursor()
    app._premios_migrate_unique_constraints(cur)
    _seed_resultado_row(app, cur, LOTERY, DRAW, fe, premios[0], premios[1], premios[2])
    _, lid = _seed_ticket_line(app, cur, numero, 10.0, fecha_sorteo=fe)
    c.commit()

    _recalc(app, cur, fe)
    c.commit()
    n, total = _premios_linea(cur, app, fe, lid)
    assert n == 1
    assert total > 0
    c.close()


def test_pale_solo_gana_con_dos_numeros(app_mod, monkeypatch):
    app = app_mod
    fe = "2026-06-12"
    _monkey_hoy(app, monkeypatch, fe)
    lot, drw = "Loteria Nacional", "2:30 PM"
    c = app.db()
    cur = c.cursor()
    app._premios_migrate_unique_constraints(cur)
    _seed_resultado_row(app, cur, lot, drw, fe, "05", "12", "30")

    cur.execute(
        app._sql("INSERT INTO tickets (cajero, created_at, pagado) VALUES ('test', %s, 0)"),
        ("%s 10:00:00" % fe,),
    )
    tid = cur.lastrowid
    cur.execute(
        app._sql(
            """
            INSERT INTO ticket_lines (ticket_id, lottery, draw, number, play, amount, fecha_sorteo, pagado, premio_linea_pagada)
            VALUES (%s, %s, %s, %s, 'Pale', %s, %s, 0, 0)
            """
        ),
        (tid, lot, drw, "05-50", 10.0, fe),
    )
    lid_parcial = cur.lastrowid
    cur.execute(
        app._sql(
            """
            INSERT INTO ticket_lines (ticket_id, lottery, draw, number, play, amount, fecha_sorteo, pagado, premio_linea_pagada)
            VALUES (%s, %s, %s, %s, 'Pale', %s, %s, 0, 0)
            """
        ),
        (tid, lot, drw, "05-12", 10.0, fe),
    )
    lid_full = cur.lastrowid
    c.commit()

    _recalc(app, cur, fe)
    c.commit()

    n_parcial, _ = _premios_linea(cur, app, fe, lid_parcial)
    n_full, total_full = _premios_linea(cur, app, fe, lid_full)
    assert n_parcial == 0
    assert n_full == 1
    assert total_full > 0
    c.close()


def test_tripleta_solo_gana_con_tres_numeros(app_mod, monkeypatch):
    app = app_mod
    fe = "2026-06-13"
    _monkey_hoy(app, monkeypatch, fe)
    lot, drw = "Loteria Nacional", "2:30 PM"
    c = app.db()
    cur = c.cursor()
    app._premios_migrate_unique_constraints(cur)
    _seed_resultado_row(app, cur, lot, drw, fe, "05", "12", "30")

    cur.execute(
        app._sql("INSERT INTO tickets (cajero, created_at, pagado) VALUES ('test', %s, 0)"),
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
        (tid, lot, drw, "05-12-40", 2.0, fe),
    )
    lid_parcial = cur.lastrowid
    cur.execute(
        app._sql(
            """
            INSERT INTO ticket_lines (ticket_id, lottery, draw, number, play, amount, fecha_sorteo, pagado, premio_linea_pagada)
            VALUES (%s, %s, %s, %s, 'Tripleta', %s, %s, 0, 0)
            """
        ),
        (tid, lot, drw, "05-12-30", 2.0, fe),
    )
    lid_full = cur.lastrowid
    c.commit()

    _recalc(app, cur, fe)
    c.commit()

    n_parcial, _ = _premios_linea(cur, app, fe, lid_parcial)
    n_full, total_full = _premios_linea(cur, app, fe, lid_full)
    assert n_parcial == 0
    assert n_full == 1
    assert total_full > 0
    c.close()


def test_recalcular_dos_veces_no_duplica_premios(app_mod, monkeypatch):
    app = app_mod
    fe = "2026-05-28"
    _monkey_hoy(app, monkeypatch, fe)
    c = app.db()
    cur = c.cursor()
    app._premios_migrate_unique_constraints(cur)
    _seed_resultado_row(app, cur, "Loteria Nacional", "2:30 PM", fe, "26", "08", "41")
    _, lid = _seed_ticket_line(
        app, cur, "41", 10.0, fecha_sorteo=fe, lottery="Loteria Nacional", draw="2:30 PM"
    )
    c.commit()

    _recalc(app, cur, fe)
    c.commit()
    n1, _ = _premios_linea(cur, app, fe, lid)
    _recalc(app, cur, fe)
    c.commit()
    n2, _ = _premios_linea(cur, app, fe, lid)
    assert n1 == 1
    assert n2 == 1
    c.close()


def test_no_ganador_otra_loteria(app_mod, monkeypatch):
    app = app_mod
    fe = FECHA
    _monkey_hoy(app, monkeypatch, fe)
    c = app.db()
    cur = c.cursor()
    app._premios_migrate_unique_constraints(cur)
    _seed_resultado_row(app, cur, LOTERY, DRAW, fe, "45", "70", "52")
    _, lid = _seed_ticket_line(
        app, cur, "45", 10.0, fecha_sorteo=fe, lottery="La Primera", draw="12:00 PM"
    )
    c.commit()

    _recalc(app, cur, fe)
    c.commit()
    n, _ = _premios_linea(cur, app, fe, lid)
    assert n == 0
    c.close()


def test_no_ganador_otra_fecha(app_mod, monkeypatch):
    app = app_mod
    fe_hoy = FECHA
    fe_ayer = "2026-05-04"
    _monkey_hoy(app, monkeypatch, fe_hoy)
    c = app.db()
    cur = c.cursor()
    app._premios_migrate_unique_constraints(cur)
    _seed_resultado_row(app, cur, LOTERY, DRAW, fe_hoy, "45", "70", "52")
    _, lid = _seed_ticket_line(app, cur, "45", 10.0, fecha_sorteo=fe_ayer)
    c.commit()

    _recalc(app, cur, fe_hoy)
    c.commit()
    n, _ = _premios_linea(cur, app, fe_hoy, lid)
    assert n == 0
    c.close()


def test_ticket_eliminado_no_gana(app_mod, monkeypatch):
    app = app_mod
    fe = FECHA
    _monkey_hoy(app, monkeypatch, fe)
    c = app.db()
    cur = c.cursor()
    app._premios_migrate_unique_constraints(cur)
    _seed_resultado_row(app, cur, LOTERY, DRAW, fe, "45", "70", "52")
    cur.execute(
        app._sql(
            """
            INSERT INTO tickets (cajero, created_at, pagado, eliminado)
            VALUES ('test', %s, 0, 1)
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
        (tid, LOTERY, DRAW, "45", 10.0, fe),
    )
    lid = cur.lastrowid
    c.commit()

    _recalc(app, cur, fe)
    c.commit()
    n, _ = _premios_linea(cur, app, fe, lid)
    assert n == 0
    c.close()


def test_recalc_log_tag_recalc_premios(app_mod, monkeypatch, caplog):
    """El recálculo emite trazas [RECALC_PREMIOS]."""
    app = app_mod
    fe = FECHA
    _monkey_hoy(app, monkeypatch, fe)
    c = app.db()
    cur = c.cursor()
    app._premios_migrate_unique_constraints(cur)
    _seed_resultado_row(app, cur, LOTERY, DRAW, fe, "45", "70", "52")
    _, lid = _seed_ticket_line(app, cur, "45", 10.0, fecha_sorteo=fe)
    c.commit()

    caplog.set_level(logging.INFO, logger="app")
    _recalc(app, cur, fe)
    c.commit()

    msgs = [r.message for r in caplog.records if "[RECALC_PREMIOS]" in r.message]
    assert any("jugada_id=" in m and str(lid) in m for m in msgs)
    assert any("coincide=true" in m for m in msgs)
    c.close()


def test_loteria_compuesta_la_primera_12pm_guarda_y_lista_ganadores(app_mod, monkeypatch):
    """POS guarda «La Primera 12:00 PM» en lottery y draw vacío → recalc persiste y /ganadores lee premios."""
    app = app_mod
    fe = "2026-06-17"
    _monkey_hoy(app, monkeypatch, fe, 14)
    c = app.db()
    cur = c.cursor()
    app._premios_migrate_unique_constraints(cur)
    _seed_resultado_row(app, cur, "La Primera", "12:00 PM", fe, "00", "18", "40")

    cur.execute(
        app._sql(
            "INSERT INTO tickets (cajero, created_at, pagado) VALUES ('Awilda', %s, 0)"
        ),
        ("%s 10:00:00" % fe,),
    )
    tid = cur.lastrowid
    cur.execute(
        app._sql(
            """
            INSERT INTO ticket_lines (ticket_id, lottery, draw, number, play, amount, fecha_sorteo, pagado, premio_linea_pagada)
            VALUES (%s, %s, '', %s, 'Quiniela', %s, %s, 0, 0)
            """
        ),
        (tid, "La Primera 12:00 PM", "40", 100.0, fe),
    )
    lid = cur.lastrowid
    c.commit()

    sync = _recalc(app, cur, fe)
    assert sync.get("ok") is True
    assert int(sync.get("filas_cruce") or 0) >= 1
    assert int(sync.get("premios_creados") or 0) + int(sync.get("premios_actualizados") or 0) >= 1
    c.commit()

    n, total = _premios_linea(cur, app, fe, lid)
    assert n == 1
    assert total > 0

    lista_admin = app.premios_pendientes_fetch(cur, fe, cajero_username=None)
    assert any(int(x.get("line_id") or 0) == int(lid) for x in lista_admin)

    lista_cajero = app.premios_pendientes_fetch(cur, fe, cajero_username="Awilda")
    assert any(int(x.get("line_id") or 0) == int(lid) for x in lista_cajero)

    visibles = app._ganadores_lista_filas_visibles_fuente_principal(
        cur, fe, None, fe, lista_live_cached=None
    )
    assert any(int(x.get("line_id") or 0) == int(lid) for x in visibles)
    c.close()


def test_recalc_idempotente_lista_un_solo_premio(app_mod, monkeypatch):
    app = app_mod
    fe = FECHA
    _monkey_hoy(app, monkeypatch, fe)
    c = app.db()
    cur = c.cursor()
    app._premios_migrate_unique_constraints(cur)
    _seed_resultado_row(app, cur, LOTERY, DRAW, fe, "45", "70", "52")
    _, lid = _seed_ticket_line(app, cur, "45", 10.0, fecha_sorteo=fe)
    c.commit()

    _recalc(app, cur, fe)
    c.commit()
    _recalc(app, cur, fe)
    c.commit()

    n, _ = _premios_linea(cur, app, fe, lid)
    assert n == 1
    c.close()
