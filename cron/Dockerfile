# syntax=docker/dockerfile:1.7
# cron 容器只负责调度:Astro 构建(Node)+ 触发 api 跑 Python 流水线(curl)。
# Phase B 2nd fix:用 node:22-bookworm-slim 替代 python:3.12-slim + apt 装 nodejs/npm(避免 OOM)
# 只需 apt 装 2 个小包(curl / ca-certificates),supercronic 直接下二进制
FROM node:22-bookworm-slim AS runtime
# PID 1 由 compose 的 init: true(docker 自带 init)提供,镜像内不装 tini。
# supercronic 一旦自己成为 PID 1 就启用 reaper,而该 reaper fork exec 失败会让进程 fatal 退出。
# 本容器不跑 Python:daily.sh 通过 curl 调 api 的 /api/backfill 执行流水线。

# 国内 ECS 上 github release 直连下载极慢,经 gh-proxy.com 代理(~100x 提速)；apt 源换阿里云镜像
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources \
 && apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && curl -fsSL https://gh-proxy.com/https://github.com/aptible/supercronic/releases/download/v0.2.33/supercronic-linux-amd64 \
        -o /usr/local/bin/supercronic \
 && chmod +x /usr/local/bin/supercronic

WORKDIR /app
# journals.ts 从 web_src/src/lib 向上三级解析到 /app/journal_metrics.json
COPY journal_metrics.json ./journal_metrics.json

# ==== web 源码(供 cron 容器 build Astro 静态站点) ====
COPY web /app/web_src
RUN cd /app/web_src && \
    # .dockerignore 排除了 web/data,创建空目录以便 symlink
    mkdir -p /app/web_src/data && \
    npm install --no-audit --no-fund --registry=https://registry.npmmirror.com && \
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

# entrypoint.sh 先做首次 Astro build,再 exec 传入的 command。
# PID 1 归 compose init: true,supercronic 因此不会启用会崩的 reaper。
ENTRYPOINT ["/entrypoint.sh"]
CMD ["supercronic", "/etc/crontab"]