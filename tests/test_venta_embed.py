"""Evita regresiones: /venta no debe embeber JSON ejecutable en <script> (solo textarea + JS externo)."""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import time

import pytest


def test_venta_uses_textarea_for_json_not_executable_script(app_mod):
    client = app_mod.app.test_client()
    with client.session_transaction() as sess:
        sess["u"] = "jose0219"
        sess["uid"] = 1
        sess["role"] = "cajero"
        sess["last_activity"] = time.time()
        sess["last_activity_touch"] = time.time()
    r = client.get("/venta")
    assert r.status_code == 200, r.status_code
    html = r.get_data(as_text=True)
    assert 'id="venta-lotteries-json"' in html
    assert "<textarea" in html
    assert 'id="venta-lotteries-json"' in html
    assert '<script type="application/json" id="venta-lotteries-json">' not in html
    assert '<script type="application/json" id="venta-msg-rechazo-json">' not in html
    assert '<script type="application/json" id="venta-repetir-json">' not in html


def test_venta_pos_js_syntax_ok():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    root = pathlib.Path(__file__).resolve().parents[1]
    path = root / "static" / "venta_pos.js"
    r = subprocess.run(
        [node, "--check", str(path)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert r.returncode == 0, r.stderr or r.stdout
