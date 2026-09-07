FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY db ./db
COPY scripts ./scripts

RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /usr/sbin/nologin -M appuser && \
    chown -R appuser:appgroup /app
USER 10001:10001

EXPOSE 8002

# Postgres migrations (db/migrations) run via the standalone
# memory-layer-migration-runner compose service (scripts/run_migrations.py),
# completing before this service starts -- see docker-compose.yml.
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8002"]
