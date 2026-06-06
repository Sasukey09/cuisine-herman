#!/bin/sh
set -e

# Apply migrations, retrying while the database finishes starting up.
# (idempotent: alembic only runs not-yet-applied revisions)
echo "[entrypoint] Running database migrations..."
n=0
until alembic upgrade head; do
  n=$((n + 1))
  if [ "$n" -ge 10 ]; then
    echo "[entrypoint] migrations failed after 10 attempts" >&2
    exit 1
  fi
  echo "[entrypoint] database not ready, retry $n/10 in 3s..."
  sleep 3
done

# Hand off to the container command (gunicorn in prod, uvicorn --reload in dev).
echo "[entrypoint] Starting: $*"
exec "$@"
