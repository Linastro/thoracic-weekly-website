# syntax=docker/dockerfile:1.7
# Stage 1 — install Python dependencies with uv
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
    uv sync --frozen --no-dev --no-editable --package thoracic-server-api || \
    UV_HTTP_TIMEOUT=180 uv sync --no-dev --no-editable --package thoracic-server-api

# Stage 2 — runtime image
# Phase B 2nd fix:用 node:22-bookworm-slim 替代 python:3.12-slim + apt 装 nodejs/npm(避免 OOM)
# node:22-bookworm-slim 内置 Node.js 22 + npm + python3(debian base)
# 只需 apt 装 4 个小包(curl/tini/ca-certificates/super-cronic)
FROM node:22-bookworm-slim AS runtime
# Phase B 5th fix:不要 tini(与 node:22-bookworm-slim glibc 兼容问题导致 fork exec 失败)
# entrypoint.sh 末尾 exec supercronic 让 supercronic 直接接管 PID 1
# tini 可选:作为 zombie reaper,但 supercronic 自己处理 signal,不需要 tini
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH=/app

RUN apt-get update \
 # Phase B 5th fix:去掉 tini,supercronic 自己当 PID 1(tini fork exec 失败)
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && curl -fsSL https://github.com/aptible/supercronic/releases/download/v0.2.33/supercronic-linux-amd64 \
        -o /usr/local/bin/supercronic \
 && chmod +x /usr/local/bin/supercronic

WORKDIR /app
COPY --from=uv /build/.venv /app/.venv
# Phase B fix:uv 0.9.30 venv launcher shebang 写死 /build/.venv/bin/python,运行时不存在
# 运行时必须用 venv 自己的 Python(/app/.venv/bin/python),才能找到 site-packages
RUN find /app/.venv/bin -type f -exec sed -i 's|#!/build/.venv/bin/python|#!/app/.venv/bin/python|' {} +
COPY api ./api

# ==== web 源码(供 cron 容器 build Astro 静态站点) ====
COPY web /app/web_src
RUN cd /app/web_src && \
    # .dockerignore 排除了 web/data,创建空目录以便 symlink
    mkdir -p /app/web_src/data && \
    npm install --no-audit --no-fund && \
    # web/data/snapshots 是 host 上的 symlink → /tmp/.../snapshots
    # 在容器内需要重定向到 /data/snapshots(thoracic-data volume mount)
    rm -f /app/web_src/data/snapshots && \
    ln -s /data/snapshots /app/web_src/data/snapshots

# crontab
COPY cron/crontab /etc/crontab

# cron_jobs 脚本(supercronic 调用)
COPY cron/cron_jobs /app/cron_jobs
RUN chmod +x /app/cron_jobs/*.sh

# entrypoint: 启动时若 web_dist 名为 volume 为空,先 build 一次让 nginx 有内容可服务
COPY cron/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN mkdir -p /var/log
VOLUME ["/data", "/var/log"]

# Phase B 5th fix:直接让 entrypoint.sh 跑(去掉 tini,supercronic 自己当 PID 1)
# tini 0.19.0 与 node:22-bookworm-slim 的 glibc 有 fork exec 兼容问题
# entrypoint.sh 末尾 exec supercronic /etc/crontab,supercronic 接管 PID 1
ENTRYPOINT ["/entrypoint.sh"]
CMD ["supercronic", "/etc/crontab"]