"""重新跑 LLM 分类+翻译(不动 PubMed 抓取结果)。

使用场景:
- LLM provider 改变 / prompt 改变
- LLM 输出解析问题(如 think-block 未剥离)
- 模型升级后重新翻译

只重新分类已在 articles 表的 records;不动 daily_snapshots 元数据,但重写 snapshot JSON。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import date
from pathlib import Path

from thoracic.classify.classify import classify_and_translate_batch
from thoracic.config import settings
from thoracic.db.connection import close_db, get_db
from thoracic.snapshots.writer import write_daily_snapshot

log = logging.getLogger(__name__)
_JSON_FIELDS = ("publication_types", "authors", "affiliations")


def _deserialize_json_fields(record: dict) -> dict:
    """反序列化 articles 表中的 JSON array 字段。"""
    for field in _JSON_FIELDS:
        value = record.get(field)
        if isinstance(value, str):
            try:
                record[field] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                record[field] = []
        elif value is None:
            record[field] = []
    return record


def _load_snapshot_membership(
    snapshot_dates: list[str],
) -> dict[str, list[str]]:
    """读取现有 snapshot 的 PMID 顺序,确保重写时不按 epdat 错分批次。"""
    membership: dict[str, list[str]] = {}
    base = Path(settings.SNAPSHOT_DIR)
    for snapshot_date in snapshot_dates:
        path = base / f"{snapshot_date}.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            membership[snapshot_date] = [
                str(article["pmid"])
                for article in payload.get("articles", [])
                if article.get("pmid") is not None
            ]
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            log.warning("cannot read snapshot %s: %s", path, exc)
    return membership


async def _snapshot_dates_from_db(conn, target_dates: list[date] | None) -> list[str]:
    if target_dates:
        return sorted({target.isoformat() for target in target_dates})
    cursor = await conn.execute("SELECT date FROM daily_snapshots ORDER BY date")
    rows = await cursor.fetchall()
    await cursor.close()
    if rows:
        return [str(row["date"]) for row in rows]
    return sorted(path.stem for path in Path(settings.SNAPSHOT_DIR).glob("*.json"))


async def _load_articles(
    conn,
    target_dates: list[date] | None,
    membership: dict[str, list[str]],
) -> list[dict]:
    if target_dates:
        target_iso = sorted({target.isoformat() for target in target_dates})
        snapshot_pmids = sorted(
            {pmid for pmids in membership.values() for pmid in pmids}
        )
        clauses: list[str] = []
        params: list[str] = []
        if snapshot_pmids:
            clauses.append(f"pmid IN ({','.join('?' for _ in snapshot_pmids)})")
            params.extend(snapshot_pmids)
        missing_snapshot_dates = [d for d in target_iso if d not in membership]
        if missing_snapshot_dates:
            clauses.append(
                f"epdat IN ({','.join('?' for _ in missing_snapshot_dates)})"
            )
            params.extend(missing_snapshot_dates)
        if not clauses:
            return []
        cursor = await conn.execute(
            f"SELECT * FROM articles WHERE llm_excluded=0 AND ({' OR '.join(clauses)})",
            params,
        )
    else:
        cursor = await conn.execute(
            "SELECT * FROM articles WHERE llm_excluded=0"
        )
    rows = [_deserialize_json_fields(dict(row)) for row in await cursor.fetchall()]
    await cursor.close()
    for row in rows:
        row["disease_hint"] = row.get("disease")
    return rows


def _group_articles(
    rows: list[dict], membership: dict[str, list[str]]
) -> dict[str, list[dict]]:
    """优先按既有 snapshot 成员分组;未映射文章才回退到 epdat。"""
    by_pmid = {str(row["pmid"]): row for row in rows}
    groups: dict[str, list[dict]] = {}
    assigned: set[str] = set()
    for snapshot_date, pmids in membership.items():
        group = [by_pmid[pmid] for pmid in pmids if pmid in by_pmid]
        if group:
            groups[snapshot_date] = group
            assigned.update(str(row["pmid"]) for row in group)
    for row in rows:
        pmid = str(row["pmid"])
        if pmid not in assigned:
            groups.setdefault(str(row["epdat"]), []).append(row)
    return groups


async def _write_articles(conn, records: list[dict]) -> None:
    for record in records:
        await conn.execute(
            """UPDATE articles SET
            title_zh = ?, abstract_zh = ?, type = ?, disease = ?,
            llm_classified_at = ?, llm_model = ?, llm_needs_review = ?,
            llm_excluded = ?, llm_exclude_reason = ?
            WHERE pmid = ?""",
            (
                record.get("title_zh", ""),
                record.get("abstract_zh"),
                record.get("type"),
                record.get("disease"),
                record.get("llm_classified_at"),
                record.get("llm_model"),
                record.get("llm_needs_review", 0),
                record.get("llm_excluded", 0),
                record.get("exclude_reason"),
                record["pmid"],
            ),
        )
    await conn.commit()


async def _rewrite_snapshot(conn, snapshot_date: str, pmids: list[str]) -> None:
    if not pmids:
        write_daily_snapshot(date.fromisoformat(snapshot_date), [])
        return
    placeholders = ",".join("?" for _ in pmids)
    cursor = await conn.execute(
        f"SELECT * FROM articles WHERE llm_excluded=0 AND pmid IN ({placeholders})",
        pmids,
    )
    by_pmid = {
        str(row["pmid"]): _deserialize_json_fields(dict(row))
        for row in await cursor.fetchall()
    }
    await cursor.close()
    records = [by_pmid[pmid] for pmid in pmids if pmid in by_pmid]
    write_daily_snapshot(date.fromisoformat(snapshot_date), records)


async def run(
    target_dates: list[date] | None = None,
    force_refresh: bool = True,
) -> dict:
    """Re-run classify_and_translate_batch on articles in DB.

    Args:
        target_dates: None = 全部;否则仅指定 snapshot 日期列表。
        force_refresh: True 时强制跳过 llm_cache。

    Returns: {"reclassified": N, "dates": [...]}.
    """
    conn = await get_db()
    try:
        snapshot_dates = await _snapshot_dates_from_db(conn, target_dates)
        membership = _load_snapshot_membership(snapshot_dates)
        rows = await _load_articles(conn, target_dates, membership)
        log.info("loaded %d articles from DB", len(rows))
        if not rows:
            return {"reclassified": 0, "dates": []}

        groups = _group_articles(rows, membership)
        planned_calls = sum(
            (len(records) + settings.LLM_BATCH_SIZE - 1)
            // settings.LLM_BATCH_SIZE
            for records in groups.values()
        )
        log.info(
            "planned MiniMax calls: %d (model=%s, force_refresh=%s)",
            planned_calls,
            settings.LLM_MODEL,
            force_refresh,
        )

        reclassified = 0
        failed_pmids: list[str] = []
        for group_date, records in sorted(groups.items()):
            pmids = [str(record["pmid"]) for record in records]
            log.info("re-classify %s: %d records", group_date, len(records))
            try:
                await classify_and_translate_batch(
                    records,
                    conn,
                    force_refresh=force_refresh,
                )
                await _write_articles(conn, records)
                reclassified += len(records)
            except Exception:  # noqa: BLE001 - 单批失败必须继续后续日期
                await conn.rollback()
                failed_pmids.extend(pmids)
                log.exception(
                    "re-classify failed for %s; continuing; PMIDs=%s",
                    group_date,
                    ",".join(pmids),
                )
                continue

            needs_review = [
                str(record["pmid"])
                for record in records
                if record.get("llm_needs_review")
            ]
            if needs_review:
                failed_pmids.extend(needs_review)
                log.warning(
                    "%s used heuristic/needs review; PMIDs=%s",
                    group_date,
                    ",".join(needs_review),
                )
            log.info("  %s: reclassified %d", group_date, len(records))

        rewritten_dates: list[str] = []
        if membership:
            for snapshot_date, pmids in sorted(membership.items()):
                try:
                    await _rewrite_snapshot(conn, snapshot_date, pmids)
                    rewritten_dates.append(snapshot_date)
                    log.info("  %s: snapshot rewritten", snapshot_date)
                except Exception:  # noqa: BLE001 - 一个文件失败不阻断其余文件
                    log.exception("snapshot rewrite failed for %s", snapshot_date)
        else:
            for group_date in sorted(groups):
                cursor = await conn.execute(
                    "SELECT pmid FROM articles WHERE epdat=? ORDER BY rowid",
                    (group_date,),
                )
                pmids = [str(row["pmid"]) for row in await cursor.fetchall()]
                await cursor.close()
                try:
                    await _rewrite_snapshot(conn, group_date, pmids)
                    rewritten_dates.append(group_date)
                    log.info("  %s: snapshot rewritten", group_date)
                except Exception:  # noqa: BLE001
                    log.exception("snapshot rewrite failed for %s", group_date)

        if failed_pmids:
            log.warning(
                "failed/needs-review PMIDs (%d): %s",
                len(set(failed_pmids)),
                ",".join(sorted(set(failed_pmids))),
            )
        else:
            log.info("all articles returned translated LLM output")
        return {"reclassified": reclassified, "dates": rewritten_dates}
    finally:
        await close_db(conn)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="Re-run LLM classify + translate on existing articles"
    )
    parser.add_argument(
        "--date",
        action="append",
        help="Target snapshot date YYYY-MM-DD (can repeat); default=all",
    )
    parser.add_argument(
        "--no-force-refresh",
        action="store_true",
        help="Use cache if present",
    )
    args = parser.parse_args()
    target_dates = [date.fromisoformat(value) for value in args.date] if args.date else None
    result = asyncio.run(
        run(
            target_dates=target_dates,
            force_refresh=not args.no_force_refresh,
        )
    )
    print(f"reclassified: {result}")


if __name__ == "__main__":
    main()
