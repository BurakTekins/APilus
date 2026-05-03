# syntax=docker/dockerfile:1.7
#
# Multi-stage build for the APilus Django backend.
#
# Layer-caching strategy:
#   1. System build deps (rarely change)
#   2. Lockfile + pyproject.toml only -> install Python deps (rebuilt only when deps change)
#   3. Application source code (changes most often, lands in its own thin layer)
#
# Build context is the project root (see docker-compose.yml: context: .).

ARG PYTHON_VERSION=3.12

# ---------- builder stage ----------
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# Build-time system deps for compiling psycopg2 / wheels with native extensions.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast resolver/installer that respects uv.lock).
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /usr/local/bin/

WORKDIR /app

# --- Dependency layer (cached unless pyproject.toml or uv.lock changes) ---
# Copy ONLY the dep manifests so this layer is reused across code-only edits.
COPY pyproject.toml uv.lock ./

# Sync the locked dependency set into /opt/venv.
# --frozen: fail if uv.lock is out of date instead of silently re-resolving.
# --no-install-project: do not try to install the local project (no source yet).
# --no-dev: production install, skip the [dependency-groups].dev group.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev


# ---------- runtime stage ----------
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings

# Runtime-only system deps: libpq5 is the shared library psycopg2 links against.
# gcc / libpq-dev / build-essential are intentionally NOT installed here -> smaller, safer image.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid app --create-home app

# Bring in the pre-built virtualenv from the builder stage.
COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# --- Application source (last layer; changes most often) ---
COPY --chown=app:app backend/ /app/

COPY --chown=app:app scraper_and_data/ /app/scraper_and_data/

RUN mkdir -p /app/RAG && chown -R app:app /app/RAG

USER app

EXPOSE 8000

# Default command. docker-compose overrides this for the dev stack
# (running migrate + runserver). For standalone use, serve via uvicorn ASGI.
CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
