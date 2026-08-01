#!/bin/sh
set -e

# Phase B fix:runtime 是 node:22-bookworm-slim,无 bash,用 sh
# supercronic 不支持 @reboot 行,initial build 完全由 entrypoint.sh 做

# 启动时:若 web_dist 为空,先 build 一次让 nginx 有内容可服务。
if [ ! -f /app/web_dist/index.html ]; then
    echo "[entrypoint] web_dist empty, running initial build..."
    cd /app/web_src && npm run build && cp -R dist/. /app/web_dist/
fi

# 执行 supercronic(由 docker-compose.yml 的 command 传入)
exec "$@"
