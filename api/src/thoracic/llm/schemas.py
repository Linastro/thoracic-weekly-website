"""LLM 响应 Pydantic schemas。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ArticleClassification(BaseModel):
    """单篇文章的 LLM 分类与翻译结果。

    Phase A 第 5 步(pipeline)会消费这个模型,校验 LLM 输出并写入 articles 表。
    """

    pmid: str
    type: str = Field(
        pattern="^(clinical|ai_ml|basic_research|review|guideline)$"
    )
    disease: str = Field(
        pattern="^(lung_cancer|esophageal|mediastinal|tracheal|chest_wall_injury)$"
    )
    exclude: bool
    exclude_reason: str | None = None
    title_zh: str
    abstract_zh: str | None = None
