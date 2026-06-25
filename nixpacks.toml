#!/usr/bin/env bash
# Render start script - --preload ensures health check responds quickly
exec gunicorn app:app --bind "0.0.0.0:${PORT:-10000}" --workers 1 --timeout 120 --preload
