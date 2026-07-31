"""LLM 分类 + 翻译批任务。"""
from __future__ import annotations
import asyncio, logging
import aiosqlite
from thoracic.config import settings
from thoracic.llm.cache import cache_get, cache_set
from thoracic.llm.client import MiniMaxClient, default_client
from thoracic.llm.errors import LlmAuthError, LlmError, LlmJsonParseError, LlmRateLimitError, LlmServerError
from thoracic.llm.prompts.classify import SYSTEM_PROMPT as CLASSIFY_SYSTEM_PROMPT, build_user_payload as build_classify_user_payload
from thoracic.llm.schemas import ArticleClassification
from .rules import fallback_type, fallback_title_zh, fallback_abstract_zh
log = logging.getLogger(__name__)

def _ensure_input_minimum(record: dict) -> dict:
    if not record.get("pmid"): raise ValueError(f"record missing pmid: {record}")
    return {"pmid": str(record["pmid"]), "title": record.get("title") or "", "abstract": record.get("abstract") or "", "publication_types": list(record.get("publication_types") or []), "disease_hint": record.get("disease_hint")}

def _build_cache_payload(item: ArticleClassification) -> dict:
    return item.model_dump()

async def _llm_classify_chunk(client: MiniMaxClient, chunk: list[dict]) -> list[ArticleClassification]:
    data = await client.chat_json([{"role":"system","content":CLASSIFY_SYSTEM_PROMPT},{"role":"user","content":build_classify_user_payload(chunk)}])
    items_raw = data.get("items")
    if not isinstance(items_raw, list): raise LlmJsonParseError(f"response missing 'items' list: {data}")
    by = {}
    for raw in items_raw:
        try: by[str(raw["pmid"])] = ArticleClassification(**raw)
        except Exception as e: log.warning("invalid classification: %s", e)
    return [by[r["pmid"]] for r in chunk if r["pmid"] in by]

def _heuristic_record(record: dict) -> ArticleClassification:
    return ArticleClassification(pmid=record["pmid"], type=fallback_type(record["publication_types"],record["title"],record["abstract"]), disease=record.get("disease_hint") or "lung_cancer", exclude=False, exclude_reason=None, title_zh=fallback_title_zh(record["title"]), abstract_zh=fallback_abstract_zh(record["abstract"]))

async def classify_and_translate_batch(records: list[dict], conn: aiosqlite.Connection, *, client: MiniMaxClient | None = None, batch_size: int | None = None, force_refresh: bool = False) -> list[dict]:
    if not records: return records
    client = client or default_client; batch_size = batch_size or settings.LLM_BATCH_SIZE
    normalized = [_ensure_input_minimum(r) for r in records]; cached = {}
    if not force_refresh:
        for r in normalized:
            p = await cache_get(conn, r["pmid"])
            if p is not None: cached[r["pmid"]] = p
    uncached = [r for r in normalized if r["pmid"] not in cached]
    try:
        chunks = [uncached[i:i+batch_size] for i in range(0,len(uncached),batch_size)]
        results = await asyncio.gather(*[_llm_classify_chunk(client,c) for c in chunks])
        for chunk, items in zip(chunks, results):
            by = {x.pmid:x for x in items}
            for r in chunk:
                item = by.get(r["pmid"]) or _heuristic_record(r)
                cached[r["pmid"]] = _build_cache_payload(item); await cache_set(conn,r["pmid"],cached[r["pmid"]],model=client.model)
            await conn.commit()
    except (LlmAuthError,LlmRateLimitError,LlmServerError,LlmError,LlmJsonParseError) as e:
        log.error("LLM failed; heuristic fallback: %s", e)
        for r in uncached:
            cached[r["pmid"]] = _build_cache_payload(_heuristic_record(r)); await cache_set(conn,r["pmid"],cached[r["pmid"]],model=client.model)
        await conn.commit()
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    for r in records:
        p = cached.get(str(r.get("pmid")))
        if not p: continue
        r.update(type=p["type"], disease=p["disease"], exclude=p["exclude"], exclude_reason=p.get("exclude_reason"), title_zh=p["title_zh"], abstract_zh=p.get("abstract_zh"), llm_classified_at=now, llm_model=client.model, llm_needs_review=int(p["title_zh"] == fallback_title_zh(r.get("title", ""))), llm_excluded=int(p["exclude"]))
        if p.get("exclude_reason"): r["llm_exclude_reason"] = p["exclude_reason"]
    return records

async def classify_one(record: dict, conn: aiosqlite.Connection, *, client: MiniMaxClient | None = None) -> dict:
    return (await classify_and_translate_batch([record], conn, client=client))[0]

if __name__ == "__main__":
    import sys; print("classify_and_translate_batch requires SQLite conn + records; use pipeline/daily.py instead"); sys.exit(0)
