#!/bin/sh
set -e

echo "Running database migrations..."
python -c "from main import _run_alembic_upgrade; _run_alembic_upgrade()"

echo "Starting application..."
exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
