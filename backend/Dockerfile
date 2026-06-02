FROM python:3.12-slim AS builder
WORKDIR /app
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libpq-dev \
 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
# libpq5 needed by asyncpg/psycopg at runtime; keep image lean
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 \
 && rm -rf /var/lib/apt/lists/* \
 && useradd -m -u 1000 app
# Copy installed packages + their console scripts from builder.
# Deps live in the system site-packages so `python -m uvicorn` works without
# PYTHONPATH gymnastics (resilient to ECS task-definition env overrides).
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --chown=app:app . .
USER app
EXPOSE 8000
# Trust X-Forwarded-For from the ALB so rate-limit / logging see the real
# client IP, not the LB. Set FORWARDED_ALLOW_IPS=<ALB-subnet-CIDR> in the
# ECS task-def for production. Defaults to "*" for dev / docker-compose.
ENV FORWARDED_ALLOW_IPS="*"
CMD ["sh", "-c", "exec python -m uvicorn main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=\"${FORWARDED_ALLOW_IPS}\""]
