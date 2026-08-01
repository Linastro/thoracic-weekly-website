#!/bin/sh
# Weekly cleanup:删除 180 天前的 snapshot JSON(保留 SQLite 数据)
set -e

LOG=/var/log/cron.log
echo "[$(date '+%Y-%m-%d %H:%M:%S')] cleanup.sh started" >> "$LOG"

cd /app
python -m thoracic.pipeline.cleanup --older-than 180 >> "$LOG" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] cleanup.sh completed" >> "$LOG"