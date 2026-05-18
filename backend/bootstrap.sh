#!/bin/sh
# Container entrypoint — auto-seeds demo data + ensures default admin before
# launching uvicorn. Idempotent: every restart is safe. Disable with AUTO_SEED=0.
set -e

# Admin user seeding moved into FastAPI lifespan (modules.auth.seed.
# ensure_default_admin) so it runs after Base.metadata.create_all. The
# inline python block here used to fire before tables existed and
# silently failed.
if [ "${AUTO_SEED:-1}" = "1" ]; then
  echo "[bootstrap] running seed_demo.py …"
  python seed_demo.py || echo "[bootstrap] seed_demo failed (continuing)"
fi

echo "[bootstrap] launching uvicorn …"
if [ "${UVICORN_RELOAD:-0}" = "1" ]; then
  exec python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
else
  exec python -m uvicorn main:app --host 0.0.0.0 --port 8000
fi
