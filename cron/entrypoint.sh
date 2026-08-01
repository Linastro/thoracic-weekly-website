#!/bin/bash
set -e

# 启动时:若 web_dist 为空,先 build 一次让 nginx 有内容可服务。
# 后续 supercronic @reboot 也会再 build 一次(daily 更新 snapshot 后)。
if [ ! -f /app/web_dist/index.html ]; then
    echo "[entrypoint] web_dist empty, running initial build..."
    cd /app/web_src && npm run build && cp -R dist/. /app/web_dist/
fi

# 执行原 CMD(supercronic)
exec "$@"
