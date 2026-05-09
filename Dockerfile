# =============================================================================
# MeliCrowd — imagem única usada por api, ui e orchestrator.
# A escolha do entrypoint é feita pelo `command` no docker-compose.yml.
# =============================================================================

FROM python:3.11-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_VERSION=1.8.5 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

# System deps. curl is used by healthchecks; libpq-dev for psycopg2 (alembic sync driver).
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libpq-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

# -----------------------------------------------------------------------------
# Dependency layer (cached aggressively).
# -----------------------------------------------------------------------------
COPY pyproject.toml ./
# We copy poetry.lock if present; otherwise poetry will resolve from pyproject only.
COPY poetry.loc[k] ./

# psycopg2-binary needed only by alembic sync engine (not in pyproject by default —
# we add it here to keep production deps lean).
RUN poetry install --only main --no-root \
    && pip install "psycopg2-binary==2.9.10"

# -----------------------------------------------------------------------------
# Source layer (changes most often).
# -----------------------------------------------------------------------------
COPY README.md ./
COPY src/ ./src/
COPY infra/ ./infra/
COPY alembic.ini ./

# Install the project itself (so `melicrowd` CLI is available).
RUN poetry install --only main

# -----------------------------------------------------------------------------
# Runtime defaults
# -----------------------------------------------------------------------------
EXPOSE 8101 8501 9091

# Default command runs the orchestrator. Compose overrides this per service.
CMD ["python", "-m", "melicrowd.orchestrator.main"]
