# MyTeam360 — Copyright © 2026 Praxis Holdings LLC. All rights reserved.
FROM python:3.12-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Create data directory for SQLite + encryption key
RUN mkdir -p /app/data && chmod 700 /app/data

# Non-root user
RUN useradd -m mt360 && chown -R mt360:mt360 /app
USER mt360

ENV PORT=8000
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production server
# gunicorn_conf.py handles --preload + post_fork hook to reset the PG pool
# so each worker gets its own fork-safe connections.
CMD ["gunicorn", "-c", "gunicorn_conf.py", "app:app"]
