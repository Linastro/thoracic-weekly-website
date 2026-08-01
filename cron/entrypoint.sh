#!/bin/sh
set -e

# Phase B fix:runtime 是 node:22-bookworm-slim,无 bash,用 sh
# supercronic 不支持 @reboot 行,initial build 完全由 entrypoint.sh 做

# 不能用 index.html 判断产物是否就绪:web_dist 这个 named volume 也挂给 nginx 的
# /usr/share/nginx/html,docker 会把 nginx 镜像自带的默认欢迎页灌进空 volume。
STAMP=/app/web_dist/.astro_build_ok

if [ ! -f "$STAMP" ]; then
    echo "[entrypoint] no build stamp, running initial build..."
    cd /app/web_src && npm run build
    rm -f /app/web_dist/index.html /app/web_dist/50x.html
    cp -R dist/. /app/web_dist/
    date -u '+%Y-%m-%dT%H:%M:%SZ' > "$STAMP"
    echo "[entrypoint] initial build done"
fi

# 执行 supercronic(由 docker-compose.yml 的 command 传入)
exec "$@"
