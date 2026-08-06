# syntax=docker/dockerfile:1.7
# Stage 1 — install dependencies with uv (cached layer)
# Phase B fix:uv:0.6.6 是 scratch 镜像无 /bin/sh,改用 python3.12-bookworm-slim(自带 shell + uv 0.9.30)
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS uv
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /build
COPY pyproject.toml uv.lock* ./
COPY api/pyproject.toml ./api/pyproject.toml
# setuptools 需要 api/src 存在才能识别 thoracic 包
COPY api/src ./api/src
RUN --mount=type=cache,target=/root/.cache/uv \
    # Phase B 4th fix:阿里云服务器访问 PyPI 慢,uv 默认 30s 超时不够
    UV_HTTP_TIMEOUT=180 \
    # --no-editable:把 thoracic 装到 site-packages(.pth 路径错配导致 ModuleNotFoundError)
    # --reinstall-package:版本号不变时 uv 会复用缓存的第一方 wheel,源码改动将静默不生效。
    # 承载 thoracic 代码的是根项目 thoracic-server,thoracic-server-api 只是 workspace 入口。
    uv sync --frozen --no-dev --no-editable \
        --reinstall-package thoracic-server --reinstall-package thoracic-server-api \
        --package thoracic-server-api || \
    UV_HTTP_TIMEOUT=180 uv sync --no-dev --no-editable \
        --reinstall-package thoracic-server --reinstall-package thoracic-server-api \
        --package thoracic-server-api

# Stage 2 — runtime image
FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH=/app \
    THORACIC_METRICS_PATH=/app/journal_metrics.json

# 国内 ECS 上 deb.debian.org 访问极慢/被卡,apt 源换阿里云镜像
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources \
 && apt-get update \
 && apt-get install -y --no-install-recommends curl tini ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=uv /build/.venv /app/.venv
# Phase B fix:uv 0.9.30 venv launcher shebang 写死 /build/.venv/bin/python(构建路径,运行时不存在)
# 运行时必须用 venv 自己的 Python(/app/.venv/bin/python),才能找到 site-packages
RUN find /app/.venv/bin -type f -exec sed -i 's|#!/build/.venv/bin/python|#!/app/.venv/bin/python|' {} +
COPY api ./api
COPY journal_metrics.json ./journal_metrics.json

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8080/api/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "thoracic.main:app", "--host", "0.0.0.0", "--port", "8080"]
