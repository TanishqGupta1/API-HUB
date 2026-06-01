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
# --proxy-headers + --forwarded-allow-ips makes uvicorn trust X-Forwarded-For
# from the ALB, so request.client.host and limiter.py's XFF parser see the
# real client IP instead of the load-balancer's. FORWARDED_ALLOW_IPS should
# be set to the ALB subnet CIDR in production (defaults to "*" for dev).
FORWARDED_ALLOW_IPS="${FORWARDED_ALLOW_IPS:-*}"
if [ "${UVICORN_RELOAD:-0}" = "1" ]; then
  exec python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload \
    --proxy-headers --forwarded-allow-ips="${FORWARDED_ALLOW_IPS}"
else
  exec python -m uvicorn main:app --host 0.0.0.0 --port 8000 \
    --proxy-headers --forwarded-allow-ips="${FORWARDED_ALLOW_IPS}"
fi
