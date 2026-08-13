#!/bin/sh
# Weekly 周一北京 19:00:生成"上一周"(上周一~上周日)的胸外文献周报并更新站点
# 周报统计口径按文章自身的入库日(edat,存于 articles.epdat 列)分组,区间含头含尾。
# 本容器只有 Node,没有 Python 解释器,交给 api 容器执行:/api/weekly 内部生成周报。
set -e

LOG=/var/log/cron.log
# cron 固定周一(0 19 * * 1)触发,所以直接以"今天"为准算上一自然周:
#   WEEK_END   = 昨天 = 上周日(周报区间右端点)
#   WEEK_START = 7 天前 = 上周一(周报区间左端点)
# 例:周一 2026-08-17 触发 → yesterday=2026-08-16(周日)、7 天前=2026-08-10(周一),区间 8-10~8-16。
WEEK_END=$(date -d 'yesterday' +%F)
WEEK_START=$(date -d '7 days ago' +%F)

echo "[$(date '+%Y-%m-%d %H:%M:%S')] weekly.sh started (range=${WEEK_START}..${WEEK_END})" >> "$LOG"

# 1. 生成周报(LLM 汇总上周文献,落在 snapshot/周报数据里)
# 选周一而非周日:周日当天入库的文献要等周一北京 14:00 的 daily 抓取后才齐全,
# 周一 19:00 触发时上一自然周(周一~周日)的入库文献已全部入库、口径完整。
# REGEN_TOKEN 由 cron 服务 environment 注入,与 daily.sh 一致。
curl -fsS -X POST http://api:8080/api/weekly \
    -H "Authorization: Bearer ${REGEN_TOKEN}" \
    -H 'Content-Type: application/json' \
    --max-time 3600 \
    -d "{\"week_start\":\"${WEEK_START}\",\"week_end\":\"${WEEK_END}\"}" >> "$LOG" 2>&1

# 2. rebuild Astro(让 web 容器读到最新 dist)
# 之前不在此 build、靠次日 daily 14:00 顺带发布;现在按用户要求改为内容更新后立即更新站点。
# 周一 19:00 与 daily 14:00 相隔 5 小时无并发,单次 build 与 daily 同款、内存安全(1.6G 机器上可用)。
cd /app/web_src
npm run build >> "$LOG" 2>&1
cp -R dist/. /app/web_dist/ >> "$LOG" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] weekly.sh completed" >> "$LOG"
