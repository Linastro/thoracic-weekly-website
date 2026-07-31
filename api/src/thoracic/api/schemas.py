"""API response schemas。"""

from __future__ import annotations
from datetime import date
from pydantic import BaseModel, Field


class Article(BaseModel):
    """单条 article(对应 articles 表行,JSON 字段已反序列化)。"""
    pmid: str
    title: str
    title_zh: str
    abstract: str | None = None
    abstract_zh: str | None = None
    authors: list[str]
    affiliations: list[str | None] | None = None
    journal: str
    journal_full: str | None = None
    journal_abbr: str | None = None
    doi: str | None = None
    publication_types: list[str]
    pubdate: str | None = None
    epdat: str
    fetched_at: str
    disease: str
    type: str
    impact_factor: float | None = None
    jcr_quartile: str | None = None
    new_talent_quartile: str | None = None
    matched_jcr: str | None = None
    llm_model: str | None = None
    llm_excluded: int = 0
    llm_needs_review: int = 0


class DateEntry(BaseModel):
    """每日聚合(用于 /api/dates 与 /api/daily/YYYY-MM-DD 头部)。"""
    date: str
    article_count: int
    total_fetched: int | None = None
    excluded_count: int | None = None
    by_disease: dict[str, int] | None = None
    by_type: dict[str, int] | None = None
    generated_at: str | None = None


class RunLogEntry(BaseModel):
    """单次抓取日志(用于 /api/changelog)。"""
    started_at: str
    finished_at: str | None = None
    kind: str
    target_date: str | None = None
    fetched_count: int | None = None
    classified_count: int | None = None
    llm_calls: int | None = None
    status: str
    error_msg: str | None = None


class HealthResponse(BaseModel):
    status: str
    db: bool
    snapshots: int = 0


class DiseaseInfo(BaseModel):
    slug: str
    name_zh: str


class TypeInfo(BaseModel):
    slug: str
    name_zh: str


class BackfillRequest(BaseModel):
    from_date: str = Field(..., alias="from", pattern=r"^\d{4}-\d{2}-\d{2}$")
    to_date: str = Field(..., alias="to", pattern=r"^\d{4}-\d{2}-\d{2}$")
    concurrency: int = 3
    dry_run: bool = False

    model_config = {"populate_by_name": True}


class BackfillDayResult(BaseModel):
    target_date: str
    total_fetched: int = 0
    to_publish: int = 0
    to_exclude: int = 0
    by_disease: dict[str, int] = Field(default_factory=dict)
    by_type: dict[str, int] = Field(default_factory=dict)
    supplemental_pmids: list[str] = Field(default_factory=list)
    error: str | None = None


class BackfillResponse(BaseModel):
    days: list[BackfillDayResult]
    total_days: int
    total_published: int
    total_excluded: int