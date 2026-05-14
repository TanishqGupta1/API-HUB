#!/bin/sh
# Container entrypoint — auto-seeds demo data + ensures default admin before
# launching uvicorn. Idempotent: every restart is safe. Disable with AUTO_SEED=0.
set -e

if [ "${AUTO_SEED:-1}" = "1" ]; then
  echo "[bootstrap] running seed_demo.py …"
  python seed_demo.py || echo "[bootstrap] seed_demo failed (continuing)"

  echo "[bootstrap] ensuring default admin user …"
  python - <<'PY' || echo "[bootstrap] admin bootstrap skipped"
import asyncio, os, sys
import modules.auth.models, modules.customers.models, modules.suppliers.models
import modules.catalog.models, modules.markup.models, modules.push_log.models
import modules.master_options.models
from sqlalchemy import select
from database import async_session
from modules.auth.models import User
from modules.auth.security import hash_password

EMAIL = os.getenv("DEMO_ADMIN_EMAIL", "admin@example.com")
PASSWORD = os.getenv("DEMO_ADMIN_PASSWORD", "demo1234")

async def go():
    async with async_session() as db:
        if (await db.execute(select(User).where(User.email == EMAIL))).scalar_one_or_none():
            print(f"[bootstrap] admin {EMAIL} already exists")
            return
        db.add(User(email=EMAIL, hashed_password=hash_password(PASSWORD),
                    role="vg_admin", is_active=True))
        await db.commit()
        print(f"[bootstrap] admin created: {EMAIL} / {PASSWORD}")
asyncio.run(go())
PY
fi

echo "[bootstrap] launching uvicorn …"
if [ "${UVICORN_RELOAD:-0}" = "1" ]; then
  exec python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
else
  exec python -m uvicorn main:app --host 0.0.0.0 --port 8000
fi
