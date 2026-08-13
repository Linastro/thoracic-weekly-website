"""Repository layer for thoracic.db.

所有函数都是 `async def`,接收一个 `aiosqlite.Connection` 参数。
调用方负责连接生命周期(由路由 / pipeline 控制)。

JSON 字段约定:
- 写入:对 `authors` / `affiliations` / `publication_types` /
  `by_disease_json` / `by_type_json` / `payload_json` 等执行 `json.dumps`。
- 读取:`row_to_dict()` 已对 `articles` 与 `excluded_records` 行做反序列化,
  其余表的 JSON 字段读取时按需 `json.loads`。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import aiosqlite

# ----------------------------------------------------------------------
# 通用 helper
# ----------------------------------------------------------------------

# 已知 JSON 字段(articles 与 snapshots)。其余表按需在读取时处理。
_ARTICLE_JSON_FIELDS = ("authors", "affiliations", "publication_types")
_SNAPSHOT_JSON_FIELDS = ("by_disease_json", "by_type_json")


def now_iso() -> str:
    """返回当前 UTC 时间 ISO 格式(秒精度,带时区)。"""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def row_to_dict(row: aiosqlite.Row | None) -> dict[str, Any] | None:
    """aiosqlite.Row → dict;None 直接返回 None。"""
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def serialize_json_fields(record: dict[str, Any]) -> dict[str, Any]:
    """对已知 JSON 字段做 `json.dumps`,避免库字段被误存字符串。"""
    out = dict(record)
    for field in _ARTICLE_JSON_FIELDS:
        if field in out and not isinstance(out[field], str):
            out[field] = json.dumps(out[field], ensure_ascii=False)
    return out


def _deserialize_article(record: dict[str, Any]) -> dict[str, Any]:
    """读取时把 articles 的 JSON 字段反序列化。"""
    if record is None:
        return record
    for field in _ARTICLE_JSON_FIELDS:
        raw = record.get(field)
        if isinstance(raw, str) and raw:
            try:
                record[field] = json.loads(raw)
            except json.JSONDecodeError:
                # 损坏的 JSON 保留原值,便于排查
                continue
    return record


def _deserialize_snapshot(record: dict[str, Any]) -> dict[str, Any]:
    if record is None:
        return record
    for field in _SNAPSHOT_JSON_FIELDS:
        raw = record.get(field)
        if isinstance(raw, str) and raw:
            try:
                record[field] = json.loads(raw)
            except json.JSONDecodeError:
                continue
    return record


# ----------------------------------------------------------------------
# articles
# ----------------------------------------------------------------------

_ARTICLE_COLUMNS = (
    "pmid",
    "title",
    "title_zh",
    "abstract",
    "abstract_zh",
    "authors",
    "affiliations",
    "journal",
    "journal_full",
    "journal_abbr",
    "doi",
    "publication_types",
    "pubdate",
    "epdat",
    "fetched_at",
    "disease",
    "type",
    "llm_classified_at",
    "llm_model",
    "llm_excluded",
    "llm_exclude_reason",
    "llm_needs_review",
    "impact_factor",
    "jcr_quartile",
    "new_talent_quartile",
    "matched_jcr",
)


async def upsert_article(conn: aiosqlite.Connection, record: dict[str, Any]) -> None:
    """INSERT OR REPLACE 一条 articles 记录。"""
    payload = serialize_json_fields(record)
    # 缺失字段用 NULL(允许 abstract / doi 等为 NULL)
    values = [payload.get(col) for col in _ARTICLE_COLUMNS]
    placeholders = ", ".join(["?"] * len(_ARTICLE_COLUMNS))
    columns_sql = ", ".join(_ARTICLE_COLUMNS)
    sql = (
        f"INSERT OR REPLACE INTO articles ({columns_sql}) "
        f"VALUES ({placeholders})"
    )
    await conn.execute(sql, values)


async def upsert_articles_batch(
    conn: aiosqlite.Connection, records: list[dict[str, Any]]
) -> int:
    """批量 upsert,返回成功写入条数。"""
    count = 0
    for record in records:
        await upsert_article(conn, record)
        count += 1
    return count


async def get_article(
    conn: aiosqlite.Connection, pmid: str
) -> dict[str, Any] | None:
    """按 PMID 查单条;JSON 字段反序列化。"""
    cursor = await conn.execute(
        "SELECT * FROM articles WHERE pmid = ?", (pmid,)
    )
    row = await cursor.fetchone()
    await cursor.close()
    return _deserialize_article(row_to_dict(row))


async def list_articles(
    conn: aiosqlite.Connection,
    *,
    disease: str | None = None,
    type_: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """筛选查询,只返回 llm_excluded = 0。

    支持 `?disease=lung_cancer&type=clinical&from=YYYY-MM-DD&to=YYYY-MM-DD`。
    """
    where = ["llm_excluded = 0"]
    params: list[Any] = []
    if disease:
        where.append("disease = ?")
        params.append(disease)
    if type_:
        where.append("type = ?")
        params.append(type_)
    if date_from:
        where.append("epdat >= ?")
        params.append(date_from)
    if date_to:
        where.append("epdat <= ?")
        params.append(date_to)
    where_sql = " AND ".join(where)
    sql = (
        f"SELECT * FROM articles WHERE {where_sql} "
        "ORDER BY epdat DESC, fetched_at DESC "
        "LIMIT ? OFFSET ?"
    )
    cursor = await conn.execute(sql, [*params, limit, offset])
    rows = await cursor.fetchall()
    await cursor.close()
    return [_deserialize_article(row_to_dict(row)) for row in rows]


async def list_articles_by_date(
    conn: aiosqlite.Connection,
    date: str,
    *,
    disease: str | None = None,
    type_: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """按 epdat = date 查当日文献。"""
    where = ["llm_excluded = 0", "epdat = ?"]
    params: list[Any] = [date]
    if disease:
        where.append("disease = ?")
        params.append(disease)
    if type_:
        where.append("type = ?")
        params.append(type_)
    where_sql = " AND ".join(where)
    sql = (
        f"SELECT * FROM articles WHERE {where_sql} "
        "ORDER BY fetched_at DESC "
        "LIMIT ? OFFSET ?"
    )
    cursor = await conn.execute(sql, [*params, limit, offset])
    rows = await cursor.fetchall()
    await cursor.close()
    return [_deserialize_article(row_to_dict(row)) for row in rows]


async def list_articles_for_snapshot(
    conn: aiosqlite.Connection, date: str
) -> list[dict[str, Any]]:
    """取某 epdat 的全部已发布文献,不分页 —— 供重建 snapshot JSON 用。"""
    cursor = await conn.execute(
        "SELECT * FROM articles WHERE llm_excluded = 0 AND epdat = ? "
        "ORDER BY fetched_at, pmid",
        (date,),
    )
    rows = await cursor.fetchall()
    await cursor.close()
    return [_deserialize_article(row_to_dict(row)) for row in rows]


async def list_articles_for_week(
    conn: aiosqlite.Connection, date_from: str, date_to: str
) -> list[dict[str, Any]]:
    """取 [date_from, date_to] epdat 区间内全部已发布文献,不分页 —— 供周报用。

    写法仿 `list_articles_for_snapshot`,仅把单日 `epdat = ?` 换成
    `epdat BETWEEN ? AND ?`,并按 epdat / fetched_at / pmid 升序稳定排序。
    """
    cursor = await conn.execute(
        "SELECT * FROM articles WHERE llm_excluded = 0 "
        "AND epdat BETWEEN ? AND ? "
        "ORDER BY epdat, fetched_at, pmid",
        (date_from, date_to),
    )
    rows = await cursor.fetchall()
    await cursor.close()
    return [_deserialize_article(row_to_dict(row)) for row in rows]


async def list_articles_search(
    conn: aiosqlite.Connection, query: str, limit: int = 50
) -> list[dict[str, Any]]:
    """FTS5 搜索 articles_fts。返回 0..limit 条,JSON 反序列化。"""
    if not query or not query.strip():
        return []
    # FTS5 MATCH:需要双引号包裹短语或直接传词项;
    # 直接拼 query 让 caller 控制(避免自动改写语义)
    fts_sql = (
        "SELECT a.* FROM articles_fts f "
        "JOIN articles a ON a.rowid = f.rowid "
        "WHERE articles_fts MATCH ? "
        "ORDER BY rank LIMIT ?"
    )
    cursor = await conn.execute(fts_sql, (query, limit))
    rows = await cursor.fetchall()
    await cursor.close()
    return [_deserialize_article(row_to_dict(row)) for row in rows]


async def list_dates(
    conn: aiosqlite.Connection, limit: int = 30
) -> list[dict[str, Any]]:
    """返回每日有数据日期(article_count、total_fetched、excluded_count、generated_at)。

    来源 daily_snapshots 优先,若缺失则回退到 articles 聚合。
    """
    snap_sql = (
        "SELECT date, article_count, total_fetched, excluded_count, generated_at "
        "FROM daily_snapshots ORDER BY date DESC LIMIT ?"
    )
    cursor = await conn.execute(snap_sql, (limit,))
    snapshots = [row_to_dict(row) for row in await cursor.fetchall()]
    await cursor.close()
    if snapshots:
        return snapshots  # type: ignore[return-value]

    # 回退:按 epdat 聚合
    fallback_sql = (
        "SELECT epdat AS date, "
        "COUNT(*) AS article_count, "
        "COUNT(*) AS total_fetched, "
        "0 AS excluded_count, "
        "MAX(fetched_at) AS generated_at "
        "FROM articles WHERE llm_excluded = 0 "
        "GROUP BY epdat ORDER BY epdat DESC LIMIT ?"
    )
    cursor = await conn.execute(fallback_sql, (limit,))
    rows = await cursor.fetchall()
    await cursor.close()
    return [row_to_dict(row) for row in rows]  # type: ignore[return-value]


# ----------------------------------------------------------------------
# daily_snapshots
# ----------------------------------------------------------------------

async def upsert_snapshot(
    conn: aiosqlite.Connection, snapshot: dict[str, Any]
) -> None:
    """INSERT OR REPLACE 一条 snapshot。"""
    payload = dict(snapshot)
    # by_disease_json / by_type_json 已经在 SQL 字段名,直接 JSON 序列化
    for field in _SNAPSHOT_JSON_FIELDS:
        if field in payload and payload[field] is not None and not isinstance(payload[field], str):
            payload[field] = json.dumps(payload[field], ensure_ascii=False)

    columns = (
        "date",
        "generated_at",
        "article_count",
        "total_fetched",
        "excluded_count",
        "by_disease_json",
        "by_type_json",
        "llm_calls",
        "llm_cost_usd",
        "note",
    )
    values = [payload.get(col) for col in columns]
    placeholders = ", ".join(["?"] * len(columns))
    columns_sql = ", ".join(columns)
    sql = (
        f"INSERT OR REPLACE INTO daily_snapshots ({columns_sql}) "
        f"VALUES ({placeholders})"
    )
    await conn.execute(sql, values)


async def list_snapshots(
    conn: aiosqlite.Connection, limit: int = 30
) -> list[dict[str, Any]]:
    """倒序返回 snapshot 列表,JSON 字段反序列化。"""
    cursor = await conn.execute(
        "SELECT * FROM daily_snapshots ORDER BY date DESC LIMIT ?", (limit,)
    )
    rows = await cursor.fetchall()
    await cursor.close()
    return [_deserialize_snapshot(row_to_dict(row)) for row in rows]  # type: ignore[arg-type]


# ----------------------------------------------------------------------
# run_log
# ----------------------------------------------------------------------

_RUN_LOG_COLUMNS = (
    "started_at",
    "finished_at",
    "kind",
    "target_date",
    "fetched_count",
    "classified_count",
    "llm_calls",
    "status",
    "error_msg",
)


async def write_run_log(
    conn: aiosqlite.Connection, log: dict[str, Any]
) -> int:
    """插入一条 run_log,返回自增 id。"""
    values = [log.get(col) for col in _RUN_LOG_COLUMNS]
    placeholders = ", ".join(["?"] * len(_RUN_LOG_COLUMNS))
    columns_sql = ", ".join(_RUN_LOG_COLUMNS)
    sql = (
        f"INSERT INTO run_log ({columns_sql}) "
        f"VALUES ({placeholders})"
    )
    cursor = await conn.execute(sql, values)
    await cursor.close()
    last_id = getattr(cursor, "lastrowid", None)
    if last_id is None:
        # 兼容:执行 SELECT last_insert_rowid()
        cur = await conn.execute("SELECT last_insert_rowid()")
        row = await cur.fetchone()
        await cur.close()
        last_id = row[0] if row else 0
    return int(last_id)


async def update_run_log(
    conn: aiosqlite.Connection, run_id: int, **fields: Any
) -> None:
    """按 run_id 更新 run_log 的若干字段。"""
    if not fields:
        return
    set_clauses = ", ".join(f"{key} = ?" for key in fields)
    params: list[Any] = list(fields.values())
    params.append(run_id)
    await conn.execute(
        f"UPDATE run_log SET {set_clauses} WHERE id = ?", params
    )


async def list_run_logs(
    conn: aiosqlite.Connection, limit: int = 20
) -> list[dict[str, Any]]:
    """按 id 倒序返回最近 run_log。"""
    cursor = await conn.execute(
        "SELECT * FROM run_log ORDER BY id DESC LIMIT ?", (limit,)
    )
    rows = await cursor.fetchall()
    await cursor.close()
    return [row_to_dict(row) for row in rows]  # type: ignore[arg-type]


# ----------------------------------------------------------------------
# excluded_records
# ----------------------------------------------------------------------

_EXCLUDED_COLUMNS = (
    "pmid",
    "hit_source",
    "title",
    "journal",
    "pubdate",
    "reason",
)


async def upsert_excluded(
    conn: aiosqlite.Connection, record: dict[str, Any]
) -> None:
    values = [record.get(col) for col in _EXCLUDED_COLUMNS]
    placeholders = ", ".join(["?"] * len(_EXCLUDED_COLUMNS))
    columns_sql = ", ".join(_EXCLUDED_COLUMNS)
    sql = (
        f"INSERT OR REPLACE INTO excluded_records ({columns_sql}) "
        f"VALUES ({placeholders})"
    )
    await conn.execute(sql, values)


async def upsert_excluded_batch(
    conn: aiosqlite.Connection, records: list[dict[str, Any]]
) -> int:
    count = 0
    for record in records:
        await upsert_excluded(conn, record)
        count += 1
    return count


# ----------------------------------------------------------------------
# llm_cache
# ----------------------------------------------------------------------

_LLM_CACHE_COLUMNS = (
    "pmid_hash",
    "payload_json",
    "model",
    "created_at",
    "expires_at",
)


async def cache_get(
    conn: aiosqlite.Connection, pmid_hash: str
) -> dict[str, Any] | None:
    """命中且未过期 → 返回反序列化的 payload;否则 None。"""
    cursor = await conn.execute(
        "SELECT payload_json, expires_at FROM llm_cache WHERE pmid_hash = ?",
        (pmid_hash,),
    )
    row = await cursor.fetchone()
    await cursor.close()
    if not row:
        return None
    payload_json, expires_at = row["payload_json"], row["expires_at"]
    if expires_at and expires_at < now_iso():
        return None
    try:
        return json.loads(payload_json)
    except json.JSONDecodeError:
        return None


async def cache_set(
    conn: aiosqlite.Connection,
    pmid_hash: str,
    payload: dict[str, Any],
    model: str,
    ttl_seconds: int = 86400 * 365,
) -> None:
    """写入缓存;默认 TTL = 1 年(LLM 翻译结果按 PMID 长期稳定)。"""
    now = datetime.now(timezone.utc)
    expires = datetime.fromtimestamp(now.timestamp() + ttl_seconds, tz=timezone.utc)
    record = {
        "pmid_hash": pmid_hash,
        "payload_json": json.dumps(payload, ensure_ascii=False),
        "model": model,
        "created_at": now.replace(microsecond=0).isoformat(),
        "expires_at": expires.replace(microsecond=0).isoformat(),
    }
    values = [record[col] for col in _LLM_CACHE_COLUMNS]
    placeholders = ", ".join(["?"] * len(_LLM_CACHE_COLUMNS))
    columns_sql = ", ".join(_LLM_CACHE_COLUMNS)
    sql = (
        f"INSERT OR REPLACE INTO llm_cache ({columns_sql}) "
        f"VALUES ({placeholders})"
    )
    await conn.execute(sql, values)
