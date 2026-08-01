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
 && apt-get install -y --no-install-recommends curl tini ca-certificates nodejs npm \
 && rm -rf /var/lib/apt/lists/* \
 && curl -fsSL https://github.com/aptible/supercronic/releases/download/v0.2.33/supercronic-linux-amd64 \
        -o /usr/local/bin/supercronic \
 && chmod +x /usr/local/bin/supercronic

WORKDIR /app
COPY --from=uv /build/.venv /app/.venv
COPY api ./api

# ==== NEW: web 源码(供 cron 容器 build Astro 静态站点) ====
# 注意: .dockerignore 排除了 web/node_modules,这里在镜像内 npm install
# 保留 node_modules 是因为 runtime 的 @reboot 与 daily 都需要它跑 `npm run build`
COPY web /app/web_src
RUN cd /app/web_src && npm install --no-audit --no-fund && \
    # web/data/snapshots 是 host 上的 symlink → /tmp/.../snapshots
    # 在容器内需要重定向到 /data/snapshots(thoracic-data volume mount)
    rm -f /app/web_src/data/snapshots && \
    ln -s /data/snapshots /app/web_src/data/snapshots

# crontab
COPY cron/crontab /etc/crontab

# entrypoint: 启动时若 web_dist 名为 volume 为空,先 build 一次让 nginx 有内容可服务
COPY cron/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN mkdir -p /var/log
VOLUME ["/data", "/var/log"]

ENTRYPOINT ["/entrypoint.sh"]
CMD ["supercronic", "/etc/crontab"]
