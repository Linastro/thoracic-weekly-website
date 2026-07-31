"""API routes(挂在 /api prefix 下)。"""

from __future__ import annotations
import json
import logging
from datetime import date as _date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from thoracic.config import settings
from thoracic.db import repo
from thoracic.db.connection import get_db, close_db, init_db
from thoracic.pipeline.backfill import run_backfill
from thoracic.pubmed.diseases import DISEASES
from .schemas import (
    Article, BackfillDayResult, BackfillRequest, BackfillResponse,
    DateEntry, DiseaseInfo, HealthResponse, RunLogEntry, TypeInfo,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

# Disease 与 type 的中文 label(供前端筛选 chip)
_DISEASE_LABELS: dict[str, str] = {d["slug"]: d["name_zh"] for d in DISEASES}
_TYPE_LABELS: dict[str, str] = {
    "clinical": "临床研究",
    "ai_ml": "AI/ML 研究",
    "basic_research": "基础研究",
    "review": "综述与 Meta",
    "guideline": "指南与共识",
}


async def _get_conn():
    """每个请求一个新连接(aiosqlite 没有池化)。"""
    return await get_db()


def _parse_iso_date(s: str, field: str) -> str:
    """验证 YYYY-MM-DD;返回规范化的 YYYY-MM-DD 字符串。"""
    try:
        return _date.fromisoformat(s).isoformat()
    except ValueError:
        raise HTTPException(400, f"invalid date for {field}: {s!r}; expected YYYY-MM-DD")


def _is_valid_disease(d: str) -> bool:
    return d in _DISEASE_LABELS


def _is_valid_type(t: str) -> bool:
    return t in _TYPE_LABELS


# ====== GET /api/health ======

@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    try:
        conn = await get_db()
        try:
            # 直接查询 SQLite(aiosqlite, 非 SQLAlchemy)
            cur = await conn.execute("SELECT COUNT(*) FROM articles")
            (n_articles,) = await cur.fetchone()
            cur = await conn.execute("SELECT COUNT(*) FROM daily_snapshots")
            (n_snaps,) = await cur.fetchone()
            return HealthResponse(status="ok", db=True, snapshots=n_snaps)
        finally:
            await close_db(conn)
    except Exception as e:
        log.error(f"health check failed: {e}")
        return HealthResponse(status="degraded", db=False, snapshots=0)


# ====== GET /api/diseases ======

@router.get("/diseases", response_model=list[DiseaseInfo])
async def list_diseases() -> list[DiseaseInfo]:
    return [DiseaseInfo(slug=s, name_zh=n) for s, n in _DISEASE_LABELS.items()]


# ====== GET /api/types ======

@router.get("/types", response_model=list[TypeInfo])
async def list_types() -> list[TypeInfo]:
    return [TypeInfo(slug=s, name_zh=n) for s, n in _TYPE_LABELS.items()]


# ====== GET /api/dates ======

@router.get("/dates", response_model=list[DateEntry])
async def list_dates(limit: int = Query(30, ge=1, le=365)) -> list[DateEntry]:
    conn = await _get_conn()
    try:
        rows = await repo.list_dates(conn, limit=limit)
        out: list[DateEntry] = []
        for r in rows:
            by_disease = None
            by_type = None
            if r.get("by_disease_json"):
                try:
                    by_disease = json.loads(r["by_disease_json"])
                except json.JSONDecodeError:
                    pass
            if r.get("by_type_json"):
                try:
                    by_type = json.loads(r["by_type_json"])
                except json.JSONDecodeError:
                    pass
            out.append(DateEntry(
                date=r["date"],
                article_count=r.get("article_count", 0),
                total_fetched=r.get("total_fetched"),
                excluded_count=r.get("excluded_count"),
                by_disease=by_disease,
                by_type=by_type,
                generated_at=r.get("generated_at"),
            ))
        return out
    finally:
        await close_db(conn)


# ====== GET /api/daily ======

@router.get("/daily", response_model=list[Article])
async def list_daily(
    date: str = Query(..., description="YYYY-MM-DD"),
    type: str | None = Query(None),
    disease: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[Article]:
    date_iso = _parse_iso_date(date, "date")
    if type is not None and not _is_valid_type(type):
        raise HTTPException(400, f"invalid type: {type!r}")
    if disease is not None and not _is_valid_disease(disease):
        raise HTTPException(400, f"invalid disease: {disease!r}")
    conn = await _get_conn()
    try:
        rows = await repo.list_articles_by_date(
            conn, date_iso, disease=disease, type_=type, limit=limit, offset=offset,
        )
        return [Article(**r) for r in rows]
    finally:
        await close_db(conn)


# ====== GET /api/all ======

@router.get("/all", response_model=list[Article])
async def list_all(
    type: str | None = Query(None),
    disease: str | None = Query(None),
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[Article]:
    if type is not None and not _is_valid_type(type):
        raise HTTPException(400, f"invalid type: {type!r}")
    if disease is not None and not _is_valid_disease(disease):
        raise HTTPException(400, f"invalid disease: {disease!r}")
    date_from = _parse_iso_date(from_, "from") if from_ else None
    date_to = _parse_iso_date(to, "to") if to else None
    conn = await _get_conn()
    try:
        rows = await repo.list_articles(
            conn, disease=disease, type_=type,
            date_from=date_from, date_to=date_to,
            limit=limit, offset=offset,
        )
        return [Article(**r) for r in rows]
    finally:
        await close_db(conn)


# ====== GET /api/article/{pmid} ======

@router.get("/article/{pmid}", response_model=Article)
async def get_article(pmid: str) -> Article:
    conn = await _get_conn()
    try:
        row = await repo.get_article(conn, pmid)
        if row is None:
            raise HTTPException(404, f"article not found: {pmid}")
        return Article(**row)
    finally:
        await close_db(conn)


# ====== GET /api/changelog ======

@router.get("/changelog", response_model=list[RunLogEntry])
async def list_changelog(limit: int = Query(20, ge=1, le=200)) -> list[RunLogEntry]:
    conn = await _get_conn()
    try:
        rows = await repo.list_run_logs(conn, limit=limit)
        return [RunLogEntry(**r) for r in rows]
    finally:
        await close_db(conn)


# ====== GET /api/snapshots ======

@router.get("/snapshots", response_model=list[DateEntry])
async def list_snapshots(limit: int = Query(30, ge=1, le=365)) -> list[DateEntry]:
    conn = await _get_conn()
    try:
        rows = await repo.list_snapshots(conn, limit=limit)
        out: list[DateEntry] = []
        for r in rows:
            by_disease = None
            by_type = None
            if r.get("by_disease_json"):
                try:
                    by_disease = json.loads(r["by_disease_json"])
                except json.JSONDecodeError:
                    pass
            if r.get("by_type_json"):
                try:
                    by_type = json.loads(r["by_type_json"])
                except json.JSONDecodeError:
                    pass
            out.append(DateEntry(
                date=r["date"],
                article_count=r.get("article_count", 0),
                total_fetched=r.get("total_fetched"),
                excluded_count=r.get("excluded_count"),
                by_disease=by_disease,
                by_type=by_type,
                generated_at=r.get("generated_at"),
            ))
        return out
    finally:
        await close_db(conn)


# ====== POST /api/backfill (Bearer auth) ======

_security = HTTPBearer(auto_error=False)


def _require_regen_token(creds: HTTPAuthorizationCredentials | None = Depends(_security)) -> None:
    if not settings.REGEN_TOKEN:
        raise HTTPException(503, "REGEN_TOKEN not configured")
    if creds is None or creds.scheme.lower() != "bearer" or creds.credentials != settings.REGEN_TOKEN:
        raise HTTPException(401, "invalid or missing Bearer token")


@router.post("/backfill", response_model=BackfillResponse, dependencies=[Depends(_require_regen_token)])
async def trigger_backfill(req: BackfillRequest) -> BackfillResponse:
    log.info(f"backfill triggered: from={req.from_date} to={req.to_date} concurrency={req.concurrency} dry_run={req.dry_run}")
    start = _date.fromisoformat(req.from_date)
    end = _date.fromisoformat(req.to_date)
    if end < start:
        raise HTTPException(400, "to < from")
    results = await run_backfill(start, end, concurrency=req.concurrency, dry_run=req.dry_run)
    days = []
    for r in results:
        if "error" in r:
            days.append(BackfillDayResult(target_date=r["target_date"], error=r["error"]))
        else:
            days.append(BackfillDayResult(**r))
    return BackfillResponse(
        days=days,
        total_days=len(days),
        total_published=sum(d.to_publish for d in days),
        total_excluded=sum(d.to_exclude for d in days),
    )