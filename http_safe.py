# -*- coding: utf-8 -*-
"""HTTP helpers: timeouts, logging resumido y sin tumbar Flask."""
from __future__ import annotations

import logging
import traceback

import requests

log = logging.getLogger(__name__)

DEFAULT_HTTP_TIMEOUT = (10, 20)


def _exc_summary(exc: BaseException | None) -> str:
    if exc is None:
        return ""
    return "%s: %s" % (type(exc).__name__, str(exc)[:240])


def _traceback_brief(exc: BaseException | None, limit: int = 4) -> str:
    if exc is None:
        return ""
    lines = traceback.format_exception(type(exc), exc, exc.__traceback__, limit=limit)
    text = "".join(lines).strip()
    if len(text) > 900:
        text = text[:900] + "…"
    return text.replace("\n", " | ")


def log_http_failure(method, url, *, exc=None, status_code=None, timeout=DEFAULT_HTTP_TIMEOUT):
    log.warning(
        "[HTTP_FAIL] method=%s url=%s timeout=%s status=%s err=%s tb=%s",
        method,
        url,
        timeout,
        status_code,
        _exc_summary(exc),
        _traceback_brief(exc),
    )


def safe_requests_get(url, timeout=DEFAULT_HTTP_TIMEOUT, **kwargs):
    try:
        return requests.get(url, timeout=timeout, **kwargs)
    except Exception as exc:
        log_http_failure("GET", url, exc=exc, timeout=timeout)
        return None


def safe_requests_post(url, timeout=DEFAULT_HTTP_TIMEOUT, **kwargs):
    try:
        return requests.post(url, timeout=timeout, **kwargs)
    except Exception as exc:
        log_http_failure("POST", url, exc=exc, timeout=timeout)
        return None
