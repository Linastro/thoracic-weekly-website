"""从 DB 重新生成所有 snapshot JSON(权威源修复)。

Phase A 第 13 步:旧 snapshot 文件因多次 backfill + reclassify + retry 留下陈旧快照,
总数 72 篇 vs DB publish 65 篇,差 7 = 1 篇 excluded 误入 + 6 篇跨日重复。
此脚本从 SQLite 读所有 llm_excluded=0 的 publish articles,按 epdat 分组写新 snapshot。
不影响 pipeline.daily.py(只新建独立脚本,供运维一次性修复使用)。
"""
from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timezone
from pathlib import Path

import aiosqlite

# 显式指向开发机 DB,避免 settings 读到容器路径 /data/thoracic.db
DB_PATH = "/tmp/thoracic-data/thoracic.db"
SNAPSHOT_DIR = Path("/tmp/thoracic-data/snapshots")

# JSON 字段,需从字符串反序列化为 list
JSON_FIELDS = ("authors", "affiliations", "publication_types")

# snapshot payload 除 articles 外的固定字段
GENERATED_AT = "2026-08-01T00:00:00+00:00"


async def _fetch_publish_articles(conn: aiosqlite.Connection) -> list[dict]:
    """查所有 llm_excluded=0 的 articles,字段名与 writer.write_daily_snapshot 输出一致。"""
    cur = await conn.execute(
        """
        SELECT
            pmid, title, title_zh, abstract, abstract_zh,
            authors, affiliations, journal, journal_full, journal_abbr,
            doi, publication_types, pubdate, epdat, fetched_at,
            disease, type,
            llm_classified_at, llm_model, llm_excluded, llm_exclude_reason, llm_needs_review,
            impact_factor, jcr_quartile, new_talent_quartile, matched_jcr
        FROM articles
        WHERE llm_excluded = 0
        ORDER BY epdat ASC, fetched_at ASC
        """
    )
    rows = await cur.fetchall()
    return [dict(r) for r in rows]


def _deserialize_json_fields(row: dict) -> None:
    """原地把字符串字段反序列化为 list;失败回退为 []。"""
    for f in JSON_FIELDS:
        v = row.get(f)
        if isinstance(v, str) and v:
            try:
                row[f] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                row[f] = []
        elif v is None:
            row[f] = []


def _group_by_epdat(rows: list[dict]) -> dict[str, list[dict]]:
    """按 epdat 分组。"""
    groups: dict[str, list[dict]] = {}
    for r in rows:
        epdat = r.get("epdat")
        if not epdat:
            continue
        groups.setdefault(epdat, []).append(r)
    return groups


def _write_snapshot_file(date_str: str, articles: list[dict]) -> Path:
    """写单个 snapshot 文件,返回路径。"""
    path = SNAPSHOT_DIR / f"{date_str}.json"
    payload = {
        "date": date_str,
        "generated_at": GENERATED_AT,
        "article_count": len(articles),
        "articles": articles,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


async def main() -> None:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    try:
        rows = await _fetch_publish_articles(conn)
        for r in rows:
            _deserialize_json_fields(r)

        groups = _group_by_epdat(rows)
        total_articles = 0
        written_paths: list[Path] = []
        for epdat_str in sorted(groups.keys()):
            # 校验 epdat 字符串格式
            try:
                d = date.fromisoformat(epdat_str)
            except ValueError:
                print(f"  [skip] invalid epdat={epdat_str!r}")
                continue
            arts = groups[epdat_str]
            path = _write_snapshot_file(d.isoformat(), arts)
            written_paths.append(path)
            total_articles += len(arts)
            print(f"  wrote {path.name} ({len(arts)} articles)")

        print(
            f"\nTOTAL: {total_articles} articles across {len(written_paths)} dates "
            f"(expected 65 publish / 12 dates)"
        )
        assert total_articles == 65, f"expected 65 publish articles, got {total_articles}"
        assert len(written_paths) == 12, f"expected 12 snapshot files, got {len(written_paths)}"
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
