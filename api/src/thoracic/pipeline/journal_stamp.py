"""把期刊 IF/Q1/新锐分区 stamp 到 records 上(基于 JournalIndex 三级 lookup)。"""

from __future__ import annotations
from typing import Iterable

from thoracic.db.seed import JournalIndex


def stamp_journal_metrics(records: Iterable[dict], index: JournalIndex) -> None:
    """对每条 record 原地填 journal_full / impact_factor / jcr_quartile / new_talent_quartile / matched_jcr。

    若 lookup 失败,journal_full 留 None,IF 等指标也留 None;但不影响主流程。
    """
    for r in records:
        m = index.lookup(r.get("journal"))
        if m is None:
            r["journal_full"] = None
            r["impact_factor"] = None
            r["jcr_quartile"] = None
            r["new_talent_quartile"] = None
            r["matched_jcr"] = None
            continue
        r["journal_full"] = m.journal
        r["impact_factor"] = m.impact_factor
        r["jcr_quartile"] = m.jcr_quartile
        r["new_talent_quartile"] = m.new_talent_quartile
        r["matched_jcr"] = m.matched_jcr_journal


def build_article_record(parsed: dict) -> dict:
    """把 pubmed parser 的 record 转成 repo.upsert_article 期望的字段 dict(不包含期刊指标与 llm_* 字段)。

    repo 层会负责 JSON 序列化。
    """
    return {
        "pmid": parsed["pmid"],
        "title": parsed.get("title") or "",
        "title_zh": parsed.get("title_zh") or "",
        "abstract": parsed.get("abstract"),
        "abstract_zh": parsed.get("abstract_zh"),
        "authors": parsed.get("authors") or [],
        "affiliations": parsed.get("affiliations") or [],
        "journal": parsed.get("journal") or "",
        "journal_full": None,  # 由 stamp_journal_metrics 填
        "journal_abbr": parsed.get("journal_abbr"),
        "doi": parsed.get("doi"),
        "publication_types": parsed.get("publication_types") or [],
        "pubdate": parsed.get("pubdate") or "",
        "epdat": parsed.get("epdat") or "",
        "fetched_at": parsed.get("fetched_at"),
        "impact_factor": None,
        "jcr_quartile": None,
        "new_talent_quartile": None,
        "matched_jcr": None,
    }
