# syntax=docker/dockerfile:1.7
# Stage 1 — install dependencies with uv (cached layer)
FROM ghcr.io/astral-sh/uv:0.6.6 AS uv
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /build
COPY pyproject.toml uv.lock* ./
COPY api/pyproject.toml ./api/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package thoracic-server-api || \
    uv sync --no-dev --package thoracic-server-api

# Stage 2 — runtime image
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH=/app

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl tini ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && curl -fsSL https://github.com/aptible/supercronic/releases/download/v0.2.33/supercronic-linux-amd64 \
        -o /usr/local/bin/supercronic \
 && chmod +x /usr/local/bin/supercronic

WORKDIR /app
COPY --from=uv /build/.venv /app/.venv
COPY api ./api
COPY cron/crontab /etc/crontab

RUN mkdir -p /var/log
VOLUME ["/data", "/var/log"]

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["supercronic", "/etc/crontab"]
