FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# Dependencies are installed from the manifest alone, so editing application
# code does not invalidate this layer.
COPY pyproject.toml ./
# The `ai` extra is installed here even though it is optional in pyproject: a deployed instance is
# expected to serve the AI features for real. Without it the app still runs, but silently falls back
# to the offline stub the moment a key is present — which is worse than failing.
RUN pip install --upgrade pip && pip install ".[ai]"

COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts
COPY app ./app

# Run as a non-root user; the data volume must be writable by it.
# Both mount points must exist in the image and be owned by appuser. A named volume inherits the
# ownership of the image directory it shadows — but only if that directory exists. /srv/logs was
# missing, so Docker created the volume root-owned and the non-root process could not write its
# log file, which failed the container's health check on first start.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /srv/data /srv/logs \
    && chown -R appuser:appuser /srv
USER appuser

EXPOSE 8000

# Migrations run at startup so a fresh volume comes up with a current schema.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
