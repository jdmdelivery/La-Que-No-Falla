"""Horarios globales: apertura 6:00 AM RD, cierre sorteo − 5 min."""
from __future__ import annotations

from datetime import datetime
import time

import pytest


def _mock_ahora(app, y, m, d, h, mi):
    naive = datetime(y, m, d, h, mi, 0)
    fixed = app.tz_rd.localize(naive)

    def _fake():
        return fixed

    return fixed, _fake


def test_cierre_cinco_minutos_antes_sorteo(app_mod, monkeypatch):
    monkeypatch.setenv("DEBUG_ALL_LOTTERIES_OPEN", "false")
    monkeypatch.setenv("CLOSE_BEFORE_DRAW_MINUTES", "5")
    app = app_mod
    _, fake = _mock_ahora(app, 2026, 6, 10, 8, 50)
    monkeypatch.setattr(app, "ahora_rd", fake)
    assert app.estado_loteria("La Anguila", "9:00 AM") == "abierta"
    assert app.loteria_disponible_para_venta("La Anguila", "9:00 AM") is True
    snap = app._horario_loteria_snapshot("La Anguila", "9:00 AM")
    assert snap["hora_cierre"] == "8:55 AM"

    _, fake2 = _mock_ahora(app, 2026, 6, 10, 8, 55)
    monkeypatch.setattr(app, "ahora_rd", fake2)
    assert app.estado_loteria("La Anguila", "9:00 AM") == "cerrada"
    assert app.loteria_cerrada_para_venta("La Anguila", "9:00 AM") is True


def test_apertura_global_seis_am(app_mod, monkeypatch):
    monkeypatch.setenv("DEBUG_ALL_LOTTERIES_OPEN", "false")
    app = app_mod
    _, fake = _mock_ahora(app, 2026, 6, 10, 5, 59)
    monkeypatch.setattr(app, "ahora_rd", fake)
    assert app.ventas_loterias_permiso_horario_global() is False
    assert app.estado_loteria("Quiniela Real", "12:55 PM") == "cerrada"

    _, fake2 = _mock_ahora(app, 2026, 6, 10, 6, 0)
    monkeypatch.setattr(app, "ahora_rd", fake2)
    assert app.ventas_loterias_permiso_horario_global() is True
    assert app.estado_loteria("Quiniela Real", "12:55 PM") == "abierta"


@pytest.mark.parametrize(
    "draw,h,mi,abierta",
    [
        ("1:00 PM", 12, 54, True),
        ("1:00 PM", 12, 55, False),
        ("2:30 PM", 14, 24, True),
        ("2:30 PM", 14, 25, False),
        ("6:00 PM", 17, 54, True),
        ("6:00 PM", 17, 55, False),
        ("9:00 PM", 20, 54, True),
        ("9:00 PM", 20, 55, False),
    ],
)
def test_ejemplos_cierre_usuario(app_mod, monkeypatch, draw, h, mi, abierta):
    monkeypatch.setenv("DEBUG_ALL_LOTTERIES_OPEN", "false")
    monkeypatch.setenv("CLOSE_BEFORE_DRAW_MINUTES", "5")
    app = app_mod
    _, fake = _mock_ahora(app, 2026, 6, 10, h, mi)
    monkeypatch.setattr(app, "ahora_rd", fake)
    assert app.estado_loteria("Test", draw) == ("abierta" if abierta else "cerrada")


def test_ui_texto_abierta_cerrada(app_mod, monkeypatch):
    monkeypatch.setenv("DEBUG_ALL_LOTTERIES_OPEN", "false")
    monkeypatch.setenv("FORCE_LOTERIAS_OPEN", "false")
    app = app_mod
    _, fake = _mock_ahora(app, 2026, 6, 10, 10, 0)
    monkeypatch.setattr(app, "ahora_rd", fake)
    ev = app.estado_venta_ui_loteria("La Anguila", "1:00 PM")
    assert ev["estado_venta_texto"] == app.TEXTO_LOTERIA_ABIERTA

    _, fake2 = _mock_ahora(app, 2026, 6, 10, 12, 55)
    monkeypatch.setattr(app, "ahora_rd", fake2)
    ev2 = app.estado_venta_ui_loteria("La Anguila", "1:00 PM")
    assert ev2["estado_venta_texto"] == app.TEXTO_LOTERIA_CERRADA
    assert "5 minutos antes" in (ev2.get("mensaje_cierre") or "")


def test_force_loterias_open_bypass_horario(app_mod, monkeypatch):
    monkeypatch.setenv("FORCE_LOTERIAS_OPEN", "true")
    monkeypatch.setenv("DEBUG_ALL_LOTTERIES_OPEN", "false")
    app = app_mod
    _, fake = _mock_ahora(app, 2026, 6, 10, 3, 0)
    monkeypatch.setattr(app, "ahora_rd", fake)
    assert app._force_loterias_open_enabled() is True
    assert app.ventas_loterias_permiso_horario_global() is True
    assert app.estado_loteria("Loteka", "7:55 PM") == "abierta"
    assert app.loteria_cerrada_para_venta("Loteka", "7:55 PM") is False
    ev = app.estado_venta_ui_loteria("Loteka", "7:55 PM")
    assert ev["estado"] == "abierta"
    assert ev["puede_vender"] is True
    assert ev["estado_venta_texto"] == app.TEXTO_LOTERIA_ABIERTA
    assert ev["permitir_venta"] is True
    assert ev["cerrada"] is False
    assert ev["abierta"] is True


def test_force_loterias_open_sin_sorteo_tambien_abierta(app_mod, monkeypatch):
    monkeypatch.setenv("FORCE_LOTERIAS_OPEN", "true")
    app = app_mod
    assert app.estado_loteria("Test", "") == "abierta"
    ev = app.estado_venta_ui_loteria("Test", "")
    assert ev["puede_vender"] is True
    assert ev["estado_venta_texto"] == app.TEXTO_LOTERIA_ABIERTA
    fila = app._fila_estado_loteria_dict("Test", "")
    assert fila["estado"] == "abierta"
    assert fila["cerrada"] is False
    assert fila["permitir_venta"] is True


def test_api_estado_loterias_force_open(client, app_mod, monkeypatch):
    monkeypatch.setenv("FORCE_LOTERIAS_OPEN", "true")
    with client.session_transaction() as sess:
        sess["u"] = "admin_test"
        sess["uid"] = 1
        sess["last_activity"] = time.time()
        sess["last_activity_touch"] = time.time()
    rv = client.get("/api/estado_loterias")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data.get("force_loterias_open") is True
    assert data.get("ventas_dia_abiertas") is True
    for row in data.get("loterias") or []:
        assert row.get("estado") == "abierta"
        assert row.get("puede_vender") is True
        assert row.get("permitir_venta") is True
        assert row.get("cerrada") is False
        assert row.get("abierta") is True
