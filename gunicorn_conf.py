# MyTeam360 — Copyright © 2026 Praxis Holdings LLC. All rights reserved.
"""Gunicorn configuration — loaded via  gunicorn -c gunicorn_conf.py app:app"""

import os

# ── Server socket ──────────────────────────────────────────
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"

# ── Workers ────────────────────────────────────────────────
workers = int(os.getenv("WEB_CONCURRENCY", "4"))
threads = 2
timeout = 120
preload_app = True          # run init_database() once in master

# ── Logging ────────────────────────────────────────────────
accesslog = "-"
errorlog = "-"
loglevel = "info"


# ── Fork-safety hook ──────────────────────────────────────
def post_fork(server, worker):
    """Ensure each worker starts with a clean PG pool.

    psycopg2 connections opened in the master (during --preload) are NOT
    fork-safe.  init_database() already calls _reset_pg_pool(), but this
    hook is a safety net in case any import-time code touches the pool.
    """
    from core.database import _reset_pg_pool
    _reset_pg_pool()
    server.log.info(f"Worker {worker.pid} — PG pool reset (post-fork)")
