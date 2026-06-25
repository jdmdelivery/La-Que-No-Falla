"""
Concurrencia: varias conexiones resuelven sorteos distintos sin mezclar triples (no hay caché global del resultado).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

FECHA = "2026-05-05"


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


def _resolve(app, lottery, draw):
    conn = app.db()
    try:
        cur = conn.cursor()
        return app._resultado_sorteo_resolver_estricto(cur, lottery, draw, FECHA)
    finally:
        conn.close()


def test_resolver_concurrent_distinct_sorteos(app_mod):
    app = app_mod
    c = app.db()
    cur = c.cursor()
    _seed_resultado_row(app, cur, "Loteka", "7:55 PM", FECHA, "01", "02", "03")
    _seed_resultado_row(app, cur, "Leidsa", "3:55 PM", FECHA, "10", "20", "30")
    c.commit()
    c.close()

    keys = [("Loteka", "7:55 PM"), ("Leidsa", "3:55 PM")] * 30
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda k: _resolve(app, k[0], k[1]), keys))

    for (lot, _dr), (trip, err, _info) in zip(keys, results):
        assert err is None and trip is not None
        if lot == "Loteka":
            assert trip == ("01", "02", "03")
        else:
            assert trip == ("10", "20", "30")
