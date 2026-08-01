#!/bin/sh
# Container 启动时:首次 build Astro(让 web_dist 立即有内容供 nginx 服务)
set -e

LOG=/var/log/cron.log
echo "[$(date '+%Y-%m-%d %H:%M:%S')] initial_build.sh started" >> "$LOG"

cd /app/web_src
npm run build >> "$LOG" 2>&1
cp -R dist/. /app/web_dist/ >> "$LOG" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] initial_build.sh completed" >> "$LOG"