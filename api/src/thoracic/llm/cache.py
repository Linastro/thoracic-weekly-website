"""LLM 输出缓存:hash(pmid) → payload_json,1 年 TTL。

表结构(已由 Phase A 第 3 步创建):

    llm_cache(pmid_hash PK, payload_json, model, created_at, expires_at)

依赖:
- `aiosqlite.Connection`(由调用方持有,与 db/connection.py 一致)
- `thoracic.llm.json_parse.parse_strict_json_object`(读取时做修复,主要是历史脏数据)

注意:本模块与 `db/repo.py` 中的 `cache_get/cache_set` **独立**,
签名一致(都基于 pmid_hash),但实现不共用 —— Phase A 第 5 步可统一替换为 repo 版本。
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import aiosqlite

from .json_parse import parse_strict_json_object


def pmid_hash(pmid: str) -> str:
    """sha256(pmid)[:16],作为 llm_cache 表主键。

    pmid 是 PubMed 数字 ID(无 PHI),用 sha256 的前 16 字符已是 64-bit 空间,
    单数年抓取量下碰撞概率可忽略;若后续要严格避免碰撞,可改 full sha256。
    """
    return hashlib.sha256(pmid.encode("utf-8")).hexdigest()[:16]


def now_iso() -> str:
    """UTC ISO8601 时间戳,统一缓存写入格式。"""
    return datetime.now(timezone.utc).isoformat()


async def cache_get(conn: aiosqlite.Connection, pmid: str) -> dict | None:
    """命中返回 dict(已 json.loads);过期或缺失返回 None。

    读取时通过 `parse_strict_json_object` 二次清洗 —— 防御历史上坏掉的双重编码或转义字符。
    """
    h = pmid_hash(pmid)
    async with conn.execute(
        "SELECT payload_json, expires_at FROM llm_cache WHERE pmid_hash = ?",
        (h,),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        return None
    payload_json, expires_at = row[0], row[1]
    if expires_at and expires_at <= now_iso():
        return None
    try:
        # 直接 loads 优先,出错再走修复管线
        return json.loads(payload_json)
    except json.JSONDecodeError:
        try:
            return parse_strict_json_object(payload_json)
        except ValueError:
            return None


async def cache_set(
    conn: aiosqlite.Connection,
    pmid: str,
    payload: dict,
    model: str,
    ttl_seconds: int = 86400 * 365,
) -> None:
    """写缓存(hash → payload_json + model + expires_at)。

    INSERT OR REPLACE 模式:同 pmid 重复写入会覆盖旧记录 + 重置 TTL。
    """
    h = pmid_hash(pmid)
    created = now_iso()
    expires = (
        datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    ).isoformat()
    await conn.execute(
        "INSERT OR REPLACE INTO llm_cache "
        "(pmid_hash, payload_json, model, created_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            h,
            json.dumps(payload, ensure_ascii=False),
            model,
            created,
            expires,
        ),
    )
