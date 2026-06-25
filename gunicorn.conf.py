"""Gunicorn defaults (auto-loaded when Render runs bare `gunicorn app:app`)."""
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"
timeout = 120
workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
worker_class = "gthread"
threads = int(os.environ.get("GUNICORN_THREADS", "4"))
