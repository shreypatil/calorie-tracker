FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# Dependencies are installed from the manifest alone, so editing application
# code does not invalidate this layer.
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts
COPY app ./app

# Run as a non-root user; the data volume must be writable by it.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /srv/data \
    && chown -R appuser:appuser /srv
USER appuser

EXPOSE 8000

# Migrations run at startup so a fresh volume comes up with a current schema.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
