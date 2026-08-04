#!/bin/sh
# Daily 8:00 Beijing:抓 PubMed 最近两天 + LLM 分类 + 入库 + rebuild Astro
set -e

LOG=/var/log/cron.log
# 回看两天而不是只抓前一天:PubMed 的 [epdat] 是陆续打上的,
# 早上 8:00 检索"昨天"只能拿到当时已入库的部分,当天晚些时候才索引的文献
# 以后永远不会再被查到。实测 08-04 08:00 查 08-03 得 2 篇,同日 13:50 再查得 4 篇。
# 重跑历史日期是安全的:run_daily step 6 按 epdat 从库里重建 snapshot,不会抹数据。
FROM=$(TZ=Asia/Shanghai date -d '2 days ago' +%Y-%m-%d)
TO=$(TZ=Asia/Shanghai date -d 'yesterday' +%Y-%m-%d)

echo "[$(date '+%Y-%m-%d %H:%M:%S')] daily.sh started (range=${FROM}..${TO})" >> "$LOG"

# 1. 抓 PubMed + LLM + 入库(防污染过滤已在 pipeline/daily.py 内置)
# 本容器只有 Node,没有 Python 解释器,交给 api 容器执行:
# /api/backfill 内部就是 run_daily,与 `python -m thoracic.pipeline.daily` 等价。
# concurrency=1 必须显式指定(默认 3):两天并发跑时各自持有独立 DB 连接,
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