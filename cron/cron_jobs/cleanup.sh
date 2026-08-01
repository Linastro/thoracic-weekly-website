#!/bin/sh
# Weekly cleanup:删除 180 天前的 snapshot JSON(保留 SQLite 数据)
set -e

LOG=/var/log/cron.log
echo "[$(date '+%Y-%m-%d %H:%M:%S')] cleanup.sh started" >> "$LOG"

# 本容器无 Python 解释器,用 shell 等价实现 pipeline.cleanup:
# snapshot 文件名是 YYYY-MM-DD,该格式下字典序比较即日期比较。
DIR=${SNAPSHOT_DIR:-/data/snapshots}
CUTOFF=$(date -d '180 days ago' +%Y-%m-%d)
REMOVED=0

for f in "$DIR"/*.json; do
    [ -f "$f" ] || continue
    STEM=$(basename "$f" .json)
    case "$STEM" in
        [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]) ;;
        *) continue ;;
    esac
    if [ "$STEM" \< "$CUTOFF" ]; then
        rm -f "$f"
        REMOVED=$((REMOVED + 1))
    fi
done

echo "removed ${REMOVED} snapshot files older than ${CUTOFF}" >> "$LOG"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] cleanup.sh completed" >> "$LOG"
