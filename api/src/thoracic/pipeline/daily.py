"""单日抓取 → LLM 分类翻译 → 入库 → snapshot 编排。"""

from __future__ import annotations
import asyncio
import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from thoracic.classify.classify import classify_and_translate_batch
from thoracic.classify.rules import looks_like_ai_ml
from thoracic.config import settings
from thoracic.db import repo
from thoracic.db.connection import get_db, close_db, init_db
from thoracic.db.seed import build_journal_index, JournalIndex
from thoracic.pubmed.client import get_api_key as pubmed_api_key_from_env
from thoracic.pubmed.pubmed import search_day, SearchDayResult
from thoracic.pubmed.diseases import DISEASES, MEDIASTINAL_SUPPLEMENT_QUERY
from .journal_stamp import stamp_journal_metrics, build_article_record
from ..snapshots.writer import write_daily_snapshot

log = logging.getLogger(__name__)


def _fetched_at_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _summarize_by_field(records: list[dict], field: str) -> dict[str, int]:
    """生成 {value: count} 统计。"""
    out: dict[str, int] = {}
    for r in records:
        v = r.get(field)
        if v is None:
            continue
        out[v] = out.get(v, 0) + 1
    return out


def _coerce_excluded_record(parsed: dict, llm_payload: dict) -> dict:
    """构造 excluded_records 表的 dict。"""
    return {
        "pmid": parsed["pmid"],
        "hit_source": parsed.get("disease_hint"),
        "title": parsed.get("title"),
        "journal": parsed.get("journal"),
        "pubdate": parsed.get("pubdate"),
        "reason": llm_payload.get("exclude_reason") or "LLM marked exclude",
    }


async def run_daily(target_date: date, *, dry_run: bool = False) -> dict[str, Any]:
    """抓取 target_date 的胸外文献,LLM 分类,写入 SQLite + JSON snapshot。

    返回 dict 含 fetch/llm/upsert/snapshot 各阶段统计。
    """
    await init_db()
    index = build_journal_index()

    conn = await get_db()
    try:
        api_key = pubmed_api_key_from_env() or settings.PUBMED_API_KEY

        # ====== Step 1: PubMed 抓取 ======
        log.info(f"[daily {target_date}] step 1: search PubMed")
        result: SearchDayResult = await search_day(target_date=target_date, api_key=api_key)

        # 纵隔补检:严格命中为 0 时跑宽泛查询(规则 §2.1 注)
        supplemental_pmids: set[str] = set()
        mediastinal_pmids = result.pmids_by_disease.get("mediastinal", set())
        if not mediastinal_pmids:
            log.info(f"[daily {target_date}] mediastinal strict=0; running supplement")
            # 跑一次宽泛 esearch;复用 gather_esearch_all 但只针对 mediastinal
            from thoracic.pubmed.client import gather_esearch_all, gather_efetch_all
            from thoracic.pubmed.dates import epdat_clause
            from thoracic.pubmed.journal_terms import load_journal_terms, chunk_journal_terms
            from thoracic.pubmed.parser import parse_pubmed_xml_batches
            chunks = chunk_journal_terms(load_journal_terms(), 18)
            supp = await gather_esearch_all(
                chunks,
                [{"slug": "mediastinal", "name_zh": "纵隔肿瘤(宽泛)", "query": MEDIASTINAL_SUPPLEMENT_QUERY}],
                epdat_clause(target_date),
                api_key,
            )
            supplemental_pmids = supp.get("mediastinal", set())
            if supplemental_pmids:
                # 抓这些 PMID 的 XML 并入主 records(但不并入 pmids_by_disease)
                from thoracic.pubmed.client import gather_efetch_all as _efetch
                xml_batches = await _efetch(supplemental_pmids, api_key)
                supp_records = parse_pubmed_xml_batches(xml_batches)
                for r in supp_records:
                    r["disease_hint"] = "mediastinal"
                result.records.extend(supp_records)

        total_fetched = len(result.records)
        log.info(f"[daily {target_date}] fetched {total_fetched} records")

        if total_fetched == 0:
            log.info(f"[daily {target_date}] no records, skip LLM")
            to_publish, to_exclude = [], []
            llm_calls = 0
        else:
            # 准备 records 给 LLM(补 fetched_at 字段)
            for r in result.records:
                if not r.get("fetched_at"):
                    r["fetched_at"] = _fetched_at_iso()

            # ====== Step 2: LLM 分类 + 翻译 ======
            log.info(f"[daily {target_date}] step 2: LLM classify")
            enriched = await classify_and_translate_batch(result.records, conn)
            llm_calls = enriched_count = len([r for r in enriched if r.get("type")])

            # 拆分 publish / exclude
            to_publish = [r for r in enriched if not r.get("exclude")]
            to_exclude = [r for r in enriched if r.get("exclude")]
            log.info(f"[daily {target_date}] {len(to_publish)} publish, {len(to_exclude)} exclude")

        # ====== Step 3: journal metrics stamp ======
        stamp_journal_metrics(to_publish, index)

        # ====== Step 4: 准备 article dict 给 repo ======
        # 把 enriched(LLM 后)的字段合并到 article 形状
        article_records = []
        for r in to_publish:
            art = build_article_record(r)
            # overlay 期刊指标(由 stamp_journal_metrics 原地写入 r,build_article_record 默认 None)
            art["journal_full"] = r.get("journal_full")
            art["impact_factor"] = r.get("impact_factor")
            art["jcr_quartile"] = r.get("jcr_quartile")
            art["new_talent_quartile"] = r.get("new_talent_quartile")
            art["matched_jcr"] = r.get("matched_jcr")
            art["disease"] = r["disease"]
            art["type"] = r["type"]
            art["llm_classified_at"] = r.get("llm_classified_at")
            art["llm_model"] = r.get("llm_model") or settings.LLM_MODEL
            art["llm_excluded"] = r.get("llm_excluded", 0)
            art["llm_exclude_reason"] = r.get("llm_exclude_reason")
            art["llm_needs_review"] = r.get("llm_needs_review", 0)
            article_records.append(art)

        excluded_records = [_coerce_excluded_record(r, {
            "exclude_reason": r.get("llm_exclude_reason")
        }) for r in to_exclude]

        # ==== 防污染过滤:即使 LLM 完全失败,写入 snapshot 与 SQLite 的 articles 必须只含 publish ====
        # 双重保险:web 端 data.ts 也过滤 `llm_excluded !== 0`,但源头先滤更安全。
        # 兜底场景:LLM 全失败 → 启发式 fallback 默认 `exclude=False` → 86 篇全部 publish →
        # 之前会写脏 snapshot;现在源头再过一道 `exclude / llm_excluded`。
        final_records = [
            r for r in article_records
            if not (r.get("llm_excluded") or r.get("exclude"))
        ]
        filtered_out = len(article_records) - len(final_records)
        if filtered_out > 0:
            log.warning(
                f"[daily {target_date}] filtered {filtered_out} articles from snapshot "
                f"(llm_excluded=1 or exclude=true)"
            )
        article_records = final_records  # 替换后续 upsert / snapshot / metadata 引用

        if dry_run:
            log.info(f"[daily {target_date}] DRY-RUN, skip DB writes")
            return {
                "target_date": target_date.isoformat(),
                "total_fetched": total_fetched,
                "to_publish": len(to_publish),
                "to_exclude": len(to_exclude),
                "filtered_out": filtered_out,
                "by_disease": _summarize_by_field(to_publish, "disease"),
                "by_type": _summarize_by_field(to_publish, "type"),
                "supplemental_pmids": list(supplemental_pmids),
                "dry_run": True,
            }

        # ====== Step 5: 写 SQLite(articles / excluded / snapshot / run_log) ======
        log.info(f"[daily {target_date}] step 5: upsert SQLite")
        if article_records:
            await repo.upsert_articles_batch(conn, article_records)
        if excluded_records:
            await repo.upsert_excluded_batch(conn, excluded_records)

        by_disease = _summarize_by_field(to_publish, "disease")
        by_type = _summarize_by_field(to_publish, "type")
        await repo.upsert_snapshot(conn, {
            "date": target_date.isoformat(),
            "generated_at": _fetched_at_iso(),
            "article_count": len(article_records),
            "total_fetched": total_fetched,
            "excluded_count": len(to_exclude),
            "by_disease_json": json.dumps(by_disease, ensure_ascii=False),
            "by_type_json": json.dumps(by_type, ensure_ascii=False),
            "llm_calls": llm_calls,
            "llm_cost_usd": None,
            "note": f"supplemental={len(supplemental_pmids)}" if supplemental_pmids else None,
        })

        # ====== Step 6: 写 JSON snapshot ======
        log.info(f"[daily {target_date}] step 6: write JSON snapshot")
        write_daily_snapshot(target_date, article_records)

        # ====== Step 7: run_log ======
        log.info(f"[daily {target_date}] step 7: run_log")
        # run_log 由 CLI 层(start_run/end_run)统一管理,这里只返回统计

        await conn.commit()

        return {
            "target_date": target_date.isoformat(),
            "total_fetched": total_fetched,
            "to_publish": len(to_publish),
            "to_exclude": len(to_exclude),
            "filtered_out": filtered_out,
            "by_disease": by_disease,
            "by_type": by_type,
            "supplemental_pmids": list(supplemental_pmids),
            "dry_run": False,
        }
    finally:
        await close_db(conn)
