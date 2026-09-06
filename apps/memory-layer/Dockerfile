FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY db ./db

EXPOSE 8002

# Postgres migrations (db/migrations) run lazily on first request, inside
# composition.py -- no separate migrate step needed here, unlike core-api's
# alembic upgrade (see README.md).
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8002"]
