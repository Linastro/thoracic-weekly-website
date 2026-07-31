"""Minimal application settings stub.

Phase A 第 2 步只引入数据库层所需的最小配置(DB_PATH / LOG_LEVEL / TZ),
第 4 步(LLM)扩展:PubMed key + MiniMax M3 客户端 + 反向触发 token。
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
    SNAPSHOT_DIR: str = "/data/snapshots"
    LOG_LEVEL: str = "INFO"
    TZ: str = "Asia/Shanghai"

    # PubMed
    PUBMED_API_KEY: str = ""

    # MiniMax M3 (OpenAI 兼容 chat completions)
    LLM_BASE_URL: str = "https://api.MiniMax.chat/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "MiniMax-M3"
    LLM_TIMEOUT_SECONDS: int = 60
    LLM_MAX_CONCURRENT: int = 3
    LLM_BATCH_SIZE: int = 10

    # 反向触发鉴权(供 /api/backfill 等使用,本步骤仅注入 settings)
    REGEN_TOKEN: str = ""

    # CORS 白名单(逗号分隔的 URL 列表;空字符串 → allow_origins=["*"],本地预览常用)
    SITE_URL: str = ""


settings = Settings()

# 确保 DB_PATH 的父目录存在,避免后续 init 失败。
try:
    Path(settings.DB_PATH).expanduser().parent.mkdir(parents=True, exist_ok=True)
except OSError:
    # /data 是容器卷,开发机上可能没有写权限;启动时再处理。
    pass
