#!/bin/sh
# Weekly 周日北京 19:00:生成"上一周"(上周一~上周日)的胸外文献周报
# 周报统计口径按文章自身的入库日(edat,存于 articles.epdat 列)分组,区间含头含尾。
# 本容器只有 Node,没有 Python 解释器,交给 api 容器执行:/api/weekly 内部生成周报。
set -e

LOG=/var/log/cron.log
# cron 固定周日(0 19 * * 0)触发,所以:
#   WEEK_END   = 今天往前 7 天 = 上周日(周报区间右端点)
#   WEEK_START = 今天往前 13 天 = 上周一(周报区间左端点)
# 这样每次都是完整的"上一周",不依赖今天是不是周日。
WEEK_END=$(date -d '7 days ago' +%F)
WEEK_START=$(date -d '13 days ago' +%F)

echo "[$(date '+%Y-%m-%d %H:%M:%S')] weekly.sh started (range=${WEEK_START}..${WEEK_END})" >> "$LOG"

# 1. 生成周报(LLM 汇总上周文献,落在 snapshot/周报数据里)
# REGEN_TOKEN 由 cron 服务 environment 注入,与 daily.sh 一致。
curl -fsS -X POST http://api:8080/api/weekly \
    -H "Authorization: Bearer ${REGEN_TOKEN}" \
    -H 'Content-Type: application/json' \
    --max-time 3600 \
    -d "{\"week_start\":\"${WEEK_START}\",\"week_end\":\"${WEEK_END}\"}" >> "$LOG" 2>&1

# 2. 不在这里 rebuild Astro:发布靠次日 daily 14:00 现有的那次 build 顺带把周报页带出去,
#    省掉一次新增的服务器构建(1.6G 内存机器上 Astro build 会 OOM 卡死整机,已踩多次坑)。
#    若想当天上线周报,可手动在本机构建上传,但日常流程依赖 daily 顺带发布即可。

echo "[$(date '+%Y-%m-%d %H:%M:%S')] weekly.sh completed" >> "$LOG"
