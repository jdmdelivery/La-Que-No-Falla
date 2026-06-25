#!/usr/bin/env python3
"""
Valida que /venta no embeba JavaScript con SyntaxError.
Uso: python scripts/validate_venta_js.py
Sale 0 si todo OK; 1 si falla (CI / pre-deploy).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"
VENTA_JS = ROOT / "static" / "venta_pos.js"

BROKEN_PATTERNS = [
    r'return\s+"<option\s+value=""\s*\+',  # comillas rotas historicas en filtrar
    r'return\s+"<option\s+value=""\s*\+\s*escVal',
]


def _node_check(js: str, label: str) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as t:
        t.write(js)
        path = t.name
    try:
        r = subprocess.run(
            ["node", "--check", path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0:
            print(f"FAIL {label}:\n{r.stderr}")
            sys.exit(1)
    except FileNotFoundError:
        print("WARN: node no instalado; omitiendo --check")
    finally:
        Path(path).unlink(missing_ok=True)


def _venta_get_template_chunk(text: str) -> str:
    """Solo el template GET de /venta (evita el primer return del POST)."""
    anchor = text.find("perf_venta_t0 = time.perf_counter()")
    if anchor == -1:
        print("FAIL: no se encontro ancla perf_venta_t0 en app.py")
        sys.exit(1)
    rel = text.find('return render_template_string(IOS + """', anchor)
    if rel == -1:
        print("FAIL: no se encontro return render_template_string GET de venta")
        sys.exit(1)
    open_tpl = text.find('"""', rel) + 3
    close_tpl = text.find('""",\n        lotteries=', open_tpl)
    if close_tpl == -1:
        print("FAIL: no se encontro cierre del template venta (lotteries=)")
        sys.exit(1)
    return text[open_tpl:close_tpl]


def _optional_prod_static(url: str, expect_marker: str) -> None:
    """Comprueba que el static servido en produccion incluye el marcador (sin auth)."""
    req = urllib.request.Request(
        url,
        headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print("WARN: no se pudo leer produccion:", url, e)
        return
    if expect_marker not in body:
        print("FAIL: produccion", url, "no contiene marcador:", repr(expect_marker))
        print("      Subir commit con static/venta_pos.js o invalidar cache (Ctrl+F5, incognito, SW).")
        sys.exit(1)
    print("OK: produccion static coincide:", url)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check-prod-static",
        metavar="URL",
        nargs="?",
        const="https://banca-la-que-nunca-falla.onrender.com/static/venta_pos.js",
        help="Verifica que el venta_pos.js servido incluye _ventaReadJsonEl.",
    )
    args = ap.parse_args()

    if not APP.is_file():
        print("FAIL: no existe", APP)
        sys.exit(1)
    text = APP.read_text(encoding="utf-8")

    for pat in BROKEN_PATTERNS:
        if re.search(pat, text):
            print("FAIL: patron JS roto en app.py:", pat)
            sys.exit(1)

    if not VENTA_JS.is_file():
        print("FAIL: falta", VENTA_JS)
        sys.exit(1)

    venta_js = VENTA_JS.read_text(encoding="utf-8")
    for pat in BROKEN_PATTERNS:
        if re.search(pat, venta_js):
            print("FAIL: patron JS roto en venta_pos.js:", pat)
            sys.exit(1)

    _node_check(venta_js, "static/venta_pos.js")

    chunk = _venta_get_template_chunk(text)

    if '<script src="' not in chunk or "venta_pos.js" not in chunk:
        print("FAIL: template /venta no referencia <script src=...venta_pos.js>")
        sys.exit(1)
    if 'id="venta-lotteries-json"' not in chunk or "<textarea" not in chunk:
        print("FAIL: template /venta debe usar <textarea id=venta-lotteries-json> para JSON")
        sys.exit(1)
    if '<script type="application/json" id="venta-lotteries-json">' in chunk:
        print("FAIL: aun existe script application/json para loterias")
        sys.exit(1)
    if "_ventaReadJsonEl" not in venta_js:
        print("FAIL: venta_pos.js debe definir _ventaReadJsonEl")
        sys.exit(1)

    for m in re.finditer(
        r"<script(?![^>]*application/json)(?![^>]*\bsrc=)[^>]*>(.*?)</script>",
        chunk,
        re.DOTALL | re.IGNORECASE,
    ):
        body = m.group(1).strip()
        if body:
            _node_check(body, "inline script en template venta")

    print("OK: validate_venta_js")

    if args.check_prod_static is not None:
        _optional_prod_static(args.check_prod_static, "_ventaReadJsonEl")


if __name__ == "__main__":
    main()
