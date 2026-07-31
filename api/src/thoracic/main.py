"""FastAPI app entry。"""

from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from thoracic.api.routes import router as api_router
from thoracic.config import settings
from thoracic.db.connection import init_db, configure_db_path
from thoracic.snapshots.writer import list_snapshots

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """启动时确保 schema 与 snapshot dir 存在。"""
    import os, pathlib
    # 设置 DB_PATH(若未设置)
    if settings.DB_PATH:
        configure_db_path(settings.DB_PATH)
    # 确保 snapshot 目录
    pathlib.Path(settings.SNAPSHOT_DIR).mkdir(parents=True, exist_ok=True)
    # 初始化 schema(幂等)
    await init_db()
    log.info(f"lifespan ready: db={settings.DB_PATH} snapshots={settings.SNAPSHOT_DIR}")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Thoracic Literature Daily Monitor API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS:基于 SITE_URL env;空字符串允许所有(本地预览时常用)
    site_url = getattr(settings, "SITE_URL", "") or ""
    cors_origins = [o.strip() for o in site_url.split(",") if o.strip()] if site_url else []
    if not cors_origins:
        cors_origins = ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    uvicorn.run("thoracic.main:app", host="0.0.0.0", port=8080, reload=False)