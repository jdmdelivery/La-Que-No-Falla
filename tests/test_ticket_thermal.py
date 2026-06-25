"""Ticket térmico 58mm — banca dominicana profesional."""
from __future__ import annotations

import base64

from ticket_thermal import (
    CHARS,
    TICKET_WIDTH_MM,
    generar_ticket,
    generar_ticket_escpos,
    render_ticket_html,
    ticket_escpos_b64,
)


def _sample_multi_lot():
    return {
        "fecha": "2026-06-10",
        "hora": "12:44 PM",
        "ticket": "1781109857789",
        "id": "43",
        "cajero": "Eli",
        "jugadas": [
            {"loteria": "La Anguila", "hora": "1:00 PM", "numero": "58", "monto": 25},
            {"loteria": "La Anguila", "hora": "1:00 PM", "numero": "85", "monto": 25},
            {"loteria": "Quiniela Real", "hora": "12:55 PM", "numero": "58", "monto": 25},
            {"loteria": "Quiniela Real", "hora": "12:55 PM", "numero": "85", "monto": 25},
        ],
    }


def test_ancho_58mm_y_separadores():
    assert TICKET_WIDTH_MM == 58
    assert CHARS == 32
    txt = generar_ticket(_sample_multi_lot())
    assert "-" * 32 in txt
    assert "JUGADA:" in txt


def test_estilo_banca_58mm():
    txt = generar_ticket(_sample_multi_lot())
    assert "LA QUE NUNCA FALLA" in txt
    assert "NO PAGAMOS SIN TICKET" in txt
    assert "Fecha: 2026-06-10 Hora: 12:44 PM" in txt
    assert "Ticket: 1781109857789 ID: 43" in txt
    assert "Cajero: Eli" in txt
    assert "La Anguila 1:00 PM" in txt
    assert "58  -  RD$25.00" in txt
    assert "Quiniela Real 12:55 PM" in txt
    assert "TOTAL RD$100.00" in txt
    assert "REVISA SU TICKET" in txt
    assert "BUENA SUERTE" in txt
    assert "ESCANEA PARA VERIFICAR" not in txt


def test_html_58mm_clases_sin_qr():
    html = render_ticket_html(_sample_multi_lot())
    assert 'class="header"' in html
    assert 'class="play-row"' in html
    assert 'class="play-number"' in html
    assert 'class="total"' in html
    assert 'class="footer"' in html
    assert "qr" not in html.lower()
    assert "58  -" in html
    assert html.rstrip().endswith("BUENA SUERTE</div>")


def test_escpos_58mm_sin_qr():
    data = _sample_multi_lot()
    raw = generar_ticket_escpos(data)
    assert raw.startswith(b"\x1b\x40")
    assert b"\x1b\x61\x01" in raw[:24]
    assert b"\x1b\x45\x01" in raw
    assert b"TOTAL RD$100.00" in raw
    assert b"BUENA SUERTE" in raw
    assert b"\x1d\x28\x6b" not in raw
    assert base64.b64decode(ticket_escpos_b64(data)) == raw
