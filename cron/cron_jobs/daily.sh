#!/bin/sh
# Daily 8:00 Beijing:抓 PubMed 前一天 + LLM 分类 + 入库 + rebuild Astro
set -e

LOG=/var/log/cron.log
TARGET=$(TZ=Asia/Shanghai date -d 'yesterday' +%Y-%m-%d)

echo "[$(date '+%Y-%m-%d %H:%M:%S')] daily.sh started (target=${TARGET})" >> "$LOG"

# 1. 抓 PubMed + LLM + 入库(防污染过滤已在 pipeline/daily.py 内置)
# 本容器只有 Node,没有 Python 解释器,交给 api 容器执行:
# /api/backfill 内部就是 run_daily,与 `python -m thoracic.pipeline.daily` 等价。
curl -fsS -X POST http://api:8080/api/backfill \
    -H "Authorization: Bearer ${REGEN_TOKEN}" \
    -H 'Content-Type: application/json' \
    --max-time 3600 \
    -d "{\"from_date\":\"${TARGET}\",\"to_date\":\"${TARGET}\"}" >> "$LOG" 2>&1

# 2. rebuild Astro(让 web 容器读到最新 dist)
cd /app/web_src
npm run build >> "$LOG" 2>&1
cp -R dist/. /app/web_dist/ >> "$LOG" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] daily.sh completed" >> "$LOG"