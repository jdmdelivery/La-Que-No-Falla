# -*- coding: utf-8 -*-
"""
Banco General único + subcuentas virtuales por cajero (derivadas del historial).
No crea bancos físicos separados: un balance global y movimientos auditables.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

TZ_RD = ZoneInfo("America/Santo_Domingo")

TIPO_BALANCE_INICIAL = "balance_inicial"
TIPO_VENTA = "venta_ticket"
TIPO_PREMIO = "premio_pagado"
TIPO_ENTREGA = "entrega_cajero_admin"
TIPO_FONDO = "fondo_entregado_cajero"
TIPO_RETIRO = "retiro_banco"
TIPO_AJUSTE = "ajuste_manual"
TIPO_ANULACION = "anulacion"
TIPO_REVERSA_PAGO_PREMIO = "reversa_pago_premio"

# Alias legible (DB conserva premio_pagado por compatibilidad)
TIPO_PAGO_PREMIO_ALIAS = "pago_premio"

TIPO_LABELS = {
    TIPO_BALANCE_INICIAL: "Balance inicial",
    TIPO_VENTA: "Venta ticket",
    TIPO_PREMIO: "Premio pagado",
    TIPO_PAGO_PREMIO_ALIAS: "Premio pagado",
    TIPO_ENTREGA: "Entrega cajero → admin",
    TIPO_FONDO: "Fondo admin → cajero",
    TIPO_RETIRO: "Retiro banco",
    TIPO_AJUSTE: "Ajuste manual",
    TIPO_ANULACION: "Anulación",
    TIPO_REVERSA_PAGO_PREMIO: "Reversa pago premio",
}

ROLE_CAJERO_DEFAULT = "cajero"


def _is_pg() -> bool:
    return bool(os.environ.get("DATABASE_URL"))


def _sql(q: str) -> str:
    if _is_pg():
        return q
    return q.replace("%s", "?")


def _now_ts() -> str:
    return datetime.now(TZ_RD).strftime("%Y-%m-%d %H:%M:%S")


def _row_dict(row):
    if row is None:
        return None
    if hasattr(row, "keys"):
        return dict(row)
    return row


def _f(v, default=0.0) -> float:
    try:
        return round(float(v or 0), 2)
    except (TypeError, ValueError):
        return float(default)


def banco_init_schema(cur, pk: str) -> None:
    """Crea tablas banco_general y banco_movimientos (idempotente)."""
    is_pg = _is_pg()
    bool_t = "BOOLEAN" if is_pg else "INTEGER"
    ts_def = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP" if is_pg else "TEXT"

    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS banco_general (
            id {pk},
            balance_inicial NUMERIC NOT NULL DEFAULT 0,
            balance_actual NUMERIC NOT NULL DEFAULT 0,
            creado_por TEXT,
            updated_by TEXT,
            created_at {ts_def},
            updated_at {ts_def},
            activo {bool_t} NOT NULL DEFAULT TRUE
        )
        """
    )
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS banco_movimientos (
            id {pk},
            tipo TEXT NOT NULL,
            monto NUMERIC NOT NULL DEFAULT 0,
            afecta_banco {bool_t} NOT NULL DEFAULT FALSE,
            suma_o_resta TEXT NOT NULL,
            balance_general_antes NUMERIC,
            balance_general_despues NUMERIC,
            cajero_balance_antes NUMERIC,
            cajero_balance_despues NUMERIC,
            cajero_id INTEGER,
            usuario_admin_id INTEGER,
            ticket_id INTEGER,
            pago_id INTEGER,
            descripcion TEXT,
            referencia_movimiento_id INTEGER,
            created_at {ts_def}
        )
        """
    )
    try:
        cur.execute(
            _sql(
                "ALTER TABLE banco_movimientos ADD COLUMN referencia_movimiento_id INTEGER"
            )
        )
    except Exception:
        pass
    for idx_sql in (
        "CREATE INDEX IF NOT EXISTS idx_banco_mov_cajero ON banco_movimientos(cajero_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_banco_mov_tipo ON banco_movimientos(tipo, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_banco_mov_ticket ON banco_movimientos(ticket_id)",
        "CREATE INDEX IF NOT EXISTS idx_banco_mov_pago ON banco_movimientos(pago_id)",
        "CREATE INDEX IF NOT EXISTS idx_banco_mov_created ON banco_movimientos(created_at DESC)",
    ):
        try:
            cur.execute(_sql(idx_sql))
        except Exception:
            pass
    if is_pg:
        try:
            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_banco_mov_venta_ticket
                ON banco_movimientos(ticket_id)
                WHERE tipo = 'venta_ticket' AND ticket_id IS NOT NULL
                """
            )
            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_banco_mov_premio_pago
                ON banco_movimientos(pago_id)
                WHERE tipo = 'premio_pagado' AND pago_id IS NOT NULL
                """
            )
        except Exception as ex:
            log.warning("banco_init_schema índices únicos PG: %s", ex)


def _resolve_cajero_id(cur, cajero_id=None, cajero_username=None):
    if cajero_id is not None:
        try:
            cid = int(cajero_id)
            if cid > 0:
                return cid
        except (TypeError, ValueError):
            pass
    uname = (cajero_username or "").strip()
    if not uname:
        return None
    cur.execute(
        _sql(
            "SELECT id FROM users WHERE TRIM(COALESCE(username, '')) = TRIM(%s) LIMIT 1"
        ),
        (uname,),
    )
    r = cur.fetchone()
    if not r:
        return None
    d = _row_dict(r)
    if d:
        return int(d.get("id") or 0) or None
    return int(r[0]) if r else None


def _ensure_banco_general_row(cur):
    if _is_pg():
        cur.execute(
            "SELECT id, balance_actual, balance_inicial FROM banco_general WHERE activo = TRUE ORDER BY id LIMIT 1"
        )
    else:
        cur.execute(
            _sql(
                "SELECT id, balance_actual, balance_inicial FROM banco_general WHERE COALESCE(activo, 1) = 1 ORDER BY id LIMIT 1"
            )
        )
    row = cur.fetchone()
    if row:
        d = _row_dict(row)
        if d:
            return int(d["id"]), _f(d.get("balance_actual")), _f(d.get("balance_inicial"))
        return int(row[0]), _f(row[1]), _f(row[2])
    ts = _now_ts()
    if _is_pg():
        cur.execute(
            """
            INSERT INTO banco_general (balance_inicial, balance_actual, creado_por, updated_by, created_at, updated_at, activo)
            VALUES (0, 0, 'sistema', 'sistema', %s, %s, TRUE)
            RETURNING id, balance_actual, balance_inicial
            """,
            (ts, ts),
        )
        r = cur.fetchone()
        d = _row_dict(r)
        return int(d["id"]), _f(d.get("balance_actual")), _f(d.get("balance_inicial"))
    cur.execute(
        _sql(
            """
            INSERT INTO banco_general (balance_inicial, balance_actual, creado_por, updated_by, created_at, updated_at, activo)
            VALUES (0, 0, 'sistema', 'sistema', %s, %s, 1)
            """
        ),
        (ts, ts),
    )
    cur.execute("SELECT last_insert_rowid()")
    rid = int(cur.fetchone()[0])
    return rid, 0.0, 0.0


def banco_get_balance_general(cur) -> float:
    _, bal, _ = _ensure_banco_general_row(cur)
    return bal


def banco_get_balance_cajero(cur, cajero_id) -> float:
    cid = _resolve_cajero_id(cur, cajero_id=cajero_id)
    if not cid:
        return 0.0
    return _balance_cajero_from_movimientos(cur, cid)


def _balance_cajero_from_movimientos(cur, cajero_id: int) -> float:
    cur.execute(
        _sql(
            """
            SELECT COALESCE(SUM(
                CASE
                    WHEN cajero_id IS NULL THEN 0
                    WHEN suma_o_resta = '+' THEN monto
                    WHEN suma_o_resta = '-' THEN -monto
                    ELSE 0
                END
            ), 0) AS bal
            FROM banco_movimientos
            WHERE cajero_id = %s
            """
        ),
        (int(cajero_id),),
    )
    row = cur.fetchone()
    if not row:
        return 0.0
    d = _row_dict(row)
    if d:
        return _f(d.get("bal"))
    return _f(row[0])


def _movimiento_duplicado(cur, tipo: str, ticket_id=None, pago_id=None) -> bool:
    if tipo == TIPO_VENTA and ticket_id:
        cur.execute(
            _sql(
                "SELECT id FROM banco_movimientos WHERE tipo = %s AND ticket_id = %s LIMIT 1"
            ),
            (TIPO_VENTA, int(ticket_id)),
        )
        return cur.fetchone() is not None
    if tipo == TIPO_PREMIO and pago_id:
        cur.execute(
            _sql(
                "SELECT id FROM banco_movimientos WHERE tipo = %s AND pago_id = %s LIMIT 1"
            ),
            (TIPO_PREMIO, int(pago_id)),
        )
        return cur.fetchone() is not None
    return False


def _update_banco_general_balance(cur, nuevo_balance: float, updated_by: str = "sistema"):
    bid, _, _ = _ensure_banco_general_row(cur)
    ts = _now_ts()
    if _is_pg():
        cur.execute(
            """
            UPDATE banco_general
            SET balance_actual = %s, updated_by = %s, updated_at = %s
            WHERE id = %s
            """,
            (_f(nuevo_balance), (updated_by or "sistema")[:120], ts, bid),
        )
    else:
        cur.execute(
            _sql(
                """
                UPDATE banco_general
                SET balance_actual = %s, updated_by = %s, updated_at = %s
                WHERE id = %s
                """
            ),
            (_f(nuevo_balance), (updated_by or "sistema")[:120], ts, bid),
        )


def _insert_movimiento(
    cur,
    *,
    tipo: str,
    monto: float,
    afecta_banco: bool,
    suma_o_resta: str,
    cajero_id=None,
    usuario_admin_id=None,
    ticket_id=None,
    pago_id=None,
    descripcion: str = "",
    updated_by: str = "sistema",
    skip_dup_check: bool = False,
    referencia_movimiento_id=None,
):
    m = _f(monto)
    if m <= 0:
        raise ValueError("monto_invalido")
    so = "+" if str(suma_o_resta).strip() == "+" else "-"
    if not skip_dup_check and _movimiento_duplicado(cur, tipo, ticket_id=ticket_id, pago_id=pago_id):
        return None

    gen_antes = banco_get_balance_general(cur)
    cid = _resolve_cajero_id(cur, cajero_id=cajero_id) if cajero_id else None
    caj_antes = _balance_cajero_from_movimientos(cur, cid) if cid else None

    gen_despues = gen_antes
    caj_despues = caj_antes

    if afecta_banco:
        gen_despues = gen_antes + m if so == "+" else gen_antes - m
        if gen_despues < -0.005 and tipo == TIPO_RETIRO:
            raise ValueError("saldo_banco_insuficiente")
        _update_banco_general_balance(cur, gen_despues, updated_by)

    if cid:
        base = caj_antes if caj_antes is not None else 0.0
        caj_despues = base + m if so == "+" else base - m
        if tipo == TIPO_ENTREGA and caj_despues < -0.005:
            raise ValueError("saldo_cajero_insuficiente")

    ts = _now_ts()
    ab = bool(afecta_banco)
    ab_store = ab if _is_pg() else (1 if ab else 0)
    ref_id = int(referencia_movimiento_id) if referencia_movimiento_id else None
    params = (
        tipo,
        m,
        ab_store,
        so,
        gen_antes,
        gen_despues,
        caj_antes,
        caj_despues,
        cid,
        int(usuario_admin_id) if usuario_admin_id else None,
        int(ticket_id) if ticket_id else None,
        int(pago_id) if pago_id else None,
        (descripcion or "")[:500],
        ref_id,
        ts,
    )
    if _is_pg():
        cur.execute(
            """
            INSERT INTO banco_movimientos (
                tipo, monto, afecta_banco, suma_o_resta,
                balance_general_antes, balance_general_despues,
                cajero_balance_antes, cajero_balance_despues,
                cajero_id, usuario_admin_id, ticket_id, pago_id,
                descripcion, referencia_movimiento_id, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            """,
            params,
        )
        r = cur.fetchone()
        return int(_row_dict(r)["id"]) if r else None
    cur.execute(
        _sql(
            """
            INSERT INTO banco_movimientos (
                tipo, monto, afecta_banco, suma_o_resta,
                balance_general_antes, balance_general_despues,
                cajero_balance_antes, cajero_balance_despues,
                cajero_id, usuario_admin_id, ticket_id, pago_id,
                descripcion, referencia_movimiento_id, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """
        ),
        params,
    )
    cur.execute("SELECT last_insert_rowid()")
    return int(cur.fetchone()[0])


def banco_tiene_balance_inicial(cur) -> bool:
    cur.execute(
        _sql("SELECT id FROM banco_movimientos WHERE tipo = %s LIMIT 1"),
        (TIPO_BALANCE_INICIAL,),
    )
    return cur.fetchone() is not None


def banco_configurar_inicial(cur, monto: float, usuario_admin_id=None, nota: str = ""):
    if banco_tiene_balance_inicial(cur):
        raise ValueError("balance_inicial_ya_configurado")
    m = _f(monto)
    if m < 0:
        raise ValueError("monto_invalido")
    admin = str(usuario_admin_id or "admin")
    bid, _, _ = _ensure_banco_general_row(cur)
    ts = _now_ts()
    if m == 0:
        cur.execute(
            _sql(
                """
                UPDATE banco_general
                SET balance_inicial = 0, creado_por = %s, updated_by = %s, updated_at = %s
                WHERE id = %s
                """
            ),
            (admin, admin, ts, bid),
        )
        cur.execute(
            _sql(
                """
                INSERT INTO banco_movimientos (
                    tipo, monto, afecta_banco, suma_o_resta,
                    balance_general_antes, balance_general_despues,
                    cajero_balance_antes, cajero_balance_despues,
                    cajero_id, usuario_admin_id, ticket_id, pago_id, descripcion, created_at
                ) VALUES (%s, 0, 0, '+', 0, 0, NULL, NULL, NULL, %s, NULL, NULL, %s, %s)
                """
            ),
            (TIPO_BALANCE_INICIAL, int(usuario_admin_id) if usuario_admin_id else None, nota or "Balance inicial cero", ts),
        )
        return None
    mov_id = _insert_movimiento(
        cur,
        tipo=TIPO_BALANCE_INICIAL,
        monto=m,
        afecta_banco=True,
        suma_o_resta="+",
        descripcion=nota or "Balance inicial del banco general",
        updated_by=admin,
        usuario_admin_id=usuario_admin_id,
        skip_dup_check=True,
    )
    cur.execute(
        _sql(
            "UPDATE banco_general SET balance_inicial = %s, creado_por = %s, updated_by = %s, updated_at = %s WHERE id = %s"
        ),
        (m, admin, admin, ts, bid),
    )
    return mov_id


def banco_registrar_venta(cur, ticket_id, cajero_id, monto, descripcion=None, cajero_username=None):
    tid = int(ticket_id)
    m = _f(monto)
    if _movimiento_duplicado(cur, TIPO_VENTA, ticket_id=tid):
        log.info(
            "[BANCO_SYNC_VENTA] ticket_id=%s monto=%.2f ya_existia=1 creado=0",
            tid,
            m,
        )
        return None
    cid = _resolve_cajero_id(cur, cajero_id=cajero_id, cajero_username=cajero_username)
    desc = descripcion or ("Venta ticket #%s" % tid)
    banco_antes = banco_get_balance_general(cur)
    mov_id = _insert_movimiento(
        cur,
        tipo=TIPO_VENTA,
        monto=m,
        afecta_banco=True,
        suma_o_resta="+",
        cajero_id=cid,
        ticket_id=tid,
        descripcion=desc,
        skip_dup_check=True,
    )
    log.info(
        "[BANCO_VENTA] ticket_id=%s monto=%.2f ya_existia=0 creado=1 banco_antes=%.2f banco_despues=%.2f",
        tid,
        m,
        banco_antes,
        banco_get_balance_general(cur),
    )
    return mov_id


def banco_registrar_pago(
    cur,
    pago_id,
    cajero_id,
    monto,
    ticket_id=None,
    descripcion=None,
    cajero_username=None,
    premio_id=None,
):
    pid = int(pago_id)
    m = _f(monto)
    if _movimiento_duplicado(cur, TIPO_PREMIO, pago_id=pid):
        log.info(
            "[BANCO_PAGO_PREMIO] premio_id=%s pago_id=%s ticket_id=%s monto=%.2f duplicado=1",
            premio_id,
            pid,
            ticket_id,
            m,
        )
        return None
    cid = _resolve_cajero_id(cur, cajero_id=cajero_id, cajero_username=cajero_username)
    desc = descripcion or ("Premio pagado #%s" % pid)
    banco_antes = banco_get_balance_general(cur)
    caj_antes = banco_get_balance_cajero(cur, cid) if cid else 0.0
    mov_id = _insert_movimiento(
        cur,
        tipo=TIPO_PREMIO,
        monto=m,
        afecta_banco=True,
        suma_o_resta="-",
        cajero_id=cid,
        pago_id=pid,
        ticket_id=ticket_id,
        descripcion=desc,
        skip_dup_check=True,
    )
    log.info(
        "[BANCO_PAGO_PREMIO] premio_id=%s pago_id=%s ticket_id=%s cajero_id=%s monto=%.2f "
        "banco_antes=%.2f banco_despues=%.2f cajero_antes=%.2f cajero_despues=%.2f",
        premio_id,
        pid,
        ticket_id,
        cid,
        m,
        banco_antes,
        banco_get_balance_general(cur),
        caj_antes,
        banco_get_balance_cajero(cur, cid) if cid else 0.0,
    )
    return mov_id


def banco_entrega_cajero_admin(cur, cajero_id, monto, nota="", usuario_admin_id=None, cajero_username=None):
    cid = _resolve_cajero_id(cur, cajero_id=cajero_id, cajero_username=cajero_username)
    if not cid:
        raise ValueError("cajero_no_encontrado")
    m = _f(monto)
    caj_antes = banco_get_balance_cajero(cur, cid)
    mov_id = _insert_movimiento(
        cur,
        tipo=TIPO_ENTREGA,
        monto=m,
        afecta_banco=False,
        suma_o_resta="-",
        cajero_id=cid,
        descripcion=nota or "Entrega cajero al admin",
        usuario_admin_id=usuario_admin_id,
        updated_by=str(usuario_admin_id or "admin"),
    )
    log.info(
        "[BANCO_ENTREGA] cajero_id=%s monto=%.2f cajero_antes=%.2f cajero_despues=%.2f mov_id=%s",
        cid,
        m,
        caj_antes,
        banco_get_balance_cajero(cur, cid),
        mov_id,
    )
    return mov_id


def banco_entregar_fondo_cajero(cur, cajero_id, monto, nota="", usuario_admin_id=None, cajero_username=None):
    cid = _resolve_cajero_id(cur, cajero_id=cajero_id, cajero_username=cajero_username)
    if not cid:
        raise ValueError("cajero_no_encontrado")
    m = _f(monto)
    caj_antes = banco_get_balance_cajero(cur, cid)
    mov_id = _insert_movimiento(
        cur,
        tipo=TIPO_FONDO,
        monto=m,
        afecta_banco=False,
        suma_o_resta="+",
        cajero_id=cid,
        descripcion=nota or "Fondo entregado al cajero",
        usuario_admin_id=usuario_admin_id,
        updated_by=str(usuario_admin_id or "admin"),
    )
    log.info(
        "[BANCO_FONDO] cajero_id=%s monto=%.2f cajero_antes=%.2f cajero_despues=%.2f mov_id=%s",
        cid,
        m,
        caj_antes,
        banco_get_balance_cajero(cur, cid),
        mov_id,
    )
    return mov_id


def banco_retiro_general(cur, monto, nota="", usuario_admin_id=None):
    m = _f(monto)
    banco_antes = banco_get_balance_general(cur)
    mov_id = _insert_movimiento(
        cur,
        tipo=TIPO_RETIRO,
        monto=m,
        afecta_banco=True,
        suma_o_resta="-",
        descripcion=nota or "Retiro del banco general",
        usuario_admin_id=usuario_admin_id,
        updated_by=str(usuario_admin_id or "admin"),
    )
    log.info(
        "[BANCO_RETIRO] monto=%.2f banco_antes=%.2f banco_despues=%.2f mov_id=%s",
        m,
        banco_antes,
        banco_get_balance_general(cur),
        mov_id,
    )
    return mov_id


def banco_ajuste_manual(
    cur,
    monto,
    suma_o_resta: str,
    nota="",
    usuario_admin_id=None,
    afecta_banco=True,
    cajero_id=None,
):
    so = "+" if str(suma_o_resta).strip() == "+" else "-"
    m = _f(monto)
    banco_antes = banco_get_balance_general(cur) if afecta_banco else None
    mov_id = _insert_movimiento(
        cur,
        tipo=TIPO_AJUSTE,
        monto=m,
        afecta_banco=bool(afecta_banco),
        suma_o_resta=so,
        cajero_id=cajero_id,
        descripcion=nota or "Ajuste manual",
        usuario_admin_id=usuario_admin_id,
        updated_by=str(usuario_admin_id or "admin"),
    )
    log.info(
        "[BANCO_AJUSTE] monto=%.2f signo=%s afecta_banco=%s banco_antes=%s banco_despues=%s mov_id=%s",
        m,
        so,
        bool(afecta_banco),
        banco_antes,
        banco_get_balance_general(cur) if afecta_banco else "—",
        mov_id,
    )
    return mov_id


def banco_anular_movimiento_venta(cur, ticket_id, cajero_id=None, monto=None, nota="", cajero_username=None):
    cur.execute(
        _sql(
            "SELECT monto, cajero_id FROM banco_movimientos WHERE tipo = %s AND ticket_id = %s LIMIT 1"
        ),
        (TIPO_VENTA, int(ticket_id)),
    )
    orig = cur.fetchone()
    if not orig:
        return None
    d = _row_dict(orig)
    m = _f(monto if monto is not None else (d.get("monto") if d else orig[0]))
    cid = cajero_id or (d.get("cajero_id") if d else None)
    return _insert_movimiento(
        cur,
        tipo=TIPO_ANULACION,
        monto=m,
        afecta_banco=True,
        suma_o_resta="-",
        cajero_id=cid,
        ticket_id=ticket_id,
        descripcion=nota or ("Anulación venta ticket #%s" % int(ticket_id)),
        skip_dup_check=True,
    )


def banco_revertir_movimiento_premio(cur, movimiento_id, nota="", usuario_admin_id=None):
    """Crea reversa_pago_premio enlazada al movimiento premio_pagado (idempotente)."""
    mid_orig = int(movimiento_id)
    cur.execute(
        _sql(
            "SELECT id, tipo, monto, afecta_banco, suma_o_resta, cajero_id, ticket_id, pago_id "
            "FROM banco_movimientos WHERE id = %s"
        ),
        (mid_orig,),
    )
    orig = cur.fetchone()
    if not orig:
        raise ValueError("movimiento_no_encontrado")
    d = _row_dict(orig) or {}
    if str(d.get("tipo") or "").strip().lower() != TIPO_PREMIO:
        raise ValueError("movimiento_no_es_premio")
    cur.execute(
        _sql(
            """
            SELECT id FROM banco_movimientos
            WHERE referencia_movimiento_id = %s
              AND tipo IN (%s, %s)
            LIMIT 1
            """
        ),
        (mid_orig, TIPO_ANULACION, TIPO_REVERSA_PAGO_PREMIO),
    )
    if cur.fetchone():
        return None
    monto_orig = _f(d.get("monto"))
    sign_orig = str(d.get("suma_o_resta") or "+").strip()
    sign_inv = "-" if sign_orig == "+" else "+"
    afecta = bool(d.get("afecta_banco"))
    cid = d.get("cajero_id")
    tid = d.get("ticket_id")
    pid_pago = d.get("pago_id")
    banco_antes = banco_get_balance_general(cur)
    cajero_antes = banco_get_balance_cajero(cur, cid) if cid else 0.0
    rev_id = _insert_movimiento(
        cur,
        tipo=TIPO_REVERSA_PAGO_PREMIO,
        monto=monto_orig,
        afecta_banco=afecta,
        suma_o_resta=sign_inv,
        cajero_id=cid,
        pago_id=pid_pago,
        ticket_id=tid,
        descripcion=nota or ("Reversa pago premio mov #%s" % mid_orig),
        usuario_admin_id=usuario_admin_id,
        skip_dup_check=True,
        referencia_movimiento_id=mid_orig,
    )
    log.info(
        "[BANCO_REVERSA_PAGO] premio_id=%s ticket_id=%s monto=%.2f "
        "banco_antes=%.2f banco_despues=%.2f cajero_antes=%.2f cajero_despues=%.2f "
        "movimiento_original=%s reversa_creada=%s",
        pid_pago,
        tid,
        monto_orig,
        banco_antes,
        banco_get_balance_general(cur),
        cajero_antes,
        banco_get_balance_cajero(cur, cid) if cid else 0.0,
        mid_orig,
        rev_id,
    )
    return rev_id


def banco_revertir_pagos_ticket(cur, ticket_id, nota="", usuario_admin_id=None):
    """Revierte todos los movimientos premio_pagado activos de un ticket."""
    tid = int(ticket_id)
    cur.execute(
        _sql(
            "SELECT id FROM banco_movimientos WHERE tipo = %s AND ticket_id = %s ORDER BY id ASC"
        ),
        (TIPO_PREMIO, tid),
    )
    out = []
    for row in cur.fetchall() or []:
        d = _row_dict(row) or {}
        mid = int(d.get("id") or 0)
        if mid > 0:
            r = banco_revertir_movimiento_premio(cur, mid, nota=nota, usuario_admin_id=usuario_admin_id)
            if r is not None:
                out.append(r)
    return out


def banco_revertir_pago_ticket(cur, ticket_id, monto_total, cajero_id=None, nota="", cajero_username=None):
    """Revierte el efecto de premios pagados (p. ej. al revertir pago de ticket)."""
    m = _f(monto_total)
    if m <= 0:
        return None
    cid = _resolve_cajero_id(cur, cajero_id=cajero_id, cajero_username=cajero_username)
    return _insert_movimiento(
        cur,
        tipo=TIPO_ANULACION,
        monto=m,
        afecta_banco=True,
        suma_o_resta="+",
        cajero_id=cid,
        ticket_id=ticket_id,
        descripcion=nota or ("Reversión pago premio ticket #%s" % int(ticket_id)),
        skip_dup_check=True,
    )


def _fecha_hoy_rd_iso() -> str:
    return datetime.now(TZ_RD).strftime("%Y-%m-%d")


def _frag_mov_hoy(is_pg: bool, alias: str = "bm") -> str:
    hoy = _fecha_hoy_rd_iso()
    if is_pg:
        return (
            f" AND ({alias}.created_at AT TIME ZONE 'America/Santo_Domingo')::date = %s "
        )
    return f" AND DATE({alias}.created_at) = %s "


def banco_get_dashboard_resumen(cur, is_pg=None, hoy_rd=None) -> dict:
    is_pg = bool(is_pg) if is_pg is not None else _is_pg()
    hoy = (hoy_rd or _fecha_hoy_rd_iso()).strip()[:10]
    bal_gen = banco_get_balance_general(cur)

    frag = _frag_mov_hoy(is_pg)
    params_hoy = (hoy,)

    cur.execute(
        _sql(
            """
            SELECT COALESCE(SUM(monto), 0) AS s
            FROM banco_movimientos bm
            WHERE tipo = %s
            """
            + frag
        ),
        (TIPO_VENTA,) + params_hoy,
    )
    r1 = cur.fetchone()
    ventas_hoy = _f(_row_dict(r1).get("s") if r1 else 0)

    cur.execute(
        _sql(
            """
            SELECT COALESCE(SUM(monto), 0) AS s
            FROM banco_movimientos bm
            WHERE tipo = %s
            """
            + frag
        ),
        (TIPO_PREMIO,) + params_hoy,
    )
    r2 = cur.fetchone()
    premios_hoy = _f(_row_dict(r2).get("s") if r2 else 0)

    dinero_cajeros = banco_sum_balances_cajeros(cur)
    _, _, bal_ini = _ensure_banco_general_row(cur)

    return {
        "balance_general": bal_gen,
        "balance_inicial": bal_ini,
        "ventas_hoy": ventas_hoy,
        "premios_hoy": premios_hoy,
        "dinero_en_cajeros": dinero_cajeros,
        "configurado": banco_tiene_balance_inicial(cur),
    }


def banco_sum_balances_cajeros(cur, role_cajero: str = ROLE_CAJERO_DEFAULT) -> float:
    cur.execute(
        _sql(
            """
            SELECT u.id FROM users u
            WHERE LOWER(TRIM(COALESCE(u.role, ''))) = LOWER(%s)
            """
        ),
        (role_cajero,),
    )
    rows = cur.fetchall() or []
    total = 0.0
    for r in rows:
        d = _row_dict(r)
        uid = int(d.get("id") if d else r[0])
        bal = banco_get_balance_cajero(cur, uid)
        if bal > 0.005:
            total += bal
    return round(total, 2)


def banco_list_cajeros_tabla(cur, role_cajero: str = ROLE_CAJERO_DEFAULT) -> list:
    cur.execute(
        _sql(
            """
            SELECT id, TRIM(COALESCE(username, '')) AS username
            FROM users
            WHERE LOWER(TRIM(COALESCE(role, ''))) = LOWER(%s)
            ORDER BY username
            """
        ),
        (role_cajero,),
    )
    users = [_row_dict(r) for r in (cur.fetchall() or [])]
    out = []
    for u in users:
        cid = int(u["id"])
        agg = banco_agregados_cajero(cur, cid)
        bal = banco_get_balance_cajero(cur, cid)
        out.append(
            {
                "cajero_id": cid,
                "username": u.get("username") or ("#%s" % cid),
                "nombre": u.get("username") or ("#%s" % cid),
                "ventas": agg["ventas"],
                "premios": agg["premios"],
                "entregado": agg["entregado"],
                "fondos": agg["fondos"],
                "balance": bal,
            }
        )
    return out


def banco_agregados_cajero(cur, cajero_id: int) -> dict:
    cur.execute(
        _sql(
            """
            SELECT
              COALESCE(SUM(CASE WHEN tipo = %s THEN monto ELSE 0 END), 0) AS ventas,
              COALESCE(SUM(CASE WHEN tipo = %s THEN monto ELSE 0 END), 0) AS premios,
              COALESCE(SUM(CASE WHEN tipo = %s THEN monto ELSE 0 END), 0) AS entregado,
              COALESCE(SUM(CASE WHEN tipo = %s THEN monto ELSE 0 END), 0) AS fondos
            FROM banco_movimientos
            WHERE cajero_id = %s
            """
        ),
        (TIPO_VENTA, TIPO_PREMIO, TIPO_ENTREGA, TIPO_FONDO, int(cajero_id)),
    )
    r = cur.fetchone()
    d = _row_dict(r) or {}
    return {
        "ventas": _f(d.get("ventas")),
        "premios": _f(d.get("premios")),
        "entregado": _f(d.get("entregado")),
        "fondos": _f(d.get("fondos")),
    }


def banco_historial(cur, limit: int = 200) -> list:
    cur.execute(
        _sql(
            """
            SELECT bm.*, u.username AS cajero_nombre
            FROM banco_movimientos bm
            LEFT JOIN users u ON u.id = bm.cajero_id
            ORDER BY bm.created_at DESC, bm.id DESC
            LIMIT %s
            """
        ),
        (int(limit),),
    )
    return [_format_hist_row(_row_dict(r)) for r in (cur.fetchall() or []) if r]


def banco_historial_cajero(cur, cajero_id, limit: int = 200) -> list:
    cur.execute(
        _sql(
            """
            SELECT bm.*, u.username AS cajero_nombre
            FROM banco_movimientos bm
            LEFT JOIN users u ON u.id = bm.cajero_id
            WHERE bm.cajero_id = %s
            ORDER BY bm.created_at DESC, bm.id DESC
            LIMIT %s
            """
        ),
        (int(cajero_id), int(limit)),
    )
    return [_format_hist_row(_row_dict(r)) for r in (cur.fetchall() or []) if r]


def _format_hist_row(d: dict) -> dict:
    if not d:
        return {}
    ab = d.get("afecta_banco")
    if isinstance(ab, bool):
        afecta = ab
    else:
        afecta = str(ab) in ("1", "true", "True", "t")
    return {
        "id": d.get("id"),
        "fecha": d.get("created_at"),
        "cajero": d.get("cajero_nombre") or ("#%s" % d.get("cajero_id") if d.get("cajero_id") else "—"),
        "tipo": d.get("tipo"),
        "monto": _f(d.get("monto")),
        "banco_antes": _f(d.get("balance_general_antes")),
        "banco_despues": _f(d.get("balance_general_despues")),
        "nota": d.get("descripcion") or "",
        "afecta_banco": afecta,
        "suma_o_resta": d.get("suma_o_resta"),
    }


def banco_get_general_row(cur) -> dict:
    _ensure_banco_general_row(cur)
    if _is_pg():
        cur.execute(
            "SELECT id, balance_inicial, balance_actual, creado_por, updated_by, created_at, updated_at FROM banco_general WHERE activo = TRUE ORDER BY id LIMIT 1"
        )
    else:
        cur.execute(
            _sql(
                "SELECT id, balance_inicial, balance_actual, creado_por, updated_by, created_at, updated_at FROM banco_general WHERE COALESCE(activo, 1) = 1 ORDER BY id LIMIT 1"
            )
        )
    r = cur.fetchone()
    return _row_dict(r) or {}


def _frag_ticket_fecha_rd(is_pg: bool, alias: str = "t") -> str:
    if is_pg:
        return (
            f"(CAST({alias}.created_at AS TIMESTAMPTZ) AT TIME ZONE 'America/Santo_Domingo')::date"
        )
    return f"DATE({alias}.created_at)"


def _tiene_col_referencia_mov(cur) -> bool:
    try:
        cur.execute(
            _sql("SELECT referencia_movimiento_id FROM banco_movimientos LIMIT 0")
        )
        return True
    except Exception:
        return False


def _sql_movimiento_activo_frag(alias: str = "bm") -> str:
    """Excluye movimientos ya revertidos/anulados (referencia_movimiento_id → original)."""
    return (
        " AND NOT EXISTS ("
        " SELECT 1 FROM banco_movimientos rev"
        " WHERE rev.referencia_movimiento_id = "
        + alias
        + ".id"
        " AND rev.tipo IN (%s, %s)"
        " )"
    )


def banco_recalcular_balance_desde_movimientos(cur) -> float:
    """
    Alinea balance_actual con la suma neta de movimientos activos que afectan el banco.
    Corrige desfases cuando hay venta_ticket en historial pero balance_actual quedó atrás.
    """
    is_pg = _is_pg()
    afecta_sql = (
        "COALESCE(bm.afecta_banco, FALSE) IS TRUE"
        if is_pg
        else "COALESCE(bm.afecta_banco, 0) <> 0"
    )
    activo_frag = ""
    params: list = [TIPO_ANULACION, TIPO_REVERSA_PAGO_PREMIO]
    if _tiene_col_referencia_mov(cur):
        activo_frag = (
            " AND NOT EXISTS ("
            " SELECT 1 FROM banco_movimientos rev"
            " WHERE rev.referencia_movimiento_id = bm.id"
            " AND rev.tipo IN (%s, %s)"
            " )"
        )
        params.extend([TIPO_ANULACION, TIPO_REVERSA_PAGO_PREMIO])
    try:
        cur.execute(
            _sql(
                """
                SELECT COALESCE(SUM(
                    CASE WHEN bm.suma_o_resta = '+' THEN bm.monto ELSE -bm.monto END
                ), 0) AS s
                FROM banco_movimientos bm
                WHERE """
                + afecta_sql
                + """
                AND bm.tipo NOT IN (%s, %s)
                """
                + activo_frag
            ),
            tuple(params),
        )
        r = cur.fetchone()
        d = _row_dict(r) or {}
        nuevo = round(_f(d.get("s") if d else (r[0] if r else 0)), 2)
    except Exception as ex:
        log.warning("banco_recalcular_balance_desde_movimientos: %s", ex, exc_info=True)
        return banco_get_balance_general(cur)
    viejo = banco_get_balance_general(cur)
    if abs(nuevo - viejo) > 0.009:
        _update_banco_general_balance(cur, nuevo, "recalc_movimientos")
        log.info(
            "[BANCO_RECALC] balance_antes=%.2f balance_despues=%.2f (suma movimientos activos)",
            viejo,
            nuevo,
        )
    return nuevo


def _fmt_ultimo_cierre_sql(ultimo_cierre):
    """Normaliza timestamp de último cierre para SQL SQLite/PG."""
    if ultimo_cierre is None:
        return None
    if hasattr(ultimo_cierre, "strftime"):
        return ultimo_cierre.strftime("%Y-%m-%d %H:%M:%S")
    return str(ultimo_cierre).strip()[:19].replace("T", " ")


def _frag_mov_despues_cierre(is_pg: bool, alias: str, ultimo_cierre) -> tuple:
    """Fragmento SQL + param para movimientos/tickets posteriores al cierre de ciclo."""
    u = _fmt_ultimo_cierre_sql(ultimo_cierre)
    if not u:
        return "", []
    if is_pg:
        return f" AND {alias}.created_at > %s::timestamptz", [u]
    return (
        f" AND datetime(substr(trim(cast({alias}.created_at as text)), 1, 19)) > datetime(%s)",
        [u],
    )


def _sum_movimientos_ciclo(
    cur,
    tipo: str,
    ultimo_cierre,
    *,
    solo_activos: bool = True,
    join_ticket: bool = False,
) -> float:
    """Suma movimientos del tipo en el ciclo actual (post último cierre)."""
    is_pg = _is_pg()
    frag, params_cierre = _frag_mov_despues_cierre(is_pg, "bm", ultimo_cierre)
    if not frag and ultimo_cierre is not None:
        return 0.0
    activo_frag = ""
    params = [tipo]
    if solo_activos:
        activo_frag = _sql_movimiento_activo_frag("bm")
        params.extend([TIPO_ANULACION, TIPO_REVERSA_PAGO_PREMIO])
    join_sql = ""
    if join_ticket:
        join_sql = " INNER JOIN tickets t ON t.id = bm.ticket_id"
        if frag:
            frag = frag.replace("bm.created_at", "t.created_at")
    params.extend(params_cierre)
    try:
        cur.execute(
            _sql(
                """
                SELECT COALESCE(SUM(bm.monto), 0) AS s
                FROM banco_movimientos bm
                """
                + join_sql
                + """
                WHERE bm.tipo = %s
                """
                + frag
                + activo_frag
            ),
            tuple(params),
        )
        r = cur.fetchone()
        d = _row_dict(r) or {}
        return _f(d.get("s") if d else (r[0] if r else 0))
    except Exception as ex:
        log.warning("_sum_movimientos_ciclo tipo=%s: %s", tipo, ex, exc_info=True)
        return 0.0


def _sum_movimientos_hoy(cur, tipo: str, fecha_rd: str, *, solo_activos: bool = True) -> float:
    is_pg = _is_pg()
    frag = _frag_mov_hoy(is_pg)
    activo_frag = ""
    params = [tipo, fecha_rd]
    if solo_activos:
        activo_frag = _sql_movimiento_activo_frag("bm")
        params.extend([TIPO_ANULACION, TIPO_REVERSA_PAGO_PREMIO])
    cur.execute(
        _sql(
            """
            SELECT COALESCE(SUM(monto), 0) AS s
            FROM banco_movimientos bm
            WHERE tipo = %s
            """
            + frag
            + activo_frag
        ),
        tuple(params),
    )
    r = cur.fetchone()
    d = _row_dict(r) or {}
    return _f(d.get("s") if d else (r[0] if r else 0))


def _ventas_tickets_dia_rd(cur, fecha_rd: str) -> float:
    """Suma ventas del día según tickets (misma lógica que panel admin «Ventas del día»)."""
    is_pg = _is_pg()
    fd = _frag_ticket_fecha_rd(is_pg, "t")
    try:
        cur.execute(
            _sql(
                """
                SELECT COALESCE(SUM(
                    COALESCE(
                        NULLIF(t.monto, 0),
                        (
                            SELECT COALESCE(SUM(tl.amount), 0)
                            FROM ticket_lines tl
                            WHERE tl.ticket_id = t.id
                              AND COALESCE(tl.estado, 'activo') <> 'cancelado'
                        ),
                        0
                    )
                ), 0) AS s
                FROM tickets t
                WHERE """
                + fd
                + """ = %s
                """
            ),
            (fecha_rd,),
        )
        r = cur.fetchone()
        d = _row_dict(r) or {}
        return _f(d.get("s") if d else (r[0] if r else 0))
    except Exception as ex:
        log.warning("_ventas_tickets_dia_rd fecha=%s: %s", fecha_rd, ex, exc_info=True)
        return 0.0


def _sum_premios_pagados_dia_rd(cur, fecha_rd: str) -> float:
    """Premios pagados del día (pagos_premios), alineado con dashboard admin."""
    is_pg = _is_pg()
    try:
        if is_pg:
            frag = (
                "(CAST(pp.fecha AS TIMESTAMPTZ) AT TIME ZONE 'America/Santo_Domingo')::date = %s"
            )
        else:
            frag = "DATE(pp.fecha) = %s"
        cur.execute(
            _sql(
                """
                SELECT COALESCE(SUM(pp.monto), 0) AS s
                FROM pagos_premios pp
                WHERE """
                + frag
                + """
                AND COALESCE(pp.revertido, 0) = 0
                """
            ),
            (fecha_rd,),
        )
        r = cur.fetchone()
        d = _row_dict(r) or {}
        return _f(d.get("s") if d else (r[0] if r else 0))
    except Exception as ex:
        log.warning("_sum_premios_pagados_dia_rd fecha=%s: %s", fecha_rd, ex, exc_info=True)
        return 0.0


def _sum_entregas_cajero_dia_rd(cur, fecha_rd: str) -> float:
    """Entregas cajero → admin del día (tabla entregas_cajero)."""
    is_pg = _is_pg()
    try:
        if is_pg:
            frag = (
                "(CAST(ec.fecha AS TIMESTAMPTZ) AT TIME ZONE 'America/Santo_Domingo')::date = %s"
            )
        else:
            frag = "DATE(ec.fecha) = %s"
        cur.execute(
            _sql(
                """
                SELECT COALESCE(SUM(ec.monto), 0) AS s
                FROM entregas_cajero ec
                WHERE """
                + frag
            ),
            (fecha_rd,),
        )
        r = cur.fetchone()
        d = _row_dict(r) or {}
        return _f(d.get("s") if d else (r[0] if r else 0))
    except Exception as ex:
        log.warning("_sum_entregas_cajero_dia_rd fecha=%s: %s", fecha_rd, ex, exc_info=True)
        return 0.0


def banco_sync_ventas(
    cur,
    fecha_rd=None,
    limit=800,
    registrar_venta_fn=None,
    *,
    desde_cierre=None,
):
    """
    Crea movimientos venta_ticket faltantes (idempotente por ticket_id).
    - Sin desde_cierre: tickets del día calendario RD.
    - Con desde_cierre: tickets del ciclo actual (post último cierre), misma fuente que «Ciclo actual».
    Devuelve dict: revisados, creados, omitidos_duplicado, errores.
    """
    _registrar = registrar_venta_fn or banco_registrar_venta
    fr = (str(fecha_rd or _fecha_hoy_rd_iso()).strip())[:10]
    is_pg = _is_pg()
    params = []
    if desde_cierre is not None:
        frag_cierre, params_cierre = _frag_mov_despues_cierre(is_pg, "t", desde_cierre)
        where_sql = " WHERE 1=1" + (frag_cierre or "")
        params.extend(params_cierre)
    else:
        if len(fr) != 10:
            return {"revisados": 0, "creados": 0, "omitidos_duplicado": 0, "errores": 0}
        fd = _frag_ticket_fecha_rd(is_pg, "t")
        where_sql = " WHERE " + fd + " = %s"
        params.append(fr)
    lim = max(1, min(int(limit or 800), 5000))
    params.append(lim)
    cur.execute(
        _sql(
            """
            SELECT t.id AS ticket_id,
                   t.cajero_id,
                   TRIM(COALESCE(t.cajero, '')) AS cajero,
                   COALESCE(
                       NULLIF(t.monto, 0),
                       (
                           SELECT COALESCE(SUM(tl.amount), 0)
                           FROM ticket_lines tl
                           WHERE tl.ticket_id = t.id
                             AND COALESCE(tl.estado, 'activo') <> 'cancelado'
                       ),
                       0
                   ) AS total
            FROM tickets t
            """
            + where_sql
            + """
              AND COALESCE(
                       NULLIF(t.monto, 0),
                       (
                           SELECT COALESCE(SUM(tl.amount), 0)
                           FROM ticket_lines tl
                           WHERE tl.ticket_id = t.id
                             AND COALESCE(tl.estado, 'activo') <> 'cancelado'
                       ),
                       0
                   ) > 0.004
            ORDER BY t.id ASC
            LIMIT %s
            """
        ),
        tuple(params),
    )
    rows = cur.fetchall() or []
    creados = 0
    omitidos = 0
    errores = 0
    for row in rows:
        d = _row_dict(row) or {}
        tid = int(d.get("ticket_id") or 0)
        if tid <= 0:
            continue
        total = _f(d.get("total"))
        if total <= 0.004:
            continue
        cid = d.get("cajero_id")
        cajero_txt = str(d.get("cajero") or "").strip()
        try:
            if _movimiento_duplicado(cur, TIPO_VENTA, ticket_id=tid):
                omitidos += 1
                log.info(
                    "[BANCO_SYNC_VENTA] ticket_id=%s monto=%.2f ya_existia=1 creado=0",
                    tid,
                    total,
                )
                continue
            _registrar(
                cur,
                tid,
                cid,
                total,
                cajero_username=cajero_txt or None,
            )
            creados += 1
        except Exception as ex:
            errores += 1
            log.warning("banco_sync_ventas ticket_id=%s: %s", tid, ex, exc_info=True)
    return {
        "fecha": fr,
        "revisados": len(rows),
        "creados": creados,
        "omitidos_duplicado": omitidos,
        "errores": errores,
    }


def _sum_ajustes_hoy_neto(cur, fecha_rd: str) -> float:
    """Suma neta de ajustes manuales del día (+ suma, − resta)."""
    is_pg = _is_pg()
    frag = _frag_mov_hoy(is_pg)
    activo_frag = ""
    params = [TIPO_AJUSTE, fecha_rd]
    if _tiene_col_referencia_mov(cur):
        activo_frag = _sql_movimiento_activo_frag("bm")
        params.extend([TIPO_ANULACION, TIPO_REVERSA_PAGO_PREMIO])
    try:
        cur.execute(
            _sql(
                """
                SELECT COALESCE(SUM(
                    CASE WHEN bm.suma_o_resta = '+' THEN bm.monto ELSE -bm.monto END
                ), 0) AS s
                FROM banco_movimientos bm
                WHERE bm.tipo = %s
                """
                + frag
                + activo_frag
            ),
            tuple(params),
        )
        r = cur.fetchone()
        d = _row_dict(r) or {}
        return round(_f(d.get("s") if d else (r[0] if r else 0)), 2)
    except Exception as ex:
        log.warning("_sum_ajustes_hoy_neto fecha=%s: %s", fecha_rd, ex, exc_info=True)
        return 0.0


def _sum_ajustes_ciclo_neto(cur, ultimo_cierre) -> float:
    """Suma neta de ajustes manuales del ciclo actual (post último cierre)."""
    is_pg = _is_pg()
    frag, params_cierre = _frag_mov_despues_cierre(is_pg, "bm", ultimo_cierre)
    if ultimo_cierre is not None and not frag:
        return 0.0
    activo_frag = ""
    params = [TIPO_AJUSTE]
    if _tiene_col_referencia_mov(cur):
        activo_frag = _sql_movimiento_activo_frag("bm")
        params.extend([TIPO_ANULACION, TIPO_REVERSA_PAGO_PREMIO])
    params.extend(params_cierre)
    try:
        cur.execute(
            _sql(
                """
                SELECT COALESCE(SUM(
                    CASE WHEN bm.suma_o_resta = '+' THEN bm.monto ELSE -bm.monto END
                ), 0) AS s
                FROM banco_movimientos bm
                WHERE bm.tipo = %s
                """
                + frag
                + activo_frag
            ),
            tuple(params),
        )
        r = cur.fetchone()
        d = _row_dict(r) or {}
        return round(_f(d.get("s") if d else (r[0] if r else 0)), 2)
    except Exception as ex:
        log.warning("_sum_ajustes_ciclo_neto: %s", ex, exc_info=True)
        return 0.0


def _auditoria_rango_fechas(periodo: str, fecha_rd: str) -> tuple:
    """Devuelve (fecha_desde, fecha_hasta) inclusive en ISO RD para filtro auditoría."""
    from datetime import timedelta

    p = (periodo or "hoy").strip().lower()
    fr = (str(fecha_rd or _fecha_hoy_rd_iso()).strip())[:10]
    if len(fr) != 10:
        fr = _fecha_hoy_rd_iso()
    if p in ("todo", "all", "historico"):
        return ("1900-01-01", fr)
    if p in ("ayer", "yesterday"):
        ay = (datetime.strptime(fr, "%Y-%m-%d").date() - timedelta(days=1)).isoformat()
        return (ay, ay)
    if p in ("semana", "week", "esta_semana"):
        d = datetime.strptime(fr, "%Y-%m-%d").date()
        ini = (d - timedelta(days=d.weekday())).isoformat()
        return (ini, fr)
    if p in ("mes", "month", "este_mes"):
        d = datetime.strptime(fr, "%Y-%m-%d").date()
        ini = d.replace(day=1).isoformat()
        return (ini, fr)
    return (fr, fr)


def banco_auditoria_consultar(
    cur,
    periodo: str = "hoy",
    fecha_rd=None,
    *,
    limit: int = 500,
    offset: int = 0,
    cajero_id=None,
    tipo=None,
) -> dict:
    """
    Auditoría financiera de banco_movimientos con filtros de periodo.
    periodo: hoy | ayer | semana | mes | todo
    """
    fr = (str(fecha_rd or _fecha_hoy_rd_iso()).strip())[:10]
    fd, fh = _auditoria_rango_fechas(periodo, fr)
    is_pg = _is_pg()
    if is_pg:
        frag = (
            "(CAST(bm.created_at AS TIMESTAMPTZ) AT TIME ZONE 'America/Santo_Domingo')::date "
            "BETWEEN %s AND %s"
        )
    else:
        frag = "DATE(bm.created_at) BETWEEN %s AND %s"
    params = [fd, fh]
    extra = ""
    if cajero_id:
        extra += " AND bm.cajero_id = %s"
        params.append(int(cajero_id))
    if tipo:
        extra += " AND bm.tipo = %s"
        params.append(str(tipo).strip().lower())
    lim = max(1, min(int(limit or 500), 2000))
    off = max(0, int(offset or 0))
    params.extend([lim, off])
    cur.execute(
        _sql(
            """
            SELECT bm.*,
                   TRIM(COALESCE(u.username, '')) AS cajero_nombre,
                   TRIM(COALESCE(ua.username, '')) AS admin_nombre
            FROM banco_movimientos bm
            LEFT JOIN users u ON u.id = bm.cajero_id
            LEFT JOIN users ua ON ua.id = bm.usuario_admin_id
            WHERE """
            + frag
            + extra
            + """
            ORDER BY bm.created_at DESC, bm.id DESC
            LIMIT %s OFFSET %s
            """
        ),
        tuple(params),
    )
    rows = []
    for r in cur.fetchall() or []:
        d = _row_dict(r) or {}
        if not d and r:
            continue
        tipo_raw = str(d.get("tipo") or "")
        rows.append(
            {
                "id": d.get("id"),
                "fecha": str(d.get("created_at") or "")[:19],
                "tipo": tipo_raw,
                "tipo_label": TIPO_LABELS.get(tipo_raw, tipo_raw),
                "usuario": d.get("admin_nombre") or d.get("cajero_nombre") or "—",
                "cajero": d.get("cajero_nombre") or "—",
                "cajero_id": d.get("cajero_id"),
                "ticket_id": d.get("ticket_id"),
                "pago_id": d.get("pago_id"),
                "monto": round(_f(d.get("monto")), 2),
                "suma_o_resta": d.get("suma_o_resta"),
                "afecta_banco": bool(d.get("afecta_banco")),
                "balance_general_antes": round(_f(d.get("balance_general_antes")), 2),
                "balance_general_despues": round(_f(d.get("balance_general_despues")), 2),
                "cajero_balance_antes": (
                    round(_f(d.get("cajero_balance_antes")), 2)
                    if d.get("cajero_balance_antes") is not None
                    else None
                ),
                "cajero_balance_despues": (
                    round(_f(d.get("cajero_balance_despues")), 2)
                    if d.get("cajero_balance_despues") is not None
                    else None
                ),
                "descripcion": d.get("descripcion") or "",
                "referencia_movimiento_id": d.get("referencia_movimiento_id"),
            }
        )
    return {
        "periodo": periodo,
        "fecha_desde": fd,
        "fecha_hasta": fh,
        "total_mostrados": len(rows),
        "movimientos": rows,
    }


def banco_resumen_global(
    cur,
    fecha_rd=None,
    *,
    premios_pendientes=None,
    pendiente_total=None,
    ciclo_ventas=None,
    ventas_ciclo_ref=None,
    premios_ciclo_ref=None,
    entregas_ciclo_ref=None,
    ultimo_cierre=None,
    ventas_dia_ref=None,
    premios_pagados_dia_ref=None,
    entregas_dia_ref=None,
    role_cajero: str = ROLE_CAJERO_DEFAULT,
):
    """
    Fuente única de KPIs financieros del banco.

    Métricas operativas (ventas, premios pagados, cajeros, retiros, ajustes, ciclo):
    solo del ciclo actual (post-cierre) — se reinician a cero tras cerrar.

    Banco General = saldo acumulado real (banco_movimientos); no se reinicia en cierre.
    neto_disponible = banco_general − premios_pendientes (ciclo).
    """
    fr = (str(fecha_rd or _fecha_hoy_rd_iso()).strip())[:10]
    if len(fr) != 10:
        fr = _fecha_hoy_rd_iso()

    _, _, bal_ini = _ensure_banco_general_row(cur)
    saldo_base = banco_recalcular_balance_desde_movimientos(cur)

    ventas_mov_ciclo = _sum_movimientos_ciclo(
        cur, TIPO_VENTA, ultimo_cierre, solo_activos=True, join_ticket=False
    )
    premios_mov_ciclo = _sum_movimientos_ciclo(
        cur, TIPO_PREMIO, ultimo_cierre, solo_activos=True, join_ticket=False
    )
    entregas_mov_ciclo = _sum_movimientos_ciclo(
        cur, TIPO_ENTREGA, ultimo_cierre, solo_activos=True, join_ticket=False
    )
    fondos_ciclo = _sum_movimientos_ciclo(
        cur, TIPO_FONDO, ultimo_cierre, solo_activos=False, join_ticket=False
    )
    retiros_ciclo = _sum_movimientos_ciclo(
        cur, TIPO_RETIRO, ultimo_cierre, solo_activos=True, join_ticket=False
    )
    ajustes_ciclo_neto = _sum_ajustes_ciclo_neto(cur, ultimo_cierre)

    ventas_ciclo = round(
        max(_f(ventas_ciclo_ref), _f(ciclo_ventas), ventas_mov_ciclo, 0.0), 2
    )
    premios_pagados_ciclo = round(
        max(_f(premios_ciclo_ref), premios_mov_ciclo, 0.0), 2
    )
    entregas_ciclo = round(
        max(_f(entregas_ciclo_ref), entregas_mov_ciclo, 0.0), 2
    )

    # KPIs operativos del ciclo (reinician tras cierre)
    ventas_hoy = ventas_ciclo
    premios_pagados_hoy = premios_pagados_ciclo
    entregas_hoy = entregas_ciclo
    retiros_hoy = retiros_ciclo
    ajustes_hoy_neto = ajustes_ciclo_neto
    ciclo_actual = ventas_ciclo

    ventas_delta = round(max(0.0, ventas_ciclo - ventas_mov_ciclo), 2)
    premios_delta = round(max(0.0, premios_pagados_ciclo - premios_mov_ciclo), 2)
    # Banco General = saldo acumulado en banco_movimientos (no reinicia en cierre).
    # No sumar ventas_delta ni restar premios_delta: eso inflaba el banco con tickets del ciclo
    # y al cerrar (ciclo→0) el KPI caía en ~dinero_en_cajeros. Sync en _banco_sync_ventas / cierre.
    banco_final = round(saldo_base, 2)
    banco_formula_dia = round(
        saldo_base + ventas_ciclo - premios_pagados_ciclo - retiros_ciclo + ajustes_ciclo_neto,
        2,
    )

    pendiente_premios = _f(premios_pendientes) if premios_pendientes is not None else 0.0
    pendiente_total_val = (
        _f(pendiente_total) if pendiente_total is not None else pendiente_premios
    )

    formula_ciclo_cajeros = round(
        max(0.0, ventas_ciclo - premios_pagados_ciclo - entregas_ciclo + fondos_ciclo), 2
    )
    cajeros = banco_list_cajeros_tabla(cur, role_cajero=role_cajero)
    suma_balances_cajeros = round(
        sum(max(0.0, _f(c.get("balance"))) for c in cajeros), 2
    )
    dinero_en_cajeros = formula_ciclo_cajeros
    neto_disponible = round(max(0.0, banco_final - pendiente_premios), 2)

    log.info(
        "[BANCO_RESUMEN] fecha=%s saldo_base_banco=%.2f ventas_hoy=%.2f premios_pagados_hoy=%.2f "
        "pendiente_premios=%.2f pendiente_total=%.2f dinero_cajeros=%.2f ciclo_actual=%.2f "
        "banco_general=%.2f neto_disponible=%.2f retiros_hoy=%.2f ajustes_hoy=%.2f "
        "| ventas_ciclo=%.2f ventas_mov_ciclo=%.2f ventas_delta=%.2f premios_delta=%.2f "
        "formula_ciclo_cajeros=%.2f suma_balances_historico=%.2f",
        fr,
        saldo_base,
        ventas_hoy,
        premios_pagados_hoy,
        pendiente_premios,
        pendiente_total_val,
        dinero_en_cajeros,
        ciclo_actual,
        banco_final,
        neto_disponible,
        retiros_hoy,
        ajustes_hoy_neto,
        ventas_ciclo,
        ventas_mov_ciclo,
        ventas_delta,
        premios_delta,
        formula_ciclo_cajeros,
        suma_balances_cajeros,
    )

    return {
        "fecha": fr,
        "balance_inicial": round(bal_ini, 2),
        "saldo_base": round(saldo_base, 2),
        "saldo_base_banco": round(saldo_base, 2),
        "banco_general": banco_final,
        "balance_general": banco_final,
        "banco_final": banco_final,
        "ventas_delta": ventas_delta,
        "premios_delta": premios_delta,
        "entregas_delta": 0.0,
        "ventas_hoy": round(ventas_hoy, 2),
        "ventas_ciclo": ventas_ciclo,
        "premios_pagados_hoy": round(premios_pagados_hoy, 2),
        "premios_hoy": round(premios_pagados_hoy, 2),
        "pendiente_premios": round(pendiente_premios, 2),
        "pendiente_total": round(pendiente_total_val, 2),
        "pendiente_en_manos_cajeros": dinero_en_cajeros,
        "dinero_en_cajeros": dinero_en_cajeros,
        "dinero_cajeros": dinero_en_cajeros,
        "ciclo_actual": round(ciclo_actual, 2),
        "entregas_hoy": round(entregas_hoy, 2),
        "fondos_hoy": round(fondos_ciclo, 2),
        "retiros_hoy": round(retiros_hoy, 2),
        "ajustes_hoy_neto": ajustes_hoy_neto,
        "banco_formula_dia": banco_formula_dia,
        "suma_balances_cajeros": suma_balances_cajeros,
        "formula_dia_cajeros": formula_ciclo_cajeros,
        "neto_disponible": neto_disponible,
        "ventas_tickets_dia": round(_ventas_tickets_dia_rd(cur, fr), 2),
        "ventas_mov": round(ventas_mov_ciclo, 2),
        "premios_mov": round(premios_mov_ciclo, 2),
        "cajeros": cajeros,
        "configurado": banco_tiene_balance_inicial(cur),
        "tipo_labels": dict(TIPO_LABELS),
    }
