FROM python:3.12-slim AS builder
WORKDIR /app
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libpq-dev \
 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --target=/deps -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app:/deps \
    PATH="/deps/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
# libpq5 needed by asyncpg/psycopg at runtime; keep image lean
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 \
 && rm -rf /var/lib/apt/lists/* \
 && useradd -m -u 1000 app
COPY --from=builder /deps /deps
COPY --chown=app:app . .
USER app
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
