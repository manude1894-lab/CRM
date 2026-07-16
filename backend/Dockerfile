FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for psycopg2, bcrypt, reportlab
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# On startup: run migrations, create admin user only (no dummy data), then serve.
# PORT env var is set by Railway; falls back to 8000 for local Docker Compose.
CMD ["sh", "-c", "alembic upgrade head && python -m app.seed --minimal && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
