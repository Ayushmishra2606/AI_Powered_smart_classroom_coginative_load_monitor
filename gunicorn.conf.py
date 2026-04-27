"""
gunicorn.conf.py — Gunicorn WSGI server configuration for production.

Start with:
    gunicorn -c gunicorn.conf.py app:app
"""
import os

# ── Bind ──────────────────────────────────────────────────────────────────────
# Render injects PORT automatically; fall back to 10000 (Render's default)
port   = int(os.environ.get('PORT', 10000))
bind   = f'0.0.0.0:{port}'

# ── Workers ───────────────────────────────────────────────────────────────────
# SSE / MJPEG streaming requires threaded workers.
# Using gevent for non-blocking I/O (SSE streams, camera feeds).
worker_class = 'gevent'
workers      = 1          # Free tier: 1 worker to stay within 512 MB RAM
threads      = 4          # 4 threads per worker handles concurrent SSE connections
worker_connections = 100

# ── Timeouts ──────────────────────────────────────────────────────────────────
timeout          = 120    # SSE connections are long-lived; keep generous timeout
keepalive        = 5
graceful_timeout = 30

# ── Logging ───────────────────────────────────────────────────────────────────
accesslog  = '-'          # stdout — Render captures this
errorlog   = '-'          # stderr
loglevel   = os.environ.get('LOG_LEVEL', 'info')
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(D)sµs'

# ── Process ───────────────────────────────────────────────────────────────────
preload_app  = True       # Load app before forking → catch startup errors early
daemon       = False      # Render manages the process; never daemonize
