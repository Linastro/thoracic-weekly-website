"""写每日 JSON snapshot(供 Astro 构建期读取)。"""

from __future__ import annotations
import json
from datetime import date as _date, datetime, timezone
from pathlib import Path

from thoracic.config import settings


def write_daily_snapshot(target_date, records: list[dict], base_dir: str | None = None) -> Path:
    """写 `/data/snapshots/YYYY-MM-DD.json` 或 `SNAPSHOT_DIR/YYYY-MM-DD.json`。

    Args:
        target_date: date 对象
        records: 列表,每条应是 upsert 后的 article dict(包含 pmid/title/title_zh/abstract/authors/affiliations/journal/journal_full/journal_abbr/doi/publication_types/pubdate/epdat/disease/type/impact_factor/jcr_quartile/new_talent_quartile)
        base_dir: 覆盖 settings.SNAPSHOT_DIR(默认)

    Returns:
        写入的 Path
    """
    base = Path(base_dir or settings.SNAPSHOT_DIR)
    base.mkdir(parents=True, exist_ok=True)
    out_path = base / f"{target_date.isoformat()}.json"
    payload = {
        "date": target_date.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "article_count": len(records),
        "articles": records,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def read_daily_snapshot(target_date, base_dir: str | None = None) -> dict | None:
    """读 snapshot(供 Phase A 第 7 步 API 与第 10 步 Astro 使用);不存在返回 None。"""
    from datetime import date as _date
    if isinstance(target_date, str):
        target_date = _date.fromisoformat(target_date)
    base = Path(base_dir or settings.SNAPSHOT_DIR)
    p = base / f"{target_date.isoformat()}.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def list_snapshots(base_dir: str | None = None) -> list[str]:
    """列出所有 snapshot 日期(YYYY-MM-DD),倒序。"""
    base = Path(base_dir or settings.SNAPSHOT_DIR)
    if not base.is_dir():
        return []
    return sorted([p.stem for p in base.glob("*.json")], reverse=True)
