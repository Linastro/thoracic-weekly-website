#!/bin/sh
# Daily 14:00 Beijing:抓 PubMed 前一个完整入库日 + LLM 分类 + 入库 + rebuild Astro
set -e

LOG=/var/log/cron.log
# 检索口径为 [edat](PubMed 入库日):入库日封口后永不再变,单日检索即完整,
# 无需像 [epdat](电子出版日)那样回看两天补索引延迟。
# 运行于北京 14:00(= 美东凌晨,入库日翻页后 1-2 小时),TARGET=美东"昨天"
# = 前一个已封口的完整入库日(美东昨天 = 北京昨天中午到今天中午进库的那批)。
# 重跑历史日期是安全的:run_daily step 6 按 epdat 从库里重建 snapshot,不会抹数据。
TARGET=$(TZ=America/New_York date -d 'yesterday' +%Y-%m-%d)
FROM=$TARGET
TO=$TARGET

echo "[$(date '+%Y-%m-%d %H:%M:%S')] daily.sh started (range=${FROM}..${TO})" >> "$LOG"

# 1. 抓 PubMed + LLM + 入库(防污染过滤已在 pipeline/daily.py 内置)
# 本容器只有 Node,没有 Python 解释器,交给 api 容器执行:
# /api/backfill 内部就是 run_daily,与 `python -m thoracic.pipeline.daily` 等价。
# concurrency=1 必须显式指定(默认 3):多日并发跑时各自持有独立 DB 连接,
# 若都命中同一个 epdat 就会同时重建同一个 snapshot JSON,后写者看不到前者未提交的行 → 丢数据。
curl -fsS -X POST http://api:8080/api/backfill \
    -H "Authorization: Bearer ${REGEN_TOKEN}" \
    -H 'Content-Type: application/json' \
    --max-time 3600 \
    -d "{\"from_date\":\"${FROM}\",\"to_date\":\"${TO}\",\"concurrency\":1}" >> "$LOG" 2>&1

# 2. rebuild Astro(让 web 容器读到最新 dist)
cd /app/web_src
npm run build >> "$LOG" 2>&1
cp -R dist/. /app/web_dist/ >> "$LOG" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] daily.sh completed" >> "$LOG"