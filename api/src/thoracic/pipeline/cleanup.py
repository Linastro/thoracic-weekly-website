"""清理 N 天前的 snapshot JSON(保留 SQLite 数据)。"""

from __future__ import annotations
import argparse
import logging
from datetime import date, timedelta
from pathlib import Path

from thoracic.config import settings

log = logging.getLogger(__name__)


def cleanup_old_snapshots(older_than_days: int = 180, base_dir: str | None = None) -> int:
    """删除 N 天前的 snapshot JSON 文件;返回删除数。"""
    base = Path(base_dir or settings.SNAPSHOT_DIR)
    if not base.is_dir():
        return 0
    cutoff = date.today() - timedelta(days=older_than_days)
    removed = 0
    for p in base.glob("*.json"):
        try:
            stem_date = date.fromisoformat(p.stem)
        except ValueError:
            continue
        if stem_date < cutoff:
            p.unlink()
            removed += 1
    return removed


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--older-than", type=int, default=180)
    args = parser.parse_args()
    n = cleanup_old_snapshots(args.older_than)
    print(f"removed {n} snapshot files older than {args.older_than} days")


if __name__ == "__main__":
    main()
