"""
Regresión: falsos positivos de premios (sorteo estricto lotería + hora + fecha).

Caso Loteka 7:55 PM, 50 vs resultado oficial 45-70-52 → no premio.
"""
from __future__ import annotations

import logging

import pytest


FECHA = "2026-05-05"
LOTERY = "Loteka"
DRAW = "7:55 PM"


def _seed_loteka_resultado(app, cur, p1="45", p2="70", p3="52"):
    nl, nd, frd = app._resultados_norm_tuple_for_unique(LOTERY, DRAW, FECHA)
    assert nl and frd
    cur.execute(
        app._sql(
            """
            INSERT INTO resultados (lottery, draw, primero, segundo, tercero, fecha, confirmado, publicado, estado,
                normalized_lottery, normalized_draw, fecha_rd)
            VALUES (%s, %s, %s, %s, %s, %s, 1, 1, 'cerrado', %s, %s, %s)
            """
        ),
        (LOTERY, DRAW, p1, p2, p3, FECHA, nl, nd, frd),
    )


def _seed_resultado_row(app, cur, lottery, draw, fecha, p1, p2, p3):
    nl, nd, frd = app._resultados_norm_tuple_for_unique(lottery, draw, fecha)
    assert nl and frd
    cur.execute(
        app._sql(
            """
            INSERT INTO resultados (lottery, draw, primero, segundo, tercero, fecha, confirmado, publicado, estado,
                normalized_lottery, normalized_draw, fecha_rd)
            VALUES (%s, %s, %s, %s, %s, %s, 1, 1, 'cerrado', %s, %s, %s)
            """
        ),
        (lottery, draw, p1, p2, p3, fecha, nl, nd, frd),
    )


def _seed_ticket_line(
    app,
    cur,
    number="50",
    amount=10.0,
    *,
    created_at=None,
    fecha_sorteo=None,
    ticket_id=None,
    lottery=None,
    draw=None,
):
    """Crea ticket + línea, o sólo línea sobre ticket existente."""
    created_at = created_at or f"{FECHA} 10:00:00"
    fecha_sorteo = fecha_sorteo or FECHA
    lot = lottery if lottery is not None else LOTERY
    dr = draw if draw is not None else DRAW
    if ticket_id is None:
        cur.execute(
            app._sql(
                """
                INSERT INTO tickets (cajero, created_at, pagado)
                VALUES ('test', %s, 0)
                """
            ),
            (created_at,),
        )
        tid = cur.lastrowid
    else:
        tid = int(ticket_id)
    cur.execute(
        app._sql(
            """
            INSERT INTO ticket_lines (ticket_id, lottery, draw, number, play, amount, fecha_sorteo, pagado, premio_linea_pagada)
            VALUES (%s, %s, %s, %s, 'Quiniela', %s, %s, 0, 0)
            """
        ),
        (tid, lot, dr, number, amount, fecha_sorteo),
    )
    lid = cur.lastrowid
    return tid, lid


def test_quiniela_50_no_paga_con_resultado_45_70_52(app_mod, caplog):
    """Caso obligatorio: 50 no acierta; no lista ganador; no premio."""
    app = app_mod
    c = app.db()
    cur = c.cursor()
    _seed_loteka_resultado(app, cur)
    tid, lid = _seed_ticket_line(app, cur, "50")
    c.commit()

    assert not app._ganadores_numero_coincide_resultado("Quiniela", "50", "45", "70", "52")

    caplog.set_level(logging.INFO, logger="app")
    os_dbg = __import__("os").environ.get("DEBUG_VALIDACION_SORTEO")
    __import__("os").environ["DEBUG_VALIDACION_SORTEO"] = "1"
    try:
        join_rows = app._ganadores_fetch_lineas_vs_resultados(cur, FECHA)
        lista = app._ganadores_procesar_filas(
            join_rows, pagos=app.PAGOS, hoy_rd_str=FECHA, cur=cur
        )
    finally:
        if os_dbg is None:
            __import__("os").environ.pop("DEBUG_VALIDACION_SORTEO", None)
        else:
            __import__("os").environ["DEBUG_VALIDACION_SORTEO"] = os_dbg

    assert lista == []
    cur.execute(app._sql("SELECT COUNT(*) AS n FROM premios WHERE line_id = %s"), (lid,))
    row = cur.fetchone()
    n = row["n"] if hasattr(row, "keys") else row[0]
    assert int(n) == 0

    joined = "45-70-52" in caplog.text or "45-70-52" in "".join(
        getattr(r, "message", str(r)) for r in caplog.records
    )
    assert joined, "log [VALIDANDO] debería incluir resultado usado 45-70-52"


def test_otra_loteria_horario_no_contamina(app_mod):
    """50-49-59 en otra lotería / hora / fecha no se usa para Loteka 7:55."""
    app = app_mod
    c = app.db()
    cur = c.cursor()
    _seed_loteka_resultado(app, cur, "45", "70", "52")
    _seed_resultado_row(app, cur, "Leidsa", "3:55 PM", FECHA, "50", "49", "59")
    _seed_resultado_row(app, cur, LOTERY, DRAW, "2026-05-06", "50", "49", "59")
    _, lid = _seed_ticket_line(app, cur, "50")
    c.commit()

    triple, err, info = app._resultado_sorteo_resolver_estricto(cur, LOTERY, DRAW, FECHA)
    assert err is None and triple == ("45", "70", "52")
    assert info.get("triple_txt") == "45-70-52"

    join_rows = app._ganadores_fetch_lineas_vs_resultados(cur, FECHA)
    lista = app._ganadores_procesar_filas(
        join_rows, pagos=app.PAGOS, hoy_rd_str=FECHA, cur=cur
    )
    assert lista == []


def test_duplicado_sorteo_no_paga(app_mod, caplog):
    """Dos filas Loteka 7:55 el mismo día → duplicado_sorteo, sin premio."""
    app = app_mod
    c = app.db()
    cur = c.cursor()
    try:
        cur.execute("DROP INDEX IF EXISTS resultados_unique_norm")
    except Exception:
        pass
    _seed_loteka_resultado(app, cur, "45", "70", "52")
    _seed_loteka_resultado(app, cur, "45", "70", "52")
    _, lid = _seed_ticket_line(app, cur, "45")
    c.commit()

    triple, err, _ = app._resultado_sorteo_resolver_estricto(cur, LOTERY, DRAW, FECHA)
    assert triple is None and err == "duplicado_sorteo"

    caplog.set_level(logging.WARNING)
    join_rows = app._ganadores_fetch_lineas_vs_resultados(cur, FECHA)
    lista = app._ganadores_procesar_filas(
        join_rows, pagos=app.PAGOS, hoy_rd_str=FECHA, cur=cur
    )
    assert lista == []
    assert "duplicado" in caplog.text.lower() or "duplicado_sorteo" in caplog.text


def test_no_encontrado_sin_resultado(app_mod, caplog):
    """Sin fila en resultados para ese sorteo → no_encontrado."""
    app = app_mod
    c = app.db()
    cur = c.cursor()
    _seed_ticket_line(app, cur, "50")
    c.commit()

    triple, err, _ = app._resultado_sorteo_resolver_estricto(cur, LOTERY, DRAW, FECHA)
    assert triple is None and err == "no_encontrado"

    caplog.set_level(logging.WARNING)
    join_rows = app._ganadores_fetch_lineas_vs_resultados(cur, FECHA)
    assert join_rows == []
    lista = app._ganadores_procesar_filas(
        join_rows, pagos=app.PAGOS, hoy_rd_str=FECHA, cur=cur
    )
    assert lista == []


def test_join_triple_distinto_al_resolutor_descartado(app_mod, caplog):
    """JOIN devuelve números incorrectos; resolutor exige 45-70-52 → línea descartada."""
    app = app_mod
    c = app.db()
    cur = c.cursor()
    _seed_loteka_resultado(app, cur, "45", "70", "52")
    _, lid = _seed_ticket_line(app, cur, "50")
    c.commit()

    d0 = {
        "line_id": lid,
        "ticket_id": 1,
        "cajero": "test",
        "number": "50",
        "lottery": LOTERY,
        "draw": DRAW,
        "play": "Quiniela",
        "play_norm": "quiniela",
        "amount": 10.0,
        "primero": "50",
        "segundo": "49",
        "tercero": "59",
        "fecha_sorteo": FECHA,
        "ticket_fecha": f"{FECHA} 10:00:00",
        "resultado_fecha": FECHA,
        "res_lottery": LOTERY,
        "res_draw": DRAW,
        "res_publicado": 1,
        "res_estado": "cerrado",
        "ticket_pagado": 0,
        "linea_pagada": 0,
        "premio_linea_pagada": 0,
        "res_ganador_detectado_en": None,
    }
    caplog.set_level(logging.WARNING)
    lista = app._ganadores_procesar_filas(
        [d0], pagos=app.PAGOS, hoy_rd_str=FECHA, cur=cur
    )
    assert lista == []
    assert "JOIN" in caplog.text or "oficial" in caplog.text.lower()


def test_quiniela_45_si_paga_cuando_coincide(app_mod):
    """Sanidad: primer premio acierta."""
    app = app_mod
    c = app.db()
    cur = c.cursor()
    _seed_loteka_resultado(app, cur, "45", "70", "52")
    _, lid = _seed_ticket_line(app, cur, "45")
    c.commit()

    join_rows = app._ganadores_fetch_lineas_vs_resultados(cur, FECHA)
    lista = app._ganadores_procesar_filas(
        join_rows, pagos=app.PAGOS, hoy_rd_str=FECHA, cur=cur
    )
    assert len(lista) == 1
    assert float(lista[0].get("premio") or 0) > 0
    assert lista[0].get("line_id") == lid


def test_collect_context_sincroniza_faltantes_aun_si_hay_un_premio(app_mod, monkeypatch):
    """Con premios parciales en BD, GET /ganadores lee sin re-cruce; force=True completa faltantes."""
    app = app_mod
    monkeypatch.setenv("GANADORES_LISTA_LIMITE", "3")
    c = app.db()
    cur = c.cursor()
    _seed_loteka_resultado(app, cur, "45", "70", "52")
    for _ in range(4):
        _seed_ticket_line(app, cur, "45")
    c.commit()

    join_rows = app._ganadores_fetch_lineas_vs_resultados(cur, FECHA)
    lista = app._ganadores_procesar_filas(
        join_rows, pagos=app.PAGOS, hoy_rd_str=FECHA, cur=cur
    )
    assert len(lista) == 4

    # Simula estado parcial previo: solo 1 línea estaba persistida en `premios`.
    assert app._premios_upsert_pendiente(cur, lista[0]) is True
    c.commit()
    assert app._premios_count_ganadores_lineas_fecha(cur, FECHA) == 1
    assert app._premios_sync_necesario(cur, FECHA) is False

    with app.app.test_request_context("/ganadores?fecha_premios=%s" % FECHA):
        ctx = app._ganadores_collect_dashboard_context(
            c,
            cur,
            hoy=FECHA,
            cajero_filtro=None,
            vista_admin=True,
            mostrar_col_cajero=True,
            debug_ganadores=False,
            solo_pendientes=True,
        )
    assert int(ctx.get("total_ganadores") or 0) == 1

    sync = app._ganadores_sync_premios_fecha_lista(
        cur, FECHA, cajero_username=None, force=True
    )
    assert sync.get("ok")
    c.commit()
    with app.app.test_request_context("/ganadores?fecha_premios=%s" % FECHA):
        ctx = app._ganadores_collect_dashboard_context(
            c,
            cur,
            hoy=FECHA,
            cajero_filtro=None,
            vista_admin=True,
            mostrar_col_cajero=True,
            debug_ganadores=False,
            solo_pendientes=True,
        )

    total_lineas_listadas = sum(len(t.get("lineas") or []) for t in (ctx.get("lista_ganadores_por_ticket") or []))
    assert int(ctx.get("total_ganadores") or 0) == 4
    assert total_lineas_listadas == 4
    assert bool(ctx.get("ganadores_lista_truncada")) is False


def test_ganadores_lista_limite_no_permite_valores_muy_bajos(app_mod, monkeypatch):
    """Evita efecto de lista rotativa cuando env fija límites como 1-3."""
    app = app_mod
    monkeypatch.setenv("GANADORES_LISTA_LIMITE", "3")
    assert app._ganadores_lista_limite() >= 50


def test_venta_anticipada_no_se_descarta_por_created_at(app_mod):
    """Ticket vendido el día anterior con fecha_sorteo de hoy debe contar como ganador."""
    app = app_mod
    c = app.db()
    cur = c.cursor()
    _seed_loteka_resultado(app, cur, "45", "70", "52")
    _, lid = _seed_ticket_line(
        app,
        cur,
        "45",
        created_at="2026-05-04 23:55:00",
        fecha_sorteo=FECHA,
    )
    c.commit()

    join_rows = app._ganadores_fetch_lineas_vs_resultados(cur, FECHA)
    lista = app._ganadores_procesar_filas(
        join_rows, pagos=app.PAGOS, hoy_rd_str=FECHA, cur=cur
    )
    assert len(lista) == 1
    assert int(lista[0].get("line_id") or 0) == int(lid)


def test_lista_recupera_premio_cuando_integridad_fecha_filtra_filas(app_mod, monkeypatch):
    """
    `fecha_día` inconsistente con la línea cae fuera del JOIN de integridad, pero coincide el día por
    `fecha_sorteo` / columnas RD: `_ganadores_enriquecer_lista_desde_cruce_vivo` debe igual mostrarla.
    """
    app = app_mod
    monkeypatch.setattr(
        app,
        "_premios_sync_desde_cruce_hoy",
        lambda *a, **k: {"ok": True, "insertados": 0},
        raising=False,
    )
    c = app.db()
    cur = c.cursor()
    _seed_loteka_resultado(app, cur, "45", "70", "52")
    _, lid = _seed_ticket_line(app, cur, "45")
    c.commit()
    join_rows = app._ganadores_fetch_lineas_vs_resultados(cur, FECHA)
    lista_live = app._ganadores_procesar_filas(
        join_rows, pagos=app.PAGOS, hoy_rd_str=FECHA, cur=cur
    )
    assert len(lista_live) == 1
    assert app._premios_upsert_pendiente(cur, lista_live[0]) is True
    c.commit()

    cur.execute(
        app._sql("UPDATE premios SET fecha_dia = %s WHERE line_id = %s"),
        ("2099-01-01", lid),
    )
    c.commit()

    lf = app._premios_fetch_por_estado(
        cur,
        ["pendiente", "pagado"],
        limit=None,
        fecha_ref=FECHA,
    )
    assert len(lf) == 0

    with app.app.test_request_context("/ganadores?fecha_premios=%s" % FECHA):
        ctx = app._ganadores_collect_dashboard_context(
            c,
            cur,
            hoy=FECHA,
            cajero_filtro=None,
            vista_admin=True,
            mostrar_col_cajero=True,
            debug_ganadores=False,
        )

    nl = sum(len(t.get("lineas") or []) for t in (ctx.get("lista_ganadores_por_ticket") or []))
    assert nl >= 1
    assert int(ctx.get("total_ganadores") or 0) >= 1


def test_calcular_premio_quiniela_suma_varios_aciertos_misma_jugada(app_mod):
    """
    Una línea con varios números debe premiar cada acierto (1º/2º/3º), no solo el de mayor tabla.
    Caso típico: 78→1ero y 73→3ero sobre el mismo monto repetido por número en el mismo campo.
    """
    app = app_mod
    m1 = float(app.PAGOS["quiniela_1"])
    m3 = float(app.PAGOS["quiniela_3"])
    monto = 25.0
    esperado = monto * m1 + monto * m3
    p = float(app.calcular_premio("Quiniela", "78, 73", monto, "78", "52", "73") or 0)
    assert abs(p - esperado) < 0.02


def test_validar_pre_pago_usa_total_devengado_aunque_tabla_premios_incomplete(app_mod):
    """
    Pago debe igualar la suma del cruce (/ganadores), no quedarse en premios.persistido incompleto.
    """
    app = app_mod
    fe_ld = "2026-05-12"
    lot_ld = "Leidsa"
    drw_ld = "8:55 PM"
    c = app.db()
    cur = c.cursor()
    _seed_resultado_row(app, cur, lot_ld, drw_ld, fe_ld, "78", "52", "73")
    created_ld = "%s 08:10:00" % fe_ld
    cur.execute(
        app._sql("INSERT INTO tickets (cajero, created_at, pagado) VALUES ('test', %s, 0)"),
        (created_ld,),
    )
    tid_ld = cur.lastrowid
    cur.execute(
        app._sql(
            """
            INSERT INTO ticket_lines (ticket_id, lottery, draw, number, play, amount, fecha_sorteo, pagado, premio_linea_pagada)
            VALUES (%s, %s, %s, %s, 'Quiniela', %s, %s, 0, 0)
            """
        ),
        (tid_ld, lot_ld, drw_ld, "78, 73", 25.0, fe_ld),
    )
    lid_ld = cur.lastrowid
    c.commit()

    join_ld = app._ganadores_fetch_lineas_vs_resultados(cur, fe_ld, ticket_id=tid_ld)
    lista_ld = app._ganadores_procesar_filas(
        join_ld, pagos=app.PAGOS, hoy_rd_str=fe_ld, cur=cur
    )
    assert len(lista_ld) >= 1
    esperado_ld = sum(float(x.get("premio") or 0) for x in lista_ld)
    q1 = float(app.PAGOS["quiniela_1"])
    q3 = float(app.PAGOS["quiniela_3"])
    assert abs(esperado_ld - (25.0 * q1 + 25.0 * q3)) < 0.05
    assert all(x.get("acierto_ok") for x in lista_ld)
    disp0 = (lista_ld[0].get("numero_jugado_display") or "").replace(" ", "")
    assert "78" in disp0 or any("78" in (x.get("numero_jugado_display") or "") for x in lista_ld)

    for row in lista_ld:
        app._premios_upsert_pendiente(cur, row)
    c.commit()
    cur.execute(
        app._sql("UPDATE premios SET premio = %s WHERE line_id = %s"),
        (100.0, lid_ld),
    )
    c.commit()

    sum_db_bad = float(app._premio_pendiente_por_ticket(cur, tid_ld) or 0)
    assert abs(sum_db_bad - 200.0) < 0.05

    val_ld = app._validar_pre_pago_premio_ticket(cur, tid_ld, fe_ld)
    assert val_ld.get("ok") is True
    assert abs(float(val_ld.get("premio") or 0) - esperado_ld) < 0.05


def test_dashboard_resumen_total_recalcula_premios_stale(app_mod, monkeypatch):
    """Con sync explícito (?sync=1), las tarjetas pendiente reflejan premios corregidos."""
    app = app_mod
    monkeypatch.setenv("PREMIOS_DASHBOARD_SYNC_ON_LOAD", "1")
    fe_ld = "2026-05-14"
    lot_ld = "Leidsa"
    drw_ld = "8:55 PM"
    c = app.db()
    cur = c.cursor()
    _seed_resultado_row(app, cur, lot_ld, drw_ld, fe_ld, "78", "52", "73")
    cur.execute(
        app._sql("INSERT INTO tickets (cajero, created_at, pagado) VALUES ('test', %s, 0)"),
        ("%s 10:10:00" % fe_ld,),
    )
    tid_ld = cur.lastrowid
    cur.execute(
        app._sql(
            """
            INSERT INTO ticket_lines (ticket_id, lottery, draw, number, play, amount, fecha_sorteo, pagado, premio_linea_pagada)
            VALUES (%s, %s, %s, %s, 'Quiniela', %s, %s, 0, 0)
            """
        ),
        (tid_ld, lot_ld, drw_ld, "78, 73", 25.0, fe_ld),
    )
    lid_ld = cur.lastrowid
    c.commit()
    lista_ld = app._ganadores_procesar_filas(
        app._ganadores_fetch_lineas_vs_resultados(cur, fe_ld, ticket_id=tid_ld),
        pagos=app.PAGOS,
        hoy_rd_str=fe_ld,
        cur=cur,
    )
    esperado_ld = sum(float(x.get("premio") or 0) for x in lista_ld)
    for row in lista_ld:
        app._premios_upsert_pendiente(cur, row)
    c.commit()
    cur.execute(
        app._sql("UPDATE premios SET premio = %s WHERE line_id = %s"),
        (100.0, lid_ld),
    )
    c.commit()

    with app.app.test_request_context("/admin?sync=1"):
        dash = app._ganadores_pendientes_dashboard_resumen(cur, c, fe_ld)
    pt = float(dash.get("pendiente_total") or 0)
    ph = float(dash.get("pendiente_hoy") or 0)
    assert abs(pt - esperado_ld) < 0.07
    assert abs(ph - esperado_ld) < 0.07
    assert abs(float(app._premio_pendiente_por_ticket(cur, tid_ld) or 0) - esperado_ld) < 0.07


def test_quiniela_leidsa_dos_lineas_distintas_mismo_ticket_ambas_listadas(app_mod):
    """Dos ticket_lines separadas que aciertan cada una; deben producir dos filas en el cruce (ej. reporte usuario 73+78)."""
    app = app_mod
    fe_ld = "2026-05-12"
    lot_ld = "Leidsa"
    drw_ld = "8:55 PM"
    c = app.db()
    cur = c.cursor()
    # 73 en tercero -> 25*quiniela_3 ; 78 en segundo -> 25*quiniela_2
    _seed_resultado_row(app, cur, lot_ld, drw_ld, fe_ld, "05", "78", "73")
    tid, lid73 = _seed_ticket_line(app, cur, "73", 25.0, fecha_sorteo=fe_ld, lottery=lot_ld, draw=drw_ld)
    _, lid78 = _seed_ticket_line(
        app, cur, "78", 25.0, fecha_sorteo=fe_ld, lottery=lot_ld, draw=drw_ld, ticket_id=tid
    )
    c.commit()

    lista = app._ganadores_procesar_filas(
        app._ganadores_fetch_lineas_vs_resultados(cur, fe_ld),
        pagos=app.PAGOS,
        hoy_rd_str=fe_ld,
        cur=cur,
    )
    por_lid = {int(x["line_id"]): x for x in lista}
    assert lid73 in por_lid and lid78 in por_lid
    assert len(lista) == 2

    q2 = float(app.PAGOS["quiniela_2"])
    q3 = float(app.PAGOS["quiniela_3"])
    assert abs(float(por_lid[lid73]["premio"] or 0) - 25.0 * q3) < 0.05
    assert abs(float(por_lid[lid78]["premio"] or 0) - 25.0 * q2) < 0.05

    pres73 = app._ganadores_acierto_presentacion(
        "Quiniela", "73", "05", "78", "73", por_lid[lid73]["premio"], pagos=app.PAGOS
    )
    pres78 = app._ganadores_acierto_presentacion(
        "Quiniela", "78", "05", "78", "73", por_lid[lid78]["premio"], pagos=app.PAGOS
    )
    assert pres73["acierto_ok"]
    assert pres78["acierto_ok"]


def test_collect_ganadores_lista_llena_cuando_hay_ganadores_cruce(app_mod, monkeypatch):
    """Regresión: lista no puede quedar vacía si el cruce detecta líneas ganadoras (sync día + enrich)."""
    app = app_mod
    from datetime import datetime

    try:
        import pytz
    except ImportError:
        pytest.skip("pytz requerido")
    fe_ld = "2026-05-12"
    tz = pytz.timezone("America/Santo_Domingo")
    monkeypatch.setattr(
        app,
        "ahora_rd",
        lambda: tz.localize(datetime(2026, 5, 12, 18, 0, 0)),
    )
    lot_ld = "Leidsa"
    drw_ld = "8:55 PM"
    c = app.db()
    cur = c.cursor()
    _seed_resultado_row(app, cur, lot_ld, drw_ld, fe_ld, "05", "78", "73")
    tid, _lid73 = _seed_ticket_line(app, cur, "73", 25.0, fecha_sorteo=fe_ld, lottery=lot_ld, draw=drw_ld)
    _, _lid78 = _seed_ticket_line(
        app, cur, "78", 25.0, fecha_sorteo=fe_ld, lottery=lot_ld, draw=drw_ld, ticket_id=tid
    )
    c.commit()

    hoy_str = app.ahora_rd().strftime("%Y-%m-%d")
    assert hoy_str == fe_ld

    sync = app._ganadores_sync_premios_fecha_lista(cur, fe_ld, cajero_username=None)
    assert sync.get("ok")
    assert not sync.get("skipped"), sync
    assert int(sync.get("insertados") or 0) >= 2, sync
    c.commit()
    with app.app.test_request_context("/ganadores?fecha_premios=%s" % fe_ld):
        ctx = app._ganadores_collect_dashboard_context(
            c,
            cur,
            hoy=hoy_str,
            cajero_filtro=None,
            vista_admin=True,
            mostrar_col_cajero=True,
            debug_ganadores=False,
            solo_pendientes=True,
        )
    lista = ctx.get("lista_ganadores") or []
    assert len(lista) >= 2
    por_ticket = ctx.get("lista_ganadores_por_ticket") or []
    assert len(por_ticket) >= 1
    cur.execute(app._sql("SELECT COUNT(*) AS n FROM premios WHERE ticket_id = %s AND estado = 'pendiente'"), (tid,))
    row = cur.fetchone()
    n = row["n"] if hasattr(row, "keys") else row[0]
    assert int(n) >= 2


def test_pendiente_ayer_sigue_visible_tras_cambio_dia(app_mod, monkeypatch):
    """
    Un premio pendiente de ayer debe seguir en la lista al abrir /ganadores «hoy»
    y desaparecer solo tras marcarlo pagado.
    """
    app = app_mod
    from datetime import datetime

    try:
        import pytz
    except ImportError:
        pytest.skip("pytz requerido")

    fe_ayer = "2026-05-11"
    fe_hoy = "2026-05-12"
    tz = pytz.timezone("America/Santo_Domingo")
    monkeypatch.setattr(
        app,
        "ahora_rd",
        lambda: tz.localize(datetime(2026, 5, 12, 9, 0, 0)),
    )
    monkeypatch.setattr(
        app,
        "_premios_quick_sync_day",
        lambda *a, **k: {"ok": True, "insertados": 0, "lista_cruce_ganadores": []},
        raising=False,
    )
    monkeypatch.setattr(
        app,
        "_premios_sync_desde_cruce_hoy",
        lambda *a, **k: {"ok": True, "insertados": 0, "lista_cruce_ganadores": []},
        raising=False,
    )

    c = app.db()
    cur = c.cursor()
    _seed_resultado_row(app, cur, LOTERY, DRAW, fe_ayer, "45", "70", "52")
    _, lid = _seed_ticket_line(app, cur, "45", fecha_sorteo=fe_ayer)
    join_rows = app._ganadores_fetch_lineas_vs_resultados(cur, fe_ayer)
    lista = app._ganadores_procesar_filas(
        join_rows, pagos=app.PAGOS, hoy_rd_str=fe_ayer, cur=cur
    )
    assert len(lista) == 1
    assert app._premios_upsert_pendiente(cur, lista[0]) is True
    c.commit()

    with app.app.test_request_context("/ganadores?fecha_premios=%s" % fe_ayer):
        ctx = app._ganadores_collect_dashboard_context(
            c,
            cur,
            hoy=fe_hoy,
            cajero_filtro=None,
            vista_admin=True,
            mostrar_col_cajero=True,
            debug_ganadores=False,
        )
    lids_vis = {
        int(x.get("line_id") or 0)
        for x in (ctx.get("lista_ganadores") or [])
        if float(x.get("premio") or 0) > 0.004
    }
    assert int(lid) in lids_vis

    dash = app._ganadores_pendientes_dashboard_resumen(cur, c, fe_hoy)
    assert float(dash.get("pendiente_total") or 0) >= float(lista[0].get("premio") or 0) - 0.05

    cur.execute(
        app._sql("UPDATE premios SET estado = 'pagado', fecha_pago = datetime('now') WHERE line_id = %s"),
        (lid,),
    )
    c.commit()

    with app.app.test_request_context("/ganadores?fecha_premios=%s" % fe_ayer):
        ctx2 = app._ganadores_collect_dashboard_context(
            c,
            cur,
            hoy=fe_hoy,
            cajero_filtro=None,
            vista_admin=True,
            mostrar_col_cajero=True,
            debug_ganadores=False,
        )
    lids_despues = {
        int(x.get("line_id") or 0)
        for x in (ctx2.get("lista_ganadores") or [])
        if str(x.get("estado") or "").strip().lower() == "pendiente"
    }
    assert int(lid) not in lids_despues


def test_collect_solo_pendientes_muestra_tres_tickets_ganadores_sin_sync_previo(app_mod, monkeypatch):
    """
    Tres tickets ganadores: lectura rápida muestra solo premios ya en BD;
    sync force=True materializa el resto (como POST recalcular).
    """
    """
    Regresión: evaluación cuenta 3 ganadores (3 tickets) pero /ganadores solo mostraba 2
  si faltaba fila en `premios` — el collect debe sincronizar y materializar el faltante.
    """
    app = app_mod
    from datetime import datetime

    try:
        import pytz
    except ImportError:
        pytest.skip("pytz requerido")

    fe = "2026-05-28"
    lot = "Loteria Nacional"
    drw = "2:30 PM"
    tz = pytz.timezone("America/Santo_Domingo")
    monkeypatch.setattr(
        app,
        "ahora_rd",
        lambda: tz.localize(datetime(2026, 5, 28, 16, 0, 0)),
    )
    c = app.db()
    cur = c.cursor()
    # 41 en tercer premio (mismo caso que ticket #2 del reporte)
    _seed_resultado_row(app, cur, lot, drw, fe, "10", "20", "41")
    _seed_ticket_line(app, cur, "41", 10.0, fecha_sorteo=fe, lottery=lot, draw=drw)
    _seed_ticket_line(app, cur, "41", 10.0, fecha_sorteo=fe, lottery=lot, draw=drw)
    _seed_ticket_line(app, cur, "41", 10.0, fecha_sorteo=fe, lottery=lot, draw=drw)
    c.commit()

    join_rows = app._ganadores_fetch_lineas_vs_resultados(cur, fe)
    lista = app._ganadores_procesar_filas(
        join_rows, pagos=app.PAGOS, hoy_rd_str=fe, cur=cur
    )
    tids = {int(x.get("ticket_id") or 0) for x in lista}
    assert len(tids) == 3

    # Solo 1 premio persistido (estado parcial como en producción)
    assert app._premios_upsert_pendiente(cur, lista[0]) is True
    c.commit()

    with app.app.test_request_context("/ganadores?fecha_premios=%s" % fe):
        ctx = app._ganadores_collect_dashboard_context(
            c,
            cur,
            hoy=fe,
            cajero_filtro=None,
            vista_admin=True,
            mostrar_col_cajero=True,
            debug_ganadores=False,
            solo_pendientes=True,
        )
    assert int(ctx.get("total_ganadores") or 0) == 1

    sync = app._ganadores_sync_premios_fecha_lista(cur, fe, cajero_username=None, force=True)
    assert sync.get("ok")
    c.commit()

    with app.app.test_request_context("/ganadores?fecha_premios=%s" % fe):
        ctx = app._ganadores_collect_dashboard_context(
            c,
            cur,
            hoy=fe,
            cajero_filtro=None,
            vista_admin=True,
            mostrar_col_cajero=True,
            debug_ganadores=False,
            solo_pendientes=True,
        )
    c.commit()
    tickets_visibles = {
        int(t.get("ticket_id") or 0) for t in (ctx.get("lista_ganadores_por_ticket") or [])
    }
    assert len(tickets_visibles) == 3
    assert int(ctx.get("total_ganadores") or 0) == 3


def test_tres_tickets_escenario_usuario_nacional_duplicado_y_primera(app_mod, monkeypatch):
    """
    Caso real 2026-05-28: Nacional 26-08-41 (tickets 2 y 3 con 41) + La Primera 42 (ticket 1).
    Dos tickets con el mismo número en la misma lotería deben verse como 3 tarjetas.
    """
    app = app_mod
    from datetime import datetime

    try:
        import pytz
    except ImportError:
        pytest.skip("pytz requerido")

    fe = "2026-05-28"
    tz = pytz.timezone("America/Santo_Domingo")
    monkeypatch.setattr(
        app,
        "ahora_rd",
        lambda: tz.localize(datetime(2026, 5, 28, 20, 0, 0)),
    )
    c = app.db()
    cur = c.cursor()
    _seed_resultado_row(app, cur, "Loteria Nacional", "2:30 PM", fe, "26", "08", "41")
    _seed_resultado_row(app, cur, "La Primera", "7:00 PM", fe, "61", "85", "42")
    tid1, _ = _seed_ticket_line(
        app, cur, "42", 10.0, fecha_sorteo=fe, lottery="La Primera", draw="7:00 PM"
    )
    tid2, _ = _seed_ticket_line(
        app, cur, "41", 10.0, fecha_sorteo=fe, lottery="Loteria Nacional", draw="2:30 PM"
    )
    tid3, _ = _seed_ticket_line(
        app, cur, "41", 10.0, fecha_sorteo=fe, lottery="Loteria Nacional", draw="2:30 PM"
    )
    c.commit()

    lista = app._ganadores_lista_pendientes_fecha_alineada(cur, fe, cajero_filtro=None)
    c.commit()
    tids = {int(x.get("ticket_id") or 0) for x in lista}
    assert tids == {tid1, tid2, tid3}
    assert len(lista) == 3

    with app.app.test_request_context("/ganadores?fecha_premios=%s" % fe):
        ctx = app._ganadores_collect_dashboard_context(
            c,
            cur,
            hoy=fe,
            cajero_filtro=None,
            vista_admin=True,
            mostrar_col_cajero=True,
            debug_ganadores=False,
            solo_pendientes=True,
        )
    por_ticket = {int(t["ticket_id"]): t for t in (ctx.get("lista_ganadores_por_ticket") or [])}
    assert set(por_ticket.keys()) == {tid1, tid2, tid3}
    assert int(ctx.get("total_ganadores") or 0) == 3
    assert abs(float(ctx.get("total_pagar") or 0) - 120.0) < 0.05


def test_recalcular_ganadores_fecha_completo_tres_premios(app_mod, monkeypatch):
    """POST recalcular: 3 ganadores persistidos y visibles tras commit."""
    app = app_mod
    from datetime import datetime

    try:
        import pytz
    except ImportError:
        pytest.skip("pytz requerido")

    fe = "2026-05-28"
    tz = pytz.timezone("America/Santo_Domingo")
    monkeypatch.setattr(
        app,
        "ahora_rd",
        lambda: tz.localize(datetime(2026, 5, 28, 20, 0, 0)),
    )
    c = app.db()
    cur = c.cursor()
    _seed_resultado_row(app, cur, "Loteria Nacional", "2:30 PM", fe, "26", "08", "41")
    _seed_resultado_row(app, cur, "La Primera", "7:00 PM", fe, "61", "85", "42")
    tid1, _ = _seed_ticket_line(
        app, cur, "42", 10.0, fecha_sorteo=fe, lottery="La Primera", draw="7:00 PM"
    )
    tid2, _ = _seed_ticket_line(
        app, cur, "41", 10.0, fecha_sorteo=fe, lottery="Loteria Nacional", draw="2:30 PM"
    )
    tid3, _ = _seed_ticket_line(
        app, cur, "41", 10.0, fecha_sorteo=fe, lottery="Loteria Nacional", draw="2:30 PM"
    )
    c.commit()

    sync = app._recalcular_ganadores_fecha_completo(cur, fe, cajero_username=None)
    assert sync.get("ok") is True
    assert int(sync.get("filas_cruce") or 0) == 3
    assert int(sync.get("premios_total") or 0) == 3
    c.commit()

    lista = app.premios_pendientes_fetch(cur, fe, limit=None)
    tids = {int(x.get("ticket_id") or 0) for x in lista}
    assert tids == {tid1, tid2, tid3}


def test_recalcular_idempotente_doble_click_sin_error(app_mod, monkeypatch):
    """Recalcular 2 veces seguidas no debe lanzar duplicate key ni perder ganadores."""
    app = app_mod
    from datetime import datetime

    try:
        import pytz
    except ImportError:
        pytest.skip("pytz requerido")

    fe = "2026-05-28"
    tz = pytz.timezone("America/Santo_Domingo")
    monkeypatch.setattr(
        app,
        "ahora_rd",
        lambda: tz.localize(datetime(2026, 5, 28, 20, 0, 0)),
    )
    c = app.db()
    cur = c.cursor()
    app._premios_migrate_unique_constraints(cur)
    _seed_resultado_row(app, cur, "Loteria Nacional", "2:30 PM", fe, "26", "08", "41")
    _seed_resultado_row(app, cur, "La Primera", "7:00 PM", fe, "61", "85", "42")
    _seed_ticket_line(
        app, cur, "42", 10.0, fecha_sorteo=fe, lottery="La Primera", draw="7:00 PM"
    )
    _seed_ticket_line(
        app, cur, "41", 10.0, fecha_sorteo=fe, lottery="Loteria Nacional", draw="2:30 PM"
    )
    _seed_ticket_line(
        app, cur, "41", 10.0, fecha_sorteo=fe, lottery="Loteria Nacional", draw="2:30 PM"
    )
    c.commit()

    s1 = app._recalcular_ganadores_fecha_completo(cur, fe)
    c.commit()
    assert s1.get("ok") is True
    assert int(s1.get("filas_cruce") or 0) == 3

    s2 = app._recalcular_ganadores_fecha_completo(cur, fe)
    c.commit()
    assert s2.get("ok") is True
    assert int(s2.get("premios_total") or 0) == 3
    assert int(s2.get("filas_cruce") or 0) == 3


def test_upsert_premio_pagado_no_duplica_fila(app_mod):
    """Si ya hay premio pagado para la línea, upsert pendiente no inserta duplicado."""
    app = app_mod
    c = app.db()
    cur = c.cursor()
    app._premios_migrate_unique_constraints(cur)
    fe = "2026-05-28"
    tid, lid = _seed_ticket_line(
        app, cur, "41", 10.0, fecha_sorteo=fe, lottery="Loteria Nacional", draw="2:30 PM"
    )
    norm = app._premios_normalize_business_fields(
        {
            "ticket_id": tid,
            "line_id": lid,
            "number": "41",
            "lottery": "Loteria Nacional",
            "draw": "2:30 PM",
            "premio_shard": "0",
        },
        fe,
        fe,
        fe,
    )
    cur.execute(
        app._sql(
            """
            INSERT INTO premios (
                ticket_id, line_id, numero, monto, premio, lottery, draw, play, resultado,
                fecha_sorteo, fecha_resultado, fecha_dia, cajero, premio_shard, estado
            )
            VALUES (%s, %s, %s, 10, 40, %s, %s, 'quiniela', '26-08-41', %s, %s, %s, 'test', %s, 'pagado')
            """
        ),
        (
            tid,
            lid,
            norm["numero"],
            norm["lottery"],
            norm["draw"],
            fe,
            norm["fecha_resultado"],
            fe,
            norm["premio_shard"],
        ),
    )
    c.commit()
    g = {
        "ticket_id": tid,
        "line_id": lid,
        "number": "41",
        "monto": 10.0,
        "premio": 40.0,
        "lottery": "Loteria Nacional",
        "draw": "2:30 PM",
        "play": "quiniela",
        "resultado": "26-08-41",
        "fecha_sorteo_linea": fe,
        "resultado_fecha_iso": fe,
        "cajero": "test",
        "premio_shard": "0",
    }
    ok = app._premios_upsert_pendiente(cur, g)
    c.commit()
    assert ok is False
    cur.execute(
        app._sql(
            "SELECT COUNT(*) AS c FROM premios WHERE line_id = %s AND lower(trim(estado)) = 'pagado'"
        ),
        (lid,),
    )
    row = cur.fetchone()
    n = int(row["c"] if hasattr(row, "__getitem__") and "c" in row.keys() else row[0])
    assert n == 1


def test_la_primera_12pm_quiniela_40_tercer_premio_ticket_526(app_mod, monkeypatch):
    """
    Ticket 526: La Primera 12:00 PM, número 40 RD$100.
    Resultado 00-18-40 → quiniela gana en 3er premio.
    """
    app = app_mod
    from datetime import datetime

    try:
        import pytz
    except ImportError:
        pytest.skip("pytz requerido")

    fe = "2026-06-17"
    tz = pytz.timezone("America/Santo_Domingo")
    monkeypatch.setattr(
        app,
        "ahora_rd",
        lambda: tz.localize(datetime(2026, 6, 17, 14, 0, 0)),
    )
    c = app.db()
    cur = c.cursor()
    app._premios_migrate_unique_constraints(cur)
    _seed_resultado_row(app, cur, "La Primera", "12:00 PM", fe, "00", "18", "40")

    tid, _ = _seed_ticket_line(
        app, cur, "09", 100.0, fecha_sorteo=fe, lottery="La Primera", draw="12:00 PM"
    )
    for num in ("14", "31", "55"):
        _seed_ticket_line(
            app, cur, num, 100.0, fecha_sorteo=fe, lottery="La Primera", draw="12:00 PM", ticket_id=tid
        )
    _, lid_40 = _seed_ticket_line(
        app, cur, "40", 100.0, fecha_sorteo=fe, lottery="La Primera", draw="12:00 PM", ticket_id=tid
    )
    c.commit()

    triple, err, _ = app._resultado_sorteo_resolver_estricto(cur, "La Primera", "12:00 PM", fe)
    assert err is None and triple == ("00", "18", "40")

    premio_40 = float(
        app.calcular_premio("Quiniela", "40", 100.0, "00", "18", "40", pagos=app.PAGOS) or 0
    )
    assert premio_40 > 0

    sync = app._recalcular_ganadores_fecha_completo(cur, fe, cajero_username=None)
    assert sync.get("ok") is True
    assert int(sync.get("filas_cruce") or 0) >= 1
    c.commit()

    lista = app.premios_pendientes_fetch(cur, fe, limit=None)
    ganadores_40 = [
        g
        for g in lista
        if int(g.get("ticket_id") or 0) == int(tid)
        and int(g.get("line_id") or 0) == int(lid_40)
    ]
    assert len(ganadores_40) == 1
    assert float(ganadores_40[0].get("premio") or 0) > 0

    join_rows = app._ganadores_fetch_lineas_vs_resultados(cur, fe)
    linea_40 = [r for r in join_rows if int(r.get("line_id") or 0) == int(lid_40)]
    assert len(linea_40) == 1
    assert app._norm_sorteo_dos_digitos(linea_40[0].get("tercero")) == "40"

