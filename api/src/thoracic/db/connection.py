"""SQLite 连接工厂与 schema 初始化。

设计要点:
- 每次调用 `get_db()` 都创建新连接(aiosqlite 不是同步连接池,
  共享一个连接会序列化所有查询,牺牲并发)。
- 连接上自动启用 WAL / foreign_keys / synchronous=NORMAL,
  符合 PLAN §六 4. 性能与并发要求。
- `row_factory = aiosqlite.Row` 让 fetchall 返回字典式访问。
- schema.sql 读取采用 `pathlib.Path(__file__).parent / "schema.sql"`,
  避免 importlib.resources 的包管理限制。
"""

from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

from thoracic.config import settings

logger = logging.getLogger(__name__)

# 模块级路径缓存(允许测试时覆盖)
_db_path_override: str | None = None


def configure_db_path(path: str) -> None:
    """测试 / 启动时覆盖 DB 路径。"""
    global _db_path_override
    _db_path_override = path


def get_db_path() -> str:
    """解析 SQLite 路径,优先使用 _db_path_override,否则读 settings。"""
    if _db_path_override is not None:
        return _db_path_override
    return settings.DB_PATH


async def get_db() -> aiosqlite.Connection:
    """创建新连接,设置 PRAGMA 与 row_factory。"""
    db_path = get_db_path()
    Path(db_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(db_path)
    # WAL 仅在第一次连接时生效,后续连接读已建立的 journal_mode。
    await conn.execute("PRAGMA journal_mode = WAL")
    await conn.execute("PRAGMA foreign_keys = ON")
    await conn.execute("PRAGMA synchronous = NORMAL")
    conn.row_factory = aiosqlite.Row
    return conn


async def close_db(conn: aiosqlite.Connection | None) -> None:
    """显式关闭连接(便于 finally 块调用)。"""
    if conn is None:
        return
    try:
        await conn.close()
    except Exception:  # noqa: BLE001 - 关闭异常仅记日志
        logger.exception("failed to close aiosqlite connection")


async def init_db() -> None:
    """读取 schema.sql 并执行(幂等,IF NOT EXISTS)。"""
    schema_path = Path(__file__).parent / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")

    conn = await get_db()
    try:
        await conn.executescript(schema_sql)
        await conn.commit()
    finally:
        await close_db(conn)
