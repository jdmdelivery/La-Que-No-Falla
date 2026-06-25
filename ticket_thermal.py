# -*- coding: utf-8 -*-
"""
Ticket térmico 58mm — banca dominicana: centrado, grande, profesional.
HTML + CSS impresión, texto plano y ESC/POS (RawBT / Sunmi / Bluetooth / Android).
"""
from __future__ import annotations

import base64
import html
import os
import re
import unicodedata
from collections import defaultdict
from enum import Enum
from typing import Dict, List, Optional, Tuple

TICKET_WIDTH_MM = 58
CHARS = 32


class _LineKind(str, Enum):
    HEADER = "header"
    META = "meta"
    SEP = "sep"
    JUGADA = "jugada"
    LOTERIA = "loteria"
    PLAY = "play"
    TOTAL = "total"
    FOOTER = "footer"
    BLANK = "blank"


def _cp437(text: str) -> bytes:
    return str(text or "").encode("cp437", "replace")


def _money(value) -> str:
    try:
        return "{:.2f}".format(float(value or 0))
    except (TypeError, ValueError):
        return "0.00"


def _clip(text: str, width: int = CHARS) -> str:
    return str(text or "")[:width]


def _center(text: str, width: int = CHARS) -> str:
    return _clip(text, width).center(width)


def _sep(width: int = CHARS) -> str:
    return "-" * width


def _hora_display(raw: str) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    if re.search(r"(AM|PM)", s, re.I):
        m = re.search(r"(\d{1,2}:\d{2}\s*(?:AM|PM))", s, re.I)
        if m:
            parts = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)", m.group(1), re.I)
            if parts:
                h12 = int(parts.group(1)) % 12 or 12
                return "%d:%02d %s" % (h12, int(parts.group(2)), parts.group(3).upper())
            return m.group(1).upper()
        return s.upper()
    m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?", s)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        ap = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        return "%d:%02d %s" % (h12, mi, ap)
    return s


def _draw_display(hora: str) -> str:
    s = str(hora or "").strip()
    if s.lower().startswith("domingos "):
        s = s[9:].strip()
    return _hora_display(s) or s


def _lot_sorteo_line(loteria: str, hora: str) -> str:
    lot = str(loteria or "").strip()
    draw = _draw_display(hora)
    if lot and draw:
        return "%s %s" % (lot, draw)
    return lot or draw


def _numero_sort_key(numero: str):
    partes = re.split(r"[-\s]+", str(numero or "").strip())
    out = []
    for p in partes:
        try:
            out.append((0, int(p)))
        except ValueError:
            out.append((1, p))
    return tuple(out)


def _jugada_linea(numero: str, monto) -> str:
    """58  -  RD$25.00 centrado en 58mm."""
    n = str(numero or "").strip()
    amt = "RD$%s" % _money(monto)
    return _center("%s  -  %s" % (n, amt))


def _play_abbr(play: str, numero: str) -> str:
    raw = str(play or "").strip()
    key = "".join(
        c for c in unicodedata.normalize("NFD", raw.lower()) if unicodedata.category(c) != "Mn"
    )
    key = " ".join(key.split())
    if "super pale" in key:
        return "SP"
    if "tripleta" in key:
        return "TP"
    if key == "pale":
        return "PL"
    if "quiniela" in key:
        return "Q"

    # Fallback por formato del numero cuando play no venga normalizado.
    n = str(numero or "").strip()
    guiones = n.count("-")
    if guiones >= 2:
        return "TP"
    if guiones == 1:
        return "PL"
    return "Q"


def _norm_lottery_key(name: str) -> str:
    raw = str(name or "").strip().lower()
    key = "".join(c for c in unicodedata.normalize("NFD", raw) if unicodedata.category(c) != "Mn")
    key = re.sub(r"[^a-z0-9]+", " ", key)
    key = " ".join(key.split())
    return key


LOTTERY_ABBR = {
    "loteria nacional": "LN",
    "nacional": "LN",
    "new york": "NY",
    "florida": "FL",
    "king lottery": "KL",
    "la anguila": "LA",
    "anguila": "LA",
    "la primera": "LP",
    "la suerte dominicana": "LSD",
    "la suerte": "LSD",
    "leidsa": "LEI",
    "loteka": "LTK",
    "lotedom": "LTD",
    "real": "REAL",
    "georgia": "GA",
}


def _lot_abbr(name: str) -> str:
    n = _norm_lottery_key(name)
    if not n:
        return "-"
    if n in LOTTERY_ABBR:
        return LOTTERY_ABBR[n]
    for k, v in LOTTERY_ABBR.items():
        if n == k or n in k or k in n:
            return v
    words = [w for w in n.split(" ") if w]
    if not words:
        return "-"
    if len(words) == 1:
        return words[0][:4].upper()
    return "".join(w[:1].upper() for w in words[:3])


def _infer_lottery_pair_from_text(text: str) -> Tuple[str, str]:
    raw = str(text or "").strip()
    if not raw:
        return "", ""
    if "/" in raw:
        parts = [p.strip() for p in raw.split("/") if p.strip()]
        if len(parts) >= 2:
            return parts[0], parts[1]
    if " - " in raw:
        parts = [p.strip() for p in raw.split(" - ") if p.strip()]
        if len(parts) >= 2:
            return parts[0], parts[1]
    if " y " in raw.lower():
        parts = re.split(r"\s+y\s+", raw, maxsplit=1, flags=re.I)
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) >= 2:
            return parts[0], parts[1]

    raw_key = _norm_lottery_key(raw)
    found = []
    for k in LOTTERY_ABBR.keys():
        if k and k in raw_key:
            found.append(k)
    found = list(dict.fromkeys(found))
    if len(found) >= 2:
        return found[0], found[1]
    return raw, ""


def _lottery_compact(play: str, lottery1: str, lottery2: str = "") -> str:
    t = _play_abbr(play, "")
    l1 = str(lottery1 or "").strip()
    l2 = str(lottery2 or "").strip()
    if t == "SP":
        if not l1 and not l2:
            return "-"
        if not l2:
            i1, i2 = _infer_lottery_pair_from_text(l1)
            l1, l2 = i1 or l1, i2 or l2
        a1 = _lot_abbr(l1)
        a2 = _lot_abbr(l2) if l2 else ""
        return ("%s/%s" % (a1, a2)) if a2 else a1
    return _lot_abbr(l1)


def _filas_jugadas_ticket(jugadas: List[dict]) -> Tuple[List[dict], float]:
    filas: List[dict] = []
    total = 0.0
    for j in jugadas or []:
        numero = str(j.get("numeros") or j.get("numero") or j.get("number") or "").strip()
        loteria = str(j.get("loteria") or j.get("lottery") or "").strip()
        loteria2 = str(j.get("loteria2") or j.get("lottery2") or "").strip()
        play = str(j.get("tipo") or j.get("play") or "").strip()
        tipo_abbr = _play_abbr(play, numero)
        try:
            monto = float(j.get("monto") or j.get("amount") or 0)
        except (TypeError, ValueError):
            monto = 0.0
        total += monto
        filas.append(
            {
                "tipo_abbr": tipo_abbr,
                "numero": numero,
                "loteria": _lottery_compact(play, loteria, loteria2),
                "monto": monto,
            }
        )
    return filas, total


def _tabla_header_line() -> str:
    # 32 columnas: 4 + 1 + 8 + 1 + 10 + 8
    return "{:<4} {:<8} {:<10}{:>8}".format("Tipo", "Número", "Lotería", "Valor")


def _tabla_filas_lines(tipo_abbr: str, numero: str, loteria: str, monto) -> List[str]:
    tipo = str(tipo_abbr or "")[:4].upper()
    num = str(numero or "").strip()[:8]
    lot = str(loteria or "").strip() or "-"
    val = ("RD$%s" % _money(monto))[:8]
    out: List[str] = []
    lot_parts = [lot[i : i + 10] for i in range(0, len(lot), 10)] or [""]
    out.append("{:<4} {:<8} {:<10}{:>8}".format(tipo, num, lot_parts[0], val))
    for part in lot_parts[1:]:
        out.append("{:<4} {:<8} {:<10}{:>8}".format("", "", part, ""))
    return out


def _total_line(total) -> str:
    val = "RD$%s" % _money(total)
    return "TOTAL: %s" % val


def _agrupar_por_loteria(jugadas: List[dict]) -> Tuple[List[dict], float]:
    tree: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    total = 0.0
    for j in jugadas or []:
        lot = str(j.get("loteria") or j.get("lottery") or "").strip()
        hora = str(j.get("hora") or j.get("draw") or "").strip()
        num = str(j.get("numeros") or j.get("numero") or j.get("number") or "").strip()
        try:
            monto = float(j.get("monto") or j.get("amount") or 0)
        except (TypeError, ValueError):
            monto = 0.0
        total += monto
        tree[(lot, hora)].append({"numero": num, "monto": monto})

    bloques: List[dict] = []
    for key in sorted(tree.keys(), key=lambda k: (k[0].lower(), k[1])):
        filas = sorted(tree[key], key=lambda x: _numero_sort_key(x.get("numero")))
        bloques.append({"encabezado": _lot_sorteo_line(key[0], key[1]), "filas": filas})
    return bloques, total


def _lineas_ticket_estructurado(data: dict) -> Tuple[List[Tuple[str, _LineKind]], float]:
    filas, total = _filas_jugadas_ticket(data.get("jugadas") or [])
    out: List[Tuple[str, _LineKind]] = []

    out.append((_sep(), _LineKind.SEP))
    out.append((_center("VENTA DE LOTERÍA"), _LineKind.HEADER))
    out.append((_sep(), _LineKind.SEP))

    fecha = str(data.get("fecha") or "").strip()
    hora = _hora_display(data.get("hora") or data.get("hora_venta") or "")
    if fecha and hora:
        out.append((_center("Fecha: %s Hora: %s" % (fecha, hora)), _LineKind.META))
    elif fecha:
        out.append((_center("Fecha: %s" % fecha), _LineKind.META))
    elif hora:
        out.append((_center("Hora: %s" % hora), _LineKind.META))

    out.append(
        (
            _center(
                "Ticket: %s ID: %s"
                % (data.get("ticket") or "", data.get("id") or data.get("ticket") or "")
            ),
            _LineKind.META,
        )
    )
    cajero = str(data.get("cajero") or "").strip()
    if cajero:
        out.append((_center("Cajero: %s" % cajero), _LineKind.META))

    out.append((_sep(), _LineKind.SEP))
    out.append((_tabla_header_line(), _LineKind.META))
    out.append((_sep(), _LineKind.SEP))
    for fila in filas:
        row_lines = _tabla_filas_lines(
            fila.get("tipo_abbr"),
            fila.get("numero"),
            fila.get("loteria"),
            fila.get("monto"),
        )
        for line in row_lines:
            out.append((line, _LineKind.PLAY))
    out.append((_sep(), _LineKind.SEP))
    out.append((_total_line(total), _LineKind.TOTAL))
    out.append((_sep(), _LineKind.SEP))

    return out, total


def generar_ticket(data: dict) -> str:
    estructurado, _ = _lineas_ticket_estructurado(data)
    parts: List[str] = []
    for txt, kind in estructurado:
        if kind == _LineKind.BLANK:
            parts.append("")
        else:
            parts.append(txt if txt is not None else "")
    return "\n".join(parts) + "\n"


def render_ticket_html(data: dict, qr_url: Optional[str] = None) -> str:
    """HTML semántico 58mm para navegador / impresión (sin QR)."""
    _ = qr_url  # obsoleto; se ignora
    filas, total = _filas_jugadas_ticket(data.get("jugadas") or [])
    fecha = str(data.get("fecha") or "").strip()
    hora = _hora_display(data.get("hora") or data.get("hora_venta") or "")
    cajero = str(data.get("cajero") or "").strip()
    ticket_pub = str(data.get("ticket") or "")
    ticket_id = str(data.get("id") or ticket_pub)

    parts: List[str] = []
    parts.append('<div class="header">VENTA DE LOTERÍA</div>')
    parts.append('<div class="line">%s</div>' % html.escape(_sep()))

    if fecha and hora:
        parts.append(
            '<div class="info">Fecha: %s Hora: %s</div>'
            % (html.escape(fecha), html.escape(hora))
        )
    elif fecha:
        parts.append('<div class="info">Fecha: %s</div>' % html.escape(fecha))
    elif hora:
        parts.append('<div class="info">Hora: %s</div>' % html.escape(hora))

    parts.append(
        '<div class="info">Ticket: %s ID: %s</div>'
        % (html.escape(ticket_pub), html.escape(ticket_id))
    )
    if cajero:
        parts.append('<div class="info">Cajero: %s</div>' % html.escape(cajero))

    parts.append('<div class="line">%s</div>' % html.escape(_sep()))
    parts.append('<table class="ticket-table" aria-label="Detalle jugadas">')
    parts.append(
        "<thead><tr>"
        "<th class=\"col-type\">Tipo</th>"
        "<th class=\"col-num\">Numero</th>"
        "<th class=\"col-lot\">Loteria</th>"
        "<th class=\"col-val\">Valor</th>"
        "</tr></thead><tbody>"
    )
    for fila in filas:
        tipo = html.escape(str(fila.get("tipo_abbr") or "Q"))
        numero = html.escape(str(fila.get("numero") or "").strip())
        loteria = html.escape(str(fila.get("loteria") or "-").strip())
        val = html.escape("RD$%s" % _money(fila.get("monto")))
        parts.append(
            "<tr>"
            "<td class=\"col-type\">%s</td>"
            "<td class=\"col-num\">%s</td>"
            "<td class=\"col-lot\">%s</td>"
            "<td class=\"col-val\">%s</td>"
            "</tr>"
            % (tipo, numero, loteria, val)
        )
    parts.append("</tbody></table>")
    parts.append('<div class="line">%s</div>' % html.escape(_sep()))
    parts.append('<div class="total">%s</div>' % html.escape(_total_line(total)))
    parts.append('<div class="line">%s</div>' % html.escape(_sep()))

    return "\n".join(parts)


# --- ESC/POS ---

def esc_init() -> bytes:
    return b"\x1b\x40"


def esc_align(mode: int = 0) -> bytes:
    return bytes([0x1B, 0x61, max(0, min(2, mode))])


def esc_feed(n: int = 1) -> bytes:
    return bytes([0x1B, 0x64, max(0, min(255, int(n)))])


def esc_bold(on: bool = True) -> bytes:
    return bytes([0x1B, 0x45, 1 if on else 0])


def esc_size(width: int = 1, height: int = 1) -> bytes:
    w = max(1, min(8, int(width))) - 1
    h = max(1, min(8, int(height))) - 1
    return bytes([0x1D, 0x21, (h << 4) | w])


def esc_reset_style() -> bytes:
    return esc_size(1, 1) + esc_bold(False)


def esc_text_line(text: str) -> bytes:
    return _cp437(text) + b"\n"


def _esc_linea(text: str, kind: _LineKind) -> bytes:
    buf = bytearray()
    if kind == _LineKind.BLANK:
        return esc_text_line("")

    if kind == _LineKind.HEADER:
        buf += esc_size(2, 2)
        buf += esc_bold(True)
    elif kind == _LineKind.TOTAL:
        buf += esc_size(2, 2)
        buf += esc_bold(True)
    elif kind in (_LineKind.JUGADA, _LineKind.LOTERIA):
        buf += esc_size(1, 2)
        buf += esc_bold(True)
    else:
        buf += esc_size(1, 1)
        buf += esc_bold(True)

    buf += esc_text_line(text)
    buf += esc_reset_style()
    return bytes(buf)


def qr_code_escpos(data: str, module_size: int = 10) -> bytes:
    payload = _cp437(str(data or ""))
    ms = max(4, min(16, int(module_size)))
    length = len(payload) + 3
    return (
        b"\x1d\x28\x6b\x04\x00\x31\x41\x32\x00"
        + b"\x1d\x28\x6b\x03\x00\x31\x43" + bytes([ms])
        + b"\x1d\x28\x6b"
        + bytes([length & 0xFF, (length >> 8) & 0xFF])
        + b"\x31\x50\x30"
        + payload
        + b"\x1d\x28\x6b\x03\x00\x31\x51\x30"
    )


def generar_ticket_escpos(data: dict, qr_url: Optional[str] = None) -> bytes:
    _ = qr_url  # obsoleto; sin QR en ticket de venta
    estructurado, _ = _lineas_ticket_estructurado(data)
    buf = bytearray()
    buf += esc_init()
    buf += esc_align(1)
    for txt, kind in estructurado:
        buf += _esc_linea(txt, kind)
    buf += esc_feed(4)
    return bytes(buf)


def ticket_escpos_b64(data: dict, qr_url: Optional[str] = None) -> str:
    return base64.b64encode(generar_ticket_escpos(data, qr_url)).decode("ascii")


def generar_recibo_pago_escpos(
    ticket_id,
    premio,
    cajero,
    fecha,
    lottery="",
    play="",
    numero_ganador="",
) -> bytes:
    buf = bytearray()
    buf += esc_init()
    buf += esc_align(1)
    buf += _esc_linea("LA QUE NUNCA FALLA", _LineKind.HEADER)
    buf += _esc_linea("PAGO DE PREMIO", _LineKind.JUGADA)
    buf += _esc_linea(_sep(), _LineKind.SEP)
    buf += _esc_linea("Ticket: %s" % ticket_id, _LineKind.META)
    buf += _esc_linea("Cajero: %s" % cajero, _LineKind.META)
    buf += _esc_linea("Fecha: %s" % fecha, _LineKind.META)
    if lottery:
        buf += _esc_linea(str(lottery).strip(), _LineKind.LOTERIA)
    if play:
        buf += _esc_linea("Jugada: %s" % play, _LineKind.META)
    if numero_ganador:
        buf += _esc_linea(str(numero_ganador), _LineKind.PLAY)
    buf += _esc_linea(_sep(), _LineKind.SEP)
    buf += _esc_linea("TOTAL RD$%s" % _money(premio), _LineKind.TOTAL)
    buf += _esc_linea(_sep(), _LineKind.SEP)
    buf += _esc_linea("PREMIO PAGADO", _LineKind.FOOTER)
    buf += esc_feed(4)
    return bytes(buf)


def recibo_pago_escpos_b64(**kwargs) -> str:
    return base64.b64encode(generar_recibo_pago_escpos(**kwargs)).decode("ascii")


TICKET_THERMAL_CSS = open(
    os.path.join(os.path.dirname(__file__), "static", "ticket_thermal.css"),
    encoding="utf-8",
).read() if os.path.isfile(os.path.join(os.path.dirname(__file__), "static", "ticket_thermal.css")) else ""
