"""Minimal application settings stub.

Phase A 第 2 步只引入数据库层所需的最小配置(DB_PATH / LOG_LEVEL / TZ),
其余字段在 Phase A 第 7 步(API 层)统一扩展。
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Project-wide settings (Phase A 最小集)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DB_PATH: str = "/data/thoracic.db"
    LOG_LEVEL: str = "INFO"
    TZ: str = "Asia/Shanghai"


settings = Settings()

# 确保 DB_PATH 的父目录存在,避免后续 init 失败。
try:
    Path(settings.DB_PATH).expanduser().parent.mkdir(parents=True, exist_ok=True)
except OSError:
    # /data 是容器卷,开发机上可能没有写权限;启动时再处理。
    pass
